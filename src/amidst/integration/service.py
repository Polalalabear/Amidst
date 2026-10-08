"""Read canonical repository records without altering the research pipeline."""

from collections.abc import Mapping

from amidst.domain.interfaces import ObservationProvider
from amidst.domain.observation import Observation
from amidst.domain.stream import StreamBinding
from amidst.integration.consumer import ConsumerEvent, ReplayFrame, ReplaySeek, to_consumer_event
from amidst.integration.consumer import replay_frame as make_replay_frame
from amidst.integration.contracts import (
    EventPage,
    EventResponse,
    ObservationPage,
    RecordQuery,
    TrajectoryResponse,
)
from amidst.integration.repositories import IntegrationRepository, RepositorySnapshot
from amidst.observation.aggregation import validate_stream_model


def _matches_binding(binding: StreamBinding, query: RecordQuery) -> bool:
    return (
        (query.source_id is None or binding.source_id == query.source_id)
        and (query.spatial_context_id is None
             or binding.spatial_context_id == query.spatial_context_id)
    )


def _overlaps(time_range: tuple[float, float], query: RecordQuery) -> bool:
    return time_range[0] <= query.time_range[1] and time_range[1] >= query.time_range[0]


class MockIntegrationService:
    """Queries use whole stored segments; provider queries retain their own semantics."""

    def __init__(
        self,
        repository: IntegrationRepository,
        providers: Mapping[str, ObservationProvider] | None = None,
    ) -> None:
        self.repository = repository
        self._providers = dict(providers or {})
        self._snapshot()

    def _snapshot(self) -> RepositorySnapshot:
        return validate_stream_model(self.repository.snapshot(), RepositorySnapshot)

    def observation_provider(self, case_id: str) -> ObservationProvider:
        """Existing window-aggregation port, distinct from canonical record overlap."""
        try:
            return self._providers[case_id]
        except KeyError as error:
            raise LookupError("unknown mock provider case") from error

    def provider_observations(
        self, case_id: str, camera_id: str, time_range: tuple[float, float],
    ) -> tuple[Observation, ...]:
        return self.observation_provider(case_id).get_observations(camera_id, time_range)

    def observations(self, query: RecordQuery) -> ObservationPage:
        query = validate_stream_model(query, RecordQuery)
        items = tuple(
            bound for bound in self._snapshot().observations
            if _matches_binding(bound.binding, query)
            and (query.camera_id is None or bound.observation.camera_id == query.camera_id)
            and (query.target_id is None or bound.observation.target_id == query.target_id)
            and _overlaps((bound.observation.start_time, bound.observation.end_time), query)
        )
        items = tuple(sorted(items, key=lambda bound: (
            bound.observation.start_time, bound.binding.source_id,
            bound.binding.spatial_context_id, bound.observation.target_id,
            bound.observation.camera_id, bound.observation.observation_id,
        )))
        return ObservationPage(query=query, items=items)

    def events(self, query: RecordQuery) -> EventPage:
        query = validate_stream_model(query, RecordQuery)
        items = tuple(
            gap for gap in self._snapshot().gaps
            if _matches_binding(gap.binding, query)
            and (query.target_id is None or gap.event.target_id == query.target_id)
            and (query.camera_id is None or query.camera_id in (
                gap.start.observation.camera_id, gap.end.observation.camera_id,
            ))
            and _overlaps(gap.event.time_range, query)
        )
        items = tuple(sorted(items, key=lambda gap: (
            gap.event.time_range[0], gap.binding.source_id,
            gap.binding.spatial_context_id, gap.event.target_id, gap.event.event_id,
        )))
        return EventPage(query=query, items=items)

    def event(self, event_id: str) -> EventResponse:
        for gap in self._snapshot().gaps:
            if gap.event.event_id == event_id:
                return EventResponse(gap=gap)
        raise LookupError("unknown event")

    def trajectories(self, event_id: str) -> TrajectoryResponse:
        gap = self.event(event_id).gap
        return TrajectoryResponse(
            event_id=event_id, binding=gap.binding,
            termination_reason=gap.event.termination_reason,
            complete=gap.search_result.complete,
            candidates=gap.event.candidates, hypotheses=gap.event.trajectories,
        )

    def consumer(self, event_id: str) -> ConsumerEvent:
        return to_consumer_event(self.event(event_id).gap)

    def replay(self, seek: ReplaySeek) -> ReplayFrame:
        seek = validate_stream_model(seek, ReplaySeek)
        return make_replay_frame(self.event(seek.event_id).gap, seek.timestamp)
