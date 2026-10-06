"""Read-only Blender adapter exporting exact source-bound candidate face triangles.

Blender --background --factory-startup --disable-autoexec SOURCE --python-exit-code 2
--python this_file -- --candidates candidates.json --output fresh_snapshot.json.
No source save, render, collider extrusion, whole-object relabeling or GT input occurs.
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


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def geometry_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def main() -> None:
    bpy = importlib.import_module("bpy")
    np = importlib.import_module("numpy")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists():
        raise FileExistsError("geometry snapshot output exists; use a fresh output path")
    document = json.loads(args.candidates.read_text())
    audit = json.loads(args.audit.read_text())
    if document.get("schema_version") != "source-bound-wall-candidates-pilot-v1":
        raise ValueError("unsupported source-bound candidate document")
    if document["policy"]["gt_used"] or document["policy"]["whole_objects_reclassified"]:
        raise ValueError("candidate policy violates geometry-only, patch-only extraction")
    source = Path(bpy.data.filepath).resolve()
    before = source.stat()
    source_hash = digest(source)
    if source_hash != document["source"]["sha256"]:
        raise ValueError("opened scene does not match candidate source SHA-256")
    if audit.get("source_sha256") != source_hash:
        raise ValueError("semantic audit does not match the opened source")
    context = document["evaluated_scene"]
    if audit.get("scene") != {key: context[key] for key in ("name", "frame", "subframe")}:
        raise ValueError("semantic audit evaluated context differs from candidate extraction")
    scene = bpy.context.scene
    if (
        scene.name != context["name"]
        or scene.frame_current != context["frame"]
        or scene.frame_subframe != context["subframe"]
        or bpy.context.view_layer.name != context["view_layer"]
    ):
        raise ValueError("evaluated scene/frame/view-layer differs from candidate extraction")
    candidates = document["candidates"]
    by_object: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        by_object.setdefault(row["object"], []).append(row)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    result: dict[str, dict[str, Any]] = {}
    for name, patches in sorted(by_object.items()):
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise ValueError(f"candidate source mesh is unavailable: {name}")
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", coordinates)
            matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
            world = coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
            triangles_by_face: dict[int, list[list[int]]] = {}
            wanted = {index for row in patches for index in row["evaluated_face_indices"]}
            for triangle in mesh.loop_triangles:
                if triangle.polygon_index in wanted:
                    triangles_by_face.setdefault(triangle.polygon_index, []).append(
                        list(triangle.vertices)
                    )
            for row in patches:
                indices = row["evaluated_face_indices"]
                if len(mesh.polygons) != row["evaluated_mesh_polygons"] or any(
                    index not in triangles_by_face for index in indices
                ):
                    raise ValueError(
                        f"evaluated source face identity mismatch: {row['candidate_id']}"
                    )
                originals = sorted(
                    {index for face in indices for tri in triangles_by_face[face] for index in tri}
                )
                remap = {index: offset for offset, index in enumerate(originals)}
                vertices = world[originals].tolist()
                triangles = [
                    [remap[index] for index in tri]
                    for face in indices
                    for tri in triangles_by_face[face]
                ]
                if not all(math.isfinite(value) for point in vertices for value in point):
                    raise ValueError("non-finite evaluated source geometry")
                actual_bounds = {
                    "minimum": [min(point[i] for point in vertices) for i in range(3)],
                    "maximum": [max(point[i] for point in vertices) for i in range(3)],
                }
                if any(
                    not math.isclose(
                        actual_bounds[key][i], row["bounds"][key][i], abs_tol=1e-7, rel_tol=1e-12
                    )
                    for key in ("minimum", "maximum")
                    for i in range(3)
                ):
                    raise ValueError(f"actual patch bounds changed: {row['candidate_id']}")
                value = {
                    "candidate_id": row["candidate_id"],
                    "source_object_id": name,
                    "source_face_indices": indices,
                    "vertices": vertices,
                    "triangles": triangles,
                }
                result[row["candidate_id"]] = {**value, "geometry_sha256": geometry_digest(value)}
        finally:
            evaluated.to_mesh_clear()
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, source_hash) != (
        after.st_size,
        after.st_mtime_ns,
        digest(source),
    ):
        raise RuntimeError("source changed during read-only geometry extraction")
    payload = {
        "schema_version": "geometry-evidence-snapshot-v1",
        "source_sha256": source_hash,
        "source_size": before.st_size,
        "source_mtime_ns": before.st_mtime_ns,
        "candidate_sha256": digest(args.candidates),
        "candidate_content_sha256": geometry_digest(document),
        "audit_sha256": digest(args.audit),
        "audit_content_sha256": geometry_digest(audit),
        "evaluated_scene": context,
        "blender_version": bpy.app.version_string,
        "source_preserved": True,
        "saved": False,
        "rendered": False,
        "patches": [result[row["candidate_id"]] for row in candidates],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                "snapshot": str(args.output),
                "patches": len(result),
                "triangles": sum(len(row["triangles"]) for row in result.values()),
                "source_preserved": True,
            }
        )
    )


if __name__ == "__main__":
    main()
