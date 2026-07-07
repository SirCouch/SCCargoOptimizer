# SCCargoOptimizer v0.1.6

## Highlights

- Fixed the MER free-space pruning bug that made large cargo grids lose valid empty
  regions and leave boxes unplaced despite open room.
- Added an inference repair pass that places skipped items when a deterministic
  integer-grid scan finds a legal slot.
- Refreshed `ships_cargo_grids.json` with the latest ship grid data.
- Updated Modern-mode box visuals to Source-style development textures with grid
  markings, SCU size labels, and priority strips.
- Made the Optimize Packing control more visible and replaced it with a progress bar
  while packing runs.
- Removed Transparent mode and the Explode slider from the 3D viewer.

## Fixed

- Viewer theme persistence no longer gets overwritten by the viewer's boot-time
  defaults on launch.
- The grid layout editor can persist Clear Layout without re-creating layout entries
  during save.
- Dragging and rotating boxes in the viewer no longer reuses stale valid positions,
  loses completed tween state, or fights reset animations.
- Elevated and stacked grid layouts now resolve snapping and floor guards using grid
  height, not just X/Z footprint.
- Checkpoint discovery and packaging now require all three specialist model files.
- Overlapping grid cutouts are counted by union volume instead of double subtraction.

## Packaging

- Windows CPU package: `SCCargoOptimizer-v0.1.6-windows-cpu.zip`
- User presets remain under `%APPDATA%\StarCitizen\CargoOptimizer\`.

## Dev Notes

- Added `tests/test_mer_manager.py` covering the large-grid MER visibility regression.
- The deterministic repair pass records repaired placements in the result diagnostics.
