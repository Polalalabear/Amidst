"""GT-free, predeclared conditioning policy for PILOT diagnostic comparisons.

These policies do not estimate probability or certify physical accuracy. The
pixel radius and point budget are synthetic diagnostic assumptions, independent
of any evaluation reference. Accepted points preserve the unchanged inverse
projection result; confidence/rejection never adjusts a coordinate or ranking.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import numpy as np
from pydantic import Field, FiniteFloat, model_validator

from amidst.datasets.pilot import Digest, Identity, PilotInferenceContext
from amidst.domain.camera import Camera
from amidst.domain.common import DomainModel, Pixel2, PositiveFinite, Vec3
from amidst.domain.evidence import ObservationFrame
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService
from amidst.observation.aggregation import validate_stream_model

LABEL = "PILOT / SYNTHETIC SAMPLE"
RejectionMode = Literal["NONE", "STANDARD", "EXTREME_ONLY"]
Incidence = Annotated[FiniteFloat, Field(gt=0, le=1)]
NonnegativeFinite = Annotated[FiniteFloat, Field(ge=0)]


class ConditioningPolicy(DomainModel):
    """Immutable engineering diagnostics; not a learned or calibrated policy."""

    pixel_uncertainty_radius_px: NonnegativeFinite = 0.002
    point_budget_bu: PositiveFinite = 0.02
    review_gain_bu_per_px: PositiveFinite = 5.0
    review_incidence: Incidence = 0.2
    reject_gain_bu_per_px: PositiveFinite = 10.0
    reject_incidence: Incidence = 0.1
    extreme_reject_gain_bu_per_px: PositiveFinite = 20.0
    extreme_reject_incidence: Incidence = 0.05

    @model_validator(mode="after")
    def ordered_thresholds(self) -> Self:
        if not (
            self.review_gain_bu_per_px
            <= self.reject_gain_bu_per_px
            <= self.extreme_reject_gain_bu_per_px
            and self.review_incidence >= self.reject_incidence >= self.extreme_reject_incidence
        ):
            raise ValueError("gain/incidence thresholds must preserve review-to-extreme ordering")
        return self


class LocalPlaneReceipt(DomainModel):
    """Independent local metadata binding, with explicitly provisional authority."""

    site_id: Identity
    source_asset_sha256: Digest
    floor_id: Identity
    zone_id: Identity
    mesh_object_id: Identity
    independent_mesh_probe_xy: Pixel2
    physical_floor_z: FiniteFloat
    physical_floor_normal: Vec3
    foot_clearance_units: NonnegativeFinite
    landmark_offset_units: NonnegativeFinite
    purpose: Literal["PILOT_DIAGNOSTIC_ONLY"] = "PILOT_DIAGNOSTIC_ONLY"

    @model_validator(mode="after")
    def horizontal_floor(self) -> Self:
        nx, ny, nz = self.physical_floor_normal
        if abs(nx) > 1e-9 or abs(ny) > 1e-9 or not math.isclose(abs(nz), 1, abs_tol=1e-9):
            raise ValueError("local binding requires independently declared horizontal floor")
        return self


@lru_cache(maxsize=1)
def _conditioning() -> Any:
    """Reuse the previous experiment's ray formula without importing evaluation."""
    path = Path(__file__).with_name("projection_conditioning.py")
    spec = importlib.util.spec_from_file_location("mitigation_conditioning_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("existing conditioning helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _policy(policy: ConditioningPolicy | None) -> ConditioningPolicy:
    return validate_stream_model(policy or ConditioningPolicy(), ConditioningPolicy)


def classify(
    diagnostics: Mapping[str, Any],
    policy: ConditioningPolicy | None = None,
    *,
    rejection_mode: RejectionMode = "NONE",
) -> dict[str, Any]:
    """Classify geometry only; equality at thresholds remains accepted/unflagged.

    Review is gain > 5 BU/px OR incidence < .2. STANDARD rejection is gain >
    10 BU/px OR incidence < .1; EXTREME_ONLY uses 20/.05. The heuristic is
    explicitly nonprobabilistic. NONE always preserves a valid service result.
    """
    current = _policy(policy)
    if rejection_mode not in ("NONE", "STANDARD", "EXTREME_ONLY"):
        raise ValueError("unknown conditioning rejection mode")
    if diagnostics.get("status") != "ACCEPTED":
        return {
            "accepted": False,
            "low_confidence": False,
            "requires_review": False,
            "confidence_score": None,
            "confidence_interpretation": "NONPROBABILISTIC_ENGINEERING_HEURISTIC",
            "label": "SERVICE_REJECTED",
            "rejection_mode": rejection_mode,
            "reasons": [f"SERVICE:{diagnostics.get('failure', 'UNAVAILABLE')}"],
        }
    gain = diagnostics["jacobian"]["max_gain_bu_per_px"]
    incidence = diagnostics["geometry"]["normalized_incidence"]
    if (
        isinstance(gain, bool)
        or isinstance(incidence, bool)
        or not isinstance(gain, (float, int))
        or not isinstance(incidence, (float, int))
        or not math.isfinite(gain)
        or not math.isfinite(incidence)
        or gain < 0
        or not 0 <= incidence <= 1
    ):
        raise ValueError("conditioning gain/incidence must be finite valid numeric diagnostics")
    uncertainty = gain * current.pixel_uncertainty_radius_px
    if not math.isfinite(uncertainty):
        raise ValueError("policy linearized uncertainty overflows finite diagnostics")
    ratio = uncertainty / current.point_budget_bu
    score = min(1.0, incidence / current.review_incidence) / (1 + ratio * ratio)
    reasons = []
    if gain > current.review_gain_bu_per_px:
        reasons.append("GAIN_EXCEEDS_REVIEW_THRESHOLD")
    if incidence < current.review_incidence:
        reasons.append("INCIDENCE_BELOW_REVIEW_THRESHOLD")
    low_confidence = bool(reasons)
    reject = False
    if rejection_mode != "NONE":
        extreme = rejection_mode == "EXTREME_ONLY"
        gain_limit = (
            current.extreme_reject_gain_bu_per_px if extreme else current.reject_gain_bu_per_px
        )
        incidence_limit = current.extreme_reject_incidence if extreme else current.reject_incidence
        if gain > gain_limit:
            reject = True
            reasons.append("GAIN_EXCEEDS_REJECTION_THRESHOLD")
        if incidence < incidence_limit:
            reject = True
            reasons.append("INCIDENCE_BELOW_REJECTION_THRESHOLD")
    return {
        "accepted": not reject,
        "low_confidence": low_confidence,
        "requires_review": low_confidence,
        "confidence_score": score,
        "confidence_interpretation": "NONPROBABILISTIC_ENGINEERING_HEURISTIC",
        "label": "REJECTED" if reject else ("LOW_CONFIDENCE" if low_confidence else "CONDITIONED"),
        "rejection_mode": rejection_mode,
        "reasons": reasons,
        "pixel_uncertainty_radius_px_assumed_not_measured": current.pixel_uncertainty_radius_px,
        "linearized_point_uncertainty_bu": uncertainty,
        "point_budget_bu_diagnostic_only": current.point_budget_bu,
    }


def diagnose_sample(
    camera: Camera,
    plane: Plane,
    frame: ObservationFrame,
    *,
    policy: ConditioningPolicy | None = None,
) -> dict[str, Any]:
    """One strict observed pixel, one unchanged projection, one analytic Jacobian.

    No files, GT positions, metric values, finite-difference perturbations or
    alternate surfaces enter this computation. DISTANCE is Euclidean; depth is
    the axial ray parameter. Signed denominator retains the supplied normal sign.
    """
    camera = validate_stream_model(camera, Camera)
    plane = validate_stream_model(plane, Plane)
    frame = validate_stream_model(frame, ObservationFrame)
    current = _policy(policy)
    report: dict[str, Any] = {
        "label": LABEL,
        "physical_validity": "PARTIAL / PROVISIONAL",
        "coordinate_units": "BLENDER_SCENE_UNITS",
        "scale_authority": "UNVERIFIED",
        "ground_truth_used": False,
        "source_camera_or_plane_modified": False,
        "camera_id": camera.camera_id,
        "plane_id": plane.plane_id,
        "floor_id": plane.floor_id,
        "zone_id": plane.zone_id,
        "frame_id": frame.frame_id,
        "timestamp": frame.timestamp,
        "pixel": frame.point_2d,
        "policy": current.model_dump(mode="json"),
    }
    try:
        projected = InverseProjectionService(camera, plane).project_frame(frame)
    except InverseProjectionError as error:
        report.update(
            status="REJECTED",
            failure=error.failure.value,
            projected_point=None,
            geometry=None,
            jacobian=None,
            service_quality=None,
        )
        report["confidence"] = classify(report, current)
        return report
    origin, rotation, ray, normal, denominator, depth, _ = _conditioning()._ray_arrays(
        camera, plane, frame
    )
    ray_length = float(np.linalg.norm(ray))
    unit_ray = ray / ray_length
    unit_normal = normal / np.linalg.norm(normal)
    incidence = min(1.0, abs(float(unit_normal @ unit_ray)))
    normal_angle = math.degrees(math.acos(incidence))
    optical = -rotation[:, 2] / np.linalg.norm(rotation[:, 2])
    off_axis = math.degrees(math.acos(float(np.clip(optical @ unit_ray, -1, 1))))
    derivative = rotation @ np.asarray(((1 / camera.fx, 0), (0, -1 / camera.fy), (0, 0)))
    jacobian = depth * (derivative - np.outer(ray, normal @ derivative) / denominator)
    singular = np.linalg.svd(jacobian, compute_uv=False)
    report.update(
        status="ACCEPTED",
        failure=None,
        projected_point=projected.model_dump(mode="json"),
        geometry={
            "camera_point_distance_bu": float(np.linalg.norm(projected.world_position - origin)),
            "intersection_distance_bu": float(depth * ray_length),
            "axial_projected_depth_bu": float(depth),
            "grazing_angle_degrees": 90 - normal_angle,
            "acute_ray_normal_angle_degrees": normal_angle,
            "off_axis_ray_angle_degrees": off_axis,
            "signed_unnormalized_denominator": float(denominator),
            "normalized_incidence": incidence,
            "conditioning_indicator": 1 / incidence,
        },
        jacobian={
            "analytic_bu_per_px": jacobian.tolist(),
            "max_gain_bu_per_px": float(singular[0]),
            "min_gain_bu_per_px": float(singular[-1]),
        },
        service_quality=projected.projection_quality,
    )
    report["confidence"] = classify(report, current)
    return report


def bind_local_landmark_plane(
    context: PilotInferenceContext | Mapping[str, Any],
    receipt: LocalPlaneReceipt,
) -> Plane:
    """Reanchor the same landmark plane to an independent local floor probe.

    The independent floor receipt does not make its mesh an approved surface.
    Offset remains explicit: a floor is not the observed body's landmark plane.
    Same normal sign, same height and same identity preserve all original points.
    """
    if isinstance(context, PilotInferenceContext):
        context = validate_stream_model(context, PilotInferenceContext)
    else:
        context = PilotInferenceContext.model_validate(context)
    receipt = validate_stream_model(receipt, LocalPlaneReceipt)
    if (
        receipt.source_asset_sha256 != context.source_asset_sha256
        or receipt.site_id != context.site_id
        or receipt.floor_id != context.zone.floor_id
        or receipt.zone_id != context.zone.zone_id
    ):
        raise ValueError("local plane receipt source/site/floor/zone differs from context")
    nx, ny, nz = context.plane.normal
    if abs(nx) > 1e-9 or abs(ny) > 1e-9 or not math.isclose(abs(nz), 1, abs_tol=1e-9):
        raise ValueError("local binding requires a horizontal context landmark plane")
    x, y = receipt.independent_mesh_probe_xy
    if not all(
        context.zone.bounds_min[axis] <= value <= context.zone.bounds_max[axis]
        for axis, value in enumerate((x, y))
    ):
        raise ValueError("independent floor probe lies outside configured local zone")
    landmark_z = (
        receipt.physical_floor_z + receipt.foot_clearance_units + receipt.landmark_offset_units
    )
    if not math.isclose(landmark_z, context.plane.point[2], rel_tol=0, abs_tol=1e-9):
        raise ValueError("independent floor plus explicit body offset differs from landmark plane")
    return Plane.model_validate(
        context.plane.model_dump(mode="python") | {"point": (x, y, landmark_z)}
    )
