# SCCargoOptimizer v0.1.4

## Highlights

- Added saved ship-space cargo grid layouts for all 113 grids in `ships_cargo_grids.json`.
- Added a dev-only grid layout editor at `tools/grid_layout_editor.py`; it is not bundled in the packaged app.
- The 3D viewer now renders laid-out grids in their saved ship positions, including elevated decks as support surfaces.
- Added app-wide Modern / 8-Bit styling and manufacturer palettes synced between the desktop app and viewer.
- Blocked cuboids now render as structural lattice meshes instead of plain translucent boxes.
- Fixed 8-Bit mode clarity by keeping the 3D scene at full canvas resolution.

## Packaging

- Windows CPU package: `SCCargoOptimizer-v0.1.4-windows-cpu.zip`
- User presets remain under `%APPDATA%\StarCitizen\CargoOptimizer\`.

## Dev Notes

- `AGENTS.md` is no longer tracked and is ignored as local agent configuration.
- The dev layout editor saves `layout: {position: [x, y, z]}` metadata and writes `ships_cargo_grids.json.bak` before overwriting the ship data file.
