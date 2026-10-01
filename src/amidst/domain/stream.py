"""Producer-neutral frame evidence and source-bound aggregation contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel, Pixel2, PositiveFinite, Provenance, Timestamp
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.observation import Observation, ProjectedPoint, Quality
from amidst.domain.trajectory import Event, ReconstructionResult


class OcclusionState(StrEnum):
    CLEAR = "CLEAR"
    OCCLUDED = "OCCLUDED"
    UNKNOWN = "UNKNOWN"


class StreamBinding(DomainModel):
    source_id: str = Field(min_length=1)
    spatial_context_id: str = Field(min_length=1)
    source_asset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    data_kind: Literal["SYNTHETIC", "REAL_CV"] = "SYNTHETIC"


class AggregationPolicy(DomainModel):
    # None applies no arbitrary sampling/duration threshold or recovery merging.
    max_visible_sample_gap_s: PositiveFinite | None = None


class RawProjectedFrameSample(DomainModel):
    """Visible pixels plus their projection, or an explicit missing-evidence marker."""

    sample_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    spatial_context_id: str = Field(min_length=1)
    source_asset_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    timestamp: Timestamp
    frame_id: int = Field(ge=0, strict=True)
    uv: Pixel2 | None
    visibility: VisibilityStatus
    occlusion_state: OcclusionState = OcclusionState.UNKNOWN
    confidence: Quality | None = None
    provenance: Literal[Provenance.OBSERVED, Provenance.PROJECTED] | None
    data_kind: Literal["SYNTHETIC", "REAL_CV"] = "SYNTHETIC"
    projected_point: ProjectedPoint | None = None
    gap_reason: GapReason | None = None
    occluder_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def consistent_evidence(self) -> Self:
        if self.visibility == VisibilityStatus.OBSERVED:
            if self.provenance == Provenance.OBSERVED:
                if self.uv is None:
                    raise ValueError("OBSERVED samples require visible uv evidence")
            elif self.provenance == Provenance.PROJECTED:
                if self.uv is not None or self.projected_point is None:
                    raise ValueError("PROJECTED-only samples require projection and null uv")
            else:
                raise ValueError("visible samples require OBSERVED or PROJECTED provenance")
            if self.gap_reason is not None or self.occluder_id is not None:
                raise ValueError("visible samples cannot carry gap metadata")
            if self.occlusion_state == OcclusionState.OCCLUDED:
                raise ValueError("fully occluded samples cannot carry visible evidence")
        else:
            if (
                self.uv is not None
                or self.provenance is not None
                or self.projected_point is not None
                or self.gap_reason is None
            ):
                raise ValueError("GAP samples require a reason and no pixels/projection/provenance")
            if (
                self.gap_reason == GapReason.OCCLUDED
                and self.occlusion_state != OcclusionState.OCCLUDED
            ):
                raise ValueError("OCCLUDED gap reason requires OCCLUDED state")
            if (
                self.occlusion_state == OcclusionState.OCCLUDED
                and self.gap_reason != GapReason.OCCLUDED
            ):
                raise ValueError("OCCLUDED state requires OCCLUDED gap reason")
            if self.occluder_id is not None and self.occlusion_state != OcclusionState.OCCLUDED:
                raise ValueError("occluder identity requires OCCLUDED state")
        if self.projected_point is not None and (
            self.projected_point.camera_id != self.camera_id
            or self.projected_point.timestamp != self.timestamp
        ):
            raise ValueError("projected point camera/time must match its raw frame sample")
        return self

    @property
    def binding(self) -> StreamBinding:
        return StreamBinding(
            source_id=self.source_id,
            spatial_context_id=self.spatial_context_id,
            source_asset_sha256=self.source_asset_sha256,
            data_kind=self.data_kind,
        )


class BoundObservation(DomainModel):
    binding: StreamBinding
    observation: Observation
    sample_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_sample_ids(self) -> Self:
        if any(not identity for identity in self.sample_ids) or len(set(self.sample_ids)) != len(
            self.sample_ids
        ):
            raise ValueError("bound observation sample identities must be nonempty and unique")
        return self


class ObservationAggregation(DomainModel):
    samples: tuple[RawProjectedFrameSample, ...]
    observations: tuple[BoundObservation, ...]
    policy: AggregationPolicy = AggregationPolicy()

    @model_validator(mode="after")
    def consistent_bindings(self) -> Self:
        by_id = {sample.sample_id: sample for sample in self.samples}
        if len(by_id) != len(self.samples):
            raise ValueError("raw frame sample identities must be unique")
        observation_ids = [item.observation.observation_id for item in self.observations]
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("aggregated observation identities must be unique")
        used: set[str] = set()
        for item in self.observations:
            selected: list[RawProjectedFrameSample] = []
            for sample_id in item.sample_ids:
                if sample_id not in by_id or sample_id in used:
                    raise ValueError(
                        "observation samples must exist and belong to only one segment"
                    )
                used.add(sample_id)
                sample = by_id[sample_id]
                selected.append(sample)
                if (
                    sample.visibility != VisibilityStatus.OBSERVED
                    or sample.binding != item.binding
                    or sample.target_id != item.observation.target_id
                    or sample.camera_id != item.observation.camera_id
                ):
                    raise ValueError(
                        "observation source/context/target/camera must match raw samples"
                    )
            if (
                any(
                    after.timestamp <= before.timestamp
                    for before, after in zip(selected[:-1], selected[1:], strict=True)
                )
                or item.observation.start_time != selected[0].timestamp
                or item.observation.end_time != selected[-1].timestamp
            ):
                raise ValueError("observation time range/order must match its raw samples")
            pixel_samples = [sample for sample in selected if sample.uv is not None]
            projected_samples = [
                sample for sample in selected if sample.projected_point is not None
            ]
            if len(pixel_samples) != len(item.observation.frames) or len(projected_samples) != len(
                item.observation.projected_path
            ):
                raise ValueError(
                    "observation must preserve raw pixels/projections without invention"
                )
            for sample, frame in zip(pixel_samples, item.observation.frames, strict=True):
                if (
                    frame.frame_id != sample.frame_id
                    or frame.timestamp != sample.timestamp
                    or frame.point_2d != sample.uv
                    or frame.data_kind != sample.data_kind
                ):
                    raise ValueError("observation frame must equal its raw source evidence")
            for sample, point in zip(
                projected_samples, item.observation.projected_path, strict=True
            ):
                assert sample.projected_point is not None
                expected = sample.projected_point.model_dump() | {
                    "observation_id": item.observation.observation_id,
                }
                if point.model_dump() != expected:
                    raise ValueError("observation projection must equal its raw source evidence")
        visible = {
            sample.sample_id
            for sample in self.samples
            if sample.visibility == VisibilityStatus.OBSERVED
        }
        if used != visible:
            raise ValueError("aggregation must preserve every visible sample exactly once")
        return self


class BoundGapEvent(DomainModel):
    """One independent blind gap with its exact producer and search bindings."""

    binding: StreamBinding
    start: BoundObservation
    end: BoundObservation
    search_result: ReconstructionResult
    event: Event

    @model_validator(mode="after")
    def consistent_gap(self) -> Self:
        start, end = self.start.observation, self.end.observation
        if self.start.binding != self.binding or self.end.binding != self.binding:
            raise ValueError("gap endpoints must preserve one source/context binding")
        if start.target_id != end.target_id or start.target_id != self.event.target_id:
            raise ValueError("gap and event target identities must match")
        if self.event.observation_ids != (start.observation_id, end.observation_id):
            raise ValueError("gap event must reference its independent endpoint observations")
        if not start.projected_path or not end.projected_path:
            raise ValueError("gap endpoints require projected evidence")
        expected = (start.projected_path[-1].timestamp, end.projected_path[0].timestamp)
        if expected[1] <= expected[0] or self.event.time_range != expected:
            raise ValueError("gap event time range must match its endpoint projected samples")
        if (
            self.event.candidates != self.search_result.candidates
            or self.event.termination_reason != self.search_result.termination_reason
        ):
            raise ValueError("gap event must preserve candidates and search termination")
        return self


@runtime_checkable
class RawFrameProvider(Protocol):
    """Inclusive configured-time query; None selects every camera in the stream."""

    def get_frame_samples(
        self, camera_id: str | None, time_range: tuple[float, float]
    ) -> tuple[RawProjectedFrameSample, ...]: ...
