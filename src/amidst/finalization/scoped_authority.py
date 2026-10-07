"""Explicit new local semantics followed by original numerical cell proofs.

Proposals and numerical previews grant no authority. A new, independently pinned
human receipt is required before support permission or bounded surface semantics
are materialized. The approved consumer retains every cell certificate and checks
continuous coverage of their union, including holes. No original office receipt,
bounding box, object name, or simulation trajectory expands this authority.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from itertools import pairwise
from typing import Any, Literal

from pydantic import Field, FiniteFloat, model_validator
from shapely import normalize, union_all
from shapely.geometry import box

from amidst.domain.camera import Camera
from amidst.finalization.scoped_semantic_cells import (
    MultiReviewedLocalScopeCertificate,
    MultiReviewedRestrictedPhysicalProvider,
    MultiSourceSurfaceReview,
    regenerate_multi_reviewed_certificate,
)
from amidst.local_physical_scopes import (
    LocalScopeCertificate,
    RestrictedLocalPhysicalProvider,
    certify_local_rectangle,
    local_domain_content_sha256,
)
from amidst.local_semantic_review import (
    ReviewedLocalScopeCertificate,
    ReviewedRestrictedLocalPhysicalProvider,
    ScopedSourceSurfaceReview,
    regenerate_reviewed_certificate,
)
from amidst.obstacle_volume_authority import content_sha256, validate_source_evidence
from amidst.physical_collision import CollisionNumerics
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.scene_geometry import (
    Authority,
    Coordinate,
    Digest,
    FloorAuthority,
    GeometryAuthorityError,
    GeometryModel,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
)
from amidst.walkable_clearance import WalkableClearanceDomain


def contract_content_sha256(contract: PhysicalPolicyContract) -> str:
    return content_sha256({
        "policy": contract.policy.model_dump(mode="json"),
        "scale": contract.scale.model_dump(mode="json"),
        "runtime": contract.runtime.model_dump(mode="json"),
    })


class ScopeAuthorityPins(GeometryModel):
    """Caller-supplied original approvals; never chosen from a new proposal."""

    source_sha256: Digest
    evidence_content_sha256: Digest
    physical_contract_content_sha256: Digest
    numerics_content_sha256: Digest
    original_human_decisions_sha256: Digest
    protocol_sha256: Digest
    floor_content_sha256: Digest
    camera_export_content_sha256: Digest | None = None


class SourceFaceBinding(GeometryModel):
    """Default guard/union ownership, with a separately explicit surface-bound extension.

    A new direct-human approval of the entire proposal may extend movement
    ownership to the named source faces inside the optional explicit bound.
    This never extends path permission, grants solid interior or approves an object.
    """
    binding_id: str = Field(min_length=1)
    source_object_id: str = Field(min_length=1)
    source_mesh_id: Digest
    source_geometry_sha256: Digest
    source_component_id: str = Field(min_length=1)
    source_face_indices: tuple[int, ...] = Field(min_length=1)
    source_triangle_indices: tuple[int, ...] = Field(min_length=1)
    exact_triangles_content_sha256: Digest
    proposed_role: Literal["WALKABLE_SUPPORT_SURFACE", "MOVEMENT_OBSTACLE_SURFACE"]
    role_application: Literal["PROPOSED_BODY_GUARDS_AND_UNION_ONLY"] = (
        "PROPOSED_BODY_GUARDS_AND_UNION_ONLY"
    )
    source_face_movement_obstacle_bounds_bu: tuple[Coordinate, Coordinate] | None = Field(
        default=None, description=(
            "Additional explicit SOURCE_FACE_MOVEMENT_OBSTACLE ownership scope for named facets. "
            "Requires new exact-proposal human approval; extends the default guard/union role "
            "only within this bound, without whole-object, solid-interior or path authority."
        ),
    )
    whole_object_approved: Literal[False] = False
    solid_interior_approved: Literal[False] = False

    @model_validator(mode="after")
    def validate_indices(self) -> SourceFaceBinding:
        for values in (self.source_face_indices, self.source_triangle_indices):
            if len(set(values)) != len(values) or any(v < 0 for v in values):
                raise ValueError("source face/triangle bindings must be unique nonnegative IDs")
        bounds = self.source_face_movement_obstacle_bounds_bu
        if bounds is not None:
            if self.proposed_role != "MOVEMENT_OBSTACLE_SURFACE":
                raise ValueError(
                    "explicit movement-obstacle ownership cannot approve floor support",
                )
            low, high = bounds
            if any(low[a] > high[a] for a in range(3)) or sum(
                low[a] < high[a] for a in range(3)
            ) < 2:
                raise ValueError("source surface ownership bounds need ordered extent in two axes")
        return self


class BoundedSurfaceSemantics(GeometryModel):
    """Proposed ownership, without an APPROVE literal or human receipt."""

    source_object_id: str = Field(min_length=1)
    source_mesh_id: Digest
    source_geometry_sha256: Digest
    source_component_id: str = Field(min_length=1)
    zero_area_source_face_indices: tuple[int, ...]
    component_interior: Literal["SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND"]
    zero_area_face_ownership: Literal["DEGENERATE_SEAM_NO_OCCUPIED_VOLUME_IN_BOUND"]
    whole_component_approved: Literal[False] = False


class ScopeCellProposal(GeometryModel):
    cell_id: str = Field(min_length=1)
    rectangle_xy_bu: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
    body_region_id: str = Field(min_length=1)
    proposed_body_guard_bounds_bu: tuple[Coordinate, Coordinate]
    surface_semantics: BoundedSurfaceSemantics | None = None
    extra_surface_semantics: tuple[BoundedSurfaceSemantics, ...] = ()

    @property
    def all_surface_semantics(self) -> tuple[BoundedSurfaceSemantics, ...]:
        return (() if self.surface_semantics is None else (self.surface_semantics,)) + (
            self.extra_surface_semantics
        )

    @model_validator(mode="after")
    def validate_bounds(self) -> ScopeCellProposal:
        xmin, ymin, xmax, ymax = self.rectangle_xy_bu
        low, high = self.proposed_body_guard_bounds_bu
        if xmin >= xmax or ymin >= ymax or any(low[a] >= high[a] for a in range(3)):
            raise ValueError("cell/guard must have finite positive extent")
        profiles = self.all_surface_semantics
        if len({(p.source_mesh_id, p.source_component_id) for p in profiles}) != len(profiles):
            raise ValueError("cell bounded semantic components must be unique")
        return self


class ScopeCameraLandmarkBinding(GeometryModel):
    """Exact source calibration and separately requested local landmark semantics."""

    camera: Camera
    calibration_content_sha256: Digest
    source_camera_export_content_sha256: Digest
    floor_id: str = Field(min_length=1)
    landmark_offset_bu: Coordinate
    projection_plane_point_bu: Coordinate
    projection_plane_normal: Coordinate = (0.0, 0.0, 1.0)
    calibration_units: Literal["BLENDER_UNITS"] = "BLENDER_UNITS"

    @model_validator(mode="after")
    def validate_camera(self) -> ScopeCameraLandmarkBinding:
        if content_sha256(self.camera.model_dump(mode="json")) != self.calibration_content_sha256:
            raise ValueError("camera calibration hash differs from its exact values")
        if self.camera.floor_id != self.floor_id or self.landmark_offset_bu[:2] != (0., 0.):
            raise ValueError("local camera floor and same-XY vertical landmark must be explicit")
        if self.projection_plane_normal != (0., 0., 1.):
            raise ValueError("new scoped projection requires the source-bound horizontal plane")
        return self


class ScopeProposal(GeometryModel):
    schema_version: Literal["phase1-new-local-scope-proposal-v1"] = (
        "phase1-new-local-scope-proposal-v1"
    )
    scope_id: str = Field(min_length=1)
    authority: Literal["HUMAN_REVIEW"] = "HUMAN_REVIEW"
    pins: ScopeAuthorityPins
    discovery_content_sha256: Digest | None = None
    floor: FloorAuthority
    support_bindings: tuple[SourceFaceBinding, ...] = Field(min_length=1)
    obstacle_bindings: tuple[SourceFaceBinding, ...] = ()
    cells: tuple[ScopeCellProposal, ...] = Field(min_length=1)
    camera_landmark_bindings: tuple[ScopeCameraLandmarkBinding, ...] = ()
    requested_projection_authority: bool = False
    maximum_enclosure_pair_checks: int = Field(default=250000, gt=0)
    self_intersection_numeric_epsilon_bu: FiniteFloat = Field(default=1e-9, ge=0)
    original_source_geometry_modified: Literal[False] = False
    original_approvals_modified: Literal[False] = False
    gt_used: Literal[False] = False
    formal_execution_enabled: Literal[False] = False

    @model_validator(mode="after")
    def validate_proposal(self) -> ScopeProposal:
        if self.floor.authority != Authority.APPROVED or self.floor.normal != (0., 0., 1.):
            raise ValueError("new local support reuses an explicitly approved horizontal floor")
        if any(b.proposed_role != "WALKABLE_SUPPORT_SURFACE" for b in self.support_bindings):
            raise ValueError("support permission requires exact proposed support surface bindings")
        if any(b.proposed_role != "MOVEMENT_OBSTACLE_SURFACE" for b in self.obstacle_bindings):
            raise ValueError("obstacle ownership must be explicitly proposed as a source surface")
        identities = [b.binding_id for b in (*self.support_bindings, *self.obstacle_bindings)]
        if len(set(identities)) != len(identities) or len({c.cell_id for c in self.cells}) != len(
            self.cells
        ):
            raise ValueError("scope binding and cell identities must be unique")
        cameras = self.camera_landmark_bindings
        if self.requested_projection_authority != bool(cameras):
            raise ValueError("projection authority requires exact camera-landmark bindings")
        if len({b.camera.camera_id for b in cameras}) != len(cameras):
            raise ValueError("scope cameras must be unique")
        if any(
            b.floor_id != self.floor.floor_id
            or b.projection_plane_point_bu[2] != self.floor.point[2] + b.landmark_offset_bu[2]
            for b in cameras
        ):
            raise ValueError("projection plane must equal approved support height plus landmark Z")
        return self


class ScopeHumanDecision(GeometryModel):
    schema_version: Literal["phase1-new-local-scope-human-decision-v1"] = (
        "phase1-new-local-scope-human-decision-v1"
    )
    proposal_content_sha256: Digest
    decision: Literal["PENDING", "APPROVE", "REJECT", "KEEP_REVIEW", "FIX_GEOMETRY"]
    approval_origin: Literal["DIRECT_HUMAN_DECISION"]
    reviewer_id: str = Field(min_length=1)
    human_approval_id: str = Field(min_length=1)
    decision_timestamp: datetime
    direct_human_decision_text: str = Field(min_length=1)
    approval_scope: Literal["EXACT_PROPOSAL_ONLY"] = "EXACT_PROPOSAL_ONLY"
    original_approvals_superseded: Literal[False] = False

    @model_validator(mode="after")
    def validate_decision(self) -> ScopeHumanDecision:
        if self.decision_timestamp.tzinfo is None:
            raise ValueError("human decision must contain an explicit timezone")
        if any(not v.strip() for v in (
            self.reviewer_id, self.human_approval_id, self.direct_human_decision_text,
        )):
            raise ValueError("human decision identity and original text cannot be blank")
        return self


CellCertificate = (
    LocalScopeCertificate | ReviewedLocalScopeCertificate | MultiReviewedLocalScopeCertificate
)
CellProvider = (
    RestrictedLocalPhysicalProvider | ReviewedRestrictedLocalPhysicalProvider
    | MultiReviewedRestrictedPhysicalProvider
)


class ScopeUnionCertificate(GeometryModel):
    schema_version: Literal["phase1-approved-local-cell-union-v1"] = (
        "phase1-approved-local-cell-union-v1"
    )
    scope_id: str
    source_sha256: Digest
    proposal_content_sha256: Digest
    human_decision_content_sha256: Digest
    pins: ScopeAuthorityPins
    domain_content_sha256: Digest
    union_wkb_hex: str = Field(min_length=1)
    union_wkb_sha256: Digest
    cells: tuple[CellCertificate, ...] = Field(min_length=1)
    cell_content_sha256: tuple[Digest, ...] = Field(min_length=1)
    local_physical_authority: Literal["APPROVED"] = "APPROVED"
    topology_requires_separate_case_readiness: Literal[True] = True
    projection_requires_separate_fresh_observations: Literal[True] = True
    overall_formal_case_execution_enabled: Literal[False] = False
    outside_union: Literal["REFUSE_VALIDATION"] = "REFUSE_VALIDATION"
    original_approvals_modified: Literal[False] = False


def _physical(certificate: CellCertificate) -> LocalScopeCertificate:
    return certificate.physical_certificate if isinstance(
        certificate, (ReviewedLocalScopeCertificate, MultiReviewedLocalScopeCertificate),
    ) else certificate


def _exact_binding(
    binding: SourceFaceBinding, evidence: Mapping[str, Any],
) -> tuple[Mapping[str, Any], tuple[tuple[Coordinate, Coordinate, Coordinate], ...]]:
    meshes = [m for m in evidence["meshes"] if m["mesh_id"] == binding.source_mesh_id]
    if len(meshes) != 1:
        raise ValueError("bound source mesh must exist exactly once")
    mesh = meshes[0]
    if mesh["source_object_id"] != binding.source_object_id or (
        mesh["geometry_sha256"] != binding.source_geometry_sha256
    ):
        raise ValueError("source object/geometry binding differs")
    parts = [p for p in mesh["components"] if p["component_id"] == binding.source_component_id]
    if len(parts) != 1:
        raise ValueError("bound source component must exist exactly once")
    selected = set(binding.source_triangle_indices)
    actual = {
        i for i, face in enumerate(mesh["triangle_source_face_indices"])
        if face in binding.source_face_indices
    }
    if selected != actual or not selected.issubset(parts[0]["source_triangle_indices"]):
        raise ValueError("binding must retain every triangle of each exact source face/component")
    if set(binding.source_face_indices) != {
        mesh["triangle_source_face_indices"][i] for i in selected
    }:
        raise ValueError("bound source face does not exist")
    triangles = tuple(
        tuple(tuple(float(v) for v in mesh["vertices"][j]) for j in mesh["triangles"][i])
        for i in binding.source_triangle_indices
    )
    if content_sha256(triangles) != binding.exact_triangles_content_sha256:
        raise ValueError("actual source face coordinates hash differs")
    return mesh, triangles  # type: ignore[return-value]


def build_source_face_binding(
    evidence: Mapping[str, Any], *, binding_id: str, source_mesh_id: str,
    source_component_id: str, source_face_indices: tuple[int, ...],
    proposed_role: Literal["WALKABLE_SUPPORT_SURFACE", "MOVEMENT_OBSTACLE_SURFACE"],
    source_face_movement_obstacle_bounds_bu: tuple[Coordinate, Coordinate] | None = None,
) -> SourceFaceBinding:
    """Copy exact source provenance into a HUMAN_REVIEW proposal; grant no role."""
    mesh = next(m for m in evidence["meshes"] if m["mesh_id"] == source_mesh_id)
    indices = tuple(
        i for i, face in enumerate(mesh["triangle_source_face_indices"])
        if face in source_face_indices
    )
    triangles = [
        [mesh["vertices"][j] for j in mesh["triangles"][i]] for i in indices
    ]
    binding = SourceFaceBinding(
        binding_id=binding_id, source_object_id=mesh["source_object_id"],
        source_mesh_id=source_mesh_id, source_geometry_sha256=mesh["geometry_sha256"],
        source_component_id=source_component_id, source_face_indices=source_face_indices,
        source_triangle_indices=indices, exact_triangles_content_sha256=content_sha256(triangles),
        proposed_role=proposed_role,
        source_face_movement_obstacle_bounds_bu=source_face_movement_obstacle_bounds_bu,
    )
    _exact_binding(binding, evidence)
    return binding


def _triangle_intersects_semantic_bound(
    triangle: tuple[Coordinate, Coordinate, Coordinate], bounds: tuple[Coordinate, Coordinate],
) -> bool:
    """Exact clipping of source facets; the bound is never collider geometry."""
    polygon = [tuple(Fraction.from_float(float(v)) for v in point) for point in triangle]
    low, high = bounds
    for axis in range(3):
        for boundary, keep_greater in ((low[axis], True), (high[axis], False)):
            if not polygon:
                return False
            q_boundary = Fraction.from_float(float(boundary))
            clipped = []
            previous = polygon[-1]
            previous_inside = previous[axis] >= q_boundary if keep_greater else (
                previous[axis] <= q_boundary
            )
            for current in polygon:
                inside = current[axis] >= q_boundary if keep_greater else (
                    current[axis] <= q_boundary
                )
                if inside != previous_inside:
                    fraction = (q_boundary - previous[axis]) / (current[axis] - previous[axis])
                    clipped.append(tuple(previous[a] + fraction * (current[a] - previous[a])
                                         for a in range(3)))
                if inside:
                    clipped.append(current)
                previous, previous_inside = current, inside
            polygon = clipped
    return bool(polygon)


def _validate_obstacle_semantic_bound(
    binding: SourceFaceBinding, triangles: tuple[tuple[Coordinate, Coordinate, Coordinate], ...],
    proposal: ScopeProposal, evidence: Mapping[str, Any],
) -> None:
    bounds = binding.source_face_movement_obstacle_bounds_bu
    if bounds is None:
        return
    low, high = bounds
    permitted_regions = {cell.body_region_id for cell in proposal.cells}
    if not any(
        region["region_id"] in permitted_regions and region["kind"] == "FULL_BODY_CONTEXT"
        and region["selection_complete"] is True and region["floor_id"] == proposal.floor.floor_id
        and all(region["bounds_bu"]["minimum"][a] <= low[a] <= high[a]
                <= region["bounds_bu"]["maximum"][a] for a in range(3))
        and any(selection["mesh_id"] == binding.source_mesh_id
                and binding.source_component_id in selection["component_ids"]
                for selection in region["selections"])
        for region in evidence["regions"]
    ):
        raise ValueError(
            "obstacle semantic bound exceeds selected complete same-floor source atlas",
        )
    if not any(_triangle_intersects_semantic_bound(triangle, bounds) for triangle in triangles):
        raise ValueError("obstacle semantic bound contains no actual bound source-face geometry")


def validate_scope_proposal(
    proposal: ScopeProposal, evidence: Mapping[str, Any], contract: PhysicalPolicyContract,
    numerics: CollisionNumerics, *, expected_pins: ScopeAuthorityPins,
    camera_export: Mapping[str, Any] | None = None,
) -> ScopeProposal:
    """Read-only validation cannot turn raw support or proposed semantics APPROVED."""
    proposal = ScopeProposal.model_validate_json(proposal.model_dump_json())
    if proposal.pins != expected_pins:
        raise ValueError("new scope differs from independently pinned original inputs")
    if content_sha256(proposal.floor.model_dump(mode="json")) != expected_pins.floor_content_sha256:
        raise ValueError("new scope floor differs from independently pinned original floor")
    validate_source_evidence(evidence, expected_source_sha256=expected_pins.source_sha256)
    if content_sha256(evidence) != expected_pins.evidence_content_sha256 or (
        contract_content_sha256(contract) != expected_pins.physical_contract_content_sha256
    ) or content_sha256(numerics.model_dump(mode="json")) != expected_pins.numerics_content_sha256:
        raise ValueError("new scope evidence/physical policy/numerics SHA-256 mismatch")
    contract.scale.require_source_sha256(expected_pins.source_sha256)
    for binding in (*proposal.support_bindings, *proposal.obstacle_bindings):
        _mesh, triangles = _exact_binding(binding, evidence)
        _validate_obstacle_semantic_bound(binding, triangles, proposal, evidence)
    for cell in proposal.cells:
        regions = [r for r in evidence["regions"] if r["region_id"] == cell.body_region_id]
        if len(regions) != 1 or regions[0]["kind"] != "FULL_BODY_CONTEXT" or (
            not regions[0]["selection_complete"]
            or regions[0]["floor_id"] != proposal.floor.floor_id
        ):
            raise ValueError("new scope requires original complete same-floor body atlas region")
        low, high = cell.proposed_body_guard_bounds_bu
        bounds = regions[0]["bounds_bu"]
        if any(low[a] < bounds["minimum"][a] or high[a] > bounds["maximum"][a] for a in range(3)):
            raise ValueError("proposed bodyguard exceeds original complete source atlas")
        for semantics in cell.all_surface_semantics:
            _validate_proposed_surface_semantics(semantics, evidence, regions[0])
    if proposal.requested_projection_authority:
        if camera_export is None or (
            camera_export.get("source_sha256") != expected_pins.source_sha256
        ):
            raise ValueError("projection approval requires original source camera export")
        if expected_pins.camera_export_content_sha256 is None or content_sha256(camera_export) != (
            expected_pins.camera_export_content_sha256
        ):
            raise ValueError(
                "scope camera export differs from independently pinned source calibration",
            )
        for camera_binding in proposal.camera_landmark_bindings:
            if content_sha256(camera_export) != camera_binding.source_camera_export_content_sha256:
                raise ValueError("camera export content SHA-256 mismatch")
            actual_cameras = camera_export.get("cameras", [])
            actual = [Camera.model_validate_json(json.dumps(c)) for c in actual_cameras
                      if c.get("camera_id") == camera_binding.camera.camera_id]
            if actual != [camera_binding.camera]:
                raise ValueError("scope camera must equal actual original source calibration")
    return proposal


def _validate_proposed_surface_semantics(
    semantics: BoundedSurfaceSemantics, evidence: Mapping[str, Any], region: Mapping[str, Any],
) -> None:
    meshes = [m for m in evidence["meshes"] if m["mesh_id"] == semantics.source_mesh_id]
    if len(meshes) != 1 or meshes[0]["source_object_id"] != semantics.source_object_id or (
        meshes[0]["geometry_sha256"] != semantics.source_geometry_sha256
    ):
        raise ValueError("proposed surface semantics require exact source object/geometry")
    mesh = meshes[0]
    parts = [p for p in mesh["components"]
             if p["component_id"] == semantics.source_component_id]
    if len(parts) != 1 or not any(
        s["mesh_id"] == semantics.source_mesh_id
        and semantics.source_component_id in s["component_ids"] for s in region["selections"]
    ):
        raise ValueError("proposed surface component must be selected by complete source region")
    faces = semantics.zero_area_source_face_indices
    if len(set(faces)) != len(faces) or any(v < 0 for v in faces):
        raise ValueError("proposed exact zero-area seams must be unique nonnegative faces")
    for face in faces:
        indices = [i for i, f in enumerate(mesh["triangle_source_face_indices"]) if f == face]
        if not indices or any(i not in parts[0]["source_triangle_indices"] for i in indices):
            raise ValueError("proposed zero-area seam is absent from exact source component")
        for index in indices:
            a, b, c = [mesh["vertices"][i] for i in mesh["triangles"][index]]
            ab, ac = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            cross = (ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2],
                     ab[0] * ac[1] - ab[1] * ac[0])
            if any(v != 0 for v in cross):
                raise ValueError("proposed surface semantics cannot waive nondegenerate triangles")


def _domain_after_approval(
    proposal: ScopeProposal, evidence: Mapping[str, Any], contract: PhysicalPolicyContract,
    decision: ScopeHumanDecision,
) -> WalkableClearanceDomain:
    if decision.decision != "APPROVE":
        raise ValueError("raw support permission requires a new explicit human APPROVE")
    decision_hash = content_sha256(decision.model_dump(mode="json"))
    return _support_domain_for_calculation(
        proposal, evidence, contract, approval_id=decision.human_approval_id,
        permission_evidence=f"NEW_SCOPE_HUMAN_RECEIPT_SHA256:{decision_hash}",
    )


def _support_domain_for_calculation(
    proposal: ScopeProposal, evidence: Mapping[str, Any], contract: PhysicalPolicyContract, *,
    approval_id: str, permission_evidence: str,
) -> WalkableClearanceDomain:
    """Core numerical input, private to approved application or labelled preview."""
    surfaces = []
    for binding in proposal.support_bindings:
        _, triangles = _exact_binding(binding, evidence)
        points = tuple(point for triangle in triangles for point in triangle)
        surfaces.append(GeometrySurface(
            surface_id=f"{proposal.scope_id}:support:{binding.binding_id}",
            source_object_id=binding.source_object_id,
            source_face_indices=binding.source_face_indices, role=GeometryRole.WALKABLE,
            floor_ids=(proposal.floor.floor_id,), vertices=points,
            triangles=tuple((i, i + 1, i + 2) for i in range(0, len(points), 3)),
            semantic_authority=Authority.APPROVED, physical_authority=Authority.APPROVED,
            support=GeometrySupport.SURFACE, approval_id=approval_id,
            evidence_ids=(f"SOURCE_SHA256:{proposal.pins.source_sha256}",
                          permission_evidence),
        ))
    return WalkableClearanceDomain.from_surfaces(
        tuple(surfaces), floor=proposal.floor, scale=contract.scale, policy=contract.policy,
        expected_source_sha256=proposal.pins.source_sha256,
    )


def _certify_cells(
    proposal: ScopeProposal, evidence: Mapping[str, Any], contract: PhysicalPolicyContract,
    numerics: CollisionNumerics, decision: ScopeHumanDecision,
) -> tuple[WalkableClearanceDomain, tuple[CellCertificate, ...], list[dict[str, Any]]]:
    domain = _domain_after_approval(proposal, evidence, contract, decision)
    support = frozenset(
        (b.source_object_id, face)
        for b in proposal.support_bindings for face in b.source_face_indices
    )
    certificates: list[CellCertificate] = []
    checks = []
    decision_hash = content_sha256(decision.model_dump(mode="json"))
    for cell in proposal.cells:
        rectangle = box(*cell.rectangle_xy_bu)
        guard_failure = _proposed_guard_failure(cell, domain, contract)
        if guard_failure is not None:
            checks.append({"cell_id": cell.cell_id, "status": "REVIEW",
                           "reason": guard_failure})
            continue
        low, high = cell.proposed_body_guard_bounds_bu
        certificate: CellCertificate | None
        profiles = cell.all_surface_semantics
        if not profiles:
            certificate, detail = certify_local_rectangle(
                domain, rectangle, evidence, cell.body_region_id, contract, numerics,
                support_source_faces=support,
                evidence_content_sha256=proposal.pins.evidence_content_sha256,
                maximum_enclosure_pair_checks=proposal.maximum_enclosure_pair_checks,
                self_intersection_numeric_epsilon_bu=proposal.self_intersection_numeric_epsilon_bu,
            )
        else:
            common = {
                "decision": "APPROVE", "decision_option": "LOCAL_SOURCE_SURFACE_ONLY",
                "human_approval_id": decision.human_approval_id,
                "human_decisions_sha256": decision_hash,
                "source_sha256": proposal.pins.source_sha256,
                "evidence_content_sha256": proposal.pins.evidence_content_sha256,
                "region_id": cell.body_region_id, "body_envelope_bounds_bu": (low, high),
            }
            if len(profiles) == 1 and profiles[0].zero_area_source_face_indices:
                receipt = ScopedSourceSurfaceReview.model_validate({
                    **profiles[0].model_dump(mode="python"), **common,
                    "decision_id": f"{proposal.scope_id}:{cell.cell_id}",
                })
                certificate, detail = regenerate_reviewed_certificate(
                    receipt, evidence, domain, rectangle,
                    cell.body_region_id, contract, numerics,
                    support_source_faces=support,
                    expected_receipt_content_sha256=content_sha256(
                        receipt.model_dump(mode="json"),
                    ), expected_human_decisions_sha256=decision_hash,
                    expected_evidence_content_sha256=proposal.pins.evidence_content_sha256,
                    maximum_enclosure_pair_checks=proposal.maximum_enclosure_pair_checks,
                    self_intersection_numeric_epsilon_bu=proposal.self_intersection_numeric_epsilon_bu,
                )
            else:
                receipts = tuple(MultiSourceSurfaceReview.model_validate({
                    **semantic.model_dump(mode="python"), **common,
                    "decision_id": f"{proposal.scope_id}:{cell.cell_id}:profile-{index}",
                }) for index, semantic in enumerate(profiles))
                certificate, detail = regenerate_multi_reviewed_certificate(
                    receipts, evidence, domain, rectangle, cell.body_region_id, contract, numerics,
                    support_source_faces=support,
                    expected_receipt_content_sha256=tuple(content_sha256(r.model_dump(mode="json"))
                                                         for r in receipts),
                    expected_human_decisions_sha256=decision_hash,
                    expected_evidence_content_sha256=proposal.pins.evidence_content_sha256,
                    maximum_enclosure_pair_checks=proposal.maximum_enclosure_pair_checks,
                    self_intersection_numeric_epsilon_bu=proposal.self_intersection_numeric_epsilon_bu,
                )
        checks.append({"cell_id": cell.cell_id, **{k: v for k, v in detail.items()
                                                  if k != "certificate"}})
        if certificate is not None:
            certificates.append(certificate)
    return domain, tuple(certificates), checks


def _proposed_guard_failure(
    cell: ScopeCellProposal, domain: WalkableClearanceDomain, contract: PhysicalPolicyContract,
) -> str | None:
    band = domain.actual_contact_height_band(box(*cell.rectangle_xy_bu))
    if band is None:
        return "NO_COMMON_ACTUAL_SOURCE_CONTACT_HEIGHT"
    guard = contract.footprint_radius_bu
    extra = contract.scale.to_blender_units(contract.parameter("body_clearance_m"))
    xmin, ymin, xmax, ymax = cell.rectangle_xy_bu
    needed_low = (xmin - guard, ymin - guard, band[0] - extra)
    needed_high = (xmax + guard, ymax + guard, band[1] + contract.scale.to_blender_units(
        contract.parameter("body_height_m") + contract.parameter("body_clearance_m"),
    ))
    low, high = cell.proposed_body_guard_bounds_bu
    return "PROPOSED_GUARD_DOES_NOT_COVER_EXACT_BODY_ENVELOPE" if any(
        low[a] > needed_low[a] or high[a] < needed_high[a] for a in range(3)
    ) else None


def apply_scope_approval(
    proposal: ScopeProposal, decision: ScopeHumanDecision, evidence: Mapping[str, Any],
    contract: PhysicalPolicyContract, numerics: CollisionNumerics, *,
    expected_pins: ScopeAuthorityPins, expected_proposal_content_sha256: str,
    expected_decision_content_sha256: str, camera_export: Mapping[str, Any] | None = None,
) -> tuple[ScopeUnionCertificate | None, dict[str, Any]]:
    """A human APPROVE is necessary, and does not imply a numerical PASS."""
    decision = ScopeHumanDecision.model_validate_json(decision.model_dump_json())
    proposal_hash = content_sha256(proposal.model_dump(mode="json"))
    decision_hash = content_sha256(decision.model_dump(mode="json"))
    if decision_hash != expected_decision_content_sha256 or (
        proposal_hash != expected_proposal_content_sha256
        or decision.proposal_content_sha256 != proposal_hash
    ):
        raise ValueError("independently pinned new proposal/human receipt SHA-256 mismatch")
    # Before source loading, numerical computation, or approved support construction.
    if decision.decision != "APPROVE":
        return None, {"status": "BLOCKED_NEW_HUMAN_APPROVAL_REQUIRED",
                      "decision": decision.decision, "formal_execution_enabled": False}
    checked = validate_scope_proposal(
        proposal, evidence, contract, numerics, expected_pins=expected_pins,
        camera_export=camera_export,
    )
    domain, certificates, checks = _certify_cells(checked, evidence, contract, numerics, decision)
    result: dict[str, Any] = {
        "schema_version": "phase1-new-local-scope-application-result-v1",
        "scope_id": checked.scope_id, "proposal_content_sha256": proposal_hash,
        "human_decision_content_sha256": decision_hash, "cell_checks": checks,
        "formal_execution_enabled": False, "original_approvals_modified": False,
    }
    if len(certificates) != len(checked.cells):
        return None, {**result, "status": "BLOCKED_NUMERICAL_CERTIFICATION"}
    union = normalize(union_all([box(*cell.rectangle_xy_bu) for cell in checked.cells]))
    certificate = ScopeUnionCertificate(
        scope_id=checked.scope_id, source_sha256=checked.pins.source_sha256,
        proposal_content_sha256=proposal_hash, human_decision_content_sha256=decision_hash,
        pins=checked.pins, domain_content_sha256=local_domain_content_sha256(domain),
        union_wkb_hex=union.wkb_hex, union_wkb_sha256=hashlib.sha256(union.wkb).hexdigest(),
        cells=certificates,
        cell_content_sha256=tuple(content_sha256(c.model_dump(mode="json")) for c in certificates),
    )
    return certificate, {**result, "status": "APPROVED_LOCAL_PHYSICAL_UNION",
                         "certificate_content_sha256": content_sha256(
                             certificate.model_dump(mode="json"),
                         ), "case_readiness": "NOT_RUN"}


def proposal_from_source_discovery(
    discovery: Mapping[str, Any], evidence: Mapping[str, Any], *, scope_id: str,
    pins: ScopeAuthorityPins, floor: FloorAuthority,
    proposed_surface_semantics: BoundedSurfaceSemantics | Mapping[
        str, BoundedSurfaceSemantics | tuple[BoundedSurfaceSemantics, ...] | None,
    ],
    camera_landmark_bindings: tuple[ScopeCameraLandmarkBinding, ...] = (),
) -> ScopeProposal:
    """Carry the actual source discovery into a separate pending review packet.

    The caller explicitly proposes bounded surface ownership. Discovery names,
    bounds, successful numerical checks and camera FOV do not approve that role.
    """
    if discovery.get("source_sha256") != pins.source_sha256 or discovery.get(
        "source_evidence_content_sha256",
    ) != pins.evidence_content_sha256 or discovery.get("authority_applied") is not False:
        raise ValueError("new scope discovery must retain original source and no authority applied")
    support = discovery["support_source_faces"]
    support_mesh = next(m for m in evidence["meshes"] if m["mesh_id"] == support["source_mesh_id"])
    support_faces = set(support["source_face_indices"])
    support_bindings = []
    for component in support_mesh["components"]:
        faces = tuple(sorted({support_mesh["triangle_source_face_indices"][i]
                              for i in component["source_triangle_indices"]
                              if support_mesh["triangle_source_face_indices"][i] in support_faces}))
        if faces:
            support_bindings.append(build_source_face_binding(
                evidence, binding_id=f"new-contact-patch:{component['component_id']}",
                source_mesh_id=support["source_mesh_id"],
                source_component_id=component["component_id"], source_face_indices=faces,
                proposed_role="WALKABLE_SUPPORT_SURFACE",
            ))
    obstacle_bindings = []
    for index, island in enumerate(discovery["source_island_bindings"]):
        mesh = next(m for m in evidence["meshes"] if m["mesh_id"] == island["source_mesh_id"])
        island_faces = set(island["source_face_indices"])
        for component in mesh["components"]:
            component_faces = tuple(sorted({
                mesh["triangle_source_face_indices"][i]
                for i in component["source_triangle_indices"]
                if mesh["triangle_source_face_indices"][i] in island_faces
            }))
            if component_faces:
                source_points = [mesh["vertices"][j]
                                 for i in component["source_triangle_indices"]
                                 if mesh["triangle_source_face_indices"][i] in component_faces
                                 for j in mesh["triangles"][i]]
                proposed_obstacle_bounds: tuple[Coordinate, Coordinate] = (
                    tuple(min(float(p[a]) for p in source_points) for a in range(3)),
                    tuple(max(float(p[a]) for p in source_points) for a in range(3)),
                )  # type: ignore[assignment]
                obstacle_bindings.append(build_source_face_binding(
                    evidence, binding_id=f"source-island-{index}:{component['component_id']}",
                    source_mesh_id=mesh["mesh_id"],
                    source_component_id=component["component_id"],
                    source_face_indices=component_faces, proposed_role="MOVEMENT_OBSTACLE_SURFACE",
                    source_face_movement_obstacle_bounds_bu=proposed_obstacle_bounds,
                ))
    cells = []
    if not isinstance(proposed_surface_semantics, BoundedSurfaceSemantics) and set(
        proposed_surface_semantics,
    ) != {str(i) for i in range(len(discovery["proposed_footpoint_cells"]))}:
        raise ValueError("per-cell proposed semantics must explicitly cover every exact cell index")
    for index, cell in enumerate(discovery["proposed_footpoint_cells"]):
        guard = cell["body_guard_bounds_bu"]
        profile_value = proposed_surface_semantics if isinstance(
            proposed_surface_semantics, BoundedSurfaceSemantics,
        ) else proposed_surface_semantics[str(index)]
        profiles = () if profile_value is None else (profile_value,) if isinstance(
            profile_value, BoundedSurfaceSemantics,
        ) else profile_value
        cells.append(ScopeCellProposal(
            cell_id=f"branch-cell-{index:02d}",
            rectangle_xy_bu=tuple(cell["footpoint_cell_bounds_xy_bu"]),
            body_region_id=cell["source_body_region_id"],
            proposed_body_guard_bounds_bu=(tuple(guard["minimum"]), tuple(guard["maximum"])),
            surface_semantics=None if not profiles else profiles[0],
            extra_surface_semantics=profiles[1:],
        ))
    return ScopeProposal(
        scope_id=scope_id, pins=pins, discovery_content_sha256=content_sha256(discovery),
        floor=floor, support_bindings=tuple(support_bindings),
        obstacle_bindings=tuple(obstacle_bindings), cells=tuple(cells),
        camera_landmark_bindings=camera_landmark_bindings,
        requested_projection_authority=bool(camera_landmark_bindings),
    )


def preview_scope_numeric(
    proposal: ScopeProposal, evidence: Mapping[str, Any], contract: PhysicalPolicyContract,
    numerics: CollisionNumerics, *, expected_pins: ScopeAuthorityPins,
    camera_export: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Hypothetical original checks for review, with no reusable authority output.

    Core routines require support-role records for their numerical calculation.
    These proposed-contact assumptions exist only in memory. Bounded surface
    semantics remain unapplied, so ambiguous enclosure/zero-area geometry remains
    REVIEW. No human APPROVE, semantic receipt, certificate or provider is created
    or returned. Formal application requires the independent direct-human receipt.
    """
    proposal = validate_scope_proposal(
        proposal, evidence, contract, numerics, expected_pins=expected_pins,
        camera_export=camera_export,
    )
    domain = _support_domain_for_calculation(
        proposal, evidence, contract, approval_id="HYPOTHETICAL_CONTACT_ONLY_NOT_APPROVAL",
        permission_evidence="UNAPPROVED_PROPOSED_CONTACT_NUMERICAL_ASSUMPTION_ONLY",
    )
    checks = []
    sufficient_count = 0
    support = frozenset((b.source_object_id, f)
                        for b in proposal.support_bindings for f in b.source_face_indices)
    for cell in proposal.cells:
        guard_failure = _proposed_guard_failure(cell, domain, contract)
        if guard_failure is not None:
            checks.append({"cell_id": cell.cell_id, "status": "REVIEW", "reason": guard_failure,
                           "bounded_surface_semantics_applied": False})
            continue
        ephemeral, detail = certify_local_rectangle(
            domain, box(*cell.rectangle_xy_bu), evidence, cell.body_region_id, contract, numerics,
            support_source_faces=support,
            evidence_content_sha256=proposal.pins.evidence_content_sha256,
            maximum_enclosure_pair_checks=proposal.maximum_enclosure_pair_checks,
            self_intersection_numeric_epsilon_bu=proposal.self_intersection_numeric_epsilon_bu,
        )
        sufficient_count += ephemeral is not None
        check = {"cell_id": cell.cell_id, **{k: v for k, v in detail.items() if k != "certificate"}}
        if ephemeral is not None:
            check["status"] = "NUMERIC_CHECK_PASS_WITH_PROPOSED_CONTACT_PERMISSION_ONLY"
        check["bounded_surface_semantics_applied"] = False
        checks.append(check)
    return {
        "schema_version": "phase1-new-local-scope-numeric-preview-v1",
        "status": "HYPOTHETICAL_NUMERIC_NOT_AUTHORITY", "scope_id": proposal.scope_id,
        "proposal_content_sha256": content_sha256(proposal.model_dump(mode="json")),
        "source_sha256": proposal.pins.source_sha256, "cell_checks": checks,
        "all_cells_strictly_sufficient_with_proposed_contact_permission_only": (
            sufficient_count == len(proposal.cells)
        ), "new_human_approval_exists": False, "authority_applied": False,
        "formal_certificate": None, "formal_execution_enabled": False,
        "case_readiness": "NOT_RUN", "source_geometry_modified": False,
        "original_approvals_modified": False, "gt_used": False,
        "required_human_semantics": [
            {"kind": "SOURCE_FACE_MOVEMENT_OBSTACLE", "binding_id": binding.binding_id,
             "source_face_movement_obstacle_bounds_bu": (
                 binding.source_face_movement_obstacle_bounds_bu
             ), "whole_object_approved": False, "solid_interior_approved": False}
            for binding in proposal.obstacle_bindings
            if binding.source_face_movement_obstacle_bounds_bu is not None
        ],
    }


