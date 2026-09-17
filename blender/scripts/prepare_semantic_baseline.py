#!/usr/bin/env python3
"""Prepare the confirmed category-agnostic first-slice semantic baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TASKS = (
    "visible_objects",
    "nearest_object",
    "distance_to_object",
    "left_of",
    "right_of",
    "in_front_of",
    "behind",
)


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=REPOSITORY_ROOT / "data/annotations/instance_registry/school.json",
    )
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=(
            REPOSITORY_ROOT
            / "data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json"
        ),
    )
    parser.add_argument(
        "--coverage-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_semantic_coverage.json",
    )
    parser.add_argument(
        "--human-report",
        type=Path,
        default=REPOSITORY_ROOT / "data/reports/school_v1_semantic_baseline.md",
    )
    return parser.parse_args()


def canonical_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def main() -> None:
    args = arguments()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    if registry.get("schema_name") != "amidst.instance_registry":
        raise ValueError("Unexpected instance registry schema")
    if registry.get("policy_id") != "amidst.school.object-id/1.0.1":
        raise ValueError("Unexpected stable-ID policy")
    records = registry.get("records", [])
    if len(records) != 2777:
        raise ValueError("Expected 2777 stable-ID records")
    if len({record["instance_id"] for record in records}) != 2777:
        raise ValueError("Stable-ID registry contains duplicate IDs")

    trusted = [
        record
        for record in records
        if record.get("category") != "Unknown"
        or record.get("annotation_status") != "needs_review"
    ]
    if trusted:
        raise ValueError(
            "Registry contains non-default semantic values; a separate trust review is required"
        )

    renderable_task_types = {"MESH", "CURVE", "FONT"}
    renderable_type_count = sum(
        record.get("identity_signals", {}).get("object_type") in renderable_task_types
        for record in records
    )
    task_definitions = [
        {
            "task": task,
            "status": "CONFIRMED",
            "semantic_category_required": False,
            "entity_reference": "stable_instance_id",
            "ground_truth_authority": "Blender-derived geometry and camera state",
            "task_contract": "amidst.school.first-dataset-slice/0.1.0",
            "open_rule": None,
        }
        for task in TASKS
    ]
    sidecar = {
        "schema_name": "amidst.semantic_annotation_sidecar",
        "schema_version": "0.1.0",
        "repository_classification": "REVIEW_REQUIRED",
        "status": "CONFIRMED",
        "approval_basis": (
            "Explicit human instruction to finalize the first-dataset-slice "
            "contract on 2026-09-14."
        ),
        "scene_id": "school",
        "scene_version": "v1",
        "source_scene": "school_v1.blend",
        "source_scene_sha256": registry["source_sha256"],
        "identity_policy_id": registry["policy_id"],
        "instance_registry": "data/annotations/instance_registry/school.json",
        "instance_registry_schema_version": registry["schema_version"],
        "annotation_version": "school.v1.semantic/0.1.0",
        "annotation_authority": "human_reviewed_sidecar_only",
        "blender_custom_properties_written": False,
        "minimum_category_vocabulary": ["Unknown"],
        "vocabulary_rule": (
            "Add a named category only after trusted evidence and explicit human approval; "
            "do not infer category from geometry."
        ),
        "unreviewed_default": {
            "category": "Unknown",
            "annotation_status": "needs_review",
            "annotation_source": "no_trusted_semantic_evidence",
            "review_status": "NOT_REVIEWED",
        },
        "reviewed_annotation_record_required_fields": [
            "instance_id",
            "category",
            "annotation_status",
            "annotation_source",
            "annotation_version",
            "reviewer",
            "review_status",
        ],
        "reviewed_annotations": [],
        "task_definitions": task_definitions,
        "notes": [
            "No semantic category is assigned by this first-slice baseline.",
            "The seven confirmed tasks use stable IDs and Blender-derived geometry without named categories.",
            "Natural-language category questions remain outside this baseline until vocabulary and labels are approved.",
        ],
    }
    coverage = {
        "schema_name": "amidst.semantic_coverage_report",
        "schema_version": "0.1.0",
        "repository_classification": "REVIEW_REQUIRED",
        "status": "CONFIRMED",
        "scene_id": "school",
        "scene_version": "v1",
        "semantic_sidecar": str(args.sidecar.relative_to(REPOSITORY_ROOT)),
        "total_stable_id_objects": 2777,
        "reviewed_semantic_objects": 0,
        "unknown_objects": 2777,
        "categories_used": ["Unknown"],
        "stable_id_objects_with_task_renderable_type": renderable_type_count,
        "objects_requiring_named_semantic_category_for_confirmed_tasks": 0,
        "exact_per_frame_required_objects": (
            "derived at generation time from render-enabled state, camera visibility, "
            "and task target selection"
        ),
        "task_definitions": task_definitions,
        "first_slice_semantic_blockers": [],
        "deferred_human_review": [
            "approve any future named categories before category-based questions are introduced",
        ],
    }
    canonical_write(args.sidecar, sidecar)
    canonical_write(args.coverage_report, coverage)
    args.human_report.parent.mkdir(parents=True, exist_ok=True)
    args.human_report.write_text(
        "\n".join(
            [
                "# School v1 Minimum Semantic Baseline",
                "",
                "Status: `CONFIRMED`",
                "",
                "- Stable-ID objects: 2777",
                "- Reviewed semantic objects: 0",
                "- Unknown / needs-review objects: 2777",
                f"- Stable-ID objects with task-renderable type: {renderable_type_count}",
                "- Named semantic categories required by the confirmed first tasks: 0",
                "- Minimum vocabulary: `Unknown`",
                "- Blender semantic custom properties written: 0",
                "",
                "The seven confirmed tasks use stable IDs and Blender-derived geometry. "
                "Named semantic categories remain outside the first-slice contract.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": coverage["status"],
                "stable_id_objects": 2777,
                "reviewed_semantic_objects": 0,
                "unknown_objects": 2777,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
