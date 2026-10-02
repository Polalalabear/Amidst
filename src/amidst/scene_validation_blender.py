"""Blender-process extraction for semantic diagnostics: no save, render, or role inference."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

KINDS = ("AREA", "WALKABLE", "WALL", "OBSTACLE", "STAIR", "PORTAL", "CAM")


def _kind(name: str) -> str | None:
    return next((kind for kind in KINDS if name.startswith(kind + "_")), None)


def _serializable(value: Any) -> Any:
    if isinstance(value, (str, bool, int)) or value is None:
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "to_list"):
        value = value.to_list()
    if isinstance(value, (list, tuple)):
        return [_serializable(v) for v in value]
    return {"unsupported_property_type": type(value).__name__}


def _properties(owner: Any) -> dict[str, Any]:
    return {key: _serializable(owner[key]) for key in owner.keys() if key != "_RNA_UI"}


def main() -> None:
    bpy = importlib.import_module("bpy")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--max-triangles", type=int, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    source = Path(bpy.data.filepath)
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != args.source_sha256:
        raise ValueError("opened source differs from requested Blender file")
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    rows = []
    for obj in sorted(bpy.data.objects, key=lambda item: item.name):
        props = _properties(obj)
        collection_classes = [_kind(c.name) for c in obj.users_collection]
        collection_classes += [_properties(c).get("semantic_class") for c in obj.users_collection]
        if not (
            _kind(obj.name)
            or props.get("semantic_class") in KINDS
            or any(kind in KINDS for kind in collection_classes)
        ):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        matrix = evaluated.matrix_world
        match = re.search(r"(?:^|_)(\d+F|B\d+)(?:_|$)", obj.name)
        row: dict[str, Any] = {
            "object": obj.name,
            "object_type": obj.type,
            "collections": sorted(c.name for c in obj.users_collection),
            "custom_properties": props,
            "declared_floor_label": match.group(1) if match else None,
            "matrix_world": [[float(v) if math.isfinite(v) else None for v in r] for r in matrix],
            "scale": [float(v) if math.isfinite(v) else None for v in obj.scale],
            "hide_viewport": bool(obj.hide_viewport),
            "hide_render": bool(obj.hide_render),
            "hidden": bool(obj.hide_get()),
            "in_active_scene": obj.name in scene.objects,
            "collection_disabled": any(
                c.hide_viewport or c.hide_render for c in obj.users_collection
            ),
            "physical_role_approved": False,
        }
        if obj.type == "MESH":
            mesh = evaluated.to_mesh()
            try:
                mesh.calc_loop_triangles()
                world = [list(matrix @ vertex.co) for vertex in mesh.vertices]
                row["mesh_statistics"] = {
                    "evaluated_vertices": len(world),
                    "evaluated_polygons": len(mesh.polygons),
                    "evaluated_triangles": len(mesh.loop_triangles),
                }
                row["geometry_status"] = (
                    "EMPTY_EVALUATED_MESH" if not world else "EVALUATED_MESH_UNREVIEWED"
                )
                finite = all(math.isfinite(v) for point in world for v in point)
                if not finite:
                    row["nonfinite_geometry"] = True
                triangles = [list(t.vertices) for t in mesh.loop_triangles]
                if len(triangles) <= args.max_triangles:
                    row["vertices"] = [
                        [float(v) if math.isfinite(v) else None for v in p] for p in world
                    ]
                    row["triangles"] = triangles
                else:
                    row["representation_unsupported"] = "MESH_COMPLEXITY_BUDGET_EXCEEDED"
                incidence: Counter[tuple[int, int]] = Counter()
                for polygon in mesh.polygons:
                    vertices = list(polygon.vertices)
                    incidence.update(
                        tuple(sorted((a, b)))
                        for a, b in zip(vertices, vertices[1:] + vertices[:1], strict=False)
                    )
                row["non_manifold_edges"] = sum(
                    incidence[tuple(sorted(edge.vertices))] != 2 for edge in mesh.edges
                )
                if finite:
                    # Fingerprint world coordinates and topology, never only bounds.
                    row["geometry_sha256"] = hashlib.sha256(
                        json.dumps(
                            {"vertices": world, "triangles": triangles},
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ).hexdigest()
                    surface_area = 0.0
                    for face in triangles:
                        a, b, c = [world[i] for i in face]
                        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
                        cross = [
                            u[1] * v[2] - u[2] * v[1],
                            u[2] * v[0] - u[0] * v[2],
                            u[0] * v[1] - u[1] * v[0],
                        ]
                        surface_area += math.sqrt(sum(q * q for q in cross)) / 2
                    row["surface_area_units2"] = surface_area
            finally:
                evaluated.to_mesh_clear()
        else:
            world = [list(matrix.translation)]
            row["geometry_status"] = "OBJECT_ORIGIN_NOT_SURFACE_GEOMETRY"
        if world and all(math.isfinite(v) for p in world for v in p):
            row["bounding_box"] = {
                "minimum": [min(p[i] for p in world) for i in range(3)],
                "maximum": [max(p[i] for p in world) for i in range(3)],
            }
            row["centroid"] = [math.fsum(p[i] for p in world) / len(world) for i in range(3)]
        rows.append(row)
    report = {
        "schema_version": "scene-validation-snapshot-v1",
        "source_sha256": digest,
        "benchmark_type": "SCENE_DIAGNOSTIC",
        "blender_version": bpy.app.version_string,
        "scene": {
            "name": scene.name,
            "frame": scene.frame_current,
            "subframe": scene.frame_subframe,
        },
        "inventory_counts": {"all_objects": len(bpy.data.objects), "semantic_objects": len(rows)},
        "objects": rows,
        "collections": [
            {
                "collection": c.name,
                "custom_properties": _properties(c),
                "hide_viewport": bool(c.hide_viewport),
                "hide_render": bool(c.hide_render),
            }
            for c in sorted(bpy.data.collections, key=lambda item: item.name)
        ],
        "endpoints": [],
    }
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
