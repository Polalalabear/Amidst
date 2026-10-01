"""Allowed-mesh physical visibility in Blender's evaluated VIEWPORT graph.

This is geometry occlusion, not rendered-pixel visibility: materials and
``hide_render`` do not remove blockers. Annotation boxes in ``Areas`` and owned
target proxies are filtered before raycasting, never skipped by advancing a
scene ray. The caller must not mutate scene geometry between queries; call
``refresh()`` after mutations. Frame/dependency-graph changes refresh the cache.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from amidst.simulation.raycast_types import RaycastResult

if TYPE_CHECKING:
    from amidst.domain.common import Vec3


@dataclass(frozen=True)
class _MeshInstance:
    obj: Any
    matrix: Any
    inverse: Any | None
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]
    padding: float
    object_name: str


def _original_pointer(obj: Any) -> int:
    return int(obj.original.as_pointer())


def _finite_matrix(matrix: Any) -> bool:
    return all(math.isfinite(value) for row in matrix for value in row)


def _transform_point(matrix: Any, point: Sequence[float]) -> tuple[float, float, float]:
    # Python float accumulation avoids an additional world-space float32 rounding.
    return tuple(
        sum(float(matrix[row][column]) * point[column] for column in range(3))
        + float(matrix[row][3])
        for row in range(3)
    )  # type: ignore[return-value]


def _segment_box_entry(
    origin: Sequence[float],
    direction: Sequence[float],
    distance: float,
    mesh: _MeshInstance,
) -> float | None:
    enter, leave = 0.0, distance
    for axis in range(3):
        low, high = mesh.minimum[axis], mesh.maximum[axis]
        component = direction[axis]
        if component == 0.0:
            if origin[axis] < low or origin[axis] > high:
                return None
        else:
            a, b = (low - origin[axis]) / component, (high - origin[axis]) / component
            enter, leave = max(enter, min(a, b)), min(leave, max(a, b))
            if enter > leave:
                return None
    return enter


class BlenderMeshRaycaster:
    """Cache evaluated mesh instances, conservatively fail closed on uncertainty.

    ``max_candidates`` bounds object ray queries per segment. A zero budget is
    valid and rejects any segment with a candidate mesh. Bounds are inflated by
    max(1e-6 m, coordinate magnitude * 2e-6) solely for the broad-phase query.
    Actual mesh intersections, not bounding boxes, establish occlusion.
    """

    def __init__(
        self,
        scene: Any,
        excluded_objects: Sequence[Any] = (),
        *,
        max_candidates: int = 10_000,
        endpoint_tolerance_m: float = 1e-3,
    ) -> None:
        if (
            not isinstance(max_candidates, int)
            or isinstance(max_candidates, bool)
            or max_candidates < 0
        ):
            raise ValueError("max_candidates must be a non-negative integer")
        if not math.isfinite(endpoint_tolerance_m) or endpoint_tolerance_m < 0:
            raise ValueError("endpoint_tolerance_m must be finite and non-negative")
        self.scene = scene
        self.excluded_objects = tuple(excluded_objects)
        self.max_candidates = max_candidates
        self.endpoint_tolerance_m = endpoint_tolerance_m
        self._meshes: tuple[_MeshInstance, ...] = ()
        self._uncertain = True
        self._depsgraph: Any = None
        self._cache_key: tuple[int, float, int] | None = None
        self.refresh()

    def refresh(self) -> None:
        """Rebuild from fresh evaluated instances without changing any scene data."""
        import bpy  # type: ignore[import-not-found]

        self._uncertain = True
        self._meshes = ()
        self._cache_key = None
        try:
            if self.scene != bpy.context.scene:
                return
            depsgraph = bpy.context.evaluated_depsgraph_get()
            if depsgraph.mode != "VIEWPORT":
                return
            excluded = {_original_pointer(obj) for obj in self.excluded_objects}
            annotation_collection = bpy.data.collections.get("Areas")
            if annotation_collection is not None:
                excluded.update(_original_pointer(obj) for obj in annotation_collection.all_objects)
            meshes = []
            for instance in depsgraph.object_instances:
                # Iterated instance RNA references/matrices can be reused by Blender.
                matrix = instance.matrix_world.copy()
                obj = instance.object
                parent = instance.parent
                if obj.type != "MESH" or not instance.show_self:
                    continue
                if _original_pointer(obj) in excluded or (
                    parent is not None and _original_pointer(parent) in excluded
                ):
                    continue
                if not len(obj.data.polygons):
                    continue
                if not _finite_matrix(matrix):
                    return
                corners = [_transform_point(matrix, corner) for corner in obj.bound_box]
                if not all(math.isfinite(value) for corner in corners for value in corner):
                    return
                padding = max(
                    1e-6, max(abs(value) for corner in corners for value in corner) * 2e-6
                )
                minimum = tuple(
                    min(corner[axis] for corner in corners) - padding for axis in range(3)
                )
                maximum = tuple(
                    max(corner[axis] for corner in corners) + padding for axis in range(3)
                )
                try:
                    inverse = matrix.inverted()
                    if not _finite_matrix(inverse):
                        inverse = None
                except (ValueError, RuntimeError):
                    inverse = None
                meshes.append(
                    _MeshInstance(
                        obj,
                        matrix,
                        inverse,
                        (minimum[0], minimum[1], minimum[2]),
                        (maximum[0], maximum[1], maximum[2]),
                        padding,
                        obj.original.name,
                    )
                )
            self._meshes = tuple(
                sorted(
                    meshes,
                    key=lambda mesh: (
                        mesh.object_name,
                        tuple(value for row in mesh.matrix for value in row),
                    ),
                )
            )
            self._depsgraph = depsgraph
            self._cache_key = (
                self.scene.frame_current,
                self.scene.frame_subframe,
                int(depsgraph.as_pointer()),
            )
            self._uncertain = False
        except Exception:
            # Missing/evaluated-invalid geometry invalidates a CLEAR assertion.
            self._uncertain = True

    def __call__(self, origin: Vec3, target: Vec3) -> RaycastResult:
        import bpy
        from mathutils import Vector  # type: ignore[import-not-found]

        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            key = (self.scene.frame_current, self.scene.frame_subframe, int(depsgraph.as_pointer()))
            if key != self._cache_key or self.scene != bpy.context.scene:
                self.refresh()
            if self._uncertain:
                return RaycastResult(True, "GEOMETRY_UNCERTAIN")
            if (
                len(origin) != 3
                or len(target) != 3
                or not all(math.isfinite(value) for value in (*origin, *target))
            ):
                return RaycastResult(True, "GEOMETRY_UNCERTAIN")
            delta = tuple(b - a for a, b in zip(origin, target, strict=True))
            distance = math.hypot(*delta)
            if not math.isfinite(distance) or distance == 0:
                return RaycastResult(True, "GEOMETRY_UNCERTAIN")
            direction = tuple(value / distance for value in delta)
            candidates = []
            for mesh in self._meshes:
                entry = _segment_box_entry(origin, direction, distance, mesh)
                if entry is not None:
                    candidates.append((entry, mesh.object_name, mesh))
            if len(candidates) > self.max_candidates:
                return RaycastResult(True, "RAYCAST_LIMIT")
            candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
            closest_distance, closest_name = math.inf, None
            for _, _, mesh in candidates:
                if mesh.inverse is None:
                    return RaycastResult(True, "GEOMETRY_UNCERTAIN", mesh.object_name)
                local_origin = mesh.inverse @ Vector(origin)
                local_direction = mesh.inverse.to_3x3() @ Vector(direction)
                local_per_world = local_direction.length
                if not math.isfinite(local_per_world) or local_per_world <= 0:
                    return RaycastResult(True, "GEOMETRY_UNCERTAIN", mesh.object_name)
                local_direction /= local_per_world
                local_distance = (
                    distance + mesh.padding + self.endpoint_tolerance_m
                ) * local_per_world
                hit, location, _, _ = mesh.obj.ray_cast(
                    local_origin,
                    local_direction,
                    distance=local_distance,
                    depsgraph=self._depsgraph,
                )
                if not hit:
                    continue
                world_location = _transform_point(mesh.matrix, location)
                hit_distance = sum(
                    (world_location[axis] - origin[axis]) * direction[axis] for axis in range(3)
                )
                if not math.isfinite(hit_distance) or hit_distance < -mesh.padding:
                    return RaycastResult(True, "GEOMETRY_UNCERTAIN", mesh.object_name)
                if (
                    hit_distance < distance - self.endpoint_tolerance_m
                    and hit_distance < closest_distance
                ):
                    closest_distance, closest_name = hit_distance, mesh.object_name
            if closest_name is not None:
                return RaycastResult(True, "OCCLUDED", closest_name)
            return RaycastResult(False, "CLEAR")
        except Exception:
            return RaycastResult(True, "GEOMETRY_UNCERTAIN")
