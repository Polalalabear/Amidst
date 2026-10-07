"""New approval gates and real numerical union checks on synthetic source meshes."""

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from shapely import from_wkb
from test_local_physical_scopes import (
    FLOOR_OBJECT,
    REGION,
    _atlas,
    _contract,
    _domain,
    _mesh,
    _numerics,
)

from amidst.domain.camera import Camera
from amidst.finalization.scoped_authority import (
    BoundedSurfaceSemantics,
    ScopeAuthorityPins,
    ScopeCameraLandmarkBinding,
    ScopeCellProposal,
    ScopedUnionPhysicalProvider,
    ScopeHumanDecision,
    ScopeProposal,
    apply_scope_approval,
    build_source_face_binding,
    contract_content_sha256,
    load_scoped_authority,
    preview_scope_numeric,
    proposal_from_source_discovery,
    validate_scope_proposal,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import GeometryAuthorityError


def _inputs() -> tuple[ScopeProposal, dict[str, Any], Any, Any]:
    contract = _contract()
    # Exact unclassified source triangle obstructs the direct connector, while
    # the four rectangular cells on the outer ring are numerically clear.
    obstacle = _mesh("SYNTHETIC_EXPLICIT_ISLAND", [
        [5., 4.5, .2], [5., 5.5, .2], [5., 5., 1.5],
    ], [[0, 1, 2]])
    evidence = _atlas(contract, [obstacle])
    numerics = _numerics()
    floor = _domain(contract).floor
    pins = ScopeAuthorityPins(
        source_sha256=evidence["source_sha256"], evidence_content_sha256=content_sha256(evidence),
        physical_contract_content_sha256=contract_content_sha256(contract),
        numerics_content_sha256=content_sha256(numerics.model_dump(mode="json")),
        original_human_decisions_sha256="a" * 64, protocol_sha256="b" * 64,
        floor_content_sha256=content_sha256(floor.model_dump(mode="json")),
    )
    support_mesh = next(m for m in evidence["meshes"] if m["source_object_id"] == FLOOR_OBJECT)
    support = build_source_face_binding(
        evidence, binding_id="synthetic-contact", source_mesh_id=support_mesh["mesh_id"],
        source_component_id="synthetic-component", source_face_indices=(0, 1, 2, 3),
        proposed_role="WALKABLE_SUPPORT_SURFACE",
    )
    obstacle_binding = build_source_face_binding(
        evidence, binding_id="synthetic-obstacle", source_mesh_id=obstacle["mesh_id"],
        source_component_id="synthetic-component", source_face_indices=(0,),
        proposed_role="MOVEMENT_OBSTACLE_SURFACE",
    )
    rectangles = ((2., 2., 8., 2.5), (2., 7.5, 8., 8.),
                  (2., 2., 2.5, 8.), (7.5, 2., 8., 8.))
    cells = tuple(ScopeCellProposal(
        cell_id=f"synthetic-cell-{i}", rectangle_xy_bu=rect,
        body_region_id=REGION, proposed_body_guard_bounds_bu=((1., 1., -.1), (9., 9., 2.)),
    ) for i, rect in enumerate(rectangles))
    proposal = ScopeProposal(
        scope_id="SYNTHETIC_UNION_NOT_SCHOOL_APPROVAL", pins=pins, floor=floor,
        support_bindings=(support,), obstacle_bindings=(obstacle_binding,), cells=cells,
    )
    return proposal, evidence, contract, numerics


def _decision(proposal: ScopeProposal, choice: str = "APPROVE") -> ScopeHumanDecision:
    return ScopeHumanDecision.model_validate({
        "proposal_content_sha256": content_sha256(proposal.model_dump(mode="json")),
        "decision": choice, "approval_origin": "DIRECT_HUMAN_DECISION",
        "reviewer_id": "SYNTHETIC_TEST_REVIEWER_NOT_REAL_APPROVAL",
        "human_approval_id": "SYNTHETIC_TEST_ONLY_NEW_SCOPE_RECEIPT",
        "decision_timestamp": datetime.fromisoformat("2026-10-08T00:00:00+08:00"),
        "direct_human_decision_text": "SYNTHETIC TEST ONLY: exact proposal approved by fixture.",
    })


def _apply(proposal: ScopeProposal, decision: ScopeHumanDecision, evidence: dict[str, Any],
           contract: Any, numerics: Any) -> tuple[Any, dict[str, Any]]:
    return apply_scope_approval(
        proposal, decision, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_proposal_content_sha256=content_sha256(proposal.model_dump(mode="json")),
        expected_decision_content_sha256=content_sha256(decision.model_dump(mode="json")),
    )


@pytest.mark.parametrize("choice", ["PENDING", "REJECT", "KEEP_REVIEW", "FIX_GEOMETRY"])
def test_unapproved_does_not_even_load_source_or_construct_numeric_authority(choice: str) -> None:
    proposal, _, contract, numerics = _inputs()
    certificate, result = _apply(proposal, _decision(proposal, choice), {}, contract, numerics)
    assert certificate is None
    assert result["status"] == "BLOCKED_NEW_HUMAN_APPROVAL_REQUIRED"
    assert result["formal_execution_enabled"] is False


def test_approved_ring_retains_real_source_numeric_cells_and_rejects_hole() -> None:
    proposal, evidence, contract, numerics = _inputs()
    decision = _decision(proposal)
    certificate, result = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None, result
    assert len(certificate.cells) == 4
    geometry = from_wkb(bytes.fromhex(certificate.union_wkb_hex))
    assert len(geometry.interiors) == 1
    provider = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
    )
    assert provider.validate_polyline(((2.25, 5., 0.), (2.25, 2.25, 0.),
                                      (7.75, 2.25, 0.), (7.75, 5., 0.)))
    assert provider.validate_polyline(((2.25, 5., 0.), (2.25, 7.75, 0.),
                                      (7.75, 7.75, 0.), (7.75, 5., 0.)))
    with pytest.raises(GeometryAuthorityError, match="UNION_OR_HOLE"):
        provider.validate_polyline(((2.25, 5., 0.), (7.75, 5., 0.)))
    assert result["formal_execution_enabled"] is False
    assert certificate.overall_formal_case_execution_enabled is False


