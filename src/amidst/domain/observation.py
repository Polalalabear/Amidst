"""Observation/evidence schemas only; no projection or reconstruction algorithms."""

from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, Provenance, Timestamp, Vec3
from amidst.domain.evidence import ObservationFrame, VisibilityStatus

Quality = Annotated[FiniteFloat, Field(ge=0, le=1)]
NonNegativeCount = Annotated[int, Field(ge=0)]


class ProjectedPoint(DomainModel):
    point_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    timestamp: Timestamp
    world_position: Vec3
    projection_quality: Quality = 1.0
    floor_id: str | None = None
    zone_id: str | None = None
    observation_id: str | None = Field(default=None, min_length=1)
    provenance: Literal[Provenance.PROJECTED] = Provenance.PROJECTED


class Observation(DomainModel):
    observation_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    start_time: Timestamp
    end_time: Timestamp
    floor_id: str | None = None
    zone_id: str | None = None
    frames: tuple[ObservationFrame, ...] = ()
    projected_path: tuple[ProjectedPoint, ...] = ()
    provenance: Literal[Provenance.OBSERVED, Provenance.PROJECTED] = Provenance.OBSERVED

    # Preserved Phase 2 fields are nullable, never synthesized from missing data.
    track_ids: tuple[str, ...] | None = None
    stitching_count: NonNegativeCount | None = None
    fragment_count: NonNegativeCount | None = None
    appearance_embedding: tuple[FiniteFloat, ...] | None = None
    appearance_labels: tuple[str, ...] | None = None
    appearance_quality: Quality | None = None
    tracking_quality: Quality | None = None
    source_video_reference: str | None = None
    entry_direction: Vec3 | None = None
    exit_direction: Vec3 | None = None
    projection_quality: Quality | None = None
    occlusion_quality: Quality | None = None
    observation_quality: Quality | None = None

    @model_validator(mode="after")
    def consistent_evidence(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError("observation end_time must not precede start_time")
        if self.provenance == Provenance.OBSERVED and self.projected_path:
            raise ValueError("OBSERVED observation cannot carry a projected_path")
        if self.provenance == Provenance.PROJECTED and not self.projected_path:
            raise ValueError("PROJECTED observation requires a projected_path")
        if any(b.timestamp <= a.timestamp for a, b in pairwise(self.frames)):
            raise ValueError("observation frames must be strictly time-ordered")
        for frame in self.frames:
            if frame.status != VisibilityStatus.OBSERVED:
                raise ValueError("GAP frames cannot be included in an observed evidence segment")
            if frame.camera_id != self.camera_id or frame.target_id != self.target_id:
                raise ValueError("observation frame camera/target identity mismatch")
            if not self.start_time <= frame.timestamp <= self.end_time:
                raise ValueError("observation frame lies outside the declared time window")
        if any(b.timestamp <= a.timestamp for a, b in pairwise(self.projected_path)):
            raise ValueError("projected_path must be strictly time-ordered")
        if len({point.point_id for point in self.projected_path}) != len(self.projected_path):
            raise ValueError("projected_path point identities must be unique")
        for point in self.projected_path:
            if point.camera_id != self.camera_id:
                raise ValueError("projected point camera identity mismatch")
            if point.observation_id is not None and point.observation_id != self.observation_id:
                raise ValueError("projected point observation identity mismatch")
            if not self.start_time <= point.timestamp <= self.end_time:
                raise ValueError("projected point lies outside the declared time window")
        return self
