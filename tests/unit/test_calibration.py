"""Portable pose/frustum contract, round trips, immutable output and SDK consumer."""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.calibration import CameraCalibration, CameraCalibrationCatalog
from amidst.domain.camera import Camera
from amidst.geometry.calibration import (
    calibration_content_sha256,
    frustum_geometry,
    frustum_line_segments,
    image_fov_radians,
    matrix_inverse,
    multiply_matrices,
    pinhole_projection_matrix,
    rigid_inverse,
    transform_point,
    validate_camera_calibration,
)
from amidst.simulation.camera_calibration import (
    export_camera_calibration_json,
    load_camera_calibration_json,
)
from amidst.simulation.virtual_camera import project_world

REPO_ROOT = Path(__file__).resolve().parents[2]


def _calibration() -> CameraCalibration:
    camera = Camera(
        camera_id="CAM_FIXTURE", camera_to_world=(
            (1, 0, 0, 10), (0, 1, 0, 20), (0, 0, 1, 30), (0, 0, 0, 1),
        ), fx=800, fy=800, cx=320, cy=240, width=640, height=480, clip_start=1, clip_end=10,
    )
    raw = ((2.0, 0.0, 0.0, 10.0), (0.0, 3.0, 0.0, 20.0),
           (0.0, 0.0, 4.0, 30.0), (0.0, 0.0, 0.0, 1.0))
    view = rigid_inverse(camera.camera_to_world)
    projection = pinhole_projection_matrix(800, 800, 320, 240, 640, 480, 1, 10)
    return CameraCalibration.model_validate({
        "camera_name": camera.camera_id, "camera": camera.model_dump(),
        "pose": {
            "evaluated_world_matrix": raw,
            "evaluated_world_inverse": matrix_inverse(raw),
            "rigid_camera_to_world": camera.camera_to_world,
            "world_to_camera": view, "position_world": (10, 20, 30),
            "rotation_quaternion_wxyz": (1, 0, 0, 0),
            "rotation_euler_xyz_radians": (0, 0, 0), "evaluated_axis_scale": (2, 3, 4),
        },
        "intrinsic_matrix": ((800, 0, 320), (0, 800, 240), (0, 0, 1)),
        "focal_length_mm": 45, "sensor_width_mm": 36, "sensor_height_mm": 24,
        "sensor_fit": "HORIZONTAL", "pixel_aspect_xy": (1, 1), "shift_xy": (0, 0),
        "image_fov_xy_radians": image_fov_radians(800, 800, 320, 240, 640, 480),
        "blender_sensor_angle_xy_radians": (0.761012754, 0.521204783),
        "projection_matrix": projection,
        "view_projection_matrix": multiply_matrices(projection, view),
        "frustum": frustum_geometry(camera.camera_to_world, 800, 800, 320, 240, 640, 480, 1, 10),
    })


def _catalog() -> CameraCalibrationCatalog:
    catalog = CameraCalibrationCatalog(
        camera_config_version="fixture-v1", calibration_content_sha256="0" * 64,
        source_asset_name="SYNTHETIC_TEST_FIXTURE.blend", source_asset_sha256="a" * 64,
        scene_name="SYNTHETIC_TEST_FIXTURE", scene_frame=1, scene_subframe=0,
        source_scene_unit_system="METRIC", source_scene_scale_length=1,
        cameras=(_calibration(),), excluded_camera_ids=("skp_camera_Last_Saved_SketchUp_View",),
    )
    return catalog.model_copy(update={
        "calibration_content_sha256": calibration_content_sha256(catalog.model_dump(mode="json")),
    })


def test_camera_calibration_roundtrip_preserves_existing_camera_and_distinct_raw_pose() -> None:
    calibration = _calibration()
    assert validate_camera_calibration(calibration) == calibration
    assert CameraCalibration.model_validate_json(calibration.model_dump_json()) == calibration
    assert Camera.model_validate_json(calibration.camera.model_dump_json()) == calibration.camera
    assert calibration.pose.evaluated_world_matrix != calibration.pose.rigid_camera_to_world
    assert calibration.pose.position_world == (10, 20, 30)
    assert calibration.pose.evaluated_axis_scale == (2, 3, 4)
    assert calibration.camera.convention == "BLENDER_NEG_Z_UP_Y"
    assert calibration.intrinsic_convention == "CV_X_RIGHT_Y_DOWN_Z_FORWARD"


