"""Candidate and event result schemas; geometry/search stays outside domain."""

import math
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, Provenance, Timestamp, Vec3

NonNegativeFinite = Annotated[FiniteFloat, Field(ge=0)]


class TerminationReason(StrEnum):
    COMPLETE = "COMPLETE"
    NO_FEASIBLE_PATH = "NO_FEASIBLE_PATH"
    MAX_PATHS_REACHED = "MAX_PATHS_REACHED"
    MAX_SEARCH_NODES = "MAX_SEARCH_NODES"
    MAX_BRANCH_FACTOR = "MAX_BRANCH_FACTOR"
    SEARCH_TIMEOUT = "SEARCH_TIMEOUT"


class CandidateTrajectory(DomainModel):
    candidate_id: str = Field(min_length=1)
    start_observation_id: str = Field(min_length=1)
    end_observation_id: str = Field(min_length=1)
    polyline: tuple[Vec3, ...] = Field(min_length=2)
    navmesh_corridor: tuple[str, ...] = ()
    path_length: NonNegativeFinite
    minimum_travel_time: NonNegativeFinite
    estimated_travel_time: NonNegativeFinite
    spatial_cost: NonNegativeFinite = 0.0
    temporal_cost: NonNegativeFinite = 0.0
    semantic_regions: tuple[str, ...] = ()
    feasibility_flags: tuple[str, ...] = ()
    path_score: FiniteFloat | None = None
    provenance: Literal[Provenance.INFERRED_GAP] = Provenance.INFERRED_GAP

    @model_validator(mode="after")
    def consistent_travel_times(self) -> Self:
        if self.estimated_travel_time < self.minimum_travel_time:
            raise ValueError("estimated travel time cannot be below minimum travel time")
        return self


