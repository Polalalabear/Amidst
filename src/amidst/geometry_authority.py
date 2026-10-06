"""Deterministic, source-bound geometry authority review, separate from inference.

Legacy seeds are evidence to recheck, never unconditional approvals. Actual triangles
preserve openings; continuous WALKABLE intervals replace sampled intrusion tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from amidst.geometry_physical_review import review_physical_geometry
from amidst.scene_geometry import (
    Authority,
    GeometryRole,
    GeometrySurface,
    ReadOnlySceneGeometryProvider,
    SceneGeometrySnapshot,
    promoted_wall_portal_conflicts,
)
from amidst.scene_validation import (
    GeometryBudgetExceeded,
    _intersections,
    _signed_area,
    _union_area,
)

WEAK_SUPPORT = "NO_THICKNESS_SUPPORT_THIN_PANEL_OR_DECOR_REVIEW"
SEED_STATUS = "AUTO_CONFIRMED_WALL"
EPS = 1e-9
Interval = tuple[float, float]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def value_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def validate_extraction_policy(document: dict[str, Any]) -> None:
    """The extraction-v1 ratios are fixed, even when consuming a claimed seed."""
    floors = document["floor_planes"]
    if (
        not isinstance(floors, dict)
        or len(floors) < 2
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
            for value in floors.values()
        )
    ):
        raise ValueError("finite distinct floor planes are required")
    levels = sorted(floors.values())
    spacing = min(b - a for a, b in zip(levels, levels[1:], strict=False))
    if spacing <= 0:
        raise ValueError("distinct floor planes are required")
    expected = {
        "storey_spacing": spacing,
        "vertical_max_abs_nz": math.sin(math.radians(5)),
        "continuity_min_normal_dot": math.cos(math.radians(1)),
        **{
            name: spacing * ratio
            for name, ratio in {
                "weld_epsilon": 1e-5,
                "plane_epsilon": 1e-4,
                "candidate_min_height": 0.2,
                "candidate_min_extent": 0.12,
                "auto_min_height": 0.75,
                "auto_max_height": 1.15,
                "auto_min_extent": 0.75,
                "broad_sheet_min_extent": 2.0,
                "floor_contact_tolerance": 0.07,
                "near_distance": 0.25,
                "thickness_min": 0.015,
                "thickness_max": 0.2,
                "section_above_floor": 0.15,
                "walk_probe_offset": 0.005,
                "portal_padding": 0.002,
            }.items()
        },
    }
    params = document["parameters"]
    if params.keys() != expected.keys() or any(
        not isinstance(params[name], (int, float))
        or isinstance(params[name], bool)
        or not math.isfinite(params[name])
        or not math.isclose(params[name], value, abs_tol=1e-12, rel_tol=1e-12)
        for name, value in expected.items()
    ):
        raise ValueError("extraction-v1 threshold policy changed; original ratios are required")


def actual_bounds(vertices: Any) -> dict[str, list[float]]:
    return {
        "minimum": [min(p[i] for p in vertices) for i in range(3)],
        "maximum": [max(p[i] for p in vertices) for i in range(3)],
    }


def bounds_distance_xy(first: dict[str, Any], second: dict[str, Any]) -> float:
    return math.hypot(
        *[
            max(
                0.0,
                first["minimum"][i] - second["maximum"][i],
                second["minimum"][i] - first["maximum"][i],
            )
            for i in range(2)
        ]
    )


def validate_patch_coordinates(
    patch: dict[str, Any], surface: GeometrySurface, document: dict[str, Any]
) -> None:
    box = actual_bounds(surface.vertices)
    if any(
        not math.isclose(box[key][i], patch["bounds"][key][i], abs_tol=1e-7, rel_tol=1e-12)
        for key in ("minimum", "maximum")
        for i in range(3)
    ):
        raise ValueError("candidate bounds differ from exact source triangles")
    normal, tangent = patch["normal"], patch["tangent"]
    if (
        len(normal) != 3
        or len(tangent) != 3
        or not all(math.isfinite(v) for v in normal + tangent)
        or not math.isclose(math.hypot(*normal), 1.0, abs_tol=1e-7, rel_tol=0)
    ):
        raise ValueError("candidate normal/tangent must be finite orthonormal vectors")
    horizontal = math.hypot(normal[0], normal[1])
    if horizontal <= EPS or any(
        not math.isclose(a, b, abs_tol=1e-7, rel_tol=0)
        for a, b in zip(tangent, [-normal[1] / horizontal, normal[0] / horizontal, 0], strict=True)
    ):
        raise ValueError("candidate tangent differs from the canonical horizontal tangent")
    planes = document["floor_planes"]
    floor = min(sorted(planes), key=lambda f: abs(box["minimum"][2] - planes[f]))
    if (
        patch["floor"] != floor
        or not math.isclose(
            patch["floor_contact_offset"], abs(box["minimum"][2] - planes[floor]), abs_tol=1e-7
        )
        or not math.isclose(
            patch["walkable_relation"]["section_z"],
            planes[floor] + document["parameters"]["section_above_floor"],
            abs_tol=1e-7,
        )
    ):
        raise ValueError(
            "candidate floor/offset/section differs from exact geometry and floor planes"
        )
    ts = [sum(p[i] * tangent[i] for i in range(3)) for p in surface.vertices]
    if any(
        not math.isclose(a, b, abs_tol=1e-7, rel_tol=1e-12)
        for a, b in zip(patch["tangent_interval"], [min(ts), max(ts)], strict=True)
    ):
        raise ValueError("candidate tangent interval differs from exact source triangles")


def merge_intervals(values: list[Interval], epsilon: float = EPS) -> list[Interval]:
    result: list[Interval] = []
    for low, high in sorted(values):
        if high - low <= epsilon:
            continue
        if result and low <= result[-1][1] + epsilon:
            result[-1] = result[-1][0], max(high, result[-1][1])
        else:
            result.append((low, high))
    return result


def welded_component_count(surface: GeometrySurface, weld_epsilon: float) -> int:
    """Recheck the extractor's edge continuity without filling missing surfaces."""
    if not math.isfinite(weld_epsilon) or weld_epsilon <= 0:
        raise ValueError("weld epsilon must be finite and positive")
    keys = [tuple(round(value / weld_epsilon) for value in point) for point in surface.vertices]
    parents = list(range(len(surface.triangles)))

    def find(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    edges: dict[Any, int] = {}
    for index, triangle in enumerate(surface.triangles):
        points = [keys[i] for i in triangle]
        for a, b in zip(points, points[1:] + points[:1], strict=True):
            if a == b:
                continue
            edge = tuple(sorted((a, b)))
            if edge in edges:
                parents[find(index)] = find(edges[edge])
            else:
                edges[edge] = index
    return len({find(index) for index in range(len(surface.triangles))})


def intersect_intervals(first: list[Interval], second: list[Interval]) -> list[Interval]:
    return merge_intervals(
        [(max(a, c), min(b, d)) for a, b in first for c, d in second if min(b, d) - max(a, c) > EPS]
    )


def section_intervals(
    surface: GeometrySurface,
    z: float,
    tangent: list[float],
) -> list[Interval]:
    """Intersect actual evaluated triangles, never a concave N-gon's crossing envelope."""
    intervals = []
    for face in surface.triangles:
        triangle = [surface.vertices[index] for index in face]
        points = []
        for a, b in zip(triangle, triangle[1:] + triangle[:1], strict=True):
            if abs(a[2] - z) <= EPS:
                points.append(a)
            if (a[2] < z < b[2]) or (b[2] < z < a[2]):
                weight = (z - a[2]) / (b[2] - a[2])
                points.append(
                    (
                        a[0] + weight * (b[0] - a[0]),
                        a[1] + weight * (b[1] - a[1]),
                        a[2] + weight * (b[2] - a[2]),
                    )
                )
        values = [sum(p[i] * tangent[i] for i in range(3)) for p in points]
        if len(values) >= 2:
            intervals.append((min(values), max(values)))
    return merge_intervals(intervals)


def line_triangle_interval(
    start: tuple[float, float],
    end: tuple[float, float],
    triangle: list[tuple[float, float]],
) -> Interval | None:
    """Continuous parameter interval inside a nondegenerate XY triangle."""
    area = _signed_area(triangle)
    if abs(area) <= EPS:
        return None
    sign = 1.0 if area > 0 else -1.0
    low, high = 0.0, 1.0
    for a, b in zip(triangle, triangle[1:] + triangle[:1], strict=True):
        first, last = [
            sign * ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]))
            for p in (start, end)
        ]
        delta = last - first
        if abs(delta) <= EPS:
            if first < -EPS:
                return None
            continue
        boundary = -first / delta
        if delta > 0:
            low = max(low, boundary)
        else:
            high = min(high, boundary)
        if low > high + EPS:
            return None
    return (max(0.0, low), min(1.0, high)) if high - low > EPS else None


