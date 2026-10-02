"""Publish a source-bound read-only school audit; stop before untrusted physical integration."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from amidst.simulation.camera_calibration import load_camera_calibration_json
from amidst.storage.json_files import write_json


def fingerprint(path: Path) -> tuple[str, int, int]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stat = path.stat()
    return digest, stat.st_size, stat.st_mtime_ns


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, default=Path("blender/school_v2.blend"))
    parser.add_argument("--blender", default="blender")
    parser.add_argument(
        "--calibration", type=Path, default=Path("data/cameras/school_v2_calibration_v1.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/scene_audit/school_v2_semantic_audit.json")
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("semantic audit output must be new")
    source = args.blend.resolve()
    before = fingerprint(source)
    with tempfile.TemporaryDirectory(prefix="school-v2-semantics-") as directory:
        temporary = Path(directory) / "inventory.json"
        command = [
            args.blender,
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "-noaudio",
            str(source),
            "--python-exit-code",
            "2",
            "--python",
            str(Path(__file__).with_name("audit_blender_semantics.py")),
            "--",
            "--output",
            str(temporary),
            "--expected-source-sha256",
            before[0],
        ]
        try:
            subprocess.run(command, check=True)
        finally:
            after = fingerprint(source)
            if after != before:
                raise RuntimeError("immutable Blender source changed during semantic audit")
        report: dict[str, Any] = json.loads(temporary.read_text())
    report["source"] = {
        "path": args.blend.as_posix(),
        "sha256_before": before[0],
        "sha256_after": after[0],
        "size_bytes": before[1],
        "mtime_ns_before": before[2],
        "mtime_ns_after": after[2],
    }
    report["read_only_contract"].update(
        source_hash_unchanged=before[0] == after[0],
        source_size_unchanged=before[1] == after[1],
        source_mtime_unchanged=before[2] == after[2],
    )
    report["audit_tools"] = {
        "inventory": {
            "path": "scripts/audit_blender_semantics.py",
            "sha256": fingerprint(Path(__file__).with_name("audit_blender_semantics.py"))[0],
        },
        "wrapper": {
            "path": "scripts/run_semantic_audit.py",
            "sha256": fingerprint(Path(__file__))[0],
        },
    }
    catalog = load_camera_calibration_json(args.calibration)
    if catalog.source_asset_sha256 != before[0]:
        raise ValueError("camera calibration must bind to the same Blender source")
    objects = {row["object"]: row for row in report["objects"]}
    included = tuple(sorted(item.camera.camera_id for item in catalog.cameras))
    actual = tuple(
        sorted(
            name
            for name, row in objects.items()
            if name.startswith("CAM_") and row["object_type"] == "CAMERA"
        )
    )
    if included != actual:
        raise ValueError("portable calibration IDs differ from the live research cameras")
    differences = {
        item.camera.camera_id: max(
            abs(left - right)
            for actual_row, exported_row in zip(
                objects[item.camera.camera_id]["matrix_world"],
                item.pose.evaluated_world_matrix,
                strict=True,
            )
            for left, right in zip(actual_row, exported_row, strict=True)
        )
        for item in catalog.cameras
    }
    report["camera_calibration_check"] = {
        "path": args.calibration.as_posix(),
        "file_sha256": fingerprint(args.calibration)[0],
        "camera_config_version": catalog.camera_config_version,
        "calibration_content_sha256": catalog.calibration_content_sha256,
        "included_camera_count": len(included),
        "ids_match_live_source": included == actual,
        "max_pose_matrix_difference": max(differences.values()),
        "pose_matrix_differences": differences,
        "meters_per_blender_unit": catalog.meters_per_blender_unit,
        "camera_axes": "BLENDER_NEG_Z_UP_Y",
        "pixels": "TOP_LEFT_CONTINUOUS",
        "floor_plane_mapping_trusted": False,
        "floor_labels": "NAME_DERIVED_NOT_GROUND_PLANE_AUTHORITY",
    }
    report["floor_separation"] = {
        "trusted_floor_surfaces": [],
        "status": "UNREVIEWED_NO_FLOOR_SURFACE_OR_CAMERA_PLANE_AUTHORITY",
        "annotation_label_bounds": {
            floor: [
                {"object": row["object"], "bounding_box": row["bounding_box"]}
                for row in report["objects"]
                if row["semantic_class"] == "AREA" and row["declared_floor_label"] == floor
            ]
            for floor in sorted(
                {
                    row["declared_floor_label"]
                    for row in report["objects"]
                    if row["declared_floor_label"] is not None
                }
            )
        },
        "annotation_bounds_are_not_floor_heights": True,
    }
    report["physical_integration_gate"] = {
        "status": "STOP_REQUIRED_HUMAN_ANNOTATION",
        "case_1_2_3_ready": False,
        "trusted_walkable_count": 0,
        "trusted_wall_count": 0,
        "trusted_obstacle_count": 0,
        "reasons": [
            "NO_APPROVED_WALKABLE_SURFACES",
            "WALL_OBSTACLE_OWNERSHIP_UNASSIGNED",
            "CAMERA_FLOOR_PLANE_MAPPING_UNREVIEWED",
        ],
        "human_inputs_required": [
            "Source-bound WALKABLE object/face/proxy IDs, floor/zone, "
            "boundaries/holes/connectivity",
            "Source-bound WALL/OBSTACLE collider IDs/proxies and movement/occlusion ownership",
            "Approved floor planes/extents and camera-to-plane bindings for selected case cameras",
            "Explicit physical collision envelope, minimum clearance and contact/tolerance policy",
        ],
        "group_and_cube_names_not_interpreted": True,
        "original_blend_modification_required": False,
        "sidecar_annotations_supported_in_principle_not_yet_approved": True,
        "case_4_deferred": True,
    }
    report["camera_calibration_check"]["poses_match_live_source_within_1e_minus_6"] = (
        max(differences.values()) <= 1e-6
    )
    if not report["camera_calibration_check"]["poses_match_live_source_within_1e_minus_6"]:
        report["physical_integration_gate"]["reasons"].append("CAMERA_CALIBRATION_POSE_MISMATCH")
    write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "source_sha256": before[0],
                "counts": report["counts"],
                "gate": report["physical_integration_gate"],
                "max_camera_pose_difference": max(differences.values()),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
