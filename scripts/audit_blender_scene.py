"""Collect a read-only, machine-readable inventory of the currently open Blender file.

Run this module through Blender.  It deliberately contains no save operation and writes
only the requested JSON report.  ``run_scene_audit.py`` wraps it with source hashing and
produces the human-readable summary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import bpy
from mathutils import Vector

HIGH_POLY_THRESHOLD = 50_000
MAX_NAMES_PER_GROUP = 100
SEMANTIC_PROPERTY_PREFIXES = (
    "annotation",
    "camera",
    "category",
    "floor",
    "navmesh",
    "portal",
    "semantic",
    "stable_id",
    "transition",
    "walkable",
    "zone",
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _float(value: float, digits: int = 9) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"non-finite numeric value in scene: {value}")
    return round(value, digits)


def _nullable_float(value: float, digits: int = 9) -> float | None:
    value = float(value)
    return round(value, digits) if math.isfinite(value) else None


def _vector(values: Iterable[float]) -> list[float]:
    return [_float(value) for value in values]


def _matrix(matrix: Any) -> list[list[float]]:
    return [[_float(value) for value in row] for row in matrix]


def _json_value(value: Any, depth: int = 0) -> Any:
    if depth >= 8:
        return {"truncated_type": type(value).__name__, "reason": "maximum_depth"}
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        if value.startswith(("http://", "https://")):
            parsed = urlsplit(value)
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        if value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value):
            normalized = value.replace("\\", "/")
            return {
                "path_kind": "absolute_redacted_to_basename",
                "basename": normalized.rsplit("/", 1)[-1],
            }
        return value
    if isinstance(value, float):
        return _float(value)
    if isinstance(value, dict):
        return {
            str(key): _json_value(item, depth + 1)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))[:200]
        }
    if hasattr(value, "keys") and hasattr(value, "__getitem__"):
        try:
            keys = sorted(str(key) for key in value.keys())[:200]
            return {key: _json_value(value[key], depth + 1) for key in keys}
        except (KeyError, ReferenceError, TypeError, ValueError):
            return {"unsupported_mapping_type": type(value).__name__}
    if isinstance(value, (list, tuple)) or hasattr(value, "to_list"):
        try:
            return [_json_value(item, depth + 1) for item in value]
        except TypeError:
            pass
    return {"unsupported_type": type(value).__name__}


def _custom_properties(data_block: Any) -> dict[str, Any]:
    keys = sorted(key for key in data_block.keys() if key != "_RNA_UI")
    if not keys:
        return {}
    semantic_values: dict[str, Any] = {}
    nested_property_keys: dict[str, list[str]] = {}
    unreadable_keys: list[str] = []
    for key in keys:
        try:
            value = data_block[key]
            if hasattr(value, "keys"):
                nested_property_keys[key] = sorted(str(child) for child in value.keys())[:200]
            is_scalar = isinstance(value, (bool, int, float, str))
            is_scalar_sequence = isinstance(value, (list, tuple)) and all(
                isinstance(item, (bool, int, float, str)) for item in value
            )
            if key.casefold().startswith(SEMANTIC_PROPERTY_PREFIXES) and (
                is_scalar or is_scalar_sequence
            ):
                semantic_values[key] = _json_value(value)
        except (ReferenceError, TypeError, ValueError) as error:
            unreadable_keys.append(f"{key}:{type(error).__name__}")
    properties: dict[str, Any] = {"keys": keys}
    if semantic_values:
        properties["semantic_values"] = semantic_values
    if nested_property_keys:
        properties["nested_property_keys"] = nested_property_keys
    if unreadable_keys:
        properties["unreadable_keys"] = unreadable_keys
    return properties


def _animation(animation_data: Any) -> dict[str, Any] | None:
    if animation_data is None:
        return None
    action = getattr(animation_data, "action", None)
    nla_tracks = list(getattr(animation_data, "nla_tracks", ()))
    drivers = list(getattr(animation_data, "drivers", ()))
    return {
        "action": action.name if action else None,
        "nla_tracks": [track.name for track in nla_tracks],
        "driver_count": len(drivers),
    }


def _layer_collections() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def visit(layer_collection: Any, view_layer_name: str, parent_path: str) -> None:
        path = f"{parent_path}/{layer_collection.name}" if parent_path else layer_collection.name
        rows.append(
            {
                "view_layer": view_layer_name,
                "path": path,
                "collection": layer_collection.collection.name,
                "exclude": bool(layer_collection.exclude),
                "hide_viewport": bool(layer_collection.hide_viewport),
                "holdout": bool(layer_collection.holdout),
                "indirect_only": bool(layer_collection.indirect_only),
                "is_visible": bool(layer_collection.visible_get()),
            }
        )
        for child in layer_collection.children:
            visit(child, view_layer_name, path)

    for scene in bpy.data.scenes:
        for view_layer in scene.view_layers:
            visit(view_layer.layer_collection, f"{scene.name}/{view_layer.name}", "")
    return rows


def _collection_parent_map() -> dict[str, list[str]]:
    parents: dict[str, list[str]] = defaultdict(list)
    for parent in bpy.data.collections:
        for child in parent.children:
            parents[child.name].append(parent.name)
    for scene in bpy.data.scenes:
        for child in scene.collection.children:
            parents[child.name].append(f"SCENE:{scene.name}")
    return {name: sorted(values) for name, values in parents.items()}


def _material_users() -> dict[str, list[str]]:
    users: dict[str, set[str]] = defaultdict(set)
    for obj in bpy.data.objects:
        for slot in obj.material_slots:
            if slot.material:
                users[slot.material.name].add(obj.name)
    return {name: sorted(values) for name, values in users.items()}


def _semantic_tags(obj: Any) -> list[dict[str, str]]:
    text = " ".join([obj.name, *(collection.name for collection in obj.users_collection)]).lower()
    named_patterns = {
        "floor": r"(?:^|[^a-z])(floor|ground|slab|deck)(?:$|[^a-z])",
        "wall": r"(?:^|[^a-z])wall(?:$|[^a-z])",
        "stair": r"(?:^|[^a-z])(stair|stairs|staircase|step)(?:$|[^a-z])",
        "walkable": (
            r"(?:^|[^a-z])"
            r"(walkable|walkway|navmesh|navigation|corridor|hallway|path)"
            r"(?:$|[^a-z])"
        ),
        "semantic_area": r"(?:^|[^a-z])area(?:$|[^a-z])",
        "portal": r"(?:^|[^a-z])(portal|door|entrance|exit)(?:$|[^a-z])",
    }
    tags = []
    wall_decor_tokens = ("wall lamp", "wall clock", "on-wall", "speaker")
    for category, pattern in named_patterns.items():
        if not re.search(pattern, text):
            continue
        if category == "wall" and any(token in text for token in wall_decor_tokens):
            continue
        tags.append(
            {
                "category": category,
                "basis": "name_or_collection",
                "confidence": "review_required",
            }
        )
    if obj.type == "MESH":
        x, y, z = (abs(float(value)) for value in obj.dimensions)
        short_horizontal = z <= max(0.01, min(x, y) * 0.05)
        large_horizontal = short_horizontal and x * y >= 10_000
        if large_horizontal:
            tags.append(
                {
                    "category": "large_horizontal_surface",
                    "basis": "dimensions_only",
                    "confidence": "low",
                }
            )
        wall_like = z >= 50 and min(x, y) <= max(1.0, max(x, y) * 0.05)
        if wall_like:
            tags.append(
                {"category": "vertical_barrier", "basis": "dimensions_only", "confidence": "low"}
            )
    return tags


def _object_row(obj: Any, scene_object_names: set[str]) -> dict[str, Any]:
    mesh_stats = None
    if obj.type == "MESH" and obj.data:
        mesh_stats = {
            "vertices": len(obj.data.vertices),
            "edges": len(obj.data.edges),
            "polygons": len(obj.data.polygons),
            "loops": len(obj.data.loops),
        }
    return {
        "name": obj.name,
        "type": obj.type,
        "data_name": obj.data.name if obj.data else None,
        "linked_collections": sorted(collection.name for collection in obj.users_collection),
        "in_active_scene": obj.name in scene_object_names,
        "hide_viewport": bool(obj.hide_viewport),
        "hide_render": bool(obj.hide_render),
        "hide_get": bool(obj.hide_get()),
        "display_type": obj.display_type,
        "parent": obj.parent.name if obj.parent else None,
        "location": _vector(obj.location),
        "rotation_mode": obj.rotation_mode,
        "rotation_euler_radians": _vector(obj.rotation_euler),
        "scale": _vector(obj.scale),
        "dimensions": _vector(obj.dimensions),
        "matrix_world": _matrix(obj.matrix_world),
        "mesh": mesh_stats,
        "material_slots": [
            slot.material.name if slot.material else None for slot in obj.material_slots
        ],
        "modifiers": [
            {
                "name": modifier.name,
                "type": modifier.type,
                "show_viewport": bool(modifier.show_viewport),
                "show_render": bool(modifier.show_render),
            }
            for modifier in obj.modifiers
        ],
        "constraints": [
            {
                "name": constraint.name,
                "type": constraint.type,
                "enabled": bool(constraint.enabled),
                "influence": _float(constraint.influence),
                "target": getattr(getattr(constraint, "target", None), "name", None),
            }
            for constraint in obj.constraints
        ],
        "animation": _animation(obj.animation_data),
        "semantic_tags": _semantic_tags(obj),
        "custom_properties": _custom_properties(obj),
    }


def _camera_row(obj: Any, active_cameras: dict[str, str | None]) -> dict[str, Any]:
    camera = obj.data
    rotation = obj.matrix_world.to_quaternion()
    forward = rotation @ Vector((0.0, 0.0, -1.0))
    up = rotation @ Vector((0.0, 1.0, 0.0))
    return {
        "object_name": obj.name,
        "data_name": camera.name,
        "active_in_scenes": sorted(
            scene_name
            for scene_name, camera_name in active_cameras.items()
            if camera_name == obj.name
        ),
        "linked_collections": sorted(collection.name for collection in obj.users_collection),
        "location": _vector(obj.matrix_world.translation),
        "rotation_mode": obj.rotation_mode,
        "rotation_euler_radians": _vector(obj.rotation_euler),
        "rotation_quaternion_wxyz": _vector(rotation),
        "scale": _vector(obj.scale),
        "matrix_world_camera_to_world": _matrix(obj.matrix_world),
        "matrix_world_to_camera": _matrix(obj.matrix_world.inverted_safe()),
        "forward_world": _vector(forward),
        "up_world": _vector(up),
        "projection_type": camera.type,
        "lens_mm": _nullable_float(camera.lens),
        "lens_is_finite": math.isfinite(float(camera.lens)),
        "lens_nonfinite_value": None if math.isfinite(float(camera.lens)) else str(camera.lens),
        "ortho_scale": _nullable_float(camera.ortho_scale),
        "sensor_fit": camera.sensor_fit,
        "sensor_width_mm": _float(camera.sensor_width),
        "sensor_height_mm": _float(camera.sensor_height),
        "shift_x": _float(camera.shift_x),
        "shift_y": _float(camera.shift_y),
        "clip_start": _float(camera.clip_start),
        "clip_end": _float(camera.clip_end),
        "angle_x_radians": _float(camera.angle_x),
        "angle_y_radians": _float(camera.angle_y),
        "angle_x_degrees": _float(math.degrees(camera.angle_x)),
        "angle_y_degrees": _float(math.degrees(camera.angle_y)),
        "hide_viewport": bool(obj.hide_viewport),
        "hide_render": bool(obj.hide_render),
        "custom_properties": _custom_properties(obj),
        "data_custom_properties": _custom_properties(camera),
    }


def _light_row(obj: Any) -> dict[str, Any]:
    light = obj.data
    return {
        "object_name": obj.name,
        "data_name": light.name,
        "type": light.type,
        "energy": _float(light.energy),
        "color": _vector(light.color),
        "location": _vector(obj.matrix_world.translation),
        "rotation_euler_radians": _vector(obj.rotation_euler),
        "scale": _vector(obj.scale),
        "hide_viewport": bool(obj.hide_viewport),
        "hide_render": bool(obj.hide_render),
        "linked_collections": sorted(collection.name for collection in obj.users_collection),
        "custom_properties": _custom_properties(obj),
    }


def _duplicate_groups(objects: list[Any]) -> dict[str, Any]:
    normalized: dict[str, list[str]] = defaultdict(list)
    shared_data: dict[tuple[str, str], list[str]] = defaultdict(list)
    geometry: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for obj in objects:
        normalized_name = re.sub(r"\.\d{3}$", "", obj.name).casefold()
        normalized[normalized_name].append(obj.name)
        if obj.data:
            shared_data[(obj.type, obj.data.name)].append(obj.name)
        if obj.type == "MESH" and obj.data:
            dimensions = tuple(round(abs(float(value)), 4) for value in obj.dimensions)
            signature = (
                len(obj.data.vertices),
                len(obj.data.edges),
                len(obj.data.polygons),
                dimensions,
                tuple(slot.material.name if slot.material else None for slot in obj.material_slots),
            )
            geometry[signature].append(obj.name)

    def rows(groups: dict[Any, list[str]], label: str) -> list[dict[str, Any]]:
        result = []
        for key, names in groups.items():
            if len(names) < 2:
                continue
            result.append(
                {
                    label: _json_value(key),
                    "count": len(names),
                    "object_names": sorted(names)[:MAX_NAMES_PER_GROUP],
                    "names_truncated": len(names) > MAX_NAMES_PER_GROUP,
                    "manual_review_only": True,
                }
            )
        return sorted(result, key=lambda row: (-row["count"], str(row[label])))

    return {
        "normalized_name_groups": rows(normalized, "normalized_name"),
        "shared_data_instance_groups": rows(shared_data, "type_and_data"),
        "coarse_geometry_signature_candidates": rows(geometry, "signature"),
        "interpretation": (
            "Shared datablocks usually indicate intentional instances. Coarse signatures use "
            "counts, dimensions, and materials only; neither category authorizes deletion."
        ),
    }


def _orphan_data() -> dict[str, list[dict[str, Any]]]:
    collection_names = [
        "actions",
        "armatures",
        "cameras",
        "collections",
        "curves",
        "images",
        "lights",
        "materials",
        "meshes",
        "node_groups",
        "objects",
        "textures",
        "worlds",
    ]
    result: dict[str, list[dict[str, Any]]] = {}
    for collection_name in collection_names:
        collection = getattr(bpy.data, collection_name, None)
        if collection is None:
            continue
        rows = []
        for data_block in collection:
            if getattr(data_block, "users", 0) != 0:
                continue
            rows.append(
                {
                    "name": data_block.name,
                    "use_fake_user": bool(getattr(data_block, "use_fake_user", False)),
                }
            )
        if rows:
            result[collection_name] = sorted(rows, key=lambda row: row["name"])
    return result


def _image_row(image: Any) -> dict[str, Any]:
    raw_path = image.filepath
    absolute_path = bpy.path.abspath(raw_path) if raw_path else ""
    if not raw_path:
        reported_path = ""
        path_kind = "empty"
    elif raw_path.startswith("//"):
        reported_path = raw_path
        path_kind = "blend_relative"
    elif Path(raw_path).is_absolute():
        reported_path = Path(raw_path).name
        path_kind = "absolute_redacted_to_basename"
    else:
        reported_path = raw_path
        path_kind = "relative"
    is_file_backed = image.source in {"FILE", "TILED", "SEQUENCE", "MOVIE"}
    exists = None
    if absolute_path and is_file_backed and "<UDIM>" not in absolute_path:
        exists = os.path.exists(absolute_path)
    return {
        "name": image.name,
        "source": image.source,
        "filepath": reported_path,
        "path_kind": path_kind,
        "exists": exists,
        "packed": bool(image.packed_file or image.packed_files),
        "packed_file_count": len(image.packed_files),
        "width": int(image.size[0]),
        "height": int(image.size[1]),
        "channels": int(image.channels),
        "depth": int(image.depth),
        "file_format": image.file_format,
        "colorspace": image.colorspace_settings.name,
        "users": int(image.users),
        "use_fake_user": bool(image.use_fake_user),
    }


def _build_report(source_path: Path, expected_sha256: str) -> dict[str, Any]:
    actual_sha256 = _sha256(source_path)
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            "source hash changed before Blender audit started: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )

    scene = bpy.context.scene
    scene_object_names = {obj.name for obj in scene.objects}
    objects = sorted(bpy.data.objects, key=lambda item: item.name)
    object_rows = [_object_row(obj, scene_object_names) for obj in objects]
    active_cameras = {
        item.name: item.camera.name if item.camera else None for item in bpy.data.scenes
    }
    cameras = [_camera_row(obj, active_cameras) for obj in objects if obj.type == "CAMERA"]
    lights = [_light_row(obj) for obj in objects if obj.type == "LIGHT"]
    collection_parents = _collection_parent_map()
    layer_collections = _layer_collections()
    material_users = _material_users()

    collections = []
    for collection in sorted(bpy.data.collections, key=lambda item: item.name):
        collections.append(
            {
                "name": collection.name,
                "parents": collection_parents.get(collection.name, []),
                "children": sorted(child.name for child in collection.children),
                "direct_object_count": len(collection.objects),
                "all_object_count": len(collection.all_objects),
                "direct_object_names": sorted(obj.name for obj in collection.objects),
                "hide_viewport": bool(collection.hide_viewport),
                "hide_render": bool(collection.hide_render),
                "instance_offset": _vector(collection.instance_offset),
                "custom_properties": _custom_properties(collection),
            }
        )

    materials = []
    for material in sorted(bpy.data.materials, key=lambda item: item.name):
        materials.append(
            {
                "name": material.name,
                "users": int(material.users),
                "use_nodes": bool(material.use_nodes),
                "object_users": material_users.get(material.name, []),
                "custom_properties": _custom_properties(material),
            }
        )

    meshes = []
    for mesh in sorted(bpy.data.meshes, key=lambda item: item.name):
        meshes.append(
            {
                "name": mesh.name,
                "users": int(mesh.users),
                "vertices": len(mesh.vertices),
                "edges": len(mesh.edges),
                "polygons": len(mesh.polygons),
                "loops": len(mesh.loops),
                "material_names": [
                    material.name if material else None for material in mesh.materials
                ],
                "shape_keys": mesh.shape_keys.name if mesh.shape_keys else None,
                "custom_properties": _custom_properties(mesh),
            }
        )

    images = [_image_row(image) for image in sorted(bpy.data.images, key=lambda item: item.name)]
    missing_images = [
        {"name": image["name"], "filepath": image["filepath"]}
        for image in images
        if image["exists"] is False and not image["packed"]
    ]
    type_counts = dict(sorted(Counter(obj.type for obj in objects).items()))
    mesh_objects = [obj for obj in objects if obj.type == "MESH" and obj.data]
    total_polygons = sum(len(obj.data.polygons) for obj in mesh_objects)
    total_vertices = sum(len(obj.data.vertices) for obj in mesh_objects)
    high_poly = sorted(
        (
            {
                "object_name": obj.name,
                "mesh_name": obj.data.name,
                "vertices": len(obj.data.vertices),
                "polygons": len(obj.data.polygons),
                "dimensions": _vector(obj.dimensions),
                "linked_collections": sorted(c.name for c in obj.users_collection),
            }
            for obj in mesh_objects
            if len(obj.data.polygons) >= HIGH_POLY_THRESHOLD
        ),
        key=lambda row: (-row["polygons"], row["object_name"]),
    )
    top_meshes = sorted(
        (
            {
                "object_name": obj.name,
                "mesh_name": obj.data.name,
                "vertices": len(obj.data.vertices),
                "polygons": len(obj.data.polygons),
                "dimensions": _vector(obj.dimensions),
            }
            for obj in mesh_objects
        ),
        key=lambda row: (-row["polygons"], row["object_name"]),
    )[:30]

    semantic_candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in object_rows:
        for tag in row["semantic_tags"]:
            semantic_candidates[tag["category"]].append(
                {
                    "object_name": row["name"],
                    "object_type": row["type"],
                    "dimensions": row["dimensions"],
                    "basis": tag["basis"],
                    "confidence": tag["confidence"],
                    "custom_properties": row["custom_properties"],
                }
            )

    area_objects = [obj for obj in objects if obj.name.startswith("AREA_")]
    portal_objects = [obj for obj in objects if obj.name.startswith("PORTAL_")]
    stair_area_objects = [obj for obj in area_objects if "STAIR" in obj.name.upper()]

    def semantic_box_row(obj: Any) -> dict[str, Any]:
        mesh = obj.data if obj.type == "MESH" else None
        return {
            "object_name": obj.name,
            "object_type": obj.type,
            "location": _vector(obj.location),
            "dimensions": _vector(obj.dimensions),
            "vertices": len(mesh.vertices) if mesh else None,
            "polygons": len(mesh.polygons) if mesh else None,
            "material_slot_count": len(obj.material_slots),
            "custom_properties": _custom_properties(obj),
            "linked_collections": sorted(collection.name for collection in obj.users_collection),
        }

    area_box_rows = [semantic_box_row(obj) for obj in area_objects]
    portal_box_rows = [semantic_box_row(obj) for obj in portal_objects]
    cross_floor_portal_overlaps: list[dict[str, Any]] = []
    portal_transform_groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for obj in portal_objects:
        signature = (
            tuple(round(float(value), 6) for value in obj.location),
            tuple(round(abs(float(value)), 6) for value in obj.dimensions),
        )
        portal_transform_groups[signature].append(obj.name)
    for signature, names in portal_transform_groups.items():
        has_1f = any(name.startswith("PORTAL_1F_") for name in names)
        has_2f = any(name.startswith("PORTAL_2F_") for name in names)
        if has_1f and has_2f:
            cross_floor_portal_overlaps.append(
                {
                    "object_names": sorted(names),
                    "location": list(signature[0]),
                    "dimensions": list(signature[1]),
                }
            )

    imported_cameras = [
        camera
        for camera in cameras
        if camera["object_name"].lower().startswith("skp_")
        or "last_saved" in camera["object_name"].lower()
    ]
    research_cameras = [camera for camera in cameras if camera["object_name"].startswith("CAM_")]
    outer_lights = [light for light in lights if light["object_name"].startswith("OUTER3X3_")]
    decoration_tokens = (
        "book",
        "box",
        "chair",
        "clock",
        "poster",
        "sofa",
        "table",
        "cabinet",
        "carpet",
        "garland",
        "lectern",
        "speaker",
        "trash",
        "trolley",
    )
    decoration_collections = [
        {
            "collection": collection["name"],
            "object_count": collection["all_object_count"],
            "reason": (
                "name suggests furnishing or decoration; may still affect occlusion/collision"
            ),
        }
        for collection in collections
        if any(token in collection["name"].lower() for token in decoration_tokens)
    ]

    scene_dimensions = None
    if mesh_objects:
        world_points = [
            obj.matrix_world @ Vector(corner) for obj in mesh_objects for corner in obj.bound_box
        ]
        minimum = Vector(min(point[i] for point in world_points) for i in range(3))
        maximum = Vector(max(point[i] for point in world_points) for i in range(3))
        scene_dimensions = {
            "minimum": _vector(minimum),
            "maximum": _vector(maximum),
            "extent": _vector(maximum - minimum),
        }

    findings: list[dict[str, Any]] = []
    camera_z_values = [camera["location"][2] for camera in research_cameras]
    if (
        scene.unit_settings.system == "METRIC"
        and _float(scene.unit_settings.scale_length) == 1.0
        and camera_z_values
        and min(camera_z_values) > 20.0
    ):
        findings.append(
            {
                "code": "UNIT_SCALE_REVIEW_REQUIRED",
                "severity": "blocking_for_metric_evaluation",
                "summary": (
                    "The scene declares metres at scale 1.0, while research-camera Z values are "
                    "approximately 132-295 scene units. A world-unit-to-metre contract is not "
                    "encoded clearly enough for metric trajectory evaluation."
                ),
                "evidence": {
                    "unit_system": scene.unit_settings.system,
                    "scale_length": _float(scene.unit_settings.scale_length),
                    "research_camera_z_range": [min(camera_z_values), max(camera_z_values)],
                    "scene_bounds": scene_dimensions,
                },
            }
        )
    if imported_cameras:
        findings.append(
            {
                "code": "IMPORTED_CAMERA_REVIEW_CANDIDATE",
                "severity": "review",
                "summary": (
                    f"Found {len(research_cameras)} CAM_* research cameras plus "
                    f"{len(imported_cameras)} imported/navigation camera candidate(s)."
                ),
                "evidence": [camera["object_name"] for camera in imported_cameras],
            }
        )
    invalid_intrinsics = [camera for camera in cameras if not camera["lens_is_finite"]]
    if invalid_intrinsics:
        findings.append(
            {
                "code": "NONFINITE_CAMERA_INTRINSICS",
                "severity": "blocking_for_camera_allowlist",
                "summary": (
                    f"{len(invalid_intrinsics)} camera(s) have a non-finite lens value. "
                    "They cannot be used for calibrated projection without an approved correction."
                ),
                "evidence": [
                    {
                        "object_name": camera["object_name"],
                        "lens_nonfinite_value": camera["lens_nonfinite_value"],
                    }
                    for camera in invalid_intrinsics
                ],
            }
        )
    area_collection = next(
        (collection for collection in collections if collection["name"] == "Areas"), None
    )
    if area_box_rows or portal_box_rows:
        simple_box_count = sum(
            row["object_type"] == "MESH"
            and row["vertices"] == 8
            and row["polygons"] == 6
            and row["material_slot_count"] == 0
            and not row["custom_properties"]
            for row in [*area_box_rows, *portal_box_rows]
        )
        findings.append(
            {
                "code": "AREA_PORTAL_BOXES_ARE_NOT_WALKABLE_GEOMETRY",
                "severity": "blocking_for_automatic_navmesh",
                "summary": (
                    f"The scene has {len(area_box_rows)} AREA_* and {len(portal_box_rows)} "
                    "PORTAL_* objects. They are semantic volumes/boxes without an encoded "
                    "walkable-surface or topology contract."
                ),
                "evidence": {
                    "area_count": len(area_box_rows),
                    "portal_count": len(portal_box_rows),
                    "simple_unannotated_box_count": simple_box_count,
                    "areas_collection_hide_render": (
                        area_collection["hide_render"] if area_collection else None
                    ),
                },
            }
        )
    if stair_area_objects:
        stair_portals = [obj.name for obj in portal_objects if "STAIR" in obj.name.upper()]
        if not stair_portals and all(not _custom_properties(obj) for obj in stair_area_objects):
            findings.append(
                {
                    "code": "STAIR_TRANSITION_METADATA_MISSING",
                    "severity": "blocking_for_cross_floor_topology",
                    "summary": (
                        "Stair AREA boxes exist, but no stair entry/exit portals, direction, "
                        "floor connection, or parameterized path metadata is encoded."
                    ),
                    "evidence": {
                        "stair_areas": [semantic_box_row(obj) for obj in stair_area_objects],
                        "stair_portals": stair_portals,
                    },
                }
            )
    if cross_floor_portal_overlaps:
        findings.append(
            {
                "code": "CROSS_FLOOR_PORTAL_TRANSFORM_OVERLAP",
                "severity": "scene_data_review",
                "summary": (
                    "At least one 1F/2F portal pair has an identical transform and dimensions; "
                    "the floor label or placement may be incorrect."
                ),
                "evidence": cross_floor_portal_overlaps,
            }
        )
    explicit_navmesh = semantic_candidates.get("walkable", [])
    navmesh_named = []
    for obj in objects:
        searchable = " ".join(
            [
                obj.name,
                *(collection.name for collection in obj.users_collection),
                *(_custom_properties(obj).keys()),
                *(str(value) for value in _custom_properties(obj).values()),
            ]
        ).lower()
        if "navmesh" in searchable or "walkable" in searchable:
            navmesh_named.append(obj.name)
    if not navmesh_named:
        findings.append(
            {
                "code": "NO_EXPLICIT_NAVMESH_OBJECT",
                "severity": "blocking_for_automatic_navmesh",
                "summary": (
                    "No object name explicitly identifies a NavMesh or walkable surface. "
                    "AREA_* and "
                    "stair candidates exist, but their geometry semantics require confirmation."
                ),
                "evidence": {
                    "walkable_tagged_objects": len(explicit_navmesh),
                    "walkable_mesh_candidates": sum(
                        item["object_type"] == "MESH" for item in explicit_navmesh
                    ),
                    "semantic_area_candidates": len(semantic_candidates.get("semantic_area", [])),
                    "stair_candidates": len(semantic_candidates.get("stair", [])),
                },
            }
        )
    if high_poly:
        findings.append(
            {
                "code": "HIGH_POLY_OBJECTS",
                "severity": "performance_review",
                "summary": (
                    f"{len(high_poly)} mesh objects meet the {HIGH_POLY_THRESHOLD:,}-polygon "
                    "review threshold. This is a complexity signal, not a deletion decision."
                ),
                "evidence": [row["object_name"] for row in high_poly],
            }
        )
    if outer_lights:
        findings.append(
            {
                "code": "OUTER_LIGHT_GRID_NOT_REQUIRED_FOR_GEOMETRY",
                "severity": "review",
                "summary": (
                    f"{len(outer_lights)} OUTER3X3 area lights exist. They are not needed by the "
                    "geometry-only Phase 1 algorithms but may be needed for synthetic rendering."
                ),
                "evidence": [light["object_name"] for light in outer_lights],
            }
        )
    if len(materials) >= 100 or len(images) >= 100:
        findings.append(
            {
                "code": "LARGE_APPEARANCE_ASSET_SET",
                "severity": "performance_review",
                "summary": (
                    f"The file contains {len(materials)} materials and {len(images)} images; "
                    "Phase 1 "
                    "geometry processing should avoid loading appearance data where possible."
                ),
                "evidence": {"materials": len(materials), "images": len(images)},
            }
        )
    if missing_images:
        findings.append(
            {
                "code": "MISSING_EXTERNAL_IMAGES",
                "severity": "render_review",
                "summary": f"{len(missing_images)} unpacked file-backed images are missing.",
                "evidence": missing_images,
            }
        )

    for finding in findings:
        finding.setdefault("confidence", "high")
        finding.setdefault("status", "candidate")
        finding.setdefault("recommended_action", "manual_review_only")
        finding.setdefault("destructive_action_authorized", False)

    report = {
        "schema_version": "1.0.0",
        "audit_kind": "READ_ONLY_SCENE_AUDIT",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": {
            "filepath": str(source_path),
            "filename": source_path.name,
            "size_bytes": source_path.stat().st_size,
            "sha256_during_blender_run": actual_sha256,
        },
        "blender": {
            "version": bpy.app.version_string,
            "version_tuple": list(bpy.app.version),
            "build_hash": bpy.app.build_hash.decode(errors="replace"),
            "background": bool(bpy.app.background),
            "file_version": list(bpy.data.version),
        },
        "read_only_contract": {
            "save_operation_performed": False,
            "source_hash_expected": expected_sha256,
            "source_hash_verified_during_audit": actual_sha256 == expected_sha256,
            "note": (
                "This script contains no bpy save call; the wrapper verifies the source hash again."
            ),
        },
        "active_scene": {
            "name": scene.name,
            "camera": scene.camera.name if scene.camera else None,
            "frame_start": int(scene.frame_start),
            "frame_end": int(scene.frame_end),
            "frame_current": int(scene.frame_current),
            "fps": int(scene.render.fps),
            "fps_base": _float(scene.render.fps_base),
            "resolution_x": int(scene.render.resolution_x),
            "resolution_y": int(scene.render.resolution_y),
            "resolution_percentage": int(scene.render.resolution_percentage),
            "render_engine": scene.render.engine,
            "unit_settings": {
                "system": scene.unit_settings.system,
                "scale_length": _float(scene.unit_settings.scale_length),
                "length_unit": scene.unit_settings.length_unit,
                "mass_unit": scene.unit_settings.mass_unit,
                "time_unit": scene.unit_settings.time_unit,
                "temperature_unit": scene.unit_settings.temperature_unit,
                "use_separate": bool(scene.unit_settings.use_separate),
                "system_rotation": scene.unit_settings.system_rotation,
            },
            "world": scene.world.name if scene.world else None,
            "object_count": len(scene.objects),
            "bounds": scene_dimensions,
            "custom_properties": _custom_properties(scene),
        },
        "scenes": [
            {
                "name": item.name,
                "camera": item.camera.name if item.camera else None,
                "object_count": len(item.objects),
                "view_layers": [layer.name for layer in item.view_layers],
            }
            for item in sorted(bpy.data.scenes, key=lambda value: value.name)
        ],
        "counts": {
            "objects": len(objects),
            "object_types": type_counts,
            "collections": len(bpy.data.collections),
            "cameras": len(cameras),
            "research_cameras_cam_prefix": len(research_cameras),
            "lights": len(lights),
            "meshes": len(bpy.data.meshes),
            "mesh_object_vertices": total_vertices,
            "mesh_object_polygons": total_polygons,
            "materials": len(materials),
            "images": len(images),
            "textures": len(bpy.data.textures),
            "actions": len(bpy.data.actions),
        },
        "inventory": {
            "objects": object_rows,
            "collections": collections,
            "layer_collections": layer_collections,
            "hidden_layer_collections": [
                row
                for row in layer_collections
                if row["exclude"] or row["hide_viewport"] or not row["is_visible"]
            ],
            "cameras": cameras,
            "lights": lights,
            "meshes": meshes,
            "materials": materials,
            "images": images,
            "textures": [
                {"name": texture.name, "type": texture.type, "users": int(texture.users)}
                for texture in sorted(bpy.data.textures, key=lambda item: item.name)
            ],
            "actions": [
                {
                    "name": action.name,
                    "users": int(action.users),
                    "frame_range": _vector(action.frame_range),
                    "use_fake_user": bool(action.use_fake_user),
                }
                for action in sorted(bpy.data.actions, key=lambda item: item.name)
            ],
            "libraries": [
                {"name": library.name, "filepath": library.filepath}
                for library in sorted(bpy.data.libraries, key=lambda item: item.name)
            ],
        },
        "analysis": {
            "high_poly_threshold_polygons": HIGH_POLY_THRESHOLD,
            "high_poly_objects": high_poly,
            "top_mesh_objects_by_polygons": top_meshes,
            "duplicate_looking": _duplicate_groups(objects),
            "unused_or_hidden_objects": {
                "unlinked_to_collection": [obj.name for obj in objects if not obj.users_collection],
                "not_in_active_scene": [
                    obj.name for obj in objects if obj.name not in scene_object_names
                ],
                "hidden_in_viewport_and_render": [
                    obj.name for obj in objects if obj.hide_viewport and obj.hide_render
                ],
            },
            "orphan_data": _orphan_data(),
            "empty_or_helper_objects": [
                row
                for row in object_rows
                if row["type"] == "EMPTY"
                or any(
                    token in row["name"].lower()
                    for token in ("helper", "proxy", "guide", "origin", "control", "rig")
                )
            ],
            "semantic_geometry_candidates": {
                key: sorted(value, key=lambda row: row["object_name"])
                for key, value in sorted(semantic_candidates.items())
            },
            "semantic_area_box_inventory": {
                "area_objects": area_box_rows,
                "portal_objects": portal_box_rows,
                "cross_floor_portal_transform_overlaps": cross_floor_portal_overlaps,
                "interpretation": (
                    "AREA_* and PORTAL_* boxes are semantic candidates only; they do not prove "
                    "walkable surfaces, navigation edges, or stair transitions."
                ),
            },
            "suspected_nonessential_assets": {
                "imported_camera_candidates": imported_cameras,
                "lighting_review_candidates": outer_lights,
                "decorative_or_furnishing_collections": decoration_collections,
                "interpretation": (
                    "These are review candidates only. Furniture can be a physical obstacle and "
                    "lights can be required for synthetic observations; nothing was removed."
                ),
            },
            "missing_external_images": missing_images,
            "core_findings": findings,
        },
    }
    return report


def main() -> None:
    args = _args()
    source_path = Path(bpy.data.filepath).resolve()
    if not source_path.is_file():
        raise RuntimeError("Blender must open a saved .blend file before this audit runs")
    report = _build_report(source_path, args.expected_source_sha256)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"SCENE_AUDIT_JSON={args.json_output}")
    print(f"SCENE_AUDIT_SOURCE_SHA256={report['source']['sha256_during_blender_run']}")


if __name__ == "__main__":
    main()
