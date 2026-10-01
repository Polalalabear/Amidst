"""Read-only Blender pinhole calibration, independent of bundled Python extras.

The camera convention is Blender's local -Z forward/+Y up, mapped to top-left
continuous pixels. Naming-derived floor/zone fields are labels, not proof of
walkable regions or valid cross-floor connectivity.
"""

from __future__ import annotations

import math
import re
from typing import Any


def extract_camera_dict(scene: Any, obj: Any) -> dict[str, Any]:
    """Extract a normalized rigid evaluated pose and Blender view-frame intrinsics."""
    import bpy  # type: ignore[import-not-found]

    if scene != bpy.context.scene:
        raise ValueError("camera extraction requires the active Blender scene")
    if obj.type != "CAMERA" or obj not in tuple(scene.objects):
        raise ValueError("object must be a camera linked to the active scene")
    camera = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    data = camera.data
    if data.type != "PERSP":
        raise ValueError("only PERSP pinhole cameras are supported")
    if scene.render.use_border or scene.render.use_crop_to_border:
        raise ValueError("render border/crop camera calibration is unsupported")
    values = (
        data.lens,
        data.sensor_width,
        data.sensor_height,
        data.clip_start,
        data.clip_end,
        scene.render.pixel_aspect_x,
        scene.render.pixel_aspect_y,
    )
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError(
            "camera lens, sensor, clipping and pixel aspect must be finite and positive"
        )
    if data.clip_end <= data.clip_start:
        raise ValueError("camera clip_end must exceed clip_start")
    if not all(math.isfinite(value) for value in (data.shift_x, data.shift_y)):
        raise ValueError("camera shift must be finite")
    width = int(scene.render.resolution_x * scene.render.resolution_percentage / 100)
    height = int(scene.render.resolution_y * scene.render.resolution_percentage / 100)
    if width <= 0 or height <= 0:
        raise ValueError("rendered resolution must be positive")

    world_matrix = camera.matrix_world.normalized()
    rotation = world_matrix.to_3x3()
    columns = [rotation.col[index] for index in range(3)]
    if not all(math.isfinite(value) for row in world_matrix for value in row):
        raise ValueError("camera pose must be finite")
    if (
        any(
            abs(columns[i].dot(columns[j]) - (1.0 if i == j else 0.0)) > 1e-5
            for i in range(3)
            for j in range(3)
        )
        or abs(rotation.determinant() - 1.0) > 1e-5
        or any(
            abs(world_matrix[3][index] - (1.0 if index == 3 else 0.0)) > 1e-6 for index in range(4)
        )
    ):
        raise ValueError(
            "camera pose must normalize to a proper rigid transform; no shear/reflection"
        )

    frame = data.view_frame(scene=scene)
    if any(vertex.z >= 0 or not all(math.isfinite(value) for value in vertex) for vertex in frame):
        raise ValueError("camera view frame must be finite and face local -Z")
    horizontal = [float(vertex.x / -vertex.z) for vertex in frame]
    vertical = [float(vertex.y / -vertex.z) for vertex in frame]
    left, right = min(horizontal), max(horizontal)
    bottom, top = min(vertical), max(vertical)
    if right <= left or top <= bottom:
        raise ValueError("camera view frame is degenerate")
    fx, fy = width / (right - left), height / (top - bottom)

    parts = obj.name.split("_")
    floor_id = parts[1] if len(parts) > 2 and re.fullmatch(r"[0-9]+F", parts[1]) else None
    zone_parts = parts[2:] if floor_id else []
    if len(zone_parts) > 1 and zone_parts[-1].isdigit():
        zone_parts = zone_parts[:-1]
    return {
        "camera_id": obj.name,
        "camera_to_world": [[float(value) for value in row] for row in world_matrix],
        "fx": fx,
        "fy": fy,
        "cx": -left * fx,
        "cy": top * fy,
        "width": width,
        "height": height,
        "clip_start": float(data.clip_start),
        "clip_end": float(data.clip_end),
        "convention": "BLENDER_NEG_Z_UP_Y",
        "pixel_origin": "TOP_LEFT_CONTINUOUS",
        "meters_per_unit": 1.0,
        "floor_id": floor_id,
        "zone_id": "_".join(zone_parts) or None,
    }


def extract_camera_catalog(
    scene: Any, *, expected_count: int | None = None
) -> tuple[dict[str, Any], ...]:
    """Select only CAM_* objects, never the non-finite saved SketchUp camera."""
    cameras = sorted(
        (obj for obj in scene.objects if obj.type == "CAMERA" and obj.name.startswith("CAM_")),
        key=lambda obj: obj.name,
    )
    if expected_count is not None and len(cameras) != expected_count:
        raise ValueError(f"expected {expected_count} CAM_* cameras, found {len(cameras)}")
    return tuple(extract_camera_dict(scene, obj) for obj in cameras)
