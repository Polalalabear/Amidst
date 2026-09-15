#!/usr/bin/env python3
"""Create the approved deterministic texture-agnostic school_v1 scene v0.1.1."""

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
    file_sha256,
    load_identity_layer,
)
from create_texture_agnostic_scene import (  # noqa: E402
    LEGACY_RESOURCES,
    load_json,
    scene_invariant_digests,
)
from persist_instance_ids import (  # noqa: E402
    save_blend,
    strict_registry,
    validate_registry_against_scene,
)
from render_policy_v0_1_1 import (  # noqa: E402
    CONFIG_ID,
    MATERIAL_NAME,
    OUTPUT_NAME,
    POLICY_ID,
    POLICY_VERSION,
    SUN_SPECS,
    WORLD_NAME,
    create_lights,
    create_material,
    create_world,
    light_record,
    principled_input_record,
    unlink_policy_lights,
)
from validate_first_slice_readiness import render_config_differences  # noqa: E402


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-scene", type=Path, required=True)
    parser.add_argument("--output-scene", type=Path, required=True)
    parser.add_argument("--source-scene", type=Path, required=True)
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
            / "data/metadata/first_dataset_slice_render_config_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--policy-output",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/metadata/first_dataset_slice_render_resource_policy_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_creation_v0_1_1.json"
        ),
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_texture_agnostic_scene_creation_v0_1_1.md"
        ),
    )
    return parser.parse_args(raw)


def write_json_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_scene_path(kind: str, path: Path) -> str:
    return f"blender/{kind}/{path.name}"


