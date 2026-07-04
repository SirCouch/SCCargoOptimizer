# Repository Guidelines

## Project Structure & Module Organization

This repository is a Windows desktop app for Star Citizen cargo packing. Core Python code lives in `src/`: `desktop_app.py` is the PySide6 entry point, `ensemble_inference.py` selects the appropriate GNN checkpoint, and `packing_core/` contains inference models and packing utilities. The 3D UI lives in `frontend/viewer.html` with vendored Three.js files under `frontend/vendor/three/`. Ship data is stored in `ships_cargo_grids.json`; bundled model checkpoints are `small_gnn_model.pt`, `medium_gnn_model.pt`, and `large_gnn_model.pt`. Packaged outputs go to `dist/`; build intermediates go to `build/`.

## Build, Test, and Development Commands

- `pip install PySide6 torch torch-geometric numpy`: install runtime dependencies for local development.
- `python src/desktop_app.py`: run the desktop app from source.
- `build_cpu.bat`: create/use `.venv-cpu`, install CPU dependencies, and package `dist\SCCargoOptimizer-cpu\SCCargoOptimizer.exe`.
- `build_gpu.bat`: create/use `.venv-gpu`, install CUDA PyTorch, and package `dist\SCCargoOptimizer-gpu\SCCargoOptimizer.exe`.
- `pyinstaller --noconfirm app.spec`: package with the currently active environment; set `BUILD_VARIANT=cpu` or `gpu` first if needed.

## Coding Style & Naming Conventions

Use 4-space indentation for Python. Follow existing naming: modules and functions use `snake_case`, classes use `PascalCase`, and constants such as `APP_NAME` or `MAX_PRIORITY` use uppercase. Keep resource paths resolved through `Path` or existing helper functions so development and PyInstaller builds both work. In `frontend/viewer.html`, keep CSS variables in `:root` and use concise DOM helper functions instead of introducing external dependencies.

## Testing Guidelines

There is no committed automated test suite yet. For Python changes, at minimum run `python -m py_compile src\desktop_app.py src\ensemble_inference.py` and smoke-test with `python src/desktop_app.py`. When adding tests, prefer `pytest` under `tests/` with files named `test_*.py`, and cover packing logic separately from GUI behavior where possible.

## Commit & Pull Request Guidelines

Recent history uses short, descriptive subjects such as `README: add install-from-release instructions` and release-style messages like `v0.1.2 - box rotation, priority MER fix`. Keep commits focused and mention the affected area first when helpful. Pull requests should describe the user-visible change, list manual validation steps, note packaging impact, and include screenshots or recordings for viewer/UI changes.

## Security & Configuration Tips

Do not commit user presets or local environment folders. Presets are written under `%APPDATA%\StarCitizen\CargoOptimizer\`. Treat model checkpoint updates as large binary changes: document their source and expected behavior in the PR.
