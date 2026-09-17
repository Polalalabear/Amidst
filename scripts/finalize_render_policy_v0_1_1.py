#!/usr/bin/env python3
"""Finalize the v0.1.1 sweep and repeat evidence without changing decisions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AGGREGATE = (
    ROOT / "data/reports/school_v1_render_policy_v0_1_1_camera_statistics_raw.json"
)
DEFAULT_REPEAT_ROOT = (
    ROOT
    / "data/reports/render_diagnostics/school_v1_render_policy_v0_1_1_r2/determinism_repeats"
)
DEFAULT_CONFIG = ROOT / "data/metadata/first_dataset_slice_render_config_v0_1_1.json"
DEFAULT_JSON_OUTPUT = (
    ROOT / "data/reports/school_v1_render_policy_v0_1_1_camera_statistics.json"
)
DEFAULT_MARKDOWN_OUTPUT = (
    ROOT / "data/reports/school_v1_render_policy_v0_1_1_diagnostic.md"
)
COMPOSITION_OCCUPANCY_PROPOSAL = 0.95
COMPOSITION_VISIBLE_OBJECT_PROPOSAL = 3


def arguments() -> argparse.Namespace:
    raw = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, default=DEFAULT_AGGREGATE)
    parser.add_argument("--repeat-root", type=Path, default=DEFAULT_REPEAT_ROOT)
    parser.add_argument("--render-config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    return parser.parse_args(raw)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def repository_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError(f"Evidence path must remain below the repository root: {path}") from error


def read_rgb(path: Path) -> Any:
    import numpy as np
    import OpenImageIO as oiio

    image = oiio.ImageInput.open(str(path))
    if image is None:
        raise RuntimeError(f"Cannot read diagnostic image: {path}")
    try:
        pixels = np.asarray(image.read_image(format=oiio.FLOAT))
    finally:
        image.close()
    if pixels.ndim != 3 or pixels.shape[2] < 3:
        raise RuntimeError(f"Unexpected diagnostic image shape: {pixels.shape}")
    return pixels[..., :3]


def composition_proposal(records: list[dict[str, Any]]) -> dict[str, Any]:
    flagged = []
    accepted = []
    for record in records:
        composition = record["composition"]
        occupancy = float(composition["largest_single_object_occupancy_ratio"])
        visible = int(composition["valid_visible_stable_id_object_count"])
        target = flagged if (
            occupancy >= COMPOSITION_OCCUPANCY_PROPOSAL
            or visible < COMPOSITION_VISIBLE_OBJECT_PROPOSAL
        ) else accepted
        target.append(record["camera_instance_id"])
    accepted_occupancies = [
        float(record["composition"]["largest_single_object_occupancy_ratio"])
        for record in records
        if record["camera_instance_id"] in accepted
    ]
    flagged_occupancies = [
        float(record["composition"]["largest_single_object_occupancy_ratio"])
        for record in records
        if record["camera_instance_id"] in flagged
    ]
    return {
        "status": "PROPOSED",
        "owner": "Peter",
        "decision_effect": "NONE_UNTIL_HUMAN_CONFIRMATION",
        "candidate_rule": {
            "largest_single_object_occupancy_ratio_must_be_less_than": (
                COMPOSITION_OCCUPANCY_PROPOSAL
            ),
            "valid_visible_stable_id_object_count_must_be_at_least": (
                COMPOSITION_VISIBLE_OBJECT_PROPOSAL
            ),
            "combination": "AND",
        },
        "basis": (
            "The observed distribution has a gap between the largest retained "
            "occupancy and the smallest flagged occupancy; both candidate clauses "
            "flag the same seven cameras in this sweep."
        ),
        "largest_retained_occupancy": max(accepted_occupancies),
        "smallest_flagged_occupancy": min(flagged_occupancies),
        "retained_camera_count": len(accepted),
        "flagged_camera_count": len(flagged),
        "flagged_camera_ids": sorted(flagged),
    }


def runtime_environment(config: dict[str, Any]) -> dict[str, Any]:
    import bpy

    build_hash = bpy.app.build_hash
    if isinstance(build_hash, bytes):
        build_hash = build_hash.decode("utf-8")
    configured = config["execution_environment"]
    return {
        "operating_system": platform.system(),
        "operating_system_release": platform.release(),
        "architecture": platform.machine(),
        "blender_version": bpy.app.version_string,
        "blender_build_hash": str(build_hash),
        "gpu_backend": configured["gpu_backend"],
        "reference_platform": configured["reference_platform"],
    }


def compare_repeat(primary: dict[str, Any], repeated: dict[str, Any]) -> dict[str, Any]:
    import numpy as np

    primary_path = ROOT / primary["render_path"]
    repeat_path = ROOT / repeated["render_path"]
    primary_pixels = read_rgb(primary_path)
    repeat_pixels = read_rgb(repeat_path)
    if primary_pixels.shape != repeat_pixels.shape:
        raise RuntimeError(f"Repeat image shape mismatch: {repeated['camera_instance_id']}")
    difference = np.abs(primary_pixels - repeat_pixels)
    different_pixels = int(np.count_nonzero(np.any(difference != 0, axis=2)))
    total_pixels = int(difference.shape[0] * difference.shape[1])
    checks = {
        "camera_selection_identical": (
            primary["camera_instance_id"] == repeated["camera_instance_id"]
        ),
        "render_policy_identical": (
            primary["render_policy_id"] == repeated["render_policy_id"]
        ),
        "render_config_identical": (
            primary["render_config_id"] == repeated["render_config_id"]
        ),
        "decoded_pixels_identical": (
            primary["decoded_pixel_sha256"] == repeated["decoded_pixel_sha256"]
        ),
        "luminance_metrics_identical": primary["luminance"] == repeated["luminance"],
        "composition_metrics_identical": (
            primary["composition"] == repeated["composition"]
        ),
        "repeat_scene_unchanged": (
            repeated["derived_scene_checksum_unchanged"]
            and repeated["scene_invariants_unchanged_after_runtime_cleanup"]
        ),
    }
    strict_pass = all(checks.values())
    return {
        "camera_instance_id": repeated["camera_instance_id"],
        "primary_record": primary["render_path"],
        "repeat_record": repeated["render_path"],
        "png_container_bytes_identical_not_required": (
            primary["png_sha256"] == repeated["png_sha256"]
        ),
        **checks,
        "different_pixel_count": different_pixels,
        "total_pixel_count": total_pixels,
        "different_pixel_fraction": different_pixels / total_pixels,
        "different_channel_value_count": int(np.count_nonzero(difference)),
        "maximum_absolute_channel_difference": float(np.max(difference)),
        "mean_absolute_channel_difference": float(np.mean(difference)),
        "strict_repeat_pass": strict_pass,
    }


def markdown(report: dict[str, Any]) -> str:
    comparison_lines = "\n".join(
        "| `{}` | {} | {} | {:.9f} |".format(
            record["camera_instance_id"],
            "PASS" if record["strict_repeat_pass"] else "FAIL",
            record["different_pixel_count"],
            record["maximum_absolute_channel_difference"],
        )
        for record in report["determinism_repeats"]
    )
    proposal = report["composition_threshold_proposal"]
    return f"""# Render Policy v0.1.1 Diagnostic Review