def exact_walkable_intrusions(
    patch: dict[str, Any],
    surface: GeometrySurface,
    walkables: dict[str, GeometrySurface],
    params: dict[str, float],
) -> list[dict[str, Any]]:
    normal, tangent = patch["normal"], patch["tangent"]
    z = patch["walkable_relation"]["section_z"]
    sections = section_intervals(surface, z, tangent)
    denominator = normal[0] ** 2 + normal[1] ** 2
    origin = [normal[i] * (patch["plane"] - normal[2] * z) / denominator for i in range(2)]
    result = []
    # Claimed legacy nearby IDs are diagnostics, never a filter for physical rejection.
    for identity, walkable in sorted(walkables.items()):
        if (
            patch["floor"] not in walkable.floor_ids
            or bounds_distance_xy(actual_bounds(surface.vertices), actual_bounds(walkable.vertices))
            > params["near_distance"]
        ):
            continue
        footprints = [
            [(walkable.vertices[i][0], walkable.vertices[i][1]) for i in face]
            for face in walkable.triangles
        ]
        lengths: list[float] = []
        for lower, upper in sections:
            sides: list[list[Interval]] = []
            for sign in (-1, 1):
                start = tuple(
                    origin[i] + tangent[i] * lower + sign * normal[i] * params["walk_probe_offset"]
                    for i in range(2)
                )
                end = tuple(
                    origin[i] + tangent[i] * upper + sign * normal[i] * params["walk_probe_offset"]
                    for i in range(2)
                )
                sides.append(
                    merge_intervals(
                        [
                            interval
                            for triangle in footprints
                            if (
                                interval := line_triangle_interval(
                                    (start[0], start[1]),
                                    (end[0], end[1]),
                                    triangle,
                                )
                            )
                            is not None
                        ]
                    )
                )
            lengths.extend(
                (b - a) * (upper - lower) for a, b in intersect_intervals(sides[0], sides[1])
            )
        length = sum(lengths)
        if length > params["weld_epsilon"]:
            result.append({"walkable_id": identity, "continuous_intrusion_length": length})
    return sorted(result, key=lambda row: row["walkable_id"])


def projected_faces(
    surface: GeometrySurface,
    tangent: list[float],
) -> list[list[tuple[float, float]]]:
    faces = [
        [
            (sum(surface.vertices[i][j] * tangent[j] for j in range(3)), surface.vertices[i][2])
            for i in triangle
        ]
        for triangle in surface.triangles
    ]
    return list(
        {tuple(sorted(face)): face for face in faces if abs(_signed_area(face)) > EPS}.values()
    )


