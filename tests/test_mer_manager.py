import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from packing_core.box3d import Box3D
from packing_core.mer_manager import MERManager


def _cell_visible(mers, x, y, z):
    cell = Box3D(
        torch.tensor([x, y, z], dtype=torch.float),
        torch.tensor([1, 1, 1], dtype=torch.float),
    )
    return any(mer.contains(cell) for mer in mers)


def test_large_grid_single_corner_box_keeps_all_remaining_cells_visible():
    manager = MERManager(torch.tensor([12, 12, 2], dtype=torch.float))
    manager.update(Box3D(
        torch.tensor([0, 0, 0], dtype=torch.float),
        torch.tensor([1, 1, 1], dtype=torch.float),
    ))

    visible = 0
    for x in range(12):
        for y in range(12):
            for z in range(2):
                if (x, y, z) == (0, 0, 0):
                    continue
                if _cell_visible(manager.mers, x, y, z):
                    visible += 1

    assert visible == (12 * 12 * 2) - 1
    assert manager.get_feasible_mers(torch.tensor([1, 1, 1], dtype=torch.float))
