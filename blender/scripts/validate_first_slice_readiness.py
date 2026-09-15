#!/usr/bin/env python3
"""Validate first-slice readiness without rendering or modifying Blender data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import file_sha256, load_identity_layer  # noqa: E402
from persist_instance_ids import (  # noqa: E402
    EXCLUDED_CAMERA,
    strict_registry,
    validate_registry_against_scene,
)
from validate_scene import inspect_external_resources  # noqa: E402


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-scene",
        type=Path,
        default=REPOSITORY_ROOT / "blender/source/school_v1.blend",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPOSITORY_ROOT / "data/annotations/instance_registry/school.json",
    )
    parser.add_argument(
        "--semantic-sidecar",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--semantic-coverage",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_semantic_coverage.json",
    )
    parser.add_argument(
        "--resource-audit",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_missing_resource_audit.json",
    )
    parser.add_argument(
        "--task-contract",
        type=Path,
        default=REPOSITORY_ROOT / "data/metadata/first_dataset_slice_tasks_v0_1_0.json",
    )
    parser.add_argument(
        "--metadata-schema",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_metadata_schema_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--render-config",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_config_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--scene-comparison",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_id_scene_comparison.json",
    )
    parser.add_argument(
        "--baseline-validation",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_ids_validation.json",
    )
    parser.add_argument(
        "--resource-repair",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_resource_repair.json",
    )
    parser.add_argument(
        "--render-resource-policy",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--texture-policy-validation",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_validation.json"
        ),
    )
    parser.add_argument(
        "--automatic-disambiguation",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/instance_registry/school_v1_disambiguation.json"
        ),
    )
    parser.add_argument(
        "--identity-bootstrap",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/instance_registry/school_v1_identity_bootstrap.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_first_slice_readiness.json",
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_first_slice_readiness.md",
    )
    return parser.parse_args(raw)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def scalar_equal(actual: Any, expected: Any) -> bool:
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and math.isclose(
            float(actual), expected, rel_tol=0.0, abs_tol=1e-12
        )
    return actual == expected


def approved_resource_record(record: dict[str, Any]) -> bool:
    digest = record.get("verified_asset_sha256")
    replacement = record.get("replacement_approval", {})
    approved_replacement = (
        replacement.get("status") == "APPROVED"
        and replacement.get("provenance_verified") is True
        and replacement.get("review_decision") == "approved_replacement"
    )


def render_config_differences(scene: Any, render_config: dict[str, Any]) -> list[str]:
    locked = render_config.get("locked_render_values", {})
    actual = {
        "render_engine": scene.render.engine,
        "resolution_x": scene.render.resolution_x,
        "resolution_y": scene.render.resolution_y,
        "resolution_percentage": scene.render.resolution_percentage,
        "pixel_aspect_x": scene.render.pixel_aspect_x,
        "pixel_aspect_y": scene.render.pixel_aspect_y,
        "use_border": scene.render.use_border,
        "use_crop_to_border": scene.render.use_crop_to_border,
        "use_motion_blur": scene.render.use_motion_blur,
        "use_compositing": scene.render.use_compositing,
        "use_sequencer": scene.render.use_sequencer,
        "use_simplify": scene.render.use_simplify,
        "film_transparent": scene.render.film_transparent,
        "filter_size": scene.render.filter_size,
        "dither_intensity": scene.render.dither_intensity,
        "use_persistent_data": scene.render.use_persistent_data,
        "file_extension": scene.render.file_extension,
        "file_format": scene.render.image_settings.file_format,
        "color_mode": scene.render.image_settings.color_mode,
        "color_depth": scene.render.image_settings.color_depth,
        "png_compression": scene.render.image_settings.compression,
        "color_management": scene.render.image_settings.color_management,
        "display_device": scene.display_settings.display_device,
        "display_emulation": scene.display_settings.emulation,
        "view_transform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": scene.view_settings.exposure,
        "gamma": scene.view_settings.gamma,
        "use_curve_mapping": scene.view_settings.use_curve_mapping,
        "use_white_balance": scene.view_settings.use_white_balance,
        "sequencer_color_space": scene.sequencer_colorspace_settings.name,
        "fps": scene.render.fps,
        "fps_base": scene.render.fps_base,
    }
    mismatches = [
        f"locked_render_values.{name}"
        for name, expected in locked.items()
        if name not in actual or not scalar_equal(actual[name], expected)
    ]
    mismatches.extend(
        f"locked_eevee_values.{name}"
        for name, expected in render_config.get("locked_eevee_values", {}).items()
        if not scalar_equal(getattr(scene.eevee, name, None), expected)
    )
    return sorted(mismatches)
    return (
        record.get("blocks_render_generation") is False
        and record.get("resolution_status") == "RESOLVED"
        and isinstance(digest, str)
        and len(digest) == 64
        and bool(record.get("provenance"))
        and (record.get("exact_original_asset_found") is True or approved_replacement)
    )


def image_nodes_without_datablock(node_tree: Any, visited: set[int] | None = None) -> list[str]:
    if node_tree is None:
        return []
    visited = visited or set()
    pointer = node_tree.as_pointer()
    if pointer in visited:
        return []
    visited.add(pointer)
    failures: list[str] = []
    for node in node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image is None:
            failures.append(f"{node_tree.name}/{node.name}")
        nested = getattr(node, "node_tree", None)
        if nested is not None:
            failures.extend(image_nodes_without_datablock(nested, visited))
    return failures


def camera_record(obj: Any) -> dict[str, Any]:
    camera = obj.data
    numeric = {
        "lens": float(camera.lens),
        "sensor_width": float(camera.sensor_width),
        "sensor_height": float(camera.sensor_height),
        "shift_x": float(camera.shift_x),
        "shift_y": float(camera.shift_y),
        "clip_start": float(camera.clip_start),
        "clip_end": float(camera.clip_end),
    }
    invalid = [name for name, value in numeric.items() if not math.isfinite(value)]
    if numeric["lens"] <= 0:
        invalid.append("lens_nonpositive")
    if numeric["sensor_width"] <= 0 or numeric["sensor_height"] <= 0:
        invalid.append("sensor_dimension_nonpositive")
    if numeric["clip_start"] <= 0 or numeric["clip_end"] <= numeric["clip_start"]:
        invalid.append("invalid_clip_range")
    return {
        "object_name_locator": obj.name,
        "instance_id": obj.get("instance_id"),
        "projection_type": camera.type,
        "numeric_parameters": numeric,
        "invalid_parameters": sorted(set(invalid)),
    }


def main() -> None:
    args = script_args()
    scene_path = Path(bpy.data.filepath).resolve()
    if not scene_path.is_file():
        raise RuntimeError("No saved Blender scene is open")
    if (REPOSITORY_ROOT / "blender/source") in scene_path.parents:
        raise RuntimeError("Refusing to validate the immutable source scene directly")

    source_path = args.source_scene.resolve()
    source_checksum = file_sha256(source_path)
    registry = strict_registry(args.registry.resolve())
    automatic = load_identity_layer(
        args.automatic_disambiguation.resolve(),
        "amidst.school_object_objective_disambiguation",
        5,
    )
    bootstrap = load_identity_layer(
        args.identity_bootstrap.resolve(),
        "amidst.school_object_identity_bootstrap",
        131,
    )
    identity = validate_registry_against_scene(
        bpy.context.scene, registry, automatic, bootstrap, require_ids=True
    )

    semantic_sidecar = load_json(args.semantic_sidecar)
    semantic_coverage = load_json(args.semantic_coverage)
    resource_audit = load_json(args.resource_audit)
    task_contract = load_json(args.task_contract)
    metadata_schema = load_json(args.metadata_schema)
    render_config = load_json(args.render_config)
    scene_comparison = load_json(args.scene_comparison)
    baseline_validation = load_json(args.baseline_validation)
    repair_report = (
        load_json(args.resource_repair) if args.resource_repair.exists() else None
    )
    render_resource_policy = (
        load_json(args.render_resource_policy)
        if args.render_resource_policy.exists()
        else None
    )
    texture_policy_validation = (
        load_json(args.texture_policy_validation)
        if args.texture_policy_validation.exists()
        else None
    )

    expected_tasks = {
        "visible_objects",
        "nearest_object",
        "distance_to_object",
        "left_of",
        "right_of",
        "in_front_of",
        "behind",
    }
    semantic_consistent = (
        semantic_sidecar.get("identity_policy_id") == registry["policy_id"]
        and semantic_sidecar.get("instance_registry_schema_version") == registry["schema_version"]
        and semantic_sidecar.get("reviewed_annotations") == []
        and semantic_coverage.get("total_stable_id_objects") == 2777
        and semantic_coverage.get("unknown_objects") == 2777
        and semantic_sidecar.get("minimum_category_vocabulary") == ["Unknown"]
        and semantic_sidecar.get("unreviewed_default", {}).get("category") == "Unknown"
        and semantic_sidecar.get("unreviewed_default", {}).get("annotation_status")
        == "needs_review"
    )
    semantic_category_agnostic = (
        semantic_sidecar.get("status") == "CONFIRMED"
        and semantic_sidecar.get("schema_version") == "0.1.0"
        and semantic_sidecar.get("annotation_version") == "school.v1.semantic/0.1.0"
        and {
            task.get("task")
            for task in semantic_sidecar.get("task_definitions", [])
            if task.get("status") == "CONFIRMED"
            and task.get("semantic_category_required") is False
        }
        == expected_tasks
    )
    task_contract_authoritative = (
        task_contract.get("status") == "CONFIRMED"
        and task_contract.get("schema_version") == "0.1.0"
        and task_contract.get("contract_id")
        == "amidst.school.first-dataset-slice/0.1.0"
        and task_contract.get("semantic_category_required") is False
        and {task.get("task") for task in task_contract.get("tasks", [])}
        == expected_tasks
        and not task_contract.get("open_parameters")
        and task_contract.get("render_resource_policy", {}).get("policy_id")
        == "amidst.school.texture-agnostic-render/0.1.0"
    )
    spatial_conventions_authoritative = (
        task_contract.get("spatial_conventions", {}).get("version")
        == "amidst.school.first-slice-spatial/1.0.0"
        and task_contract.get("visibility_definition", {}).get("version")
        == "amidst.school.first-slice-visibility/1.0.0"
        and task_contract.get("numeric_tolerances", {}).get("finite_values_required")
        is True
        and bool(task_contract.get("tie_breaking"))
        and bool(task_contract.get("valid_sample_conditions"))
        and bool(task_contract.get("invalid_sample_reasons"))
        and bool(task_contract.get("output_naming"))
    )
    metadata_schema_authoritative = (
        metadata_schema.get("$id") == "amidst.first-dataset-slice.metadata/0.1.0"
        and metadata_schema.get("properties", {})
        .get("schema_version", {})
        .get("const")
        == "0.1.0"
        and metadata_schema.get("properties", {})
        .get("contract_version", {})
        .get("const")
        == "amidst.school.first-dataset-slice/0.1.0"
        and metadata_schema.get("properties", {})
        .get("provenance", {})
        .get("properties", {})
        .get("render_resource_policy_id", {})
        .get("const")
        == "amidst.school.texture-agnostic-render/0.1.0"
    )
    render_config_authoritative = (
        render_config.get("status") == "CONFIRMED"
        and render_config.get("schema_version") == "0.1.0"
        and render_config.get("config_id")
        == "amidst.school.first-slice-render/0.1.0"
        and render_config.get("generation_authorized") is True
        and not render_config.get("open_determinism_decisions")
        and render_config.get("contract_dependencies", {}).get(
            "render_resource_policy"
        )
        == "amidst.school.texture-agnostic-render/0.1.0"
    )
    cameras = sorted(
        (obj for obj in bpy.context.scene.objects if obj.type == "CAMERA"),
        key=lambda obj: obj.name,
    )
    eligible_cameras = [obj for obj in cameras if obj.name != EXCLUDED_CAMERA]
    camera_records = [camera_record(obj) for obj in eligible_cameras]
    invalid_eligible_cameras = [
        record for record in camera_records if record["invalid_parameters"]
    ]
    excluded_camera = next((obj for obj in cameras if obj.name == EXCLUDED_CAMERA), None)

    broken_image_nodes: list[dict[str, Any]] = []
    for material in bpy.data.materials:
        for node_path in image_nodes_without_datablock(material.node_tree):
            broken_image_nodes.append({"material": material.name, "node_path": node_path})

    resources = inspect_external_resources()
    baseline_resource_paths = {
        (item["resource_type"], item["name"], item["path"])
        for item in baseline_validation["checks"]["external_resources"]
    }
    current_resource_paths = {
        (item["resource_type"], item["name"], item["path"]) for item in resources
    }
    raw_paths_preserved = baseline_resource_paths == current_resource_paths
    missing_resources = [item for item in resources if not item["exists"]]
    current_scene_sha256 = file_sha256(scene_path)
    texture_policy_authoritative = (
        render_resource_policy is not None
        and texture_policy_validation is not None
        and render_resource_policy.get("status") == "CONFIRMED"
        and render_resource_policy.get("policy_id")
        == "amidst.school.texture-agnostic-render/0.1.0"
        and render_resource_policy.get("resource_policy") == "texture_agnostic"
        and render_resource_policy.get("authoritative_visual_fidelity") is False
        and render_resource_policy.get("derived_scene_sha256") == current_scene_sha256
        and texture_policy_validation.get("status") == "PASS"
        and texture_policy_validation.get("derived_scene_sha256")
        == current_scene_sha256
    )
    runtime_required_missing_count = (
        texture_policy_validation.get("runtime_required_missing_resource_count")
        if texture_policy_validation is not None
        else len(missing_resources)
    )
    legacy_history_preserved = (
        len(resource_audit.get("resources", [])) == 5
        and resource_audit.get("summary", {}).get("unresolved_resources") == 5
        and render_resource_policy is not None
        and len(render_resource_policy.get("legacy_resources", [])) == 5
        and texture_policy_validation is not None
        and texture_policy_validation.get("checks", {}).get(
            "five_legacy_resources_remain_recorded_unavailable"
        )
        is True
    )
    derived_scene_invariants_pass = (
        texture_policy_validation is not None
        and texture_policy_validation.get("status") == "PASS"
        and texture_policy_validation.get("unauthorized_scene_change_count") == 0
        and texture_policy_validation.get("checks", {}).get(
            "object_transforms_unchanged"
        )
        is True
        and texture_policy_validation.get("checks", {}).get(
            "geometry_topology_material_structure_unchanged"
        )
        is True
    )
    derived_scene_provenance = (
        texture_policy_authoritative
        and render_resource_policy.get("source_scene_sha256") == source_checksum
        and render_resource_policy.get("input_scene_sha256")
        == render_config.get("identity_output_scene_sha256")
        and bool(render_resource_policy.get("authorized_datablock_changes"))
    )

    scene = bpy.context.scene
    render_config_mismatches = render_config_differences(scene, render_config)

    checks = {
        "source_checksum_unchanged": source_checksum == registry["source_sha256"],
        "stable_ids_match_authoritative_registry": identity["ids_verified"] == 2777,
        "stable_ids_unique": len(set(identity["expected_by_name"].values())) == 2777,
        "semantic_registry_structurally_consistent": semantic_consistent,
        "semantic_baseline_human_approved": semantic_category_agnostic,
        "semantic_baseline_intentionally_category_agnostic": semantic_category_agnostic,
        "camera_count_is_30": len(cameras) == 30,
        "eligible_camera_count_is_29": len(eligible_cameras) == 29,
        "excluded_helper_camera_has_no_id": (
            excluded_camera is not None and excluded_camera.get("instance_id") is None
        ),
        "eligible_cameras_have_finite_valid_parameters": not invalid_eligible_cameras,
        "material_image_nodes_have_datablocks": not broken_image_nodes,
        "zero_missing_external_render_resources": not missing_resources,
        "five_legacy_resources_remain_recorded_unavailable": legacy_history_preserved,
        "render_resource_policy_authoritative": texture_policy_authoritative,
        "zero_unresolved_resources_required_by_approved_render_policy": (
            texture_policy_authoritative and runtime_required_missing_count == 0
        ),
        "raw_external_resource_paths_preserved": raw_paths_preserved,
        "raw_external_resource_paths_approved_intentional": (
            texture_policy_authoritative
            and texture_policy_validation.get("checks", {}).get(
                "legacy_resource_paths_preserved"
            )
            is True
        ),
        "object_transforms_and_inventory_unchanged": (
            derived_scene_invariants_pass
        ),
        "scene_units_recorded": True,
        "render_engine_and_settings_recorded": True,
        "deterministic_render_configuration_approved": render_config_authoritative,
        "current_scene_matches_locked_render_values": not render_config_mismatches,
        "task_contract_approved": task_contract_authoritative,
        "spatial_conventions_authoritative": spatial_conventions_authoritative,
        "metadata_schema_approved": metadata_schema_authoritative,
        "derived_scene_render_policy_provenance_recorded": derived_scene_provenance,
        "source_output_provenance_recorded": (
            render_config.get("source_scene_sha256") == source_checksum
            and derived_scene_provenance
        ),
        "dataset_images_generated": False,
    }
    required_true = [
        key
        for key in checks
        if key
        not in {
            "dataset_images_generated",
            "raw_external_resource_paths_preserved",
            "zero_missing_external_render_resources",
        }
    ]
    blockers = [key for key in required_true if checks[key] is not True]
    blockers = sorted(set(blockers))
    status = "READY_FOR_FIRST_DATASET_SLICE" if not blockers else "REVIEW_REQUIRED"

    report = {
        "schema_name": "amidst.first_dataset_slice_readiness",
        "schema_version": "0.1.0",
        "repository_classification": "REVIEW_REQUIRED",
        "status": status,
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scene_id": "school",
        "scene_version": "v1",
        "source_scene": str(source_path),
        "source_scene_sha256": source_checksum,
        "validated_output_scene": str(scene_path),
        "validated_output_scene_sha256": current_scene_sha256,
        "instance_registry": str(args.registry.resolve()),
        "semantic_sidecar": str(args.semantic_sidecar.resolve()),
        "task_contract": str(args.task_contract.resolve()),
        "metadata_schema": str(args.metadata_schema.resolve()),
        "render_config": str(args.render_config.resolve()),
        "render_resource_policy": str(args.render_resource_policy.resolve()),
        "texture_policy_validation": str(args.texture_policy_validation.resolve()),
        "checks": checks,
        "counts": {
            "total_objects": len(scene.objects),
            "stable_ids_verified": identity["ids_verified"],
            "camera_count": len(cameras),
            "eligible_camera_count": len(eligible_cameras),
            "invalid_eligible_camera_count": len(invalid_eligible_cameras),
            "external_resource_count": len(resources),
            "missing_external_resource_count": len(missing_resources),
            "legacy_missing_external_resource_count": len(missing_resources),
            "runtime_required_missing_resource_count": runtime_required_missing_count,
            "missing_render_resource_count": runtime_required_missing_count,
            "broken_material_image_node_count": len(broken_image_nodes),
        },
        "eligible_cameras": camera_records,
        "invalid_eligible_cameras": invalid_eligible_cameras,
        "excluded_camera": camera_record(excluded_camera) if excluded_camera else None,
        "broken_material_image_nodes": broken_image_nodes,
        "scene_units": {
            "system": scene.unit_settings.system,
            "scale_length": scene.unit_settings.scale_length,
            "length_unit": scene.unit_settings.length_unit,
        },
        "render_settings": {
            "engine": scene.render.engine,
            "resolution_x": scene.render.resolution_x,
            "resolution_y": scene.render.resolution_y,
            "resolution_percentage": scene.render.resolution_percentage,
            "file_format": scene.render.image_settings.file_format,
            "color_mode": scene.render.image_settings.color_mode,
            "color_depth": scene.render.image_settings.color_depth,
            "film_transparent": scene.render.film_transparent,
            "fps": scene.render.fps,
        },
        "blockers": blockers,
        "scene_mutated": False,
        "images_generated": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    args.human_report.write_text(
        "\n".join(
            [
                "# School v1 First Dataset Slice Readiness",
                "",
                f"Status: `{status}`",
                "",
                f"- Stable IDs verified: {identity['ids_verified']}",
                f"- Eligible cameras: {len(eligible_cameras)}; invalid: {len(invalid_eligible_cameras)}",
                f"- Legacy resources still unavailable: {len(missing_resources)}",
                f"- Runtime-required missing resources: {runtime_required_missing_count}",
                f"- Broken material image links: {len(broken_image_nodes)}",
                f"- Raw external paths preserved: `{str(raw_paths_preserved).lower()}`",
                f"- Semantic baseline approved: `{str(checks['semantic_baseline_human_approved']).lower()}`",
                f"- Task contract approved: `{str(task_contract_authoritative).lower()}`",
                f"- Metadata schema approved: `{str(metadata_schema_authoritative).lower()}`",
                f"- Spatial conventions approved: `{str(spatial_conventions_authoritative).lower()}`",
                f"- Render configuration approved: `{str(render_config_authoritative).lower()}`",
                f"- Scene matches locked render values: `{str(not render_config_mismatches).lower()}`",
                f"- Texture-agnostic policy authoritative: `{str(texture_policy_authoritative).lower()}`",
                f"- Derived-scene provenance sufficient: `{str(derived_scene_provenance).lower()}`",
                "- Images generated: `false`",
                "",
                "## Blockers",
                "",
                *([f"- `{blocker}`" for blocker in blockers] or ["- None"]),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "blocker_count": len(blockers), **report["counts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
