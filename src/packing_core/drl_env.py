from dataclasses import dataclass
from itertools import product

import numpy as np
import torch
from torch_geometric.data import Data

from scu_manifest_generator import generate_scu_manifest, manifest_to_item_list
from .box3d import Box3D, _integer_triplet
from .grid_utils import grid_blocked_volume, normalize_grids
from .mer_manager import MERManager


@dataclass(frozen=True, slots=True)
class ResolvedAction:
    action_idx: int
    grid_idx: int
    mer_idx: int
    rotation: int
    position: tuple[int, int, int]
    dimensions: tuple[int, int, int]


class DRLBinPackingEnv:
    NODE_TYPE_CONTAINER = 0
    NODE_TYPE_PLACED = 1
    NODE_TYPE_ITEM = 2
    NODE_TYPE_MER = 3
    NODE_TYPE_SHIP = 4

    def __init__(self, grids_list=None, max_stack_weight=100000.0):
        if grids_list is None:
            grids_list = [((10, 10, 10), "Main")]

        self.grid_defs = normalize_grids(grids_list)
        self.grids = [
            {
                "dims": _integer_triplet(grid["dimensions"], "grid dimensions"),
                "name": grid["name"],
                "blocked": grid["blocked"],
            }
            for grid in self.grid_defs
        ]
        self.grids_list = [(grid["dims"], grid["name"]) for grid in self.grids]
        self.grid_bounding_volumes = [
            dims[0] * dims[1] * dims[2]
            for dims, _name in self.grids_list
        ]
        self.grid_blocked_volumes = [grid_blocked_volume(grid) for grid in self.grid_defs]
        self.grid_volumes = [
            max(0.0, bounding - blocked)
            for bounding, blocked in zip(self.grid_bounding_volumes, self.grid_blocked_volumes)
        ]
        self.total_ship_volume = sum(self.grid_volumes)
        self.max_stack_weight = max_stack_weight

        self.cargo_manifest = []
        self.current_item_idx = 0
        self.current_item = None
        self.successful_placements = 0
        self.total_items = 0
        self._initialize_runtime_state()

    def _initialize_runtime_state(self):
        self.steps_in_episode = 0
        self.placed_items = []
        self.mer_managers = [MERManager(grid["dims"]) for grid in self.grids]
        self._cached_mers = None
        self._resolved_actions = {}
        self._grid_placed_vol = [0.0] * len(self.grids)
        self._grid_placed_count = [0] * len(self.grids)
        self._occupancy = [np.full(grid["dims"], -1, dtype=np.int32) for grid in self.grids]
        self._support_mask = [np.zeros(grid["dims"], dtype=np.bool_) for grid in self.grids]
        self._priority_y_bounds = [dict() for _grid in self.grids]
        self._placed_node_features = []
        self._placed_node_positions = []
        self._placed_touch_edges = []

    def reset(self, cargo_manifest=None, difficulty=None):
        self._initialize_runtime_state()
        self._seed_blockers()

        if cargo_manifest is None:
            total_vol = int(sum(self.grid_volumes))
            manifest = generate_scu_manifest(
                grid_dims=(total_vol, 1, 1),
                grids_list=self.grid_defs,
                target_fill_ratio=0.7,
                difficulty=difficulty if difficulty is not None else "medium",
                priority_groups=3,
            )
            self.cargo_manifest = manifest_to_item_list(manifest)
        else:
            self.cargo_manifest = cargo_manifest

        self.current_item_idx = 0
        self.successful_placements = 0
        self.total_items = len(self.cargo_manifest)
        self.current_item = (
            self._get_item_features(self.cargo_manifest[0])
            if self.cargo_manifest else None
        )
        return self._build_graph_state()

    def _placement_record(self, box, weight, priority, grid_idx, is_blocker=False, supports=True):
        return {
            "box": box,
            "weight": float(weight),
            "priority": int(priority),
            "grid_idx": int(grid_idx),
            "x1": box.x1,
            "y1": box.y1,
            "z1": box.z1,
            "x2": box.x2,
            "y2": box.y2,
            "z2": box.z2,
            "is_blocker": bool(is_blocker),
            "supports": bool(supports),
        }

    def _seed_blockers(self):
        for grid_idx, grid in enumerate(self.grids):
            container = Box3D((0, 0, 0), grid["dims"])
            for blocker in grid.get("blocked", []):
                blocker_box = Box3D(blocker["position"], blocker["dimensions"])
                if not container.contains(blocker_box):
                    raise ValueError(
                        f"Blocked cuboid on grid '{grid['name']}' is outside the grid bounds: {blocker}"
                    )
                self._commit_box(
                    blocker_box,
                    weight=0.0,
                    priority=0,
                    grid_idx=grid_idx,
                    is_blocker=True,
                    supports=blocker.get("supports", True),
                )

    def _get_item_features(self, item_tuple):
        width, length, height, weight, priority = item_tuple
        dimensions = tuple(sorted(_integer_triplet((width, length, height), "item dimensions"), reverse=True))
        return {
            "dimensions": dimensions,
            "weight": float(weight),
            "priority": int(priority),
        }

    def _get_all_mers(self):
        if self._cached_mers is None:
            self._cached_mers = [
                {"grid_idx": grid_idx, "mer_idx": mer_idx, "box": mer}
                for grid_idx, manager in enumerate(self.mer_managers)
                for mer_idx, mer in enumerate(manager.mers)
            ]
        return self._cached_mers

    def _invalidate_action_caches(self):
        self._cached_mers = None
        self._resolved_actions = {}

    @staticmethod
    def _boxes_touch(first, second, eps=0.001):
        x_overlap = first["x1"] < second["x2"] and first["x2"] > second["x1"]
        y_overlap = first["y1"] < second["y2"] and first["y2"] > second["y1"]
        z_overlap = first["z1"] < second["z2"] and first["z2"] > second["z1"]
        x_touch = abs(first["x1"] - second["x2"]) < eps or abs(first["x2"] - second["x1"]) < eps
        y_touch = abs(first["y1"] - second["y2"]) < eps or abs(first["y2"] - second["y1"]) < eps
        z_touch = abs(first["z1"] - second["z2"]) < eps or abs(first["z2"] - second["z1"]) < eps
        return (
            (x_touch and y_overlap and z_overlap) or
            (y_touch and x_overlap and z_overlap) or
            (z_touch and x_overlap and y_overlap)
        )

    def _cache_placed_graph_entry(self, placed_idx):
        placed = self.placed_items[placed_idx]
        self._placed_node_features.append([
            self.NODE_TYPE_PLACED,
            placed["x2"] - placed["x1"],
            placed["y2"] - placed["y1"],
            placed["z2"] - placed["z1"],
            placed["weight"],
            placed["priority"],
            placed["grid_idx"],
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        ])
        self._placed_node_positions.append([placed["x1"], placed["y1"], placed["z1"]])
        for other_idx, other in enumerate(self.placed_items[:placed_idx]):
            if other["grid_idx"] == placed["grid_idx"] and self._boxes_touch(other, placed):
                self._placed_touch_edges.append((other_idx, placed_idx))

    def _commit_box(self, box, weight, priority, grid_idx, is_blocker=False, supports=True):
        occupancy = self._occupancy[grid_idx]
        region = np.s_[box.x1:box.x2, box.y1:box.y2, box.z1:box.z2]
        if np.any(occupancy[region] != -1):
            raise ValueError("attempted to commit overlapping geometry")

        record = self._placement_record(
            box, weight, priority, grid_idx, is_blocker=is_blocker, supports=supports)
        placed_idx = len(self.placed_items)
        self.placed_items.append(record)
        occupancy[region] = placed_idx
        self._support_mask[grid_idx][region] = bool(supports)
        self._cache_placed_graph_entry(placed_idx)
        self.mer_managers[grid_idx].update(box)

        if not is_blocker:
            self.successful_placements += 1
            self._grid_placed_vol[grid_idx] += box.volume
            self._grid_placed_count[grid_idx] += 1
            bounds = self._priority_y_bounds[grid_idx].setdefault(int(priority), [box.y1, box.y1])
            bounds[0] = min(bounds[0], box.y1)
            bounds[1] = max(bounds[1], box.y1)

        self._invalidate_action_caches()
        return record

    def _commit_resolved(self, resolved):
        item = self.current_item
        box = Box3D(resolved.position, resolved.dimensions)
        self._commit_box(
            box,
            weight=item["weight"],
            priority=item["priority"],
            grid_idx=resolved.grid_idx,
        )
        return box

    def commit_action(self, action):
        """Commit a resolved inference action without reward or graph construction."""
        resolved = self._resolved_actions.get(int(action))
        if resolved is None:
            resolved = self._resolve_action(int(action))
        if resolved is None:
            return False, {"feasible": False, "error": "Action is not feasible"}

        self._commit_resolved(resolved)
        self._move_to_next_item()
        return self.current_item is None, {"feasible": True}

    def step(self, action):
        self.steps_in_episode += 1
        if self.steps_in_episode > max(1, self.total_items):
            return self._build_graph_state(), -10, True, {"error": "Episode timeout"}
        if self.current_item is None:
            return self._build_graph_state(), 0, True, {"error": "No item to place"}

        all_mers = self._get_all_mers()
        if not all_mers:
            return self._build_graph_state(), -10, True, {"error": "No MERs available"}
        if int(action) // 2 >= len(all_mers):
            self._move_to_next_item()
            return self._build_graph_state(), -5, self.current_item is None, {"error": "Invalid MER index"}

        resolved = self._resolved_actions.get(int(action))
        if resolved is None:
            resolved = self._resolve_action(int(action))
        if resolved is None:
            self._move_to_next_item()
            return self._build_graph_state(), -5.0, self.current_item is None, {"feasible": False}

        item_priority = self.current_item["priority"]
        placed_box = self._commit_resolved(resolved)
        reward = self._calculate_reward(
            resolved.position,
            resolved.dimensions,
            resolved.grid_idx,
            self.grids[resolved.grid_idx]["dims"],
            item_priority,
        )
        self._move_to_next_item()
        done = self.current_item is None
        if done and self.successful_placements == self.total_items:
            reward += min(5.0 * self.total_items, 100.0)
        return self._build_graph_state(), reward, done, {"feasible": True, "box": placed_box}

    def _move_to_next_item(self):
        self.current_item_idx += 1
        self._resolved_actions = {}
        if self.current_item_idx < len(self.cargo_manifest):
            self.current_item = self._get_item_features(self.cargo_manifest[self.current_item_idx])
        else:
            self.current_item = None

    def _check_priority_fast(self, y, priority, grid_idx):
        for placed_priority, (minimum_y, maximum_y) in self._priority_y_bounds[grid_idx].items():
            if priority < placed_priority and y > minimum_y:
                return False
            if priority > placed_priority and y < maximum_y:
                return False
        return True

    def _check_constraints_fast(
        self,
        position,
        dimensions,
        weight,
        priority,
        grid_idx,
        grid_dims=None,
        grid_items=None,
        enforce_priority=True,
    ):
        x, y, z = _integer_triplet(position, "position")
        width, length, height = _integer_triplet(dimensions, "dimensions")
        grid_width, grid_length, grid_height = self.grids[grid_idx]["dims"]
        x2, y2, z2 = x + width, y + length, z + height
        if x < 0 or y < 0 or z < 0 or x2 > grid_width or y2 > grid_length or z2 > grid_height:
            return False

        occupancy = self._occupancy[grid_idx]
        if np.any(occupancy[x:x2, y:y2, z:z2] != -1):
            return False

        if enforce_priority and not self._check_priority_fast(y, int(priority), grid_idx):
            return False

        if z > 0:
            supporting_cells = self._support_mask[grid_idx][x:x2, y:y2, z - 1]
            if supporting_cells.size == 0 or not bool(np.all(supporting_cells)):
                return False

            below_ids = np.unique(occupancy[x:x2, y:y2, :z])
            for placed_idx in below_ids:
                if placed_idx < 0:
                    continue
                placed = self.placed_items[int(placed_idx)]
                if placed["is_blocker"]:
                    continue
                placed_box = placed["box"]
                if placed_box.z2 <= z:
                    if placed["weight"] + weight > self.max_stack_weight:
                        return False
                    if weight > placed["weight"]:
                        return False
        return True

    def _check_additional_constraints(
        self,
        position,
        dimensions,
        weight,
        priority,
        grid_idx,
        grid_dims=None,
        enforce_priority=True,
    ):
        return self._check_constraints_fast(
            position,
            dimensions,
            weight,
            priority,
            grid_idx,
            grid_dims=grid_dims,
            enforce_priority=enforce_priority,
        )

    def _check_support(self, item_box, grid_items, min_ratio=0.99):
        if item_box.z1 == 0:
            return True
        supported = 0
        for placed in grid_items:
            if placed.get("is_blocker") and not placed.get("supports", True):
                continue
            box = placed["box"]
            if box.z2 == item_box.z1:
                supported += max(0, min(item_box.x2, box.x2) - max(item_box.x1, box.x1)) * max(
                    0, min(item_box.y2, box.y2) - max(item_box.y1, box.y1))
        return supported / (item_box.width * item_box.length) >= min_ratio

    def _check_stacking_weight(self, item_box, item_weight, grid_items):
        for placed in grid_items:
            if placed.get("is_blocker"):
                continue
            box = placed["box"]
            if (
                box.z2 <= item_box.z1 and
                box.x1 < item_box.x2 and box.x2 > item_box.x1 and
                box.y1 < item_box.y2 and box.y2 > item_box.y1
            ):
                if placed["weight"] + item_weight > self.max_stack_weight:
                    return False
                if item_weight > placed["weight"]:
                    return False
        return True

    def _check_priority_constraint(self, item_box, item_priority, grid_items):
        for placed in grid_items:
            if placed.get("is_blocker"):
                continue
            if item_priority < placed["priority"] and item_box.y1 > placed["y1"]:
                return False
            if item_priority > placed["priority"] and item_box.y1 < placed["y1"]:
                return False
        return True

    def _candidate_anchors(self, bounds, item_dims, grid_idx, include_mers=False):
        width, length, height = item_dims
        xs = {bounds.x1, bounds.x2 - width}
        ys = {bounds.y1, bounds.y2 - length}
        zs = {bounds.z1, bounds.z2 - height, 0}

        for placed in self.placed_items:
            if placed["grid_idx"] != grid_idx:
                continue
            box = placed["box"]
            xs.update((box.x1 - width, box.x1, box.x2 - width, box.x2))
            ys.update((box.y1 - length, box.y1, box.y2 - length, box.y2))
            zs.update((box.z1 - height, box.z2))

        if include_mers:
            for mer in self.mer_managers[grid_idx].mers:
                if mer.can_fit(item_dims):
                    xs.update((mer.x1, mer.x2 - width))
                    ys.update((mer.y1, mer.y2 - length))
                    zs.update((mer.z1, mer.z2 - height))

        xs = sorted(x for x in xs if bounds.x1 <= x <= bounds.x2 - width)
        ys = sorted(y for y in ys if bounds.y1 <= y <= bounds.y2 - length)
        zs = sorted(z for z in zs if bounds.z1 <= z <= bounds.z2 - height)
        return product(xs, ys, zs)

    def _find_valid_anchor_in_mer(
        self,
        mer_box,
        item_dims,
        weight,
        priority,
        grid_idx,
        grid_dims=None,
        grid_items=None,
    ):
        dimensions = _integer_triplet(item_dims, "item dimensions")
        for position in self._candidate_anchors(mer_box, dimensions, grid_idx):
            if self._check_constraints_fast(
                position, dimensions, weight, priority, grid_idx, grid_dims=grid_dims):
                return position
        return None

    def _resolve_action(self, action):
        if self.current_item is None:
            return None
        all_mers = self._get_all_mers()
        action = int(action)
        mer_action, rotation = divmod(action, 2)
        if mer_action >= len(all_mers):
            return None

        mer_info = all_mers[mer_action]
        base_dims = self.current_item["dimensions"]
        dimensions = base_dims if rotation == 0 else (base_dims[1], base_dims[0], base_dims[2])
        mer = mer_info["box"]
        if not mer.can_fit(dimensions):
            return None

        position = mer.position
        if not self._check_constraints_fast(
            position,
            dimensions,
            self.current_item["weight"],
            self.current_item["priority"],
            mer_info["grid_idx"],
        ):
            position = self._find_valid_anchor_in_mer(
                mer,
                dimensions,
                self.current_item["weight"],
                self.current_item["priority"],
                mer_info["grid_idx"],
            )
        if position is None:
            return None
        return ResolvedAction(
            action_idx=action,
            grid_idx=mer_info["grid_idx"],
            mer_idx=mer_info["mer_idx"],
            rotation=rotation,
            position=tuple(position),
            dimensions=dimensions,
        )

    def get_feasibility_mask(self):
        all_mers = self._get_all_mers()
        if self.current_item is None or not all_mers:
            self._resolved_actions = {}
            return np.zeros(max(1, len(all_mers) * 2), dtype=np.bool_)

        mask = np.zeros(len(all_mers) * 2, dtype=np.bool_)
        self._resolved_actions = {}
        square_footprint = self.current_item["dimensions"][0] == self.current_item["dimensions"][1]
        for mer_action in range(len(all_mers)):
            base_action = mer_action * 2
            resolved = self._resolve_action(base_action)
            if resolved is not None:
                mask[base_action] = True
                self._resolved_actions[base_action] = resolved
            if square_footprint:
                if resolved is not None:
                    rotated = ResolvedAction(
                        action_idx=base_action + 1,
                        grid_idx=resolved.grid_idx,
                        mer_idx=resolved.mer_idx,
                        rotation=1,
                        position=resolved.position,
                        dimensions=resolved.dimensions,
                    )
                    mask[base_action + 1] = True
                    self._resolved_actions[base_action + 1] = rotated
                continue
            rotated = self._resolve_action(base_action + 1)
            if rotated is not None:
                mask[base_action + 1] = True
                self._resolved_actions[base_action + 1] = rotated
        return mask

    def find_candidate_placement(self, item_tuple, enforce_priority=True):
        width, length, height, weight, priority = item_tuple
        base = _integer_triplet((width, length, height), "item dimensions")
        rotations = [(base[0], base[1], base[2])]
        if base[0] != base[1]:
            rotations.append((base[1], base[0], base[2]))

        for grid_idx, grid in enumerate(self.grids):
            bounds = Box3D((0, 0, 0), grid["dims"])
            for rotation, dimensions in enumerate(rotations):
                if not bounds.can_fit(dimensions):
                    continue
                for position in self._candidate_anchors(bounds, dimensions, grid_idx, include_mers=True):
                    if self._check_constraints_fast(
                        position,
                        dimensions,
                        weight,
                        priority,
                        grid_idx,
                        enforce_priority=enforce_priority,
                    ):
                        return (
                            grid_idx,
                            position[0], position[1], position[2],
                            rotation,
                            dimensions[0], dimensions[1], dimensions[2],
                        )
        return None

    def _calculate_reward(self, position, dimensions, grid_idx, grid_dims, item_priority):
        x, y, z = position
        width, length, height = dimensions
        grid_width, grid_length, grid_height = grid_dims
        volume_ratio = (width * length * height) / self.grid_volumes[grid_idx] if self.grid_volumes[grid_idx] else 0
        reward = volume_ratio * 10.0
        x2, y2, z2 = x + width, y + length, z + height

        touching_reward = 0.0
        touching_reward += 0.5 if x == 0 else 0.0
        touching_reward += 0.5 if y == 0 else 0.0
        touching_reward += 0.5 if z == 0 else 0.0
        touching_reward += 0.5 if x2 == grid_width else 0.0
        touching_reward += 0.5 if y2 == grid_length else 0.0
        touching_reward += 0.5 if z2 == grid_height else 0.0

        grid_items = [placed for placed in self.placed_items if placed["grid_idx"] == grid_idx]
        previous = grid_items[:-1]
        same_priority = sum(
            1 for placed in previous
            if not placed["is_blocker"] and placed["priority"] == item_priority
        )
        touching_reward += min(3.0, 0.4 * same_priority)
        touching_reward += 2.0

        for placed in previous:
            if (
                x == placed["x2"] or x2 == placed["x1"] or
                y == placed["y2"] or y2 == placed["y1"] or
                z == placed["z2"] or z2 == placed["z1"]
            ):
                touching_reward += 0.5
            if not placed["is_blocker"] and abs(placed["priority"] - item_priority) <= 1:
                touching_reward += 0.25

        reward += 2.0 + min(touching_reward, 2.0)
        if len(self.grids) > 1:
            fill_ratios = [
                self._grid_placed_vol[index] / self.grid_volumes[index]
                if self.grid_volumes[index] else 0.0
                for index in range(len(self.grids))
            ]
            reward += max(1.0 - float(np.std(fill_ratios)), 0.0) * 2.0
        return reward

    def _build_graph_state(self):
        node_features = [[self.NODE_TYPE_SHIP] + [0.0] * 12]
        node_types = [self.NODE_TYPE_SHIP]
        node_positions = [[0.0, 0.0, 0.0]]
        ship_node_idx = 0
        container_indices = {}

        for grid_idx, grid in enumerate(self.grids):
            grid_volume = self.grid_volumes[grid_idx]
            width, length, height = grid["dims"]
            node_features.append([
                self.NODE_TYPE_CONTAINER,
                width, length, height,
                self._grid_placed_count[grid_idx],
                self.total_items,
                self._grid_placed_vol[grid_idx] / grid_volume if grid_volume else 0.0,
                len(self.mer_managers[grid_idx].mers),
                width / length if length else 0.0,
                width / height if height else 0.0,
                length / height if height else 0.0,
                grid_volume / self.total_ship_volume if self.total_ship_volume else 0.0,
                grid_idx,
            ])
            node_types.append(self.NODE_TYPE_CONTAINER)
            node_positions.append([0.0, 0.0, 0.0])
            container_indices[grid_idx] = len(node_features) - 1

        current_item_node_idx = -1
        if self.current_item is not None:
            width, length, height = self.current_item["dimensions"]
            node_features.append([
                self.NODE_TYPE_ITEM,
                width, length, height,
                self.current_item["weight"],
                self.current_item["priority"],
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            ])
            node_types.append(self.NODE_TYPE_ITEM)
            node_positions.append([0.0, 0.0, 0.0])
            current_item_node_idx = len(node_features) - 1

        placed_start = len(node_features)
        node_features.extend(self._placed_node_features)
        node_types.extend([self.NODE_TYPE_PLACED] * len(self._placed_node_features))
        node_positions.extend(self._placed_node_positions)

        all_mers = self._get_all_mers()
        mer_indices = {}
        for mer_idx, mer_info in enumerate(all_mers):
            mer = mer_info["box"]
            grid_volume = self.grid_volumes[mer_info["grid_idx"]]
            node_features.append([
                self.NODE_TYPE_MER,
                mer.width, mer.length, mer.height,
                mer.volume,
                mer_info["grid_idx"],
                mer.volume / grid_volume if grid_volume else 0.0,
                0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            ])
            node_types.append(self.NODE_TYPE_MER)
            node_positions.append([mer.x1, mer.y1, mer.z1])
            mer_indices[mer_idx] = len(node_features) - 1

        edges = []
        for container_idx in container_indices.values():
            edges.extend(((ship_node_idx, container_idx), (container_idx, ship_node_idx)))

        container_nodes = list(container_indices.values())
        for first_idx, first in enumerate(container_nodes):
            for second in container_nodes[first_idx + 1:]:
                edges.extend(((first, second), (second, first)))

        for placed_idx, placed in enumerate(self.placed_items):
            node_idx = placed_start + placed_idx
            container_idx = container_indices[placed["grid_idx"]]
            edges.extend(((container_idx, node_idx), (node_idx, container_idx)))

        for mer_idx, mer_info in enumerate(all_mers):
            node_idx = mer_indices[mer_idx]
            container_idx = container_indices[mer_info["grid_idx"]]
            edges.extend(((container_idx, node_idx), (node_idx, container_idx)))

        if current_item_node_idx != -1:
            for container_idx in container_indices.values():
                edges.extend(((current_item_node_idx, container_idx), (container_idx, current_item_node_idx)))
            feasible_by_grid = {
                grid_idx: set(manager.get_feasible_mers(self.current_item["dimensions"]))
                for grid_idx, manager in enumerate(self.mer_managers)
            }
            for mer_idx, mer_info in enumerate(all_mers):
                if mer_info["mer_idx"] in feasible_by_grid[mer_info["grid_idx"]]:
                    node_idx = mer_indices[mer_idx]
                    edges.extend(((current_item_node_idx, node_idx), (node_idx, current_item_node_idx)))

        for first, second in self._placed_touch_edges:
            first_node = placed_start + first
            second_node = placed_start + second
            edges.extend(((first_node, second_node), (second_node, first_node)))

        x = torch.tensor(node_features, dtype=torch.float)
        node_type = torch.tensor(node_types, dtype=torch.long)
        pos = torch.tensor(node_positions, dtype=torch.float)
        edge_index = (
            torch.tensor(edges, dtype=torch.long).t().contiguous()
            if edges else torch.empty((2, 0), dtype=torch.long)
        )
        graph = Data(x=x, edge_index=edge_index, node_type=node_type, pos=pos)
        graph.mer_node_indices = mer_indices
        graph.current_item_node_idx = current_item_node_idx
        return graph

    def mer_statistics(self):
        updates = sum(manager.update_count + 1 for manager in self.mer_managers)
        total = sum(manager.mer_count_total for manager in self.mer_managers)
        return {
            "max": max((manager.max_mer_count for manager in self.mer_managers), default=0),
            "average": total / updates if updates else 0.0,
            "current": sum(len(manager.mers) for manager in self.mer_managers),
        }
