"""Multiple bounded human profiles, on fully hashed synthetic source evidence."""

import math
from typing import Any

import pytest
from test_local_physical_scopes import _atlas, _mesh, _unknown_enclosure
from test_scoped_authority import _apply, _decision, _inputs

from amidst.finalization.scoped_authority import (
    BoundedSurfaceSemantics,
    _segment_interval,
    load_scoped_authority,
)
from amidst.finalization.scoped_authority_cli import _proposed_semantics
from amidst.finalization.scoped_semantic_cells import (
    MultiReviewedLocalScopeCertificate,
    MultiReviewedRestrictedPhysicalProvider,
)
from amidst.obstacle_volume_authority import content_sha256


def _multi_inputs(count: int = 2, *, contact: bool = False) -> tuple[Any, ...]:
    proposal, _, contract, numerics = _inputs()
    meshes = []
    for index in range(count):
        raw = _unknown_enclosure()
        points = raw["vertices"]
        triangles = raw["triangles"] + [list(reversed(t)) for t in raw["triangles"]]
        if contact and index == 0:
            points = points + [[5., 4., .5], [5., 6., .5], [5., 5., 1.5]]
            triangles = triangles + [[8, 9, 10]]
        meshes.append(_mesh(f"SYNTHETIC_AMBIGUOUS_SURFACE_{index}", points, triangles))
    evidence = _atlas(contract, meshes)
    profiles = tuple(BoundedSurfaceSemantics(
        source_object_id=m["source_object_id"], source_mesh_id=m["mesh_id"],
        source_geometry_sha256=m["geometry_sha256"], source_component_id="synthetic-component",
        zero_area_source_face_indices=(),
        component_interior="SURFACE_ONLY_NO_SOLID_INTERIOR_IN_BOUND",
        zero_area_face_ownership="DEGENERATE_SEAM_NO_OCCUPIED_VOLUME_IN_BOUND",
    ) for m in meshes)
    cell = proposal.cells[0].model_copy(update={
        "rectangle_xy_bu": (2., 2., 8., 8.), "surface_semantics": profiles[0],
        "extra_surface_semantics": profiles[1:min(count, 2)],
    })
    proposal = proposal.model_copy(update={
        "pins": proposal.pins.model_copy(update={
            "evidence_content_sha256": content_sha256(evidence),
        }),
        "obstacle_bindings": (), "cells": (cell,),
    })
    return proposal, evidence, contract, numerics


@pytest.mark.parametrize("count", [1, 2])
def test_empty_zero_area_profiles_retain_every_receipt_without_invented_exemptions(
    count: int,
) -> None:
    proposal, evidence, contract, numerics = _multi_inputs(count)
    decision = _decision(proposal)
    certificate, result = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None, result
    cell = certificate.cells[0]
    assert isinstance(cell, MultiReviewedLocalScopeCertificate)
    assert len(cell.semantic_reviews) == count
    assert cell.exact_zero_area_source_triangles_excluded == 0
    assert all(r.zero_area_source_face_indices == () for r in cell.semantic_reviews)
    assert all(r.human_decisions_sha256 == certificate.human_decision_content_sha256
               for r in cell.semantic_reviews)
    provider = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
    )
    assert provider.validate_polyline(((2.5, 2.5, 0.), (7.5, 7.5, 0.)))
    assert certificate.overall_formal_case_execution_enabled is False


def test_unsupplied_third_ambiguous_component_remains_review() -> None:
    proposal, evidence, contract, numerics = _multi_inputs(3)
    certificate, result = _apply(proposal, _decision(proposal), evidence, contract, numerics)
    assert certificate is None
    assert result["cell_checks"][0]["reason"] == "UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN"
    assert result["cell_checks"][0]["source_object_id"] == "SYNTHETIC_AMBIGUOUS_SURFACE_2"


