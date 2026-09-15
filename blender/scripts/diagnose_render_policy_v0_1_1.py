#!/usr/bin/env python3
"""Render all eligible school_v1 cameras under policy v0.1.1 and collect raw metrics."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import tempfile
import time
import traceback
from typing import Any

import bpy
import numpy as np
import OpenImageIO as oiio


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import file_sha256  # noqa: E402
from create_texture_agnostic_scene import load_json, scene_invariant_digests  # noqa: E402
from generate_first_dataset_slice import (  # noqa: E402
    camera_is_valid,
    camera_metadata,
    cleanup_aov,
    eligible_task_objects,
    read_aov,
    render,
    setup_aov,
)
from persist_instance_ids import EXCLUDED_CAMERA, strict_registry  # noqa: E402
from render_policy_v0_1_1 import CONFIG_ID, MATERIAL_NAME, POLICY_ID  # noqa: E402
from validate_first_slice_readiness import render_config_differences  # noqa: E402


DIAGNOSTIC_VERSION = "amidst.school.render-policy-diagnostic/0.1.1"
NEAR_BLACK = 0.02
NEAR_WHITE = 0.98


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", type=Path, required=True)
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
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/render_diagnostics/school_v1_render_policy_v0_1_1_r2"
        ),
    )
    parser.add_argument(
        "--statistics-output",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_render_policy_v0_1_1_camera_statistics_raw.json"
        ),
    )
    return parser.parse_args(raw)


def read_rgb(path: Path) -> np.ndarray:
    image = oiio.ImageInput.open(str(path))
    if image is None:
        raise RuntimeError(f"Cannot read render: {path}")
    try:
        pixels = np.asarray(image.read_image(format=oiio.FLOAT))
    finally:
        image.close()
    if pixels.ndim != 3 or pixels.shape[2] < 3:
        raise RuntimeError(f"Unexpected render shape: {pixels.shape}")
    return np.clip(pixels[..., :3], 0.0, 1.0)


def decoded_pixel_digest(path: Path) -> str:
    return hashlib.sha256(read_rgb(path).tobytes(order="C")).hexdigest()


def report_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError as error:
        raise RuntimeError(
            f"Diagnostic evidence must be below the repository root: {path.name}"
        ) from error


def canonical_scene_path(path: Path) -> str:
    return f"blender/output/{path.name}"


def luminance_metrics(path: Path) -> dict[str, Any]:
    rgb = read_rgb(path)
    luminance = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    p1, p99 = np.percentile(luminance, [1, 99])
    return {
        "measurement_space": "saved PNG normalized RGB with Rec.709 coefficients",
        "near_black_measurement_threshold": NEAR_BLACK,
        "near_white_measurement_threshold": NEAR_WHITE,
        "mean_luminance": float(np.mean(luminance)),
        "median_luminance": float(np.median(luminance)),
        "p1_luminance": float(p1),
        "p99_luminance": float(p99),
        "p99_minus_p1_luminance": float(p99 - p1),
        "near_black_fraction": float(np.mean(luminance < NEAR_BLACK)),
        "near_white_or_clipped_fraction": float(np.mean(luminance > NEAR_WHITE)),
    }


def composition_metrics(
    indices: np.ndarray, index_to_object: dict[int, Any]
) -> dict[str, Any]:
    maximum = int(indices.max(initial=0))
    if maximum > len(index_to_object) or int(indices.min(initial=0)) < 0:
        raise RuntimeError("AOV contains an unknown object index")
    counts = np.bincount(indices.ravel(), minlength=len(index_to_object) + 1)
    total = int(indices.size)
    object_counts = [int(counts[index]) for index in range(1, len(index_to_object) + 1)]
    largest_index = max(range(1, len(index_to_object) + 1), key=lambda index: counts[index])
    visible = [
        {
            "instance_id": index_to_object[index]["instance_id"],
            "pixel_count": int(counts[index]),
        }
        for index in range(1, len(index_to_object) + 1)
        if counts[index] >= 16
    ]
    valid_geometry_pixels = int(sum(object_counts))
    return {
        "evidence_source": "single-sample deterministic Object Index AOV",
        "aov_pixel_sha256": hashlib.sha256(indices.tobytes(order="C")).hexdigest(),
        "valid_scene_geometry_pixel_count": valid_geometry_pixels,
        "valid_scene_geometry_fraction": valid_geometry_pixels / total,
        "background_or_noneligible_pixel_count": int(counts[0]),
        "valid_visible_stable_id_object_count": len(visible),
        "valid_visible_objects": visible,
        "largest_single_object_instance_id": index_to_object[largest_index]["instance_id"],
        "largest_single_object_pixel_count": int(counts[largest_index]),
        "largest_single_object_occupancy_ratio": int(counts[largest_index]) / total,
        "dominated_by_one_object": None,
        "sufficient_distinguishable_scene_structure": None,
        "threshold_status": "PENDING_DISTRIBUTION_BASED_PROPOSAL",
    }


def render_camera(
    scene: Any,
    view_layer: Any,
    material: Any,
    camera: Any,
    index_to_object: dict[int, Any],
    image_path: Path,
    temporary_root: Path,
) -> tuple[dict[str, Any], np.ndarray]:
    camera_temp = temporary_root / (
        f"{camera['instance_id'].split(':')[-1]}_{image_path.stem}"
    )
    camera_temp.mkdir(parents=True, exist_ok=False)
    previous_compositor = scene.compositing_node_group
    original_samples = scene.eevee.taa_render_samples
    original_reprojection = scene.eevee.use_taa_reprojection
    aov_state = setup_aov(scene, view_layer, material, camera_temp)
    aov_state["previous_compositor"] = previous_compositor
    try:
        scene.camera = camera
        scene.render.filepath = str(image_path)
        if render_config_differences(scene, render_camera.render_config):
            raise RuntimeError("Render config changed before formal observation")
        seconds = render(scene, write_still=True)
        if not image_path.is_file():
            raise RuntimeError("Formal EEVEE output was not written")
        scene.eevee.taa_render_samples = 1
        scene.eevee.use_taa_reprojection = False
        aov_started = time.perf_counter()
        render(scene, write_still=False)
        aov_seconds = time.perf_counter() - aov_started
        indices = read_aov(
            aov_state["path"], scene.render.resolution_x, scene.render.resolution_y
        )
        scene.eevee.taa_render_samples = original_samples
        scene.eevee.use_taa_reprojection = original_reprojection
        record = {
            "render_seconds": seconds,
            "single_sample_aov_render_seconds": aov_seconds,
            "render_path": report_path(image_path),
            "png_sha256": file_sha256(image_path),
            "decoded_pixel_sha256": decoded_pixel_digest(image_path),
            "luminance": luminance_metrics(image_path),
            "composition": composition_metrics(indices, index_to_object),
        }
        return record, indices
    finally:
        scene.eevee.taa_render_samples = original_samples
        scene.eevee.use_taa_reprojection = original_reprojection
        cleanup_aov(scene, view_layer, material, aov_state)
        shutil.rmtree(camera_temp, ignore_errors=True)


render_camera.render_config = {}


def distribution(values: list[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum": float(np.min(array)),
        "p10": float(np.percentile(array, 10)),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.median(array)),
        "p75": float(np.percentile(array, 75)),
        "p90": float(np.percentile(array, 90)),
        "maximum": float(np.max(array)),
    }


def main() -> None:
    args = script_args()
    scene_path = args.scene.resolve()
    if Path(bpy.data.filepath).resolve() != scene_path:
        raise RuntimeError("Loaded scene does not match --scene")
    output_root = args.output_directory.resolve()
    statistics_path = args.statistics_output.resolve()
    if output_root.exists() or statistics_path.exists():
        raise RuntimeError("Refusing to overwrite diagnostic sweep evidence")
    output_root.mkdir(parents=True, exist_ok=False)

    config = load_json(args.render_config.resolve())
    policy = load_json(args.resource_policy.resolve())
    registry = strict_registry(args.registry.resolve())
    if config.get("config_id") != CONFIG_ID or policy.get("policy_id") != POLICY_ID:
        raise RuntimeError("v0.1.1 config/policy mismatch")
    if config.get("generation_authorized") is not False:
        raise RuntimeError("Diagnostic sweep must not authorize dataset generation")
    checksum_before = file_sha256(scene_path)
    if checksum_before != policy.get("derived_scene_sha256"):
        raise RuntimeError("Derived scene checksum does not match v0.1.1 policy")
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    material = bpy.data.materials.get(MATERIAL_NAME)
    if material is None or view_layer.material_override != material:
        raise RuntimeError("v0.1.1 material override is unavailable")
    config_differences = render_config_differences(scene, config)
    if config_differences:
        raise RuntimeError(f"Render-config differences: {config_differences}")

    helper = scene.objects.get(EXCLUDED_CAMERA)
    cameras = sorted(
        (
            obj
            for obj in scene.objects
            if obj.type == "CAMERA" and obj.name != EXCLUDED_CAMERA and camera_is_valid(obj)
        ),
        key=lambda obj: obj["instance_id"],
    )
    if helper is None or helper.get("instance_id") is not None or len(cameras) != 29:
        raise RuntimeError("Eligible camera contract mismatch")
    registry_ids = {record["instance_id"] for record in registry["records"]}
    task_objects = eligible_task_objects(scene, view_layer, registry_ids)
    index_to_object = {index: obj for index, obj in enumerate(task_objects, start=1)}
    object_to_index = {obj.name: index for index, obj in index_to_object.items()}

    previous_camera = scene.camera
    previous_filepath = scene.render.filepath
    previous_compositor = scene.compositing_node_group
    previous_pass_indices = {obj.name: obj.pass_index for obj in task_objects}
    for obj in task_objects:
        obj.pass_index = object_to_index[obj.name]
    invariants_before = scene_invariant_digests(scene, registry)
    started = datetime.now(timezone.utc)
    records = []
    repeat_results = []
    fatal_error = None
    render_camera.render_config = config
    try:
        with tempfile.TemporaryDirectory(prefix="amidst_policy_v0_1_1_") as temporary:
            temporary_root = Path(temporary)
            for camera in cameras:
                camera_uuid = camera["instance_id"].split(":")[-1]
                camera_dir = output_root / f"camera_{camera_uuid}"
                camera_dir.mkdir()
                image_path = camera_dir / "formal_eevee.png"
                base_record = {
                    "camera_instance_id": camera["instance_id"],
                    "camera_blender_name_diagnostic_only": camera.name,
                    "camera": camera_metadata(camera, scene, bpy.context.evaluated_depsgraph_get()),
                    "render_success": False,
                    "usability_status": "PENDING_THRESHOLD_PROPOSAL",
                    "failure_reasons": [],
                }
                try:
                    rendered, _indices = render_camera(
                        scene,
                        view_layer,
                        material,
                        camera,
                        index_to_object,
                        image_path,
                        temporary_root,
                    )
                    base_record.update(rendered)
                    base_record["render_success"] = True
                except Exception as exc:
                    base_record["usability_status"] = "RENDER_FAILURE"
                    base_record["failure_reasons"] = [f"{type(exc).__name__}: {exc}"]
                    base_record["traceback"] = traceback.format_exc()
                records.append(base_record)

            successful = [record for record in records if record["render_success"]]
            if successful:
                ordered = sorted(
                    successful,
                    key=lambda record: record["composition"][
                        "largest_single_object_occupancy_ratio"
                    ],
                )
                selected = [ordered[0], ordered[len(ordered) // 2], ordered[-1]]
                by_id = {camera["instance_id"]: camera for camera in cameras}
                repeat_root = output_root / "determinism_repeats"
                repeat_root.mkdir()
                for initial in selected:
                    camera = by_id[initial["camera_instance_id"]]
                    repeat_path = repeat_root / (
                        f"camera_{camera['instance_id'].split(':')[-1]}_repeat.png"
                    )
                    repeated, _indices = render_camera(
                        scene,
                        view_layer,
                        material,
                        camera,
                        index_to_object,
                        repeat_path,
                        temporary_root,
                    )
                    repeat_results.append(
                        {
                            "camera_instance_id": camera["instance_id"],
                            "selection_basis": (
                                "minimum, median, or maximum primary largest-single-object occupancy"
                            ),
                            "repeat_render_path": repeated["render_path"],
                            "camera_selection_identical": True,
                            "render_settings_identical": not render_config_differences(scene, config),
                            "decoded_pixels_identical": (
                                repeated["decoded_pixel_sha256"]
                                == initial["decoded_pixel_sha256"]
                            ),
                            "luminance_metrics_identical": (
                                repeated["luminance"] == initial["luminance"]
                            ),
                            "composition_metrics_identical": (
                                repeated["composition"] == initial["composition"]
                            ),
                            "primary_decoded_pixel_sha256": initial[
                                "decoded_pixel_sha256"
                            ],
                            "repeat_decoded_pixel_sha256": repeated[
                                "decoded_pixel_sha256"
                            ],
                            "primary_aov_pixel_sha256": initial["composition"][
                                "aov_pixel_sha256"
                            ],
                            "repeat_aov_pixel_sha256": repeated["composition"][
                                "aov_pixel_sha256"
                            ],
                        }
                    )
    except Exception as exc:
        fatal_error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        scene.compositing_node_group = previous_compositor
        scene.camera = previous_camera
        scene.render.filepath = previous_filepath
        for obj in task_objects:
            obj.pass_index = previous_pass_indices[obj.name]

    invariants_after = scene_invariant_digests(scene, registry)
    checksum_after = file_sha256(scene_path)
    success_records = [record for record in records if record.get("render_success")]
    distributions = {}
    if success_records:
        distributions = {
            "mean_luminance": distribution(
                [record["luminance"]["mean_luminance"] for record in success_records]
            ),
            "luminance_spread": distribution(
                [record["luminance"]["p99_minus_p1_luminance"] for record in success_records]
            ),
            "near_black_fraction": distribution(
                [record["luminance"]["near_black_fraction"] for record in success_records]
            ),
            "near_white_or_clipped_fraction": distribution(
                [
                    record["luminance"]["near_white_or_clipped_fraction"]
                    for record in success_records
                ]
            ),
            "largest_single_object_occupancy_ratio": distribution(
                [
                    record["composition"]["largest_single_object_occupancy_ratio"]
                    for record in success_records
                ]
            ),
            "valid_visible_stable_id_object_count": distribution(
                [
                    record["composition"]["valid_visible_stable_id_object_count"]
                    for record in success_records
                ]
            ),
            "valid_scene_geometry_fraction": distribution(
                [
                    record["composition"]["valid_scene_geometry_fraction"]
                    for record in success_records
                ]
            ),
        }
    report = {
        "schema_name": "amidst.render_policy_camera_statistics_raw",
        "schema_version": "0.1.1",
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "status": "STATISTICS_COLLECTED_THRESHOLD_PROPOSAL_PENDING",
        "repository_classification": "REVIEW_REQUIRED",
        "path_base": "repository_root",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "render_policy_id": POLICY_ID,
        "render_config_id": CONFIG_ID,
        "derived_scene": canonical_scene_path(scene_path),
        "derived_scene_sha256_before": checksum_before,
        "derived_scene_sha256_after": checksum_after,
        "derived_scene_checksum_unchanged": checksum_before == checksum_after,
        "scene_invariants_unchanged_after_runtime_cleanup": invariants_before == invariants_after,
        "eligible_camera_count": len(cameras),
        "render_success_count": len(success_records),
        "render_failure_count": len(records) - len(success_records),
        "dataset_frames_created": False,
        "dataset_pilot_created": False,
        "gt_contract_changed": False,
        "per_camera": records,
        "distributions": distributions,
        "determinism_repeats": repeat_results,
        "determinism_pass": (
            len(repeat_results) == 3
            and all(
                record["camera_selection_identical"]
                and record["render_settings_identical"]
                and record["decoded_pixels_identical"]
                and record["luminance_metrics_identical"]
                and record["composition_metrics_identical"]
                for record in repeat_results
            )
        ),
        "fatal_error": fatal_error,
    }
    statistics_path.parent.mkdir(parents=True, exist_ok=True)
    statistics_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "render_success_count": report["render_success_count"],
                "render_failure_count": report["render_failure_count"],
                "determinism_pass": report["determinism_pass"],
                "fatal_error": fatal_error,
            },
            sort_keys=True,
        )
    )
    if (
        fatal_error
        or len(records) != 29
        or len(success_records) != 29
        or not report["determinism_pass"]
        or invariants_before != invariants_after
        or checksum_before != checksum_after
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
