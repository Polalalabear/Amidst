"""Additive GT-free fixed-plane uncertainty sidecars for synthetic diagnostics.

The unchanged service point is accompanied by a first-order covariance conditional
on an exact configured plane. Pixel/calibration sigmas are explicit, unmeasured
assumptions. This is neither calibrated physical uncertainty nor a Graph policy.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import numpy as np
from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.camera import Camera
from amidst.domain.common import DomainModel, Vec3
from amidst.domain.evidence import ObservationFrame
from amidst.domain.geometry import Plane
from amidst.domain.observation import ProjectedPoint
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService
from amidst.observation.aggregation import validate_stream_model

LABEL = "PILOT / SYNTHETIC SAMPLE"
POINT_BUDGET_BU = 0.02
CHI_SQUARE_2D_95 = 5.991464547107979
NonnegativeFinite = Annotated[FiniteFloat, Field(ge=0)]
Row2 = tuple[FiniteFloat, FiniteFloat]
Matrix32 = tuple[Row2, Row2, Row2]
Matrix33 = tuple[Vec3, Vec3, Vec3]
CalibrationParameter = Literal["joint_focal", "cx", "cy", "local_pitch", "world_z"]
CalibrationUnit = Literal["RELATIVE_FOCAL", "PIXELS", "DEGREES", "BLENDER_SCENE_UNITS"]
UseState = Literal[
    "USABLE_WITH_UNCERTAINTY", "REVIEW_REQUIRED", "UNAVAILABLE_ZERO_VARIANCE", "SERVICE_REJECTED"
]
_STEPS: dict[CalibrationParameter, tuple[float, CalibrationUnit]] = {
    "joint_focal": (0.000001, "RELATIVE_FOCAL"),
    "cx": (0.001, "PIXELS"),
    "cy": (0.001, "PIXELS"),
    "local_pitch": (0.00001, "DEGREES"),
    "world_z": (0.0001, "BLENDER_SCENE_UNITS"),
}


class CalibrationDerivative(DomainModel):
    """One independent calibration parameter; shared across the camera's samples."""

    parameter: CalibrationParameter
    sigma_in_parameter_units: NonnegativeFinite
    parameter_unit: CalibrationUnit
    central_difference_step: Annotated[FiniteFloat, Field(gt=0)]
    derivative_bu_per_parameter_unit: Vec3
    common_mode_across_camera_samples: Literal[True] = True

    @model_validator(mode="after")
    def declared_units_and_step(self) -> Self:
        step, unit = _STEPS[self.parameter]
        if self.parameter_unit != unit or self.central_difference_step != step:
            raise ValueError("calibration derivative must use the declared diagnostic units/step")
        return self