def test_human_approval_cannot_clear_actual_source_collision() -> None:
    proposal, evidence, contract, numerics = _inputs()
    cell = proposal.cells[0].model_copy(update={"rectangle_xy_bu": (2., 4.5, 8., 5.5)})
    proposal = proposal.model_copy(update={"cells": (cell,)})
    certificate, result = _apply(proposal, _decision(proposal), evidence, contract, numerics)
    assert certificate is None
    assert result["status"] == "BLOCKED_NUMERICAL_CERTIFICATION"
    assert result["cell_checks"][0]["reason"] == "UNCLASSIFIED_SOURCE_BODY_CONTACT"


def test_human_approval_cannot_extend_body_guard() -> None:
    proposal, evidence, contract, numerics = _inputs()
    cell = proposal.cells[0].model_copy(update={
        "proposed_body_guard_bounds_bu": ((2., 2., 0.), (8., 8., 1.)),
    })
    proposal = proposal.model_copy(update={"cells": (cell,)})
    certificate, result = _apply(proposal, _decision(proposal), evidence, contract, numerics)
    assert certificate is None
    assert result["cell_checks"][0]["reason"] == (
        "PROPOSED_GUARD_DOES_NOT_COVER_EXACT_BODY_ENVELOPE"
    )


def test_original_receipt_and_new_proposal_cannot_be_interchanged() -> None:
    proposal, evidence, contract, numerics = _inputs()
    decision = _decision(proposal).model_copy(update={"proposal_content_sha256": "1" * 64})
    with pytest.raises(ValueError, match="proposal/human receipt"):
        _apply(proposal, decision, evidence, contract, numerics)


def test_proposal_requires_exact_whole_source_face_coordinates_and_component() -> None:
    proposal, evidence, contract, numerics = _inputs()
    bad = proposal.support_bindings[0].model_copy(update={
        "source_triangle_indices": (0,), "exact_triangles_content_sha256": "2" * 64,
    })
    changed = proposal.model_copy(update={"support_bindings": (bad,)})
    with pytest.raises(ValueError, match="retain every triangle"):
        validate_scope_proposal(changed, evidence, contract, numerics, expected_pins=proposal.pins)


