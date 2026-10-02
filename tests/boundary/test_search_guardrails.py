"""Tiny branching cycles prove bounded work even for very long blind gaps."""

import time

import pytest

from amidst.domain.trajectory import TerminationReason

from .graph_cases import graph_case_spec, infer_graph_case, load_graph_case


@pytest.mark.parametrize("case_id", [
    "search_node_limit", "branch_factor_limit", "branch_limit_after_feasible_candidate",
    "fixed_clock_timeout",
    "long_gap_twenty_minutes", "long_gap_one_hour", "maximum_path_length_boundary",
])
def test_search_protection_matches_exact_fixture_boundary(case_id: str) -> None:
    expected = graph_case_spec(case_id)["expected"]
    started = time.monotonic()
    repeated = [infer_graph_case(case_id) for _ in range(5)]
    elapsed = time.monotonic() - started
    assert repeated.count(repeated[0]) == 5
    result, event = repeated[0]
    assert result.expanded_nodes == expected["expanded_nodes"]
    assert result.termination_reason == TerminationReason(expected["termination"])
    assert result.complete == expected["complete"]
    assert result.rejection_reasons == tuple(expected["rejected_transitions"])
    assert [list(candidate.navmesh_corridor) for candidate in result.candidates] == (
        expected["candidates"]
    )
    assert event.candidates == result.candidates
    # Deliberately generous smoke guard; exact expanded-state assertions above
    # establish algorithmic work independently of machine speed.
    assert elapsed < 5.0


@pytest.mark.parametrize("case_id,gap_s", [
    ("long_gap_twenty_minutes", 1200), ("long_gap_one_hour", 3600),
])
def test_long_gap_uses_small_graph_and_finite_explicit_search_policy(
    case_id: str, gap_s: int,
) -> None:
    inputs = load_graph_case(case_id)
    assert inputs.end_observation.start_time - inputs.start_observation.end_time == gap_s
    assert len(inputs.navigation.nodes) == 3 and len(inputs.navigation.edges) == 4
    assert len(inputs.topology.transitions) == 4
    result, event = infer_graph_case(case_id)
    assert result.expanded_nodes <= inputs.search_policy.max_search_nodes
    assert result.candidates == event.candidates == event.trajectories == ()


@pytest.mark.parametrize("case_id", [
    "search_node_limit", "branch_limit_after_feasible_candidate", "fixed_clock_timeout",
])
def test_incomplete_search_preserves_only_already_proven_feasible_candidates(case_id: str) -> None:
    result, event = infer_graph_case(case_id)
    assert len(result.candidates) == 1 and not result.complete
    assert result.candidates[0].navmesh_corridor == ("route_a",)
    assert {trajectory.candidate_id for trajectory in event.trajectories} == {
        result.candidates[0].candidate_id,
    }