Status: `{report['status']}`

Repository classification: `REVIEW_REQUIRED`

## Evidence outcome

- Camera sweep: {report['sweep']['render_success_count']}/{report['sweep']['eligible_camera_count']} successful.
- Fresh-process repeat comparisons: {report['repeat_summary']['strict_pass_count']}/3 strict decoded-pixel passes.
- Confirmed decoded-pixel identity requirement: **not satisfied**.
- Dataset frames created: no.
- Ground Truth contract changed: no.

| Camera | Strict repeat | Different pixels | Maximum channel difference |
| --- | --- | ---: | ---: |
{comparison_lines}

PNG container-byte identity is not required. The failed repeats differ by decoded
pixel values, so they remain failures even though luminance and composition
metrics are unchanged.

## Composition threshold proposal

Status: `PROPOSED`; it has no decision effect until Peter confirms it.

- Require largest-single-object occupancy below {COMPOSITION_OCCUPANCY_PROPOSAL}.
- Require at least {COMPOSITION_VISIBLE_OBJECT_PROPOSAL} visible stable-ID objects.
- The proposal flags {proposal['flagged_camera_count']} cameras and retains {proposal['retained_camera_count']}.
- Observed gap: {proposal['largest_retained_occupancy']:.9f} to {proposal['smallest_flagged_occupancy']:.9f}.

