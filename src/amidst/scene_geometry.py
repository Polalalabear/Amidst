"""Source-bound, immutable scene geometry; no Blender or inference dependencies.

Authority describes evidence, not a new permission to use reviewed geometry.
Exact triangle surfaces are retained, including holes and disconnected pieces.
"""

import math
from dataclasses import InitVar, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, StrictInt, model_validator

Coordinate = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
Triangle = tuple[StrictInt, StrictInt, StrictInt]
Nonnegative = Annotated[FiniteFloat, Field(ge=0)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class Authority(StrEnum):
    APPROVED = "APPROVED"
    HIGH_CONFIDENCE = "HIGH_CONFIDENCE"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    REJECTED = "REJECTED"


class GeometryRole(StrEnum):
    WALKABLE = "WALKABLE"
    WALL = "WALL"
    OBSTACLE = "OBSTACLE"
    PORTAL = "PORTAL"
    STAIR = "STAIR"


class GeometrySupport(StrEnum):
    SURFACE = "SURFACE"
    VOLUME = "VOLUME"
    FOOTPRINT = "FOOTPRINT"
    ANNOTATION = "ANNOTATION"


class GeometryAuthorityError(ValueError):
    """Formal physical consumption refused; inspection remains available."""

    def __init__(self, reasons: tuple[str, ...]) -> None:
        self.reasons = reasons
        summary = ", ".join(reasons[:5])
        if len(reasons) > 5:
            summary += f", and {len(reasons) - 5} further unresolved authorities"
        super().__init__(f"approved physics unavailable: {summary}")


class GeometryModel(BaseModel):
    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, validate_default=True,
        revalidate_instances="always",
    )


def _subtract(a: Coordinate, b: Coordinate) -> Coordinate:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Coordinate, b: Coordinate) -> Coordinate:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(a: Coordinate, scale: float) -> Coordinate:
    return (a[0] * scale, a[1] * scale, a[2] * scale)