def test_frustum_corner_roundtrips_and_ndc_match_image_and_axial_clipping() -> None:
    calibration = _calibration()
    camera = calibration.camera
    expected_pixels = ((0, 0), (640, 0), (640, 480), (0, 480)) * 2
    for index, (local, world, pixels) in enumerate(zip(
        calibration.frustum.camera_space_corners,
        calibration.frustum.world_space_corners, expected_pixels, strict=True,
    )):
        assert transform_point(calibration.pose.world_to_camera, world) == pytest.approx(local)
        result = project_world(camera, world)
        assert result.point_2d == pytest.approx(pixels)
        assert result.axial_depth == (1 if index < 4 else 10)
        ndc = transform_point(calibration.view_projection_matrix, world)
        assert ndc[:2] == pytest.approx((2 * pixels[0] / 640 - 1, 1 - 2 * pixels[1] / 480))
        assert ndc[2] == pytest.approx(-1 if index < 4 else 1)
    assert len(frustum_line_segments(calibration)) == 12
    # Closed frustum boundaries do not turn right/bottom into valid observed pixels.
    assert not project_world(camera, calibration.frustum.world_space_corners[2]).in_frustum


@pytest.mark.parametrize("field", ["raw_scale", "view", "projection", "frustum", "quaternion"])
def test_calibration_fails_closed_on_inconsistent_geometry(field: str) -> None:
    payload = copy.deepcopy(_calibration().model_dump(mode="json"))
    if field == "raw_scale":
        payload["pose"]["evaluated_axis_scale"][0] = 4
    elif field == "view":
        payload["pose"]["world_to_camera"][0][3] += 1
    elif field == "projection":
        payload["projection_matrix"][0][0] += 1
    elif field == "frustum":
        payload["frustum"]["world_space_corners"][0][0] += 1
    else:
        payload["pose"]["rotation_quaternion_wxyz"][0] = 2
    with pytest.raises(ValueError, match="inconsistent"):
        validate_camera_calibration(CameraCalibration.model_validate(payload))


def test_invalid_provenance_free_schema_and_reflection_are_rejected() -> None:
    payload = _calibration().model_dump(mode="json")
    with pytest.raises(ValidationError):
        CameraCalibration.model_validate({**payload, "ground_truth_3d": [1, 2, 3]})
    payload["camera"]["camera_to_world"][0][0] = -1
    with pytest.raises(ValueError):
        validate_camera_calibration(CameraCalibration.model_validate(payload))


def test_catalog_export_is_deterministic_digest_bound_and_never_overwrites(tmp_path: Path) -> None:
    catalog = _catalog()
    first, second = tmp_path / "first.json", tmp_path / "second.json"
    export_camera_calibration_json(catalog, first)
    export_camera_calibration_json(catalog, second)
    assert first.read_bytes() == second.read_bytes()
    assert load_camera_calibration_json(first) == catalog
    with pytest.raises(FileExistsError):
        export_camera_calibration_json(catalog, first)
    invalid = catalog.model_copy(update={"camera_config_version": "tampered-v2"})
    with pytest.raises(ValueError, match="digest mismatch"):
        export_camera_calibration_json(invalid, tmp_path / "tampered.json")
    assert not (tmp_path / "tampered.json").exists()
    asset = tmp_path / "source.blend"
    asset.write_bytes(b"preserve immutable scene")
    with pytest.raises(ValueError, match=".json"):
        export_camera_calibration_json(catalog, asset)
    assert asset.read_bytes() == b"preserve immutable scene"


def test_blender_extraction_modules_import_with_no_site_packages() -> None:
    code = (
        f"import sys; sys.path.insert(0, {str(REPO_ROOT / 'src')!r}); "
        "import amidst.simulation.camera_calibration; "
        "assert 'pydantic' not in sys.modules; assert 'numpy' not in sys.modules; "
        "assert 'bpy' not in sys.modules"
    )
    subprocess.run([sys.executable, "-S", "-c", code], check=True, capture_output=True, text=True)
