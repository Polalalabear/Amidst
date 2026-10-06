"""Camera calibration parity with Blender's own projection, without rendering."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from amidst.domain.camera import Camera
from amidst.portability.blender import resolve_blender_executable
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
    stat = path.stat()
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest(), stat.st_size, stat.st_mtime_ns


def _school_scene() -> Path:
    research = REPO_ROOT / "blender/working/school_v2_research.blend"
    if research.is_file():
        return research
    original = REPO_ROOT / "blender/school_v2.blend"
    if original.is_file():
        return original
    pytest.skip("local school_v2 asset is unavailable")


def _run(code: str, *, scene: Path | None = None) -> None:
    command = [_blender(), "--background", "--factory-startup", "--disable-autoexec", "-noaudio"]
    if scene is not None:
        command.append(str(scene))
    command.extend(["--python-exit-code", "2", "--python-expr", code])
    completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
    assert "CAMERA_PARITY_OK" in completed.stdout


def _assert_projection_parity(records: list[dict[str, Any]], *, tolerance: float) -> None:
    for record in records:
        camera = Camera.model_validate(record["camera"])
        for probe in record["probes"]:
            projected = project_world(camera, tuple(probe["world"]))
            assert projected.point_2d == pytest.approx(probe["pixel"], abs=tolerance)
            assert projected.axial_depth == pytest.approx(probe["depth"], abs=1e-3)
            u, v = probe["pixel"]
            expected_visible = (
                camera.clip_start <= probe["depth"] <= camera.clip_end
                and 0 <= u < camera.width
                and 0 <= v < camera.height
            )
            assert projected.in_frustum == expected_visible


def test_factory_intrinsics_lens_shift_sensor_fit_pixel_aspect_and_percentage(
    tmp_path: Path,
) -> None:
    output = tmp_path / "factory_cameras.json"
    code = f"""
import json
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from amidst.simulation.blender_camera import extract_camera_dict
scene = bpy.context.scene
data = bpy.data.cameras.new('FixtureCalibration')
obj = bpy.data.objects.new('CAM_FIXTURE', data)
scene.collection.objects.link(obj)
obj.location = (7, -3, 5)
obj.rotation_euler = (0.12, -0.27, 0.41)
obj.scale = (2, 3, 4)
cases = [
    ('AUTO', 640, 480, 100, 1.0, 1.0, 0.0, 0.0, 22),
    ('HORIZONTAL', 643, 481, 37, 2.0, 0.75, 0.15, -0.1, 35),
    ('VERTICAL', 800, 450, 63, 0.8, 1.3, -0.2, 0.25, 85),
    ('AUTO', 400, 800, 50, 1.5, 0.7, 0.1, 0.2, 24)]
records = []
for fit, width, height, percentage, aspect_x, aspect_y, shift_x, shift_y, lens in cases:
    scene.render.resolution_x, scene.render.resolution_y = width, height
    scene.render.resolution_percentage = percentage
    scene.render.pixel_aspect_x, scene.render.pixel_aspect_y = aspect_x, aspect_y
    data.sensor_fit, data.sensor_width, data.sensor_height = fit, 36, 24
    data.shift_x, data.shift_y, data.lens = shift_x, shift_y, lens
    bpy.context.view_layer.update()
    camera = extract_camera_dict(scene, obj)
    assert camera['width'] == int(width * percentage / 100)
    assert camera['height'] == int(height * percentage / 100)
    probes = []
    for local in [(0,0,-20), (1.1,-0.7,-10), (-2,3,-30)]:
        world = obj.matrix_world.normalized() @ Vector(local)
        reference = world_to_camera_view(scene, obj, world)
        pixel = [reference.x * camera['width'], (1-reference.y) * camera['height']]
        probes.append({{'world': list(world), 'depth': reference.z,
                       'pixel': pixel}})
    records.append({{'camera': camera, 'probes': probes}})
Path({str(output)!r}).write_text(json.dumps(records, allow_nan=False), encoding='utf-8')
print('CAMERA_PARITY_OK')
"""
    _run(code)
    records = json.loads(output.read_text())
    assert len(records) == 4
    _assert_projection_parity(records, tolerance=2e-3)


def test_research_29_camera_catalog_and_blender_projection_parity(tmp_path: Path) -> None:
    source, output = _school_scene(), tmp_path / "school_cameras.json"
    before = _fingerprint(source)
    code = f"""