def test_approved_no_solid_profile_cannot_remove_actual_triangle_contact() -> None:
    proposal, evidence, contract, numerics = _multi_inputs(contact=True)
    certificate, result = _apply(proposal, _decision(proposal), evidence, contract, numerics)
    assert certificate is None
    assert result["cell_checks"][0]["reason"] == "UNCLASSIFIED_SOURCE_BODY_CONTACT"
    assert result["cell_checks"][0]["source_object_id"] == "SYNTHETIC_AMBIGUOUS_SURFACE_0"


def test_pending_multi_profiles_block_without_consuming_source() -> None:
    proposal, _, contract, numerics = _multi_inputs()
    certificate, result = _apply(proposal, _decision(proposal, "PENDING"), {}, contract, numerics)
    assert certificate is None
    assert result["status"] == "BLOCKED_NEW_HUMAN_APPROVAL_REQUIRED"


def test_extra_profile_mutation_cannot_reuse_prior_direct_human_receipt() -> None:
    proposal, evidence, contract, numerics = _multi_inputs()
    decision = _decision(proposal)
    cell = proposal.cells[0].model_copy(update={"extra_surface_semantics": ()})
    with pytest.raises(ValueError, match="proposal/human receipt"):
        _apply(proposal.model_copy(update={"cells": (cell,)}),
               decision, evidence, contract, numerics)


def test_provider_operation_revalidates_nested_certificate_before_path() -> None:
    proposal, evidence, contract, numerics = _multi_inputs()
    decision = _decision(proposal)
    certificate, _ = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None
    provider = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
    )
    object.__setattr__(provider.certificate, "union_wkb_sha256", "f" * 64)
    with pytest.raises(ValueError, match="certificate/domain binding"):
        provider.validate_polyline(((2.5, 2.5, 0.), (7.5, 7.5, 0.)))


def test_exact_segment_intervals_preserve_nextafter_gap_with_large_endpoints() -> None:
    start, end = (-1e18, 0., 0.), (1e18, 0., 0.)
    left_edge, right_edge = 5., math.nextafter(5., math.inf)
    # Historical float subtraction loses the genuine representable gap.
    assert (left_edge - start[0]) / (end[0] - start[0]) == (
        (right_edge - start[0]) / (end[0] - start[0])
    )
    left = _segment_interval(start, end, ((-1e18, -1., -1.), (left_edge, 1., 1.)))
    right = _segment_interval(start, end, ((right_edge, -1., -1.), (1e18, 1., 1.)))
    assert left is not None and right is not None
    assert left[1] < right[0]


def test_cli_explicit_profile_lists_preserve_empty_zero_arrays() -> None:
    proposal, _, _, _ = _multi_inputs()
    profiles = proposal.cells[0].all_surface_semantics
    loaded = _proposed_semantics({"profiles_by_cell_index": {
        "0": [p.model_dump(mode="json") for p in profiles],
    }})
    assert loaded == {"0": profiles}


@pytest.mark.parametrize("count", [1, 2])
def test_inner_provider_operation_rejects_postconstruction_human_receipt_mutation(
    count: int,
) -> None:
    proposal, evidence, contract, numerics = _multi_inputs(count)
    decision = _decision(proposal)
    certificate, _ = _apply(proposal, decision, evidence, contract, numerics)
    assert certificate is not None
    union = load_scoped_authority(
        proposal, decision, certificate, evidence, contract, numerics, expected_pins=proposal.pins,
        expected_certificate_content_sha256=content_sha256(certificate.model_dump(mode="json")),
    )
    inner = union._provider(union.certificate.cells[0])
    assert isinstance(inner, MultiReviewedRestrictedPhysicalProvider)
    points = ((2.5, 2.5, 0.), (7.5, 7.5, 0.))
    assert inner.validate_polyline(points)
    object.__setattr__(inner.certificate.semantic_reviews[0], "human_decisions_sha256", "f" * 64)
    with pytest.raises(ValueError, match="human decision|certificate/human receipt"):
        inner.validate_polyline(points)
    # The standalone provider detached its wrapper on construction; the original
    # union remains intact and independently revalidates its own expected hashes.
    assert union.validate_polyline(points)
