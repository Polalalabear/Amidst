"""Export only GT-free metadata from an existing bounded Blender pilot.

This preparation stage may inspect the combined export container; downstream
consumers receive only observations and the strict context emitted here. No GT
positions, route waypoints, sample depth or visibility-derived 3D truth is copied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from amidst.datasets.pilot import PilotInferenceContext
from amidst.domain.evidence import ObservationFrame

LABEL = "PILOT / SYNTHETIC SAMPLE"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _verify_asset(path: Path, digest: str, size: int, mtime_ns: int) -> None:
    stat = path.stat()
    if (sha256(path), stat.st_size, stat.st_mtime_ns) != (digest, size, mtime_ns):
        raise ValueError("pilot source asset hash/size/mtime differs from its export")


def prepare_context(
    dataset_path: Path,
    observations_path: Path,
    semantic_audit_path: Path,
    output: Path,
    *,
    zone_id: str = "AREA_1F_OFFICE",
    walkable_id: str = "WALK_1F_OFFICE",
) -> PilotInferenceContext:
    """Allowlist source/calibration/independently configured plane metadata only."""
    if output.exists():
        raise FileExistsError(output)
    dataset = json.loads(dataset_path.read_text())
    observations = json.loads(observations_path.read_text())
    audit = json.loads(semantic_audit_path.read_text())
    if dataset.get("label") != LABEL or observations.get("label") != LABEL:
        raise ValueError("inputs must be PILOT / SYNTHETIC SAMPLE")
    if observations.get("data_kind") != "SYNTHETIC":
        raise ValueError("only synthetic pilot evidence is supported")
    if set(observations) != {
        "data_kind", "label", "source_asset_sha256", "frames", "site_id",
    }:
        raise ValueError("pilot observation container contains unsupported fields")
    frames = tuple(ObservationFrame.model_validate(row) for row in observations["frames"])
    source = dataset["source_scene"]
    digest = source["sha256_before"]
    if digest != source["sha256_after"] or digest != observations["source_asset_sha256"]:
        raise ValueError("pilot observations/source identities differ")
    if dataset.get("site_id") != observations["site_id"]:
        raise ValueError("pilot metadata and observation site differ")
    primary = Path(source["path"])
    _verify_asset(primary, digest, source["size_before"], source["mtime_ns_before"])
    lineage = dataset["source_lineage"]
    original = Path(lineage["original_source_path"])
    _verify_asset(
        original, lineage["original_source_sha256"], lineage["original_source_size"],
        lineage["original_source_mtime_ns"],
    )
    if (
        lineage.get("original_source_identity_verified") is not True
        or lineage.get("wall_semantic_marking_policy")
        != "ANNOTATION_ONLY_PHYSICAL_ROLE_NOT_APPROVED"
        or audit["source_sha256"] != lineage["original_source_sha256"]
    ):
        raise ValueError("semantic metadata must bind the preserved original source")
    objects = {row["id"]: row for row in audit["geometry_objects"]}
    area, walkable = objects[zone_id], objects[walkable_id]
    if (
        area["kind"] != "AREA" or walkable["kind"] != "WALKABLE"
        or area["floor"] != walkable["floor"]
    ):
        raise ValueError("local envelope requires matching AREA/WALKABLE floor metadata")
    # The static landmark plane is independently mesh-probed metadata, never a
    # fit to hidden GT positions. Its diagnostic authority remains explicit.
    trajectory_metadata = dataset["trajectory"]
    basis = trajectory_metadata["projection_plane_basis"]
    if (
        basis["purpose"] != "PILOT_DIAGNOSTIC_ONLY"
        or basis["source_asset_sha256"] != digest
    ):
        raise ValueError("projection plane requires a source-bound independent diagnostic basis")
    plane_z = float(basis["physical_floor_z"]) + float(basis["foot_clearance_units"]) + float(
        basis["landmark_offset_units"]
    )
    if not math.isfinite(plane_z) or not math.isclose(
        plane_z, trajectory_metadata["observation_plane_z"], rel_tol=0, abs_tol=1e-9,
    ):
        raise ValueError("declared static plane differs from independent mesh metadata")
    camera_ids = {frame.camera_id for frame in frames}
    cameras = [row for row in dataset["cameras"] if row["camera_id"] in camera_ids]
    if len(cameras) != len(camera_ids):
        raise ValueError("all observed cameras require source calibration")
    site_id = observations["site_id"]
    context = PilotInferenceContext.model_validate({
        "label": LABEL, "data_kind": "SYNTHETIC", "site_id": site_id,
        "source_id": f"pilot_blender:{site_id}",
        "spatial_context_id": f"PILOT_SCHOOL_V3_{site_id.upper()}",
        "source_asset_sha256": digest,
        "observations_sha256": sha256(observations_path),
        "cameras": cameras,
        "plane": {
            "plane_id": f"PILOT_{site_id.upper()}_STATIC_LANDMARK_PLANE",
            "point": [0.0, 0.0, plane_z], "normal": [0.0, 0.0, 1.0],
            "floor_id": area["floor"], "zone_id": zone_id,
        },
        "zone": {
            "floor_id": area["floor"], "zone_id": zone_id,
            "walkable_object_id": walkable_id,
            "bounds_min": area["bounds"][0], "bounds_max": area["bounds"][1],
            "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL",
        },
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(context.model_dump_json(indent=2) + "\n")
    # Container digest is export audit evidence, deliberately outside inference
    # context so changing GT cannot influence graph IDs, routes or ordering.
    output.with_name("preparation_manifest.json").write_text(json.dumps({
        "label": LABEL, "stage": "EXPORT_METADATA_PREPARATION_ONLY",
        "source_dataset_sha256": sha256(dataset_path),
        "observations_sha256": context.observations_sha256,
        "semantic_audit_sha256": sha256(semantic_audit_path),
        "context_sha256": sha256(output),
        "original_source_sha256": lineage["original_source_sha256"],
        "derived_source_sha256": digest,
        "independent_plane_basis": basis,
        "zone_geometry_authority": "ANNOTATION_AABB_ONLY_PROVISIONAL",
        "walkable_polygon_or_collision_certified": False,
        "gt_positions_or_plan_waypoints_exported": False,
        "physical_scale_authority": "UNVERIFIED",
        "consumer_inputs": ["observations.json", "projection_context.json"],
    }, indent=2, allow_nan=False) + "\n")
    return context


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--semantic-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    context = prepare_context(
        args.dataset, args.observations, args.semantic_audit, args.output,
    )
    print(f"PILOT_CONTEXT_READY {context.site_id}: {args.output}")


if __name__ == "__main__":
    main()
