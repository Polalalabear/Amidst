"""Exhaustively screened local physical islands with explicit restricted domains.

Unclassified source geometry can block certification. It never becomes an
APPROVED collider, wall, occluder or navigation edge by proximity or name.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import InitVar, dataclass, field
from itertools import pairwise
from typing import Any, Literal

import numpy as np
from pydantic import Field, FiniteFloat, model_validator
from shapely import from_wkb, normalize, union_all
from shapely.geometry import Polygon, box

from amidst.obstacle_volume_authority import (
    component_geometry,
    component_self_intersection,
    component_topology,
    content_sha256,
    region_patches,
    validate_source_evidence,
)
from amidst.physical_collision import (
    CollisionNumerics,
    point_inside_closed_mesh,
    upright_body_triangle_distance,
)
from amidst.physical_policy_contract import PhysicalPolicyContract
from amidst.scene_geometry import (
    Authority,
    Coordinate,
    Digest,
    GeometryAuthorityError,
    GeometryModel,
)
from amidst.walkable_clearance import WalkableClearanceDomain


class LocalScopeCertificate(GeometryModel):
    schema_version: Literal["local-physical-scope-v1"] = "local-physical-scope-v1"
    scope_id: str = Field(min_length=1)
    authority: Literal["APPROVED"] = "APPROVED"
    source_sha256: Digest
    evidence_content_sha256: Digest
    policy_content_sha256: Digest
    support_union_sha256: Digest
    domain_content_sha256: Digest
    approval_id: str = Field(min_length=1)
    region_id: str = Field(min_length=1)
    floor_id: str = Field(min_length=1)
    footpoint_bounds_bu: tuple[Coordinate, Coordinate]
    support_surface_ids: tuple[str, ...] = Field(min_length=1)
    source_triangles_screened: int = Field(gt=0)
    exact_distance_queries: int = Field(ge=0)
    legal_support_triangles: int = Field(gt=0)
    minimum_other_geometry_gap_m: FiniteFloat | None = Field(default=None, ge=0)
    coverage: Literal["COMPLETE_RESTRICTED_FOOTPOINT_DOMAIN"] = (
        "COMPLETE_RESTRICTED_FOOTPOINT_DOMAIN"
    )
    outside_domain: Literal["REFUSE_VALIDATION"] = "REFUSE_VALIDATION"
    source_geometry_reclassified: Literal[False] = False
    approved_for_collision: Literal[True] = True
    approved_for_topology: Literal[True] = True
    physical_ready_for_case1_3: Literal[True] = True
    formal_case1_3_started: Literal[False] = False

    @model_validator(mode="after")
    def validate_certificate(self) -> LocalScopeCertificate:
        identities = (self.scope_id, self.region_id, self.floor_id, self.approval_id)
        if any(not value.strip() for value in identities):
            raise ValueError("local certificate identities/approval cannot be blank")
        if (
            any(not value.strip() for value in self.support_surface_ids)
            or len(set(self.support_surface_ids)) != len(self.support_surface_ids)
        ):
            raise ValueError("local support identities must be unique nonempty IDs")
        low, high = self.footpoint_bounds_bu
        if low[0] >= high[0] or low[1] >= high[1] or low[2] > high[2]:
            raise ValueError("local certificate bounds require positive XY area and ordered Z")
        if (
            self.legal_support_triangles > self.source_triangles_screened
            or self.exact_distance_queries > self.source_triangles_screened
        ):
            raise ValueError("local certificate counts exceed screened source geometry")
        return self


def _expected_digest(value: str, description: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{description} must be an independently provided SHA-256")


def local_domain_content_sha256(domain: WalkableClearanceDomain) -> str:
    """Bind every authority and quantity used by the immutable domain consumer."""
    return content_sha256({
        "source_sha256": domain.source_sha256,
        "floor": domain.floor.model_dump(mode="json"),
        "scale": domain.scale.model_dump(mode="json"),
        "policy": domain.policy.model_dump(mode="json"),
        "surface_ids": domain.surface_ids,
        "union_wkb": domain.union_wkb.hex(),
        "required_clearance_bu": domain.required_clearance_bu,
        "required_clearance_m": domain.required_clearance_m,
        "contact_tolerance_bu": domain.contact_tolerance_bu,
        "actual_support_surfaces": [
            surface.model_dump(mode="json") for surface in domain.support_surfaces
        ],
    })


def _check_domain_contract(
    domain: WalkableClearanceDomain, contract: PhysicalPolicyContract,
) -> None:
    contract = PhysicalPolicyContract(contract.policy, contract.scale, contract.runtime)
    contract.scale.require_source_sha256(domain.source_sha256)
    if (
        domain.policy != contract.policy or domain.scale != contract.scale
        or domain.floor.authority != Authority.APPROVED
        or domain.floor.normal != (0., 0., 1.)
        or domain.required_clearance_m != contract.footprint_radius_m
        or domain.required_clearance_bu != contract.footprint_radius_bu
        or domain.contact_tolerance_bu != contract.scale.to_blender_units(
            contract.parameter("collision_tolerance_m"),
        )
        or not domain.surface_ids or len(set(domain.surface_ids)) != len(domain.surface_ids)
        or any(not identity.strip() for identity in domain.surface_ids)
    ):
        raise ValueError("local scope domain differs from approved source/floor/body authority")
    # Domain construction uses frozen validated models, but these public records
    # can also be supplied through an unchecked dataclass replace/model_copy.
    type(domain.floor).model_validate(domain.floor)
    type(domain.policy).model_validate(domain.policy)
    type(domain.scale).model_validate(domain.scale)
    united = from_wkb(domain.union_wkb)
    if tuple(surface.surface_id for surface in domain.support_surfaces) != domain.surface_ids:
        raise ValueError("local domain actual source support identities differ")
    if (
        united.is_empty or not united.is_valid
        or united.geom_type not in ("Polygon", "MultiPolygon")
        or not all(math.isfinite(value) for value in united.bounds)
        or united.area <= 0
    ):
        raise ValueError("local scope requires finite nonempty actual support geometry")


def _check_rectangle(rectangle_bu: Polygon) -> None:
    if (
        not isinstance(rectangle_bu, Polygon) or rectangle_bu.is_empty
        or not rectangle_bu.is_valid or rectangle_bu.area <= 0
        or not all(math.isfinite(value) for value in rectangle_bu.bounds)
        or rectangle_bu.interiors
        or not rectangle_bu.equals(box(*rectangle_bu.bounds))
    ):
        raise ValueError("local footpoint domain must be a finite positive axis-aligned rectangle")


def _checked_bounds(value: Any) -> tuple[np.ndarray[Any, Any], np.ndarray[Any, Any]]:
    if not isinstance(value, Mapping):
        raise ValueError("source region bounds must be an explicit object")
    low, high = value.get("minimum"), value.get("maximum")
    if any(
        not isinstance(point, (list, tuple)) or len(point) != 3
        or any(isinstance(number, bool) or not isinstance(number, (int, float))
               or not math.isfinite(number) for number in point)
        for point in (low, high)
    ):
        raise ValueError("source region bounds must contain finite three-coordinate endpoints")
    lower, upper = np.asarray(low, dtype=float), np.asarray(high, dtype=float)
    if np.any(lower > upper):
        raise ValueError("source region bounds must have ordered endpoints")
    return lower, upper


def _validate_local_evidence(evidence: Mapping[str, Any], source_sha256: str) -> None:
    try:
        validate_source_evidence(evidence, expected_source_sha256=source_sha256)
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(
            "malformed local source evidence; original source bindings are required",
        ) from error


def _check_enclosure_limits(maximum_pairs: int, epsilon: float) -> None:
    if (
        isinstance(maximum_pairs, bool) or not isinstance(maximum_pairs, int) or maximum_pairs < 1
        or isinstance(epsilon, bool) or not math.isfinite(epsilon) or epsilon < 0
    ):
        raise ValueError("local enclosure guard requires a positive pair budget and finite epsilon")


def _triangle(raw: Any, scale: float) -> tuple[Coordinate, Coordinate, Coordinate]:
    points = [(float(p[0]) * scale, float(p[1]) * scale, float(p[2]) * scale) for p in raw]
    return points[0], points[1], points[2]


def _body_vertices(
    rectangle_bu: Polygon, min_z_bu: float, max_z_bu: float, ratio: float,
) -> tuple[Coordinate, ...]:
    return tuple(
        (float(x) * ratio, float(y) * ratio, z * ratio)
        for x, y in list(rectangle_bu.exterior.coords)[:-1]
        for z in sorted({min_z_bu, max_z_bu})
    )


def certify_local_rectangle(
    domain: WalkableClearanceDomain, rectangle_bu: Polygon,
    evidence: Mapping[str, Any], region_id: str, contract: PhysicalPolicyContract,
    numerics: CollisionNumerics, *, support_source_faces: frozenset[tuple[str, int]],
    evidence_content_sha256: str,
    maximum_enclosure_pair_checks: int = 250000,
    self_intersection_numeric_epsilon_bu: float = 1e-9,
) -> tuple[LocalScopeCertificate | None, dict[str, Any]]:
    """Public proof entry point, requiring independently checked immutable evidence.

    Discovery validates once and calls a private helper for its bounded search.
    Direct callers cannot bypass source verification with a populated cache.
    """
    _expected_digest(evidence_content_sha256, "expected evidence content hash")
    _validate_local_evidence(evidence, domain.source_sha256)
    _check_enclosure_limits(maximum_enclosure_pair_checks, self_intersection_numeric_epsilon_bu)
    if content_sha256(evidence) != evidence_content_sha256:
        raise ValueError("local source evidence content SHA-256 mismatch")
    if evidence["architectural_scale"] != contract.scale.model_dump(mode="json"):
        raise ValueError("local source evidence architectural scale differs from approved contract")
    return _certify_local_rectangle_verified(
        domain, rectangle_bu, evidence, region_id, contract, numerics,
        support_source_faces=support_source_faces,
        evidence_content_sha256=evidence_content_sha256, enclosure_cache={},
        maximum_enclosure_pair_checks=maximum_enclosure_pair_checks,
        self_intersection_numeric_epsilon_bu=self_intersection_numeric_epsilon_bu,
    )


def _certify_local_rectangle_verified(
    domain: WalkableClearanceDomain, rectangle_bu: Polygon,
    evidence: Mapping[str, Any], region_id: str, contract: PhysicalPolicyContract,
    numerics: CollisionNumerics, *, support_source_faces: frozenset[tuple[str, int]],
    evidence_content_sha256: str, enclosure_cache: dict[tuple[str, str], Any],
    maximum_enclosure_pair_checks: int,
    self_intersection_numeric_epsilon_bu: float,
) -> tuple[LocalScopeCertificate | None, dict[str, Any]]:
    """Prove every cylinder placement in a rectangular footpoint domain is clear.

    Source region selection is exhaustive and must cover the complete expanded
    body envelope. Exact convex distance screens actual triangles, never boxes.
    A failed/uncertain proof leaves REVIEW and records source faces for inspection.
    """
    _check_domain_contract(domain, contract)
    _check_rectangle(rectangle_bu)
    numerics = CollisionNumerics.model_validate(numerics)
    if any(
        not isinstance(binding, tuple) or len(binding) != 2
        or not isinstance(binding[0], str) or not binding[0].strip()
        or isinstance(binding[1], bool) or not isinstance(binding[1], int) or binding[1] < 0
        for binding in support_source_faces
    ):
        raise ValueError("legal support source bindings require object and nonnegative face IDs")
    if evidence["policy"].get("component_enclosure_candidates_included") is not True:
        return None, {"status": "REVIEW", "reason": "CLOSED_ENCLOSURES_NOT_EXHAUSTIVELY_SELECTED"}
    union = from_wkb(domain.union_wkb)
    if not union.covers(rectangle_bu) or (
        union.boundary.distance(rectangle_bu) < domain.required_clearance_bu
    ):
        return None, {"status": "REVIEW", "reason": "OUTSIDE_ERODED_APPROVED_SUPPORT"}
    matching = [row for row in evidence["regions"] if row["region_id"] == region_id]
    if len(matching) != 1:
        raise ValueError("local scope source region is missing or duplicated")
    region = matching[0]
    if region.get("floor_id") != domain.floor.floor_id:
        raise ValueError("local scope source region floor binding differs from approved support")
    if region["kind"] != "FULL_BODY_CONTEXT" or not region["selection_complete"]:
        return None, {"status": "REVIEW", "reason": "FULL_BODY_SOURCE_SELECTION_INCOMPLETE"}
    ratio = contract.scale.metres_per_blender_unit
    # Intersect the contact bands of every raw source-support fragment. Using
    # nominal +/- tolerance here would add plane and footpoint tolerances twice.
    contact_band = domain.actual_contact_height_band(rectangle_bu)
    if contact_band is None:
        return None, {"status": "REVIEW", "reason": "NO_COMMON_ACTUAL_SOURCE_CONTACT_HEIGHT"}
    low_z, high_z = contact_band
    minimum_x, minimum_y, maximum_x, maximum_y = rectangle_bu.bounds
    horizontal = contract.footprint_radius_bu
    body_extra = contract.scale.to_blender_units(contract.parameter("body_clearance_m"))
    envelope_low = np.array([minimum_x - horizontal, minimum_y - horizontal, low_z - body_extra])
    envelope_high = np.array([
        maximum_x + horizontal, maximum_y + horizontal,
        high_z + contract.scale.to_blender_units(
            contract.parameter("body_height_m") + contract.parameter("body_clearance_m"),
        ),
    ])
    region_lower, region_upper = _checked_bounds(region["bounds_bu"])
    if not (
        np.all(envelope_low >= region_lower)
        and np.all(envelope_high <= region_upper)
    ):
        return None, {"status": "REVIEW", "reason": "SOURCE_REGION_DOES_NOT_COVER_BODY_ENVELOPE"}
    vertices = _body_vertices(rectangle_bu, low_z, high_z, ratio)
    screened, queries, legal = 0, 0, 0
    minimum_gap: float | None = None
    legal_support_footprints = []
    clearance = contract.parameter("body_clearance_m")
    contact = contract.parameter("collision_tolerance_m")
    for patch in region_patches(evidence, region_id):
        points = np.array(patch["vertices"], dtype=np.float64)
        triangles = points[np.array(patch["triangles"], dtype=np.int64)]
        indices = np.flatnonzero(
            (triangles.max(axis=1) >= envelope_low).all(axis=1)
            & (triangles.min(axis=1) <= envelope_high).all(axis=1)
        )
        screened += len(triangles)
        for index in indices:
            triangle = triangles[index]
            face = int(patch["triangle_source_face_indices"][index])
            binding = (patch["source_object_id"], face)
            triangle_m = _triangle(triangle, ratio)
            actual = np.asarray(triangle_m)
            normal_length = float(np.linalg.norm(np.cross(
                actual[1] - actual[0], actual[2] - actual[0],
            )))
            if not math.isfinite(normal_length) or normal_length == 0:
                return None, {
                    "status": "REVIEW", "reason": "DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE",
                    "source_object_id": patch["source_object_id"], "source_face_index": face,
                    "triangle_bu": triangle.tolist(),
                    "source_triangles_screened": screened, "exact_distance_queries": queries,
                }
            if binding in support_source_faces and (
                low_z >= float(triangle[:, 2].max()) - domain.contact_tolerance_bu
                and high_z <= float(triangle[:, 2].min()) + domain.contact_tolerance_bu
            ):
                legal += 1
                legal_support_footprints.append(Polygon(triangle[:, :2]))
                continue
            queries += 1
            if queries > numerics.maximum_triangles_per_segment:
                return None, {"status": "REVIEW", "reason": "LOCAL_BODY_QUERY_BUDGET_EXCEEDED"}
            distance = upright_body_triangle_distance(
                vertices, triangle_m,
                radius_m=contract.parameter("body_radius_m"),
                height_m=contract.parameter("body_height_m"), numerics=numerics,
            )
            roundoff = 16 * math.ulp(max(clearance, distance.upper_m, 1.0))
            if distance.lower_m < clearance - roundoff:
                reason = (
                    "UNCLASSIFIED_SOURCE_BODY_CONTACT" if distance.upper_m <= contact else
                    "UNCLASSIFIED_SOURCE_BODY_CLEARANCE" if distance.upper_m < clearance else
                    "UNCLASSIFIED_SOURCE_DISTANCE_UNCERTAIN"
                )
                return None, {
                    "status": "REVIEW", "reason": reason,
                    "source_object_id": patch["source_object_id"], "source_face_index": face,
                    "triangle_bu": triangle.tolist(),
                    "distance_lower_m": distance.lower_m, "distance_upper_m": distance.upper_m,
                    "source_triangles_screened": screened, "exact_distance_queries": queries,
                }
            minimum_gap = (
                distance.lower_m if minimum_gap is None else min(minimum_gap, distance.lower_m)
            )
    # A cylinder wholly inside an unclassified solid need not touch its boundary.
    # This is a diagnostic blocker, never a semantic role or formal collider.
    center_bu = np.array([
        (minimum_x + maximum_x) / 2, (minimum_y + maximum_y) / 2,
        (low_z + high_z) / 2 + contract.scale.to_blender_units(
            contract.parameter("body_height_m") / 2,
        ),
    ])
    cache = enclosure_cache
    meshes = {mesh["mesh_id"]: mesh for mesh in evidence["meshes"]}
    for selection in region["selections"]:
        mesh = meshes[selection["mesh_id"]]
        for component in mesh["components"]:
            if component["component_id"] not in selection["component_ids"]:
                continue
            bounds = component["bounds_bu"]
            if not (np.all(center_bu >= bounds["minimum"])
                    and np.all(center_bu <= bounds["maximum"])):
                continue
            key = (mesh["mesh_id"], component["component_id"])
            if key not in cache:
                component_vertices, component_triangles, _ = component_geometry(mesh, component)
                topology = component_topology(component_vertices, component_triangles)
                if topology["boundary_edge_count"] > 0:
                    cache[key] = {"state": "OPEN_SOURCE_SURFACE_NOT_SOLID"}
                elif not topology["closed_consistent_nonzero_volume"]:
                    cache[key] = {
                        "state": "UNRESOLVED_CLOSED_GEOMETRY", "topology": topology,
                    }
                else:
                    safety = component_self_intersection(
                        component_vertices, component_triangles,
                        maximum_pair_checks=maximum_enclosure_pair_checks,
                        numerical_epsilon_bu=self_intersection_numeric_epsilon_bu,
                    )
                    cache[key] = (
                        {"state": "UNRESOLVED_CLOSED_GEOMETRY", "topology": topology,
                         "self_intersection": safety}
                        if safety["status"] != "PASS" else
                        {"state": "CHECKED_CLOSED_GEOMETRY",
                         "triangles_m": np.asarray(component_vertices)[
                             np.asarray(component_triangles),
                         ] * ratio}
                    )
            entry = cache[key]
            if entry["state"] == "UNRESOLVED_CLOSED_GEOMETRY":
                return None, {
                    "status": "REVIEW", "reason": "UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN",
                    "source_object_id": mesh["source_object_id"],
                    "source_component_id": component["component_id"],
                    "location_bu": center_bu.tolist(),
                    "enclosure_evidence": {k: v for k, v in entry.items() if k != "state"},
                }
            if entry["state"] != "CHECKED_CLOSED_GEOMETRY":
                continue
            inside = point_inside_closed_mesh(center_bu * ratio, entry["triangles_m"])
            if inside is None:
                return None, {
                    "status": "REVIEW", "reason": "UNKNOWN_CLOSED_VOLUME_CONTAINMENT_UNCERTAIN",
                    "source_object_id": mesh["source_object_id"],
                    "source_component_id": component["component_id"],
                    "location_bu": center_bu.tolist(),
                }
            if inside:
                return None, {
                    "status": "REVIEW", "reason": "INSIDE_UNCLASSIFIED_CLOSED_COMPONENT",
                    "source_object_id": mesh["source_object_id"],
                    "source_component_id": component["component_id"],
                    "location_bu": center_bu.tolist(),
                }
    if screened == 0 or legal == 0:
        return None, {
            "status": "REVIEW", "reason": "NO_EXHAUSTIVE_SOURCE_SUPPORT_EVIDENCE",
            "source_triangles_screened": screened, "legal_support_triangles": legal,
        }
    if not union_all(legal_support_footprints).covers(rectangle_bu):
        return None, {
            "status": "REVIEW", "reason": "INCOMPLETE_ACTUAL_LEGAL_SUPPORT_COVERAGE",
            "source_triangles_screened": screened, "legal_support_triangles": legal,
        }
    identity = {
        "floor": domain.floor.floor_id, "region": region_id,
        "rectangle_wkb": normalize(rectangle_bu).wkb_hex,
        "support": hashlib.sha256(domain.union_wkb).hexdigest(),
        "evidence": evidence_content_sha256,
        "policy": content_sha256(contract.policy.model_dump(mode="json")),
        "domain": local_domain_content_sha256(domain),
    }
    certificate = LocalScopeCertificate(
        scope_id="school-v3:physical-island:" + content_sha256(identity)[:20],
        source_sha256=domain.source_sha256, evidence_content_sha256=evidence_content_sha256,
        policy_content_sha256=identity["policy"], support_union_sha256=identity["support"],
        domain_content_sha256=identity["domain"], approval_id=contract.runtime.approval_id,
        region_id=region_id, floor_id=domain.floor.floor_id,
        footpoint_bounds_bu=((minimum_x, minimum_y, low_z), (maximum_x, maximum_y, high_z)),
        support_surface_ids=domain.surface_ids, source_triangles_screened=screened,
        exact_distance_queries=queries, legal_support_triangles=legal,
        minimum_other_geometry_gap_m=minimum_gap,
    )
    return certificate, {"status": "APPROVED", "certificate": certificate.model_dump(mode="json")}


def discover_local_scopes(
    domains: Mapping[str, WalkableClearanceDomain], evidence: Mapping[str, Any],
    contract: PhysicalPolicyContract, numerics: CollisionNumerics,
    *, support_source_faces: Mapping[str, frozenset[tuple[str, int]]],
    half_extent_m: tuple[float, ...], maximum_centers: int, maximum_approved: int,
    maximum_enclosure_pair_checks: int = 250000,
    self_intersection_numeric_epsilon_bu: float = 1e-9,
) -> dict[str, Any]:
    """Finite search for usable certified windows; bounds select, triangles decide."""
    if not half_extent_m or any(
        isinstance(x, bool) or not math.isfinite(x) or x <= 0 for x in half_extent_m
    ):
        raise ValueError("local window extents must be finite positive configured lengths")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
           for value in (maximum_centers, maximum_approved)):
        raise ValueError("local scope search budgets must be positive")
    source = contract.scale.source_asset_sha256
    _validate_local_evidence(evidence, source)
    _check_enclosure_limits(maximum_enclosure_pair_checks, self_intersection_numeric_epsilon_bu)
    numerics = CollisionNumerics.model_validate(numerics)
    if evidence["architectural_scale"] != contract.scale.model_dump(mode="json"):
        raise ValueError("local source evidence architectural scale differs from approved contract")
    evidence_digest = content_sha256(evidence)
    results: list[dict[str, Any]] = []
    approved: list[dict[str, Any]] = []
    enclosure_cache: dict[tuple[str, str], Any] = {}
    for region in sorted(evidence["regions"], key=lambda row: row["region_id"]):
        if region["kind"] != "FULL_BODY_CONTEXT":
            continue
        domain_id = region["annotation_object_id"]
        if domain_id not in domains:
            raise ValueError("full body context has no approved source-support domain")
        domain = domains[domain_id]
        union = from_wkb(domain.union_wkb)
        xmin, ymin, xmax, ymax = union.bounds
        representative = union.representative_point()
        grid = [(float(x), float(y)) for x in np.linspace(xmin, xmax, 9)
                for y in np.linspace(ymin, ymax, 9)]
        centers = [(representative.x, representative.y), *sorted(
            grid, key=lambda point: (math.dist(point, (representative.x, representative.y)), point),
        )]
        reviews = []
        found = None
        searched_windows = 0
        for half_m in half_extent_m:
            half_bu = contract.scale.to_blender_units(half_m)
            for x, y in centers[:maximum_centers]:
                searched_windows += 1
                rectangle = box(x - half_bu, y - half_bu, x + half_bu, y + half_bu)
                certificate, detail = _certify_local_rectangle_verified(
                    domain, rectangle, evidence, region["region_id"], contract, numerics,
                    support_source_faces=support_source_faces[domain.floor.floor_id],
                    evidence_content_sha256=evidence_digest,
                    enclosure_cache=enclosure_cache,
                    maximum_enclosure_pair_checks=maximum_enclosure_pair_checks,
                    self_intersection_numeric_epsilon_bu=self_intersection_numeric_epsilon_bu,
                )
                if certificate is not None:
                    found = certificate
                    break
                if detail["reason"] != "OUTSIDE_ERODED_APPROVED_SUPPORT":
                    reviews.append(detail)
            if found is not None:
                break
        results.append({
            "walkable_id": domain_id, "region_id": region["region_id"],
            "status": "APPROVED" if found else "REVIEW",
            "certificate": None if found is None else found.model_dump(mode="json"),
            "review_witnesses": reviews[:10],
            "window_search_complete": False,
            "configured_window_search_finished": found is None,
            "search_is_exhaustive_geometric_window_enumeration": False,
            "searched_window_count": searched_windows,
            "available_grid_center_count": len(centers),
        })
        if found:
            approved.append(found.model_dump(mode="json"))
        if len(approved) >= maximum_approved:
            break
    return {
        "schema_version": "local-physical-scope-discovery-v1",
        "source_sha256": source, "source_evidence_content_sha256": evidence_digest,
        "approved_scope_count": len(approved), "approved_scopes": approved,
        "regions": results, "global_building_authority_approved": False,
        "source_geometry_reclassified": False, "gt_used": False,
        "formal_cases_started": False,
        "search_configuration": {
            "half_extent_m": list(half_extent_m),
            "maximum_centers_per_extent": maximum_centers,
            "maximum_approved_scopes": maximum_approved,
            "center_grid_points_per_axis": 9,
            "numerics": numerics.model_dump(mode="json"),
            "maximum_enclosure_pair_checks": maximum_enclosure_pair_checks,
            "self_intersection_numeric_epsilon_bu": self_intersection_numeric_epsilon_bu,
            "termination": "MAX_APPROVED_SCOPES_REACHED" if len(approved) >= maximum_approved
            else "CONFIGURED_WINDOW_SEARCH_FINISHED",
            "exhaustive_geometric_window_search": False,
        },
    }


@dataclass(frozen=True, slots=True)
class RestrictedLocalPhysicalProvider:
    """A local certificate is unusable beyond its exact registered footpoint domain."""

    certificate: LocalScopeCertificate
    domain: WalkableClearanceDomain
    contract: PhysicalPolicyContract
    expected_source_sha256: InitVar[str] = field(kw_only=True)
    expected_evidence_content_sha256: InitVar[str] = field(kw_only=True)
    expected_certificate_content_sha256: InitVar[str] = field(kw_only=True)

    def __post_init__(
        self, expected_source_sha256: str, expected_evidence_content_sha256: str,
        expected_certificate_content_sha256: str,
    ) -> None:
        certificate = LocalScopeCertificate.model_validate(self.certificate)
        for value, label in (
            (expected_source_sha256, "expected source hash"),
            (expected_evidence_content_sha256, "expected source evidence hash"),
            (expected_certificate_content_sha256, "expected authority certificate hash"),
        ):
            _expected_digest(value, label)
        if (
            certificate.source_sha256 != expected_source_sha256
            or self.domain.source_sha256 != expected_source_sha256
            or certificate.evidence_content_sha256 != expected_evidence_content_sha256
            or content_sha256(certificate.model_dump(mode="json"))
            != expected_certificate_content_sha256
        ):
            raise ValueError("local physical provider source/evidence/certificate SHA-256 mismatch")
        _check_domain_contract(self.domain, self.contract)
        self.contract.scale.require_source_sha256(certificate.source_sha256)
        if (
            certificate.support_union_sha256 != hashlib.sha256(self.domain.union_wkb).hexdigest()
            or certificate.policy_content_sha256
            != content_sha256(self.contract.policy.model_dump(mode="json"))
            or certificate.support_surface_ids != self.domain.surface_ids
            or certificate.floor_id != self.domain.floor.floor_id
            or certificate.domain_content_sha256 != local_domain_content_sha256(self.domain)
            or certificate.approval_id != self.contract.runtime.approval_id
        ):
            raise ValueError("local physical certificate domain/policy binding mismatch")
        low, high = certificate.footpoint_bounds_bu
        rectangle = box(low[0], low[1], high[0], high[1])
        actual_band = self.domain.actual_contact_height_band(rectangle)
        if actual_band is None or low[2] < actual_band[0] or high[2] > actual_band[1]:
            raise ValueError("local certificate extends outside actual source contact height")
        united = from_wkb(self.domain.union_wkb)
        if (
            not united.covers(rectangle)
            or united.boundary.distance(rectangle) < self.domain.required_clearance_bu
        ):
            raise ValueError("local certificate extends outside eroded approved support")
        object.__setattr__(self, "certificate", certificate)

    def validate_polyline(self, points_bu: tuple[Coordinate, ...]) -> bool:
        if len(points_bu) < 2:
            raise ValueError("local physical path requires at least two footpoints")
        low, high = self.certificate.footpoint_bounds_bu
        for point in points_bu:
            if len(point) != 3 or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) for value in point
            ):
                raise ValueError("local physical footpoints must contain three finite coordinates")
            if any(point[axis] < low[axis] or point[axis] > high[axis] for axis in range(3)):
                raise GeometryAuthorityError(("OUTSIDE_APPROVED_LOCAL_PHYSICAL_DOMAIN",))
        for start, end in pairwise(points_bu):
            if not self.domain.validate_segment(start, end).valid:
                raise GeometryAuthorityError(("OFF_APPROVED_BODY_CLEAR_WALKABLE",))
        return True
