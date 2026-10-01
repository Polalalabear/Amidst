"""Versioned metric semantics independent of a dataset or fixture provider."""

from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, PositiveInt, model_validator

from amidst.domain.common import DomainModel, PositiveFinite

NonNegativeFinite = Annotated[FiniteFloat, Field(ge=0)]
RelativeTolerance = Annotated[FiniteFloat, Field(ge=0, lt=1)]


class MetricConfig(DomainModel):
    """Defaults replay the synthetic regression; formal research values remain open.

    Policy fields expose the supported meanings instead of implying that changing a
    policy string implements a different metric. Unsupported policies are rejected.
    Tolerances are configured numeric allowances, not learned behavioral probabilities
    or proof of Blender mesh collision/clearance.
    """

    metric_config_version: str = Field(default="synthetic-regression-metrics-v1", min_length=1)
    k_values: tuple[PositiveInt, ...] = Field(default=(3,), min_length=1)
    trajectory_distance_metric: Literal["ADE"] = "ADE"
    coverage_epsilon_m: PositiveFinite = 1e-6
    coverage_comparison: Literal["STRICTLY_LESS_THAN"] = "STRICTLY_LESS_THAN"
    interpolation_policy: Literal["PIECEWISE_LINEAR"] = "PIECEWISE_LINEAR"
    temporal_alignment_policy: Literal["ALL_GROUND_TRUTH_TIMESTAMPS_EXACT_EXTENT"] = (
        "ALL_GROUND_TRUTH_TIMESTAMPS_EXACT_EXTENT"
    )
    ade_policy: Literal["ARITHMETIC_MEAN_3D_EUCLIDEAN"] = "ARITHMETIC_MEAN_3D_EUCLIDEAN"
    fde_policy: Literal["LAST_GROUND_TRUTH_TIMESTAMP_3D_EUCLIDEAN"] = (
        "LAST_GROUND_TRUTH_TIMESTAMP_3D_EUCLIDEAN"
    )
    top_k_policy: Literal["FIRST_HYPOTHESIS_PER_DISTINCT_CANDIDATE_IN_INPUT_ORDER"] = (
        "FIRST_HYPOTHESIS_PER_DISTINCT_CANDIDATE_IN_INPUT_ORDER"
    )
    collision_tolerance_m: NonNegativeFinite = 0.0
    collision_tolerance_policy: Literal["EXPAND_CLOSED_AABB"] = "EXPAND_CLOSED_AABB"
    collision_boundary_policy: Literal["CLOSED_AABB_TOUCH_COUNTS"] = "CLOSED_AABB_TOUCH_COUNTS"
    constraint_speed_relative_tolerance: RelativeTolerance = 1e-12
    constraint_corridor_tolerance_m: NonNegativeFinite = 1e-6
    constraint_denominator: Literal["CONSECUTIVE_TIMED_POINT_PAIRS_INCLUDING_DWELL"] = (
        "CONSECUTIVE_TIMED_POINT_PAIRS_INCLUDING_DWELL"
    )
    formal_benchmark_status: Literal["UNRESOLVED"] = "UNRESOLVED"

    @model_validator(mode="after")
    def unique_k_values(self) -> Self:
        if not self.metric_config_version.strip():
            raise ValueError("metric configuration version cannot contain only whitespace")
        if len(set(self.k_values)) != len(self.k_values):
            raise ValueError("metric K values must be unique")
        return self
