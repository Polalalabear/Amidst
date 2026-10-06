"""Exact-time, GT-free multi-view sidecars; no replacement of production projection.

This diagnostic model binds pixels to the caller's strict PilotInferenceContext.
It does not certify those bindings or verify an observation file digest from a
partial timestamp request. The export-loading caller owns that content check.
All geometrically legal camera pairs remain separate hypotheses; no pair or
hypothesis is selected using truth, residual ranking or a plane assumption.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
from typing import Annotated, Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import Field, FiniteFloat, model_validator

from amidst.datasets.pilot import PilotInferenceContext
from amidst.domain.camera import Camera
from amidst.domain.common import DomainModel, Pixel2, Timestamp, Vec3
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.geometry.inverse_projection import InverseProjectionError, _validated_pose
from amidst.observation.aggregation import validate_stream_model

Identity = Annotated[str, Field(min_length=1)]
NonnegativeFinite = Annotated[FiniteFloat, Field(ge=0)]
PositiveFinite = Annotated[FiniteFloat, Field(gt=0)]
FloatArray = NDArray[np.float64]


class MultiViewEvidenceRef(DomainModel):
    source_id: Identity
    site_id: Identity
    spatial_context_id: Identity
    source_asset_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    observations_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    camera_id: Identity
    target_id: Identity
    frame_id: int = Field(ge=0)
    timestamp: Timestamp
    point_2d: Pixel2
    provenance: Literal["OBSERVED"] = "OBSERVED"


class MultiViewReprojection(DomainModel):
    camera_id: Identity
    axial_depth_scene_units: PositiveFinite
    projected_pixel: Pixel2
    observed_pixel: Pixel2
    residual_pixels: NonnegativeFinite


class MultiViewHypothesis(DomainModel):
    hypothesis_id: Identity
    model_kind: Literal["MULTIVIEW"] = "MULTIVIEW"
    method: Literal["CLOSEST_RAYS_MIDPOINT_ALL_LEGAL_PAIRS"] = (
        "CLOSEST_RAYS_MIDPOINT_ALL_LEGAL_PAIRS"
    )
    provenance: Literal["PROJECTED_DIAGNOSTIC"] = "PROJECTED_DIAGNOSTIC"
    world_position: Vec3
    camera_ids: tuple[Identity, Identity]
    evidence_refs: tuple[MultiViewEvidenceRef, MultiViewEvidenceRef]
    reprojections: tuple[MultiViewReprojection, MultiViewReprojection]
    ray_miss_distance_scene_units: NonnegativeFinite
    parallax_angle_degrees: Annotated[FiniteFloat, Field(ge=0, le=180)]
    acute_parallax_angle_degrees: Annotated[FiniteFloat, Field(ge=0, le=90)]
    line_system_condition_number: PositiveFinite
    calibration_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]

    @model_validator(mode="after")
    def pair_consistency(self) -> MultiViewHypothesis:
        if tuple(sorted(set(self.camera_ids))) != self.camera_ids:
            raise ValueError("hypothesis camera pair must be distinct and sorted")
        if tuple(ref.camera_id for ref in self.evidence_refs) != self.camera_ids:
            raise ValueError("hypothesis evidence must preserve camera-pair identity")
        if tuple(ref.camera_id for ref in self.reprojections) != self.camera_ids:
            raise ValueError("hypothesis residuals must preserve camera-pair identity")
        first, second = self.evidence_refs
        for field in (
            "source_id", "site_id", "spatial_context_id", "source_asset_sha256",
            "observations_sha256", "target_id", "frame_id", "timestamp",
        ):
            if getattr(first, field) != getattr(second, field):
                raise ValueError("multi-view evidence must have one exact time and source binding")
        return self


class MultiViewPairRejection(DomainModel):
    camera_ids: tuple[Identity, Identity]
    reason: Identity


class MultiViewResult(DomainModel):
    label: Literal["PILOT / SYNTHETIC SAMPLE"] = "PILOT / SYNTHETIC SAMPLE"
    model_kind: Literal["MULTIVIEW"] = "MULTIVIEW"
    method: Literal["EXACT_TIME_MULTI_VIEW_TRIANGULATION"] = "EXACT_TIME_MULTI_VIEW_TRIANGULATION"
    provenance: Literal["PROJECTED_DIAGNOSTIC"] = "PROJECTED_DIAGNOSTIC"
    source_id: Identity
    site_id: Identity
    spatial_context_id: Identity
    floor_id: Identity
    target_id: Identity | None
    frame_id: int | None = Field(default=None, ge=0)
    timestamp: Timestamp | None
    evidence_refs: tuple[MultiViewEvidenceRef, ...]
    status: Literal["ACCEPTED", "REJECTED", "NO_EVIDENCE"]
    rejection_reason: str | None
    hypotheses: tuple[MultiViewHypothesis, ...]
    pair_rejections: tuple[MultiViewPairRejection, ...]
    minimum_acute_angle_degrees: Annotated[FiniteFloat, Field(gt=0, le=90)]
    binding_authority: Literal["PILOT_DIAGNOSTIC_ONLY_NOT_APPROVED_SCHOOL_BINDING"] = (
        "PILOT_DIAGNOSTIC_ONLY_NOT_APPROVED_SCHOOL_BINDING"
    )
    coordinate_units: Literal["BLENDER_SCENE_UNITS"] = "BLENDER_SCENE_UNITS"
    ground_truth_used: Literal[False] = False
    pair_selected_by_ground_truth: Literal[False] = False
    hypotheses_selected_by_ground_truth: Literal[False] = False
    time_alignment: Literal["EXACT_TIMESTAMP_AND_FRAME_ID_NO_INTERPOLATION"] = (
        "EXACT_TIMESTAMP_AND_FRAME_ID_NO_INTERPOLATION"
    )

    @model_validator(mode="after")
    def status_consistency(self) -> MultiViewResult:
        if (self.status == "ACCEPTED") != bool(self.hypotheses):
            raise ValueError("only ACCEPTED results may contain hypotheses")
        for hypothesis in self.hypotheses:
            ref = hypothesis.evidence_refs[0]
            if (
                ref.source_id != self.source_id or ref.site_id != self.site_id
                or ref.spatial_context_id != self.spatial_context_id
                or ref.target_id != self.target_id or ref.frame_id != self.frame_id
                or ref.timestamp != self.timestamp
            ):
                raise ValueError("hypothesis must preserve result source/time/target binding")
        return self


# Diagnostic scripts are also loaded by importlib without a sys.modules entry.
# Resolve the strict schemas explicitly in that supported execution mode.
for _sidecar_model in (
    MultiViewEvidenceRef, MultiViewReprojection, MultiViewHypothesis,
    MultiViewPairRejection, MultiViewResult,
):
    _sidecar_model.model_rebuild(_types_namespace=globals())


def _digest(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def _evidence(context: PilotInferenceContext, frame: ObservationFrame) -> MultiViewEvidenceRef:
    if frame.point_2d is None:
        raise ValueError("a multi-view evidence reference requires observed pixels")
    return MultiViewEvidenceRef(
        source_id=context.source_id, site_id=context.site_id,
        spatial_context_id=context.spatial_context_id,
        source_asset_sha256=context.source_asset_sha256,
        observations_sha256=context.observations_sha256,
        camera_id=frame.camera_id, target_id=frame.target_id, frame_id=frame.frame_id,
        timestamp=frame.timestamp, point_2d=frame.point_2d,
    )


def _ray(camera: Camera, pixel: Pixel2) -> tuple[FloatArray, FloatArray]:
    if not (0 <= pixel[0] < camera.width and 0 <= pixel[1] < camera.height):
        raise ValueError("PIXEL_OUTSIDE_IMAGE")
    try:
        rotation, origin = _validated_pose(camera)
    except InverseProjectionError as error:
        raise ValueError(error.failure.value) from error
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        local = np.array(((pixel[0] - camera.cx) / camera.fx,
                          (camera.cy - pixel[1]) / camera.fy, -1.0), dtype=np.float64)
        direction = rotation @ local
        norm = float(np.linalg.norm(direction))
    if not np.isfinite(direction).all() or not math.isfinite(norm) or norm <= 0:
        raise ValueError("NUMERICAL_FAILURE")
    return origin, direction / norm


def _reprojection(
    camera: Camera, point: FloatArray, observed_pixel: Pixel2,
) -> MultiViewReprojection:
    matrix = np.asarray(camera.camera_to_world, dtype=np.float64)
    local = np.linalg.solve(matrix, np.append(point, 1.0))[:3]
    depth = float(-local[2])
    if depth <= 0:
        raise ValueError("INTERSECTION_BEHIND_CAMERA")
    if depth < camera.clip_start:
        raise ValueError("NEAR_CLIPPED")
    if depth > camera.clip_end:
        raise ValueError("FAR_CLIPPED")
    pixel = (float(camera.fx * local[0] / depth + camera.cx),
             float(camera.cy - camera.fy * local[1] / depth))
    if not (0 <= pixel[0] < camera.width and 0 <= pixel[1] < camera.height):
        raise ValueError("REPROJECTED_POINT_OUTSIDE_FOV")
    return MultiViewReprojection(
        camera_id=camera.camera_id, axial_depth_scene_units=depth,
        projected_pixel=pixel, observed_pixel=observed_pixel,
        residual_pixels=float(np.linalg.norm(np.subtract(pixel, observed_pixel))),
    )


def _pair_hypothesis(
    cameras: tuple[Camera, Camera],
    references: tuple[MultiViewEvidenceRef, MultiViewEvidenceRef],
    minimum_angle: float,
) -> MultiViewHypothesis:
    origins_and_rays = tuple(_ray(cam, ref.point_2d)
                             for cam, ref in zip(cameras, references, strict=True))
    (origin0, direction0), (origin1, direction1) = origins_and_rays
    cosine = float(np.clip(direction0 @ direction1, -1, 1))
    parallax = math.degrees(math.acos(cosine))
    acute = math.degrees(math.acos(abs(cosine)))
    if acute < minimum_angle:
        raise ValueError("INSUFFICIENT_PARALLAX")
    system = np.column_stack((direction0, -direction1))
    parameters, _, rank, singular = np.linalg.lstsq(system, origin1 - origin0, rcond=None)
    if rank < 2 or not np.isfinite(parameters).all():
        raise ValueError("NUMERICAL_FAILURE")
    if bool(np.any(parameters <= 0)):
        raise ValueError("INTERSECTION_BEHIND_CAMERA")
    closest0 = origin0 + parameters[0] * direction0
    closest1 = origin1 + parameters[1] * direction1
    point = (closest0 + closest1) / 2
    if not np.isfinite(point).all():
        raise ValueError("NUMERICAL_FAILURE")
    reprojections = tuple(_reprojection(cam, point, ref.point_2d)
                          for cam, ref in zip(cameras, references, strict=True))
    calibration = [camera.model_dump(mode="json") for camera in cameras]
    identity = {
        "model_kind": "MULTIVIEW", "calibration": calibration,
        "evidence": [ref.model_dump(mode="json") for ref in references],
        "minimum_acute_angle_degrees": minimum_angle,
    }
    return MultiViewHypothesis(
        hypothesis_id=f"multiview:{_digest(identity)}",
        world_position=(float(point[0]), float(point[1]), float(point[2])),
        camera_ids=(cameras[0].camera_id, cameras[1].camera_id), evidence_refs=references,
        reprojections=(reprojections[0], reprojections[1]),
        ray_miss_distance_scene_units=float(np.linalg.norm(closest0 - closest1)),
        parallax_angle_degrees=parallax, acute_parallax_angle_degrees=acute,
        line_system_condition_number=float(singular[0] / singular[-1]),
        calibration_sha256=_digest(calibration),
    )


def triangulate_exact_time(
    context: PilotInferenceContext, frames: tuple[ObservationFrame, ...],
    *, minimum_acute_angle_degrees: float = 1.0,
) -> dict[str, object]:
    """Preserve all legal exact-time camera-pair hypotheses without truth or plane use.

    Contract/provenance tampering raises ValueError before any pixel computation.
    Evidence insufficiency and geometric failure return explicit point-free results.
    A common timestamp plus frame identity is required; this function never invents
    synchronization or fills an absent camera observation.
    """
    context = validate_stream_model(context, PilotInferenceContext)
    if not isinstance(frames, tuple):
        raise ValueError("frames must be a tuple of strict ObservationFrame models")
    frames = tuple(validate_stream_model(frame, ObservationFrame) for frame in frames)
    if not math.isfinite(minimum_acute_angle_degrees) or not 0 < minimum_acute_angle_degrees <= 90:
        raise ValueError("minimum acute parallax must be finite and in (0, 90] degrees")
    frames = tuple(sorted(frames, key=lambda frame: frame.camera_id))
    cameras = {camera.camera_id: camera for camera in context.cameras}
    reason: str | None = None
    target = frames[0].target_id if frames else None
    frame_id = frames[0].frame_id if frames else None
    timestamp = frames[0].timestamp if frames else None
    if len({frame.camera_id for frame in frames}) != len(frames):
        reason = "DUPLICATE_CAMERA_EVIDENCE"
    elif any(frame.camera_id not in cameras for frame in frames):
        reason = "CAMERA_NOT_IN_SOURCE_BINDING"
    elif any(frame.data_kind != context.data_kind for frame in frames):
        reason = "SOURCE_DATA_KIND_MISMATCH"
    elif any(frame.target_id != target for frame in frames):
        reason = "TARGET_MISMATCH"
    elif any(frame.timestamp != timestamp or frame.frame_id != frame_id for frame in frames):
        reason = "EXACT_TIME_IDENTITY_MISMATCH"
    visible = tuple(frame for frame in frames if frame.status == VisibilityStatus.OBSERVED)
    references = tuple(_evidence(context, frame) for frame in visible)
    hypotheses: list[MultiViewHypothesis] = []
    rejections: list[MultiViewPairRejection] = []
    if reason is None and len(visible) < 2:
        reason = "INSUFFICIENT_EXACT_TIME_EVIDENCE"
    if reason is None:
        for pair in itertools.combinations(references, 2):
            camera_pair = (cameras[pair[0].camera_id], cameras[pair[1].camera_id])
            try:
                hypotheses.append(_pair_hypothesis(camera_pair, pair, minimum_acute_angle_degrees))
            except (ValueError, np.linalg.LinAlgError) as error:
                rejections.append(MultiViewPairRejection(
                    camera_ids=(pair[0].camera_id, pair[1].camera_id), reason=str(error),
                ))
        if not hypotheses:
            reason = "NO_LEGAL_CAMERA_PAIR"
    result = MultiViewResult(
        source_id=context.source_id, site_id=context.site_id,
        spatial_context_id=context.spatial_context_id, floor_id=context.zone.floor_id,
        target_id=target, frame_id=frame_id, timestamp=timestamp, evidence_refs=references,
        status=("ACCEPTED" if hypotheses else "REJECTED" if frames else "NO_EVIDENCE"),
        rejection_reason=reason, hypotheses=tuple(hypotheses), pair_rejections=tuple(rejections),
        minimum_acute_angle_degrees=minimum_acute_angle_degrees,
    )
    return result.model_dump(mode="json")