def _segment_interval(
    start: Coordinate, end: Coordinate, bounds: tuple[Coordinate, Coordinate],
) -> tuple[Fraction, Fraction] | None:
    """Exact closed-box parameter intervals; never bridge a gap with epsilon."""
    enter, leave = Fraction(0), Fraction(1)
    q_start = tuple(Fraction.from_float(float(v)) for v in start)
    q_end = tuple(Fraction.from_float(float(v)) for v in end)
    low, high = (tuple(Fraction.from_float(float(v)) for v in point) for point in bounds)
    for axis in range(3):
        delta = q_end[axis] - q_start[axis]
        if delta == 0:
            if not low[axis] <= q_start[axis] <= high[axis]:
                return None
        else:
            a, b = (low[axis] - q_start[axis]) / delta, (high[axis] - q_start[axis]) / delta
            enter, leave = max(enter, min(a, b)), min(leave, max(a, b))
            if enter > leave:
                return None
    return enter, leave


@dataclass(frozen=True, slots=True)
class ScopedUnionPhysicalProvider:
    """The intact union receipt is the consumer's authority, never its outer box."""

    certificate: ScopeUnionCertificate
    domain: WalkableClearanceDomain
    contract: PhysicalPolicyContract
    proposal: ScopeProposal
    decision: ScopeHumanDecision
    expected_certificate_content_sha256: str

    @property
    def source_sha256(self) -> str:
        return self.certificate.source_sha256

    @property
    def certificate_content_sha256(self) -> str:
        return self.expected_certificate_content_sha256

    @property
    def semantic_review_content_sha256(self) -> str:
        return self.certificate.human_decision_content_sha256

    @property
    def human_decisions_sha256(self) -> str:
        return self.certificate.human_decision_content_sha256

    @property
    def scope_id(self) -> str:
        return self.certificate.scope_id

    def validate(self) -> None:
        type(self)(self.certificate, self.domain, self.contract, self.proposal, self.decision,
                   self.expected_certificate_content_sha256)

    def __post_init__(self) -> None:
        cert = ScopeUnionCertificate.model_validate_json(self.certificate.model_dump_json())
        proposal = ScopeProposal.model_validate_json(self.proposal.model_dump_json())
        decision = ScopeHumanDecision.model_validate_json(self.decision.model_dump_json())
        if decision.decision != "APPROVE" or (
            content_sha256(cert.model_dump(mode="json")) != self.expected_certificate_content_sha256
            or cert.proposal_content_sha256 != content_sha256(proposal.model_dump(mode="json"))
            or cert.human_decision_content_sha256 != content_sha256(
                decision.model_dump(mode="json"),
            )
            or decision.proposal_content_sha256 != cert.proposal_content_sha256
            or cert.pins != proposal.pins or cert.scope_id != proposal.scope_id
            or cert.source_sha256 != proposal.pins.source_sha256
            or cert.domain_content_sha256 != local_domain_content_sha256(self.domain)
            or contract_content_sha256(self.contract) != cert.pins.physical_contract_content_sha256
            or len(cert.cells) != len(proposal.cells)
            or tuple(content_sha256(c.model_dump(mode="json")) for c in cert.cells)
            != cert.cell_content_sha256
        ):
            raise ValueError("new local union proposal/approval/certificate/domain binding differs")
        union = normalize(union_all([box(*c.rectangle_xy_bu) for c in proposal.cells]))
        if cert.union_wkb_hex != union.wkb_hex or cert.union_wkb_sha256 != hashlib.sha256(
            union.wkb,
        ).hexdigest():
            raise ValueError("local union differs from exact approved cells")
        for cell, proof in zip(proposal.cells, cert.cells, strict=True):
            physical = _physical(proof)
            low, high = physical.footpoint_bounds_bu
            if (low[0], low[1], high[0], high[1]) != cell.rectangle_xy_bu or (
                physical.region_id != cell.body_region_id
                or physical.evidence_content_sha256 != cert.pins.evidence_content_sha256
            ):
                raise ValueError("cell physical certificate differs from approved exact rectangle")
            profiles = cell.all_surface_semantics
            if isinstance(proof, (
                ReviewedLocalScopeCertificate, MultiReviewedLocalScopeCertificate,
            )):
                reviews: tuple[ScopedSourceSurfaceReview | MultiSourceSurfaceReview, ...]
                reviews = (proof.semantic_review,) if isinstance(
                    proof, ReviewedLocalScopeCertificate,
                ) else proof.semantic_reviews
                if len(reviews) != len(profiles):
                    raise ValueError("cell certificate differs from approved bounded semantics")
                for index, review in enumerate(reviews):
                    semantics = profiles[index]
                    if review.model_dump(mode="python")["body_envelope_bounds_bu"] != (
                        cell.proposed_body_guard_bounds_bu
                    ) or any(
                        review.model_dump(mode="json")[k] != v
                        for k, v in semantics.model_dump(mode="json").items()
                    ):
                        raise ValueError("cell certificate differs from approved bounded semantics")
            elif profiles:
                raise ValueError("bounded semantic wrapper cannot be discarded")
            self._provider(proof)
        object.__setattr__(self, "certificate", cert)
        object.__setattr__(self, "proposal", proposal)
        object.__setattr__(self, "decision", decision)

    def _provider(self, proof: CellCertificate) -> CellProvider:
        if isinstance(proof, MultiReviewedLocalScopeCertificate):
            return MultiReviewedRestrictedPhysicalProvider(
                proof, self.domain, self.contract, content_sha256(proof.model_dump(mode="json")),
                self.certificate.human_decision_content_sha256,
            )
        if isinstance(proof, ReviewedLocalScopeCertificate):
            return ReviewedRestrictedLocalPhysicalProvider(
                proof, self.domain, self.contract, content_sha256(proof.model_dump(mode="json")),
                self.certificate.human_decision_content_sha256,
            )
        return RestrictedLocalPhysicalProvider(
            proof, self.domain, self.contract,
            expected_source_sha256=self.certificate.source_sha256,
            expected_evidence_content_sha256=self.certificate.pins.evidence_content_sha256,
            expected_certificate_content_sha256=content_sha256(proof.model_dump(mode="json")),
        )

    def validate_polyline(self, points_bu: tuple[Coordinate, ...]) -> bool:
        self.validate()
        if len(points_bu) < 2 or any(
            len(point) != 3 or any(isinstance(v, bool) or not math.isfinite(v) for v in point)
            for point in points_bu
        ):
            raise ValueError("local union requires at least two finite 3D footpoints")
        for start, end in pairwise(points_bu):
            intervals = []
            for proof in self.certificate.cells:
                interval = _segment_interval(start, end, _physical(proof).footpoint_bounds_bu)
                if interval is not None:
                    intervals.append((interval[0], interval[1], proof))
            intervals.sort(key=lambda value: (value[0], -value[1]))
            covered = Fraction(0)
            for left, right, _proof in intervals:
                if left > covered:
                    break
                covered = max(covered, right)
            if covered < 1 or not intervals or intervals[0][0] > 0:
                raise GeometryAuthorityError(("OUTSIDE_APPROVED_LOCAL_UNION_OR_HOLE",))
            # Every placement is covered by a certified cell. The support consumer
            # additionally checks the original, unsplit segment and actual Z band.
            if not self.domain.validate_segment(start, end).valid:
                raise GeometryAuthorityError(("OFF_APPROVED_BODY_CLEAR_WALKABLE",))
        return True


def load_scoped_authority(
    proposal: ScopeProposal, decision: ScopeHumanDecision, certificate: ScopeUnionCertificate,
    evidence: Mapping[str, Any], contract: PhysicalPolicyContract, numerics: CollisionNumerics, *,
    expected_pins: ScopeAuthorityPins, expected_certificate_content_sha256: str,
    camera_export: Mapping[str, Any] | None = None,
) -> ScopedUnionPhysicalProvider:
    """Revalidate source bindings and regenerate all numerical proofs on load."""
    checked, detail = apply_scope_approval(
        proposal, decision, evidence, contract, numerics, expected_pins=expected_pins,
        expected_proposal_content_sha256=certificate.proposal_content_sha256,
        expected_decision_content_sha256=certificate.human_decision_content_sha256,
        camera_export=camera_export,
    )
    if checked is None or checked != certificate or content_sha256(
        certificate.model_dump(mode="json"),
    ) != expected_certificate_content_sha256:
        raise ValueError(f"new local authority numerical proof/certificate unavailable: {detail}")
    return ScopedUnionPhysicalProvider(
        certificate, _domain_after_approval(proposal, evidence, contract, decision), contract,
        proposal, decision, expected_certificate_content_sha256,
    )
