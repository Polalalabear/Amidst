"""Independent lower bounds on source-bound, same-floor scoped route classes.

Canonical representatives come from approved cell geometry. Exact rational
coverage, a genuine source triangle witness in a bounded union hole, and integer
winding separate supplied representatives. Graph outputs, GT and parallel offsets
are absent. This proves inequality of classes, not exhaustive protocol eligibility.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from fractions import Fraction
from itertools import combinations, pairwise
from typing import Any, Literal

from pydantic import Field, FiniteFloat, model_validator

from amidst.finalization.scoped_authority import (
    ScopeAuthorityPins,
    ScopedUnionPhysicalProvider,
    SourceFaceBinding,
    build_source_face_binding,
)
from amidst.obstacle_volume_authority import content_sha256, validate_source_evidence
from amidst.physical_collision import CollisionNumerics
from amidst.scene_geometry import Coordinate, Digest, GeometryAuthorityError, GeometryModel

QPoint = tuple[Fraction, Fraction]
QRectangle = tuple[Fraction, Fraction, Fraction, Fraction]
RECALL_BLOCKER = "INDEPENDENT_EXHAUSTIVE_ELIGIBILITY_EQUIVALENCE_NOT_PROVEN"


class ScopedRouteAuthorityBinding(GeometryModel):
    pins: ScopeAuthorityPins
    proposal_content_sha256: Digest
    decision_content_sha256: Digest
    certificate_content_sha256: Digest
    union_wkb_sha256: Digest


class ScopedCanonicalPath(GeometryModel):
    path_id: str = Field(min_length=1)
    authority: ScopedRouteAuthorityBinding
    construction: Literal["EXACT_CELL_OVERLAP_VERTICES_FIXED_ENDPOINTS"] = (
        "EXACT_CELL_OVERLAP_VERTICES_FIXED_ENDPOINTS"
    )
    cell_ids: tuple[str, ...] = Field(min_length=1)
    cell_proposal_content_sha256: tuple[Digest, ...] = Field(min_length=1)
    cell_certificate_content_sha256: tuple[Digest, ...] = Field(min_length=1)
    support_bindings: tuple[SourceFaceBinding, ...] = Field(min_length=1)
    polyline_bu: tuple[Coordinate, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def simple_cell_chain(self) -> ScopedCanonicalPath:
        if len(set(self.cell_ids)) != len(self.cell_ids) or not (
            len(self.cell_ids) == len(self.cell_proposal_content_sha256)
            == len(self.cell_certificate_content_sha256)
        ):
            raise ValueError(
                "canonical representative requires unique cells and aligned provenance",
            )
        return self


class SourceObstacleHoleWitness(GeometryModel):
    obstacle_binding_id: str = Field(min_length=1)
    source_triangle_index: int = Field(ge=0)
    barycentric_weights: tuple[FiniteFloat, FiniteFloat, FiniteFloat]


class ScopedRouteClassProof(GeometryModel):
    schema_version: Literal["phase1-scoped-source-route-class-lower-bound-v1"] = (
        "phase1-scoped-source-route-class-lower-bound-v1"
    )
    authority: ScopedRouteAuthorityBinding
    floor_id: str
    paths: tuple[ScopedCanonicalPath, ...]
    path_content_sha256: tuple[Digest, ...]
    source_obstacle_binding: SourceFaceBinding
    source_obstacle_binding_content_sha256: Digest
    witness: SourceObstacleHoleWitness
    exact_witness_xyz_bu: tuple[str, str, str]
    witness_semantic_bound_kind: Literal[
        "SOURCE_FACE_MOVEMENT_OBSTACLE_BOUND", "APPROVED_CELL_BODY_GUARDS",
    ]
    witness_semantic_guard_cell_ids: tuple[str, ...] = ()
    witness_semantic_bounds_bu: tuple[tuple[Coordinate, Coordinate], ...] = (
        Field(min_length=1)
    )
    hole_component_grid_bu: tuple[tuple[str, str, str, str], ...]
    hole_component_content_sha256: Digest
    hole_grid_cells_are_open: Literal[True] = True
    continuous_cell_coverage: tuple[dict[str, Any], ...]
    pair_windings: tuple[dict[str, Any], ...]
    distinct_classes_lower_bound: int = Field(ge=2)
    separation_method: Literal["EXACT_INTEGER_WINDING_SOURCE_WITNESS_IN_UNION_HOLE"] = (
        "EXACT_INTEGER_WINDING_SOURCE_WITNESS_IN_UNION_HOLE"
    )
    inventory_exhaustive: Literal[False] = False
    feasible_candidate_recall: None = None
    feasible_candidate_recall_status: Literal[
        "N/A_INDEPENDENT_EXHAUSTIVE_ELIGIBILITY_EQUIVALENCE_NOT_PROVEN",
    ] = "N/A_INDEPENDENT_EXHAUSTIVE_ELIGIBILITY_EQUIVALENCE_NOT_PROVEN"
    formal_case_readiness: Literal[False] = False
    source_distinct_class_scope: Literal["FIXED_ENDPOINTS_SAME_FLOOR_APPROVED_CELL_UNION"] = (
        "FIXED_ENDPOINTS_SAME_FLOOR_APPROVED_CELL_UNION"
    )
    graph_outputs_read: Literal[False] = False
    ground_truth_read: Literal[False] = False
    new_semantic_authority_granted: Literal[False] = False


def _q(value: float) -> Fraction:
    return Fraction.from_float(float(value))


def _xy(point: Coordinate) -> QPoint:
    return _q(point[0]), _q(point[1])


def _rectangles(provider: ScopedUnionPhysicalProvider) -> dict[str, QRectangle]:
    return {cell.cell_id: (_q(cell.rectangle_xy_bu[0]), _q(cell.rectangle_xy_bu[1]),
                          _q(cell.rectangle_xy_bu[2]), _q(cell.rectangle_xy_bu[3]))
            for cell in provider.proposal.cells}


def _covers(rect: QRectangle, point: QPoint) -> bool:
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def _check_authority(
    provider: ScopedUnionPhysicalProvider, expected: ScopedRouteAuthorityBinding,
) -> None:
    # This runs before evidence access or any topology/class claim. The provider
    # retains each physical/semantic cell wrapper and refuses pending decisions.
    if not isinstance(provider, ScopedUnionPhysicalProvider):
        raise TypeError("scoped route proof requires the intact approved union provider")
    provider.validate()
    expected = ScopedRouteAuthorityBinding.model_validate_json(expected.model_dump_json())
    certificate = provider.certificate
    actual = ScopedRouteAuthorityBinding(
        pins=certificate.pins, proposal_content_sha256=certificate.proposal_content_sha256,
        decision_content_sha256=certificate.human_decision_content_sha256,
        certificate_content_sha256=provider.certificate_content_sha256,
        union_wkb_sha256=certificate.union_wkb_sha256,
    )
    if actual != expected or content_sha256(provider.proposal.floor.model_dump(mode="json")) != (
        expected.pins.floor_content_sha256
    ):
        raise ValueError("scoped route source/proposal/decision/certificate/floor pins differ")


def _point(point: QPoint, z: float) -> Coordinate:
    result = float(point[0]), float(point[1]), z
    if _xy(result) != point:
        raise ValueError("source overlap vertex is not exactly representable in binary64")
    return result


def _canonical(
    provider: ScopedUnionPhysicalProvider, expected: ScopedRouteAuthorityBinding, *,
    path_id: str, cell_ids: tuple[str, ...], start_bu: Coordinate, end_bu: Coordinate,
) -> ScopedCanonicalPath:
    rectangles = _rectangles(provider)
    if not cell_ids or len(set(cell_ids)) != len(cell_ids) or any(
        identity not in rectangles for identity in cell_ids
    ):
        raise ValueError("canonical path requires an explicit simple chain of approved cells")
    z = provider.proposal.floor.point[2]
    if start_bu[2] != z or end_bu[2] != z or start_bu == end_bu:
        raise ValueError("canonical fixed endpoints require distinct exact floor-contact positions")
    if not _covers(rectangles[cell_ids[0]], _xy(start_bu)) or not _covers(
        rectangles[cell_ids[-1]], _xy(end_bu),
    ):
        raise ValueError("canonical endpoints differ from declared first/last approved cells")
    points = [start_bu]
    for first, second in pairwise(cell_ids):
        rect, next_rect = rectangles[first], rectangles[second]
        overlap = (max(rect[0], next_rect[0]), max(rect[1], next_rect[1]),
                   min(rect[2], next_rect[2]), min(rect[3], next_rect[3]))
        if overlap[0] > overlap[2] or overlap[1] > overlap[3]:
            raise ValueError("canonical cell chain crosses an unapproved gap")
        # The lexicographically first overlap vertex copies exact existing cell
        # boundaries. Consecutive vertices share a convex certified cell, avoiding
        # midpoint rounding and adding no geometric or research epsilon.
        points.append(_point((overlap[0], overlap[1]), z))
    points.append(end_bu)
    retained = tuple(point for index, point in enumerate(points)
                     if not index or point != points[index - 1])
    provider.validate_polyline(retained)
    by_id = {cell.cell_id: index for index, cell in enumerate(provider.proposal.cells)}
    return ScopedCanonicalPath(
        path_id=path_id, authority=expected, cell_ids=cell_ids,
        cell_proposal_content_sha256=tuple(content_sha256(
            provider.proposal.cells[by_id[identity]].model_dump(mode="json"),
        ) for identity in cell_ids),
        cell_certificate_content_sha256=tuple(
            provider.certificate.cell_content_sha256[by_id[identity]] for identity in cell_ids
        ), support_bindings=provider.proposal.support_bindings, polyline_bu=retained,
    )


def canonical_path_from_cells(
    provider: ScopedUnionPhysicalProvider, *, expected_binding: ScopedRouteAuthorityBinding,
    path_id: str, cell_ids: tuple[str, ...], start_bu: Coordinate, end_bu: Coordinate,
) -> ScopedCanonicalPath:
    """Construct source-cell representatives; endpoints are a separate public input.

    Endpoints must come from the caller's source/observation boundary. This utility
    reads no recipe, reference, observation file, graph or search output.
    """
    _check_authority(provider, expected_binding)
    return _canonical(provider, expected_binding, path_id=path_id, cell_ids=cell_ids,
                      start_bu=start_bu, end_bu=end_bu)


def _interval(start: QPoint, end: QPoint, rect: QRectangle) -> tuple[Fraction, Fraction] | None:
    low, high = Fraction(0), Fraction(1)
    for axis in range(2):
        delta = end[axis] - start[axis]
        if delta == 0:
            if not rect[axis] <= start[axis] <= rect[axis + 2]:
                return None
        else:
            a, b = (rect[axis] - start[axis]) / delta, (rect[axis + 2] - start[axis]) / delta
            low, high = max(low, min(a, b)), min(high, max(a, b))
            if low > high:
                return None
    return low, high


def _coverage(path: ScopedCanonicalPath, rectangles: dict[str, QRectangle]) -> dict[str, Any]:
    segments = []
    for index, (a, b) in enumerate(pairwise(path.polyline_bu)):
        intervals = sorted((interval[0], interval[1], identity)
                           for identity, rect in rectangles.items()
                           if (interval := _interval(_xy(a), _xy(b), rect)) is not None)
        covered = Fraction(0)
        for low, high, _ in intervals:
            if low > covered:
                break
            covered = max(covered, high)
        if not intervals or intervals[0][0] > 0 or covered < 1:
            raise GeometryAuthorityError(("EXACT_SEGMENT_NOT_COVERED_BY_APPROVED_CELLS",))
        segments.append({"segment_index": index, "cell_intervals": [
            {"cell_id": identity, "start_exact": str(low), "end_exact": str(high)}
            for low, high, identity in intervals
        ]})
    return {"path_id": path.path_id, "segments": segments, "epsilon_used": False}


def _bounded_hole(point: QPoint, rectangles: dict[str, QRectangle]) -> tuple[QRectangle, ...]:
    """Exact complement connectivity in the rectangle-boundary arrangement."""
    values = tuple(rectangles.values())
    if any(_covers(rect, point) for rect in values):
        raise ValueError("source witness is in the approved union, not an actual hole")
    xs = sorted({v for rect in values for v in (rect[0], rect[2])})
    ys = sorted({v for rect in values for v in (rect[1], rect[3])})
    if not xs[0] < point[0] < xs[-1] or not ys[0] < point[1] < ys[-1]:
        raise ValueError("source witness belongs to the unbounded complement")
    if (len(xs) - 1) * (len(ys) - 1) > 10000:
        raise ValueError("exact hole proof exceeds the bounded source arrangement budget")
    free = {(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)
            if not any(_covers(rect, ((xs[i] + xs[i + 1]) / 2,
                                     (ys[j] + ys[j + 1]) / 2)) for rect in values)}
    seeds = {(i, j) for i, j in free
             if xs[i] <= point[0] <= xs[i + 1] and ys[j] <= point[1] <= ys[j + 1]}
    if not seeds:
        raise ValueError("source witness has no exact open-complement neighbourhood")
    seen, queue = set(seeds), deque(sorted(seeds))
    while queue:
        i, j = queue.popleft()
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            edge = ((xs[i if di < 0 else i + 1], (ys[j] + ys[j + 1]) / 2) if di else
                    ((xs[i] + xs[i + 1]) / 2, ys[j if dj < 0 else j + 1]))
            if any(_covers(rect, edge) for rect in values):
                continue
            neighbour = i + di, j + dj
            if not (0 <= neighbour[0] < len(xs) - 1 and 0 <= neighbour[1] < len(ys) - 1):
                raise ValueError("source witness belongs to the unbounded complement")
            if neighbour in free and neighbour not in seen:
                seen.add(neighbour)
                queue.append(neighbour)
    return tuple((xs[i], ys[j], xs[i + 1], ys[j + 1]) for i, j in sorted(seen))


def _cross(a: QPoint, b: QPoint, q: QPoint) -> Fraction:
    return (b[0] - a[0]) * (q[1] - a[1]) - (q[0] - a[0]) * (b[1] - a[1])


def _winding(loop: tuple[Coordinate, ...], point: QPoint) -> int:
    result = 0
    for first, second in pairwise(loop):
        a, b = _xy(first), _xy(second)
        cross = _cross(a, b, point)
        if cross == 0 and min(a[0], b[0]) <= point[0] <= max(a[0], b[0]) and (
            min(a[1], b[1]) <= point[1] <= max(a[1], b[1])
        ):
            raise ValueError("winding is undefined on the source witness")
        if a[1] <= point[1] < b[1] and cross > 0:
            result += 1
        elif b[1] <= point[1] < a[1] and cross < 0:
            result -= 1
    return result


def prove_scoped_route_classes(
    provider: ScopedUnionPhysicalProvider, paths: tuple[ScopedCanonicalPath, ...],
    witness: SourceObstacleHoleWitness, source_evidence: Mapping[str, Any],
    numerics: CollisionNumerics, *, expected_binding: ScopedRouteAuthorityBinding,
) -> ScopedRouteClassProof:
    """Prove supplied canonical classes differ; never grant exhaustive recall/readiness."""
    _check_authority(provider, expected_binding)
    validate_source_evidence(
        source_evidence, expected_source_sha256=expected_binding.pins.source_sha256,
    )
    if content_sha256(source_evidence) != expected_binding.pins.evidence_content_sha256 or (
        content_sha256(CollisionNumerics.model_validate(numerics).model_dump(mode="json"))
        != expected_binding.pins.numerics_content_sha256
    ):
        raise ValueError("scoped route source evidence/numerics pins differ")
    paths = tuple(ScopedCanonicalPath.model_validate_json(path.model_dump_json()) for path in paths)
    witness = SourceObstacleHoleWitness.model_validate_json(witness.model_dump_json())
    if len(paths) < 2 or len({path.path_id for path in paths}) != len(paths):
        raise ValueError("route separation requires at least two unique representatives")
    endpoints = paths[0].polyline_bu[0], paths[0].polyline_bu[-1]
    coverage = []
    for path in paths:
        if (path.polyline_bu[0], path.polyline_bu[-1]) != endpoints:
            raise ValueError("route homotopy requires exactly equal fixed endpoints; no epsilon")
        canonical = _canonical(provider, expected_binding, path_id=path.path_id,
                               cell_ids=path.cell_ids, start_bu=endpoints[0], end_bu=endpoints[1])
        if path != canonical:
            raise ValueError("supplied route differs from exact cell construction/provenance")
        coverage.append(_coverage(path, _rectangles(provider)))
    bindings = [b for b in provider.proposal.obstacle_bindings
                if b.binding_id == witness.obstacle_binding_id]
    if len(bindings) != 1:
        raise ValueError("hole witness requires an exact approved movement obstacle binding")
    binding = bindings[0]
    regenerated = build_source_face_binding(
        source_evidence, binding_id=binding.binding_id, source_mesh_id=binding.source_mesh_id,
        source_component_id=binding.source_component_id,
        source_face_indices=binding.source_face_indices, proposed_role="MOVEMENT_OBSTACLE_SURFACE",
        source_face_movement_obstacle_bounds_bu=binding.source_face_movement_obstacle_bounds_bu,
    )
    if regenerated != binding or (
        witness.source_triangle_index not in binding.source_triangle_indices
    ):
        raise ValueError("hole witness source faces/triangles differ from approved binding")
    mesh = next(m for m in source_evidence["meshes"] if m["mesh_id"] == binding.source_mesh_id)
    triangle = tuple(tuple(_q(v) for v in mesh["vertices"][index])
                     for index in mesh["triangles"][witness.source_triangle_index])
    weights = tuple(_q(v) for v in witness.barycentric_weights)
    if min(weights) <= 0 or sum(weights) != 1:
        raise ValueError("source witness requires exact positive barycentric weights summing to 1")
    a, b = (tuple(triangle[index][axis] - triangle[0][axis] for axis in range(3))
            for index in (1, 2))
    if all(a[i] * b[j] == a[j] * b[i] for i, j in ((0, 1), (1, 2), (2, 0))):
        raise ValueError("degenerate source triangle cannot certify a physical obstacle witness")
    xyz = tuple(sum((weights[index] * triangle[index][axis] for index in range(3)), Fraction(0))
                for axis in range(3))
    semantic_guards = tuple(cell for cell in provider.proposal.cells if all(
        _q(cell.proposed_body_guard_bounds_bu[0][axis]) <= xyz[axis]
        <= _q(cell.proposed_body_guard_bounds_bu[1][axis]) for axis in range(3)
    ))
    explicit_bound = binding.source_face_movement_obstacle_bounds_bu
    explicit_witness_owned = explicit_bound is not None and all(
        _q(explicit_bound[0][axis]) <= xyz[axis] <= _q(explicit_bound[1][axis])
        for axis in range(3)
    )
    floor_z = _q(provider.proposal.floor.point[2])
    body_height = _q(provider.contract.parameter("body_height_m")) / _q(
        provider.contract.scale.metres_per_blender_unit,
    )
    if not floor_z < xyz[2] < floor_z + body_height:
        raise ValueError("source witness does not intersect approved upright body height")
    if not explicit_witness_owned and not semantic_guards:
        raise GeometryAuthorityError(("OBSTACLE_WITNESS_OUTSIDE_APPROVED_SEMANTIC_BOUNDS",))
    point = xyz[0], xyz[1]
    hole = tuple(tuple(str(v) for v in rect)
                 for rect in _bounded_hole(point, _rectangles(provider)))
    winding = []
    for left, right in combinations(paths, 2):
        loop = (*left.polyline_bu, *tuple(reversed(right.polyline_bu))[1:])
        number = _winding(loop, point)
        if not number:
            raise ValueError("exact winding does not separate the supplied route classes")
        winding.append({"first_path_id": left.path_id, "second_path_id": right.path_id,
                        "closed_path_pair_winding": number})
    return ScopedRouteClassProof(
        authority=expected_binding, floor_id=provider.proposal.floor.floor_id, paths=paths,
        path_content_sha256=tuple(content_sha256(p.model_dump(mode="json")) for p in paths),
        source_obstacle_binding=binding,
        source_obstacle_binding_content_sha256=content_sha256(binding.model_dump(mode="json")),
        witness=witness, exact_witness_xyz_bu=tuple(str(v) for v in xyz),  # type: ignore[arg-type]
        witness_semantic_bound_kind=("SOURCE_FACE_MOVEMENT_OBSTACLE_BOUND"
                                     if explicit_witness_owned else "APPROVED_CELL_BODY_GUARDS"),
        witness_semantic_guard_cell_ids=(tuple(cell.cell_id for cell in semantic_guards)
                                         if not explicit_witness_owned else ()),
        witness_semantic_bounds_bu=((explicit_bound,) if explicit_witness_owned and explicit_bound
                                   else tuple(cell.proposed_body_guard_bounds_bu
                                              for cell in semantic_guards)),
        hole_component_grid_bu=hole,  # type: ignore[arg-type]
        hole_component_content_sha256=content_sha256(hole),
        continuous_cell_coverage=tuple(coverage), pair_windings=tuple(winding),
        distinct_classes_lower_bound=len(paths),
    )


def validate_scoped_route_class_proof(
    proof: ScopedRouteClassProof, provider: ScopedUnionPhysicalProvider,
    source_evidence: Mapping[str, Any], numerics: CollisionNumerics, *,
    expected_binding: ScopedRouteAuthorityBinding, expected_proof_content_sha256: str,
) -> None:
    """Consumer gate: regenerate the independent proof instead of trusting its label."""
    proof = ScopedRouteClassProof.model_validate_json(proof.model_dump_json())
    regenerated = prove_scoped_route_classes(
        provider, proof.paths, proof.witness, source_evidence, numerics,
        expected_binding=expected_binding,
    )
    if regenerated != proof or content_sha256(proof.model_dump(mode="json")) != (
        expected_proof_content_sha256
    ):
        raise ValueError("scoped route class proof differs from exact regenerated/pinned evidence")
