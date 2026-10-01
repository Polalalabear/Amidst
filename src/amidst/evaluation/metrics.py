"""Time-aligned displacement errors and deterministic physical constraint checks."""

from __future__ import annotations

import math
from bisect import bisect_right
from itertools import pairwise

from amidst.domain.common import Vec3
from amidst.domain.evaluation import (
    AABBObstacle,
    ConstraintConfig,
    EvaluationConfig,
    EvaluationResult,
    PhysicalMetrics,
    TrajectoryMetrics,
)
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.navigation import NavigationGraphConfig
from amidst.domain.trajectory import TrajectoryHypothesis
from amidst.navigation.graph import NavigationGraph


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("evaluation numeric calculation must remain finite")
    return value


def _position_at(trajectory: TrajectoryHypothesis, timestamp: float) -> Vec3:
    points = trajectory.timed_points
    times = tuple(float(point.timestamp) for point in points)
    index = min(bisect_right(times, timestamp) - 1, len(points) - 2)
    before, after = points[index : index + 2]
    fraction = (timestamp - before.timestamp) / (after.timestamp - before.timestamp)
    return (
        _finite((1 - fraction) * before.world_position[0] + fraction * after.world_position[0]),
        _finite((1 - fraction) * before.world_position[1] + fraction * after.world_position[1]),
        _finite((1 - fraction) * before.world_position[2] + fraction * after.world_position[2]),
    )


def _collides(start: Vec3, end: Vec3, obstacle: AABBObstacle, tolerance_m: float) -> bool:
    """Slab clipping tests the entire closed segment, including a stationary dwell."""
    entry, exit_ = 0.0, 1.0
    for axis in range(3):
        delta = _finite(end[axis] - start[axis])
        low = _finite(obstacle.minimum[axis] - tolerance_m)
        high = _finite(obstacle.maximum[axis] + tolerance_m)
        if delta == 0:
            if not low <= start[axis] <= high:
                return False
            continue
        low = max(low, min(start[axis], end[axis]))
        high = min(high, max(start[axis], end[axis]))
        if low > high:
            return False
        first = _finite((low - start[axis]) / delta)
        second = _finite((high - start[axis]) / delta)
        entry = max(entry, min(first, second))
        exit_ = min(exit_, max(first, second))
        if entry > exit_:
            return False
    return True


def _subtract(first: Vec3, second: Vec3) -> Vec3:
    return (
        _finite(first[0] - second[0]),
        _finite(first[1] - second[1]),
        _finite(first[2] - second[2]),
    )


def _dot(first: Vec3, second: Vec3) -> float:
    return _finite(math.fsum(a * b for a, b in zip(first, second, strict=True)))


def _point_on_segment(point: Vec3, start: Vec3, end: Vec3, tolerance: float) -> bool:
    direction = _subtract(end, start)
    length = _finite(math.dist(start, end))
    if length == 0:
        return _finite(math.dist(point, start)) <= tolerance
    relative = _subtract(point, start)
    fraction = _dot(relative, direction) / (length * length)
    closest: Vec3 = (
        start[0] + min(1.0, max(0.0, fraction)) * direction[0],
        start[1] + min(1.0, max(0.0, fraction)) * direction[1],
        start[2] + min(1.0, max(0.0, fraction)) * direction[2],
    )
    return _finite(math.dist(point, closest)) <= tolerance


def _authorized_segment(
    start: Vec3,
    end: Vec3,
    corridor_segments: tuple[tuple[Vec3, Vec3], ...],
    tolerance: float,
) -> bool:
    """Require full directed coverage, allowing collinear configured edge subdivisions."""
    length = _finite(math.dist(start, end))
    if length == 0:
        return any(
            _point_on_segment(start, first, second, tolerance)
            for first, second in corridor_segments
        )
    direction = _subtract(end, start)
    squared_length = _finite(length * length)
    intervals: list[tuple[float, float]] = []
    for first, second in corridor_segments:
        edge_direction = _subtract(second, first)
        if _dot(direction, edge_direction) <= 0:
            continue
        first_fraction = _dot(_subtract(first, start), direction) / squared_length
        second_fraction = _dot(_subtract(second, start), direction) / squared_length
        first_projection: Vec3 = (
            start[0] + first_fraction * direction[0],
            start[1] + first_fraction * direction[1],
            start[2] + first_fraction * direction[2],
        )
        second_projection: Vec3 = (
            start[0] + second_fraction * direction[0],
            start[1] + second_fraction * direction[1],
            start[2] + second_fraction * direction[2],
        )
        if (
            _finite(math.dist(first, first_projection)) <= tolerance
            and _finite(math.dist(second, second_projection)) <= tolerance
        ):
            intervals.append((max(0.0, first_fraction), min(1.0, second_fraction)))
    covered_until = 0.0
    parameter_tolerance = tolerance / length
    for interval_start, interval_end in sorted(intervals):
        if interval_end < interval_start:
            continue
        if interval_start > covered_until + parameter_tolerance:
            return False
        covered_until = max(covered_until, interval_end)
    return bool(intervals) and covered_until >= 1.0 - parameter_tolerance


