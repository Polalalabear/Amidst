"""Read-only actual school camera export plus generic Blender projection parity."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from amidst.domain.calibration import CameraCalibration
from amidst.geometry.calibration import transform_point, validate_camera_calibration
from amidst.portability.blender import resolve_blender_executable
from amidst.simulation.camera_calibration import (
    export_camera_calibration_json,
    load_camera_calibration_json,
    read_camera_calibration_catalog,
)
from amidst.simulation.virtual_camera import project_world

REPO_ROOT = Path(__file__).resolve().parents[2]


def _blender() -> str:
    try:
        return resolve_blender_executable()
    except FileNotFoundError:
        if os.environ.get("BLENDER_BIN"):
            raise
        pytest.skip("Blender CLI unavailable; configure BLENDER_BIN or PATH")



def _fingerprint(path: Path) -> tuple[str, int, int]:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    stat = path.stat()
    return digest, stat.st_size, stat.st_mtime_ns


def test_actual_school_v2_calibration_is_read_only_deterministic_and_roundtrips(
    tmp_path: Path,
) -> None:
    source = REPO_ROOT / "blender/school_v2.blend"
    if not source.is_file():
        pytest.skip("local private school_v2 source unavailable")
    fingerprint = _fingerprint(source)
    first = read_camera_calibration_catalog(
        source, camera_config_version="school-v2-calibration-v1", blender_binary=_blender(),
    )
    second = read_camera_calibration_catalog(
        source, camera_config_version="school-v2-calibration-v1", blender_binary=_blender(),
    )
    assert _fingerprint(source) == fingerprint
    assert first == second
    assert first.source_asset_sha256 == fingerprint[0]
    assert len(first.cameras) == 29
    assert first.excluded_camera_ids == ("skp_camera_Last_Saved_SketchUp_View",)
    assert all(item.camera.camera_id.startswith("CAM_") for item in first.cameras)
    paths = (tmp_path / "first.json", tmp_path / "second.json")
    for catalog, path in zip((first, second), paths, strict=True):
        export_camera_calibration_json(catalog, path)
    assert paths[0].read_bytes() == paths[1].read_bytes()
    assert load_camera_calibration_json(paths[0]) == first
    for calibration in first.cameras:
        camera = calibration.camera
        depth = (camera.clip_start + camera.clip_end) / 2
        world = transform_point(camera.camera_to_world, (0, 0, -depth))
        projected = project_world(camera, world)
        ndc = transform_point(calibration.view_projection_matrix, world)
        assert projected.point_2d == pytest.approx((camera.cx, camera.cy), abs=1e-3)
        assert (camera.width * (ndc[0] + 1) / 2, camera.height * (1 - ndc[1]) / 2) == (
            pytest.approx(projected.point_2d, abs=1e-3)
        )


def test_blender_projection_parity_with_shift_pixel_aspect_and_nonuniform_pose_scale(
    tmp_path: Path,
) -> None:
    output = tmp_path / "camera_variants.json"
    code = f"""
import sys, json
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / 'src')!r})
import bpy
from amidst.simulation.camera_calibration import extract_camera_calibration_dict
scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = 800, 600
scene.render.resolution_percentage = 75
scene.render.pixel_aspect_x, scene.render.pixel_aspect_y = 1.0, 1.25
rows = []
for index, fit in enumerate(('AUTO', 'HORIZONTAL', 'VERTICAL')):
    data = bpy.data.cameras.new('CAM_VARIANT_' + str(index))
    obj = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(obj)
    obj.location = (1, 2, 3)
    obj.rotation_euler = (0.3, -0.4, 0.8)
    obj.scale = (2, 3, 4)
    data.lens, data.sensor_fit = 45, fit
    data.shift_x, data.shift_y = 0.15, -0.08
    bpy.context.view_layer.update()
    rows.append(extract_camera_calibration_dict(scene, obj))
obj.scale = (-1, 1, 1)
bpy.context.view_layer.update()
try:
    extract_camera_calibration_dict(scene, obj)
    raise AssertionError('reflection must be rejected')
except ValueError:
    pass
data.type = 'ORTHO'
try:
    extract_camera_calibration_dict(scene, obj)
    raise AssertionError('orthographic calibration must be rejected')
except ValueError:
    pass
Path({str(output)!r}).write_text(json.dumps(rows, allow_nan=False), encoding='utf-8')
print('CAMERA_VARIANTS_OK')
"""
    completed = subprocess.run([
        _blender(), "--background", "--factory-startup", "--disable-autoexec", "-noaudio",
        "--python-exit-code", "2", "--python-expr", code,
    ], check=True, capture_output=True, text=True, timeout=60)
    assert "CAMERA_VARIANTS_OK" in completed.stdout
    for raw in json.loads(output.read_text(encoding="utf-8")):
        calibration = validate_camera_calibration(CameraCalibration.model_validate(raw))
        assert calibration.pose.evaluated_world_matrix != calibration.pose.rigid_camera_to_world
        assert calibration.pose.evaluated_axis_scale == pytest.approx((2, 3, 4))
        assert (calibration.camera.width, calibration.camera.height) == (600, 450)
        assert calibration.pixel_aspect_xy == (1.0, 1.25)


def test_calibration_cli_rejects_existing_output_and_blender_suffix_before_extraction(
    tmp_path: Path,
) -> None:
    for path in (tmp_path / "source.blend", tmp_path / "existing.json"):
        path.write_bytes(b"preserved source or artifact")
        completed = subprocess.run([
            sys.executable, str(REPO_ROOT / "scripts/export_camera_calibration.py"),
            "--output", str(path), "--camera-config-version", "v1",
        ], capture_output=True, text=True, timeout=10)
        assert completed.returncode == 2
        assert path.read_bytes() == b"preserved source or artifact"
