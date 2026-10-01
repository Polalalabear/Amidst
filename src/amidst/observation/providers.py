"""Adapt any raw frame provider to the existing ObservationProvider interface."""

import math

from amidst.domain.observation import Observation
from amidst.domain.stream import (
    AggregationPolicy,
    ObservationAggregation,
    RawFrameProvider,
    RawProjectedFrameSample,
)
from amidst.observation.aggregation import (
    AggregationInputError,
    aggregate_frames,
    validate_stream_model,
)


def _validate_range(time_range: tuple[float, float]) -> None:
    if (
        not isinstance(time_range, tuple)
        or len(time_range) != 2
        or any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for value in time_range
        )
    ):
        raise AggregationInputError("query time_range must contain two finite timestamps")
    if time_range[0] < 0 or time_range[1] < time_range[0]:
        raise AggregationInputError("query time_range must be nonnegative and ordered")


class InMemoryRawFrameProvider:
    """Generic configured samples for tests/adapters; no scenario-specific behavior."""

    def __init__(self, samples: tuple[RawProjectedFrameSample, ...]) -> None:
        self._samples = aggregate_frames(samples).samples

    def get_frame_samples(
        self, camera_id: str | None, time_range: tuple[float, float]
    ) -> tuple[RawProjectedFrameSample, ...]:
        _validate_range(time_range)
        return tuple(
            sample
            for sample in self._samples
            if (
                (camera_id is None or sample.camera_id == camera_id)
                and time_range[0] <= sample.timestamp <= time_range[1]
            )
        )


class AggregatingObservationProvider:
    """Keep producer replacement outside Graph/Reconstruction/metrics consumers."""

    def __init__(
        self,
        raw_provider: RawFrameProvider,
        policy: AggregationPolicy | None = None,
    ) -> None:
        self.raw_provider = raw_provider
        self.policy = validate_stream_model(policy or AggregationPolicy(), AggregationPolicy)

    def aggregate(self, time_range: tuple[float, float]) -> ObservationAggregation:
        _validate_range(time_range)
        samples = self.raw_provider.get_frame_samples(None, time_range)
        aggregated = aggregate_frames(samples, self.policy)
        if any(
            not time_range[0] <= sample.timestamp <= time_range[1] for sample in aggregated.samples
        ):
            raise AggregationInputError(
                "raw provider returned evidence outside the requested range"
            )
        return aggregated

    def get_observations(
        self, camera_id: str, time_range: tuple[float, float]
    ) -> tuple[Observation, ...]:
        if not camera_id:
            raise AggregationInputError("camera query identity cannot be empty")
        return tuple(
            item.observation
            for item in self.aggregate(time_range).observations
            if item.observation.camera_id == camera_id
        )