def parallel_support(
    patch: dict[str, Any],
    peer: dict[str, Any],
    surfaces: dict[str, GeometrySurface],
    params: dict[str, float],
) -> dict[str, Any] | None:
    """Confirm existing extent/height bounds with actual projected face/section overlap."""
    if patch["candidate_id"] == peer["candidate_id"] or patch["floor"] != peer["floor"]:
        return None
    if sum(a * b for a, b in zip(patch["normal"], peer["normal"], strict=True)) < 0.9999:
        return None
    separation = abs(patch["plane"] - peer["plane"])
    if not params["thickness_min"] <= separation <= params["thickness_max"]:
        return None
    surface, other = surfaces[patch["candidate_id"]], surfaces[peer["candidate_id"]]
    tangent = patch["tangent"]
    points = [sum(p[i] * tangent[i] for i in range(3)) for p in other.vertices]
    lo, hi = patch["tangent_interval"]
    extent_overlap = max(0.0, min(hi, max(points)) - max(lo, min(points))) / patch["extent"]
    box, other_box = patch["bounds"], peer["bounds"]
    height_overlap = (
        max(
            0.0,
            min(box["maximum"][2], other_box["maximum"][2])
            - max(box["minimum"][2], other_box["minimum"][2]),
        )
        / patch["height"]
    )
    if extent_overlap < 0.7 or height_overlap < 0.9:
        return None
    first, second = projected_faces(surface, tangent), projected_faces(other, tangent)
    area = _union_area(first, EPS)
    overlap_faces = [
        face
        for face in _intersections(first, second, EPS)
        if len(face) >= 3 and abs(_signed_area(face)) > EPS
    ]
    overlap = _union_area(overlap_faces, EPS)
    actual_extent = (
        sum(
            b - a
            for a, b in merge_intervals(
                [(min(p[0] for p in face), max(p[0] for p in face)) for face in overlap_faces]
            )
        )
        / patch["extent"]
    )
    actual_height = (
        sum(
            b - a
            for a, b in merge_intervals(
                [(min(p[1] for p in face), max(p[1] for p in face)) for face in overlap_faces]
            )
        )
        / patch["height"]
    )
    first_sections = section_intervals(surface, patch["walkable_relation"]["section_z"], tangent)
    second_sections = section_intervals(other, patch["walkable_relation"]["section_z"], tangent)
    section_length = sum(b - a for a, b in first_sections)
    section_overlap = sum(b - a for a, b in intersect_intervals(first_sections, second_sections))
    ratio, section_ratio = (
        overlap / area if area else 0,
        (section_overlap / section_length if section_length else 0),
    )
    return {
        "paired_patch": peer["candidate_id"],
        "source_object_id": peer["object"],
        "separation": separation,
        "extent_overlap_ratio": extent_overlap,
        "height_overlap_ratio": height_overlap,
        "actual_face_area_overlap_ratio": ratio,
        "actual_extent_overlap_ratio": actual_extent,
        "actual_height_overlap_ratio": actual_height,
        "actual_lower_section_overlap_ratio": section_ratio,
        "passes": actual_extent >= 0.7 and actual_height >= 0.9,
        "basis": "EXACT_PROJECTED_TRIANGLE_UNIONS_AND_LOWER_SECTIONS_NO_HULL_FILL",
    }


def raw_surface(row: dict[str, Any], patch: dict[str, Any]) -> GeometrySurface:
    payload = {
        "surface_id": patch["candidate_id"],
        "source_object_id": row["source_object_id"],
        "source_face_indices": row["source_face_indices"],
        "role": "WALL",
        "floor_ids": [patch["floor"]],
        "vertices": row["vertices"],
        "triangles": row["triangles"],
        "semantic_authority": "HUMAN_REVIEW",
        "physical_authority": "HUMAN_REVIEW",
        "support": "SURFACE",
    }
    return GeometrySurface.model_validate_json(json.dumps(payload))


def audit_surfaces(
    audit: dict[str, Any],
    approved_obstacle_ids: set[str] | None = None,
    obstacle_approval_id: str | None = None,
) -> list[dict[str, Any]]:
    result = []
    for row in audit["objects"]:
        props = row["custom_properties"]
        role = props.get("semantic_class")
        if role not in {"WALKABLE", "OBSTACLE", "PORTAL", "STAIR"} or not row.get("triangles"):
            continue
        floor_ids = (
            [props["floor_id"]]
            if props.get("floor_id")
            else [props[key] for key in ("floor_from", "floor_to") if props.get(key)]
        )
        approved = role == "OBSTACLE" and row["object"] in (approved_obstacle_ids or set())
        result.append(
            {
                "surface_id": row["object"],
                "source_object_id": row["object"],
                "role": role,
                "floor_ids": floor_ids,
                "vertices": row["vertices"],
                "triangles": row["triangles"],
                "semantic_authority": ("APPROVED" if approved else "HUMAN_REVIEW")
                if role == "OBSTACLE"
                else "HIGH_CONFIDENCE",
                "physical_authority": "HUMAN_REVIEW",
                "approval_id": obstacle_approval_id if approved else None,
                "support": "FOOTPRINT"
                if role == "OBSTACLE"
                else ("ANNOTATION" if role == "PORTAL" else "SURFACE"),
                "blocks_movement": role == "OBSTACLE",
                "occludes_visibility": role == "OBSTACLE",
                "stair_id": props.get("stair_id"),
                "evidence_ids": [row["object"]],
            }
        )
    return result


