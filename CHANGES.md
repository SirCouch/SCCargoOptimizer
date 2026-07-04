# Changes

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
