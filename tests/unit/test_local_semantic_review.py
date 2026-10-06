"""Synthetic-only engineering review receipts; no school authority is applied."""

from __future__ import annotations

import importlib.util
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from shapely.geometry import box

from amidst.local_semantic_review import (
    ReviewedRestrictedLocalPhysicalProvider,
    ScopedSourceSurfaceReview,
    regenerate_reviewed_certificate,
    validate_scoped_source_review,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import GeometryAuthorityError

_SPEC = importlib.util.spec_from_file_location(
    "synthetic_scope_fixtures",
    Path(__file__).with_name("test_local_physical_scopes.py"),
)
assert _SPEC is not None and _SPEC.loader is not None
_FAKE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_FAKE)

SOURCE = "a" * 64
HUMAN = "b" * 64
MESH = "c" * 64
GEOMETRY = "d" * 64


def _evidence(*, degenerate: bool = True) -> dict[str, Any]:
    return {
        "source_sha256": SOURCE,
        "meshes": [
            {
                "mesh_id": MESH,
                "geometry_sha256": GEOMETRY,
                "source_object_id": "SYNTHETIC_SURFACE",
                "vertices": [
                    [1.0, 1.0, 0.0],
                    [1.0, 2.0, 0.0],
                    [1.0 if degenerate else 2.0, 3.0, 0.0],
                ],
                "triangles": [[0, 1, 2]],
                "triangle_source_face_indices": [7],
                "components": [{"component_id": "synthetic-part", "source_triangle_indices": [0]}],
            }
        ],
        "regions": [
            {
                "region_id": "BODY:synthetic",
                "kind": "FULL_BODY_CONTEXT",
                "selections": [{"mesh_id": MESH, "component_ids": ["synthetic-part"]}],
            }
        ],
    }


def _receipt(evidence: dict[str, Any]) -> ScopedSourceSurfaceReview:
    return ScopedSourceSurfaceReview(
        decision_id="SYNTHETIC_HR_ONLY",
        decision="APPROVE",
        decision_option="LOCAL_SOURCE_SURFACE_ONLY",
        human_approval_id="FAKE_TEST_APPROVAL",
        human_decisions_sha256=HUMAN,
        source_sha256=SOURCE,
        evidence_content_sha256=content_sha256(evidence),
        source_mesh_id=MESH,
        source_geometry_sha256=GEOMETRY,
        source_object_id="SYNTHETIC_SURFACE",
        source_component_id="synthetic-part",
        region_id="BODY:synthetic",
        body_envelope_bounds_bu=((0.0, 0.0, -1.0), (10.0, 10.0, 3.0)),
        zero_area_source_face_indices=(7,),
    )


def _validate(
    receipt: ScopedSourceSurfaceReview,
    evidence: dict[str, Any],
    **overrides: str,
) -> ScopedSourceSurfaceReview:
    options = {
        "expected_receipt_content_sha256": content_sha256(receipt.model_dump(mode="json")),
        "expected_human_decisions_sha256": HUMAN,
        "region_id": "BODY:synthetic",
    } | overrides
    return validate_scoped_source_review(receipt, evidence, **options)


def test_synthetic_exact_surface_receipt_is_bounded_and_hash_bound() -> None:
    evidence = _evidence()
    receipt = _validate(_receipt(evidence), evidence)
    assert receipt.contains_envelope((1.0, 1.0, 0.0), (9.0, 9.0, 2.0))
    assert not receipt.contains_envelope((-0.001, 1.0, 0.0), (9.0, 9.0, 2.0))
    assert receipt.matches_component(evidence["meshes"][0], "synthetic-part")
    assert not receipt.matches_component(evidence["meshes"][0], "other-part")
    assert receipt.whole_component_approved is False


@pytest.mark.parametrize(
    "override,error",
    [
        ({"expected_receipt_content_sha256": "e" * 64}, "receipt hash"),
        ({"expected_human_decisions_sha256": "e" * 64}, "decisions hash"),
        ({"region_id": "BODY:other"}, "region binding"),
    ],
)
def test_independent_receipt_decision_and_region_hashes_cannot_be_replaced(
    override: dict[str, str],
    error: str,
) -> None:
    evidence = _evidence()
    with pytest.raises(ValueError, match=error):
        _validate(_receipt(evidence), evidence, **override)


