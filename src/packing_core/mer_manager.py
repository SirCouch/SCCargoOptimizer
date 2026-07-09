from .box3d import Box3D, _integer_triplet


class MERManager:
    """Maintain maximal empty rectangular volumes in CPU integer geometry."""

    def __init__(self, container_dimensions):
        dimensions = _integer_triplet(container_dimensions, "container_dimensions")
        self.container = Box3D((0, 0, 0), dimensions)
        self.mers = [self.container]
        self.max_mer_count = 1
        self.mer_count_total = 1
        self.update_count = 0

    @property
    def average_mer_count(self):
        return self.mer_count_total / (self.update_count + 1)

    def update(self, placed_item):
        new_mers = []
        non_overlapping = []

        for mer in self.mers:
            if not mer.overlaps(placed_item):
                non_overlapping.append(mer)
                continue

            if placed_item.x2 < mer.x2:
                new_mers.append(Box3D.from_bounds(
                    placed_item.x2, mer.y1, mer.z1, mer.x2, mer.y2, mer.z2))
            if placed_item.x1 > mer.x1:
                new_mers.append(Box3D.from_bounds(
                    mer.x1, mer.y1, mer.z1, placed_item.x1, mer.y2, mer.z2))
            if placed_item.y2 < mer.y2:
                new_mers.append(Box3D.from_bounds(
                    mer.x1, placed_item.y2, mer.z1, mer.x2, mer.y2, mer.z2))
            if placed_item.y1 > mer.y1:
                new_mers.append(Box3D.from_bounds(
                    mer.x1, mer.y1, mer.z1, mer.x2, placed_item.y1, mer.z2))
            if placed_item.z2 < mer.z2:
                new_mers.append(Box3D.from_bounds(
                    mer.x1, mer.y1, placed_item.z2, mer.x2, mer.y2, mer.z2))
            if placed_item.z1 > mer.z1:
                new_mers.append(Box3D.from_bounds(
                    mer.x1, mer.y1, mer.z1, mer.x2, mer.y2, placed_item.z1))

        self.mers = self._filter_redundant(new_mers + non_overlapping)
        self.update_count += 1
        self.mer_count_total += len(self.mers)
        self.max_mer_count = max(self.max_mer_count, len(self.mers))
        return self.mers

    def _filter_redundant(self, boxes):
        candidates = sorted(dict.fromkeys(boxes), key=lambda box: box.volume, reverse=True)
        kept = []
        for candidate in candidates:
            if candidate.volume < 1:
                continue
            if any(container.contains(candidate) for container in kept):
                continue
            kept.append(candidate)
        return kept

    def get_feasible_mers(self, item_dimensions):
        dimensions = _integer_triplet(item_dimensions, "item_dimensions")
        orientations = {dimensions, (dimensions[1], dimensions[0], dimensions[2])}
        return [
            index
            for index, mer in enumerate(self.mers)
            if any(mer.can_fit(orientation) for orientation in orientations)
        ]

    def __len__(self):
        return len(self.mers)
