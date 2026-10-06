"""Conditional uncertainty is additive, honest about assumptions, and GT-free."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionService
from amidst.observation.aggregation import AggregationInputError, validate_stream_model

_PATH = Path(__file__).parents[2] / "scripts" / "projection_uncertainty_model.py"
_SPEC = importlib.util.spec_from_file_location("projection_uncertainty_model_test", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
uncertainty = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = uncertainty
_SPEC.loader.exec_module(uncertainty)


def camera(**changes: Any) -> Camera:
    return Camera.model_validate(
        {
            "camera_id": "front",
            "camera_to_world": np.eye(4).tolist(),
            "fx": 640,
            "fy": 640,
            "cx": 640,
            "cy": 360,
            "width": 1280,
            "height": 720,
            "clip_start": 0.01,
            "clip_end": 1000,
            "floor_id": "1F",
        }
        | changes
    )


def plane(**changes: Any) -> Plane:
    return Plane.model_validate(
        {
            "plane_id": "landmark",
            "floor_id": "1F",
            "zone_id": "AREA_ROOM",
            "point": (0, 0, -100),
            "normal": (0, 0, 1),
        }
        | changes
    )


def frame(**changes: Any) -> ObservationFrame:
    return ObservationFrame.model_validate(
        {
            "frame_id": 3,
            "timestamp": 0.6,
            "target_id": "synthetic_pixel",
            "camera_id": "front",
            "status": VisibilityStatus.OBSERVED,
            "point_2d": (700, 400),
            "provenance": Provenance.OBSERVED,
        }
        | changes
    )


def propagate(**changes: Any) -> dict[str, Any]:
    return uncertainty.propagate_fixed_plane(
        camera(), plane(), frame(), pixel_sigma_px=0.002, **changes
    )


def test_sidecar_preserves_the_actual_service_point_quality_and_sources() -> None:
    inputs = (camera(), plane(), frame())
    before = [item.model_dump(mode="json") for item in inputs]
    result = uncertainty.propagate_fixed_plane(*inputs, pixel_sigma_px=0.002)
    service = InverseProjectionService(inputs[0], inputs[1]).project_frame(inputs[2])
    assert result["projected_point"] == service.model_dump(mode="json")
    assert before == [item.model_dump(mode="json") for item in inputs]
    assert result["measurement_status"] == "UNMEASURED_ASSUMPTION"
    assert result["covariance_status"] == "CONDITIONAL_EXACT_PLANE"
    assert result["formal_approval"] is False
    assert result["normal_height_uncertainty_modeled"] is False
    assert result["ground_truth_used"] is False
    assert result["downstream_policy_applied"] is False
    encoded = json.dumps(result, allow_nan=False)
    recovered = uncertainty.ProjectionUncertaintySidecar.model_validate_json(encoded)
    assert recovered.model_dump(mode="json") == result
    with pytest.raises(ValidationError):
        recovered.use_state = "REVIEW_REQUIRED"


def test_pixel_sigma_variance_scaling_and_conditioning_distance_are_explicit() -> None:
    values = []
    for sigma in (0.001, 0.002, 0.004):
        result = uncertainty.propagate_fixed_plane(camera(), plane(), frame(), pixel_sigma_px=sigma)
        covariance = np.asarray(result["covariance_bu2"])
        np.testing.assert_allclose(covariance, np.diag(((sigma * 100 / 640) ** 2,) * 2 + (0,)))
        assert result["covariance_rank"] == 2
        np.testing.assert_allclose(covariance @ np.asarray(plane().normal), 0)
        values.append(covariance)
    np.testing.assert_allclose(values[1], values[0] * 4)
    np.testing.assert_allclose(values[2], values[0] * 16)
    near = uncertainty.propagate_fixed_plane(camera(), plane(), frame(), pixel_sigma_px=0.002)
    far = uncertainty.propagate_fixed_plane(
        camera(), plane(point=(0, 0, -800)), frame(), pixel_sigma_px=0.002
    )
    np.testing.assert_allclose(far["covariance_bu2"], np.asarray(near["covariance_bu2"]) * 64)
    assert far["tangential_radius_95_bu"] == pytest.approx(
        near["tangential_radius_95_bu"] * 8
    )


def test_grazing_angle_amplification_changes_use_state_without_deleting_point() -> None:
    central = frame(point_2d=(640, 360))
    frontal = uncertainty.propagate_fixed_plane(camera(), plane(), central, pixel_sigma_px=0.01)
    grazing = uncertainty.propagate_fixed_plane(
        camera(),
        plane(normal=(math.sqrt(1 - 0.01**2), 0, 0.01)),
        central,
        pixel_sigma_px=0.01,
    )
    assert frontal["use_state"] == "USABLE_WITH_UNCERTAINTY"
    assert grazing["use_state"] == "REVIEW_REQUIRED"
    assert grazing["projected_point"] is not None
    assert grazing["tangential_radius_95_bu"] > frontal["tangential_radius_95_bu"] * 90
    assert grazing["covariance_rank"] == 2
    np.testing.assert_allclose(
        np.asarray(grazing["covariance_bu2"]) @ np.asarray(grazing["plane_unit_normal"]),
        0,
        atol=1e-14,
    )


def test_zero_variance_is_unavailable_and_never_claims_perfect_confidence() -> None:
    result = uncertainty.propagate_fixed_plane(camera(), plane(), frame(), pixel_sigma_px=0)
    assert result["use_state"] == "UNAVAILABLE_ZERO_VARIANCE"
    assert result["covariance_rank"] == 0
    assert result["principal_std_bu"] == [0, 0, 0]
    assert result["unmodeled_export_residuals"] is True
    assert result["sigma_is_measured_or_calibrated"] is False
    assert result["projected_point"] is not None


@pytest.mark.parametrize(
    ("parameter", "sigma", "unit", "expected"),
    [
        ("joint_focal", 0.001, "RELATIVE_FOCAL", (-9.375, 6.25, 0)),
        ("cx", 0.1, "PIXELS", (-0.15625, 0, 0)),
        ("cy", 0.1, "PIXELS", (0, 0.15625, 0)),
        ("local_pitch", 0.01, "DEGREES", (-0.5859375, 100.390625, 0)),
        ("world_z", 0.1, "BLENDER_SCENE_UNITS", (0.09375, -0.0625, 0)),
    ],
)
def test_calibration_units_and_independent_known_camera_derivatives(
    parameter: str, sigma: float, unit: str, expected: tuple[float, float, float]
) -> None:
    result = uncertainty.propagate_fixed_plane(
        camera(), plane(), frame(), pixel_sigma_px=0,
        calibration_parameter=parameter, calibration_sigma=sigma,
    )
    derivative = result["calibration_derivative"]
    assert derivative["parameter_unit"] == unit
    assert derivative["common_mode_across_camera_samples"] is True
    expected_array = np.asarray(expected)
    if parameter == "local_pitch":
        expected_array *= math.pi / 180
    np.testing.assert_allclose(
        derivative["derivative_bu_per_parameter_unit"], expected_array, rtol=1e-7, atol=1e-9
    )
    np.testing.assert_allclose(
        result["covariance_bu2"], np.outer(expected_array, expected_array) * sigma**2,
        rtol=1e-7, atol=1e-11,
    )
    assert result["covariance_rank"] == 1
    assert result["projected_point"] == propagate()["projected_point"]


def test_calibration_and_pixel_covariances_add_without_assuming_calibrated_measurements() -> None:
    pixel = propagate()
    calibration = uncertainty.propagate_fixed_plane(
        camera(), plane(), frame(), pixel_sigma_px=0,
        calibration_parameter="joint_focal", calibration_sigma=0.001,
    )
    combined = propagate(calibration_parameter="joint_focal", calibration_sigma=0.001)
    np.testing.assert_allclose(
        combined["covariance_bu2"],
        np.asarray(pixel["covariance_bu2"]) + np.asarray(calibration["covariance_bu2"]),
    )
    assert combined["cross_sample_calibration_correlation_ignored_by_downstream"] is True


def test_analytic_covariance_matches_independent_pixel_monte_carlo_without_gt() -> None:
    source_camera = camera()
    source_plane = plane(normal=(0.6, 0, 0.8))
    source_frame = frame()
    sigma = 0.005
    result = uncertainty.propagate_fixed_plane(
        source_camera, source_plane, source_frame, pixel_sigma_px=sigma
    )
    generator = np.random.default_rng(8931)
    service = InverseProjectionService(source_camera, source_plane)
    points = []
    for delta in generator.normal(0, sigma, size=(3000, 2)):
        noisy = ObservationFrame.model_validate(
            source_frame.model_dump(mode="json")
            | {"point_2d": (np.asarray(source_frame.point_2d) + delta).tolist()}
        )
        points.append(service.project_frame(noisy).world_position)
    empirical = np.cov(np.asarray(points).T)
    np.testing.assert_allclose(
        empirical, np.asarray(result["covariance_bu2"]), rtol=0.08, atol=2e-8
    )


def test_analytic_pixel_jacobian_matches_independent_central_service_projections() -> None:
    source_frame = frame()
    result = uncertainty.propagate_fixed_plane(
        camera(), plane(normal=(0.6, 0, 0.8)), source_frame, pixel_sigma_px=0.002
    )
    service = InverseProjectionService(camera(), plane(normal=(0.6, 0, 0.8)))
    columns = []
    for axis in range(2):
        points = []
        for delta in (-0.0001, 0.0001):
            pixel = list(source_frame.point_2d)
            pixel[axis] += delta
            changed = ObservationFrame.model_validate(
                source_frame.model_dump(mode="json") | {"point_2d": pixel}
            )
            points.append(np.asarray(service.project_frame(changed).world_position))
        columns.append((points[1] - points[0]) / 0.0002)
    np.testing.assert_allclose(
        result["analytic_pixel_jacobian_bu_per_px"], np.column_stack(columns), rtol=1e-8
    )


@pytest.mark.parametrize("sigma", [-1, float("nan"), float("inf"), True, "0.1", 1e300])
def test_invalid_sigmas_fail_closed(sigma: Any) -> None:
    with pytest.raises(ValueError):
        uncertainty.propagate_fixed_plane(camera(), plane(), frame(), pixel_sigma_px=sigma)
    with pytest.raises(ValueError):
        uncertainty.propagate_fixed_plane(
            camera(), plane(), frame(), pixel_sigma_px=0.002,
            calibration_parameter="cx", calibration_sigma=sigma,
        )


def test_missing_or_unknown_calibration_parameter_fails_closed() -> None:
    with pytest.raises(ValueError, match="explicit parameter"):
        propagate(calibration_sigma=0.1)
    with pytest.raises(ValueError, match="unsupported"):
        propagate(calibration_parameter="camera_selection_by_truth", calibration_sigma=0.1)
    with pytest.raises(TypeError):
        uncertainty.propagate_fixed_plane(camera(), plane(), frame())


def test_gap_and_contract_boundary_never_publish_a_covariance() -> None:
    gap = frame(
        status=VisibilityStatus.GAP, point_2d=None, provenance=None, gap_reason=GapReason.OCCLUDED
    )
    result = uncertainty.propagate_fixed_plane(camera(), plane(), gap, pixel_sigma_px=0.002)
    assert result["status"] == "SERVICE_REJECTED"
    assert result["failure"] == "FRAME_NOT_OBSERVED"
    assert result["projected_point"] is None
    assert result["covariance_bu2"] is None
    boundary = uncertainty.propagate_fixed_plane(
        camera(clip_end=100), plane(), frame(), pixel_sigma_px=0.002,
        calibration_parameter="world_z", calibration_sigma=0.1,
    )
    assert boundary["status"] == "CALIBRATION_DERIVATIVE_UNAVAILABLE"
    assert boundary["failure"] == "CENTRAL_DIFFERENCE_BOUNDARY:FAR_CLIPPED"
    assert boundary["use_state"] == "REVIEW_REQUIRED"
    assert boundary["projected_point"] is not None
    assert boundary["covariance_bu2"] is None


@pytest.mark.parametrize("input_kind", ["camera", "plane", "frame"])
def test_hidden_gt_model_copy_fields_are_rejected(input_kind: str) -> None:
    values = {"camera": camera(), "plane": plane(), "frame": frame()}
    values[input_kind] = values[input_kind].model_copy(update={"ground_truth_position": (1, 2, 3)})
    with pytest.raises(AggregationInputError):
        uncertainty.propagate_fixed_plane(
            values["camera"], values["plane"], values["frame"], pixel_sigma_px=0.002
        )


def test_strict_frozen_sidecar_rejects_gt_and_inconsistent_covariance() -> None:
    result = propagate()
    with pytest.raises(ValidationError):
        uncertainty.ProjectionUncertaintySidecar.model_validate(
            result | {"ground_truth": (1, 2, 3)}
        )
    for changes in (
        {"covariance_bu2": [[-1, 0, 0], [0, 1, 0], [0, 0, 0]]},
        {"covariance_bu2": [[1, 0.1, 0], [0, 1, 0], [0, 0, 0]]},
        {"covariance_bu2": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        {"covariance_rank": 1},
        {"tangential_radius_95_bu": 100},
        {"use_state": "REVIEW_REQUIRED"},
        {"eigenvalues_bu2": [float("nan"), 0, 0]},
        {"formal_approval": True},
        {"point_budget_bu_diagnostic_only": 100},
        {"chi_square_2d_95": 1},
        {"pixel_covariance_px2": [[0, 0], [0, 0]]},
    ):
        with pytest.raises(ValidationError):
            uncertainty.ProjectionUncertaintySidecar.model_validate(result | changes)
    frozen = uncertainty.ProjectionUncertaintySidecar.model_validate(result).model_copy(
        update={"ground_truth_position": (1, 2, 3)}
    )
    with pytest.raises(AggregationInputError):
        validate_stream_model(frozen, uncertainty.ProjectionUncertaintySidecar)


def test_repeat_is_identical_and_preloaded_helper_does_not_read_dataset_files(monkeypatch) -> None:
    uncertainty._policy()
    uncertainty._policy()._conditioning()
    import builtins

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("pure projection uncertainty cannot read dataset/evaluation files")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    first = propagate(calibration_parameter="joint_focal", calibration_sigma=0.001)
    second = propagate(calibration_parameter="joint_focal", calibration_sigma=0.001)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
