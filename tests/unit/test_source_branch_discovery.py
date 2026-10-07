"""Source discovery refuses missing geometry/authority; synthetic engineering only."""

from copy import deepcopy

import pytest
from shapely.geometry import box
from test_local_physical_scopes import FLOOR_OBJECT, REGION, _atlas, _contract, _mesh, _numerics
from test_physical_collision import _cube

from amidst.finalization.source_branch_discovery import (
    body_cell_evidence,
    combine_source_support_patches,
    propose_source_island,
    source_support_patch,
    support_route_evidence,
)
from amidst.obstacle_volume_authority import content_sha256


def _support(atlas: dict, z: float = 0.) -> dict:
    return source_support_patch(
        atlas, source_object_id=FLOOR_OBJECT, floor_z_bu=z,
        query_xy=box(1., 1., 9., 9.), contact_tolerance_bu=.001,
    )


def test_raw_source_contact_does_not_grant_walkable_or_physical_authority() -> None:
    evidence = _atlas(_contract())
    original = deepcopy(evidence)
    support = _support(evidence)
    decision = support_route_evidence(support, ((2., 5., 0.), (8., 5., 0.)), .35)
    assert support["source_face_indices"] == [0, 1, 2, 3]
    assert support["semantic_authority"] == support["physical_authority"] == "HUMAN_REVIEW"
    assert decision["source_support_geometrically_sufficient"] is True
    assert decision["formal_support_pass"] is False
    assert evidence == original


def test_actual_source_height_is_never_flattened_to_the_office_plane() -> None:
    evidence = _atlas(_contract(), floor_raise=2.)
    wrong_height = _support(evidence)
    assert wrong_height["actual_source_triangles"] == []
    assert wrong_height["contact_height_band_bu"] is None
    actual_height = _support(evidence, 2.)
    assert actual_height["contact_height_band_bu"] == (1.999, 2.001)
    assert support_route_evidence(actual_height, ((2., 5., 0.), (8., 5., 0.)), .35)[
        "source_support_geometrically_sufficient"
    ] is False


def test_actual_disk_clearance_rejects_a_centerline_near_the_support_boundary() -> None:
    support = _support(_atlas(_contract()))
    result = support_route_evidence(support, ((.1, 2., 0.), (.1, 8., 0.)), .35)
    assert result["centerline_on_actual_source_union"] is True
    assert result["source_support_geometrically_sufficient"] is False


def test_missing_or_incomplete_raw_source_floor_refuses_discovery() -> None:
    atlas = _atlas(_contract(), floor_present=False)
    with pytest.raises(ValueError, match="complete exact mesh"):
        _support(atlas)
    atlas = _atlas(_contract())
    atlas["meshes"][0]["full_object_exported"] = False
    with pytest.raises(ValueError, match="complete exact mesh"):
        _support(atlas)


def test_body_tube_outside_the_complete_source_region_requires_fresh_evidence() -> None:
    contract = _contract()
    evidence = _atlas(contract)
    result = body_cell_evidence(evidence, REGION, box(10.8, 3., 11., 4.), (0., 0.),
                                _support(evidence), contract, _numerics())
    assert result["source_body_geometry_clear"] is False
    assert result["blockers"] == ["FRESH_EXHAUSTIVE_BODY_SOURCE_SELECTION_REQUIRED"]


def test_actual_source_triangle_establishes_direct_body_obstruction() -> None:
    contract = _contract()
    wall = _mesh("explicit-source-wall", [[5., 0., 0.], [5., 10., 0.],
                                         [5., 10., 3.], [5., 0., 3.]], [[0, 1, 2], [0, 2, 3]])
    evidence = _atlas(contract, [wall])
    result = body_cell_evidence(
        evidence, REGION, box(2., 4.9, 8., 5.1), (0., 0.), _support(evidence), contract,
        _numerics(), obstruction_object_ids=frozenset({"explicit-source-wall"}),
    )
    assert result["actual_source_obstruction_witness_found"] is True
    assert result["source_body_geometry_clear"] is False
    witness = result["source_triangle_failures"][0]
    assert witness["source_object_id"] == "explicit-source-wall"
    assert witness["distance_upper_m"] <= .001
    assert len(witness["actual_source_triangle_bu"]) == 3


