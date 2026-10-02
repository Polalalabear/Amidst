"""Positive fake-geometry detection and the existing closed-AABB tolerance boundary.

These evaluate supplied hypotheses. Graph collision exclusion needs an approved
obstacle input/ownership contract; this suite does not claim that exclusion.
"""

from typing import Any

import pytest

from amidst.domain.evaluation import AABBObstacle, ConstraintConfig
from amidst.domain.metric_config import MetricConfig
from amidst.evaluation.configured import evaluate_configured_trajectories

from .guards_helpers import guards_fixture, guards_numeric_tokens, guards_trajectory, guards_truth

FIXTURE = guards_fixture("guards_collision.json")


@pytest.mark.parametrize("scenario", FIXTURE["scenarios"], ids=lambda item: item["scenario_id"])
def test_continuous_collision_and_clearance_boundary_are_configured_and_deterministic(
    scenario: dict[str, Any],
) -> None:
    case = guards_numeric_tokens(scenario["input"])
    obstacle = AABBObstacle.model_validate(FIXTURE["input"]["obstacle"])
    trajectory = guards_trajectory(case["y"])
    # Both endpoints are outside: this is a positive continuous-segment regression.
    assert trajectory.timed_points[0].world_position[0] < obstacle.minimum[0]
    assert trajectory.timed_points[-1].world_position[0] > obstacle.maximum[0]
    constraints = ConstraintConfig(max_speed_m_s=10, obstacles=(obstacle,), collision_tolerance_m=9)
    config = MetricConfig(k_values=(1,), collision_tolerance_m=case["collision_tolerance_m"])
    results = tuple(
        evaluate_configured_trajectories(
            (trajectory,), guards_truth(case["y"]), config, constraints=constraints,
        )
        for _ in range(5)
    )
    assert all(result == results[0] for result in results)
    assert results[0].constraints.collision_tolerance_m == case["collision_tolerance_m"]
    evaluation = results[0].for_k(1)
    physical = evaluation.trajectory_metrics[0].physical
    expected = scenario["expected"]["collision_count"]
    assert physical.collision_segment_count == evaluation.collision_segment_count == expected
    assert physical.collision_rate == evaluation.collision_rate == expected
    assert physical.constraint_violation_rate == evaluation.constraint_violation_rate == expected
    assert physical.collision_method == "CONTINUOUS_SEGMENT_CLOSED_AABB"
    assert not physical.mesh_collision_certified
    assert evaluation.top_k_hypothesis_ids == (trajectory.hypothesis_id,)
    assert scenario["expected"]["candidates"] == [trajectory.candidate_id]
    assert trajectory.provenance.value == scenario["expected"]["provenance"]
    assert constraints.collision_tolerance_m == 9  # The input remains unchanged.