class ReconstructionResult(DomainModel):
    candidates: tuple[CandidateTrajectory, ...] = ()
    termination_reason: TerminationReason
    expanded_nodes: int = Field(default=0, ge=0)
    # True means search enumeration was exhausted, not merely that a run ended.
    complete: bool = True
    rejection_reasons: tuple[str, ...] = ()

    @model_validator(mode="after")
    def consistent_termination(self) -> Self:
        if len({candidate.candidate_id for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("reconstruction candidate identities must be unique")
        exhaustive_reasons = {
            TerminationReason.COMPLETE,
            TerminationReason.NO_FEASIBLE_PATH,
        }
        if self.complete != (self.termination_reason in exhaustive_reasons):
            raise ValueError("complete must agree with whether search enumeration was exhausted")
        if self.termination_reason == TerminationReason.NO_FEASIBLE_PATH and self.candidates:
            raise ValueError("NO_FEASIBLE_PATH cannot include candidates")
        return self


class HypothesisKind(StrEnum):
    DIRECT_PATH = "DIRECT_PATH"
    SLOWER_MOVEMENT = "SLOWER_MOVEMENT"
    DWELL = "DWELL"
    DETOUR = "DETOUR"


class SegmentKind(StrEnum):
    MOVEMENT = "MOVEMENT"
    DWELL = "DWELL"


class TimedTrajectoryPoint(DomainModel):
    timestamp: Timestamp
    world_position: Vec3
    provenance: Literal[Provenance.PROJECTED, Provenance.INFERRED_GAP] = Provenance.INFERRED_GAP


class TrajectorySegment(DomainModel):
    time_range: tuple[Timestamp, Timestamp]
    kind: SegmentKind
    provenance: Literal[Provenance.INFERRED_GAP] = Provenance.INFERRED_GAP

    @model_validator(mode="after")
    def ordered_segment(self) -> Self:
        if self.time_range[1] <= self.time_range[0]:
            raise ValueError("trajectory segment must have positive duration")
        return self


class TrajectoryHypothesis(DomainModel):
    """An admissible timing of a supplied route, without a behavioral probability."""

    hypothesis_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    kind: HypothesisKind
    timed_points: tuple[TimedTrajectoryPoint, ...] = Field(min_length=2)
    segments: tuple[TrajectorySegment, ...] = Field(min_length=1)
    minimum_travel_time: NonNegativeFinite
    temporal_slack: NonNegativeFinite
    movement_duration: NonNegativeFinite
    dwell_duration: NonNegativeFinite = 0.0
    uncertainty: str = Field(min_length=1)
    provenance: Literal[Provenance.INFERRED_GAP] = Provenance.INFERRED_GAP

    @model_validator(mode="after")
    def consistent_timing(self) -> Self:
        if any(
            after.timestamp <= before.timestamp for before, after in pairwise(self.timed_points)
        ):
            raise ValueError("trajectory points must be strictly time-ordered")
        start, end = self.timed_points[0].timestamp, self.timed_points[-1].timestamp
        duration = end - start
        if not math.isclose(
            self.minimum_travel_time + self.temporal_slack,
            duration,
            rel_tol=1e-12,
            abs_tol=1e-9,
        ):
            raise ValueError("temporal slack must equal gap duration minus minimum travel time")
        if not math.isclose(
            self.movement_duration + self.dwell_duration,
            duration,
            rel_tol=1e-12,
            abs_tol=1e-9,
        ):
            raise ValueError("movement and dwell durations must cover the gap")
        if self.movement_duration < self.minimum_travel_time:
            raise ValueError("movement duration cannot be below minimum travel time")
        if self.segments[0].time_range[0] != start or self.segments[-1].time_range[1] != end:
            raise ValueError("trajectory segments must span the sampled time range")
        if any(
            first.time_range[1] != second.time_range[0] for first, second in pairwise(self.segments)
        ):
            raise ValueError("trajectory segments must be contiguous")
        movement = math.fsum(
            segment.time_range[1] - segment.time_range[0]
            for segment in self.segments
            if segment.kind == SegmentKind.MOVEMENT
        )
        dwell = math.fsum(
            segment.time_range[1] - segment.time_range[0]
            for segment in self.segments
            if segment.kind == SegmentKind.DWELL
        )
        if not math.isclose(movement, self.movement_duration, rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("movement segments must agree with movement duration")
        if not math.isclose(dwell, self.dwell_duration, rel_tol=1e-12, abs_tol=1e-9):
            raise ValueError("dwell segments must agree with dwell duration")
        timestamps = {point.timestamp for point in self.timed_points}
        for segment in self.segments:
            if any(boundary not in timestamps for boundary in segment.time_range):
                raise ValueError("trajectory segment boundaries must coincide with timed points")
            covered = tuple(
                point
                for point in self.timed_points
                if segment.time_range[0] <= point.timestamp <= segment.time_range[1]
            )
            if segment.kind == SegmentKind.DWELL and any(
                before.world_position != after.world_position for before, after in pairwise(covered)
            ):
                raise ValueError("DWELL segment must remain at one position")
            if segment.kind == SegmentKind.MOVEMENT and any(
                before.world_position == after.world_position for before, after in pairwise(covered)
            ):
                raise ValueError("MOVEMENT segment cannot contain a stationary interval")
        if (self.kind == HypothesisKind.DWELL) != (self.dwell_duration > 0):
            raise ValueError("DWELL hypothesis kind must agree with a positive dwell duration")
        return self


class Event(DomainModel):
    event_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    time_range: tuple[Timestamp, Timestamp]
    observation_ids: tuple[str, ...]
    candidates: tuple[CandidateTrajectory, ...]
    termination_reason: TerminationReason
    trajectories: tuple[TrajectoryHypothesis, ...] = ()

    @model_validator(mode="after")
    def consistent_event(self) -> Self:
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("event time_range must be ordered")
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("event observation identities must be unique")
        if any(not observation_id for observation_id in self.observation_ids):
            raise ValueError("event observation identities cannot be empty")
        if len({candidate.candidate_id for candidate in self.candidates}) != len(self.candidates):
            raise ValueError("event candidate identities must be unique")
        if self.termination_reason == TerminationReason.NO_FEASIBLE_PATH and self.candidates:
            raise ValueError("NO_FEASIBLE_PATH event cannot include candidates")
        observations = set(self.observation_ids)
        if any(
            candidate.start_observation_id not in observations
            or candidate.end_observation_id not in observations
            for candidate in self.candidates
        ):
            raise ValueError("event candidate endpoints must reference event observations")
        if len({trajectory.hypothesis_id for trajectory in self.trajectories}) != len(
            self.trajectories
        ):
            raise ValueError("event hypothesis identities must be unique")
        candidates = {candidate.candidate_id for candidate in self.candidates}
        for trajectory in self.trajectories:
            if trajectory.candidate_id not in candidates:
                raise ValueError("event trajectory must reference an event candidate")
            if (
                trajectory.timed_points[0].timestamp < self.time_range[0]
                or trajectory.timed_points[-1].timestamp > self.time_range[1]
            ):
                raise ValueError("event trajectory lies outside event time_range")
        return self
