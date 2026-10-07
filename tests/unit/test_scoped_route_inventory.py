"""Synthetic approved source-ring proofs; no real school approval is fabricated."""

import math
from copy import deepcopy
from typing import Any

import pytest
from test_local_physical_scopes import _atlas, _mesh
from test_scoped_authority import _apply, _decision, _inputs

from amidst.finalization.scoped_authority import (
    ScopedUnionPhysicalProvider,
    build_source_face_binding,
    load_scoped_authority,
)
from amidst.finalization.scoped_route_inventory import (
    ScopedCanonicalPath,
    ScopedRouteAuthorityBinding,
    SourceObstacleHoleWitness,
    canonical_path_from_cells,
    prove_scoped_route_classes,
    validate_scoped_route_class_proof,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import GeometryAuthorityError


def _approved(
    *, tiny_open_gap: bool = False, no_obstacle_role: bool = False, overhead: bool = False,
    narrow_semantic_guards: bool = False,
    obstacle_semantic_bound: Any = None,
) -> tuple[ScopedUnionPhysicalProvider, dict[str, Any], Any, ScopedRouteAuthorityBinding]:
    proposal, evidence, contract, numerics = _inputs()
    if overhead:
        obstacle = _mesh("SYNTHETIC_EXPLICIT_ISLAND", [
            [5., 4.5, 4.], [5., 5.5, 4.], [5., 5., 5.],
        ], [[0, 1, 2]])
        evidence = _atlas(contract, [obstacle])
        binding = build_source_face_binding(
            evidence, binding_id="synthetic-obstacle", source_mesh_id=obstacle["mesh_id"],
            source_component_id="synthetic-component", source_face_indices=(0,),
            proposed_role="MOVEMENT_OBSTACLE_SURFACE",
        )
        proposal = proposal.model_copy(update={
            "pins": proposal.pins.model_copy(update={
                "evidence_content_sha256": content_sha256(evidence),
            }), "obstacle_bindings": (binding,),
        })
    if tiny_open_gap:
        cells = tuple(cell.model_copy(update={
            "rectangle_xy_bu": (2., 2., 2.5, 7.5 - 1e-12),
        }) if index == 2 else cell for index, cell in enumerate(proposal.cells))
        proposal = proposal.model_copy(update={"cells": cells})
    if no_obstacle_role:
        proposal = proposal.model_copy(update={"obstacle_bindings": ()})
    if narrow_semantic_guards:
        proposal = proposal.model_copy(update={"cells": tuple(cell.model_copy(update={
            "proposed_body_guard_bounds_bu": (
                (cell.rectangle_xy_bu[0] - .5, cell.rectangle_xy_bu[1] - .5, -.1),
                (cell.rectangle_xy_bu[2] + .5, cell.rectangle_xy_bu[3] + .5, 2.),
            ),
        }) for cell in proposal.cells)})
    if obstacle_semantic_bound is not None:
        proposal = proposal.model_copy(update={"obstacle_bindings": tuple(
            build_source_face_binding(
                evidence, binding_id=binding.binding_id, source_mesh_id=binding.source_mesh_id,
                source_component_id=binding.source_component_id,
                source_face_indices=binding.source_face_indices,
                proposed_role="MOVEMENT_OBSTACLE_SURFACE",
                source_face_movement_obstacle_bounds_bu=obstacle_semantic_bound,
            ) for binding in proposal.obstacle_bindings
        )})
    decision = _decision(proposal)
    certificate, detail = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None, detail
    provider = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics,
        expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
    )
    pins = ScopedRouteAuthorityBinding(
        pins=proposal.pins,
        proposal_content_sha256=content_sha256(proposal.model_dump(mode="json")),
        decision_content_sha256=content_sha256(decision.model_dump(mode="json")),
        certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
        union_wkb_sha256=certificate.union_wkb_sha256,
    )
    return provider, evidence, numerics, pins


@pytest.fixture(scope="module")
def ring() -> tuple[ScopedUnionPhysicalProvider, dict[str, Any], Any, ScopedRouteAuthorityBinding]:
    return _approved()


def _path(
    provider: ScopedUnionPhysicalProvider, pins: ScopedRouteAuthorityBinding, *, top: bool,
    path_id: str | None = None, start_y: float = 5.,
) -> ScopedCanonicalPath:
    return canonical_path_from_cells(
        provider, expected_binding=pins, path_id=path_id or ("top" if top else "bottom"),
        cell_ids=("synthetic-cell-2", f"synthetic-cell-{1 if top else 0}", "synthetic-cell-3"),
        start_bu=(2.25, start_y, 0.), end_bu=(7.75, 5., 0.),
    )


def _witness(**changes: Any) -> SourceObstacleHoleWitness:
    value = dict(obstacle_binding_id="synthetic-obstacle", source_triangle_index=0,
                 barycentric_weights=(.25, .25, .5))
    value.update(changes)
    return SourceObstacleHoleWitness.model_validate(value)


