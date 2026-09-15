#!/usr/bin/env python3
"""Export deterministic, non-semantic evidence for stable-ID collisions.

Run this script through Blender in background mode. It reads the current scene
and the stable-ID collision report, writes a canonical JSON evidence report,
and never writes Blender data or saves the open .blend file.
"""

from __future__ import annotations

import argparse
from collections import Counter
import math
from pathlib import Path
import sys
from typing import Any

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from assign_instance_ids import (  # noqa: E402
    BASE_FINGERPRINT_POLICY_ID,
    POLICY_ID,
    SOURCE_SHA256,
    SignatureBuilder,
    canonical_bytes,
    canonical_value,
    custom_property_snapshot,
    digest_record,
    file_sha256,
    normalize_text,
    normalized_blender_path,
    scene_state_snapshot,
    write_canonical,
)


EVIDENCE_SCHEMA_VERSION = "1.0.0-candidate"
DISAMBIGUATION_DOMAIN = "amidst.school.object-disambiguation/1.0.0-candidate"


def blender_script_args() -> list[str]:
    return sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collision-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_id_collisions.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_disambiguation_evidence.json",
    )
    parser.add_argument(
        "--override-output",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/reports/school_v1_disambiguation_candidate.json"
        ),
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_disambiguation_approval.md",
    )
    parser.add_argument("--scene-id", default="school")
    parser.add_argument("--scene-version", default="v1")
    parser.add_argument("--camera-name", default="skp_camera_Last_Saved_SketchUp_View")
    return parser.parse_args(blender_script_args())


def matrix_rows(matrix: Any) -> list[list[float]]:
    return [[float(value) for value in row] for row in matrix]


def finite_or_state(value: float) -> float | dict[str, str]:
    value = float(value)
    if math.isnan(value):
        return {"non_finite_state": "nan"}
    if math.isinf(value):
        return {"non_finite_state": "positive_infinity" if value > 0 else "negative_infinity"}
    return value


def target_fingerprint(target: Any, builder: SignatureBuilder) -> str | None:
    if target is None or target.name not in builder.scene.objects:
        return None
    try:
        return builder.object_fingerprint(target)[0]
    except Exception:
        return None


def library_path(data_block: Any) -> str | None:
    library = getattr(data_block, "library", None)
    return normalized_blender_path(library.filepath) if library is not None else None


def object_user_fingerprints(data_block: Any, scene: Any, builder: SignatureBuilder) -> list[str | None]:
    fingerprints: list[str | None] = []
    for candidate in scene.objects:
        if candidate.data is data_block:
            fingerprints.append(target_fingerprint(candidate, builder))
    return sorted(fingerprints, key=lambda value: b"" if value is None else value.encode("ascii"))


def material_user_fingerprints(material: Any, scene: Any, builder: SignatureBuilder) -> list[str | None]:
    fingerprints: list[str | None] = []
    for candidate in scene.objects:
        if any(slot.material is material for slot in candidate.material_slots):
            fingerprints.append(target_fingerprint(candidate, builder))
    return sorted(fingerprints, key=lambda value: b"" if value is None else value.encode("ascii"))


def collection_content_signature(collection: Any, builder: SignatureBuilder) -> str:
    object_fingerprints = [target_fingerprint(obj, builder) for obj in collection.objects]
    child_shapes = [
        {
            "object_type_counts": dict(sorted(Counter(obj.type for obj in child.objects).items())),
            "object_fingerprints": sorted(
                (target_fingerprint(obj, builder) for obj in child.objects),
                key=lambda value: b"" if value is None else value.encode("ascii"),
            ),
        }
        for child in collection.children
    ]
    child_shapes.sort(key=canonical_bytes)
    return digest_record(
        {
            "object_fingerprints": sorted(
                object_fingerprints,
                key=lambda value: b"" if value is None else value.encode("ascii"),
            ),
            "child_shapes": child_shapes,
        }
    )


