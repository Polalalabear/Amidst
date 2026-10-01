"""Camera calibration geometry; pure standard library supports Blender extraction.

Domain imports occur only when validating a completed export, so the extraction
process does not need Pydantic or NumPy in Blender's bundled Python.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from amidst.domain.calibration import CameraCalibration, CameraCalibrationCatalog
    from amidst.domain.camera import Matrix4
    from amidst.domain.common import Vec3


def multiply_matrices(left: Matrix4, right: Matrix4) -> Matrix4:
    rows = tuple(tuple(
        math.fsum(left[row][index] * right[index][column] for index in range(4))
        for column in range(4)
    ) for row in range(4))
    return (rows[0], rows[1], rows[2], rows[3])  # type: ignore[return-value]


def transform_point(matrix: Matrix4, point: Vec3) -> Vec3:
    homogeneous = (*point, 1.0)
    result = tuple(math.fsum(row[index] * homogeneous[index] for index in range(4))
                   for row in matrix)
    if not math.isfinite(result[3]) or abs(result[3]) < 1e-15:
        raise ValueError("camera transform produced a zero/nonfinite homogeneous denominator")
    return (result[0] / result[3], result[1] / result[3], result[2] / result[3])


def rigid_inverse(matrix: Matrix4) -> Matrix4:
    return (
        (matrix[0][0], matrix[1][0], matrix[2][0], -math.fsum(
            matrix[index][0] * matrix[index][3] for index in range(3))),
        (matrix[0][1], matrix[1][1], matrix[2][1], -math.fsum(
            matrix[index][1] * matrix[index][3] for index in range(3))),
        (matrix[0][2], matrix[1][2], matrix[2][2], -math.fsum(
            matrix[index][2] * matrix[index][3] for index in range(3))),
        (0.0, 0.0, 0.0, 1.0),
    )


def matrix_inverse(matrix: Matrix4) -> Matrix4:
    augmented = [list(row) + [float(i == j) for j in range(4)]
                 for i, row in enumerate(matrix)]
    for column in range(4):
        pivot = max(range(column, 4), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-15:
            raise ValueError("camera world matrix is singular")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        denominator = augmented[column][column]
        augmented[column] = [value / denominator for value in augmented[column]]
        for row in range(4):
            if row != column:
                factor = augmented[row][column]
                augmented[row] = [first - factor * second for first, second in
                                  zip(augmented[row], augmented[column], strict=True)]
    rows = tuple(tuple(row[4:]) for row in augmented)
    return (rows[0], rows[1], rows[2], rows[3])  # type: ignore[return-value]


def pinhole_projection_matrix(
    fx: float, fy: float, cx: float, cy: float,
    width: int, height: int, near: float, far: float,
) -> Matrix4:
    return (
        (2 * fx / width, 0.0, 1 - 2 * cx / width, 0.0),
        (0.0, 2 * fy / height, 2 * cy / height - 1, 0.0),
        (0.0, 0.0, -(far + near) / (far - near), -2 * far * near / (far - near)),
        (0.0, 0.0, -1.0, 0.0),
    )


def image_fov_radians(
    fx: float, fy: float, cx: float, cy: float, width: int, height: int,
) -> tuple[float, float]:
    return (
        math.atan((width - cx) / fx) - math.atan(-cx / fx),
        math.atan(cy / fy) - math.atan((cy - height) / fy),
    )


def frustum_geometry(
    camera_to_world: Matrix4, fx: float, fy: float, cx: float, cy: float,
    width: int, height: int, near: float, far: float,
) -> dict[str, object]:
    local = tuple(
        ((u - cx) * depth / fx, (cy - v) * depth / fy, -depth)
        for depth in (near, far)
        for u, v in ((0, 0), (width, 0), (width, height), (0, height))
    )
    return {
        "camera_space_corners": local,
        "world_space_corners": tuple(transform_point(camera_to_world, point) for point in local),
    }


def frustum_line_segments(calibration: CameraCalibration) -> tuple[tuple[Vec3, Vec3], ...]:
    return tuple(
        (calibration.frustum.world_space_corners[start],
         calibration.frustum.world_space_corners[end])
        for start, end in calibration.frustum.edge_indices
    )


def validate_camera_calibration(calibration: CameraCalibration) -> CameraCalibration:
    """Fail closed on cross-field pose, projection, orientation, and frustum drift."""
    from amidst.domain.calibration import CameraCalibration

    validated = CameraCalibration.model_validate(calibration.model_dump())
    camera, pose = validated.camera, validated.pose
    matrix = camera.camera_to_world

    def close(actual: object, expected: object, *, tolerance: float = 1e-5) -> None:
        if isinstance(actual, (tuple, list)) and isinstance(expected, (tuple, list)):
            if len(actual) != len(expected):
                raise ValueError("camera calibration geometry shape mismatch")
            for first, second in zip(actual, expected, strict=True):
                close(first, second, tolerance=tolerance)
        elif not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
            raise ValueError("camera calibration geometry must contain numbers")
        elif not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
            raise ValueError("camera calibration geometry is inconsistent")

    close(matrix[3], (0, 0, 0, 1), tolerance=1e-6)
    rotation = tuple(tuple(matrix[row][column] for column in range(3)) for row in range(3))
    for i in range(3):
        for j in range(3):
            close(math.fsum(rotation[row][i] * rotation[row][j] for row in range(3)),
                  1 if i == j else 0)
    determinant = (
        rotation[0][0] * (rotation[1][1] * rotation[2][2] - rotation[1][2] * rotation[2][1])
        - rotation[0][1] * (rotation[1][0] * rotation[2][2] - rotation[1][2] * rotation[2][0])
        + rotation[0][2] * (rotation[1][0] * rotation[2][1] - rotation[1][1] * rotation[2][0])
    )
    close(determinant, 1)
    close(pose.rigid_camera_to_world, matrix)
    close(pose.world_to_camera, rigid_inverse(matrix))
    close(pose.position_world, (matrix[0][3], matrix[1][3], matrix[2][3]))
    close(pose.evaluated_world_matrix[3], (0, 0, 0, 1), tolerance=1e-6)
    for row in range(3):
        for column in range(3):
            close(pose.evaluated_world_matrix[row][column],
                  matrix[row][column] * pose.evaluated_axis_scale[column])
        close(pose.evaluated_world_matrix[row][3], matrix[row][3])
    close(multiply_matrices(pose.evaluated_world_matrix, pose.evaluated_world_inverse),
          ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
    w, x, y, z = pose.rotation_quaternion_wxyz
    close(w * w + x * x + y * y + z * z, 1)
    close(rotation, (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)),
    ))
    ex, ey, ez = pose.rotation_euler_xyz_radians
    sx, sy, sz, cx, cy, cz = (
        math.sin(ex), math.sin(ey), math.sin(ez), math.cos(ex), math.cos(ey), math.cos(ez)
    )
    close(rotation, (
        (cy * cz, sx * sy * cz - cx * sz, cx * sy * cz + sx * sz),
        (cy * sz, sx * sy * sz + cx * cz, cx * sy * sz - sx * cz),
        (-sy, sx * cy, cx * cy),
    ))
    close(validated.intrinsic_matrix,
          ((camera.fx, 0, camera.cx), (0, camera.fy, camera.cy), (0, 0, 1)))
    close(validated.projection_matrix, pinhole_projection_matrix(
        camera.fx, camera.fy, camera.cx, camera.cy, camera.width, camera.height,
        camera.clip_start, camera.clip_end,
    ))
    close(validated.view_projection_matrix,
          multiply_matrices(validated.projection_matrix, pose.world_to_camera))
    close(validated.image_fov_xy_radians, image_fov_radians(
        camera.fx, camera.fy, camera.cx, camera.cy, camera.width, camera.height,
    ))
    expected_frustum = frustum_geometry(
        matrix, camera.fx, camera.fy, camera.cx, camera.cy, camera.width, camera.height,
        camera.clip_start, camera.clip_end,
    )
    close(validated.frustum.camera_space_corners, expected_frustum["camera_space_corners"])
    close(validated.frustum.world_space_corners, expected_frustum["world_space_corners"])
    return validated


def calibration_content_sha256(payload: Mapping[str, object]) -> str:
    content = {key: value for key, value in payload.items() if key != "calibration_content_sha256"}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_camera_calibration_catalog(
    catalog: CameraCalibrationCatalog,
) -> CameraCalibrationCatalog:
    from amidst.domain.calibration import CameraCalibrationCatalog

    validated = CameraCalibrationCatalog.model_validate(catalog.model_dump())
    for camera in validated.cameras:
        validate_camera_calibration(camera)
    if calibration_content_sha256(validated.model_dump(mode="json")) != (
        validated.calibration_content_sha256
    ):
        raise ValueError("camera calibration content digest mismatch")
    return validated
