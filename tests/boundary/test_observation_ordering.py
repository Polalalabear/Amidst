"""Reject duplicate evidence and normalize order before any Event search."""

from __future__ import annotations

from itertools import permutations
from typing import Any

import pytest
from pydantic import ValidationError

import amidst.events.aggregation as event_module
from amidst.domain.observation import Observation
from amidst.events import EventAggregationError
from amidst.observation import AggregationInputError, InMemoryRawFrameProvider, aggregate_frames

from .observation_fixtures import assert_expected, cases, run, samples


@pytest.mark.parametrize(
    "case",
    cases("duplicate_exact", "duplicate_camera_timestamp", "duplicate_source_frame"),
    ids=lambda case: case["scenario_id"],
)
def test_duplicate_evidence_fails_closed_before_event_search(
    case: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_search(*args: object, **kwargs: object) -> None:
        raise AssertionError("duplicate observations must never reach Graph inference")

    monkeypatch.setattr(event_module, "reconstruct_input", forbidden_search)
    stream = samples(case)
    for ordered in (stream, tuple(reversed(stream))):
        with pytest.raises(AggregationInputError, match=case["expected"]["error"]):
            run(case, ordered)
        # Providers enforce the same policy rather than silently deduplicating.
        with pytest.raises(AggregationInputError, match="duplicate"):
            InMemoryRawFrameProvider(ordered)
    assert case["expected"]["state"] == "REJECTED"
    assert case["expected"]["metric_behavior"] == "NOT_RUN_INPUT_REJECTED"


def test_all_permutations_preserve_observation_event_candidate_and_timing_ids() -> None:
    case = cases("out_of_order")[0]
    stream = samples(case)
    aggregation, gaps = run(case)
    assert_expected(case, aggregation, gaps)
    snapshot = (aggregation.model_dump_json(), tuple(gap.model_dump_json() for gap in gaps))
    # Five records = 120 small permutations, no randomized order or random seed state.
    for permutation in permutations(stream):
        reordered, inferred = run(case, permutation)
        assert (reordered.model_dump_json(), tuple(gap.model_dump_json() for gap in inferred)) == (
            snapshot
        )
    candidates = [candidate.candidate_id for gap in gaps for candidate in gap.event.candidates]
    assert len(set(candidates)) == len(candidates)


@pytest.mark.parametrize(
    "case", cases("zero_duration_camera_handoff"), ids=lambda case: case["scenario_id"],
)
def test_simultaneous_camera_endpoints_are_rejected_before_zero_duration_search(
    case: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_search(*args: object, **kwargs: object) -> None:
        raise AssertionError("zero-duration handoff must never reach Graph inference")

    monkeypatch.setattr(event_module, "reconstruct_input", forbidden_search)
    for stream in (samples(case), tuple(reversed(samples(case)))):
        with pytest.raises(EventAggregationError, match=case["expected"]["error"]):
            run(case, stream)


@pytest.mark.parametrize(
    "case", cases(
        "reverse_extent", "duplicate_projected_time", "reverse_projected_order",
        "reverse_frame_order",
    ), ids=lambda case: case["scenario_id"],
)
def test_observation_time_schema_rejects_reverse_and_nonmonotonic_evidence(
    case: dict[str, Any],
) -> None:
    observation = aggregate_frames(samples(case)).observations[0].observation
    payload = observation.model_dump(mode="python")
    mutation = case["input"]["observation_mutation"]
    if mutation == "reverse_extent":
        payload.update(start_time=1, end_time=0)
    elif mutation == "duplicate_projected_time":
        payload["projected_path"][1]["timestamp"] = payload["projected_path"][0]["timestamp"]
    elif mutation == "reverse_projected_order":
        payload["projected_path"] = tuple(reversed(payload["projected_path"]))
    else:
        payload["frames"] = tuple(reversed(payload["frames"]))
    for _ in range(3):
        with pytest.raises(ValidationError, match=case["expected"]["error"]):
            Observation.model_validate(payload)


def test_single_visible_frame_is_valid_but_does_not_create_a_zero_duration_gap() -> None:
    case = cases("zero_duration_visible_segment")[0]
    recovery = samples(case)[0]
    aggregation, gaps = run(case)
    assert_expected(case, aggregation, gaps)
    assert len(aggregation.observations) == 1
    assert aggregation.observations[0].observation.start_time == recovery.timestamp
    assert aggregation.observations[0].observation.end_time == recovery.timestamp
    assert gaps == ()