def test_source_ring_separates_two_classes_with_intact_cell_and_face_provenance(ring: Any) -> None:
    provider, evidence, numerics, pins = ring
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    proof = prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                      expected_binding=pins)
    assert proof.distinct_classes_lower_bound == 2
    assert abs(proof.pair_windings[0]["closed_path_pair_winding"]) == 1
    assert proof.exact_witness_xyz_bu[:2] == ("5", "5")
    assert proof.hole_component_grid_bu
    assert proof.source_obstacle_binding == provider.proposal.obstacle_bindings[0]
    assert all(path.support_bindings == provider.proposal.support_bindings for path in proof.paths)
    assert all(path.cell_certificate_content_sha256 for path in proof.paths)
    assert all(record["epsilon_used"] is False for record in proof.continuous_cell_coverage)
    assert proof.inventory_exhaustive is False
    assert proof.formal_case_readiness is False
    assert proof.feasible_candidate_recall is None
    assert "EXHAUSTIVE_ELIGIBILITY_EQUIVALENCE_NOT_PROVEN" in proof.feasible_candidate_recall_status
    assert proof.graph_outputs_read is False
    assert proof.ground_truth_read is False


def test_two_ids_or_parallel_offsets_cannot_manufacture_classes(ring: Any) -> None:
    provider, evidence, numerics, pins = ring
    a = _path(provider, pins, top=False)
    duplicate = _path(provider, pins, top=False, path_id="duplicate")
    with pytest.raises(ValueError, match="winding does not separate"):
        prove_scoped_route_classes(provider, (a, duplicate), _witness(), evidence, numerics,
                                  expected_binding=pins)
    top = _path(provider, pins, top=True)
    points = tuple((x, y + .01, z) if index == 2 else (x, y, z)
                   for index, (x, y, z) in enumerate(top.polyline_bu))
    shifted = top.model_copy(update={"polyline_bu": points})
    assert provider.validate_polyline(points)
    with pytest.raises(ValueError, match="construction/provenance"):
        prove_scoped_route_classes(provider, (a, shifted), _witness(), evidence, numerics,
                                  expected_binding=pins)


def test_valid_endpoints_do_not_authorize_a_shortcut_through_the_union_hole(ring: Any) -> None:
    provider, evidence, numerics, pins = ring
    a, b = _path(provider, pins, top=False), _path(provider, pins, top=True)
    shortcut = a.model_copy(update={"polyline_bu": (a.polyline_bu[0], a.polyline_bu[-1])})
    with pytest.raises((ValueError, GeometryAuthorityError)):
        prove_scoped_route_classes(provider, (shortcut, b), _witness(), evidence, numerics,
                                  expected_binding=pins)


def test_fixed_endpoint_equality_is_exact_without_a_new_epsilon(ring: Any) -> None:
    provider, evidence, numerics, pins = ring
    a = _path(provider, pins, top=False)
    b = _path(provider, pins, top=True, start_y=math.nextafter(5., math.inf))
    with pytest.raises(ValueError, match="exactly equal fixed endpoints"):
        prove_scoped_route_classes(provider, (a, b), _witness(), evidence, numerics,
                                  expected_binding=pins)


@pytest.mark.parametrize("field", [
    "proposal_content_sha256", "decision_content_sha256", "certificate_content_sha256",
    "union_wkb_sha256",
])
def test_independent_authority_hash_mismatch_refused_before_class_claim(
    ring: Any, field: str,
) -> None:
    provider, evidence, numerics, pins = ring
    bad = pins.model_copy(update={field: "f" * 64})
    with pytest.raises(ValueError, match="pins differ"):
        prove_scoped_route_classes(provider, (), _witness(), evidence, numerics,
                                  expected_binding=bad)


@pytest.mark.parametrize("field", ["source_sha256", "floor_content_sha256",
                                  "numerics_content_sha256", "protocol_sha256"])
def test_original_source_floor_numerics_protocol_pins_are_retained(ring: Any, field: str) -> None:
    provider, evidence, numerics, pins = ring
    bad = pins.model_copy(update={"pins": pins.pins.model_copy(update={field: "f" * 64})})
    with pytest.raises(ValueError, match="pins differ"):
        prove_scoped_route_classes(provider, (), _witness(), evidence, numerics,
                                  expected_binding=bad)


def test_pending_decision_refuses_before_reading_source_evidence() -> None:
    provider, _, numerics, pins = _approved()
    object.__setattr__(provider, "decision", _decision(provider.proposal, "PENDING"))
    with pytest.raises(ValueError, match="approval/certificate/domain binding"):
        prove_scoped_route_classes(provider, (), _witness(), {}, numerics, expected_binding=pins)