def test_core_policy_and_original_floor_are_pinned_outside_proposal() -> None:
    proposal, evidence, contract, numerics = _inputs()
    floor = proposal.floor.model_copy(update={"point": (0., 0., .01)})
    with pytest.raises(ValueError, match="original floor"):
        validate_scope_proposal(proposal.model_copy(update={"floor": floor}), evidence,
                                contract, numerics, expected_pins=proposal.pins)
    with pytest.raises(ValueError, match="policy/numerics"):
        validate_scope_proposal(proposal, evidence, contract, _numerics(iterations=129),
                                expected_pins=proposal.pins)


def test_nondegenerate_source_face_cannot_be_declared_a_zero_area_seam() -> None:
    proposal, evidence, contract, numerics = _inputs()
    support = proposal.support_bindings[0]
    semantics = BoundedSurfaceSemantics(
        source_object_id=support.source_object_id, source_mesh_id=support.source_mesh_id,
        source_geometry_sha256=support.source_geometry_sha256,
        source_component_id=support.source_component_id, zero_area_source_face_indices=(0,),
        component_interior="SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND",
        zero_area_face_ownership="DEGENERATE_SEAM_NO_OCCUPIED_VOLUME_IN_BOUND",
    )
    proposal = proposal.model_copy(update={"cells": (
        proposal.cells[0].model_copy(update={"surface_semantics": semantics}),
    )})
    with pytest.raises(ValueError, match="cannot waive nondegenerate"):
        validate_scope_proposal(proposal, evidence, contract, numerics,
                                expected_pins=proposal.pins)


def test_preview_returns_no_approval_receipt_certificate_or_provider() -> None:
    proposal, evidence, contract, numerics = _inputs()
    result = preview_scope_numeric(proposal, evidence, contract, numerics,
                                   expected_pins=proposal.pins)
    assert result["status"] == "HYPOTHETICAL_NUMERIC_NOT_AUTHORITY"
    assert result["authority_applied"] is False
    assert result["new_human_approval_exists"] is False
    assert result["formal_certificate"] is None
    assert all(c["bounded_surface_semantics_applied"] is False for c in result["cell_checks"])
    assert all(not c["status"].startswith("APPROVED") for c in result["cell_checks"])


def test_union_or_cell_hash_mutation_is_rejected() -> None:
    proposal, evidence, contract, numerics = _inputs()
    decision = _decision(proposal)
    certificate, _ = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None
    changed = certificate.model_copy(update={"union_wkb_sha256": "2" * 64})
    with pytest.raises(ValueError, match="local union differs"):
        ScopedUnionPhysicalProvider(
            changed, _domain_for_fixture(proposal, decision, evidence, contract), contract,
            proposal, decision, content_sha256(changed.model_dump(mode="json")),
        )


def test_new_bounded_semantic_receipt_is_retained_for_each_cell() -> None:
    proposal, _, contract, numerics = _inputs()
    seam = _mesh("SYNTHETIC_EXACT_SEAM", [[2., 2., 0.], [2., 3., 0.], [2., 4., 0.]],
                 [[0, 1, 2]])
    evidence = _atlas(contract, [seam])
    pins = proposal.pins.model_copy(update={"evidence_content_sha256": content_sha256(evidence)})
    semantics = BoundedSurfaceSemantics(
        source_object_id=seam["source_object_id"], source_mesh_id=seam["mesh_id"],
        source_geometry_sha256=seam["geometry_sha256"],
        source_component_id="synthetic-component", zero_area_source_face_indices=(0,),
        component_interior="SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND",
        zero_area_face_ownership="DEGENERATE_SEAM_NO_OCCUPIED_VOLUME_IN_BOUND",
    )
    proposal = proposal.model_copy(update={
        "pins": pins, "obstacle_bindings": (),
        "cells": tuple(c.model_copy(update={"surface_semantics": semantics})
                       for c in proposal.cells),
    })
    decision = _decision(proposal)
    certificate, result = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None, result
    assert all(c.semantic_review.human_decisions_sha256 == certificate.human_decision_content_sha256
               for c in certificate.cells)
    provider = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
    )
    provider.validate()
    assert provider.validate_polyline(((2.25, 2.25, 0.), (7.75, 2.25, 0.)))
    preview = preview_scope_numeric(proposal, evidence, contract, numerics, expected_pins=pins)
    assert preview["cell_checks"][0]["reason"] == "DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE"
    assert preview["new_human_approval_exists"] is False


