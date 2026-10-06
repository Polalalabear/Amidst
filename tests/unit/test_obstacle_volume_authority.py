"""Component completeness, collision authority and aperture ambiguity regressions."""

from __future__ import annotations

import copy

import pytest

from amidst.architectural_scale import ArchitecturalScale
from amidst.obstacle_volume_authority import (
    approved_obstacle_surfaces,
    component_self_intersection,
    component_topology,
    content_sha256,
    region_patches,
    review_obstacle_volumes,
    review_portal_clearance,
    validate_source_evidence,
)
from amidst.physical_authority import PhysicalPolicy
from amidst.scene_geometry import Authority, FloorAuthority

SOURCE = "0" * 64
VERTICES = (
    (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
    (0.0, 0.0, 10.0), (10.0, 0.0, 10.0), (10.0, 10.0, 10.0), (0.0, 10.0, 10.0),
)
TRIANGLES = (
    (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
    (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
)


def scale() -> ArchitecturalScale:
    return ArchitecturalScale(
        source_asset_sha256=SOURCE, metres_per_blender_unit=0.0247,
        authority=Authority.APPROVED, approval_id="human-model-scale",
        evidence_ids=("human-scale",),
    )


def policy() -> PhysicalPolicy:
    return PhysicalPolicy(
        policy_id="approved-policy", config_version="v1", authority=Authority.APPROVED,
        body_model="UPRIGHT_CYLINDER", trajectory_reference="FLOOR_CONTACT_POINT",
        body_radius_m=0.30, body_height_m=1.70, body_clearance_m=0.05,
        portal_horizontal_clearance_m=0.05, portal_vertical_clearance_m=0.10,
        collision_tolerance_m=0.001, clearance_comparison="MINIMUM_INCLUSIVE",
        collision_comparison="CONTACT_INCLUSIVE", approval_id="human-policy",
        evidence_ids=("human-policy",),
    )


def floor() -> FloorAuthority:
    return FloorAuthority(
        floor_id="1F", point=(0.0, 0.0, 0.0), normal=(0.0, 0.0, 1.0),
        authority=Authority.APPROVED, approval_id="source-floor", evidence_ids=("floor",),
    )


def fixture() -> tuple[dict, dict, dict]:
    audit = {
        "source_sha256": SOURCE,
        "objects": [{
            "object": "OBSTACLE_1", "vertices": [[-1., -1., 0.], [11., -1., 0.],
                                                   [11., 11., 0.], [-1., 11., 0.]],
            "triangles": [[0, 1, 2], [0, 2, 3]],
            "custom_properties": {"semantic_class": "OBSTACLE", "floor_id": "1F"},
        }],
    }
    mesh = {
        "source_object_id": "Cube.030",  # Explicit geometry binding, never name classification.
        "vertices": [list(point) for point in VERTICES],
        "triangles": [list(triangle) for triangle in TRIANGLES],
        "triangle_source_face_indices": list(range(12)),
        "source_face_indices": list(range(12)),
        "evaluated_vertex_count": 8, "evaluated_triangle_count": 12,
        "evaluated_polygon_count": 12, "full_object_exported": True,
        "components": [{
            "component_id": "component-00000000", "source_triangle_indices": list(range(12)),
            "source_vertex_indices": list(range(8)), "triangle_count": 12,
            "bounds_bu": {"minimum": [0., 0., 0.], "maximum": [10., 10., 10.]},
            "full_component_exported": True,
        }],
        "hidden_render": True, "hidden_viewport": True, "viewport_disabled": False,
        "collection_disabled": False,
        "semantic_role": "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY",
    }
    mesh["mesh_id"] = content_sha256({key: mesh[key] for key in
                                     ("source_object_id", "vertices", "triangles",
                                      "triangle_source_face_indices")})
    mesh["geometry_sha256"] = content_sha256(mesh)
    authority = scale().model_dump(mode="json")
    evidence = {
        "schema_version": "physical-policy-source-evidence-v1", "source_sha256": SOURCE,
        "source_preserved": True, "saved": False, "rendered": False,
        "geometry_modified": False, "audit_content_sha256": content_sha256(audit),
        "architectural_scale": authority,
        "architectural_scale_content_sha256": content_sha256(authority),
        "policy": {
            "gt_used": False, "roles_inferred_from_names": False, "bounds_are_colliders": False,
            "hidden_geometry_included": True, "missing_triangles_certify_clearance": False,
            "source_object_geometry_complete": True,
            "component_enclosure_candidates_included": True,
            "region_complete_means_exhaustive_selection_only": True,
        },
        "meshes": [mesh],
        "regions": [{
            "region_id": "OBSTACLE_1", "kind": "OBSTACLE_COMPONENT_SELECTION",
            "annotation_object_id": "OBSTACLE_1", "selection_complete": True,
            "selections": [{"mesh_id": mesh["mesh_id"], "source_object_id": "Cube.030",
                            "source_triangle_indices": list(range(12)),
                            "component_ids": ["component-00000000"]}],
        }],
    }
    roles = {
        "schema_version": "geometry-role-authorization-v1", "source_sha256": SOURCE,
        "authority_scope": "SEMANTIC_ROLE_ONLY", "approval_id": "approved-obstacle-role",
        "approved_obstacle_ids": ["OBSTACLE_1"],
    }
    return evidence, audit, roles


def test_closed_source_component_can_approve_positive_collider_but_not_whole_obstacle() -> None:
    evidence, audit, roles = fixture()
    report = review_obstacle_volumes(evidence, audit, roles, scale=scale(), policy=policy(),
                                    floors=(floor(),))
    surfaces = approved_obstacle_surfaces(report)
    assert len(surfaces) == 1
    assert surfaces[0].source_object_id == "Cube.030"
    assert set(surfaces[0].vertices) == set(VERTICES)
    assert report["obstacles"][0]["whole_obstacle_authority"] == "HUMAN_REVIEW"
    assert report["free_space_certified"] is False
    component = report["obstacles"][0]["components"][0]
    assert component["self_intersection"]["status"] == "PASS"
    assert component["hidden_render"] is True
    assert component["topology"]["signed_volume_m3"] == pytest.approx(1000 * 0.0247**3)


def test_pending_floor_cannot_promote_geometry() -> None:
    evidence, audit, roles = fixture()
    report = review_obstacle_volumes(evidence, audit, roles, scale=scale(), policy=policy())
    assert report["approved_component_count"] == 0
    assert "SOURCE_FLOOR_AUTHORITY_PENDING" in (
        report["obstacles"][0]["components"][0]["unresolved_reasons"]
    )


def test_open_source_geometry_not_extruded_to_volume() -> None:
    result = component_topology(VERTICES, TRIANGLES[:-1])
    assert not result["closed_consistent_nonzero_volume"]
    assert result["boundary_edge_count"] == 3


def test_inconsistent_winding_is_rejected() -> None:
    result = component_topology(VERTICES, (tuple(reversed(TRIANGLES[0])), *TRIANGLES[1:]))
    assert not result["closed_consistent_nonzero_volume"]
    assert result["inconsistent_winding_edge_count"] == 3


def test_batched_topology_retains_translation_orientation_and_degenerate_guards() -> None:
    shifted = tuple((x + 1_000_000., y - 500_000., z + 200_000.) for x, y, z in VERTICES)
    result = component_topology(shifted, TRIANGLES)
    assert result["closed_consistent_nonzero_volume"]
    assert result["signed_volume_bu3"] == pytest.approx(1000.)
    reversed_faces = tuple(tuple(reversed(triangle)) for triangle in TRIANGLES)
    reversed_result = component_topology(shifted, reversed_faces)
    assert reversed_result["closed_consistent_nonzero_volume"]
    assert reversed_result["signed_volume_bu3"] == pytest.approx(-1000.)
    broken = component_topology(shifted, (*TRIANGLES, (0, 0, 1)))
    assert broken["degenerate_triangle_count"] == 1
    assert not broken["closed_consistent_nonzero_volume"]


def test_nonadjacent_self_intersection_is_detected() -> None:
    moved = tuple((x + 5., y + 5., z + 5.) for x, y, z in VERTICES)
    triangles = TRIANGLES + tuple(tuple(index + 8 for index in triangle) for triangle in TRIANGLES)
    result = component_self_intersection((*VERTICES, *moved), triangles)
    assert result["status"] == "REJECTED"
    assert result["reason"] == "NONADJACENT_SELF_INTERSECTION"


def test_guard_budget_is_review_not_approval() -> None:
    moved = tuple((x + 5., y + 5., z + 5.) for x, y, z in VERTICES)
    triangles = TRIANGLES + tuple(tuple(index + 8 for index in triangle) for triangle in TRIANGLES)
    result = component_self_intersection((*VERTICES, *moved), triangles, maximum_pair_checks=1)
    assert result["status"] in {"REJECTED", "HUMAN_REVIEW"}
    assert result["status"] != "PASS"


def _folded_closed_fan() -> tuple[tuple, tuple]:
    # An octahedron's combinatorial manifold is unchanged, but the equatorial
    # vertex folds into another face. Edges and winding alone still pass.
    vertices = ((0., 0., 1.), (0., 0., -1.), (1., 0., 0.), (0., 1., 0.),
                (.5, .5, 0.), (0., -1., 0.))
    triangles = ((0, 2, 3), (0, 3, 4), (0, 4, 5), (0, 5, 2),
                 (1, 3, 2), (1, 4, 3), (1, 5, 4), (1, 2, 5))
    return vertices, triangles


def test_closed_consistent_shared_edge_coplanar_fold_is_not_certified() -> None:
    vertices, triangles = _folded_closed_fan()
    assert component_topology(vertices, triangles)["closed_consistent_nonzero_volume"]
    result = component_self_intersection(vertices, triangles)
    assert result["status"] == "REJECTED"
    assert result["reason"] == "SHARED_FEATURE_SELF_INTERSECTION"
    assert result["triangle_indices"] == [0, 1]


def test_closed_consistent_shared_vertex_remote_intersection_is_not_certified() -> None:
    vertices, faces = _folded_closed_fan()
    # The first two faces share only the north vertex, and intersect along an
    # additional segment. Their planes are noncoplanar.
    triangles = (faces[0], faces[2], faces[1], *faces[3:])
    assert component_topology(vertices, triangles)["closed_consistent_nonzero_volume"]
    result = component_self_intersection(vertices, triangles)
    assert result["status"] == "REJECTED"
    assert result["reason"] == "SHARED_FEATURE_SELF_INTERSECTION"
    assert result["triangle_indices"] == [0, 1]


def test_exact_guard_budget_exhaustion_is_review() -> None:
    vertices = ((0., 0., 0.), (10., 0., 0.), (0., 10., 0.),
                (6., 6., 0.), (10., 6., 0.), (6., 10., 0.),
                (7., 7., 0.), (10., 7., 0.), (7., 10., 0.))
    triangles = ((0, 1, 2), (3, 4, 5), (6, 7, 8))
    result = component_self_intersection(vertices, triangles, maximum_pair_checks=1)
    assert result["status"] == "HUMAN_REVIEW"
    assert result["reason"] == "SELF_INTERSECTION_GUARD_BUDGET"
    assert result["pair_checks"] == 1


@pytest.mark.parametrize("field,value", [
    ("source_sha256", "1" * 64), ("saved", True), ("geometry_modified", True),
    ("source_preserved", False),
])
def test_source_integrity_and_bindings_fail_closed(field: str, value: object) -> None:
    evidence, _, _ = fixture()
    evidence[field] = value
    with pytest.raises(ValueError, match="unchanged source"):
        validate_source_evidence(evidence, expected_source_sha256=SOURCE)


def test_forged_complete_component_partition_rejected() -> None:
    evidence, _, _ = fixture()
    mesh = evidence["meshes"][0]
    mesh["components"][0]["source_triangle_indices"] = list(range(11))
    mesh["components"][0]["triangle_count"] = 11
    mesh["geometry_sha256"] = content_sha256({key: value for key, value in mesh.items()
                                             if key != "geometry_sha256"})
    with pytest.raises(ValueError, match="partition"):
        validate_source_evidence(evidence, expected_source_sha256=SOURCE)


def test_original_face_refs_preserved_in_region_adapter() -> None:
    evidence, _, _ = fixture()
    validate_source_evidence(evidence, expected_source_sha256=SOURCE)
    patch = region_patches(evidence, "OBSTACLE_1")[0]
    assert patch["source_vertex_indices"] == list(range(8))
    assert patch["source_triangle_indices"] == list(range(12))
    assert patch["source_face_indices"] == list(range(12))
    assert patch["vertices"] == evidence["meshes"][0]["vertices"]
    assert patch["hidden_render"] is True
    with pytest.raises(ValueError, match="unknown"):
        region_patches(evidence, "missing")


def test_enclosing_source_component_is_retained_without_selected_surface_triangles() -> None:
    evidence, _, _ = fixture()
    selection = evidence["regions"][0]["selections"][0]
    selection["source_triangle_indices"] = []
    validate_source_evidence(evidence, expected_source_sha256=SOURCE)
    assert selection["component_ids"] == ["component-00000000"]
    assert region_patches(evidence, "OBSTACLE_1") == []


def test_old_export_without_enclosure_candidates_cannot_certify_physics() -> None:
    evidence, _, _ = fixture()
    del evidence["policy"]["component_enclosure_candidates_included"]
    with pytest.raises(ValueError, match="invent space"):
        validate_source_evidence(evidence, expected_source_sha256=SOURCE)


def test_partial_footprint_binding_does_not_approve_whole_source_component() -> None:
    evidence, audit, roles = fixture()
    audit["objects"][0]["vertices"][1][0] = 5.
    audit["objects"][0]["vertices"][2][0] = 5.
    evidence["audit_content_sha256"] = content_sha256(audit)
    report = review_obstacle_volumes(evidence, audit, roles, scale=scale(), policy=policy(),
                                    floors=(floor(),))
    assert report["approved_component_count"] == 0
    assert report["obstacles"][0]["components"][0]["footprint_contained"] is False


def test_region_selection_does_not_implicitly_certify_empty_space() -> None:
    evidence, audit, roles = fixture()
    evidence["regions"][0]["selection_complete"] = False
    report = review_obstacle_volumes(evidence, audit, roles, scale=scale(), policy=policy(),
                                    floors=(floor(),))
    assert report["approved_component_count"] == 1
    assert report["obstacles"][0]["source_selection_complete"] is False
    assert "SOURCE_REGION_SELECTION_INCOMPLETE" in report["obstacles"][0]["unresolved_reasons"]
    assert report["free_space_certified"] is False


def test_portal_review_preserves_ambiguity_and_stricter_clearance_not_sum() -> None:
    evidence, audit, _ = fixture()
    audit["objects"].append({
        "object": "PORTAL_1", "vertices": [[0., 0., -1.], [40., 0., -1.],
                                              [40., 10., 100.], [0., 10., 100.]],
        "triangles": [[0, 1, 2], [0, 2, 3]],
        "custom_properties": {"semantic_class": "PORTAL", "floor_id": "1F",
                              "portal_normal": [0., 1., 0.]},
    })
    evidence["audit_content_sha256"] = content_sha256(audit)
    report = review_portal_clearance(evidence, audit, scale=scale(), policy=policy())
    assert report["required_width_m"] == pytest.approx(.70)
    assert report["required_height_m"] == pytest.approx(1.80)
    assert report["pair_count"] == 1
    assert report["pairs"][0]["actual_source_bound_opening"] is None
    assert report["pairs"][0]["physical_body_feasibility"] == "UNDETERMINED_REVIEW"
    assert report["pairs"][0]["source_face_review"][0]["source_face_indices"] == list(range(12))
    no_normal = copy.deepcopy(audit)
    del no_normal["objects"][1]["custom_properties"]["portal_normal"]
    evidence["audit_content_sha256"] = content_sha256(no_normal)
    report = review_portal_clearance(evidence, no_normal, scale=scale(), policy=policy())
    assert "PORTAL_NORMAL_NOT_DECLARED" in report["pairs"][0]["remaining_decisions"]
