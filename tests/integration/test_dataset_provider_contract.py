"""Switch sanitized providers while keeping all inference consumers unchanged."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
import rerun as rr

from amidst.datasets import BlenderDataset, MockDataset
from amidst.datasets.providers import JsonFrameDataset
from amidst.domain.common import Provenance
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.interfaces import ObservationProvider
from amidst.domain.metric_config import MetricConfig
from amidst.domain.pipeline import InferenceInput, PipelineConfig
from amidst.domain.stream import (
    AggregationPolicy,
    BoundGapEvent,
    ObservationAggregation,
    RawFrameProvider,
    RawProjectedFrameSample,
    StreamBinding,
)
from amidst.domain.trajectory import TerminationReason
from amidst.evaluation.configured import evaluate_configured_trajectories
from amidst.events import reconstruct_gaps
from amidst.pipeline import load_inference_input
from amidst.visualization import RerunDebugVisualizationAdapter

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "mock"
# A fixture identity only. This is deliberately not the school source-asset hash.
SYNTHETIC_ASSET_SHA256 = "c" * 64


def _provider_inputs(
    name: str,
) -> tuple[FrameSampleDataset, StreamBinding, PipelineConfig, InferenceInput]:
    inputs = load_inference_input(FIXTURES / name / "inference.json")
    binding = StreamBinding(
        source_id="SYNTHETIC_PROVIDER_CONTRACT",
        spatial_context_id=inputs.navigation.spatial_context_id,
        source_asset_sha256=SYNTHETIC_ASSET_SHA256,
    )
    pipeline = PipelineConfig(
        navigation=inputs.navigation.model_copy(
            update={"source_asset_sha256": SYNTHETIC_ASSET_SHA256}
        ),
        topology=inputs.topology.model_copy(update={"source_asset_sha256": SYNTHETIC_ASSET_SHA256}),
        movement=inputs.movement,
        search_policy=inputs.search_policy,
        reconstruction_policy=inputs.reconstruction_policy,
    )
    samples = []
    for index, observation in enumerate((inputs.start_observation, inputs.end_observation)):
        point = observation.projected_path[0]
        samples.append(
            RawProjectedFrameSample(
                sample_id=f"{name}:visible:{index}",
                **binding.model_dump(),
                target_id=observation.target_id,
                camera_id=observation.camera_id,
                timestamp=point.timestamp,
                frame_id=index * 2,
                uv=None,
                visibility=VisibilityStatus.OBSERVED,
                provenance=Provenance.PROJECTED,
                projected_point=point.model_copy(update={"observation_id": None}),
            )
        )
    start, end = samples
    samples.append(
        RawProjectedFrameSample(
            sample_id=f"{name}:missing",
            **binding.model_dump(),
            target_id=start.target_id,
            camera_id=start.camera_id,
            timestamp=(start.timestamp + end.timestamp) / 2,
            frame_id=1,
            uv=None,
            visibility=VisibilityStatus.GAP,
            provenance=None,
            gap_reason=GapReason.OUTSIDE_FOV,
        )
    )
    return FrameSampleDataset(samples=tuple(samples)), binding, pipeline, inputs


def _inference(
    provider: JsonFrameDataset,
    pipeline: PipelineConfig,
    inputs: InferenceInput,
) -> tuple[ObservationAggregation, tuple[BoundGapEvent, ...]]:
    time_range = (inputs.start_observation.start_time, inputs.end_observation.end_time)
    aggregation = provider.aggregate(time_range, AggregationPolicy())
    gaps = reconstruct_gaps(
        aggregation,
        pipeline,
        dataset_id=inputs.dataset_id,
        random_seed=inputs.random_seed,
        clock=lambda: 0.0,
    )
    return aggregation, gaps


@dataclass
class _RecordingSink:
    """Compare every SDK component value, entity path and timeline timestamp."""

    logs: list[object] = field(default_factory=list)
    current_time: float | None = None

    def log(self, entity_path: str, entity: rr.AsComponents, *, static: bool = False) -> None:
        components = tuple(
            (str(batch.component_descriptor()), batch.as_arrow_array().to_pylist())
            for batch in entity.as_component_batches()
        )
        self.logs.append((entity_path, static, None if static else self.current_time, components))

    def set_time(self, timeline: str, *, duration: float) -> None:
        self.current_time = duration
        self.logs.append(("timeline", timeline, duration))

    def save(self, path: str | Path) -> None:
        raise AssertionError("this contract test compares SDK logs without saving recordings")

    def flush(self) -> None:
        pass

    def disconnect(self) -> None:
        pass


@pytest.mark.parametrize(
    "name,route_count",
    [
        ("single_path", 1),
        ("branching_top_k", 3),
        ("temporal_slack", 2),
        ("simplified_stair", 1),
    ],
)
def test_provider_replacement_preserves_aggregation_top_k_events_metrics_and_rerun(
    name: str,
    route_count: int,
) -> None:
    dataset, binding, pipeline, inputs = _provider_inputs(name)
    providers = (MockDataset(dataset, binding), BlenderDataset(dataset, binding))
    snapshots = []
    for provider in providers:
        assert isinstance(provider, RawFrameProvider)
        protocol_consumer: ObservationProvider = provider
        time_range = (inputs.start_observation.start_time, inputs.end_observation.end_time)
        observations = protocol_consumer.get_observations(
            inputs.start_observation.camera_id,
            time_range,
        )
        assert len(observations) == 1
        aggregation, gaps = _inference(provider, pipeline, inputs)
        assert len(gaps) == 1
        gap = gaps[0]
        assert len(gap.search_result.candidates) == route_count
        assert gap.binding == binding
        assert (
            gap.search_result.termination_reason
            == gap.event.termination_reason
            == (TerminationReason.COMPLETE)
        )
        assert all(candidate.path_score is None for candidate in gap.event.candidates)
        truth = GroundTruthTrajectory.model_validate_json(
            (FIXTURES / name / "ground_truth.json").read_text()
        )
        constraints = ConstraintConfig.model_validate_json(
            (FIXTURES / "constraints.json").read_text()
        )
        constraints = constraints.model_copy(
            update={
                "max_speed_m_s": inputs.movement.max_speed_m_s,
                "navigation_graph": pipeline.navigation,
            }
        )
        metrics = evaluate_configured_trajectories(
            gap.event.trajectories,
            truth,
            MetricConfig(k_values=(1, 3)),
            constraints=constraints,
        )
        assert metrics.for_k(3).coverage_at_k
        assert metrics.for_k(3).collision_rate == metrics.for_k(3).constraint_violation_rate == 0
        if name == "branching_top_k":
            assert not metrics.for_k(1).coverage_at_k
        sink = _RecordingSink()
        visualization = RerunDebugVisualizationAdapter(
            observations=tuple(item.observation for item in aggregation.observations),
            navigation_config=pipeline.navigation,
            topology_config=pipeline.topology,
            recording=sink,
        )
        visualization.log_event(gap.event)
        visualization.log_metrics(metrics.model_dump(mode="json"))
        visualization.close()
        assert sink.logs
        assert not any("debug_ground_truth" in str(log) for log in sink.logs)
        snapshots.append(
            (
                aggregation.model_dump_json(),
                gap.model_dump_json(),
                metrics.model_dump_json(),
                sink.logs,
            )
        )
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("provider_class", [MockDataset, BlenderDataset])
def test_query_contract_is_inclusive_filtered_and_deterministic(
    provider_class: type[JsonFrameDataset],
) -> None:
    dataset, binding, _, inputs = _provider_inputs("single_path")
    provider = provider_class(dataset, binding)
    shuffled = provider_class(
        dataset.model_copy(update={"samples": tuple(reversed(dataset.samples))}), binding
    )
    time_range = (inputs.start_observation.start_time, inputs.end_observation.end_time)
    assert provider.get_frame_samples(None, time_range) == shuffled.get_frame_samples(
        None, time_range
    )
    assert len(provider.get_frame_samples(None, time_range)) == 3
    camera = inputs.start_observation.camera_id
    start_time = inputs.start_observation.start_time
    assert len(provider.get_frame_samples(camera, (start_time, start_time))) == 1
    assert provider.get_frame_samples("UNKNOWN_CAMERA", time_range) == ()
    assert provider.get_observations("UNKNOWN_CAMERA", time_range) == ()
    assert provider.aggregate(time_range) == shuffled.aggregate(time_range)


@pytest.mark.parametrize("provider_class", [MockDataset, BlenderDataset])
def test_provider_rejects_mismatched_source_binding(provider_class: type[JsonFrameDataset]) -> None:
    dataset, binding, _, _ = _provider_inputs("single_path")
    for updates in (
        {"source_id": "other"},
        {"spatial_context_id": "other"},
        {"source_asset_sha256": "d" * 64},
    ):
        with pytest.raises(ValueError, match="binding mismatch"):
            provider_class(dataset, binding.model_copy(update=updates))


def test_future_blender_adapter_requires_explicit_synthetic_asset_binding() -> None:
    dataset, binding, _, _ = _provider_inputs("single_path")
    with pytest.raises(ValueError, match="source asset SHA-256"):
        BlenderDataset(dataset, binding.model_copy(update={"source_asset_sha256": None}))
    with pytest.raises(ValueError, match="source asset SHA-256"):
        BlenderDataset(dataset, binding.model_copy(update={"data_kind": "REAL_CV"}))
