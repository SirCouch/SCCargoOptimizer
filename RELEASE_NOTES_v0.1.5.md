# SCCargoOptimizer v0.1.5

## Highlights

- Updated the bundled small, medium, and large GNN specialist checkpoints.
- The app now prefers model files in `checkpoints/` and falls back to the root model
  files, so development runs and packaged releases load the intended checkpoints.
- Improved 3D viewer labels by placing grid and staging labels on the floor outside
  their areas and redrawing them correctly after theme changes.
- Improved shelf support handling for elevated blockers.
- Corrected the 890 Jump main cargo grid width.

## Packaging

- Windows CPU package: `SCCargoOptimizer-v0.1.5-windows-cpu.zip`
- User presets remain under `%APPDATA%\StarCitizen\CargoOptimizer\`.

## Dev Notes

- `checkpoints/` remains ignored as a local checkpoint drop folder.
- The tracked root-level model files were refreshed to match the v0.1.5 checkpoints
  so source fallback behavior matches the packaged release.
