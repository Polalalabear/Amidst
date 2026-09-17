#!/usr/bin/env python3
"""Render one eligible camera in a fresh process under render policy v0.1.1."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import file_sha256  # noqa: E402
from create_texture_agnostic_scene import load_json, scene_invariant_digests  # noqa: E402
from diagnose_render_policy_v0_1_1 import (  # noqa: E402
    DIAGNOSTIC_VERSION,
    render_camera,
)
from generate_first_dataset_slice import (  # noqa: E402
    camera_is_valid,
    camera_metadata,
    eligible_task_objects,
)
from persist_instance_ids import EXCLUDED_CAMERA, strict_registry  # noqa: E402
from render_policy_v0_1_1 import CONFIG_ID, MATERIAL_NAME, POLICY_ID  # noqa: E402
from validate_first_slice_readiness import render_config_differences  # noqa: E402


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
    parser.add_argument("--camera-id", required=True)
    parser.add_argument("--image-output", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument(
        "--render-config",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_config_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--resource-policy",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_resource_policy_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPOSITORY_ROOT / "data/annotations/instance_registry/school.json",
    )
    return parser.parse_args(raw)


def write_json_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite camera diagnostic: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = script_args()
    scene_path = args.scene.resolve()
    image_path = args.image_output.resolve()
    record_path = args.record_output.resolve()
    if Path(bpy.data.filepath).resolve() != scene_path:
        raise RuntimeError("Loaded scene does not match --scene")
    if image_path.exists() or record_path.exists():
        raise RuntimeError("Refusing to overwrite per-camera diagnostic evidence")

    config = load_json(args.render_config.resolve())
    policy = load_json(args.resource_policy.resolve())
    registry = strict_registry(args.registry.resolve())
    if config.get("config_id") != CONFIG_ID or policy.get("policy_id") != POLICY_ID:
        raise RuntimeError("v0.1.1 config/policy mismatch")
    if config.get("generation_authorized") is not False:
        raise RuntimeError("Diagnostic process must not authorize dataset generation")
    checksum_before = file_sha256(scene_path)
    if checksum_before != policy.get("derived_scene_sha256"):
        raise RuntimeError("Derived scene checksum mismatch")

    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    material = bpy.data.materials.get(MATERIAL_NAME)
    if material is None or view_layer.material_override != material:
        raise RuntimeError("v0.1.1 material override is unavailable")
    if render_config_differences(scene, config):
        raise RuntimeError("Render config differs before camera diagnostic")
    matches = [
        obj
        for obj in scene.objects
        if obj.type == "CAMERA"
        and obj.name != EXCLUDED_CAMERA
        and obj.get("instance_id") == args.camera_id
        and camera_is_valid(obj)
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one eligible camera, found {len(matches)}")
    camera = matches[0]

    registry_ids = {record["instance_id"] for record in registry["records"]}
    task_objects = eligible_task_objects(scene, view_layer, registry_ids)
    index_to_object = {index: obj for index, obj in enumerate(task_objects, start=1)}
    previous_pass_indices = {obj.name: obj.pass_index for obj in task_objects}
    previous_camera = scene.camera
    previous_filepath = scene.render.filepath
    previous_compositor = scene.compositing_node_group
    invariants_before = scene_invariant_digests(scene, registry)
    for index, obj in index_to_object.items():
        obj.pass_index = index
    render_camera.render_config = config
    started = datetime.now(timezone.utc)
    try:
        with tempfile.TemporaryDirectory(prefix="amidst_policy_camera_v0_1_1_") as temporary:
            rendered, _indices = render_camera(
                scene,
                view_layer,
                material,
                camera,
                index_to_object,
                image_path,
                Path(temporary),
            )
    finally:
        scene.camera = previous_camera
        scene.render.filepath = previous_filepath
        scene.compositing_node_group = previous_compositor
        for obj in task_objects:
            obj.pass_index = previous_pass_indices[obj.name]

    invariants_after = scene_invariant_digests(scene, registry)
    checksum_after = file_sha256(scene_path)
    record = {
        "schema_name": "amidst.render_policy_camera_diagnostic",
        "schema_version": "0.1.1",
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "repository_classification": "REVIEW_REQUIRED",
        "path_base": "repository_root",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "render_policy_id": POLICY_ID,
        "render_config_id": CONFIG_ID,
        "camera_instance_id": camera["instance_id"],
        "camera_blender_name_diagnostic_only": camera.name,
        "camera": camera_metadata(camera, scene, bpy.context.evaluated_depsgraph_get()),
        "render_success": True,
        "usability_status": "PENDING_THRESHOLD_PROPOSAL",
        "failure_reasons": [],
        **rendered,
        "derived_scene_sha256_before": checksum_before,
        "derived_scene_sha256_after": checksum_after,
        "derived_scene_checksum_unchanged": checksum_before == checksum_after,
        "scene_invariants_unchanged_after_runtime_cleanup": invariants_before == invariants_after,
        "dataset_frame_created": False,
        "dataset_pilot_created": False,
        "gt_contract_changed": False,
    }
    write_json_new(record_path, record)
    print(
        json.dumps(
            {
                "camera_id": record["camera_instance_id"],
                "render_success": True,
                "mean_luminance": record["luminance"]["mean_luminance"],
                "largest_occupancy": record["composition"][
                    "largest_single_object_occupancy_ratio"
                ],
                "visible_object_count": record["composition"][
                    "valid_visible_stable_id_object_count"
                ],
                "scene_unchanged": (
                    record["derived_scene_checksum_unchanged"]
                    and record["scene_invariants_unchanged_after_runtime_cleanup"]
                ),
            },
            sort_keys=True,
        )
    )
    if checksum_before != checksum_after or invariants_before != invariants_after:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
