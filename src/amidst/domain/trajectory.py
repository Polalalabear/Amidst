"""Candidate and event result schemas; geometry/search stays outside domain."""

from enum import StrEnum
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


class Event(DomainModel):
    event_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    time_range: tuple[Timestamp, Timestamp]
    observation_ids: tuple[str, ...]
    candidates: tuple[CandidateTrajectory, ...]
    termination_reason: TerminationReason

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
        observations = set(self.observation_ids)
        if any(
            candidate.start_observation_id not in observations
            or candidate.end_observation_id not in observations
            for candidate in self.candidates
        ):
            raise ValueError("event candidate endpoints must reference event observations")
        return self
