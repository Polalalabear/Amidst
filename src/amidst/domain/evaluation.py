"""Evaluation-only metric contracts with explicit synthetic benchmark settings."""

from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, PositiveInt, model_validator

from amidst.domain.common import DomainModel, PositiveFinite, Vec3
from amidst.domain.navigation import NavigationGraphConfig

NonNegativeFinite = Annotated[FiniteFloat, Field(ge=0)]
Rate = Annotated[FiniteFloat, Field(ge=0, le=1)]


class EvaluationConfig(DomainModel):
    k_routes: PositiveInt = 3
    coverage_distance: Literal["ADE"] = "ADE"
    coverage_epsilon_m: PositiveFinite = 1e-6
    benchmark_kind: Literal["SYNTHETIC_TEST_FIXTURE"] = "SYNTHETIC_TEST_FIXTURE"


class AABBObstacle(DomainModel):
    """Closed explicit obstacle box; boundary contact counts as collision."""

    obstacle_id: str = Field(min_length=1)
    minimum: Vec3
    maximum: Vec3

    @model_validator(mode="after")
    def positive_box_volume(self) -> Self:
        if any(low >= high for low, high in zip(self.minimum, self.maximum, strict=True)):
            raise ValueError("obstacle bounds must have positive extent on all three axes")
        return self


class ConstraintConfig(DomainModel):
    max_speed_m_s: PositiveFinite
    navigation_graph: NavigationGraphConfig | None = None
    obstacles: tuple[AABBObstacle, ...] = ()
    corridor_tolerance_m: PositiveFinite = 1e-6

    @model_validator(mode="after")
    def unique_obstacles(self) -> Self:
        if len({obstacle.obstacle_id for obstacle in self.obstacles}) != len(self.obstacles):
            raise ValueError("obstacle identities must be unique")
        return self


class PhysicalMetrics(DomainModel):
    """Denominator is consecutive timed-point pairs, including stationary dwells."""

    segment_count: int = Field(ge=1)
    collision_segment_count: int = Field(ge=0)
    collision_rate: Rate
    speed_violation_segment_count: int = Field(ge=0)
    speed_violation_rate: Rate
    corridor_segment_count: int = Field(ge=0)
    corridor_violation_segment_count: int = Field(ge=0)
    corridor_violation_rate: Rate | None
    constraint_violation_segment_count: int = Field(ge=0)
    constraint_violation_rate: Rate
    collision_method: Literal["CONTINUOUS_SEGMENT_CLOSED_AABB"] = "CONTINUOUS_SEGMENT_CLOSED_AABB"
    mesh_collision_certified: Literal[False] = False


class TrajectoryMetrics(DomainModel):
    hypothesis_id: str
    candidate_id: str
    ground_truth_sample_count: int = Field(ge=2)
    ade_m: NonNegativeFinite
    fde_m: NonNegativeFinite
    physical: PhysicalMetrics


class EvaluationResult(DomainModel):
    config: EvaluationConfig
    trajectory_metrics: tuple[TrajectoryMetrics, ...]
    # First hypothesis for each route in caller order; never chosen using truth.
    top_k_hypothesis_ids: tuple[str, ...]
    selected_route_count: int = Field(ge=0)
    evaluated_hypothesis_count: int = Field(ge=0)
    min_ade_at_k_m: NonNegativeFinite | None
    min_fde_at_k_m: NonNegativeFinite | None
    coverage_at_k: bool
    total_segment_count: int = Field(ge=0)
    collision_segment_count: int = Field(ge=0)
    collision_rate: Rate | None
    constraint_violation_segment_count: int = Field(ge=0)
    constraint_violation_rate: Rate | None
    time_alignment: Literal["LINEAR_AT_ALL_GROUND_TRUTH_TIMESTAMPS"] = (
        "LINEAR_AT_ALL_GROUND_TRUTH_TIMESTAMPS"
    )
    denominator_definition: Literal["CONSECUTIVE_TIMED_POINT_PAIRS_INCLUDING_DWELL"] = (
        "CONSECUTIVE_TIMED_POINT_PAIRS_INCLUDING_DWELL"
    )
    # Validation rejects discontinuous time order and mismatched evaluation ranges.
    temporal_contract: Literal["STRICTLY_ORDERED_POINTS_AND_EXACT_GROUND_TRUTH_EXTENT"] = (
        "STRICTLY_ORDERED_POINTS_AND_EXACT_GROUND_TRUTH_EXTENT"
    )
    limits: tuple[str, ...] = (
        "Coverage distance and epsilon are synthetic test configuration, not a formal benchmark.",
        "Collision checks cover supplied AABBs only; they do not certify Blender mesh geometry.",
        "Corridor checks use directed configured polylines, not navigation mesh volume.",
        "ADE averages supplied Ground Truth timestamps; it is not a continuous-time integral.",
        "Top-K scores the first timing hypothesis for each candidate route in caller order.",
    )
