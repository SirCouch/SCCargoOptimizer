# Star Citizen Cargo Optimizer

Desktop app for optimizing 3D cargo packing across Star Citizen ship grids using
trained Graph Attention Network (GAT) models.

## Features

- **Ship selector** for 43 Star Citizen ships from `ships_cargo_grids.json`
- **Cargo manifest** editor with priority groups (1–5), bulk-edit, and per-row volume tracking
- **Presets** — save/load named manifest configurations
- **3D viewer** (Three.js) with:
  - Click + drag to move boxes (horizontal slide; Shift+drag for vertical lift)
  - Collision detection — overlapping placements snap back
  - Snap-to-grid integer alignment
  - Unplaced items spawn in a staging zone for manual placement
  - Click an item for full details (priority, dimensions, grid)
  - Source-style development textures for modern cargo boxes
  - Grid-line overlay
- **Ensemble inference** — three size-specialized models (small / medium / large)
  selected automatically based on ship total SCU capacity

## Install

### From a release (recommended)

1. Go to [Releases](https://github.com/SirCouch/SCCargoOptimizer/releases) and download
   the latest `SCCargoOptimizer-vX.Y.Z-windows-cpu.zip`.
2. Right-click the zip.
3. Extract the zip anywhere — e.g. `C:\Tools\SCCargoOptimizer\`. The folder is
   self-contained; nothing else needs to be installed.
4. Run `SCCargoOptimizer.exe` from inside the extracted folder. First launch may take
   a few seconds while Qt and the model files load.

Windows SmartScreen will warn that the publisher is unverified — click **More info →
Run anyway**. The build is unsigned. User data (presets, window state) is written to
`%APPDATA%\StarCitizen\CargoOptimizer\` and survives upgrades.

To upgrade, delete the old folder and extract the new zip. Your presets stay put.

### From source

```bash
pip install PySide6 torch torch-geometric numpy
python src/desktop_app.py
```

Inference defaults to CPU because the sequential graphs are faster there on the
supported Windows hardware. A CUDA build can opt in with
`SC_CARGO_MODEL_DEVICE=cuda`; geometry remains on CPU in either mode.
CPU inference uses four Torch worker threads by default; override it with
`SC_CARGO_CPU_THREADS` when benchmarking a different processor.

Use `build_cpu.bat` for the release CPU-only package. The build uses an isolated
CPU PyTorch environment and writes `dist\SCCargoOptimizer-cpu\SCCargoOptimizer.exe`.

Inference actors (`small_actor_model.pt` / `medium_actor_model.pt` /
`large_actor_model.pt`) are bundled in this repo. Full training checkpoints can
be converted with `python tools/export_actor_checkpoints.py`. The training pipeline lives in the separate
[3d-Bin-packing-StarCitizen](https://github.com/SirCouch/3d-Bin-packing-StarCitizen)
repo — that's where you go to retrain or modify the models.

## Dev tools

Ship cargo grid layouts can be edited with the dev-only layout editor:

```bash
python tools/grid_layout_editor.py
```

The editor opens a local browser tool for moving each ship's cargo grids and
saving optional `layout: {position: [x, y, z]}` metadata into
`ships_cargo_grids.json`. Rotation is baked into grid `dimensions` and blocked
cuboids, so the app only translates laid-out grids at runtime. It writes
`ships_cargo_grids.json.bak` before saving. The `tools/` folder is not
referenced by `app.spec`, so this editor is not bundled into the final desktop
app.

## Project structure

```
sc-cargo-optimizer/
├── ships_cargo_grids.json        # ship + grid definitions
├── small_actor_model.pt          # specialized actor: ≤64 SCU
├── medium_actor_model.pt         # specialized actor: 65–256 SCU
├── large_actor_model.pt          # specialized actor: >256 SCU
├── frontend/
│   ├── viewer.html               # Three.js scene + custom drag controls
│   └── vendor/three/             # Three.js + OrbitControls + DragControls
├── tools/
│   └── grid_layout_editor.py     # dev-only grid layout editor
└── src/
    ├── desktop_app.py            # PySide6 GUI entry point
    ├── ensemble_inference.py     # routes to specialized model by ship volume
    ├── scu_manifest_generator.py # SCU container definitions
    └── packing_core/             # env + GNN models for inference
```