def test_tiny_open_union_gap_cannot_be_promoted_to_a_bounded_hole() -> None:
    provider, evidence, numerics, pins = _approved(tiny_open_gap=True)
    paths = (_path(provider, pins, top=False),
             _path(provider, pins, top=False, path_id="second-bottom"))
    with pytest.raises(ValueError, match="unbounded complement"):
        prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                  expected_binding=pins)


def test_source_name_or_raw_face_cannot_supply_missing_obstacle_authority() -> None:
    provider, evidence, numerics, pins = _approved(no_obstacle_role=True)
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    with pytest.raises(ValueError, match="approved movement obstacle binding"):
        prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                  expected_binding=pins)


def test_overhead_triangle_in_union_hole_is_not_a_body_obstruction_witness() -> None:
    provider, evidence, numerics, pins = _approved(overhead=True)
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    with pytest.raises(ValueError, match="upright body height"):
        prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                  expected_binding=pins)


def test_approved_cell_guards_do_not_authorize_island_witness_outside_semantic_bounds() -> None:
    provider, evidence, numerics, pins = _approved(narrow_semantic_guards=True)
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    assert all(provider.validate_polyline(path.polyline_bu) for path in paths)
    with pytest.raises(GeometryAuthorityError, match="OUTSIDE_APPROVED_SEMANTIC_BOUNDS"):
        prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                  expected_binding=pins)


def test_explicit_approved_source_face_bound_can_own_witness_outside_cell_guards() -> None:
    bound = ((5., 4.5, .2), (5., 5.5, 1.5))
    provider, evidence, numerics, pins = _approved(narrow_semantic_guards=True,
                                                  obstacle_semantic_bound=bound)
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    proof = prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                      expected_binding=pins)
    assert proof.distinct_classes_lower_bound == 2
    assert proof.witness_semantic_bound_kind == "SOURCE_FACE_MOVEMENT_OBSTACLE_BOUND"
    assert proof.witness_semantic_bounds_bu == (bound,)
    assert proof.witness_semantic_guard_cell_ids == ()
    assert proof.source_obstacle_binding.source_face_movement_obstacle_bounds_bu == bound


def test_witness_outside_both_explicit_source_bound_and_cell_guards_is_refused() -> None:
    bound = ((5., 4.5, .2), (5., 4.6, .4))
    provider, evidence, numerics, pins = _approved(narrow_semantic_guards=True,
                                                  obstacle_semantic_bound=bound)
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    with pytest.raises(GeometryAuthorityError, match="OUTSIDE_APPROVED_SEMANTIC_BOUNDS"):
        prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                  expected_binding=pins)


@pytest.mark.parametrize("change", [
    {"source_triangle_index": 999}, {"barycentric_weights": (.1, .2, .7)},
    {"barycentric_weights": (0., .5, .5)},
])
def test_witness_must_be_exact_interior_of_bound_source_triangle(ring: Any, change: Any) -> None:
    provider, evidence, numerics, pins = ring
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    with pytest.raises(ValueError, match="source faces/triangles|barycentric"):
        prove_scoped_route_classes(provider, paths, _witness(**change), evidence, numerics,
                                  expected_binding=pins)


def test_source_evidence_and_numeric_policy_changes_are_not_consumed(ring: Any) -> None:
    provider, evidence, numerics, pins = ring
    changed = deepcopy(evidence)
    changed["topology_test_extra_unreviewed_data"] = True
    with pytest.raises(ValueError):
        prove_scoped_route_classes(provider, (), _witness(), changed, numerics,
                                  expected_binding=pins)
    changed_numeric = numerics.model_copy(update={"maximum_distance_iterations": 2})
    with pytest.raises(ValueError, match="evidence/numerics pins differ"):
        prove_scoped_route_classes(provider, (), _witness(), evidence, changed_numeric,
                                  expected_binding=pins)


def test_consumer_regenerates_winding_receipt_instead_of_trusting_a_class_label(ring: Any) -> None:
    provider, evidence, numerics, pins = ring
    paths = (_path(provider, pins, top=False), _path(provider, pins, top=True))
    proof = prove_scoped_route_classes(provider, paths, _witness(), evidence, numerics,
                                      expected_binding=pins)
    digest = content_sha256(proof.model_dump(mode="json"))
    validate_scoped_route_class_proof(
        proof, provider, evidence, numerics, expected_binding=pins,
        expected_proof_content_sha256=digest,
    )
    changed = proof.model_copy(update={"pair_windings": ({
        "first_path_id": "bottom", "second_path_id": "top", "closed_path_pair_winding": 99,
    },)})
    # Even a newly hash-consistent receipt cannot replace exact regeneration.
    with pytest.raises(ValueError, match="regenerated/pinned evidence"):
        validate_scoped_route_class_proof(
            changed, provider, evidence, numerics, expected_binding=pins,
            expected_proof_content_sha256=content_sha256(changed.model_dump(mode="json")),
        )