def test_boundary_separation_alone_does_not_hide_a_closed_enclosure() -> None:
    contract = _contract()
    cube = _cube()
    points = [[point[0] + 4., point[1] + 4., point[2]] for point in cube["vertices"]]
    enclosed = _mesh("explicit-source-enclosure", points, cube["triangles"])
    evidence = _atlas(contract, [enclosed])
    result = body_cell_evidence(evidence, REGION, box(3., 3., 3.1, 3.1), (0., 0.),
                                _support(evidence), contract, _numerics())
    assert result["continuous_body_triangle_sweep_clear"] is True
    assert result["source_body_geometry_clear"] is False
    assert result["enclosure"]["blockers"][0]["state"] == "INSIDE_SOURCE_VOLUME"


def test_clear_geometry_still_is_not_a_formal_certificate() -> None:
    contract = _contract()
    evidence = _atlas(contract)
    result = body_cell_evidence(evidence, REGION, box(3., 3., 3.1, 7.), (0., 0.),
                                _support(evidence), contract, _numerics())
    assert result["source_body_geometry_clear"] is True
    assert result["formal_certificate"] == "NOT_CERTIFIED"
    assert result["semantic_authority"] == "HUMAN_REVIEW"
    assert result["legal_support_contacts_require_approval"] is True


def test_support_patch_union_keeps_incompatible_source_contact_heights_unusable() -> None:
    low = _support(_atlas(_contract()))
    high = _support(_atlas(_contract(), floor_raise=2.), 2.)
    combined = combine_source_support_patches((low, high))
    assert combined["contact_height_band_bu"][0] > combined["contact_height_band_bu"][1]
    assert support_route_evidence(combined, ((2., 5., 0.), (8., 5., 0.)), .35)[
        "source_support_geometrically_sufficient"
    ] is False


def test_real_two_route_winding_proposal_still_requires_human_semantics() -> None:
    contract = _contract()
    cube = _cube()
    points = [[point[0] + 4., point[1] + 4., point[2]] for point in cube["vertices"]]
    island = _mesh("explicit-source-island", points, cube["triangles"])
    evidence = _atlas(contract, [island])
    component = island["components"][0]
    obstacles = {
        "source_sha256": evidence["source_sha256"],
        "source_evidence_content_sha256": content_sha256(evidence),
        "obstacles": [{"obstacle_id": "explicit-island", "floor_id": "1F", "components": [{
            "status": "APPROVED", "source_object_id": island["source_object_id"],
            "component_id": component["component_id"], "bounds_bu": component["bounds_bu"],
            "source_binding": {"source_mesh_id": island["mesh_id"],
                               "source_geometry_sha256": island["geometry_sha256"]},
        }]}],
    }
    original = deepcopy(evidence)
    result = propose_source_island(
        evidence, obstacles, contract, _numerics(), (), obstacle_id="explicit-island",
        support_source_object_id=FLOOR_OBJECT, floor_z_bu=0., source_body_region_id=REGION,
        landmark_offset_bu=1.,
    )
    assert result["source_physical_candidate_geometry_sufficient"] is True
    assert result["source_route_winding_witness"][
        "two_routes_wind_differently_around_actual_body_obstruction"
    ] is True
    assert result["obstruction_probe_is_common_endpoint_connector"] is True
    assert result["formal_readiness"] is False
    assert result["new_scope_semantics"] == "HUMAN_REVIEW"
    assert result["authority_applied"] is False
    assert evidence == original
    binding = obstacles["obstacles"][0]["components"][0]["source_binding"]
    binding["source_geometry_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="source component geometry binding differs"):
        propose_source_island(evidence, obstacles, contract, _numerics(), (),
                              obstacle_id="explicit-island", support_source_object_id=FLOOR_OBJECT,
                              floor_z_bu=0., source_body_region_id=REGION, landmark_offset_bu=1.)
