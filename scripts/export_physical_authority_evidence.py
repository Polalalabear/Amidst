"""Read-only source mesh context for floor, stair and obstacle authority review.

Selection boxes only limit export; they never become colliders or certify empty space.
Unclassified geometry retains its source identity without semantic-role inference.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def content_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def bounds(vertices: Any) -> dict[str, list[float]]:
    return {
        "minimum": [min(p[i] for p in vertices) for i in range(3)],
        "maximum": [max(p[i] for p in vertices) for i in range(3)],
    }


def regions(audit: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in audit["objects"]:
        props = row["custom_properties"]
        role = props.get("semantic_class")
        if role not in {"WALKABLE", "OBSTACLE"}:
            continue
        floor = props["floor_id"]
        box = bounds(row["vertices"])
        band = (
            config["floor_stair_review"]["floor_support_bands"]
            if role == "WALKABLE"
            else config["obstacle_support_bands"]
        )[floor]
        box["minimum"][2], box["maximum"][2] = band
        result.append(
            {
                "region_id": row["object"],
                "floor_id": floor,
                "kind": "FLOOR_SUPPORT" if role == "WALKABLE" else "OBSTACLE_CONTEXT",
                "bounds": box,
                "complete": True,
                "unresolved_reasons": [],
                "patches": [],
            }
        )
    for identity, box in config["stair_context_regions"].items():
        result.append(
            {
                "region_id": identity,
                "floor_id": None,
                "kind": "STAIR_CONTEXT",
                "bounds": box,
                "complete": True,
                "unresolved_reasons": [],
                "patches": [],
            }
        )
    return sorted(result, key=lambda row: (row["kind"], row["region_id"]))


def main() -> None:
    bpy = importlib.import_module("bpy")
    np = importlib.import_module("numpy")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    if args.output.exists():
        raise FileExistsError("physical evidence output exists; use a fresh output path")
    audit, config = json.loads(args.audit.read_text()), json.loads(args.config.read_text())
    source = Path(bpy.data.filepath).resolve()
    before, source_hash = source.stat(), digest(source)
    if source_hash != args.expected_source_sha256 or any(
        value != source_hash for value in (audit["source_sha256"], config["source_sha256"])
    ):
        raise ValueError("physical evidence source SHA-256 mismatch")
    scene = bpy.context.scene
    if audit["scene"] != {
        "name": scene.name,
        "frame": scene.frame_current,
        "subframe": scene.frame_subframe,
    }:
        raise ValueError("physical evidence evaluated context differs from semantic audit")
    review = config["floor_stair_review"]
    per_region = review["max_triangles_per_region"]
    maximum = config["maximum_total_triangles"]
    threshold = review["horizontal_normal_abs_z_min"]
    if (
        any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in (per_region, maximum)
        )
        or not 0 < threshold <= 1
    ):
        raise ValueError("invalid physical evidence selection policy")
    selected = regions(audit, config)
    counts = {row["region_id"]: 0 for row in selected}
    total = 0
    # Explicit semantic/ref/helper objects are excluded as physical support evidence.
    excluded = {row["object"] for row in audit["objects"]}
    depsgraph = bpy.context.evaluated_depsgraph_get()
    inspected, evaluated_triangles = 0, 0
    for obj in sorted(scene.objects, key=lambda item: item.name):
        if obj.type != "MESH" or obj.name in excluded or obj.get("phase1_annotation_only", False):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            inspected += 1
            if not mesh.vertices or not mesh.polygons:
                continue
            coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float64)
            mesh.vertices.foreach_get("co", coordinates)
            matrix = np.asarray(evaluated.matrix_world, dtype=np.float64)
            world = coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
            if not bool(np.isfinite(world).all()):
                raise ValueError(f"non-finite source mesh: {obj.name}")
            lo, hi = world.min(axis=0), world.max(axis=0)
            relevant = [
                row
                for row in selected
                if bool(
                    (hi >= np.asarray(row["bounds"]["minimum"])).all()
                    and (lo <= np.asarray(row["bounds"]["maximum"])).all()
                )
            ]
            if not relevant:
                continue
            mesh.calc_loop_triangles()
            indices = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int32)
            mesh.loop_triangles.foreach_get("vertices", indices)
            triangles = indices.reshape(-1, 3)
            evaluated_triangles += len(triangles)
            points = world[triangles]
            triangle_min, triangle_max = points.min(axis=1), points.max(axis=1)
            cross = np.cross(points[:, 1] - points[:, 0], points[:, 2] - points[:, 0])
            lengths = np.linalg.norm(cross, axis=1)
            normal_z = np.divide(
                abs(cross[:, 2]), lengths, out=np.zeros_like(lengths), where=lengths > 0
            )
            face_indices = np.empty(len(mesh.loop_triangles), dtype=np.int32)
            mesh.loop_triangles.foreach_get("polygon_index", face_indices)
            for region in relevant:
                box = region["bounds"]
                mask = (
                    (triangle_max >= np.asarray(box["minimum"])).all(axis=1)
                    & (triangle_min <= np.asarray(box["maximum"])).all(axis=1)
                    & (lengths > 1e-9)
                )
                if region["kind"] == "FLOOR_SUPPORT":
                    mask &= normal_z >= threshold
                wanted = np.flatnonzero(mask)
                if not len(wanted):
                    continue
                if (
                    counts[region["region_id"]] + len(wanted) > per_region
                    or total + len(wanted) > maximum
                ):
                    region["complete"] = False
                    region["unresolved_reasons"].append(
                        f"EXPORT_TRIANGLE_BUDGET_EXCEEDED:{obj.name}"
                    )
                    continue
                originals = sorted(set(int(i) for tri in triangles[wanted] for i in tri))
                remap = {index: offset for offset, index in enumerate(originals)}
                patch = {
                    "source_object_id": obj.name,
                    "source_face_indices": sorted(set(int(i) for i in face_indices[wanted])),
                    "vertices": world[originals].tolist(),
                    "triangles": [[remap[int(i)] for i in tri] for tri in triangles[wanted]],
                    "triangle_source_face_indices": face_indices[wanted].tolist(),
                    "source_triangle_indices": wanted.tolist(),
                    "hidden_render": bool(obj.hide_render),
                    "hidden_viewport": bool(obj.hide_get()),
                    "semantic_role": "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY",
                }
                patch["geometry_sha256"] = content_digest(patch)
                region["patches"].append(patch)
                counts[region["region_id"]] += len(wanted)
                total += len(wanted)
        finally:
            evaluated.to_mesh_clear()
    after = source.stat()
    if (before.st_size, before.st_mtime_ns, source_hash) != (
        after.st_size,
        after.st_mtime_ns,
        digest(source),
    ):
        raise RuntimeError("source changed during read-only physical evidence export")
    for region in selected:
        region["triangle_count"] = counts[region["region_id"]]
        region["unresolved_reasons"] = sorted(set(region["unresolved_reasons"]))
    payload = {
        "schema_version": "physical-source-mesh-evidence-v1",
        "source_sha256": source_hash,
        "source_size": before.st_size,
        "source_mtime_ns": before.st_mtime_ns,
        "audit_content_sha256": content_digest(audit),
        "config_content_sha256": content_digest(config),
        "blender_version": bpy.app.version_string,
        "evaluated_scene": audit["scene"],
        "source_preserved": True,
        "saved": False,
        "rendered": False,
        "policy": {
            "gt_used": False,
            "roles_inferred_from_names": False,
            "region_complete_is_selection_complete_only": True,
            "missing_triangles_certify_clearance": False,
        },
        "summary": {
            "source_meshes_inspected": inspected,
            "evaluated_triangles_in_relevant_meshes": evaluated_triangles,
            "exported_triangles": total,
            "regions": len(selected),
        },
        "regions": selected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False) + "\n")
    print(
        json.dumps(
            {
                **payload["summary"],
                "source_preserved": True,
                "incomplete_regions": sum(not row["complete"] for row in selected),
            }
        )
    )


if __name__ == "__main__":
    main()
