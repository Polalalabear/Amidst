#!/usr/bin/env python3
"""Export a read-only CSV inventory and JSON validation report from Blender."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

import bpy

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

from validate_scene import collect_validation, custom_properties


CSV_FIELDS = (
    "object_name",
    "object_type",
    "collection",
    "collections",
    "parent",
    "parent_type",
    "parent_bone",
    "location",
    "rotation_mode",
    "rotation_euler_radians",
    "rotation_quaternion",
    "scale",
    "dimensions",
    "material_names",
    "custom_properties",
    "instance_id",
)


def _arguments() -> argparse.Namespace:
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--scene-id", default="school")
    parser.add_argument("--scene-version", default="v1")
    parser.add_argument("--expected-source", type=Path)
    return parser.parse_args(arguments)


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _assert_safe_output(path: Path, source_path: Path) -> None:
    resolved = path.resolve()
    if resolved == source_path or source_path.parent in resolved.parents:
        raise ValueError(f"Refusing to write inspection output under source directory: {resolved}")


def _material_names(obj: Any) -> list[str]:
    return [slot.material.name for slot in obj.material_slots if slot.material is not None]


def _inventory_row(obj: Any) -> dict[str, Any]:
    collections = sorted(collection.name for collection in obj.users_collection)
    instance_id = obj.get("instance_id")
    return {
        "object_name": obj.name,
        "object_type": obj.type,
        "collection": collections[0] if collections else "",
        "collections": _json_cell(collections),
        "parent": obj.parent.name if obj.parent else "",
        "parent_type": obj.parent_type if obj.parent else "",
        "parent_bone": obj.parent_bone if obj.parent and obj.parent_type == "BONE" else "",
        "location": _json_cell(list(obj.location)),
        "rotation_mode": obj.rotation_mode,
        "rotation_euler_radians": _json_cell(list(obj.rotation_euler)),
        "rotation_quaternion": _json_cell(list(obj.rotation_quaternion)),
        "scale": _json_cell(list(obj.scale)),
        "dimensions": _json_cell(list(obj.dimensions)),
        "material_names": _json_cell(_material_names(obj)),
        "custom_properties": _json_cell(custom_properties(obj)),
        "instance_id": instance_id if isinstance(instance_id, str) else "",
    }


def main() -> None:
    args = _arguments()
    if not bpy.data.filepath:
        raise RuntimeError("No saved .blend scene is currently open")

    source_path = Path(bpy.data.filepath).resolve()
    if args.expected_source and source_path != args.expected_source.resolve():
        raise RuntimeError(
            f"Loaded scene {source_path} does not match expected source "
            f"{args.expected_source.resolve()}"
        )
    _assert_safe_output(args.inventory, source_path)
    _assert_safe_output(args.report, source_path)

    source_stat_before = source_path.stat()
    report = collect_validation(args.scene_id, args.scene_version)
    objects = sorted(bpy.context.scene.objects, key=lambda obj: obj.name)

    args.inventory.parent.mkdir(parents=True, exist_ok=True)
    with args.inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(_inventory_row(obj) for obj in objects)

    source_stat_after = source_path.stat()
    if (
        source_stat_before.st_size != source_stat_after.st_size
        or source_stat_before.st_mtime_ns != source_stat_after.st_mtime_ns
    ):
        raise RuntimeError("Source scene size or modification time changed during inspection")

    report["inventory_file"] = str(args.inventory.resolve())
    report["inventory_columns"] = list(CSV_FIELDS)
    report["source_unchanged_during_inspection"] = True
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "inventory": str(args.inventory),
                "report": str(args.report),
                "object_count": len(objects),
                **report["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
