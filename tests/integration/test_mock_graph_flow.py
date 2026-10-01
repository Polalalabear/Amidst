"""All data producers exercise ordinary topology-authorized bounded search."""

from collections.abc import Callable
from pathlib import Path

import pytest

from amidst.domain.common import Provenance
from amidst.domain.observation import Observation
from amidst.domain.pipeline import InferenceInput
from amidst.domain.search import GraphSearchPolicy
from amidst.domain.trajectory import TerminationReason
from amidst.graph.engine import GraphInputError
from amidst.navigation.graph import NavigationGraph
from amidst.navigation.topology import CameraTopologyGraph
from amidst.pipeline import generate_candidates, load_inference_input

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "mock"


def _input(name: str) -> InferenceInput:
    return load_inference_input(FIXTURES / name / "inference.json")


@pytest.mark.parametrize("name,lengths", [
    ("single_path", (20.0,)), ("branching_top_k", (20.0, 30.0, 40.0)),
    ("temporal_slack", (20.0, 40.0)), ("simplified_stair", (7.0,)),
])
def test_reachability_minimum_time_and_repeatable_complete(
    name: str, lengths: tuple[float, ...],
) -> None:
    inputs = _input(name)
    topology = CameraTopologyGraph(inputs.topology)
    assert topology.minimum_hop_transition_path("CAM_A", "CAM_B") is not None
    assert topology.minimum_hop_transition_path("CAM_B", "CAM_A") is None
    minimum = NavigationGraph(inputs.navigation).minimum_path("A", "B")
    assert minimum is not None and minimum.distance_m == lengths[0]
    outputs = [generate_candidates(inputs, clock=lambda: 0.0) for _ in range(3)]
    assert len({output.model_dump_json() for output in outputs}) == 1
    result = outputs[0]
    assert result.complete and result.termination_reason == TerminationReason.COMPLETE
    assert tuple(candidate.path_length for candidate in result.candidates) == lengths
    assert tuple(candidate.minimum_travel_time for candidate in result.candidates) == lengths
    assert all(candidate.provenance == Provenance.INFERRED_GAP for candidate in result.candidates)
    assert all(candidate.path_score is None for candidate in result.candidates)


def _retime(observation: Observation, timestamp: float) -> Observation:
    payload = observation.model_dump(mode="python")
    payload.update(start_time=timestamp, end_time=timestamp)
    payload["projected_path"][0]["timestamp"] = timestamp
    return Observation.model_validate(payload)


def test_speed_and_unreachable_reverse_rejection_and_bad_time() -> None:
    inputs = _input("single_path")
    too_fast = inputs.model_copy(update={
        "end_observation": _retime(inputs.end_observation, 29.0),
    })
    rejected = generate_candidates(too_fast, clock=lambda: 0.0)
    assert rejected.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    assert "PHYSICALLY_IMPOSSIBLE_SPEED" in rejected.rejection_reasons
    reversed_input = inputs.model_copy(update={
        "start_observation": _retime(inputs.end_observation, 10.0),
        "end_observation": _retime(inputs.start_observation, 30.0),
    })
    reverse = generate_candidates(reversed_input)
    assert reverse.termination_reason == TerminationReason.NO_FEASIBLE_PATH
    with pytest.raises(GraphInputError):
        generate_candidates(inputs.model_copy(update={
            "end_observation": _retime(inputs.end_observation, 10.0),
        }))


def test_top_k_preserves_distinct_routes_and_truth_can_be_rank_three() -> None:
    inputs = _input("branching_top_k")
    full = generate_candidates(inputs, clock=lambda: 0.0)
    assert tuple(candidate.navmesh_corridor for candidate in full.candidates) == (
        ("direct",), ("upper",), ("lower",),
    )
    truncated = generate_candidates(inputs, max_paths=2, clock=lambda: 0.0)
    assert truncated.candidates == full.candidates[:2]
    assert truncated.termination_reason == TerminationReason.MAX_PATHS_REACHED
    assert not truncated.complete


@pytest.mark.parametrize("updates,reason", [
    ({"max_search_nodes": 1}, TerminationReason.MAX_SEARCH_NODES),
    ({"max_branch_factor": 1}, TerminationReason.MAX_BRANCH_FACTOR),
])
def test_structural_bounds_terminate_deterministically(
    updates: dict[str, int], reason: TerminationReason,
) -> None:
    inputs = _input("branching_top_k")
    policy = GraphSearchPolicy.model_validate(inputs.search_policy.model_dump() | updates)
    bounded = inputs.model_copy(update={"search_policy": policy})
    outputs = [generate_candidates(bounded, clock=lambda: 0.0) for _ in range(2)]
    assert outputs[0] == outputs[1]
    assert outputs[0].termination_reason == reason and not outputs[0].complete


def test_injected_operational_timeout_is_explicit() -> None:
    def clock() -> Callable[[], float]:
        times = iter((0.0, 61.0))
        return lambda: next(times)
    first = generate_candidates(_input("single_path"), clock=clock())
    second = generate_candidates(_input("single_path"), clock=clock())
    assert first == second
    assert first.termination_reason == TerminationReason.SEARCH_TIMEOUT
    assert not first.complete
