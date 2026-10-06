"""Synthetic engineering evidence only; no school physical-authority claim.

Tiny analytic wall/ceiling and closed cube meshes exercise continuous full-body
collision, strict clearance, refusal budgets and filtering before final Top-K.
"""

import inspect
import json
import math
from typing import Any

import numpy as np
import pytest
from pydantic import ValidationError

from amidst.architectural_scale import ArchitecturalScale
from amidst.domain.trajectory import CandidateTrajectory
from amidst.physical_authority import (
    PhysicalAuthorityResolution,
    PhysicalPolicy,
    ReadOnlyPhysicalAuthorityProvider,
    canonical_geometry_sha256,
)
from amidst.physical_collision import (
    CollisionNumerics,
    CylinderCollisionConsumer,
    cylinder_triangle_distance,
    point_inside_closed_mesh,
    prune_before_top_k,
    upright_body_triangle_distance,
)
from amidst.physical_policy_contract import PhysicalPolicyContract, PhysicalPolicyRuntime
from amidst.scene_geometry import Authority, GeometryAuthorityError, SceneGeometrySnapshot

SOURCE = "c" * 64
APPROVAL = "SYNTHETIC_ENGINEERING_TEST_ONLY_NOT_SCHOOL_APPROVAL"


def _policy() -> PhysicalPolicy:
    return PhysicalPolicy(
        policy_id="synthetic-cylinder", config_version="synthetic-engineering-v1",
        authority=Authority.APPROVED, body_model="UPRIGHT_CYLINDER",
        trajectory_reference="FLOOR_CONTACT_POINT", body_radius_m=.30, body_height_m=1.70,
        body_clearance_m=.05, portal_horizontal_clearance_m=.05,
        portal_vertical_clearance_m=.10, collision_tolerance_m=.001,
        clearance_comparison="MINIMUM_INCLUSIVE", collision_comparison="CONTACT_INCLUSIVE",
        approval_id=APPROVAL, evidence_ids=("SYNTHETIC_EXPLICIT_TEST_POLICY",),
    )


def _contract(ratio: float = 1., source: str = SOURCE) -> PhysicalPolicyContract:
    scale = ArchitecturalScale(
        source_asset_sha256=source, metres_per_blender_unit=ratio,
        authority=Authority.APPROVED, approval_id=APPROVAL,
        evidence_ids=("SYNTHETIC_DECLARED_SCALE",),
    )
    runtime = PhysicalPolicyRuntime(
        source_asset_sha256=source, authority="APPROVED", approval_id=APPROVAL,
        policy_config="synthetic-test-policy.json",
        architectural_scale_config="synthetic-scale.json",
        legal_support_contact="APPROVED_SUPPORT_ONLY", portal_clearance_combination="MAXIMUM",
        stair_direction="BIDIRECTIONAL", navigation_allowed_roles=("WALKABLE", "STAIR"),
        navigation_outside_approved_support="FORBIDDEN",
        walkable_representation="RAW_SUPPORT_SURFACE",
        footprint_preprocess="UNION_THEN_EROSION",
    )
    return PhysicalPolicyContract(_policy(), scale, runtime)


def _numerics(*, iterations: int = 128, triangles: int = 64) -> CollisionNumerics:
    return CollisionNumerics(
        distance_error_budget_m=1e-9, maximum_distance_iterations=iterations,
        maximum_triangles_per_segment=triangles,
    )


def _wall(x: float = 0.) -> dict[str, Any]:
    return {
        "surface_id": "synthetic-wall", "source_object_id": "SYNTHETIC_ANALYTIC_WALL",
        "source_face_indices": [0, 1], "role": "WALL", "floor_ids": ["1F"],
        "vertices": [[x, -5., -1.], [x, 5., -1.], [x, 5., 4.], [x, -5., 4.]],
        "triangles": [[0, 1, 2], [0, 2, 3]], "semantic_authority": "APPROVED",
        "physical_authority": "APPROVED", "support": "SURFACE", "blocks_movement": True,
        "occludes_visibility": True, "approval_id": APPROVAL,
        "evidence_ids": ["SYNTHETIC_ANALYTIC_SURFACE"],
    }


def _ceiling(z: float) -> dict[str, Any]:
    surface = _wall()
    surface.update({
        "surface_id": "synthetic-overhead", "source_object_id": "SYNTHETIC_OVERHEAD_SURFACE",
        "vertices": [[-5., -5., z], [5., -5., z], [5., 5., z], [-5., 5., z]],
    })
    return surface