def test_surface_receipt_cannot_waive_a_nondegenerate_triangle() -> None:
    evidence = _evidence(degenerate=False)
    with pytest.raises(ValueError, match="nondegenerate"):
        _validate(_receipt(evidence), evidence)


def test_source_evidence_changes_are_rejected_before_semantic_use() -> None:
    evidence = _evidence()
    receipt = _receipt(evidence)
    changed = deepcopy(evidence)
    changed["meshes"][0]["vertices"][0][0] += 0.001
    with pytest.raises(ValueError, match="evidence/region binding"):
        _validate(receipt, changed)


def test_wrong_mesh_component_and_unreviewed_face_remain_rejected() -> None:
    evidence = _evidence()
    receipt = _receipt(evidence)
    for change in (
        {"source_geometry_sha256": "f" * 64},
        {"source_object_id": "SYNTHETIC_OTHER"},
        {"source_component_id": "SYNTHETIC_OTHER"},
        {"zero_area_source_face_indices": (6,)},
    ):
        with pytest.raises(ValueError):
            _validate(receipt.model_copy(update=change), evidence)


def test_revalidation_refuses_forged_approval_and_unbounded_scope() -> None:
    evidence = _evidence()
    receipt = _receipt(evidence)
    for change in (
        {"decision": "KEEP_REVIEW"},
        {"whole_component_approved": True},
        {"body_envelope_bounds_bu": ((0.0, 0.0, 0.0), (0.0, 1.0, 1.0))},
    ):
        with pytest.raises(ValidationError):
            _validate(receipt.model_copy(update=change), evidence)


def _proof_inputs(extra: dict[str, Any] | None = None) -> tuple[Any, ...]:
    contract = _FAKE._contract()
    enclosure = _FAKE._unknown_enclosure()
    points = enclosure["vertices"] + [[5.0, 4.0, 0.0], [5.0, 5.0, 0.0], [5.0, 6.0, 0.0]]
    triangles = enclosure["triangles"] + [[8, 9, 10], [9, 8, 10]]
    reviewed = _FAKE._mesh("SYNTHETIC_REVIEWED_SURFACES", points, triangles)
    evidence = _FAKE._atlas(contract, [reviewed, *([] if extra is None else [extra])])
    receipt = ScopedSourceSurfaceReview(
        decision_id="SYNTHETIC_HR_ONLY",
        decision="APPROVE",
        decision_option="LOCAL_SOURCE_SURFACE_ONLY",
        human_approval_id="FAKE_TEST_APPROVAL",
        human_decisions_sha256=HUMAN,
        source_sha256=_FAKE.SOURCE,
        evidence_content_sha256=content_sha256(evidence),
        source_mesh_id=reviewed["mesh_id"],
        source_geometry_sha256=reviewed["geometry_sha256"],
        source_object_id=reviewed["source_object_id"],
        source_component_id="synthetic-component",
        region_id=_FAKE.REGION,
        body_envelope_bounds_bu=((1.0, 1.0, -1.0), (9.0, 9.0, 3.0)),
        zero_area_source_face_indices=(12, 13),
    )
    return receipt, evidence, _FAKE._domain(contract), contract


def _reviewed_proof(
    receipt: ScopedSourceSurfaceReview, evidence: dict[str, Any], domain: Any, contract: Any
) -> Any:
    return regenerate_reviewed_certificate(
        receipt,
        evidence,
        domain,
        box(2.0, 2.0, 8.0, 8.0),
        _FAKE.REGION,
        contract,
        _FAKE._numerics(),
        support_source_faces=frozenset((_FAKE.FLOOR_OBJECT, i) for i in range(4)),
        expected_receipt_content_sha256=content_sha256(receipt.model_dump(mode="json")),
        expected_human_decisions_sha256=HUMAN,
        expected_evidence_content_sha256=content_sha256(evidence),
    )


