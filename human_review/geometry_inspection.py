"""Read-only local office evidence, using public inference and approved body policy.

No evaluation, GT, simulation recipes or formal inference is read or executed.
Prospective floor-contact paths are hypotheses, never accepted trajectories.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import box

from amidst.local_physical_scopes import certify_local_rectangle
from amidst.obstacle_volume_authority import (
    component_geometry,
    component_topology,
    content_sha256,
    region_patches,
    validate_source_evidence,
)
from amidst.physical_collision import CollisionNumerics, upright_body_triangle_distance
from amidst.physical_policy_contract import load_physical_policy_contract
from amidst.scene_geometry import FloorAuthority, GeometrySurface
from amidst.walkable_clearance import WalkableClearanceDomain

ROOT = Path(__file__).resolve().parents[1]
PHYSICAL = ROOT / "data/scene_audit/phase1_physical_policy_approval_20261006"
PUBLIC = ROOT / "data/finalization/local_run/diagnostics/office/policy_graph_primary"
ALLOWED = {
    PHYSICAL / "source_evidence.json.gz",
    PHYSICAL / "floor_support_details.json.gz",
    PUBLIC / "candidates.json",
    PUBLIC / "projected_frames.json",
    ROOT / "configs/physical_collision_numerics_v1.json",
}


def read_allowed(path: Path) -> dict[str, Any]:
    """An explicit input allowlist prevents accidental future GT file reads."""
    path = path.resolve()
    if path not in {p.resolve() for p in ALLOWED}:
        raise ValueError("geometry review reads only explicitly allowlisted public evidence")
    raw = path.read_bytes()
    value = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
    if not isinstance(value, dict):
        raise ValueError("public geometry evidence must be a JSON object")
    return value


def main() -> None:
    evidence = read_allowed(PHYSICAL / "source_evidence.json.gz")
    support = read_allowed(PHYSICAL / "floor_support_details.json.gz")
    candidates_document = read_allowed(PUBLIC / "candidates.json")
    frame_document = read_allowed(PUBLIC / "projected_frames.json")
    contract = load_physical_policy_contract(
        ROOT / "configs/physical_policy_runtime_school_v3.json"
    )
    numerics = CollisionNumerics.model_validate(
        read_allowed(ROOT / "configs/physical_collision_numerics_v1.json"),
    )
    validate_source_evidence(evidence, expected_source_sha256=contract.scale.source_asset_sha256)
    office = next(
        row for row in support["walkable_reviews"] if row["walkable_id"] == "WALK_1F_OFFICE"
    )
    floor = FloorAuthority.model_validate_json(
        json.dumps(next(row for row in support["floor_authorities"] if row["floor_id"] == "1F"))
    )
    approved_surfaces = tuple(
        GeometrySurface.model_validate_json(json.dumps(row)) for row in support["support_surfaces"]
    )
    domain = WalkableClearanceDomain.from_surfaces(
        tuple(row for row in approved_surfaces if row.surface_id in office["support_surface_ids"]),
        floor=floor,
        scale=contract.scale,
        policy=contract.policy,
        expected_source_sha256=contract.scale.source_asset_sha256,
    )
    source_faces = frozenset(
        (surface.source_object_id, face)
        for surface in approved_surfaces
        if "1F" in surface.floor_ids
        for face in surface.source_face_indices
    )
    candidates = [row for result in candidates_document["results"] for row in result["candidates"]]
    if not candidates:
        raise ValueError("public office graph has no candidate paths")
    projected = [
        row["projected_point"]["world_position"]
        for row in frame_document["dataset"]["samples"]
        if row.get("projected_point") is not None
    ]
    paths = []
    for row in candidates:
        foot = [
            (float(p[0]), float(p[1]), office["source_support_height_bu"]) for p in row["polyline"]
        ]
        checks = [
            asdict(domain.validate_segment(a, b)) for a, b in zip(foot, foot[1:], strict=False)
        ]
        paths.append(
            {
                "candidate_id": row["candidate_id"],
                "route": row["navmesh_corridor"],
                "prospective_foot_polyline_bu": foot,
                "source_landmark_polyline_bu": row["polyline"],
                "support_checks": checks,
                "support_eligible_for_prospective_scope": all(d["valid"] for d in checks),
                "physical_route_approved": False,
                "status": "DIAGNOSTIC_PUBLIC_INFERRED_CANDIDATE_NOT_GT",
            }
        )
    eligible = [row for row in paths if row["support_eligible_for_prospective_scope"]]
    public_points = np.asarray(
        [p for row in eligible for p in row["source_landmark_polyline_bu"]] + projected
    )
    low_xy, high_xy = public_points[:, :2].min(axis=0), public_points[:, :2].max(axis=0)
    rectangle = box(*low_xy, *high_xy)
    contact_band = domain.actual_contact_height_band(rectangle)
    if contact_band is None:
        raise ValueError("prospective office domain has no common source contact height")
    support_z = office["source_support_height_bu"]
    ratio = contract.scale.metres_per_blender_unit
    envelope_low = np.r_[
        low_xy - contract.footprint_radius_bu,
        contact_band[0] - contract.scale.to_blender_units(0.05),
    ]
    envelope_high = np.r_[
        high_xy + contract.footprint_radius_bu,
        contact_band[1] + contract.scale.to_blender_units(1.75),
    ]
    vertices = tuple(
        (float(x) * ratio, float(y) * ratio, float(z) * ratio)
        for x, y in list(rectangle.exterior.coords)[:-1]
        for z in contact_band
    )
    selected, findings, legal_support = 0, [], 0
    for patch in region_patches(evidence, "BODY:WALK_1F_OFFICE"):
        triangles = np.asarray(patch["vertices"])[np.asarray(patch["triangles"])]
        indices = np.flatnonzero(
            (triangles.max(axis=1) >= envelope_low).all(axis=1)
            & (triangles.min(axis=1) <= envelope_high).all(axis=1)
        )
        for index in indices:
            selected += 1
            triangle = triangles[index]
            object_id = patch["source_object_id"]
            face_id = int(patch["triangle_source_face_indices"][index])
            norm = float(
                np.linalg.norm(np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0]))
            )
            item = {
                "source_object_id": object_id,
                "source_face_index": face_id,
                "source_triangle_index": patch["source_triangle_indices"][index],
                "source_mesh_id": patch["mesh_id"],
                "source_geometry_sha256": patch["source_geometry_sha256"],
                "triangle_bu": triangle.tolist(),
                "triangle_m": (triangle * ratio).tolist(),
                "centroid_bu": triangle.mean(axis=0).tolist(),
                "centroid_m": (triangle.mean(axis=0) * ratio).tolist(),
                "bounds_bu": [triangle.min(axis=0).tolist(), triangle.max(axis=0).tolist()],
                "current_authority": "SOURCE_CONTEXT_ONLY_NOT_APPROVED_COLLIDER",
            }
            if norm == 0:
                item["machine_status"] = "EXACT_ZERO_AREA_DEGENERATE"
                findings.append(item)
                continue
            if (object_id, face_id) in source_faces and (
                contact_band[0] >= triangle[:, 2].max() - domain.contact_tolerance_bu
                and contact_band[1] <= triangle[:, 2].min() + domain.contact_tolerance_bu
            ):
                legal_support += 1
                continue
            triangle_m = [tuple(float(v) for v in p) for p in triangle * ratio]
            distance = upright_body_triangle_distance(
                vertices,
                (
                    (triangle_m[0][0], triangle_m[0][1], triangle_m[0][2]),
                    (triangle_m[1][0], triangle_m[1][1], triangle_m[1][2]),
                    (triangle_m[2][0], triangle_m[2][1], triangle_m[2][2]),
                ),
                radius_m=0.3,
                height_m=1.7,
                numerics=numerics,
            )
            if distance.lower_m < 0.05:
                item["machine_status"] = (
                    "BODY_CONTACT"
                    if distance.upper_m <= 0.001
                    else "BODY_CLEARANCE"
                    if distance.upper_m < 0.05
                    else "DISTANCE_UNCERTAIN"
                )
                item["distance_bounds_m"] = [distance.lower_m, distance.upper_m]
                findings.append(item)
    certificate, certificate_result = certify_local_rectangle(
        domain,
        rectangle,
        evidence,
        "BODY:WALK_1F_OFFICE",
        contract,
        numerics,
        support_source_faces=source_faces,
        evidence_content_sha256=content_sha256(evidence),
    )
    group = next(row for row in evidence["meshes"] if row["source_object_id"] == "group_0")
    component = next(
        row for row in group["components"] if row["component_id"] == "component-00000000"
    )
    region = next(row for row in evidence["regions"] if row["region_id"] == "BODY:WALK_1F_OFFICE")
    center = np.r_[
        (low_xy + high_xy) / 2, sum(contact_band) / 2 + contract.scale.to_blender_units(0.85)
    ]
    meshes = {m["mesh_id"]: m for m in evidence["meshes"]}
    enclosing_context = []
    for selection in region["selections"]:
        mesh = meshes[selection["mesh_id"]]
        for part in mesh["components"]:
            if part["component_id"] not in selection["component_ids"]:
                continue
            bounds = part["bounds_bu"]
            if np.all(center >= bounds["minimum"]) and np.all(center <= bounds["maximum"]):
                part_vertices, part_triangles, _ = component_geometry(mesh, part)
                enclosing_context.append(
                    {
                        "source_object_id": mesh["source_object_id"],
                        "component_id": part["component_id"],
                        "topology": component_topology(part_vertices, part_triangles),
                    }
                )
    output = {
        "schema_version": "human-review-office-geometry-inspection-v1",
        "status": "DIAGNOSTIC_PROSPECTIVE_SCOPE_NOT_CERTIFIED",
        "gt_used": False,
        "source_sha256": contract.scale.source_asset_sha256,
        "source_evidence_content_sha256": content_sha256(evidence),
        "input_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(ALLOWED)
        },
        "floor_id": "1F",
        "area": "AREA_1F_OFFICE",
        "walkable": "WALK_1F_OFFICE",
        "portal": None,
        "portal_reason": "public reviewed candidates do not require a portal transition",
        "scope_basis": (
            "all public observed projections and all support-eligible public candidate vertices "
            "plus approved body guard; support-failing left route excluded automatically"
        ),
        "prospective_footpoint_bounds_bu": [
            low_xy.tolist() + [support_z],
            high_xy.tolist() + [support_z],
        ],
        "prospective_footpoint_bounds_m": [
            (low_xy * ratio).tolist() + [support_z * ratio],
            (high_xy * ratio).tolist() + [support_z * ratio],
        ],
        "body_envelope_bounds_bu": [envelope_low.tolist(), envelope_high.tolist()],
        "body_envelope_bounds_m": [
            (envelope_low * ratio).tolist(),
            (envelope_high * ratio).tolist(),
        ],
        "body_policy_m": {"radius": 0.3, "height": 1.7, "clearance": 0.05, "contact": 0.001},
        "source_triangles_selected_by_envelope": selected,
        "legal_actual_support_triangles": legal_support,
        "findings": findings,
        "paths": paths,
        "certificate_result": certificate_result,
        "certificate_generated": certificate is not None,
        "enclosure_witness_bu": center.tolist(),
        "enclosing_context_components": enclosing_context,
        "enclosure": {
            "source_object_id": "group_0",
            "component_id": "component-00000000",
            "bounds_bu": component["bounds_bu"],
            "full_component_approval_requested": False,
            "current_semantics": "UNKNOWN_SOLID_INTERIOR_OR_SOURCE_SURFACE",
        },
        "limitations": [
            "Prospective foot coordinates require the separate landmark/floor binding decision.",
            "Exact zero area is machine determined; whether these seams have physical ownership "
            "is human semantics.",
            "The original strict certificate rejects degenerate source context and unknown "
            "component enclosure. An additive reviewed-scope certifier is prepared but unapplied.",
            "APPROVE never sets certificate=PASS. The bound human receipt and original-source "
            "exhaustive support/body/clearance/enclosure checks must still run.",
            "Configured direct/left/right routes do not prove school topology, Case 1 uniqueness "
            "or Case 2 independent branch diversity.",
        ],
    }
    (ROOT / "human_review/geometry_evidence.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
    )
    print(
        json.dumps(
            {
                "findings": len(findings),
                "selected": selected,
                "certificate_reason": certificate_result.get("reason"),
                "finding_faces": sorted(
                    {(r["source_object_id"], r["source_face_index"]) for r in findings}
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
