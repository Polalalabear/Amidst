"""Physical authority stays fail-closed despite internally consistent proxies."""

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from amidst.physical_floor_stair_review import review_floor_stairs

SOURCE = "a" * 64


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _quad(
    z: float, *, x0: float = 0, x1: float = 10, y0: float = 0, y1: float = 10
) -> dict[str, Any]:
    return {
        "vertices": [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]],
        "triangles": [[0, 1, 2], [0, 2, 3]],
    }


def _patch(z: float = 20, *, name: str = "opaque_source", **bounds: float) -> dict[str, Any]:
    result = {
        "source_object_id": name,
        "source_face_indices": [3],
        "triangle_source_face_indices": [3, 3],
        **_quad(z, **bounds),
    }
    result["geometry_sha256"] = _digest(result)
    return result


def _audit() -> dict[str, Any]:
    return {
        "source_sha256": SOURCE,
        "objects": [
            {
                "object": "walk",
                "declared_floor_label": "1F",
                "custom_properties": {"semantic_class": "WALKABLE"},
                **_quad(25),
            }
        ],
    }


def _survey(audit: dict[str, Any], patches: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "source_sha256": SOURCE,
        "source_preserved": True,
        "audit_content_sha256": _digest(audit),
        "regions": [
            {
                "region_id": "walk",
                "kind": "FLOOR_SUPPORT",
                "floor_id": "1F",
                "complete": True,
                "patches": [_patch()] if patches is None else patches,
            }
        ],
    }


def _config() -> dict[str, Any]:
    # These fake source coordinates intentionally exercise the historical 1:1
    # diagnostic contract; the active school authority is tested separately.
    config = json.loads(Path("configs/scene_validation_v1.json").read_text())
    config["floor_planes"] = {
        "1F": {"height_m": 25.0}, "2F": {"height_m": 165.0},
    }
    config["floor_stair_review"] = {
        "horizontal_normal_abs_z_min": math.cos(math.radians(10)),
        "horizontal_layer_tolerance_units": 0.25,
        "max_triangles_per_region": 20000,
        "max_pair_intersections": 8192,
        "floor_support_bands": {"1F": [10, 30], "2F": [150, 175]},
    }
    return config


