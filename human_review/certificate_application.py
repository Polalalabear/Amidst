"""Apply an explicit completed HR-01 decision to the exact bounded office proposal.

No callable in this module starts formal inference or edits a source scene. The
calling decision pipeline must require a completed explicit APPROVE first.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import box

from amidst.local_semantic_review import (
    ScopedSourceSurfaceReview,
    regenerate_reviewed_certificate,
)
from amidst.obstacle_volume_authority import content_sha256, validate_source_evidence
from amidst.physical_collision import CollisionNumerics
from amidst.physical_policy_contract import load_physical_policy_contract
from amidst.scene_geometry import Coordinate, FloorAuthority, GeometrySurface
from amidst.walkable_clearance import WalkableClearanceDomain

PHYSICAL = "data/scene_audit/phase1_physical_policy_approval_20261006"
PUBLIC = "data/finalization/local_run/diagnostics/office/policy_graph_primary"
REQUIRED_INPUTS = frozenset(
    {
        f"{PHYSICAL}/source_evidence.json.gz",
        f"{PHYSICAL}/floor_support_details.json.gz",
        f"{PUBLIC}/candidates.json",
        f"{PUBLIC}/projected_frames.json",
        "configs/physical_collision_numerics_v1.json",
    }
)


def _verified_inputs(repo_root: Path, geometry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    hashes = geometry["input_hashes"]
    if set(hashes) != REQUIRED_INPUTS:
        raise ValueError("reviewed geometry input paths differ from the public evidence allowlist")
    inputs = {}
    for relative in sorted(REQUIRED_INPUTS):
        path = repo_root / relative
        if not path.resolve().is_relative_to(repo_root.resolve()):
            raise ValueError("reviewed geometry input escaped its repository root")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != hashes[relative]:
            raise ValueError(f"reviewed geometry input SHA-256 mismatch: {relative}")
        value = json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)
        if not isinstance(value, dict):
            raise ValueError("reviewed geometry input must be a JSON object")
        inputs[relative] = value
    return inputs


def regenerate_from_completed_review(
    repo_root: Path,
    geometry_evidence: dict[str, Any],
    approved_geometry_option: str,
    receipt_id: str,
    human_decisions_sha256: str,
) -> dict[str, Any]:
    """Return JSON-ready certificate/result/declaration after an explicit APPROVE.

    Recomputes the exact office proposal solely from the hash-bound public graph,
    projected observations, actual approved floor support and body policy. Human
    decisions cannot move the scope, change a threshold or waive nonzero geometry.
    """
    if approved_geometry_option not in (
        "LOCAL_SOURCE_SURFACE_ONLY",
        "EXACT_DERIVED_SURFACE_REPAIR",
    ):
        raise ValueError("an explicit approved geometry semantics option is required")
    geometry = geometry_evidence
    if (
        geometry["schema_version"] != "human-review-office-geometry-inspection-v1"
        or geometry["gt_used"] is not False
        or geometry["floor_id"] != "1F"
        or geometry["area"] != "AREA_1F_OFFICE"
        or geometry["walkable"] != "WALK_1F_OFFICE"
        or geometry["portal"] is not None
    ):
        raise ValueError("reviewed proposal differs from the exact bounded office scope")
    inputs = _verified_inputs(repo_root, geometry)
    evidence = inputs[f"{PHYSICAL}/source_evidence.json.gz"]
    support = inputs[f"{PHYSICAL}/floor_support_details.json.gz"]
    contract = load_physical_policy_contract(
        repo_root / "configs/physical_policy_runtime_school_v3.json"
    )
    validate_source_evidence(evidence, expected_source_sha256=contract.scale.source_asset_sha256)
    if (
        geometry["source_sha256"] != evidence["source_sha256"]
        or geometry["source_evidence_content_sha256"] != content_sha256(evidence)
        or support["source_sha256"] != evidence["source_sha256"]
    ):
        raise ValueError("reviewed source/evidence/support authority binding changed")
    office = next(
        row for row in support["walkable_reviews"] if row["walkable_id"] == "WALK_1F_OFFICE"
    )
    floor = FloorAuthority.model_validate_json(
        json.dumps(next(row for row in support["floor_authorities"] if row["floor_id"] == "1F"))
    )
    surfaces = tuple(
        GeometrySurface.model_validate_json(json.dumps(row)) for row in support["support_surfaces"]
    )
    domain = WalkableClearanceDomain.from_surfaces(
        tuple(row for row in surfaces if row.surface_id in office["support_surface_ids"]),
        floor=floor,
        scale=contract.scale,
        policy=contract.policy,
        expected_source_sha256=contract.scale.source_asset_sha256,
    )
    support_z = float(office["source_support_height_bu"])
    candidates = [
        row
        for result in inputs[f"{PUBLIC}/candidates.json"]["results"]
        for row in result["candidates"]
    ]
    eligible_points = []
    for candidate in candidates:
        foot: tuple[Coordinate, ...] = tuple(
            (float(p[0]), float(p[1]), support_z) for p in candidate["polyline"]
        )
        if all(domain.validate_segment(a, b).valid for a, b in zip(foot, foot[1:], strict=False)):
            eligible_points.extend(candidate["polyline"])
    eligible_points.extend(
        row["projected_point"]["world_position"]
        for row in inputs[f"{PUBLIC}/projected_frames.json"]["dataset"]["samples"]
        if row.get("projected_point") is not None
    )
    if not eligible_points:
        raise ValueError("reviewed office has no public projected/candidate locations")
    points = np.asarray(eligible_points)
    low_xy, high_xy = points[:, :2].min(axis=0), points[:, :2].max(axis=0)
    foot_bounds = [low_xy.tolist() + [support_z], high_xy.tolist() + [support_z]]
    if geometry["prospective_footpoint_bounds_bu"] != foot_bounds:
        raise ValueError("reviewed footpoint bounds differ from public evidence reconstruction")
    rectangle = box(*low_xy, *high_xy)
    band = domain.actual_contact_height_band(rectangle)
    if band is None:
        raise ValueError("reviewed office has no actual source contact-height band")
    guard = contract.footprint_radius_bu
    extra = contract.scale.to_blender_units(contract.parameter("body_clearance_m"))
    envelope = [
        [float(low_xy[0] - guard), float(low_xy[1] - guard), float(band[0] - extra)],
        [
            float(high_xy[0] + guard),
            float(high_xy[1] + guard),
            float(
                band[1]
                + contract.scale.to_blender_units(
                    contract.parameter("body_height_m") + contract.parameter("body_clearance_m"),
                )
            ),
        ],
    ]
    if geometry["body_envelope_bounds_bu"] != envelope:
        raise ValueError("reviewed body bounds differ from actual source/body guard")
    if geometry["enclosure"]["source_object_id"] != "group_0" or (
        geometry["enclosure"]["component_id"] != "component-00000000"
        or geometry["enclosure"]["full_component_approval_requested"] is not False
    ):
        raise ValueError("reviewed component differs from the bounded source surface proposal")
    findings = geometry["findings"]
    if {(row["source_object_id"], row["source_face_index"]) for row in findings} != {
        ("group_0", 1975),
        ("group_0", 2398),
    }:
        raise ValueError("reviewed source faces differ from the two exact zero-area seams")
    mesh = next(row for row in evidence["meshes"] if row["source_object_id"] == "group_0")
    for row in findings:
        index = row["source_triangle_index"]
        original = [mesh["vertices"][v] for v in mesh["triangles"][index]]
        if (
            row["source_mesh_id"] != mesh["mesh_id"]
            or row["source_geometry_sha256"] != mesh["geometry_sha256"]
            or mesh["triangle_source_face_indices"][index] != row["source_face_index"]
            or row["triangle_bu"] != original
        ):
            raise ValueError("reviewed evaluated source face/triangle/mesh provenance differs")
    payload = {
        "decision_id": "HR-01",
        "decision": "APPROVE",
        "decision_option": approved_geometry_option,
        "human_approval_id": receipt_id,
        "human_decisions_sha256": human_decisions_sha256,
        "source_sha256": evidence["source_sha256"],
        "evidence_content_sha256": content_sha256(evidence),
        "source_mesh_id": mesh["mesh_id"],
        "source_geometry_sha256": mesh["geometry_sha256"],
        "source_object_id": "group_0",
        "source_component_id": "component-00000000",
        "region_id": "BODY:WALK_1F_OFFICE",
        "body_envelope_bounds_bu": envelope,
        "zero_area_source_face_indices": [1975, 2398],
    }
    declaration = ScopedSourceSurfaceReview.model_validate_json(json.dumps(payload))
    source_faces = frozenset(
        (surface.source_object_id, face)
        for surface in surfaces
        if "1F" in surface.floor_ids
        for face in surface.source_face_indices
    )
    certificate, result = regenerate_reviewed_certificate(
        declaration,
        evidence,
        domain,
        rectangle,
        "BODY:WALK_1F_OFFICE",
        contract,
        CollisionNumerics.model_validate(inputs["configs/physical_collision_numerics_v1.json"]),
        support_source_faces=source_faces,
        expected_receipt_content_sha256=content_sha256(declaration.model_dump(mode="json")),
        expected_human_decisions_sha256=human_decisions_sha256,
        expected_evidence_content_sha256=content_sha256(evidence),
    )
    return {
        "certificate": None if certificate is None else certificate.model_dump(mode="json"),
        "result": result,
        "declaration": declaration.model_dump(mode="json"),
    }
