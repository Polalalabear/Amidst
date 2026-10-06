"""Purpose-specific physical authority, independent of Blender and inference.

This additive sidecar never upgrades a geometry snapshot. A partial approved
collider set can support positive rejection without certifying free space.
"""

import hashlib
import json
from dataclasses import InitVar, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import Field, FiniteFloat, model_validator

from amidst.scene_geometry import (
    Authority,
    Digest,
    FloorAuthority,
    GeometryAuthorityError,
    GeometryModel,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
    PortalGeometry,
    ReadOnlySceneGeometryProvider,
    SceneGeometrySnapshot,
    StairGeometry,
)

Nonnegative = Annotated[FiniteFloat, Field(ge=0)]
Positive = Annotated[FiniteFloat, Field(gt=0)]


class PhysicalAuthorityLevel(StrEnum):
    PROVISIONAL = "PROVISIONAL"
    PARTIAL_APPROVED = "PARTIAL_APPROVED"
    APPROVED = "APPROVED"


class PhysicalPurpose(StrEnum):
    KNOWN_COLLISION_PRUNING = "KNOWN_COLLISION_PRUNING"
    COLLISION_FREE_VALIDATION = "COLLISION_FREE_VALIDATION"
    TOPOLOGY_VALIDATION = "TOPOLOGY_VALIDATION"
    PHYSICAL_VALIDITY_METRICS = "PHYSICAL_VALIDITY_METRICS"


class PhysicalCoverage(StrEnum):
    PARTIAL = "PARTIAL"
    COMPLETE = "COMPLETE"


def _unique(values: tuple[str, ...], description: str) -> None:
    if any(not value.strip() for value in values) or len(set(values)) != len(values):
        raise ValueError(f"{description} must contain unique nonempty identities")


def _approved_evidence(
    authority: Authority,
    approval_id: str | None,
    evidence_ids: tuple[str, ...],
) -> None:
    _unique(evidence_ids, "evidence_ids")
    if authority == Authority.APPROVED and (
        not approval_id or not approval_id.strip() or not evidence_ids
    ):
        raise ValueError("APPROVED authority requires approval_id and evidence_ids")


class PhysicalPolicy(GeometryModel):
    policy_id: str = Field(min_length=1)
    config_version: str = Field(min_length=1)
    units: Literal["metres"] = "metres"
    authority: Authority = Authority.HUMAN_REVIEW
    body_model: Literal["UPRIGHT_CYLINDER", "UPRIGHT_CAPSULE"] | None = None
    trajectory_reference: Literal["FLOOR_CONTACT_POINT"] | None = None
    body_radius_m: Positive | None = None
    body_height_m: Positive | None = None
    body_clearance_m: Nonnegative | None = None
    portal_horizontal_clearance_m: Nonnegative | None = None
    portal_vertical_clearance_m: Nonnegative | None = None
    collision_tolerance_m: Nonnegative | None = None
    clearance_comparison: Literal["MINIMUM_INCLUSIVE", "MINIMUM_EXCLUSIVE"] | None = None
    collision_comparison: Literal["CONTACT_INCLUSIVE", "CONTACT_EXCLUSIVE"] | None = None
    evidence_ids: tuple[str, ...] = ()
    approval_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if not self.policy_id.strip() or not self.config_version.strip():
            raise ValueError("physical policy ID and config version cannot be blank")
        _approved_evidence(self.authority, self.approval_id, self.evidence_ids)
        missing = self.pending_fields()
        if self.authority == Authority.APPROVED and missing:
            raise ValueError(f"APPROVED physical policy has pending fields: {missing}")
        if (
            self.body_model == "UPRIGHT_CAPSULE"
            and self.body_radius_m is not None
            and self.body_height_m is not None
            and self.body_height_m < 2 * self.body_radius_m
        ):
            raise ValueError("capsule body height must include both hemispheres")
        return self

    def pending_fields(self) -> tuple[str, ...]:
        fields = (
            "body_model",
            "trajectory_reference",
            "body_radius_m",
            "body_height_m",
            "body_clearance_m",
            "portal_horizontal_clearance_m",
            "portal_vertical_clearance_m",
            "collision_tolerance_m",
            "clearance_comparison",
            "collision_comparison",
        )
        return tuple(field for field in fields if getattr(self, field) is None)


