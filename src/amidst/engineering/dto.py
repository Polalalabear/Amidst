"""Strict response allowlists; internal records cannot acquire export fields by accident."""

from typing import Literal

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel, Timestamp
from amidst.engineering.access import TaskContext, Tool
from amidst.engineering.facade import EventDetail, EventView, MeasurementView, ObservationView
from amidst.engineering.registry import ResourceRef
from amidst.integration.consumer import ReplayFrame


class PlaceSummary(DomainModel):
    place_id: str
    display_name: str
    model_id: str
    model_revision: str
    resource_ref: ResourceRef


class PlacePage(DomainModel):
    scope: TaskContext
    items: tuple[PlaceSummary, ...]
    ambiguous: bool


class CameraFrame(DomainModel):
    media_ref: ResourceRef
    frame_id: int = Field(ge=0, strict=True)
    timestamp: Timestamp


class CameraSummary(DomainModel):
    camera_id: str
    camera_ref: ResourceRef
    group_ids: tuple[str, ...]
    coverage_status: Literal["UNKNOWN", "CONFIGURED_SYNTHETIC", "REVIEWED_PARTIAL"]
    region_ids: tuple[str, ...]
    origin: Literal["SYNTHETIC"]
    authority: Literal["SYNTHETIC_CONFIG", "SOURCE_VERIFIED_PARTIAL_REVIEW"]
    media_refs: tuple[ResourceRef, ...]
    frames: tuple[CameraFrame, ...]
    time_range: tuple[Timestamp, Timestamp] | None


class CameraPage(DomainModel):
    scope: TaskContext
    items: tuple[CameraSummary, ...]


class InputObservation(DomainModel):
    observation_ref: ResourceRef
    canonical_observation_id: str
    local_track_ref: ResourceRef
    camera_id: str
    camera_ref: ResourceRef
    time_range: tuple[Timestamp, Timestamp]
    evidence_refs: tuple[ResourceRef, ...]
    media_refs: tuple[ResourceRef, ...]
    measurements: tuple[MeasurementView, ...]
    origin: Literal["SYNTHETIC"]
    authority: Literal["CONFIGURED_ENGINEERING_ONLY"]
    image_measurement: Literal[True]
    producer_version: str
    uncertainty: str


class ObservationPage(DomainModel):
    scope: TaskContext
    items: tuple[InputObservation | ObservationView, ...]

    @model_validator(mode="after")
    def stage_allowlist(self) -> "ObservationPage":
        if self.scope.decision_stage == "INPUT" and any(
            not isinstance(item, InputObservation) for item in self.items
        ):
            raise ValueError("input observation fields denied")
        return self


class EventPage(DomainModel):
    scope: TaskContext
    items: tuple[EventView, ...]
    association_hypothesis_count: int = Field(ge=0)


class EventSummaryResponse(EventView):
    scope: TaskContext


class EventDetailResponse(EventDetail):
    scope: TaskContext


class MediaResponse(DomainModel):
    scope: TaskContext
    media_ref: ResourceRef
    camera_ref: ResourceRef
    camera_id: str
    frame_id: int = Field(ge=0, strict=True)
    timestamp: Timestamp
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    origin: Literal["SYNTHETIC"]
    annotations: Literal["NONE"]
    mime_type: Literal["image/png", "image/jpeg"]
    content_base64: str


class ReplayResponse(ReplayFrame):
    scope: TaskContext
    replay_ref: ResourceRef


RESPONSE_TYPES: dict[Tool, type[DomainModel]] = {
    "resolve_place": PlacePage, "list_cameras": CameraPage,
    "query_observations": ObservationPage, "query_events": EventPage,
    "get_event_summary": EventSummaryResponse, "get_event_detail": EventDetailResponse,
    "get_media": MediaResponse, "get_replay": ReplayResponse,
}
