"""Apply versioned metric policy to generic reconstructed trajectories."""

from typing import Self

from pydantic import model_validator

from amidst.domain.common import DomainModel
from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig, EvaluationResult
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.metric_config import MetricConfig
from amidst.domain.trajectory import TrajectoryHypothesis
from amidst.evaluation.metrics import evaluate_trajectories


class ConfiguredEvaluationResult(DomainModel):
    metric_config: MetricConfig
    constraints: ConstraintConfig
    evaluations: tuple[EvaluationResult, ...]

    @model_validator(mode="after")
    def matches_requested_k_values(self) -> Self:
        if (
            tuple(result.config.k_routes for result in self.evaluations)
            != self.metric_config.k_values
        ):
            raise ValueError("configured evaluation must contain every requested K in config order")
        return self

    def for_k(self, k_routes: int) -> EvaluationResult:
        """Return the requested K result; absent K values are not silently evaluated."""
        for result in self.evaluations:
            if result.config.k_routes == k_routes:
                return result
        raise KeyError(f"K={k_routes} was not requested by this metric configuration")


def evaluate_configured_trajectories(
    trajectories: tuple[TrajectoryHypothesis, ...],
    ground_truth: GroundTruthTrajectory,
    metric_config: MetricConfig,
    *,
    constraints: ConstraintConfig,
) -> ConfiguredEvaluationResult:
    """Evaluate each configured K without modifying candidates or their input order.

    Physical domain inputs (speed ceiling, graph, supplied obstacles) come from the
    benchmark's constraint config. MetricConfig is authoritative for metric tolerances;
    the returned constraints record the effective values used in every K evaluation.
    """
    metric_config = MetricConfig.model_validate(metric_config.model_dump(mode="python"))
    constraints = ConstraintConfig.model_validate(constraints.model_dump(mode="python"))
    constraints_payload = constraints.model_dump(mode="python")
    constraints_payload.update(
        collision_tolerance_m=metric_config.collision_tolerance_m,
        speed_relative_tolerance=metric_config.constraint_speed_relative_tolerance,
        corridor_tolerance_m=metric_config.constraint_corridor_tolerance_m,
    )
    effective_constraints = ConstraintConfig.model_validate(constraints_payload)
    results = tuple(
        evaluate_trajectories(
            trajectories,
            ground_truth,
            EvaluationConfig(
                k_routes=k_routes,
                coverage_distance=metric_config.trajectory_distance_metric,
                coverage_epsilon_m=metric_config.coverage_epsilon_m,
            ),
            constraints=effective_constraints,
        )
        for k_routes in metric_config.k_values
    )
    return ConfiguredEvaluationResult(
        metric_config=metric_config,
        constraints=effective_constraints,
        evaluations=results,
    )
