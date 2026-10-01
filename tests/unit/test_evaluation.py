"""Numeric metric references and continuous physical constraint regression checks."""

from itertools import pairwise

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance, Vec3
from amidst.domain.evaluation import AABBObstacle, ConstraintConfig, EvaluationConfig
from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory
from amidst.domain.navigation import (
    CrossFloorPolicy,
    NavigationDataKind,
    NavigationEdge,
    NavigationGraphConfig,
    NavigationNode,
    NavigationTransitionType,
)
from amidst.domain.trajectory import (
    HypothesisKind,
    SegmentKind,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.evaluation import evaluate_trajectories


def _hypothesis(
    points: tuple[Vec3, ...],
    *,
    times: tuple[float, ...] | None = None,
    candidate_id: str = "candidate",
    hypothesis_id: str = "hypothesis",
) -> TrajectoryHypothesis:
    if times is None:
        times = tuple(float(index) for index in range(len(points)))
    pairs = tuple(pairwise(tuple(zip(times, points, strict=True))))
    segments = tuple(
        TrajectorySegment(
            time_range=(before[0], after[0]),
            kind=SegmentKind.DWELL if before[1] == after[1] else SegmentKind.MOVEMENT,
        )
        for before, after in pairs
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
            for time, position in zip(times, points, strict=True)
        ),
        segments=segments,
        minimum_travel_time=0,
        temporal_slack=duration,
        movement_duration=duration - dwell,
        dwell_duration=dwell,
        uncertainty="SYNTHETIC_TEST_FIXTURE: timing is uncalibrated",
    )


def _truth(
    points: tuple[Vec3, ...] = ((0, 0, 0), (1, 0, 0), (2, 0, 0)),
    times: tuple[float, ...] | None = None,
) -> GroundTruthTrajectory:
    if times is None:
        times = tuple(float(index) for index in range(len(points)))
    return GroundTruthTrajectory(
        trajectory_id="truth",
        target_id="target",
        scene_id="SYNTHETIC_TEST_FIXTURE",
        random_seed=7,
        sample_rate_hz=1,
        samples=tuple(
            GroundTruthSample(timestamp=time, position=position, velocity=(0, 0, 0))
            for time, position in zip(times, points, strict=True)
        ),
    )


def _graph(*, stairs: bool = False) -> NavigationGraphConfig:
    return NavigationGraphConfig(
        graph_id="SYNTHETIC_TEST_FIXTURE",
        spatial_context_id="synthetic-frame",
        data_kind=NavigationDataKind.SYNTHETIC_TEST_FIXTURE,
        cross_floor_policy=(
            CrossFloorPolicy.EXPLICIT_PARAMETERIZED_STAIRS
            if stairs
            else CrossFloorPolicy.DISCONNECTED
        ),
        nodes=(
            NavigationNode(node_id="a", position=(0, 0, 0), floor_id="1F"),
            NavigationNode(
                node_id="b", position=(10, 0, 3 if stairs else 0), floor_id="2F" if stairs else "1F"
            ),
        ),
        edges=(
            NavigationEdge(
                edge_id="edge",
                from_node_id="a",
                to_node_id="b",
                polyline=((0, 0, 0), (0, 0, 3), (10, 0, 3)) if stairs else ((0, 0, 0), (10, 0, 0)),
                transition_type=(
                    NavigationTransitionType.STAIR_UP if stairs else NavigationTransitionType.WALK
                ),
                stair_id="stair" if stairs else None,
            ),
        ),
    )


def test_ade_fde_interpolate_all_truth_timestamps_with_known_errors() -> None:
    result = evaluate_trajectories(
        (_hypothesis(((0, 0, 0), (4, 0, 0)), times=(0, 2)),),
        _truth(),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=2),
    )
    metric = result.trajectory_metrics[0]
    assert metric.ground_truth_sample_count == 3
    assert metric.ade_m == pytest.approx(1)
    assert metric.fde_m == pytest.approx(2)
    assert result.min_ade_at_k_m == pytest.approx(1)
    assert result.min_fde_at_k_m == pytest.approx(2)
    assert not result.coverage_at_k


