"""GT-free conditioning diagnostics against unchanged production projection."""

from __future__ import annotations

import builtins
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from amidst.domain.camera import Camera
from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionService

_SCRIPT = Path(__file__).parents[2] / "scripts" / "projection_conditioning.py"
_SPEC = importlib.util.spec_from_file_location("projection_conditioning_diagnostics", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
conditioning = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(conditioning)


def _camera(**changes: Any) -> Camera:
    return Camera.model_validate(
        {
            "camera_id": "diagnostic_camera",
            "width": 1280,
            "height": 720,
            "fx": 640,
            "fy": 610,
            "cx": 640,
            "cy": 360,
            "clip_start": 0.01,
            "clip_end": 1000,
            "camera_to_world": np.eye(4).tolist(),
            "floor_id": "DIAGNOSTIC",
        }
        | changes
    )


def _plane(**changes: Any) -> Plane:
    return Plane.model_validate(
        {
            "plane_id": "diagnostic_plane",
            "point": (0, 0, -300),
            "normal": (0, 0, 1),
            "floor_id": "DIAGNOSTIC",
        }
        | changes
    )


def _frame(**changes: Any) -> ObservationFrame:
    return ObservationFrame.model_validate(
        {
            "frame_id": 1,
            "timestamp": 0.2,
            "target_id": "observed_pixel_only",
            "camera_id": "diagnostic_camera",
            "status": VisibilityStatus.OBSERVED,
            "point_2d": (700.125, 381.25),
            "provenance": Provenance.OBSERVED,
        }
        | changes
    )


def test_analytic_jacobian_matches_actual_service_central_difference() -> None:
    rotation = conditioning._rotation(2, 17) @ conditioning._rotation(1, 11)
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = (1234.56789, 987.654321, 500.12345)
    camera = _camera(camera_to_world=matrix.tolist(), fx=701.125, fy=602.75)
    plane = _plane(point=(0, 0, 75.128847))
    frame = _frame()
    result = conditioning.diagnose_projection(camera, plane, frame)
    actual = InverseProjectionService(camera, plane).project_frame(frame)
    assert result["status"] == "ACCEPTED"
    assert result["baseline_projected_point"]["world_position"] == list(actual.world_position)
    assert result["baseline_projected_point"]["provenance"] == "PROJECTED"
    jacobian = result["jacobian"]
    assert jacobian["central_difference"]["status"] == "COMPUTED"
    np.testing.assert_allclose(
        jacobian["analytic_scene_units_per_pixel"],
        jacobian["central_difference"]["jacobian_scene_units_per_pixel"],
        rtol=2e-7,
        atol=2e-8,
    )
    singular = np.linalg.svd(jacobian["analytic_scene_units_per_pixel"], compute_uv=False)
    assert jacobian["max_scene_units_per_pixel"] == singular[0]
    assert jacobian["min_scene_units_per_pixel"] == singular[1]
    assert jacobian["central_difference_relative_frobenius_error"] < 2e-7


def test_high_precision_and_forward_roundtrip_use_projected_baseline_only() -> None:
    matrix = np.eye(4)
    matrix[:3, 3] = (1234.56789123, 987.65432109, 500.123456789)
    camera = _camera(camera_to_world=matrix.tolist())
    result = conditioning.diagnose_projection(camera, _plane(point=(0, 0, 75.128847)), _frame())
    assert result["high_precision"]["precision_decimal_digits"] == 60
    assert (
        result["high_precision"]["input_conversion"] == "EXACT_BINARY64_VALUES_DECIMAL_FROM_FLOAT"
    )
    assert len(result["high_precision"]["point_decimal_strings"]) == 3
    assert result["high_precision"]["difference_from_service_scene_units"] < 5e-12
    assert result["float32_diagnostic"]["status"] == "COMPUTED"
    assert result["float32_diagnostic"]["difference_from_service_scene_units"] > 1e-6
    assert result["roundtrip"]["input_point_provenance"] == "PROJECTED"
    assert result["roundtrip"]["status"] == "COMPUTED"
    assert result["roundtrip"]["pixel_error"] < 1e-9
    assert result["roundtrip"]["forward_then_inverse_position_error_scene_units"] < 1e-9
    assert result["ground_truth_used"] is False
    json.dumps(result, allow_nan=False)


def test_geometry_distinguishes_axial_and_euclidean_distance_and_angles() -> None:
    frame = _frame(point_2d=(960, 360))
    result = conditioning.diagnose_projection(_camera(), _plane(), frame)
    geometry = result["geometry"]
    assert geometry["intersection_axial_depth_scene_units"] == pytest.approx(300)
    assert geometry["forward_axial_depth_scene_units"] == pytest.approx(300)
    distance = 300 * math.sqrt(1.25)
    assert geometry["intersection_euclidean_distance_scene_units"] == pytest.approx(distance)
    assert geometry["camera_point_euclidean_distance_scene_units"] == pytest.approx(distance)
    assert geometry["optical_off_axis_ray_angle_degrees"] == pytest.approx(
        math.degrees(math.atan(0.5))
    )
    assert geometry["normalized_incidence"] == pytest.approx(1 / math.sqrt(1.25))
    assert geometry["acute_ray_normal_angle_degrees"] + geometry[
        "grazing_angle_degrees"
    ] == pytest.approx(90)


@pytest.mark.parametrize(
    ("plane", "pixel", "failure"),
    [
        (_plane(normal=(1, 0, 0)), (640, 360), "RAY_PARALLEL_TO_PLANE"),
        (_plane(point=(0, 0, 1)), (640, 360), "INTERSECTION_BEHIND_CAMERA"),
        (_plane(point=(0, 0, -0.005)), (640, 360), "NEAR_CLIPPED"),
        (_plane(point=(0, 0, -1001)), (640, 360), "FAR_CLIPPED"),
        (_plane(), (1280, 360), "PIXEL_OUTSIDE_IMAGE"),
    ],
)
def test_diagnostics_preserve_actual_service_failure_contract(
    plane: Plane, pixel: tuple[float, float], failure: str
) -> None:
    result = conditioning.diagnose_projection(_camera(), plane, _frame(point_2d=pixel))
    assert result["status"] == "REJECTED"
    assert result["failure"] == failure
    assert result["baseline_projected_point"] is None
    assert result["jacobian"] is None
    assert result["high_precision"] is None
    assert result["roundtrip"] is None


def test_gap_never_gets_synthetic_pixel_or_projected_position() -> None:
    gap = _frame(
        status=VisibilityStatus.GAP,
        point_2d=None,
        provenance=None,
        gap_reason=GapReason.OCCLUDED,
    )
    result = conditioning.diagnose_perturbations(_camera(), _plane(), gap)
    assert result["baseline"]["failure"] == "FRAME_NOT_OBSERVED"
    assert result["calibration_variants"] == []
    assert result["plane_variants"] == []


def test_central_difference_boundary_is_na_not_fabricated_derivative() -> None:
    result = conditioning.diagnose_projection(_camera(), _plane(), _frame(point_2d=(0, 360)))
    assert result["status"] == "ACCEPTED"
    jacobian = result["jacobian"]
    assert jacobian["central_difference"]["status"] == "UNAVAILABLE_AT_SERVICE_CONTRACT_BOUNDARY"
    assert jacobian["central_difference"]["failures"] == [
        {"axis": 0, "sign": -1, "failure": "PIXEL_OUTSIDE_IMAGE"}
    ]
    assert jacobian["central_difference_relative_frobenius_error"] is None
    assert jacobian["analytic_scene_units_per_pixel"] is not None


def test_camera_variants_are_immutable_and_preserve_original_float32_pose() -> None:
    matrix = np.eye(4)
    matrix[0, 0] += 2e-7
    matrix[:3, 3] = (100, 200, 300)
    camera = _camera(camera_to_world=matrix.tolist())
    original = camera.model_dump_json()
    variants = conditioning.camera_perturbations(camera)
    assert len(variants) == 18
    assert len({metadata["variant_id"] for metadata, _ in variants}) == 18
    for metadata, variant in variants:
        assert metadata["source_camera_or_plane_modified"] is False
        assert variant is not camera
        InverseProjectionService(variant, _plane())
        pose = np.asarray(variant.camera_to_world)
        if metadata["parameter"].startswith("world_"):
            np.testing.assert_array_equal(pose[:3, :3], matrix[:3, :3])
            axis = ("world_x", "world_y", "world_z").index(metadata["parameter"])
            expected = matrix.copy()
            expected[axis, 3] += metadata["delta"]
            np.testing.assert_array_equal(pose, expected)
        elif metadata["parameter"].startswith("local_"):
            np.testing.assert_array_equal(pose[:3, 3], matrix[:3, 3])
            axis = 0 if metadata["parameter"] == "local_pitch" else 1
            np.testing.assert_array_equal(
                pose[:3, :3], matrix[:3, :3] @ conditioning._rotation(axis, metadata["delta"])
            )
        else:
            np.testing.assert_array_equal(pose, matrix)
    assert camera.model_dump_json() == original
    # No orthogonalization/repair of the accepted original float32-like R.
    assert variants[0][1].camera_to_world[0][0] == matrix[0, 0]


def test_plane_pivots_separate_parameter_bias_from_anchor_conditioning() -> None:
    plane = _plane()
    original = plane.model_dump_json()
    result = conditioning.diagnose_perturbations(_camera(), plane, _frame())
    assert len(result["calibration_variants"]) == 18
    rows = result["plane_variants"]
    assert len(rows) == 12
    assert len({row["perturbation"]["variant_id"] for row in rows}) == 12
    anchor_rows = [
        row
        for row in rows
        if row["perturbation"]["pivot_policy"] == "BASELINE_PROJECTED_ANCHOR_CONDITIONING_ONLY"
    ]
    assert len(anchor_rows) == 4
    for row in anchor_rows:
        assert row["displacement_from_baseline_scene_units"] < 1e-10
        assert (
            row["perturbation"]["pivot_scene_units"]
            == result["baseline"]["baseline_projected_point"]["world_position"]
        )
    source_tilts = [
        row
        for row in rows
        if row["perturbation"]["parameter"].endswith("tilt")
        and row["perturbation"]["pivot_policy"] == "METADATA_PLANE_POINT"
    ]
    assert max(row["displacement_from_baseline_scene_units"] for row in source_tilts) > 0.001
    assert plane.model_dump_json() == original
    assert len(conditioning.plane_perturbations(plane)) == 8
    json.dumps(result, allow_nan=False)


def test_fixed_grid_separates_conditioning_growth_and_hard_contract_failure() -> None:
    rows = conditioning.synthetic_conditioning_grid()
    assert len(rows) == 27
    assert all(row["control_kind"] == "SYNTHETIC_FACTORIAL_ONLY_NOT_SCHOOL" for row in rows)
    assert all(row["control_clip_end_scene_units"] == 1000 for row in rows)
    for row in rows:
        grazing = row["control_grazing_angle_degrees"]
        distance = row["control_distance_scene_units"]
        assert len(row["directional_pixel_perturbations"]) == 12
        if grazing == 0:
            assert row["status"] == "REJECTED"
            assert row["failure"] == "RAY_PARALLEL_TO_PLANE"
            assert all(
                noise["world_displacement_from_center_scene_units"] is None
                for noise in row["directional_pixel_perturbations"]
            )
            continue
        assert row["status"] == "ACCEPTED"
        assert row["geometry"]["normalized_incidence"] == pytest.approx(
            math.sin(math.radians(grazing))
        )
        assert row["geometry"]["camera_point_euclidean_distance_scene_units"] == pytest.approx(
            distance
        )
        assert row["jacobian"]["min_scene_units_per_pixel"] == pytest.approx(distance / 640)
        assert row["jacobian"]["max_scene_units_per_pixel"] == pytest.approx(
            distance / (640 * math.sin(math.radians(grazing)))
        )
        assert row["high_precision"]["difference_from_service_scene_units"] < 1e-10
    ordinary = [row for row in rows if row["control_grazing_angle_degrees"] >= 1]
    assert all(
        row["jacobian"]["central_difference_relative_frobenius_error"] < 2e-7 for row in ordinary
    )
    failures = {
        noise["failure"]
        for row in rows
        for noise in row["directional_pixel_perturbations"]
        if noise["status"] == "REJECTED"
    }
    assert {"FAR_CLIPPED", "INTERSECTION_BEHIND_CAMERA", "RAY_PARALLEL_TO_PLANE"} <= failures
    for distance in (100, 300, 800):
        values = [
            row["jacobian"]["max_scene_units_per_pixel"]
            for row in rows
            if row["control_distance_scene_units"] == distance and row["status"] == "ACCEPTED"
        ]
        assert values == sorted(values)
    json.dumps(rows, allow_nan=False)


def test_diagnostics_do_not_open_gt_or_any_dataset_file(monkeypatch: pytest.MonkeyPatch) -> None:
    camera, plane, frame = _camera(), _plane(), _frame()

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Numeric diagnostics must not read any files, including GT")

    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(Path, "open", forbidden)
        guard.setattr(Path, "read_text", forbidden)
        guard.setattr(Path, "read_bytes", forbidden)
        direct = conditioning.diagnose_projection(camera, plane, frame)
        variants = conditioning.diagnose_perturbations(camera, plane, frame)
        grid = conditioning.synthetic_conditioning_grid(distances=(100,), grazing_degrees=(1, 0))
    assert direct["ground_truth_used"] is False
    assert variants["ground_truth_used"] is False
    assert len(grid) == 2


@pytest.mark.parametrize("contract", ("camera", "plane", "frame"))
def test_hidden_gt_fields_fail_closed(contract: str) -> None:
    inputs = {"camera": _camera(), "plane": _plane(), "frame": _frame()}
    inputs[contract] = inputs[contract].model_copy(update={"ground_truth_3d": (1, 2, 3)})
    with pytest.raises(ValueError, match="without hidden fields"):
        conditioning.diagnose_projection(**inputs)


@pytest.mark.parametrize("step", (0, -1, math.nan, math.inf, True))
def test_invalid_central_step_is_rejected(step: float) -> None:
    with pytest.raises(ValueError, match="finite positive"):
        conditioning.diagnose_projection(_camera(), _plane(), _frame(), pixel_step=step)


@pytest.mark.parametrize("delta", (-0.001, 0.001))
def test_joint_focal_controls_match_off_axis_closed_form_and_preserve_center(delta: float) -> None:
    camera, plane, frame = _camera(), _plane(), _frame()
    original = camera.model_dump_json()
    baseline = InverseProjectionService(camera, plane).project_frame(frame)
    center = _frame(point_2d=(camera.cx, camera.cy))
    baseline_center = InverseProjectionService(camera, plane).project_frame(center)
    variants = conditioning.joint_focal_perturbations(camera)
    assert len(variants) == 2
    metadata, variant = next(row for row in variants if row[0]["delta"] == delta)
    assert metadata["variant_id"] == f"joint_focal:{delta:+g}"
    assert metadata["parameter"] == "fx_and_fy"
    assert metadata["diagnostic_family"] == "JOINT_FOCAL_LENGTH_ONLY"
    assert variant.fx == camera.fx * (1 + delta)
    assert variant.fy == camera.fy * (1 + delta)
    assert variant.cx == camera.cx and variant.cy == camera.cy
    assert variant.camera_to_world == camera.camera_to_world
    result = InverseProjectionService(variant, plane).project_frame(frame)
    baseline_xy = np.asarray(baseline.world_position[:2])
    expected_xy = baseline_xy / (1 + delta)
    np.testing.assert_allclose(result.world_position[:2], expected_xy, atol=1e-12, rtol=1e-12)
    expected_displacement = np.linalg.norm(baseline_xy) * abs(delta / (1 + delta))
    assert math.dist(result.world_position, baseline.world_position) == pytest.approx(
        expected_displacement, abs=1e-12, rel=1e-12
    )
    assert (
        InverseProjectionService(variant, plane).project_frame(center).world_position
        == baseline_center.world_position
    )
    assert camera.model_dump_json() == original
    assert len(conditioning.camera_perturbations(camera)) == 18
