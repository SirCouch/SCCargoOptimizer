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
- Added repository contributor guidance in `AGENTS.md`.

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
