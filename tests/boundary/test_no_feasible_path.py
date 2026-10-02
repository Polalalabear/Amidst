"""Disconnected/isolated endpoints stay visible without fabricated inference."""

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import rerun as rr

from amidst.domain.common import Provenance
from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig
from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory
from amidst.domain.trajectory import TerminationReason
from amidst.evaluation.metrics import evaluate_trajectories
from amidst.navigation.graph import NavigationGraph
from amidst.visualization import RerunDebugVisualizationAdapter

from .graph_cases import graph_case_spec, infer_graph_case, load_graph_case


@dataclass
class GraphRecordingSpy:
    """Observe SDK log intent without comparing nondeterministic recording bytes."""

    paths: list[str] = field(default_factory=list)
    entities: list[rr.AsComponents] = field(default_factory=list)

    def log(self, entity_path: str, entity: rr.AsComponents, *, static: bool = False) -> None:
        self.paths.append(entity_path)
        self.entities.append(entity)

    def set_time(self, timeline: str, *, duration: float) -> None:
        pass

    def save(self, path: str | Path) -> None:
        pass

    def flush(self) -> None:
        pass

    def disconnect(self) -> None:
        pass


@pytest.mark.parametrize("case_id", [
    "uncited_navigation_bridge", "isolated_start", "isolated_end",
])
def test_unreachable_endpoints_return_empty_structured_result(case_id: str) -> None:
    inputs = load_graph_case(case_id)
    expected = graph_case_spec(case_id)["expected"]
    result, event = infer_graph_case(case_id)
    assert result.termination_reason == event.termination_reason == (
        TerminationReason.NO_FEASIBLE_PATH
    )
    assert result.complete and result.candidates == event.candidates == event.trajectories == ()
    assert result.rejection_reasons == tuple(expected["rejected_transitions"])
    assert result.expanded_nodes == expected["expanded_nodes"]
    assert event.observation_ids == (
        inputs.start_observation.observation_id, inputs.end_observation.observation_id,
    )
    assert inputs.start_observation.provenance == inputs.end_observation.provenance == (
        Provenance.PROJECTED
    )
    report = json.loads(result.model_dump_json())
    assert report["candidates"] == [] and report["termination_reason"] == "NO_FEASIBLE_PATH"

    # GT is supplied only to evaluation, after an empty inference result is complete.
    truth = GroundTruthTrajectory(
        trajectory_id="empty_candidate_evaluation_only",
        target_id=event.target_id, scene_id="SYNTHETIC_TEST_FIXTURE", random_seed=0,
        sample_rate_hz=1,
        samples=tuple(GroundTruthSample(
            timestamp=observation.projected_path[0].timestamp,
            position=observation.projected_path[0].world_position,
            velocity=(0, 0, 0), floor_id=observation.floor_id,
        ) for observation in (inputs.start_observation, inputs.end_observation)),
    )
    metrics = evaluate_trajectories(
        event.trajectories, truth, EvaluationConfig(),
        constraints=ConstraintConfig(
            max_speed_m_s=inputs.movement.max_speed_m_s, navigation_graph=inputs.navigation,
        ),
    )
    assert metrics.selected_route_count == metrics.evaluated_hypothesis_count == 0
    assert metrics.min_ade_at_k_m is None and metrics.min_fde_at_k_m is None
    assert metrics.collision_rate is None and metrics.constraint_violation_rate is None
    assert not metrics.coverage_at_k
    assert json.loads(metrics.model_dump_json())["trajectory_metrics"] == []

    sink = GraphRecordingSpy()
    adapter = RerunDebugVisualizationAdapter(
        observations=(inputs.start_observation, inputs.end_observation),
        navigation_config=inputs.navigation, topology_config=inputs.topology, recording=sink,
    )
    adapter.log_event(event)
    adapter.close()
    for observation in (inputs.start_observation, inputs.end_observation):
        assert any(observation.observation_id.replace(":", "%3A") in path and (
            "projected" in path
        ) for path in sink.paths)
    assert not any("/candidates/" in path or "/hypotheses/" in path for path in sink.paths)


def test_uncited_navigation_connection_does_not_authorize_camera_route() -> None:
    inputs = load_graph_case("uncited_navigation_bridge")
    assert NavigationGraph(inputs.navigation).minimum_path("A", "B") is not None
    assert inputs.topology.transitions == ()
    result, _event = infer_graph_case("uncited_navigation_bridge")
    assert result.candidates == ()


@pytest.mark.parametrize("case_id", ["isolated_start", "isolated_end"])
def test_isolated_endpoint_is_a_known_node_with_reportable_identity(case_id: str) -> None:
    inputs = load_graph_case(case_id)
    side = graph_case_spec(case_id)["expected"]["isolated_endpoint"]
    observation = inputs.start_observation if side == "start" else inputs.end_observation
    navigation = NavigationGraph(inputs.navigation)
    assert navigation.locate_node(
        observation.projected_path[0].world_position, observation.floor_id,
    ) == graph_case_spec(case_id)["input"][f"{side}_node"]
    assert observation.observation_id and observation.floor_id
