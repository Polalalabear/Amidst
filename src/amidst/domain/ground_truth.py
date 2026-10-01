"""Simulation/export/evaluation-only schemas. Never import into inference modules."""

from itertools import pairwise
from typing import Literal, Self

from pydantic import Field, PositiveInt, model_validator

from amidst.domain.common import DomainModel, Provenance, Timestamp, Vec3


class PathKeyframe(DomainModel):
    timestamp: Timestamp
    position: Vec3
    floor_id: str | None = None
    zone_id: str | None = None
    semantic_region: str | None = None


class TrajectoryConfig(DomainModel):
    trajectory_id: str = "synthetic_trajectory_01"
    target_id: str = "sim_person_01"
    scene_id: str = "SYNTHETIC_TEST_FIXTURE"
    random_seed: int = 0
    sample_rate_hz: PositiveInt = 10
    keyframes: tuple[PathKeyframe, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def ordered_keyframes(self) -> Self:
        if any(b.timestamp <= a.timestamp for a, b in pairwise(self.keyframes)):
            raise ValueError("keyframe timestamps must be strictly increasing")
        return self


class GroundTruthSample(DomainModel):
    timestamp: Timestamp
    position: Vec3
    velocity: Vec3
    floor_id: str | None = None
    zone_id: str | None = None
    semantic_region: str | None = None
    provenance: Literal[Provenance.GROUND_TRUTH] = Provenance.GROUND_TRUTH


class GroundTruthTrajectory(DomainModel):
    trajectory_id: str
    target_id: str
    scene_id: str
    random_seed: int
    sample_rate_hz: PositiveInt
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"
    sample_source: Literal["BLENDER_EVALUATED", "CONFIGURATION_SAMPLER"] = "CONFIGURATION_SAMPLER"
    samples: tuple[GroundTruthSample, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def ordered_samples(self) -> Self:
        if any(b.timestamp <= a.timestamp for a, b in pairwise(self.samples)):
            raise ValueError("sample timestamps must be strictly increasing")
        return self