def test_full_three_dimensional_displacement_and_strict_coverage_epsilon() -> None:
    trajectory = _hypothesis(((0, 0, 1), (2, 0, 1)), times=(0, 2))
    result = evaluate_trajectories(
        (trajectory,),
        _truth(),
        EvaluationConfig(coverage_epsilon_m=1),
        constraints=ConstraintConfig(max_speed_m_s=1),
    )
    assert result.trajectory_metrics[0].ade_m == 1
    assert result.trajectory_metrics[0].fde_m == 1
    assert not result.coverage_at_k
    assert evaluate_trajectories(
        (trajectory,),
        _truth(),
        EvaluationConfig(coverage_epsilon_m=1.01),
        constraints=ConstraintConfig(max_speed_m_s=1),
    ).coverage_at_k


def test_true_route_is_preserved_at_k_three_with_distinct_route_denominator() -> None:
    trajectories = tuple(
        _hypothesis(
            ((0, offset, 0), (2, offset, 0)),
            times=(0, 2),
            candidate_id=f"route-{rank}",
            hypothesis_id=f"route-{rank}-primary",
        )
        for rank, offset in enumerate((3, 1, 0), start=1)
    )
    one = evaluate_trajectories(
        trajectories,
        _truth(),
        EvaluationConfig(k_routes=1),
        constraints=ConstraintConfig(max_speed_m_s=1),
    )
    three = evaluate_trajectories(
        trajectories,
        _truth(),
        EvaluationConfig(k_routes=3),
        constraints=ConstraintConfig(max_speed_m_s=1),
    )
    assert one.min_ade_at_k_m == 3
    assert one.min_fde_at_k_m == 3
    assert not one.coverage_at_k
    assert three.selected_route_count == 3
    assert three.min_ade_at_k_m == three.min_fde_at_k_m == 0
    assert three.coverage_at_k
    assert three.top_k_hypothesis_ids == tuple(
        trajectory.hypothesis_id for trajectory in trajectories
    )


def test_alternate_timing_never_inflates_top_k_or_selects_best_timing_using_truth() -> None:
    bad_primary = _hypothesis(
        ((0, 3, 0), (2, 3, 0)), times=(0, 2), candidate_id="route-1", hypothesis_id="primary"
    )
    exact_alternate = _hypothesis(
        ((0, 0, 0), (2, 0, 0)), times=(0, 2), candidate_id="route-1", hypothesis_id="alternate"
    )
    second_route = _hypothesis(
        ((0, 1, 0), (2, 1, 0)), times=(0, 2), candidate_id="route-2", hypothesis_id="second"
    )
    result = evaluate_trajectories(
        (bad_primary, exact_alternate, second_route),
        _truth(),
        EvaluationConfig(k_routes=2),
        constraints=ConstraintConfig(max_speed_m_s=1),
    )
    assert result.top_k_hypothesis_ids == ("primary", "second")
    assert result.selected_route_count == 2
    assert result.evaluated_hypothesis_count == 3
    assert result.trajectory_metrics[1].ade_m == 0
    assert result.min_ade_at_k_m == 1
    assert not result.coverage_at_k


@pytest.mark.parametrize("time_range", [(0.5, 2), (0, 1.5), (0, 3)])
def test_rejects_partial_coverage_and_extended_extents(time_range: tuple[float, float]) -> None:
    with pytest.raises(ValueError, match="exactly matching time extents"):
        evaluate_trajectories(
            (_hypothesis(((0, 0, 0), (2, 0, 0)), times=time_range),),
            _truth(),
            EvaluationConfig(),
            constraints=ConstraintConfig(max_speed_m_s=10),
        )


@pytest.mark.parametrize("offset, expected", [(0, 1), (2, 0), (0.5, 1)])
def test_continuous_collision_checks_midsegment_and_closed_boundary(
    offset: float, expected: int
) -> None:
    trajectory = _hypothesis(((0, offset, 0), (10, offset, 0)))
    result = evaluate_trajectories(
        (trajectory,),
        _truth(((0, offset, 0), (10, offset, 0))),
        EvaluationConfig(),
        constraints=ConstraintConfig(
            max_speed_m_s=10,
            obstacles=(
                AABBObstacle(obstacle_id="wall", minimum=(4.9, -0.5, -1), maximum=(5.1, 0.5, 1)),
            ),
        ),
    )
    physical = result.trajectory_metrics[0].physical
    assert physical.collision_segment_count == expected
    assert physical.collision_rate == expected
    assert result.collision_rate == expected
    assert not physical.mesh_collision_certified


