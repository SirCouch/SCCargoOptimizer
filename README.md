# Star Citizen Cargo Optimizer

Desktop app for optimizing 3D cargo packing across Star Citizen ship grids using
trained Graph Attention Network (GAT) models.

## Features

- **Ship selector** for 40 Star Citizen ships from `ships_cargo_grids.json`
- **Cargo manifest** editor with priority groups (1–5), bulk-edit, and per-row volume tracking
- **Presets** — save/load named manifest configurations
- **3D viewer** (Three.js) with:
  - Click + drag to move boxes (horizontal slide; Shift+drag for vertical lift)
  - Collision detection — overlapping placements snap back
  - Snap-to-grid integer alignment
  - Unplaced items spawn in a staging zone for manual placement
  - Click an item for full details (priority, dimensions, grid)
  - Explode slider, transparency, grid-line overlay
- **Ensemble inference** — three size-specialized models (small / medium / large)
  selected automatically based on ship total SCU capacity

## Run from source

```bash
pip install PySide6 torch torch-geometric numpy
python src/desktop_app.py
```

## Build distributable .exe (Windows)

Two variants are built into separate folders so they don't conflict:

```cmd
build_cpu.bat    REM ~600 MB output. Works on any machine, CPU inference.
build_gpu.bat    REM ~3 GB output. Requires NVIDIA GPU + CUDA 12.x at runtime.
```

First run of either creates a dedicated venv (`.venv-cpu` or `.venv-gpu`) and
downloads its own PyTorch flavor — subsequent rebuilds reuse the venv.

Output:

```
dist/SCCargoOptimizer-cpu/SCCargoOptimizer.exe
dist/SCCargoOptimizer-gpu/SCCargoOptimizer.exe
```

Distribute by zipping the entire `SCCargoOptimizer-<variant>/` folder. User
data (presets, window state) is stored at
`%APPDATA%\StarCitizen\CargoOptimizer\` so it survives version updates.

Models (`small_gnn_model.pt` / `medium_gnn_model.pt` / `large_gnn_model.pt`) are
bundled in this repo. The training pipeline lives in the separate
[3d-Bin-packing-StarCitizen](https://github.com/SirCouch/3d-Bin-packing-StarCitizen)
repo — that's where you go to retrain or modify the models.

## Project structure

```
sc-cargo-optimizer/
├── ships_cargo_grids.json        # ship + grid definitions
├── small_gnn_model.pt            # specialized model: ≤64 SCU
├── medium_gnn_model.pt           # specialized model: 65–256 SCU
├── large_gnn_model.pt            # specialized model: >256 SCU
├── frontend/
│   ├── viewer.html               # Three.js scene + custom drag controls
│   └── vendor/three/             # Three.js + OrbitControls + DragControls
└── src/
    ├── desktop_app.py            # PySide6 GUI entry point
    ├── ensemble_inference.py     # routes to specialized model by ship volume
    ├── scu_manifest_generator.py # SCU container definitions
    └── packing_core/             # env + GNN models for inference
```