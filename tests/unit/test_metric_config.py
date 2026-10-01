"""External metric policies preserve the previous synthetic numeric semantics."""

from itertools import pairwise
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.common import Vec3
from amidst.domain.evaluation import AABBObstacle, ConstraintConfig, EvaluationConfig
from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory
from amidst.domain.metric_config import MetricConfig
from amidst.domain.navigation import (
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
)
from amidst.domain.trajectory import (
    HypothesisKind,
    SegmentKind,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.evaluation import evaluate_trajectories
from amidst.evaluation.configured import (
    ConfiguredEvaluationResult,
    evaluate_configured_trajectories,
)


def _hypothesis(
    positions: tuple[Vec3, ...],
    *,
    candidate_id: str = "candidate",
    hypothesis_id: str = "hypothesis",
    times: tuple[float, ...] | None = None,
) -> TrajectoryHypothesis:
    if times is None:
        times = tuple(float(index) for index in range(len(positions)))
    segments = tuple(
        TrajectorySegment(
            time_range=(before[0], after[0]),
            kind=SegmentKind.DWELL if before[1] == after[1] else SegmentKind.MOVEMENT,
        )
        for before, after in pairwise(tuple(zip(times, positions, strict=True)))
    )
    dwell = sum(
        segment.time_range[1] - segment.time_range[0]
        for segment in segments
        if segment.kind == SegmentKind.DWELL
    )
    duration = times[-1] - times[0]
    return TrajectoryHypothesis(
        hypothesis_id=hypothesis_id,
        candidate_id=candidate_id,
        kind=HypothesisKind.DWELL if dwell else HypothesisKind.SLOWER_MOVEMENT,
        timed_points=tuple(
            TimedTrajectoryPoint(timestamp=time, world_position=position)
            for time, position in zip(times, positions, strict=True)
        ),
        segments=segments,
        minimum_travel_time=0,
        temporal_slack=duration,
        movement_duration=duration - dwell,
        dwell_duration=dwell,
        uncertainty="SYNTHETIC_TEST_FIXTURE: uncalibrated timing",
    )


def _truth(
    positions: tuple[Vec3, ...] = ((0, 0, 0), (1, 0, 0), (2, 0, 0)),
    times: tuple[float, ...] | None = None,
) -> GroundTruthTrajectory:
    if times is None:
        times = tuple(float(index) for index in range(len(positions)))
    return GroundTruthTrajectory(
        trajectory_id="metric-reference",
        target_id="target",
        scene_id="SYNTHETIC_TEST_FIXTURE",
        random_seed=20261001,
        sample_rate_hz=1,
        samples=tuple(
            GroundTruthSample(timestamp=time, position=position, velocity=(0, 0, 0))
            for time, position in zip(times, positions, strict=True)
        ),
    )


def test_default_metric_config_roundtrip_exposes_unresolved_formal_status() -> None:
    config = MetricConfig()
    assert MetricConfig.model_validate_json(config.model_dump_json()) == config
    assert config.metric_config_version == "synthetic-regression-metrics-v1"
    assert config.k_values == (3,)
    assert config.trajectory_distance_metric == "ADE"
    assert config.coverage_epsilon_m == 1e-6
    assert config.collision_tolerance_m == 0
    assert config.constraint_speed_relative_tolerance == 1e-12
    assert config.constraint_corridor_tolerance_m == 1e-6
    assert config.formal_benchmark_status == "UNRESOLVED"


def test_default_config_reproduces_entire_existing_evaluation_result() -> None:
    trajectory = _hypothesis(((0, 0, 0), (4, 0, 0)), times=(0, 2))
    constraints = ConstraintConfig(max_speed_m_s=2)
    original = evaluate_trajectories(
        (trajectory,), _truth(), EvaluationConfig(), constraints=constraints
    )
    configured = evaluate_configured_trajectories(
        (trajectory,), _truth(), MetricConfig(), constraints=constraints
    )
    assert configured.for_k(3) == original
    assert configured.constraints == constraints
    assert configured.for_k(3).trajectory_metrics[0].ade_m == 1
    assert configured.for_k(3).trajectory_metrics[0].fde_m == 2
    assert (
        ConfiguredEvaluationResult.model_validate_json(configured.model_dump_json()) == configured
    )


def test_requested_k_order_and_first_route_timing_remain_authoritative() -> None:
    trajectories = (
        _hypothesis(
            ((0, 3, 0), (2, 3, 0)),
            times=(0, 2),
            candidate_id="route-1",
            hypothesis_id="route-1-primary",
        ),
        _hypothesis(
            ((0, 0, 0), (2, 0, 0)),
            times=(0, 2),
            candidate_id="route-1",
            hypothesis_id="route-1-alternate",
        ),
        _hypothesis(
            ((0, 1, 0), (2, 1, 0)),
            times=(0, 2),
            candidate_id="route-2",
            hypothesis_id="route-2-primary",
        ),
        _hypothesis(
            ((0, 0, 0), (2, 0, 0)),
            times=(0, 2),
            candidate_id="route-3",
            hypothesis_id="route-3-primary",
        ),
    )
    original_order = tuple(trajectory.model_dump_json() for trajectory in trajectories)
    result = evaluate_configured_trajectories(
        trajectories,
        _truth(),
        MetricConfig(k_values=(3, 1, 2)),
        constraints=ConstraintConfig(max_speed_m_s=1),
    )
    assert tuple(evaluation.config.k_routes for evaluation in result.evaluations) == (3, 1, 2)
    assert result.for_k(1).min_ade_at_k_m == 3
    assert result.for_k(2).min_ade_at_k_m == 1
    assert result.for_k(3).min_ade_at_k_m == 0
    assert not result.for_k(1).coverage_at_k
    assert result.for_k(3).coverage_at_k
    assert result.for_k(3).top_k_hypothesis_ids == (
        "route-1-primary",
        "route-2-primary",
        "route-3-primary",
    )
    assert tuple(trajectory.model_dump_json() for trajectory in trajectories) == original_order
    with pytest.raises(KeyError, match="not requested"):
        result.for_k(4)


def test_ade_arithmetic_mean_and_last_timestamp_fde_with_uneven_truth_sampling() -> None:
    result = evaluate_configured_trajectories(
        (_hypothesis(((0, 0, 0), (0, 0, 0)), times=(0, 10)),),
        _truth(((0, 0, 0), (1, 0, 0), (10, 0, 0)), times=(0, 1, 10)),
        MetricConfig(),
        constraints=ConstraintConfig(max_speed_m_s=1),
    ).for_k(3)
    assert result.min_ade_at_k_m == pytest.approx(11 / 3)
    assert result.min_fde_at_k_m == 10


def test_coverage_epsilon_is_external_and_strict_without_altering_distance() -> None:
    trajectory = _hypothesis(((0, 1, 0), (2, 1, 0)), times=(0, 2))
    for epsilon, expected in ((1, False), (1.01, True)):
        result = evaluate_configured_trajectories(
            (trajectory,),
            _truth(),
            MetricConfig(coverage_epsilon_m=epsilon),
            constraints=ConstraintConfig(max_speed_m_s=1),
        ).for_k(3)
        assert result.coverage_at_k is expected
        assert result.min_ade_at_k_m == result.min_fde_at_k_m == 1


def test_collision_tolerance_expands_closed_boxes_and_default_preserves_touching() -> None:
    trajectory = _hypothesis(((0, 0.6, 0), (10, 0.6, 0)))
    truth = _truth(((0, 0.6, 0), (10, 0.6, 0)))
    constraints = ConstraintConfig(
        max_speed_m_s=10,
        obstacles=(AABBObstacle(obstacle_id="box", minimum=(4, -0.5, -1), maximum=(6, 0.5, 1)),),
    )
    no_margin = evaluate_configured_trajectories(
        (trajectory,), truth, MetricConfig(), constraints=constraints
    )
    margin = evaluate_configured_trajectories(
        (trajectory,), truth, MetricConfig(collision_tolerance_m=0.1), constraints=constraints
    )
    assert no_margin.for_k(3).collision_rate == 0
    assert margin.for_k(3).collision_rate == 1
    assert margin.constraints.collision_tolerance_m == 0.1
    assert constraints.collision_tolerance_m == 0
    assert not margin.for_k(3).trajectory_metrics[0].physical.mesh_collision_certified


def test_relative_speed_tolerance_is_configurable_and_defaults_replay_isclose_policy() -> None:
    positions = ((0, 0, 0), (1 + 5e-8, 0, 0))
    trajectory = _hypothesis(positions)
    constraints = ConstraintConfig(max_speed_m_s=1)
    strict = evaluate_configured_trajectories(
        (trajectory,), _truth(positions), MetricConfig(), constraints=constraints
    )
    tolerant = evaluate_configured_trajectories(
        (trajectory,),
        _truth(positions),
        MetricConfig(constraint_speed_relative_tolerance=1e-6),
        constraints=constraints,
    )
    assert strict.for_k(3).trajectory_metrics[0].physical.speed_violation_rate == 1
    assert tolerant.for_k(3).trajectory_metrics[0].physical.speed_violation_rate == 0


def test_corridor_tolerance_comes_from_metrics_instead_of_legacy_constraint_input() -> None:
    graph = NavigationGraphConfig(
        graph_id="graph",
        spatial_context_id="SYNTHETIC_TEST_FIXTURE",
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        nodes=(
            NavigationNode(node_id="a", floor_id="1F", position=(0, 0, 0)),
            NavigationNode(node_id="b", floor_id="1F", position=(2, 0, 0)),
        ),
        edges=(
            NavigationEdge(
                edge_id="ab",
                from_node_id="a",
                to_node_id="b",
                polyline=((0, 0, 0), (2, 0, 0)),
            ),
        ),
    )
    positions = ((0, 0.0001, 0), (2, 0.0001, 0))
    constraints = ConstraintConfig(max_speed_m_s=2, navigation_graph=graph, corridor_tolerance_m=1)
    trajectory = _hypothesis(positions)
    strict = evaluate_configured_trajectories(
        (trajectory,), _truth(positions), MetricConfig(), constraints=constraints
    )
    tolerant = evaluate_configured_trajectories(
        (trajectory,),
        _truth(positions),
        MetricConfig(constraint_corridor_tolerance_m=0.001),
        constraints=constraints,
    )
    assert strict.for_k(3).constraint_violation_rate == 1
    assert tolerant.for_k(3).constraint_violation_rate == 0
    assert constraints.corridor_tolerance_m == 1
    assert strict.constraints.corridor_tolerance_m == 1e-6


def test_exact_zero_constraint_tolerances_are_supported() -> None:
    result = evaluate_configured_trajectories(
        (_hypothesis(((0, 0, 0), (2, 0, 0)), times=(0, 2)),),
        _truth(),
        MetricConfig(constraint_speed_relative_tolerance=0, constraint_corridor_tolerance_m=0),
        constraints=ConstraintConfig(max_speed_m_s=1),
    )
    assert result.for_k(3).constraint_violation_rate == 0


def test_configured_alignment_rejects_partial_extents_instead_of_clipping() -> None:
    with pytest.raises(ValueError, match="exactly matching time extents"):
        evaluate_configured_trajectories(
            (_hypothesis(((0, 0, 0), (2, 0, 0)), times=(0, 3)),),
            _truth(),
            MetricConfig(),
            constraints=ConstraintConfig(max_speed_m_s=1),
        )


def test_empty_candidates_preserve_missing_metric_values_for_every_requested_k() -> None:
    result = evaluate_configured_trajectories(
        (), _truth(), MetricConfig(k_values=(1, 3)), constraints=ConstraintConfig(max_speed_m_s=1)
    )
    for evaluation in result.evaluations:
        assert evaluation.min_ade_at_k_m is evaluation.min_fde_at_k_m is None
        assert not evaluation.coverage_at_k
        assert evaluation.collision_rate is evaluation.constraint_violation_rate is None


@pytest.mark.parametrize(
    "changes",
    [
        {"trajectory_distance_metric": "FDE"},
        {"interpolation_policy": "NEAREST_NEIGHBOR"},
        {"temporal_alignment_policy": "CLIP_SHARED_RANGE"},
        {"ade_policy": "TIME_WEIGHTED_INTEGRAL"},
        {"fde_policy": "LAST_SHARED_TIMESTAMP"},
        {"coverage_comparison": "LESS_THAN_OR_EQUAL"},
        {"top_k_policy": "BEST_TIMING_BY_GROUND_TRUTH"},
        {"collision_tolerance_policy": "ALLOW_PENETRATION"},
        {"collision_boundary_policy": "IGNORE_TOUCHING"},
        {"constraint_denominator": "ONLY_MOVING_SEGMENTS"},
        {"formal_benchmark_status": "APPROVED"},
        {"metric_config_version": " "},
        {"k_values": ()},
        {"k_values": (1, 1)},
        {"k_values": (0, 1)},
        {"coverage_epsilon_m": 0},
        {"collision_tolerance_m": -1},
        {"collision_tolerance_m": float("nan")},
        {"constraint_speed_relative_tolerance": 1},
        {"constraint_corridor_tolerance_m": float("inf")},
        {"unsupported_policy": "value"},
    ],
)
def test_unsupported_or_invalid_metric_configuration_fails(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MetricConfig.model_validate(changes)


def test_adapter_revalidates_bypassed_config_and_constraint_models() -> None:
    trajectory = _hypothesis(((0, 0, 0), (2, 0, 0)), times=(0, 2))
    constraints = ConstraintConfig(max_speed_m_s=1)
    for metric_config, constraint_config in (
        (MetricConfig().model_copy(update={"interpolation_policy": "UNSUPPORTED"}), constraints),
        (MetricConfig(), constraints.model_copy(update={"speed_relative_tolerance": -1})),
    ):
        with pytest.raises(ValidationError):
            evaluate_configured_trajectories(
                (trajectory,), _truth(), metric_config, constraints=constraint_config
            )


def test_configured_output_must_bind_each_requested_k_in_configuration_order() -> None:
    result = evaluate_configured_trajectories(
        (), _truth(), MetricConfig(k_values=(1, 3)), constraints=ConstraintConfig(max_speed_m_s=1)
    )
    with pytest.raises(ValidationError, match="every requested K"):
        ConfiguredEvaluationResult(
            metric_config=result.metric_config,
            constraints=result.constraints,
            evaluations=tuple(reversed(result.evaluations)),
        )