def test_collision_denominator_counts_segments_once_even_for_overlapping_obstacles() -> None:
    trajectory = _hypothesis(((0, 0, 0), (10, 0, 0), (20, 0, 0)))
    obstacles = tuple(
        AABBObstacle(obstacle_id=f"wall-{index}", minimum=(4, -1, -1), maximum=(6, 1, 1))
        for index in range(2)
    )
    result = evaluate_trajectories(
        (trajectory,),
        _truth(((0, 0, 0), (10, 0, 0), (20, 0, 0))),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=10, obstacles=obstacles),
    )
    assert result.total_segment_count == 2
    assert result.collision_segment_count == 1
    assert result.collision_rate == 0.5
    assert result.constraint_violation_rate == 0.5


def test_speed_violation_and_missing_corridor_are_explicit() -> None:
    result = evaluate_trajectories(
        (_hypothesis(((0, 0, 0), (10, 0, 0))),),
        _truth(((0, 0, 0), (10, 0, 0))),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=5),
    )
    physical = result.trajectory_metrics[0].physical
    assert physical.speed_violation_segment_count == 1
    assert physical.speed_violation_rate == 1
    assert physical.collision_rate == 0
    assert physical.corridor_segment_count == 0
    assert physical.corridor_violation_rate is None
    assert physical.constraint_violation_rate == 1


@pytest.mark.parametrize(
    "points, expected",
    [
        (((0, 0, 0), (10, 0, 0)), 0),
        (((10, 0, 0), (0, 0, 0)), 1),
        (((0, 0, 0), (10, 1, 0)), 1),
        (((0, 0, 0), (0, 0, 0)), 0),
        (((5, 1, 0), (5, 1, 0)), 1),
    ],
)
def test_directed_corridor_checks_movement_and_dwell(
    points: tuple[Vec3, ...], expected: int
) -> None:
    result = evaluate_trajectories(
        (_hypothesis(points),),
        _truth(points),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=20, navigation_graph=_graph()),
    )
    physical = result.trajectory_metrics[0].physical
    assert physical.corridor_segment_count == 1
    assert physical.corridor_violation_segment_count == expected
    assert physical.corridor_violation_rate == expected
    assert physical.constraint_violation_rate == expected


def test_parameterized_stair_continuity_passes_but_corner_cutting_fails() -> None:
    graph = _graph(stairs=True)
    on_stair = ((0, 0, 0), (0, 0, 3), (10, 0, 3))
    result = evaluate_trajectories(
        (_hypothesis(on_stair),),
        _truth(on_stair),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=10, navigation_graph=graph),
    )
    assert result.constraint_violation_rate == 0
    shortcut = ((0, 0, 0), (10, 0, 3))
    result = evaluate_trajectories(
        (_hypothesis(shortcut),),
        _truth(shortcut),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=20, navigation_graph=graph),
    )
    assert result.trajectory_metrics[0].physical.corridor_violation_rate == 1


def test_collinear_subdivided_corridors_allow_unsampled_intermediate_vertices() -> None:
    graph = _graph()
    edge = graph.edges[0].model_copy(update={"polyline": ((0, 0, 0), (5, 0, 0), (10, 0, 0))})
    graph = graph.model_copy(update={"edges": (edge,)})
    result = evaluate_trajectories(
        (_hypothesis(((0, 0, 0), (10, 0, 0))),),
        _truth(((0, 0, 0), (10, 0, 0))),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=10, navigation_graph=graph),
    )
    assert result.constraint_violation_rate == 0


def test_stationary_route_on_isolated_node_is_authorized_without_movement_edges() -> None:
    graph = _graph().model_copy(update={"edges": ()})
    result = evaluate_trajectories(
        (_hypothesis(((0, 0, 0), (0, 0, 0))),),
        _truth(((0, 0, 0), (0, 0, 0))),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=1, navigation_graph=graph),
    )
    assert result.constraint_violation_rate == 0


def test_tiny_off_corridor_motion_does_not_pass_vacuously() -> None:
    points = ((0, 1, 0), (1e-8, 1, 0))
    result = evaluate_trajectories(
        (_hypothesis(points),),
        _truth(points),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=1, navigation_graph=_graph()),
    )
    assert result.trajectory_metrics[0].physical.corridor_violation_rate == 1


