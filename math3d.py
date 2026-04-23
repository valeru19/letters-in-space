import math
from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

from PySide6.QtGui import QColor


EPS = 1e-6


@dataclass
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, value: float) -> "Vec3":
        return Vec3(self.x * value, self.y * value, self.z * value)

    __rmul__ = __mul__

    def __truediv__(self, value: float) -> "Vec3":
        return Vec3(self.x / value, self.y / value, self.z / value)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> "Vec3":
        l = self.length()
        if l < EPS:
            return Vec3(0.0, 0.0, 0.0)
        return self / l

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z]

    @staticmethod
    def from_list(values: Sequence[float]) -> "Vec3":
        if len(values) != 3:
            return Vec3(0.0, 0.0, 0.0)
        return Vec3(float(values[0]), float(values[1]), float(values[2]))


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def rotate_x(v: Vec3, angle_deg: float) -> Vec3:
    a = math.radians(angle_deg)
    ca = math.cos(a)
    sa = math.sin(a)
    return Vec3(v.x, v.y * ca - v.z * sa, v.y * sa + v.z * ca)


def rotate_y(v: Vec3, angle_deg: float) -> Vec3:
    a = math.radians(angle_deg)
    ca = math.cos(a)
    sa = math.sin(a)
    return Vec3(v.x * ca + v.z * sa, v.y, -v.x * sa + v.z * ca)


def rotate_z(v: Vec3, angle_deg: float) -> Vec3:
    a = math.radians(angle_deg)
    ca = math.cos(a)
    sa = math.sin(a)
    return Vec3(v.x * ca - v.y * sa, v.x * sa + v.y * ca, v.z)


def apply_euler(v: Vec3, rot: Vec3) -> Vec3:
    r = rotate_x(v, rot.x)
    r = rotate_y(r, rot.y)
    r = rotate_z(r, rot.z)
    return r


def apply_inverse_euler(v: Vec3, rot: Vec3) -> Vec3:
    r = rotate_z(v, -rot.z)
    r = rotate_y(r, -rot.y)
    r = rotate_x(r, -rot.x)
    return r


@dataclass
class Mesh:
    vertices: List[Vec3]
    faces: List[Tuple[int, int, int]]
    edges: List[Tuple[int, int]]


@dataclass
class Object3D:
    name: str
    mesh: Mesh
    color: QColor
    size: Vec3
    position: Vec3
    rotation: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    mirror: Vec3 = field(default_factory=lambda: Vec3(1.0, 1.0, 1.0))

    def world_vertices(self) -> List[Vec3]:
        out: List[Vec3] = []
        for v in self.mesh.vertices:
            scaled = Vec3(
                v.x * self.size.x * self.mirror.x,
                v.y * self.size.y * self.mirror.y,
                v.z * self.size.z * self.mirror.z,
            )
            rotated = apply_euler(scaled, self.rotation)
            out.append(rotated + self.position)
        return out

    def reflect(self, axis: str) -> None:
        if axis == "x":
            self.mirror.x *= -1.0
        elif axis == "y":
            self.mirror.y *= -1.0
        elif axis == "z":
            self.mirror.z *= -1.0


@dataclass
class Camera:
    position: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, -12.0))
    rotation: Vec3 = field(default_factory=lambda: Vec3(0.0, 0.0, 0.0))
    fov_deg: float = 65.0
    near: float = 0.1

    def world_to_camera(self, p: Vec3) -> Vec3:
        return apply_inverse_euler(p - self.position, self.rotation)


