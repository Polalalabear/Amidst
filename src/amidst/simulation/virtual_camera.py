"""Simulation-only world-to-pixel projection; inference never consumes GT here."""

from __future__ import annotations

import numpy as np

from amidst.domain.camera import Camera, CameraProjection, ProjectionReason
from amidst.domain.common import Vec3


def project_world(camera: Camera, position: Vec3) -> CameraProjection:
    """Project a world point into top-left continuous pixels with axial clipping."""
    matrix = np.asarray(camera.camera_to_world, dtype=np.float64)
    rotation = matrix[:3, :3]
    if not np.allclose(matrix[3], (0, 0, 0, 1), atol=1e-6, rtol=0) or not (
        np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5, rtol=0)
        and abs(float(np.linalg.det(rotation)) - 1) < 1e-5
    ):
        raise ValueError("camera_to_world must be a proper rigid transform")
    point = np.asarray(position, dtype=np.float64)
    if point.shape != (3,) or not np.isfinite(point).all():
        raise ValueError("world position must have three finite coordinates")
    local = np.linalg.solve(matrix, np.append(point, 1.0))[:3]
    depth = float(-local[2])
    if depth <= 0:
        return CameraProjection(
            point_2d=None,
            axial_depth=depth,
            in_frustum=False,
            reason=ProjectionReason.BEHIND_CAMERA,
        )
    if depth < camera.clip_start or depth > camera.clip_end:
        return CameraProjection(
            point_2d=None,
            axial_depth=depth,
            in_frustum=False,
            reason=(
                ProjectionReason.NEAR_CLIPPED
                if depth < camera.clip_start
                else ProjectionReason.FAR_CLIPPED
            ),
        )
    pixel = (
        float(camera.fx * local[0] / depth + camera.cx),
        float(camera.cy - camera.fy * local[1] / depth),
    )
    if not (0 <= pixel[0] < camera.width and 0 <= pixel[1] < camera.height):
        reason = ProjectionReason.OUTSIDE_FOV
    else:
        reason = ProjectionReason.IN_FRUSTUM
    return CameraProjection(
        point_2d=pixel,
        axial_depth=depth,
        in_frustum=reason == ProjectionReason.IN_FRUSTUM,
        reason=reason,
    )
