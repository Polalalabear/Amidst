"""Deterministic producer-neutral frame to Observation aggregation."""

from amidst.observation.aggregation import AggregationInputError, aggregate_frames
from amidst.observation.providers import AggregatingObservationProvider, InMemoryRawFrameProvider

__all__ = [
    "AggregationInputError",
    "AggregatingObservationProvider",
    "InMemoryRawFrameProvider",
    "aggregate_frames",
]
