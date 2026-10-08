"""Strict public presentation/retrieval contracts over verified synthetic records."""

from typing import Any, Literal

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel, Timestamp, Vec3
from amidst.domain.trajectory import CandidateTrajectory, TrajectoryHypothesis
from amidst.engineering.access import TaskContext
from amidst.engineering.registry import ResourceRef


class PixelSample(DomainModel):
    frame_ref: ResourceRef
    timestamp: Timestamp
    bbox: tuple[float, float, float, float]
    point_2d: tuple[float, float]
    visible_features: tuple[float, ...]


class PixelObservation(DomainModel):
    observation_ref: ResourceRef
    local_track_ref: ResourceRef
    camera_refs: tuple[ResourceRef, ...]
    camera_ids: tuple[str, ...]
    time_range: tuple[Timestamp, Timestamp]
    media_refs: tuple[ResourceRef, ...]
    measurements: tuple[PixelSample, ...]
    origin: Literal["SYNTHETIC"]
    image_measurement: Literal[True]
    authority: Literal["RGB_PIXELS_WITH_SYNTHETIC_CONFIG"]
    uncertainty: str


class ObservationDetail(PixelObservation):
    region_ids: tuple[str, ...]
    projected_path: tuple[Vec3, ...]


class SourceFrame(DomainModel):
    frame_ref: ResourceRef
    camera_id: str
    timestamp: Timestamp
    evidence_state: Literal["PROJECTED"]


class ProjectedPoint(DomainModel):
    observation_id: str
    local_track_id: str
    camera_id: str
    timestamp: Timestamp
    world_position: Vec3
    uncertainty_m: float = Field(gt=0)
    evidence_state: Literal["PROJECTED"]


class AssociationState(DomainModel):
    association_ref: ResourceRef
    kind: str
    status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE", "UNMATCHED"]
    reason: str


class EventSummary(DomainModel):
    event_ref: ResourceRef
    event_id: str
    kind: str
    time_range: tuple[Timestamp, Timestamp]
    local_track_refs: tuple[ResourceRef, ...]
    segment_refs: tuple[ResourceRef, ...]
    association_refs: tuple[ResourceRef, ...]
    association_states: tuple[AssociationState, ...]
    source_frames: tuple[SourceFrame, ...]
    missing_evidence: tuple[str, ...]
    region_ids: tuple[str, ...]
    portal_ids: tuple[str, ...]
    corner_ids: tuple[str, ...]
    rule_version: str
    config_version: str
    config_sha256: str
    supports: tuple[str, ...]
    conflicts: tuple[str, ...]
    alternatives: tuple[str, ...]
    uncertainty: str
    evidence_state: Literal["PROJECTED", "INFERRED_GAP"]
    canonical_event_id: str | None
    termination_reason: str | None
    complete: bool | None
    candidate_count: int = Field(ge=0, strict=True)
    hypothesis_count: int = Field(ge=0, strict=True)
    detail_ref: ResourceRef
    replay_ref: ResourceRef | None
    origin: Literal["SYNTHETIC"]
    authority: Literal["CONFIGURED_PIXEL_BEHAVIOR_HYPOTHESIS"]
    camera_refs: tuple[ResourceRef, ...]
    camera_ids: tuple[str, ...]
    media_refs: tuple[ResourceRef, ...]


class EventDetail(EventSummary):
    projected_path: tuple[ProjectedPoint, ...]
    candidates: tuple[CandidateTrajectory, ...]
    trajectories: tuple[TrajectoryHypothesis, ...]

    @model_validator(mode="before")
    @classmethod
    def derived_counts(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = dict(value)
            for field, source in (("candidate_count", "candidates"),
                                  ("hypothesis_count", "trajectories")):
                if isinstance(value.get(source), (list, tuple)):
                    count = len(value[source])
                    if field in value and (type(value[field]) is not int
                                           or value[field] != count):
                        raise ValueError("summary count differs from canonical detail")
                    value[field] = count
        return value


class CameraSummary(DomainModel):
    camera_id: str
    camera_ref: ResourceRef
    coverage_status: Literal["UNKNOWN", "CONFIGURED_SYNTHETIC", "REVIEWED_PARTIAL"]
    region_ids: tuple[str, ...]
    origin: Literal["SYNTHETIC"]
    authority: Literal["SYNTHETIC_CONFIG", "SOURCE_VERIFIED_PARTIAL_REVIEW"]


class RetrievalReceipt(DomainModel):
    records_read: int = Field(ge=0)
    frames_read: int = Field(ge=0)
    bytes_read: int = Field(ge=0)
    index_entries_touched: int = Field(ge=0)
    coverage: str
    time_range: tuple[Timestamp, Timestamp]
    truncated: bool
    graph_complete: None


class MediaResponse(DomainModel):
    media_ref: ResourceRef
    camera_id: str
    timestamp: Timestamp
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mime_type: Literal["image/png", "image/jpeg"]
    evidence_state: Literal["RGB_PIXELS"]
    base64: str
    bytes_read: int = Field(ge=0)


class ProductContext(DomainModel):
    session_ref: str
    run_ref: ResourceRef
    context: TaskContext
    product_version: Literal["local-product.v1"] = "local-product.v1"
    product_freeze_ref: str
    operator_ref: ResourceRef
    role: Literal["TRUSTED_LOCAL_OPERATOR"] = "TRUSTED_LOCAL_OPERATOR"
    allowed_tools: tuple[str, ...]
    external_model_calls: Literal[False] = False


class Marker(DomainModel):
    marker_ref: str
    event_ref: ResourceRef
    timestamp: Timestamp
    world_position: Vec3
    evidence_state: Literal["PROJECTED", "INFERRED_GAP"]
    interpolated: bool
    candidate_ref: str | None = None
    hypothesis_ref: str | None = None
    camera_id: str | None = None
    source_frame_ref: ResourceRef | None = None
    sample_offset_seconds: float | None = None


class FrameSelection(DomainModel):
    camera_ref: ResourceRef
    camera_id: str
    media_ref: ResourceRef | None
    frame_timestamp: Timestamp | None
    requested_timestamp: Timestamp
    status: Literal["AVAILABLE", "NO_FRAME_WITHIN_TOLERANCE"]
    offset_seconds: float | None


class TimelineState(DomainModel):
    run_ref: ResourceRef
    timestamp: Timestamp
    frames: tuple[FrameSelection, ...]
    markers: tuple[Marker, ...]
    presentation_only: Literal[True] = True
    synchronization: Literal["SOFT_SYNCHRONIZATION"] = "SOFT_SYNCHRONIZATION"
