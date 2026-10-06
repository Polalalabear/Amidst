"""Fresh source-bound export of existing pilot definitions, never formal certification.

Run inside an unsaved Blender process. This export stage alone reads simulation
waypoints. Inference receives only strict 2D evidence and independent context;
evaluation truth and simulation recipes are separate files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def main() -> None:
    import bpy
    from mathutils import Matrix

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "scripts"))
    from export_blender_pilot import annotation_objects, project

    from amidst.simulation.blender_camera import extract_camera_dict
    from amidst.simulation.blender_visibility import BlenderMeshRaycaster

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    config = json.loads(args.config.read_bytes())
    source = Path(bpy.data.filepath)
    before = (digest(source), source.stat().st_size, source.stat().st_mtime_ns)
    if before[:2] != (config["source_sha256"], config["source_size_bytes"]):
        raise ValueError("source differs from the pinned checkpoint")
    if args.output.exists():
        raise FileExistsError("fresh output required")
    scene = bpy.context.scene
    scene.render.resolution_x = config["width"]
    scene.render.resolution_y = config["height"]
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1
    scene.render.use_border = scene.render.use_crop_to_border = False
    raycaster = BlenderMeshRaycaster(scene, excluded_objects=annotation_objects(bpy, scene))
    summaries = []
    for recipe in config["streams"]:
        site = recipe["site_id"]
        cameras = [extract_camera_dict(scene, bpy.data.objects[name])
                   for name in sorted(recipe["camera_ids"])]
        frames, truth, visibility = [], [], []
        a, b = recipe["waypoints"]
        for index in range(config["timestamp_count"]):
            timestamp = index / config["sampling_fps"]
            fraction = (timestamp - a["timestamp"]) / (b["timestamp"] - a["timestamp"])
            foot = [x + fraction * (y - x)
                    for x, y in zip(a["position"], b["position"], strict=True)]
            position = [foot[0], foot[1], foot[2] + recipe["landmark_offset_bu"]]
            truth.append({"timestamp": timestamp, "position": position,
                          "foot_position": foot, "floor_id": "1F",
                          "trajectory_id": recipe["trajectory_id"]})
            for camera in cameras:
                projected = project(camera, position, Matrix)
                reason, occluder = projected["reason"], None
                if reason == "IN_FRUSTUM":
                    matrix = camera["camera_to_world"]
                    ray = raycaster(tuple(matrix[i][3] for i in range(3)), tuple(position))
                    reason, occluder = ray.reason, ray.occluder_id
                observed = reason == "CLEAR"
                frames.append({"frame_id": index, "timestamp": timestamp,
                               "target_id": f"finalization_{site}",
                               "camera_id": camera["camera_id"],
                               "status": "OBSERVED" if observed else "GAP",
                               "point_2d": projected["pixel"] if observed else None,
                               "provenance": "OBSERVED" if observed else None,
                               "gap_reason": None if observed else reason,
                               "occluder_id": occluder, "data_kind": "SYNTHETIC"})
                visibility.append({"frame_id": index, "timestamp": timestamp,
                                   "camera_id": camera["camera_id"], "reason": reason,
                                   "status": "OBSERVED" if observed else "GAP",
                                   "occluder_id": occluder})
        observation = {"label": "PILOT / SYNTHETIC SAMPLE", "data_kind": "SYNTHETIC",
                       "source_asset_sha256": before[0], "site_id": site, "frames": frames}
        observation_path = args.output / "inference" / site / "observations.json"
        write(observation_path, observation)
        context = {"label": "PILOT / SYNTHETIC SAMPLE", "data_kind": "SYNTHETIC",
                   "site_id": site, "source_id": f"finalization_blender:{site}",
                   "spatial_context_id": f"FINALIZATION_DIAGNOSTIC_{site.upper()}",
                   "source_asset_sha256": before[0],
                   "observations_sha256": digest(observation_path), "cameras": cameras,
                   "plane": {"plane_id": f"DIAGNOSTIC_{site.upper()}_LANDMARK",
                             "point": [0, 0, recipe["plane_z_bu"]], "normal": [0, 0, 1],
                             "floor_id": "1F", "zone_id": recipe["zone_id"]},
                   "zone": {"floor_id": "1F", "zone_id": recipe["zone_id"],
                            "walkable_object_id": recipe["walkable_id"],
                            "bounds_min": recipe["bounds_min"],
                            "bounds_max": recipe["bounds_max"],
                            "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL"}}
        write(args.output / "inference" / site / "context.json", context)
        write(args.output / "inference" / site / "visibility.json", visibility)
        write(args.output / "evaluation" / site / "ground_truth.json",
              {"label": "PILOT / SYNTHETIC SAMPLE", "site_id": site,
               "source_asset_sha256": before[0], "provenance": "GROUND_TRUTH",
               "trajectory_id": recipe["trajectory_id"], "samples": truth})
        write(args.output / "simulation" / site / "recipe.json", recipe)
        summaries.append({"stream": site, "timestamps": len(truth),
                          "records": len(frames),
                          "observed_records": sum(row["status"] == "OBSERVED" for row in frames),
                          "synchronized_dual_timestamps": sum(
                              sum(row["status"] == "OBSERVED" for row in frames
                                  if row["frame_id"] == i) >= 2
                              for i in range(config["timestamp_count"]))})
    if before != (digest(source), source.stat().st_size, source.stat().st_mtime_ns):
        raise RuntimeError("source changed during read-only export")
    manifest = {"dataset_version": config["dataset_version"], "status": "DIAGNOSTIC",
                "formal_cases_executed": False, "source_sha256": before[0],
                "source_size_bytes": before[1], "source_saved": False,
                "blender_version": bpy.app.version_string,
                "blender_build": bpy.app.build_hash.decode(),
                "metres_per_blender_unit": config["metres_per_blender_unit"],
                "scale_authority": "APPROVED", "seed": config["seed"],
                "coordinate_storage": "BLENDER_NATIVE_UNITS",
                "legacy_context_scale_authority": "UNVERIFIED_LEGACY_SCHEMA_LABEL",
                "legacy_domain_m_fields_are_native_bu": True,
                "reporting_conversion": "multiply native distances by 0.0247",
                "camera_plane_authority": "PROVISIONAL",
                "physical_scope": "NOT_CERTIFIED",
                "gt_isolation": "evaluation/ and simulation/ forbidden to inference",
                "config_sha256": digest(args.config), "streams": summaries,
                "producer_hashes": {str(p.relative_to(root)): digest(p) for p in (
                    Path(__file__), root / "scripts/export_blender_pilot.py",
                    root / "src/amidst/simulation/blender_camera.py",
                    root / "src/amidst/simulation/blender_visibility.py")},
                "artifacts": {str(p.relative_to(args.output)): digest(p)
                              for p in sorted(args.output.rglob("*.json"))}}
    write(args.output / "manifest.json", manifest)
    print(json.dumps(summaries), flush=True)


if __name__ == "__main__":
    main()