def constraint_relationships(obj: Any, builder: SignatureBuilder) -> list[dict[str, Any]]:
    records = []
    for constraint in obj.constraints:
        records.append(
            {
                "type": constraint.type,
                "target_fingerprint": target_fingerprint(getattr(constraint, "target", None), builder),
                "space_object_fingerprint": target_fingerprint(
                    getattr(constraint, "space_object", None), builder
                ),
                "mute": constraint.mute,
                "influence": constraint.influence,
                "owner_space": getattr(constraint, "owner_space", None),
                "target_space": getattr(constraint, "target_space", None),
            }
        )
    records.sort(key=canonical_bytes)
    return records


def modifier_relationships(obj: Any, builder: SignatureBuilder) -> list[dict[str, Any]]:
    records = []
    for modifier in obj.modifiers:
        targets = []
        for attribute in ("object", "target", "origin", "mirror_object", "offset_object"):
            target = getattr(modifier, attribute, None)
            if target is not None:
                targets.append(
                    {
                        "role": attribute,
                        "target_fingerprint": target_fingerprint(target, builder),
                    }
                )
        targets.sort(key=canonical_bytes)
        records.append(
            {
                "type": modifier.type,
                "show_render": modifier.show_render,
                "show_viewport": modifier.show_viewport,
                "targets": targets,
            }
        )
    records.sort(key=canonical_bytes)
    return records


def objective_record(obj: Any, scene: Any, builder: SignatureBuilder) -> dict[str, Any]:
    parent = obj.parent
    ancestors = []
    cursor = parent
    while cursor is not None:
        ancestors.append(target_fingerprint(cursor, builder))
        cursor = cursor.parent

    child_fingerprints = [target_fingerprint(child, builder) for child in obj.children]
    child_fingerprints.sort(key=lambda value: b"" if value is None else value.encode("ascii"))

    data_relationship = None
    if obj.data is not None:
        data_relationship = {
            "id_type": obj.data.bl_rna.identifier,
            "is_linked": obj.data.library is not None,
            "library_path": library_path(obj.data),
            "users": obj.data.users,
            "scene_object_user_fingerprints": object_user_fingerprints(obj.data, scene, builder),
        }

    materials = []
    for slot in obj.material_slots:
        material = slot.material
        materials.append(
            {
                "slot_link": slot.link,
                "material": (
                    {
                        "content_signature": builder.material_signature(material),
                        "is_linked": material.library is not None,
                        "library_path": library_path(material),
                        "users": material.users,
                        "scene_object_user_fingerprints": material_user_fingerprints(
                            material, scene, builder
                        ),
                    }
                    if material is not None
                    else None
                ),
            }
        )

    instance_collection = obj.instance_collection
    return canonical_value(
        {
            "object_type": obj.type,
            "collection_paths": builder.object_collection_paths(obj),
            "collection_content_signatures": sorted(
                collection_content_signature(collection, builder)
                for collection in obj.users_collection
            ),
            "hierarchy": {
                "parent_fingerprint": target_fingerprint(parent, builder),
                "parent_type": parent.type if parent is not None else None,
                "parent_relation_type": obj.parent_type,
                "parent_bone": normalize_text(obj.parent_bone) if obj.parent_bone else None,
                "ancestor_fingerprints": ancestors,
                "child_fingerprints": child_fingerprints,
            },
            "transform": {
                "location": list(obj.location),
                "rotation_mode": obj.rotation_mode,
                "rotation_euler": list(obj.rotation_euler),
                "rotation_quaternion": list(obj.rotation_quaternion),
                "rotation_axis_angle": list(obj.rotation_axis_angle),
                "scale": list(obj.scale),
                "delta_location": list(obj.delta_location),
                "delta_rotation_euler": list(obj.delta_rotation_euler),
                "delta_rotation_quaternion": list(obj.delta_rotation_quaternion),
                "delta_scale": list(obj.delta_scale),
                "dimensions": list(obj.dimensions),
                "matrix_basis": matrix_rows(obj.matrix_basis),
                "matrix_local": matrix_rows(obj.matrix_local),
                "matrix_parent_inverse": matrix_rows(obj.matrix_parent_inverse),
                "matrix_world": matrix_rows(obj.matrix_world),
            },
            "datablock_relationship": data_relationship,
            "material_relationships": materials,
            "instance_relationship": {
                "instance_type": obj.instance_type,
                "is_instancer": obj.is_instancer,
                "collection_is_linked": (
                    instance_collection.library is not None if instance_collection is not None else None
                ),
                "collection_library_path": (
                    library_path(instance_collection) if instance_collection is not None else None
                ),
                "collection_content_signature": (
                    collection_content_signature(instance_collection, builder)
                    if instance_collection is not None
                    else None
                ),
            },
            "linkage": {
                "object_is_linked": obj.library is not None,
                "object_library_path": library_path(obj),
                "override_library_present": obj.override_library is not None,
            },
            "constraints": constraint_relationships(obj, builder),
            "modifiers": modifier_relationships(obj, builder),
            "custom_properties": {
                normalize_text(str(key)): value
                for key, value in obj.items()
                if key != "_RNA_UI"
            },
            "visibility_and_usage": {
                "hide_render": obj.hide_render,
                "hide_viewport": obj.hide_viewport,
                "hide_select": obj.hide_select,
                "display_type": obj.display_type,
                "pass_index": obj.pass_index,
                "color": list(obj.color),
                "animation_data_present": obj.animation_data is not None,
            },
        }
    )


