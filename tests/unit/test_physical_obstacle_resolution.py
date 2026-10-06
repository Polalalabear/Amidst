"""Physical obstacle diagnosis never turns annotation overlaps into authority."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.physical_obstacle_resolution import content_sha256, review_obstacle_portal_conflicts

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "a" * 64


@pytest.fixture
def config() -> dict[str, Any]:
    # These synthetic rectangles retain their original 1:1 metre coordinates;
    # the source-bound school-v3 architectural setting does not define their units.
    return json.loads((ROOT / "configs/scene_validation_v1.json").read_text())


def rectangle(name: str, x0: float, y0: float, x1: float, y1: float) -> dict[str, Any]:
    return {
        "object": name,
        "vertices": [[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]],
        "triangles": [[0, 1, 2], [0, 2, 3]],
        "custom_properties": {"floor_id": "1F", "semantic_class": name.split("_")[0]},
    }


def evidence() -> tuple[dict[str, Any], dict[str, Any]]:
    obstacle = rectangle("OBSTACLE_1F_BLOCK", 0, 0, 2, 2)
    obstacle["custom_properties"].update(
        blocks_movement=True, occludes_visibility=True, collision_role="BOTH"
    )
    portal = rectangle("PORTAL_1F_DOOR", 1, 0, 3, 2)
    portal["custom_properties"]["portal_normal"] = [1, 0, 0]
    audit = {"source_sha256": SOURCE, "objects": [obstacle, portal]}
    baseline = {
        "source_sha256": SOURCE,
        "physical_review": {
            "source_sha256": SOURCE,
            "obstacle_reviews": [
                {
                    "object_id": obstacle["object"],
                    "conflicts": {"portal": [{"other_object_id": portal["object"]}]},
                }
            ],
        },
    }
    return audit, baseline


def review(config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    audit, baseline = evidence()
    return review_obstacle_portal_conflicts(
        audit, baseline, config, expected_source_sha256=SOURCE, **kwargs
    )


def selection_config() -> dict[str, Any]:
    return {"source_sha256": SOURCE, "schema_version": "physical-resolution-evidence-config-v1"}


def source_context(audit: dict[str, Any]) -> dict[str, Any]:
    mesh = rectangle("unclassified-source", 0, 0, 2, 2)
    patch = {
        "source_object_id": mesh["object"],
        "vertices": mesh["vertices"],
        "triangles": mesh["triangles"],
        "source_face_indices": [0],
        "triangle_source_face_indices": [0, 0],
        "semantic_role": "UNCLASSIFIED_SOURCE_MESH_CONTEXT_ONLY",
    }
    patch["geometry_sha256"] = content_sha256(patch)
    return {
        "schema_version": "physical-source-mesh-evidence-v1",
        "source_sha256": SOURCE,
        "audit_content_sha256": content_sha256(audit),
        "config_content_sha256": content_sha256(selection_config()),
        "source_preserved": True,
        "saved": False,
        "rendered": False,
        "policy": {
            "gt_used": False,
            "roles_inferred_from_names": False,
            "region_complete_is_selection_complete_only": True,
            "missing_triangles_certify_clearance": False,
        },
        "regions": [
            {
                "region_id": "OBSTACLE_1F_BLOCK",
                "kind": "OBSTACLE_CONTEXT",
                "complete": True,
                "patches": [patch],
                "triangle_count": 2,
            }
        ],
    }


def test_measured_footprint_contact_is_never_physical_approval(config: dict[str, Any]) -> None:
    result = review(config)
    row = result["pairs"][0]
    assert row["overlap_area_m2"] == pytest.approx(2)
    assert row["portal_overlap_ratio"] == pytest.approx(0.5)
    assert row["physical_status"] == "HUMAN_REVIEW"
    assert row["revalidation_status"] == "MEASURED"
    assert row["center_plane_measurement"]["blocked_width_m"] == pytest.approx(2)
    assert result["physical_approval_count"] == result["repair_count"] == 0
    assert result["volume_authority"] == "HUMAN_REVIEW"
    assert result["obstacle_volume_evidence"][0]["z_extent_m"] == 0
    assert not result["obstacle_volume_evidence"][0]["closed_volume_evidence"]


def test_annotation_depth_overlap_with_clear_center_keeps_review(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    audit["objects"][0] = rectangle("OBSTACLE_1F_BLOCK", 0, 0, 1.2, 2)
    result = review_obstacle_portal_conflicts(
        audit, baseline, config, expected_source_sha256=SOURCE
    )
    row = result["pairs"][0]
    assert row["portal_overlap_ratio"] == pytest.approx(0.1)
    assert row["classification"] == (
        "SEMANTIC_ANNOTATION_DEPTH_OVERLAP_CLEAR_DECLARED_CENTER_PLANE"
    )
    assert row["center_plane_measurement"]["blocked_width_m"] == 0
    assert row["physical_status"] == "HUMAN_REVIEW"
    assert not row["repair_applied"]


@pytest.mark.parametrize(
    "normal, reason",
    [
        (None, "PORTAL_NORMAL_NOT_DECLARED"),
        ([0, 0, 0], "PORTAL_NORMAL_NOT_HORIZONTAL"),
        ([1, 0, 1], "PORTAL_NORMAL_NOT_HORIZONTAL"),
        ([True, 0, 0], "PORTAL_NORMAL_INVALID"),
    ],
)
def test_missing_or_invalid_normal_is_not_guessed(
    config: dict[str, Any], normal: Any, reason: str
) -> None:
    audit, baseline = evidence()
    audit["objects"][1]["custom_properties"]["portal_normal"] = normal
    row = review_obstacle_portal_conflicts(audit, baseline, config, expected_source_sha256=SOURCE)[
        "pairs"
    ][0]
    assert row["center_plane_measurement"]["reason"] == reason
    assert row["physical_status"] == "HUMAN_REVIEW"


def test_world_scale_does_not_extrude_planar_footprint(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    audit["objects"][0]["scale"] = [1, 1, -100]
    audit["objects"][0]["matrix_world"] = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -100, 0]]
    result = review_obstacle_portal_conflicts(
        audit, baseline, config, expected_source_sha256=SOURCE
    )
    assert result["obstacle_volume_evidence"][0]["z_extent_m"] == 0
    assert not result["obstacle_volume_evidence"][0]["closed_volume_evidence"]


def test_conflicting_floor_label_cannot_hide_actual_portal_contact(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    audit["objects"][1]["object"] = "PORTAL_2F_DOOR"
    audit["objects"][1]["custom_properties"]["floor_id"] = "2F"
    baseline["physical_review"]["obstacle_reviews"][0]["conflicts"]["portal"][0][
        "other_object_id"
    ] = "PORTAL_2F_DOOR"
    row = review_obstacle_portal_conflicts(audit, baseline, config, expected_source_sha256=SOURCE)[
        "pairs"
    ][0]
    assert row["floor_id"] == "1F"
    assert row["portal_floor_id"] == "2F"
    assert row["portal_overlap_ratio"] == pytest.approx(0.5)
    assert row["vertical_interval_gap_m"] == 0
    assert row["physical_status"] == "HUMAN_REVIEW"


def test_hole_in_portal_geometry_is_not_filled_by_bounds(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    portal = audit["objects"][1]
    portal["vertices"], portal["triangles"] = [], []
    for region in [(-2, -2, -1, 2), (1, -2, 2, 2), (-1, -2, 1, -1), (-1, 1, 1, 2)]:
        part = rectangle("unused", *region)
        offset = len(portal["vertices"])
        portal["vertices"].extend(part["vertices"])
        portal["triangles"].extend(
            [[index + offset for index in face] for face in part["triangles"]]
        )
    portal["custom_properties"]["portal_normal"] = [0, 1, 0]
    audit["objects"][0] = rectangle("OBSTACLE_1F_BLOCK", -0.5, -0.5, 0.5, 0.5)
    row = review_obstacle_portal_conflicts(audit, baseline, config, expected_source_sha256=SOURCE)[
        "pairs"
    ][0]
    assert row["overlap_area_m2"] == 0
    assert row["center_plane_measurement"]["cross_section_width_m"] == pytest.approx(2)
    assert row["center_plane_measurement"]["blocked_width_m"] == 0
    assert row["revalidation_status"] == "STALE_BASELINE_CONFLICT"


def test_area_context_uses_actual_geometry_and_preserves_input(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    area = rectangle("AREA_1F_ROOM", 1, 0, 4, 2)
    audit["objects"].append(area)
    before = copy.deepcopy((audit, baseline, config))
    row = review_obstacle_portal_conflicts(audit, baseline, config, expected_source_sha256=SOURCE)[
        "pairs"
    ][0]
    assert row["areas"][0]["obstacle_coverage_ratio"] == pytest.approx(1 / 3)
    assert row["areas"][0]["bounds_m"]["maximum"] == [4, 2, 0]
    assert (audit, baseline, config) == before


@pytest.mark.parametrize("document", ["audit", "baseline", "physical_review"])
def test_mismatched_source_is_rejected(config: dict[str, Any], document: str) -> None:
    audit, baseline = evidence()
    target = audit if document == "audit" else baseline
    if document == "physical_review":
        target = baseline["physical_review"]
    target["source_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="source SHA-256"):
        review_obstacle_portal_conflicts(audit, baseline, config, expected_source_sha256=SOURCE)


def test_content_binding_detects_forged_footprint(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    expected = content_sha256(audit)
    audit["objects"][0]["vertices"][0][0] -= 0.1
    with pytest.raises(ValueError, match="source-verified geometry binding"):
        review_obstacle_portal_conflicts(
            audit,
            baseline,
            config,
            expected_source_sha256=SOURCE,
            expected_audit_content_sha256=expected,
        )


def test_absent_baseline_endpoint_is_explicitly_rejected(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    audit["objects"].pop()
    with pytest.raises(ValueError, match="absent source objects"):
        review_obstacle_portal_conflicts(audit, baseline, config, expected_source_sha256=SOURCE)


def test_malformed_geometry_has_structured_review_error(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    audit["objects"][0]["triangles"] = [[0, 0, 1]]
    result = review_obstacle_portal_conflicts(
        audit, baseline, config, expected_source_sha256=SOURCE
    )
    row = result["pairs"][0]
    assert row["revalidation_status"] == "REJECTED_EVIDENCE"
    assert "triangle indices" in row["error"]
    assert row["physical_status"] == "HUMAN_REVIEW"
    assert result["rejected_geometry"]
    json.dumps(result, allow_nan=False)


def test_ordering_is_stable(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    first = review_obstacle_portal_conflicts(audit, baseline, config, expected_source_sha256=SOURCE)
    audit["objects"].reverse()
    second = review_obstacle_portal_conflicts(
        audit, baseline, config, expected_source_sha256=SOURCE
    )
    assert first["pairs"] == second["pairs"]
    assert first["obstacle_volume_evidence"] == second["obstacle_volume_evidence"]


@pytest.mark.parametrize("complete", [True, False])
def test_source_context_completeness_does_not_approve_collider(
    config: dict[str, Any], complete: bool
) -> None:
    audit, baseline = evidence()
    context = source_context(audit)
    context["regions"][0]["complete"] = complete
    result = review_obstacle_portal_conflicts(
        audit,
        baseline,
        config,
        expected_source_sha256=SOURCE,
        source_mesh_evidence=context,
        source_mesh_config=selection_config(),
    )
    source = result["pairs"][0]["source_geometry_context"]
    assert source["selection_complete"] is complete
    assert source["source_object_count"] == 1
    assert source["selected_triangle_count"] == 2
    assert not source["collider_ownership_certified"]
    assert not source["empty_space_certified"]
    assert result["pairs"][0]["physical_status"] == "HUMAN_REVIEW"
    assert result["physical_approval_count"] == 0


@pytest.mark.parametrize("change", ["role", "geometry", "source", "empty_space"])
def test_source_context_cannot_forge_authority(config: dict[str, Any], change: str) -> None:
    audit, baseline = evidence()
    context = source_context(audit)
    patch = context["regions"][0]["patches"][0]
    if change == "role":
        patch["semantic_role"] = "APPROVED_OBSTACLE"
        patch["geometry_sha256"] = content_sha256(
            {key: value for key, value in patch.items() if key != "geometry_sha256"}
        )
    elif change == "geometry":
        patch["vertices"][0][2] = 10
    elif change == "source":
        context["source_sha256"] = "b" * 64
    else:
        context["policy"]["missing_triangles_certify_clearance"] = True
    with pytest.raises(ValueError, match="source|unclassified"):
        review_obstacle_portal_conflicts(
            audit,
            baseline,
            config,
            expected_source_sha256=SOURCE,
            source_mesh_evidence=context,
            source_mesh_config=selection_config(),
        )


def test_source_selection_config_cannot_be_replaced_by_diagnostic_config(
    config: dict[str, Any],
) -> None:
    audit, baseline = evidence()
    with pytest.raises(ValueError, match="selection config"):
        review_obstacle_portal_conflicts(
            audit,
            baseline,
            config,
            expected_source_sha256=SOURCE,
            source_mesh_evidence=source_context(audit),
            source_mesh_config=config,
        )


def test_source_context_requires_its_config_binding(config: dict[str, Any]) -> None:
    audit, baseline = evidence()
    with pytest.raises(ValueError, match="supplied together"):
        review_obstacle_portal_conflicts(
            audit,
            baseline,
            config,
            expected_source_sha256=SOURCE,
            source_mesh_evidence=source_context(audit),
        )


def test_real_eight_conflicts_have_zero_unjustified_repairs(config: dict[str, Any]) -> None:
    directory = ROOT / "data/scene_audit/phase1_geometry_authority_20261006"
    audit = json.loads((ROOT / "data/scene_audit/school_v3_semantic_audit.json").read_text())
    baseline = json.loads((directory / "authority.json").read_text())
    meshes = json.loads((directory / "wall_meshes.json").read_text())
    result = review_obstacle_portal_conflicts(
        audit,
        baseline,
        config,
        expected_source_sha256=baseline["source_sha256"],
        expected_audit_content_sha256=meshes["audit_content_sha256"],
        source_mesh_evidence=json.loads(
            (
                ROOT
                / "data/scene_audit/phase1_physical_authority_20261006/source_mesh_evidence.json"
            ).read_text()
        ),
        source_mesh_config=json.loads(
            (ROOT / "configs/physical_authority_resolution_school_v3.json").read_text()
        ),
    )
    assert result["pair_count"] == result["human_review_count"] == 8
    assert result["repair_count"] == result["physical_approval_count"] == 0
    assert all(row["revalidation_status"] == "MEASURED" for row in result["pairs"])
    center_clear = {
        row["portal_id"]
        for row in result["pairs"]
        if row["classification"].startswith("SEMANTIC_ANNOTATION_DEPTH_OVERLAP")
    }
    assert center_clear == {"PORTAL_2F_MEETINGROOM_01", "PORTAL_2F_MEETINGROOM_02"}
    bathroom = [row for row in result["pairs"] if "BATHROOM" in row["obstacle_id"]]
    assert len(bathroom) == 4
    assert all(row["portal_overlap_ratio"] == pytest.approx(1) for row in bathroom)
    assert all(row["areas"][0]["obstacle_coverage_ratio"] == pytest.approx(1) for row in bathroom)
    assert len(result["obstacle_volume_evidence"]) == 19
    assert not any(row["closed_volume_evidence"] for row in result["obstacle_volume_evidence"])
    assert all(row["source_geometry_context"]["selection_complete"] for row in result["pairs"])
