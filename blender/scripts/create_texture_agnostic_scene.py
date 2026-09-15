#!/usr/bin/env python3
"""Create the approved texture-agnostic school_v1 first-slice scene."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import (  # noqa: E402
    SOURCE_SHA256,
    SUPPORTED_TYPES,
    SignatureBuilder,
    digest_record,
    file_sha256,
    load_identity_layer,
)
from persist_instance_ids import (  # noqa: E402
    EXCLUDED_CAMERA,
    camera_snapshot,
    finite_value,
    objective_scene_snapshot,
    save_blend,
    strict_registry,
    validate_registry_against_scene,
)
from validate_first_slice_readiness import render_config_differences  # noqa: E402


POLICY_ID = "amidst.school.texture-agnostic-render/0.1.0"
POLICY_VERSION = "0.1.0"
OVERRIDE_MATERIAL = "AMIDST_FirstSlice_Neutral_v0_1_0"
OUTPUT_NAME = "school_v1_first_slice_texture_agnostic_v0_1_0.blend"
LEGACY_RESOURCES = (
    "__Brick-antique_.jpg",
    "__Brick-antique__1.jpg",
    "__Glass_Sky_Reflection_.jpg",
    "__Wood-cherry_1.jpg",
    "__Wood-cherry_1_0.jpg",
)
SEMANTIC_KEYS = (
    "category",
    "annotation_status",
    "annotation_source",
    "annotation_version",
)


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-scene",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "blender/output/school_v1_ids_policy_1_0_1_r2.blend"
        ),
    )
    parser.add_argument(
        "--output-scene",
        type=Path,
        default=REPOSITORY_ROOT / "blender/output" / OUTPUT_NAME,
    )
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
        "--semantic-sidecar",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--resource-audit",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_missing_resource_audit.json",
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
        "--policy-output",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_creation.json"
        ),
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_creation.md"
        ),
    )
    return parser.parse_args(raw)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def scene_invariant_digests(scene: Any, registry: dict[str, Any]) -> dict[str, Any]:
    builder = SignatureBuilder(
        scene,
        registry["scene_id"],
        registry["scene_version"],
        registry["source_sha256"],
    )
    objects = sorted(scene.objects, key=lambda item: item.name)
    object_names = [obj.name for obj in objects]
    hierarchy = {
        obj.name: {
            "parent": obj.parent.name if obj.parent else None,
            "parent_type": obj.parent_type if obj.parent else None,
            "parent_bone": (
                obj.parent_bone
                if obj.parent and obj.parent_type == "BONE"
                else None
            ),
        }
        for obj in objects
    }
    collections = {
        obj.name: sorted(collection.name for collection in obj.users_collection)
        for obj in objects
    }
    transforms = {
        obj.name: {
            "location": finite_value(list(obj.location)),
            "rotation_mode": obj.rotation_mode,
            "rotation_euler": finite_value(list(obj.rotation_euler)),
            "rotation_quaternion": finite_value(list(obj.rotation_quaternion)),
            "rotation_axis_angle": finite_value(list(obj.rotation_axis_angle)),
            "scale": finite_value(list(obj.scale)),
            "matrix_world": [
                [finite_value(value) for value in row] for row in obj.matrix_world
            ],
            "dimensions": finite_value(list(obj.dimensions)),
        }
        for obj in objects
    }
    geometry_and_material_structure = {}
    for obj in objects:
        if obj.name == EXCLUDED_CAMERA:
            signature: Any = {"excluded_camera": camera_snapshot(obj.data)}
        elif obj.type in SUPPORTED_TYPES:
            signature = builder.data_signature(obj)
        else:
            signature = {"unsupported_type": obj.type}
        geometry_and_material_structure[obj.name] = {
            "object_type": obj.type,
            "data_name": obj.data.name if obj.data else None,
            "data_signature": signature,
            "material_assignments": [
                slot.material.name if slot.material else None
                for slot in obj.material_slots
            ],
        }
    stable_ids = {obj.name: obj.get("instance_id") for obj in objects}
    semantic_state = {
        obj.name: {key: obj.get(key) for key in SEMANTIC_KEYS if key in obj}
        for obj in objects
    }
    cameras = {
        obj.name: camera_snapshot(obj.data)
        for obj in objects
        if obj.type == "CAMERA"
    }
    unit_settings = {
        "system": scene.unit_settings.system,
        "scale_length": scene.unit_settings.scale_length,
        "length_unit": scene.unit_settings.length_unit,
    }
    objective = objective_scene_snapshot(scene, builder)
    sections = {
        "object_names": object_names,
        "hierarchy": hierarchy,
        "collection_membership": collections,
        "object_transforms": transforms,
        "geometry_topology_material_structure": geometry_and_material_structure,
        "stable_ids": stable_ids,
        "semantic_state": semantic_state,
        "cameras": cameras,
        "scene_units": unit_settings,
        "objective_scene": objective,
    }
    return {
        "object_count": len(objects),
        "digests": {name: digest_record(value) for name, value in sections.items()},
    }


def neutral_material() -> Any:
    if bpy.data.materials.get(OVERRIDE_MATERIAL) is not None:
        raise RuntimeError(f"Override material already exists: {OVERRIDE_MATERIAL}")
    material = bpy.data.materials.new(OVERRIDE_MATERIAL)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "AMIDST_Material_Output"
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.name = "AMIDST_Neutral_Opaque"
    shader.inputs["Base Color"].default_value = (0.18, 0.18, 0.18, 1.0)
    shader.inputs["Metallic"].default_value = 0.0
    shader.inputs["Roughness"].default_value = 0.8
    shader.inputs["IOR"].default_value = 1.45
    shader.inputs["Alpha"].default_value = 1.0
    transmission = shader.inputs.get("Transmission Weight")
    if transmission is not None:
        transmission.default_value = 0.0
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    material.diffuse_color = (0.18, 0.18, 0.18, 1.0)
    material["render_resource_policy_id"] = POLICY_ID
    material["semantic_encoding"] = False
    return material


def main() -> None:
    args = script_args()
    open_path = Path(bpy.data.filepath).resolve()
    input_path = args.input_scene.resolve()
    output_path = args.output_scene.resolve()
    source_path = args.source_scene.resolve()
    if open_path != input_path:
        raise RuntimeError(f"Loaded scene does not match --input-scene: {open_path}")
    if input_path == source_path or source_path.parent in input_path.parents:
        raise RuntimeError("Refusing to mutate the immutable source scene")
    if output_path.parent != (REPOSITORY_ROOT / "blender/output").resolve():
        raise RuntimeError("Derived scene must be written directly under blender/output")
    if output_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing derived scene: {output_path}")
    if output_path.name != OUTPUT_NAME:
        raise RuntimeError(f"Unexpected versioned output filename: {output_path.name}")

    input_checksum = file_sha256(input_path)
    source_checksum = file_sha256(source_path)
    if source_checksum != SOURCE_SHA256:
        raise RuntimeError("Immutable source checksum changed")

    registry = strict_registry(args.registry.resolve())
    render_config = load_json(args.render_config.resolve())
    semantic_sidecar = load_json(args.semantic_sidecar.resolve())
    resource_audit = load_json(args.resource_audit.resolve())
    if input_checksum != render_config.get("identity_output_scene_sha256"):
        raise RuntimeError("Input scene checksum does not match the render contract")
    if render_config.get("status") != "CONFIRMED":
        raise RuntimeError("Render config is not confirmed")
    if render_config_differences(bpy.context.scene, render_config):
        raise RuntimeError("Input scene does not match the confirmed render config")
    if semantic_sidecar.get("status") != "CONFIRMED":
        raise RuntimeError("Semantic baseline is not confirmed")
    if semantic_sidecar.get("reviewed_annotations") != []:
        raise RuntimeError("Unexpected reviewed semantic annotations")
    if semantic_sidecar.get("unreviewed_default") != {
        "annotation_source": "no_trusted_semantic_evidence",
        "annotation_status": "needs_review",
        "category": "Unknown",
        "review_status": "NOT_REVIEWED",
    }:
        raise RuntimeError("Semantic default differs from Unknown / needs_review")

    audit_by_name = {
        record["filename"]: record for record in resource_audit.get("resources", [])
    }
    if set(audit_by_name) != set(LEGACY_RESOURCES):
        raise RuntimeError("Legacy resource audit coverage mismatch")
    for name in LEGACY_RESOURCES:
        record = audit_by_name[name]
        if record.get("resolution_status") != "REVIEW_REQUIRED":
            raise RuntimeError(f"Legacy resource status changed unexpectedly: {name}")
        if record.get("other_node_usage"):
            raise RuntimeError(f"Legacy resource is used outside material nodes: {name}")

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
    if identity["ids_verified"] != 2777:
        raise RuntimeError("Stable-ID count mismatch")

    before = scene_invariant_digests(bpy.context.scene, registry)
    material = neutral_material()
    changes: list[dict[str, Any]] = [
        {
            "datablock_path": f"Material:{OVERRIDE_MATERIAL}",
            "before": None,
            "after": "created neutral opaque node material",
        }
    ]
    for view_layer in bpy.context.scene.view_layers:
        before_override = (
            view_layer.material_override.name if view_layer.material_override else None
        )
        if before_override is not None:
            raise RuntimeError(
                f"Unexpected pre-existing view-layer override: {view_layer.name}"
            )
        view_layer.material_override = material
        changes.append(
            {
                "datablock_path": (
                    f"Scene:{bpy.context.scene.name}/ViewLayer:"
                    f"{view_layer.name}.material_override"
                ),
                "before": before_override,
                "after": OVERRIDE_MATERIAL,
            }
        )

    markers = {
        "resource_policy": "texture_agnostic",
        "render_resource_policy_id": POLICY_ID,
        "render_resource_policy_version": POLICY_VERSION,
        "authoritative_visual_fidelity": False,
        "geometry_ground_truth_authoritative": True,
        "render_config_id": render_config["config_id"],
        "input_scene_sha256": input_checksum,
    }
    for key, value in markers.items():
        if key in bpy.context.scene:
            raise RuntimeError(f"Refusing to replace existing scene marker: {key}")
        bpy.context.scene[key] = value
        changes.append(
            {
                "datablock_path": f"Scene:{bpy.context.scene.name}[{key!r}]",
                "before": None,
                "after": value,
            }
        )

    after = scene_invariant_digests(bpy.context.scene, registry)
    invariant_mismatches = sorted(
        name
        for name, digest in before["digests"].items()
        if after["digests"].get(name) != digest
    )
    if before["object_count"] != after["object_count"] or invariant_mismatches:
        raise RuntimeError(
            "Unauthorized in-memory scene mutation: "
            f"object_count={before['object_count']}/{after['object_count']} "
            f"digests={invariant_mismatches}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_blend(output_path, copy=False)
    if file_sha256(input_path) != input_checksum:
        raise RuntimeError("Validated ID input scene changed while creating output")
    if file_sha256(source_path) != source_checksum:
        raise RuntimeError("Immutable source scene changed while creating output")
    output_checksum = file_sha256(output_path)

    unavailable = [
        {
            "filename": name,
            "referenced_filepath": audit_by_name[name]["referenced_filepath"],
            "image_datablock": audit_by_name[name]["image_datablock"]["name"],
            "affected_materials": [
                usage["material"]
                for usage in audit_by_name[name]["material_node_usage"]
            ],
            "affected_render_object_count": audit_by_name[name][
                "render_enabled_object_count"
            ],
            "legacy_status": "historically_unresolved",
            "first_slice_runtime_status": "not_required_by_texture_agnostic_policy",
        }
        for name in LEGACY_RESOURCES
    ]
    policy = {
        "schema_name": "amidst.first_slice_render_resource_policy",
        "schema_version": POLICY_VERSION,
        "policy_id": POLICY_ID,
        "status": "CONFIRMED",
        "repository_classification": "REVIEW_REQUIRED",
        "approval_basis": (
            "Explicit human approval of texture-agnostic first-slice rendering "
            "on 2026-09-14."
        ),
        "resource_policy": "texture_agnostic",
        "authoritative_visual_fidelity": False,
        "geometry_spatial_ground_truth_authoritative": True,
        "source_scene": "blender/source/school_v1.blend",
        "source_scene_sha256": source_checksum,
        "input_scene": str(input_path.relative_to(REPOSITORY_ROOT)),
        "input_scene_sha256": input_checksum,
        "derived_scene": str(output_path.relative_to(REPOSITORY_ROOT)),
        "derived_scene_sha256": output_checksum,
        "blender_version": bpy.app.version_string,
        "blender_build_hash": bpy.app.build_hash.decode("ascii"),
        "authoritative_render_config": render_config["config_id"],
        "material_override": {
            "method": "set ViewLayer.material_override on every view layer",
            "material": OVERRIDE_MATERIAL,
            "base_color_linear_rgba": [0.18, 0.18, 0.18, 1.0],
            "metallic": 0.0,
            "roughness": 0.8,
            "alpha": 1.0,
            "transmission_weight": 0.0,
            "external_image_nodes": 0,
            "semantic_encoding": False,
            "per_object_variation": False,
            "visibility_behavior": "opaque geometry first-hit",
        },
        "legacy_resources": unavailable,
        "legacy_resource_audit": str(args.resource_audit.relative_to(REPOSITORY_ROOT)),
        "legacy_paths_modified": False,
        "runtime_required_missing_resource_count": 0,
        "input_invariants": before,
        "authorized_datablock_changes": changes,
        "unauthorized_scene_change_count_before_save": 0,
        "fresh_process_validation": (
            "data/reports/school_v1_texture_agnostic_scene_validation.json"
        ),
    }
    report = {
        "schema_name": "amidst.texture_agnostic_scene_creation",
        "schema_version": "0.1.0",
        "status": "CREATED_PENDING_FRESH_VALIDATION",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_classification": "REVIEW_REQUIRED",
        "policy_id": POLICY_ID,
        "input_scene": str(input_path),
        "input_scene_sha256": input_checksum,
        "derived_scene": str(output_path),
        "derived_scene_sha256": output_checksum,
        "stable_ids_verified_before_save": identity["ids_verified"],
        "object_count": before["object_count"],
        "authorized_datablock_changes": changes,
        "unauthorized_scene_change_count": 0,
        "input_invariants": before,
        "runtime_required_missing_resource_count": 0,
        "images_generated": False,
    }
    write_json(args.policy_output, policy)
    write_json(args.report, report)
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    args.human_report.write_text(
        "\n".join(
            [
                "# School v1 Texture-Agnostic Scene Creation",
                "",
                "Status: `CREATED_PENDING_FRESH_VALIDATION`",
                "",
                f"- Policy: `{POLICY_ID}`",
                f"- Input SHA-256: `{input_checksum}`",
                f"- Derived scene: `{output_path}`",
                f"- Derived SHA-256: `{output_checksum}`",
                f"- Stable IDs verified before save: {identity['ids_verified']}",
                f"- Object count: {before['object_count']}",
                "- Runtime-required missing resources: 0",
                "- Unauthorized in-memory changes: 0",
                "- Images generated: false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "derived_scene_sha256": output_checksum,
                "stable_ids_verified": identity["ids_verified"],
                "object_count": before["object_count"],
                "unauthorized_scene_change_count": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