import json
import sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from amidst.simulation.blender_camera import extract_camera_catalog
scene = bpy.context.scene
cameras = extract_camera_catalog(scene, expected_count=29)
records = []
for camera in cameras:
    obj = scene.objects[camera['camera_id']]
    probes = []
    for local in [(0,0,-20), (1.1,-0.7,-10), (-2,3,-30)]:
        world = obj.matrix_world.normalized() @ Vector(local)
        reference = world_to_camera_view(scene, obj, world)
        pixel = [reference.x * camera['width'], (1-reference.y) * camera['height']]
        probes.append({{'world': list(world), 'depth': reference.z,
                       'pixel': pixel}})
    records.append({{'camera': camera, 'probes': probes}})
Path({str(output)!r}).write_text(json.dumps(records, allow_nan=False), encoding='utf-8')
print('CAMERA_PARITY_OK')
"""
    try:
        _run(code, scene=source)
    finally:
        assert _fingerprint(source) == before
    records = json.loads(output.read_text())
    assert len(records) == 29
    assert len({record["camera"]["camera_id"] for record in records}) == 29
    assert all(record["camera"]["camera_id"].startswith("CAM_") for record in records)
    assert not any("skp_camera" in record["camera"]["camera_id"] for record in records)
    _assert_projection_parity(records, tolerance=5e-2)


def test_unsupported_border_orthographic_reflection_and_shear_fail_closed() -> None:
    code = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
import bpy
from amidst.simulation.blender_camera import extract_camera_dict, extract_camera_catalog
scene = bpy.context.scene
data = bpy.data.cameras.new('Fixture')
obj = bpy.data.objects.new('CAM_FIXTURE', data)
scene.collection.objects.link(obj)
def reject(message):
    bpy.context.view_layer.update()
    try:
        extract_camera_dict(scene, obj)
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        raise AssertionError('invalid calibration was accepted')
data.type = 'ORTHO'
reject('PERSP')
data.type = 'PERSP'
scene.render.use_border = True
reject('border/crop')
scene.render.use_border = False
scene.render.use_crop_to_border = True
reject('border/crop')
scene.render.use_crop_to_border = False
obj.scale = (-1, 1, 1)
reject('proper rigid')
obj.scale = (1, 1, 1)
parent = bpy.data.objects.new('ShearParent', None)
scene.collection.objects.link(parent)
parent.scale = (2, 1, 1)
obj.parent = parent
obj.rotation_euler = (0, 0, 0.5)
reject('proper rigid')
obj.parent = None
obj.rotation_euler = (0, 0, 0)
bpy.context.view_layer.update()
assert len(extract_camera_catalog(scene, expected_count=1)) == 1
try:
    extract_camera_catalog(scene, expected_count=29)
except ValueError as error:
    assert 'expected 29' in str(error)
else:
    raise AssertionError('invalid camera count was accepted')
print('CAMERA_PARITY_OK')
"""
    _run(code)


def test_cli_camera_export_roundtrip_and_asset_nonoverwrite(tmp_path: Path) -> None:
    source, output = _school_scene(), tmp_path / "camera_catalog.json"
    before = _fingerprint(source)
    command = [
        "uv",
        "run",
        "python",
        "scripts/export_cameras.py",
        "--blend",
        str(source),
        "--output",
        str(output),
        "--blender-bin",
        _blender(),
    ]
    try:
        completed = subprocess.run(
            command, cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=90
        )
        assert "29 CAM_* cameras" in completed.stdout
        catalog = json.loads(output.read_text())
        assert catalog["data_kind"] == "SYNTHETIC"
        assert catalog["camera_count"] == 29
        assert catalog["source_asset_sha256"] == before[0]
        assert all(Camera.model_validate(raw) for raw in catalog["cameras"])
        contents_before = output.read_bytes()
        rejected = subprocess.run(
            command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
        )
        assert rejected.returncode == 2
        assert output.read_bytes() == contents_before
        rejected_asset = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "scripts/export_cameras.py",
                "--blend",
                str(source),
                "--output",
                str(source),
                "--overwrite",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert rejected_asset.returncode == 2
        assert "immutable" in rejected_asset.stderr
    finally:
        assert _fingerprint(source) == before
