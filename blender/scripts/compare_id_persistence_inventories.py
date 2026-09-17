#!/usr/bin/env python3
"""Compare pre/post Blender inspections for instance_id-only persistence."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


EXCLUDED_CAMERA = "skp_camera_Last_Saved_SketchUp_View"
EXPECTED_AUTHORIZED_CHANGES = 2777


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-inventory", required=True, type=Path)
    parser.add_argument("--post-inventory", required=True, type=Path)
    parser.add_argument("--pre-validation", required=True, type=Path)
    parser.add_argument("--post-validation", required=True, type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def load_inventory(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        name = row["object_name"]
        if name in result:
            raise ValueError(f"Duplicate inventory object name: {name}")
        result[name] = row
    return result


def normalized_custom_properties(value: str) -> tuple[dict[str, Any], Any]:
    properties = json.loads(value)
    instance_id = properties.pop("instance_id", None)
    return properties, instance_id


def sanitized_validation(report: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(json.dumps(report))
    for key in (
        "inspected_at_utc",
        "source_file",
        "source_path",
        "source_sha256",
        "inventory_file",
    ):
        result.pop(key, None)
    checks = result.get("checks", {})
    checks.pop("missing_instance_id", None)
    normalized_semantic = []
    for record in checks.get("semantic_custom_properties", []):
        record.get("properties", {}).pop("instance_id", None)
        if record.get("properties"):
            normalized_semantic.append(record)
    checks["semantic_custom_properties"] = normalized_semantic
    for camera in checks.get("existing_cameras", []):
        camera.pop("instance_id", None)
        camera.get("custom_properties", {}).pop("instance_id", None)
    result.get("summary", {}).pop("missing_instance_id_count", None)
    result.get("summary", {})["semantic_metadata_object_count"] = len(normalized_semantic)
    return result


def main() -> None:
    args = arguments()
    registry = load_json(args.registry)
    expected = {record["object_name"]: record["instance_id"] for record in registry["records"]}
    if len(expected) != EXPECTED_AUTHORIZED_CHANGES:
        raise ValueError("Registry does not contain 2777 unique object locators")

    before = load_inventory(args.pre_inventory)
    after = load_inventory(args.post_inventory)
    differences: list[dict[str, Any]] = []
    authorized: list[dict[str, str]] = []
    if set(before) != set(after):
        differences.append(
            {
                "kind": "object_name_set_changed",
                "removed": sorted(set(before) - set(after)),
                "added": sorted(set(after) - set(before)),
            }
        )

    for name in sorted(set(before) & set(after)):
        left = before[name]
        right = after[name]
        for field in left:
            if field in {"custom_properties", "instance_id"}:
                continue
            if left[field] != right[field]:
                differences.append(
                    {
                        "kind": "inventory_field_changed",
                        "object_name": name,
                        "field": field,
                        "before": left[field],
                        "after": right[field],
                    }
                )
        left_props, left_prop_id = normalized_custom_properties(left["custom_properties"])
        right_props, right_prop_id = normalized_custom_properties(right["custom_properties"])
        if left_props != right_props:
            differences.append(
                {
                    "kind": "non_instance_custom_property_changed",
                    "object_name": name,
                    "before": left_props,
                    "after": right_props,
                }
            )
        expected_id = expected.get(name)
        if expected_id is None:
            if right["instance_id"] or right_prop_id is not None:
                differences.append(
                    {"kind": "excluded_or_unregistered_object_received_id", "object_name": name}
                )
            continue
        if left["instance_id"] or left_prop_id is not None:
            differences.append(
                {"kind": "pre_write_instance_id_already_present", "object_name": name}
            )
        if right["instance_id"] != expected_id or right_prop_id != expected_id:
            differences.append(
                {
                    "kind": "post_write_instance_id_mismatch",
                    "object_name": name,
                    "expected": expected_id,
                    "csv_instance_id": right["instance_id"],
                    "custom_property_instance_id": right_prop_id,
                }
            )
        else:
            authorized.append({"object_name": name, "instance_id": expected_id})

    if EXCLUDED_CAMERA not in after:
        differences.append({"kind": "excluded_camera_missing", "object_name": EXCLUDED_CAMERA})
    pre_validation = sanitized_validation(load_json(args.pre_validation))
    post_validation = sanitized_validation(load_json(args.post_validation))
    if pre_validation != post_validation:
        differences.append(
            {
                "kind": "sanitized_validation_changed",
                "before": pre_validation,
                "after": post_validation,
            }
        )

    report = {
        "schema_name": "amidst.instance_id_scene_comparison",
        "schema_version": "1.0.0",
        "repository_classification": "REVIEW_REQUIRED",
        "status": (
            "PASS"
            if not differences and len(authorized) == EXPECTED_AUTHORIZED_CHANGES
            else "REVIEW_REQUIRED"
        ),
        "pre_inventory": str(args.pre_inventory.resolve()),
        "post_inventory": str(args.post_inventory.resolve()),
        "pre_validation": str(args.pre_validation.resolve()),
        "post_validation": str(args.post_validation.resolve()),
        "registry": str(args.registry.resolve()),
        "object_count_before": len(before),
        "object_count_after": len(after),
        "authorized_change": "add approved instance_id object custom property",
        "authorized_instance_id_change_count": len(authorized),
        "unauthorized_scene_change_count": len(differences),
        "unauthorized_scene_differences": differences,
        "excluded_object": EXCLUDED_CAMERA,
        "excluded_object_has_no_id": (
            EXCLUDED_CAMERA in after
            and not after[EXCLUDED_CAMERA]["instance_id"]
            and normalized_custom_properties(after[EXCLUDED_CAMERA]["custom_properties"])[1]
            is None
        ),
        "compared_inventory_fields": [
            field
            for field in next(iter(before.values()))
            if field not in {"custom_properties", "instance_id"}
        ],
        "validation_comparison": "exact_after_removing_path_hash_timestamp_and_instance_id_fields",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "authorized": len(authorized), "unauthorized": len(differences)}, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
