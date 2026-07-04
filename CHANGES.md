# Changes

## v0.1.3

### New
- **Cargo grid cutouts.** Ship grids can now define optional `blocked` cuboids with
  `position`, `dimensions`, and `supports` fields. Inference treats these as fixed
  obstacles, carves them out of MER space, and excludes them from placement output.
- **Usable-volume routing and metrics.** Model routing, utilization, manifest generation,
  rewards, and capacity display now use bounding volume minus blocked volume.
- **Viewer blocker support.** The 3D viewer preserves object-shaped grid payloads,
  renders cutouts as fixed blockers, and includes them in drag collision/support checks.

### Changed
- Desktop payload handling now keeps full grid metadata instead of reducing grids to
  `[dimensions, name]`.
### New — visual styles & manufacturer palettes
Style selector (Modern / 8-Bit). The new 8-Bit style renders the scene at low resolution with pixelated upscaling and scanlines, flattens the lighting, and paints every box with a beveled unit-cell texture — an 8 SCU crate visibly reads as its 2×2×2 blocks. The overlay UI switches to square corners, hard shadows and monospace.
Palette selector with 8 schemes inspired by ship manufacturers' in-game UI: Default, Drake, Origin (light), RSI, Aegis, MISC, Crusader, Argo. A palette retints everything — background, floors, panels, highlights, ghost/collision colors, grid labels and the per-priority cargo colors.
Priority color ramps were generated in OKLCH and validated per-surface for lightness band, chroma floor, colorblind (CVD) separation and contrast; borderline pairs are covered by the labeled legend and box outlines.
Choices persist across sessions (localStorage) and are scriptable via window.setTheme(style, palette).
Fixed: the staging-zone label ("Unplaced — drag to place") could be clipped by its texture canvas and hidden behind the unplaced pile; it now auto-fits and sits in front of the staging zone.

### Improved — 3D viewer interaction overhaul
Drop preview ghost. While dragging, a ghost outline marks the exact cell the box will land in — green when free, red when blocked.
Nearest-free-cell drops. Dropping onto an occupied cell no longer bounces the box back; it lands in the closest free snapped cell (searching up to 2 cells out) and only reverts when everything nearby is blocked.
Smooth animations. Snap-on-drop, blocked-drop reverts, Reset Positions, Reset View and camera focus are short eased animations instead of teleports.
Camera. Double-click a box to focus the orbit pivot on it; scroll zooms toward the cursor; the camera can no longer orbit below the floor; render resolution is capped at 2× DPI for smoother frame rates on high-DPI screens.
Keyboard placement. Arrow keys nudge the selected box one cell at a time (camera-relative, so "left" is left on screen); PgUp/PgDn lift and lower it; R now also rotates the box you are currently dragging.
Hover highlight on boxes, and orbiting the camera no longer clears the current selection (previously any camera drag closed the inspector panel).

### Fixed
Inspector Position readout used the first grid's origin for items in any grid and reported the box center instead of its cell corner — it now shows the correct grid-local integer cell.
Dragging, nudging or rotating a box while the Explode slider was active corrupted its stored position; manual moves now compose correctly with the explode view.
Selection/drag/collision highlights were separate cloned materials that could fight and leave boxes stuck opaque or tinted; all highlight state now derives from one place.
An unplaced item dragged into a grid kept its "Unplaced" badge forever; the badge now follows where the box actually is (Placed / Unplaced / Outside Grid).

## v0.1.2

### New
- **Box rotation in the 3D viewer.** Select a box, press `R` (or click *Rotate 90°* in the
  inspector panel) to rotate around the vertical axis. Matches the model's training-time
  Z-axis rotation constraint (height locked, X/Y footprint swapped). Rotations that would
  overlap a neighbouring box revert automatically. Square footprints (1×1, 2×2) get the
  button greyed out since the rotation would be a visual no-op.

### Fixed
- **Priority-driven packing collapse.** Manifests with mixed priorities were dropping
  small items that the layout had room for. Same cargo, four priority tiers, on Polaris:
  47.8% placement → 100% placement. Two underlying bugs:
  - `MERManager._filter_redundant` discarded any empty pocket smaller than 1% of the
    container volume. On a 288-vol grid, that culled every 1- and 2-SCU MER. Threshold
    is now an absolute floor of 1.0 (the smallest packable item).
  - `DRLBinPackingEnv.get_feasibility_mask` only checked the MER corner. If the corner
    failed a constraint (priority, support, neighbour overlap) the whole MER was hidden
    from the model — even when an interior anchor would have worked. The mask now falls
    through to `_find_valid_anchor_in_mer`; `step()` does the same so the placement
    actually lands at the valid anchor.

  Net effect: harder priority configurations that previously dropped 5–24 items now
  pack cleanly. Existing trained checkpoints unchanged — this is an inference-side
  fix only.

## v0.1.1
- Better snap, auto-stack on drag, in-app help

## v0.1.0
- First packaged release
