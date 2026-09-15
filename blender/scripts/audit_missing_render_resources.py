#!/usr/bin/env python3
"""Audit the five known missing render resources without modifying Blender data."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import bpy


SCRIPT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_DIR.parents[1]
TARGETS = (
    "__Brick-antique_.jpg",
    "__Brick-antique__1.jpg",
    "__Glass_Sky_Reflection_.jpg",
    "__Wood-cherry_1.jpg",
    "__Wood-cherry_1_0.jpg",
)


def script_args() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPOSITORY_ROOT / "data/annotations/instance_registry/school.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_missing_resource_audit.json",
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_missing_resource_audit.md",
    )
    return parser.parse_args(raw)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_nodes(node_tree: Any, image: Any, visited: set[int] | None = None) -> list[dict[str, str]]:
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
        nested = getattr(node, "node_tree", None)
        if nested is not None:
            uses.extend(image_nodes(nested, image, visited))
    return uses


def exact_repository_matches(filename: str) -> list[dict[str, str]]:
    matches: list[dict[str, str]] = []
    for path in REPOSITORY_ROOT.rglob(filename):
        if not path.is_file() or ".git" in path.parts:
            continue
        matches.append(
            {
                "path": str(path.resolve()),
                "sha256": file_sha256(path),
            }
        )
    return sorted(matches, key=lambda record: record["path"])


def main() -> None:
    args = script_args()
    scene_path = Path(bpy.data.filepath).resolve()
    if not scene_path.is_file():
        raise RuntimeError("No saved Blender scene is open")
    if (REPOSITORY_ROOT / "blender/source") in scene_path.parents:
        raise RuntimeError("Refusing to inspect the immutable source scene directly")
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    if registry.get("policy_id") != "amidst.school.object-id/1.0.1":
        raise RuntimeError("Unexpected stable-ID registry policy")
    expected_ids = {record["object_name"]: record["instance_id"] for record in registry["records"]}

    records: list[dict[str, Any]] = []
    for filename in TARGETS:
        matches = [image for image in bpy.data.images if image.name == filename]
        if len(matches) != 1:
            raise RuntimeError(f"Expected exactly one image datablock named {filename!r}")
        image = matches[0]
        packed = bool(image.packed_file) or bool(getattr(image, "packed_files", ()))
        raw_path = image.filepath
        resolved_path = Path(bpy.path.abspath(raw_path)).resolve()

        material_usage: list[dict[str, Any]] = []
        used_materials: set[Any] = set()
        for material in bpy.data.materials:
            nodes = image_nodes(material.node_tree, image)
            if nodes:
                used_materials.add(material)
                material_usage.append({"material": material.name, "nodes": nodes})
        material_usage.sort(key=lambda record: record["material"])

        render_objects: list[dict[str, Any]] = []
        for obj in sorted(bpy.context.scene.objects, key=lambda item: item.name):
            materials = {slot.material for slot in obj.material_slots if slot.material is not None}
            matching_materials = sorted(material.name for material in materials & used_materials)
            if not matching_materials or obj.hide_render:
                continue
            instance_id = obj.get("instance_id")
            if instance_id != expected_ids.get(obj.name):
                raise RuntimeError(f"Affected object stable-ID mismatch: {obj.name}")
            render_objects.append(
                {
                    "instance_id": instance_id,
                    "object_name_locator": obj.name,
                    "object_type": obj.type,
                    "materials": matching_materials,
                }
            )

        other_usage: list[dict[str, Any]] = []
        for datablocks, kind in (
            (bpy.data.worlds, "world"),
            (bpy.data.lights, "light"),
            (bpy.data.scenes, "scene_compositor"),
        ):
            for datablock in datablocks:
                nodes = image_nodes(getattr(datablock, "node_tree", None), image)
                if nodes:
                    other_usage.append(
                        {
                            "datablock_type": kind,
                            "datablock_name": datablock.name,
                            "nodes": nodes,
                        }
                    )

        repository_matches = exact_repository_matches(filename)
        exact_found = len(repository_matches) == 1
        records.append(
            {
                "filename": filename,
                "referenced_filepath": raw_path,
                "resolved_filepath": str(resolved_path),
                "exists_at_referenced_path": resolved_path.is_file(),
                "image_datablock": {
                    "name": image.name,
                    "source": image.source,
                    "users": image.users,
                    "packed": packed,
                },
                "material_node_usage": material_usage,
                "other_node_usage": other_usage,
                "render_enabled_object_count": len(render_objects),
                "render_enabled_objects": render_objects,
                "appears_to_affect_render_output": bool(render_objects or other_usage),
                "approved_search_roots": [str(REPOSITORY_ROOT)],
                "exact_repository_matches": repository_matches,
                "exact_original_asset_found": exact_found,
                "verified_asset_sha256": (
                    repository_matches[0]["sha256"] if exact_found else None
                ),
                "provenance": (
                    {
                        "kind": "exact_repository_filename_match",
                        "path": repository_matches[0]["path"],
                        "sha256": repository_matches[0]["sha256"],
                    }
                    if exact_found
                    else None
                ),
                "resolution_status": "PROPOSED_EXACT_MATCH" if exact_found else "REVIEW_REQUIRED",
                "blocks_render_generation": not exact_found,
                "replacement_approval": {
                    "status": "REVIEW_REQUIRED",
                    "original_expected_filename": filename,
                    "candidate_path": repository_matches[0]["path"] if exact_found else None,
                    "candidate_sha256": repository_matches[0]["sha256"] if exact_found else None,
                    "provenance_verified": exact_found,
                    "reviewer": None,
                    "review_decision": None,
                    "path_repair_authorized": False,
                    "notes": (
                        "No exact file was found in the approved repository/project search root. "
                        "Do not substitute a visually similar image."
                        if not exact_found
                        else "Exact-name match still requires human provenance and path-repair approval."
                    ),
                },
            }
        )

    unresolved = [record for record in records if record["blocks_render_generation"]]
    report = {
        "schema_name": "amidst.missing_render_resource_audit",
        "schema_version": "1.0.0",
        "repository_classification": "REVIEW_REQUIRED",
        "status": "REVIEW_REQUIRED" if unresolved else "PROPOSED_RESOLUTION_AVAILABLE",
        "inspected_at_utc": datetime.now(timezone.utc).isoformat(),
        "scene_id": "school",
        "scene_version": "v1",
        "inspected_scene": str(scene_path),
        "inspected_scene_sha256": file_sha256(scene_path),
        "immutable_source_scene": "blender/source/school_v1.blend",
        "immutable_source_sha256": registry["source_sha256"],
        "stable_id_policy": registry["policy_id"],
        "search_scope": {
            "roots": [str(REPOSITORY_ROOT)],
            "external_locations_searched": False,
            "visually_similar_substitution_allowed": False,
        },
        "resources": records,
        "summary": {
            "expected_missing_resources": len(TARGETS),
            "audited_resources": len(records),
            "exact_original_assets_found": len(records) - len(unresolved),
            "unresolved_resources": len(unresolved),
            "render_blockers_remaining": len(unresolved),
            "all_affect_render_output": all(
                record["appears_to_affect_render_output"] for record in records
            ),
            "resource_resolution_complete": not unresolved,
        },
        "scene_mutated": False,
        "path_repairs_applied": 0,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# School v1 Missing Render Resource Audit",
        "",
        f"Status: `{report['status']}`",
        "",
        "No Blender data or external-resource path was changed.",
        "",
        "| Resource | Packed | Material | Render objects | Exact asset found | Status |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for record in records:
        materials = ", ".join(item["material"] for item in record["material_node_usage"])
        lines.append(
            f"| `{record['filename']}` | {str(record['image_datablock']['packed']).lower()} "
            f"| `{materials}` | {record['render_enabled_object_count']} "
            f"| {str(record['exact_original_asset_found']).lower()} | `{record['resolution_status']}` |"
        )
    lines.extend(
        [
            "",
            "All five exact files are absent from the approved repository/project search root. "
            "Each remains a render blocker and requires an approved original asset or explicit replacement decision.",
            "",
        ]
    )
    args.human_report.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"status": report["status"], **report["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
