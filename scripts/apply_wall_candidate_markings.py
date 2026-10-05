"""Save source-bound WALL face-selection annotations to an isolated derived scene.

Blender invocation: --background --disable-autoexec SOURCE --python this_file --
--candidates candidates.json --output blender/working/RUN/derived.blend --result result.json.
Then reopen the derived scene with the same arguments plus --verify. Exact existing
evaluated polygons are copied as hidden annotation meshes; source objects, portal
apertures and physical evaluated geometry remain unchanged. This does not approve
navigation geometry or run a benchmark, and it never saves the original asset.
"""

from __future__ import annotations

import argparse
import array
import copy
import hashlib
import importlib
import json
import math
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

LABEL = "PILOT / SYNTHETIC SAMPLE"
COLLECTION = "WALL_ANNOTATIONS"
ANNOTATION_CLASSES = {"AREA", "WALKABLE", "PORTAL", "OBSTACLE", "STAIR", "WALL"}
ANNOTATION_PREFIXES = ("AREA_", "WALK_", "WALKABLE_", "PORTAL_", "OBSTACLE_", "STAIR_", "WALL_")
ANNOTATION_COLLECTIONS = {
    "Areas",
    "WALKABLE_AREAS",
    "OBSTACLE_AREAS",
    "STAIR_ANNOTATIONS",
    "Stair Reference Surfaces",
    COLLECTION,
}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def json_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def snapshot_value(value: Any) -> Any:
    """Preserve inherited nonfinite camera settings as explicit identity tokens."""
    if isinstance(value, float) and not math.isfinite(value):
        return {"inherited_nonfinite_float": str(value)}
    if isinstance(value, dict):
        return {key: snapshot_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [snapshot_value(item) for item in value]
    return value


def extraction_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "wall_candidate_extraction", Path(__file__).with_name("extract_wall_candidates.py")
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("WALL extractor is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def annotation_name(row: dict[str, Any]) -> str:
    suffix = row["candidate_id"].removeprefix("WALL-PATCH-")
    if not suffix.isdigit() or row["floor"] not in {"1F", "2F"}:
        raise ValueError("invalid source-bound WALL candidate identity or floor")
    return f"WALL_{row['floor']}_PATCH_{suffix}"


def validate_document(document: dict[str, Any]) -> list[dict[str, Any]]:
    if document.get("schema_version") != "source-bound-wall-candidates-pilot-v1":
        raise ValueError("unsupported WALL candidate schema")
    if (
        document.get("label") != LABEL
        or document.get("authority") != "GEOMETRY_DERIVED_PATCH_SIDECAR"
    ):
        raise ValueError("candidate source authority/label is unsupported")
    if document["policy"].get("gt_used") or document["policy"].get("whole_objects_reclassified"):
        raise ValueError("candidate extraction violated geometry-only/patch-only policy")
    candidates = document["candidates"]
    ids = [row["candidate_id"] for row in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate candidate identities")
    confirmed = [row for row in candidates if row["status"] == "AUTO_CONFIRMED_WALL"]
    review = [row for row in candidates if row["status"] == "HUMAN_REVIEW"]
    summary = document["summary"]
    if (
        len(confirmed) != summary["auto_confirmed_wall_patches"]
        or len(review) != summary["human_review_patches"]
        or len(candidates) != len(confirmed) + len(review)
        or not confirmed
    ):
        raise ValueError("candidate status/count summary is inconsistent")
    for row in confirmed:
        annotation_name(row)
        if (
            row["semantic_class"] != "WALL"
            or row["protected_portal_conflicts"]
            or row["walkable_relation"]["interior_conflicts"]
            or row["material_review_flags"]
            or row["hidden_render"]
            or row["hidden_viewport"]
            or not row["evaluated_face_indices"]
            or row["annotation"]["evaluated_face_indices"] != row["evaluated_face_indices"]
            or row["annotation"]["create_or_fill_geometry"]
            or row["annotation"]["movement_collider_installed"]
        ):
            raise ValueError(f"unsafe confirmed WALL candidate: {row['candidate_id']}")
    for row in review:
        if row["annotation"]["evaluated_face_indices"]:
            raise ValueError("HUMAN_REVIEW geometry must not be marked")
    return confirmed


def same_value(left: Any, right: Any, tolerance: float = 1e-6) -> bool:
    if isinstance(left, float) or isinstance(right, float):
        return (
            isinstance(left, int | float)
            and isinstance(right, int | float)
            and math.isclose(left, right, rel_tol=1e-10, abs_tol=tolerance)
        )
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(same_value(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            same_value(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def verify_live_candidate(recorded: dict[str, Any], live: dict[str, Any]) -> None:
    # Re-run the same classifier, rather than treating the sidecar's status as proof.
    if not same_value(recorded, live):
        differing = sorted(k for k in recorded if not same_value(recorded[k], live.get(k)))
        raise ValueError(
            f"live candidate differs from source-bound extraction {recorded['candidate_id']}: "
            f"{differing}"
        )
    if live["status"] != "AUTO_CONFIRMED_WALL" or live["protected_portal_conflicts"]:
        raise ValueError("live WALL classification conflicts with a protected aperture")


def polygons_to_mesh(polygons: list[list[list[float]]]) -> tuple[list[Any], list[list[int]]]:
    """Copy real face vertices; never use bounds, convex hulls or rectangular infill."""
    vertices: list[Any] = []
    faces: list[list[int]] = []
    indices: dict[tuple[float, ...], int] = {}
    for polygon in polygons:
        if len(polygon) < 3 or not all(
            len(point) == 3 and all(math.isfinite(value) for value in point) for point in polygon
        ):
            raise ValueError("invalid evaluated WALL polygon")
        face = []
        for point in polygon:
            key = tuple(point)
            if key not in indices:
                indices[key] = len(vertices)
                vertices.append(list(point))
            face.append(indices[key])
        if len(set(face)) < 3:
            raise ValueError("degenerate evaluated WALL polygon")
        faces.append(face)
    if not faces:
        raise ValueError("WALL annotation cannot have empty geometry")
    return vertices, faces


def mesh_digest(mesh: Any) -> str:
    result = hashlib.sha256()
    for items, property_name, width, typecode in (
        (mesh.vertices, "co", 3, "f"),
        (mesh.edges, "vertices", 2, "i"),
        (mesh.loops, "vertex_index", 1, "i"),
        (mesh.polygons, "loop_start", 1, "i"),
        (mesh.polygons, "loop_total", 1, "i"),
    ):
        values = array.array(typecode, [0]) * (len(items) * width)
        items.foreach_get(property_name, values)
        result.update(f"{property_name}:{len(items)}:".encode())
        result.update(values.tobytes())
    return result.hexdigest()


def original_objects_snapshot(bpy: Any, names: list[str] | None = None) -> dict[str, str]:
    result = {}
    for name in names or sorted(obj.name for obj in bpy.data.objects):
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise ValueError(f"original source object disappeared: {name}")
        state: dict[str, Any] = {
            "type": obj.type,
            "matrix": [list(row) for row in obj.matrix_world],
            "collections": sorted(c.name for c in obj.users_collection),
            "hide_render": obj.hide_render,
            "hide_viewport": obj.hide_viewport,
            "hidden": obj.hide_get(),
            "modifiers": [(m.name, m.type, m.show_viewport, m.show_render) for m in obj.modifiers],
        }
        if obj.type == "MESH":
            state["mesh"] = mesh_digest(obj.data)
        if obj.type == "CAMERA":
            state["camera"] = {
                key: getattr(obj.data, key)
                for key in (
                    "type",
                    "lens",
                    "sensor_width",
                    "sensor_height",
                    "sensor_fit",
                    "shift_x",
                    "shift_y",
                    "clip_start",
                    "clip_end",
                    "ortho_scale",
                )
            }
        result[name] = json_digest(snapshot_value(state))
    return result


def is_annotation(obj: Any) -> bool:
    original = obj.original
    return bool(
        original.get("annotation_only")
        or original.get("semantic_class") in ANNOTATION_CLASSES
        or original.name.startswith(ANNOTATION_PREFIXES)
        or any(c.name in ANNOTATION_COLLECTIONS for c in original.users_collection)
    )


def physical_geometry_fingerprint(bpy: Any) -> dict[str, Any]:
    """Fingerprint evaluated physical instance geometry and transforms at the fixed frame."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    geometries: dict[tuple[int, int], str] = {}
    rows = []
    for instance in depsgraph.object_instances:
        obj = instance.object
        if (
            obj.type != "MESH"
            or not instance.show_self
            or not len(obj.data.polygons)
            or is_annotation(obj)
            or (instance.parent is not None and is_annotation(instance.parent))
        ):
            continue
        key = (obj.as_pointer(), obj.data.as_pointer())
        if key not in geometries:
            mesh = obj.to_mesh()
            try:
                geometries[key] = mesh_digest(mesh)
            finally:
                obj.to_mesh_clear()
        rows.append(
            {
                "source_object": obj.original.name,
                "geometry": geometries[key],
                "matrix": [list(row) for row in instance.matrix_world],
            }
        )
    rows.sort(key=lambda row: json.dumps(row, sort_keys=True))
    return {"sha256": json_digest(rows), "physical_mesh_instances": len(rows)}


def resolve_live_patches(bpy: Any, document: dict[str, Any]) -> dict[str, list[Any]]:
    extraction = extraction_module()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    semantic = extraction.semantics(bpy, depsgraph)
    confirmed = validate_document(document)
    object_names = sorted({row["object"] for row in confirmed})
    live_patches = []
    originals: dict[str, dict[str, Any]] = {}
    for name in object_names:
        obj = bpy.context.scene.objects.get(name)
        if obj is None or obj.type != "MESH" or is_annotation(obj):
            raise ValueError(f"candidate architectural source is absent or semantic: {name}")
        recorded = {
            tuple(row["evaluated_face_indices"]): row
            for row in document["candidates"]
            if row["object"] == name
        }
        patches = extraction.extract_patches(obj, depsgraph, document["parameters"])
        if len(patches) != len(recorded):
            raise ValueError(f"live candidate topology/count changed for {name}")
        for patch in patches:
            prior = recorded.get(tuple(patch["evaluated_face_indices"]))
            if prior is None:
                raise ValueError(f"source-bound evaluated face selection changed: {name}")
            patch["candidate_id"] = prior["candidate_id"]
            originals[prior["candidate_id"]] = prior
            live_patches.append(patch)
    polygons = {}
    for patch in live_patches:
        geometry = copy.deepcopy(patch["polygons"])
        extraction.classify(
            patch, live_patches, semantic, document["floor_planes"], document["parameters"]
        )
        if originals[patch["candidate_id"]]["status"] == "AUTO_CONFIRMED_WALL":
            verify_live_candidate(originals[patch["candidate_id"]], patch)
            polygons[patch["candidate_id"]] = geometry
    if len(polygons) != len(confirmed):
        raise ValueError("not every confirmed WALL patch has verified live geometry")
    return polygons


def annotation_properties(
    row: dict[str, Any], document: dict[str, Any], sidecar_sha: str
) -> dict[str, Any]:
    return {
        "semantic_class": "WALL",
        "floor_id": row["floor"],
        "annotation_only": True,
        "physical_role_approved": False,
        "movement_collider_installed": False,
        "semantic_status": "GEOMETRY_AUTO_CONFIRMED",
        "semantic_authority": "SOURCE_BOUND_EVALUATED_FACE_SELECTION",
        "sample_label": LABEL,
        "source_object": row["object"],
        "source_sha256": document["source"]["sha256"],
        "candidate_id": row["candidate_id"],
        "candidate_sidecar_sha256": sidecar_sha,
        "source_evaluated_frame": document["evaluated_scene"]["frame"],
        "source_evaluated_subframe": document["evaluated_scene"]["subframe"],
        "source_face_indices": row["evaluated_face_indices"],
        "nearby_area_json": json.dumps(row["nearby_area"], sort_keys=True),
        "nearby_portal_json": json.dumps(row["nearby_portal"], sort_keys=True),
        "judgment_reasons_json": json.dumps(row["reasons"]),
        "doorway_policy": "EXACT_EXISTING_FACE_COPY_NO_APERTURE_INFILL",
    }


def verify_annotation_apertures(bpy: Any, document: dict[str, Any]) -> dict[str, Any]:
    """Recheck stored annotation faces, including their Blender float precision."""
    extraction = extraction_module()
    semantic = extraction.semantics(bpy, bpy.context.evaluated_depsgraph_get())
    intersection_area = 0.0
    epsilon = document["parameters"]["weld_epsilon"] ** 2
    for row in validate_document(document):
        obj = bpy.data.objects[annotation_name(row)]
        world = [list(obj.matrix_world @ v.co) for v in obj.data.vertices]
        for polygon in obj.data.polygons:
            points = [world[i] for i in polygon.vertices]
            for portal in semantic["PORTAL"]:
                if portal["floor"] != row["floor"]:
                    continue
                area = extraction.polygon_area(
                    extraction.clip_polygon_box(
                        points, portal["bounds"], document["parameters"]["portal_padding"]
                    )
                )
                if area > epsilon:
                    raise ValueError(f"saved WALL polygon intersects portal: {portal['object']}")
                intersection_area += area
    return {
        "actual_annotation_portal_intersection_area": intersection_area,
        "protected_portals": len(semantic["PORTAL"]),
    }


def write_result(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — Phase 1 WALL semantic markings",
        "",
        "高信心 evaluated surface patches 已在獨立 derived scene 建立 `semantic_class=WALL`。",
        "僅複製既有實際面，不填 AABB／矩形／doorway；原 `group_*` objects 不重新分類。",
        "標記為 hidden annotation-only meshes，不加入 renderer、raycaster 或 movement collider。",
        "",
        f"- Source: `{result['source']['path']}` / `{result['source']['sha256']}`",
        f"- Derived: `{result['derived']['path']}` / `{result['derived']['sha256']}`",
        f"- Candidate sidecar SHA: `{result['candidate_sidecar_sha256']}`",
        f"- WALL: **{result['summary']['wall_markings']} patches**; "
        f"HUMAN_REVIEW: **{result['summary']['human_review_patches']} patches**",
        f"- Reopened saved scene verification: `{result['verification']['saved_scene_reopened']}`",
        "- Original raw meshes, transforms, cameras and evaluated physical instance "
        "geometry unchanged.",
        "- All protected PORTAL actual-face intersections: **0**.",
        "- Geometry-derived semantic marking does not certify navigation, metric scale "
        "or benchmark authority.",
        "- GT not used; no elevator transitions or Case 1–3 benchmark.",
        "",
        "| Marking | Source object | Floor | Bounds | Nearby AREA | Nearby PORTAL | Reasons |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in result["markings"]:
        lines.append(
            f"| {row['object']} | {row['source_object']} | {row['floor']} | "
            f"`{row['bounds']['minimum']}` → `{row['bounds']['maximum']}` | "
            f"{', '.join(row['nearby_area']) or 'NONE'} | "
            f"{', '.join(row['nearby_portal']) or 'NONE'} | {'; '.join(row['reasons'])} |"
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n")


def verify_saved(bpy: Any, document: dict[str, Any], args: Any) -> None:
    result = json.loads(args.result.read_text())
    if Path(bpy.data.filepath).resolve() != args.output.resolve():
        raise ValueError("verification must reopen the saved derived scene")
    if digest(args.output) != result["derived"]["sha256"]:
        raise ValueError("derived scene changed after annotation save")
    if digest(args.candidates) != result["candidate_sidecar_sha256"]:
        raise ValueError("candidate evidence changed after annotation save")
    source = Path(document["source"]["path"])
    if digest(source) != document["source"]["sha256"]:
        raise ValueError("immutable source changed after annotation save")
    scene = bpy.context.scene
    if (
        scene.frame_current != document["evaluated_scene"]["frame"]
        or scene.frame_subframe != document["evaluated_scene"]["subframe"]
    ):
        raise ValueError("derived evaluated frame changed")
    originals = result["original_object_fingerprints"]
    for key, expected in {
        "phase1_wall_marking_source_path": str(source.resolve()),
        "phase1_wall_marking_source_sha256": document["source"]["sha256"],
        "phase1_wall_marking_candidate_sidecar_sha256": result["candidate_sidecar_sha256"],
        "phase1_wall_marking_physical_geometry_sha256": result["physical_geometry"]["sha256"],
        "phase1_wall_marking_count": result["summary"]["wall_markings"],
    }.items():
        if scene.get(key) != expected:
            raise ValueError(f"saved scene lineage property changed: {key}")
    collection = bpy.data.collections.get(COLLECTION)
    if (
        collection is None
        or not collection.hide_render
        or collection.get("semantic_class") != "WALL"
        or collection.get("annotation_only") is not True
    ):
        raise ValueError("saved WALL collection annotation isolation changed")
    if original_objects_snapshot(bpy, list(originals)) != originals:
        raise ValueError("saved scene changed an original mesh, transform, camera or visibility")
    if physical_geometry_fingerprint(bpy) != result["physical_geometry"]:
        raise ValueError("saved scene changed evaluated physical instance geometry")
    names = set(originals) | {row["object"] for row in result["markings"]}
    if names != {obj.name for obj in bpy.data.objects}:
        raise ValueError("unexpected objects in saved derived scene")
    confirmed = {row["candidate_id"]: row for row in validate_document(document)}
    for row in result["markings"]:
        obj = bpy.data.objects.get(row["object"])
        if obj is None or obj.type != "MESH" or mesh_digest(obj.data) != row["mesh_sha256"]:
            raise ValueError("saved WALL marking mesh changed")
        props = annotation_properties(
            confirmed[row["candidate_id"]], document, digest(args.candidates)
        )
        for key, value in props.items():
            actual = obj.get(key)
            if hasattr(actual, "to_list"):
                actual = actual.to_list()
            if not same_value(actual, value):
                raise ValueError(f"saved WALL marking provenance changed: {key}")
        if (
            not obj.hide_render
            or not obj.hide_get()
            or obj.name not in bpy.data.collections[COLLECTION].objects
        ):
            raise ValueError("saved WALL annotation visibility/collection isolation changed")
    result["verification"].update(verify_annotation_apertures(bpy, document))
    result["verification"]["saved_scene_reopened"] = True
    result["verification"]["saved_marking_count"] = len(confirmed)
    result["verification"]["reopened_physical_geometry_sha256"] = result["physical_geometry"][
        "sha256"
    ]
    write_result(result, args.result)
    print("WALL_MARKINGS_REOPEN_VERIFIED", json.dumps(result["summary"]))


def main() -> None:
    bpy = importlib.import_module("bpy")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    document = json.loads(args.candidates.read_text())
    confirmed = validate_document(document)
    if args.verify:
        verify_saved(bpy, document, args)
        return
    source = Path(bpy.data.filepath).resolve()
    initial = source.stat()
    if (
        source != Path(document["source"]["path"]).resolve()
        or digest(source) != document["source"]["sha256"]
    ):
        raise ValueError("opened immutable source differs from candidate evidence")
    if args.output.resolve() == source or not args.output.resolve().is_relative_to(
        source.parent / "working"
    ):
        raise ValueError("derived output must be isolated under blender/working")
    if args.output.exists() or args.result.exists() or bpy.data.collections.get(COLLECTION):
        raise ValueError("derived output, result or WALL annotation collection already exists")
    scene = bpy.context.scene
    if scene.name != document["evaluated_scene"]["name"] or (
        scene.frame_current != document["evaluated_scene"]["frame"]
        or scene.frame_subframe != document["evaluated_scene"]["subframe"]
        or bpy.context.view_layer.name != document["evaluated_scene"]["view_layer"]
    ):
        raise ValueError("loaded evaluated scene/frame/view layer differs from extraction")
    original_objects = original_objects_snapshot(bpy)
    physical = physical_geometry_fingerprint(bpy)
    polygons = resolve_live_patches(bpy, document)
    sidecar_sha = digest(args.candidates)
    collection = bpy.data.collections.new(COLLECTION)
    scene.collection.children.link(collection)
    collection.hide_render = True
    collection["semantic_class"] = "WALL"
    collection["annotation_only"] = True
    collection["sample_label"] = LABEL
    markings = []
    for row in confirmed:
        name = annotation_name(row)
        if bpy.data.objects.get(name):
            raise ValueError(f"WALL annotation destination exists: {name}")
        vertices, faces = polygons_to_mesh(polygons[row["candidate_id"]])
        mesh = bpy.data.meshes.new(name + "_SOURCE_FACE_SELECTION")
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        collection.objects.link(obj)
        for key, value in annotation_properties(row, document, sidecar_sha).items():
            obj[key] = value
        obj.hide_render = True
        obj.hide_set(True)
        obj.display_type = "WIRE"
        markings.append(
            {
                "object": name,
                "candidate_id": row["candidate_id"],
                "source_object": row["object"],
                "floor": row["floor"],
                "bounds": row["bounds"],
                "nearby_area": [r["object"] for r in row["nearby_area"]],
                "nearby_portal": [r["object"] for r in row["nearby_portal"]],
                "reasons": row["reasons"],
                "mesh_sha256": mesh_digest(mesh),
                "source_evaluated_face_indices": row["evaluated_face_indices"],
                "unique_polygons": len(faces),
                "vertices": len(vertices),
                "geometry_selection_sha256": json_digest(polygons[row["candidate_id"]]),
            }
        )
    bpy.context.view_layer.update()
    aperture_verification = verify_annotation_apertures(bpy, document)
    if original_objects_snapshot(bpy, list(original_objects)) != original_objects:
        raise RuntimeError("an original source object changed while marking WALL patches")
    if physical_geometry_fingerprint(bpy) != physical:
        raise RuntimeError("WALL annotations changed evaluated physical instance geometry")
    for key, value in {
        "phase1_wall_marking_source_path": str(source),
        "phase1_wall_marking_source_sha256": document["source"]["sha256"],
        "phase1_wall_marking_candidate_sidecar_sha256": sidecar_sha,
        "phase1_wall_marking_physical_geometry_sha256": physical["sha256"],
        "phase1_wall_marking_count": len(markings),
    }.items():
        scene[key] = value
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Stage a new derived file; never replace either source or an existing output.
    with tempfile.TemporaryDirectory(
        prefix=".wall-derived-save-", dir=args.output.parent
    ) as temporary:
        staged = Path(temporary) / args.output.name
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(
            filepath=str(staged), check_existing=False, relative_remap=False
        )
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError("Blender did not save the isolated derived scene")
        if args.output.exists():
            raise RuntimeError("derived output appeared concurrently")
        os.link(staged, args.output)
    if (initial.st_size, initial.st_mtime_ns, document["source"]["sha256"]) != (
        source.stat().st_size,
        source.stat().st_mtime_ns,
        digest(source),
    ):
        raise RuntimeError("immutable source changed during derived save")
    result = {
        "schema_version": "source-bound-wall-semantic-markings-pilot-v1",
        "label": LABEL,
        "source": document["source"],
        "derived": {
            "path": str(args.output.resolve()),
            "sha256": digest(args.output),
            "size": args.output.stat().st_size,
        },
        "candidate_sidecar_path": str(args.candidates.resolve()),
        "candidate_sidecar_sha256": sidecar_sha,
        "physical_geometry": physical,
        "original_object_fingerprints": original_objects,
        "summary": {
            "wall_markings": len(markings),
            "human_review_patches": document["summary"]["human_review_patches"],
            "source_objects": len({row["source_object"] for row in markings}),
            "by_floor": dict(Counter(row["floor"] for row in markings)),
            "protected_portals": document["summary"]["protected_portals"],
            "portal_intersections": 0,
        },
        "verification": {
            "live_source_patches_reclassified": True,
            "original_objects_and_camera_calibration_unchanged": True,
            "evaluated_physical_geometry_unchanged": True,
            "source_hash_size_mtime_unchanged": True,
            "saved_scene_reopened": False,
            **aperture_verification,
        },
        "policy": {
            "annotation_only": True,
            "source_saved": False,
            "whole_objects_reclassified": False,
            "physical_role_approved": False,
            "movement_colliders_installed": False,
            "portal_aperture_infill": False,
            "gt_used": False,
            "benchmark_run": False,
            "elevator_transition_created": False,
        },
        "markings": markings,
    }
    write_result(result, args.result)
    print("WALL_MARKINGS_SAVED", json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
