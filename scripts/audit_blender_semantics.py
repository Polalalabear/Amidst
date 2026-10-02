"""Blender-only read-only inventory; labels never establish physical authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import bpy
from mathutils import Vector

PREFIXES = ("AREA_", "PORTAL_", "WALKABLE_", "WALL_", "OBSTACLE_", "STAIR_", "CAM_")
SEMANTIC_KEYS = (
    "semantic_class",
    "semantic_role",
    "floor_id",
    "zone_id",
    "region_id",
    "trusted",
    "review_status",
    "collision_role",
    "clearance_policy",
)


def finite_vector(values: Any) -> list[float]:
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ValueError("nonfinite geometry cannot be inventoried as valid coordinates")
    return result


def bounds(points: list[list[float]]) -> dict[str, list[float]]:
    return {
        "minimum": [min(point[axis] for point in points) for axis in range(3)],
        "maximum": [max(point[axis] for point in points) for axis in range(3)],
    }


def label(name: str) -> dict[str, Any]:
    prefix = next((prefix for prefix in PREFIXES if name.startswith(prefix)), None)
    match = re.search(r"(?:^|_)(\d+F)(?:_|$)", name)
    return {
        "semantic_class": prefix[:-1] if prefix else "UNCLASSIFIED",
        "classification_basis": "EXPLICIT_NAME_PREFIX" if prefix else "NONE",
        "floor": None,
        "declared_floor_label": match.group(1) if match else None,
        "floor_label_basis": "NAME_TOKEN_ONLY" if match else None,
        "confidence": "NAME_LABEL_ONLY" if prefix else "NOT_ASSESSED",
        "trusted_status": "UNREVIEWED_NO_PHYSICAL_AUTHORITY",
        "physical_role_approved": False,
    }


def properties(owner: Any) -> dict[str, Any]:
    declared = {}
    for key in SEMANTIC_KEYS:
        if key in owner:
            value = owner[key]
            if isinstance(value, (str, bool, int)):
                declared[key] = value
            elif isinstance(value, float) and math.isfinite(value):
                declared[key] = value
            else:
                declared[key] = {"blender_property_type": type(value).__name__}
    return {"keys": sorted(owner.keys()), "declared_semantic_fields_unreviewed": declared}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    source = Path(bpy.data.filepath)
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != args.expected_source_sha256:
        raise ValueError("opened Blender source does not match the requested content")
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    rows = []
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        evaluated = obj.evaluated_get(depsgraph)
        matrix = evaluated.matrix_world
        row = {
            "object": obj.name,
            "object_type": obj.type,
            "collections": sorted(item.name for item in obj.users_collection),
            "parent": obj.parent.name if obj.parent else None,
            "in_active_scene": obj.name in scene.objects,
            "matrix_world": [finite_vector(values) for values in matrix],
            "custom_properties": properties(obj),
            **label(obj.name),
        }
        mesh_stats = None
        if obj.type == "MESH":
            mesh = evaluated.to_mesh()
            try:
                world = [finite_vector(matrix @ vertex.co) for vertex in mesh.vertices]
                empty_mesh = not world
                if empty_mesh:
                    world = [finite_vector(matrix.translation)]
                mesh_stats = {
                    "source_vertices": len(obj.data.vertices),
                    "source_edges": len(obj.data.edges),
                    "source_polygons": len(obj.data.polygons),
                    "evaluated_vertices": len(mesh.vertices),
                    "evaluated_edges": len(mesh.edges),
                    "evaluated_polygons": len(mesh.polygons),
                }
                center = [
                    math.fsum(point[axis] for point in world) / len(world) for axis in range(3)
                ]
            finally:
                evaluated.to_mesh_clear()
            row["geometry_status"] = (
                "EMPTY_EVALUATED_MESH" if empty_mesh else "EVALUATED_MESH_UNREVIEWED"
            )
            row["centroid_method"] = (
                "EMPTY_MESH_ORIGIN_NOT_SURFACE_CENTROID"
                if empty_mesh
                else "ARITHMETIC_MEAN_EVALUATED_WORLD_VERTICES"
            )
            row["bounding_box_method"] = (
                "EMPTY_MESH_DEGENERATE_ORIGIN_POINT_NOT_GEOMETRY"
                if empty_mesh
                else "EVALUATED_WORLD_VERTEX_AABB"
            )
        elif obj.type in {"CURVE", "FONT", "SURFACE"}:
            world = [finite_vector(matrix @ Vector(corner)) for corner in evaluated.bound_box]
            center = [math.fsum(point[axis] for point in world) / len(world) for axis in range(3)]
            row["centroid_method"] = "BOUNDING_BOX_CENTER"
            row["bounding_box_method"] = "EVALUATED_OBJECT_BOUNDING_BOX_WORLD_AABB"
        else:
            center = finite_vector(matrix.translation)
            world = [center]
            row["centroid_method"] = "OBJECT_ORIGIN_NOT_SURFACE_CENTROID"
            row["bounding_box_method"] = "DEGENERATE_ORIGIN_POINT_NOT_GEOMETRY"
        row.update(bounding_box=bounds(world), centroid=center, mesh_statistics=mesh_stats)
        semantic_class = row["semantic_class"]
        if semantic_class in {"AREA", "PORTAL"}:
            role = "ANNOTATION_ONLY_NOT_WALKABLE_OR_COLLIDER"
        elif semantic_class in {"WALKABLE", "WALL", "OBSTACLE", "STAIR"}:
            role = "EXPLICIT_PHYSICAL_LABEL_REQUIRES_OWNERSHIP_REVIEW"
        elif obj.type == "CAMERA":
            role = "CAMERA_CALIBRATION_REVIEW"
            lens = float(obj.data.lens)
            row["camera_lens"] = {
                "finite": math.isfinite(lens),
                "value": lens if math.isfinite(lens) else None,
            }
        elif obj.type == "MESH":
            role = "UNASSIGNED_MESH_SURFACE_OR_COLLIDER_REVIEW"
        else:
            role = "UNASSIGNED_HELPER_OR_PRESENTATION_REVIEW"
        row["candidate_role"] = role
        rows.append(row)
    by_name = {row["object"]: row for row in rows}
    collections = []
    for collection in sorted(bpy.data.collections, key=lambda item: item.name):
        members = sorted(obj.name for obj in collection.all_objects)
        corners = [point for name in members for point in by_name[name]["bounding_box"].values()]
        box = bounds(corners) if corners else None
        collections.append(
            {
                "collection": collection.name,
                **label(collection.name),
                "candidate_role": "COLLECTION_MEMBERSHIP_ONLY_NOT_PHYSICAL_AUTHORITY",
                "children": sorted(child.name for child in collection.children),
                "direct_objects": sorted(obj.name for obj in collection.objects),
                "all_object_count": len(members),
                "custom_properties": properties(collection),
                "bounding_box": box,
                "centroid": [
                    (low + high) / 2
                    for low, high in zip(
                        box["minimum"],
                        box["maximum"],
                        strict=True,
                    )
                ]
                if box
                else None,
                "centroid_method": "MEMBER_BOUNDING_BOX_CENTER",
                "mesh_statistics": {
                    "mesh_objects": sum(by_name[name]["object_type"] == "MESH" for name in members),
                    "evaluated_polygons": sum(
                        by_name[name]["mesh_statistics"]["evaluated_polygons"]
                        for name in members
                        if by_name[name]["mesh_statistics"] is not None
                    ),
                },
            }
        )
    payload = {
        "schema_version": "school-semantic-audit-v1",
        "audit_kind": "READ_ONLY_NAME_AND_GEOMETRY_INVENTORY_NO_AUTHORITY_INFERENCE",
        "source_sha256_during_blender_run": digest,
        "scene": {
            "name": scene.name,
            "frame": scene.frame_current,
            "subframe": scene.frame_subframe,
            "unit_system": scene.unit_settings.system,
            "scale_length": scene.unit_settings.scale_length,
        },
        "blender_version": bpy.app.version_string,
        "counts": {
            "objects": len(rows),
            "collections": len(collections),
            "object_types": dict(sorted(Counter(row["object_type"] for row in rows).items())),
            "explicit_object_prefixes": {
                prefix: sum(row["object"].startswith(prefix) for row in rows) for prefix in PREFIXES
            },
            "explicit_collection_prefixes": {
                prefix: sum(row["collection"].startswith(prefix) for row in collections)
                for prefix in PREFIXES
            },
        },
        "objects": rows,
        "collections": collections,
        "read_only_contract": {
            "save_called": False,
            "render_called": False,
            "autoexec_disabled_by_wrapper": True,
        },
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"semantic_inventory": str(args.output), "counts": payload["counts"]}))


if __name__ == "__main__":
    main()
