#!/usr/bin/env python3
"""Fresh-process validation for deterministic render-only scene v0.1.1."""

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

from asset_paths import logical_uri_for_path  # noqa: E402
from assign_instance_ids import file_sha256, load_identity_layer  # noqa: E402
from create_texture_agnostic_scene import (  # noqa: E402
    load_json,
    scene_invariant_digests,
)
from persist_instance_ids import (  # noqa: E402
    EXCLUDED_CAMERA,
    strict_registry,
    validate_registry_against_scene,
)
from render_policy_v0_1_1 import (  # noqa: E402
    CONFIG_ID,
    MATERIAL_NAME,
    POLICY_ID,
    POLICY_VERSION,
    SUN_ANGLE_RADIANS,
    SUN_COLOR,
    SUN_ENERGY,
    SUN_SPECS,
    WORLD_COLOR,
    WORLD_NAME,
    WORLD_STRENGTH,
    principled_input_record,
    unlink_policy_lights,
)
from validate_first_slice_readiness import (  # noqa: E402
    camera_record,
    render_config_differences,
)
from validate_texture_agnostic_scene import legacy_runtime_dependencies  # noqa: E402


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--derived-scene", type=Path, required=True)
    parser.add_argument("--source-scene", type=Path, required=True)
    parser.add_argument("--input-scene", type=Path, required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPOSITORY_ROOT / "data/annotations/instance_registry/school.json",
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
        "--policy",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_resource_policy_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--render-config",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_config_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_validation_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_validation_v0_1_1.md"
        ),
    )
    return parser.parse_args(raw)


def close(actual: Any, expected: Any, tolerance: float = 1e-7) -> bool:
    return math.isclose(float(actual), float(expected), rel_tol=0.0, abs_tol=tolerance)


