"""Reviewed orchestration with immutable inference and an explicit GT boundary.

The existing projector, graph and reconstruction implementations do the work.
This module coordinates authority, independently ready cases and persisted evidence;
it never selects routes, changes sampling or hides unavailable benchmark rows.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from amidst.datasets.pilot import PilotInferenceContext, PilotObservationExport
from amidst.domain.pipeline import InferenceInput
from amidst.domain.stream import AggregationPolicy
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256

METHODS = ("shortest_path", "geometry", "spatiotemporal")
ABLATIONS = ("remove_travel_time", "remove_collision", "remove_topology",
             "shortest_path_only", "full_deterministic_graph")
K_VALUES = (1, 2, 3)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("reviewed artifact must contain a JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def safe_artifact(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("manifest artifact escapes its dataset")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("manifest artifact escapes its dataset")
    return resolved


def verify_dataset(dataset: Path, *, inference_only: bool = True) -> dict[str, Any]:
    """Inference checks strict input bytes without opening simulation/evaluation."""
    manifest = read_json(dataset / "manifest.json")
    if manifest.get("schema_version") != "phase1-reviewed-dataset-v1":
        raise ValueError("fresh reviewed dataset manifest required")
    artifacts = manifest["artifacts"]
    for relative, expected in artifacts.items():
        path = safe_artifact(dataset, relative)
        if inference_only and Path(relative).parts[0] != "inference":
            continue
        if digest(path) != expected:
            raise ValueError("dataset artifact differs from frozen manifest: " + relative)
    return manifest


def canonical_hashes(directory: Path) -> dict[str, str]:
    """Runtime and recording metadata remain explicit noncanonical artifacts."""
    return {str(path.relative_to(directory)): digest(path)
            for path in sorted(directory.rglob("*"))
            if path.is_file() and path.suffix != ".rrd"
            and path.name not in {"runtime.json", "inference_freeze.json"}}


def freeze_inference(directory: Path, *, dataset_manifest_sha256: str,
                     config_sha256: str) -> dict[str, Any]:
    artifact_hashes = canonical_hashes(directory)
    if not artifact_hashes:
        raise ValueError("cannot freeze absent inference evidence")
    result = {
        "schema_version": "phase1-reviewed-inference-freeze-v1",
        "status": "FROZEN_BEFORE_EVALUATION", "ground_truth_read": False,
        "dataset_manifest_sha256": dataset_manifest_sha256,
        "config_sha256": config_sha256, "artifacts": artifact_hashes,
    }
    write_json(directory / "inference_freeze.json", result)
    return result


def require_inference_freeze(directory: Path) -> dict[str, Any]:
    freeze = read_json(directory / "inference_freeze.json")
    if freeze.get("status") != "FROZEN_BEFORE_EVALUATION" or freeze.get("ground_truth_read"):
        raise ValueError("evaluation requires a GT-free inference freeze receipt")
    if canonical_hashes(directory) != freeze.get("artifacts"):
        raise ValueError("primary inference changed after freeze")
    return freeze


def _module(repo_root: Path, name: str) -> Any:
    path = repo_root / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location("reviewed_pipeline_" + name, path)
    if spec is None or spec.loader is None:
        raise ValueError("existing projection module is unavailable")
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    spec.loader.exec_module(result)
    return result


def _cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    cases = config["cases"]
    if isinstance(cases, dict):
        return [dict(value, case_id=identity) for identity, value in cases.items()]
    return list(cases)


def infer_dataset(dataset: Path, application: Path, config_path: Path, output: Path,
                  *, repo_root: Path, reordered: bool = False) -> dict[str, Any]:
    """Run all ready A/B/C variants and freeze them before any GT file opens."""
    from amidst.finalization.reviewed_authority import (
        build_reviewed_context,
        convert_landmark_dataset,
        load_reviewed_authority,
        run_reviewed_baseline,
        validate_reviewed_endpoints,
    )
    from amidst.finalization.route_inventory import (
        build_reviewed_case_pipeline,
        load_reviewed_case_inference_config,
        reviewed_case_readiness,
    )

    manifest = verify_dataset(dataset)
    typed_config = load_reviewed_case_inference_config(config_path)
    config = typed_config.model_dump(mode="json")
    if manifest["config_sha256"] != typed_config.export_config_file_sha256:
        raise ValueError("dataset configuration does not match frozen reviewed config")
    authority = load_reviewed_authority(application, repo_root=repo_root)
    if manifest["source_sha256"] != authority.source_sha256:
        raise ValueError("dataset source differs from the reviewed authority")
    if manifest.get("application_manifest_sha256") != digest(application / "manifest.json") or (
        manifest.get("human_decisions_sha256") != authority.human_decisions_sha256
    ):
        raise ValueError("dataset application manifest or human decisions binding differs")
    if output.exists():
        raise FileExistsError("inference output must be fresh")
    output.mkdir(parents=True)
    composer = _module(repo_root, "phase1_projection_policy")
    summaries: list[dict[str, Any]] = []
    for recipe in _cases(config):
        identity = recipe["case_id"]
        directory = output / identity
        observed_path = dataset / "inference" / identity / "observations.json"
        if not observed_path.exists():
            record = {"case_id": identity, "status": "BLOCKED", "result_type": "N/A",
                      "blockers": recipe.get("blockers", ["CASE_NOT_EXPORTABLE"]),
                      "formal_inference_executed": False, "ground_truth_read": False}
            write_json(directory / "readiness.json", record)
            summaries.append(record)
            continue
        for name in ("observations.json", "context.json"):
            relative = f"inference/{identity}/{name}"
            if relative not in manifest["artifacts"] or digest(
                safe_artifact(dataset, relative)
            ) != manifest["artifacts"][relative]:
                raise ValueError("required case inference input is missing from frozen manifest")
        observations = PilotObservationExport.model_validate_json(observed_path.read_bytes())
        native_context = PilotInferenceContext.model_validate_json(
            (observed_path.parent / "context.json").read_bytes(),
        )
        context = build_reviewed_context(
            authority, native_context, observations_sha256=digest(observed_path),
            fresh_export_config_sha256=typed_config.export_config_file_sha256,
        )
        if reordered:
            observations = PilotObservationExport.model_validate(
                observations.model_dump(mode="python") | {"frames":
                                                           tuple(reversed(observations.frames))},
            )
        sidecar = composer.project_export(context.computation_context, observations)
        native_frames = composer.project_policy_frames(observations, context.computation_context)
        frames = convert_landmark_dataset(native_frames, context, authority,
                                          projection_sidecar=sidecar)
        aggregation = aggregate_frames(
            frames.samples, AggregationPolicy(
                max_visible_sample_gap_s=typed_config.aggregation_max_visible_sample_gap_s,
            ),
        )
        write_json(directory / "projection.json", sidecar)
        write_json(directory / "frames.json", frames.model_dump(mode="json"))
        write_json(directory / "aggregation.json", aggregation.model_dump(mode="json"))
        write_json(directory / "reviewed_context.json", context.model_dump(mode="json"))
        try:
            start, end = validate_reviewed_endpoints(aggregation, context, authority)
            pipeline = build_reviewed_case_pipeline(
                start, end, authority.provider, typed_config,
                identity, context.binding.spatial_context_id,
            )
        except ValueError as error:
            record = {"case_id": identity, "status": "BLOCKED", "result_type": "N/A",
                      "blockers": [str(error)], "formal_inference_executed": False,
                      "ground_truth_read": False,
                      "projection_method_counts": dict(Counter(row["method"]
                                                               for row in sidecar["rows"])),
                      "projection_state_counts": dict(Counter(row["state"]
                                                              for row in sidecar["rows"]))}
            write_json(directory / "readiness.json", record)
            summaries.append(record)
            continue
        if isinstance(pipeline, tuple):
            pipeline = pipeline[0]
        readiness = reviewed_case_readiness(
            start, end, authority.provider, typed_config,
            identity, context.binding.spatial_context_id,
        ) | {
            "case_id": identity, "status": "READY", "result_type": "FORMAL",
            "source_sha256": authority.source_sha256,
            "config_sha256": digest(config_path), "ground_truth_read": False,
            "visible_gap_visible": True,
            "gap_time_range": [start.end_time, end.start_time],
            "scope_hashes_retained": True,
            "aggregation_max_visible_sample_gap_s": aggregation.policy.max_visible_sample_gap_s,
            "aggregation_policy_content_sha256":
            content_sha256(aggregation.policy.model_dump(mode="json")),
        }
        if readiness.get("case_execution_ready") is not True:
            readiness.update(status="BLOCKED", result_type="N/A",
                             blockers=["CASE_PROTOCOL_READINESS_NOT_PROVEN"])
            write_json(directory / "readiness.json", readiness)
            summaries.append(readiness)
            continue
        write_json(directory / "readiness.json", readiness)
        write_json(directory / "pipeline.json", pipeline.model_dump(mode="json"))
        inputs = InferenceInput(
            dataset_id=manifest["dataset_version"], random_seed=config.get("inference_seed", 42),
            start_observation=start, end_observation=end,
            **pipeline.model_dump(mode="python"),
        )
        write_json(directory / "inputs.json", inputs.model_dump(mode="json"))
        variants: list[tuple[str, str | None]] = [(method, None) for method in METHODS]
        variants.extend(("spatiotemporal", ablation) for ablation in ABLATIONS)
        runtime: dict[str, float | None] = {}
        for method, ablation in variants:
            variant = ablation or method
            started = time.perf_counter()
            try:
                result = run_reviewed_baseline(
                    inputs, method, authority=authority, context=context,
                    frozen_config_sha256=content_sha256(typed_config.model_dump(mode="json")),
                    case_readiness_sha256=content_sha256(readiness),
                    case_readiness=readiness, aggregation=aggregation,
                    ablation_id=ablation,
                )
            except ValueError as error:
                if ablation != "remove_collision":
                    raise
                write_json(directory / (variant + ".json"), {
                    "method_id": method, "ablation_id": ablation, "result_type": "N/A",
                    "status": "UNAVAILABLE", "reasons": [str(error)],
                    "reference_full_collision_scope_preserved": True,
                })
                runtime[variant] = None
                continue
            runtime[variant] = time.perf_counter() - started
            write_json(directory / (variant + ".json"), result.model_dump(mode="json"))
        write_json(directory / "runtime.json", runtime)
        summaries.append(readiness)
    write_json(output / "summary.json", {"cases": summaries, "ground_truth_read": False,
                                          "all_cases_ready": all(row["status"] == "READY"
                                                                 for row in summaries)})
    freeze = freeze_inference(output, dataset_manifest_sha256=digest(dataset / "manifest.json"),
                              config_sha256=digest(config_path))
    verify_dataset(dataset)
    return freeze


def benchmark_rows(case_summaries: list[dict[str, Any]],
                   measurements: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep every Case × A/B/C × K row, preserving nulls and actual blockers."""
    by_case = {row["case_id"]: row for row in case_summaries}
    rows = []
    for case_id in ("case1", "case2", "case3"):
        case = by_case.get(case_id, {"status": "NOT_RUN", "blockers": ["CASE_NOT_RUN"]})
        for method in METHODS:
            measurement = measurements.get(case_id, {}).get(method, {})
            for k in K_VALUES:
                at_k = measurement.get("metrics_at_k", {}).get(str(k), {})
                rows.append({
                    "case_id": case_id, "method_id": method, "k": k,
                    "result_type": measurement.get("result_type", "N/A"),
                    "status": measurement.get("status", case["status"]),
                    "blockers": case.get("blockers", []),
                    "ade_m": measurement.get("ade_m"), "fde_m": measurement.get("fde_m"),
                    "min_ade_at_k_m": at_k.get("min_ade_at_k_m"),
                    "min_fde_at_k_m": at_k.get("min_fde_at_k_m"),
                    "coverage_at_k": at_k.get("coverage_at_k"),
                    "collision_rate": measurement.get("collision_rate"),
                    "constraint_violation_rate": measurement.get("constraint_violation_rate"),
                    "candidate_count": measurement.get("candidate_count"),
                    "expanded_states": measurement.get("expanded_states"),
                    "inference_runtime_s": measurement.get("inference_runtime_s"),
                    "termination_reason": measurement.get("termination_reason"),
                    "projection_error_m": measurement.get("projection_error_m"),
                    "feasible_candidate_recall": measurement.get("feasible_candidate_recall"),
                    "impossible_transition_rate": measurement.get("impossible_transition_rate"),
                    "path_length_error_m": measurement.get("path_length_error_m"),
                    "travel_time_error_s": measurement.get("travel_time_error_s"),
                })
    return rows


