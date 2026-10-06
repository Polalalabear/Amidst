"""Physical permission comes from actual support, preserving holes and seams."""

import copy
import hashlib
import json
from typing import Any

import pytest

from amidst.architectural_scale import ArchitecturalScale
from amidst.physical_authority import PhysicalPolicy
from amidst.scene_geometry import (
    Authority,
    FloorAuthority,
    GeometryAuthorityError,
    GeometryRole,
    GeometrySupport,
    GeometrySurface,
)
from amidst.walkable_clearance import (
    WalkableClearanceDomain,
    build_source_bound_floor_support,
)

SOURCE = "a" * 64


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _scale(ratio: float = 1.0) -> ArchitecturalScale:
    return ArchitecturalScale(
        source_asset_sha256=SOURCE, metres_per_blender_unit=ratio,
        authority=Authority.APPROVED, approval_id="user-model-scale", evidence_ids=("user",),
    )


def _policy() -> PhysicalPolicy:
    return PhysicalPolicy(
        policy_id="approved-cylinder", config_version="test-source-bound",
        authority=Authority.APPROVED, body_model="UPRIGHT_CYLINDER",
        trajectory_reference="FLOOR_CONTACT_POINT", body_radius_m=.30, body_height_m=1.70,
        body_clearance_m=.05, portal_horizontal_clearance_m=.05,
        portal_vertical_clearance_m=.10, collision_tolerance_m=.001,
        clearance_comparison="MINIMUM_INCLUSIVE", collision_comparison="CONTACT_INCLUSIVE",
        approval_id="user-policy", evidence_ids=("user",),
    )


def _floor() -> FloorAuthority:
    return FloorAuthority(
        floor_id="1F", point=(0., 0., 20.), normal=(0., 0., 1.),
        authority=Authority.APPROVED, approval_id="source-supported", evidence_ids=("source-face",),
    )


def _quad(
    x0: float = 0, x1: float = 10, y0: float = 0, y1: float = 10, z: float = 20,
) -> dict[str, Any]:
    return {
        "vertices": [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]],
        "triangles": [[0, 1, 2], [0, 2, 3]],
    }


def _surface(identity: str, **dimensions: float) -> GeometrySurface:
    mesh = _quad(**dimensions)
    return GeometrySurface(
        surface_id=identity, source_object_id="opaque-source", source_face_indices=(3,),
        role=GeometryRole.WALKABLE, floor_ids=("1F",),
        vertices=tuple(tuple(point) for point in mesh["vertices"]),
        triangles=tuple(tuple(triangle) for triangle in mesh["triangles"]),
        semantic_authority=Authority.APPROVED, physical_authority=Authority.APPROVED,
        support=GeometrySupport.SURFACE, approval_id="source-supported",
        evidence_ids=(f"SOURCE_SHA256:{SOURCE}",),
    )


def _domain(*surfaces: GeometrySurface, scale: float = 1) -> WalkableClearanceDomain:
    return WalkableClearanceDomain.from_surfaces(
        tuple(surfaces), floor=_floor(), scale=_scale(scale), policy=_policy(),
        expected_source_sha256=SOURCE,
    )


def _patch(**dimensions: float) -> dict[str, Any]:
    result = {
        "source_object_id": "opaque-source", "source_face_indices": [3],
        "triangle_source_face_indices": [3, 3], **_quad(**dimensions),
    }
    result["geometry_sha256"] = _digest(result)
    return result


