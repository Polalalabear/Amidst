"""Export full source components and exhaustive ROI selections without changing Blender.

An exact-coordinate weld establishes connectivity only. Output coordinates, source
vertex/triangle/face identities and winding remain the original evaluated source.
Region bounds select evidence; they never become colliders or prove semantic roles.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def content_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bounds(vertices: list[list[float]]) -> dict[str, list[float]]:
    return {
        "minimum": [min(point[axis] for point in vertices) for axis in range(3)],
        "maximum": [max(point[axis] for point in vertices) for axis in range(3)],
    }


def source_components(
    vertices: list[list[float]], triangles: list[list[int]]
) -> list[dict[str, Any]]:
    """Return complete edge-connected components using exact coincident coordinates."""
    identities: dict[tuple[float, ...], int] = {}
    welded = []
    for point in vertices:
        key = tuple(point)
        if key not in identities:
            identities[key] = len(identities)
        welded.append(identities[key])
    parent = list(range(len(triangles)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    edges: dict[tuple[int, int], int] = {}
    for index, triangle in enumerate(triangles):
        values = [welded[vertex] for vertex in triangle]
        for a, b in zip(values, values[1:] + values[:1], strict=True):
            edge = (min(a, b), max(a, b))
            previous = edges.get(edge)
            if previous is None:
                edges[edge] = index
            else:
                parent[find(index)] = find(previous)
    groups: dict[int, list[int]] = {}
    for index in range(len(triangles)):
        groups.setdefault(find(index), []).append(index)
    result = []
    for indices in sorted(groups.values(), key=lambda values: values[0]):
        referenced = sorted({vertex for index in indices for vertex in triangles[index]})
        result.append(
            {
                "component_id": f"component-{indices[0]:08d}",
                "source_triangle_indices": indices,
                "source_vertex_indices": referenced,
                "triangle_count": len(indices),
                "bounds_bu": bounds([vertices[index] for index in referenced]),
                "connectivity_basis": "EXACT_COINCIDENT_VERTEX_EDGE_CONNECTIVITY",
                "full_component_exported": True,
            }
        )
    return result


def selection_regions(
    audit: dict[str, Any], config: dict[str, Any], scale: float
) -> list[dict[str, Any]]:
    rows = {row["object"]: row for row in audit["objects"]}
    result = []
    for row in audit["objects"]:
        props = row["custom_properties"]
        if props.get("semantic_class") != "OBSTACLE":
            continue
        floor = props["floor_id"]
        box = bounds(row["vertices"])
        box["minimum"][2], box["maximum"][2] = config["obstacle_support_bands_bu"][floor]
        result.append(
            {
                "region_id": row["object"],
                "kind": "OBSTACLE_COMPONENT_SELECTION",
                "floor_id": floor,
                "annotation_object_id": row["object"],
                "bounds_bu": box,
            }
        )
    body = config["full_body_context"]
    for identity in body["walkable_ids"]:
        if identity not in rows or rows[identity]["custom_properties"].get(
            "semantic_class"
        ) != "WALKABLE":
            raise ValueError(f"full-body selection requires explicit WALKABLE: {identity}")
        row = rows[identity]
        floor = row["custom_properties"]["floor_id"]
        box = bounds(row["vertices"])
        for axis in (0, 1):
            box["minimum"][axis] -= body["horizontal_padding_m"] / scale
            box["maximum"][axis] += body["horizontal_padding_m"] / scale
        box["minimum"][2] = body["support_bands_bu"][floor][0]
        box["maximum"][2] = (
            body["support_bands_bu"][floor][1]
            + body["maximum_height_above_support_m"] / scale
        )
        result.append(
            {
                "region_id": f"BODY:{identity}",
                "kind": "FULL_BODY_CONTEXT",
                "floor_id": floor,
                "annotation_object_id": identity,
                "bounds_bu": box,
            }
        )
    for identity, box in config["stair_context_regions_bu"].items():
        result.append(
            {
                "region_id": identity,
                "kind": "STAIR_CONTEXT",
                "floor_id": None,
                "annotation_object_id": None,
                "bounds_bu": box,
            }
        )
    return sorted(result, key=lambda row: (row["kind"], row["region_id"]))


def main() -> None:
    bpy = importlib.import_module("bpy")
    np = importlib.import_module("numpy")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists():
        raise FileExistsError("source evidence output exists; use a fresh path")
    audit = json.loads(args.audit.read_text())
    config = json.loads(args.config.read_text())
    scale_path = Path(config["architectural_scale_config"])
    authority = json.loads(scale_path.read_text())
    scale = authority["metres_per_blender_unit"]
    source = Path(bpy.data.filepath).resolve()
    before = source.stat()
    digest = file_sha256(source)
    if (
        digest != args.expected_source_sha256
        or any(value != digest for value in (
            audit["source_sha256"], config["source_sha256"], authority["source_asset_sha256"]
        ))
        or authority["authority"] != "APPROVED"
        or not math.isfinite(scale)
        or scale <= 0
        or config["schema_version"] != "physical-policy-source-selection-v1"
    ):
        raise ValueError("source evidence requires matching approved source/scale bindings")
    scene = bpy.context.scene
    if audit["scene"] != {
        "name": scene.name, "frame": scene.frame_current, "subframe": scene.frame_subframe
    }:
        raise ValueError("source evidence context differs from audited source scene")
    maximum_mesh = config["maximum_mesh_triangles"]
    maximum_total = config["maximum_total_triangles"]
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in (maximum_mesh, maximum_total)):
        raise ValueError("source mesh budgets must be positive integers")
    regions = selection_regions(audit, config, scale)
    for region in regions:
        region.update(selection_complete=True, unresolved_reasons=[], selections=[])
    excluded = {row["object"] for row in audit["objects"]}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    meshes = []
    inspected = total = total_scene_triangles = 0
    # Exhaustive scene.objects iteration includes hidden objects; semantic/helpers
    # are excluded only via explicit audited identity or annotation property.
    for obj in sorted(scene.objects, key=lambda item: item.name):
        if obj.type != "MESH" or obj.name in excluded or obj.get("phase1_annotation_only", False):
            continue
        inspected += 1
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            if not mesh.vertices or not mesh.polygons:
                continue
            coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", coordinates)
            matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
            world = coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
            if not bool(np.isfinite(world).all()):
                raise ValueError(f"non-finite source geometry: {obj.name}")
            lo, hi = world.min(axis=0), world.max(axis=0)
            relevant = [region for region in regions if bool(
                (hi >= np.asarray(region["bounds_bu"]["minimum"])).all()
                and (lo <= np.asarray(region["bounds_bu"]["maximum"])).all()
            )]
            if not relevant:
                continue
            mesh.calc_loop_triangles()
            total_scene_triangles += len(mesh.loop_triangles)
            indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get("vertices", indices)
            triangles = indices.reshape(-1, 3)
            points = world[triangles]
            triangle_min, triangle_max = points.min(axis=1), points.max(axis=1)
            selections = []
            for region in relevant:
                box = region["bounds_bu"]
                mask = (
                    (triangle_max >= np.asarray(box["minimum"])).all(axis=1)
                    & (triangle_min <= np.asarray(box["maximum"])).all(axis=1)
                )
                wanted = np.flatnonzero(mask).tolist()
                # Keep empty surface selections too: a closed component can
                # enclose an ROI without any triangle touching the ROI box.
                selections.append((region, wanted))
            if len(triangles) > maximum_mesh or total + len(triangles) > maximum_total:
                for region, _ in selections:
                    region["selection_complete"] = False
                    region["unresolved_reasons"].append(f"SOURCE_MESH_BUDGET_EXCEEDED:{obj.name}")
                continue
            faces = np.empty(len(mesh.loop_triangles), dtype=np.int32)
            mesh.loop_triangles.foreach_get("polygon_index", faces)
            vertices_list, triangles_list = world.tolist(), triangles.tolist()
            components = source_components(vertices_list, triangles_list)
            identity = content_sha256({
                "source_object_id": obj.name,
                "vertices": vertices_list,
                "triangles": triangles_list,
                "triangle_source_face_indices": faces.tolist(),
            })
            payload = {
                "mesh_id": identity,
                "source_object_id": obj.name,
                "vertices": vertices_list,
                "triangles": triangles_list,
                "triangle_source_face_indices": faces.tolist(),
                "source_face_indices": sorted(set(faces.tolist())),
                "evaluated_vertex_count": len(mesh.vertices),
                "evaluated_triangle_count": len(triangles),
                "evaluated_polygon_count": len(mesh.polygons),
                "full_object_exported": True,
                "components": components,
                "hidden_render": bool(obj.hide_render),
                "hidden_viewport": bool(obj.hide_get()),
                "viewport_disabled": bool(obj.hide_viewport),
                "collection_disabled": any(collection.hide_viewport or collection.hide_render
                                           for collection in obj.users_collection),
                "semantic_role": "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY",
            }
            payload["geometry_sha256"] = content_sha256(payload)
            meshes.append(payload)
            total += len(triangles)
            for region, wanted in selections:
                box = region["bounds_bu"]
                region["selections"].append({
                    "mesh_id": identity,
                    "source_object_id": obj.name,
                    "source_triangle_indices": wanted,
                    "component_ids": [
                        component["component_id"] for component in components
                        if all(component["bounds_bu"]["minimum"][axis] <= box["maximum"][axis]
                               and component["bounds_bu"]["maximum"][axis] >= box["minimum"][axis]
                               for axis in range(3))
                    ],
                })
        finally:
            evaluated.to_mesh_clear()
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, digest) != (
        after.st_size, after.st_mtime_ns, file_sha256(source)
    ):
        raise RuntimeError("source changed during read-only evidence extraction")
    for region in regions:
        region["unresolved_reasons"] = sorted(set(region["unresolved_reasons"]))
        region["selected_triangle_count"] = sum(
            len(selection["source_triangle_indices"]) for selection in region["selections"]
        )
        region["selection_basis"] = "EXHAUSTIVE_SOURCE_TRIANGLE_AABB_SUPERSET_QUERY"
    document = {
        "schema_version": "physical-policy-source-evidence-v1",
        "source_sha256": digest,
        "source_size": before.st_size,
        "source_mtime_ns": before.st_mtime_ns,
        "audit_content_sha256": content_sha256(audit),
        "config_content_sha256": content_sha256(config),
        "architectural_scale_content_sha256": content_sha256(authority),
        "exporter_code_sha256": file_sha256(Path(__file__)),
        "architectural_scale": authority,
        "blender_version": bpy.app.version_string,
        "evaluated_scene": audit["scene"],
        "source_preserved": True,
        "saved": False,
        "rendered": False,
        "geometry_modified": False,
        "policy": {
            "gt_used": False,
            "roles_inferred_from_names": False,
            "bounds_are_colliders": False,
            "hidden_geometry_included": True,
            "missing_triangles_certify_clearance": False,
            "source_object_geometry_complete": True,
            "component_enclosure_candidates_included": True,
            "region_complete_means_exhaustive_selection_only": True,
        },
        "summary": {
            "source_meshes_inspected": inspected,
            "relevant_evaluated_triangles": total_scene_triangles,
            "full_object_triangles_exported": total,
            "source_objects_exported": len(meshes),
            "regions": len(regions),
            "incomplete_regions": sum(not region["selection_complete"] for region in regions),
        },
        "excluded_annotation_object_ids": sorted(excluded),
        "meshes": meshes,
        "regions": regions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, separators=(",", ":"), allow_nan=False) + "\n")
    print(json.dumps({"output": str(args.output), **document["summary"]}))


if __name__ == "__main__":
    main()
