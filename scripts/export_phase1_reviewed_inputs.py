"""Fresh reviewed source export using the existing Blender camera and raycaster.

This producer reads frozen simulation recipes. Its strict inference payload retains
the legacy computational schema; reviewed authority lives in a separate manifest.
Visibility and case acceptance are measured afterwards, never forced by this tool.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def sample_waypoints(waypoints: list[dict[str, Any]], timestamp: float) -> list[float]:
    """Inclusive piecewise-linear sampling; no extrapolation or rejection."""
    if len(waypoints) < 2 or any(
        after["timestamp"] <= before["timestamp"]
        for before, after in zip(waypoints[:-1], waypoints[1:], strict=True)
    ):
        raise ValueError("strictly increasing simulation waypoints are required")
    if not waypoints[0]["timestamp"] <= timestamp <= waypoints[-1]["timestamp"]:
        raise ValueError("sampling outside the exact recipe extent is forbidden")
    for before, after in zip(waypoints[:-1], waypoints[1:], strict=True):
        if before["timestamp"] <= timestamp <= after["timestamp"]:
            fraction = (timestamp - before["timestamp"]) / (
                after["timestamp"] - before["timestamp"]
            )
            return [float(a + fraction * (b - a))
                    for a, b in zip(before["position"], after["position"], strict=True)]
    raise ValueError("timestamp has no recipe segment")


def inclusive_timestamps(start: float, end: float, fps: int) -> list[float]:
    if fps != 5 or start < 0 or end <= start:
        raise ValueError("reviewed schedule requires 5 Hz and positive exact extent")
    first, last = round(start * fps), round(end * fps)
    if not math.isclose(first / fps, start, abs_tol=1e-12) or not math.isclose(
        last / fps, end, abs_tol=1e-12,
    ):
        raise ValueError("source endpoints must lie on the locked sampling grid")
    return [index / fps for index in range(first, last + 1)]


def export(config_path: Path, application: Path, output: Path) -> dict[str, Any]:
    import bpy  # type: ignore[import-not-found]  # Blender embedded Python only.
    from mathutils import Matrix  # type: ignore[import-not-found]  # Blender embedded Python only.

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "scripts"))
    from export_blender_pilot import annotation_objects, project

    from amidst.simulation.blender_camera import extract_camera_dict
    from amidst.simulation.blender_visibility import BlenderMeshRaycaster

    configuration_document = json.loads(config_path.read_bytes())
    config = configuration_document.get("base_export_config", configuration_document)
    dataset_version = configuration_document.get(
        "dataset_version", config.get("dataset_version", "phase1-reviewed-inputs-v1"),
    )
    receipt = json.loads((application / "review_receipt.json").read_bytes())
    approved = json.loads((application / "approved_input_lock.json").read_bytes())
    manifest = json.loads((application / "manifest.json").read_bytes())
    for artifact in manifest["artifacts"]:
        relative = Path(artifact["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("authority artifact escapes its application directory")
        if digest(application / relative) != artifact["sha256"]:
            raise ValueError("application artifact hash changed")
    if receipt["certificate_status"] != "PASS":
        raise ValueError("reviewed bounded certificate must PASS before export")
    source = Path(bpy.data.filepath)
    before = (digest(source), source.stat().st_size, source.stat().st_mtime_ns)
    if before[:2] != (config["source_sha256"], config["source_size_bytes"]):
        raise ValueError("source differs from the frozen reviewed configuration")
    if before[0] != receipt["source_sha256"]:
        raise ValueError("source differs from the semantic review receipt")
    if config.get("config_locked_before_simulation") is not True:
        raise ValueError("formal settings must be locked before simulation")
    movement_approval = None
    if configuration_document.get("schema_version") == "phase1-reviewed-case-export-v2":
        from amidst.finalization.reviewed_reference_movement import (
            build_reference_annotation_document,
            load_reference_movement_approval,
        )

        encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if hashlib.sha256(encoded.encode()).hexdigest() != configuration_document[
            "base_export_config_content_sha256"
        ]:
            raise ValueError("new export lock differs from frozen source recipes")
        base_path = root / "configs/finalization/reviewed_case_inventory_v1.json"
        if digest(base_path) != configuration_document["base_export_config_file_sha256"] or (
            json.loads(base_path.read_bytes()) != config
        ):
            raise ValueError(
                "movement-only extension must preserve the original source recipe lock",
            )
        movement_approval = load_reference_movement_approval(
            root / configuration_document["reference_movement_approval_receipt_path"],
            root / configuration_document["reference_movement_policy_path"],
            expected_receipt_content_sha256=configuration_document[
                "reference_movement_approval_receipt_content_sha256"],
            expected_source_sha256=before[0], expected_protocol_sha256=config["protocol_sha256"],
            expected_original_human_decisions_sha256=receipt["human_decisions_sha256"],
        )
        if movement_approval.proposal_content_sha256 != configuration_document[
            "reference_movement_policy_content_sha256"
        ]:
            raise ValueError("new export policy differs from the approved movement receipt")
    if output.exists():
        raise FileExistsError("fresh reviewed dataset output required")
    historical_path = root / "data/finalization/local_run/dataset/inference/office/context.json"
    historical = json.loads(historical_path.read_bytes())
    scene = bpy.context.scene
    scene.render.resolution_x = config.get("width", 960)
    scene.render.resolution_y = config.get("height", 540)
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = scene.render.use_crop_to_border = False
    raycaster = BlenderMeshRaycaster(scene, excluded_objects=annotation_objects(bpy, scene))
    if approved["projection_binding"]["conversion"] != "SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY":
        raise ValueError("unsupported reviewed landmark conversion")
    summaries = []
    cases = config["cases"]
    if isinstance(cases, dict):
        cases = [dict(value, case_id=identity) for identity, value in cases.items()]
    for recipe in cases:
        if not recipe.get("waypoints"):
            summaries.append({"case_id": recipe["case_id"], "status": "BLOCKED",
                              "blockers": recipe.get("blockers", [])})
            continue
        identity = recipe["case_id"]
        offset = recipe.get("landmark_offset_bu", config.get("landmark_offset_bu"))
        support_z = recipe.get("support_z_bu", config.get("support_z_bu"))
        if offset is None or support_z is None or not math.isclose(
            historical["plane"]["point"][2] - support_z, offset,
            rel_tol=0, abs_tol=1e-12,
        ):
            raise ValueError("export requires the exact locked source-bound landmark offset")
        camera_ids = recipe.get("camera_ids", [row["camera_id"]
                                               for row in historical["cameras"]])
        cameras = [extract_camera_dict(scene, bpy.data.objects[name])
                   for name in sorted(camera_ids)]
        if cameras != sorted(historical["cameras"], key=lambda row: row["camera_id"]):
            raise ValueError("fresh source cameras differ from the reviewed calibration")
        waypoints = recipe["waypoints"]
        timestamps = inclusive_timestamps(waypoints[0]["timestamp"],
                                          waypoints[-1]["timestamp"], 5)
        frames, truth, visibility = [], [], []
        target_id = "reviewed_" + identity
        for index, timestamp in enumerate(timestamps):
            foot = sample_waypoints(waypoints, timestamp)
            position = [foot[0], foot[1], foot[2] + offset]
            truth.append({"timestamp": timestamp, "position": foot,
                          "landmark_position": position, "floor_id": "1F",
                          "trajectory_id": recipe.get("trajectory_id", identity)})
            for camera in cameras:
                projected = project(camera, position, Matrix)
                reason, occluder = projected["reason"], None
                if reason == "IN_FRUSTUM":
                    matrix = camera["camera_to_world"]
                    ray = raycaster(tuple(matrix[i][3] for i in range(3)), tuple(position))
                    reason, occluder = ray.reason, ray.occluder_id
                observed = reason == "CLEAR"
                frames.append({"frame_id": index, "timestamp": timestamp,
                               "target_id": target_id, "camera_id": camera["camera_id"],
                               "status": "OBSERVED" if observed else "GAP",
                               "point_2d": projected["pixel"] if observed else None,
                               "provenance": "OBSERVED" if observed else None,
                               "gap_reason": None if observed else reason,
                               "occluder_id": occluder, "data_kind": "SYNTHETIC"})
                visibility.append({"frame_id": index, "timestamp": timestamp,
                                   "camera_id": camera["camera_id"], "reason": reason,
                                   "status": "OBSERVED" if observed else "GAP",
                                   "occluder_id": occluder})
        observations = {"label": "PILOT / SYNTHETIC SAMPLE", "data_kind": "SYNTHETIC",
                        "source_asset_sha256": before[0], "site_id": "office", "frames": frames}
        observed_path = output / "inference" / identity / "observations.json"
        write(observed_path, observations)
        context = copy.deepcopy(historical)
        context.update(source_id="reviewed_export:" + identity,
                       spatial_context_id="REVIEWED_LOCAL_OFFICE_" + identity.upper(),
                       observations_sha256=digest(observed_path))
        write(output / "inference" / identity / "context.json", context)
        write(output / "inference" / identity / "visibility.json", visibility)
        write(output / "evaluation" / identity / "ground_truth.json", {
            "source_asset_sha256": before[0], "provenance": "GROUND_TRUTH",
            "trajectory_id": recipe.get("trajectory_id", identity), "target_id": target_id,
            "spatial_context_id": context["spatial_context_id"],
            "coordinate_units": "BLENDER_NATIVE_UNITS", "samples": truth,
            "sample_source": "CONFIGURATION_SAMPLER",
        })
        if movement_approval is not None:
            annotations = build_reference_annotation_document(
                waypoints, movement_approval, target_id=target_id,
                trajectory_id=recipe.get("trajectory_id", identity),
                dataset_version=dataset_version,
            )
            write(output / "evaluation" / identity / "reference_movement_annotations.json",
                  annotations)
        write(output / "simulation" / identity / "recipe.json", recipe)
        summaries.append({"case_id": identity, "status": "EXPORTED_READINESS_PENDING",
                          "timestamps": len(timestamps), "records": len(frames),
                          "observed_records": sum(row["status"] == "OBSERVED" for row in frames),
                          "gap_records": sum(row["status"] == "GAP" for row in frames)})
    if before != (digest(source), source.stat().st_size, source.stat().st_mtime_ns):
        raise RuntimeError("source changed during unsaved read-only reviewed export")
    result = {
        "schema_version": "phase1-reviewed-dataset-v1",
        "dataset_version": dataset_version,
        "status": "REVIEWED_SOURCE_EXPORT_CASE_READINESS_PENDING",
        "formal_cases_executed": False, "legacy_diagnostic_artifacts_promoted": False,
        "source_sha256": before[0], "source_size_bytes": before[1], "source_saved": False,
        "metres_per_blender_unit": .0247, "scale_authority": "APPROVED",
        "export_seed": config.get("export_seed", 20261005),
        "ground_truth_sample_source": "CONFIGURATION_SAMPLER",
        "inference_seed": config.get("inference_seed", 42), "sampling_fps": 5,
        "sampling_extent": "SOURCE_ENDPOINTS_INCLUSIVE",
        "blender_version": bpy.app.version_string, "blender_build": bpy.app.build_hash.decode(),
        "config_sha256": digest(config_path), "application_manifest_sha256":
        digest(application / "manifest.json"), "human_decisions_sha256":
        receipt["human_decisions_sha256"], "coordinate_storage": "BLENDER_NATIVE_UNITS",
        "gt_isolation": "inference never reads evaluation/ or simulation/", "cases": summaries,
        "producer_hashes": {str(path.relative_to(root)): digest(path) for path in (
            Path(__file__), root / "scripts/export_blender_pilot.py",
            root / "src/amidst/simulation/blender_camera.py",
            root / "src/amidst/simulation/blender_visibility.py")},
        "artifacts": {str(path.relative_to(output)): digest(path)
                      for path in sorted(output.rglob("*.json"))},
    }
    if movement_approval is not None:
        movement_producer = root / "src/amidst/finalization/reviewed_reference_movement.py"
        result["producer_hashes"][str(movement_producer.relative_to(root))] = digest(
            movement_producer,
        )
        result["reference_movement_policy_content_sha256"] = configuration_document[
            "reference_movement_policy_content_sha256"]
        result["reference_movement_approval_receipt_content_sha256"] = configuration_document[
            "reference_movement_approval_receipt_content_sha256"]
        result["reference_annotations_partition"] = "evaluation"
    write(output / "manifest.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--application", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    result = export(args.config, args.application, args.output)
    print(json.dumps({"status": result["status"], "cases": result["cases"]}), flush=True)


if __name__ == "__main__":
    main()