@pytest.mark.parametrize("gap", [0., 1e-12])
def test_continuous_union_coverage_never_bridges_even_tiny_unapproved_gap(gap: float) -> None:
    proposal, evidence, contract, numerics = _inputs()
    cells = (
        proposal.cells[0].model_copy(update={"cell_id": "left",
                                            "rectangle_xy_bu": (2., 2., 5., 2.5)}),
        proposal.cells[0].model_copy(update={"cell_id": "right",
                                            "rectangle_xy_bu": (5. + gap, 2., 8., 2.5)}),
    )
    proposal = proposal.model_copy(update={"cells": cells})
    decision = _decision(proposal)
    certificate, result = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None, result
    provider = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
    )
    if gap:
        with pytest.raises(GeometryAuthorityError, match="UNION_OR_HOLE"):
            provider.validate_polyline(((2.25, 2.25, 0.), (7.75, 2.25, 0.)))
    else:
        assert provider.validate_polyline(((2.25, 2.25, 0.), (7.75, 2.25, 0.)))


def test_camera_landmark_authority_requires_the_actual_source_calibration_export() -> None:
    proposal, evidence, contract, numerics = _inputs()
    camera = Camera(
        camera_id="SYNTHETIC_SOURCE_CAMERA", camera_to_world=(
            (1., 0., 0., 0.), (0., 1., 0., 0.), (0., 0., 1., 3.), (0., 0., 0., 1.),
        ), fx=100., fy=100., cx=50., cy=50., width=100, height=100, floor_id="1F",
    )
    export = {"source_sha256": proposal.pins.source_sha256,
              "cameras": [camera.model_dump(mode="json")]}
    camera_pins = proposal.pins.model_copy(update={
        "camera_export_content_sha256": content_sha256(export),
    })
    binding = ScopeCameraLandmarkBinding(
        camera=camera, calibration_content_sha256=content_sha256(camera.model_dump(mode="json")),
        source_camera_export_content_sha256=content_sha256(export), floor_id="1F",
        landmark_offset_bu=(0., 0., 1.), projection_plane_point_bu=(0., 0., 1.),
    )
    proposal = proposal.model_copy(update={"pins": camera_pins,
                                          "camera_landmark_bindings": (binding,),
                                          "requested_projection_authority": True})
    with pytest.raises(ValueError, match="requires original source camera export"):
        validate_scope_proposal(proposal, evidence, contract, numerics,
                                expected_pins=proposal.pins)
    validate_scope_proposal(proposal, evidence, contract, numerics,
                            expected_pins=proposal.pins, camera_export=export)
    changed = {**export, "cameras": [
        camera.model_copy(update={"fx": 101.}).model_dump(mode="json"),
    ]}
    with pytest.raises(ValueError, match="independently pinned source calibration"):
        validate_scope_proposal(proposal, evidence, contract, numerics,
                                expected_pins=proposal.pins, camera_export=changed)


def test_cli_rejects_actual_source_bytes_mismatch_before_any_output(tmp_path: Path) -> None:
    import json

    from amidst.finalization.scoped_authority_cli import main

    proposal, _, _, _ = _inputs()
    pins_file = tmp_path / "pins.json"
    pins_file.write_text(proposal.pins.model_dump_json())
    source = tmp_path / "synthetic-source.blend"
    source.write_bytes(b"SYNTHETIC_TEST_ONLY_DIFFERENT_SOURCE")
    proposal_file = tmp_path / "proposal.json"
    proposal_file.write_text(json.dumps(proposal.model_dump(mode="json")))
    output = tmp_path / "new-output"
    with pytest.raises(ValueError, match="preserved source bytes"):
        main(["inspect", "--pins", str(pins_file), "--source", str(source),
              "--proposal", str(proposal_file), "--output", str(output),
              "--evidence", "unread-evidence.json", "--runtime", "unread-runtime.json",
              "--numerics", "unread-numerics.json"])
    assert not output.exists()


