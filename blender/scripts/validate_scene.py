#!/usr/bin/env python3
"""Read-only validation for an already-open Blender scene.

Run through Blender, for example:

    blender -b "$AMIDST_BLENDER_SOURCE_ROOT/school_v1.blend" \
      --python blender/scripts/validate_scene.py -- \
      --report data/reports/school_v1_validation.json

The script never saves or mutates the scene. Findings describe inspection gaps;
they do not assign semantic labels or stable IDs.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from asset_paths import logical_uri_for_path  # noqa: E402


SEMANTIC_PROPERTY_KEYS = (
    "category",
    "semantic_category",
    "annotation_status",
    "instance_id",
)
GENERIC_NAME_RE = re.compile(
    r"^(?:Cube|Plane|Cylinder|Sphere|Icosphere|Cone|Torus|Empty|Camera|Light|"
    r"Armature|Curve|Text|Volume)(?:\.\d{3})?$",
    re.IGNORECASE,
)
NUMERIC_SUFFIX_RE = re.compile(r"\.\d{3}$")


def _json_value(value: Any) -> Any:
    """Convert Blender ID-property values into JSON-safe values."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "to_list"):
        return [_json_value(item) for item in value.to_list()]
    if hasattr(value, "items"):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Iterable):
        try:
            return [_json_value(item) for item in value]
        except TypeError:
            pass
    return str(value)


