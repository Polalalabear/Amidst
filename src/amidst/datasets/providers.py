"""Shared provider implementations over sanitized raw-frame contracts."""

from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.observation import Observation
from amidst.domain.stream import (
    AggregationPolicy,
    ObservationAggregation,
    RawProjectedFrameSample,
    StreamBinding,
)
from amidst.observation.aggregation import validate_stream_model
from amidst.observation.providers import AggregatingObservationProvider, InMemoryRawFrameProvider


class JsonFrameDataset:
    """An adapter implementing both raw and aggregated Observation interfaces.

    Providers consume no evaluation references. The Blender adapter only differs
    in requiring a declared source asset hash; all aggregation/search consumers
    use identical schemas and algorithms.
    """

    def __init__(self, dataset: FrameSampleDataset, expected_binding: StreamBinding) -> None:
        dataset = validate_stream_model(dataset, FrameSampleDataset)
        binding = validate_stream_model(expected_binding, StreamBinding)
        if any(sample.binding != binding for sample in dataset.samples):
            raise ValueError("dataset frame source/context binding mismatch")
        self.binding = binding
        self.raw_provider = InMemoryRawFrameProvider(dataset.samples)
        self.time_range: tuple[float, float] = (
            (min(sample.timestamp for sample in dataset.samples),
             max(sample.timestamp for sample in dataset.samples)) if dataset.samples else (0.0, 0.0)
        )

    def get_frame_samples(
        self,
        camera_id: str | None,
        time_range: tuple[float, float],
    ) -> tuple[RawProjectedFrameSample, ...]:
        return self.raw_provider.get_frame_samples(camera_id, time_range)

    def aggregate(
        self,
        time_range: tuple[float, float],
        policy: AggregationPolicy | None = None,
    ) -> ObservationAggregation:
        return AggregatingObservationProvider(self.raw_provider, policy).aggregate(time_range)

    def get_observations(
        self,
        camera_id: str,
        time_range: tuple[float, float],
    ) -> tuple[Observation, ...]:
        return AggregatingObservationProvider(self.raw_provider).get_observations(
            camera_id,
            time_range,
        )


class MockDataset(JsonFrameDataset):
    """Configured mock source, using the same contract as scene-derived frames."""


class BlenderDataset(JsonFrameDataset):
    """Adapter for already sanitized/projected Blender export JSON, never bpy data."""

    def __init__(self, dataset: FrameSampleDataset, expected_binding: StreamBinding) -> None:
        if (
            expected_binding.data_kind != "SYNTHETIC"
            or expected_binding.source_asset_sha256 is None
        ):
            raise ValueError("Blender synthetic datasets require a source asset SHA-256")
        super().__init__(dataset, expected_binding)
