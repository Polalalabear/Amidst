#!/usr/bin/env python3
"""Aggregate immutable per-camera render-policy v0.1.1 diagnostics."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--camera-root",
        type=Path,
        default=ROOT / "data/reports/render_diagnostics/school_v1_render_policy_v0_1_1_r2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/reports/school_v1_render_policy_v0_1_1_camera_statistics_raw.json",
    )
    return parser.parse_args()


def quantile(values: list[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(values: list[float]) -> dict[str, float]:
    return {
        "minimum": min(values),
        "p10": quantile(values, 0.10),
        "p25": quantile(values, 0.25),
        "median": quantile(values, 0.50),
        "p75": quantile(values, 0.75),
        "p90": quantile(values, 0.90),
        "maximum": max(values),
    }


def metric(records: list[dict[str, Any]], *keys: str) -> list[float]:
    values = []
    for record in records:
        value: Any = record
        for key in keys:
            value = value[key]
        values.append(float(value))
    return values


def main() -> None:
    options = args()
    output = options.output.resolve()
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite raw aggregate: {output}")
    record_paths = sorted(options.camera_root.glob("camera_*/statistics.json"))
    records = [json.loads(path.read_text(encoding="utf-8")) for path in record_paths]
    ids = [record["camera_instance_id"] for record in records]
    if len(records) != 29 or len(set(ids)) != 29:
        raise RuntimeError(f"Expected 29 unique camera records, found {len(records)}")
    if not all(record.get("render_success") is True for record in records):
        raise RuntimeError("One or more camera renders failed")
    if not all(
        record.get("derived_scene_checksum_unchanged") is True
        and record.get("scene_invariants_unchanged_after_runtime_cleanup") is True
        for record in records
    ):
        raise RuntimeError("One or more per-camera processes changed scene state")

    occupancy_order = sorted(
        records,
        key=lambda record: record["composition"][
            "largest_single_object_occupancy_ratio"
        ],
    )
    repeat_selection = [
        occupancy_order[0]["camera_instance_id"],
        occupancy_order[len(occupancy_order) // 2]["camera_instance_id"],
        occupancy_order[-1]["camera_instance_id"],
    ]
    distributions = {
        "mean_luminance": distribution(metric(records, "luminance", "mean_luminance")),
        "median_luminance": distribution(metric(records, "luminance", "median_luminance")),
        "p1_luminance": distribution(metric(records, "luminance", "p1_luminance")),
        "p99_luminance": distribution(metric(records, "luminance", "p99_luminance")),
        "p99_minus_p1_luminance": distribution(
            metric(records, "luminance", "p99_minus_p1_luminance")
        ),
        "near_black_fraction": distribution(
            metric(records, "luminance", "near_black_fraction")
        ),
        "near_white_or_clipped_fraction": distribution(
            metric(records, "luminance", "near_white_or_clipped_fraction")
        ),
        "largest_single_object_occupancy_ratio": distribution(
            metric(records, "composition", "largest_single_object_occupancy_ratio")
        ),
        "valid_visible_stable_id_object_count": distribution(
            metric(records, "composition", "valid_visible_stable_id_object_count")
        ),
        "valid_scene_geometry_fraction": distribution(
            metric(records, "composition", "valid_scene_geometry_fraction")
        ),
    }
    report = {
        "schema_name": "amidst.render_policy_camera_statistics_raw",
        "schema_version": "0.1.1",
        "status": "STATISTICS_COLLECTED_THRESHOLD_PROPOSAL_PENDING",
        "repository_classification": "REVIEW_REQUIRED",
        "path_base": "repository_root",
        "aggregated_at_utc": datetime.now(timezone.utc).isoformat(),
        "render_policy_id": "amidst.school.texture-agnostic-render/0.1.1",
        "render_config_id": "amidst.school.first-slice-render/0.1.1",
        "eligible_camera_count": 29,
        "render_success_count": 29,
        "render_failure_count": 0,
        "camera_ids": sorted(ids),
        "per_camera": sorted(records, key=lambda record: record["camera_instance_id"]),
        "distributions": distributions,
        "determinism_repeat_selection": {
            "method": "minimum, median, and maximum largest-single-object occupancy",
            "camera_ids": repeat_selection,
        },
        "dataset_frames_created": False,
        "dataset_pilot_created": False,
        "gt_contract_changed": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": report["status"], "repeat_selection": repeat_selection}))


if __name__ == "__main__":
    main()