def test_speed_limit_precision_scales_to_configured_units() -> None:
    points = ((0, 0, 0), (1e-14, 0, 0))
    result = evaluate_trajectories(
        (_hypothesis(points),),
        _truth(points),
        EvaluationConfig(),
        constraints=ConstraintConfig(max_speed_m_s=1e-15),
    )
    assert result.trajectory_metrics[0].physical.speed_violation_rate == 1


def test_empty_candidates_report_missing_error_and_denominators_not_false_perfection() -> None:
    result = evaluate_trajectories(
        (), _truth(), EvaluationConfig(), constraints=ConstraintConfig(max_speed_m_s=1)
    )
    assert result.trajectory_metrics == result.top_k_hypothesis_ids == ()
    assert result.selected_route_count == result.total_segment_count == 0
    assert result.min_ade_at_k_m is result.min_fde_at_k_m is None
    assert result.collision_rate is result.constraint_violation_rate is None
    assert not result.coverage_at_k


def test_revalidates_bypassed_hypothesis_ground_truth_and_config() -> None:
    trajectory = _hypothesis(((0, 0, 0), (2, 0, 0)), times=(0, 2))
    truth = _truth()
    config = EvaluationConfig()
    constraints = ConstraintConfig(max_speed_m_s=1)
    for trajectories, ground_truth, eval_config, constraint_config in (
        (
            (trajectory.model_copy(update={"provenance": Provenance.GROUND_TRUTH}),),
            truth,
            config,
            constraints,
        ),
        (
            (trajectory,),
            truth.model_copy(update={"samples": tuple(reversed(truth.samples))}),
            config,
            constraints,
        ),
        ((trajectory,), truth, config.model_copy(update={"coverage_epsilon_m": -1}), constraints),
        ((trajectory,), truth, config, constraints.model_copy(update={"max_speed_m_s": 0})),
    ):
        with pytest.raises(ValidationError):
            evaluate_trajectories(
                trajectories, ground_truth, eval_config, constraints=constraint_config
            )


def test_revalidates_ordered_samples_and_rejects_duplicate_hypothesis_ids() -> None:
    trajectory = _hypothesis(((0, 0, 0), (2, 0, 0)), times=(0, 2))
    malformed = trajectory.model_copy(
        update={"timed_points": tuple(reversed(trajectory.timed_points))}
    )
    with pytest.raises(ValidationError, match="strictly time-ordered"):
        evaluate_trajectories(
            (malformed,),
            _truth(),
            EvaluationConfig(),
            constraints=ConstraintConfig(max_speed_m_s=1),
        )
    with pytest.raises(ValueError, match="identities must be unique"):
        evaluate_trajectories(
            (trajectory, trajectory),
            _truth(),
            EvaluationConfig(),
            constraints=ConstraintConfig(max_speed_m_s=1),
        )


def test_revalidates_navigation_graph_and_obstacle_bypass_instances() -> None:
    trajectory = _hypothesis(((0, 0, 0), (10, 0, 0)))
    graph = _graph()
    bad_edge = graph.edges[0].model_copy(update={"polyline": ((1, 0, 0), (10, 0, 0))})
    bad_graph = graph.model_copy(update={"edges": (bad_edge,)})
    with pytest.raises(ValueError, match="endpoints must match"):
        evaluate_trajectories(
            (trajectory,),
            _truth(((0, 0, 0), (10, 0, 0))),
            EvaluationConfig(),
            constraints=ConstraintConfig(max_speed_m_s=10, navigation_graph=bad_graph),
        )
    obstacle = AABBObstacle(obstacle_id="box", minimum=(0, 0, 0), maximum=(1, 1, 1))
    constraints = ConstraintConfig(max_speed_m_s=10).model_copy(
        update={"obstacles": (obstacle.model_copy(update={"minimum": (2, 2, 2)}),)}
    )
    with pytest.raises(ValidationError, match="positive extent"):
        evaluate_trajectories(
            (trajectory,),
            _truth(((0, 0, 0), (10, 0, 0))),
            EvaluationConfig(),
            constraints=constraints,
        )


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_invalid_coverage_threshold_rejected(value: float) -> None:
    with pytest.raises(ValidationError):
        EvaluationConfig(coverage_epsilon_m=value)
