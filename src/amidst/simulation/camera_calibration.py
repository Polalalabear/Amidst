"""Read-only Blender camera extraction with stdlib-only Blender-side imports."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from amidst.geometry.calibration import (
    calibration_content_sha256,
    frustum_geometry,
    image_fov_radians,
    matrix_inverse,
    multiply_matrices,
    rigid_inverse,
)
from amidst.simulation.blender_camera import extract_camera_dict

if TYPE_CHECKING:
    from amidst.domain.calibration import CameraCalibrationCatalog
    from amidst.domain.camera import Matrix4

REPO_ROOT = Path(__file__).resolve().parents[3]


def extract_camera_calibration_dict(scene: Any, obj: Any) -> dict[str, Any]:
    """Use the adopted pinhole convention; preserve raw and normalized poses separately."""
    import bpy  # type: ignore[import-not-found]

    camera = extract_camera_dict(scene, obj)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(depsgraph)
    data = evaluated.data
    raw = evaluated.matrix_world
    rigid = raw.normalized()
    matrix = cast("Matrix4", tuple(tuple(float(value) for value in row) for row in rigid))
    raw_matrix = cast("Matrix4", tuple(tuple(float(value) for value in row) for row in raw))
    view = rigid_inverse(matrix)
    projection = cast("Matrix4", tuple(tuple(float(value) for value in row) for row in
                       evaluated.calc_matrix_camera(
                           depsgraph, x=camera["width"], y=camera["height"],
                           scale_x=scene.render.pixel_aspect_x,
                           scale_y=scene.render.pixel_aspect_y,
                       )))
    quaternion = rigid.to_quaternion()
    return {
        "camera_name": obj.name,
        "camera": camera,
        "pose": {
            "evaluated_world_matrix": raw_matrix,
            "evaluated_world_inverse": matrix_inverse(raw_matrix),
            "rigid_camera_to_world": matrix,
            "world_to_camera": view,
            "position_world": tuple(float(value) for value in rigid.translation),
            "rotation_quaternion_wxyz": tuple(float(value) for value in quaternion),
            "rotation_euler_xyz_radians": tuple(float(value) for value in rigid.to_euler("XYZ")),
            "evaluated_axis_scale": tuple(float(raw.to_3x3().col[index].length)
                                          for index in range(3)),
        },
        "intrinsic_matrix": (
            (camera["fx"], 0.0, camera["cx"]),
            (0.0, camera["fy"], camera["cy"]), (0.0, 0.0, 1.0),
        ),
        "focal_length_mm": float(data.lens),
        "sensor_width_mm": float(data.sensor_width),
        "sensor_height_mm": float(data.sensor_height),
        "sensor_fit": data.sensor_fit,
        "pixel_aspect_xy": (float(scene.render.pixel_aspect_x), float(scene.render.pixel_aspect_y)),
        "shift_xy": (float(data.shift_x), float(data.shift_y)),
        "image_fov_xy_radians": image_fov_radians(
            camera["fx"], camera["fy"], camera["cx"], camera["cy"],
            camera["width"], camera["height"],
        ),
        "blender_sensor_angle_xy_radians": (float(data.angle_x), float(data.angle_y)),
        "projection_matrix": projection,
        "view_projection_matrix": multiply_matrices(projection, view),
        "frustum": frustum_geometry(
            matrix, camera["fx"], camera["fy"], camera["cx"], camera["cy"],
            camera["width"], camera["height"], camera["clip_start"], camera["clip_end"],
        ),
    }


def _fingerprint(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return digest.hexdigest(), stat.st_size, stat.st_mtime_ns


def read_camera_calibration_catalog(
    blend_path: str | Path,
    *,
    camera_config_version: str,
    blender_binary: str | None = None,
    expected_count: int = 29,
) -> CameraCalibrationCatalog:
    """Extract evaluated cameras without rendering, modifying, or saving the scene."""
    from amidst.domain.calibration import CameraCalibrationCatalog
    from amidst.geometry.calibration import validate_camera_calibration

    source = Path(blend_path).resolve(strict=True)
    if source.suffix.lower() != ".blend":
        raise ValueError("camera extraction requires a .blend source")
    if not camera_config_version or expected_count < 1:
        raise ValueError("camera config version and positive expected camera count are required")
    executable = blender_binary or os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if executable is None:
        installed = Path("/Applications/Blender.app/Contents/MacOS/blender")
        executable = str(installed) if installed.is_file() else None
    if executable is None:
        raise ValueError("Blender CLI unavailable; provide BLENDER_BIN or blender_binary")
    fingerprint = _fingerprint(source)
    with tempfile.TemporaryDirectory(prefix="amidst-calibration-") as directory:
        output = Path(directory) / "calibration.json"
        code = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
import bpy
from amidst.simulation.camera_calibration import extract_camera_calibration_dict
scene = bpy.context.scene
objects = sorted((o for o in scene.objects if o.type == 'CAMERA' and o.name.startswith('CAM_')),
                 key=lambda o: o.name)
if len(objects) != {expected_count!r}:
    raise ValueError('unexpected CAM_* camera count')
payload = {{
    'schema_version': 'camera_calibration/1',
    'camera_config_version': {camera_config_version!r},
    'calibration_content_sha256': '0' * 64,
    'source_asset_name': {source.name!r},
    'source_asset_sha256': {fingerprint[0]!r},
    'scene_name': scene.name, 'scene_frame': scene.frame_current,
    'scene_subframe': float(scene.frame_subframe),
    'source_scene_unit_system': scene.unit_settings.system,
    'source_scene_scale_length': float(scene.unit_settings.scale_length),
    'meters_per_blender_unit': 1.0,
    'cameras': [extract_camera_calibration_dict(scene, obj) for obj in objects],
    'excluded_camera_ids': sorted(o.name for o in scene.objects
                                 if o.type == 'CAMERA' and not o.name.startswith('CAM_')),
}}
Path({str(output)!r}).write_text(json.dumps(payload, allow_nan=False), encoding='utf-8')
print('BLENDER_CALIBRATION_EXPORT_OK')
"""
        try:
            completed = subprocess.run([
                executable, "--background", "--factory-startup", "--disable-autoexec", "-noaudio",
                str(source), "--python-exit-code", "2", "--python-expr", code,
            ], check=True, capture_output=True, text=True, timeout=120)
        finally:
            if _fingerprint(source) != fingerprint:
                raise RuntimeError(
                    "source Blender asset changed during read-only camera extraction"
                )
        if "BLENDER_CALIBRATION_EXPORT_OK" not in completed.stdout:
            raise RuntimeError("Blender did not confirm camera calibration extraction")
        catalog = CameraCalibrationCatalog.model_validate_json(output.read_text(encoding="utf-8"))
    for camera in catalog.cameras:
        validate_camera_calibration(camera)
    payload = catalog.model_dump(mode="json")
    payload["calibration_content_sha256"] = calibration_content_sha256(payload)
    return CameraCalibrationCatalog.model_validate(payload)


def export_camera_calibration_json(catalog: CameraCalibrationCatalog, path: str | Path) -> None:
    """Write a fresh JSON artifact; never overwrite an input or any existing file."""
    from amidst.geometry.calibration import validate_camera_calibration_catalog

    validated = validate_camera_calibration_catalog(catalog)
    destination = Path(path)
    if destination.suffix.lower() != ".json" or destination.resolve().suffix.lower() != ".json":
        raise ValueError("calibration output must use a .json destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(validated.model_dump(mode="json"), indent=2,
                                sort_keys=True, allow_nan=False) + "\n")


def load_camera_calibration_json(path: str | Path) -> CameraCalibrationCatalog:
    from amidst.domain.calibration import CameraCalibrationCatalog
    from amidst.geometry.calibration import validate_camera_calibration_catalog

    return validate_camera_calibration_catalog(CameraCalibrationCatalog.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    ))