def test_cli_rejects_ground_truth_partition_and_preserves_existing_output(tmp_path: Path) -> None:
    from amidst.finalization.scoped_authority_cli import main

    common = ["inspect", "--pins", "pins.json", "--source", "source.blend",
              "--proposal", "proposal.json", "--runtime", "runtime.json",
              "--numerics", "numerics.json", "--output", str(tmp_path / "output")]
    with pytest.raises(SystemExit):
        main([*common, "--evidence", "ground_truth/source_evidence.json"])
    output = tmp_path / "output"
    output.mkdir()
    marker = output / "preserved.txt"
    marker.write_text("PRESERVED")
    with pytest.raises(SystemExit):
        main([*common, "--evidence", "source_evidence.json"])
    assert marker.read_text() == "PRESERVED"


def test_explicit_per_cell_semantic_file_has_no_implicit_profile_fallback() -> None:
    from amidst.finalization.scoped_authority_cli import _proposed_semantics

    assert _proposed_semantics({"profiles_by_cell_index": {"0": None, "1": None}}) == {
        "0": None, "1": None,
    }
    with pytest.raises(ValueError, match="only profiles_by_cell_index"):
        _proposed_semantics({"profiles_by_cell_index": {"0": None}, "auto_approve": True})


def test_discovery_bridge_binds_each_disconnected_component_and_all_source_faces() -> None:
    proposal, _, contract, numerics = _inputs()
    obstacle = _mesh("SYNTHETIC_TWO_COMPONENT_ISLAND", [
        [4.8, 4.5, .2], [4.8, 5.5, .2], [4.8, 5., 1.5],
        [5.2, 4.5, .2], [5.2, 5.5, .2], [5.2, 5., 1.5],
    ], [[0, 1, 2], [3, 4, 5]])
    original = obstacle["components"][0]
    obstacle["components"] = [{
        **original, "component_id": f"synthetic-part-{i}",
        "source_triangle_indices": [i], "source_vertex_indices": list(range(i * 3, i * 3 + 3)),
        "triangle_count": 1,
        "bounds_bu": {"minimum": [4.8 + .4 * i, 4.5, .2],
                      "maximum": [4.8 + .4 * i, 5.5, 1.5]},
    } for i in range(2)]
    obstacle["geometry_sha256"] = content_sha256({
        k: v for k, v in obstacle.items() if k != "geometry_sha256"
    })
    evidence = _atlas(contract, [obstacle])
    evidence["regions"][0]["selections"][1]["component_ids"] = [
        "synthetic-part-0", "synthetic-part-1",
    ]
    pins = proposal.pins.model_copy(update={"evidence_content_sha256": content_sha256(evidence)})
    support = proposal.support_bindings[0]
    discovery = {
        "source_sha256": pins.source_sha256, "source_evidence_content_sha256": content_sha256(
            evidence,
        ), "authority_applied": False,
        "support_source_faces": {"source_mesh_id": support.source_mesh_id,
                                 "source_face_indices": list(support.source_face_indices)},
        "source_island_bindings": [{"source_mesh_id": obstacle["mesh_id"],
                                    "source_face_indices": [0, 1]}],
        "proposed_footpoint_cells": [{
            "footpoint_cell_bounds_xy_bu": c.rectangle_xy_bu,
            "source_body_region_id": c.body_region_id,
            "body_guard_bounds_bu": {"minimum": c.proposed_body_guard_bounds_bu[0],
                                     "maximum": c.proposed_body_guard_bounds_bu[1]},
        } for c in proposal.cells],
    }
    bridged = proposal_from_source_discovery(
        discovery, evidence, scope_id=proposal.scope_id, pins=pins, floor=proposal.floor,
        proposed_surface_semantics={str(i): None for i in range(4)},
    )
    assert len(bridged.obstacle_bindings) == 2
    assert {b.source_component_id for b in bridged.obstacle_bindings} == {
        "synthetic-part-0", "synthetic-part-1",
    }
    assert {b.source_triangle_indices for b in bridged.obstacle_bindings} == {(0,), (1,)}
    assert all(b.source_face_movement_obstacle_bounds_bu is not None
               for b in bridged.obstacle_bindings)
    assert bridged.authority == "HUMAN_REVIEW"
    validate_scope_proposal(bridged, evidence, contract, numerics, expected_pins=pins)
    with pytest.raises(ValueError, match="every exact cell index"):
        proposal_from_source_discovery(discovery, evidence, scope_id=proposal.scope_id, pins=pins,
                                       floor=proposal.floor, proposed_surface_semantics={"0": None})


