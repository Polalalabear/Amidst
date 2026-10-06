"""Additive, GT-free projection composition from the pinned Phase 1 checkpoints.

The existing ProjectedPoint and Graph contracts are unchanged. This sidecar keeps
every observed pixel, every legal multi-view pair and every valid plane result.
It does not certify the pilot camera/landmark-plane bindings as school authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, FiniteFloat

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, PilotObservationExport
from amidst.domain.common import DomainModel
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.observation import ProjectedPoint
from amidst.domain.stream import OcclusionState, RawProjectedFrameSample
from amidst.observation.aggregation import aggregate_frames, validate_stream_model
from amidst.storage.json_files import write_json


class ProjectionPolicy(DomainModel):
    version: Literal["PHASE1_ADDITIVE_PROJECTION_POLICY_V1"] = (
        "PHASE1_ADDITIVE_PROJECTION_POLICY_V1"
    )
    source_checkpoint_sha: Literal["8f4055ffcdc3bf6efd723c7956ac685e1fe033f1"] = (
        "8f4055ffcdc3bf6efd723c7956ac685e1fe033f1"
    )
    minimum_acute_angle_degrees: Annotated[FiniteFloat, Field(gt=0, le=90)] = 1.0
    pixel_sigma_px: Annotated[FiniteFloat, Field(ge=0)] | None = None
    conditioning_rejection_mode: Literal["NONE"] = "NONE"
    multiview_selection: Literal["MIN_LINE_SYSTEM_CONDITION_THEN_CAMERA_IDS"] = (
        "MIN_LINE_SYSTEM_CONDITION_THEN_CAMERA_IDS"
    )
    fixed_plane_selection: Literal["SORTED_CAMERA_ID_ALL_VALID_POINTS_RETAINED"] = (
        "SORTED_CAMERA_ID_ALL_VALID_POINTS_RETAINED"
    )


@lru_cache(maxsize=3)
def _helper(name: str) -> Any:
    if name not in {
        "projection_multiview_model", "projection_mitigation_policy",
        "projection_uncertainty_model",
    }:
        raise ValueError("projection helper is not allowlisted")
    path = Path(__file__).with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("phase1_additive_" + name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("pinned projection helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def _uncertainty_unavailable(reason: str) -> dict[str, object]:
    return {
        "status": "UNAVAILABLE", "reason": reason, "covariance_bu2": None,
        "ground_truth_used": False, "calibrated_probability": False,
        "downstream_policy_applied": False,
    }


def project_exact_time(
    context: PilotInferenceContext,
    frames: tuple[ObservationFrame, ...],
    *,
    policy: ProjectionPolicy | None = None,
) -> dict[str, Any]:
    """Compose one strict exact-time group without file, GT or evaluation inputs.

    The export-loading caller owns the observations file digest verification.
    Contract/binding mismatches raise; missing/legal-pair insufficiency falls back
    to fixed plane. LOW_CONFIDENCE never removes a point or any input evidence.
    """
    context = validate_stream_model(context, PilotInferenceContext)
    current = validate_stream_model(
        ProjectionPolicy() if policy is None else policy, ProjectionPolicy,
    )
    if not isinstance(frames, tuple):
        raise ValueError("frames must be a tuple of strict ObservationFrame models")
    frames = tuple(validate_stream_model(frame, ObservationFrame) for frame in frames)
    frames = tuple(sorted(frames, key=lambda frame: frame.camera_id))
    cameras = {camera.camera_id: camera for camera in context.cameras}
    if len({frame.camera_id for frame in frames}) != len(frames):
        raise ValueError("duplicate camera evidence in exact-time group")
    if any(frame.camera_id not in cameras for frame in frames):
        raise ValueError("camera evidence is outside source calibration binding")
    if any(frame.data_kind != context.data_kind for frame in frames):
        raise ValueError("camera evidence data kind differs from source binding")
    if len({(frame.target_id, frame.timestamp, frame.frame_id) for frame in frames}) > 1:
        raise ValueError("projection group requires exact target, timestamp and frame identity")
    visible = tuple(frame for frame in frames if frame.status == VisibilityStatus.OBSERVED)
    multiview = _helper("projection_multiview_model").triangulate_exact_time(
        context, frames, minimum_acute_angle_degrees=current.minimum_acute_angle_degrees,
    )
    plane_sidecars = []
    for frame in visible:
        camera = cameras[frame.camera_id]
        diagnostic = _helper("projection_mitigation_policy").diagnose_sample(
            camera, context.plane, frame,
        )
        uncertainty = _uncertainty_unavailable("PIXEL_SIGMA_NOT_DECLARED")
        if current.pixel_sigma_px is not None:
            uncertainty = _helper("projection_uncertainty_model").propagate_fixed_plane(
                camera, context.plane, frame, pixel_sigma_px=current.pixel_sigma_px,
            )
        plane_sidecars.append({"conditioning": diagnostic, "uncertainty": uncertainty})
    accepted_planes = [
        row for row in plane_sidecars if row["conditioning"]["projected_point"] is not None
    ]
    selected = None
    selected_ids: list[str] = []
    selected_point = None
    state = "UNAVAILABLE"
    method = "UNAVAILABLE"
    uncertainty = _uncertainty_unavailable("NO_VALID_OBSERVED_PROJECTION")
    if multiview["hypotheses"]:
        selected = min(
            multiview["hypotheses"],
            key=lambda row: (row["line_system_condition_number"], tuple(row["camera_ids"])),
        )
        selected_point = selected["world_position"]
        selected_ids = selected["camera_ids"]
        method = "EXACT_TIME_MULTIVIEW"
        # Geometry is legal, but no calibrated multi-view covariance is available.
        state = "LOW_CONFIDENCE"
        uncertainty = _uncertainty_unavailable("MULTIVIEW_COVARIANCE_NOT_MODELED")
    elif accepted_planes:
        primary = accepted_planes[0]
        point = primary["conditioning"]["projected_point"]
        selected_point = point["world_position"]
        selected_ids = [point["camera_id"]]
        method = "SINGLE_VIEW_FIXED_PLANE"
        uncertainty = primary["uncertainty"]
        low_confidence = primary["conditioning"]["confidence"]["low_confidence"]
        low_confidence |= uncertainty.get("use_state") in {
            "REVIEW_REQUIRED", "UNAVAILABLE_ZERO_VARIANCE",
        }
        low_confidence |= uncertainty.get("status") == "UNAVAILABLE"
        state = "LOW_CONFIDENCE" if low_confidence else "AVAILABLE_WITH_CONDITIONAL_UNCERTAINTY"
    return {
        "label": PILOT_LABEL,
        "policy_status": "PROVISIONAL_NOT_APPROVED_SCHOOL_CAMERA_PLANE_BINDING",
        "version": current.version,
        "policy": current.model_dump(mode="json"),
        "policy_sha256": _digest(current.model_dump(mode="json")),
        "source_id": context.source_id, "site_id": context.site_id,
        "spatial_context_id": context.spatial_context_id,
        "source_asset_sha256": context.source_asset_sha256,
        "observations_sha256": context.observations_sha256,
        "camera_calibration_sha256": _digest([
            cameras[identity].model_dump(mode="json") for identity in sorted(cameras)
        ]),
        "plane": context.plane.model_dump(mode="json"),
        "plane_authority": context.plane_authority,
        "coordinate_units": context.coordinate_units,
        "frame_id": frames[0].frame_id if frames else None,
        "timestamp": frames[0].timestamp if frames else None,
        "target_id": frames[0].target_id if frames else None,
        "input_evidence": [frame.model_dump(mode="json") for frame in frames],
        "observed_count": len(visible), "evidence_rejected_by_confidence": 0,
        "method": method, "state": state,
        "selected_world_position": selected_point,
        "selected_camera_ids": selected_ids,
        "selected_multiview_hypothesis_id": selected["hypothesis_id"] if selected else None,
        "multiview": multiview, "fixed_plane_sidecars": plane_sidecars,
        "uncertainty": uncertainty,
        "selection_uses_ground_truth": False,
        "ground_truth_read": False, "graph_contract_modified": False,
        "surface_constrained_school_inference": "N/A / UNAVAILABLE_AUTHORITY",
        "multiview_unavailable_is_inference_failure": False,
        "confidence_is_calibrated_probability": False,
    }


def project_export(
    context: PilotInferenceContext,
    evidence: PilotObservationExport,
    *,
    policy: ProjectionPolicy | None = None,
) -> dict[str, Any]:
    """Preserve all frames, canonically grouped by exact target/time/frame identity."""
    context = validate_stream_model(context, PilotInferenceContext)
    evidence = validate_stream_model(evidence, PilotObservationExport)
    if (
        evidence.source_asset_sha256 != context.source_asset_sha256
        or evidence.site_id != context.site_id
    ):
        raise ValueError("observations and context source/site must match")
    if {frame.camera_id for frame in evidence.frames} != {cam.camera_id for cam in context.cameras}:
        raise ValueError("export camera set differs from source calibration binding")
    groups: dict[tuple[float, int, str], list[ObservationFrame]] = {}
    identities: set[tuple[str, int, float, str]] = set()
    for frame in evidence.frames:
        identity = (frame.camera_id, frame.frame_id, float(frame.timestamp), frame.target_id)
        if identity in identities:
            raise ValueError("duplicate observation identity")
        identities.add(identity)
        group_identity = (float(frame.timestamp), frame.frame_id, frame.target_id)
        groups.setdefault(group_identity, []).append(frame)
    rows = [
        project_exact_time(context, tuple(groups[key]), policy=policy) for key in sorted(groups)
    ]
    return {
        "label": PILOT_LABEL, "version": "PHASE1_ADDITIVE_PROJECTION_EXPORT_V1",
        "policy_status": "PROVISIONAL_NOT_APPROVED_SCHOOL_CAMERA_PLANE_BINDING",
        "source_asset_sha256": context.source_asset_sha256,
        "observations_sha256": context.observations_sha256,
        "frame_count": len(evidence.frames),
        "retained_evidence_count": sum(len(row["input_evidence"]) for row in rows),
        "ground_truth_read": False, "rows": rows,
    }


def project_policy_frames(
    observations: PilotObservationExport, context: PilotInferenceContext,
    *, policy: ProjectionPolicy | None = None,
) -> FrameSampleDataset:
    """Apply the additive policy through the existing frame/aggregation contract.

    A pair-bound multi-view point replaces the two contributing cameras' plane
    points. Additional views retain their own fixed-plane result. A multi-view
    plane_id explicitly denotes no plane assumption; legacy topology may reject
    such endpoints instead of silently assigning them school floor authority.
    projection_quality is sin(acute parallax), a geometric indicator, not a
    calibrated probability. Full uncertainty/method/evidence remain in sidecars.
    """
    context = validate_stream_model(context, PilotInferenceContext)
    observations = validate_stream_model(observations, PilotObservationExport)
    sidecar = project_export(context, observations, policy=policy)
    rows = {(row["timestamp"], row["frame_id"], row["target_id"]): row
            for row in sidecar["rows"]}
    samples = []
    for frame in observations.frames:
        row = rows[(frame.timestamp, frame.frame_id, frame.target_id)]
        point = None
        if frame.status == VisibilityStatus.OBSERVED:
            if row["method"] == "EXACT_TIME_MULTIVIEW" and frame.camera_id in (
                row["selected_camera_ids"]
            ):
                hypothesis = next(
                    item for item in row["multiview"]["hypotheses"]
                    if item["hypothesis_id"] == row["selected_multiview_hypothesis_id"]
                )
                point = ProjectedPoint(
                    point_id=hypothesis["hypothesis_id"] + ":" + frame.camera_id,
                    camera_id=frame.camera_id, timestamp=frame.timestamp,
                    plane_id="EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION",
                    world_position=hypothesis["world_position"],
                    projection_quality=math.sin(math.radians(
                        hypothesis["acute_parallax_angle_degrees"],
                    )),
                    floor_id=context.zone.floor_id, zone_id=context.zone.zone_id,
                )
            else:
                diagnostic = next(item["conditioning"] for item in row["fixed_plane_sidecars"]
                                  if item["conditioning"]["camera_id"] == frame.camera_id)
                if diagnostic["projected_point"] is not None:
                    point = ProjectedPoint.model_validate(diagnostic["projected_point"])
        state = OcclusionState.CLEAR if frame.status == VisibilityStatus.OBSERVED else (
            OcclusionState.OCCLUDED if frame.gap_reason == GapReason.OCCLUDED
            else OcclusionState.UNKNOWN
        )
        sample_digest = hashlib.sha256(
            f"{context.source_id}\0{frame.target_id}\0{frame.camera_id}\0{frame.frame_id}".encode(),
        ).hexdigest()
        samples.append(RawProjectedFrameSample(
            sample_id=f"pilot-frame:{sample_digest}", **context.binding.model_dump(mode="python"),
            target_id=frame.target_id, camera_id=frame.camera_id,
            timestamp=frame.timestamp, frame_id=frame.frame_id, uv=frame.point_2d,
            visibility=frame.status, occlusion_state=state, provenance=frame.provenance,
            projected_point=point, gap_reason=frame.gap_reason, occluder_id=frame.occluder_id,
        ))
    return FrameSampleDataset(samples=aggregate_frames(tuple(samples)).samples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pixel-sigma-px", type=float, default=None)
    parser.add_argument("--frames-output", type=Path)
    args = parser.parse_args()
    raw = args.observations.read_bytes()
    context = PilotInferenceContext.model_validate_json(args.context.read_bytes())
    if hashlib.sha256(raw).hexdigest() != context.observations_sha256:
        raise ValueError("observations SHA-256 differs from context content binding")
    evidence = PilotObservationExport.model_validate_json(raw)
    policy = ProjectionPolicy(pixel_sigma_px=args.pixel_sigma_px)
    result = project_export(context, evidence, policy=policy)
    write_json(args.output, result, protected_inputs=(args.observations, args.context))
    if args.frames_output is not None:
        frames = project_policy_frames(evidence, context, policy=policy)
        write_json(args.frames_output, {
            "label": PILOT_LABEL, "status": "DIAGNOSTIC_POLICY_PROJECTED_FRAMES",
            "dataset": frames.model_dump(mode="json"),
        }, protected_inputs=(args.observations, args.context))


if __name__ == "__main__":
    main()
