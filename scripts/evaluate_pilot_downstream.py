"""Evaluate an already completed pilot inference; GT never selects a route.

Metric semantics are the existing configured metrics. Their *_m field names are
retained in raw domain output, while this report explicitly labels native Blender
units because physical scale and mesh collision authority are unverified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext
from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory
from amidst.domain.metric_config import MetricConfig
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import BoundGapEvent, ObservationAggregation
from amidst.evaluation.configured import evaluate_configured_trajectories

INFERENCE_FILES = (
    "projected_frames.json", "aggregation.json", "pipeline_config.json", "gap_events.json",
    "candidates.json", "events.json", "topology_evidence.json", "inference_report.json",
)


def artifact_digests(root: Path) -> dict[str, str]:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in INFERENCE_FILES}


def load_labeled(path: Path) -> dict:
    value = json.loads(path.read_text())
    if value.get("label") != PILOT_LABEL:
        raise ValueError("downstream outputs must be labeled PILOT / SYNTHETIC SAMPLE")
    return value


def load_evaluation_truth(
    path: Path, context: PilotInferenceContext, aggregation: ObservationAggregation,
) -> GroundTruthTrajectory:
    """Evaluation-only conversion of the existing flat Blender GT export."""
    truth = load_labeled(path)
    if (
        truth.get("provenance") != "GROUND_TRUTH"
        or truth.get("source_asset_sha256") != context.source_asset_sha256
        or truth.get("site_id") != context.site_id
    ):
        raise ValueError("evaluation GT source/site/provenance differs from inference")
    rows = truth["samples"]
    sample_times = [float(row["timestamp"]) for row in rows]
    observed_times = sorted({float(sample.timestamp) for sample in aggregation.samples})
    if sample_times != observed_times or len(rows) < 2:
        raise ValueError("evaluation GT must cover exactly the original ordered pilot timestamps")
    trajectory_id = truth["trajectory_id"]
    if any(
        row["trajectory_id"] != trajectory_id or row["floor_id"] != context.zone.floor_id
        for row in rows
    ):
        raise ValueError("evaluation GT trajectory/floor binding differs")
    rate = 1.0 / (sample_times[1] - sample_times[0])
    if not math.isclose(rate, round(rate), rel_tol=0, abs_tol=1e-9):
        raise ValueError("bounded pilot evaluation requires an integer sampling rate")
    samples = []
    for index, row in enumerate(rows):
        first = rows[index] if index < len(rows) - 1 else rows[index - 1]
        second = rows[index + 1] if index < len(rows) - 1 else row
        delta = second["timestamp"] - first["timestamp"]
        velocity = tuple((b - a) / delta for a, b in zip(
            first["position"], second["position"], strict=True,
        ))
        samples.append(GroundTruthSample(
            timestamp=row["timestamp"], position=row["position"], velocity=velocity,
            floor_id=row["floor_id"],
        ))
    targets = {sample.target_id for sample in aggregation.samples}
    if len(targets) != 1:
        raise ValueError("bounded evaluation requires one observed target")
    return GroundTruthTrajectory(
        trajectory_id=trajectory_id, target_id=next(iter(targets)),
        scene_id=context.spatial_context_id, random_seed=20261005,
        sample_rate_hz=round(rate), sample_source="BLENDER_EVALUATED",
        source_asset_sha256=context.source_asset_sha256, samples=tuple(samples),
    )


def evaluate_saved_pilot(
    root: Path, truth_path: Path, context_path: Path, *, coverage_epsilon: float = 0.02,
) -> dict:
    if (root / "metrics.json").exists():
        raise FileExistsError(root / "metrics.json")
    # Load/freeze completed inference artifacts before opening any truth file.
    before = artifact_digests(root)
    context = PilotInferenceContext.model_validate_json(context_path.read_bytes())
    aggregation = ObservationAggregation.model_validate(
        load_labeled(root / "aggregation.json")["aggregation"],
    )
    pipeline = PipelineConfig.model_validate(
        load_labeled(root / "pipeline_config.json")["pipeline"],
    )
    gaps = tuple(BoundGapEvent.model_validate(row) for row in
                 load_labeled(root / "gap_events.json")["gaps"])
    if len(gaps) != 1 or not gaps[0].event.trajectories:
        raise ValueError("this bounded pilot evaluation requires one reconstructed gap")
    if any(sample.binding != context.binding for sample in aggregation.samples):
        raise ValueError("evaluation aggregation source/context differs")
    gap = gaps[0]
    if gap.binding != context.binding or pipeline.navigation.source_asset_sha256 != (
        context.source_asset_sha256
    ):
        raise ValueError("evaluation gap/navigation must preserve source binding")
    order_before = [row.candidate_id for row in gap.event.candidates]
    # First GT access occurs here, after the immutable search/event outputs exist.
    full_truth = load_evaluation_truth(truth_path, context, aggregation)
    start, end = gap.event.time_range
    gap_samples = tuple(sample for sample in full_truth.samples if start <= sample.timestamp <= end)
    gap_truth = GroundTruthTrajectory.model_validate({
        **full_truth.model_dump(mode="python"), "samples": gap_samples,
    })
    metric_config = MetricConfig(
        metric_config_version="pilot-diagnostic-metrics-v1", k_values=(1, 2, 3),
        coverage_epsilon_m=coverage_epsilon,
    )
    metrics = evaluate_configured_trajectories(
        gap.event.trajectories, gap_truth, metric_config,
        constraints=ConstraintConfig(
            max_speed_m_s=pipeline.movement.max_speed_m_s,
            navigation_graph=pipeline.navigation, obstacles=(),
        ),
    )
    summaries = []
    for result in metrics.evaluations:
        first = result.trajectory_metrics[0]
        summaries.append({
            "k": result.config.k_routes,
            "ade_first_primary_scene_units": first.ade_m,
            "fde_first_primary_scene_units": first.fde_m,
            "min_ade_at_k_scene_units": result.min_ade_at_k_m,
            "min_fde_at_k_scene_units": result.min_fde_at_k_m,
            "coverage_at_k": result.coverage_at_k,
            "selected_route_count": result.selected_route_count,
            "selected_hypothesis_ids": list(result.top_k_hypothesis_ids),
        })
    after = artifact_digests(root)
    if before != after or order_before != [row.candidate_id for row in gap.event.candidates]:
        raise RuntimeError("evaluation changed the frozen inference outputs or candidate order")
    report = {
        "label": PILOT_LABEL, "scope": "PILOT_EVALUATION_ONLY_NOT_FORMAL_CASES_1_3",
        "trajectory_id": full_truth.trajectory_id,
        "coordinate_units": "BLENDER_SCENE_UNITS", "physical_scale_authority": "UNVERIFIED",
        "metric_domain_field_units": "*_m fields represent native scene units at declared scale 1",
        "gap_time_range": list(gap.event.time_range), "gap_gt_sample_count": len(gap_samples),
        "full_gt_sample_count": len(full_truth.samples),
        "coverage_epsilon_scene_units": coverage_epsilon,
        "coverage_comparison": "STRICTLY_LESS_THAN_ADE",
        "top_k_policy": metric_config.top_k_policy,
        "gt_loaded_only_after_completed_inference": True,
        "inference_artifacts_unchanged_after_evaluation": before == after,
        "inference_artifact_sha256": before,
        "ground_truth_sha256": hashlib.sha256(truth_path.read_bytes()).hexdigest(),
        "physical_validity": {
            "status": "PARTIAL_PROVISIONAL", "mesh_collision_certified": False,
            "wall_authority_complete": False, "supplied_obstacle_count": 0,
            "blender_mesh_collision_rate": None,
            "assessment": "Only configured graph corridor/speed; no actual mesh collision check.",
            "empty_obstacle_zero_rates_are_not_physical_clearance_proof": True,
        },
        "summaries": summaries, "configured_evaluation": metrics.model_dump(mode="json"),
    }
    (root / "metrics.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    overlay = {
        "label": PILOT_LABEL, "purpose": "EVALUATION_DEBUG_ONLY",
        "source_asset_sha256": context.source_asset_sha256,
        "target_id": full_truth.target_id, "trajectory_id": full_truth.trajectory_id,
        "samples": [{"timestamp": sample.timestamp, "position": list(sample.position),
                     "floor_id": sample.floor_id} for sample in full_truth.samples],
    }
    (root / "evaluation_gt.json").write_text(json.dumps(overlay, indent=2, allow_nan=False) + "\n")
    (root / "evaluation_gap_gt.json").write_text(json.dumps({
        "label": PILOT_LABEL, "purpose": "EVALUATION_ONLY",
        "ground_truth": gap_truth.model_dump(mode="json"),
    }, indent=2, allow_nan=False) + "\n")
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — downstream evaluation", "",
        "GT is loaded only after completed inference; candidate order is preserved.",
        "Units: native Blender scene units. Physical scale and WALL authority unverified.",
        f"Gap: {start}–{end}s; {len(gap_samples)} GT timestamps including visible endpoints.",
        f"Coverage: ADE < {coverage_epsilon} scene units; provisional diagnostic threshold.", "",
        "| K | ADE first primary | FDE first primary | minADE@K | minFDE@K | Coverage@K |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for summary in summaries:
        lines.append(
            f"| {summary['k']} | {summary['ade_first_primary_scene_units']:.8g} | "
            f"{summary['fde_first_primary_scene_units']:.8g} | "
            f"{summary['min_ade_at_k_scene_units']:.8g} | "
            f"{summary['min_fde_at_k_scene_units']:.8g} | {summary['coverage_at_k']} |"
        )
    lines += ["", "Collision/physical validity: PARTIAL / PROVISIONAL. No mesh obstacle test;",
              "empty supplied-obstacle zero rates are not clearance evidence.",
              "No GT ranking, dataset expansion or formal Case 1–3 execution.", ""]
    (root / "metrics.md").write_text("\n".join(lines))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--coverage-epsilon-scene-units", type=float, default=0.02)
    args = parser.parse_args()
    report = evaluate_saved_pilot(
        args.run, args.ground_truth, args.context,
        coverage_epsilon=args.coverage_epsilon_scene_units,
    )
    print(json.dumps({"label": PILOT_LABEL, "metrics": report["summaries"]}))


if __name__ == "__main__":
    main()
