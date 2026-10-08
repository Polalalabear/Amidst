"""Additive snapshot storage contracts; production PostgreSQL remains an interface."""

from __future__ import annotations

from typing import Literal, Protocol, Self

from pydantic import Field, SecretStr, model_validator

from amidst.domain.common import DomainModel
from amidst.domain.stream import BoundGapEvent, BoundObservation
from amidst.observation.aggregation import validate_stream_model


class RepositoryConflictError(ValueError):
    """An existing immutable identity has a different payload."""


class RepositorySnapshot(DomainModel):
    """Canonical synthetic records, including their unchanged Phase 1 bindings."""

    schema_version: Literal["phase2.integration.v1"] = "phase2.integration.v1"
    observations: tuple[BoundObservation, ...] = ()
    gaps: tuple[BoundGapEvent, ...] = ()

    @model_validator(mode="after")
    def consistent_records(self) -> Self:
        observations: dict[str, BoundObservation] = {}
        for item in self.observations:
            validate_stream_model(item, BoundObservation)
            if item.binding.data_kind != "SYNTHETIC" or any(
                frame.data_kind != "SYNTHETIC" for frame in item.observation.frames
            ):
                raise ValueError("integration repositories accept only SYNTHETIC observations")
            identity = item.observation.observation_id
            if identity in observations:
                raise ValueError("repository observation identities must be unique")
            observations[identity] = item
        event_ids: set[str] = set()
        for gap in self.gaps:
            validate_stream_model(gap, BoundGapEvent)
            if gap.binding.data_kind != "SYNTHETIC":
                raise ValueError("integration repositories accept only SYNTHETIC gaps")
            if gap.event.event_id in event_ids:
                raise ValueError("repository event identities must be unique")
            event_ids.add(gap.event.event_id)
            if any(
                observations.get(endpoint.observation.observation_id) != endpoint
                for endpoint in (gap.start, gap.end)
            ):
                raise ValueError("gap endpoints must exactly match stored observations")
        return self


class IntegrationRepository(Protocol):
    """Atomic merge for one writer; exact existing records are idempotent."""

    def snapshot(self) -> RepositorySnapshot: ...

    def add(self, snapshot: RepositorySnapshot) -> None: ...


class PostgreSQLRepositorySettings(DomainModel):
    """Future adapter input only; the foundation never opens a database."""

    dsn: SecretStr = Field(min_length=1)


class PostgreSQLRepositoryFactory(Protocol):
    """Reserved PostgreSQL adapter factory; no driver or concrete implementation."""

    def open(self, settings: PostgreSQLRepositorySettings) -> IntegrationRepository: ...


def _merge_snapshots(
    current: RepositorySnapshot, incoming: RepositorySnapshot,
) -> RepositorySnapshot:
    """Validate the complete merge before a repository changes its stored state."""
    current = validate_stream_model(current, RepositorySnapshot)
    incoming = validate_stream_model(incoming, RepositorySnapshot)
    observations = {
        item.observation.observation_id: item for item in current.observations
    }
    gaps = {item.event.event_id: item for item in current.gaps}
    for observation in incoming.observations:
        identity = observation.observation.observation_id
        existing = observations.get(identity)
        if existing is not None and existing != observation:
            raise RepositoryConflictError(f"conflicting observation identity: {identity}")
        observations[identity] = observation
    for gap in incoming.gaps:
        identity = gap.event.event_id
        existing_gap = gaps.get(identity)
        if existing_gap is not None and existing_gap != gap:
            raise RepositoryConflictError(f"conflicting event identity: {identity}")
        gaps[identity] = gap
    return RepositorySnapshot(observations=tuple(observations.values()), gaps=tuple(gaps.values()))