def test_reviewed_proof_changes_only_exact_bounded_human_semantics_and_preserves_source() -> None:
    receipt, evidence, domain, contract = _proof_inputs()
    original = deepcopy(evidence)
    strict, strict_detail = _FAKE._certify(evidence, contract)
    assert strict is None and strict_detail["reason"] == "DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE"
    certificate, detail = _reviewed_proof(receipt, evidence, domain, contract)
    assert certificate is not None, detail
    assert certificate.exact_zero_area_source_triangles_excluded == 2
    assert certificate.original_source_geometry_modified is False
    assert certificate.whole_component_authority_upgraded is False
    assert evidence == original
    provider = ReviewedRestrictedLocalPhysicalProvider(
        certificate,
        domain,
        contract,
        content_sha256(certificate.model_dump(mode="json")),
        HUMAN,
    )
    assert provider.validate_polyline(((3.0, 5.0, 0.0), (7.0, 5.0, 0.0)))
    with pytest.raises(GeometryAuthorityError, match="OUTSIDE_APPROVED_LOCAL"):
        provider.validate_polyline(((1.9, 5.0, 0.0), (7.0, 5.0, 0.0)))
    strict_again, _ = _FAKE._certify(evidence, contract)
    assert strict_again is None


def test_reviewed_proof_refuses_body_envelope_outside_explicit_human_bound() -> None:
    receipt, evidence, domain, contract = _proof_inputs()
    receipt = receipt.model_copy(
        update={"body_envelope_bounds_bu": ((2.0, 2.0, -1.0), (8.0, 8.0, 3.0))}
    )
    certificate, detail = _reviewed_proof(receipt, evidence, domain, contract)
    assert certificate is None
    assert detail["reason"] == "OUTSIDE_HUMAN_REVIEWED_BODY_ENVELOPE"


@pytest.mark.parametrize("extra_kind", ["wall", "degenerate", "closed_solid"])
def test_unreviewed_collision_degenerate_and_solid_interior_are_still_refused(
    extra_kind: str,
) -> None:
    if extra_kind == "wall":
        extra = _FAKE._mesh(
            "SYNTHETIC_OTHER_WALL", [[2.1, 1.0, 0.0], [2.1, 9.0, 0.0], [2.1, 9.0, 3.0]], [[0, 1, 2]]
        )
        reason = "UNCLASSIFIED_SOURCE_BODY_CONTACT"
    elif extra_kind == "degenerate":
        extra = _FAKE._mesh(
            "SYNTHETIC_OTHER_SEAM", [[6.0, 4.0, 1.0], [6.0, 5.0, 1.0], [6.0, 6.0, 1.0]], [[0, 1, 2]]
        )
        reason = "DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE"
    else:
        extra = _FAKE._unknown_enclosure()
        reason = "INSIDE_UNCLASSIFIED_CLOSED_COMPONENT"
    receipt, evidence, domain, contract = _proof_inputs(extra)
    certificate, detail = _reviewed_proof(receipt, evidence, domain, contract)
    assert certificate is None
    assert detail["reason"] == reason


def test_reviewed_provider_rejects_forged_digest_and_expanded_certificate() -> None:
    receipt, evidence, domain, contract = _proof_inputs()
    certificate, detail = _reviewed_proof(receipt, evidence, domain, contract)
    assert certificate is not None, detail
    digest = content_sha256(certificate.model_dump(mode="json"))
    with pytest.raises(ValueError, match="certificate/human decisions hash"):
        ReviewedRestrictedLocalPhysicalProvider(certificate, domain, contract, digest, "f" * 64)
    changed = certificate.model_copy(
        update={
            "physical_certificate": certificate.physical_certificate.model_copy(
                update={
                    "footpoint_bounds_bu": ((1.0, 1.0, -0.001), (9.0, 9.0, 0.001)),
                }
            )
        }
    )
    with pytest.raises(ValueError, match="outside approved semantic body envelope"):
        ReviewedRestrictedLocalPhysicalProvider(
            changed,
            domain,
            contract,
            content_sha256(changed.model_dump(mode="json")),
            HUMAN,
        )