def classify_walls(
    document: dict[str, Any],
    meshes: dict[str, Any],
    audit: dict[str, Any],
) -> list[dict[str, Any]]:
    validate_extraction_policy(document)
    params = document["parameters"]
    patches = {row["candidate_id"]: row for row in document["candidates"]}
    raw = {row["candidate_id"]: row for row in meshes["patches"]}
    if len(patches) != len(document["candidates"]) or len(raw) != len(meshes["patches"]):
        raise ValueError("duplicate candidate or exact geometry identity")
    if patches.keys() != raw.keys():
        raise ValueError("candidate and exact geometry identities differ")
    surfaces = {identity: raw_surface(raw[identity], patch) for identity, patch in patches.items()}
    for identity, patch in patches.items():
        row = raw[identity]
        if row["source_object_id"] != patch["object"] or (
            row["source_face_indices"] != patch["evaluated_face_indices"]
        ):
            raise ValueError("exact surface source face identity differs from candidate")
        geometry = {key: value for key, value in row.items() if key != "geometry_sha256"}
        if value_digest(geometry) != row["geometry_sha256"]:
            raise ValueError("exact geometry content hash differs from recorded evidence")
        validate_patch_coordinates(patch, surfaces[identity], document)
    semantic = [
        GeometrySurface.model_validate_json(json.dumps(row)) for row in audit_surfaces(audit)
    ]
    walkables = {row.surface_id: row for row in semantic if row.role == GeometryRole.WALKABLE}
    portals = tuple(row for row in semantic if row.role == GeometryRole.PORTAL)
    areas = {
        row["object"]: (
            row["custom_properties"].get("floor_id") or row["declared_floor_label"],
            actual_bounds(row["vertices"]),
        )
        for row in audit["objects"]
        if row["custom_properties"].get("semantic_class") == "AREA" and row.get("vertices")
    }
    stair_references = {
        identity
        for row in audit["objects"]
        if row["custom_properties"].get("semantic_class") == "STAIR"
        for identity in row["custom_properties"].get("source_objects", [])
    }
    records: dict[str, dict[str, Any]] = {}
    for identity, patch in sorted(patches.items()):
        nearby_walkables = [
            key
            for key, row in sorted(walkables.items())
            if patch["floor"] in row.floor_ids
            and bounds_distance_xy(
                actual_bounds(surfaces[identity].vertices), actual_bounds(row.vertices)
            )
            <= params["near_distance"]
        ]
        nearby_areas = [
            key
            for key, (floor, box) in sorted(areas.items())
            if floor == patch["floor"]
            and bounds_distance_xy(actual_bounds(surfaces[identity].vertices), box)
            <= params["near_distance"]
        ]
        portal_hits = promoted_wall_portal_conflicts(
            surfaces[identity],
            portals,
            tolerance_m=params["portal_padding"],
            unit_scale_m=1.0,
        )
        intrusions = exact_walkable_intrusions(patch, surfaces[identity], walkables, params)
        components = welded_component_count(surfaces[identity], params["weld_epsilon"])
        reasons = [] if patch["status"] == SEED_STATUS else list(patch["reasons"])
        if patch["status"] not in {SEED_STATUS, "HUMAN_REVIEW"}:
            raise ValueError("unsupported legacy candidate status")
        actual_surface = surfaces[identity]
        actual_height = max(p[2] for p in actual_surface.vertices) - min(
            p[2] for p in actual_surface.vertices
        )
        ts = [sum(p[i] * patch["tangent"][i] for i in range(3)) for p in actual_surface.vertices]
        if not math.isclose(actual_height, patch["height"], abs_tol=EPS) or not math.isclose(
            max(ts) - min(ts), patch["extent"], abs_tol=EPS
        ):
            raise ValueError("candidate height/extent differs from actual source triangles")
        if any(
            abs(sum(point[i] * patch["normal"][i] for i in range(3)) - patch["plane"])
            > params["plane_epsilon"]
            for point in actual_surface.vertices
        ):
            reasons.append("ACTUAL_TRIANGLES_EXCEED_ORIGINAL_COPLANAR_TOLERANCE")
        for a, b, c in actual_surface.triangles:
            u = [actual_surface.vertices[b][i] - actual_surface.vertices[a][i] for i in range(3)]
            v = [actual_surface.vertices[c][i] - actual_surface.vertices[a][i] for i in range(3)]
            normal = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            length = math.hypot(*normal)
            if abs(normal[2]) / length > params["vertical_max_abs_nz"]:
                reasons.append("ACTUAL_TRIANGLE_VERTICALITY_OUTSIDE_ORIGINAL_THRESHOLD")
                break
        # Even a claimed legacy seed must satisfy the original feature gates.
        if components != 1:
            reasons.append("ACTUAL_TRIANGLE_EDGE_CONTINUITY_UNPROVEN")
        if patch["height"] < params["auto_min_height"]:
            reasons.append("INSUFFICIENT_FULL_STOREY_HEIGHT_WINDOW_PANEL_DECOR_OR_FURNITURE_REVIEW")
        if patch["height"] > params["auto_max_height"]:
            reasons.append("MULTI_STOREY_OR_UNASSIGNED_FLOOR_EXTENT_REVIEW")
        if patch["extent"] < params["auto_min_extent"]:
            reasons.append("NARROW_DOOR_PANEL_COLUMN_OR_DECOR_REVIEW")
        if patch["floor_contact_offset"] > params["floor_contact_tolerance"]:
            reasons.append("DOES_NOT_CONTACT_EXISTING_FLOOR_WINDOW_LINTEL_OR_DECOR_REVIEW")
        if not nearby_areas:
            reasons.append("NO_NEARBY_SAME_FLOOR_AREA_AND_WALKABLE_SUPPORT")
        if not section_intervals(
            surfaces[identity], patch["walkable_relation"]["section_z"], patch["tangent"]
        ):
            reasons.append("NO_ACTUAL_SURFACE_AT_LOWER_WALL_SECTION")
        reasons.extend(patch["material_review_flags"])
        if patch["hidden_render"] or patch["hidden_viewport"]:
            reasons.append("HIDDEN_GEOMETRY_REVIEW")
        ignored = [
            identity
            for identity in patch["walkable_relation"]["nearby"]
            if identity not in walkables
        ]
        if any(identity not in stair_references for identity in ignored):
            raise ValueError("legacy WALKABLE reference has no exact source geometry")
        if not nearby_walkables:
            reasons.append("NO_ACTUAL_SAME_FLOOR_WALKABLE_SUPPORT")
        if intrusions:
            reasons.append("CONTINUOUS_WALKABLE_INTERIOR_INTRUSION")
        if portal_hits:
            reasons.append("HARD_PROTECTED_PORTAL_CONTACT_OR_INTERSECTION")
        support, limited = [], False
        # Recheck legacy bounding-interval evidence using actual triangles.
        for evidence in patch["thickness_evidence"]:
            try:
                actual = parallel_support(
                    patch, patches[evidence["paired_patch"]], surfaces, params
                )
            except GeometryBudgetExceeded:
                limited = True
                continue
            if actual is not None:
                support.append(actual)
        try:
            actual_fill = _union_area(
                projected_faces(surfaces[identity], patch["tangent"]), EPS
            ) / (patch["height"] * patch["extent"])
        except GeometryBudgetExceeded:
            actual_fill = 0.0
            reasons.append("EXACT_FILL_GEOMETRY_BUDGET_EXCEEDED")
        broad = patch["extent"] >= params["broad_sheet_min_extent"] and actual_fill >= 0.9
        valid_support = any(row["passes"] for row in support) or broad
        if patch["status"] == SEED_STATUS and not valid_support:
            reasons.append("ACTUAL_PARALLEL_FACE_OR_LOWER_SECTION_SUPPORT_UNPROVEN")
        if limited and not valid_support:
            reasons.append("EXACT_SUPPORT_GEOMETRY_BUDGET_EXCEEDED")
        records[identity] = {
            "candidate_id": identity,
            "source_object_id": patch["object"],
            "floor": patch["floor"],
            "baseline_status": patch["status"],
            "bounds": patch["bounds"],
            "source_face_indices": patch["evaluated_face_indices"],
            "status": "REJECTED"
            if portal_hits
            else ("HUMAN_REVIEW" if reasons else "HIGH_CONFIDENCE"),
            "reasons": sorted(set(reasons)),
            "protected_portal_conflicts": list(portal_hits),
            "continuous_walkable_intrusions": intrusions,
            "actual_nearby_walkables": nearby_walkables,
            "actual_nearby_areas": nearby_areas,
            "exact_parallel_support": support,
            "broad_sheet_exception": broad,
            "actual_projected_fill_ratio": actual_fill,
            "actual_welded_triangle_components": components,
            "ignored_explicit_stair_references": ignored,
        }
    seeds = {identity for identity, row in records.items() if row["status"] == "HIGH_CONFIDENCE"}
    # Only isolated weak support may be resolved. Do not relax height/extent/material/floor rules.
    for identity, row in records.items():
        if row["status"] != "HUMAN_REVIEW" or row["reasons"] != [WEAK_SUPPORT]:
            continue
        patch = patches[identity]
        for peer_id in sorted(seeds):
            if patch["object"] == patches[peer_id]["object"]:
                continue
            try:
                new_support = parallel_support(patch, patches[peer_id], surfaces, params)
            except GeometryBudgetExceeded:
                row["reasons"].append("EXACT_SUPPORT_GEOMETRY_BUDGET_EXCEEDED")
                continue
            if new_support is not None and new_support["passes"]:
                row["exact_parallel_support"].append(new_support)
                row["status"], row["reasons"] = (
                    "HIGH_CONFIDENCE",
                    ["CROSS_OBJECT_ACTUAL_FACE_SUPPORT_FROM_REVALIDATED_SEED"],
                )
                break
    return list(records.values())