def _with_obstacle_bound(bounds: Any) -> tuple[ScopeProposal, dict[str, Any], Any, Any]:
    proposal, evidence, contract, numerics = _inputs()
    binding = proposal.obstacle_bindings[0].model_copy(update={
        "source_face_movement_obstacle_bounds_bu": bounds,
    })
    return (proposal.model_copy(update={"obstacle_bindings": (binding,)}),
            evidence, contract, numerics)


def test_explicit_planar_source_surface_bound_is_pinned_without_extra_thickness() -> None:
    proposal, evidence, contract, numerics = _with_obstacle_bound(
        ((5., 4.5, .2), (5., 5.5, 1.5)),
    )
    decision = _decision(proposal)
    certificate, result = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None, result
    assert proposal.obstacle_bindings[0].whole_object_approved is False
    assert proposal.obstacle_bindings[0].solid_interior_approved is False
    changed = proposal.model_copy(update={"obstacle_bindings": (
        proposal.obstacle_bindings[0].model_copy(update={
            "source_face_movement_obstacle_bounds_bu": ((5., 4.5, .2), (5., 5.6, 1.5)),
        }),
    )})
    with pytest.raises(ValueError, match="proposal/human receipt"):
        _apply(changed, decision, evidence, contract, numerics)
    preview = preview_scope_numeric(proposal, evidence, contract, numerics,
                                   expected_pins=proposal.pins)
    assert preview["required_human_semantics"][0]["kind"] == "SOURCE_FACE_MOVEMENT_OBSTACLE"
    assert preview["authority_applied"] is False


def test_explicit_obstacle_bound_requires_actual_source_facets_not_bbox_overlap() -> None:
    proposal, evidence, contract, numerics = _with_obstacle_bound(
        ((5., 4.5, 1.4), (5., 4.6, 1.5)),
    )
    # This intersects the triangle's outer box but no point on the real triangle.
    with pytest.raises(ValueError, match="no actual bound source-face geometry"):
        validate_scope_proposal(proposal, evidence, contract, numerics, expected_pins=proposal.pins)
    valid, evidence, contract, numerics = _with_obstacle_bound(
        ((5., 4.5, .2), (5., 5.5, 1.5)),
    )
    invalid_binding = valid.obstacle_bindings[0].model_copy(update={
        "source_geometry_sha256": "c" * 64,
    })
    with pytest.raises(ValueError, match="source object/geometry"):
        validate_scope_proposal(valid.model_copy(update={"obstacle_bindings": (invalid_binding,)}),
                                evidence, contract, numerics, expected_pins=valid.pins)


def test_obstacle_bound_cannot_approve_floor_or_escape_original_samefloor_atlas() -> None:
    proposal, evidence, contract, numerics = _inputs()
    support = proposal.support_bindings[0].model_copy(update={
        "source_face_movement_obstacle_bounds_bu": ((1., 1., 0.), (9., 9., 0.)),
    })
    with pytest.raises(ValueError, match="cannot approve floor support"):
        validate_scope_proposal(proposal.model_copy(update={"support_bindings": (support,)}),
                                evidence, contract, numerics, expected_pins=proposal.pins)
    for bounds in (((5., 4.5, 100.), (5., 5.5, 101.)),
                   ((-2., 4.5, .2), (5., 5.5, 1.5))):
        altered, evidence, contract, numerics = _with_obstacle_bound(bounds)
        with pytest.raises(ValueError, match="same-floor source atlas"):
            validate_scope_proposal(altered, evidence, contract, numerics,
                                    expected_pins=altered.pins)


def test_unapproved_new_obstacle_ownership_bound_cannot_create_any_authority() -> None:
    proposal, _, contract, numerics = _with_obstacle_bound(((5., 4.5, .2), (5., 5.5, 1.5)))
    certificate, result = _apply(proposal, _decision(proposal, "PENDING"), {}, contract, numerics)
    assert certificate is None
    assert result["status"] == "BLOCKED_NEW_HUMAN_APPROVAL_REQUIRED"


def _domain_for_fixture(proposal: ScopeProposal, decision: ScopeHumanDecision,
                        evidence: dict[str, Any], contract: Any) -> Any:
    # The public loader is the source-verifying entry. This test mutates only the
    # immutable consumer receipt after a legitimate synthetic application.
    from amidst.finalization.scoped_authority import _domain_after_approval
    return _domain_after_approval(proposal, evidence, contract, decision)
