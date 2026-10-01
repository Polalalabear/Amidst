"""Ground-Truth-free pixel-to-plane inverse projection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from numpy.typing import NDArray
from pydantic import ValidationError

from amidst.domain.camera import Camera
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.domain.observation import ProjectedPoint

FloatArray = NDArray[np.float64]


class InverseProjectionFailure(StrEnum):
    INVALID_FRAME = "INVALID_FRAME"
    FRAME_NOT_OBSERVED = "FRAME_NOT_OBSERVED"
    CAMERA_MISMATCH = "CAMERA_MISMATCH"
    PIXEL_OUTSIDE_IMAGE = "PIXEL_OUTSIDE_IMAGE"
    INVALID_CAMERA_POSE = "INVALID_CAMERA_POSE"
    INVALID_PLANE = "INVALID_PLANE"
    RAY_PARALLEL_TO_PLANE = "RAY_PARALLEL_TO_PLANE"
    INTERSECTION_BEHIND_CAMERA = "INTERSECTION_BEHIND_CAMERA"
    NEAR_CLIPPED = "NEAR_CLIPPED"
    FAR_CLIPPED = "FAR_CLIPPED"
    NUMERICAL_FAILURE = "NUMERICAL_FAILURE"


class InverseProjectionError(ValueError):
    """A deterministic, caller-inspectable fail-closed projection error."""

    def __init__(self, failure: InverseProjectionFailure, message: str) -> None:
        super().__init__(message)
        self.failure = failure


def _point_id(frame: ObservationFrame, plane: Plane) -> str:
    identity = json.dumps(
        [
            frame.camera_id,
            frame.target_id,
            frame.frame_id,
            float(frame.timestamp).hex(),
            plane.plane_id,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"projected:{hashlib.sha256(identity.encode()).hexdigest()}"


def _validated_pose(camera: Camera) -> tuple[FloatArray, FloatArray]:
    try:
        Camera.model_validate(camera.model_dump())
    except ValidationError as error:
        raise InverseProjectionError(
            InverseProjectionFailure.INVALID_CAMERA_POSE,
            "camera calibration must satisfy the Camera contract",
        ) from error
    matrix = np.asarray(camera.camera_to_world, dtype=np.float64)
    rotation = matrix[:3, :3]
    if not (
        np.isfinite(matrix).all()
        and np.allclose(matrix[3], (0, 0, 0, 1), atol=1e-6, rtol=0)
        and np.allclose(rotation.T @ rotation, np.eye(3), atol=1e-5, rtol=0)
        and abs(float(np.linalg.det(rotation)) - 1) < 1e-5
    ):
        raise InverseProjectionError(
            InverseProjectionFailure.INVALID_CAMERA_POSE,
            "camera_to_world must be a finite proper rigid transform",
        )
    return rotation, matrix[:3, 3]


def _validated_plane(plane: Plane) -> tuple[FloatArray, FloatArray]:
    try:
        Plane.model_validate(plane.model_dump())
    except ValidationError as error:
        raise InverseProjectionError(
            InverseProjectionFailure.INVALID_PLANE,
            "projection plane must satisfy the Plane contract",
        ) from error
    return (
        np.asarray(plane.point, dtype=np.float64),
        np.asarray(plane.normal, dtype=np.float64),
    )


@dataclass(frozen=True, slots=True)
class InverseProjectionService:
    """Project one camera's observed pixels onto one explicitly bound plane."""

    camera: Camera
    plane: Plane

    def __post_init__(self) -> None:
        _validated_pose(self.camera)
        _validated_plane(self.plane)

    def project_frame(self, frame: ObservationFrame) -> ProjectedPoint:
        if not isinstance(frame, ObservationFrame):
            raise InverseProjectionError(
                InverseProjectionFailure.INVALID_FRAME,
                "inverse projection requires an ObservationFrame",
            )
        try:
            frame = ObservationFrame.model_validate(frame.model_dump(mode="python"))
        except ValidationError as error:
            raise InverseProjectionError(
                InverseProjectionFailure.INVALID_FRAME,
                "frame must satisfy the full 2D evidence contract",
            ) from error
        if frame.status != VisibilityStatus.OBSERVED or frame.point_2d is None:
            raise InverseProjectionError(
                InverseProjectionFailure.FRAME_NOT_OBSERVED,
                "inverse projection requires an OBSERVED frame with pixels",
            )
        if frame.camera_id != self.camera.camera_id:
            raise InverseProjectionError(
                InverseProjectionFailure.CAMERA_MISMATCH,
                "observation camera does not match configured calibration",
            )
        u, v = (float(coordinate) for coordinate in frame.point_2d)
        if not (0 <= u < self.camera.width and 0 <= v < self.camera.height):
            raise InverseProjectionError(
                InverseProjectionFailure.PIXEL_OUTSIDE_IMAGE,
                "observed pixel lies outside the camera's half-open image bounds",
            )

        rotation, origin = _validated_pose(self.camera)
        local_direction = np.asarray(
            (
                (u - float(self.camera.cx)) / float(self.camera.fx),
                (float(self.camera.cy) - v) / float(self.camera.fy),
                -1.0,
            ),
            dtype=np.float64,
        )
        world_direction = rotation @ local_direction
        plane_point, normal = _validated_plane(self.plane)
        denominator = float(normal @ world_direction)
        direction_norm = float(np.linalg.norm(world_direction))
        if not (
            np.isfinite(local_direction).all()
            and np.isfinite(world_direction).all()
            and np.isfinite(denominator)
            and np.isfinite(direction_norm)
            and direction_norm > 0
        ):
            raise InverseProjectionError(
                InverseProjectionFailure.NUMERICAL_FAILURE,
                "camera ray calculation produced a non-finite result",
            )
        incidence = abs(denominator) / direction_norm
        if incidence <= 1e-12:
            raise InverseProjectionError(
                InverseProjectionFailure.RAY_PARALLEL_TO_PLANE,
                "camera ray is parallel to or contained in the configured plane",
            )
        axial_depth = float(normal @ (plane_point - origin) / denominator)
        if not np.isfinite(axial_depth):
            raise InverseProjectionError(
                InverseProjectionFailure.NUMERICAL_FAILURE,
                "plane intersection produced a non-finite axial depth",
            )
        if axial_depth <= 0:
            raise InverseProjectionError(
                InverseProjectionFailure.INTERSECTION_BEHIND_CAMERA,
                "configured plane intersects the ray at or behind the camera",
            )
        if axial_depth < self.camera.clip_start:
            raise InverseProjectionError(
                InverseProjectionFailure.NEAR_CLIPPED,
                "plane intersection is before the camera near clip",
            )
        if axial_depth > self.camera.clip_end:
            raise InverseProjectionError(
                InverseProjectionFailure.FAR_CLIPPED,
                "plane intersection is beyond the camera far clip",
            )

        position = origin + axial_depth * world_direction
        if not np.isfinite(position).all():
            raise InverseProjectionError(
                InverseProjectionFailure.NUMERICAL_FAILURE,
                "plane intersection produced a non-finite world position",
            )
        return ProjectedPoint(
            point_id=_point_id(frame, self.plane),
            camera_id=frame.camera_id,
            plane_id=self.plane.plane_id,
            timestamp=frame.timestamp,
            world_position=(float(position[0]), float(position[1]), float(position[2])),
            projection_quality=min(1.0, incidence),
            floor_id=self.plane.floor_id,
            zone_id=self.plane.zone_id,
        )
