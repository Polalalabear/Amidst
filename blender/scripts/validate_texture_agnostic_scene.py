#!/usr/bin/env python3
"""Fresh-process validation for the approved texture-agnostic render scene."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import sys
from typing import Any

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_paths import root_path  # noqa: E402
from assign_instance_ids import file_sha256, load_identity_layer  # noqa: E402
from audit_missing_render_resources import image_nodes  # noqa: E402
from create_texture_agnostic_scene import (  # noqa: E402
    LEGACY_RESOURCES,
    OUTPUT_NAME,
    OVERRIDE_MATERIAL,
    POLICY_ID,
    scene_invariant_digests,
)
from persist_instance_ids import (  # noqa: E402
    EXCLUDED_CAMERA,
    strict_registry,
    validate_registry_against_scene,
)
from validate_first_slice_readiness import (  # noqa: E402
    camera_record,
    render_config_differences,
)


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--derived-scene",
        type=Path,
        default=root_path(
            "blender-output", OUTPUT_NAME, repo_root=REPOSITORY_ROOT
        ),
    )
    parser.add_argument(
        "--source-scene",
        type=Path,
        default=root_path(
            "blender-source", "school_v1.blend", repo_root=REPOSITORY_ROOT
        ),
    )
    parser.add_argument(
        "--input-scene",
        type=Path,
        default=root_path(
            "blender-output",
            "school_v1_ids_policy_1_0_1_r2.blend",
            repo_root=REPOSITORY_ROOT,
        ),
    )
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
            / "data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json"
        ),
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
        "--semantic-sidecar",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_validation.json"
        ),
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_validation.md"
        ),
    )
    return parser.parse_args(raw)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def close(actual: float, expected: float) -> bool:
    expected_float32 = struct.unpack("!f", struct.pack("!f", float(expected)))[0]
    return float(actual) == expected_float32


def validate_override_material(material: Any) -> list[str]:
    failures: list[str] = []
    if material is None or not material.use_nodes or material.node_tree is None:
        return ["neutral_override_material_missing_or_not_node_based"]
    image_node_count = sum(node.type == "TEX_IMAGE" for node in material.node_tree.nodes)
    if image_node_count:
        failures.append("neutral_override_contains_image_nodes")
    shaders = [node for node in material.node_tree.nodes if node.type == "BSDF_PRINCIPLED"]
    outputs = [node for node in material.node_tree.nodes if node.type == "OUTPUT_MATERIAL"]
    if len(shaders) != 1 or len(outputs) != 1:
        failures.append("neutral_override_node_count_mismatch")
        return failures
    shader = shaders[0]
    expected_inputs = {
        "Base Color": (0.18, 0.18, 0.18, 1.0),
        "Metallic": 0.0,
        "Roughness": 0.8,
        "IOR": 1.45,
        "Alpha": 1.0,
        "Weight": 1.0,
        "Transmission Weight": 0.0,
    }
    for name, expected in expected_inputs.items():
        socket = next(
            (item for item in shader.inputs if item.identifier == name),
            None,
        )
        if socket is None:
            failures.append(f"neutral_override_missing_input:{name}")
            continue
        actual = socket.default_value
        if isinstance(expected, tuple):
            if len(actual) != len(expected) or any(
                not close(value, target) for value, target in zip(actual, expected)
            ):
                failures.append(f"neutral_override_input_mismatch:{name}")
        elif not close(actual, expected):
            failures.append(f"neutral_override_input_mismatch:{name}")
    surface_links = outputs[0].inputs["Surface"].links
    if len(surface_links) != 1 or surface_links[0].from_node != shader:
        failures.append("neutral_override_surface_link_mismatch")
    if material.get("render_resource_policy_id") != POLICY_ID:
        failures.append("neutral_override_policy_marker_mismatch")
    if material.get("semantic_encoding") is not False:
        failures.append("neutral_override_semantic_encoding_mismatch")
    return failures


def legacy_runtime_dependencies() -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    required_missing: list[str] = []
    for filename in LEGACY_RESOURCES:
        matches = [image for image in bpy.data.images if image.name == filename]
        if len(matches) != 1:
            required_missing.append(f"legacy_image_datablock_count:{filename}")
            continue
        image = matches[0]
        material_uses = []
        for material in bpy.data.materials:
            nodes = image_nodes(material.node_tree, image)
            if nodes:
                material_uses.append(
                    {"material": material.name, "nodes": nodes}
                )
        other_uses = []
        for datablocks, kind in (
            (bpy.data.worlds, "world"),
            (bpy.data.lights, "light"),
            (bpy.data.scenes, "scene_compositor"),
        ):
            for datablock in datablocks:
                nodes = image_nodes(getattr(datablock, "node_tree", None), image)
                if nodes:
                    other_uses.append(
                        {
                            "datablock_type": kind,
                            "datablock_name": datablock.name,
                            "nodes": nodes,
                        }
                    )
        resolved = Path(bpy.path.abspath(image.filepath)).resolve()
        if other_uses:
            required_missing.append(f"legacy_image_used_outside_overridden_material:{filename}")
        records.append(
            {
                "filename": filename,
                "referenced_filepath": image.filepath,
                "resolved_filepath": str(resolved),
                "exists": resolved.is_file(),
                "packed": bool(image.packed_file)
                or bool(getattr(image, "packed_files", ())),
                "material_node_usage": material_uses,
                "other_node_usage": other_uses,
                "runtime_required": bool(other_uses),
            }
        )
    return records, required_missing


def main() -> None:
    args = script_args()
    scene_path = Path(bpy.data.filepath).resolve()
    expected_scene = args.derived_scene.resolve()
    if scene_path != expected_scene:
        raise RuntimeError(f"Loaded scene does not match --derived-scene: {scene_path}")
    source_root = root_path("blender-source", repo_root=REPOSITORY_ROOT)
    if scene_path == source_root or source_root in scene_path.parents:
        raise RuntimeError("Refusing to validate the immutable source scene directly")

    policy = load_json(args.policy.resolve())
    task_contract = load_json(args.task_contract.resolve())
    metadata_schema = load_json(args.metadata_schema.resolve())
    render_config = load_json(args.render_config.resolve())
    semantic_sidecar = load_json(args.semantic_sidecar.resolve())
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

    current_checksum = file_sha256(scene_path)
    invariants = scene_invariant_digests(bpy.context.scene, registry)
    expected_invariants = policy.get("input_invariants", {})
    invariant_mismatches = sorted(
        name
        for name, expected in expected_invariants.get("digests", {}).items()
        if invariants.get("digests", {}).get(name) != expected
    )
    if invariants.get("object_count") != expected_invariants.get("object_count"):
        invariant_mismatches.append("object_count")

    material = bpy.data.materials.get(OVERRIDE_MATERIAL)
    material_failures = validate_override_material(material)
    view_layer_failures = [
        view_layer.name
        for view_layer in bpy.context.scene.view_layers
        if view_layer.material_override != material
    ]
    expected_markers = {
        "resource_policy": "texture_agnostic",
        "render_resource_policy_id": POLICY_ID,
        "render_resource_policy_version": "0.1.0",
        "authoritative_visual_fidelity": False,
        "geometry_ground_truth_authoritative": True,
        "render_config_id": "amidst.school.first-slice-render/0.1.0",
        "input_scene_sha256": policy.get("input_scene_sha256"),
    }
    marker_mismatches = [
        key
        for key, expected in expected_markers.items()
        if bpy.context.scene.get(key) != expected
    ]

    legacy_records, required_missing = legacy_runtime_dependencies()
    legacy_paths_match = all(
        next(
            item["referenced_filepath"]
            for item in policy["legacy_resources"]
            if item["filename"] == record["filename"]
        )
        == record["referenced_filepath"]
        for record in legacy_records
    )
    all_legacy_unavailable = (
        len(legacy_records) == 5
        and all(not record["exists"] and not record["packed"] for record in legacy_records)
    )
    cameras = sorted(
        (obj for obj in bpy.context.scene.objects if obj.type == "CAMERA"),
        key=lambda obj: obj.name,
    )
    eligible = [obj for obj in cameras if obj.name != EXCLUDED_CAMERA]
    invalid_cameras = [
        record for record in map(camera_record, eligible) if record["invalid_parameters"]
    ]
    helper = next((obj for obj in cameras if obj.name == EXCLUDED_CAMERA), None)
    render_mismatches = render_config_differences(bpy.context.scene, render_config)
    visibility_valid = (
        not material_failures
        and not view_layer_failures
        and not invariant_mismatches
        and task_contract.get("visibility_definition", {}).get("version")
        == "amidst.school.first-slice-visibility/1.0.0"
        and task_contract.get("visibility_definition", {}).get(
            "unsupported_material_behavior"
        )
        is not None
    )

    checks = {
        "policy_confirmed_texture_agnostic": (
            policy.get("status") == "CONFIRMED"
            and policy.get("policy_id") == POLICY_ID
            and policy.get("resource_policy") == "texture_agnostic"
            and policy.get("authoritative_visual_fidelity") is False
        ),
        "derived_scene_checksum_matches_policy": (
            policy.get("derived_scene_sha256") == current_checksum
        ),
        "source_and_input_scene_checksums_unchanged": (
            file_sha256(args.source_scene.resolve()) == policy.get("source_scene_sha256")
            and file_sha256(args.input_scene.resolve()) == policy.get("input_scene_sha256")
        ),
        "object_count_unchanged": invariants.get("object_count") == 2778,
        "object_names_unchanged": "object_names" not in invariant_mismatches,
        "hierarchy_unchanged": "hierarchy" not in invariant_mismatches,
        "collection_membership_unchanged": (
            "collection_membership" not in invariant_mismatches
        ),
        "object_transforms_unchanged": "object_transforms" not in invariant_mismatches,
        "geometry_topology_material_structure_unchanged": (
            "geometry_topology_material_structure" not in invariant_mismatches
        ),
        "stable_ids_unchanged": (
            identity["ids_verified"] == 2777
            and "stable_ids" not in invariant_mismatches
        ),
        "semantic_state_unchanged": (
            "semantic_state" not in invariant_mismatches
            and semantic_sidecar.get("reviewed_annotations") == []
            and semantic_sidecar.get("unreviewed_default", {}).get("category")
            == "Unknown"
            and semantic_sidecar.get("unreviewed_default", {}).get(
                "annotation_status"
            )
            == "needs_review"
        ),
        "camera_count_is_30": len(cameras) == 30,
        "eligible_camera_count_is_29": len(eligible) == 29,
        "eligible_cameras_valid": not invalid_cameras,
        "excluded_helper_camera_remains_excluded": (
            helper is not None and helper.get("instance_id") is None
        ),
        "neutral_override_material_valid": not material_failures,
        "all_view_layers_use_neutral_override": not view_layer_failures,
        "legacy_resource_paths_preserved": legacy_paths_match,
        "five_legacy_resources_remain_recorded_unavailable": all_legacy_unavailable,
        "zero_unresolved_resources_required_by_approved_render_policy": (
            not required_missing
            and policy.get("runtime_required_missing_resource_count") == 0
        ),
        "render_config_matches_authoritative_contract": not render_mismatches,
        "task_contract_authoritative": (
            task_contract.get("status") == "CONFIRMED"
            and task_contract.get("contract_id")
            == "amidst.school.first-dataset-slice/0.1.0"
        ),
        "metadata_schema_authoritative": (
            metadata_schema.get("$id")
            == "amidst.first-dataset-slice.metadata/0.1.0"
        ),
        "visibility_occlusion_semantics_valid": visibility_valid,
    }
    failures = sorted(key for key, value in checks.items() if value is not True)
    unauthorized = sorted(
        set(invariant_mismatches + material_failures + view_layer_failures + marker_mismatches)
    )
    status = "PASS" if not failures and not unauthorized else "REVIEW_REQUIRED"
    report = {
        "schema_name": "amidst.texture_agnostic_scene_validation",
        "schema_version": "0.1.0",
        "status": status,
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_classification": "REVIEW_REQUIRED",
        "policy_id": POLICY_ID,
        "derived_scene": str(scene_path),
        "derived_scene_sha256": current_checksum,
        "source_scene_sha256": file_sha256(args.source_scene.resolve()),
        "input_scene_sha256": file_sha256(args.input_scene.resolve()),
        "checks": checks,
        "stable_ids_verified": identity["ids_verified"],
        "object_count": len(bpy.context.scene.objects),
        "camera_count": len(cameras),
        "eligible_camera_count": len(eligible),
        "invalid_eligible_camera_count": len(invalid_cameras),
        "legacy_resources": legacy_records,
        "legacy_resource_count": len(legacy_records),
        "runtime_required_missing_resource_count": len(required_missing),
        "render_config_mismatches": render_mismatches,
        "invariant_mismatches": invariant_mismatches,
        "unauthorized_scene_changes": unauthorized,
        "unauthorized_scene_change_count": len(unauthorized),
        "images_generated": False,
        "pilot_generation_executed": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    args.human_report.write_text(
        "\n".join(
            [
                "# School v1 Texture-Agnostic Scene Validation",
                "",
                f"Status: `{status}`",
                "",
                f"- Derived SHA-256: `{current_checksum}`",
                f"- Stable IDs verified: {identity['ids_verified']}",
                f"- Objects: {len(bpy.context.scene.objects)}",
                f"- Eligible cameras: {len(eligible)}; invalid: {len(invalid_cameras)}",
                f"- Legacy resources recorded unavailable: {len(legacy_records)}",
                f"- Runtime-required missing resources: {len(required_missing)}",
                f"- Unauthorized scene changes: {len(unauthorized)}",
                "- Pilot generation executed: false",
                "",
                "## Failures",
                "",
                *([f"- `{failure}`" for failure in failures] or ["- None"]),
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": status,
                "stable_ids_verified": identity["ids_verified"],
                "eligible_camera_count": len(eligible),
                "runtime_required_missing_resource_count": len(required_missing),
                "unauthorized_scene_change_count": len(unauthorized),
            },
            sort_keys=True,
        )
    )
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