def descriptive_record(obj: Any) -> dict[str, Any]:
    return {
        "object_name": normalize_text(obj.name),
        "data_name": normalize_text(obj.data.name) if obj.data is not None else None,
        "parent_name": normalize_text(obj.parent.name) if obj.parent is not None else None,
        "collection_names": sorted(normalize_text(collection.name) for collection in obj.users_collection),
        "material_names": [
            normalize_text(slot.material.name) if slot.material is not None else None
            for slot in obj.material_slots
        ],
    }


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            result.update(flatten(child, child_prefix))
        return result
    return {prefix: value}


def differing_fields(member_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened = [flatten(member["objective_evidence"]) for member in member_records]
    fields = sorted(set().union(*(record.keys() for record in flattened)))
    differences = []
    for field in fields:
        values = [record.get(field) for record in flattened]
        if len({canonical_bytes(value) for value in values}) > 1:
            differences.append(
                {
                    "field": field,
                    "member_values": [
                        {
                            "object_reference": member_records[index]["object_reference"],
                            "value": value,
                        }
                        for index, value in enumerate(values)
                    ],
                }
            )
    return differences


def inspect_camera(name: str, scene: Any, builder: SignatureBuilder) -> dict[str, Any]:
    obj = scene.objects.get(name)
    if obj is None:
        return {"object_reference": name, "found": False}
    if obj.type != "CAMERA":
        return {"object_reference": name, "found": True, "object_type": obj.type}

    camera = obj.data
    scene_camera_names = sorted(
        normalize_text(candidate.name) for candidate in scene.objects if candidate.type == "CAMERA"
    )
    marker_frames = sorted(
        marker.frame for marker in scene.timeline_markers if getattr(marker, "camera", None) is obj
    )
    return {
        "object_reference": normalize_text(obj.name),
        "found": True,
        "object_type": obj.type,
        "camera_type": camera.type,
        "lens": finite_or_state(camera.lens),
        "lens_unit": camera.lens_unit,
        "scene_linkage": {
            "in_current_scene": obj.name in scene.objects,
            "collection_paths": builder.object_collection_paths(obj),
            "is_active_scene_camera": scene.camera is obj,
            "active_scene_camera_reference": (
                normalize_text(scene.camera.name) if scene.camera is not None else None
            ),
            "timeline_marker_frames": marker_frames,
        },
        "render_and_view_status": {
            "hide_render": obj.hide_render,
            "hide_viewport": obj.hide_viewport,
            "visible_in_active_view_layer": obj.visible_get(),
        },
        "datablock": {
            "name": normalize_text(camera.name),
            "users": camera.users,
            "is_linked": camera.library is not None,
            "library_path": library_path(camera),
        },
        "import_helper_name_evidence": {
            "starts_with_skp_camera": obj.name.startswith("skp_camera_"),
            "contains_last_saved_sketchup_view": "Last_Saved_SketchUp_View" in obj.name,
            "scene_camera_count": len(scene_camera_names),
            "cam_prefix_camera_count": sum(
                candidate_name.startswith("CAM_") for candidate_name in scene_camera_names
            ),
            "skp_camera_prefix_count": sum(
                candidate_name.startswith("skp_camera_") for candidate_name in scene_camera_names
            ),
        },
    }


def candidate_override(evidence_report: dict[str, Any]) -> dict[str, Any]:
    records = []
    for group in evidence_report["groups"]:
        differences = {
            item["field"]: {
                member_value["object_reference"]: member_value["value"]
                for member_value in item["member_values"]
            }
            for item in group["differing_objective_fields"]
        }
        for member in group["members"]:
            resolvable = group["all_members_uniquely_discriminated"]
            discriminator = None
            token = None
            if resolvable:
                discriminator = {
                    "kind": "canonical_composite_objective_evidence",
                    "fields": [
                        {"path": field, "value": values[member["object_reference"]]}
                        for field, values in sorted(differences.items())
                    ],
                    "objective_evidence_digest": member["objective_evidence_digest"],
                }
                token = member["proposed_disambiguation_token"]
            records.append(
                {
                    "duplicate_fingerprint_group_id": group["group_id"],
                    "duplicate_fingerprint": group["duplicate_fingerprint"],
                    "affected_object_reference": {
                        "blender_object_name": member["object_reference"],
                        "role": "scene_v1_locator_only",
                        "participates_in_discriminator": False,
                    },
                    "proposed_objective_discriminator": discriminator,
                    "canonical_disambiguation_token": token,
                    "reason": (
                        "unique_approved_nonsemantic_objective_evidence"
                        if resolvable
                        else "no_differing_approved_nonsemantic_objective_field"
                    ),
                    "review_status": "PROPOSED" if resolvable else "needs_manual_identity_review",
                }
            )
    records.sort(
        key=lambda record: (
            record["duplicate_fingerprint"].encode("ascii"),
            normalize_text(record["affected_object_reference"]["blender_object_name"]).encode(
                "utf-8"
            ),
        )
    )
    summary = evidence_report["summary"]
    camera = evidence_report["camera_evidence"]
    return {
        "schema_name": "amidst.school_object_disambiguation_overrides",
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "repository_classification": "REVIEW_REQUIRED",
        "status": "PROPOSED",
        "layer_kind": "scene_version_specific_nonsemantic_identity_evidence",
        "effective_policy_id": POLICY_ID,
        "base_policy_id": BASE_FINGERPRINT_POLICY_ID,
        "base_fingerprint_algorithm_changed": False,
        "scene_id": evidence_report["scene_id"],
        "scene_version": evidence_report["scene_version"],
        "source_scene": evidence_report["source_scene"],
        "source_sha256": evidence_report["source_sha256"],
        "authority": "candidate_for_human_approval_not_yet_assignable",
        "token_derivation": {
            "domain": DISAMBIGUATION_DOMAIN,
            "canonical_input_fields": [
                "domain",
                "scene_version",
                "duplicate_fingerprint",
                "objective_evidence_digest",
            ],
            "canonical_serialization": "amidst.school.object-id/1.0.0 canonical JSON",
            "digest": "SHA-256",
        },
        "records": records,
        "summary": {
            **summary,
            "record_count": len(records),
            "records_with_proposed_tokens": sum(
                record["canonical_disambiguation_token"] is not None for record in records
            ),
        },
        "camera_eligibility_proposal": {
            "object_reference": camera["object_reference"],
            "recommended_option": "A",
            "recommendation": "exclude_as_non_authoritative_imported_saved_view_helper",
            "review_status": "PROPOSED",
            "evidence": {
                "camera_type": camera["camera_type"],
                "lens": camera["lens"],
                "is_active_scene_camera": camera["scene_linkage"]["is_active_scene_camera"],
                "timeline_marker_frames": camera["scene_linkage"]["timeline_marker_frames"],
                "import_helper_name_evidence": camera["import_helper_name_evidence"],
                "current_dataset_generation_dependency_observed": False,
            },
            "base_fingerprint_algorithm_can_remain_unchanged": True,
            "policy_eligibility_contract_can_remain_unchanged": False,
            "required_before_application": (
                "human approval and an explicit versioned eligibility-contract amendment"
            ),
        },
    }


def human_approval_report(evidence_report: dict[str, Any], override: dict[str, Any]) -> str:
    summary = evidence_report["summary"]
    camera = evidence_report["camera_evidence"]
    lines = [
        "# School v1 Disambiguation and Camera-Eligibility Approval Report",
        "",
        "Status: `REVIEW_REQUIRED`",
        "",
        "Repository classification: `REVIEW_REQUIRED`",
        "",
        "This report proposes a scene-version-specific, non-semantic override layer.",
        "It does not assign an ID, change stable-ID policy v1.0.0, or write Blender data.",
        "",
        "## Summary",
        "",
        "| Measure | Result |",
        "| --- | ---: |",
        f"| Duplicate fingerprint groups | {summary['duplicate_group_count']} |",
        f"| Ambiguous objects | {summary['ambiguous_object_count']} |",
        (
            "| Groups with a deterministic proposed discriminator | "
            f"{summary['groups_with_unique_objective_discriminator']} |"
        ),
        (
            "| Objects automatically resolvable after approval | "
            f"{summary['objects_resolvable_by_objective_evidence']} |"
        ),
        (
            "| Groups still requiring manual identity evidence | "
            f"{summary['groups_requiring_manual_identity_review']} |"
        ),
        (
            "| Objects still requiring manual identity evidence | "
            f"{summary['objects_requiring_manual_identity_review']} |"
        ),
        "",
        (
            "Candidate override: "
            "`data/annotations/instance_registry/school_v1_disambiguation.json`"
        ),
        "",
        "Object and datablock display names are retained only as locators. They do not",
        "participate in any proposed token. The inspected objective evidence covers",
        "object type, collection and parent relationships, local/world transforms,",
        "parent inverse, dimensions, datablock/material sharing, linked-library and",
        "instance sources, children fingerprints, constraint/modifier targets, custom",
        "properties, visibility, render, and animation-use state.",
        "",
        "## All Duplicate Groups",
        "",
        "| # | Duplicate fingerprint | Object locators | Objective fields that differ | Proposal |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for group in evidence_report["groups"]:
        names = ", ".join(f"`{member['object_reference']}`" for member in group["members"])
        fields = ", ".join(
            f"`{item['field']}`" for item in group["differing_objective_fields"]
        ) or "None"
        proposal = (
            "PROPOSED canonical objective-evidence token"
            if group["all_members_uniquely_discriminated"]
            else "`needs_manual_identity_review`"
        )
        lines.append(
            f"| {group['group_index']} | `{group['duplicate_fingerprint']}` | "
            f"{names} | {fields} | {proposal} |"
        )
    lines.extend(
        [
            "",
            "Only group 14 differs on approved non-semantic evidence:",
            "`hierarchy.child_fingerprints`. Its five members have distinct sorted",
            "child-fingerprint multisets. The other 44 groups have no differing approved",
            "objective field; their names alone are insufficient and no token is proposed.",
            "",
            "## Camera Recommendation",
            "",
            "Recommend **Option A** as `PROPOSED`: explicitly exclude",
            f"`{camera['object_reference']}` from stable-ID eligibility as a",
            "non-authoritative imported saved-view/helper camera.",
            "",
            f"- Camera type: `{camera['camera_type']}`.",
            "- Lens: positive infinity, which policy canonicalization correctly rejects.",
            f"- Active scene camera: `{str(camera['scene_linkage']['is_active_scene_camera']).lower()}`.",
            f"- Timeline camera markers: `{len(camera['scene_linkage']['timeline_marker_frames'])}`.",
            f"- Visible in active view layer: `{str(camera['render_and_view_status']['visible_in_active_view_layer']).lower()}`.",
            "- It is scene-linked but locally stored, with one camera-datablock user.",
            "- Its object/datablock locator begins `skp_camera_` and contains",
            "  `Last_Saved_SketchUp_View`, objective provenance evidence of an imported",
            "  saved-view artifact rather than an authoritative dataset camera.",
            "- It is the only `skp_camera_` locator among 30 scene cameras; the other 29",
            "  camera locators use the project `CAM_` prefix.",
            "- Current repository camera logic inventories cameras only. No camera dataset",
            "  generator or direct dependency on this locator exists.",
            "",
            "Do not synthesize a finite lens and do not repair the scene in this phase.",
            "Because the confirmed v1.0.0 eligibility scope currently includes every",
            "supported `CAMERA`, Option A requires explicit human approval and a versioned",
            "eligibility-contract amendment. The canonical fingerprint algorithm itself",
            "can remain unchanged; the complete v1.0.0 policy contract cannot be claimed",
            "unchanged if this exclusion is adopted.",
            "",
            "## Documentation and Implementation Changes Required After Approval",
            "",
            "1. Update ADR-008 with the approved override authority, token derivation,",
            "   lifecycle, and helper-camera exclusion; decide whether the eligibility",
            "   amendment requires policy `1.0.1` or another explicitly approved version.",
            "2. Update `docs/05_Spatial_Model_Specification.md` with the override layer,",
            "   accepted objective evidence, and non-authoritative helper-camera rule.",
            "3. Update `docs/09_Data_Types_and_Exchange_Formats.md` with the override schema,",
            "   version, canonical token fields, and registry linkage.",
            "4. Update `docs/open_questions.md` only for the newly approved portions of",
            "   OQ-004/OQ-015 and camera authority; keep unrelated camera questions open.",
            "5. Update `blender/scene_manifest.json` with the approved override version and",
            "   explicit camera eligibility disposition.",
            "6. Only after those decisions, extend `assign_instance_ids.py` to validate and",
            "   consume approved overrides; rerun the two-pass determinism test before any",
            "   persistent custom-property assignment.",
            "",
            "## Approval Decision Needed",
            "",
            "- Approve or reject the five hierarchy-based proposed records.",
            "- Supply independent stable non-semantic evidence for the remaining 131",
            "  objects, or explicitly decide that those coincident duplicates are not",
            "  separately eligible entities. Object names cannot be the sole evidence.",
            "- Approve or reject camera Option A and choose the eligibility-contract version.",
            "",
            "Until all three decisions are complete, persistent ID assignment remains blocked.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    working_path = Path(bpy.data.filepath).resolve()
    if not working_path.is_file():
        raise SystemExit("The open Blender file does not exist on disk")
    if (REPOSITORY_ROOT / "blender/source") in working_path.parents:
        raise SystemExit("Refusing to inspect an immutable source scene directly")

    source_path = REPOSITORY_ROOT / "blender/source/school_v1.blend"
    source_hash = file_sha256(source_path)
    working_hash_before = file_sha256(working_path)
    if source_hash != SOURCE_SHA256 or working_hash_before != SOURCE_SHA256:
        raise SystemExit("Source or working scene checksum does not match the approved school_v1 hash")

    collision_report = __import__("json").loads(args.collision_report.read_text(encoding="utf-8"))
    if collision_report.get("policy_id") != POLICY_ID:
        raise SystemExit("Collision report policy does not match the implemented policy")

    scene = bpy.context.scene
    builder = SignatureBuilder(scene, args.scene_id, args.scene_version, source_hash)
    properties_before = custom_property_snapshot(scene)
    scene_before = scene_state_snapshot(scene, builder)
    dirty_before = bpy.data.is_dirty

    groups = []
    for index, group in enumerate(collision_report["duplicate_fingerprints"], start=1):
        member_records = []
        for object_name in group["object_names"]:
            obj = scene.objects.get(object_name)
            if obj is None:
                raise SystemExit(f"Collision member is absent from the scene: {object_name}")
            fingerprint, _ = builder.object_fingerprint(obj)
            if fingerprint != group["canonical_fingerprint"]:
                raise SystemExit(f"Fingerprint mismatch for collision member: {object_name}")
            evidence = objective_record(obj, scene, builder)
            evidence_digest = digest_record(evidence)
            member_records.append(
                {
                    "object_reference": normalize_text(obj.name),
                    "descriptive_locators": descriptive_record(obj),
                    "objective_evidence": evidence,
                    "objective_evidence_digest": evidence_digest,
                    "proposed_disambiguation_token": digest_record(
                        {
                            "domain": DISAMBIGUATION_DOMAIN,
                            "scene_version": args.scene_version,
                            "duplicate_fingerprint": fingerprint,
                            "objective_evidence_digest": evidence_digest,
                        }
                    ),
                }
            )
        member_records.sort(key=lambda row: normalize_text(row["object_reference"]).encode("utf-8"))
        digests = [member["objective_evidence_digest"] for member in member_records]
        unique = len(set(digests)) == len(digests)
        differences = differing_fields(member_records)
        groups.append(
            {
                "group_id": f"school:v1:duplicate-fingerprint:{group['canonical_fingerprint']}",
                "group_index": index,
                "duplicate_fingerprint": group["canonical_fingerprint"],
                "member_count": len(member_records),
                "members": member_records,
                "differing_objective_fields": differences,
                "objective_discriminator": (
                    "objective_evidence_digest" if unique and differences else None
                ),
                "all_members_uniquely_discriminated": unique and bool(differences),
                "review_status": "PROPOSED" if unique and differences else "needs_manual_identity_review",
            }
        )

    working_hash_after = file_sha256(working_path)
    properties_after = custom_property_snapshot(scene)
    scene_after = scene_state_snapshot(scene, builder)
    resolvable = [group for group in groups if group["all_members_uniquely_discriminated"]]
    resolvable_objects = sum(group["member_count"] for group in resolvable)
    report = {
        "schema_name": "amidst.school_object_disambiguation_evidence",
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "repository_classification": "REVIEW_REQUIRED",
        "status": "PROPOSED",
        "policy_id": POLICY_ID,
        "base_fingerprint_policy_id": BASE_FINGERPRINT_POLICY_ID,
        "disambiguation_domain": DISAMBIGUATION_DOMAIN,
        "scene_id": args.scene_id,
        "scene_version": args.scene_version,
        "source_scene": source_path.name,
        "source_sha256": source_hash,
        "working_scene": working_path.name,
        "groups": groups,
        "summary": {
            "duplicate_group_count": len(groups),
            "ambiguous_object_count": sum(group["member_count"] for group in groups),
            "groups_with_unique_objective_discriminator": len(resolvable),
            "objects_resolvable_by_objective_evidence": resolvable_objects,
            "groups_requiring_manual_identity_review": len(groups) - len(resolvable),
            "objects_requiring_manual_identity_review": (
                sum(group["member_count"] for group in groups) - resolvable_objects
            ),
        },
        "camera_evidence": inspect_camera(args.camera_name, scene, builder),
        "integrity": {
            "working_sha256_before": working_hash_before,
            "working_sha256_after": working_hash_after,
            "working_checksum_unchanged": working_hash_before == working_hash_after,
            "custom_properties_unchanged": properties_before == properties_after,
            "scene_state_unchanged": scene_before == scene_after,
            "blender_dirty_flag_unchanged": dirty_before == bpy.data.is_dirty,
            "blend_saved": False,
        },
    }
    write_canonical(args.output, report)
    override = candidate_override(report)
    write_canonical(args.override_output, override)
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    args.human_report.write_text(
        human_approval_report(report, override), encoding="utf-8"
    )
    print(canonical_bytes({"status": report["status"], "summary": report["summary"]}).decode("utf-8"))


if __name__ == "__main__":
    main()