def _cube() -> dict[str, Any]:
    return {
        "surface_id": "synthetic-volume", "source_object_id": "SYNTHETIC_CLOSED_CUBE",
        "source_face_indices": list(range(12)), "role": "OBSTACLE", "floor_ids": ["1F"],
        "vertices": [[-2., -2., -1.], [2., -2., -1.], [2., 2., -1.], [-2., 2., -1.],
                     [-2., -2., 3.], [2., -2., 3.], [2., 2., 3.], [-2., 2., 3.]],
        "triangles": [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
                      [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
                      [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]],
        "semantic_authority": "APPROVED", "physical_authority": "APPROVED",
        "support": "VOLUME", "blocks_movement": True, "occludes_visibility": True,
        "approval_id": APPROVAL, "evidence_ids": ["SYNTHETIC_CLOSED_MANIFOLD"],
    }


def _provider(
    surfaces: list[dict[str, Any]], *, ratio: float = 1., review: bool = False,
    floor_heights_m: dict[str, float] | None = None,
    scope_floor_ids: tuple[str, ...] = ("1F",),
) -> ReadOnlyPhysicalAuthorityProvider:
    floor_heights_m = {"1F": 0.} if floor_heights_m is None else floor_heights_m
    native = []
    for surface in surfaces:
        row = dict(surface)
        row["vertices"] = [[value / ratio for value in p] for p in surface["vertices"]]
        native.append(row)
    geometry = SceneGeometrySnapshot.model_validate_json(json.dumps({
        "source_sha256": SOURCE, "scene_id": "SYNTHETIC_ENGINEERING_ONLY",
        "unit_scale_m": ratio, "scale_authority": "APPROVED", "scale_approval_id": APPROVAL,
        "surfaces": native, "floors": [{
            "floor_id": identity, "point": [0., 0., height / ratio], "normal": [0., 0., 1.],
            "authority": "APPROVED", "approval_id": APPROVAL,
            "evidence_ids": ["SYNTHETIC_FLOOR_REFERENCE"],
        } for identity, height in floor_heights_m.items()],
    }))
    digest = canonical_geometry_sha256(geometry)
    resolution = PhysicalAuthorityResolution.model_validate_json(json.dumps({
        "source_sha256": SOURCE, "geometry_sha256": digest,
        "level": "PROVISIONAL" if review else "PARTIAL_APPROVED",
        "policy": _policy().model_dump(mode="json"), "scopes": [{
            "scope_id": "synthetic-known-colliders", "purpose": "KNOWN_COLLISION_PRUNING",
            "floor_ids": scope_floor_ids, "surface_ids": [row["surface_id"] for row in surfaces],
            "coverage": "PARTIAL", "authority": "HUMAN_REVIEW" if review else "APPROVED",
            "approval_id": None if review else APPROVAL,
            "evidence_ids": ["SYNTHETIC_SCOPE_BOUNDARY"],
        }],
    }))
    return ReadOnlyPhysicalAuthorityProvider(geometry, resolution, SOURCE, digest)


def _consumer(
    surfaces: list[dict[str, Any]], *, ratio: float = 1., iterations: int = 128,
    triangles: int = 64, floor_heights_m: dict[str, float] | None = None,
    scope_floor_ids: tuple[str, ...] = ("1F",),
) -> CylinderCollisionConsumer:
    return CylinderCollisionConsumer.from_provider(
        _provider(surfaces, ratio=ratio, floor_heights_m=floor_heights_m,
                  scope_floor_ids=scope_floor_ids),
        "synthetic-known-colliders", _contract(ratio),
        _numerics(iterations=iterations, triangles=triangles),
    )


def _candidate(identity: str, x: float, *, score: float) -> CandidateTrajectory:
    return CandidateTrajectory(
        candidate_id=identity, start_observation_id="synthetic-start",
        end_observation_id="synthetic-end", polyline=((x, -1., 0.), (x, 1., 0.)),
        path_length=2., minimum_travel_time=2., estimated_travel_time=3., path_score=score,
    )


def test_wall_positive_collision_is_rejected_before_metrics() -> None:
    decision = _consumer([_wall()]).validate(((.2, -1., 0.), (.2, 1., 0.)))
    assert decision.state == "REJECTED"
    assert any("COLLISION_CONTACT" in reason for reason in decision.reasons)
    assert decision.complete_physical_validation is False


def test_continuous_sweep_catches_wall_between_clear_endpoints() -> None:
    consumer = _consumer([_wall()])
    for x in (-1., 1.):
        assert consumer.validate(((x, -1., 0.), (x, 1., 0.))).state == "RETAINED"
    crossing = consumer.validate(((-1., 0., 0.), (1., 0., 0.)))
    assert crossing.state == "REJECTED"
    assert "COLLISION_CONTACT" in crossing.reasons[0]


def test_overhead_surface_catches_full_body_instead_of_footpoint() -> None:
    decision = _consumer([_ceiling(1.65)]).validate(((-1., 0., 0.), (1., 0., 0.)))
    assert decision.state == "REJECTED"
    assert "synthetic-overhead" in decision.reasons[0]


def test_body_wholly_inside_closed_collider_is_collision() -> None:
    decision = _consumer([_cube()]).validate(((-.2, 0., 0.), (.2, 0., 0.)))
    assert decision.state == "REJECTED"
    assert decision.reasons == ("BODY_INSIDE_COLLIDER:synthetic-volume",)


def _concave_ring() -> dict[str, Any]:
    # A former parity ray grazed the hole's lower-right corner and then exited
    # the outer wall: two unique hits incorrectly classified an interior as OUT.
    corner_y = .5 + 1.5 * .2718281828
    xy = [(0., 0.), (4., 0.), (4., 4.), (0., 4.),
          (1., corner_y), (2., corner_y), (2., corner_y + 1), (1., corner_y + 1)]
    vertices = [[x, y, z] for z in (0., 4.) for x, y in xy]
    triangles = []
    for first in range(4):
        second = (first + 1) % 4
        quad = (first, second, 4 + second, 4 + first)
        triangles.extend([
            list(reversed((quad[0], quad[1], quad[2]))),
            list(reversed((quad[0], quad[2], quad[3]))),
            [quad[0] + 8, quad[1] + 8, quad[2] + 8],
            [quad[0] + 8, quad[2] + 8, quad[3] + 8],
            [first, second, second + 8], [first, second + 8, first + 8],
            [4 + first, 12 + second, 4 + second],
            [4 + first, 12 + first, 12 + second],
        ])
    ring = _cube()
    ring.update(vertices=vertices, triangles=triangles, source_face_indices=list(range(32)),
                source_object_id="SYNTHETIC_CLOSED_CONCAVE_RING")
    return ring


def test_concave_tangent_ray_cannot_make_wholly_contained_body_retainable() -> None:
    ring = _concave_ring()
    triangle_array = np.asarray(ring["vertices"])[np.asarray(ring["triangles"])]
    assert point_inside_closed_mesh(np.array([.5, .5, .95]), triangle_array) is True
    # All boundary triangles have an independent certified .10m-or-better
    # separation from this body. Containment, not a surface collision, rejects.
    start, end = (.5, .5, .1), (.5, .5001, .1)
    for triangle in triangle_array:
        distance = cylinder_triangle_distance(
            start, end, tuple(tuple(float(v) for v in point) for point in triangle),
            radius_m=.30, height_m=1.70, numerics=_numerics(),
        )
        assert distance.lower_m >= .05
    decision = _consumer([ring], floor_heights_m={"1F": .1}).validate((start, end))
    assert decision.state == "REJECTED"
    assert decision.reasons == ("BODY_INSIDE_COLLIDER:synthetic-volume",)


def test_winding_distinguishes_solid_hole_and_reversed_orientation() -> None:
    ring = _concave_ring()
    triangles = np.asarray(ring["vertices"])[np.asarray(ring["triangles"])]
    hole_y = .5 + 1.5 * .2718281828 + .5
    assert point_inside_closed_mesh(np.array([1.5, hole_y, 1.]), triangles) is False
    assert point_inside_closed_mesh(np.array([5., 5., 1.]), triangles) is False
    assert point_inside_closed_mesh(np.array([.5, .5, 1.]), triangles[:, ::-1]) is True


def test_closed_mesh_boundary_returns_unknown_and_consumer_refuses() -> None:
    cube = _cube()
    triangles = np.asarray(cube["vertices"])[np.asarray(cube["triangles"])]
    assert point_inside_closed_mesh(np.array(cube["vertices"][0]), triangles) is None
    assert point_inside_closed_mesh(np.array([2., 0., 1.]), triangles) is None
    decision = _consumer([cube]).validate(((2., 0., 0.), (2., .1, 0.)))
    assert decision.state == "UNVALIDATED"
    assert decision.reasons == ("CLOSED_VOLUME_CONTAINMENT_UNCERTAIN:synthetic-volume",)


def test_legal_approved_floor_support_contact_is_not_an_obstacle_collision() -> None:
    support = _ceiling(0.)
    support.update({
        "surface_id": "synthetic-legal-support", "role": "WALKABLE",
        "blocks_movement": False, "occludes_visibility": False,
    })
    consumer = _consumer([support, _wall(3.)])
    assert consumer.contract.approved_support_contact_allowed(consumer.inputs.surfaces[0])
    decision = consumer.validate(((-1., 0., 0.), (1., 0., 0.)))
    assert decision.state == "RETAINED"
    assert all(surface.surface_id != "synthetic-legal-support" for surface, _ in consumer.meshes)
    assert decision.complete_physical_validation is False


@pytest.mark.parametrize("gap,expected", [(.05, "RETAINED"), (.0499, "REJECTED"),
                                         (.0501, "RETAINED")])
def test_wall_clearance_exact_minimum_and_neighbors(gap: float, expected: str) -> None:
    x = .30 + gap
    decision = _consumer([_wall()]).validate(((x, -1., 0.), (x, 1., 0.)))
    assert decision.state == expected
    if expected == "REJECTED":
        assert "BODY_CLEARANCE_VIOLATION" in decision.reasons[0]


@pytest.mark.parametrize("gap,expected", [(.05, "RETAINED"), (.0499, "REJECTED"),
                                         (.0501, "RETAINED")])
def test_head_clearance_exact_minimum_and_neighbors(gap: float, expected: str) -> None:
    decision = _consumer([_ceiling(1.70 + gap)]).validate(((-1., 0., 0.), (1., 0., 0.)))
    assert decision.state == expected


def test_contact_tolerance_does_not_relax_minimum_clearance() -> None:
    decision = _consumer([_wall()]).validate(((.3495, -1., 0.), (.3495, 1., 0.)))
    assert decision.state == "REJECTED"
    assert "BODY_CLEARANCE_VIOLATION" in decision.reasons[0]
    # .0005m is beyond the body's wall surface, within the separate contact band.
    contact = _consumer([_wall()]).validate(((.3005, -1., 0.), (.3005, 1., 0.)))
    assert contact.state == "REJECTED"
    assert "COLLISION_CONTACT" in contact.reasons[0]


def test_other_scene_floor_outside_collision_scope_is_unvalidated() -> None:
    consumer = _consumer([_wall(10.)], floor_heights_m={"1F": 0., "2F": 3.})
    assert consumer.validate(((1., -1., 0.), (1., 1., 0.))).state == "RETAINED"
    decision = consumer.validate(((1., -1., 3.), (1., 1., 3.)))
    assert decision.state == "UNVALIDATED"
    assert decision.reasons == ("OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:point=0",)
    assert decision.tested_triangles == 0
    assert decision.complete_physical_validation is False


@pytest.mark.parametrize("height,expected", [
    (.001, "RETAINED"), (-.001, "RETAINED"), (.00101, "UNVALIDATED"),
])
def test_floor_contact_reference_band_is_inclusive(height: float, expected: str) -> None:
    decision = _consumer([_wall(10.)]).validate(((1., -1., height), (1., 1., height)))
    assert decision.state == expected
    assert decision.complete_physical_validation is False
    if expected == "UNVALIDATED":
        assert decision.reasons == ("OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:point=0",)


def test_floor_reference_contact_band_does_not_buffer_wall_clearance() -> None:
    decision = _consumer([_wall()]).validate(((.3499, -1., .001), (.3499, 1., .001)))
    assert decision.state == "REJECTED"
    assert "BODY_CLEARANCE_VIOLATION" in decision.reasons[0]


@pytest.mark.parametrize("ratio", [1., .0247])
def test_offset_native_floor_plane_is_compared_in_metres(ratio: float) -> None:
    consumer = _consumer([_wall(10.)], ratio=ratio, floor_heights_m={"1F": .6})
    assert consumer.validate(((1., -1., .6), (1., 1., .6))).state == "RETAINED"
    outside = consumer.validate(((1., -1., .60101), (1., 1., .60101)))
    assert outside.state == "UNVALIDATED"
    assert outside.reasons == ("OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:point=0",)


@pytest.mark.parametrize("path,segment_index", [
    (((1., -1., 0.), (1., 1., 3.)), 0),
    (((1., -1., 0.), (1., 0., 0.), (1., 1., 3.)), 1),
])
def test_segment_between_approved_floor_planes_requires_stair_authority(
    path: tuple[tuple[float, float, float], ...], segment_index: int,
) -> None:
    wall = _wall(10.)
    wall["floor_ids"] = ["1F", "2F"]
    consumer = _consumer([wall], floor_heights_m={"1F": 0., "2F": 3.},
                         scope_floor_ids=("1F", "2F"))
    for height in (0., 3.):
        assert consumer.validate(((1., -1., height), (1., 1., height))).state == "RETAINED"
    decision = consumer.validate(path)
    assert decision.state == "UNVALIDATED"
    assert decision.reasons == (
        f"OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:segment={segment_index}",
    )
    assert decision.tested_triangles == 0
    assert decision.complete_physical_validation is False


def test_intermediate_off_floor_point_cannot_use_matching_endpoint_planes() -> None:
    decision = _consumer([_wall(10.)]).validate((
        (1., -1., 0.), (1., 0., .1), (1., 1., 0.),
    ))
    assert decision.state == "UNVALIDATED"
    assert decision.reasons == ("OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:point=1",)
    assert decision.tested_triangles == 0


def test_out_of_floor_scope_candidate_is_excluded_with_metadata_before_k() -> None:
    outside = _candidate("outside-floor", 1., score=100.).model_copy(update={
        "polyline": ((1., -1., 3.), (1., 1., 3.)),
    })
    valid = _candidate("inside-floor", 1., score=10.)
    output, report = prune_before_top_k((outside, valid), _consumer([_wall(10.)]), top_k=1)
    assert output == (valid,)
    assert report["after_pruning_count"] == 1
    record = report["records"][0]
    assert record["candidate_id"] == "outside-floor"
    assert record["state"] == "UNVALIDATED"
    assert record["reasons"] == ("OUT_OF_APPROVED_COLLISION_FLOOR_SCOPE:point=0",)
    assert record["tested_triangles"] == 0


def test_analytic_wall_plane_lower_bound_accepts_equality() -> None:
    wall_triangle = ((0., -5., -1.), (0., 5., -1.), (0., 5., 4.))
    distance = cylinder_triangle_distance(
        (.35, -1., 0.), (.35, 1., 0.), wall_triangle,
        radius_m=.30, height_m=1.70, numerics=_numerics(),
    )
    assert distance.lower_m == pytest.approx(.05, abs=1e-12)
    assert distance.upper_m >= distance.lower_m
    assert distance.upper_m - distance.lower_m <= 1e-9


def test_analytic_overhead_plane_lower_bound_preserves_flat_cap_equality() -> None:
    ceiling_triangle = ((-5., -5., 1.75), (5., -5., 1.75), (5., 5., 1.75))
    distance = cylinder_triangle_distance(
        (-1., 0., 0.), (1., 0., 0.), ceiling_triangle,
        radius_m=.30, height_m=1.70, numerics=_numerics(),
    )
    assert distance.lower_m == pytest.approx(.05, abs=1e-12)
    assert distance.upper_m - distance.lower_m <= 1e-9


def test_convex_foot_domain_detects_interior_body_collision() -> None:
    distance = upright_body_triangle_distance(
        ((-1., -1., 0.), (1., -1., 0.), (0., 1., 0.)),
        ((-.1, -.1, 1.), (.1, -.1, 1.), (0., .1, 1.)),
        radius_m=.30, height_m=1.70, numerics=_numerics(),
    )
    assert distance.upper_m <= 1e-9


def test_triangle_budget_refuses_validation_instead_of_fabricating_clearance() -> None:
    decision = _consumer([_wall()], triangles=1).validate(((.35, -1., 0.), (.35, 1., 0.)))
    assert decision.state == "UNVALIDATED"
    assert decision.reasons == ("COLLISION_TRIANGLE_BUDGET_EXCEEDED",)
    assert decision.complete_physical_validation is False


def test_distance_iteration_limit_keeps_uncertain_collision_unvalidated() -> None:
    decision = _consumer([_wall()], iterations=1).validate(((.30, -1., 0.), (.30, 1., 0.)))
    assert decision.state == "UNVALIDATED"
    assert "COLLISION_DISTANCE_UNCERTAIN" in decision.reasons[0]


def test_review_scope_and_review_collider_cannot_be_used_formally() -> None:
    provider = _provider([_wall()], review=True)
    with pytest.raises(GeometryAuthorityError, match="SCOPE_NOT_APPROVED"):
        CylinderCollisionConsumer.from_provider(
            provider, "synthetic-known-colliders", _contract(), _numerics(),
        )
    review_wall = _wall()
    review_wall["physical_authority"] = "HUMAN_REVIEW"
    with pytest.raises(GeometryAuthorityError, match="SURFACE_NOT_APPROVED"):
        _provider([review_wall])


def test_filter_before_k_keeps_relative_order_and_original_scores() -> None:
    invalid = _candidate("invalid-first", .20, score=100.)
    valid_one = _candidate("valid-second", 1., score=20.)
    valid_two = _candidate("valid-third", 2., score=50.)
    consumer = _consumer([_wall()])
    top_two, report = prune_before_top_k((invalid, valid_one, valid_two), consumer, top_k=2)
    assert top_two == (valid_one, valid_two)
    assert report["before_count"] == 3
    assert report["after_pruning_count"] == 2
    assert report["output_count"] == 2
    assert report["ranking_changed"] is False
    assert report["gt_used"] is False
    top_one, _ = prune_before_top_k((invalid, valid_one, valid_two), consumer, top_k=1)
    assert top_one == (valid_one,)


def test_unvalidated_paths_are_excluded_and_duplicate_ids_rejected() -> None:
    candidate = _candidate("uncertain", .35, score=10.)
    output, report = prune_before_top_k((candidate,), _consumer([_wall()], triangles=1), top_k=1)
    assert output == ()
    assert report["after_pruning_count"] == 0
    with pytest.raises(ValueError, match="duplicate IDs"):
        prune_before_top_k((candidate, candidate), _consumer([_wall()]), top_k=1)


def test_empty_candidate_pool_keeps_structured_failure_metadata() -> None:
    output, report = prune_before_top_k((), _consumer([_wall()]), top_k=3)
    assert output == ()
    assert report["before_count"] == report["after_pruning_count"] == report["output_count"] == 0
    assert report["records"] == []
    assert report["known_collision_pruning_only"] is True


def test_native_bu_colliders_and_meter_paths_have_equivalent_results() -> None:
    meter = _consumer([_wall()], ratio=1.)
    native = _consumer([_wall()], ratio=.0247)
    for x in (.2, .35, .3499, 1.):
        path = ((x, -1., 0.), (x, 1., 0.))
        assert meter.validate(path).state == native.validate(path).state
    native_wall = native.inputs.colliders[0]
    assert native_wall.vertices[0][1] == pytest.approx(-5. / .0247)
    assert native.contract.parameter("body_radius_m") == .30


def test_source_mismatch_and_non_finite_paths_fail_fast() -> None:
    with pytest.raises(ValueError, match="source SHA"):
        CylinderCollisionConsumer.from_provider(
            _provider([_wall()]), "synthetic-known-colliders", _contract(source="d" * 64),
            _numerics(),
        )
    consumer = _consumer([_wall()])
    with pytest.raises(ValueError, match="finite"):
        consumer.validate(((1., 0., 0.), (math.inf, 0., 0.)))


def test_gt_has_no_inference_interface_and_forged_candidate_provenance_fails() -> None:
    assert "ground_truth" not in inspect.signature(prune_before_top_k).parameters
    assert "ground_truth" not in inspect.signature(CylinderCollisionConsumer.validate).parameters
    candidate = _candidate("candidate", 1., score=10.)
    forged = candidate.model_copy(update={"provenance": "GROUND_TRUTH"})
    with pytest.raises(ValidationError, match="provenance"):
        prune_before_top_k((forged,), _consumer([_wall()]), top_k=1)


@pytest.mark.parametrize("top_k", [0, -1, True])
def test_invalid_top_k_fails_fast(top_k: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        prune_before_top_k((), _consumer([_wall()]), top_k=top_k)
