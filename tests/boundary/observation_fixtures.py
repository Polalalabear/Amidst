"""Readable frame descriptors for synthetic observation-boundary fixtures only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.observation import ProjectedPoint
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import (
    AggregationPolicy,
    BoundGapEvent,
    ObservationAggregation,
    OcclusionState,
    RawProjectedFrameSample,
    StreamBinding,
)
from amidst.events import reconstruct_gaps
from amidst.observation import aggregate_frames

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "mock" / "boundary"
SOURCE = StreamBinding(
    source_id="SYNTHETIC:observation_boundaries",
    spatial_context_id="SYNTHETIC:observation_boundaries",
    source_asset_sha256="e" * 64,
)
POSITIONS = {"CAM_A": (0, 0, 0), "CAM_B": (0.02, 0, 0), "CAM_C": (0.04, 0, 0)}


def cases(*names: str) -> list[dict[str, Any]]:
    payload = json.loads((FIXTURES / "observation_scenarios.json").read_text())
    selected = [case for case in payload["scenarios"] if case["scenario_id"] in names]
    assert {case["scenario_id"] for case in selected} == set(names)
    return selected


def samples(case: dict[str, Any]) -> tuple[RawProjectedFrameSample, ...]:
    result = []
    for descriptor in case["input"]["samples"]:
        visible = descriptor.get("visibility", "OBSERVED") == "OBSERVED"
        identity = descriptor["sample_id"]
        camera = descriptor["camera_id"]
        timestamp = descriptor["timestamp"]
        result.append(
            RawProjectedFrameSample(
                **SOURCE.model_dump(),
                sample_id=identity,
                target_id="SYNTHETIC:boundary_target",
                camera_id=camera,
                timestamp=timestamp,
                frame_id=descriptor["frame_id"],
                uv=(32, 24) if visible else None,
                visibility=VisibilityStatus.OBSERVED if visible else VisibilityStatus.GAP,
                occlusion_state=OcclusionState.CLEAR if visible else OcclusionState.UNKNOWN,
                provenance=Provenance.OBSERVED if visible else None,
                projected_point=ProjectedPoint(
                    point_id=f"{identity}:point",
                    camera_id=camera,
                    timestamp=timestamp,
                    plane_id="SYNTHETIC:floor_1F",
                    floor_id="1F",
                    world_position=POSITIONS[camera],
                ) if visible else None,
                gap_reason=None if visible else GapReason(descriptor["gap_reason"]),
            )
        )
    return tuple(result)


def pipeline() -> PipelineConfig:
    return PipelineConfig.model_validate_json(
        (FIXTURES / "observation_pipeline.json").read_text()
    )


def run(
    case: dict[str, Any],
    stream: tuple[RawProjectedFrameSample, ...] | None = None,
) -> tuple[ObservationAggregation, tuple[BoundGapEvent, ...]]:
    policy = AggregationPolicy.model_validate(case["input"].get("aggregation_policy", {}))
    aggregation = aggregate_frames(samples(case) if stream is None else stream, policy)
    gaps = reconstruct_gaps(
        aggregation, pipeline(), dataset_id="SYNTHETIC:observation_boundaries",
        random_seed=20261002, clock=lambda: 0.0,
    )
    return aggregation, gaps


def assert_expected(
    case: dict[str, Any],
    aggregation: ObservationAggregation,
    gaps: tuple[BoundGapEvent, ...],
) -> None:
    expected = case["expected"]
    assert [list(item.sample_ids) for item in aggregation.observations] == expected["segments"]
    assert [list(gap.event.time_range) for gap in gaps] == expected["event_time_ranges"]
    assert [len(gap.event.candidates) for gap in gaps] == expected["candidates_per_gap"]
    assert [gap.event.termination_reason.value for gap in gaps] == expected["termination"]
    assert [list(gap.search_result.rejection_reasons) for gap in gaps] == (
        expected["rejected_transitions"]
    )
    assert all(gap.binding == SOURCE for gap in gaps)
    assert all(item.binding == SOURCE for item in aggregation.observations)
    assert all(
        item.observation.provenance.value == expected["provenance"]["observations"]
        for item in aggregation.observations
    )
    assert all(
        frame.provenance is not None
        and frame.provenance.value == expected["provenance"]["visible_pixels"]
        for item in aggregation.observations for frame in item.observation.frames
    )
    assert all(
        sample.provenance == expected["provenance"]["explicit_gap"]
        and sample.projected_point is None and sample.uv is None
        for sample in aggregation.samples if sample.visibility == VisibilityStatus.GAP
    )
    for gap in gaps:
        assert gap.search_result.complete
        assert gap.event.candidates == gap.search_result.candidates
        assert all(
            candidate.provenance.value == expected["provenance"]["candidates"]
            and candidate.path_score is None
            for candidate in gap.event.candidates
        )
        assert all(
            hypothesis.timed_points[0].provenance == Provenance.PROJECTED
            and hypothesis.timed_points[-1].provenance == Provenance.PROJECTED
            and hypothesis.provenance == Provenance.INFERRED_GAP
            for hypothesis in gap.event.trajectories
        )
    # These fixtures do not supply truth or invoke the evaluation consumer.
    assert expected["metric_behavior"] == "NOT_REQUESTED_NO_GT"
    assert expected["state"] == "SUCCESS"
