"""Repeatable local inference benchmark with MER growth reporting."""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from packing_core.utils import load_trained_model, pack_single_manifest


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ship", default="Hull-C")
    parser.add_argument("--items", type=int, default=200)
    parser.add_argument("--scu-type", default="1 SCU")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    parser.add_argument("--checkpoint", default="large_actor_model.pt")
    parser.add_argument("--threads", type=int, default=4)
    return parser.parse_args()


def main():
    args = parse_args()
    ships = json.loads((ROOT / "ships_cargo_grids.json").read_text())["ships"]
    ship = next((candidate for candidate in ships if candidate["name"] == args.ship), None)
    if ship is None:
        raise SystemExit(f"Unknown ship: {args.ship}")

    device = torch.device(args.device)
    if device.type == "cpu":
        torch.set_num_threads(max(1, args.threads))
    actor, _checkpoint = load_trained_model(ROOT / args.checkpoint, device=device)
    manifest = [{"scu_type": args.scu_type, "quantity": args.items, "priority": 1}]
    durations = []
    result = None
    for _repeat in range(args.repeats):
        started = time.perf_counter()
        result = pack_single_manifest(actor, ship["grids"], manifest, device=device)
        if device.type == "cuda":
            torch.cuda.synchronize()
        durations.append(time.perf_counter() - started)

    metrics = result["metrics"]
    summary = {
        "ship": args.ship,
        "items": args.items,
        "device": args.device,
        "seconds": {
            "min": min(durations),
            "median": statistics.median(durations),
            "max": max(durations),
        },
        "items_per_second": args.items / statistics.median(durations),
        "items_placed": metrics["items_placed"],
        "max_mer_count": metrics["max_mer_count"],
        "average_mer_count": metrics["average_mer_count"],
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
