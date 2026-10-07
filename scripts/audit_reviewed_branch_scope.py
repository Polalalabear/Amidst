"""Reproduce a bounded, GT-free candidate audit; no new authority is applied."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
from typing import Any

from amidst.finalization.reviewed_authority import load_reviewed_authority
from amidst.finalization.scope_inventory import (
    audit_approved_island_candidates,
    audit_two_sided_source_candidates,
)
from amidst.scene_geometry import GeometrySurface
from amidst.simulation.camera_calibration import load_camera_calibration_json
from amidst.walkable_clearance import WalkableClearanceDomain


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path: Path, value: Any) -> None:
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application", type=Path,
                        default=root / "data/finalization/human_review_applied_v1")
    parser.add_argument("--source-catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.application = args.application.resolve()
    args.source_catalog = args.source_catalog.resolve()
    args.output = args.output.resolve()
    if args.output.exists():
        raise FileExistsError("candidate audit output must be fresh")
    authority = load_reviewed_authority(args.application, repo_root=root)
    catalog = load_camera_calibration_json(args.source_catalog)
    if catalog.source_asset_sha256 != authority.source_sha256:
        raise ValueError("candidate camera catalog source differs from reviewed source")
    directory = root / "data/scene_audit/phase1_physical_policy_approval_20261006"
    source, obstacle_path = directory / "source_evidence.json.gz", (
        directory / "obstacle_collider_authority.json"
    )
    support_path = directory / "floor_support_details.json.gz"
    native_offset = authority.historical_context.plane.point[2] - authority.floor_support_z_bu
    islands = audit_approved_island_candidates(
        authority.provider, obstacle_path, source, authority.historical_context.cameras,
        expected_obstacle_authority_file_sha256=digest(obstacle_path),
        floor_support_z_bu=authority.floor_support_z_bu,
        proposed_landmark_offset_bu=native_offset,
    )
    support = json.loads(gzip.decompress(support_path.read_bytes()))
    if support["source_sha256"] != authority.source_sha256:
        raise ValueError("branch support evidence source differs")
    surfaces = tuple(GeometrySurface.model_validate_json(json.dumps(row))
                     for row in support["support_surfaces"] if row["floor_ids"] == ["1F"])
    domain = WalkableClearanceDomain.from_surfaces(
        surfaces, floor=authority.provider.domain.floor, scale=authority.provider.contract.scale,
        policy=authority.provider.contract.policy, expected_source_sha256=authority.source_sha256,
    )
    bypass = audit_two_sided_source_candidates(
        islands, domain, tuple(row.camera for row in catalog.cameras),
        floor_support_z_bu=authority.floor_support_z_bu,
        proposed_landmark_offset_bu=native_offset,
    )
    representatives = []
    for role in sorted({row["obstacle_id"] for row in bypass["candidates"]}):
        candidates = [row for row in bypass["candidates"] if row["obstacle_id"] == role]
        candidate = min(candidates, key=lambda row: (
            not row["two_distinct_cameras_match"], len(row["support_fail_reasons"]),
            row["component"], row["axis"],
        ))
        source_component = candidate["source_component"]
        faces = source_component["source_face_indices"]
        representatives.append({
            "obstacle_id": role, "component": candidate["component"], "axis": candidate["axis"],
            "source_mesh_id": source_component["source_mesh_id"],
            "source_geometry_sha256": source_component["source_geometry_sha256"],
            "source_bounds_bu": source_component["source_bounds_bu"],
            "source_face_count": len(faces),
            "source_face_indices_content_sha256": hashlib.sha256(json.dumps(
                faces, separators=(",", ":"), allow_nan=False,
            ).encode()).hexdigest(),
            "source_face_indices_first_16": faces[:16],
            "proposed_route_footpoints_bu": candidate["routes"],
            "support_all_segments_pass": candidate["support_all_segments_pass"],
            "support_fail_reasons": candidate["support_fail_reasons"],
            "departure_source_cameras_in_frustum": candidate["start_cameras_in_frustum"],
            "recovery_source_cameras_in_frustum": candidate["end_cameras_in_frustum"],
            "source_occlusion": "NOT_RUN", "scope_body_authority": "HUMAN_REVIEW",
            "new_camera_landmark_binding": "HUMAN_REVIEW",
            "free_space_certificate": "NOT_CERTIFIED",
        })
    summary = {
        "schema_version": "phase1-branch-candidate-audit-summary-v1",
        "status": bypass["status"], "source_sha256": authority.source_sha256,
        "source_camera_count": len(catalog.cameras),
        "source_camera_catalog_content_sha256": catalog.calibration_content_sha256,
        "approved_1f_closed_component_count": islands["approved_floor_component_count"],
        "approved_obstacle_role_count": islands["approved_obstacle_role_count"],
        "original_office_cameras_exclude_all_local_component_boxes": all(
            row["both_local_source_camera_views_impossible"] for row in islands["candidates"]
        ),
        "minimum_office_return_route_length_lower_bound_m": min(
            row["office_to_island_and_return_length_lower_bound_m"]
            for row in islands["candidates"]
        ),
        "maximum_office_direct_detour_budget_m": islands["candidates"][0][
            "maximum_current_domain_direct_detour_budget_m"
        ],
        "configured_candidate_count": bypass["configured_candidate_count"],
        "candidate_family": bypass["candidate_family"],
        "candidate_margin_bu": domain.required_clearance_bu + .5,
        "support_pass_count": bypass["support_pass_count"],
        "source_camera_fov_pair_count": bypass["source_camera_fov_pair_count"],
        "combined_support_and_camera_fov_pair_count": bypass[
            "combined_support_and_camera_fov_pair_count"
        ],
        "global_exhaustive_branch_search": False,
        "scope_extended": False, "human_approval_applied": False,
        "original_hr01_hr04_approvals_remain_valid": True,
        "ground_truth_read": False,
        "precise_blocker": (
            "NO_CONFIGURED_TWO_SIDED_SOURCE_ISLAND_BYPASS_IN_APPROVED_CONTACT_DOMAIN"
        ),
        "representative_source_candidates": representatives,
    }
    args.output.mkdir(parents=True)
    write(args.output / "approved_island_candidates.json", islands)
    write(args.output / "two_sided_source_candidates.json", bypass)
    write(args.output / "candidate_audit_summary.json", summary)
    inputs = (source, support_path, obstacle_path, args.source_catalog)
    artifacts = tuple({"path": path.name, "sha256": digest(path), "bytes": path.stat().st_size}
                      for path in sorted(args.output.iterdir()))
    manifest = {
        "schema_version": "phase1-branch-scope-audit-manifest-v1",
        "status": "DIAGNOSTIC_READ_ONLY_NO_AUTHORITY_APPLIED",
        "artifacts": artifacts,
        "input_files": tuple({"path": str(path.relative_to(root)), "sha256": digest(path),
                              "bytes": path.stat().st_size} for path in inputs),
        "reproduce_entry": "UV_CACHE_DIR=/private/tmp/amidst-finalization-uv-cache "
        "uv run python scripts/audit_reviewed_branch_scope.py "
        "--source-catalog data/finalization/reviewed_route_inventory_v1/source_camera_catalog.json "
        "--output <fresh-local-output>",
        "source_camera_extraction": "amidst.simulation.camera_calibration."
        "read_camera_calibration_catalog(source, expected_count=29); unsaved Blender process, "
        "source SHA-256/size/mtime checked before and after",
        "producer_hashes": {str(path.relative_to(root)): digest(path) for path in (
            Path(__file__).resolve(), root / "src/amidst/finalization/scope_inventory.py",
        )},
    }
    write(args.output / "manifest.json", manifest)
    print(json.dumps({key: value for key, value in summary.items()
                      if key != "representative_source_candidates"}, sort_keys=True))


if __name__ == "__main__":
    main()
