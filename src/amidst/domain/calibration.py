"""Portable camera export contracts; no Blender types or geometry algorithms."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.domain.camera import Camera, Matrix4
from amidst.domain.common import DomainModel, PositiveFinite, Vec3

Matrix3 = tuple[Vec3, Vec3, Vec3]
QuaternionWXYZ = tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
EightCorners = Annotated[tuple[Vec3, ...], Field(min_length=8, max_length=8)]
FRUSTUM_EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
)


class CameraPose(DomainModel):
    evaluated_world_matrix: Matrix4
    evaluated_world_inverse: Matrix4
    rigid_camera_to_world: Matrix4
    world_to_camera: Matrix4
    position_world: Vec3
    rotation_quaternion_wxyz: QuaternionWXYZ
    rotation_euler_xyz_radians: Vec3
    evaluated_axis_scale: tuple[PositiveFinite, PositiveFinite, PositiveFinite]
    normalization_policy: Literal["NORMALIZE_BASIS_COLUMNS_NO_SHEAR_REFLECTION"] = (
        "NORMALIZE_BASIS_COLUMNS_NO_SHEAR_REFLECTION"
    )


class CameraFrustum(DomainModel):
    corner_order: Literal["NEAR_TL_TR_BR_BL_FAR_TL_TR_BR_BL"] = (
        "NEAR_TL_TR_BR_BL_FAR_TL_TR_BR_BL"
    )
    camera_space_corners: EightCorners
    world_space_corners: EightCorners
    edge_indices: tuple[tuple[int, int], ...] = FRUSTUM_EDGES
    image_boundaries: Literal["CLOSED_GEOMETRIC_BOUNDARY_NOT_VALID_PIXEL_SAMPLES"] = (
        "CLOSED_GEOMETRIC_BOUNDARY_NOT_VALID_PIXEL_SAMPLES"
    )

    @model_validator(mode="after")
    def canonical_edges(self) -> Self:
        if self.edge_indices != FRUSTUM_EDGES:
            raise ValueError("frustum must use the canonical twelve boundary edges")
        return self


class CameraCalibration(DomainModel):
    camera_name: str = Field(min_length=1)
    camera: Camera
    pose: CameraPose
    intrinsic_matrix: Matrix3
    intrinsic_convention: Literal["CV_X_RIGHT_Y_DOWN_Z_FORWARD"] = (
        "CV_X_RIGHT_Y_DOWN_Z_FORWARD"
    )
    focal_length_mm: PositiveFinite
    sensor_width_mm: PositiveFinite
    sensor_height_mm: PositiveFinite
    sensor_fit: Literal["AUTO", "HORIZONTAL", "VERTICAL"]
    pixel_aspect_xy: tuple[PositiveFinite, PositiveFinite]
    shift_xy: tuple[FiniteFloat, FiniteFloat]
    image_fov_xy_radians: tuple[PositiveFinite, PositiveFinite]
    blender_sensor_angle_xy_radians: tuple[PositiveFinite, PositiveFinite]
    projection_matrix: Matrix4
    view_projection_matrix: Matrix4
    projection_convention: Literal["OPENGL_NDC_X_RIGHT_Y_UP_Z_MINUS1_TO1"] = (
        "OPENGL_NDC_X_RIGHT_Y_UP_Z_MINUS1_TO1"
    )
    frustum: CameraFrustum

    @model_validator(mode="after")
    def matching_identity(self) -> Self:
        if self.camera_name != self.camera.camera_id:
            raise ValueError("camera object name must match exported camera identity")
        return self


class CameraCalibrationCatalog(DomainModel):
    schema_version: Literal["camera_calibration/1"] = "camera_calibration/1"
    camera_config_version: str = Field(min_length=1)
    calibration_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_asset_name: str = Field(min_length=1)
    source_asset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scene_name: str = Field(min_length=1)
    scene_frame: int
    scene_subframe: Annotated[FiniteFloat, Field(ge=0, lt=1)]
    source_scene_unit_system: str
    source_scene_scale_length: PositiveFinite
    meters_per_blender_unit: Literal[1] = 1
    cameras: tuple[CameraCalibration, ...] = Field(min_length=1)
    excluded_camera_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def sorted_unique_cameras(self) -> Self:
        identities = tuple(item.camera.camera_id for item in self.cameras)
        if identities != tuple(sorted(set(identities))):
            raise ValueError("calibration catalog cameras must be unique and sorted")
        if set(identities) & set(self.excluded_camera_ids):
            raise ValueError("included and excluded camera identities cannot overlap")
        return self
