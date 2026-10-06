"""Approved research-model units; no inference, geometry mutation or Blender import."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.scene_geometry import Authority, Digest, GeometryModel


class ArchitecturalScale(GeometryModel):
    schema_version: Literal["architectural-scale-v1"] = "architectural-scale-v1"
    scope: Literal["PHASE1_SCHOOL_V3_RESEARCH_MODEL"] = "PHASE1_SCHOOL_V3_RESEARCH_MODEL"
    source_asset_sha256: Digest
    metres_per_blender_unit: Annotated[FiniteFloat, Field(gt=0)]
    authority: Authority
    approval_id: str = Field(min_length=1)
    approval_basis: Literal["USER_DEFINED_RESEARCH_MODEL_SETTING"] = (
        "USER_DEFINED_RESEARCH_MODEL_SETTING"
    )
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    measurement_role: Literal["SANITY_CHECK_EVIDENCE"] = "SANITY_CHECK_EVIDENCE"
    source_geometry_scaled: Literal[False] = False
    external_dimensions_required: Literal[False] = False

    @model_validator(mode="after")
    def validate_approval(self) -> Self:
        if self.authority != Authority.APPROVED:
            raise ValueError("architectural scale requires explicit APPROVED user authority")
        if not self.approval_id.strip() or any(not value.strip() for value in self.evidence_ids):
            raise ValueError("scale approval and evidence identities cannot be blank")
        return self

    def require_source_sha256(self, source_sha256: str) -> None:
        checked = ArchitecturalScale.model_validate_json(self.model_dump_json())
        if checked.source_asset_sha256 != source_sha256:
            raise ValueError("architectural scale source SHA-256 mismatch")

    def _convert(self, value: float, exponent: int = 1) -> float:
        checked = ArchitecturalScale.model_validate_json(self.model_dump_json())
        if isinstance(value, bool) or not isinstance(value, (int, float)) or (
            not math.isfinite(value)
        ):
            raise ValueError("physical quantity must be finite")
        try:
            factor = checked.metres_per_blender_unit ** exponent
        except OverflowError as error:
            raise ValueError("physical unit factor overflow") from error
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("physical unit factor is outside finite positive range")
        result = value * factor
        if not math.isfinite(result):
            raise ValueError("physical quantity conversion overflow")
        return result

    def to_metres(self, length_bu: float) -> float:
        return self._convert(length_bu)

    def to_blender_units(self, length_m: float) -> float:
        return self._convert(length_m, -1)

    def to_square_metres(self, area_bu2: float) -> float:
        return self._convert(area_bu2, 2)

    def to_cubic_metres(self, volume_bu3: float) -> float:
        return self._convert(volume_bu3, 3)

    def speed_to_metres_per_second(self, speed_bu_per_s: float) -> float:
        return self.to_metres(speed_bu_per_s)

    def speed_to_blender_units_per_second(self, speed_m_per_s: float) -> float:
        return self.to_blender_units(speed_m_per_s)


def load_architectural_scale(
    path: Path | str, expected_source_sha256: str | None = None,
) -> ArchitecturalScale:
    scale = ArchitecturalScale.model_validate_json(Path(path).read_bytes())
    if expected_source_sha256 is not None:
        scale.require_source_sha256(expected_source_sha256)
    return scale


def scale_for_scene_config(
    config: dict[str, object], expected_source_sha256: str,
) -> ArchitecturalScale | None:
    """Legacy fixtures retain 1:1; active non-1 units require the source-bound approval."""
    path = config.get("architectural_scale_config")
    ratio = config.get("meters_per_blender_unit")
    if path is None:
        if ratio != 1.0:
            raise ValueError("non-1 scene scale requires source-bound architectural authority")
        return None
    if not isinstance(path, str):
        raise ValueError("architectural_scale_config must be a path")
    scale = load_architectural_scale(path, expected_source_sha256)
    if ratio != scale.metres_per_blender_unit:
        raise ValueError("scene config scale differs from approved architectural scale")
    declared = config.get("scale_authority")
    if declared is not None and declared != "APPROVED":
        raise ValueError("scene config scale authority differs from approved record")
    return scale


def architectural_scale_metadata(scale: ArchitecturalScale) -> dict[str, object]:
    checked = ArchitecturalScale.model_validate_json(scale.model_dump_json())
    return checked.model_dump(mode="json")