class PhysicalScope(GeometryModel):
    scope_id: str = Field(min_length=1)
    purpose: PhysicalPurpose
    floor_ids: tuple[str, ...] = Field(min_length=1)
    surface_ids: tuple[str, ...] = ()
    portal_ids: tuple[str, ...] = ()
    stair_ids: tuple[str, ...] = ()
    coverage: PhysicalCoverage
    authority: Authority
    unresolved_reasons: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    approval_id: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        for field in ("floor_ids", "surface_ids", "portal_ids", "stair_ids"):
            _unique(getattr(self, field), field)
        _unique(self.unresolved_reasons, "unresolved_reasons")
        _approved_evidence(self.authority, self.approval_id, self.evidence_ids)
        if self.authority == Authority.APPROVED:
            if self.unresolved_reasons:
                raise ValueError("APPROVED scope cannot retain unresolved reasons")
            if self.purpose != PhysicalPurpose.KNOWN_COLLISION_PRUNING and (
                self.coverage != PhysicalCoverage.COMPLETE
            ):
                raise ValueError(
                    "formal free-space/topology/metrics scope requires COMPLETE coverage"
                )
        return self


class PhysicalAuthorityResolution(GeometryModel):
    schema_version: Literal["physical-authority-v1"] = "physical-authority-v1"
    source_sha256: Digest
    geometry_sha256: Digest
    level: PhysicalAuthorityLevel
    policy: PhysicalPolicy
    scopes: tuple[PhysicalScope, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        _unique(tuple(scope.scope_id for scope in self.scopes), "scope IDs")
        _unique(self.evidence_ids, "evidence_ids")
        return self


def canonical_geometry_sha256(snapshot: SceneGeometrySnapshot) -> str:
    """Digest validated model JSON, independent of whitespace and output directory."""
    validated = SceneGeometrySnapshot.model_validate(snapshot)
    encoded = json.dumps(
        validated.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ApprovedPhysicalInputs:
    """Approved inputs, not a route-validity or collision-free certificate."""

    source_sha256: str
    geometry_sha256: str
    scope: PhysicalScope
    policy: PhysicalPolicy
    floors: tuple[FloorAuthority, ...]
    surfaces: tuple[GeometrySurface, ...]
    portals: tuple[PortalGeometry, ...]
    stairs: tuple[StairGeometry, ...]

    @property
    def colliders(self) -> tuple[GeometrySurface, ...]:
        return tuple(
            surface
            for surface in self.surfaces
            if surface.role
            in (
                GeometryRole.WALL,
                GeometryRole.OBSTACLE,
            )
        )


@dataclass(frozen=True, slots=True)
class ReadOnlyPhysicalAuthorityProvider:
    geometry: SceneGeometrySnapshot
    resolution: PhysicalAuthorityResolution
    expected_source_sha256: InitVar[str]
    expected_geometry_sha256: InitVar[str]

    def __post_init__(
        self,
        expected_source_sha256: str,
        expected_geometry_sha256: str,
    ) -> None:
        geometry = ReadOnlySceneGeometryProvider(self.geometry, expected_source_sha256).snapshot
        resolution = PhysicalAuthorityResolution.model_validate(self.resolution)
        if resolution.source_sha256 != expected_source_sha256:
            raise ValueError("physical authority source SHA-256 does not match caller expectation")
        actual = canonical_geometry_sha256(geometry)
        if actual != expected_geometry_sha256 or resolution.geometry_sha256 != actual:
            raise ValueError(
                "physical authority geometry SHA-256 does not match caller expectation"
            )
        object.__setattr__(self, "geometry", geometry)
        object.__setattr__(self, "resolution", resolution)
        self._validate_references()
        for scope in sorted(resolution.scopes, key=lambda item: item.scope_id):
            if scope.authority == Authority.APPROVED:
                reasons = self._reasons(scope)
                if reasons:
                    raise GeometryAuthorityError(reasons)
        if resolution.level != self._computed_level():
            raise ValueError(
                "physical authority level does not match approved purpose/floor scopes"
            )

    @classmethod
    def from_json(
        cls,
        geometry_path: Path,
        resolution_path: Path,
        *,
        expected_source_sha256: str,
        expected_geometry_sha256: str,
    ) -> Self:
        return cls(
            SceneGeometrySnapshot.model_validate_json(geometry_path.read_text(encoding="utf-8")),
            PhysicalAuthorityResolution.model_validate_json(
                resolution_path.read_text(encoding="utf-8"),
            ),
            expected_source_sha256,
            expected_geometry_sha256,
        )

    def _validate_references(self) -> None:
        floors = {floor.floor_id for floor in self.geometry.floors}
        surfaces = {surface.surface_id: surface for surface in self.geometry.surfaces}
        portals = {portal.portal_id: portal for portal in self.geometry.portals}
        stairs = {stair.stair_id: stair for stair in self.geometry.stairs}
        for scope in self.resolution.scopes:
            if not set(scope.floor_ids) <= floors:
                raise ValueError(f"unknown floor reference in physical scope {scope.scope_id}")
            for identity in scope.surface_ids:
                if (
                    identity not in surfaces
                    or not surfaces[identity].floor_ids
                    or not (set(surfaces[identity].floor_ids) <= set(scope.floor_ids))
                ):
                    raise ValueError(f"unknown or out-of-scope surface reference: {identity}")
            for identity in scope.portal_ids:
                if identity not in portals or portals[identity].floor_id not in scope.floor_ids:
                    raise ValueError(f"unknown or out-of-scope portal reference: {identity}")
            for identity in scope.stair_ids:
                if identity not in stairs or not {
                    stairs[identity].floor_from,
                    stairs[identity].floor_to,
                } <= set(scope.floor_ids):
                    raise ValueError(f"unknown or out-of-scope stair reference: {identity}")

    def get_scopes(
        self,
        *,
        purpose: PhysicalPurpose | None = None,
        floor_id: str | None = None,
    ) -> tuple[PhysicalScope, ...]:
        if floor_id is not None and floor_id not in {
            floor.floor_id for floor in self.geometry.floors
        }:
            raise KeyError(f"unknown floor: {floor_id}")
        return tuple(
            sorted(
                (
                    scope
                    for scope in self.resolution.scopes
                    if (purpose is None or scope.purpose == purpose)
                    and (floor_id is None or floor_id in scope.floor_ids)
                ),
                key=lambda item: item.scope_id,
            )
        )

    def _reasons(self, scope: PhysicalScope) -> tuple[str, ...]:
        reasons: list[str] = []
        if scope.authority != Authority.APPROVED:
            reasons.append(f"SCOPE_NOT_APPROVED:{scope.scope_id}")
        reasons.extend(f"UNRESOLVED:{reason}" for reason in sorted(scope.unresolved_reasons))
        policy = self.resolution.policy
        if policy.authority != Authority.APPROVED:
            reasons.append(f"POLICY_NOT_APPROVED:{policy.policy_id}")
        reasons.extend(f"POLICY_PENDING:{field}" for field in policy.pending_fields())
        if self.geometry.scale_authority != Authority.APPROVED:
            reasons.append("SCALE_NOT_APPROVED")
        for floor in sorted(self.geometry.floors, key=lambda item: item.floor_id):
            if floor.floor_id in scope.floor_ids and floor.authority != Authority.APPROVED:
                reasons.append(f"FLOOR_NOT_APPROVED:{floor.floor_id}")
        selected = {
            surface.surface_id: surface
            for surface in self.geometry.surfaces
            if surface.surface_id in scope.surface_ids
        }
        for surface in sorted(selected.values(), key=lambda item: item.surface_id):
            if surface.role in (GeometryRole.WALKABLE, GeometryRole.WALL, GeometryRole.OBSTACLE):
                if surface.physical_authority != Authority.APPROVED:
                    reasons.append(f"SURFACE_NOT_APPROVED:{surface.surface_id}")
                if surface.semantic_authority != Authority.APPROVED:
                    reasons.append(f"SEMANTIC_SURFACE_NOT_APPROVED:{surface.surface_id}")
                if (
                    surface.role == GeometryRole.OBSTACLE
                    and surface.support != GeometrySupport.VOLUME
                ):
                    reasons.append(f"OBSTACLE_VOLUME_NOT_APPROVED:{surface.surface_id}")
            elif surface.semantic_authority != Authority.APPROVED:
                reasons.append(f"SEMANTIC_SURFACE_NOT_APPROVED:{surface.surface_id}")
        for portal in sorted(self.geometry.portals, key=lambda item: item.portal_id):
            if portal.portal_id in scope.portal_ids and portal.authority != Authority.APPROVED:
                reasons.append(f"PORTAL_NOT_APPROVED:{portal.portal_id}")
        for stair in sorted(self.geometry.stairs, key=lambda item: item.stair_id):
            if stair.stair_id in scope.stair_ids:
                for name in ("connectivity_authority", "opening_authority", "clearance_authority"):
                    if getattr(stair, name) != Authority.APPROVED:
                        reasons.append(f"STAIR_NOT_APPROVED:{stair.stair_id}:{name}")
        if scope.purpose == PhysicalPurpose.KNOWN_COLLISION_PRUNING:
            for floor_id in sorted(scope.floor_ids):
                if not any(
                    floor_id in surface.floor_ids
                    and surface.blocks_movement
                    and surface.role in (GeometryRole.WALL, GeometryRole.OBSTACLE)
                    for surface in selected.values()
                ):
                    reasons.append(f"MOVEMENT_COLLIDER_MISSING:{floor_id}")
        if scope.coverage == PhysicalCoverage.COMPLETE:
            for floor_id in sorted(scope.floor_ids):
                if not any(
                    floor_id in surface.floor_ids
                    and surface.role == GeometryRole.WALKABLE
                    and surface.physical_authority == Authority.APPROVED
                    for surface in selected.values()
                ):
                    reasons.append(f"WALKABLE_SCOPE_NOT_APPROVED:{floor_id}")
            required = {
                surface.surface_id
                for surface in self.geometry.surfaces
                if set(surface.floor_ids) & set(scope.floor_ids)
                and surface.role
                in (
                    GeometryRole.WALKABLE,
                    GeometryRole.WALL,
                    GeometryRole.OBSTACLE,
                )
                and surface.semantic_authority != Authority.REJECTED
            }
            reasons.extend(
                f"SURFACE_SCOPE_OMITTED:{identity}"
                for identity in sorted(
                    required - set(scope.surface_ids),
                )
            )
            reasons.extend(
                f"PORTAL_SCOPE_OMITTED:{portal.portal_id}"
                for portal in sorted(
                    self.geometry.portals,
                    key=lambda item: item.portal_id,
                )
                if portal.floor_id in scope.floor_ids and portal.portal_id not in scope.portal_ids
            )
            reasons.extend(
                f"STAIR_SCOPE_OMITTED:{stair.stair_id}"
                for stair in sorted(
                    self.geometry.stairs,
                    key=lambda item: item.stair_id,
                )
                if {stair.floor_from, stair.floor_to} & set(scope.floor_ids)
                and stair.stair_id not in scope.stair_ids
            )
        elif scope.purpose != PhysicalPurpose.KNOWN_COLLISION_PRUNING:
            reasons.append("COMPLETE_SCOPE_REQUIRED")
        return tuple(reasons)

    def _computed_level(self) -> PhysicalAuthorityLevel:
        approved = tuple(
            scope for scope in self.resolution.scopes if scope.authority == Authority.APPROVED
        )
        if not approved:
            return PhysicalAuthorityLevel.PROVISIONAL
        if (
            self.geometry.floors
            and self.geometry.physical_complete
            and len(approved) == len(self.resolution.scopes)
            and all(
                any(
                    scope.purpose == purpose
                    and floor.floor_id in scope.floor_ids
                    and scope.coverage == PhysicalCoverage.COMPLETE
                    for scope in approved
                )
                for floor in self.geometry.floors
                for purpose in PhysicalPurpose
            )
        ):
            return PhysicalAuthorityLevel.APPROVED
        return PhysicalAuthorityLevel.PARTIAL_APPROVED

    def require_scope(
        self,
        scope_id: str,
        *,
        purpose: PhysicalPurpose,
    ) -> ApprovedPhysicalInputs:
        if not isinstance(purpose, PhysicalPurpose):
            raise TypeError("formal consumption requires an explicit PhysicalPurpose")
        scope = next(
            (scope for scope in self.resolution.scopes if scope.scope_id == scope_id), None
        )
        if scope is None:
            raise GeometryAuthorityError((f"PHYSICAL_SCOPE_MISSING:{scope_id}",))
        if scope.purpose != purpose:
            raise GeometryAuthorityError((f"PHYSICAL_PURPOSE_MISMATCH:{scope_id}",))
        reasons = self._reasons(scope)
        if reasons:
            raise GeometryAuthorityError(reasons)
        return ApprovedPhysicalInputs(
            self.geometry.source_sha256,
            self.resolution.geometry_sha256,
            scope,
            self.resolution.policy,
            tuple(
                sorted(
                    (floor for floor in self.geometry.floors if floor.floor_id in scope.floor_ids),
                    key=lambda item: item.floor_id,
                )
            ),
            tuple(
                sorted(
                    (
                        surface
                        for surface in self.geometry.surfaces
                        if surface.surface_id in scope.surface_ids
                    ),
                    key=lambda item: item.surface_id,
                )
            ),
            tuple(
                sorted(
                    (
                        portal
                        for portal in self.geometry.portals
                        if portal.portal_id in scope.portal_ids
                    ),
                    key=lambda item: item.portal_id,
                )
            ),
            tuple(
                sorted(
                    (stair for stair in self.geometry.stairs if stair.stair_id in scope.stair_ids),
                    key=lambda item: item.stair_id,
                )
            ),
        )
