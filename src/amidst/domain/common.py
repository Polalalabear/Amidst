"""Shared finite coordinate types and evidence provenance."""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

Vec3 = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
Pixel2 = tuple[FiniteFloat, FiniteFloat]
Timestamp = Annotated[FiniteFloat, Field(ge=0)]
PositiveFinite = Annotated[FiniteFloat, Field(gt=0)]


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class Provenance(StrEnum):
    OBSERVED = "OBSERVED"
    PROJECTED = "PROJECTED"
    INFERRED_GAP = "INFERRED_GAP"
    GROUND_TRUTH = "GROUND_TRUTH"
