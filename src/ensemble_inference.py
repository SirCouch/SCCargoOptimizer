from pathlib import Path
import os
import threading
import torch
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
    def __init__(self, small_ckpt="small_actor_model.pt", medium_ckpt="medium_actor_model.pt",
                 large_ckpt="large_actor_model.pt", base_dir=None, checkpoint_dir=CHECKPOINT_DIR,
                 device=None, preload=True):
        print("Initializing Specialized Ensemble Router...")
        requested_device = str(device or os.environ.get("SC_CARGO_MODEL_DEVICE", "cpu")).lower()
        if requested_device == "auto":
            requested_device = "cuda" if torch.cuda.is_available() else "cpu"
        if requested_device == "cuda" and not torch.cuda.is_available():
            print("CUDA was requested but is unavailable; using CPU inference.")
            requested_device = "cpu"
        self.device = torch.device(requested_device)
        if self.device.type == "cpu":
            default_threads = min(4, os.cpu_count() or 1)
            cpu_threads = max(1, int(os.environ.get("SC_CARGO_CPU_THREADS", default_threads)))
            torch.set_num_threads(cpu_threads)
            try:
                torch.set_num_interop_threads(1)
            except RuntimeError:
                pass
        self.preload = preload
        self._actors = {"small": None, "medium": None, "large": None}
        self._load_errors = {}
        self._load_lock = threading.Lock()
        self._preload_started = False

        # Prefer the explicit checkpoints/ folder while keeping root-level
        # checkpoints as a fallback for older source trees and bundles.
        base_path = Path(base_dir) if base_dir is not None else _default_base_path(
            checkpoint_dir, (small_ckpt, medium_ckpt, large_ckpt))
        self.checkpoint_paths = {
            "small": _resolve_checkpoint(base_path, checkpoint_dir, small_ckpt),
            "medium": _resolve_checkpoint(base_path, checkpoint_dir, medium_ckpt),
            "large": _resolve_checkpoint(base_path, checkpoint_dir, large_ckpt),
        }

    @property
    def actor_small(self):
        return self._actors["small"]

    @property
    def actor_medium(self):
        return self._actors["medium"]

    @property
    def actor_large(self):
        return self._actors["large"]

    def _load_actor(self, tier):
        if self._actors[tier] is not None:
            return self._actors[tier]
        with self._load_lock:
            if self._actors[tier] is not None:
                return self._actors[tier]
            if tier in self._load_errors:
                return None
            try:
                print(f"Loading {tier.title()} Model from {self.checkpoint_paths[tier]}...")
                actor, _checkpoint = load_trained_model(
                    checkpoint_path=self.checkpoint_paths[tier], device=self.device)
                self._actors[tier] = actor
                print(f"{tier.title()} Model Online.")
            except Exception as exc:
                self._load_errors[tier] = exc
                print(f"Warning: {tier.title()} Model offline: {exc}")
        return self._actors[tier]

    def _start_preload(self, selected_tier):
        if not self.preload or self._preload_started:
            return
        self._preload_started = True

        def load_remaining():
            for tier in ("small", "medium", "large"):
                if tier != selected_tier:
                    self._load_actor(tier)

        threading.Thread(target=load_remaining, name="model-preloader", daemon=True).start()

    def route_manifest(self, ship_grids, manifest, diagnose=False):
        """
        Calculates the usable volume of the ship and routes the payload to the specialized model.
        """
        total_vol = total_usable_volume(ship_grids)

        print(f"Incoming Ship Usable Volume: {total_vol:g} SCU. Routing to specialized model...")

        if total_vol <= 64:
            selected_tier = "small"
        elif total_vol <= 256:
            selected_tier = "medium"
        else:
            selected_tier = "large"

        selected_actor = self._load_actor(selected_tier)
        if selected_actor is None:
            print("WARNING: Falling back to first available model due to offline specialized models.")
            for fallback_tier in ("large", "medium", "small"):
                selected_actor = self._load_actor(fallback_tier)
                if selected_actor is not None:
                    selected_tier = fallback_tier
                    break

        if selected_actor is None:
            raise ValueError("All specialized models are offline. Cannot route request.")

        print(f"Routed to: {selected_tier.upper()} MODEL on {self.device.type.upper()}")
        self._start_preload(selected_tier)
        return pack_single_manifest(selected_actor, ship_grids, manifest, device=self.device, diagnose=diagnose)
