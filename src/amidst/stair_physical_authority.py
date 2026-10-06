"""Read-only source staircase inspection; proxy paths never become physical support.

The census identifies actual horizontal/inclined source geometry and measures
body-sized landing candidates. A structural candidate alone does not certify a
body sweep, an opening, stepping ability, or bidirectional traversability.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from amidst.obstacle_volume_authority import (
    content_sha256,
    region_patches,
    validate_source_evidence,
)
from amidst.physical_floor_stair_review import _ray_height
from amidst.physical_policy_contract import PhysicalPolicyContract


def _normal(points: list[list[float]]) -> tuple[float, float, float] | None:
    a, b, c = points
    u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0])
    length = math.hypot(*n)
    if length == 0 or not math.isfinite(length):
        return None
    return n[0] / length, n[1] / length, n[2] / length


def _rows(audit: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in audit["objects"]:
        props = row.get("custom_properties", {})
        if props.get("semantic_class") == "STAIR":
            identity = props.get("stair_id")
            if not isinstance(identity, str) or not identity:
                raise ValueError("stair annotation requires an explicit identity")
            grouped[identity].append(row)
    return grouped


def review_stair_physical_authority(
    evidence: Mapping[str, Any], audit: Mapping[str, Any], contract: PhysicalPolicyContract,
    *, floor_points_bu: Mapping[str, Sequence[float]] | None = None,
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect complete source selections without making up a run/landing/route.

    Native floor points are optional source-coordinate references, not approvals.
    Formal stair authority still requires continuous supports plus opening and
    full-body swept-clearance evidence; the census never substitutes ray probes.
    """
    contract = PhysicalPolicyContract(contract.policy, contract.scale, contract.runtime)
    validate_source_evidence(
        evidence, expected_source_sha256=contract.runtime.source_asset_sha256,
        expected_audit_content_sha256=content_sha256(audit),
    )
    if evidence["architectural_scale"] != contract.scale.model_dump(mode="json"):
        raise ValueError("stair source evidence architectural scale differs from runtime")
    if settings is None:
        settings = json.loads(Path(
            "configs/physical_authority_resolution_school_v3.json"
        ).read_text())["floor_stair_review"]
    normal_min = settings["horizontal_normal_abs_z_min"]
    layer_tolerance = settings["horizontal_layer_tolerance_units"]
    if (
        isinstance(normal_min, bool) or not isinstance(normal_min, (int, float))
        or not math.isfinite(normal_min) or not 0 < normal_min <= 1
        or isinstance(layer_tolerance, bool) or not isinstance(layer_tolerance, (int, float))
        or not math.isfinite(layer_tolerance) or layer_tolerance <= 0
    ):
        raise ValueError("stair diagnostic orientation/layer settings must be finite and positive")
    floors = {} if floor_points_bu is None else dict(floor_points_bu)
    for point in floors.values():
        if len(point) != 3 or any(
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) for value in point
        ):
            raise ValueError("stair floor references require finite native coordinates")
    regions = [r for r in evidence["regions"] if r["kind"] == "STAIR_CONTEXT"]
    annotated = _rows(audit)
    result = []
    for region in sorted(regions, key=lambda item: item["region_id"]):
        identity = region.get("stair_id")
        if identity is None:
            identity = next((key for key in annotated if region["region_id"] in {
                key, "STAIR_" + key, "STAIR:" + key,
            }), None)
        if identity not in annotated:
            raise ValueError("source stair region lacks an explicit known annotation binding")
        members = annotated[identity]
        props = members[0]["custom_properties"]
        source_helpers = {
            source for row in members
            if row["custom_properties"].get("geometry_authority")
            == "ANNOTATION_PROXY_NOT_PHYSICAL_CERTIFICATION"
            for source in row["custom_properties"].get("source_objects", [])
        }
        patches = region_patches(evidence, region["region_id"])
        bounds = region["bounds_bu"]
        footprint = box(bounds["minimum"][0], bounds["minimum"][1],
                        bounds["maximum"][0], bounds["maximum"][1])
        groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
        incline = []
        all_faces = []
        invalid_faces = []
        for patch in patches:
            if patch["source_object_id"] in source_helpers:
                continue
            for triangle, face, original_index in zip(
                patch["triangles"], patch["triangle_source_face_indices"],
                patch["source_triangle_indices"], strict=True,
            ):
                points = [patch["vertices"][index] for index in triangle]
                normal = _normal(points)
                if normal is None:
                    invalid_faces.append({
                        "source_object_id": patch["source_object_id"],
                        "source_face_index": face, "source_triangle_index": original_index,
                        "reason_code": "DEGENERATE_OR_NONFINITE_SOURCE_FACE_GEOMETRY",
                    })
                    continue
                polygon = Polygon([(p[0], p[1]) for p in points]).intersection(footprint)
                record = {
                    "source_object_id": patch["source_object_id"], "mesh_id": patch["mesh_id"],
                    "source_face_index": face, "source_triangle_index": original_index,
                    "points": points, "polygon": polygon, "normal": normal,
                }
                all_faces.append(record)
                if polygon.is_empty or polygon.area == 0:
                    continue
                if abs(normal[2]) >= normal_min:
                    groups[round(sum(p[2] for p in points) / (3 * layer_tolerance))].append(record)
                elif abs(normal[2]) > 1e-9:
                    incline.append(record)
        levels = []
        required_radius = contract.footprint_radius_bu
        all_faces.sort(key=lambda r: (
            r["source_object_id"], r["source_face_index"], r["source_triangle_index"],
        ))
        incline.sort(key=lambda r: (
            r["source_object_id"], r["source_face_index"], r["source_triangle_index"],
        ))
        for _, records in sorted(groups.items()):
            records.sort(key=lambda r: (
                r["source_object_id"], r["source_face_index"], r["source_triangle_index"],
            ))
            union = unary_union([r["polygon"] for r in records])
            # Erosion proposes a centre; exact boundary distance independently
            # verifies the full disk instead of treating a buffer as a certificate.
            eroded = union.buffer(-required_radius, quad_segs=64)
            centre = None if eroded.is_empty else eroded.representative_point()
            fits = centre is not None and union.covers(centre) and (
                union.boundary.distance(centre) >= required_radius
            )
            xyz = [p for r in records for p in r["points"]]
            z = sum(p[2] for p in xyz) / len(xyz)
            layer_bounds = {
                "minimum": [union.bounds[0], union.bounds[1], min(p[2] for p in xyz)],
                "maximum": [union.bounds[2], union.bounds[3], max(p[2] for p in xyz)],
            }
            headroom = None
            obstruction = None
            if fits and centre is not None:
                contacts = []
                for other in all_faces:
                    pts = tuple(tuple(p) for p in other["points"])
                    height = _ray_height(centre.x, centre.y, pts, 1e-9)  # type: ignore[arg-type]
                    if height is not None and height > z + contract.scale.to_blender_units(
                        contract.parameter("collision_tolerance_m")
                    ):
                        contacts.append((height - z, other))
                if contacts:
                    gap, nearest = min(contacts, key=lambda pair: (
                        pair[0], pair[1]["source_object_id"], pair[1]["source_face_index"],
                    ))
                    headroom = contract.scale.to_metres(gap)
                    obstruction = {key: nearest[key] for key in (
                        "source_object_id", "source_face_index", "source_triangle_index",
                    )}
            levels.append({
                "z_bu": z, "z_m": contract.scale.to_metres(z),
                "z_range_bu": [min(p[2] for p in xyz), max(p[2] for p in xyz)],
                "bounds_bu": layer_bounds,
                "bounds_m": {key: [contract.scale.to_metres(value) for value in values]
                             for key, values in layer_bounds.items()},
                "support_area_bu2": union.area,
                "support_area_m2": contract.scale.to_square_metres(union.area),
                "body_sized_disk_fits": fits,
                "centre_bu": None if not fits or centre is None else [centre.x, centre.y, z],
                "point_headroom_m": headroom, "point_obstruction": obstruction,
                "point_headroom_policy_check": (
                    "UNAVAILABLE" if headroom is None else
                    "FAIL_KNOWN_SOURCE_INTERSECTION" if headroom < (
                        contract.parameter("body_height_m") + contract.parameter("body_clearance_m")
                    ) else "PASS_POINT_DIAGNOSTIC_ONLY"
                ),
                "headroom_evidence": "POINT_DIAGNOSTIC_NOT_BODY_OR_OPENING_CERTIFICATION",
                "geometry_role": "HORIZONTAL_SOURCE_SURFACE_CANDIDATE_ONLY",
                "source_faces": sorted({(r["source_object_id"], r["source_face_index"])
                                        for r in records}),
            })
        lower, upper = floors.get(props["floor_from"]), floors.get(props["floor_to"])
        middle = [] if lower is None or upper is None else [
            layer for layer in levels if min(lower[2], upper[2]) + layer_tolerance
            < layer["z_bu"] < max(lower[2], upper[2]) - layer_tolerance
        ]
        landing = [layer for layer in middle if layer["body_sized_disk_fits"] and (
            layer["point_headroom_policy_check"] != "FAIL_KNOWN_SOURCE_INTERSECTION"
        )]
        slopes = [{
            "source_object_id": r["source_object_id"], "source_face_index": r["source_face_index"],
            "source_triangle_index": r["source_triangle_index"],
            "slope_degrees": math.degrees(math.acos(abs(r["normal"][2]))),
            "z_range_bu": [min(p[2] for p in r["points"]), max(p[2] for p in r["points"])],
            "centroid_bu": [sum(p[i] for p in r["points"]) / 3 for i in range(3)],
            "projected_area_m2": contract.scale.to_square_metres(r["polygon"].area),
            "geometry_role": "INCLINED_SOURCE_FACE_CANDIDATE_ONLY",
        } for r in incline]
        reasons = ["SOURCE_SUPPORT_CHAIN_NOT_PROVEN", "FULL_BODY_BIDIRECTIONAL_SWEEP_NOT_PROVEN",
                   "SLAB_OPENING_NOT_PROVEN"]
        if lower is None or upper is None:
            reasons.append("SOURCE_FLOOR_REFERENCES_UNAVAILABLE")
        if not landing:
            reasons.append("NO_BODY_SIZED_INTERMEDIATE_LANDING_EVIDENCE_IN_SELECTED_SOURCE")
        if not slopes:
            reasons.append("NO_INCLINED_SOURCE_RUN_EVIDENCE_IN_SELECTED_SOURCE")
        if not region["selection_complete"]:
            reasons.append("SOURCE_REGION_SELECTION_INCOMPLETE")
        if invalid_faces:
            reasons.append("INVALID_SOURCE_FACE_GEOMETRY_REPORTED")
        result.append({
            "stair_id": identity, "region_id": region["region_id"],
            "authority": "HUMAN_REVIEW", "direction": "BIDIRECTIONAL",
            "floor_from": props["floor_from"], "floor_to": props["floor_to"],
            "source_selection_complete": region["selection_complete"],
            "source_triangles_inspected": len(all_faces),
            "invalid_source_faces": invalid_faces,
            "excluded_annotation_helper_ids": sorted(source_helpers),
            "horizontal_support_layers": levels, "inclined_source_faces": slopes,
            "intermediate_landing_candidates": landing,
            "measured_level_progression_bu": [b["z_bu"] - a["z_bu"]
                                               for a, b in zip(middle, middle[1:], strict=False)],
            "reason_codes": sorted(reasons),
            "support_chain_approved": False, "opening_approved": False,
            "body_clearance_approved": False, "connectivity_created": False,
            "scene_geometry_modified": False,
            "human_decisions": [
                "Bind actual tread/run/landing faces if a credible complete chain exists",
                "Resolve source support interpretation; annotation ramps are not physical evidence",
            ],
            "missing_geometry_statement": (
                "Selected source evidence does not prove a continuous staircase; "
                "this does not assert that the entire scene lacks stair geometry"
            ),
        })
    return {
        "schema_version": "stair-physical-authority-review-v1",
        "source_sha256": contract.runtime.source_asset_sha256,
        "scale_authority": "APPROVED", "policy_authority": "APPROVED",
        "direction": "BIDIRECTIONAL", "stairs": result,
        "physical_stair_approved_count": 0,
        "geometry_modified": False, "gt_used": False,
    }
