# Changes

## v0.1.7 - 2026-07-09

### New
- **Selectable box designs.** Modern mode now exposes all modern cargo-box concepts
  in the viewer's Boxes selector, and 8-Bit mode adds selectable pixel-art crate
  variants alongside the classic crate.
- **Box concept reference page.** Added `frontend/box_concepts.html` as a visual
  reference for the implemented modern and 8-Bit box styles.

### Fixed
- **Priority-relaxed packing fallback.** If strict model/MER inference and the
  deterministic repair scan cannot place an item because of unload-priority ordering,
  inference now retries with priority relaxed while keeping overlap, support, and
  stack-weight constraints hard. Diagnostics mark these placements as placed out of
  priority order instead of leaving cargo behind.
- **Large cargo ordering.** The big-item tier now sorts by priority before volume
  inside that tier, so high-priority 32 SCU boxes are considered before lower-priority
  large boxes.
- **Theme-consistent splitter resize.** The desktop panel resize handle now uses the
  same geometry, visible styling, and pane resize bounds in Modern and 8-Bit themes.

## v0.1.6 - 2026-07-07

### New
- **Source development textures for cargo boxes.** Modern-mode cargo boxes now use
  procedural Source-style development panels with grid markings, face labels, SCU
  size text, and a small priority strip. The 8-Bit box style remains unchanged.
- **Clear packing progress state.** The Optimize control is now a prominent
  call-to-action button and swaps to an indeterminate progress bar while packing runs.
- **Updated ship grid data.** `ships_cargo_grids.json` has been refreshed with the
  latest ship/grid updates.

### Fixed
- **Large-grid MER geometry loss.** Replaced the MER pruning overlap heuristic with
  true containment checks. Large grids no longer lose valid empty regions after early
  placements, which was causing boxes to be marked unplaceable despite visible space.
- **Inference repair fallback.** If the model/MER path skips an item but a deterministic
  integer-grid scan finds a legal placement, inference now places the item and records
  the repair in diagnostics instead of leaving it unplaced.
- **Viewer startup theme sync.** The desktop app now ignores the viewer's boot-time
  default theme broadcast until the saved host theme has been pushed into the page.
- **Grid editor Clear Layout.** The dev grid editor can now persist a cleared layout
  instead of re-baking auto-row positions during save.
- **Viewer drag/drop edge cases.** Fixed stale mid-drag rotation fallback positions,
  cancelled tween state, reset-animation drag conflicts, stacked-grid snapping, and
  elevated-grid floor guards.
- **Checkpoint discovery and packaging.** Model discovery now probes all three
  specialist checkpoint names, and PyInstaller fails fast if any required checkpoint
  is missing instead of silently packaging a partial model set.
- **Blocked-volume accounting.** Overlapping grid cutouts are now counted as a union
  instead of double-subtracting shared volume.
- **Debug visualization labels.** Cargo labels in debug plots now skip seeded blockers
  so numbering matches packed cargo IDs.

### Removed
- Removed the viewer Transparent mode and Explode slider. Cargo boxes now render solid
  and stay at their actual model/manual positions.

## v0.1.5 - 2026-07-05

### New
- **Fresh specialist checkpoints.** Updated the small, medium, and large GNN model
  weights. The loader now prefers `checkpoints/` when present and falls back to the
  root-level model files for older source trees and bundles.
- **Release packaging alignment.** PyInstaller now bundles `checkpoints/` when the
  folder exists, keeping local release builds on the same model files that the app
  uses in development.

### Fixed
- **Viewer floor labels.** Grid and staging labels now sit on the floor just outside
  their areas instead of floating above the cargo space, and palette changes redraw
  label textures correctly.
- **Shelf support behavior.** Elevated supporting blockers now act as shelves only
  when the item cannot fit below them, avoiding unnecessary vertical snapping.
- **890 Jump grid dimensions.** Corrected the main cargo grid width from 8 to 6 SCU.

## v0.1.4 - 2026-07-04

### New
- **Ship grid layouts + dev layout editor.** Grids can carry an optional
  `layout: {position: [x, y, z]}` (same axis convention as blockers, z vertical) placing
  them where they physically sit in the ship; all 113 committed cargo grids now include
  saved layout positions. The 3D viewer renders laid-out grids at those positions —
  including elevated decks, whose floors act as support surfaces for drag & drop — and
  falls back to the old auto-row for grids without one. Layouts are
  authored with `python tools/grid_layout_editor.py`, a dev-only tool (not bundled by
  `app.spec`): drag grids on the deck plane, Shift-drag to raise/lower, `R` rotates 90°
  (baked into `dimensions`/`blocked` so the app only ever translates), snap to 1/0.5 SCU,
  and Save writes every grid position in `ships_cargo_grids.json` with a `.bak` backup.
  Packing itself ignores `layout` entirely.
- **App-wide theming.** Theme is now an app-level setting: a Theme box in the main
  window (Style + Palette) restyles the entire desktop app and the 3D viewer together,
  and the pickers inside the viewer's bottom bar drive the same sync in the other
  direction (broadcast via the viewer page title). The Qt stylesheet is regenerated from
  the matching palette (all 8 manufacturer palettes, plus a square-cornered monospace
  variant for 8-Bit mode) and the choice persists in `QSettings` across launches.
- **Structural lattice meshes for cutouts.** Blocked cuboids render as strut-truss
  wireframes — cage bars at every 1-SCU grid line plus per-cell diagonal bracing — sized
  to the blocker dimensions from `ships_cargo_grids.json`, instead of plain translucent
  boxes. Blockers with `supports: true` render in the neutral wire color with a visible
  top shelf plate; non-supporting cutouts render in the palette's danger color.

### Fixed
- **8-Bit mode blurriness.** The retro style previously rendered at low resolution and
  reduced the effective detail of the cargo view. The 8-Bit theme now keeps the 3D scene
  at full canvas resolution while retaining the chunky UI, scanlines, lighting, and box
  texture styling.
- Blocker meshes now recolor when switching palettes (previously kept the old palette
  until the next optimize run).
- `ships_cargo_grids.json`: fixed duplicate grid names (Carrack had two grids named "1",
  Starlancer MAX had two "FWDRight"; renamed to "2" and "AFTLeft").

### Changed
- `AGENTS.md` is no longer tracked; it is ignored as local agent configuration.

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
