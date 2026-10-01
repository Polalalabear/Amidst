"""Immutable geometry contracts; projection algorithms live outside domain."""

import math
from typing import Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel, Vec3


class Plane(DomainModel):
    """An explicitly configured plane with a normalized world-space normal."""

    plane_id: str = Field(min_length=1)
    point: Vec3
    normal: Vec3
    floor_id: str = Field(min_length=1)
    zone_id: str | None = None

    @model_validator(mode="after")
    def normalized_normal(self) -> Self:
        length = math.hypot(*(float(component) for component in self.normal))
        if not math.isclose(length, 1.0, rel_tol=0, abs_tol=1e-6):
            raise ValueError("plane normal must be a nonzero unit vector")
        return self