def build_snapshot(
    document: dict[str, Any],
    meshes: dict[str, Any],
    audit: dict[str, Any],
    walls: list[dict[str, Any]],
    *,
    approved_obstacle_ids: set[str] | None = None,
    obstacle_approval_id: str | None = None,
) -> SceneGeometrySnapshot:
    """Publish exact, reviewable surfaces, never a wall envelope or obstacle extrusion."""
    surfaces = audit_surfaces(audit, approved_obstacle_ids, obstacle_approval_id)
    raw = {row["candidate_id"]: row for row in meshes["patches"]}
    for record in walls:
        row = raw[record["candidate_id"]]
        status = record["status"]
        surfaces.append(
            {
                "surface_id": record["candidate_id"],
                "source_object_id": row["source_object_id"],
                "source_face_indices": row["source_face_indices"],
                "role": "WALL",
                "floor_ids": [record["floor"]],
                "vertices": row["vertices"],
                "triangles": row["triangles"],
                "semantic_authority": status,
                "physical_authority": status,
                "support": "SURFACE",
                "blocks_movement": status == "HIGH_CONFIDENCE",
                "occludes_visibility": status == "HIGH_CONFIDENCE",
                "evidence_ids": [record["candidate_id"], row["geometry_sha256"]],
            }
        )
    portals, stairs = [], []
    for row in audit["objects"]:
        props = row["custom_properties"]
        if props.get("semantic_class") == "PORTAL":
            portals.append(
                {
                    "portal_id": row["object"],
                    "surface_id": row["object"],
                    "floor_id": props["floor_id"],
                    "authority": "HUMAN_REVIEW",
                    "evidence_ids": [row["object"]],
                }
            )
    for identity in sorted(
        {
            row["custom_properties"].get("stair_id")
            for row in audit["objects"]
            if row["custom_properties"].get("semantic_class") == "STAIR"
        }
    ):
        rows = [
            row
            for row in audit["objects"]
            if row["custom_properties"].get("semantic_class") == "STAIR"
            and row["custom_properties"].get("stair_id") == identity
        ]
        entry = next(
            (row for row in rows if row["custom_properties"]["stair_role"] == "ENTRY"), None
        )
        exit_row = next(
            (row for row in rows if row["custom_properties"]["stair_role"] == "EXIT"), None
        )
        declared = rows[0]["custom_properties"]
        stairs.append(
            {
                "stair_id": identity,
                "floor_from": declared["floor_from"],
                "floor_to": declared["floor_to"],
                "entry_point": entry["centroid"] if entry else None,
                "exit_point": exit_row["centroid"] if exit_row else None,
                "path_surface_ids": [
                    row["object"]
                    for row in rows
                    if row["custom_properties"]["stair_role"] == "PATH"
                ],
                "connectivity_authority": "HUMAN_REVIEW",
                "opening_authority": "HUMAN_REVIEW",
                "clearance_authority": "HUMAN_REVIEW",
                "evidence_ids": [row["object"] for row in rows],
            }
        )
    payload = {
        "schema_version": "scene-geometry-v1",
        "source_sha256": document["source"]["sha256"],
        "scene_id": Path(document["source"]["path"]).stem,
        "unit_scale_m": 1.0,
        "scale_authority": "HUMAN_REVIEW",
        "physical_complete": False,
        "coordinate_convention": "RIGHT_HANDED_Z_UP",
        "portal_protection_tolerance_m": document["parameters"]["portal_padding"],
        "floors": [
            {
                "floor_id": floor,
                "point": [0, 0, height],
                "normal": [0, 0, 1],
                "authority": "HUMAN_REVIEW",
                "evidence_ids": ["PROPOSED_FLOOR_" + floor],
            }
            for floor, height in sorted(document["floor_planes"].items())
        ],
        "surfaces": surfaces,
        "portals": portals,
        "stairs": stairs,
    }
    return SceneGeometrySnapshot.model_validate_json(json.dumps(payload))