def _physical_metrics(
    trajectory: TrajectoryHypothesis,
    constraints: ConstraintConfig,
    corridor_segments: tuple[tuple[Vec3, Vec3], ...] | None,
) -> PhysicalMetrics:
    collision_count, speed_count, corridor_count, violation_count = 0, 0, 0, 0
    pairs = tuple(pairwise(trajectory.timed_points))
    for before, after in pairs:
        start, end = before.world_position, after.world_position
        speed = _finite(math.dist(start, end) / (after.timestamp - before.timestamp))
        speed_violation = speed > constraints.max_speed_m_s and not math.isclose(
            speed,
            constraints.max_speed_m_s,
            rel_tol=constraints.speed_relative_tolerance,
            abs_tol=0,
        )
        collision = any(
            _collides(start, end, obstacle, float(constraints.collision_tolerance_m))
            for obstacle in constraints.obstacles
        )
        corridor_violation = corridor_segments is not None and not _authorized_segment(
            start, end, corridor_segments, float(constraints.corridor_tolerance_m)
        )
        collision_count += int(collision)
        speed_count += int(speed_violation)
        corridor_count += int(corridor_violation)
        violation_count += int(collision or speed_violation or corridor_violation)
    count = len(pairs)
    return PhysicalMetrics(
        segment_count=count,
        collision_segment_count=collision_count,
        collision_rate=collision_count / count,
        speed_violation_segment_count=speed_count,
        speed_violation_rate=speed_count / count,
        corridor_segment_count=count if corridor_segments is not None else 0,
        corridor_violation_segment_count=corridor_count,
        corridor_violation_rate=corridor_count / count if corridor_segments is not None else None,
        constraint_violation_segment_count=violation_count,
        constraint_violation_rate=violation_count / count,
    )


def evaluate_trajectories(
    trajectories: tuple[TrajectoryHypothesis, ...],
    ground_truth: GroundTruthTrajectory,
    config: EvaluationConfig,
    *,
    constraints: ConstraintConfig,
) -> EvaluationResult:
    """Score all truth timestamps; Top-K contains primary timings of distinct routes.

    The caller's hypothesis order represents its prior deterministic candidate ordering.
    Alternate timings are scored individually for debugging but never selected by truth
    for Top-K. Every hypothesis must cover the exact Ground Truth time extent. Invalid
    time order, incomplete time coverage, forged provenance, and bypass-created schema
    violations fail explicitly instead of silently clipping or extrapolating.
    """
    config = EvaluationConfig.model_validate(config.model_dump(mode="python"))
    constraints = ConstraintConfig.model_validate(constraints.model_dump(mode="python"))
    ground_truth = GroundTruthTrajectory.model_validate(ground_truth.model_dump(mode="python"))
    trajectories = tuple(
        TrajectoryHypothesis.model_validate(trajectory.model_dump(mode="python"))
        for trajectory in trajectories
    )
    if len({trajectory.hypothesis_id for trajectory in trajectories}) != len(trajectories):
        raise ValueError("evaluation hypothesis identities must be unique")
    corridor_segments = None
    if constraints.navigation_graph is not None:
        graph = NavigationGraph(
            NavigationGraphConfig.model_validate(constraints.navigation_graph.model_dump())
        )
        corridor_segments = tuple(
            pair for edge in graph.config.edges for pair in pairwise(edge.polyline)
        ) + tuple((node.position, node.position) for node in graph.config.nodes)
    metrics: list[TrajectoryMetrics] = []
    selected: list[TrajectoryMetrics] = []
    seen_candidates: set[str] = set()
    for trajectory in trajectories:
        if (
            trajectory.timed_points[0].timestamp != ground_truth.samples[0].timestamp
            or trajectory.timed_points[-1].timestamp != ground_truth.samples[-1].timestamp
        ):
            raise ValueError("trajectory and Ground Truth must have exactly matching time extents")
        errors = tuple(
            _finite(math.dist(_position_at(trajectory, float(sample.timestamp)), sample.position))
            for sample in ground_truth.samples
        )
        metric = TrajectoryMetrics(
            hypothesis_id=trajectory.hypothesis_id,
            candidate_id=trajectory.candidate_id,
            ground_truth_sample_count=len(errors),
            ade_m=_finite(math.fsum(errors) / len(errors)),
            fde_m=errors[-1],
            physical=_physical_metrics(trajectory, constraints, corridor_segments),
        )
        metrics.append(metric)
        if trajectory.candidate_id not in seen_candidates:
            seen_candidates.add(trajectory.candidate_id)
            if len(selected) < config.k_routes:
                selected.append(metric)
    min_ade = min((float(metric.ade_m) for metric in selected), default=None)
    min_fde = min((float(metric.fde_m) for metric in selected), default=None)
    segment_count = sum(metric.physical.segment_count for metric in metrics)
    collision_count = sum(metric.physical.collision_segment_count for metric in metrics)
    violation_count = sum(metric.physical.constraint_violation_segment_count for metric in metrics)
    return EvaluationResult(
        config=config,
        trajectory_metrics=tuple(metrics),
        top_k_hypothesis_ids=tuple(metric.hypothesis_id for metric in selected),
        selected_route_count=len(selected),
        evaluated_hypothesis_count=len(metrics),
        min_ade_at_k_m=min_ade,
        min_fde_at_k_m=min_fde,
        coverage_at_k=min_ade is not None and min_ade < config.coverage_epsilon_m,
        total_segment_count=segment_count,
        collision_segment_count=collision_count,
        collision_rate=collision_count / segment_count if segment_count else None,
        constraint_violation_segment_count=violation_count,
        constraint_violation_rate=violation_count / segment_count if segment_count else None,
    )
