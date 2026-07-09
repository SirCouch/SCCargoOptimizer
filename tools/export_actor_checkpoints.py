"""Export compact inference-only actor checkpoints from training checkpoints."""

from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]


def _source_path(name):
    checkpoint_copy = ROOT / "checkpoints" / name
    return checkpoint_copy if checkpoint_copy.exists() else ROOT / name


def export_checkpoint(source, destination):
    checkpoint = torch.load(source, map_location="cpu", weights_only=False)
    actor_weights = checkpoint["actor_state_dict"]
    node_feature_dim = 13
    hidden_dim = 128
    for key, value in actor_weights.items():
        if key.endswith("conv1.lin.weight"):
            node_feature_dim = value.shape[1]
        elif key.endswith("score_head.0.weight"):
            hidden_dim = value.shape[1]

    compact = {
        "format_version": 1,
        "node_feature_dim": node_feature_dim,
        "hidden_dim": hidden_dim,
        "actor_state_dict": actor_weights,
    }
    if "episode" in checkpoint:
        compact["episode"] = checkpoint["episode"]
    torch.save(compact, destination)
    print(f"{source.name} -> {destination.name} ({destination.stat().st_size:,} bytes)")


def main():
    for tier in ("small", "medium", "large"):
        export_checkpoint(
            _source_path(f"{tier}_gnn_model.pt"),
            ROOT / f"{tier}_actor_model.pt",
        )


if __name__ == "__main__":
    main()
