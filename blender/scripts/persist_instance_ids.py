#!/usr/bin/env python3
"""Persist and verify approved Blender instance_id mirrors.

This script never generates IDs. It accepts only the approved sidecar registry,
validates the current scene against the frozen identity evidence, and limits
scene mutation to Object["instance_id"].
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
from typing import Any
import uuid

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import (  # noqa: E402
    AUTOMATIC_METHOD,
    BASE_FINGERPRINT_POLICY_ID,
    BOOTSTRAP_METHOD,
    BOOTSTRAP_RE,
    NAMESPACE_UUID,
    POLICY_ID,
    POLICY_VERSION,
    SOURCE_SHA256,
    SUPPORTED_TYPES,
    DeterminismError,
    SignatureBuilder,
    canonical_value,
    digest_record,
    file_sha256,
    index_layer_records,
    load_identity_layer,
    normalize_text,
    resolved_identity,
    valid_instance_id,
    write_canonical,
)
from validate_scene import inspect_external_resources  # noqa: E402


EXPECTED_TOTAL = 2778
EXPECTED_ELIGIBLE = 2777
EXCLUDED_CAMERA = "skp_camera_Last_Saved_SketchUp_View"
REPORT_SCHEMA = "amidst.instance_id_persistence"
REPORT_SCHEMA_VERSION = "1.0.0"


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("persist-working", "verify-working-and-create-output", "verify-output"),
    )
    parser.add_argument("--open-scene", required=True, type=Path)
    parser.add_argument(
        "--source-scene",
        type=Path,
        default=REPOSITORY_ROOT / "blender/source/school_v1.blend",
    )
    parser.add_argument("--expected-source-sha256", default=SOURCE_SHA256)
    parser.add_argument("--expected-pre-write-sha256")
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
        "--inventory-comparison",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_id_scene_comparison.json",
    )
    parser.add_argument(
        "--output-scene",
        type=Path,
        default=REPOSITORY_ROOT / "blender/output/school_v1_ids_policy_1_0_1.blend",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_id_persistence.json",
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_id_persistence.md",
    )
    return parser.parse_args(raw)


def fail(message: str) -> None:
    raise DeterminismError(message)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        fail(f"Required file is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail(f"Expected a JSON object: {path}")
    return value


def strict_registry(path: Path) -> dict[str, Any]:
    registry = load_json(path)
    required = {
        "schema_name": "amidst.instance_registry",
        "schema_version": "1.1.0",
        "policy_id": POLICY_ID,
        "policy_version": POLICY_VERSION,
        "base_fingerprint_policy_id": BASE_FINGERPRINT_POLICY_ID,
        "namespace_uuid": str(NAMESPACE_UUID),
        "authority": "sidecar",
        "source_sha256": SOURCE_SHA256,
    }
    for key, expected in required.items():
        if registry.get(key) != expected:
            fail(f"Registry {key} mismatch: expected {expected!r}")
    records = registry.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_ELIGIBLE:
        fail("Registry must contain exactly 2777 records")
    names = [record.get("object_name") for record in records]
    identifiers = [record.get("instance_id") for record in records]
    if any(not isinstance(name, str) or not name for name in names):
        fail("Registry contains an invalid object locator")
    if len(names) != len(set(names)):
        fail("Registry contains duplicate object locators")
    if any(not valid_instance_id(value) for value in identifiers):
        fail("Registry contains an invalid instance_id")
    if len(identifiers) != len(set(identifiers)):
        fail("Registry contains duplicate instance_id values")
    exclusions = registry.get("eligibility_exclusions")
    if not isinstance(exclusions, list) or len(exclusions) != 1:
        fail("Registry must contain exactly one eligibility exclusion")
    exclusion = exclusions[0]
    if exclusion.get("object_name") != EXCLUDED_CAMERA or exclusion.get("object_type") != "CAMERA":
        fail("Registry eligibility exclusion does not match the approved helper camera")
    return registry


def property_snapshot(data_block: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in data_block.items():
        if key in {"_RNA_UI", "instance_id"}:
            continue
        try:
            result[str(key)] = canonical_value(value)
        except DeterminismError:
            result[str(key)] = str(value)
    return result


def finite_value(value: Any) -> Any:
    if isinstance(value, float):
        if math.isnan(value):
            return {"non_finite_state": "nan"}
        if math.isinf(value):
            return {"non_finite_state": "positive_infinity" if value > 0 else "negative_infinity"}
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [finite_value(item) for item in value]
    return value


def camera_snapshot(camera: Any) -> dict[str, Any]:
    fields = (
        "type",
        "lens",
        "lens_unit",
        "sensor_fit",
        "sensor_width",
        "sensor_height",
        "shift_x",
        "shift_y",
        "clip_start",
        "clip_end",
        "ortho_scale",
        "panorama_type",
        "fisheye_fov",
        "fisheye_lens",
        "latitude_min",
        "latitude_max",
        "longitude_min",
        "longitude_max",
    )
    return {
        "name": camera.name,
        "library": camera.library.filepath if camera.library else None,
        "settings": {field: finite_value(getattr(camera, field, None)) for field in fields},
        "custom_properties": property_snapshot(camera),
    }


def objective_scene_snapshot(scene: Any, builder: SignatureBuilder) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    for obj in sorted(scene.objects, key=lambda item: normalize_text(item.name).encode("utf-8")):
        if obj.name == EXCLUDED_CAMERA:
            data_signature: Any = {"excluded_camera": camera_snapshot(obj.data)}
        elif obj.type in SUPPORTED_TYPES:
            data_signature = builder.data_signature(obj)
        else:
            data_signature = {"unsupported_type": obj.type}
        objects.append(
            {
                "object_name": obj.name,
                "object_type": obj.type,
                "collections": sorted(collection.name for collection in obj.users_collection),
                "parent": obj.parent.name if obj.parent else None,
                "parent_type": obj.parent_type if obj.parent else None,
                "parent_bone": obj.parent_bone if obj.parent and obj.parent_type == "BONE" else None,
                "location": finite_value(list(obj.location)),
                "rotation_mode": obj.rotation_mode,
                "rotation_euler": finite_value(list(obj.rotation_euler)),
                "rotation_quaternion": finite_value(list(obj.rotation_quaternion)),
                "rotation_axis_angle": finite_value(list(obj.rotation_axis_angle)),
                "scale": finite_value(list(obj.scale)),
                "matrix_world": [[finite_value(value) for value in row] for row in obj.matrix_world],
                "dimensions": finite_value(list(obj.dimensions)),
                "data_name": obj.data.name if obj.data else None,
                "data_type": type(obj.data).__name__ if obj.data else None,
                "data_library": obj.data.library.filepath if obj.data and obj.data.library else None,
                "data_signature": data_signature,
                "data_custom_properties": property_snapshot(obj.data) if obj.data else {},
                "material_assignments": [
                    slot.material.name if slot.material else None for slot in obj.material_slots
                ],
                "modifiers": [
                    {
                        "name": modifier.name,
                        "type": modifier.type,
                        "show_viewport": modifier.show_viewport,
                        "show_render": modifier.show_render,
                    }
                    for modifier in obj.modifiers
                ],
                "constraints": [
                    {
                        "name": constraint.name,
                        "type": constraint.type,
                        "influence": finite_value(constraint.influence),
                        "mute": constraint.mute,
                        "target": getattr(getattr(constraint, "target", None), "name", None),
                    }
                    for constraint in obj.constraints
                ],
                "custom_properties_except_instance_id": property_snapshot(obj),
            }
        )

    world = scene.world
    world_record = None
    if world is not None:
        world_record = {
            "name": world.name,
            "color": finite_value(list(world.color)),
            "use_nodes": world.use_nodes,
            "node_tree_signature": (
                builder.node_tree_signature(world.node_tree)
                if world.use_nodes and world.node_tree
                else None
            ),
            "custom_properties": property_snapshot(world),
        }
    resources = []
    for resource in inspect_external_resources():
        normalized_resource = dict(resource)
        normalized_resource.pop("resolved_path", None)
        resources.append(normalized_resource)
    return canonical_value(
        {
            "scene_name": scene.name,
            "object_count": len(scene.objects),
            "objects": objects,
            "camera_count": sum(obj.type == "CAMERA" for obj in scene.objects),
            "cameras": [
                camera_snapshot(obj.data)
                for obj in sorted(scene.objects, key=lambda item: item.name)
                if obj.type == "CAMERA"
            ],
            "scene_camera": scene.camera.name if scene.camera else None,
            "unit_settings": {
                "system": scene.unit_settings.system,
                "scale_length": scene.unit_settings.scale_length,
                "length_unit": scene.unit_settings.length_unit,
            },
            "render_settings": {
                "engine": scene.render.engine,
                "resolution_x": scene.render.resolution_x,
                "resolution_y": scene.render.resolution_y,
                "resolution_percentage": scene.render.resolution_percentage,
                "filepath": scene.render.filepath,
                "film_transparent": scene.render.film_transparent,
            },
            "world": world_record,
            "external_resources": resources,
        }
    )


def diff_values(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    if type(before) is not type(after):
        return [{"path": path, "before": before, "after": after}]
    if isinstance(before, dict):
        differences: list[dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}" if path else str(key)
            if key not in before or key not in after:
                differences.append(
                    {"path": child, "before": before.get(key), "after": after.get(key)}
                )
            else:
                differences.extend(diff_values(before[key], after[key], child))
        return differences
    if isinstance(before, list):
        if len(before) != len(after):
            return [{"path": path, "before": before, "after": after}]
        differences = []
        for index, (left, right) in enumerate(zip(before, after)):
            differences.extend(diff_values(left, right, f"{path}[{index}]"))
        return differences
    return [] if before == after else [{"path": path, "before": before, "after": after}]


def validate_registry_against_scene(
    scene: Any,
    registry: dict[str, Any],
    automatic_layer: dict[str, Any],
    bootstrap_layer: dict[str, Any],
    require_ids: bool,
) -> dict[str, Any]:
    if len(scene.objects) != EXPECTED_TOTAL:
        fail(f"Scene object count mismatch: {len(scene.objects)}")
    excluded_matches = [obj for obj in scene.objects if obj.name == EXCLUDED_CAMERA]
    if len(excluded_matches) != 1 or excluded_matches[0].type != "CAMERA":
        fail("Approved excluded helper camera is missing or ambiguous")
    if excluded_matches[0].get("instance_id") is not None:
        fail("Excluded helper camera unexpectedly contains instance_id")

    unsupported = [
        obj.name
        for obj in scene.objects
        if obj.name != EXCLUDED_CAMERA and obj.type not in SUPPORTED_TYPES
    ]
    if unsupported:
        fail(f"Scene contains unsupported eligible objects: {unsupported!r}")
    eligible = [obj for obj in scene.objects if obj.name != EXCLUDED_CAMERA]
    if len(eligible) != EXPECTED_ELIGIBLE:
        fail(f"Eligible object count mismatch: {len(eligible)}")

    records = registry["records"]
    registry_names = {record["object_name"] for record in records}
    scene_names = {obj.name for obj in eligible}
    if registry_names != scene_names:
        fail(
            "Registry and scene locator sets differ; "
            f"missing={sorted(registry_names - scene_names)!r}, "
            f"unexpected={sorted(scene_names - registry_names)!r}"
        )

    automatic_by_name = index_layer_records(automatic_layer)
    bootstrap_by_name = index_layer_records(bootstrap_layer)
    if set(automatic_by_name) & set(bootstrap_by_name):
        fail("Identity layers contain overlapping locators")
    builder = SignatureBuilder(scene, registry["scene_id"], registry["scene_version"], SOURCE_SHA256)
    ids_seen: dict[str, str] = {}
    missing_ids: list[str] = []
    mismatches: list[dict[str, Any]] = []
    expected_by_name: dict[str, str] = {}

    for record in records:
        locator = record["object_name"]
        matches = [obj for obj in scene.objects if normalize_text(obj.name) == normalize_text(locator)]
        if len(matches) != 1:
            fail(f"Registry locator does not resolve exactly once: {locator!r}")
        obj = matches[0]
        fingerprint, signals = builder.object_fingerprint(obj)
        if fingerprint != record.get("canonical_fingerprint"):
            fail(f"Registry/object fingerprint mismatch: {locator}")
        if canonical_value(record.get("identity_signals")) != signals:
            fail(f"Registry/object identity evidence mismatch: {locator}")

        method = record.get("assignment_method")
        token = record.get("disambiguation_token")
        if method == "canonical_fingerprint":
            if locator in automatic_by_name or locator in bootstrap_by_name or token is not None:
                fail(f"Normal registry record has unexpected override evidence: {locator}")
            resolved_fingerprint = fingerprint
            object_uuid = uuid.uuid5(
                NAMESPACE_UUID, f"{BASE_FINGERPRINT_POLICY_ID}:{fingerprint}"
            )
            expected_id = f"amidst:school:object:{object_uuid}"
        elif method == AUTOMATIC_METHOD:
            layer_record = automatic_by_name.get(locator)
            if layer_record is None:
                fail(f"Automatic identity-layer record missing: {locator}")
            discriminator = layer_record.get("objective_discriminator", {})
            current_children = sorted(
                builder.object_fingerprint(child)[0] for child in obj.children
            )
            if discriminator.get("field") != "hierarchy.child_fingerprints":
                fail(f"Automatic discriminator field mismatch: {locator}")
            if discriminator.get("value") != current_children:
                fail(f"Automatic objective evidence mismatch: {locator}")
            if token != layer_record.get("disambiguation_token"):
                fail(f"Automatic token mismatch: {locator}")
            resolved_fingerprint, expected_id = resolved_identity(fingerprint, method, token)
            if layer_record.get("final_proposed_instance_id") != expected_id:
                fail(f"Automatic layer instance_id mismatch: {locator}")
        elif method == BOOTSTRAP_METHOD:
            layer_record = bootstrap_by_name.get(locator)
            if layer_record is None:
                fail(f"Bootstrap identity-layer record missing: {locator}")
            if token != layer_record.get("bootstrap_discriminator"):
                fail(f"Bootstrap token mismatch: {locator}")
            if not isinstance(token, str) or not BOOTSTRAP_RE.fullmatch(token):
                fail(f"Bootstrap token format mismatch: {locator}")
            resolved_fingerprint, expected_id = resolved_identity(fingerprint, method, token)
            if layer_record.get("final_proposed_instance_id") != expected_id:
                fail(f"Bootstrap layer instance_id mismatch: {locator}")
        else:
            fail(f"Unsupported registry assignment method for {locator}: {method!r}")

        if record.get("resolved_identity_fingerprint") != resolved_fingerprint:
            fail(f"Resolved fingerprint mismatch: {locator}")
        if record.get("instance_id") != expected_id:
            fail(f"Registry contains a non-approved instance_id: {locator}")
        if expected_id in ids_seen:
            fail(f"Duplicate registry ID for {locator} and {ids_seen[expected_id]}")
        ids_seen[expected_id] = locator
        expected_by_name[locator] = expected_id

        actual = obj.get("instance_id")
        if actual is None:
            missing_ids.append(locator)
        elif actual != expected_id:
            mismatches.append(
                {"object_name": locator, "expected_instance_id": expected_id, "actual_instance_id": actual}
            )

    if len(automatic_by_name) != 5 or len(bootstrap_by_name) != 131:
        fail("Identity-layer counts differ from the approved 5/131 split")
    if set(automatic_by_name) != {
        record["object_name"] for record in records if record["assignment_method"] == AUTOMATIC_METHOD
    }:
        fail("Automatic identity layer and registry coverage differ")
    if set(bootstrap_by_name) != {
        record["object_name"] for record in records if record["assignment_method"] == BOOTSTRAP_METHOD
    }:
        fail("Bootstrap identity layer and registry coverage differ")
    if mismatches:
        fail(f"Blender mirror conflicts with the registry: {mismatches!r}")
    if require_ids and missing_ids:
        fail(f"Expected Blender instance_id values are missing: {missing_ids!r}")

    unexpected = [
        obj.name
        for obj in scene.objects
        if obj.name not in expected_by_name and obj.get("instance_id") is not None
    ]
    actual_ids = [obj.get("instance_id") for obj in eligible if obj.get("instance_id") is not None]
    duplicate_ids = sorted({value for value in actual_ids if actual_ids.count(value) > 1})
    if unexpected:
        fail(f"Unexpected Blender instance_id values exist: {unexpected!r}")
    if duplicate_ids:
        fail(f"Duplicate Blender instance_id values exist: {duplicate_ids!r}")
    return {
        "expected_by_name": expected_by_name,
        "missing_ids": sorted(missing_ids),
        "unexpected_ids": unexpected,
        "duplicate_ids": duplicate_ids,
        "registry_mismatches": mismatches,
        "ids_verified": len(actual_ids),
        "builder": builder,
    }


def save_blend(path: Path, copy: bool) -> None:
    previous_save_versions = bpy.context.preferences.filepaths.save_version
    try:
        bpy.context.preferences.filepaths.save_version = 0
        result = bpy.ops.wm.save_as_mainfile(
            filepath=str(path),
            check_existing=False,
            copy=copy,
            relative_remap=False,
        )
    finally:
        bpy.context.preferences.filepaths.save_version = previous_save_versions
    if "FINISHED" not in result:
        fail(f"Blender failed to save scene: {path}")


def human_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# School v1 Instance-ID Persistence Report",
            "",
            f"Status: `{report['status']}`",
            "",
            "Repository classification: `REVIEW_REQUIRED`",
            "",
            f"- Policy: `{report['policy_id']}`",
            f"- Registry schema: `{report['registry_version']}`",
            f"- Source SHA-256: `{report['source_checksum']}`",
            f"- Working pre-write SHA-256: `{report['working_pre_write_checksum']}`",
            f"- Working post-write SHA-256: `{report.get('working_post_write_checksum')}`",
            f"- Output: `{report.get('output_scene')}`",
            f"- Output SHA-256: `{report.get('output_checksum')}`",
            f"- IDs expected / written / verified: {report['ids_expected']} / {report['ids_written']} / {report['ids_verified']}",
            f"- Missing IDs: {len(report['missing_ids'])}",
            f"- Unexpected IDs: {len(report['unexpected_ids'])}",
            f"- Duplicate IDs: {len(report['duplicate_ids'])}",
            f"- Registry mismatches: {len(report['registry_mismatches'])}",
            f"- Unauthorized scene differences: {len(report['unauthorized_scene_differences'])}",
            f"- Failed output artifacts preserved for review: {len(report.get('failed_output_artifacts', []))}",
            f"- Excluded helper camera has no ID: `{str(report['excluded_object_has_no_id']).lower()}`",
            "- Semantic custom properties written: `0`",
            "- Rendering remains blocked by five missing external image resources.",
            "",
        ]
    )


def write_reports(args: argparse.Namespace, report: dict[str, Any]) -> None:
    write_canonical(args.report, report)
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    args.human_report.write_text(human_report(report), encoding="utf-8")


def main() -> None:
    args = script_args()
    if not bpy.data.filepath:
        fail("No saved Blender scene is open")
    open_path = Path(bpy.data.filepath).resolve()
    expected_open_path = args.open_scene.resolve()
    source_path = args.source_scene.resolve()
    if open_path != expected_open_path:
        fail(f"Loaded scene does not match --open-scene: {open_path}")
    if open_path == source_path or source_path.parent in open_path.parents:
        fail("Refusing to modify or use the immutable source scene as a writable scene")
    source_checksum = file_sha256(source_path)
    if source_checksum != args.expected_source_sha256 or source_checksum != SOURCE_SHA256:
        fail("Immutable source checksum does not match the approved value")

    registry = strict_registry(args.registry.resolve())
    automatic_layer = load_identity_layer(
        args.automatic_disambiguation.resolve(),
        "amidst.school_object_objective_disambiguation",
        5,
    )
    bootstrap_layer = load_identity_layer(
        args.identity_bootstrap.resolve(),
        "amidst.school_object_identity_bootstrap",
        131,
    )
    scene = bpy.context.scene

    if args.action == "persist-working":
        pre_checksum = file_sha256(open_path)
        if not args.expected_pre_write_sha256:
            fail("persist-working requires --expected-pre-write-sha256")
        if pre_checksum != args.expected_pre_write_sha256 or pre_checksum != SOURCE_SHA256:
            fail("Working pre-write checksum is not identical to the approved source checksum")
        validation = validate_registry_against_scene(
            scene, registry, automatic_layer, bootstrap_layer, require_ids=False
        )
        if len(validation["missing_ids"]) != EXPECTED_ELIGIBLE:
            fail("Working scene is not a pristine pre-write scene with 2777 missing IDs")
        objective_before = objective_scene_snapshot(scene, validation["builder"])
        objective_before_digest = digest_record(objective_before)

        for object_name, instance_id in validation["expected_by_name"].items():
            obj = scene.objects[object_name]
            if obj.get("instance_id") is not None:
                fail(f"Refusing to replace existing instance_id: {object_name}")
            obj["instance_id"] = instance_id

        post_validation = validate_registry_against_scene(
            scene, registry, automatic_layer, bootstrap_layer, require_ids=True
        )
        objective_after = objective_scene_snapshot(scene, post_validation["builder"])
        unauthorized = diff_values(objective_before, objective_after)
        if unauthorized:
            fail(f"Unauthorized in-memory scene changes detected: {unauthorized!r}")

        save_blend(open_path, copy=False)
        post_checksum = file_sha256(open_path)
        if post_checksum == pre_checksum:
            fail("Working checksum did not change after approved property persistence")
        if file_sha256(source_path) != SOURCE_SHA256:
            fail("Immutable source checksum changed during persistence")
        report = {
            "schema_name": REPORT_SCHEMA,
            "schema_version": REPORT_SCHEMA_VERSION,
            "repository_classification": "REVIEW_REQUIRED",
            "status": "WORKING_SAVED_PENDING_FRESH_VALIDATION",
            "policy_id": POLICY_ID,
            "policy_version": POLICY_VERSION,
            "base_fingerprint_policy_id": BASE_FINGERPRINT_POLICY_ID,
            "registry": str(args.registry.resolve()),
            "registry_version": registry["schema_version"],
            "source_scene": str(source_path),
            "source_checksum": SOURCE_SHA256,
            "working_scene": str(open_path),
            "working_pre_write_checksum": pre_checksum,
            "working_post_write_checksum": post_checksum,
            "output_scene": None,
            "output_checksum": None,
            "write_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "blender_version": bpy.app.version_string,
            "total_objects": EXPECTED_TOTAL,
            "eligible_objects": EXPECTED_ELIGIBLE,
            "ids_expected": EXPECTED_ELIGIBLE,
            "ids_written": EXPECTED_ELIGIBLE,
            "ids_verified": 0,
            "output_ids_verified": 0,
            "missing_ids": [],
            "unexpected_ids": [],
            "duplicate_ids": [],
            "excluded_objects": [EXCLUDED_CAMERA],
            "excluded_object_has_no_id": True,
            "registry_mismatches": [],
            "unauthorized_scene_differences": unauthorized,
            "objective_scene_state": {
                "pre_write_sha256": objective_before_digest,
                "post_write_in_memory_sha256": digest_record(objective_after),
                "relocation_invariant_reference_sha256": objective_before_digest,
                "fresh_working_sha256": None,
                "fresh_output_sha256": None,
            },
            "inventory_comparison": None,
            "semantic_properties_written": 0,
            "blend_saved": True,
            "output_created": False,
            "render_generation_status": "blocked_five_missing_external_image_resources",
        }
        write_reports(args, report)
        print(json.dumps({"status": report["status"], "ids_written": EXPECTED_ELIGIBLE}))
        return

    report = load_json(args.report.resolve())
    if report.get("schema_name") != REPORT_SCHEMA or report.get("policy_id") != POLICY_ID:
        fail("Persistence report schema or policy mismatch")
    require_stage = (
        "WORKING_SAVED_PENDING_FRESH_VALIDATION"
        if args.action == "verify-working-and-create-output"
        else "OUTPUT_CREATED_PENDING_FRESH_VALIDATION"
    )
    if report.get("status") != require_stage:
        fail(f"Persistence report is not at required stage {require_stage}")
    open_checksum = file_sha256(open_path)
    if args.action == "verify-working-and-create-output":
        if open_checksum != report.get("working_post_write_checksum"):
            fail("Fresh working-scene checksum differs from the saved persistence result")
    else:
        if open_checksum != report.get("output_checksum"):
            fail("Fresh output-scene checksum differs from the created output")

    validation = validate_registry_against_scene(
        scene, registry, automatic_layer, bootstrap_layer, require_ids=True
    )
    objective = objective_scene_snapshot(scene, validation["builder"])
    objective_digest = digest_record(objective)

    report["ids_verified"] = validation["ids_verified"]
    report["missing_ids"] = validation["missing_ids"]
    report["unexpected_ids"] = validation["unexpected_ids"]
    report["duplicate_ids"] = validation["duplicate_ids"]
    report["registry_mismatches"] = validation["registry_mismatches"]
    report["excluded_object_has_no_id"] = True
    if args.action == "verify-working-and-create-output":
        comparison = load_json(args.inventory_comparison.resolve())
        if comparison.get("status") != "PASS":
            fail("Pre/post inspection comparison did not pass")
        if comparison.get("unauthorized_scene_change_count") != 0:
            fail("Pre/post inspection comparison contains unauthorized differences")
        if comparison.get("authorized_instance_id_change_count") != EXPECTED_ELIGIBLE:
            fail("Pre/post inspection comparison does not contain 2777 authorized ID additions")
        reference_digest = report["objective_scene_state"].get(
            "relocation_invariant_reference_sha256"
        )
        if reference_digest is not None and objective_digest != reference_digest:
            fail("Fresh-process objective scene state differs from the approved reference")
        report["objective_scene_state"][
            "relocation_invariant_reference_sha256"
        ] = objective_digest
        report["inventory_comparison"] = str(args.inventory_comparison.resolve())
        report["objective_scene_state"]["fresh_working_sha256"] = objective_digest

        output_path = args.output_scene.resolve()
        if output_path.exists():
            fail(f"Refusing to overwrite existing output scene: {output_path}")
        if source_path.parent in output_path.parents:
            fail("Refusing to write output under the immutable source directory")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        working_checksum_before_copy = file_sha256(open_path)
        save_blend(output_path, copy=True)
        if file_sha256(open_path) != working_checksum_before_copy:
            fail("Working scene changed while creating the output copy")
        output_checksum = file_sha256(output_path)
        if file_sha256(source_path) != SOURCE_SHA256:
            fail("Immutable source checksum changed while creating output")
        report["output_scene"] = str(output_path)
        report["output_checksum"] = output_checksum
        report["output_created"] = True
        report["status"] = "OUTPUT_CREATED_PENDING_FRESH_VALIDATION"
    else:
        reference_digest = report["objective_scene_state"].get(
            "relocation_invariant_reference_sha256"
        )
        if objective_digest != reference_digest:
            fail("Fresh output objective scene state differs from the working reference")
        report["objective_scene_state"]["fresh_output_sha256"] = objective_digest
        report["output_ids_verified"] = validation["ids_verified"]
        report["status"] = "READY_FOR_SEMANTIC_ANNOTATION"
    write_reports(args, report)
    print(
        json.dumps(
            {
                "status": report["status"],
                "ids_verified": validation["ids_verified"],
                "output_checksum": report.get("output_checksum"),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