class ProjectionUncertaintySidecar(DomainModel):
    """Frozen additive payload; cannot contain GT or modify a ProjectedPoint."""

    label: Literal["PILOT / SYNTHETIC SAMPLE"] = "PILOT / SYNTHETIC SAMPLE"
    version: Literal["FIXED_PLANE_UNCERTAINTY_SIDECAR_V1"] = "FIXED_PLANE_UNCERTAINTY_SIDECAR_V1"
    measurement_status: Literal["UNMEASURED_ASSUMPTION"] = "UNMEASURED_ASSUMPTION"
    covariance_status: Literal["CONDITIONAL_EXACT_PLANE"] = "CONDITIONAL_EXACT_PLANE"
    approximation: Literal["FIRST_ORDER_LINEARIZED"] = "FIRST_ORDER_LINEARIZED"
    physical_validity: Literal["PARTIAL / PROVISIONAL"] = "PARTIAL / PROVISIONAL"
    formal_approval: Literal[False] = False
    ground_truth_used: Literal[False] = False
    original_point_or_quality_modified: Literal[False] = False
    normal_height_uncertainty_modeled: Literal[False] = False
    unmodeled_export_residuals: Literal[True] = True
    sigma_is_measured_or_calibrated: Literal[False] = False
    cross_sample_calibration_correlation_ignored_by_downstream: Literal[True] = True
    downstream_policy_applied: Literal[False] = False
    camera_id: str = Field(min_length=1)
    plane_id: str = Field(min_length=1)
    frame_id: int = Field(ge=0)
    timestamp: Annotated[FiniteFloat, Field(ge=0)]
    status: Literal["ACCEPTED", "SERVICE_REJECTED", "CALIBRATION_DERIVATIVE_UNAVAILABLE"]
    failure: str | None
    projected_point: ProjectedPoint | None
    plane_unit_normal: Vec3
    pixel_sigma_px: NonnegativeFinite
    pixel_covariance_px2: tuple[Row2, Row2]
    analytic_pixel_jacobian_bu_per_px: Matrix32 | None
    calibration_derivative: CalibrationDerivative | None
    calibration_parameter_requested: CalibrationParameter | None
    calibration_sigma_requested: NonnegativeFinite
    covariance_bu2: Matrix33 | None
    covariance_rank: Annotated[int, Field(ge=0, le=2)] | None
    eigenvalues_bu2: Vec3 | None
    principal_std_bu: Vec3 | None
    tangential_radius_95_bu: NonnegativeFinite | None
    chi_square_2d_95: NonnegativeFinite = CHI_SQUARE_2D_95
    point_budget_bu_diagnostic_only: NonnegativeFinite = POINT_BUDGET_BU
    use_state: UseState
    max_gain_bu_per_px: NonnegativeFinite | None
    normalized_incidence: Annotated[FiniteFloat, Field(gt=0, le=1)] | None
    confidence_interpretation: Literal[
        "ASSUMED_GAUSSIAN_LINEARIZED_TANGENTIAL_BOUND_NOT_PHYSICAL_ACCURACY"
    ] = "ASSUMED_GAUSSIAN_LINEARIZED_TANGENTIAL_BOUND_NOT_PHYSICAL_ACCURACY"

    @model_validator(mode="after")
    def consistent_covariance(self) -> Self:
        if (
            self.chi_square_2d_95 != CHI_SQUARE_2D_95
            or self.point_budget_bu_diagnostic_only != POINT_BUDGET_BU
        ):
            raise ValueError("uncertainty diagnostic radius/budget are fixed predeclared constants")
        normal = np.asarray(self.plane_unit_normal, dtype=float)
        if not math.isclose(float(np.linalg.norm(normal)), 1, abs_tol=1e-6, rel_tol=0):
            raise ValueError("uncertainty requires a unit plane normal")
        pixel_cov = np.asarray(self.pixel_covariance_px2, dtype=float)
        expected_pixel_cov = np.eye(2) * self.pixel_sigma_px**2
        if not np.isfinite(expected_pixel_cov).all() or not np.array_equal(
            pixel_cov, expected_pixel_cov
        ):
            raise ValueError("pixel covariance must be the declared finite isotropic sigma squared")
        if self.calibration_parameter_requested is None and self.calibration_sigma_requested != 0:
            raise ValueError("calibration sigma requires an explicit calibration parameter")
        if self.projected_point is not None:
            point = validate_stream_model(self.projected_point, ProjectedPoint)
            if (
                point.camera_id != self.camera_id
                or point.plane_id != self.plane_id
                or point.timestamp != self.timestamp
            ):
                raise ValueError("sidecar identity must match the unchanged projected point")
        covariance_fields = (
            self.covariance_bu2,
            self.covariance_rank,
            self.eigenvalues_bu2,
            self.principal_std_bu,
            self.tangential_radius_95_bu,
        )
        if self.status != "ACCEPTED":
            if any(value is not None for value in covariance_fields):
                raise ValueError("failed propagation cannot publish a covariance")
            if self.failure is None:
                raise ValueError("failed propagation requires an explicit reason")
            if self.status == "SERVICE_REJECTED":
                if self.projected_point is not None or self.use_state != "SERVICE_REJECTED":
                    raise ValueError("service rejection cannot publish a reliable point")
            elif self.projected_point is None or self.use_state != "REVIEW_REQUIRED":
                raise ValueError("derivative failure preserves the point but requires review")
            return self
        if (
            self.failure is not None
            or self.projected_point is None
            or self.analytic_pixel_jacobian_bu_per_px is None
            or any(value is None for value in covariance_fields)
            or self.max_gain_bu_per_px is None
            or self.normalized_incidence is None
        ):
            raise ValueError("accepted uncertainty requires a point and complete diagnostics")
        assert self.eigenvalues_bu2 is not None
        assert self.principal_std_bu is not None
        assert self.tangential_radius_95_bu is not None
        assert self.covariance_rank is not None
        jacobian = np.asarray(self.analytic_pixel_jacobian_bu_per_px, dtype=float)
        expected = jacobian @ pixel_cov @ jacobian.T
        if self.calibration_parameter_requested is not None:
            if self.calibration_derivative is None:
                raise ValueError("requested calibration propagation requires its derivative")
            derivative_model = validate_stream_model(
                self.calibration_derivative, CalibrationDerivative
            )
            if (
                derivative_model.parameter != self.calibration_parameter_requested
                or derivative_model.sigma_in_parameter_units != self.calibration_sigma_requested
            ):
                raise ValueError("calibration derivative must match declared parameter/sigma")
            derivative = np.asarray(derivative_model.derivative_bu_per_parameter_unit, dtype=float)
            expected += np.outer(derivative, derivative) * self.calibration_sigma_requested**2
        elif self.calibration_derivative is not None:
            raise ValueError("unspecified calibration derivative cannot enter the covariance")
        covariance = np.asarray(self.covariance_bu2, dtype=float)
        scale = max(float(np.max(np.abs(expected))), np.finfo(float).tiny)
        tolerance = 1e-10 * scale
        if not np.isfinite(expected).all() or not np.allclose(
            covariance, expected, atol=tolerance, rtol=1e-10
        ):
            raise ValueError("covariance must equal propagated declared uncertainty")
        if not np.allclose(covariance, covariance.T, atol=tolerance, rtol=1e-10):
            raise ValueError("covariance must be symmetric")
        eigenvalues = np.linalg.eigvalsh(covariance)[::-1]
        if eigenvalues[-1] < -tolerance:
            raise ValueError("covariance must be positive semidefinite")
        eigenvalues = np.maximum(eigenvalues, 0)
        if float(np.linalg.norm(covariance @ normal)) > tolerance * 4:
            raise ValueError("exact-plane covariance cannot claim normal-height support")
        if self.covariance_rank != _rank(eigenvalues):
            raise ValueError("reported covariance rank is inconsistent")
        if not np.allclose(self.eigenvalues_bu2, eigenvalues, atol=tolerance, rtol=1e-10):
            raise ValueError("reported covariance eigenvalues are inconsistent")
        std = np.sqrt(eigenvalues)
        if not np.allclose(self.principal_std_bu, std, atol=math.sqrt(tolerance), rtol=1e-10):
            raise ValueError("reported principal standard deviations are inconsistent")
        radius = math.sqrt(CHI_SQUARE_2D_95 * float(eigenvalues[0]))
        if not math.isclose(self.tangential_radius_95_bu, radius, abs_tol=1e-14, rel_tol=1e-10):
            raise ValueError("reported tangential radius is inconsistent")
        expected_state = _use_state(radius, self.covariance_rank)
        if self.use_state != expected_state:
            raise ValueError("uncertainty use state must follow the fixed diagnostic budget")
        return self


