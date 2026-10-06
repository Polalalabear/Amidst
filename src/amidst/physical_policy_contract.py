"""Source-bound Phase 1 body behavior, additive to the immutable SI policy schema."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator

from amidst.architectural_scale import ArchitecturalScale, load_architectural_scale
from amidst.physical_authority import PhysicalPolicy
from amidst.physical_units import physical_policy_in_blender_units
from amidst.scene_geometry import (
    Authority,
    Digest,
    GeometryModel,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
)


class PhysicalPolicyRuntime(GeometryModel):
    schema_version: Literal["physical-policy-runtime-v1"] = "physical-policy-runtime-v1"
    source_asset_sha256: Digest
    authority: Literal["APPROVED"]
    approval_id: str = Field(min_length=1)
    policy_config: str = Field(min_length=1)
    architectural_scale_config: str = Field(min_length=1)
    legal_support_contact: Literal["APPROVED_SUPPORT_ONLY"]
    portal_clearance_combination: Literal["MAXIMUM"]
    stair_direction: Literal["BIDIRECTIONAL"]
    navigation_allowed_roles: tuple[Literal["WALKABLE"], Literal["STAIR"]]
    navigation_outside_approved_support: Literal["FORBIDDEN"]
    walkable_representation: Literal["RAW_SUPPORT_SURFACE"]
    footprint_preprocess: Literal["UNION_THEN_EROSION"]

    @model_validator(mode="after")
    def validate_identities(self) -> Self:
        if any(not value.strip() for value in (
            self.approval_id, self.policy_config, self.architectural_scale_config,
        )):
            raise ValueError("physical runtime approval/config identities cannot be blank")
        return self


def _finite(value: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


@dataclass(frozen=True, slots=True)
class PhysicalPolicyContract:
    policy: PhysicalPolicy
    scale: ArchitecturalScale
    runtime: PhysicalPolicyRuntime

    def __post_init__(self) -> None:
        policy = PhysicalPolicy.model_validate(self.policy)
        scale = ArchitecturalScale.model_validate(self.scale)
        runtime = PhysicalPolicyRuntime.model_validate(self.runtime)
        scale.require_source_sha256(runtime.source_asset_sha256)
        if policy.authority != Authority.APPROVED or policy.pending_fields():
            raise ValueError("physical behavior requires a complete APPROVED policy")
        if (
            policy.body_model != "UPRIGHT_CYLINDER"
            or policy.trajectory_reference != "FLOOR_CONTACT_POINT"
            or policy.clearance_comparison != "MINIMUM_INCLUSIVE"
            or policy.collision_comparison != "CONTACT_INCLUSIVE"
        ):
            raise ValueError(
                "physical runtime requires the approved Phase 1 body/contact semantics"
            )
        object.__setattr__(self, "policy", policy)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "runtime", runtime)

    def parameter(self, name: str) -> float:
        if name not in {
            "body_radius_m", "body_height_m", "body_clearance_m",
            "portal_horizontal_clearance_m", "portal_vertical_clearance_m",
            "collision_tolerance_m",
        }:
            raise KeyError(f"unknown physical parameter: {name}")
        value = getattr(self.policy, name)
        if value is None:
            raise ValueError(f"physical parameter is pending: {name}")
        return float(value)

    @property
    def footprint_radius_m(self) -> float:
        return self.parameter("body_radius_m") + self.parameter("body_clearance_m")

    @property
    def footprint_radius_bu(self) -> float:
        return self.scale.to_blender_units(self.footprint_radius_m)

    @property
    def portal_min_width_m(self) -> float:
        margin = max(
            self.parameter("body_clearance_m"), self.parameter("portal_horizontal_clearance_m"),
        )
        return 2 * (self.parameter("body_radius_m") + margin)

    @property
    def portal_min_height_m(self) -> float:
        margin = max(
            self.parameter("body_clearance_m"), self.parameter("portal_vertical_clearance_m"),
        )
        return self.parameter("body_height_m") + margin

    def clearance_pass(self, distance_m: float, required_m: float | None = None) -> bool:
        distance = _finite(distance_m, "measured clearance")
        required = self.parameter("body_clearance_m") if required_m is None else _finite(
            required_m, "required clearance",
        )
        if required < 0:
            raise ValueError("required clearance must be nonnegative")
        # Equality is accepted. Contact tolerance does not relax minimum clearance.
        return distance >= required

    def is_obstacle_contact(self, physical_body_gap_m: float) -> bool:
        return _finite(physical_body_gap_m, "body gap") <= self.parameter("collision_tolerance_m")

    def approved_support_contact_allowed(self, surface: GeometrySurface) -> bool:
        surface = GeometrySurface.model_validate(surface)
        return (
            surface.role in (GeometryRole.WALKABLE, GeometryRole.STAIR)
            and surface.support == GeometrySupport.SURFACE
            and surface.semantic_authority == Authority.APPROVED
            and surface.physical_authority == Authority.APPROVED
        )

    def report(self) -> dict[str, object]:
        values = physical_policy_in_blender_units(
            self.policy, self.scale, source_asset_sha256=self.runtime.source_asset_sha256,
        )
        values.update(
            runtime=self.runtime.model_dump(mode="json"),
            footprint_radius_m=self.footprint_radius_m,
            footprint_radius_bu=self.footprint_radius_bu,
            portal_min_width_m=self.portal_min_width_m,
            portal_min_width_bu=self.scale.to_blender_units(self.portal_min_width_m),
            portal_min_height_m=self.portal_min_height_m,
            portal_min_height_bu=self.scale.to_blender_units(self.portal_min_height_m),
            geometry_authority_upgraded=False,
        )
        return values


def load_physical_policy_contract(runtime_path: Path | str) -> PhysicalPolicyContract:
    runtime = PhysicalPolicyRuntime.model_validate_json(Path(runtime_path).read_bytes())
    policy = PhysicalPolicy.model_validate_json(Path(runtime.policy_config).read_bytes())
    scale = load_architectural_scale(
        runtime.architectural_scale_config, runtime.source_asset_sha256,
    )
    return PhysicalPolicyContract(policy, scale, runtime)