def main() -> None:
    args = script_args()
    input_path = args.input_scene.resolve()
    output_path = args.output_scene.resolve()
    source_path = args.source_scene.resolve()
    if Path(bpy.data.filepath).resolve() != input_path:
        raise RuntimeError("Loaded scene does not match --input-scene")
    if output_path.name != OUTPUT_NAME or output_path.parent.name != "output":
        raise RuntimeError(f"Unexpected versioned output path: {output_path}")
    if output_path.exists():
        raise RuntimeError(f"Refusing to overwrite derived scene: {output_path}")
    if input_path == source_path or output_path == source_path:
        raise RuntimeError("Refusing to mutate or overwrite the immutable source scene")

    input_checksum = file_sha256(input_path)
    source_checksum = file_sha256(source_path)
    if source_checksum != SOURCE_SHA256:
        raise RuntimeError("Immutable source checksum changed")

    config = load_json(args.render_config.resolve())
    if config.get("status") != "CONFIRMED" or config.get("config_id") != CONFIG_ID:
        raise RuntimeError("Render config v0.1.1 is not confirmed")
    if config.get("generation_authorized") is not False:
        raise RuntimeError("Diagnostic config must not authorize dataset generation")
    if input_checksum != config.get("identity_output_scene_sha256"):
        raise RuntimeError("Input scene checksum does not match render config v0.1.1")
    config_mismatches = render_config_differences(bpy.context.scene, config)
    allowed_input_render_differences = ["locked_render_values.dither_intensity"]
    if config_mismatches != allowed_input_render_differences:
        raise RuntimeError(f"Input render settings differ: {config_mismatches}")
    previous_dither = float(bpy.context.scene.render.dither_intensity)
    bpy.context.scene.render.dither_intensity = config["locked_render_values"][
        "dither_intensity"
    ]
    if render_config_differences(bpy.context.scene, config):
        raise RuntimeError("Unable to apply the approved dither-disabled render config")

    semantic = load_json(args.semantic_sidecar.resolve())
    if semantic.get("status") != "CONFIRMED" or semantic.get("reviewed_annotations") != []:
        raise RuntimeError("Semantic baseline is not the confirmed category-agnostic baseline")
    resource_audit = load_json(args.resource_audit.resolve())
    audit_by_name = {
        record["filename"]: record for record in resource_audit.get("resources", [])
    }
    if set(audit_by_name) != set(LEGACY_RESOURCES):
        raise RuntimeError("Legacy resource audit coverage mismatch")
    if any(audit_by_name[name].get("other_node_usage") for name in LEGACY_RESOURCES):
        raise RuntimeError("Legacy resource is used outside an overridden material path")

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
    if identity["ids_verified"] != 2777:
        raise RuntimeError("Stable-ID count mismatch")

    scene = bpy.context.scene
    render_enabled_before = [
        obj.name for obj in scene.objects if obj.type == "LIGHT" and not obj.hide_render
    ]
    if render_enabled_before:
        raise RuntimeError(f"Unexpected render-enabled input lights: {render_enabled_before}")
    if any(view_layer.material_override is not None for view_layer in scene.view_layers):
        raise RuntimeError("Input scene already has a material override")

    before = scene_invariant_digests(scene, registry)
    previous_world = scene.world.name if scene.world else None
    material = create_material()
    world = create_world()
    lights = create_lights(scene)
    scene.world = world
    changes: list[dict[str, Any]] = [
        {
            "datablock_path": f"Scene:{scene.name}.render.dither_intensity",
            "before": previous_dither,
            "after": float(scene.render.dither_intensity),
        },
        {
            "datablock_path": f"Material:{MATERIAL_NAME}",
            "before": None,
            "after": "created deterministic neutral opaque Principled material",
        },
        {
            "datablock_path": f"World:{WORLD_NAME}",
            "before": None,
            "after": "created deterministic node World",
        },
        {
            "datablock_path": f"Scene:{scene.name}.world",
            "before": previous_world,
            "after": WORLD_NAME,
        },
    ]
    for view_layer in scene.view_layers:
        view_layer.material_override = material
        changes.append(
            {
                "datablock_path": (
                    f"Scene:{scene.name}/ViewLayer:{view_layer.name}.material_override"
                ),
                "before": None,
                "after": MATERIAL_NAME,
            }
        )
    for light in lights:
        changes.extend(
            [
                {
                    "datablock_path": f"Light:{light.data.name}",
                    "before": None,
                    "after": "created deterministic shadow-disabled Sun",
                },
                {
                    "datablock_path": f"Object:{light.name}",
                    "before": None,
                    "after": "created deterministic render-only light object",
                },
            ]
        )

    markers = {
        "resource_policy": "texture_agnostic",
        "render_resource_policy_id": POLICY_ID,
        "render_resource_policy_version": POLICY_VERSION,
        "render_config_id": CONFIG_ID,
        "authoritative_visual_fidelity": False,
        "geometry_ground_truth_authoritative": True,
        "diagnostic_only_no_dataset_generation": True,
        "input_scene_sha256": input_checksum,
    }
    for key, value in markers.items():
        if key in scene:
            raise RuntimeError(f"Refusing to replace scene marker: {key}")
        scene[key] = value
        changes.append(
            {
                "datablock_path": f"Scene:{scene.name}[{key!r}]",
                "before": None,
                "after": value,
            }
        )

    unlinked = unlink_policy_lights(scene)
    if {obj.name for obj in unlinked} != {name for name, _direction in SUN_SPECS}:
        raise RuntimeError("Authorized light unlink coverage mismatch")
    after_without_policy_lights = scene_invariant_digests(scene, registry)
    for light in unlinked:
        scene.collection.objects.link(light)
    invariant_mismatches = sorted(
        name
        for name, digest in before["digests"].items()
        if name != "objective_scene"
        if after_without_policy_lights["digests"].get(name) != digest
    )
    if before["object_count"] != after_without_policy_lights["object_count"] or invariant_mismatches:
        raise RuntimeError(
            "Unauthorized scene invariant changed before save: "
            f"object_count={before['object_count']}/"
            f"{after_without_policy_lights['object_count']} "
            f"digests={invariant_mismatches}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_blend(output_path, copy=False)
    if file_sha256(input_path) != input_checksum:
        raise RuntimeError("Validated stable-ID input scene changed")
    if file_sha256(source_path) != source_checksum:
        raise RuntimeError("Immutable source scene changed")
    output_checksum = file_sha256(output_path)

    unavailable = [
        {
            "filename": name,
            "referenced_filepath": audit_by_name[name]["referenced_filepath"],
            "image_datablock": audit_by_name[name]["image_datablock"]["name"],
            "legacy_status": "historically_unresolved",
            "runtime_status": "not_required_by_texture_agnostic_policy",
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
            "Explicit human approval on 2026-09-15 for deterministic v0.1.1 "
            "texture-agnostic diagnostic rendering without a dataset pilot."
        ),
        "resource_policy": "texture_agnostic",
        "authoritative_visual_fidelity": False,
        "geometry_spatial_ground_truth_authoritative": True,
        "source_scene": canonical_scene_path("source", source_path),
        "source_scene_sha256": source_checksum,
        "input_scene": canonical_scene_path("output", input_path),
        "input_scene_sha256": input_checksum,
        "derived_scene": canonical_scene_path("output", output_path),
        "derived_scene_sha256": output_checksum,
        "blender_version": bpy.app.version_string,
        "blender_build_hash": bpy.app.build_hash.decode("ascii"),
        "authoritative_render_config": CONFIG_ID,
        "material_override": {
            "method": "set ViewLayer.material_override on every view layer",
            "material": MATERIAL_NAME,
            "shader": "Principled BSDF",
            "principled_inputs": principled_input_record(material),
            "external_image_nodes": 0,
            "semantic_encoding": False,
            "per_object_variation": False,
            "object_material_slots_modified": False,
            "visibility_behavior": "opaque geometry first-hit",
        },
        "illumination": {
            "viewport_or_studio_light_dependency": False,
            "world": {
                "name": WORLD_NAME,
                "color_linear_rgba": [0.02, 0.02, 0.02, 1.0],
                "strength": 0.25,
            },
            "lights": [light_record(light) for light in lights],
            "camera_specific_tuning": False,
        },
        "legacy_resources": unavailable,
        "legacy_resource_audit": "data/reports/school_v1_missing_resource_audit.json",
        "legacy_paths_modified": False,
        "runtime_required_missing_resource_count": 0,
        "input_invariants": before,
        "authorized_objective_scene_difference": (
            "The objective-scene digest includes World state. v0.1.1 explicitly "
            "authorizes replacing only the active render World; all narrower "
            "geometry, transform, identity, hierarchy, collection, camera, "
            "semantic, material-slot, and unit digests remain unchanged."
        ),
        "authorized_datablock_changes": changes,
        "unauthorized_scene_change_count_before_save": 0,
        "fresh_process_validation": (
            "data/reports/school_v1_texture_agnostic_scene_validation_v0_1_1.json"
        ),
        "dataset_generation_authorized": False,
        "determinism_correction": {
            "candidate_dither_intensity": previous_dither,
            "approved_dither_intensity": float(scene.render.dither_intensity),
            "evidence": (
                "The dither=1.0 candidate produced one or two 1-LSB channel "
                "differences in two of three fresh-process rerenders. A "
                "dither=0.0 probe produced decoded-pixel-identical output."
            ),
        },
    }
    report = {
        "schema_name": "amidst.texture_agnostic_scene_creation",
        "schema_version": POLICY_VERSION,
        "status": "CREATED_PENDING_FRESH_VALIDATION",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_classification": "REVIEW_REQUIRED",
        "path_base": "repository_root",
        "policy_id": POLICY_ID,
        "derived_scene": canonical_scene_path("output", output_path),
        "derived_scene_sha256": output_checksum,
        "stable_ids_verified_before_save": identity["ids_verified"],
        "input_object_count": before["object_count"],
        "deterministic_light_count": len(lights),
        "authorized_datablock_changes": changes,
        "unauthorized_scene_change_count": 0,
        "runtime_required_missing_resource_count": 0,
        "images_generated": False,
        "dataset_generated": False,
    }
    write_json_new(args.policy_output.resolve(), policy)
    write_json_new(args.report.resolve(), report)
    human_path = args.human_report.resolve()
    if human_path.exists():
        raise RuntimeError(f"Refusing to overwrite evidence: {human_path}")
    human_path.write_text(
        "\n".join(
            [
                "# School v1 Texture-Agnostic Scene Creation v0.1.1",
                "",
                "Status: `CREATED_PENDING_FRESH_VALIDATION`",
                "",
                f"- Policy: `{POLICY_ID}`",
                f"- Render config: `{CONFIG_ID}`",
                f"- Derived scene: `{canonical_scene_path('output', output_path)}`",
                f"- Derived SHA-256: `{output_checksum}`",
                f"- Stable IDs verified: {identity['ids_verified']}",
                f"- Deterministic render-only Suns: {len(lights)}",
                "- Runtime-required missing resources: 0",
                "- Unauthorized invariant changes: 0",
                "- Dataset generated: false",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "sha256": output_checksum}))


if __name__ == "__main__":
    main()
