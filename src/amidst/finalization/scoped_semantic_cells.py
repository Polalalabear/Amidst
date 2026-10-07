"""Multiple explicit bounded source reviews, with original numerical primitives.

Original single-profile producers are unchanged. Each supplied component owns
only its own reviewed envelope and exact zero-area source faces. All actual
nondegenerate source triangles and every unsupplied component remain screened.
No review is generated here: a caller must provide independently pinned direct
human receipts before invoking this numerical application function.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
from pydantic import Field, model_validator
from shapely import from_wkb, normalize, union_all
from shapely.geometry import Polygon

from amidst.local_physical_scopes import (
    LocalScopeCertificate,
    RestrictedLocalPhysicalProvider,
    _body_vertices,
    _check_domain_contract,
    _check_enclosure_limits,
    _check_rectangle,
    _checked_bounds,
    _triangle,
    _validate_local_evidence,
    certify_local_rectangle,
    local_domain_content_sha256,
)
from amidst.obstacle_volume_authority import (
    component_geometry,
    component_self_intersection,
    component_topology,
    content_sha256,
    region_patches,
)
from amidst.physical_collision import (
    CollisionNumerics,
    point_inside_closed_mesh,
    upright_body_triangle_distance,
)
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.scene_geometry import Coordinate, Digest, GeometryModel
from amidst.walkable_clearance import WalkableClearanceDomain


class MultiSourceSurfaceReview(GeometryModel):
    schema_version: Literal["bounded-source-surface-review-v2"] = "bounded-source-surface-review-v2"
    decision_id: str = Field(min_length=1)
    decision: Literal["APPROVE"]
    decision_option: Literal["LOCAL_SOURCE_SURFACE_ONLY", "EXACT_DERIVED_SURFACE_REPAIR"]
    human_approval_id: str = Field(min_length=1)
    human_decisions_sha256: Digest
    source_sha256: Digest
    evidence_content_sha256: Digest
    source_mesh_id: Digest
    source_geometry_sha256: Digest
    source_object_id: str = Field(min_length=1)
    source_component_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    body_envelope_bounds_bu: tuple[Coordinate, Coordinate]
    zero_area_source_face_indices: tuple[int, ...]
    component_interior: Literal["SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND"] = (
        "SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND"
    )
    zero_area_face_ownership: Literal["DEGENERATE_SEAM_NO_OCCUPIED_VOLUME_IN_BOUND"] = (
        "DEGENERATE_SEAM_NO_OCCUPIED_VOLUME_IN_BOUND"
    )
    whole_component_approved: Literal[False] = False
    source_geometry_modified: Literal[False] = False

    @model_validator(mode="after")
    def validate_receipt(self) -> MultiSourceSurfaceReview:
        if any(
            not value.strip()
            for value in (
                self.decision_id,
                self.human_approval_id,
                self.source_object_id,
                self.source_component_id,
                self.region_id,
            )
        ):
            raise ValueError("scoped human review identities cannot be blank")
        low, high = self.body_envelope_bounds_bu
        if any(not math.isfinite(v) for p in (low, high) for v in p) or any(
            low[i] >= high[i] for i in range(3)
        ):
            raise ValueError("reviewed body envelope must have finite positive 3D extent")
        if len(set(self.zero_area_source_face_indices)) != len(
            self.zero_area_source_face_indices
        ) or any(isinstance(v, bool) or v < 0 for v in self.zero_area_source_face_indices):
            raise ValueError("source zero-area face indices must be unique nonnegative integers")
        return self

    def contains_envelope(self, low: Coordinate, high: Coordinate) -> bool:
        bounds_low, bounds_high = self.body_envelope_bounds_bu
        return all(bounds_low[i] <= low[i] <= high[i] <= bounds_high[i] for i in range(3))

    def matches_component(self, mesh: Mapping[str, Any], component_id: str) -> bool:
        return (
            mesh["mesh_id"] == self.source_mesh_id
            and mesh["source_object_id"] == self.source_object_id
            and mesh["geometry_sha256"] == self.source_geometry_sha256
            and component_id == self.source_component_id
        )


def validate_multi_source_review(
    receipt: MultiSourceSurfaceReview,
    evidence: Mapping[str, Any],
    *,
    expected_receipt_content_sha256: str,
    expected_human_decisions_sha256: str,
    region_id: str,
) -> MultiSourceSurfaceReview:
    """Validate explicit independent hashes against previously validated source atlas."""
    checked = MultiSourceSurfaceReview.model_validate(receipt)
    if content_sha256(checked.model_dump(mode="json")) != expected_receipt_content_sha256:
        raise ValueError("scoped semantic human receipt hash mismatch")
    if checked.human_decisions_sha256 != expected_human_decisions_sha256:
        raise ValueError("scoped semantic human decisions hash mismatch")
    if (
        checked.source_sha256 != evidence["source_sha256"]
        or checked.evidence_content_sha256 != content_sha256(evidence)
        or checked.region_id != region_id
    ):
        raise ValueError("scoped semantic source/evidence/region binding mismatch")
    regions = [region for region in evidence["regions"] if region["region_id"] == region_id]
    if len(regions) != 1 or regions[0]["kind"] != "FULL_BODY_CONTEXT":
        raise ValueError("scoped semantic review requires a unique full-body source region")
    if not any(
        selection["mesh_id"] == checked.source_mesh_id
        and checked.source_component_id in selection["component_ids"]
        for selection in regions[0]["selections"]
    ):
        raise ValueError("reviewed source component is not selected by this local body region")
    meshes = [mesh for mesh in evidence["meshes"] if mesh["mesh_id"] == checked.source_mesh_id]
    if len(meshes) != 1:
        raise ValueError("reviewed source mesh missing or duplicated")
    mesh = meshes[0]
    if (
        mesh["source_object_id"] != checked.source_object_id
        or mesh["geometry_sha256"] != checked.source_geometry_sha256
    ):
        raise ValueError("reviewed source object/geometry binding mismatch")
    parts = [
        part for part in mesh["components"] if part["component_id"] == checked.source_component_id
    ]
    if len(parts) != 1:
        raise ValueError("reviewed source component missing or duplicated")
    selected = set(parts[0]["source_triangle_indices"])
    points = np.asarray(mesh["vertices"], dtype=float)
    for face in checked.zero_area_source_face_indices:
        triangles = [
            index
            for index, parent in enumerate(mesh["triangle_source_face_indices"])
            if parent == face
        ]
        if not triangles or any(index not in selected for index in triangles):
            raise ValueError("reviewed zero-area face has missing/different source component")
        for index in triangles:
            triangle = points[np.asarray(mesh["triangles"][index], dtype=int)]
            if np.linalg.norm(np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])) != 0:
                raise ValueError("scoped semantics cannot waive a nondegenerate source triangle")
    return checked


class MultiReviewedLocalScopeCertificate(GeometryModel):
    schema_version: Literal["phase1-multi-reviewed-local-cell-v1"] = (
        "phase1-multi-reviewed-local-cell-v1"
    )
    physical_certificate: LocalScopeCertificate
    semantic_reviews: tuple[MultiSourceSurfaceReview, ...] = Field(min_length=1)
    semantic_review_content_sha256: tuple[Digest, ...] = Field(min_length=1)
    exact_zero_area_source_triangles_excluded: int = Field(ge=0)
    original_strict_result_reason: str = Field(min_length=1)
    bounded_source_semantics_applied: Literal[True] = True
    original_source_geometry_modified: Literal[False] = False
    whole_component_authority_upgraded: Literal[False] = False

    @model_validator(mode="after")
    def validate_bindings(self) -> MultiReviewedLocalScopeCertificate:
        physical = self.physical_certificate
        if len({(r.source_mesh_id, r.source_component_id) for r in self.semantic_reviews}) != len(
            self.semantic_reviews,
        ) or len(self.semantic_reviews) != len(self.semantic_review_content_sha256):
            raise ValueError(
                "multi-reviewed cell requires unique components and aligned receipt hashes",
            )
        if tuple(content_sha256(r.model_dump(mode="json")) for r in self.semantic_reviews) != (
            self.semantic_review_content_sha256
        ) or len({r.human_decisions_sha256 for r in self.semantic_reviews}) != 1:
            raise ValueError("multi-reviewed cell receipts require one exact human decision")
        if any(r.source_sha256 != physical.source_sha256
               or r.evidence_content_sha256 != physical.evidence_content_sha256
               or r.region_id != physical.region_id for r in self.semantic_reviews):
            raise ValueError("multi-reviewed cell source/evidence/region receipt mismatch")
        if self.exact_zero_area_source_triangles_excluded > physical.source_triangles_screened:
            raise ValueError("multi-reviewed excluded count exceeds original screened triangles")
        return self


def regenerate_multi_reviewed_certificate(
    declarations: tuple[MultiSourceSurfaceReview, ...],
    original_evidence: Mapping[str, Any],
    domain: WalkableClearanceDomain,
    rectangle_bu: Polygon,
    region_id: str,
    contract: PhysicalPolicyContract,
    numerics: CollisionNumerics,
    *,
    support_source_faces: frozenset[tuple[str, int]],
    expected_receipt_content_sha256: tuple[str, ...],
    expected_human_decisions_sha256: str,
    expected_evidence_content_sha256: str,
    maximum_enclosure_pair_checks: int = 250000,
    self_intersection_numeric_epsilon_bu: float = 1e-9,
) -> tuple[MultiReviewedLocalScopeCertificate | None, dict[str, Any]]:
    """Exhaustive original-source proof with exactly bounded, human approved semantics.

    Historical producers and artifacts stay byte-for-byte unchanged. The original
    strict certifier validates the atlas/domain/policy first. This additive proof
    uses its support/body/distance/topology helpers; only reviewed exact zero-area
    source faces and the reviewed component's interior in the bound are exempt.
    It never derives a new atlas or changes complete-object/source hash claims.
    """
    _validate_local_evidence(original_evidence, domain.source_sha256)
    if content_sha256(original_evidence) != expected_evidence_content_sha256:
        raise ValueError("reviewed certificate original source evidence hash mismatch")
    if not declarations or len(declarations) != len(expected_receipt_content_sha256):
        raise ValueError("multi-profile proof requires explicit independently pinned reviews")
    reviews = tuple(validate_multi_source_review(
        declaration, original_evidence, expected_receipt_content_sha256=receipt_hash,
        expected_human_decisions_sha256=expected_human_decisions_sha256, region_id=region_id,
    ) for declaration, receipt_hash in zip(
        declarations, expected_receipt_content_sha256, strict=True,
    ))
    if len({(r.source_mesh_id, r.source_component_id) for r in reviews}) != len(reviews):
        raise ValueError("multi-profile component ownership must be unique")
    strict_certificate, strict_result = certify_local_rectangle(
        domain,
        rectangle_bu,
        original_evidence,
        region_id,
        contract,
        numerics,
        support_source_faces=support_source_faces,
        evidence_content_sha256=expected_evidence_content_sha256,
        maximum_enclosure_pair_checks=maximum_enclosure_pair_checks,
        self_intersection_numeric_epsilon_bu=self_intersection_numeric_epsilon_bu,
    )
    _check_domain_contract(domain, contract)
    _check_rectangle(rectangle_bu)
    _check_enclosure_limits(maximum_enclosure_pair_checks, self_intersection_numeric_epsilon_bu)
    numerics = CollisionNumerics.model_validate(numerics)
    region = next(row for row in original_evidence["regions"] if row["region_id"] == region_id)
    if (
        region["kind"] != "FULL_BODY_CONTEXT"
        or not region["selection_complete"]
        or original_evidence["policy"].get("component_enclosure_candidates_included") is not True
    ):
        return None, {"status": "REVIEW", "reason": "FULL_BODY_SOURCE_SELECTION_INCOMPLETE"}
    union = from_wkb(domain.union_wkb)
    if (
        not union.covers(rectangle_bu)
        or union.boundary.distance(rectangle_bu) < domain.required_clearance_bu
    ):
        return None, {"status": "REVIEW", "reason": "OUTSIDE_ERODED_APPROVED_SUPPORT"}
    band = domain.actual_contact_height_band(rectangle_bu)
    if band is None:
        return None, {"status": "REVIEW", "reason": "NO_COMMON_ACTUAL_SOURCE_CONTACT_HEIGHT"}
    low_z, high_z = band
    xmin, ymin, xmax, ymax = rectangle_bu.bounds
    extra = contract.scale.to_blender_units(contract.parameter("body_clearance_m"))
    envelope_low = np.array(
        [xmin - domain.required_clearance_bu, ymin - domain.required_clearance_bu, low_z - extra]
    )
    envelope_high = np.array(
        [
            xmax + domain.required_clearance_bu,
            ymax + domain.required_clearance_bu,
            high_z
            + contract.scale.to_blender_units(
                contract.parameter("body_height_m") + contract.parameter("body_clearance_m"),
            ),
        ]
    )
    low_coord: Coordinate = tuple(float(v) for v in envelope_low)  # type: ignore[assignment]
    high_coord: Coordinate = tuple(float(v) for v in envelope_high)  # type: ignore[assignment]
    if not all(review.contains_envelope(low_coord, high_coord) for review in reviews):
        return None, {"status": "REVIEW", "reason": "OUTSIDE_HUMAN_REVIEWED_BODY_ENVELOPE"}
    region_low, region_high = _checked_bounds(region["bounds_bu"])
    if not (np.all(envelope_low >= region_low) and np.all(envelope_high <= region_high)):
        return None, {"status": "REVIEW", "reason": "SOURCE_REGION_DOES_NOT_COVER_BODY_ENVELOPE"}
    ratio = contract.scale.metres_per_blender_unit
    vertices = _body_vertices(rectangle_bu, low_z, high_z, ratio)
    screened, queries, legal, excluded = 0, 0, 0, 0
    minimum_gap: float | None = None
    support_polygons = []
    clearance = contract.parameter("body_clearance_m")
    contact = contract.parameter("collision_tolerance_m")
    for patch in region_patches(original_evidence, region_id):
        triangles = np.asarray(patch["vertices"])[np.asarray(patch["triangles"])]
        screened += len(triangles)
        indices = np.flatnonzero(
            (triangles.max(axis=1) >= envelope_low).all(axis=1)
            & (triangles.min(axis=1) <= envelope_high).all(axis=1)
        )
        for index in indices:
            triangle = triangles[index]
            binding = (patch["source_object_id"], int(patch["triangle_source_face_indices"][index]))
            norm = float(
                np.linalg.norm(np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0]))
            )
            if norm == 0:
                if (
                    any(patch["mesh_id"] == review.source_mesh_id
                        and binding[0] == review.source_object_id
                        and binding[1] in review.zero_area_source_face_indices
                        for review in reviews)
                ):
                    excluded += 1
                    continue
                return None, {
                    "status": "REVIEW",
                    "reason": "DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE",
                    "source_object_id": binding[0],
                    "source_face_index": binding[1],
                }
            if binding in support_source_faces and (
                low_z >= float(triangle[:, 2].max()) - domain.contact_tolerance_bu
                and high_z <= float(triangle[:, 2].min()) + domain.contact_tolerance_bu
            ):
                legal += 1
                support_polygons.append(Polygon(triangle[:, :2]))
                continue
            queries += 1
            if queries > numerics.maximum_triangles_per_segment:
                return None, {"status": "REVIEW", "reason": "LOCAL_BODY_QUERY_BUDGET_EXCEEDED"}
            distance = upright_body_triangle_distance(
                vertices,
                _triangle(triangle, ratio),
                radius_m=contract.parameter("body_radius_m"),
                height_m=contract.parameter("body_height_m"),
                numerics=numerics,
            )
            roundoff = 16 * math.ulp(max(clearance, distance.upper_m, 1.0))
            if distance.lower_m < clearance - roundoff:
                reason = (
                    "UNCLASSIFIED_SOURCE_BODY_CONTACT"
                    if distance.upper_m <= contact
                    else "UNCLASSIFIED_SOURCE_BODY_CLEARANCE"
                    if distance.upper_m < clearance
                    else "UNCLASSIFIED_SOURCE_DISTANCE_UNCERTAIN"
                )
                return None, {
                    "status": "REVIEW",
                    "reason": reason,
                    "source_object_id": binding[0],
                    "source_face_index": binding[1],
                    "distance_lower_m": distance.lower_m,
                    "distance_upper_m": distance.upper_m,
                }
            minimum_gap = (
                distance.lower_m
                if minimum_gap is None
                else min(
                    minimum_gap,
                    distance.lower_m,
                )
            )
    center = np.array(
        [
            (xmin + xmax) / 2,
            (ymin + ymax) / 2,
            (low_z + high_z) / 2
            + contract.scale.to_blender_units(
                contract.parameter("body_height_m") / 2,
            ),
        ]
    )
    meshes = {mesh["mesh_id"]: mesh for mesh in original_evidence["meshes"]}
    for selection in region["selections"]:
        mesh = meshes[selection["mesh_id"]]
        for component in mesh["components"]:
            if component["component_id"] not in selection["component_ids"]:
                continue
            bounds = component["bounds_bu"]
            if not (np.all(center >= bounds["minimum"]) and np.all(center <= bounds["maximum"])):
                continue
            if any(review.matches_component(mesh, component["component_id"]) for review in reviews):
                # This exact body envelope is entirely in the reviewed surface-only bound.
                # No assertion about the component's interior outside the bound is made.
                continue
            component_vertices, component_triangles, _ = component_geometry(mesh, component)
            topology = component_topology(component_vertices, component_triangles)
            if topology["boundary_edge_count"] > 0:
                continue
            if not topology["closed_consistent_nonzero_volume"]:
                return None, {
                    "status": "REVIEW",
                    "reason": "UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN",
                    "source_object_id": mesh["source_object_id"],
                    "source_component_id": component["component_id"],
                }
            safety = component_self_intersection(
                component_vertices,
                component_triangles,
                maximum_pair_checks=maximum_enclosure_pair_checks,
                numerical_epsilon_bu=self_intersection_numeric_epsilon_bu,
            )
            if safety["status"] != "PASS":
                return None, {
                    "status": "REVIEW",
                    "reason": "UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN",
                }
            inside = point_inside_closed_mesh(
                center * ratio,
                np.asarray(component_vertices)[np.asarray(component_triangles)] * ratio,
            )
            if inside is None or inside:
                return None, {
                    "status": "REVIEW",
                    "reason": (
                        "UNKNOWN_CLOSED_VOLUME_CONTAINMENT_UNCERTAIN"
                        if inside is None
                        else "INSIDE_UNCLASSIFIED_CLOSED_COMPONENT"
                    ),
                    "source_object_id": mesh["source_object_id"],
                    "source_component_id": component["component_id"],
                }
    if screened == 0 or legal == 0 or not union_all(support_polygons).covers(rectangle_bu):
        return None, {"status": "REVIEW", "reason": "INCOMPLETE_ACTUAL_LEGAL_SUPPORT_COVERAGE"}
    import hashlib

    identity: dict[str, Any] = {
        "floor": domain.floor.floor_id,
        "region": region_id,
        "rectangle_wkb": normalize(rectangle_bu).wkb_hex,
        "source_evidence": expected_evidence_content_sha256,
        "semantic_reviews": expected_receipt_content_sha256,
        "domain": local_domain_content_sha256(domain),
    }
    physical = LocalScopeCertificate(
        scope_id="school-v3:multi-reviewed-physical-island:" + content_sha256(identity)[:20],
        source_sha256=domain.source_sha256,
        evidence_content_sha256=expected_evidence_content_sha256,
        policy_content_sha256=content_sha256(contract.policy.model_dump(mode="json")),
        support_union_sha256=hashlib.sha256(domain.union_wkb).hexdigest(),
        domain_content_sha256=identity["domain"],
        approval_id=contract.runtime.approval_id,
        region_id=region_id,
        floor_id=domain.floor.floor_id,
        footpoint_bounds_bu=((xmin, ymin, low_z), (xmax, ymax, high_z)),
        support_surface_ids=domain.surface_ids,
        source_triangles_screened=screened,
        exact_distance_queries=queries,
        legal_support_triangles=legal,
        minimum_other_geometry_gap_m=minimum_gap,
    )
    certificate = MultiReviewedLocalScopeCertificate(
        physical_certificate=physical,
        semantic_reviews=reviews,
        semantic_review_content_sha256=expected_receipt_content_sha256,
        exact_zero_area_source_triangles_excluded=excluded,
        original_strict_result_reason=(
            "APPROVED" if strict_certificate is not None else strict_result["reason"]
        ),
    )
    return certificate, {
        "status": "APPROVED_RESTRICTED_MULTI_HUMAN_REVIEWED_SCOPE",
        "certificate": certificate.model_dump(mode="json"),
    }


@dataclass(frozen=True, slots=True)
class MultiReviewedRestrictedPhysicalProvider:
    certificate: MultiReviewedLocalScopeCertificate
    domain: WalkableClearanceDomain
    contract: PhysicalPolicyContract
    expected_certificate_content_sha256: str
    expected_human_decisions_sha256: str

    def __post_init__(self) -> None:
        checked = MultiReviewedLocalScopeCertificate.model_validate_json(
            self.certificate.model_dump_json(),
        )
        if content_sha256(checked.model_dump(mode="json")) != (
            self.expected_certificate_content_sha256
        ) or any(r.human_decisions_sha256 != self.expected_human_decisions_sha256
                 for r in checked.semantic_reviews):
            raise ValueError("multi-reviewed provider certificate/human receipt mismatch")
        low, high = checked.physical_certificate.footpoint_bounds_bu
        guard = self.contract.footprint_radius_bu
        extra = self.contract.scale.to_blender_units(self.contract.parameter("body_clearance_m"))
        envelope_low = (low[0] - guard, low[1] - guard, low[2] - extra)
        envelope_high = (high[0] + guard, high[1] + guard, high[2]
                         + self.contract.scale.to_blender_units(
                             self.contract.parameter("body_height_m")
                             + self.contract.parameter("body_clearance_m"),
                         ))
        if not all(r.contains_envelope(envelope_low, envelope_high)
                   for r in checked.semantic_reviews):
            raise ValueError("multi-reviewed certificate exceeds an approved semantic envelope")
        self._strict_provider(checked)
        object.__setattr__(self, "certificate", checked)

    def _strict_provider(
        self, certificate: MultiReviewedLocalScopeCertificate,
    ) -> RestrictedLocalPhysicalProvider:
        physical = certificate.physical_certificate
        return RestrictedLocalPhysicalProvider(
            physical, self.domain, self.contract,
            expected_source_sha256=physical.source_sha256,
            expected_evidence_content_sha256=physical.evidence_content_sha256,
            expected_certificate_content_sha256=content_sha256(physical.model_dump(mode="json")),
        )

    def validate_polyline(self, points_bu: tuple[Coordinate, ...]) -> bool:
        checked = type(self)(
            self.certificate, self.domain, self.contract,
            self.expected_certificate_content_sha256, self.expected_human_decisions_sha256,
        )
        return checked._strict_provider(checked.certificate).validate_polyline(points_bu)
