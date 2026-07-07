from collections.abc import Mapping, Sequence


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_triplet(values, field_name):
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be a 3-value sequence")
    if len(values) != 3:
        raise ValueError(f"{field_name} must contain exactly 3 values")
    triplet = []
    for value in values:
        if not _is_number(value):
            raise ValueError(f"{field_name} values must be numeric")
        triplet.append(float(value))
    return triplet


def _looks_like_dimensions(value):
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and len(value) == 3
        and all(_is_number(v) for v in value)
    )


def normalize_blockers(blocked):
    normalized = []
    for idx, blocker in enumerate(blocked or []):
        if isinstance(blocker, Mapping):
            position = _coerce_triplet(blocker.get("position"), f"blocked[{idx}].position")
            dimensions = _coerce_triplet(blocker.get("dimensions"), f"blocked[{idx}].dimensions")
            supports = blocker.get("supports", True)
        elif isinstance(blocker, Sequence) and not isinstance(blocker, (str, bytes)) and len(blocker) >= 2:
            position = _coerce_triplet(blocker[0], f"blocked[{idx}].position")
            dimensions = _coerce_triplet(blocker[1], f"blocked[{idx}].dimensions")
            supports = blocker[2] if len(blocker) > 2 else True
        else:
            raise ValueError(f"blocked[{idx}] must be a mapping or (position, dimensions) sequence")

        normalized.append({
            "position": position,
            "dimensions": dimensions,
            "supports": bool(supports),
        })
    return normalized


def normalize_layout(layout):
    """Optional viewer-only placement of a grid within its ship: where the
    grid's origin corner sits in ship space, same [x, y, z] axis convention
    as blocker positions (z vertical). Authored by tools/grid_layout_editor;
    packing itself never reads it — it is carried through so the 3D viewer
    can draw grids where they physically are in the ship."""
    if layout is None:
        return None
    if not isinstance(layout, Mapping):
        raise ValueError("layout must be a mapping with a 'position' field")
    return {"position": _coerce_triplet(layout.get("position"), "layout.position")}


def normalize_grid(grid, index=0):
    layout = None
    if isinstance(grid, Mapping):
        dimensions = _coerce_triplet(grid.get("dimensions"), f"grids[{index}].dimensions")
        name = str(grid.get("name", f"Grid {index + 1}"))
        blocked = normalize_blockers(grid.get("blocked", []))
        layout = normalize_layout(grid.get("layout"))
    elif _looks_like_dimensions(grid):
        dimensions = _coerce_triplet(grid, f"grids[{index}].dimensions")
        name = f"Grid {index + 1}"
        blocked = []
    elif isinstance(grid, Sequence) and not isinstance(grid, (str, bytes)) and len(grid) >= 2:
        dimensions = _coerce_triplet(grid[0], f"grids[{index}].dimensions")
        name = str(grid[1])
        blocked = normalize_blockers(grid[2] if len(grid) > 2 else [])
    else:
        raise ValueError(f"grids[{index}] must be a grid mapping, dimensions triplet, or (dimensions, name) sequence")

    normalized = {
        "dimensions": dimensions,
        "name": name,
        "blocked": blocked,
    }
    if layout is not None:
        normalized["layout"] = layout
    return normalized


def normalize_grids(grids_list):
    return [normalize_grid(grid, idx) for idx, grid in enumerate(grids_list or [])]


def _volume(dimensions):
    return float(dimensions[0]) * float(dimensions[1]) * float(dimensions[2])


def _blocked_union_volume(grid):
    grid_dims = grid["dimensions"]
    cuboids = []
    for blocker in grid["blocked"]:
        pos = blocker["position"]
        dims = blocker["dimensions"]
        lo = [max(0.0, float(pos[i])) for i in range(3)]
        hi = [min(float(grid_dims[i]), float(pos[i]) + float(dims[i])) for i in range(3)]
        if all(hi[i] > lo[i] for i in range(3)):
            cuboids.append((lo, hi))

    if not cuboids:
        return 0.0

    axes = [
        sorted({coord for lo, hi in cuboids for coord in (lo[axis], hi[axis])})
        for axis in range(3)
    ]
    total = 0.0
    for xi in range(len(axes[0]) - 1):
        x0, x1 = axes[0][xi], axes[0][xi + 1]
        xm = (x0 + x1) / 2
        for yi in range(len(axes[1]) - 1):
            y0, y1 = axes[1][yi], axes[1][yi + 1]
            ym = (y0 + y1) / 2
            for zi in range(len(axes[2]) - 1):
                z0, z1 = axes[2][zi], axes[2][zi + 1]
                zm = (z0 + z1) / 2
                if any(
                    lo[0] <= xm < hi[0] and
                    lo[1] <= ym < hi[1] and
                    lo[2] <= zm < hi[2]
                    for lo, hi in cuboids
                ):
                    total += (x1 - x0) * (y1 - y0) * (z1 - z0)
    return total


def grid_bounding_volume(grid):
    return _volume(normalize_grid(grid)["dimensions"])


def grid_blocked_volume(grid):
    normalized = normalize_grid(grid)
    return _blocked_union_volume(normalized)


def grid_usable_volume(grid):
    normalized = normalize_grid(grid)
    return max(0.0, _volume(normalized["dimensions"]) - grid_blocked_volume(normalized))


def total_usable_volume(grids_list):
    return sum(grid_usable_volume(grid) for grid in normalize_grids(grids_list))


def legacy_grid_pairs(grids_list):
    return [(tuple(grid["dimensions"]), grid["name"]) for grid in normalize_grids(grids_list)]


def _json_number(value):
    value = float(value)
    return int(value) if value.is_integer() else value


def serialize_grid(grid):
    normalized = normalize_grid(grid)
    result = {
        "dimensions": [_json_number(v) for v in normalized["dimensions"]],
        "name": normalized["name"],
    }
    if normalized["blocked"]:
        result["blocked"] = [
            {
                "position": [_json_number(v) for v in blocker["position"]],
                "dimensions": [_json_number(v) for v in blocker["dimensions"]],
                "supports": bool(blocker.get("supports", True)),
            }
            for blocker in normalized["blocked"]
        ]
    if normalized.get("layout"):
        result["layout"] = {
            "position": [_json_number(v) for v in normalized["layout"]["position"]],
        }
    return result


def serialize_grids(grids_list):
    return [serialize_grid(grid) for grid in normalize_grids(grids_list)]
