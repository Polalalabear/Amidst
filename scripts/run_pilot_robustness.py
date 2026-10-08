"""Controlled PILOT inference with preserved prefixes and explicit failure states.

Only strict 2D observations, strict projection context and six-key numeric scenario
configuration are accepted. No truth, mixed dataset, trajectory plan or assets
are read. Ordinary successful inference delegates to the existing pilot runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from itertools import groupby
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, FiniteFloat, ValidationError

from amidst.datasets.pilot import (
    PILOT_LABEL,
    PilotInferenceContext,
    PilotObservationExport,
    project_pilot_observations,
    run_pilot_downstream,
)
from amidst.datasets.pilot_topology import build_pilot_pipeline
from amidst.datasets.providers import BlenderDataset
from amidst.domain.common import DomainModel
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import VisibilityStatus
from amidst.domain.stream import ObservationAggregation
from amidst.geometry.inverse_projection import InverseProjectionError
from amidst.storage.json_files import write_json

INFERENCE_FILES = (
    "projected_frames.json", "aggregation.json", "pipeline_config.json",
    "topology_evidence.json", "gap_events.json", "candidates.json", "events.json",
    "inference_report.json", "inference_report.md", "digests.json",
    "robustness_status.json", "robustness_report.md",
)
STAGES = (
    "SCENARIO_CONFIG", "INPUT_CONTEXT", "INPUT_OBSERVATIONS", "INPUT_BINDING",
    "PROJECTION", "AGGREGATION", "TOPOLOGY", "SEARCH", "RECONSTRUCTION",
)
FORBIDDEN_INPUT_NAMES = frozenset({
    "dataset.json", "ground_truth.json", "trajectory_plan.json",
    "evaluation_gt.json", "evaluation_gap_gt.json",
})
PositiveSetting = Annotated[FiniteFloat, Field(gt=0, strict=True)]


class RobustnessScenario(DomainModel):
    label: Literal["PILOT / SYNTHETIC SAMPLE"]
    scenario_id: str = Field(min_length=1)
    lateral_offset_scene_units: PositiveSetting
    max_speed_scene_units_s: PositiveSetting
    max_candidate_paths: int = Field(ge=1, le=3, strict=True)
    random_seed: int = Field(strict=True)


# Repository tools are also loaded through importlib without sys.modules registration.
RobustnessScenario.model_rebuild(_types_namespace=globals())


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _safe_input(path: Path) -> bytes:
    if path.name in FORBIDDEN_INPUT_NAMES:
        raise ValueError("mixed simulation/truth/plan files are forbidden consumer inputs")
    return path.read_bytes()


def _error_fields(error: Exception) -> list[str]:
    if not isinstance(error, ValidationError):
        return []
    return sorted({
        ".".join(str(item) for item in row["loc"])
        for row in error.errors(include_input=False, include_context=False)
    })


def _untrusted_binding(content: bytes) -> dict[str, Any]:
    try:
        value = json.loads(content)
    except (ValueError, UnicodeDecodeError):
        return {"validated": False}
    if not isinstance(value, dict):
        return {"validated": False}
    result: dict[str, Any] = {"validated": False}
    for key in ("source_asset_sha256", "source_id", "spatial_context_id", "site_id"):
        if isinstance(value.get(key), str):
            result[key] = value[key]
    return result


def run_robustness(
    observations_path: Path, context_path: Path, output_directory: Path,
    scenario_config_path: Path,
) -> dict[str, Any]:
    """Persist only completed stages; a missing endpoint never becomes a fake gap."""
    if output_directory.exists():
        raise FileExistsError(output_directory)
    if any(path.name in FORBIDDEN_INPUT_NAMES for path in
           (observations_path, context_path, scenario_config_path)):
        raise ValueError("mixed simulation/truth/plan files are forbidden consumer inputs")
    scenario_bytes = _safe_input(scenario_config_path)
    scenario = RobustnessScenario.model_validate_json(scenario_bytes)
    observation_bytes, context_bytes = _safe_input(observations_path), _safe_input(context_path)
    digests = {
        "observations_sha256": _sha(observation_bytes),
        "context_sha256": _sha(context_bytes),
        "scenario_config_sha256": _sha(scenario_bytes),
    }
    states = dict.fromkeys(STAGES, "NOT_RUN")
    states["SCENARIO_CONFIG"] = "PASSED"
    context: PilotInferenceContext | None = None
    observations: PilotObservationExport | None = None
    frames: FrameSampleDataset | None = None
    aggregation: ObservationAggregation | None = None
    status: dict[str, Any] = {
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC",
        "scope": "CONTROLLED_ROBUSTNESS_SYNTHETIC_NOT_FORMAL_CASES_1_3",
        "scenario_id": scenario.scenario_id,
        "scenario": scenario.model_dump(mode="json"),
        "outcome": "EXPECTED_FAILURE", "failed_stage": None, "reason": "NONE",
        "termination_reason": "NOT_RUN", "evaluation_eligible": False,
        "available_artifacts": [], "stage_states": states,
        "candidate_count": 0, "hypothesis_count": 0, "candidate_count_state": "NOT_RUN",
        "raw_sample_count": None, "timestamp_count": None, "observation_count": None,
        "global_gap_timestamp_count": None, "global_gap_timestamps": None,
        "gap_window": None, "gap_window_state": "UNAVAILABLE",
        "search_executed": False, "binding_validated": False,
        "input_digests": digests,
        "physical_validity": {
            "status": "PARTIAL_PROVISIONAL", "mesh_collision_certified": False,
            "physical_scale_authority": "UNVERIFIED",
            "navigation_authority": "ANNOTATION_AABB_ONLY_PROVISIONAL",
        },
        "ground_truth_read": False, "formal_benchmark_executed": False,
    }
    stage = "INPUT_CONTEXT"
    try:
        context = PilotInferenceContext.model_validate_json(context_bytes)
        states[stage] = "PASSED"
        status.update(
            source_asset_sha256=context.source_asset_sha256,
            source_id=context.source_id, spatial_context_id=context.spatial_context_id,
            site_id=context.site_id,
        )
        stage = "INPUT_OBSERVATIONS"
        observations = PilotObservationExport.model_validate_json(observation_bytes)
        states[stage] = "PASSED"
        status["target_id"] = observations.frames[0].target_id
        status["raw_sample_count"] = len(observations.frames)
        status["timestamp_count"] = len({row.timestamp for row in observations.frames})
        stage = "INPUT_BINDING"
        if (
            digests["observations_sha256"] != context.observations_sha256
            or observations.source_asset_sha256 != context.source_asset_sha256
            or observations.site_id != context.site_id
        ):
            raise ValueError("content/source/site binding differs")
        states[stage] = "PASSED"
        status["binding_validated"] = True
        stage = "PROJECTION"
        frames = project_pilot_observations(observations, context)
        states[stage] = "PASSED"
        status["projected_observed_count"] = sum(
            sample.visibility == VisibilityStatus.OBSERVED for sample in frames.samples
        )
        status["gap_without_projection_count"] = sum(
            sample.visibility == VisibilityStatus.GAP for sample in frames.samples
        )
        stage = "AGGREGATION"
        provider = BlenderDataset(frames, context.binding)
        aggregation = provider.aggregate(provider.time_range)
        states[stage] = "PASSED"
        status["observation_count"] = len(aggregation.observations)
        gap_times = [
            timestamp for timestamp, samples in
            groupby(aggregation.samples, key=lambda sample: sample.timestamp)
            if not any(sample.visibility == VisibilityStatus.OBSERVED for sample in samples)
        ]
        status["global_gap_timestamps"] = gap_times
        status["global_gap_timestamp_count"] = len(gap_times)
        if len(aggregation.observations) == 2:
            first, last = sorted(aggregation.observations,
                                 key=lambda bound: bound.observation.start_time)
            if first.observation.end_time < last.observation.start_time:
                status["gap_window"] = (
                    first.observation.end_time, last.observation.start_time,
                )
                status["gap_window_state"] = "PROJECTED_OBSERVATION_ENDPOINTS"
        stage = "TOPOLOGY"
        build_pilot_pipeline(
            aggregation, context,
            lateral_offset_scene_units=scenario.lateral_offset_scene_units,
            max_speed_scene_units_s=scenario.max_speed_scene_units_s,
            max_candidate_paths=scenario.max_candidate_paths,
        )
        states[stage] = "PASSED"
    except ValueError as error:
        states[stage] = "FAILED"
        reason = "INVALID_INPUT"
        if stage == "TOPOLOGY":
            same_camera = (
                aggregation is not None and len(aggregation.observations) == 2
                and aggregation.observations[0].observation.camera_id
                == aggregation.observations[1].observation.camera_id
            )
            reason = "UNSUPPORTED_SAME_CAMERA" if same_camera else "PROVISIONAL_TOPOLOGY_REJECTED"
        elif isinstance(error, InverseProjectionError):
            reason = error.failure.value
        status.update(failed_stage=stage, reason=reason, validation_fields=_error_fields(error))
        if context is None:
            status["untrusted_binding"] = _untrusted_binding(context_bytes)
        output_directory.mkdir(parents=True, exist_ok=False)
        protected = (observations_path, context_path, scenario_config_path)
        if frames is not None:
            write_json(output_directory / "projected_frames.json", {
                "label": PILOT_LABEL, "dataset": frames.model_dump(mode="json"),
            }, protected_inputs=protected)
        if aggregation is not None:
            write_json(output_directory / "aggregation.json", {
                "label": PILOT_LABEL, "aggregation": aggregation.model_dump(mode="json"),
            }, protected_inputs=protected)
    else:
        # Full ordinary runner remains unchanged and retains its own input guards.
        run = run_pilot_downstream(
            observations_path, context_path, output_directory,
            lateral_offset_scene_units=scenario.lateral_offset_scene_units,
            max_speed_scene_units_s=scenario.max_speed_scene_units_s,
            max_candidate_paths=scenario.max_candidate_paths, random_seed=scenario.random_seed,
        )
        result = run.gaps[0].search_result
        hypotheses = run.gaps[0].event.trajectories
        states["SEARCH"] = "PASSED" if result.candidates else "COMPLETED_WITHOUT_CANDIDATES"
        states["RECONSTRUCTION"] = "PASSED" if hypotheses else "COMPLETED_EMPTY_EVENT"
        status.update(
            outcome="SUCCESS" if hypotheses else "EXPECTED_FAILURE",
            failed_stage=None if hypotheses else "SEARCH",
            reason="NONE" if hypotheses else result.termination_reason.value,
            termination_reason=result.termination_reason.value,
            evaluation_eligible=bool(hypotheses), search_executed=True,
            candidate_count=len(result.candidates), hypothesis_count=len(hypotheses),
            candidate_count_state="SEARCH_RESULT", enumeration_complete=result.complete,
        )
    status["available_artifacts"] = sorted({
        path.name for path in output_directory.iterdir() if path.is_file()
    } | {"robustness_status.json", "robustness_report.md"})
    write_json(output_directory / "robustness_status.json", status,
               protected_inputs=(observations_path, context_path, scenario_config_path))
    (output_directory / "robustness_report.md").write_text("\n".join([
        f"# {PILOT_LABEL} — controlled robustness", "",
        f"Scenario: `{scenario.scenario_id}`. Outcome: `{status['outcome']}`.",
        f"Stage: `{status['failed_stage']}`; reason: `{status['reason']}`; "
        f"termination: `{status['termination_reason']}`.",
        f"Candidate count: {status['candidate_count']} ({status['candidate_count_state']}); "
        f"hypotheses: {status['hypothesis_count']}; evaluation eligible: "
        f"{status['evaluation_eligible']}.",
        "Only completed prefixes are saved. No GT, mixed dataset, trajectory plan, render "
        "or formal benchmark was consumed. Physical/mesh authority remains provisional.", "",
    ]), encoding="utf-8")
    return status


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="fresh output directory")
    parser.add_argument("--scenario-config", type=Path, required=True)
    args = parser.parse_args()
    status = run_robustness(args.observations, args.context, args.output, args.scenario_config)
    print(json.dumps({key: status[key] for key in (
        "label", "scenario_id", "outcome", "failed_stage", "reason", "termination_reason",
        "candidate_count", "hypothesis_count", "evaluation_eligible",
    )}, sort_keys=True))


if __name__ == "__main__":
    main()
