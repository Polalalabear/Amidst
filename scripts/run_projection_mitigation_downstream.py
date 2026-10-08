"""GT-free diagnostic projection availability adapter for ordinary pilot consumers.

The caller retains original 2D evidence separately. A rejected projection is an
availability GAP (GEOMETRY_UNCERTAIN / UNKNOWN), never asserted physical occlusion.
This module changes no accepted coordinate, quality, Graph, Top-K or metric policy.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from itertools import groupby
from pathlib import Path
from typing import Any

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext
from amidst.datasets.pilot_topology import build_pilot_pipeline
from amidst.datasets.providers import BlenderDataset
from amidst.domain.common import DomainModel
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.stream import ObservationAggregation, OcclusionState, RawProjectedFrameSample
from amidst.events import reconstruct_gaps
from amidst.observation.aggregation import aggregate_frames, validate_stream_model
from amidst.storage.json_files import write_json

SampleKey = tuple[str, int, float]
SCOPE = "PILOT_PROJECTION_CONDITIONING_MITIGATION_NOT_FORMAL_CASES_1_3"


def _load_existing_runner() -> Any:
    spec = importlib.util.spec_from_file_location(
        "mitigation_existing_robustness", Path(__file__).with_name("run_pilot_robustness.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("existing bounded pilot robustness runner is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


robustness = _load_existing_runner()
INFERENCE_FILES = robustness.INFERENCE_FILES


def _key(sample: RawProjectedFrameSample) -> SampleKey:
    return sample.camera_id, sample.frame_id, float(sample.timestamp)


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _model_digest(model: DomainModel) -> str:
    return hashlib.sha256(_json_bytes(model.model_dump(mode="json"))).hexdigest()


def adapt_projected_frames(
    original_dataset: FrameSampleDataset, decisions: dict[SampleKey, bool],
) -> FrameSampleDataset:
    """Accept/reject every visible projection while preserving every original GAP.

    Keys must exactly cover visible samples and values must be literal booleans.
    Rejecting never removes a timestamp, invents a pixel/world point, or supplies
    an occluder. The caller must retain original evidence outside this adapter.
    """
    dataset = validate_stream_model(original_dataset, FrameSampleDataset)
    canonical = aggregate_frames(dataset.samples).samples
    keys = {_key(row) for row in canonical if row.visibility == VisibilityStatus.OBSERVED}
    if len(keys) != sum(row.visibility == VisibilityStatus.OBSERVED for row in canonical):
        raise ValueError("visible projection decision keys must be unique")
    if type(decisions) is not dict or set(decisions) != keys:
        raise ValueError("projection decisions must cover exactly the observed sample identities")
    if any(type(accepted) is not bool for accepted in decisions.values()):
        raise ValueError("projection decisions must use strict boolean acceptance")
    samples = []
    for row in canonical:
        if row.visibility == VisibilityStatus.OBSERVED:
            if row.projected_point is None:
                raise ValueError("visible adapter inputs require actual projected points")
            if not decisions[_key(row)]:
                value = row.model_dump(mode="python")
                value.update(
                    visibility=VisibilityStatus.GAP, uv=None, provenance=None,
                    projected_point=None, confidence=None, gap_reason=GapReason.GEOMETRY_UNCERTAIN,
                    occlusion_state=OcclusionState.UNKNOWN, occluder_id=None,
                )
                row = RawProjectedFrameSample.model_validate(value)
        samples.append(row)
    return FrameSampleDataset(samples=aggregate_frames(tuple(samples)).samples)


def _scenario(scenario: DomainModel) -> Any:
    # A parent orchestration tool can load the existing script under another
    # importlib module identity. Recheck that exact object's nested contract first,
    # then validate the original six-key scenario schema independently.
    if not isinstance(scenario, DomainModel):
        raise ValueError("scenario must use the existing strict numeric scenario model")
    checked = validate_stream_model(scenario, type(scenario))
    return robustness.RobustnessScenario.model_validate(checked.model_dump(mode="python"))


def _binding(dataset: FrameSampleDataset, context: PilotInferenceContext) -> None:
    if not dataset.samples or any(row.binding != context.binding for row in dataset.samples):
        raise ValueError("projected frame source/context binding differs from explicit context")
    if {row.camera_id for row in dataset.samples} != {row.camera_id for row in context.cameras}:
        raise ValueError("projected frame cameras differ from configured context")
    if len({row.target_id for row in dataset.samples}) != 1:
        raise ValueError("bounded pilot consumers require exactly one observed target")
    for row in dataset.samples:
        if row.visibility == VisibilityStatus.OBSERVED:
            point = row.projected_point
            if point is None or (
                point.plane_id != context.plane.plane_id
                or point.floor_id != context.zone.floor_id
                or point.zone_id != context.zone.zone_id
            ):
                raise ValueError("accepted projection must preserve plane/floor/zone binding")


def _gap_times(aggregation: ObservationAggregation) -> list[float]:
    return [
        float(timestamp)
        for timestamp, rows in groupby(aggregation.samples, key=lambda row: row.timestamp)
        if not any(row.visibility == VisibilityStatus.OBSERVED for row in rows)
    ]


def _prefix_failure(status: dict[str, Any], reason: str) -> None:
    status.update(failed_stage="TOPOLOGY", reason=reason)
    status["stage_states"]["TOPOLOGY"] = "NOT_RUN"


def run_projected_downstream(
    dataset: FrameSampleDataset, context: PilotInferenceContext,
    scenario: DomainModel, output: Path,
) -> dict[str, Any]:
    """Persist ordinary downstream inference from already projected strict inputs.

    No observation, calibration, truth, plan, asset or original render file is
    read. Invalid mixed inputs raise before output creation. Missing/fragmented
    evidence saves completed prefixes and NOT_RUN search with no fake event.
    Timings deliberately belong to the caller, outside deterministic artifacts.
    """
    if output.exists():
        raise FileExistsError(output)
    dataset = validate_stream_model(dataset, FrameSampleDataset)
    context = validate_stream_model(context, PilotInferenceContext)
    configuration = _scenario(scenario)
    _binding(dataset, context)
    provider = BlenderDataset(dataset, context.binding)
    aggregation = provider.aggregate(provider.time_range)
    canonical_dataset = FrameSampleDataset(samples=aggregation.samples)
    visible = sum(row.visibility == VisibilityStatus.OBSERVED for row in aggregation.samples)
    gaps = _gap_times(aggregation)
    stage_states = dict.fromkeys(robustness.STAGES, "NOT_RUN")
    for stage in robustness.STAGES[:6]:
        stage_states[stage] = "PASSED"
    status: dict[str, Any] = {
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "scope": SCOPE,
        "scenario_id": configuration.scenario_id, "scenario": configuration.model_dump(mode="json"),
        "source_asset_sha256": context.source_asset_sha256, "source_id": context.source_id,
        "spatial_context_id": context.spatial_context_id, "site_id": context.site_id,
        "target_id": aggregation.samples[0].target_id,
        "outcome": "EXPECTED_FAILURE", "failed_stage": None, "reason": "NONE",
        "termination_reason": "NOT_RUN", "evaluation_eligible": False,
        "candidate_count": 0, "hypothesis_count": 0, "candidate_count_state": "NOT_RUN",
        "raw_sample_count": len(aggregation.samples),
        "timestamp_count": len({row.timestamp for row in aggregation.samples}),
        "projected_observed_count": visible,
        "gap_without_projection_count": len(aggregation.samples) - visible,
        "projection_availability_gap_sample_count": sum(
            row.gap_reason == GapReason.GEOMETRY_UNCERTAIN for row in aggregation.samples
        ),
        "projection_rejection_is_physical_occlusion": False,
        "original_2d_evidence_retained_by_caller": True,
        "observation_count": len(aggregation.observations),
        "global_gap_timestamp_count": len(gaps), "global_gap_timestamps": gaps,
        "gap_window": None, "gap_window_state": "UNAVAILABLE",
        "search_executed": False, "binding_validated": True,
        "stage_states": stage_states,
        "input_digests": {
            "projected_dataset_sha256": _model_digest(canonical_dataset),
            "context_sha256": _model_digest(context),
            "scenario_config_sha256": _model_digest(configuration),
        },
        "physical_validity": {
            "status": "PARTIAL_PROVISIONAL", "mesh_collision_certified": False,
            "physical_scale_authority": "UNVERIFIED",
            "navigation_authority": "ANNOTATION_AABB_ONLY_PROVISIONAL",
        },
        "ground_truth_read": False, "formal_benchmark_executed": False,
        "formal_benchmark_semantics_modified": False,
    }
    payloads: dict[str, Any] = {
        "projected_frames.json": {
            "label": PILOT_LABEL, "dataset": canonical_dataset.model_dump(mode="json"),
        },
        "aggregation.json": {
            "label": PILOT_LABEL, "aggregation": aggregation.model_dump(mode="json"),
        },
    }
    count = len(aggregation.observations)
    if count < 2:
        _prefix_failure(status, "INSUFFICIENT_PROJECTED_ENDPOINT_EVIDENCE")
    elif count > 2:
        _prefix_failure(status, "UNSUPPORTED_FRAGMENTED_PROJECTED_EVIDENCE")
    else:
        first, last = sorted(
            aggregation.observations, key=lambda row: row.observation.start_time,
        )
        if first.observation.end_time < last.observation.start_time:
            status.update(
                gap_window=(first.observation.end_time, last.observation.start_time),
                gap_window_state="ACTUAL_RETAINED_PROJECTED_OBSERVATION_ENDPOINTS",
            )
        try:
            pipeline, evidence = build_pilot_pipeline(
                aggregation, context,
                lateral_offset_scene_units=configuration.lateral_offset_scene_units,
                max_speed_scene_units_s=configuration.max_speed_scene_units_s,
                max_candidate_paths=configuration.max_candidate_paths,
            )
        except ValueError as error:
            stage_states["TOPOLOGY"] = "FAILED"
            status.update(
                failed_stage="TOPOLOGY", reason="PROVISIONAL_TOPOLOGY_REJECTED",
                diagnostic_reason=str(error),
            )
        else:
            stage_states["TOPOLOGY"] = "PASSED"
            payloads.update({
                "pipeline_config.json": {
                    "label": PILOT_LABEL, "pipeline": pipeline.model_dump(mode="json"),
                },
                "topology_evidence.json": {"label": PILOT_LABEL, "evidence": evidence},
            })
            reconstructed = reconstruct_gaps(
                aggregation, pipeline, dataset_id=context.source_id,
                random_seed=configuration.random_seed,
            )
            if len(reconstructed) != 1:
                raise ValueError("ordinary bounded consumer requires exactly one independent gap")
            result, event = reconstructed[0].search_result, reconstructed[0].event
            stage_states["SEARCH"] = (
                "PASSED" if result.candidates else "COMPLETED_WITHOUT_CANDIDATES"
            )
            stage_states["RECONSTRUCTION"] = (
                "PASSED" if event.trajectories else "COMPLETED_EMPTY_EVENT"
            )
            status.update(
                outcome="SUCCESS" if event.trajectories else "EXPECTED_FAILURE",
                failed_stage=None if event.trajectories else "SEARCH",
                reason="NONE" if event.trajectories else result.termination_reason.value,
                termination_reason=result.termination_reason.value,
                evaluation_eligible=bool(event.trajectories), search_executed=True,
                candidate_count=len(result.candidates), hypothesis_count=len(event.trajectories),
                candidate_count_state="SEARCH_RESULT", enumeration_complete=result.complete,
            )
            payloads.update({
                "gap_events.json": {
                    "label": PILOT_LABEL,
                    "gaps": [row.model_dump(mode="json") for row in reconstructed],
                },
                "candidates.json": {
                    "label": PILOT_LABEL, "results": [result.model_dump(mode="json")],
                },
                "events.json": {"label": PILOT_LABEL, "events": [event.model_dump(mode="json")]},
                "inference_report.json": {
                    **status,
                    "purpose": "PILOT_DOWNSTREAM_ALREADY_PROJECTED_DIAGNOSTIC_ADAPTER",
                    "camera_ids": [row.camera_id for row in context.cameras],
                    "rejection_reasons": result.rejection_reasons,
                    "configured_max_speed_scene_units_s": configuration.max_speed_scene_units_s,
                    "configured_lateral_offset_scene_units": (
                        configuration.lateral_offset_scene_units
                    ),
                    "configured_max_candidate_paths": configuration.max_candidate_paths,
                    "random_seed": configuration.random_seed,
                },
            })
    output.mkdir(parents=True, exist_ok=False)
    for name, payload in payloads.items():
        write_json(output / name, payload)
    lines = [
        f"# {PILOT_LABEL} — projection mitigation downstream", "",
        f"Scenario: `{configuration.scenario_id}`; outcome `{status['outcome']}`.",
        f"Reason: `{status['reason']}`; termination `{status['termination_reason']}`.",
        f"Accepted projected samples: {visible}; Observation segments: {count}.",
        f"Actual retained endpoint gap: `{status['gap_window']}`.",
        f"Candidates: {status['candidate_count']}; hypotheses: {status['hypothesis_count']}.",
        "Projection availability GAP is GEOMETRY_UNCERTAIN / UNKNOWN, not physical occlusion.",
        "Original 2D evidence is retained separately by the experiment caller.",
        "Graph/Top-K/metrics unchanged; no GT read; physical validity PARTIAL / PROVISIONAL.", "",
    ]
    (output / "robustness_report.md").write_text("\n".join(lines), encoding="utf-8")
    if "inference_report.json" in payloads:
        (output / "inference_report.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(output / "digests.json", {
        "label": PILOT_LABEL, "inputs": status["input_digests"],
        "outputs": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.iterdir()) if path.is_file()
        },
    })
    status["available_artifacts"] = sorted({
        path.name for path in output.iterdir() if path.is_file()
    } | {"robustness_status.json"})
    write_json(output / "robustness_status.json", status)
    return status
