"""Producer, aggregation and multi-gap inference never receive hidden truth."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.datasets import BlenderDataset, MockDataset
from amidst.datasets.loading import load_dataset_case
from amidst.datasets.providers import JsonFrameDataset
from amidst.domain.common import Provenance
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.evidence import VisibilityStatus
from amidst.domain.experiment import ArtifactReference, DatasetCase, DatasetManifest
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.metric_config import MetricConfig
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import RawProjectedFrameSample, StreamBinding
from amidst.evaluation.configured import evaluate_configured_trajectories
from amidst.events import EventAggregationError, reconstruct_gaps
from amidst.observation.aggregation import AggregationInputError
from amidst.observation.providers import InMemoryRawFrameProvider
from amidst.pipeline import load_inference_input

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "mock"
SYNTHETIC_ASSET_SHA256 = "c" * 64


def _inputs() -> tuple[FrameSampleDataset, StreamBinding, PipelineConfig]:
    inputs = load_inference_input(FIXTURES / "branching_top_k" / "inference.json")
    binding = StreamBinding(
        source_id="SYNTHETIC_GT_ISOLATION",
        spatial_context_id=inputs.navigation.spatial_context_id,
        source_asset_sha256=SYNTHETIC_ASSET_SHA256,
    )
    samples = tuple(
        RawProjectedFrameSample(
            sample_id=f"isolation:{index}",
            **binding.model_dump(),
            camera_id=observation.camera_id,
            target_id=observation.target_id,
            timestamp=observation.projected_path[0].timestamp,
            frame_id=index,
            uv=None,
            visibility=VisibilityStatus.OBSERVED,
            provenance=Provenance.PROJECTED,
            projected_point=observation.projected_path[0].model_copy(
                update={"observation_id": None}
            ),
        )
        for index, observation in enumerate((inputs.start_observation, inputs.end_observation))
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
    return FrameSampleDataset(samples=samples), binding, pipeline


def _run_inference(provider: JsonFrameDataset, pipeline: PipelineConfig):
    aggregation = provider.aggregate((0, 100))
    gaps = reconstruct_gaps(
        aggregation,
        pipeline,
        dataset_id="SYNTHETIC_GT_ISOLATION",
        random_seed=20261001,
        clock=lambda: 0.0,
    )
    assert len(gaps) == 1 and len(gaps[0].search_result.candidates) == 3
    assert all(candidate.path_score is None for candidate in gaps[0].event.candidates)
    assert "GROUND_TRUTH" not in aggregation.model_dump_json()
    assert "GROUND_TRUTH" not in gaps[0].model_dump_json()
    return aggregation, gaps


def test_new_inference_surfaces_exclude_ground_truth_and_benchmark_consumers() -> None:
    source = ROOT / "src" / "amidst"
    paths = [
        source / "pipeline.py",
        source / "domain" / "pipeline.py",
        source / "domain" / "stream.py",
        source / "domain" / "dataset.py",
    ]
    for folder in ("observation", "events", "datasets", "graph", "navigation", "reconstruction"):
        paths.extend((source / folder).rglob("*.py"))
    forbidden = (
        "ground_truth",
        ".simulation",
        ".evaluation",
        ".visualization",
        ".benchmark",
        ".debug.runner",
    )
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
                assert not any("GroundTruth" in alias.name for alias in node.names), path
            assert not any(word in module for word in forbidden for module in modules), path


class _PoisonedRawProvider(InMemoryRawFrameProvider):
    @property
    def ground_truth(self) -> object:
        raise AssertionError("aggregation or inference attempted to read Ground Truth")

    def get_ground_truth(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("aggregation or inference attempted to request Ground Truth")

    @property
    def future_positions(self) -> object:
        raise AssertionError("aggregation or inference attempted to read future positions")


@pytest.mark.parametrize("provider_class", [MockDataset, BlenderDataset])
def test_raw_provider_hidden_truth_access_is_poisoned_without_breaking_inference(
    provider_class: type[JsonFrameDataset],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, binding, pipeline = _inputs()
    provider = provider_class(dataset, binding)
    provider.raw_provider = _PoisonedRawProvider(dataset.samples)
    original_read_text = Path.read_text

    def read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if "ground_truth" in str(path):
            raise AssertionError("inference attempted to open a Ground Truth file")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    _run_inference(provider, pipeline)


@pytest.mark.parametrize("provider_class", [MockDataset, BlenderDataset])
def test_changed_evaluation_reference_changes_metrics_without_changing_inference(
    provider_class: type[JsonFrameDataset],
) -> None:
    dataset, binding, pipeline = _inputs()
    provider = provider_class(dataset, binding)
    before_aggregation, before_gaps = _run_inference(provider, pipeline)
    truth = GroundTruthTrajectory.model_validate_json(
        (FIXTURES / "branching_top_k" / "ground_truth.json").read_text()
    )
    altered_payload = truth.model_dump(mode="python")
    for sample in altered_payload["samples"]:
        sample["position"] = (
            sample["position"][0],
            sample["position"][1] + 100,
            sample["position"][2],
        )
    altered_truth = GroundTruthTrajectory.model_validate(altered_payload)
    constraints = ConstraintConfig(max_speed_m_s=1, navigation_graph=pipeline.navigation)
    original_metrics = evaluate_configured_trajectories(
        before_gaps[0].event.trajectories,
        truth,
        MetricConfig(),
        constraints=constraints,
    )
    changed_metrics = evaluate_configured_trajectories(
        before_gaps[0].event.trajectories,
        altered_truth,
        MetricConfig(),
        constraints=constraints,
    )
    after_aggregation, after_gaps = _run_inference(provider, pipeline)
    assert original_metrics.for_k(3).coverage_at_k
    assert not changed_metrics.for_k(3).coverage_at_k
    assert before_aggregation == after_aggregation
    assert before_gaps == after_gaps


@pytest.mark.parametrize("provider_kind", ["MOCK_JSON", "BLENDER_SYNTHETIC_JSON"])
def test_case_loading_never_opens_evaluation_references(
    provider_kind: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dataset, binding, pipeline = _inputs()
    pipeline_path, frames_path = tmp_path / "pipeline.json", tmp_path / "frames.json"
    pipeline_path.write_text(pipeline.model_dump_json())
    frames_path.write_text(dataset.model_dump_json())
    case = DatasetCase(
        case_id="SYNTHETIC_REFERENCE_ISOLATION",
        source_id=binding.source_id,
        spatial_context_id=binding.spatial_context_id,
        source_asset_sha256=binding.source_asset_sha256,
        pipeline=ArtifactReference(
            path="pipeline.json", sha256=hashlib.sha256(pipeline_path.read_bytes()).hexdigest()
        ),
        frames=ArtifactReference(
            path="frames.json", sha256=hashlib.sha256(frames_path.read_bytes()).hexdigest()
        ),
        evaluation_references=(
            ArtifactReference(path="ground_truth_must_not_open.json", sha256="f" * 64),
        ),
    )
    manifest = DatasetManifest(
        dataset_id="SYNTHETIC_REFERENCE_ISOLATION",
        dataset_version="1",
        seed=20261001,
        scene_version="SYNTHETIC_TEST_FIXTURE",
        camera_config_version="anchors-v1",
        topology_version="configured-fixture-v1",
        provider_kind=provider_kind,
        cases=(case,),
    )
    original_open = Path.open

    def open_path(path: Path, *args: Any, **kwargs: Any) -> Any:
        if "ground_truth" in str(path):
            raise AssertionError("dataset provider opened an evaluation-only reference")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_path)
    provider, loaded_pipeline = load_dataset_case(manifest, case, tmp_path / "manifest.json")
    assert loaded_pipeline == pipeline
    _run_inference(provider, loaded_pipeline)


@pytest.mark.parametrize("field", ["ground_truth_3d", "ground_truth", "future_position"])
@pytest.mark.parametrize("provider_class", [MockDataset, BlenderDataset])
def test_hidden_truth_fields_are_rejected_at_dataset_and_raw_sample_boundaries(
    field: str,
    provider_class: type[JsonFrameDataset],
) -> None:
    dataset, binding, _ = _inputs()
    payload = dataset.model_dump(mode="python")
    payload[field] = (999, 999, 999)
    with pytest.raises(ValidationError):
        FrameSampleDataset.model_validate(payload)
    del payload[field]
    payload["samples"][0][field] = (999, 999, 999)
    with pytest.raises(ValidationError):
        FrameSampleDataset.model_validate(payload)
    forged_sample = dataset.samples[0].model_copy(update={field: (999, 999, 999)})
    forged_dataset = dataset.model_copy(update={"samples": (forged_sample, *dataset.samples[1:])})
    with pytest.raises(AggregationInputError):
        provider_class(forged_dataset, binding)


@pytest.mark.parametrize("level", ["sample", "projected_point"])
@pytest.mark.parametrize("provider_class", [MockDataset, BlenderDataset])
def test_forged_truth_provenance_cannot_enter_provider_aggregation_or_events(
    level: str,
    provider_class: type[JsonFrameDataset],
) -> None:
    dataset, binding, pipeline = _inputs()
    original = dataset.samples[0]
    if level == "sample":
        forged = original.model_copy(update={"provenance": Provenance.GROUND_TRUTH})
    else:
        assert original.projected_point is not None
        point = original.projected_point.model_copy(update={"provenance": Provenance.GROUND_TRUTH})
        forged = original.model_copy(update={"projected_point": point})
    bad_dataset = dataset.model_copy(update={"samples": (forged, *dataset.samples[1:])})
    with pytest.raises(AggregationInputError):
        provider_class(bad_dataset, binding)
    provider = provider_class(dataset, binding)
    aggregation = provider.aggregate((0, 100))
    first = aggregation.observations[0]
    point = first.observation.projected_path[0].model_copy(
        update={"provenance": Provenance.GROUND_TRUTH}
    )
    observation = first.observation.model_copy(update={"projected_path": (point,)})
    forged_aggregation = aggregation.model_copy(
        update={
            "observations": (
                first.model_copy(update={"observation": observation}),
                *aggregation.observations[1:],
            ),
        }
    )
    with pytest.raises(AggregationInputError):
        reconstruct_gaps(forged_aggregation, pipeline, dataset_id="isolation", random_seed=1)


def test_source_context_and_asset_tampering_is_rejected_before_event_inference() -> None:
    dataset, binding, pipeline = _inputs()
    provider = MockDataset(dataset, binding)
    aggregation = provider.aggregate((0, 100))
    changed_pipeline = pipeline.model_copy(
        update={
            "navigation": pipeline.navigation.model_copy(update={"source_asset_sha256": "d" * 64}),
        }
    )
    with pytest.raises(EventAggregationError, match="source/context"):
        reconstruct_gaps(aggregation, changed_pipeline, dataset_id="isolation", random_seed=1)