def _evidence(patches: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    audit = {
        "source_sha256": SOURCE, "objects": [{
            "object": "walk", "declared_floor_label": "1F",
            "custom_properties": {"semantic_class": "WALKABLE"}, **_quad(z=25),
        }],
    }
    survey = {
        "source_sha256": SOURCE, "source_preserved": True,
        "audit_content_sha256": _digest(audit), "regions": [{
            "kind": "FLOOR_SUPPORT", "region_id": "walk", "floor_id": "1F",
            "complete": True, "patches": patches,
        }],
    }
    return audit, survey


def _report(
    audit: dict[str, Any], survey: dict[str, Any], *, approved: tuple[str, ...] = ("walk",),
) -> dict[str, Any]:
    return build_source_bound_floor_support(
        audit, survey, scale=_scale(), approved_walkable_ids=approved,
        approval_id="explicit-source-floor-review", support_heights_bu={"1F": 20.},
        contact_tolerance_m=.001, horizontal_normal_abs_z_min=.984807753012208,
        max_triangles_per_region=20000, numeric_epsilon=1e-9,
    )


def test_union_before_erosion_removes_internal_seam() -> None:
    left, right = _surface("left", x1=5), _surface("right", x0=5)
    domain = _domain(left, right)
    assert domain.validate_point((5., 5., 20.)).valid
    assert domain.validate_segment((1., 5., 20.), (9., 5., 20.)).valid
    assert domain.report()["support_components"] == 1
    assert domain.report()["support_area_bu2"] == 100
    assert _domain(left).validate_point((5., 5., 20.)).reason == "INSUFFICIENT_WALKABLE_CLEARANCE"


def test_clearance_threshold_equality_passes_without_tolerance_relaxation() -> None:
    domain = _domain(_surface("support"))
    threshold = domain.required_clearance_bu
    assert domain.validate_point((threshold, 5., 20.)).valid
    assert not domain.validate_point((threshold - .0001, 5., 20.)).valid
    assert domain.validate_point((threshold + .0001, 5., 20.)).valid
    assert domain.validate_segment((threshold, 1., 20.), (threshold, 9., 20.)).valid


def test_actual_hole_and_segment_crossing_are_not_filled() -> None:
    domain = _domain(
        _surface("bottom", y1=4), _surface("top", y0=6),
        _surface("left", x1=4, y0=4, y1=6), _surface("right", x0=6, y0=4, y1=6),
    )
    assert domain.report()["support_holes"] == 1
    assert domain.validate_point((5., 5., 20.)).reason == "OUTSIDE_APPROVED_WALKABLE"
    assert domain.validate_segment((2., 5., 20.), (8., 5., 20.)).reason == (
        "OUTSIDE_APPROVED_WALKABLE"
    )


def test_disconnected_islands_and_non_finite_input_are_explicit() -> None:
    domain = _domain(_surface("left", x1=4), _surface("right", x0=6))
    assert domain.report()["support_components"] == 2
    assert not domain.validate_segment((2., 5., 20.), (8., 5., 20.)).valid
    with pytest.raises(ValueError, match="finite"):
        domain.validate_point((float("nan"), 5., 20.))


def test_surface_order_and_duplicate_overlap_do_not_change_domain() -> None:
    one, two = _surface("one", x1=6), _surface("two", x0=4)
    assert _domain(one, two).report() == _domain(two, one).report()
    assert _domain(one, two).report()["support_area_bu2"] == 100


def test_point_support_height_and_incompatible_layer_are_rejected() -> None:
    domain = _domain(_surface("surface"))
    assert domain.validate_point((5., 5., 20.01)).reason == "OFF_SUPPORT_HEIGHT"
    with pytest.raises(GeometryAuthorityError, match="INCOMPATIBLE_SUPPORT_HEIGHT"):
        _domain(_surface("different-layer", z=20.01))


def test_actual_surface_contact_cannot_add_plane_and_footpoint_tolerances_twice() -> None:
    domain = _domain(_surface("raised-raw-support", z=20.0006))
    assert not domain.validate_point((5., 5., 19.999)).valid
    assert not domain.validate_segment((1., 5., 19.999), (9., 5., 19.999)).valid
    assert domain.validate_point((5., 5., 20.0006)).valid
    band = domain.actual_contact_height_band(domain._geometry())
    assert band == pytest.approx((19.9996, 20.0016))


def test_raw_slope_is_checked_analytically_without_flattening_or_frame_sampling() -> None:
    surface = _surface("actual-affine-slope")
    points = tuple((x, y, 19.9992 + .00016 * x) for x, y, _ in surface.vertices)
    surface = surface.model_copy(update={"vertices": points})
    domain = _domain(surface)
    assert domain.validate_segment((1., 5., 19.99936), (9., 5., 20.00064)).valid
    assert not domain.validate_segment((1., 5., 19.999), (9., 5., 19.999)).valid
    assert domain.report()["segment_height_validation"] == "ANALYTIC_SOURCE_TRIANGLE_PARTITIONS"


def test_source_height_at_internal_seam_limits_contact_to_actual_layers() -> None:
    domain = _domain(_surface("lower", x1=5, z=19.9994),
                     _surface("upper", x0=5, z=20.0006))
    assert domain.validate_segment((1., 5., 20.), (9., 5., 20.)).valid
    assert not domain.validate_segment((1., 5., 19.999), (9., 5., 19.999)).valid


def test_review_or_missing_source_binding_cannot_supply_navigation() -> None:
    surface = _surface("support")
    review = surface.model_copy(update={"physical_authority": Authority.HUMAN_REVIEW})
    with pytest.raises(GeometryAuthorityError, match="SUPPORT_NOT_APPROVED"):
        _domain(review)
    forged = surface.model_copy(update={"evidence_ids": ("unbound",)})
    with pytest.raises(GeometryAuthorityError, match="SUPPORT_NOT_APPROVED"):
        _domain(forged)
    with pytest.raises(ValueError, match="source SHA"):
        WalkableClearanceDomain.from_surfaces(
            (surface,), floor=_floor(), scale=_scale(), policy=_policy(),
            expected_source_sha256="b" * 64,
        )


def test_approved_scale_dual_units_and_display_contour_scope() -> None:
    domain = _domain(_surface("support", x1=100, y1=100), scale=.0247)
    assert domain.required_clearance_m == pytest.approx(.35)
    assert domain.required_clearance_bu == pytest.approx(.35 / .0247)
    assert domain.validate_point((50., 50., 20.)).clearance_m == pytest.approx(1.235)
    assert domain.report()["display_contour_is_physical_authority"] is False
    assert domain.report()["outside_is_wall_or_occluder"] is False


def test_annotation_proxy_is_replaced_by_exact_bound_source_support() -> None:
    audit, survey = _evidence([_patch()])
    before = copy.deepcopy(audit)
    report = _report(audit, survey)
    assert audit == before
    assert report["approved_supported_subdomain_count"] == 1
    assert report["whole_annotation_supported_count"] == 1
    support = report["support_surfaces"][0]
    assert all(point[2] == 20 for point in support["vertices"])
    assert support["source_object_id"] == "opaque-source"
    assert support["source_face_indices"] == [3]
    assert report["body_or_ceiling_clearance_approved"] is False


def test_partial_source_support_approves_only_intersection() -> None:
    audit, survey = _evidence([_patch(x1=4)])
    report = _report(audit, survey)
    row = report["walkable_reviews"][0]
    assert row["authority"] == "APPROVED"
    assert row["support_coverage_ratio"] == .4
    assert row["uncovered_area_bu2"] == 60
    assert row["uncovered_authority"] == "HUMAN_REVIEW"
    assert all(p[0] <= 4 for surface in report["support_surfaces"] for p in surface["vertices"])


def test_missing_semantic_approval_or_incomplete_source_keeps_review() -> None:
    audit, survey = _evidence([_patch()])
    assert not _report(audit, survey, approved=())["support_surfaces"]
    survey["regions"][0]["complete"] = False
    row = _report(audit, survey)["walkable_reviews"][0]
    assert row["authority"] == "HUMAN_REVIEW"
    assert "SOURCE_REGION_INCOMPLETE" in row["reason_codes"]


def test_source_mutation_and_annotation_mutation_fail_closed() -> None:
    audit, survey = _evidence([_patch()])
    survey["regions"][0]["patches"][0]["vertices"][0][2] = 21
    with pytest.raises(ValueError, match="geometry_sha256"):
        _report(audit, survey)
    audit, survey = _evidence([_patch()])
    audit["objects"][0]["vertices"][0][0] = 1
    with pytest.raises(ValueError, match="audit content"):
        _report(audit, survey)


def test_no_floor_or_other_local_height_is_not_fabricated_or_flattened() -> None:
    audit, survey = _evidence([_patch(z=21)])
    report = _report(audit, survey)
    assert not report["support_surfaces"]
    row = report["walkable_reviews"][0]
    assert row["other_height_source_evidence"][0]["z_range_bu"] == [21, 21]
    assert row["geometry_flattened"] is False
    assert "NO_COMPATIBLE_ACTUAL_SOURCE_SUPPORT" in row["reason_codes"]


def test_source_hole_remains_review_and_support_hole() -> None:
    patches = [_patch(y1=4), _patch(y0=6), _patch(x1=4, y0=4, y1=6),
               _patch(x0=6, y0=4, y1=6)]
    audit, survey = _evidence(patches)
    row = _report(audit, survey)["walkable_reviews"][0]
    assert row["support_holes"] == 1
    assert row["uncovered_area_bu2"] == 4


def test_source_input_order_preserves_derived_ids_and_geometry() -> None:
    audit, survey = _evidence([_patch(x1=4), _patch(x0=6)])
    first = _report(audit, survey)
    survey["regions"][0]["patches"].reverse()
    second = _report(audit, survey)
    assert first["support_surfaces"] == second["support_surfaces"]
    assert first["walkable_reviews"] == second["walkable_reviews"]


def test_duplicate_annotation_and_mismatched_region_floor_fail_fast() -> None:
    audit, survey = _evidence([_patch()])
    audit["objects"].append(copy.deepcopy(audit["objects"][0]))
    survey["audit_content_sha256"] = _digest(audit)
    with pytest.raises(ValueError, match="duplicate WALKABLE"):
        _report(audit, survey)
    audit, survey = _evidence([_patch()])
    survey["regions"][0]["floor_id"] = "2F"
    with pytest.raises(ValueError, match="floor binding"):
        _report(audit, survey)
