"""Apply a reviewed, source-bound annotation patch in Blender; never infer geometry roles.

Run with Blender --background --disable-autoexec --python this_file --
--plan patch.json --result update.json.
The plan is an explicit artifact, not an inference input. Architectural meshes and cameras
are checked for unintended changes, and the source is replaced only after a successful save.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def mesh_identity(obj: Any) -> str:
    if obj.type != "MESH":
        return "NON_MESH"
    data = obj.data
    value = {
        "vertices": [list(v.co) for v in data.vertices],
        "edges": [list(e.vertices) for e in data.edges],
        "polygons": [list(p.vertices) for p in data.polygons],
    }
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def set_properties(owner: Any, values: dict[str, Any]) -> None:
    for key, value in values.items():
        if isinstance(value, dict) or value is None:
            raise ValueError(f"patch properties must be scalar or flat arrays: {key}")
        owner[key] = value


def assign_collection(bpy: Any, obj: Any, name: str) -> None:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def main() -> None:
    bpy = importlib.import_module("bpy")
    matrix_type = importlib.import_module("mathutils").Matrix
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    plan = json.loads(args.plan.read_text())
    source = Path(bpy.data.filepath).resolve()
    if source != Path(plan["source_path"]).resolve() or digest(source) != plan["source_sha256"]:
        raise ValueError("patch source path/hash differs from the reviewed plan")
    if not plan.get("semantic_review_id") or plan.get("source_modification_authorized") is not True:
        raise ValueError("explicit source modification authorization is required")
    original_objects = list(bpy.data.objects)
    originals = {
        obj.as_pointer(): {
            "object": obj.name,
            "matrix": [list(row) for row in obj.matrix_world],
            "mesh": mesh_identity(obj),
            "camera": [obj.data.lens, obj.data.clip_start, obj.data.clip_end]
            if obj.type == "CAMERA"
            else None,
        }
        for obj in original_objects
    }
    # Preflight every action before changing even in-memory annotations.
    mesh_targets = {action["object"] for action in plan["mesh_updates"]}
    renamed = {action["object"] for action in plan["object_updates"] if action.get("rename")}
    for action in plan["object_updates"]:
        if action["object"] not in bpy.data.objects:
            raise ValueError(f"patch object is absent: {action['object']}")
        if action.get("rename") and action["rename"] in bpy.data.objects:
            raise ValueError(f"rename destination exists: {action['rename']}")
    for action in plan["mesh_updates"]:
        if not action.get("create") and action["object"] not in bpy.data.objects:
            raise ValueError(f"mesh target is absent: {action['object']}")
        if action.get("create") and action["object"] in bpy.data.objects:
            raise ValueError(f"new mesh destination exists: {action['object']}")
        vertices, faces = action["vertices"], action["faces"]
        if not vertices or not faces or not all(
            len(point) == 3 and all(math.isfinite(value) for value in point) for point in vertices
        ):
            raise ValueError(f"empty or non-finite mesh patch: {action['object']}")
        if not all(len(face) >= 3 and all(0 <= i < len(vertices) for i in face) for face in faces):
            raise ValueError(f"malformed face patch: {action['object']}")
    for action in plan["markers"]:
        if action["object"] in bpy.data.objects:
            raise ValueError(f"marker destination exists: {action['object']}")
    required_space = 2 * source.stat().st_size + 64 * 1024 * 1024
    if shutil.disk_usage(source.parent).free < required_space:
        raise OSError("insufficient space for verified backup and atomic staged scene save")
    backup_dir = Path(tempfile.mkdtemp(prefix="school-v3-original-", dir="/private/tmp"))
    backup = backup_dir / source.name
    try:
        shutil.copy2(source, backup)
    except OSError:
        # Only remove the incomplete backup created by this invocation, never user assets.
        if backup.exists():
            backup.unlink()
        backup_dir.rmdir()
        raise
    if digest(backup) != plan["source_sha256"]:
        raise RuntimeError("original asset backup verification failed")
    for action in plan["collection_updates"]:
        collection = bpy.data.collections[action["collection"]]
        if action.get("rename"):
            collection.name = action["rename"]
        set_properties(collection, action.get("properties", {}))
    transformed = set()
    for action in plan["object_updates"]:
        obj = bpy.data.objects[action["object"]]
        if action.get("translation"):
            delta = action["translation"]
            obj.location += importlib.import_module("mathutils").Vector(delta)
            transformed.add(action["object"])
        if action.get("rename"):
            obj.name = action["rename"]
        if action.get("collection"):
            assign_collection(bpy, obj, action["collection"])
        set_properties(obj, action.get("properties", {}))
    for action in plan["mesh_updates"]:
        obj = bpy.data.objects.get(action["object"])
        previous_materials = list(obj.data.materials) if obj else []
        mesh = bpy.data.meshes.new(action["object"] + "_SEMANTIC_SURFACE")
        mesh.from_pydata(action["vertices"], [], action["faces"])
        mesh.update()
        for material in previous_materials:
            mesh.materials.append(material)
        if obj is None:
            obj = bpy.data.objects.new(action["object"], mesh)
        else:
            obj.data = mesh
        obj.matrix_world = matrix_type.Identity(4)
        assign_collection(bpy, obj, action["collection"])
        set_properties(obj, action["properties"])
    for action in plan["markers"]:
        obj = bpy.data.objects.new(action["object"], None)
        obj.location = action["position"]
        obj.empty_display_type = "PLAIN_AXES"
        obj.empty_display_size = 5
        assign_collection(bpy, obj, action["collection"])
        set_properties(obj, action["properties"])
    bpy.context.view_layer.update()
    for obj in original_objects:
        original = originals[obj.as_pointer()]
        name = original["object"]
        if name not in mesh_targets and mesh_identity(obj) != original["mesh"]:
            raise RuntimeError(f"unintended architectural/reference mesh mutation: {name}")
        if (
            name not in mesh_targets | transformed
            and [list(row) for row in obj.matrix_world] != original["matrix"]
        ):
            raise RuntimeError(f"unintended transform mutation: {name}")
        if obj.type == "CAMERA" and original["camera"] != [
            obj.data.lens,
            obj.data.clip_start,
            obj.data.clip_end,
        ]:
            raise RuntimeError(f"unintended camera calibration mutation: {name}")
        if name not in renamed and obj.name != name:
            raise RuntimeError(f"unintended object rename: {name}")
    staged_dir = Path(tempfile.mkdtemp(prefix=".semantic-save-", dir=source.parent))
    staged = staged_dir / source.name
    try:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(
            filepath=str(staged), check_existing=False, relative_remap=False
        )
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError("Blender did not save the staged semantic scene")
        if digest(source) != plan["source_sha256"]:
            raise RuntimeError("source changed concurrently before atomic replacement")
        after_sha = digest(staged)
        os.replace(staged, source)
    finally:
        shutil.rmtree(staged_dir)
    result = {
        "source_sha256_before": plan["source_sha256"],
        "source_sha256_after": after_sha,
        "source_size_after": source.stat().st_size,
        "original_backup_path": str(backup),
        "original_backup_sha256_verified": True,
        "architectural_meshes_and_camera_calibration_unchanged": True,
        "only_planned_annotation_transforms_and_meshes_changed": True,
        "render_performed": False,
        "plan_sha256": digest(args.plan),
        "blender_version": bpy.app.version_string,
    }
    args.result.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