def _dot(a: Coordinate, b: Coordinate) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Coordinate, b: Coordinate) -> Coordinate:
    return (
        a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _check_approval(statuses: tuple[Authority, ...], approval_id: str | None) -> None:
    if Authority.APPROVED in statuses and not approval_id:
        raise ValueError("APPROVED authority requires an explicit approval_id")


def _check_evidence(statuses: tuple[Authority, ...], evidence_ids: tuple[str, ...]) -> None:
    if any(not identity.strip() for identity in evidence_ids):
        raise ValueError("evidence identities cannot be empty")
    if any(status in (Authority.APPROVED, Authority.HIGH_CONFIDENCE) for status in statuses):
        if not evidence_ids:
            raise ValueError("accepted authority requires traceable evidence_ids")


class FloorAuthority(GeometryModel):
    floor_id: str = Field(min_length=1)
    point: Coordinate
    normal: Coordinate
    authority: Authority
    evidence_ids: tuple[str, ...] = ()
    approval_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_floor(self) -> Self:
        if abs(_dot(self.normal, self.normal) - 1.0) > 1e-6:
            raise ValueError("floor normal must be a unit vector")
        _check_approval((self.authority,), self.approval_id)
        _check_evidence((self.authority,), self.evidence_ids)
        return self


class GeometrySurface(GeometryModel):
    surface_id: str = Field(min_length=1)
    source_object_id: str = Field(min_length=1)
    source_face_indices: tuple[StrictInt, ...] = ()
    role: GeometryRole
    floor_ids: tuple[str, ...] = ()
    vertices: tuple[Coordinate, ...] = Field(min_length=1)
    triangles: tuple[Triangle, ...] = ()
    semantic_authority: Authority
    physical_authority: Authority
    support: GeometrySupport
    evidence_ids: tuple[str, ...] = ()
    approval_id: str | None = Field(default=None, min_length=1)
    blocks_movement: bool = False
    occludes_visibility: bool = False
    portal_ids: tuple[str, ...] = ()
    stair_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_surface(self) -> Self:
        if self.support != GeometrySupport.ANNOTATION and (
            len(self.vertices) < 3 or not self.triangles
        ):
            raise ValueError("physical surface evidence requires vertices and actual triangles")
        if any(index < 0 for index in self.source_face_indices):
            raise ValueError("source face indices must be nonnegative")
        if len(set(self.floor_ids)) != len(self.floor_ids):
            raise ValueError("surface floor_ids must be unique")
        for triangle in self.triangles:
            if len(set(triangle)) != 3 or any(
                index < 0 or index >= len(self.vertices) for index in triangle
            ):
                raise ValueError("triangle indices must refer to three distinct vertices")
            a, b, c = (self.vertices[index] for index in triangle)
            normal = _cross(_subtract(b, a), _subtract(c, a))
            squared = _dot(normal, normal)
            if not math.isfinite(squared) or squared == 0:
                raise ValueError("degenerate triangle is not valid surface evidence")
        _check_approval((self.semantic_authority, self.physical_authority), self.approval_id)
        _check_evidence((self.semantic_authority, self.physical_authority), self.evidence_ids)
        if self.physical_authority in (Authority.APPROVED, Authority.HIGH_CONFIDENCE):
            if self.support in (GeometrySupport.FOOTPRINT, GeometrySupport.ANNOTATION):
                raise ValueError("footprint/annotation cannot certify physical collider authority")
            if self.semantic_authority not in (Authority.APPROVED, Authority.HIGH_CONFIDENCE):
                raise ValueError("physical authority requires accepted semantic role evidence")
        if self.support == GeometrySupport.VOLUME:
            counts: dict[tuple[int, int], int] = {}
            orientations: dict[tuple[int, int], int] = {}
            for triangle in self.triangles:
                for index_a, index_b in zip(triangle, (*triangle[1:], triangle[0]), strict=True):
                    edge = tuple(sorted((index_a, index_b)))
                    key = (edge[0], edge[1])
                    counts[key] = counts.get(key, 0) + 1
                    orientations[key] = orientations.get(key, 0) + (1 if index_a < index_b else -1)
            if any(count != 2 for count in counts.values()):
                raise ValueError("VOLUME requires closed two-manifold triangle edge support")
            if any(orientation != 0 for orientation in orientations.values()):
                raise ValueError("VOLUME triangle winding must be consistent")
            volume = sum(
                _dot(self.vertices[a], _cross(self.vertices[b], self.vertices[c]))
                for a, b, c in self.triangles
            )
            if volume == 0:
                raise ValueError("VOLUME evidence cannot have zero enclosed signed volume")
        return self


class PortalGeometry(GeometryModel):
    portal_id: str = Field(min_length=1)
    floor_id: str = Field(min_length=1)
    surface_id: str = Field(min_length=1)
    adjacent_walkable_ids: tuple[str, ...] = ()
    authority: Authority
    evidence_ids: tuple[str, ...] = ()
    approval_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_portal(self) -> Self:
        _check_approval((self.authority,), self.approval_id)
        _check_evidence((self.authority,), self.evidence_ids)
        return self


class StairGeometry(GeometryModel):
    stair_id: str = Field(min_length=1)
    floor_from: str = Field(min_length=1)
    floor_to: str = Field(min_length=1)
    entry_point: Coordinate | None = None
    exit_point: Coordinate | None = None
    entry_surface_id: str | None = Field(default=None, min_length=1)
    path_surface_ids: tuple[str, ...] = ()
    exit_surface_id: str | None = Field(default=None, min_length=1)
    connectivity_authority: Authority
    opening_authority: Authority
    clearance_authority: Authority
    evidence_ids: tuple[str, ...] = ()
    approval_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_stair(self) -> Self:
        if self.floor_from == self.floor_to:
            raise ValueError("stair must connect two distinct floors")
        _check_approval(
            (self.connectivity_authority, self.opening_authority, self.clearance_authority),
            self.approval_id,
        )
        _check_evidence(
            (self.connectivity_authority, self.opening_authority, self.clearance_authority),
            self.evidence_ids,
        )
        if self.connectivity_authority == Authority.APPROVED and (
            self.entry_point is None or self.exit_point is None or not self.path_surface_ids
        ):
            raise ValueError("APPROVED stair connectivity requires entry/path/exit evidence")
        return self


def _point_triangle_squared(point: Coordinate, triangle: tuple[Coordinate, ...]) -> float:
    a, b, c = triangle
    ab, ac, ap = _subtract(b, a), _subtract(c, a), _subtract(point, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return _dot(ap, ap)
    bp = _subtract(point, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return _dot(bp, bp)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        closest = _add(a, _scale(ab, d1 / (d1 - d3)))
    else:
        cp = _subtract(point, c)
        d5, d6 = _dot(ab, cp), _dot(ac, cp)
        if d6 >= 0 and d5 <= d6:
            return _dot(cp, cp)
        vb = d5 * d2 - d1 * d6
        if vb <= 0 and d2 >= 0 and d6 <= 0:
            closest = _add(a, _scale(ac, d2 / (d2 - d6)))
        else:
            va = d3 * d6 - d5 * d4
            if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
                closest = _add(b, _scale(_subtract(c, b), (d4 - d3) / (d4 - d3 + d5 - d6)))
            else:
                denominator = 1.0 / (va + vb + vc)
                closest = _add(a, _add(_scale(ab, vb * denominator), _scale(ac, vc * denominator)))
    delta = _subtract(point, closest)
    return _dot(delta, delta)


def _segment_squared(a: Coordinate, b: Coordinate, c: Coordinate, d: Coordinate) -> float:
    first, second, delta = _subtract(b, a), _subtract(d, c), _subtract(a, c)
    aa, ee, ff = _dot(first, first), _dot(second, second), _dot(second, delta)
    cc, bb = _dot(first, delta), _dot(first, second)
    denominator = aa * ee - bb * bb
    s = min(1.0, max(0.0, (bb * ff - cc * ee) / denominator)) if denominator > 0 else 0.0
    t = (bb * s + ff) / ee
    if t < 0:
        t, s = 0.0, min(1.0, max(0.0, -cc / aa))
    elif t > 1:
        t, s = 1.0, min(1.0, max(0.0, (bb - cc) / aa))
    difference = _subtract(_add(a, _scale(first, s)), _add(c, _scale(second, t)))
    return _dot(difference, difference)


def _segment_intersects_triangle(
    a: Coordinate, b: Coordinate, triangle: tuple[Coordinate, ...], numerical_epsilon: float,
) -> bool:
    origin, second, third = triangle
    normal = _cross(_subtract(second, origin), _subtract(third, origin))
    direction = _subtract(b, a)
    denominator = _dot(normal, direction)
    if denominator == 0:
        return False  # Coplanar contacts are caught by point/edge distance.
    parameter = _dot(normal, _subtract(origin, a)) / denominator
    if not 0 <= parameter <= 1:
        return False
    point = _add(a, _scale(direction, parameter))
    return _point_triangle_squared(point, triangle) <= numerical_epsilon**2


def triangle_distance(
    first: tuple[Coordinate, Coordinate, Coordinate],
    second: tuple[Coordinate, Coordinate, Coordinate],
    *, numerical_epsilon: float = 1e-9,
) -> float:
    """Distance of actual triangles, including coplanar and transverse intersections.

    Inputs must be finite nondegenerate geometry already checked by GeometrySurface.
    numerical_epsilon handles intersection arithmetic; it is not clearance approval.
    """
    edges1 = tuple(zip(first, (*first[1:], first[0]), strict=True))
    edges2 = tuple(zip(second, (*second[1:], second[0]), strict=True))
    if any(_segment_intersects_triangle(a, b, second, numerical_epsilon) for a, b in edges1):
        return 0.0
    if any(_segment_intersects_triangle(a, b, first, numerical_epsilon) for a, b in edges2):
        return 0.0
    squared = min(
        *(_point_triangle_squared(point, second) for point in first),
        *(_point_triangle_squared(point, first) for point in second),
        *(_segment_squared(a, b, c, d) for a, b in edges1 for c, d in edges2),
    )
    return math.sqrt(max(0.0, squared))


def surface_distance(first: GeometrySurface, second: GeometrySurface) -> float:
    """Exact-triangle distance; no bounds are substituted for collider geometry."""
    if not first.triangles or not second.triangles:
        raise ValueError("surface distance requires actual triangles, not annotation points")
    return min(
        triangle_distance(
            tuple(first.vertices[index] for index in triangle1),  # type: ignore[arg-type]
            tuple(second.vertices[index] for index in triangle2),  # type: ignore[arg-type]
        )
        for triangle1 in first.triangles for triangle2 in second.triangles
    )


def clip_triangle_to_box(
    triangle: tuple[Coordinate, Coordinate, Coordinate],
    minimum: Coordinate, maximum: Coordinate,
) -> tuple[Coordinate, ...]:
    """Clip actual triangle against an explicit protected aperture box.

    The result includes point/line contact; an enclosed triangle is retained.
    This box is never exposed as wall/collider geometry.
    """
    if any(not math.isfinite(value) for point in (*triangle, minimum, maximum) for value in point):
        raise ValueError("triangle/box coordinates must be finite")
    if any(low > high for low, high in zip(minimum, maximum, strict=True)):
        raise ValueError("box minimum must not exceed maximum")
    polygon: tuple[Coordinate, ...] = triangle
    for axis in range(3):
        for boundary, retain_greater in ((minimum[axis], True), (maximum[axis], False)):
            if not polygon:
                return ()
            result: list[Coordinate] = []
            previous = polygon[-1]
            previous_inside = (
                previous[axis] >= boundary if retain_greater else previous[axis] <= boundary
            )
            for point in polygon:
                inside = point[axis] >= boundary if retain_greater else point[axis] <= boundary
                if inside != previous_inside:
                    ratio = (boundary - previous[axis]) / (point[axis] - previous[axis])
                    result.append(_add(previous, _scale(_subtract(point, previous), ratio)))
                if inside:
                    result.append(point)
                previous, previous_inside = point, inside
            polygon = tuple(result)
    return polygon


def promoted_wall_portal_conflicts(
    wall: GeometrySurface, portal_surfaces: tuple[GeometrySurface, ...],
    *, tolerance_m: float, unit_scale_m: float,
) -> tuple[str, ...]:
    """Return protected portal IDs hit by actual WALL triangles, floor aware.

    Every portal is checked, even HUMAN_REVIEW/REJECTED annotations. An unknown
    floor cannot bypass protection. Protection boxes derive from the explicit
    aperture vertices; neither wall hulls nor claimed no-conflict flags are used.
    """
    if not math.isfinite(tolerance_m) or tolerance_m < 0:
        raise ValueError("portal tolerance must be finite and nonnegative")
    if not math.isfinite(unit_scale_m) or unit_scale_m <= 0:
        raise ValueError("unit_scale_m must be finite and positive")
    if wall.role != GeometryRole.WALL:
        raise ValueError("portal protection expects WALL surface evidence")
    padding = tolerance_m / unit_scale_m
    conflicts: list[str] = []
    for portal in portal_surfaces:
        if portal.role != GeometryRole.PORTAL:
            raise ValueError("portal protection requires explicit PORTAL geometry")
        minimum: Coordinate = tuple(  # type: ignore[assignment]
            min(point[axis] for point in portal.vertices) - padding for axis in range(3)
        )
        maximum: Coordinate = tuple(  # type: ignore[assignment]
            max(point[axis] for point in portal.vertices) + padding for axis in range(3)
        )
        # Geometry, rather than unapproved floor strings, proves aperture disjointness.
        if any(
            max(point[axis] for point in wall.vertices) < minimum[axis]
            or min(point[axis] for point in wall.vertices) > maximum[axis]
            for axis in range(3)
        ):
            continue
        if any(clip_triangle_to_box(
            (wall.vertices[a], wall.vertices[b], wall.vertices[c]), minimum, maximum,
        ) for a, b, c in wall.triangles):
            conflicts.append(portal.surface_id)
    return tuple(sorted(set(conflicts)))


class SceneGeometrySnapshot(GeometryModel):
    schema_version: Literal["scene-geometry-v1"] = "scene-geometry-v1"
    source_sha256: Digest
    scene_id: str = Field(min_length=1)
    unit_scale_m: Annotated[FiniteFloat, Field(gt=0)]
    scale_authority: Authority = Authority.HUMAN_REVIEW
    scale_approval_id: str | None = Field(default=None, min_length=1)
    physical_complete: bool = False
    coordinate_convention: Literal["RIGHT_HANDED_Z_UP"] = "RIGHT_HANDED_Z_UP"
    portal_protection_tolerance_m: Nonnegative = 0.0
    floors: tuple[FloorAuthority, ...]
    surfaces: tuple[GeometrySurface, ...]
    portals: tuple[PortalGeometry, ...] = ()
    stairs: tuple[StairGeometry, ...] = ()

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        _check_approval((self.scale_authority,), self.scale_approval_id)
        def unique(ids: tuple[str, ...], kind: str) -> None:
            if len(set(ids)) != len(ids):
                raise ValueError(f"duplicate {kind} identity")

        unique(tuple(floor.floor_id for floor in self.floors), "floor")
        unique(tuple(surface.surface_id for surface in self.surfaces), "surface")
        unique(tuple(portal.portal_id for portal in self.portals), "portal")
        unique(tuple(stair.stair_id for stair in self.stairs), "stair")
        floors = {floor.floor_id: floor for floor in self.floors}
        surfaces = {surface.surface_id: surface for surface in self.surfaces}
        portal_ids = {portal.portal_id for portal in self.portals}
        stair_ids = {stair.stair_id for stair in self.stairs}
        for surface in self.surfaces:
            if any(floor_id not in floors for floor_id in surface.floor_ids):
                raise ValueError(f"unknown floor reference on surface {surface.surface_id}")
            if any(portal_id not in portal_ids for portal_id in surface.portal_ids):
                raise ValueError("unknown portal reference on surface")
            if surface.stair_id is not None and surface.stair_id not in stair_ids:
                raise ValueError("unknown stair reference on surface")
            if surface.physical_authority == Authority.APPROVED and (
                self.scale_authority != Authority.APPROVED or not surface.floor_ids or any(
                    floors[floor_id].authority != Authority.APPROVED
                    for floor_id in surface.floor_ids
                )
            ):
                raise ValueError(
                    "APPROVED physical surface requires approved floor and scale authority"
                )
        for portal in self.portals:
            if portal.floor_id not in floors:
                raise ValueError("unknown floor reference on portal")
            if portal.surface_id not in surfaces or (
                surfaces[portal.surface_id].role != GeometryRole.PORTAL
                or portal.floor_id not in surfaces[portal.surface_id].floor_ids
            ):
                raise ValueError("portal must reference same-floor actual PORTAL geometry")
            for identity in portal.adjacent_walkable_ids:
                if identity not in surfaces or (
                    surfaces[identity].role != GeometryRole.WALKABLE
                    or portal.floor_id not in surfaces[identity].floor_ids
                ):
                    raise ValueError("portal neighbor must reference same-floor WALKABLE")
        for stair in self.stairs:
            if stair.floor_from not in floors or stair.floor_to not in floors:
                raise ValueError("unknown floor reference on stair")
            for identity in (
                *stair.path_surface_ids,
                *((stair.entry_surface_id,) if stair.entry_surface_id else ()),
                *((stair.exit_surface_id,) if stair.exit_surface_id else ()),
            ):
                if identity not in surfaces or surfaces[identity].role != GeometryRole.STAIR:
                    raise ValueError("stair surface must reference actual STAIR geometry")
        for wall in self.surfaces:
            if wall.role != GeometryRole.WALL or wall.semantic_authority not in (
                Authority.APPROVED, Authority.HIGH_CONFIDENCE,
            ):
                continue
            if not wall.floor_ids:
                raise ValueError("promoted wall requires floor assignment for portal protection")
            conflicts = promoted_wall_portal_conflicts(
                wall, tuple(surfaces[portal.surface_id] for portal in self.portals),
                tolerance_m=self.portal_protection_tolerance_m, unit_scale_m=self.unit_scale_m,
            )
            if conflicts:
                raise ValueError(
                    f"promoted wall {wall.surface_id} violates protected portals {conflicts}"
                )
        if self.physical_complete and (
            self.scale_authority != Authority.APPROVED
            or not floors or any(floor.authority != Authority.APPROVED for floor in self.floors)
            or any(not any(
                surface.role == GeometryRole.WALKABLE
                and floor.floor_id in surface.floor_ids
                and surface.physical_authority == Authority.APPROVED
                for surface in self.surfaces
            ) for floor in self.floors)
            or any(
                surface.physical_authority != Authority.APPROVED for surface in self.surfaces
                if surface.role in (GeometryRole.WALKABLE, GeometryRole.WALL, GeometryRole.OBSTACLE)
            )
            or any(
                surface.role == GeometryRole.WALL
                and surface.semantic_authority == Authority.HUMAN_REVIEW
                for surface in self.surfaces
            )
            or any(portal.authority != Authority.APPROVED for portal in self.portals)
            or any(status != Authority.APPROVED for stair in self.stairs for status in (
                stair.connectivity_authority, stair.opening_authority, stair.clearance_authority,
            ))
        ):
            raise ValueError(
                "physical_complete cannot be true while physical authority remains unresolved"
            )
        return self


class SceneGeometryProvider(Protocol):
    def get_walkable(self, floor_id: str | None = None) -> tuple[GeometrySurface, ...]: ...
    def get_walls(self, floor_id: str | None = None) -> tuple[GeometrySurface, ...]: ...
    def get_obstacles(self, floor_id: str | None = None) -> tuple[GeometrySurface, ...]: ...
    def get_portals(self, floor_id: str | None = None) -> tuple[PortalGeometry, ...]: ...
    def get_stairs(self) -> tuple[StairGeometry, ...]: ...
    def get_floors(self) -> tuple[FloorAuthority, ...]: ...
    def require_approved_physics(self, floor_id: str) -> tuple[GeometrySurface, ...]: ...


@dataclass(frozen=True, slots=True)
class ReadOnlySceneGeometryProvider:
    snapshot: SceneGeometrySnapshot
    expected_source_sha256: InitVar[str]

    def __post_init__(self, expected_source_sha256: str) -> None:
        # Revalidate even model_construct instances supplied by another Python caller.
        validated = SceneGeometrySnapshot.model_validate(self.snapshot)
        if validated.source_sha256 != expected_source_sha256:
            raise ValueError("scene geometry source SHA-256 does not match caller expectation")
        object.__setattr__(self, "snapshot", validated)

    @classmethod
    def from_json(cls, path: Path, *, expected_source_sha256: str) -> Self:
        return cls(
            SceneGeometrySnapshot.model_validate_json(path.read_text(encoding="utf-8")),
            expected_source_sha256,
        )

    def _check_floor(self, floor_id: str | None) -> None:
        if floor_id is not None and floor_id not in {
            floor.floor_id for floor in self.snapshot.floors
        }:
            raise KeyError(f"unknown floor: {floor_id}")

    def _get_role(self, role: GeometryRole, floor_id: str | None) -> tuple[GeometrySurface, ...]:
        self._check_floor(floor_id)
        return tuple(sorted((
            surface for surface in self.snapshot.surfaces
            if surface.role == role and (floor_id is None or floor_id in surface.floor_ids)
        ), key=lambda surface: surface.surface_id))

    def get_walkable(self, floor_id: str | None = None) -> tuple[GeometrySurface, ...]:
        return self._get_role(GeometryRole.WALKABLE, floor_id)

    def get_walls(self, floor_id: str | None = None) -> tuple[GeometrySurface, ...]:
        return self._get_role(GeometryRole.WALL, floor_id)

    def get_obstacles(self, floor_id: str | None = None) -> tuple[GeometrySurface, ...]:
        return self._get_role(GeometryRole.OBSTACLE, floor_id)

    def get_portals(self, floor_id: str | None = None) -> tuple[PortalGeometry, ...]:
        self._check_floor(floor_id)
        return tuple(sorted((
            portal for portal in self.snapshot.portals
            if floor_id is None or portal.floor_id == floor_id
        ), key=lambda portal: portal.portal_id))

    def get_stairs(self) -> tuple[StairGeometry, ...]:
        return tuple(sorted(self.snapshot.stairs, key=lambda stair: stair.stair_id))

    def get_floors(self) -> tuple[FloorAuthority, ...]:
        return tuple(sorted(self.snapshot.floors, key=lambda floor: floor.floor_id))

    def get_colliders(
        self, floor_id: str, *, authority: Authority = Authority.APPROVED,
    ) -> tuple[GeometrySurface, ...]:
        """Inspection filter only; an empty tuple never certifies collision-free space."""
        self._check_floor(floor_id)
        if authority not in (Authority.APPROVED, Authority.HIGH_CONFIDENCE):
            raise ValueError("collider queries require APPROVED or explicit HIGH_CONFIDENCE")
        return tuple(sorted((
            surface for surface in self.snapshot.surfaces
            if floor_id in surface.floor_ids
            and surface.role in (GeometryRole.WALL, GeometryRole.OBSTACLE)
            and surface.physical_authority == authority
            and (surface.blocks_movement or surface.occludes_visibility)
        ), key=lambda surface: surface.surface_id))

    def require_approved_physics(self, floor_id: str) -> tuple[GeometrySurface, ...]:
        """Fail closed before formal collision use; return the approved input surfaces.

        This gate does not validate a route. Consumers still perform segment/
        clearance validation after obtaining a complete, approved physical scope.
        """
        reasons: list[str] = []
        if not self.snapshot.physical_complete:
            reasons.append("PHYSICAL_AUTHORITY_INCOMPLETE")
        floor = next((item for item in self.snapshot.floors if item.floor_id == floor_id), None)
        if floor is None:
            reasons.append(f"FLOOR_AUTHORITY_MISSING:{floor_id}")
        elif floor.authority != Authority.APPROVED:
            reasons.append(f"FLOOR_NOT_APPROVED:{floor_id}")
        if self.snapshot.scale_authority != Authority.APPROVED:
            reasons.append("SCALE_NOT_APPROVED")
        walkable = self.get_walkable(floor_id) if floor is not None else ()
        if not walkable:
            reasons.append(f"WALKABLE_AUTHORITY_MISSING:{floor_id}")
        elif not any(item.physical_authority == Authority.APPROVED for item in walkable):
            reasons.append(f"WALKABLE_SCOPE_NOT_APPROVED:{floor_id}")
        for surface in sorted(self.snapshot.surfaces, key=lambda item: item.surface_id):
            if floor_id not in surface.floor_ids:
                continue
            if surface.role == GeometryRole.WALKABLE:
                if surface.physical_authority != Authority.APPROVED:
                    reasons.append(f"WALKABLE_NOT_APPROVED:{surface.surface_id}")
            elif surface.role in (GeometryRole.WALL, GeometryRole.OBSTACLE) and (
                surface.physical_authority != Authority.APPROVED
            ):
                reasons.append(f"COLLIDER_NOT_APPROVED:{surface.surface_id}")
        if reasons:
            raise GeometryAuthorityError(tuple(reasons))
        return self.get_colliders(floor_id)
