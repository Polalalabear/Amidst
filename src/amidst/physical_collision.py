"""Read-only full-body cylinder validation and stable pruning of an existing route pool.

The graph, ranking and truth are absent. Triangle bounds only accelerate exact
convex distance queries. A partial collider scope proves known collisions, never
the absence of unclassified geometry or complete physical validity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations, pairwise
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import Field, FiniteFloat

from amidst.domain.trajectory import CandidateTrajectory
from amidst.physical_authority import (
    ApprovedPhysicalInputs,
    PhysicalPurpose,
    PhysicalScope,
    ReadOnlyPhysicalAuthorityProvider,
)
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.scene_geometry import (
    Authority,
    Coordinate,
    FloorAuthority,
    GeometryModel,
    GeometrySupport,
    GeometrySurface,
)

VectorArray = NDArray[np.float64]


class CollisionNumerics(GeometryModel):
    schema_version: Literal["physical-collision-numerics-v1"] = "physical-collision-numerics-v1"
    units: Literal["metres"] = "metres"
    distance_error_budget_m: FiniteFloat = Field(gt=0)
    maximum_distance_iterations: int = Field(gt=0)
    maximum_triangles_per_segment: int = Field(gt=0)
    uncertain_distance: Literal["REFUSE_VALIDATION"] = "REFUSE_VALIDATION"
    research_metric_epsilon_changed: Literal[False] = False


@dataclass(frozen=True, slots=True)
class ConvexDistance:
    lower_m: float
    upper_m: float
    iterations: int
    converged: bool


def _closest_simplex(points: list[VectorArray]) -> tuple[VectorArray, list[VectorArray]]:
    """Closest feasible convex combination; degenerate subsets retain vertex alternatives."""
    best: tuple[float, tuple[int, ...], VectorArray] | None = None
    for size in range(1, min(4, len(points)) + 1):
        for selected in combinations(range(len(points)), size):
            vertices = np.array([points[index] for index in selected])
            if size == 1:
                closest = vertices[0]
            else:
                gram = vertices @ vertices.T
                system = np.zeros((size + 1, size + 1))
                system[:size, :size] = gram
                system[size, :size] = system[:size, size] = 1
                rhs = np.zeros(size + 1)
                rhs[size] = 1
                try:
                    weights = np.linalg.solve(system, rhs)[:size]
                except np.linalg.LinAlgError:
                    continue
                if np.any(weights < -1e-13):
                    continue
                weights = np.maximum(weights, 0)
                weights /= weights.sum()
                closest = weights @ vertices
            distance = float(closest @ closest)
            if best is None or distance < best[0]:
                best = (distance, selected, closest)
    if best is None:
        raise ValueError("finite simplex has no feasible vertex")
    return best[2], [points[index] for index in best[1]]


def upright_body_triangle_distance(
    footpoint_vertices_m: tuple[Coordinate, ...],
    triangle_m: tuple[Coordinate, Coordinate, Coordinate],
    *, radius_m: float, height_m: float, numerics: CollisionNumerics,
) -> ConvexDistance:
    """Distance between a convex footpoint domain plus an upright body and a triangle.

    Analytic support functions retain circular sides and flat caps. The capsule
    in XY is extruded by body height; all support heights enter the swept hull.
    No cylinder sampling, wall AABB substitution or guessed obstacle extrusion.
    """
    numerics = CollisionNumerics.model_validate(numerics)
    if not footpoint_vertices_m:
        raise ValueError("a body domain requires at least one footpoint")
    values = np.asarray([*footpoint_vertices_m, *triangle_m], dtype=np.float64)
    if not np.isfinite(values).all() or not all(
        math.isfinite(value) and value > 0 for value in (radius_m, height_m)
    ):
        raise ValueError("cylinder/triangle inputs must be finite with a positive body")
    # Local coordinates reduce cancellation on large building-world offsets.
    anchor = values[0].copy()
    values -= anchor
    footpoints = values[:-3]
    triangle = values[-3:]
    if np.linalg.norm(np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])) == 0:
        raise ValueError("degenerate collision triangle")

    def body_support(direction: VectorArray) -> VectorArray:
        point = footpoints[int(np.argmax(footpoints @ direction))].copy()
        norm_xy = float(np.linalg.norm(direction[:2]))
        if norm_xy:
            point[:2] += radius_m * direction[:2] / norm_xy
        if direction[2] > 0:
            point[2] += height_m
        return np.asarray(point, dtype=np.float64)

    def support(direction: VectorArray) -> VectorArray:
        point = body_support(direction)
        opposite = triangle[int(np.argmax(triangle @ -direction))]
        return np.asarray(point - opposite, dtype=np.float64)

    simplex = [support(np.array([1.0, 0.0, 0.0]))]
    normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
    normal /= np.linalg.norm(normal)
    plane = float(triangle[0] @ normal)
    # The unbounded triangle plane supplies an independent analytic lower bound.
    # It also preserves inclusive equality on flat walls and overhead faces.
    lower = max(0.0, plane - float(body_support(normal) @ normal),
                float(body_support(-normal) @ normal) - plane)
    for iteration in range(1, numerics.maximum_distance_iterations + 1):
        closest, simplex = _closest_simplex(simplex)
        upper = float(np.linalg.norm(closest))
        if upper <= numerics.distance_error_budget_m:
            return ConvexDistance(0.0, upper, iteration, True)
        next_point = support(-closest)
        lower = max(lower, 0.0, float(closest @ next_point) / upper)
        lower = min(lower, upper)
        if upper - lower <= numerics.distance_error_budget_m:
            return ConvexDistance(lower, upper, iteration, True)
        if any(np.array_equal(next_point, point) for point in simplex):
            return ConvexDistance(lower, upper, iteration, False)
        simplex.append(next_point)
    return ConvexDistance(lower, upper, numerics.maximum_distance_iterations, False)


def cylinder_triangle_distance(
    start_m: Coordinate, end_m: Coordinate, triangle_m: tuple[Coordinate, Coordinate, Coordinate],
    *, radius_m: float, height_m: float, numerics: CollisionNumerics,
) -> ConvexDistance:
    """Continuous segment sweep, with no time sampling or point-body substitution."""
    return upright_body_triangle_distance(
        (start_m, end_m), triangle_m, radius_m=radius_m, height_m=height_m, numerics=numerics,
    )


def point_inside_closed_mesh(point: VectorArray, triangles: VectorArray) -> bool | None:
    """Signed solid-angle containment of a prevalidated closed, consistently wound mesh.

    Ray tangencies cannot toggle parity. Boundary points and uncertain winding
    return None, never a certified exterior. Arithmetic error checks concern
    normalized angles only; they do not buffer or shrink physical geometry.
    """
    if (
        point.shape != (3,) or triangles.ndim != 3 or triangles.shape[1:] != (3, 3)
        or not len(triangles) or not np.isfinite(point).all()
        or not np.isfinite(triangles).all()
    ):
        raise ValueError("closed-volume containment requires finite point and actual triangles")
    offsets = triangles - point
    lengths = np.linalg.norm(offsets, axis=2)
    if not np.isfinite(lengths).all() or np.any(lengths == 0):
        return None
    directions = offsets / lengths[:, :, np.newaxis]
    a, b, c = directions[:, 0], directions[:, 1], directions[:, 2]
    numerator = np.einsum("ij,ij->i", a, np.cross(b, c))
    denominator = (1.0 + np.einsum("ij,ij->i", a, b)
                   + np.einsum("ij,ij->i", b, c) + np.einsum("ij,ij->i", c, a))
    arithmetic_epsilon = 64 * np.finfo(np.float64).eps
    # Coplanar directions spanning at least a half sphere are a point on
    # the actual triangle, not a ray-crossing/solid-angle choice of sign.
    if np.any((np.abs(numerator) <= arithmetic_epsilon)
              & (denominator <= arithmetic_epsilon)):
        return None
    angles = 2 * np.arctan2(numerator, denominator)
    if not np.isfinite(angles).all():
        return None
    winding = abs(math.fsum(float(value) for value in angles)) / (4 * math.pi)
    integer = round(winding)
    arithmetic_budget = 128 * np.finfo(np.float64).eps * len(triangles)
    if integer not in (0, 1) or abs(winding - integer) > arithmetic_budget:
        return None
    return integer == 1


@dataclass(frozen=True, slots=True)
class PhysicalPathDecision:
    state: Literal["RETAINED", "REJECTED", "UNVALIDATED"]
    reasons: tuple[str, ...]
    tested_triangles: int
    complete_physical_validation: bool


class CylinderCollisionConsumer:
    """Obtain formal inputs only through an approved purpose-specific provider gate."""

    def __init__(
        self, inputs: ApprovedPhysicalInputs, contract: PhysicalPolicyContract,
        numerics: CollisionNumerics,
    ) -> None:
        contract.scale.require_source_sha256(inputs.source_sha256)
        scope = PhysicalScope.model_validate(inputs.scope)
        if scope.authority != Authority.APPROVED or (
            scope.purpose != PhysicalPurpose.KNOWN_COLLISION_PRUNING
        ):
            raise ValueError("collision consumer requires an approved collision-pruning scope")
        floors = tuple(FloorAuthority.model_validate(floor) for floor in inputs.floors)
        if not floors or any(floor.authority != Authority.APPROVED for floor in floors):
            raise ValueError("collision consumer requires approved physical floors")
        if {floor.floor_id for floor in floors} != set(scope.floor_ids):
            raise ValueError("collision consumer floors must match approved scope floors")
        if inputs.policy != contract.policy:
            raise ValueError("collision consumer policy differs from authority policy")
        self.inputs = inputs
        self.contract = contract
        self.numerics = CollisionNumerics.model_validate(numerics)
        self.floor_planes = tuple(
            (
                floor.floor_id,
                np.asarray(floor.point, dtype=np.float64) * contract.scale.metres_per_blender_unit,
                np.asarray(floor.normal, dtype=np.float64) / np.linalg.norm(floor.normal),
            )
            for floor in floors
        )
        self.meshes: tuple[tuple[GeometrySurface, VectorArray], ...] = tuple(
            (
                GeometrySurface.model_validate(surface),
                np.asarray(surface.vertices, dtype=np.float64)[np.asarray(surface.triangles)]
                * contract.scale.metres_per_blender_unit,
            )
            for surface in inputs.colliders
        )
        if any(surface.physical_authority != Authority.APPROVED for surface, _ in self.meshes):
            raise ValueError("REVIEW geometry cannot become a formal collider")

    @classmethod
    def from_provider(
        cls, provider: ReadOnlyPhysicalAuthorityProvider, scope_id: str,
        contract: PhysicalPolicyContract, numerics: CollisionNumerics,
    ) -> CylinderCollisionConsumer:
        inputs = provider.require_scope(scope_id, purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING)
        return cls(inputs, contract, numerics)

    def validate(self, polyline_m: tuple[Coordinate, ...]) -> PhysicalPathDecision:
        if len(polyline_m) < 2 or not np.isfinite(np.asarray(polyline_m)).all():
            raise ValueError("physical polyline requires two or more finite points")
        radius, height = (
            self.contract.parameter("body_radius_m"), self.contract.parameter("body_height_m"),
        )
        clearance = self.contract.parameter("body_clearance_m")
        contact = self.contract.parameter("collision_tolerance_m")
        # This band binds the foot reference to its approved floor. It neither
        # certifies walkable support nor widens the separate clearance minimum.
        point_floors = []
        for index, point in enumerate(polyline_m):
            matching = frozenset(
                floor_id for floor_id, origin, normal in self.floor_planes
                if abs(float((np.asarray(point) - origin) @ normal)) <= contact
            )
            if not matching:
                return PhysicalPathDecision("UNVALIDATED", (
                    f"OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:point={index}",
                ), 0, False)
            point_floors.append(matching)
        for index, (first, second) in enumerate(pairwise(point_floors)):
            # A straight segment remains in one plane's contact band only when
            # both endpoints share that plane. No approved stair sweep is given.
            if not first.intersection(second):
                return PhysicalPathDecision("UNVALIDATED", (
                    f"OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:segment={index}",
                ), 0, False)
        tested = 0
        for segment_index, (start, end) in enumerate(pairwise(polyline_m)):
            segment_tested = 0
            points = np.asarray([start, end])
            lower = points.min(axis=0) - np.array([radius + clearance] * 2 + [clearance])
            upper = points.max(axis=0) + np.array([radius + clearance] * 2 + [height + clearance])
            for surface, triangles in self.meshes:
                for point in (points[0], points[1]):
                    center = point + np.array([0, 0, height / 2])
                    if surface.support == GeometrySupport.VOLUME:
                        inside = point_inside_closed_mesh(center, triangles)
                        if inside is None:
                            return PhysicalPathDecision(
                                "UNVALIDATED", (
                                    f"CLOSED_VOLUME_CONTAINMENT_UNCERTAIN:{surface.surface_id}",
                                ), tested, False,
                            )
                        if inside:
                            return PhysicalPathDecision(
                                "REJECTED", (f"BODY_INSIDE_COLLIDER:{surface.surface_id}",), tested,
                                False,
                            )
                selected = triangles[
                    (triangles.max(axis=1) >= lower).all(axis=1)
                    & (triangles.min(axis=1) <= upper).all(axis=1)
                ]
                for triangle in selected:
                    tested += 1
                    segment_tested += 1
                    if segment_tested > self.numerics.maximum_triangles_per_segment:
                        return PhysicalPathDecision(
                            "UNVALIDATED", ("COLLISION_TRIANGLE_BUDGET_EXCEEDED",), tested, False,
                        )
                    a, b, c = triangle
                    triangle_coordinates = (
                        (float(a[0]), float(a[1]), float(a[2])),
                        (float(b[0]), float(b[1]), float(b[2])),
                        (float(c[0]), float(c[1]), float(c[2])),
                    )
                    distance = cylinder_triangle_distance(
                        start, end, triangle_coordinates,
                        radius_m=radius, height_m=height, numerics=self.numerics,
                    )
                    if distance.upper_m <= contact:
                        return PhysicalPathDecision("REJECTED", (
                            f"COLLISION_CONTACT:{surface.surface_id}:segment={segment_index}",
                        ), tested, False)
                    # ULP handling addresses float representation at exact equality only;
                    # the research contact tolerance never relaxes the clearance minimum.
                    roundoff = 16 * math.ulp(max(clearance, distance.upper_m, 1.0))
                    if distance.upper_m < clearance - roundoff:
                        return PhysicalPathDecision("REJECTED", (
                            f"BODY_CLEARANCE_VIOLATION:{surface.surface_id}:"
                            f"segment={segment_index}",
                        ), tested, False)
                    if distance.lower_m < clearance - roundoff:
                        return PhysicalPathDecision("UNVALIDATED", (
                            f"COLLISION_DISTANCE_UNCERTAIN:{surface.surface_id}:"
                            f"segment={segment_index}",
                        ), tested, False)
        return PhysicalPathDecision("RETAINED", (), tested, False)


def prune_before_top_k(
    candidate_pool: tuple[CandidateTrajectory, ...], consumer: CylinderCollisionConsumer,
    *, top_k: int,
) -> tuple[tuple[CandidateTrajectory, ...], dict[str, object]]:
    """Filter the supplied ordered pool before truncation; no rescoring or GT interface."""
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("physical Top-K must be a positive integer")
    if len({candidate.candidate_id for candidate in candidate_pool}) != len(candidate_pool):
        raise ValueError("physical candidate pool contains duplicate IDs")
    retained: list[CandidateTrajectory] = []
    records: list[dict[str, object]] = []
    for candidate in candidate_pool:
        checked = CandidateTrajectory.model_validate(candidate.model_dump(mode="python"))
        decision = consumer.validate(checked.polyline)
        if decision.state == "RETAINED":
            retained.append(checked)
        records.append({
            "candidate_id": checked.candidate_id, "state": decision.state,
            "reasons": decision.reasons, "tested_triangles": decision.tested_triangles,
            "complete_physical_validation": decision.complete_physical_validation,
        })
    return tuple(retained[:top_k]), {
        "before_count": len(candidate_pool), "after_pruning_count": len(retained),
        "output_count": min(top_k, len(retained)), "requested_k": top_k,
        "records": records, "ordering": "INPUT_RELATIVE_ORDER_PRESERVED",
        "scope_id": consumer.inputs.scope.scope_id,
        "coverage": str(consumer.inputs.scope.coverage),
        "source_sha256": consumer.inputs.source_sha256,
        "geometry_sha256": consumer.inputs.geometry_sha256,
        "gt_used": False, "ranking_changed": False,
        "known_collision_pruning_only": True,
    }


def load_collision_numerics(path: Path | str) -> CollisionNumerics:
    return CollisionNumerics.model_validate_json(Path(path).read_bytes())
