from dataclasses import dataclass
from numbers import Real


def _integer_triplet(values, field_name):
    if (
        isinstance(values, tuple) and
        len(values) == 3 and
        all(isinstance(value, int) and not isinstance(value, bool) for value in values)
    ):
        return values
    if hasattr(values, "detach"):
        values = values.detach().cpu().tolist()
    if len(values) != 3:
        raise ValueError(f"{field_name} must contain exactly three values")

    result = []
    for value in values:
        if hasattr(value, "item"):
            value = value.item()
        if not isinstance(value, Real):
            raise TypeError(f"{field_name} values must be numeric")
        rounded = round(float(value))
        if abs(float(value) - rounded) > 1e-6:
            raise ValueError(f"{field_name} values must be integer SCU coordinates")
        result.append(int(rounded))
    return tuple(result)


@dataclass(frozen=True, slots=True, init=False)
class Box3D:
    """Immutable axis-aligned box in integer SCU geometry space."""

    x1: int
    y1: int
    z1: int
    x2: int
    y2: int
    z2: int

    def __init__(self, position, dimensions):
        x1, y1, z1 = _integer_triplet(position, "position")
        width, length, height = _integer_triplet(dimensions, "dimensions")
        if width <= 0 or length <= 0 or height <= 0:
            raise ValueError("dimensions must be positive")
        object.__setattr__(self, "x1", x1)
        object.__setattr__(self, "y1", y1)
        object.__setattr__(self, "z1", z1)
        object.__setattr__(self, "x2", x1 + width)
        object.__setattr__(self, "y2", y1 + length)
        object.__setattr__(self, "z2", z1 + height)

    @classmethod
    def from_bounds(cls, x1, y1, z1, x2, y2, z2):
        return cls((x1, y1, z1), (x2 - x1, y2 - y1, z2 - z1))

    @property
    def position(self):
        return self.x1, self.y1, self.z1

    @property
    def dimensions(self):
        return self.width, self.length, self.height

    @property
    def width(self):
        return self.x2 - self.x1

    @property
    def length(self):
        return self.y2 - self.y1

    @property
    def height(self):
        return self.z2 - self.z1

    @property
    def volume(self):
        return self.width * self.length * self.height

    def overlaps(self, other):
        return not (
            self.x2 <= other.x1 or other.x2 <= self.x1 or
            self.y2 <= other.y1 or other.y2 <= self.y1 or
            self.z2 <= other.z1 or other.z2 <= self.z1
        )

    def contains(self, other):
        return (
            self.x1 <= other.x1 and other.x2 <= self.x2 and
            self.y1 <= other.y1 and other.y2 <= self.y2 and
            self.z1 <= other.z1 and other.z2 <= self.z2
        )

    def get_intersection(self, other):
        if not self.overlaps(other):
            return None
        return Box3D.from_bounds(
            max(self.x1, other.x1),
            max(self.y1, other.y1),
            max(self.z1, other.z1),
            min(self.x2, other.x2),
            min(self.y2, other.y2),
            min(self.z2, other.z2),
        )

    def can_fit(self, item_dimensions):
        width, length, height = _integer_triplet(item_dimensions, "item_dimensions")
        return self.width >= width and self.length >= length and self.height >= height

    def to_dict(self):
        return {"position": self.position, "dimensions": self.dimensions}

    def __repr__(self):
        return f"Box3D(pos={self.position}, dims={self.dimensions})"
