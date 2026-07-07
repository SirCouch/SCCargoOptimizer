from pathlib import Path
import torch
import numpy as np
from packing_core.grid_utils import total_usable_volume
from packing_core.utils import load_trained_model, pack_single_manifest


CHECKPOINT_DIR = "checkpoints"


def _checkpoint_candidates(base_path, checkpoint_dir, checkpoint_name):
    checkpoint_path = Path(checkpoint_name)
    if checkpoint_path.is_absolute():
        return [checkpoint_path]
    return [
        base_path / checkpoint_dir / checkpoint_path,
        base_path / checkpoint_path,
    ]


def _default_base_path(checkpoint_dir, probe_checkpoints):
    cwd = Path.cwd()
    project_root = Path(__file__).resolve().parent.parent
    if isinstance(probe_checkpoints, (str, Path)):
        probe_checkpoints = (probe_checkpoints,)
    for base_path in (cwd, cwd.parent, project_root):
        for probe_checkpoint in probe_checkpoints:
            if any(candidate.exists() for candidate in _checkpoint_candidates(
                    base_path, checkpoint_dir, probe_checkpoint)):
                return base_path
    return cwd


def _resolve_checkpoint(base_path, checkpoint_dir, checkpoint_name):
    candidates = _checkpoint_candidates(base_path, checkpoint_dir, checkpoint_name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


class EnsembleRouter:
    def __init__(self, small_ckpt="small_gnn_model.pt", medium_ckpt="medium_gnn_model.pt",
                 large_ckpt="large_gnn_model.pt", base_dir=None, checkpoint_dir=CHECKPOINT_DIR):
        print("Initializing Specialized Ensemble Router...")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Prefer the explicit checkpoints/ folder while keeping root-level
        # checkpoints as a fallback for older source trees and bundles.
        base_path = Path(base_dir) if base_dir is not None else _default_base_path(
            checkpoint_dir, (small_ckpt, medium_ckpt, large_ckpt))
        self.checkpoint_paths = {
            "small": _resolve_checkpoint(base_path, checkpoint_dir, small_ckpt),
            "medium": _resolve_checkpoint(base_path, checkpoint_dir, medium_ckpt),
            "large": _resolve_checkpoint(base_path, checkpoint_dir, large_ckpt),
        }

        # Load models
        try:
            print(f"Loading Small Model from {self.checkpoint_paths['small']}...")
            self.actor_small, _ = load_trained_model(
                checkpoint_path=self.checkpoint_paths["small"], device=self.device)
            print("Small Model Online.")
        except Exception as e:
            print(f"Warning: Small Model offline: {e}")
            self.actor_small = None

        try:
            print(f"Loading Medium Model from {self.checkpoint_paths['medium']}...")
            self.actor_medium, _ = load_trained_model(
                checkpoint_path=self.checkpoint_paths["medium"], device=self.device)
            print("Medium Model Online.")
        except Exception as e:
            print(f"Warning: Medium Model offline: {e}")
            self.actor_medium = None

        try:
            print(f"Loading Large Model from {self.checkpoint_paths['large']}...")
            self.actor_large, _ = load_trained_model(
                checkpoint_path=self.checkpoint_paths["large"], device=self.device)
            print("Large Model Online.")
        except Exception as e:
            print(f"Warning: Large Model offline: {e}")
            self.actor_large = None

    def route_manifest(self, ship_grids, manifest, diagnose=False):
        """
        Calculates the usable volume of the ship and routes the payload to the specialized model.
        """
        total_vol = total_usable_volume(ship_grids)

        print(f"Incoming Ship Usable Volume: {total_vol:g} SCU. Routing to specialized model...")

        # Select model based on breakpoints
        if total_vol <= 64 and self.actor_small is not None:
            print("Routed to: SMALL MODEL")
            selected_actor = self.actor_small
        elif total_vol <= 256 and self.actor_medium is not None:
            print("Routed to: MEDIUM MODEL")
            selected_actor = self.actor_medium
        elif self.actor_large is not None:
            print("Routed to: LARGE MODEL")
            selected_actor = self.actor_large
        else:
            # Fallback
            print("WARNING: Falling back to first available model due to offline specialized models.")
            selected_actor = self.actor_large or self.actor_medium or self.actor_small

        if selected_actor is None:
            raise ValueError("All specialized models are offline. Cannot route request.")

        # Run inference using the selected specialist
        return pack_single_manifest(selected_actor, ship_grids, manifest, device=self.device, diagnose=diagnose)