## Required decision

Do not authorize another dataset pilot. Decide whether to change the confirmed
decoded-pixel identity requirement, change the render policy, or reject the
current policy. Cross-environment acceptance remains `OPEN` under OQ-016.
"""


def main() -> int:
    options = arguments()
    aggregate = load_json(options.aggregate.resolve())
    config = load_json(options.render_config.resolve())
    primary_records = aggregate.get("per_camera", [])
    selected = aggregate["determinism_repeat_selection"]["camera_ids"]
    if len(primary_records) != 29 or len(selected) != 3:
        raise ValueError("Expected a complete 29-camera aggregate and three selections")
    primary_by_id = {record["camera_instance_id"]: record for record in primary_records}
    repeat_paths = sorted(options.repeat_root.resolve().glob("*_repeat_statistics.json"))
    repeats = [load_json(path) for path in repeat_paths]
    repeat_by_id = {record["camera_instance_id"]: record for record in repeats}
    if len(repeats) != 3 or set(repeat_by_id) != set(selected):
        raise ValueError("Repeat records do not match the aggregate selection")
    comparisons = [compare_repeat(primary_by_id[camera_id], repeat_by_id[camera_id]) for camera_id in selected]
    strict_pass_count = sum(record["strict_repeat_pass"] for record in comparisons)
    decoded_identity_required = bool(
        config["diagnostic_policy"]["decoded_pixel_identity_required"]
    )
    strict_determinism_pass = strict_pass_count == 3
    report = {
        "schema_name": "amidst.render_policy_diagnostic_review",
        "schema_version": "0.1.1",
        "status": (
            "DIAGNOSTIC_COMPLETE"
            if strict_determinism_pass
            else "DIAGNOSTIC_COMPLETE_DETERMINISM_FAILED"
        ),
        "repository_classification": "REVIEW_REQUIRED",
        "path_base": "repository_root",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_environment": runtime_environment(config),
        "raw_aggregate": repository_path(options.aggregate),
        "render_config": repository_path(options.render_config),
        "sweep": {
            "eligible_camera_count": aggregate["eligible_camera_count"],
            "render_success_count": aggregate["render_success_count"],
            "render_failure_count": aggregate["render_failure_count"],
            "unique_camera_count": len(primary_by_id),
            "scene_unchanged_for_all_records": all(
                record["derived_scene_checksum_unchanged"]
                and record["scene_invariants_unchanged_after_runtime_cleanup"]
                for record in primary_records
            ),
        },
        "confirmed_determinism_contract": {
            "png_byte_identity_required": bool(
                config["diagnostic_policy"]["png_byte_identity_required"]
            ),
            "decoded_pixel_identity_required": decoded_identity_required,
        },
        "determinism_repeats": comparisons,
        "repeat_summary": {
            "repeat_count": len(comparisons),
            "strict_pass_count": strict_pass_count,
            "strict_failure_count": len(comparisons) - strict_pass_count,
            "strict_determinism_pass": strict_determinism_pass,
        },
        "composition_threshold_proposal": composition_proposal(primary_records),
        "cross_environment_acceptance_status": "OPEN",
        "dataset_generation_authorized": False,
        "dataset_frames_created": False,
        "dataset_pilot_created": False,
        "gt_contract_changed": False,
        "required_human_decision": (
            "Keep or change the confirmed decoded-pixel identity requirement, "
            "and accept, revise, or reject the proposed composition thresholds."
        ),
    }
    json_output = options.json_output.resolve()
    markdown_output = options.markdown_output.resolve()
    for path in (json_output, markdown_output):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite final diagnostic evidence: {path}")
        repository_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_output.write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "render_success_count": report["sweep"]["render_success_count"],
                "strict_repeat_pass_count": strict_pass_count,
                "strict_repeat_failure_count": len(comparisons) - strict_pass_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
