"""Strict GT-free inputs for a small Blender pilot consumer.

Mixed simulation exports must be sanitized by an export-stage tool first.
This module reads only 2D evidence and independent, explicit projection context.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from amidst.domain.camera import Camera
from amidst.domain.common import DomainModel, Vec3
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.domain.pipeline import PipelineConfig
from amidst.domain.stream import (
    BoundGapEvent,
    ObservationAggregation,
    OcclusionState,
    RawProjectedFrameSample,
    StreamBinding,
)
from amidst.events import reconstruct_gaps
from amidst.geometry.inverse_projection import InverseProjectionService
from amidst.observation.aggregation import aggregate_frames, validate_stream_model
from amidst.storage.json_files import write_json

PILOT_LABEL = "PILOT / SYNTHETIC SAMPLE"
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Identity = Annotated[str, Field(min_length=1)]

type PilotFrameProjector = Callable[
    ["PilotObservationExport", "PilotInferenceContext"], FrameSampleDataset,
]


class PilotZoneContext(DomainModel):
    floor_id: Identity
    zone_id: Identity
    walkable_object_id: Identity
    bounds_min: Vec3
    bounds_max: Vec3
    authority: Literal["ANNOTATION_AABB_ONLY_PROVISIONAL"]

    @model_validator(mode="after")
    def ordered_bounds(self) -> Self:
        if any(low > high for low, high in zip(self.bounds_min, self.bounds_max, strict=True)):
            raise ValueError("pilot annotation bounds must be ordered")
        if any(self.bounds_min[axis] >= self.bounds_max[axis] for axis in (0, 1)):
            raise ValueError("pilot annotation envelope requires positive XY extent")
        return self


class PilotInferenceContext(DomainModel):
    label: Literal["PILOT / SYNTHETIC SAMPLE"]
    data_kind: Literal["SYNTHETIC"]
    site_id: Identity
    source_id: Identity
    spatial_context_id: Identity
    source_asset_sha256: Digest
    observations_sha256: Digest
    cameras: tuple[Camera, ...] = Field(min_length=2, max_length=3)
    plane: Plane
    zone: PilotZoneContext
    coordinate_units: Literal["BLENDER_SCENE_UNITS"] = "BLENDER_SCENE_UNITS"
    scale_authority: Literal["UNVERIFIED"] = "UNVERIFIED"
    plane_authority: Literal["PILOT_DIAGNOSTIC_ONLY_NOT_FORMAL_FLOOR_BINDING"] = (
        "PILOT_DIAGNOSTIC_ONLY_NOT_FORMAL_FLOOR_BINDING"
    )

    @model_validator(mode="after")
    def consistent_context(self) -> Self:
        camera_ids = [camera.camera_id for camera in self.cameras]
        if len(set(camera_ids)) != len(camera_ids):
            raise ValueError("pilot camera identities must be unique")
        if any(camera.floor_id != self.zone.floor_id for camera in self.cameras):
            raise ValueError("pilot camera floors must match the explicit local zone")
        if self.plane.floor_id != self.zone.floor_id or self.plane.zone_id != self.zone.zone_id:
            raise ValueError("pilot plane floor/zone must match the explicit local zone")
        return self

    @property
    def binding(self) -> StreamBinding:
        return StreamBinding(
            source_id=self.source_id,
            spatial_context_id=self.spatial_context_id,
            source_asset_sha256=self.source_asset_sha256,
            data_kind=self.data_kind,
        )


class PilotObservationExport(DomainModel):
    """The existing pilot's sanitized observations.json contract, with no GT fields."""

    label: Literal["PILOT / SYNTHETIC SAMPLE"]
    data_kind: Literal["SYNTHETIC"]
    source_asset_sha256: Digest
    site_id: Identity
    frames: tuple[ObservationFrame, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def synthetic_target(self) -> Self:
        if any(frame.data_kind != "SYNTHETIC" for frame in self.frames):
            raise ValueError("pilot observations must preserve SYNTHETIC provenance")
        if len({frame.target_id for frame in self.frames}) != 1:
            raise ValueError("this bounded pilot consumer requires exactly one target")
        return self


@dataclass(frozen=True, slots=True)
class PilotProjection:
    context: PilotInferenceContext
    frames: FrameSampleDataset
    binding: StreamBinding
    observations_sha256: str
    context_sha256: str
    projected_observed_count: int
    gap_without_projection_count: int


def project_pilot_observations(
    observations: PilotObservationExport, context: PilotInferenceContext,
) -> FrameSampleDataset:
    """Inverse-project visible pixels only; GAP never receives hidden coordinates."""
    observations = validate_stream_model(observations, PilotObservationExport)
    context = validate_stream_model(context, PilotInferenceContext)
    if (
        observations.source_asset_sha256 != context.source_asset_sha256
        or observations.site_id != context.site_id
    ):
        raise ValueError("pilot observations and projection context source/site must match")
    cameras = {camera.camera_id: camera for camera in context.cameras}
    if {frame.camera_id for frame in observations.frames} != set(cameras):
        raise ValueError("pilot frame camera set must match the configured calibration")
    services = {
        camera_id: InverseProjectionService(camera, context.plane)
        for camera_id, camera in cameras.items()
    }
    samples = []
    for frame in observations.frames:
        point = None
        if frame.status == VisibilityStatus.OBSERVED:
            point = services[frame.camera_id].project_frame(frame)
        state = OcclusionState.CLEAR if frame.status == VisibilityStatus.OBSERVED else (
            OcclusionState.OCCLUDED if frame.gap_reason == GapReason.OCCLUDED
            else OcclusionState.UNKNOWN
        )
        sample_digest = hashlib.sha256(
            f"{context.source_id}\0{frame.target_id}\0{frame.camera_id}\0{frame.frame_id}".encode()
        ).hexdigest()
        samples.append(RawProjectedFrameSample(
            sample_id=f"pilot-frame:{sample_digest}",
            **context.binding.model_dump(mode="python"),
            target_id=frame.target_id, camera_id=frame.camera_id,
            timestamp=frame.timestamp, frame_id=frame.frame_id, uv=frame.point_2d,
            visibility=frame.status, occlusion_state=state, provenance=frame.provenance,
            projected_point=point, gap_reason=frame.gap_reason, occluder_id=frame.occluder_id,
        ))
    # The ordinary aggregator rejects duplicate identities/times and preserves order.
    canonical = aggregate_frames(tuple(samples))
    return FrameSampleDataset(samples=canonical.samples)


def load_pilot_projection(
    observations_path: Path, context_path: Path, *, projector: PilotFrameProjector | None = None,
) -> PilotProjection:
    """Read only strict 2D evidence and strict context; no mixed export/plan/GT reads."""
    evidence_bytes = observations_path.read_bytes()
    context_bytes = context_path.read_bytes()
    context = PilotInferenceContext.model_validate_json(context_bytes)
    digest = hashlib.sha256(evidence_bytes).hexdigest()
    if digest != context.observations_sha256:
        raise ValueError("pilot observations content SHA-256 differs from context binding")
    observations = PilotObservationExport.model_validate_json(evidence_bytes)
    if projector is None:
        frames = project_pilot_observations(observations, context)
    else:
        if (
            observations.source_asset_sha256 != context.source_asset_sha256
            or observations.site_id != context.site_id
            or {frame.camera_id for frame in observations.frames}
            != {camera.camera_id for camera in context.cameras}
        ):
            raise ValueError("additive projection inputs must preserve source/site/camera binding")
        frames = validate_stream_model(projector(observations, context), FrameSampleDataset)
        original = {(f.camera_id, f.frame_id, f.timestamp, f.target_id): f
                    for f in observations.frames}
        if len(frames.samples) != len(observations.frames) or {
            (s.camera_id, s.frame_id, s.timestamp, s.target_id) for s in frames.samples
        } != set(original):
            raise ValueError("additive projection must preserve every original evidence identity")
        for sample in frames.samples:
            key = (sample.camera_id, sample.frame_id, sample.timestamp, sample.target_id)
            frame = original[key]
            if (
                sample.binding != context.binding or sample.uv != frame.point_2d
                or sample.visibility != frame.status or sample.provenance != frame.provenance
                or sample.gap_reason != frame.gap_reason or sample.occluder_id != frame.occluder_id
            ):
                raise ValueError("additive projection must preserve binding and raw evidence")
    visible_count = sum(s.projected_point is not None for s in frames.samples)
    return PilotProjection(
        context=context, frames=frames, binding=context.binding,
        observations_sha256=digest, context_sha256=hashlib.sha256(context_bytes).hexdigest(),
        projected_observed_count=visible_count,
        gap_without_projection_count=sum(
            s.visibility == VisibilityStatus.GAP for s in frames.samples
        ),
    )


@dataclass(frozen=True, slots=True)
class PilotInferenceRun:
    projection: PilotProjection
    aggregation: ObservationAggregation
    pipeline: PipelineConfig
    gaps: tuple[BoundGapEvent, ...]
    report: dict[str, object]


def _file_digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run_pilot_downstream(
    observations_path: Path, context_path: Path, output_directory: Path,
    *, lateral_offset_scene_units: float = 12.0, max_speed_scene_units_s: float = 32.0,
    max_candidate_paths: int = 3, random_seed: int = 42,
    projector: PilotFrameProjector | None = None,
) -> PilotInferenceRun:
    """Run ordinary consumers without accepting a truth/plan/mixed-export path."""
    from amidst.datasets.pilot_topology import build_pilot_pipeline
    from amidst.datasets.providers import BlenderDataset

    projection = load_pilot_projection(observations_path, context_path, projector=projector)
    provider = BlenderDataset(projection.frames, projection.binding)
    aggregation = provider.aggregate(provider.time_range)
    pipeline, topology_evidence = build_pilot_pipeline(
        aggregation, projection.context,
        lateral_offset_scene_units=lateral_offset_scene_units,
        max_speed_scene_units_s=max_speed_scene_units_s,
        max_candidate_paths=max_candidate_paths,
    )
    gaps = reconstruct_gaps(
        aggregation, pipeline, dataset_id=projection.context.source_id,
        random_seed=random_seed,
    )
    if len(gaps) != 1:
        raise ValueError("this pilot runner requires exactly one independently bounded gap")
    gap_timestamps = [
        timestamp
        for timestamp, samples in groupby(aggregation.samples, key=lambda sample: sample.timestamp)
        if not any(sample.visibility == VisibilityStatus.OBSERVED for sample in samples)
    ]
    report: dict[str, object] = {
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC",
        "purpose": "PILOT_DOWNSTREAM_INFERENCE_ONLY",
        "source_asset_sha256": projection.context.source_asset_sha256,
        "source_id": projection.context.source_id,
        "spatial_context_id": projection.context.spatial_context_id,
        "input_observations_sha256": projection.observations_sha256,
        "input_context_sha256": projection.context_sha256,
        "camera_ids": [camera.camera_id for camera in projection.context.cameras],
        "raw_sample_count": len(projection.frames.samples),
        "timestamp_count": len({sample.timestamp for sample in projection.frames.samples}),
        "projected_observed_count": projection.projected_observed_count,
        "gap_without_projection_count": projection.gap_without_projection_count,
        "global_gap_timestamps": gap_timestamps,
        "observation_count": len(aggregation.observations),
        "observation_windows": [
            {
                "camera_id": bound.observation.camera_id,
                "start_time": bound.observation.start_time,
                "end_time": bound.observation.end_time,
                "visible_sample_count": len(bound.sample_ids),
            }
            for bound in aggregation.observations
        ],
        "gap_count": len(gaps),
        "gap_window": gaps[0].event.time_range,
        "candidate_count": len(gaps[0].search_result.candidates),
        "hypothesis_count": len(gaps[0].event.trajectories),
        "termination_reason": gaps[0].search_result.termination_reason.value,
        "enumeration_complete": gaps[0].search_result.complete,
        "rejection_reasons": gaps[0].search_result.rejection_reasons,
        "coordinate_units": projection.context.coordinate_units,
        "physical_scale_authority": projection.context.scale_authority,
        "plane_authority": projection.context.plane_authority,
        "navigation_authority": projection.context.zone.authority,
        "physical_collision_authority": "UNVALIDATED_PROVISIONAL",
        "configured_max_speed_scene_units_s": max_speed_scene_units_s,
        "configured_lateral_offset_scene_units": lateral_offset_scene_units,
        "configured_max_candidate_paths": max_candidate_paths,
        "random_seed": random_seed,
        "ground_truth_read": False,
        "formal_benchmark_executed": False,
        "formal_benchmark_semantics_modified": False,
    }
    if projector is not None:
        report["additive_projection_adapter_applied"] = True
        report["observed_without_available_projection_count"] = sum(
            sample.visibility == VisibilityStatus.OBSERVED and sample.projected_point is None
            for sample in projection.frames.samples
        )
    # Verify both content-bound inputs again before publishing inference artifacts.
    if (
        _file_digest(observations_path) != projection.observations_sha256
        or _file_digest(context_path) != projection.context_sha256
    ):
        raise ValueError("pilot inference input changed while consumers were running")
    output_directory.mkdir(parents=True, exist_ok=False)
    protected = (observations_path, context_path)
    payloads: dict[str, object] = {
        "projected_frames.json": {
            "label": PILOT_LABEL, "dataset": projection.frames.model_dump(mode="json"),
        },
        "aggregation.json": {
            "label": PILOT_LABEL, "aggregation": aggregation.model_dump(mode="json"),
        },
        "pipeline_config.json": {
            "label": PILOT_LABEL, "pipeline": pipeline.model_dump(mode="json"),
        },
        "topology_evidence.json": {"label": PILOT_LABEL, "evidence": topology_evidence},
        "gap_events.json": {
            "label": PILOT_LABEL, "gaps": [gap.model_dump(mode="json") for gap in gaps],
        },
        "candidates.json": {
            "label": PILOT_LABEL,
            "results": [gap.search_result.model_dump(mode="json") for gap in gaps],
        },
        "events.json": {
            "label": PILOT_LABEL, "events": [gap.event.model_dump(mode="json") for gap in gaps],
        },
        "inference_report.json": report,
    }
    for name, payload in payloads.items():
        write_json(output_directory / name, payload, protected_inputs=protected)
    lines = [
        f"# {PILOT_LABEL} — downstream inference", "",
        f"- {report['raw_sample_count']} pure evidence samples; "
        f"{report['projected_observed_count']} inverse-projected visible samples; "
        f"{report['gap_without_projection_count']} GAP records without projection.",
        f"- {report['observation_count']} Observation segments; one endpoint-bounded gap "
        f"{report['gap_window']} seconds.",
        f"- {report['candidate_count']} candidate routes; {report['hypothesis_count']} timed "
        f"hypotheses; termination {report['termination_reason']}; exhaustive enumeration "
        f"{report['enumeration_complete']}.",
        "- Inputs: sanitized 2D observations, source-bound camera calibration and static "
        "diagnostic landmark plane, explicit provisional topology configuration.",
        "- Coordinate units are native Blender scene units. Physical scale, floor/plane "
        "authority and mesh/body collision certification remain unverified.",
        "- No GT, mixed simulation export or trajectory plan was read. "
        "No formal benchmark or Case 1–3 execution.", "",
    ]
    (output_directory / "inference_report.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(output_directory / "digests.json", {
        "label": PILOT_LABEL,
        "inputs": {
            "observations": projection.observations_sha256,
            "context": projection.context_sha256,
        },
        "outputs": {
            name: _file_digest(output_directory / name)
            for name in (*payloads, "inference_report.md")
        },
    }, protected_inputs=protected)
    return PilotInferenceRun(projection, aggregation, pipeline, gaps, report)
