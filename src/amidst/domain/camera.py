"""Calibrated pinhole camera and forward-projection result schemas."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, FiniteFloat, PositiveInt, model_validator

from amidst.domain.common import DomainModel, Pixel2, PositiveFinite

Row4 = tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
Matrix4 = tuple[Row4, Row4, Row4, Row4]


class Camera(DomainModel):
    camera_id: str = Field(min_length=1)
    camera_to_world: Matrix4
    fx: PositiveFinite
    fy: PositiveFinite
    cx: FiniteFloat
    cy: FiniteFloat
    width: PositiveInt
    height: PositiveInt
    clip_start: PositiveFinite = 0.1
    clip_end: PositiveFinite = 1000.0
    convention: Literal["BLENDER_NEG_Z_UP_Y"] = "BLENDER_NEG_Z_UP_Y"
    pixel_origin: Literal["TOP_LEFT_CONTINUOUS"] = "TOP_LEFT_CONTINUOUS"
    meters_per_unit: Literal[1] = 1
    floor_id: str | None = None
    zone_id: str | None = None

    @model_validator(mode="after")
    def valid_clipping(self) -> Self:
        if self.clip_end <= self.clip_start:
            raise ValueError("clip_end must exceed clip_start")
        return self


class ProjectionReason(StrEnum):
    IN_FRUSTUM = "IN_FRUSTUM"
    BEHIND_CAMERA = "BEHIND_CAMERA"
    NEAR_CLIPPED = "NEAR_CLIPPED"
    FAR_CLIPPED = "FAR_CLIPPED"
    OUTSIDE_FOV = "OUTSIDE_FOV"


class CameraProjection(DomainModel):
    point_2d: Pixel2 | None
    axial_depth: FiniteFloat
    in_frustum: bool
    reason: ProjectionReason