def _review(patches: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    audit = _audit()
    return review_floor_stairs(audit, _survey(audit, patches), _config())


def test_actual_floor_offset_is_not_approved_from_proxy_alignment() -> None:
    result = _review()
    floor = result["floor_reviews"][0]
    assert floor["dominant_support"]["coverage_ratio"] == 1
    assert floor["proposed_minus_actual_z_units"] == 5
    assert floor["status"] == "HUMAN_REVIEW"
    assert "PROPOSED_PLANE_DIFFERS_FROM_ACTUAL_MESH_SUPPORT" in floor["reason_codes"]
    assert result["floor_authority"] == "HUMAN_REVIEW"
    assert result["geometry_modified"] is False


def test_matching_source_plane_is_measurement_not_scale_or_camera_approval() -> None:
    result = _review([_patch(25)])
    assert result["floor_reviews"][0]["status"] == "HIGH_CONFIDENCE"
    assert result["floor_reviews"][0]["physical_floor_approved"] is False
    assert result["scale_authority"] == "HUMAN_REVIEW"
    assert result["camera_plane_authority"] == "HUMAN_REVIEW"


def test_exact_footprint_coverage_does_not_fill_the_source_hole() -> None:
    patches = [_patch(20, x1=4), _patch(20, name="other_source", x0=6)]
    floor = _review(patches)["floor_reviews"][0]
    assert floor["dominant_support"]["coverage_ratio"] == pytest.approx(0.8)
    assert floor["dominant_support"]["covered_area_units2"] == pytest.approx(80)


def test_duplicate_surface_overlap_cannot_inflate_coverage() -> None:
    floor = _review([_patch(20, x1=4), _patch(20, name="duplicate_object", x1=4)])["floor_reviews"][
        0
    ]
    assert floor["dominant_support"]["coverage_ratio"] == pytest.approx(0.4)
    assert "INCOMPLETE_ACTUAL_WALKABLE_SUPPORT" in floor["reason_codes"]


def test_equivalent_coverage_does_not_prefer_slab_underside_from_rounding() -> None:
    result = _review([_patch(15), _patch(20, name="upper", x1=9.99999999999)])
    floor = result["floor_reviews"][0]
    assert len(floor["physical_support_layers"]) == 2
    assert floor["dominant_support"]["representative_z_units"] == 20
    assert floor["status"] == "HUMAN_REVIEW"


def test_no_source_floor_does_not_fabricate_support() -> None:
    floor = _review([])["floor_reviews"][0]
    assert floor["dominant_support"] is None
    assert floor["physical_support_layers"] == []
    assert floor["status"] == "HUMAN_REVIEW"


def test_source_hash_mismatch_rejected() -> None:
    audit = _audit()
    survey = _survey(audit)
    survey["source_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="SHA binding mismatch"):
        review_floor_stairs(audit, survey, _config())


def test_proxy_mutation_rejected_without_new_source_bound_snapshot() -> None:
    audit = _audit()
    survey = _survey(audit)
    audit["objects"][0]["vertices"][0][2] = 20
    with pytest.raises(ValueError, match="audit content"):
        review_floor_stairs(audit, survey, _config())


def test_source_geometry_mutation_rejected_without_matching_digest() -> None:
    audit = _audit()
    survey = _survey(audit)
    survey["regions"][0]["patches"][0]["vertices"][0][2] = 25
    with pytest.raises(ValueError, match="geometry_sha256"):
        review_floor_stairs(audit, survey, _config())


def test_missing_preservation_attestation_rejected() -> None:
    audit = _audit()
    survey = _survey(audit)
    survey["source_preserved"] = False
    with pytest.raises(ValueError, match="source preservation"):
        review_floor_stairs(audit, survey, _config())


def test_invalid_triangle_is_rejected_even_with_matching_content_hash() -> None:
    audit = _audit()
    patch = _patch()
    patch["triangles"][0] = [0, 0, 1]
    patch["geometry_sha256"] = _digest({k: v for k, v in patch.items() if k != "geometry_sha256"})
    with pytest.raises(ValueError, match="distinct valid indices"):
        review_floor_stairs(audit, _survey(audit, [patch]), _config())


def test_forged_source_face_identity_is_rejected() -> None:
    audit = _audit()
    patch = _patch()
    patch["triangle_source_face_indices"][0] = 99
    patch["geometry_sha256"] = _digest({k: v for k, v in patch.items() if k != "geometry_sha256"})
    with pytest.raises(ValueError, match="exported source face"):
        review_floor_stairs(audit, _survey(audit, [patch]), _config())


def test_triangle_budget_is_structured_review_not_silent_failure() -> None:
    audit = _audit()
    config = _config()
    config["floor_stair_review"]["max_triangles_per_region"] = 1
    result = review_floor_stairs(audit, _survey(audit), config)
    floor = result["floor_reviews"][0]
    assert floor["reason_codes"] == ["GEOMETRY_BUDGET_EXCEEDED"]
    assert "triangle budget" in floor["error"]
    assert floor["physical_floor_approved"] is False


def test_union_budget_is_structured_review() -> None:
    audit = _audit()
    config = _config()
    config["floor_stair_review"]["max_pair_intersections"] = 1
    result = review_floor_stairs(audit, _survey(audit), config)
    assert result["floor_reviews"][0]["reason_codes"] == ["GEOMETRY_BUDGET_EXCEEDED"]
    assert (
        result["floor_reviews"][0]["partial_ray_evidence"][0]["actual_source_hits"][0]["z_units"]
        == 20
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("horizontal_normal_abs_z_min", 1.1),
        ("horizontal_normal_abs_z_min", math.nan),
        ("max_triangles_per_region", -1),
        ("max_triangles_per_region", True),
        ("horizontal_layer_tolerance_units", 0),
    ],
)
def test_invalid_review_config_fails_fast(field: str, value: Any) -> None:
    audit = _audit()
    config = _config()
    config["floor_stair_review"][field] = value
    with pytest.raises(ValueError):
        review_floor_stairs(audit, _survey(audit), config)


def test_duplicate_region_identity_rejected() -> None:
    audit = _audit()
    survey = _survey(audit)
    survey["regions"].append(copy.deepcopy(survey["regions"][0]))
    with pytest.raises(ValueError, match="duplicate region"):
        review_floor_stairs(audit, survey, _config())


def test_missing_source_region_stays_review() -> None:
    audit = _audit()
    survey = _survey(audit)
    survey["regions"] = []
    result = review_floor_stairs(audit, survey, _config())
    assert result["floor_reviews"][0]["reason_codes"] == ["MISSING_SOURCE_REGION"]


def test_incomplete_region_cannot_approve_even_aligned_source() -> None:
    audit = _audit()
    survey = _survey(audit, [_patch(25)])
    survey["regions"][0]["complete"] = False
    result = review_floor_stairs(audit, survey, _config())
    assert result["floor_reviews"][0]["status"] == "HUMAN_REVIEW"
    assert result["floor_reviews"][0]["reason_codes"] == ["SOURCE_REGION_SELECTION_INCOMPLETE"]


def test_older_camera_calibration_is_not_school_v3_plane_authority() -> None:
    audit = _audit()
    result = review_floor_stairs(
        audit, _survey(audit), _config(), camera_calibration={"source_asset_sha256": "b" * 64}
    )
    assert result["camera_reason"] == "CAMERA_CALIBRATION_SOURCE_DIFFERS_FROM_SCHOOL_V3"
    assert result["camera_plane_authority"] == "HUMAN_REVIEW"


def _stair_audit() -> dict[str, Any]:
    rows = [
        {
            "object": "entry",
            "centroid": [0, 0, 0],
            "custom_properties": {
                "semantic_class": "STAIR",
                "stair_id": "A",
                "stair_role": "ENTRY",
                "floor_id": "1F",
            },
        },
        {
            "object": "exit",
            "centroid": [0, 2, 10],
            "custom_properties": {
                "semantic_class": "STAIR",
                "stair_id": "A",
                "stair_role": "EXIT",
                "floor_id": "2F",
            },
        },
        {
            "object": "path",
            "custom_properties": {
                "semantic_class": "STAIR",
                "stair_id": "A",
                "stair_role": "PATH",
                "floor_from": "1F",
                "floor_to": "2F",
                "path_segment_points_json": json.dumps(
                    [[[0, 0, 0], [0, 0, 5]], [[0, 2, 5], [0, 2, 10]]]
                ),
            },
        },
    ]
    return {"source_sha256": SOURCE, "objects": rows}


def _stair_survey(audit: dict[str, Any], patches: list[dict[str, Any]]) -> dict[str, Any]:
    result = _survey(audit)
    result["regions"] = [
        {"region_id": "A", "kind": "STAIR_CONTEXT", "complete": True, "patches": patches}
    ]
    return result


def test_real_shared_landing_is_reported_without_approving_body_or_opening() -> None:
    audit = _stair_audit()
    survey = _stair_survey(audit, [_patch(5, x0=-1, x1=1, y0=-1, y1=3)])
    result = review_floor_stairs(audit, survey, _config())["stair_reviews"][0]
    assert result["landing_join_measurements"][0]["actual_shared_landing_evidence"] is True
    assert result["status"] == "HUMAN_REVIEW"
    assert result["opening_status"] == result["clearance_status"] == "HUMAN_REVIEW"
    assert result["geometry_repaired"] is result["connectivity_created"] is False


def test_separate_source_landing_patches_cannot_be_joined_by_bounds() -> None:
    audit = _stair_audit()
    survey = _stair_survey(
        audit,
        [_patch(5, x0=-1, x1=1, y0=-1, y1=0.5), _patch(5, name="upper", x0=-1, x1=1, y0=1.5, y1=3)],
    )
    result = review_floor_stairs(audit, survey, _config())["stair_reviews"][0]
    assert result["landing_join_measurements"][0]["actual_shared_landing_evidence"] is False
    assert "NO_SHARED_ACTUAL_LANDING_SUPPORT_FOR_PROXY_JOIN" in result["reason_codes"]


def test_edge_only_stair_inventory_cannot_supply_landing_surface() -> None:
    audit = _stair_audit()
    result = review_floor_stairs(audit, _stair_survey(audit, []), _config())["stair_reviews"][0]
    assert result["actual_horizontal_triangle_count"] == 0
    assert result["landing_join_measurements"][0]["actual_shared_landing_evidence"] is False


def test_input_order_does_not_change_measurement_semantics() -> None:
    audit = _audit()
    first = _survey(audit, [_patch(20, x1=4), _patch(20, name="other", x0=6)])
    second = copy.deepcopy(first)
    second["regions"][0]["patches"].reverse()
    assert review_floor_stairs(audit, first, _config()) == review_floor_stairs(
        audit, second, _config()
    )


def test_school_v3_source_floor_exceptions_and_missing_landings_are_preserved() -> None:
    root = Path("data/scene_audit")
    audit = json.loads((root / "school_v3_semantic_audit.json").read_text())
    survey = json.loads(
        (root / "phase1_physical_authority_20261006" / "source_mesh_evidence.json").read_text()
    )
    # A small exact source subset avoids repeating the complete diagnostic audit
    # in every pytest run. Missing other regions explicitly remain REVIEW.
    identities = {"WALK_1F_OFFICE_THRESHOLD", "WALK_2F_CLASS201_THRESHOLD", "A", "B"}
    survey["regions"] = [r for r in survey["regions"] if r["region_id"] in identities]
    result = review_floor_stairs(audit, survey, _config())
    floors = {row["object_id"]: row for row in result["floor_reviews"]}
    assert floors["WALK_1F_OFFICE_THRESHOLD"]["dominant_support"][
        "representative_z_units"
    ] == pytest.approx(20.07884979248047)
    assert floors["WALK_2F_CLASS201_THRESHOLD"]["dominant_support"][
        "representative_z_units"
    ] == pytest.approx(161.81109619140625)
    assert result["floor_authority"] == "HUMAN_REVIEW"
    stairs = {row["stair_id"]: row for row in result["stair_reviews"]}
    for identity in ("A", "B"):
        assert (
            stairs[identity]["landing_join_measurements"][0]["actual_shared_landing_evidence"]
            is False
        )
        assert stairs[identity]["physical_stair_approved"] is False
    assert stairs["A"]["anchors"][0]["actual_horizontal_surface_distance_units"] == pytest.approx(
        2.783161163330078
    )
    assert stairs["B"]["anchors"][1]["actual_horizontal_surface_distance_units"] == pytest.approx(
        3.06109619140625
    )


def test_approved_scale_preserves_native_diagnostics_and_dual_unit_measurements() -> None:
    root = Path("data/scene_audit")
    audit = json.loads((root / "school_v3_semantic_audit.json").read_text())
    survey = json.loads(
        (root / "phase1_physical_authority_20261006/source_mesh_evidence.json").read_text()
    )
    identities = {"WALK_1F_OFFICE_THRESHOLD", "WALK_2F_CLASS201_THRESHOLD", "A", "B"}
    survey["regions"] = [row for row in survey["regions"] if row["region_id"] in identities]
    legacy_config = _config()
    # Replay the scale-only checkpoint. Its proposed proxy planes are historical;
    # today's active config separately approves actual source-supported heights.
    active = json.loads((root / "school_v3_approved_scale_20261006/scene_validation.json")
                        .read_text())["config"]
    active["floor_stair_review"] = legacy_config["floor_stair_review"]
    before = review_floor_stairs(audit, survey, legacy_config)
    after = review_floor_stairs(audit, survey, active)
    assert after["scale_authority"] == "APPROVED"
    assert after["scale_approval_id"]
    assert after["floor_authority"] == after["stair_authority"] == "HUMAN_REVIEW"
    assert after["floor_counts"] == before["floor_counts"]
    for original, converted in zip(before["floor_reviews"], after["floor_reviews"], strict=True):
        assert original["status"] == converted["status"]
        assert original["reason_codes"] == converted["reason_codes"]
        if original.get("dominant_support") is None:
            continue
        assert converted["proposed_plane_z_units"] == original["proposed_plane_z_units"]
        assert converted["proposed_plane_z_m"] == pytest.approx(
            original["proposed_plane_z_units"] * 0.0247
        )
        old_support, new_support = original["dominant_support"], converted["dominant_support"]
        assert new_support["representative_z_units"] == old_support["representative_z_units"]
        assert new_support["representative_z_m"] == pytest.approx(
            old_support["representative_z_units"] * 0.0247
        )
        assert new_support["covered_area_m2"] == pytest.approx(
            old_support["covered_area_units2"] * 0.0247 ** 2
        )
        assert converted["physical_floor_approved"] is False
    for original, converted in zip(before["stair_reviews"], after["stair_reviews"], strict=True):
        assert converted["reason_codes"] == [
            "FLOOR_AUTHORITY_UNAPPROVED"
            if reason == "FLOOR_AND_SCALE_AUTHORITY_UNAPPROVED" else reason
            for reason in original["reason_codes"]
        ]
        assert not any("SCALE" in reason for reason in converted["reason_codes"])
        assert converted["physical_stair_approved"] is False
        old_join = original["landing_join_measurements"][0]
        new_join = converted["landing_join_measurements"][0]
        assert new_join["proxy_centerline_join_gap_units"] == (
            old_join["proxy_centerline_join_gap_units"]
        )
        assert new_join["proxy_centerline_join_gap_m"] == pytest.approx(
            old_join["proxy_centerline_join_gap_units"] * 0.0247
        )


def test_active_scale_cannot_approve_a_different_source() -> None:
    active = json.loads(Path("configs/scene_validation_school_v3.json").read_text())
    active["floor_stair_review"] = _config()["floor_stair_review"]
    audit = _audit()
    with pytest.raises(ValueError, match="architectural scale source SHA-256 mismatch"):
        review_floor_stairs(audit, _survey(audit), active)


def test_active_diagnostic_thresholds_preserve_native_quantities() -> None:
    active = json.loads(Path("configs/scene_validation_school_v3.json").read_text())
    legacy = _config()
    scale = active["meters_per_blender_unit"]
    for key, value in legacy["tolerances"].items():
        if value is None:
            assert active["tolerances"][key] is None
        elif key.endswith("_m2"):
            assert active["tolerances"][key] / scale ** 2 == pytest.approx(value)
        elif key.endswith("_m"):
            assert active["tolerances"][key] / scale == pytest.approx(value)
        else:
            assert active["tolerances"][key] == value
    # Updated source-bound planes retain raw BU coordinates, rather than the old
    # 25/165 annotation heights. This is independent of diagnostic tolerances.
    heights = {"1F": 20.07884979248047, "2F": 161.81109619140625}
    for floor, plane in active["floor_planes"].items():
        assert plane["status"] == "APPROVED"
        assert plane["height_m"] / scale == pytest.approx(heights[floor])
        assert plane["height_bu"] == pytest.approx(heights[floor])


@pytest.mark.parametrize("height_bu", [False, math.nan, math.inf, 250])
def test_conflicting_native_floor_height_cannot_enter_report(height_bu: Any) -> None:
    config = _config()
    config["floor_planes"]["1F"]["height_bu"] = height_bu
    audit = _audit()
    with pytest.raises(ValueError, match="BU/metre representations disagree"):
        review_floor_stairs(audit, _survey(audit), config)