@lru_cache(maxsize=1)
def _policy() -> Any:
    """Load the existing pure diagnostic helper, without dataset/evaluation modules."""
    path = Path(__file__).with_name("projection_mitigation_policy.py")
    spec = importlib.util.spec_from_file_location("uncertainty_mitigation_policy_reference", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("existing conditioning helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rank(eigenvalues: np.ndarray) -> int:
    largest = float(eigenvalues[0])
    if largest <= 0:
        return 0
    return int(np.count_nonzero(eigenvalues > largest * 1e-10))


def _use_state(radius: float, rank: int) -> UseState:
    if rank == 0:
        return "UNAVAILABLE_ZERO_VARIANCE"
    return "USABLE_WITH_UNCERTAINTY" if radius <= POINT_BUDGET_BU else "REVIEW_REQUIRED"


def _finite_sigma(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a numeric finite nonnegative sigma")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a numeric finite nonnegative sigma")
    if not math.isfinite(value * value):
        raise ValueError(f"{name} squared overflows finite covariance")
    return float(value)


def _camera_delta(camera: Camera, parameter: CalibrationParameter, delta: float) -> Camera:
    payload = camera.model_dump(mode="json")
    if parameter == "joint_focal":
        payload.update(fx=camera.fx * (1 + delta), fy=camera.fy * (1 + delta))
    elif parameter in ("cx", "cy"):
        payload[parameter] = getattr(camera, parameter) + delta
    else:
        original = np.asarray(camera.camera_to_world, dtype=float)
        matrix = original.copy()
        if parameter == "world_z":
            matrix[2, 3] += delta
        elif parameter == "local_pitch":
            angle = math.radians(delta)
            cosine, sine = math.cos(angle), math.sin(angle)
            pitch = np.asarray(((1, 0, 0), (0, cosine, -sine), (0, sine, cosine)))
            matrix[:3, :3] = original[:3, :3] @ pitch
        payload["camera_to_world"] = matrix.tolist()
    return Camera.model_validate(payload)


def propagate_fixed_plane(
    camera: Camera,
    plane: Plane,
    frame: ObservationFrame,
    *,
    pixel_sigma_px: float,
    calibration_parameter: CalibrationParameter | None = None,
    calibration_sigma: float = 0,
) -> dict[str, Any]:
    """Propagate declared assumptions; never change coordinates or reject evidence.

    A calibration parameter is an independent scalar nuisance variable shared by
    this camera's observations. Its cross-sample covariance is not consumed by
    existing downstream contracts. The 95% radius uses chi-square(2); it is a
    conservative tangent-plane radius for rank-one covariance, not a 3D bound.
    """
    camera = validate_stream_model(camera, Camera)
    plane = validate_stream_model(plane, Plane)
    frame = validate_stream_model(frame, ObservationFrame)
    pixel_sigma = _finite_sigma(pixel_sigma_px, "pixel_sigma_px")
    calibration_sigma = _finite_sigma(calibration_sigma, "calibration_sigma")
    if calibration_parameter is not None and calibration_parameter not in _STEPS:
        raise ValueError("unsupported diagnostic calibration parameter")
    if calibration_parameter is None and calibration_sigma != 0:
        raise ValueError("nonzero calibration sigma requires an explicit parameter")
    diagnostic = _policy().diagnose_sample(camera, plane, frame)
    payload: dict[str, Any] = {
        "camera_id": camera.camera_id,
        "plane_id": plane.plane_id,
        "frame_id": frame.frame_id,
        "timestamp": frame.timestamp,
        "status": "ACCEPTED",
        "failure": None,
        "projected_point": diagnostic["projected_point"],
        "plane_unit_normal": plane.normal,
        "pixel_sigma_px": pixel_sigma,
        "pixel_covariance_px2": (np.eye(2) * pixel_sigma**2).tolist(),
        "analytic_pixel_jacobian_bu_per_px": None,
        "calibration_derivative": None,
        "calibration_parameter_requested": calibration_parameter,
        "calibration_sigma_requested": calibration_sigma,
        "covariance_bu2": None,
        "covariance_rank": None,
        "eigenvalues_bu2": None,
        "principal_std_bu": None,
        "tangential_radius_95_bu": None,
        "use_state": "SERVICE_REJECTED",
        "max_gain_bu_per_px": None,
        "normalized_incidence": None,
    }
    if diagnostic["status"] != "ACCEPTED":
        payload.update(status="SERVICE_REJECTED", failure=diagnostic["failure"])
        return ProjectionUncertaintySidecar.model_validate(payload).model_dump(mode="json")
    jacobian = np.asarray(diagnostic["jacobian"]["analytic_bu_per_px"], dtype=float)
    payload.update(
        analytic_pixel_jacobian_bu_per_px=jacobian.tolist(),
        max_gain_bu_per_px=diagnostic["jacobian"]["max_gain_bu_per_px"],
        normalized_incidence=diagnostic["geometry"]["normalized_incidence"],
    )
    covariance = jacobian @ (np.eye(2) * pixel_sigma**2) @ jacobian.T
    if calibration_parameter is not None:
        step, unit = _STEPS[calibration_parameter]
        try:
            plus = InverseProjectionService(
                _camera_delta(camera, calibration_parameter, step), plane
            ).project_frame(frame)
            minus = InverseProjectionService(
                _camera_delta(camera, calibration_parameter, -step), plane
            ).project_frame(frame)
        except InverseProjectionError as error:
            payload.update(
                status="CALIBRATION_DERIVATIVE_UNAVAILABLE",
                failure=f"CENTRAL_DIFFERENCE_BOUNDARY:{error.failure.value}",
                use_state="REVIEW_REQUIRED",
            )
            return ProjectionUncertaintySidecar.model_validate(payload).model_dump(mode="json")
        derivative = (
            np.asarray(plus.world_position) - np.asarray(minus.world_position)
        ) / (2 * step)
        payload["calibration_derivative"] = CalibrationDerivative(
            parameter=calibration_parameter,
            sigma_in_parameter_units=calibration_sigma,
            parameter_unit=unit,
            central_difference_step=step,
            derivative_bu_per_parameter_unit=tuple(derivative),
        ).model_dump(mode="json")
        covariance += np.outer(derivative, derivative) * calibration_sigma**2
    if not np.isfinite(covariance).all():
        raise ValueError("propagated covariance is not finite")
    covariance = (covariance + covariance.T) / 2
    eigenvalues = np.maximum(np.linalg.eigvalsh(covariance)[::-1], 0)
    rank = _rank(eigenvalues)
    radius = math.sqrt(CHI_SQUARE_2D_95 * float(eigenvalues[0]))
    payload.update(
        covariance_bu2=covariance.tolist(),
        covariance_rank=rank,
        eigenvalues_bu2=eigenvalues.tolist(),
        principal_std_bu=np.sqrt(eigenvalues).tolist(),
        tangential_radius_95_bu=radius,
        use_state=_use_state(radius, rank),
    )
    return ProjectionUncertaintySidecar.model_validate(payload).model_dump(mode="json")
