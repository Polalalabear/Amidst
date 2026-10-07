"""Discover an unapproved, source-supported local island; never apply authority."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import numpy as np
from shapely.geometry import LineString

from amidst.domain.common import Vec3
from amidst.finalization.reviewed_authority import load_reviewed_authority
from amidst.finalization.source_branch_discovery import propose_source_island
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_collision import CollisionNumerics
from amidst.simulation.camera_calibration import load_camera_calibration_json
from amidst.simulation.observation_export import blender_ray_queries
from amidst.simulation.virtual_camera import project_world


def fingerprint(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stat = path.stat()
    return {"sha256": digest, "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def probe_visibility(proposal: dict[str, Any], catalog: Any, source: Path,
                     blender: str, sample_count: int) -> dict[str, Any]:
    """Fixed-frame source ray queries, not a simulation/inference dataset."""
    if not 3 <= sample_count <= 101:
        raise ValueError("geometric visibility audit requires 3..101 bounded samples per side")
    camera_ids = sorted({value for pair in proposal["distinct_source_camera_fov_pairs"]
                         for value in pair})
    cameras = {row.camera.camera_id: row.camera for row in catalog.cameras
               if row.camera.camera_id in camera_ids}
    rows = []
    queries: list[tuple[Vec3, Vec3]] = []
    for route_index, route in enumerate(proposal["two_sided_routes_bu"]):
        line = LineString([point[:2] for point in route])
        for index in range(sample_count):
            point = line.interpolate(index / (sample_count - 1), normalized=True)
            marker: Vec3 = (float(point.x), float(point.y),
                            route[0][2] + proposal["proposed_landmark_offset_bu"])
            for camera_id in camera_ids:
                camera = cameras[camera_id]
                origin = cast(
                    Vec3, tuple(float(v) for v in np.asarray(camera.camera_to_world)[:3, 3]),
                )
                projection = project_world(camera, marker)
                rows.append({"route_index": route_index, "sample_index": index,
                             "arc_fraction": index / (sample_count - 1),
                             "camera_id": camera_id, "marker_position_bu": marker,
                             "source_projection": projection.model_dump(mode="json")})
                queries.append((origin, marker))
    answers = blender_ray_queries(tuple(queries), blend_path=source, blender_binary=blender)
    for row, answer in zip(rows, answers, strict=True):
        row["source_ray_result"] = asdict(answer)
        row["visible"] = row["source_projection"]["in_frustum"] and not answer.occluded
    pairs = []
    for departure, recovery in proposal["distinct_source_camera_fov_pairs"]:
        routes = []
        for route_index in range(2):
            selected = [row for row in rows if row["route_index"] == route_index
                        and row["camera_id"] in (departure, recovery)]
            jointly_blind = [index for index in range(sample_count) if all(
                not row["visible"] for row in selected if row["sample_index"] == index
            )]
            first_visible = any(row["visible"] for row in selected if row["sample_index"] == 0
                                and row["camera_id"] == departure)
            last_visible = any(row["visible"] for row in selected
                               if row["sample_index"] == sample_count - 1
                               and row["camera_id"] == recovery)
            routes.append({"route_index": route_index,
                           "departure_source_visible": first_visible,
                           "recovery_source_visible": last_visible,
                           "jointly_blind_geometric_sample_indices": jointly_blind,
                           "sampled_visible_gap_visible": first_visible and last_visible
                           and any(0 < index < sample_count - 1 for index in jointly_blind)})
        pairs.append({"camera_pair": (departure, recovery), "routes": routes,
                      "both_sides_sampled_visible_gap_visible": all(
                          row["sampled_visible_gap_visible"] for row in routes)})
    return {"schema_version": "source-branch-geometric-visibility-v1",
            "status": "DIAGNOSTIC_FIXED_FRAME_SOURCE_QUERY",
            "source_saved": False, "rendered": False, "ground_truth_read": False,
            "timestamp_schedule_or_dataset_generated": False,
            "sampling_policy": "EQUAL_ROUTE_ARC_FRACTION_NO_TIMESTAMPS",
            "sample_count_per_side": sample_count, "samples": rows, "camera_pairs": pairs,
            "formal_visible_gap_visible": "NOT_PROVEN_REQUIRES_FROZEN_FRESH_EXPORT",
            "continuous_visibility_between_queries": "NOT_CLAIMED"}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--application", type=Path,
                        default=root / "data/finalization/human_review_applied_v1")
    parser.add_argument("--evidence-directory", type=Path,
                        default=root / "data/scene_audit/phase1_physical_policy_approval_20261006")
    parser.add_argument("--source-catalog", type=Path,
                        default=root / "data/finalization/reviewed_route_inventory_v1/"
                        "source_camera_catalog.json")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--obstacle-id", default="OBSTACLE_1F_CORRIDOR_01_02")
    parser.add_argument("--support-source-object", default="group_0")
    parser.add_argument("--island-source-object", action="append", default=[])
    parser.add_argument("--additional-support-source-object", action="append", default=[])
    parser.add_argument("--same-side-endpoints-x-bu", type=float, nargs=2)
    parser.add_argument("--east-return-endpoints-xy-bu", type=float, nargs=4)
    parser.add_argument("--east-return-turn-x-bu", type=float)
    parser.add_argument("--camera-id", action="append", default=[])
    parser.add_argument("--endpoint-extension-bu", type=float, default=0.)
    parser.add_argument("--body-region", default="BODY:WALK_1F_CORRIDOR_01")
    parser.add_argument("--blender", default=None,
                        help="Optional read-only actual-source fixed-frame visibility probe")
    parser.add_argument("--visibility-samples", type=int, default=41)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("source branching discovery output must be fresh")
    authority = load_reviewed_authority(args.application.resolve(), repo_root=root)
    source = args.source.resolve()
    before = fingerprint(source)
    if before["sha256"] != authority.source_sha256 or before["bytes"] != 468300506:
        raise ValueError("original source differs from reviewed source SHA/size")
    directory = args.evidence_directory.resolve()
    evidence_path = directory / "source_evidence.json.gz"
    floor_path = directory / "floor_support_details.json.gz"
    geometry_path = directory / "geometry.json.gz"
    obstacle_path = directory / "obstacle_collider_authority.json"
    evidence = json.loads(gzip.decompress(evidence_path.read_bytes()))
    floor = json.loads(gzip.decompress(floor_path.read_bytes()))
    geometry = json.loads(gzip.decompress(geometry_path.read_bytes()))
    if any(row["source_sha256"] != authority.source_sha256 for row in (floor, geometry)):
        raise ValueError("actual source geometry/support binding differs")
    catalog = load_camera_calibration_json(args.source_catalog)
    if catalog.source_asset_sha256 != authority.source_sha256:
        raise ValueError("source camera catalog binding differs")
    if args.camera_id and (len(args.camera_id) != len(set(args.camera_id)) or not set(
        args.camera_id).issubset({row.camera.camera_id for row in catalog.cameras})
    ):
        raise ValueError("discovery cameras must be distinct actual source catalog identities")
    numerics_path = root / "configs/physical_collision_numerics_v1.json"
    numerics = CollisionNumerics.model_validate_json(numerics_path.read_bytes())
    proposal = propose_source_island(
        evidence, json.loads(obstacle_path.read_bytes()), authority.provider.contract, numerics,
        tuple(row.camera for row in catalog.cameras
              if not args.camera_id or row.camera.camera_id in args.camera_id),
        obstacle_id=args.obstacle_id,
        support_source_object_id=args.support_source_object,
        floor_z_bu=authority.floor_support_z_bu,
        source_body_region_id=args.body_region,
        landmark_offset_bu=authority.historical_context.plane.point[2]
        - authority.floor_support_z_bu,
        additional_source_object_ids=tuple(args.island_source_object),
        endpoint_extension_bu=args.endpoint_extension_bu,
        additional_support_source_object_ids=tuple(args.additional_support_source_object),
        same_side_endpoint_x_bu=None if args.same_side_endpoints_x_bu is None else tuple(
            args.same_side_endpoints_x_bu),
        east_return_endpoints_xy_bu=None if args.east_return_endpoints_xy_bu is None else tuple(
            args.east_return_endpoints_xy_bu),
        east_return_turn_x_bu=args.east_return_turn_x_bu,
    )
    proposal["actual_floor_support_evidence_content_sha256"] = content_sha256(floor)
    proposal["source_geometry_evidence_content_sha256"] = content_sha256(geometry)
    proposal["source_camera_catalog_content_sha256"] = catalog.calibration_content_sha256
    camera_export = {"source_sha256": authority.source_sha256,
                     "cameras": [row["actual_source_camera"]
                                 for row in proposal["source_camera_endpoint_projections"]]}
    proposal["actual_source_camera_export_content_sha256"] = content_sha256(camera_export)
    output.mkdir(parents=True)
    write(output / "source_supported_proposal.json", proposal)
    write(output / "actual_source_cameras.json", camera_export)
    visibility = None
    try:
        if args.blender:
            visibility = probe_visibility(proposal, catalog, source, args.blender,
                                          args.visibility_samples)
            write(output / "source_visibility.json", visibility)
    finally:
        after = fingerprint(source)
        write(output / "source_preservation.json", {
            "before": before, "after": after, "unchanged": before == after,
            "source_saved": False, "source_geometry_modified": False,
        })
        if after != before:
            raise RuntimeError("immutable source changed during discovery")
    inputs = (evidence_path, floor_path, geometry_path, obstacle_path,
              args.source_catalog.resolve(), numerics_path)
    manifest = {
        "schema_version": "source-branch-discovery-artifact-manifest-v1",
        "status": "PROPOSED_NO_AUTHORITY_APPLIED" if proposal["status"] == "PROPOSED"
        else "DISCOVERY_BLOCKED",
        "artifacts": [{"path": path.name, **fingerprint(path)}
                      for path in sorted(output.iterdir())],
        "inputs": [{"path": str(path.relative_to(root)), **fingerprint(path)} for path in inputs],
        "producer_files": [{"path": str(path.relative_to(root)), **fingerprint(path)}
                           for path in (Path(__file__).resolve(), root / "src/amidst/finalization/"
                                        "source_branch_discovery.py")],
        "source": before, "authority_applied": False, "ground_truth_read": False,
        "source_saved": False, "new_floor_and_camera_bindings": "HUMAN_REVIEW",
        "formal_readiness": False,
        "source_visibility_query_completed": visibility is not None,
        "reproduce_entry": "uv run python scripts/discover_source_branch_scope.py "
        "--source <hash-matching-school_v3.blend> --output <fresh-local-output> "
        "[--blender <Blender-executable>]",
    }
    write(output / "manifest.json", manifest)
    print(json.dumps({"status": proposal["status"], "output": str(output),
                      "common_endpoints_bu": proposal["common_endpoints_bu"],
                      "source_camera_fov_pairs": proposal["distinct_source_camera_fov_pairs"],
                      "formal_readiness": False}, sort_keys=True))


if __name__ == "__main__":
    main()
