"""Use ordinary pipeline consumers for each independently bounded missing interval."""

from __future__ import annotations

from collections.abc import Callable
from itertools import groupby, pairwise
from time import monotonic

from amidst.domain.pipeline import InferenceInput, PipelineConfig
from amidst.domain.stream import BoundGapEvent, ObservationAggregation
from amidst.observation.aggregation import aggregate_frames, validate_stream_model
from amidst.pipeline import reconstruct_input


class EventAggregationError(ValueError):
    """Ambiguous visibility or mismatched source/context must not enter search."""


def reconstruct_gaps(
    aggregation: ObservationAggregation,
    pipeline: PipelineConfig,
    *,
    dataset_id: str,
    random_seed: int,
    clock: Callable[[], float] = monotonic,
) -> tuple[BoundGapEvent, ...]:
    """Build one Event per pair of adjacent visible segments, preserving recovery.

    Target-global ordering spans cameras. Inclusive overlapping/tied visibility
    is ambiguous and rejected before search; no confidence/ranking arbitration is
    invented. A source/context change breaks the chain, never reconnecting across
    an intervening binding. A same-camera continuous stream was already grouped
    into one Observation, so it creates no gap. Endpoint positions are handed to
    the existing configured-node engine without semantic alignment or snapping.
    """
    aggregation = validate_stream_model(aggregation, ObservationAggregation)
    pipeline = validate_stream_model(pipeline, PipelineConfig)
    canonical = aggregate_frames(aggregation.samples, aggregation.policy)
    if canonical != aggregation:
        raise EventAggregationError("observation aggregation must preserve its canonical partition")
    if not isinstance(dataset_id, str) or not dataset_id:
        raise EventAggregationError("dataset_id must be nonempty")
    if isinstance(random_seed, bool) or not isinstance(random_seed, int):
        raise EventAggregationError("random_seed must be an integer")
    navigation, topology = pipeline.navigation, pipeline.topology
    for sample in aggregation.samples:
        binding = sample.binding
        if (
            binding.spatial_context_id != navigation.spatial_context_id
            or binding.spatial_context_id != topology.spatial_context_id
            or binding.source_asset_sha256 != navigation.source_asset_sha256
            or binding.source_asset_sha256 != topology.source_asset_sha256
        ):
            raise EventAggregationError("observation source/context must match topology/navigation")
        if binding.data_kind != "SYNTHETIC":
            raise EventAggregationError(
                "REAL_CV inference is deferred; only its producer contract exists"
            )
    ordered = sorted(
        aggregation.observations,
        key=lambda bound: (
            bound.observation.target_id,
            bound.observation.start_time,
            bound.observation.end_time,
            bound.observation.observation_id,
        ),
    )
    pairs = []
    for _, observations in groupby(ordered, key=lambda bound: bound.observation.target_id):
        for start, end in pairwise(observations):
            if end.observation.start_time <= start.observation.end_time:
                raise EventAggregationError(
                    "overlapping visible segments require unresolved arbitration"
                )
            if start.binding != end.binding:
                continue
            if any(
                sample.target_id == start.observation.target_id
                and start.observation.end_time < sample.timestamp < end.observation.start_time
                and sample.binding != start.binding
                for sample in aggregation.samples
            ):
                continue
            pairs.append((start, end))
    result: list[BoundGapEvent] = []
    for start, end in pairs:
        inputs = InferenceInput(
            dataset_id=dataset_id,
            random_seed=random_seed,
            start_observation=start.observation,
            end_observation=end.observation,
            navigation=navigation,
            topology=topology,
            movement=pipeline.movement,
            search_policy=pipeline.search_policy,
            reconstruction_policy=pipeline.reconstruction_policy,
        )
        search, event = reconstruct_input(inputs, clock=clock)
        result.append(
            BoundGapEvent(
                binding=start.binding,
                start=start,
                end=end,
                search_result=search,
                event=event,
            )
        )
    return tuple(
        sorted(
            result,
            key=lambda gap: (
                gap.event.time_range[0],
                gap.event.target_id,
                gap.event.event_id,
            ),
        )
    )
