"""Source-bound obstacle/stair measurements, without inferred physical certification.

This read-only diagnostic layer consumes world-space triangles, never Blender objects.
Role approval is supplied separately by the caller; annotations cannot approve themselves.
XY footprint conflicts preserve triangle holes. Stair contacts use actual 3D surfaces.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import Any

from amidst.scene_validation import (
    _GEOMETRY_BUDGET,
    GeometryBudgetExceeded,
    _floor,
    _intersections,
    _signed_area,
    _union_area,
)

Vector = tuple[float, float, float]
Triangle = tuple[Vector, Vector, Vector]


@dataclass(frozen=True)
class _Mesh:
    object_id: str
    floor: str | None
    vertices: tuple[Vector, ...]
    triangles: tuple[Triangle, ...]
    props: Mapping[str, Any]

    @property
    def footprints(self) -> list[list[tuple[float, float]]]:
        return [[(p[0], p[1]) for p in face] for face in self.triangles]


def _sub(a: Vector, b: Vector) -> Vector:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _cross(a: Vector, b: Vector) -> Vector:
    return a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]


def _add_scaled(a: Vector, b: Vector, scale: float) -> Vector:
    return a[0] + b[0] * scale, a[1] + b[1] * scale, a[2] + b[2] * scale


def _point(value: Any, scale: float) -> Vector:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in value
        )
    ):
        raise ValueError("coordinates must be three finite numbers")
    result = tuple(float(v) * scale for v in value)
    if not all(math.isfinite(v) for v in result):
        raise ValueError("scaled coordinates must remain finite")
    return result[0], result[1], result[2]


def _properties(row: Mapping[str, Any]) -> Mapping[str, Any]:
    props = row.get("custom_properties", {})
    if not isinstance(props, Mapping):
        raise ValueError("custom_properties must be an object")
    wrapped = props.get("declared_semantic_fields_unreviewed", props)
    if not isinstance(wrapped, Mapping):
        raise ValueError("declared semantic fields must be an object")
    return wrapped


def _declared_floor(row: Mapping[str, Any], props: Mapping[str, Any]) -> str | None:
    labels = {
        value
        for value in (props.get("floor_id"), row.get("declared_floor_label"), _floor(row["object"]))
        if value is not None
    }
    if any(not isinstance(label, str) for label in labels) or len(labels) > 1:
        raise ValueError("conflicting or invalid floor labels")
    return next(iter(labels), None)


def _mesh(row: Mapping[str, Any], scale: float, maximum: int, eps: float) -> _Mesh:
    vertices = row.get("vertices")
    faces = row.get("triangles")
    if not isinstance(vertices, list) or not vertices or not isinstance(faces, list) or not faces:
        raise ValueError("finite world-space vertices and nonempty triangles are required")
    if len(faces) > maximum:
        raise GeometryBudgetExceeded("mesh exceeds configured triangle budget")
    points = tuple(_point(p, scale) for p in vertices)
    triangles = []
    for face in faces:
        if (
            not isinstance(face, (list, tuple))
            or len(face) != 3
            or len(set(face)) != 3
            or any(
                isinstance(index, bool)
                or not isinstance(index, int)
                or index < 0
                or index >= len(points)
                for index in face
            )
        ):
            raise ValueError("triangle indices must be three distinct valid integers")
        triangle = points[face[0]], points[face[1]], points[face[2]]
        normal = _cross(_sub(triangle[1], triangle[0]), _sub(triangle[2], triangle[0]))
        if not all(math.isfinite(value) for value in normal):
            raise ValueError("triangle arithmetic overflows finite geometry")
        if math.hypot(*normal) <= eps:
            raise ValueError("zero-area triangles are not physical surface evidence")
        triangles.append(triangle)
    props = _properties(row)
    referenced = tuple(dict.fromkeys(point for face in triangles for point in face))
    return _Mesh(row["object"], _declared_floor(row, props), referenced, tuple(triangles), props)


def _point_triangle_distance(point: Vector, face: Triangle) -> float:
    """Closest point on a nondegenerate triangle, including its actual boundary."""
    a, b, c = face
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(point, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0 and d2 <= 0:
        return math.dist(point, a)
    bp = _sub(point, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0 and d4 <= d3:
        return math.dist(point, b)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        return math.dist(point, _add_scaled(a, ab, d1 / (d1 - d3)))
    cp = _sub(point, c)
    d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0 and d5 <= d6:
        return math.dist(point, c)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        return math.dist(point, _add_scaled(a, ac, d2 / (d2 - d6)))
    va = d3 * d6 - d5 * d4
    if va <= 0 and d4 - d3 >= 0 and d5 - d6 >= 0:
        return math.dist(point, _add_scaled(b, _sub(c, b), (d4 - d3) / ((d4 - d3) + (d5 - d6))))
    denominator = 1 / (va + vb + vc)
    closest = _add_scaled(_add_scaled(a, ab, vb * denominator), ac, vc * denominator)
    return math.dist(point, closest)


def _edges(face: Triangle) -> tuple[tuple[Vector, Vector], ...]:
    return (face[0], face[1]), (face[1], face[2]), (face[2], face[0])


def _segment_distance(a: Vector, b: Vector, c: Vector, d: Vector, eps: float) -> float:
    u, v, w = _sub(b, a), _sub(d, c), _sub(a, c)
    aa, bb, cc, dd, ee = _dot(u, u), _dot(u, v), _dot(v, v), _dot(u, w), _dot(v, w)
    denominator = aa * cc - bb * bb
    s = max(0.0, min(1.0, (bb * ee - cc * dd) / denominator)) if denominator > eps else 0.0
    t = (bb * s + ee) / cc
    if t < 0:
        t, s = 0.0, max(0.0, min(1.0, -dd / aa))
    elif t > 1:
        t, s = 1.0, max(0.0, min(1.0, (bb - dd) / aa))
    return math.dist(_add_scaled(a, u, s), _add_scaled(c, v, t))


def _segment_intersects_triangle(a: Vector, b: Vector, face: Triangle, eps: float) -> bool:
    normal = _cross(_sub(face[1], face[0]), _sub(face[2], face[0]))
    denominator = _dot(normal, _sub(b, a))
    if abs(denominator) <= eps:
        return False
    fraction = _dot(normal, _sub(face[0], a)) / denominator
    if not 0 <= fraction <= 1:
        return False
    point = _add_scaled(a, _sub(b, a), fraction)
    return _point_triangle_distance(point, face) <= eps


def _triangle_distance(a: Triangle, b: Triangle, eps: float) -> float:
    if any(_segment_intersects_triangle(p, q, b, eps) for p, q in _edges(a)) or any(
        _segment_intersects_triangle(p, q, a, eps) for p, q in _edges(b)
    ):
        return 0.0
    return min(
        *(_point_triangle_distance(p, b) for p in a),
        *(_point_triangle_distance(p, a) for p in b),
        *(_segment_distance(p, q, r, s, eps) for p, q in _edges(a) for r, s in _edges(b)),
    )


def _components(mesh: _Mesh) -> list[list[int]]:
    # Shared full geometric edges join triangles. A single touching vertex is not a landing.
    edge_faces: dict[tuple[Vector, Vector], list[int]] = defaultdict(list)
    for index, face in enumerate(mesh.triangles):
        for a, b in _edges(face):
            edge_faces[(min(a, b), max(a, b))].append(index)
    adjacency: dict[int, set[int]] = defaultdict(set)
    for indices in edge_faces.values():
        for index in indices:
            adjacency[index].update(indices)
    remaining = set(range(len(mesh.triangles)))
    result = []
    while remaining:
        pending = [min(remaining)]
        component: set[int] = set()
        while pending:
            index = pending.pop()
            if index in component:
                continue
            component.add(index)
            pending.extend(sorted(adjacency[index] - component, reverse=True))
        remaining -= component
        result.append(sorted(component))
    return result


def _closed_volume(mesh: _Mesh, eps: float) -> bool:
    edge_counts = Counter(tuple(sorted(edge)) for face in mesh.triangles for edge in _edges(face))
    directions = Counter(edge for face in mesh.triangles for edge in _edges(face))
    # Translate before signed volume measurement to avoid origin-dependent cancellation.
    origin = mesh.vertices[0]
    volume = (
        abs(
            sum(
                _dot(_sub(a, origin), _cross(_sub(b, origin), _sub(c, origin)))
                for a, b, c in mesh.triangles
            )
        )
        / 6
    )
    return (
        all(count == 2 for count in edge_counts.values())
        and all(count == directions[(b, a)] for (a, b), count in directions.items())
        and math.isfinite(volume)
        and volume > eps
    )


def _pair_evidence(left: _Mesh, right: _Mesh, tol: Mapping[str, float | None]) -> dict[str, Any]:
    eps = float(tol["numeric_epsilon"] or 0)
    area = _union_area(_intersections(left.footprints, right.footprints, eps), eps)
    denominator = min(_union_area(left.footprints, eps), _union_area(right.footprints, eps))
    ratio = area / denominator if denominator > eps else None
    left_z = min(p[2] for p in left.vertices), max(p[2] for p in left.vertices)
    right_z = min(p[2] for p in right.vertices), max(p[2] for p in right.vertices)
    gap = max(right_z[0] - left_z[1], left_z[0] - right_z[1], 0.0)
    contact = gap <= float(tol["conflict_vertical_contact_m"] or 0)
    above = ratio is not None and ratio > float(tol["contact_overlap_ratio"] or 0)
    return {
        "other_object_id": right.object_id,
        "footprint_overlap_area_m2": area,
        "smaller_footprint_overlap_ratio": ratio,
        "vertical_interval_gap_m": gap,
        "vertical_contact": contact,
        "above_contact_tolerance": above,
        "status": "HUMAN_REVIEW" if above else "HIGH_CONFIDENCE",
        "physical_collision_certified": False,
        "reason": "FOOTPRINT_OVERLAP" if above else "BELOW_CONFIGURED_FOOTPRINT_CONTACT_TOLERANCE",
    }


def _obstacle_review(
    mesh: _Mesh,
    walkables: list[_Mesh],
    portals: list[_Mesh],
    tol: Mapping[str, float | None],
    approved: Collection[str],
    review_id: str | None,
) -> dict[str, Any]:
    explicit_both = (
        mesh.props.get("blocks_movement") is True
        and mesh.props.get("occludes_visibility") is True
        and mesh.props.get("collision_role") == "BOTH"
    )
    role_status = (
        "APPROVED" if mesh.object_id in approved and review_id and explicit_both else "HUMAN_REVIEW"
    )
    invalid_flags = any(
        mesh.props.get(key) is not None and not isinstance(mesh.props[key], bool)
        for key in ("blocks_movement", "occludes_visibility")
    )
    if invalid_flags:
        role_status = "REJECTED"
    eps = float(tol["numeric_epsilon"] or 0)
    closed = _closed_volume(mesh, eps)
    conflicts: dict[str, list[dict[str, Any]]] = {"walkable": [], "portal": []}
    for kind, others in (("walkable", walkables), ("portal", portals)):
        for other in others:
            if mesh.floor is None or other.floor != mesh.floor:
                continue
            pair = _pair_evidence(mesh, other, tol)
            if pair["footprint_overlap_area_m2"] > eps:
                # For portal protection the denominator is the actual portal aperture footprint.
                if kind == "portal":
                    portal_area = _union_area(other.footprints, eps)
                    pair["portal_overlap_ratio"] = (
                        pair["footprint_overlap_area_m2"] / portal_area
                        if portal_area > eps
                        else None
                    )
                    pair["above_contact_tolerance"] = pair[
                        "portal_overlap_ratio"
                    ] is not None and pair["portal_overlap_ratio"] > float(
                        tol["contact_overlap_ratio"] or 0
                    )
                    pair["status"] = (
                        "HUMAN_REVIEW" if pair["above_contact_tolerance"] else "HIGH_CONFIDENCE"
                    )
                conflicts[kind].append(pair)
    return {
        "object_id": mesh.object_id,
        "floor_id": mesh.floor,
        "semantic_role_status": role_status,
        "role_review_id": review_id if role_status == "APPROVED" else None,
        "blocks_movement": mesh.props.get("blocks_movement")
        if isinstance(mesh.props.get("blocks_movement"), bool)
        else None,
        "occludes_visibility": mesh.props.get("occludes_visibility")
        if isinstance(mesh.props.get("occludes_visibility"), bool)
        else None,
        "physical_geometry_status": "HIGH_CONFIDENCE" if closed else "HUMAN_REVIEW",
        "status": "REJECTED" if invalid_flags else "HUMAN_REVIEW",
        "representation": "CLOSED_TRIANGLE_MESH" if closed else "OPEN_SURFACE_OR_FOOTPRINT_PROXY",
        "closed_volume_evidence": closed,
        "z_extent_m": max(p[2] for p in mesh.vertices) - min(p[2] for p in mesh.vertices),
        "footprint_area_m2": _union_area(mesh.footprints, eps),
        "conflicts": conflicts,
        "physical_collision_certified": False,
        "visibility_occlusion_certified": False,
        "reason": "PHYSICAL_AUTHORITY_REQUIRES_SOURCE_BOUND_REVIEW"
        if closed
        else "NO_HEIGHT_EXTRUSION_OR_CLOSED_VOLUME_AUTHORITY",
    }


def _segment_on_mesh(a: Vector, b: Vector, mesh: _Mesh, eps: float) -> bool:
    intervals = []
    for face in mesh.triangles:
        normal = _cross(_sub(face[1], face[0]), _sub(face[2], face[0]))
        length = math.sqrt(_dot(normal, normal))
        if any(abs(_dot(normal, _sub(p, face[0]))) / length > eps for p in (a, b)):
            continue
        axis = max(range(3), key=lambda i: abs(normal[i]))
        axes = [i for i in range(3) if i != axis]
        polygon = [(p[axes[0]], p[axes[1]]) for p in face]
        start, end = (a[axes[0]], a[axes[1]]), (b[axes[0]], b[axes[1]])
        sign = 1 if _signed_area(polygon) > 0 else -1
        lower, upper = 0.0, 1.0
        for p, q in zip(polygon, polygon[1:] + polygon[:1], strict=True):
            values = [
                sign * ((q[0] - p[0]) * (v[1] - p[1]) - (q[1] - p[1]) * (v[0] - p[0]))
                for v in (start, end)
            ]
            change = values[1] - values[0]
            if abs(change) <= eps:
                if values[0] < -eps:
                    lower, upper = 1.0, 0.0
                    break
            elif change > 0:
                lower = max(lower, -values[0] / change)
            else:
                upper = min(upper, -values[0] / change)
        if lower <= upper:
            intervals.append((max(0.0, lower), min(1.0, upper)))
    covered = 0.0
    for lower, upper in sorted(intervals):
        if lower > covered + eps:
            return False
        covered = max(covered, upper)
    return covered >= 1 - eps


def _ordered_segments(props: Mapping[str, Any]) -> list[list[Vector]] | None:
    points = props.get("path_points_m")
    if points is not None:
        raw = [points]
    elif props.get("path_segment_points_json") is not None:
        raw = json.loads(props["path_segment_points_json"])
    else:
        return None
    if not isinstance(raw, list) or not raw:
        raise ValueError("ordered stair segments must be a nonempty list")
    if any(not isinstance(segment, list) or len(segment) < 2 for segment in raw):
        raise ValueError("each ordered stair segment must have at least two finite points")
    return [[_point(p, 1.0) for p in segment] for segment in raw]


def _stair_review(
    stair_id: str,
    members: list[Mapping[str, Any]],
    walkables: list[_Mesh],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    tol = config["tolerances"]
    eps = float(tol["numeric_epsilon"])
    by_role = {
        role: [r for r in members if _properties(r).get("stair_role") == role]
        for role in ("ENTRY", "PATH", "EXIT")
    }
    checks: dict[str, Any] = {}
    reasons = []
    for role, rows in by_role.items():
        checks[role.lower()] = "HIGH_CONFIDENCE" if len(rows) == 1 else "REJECTED"
        if len(rows) != 1:
            reasons.append("MISSING_OR_DUPLICATE_" + role)
    result: dict[str, Any] = {
        "stair_id": stair_id,
        "object_ids": sorted(row["object"] for row in members),
        "status": "HUMAN_REVIEW",
        "checks": checks,
        "reason_codes": reasons,
        "connectivity_created": False,
        "physical_collision_certified": False,
    }
    if reasons:
        result["status"] = "REJECTED"
        return result
    entry, path, exit_ = (by_role[role][0] for role in ("ENTRY", "PATH", "EXIT"))
    props = _properties(path)
    floor_from, floor_to = props.get("floor_from"), props.get("floor_to")
    result.update(
        floor_from=floor_from if isinstance(floor_from, str) else None,
        floor_to=floor_to if isinstance(floor_to, str) else None,
    )
    floors = config["allowed_floors"]
    consistent = (
        floor_from in floors
        and floor_to in floors
        and floor_from != floor_to
        and _declared_floor(entry, _properties(entry)) == floor_from
        and _declared_floor(exit_, _properties(exit_)) == floor_to
        and all(
            _properties(row).get("floor_from") == floor_from
            and _properties(row).get("floor_to") == floor_to
            for row in members
        )
    )
    checks["floor_transition"] = "HIGH_CONFIDENCE" if consistent else "REJECTED"
    if not consistent:
        reasons.append("CONTRADICTORY_FLOOR_TRANSITION")
        result["status"] = "REJECTED"
        return result
    mesh = _mesh(
        path,
        config["meters_per_blender_unit"],
        config["geometry_complexity"]["maximum_mesh_triangles"],
        eps,
    )
    components = _components(mesh)
    result["path_mesh_components"] = [
        {"component_id": index, "triangle_indices": faces} for index, faces in enumerate(components)
    ]
    checks["path_surface_continuity"] = (
        "HIGH_CONFIDENCE" if len(components) == 1 else "HUMAN_REVIEW"
    )
    gaps = []
    pair_count = 0
    for left in range(len(components)):
        for right in range(left + 1, len(components)):
            pair_count += len(components[left]) * len(components[right])
            if pair_count > config["geometry_complexity"]["maximum_pair_intersections"]:
                raise GeometryBudgetExceeded("stair component distance exceeds pair budget")
            gap = min(
                _triangle_distance(mesh.triangles[a], mesh.triangles[b], eps)
                for a in components[left]
                for b in components[right]
            )
            gaps.append({"component_ids": [left, right], "closest_surface_gap_m": gap})
    result["component_gap_measurements"] = gaps
    if len(components) > 1:
        reasons.append("DISCONNECTED_PATH_SURFACES_NO_LANDING_AUTHORITY")
    scale = config["meters_per_blender_unit"]
    for role, anchor, floor in (("entry", entry, floor_from), ("exit", exit_, floor_to)):
        point = _point(anchor.get("centroid"), scale)
        candidates = sorted(
            (
                (
                    min(_point_triangle_distance(point, face) for face in surface.triangles),
                    surface.object_id,
                )
                for surface in walkables
                if surface.floor == floor
            ),
        )
        distance, object_id = candidates[0] if candidates else (None, None)
        checks[role + "_walkable_contact"] = (
            "HIGH_CONFIDENCE"
            if distance is not None and distance <= tol["stair_join_distance_m"]
            else "HUMAN_REVIEW"
        )
        result[role + "_walkable"] = {
            "nearest_object_id": object_id,
            "distance_m": distance,
            "floor_id": floor,
            "position_m": list(point),
        }
        result[role + "_path_distance_m"] = min(
            _point_triangle_distance(point, face) for face in mesh.triangles
        )
        checks[role + "_path_contact"] = (
            "HIGH_CONFIDENCE"
            if result[role + "_path_distance_m"] <= tol["stair_join_distance_m"]
            else "HUMAN_REVIEW"
        )
        if checks[role + "_path_contact"] == "HUMAN_REVIEW":
            reasons.append(role.upper() + "_NOT_CONNECTED_TO_PATH_SURFACE")
        if checks[role + "_walkable_contact"] == "HUMAN_REVIEW":
            reasons.append(role.upper() + "_NOT_CONNECTED_TO_DECLARED_FLOOR_WALKABLE")
    segments = _ordered_segments(props)
    checks["z_direction"] = "HUMAN_REVIEW"
    checks["ordered_segment_alignment"] = "HUMAN_REVIEW"
    if segments is not None:
        aligned = all(
            _segment_on_mesh(a, b, mesh, eps)
            for segment in segments
            for a, b in zip(segment, segment[1:], strict=False)
        )
        checks["ordered_segment_alignment"] = "HIGH_CONFIDENCE" if aligned else "REJECTED"
        direction = props.get("direction")
        changes = [
            b[2] - a[2] for segment in segments for a, b in zip(segment, segment[1:], strict=False)
        ]
        valid_direction = (
            direction in {"UP", "DOWN"}
            and all(_properties(row).get("direction") == direction for row in members)
            and all(
                change >= -tol["stair_direction_tolerance_m"]
                if direction == "UP"
                else change <= tol["stair_direction_tolerance_m"]
                for change in changes
            )
            and abs(segments[-1][-1][2] - segments[0][0][2]) >= tol["stair_min_rise_m"]
        )
        checks["z_direction"] = "HIGH_CONFIDENCE" if valid_direction else "REJECTED"
        result["ordered_segment_count"] = len(segments)
        result["ordered_segment_join_gaps_m"] = [
            math.dist(a[-1], b[0]) for a, b in zip(segments, segments[1:], strict=False)
        ]
        joined = all(
            gap <= tol["stair_join_distance_m"] for gap in result["ordered_segment_join_gaps_m"]
        )
        checks["ordered_segment_continuity"] = "HIGH_CONFIDENCE" if joined else "HUMAN_REVIEW"
        if not joined:
            reasons.append("ORDERED_SEGMENTS_HAVE_UNSUPPORTED_JOIN_GAP")
        bound = (
            math.dist(segments[0][0], _point(entry.get("centroid"), scale))
            <= tol["stair_join_distance_m"]
            and math.dist(segments[-1][-1], _point(exit_.get("centroid"), scale))
            <= tol["stair_join_distance_m"]
        )
        checks["ordered_traversal_anchor_binding"] = "HIGH_CONFIDENCE" if bound else "REJECTED"
        if not aligned or not valid_direction or not bound:
            result["status"] = "REJECTED"
            reasons.append("ORDERED_SEGMENT_GEOMETRY_OR_DIRECTION_INVALID")
    else:
        reasons.append("NO_ORDERED_STAIR_TRAVERSAL_EVIDENCE")
    # Existing metadata is evidence to review, never an approval of unseen slab or headroom.
    clearance = props.get("measured_clearance_m")
    minimum = tol["minimum_clearance_m"]
    valid_clearance = (
        isinstance(clearance, (int, float))
        and not isinstance(clearance, bool)
        and math.isfinite(clearance)
        and clearance >= 0
    )
    checks["clearance"] = "HUMAN_REVIEW"
    if clearance is not None and not valid_clearance:
        checks["clearance"] = "REJECTED"
        result["status"] = "REJECTED"
        reasons.append("INVALID_DECLARED_CLEARANCE")
    elif valid_clearance and minimum is not None and clearance < minimum:
        checks["clearance"] = "REJECTED"
        result["status"] = "REJECTED"
        reasons.append("DECLARED_CLEARANCE_BELOW_CONFIGURED_MINIMUM")
    result["clearance_evidence"] = {
        "declared_measurement_m": clearance if valid_clearance else None,
        "configured_minimum_m": minimum,
        "source_bound_physical_approval": False,
    }
    checks["slab_opening"] = (
        "REJECTED" if props.get("slab_opening_review") == "FAIL" else "HUMAN_REVIEW"
    )
    if checks["slab_opening"] == "REJECTED":
        result["status"] = "REJECTED"
        reasons.append("DECLARED_SLAB_OPENING_FAILURE")
    reasons.extend(
        ("SLAB_OPENING_PHYSICAL_AUTHORITY_UNRESOLVED", "CLEARANCE_PHYSICAL_AUTHORITY_UNRESOLVED")
    )
    return result


def review_physical_geometry(
    audit: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    approved_obstacle_ids: Collection[str] = (),
    obstacle_review_id: str | None = None,
) -> dict[str, Any]:
    """Measure existing geometry; return deterministic, JSON-compatible review evidence.

    The caller supplies source-bound human role approval separately. No mesh extrusion,
    floor approval, geometry edits, graph edges, or physical clearance certification occurs.
    Malformed object evidence is returned as REJECTED; malformed global config fails fast.
    """
    source_sha = audit.get("source_sha256")
    if not isinstance(source_sha, str) or re.fullmatch("[0-9a-f]{64}", source_sha) is None:
        raise ValueError("source_sha256 must bind review to a concrete source asset")
    rows = audit.get("objects")
    if not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows):
        raise ValueError("audit objects must be a list of objects")
    ids = [row.get("object") for row in rows]
    if any(not isinstance(name, str) or not name for name in ids) or len(ids) != len(set(ids)):
        raise ValueError("audit object IDs must be nonempty and unique")
    if set(approved_obstacle_ids) - set(ids):
        raise ValueError("role approval references absent source objects")
    if any(not name.startswith("OBSTACLE_") for name in approved_obstacle_ids):
        raise ValueError("obstacle role approval cannot authorize another semantic class")
    if approved_obstacle_ids and (
        not isinstance(obstacle_review_id, str) or not obstacle_review_id.strip()
    ):
        raise ValueError("approved obstacle roles require an explicit human review ID")
    scale = config.get("meters_per_blender_unit")
    if (
        isinstance(scale, bool)
        or not isinstance(scale, (int, float))
        or not math.isfinite(scale)
        or scale <= 0
    ):
        raise ValueError("meters_per_blender_unit must be finite and positive")
    tolerances = config.get("tolerances", {})
    required = (
        "numeric_epsilon",
        "contact_overlap_ratio",
        "conflict_vertical_contact_m",
        "stair_join_distance_m",
        "stair_min_rise_m",
        "stair_direction_tolerance_m",
        "minimum_clearance_m",
    )
    for key in required:
        value = tolerances.get(key)
        if key == "minimum_clearance_m" and value is None and key in tolerances:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError(f"invalid physical review tolerance: {key}")
    if tolerances["numeric_epsilon"] <= 0 or tolerances["contact_overlap_ratio"] > 1:
        raise ValueError("numeric epsilon must be positive and contact ratio must be <= 1")
    budgets = config.get("geometry_complexity", {})
    for key in ("maximum_mesh_triangles", "maximum_union_polygons", "maximum_pair_intersections"):
        if (
            isinstance(budgets.get(key), bool)
            or not isinstance(budgets.get(key), int)
            or budgets[key] <= 0
        ):
            raise ValueError("physical review geometry budgets must be positive integers")
    allowed = config.get("allowed_floors")
    if not isinstance(allowed, list) or any(
        not isinstance(floor, str) or not floor for floor in allowed
    ):
        raise ValueError("allowed_floors must be a list of floor IDs")
    obstacles: list[_Mesh] = []
    walkables: list[_Mesh] = []
    portals: list[_Mesh] = []
    failures = []
    unmeasured = []
    stairs: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    token = _GEOMETRY_BUDGET.set(dict(budgets))
    try:
        for row in sorted(rows, key=lambda item: item["object"]):
            name = row["object"]
            kind = name.split("_", 1)[0]
            if kind == "WALK":
                declared = _properties(row)
                if (
                    declared.get("semantic_class") == "WALKABLE"
                    and isinstance(declared.get("semantic_review_id"), str)
                    and declared["semantic_review_id"].strip()
                ):
                    kind = "WALKABLE"
            if kind not in {"WALKABLE", "OBSTACLE", "PORTAL", "STAIR"}:
                continue
            try:
                props = _properties(row)
                if props.get("semantic_class") not in {None, kind}:
                    raise ValueError("semantic class conflicts with explicit object prefix")
                if kind == "STAIR":
                    stair_id = props.get("stair_id")
                    if not isinstance(stair_id, str) or not stair_id:
                        raise ValueError("explicit stair_id is required")
                    stairs[stair_id].append(row)
                else:
                    mesh = _mesh(
                        row, scale, budgets["maximum_mesh_triangles"], tolerances["numeric_epsilon"]
                    )
                    if mesh.floor not in allowed:
                        raise ValueError("geometry requires a configured explicit floor")
                    {"OBSTACLE": obstacles, "WALKABLE": walkables, "PORTAL": portals}[kind].append(
                        mesh
                    )
            except GeometryBudgetExceeded as error:
                unmeasured.append(
                    {"object_id": name, "status": "HUMAN_REVIEW", "reason": str(error)}
                )
            except (ValueError, TypeError, KeyError) as error:
                failures.append({"object_id": name, "status": "REJECTED", "reason": str(error)})
        obstacle_results = []
        for mesh in obstacles:
            try:
                obstacle_results.append(
                    _obstacle_review(
                        mesh,
                        walkables,
                        portals,
                        tolerances,
                        approved_obstacle_ids,
                        obstacle_review_id,
                    )
                )
            except GeometryBudgetExceeded as error:
                obstacle_results.append(
                    {
                        "object_id": mesh.object_id,
                        "status": "HUMAN_REVIEW",
                        "reason": str(error),
                        "physical_collision_certified": False,
                    }
                )
        stair_results = []
        for stair_id, members in sorted(stairs.items()):
            try:
                stair_results.append(_stair_review(stair_id, members, walkables, config))
            except GeometryBudgetExceeded as error:
                stair_results.append(
                    {
                        "stair_id": stair_id,
                        "status": "HUMAN_REVIEW",
                        "reason": str(error),
                        "connectivity_created": False,
                    }
                )
            except (ValueError, TypeError, KeyError) as error:
                stair_results.append(
                    {
                        "stair_id": stair_id,
                        "status": "REJECTED",
                        "reason": str(error),
                        "connectivity_created": False,
                    }
                )
        return {
            "schema_version": "geometry-physical-review-v1",
            "source_sha256": source_sha,
            "authority": "SOURCE_BOUND_MEASUREMENTS_NOT_PHYSICAL_CERTIFICATION",
            "obstacle_reviews": obstacle_results,
            "stair_reviews": stair_results,
            "rejected_geometry": failures,
            "unmeasured_geometry": unmeasured,
            "measured_geometry_counts": {
                "walkable_meshes": len(walkables),
                "obstacle_meshes": len(obstacles),
                "portal_meshes": len(portals),
                "stair_groups": len(stairs),
            },
            "physical_authority_status": "PROVISIONAL",
            "read_only": True,
            "floor_authority_modified": False,
            "inference_connectivity_created": False,
        }
    finally:
        _GEOMETRY_BUDGET.reset(token)
