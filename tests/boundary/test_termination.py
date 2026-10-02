"""Minimal fixtures cover every current reason without inventing Agent reasons."""

import pytest

from amidst.domain.trajectory import TerminationReason

from .graph_cases import graph_manifest, infer_graph_case

TERMINATION_CASES = {
    "exact_minimum_travel_time": TerminationReason.COMPLETE,
    "uncited_navigation_bridge": TerminationReason.NO_FEASIBLE_PATH,
    "eight_routes_k3": TerminationReason.MAX_PATHS_REACHED,
    "search_node_limit": TerminationReason.MAX_SEARCH_NODES,
    "branch_factor_limit": TerminationReason.MAX_BRANCH_FACTOR,
    "fixed_clock_timeout": TerminationReason.SEARCH_TIMEOUT,
}


@pytest.mark.parametrize("case_id,expected_reason", TERMINATION_CASES.items())
def test_supported_search_reason_propagates_to_event(
    case_id: str, expected_reason: TerminationReason,
) -> None:
    first = infer_graph_case(case_id)
    assert infer_graph_case(case_id) == first
    result, event = first
    assert result.termination_reason == event.termination_reason == expected_reason
    assert result.complete == (expected_reason in {
        TerminationReason.COMPLETE, TerminationReason.NO_FEASIBLE_PATH,
    })
    assert event.candidates == result.candidates
    assert {trajectory.candidate_id for trajectory in event.trajectories} == {
        candidate.candidate_id for candidate in result.candidates
    }


def test_coverage_matches_current_enum_and_explicitly_excludes_future_concerns() -> None:
    assert set(TERMINATION_CASES.values()) == set(TerminationReason)
    manifest = graph_manifest()
    assert set(manifest["future_scope"]["agent_runtime_only"]) == {
        "LOW_CONFIDENCE", "TOOL_BUDGET_EXCEEDED", "USER_TERMINATED",
    }
    assert set(manifest["future_scope"]["unsupported_termination"]) == {
        "COMPLETE_EVENT", "SEARCH_WINDOW_EXCEEDED", "MAX_HOPS_EXCEEDED",
    }


def test_each_fake_graph_scenario_declares_all_requested_expected_contract_fields() -> None:
    manifest = graph_manifest()
    assert manifest["data_kind"] == "SYNTHETIC_TEST_FIXTURE"
    assert len({case["id"] for case in manifest["scenarios"]}) == len(manifest["scenarios"])
    for case in manifest["scenarios"]:
        assert case["input"] and case["purpose"]
        assert set(case["expected"]) >= {
            "candidates", "termination", "rejected_transitions", "provenance",
            "metric_behavior", "state", "complete",
        }
        assert case["expected"]["provenance"] == {
            "endpoints": "PROJECTED", "candidates": "INFERRED_GAP",
            "fabricated_observations": False,
        }