def box_geometry(center: Vec3, size: Vec3) -> Tuple[List[Vec3], List[Tuple[int, int, int]], List[Tuple[int, int]]]:
    hx, hy, hz = size.x / 2.0, size.y / 2.0, size.z / 2.0
    cx, cy, cz = center.x, center.y, center.z
    verts = [
        Vec3(cx - hx, cy - hy, cz - hz),
        Vec3(cx + hx, cy - hy, cz - hz),
        Vec3(cx + hx, cy + hy, cz - hz),
        Vec3(cx - hx, cy + hy, cz - hz),
        Vec3(cx - hx, cy - hy, cz + hz),
        Vec3(cx + hx, cy - hy, cz + hz),
        Vec3(cx + hx, cy + hy, cz + hz),
        Vec3(cx - hx, cy + hy, cz + hz),
    ]
    quads = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 4, 7, 3),
        (1, 2, 6, 5),
        (3, 7, 6, 2),
        (0, 1, 5, 4),
    ]
    faces: List[Tuple[int, int, int]] = []
    edges: set[Tuple[int, int]] = set()
    for a, b, c, d in quads:
        faces.append((a, b, c))
        faces.append((a, c, d))
        quad_edges = [(a, b), (b, c), (c, d), (d, a)]
        for i, j in quad_edges:
            edges.add(tuple(sorted((i, j))))
    return verts, faces, sorted(edges)


def merge_meshes(parts: Sequence[Tuple[List[Vec3], List[Tuple[int, int, int]], List[Tuple[int, int]]]]) -> Mesh:
    vertices: List[Vec3] = []
    faces: List[Tuple[int, int, int]] = []
    edges: set[Tuple[int, int]] = set()
    shift = 0
    for part_vertices, part_faces, part_edges in parts:
        vertices.extend(part_vertices)
        for a, b, c in part_faces:
            faces.append((a + shift, b + shift, c + shift))
        for i, j in part_edges:
            edges.add(tuple(sorted((i + shift, j + shift))))
        shift += len(part_vertices)
    return Mesh(vertices=vertices, faces=faces, edges=sorted(edges))


def build_letter_em() -> Mesh:
    w, h, d = 2.6, 3.0, 1.0
    t = 0.45
    parts = [
        box_geometry(Vec3(-w / 2.0 + t / 2.0, 0.0, 0.0), Vec3(t, h, d)),
        box_geometry(Vec3(w / 2.0 - t / 2.0, 0.0, 0.0), Vec3(t, h, d)),
    ]

    # Central diagonals are approximated by a staircase of short blocks.
    # We intentionally overlap both diagonals in the center to avoid gaps.
    steps = 8
    start_left = Vec3(-w / 2.0 + t * 1.1, h / 2.0 - t * 0.7, 0.0)
    center_joint = Vec3(0.0, -h * 0.12, 0.0)
    end_center = center_joint
    start_center = center_joint
    end_right = Vec3(w / 2.0 - t * 1.1, h / 2.0 - t * 0.7, 0.0)

    for i in range(steps):
        k = i / (steps - 1)
        p = start_left * (1.0 - k) + end_center * k
        parts.append(box_geometry(p, Vec3(t * 1.05, t * 1.05, d)))

    for i in range(steps):
        k = i / (steps - 1)
        p = start_center * (1.0 - k) + end_right * k
        parts.append(box_geometry(p, Vec3(t * 1.05, t * 1.05, d)))

    # Extra bridge in the middle keeps the letter visually solid.
    parts.append(box_geometry(center_joint, Vec3(t * 1.35, t * 1.25, d)))

    return merge_meshes(parts)


def build_letter_pe() -> Mesh:
    w, h, d = 2.4, 3.0, 1.0
    t = 0.45
    parts = [
        box_geometry(Vec3(-w / 2.0 + t / 2.0, 0.0, 0.0), Vec3(t, h, d)),
        box_geometry(Vec3(w / 2.0 - t / 2.0, 0.0, 0.0), Vec3(t, h, d)),
        box_geometry(Vec3(0.0, h / 2.0 - t / 2.0, 0.0), Vec3(w, t, d)),
    ]
    return merge_meshes(parts)


def build_default_objects() -> List[Object3D]:
    obj_m = Object3D(
        name="М",
        mesh=build_letter_em(),
        color=QColor(230, 130, 90),
        size=Vec3(1.0, 1.0, 1.0),
        position=Vec3(-1.8, 0.0, 4.5),
    )
    obj_p = Object3D(
        name="П",
        mesh=build_letter_pe(),
        color=QColor(85, 155, 235),
        size=Vec3(1.0, 1.0, 1.0),
        position=Vec3(1.8, 0.0, 5.0),
    )
    return [obj_m, obj_p]
