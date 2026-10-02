"""Speed and timestamp adversaries are rejected before path interpolation."""

from itertools import pairwise

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance
from amidst.domain.trajectory import TerminationReason
from amidst.graph.engine import GraphInputError, GraphInputFailure

from .graph_cases import graph_case_spec, infer_graph_case, load_graph_case


@pytest.mark.parametrize("case_id", ["insufficient_travel_time", "speed_limit_violation"])
def test_speed_invalid_route_never_reaches_reconstruction(case_id: str) -> None:
    expected = graph_case_spec(case_id)["expected"]
    results = [infer_graph_case(case_id) for _ in range(3)]
    assert results[0] == results[1] == results[2]
    result, event = results[0]
    assert result.candidates == event.candidates == event.trajectories == ()
    assert result.termination_reason == event.termination_reason == (
        TerminationReason.NO_FEASIBLE_PATH
    )
    assert result.complete
    assert result.rejection_reasons == tuple(expected["rejected_transitions"])
    assert result.expanded_nodes == expected["expanded_nodes"]


def test_exact_minimum_time_has_no_negative_slack_or_speed_violation() -> None:
    inputs = load_graph_case("exact_minimum_travel_time")
    result, event = infer_graph_case("exact_minimum_travel_time")
    assert result.termination_reason == TerminationReason.COMPLETE and result.complete
    assert len(result.candidates) == len(event.trajectories) == 1
    candidate = result.candidates[0]
    assert candidate.minimum_travel_time == candidate.estimated_travel_time == 20
    assert candidate.temporal_cost == 0
    assert candidate.path_length / candidate.estimated_travel_time == inputs.movement.max_speed_m_s
    assert candidate.provenance == Provenance.INFERRED_GAP
    assert all(after.timestamp > before.timestamp for trajectory in event.trajectories
               for before, after in pairwise(trajectory.timed_points))


@pytest.mark.parametrize("case_id", ["reverse_gap", "zero_duration_gap"])
def test_reverse_or_zero_endpoint_gap_has_deterministic_typed_rejection(case_id: str) -> None:
    expected = graph_case_spec(case_id)["expected"]
    failures = []
    for _ in range(3):
        with pytest.raises(GraphInputError, match=expected["error_message"]) as captured:
            infer_graph_case(case_id)
        failures.append((captured.value.failure, str(captured.value)))
    assert failures[0] == failures[1] == failures[2]
    assert failures[0][0] == GraphInputFailure.INVALID_TIME_GAP
    assert expected["termination"] is None


@pytest.mark.parametrize("case_id", [
    "duplicate_projected_timestamp", "nonmonotonic_projected_timestamps",
])
def test_duplicate_or_nonmonotonic_evidence_fails_schema_before_graph(case_id: str) -> None:
    expected = graph_case_spec(case_id)["expected"]
    errors = []
    for _ in range(3):
        with pytest.raises(ValidationError, match=expected["error_message"]) as captured:
            load_graph_case(case_id)
        errors.append(captured.value.errors(include_url=False, include_context=False))
    assert errors[0] == errors[1] == errors[2]
