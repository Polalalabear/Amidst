"""Adapt existing mock endpoints into sanitized streams without reading truth geometry."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from amidst.domain.common import Provenance
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.experiment import (
    ArtifactReference,
    DatasetCase,
    DatasetManifest,
    ExperimentConfig,
)
from amidst.domain.metric_config import MetricConfig
from amidst.domain.pipeline import InferenceInput, PipelineConfig
from amidst.domain.stream import OcclusionState, RawProjectedFrameSample
from amidst.experiments.versioning import PIPELINE_VERSION, read_local_bytes
from amidst.storage.json_files import write_json


def samples_from_input(inputs: InferenceInput) -> FrameSampleDataset:
    """Keep projected-only endpoints; never fabricate uv or missing interval positions."""
    inputs = InferenceInput.model_validate(inputs.model_dump(mode="python"))
    rows: list[RawProjectedFrameSample] = []
    frame_counters: dict[str, int] = {}
    for observation in (inputs.start_observation, inputs.end_observation):
        by_time = {frame.timestamp: frame for frame in observation.frames}
        for point in observation.projected_path:
            frame = by_time.get(point.timestamp)
            frame_id = frame.frame_id if frame else frame_counters.get(observation.camera_id, 0)
            frame_counters[observation.camera_id] = frame_id + 1
            rows.append(
                RawProjectedFrameSample(
                    sample_id=point.point_id,
                    source_id=f"mock:{inputs.dataset_id}",
                    spatial_context_id=inputs.navigation.spatial_context_id,
                    source_asset_sha256=inputs.navigation.source_asset_sha256,
                    target_id=observation.target_id,
                    camera_id=observation.camera_id,
                    timestamp=point.timestamp,
                    frame_id=frame_id,
                    uv=frame.point_2d if frame else None,
                    visibility=VisibilityStatus.OBSERVED,
                    provenance=Provenance.OBSERVED if frame else Provenance.PROJECTED,
                    occlusion_state=OcclusionState.UNKNOWN,
                    projected_point=point,
                )
            )
    start, end = inputs.start_observation, inputs.end_observation
    midpoint = (start.projected_path[-1].timestamp + end.projected_path[0].timestamp) / 2
    rows.append(
        RawProjectedFrameSample(
            sample_id=f"{inputs.dataset_id}:gap",
            source_id=f"mock:{inputs.dataset_id}",
            spatial_context_id=inputs.navigation.spatial_context_id,
            source_asset_sha256=inputs.navigation.source_asset_sha256,
            target_id=start.target_id,
            camera_id=start.camera_id,
            timestamp=midpoint,
            frame_id=frame_counters[start.camera_id],
            uv=None,
            visibility=VisibilityStatus.GAP,
            provenance=None,
            gap_reason=GapReason.OUTSIDE_FOV,
            occlusion_state=OcclusionState.UNKNOWN,
        )
    )
    return FrameSampleDataset(samples=tuple(rows))


def _reference(path: Path, relative_path: str) -> ArtifactReference:
    with path.open("rb") as stream:
        return ArtifactReference(
            path=relative_path, sha256=hashlib.file_digest(stream, "sha256").hexdigest()
        )


def export_stream_dataset(legacy_root: Path, destination: Path) -> DatasetManifest:
    """Generate versioned stream inputs; existing outputs are never replaced."""
    cases: list[DatasetCase] = []
    seed: int | None = None
    for source in sorted(legacy_root.glob("*/inference.json")):
        inputs = InferenceInput.model_validate_json(source.read_text())
        if seed is not None and seed != inputs.random_seed:
            raise ValueError("all fixture cases must share a declared seed")
        seed = inputs.random_seed
        folder = destination / inputs.dataset_id
        pipeline = PipelineConfig.model_validate(
            {field: getattr(inputs, field) for field in PipelineConfig.model_fields}
        )
        write_json(folder / "pipeline.json", pipeline.model_dump(mode="json"))
        frames = samples_from_input(inputs)
        write_json(folder / "frames.json", frames.model_dump(mode="json"))
        truth_path = source.parent / "ground_truth.json"
        # Reference fingerprinting is benchmark metadata, not inference geometry input.
        truth_relative = os.path.relpath(truth_path, destination)
        cases.append(
            DatasetCase(
                case_id=inputs.dataset_id,
                source_id=f"mock:{inputs.dataset_id}",
                spatial_context_id=inputs.navigation.spatial_context_id,
                source_asset_sha256=inputs.navigation.source_asset_sha256,
                pipeline=_reference(folder / "pipeline.json", f"{inputs.dataset_id}/pipeline.json"),
                frames=_reference(folder / "frames.json", f"{inputs.dataset_id}/frames.json"),
                evaluation_references=(_reference(truth_path, truth_relative),),
                constraints=_reference(
                    legacy_root / "constraints.json",
                    os.path.relpath(legacy_root / "constraints.json", destination),
                ),
            )
        )
    if seed is None:
        raise ValueError("source has no strict inference inputs")
    manifest = DatasetManifest(
        dataset_id="mock-stream",
        dataset_version="mock-stream-v1",
        seed=seed,
        scene_version="configured-fake-scenes-v1",
        camera_config_version="projected-endpoints-v1",
        topology_version="topology-authorized-v1",
        provider_kind="MOCK_JSON",
        cases=tuple(cases),
    )
    write_json(destination / "dataset.json", manifest.model_dump(mode="json"))
    return manifest


def experiment_config(
    manifest: DatasetManifest,
    dataset_path: Path,
    metric_path: Path,
    *,
    config_directory: Path,
) -> ExperimentConfig:
    metric_config = MetricConfig.model_validate_json(read_local_bytes(metric_path))
    return ExperimentConfig(
        experiment_id="mock-stream-regression-v1",
        dataset_version=manifest.dataset_version,
        seed=manifest.seed,
        scene_version=manifest.scene_version,
        camera_config_version=manifest.camera_config_version,
        topology_version=manifest.topology_version,
        metric_config_version=metric_config.metric_config_version,
        pipeline_version=PIPELINE_VERSION,
        dataset_manifest=_reference(dataset_path, os.path.relpath(dataset_path, config_directory)),
        metric_config=_reference(metric_path, os.path.relpath(metric_path, config_directory)),
    )
