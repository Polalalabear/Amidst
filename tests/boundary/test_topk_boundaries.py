"""Top-K truncation and adopted distance/edge tie ordering stay deterministic."""

import itertools
from urllib.parse import quote

import pytest

from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig
from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory
from amidst.domain.pipeline import InferenceInput
from amidst.domain.trajectory import TerminationReason
from amidst.evaluation.metrics import evaluate_trajectories
from amidst.pipeline import reconstruct_input
from amidst.visualization import RerunDebugVisualizationAdapter

from .graph_cases import graph_case_spec, infer_graph_case, load_graph_case
from .test_no_feasible_path import GraphRecordingSpy


@pytest.mark.parametrize("case_id", ["eight_routes_k1", "eight_routes_k3", "eight_routes_k12"])
def test_topk_boundaries_count_only_formal_distinct_corridors(case_id: str) -> None:
    expected = graph_case_spec(case_id)["expected"]
    results = [infer_graph_case(case_id) for _ in range(3)]
    assert results[0] == results[1] == results[2]
    result, event = results[0]
    assert [list(candidate.navmesh_corridor) for candidate in result.candidates] == (
        expected["candidates"]
    )
    assert result.termination_reason == TerminationReason(expected["termination"])
    assert result.complete == expected["complete"]
    assert result.expanded_nodes == expected["expanded_nodes"]
    assert len(set(candidate.candidate_id for candidate in result.candidates)) == len(
        result.candidates
    )
    assert event.candidates == result.candidates
    assert {trajectory.candidate_id for trajectory in event.trajectories} == {
        candidate.candidate_id for candidate in result.candidates
    }
    full, _full_event = infer_graph_case("eight_routes_k12")
    assert [candidate.navmesh_corridor for candidate in result.candidates] == [
        candidate.navmesh_corridor for candidate in full.candidates[:len(result.candidates)]
    ]


def test_k_truncation_preserves_candidate_ids_for_the_same_bound_input() -> None:
    inputs = load_graph_case("eight_routes_k3")
    one, _one_event = reconstruct_input(inputs, max_paths=1, clock=lambda: 0.0)
    three, _three_event = reconstruct_input(inputs, max_paths=3, clock=lambda: 0.0)
    full, _full_event = reconstruct_input(inputs, max_paths=12, clock=lambda: 0.0)
    assert len(full.candidates) == 8
    assert full.termination_reason == TerminationReason.COMPLETE
    assert one.candidates == full.candidates[:1]
    assert three.candidates == full.candidates[:3]


def test_truncated_routes_alone_reach_metrics_and_rerun() -> None:
    inputs = load_graph_case("eight_routes_k3")
    result, event = infer_graph_case("eight_routes_k3")
    assert len(result.candidates) == 3
    output_ids = {candidate.candidate_id for candidate in result.candidates}
    truth = GroundTruthTrajectory(
        trajectory_id="topk_evaluation_only", target_id=event.target_id,
        scene_id="SYNTHETIC_TEST_FIXTURE", random_seed=0, sample_rate_hz=1,
        samples=tuple(GroundTruthSample(
            timestamp=point.timestamp, position=point.world_position, velocity=(0, 0, 0),
        ) for point in event.trajectories[0].timed_points),
    )
    metrics = evaluate_trajectories(
        event.trajectories, truth, EvaluationConfig(k_routes=12),
        constraints=ConstraintConfig(
            max_speed_m_s=inputs.movement.max_speed_m_s, navigation_graph=inputs.navigation,
        ),
    )
    assert metrics.selected_route_count == 3
    assert {metric.candidate_id for metric in metrics.trajectory_metrics} == output_ids
    assert all(metric.physical.constraint_violation_rate == 0 for metric in (
        metrics.trajectory_metrics
    ))

    sink = GraphRecordingSpy()
    adapter = RerunDebugVisualizationAdapter(
        observations=(inputs.start_observation, inputs.end_observation),
        navigation_config=inputs.navigation, topology_config=inputs.topology, recording=sink,
    )
    adapter.log_event(event)
    adapter.close()
    logged_candidate_paths = [path for path in sink.paths if path.startswith("world/") and (
        "/candidates/" in path
    )]
    assert len(logged_candidate_paths) == 3
    assert all(any(quote(candidate_id, safe="") in path for candidate_id in output_ids)
               for path in logged_candidate_paths)


@pytest.mark.parametrize("edge_order", list(itertools.permutations(range(3))))
@pytest.mark.parametrize("reverse_other_inputs", [False, True])
def test_equal_distance_ties_follow_complete_edge_identity_without_scores(
    edge_order: tuple[int, ...], reverse_other_inputs: bool,
) -> None:
    inputs = load_graph_case("equal_distance_ties")
    payload = inputs.model_dump(mode="python")
    payload["navigation"]["edges"] = tuple(inputs.navigation.edges[index] for index in edge_order)
    payload["topology"]["transitions"] = tuple(
        inputs.topology.transitions[index] for index in reversed(edge_order)
    )
    if reverse_other_inputs:
        payload["navigation"]["nodes"] = tuple(reversed(inputs.navigation.nodes))
        payload["topology"]["nodes"] = tuple(reversed(inputs.topology.nodes))
        payload = dict(reversed(list(payload.items())))
    shuffled = InferenceInput.model_validate(payload)
    result, event = reconstruct_input(shuffled, max_paths=3, clock=lambda: 0.0)
    baseline_result, baseline_event = infer_graph_case("equal_distance_ties")
    assert result == baseline_result and event == baseline_event
    assert tuple(candidate.navmesh_corridor for candidate in result.candidates) == (
        ("a_edge",), ("m_edge",), ("z_edge",),
    )
    assert len({candidate.path_length for candidate in result.candidates}) == 1
    assert len({candidate.temporal_cost for candidate in result.candidates}) == 1
    assert all(candidate.path_score is None and not candidate.semantic_regions
               for candidate in result.candidates)