def custom_properties(data_block: Any) -> dict[str, Any]:
    return {
        str(key): _json_value(value)
        for key, value in sorted(data_block.items(), key=lambda item: str(item[0]))
        if key != "_RNA_UI"
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resource_record(
    resource_type: str,
    name: str,
    raw_path: str,
    *,
    packed: bool = False,
) -> dict[str, Any] | None:
    if not raw_path or raw_path == "<builtin>":
        return None
    absolute = Path(bpy.path.abspath(raw_path)).resolve()
    return {
        "resource_type": resource_type,
        "name": name,
        "path": raw_path,
        "resolved_path": str(absolute),
        "packed": packed,
        "exists": packed or absolute.exists(),
    }


def inspect_external_resources() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for library in bpy.data.libraries:
        record = _resource_record("library", library.name, library.filepath)
        if record:
            records.append(record)

    for image in bpy.data.images:
        if image.source in {"GENERATED", "VIEWER"}:
            continue
        packed = bool(image.packed_file) or bool(getattr(image, "packed_files", ()))
        record = _resource_record("image", image.name, image.filepath, packed=packed)
        if record:
            record["source"] = image.source
            records.append(record)

    for collection_name, resource_type in (
        ("movieclips", "movie_clip"),
        ("sounds", "sound"),
        ("fonts", "font"),
        ("cache_files", "cache_file"),
        ("volumes", "volume"),
    ):
        for data_block in getattr(bpy.data, collection_name, ()):
            packed = bool(getattr(data_block, "packed_file", None))
            record = _resource_record(
                resource_type,
                data_block.name,
                getattr(data_block, "filepath", ""),
                packed=packed,
            )
            if record:
                records.append(record)

    return sorted(
        records,
        key=lambda item: (item["resource_type"], item["name"], item["path"]),
    )


def _image_nodes(node_tree: Any, image: Any, visited: set[int] | None = None) -> list[dict[str, str]]:
    """Find direct or nested node-group references to an image datablock."""
    if node_tree is None:
        return []
    visited = visited or set()
    pointer = node_tree.as_pointer()
    if pointer in visited:
        return []
    visited.add(pointer)

    uses: list[dict[str, str]] = []
    for node in node_tree.nodes:
        if getattr(node, "image", None) == image:
            uses.append({"node_tree": node_tree.name, "node": node.name})
        nested_tree = getattr(node, "node_tree", None)
        if nested_tree is not None:
            uses.extend(_image_nodes(nested_tree, image, visited))
    return uses


def inspect_missing_image_usage(resource: dict[str, Any]) -> dict[str, Any]:
    """Trace one missing image to node trees, materials, and scene objects."""
    image = bpy.data.images.get(resource["name"])
    if image is None:
        return {
            "datablock": None,
            "material_node_usage": [],
            "render_enabled_object_count": 0,
            "render_enabled_object_examples": [],
            "other_node_usage": [],
            "appears_to_affect_render_output": False,
        }

    material_usage: list[dict[str, Any]] = []
    used_materials: set[Any] = set()
    for material in bpy.data.materials:
        nodes = _image_nodes(material.node_tree, image)
        if nodes:
            used_materials.add(material)
            material_usage.append({"material": material.name, "nodes": nodes})

    render_objects: list[dict[str, Any]] = []
    for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
        materials = {
            slot.material for slot in obj.material_slots if slot.material is not None
        }
        matching = sorted(material.name for material in materials & used_materials)
        if matching and not obj.hide_render:
            render_objects.append(
                {
                    "object_name": obj.name,
                    "object_type": obj.type,
                    "materials": matching,
                }
            )

    other_usage: list[dict[str, Any]] = []
    for datablocks, kind in (
        (bpy.data.worlds, "world"),
        (bpy.data.lights, "light"),
        (bpy.data.scenes, "scene_compositor"),
    ):
        for datablock in datablocks:
            nodes = _image_nodes(getattr(datablock, "node_tree", None), image)
            if nodes:
                other_usage.append(
                    {"datablock_type": kind, "datablock_name": datablock.name, "nodes": nodes}
                )

    return {
        "datablock": {
            "type": "IMAGE",
            "name": image.name,
            "users": image.users,
            "packed": bool(image.packed_file) or bool(getattr(image, "packed_files", ())),
        },
        "material_node_usage": material_usage,
        "render_enabled_object_count": len(render_objects),
        "render_enabled_object_examples": render_objects[:20],
        "other_node_usage": other_usage,
        "appears_to_affect_render_output": bool(render_objects or other_usage),
    }


def _hierarchy_issues(objects: list[Any]) -> list[dict[str, Any]]:
    object_names = {obj.name for obj in objects}
    issues: list[dict[str, Any]] = []

    for obj in objects:
        parent = obj.parent
        if parent is not None and parent.name not in object_names:
            issues.append(
                {
                    "object_name": obj.name,
                    "issue": "parent_not_in_current_scene",
                    "parent": parent.name,
                }
            )

        if obj.parent_type == "BONE":
            if parent is None or parent.type != "ARMATURE":
                issues.append(
                    {
                        "object_name": obj.name,
                        "issue": "bone_parent_without_armature_parent",
                        "parent": parent.name if parent else None,
                    }
                )
            elif obj.parent_bone not in parent.data.bones:
                issues.append(
                    {
                        "object_name": obj.name,
                        "issue": "missing_parent_bone",
                        "parent": parent.name,
                        "parent_bone": obj.parent_bone,
                    }
                )

        seen: set[str] = set()
        cursor = obj
        while cursor is not None:
            if cursor.name in seen:
                issues.append(
                    {
                        "object_name": obj.name,
                        "issue": "parent_cycle",
                        "cycle_at": cursor.name,
                    }
                )
                break
            seen.add(cursor.name)
            cursor = cursor.parent

    return issues


def _ambiguous_names(objects: list[Any]) -> list[dict[str, Any]]:
    folded: dict[str, list[str]] = {}
    for obj in objects:
        folded.setdefault(obj.name.casefold(), []).append(obj.name)

    results: list[dict[str, Any]] = []
    for obj in objects:
        reasons: list[str] = []
        if GENERIC_NAME_RE.match(obj.name):
            reasons.append("generic_blender_style_name")
        if NUMERIC_SUFFIX_RE.search(obj.name):
            reasons.append("generated_numeric_suffix")
        if len(folded[obj.name.casefold()]) > 1:
            reasons.append("case_insensitive_name_collision")
        if reasons:
            results.append({"object_name": obj.name, "reasons": reasons})
    return results


def _camera_record(obj: Any) -> dict[str, Any]:
    camera = obj.data
    return {
        "object_name": obj.name,
        "instance_id": obj.get("instance_id"),
        "location": list(obj.location),
        "rotation_mode": obj.rotation_mode,
        "rotation_euler_radians": list(obj.rotation_euler),
        "projection_type": camera.type,
        "lens_mm": camera.lens,
        "angle_x_radians": camera.angle_x,
        "angle_y_radians": camera.angle_y,
        "sensor_width_mm": camera.sensor_width,
        "sensor_height_mm": camera.sensor_height,
        "sensor_fit": camera.sensor_fit,
        "shift_x": camera.shift_x,
        "shift_y": camera.shift_y,
        "clip_start": camera.clip_start,
        "clip_end": camera.clip_end,
        "custom_properties": custom_properties(obj),
        "camera_data_custom_properties": custom_properties(camera),
    }


def collect_validation(scene_id: str, scene_version: str) -> dict[str, Any]:
    source_path = Path(bpy.data.filepath).resolve()
    objects = sorted(bpy.context.scene.objects, key=lambda obj: obj.name)

    instance_ids: dict[str, list[str]] = {}
    missing_ids: list[str] = []
    unlabeled: list[str] = []
    semantic_metadata: list[dict[str, Any]] = []

    for obj in objects:
        instance_id = obj.get("instance_id")
        if not isinstance(instance_id, str) or not instance_id.strip():
            missing_ids.append(obj.name)
        else:
            instance_ids.setdefault(instance_id, []).append(obj.name)

        properties = custom_properties(obj)
        semantic = {
            key: properties[key]
            for key in SEMANTIC_PROPERTY_KEYS
            if key in properties
        }
        if semantic:
            semantic_metadata.append(
                {"object_name": obj.name, "properties": semantic}
            )

        category = obj.get("category")
        semantic_category = obj.get("semantic_category")
        if not any(
            isinstance(value, str) and value.strip()
            for value in (category, semantic_category)
        ):
            unlabeled.append(obj.name)

    duplicates = [
        {"instance_id": instance_id, "object_names": names}
        for instance_id, names in sorted(instance_ids.items())
        if len(names) > 1
    ]
    resources = inspect_external_resources()
    missing_resources = [record for record in resources if not record["exists"]]
    for resource in missing_resources:
        if resource["resource_type"] == "image":
            resource["usage"] = inspect_missing_image_usage(resource)
    hierarchy_issues = _hierarchy_issues(objects)
    cameras = [_camera_record(obj) for obj in objects if obj.type == "CAMERA"]

    return {
        "report_kind": "read_only_scene_validation",
        "inspected_at_utc": datetime.now(timezone.utc).isoformat(),
        "scene_id": scene_id,
        "scene_version": scene_version,
        "source_file": source_path.name,
        "source_path": logical_uri_for_path(
            "blender-source", source_path, repo_root=REPOSITORY_ROOT
        ),
        "source_sha256": _sha256(source_path),
        "blender_version": bpy.app.version_string,
        "scene_name": bpy.context.scene.name,
        "object_count": len(objects),
        "scene_settings": {
            "unit_system": bpy.context.scene.unit_settings.system,
            "unit_scale_length": bpy.context.scene.unit_settings.scale_length,
            "length_unit": bpy.context.scene.unit_settings.length_unit,
            "render_resolution_x": bpy.context.scene.render.resolution_x,
            "render_resolution_y": bpy.context.scene.render.resolution_y,
            "render_resolution_percentage": bpy.context.scene.render.resolution_percentage,
            "active_camera": (
                bpy.context.scene.camera.name if bpy.context.scene.camera else None
            ),
            "collection_count": len(bpy.data.collections),
        },
        "checks": {
            "missing_instance_id": missing_ids,
            "duplicate_instance_id": duplicates,
            "object_hierarchy": {
                "parented_object_count": sum(obj.parent is not None for obj in objects),
                "issues": hierarchy_issues,
            },
            "suspicious_hierarchy": hierarchy_issues,
            "semantic_custom_properties": semantic_metadata,
            "unlabeled_objects": unlabeled,
            "ambiguous_object_names": _ambiguous_names(objects),
            "existing_cameras": cameras,
            "external_resources": resources,
            "missing_resources": missing_resources,
        },
        "summary": {
            "object_count": len(objects),
            "missing_instance_id_count": len(missing_ids),
            "duplicate_instance_id_count": len(duplicates),
            "hierarchy_issue_count": len(hierarchy_issues),
            "semantic_metadata_object_count": len(semantic_metadata),
            "unlabeled_object_count": len(unlabeled),
            "ambiguous_object_name_count": len(_ambiguous_names(objects)),
            "camera_count": len(cameras),
            "external_resource_count": len(resources),
            "missing_resource_count": len(missing_resources),
        },
        "notes": [
            "No semantic category or instance_id was assigned by this validation.",
            "Unlabeled means no non-empty category or semantic_category custom property was found.",
            "Ambiguous-name flags are lexical review hints, not semantic conclusions.",
            "Blender unit settings do not independently verify physical scale.",
        ],
    }


def _arguments() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--scene-id", default="school")
    parser.add_argument("--scene-version", default="v1")
    return parser.parse_args(arguments)


def _assert_safe_output(path: Path) -> None:
    source_directory = Path(bpy.data.filepath).resolve().parent
    resolved = path.resolve()
    if resolved == Path(bpy.data.filepath).resolve() or source_directory in resolved.parents:
        raise ValueError(f"Refusing to write inspection output under source directory: {resolved}")


def main() -> None:
    args = _arguments()
    if not bpy.data.filepath:
        raise RuntimeError("No saved .blend scene is currently open")
    _assert_safe_output(args.report)
    report = collect_validation(args.scene_id, args.scene_version)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
