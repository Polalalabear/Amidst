"""Audit existing pilot runs, repeated inference, GT poison and visualization.

This reads completed outputs only; it does not generate trajectories, run a
benchmark or promote provisional annotations to physical authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

LABEL = "PILOT / SYNTHETIC SAMPLE"
INFERENCE_FILES = (
    "projected_frames.json", "aggregation.json", "pipeline_config.json", "gap_events.json",
    "candidates.json", "events.json", "topology_evidence.json", "inference_report.json",
    "inference_report.md", "digests.json",
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_pilot(root: Path, pilot: Path) -> dict:
    baseline, repeated, poison = (root / name for name in ("run_01", "run_02", "poison_run"))
    if (root / "verification.json").exists():
        raise FileExistsError(root / "verification.json")
    errors = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def labeled(path: Path) -> dict:
        payload = json.loads(path.read_text())
        check(payload.get("label") == LABEL, f"missing PILOT label: {path.name}")
        return payload

    hashes = {run.name: {name: digest(run / name) for name in INFERENCE_FILES}
              for run in (baseline, repeated, poison)}
    repeat_equal = hashes[baseline.name] == hashes[repeated.name]
    poison_equal = hashes[baseline.name] == hashes[poison.name]
    check(repeat_equal, "repeated inference artifacts differ")
    check(poison_equal, "GT-poison inference artifacts differ")
    context_equal = (root / "input/projection_context.json").read_bytes() == (
        root / "poison_input/projection_context.json"
    ).read_bytes()
    check(context_equal, "GT poison changed exported inference context")
    projected = labeled(baseline / "projected_frames.json")["dataset"]["samples"]
    aggregation = labeled(baseline / "aggregation.json")["aggregation"]
    gaps = labeled(baseline / "gap_events.json")["gaps"]
    inference = labeled(baseline / "inference_report.json")
    check(len(projected) == 100, "consumer did not preserve all 100 camera records")
    timestamps = sorted({row["timestamp"] for row in projected})
    check(len(timestamps) == 50, "consumer did not preserve all 50 timestamps")
    observed = [row for row in projected if row["visibility"] == "OBSERVED"]
    absent = [row for row in projected if row["visibility"] == "GAP"]
    check(len(observed) == 26 and len(absent) == 74, "unexpected camera evidence counts")
    check(all(row["projected_point"] is not None for row in observed), "visible projection missing")
    check(all(row["projected_point"] is None and row["uv"] is None for row in absent),
          "GAP contains hidden coordinates")
    check(len(aggregation["observations"]) == 2 and len(gaps) == 1,
          "expected one independently bounded gap")
    gap = gaps[0]
    event, search = gap["event"], gap["search_result"]
    check(event["time_range"] == [4.0, 9.0],
          "reconstruction window differs from observed endpoints")
    check(len(event["candidates"]) == 3 and len(event["trajectories"]) == 6,
          "expected three routes and six timing hypotheses")
    check(search["termination_reason"] == "COMPLETE" and search["complete"] is True,
          "search did not terminate with exhaustive COMPLETE")
    check(all(row["path_score"] is None for row in event["candidates"]), "unexpected route score")
    check(inference["ground_truth_read"] is False
          and inference["formal_benchmark_executed"] is False,
          "inference reports GT or benchmark access")
    global_gaps = [timestamp for timestamp in timestamps if not any(
        row["timestamp"] == timestamp for row in observed
    )]
    check(len(global_gaps) == 24 and global_gaps[0] == 4.2 and global_gaps[-1] == 8.8,
          "global visible/GAP/recovery partition differs")
    metrics = labeled(baseline / "metrics.json")
    changed_metrics = labeled(poison / "metrics.json")
    metrics_repeat_equal = (baseline / "metrics.json").read_bytes() == (
        repeated / "metrics.json"
    ).read_bytes()
    check(metrics_repeat_equal, "repeated evaluation differs")
    check(metrics["summaries"] != changed_metrics["summaries"], "GT poison did not change metrics")
    check(changed_metrics["summaries"][-1]["coverage_at_k"] is False,
          "poisoned GT unexpectedly has diagnostic coverage")
    check(metrics["gt_loaded_only_after_completed_inference"] is True,
          "evaluation did not preserve inference/GT ordering")
    check(metrics["inference_artifacts_unchanged_after_evaluation"] is True,
          "evaluation changed inference outputs")
    check(metrics["physical_validity"]["status"] == "PARTIAL_PROVISIONAL"
          and metrics["physical_validity"]["blender_mesh_collision_rate"] is None,
          "physical/collision validity was overstated")
    visualization = root / "run_01/visualization"
    vis = labeled(visualization / "visualization_manifest.json")
    check(vis["counts"] == {
        "candidates": 3, "hypotheses": 6, "projected_samples": 26, "gt_samples": 50,
    }, "visualization dropped observed/candidate/hypothesis/GT data")
    check(vis["inference_executed"] is False and vis["gt_overlay_enabled"] is True,
          "visualization must remain debug-only")
    for path, expected in vis["inputs"].items():
        check(digest(Path(path)) == expected, f"visualization input changed: {Path(path).name}")
    for name, expected in vis["outputs"].items():
        check(digest(visualization / name) == expected, f"visualization artifact changed: {name}")
    original = json.loads((pilot / "dataset.json").read_text())
    prior_audit = json.loads((pilot / "independent_frame_audit.json").read_text())
    context = labeled(root / "input/projection_context.json")
    check(digest(pilot / "dataset.json") == prior_audit["dataset_sha256"],
          "original dataset changed")
    check(digest(pilot / "trajectory_plan.json") == prior_audit["trajectory_plan_sha256"],
          "original simulation plan changed")
    check(digest(pilot / "observations.json") == context["observations_sha256"],
          "original 2D observations changed")
    check(digest(pilot / "ground_truth.json") == metrics["ground_truth_sha256"],
          "original GT changed")
    source = original["source_scene"]
    lineage = original["source_lineage"]
    for path, expected_digest, size, mtime in (
        (Path(source["path"]), source["sha256_before"], source["size_before"],
         source["mtime_ns_before"]),
        (Path(lineage["original_source_path"]), lineage["original_source_sha256"],
         lineage["original_source_size"], lineage["original_source_mtime_ns"]),
    ):
        stat = path.stat()
        check((digest(path), stat.st_size, stat.st_mtime_ns) == (expected_digest, size, mtime),
              f"original/derived Blender identity changed: {path.name}")
    report = {
        "label": LABEL, "status": "PASS_WITH_PROVISIONAL_PHYSICS" if not errors else "FAILED",
        "checkpoint_commit": "fdf9e7e8f2dc695917ba42094a63cc06ca910963",
        "trajectory_count": 1, "timestamp_count": 50, "camera_record_count": len(projected),
        "projected_visible_count": len(observed), "unprojected_gap_camera_count": len(absent),
        "global_gap_timestamps": global_gaps, "reconstruction_window": event["time_range"],
        "candidate_route_count": len(event["candidates"]),
        "timing_hypothesis_count": len(event["trajectories"]),
        "termination_reason": search["termination_reason"], "search_exhausted": search["complete"],
        "repeated_inference_byte_identical": repeat_equal,
        "gt_poison_inference_byte_identical": poison_equal,
        "gt_poison_context_byte_identical": context_equal,
        "repeated_metrics_byte_identical": metrics_repeat_equal,
        "gt_poison_metrics_change_only": poison_equal and metrics["summaries"] != (
            changed_metrics["summaries"]
        ),
        "inference_artifact_hashes_by_run": hashes,
        "metric_summaries": metrics["summaries"],
        "metric_units": "BLENDER_SCENE_UNITS_PHYSICAL_SCALE_UNVERIFIED",
        "coverage_epsilon_scene_units": metrics["coverage_epsilon_scene_units"],
        "physical_validity": metrics["physical_validity"],
        "visualization_manifest": vis,
        "original_pilot_and_blender_inputs_unchanged": not any(
            "original" in error or "Blender identity" in error for error in errors
        ),
        "formal_cases_1_3_executed": False, "dataset_expanded": False, "errors": errors,
    }
    (root / "verification.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    summary = metrics["summaries"][-1]
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — bounded downstream verification", "",
        f"Status: **{report['status']}**; one existing trajectory, no new dataset/render.",
        "Observation → inverse Projection → provisional Topology → Graph Top-K →",
        "reconstruction → evaluation → Rerun/3D presentation.", "",
        "- 100/100 camera records and 50/50 timestamps consumed; 26 projected / 74 null GAP.",
        "- Two visible Observations; 24 global GAP samples (4.2–8.8s).",
        "- Reconstruction window: 4.0–9.0s; 3 routes / 6 timing hypotheses; COMPLETE/exhaustive.",
        f"- Repeated inference: {repeat_equal}; GT-poison inference/context: "
        f"{poison_equal}/{context_equal}; repeated metrics: {metrics_repeat_equal}.",
        f"- ADE / FDE first primary: {summary['ade_first_primary_scene_units']:.8g} / "
        f"{summary['fde_first_primary_scene_units']:.8g} native scene units.",
        f"- minADE@3 / minFDE@3: {summary['min_ade_at_k_scene_units']:.8g} / "
        f"{summary['min_fde_at_k_scene_units']:.8g}; Coverage@3={summary['coverage_at_k']} "
        "at diagnostic ADE < 0.02 scene units.",
        "- Coverage/GT compatibility is evaluation-only; candidate order and alternatives remain.",
        "- Collision/physical validity PARTIAL/PROVISIONAL; mesh/scale remain uncertified.",
        "- Rerun retains all 3 routes / 6 hypotheses / 26 projected / 50 GT debug samples.",
        "- Browser file:// policy prevented HTML UI verification; static PNG/RRD were verified.",
        "- Original inputs unchanged; no formal Cases1–3 or benchmark semantic changes.",
        "", "[Metrics](run_01/metrics.md) · [Inference](run_01/inference_report.md) · "
        "[3D preview](run_01/visualization/preview_3d.png) · "
        "[Rerun](run_01/visualization/debug.rrd) · "
        "[Interactive HTML](run_01/visualization/review_3d.html)", "", "## Errors", "",
    ]
    lines += [f"- {error}" for error in errors] or ["- None."]
    (root / "verification.md").write_text("\n".join(lines) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    args = parser.parse_args()
    report = verify_pilot(args.root, args.pilot)
    print(f"{LABEL}: {report['status']}; {len(report['errors'])} errors")
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
