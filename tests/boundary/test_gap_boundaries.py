"""Threshold edges, short recovery and absent frames preserve supplied evidence."""

from __future__ import annotations

from typing import Any

import pytest

from amidst.domain.common import Provenance
from amidst.domain.evidence import VisibilityStatus
from amidst.domain.stream import OcclusionState
from amidst.observation import InMemoryRawFrameProvider, aggregate_frames

from .observation_fixtures import SOURCE, assert_expected, cases, run, samples


@pytest.mark.parametrize(
    "case", cases("threshold_below", "threshold_equal", "threshold_above"),
    ids=lambda case: case["scenario_id"],
)
def test_sampling_threshold_is_strictly_greater_and_does_not_invent_lost_frames(
    case: dict[str, Any],
) -> None:
    aggregation, gaps = run(case)
    assert_expected(case, aggregation, gaps)
    assert len(aggregation.samples) == 2
    assert all(sample.visibility == VisibilityStatus.OBSERVED for sample in aggregation.samples)
    # Just above the sampling threshold creates a stationary candidate, not a detour.
    for gap in gaps:
        assert gap.event.candidates[0].path_length == 0
        assert len(gap.event.trajectories) == 1


@pytest.mark.parametrize(
    "case", cases("explicit_short_gap_1_frames", "explicit_short_gap_2_frames"),
    ids=lambda case: case["scenario_id"],
)
def test_one_or_two_missing_visibility_frames_still_split_at_explicit_gap(
    case: dict[str, Any],
) -> None:
    aggregation, gaps = run(case)
    assert_expected(case, aggregation, gaps)
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap.event.candidates[0].navmesh_corridor == ("AB",)
    assert gap.event.candidates[0].path_length == 0.02
    assert len(gap.event.trajectories) <= 2
    assert all(len(hypothesis.timed_points) <= 3 for hypothesis in gap.event.trajectories)
    assert all(
        sample.uv is None and sample.projected_point is None and sample.provenance is None
        for sample in aggregation.samples if sample.visibility == VisibilityStatus.GAP
    )


@pytest.mark.parametrize(
    "case", cases("single_frame_recovery", "two_frame_recovery"),
    ids=lambda case: case["scenario_id"],
)
def test_adjacent_gaps_keep_single_or_brief_recovery_and_independent_endpoints(
    case: dict[str, Any],
) -> None:
    aggregation, gaps = run(case)
    assert_expected(case, aggregation, gaps)
    first, second = gaps
    recovery = aggregation.observations[1]
    assert first.end == recovery == second.start
    assert first.event.event_id != second.event.event_id
    assert first.event.observation_ids[1] == second.event.observation_ids[0]
    assert first.event.candidates[0].navmesh_corridor == ("AB",)
    assert second.event.candidates[0].navmesh_corridor == ("BC",)
    visible_ids = {
        sample.sample_id for sample in aggregation.samples
        if sample.visibility == VisibilityStatus.OBSERVED
    }
    segment_ids = [sample_id for item in aggregation.observations for sample_id in item.sample_ids]
    assert len(segment_ids) == len(set(segment_ids))
    assert set(segment_ids) == visible_ids
    assert recovery.binding == first.binding == second.binding == SOURCE


def test_camera_dropout_remains_absence_without_occlusion_or_fov_classification() -> None:
    case = cases("missing_camera_frames")[0]
    stream = samples(case)
    provider = InMemoryRawFrameProvider(stream)
    missing_range = tuple(case["input"]["absent_interval"])
    assert provider.get_frame_samples(None, missing_range) == ()
    assert provider.get_frame_samples("CAM_A", missing_range) == ()
    aggregation, gaps = run(case)
    assert_expected(case, aggregation, gaps)
    assert tuple(sample.sample_id for sample in aggregation.samples) == ("a0", "b0")
    assert sum(len(item.observation.frames) for item in aggregation.observations) == 2
    assert all(
        sample.visibility == VisibilityStatus.OBSERVED
        and sample.provenance == Provenance.OBSERVED
        and sample.occlusion_state == OcclusionState.CLEAR
        and sample.gap_reason is None
        and sample.occluder_id is None
        for sample in aggregation.samples
    )
    # Empty provider query is also a valid aggregation, with no fabricated evidence.
    empty = aggregate_frames(provider.get_frame_samples(None, missing_range))
    assert empty.samples == empty.observations == ()
    _, missing_gaps = run(case, ())
    assert missing_gaps == ()


@pytest.mark.parametrize(
    "case", cases("missing_same_camera_default", "missing_same_camera_threshold"),
    ids=lambda case: case["scenario_id"],
)
def test_absent_same_camera_frames_split_only_under_explicit_sampling_policy(
    case: dict[str, Any],
) -> None:
    aggregation, gaps = run(case)
    assert_expected(case, aggregation, gaps)
    assert tuple(sample.frame_id for sample in aggregation.samples) == (0, 30)
    assert all(sample.gap_reason is None for sample in aggregation.samples)
    assert all(sample.occlusion_state == OcclusionState.CLEAR for sample in aggregation.samples)
