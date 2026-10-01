"""Public synthetic camera evidence deliberately contains no hidden 3D coordinates."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel, Pixel2, Provenance, Timestamp


class VisibilityStatus(StrEnum):
    OBSERVED = "OBSERVED"
    GAP = "GAP"


class GapReason(StrEnum):
    BEHIND_CAMERA = "BEHIND_CAMERA"
    NEAR_CLIPPED = "NEAR_CLIPPED"
    FAR_CLIPPED = "FAR_CLIPPED"
    OUTSIDE_FOV = "OUTSIDE_FOV"
    OCCLUDED = "OCCLUDED"
    GEOMETRY_UNCERTAIN = "GEOMETRY_UNCERTAIN"
    RAYCAST_LIMIT = "RAYCAST_LIMIT"


class ObservationFrame(DomainModel):
    frame_id: int = Field(ge=0)
    timestamp: Timestamp
    target_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    status: VisibilityStatus
    point_2d: Pixel2 | None
    provenance: Literal[Provenance.OBSERVED] | None
    gap_reason: GapReason | None = None
    occluder_id: str | None = None
    data_kind: Literal["SYNTHETIC"] = "SYNTHETIC"

    @model_validator(mode="after")
    def consistent_visibility(self) -> Self:
        if self.status == VisibilityStatus.OBSERVED:
            if self.point_2d is None or self.provenance != Provenance.OBSERVED:
                raise ValueError("OBSERVED requires pixels and OBSERVED provenance")
            if self.gap_reason is not None or self.occluder_id is not None:
                raise ValueError("OBSERVED cannot carry a gap reason/occluder")
        elif self.point_2d is not None or self.provenance is not None or self.gap_reason is None:
            raise ValueError("GAP requires null pixels/provenance and an explicit reason")
        return self
