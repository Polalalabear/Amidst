"""Additive backend contracts composed from unchanged Phase 1 models."""

from typing import Literal, Protocol, Self

from pydantic import Field, field_validator, model_validator

from amidst.domain.common import DomainModel, Timestamp
from amidst.domain.stream import BoundGapEvent, BoundObservation, StreamBinding
from amidst.domain.trajectory import (
    CandidateTrajectory,
    TerminationReason,
    TrajectoryHypothesis,
)


class IntegrationMetadata(DomainModel):
    contract_version: Literal["phase2.integration.v1"] = "phase2.integration.v1"
    mode: Literal["MOCK_INTEGRATION_ONLY"] = "MOCK_INTEGRATION_ONLY"
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"
    time_basis: Literal["CONFIGURED_SECONDS"] = "CONFIGURED_SECONDS"
    time_interval: Literal["CLOSED"] = "CLOSED"
    coordinate_system: Literal["BLENDER_RIGHT_HANDED_Z_UP"] = "BLENDER_RIGHT_HANDED_Z_UP"
    units: Literal["METRES"] = "METRES"


class RecordQuery(DomainModel):
    """Inclusive overlap of canonical records; never reaggregate or clip evidence."""

    time_range: tuple[Timestamp, Timestamp]
    camera_id: str | None = Field(default=None, min_length=1)
    target_id: str | None = Field(default=None, min_length=1)
    source_id: str | None = Field(default=None, min_length=1)
    spatial_context_id: str | None = Field(default=None, min_length=1)

    @field_validator("time_range", mode="before")
    @classmethod
    def numeric_times(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)) or any(isinstance(item, bool) for item in value):
            raise ValueError("time_range must contain numeric configured timestamps")
        return value

    @model_validator(mode="after")
    def ordered_range(self) -> Self:
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("time_range must be ordered")
        return self


class ObservationPage(DomainModel):
    metadata: IntegrationMetadata = IntegrationMetadata()
    query: RecordQuery
    items: tuple[BoundObservation, ...]


class EventPage(DomainModel):
    metadata: IntegrationMetadata = IntegrationMetadata()
    query: RecordQuery
    items: tuple[BoundGapEvent, ...]


class EventResponse(DomainModel):
    metadata: IntegrationMetadata = IntegrationMetadata()
    gap: BoundGapEvent


class TrajectoryResponse(DomainModel):
    """All routes and timings, retaining exhaustive versus incomplete search status."""

    metadata: IntegrationMetadata = IntegrationMetadata()
    event_id: str = Field(min_length=1)
    binding: StreamBinding
    termination_reason: TerminationReason
    complete: bool
    candidates: tuple[CandidateTrajectory, ...]
    hypotheses: tuple[TrajectoryHypothesis, ...]


class ApiError(DomainModel):
    metadata: IntegrationMetadata = IntegrationMetadata()
    code: Literal["INVALID_REQUEST", "NOT_FOUND", "METHOD_NOT_ALLOWED"]
    message: str


class EndpointContract(DomainModel):
    method: Literal["GET"] = "GET"
    path: str
    request: str | None = None
    response: str


class ApiContract(DomainModel):
    metadata: IntegrationMetadata = IntegrationMetadata()
    endpoints: tuple[EndpointContract, ...] = (
        EndpointContract(path="/v1/contract", response="ApiContract"),
        EndpointContract(path="/v1/observations", request="RecordQuery",
                         response="ObservationPage"),
        EndpointContract(path="/v1/events", request="RecordQuery", response="EventPage"),
        EndpointContract(path="/v1/events/{event_id}", response="EventResponse"),
        EndpointContract(path="/v1/events/{event_id}/trajectories", response="TrajectoryResponse"),
        EndpointContract(path="/v1/events/{event_id}/consumer", response="ConsumerEvent"),
        EndpointContract(path="/v1/events/{event_id}/replay", request="ReplaySeek",
                         response="ReplayFrame"),
    )
    schemas: dict[str, object]


class BackendAPI(Protocol):
    """Transport-neutral port; a future HTTP framework may wrap the same service."""

    def observations(self, query: RecordQuery) -> ObservationPage: ...

    def events(self, query: RecordQuery) -> EventPage: ...

    def event(self, event_id: str) -> EventResponse: ...

    def trajectories(self, event_id: str) -> TrajectoryResponse: ...