def validate_material(material: Any, policy: dict[str, Any]) -> list[str]:
    failures = []
    if material is None or not material.use_nodes or material.node_tree is None:
        return ["material_missing_or_not_node_based"]
    if any(node.type == "TEX_IMAGE" for node in material.node_tree.nodes):
        failures.append("material_contains_image_texture")
    shaders = [node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"]
    outputs = [node for node in material.node_tree.nodes if node.type == "OUTPUT_MATERIAL"]
    if len(shaders) != 1 or len(outputs) != 1:
        return failures + ["material_node_count_mismatch"]
    links = outputs[0].inputs["Surface"].links
    if len(links) != 1 or links[0].from_node != shaders[0]:
        failures.append("material_surface_link_mismatch")
    if material.get("render_resource_policy_id") != POLICY_ID:
        failures.append("material_policy_marker_mismatch")
    if material.get("semantic_encoding") is not False:
        failures.append("material_semantic_encoding_mismatch")
    expected = policy.get("material_override", {}).get("principled_inputs")
    if principled_input_record(material) != expected:
        failures.append("material_principled_input_record_mismatch")
    return failures


def validate_world(scene: Any) -> list[str]:
    failures = []
    world = scene.world
    if world is None or world.name != WORLD_NAME or not world.use_nodes:
        return ["deterministic_world_missing"]
    if world.get("render_resource_policy_id") != POLICY_ID:
        failures.append("world_policy_marker_mismatch")
    backgrounds = [node for node in world.node_tree.nodes if node.type == "BACKGROUND"]
    outputs = [node for node in world.node_tree.nodes if node.type == "OUTPUT_WORLD"]
    if len(backgrounds) != 1 or len(outputs) != 1:
        return failures + ["world_node_count_mismatch"]
    color = backgrounds[0].inputs["Color"].default_value
    if any(not close(value, expected) for value, expected in zip(color, WORLD_COLOR)):
        failures.append("world_color_mismatch")
    if not close(backgrounds[0].inputs["Strength"].default_value, WORLD_STRENGTH):
        failures.append("world_strength_mismatch")
    links = outputs[0].inputs["Surface"].links
    if len(links) != 1 or links[0].from_node != backgrounds[0]:
        failures.append("world_surface_link_mismatch")
    if any(node.type == "TEX_ENVIRONMENT" for node in world.node_tree.nodes):
        failures.append("world_contains_environment_texture")
    return failures


def validate_lights(scene: Any) -> tuple[list[str], list[dict[str, Any]]]:
    failures = []
    expected_names = {name for name, _direction in SUN_SPECS}
    policy_lights = [obj for obj in scene.objects if obj.name in expected_names]
    if {obj.name for obj in policy_lights} != expected_names:
        failures.append("deterministic_light_name_coverage_mismatch")
    records = []
    for obj in sorted(policy_lights, key=lambda item: item.name):
        data = obj.data
        record = {
            "name": obj.name,
            "type": data.type,
            "energy": float(data.energy),
            "color": [float(value) for value in data.color],
            "angle_radians": float(data.angle),
            "use_shadow": bool(data.use_shadow),
            "hide_render": bool(obj.hide_render),
        }
        records.append(record)
        if obj.type != "LIGHT" or data.type != "SUN":
            failures.append(f"light_type_mismatch:{obj.name}")
        if not close(data.energy, SUN_ENERGY):
            failures.append(f"light_energy_mismatch:{obj.name}")
        if any(not close(value, expected) for value, expected in zip(data.color, SUN_COLOR)):
            failures.append(f"light_color_mismatch:{obj.name}")
        if not close(data.angle, SUN_ANGLE_RADIANS):
            failures.append(f"light_angle_mismatch:{obj.name}")
        if data.use_shadow or obj.hide_render:
            failures.append(f"light_enablement_mismatch:{obj.name}")
        if data.get("render_resource_policy_id") != POLICY_ID:
            failures.append(f"light_data_policy_marker_mismatch:{obj.name}")
        if obj.get("render_resource_policy_id") != POLICY_ID:
            failures.append(f"light_object_policy_marker_mismatch:{obj.name}")
    unexpected_enabled = sorted(
        obj.name
        for obj in scene.objects
        if obj.type == "LIGHT" and not obj.hide_render and obj.name not in expected_names
    )
    failures.extend(f"unexpected_render_enabled_light:{name}" for name in unexpected_enabled)
    return failures, records


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_scene_path(path: Path) -> str:
    return logical_uri_for_path(
        "blender-output", path, repo_root=REPOSITORY_ROOT
    )


def main() -> None:
    args = script_args()
    scene_path = args.derived_scene.resolve()
    if Path(bpy.data.filepath).resolve() != scene_path:
        raise RuntimeError("Loaded scene does not match --derived-scene")
    checksum_before = file_sha256(scene_path)
    policy = load_json(args.policy.resolve())
    config = load_json(args.render_config.resolve())
    registry = strict_registry(args.registry.resolve())
    scene = bpy.context.scene

    failures = []
    if policy.get("policy_id") != POLICY_ID or policy.get("status") != "CONFIRMED":
        failures.append("policy_id_or_status_mismatch")
    if policy.get("derived_scene_sha256") != checksum_before:
        failures.append("derived_scene_checksum_mismatch")
    if config.get("config_id") != CONFIG_ID or config.get("status") != "CONFIRMED":
        failures.append("render_config_id_or_status_mismatch")
    if config.get("generation_authorized") is not False:
        failures.append("dataset_generation_unexpectedly_authorized")
    if file_sha256(args.source_scene.resolve()) != policy.get("source_scene_sha256"):
        failures.append("source_scene_checksum_mismatch")
    if file_sha256(args.input_scene.resolve()) != policy.get("input_scene_sha256"):
        failures.append("input_scene_checksum_mismatch")

    material = bpy.data.materials.get(MATERIAL_NAME)
    failures.extend(validate_material(material, policy))
    failures.extend(validate_world(scene))
    light_failures, light_records = validate_lights(scene)
    failures.extend(light_failures)
    failures.extend(
        f"view_layer_override_mismatch:{view_layer.name}"
        for view_layer in scene.view_layers
        if view_layer.material_override != material
    )
    failures.extend(render_config_differences(scene, config))

    expected_markers = {
        "resource_policy": "texture_agnostic",
        "render_resource_policy_id": POLICY_ID,
        "render_resource_policy_version": POLICY_VERSION,
        "render_config_id": CONFIG_ID,
        "authoritative_visual_fidelity": False,
        "geometry_ground_truth_authoritative": True,
        "diagnostic_only_no_dataset_generation": True,
        "input_scene_sha256": policy.get("input_scene_sha256"),
    }
    failures.extend(
        f"scene_marker_mismatch:{key}"
        for key, expected in expected_markers.items()
        if scene.get(key) != expected
    )

    runtime_before = scene_invariant_digests(scene, registry)
    unlinked = unlink_policy_lights(scene)
    core_invariants = scene_invariant_digests(scene, registry)
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
        scene, registry, automatic, bootstrap, require_ids=True
    )
    for light in unlinked:
        scene.collection.objects.link(light)
    runtime_after = scene_invariant_digests(scene, registry)
    expected_core = policy.get("input_invariants", {})
    core_mismatches = sorted(
        name
        for name, expected in expected_core.get("digests", {}).items()
        if name != "objective_scene"
        if core_invariants.get("digests", {}).get(name) != expected
    )
    if core_invariants.get("object_count") != expected_core.get("object_count"):
        core_mismatches.append("object_count")
    if core_mismatches:
        failures.append("unauthorized_core_scene_invariant_change")
    if runtime_before != runtime_after:
        failures.append("validator_runtime_cleanup_changed_scene_invariants")
    if identity.get("ids_verified") != 2777:
        failures.append("stable_id_count_mismatch")

    legacy_records, required_missing = legacy_runtime_dependencies()
    failures.extend(required_missing)
    if len(legacy_records) != 5:
        failures.append("legacy_resource_count_mismatch")
    policy_paths = {
        record["filename"]: record["referenced_filepath"]
        for record in policy.get("legacy_resources", [])
    }
    for record in legacy_records:
        if policy_paths.get(record["filename"]) != record["referenced_filepath"]:
            failures.append(f"legacy_path_mismatch:{record['filename']}")

    cameras = sorted(
        (obj for obj in scene.objects if obj.type == "CAMERA"), key=lambda obj: obj.name
    )
    eligible = [obj for obj in cameras if obj.name != EXCLUDED_CAMERA]
    invalid_cameras = [record for record in map(camera_record, eligible) if record["invalid_parameters"]]
    if len(cameras) != 30 or len(eligible) != 29 or invalid_cameras:
        failures.append("eligible_camera_contract_mismatch")

    checksum_after = file_sha256(scene_path)
    if checksum_after != checksum_before:
        failures.append("derived_scene_file_changed_during_validation")
    status = "PASS" if not failures else "BLOCKED"
    report = {
        "schema_name": "amidst.texture_agnostic_scene_validation",
        "schema_version": POLICY_VERSION,
        "status": status,
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_classification": "REVIEW_REQUIRED",
        "path_base": "repository_root",
        "policy_id": POLICY_ID,
        "render_config_id": CONFIG_ID,
        "derived_scene": canonical_scene_path(scene_path),
        "derived_scene_sha256": checksum_before,
        "checks": {
            "fresh_process": True,
            "source_and_input_checksums_match": not any(
                item in failures
                for item in ("source_scene_checksum_mismatch", "input_scene_checksum_mismatch")
            ),
            "material_override_exact": not any("material_" in item for item in failures),
            "deterministic_world_exact": not any("world_" in item for item in failures),
            "deterministic_lights_exact": not any("light" in item for item in failures),
            "render_config_exact": not any(
                item.startswith("locked_") for item in failures
            ),
            "core_scene_invariants_unchanged": (
                "unauthorized_core_scene_invariant_change" not in failures
            ),
            "legacy_paths_unchanged": not any(
                item.startswith("legacy_path_mismatch") for item in failures
            ),
            "runtime_required_missing_resource_count": len(required_missing),
            "stable_ids_verified": identity.get("ids_verified"),
            "eligible_camera_count": len(eligible),
            "dataset_generation_authorized": False,
            "gt_contract_changed": False,
        },
        "deterministic_light_records": light_records,
        "core_invariant_mismatches": core_mismatches,
        "authorized_objective_scene_difference": (
            "active deterministic render World only"
        ),
        "failures": sorted(set(failures)),
    }
    write_json(args.report.resolve(), report)
    args.human_report.resolve().write_text(
        "\n".join(
            [
                "# School v1 Texture-Agnostic Scene Validation v0.1.1",
                "",
                f"Status: `{status}`",
                "",
                f"- Derived scene: `{canonical_scene_path(scene_path)}`",
                f"- Derived SHA-256: `{checksum_before}`",
                f"- Stable IDs verified: {identity.get('ids_verified')}",
                f"- Eligible cameras: {len(eligible)}",
                f"- Deterministic render-enabled lights: {len(light_records)}",
                f"- Runtime-required missing resources: {len(required_missing)}",
                f"- Core scene invariants unchanged: `{str('unauthorized_core_scene_invariant_change' not in failures).lower()}`",
                f"- GT contract changed: `false`",
                f"- Dataset generation authorized: `false`",
                f"- Failures: `{sorted(set(failures))}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "failures": sorted(set(failures))}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
