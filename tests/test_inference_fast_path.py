import sys
import random
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from packing_core.drl_env import DRLBinPackingEnv
from packing_core.box3d import Box3D
from packing_core.utils import pack_single_manifest


class FirstFeasibleActor(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.device_anchor = torch.nn.Parameter(torch.zeros(()), requires_grad=False)

    def action_logits(self, data, feasibility_mask=None):
        count = len(feasibility_mask)
        logits = torch.arange(count, 0, -1, dtype=torch.float, device=self.device_anchor.device)
        mask = torch.as_tensor(feasibility_mask, dtype=torch.bool, device=logits.device)
        return logits.masked_fill(~mask, float("-inf"))


def test_cached_action_commit_does_not_revalidate_or_build_terminal_graph(monkeypatch):
    env = DRLBinPackingEnv(grids_list=[((2, 2, 1), "Main")])
    env.reset(cargo_manifest=[(1, 1, 1, 10, 1)])
    mask = env.get_feasibility_mask()
    action = int(mask.nonzero()[0][0])

    monkeypatch.setattr(
        env,
        "_resolve_action",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("action was revalidated")),
    )
    monkeypatch.setattr(
        env,
        "_build_graph_state",
        lambda: (_ for _ in ()).throw(AssertionError("terminal graph was built")),
    )

    done, info = env.commit_action(action)

    assert done is True
    assert info["feasible"] is True
    assert env.successful_placements == 1


def test_square_footprint_feasibility_is_resolved_once_for_both_rotations(monkeypatch):
    env = DRLBinPackingEnv(grids_list=[((4, 4, 1), "Main")])
    env.reset(cargo_manifest=[(2, 2, 1, 40, 1)])
    calls = 0
    original = env._resolve_action

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(env, "_resolve_action", counted)
    mask = env.get_feasibility_mask()

    assert mask.tolist() == [True, True]
    assert calls == 1


def test_pack_processes_manifest_beyond_old_500_item_limit():
    actor = FirstFeasibleActor()
    result = pack_single_manifest(
        actor,
        [((501, 1, 1), "Main")],
        [{"scu_type": "1 SCU", "quantity": 501, "priority": 1}],
        device=torch.device("cpu"),
    )

    assert result["metrics"]["items_placed"] == 501
    assert result["unplaced_items"] == []


def test_training_step_guard_allows_the_thousandth_manifest_item():
    env = DRLBinPackingEnv(grids_list=[((1, 1, 1), "Main")])
    env.reset(cargo_manifest=[(1, 1, 1, 10, 1)] * 1001)

    done = False
    for _ in range(1000):
        _state, _reward, done, _info = env.step(999)

    assert done is False
    assert env.current_item_idx == 1000


def test_candidate_repair_matches_exhaustive_small_grid_search():
    for seed in range(12):
        rng = random.Random(seed)
        env = DRLBinPackingEnv(grids_list=[((4, 4, 3), "Main")])
        env.reset(cargo_manifest=[])
        floor_cells = [(x, y) for x in range(4) for y in range(4)]
        rng.shuffle(floor_cells)
        for x, y in floor_cells[:5]:
            env._commit_box(Box3D((x, y, 0), (1, 1, 1)), 10, rng.randint(1, 2), 0)

        item = (2, 1, 1, 10, rng.randint(1, 2))
        exhaustive = None
        for x in range(3):
            for y in range(4):
                for z in range(3):
                    if env._check_constraints_fast((x, y, z), item[:3], item[3], item[4], 0):
                        exhaustive = (x, y, z)
                        break
                if exhaustive is not None:
                    break
            if exhaustive is not None:
                break

        candidate = env.find_candidate_placement(item)
        assert (candidate is not None) == (exhaustive is not None)
        if candidate is not None:
            assert env._check_constraints_fast(
                candidate[1:4], candidate[5:8], item[3], item[4], candidate[0])