def _reject_truth(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("geometry authority input keys must be strings")
            if "ground_truth" in key.lower() or key.lower() in {"gt", "truth", "target_trajectory"}:
                raise ValueError("Ground Truth fields are forbidden in geometry authority input")
            _reject_truth(item)
    elif isinstance(value, list):
        for item in value:
            _reject_truth(item)


def review_authority(
    candidates: dict[str, Any],
    meshes: dict[str, Any],
    audit: dict[str, Any],
    config: dict[str, Any],
    *,
    expected_source_sha256: str,
    obstacle_authorization: dict[str, Any] | None = None,
    baseline_git_commit: str | None = None,
) -> tuple[dict[str, Any], SceneGeometrySnapshot]:
    for document in (candidates, meshes, audit, config):
        _reject_truth(document)
    if candidates.get("schema_version") != "source-bound-wall-candidates-pilot-v1" or (
        meshes.get("schema_version") != "geometry-evidence-snapshot-v1"
    ):
        raise ValueError("unsupported source-bound geometry evidence version")
    if (
        candidates["source"]["sha256"] != expected_source_sha256
        or meshes["source_sha256"] != expected_source_sha256
        or audit["source_sha256"] != expected_source_sha256
    ):
        raise ValueError("geometry evidence source SHA-256 mismatch")
    if meshes.get("candidate_content_sha256") != value_digest(candidates):
        raise ValueError("candidate content differs from source-bound extraction evidence")
    if meshes.get("audit_content_sha256") != value_digest(audit):
        raise ValueError("semantic audit content differs from source-bound extraction evidence")
    if config.get("meters_per_blender_unit") != 1.0:
        raise ValueError("geometry review must preserve the accepted 1m-per-unit conversion")
    if candidates["policy"]["gt_used"] or candidates["policy"]["whole_objects_reclassified"]:
        raise ValueError("candidate extraction must be geometry-only and patch-only")
    if not meshes["source_preserved"] or meshes["saved"] or meshes["rendered"]:
        raise ValueError("geometry export must preserve the source without save/render")
    authorized: set[str] = set()
    approval_id = None
    if obstacle_authorization is not None:
        if obstacle_authorization.get("schema_version") != "geometry-role-authorization-v1" or (
            obstacle_authorization.get("source_sha256") != expected_source_sha256
            or obstacle_authorization.get("authority_scope") != "SEMANTIC_ROLE_ONLY"
        ):
            raise ValueError("obstacle role authorization source/scope mismatch")
        _reject_truth(obstacle_authorization)
        approval_id = obstacle_authorization["approval_id"]
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise ValueError("obstacle role approval_id must be nonempty")
        identifiers = obstacle_authorization["approved_obstacle_ids"]
        if not isinstance(identifiers, list) or any(not isinstance(x, str) for x in identifiers):
            raise ValueError("approved obstacle identities must be an explicit string list")
        authorized = set(identifiers)
        known = {
            row["object"]
            for row in audit["objects"]
            if row["custom_properties"].get("semantic_class") == "OBSTACLE"
        }
        if len(authorized) != len(identifiers) or not authorized <= known:
            raise ValueError("duplicate or unknown source-bound obstacle role identity")
    walls = classify_walls(candidates, meshes, audit)
    physical = review_physical_geometry(
        audit,
        config,
        approved_obstacle_ids=authorized,
        obstacle_review_id=approval_id,
    )
    snapshot = build_snapshot(
        candidates,
        meshes,
        audit,
        walls,
        approved_obstacle_ids=authorized,
        obstacle_approval_id=approval_id,
    )
    provider = ReadOnlySceneGeometryProvider(snapshot, expected_source_sha256)
    seed_rows = [row for row in walls if row["baseline_status"] == SEED_STATUS]
    reviewed = [row for row in walls if row["baseline_status"] != SEED_STATUS]
    counts = {
        status.value: sum(row["status"] == status.value for row in walls) for status in Authority
    }
    report = {
        "schema_version": "geometry-authority-review-v1",
        "source_sha256": expected_source_sha256,
        "baseline_git_commit": baseline_git_commit,
        "scope": "PHASE1_GEOMETRY_AUTHORITY_NOT_BENCHMARK",
        "physical_authority": "PROVISIONAL",
        "thresholds": candidates["parameters"],
        "thresholds_lowered": False,
        "policy": {
            "approved": "EXPLICIT_SOURCE_BOUND_HUMAN_APPROVAL; NOT AUTOMATIC_CONFIDENCE",
            "high_confidence": (
                "RECHECKED_GEOMETRY_HEURISTICS; NOT COMPLETE_NAVIGATION_CERTIFICATION"
            ),
            "human_review": "UNRESOLVED_ROLE_OR_PHYSICAL_EVIDENCE",
            "rejected": "UNSAFE_FOR_WALL_INSTALLATION; ORIGINAL_SOURCE_FACE_IS_PRESERVED",
            "doorway": (
                "ALL_EXPLICIT_PORTAL_VOLUMES_PROTECT_ACTUAL_TRIANGLES_WITH_ORIGINAL_PADDING"
            ),
            "parallel_support": "ACTUAL_OVERLAP_COVERAGE_TANGENT_GE_0.7_HEIGHT_GE_0.9",
            "broad_sheet": "ACTUAL_UNION_FILL_GE_0.9_EXTENT_GE_ORIGINAL_280; NO_RECTANGLE_INFILL",
            "walkable_intrusion": (
                "CONTINUOUS_TWO_SIDE_TRIANGLE_UNION_INTERVALS_AT_EXISTING_SECTION_Z"
            ),
            "source_saved": False,
            "rendered": False,
            "gt_used": False,
            "graph_or_ranking_modified": False,
            "elevator_exists": False,
        },
        "wall_summary": {
            "baseline_seeds": len(seed_rows),
            "baseline_human_review": len(reviewed),
            "final": counts,
            "seeds_retained": sum(row["status"] == "HIGH_CONFIDENCE" for row in seed_rows),
            "seed_downgrades": [
                row["candidate_id"] for row in seed_rows if row["status"] != "HIGH_CONFIDENCE"
            ],
            "new_promotions": [
                row["candidate_id"] for row in reviewed if row["status"] == "HIGH_CONFIDENCE"
            ],
            "by_floor": dict(
                sorted(
                    Counter(
                        row["floor"] for row in walls if row["status"] == "HIGH_CONFIDENCE"
                    ).items()
                )
            ),
        },
        "doorway_protection": {
            "protected_portals": len(provider.get_portals()),
            "rejected_patches": counts["REJECTED"],
            "accepted_wall_contacts": 0,
            "rejected_ids": [row["candidate_id"] for row in walls if row["status"] == "REJECTED"],
        },
        "walls": walls,
        "physical_review": physical,
        "provider": {
            "schema_version": snapshot.schema_version,
            "read_only": True,
            "blender_dependency": False,
            "walkables": len(provider.get_walkable()),
            "wall_surfaces": len(provider.get_walls()),
            "obstacles": len(provider.get_obstacles()),
            "portals": len(provider.get_portals()),
            "stairs": len(provider.get_stairs()),
            "floors": len(provider.get_floors()),
            "default_approved_colliders": sum(
                len(provider.get_colliders(floor.floor_id)) for floor in provider.get_floors()
            ),
            "high_confidence_wall_surfaces": counts["HIGH_CONFIDENCE"],
            "physical_complete": False,
        },
        "unresolved_human_decisions": [
            "Confirm remaining wall/window/door/decor roles; reconcile downgraded seed boundaries",
            "Reconcile bathroom/main-entrance/meeting-room obstacle-to-portal footprint conflicts",
            "Supply source-bound OBSTACLE height/volume and visibility evidence; "
            "no invented extrusion",
            "Reconcile proposed WALKABLE floors with actual mesh support; approve floor authority",
            "Confirm independent architectural dimensions; preserve the accepted "
            "1m-per-unit calculation config",
            "Provide stair landing, floor endpoint connections and opening/clearance evidence",
            "Approve geometry completeness and clearance/contact policy before "
            "formal collision validity",
        ],
    }
    return report, snapshot


def write_report(report: dict[str, Any], output: Path) -> None:
    wall = report["wall_summary"]
    physical = report["physical_review"]
    downgraded = [row for row in report["walls"] if row["candidate_id"] in wall["seed_downgrades"]]
    intrusion_count = sum(bool(row["continuous_walkable_intrusions"]) for row in downgraded)
    unsupported_count = sum(
        "ACTUAL_PARALLEL_FACE_OR_LOWER_SECTION_SUPPORT_UNPROVEN" in row["reasons"]
        for row in downgraded
    )
    obstacle_rows = physical["obstacle_reviews"]
    approved_roles = sum(row["semantic_role_status"] == "APPROVED" for row in obstacle_rows)
    walk_conflicts = sum(len(row["conflicts"]["walkable"]) for row in obstacle_rows)
    portal_conflicts = sum(len(row["conflicts"]["portal"]) for row in obstacle_rows)
    lines = [
        "# Phase 1 geometry authority",
        "",
        "Physical / collision validity: **PROVISIONAL**。",
        "本報告為幾何審查，不執行 benchmark 或建立 Graph connectivity。",
        f"Source SHA-256: `{report['source_sha256']}`；"
        f"checkpoint `{report['baseline_git_commit']}`。",
        "",
        "APPROVED 是明確人工 role/physical approval；HIGH_CONFIDENCE 是可重驗幾何信心，",
        "不等於完整 physical approval；HUMAN_REVIEW 保留歧義；REJECTED 禁止安裝成 WALL，",
        "但不刪除原始 source faces。沒有降低原閾值、填 rectangle、封門、改米制換算或讀 GT。",
        "",
        f"## WALL: {wall['baseline_seeds']} seeds + {wall['baseline_human_review']} review patches",
        "",
        "| 最終狀態 | Patches |",
        "| --- | ---: |",
        *[f"| {status} | {count} |" for status, count in wall["final"].items()],
        "",
        f"原 seeds 保留 {wall['seeds_retained']}；降級 {len(wall['seed_downgrades'])}；"
        f"原 review 升級 {len(wall['new_promotions'])}。",
        "",
        "新升級：" + ", ".join(f"`{identity}`" for identity in wall["new_promotions"]),
        "",
        f"{len(downgraded)} 個 seeds 降級；其中 {intrusion_count} 個 "
        "continuous WALKABLE intrusion，",
        f"{unsupported_count} 個 actual parallel face support",
        "未達原 0.7 tangent／0.9 height coverage。原 17-point sampling 與 bounding interval 證據",
        "漏掉局部穿入或跨缺面支持；新的實際 triangle unions／連續 intervals 保留 openings。",
        "",
        "## Doorway hard protection",
        "",
        f"全部 {report['doorway_protection']['protected_portals']} PORTAL："
        f"{report['doorway_protection']['rejected_patches']} patches hard REJECTED；"
        "accepted contacts **0**。",
        "沿用 portal padding 0.28 native units，檢查所有樓層的實際 aperture volumes；",
        "wall wholly inside aperture、交叉及 boundary contact 都不能透過錯誤 floor label 繞過。",
        "Floor label 不一致也不能放過實際相交；逐 patch rejection IDs 完整保存。",
        "",
        "## OBSTACLE",
        "",
        f"{len(obstacle_rows)} 個 OBSTACLE；其中 {approved_roles} 個 semantic roles APPROVED。",
        "movement blocking / visibility occlusion 均 true；role approval 來自獨立明示授權。",
        "實際 footprints／open surfaces 不自動擠出高度，physical authority 全部 HUMAN_REVIEW。",
        "",
        "| OBSTACLE | Role | Geometry | WALKABLE conflict pairs | PORTAL conflict pairs |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in physical["obstacle_reviews"]:
        lines.append(
            f"| {row['object_id']} | {row['semantic_role_status']} | "
            f"{row['physical_geometry_status']} | {len(row['conflicts']['walkable'])} | "
            f"{len(row['conflicts']['portal'])} |"
        )
    lines.extend(
        [
            "",
            f"WALKABLE 超過配置 contact ratio：{walk_conflicts} pairs；"
            f"PORTAL：{portal_conflicts} pairs。",
            "逐 obstacle conflict IDs / overlap 比例保存於 authority.json；",
            "人工修正實際佔地／門洞，不因 role approval 自動核准 physical volume。",
            "",
            "## Stair A/B",
            "",
            "| Stair | Authority | PATH components | Closest surface gap | "
            "ENTRY→WALKABLE | EXIT→WALKABLE |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in physical["stair_reviews"]:
        gaps = row.get("component_gap_measurements", [])
        gap = f"{gaps[0]['closest_surface_gap_m']:.6f}" if gaps else "N/A"
        entry_distance = row.get("entry_walkable", {}).get("distance_m")
        exit_distance = row.get("exit_walkable", {}).get("distance_m")
        entry_text = f"{entry_distance:.6f}" if entry_distance is not None else "N/A"
        exit_text = f"{exit_distance:.6f}" if exit_distance is not None else "N/A"
        lines.append(
            f"| {row['stair_id']} | {row['status']} | "
            f"{len(row.get('path_mesh_components', []))} | {gap} | {entry_text} | {exit_text} |"
        )
    lines.extend(
        [
            "",
            "Distances 保留已採用1m-per-unit配置；不等於建築尺寸另行認證。",
            "PATH components / nearest3Dgap 與中心線join不同。ENTRY/PATH/EXIT及UP metadata",
            "可核對，但landing／opening／clearance未核准，不生成跨層 connector。",
            "只有樓梯，沒有電梯。",
            "",
            "## Read-only provider",
            "",
            "[Contract](../../../docs/GEOMETRY_PROVIDER.md)；[portable geometry](geometry.json)；",
            "[raw exact mesh evidence](wall_meshes.json)。",
            "Frozen tuples/models、source/content SHA binding、exact triangle holes、",
            "explicit authority filters；require_approved_physics 對 PROVISIONAL 明確拒絕。",
            "無 bpy、GT、ranking 或 benchmark dependency。",
            "Default APPROVED collider query 為"
            f"{report['provider']['default_approved_colliders']}；空結果不能證明無碰撞。",
            f"caller可明示HIGH_CONFIDENCE查看{wall['final']['HIGH_CONFIDENCE']}個wall surfaces。",
            "Review／rejected geometry 保留供 inspection，不自動變成 collision colliders。",
            "",
            "## 尚需人工決定",
            "",
            *["- " + value for value in report["unresolved_human_decisions"]],
            "",
            "## 每個 HIGH_CONFIDENCE / HUMAN_REVIEW / REJECTED patch",
            "",
            "| Patch / source object | Floor | Bounds | Status | Evidence / reasons |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report["walls"]:
        reasons = (
            "; ".join(row["reasons"]) or "REVALIDATED_ORIGINAL_FEATURE_GATES_AND_ACTUAL_GEOMETRY"
        )
        lines.append(
            f"| {row['candidate_id']} / {row['source_object_id']} | {row['floor']} | "
            f"{row['bounds']['minimum']} → {row['bounds']['maximum']} | "
            f"{row['status']} | {reasons} |"
        )
    output.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--meshes", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--obstacle-authorization", type=Path, required=True)
    parser.add_argument("--baseline-git-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    outputs = [
        args.output / name
        for name in ("authority.json", "authority.md", "geometry.json", "manifest.json")
    ]
    if any(path.exists() for path in outputs):
        raise FileExistsError("authority output exists; use a fresh output directory")
    paths = {
        name: getattr(args, name)
        for name in ("candidates", "meshes", "audit", "config", "obstacle_authorization")
    }
    documents = {name: json.loads(path.read_text()) for name, path in paths.items()}
    if documents["meshes"]["candidate_sha256"] != digest(args.candidates):
        raise ValueError("mesh evidence candidate document SHA-256 differs")
    report, snapshot = review_authority(
        documents["candidates"],
        documents["meshes"],
        documents["audit"],
        documents["config"],
        expected_source_sha256=args.expected_source_sha256,
        obstacle_authorization=documents["obstacle_authorization"],
        baseline_git_commit=args.baseline_git_commit,
    )
    report["input_bindings"] = {
        name: {"path": str(path), "sha256": digest(path)} for name, path in paths.items()
    }
    args.output.mkdir(parents=True, exist_ok=True)
    outputs[0].write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    write_report(report, outputs[1])
    outputs[2].write_text(snapshot.model_dump_json(indent=2) + "\n")
    outputs[3].write_text(
        json.dumps(
            {
                "schema_version": "geometry-authority-manifest-v1",
                "source_sha256": args.expected_source_sha256,
                "inputs": report["input_bindings"],
                "artifacts": {path.name: digest(path) for path in outputs[:3]},
                "code_sha256": {
                    name: digest(Path(name))
                    for name in (
                        "src/amidst/geometry_authority.py",
                        "src/amidst/geometry_physical_review.py",
                        "src/amidst/scene_geometry.py",
                        "scripts/export_geometry_authority_snapshot.py",
                    )
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "walls": report["wall_summary"]["final"],
                "physical_authority": report["physical_authority"],
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
