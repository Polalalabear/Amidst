"""Versioned synthetic presentation contracts; never change inference results."""

from bisect import bisect_left
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from amidst.domain.common import DomainModel, Provenance, Timestamp, Vec3
from amidst.domain.stream import BoundGapEvent
from amidst.observation.aggregation import validate_stream_model


class ConsumerContractError(ValueError):
    """An input is outside the synthetic consumer or configured replay contract."""


def _synthetic_gap(gap: BoundGapEvent) -> BoundGapEvent:
    validated = validate_stream_model(gap, BoundGapEvent)
    if validated.binding.data_kind != "SYNTHETIC" or any(
        frame.data_kind != "SYNTHETIC"
        for bound in (validated.start, validated.end)
        for frame in bound.observation.frames
    ):
        raise ConsumerContractError("Phase 2 consumer accepts SYNTHETIC evidence only")
    return validated


class ConsumerEvent(DomainModel):
    """Lossless envelope: coordinates and seconds retain their Phase 1 meaning."""

    contract_version: Literal["phase2.integration.v1"] = "phase2.integration.v1"
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"
    time_basis: Literal["CONFIGURED_SECONDS"] = "CONFIGURED_SECONDS"
    time_interval: Literal["CLOSED"] = "CLOSED"
    coordinate_system: Literal["BLENDER_RIGHT_HANDED_Z_UP"] = "BLENDER_RIGHT_HANDED_Z_UP"
    units: Literal["METRES"] = "METRES"
    gap: BoundGapEvent

    @model_validator(mode="after")
    def synthetic_evidence_only(self) -> Self:
        _synthetic_gap(self.gap)
        return self


class ReplaySeek(DomainModel):
    event_id: str = Field(min_length=1)
    timestamp: Timestamp

    @field_validator("timestamp", mode="before")
    @classmethod
    def numeric_configured_time(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("replay timestamp must be a number in configured seconds")
        return value


class ReplayMarker(DomainModel):
    hypothesis_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    world_position: Vec3
    provenance: Literal[Provenance.PROJECTED, Provenance.INFERRED_GAP]
    interpolated: bool = Field(strict=True)

    @model_validator(mode="after")
    def display_interpolation_provenance(self) -> Self:
        if self.interpolated and self.provenance != Provenance.INFERRED_GAP:
            raise ValueError("interpolated presentation markers must remain INFERRED_GAP")
        return self


class ReplayFrame(DomainModel):
    """One presentation sample for every hypothesis, retaining declared order."""

    contract_version: Literal["phase2.integration.v1"] = "phase2.integration.v1"
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"
    time_basis: Literal["CONFIGURED_SECONDS"] = "CONFIGURED_SECONDS"
    time_interval: Literal["CLOSED"] = "CLOSED"
    coordinate_system: Literal["BLENDER_RIGHT_HANDED_Z_UP"] = "BLENDER_RIGHT_HANDED_Z_UP"
    units: Literal["METRES"] = "METRES"
    event_id: str = Field(min_length=1)
    timestamp: Timestamp
    markers: tuple[ReplayMarker, ...]

    @model_validator(mode="after")
    def unique_hypotheses(self) -> Self:
        if len({marker.hypothesis_id for marker in self.markers}) != len(self.markers):
            raise ValueError("replay frame hypothesis identities must be unique")
        return self


def to_consumer_event(gap: BoundGapEvent) -> ConsumerEvent:
    """Revalidate the exact domain contracts without projection, ranking or GT."""
    return ConsumerEvent(gap=_synthetic_gap(gap))


def replay_frame(gap: BoundGapEvent, timestamp: float) -> ReplayFrame:
    """Interpolate display markers only; never extrapolate or select alternatives."""
    validated = _synthetic_gap(gap)
    seek = ReplaySeek(event_id=validated.event.event_id, timestamp=timestamp)
    event = validated.event
    if not event.time_range[0] <= seek.timestamp <= event.time_range[1]:
        raise ConsumerContractError("replay timestamp lies outside the closed event time range")
    markers: list[ReplayMarker] = []
    for hypothesis in event.trajectories:
        points = hypothesis.timed_points
        if not points[0].timestamp <= seek.timestamp <= points[-1].timestamp:
            raise ConsumerContractError("replay timestamp lies outside a hypothesis time range")
        index = bisect_left([point.timestamp for point in points], seek.timestamp)
        exact = points[index].timestamp == seek.timestamp
        if exact:
            position, provenance = points[index].world_position, points[index].provenance
        else:
            before, after = points[index - 1], points[index]
            fraction = (seek.timestamp - before.timestamp) / (after.timestamp - before.timestamp)
            position = (
                before.world_position[0]
                + fraction * (after.world_position[0] - before.world_position[0]),
                before.world_position[1]
                + fraction * (after.world_position[1] - before.world_position[1]),
                before.world_position[2]
                + fraction * (after.world_position[2] - before.world_position[2]),
            )
            provenance = Provenance.INFERRED_GAP
        markers.append(ReplayMarker(
            hypothesis_id=hypothesis.hypothesis_id,
            candidate_id=hypothesis.candidate_id,
            world_position=position,
            provenance=provenance,
            interpolated=not exact,
        ))
    return ReplayFrame(event_id=event.event_id, timestamp=seek.timestamp, markers=tuple(markers))
