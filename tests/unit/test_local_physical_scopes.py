"""Source-bound restricted-domain guards, using synthetic engineering artifacts only."""

import math
from dataclasses import replace
from typing import Any

import pytest
from pydantic import ValidationError
from shapely.geometry import Polygon, box

from amidst.architectural_scale import ArchitecturalScale
from amidst.local_physical_scopes import (
    LocalScopeCertificate,
    RestrictedLocalPhysicalProvider,
    certify_local_rectangle,
    discover_local_scopes,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_authority import PhysicalPolicy
from amidst.physical_collision import CollisionNumerics
from amidst.physical_policy_contract import PhysicalPolicyContract, PhysicalPolicyRuntime
from amidst.scene_geometry import (
    Authority,
    FloorAuthority,
    GeometryAuthorityError,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
)
from amidst.walkable_clearance import WalkableClearanceDomain

SOURCE = "e" * 64
APPROVAL = "SYNTHETIC_TEST_ONLY_NOT_BUILDING_APPROVAL"
FLOOR_OBJECT = "SYNTHETIC_EXPLICIT_SOURCE_FLOOR"
REGION = "BODY:synthetic-walk"


def _contract() -> PhysicalPolicyContract:
    policy = PhysicalPolicy(
        policy_id="synthetic-body", config_version="synthetic-source-proof-v1",
        authority=Authority.APPROVED, body_model="UPRIGHT_CYLINDER",
        trajectory_reference="FLOOR_CONTACT_POINT", body_radius_m=.30, body_height_m=1.70,
        body_clearance_m=.05, portal_horizontal_clearance_m=.05,
        portal_vertical_clearance_m=.10, collision_tolerance_m=.001,
        clearance_comparison="MINIMUM_INCLUSIVE", collision_comparison="CONTACT_INCLUSIVE",
        approval_id=APPROVAL, evidence_ids=("SYNTHETIC_ENGINEERING_SETTING",),
    )
    scale = ArchitecturalScale(
        source_asset_sha256=SOURCE, metres_per_blender_unit=1., authority=Authority.APPROVED,
        approval_id=APPROVAL, evidence_ids=("SYNTHETIC_COORDINATE_SCALE",),
    )
    runtime = PhysicalPolicyRuntime(
        source_asset_sha256=SOURCE, authority="APPROVED", approval_id=APPROVAL,
        policy_config="synthetic-policy.json", architectural_scale_config="synthetic-scale.json",
        legal_support_contact="APPROVED_SUPPORT_ONLY", portal_clearance_combination="MAXIMUM",
        stair_direction="BIDIRECTIONAL", navigation_allowed_roles=("WALKABLE", "STAIR"),
        navigation_outside_approved_support="FORBIDDEN",
        walkable_representation="RAW_SUPPORT_SURFACE",
        footprint_preprocess="UNION_THEN_EROSION",
    )
    return PhysicalPolicyContract(policy, scale, runtime)


def _floor_geometry() -> tuple[list[list[float]], list[list[int]]]:
    return (
        [[0., 0., 0.], [5., 0., 0.], [10., 0., 0.],
         [0., 10., 0.], [5., 10., 0.], [10., 10., 0.]],
        [[0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4]],
    )


def _domain(
    contract: PhysicalPolicyContract, *, support_raise: float = 0.,
) -> WalkableClearanceDomain:
    points, triangles = _floor_geometry()
    for point in points:
        point[2] += support_raise
    surface = GeometrySurface(
        surface_id="synthetic-support", source_object_id=FLOOR_OBJECT,
        source_face_indices=(0, 1, 2, 3), role=GeometryRole.WALKABLE, floor_ids=("1F",),
        vertices=tuple(tuple(p) for p in points), triangles=tuple(tuple(t) for t in triangles),
        semantic_authority=Authority.APPROVED, physical_authority=Authority.APPROVED,
        support=GeometrySupport.SURFACE, approval_id=APPROVAL,
        evidence_ids=(f"SOURCE_SHA256:{SOURCE}",),
    )
    floor = FloorAuthority(
        floor_id="1F", point=(0., 0., 0.), normal=(0., 0., 1.), authority=Authority.APPROVED,
        approval_id=APPROVAL, evidence_ids=("SYNTHETIC_FLOOR_FACES",),
    )
    return WalkableClearanceDomain.from_surfaces(
        (surface,), floor=floor, scale=contract.scale, policy=contract.policy,
        expected_source_sha256=SOURCE,
    )


def _mesh(name: str, points: list[list[float]], triangles: list[list[int]]) -> dict[str, Any]:
    ids = list(range(len(triangles)))
    geometry = {
        "source_object_id": name, "vertices": points, "triangles": triangles,
        "triangle_source_face_indices": ids,
    }
    bounds = {
        "minimum": [min(p[axis] for p in points) for axis in range(3)],
        "maximum": [max(p[axis] for p in points) for axis in range(3)],
    }
    result = {
        **geometry, "mesh_id": content_sha256(geometry), "full_object_exported": True,
        "semantic_role": "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY",
        "evaluated_vertex_count": len(points), "evaluated_triangle_count": len(triangles),
        "evaluated_polygon_count": len(triangles), "source_face_indices": ids,
        "hidden_render": False, "hidden_viewport": False, "viewport_disabled": False,
        "collection_disabled": False, "components": [{
            "component_id": "synthetic-component", "source_triangle_indices": ids,
            "source_vertex_indices": sorted({i for t in triangles for i in t}),
            "triangle_count": len(triangles), "full_component_exported": True,
            "bounds_bu": bounds,
        }],
    }
    result["geometry_sha256"] = content_sha256(result)
    return result


def _atlas(
    contract: PhysicalPolicyContract, extras: list[dict[str, Any]] | None = None,
    *, floor_present: bool = True, floor_raise: float = 0.,
) -> dict[str, Any]:
    points, triangles = _floor_geometry()
    for point in points:
        point[2] += floor_raise
    meshes = [_mesh(FLOOR_OBJECT, points, triangles)] if floor_present else []
    meshes.extend(extras or [])
    return {
        "schema_version": "physical-policy-source-evidence-v1", "source_sha256": SOURCE,
        "source_preserved": True, "saved": False, "rendered": False, "geometry_modified": False,
        "architectural_scale": contract.scale.model_dump(mode="json"),
        "architectural_scale_content_sha256": content_sha256(
            contract.scale.model_dump(mode="json"),
        ),
        "policy": {
            "gt_used": False, "roles_inferred_from_names": False, "bounds_are_colliders": False,
            "hidden_geometry_included": True, "missing_triangles_certify_clearance": False,
            "source_object_geometry_complete": True,
            "component_enclosure_candidates_included": True,
            "region_complete_means_exhaustive_selection_only": True,
        },
        "meshes": meshes, "regions": [{
            "region_id": REGION, "kind": "FULL_BODY_CONTEXT", "floor_id": "1F",
            "annotation_object_id": "synthetic-walk", "selection_complete": True,
            "bounds_bu": {"minimum": [-1., -1., -1.], "maximum": [11., 11., 5.]},
            "selections": [{
                "mesh_id": mesh["mesh_id"], "source_object_id": mesh["source_object_id"],
                "source_triangle_indices": list(range(len(mesh["triangles"]))),
                "component_ids": ["synthetic-component"],
            } for mesh in meshes],
        }],
    }


def _numerics(queries: int = 64, iterations: int = 128) -> CollisionNumerics:
    return CollisionNumerics(
        distance_error_budget_m=1e-9, maximum_distance_iterations=iterations,
        maximum_triangles_per_segment=queries,
    )


def _certify(
    evidence: dict[str, Any], contract: PhysicalPolicyContract,
    *, rectangle: Polygon | None = None, queries: int = 64, iterations: int = 128,
    enclosure_pairs: int = 250000,
    domain: WalkableClearanceDomain | None = None,
) -> tuple[LocalScopeCertificate | None, dict[str, Any]]:
    return certify_local_rectangle(
        _domain(contract) if domain is None else domain,
        box(2., 2., 8., 8.) if rectangle is None else rectangle,
        evidence, REGION, contract, _numerics(queries, iterations),
        support_source_faces=frozenset((FLOOR_OBJECT, index) for index in range(4)),
        evidence_content_sha256=content_sha256(evidence),
        maximum_enclosure_pair_checks=enclosure_pairs,
    )


def _approved() -> tuple[
    LocalScopeCertificate, WalkableClearanceDomain, PhysicalPolicyContract, dict[str, Any],
]:
    contract = _contract()
    evidence = _atlas(contract)
    certificate, detail = _certify(evidence, contract)
    assert certificate is not None, detail
    return certificate, _domain(contract), contract, evidence


def _provider(
    certificate: LocalScopeCertificate, domain: WalkableClearanceDomain,
    contract: PhysicalPolicyContract, evidence: dict[str, Any],
    **overrides: str,
) -> RestrictedLocalPhysicalProvider:
    guards = {
        "expected_source_sha256": SOURCE,
        "expected_evidence_content_sha256": content_sha256(evidence),
        "expected_certificate_content_sha256": content_sha256(
            certificate.model_dump(mode="json"),
        ),
    }
    guards.update(overrides)
    return RestrictedLocalPhysicalProvider(certificate, domain, contract, **guards)


def test_clear_source_bound_rectangle_and_internal_support_seam_are_certified() -> None:
    certificate, domain, contract, evidence = _approved()
    assert certificate.source_triangles_screened == 4
    assert certificate.legal_support_triangles == 4
    assert certificate.exact_distance_queries == 0
    assert certificate.source_geometry_reclassified is False
    provider = _provider(certificate, domain, contract, evidence)
    assert provider.validate_polyline(((4., 5., 0.), (6., 5., 0.)))
    assert certificate.coverage == "COMPLETE_RESTRICTED_FOOTPOINT_DOMAIN"
    assert certificate.formal_case1_3_started is False


def test_scope_foot_height_band_uses_actual_source_instead_of_double_tolerance() -> None:
    contract = _contract()
    domain = _domain(contract, support_raise=.0006)
    evidence = _atlas(contract, floor_raise=.0006)
    certificate, detail = _certify(evidence, contract, domain=domain)
    assert certificate is not None, detail
    low, high = certificate.footpoint_bounds_bu
    assert low[2] == pytest.approx(-.0004)
    assert high[2] == pytest.approx(.0016)
    provider = _provider(certificate, domain, contract, evidence)
    assert provider.validate_polyline(((4., 5., .0006), (6., 5., .0006)))
    with pytest.raises(GeometryAuthorityError, match="OUTSIDE_APPROVED_LOCAL"):
        provider.validate_polyline(((4., 5., -.001), (6., 5., -.001)))


def test_absent_source_and_wrong_expected_evidence_hash_are_rejected() -> None:
    contract = _contract()
    with pytest.raises(ValueError, match="source SHA"):
        _certify({}, contract)
    evidence = _atlas(contract)
    with pytest.raises(ValueError, match="evidence content SHA"):
        certify_local_rectangle(
            _domain(contract), box(2., 2., 8., 8.), evidence, REGION, contract, _numerics(),
            support_source_faces=frozenset(), evidence_content_sha256="f" * 64,
        )


def test_empty_exhaustive_selection_cannot_certify_an_absence_of_geometry() -> None:
    contract = _contract()
    certificate, detail = _certify(_atlas(contract, floor_present=False), contract)
    assert certificate is None
    assert detail["reason"] == "NO_EXHAUSTIVE_SOURCE_SUPPORT_EVIDENCE"


def test_source_mesh_content_mutation_fails_before_physical_screening() -> None:
    contract = _contract()
    evidence = _atlas(contract)
    evidence["meshes"][0]["vertices"][0][0] = 1.
    with pytest.raises(ValueError, match="geometry or complete-object"):
        _certify(evidence, contract)


def test_source_envelope_must_cover_the_whole_body_not_only_foot_rectangle() -> None:
    contract = _contract()
    evidence = _atlas(contract)
    evidence["regions"][0]["bounds_bu"]["maximum"][2] = .5
    certificate, detail = _certify(evidence, contract)
    assert certificate is None
    assert detail["reason"] == "SOURCE_REGION_DOES_NOT_COVER_BODY_ENVELOPE"


def test_complete_rectangle_screen_catches_corner_collision_away_from_center() -> None:
    wall = _mesh("SYNTHETIC_UNKNOWN_CORNER_WALL", [
        [2.1, 1., 0.], [2.1, 9., 0.], [2.1, 9., 3.], [2.1, 1., 3.],
    ], [[0, 1, 2], [0, 2, 3]])
    contract = _contract()
    certificate, detail = _certify(_atlas(contract, [wall]), contract)
    assert certificate is None
    assert detail["reason"] == "UNCLASSIFIED_SOURCE_BODY_CONTACT"
    assert detail["source_object_id"] == "SYNTHETIC_UNKNOWN_CORNER_WALL"


def _unknown_enclosure() -> dict[str, Any]:
    points = [[-100., -100., -100.], [100., -100., -100.], [100., 100., -100.],
              [-100., 100., -100.], [-100., -100., 100.], [100., -100., 100.],
              [100., 100., 100.], [-100., 100., 100.]]
    triangles = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
                 [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                 [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
    return _mesh("SYNTHETIC_UNKNOWN_ENCLOSURE", points, triangles)


def _enclosure_atlas(contract: PhysicalPolicyContract) -> dict[str, Any]:
    evidence = _atlas(contract, [_unknown_enclosure()])
    evidence["regions"][0]["selections"][-1]["source_triangle_indices"] = []
    return evidence


def test_unknown_closed_component_enclosing_domain_blocks_even_without_boundary_triangles() -> None:
    contract = _contract()
    evidence = _enclosure_atlas(contract)
    certificate, detail = _certify(evidence, contract)
    assert certificate is None
    assert detail["reason"] == "INSIDE_UNCLASSIFIED_CLOSED_COMPONENT"


def test_enclosure_self_intersection_budget_refuses_ambiguous_closed_geometry() -> None:
    contract = _contract()
    certificate, detail = _certify(_enclosure_atlas(contract), contract, enclosure_pairs=1)
    assert certificate is None
    assert detail["reason"] == "UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN"
    assert detail["enclosure_evidence"]["self_intersection"]["reason"] == (
        "SELF_INTERSECTION_GUARD_BUDGET"
    )


def test_uncertain_signed_winding_result_cannot_certify_empty_space(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("amidst.local_physical_scopes.point_inside_closed_mesh", lambda *args: None)
    contract = _contract()
    certificate, detail = _certify(_enclosure_atlas(contract), contract)
    assert certificate is None
    assert detail["reason"] == "UNKNOWN_CLOSED_VOLUME_CONTAINMENT_UNCERTAIN"


def test_degenerate_triangle_in_body_envelope_is_structured_review() -> None:
    degenerate = _mesh("SYNTHETIC_INVALID_FACE", [[5., 5., 1.], [6., 5., 1.], [7., 5., 1.]],
                       [[0, 1, 2]])
    contract = _contract()
    certificate, detail = _certify(_atlas(contract, [degenerate]), contract)
    assert certificate is None
    assert detail["reason"] == "DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE"
    assert detail["source_object_id"] == "SYNTHETIC_INVALID_FACE"
    assert detail["source_face_index"] == 0


def test_degenerate_triangle_outside_body_envelope_does_not_become_a_fake_collider() -> None:
    degenerate = _mesh("SYNTHETIC_DISTANT_INVALID_FACE", [[50., 50., 1.], [51., 50., 1.],
                                                        [52., 50., 1.]], [[0, 1, 2]])
    contract = _contract()
    certificate, _ = _certify(_atlas(contract, [degenerate]), contract)
    assert certificate is not None
    assert certificate.exact_distance_queries == 0


def test_query_budget_is_review_instead_of_partial_approval() -> None:
    overhead = _mesh("SYNTHETIC_OVERHEAD_MARGIN", [[1., 1., 1.751], [9., 1., 1.751],
                                                 [9., 9., 1.751], [1., 9., 1.751]],
                     [[0, 1, 2], [0, 2, 3]])
    contract = _contract()
    certificate, detail = _certify(_atlas(contract, [overhead]), contract, queries=1)
    assert certificate is None
    assert detail["reason"] == "LOCAL_BODY_QUERY_BUDGET_EXCEEDED"


def test_uncertain_distance_and_incomplete_source_selection_are_review() -> None:
    wall = _mesh("SYNTHETIC_UNKNOWN_WALL", [[2.3, 1., 0.], [2.3, 9., 0.],
                                          [2.3, 9., 3.]], [[0, 1, 2]])
    contract = _contract()
    certificate, detail = _certify(_atlas(contract, [wall]), contract, iterations=1)
    assert certificate is None
    assert detail["reason"] == "UNCLASSIFIED_SOURCE_DISTANCE_UNCERTAIN"
    incomplete = _atlas(contract)
    incomplete["regions"][0]["selection_complete"] = False
    certificate, detail = _certify(incomplete, contract)
    assert certificate is None
    assert detail["reason"] == "FULL_BODY_SOURCE_SELECTION_INCOMPLETE"


def test_evaluation_geometry_and_guessed_roles_are_not_acceptable_source_evidence() -> None:
    contract = _contract()
    evidence = _atlas(contract)
    evidence["policy"]["gt_used"] = True
    with pytest.raises(ValueError, match="cannot infer roles"):
        _certify(evidence, contract)


def test_rectangle_clearance_failure_and_invalid_rectangle_are_distinct() -> None:
    contract = _contract()
    evidence = _atlas(contract)
    certificate, detail = _certify(evidence, contract, rectangle=box(.3499, 2., 8., 8.))
    assert certificate is None
    assert detail["reason"] == "OUTSIDE_ERODED_APPROVED_SUPPORT"
    with pytest.raises(ValueError, match="axis-aligned rectangle"):
        _certify(evidence, contract, rectangle=Polygon([(2., 2.), (8., 2.), (4., 8.)]))


@pytest.mark.parametrize("field", ["expected_source_sha256", "expected_evidence_content_sha256",
                                  "expected_certificate_content_sha256"])
def test_provider_requires_independent_matching_hashes(field: str) -> None:
    certificate, domain, contract, evidence = _approved()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        _provider(certificate, domain, contract, evidence, **{field: "f" * 64})


def test_provider_has_no_unguarded_constructor() -> None:
    certificate, domain, contract, _ = _approved()
    with pytest.raises(TypeError, match="expected_source_sha256"):
        RestrictedLocalPhysicalProvider(certificate, domain, contract)


def test_same_union_with_changed_floor_height_or_clearance_cannot_reuse_certificate() -> None:
    certificate, domain, contract, evidence = _approved()
    changed_height = replace(
        domain, floor=domain.floor.model_copy(update={"point": (0., 0., .0005)}),
    )
    with pytest.raises(ValueError, match="domain/policy binding"):
        _provider(certificate, changed_height, contract, evidence)
    weakened = replace(domain, required_clearance_bu=0., required_clearance_m=0.)
    with pytest.raises(ValueError, match="domain differs"):
        _provider(certificate, weakened, contract, evidence)


def test_modified_certificate_requires_new_independent_authority_digest() -> None:
    certificate, domain, contract, evidence = _approved()
    original_digest = content_sha256(certificate.model_dump(mode="json"))
    forged = certificate.model_copy(update={
        "footpoint_bounds_bu": ((3., 3., -.001), (7., 7., .001)),
    })
    with pytest.raises(ValueError, match="certificate SHA-256 mismatch"):
        _provider(forged, domain, contract, evidence,
                  expected_certificate_content_sha256=original_digest)


def test_even_a_rehashed_certificate_cannot_expand_support_height_or_navigation_domain() -> None:
    certificate, domain, contract, evidence = _approved()
    changed_height = certificate.model_copy(update={
        "footpoint_bounds_bu": ((2., 2., -.001), (8., 8., .1)),
    })
    with pytest.raises(ValueError, match="outside actual source contact height"):
        _provider(changed_height, domain, contract, evidence)
    changed_xy = certificate.model_copy(update={
        "footpoint_bounds_bu": ((.1, 2., -.001), (8., 8., .001)),
    })
    with pytest.raises(ValueError, match="outside eroded approved support"):
        _provider(changed_xy, domain, contract, evidence)


def test_nan_empty_ids_and_reversed_or_empty_bounds_are_schema_rejected() -> None:
    certificate, _, _, _ = _approved()
    for update in (
        {"support_surface_ids": ()}, {"support_surface_ids": (" ",)},
        {"footpoint_bounds_bu": ((2., 2., 0.), (2., 8., 0.))},
        {"footpoint_bounds_bu": ((math.nan, 2., 0.), (8., 8., 0.))},
        {"minimum_other_geometry_gap_m": math.inf}, {"source_triangles_screened": 0},
        {"legal_support_triangles": 0},
    ):
        with pytest.raises(ValidationError):
            LocalScopeCertificate.model_validate(certificate.model_copy(update=update))


def test_provider_refuses_outside_or_non_finite_footpoints() -> None:
    certificate, domain, contract, evidence = _approved()
    provider = _provider(certificate, domain, contract, evidence)
    with pytest.raises(GeometryAuthorityError, match="OUTSIDE_APPROVED_LOCAL"):
        provider.validate_polyline(((1., 5., 0.), (3., 5., 0.)))
    with pytest.raises(ValueError, match="finite"):
        provider.validate_polyline(((math.nan, 5., 0.), (3., 5., 0.)))


def test_discovery_records_configured_budget_without_claiming_exhaustive_windows() -> None:
    contract = _contract()
    evidence = _atlas(contract)
    result = discover_local_scopes(
        {"synthetic-walk": _domain(contract)}, evidence, contract, _numerics(),
        support_source_faces={"1F": frozenset((FLOOR_OBJECT, i) for i in range(4))},
        half_extent_m=(1.,), maximum_centers=1, maximum_approved=1,
    )
    assert result["approved_scope_count"] == 1
    assert result["regions"][0]["window_search_complete"] is False
    assert result["search_configuration"]["maximum_centers_per_extent"] == 1
    assert result["search_configuration"]["termination"] == "MAX_APPROVED_SCOPES_REACHED"
    assert result["global_building_authority_approved"] is False