def write_benchmark_tables(output: Path, rows: list[dict[str, Any]]) -> None:
    write_json(output / "benchmark_table.json", {"rows": rows})
    if not rows:
        raise ValueError("all requested benchmark rows must remain visible")
    with (output / "benchmark_table.csv").open("x", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    columns = [name for name in rows[0] if name != "blockers"]
    lines = ["# Reviewed Phase 1 benchmark", "", "N/A values retain their recorded blockers.",
             "", "| " + " | ".join(columns) + " |",
             "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend("| " + " | ".join("N/A" if row[name] is None else str(row[name])
                                   for name in columns) + " |" for row in rows)
    (output / "benchmark_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def compare_frozen_runs(local: Path, fresh: Path) -> dict[str, Any]:
    local_freeze, fresh_freeze = require_inference_freeze(local), require_inference_freeze(fresh)
    equal = all(local_freeze[field] == fresh_freeze[field]
                for field in ("dataset_manifest_sha256", "config_sha256", "artifacts"))
    return {"status": "PASS" if equal else "FAIL", "canonical_inference_equal": equal,
            "candidate_order_and_termination_included": True,
            "runtime_and_rrd_container_bytes_excluded": True,
            "noncanonical_reason": "measured runtime and recording metadata",
            "freeze_permitted_by_this_comparison": False}


def fresh_process_inference(dataset: Path, application: Path, config: Path, output: Path,
                            *, repo_root: Path, reordered: bool = False) -> None:
    arguments = [sys.executable, str(repo_root / "scripts/run_phase1_reviewed.py"),
                 "infer", "--dataset", str(dataset), "--application", str(application),
                 "--config", str(config), "--output", str(output)]
    if reordered:
        arguments.append("--reordered")
    result = subprocess.run(arguments, cwd=repo_root, capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def create_gt_poison_dataset(dataset: Path, output: Path) -> None:
    """Evaluation-only poison copy; inference payloads are copied byte-for-byte."""
    verify_dataset(dataset, inference_only=False)
    if output.exists():
        raise FileExistsError("GT poison dataset must be fresh")
    shutil.copytree(dataset, output)
    for path in sorted((output / "evaluation").rglob("ground_truth.json")):
        truth = read_json(path)
        for row in truth["samples"]:
            row["position"] = [value + 100000 * (axis + 1)
                               for axis, value in enumerate(row["position"])]
        path.write_text(json.dumps(truth, sort_keys=True, indent=2, allow_nan=False) + "\n")
    for path in sorted((output / "simulation").rglob("recipe.json")):
        recipe = read_json(path)
        for row in recipe.get("waypoints", []):
            row["position"] = [value - 100000 * (axis + 1)
                               for axis, value in enumerate(row["position"])]
        recipe["poisoned_for_gt_isolation_test"] = True
        path.write_text(json.dumps(recipe, sort_keys=True, indent=2, allow_nan=False) + "\n")
    for path in sorted((output / "evaluation").rglob("reference_movement_annotations.json")):
        path.write_text('{"poisoned_reference_annotations": true, "segments": "INVALID"}\n')
    # Preserve the manifest bytes; inference-only validation deliberately ignores GT.


def evaluation_reference(truth: dict[str, Any], event: Any, *, seed: int) -> Any:
    """Build the exact all-timestamps gap reference only in the post-freeze stage."""
    from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory

    if truth.get("provenance") != "GROUND_TRUTH":
        raise ValueError("evaluation reference requires explicit Ground Truth provenance")
    start, end = event.time_range
    selected = [row for row in truth["samples"] if start <= row["timestamp"] <= end]
    if len(selected) < 2 or selected[0]["timestamp"] != start or (
        selected[-1]["timestamp"] != end
    ):
        raise ValueError("reference must include every exact GAP endpoint without extrapolation")
    samples = []
    for index, row in enumerate(selected):
        position = tuple(value * .0247 for value in row["position"])
        previous = selected[max(0, index - 1)]
        following = selected[min(index + 1, len(selected) - 1)]
        duration = following["timestamp"] - previous["timestamp"]
        velocity = tuple((b - a) * .0247 / duration
                         for a, b in zip(previous["position"], following["position"], strict=True))
        samples.append(GroundTruthSample(timestamp=row["timestamp"], position=position,
                                         velocity=velocity, floor_id=row["floor_id"]))
    return GroundTruthTrajectory(
        trajectory_id=truth["trajectory_id"], target_id=truth["target_id"],
        scene_id=truth["spatial_context_id"], random_seed=seed, sample_rate_hz=5,
        sample_source=truth.get("sample_source", "CONFIGURATION_SAMPLER"),
        source_asset_sha256=truth["source_asset_sha256"],
        samples=tuple(samples),
    )


def additional_metrics(sidecar: dict[str, Any], truth: dict[str, Any], run: Any,
                       *,
                       source_bound_offset_bu: float) -> dict[str, Any]:
    """Evaluation-only additional metrics with exact populations and authority."""
    by_time = {row["timestamp"]: row["position"] for row in truth["samples"]}
    errors = []
    for row in sidecar["rows"]:
        selected = row["selected_world_position"]
        if selected is not None:
            foot = [selected[0], selected[1], selected[2] - source_bound_offset_bu]
            errors.append(math.dist(foot, by_time[row["timestamp"]]) * .0247)
    start, end = run.event.time_range
    points = [row["position"] for row in truth["samples"]
              if start <= row["timestamp"] <= end]
    reference_length = sum(math.dist(a, b) for a, b in zip(points[:-1], points[1:], strict=True))
    path_length = None
    if run.event.candidates:
        primary = run.event.candidates[0]
        candidate_length = sum(math.dist(a, b) for a, b in zip(
            primary.polyline[:-1], primary.polyline[1:], strict=True,
        ))
        path_length = abs(candidate_length - reference_length * .0247)
    return {
        "projection_error_m": sum(errors) / len(errors) if errors else None,
        "projection_error_population": "POLICY_SELECTED_VISIBLE_TIMESTAMP_FOOTPOINTS",
        "projection_error_sample_count": len(errors),
        "path_length_error_m": path_length,
        "path_length_reference": "ALL_EXACT_GAP_REFERENCE_TIMESTAMPS_3D_POLYLINE",
        "travel_time_error_s": None,
        "travel_time_error_status": "N/A_REFERENCE_MOVING_TIME_DWELL_ANNOTATION_NOT_APPROVED",
    }


def evaluate_dataset(dataset: Path, inference: Path, application: Path, output: Path,
                     *, repo_root: Path, demos: bool = True) -> dict[str, Any]:
    """Open GT only after all primary inference and blocked evidence have frozen."""
    freeze = require_inference_freeze(inference)
    from amidst.benchmark_report import generate_comparison
    from amidst.domain.evaluation import ConstraintConfig
    from amidst.domain.pipeline import PipelineConfig
    from amidst.domain.stream import ObservationAggregation
    from amidst.finalization.reviewed_authority import (
        ReviewedBaselineRun,
        ReviewedInferenceContext,
        load_reviewed_authority,
        reviewed_metric_config,
    )
    from amidst.finalization.reviewed_evaluation import evaluate_reviewed_trajectories
    from amidst.finalization.reviewed_evaluation_metrics import (
        build_reviewed_metric_inventory,
        evaluate_reviewed_inventory_metrics,
    )
    from amidst.finalization.reviewed_reference_movement import (
        evaluate_reference_movement,
        load_reference_movement_approval,
    )

    manifest = verify_dataset(dataset, inference_only=False)
    if digest(dataset / "manifest.json") != freeze["dataset_manifest_sha256"]:
        raise ValueError("evaluation dataset differs from the primary inference freeze")
    if output.exists():
        raise FileExistsError("evaluation output must be fresh")
    output.mkdir(parents=True)
    authority = load_reviewed_authority(application, repo_root=repo_root)
    metrics = reviewed_metric_config(authority)
    movement_approval = None
    if "reference_movement_approval_receipt_content_sha256" in manifest:
        movement_approval = load_reference_movement_approval(
            repo_root / "data/finalization/reference_movement_approved_v1/approval_receipt.json",
            repo_root / "configs/finalization/proposed_reference_movement_policy_v1.json",
            expected_receipt_content_sha256=manifest[
                "reference_movement_approval_receipt_content_sha256"],
            expected_source_sha256=authority.source_sha256,
            expected_protocol_sha256=read_json(
                repo_root / "data/finalization/reference_movement_approved_v1" /
                "approved_input_lock.json",
            )["protocol_sha256"],
            expected_original_human_decisions_sha256=authority.human_decisions_sha256,
        )
        if movement_approval.proposal_content_sha256 != manifest[
            "reference_movement_policy_content_sha256"
        ]:
            raise ValueError("dataset reference policy differs from its fresh movement approval")
    write_json(output / "metric_authority.json", metrics.model_dump(mode="json"))
    case_summaries = read_json(inference / "summary.json")["cases"]
    measurements: dict[str, dict[str, Any]] = {}
    normalized = []
    demo_results = []
    for case in case_summaries:
        identity = case["case_id"]
        measurements[identity] = {}
        if case["status"] != "READY":
            for method in METHODS:
                normalized.append({"case_id": identity, "method_id": method,
                                   "run_id": "reviewed_v1", "status": case["status"],
                                   "metrics": {}, "coverage_at_k": {"1": None, "2": None,
                                                                        "3": None}})
            continue
        directory = inference / identity
        frozen_aggregation = ObservationAggregation.model_validate_json(
            (directory / "aggregation.json").read_bytes(),
        )
        frozen_context = ReviewedInferenceContext.model_validate_json(
            (directory / "reviewed_context.json").read_bytes(),
        )
        pipeline = PipelineConfig.model_validate_json((directory / "pipeline.json").read_bytes())
        metric_inventory = build_reviewed_metric_inventory(
            frozen_aggregation, frozen_context, authority,
            frozen_config_sha256=case["case_config_content_sha256"],
            endpoint_tolerance_m=pipeline.reconstruction_policy.endpoint_tolerance_m,
        )
        write_json(output / identity / "independent_metric_inventory.json",
                   metric_inventory.model_dump(mode="json"))
        truth = read_json(dataset / "evaluation" / identity / "ground_truth.json")
        constraints = ConstraintConfig(max_speed_m_s=pipeline.movement.max_speed_m_s,
                                       navigation_graph=pipeline.navigation)
        runtime = read_json(directory / "runtime.json")
        sidecar = read_json(directory / "projection.json")
        source_offset = read_json(directory / "reviewed_context.json")["offset_bu"]
        variants: list[tuple[str, str | None]] = [(method, None) for method in METHODS]
        variants.extend(("spatiotemporal", ablation) for ablation in ABLATIONS)
        for method, ablation in variants:
            variant = ablation or method
            raw = read_json(directory / (variant + ".json"))
            if raw.get("result_type") == "N/A":
                write_json(output / identity / (variant + ".json"), raw)
                continue
            run = ReviewedBaselineRun.model_validate(raw)
            if run.timed_metrics_status != "AVAILABLE":
                record = {
                    "result_type": "FORMAL", "status": "N/A_TIMING_UNAVAILABLE",
                    "candidate_count": len(run.event.candidates),
                    "expanded_states": run.geometric_result.expanded_nodes,
                    "inference_runtime_s": runtime[variant],
                    "termination_reason": run.event.termination_reason.value,
                    "metrics_at_k": {}, "timing_unavailable_route_ids":
                    run.timing_unavailable_route_ids,
                    "reason": "COMPRESSED_TIMED_SUBSET_IS_NOT_ORIGINAL_TOP_K",
                }
                write_json(output / identity / (variant + ".json"), record)
                if ablation is None:
                    measurements[identity][method] = record
                    normalized.append({"case_id": identity, "method_id": method,
                                       "run_id": "reviewed_v1", "status": record["status"],
                                       "metrics": {}, "coverage_at_k": {"1": None, "2": None,
                                                                            "3": None}})
                continue
            reference = evaluation_reference(truth, run.event, seed=manifest["inference_seed"])
            evaluated = evaluate_reviewed_trajectories(
                run.event, reference, metrics, constraints=constraints, authority=authority,
            )
            evaluated["inference_freeze_sha256"] = digest(inference / "inference_freeze.json")
            evaluated["ground_truth_loaded_after_inference_freeze"] = True
            write_json(output / identity / (variant + ".json"), evaluated)
            payload = evaluated["computation_result"]["evaluations"]
            first_metrics = payload[0]["trajectory_metrics"]
            physical = evaluated["reviewed_physical"]
            extra = additional_metrics(sidecar, truth, run,
                                       source_bound_offset_bu=source_offset) | (
                evaluate_reviewed_inventory_metrics(run, metric_inventory, authority)
            )
            if movement_approval is not None:
                annotations = read_json(
                    dataset / "evaluation" / identity / "reference_movement_annotations.json",
                )
                extra.update(evaluate_reference_movement(
                    run.event, annotations, movement_approval,
                    expected_dataset_version=manifest["dataset_version"],
                ))
            write_json(output / identity / (variant + "_additional_metrics.json"), extra)
            record = {
                "result_type": "FORMAL", "status": "EVALUATED",
                "ade_m": first_metrics[0]["ade_m"] if first_metrics else None,
                "fde_m": first_metrics[0]["fde_m"] if first_metrics else None,
                "collision_rate": (0.0 if physical["segment_count"] > 0
                                   and physical["violation_segment_count"] == 0 else None),
                "collision_status": "AVAILABLE_COMPLETE_SCOPE" if (
                    physical["segment_count"] > 0 and physical["violation_segment_count"] == 0
                ) else "N/A_UNVALIDATED_SCOPE_SEGMENTS_ARE_NOT_COLLISION_INTERSECTIONS",
                "constraint_violation_rate": payload[0]["constraint_violation_rate"],
                "candidate_count": len(run.event.candidates),
                "expanded_states": run.geometric_result.expanded_nodes,
                "inference_runtime_s": runtime[variant],
                "termination_reason": run.event.termination_reason.value,
                "metrics_at_k": {str(row["config"]["k_routes"]): {
                    "min_ade_at_k_m": row["min_ade_at_k_m"],
                    "min_fde_at_k_m": row["min_fde_at_k_m"],
                    "coverage_at_k": row["coverage_at_k"],
                } for row in payload},
                "physical_segment_count": physical["segment_count"],
                "physical_violation_segment_count": physical["violation_segment_count"],
            } | extra
            if ablation is None:
                measurements[identity][method] = record
                normalized.append({
                    "case_id": identity, "method_id": method, "run_id": "reviewed_v1",
                    "status": "EVALUATED", "selected_k": 3,
                    "metrics": {"ade_m": record["ade_m"], "fde_m": record["fde_m"],
                                "min_ade_at_k_m": record["metrics_at_k"]["3"]["min_ade_at_k_m"],
                                "min_fde_at_k_m": record["metrics_at_k"]["3"]["min_fde_at_k_m"],
                                "collision_rate": record["collision_rate"],
                                "constraint_violation_rate": record["constraint_violation_rate"],
                                "candidate_count": record["candidate_count"],
                                "search_nodes": record["expanded_states"],
                                "runtime_s": record["inference_runtime_s"],
                                "projection_error_m": extra["projection_error_m"],
                                "path_length_error_m": extra["path_length_error_m"],
                                "feasible_candidate_recall": extra["feasible_candidate_recall"],
                                "impossible_transition_rate": extra["impossible_transition_rate"],
                                "travel_time_error_s": extra["travel_time_error_s"]},
                    "coverage_at_k": {k: row["coverage_at_k"]
                                      for k, row in record["metrics_at_k"].items()},
                    "termination_reason": record["termination_reason"],
                    "physical_counts": {"collision_rate": {
                        "numerator": physical["violation_segment_count"],
                        "denominator": physical["segment_count"]}},
                    "provenance": {"benchmark_kind": "BLENDER_RESEARCH_RESULT",
                                   "formal_benchmark_status": "APPROVED",
                                   "scene_sha256": authority.source_sha256,
                                   "dataset_id": manifest["dataset_version"],
                                   "protocol_version": "phase1-benchmark-protocol-v1"},
                })
            if demos and method == "spatiotemporal" and ablation is None:
                demo_results.append(write_reviewed_demo(
                    directory, run.event, pipeline, output / "demos" / identity,
                    authority_summary={"result_type": "FORMAL_LOCAL_SCOPE",
                                       "scope_id":
                                       authority.certificate.physical_certificate.scope_id,
                                       "certificate_sha256": authority.certificate_content_sha256,
                                       "case_full_exit_complete": False,
                                       "source_sha256": authority.source_sha256,
                                       "semantic_review_content_sha256":
                                       authority.semantic_review_content_sha256,
                                       "footpoint_bounds_bu":
                                       authority.certificate.physical_certificate.footpoint_bounds_bu,
                                       "body_guard_bounds_bu": authority.approved_input_lock[
                                           "geometry_semantics"]["body_envelope_bounds_bu"],
                                       "support_z_bu": authority.floor_support_z_bu,
                                       "whole_component_approved": False,
                                       "metres_per_blender_unit": .0247},
                ))
    rows = benchmark_rows(case_summaries, measurements)
    write_json(output / "dataset_acceptance.json", {
        "schema_version": "phase1-reviewed-dataset-acceptance-v1",
        "source_export_manifest_sha256": digest(dataset / "manifest.json"),
        "primary_inference_freeze_sha256": digest(inference / "inference_freeze.json"),
        "source_export_manifest_preserved": True,
        "overall_formal_execution_enabled": False,
        "formal_dataset_all_cases_validated": False,
        "per_case_execution_ready": {case["case_id"]: case["status"] == "READY"
                                     for case in case_summaries},
        "case_results": {
            "case1": "FORMAL_REVIEWED_LOCAL_RUN" if measurements.get("case1") else "N/A",
            "case2": "N/A_BLOCKED_SCOPE",
            "case3": "FORMAL_REVIEWED_LOCAL_TEMPORAL_COMPONENT" if (
                measurements.get("case3")
            ) else "N/A",
        },
        "case3_full_stress_exit_complete": False,
        "human_decisions_sha256": authority.human_decisions_sha256,
        "certificate_content_sha256": authority.certificate_content_sha256,
        "semantic_review_content_sha256": authority.semantic_review_content_sha256,
        "reference_movement_approval_receipt_content_sha256": manifest.get(
            "reference_movement_approval_receipt_content_sha256"),
        "legacy_diagnostic_artifacts_promoted": False,
    })
    write_benchmark_tables(output, rows)
    write_json(output / "comparison.json", {
        "schema_version": "benchmark-comparison/v1", "cases": ["case1", "case2", "case3"],
        "methods": list(METHODS), "runs": normalized,
        "comparison_settings": {"dataset_version": manifest["dataset_version"],
                                "seed": manifest["inference_seed"],
                                "metric_config": metrics.computation_config.model_dump(mode="json"),
                                "requested_k": list(K_VALUES)},
    })
    comparison = generate_comparison(output / "comparison.json", output / "charts")
    projection_summary = write_projection_charts(inference, output / "charts")
    report = {
        "schema_version": "phase1-reviewed-evaluation-report-v1",
        "status": "PHASE1_FINALIZATION_BLOCKED", "freeze_allowed": False,
        "dataset_manifest_sha256": digest(dataset / "manifest.json"),
        "primary_inference_freeze_sha256": digest(inference / "inference_freeze.json"),
        "evaluation_inference_freeze_verified": True,
        "cases": case_summaries, "measurements": measurements,
        "formal_case_execution": {row["case_id"]: row["status"] == "READY"
                                  for row in case_summaries},
        "all_case_exit_complete": False,
        "overall_physical_authority": "PARTIAL_APPROVED",
        "geometry_scope": "ONE_COMPLETE_REVIEWED_RESTRICTED_OFFICE_RECTANGLE",
        "benchmark_rows": len(rows), "demos": demo_results,
        "chart_files": comparison["generated_charts"] + [
            "projection_methods.png", "projection_confidence.png", "projection_uncertainty.png"],
        "projection_diagnostics": projection_summary,
        "required_metric_unavailable_reasons": {} if movement_approval is not None else {
            "travel_time_error_s": "REFERENCE_MOVING_TIME_DWELL_ANNOTATION_NOT_APPROVED"},
        "case4_status": "DEFERRED", "phase2_status": "FROZEN",
    }
    require_inference_freeze(inference)
    write_json(output / "verification.json", report)
    return report


def write_projection_charts(inference: Path, output: Path) -> dict[str, Any]:
    """One metric per plot, with no calibrated probability invented from geometry."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = []
    for path in sorted(inference.glob("*/projection.json")):
        sidecar = read_json(path)
        rows.append({
            "case_id": path.parent.name,
            "methods": dict(Counter(row["method"] for row in sidecar["rows"])),
            "confidence_states": dict(Counter(row["state"] for row in sidecar["rows"])),
            "uncertainty_states": dict(Counter(row["uncertainty"]["status"]
                                               for row in sidecar["rows"])),
            "pixel_sigma_px": None, "confidence_is_calibrated_probability": False,
            "surface_constrained_inference": "N/A_UNAPPROVED_SCHOOL_SURFACE_AUTHORITY",
            "retained_evidence_count": sidecar["retained_evidence_count"],
        })
    for field, filename, title in (
        ("methods", "projection_methods.png", "Projection methods"),
        ("confidence_states", "projection_confidence.png", "Projection confidence states"),
        ("uncertainty_states", "projection_uncertainty.png", "Projection uncertainty states"),
    ):
        labels = sorted({label for row in rows for label in row[field]})
        figure, axis = plt.subplots(figsize=(9, 4))
        bottom = [0] * len(rows)
        for label in labels:
            values = [row[field].get(label, 0) for row in rows]
            axis.bar([row["case_id"] for row in rows], values, bottom=bottom, label=label)
            bottom = [a + b for a, b in zip(bottom, values, strict=True)]
        axis.set(ylabel="Source timestamps", title=title + " / FORMAL reviewed local scope")
        axis.legend(fontsize=7)
        figure.tight_layout()
        figure.savefig(output / filename, dpi=120)
        plt.close(figure)
    result = {"cases": rows, "ground_truth_used": False,
              "pixel_noise_not_declared": True, "uncertainty_probability_not_calibrated": True}
    write_json(output / "projection_diagnostics.json", result)
    return result


def write_reviewed_demo(inference: Path, event: Any, pipeline: Any, output: Path,
                        *, authority_summary: dict[str, Any]) -> dict[str, Any]:
    """Replay the existing Event adapter; GT stays in an independent optional layer."""
    import matplotlib
    import rerun as rr
    import rerun.blueprint as rrb

    from amidst.domain.stream import ObservationAggregation
    from amidst.visualization.rerun_adapter import RerunDebugVisualizationAdapter

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(parents=True, exist_ok=False)
    aggregation = ObservationAggregation.model_validate_json(
        (inference / "aggregation.json").read_bytes(),
    )
    recording = rr.RecordingStream("amidst_reviewed_phase1_local")
    adapter = RerunDebugVisualizationAdapter(
        observations=tuple(row.observation for row in aggregation.observations),
        navigation_config=pipeline.navigation, topology_config=pipeline.topology,
        recording=recording, debug_mode=False,
    )
    adapter.save(output / "reviewed.rrd")
    adapter.log_event(event)
    recording.log("debug/reviewed_authority", rr.TextDocument(json.dumps(
        authority_summary, sort_keys=True, indent=2,
    )), static=True)
    native_context = read_json(inference / "reviewed_context.json")["computation_context"]
    ratio = authority_summary["metres_per_blender_unit"]

    def wire_box(bounds: Any) -> list[list[list[float]]]:
        low, high = [[value * ratio for value in point] for point in bounds]
        corners = [[high[axis] if index & (1 << axis) else low[axis]
                    for axis in range(3)] for index in range(8)]
        return [[corners[index], corners[index ^ (1 << axis)]]
                for index in range(8) for axis in range(3) if not index & (1 << axis)]

    certificate_outline = wire_box(authority_summary["footpoint_bounds_bu"])
    guard_outline = wire_box(authority_summary["body_guard_bounds_bu"])
    recording.log("world/reviewed_certificate/footpoint_domain", rr.LineStrips3D(
        certificate_outline, colors=(50, 170, 100), radii=.006,
        labels=["Complete reviewed local footpoint domain"] * len(certificate_outline),
    ), static=True)
    recording.log("world/reviewed_certificate/body_guard", rr.LineStrips3D(
        guard_outline, colors=(130, 130, 130), radii=.004,
        labels=["Exact approved body guard / scope only"] * len(guard_outline),
    ), static=True)
    source_cameras = []
    for camera in native_context["cameras"]:
        matrix = camera["camera_to_world"]
        origin = [matrix[axis][3] * ratio for axis in range(3)]
        optical_norm = math.sqrt(sum(matrix[axis][2] ** 2 for axis in range(3)))
        if optical_norm <= 0:
            raise ValueError("source camera optical heading must have positive length")
        heading = [origin[axis] - matrix[axis][2] / optical_norm for axis in range(3)]
        source_cameras.append({"camera_id": camera["camera_id"], "position_m": origin,
                               "heading_display_endpoint_m": heading,
                               "heading_display_length_m": 1.0,
                               "calibration_source_sha256": authority_summary["source_sha256"]})
        camera_root = "world/source_observation_cameras/" + camera["camera_id"]
        recording.log(camera_root + "/pose", rr.Points3D(
            [origin], radii=.07, labels=["Source observation camera " + camera["camera_id"]],
            colors=(70, 150, 200),
        ), static=True)
        recording.log(camera_root + "/heading", rr.LineStrips3D(
            [[origin, heading]], radii=.012, colors=(70, 150, 200),
            labels=["Source optical heading / presentation length 1 m"],
        ), static=True)
    recording.send_blueprint(rrb.Blueprint(rrb.Horizontal(
        rrb.Spatial3DView(origin="/world", name="FORMAL / reviewed local scope",
                          contents=["+ /world/**", "- /world/debug_ground_truth/**"]),
        rrb.TextDocumentView(origin="/debug/reviewed_authority", name="Authority / limits"),
    ), auto_views=False, auto_layout=False))
    adapter.close()
    result = subprocess.run([str(Path(sys.executable).with_name("rerun")), "rrd", "verify",
                             str(output / "reviewed.rrd")], capture_output=True, text=True,
                            check=False)
    if result.returncode:
        raise RuntimeError("Rerun reader rejected reviewed recording: " + result.stderr)
    figure, axis = plt.subplots(figsize=(9, 5))
    for bounds, label, style in (
        (authority_summary["footpoint_bounds_bu"], "Certified footpoint domain", "-"),
        (authority_summary["body_guard_bounds_bu"], "Approved body guard", ":"),
    ):
        low, high = [[value * ratio for value in point] for point in bounds]
        outline = [(low[0], low[1]), (high[0], low[1]), (high[0], high[1]),
                   (low[0], high[1]), (low[0], low[1])]
        axis.plot([point[0] for point in outline], [point[1] for point in outline],
                  linestyle=style, label=label)
    for observation in aggregation.observations:
        points = observation.observation.projected_path
        axis.scatter([point.world_position[0] for point in points],
                     [point.world_position[1] for point in points], s=12,
                     label="PROJECTED " + observation.observation.camera_id)
    for rank, candidate in enumerate(event.candidates, 1):
        axis.plot([point[0] for point in candidate.polyline],
                  [point[1] for point in candidate.polyline], linestyle="--",
                  label="INFERRED_GAP Top-" + str(rank))
    axis.set(xlabel="X (m)", ylabel="Y (m)", title="FORMAL / reviewed local scope")
    axis.set_aspect("equal", adjustable="datalim")
    axis.legend(fontsize=7)
    figure.tight_layout()
    figure.savefig(output / "preview.png", dpi=120)
    plt.close(figure)
    presentation = {"authority": authority_summary, "event": event.model_dump(mode="json"),
                    "source_observation_cameras": source_cameras,
                    "certificate_outline_m": certificate_outline,
                    "body_guard_outline_m": guard_outline,
                    "gt_debug_default_visible": False,
                    "ground_truth_logged_to_primary_recording": False,
                    "rrd_reader_verified": True, "coordinate_units": "METRES"}
    write_json(output / "presentation.json", presentation)
    (output / "README.md").write_text(
        "# Reviewed local replay\n\nOpen with `uv run rerun reviewed.rrd`.\n\n"
        "The event_time timeline shows observed pixels, projected footpoints and all timed "
        "hypotheses in their inference order. Units are metres. The reviewed authority panel "
        "and green scope wireframe record the complete local footpoint domain; the gray "
        "wireframe is its exact approved body guard. Source camera poses and optical headings "
        "come from the immutable scene calibration; heading display length is 1 metre. "
        "These geometry layers cover only this local scope; overall school authority stays "
        "PARTIAL_APPROVED. "
        "Ground Truth is not logged to this primary recording; it remains in the separate "
        "evaluation package and is disabled by default. The full Phase 1 Exit Gate is blocked.\n",
        encoding="utf-8",
    )
    return {"case_id": inference.name, "rrd_reader_verified": True,
            "gt_debug_default_visible": False, "recording": str(output / "reviewed.rrd"),
            "preview": str(output / "preview.png")}


def verify_reproduction(dataset: Path, primary: Path, application: Path, config: Path,
                        output: Path, *, repo_root: Path) -> dict[str, Any]:
    """Actually rerun repeated/order/fresh/poison processes against frozen bytes."""
    from amidst.domain.evaluation import ConstraintConfig
    from amidst.domain.pipeline import PipelineConfig
    from amidst.finalization.reviewed_authority import (
        ReviewedBaselineRun,
        load_reviewed_authority,
        reviewed_metric_config,
    )
    from amidst.finalization.reviewed_evaluation import evaluate_reviewed_trajectories

    require_inference_freeze(primary)
    if output.exists():
        raise FileExistsError("reproduction output must be fresh")
    output.mkdir(parents=True)
    infer_dataset(dataset, application, config, output / "repeat", repo_root=repo_root)
    fresh_process_inference(dataset, application, config, output / "fresh_process",
                            repo_root=repo_root)
    infer_dataset(dataset, application, config, output / "reordered", repo_root=repo_root,
                  reordered=True)
    poison_dataset = output / "poison_dataset"
    create_gt_poison_dataset(dataset, poison_dataset)
    fresh_process_inference(poison_dataset, application, config, output / "gt_poison",
                            repo_root=repo_root)
    comparisons = {name: compare_frozen_runs(primary, output / name)
                   for name in ("repeat", "fresh_process", "reordered", "gt_poison")}
    annotation_paths = sorted((dataset / "evaluation").rglob("reference_movement_annotations.json"))
    annotation_poison_pass = bool(annotation_paths) and all(
        path.read_bytes() != (poison_dataset / path.relative_to(dataset)).read_bytes()
        for path in annotation_paths
    ) and comparisons["gt_poison"]["status"] == "PASS"
    authority = load_reviewed_authority(application, repo_root=repo_root)
    metrics = reviewed_metric_config(authority)
    evaluated_changes = []
    all_events = []
    for case in read_json(primary / "summary.json")["cases"]:
        if case["status"] != "READY":
            continue
        identity = case["case_id"]
        directory = primary / identity
        run = ReviewedBaselineRun.model_validate_json(
            (directory / "spatiotemporal.json").read_bytes(),
        )
        pipeline = PipelineConfig.model_validate_json((directory / "pipeline.json").read_bytes())
        constraints = ConstraintConfig(max_speed_m_s=pipeline.movement.max_speed_m_s,
                                       navigation_graph=pipeline.navigation)
        normal_truth = read_json(dataset / "evaluation" / identity / "ground_truth.json")
        poisoned_truth = read_json(poison_dataset / "evaluation" / identity / "ground_truth.json")
        normal = evaluate_reviewed_trajectories(
            run.event, evaluation_reference(normal_truth, run.event, seed=42), metrics,
            constraints=constraints, authority=authority,
        )
        poisoned = evaluate_reviewed_trajectories(
            run.event, evaluation_reference(poisoned_truth, run.event, seed=42), metrics,
            constraints=constraints, authority=authority,
        )
        write_json(output / "poison_evaluation" / (identity + ".json"), {
            "normal": normal, "poisoned": poisoned,
            "evaluation_changed": normal != poisoned,
            "primary_inference_equal": comparisons["gt_poison"]["status"] == "PASS",
        })
        evaluated_changes.append(normal != poisoned)
        all_events.append(run.event)
    passed = all(row["status"] == "PASS" for row in comparisons.values())
    poison_pass = bool(evaluated_changes) and all(evaluated_changes) and (
        comparisons["gt_poison"]["status"] == "PASS"
    )
    result = {
        "schema_version": "phase1-reviewed-reproduction-v1",
        "status": "PASS" if passed and poison_pass else "FAIL",
        "repeat_status": comparisons["repeat"]["status"],
        "fresh_process_status": comparisons["fresh_process"]["status"],
        "ordering_status": comparisons["reordered"]["status"],
        "gt_poison_status": "PASS" if poison_pass else "FAIL",
        "annotation_poison_inference_unchanged": annotation_poison_pass,
        "poisoned_reference_annotation_files": len(annotation_paths),
        "gt_poison_evaluation_changed": evaluated_changes,
        "comparisons": comparisons,
        "termination_status": "PASS" if all(event.termination_reason.value == "COMPLETE"
                                               for event in all_events) else "FAIL",
        "scope": "READY_REVIEWED_CASES_ONLY_CASE2_REMAINS_BLOCKED",
        "all_case_exit_complete": False, "freeze_allowed": False,
        "dataset_manifest_sha256": digest(dataset / "manifest.json"),
        "config_sha256": digest(config),
    }
    require_inference_freeze(primary)
    write_json(output / "verification.json", result)
    return result
