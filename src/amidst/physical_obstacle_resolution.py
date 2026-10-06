"""Read-only obstacle/portal blocker diagnosis from source-bound exact geometry.

Annotation-depth overlap is distinct from a blocked declared center plane. Neither
measurement approves a physical aperture, collider volume, or pedestrian clearance.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from typing import Any

from amidst.geometry_physical_review import _Mesh, _mesh, review_physical_geometry
from amidst.scene_validation import (
    _GEOMETRY_BUDGET,
    GeometryBudgetExceeded,
    _distance,
    _intersections,
    _signed_area,
    _union_area,
)

Interval = tuple[float, float]


def content_sha256(document: Mapping[str, Any]) -> str:
    """Canonical evidence digest; the expected digest must come from the caller."""
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _bounds(mesh: _Mesh) -> dict[str, list[float]]:
    return {
        "minimum": [min(point[axis] for point in mesh.vertices) for axis in range(3)],
        "maximum": [max(point[axis] for point in mesh.vertices) for axis in range(3)],
    }


def _merge(intervals: list[Interval], epsilon: float) -> list[Interval]:
    result: list[Interval] = []
    for lower, upper in sorted(intervals):
        if upper - lower <= epsilon:
            continue
        if result and lower <= result[-1][1] + epsilon:
            result[-1] = result[-1][0], max(result[-1][1], upper)
        else:
            result.append((lower, upper))
    return result


def _line_intervals(
    mesh: _Mesh, start: tuple[float, float], end: tuple[float, float], epsilon: float
) -> list[Interval]:
    intervals: list[Interval] = []
    for triangle in mesh.footprints:
        area = _signed_area(triangle)
        if abs(area) <= epsilon:
            continue
        sign = 1.0 if area > 0 else -1.0
        lower, upper = 0.0, 1.0
        for a, b in zip(triangle, triangle[1:] + triangle[:1], strict=True):
            first, last = [
                sign * ((b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]))
                for point in (start, end)
            ]
            change = last - first
            if abs(change) <= epsilon:
                if first < -epsilon:
                    lower, upper = 1.0, 0.0
                    break
                continue
            bound = -first / change
            if change > 0:
                lower = max(lower, bound)
            else:
                upper = min(upper, bound)
        if upper - lower > epsilon:
            intervals.append((max(0.0, lower), min(1.0, upper)))
    return _merge(intervals, epsilon)


def _center_plane(obstacle: _Mesh, portal: _Mesh, epsilon: float) -> dict[str, Any]:
    result: dict[str, Any] = {
        "basis": "DECLARED_ANNOTATION_NORMAL_NOT_PHYSICAL_APERTURE_APPROVAL",
        "physical_aperture_certified": False,
        "status": "UNMEASURED",
    }
    normal = portal.props.get("portal_normal")
    if normal is None:
        return {**result, "reason": "PORTAL_NORMAL_NOT_DECLARED"}
    if (
        not isinstance(normal, (list, tuple))
        or len(normal) != 3
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in normal
        )
    ):
        return {**result, "reason": "PORTAL_NORMAL_INVALID"}
    horizontal = math.hypot(normal[0], normal[1])
    if horizontal <= epsilon or abs(normal[2]) > epsilon:
        return {**result, "reason": "PORTAL_NORMAL_NOT_HORIZONTAL"}
    tangent = (-normal[1] / horizontal, normal[0] / horizontal)
    box = _bounds(portal)
    center = [(box["minimum"][axis] + box["maximum"][axis]) / 2 for axis in range(3)]
    offsets = [
        sum((point[axis] - center[axis]) * tangent[axis] for axis in range(2))
        for point in portal.vertices
    ]
    lower, upper = min(offsets), max(offsets)
    length = upper - lower
    if length <= epsilon:
        return {**result, "reason": "PORTAL_HAS_NO_TRANSVERSE_EXTENT"}
    start, end = (
        tuple(center[axis] + offset * tangent[axis] for axis in range(2))
        for offset in (lower, upper)
    )
    portal_intervals = _line_intervals(portal, (start[0], start[1]), (end[0], end[1]), epsilon)
    obstacle_intervals = _line_intervals(obstacle, (start[0], start[1]), (end[0], end[1]), epsilon)
    blocked = _merge(
        [(max(a, c), min(b, d)) for a, b in portal_intervals for c, d in obstacle_intervals],
        epsilon,
    )
    width = sum(b - a for a, b in portal_intervals) * length
    blocked_width = sum(b - a for a, b in blocked) * length
    if width <= epsilon:
        return {**result, "reason": "PORTAL_CENTER_SECTION_EMPTY"}
    return {
        **result,
        "status": "MEASURED_ANNOTATION_ONLY",
        "center_m": center,
        "normal": [normal[0] / horizontal, normal[1] / horizontal, 0.0],
        "portal_intervals_m": [
            [lower + a * length, lower + b * length] for a, b in portal_intervals
        ],
        "blocked_intervals_m": [[lower + a * length, lower + b * length] for a, b in blocked],
        "cross_section_width_m": width,
        "blocked_width_m": blocked_width,
        "blocked_ratio": blocked_width / width,
        "scale_note": (
            "Configured unit conversion is preserved; physical scale approval is separate."
        ),
    }


def _baseline_pairs(authority: Mapping[str, Any]) -> list[tuple[str, str]]:
    physical = authority.get("physical_review")
    if not isinstance(physical, Mapping) or not isinstance(physical.get("obstacle_reviews"), list):
        raise ValueError("baseline authority requires structured obstacle reviews")
    pairs: list[tuple[str, str]] = []
    for row in physical["obstacle_reviews"]:
        if not isinstance(row, Mapping) or not isinstance(row.get("object_id"), str):
            raise ValueError("baseline obstacle review must name a source object")
        conflicts = row.get("conflicts")
        if not isinstance(conflicts, Mapping) or not isinstance(conflicts.get("portal"), list):
            raise ValueError("baseline obstacle review requires structured portal conflicts")
        for conflict in conflicts["portal"]:
            if not isinstance(conflict, Mapping) or not isinstance(
                conflict.get("other_object_id"), str
            ):
                raise ValueError("baseline portal conflict must name a source object")
            pairs.append((row["object_id"], conflict["other_object_id"]))
    if len(pairs) != len(set(pairs)):
        raise ValueError("baseline obstacle/portal conflict pairs must be unique")
    return sorted(pairs)


def _source_context(
    evidence: Mapping[str, Any] | None,
    source_sha256: str,
    audit_digest: str,
    config_digest: str,
    scale: float,
) -> dict[str, dict[str, Any]]:
    if evidence is None:
        return {}
    if (
        evidence.get("schema_version") != "physical-source-mesh-evidence-v1"
        or evidence.get("source_sha256") != source_sha256
        or evidence.get("audit_content_sha256") != audit_digest
        or evidence.get("config_content_sha256") != config_digest
        or evidence.get("source_preserved") is not True
        or evidence.get("saved") is not False
        or evidence.get("rendered") is not False
    ):
        raise ValueError("source context differs from source/audit/config read-only bindings")
    policy = evidence.get("policy")
    if not isinstance(policy, Mapping) or any(
        policy.get(key) is not required
        for key, required in {
            "gt_used": False,
            "roles_inferred_from_names": False,
            "region_complete_is_selection_complete_only": True,
            "missing_triangles_certify_clearance": False,
        }.items()
    ):
        raise ValueError("unclassified source context cannot certify roles or empty space")
    regions = evidence.get("regions")
    if not isinstance(regions, list) or any(not isinstance(row, Mapping) for row in regions):
        raise ValueError("source context regions must be structured objects")
    result: dict[str, dict[str, Any]] = {}
    for region in regions:
        if region.get("kind") != "OBSTACLE_CONTEXT":
            continue
        name = region.get("region_id")
        patches = region.get("patches")
        if (
            not isinstance(name, str)
            or name in result
            or not isinstance(region.get("complete"), bool)
            or not isinstance(patches, list)
        ):
            raise ValueError(
                "obstacle source contexts require unique IDs and selection completeness"
            )
        sources = []
        for patch in patches:
            if (
                not isinstance(patch, Mapping)
                or patch.get("semantic_role") != "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY"
                or not isinstance(patch.get("source_object_id"), str)
                or patch.get("geometry_sha256")
                != content_sha256(
                    {key: value for key, value in patch.items() if key != "geometry_sha256"}
                )
            ):
                raise ValueError(
                    "source patch must retain its unclassified role and geometry binding"
                )
            vertices, triangles = patch.get("vertices"), patch.get("triangles")
            face_ids = patch.get("source_face_indices")
            triangle_faces = patch.get("triangle_source_face_indices")
            if (
                not isinstance(vertices, list)
                or not vertices
                or not isinstance(triangles, list)
                or not isinstance(face_ids, list)
                or any(
                    isinstance(index, bool) or not isinstance(index, int) or index < 0
                    for index in face_ids
                )
                or len(set(face_ids)) != len(face_ids)
                or not isinstance(triangle_faces, list)
                or len(triangle_faces) != len(triangles)
                or any(
                    isinstance(index, bool) or not isinstance(index, int) or index not in face_ids
                    for index in triangle_faces
                )
            ):
                raise ValueError("source patch requires finite vertices and triangle indices")
            if any(
                not isinstance(point, (list, tuple))
                or len(point) != 3
                or any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    for value in point
                )
                for point in vertices
            ) or any(
                not isinstance(face, (list, tuple))
                or len(face) != 3
                or len(set(face)) != 3
                or any(
                    isinstance(index, bool)
                    or not isinstance(index, int)
                    or index < 0
                    or index >= len(vertices)
                    for index in face
                )
                for face in triangles
            ):
                raise ValueError("source patch has invalid finite geometry or triangle indices")
            referenced = {index for face in triangles for index in face}
            if not referenced:
                raise ValueError("source context patch must contain selected triangles")
            scaled = [[value * scale for value in vertices[index]] for index in referenced]
            if any(not math.isfinite(value) for point in scaled for value in point):
                raise ValueError("source context scaled geometry must remain finite")
            sources.append(
                {
                    "source_object_id": patch["source_object_id"],
                    "source_face_count": len(face_ids),
                    "selected_triangle_count": len(triangles),
                    "bounds_m": {
                        "minimum": [
                            min(vertices[index][axis] for index in referenced) * scale
                            for axis in range(3)
                        ],
                        "maximum": [
                            max(vertices[index][axis] for index in referenced) * scale
                            for axis in range(3)
                        ],
                    },
                    "semantic_role": "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY",
                    "geometry_sha256": patch["geometry_sha256"],
                }
            )
        total = sum(row["selected_triangle_count"] for row in sources)
        if (
            isinstance(region.get("triangle_count"), bool)
            or not isinstance(region.get("triangle_count"), int)
            or total != region["triangle_count"]
        ):
            raise ValueError("source context triangle count differs from selected geometry")
        result[name] = {
            "selection_complete": region["complete"],
            "source_object_count": len(sources),
            "selected_triangle_count": total,
            "sources": sorted(sources, key=lambda row: row["source_object_id"]),
            "collider_ownership_certified": False,
            "empty_space_certified": False,
            "physical_status": "HUMAN_REVIEW",
        }
    return result


def review_obstacle_portal_conflicts(
    audit: Mapping[str, Any],
    baseline_authority: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    expected_source_sha256: str,
    expected_audit_content_sha256: str | None = None,
    source_mesh_evidence: Mapping[str, Any] | None = None,
    source_mesh_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Re-measure each baseline conflict without changing any scene annotation.

    The optional canonical audit binding should be supplied by a source-verified
    adapter/manifest. No diagnostic result is a physical approval or a scene repair.
    """
    if (
        not isinstance(expected_source_sha256, str)
        or re.fullmatch("[0-9a-f]{64}", expected_source_sha256) is None
        or any(
            document.get("source_sha256") != expected_source_sha256
            for document in (audit, baseline_authority)
        )
    ):
        raise ValueError("obstacle resolution evidence differs from expected source SHA-256")
    physical = baseline_authority.get("physical_review")
    if not isinstance(physical, Mapping) or physical.get("source_sha256") != expected_source_sha256:
        raise ValueError("baseline physical review differs from expected source SHA-256")
    audit_digest = content_sha256(audit)
    if expected_audit_content_sha256 is not None and audit_digest != expected_audit_content_sha256:
        raise ValueError("audit content differs from the source-verified geometry binding")
    # Reuse the existing global config and mesh validation; no new research tolerance.
    remeasurement = review_physical_geometry(audit, config)
    pairs = _baseline_pairs(baseline_authority)
    rows = {row["object"]: row for row in audit["objects"]}
    missing = sorted({name for pair in pairs for name in pair} - rows.keys())
    if missing:
        raise ValueError(f"baseline conflicts reference absent source objects: {missing}")
    scale = float(config["meters_per_blender_unit"])
    if (source_mesh_evidence is None) != (source_mesh_config is None):
        raise ValueError("source mesh evidence and its selection config must be supplied together")
    if (
        source_mesh_config is not None
        and source_mesh_config.get("source_sha256") != expected_source_sha256
    ):
        raise ValueError("source mesh selection config differs from expected source SHA-256")
    contexts = _source_context(
        source_mesh_evidence,
        expected_source_sha256,
        audit_digest,
        content_sha256(source_mesh_config) if source_mesh_config is not None else "",
        scale,
    )
    tolerance = config["tolerances"]
    epsilon = float(tolerance["numeric_epsilon"])
    near = tolerance.get("portal_near_distance_m")
    if (
        isinstance(near, bool)
        or not isinstance(near, (int, float))
        or not math.isfinite(near)
        or near < 0
    ):
        raise ValueError("portal_near_distance_m must be finite and nonnegative")
    maximum = config["geometry_complexity"]["maximum_mesh_triangles"]
    records: list[dict[str, Any]] = []
    token = _GEOMETRY_BUDGET.set(dict(config["geometry_complexity"]))
    try:
        for obstacle_id, portal_id in pairs:
            record: dict[str, Any] = {
                "obstacle_id": obstacle_id,
                "portal_id": portal_id,
                "physical_status": "HUMAN_REVIEW",
                "physical_collision_certified": False,
                "repair_applied": False,
                "source_geometry_context": contexts.get(obstacle_id),
                "remaining_decision": (
                    "Bind actual physical source meshes, aperture, collider volume and body "
                    "clearance. Annotation overlap alone does not authorize trimming or movement."
                ),
            }
            try:
                if not obstacle_id.startswith("OBSTACLE_") or not portal_id.startswith("PORTAL_"):
                    raise ValueError("baseline conflicts must bind OBSTACLE and PORTAL roles")
                obstacle = _mesh(rows[obstacle_id], scale, maximum, epsilon)
                portal = _mesh(rows[portal_id], scale, maximum, epsilon)
                for mesh, role in ((obstacle, "OBSTACLE"), (portal, "PORTAL")):
                    if mesh.props.get("semantic_class") not in {None, role}:
                        raise ValueError("conflicting declared semantic ownership")
                overlap = _union_area(
                    _intersections(obstacle.footprints, portal.footprints, epsilon), epsilon
                )
                portal_area = _union_area(portal.footprints, epsilon)
                ob, pb = _bounds(obstacle), _bounds(portal)
                vertical_gap = max(
                    0.0,
                    ob["minimum"][2] - pb["maximum"][2],
                    pb["minimum"][2] - ob["maximum"][2],
                )
                area_context = []
                for name, row in sorted(rows.items()):
                    if not name.startswith("AREA_") or not row.get("triangles"):
                        continue
                    area = _mesh(row, scale, maximum, epsilon)
                    ab = _bounds(area)
                    if (
                        any(
                            pb["minimum"][axis] > ab["maximum"][axis] + near
                            or pb["maximum"][axis] < ab["minimum"][axis] - near
                            for axis in range(3)
                        )
                        or _distance(portal.footprints, area.footprints, epsilon) > near
                    ):
                        continue
                    size = _union_area(area.footprints, epsilon)
                    if size <= epsilon:
                        continue
                    area_context.append(
                        {
                            "object_id": name,
                            "floor_id": area.floor,
                            "bounds_m": ab,
                            "obstacle_coverage_ratio": _union_area(
                                _intersections(obstacle.footprints, area.footprints, epsilon),
                                epsilon,
                            )
                            / size,
                        }
                    )
                plane = _center_plane(obstacle, portal, epsilon)
                classification = "UNRESOLVED_BLOCKER_FOOTPRINT_OR_PORTAL_PLACEMENT"
                if plane.get("status") == "MEASURED_ANNOTATION_ONLY" and (
                    plane["blocked_width_m"] <= epsilon
                ):
                    classification = "SEMANTIC_ANNOTATION_DEPTH_OVERLAP_CLEAR_DECLARED_CENTER_PLANE"
                record.update(
                    {
                        "floor_id": obstacle.floor,
                        "portal_floor_id": portal.floor,
                        "areas": area_context,
                        "obstacle_bounds_m": ob,
                        "portal_bounds_m": pb,
                        "overlap_area_m2": overlap,
                        "portal_overlap_ratio": overlap / portal_area
                        if portal_area > epsilon
                        else None,
                        "vertical_interval_gap_m": vertical_gap,
                        "center_plane_measurement": plane,
                        "classification": classification,
                        "revalidation_status": (
                            "MEASURED"
                            if overlap > epsilon
                            and vertical_gap <= tolerance["conflict_vertical_contact_m"]
                            else "STALE_BASELINE_CONFLICT"
                        ),
                    }
                )
            except (ValueError, GeometryBudgetExceeded) as error:
                record.update(
                    {
                        "revalidation_status": "REJECTED_EVIDENCE",
                        "classification": "UNMEASURED_INVALID_SOURCE_GEOMETRY",
                        "error": str(error),
                    }
                )
            records.append(record)
    finally:
        _GEOMETRY_BUDGET.reset(token)
    return {
        "schema_version": "obstacle-portal-resolution-v1",
        "source_sha256": expected_source_sha256,
        "scope": "SOURCE_BOUND_DIAGNOSTIC_NOT_PHYSICAL_CERTIFICATION",
        "input_bindings": {
            "audit_content_sha256": audit_digest,
            "baseline_authority_content_sha256": content_sha256(baseline_authority),
            "config_content_sha256": content_sha256(config),
            "source_mesh_evidence_content_sha256": (
                content_sha256(source_mesh_evidence) if source_mesh_evidence is not None else None
            ),
            "source_mesh_config_content_sha256": (
                content_sha256(source_mesh_config) if source_mesh_config is not None else None
            ),
        },
        "pairs": records,
        "pair_count": len(records),
        "repair_count": 0,
        "human_review_count": len(records),
        "physical_approval_count": 0,
        "scene_geometry_changed": False,
        "volume_authority": "HUMAN_REVIEW",
        "obstacle_volume_evidence": [
            {
                "object_id": row["object_id"],
                "closed_volume_evidence": row["closed_volume_evidence"],
                "representation": row["representation"],
                "z_extent_m": row["z_extent_m"],
                "physical_collision_certified": False,
                "source_geometry_context": contexts.get(row["object_id"]),
            }
            for row in remeasurement["obstacle_reviews"]
        ],
        "rejected_geometry": remeasurement["rejected_geometry"],
    }
