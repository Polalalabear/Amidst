"""Physical-authority review regressions preserve conservative approval boundaries."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.geometry_physical_review import review_physical_geometry

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "a" * 64


@pytest.fixture
def config() -> dict[str, Any]:
    return json.loads((ROOT / "configs/scene_validation_school_v3.json").read_text())


def rectangle(
    name: str,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z: float = 0,
    floor: str = "1F",
    **props: Any,
) -> dict[str, Any]:
    return {
        "object": name,
        "vertices": [[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]],
        "triangles": [[0, 1, 2], [0, 2, 3]],
        "custom_properties": {"floor_id": floor, **props},
    }


def obstacle(name: str = "OBSTACLE_1F_TEST", **props: Any) -> dict[str, Any]:
    return rectangle(
        name,
        0,
        0,
        1,
        1,
        blocks_movement=True,
        occludes_visibility=True,
        collision_role="BOTH",
        semantic_review_id="forged approval",
        **props,
    )


def review(rows: list[dict[str, Any]], config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return review_physical_geometry({"source_sha256": SOURCE, "objects": rows}, config, **kwargs)


def stair_rows() -> list[dict[str, Any]]:
    common = {"stair_id": "A", "floor_from": "1F", "floor_to": "2F", "direction": "UP"}
    return [
        {
            "object": "STAIR_A_ENTRY",
            "centroid": [0, 0, 0],
            "custom_properties": {**common, "stair_role": "ENTRY", "floor_id": "1F"},
        },
        {
            "object": "STAIR_A_EXIT",
            "centroid": [2, 0, 2],
            "custom_properties": {**common, "stair_role": "EXIT", "floor_id": "2F"},
        },
        {
            "object": "STAIR_A_PATH",
            "vertices": [[0, -1, 0], [0, 1, 0], [2, 1, 2], [2, -1, 2]],
            "triangles": [[0, 1, 2], [0, 2, 3]],
            "custom_properties": {
                **common,
                "stair_role": "PATH",
                "path_points_m": [[0, 0, 0], [2, 0, 2]],
            },
        },
        rectangle("WALKABLE_1F_START", -1, -1, 0, 1),
        rectangle("WALKABLE_2F_END", 2, -1, 3, 1, 2, "2F"),
    ]


def test_role_approval_is_external_and_does_not_certify_proxy(config: dict[str, Any]) -> None:
    row = obstacle()
    first = review([row], config)["obstacle_reviews"][0]
    assert first["semantic_role_status"] == "HUMAN_REVIEW"
    second = review(
        [row], config, approved_obstacle_ids=[row["object"]], obstacle_review_id="human-2026-10-06"
    )["obstacle_reviews"][0]
    assert second["semantic_role_status"] == "APPROVED"
    assert second["physical_geometry_status"] == "HUMAN_REVIEW"
    assert second["representation"] == "OPEN_SURFACE_OR_FOOTPRINT_PROXY"
    assert not second["physical_collision_certified"]
    assert not second["visibility_occlusion_certified"]


def test_invalid_role_flag_cannot_leak_nonfinite_json(config: dict[str, Any]) -> None:
    row = obstacle()
    row["custom_properties"]["blocks_movement"] = float("nan")
    result = review([row], config)
    assert result["obstacle_reviews"][0]["semantic_role_status"] == "REJECTED"
    json.dumps(result, allow_nan=False)


def test_closed_mesh_is_evidence_not_physical_approval(config: dict[str, Any]) -> None:
    row = obstacle()
    row["vertices"] = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]]
    row["triangles"] = [[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]]
    result = review([row], config)["obstacle_reviews"][0]
    assert result["physical_geometry_status"] == "HIGH_CONFIDENCE"
    assert result["status"] == "HUMAN_REVIEW"
    assert not result["physical_collision_certified"]
    row["triangles"][0].reverse()
    assert (
        review([row], config)["obstacle_reviews"][0]["physical_geometry_status"] == "HUMAN_REVIEW"
    )


def test_unreferenced_vertex_does_not_invent_obstacle_height(config: dict[str, Any]) -> None:
    row = obstacle()
    row["vertices"].append([0, 0, 100])
    assert review([row], config)["obstacle_reviews"][0]["z_extent_m"] == 0


def test_footprint_hole_is_not_aabb_collision(config: dict[str, Any]) -> None:
    rings = [
        rectangle("unused", -2, -2, -1, 2),
        rectangle("unused", 1, -2, 2, 2),
        rectangle("unused", -1, -2, 1, -1),
        rectangle("unused", -1, 1, 1, 2),
    ]
    walk = rectangle("WALKABLE_1F_RING", -2, -2, 2, 2)
    walk["vertices"], walk["triangles"] = [], []
    for ring in rings:
        offset = len(walk["vertices"])
        walk["vertices"].extend(ring["vertices"])
        walk["triangles"].extend([[index + offset for index in face] for face in ring["triangles"]])
    center = rectangle("OBSTACLE_1F_HOLE", -0.5, -0.5, 0.5, 0.5)
    result = review([center, walk], config)["obstacle_reviews"][0]
    assert result["conflicts"]["walkable"] == []


def test_exact_boundary_touch_is_not_positive_area_overlap(config: dict[str, Any]) -> None:
    rows = [obstacle(), rectangle("WALKABLE_1F_TOUCH", 1, 0, 2, 1)]
    assert review(rows, config)["obstacle_reviews"][0]["conflicts"]["walkable"] == []


@pytest.mark.parametrize("ratio, expected", [(0.01, False), (0.009, False), (0.011, True)])
def test_existing_contact_ratio_boundary(
    config: dict[str, Any], ratio: float, expected: bool
) -> None:
    rows = [obstacle(), rectangle("WALKABLE_1F_OVERLAP", 1 - ratio, 0, 2 - ratio, 1)]
    pair = review(rows, config)["obstacle_reviews"][0]["conflicts"]["walkable"][0]
    # Binary representability of 1 - 0.01 can otherwise move the intended equality by 1 ULP.
    if ratio == 0.01:
        config["tolerances"]["contact_overlap_ratio"] = pair["smaller_footprint_overlap_ratio"]
        pair = review(rows, config)["obstacle_reviews"][0]["conflicts"]["walkable"][0]
    assert pair["above_contact_tolerance"] is expected


def test_portal_overlap_uses_actual_mesh_and_vertical_evidence(config: dict[str, Any]) -> None:
    rows = [
        obstacle(),
        rectangle("PORTAL_1F_DOOR", 0.5, 0, 1.5, 1),
        rectangle("WALKABLE_1F_ABOVE", 0, 0, 1, 1, 2),
        rectangle("WALKABLE_2F_OTHER", 0, 0, 1, 1, 0, "2F"),
    ]
    result = review(rows, config)["obstacle_reviews"][0]
    assert result["conflicts"]["portal"][0]["portal_overlap_ratio"] == pytest.approx(0.5)
    assert result["conflicts"]["portal"][0]["status"] == "HUMAN_REVIEW"
    assert len(result["conflicts"]["walkable"]) == 1
    assert not result["conflicts"]["walkable"][0]["vertical_contact"]


@pytest.mark.parametrize(
    "damage", ["nan", "invalid_triangle", "empty", "zero_area", "floor_conflict", "role_conflict"]
)
def test_malformed_surface_is_structured_rejected(config: dict[str, Any], damage: str) -> None:
    row = obstacle()
    if damage == "nan":
        row["vertices"][0][0] = float("nan")
    elif damage == "invalid_triangle":
        row["triangles"][0] = [0, 1, 20]
    elif damage == "empty":
        row["triangles"] = []
    elif damage == "zero_area":
        row["vertices"][1] = row["vertices"][0]
    elif damage == "floor_conflict":
        row["declared_floor_label"] = "2F"
    else:
        row["custom_properties"]["semantic_class"] = "WALL"
    result = review([row], config)
    assert len(result["rejected_geometry"]) == 1
    assert result["rejected_geometry"][0]["status"] == "REJECTED"
    assert result["obstacle_reviews"] == []
    json.dumps(result, allow_nan=False)


def test_missing_source_and_forged_authorization_fail_fast(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="source_sha256"):
        review_physical_geometry({"objects": []}, config)
    with pytest.raises(ValueError, match="absent"):
        review(
            [obstacle()], config, approved_obstacle_ids=["OBSTACLE_missing"], obstacle_review_id="h"
        )
    with pytest.raises(ValueError, match="review ID"):
        review([obstacle()], config, approved_obstacle_ids=["OBSTACLE_1F_TEST"])
    walk = rectangle("WALKABLE_1F_TEST", 0, 0, 1, 1)
    with pytest.raises(ValueError, match="another semantic class"):
        review([walk], config, approved_obstacle_ids=[walk["object"]], obstacle_review_id="h")


def test_connected_stair_and_declared_pass_do_not_certify_opening(config: dict[str, Any]) -> None:
    rows = stair_rows()
    rows[2]["custom_properties"].update(slab_opening_review="PASS", measured_clearance_m=10)
    config["tolerances"]["minimum_clearance_m"] = 1
    result = review(rows, config)["stair_reviews"][0]
    assert result["checks"]["path_surface_continuity"] == "HIGH_CONFIDENCE"
    assert result["checks"]["entry_walkable_contact"] == "HIGH_CONFIDENCE"
    assert result["checks"]["exit_walkable_contact"] == "HIGH_CONFIDENCE"
    assert result["checks"]["ordered_segment_alignment"] == "HIGH_CONFIDENCE"
    assert result["checks"]["z_direction"] == "HIGH_CONFIDENCE"
    assert result["checks"]["clearance"] == "HUMAN_REVIEW"
    assert result["checks"]["slab_opening"] == "HUMAN_REVIEW"
    assert result["status"] == "HUMAN_REVIEW"
    assert not result["connectivity_created"]


@pytest.mark.parametrize("offset, expected", [(0.25, "HIGH_CONFIDENCE"), (0.25001, "HUMAN_REVIEW")])
def test_stair_contact_uses_three_dimensions_at_boundary(
    config: dict[str, Any], offset: float, expected: str
) -> None:
    rows = stair_rows()
    rows[0]["centroid"][2] = offset
    result = review(rows, config)["stair_reviews"][0]
    assert result["entry_walkable"]["distance_m"] == pytest.approx(offset)
    assert result["checks"]["entry_walkable_contact"] == expected


def test_stair_contact_does_not_snap_through_floor_hole(config: dict[str, Any]) -> None:
    rows = stair_rows()
    rows.pop(3)
    rows.extend(
        [
            rectangle("WALKABLE_1F_LEFT", -2, -1, -0.5, 1),
            rectangle("WALKABLE_1F_RIGHT", 0.5, -1, 2, 1),
        ]
    )
    result = review(rows, config)["stair_reviews"][0]
    assert result["entry_walkable"]["distance_m"] == 0.5
    assert result["checks"]["entry_walkable_contact"] == "HUMAN_REVIEW"


def test_missing_role_and_wrong_floor_reject(config: dict[str, Any]) -> None:
    rows = stair_rows()
    assert review(rows[1:], config)["stair_reviews"][0]["status"] == "REJECTED"
    rows[1]["custom_properties"]["floor_id"] = "1F"
    result = review(rows, config)["stair_reviews"][0]
    assert result["checks"]["floor_transition"] == "REJECTED"
    assert result["status"] == "REJECTED"


def test_nonfinite_stair_floor_metadata_cannot_leak_json(config: dict[str, Any]) -> None:
    rows = stair_rows()
    rows[2]["custom_properties"]["floor_from"] = float("nan")
    result = review(rows, config)
    assert result["stair_reviews"][0]["status"] == "REJECTED"
    json.dumps(result, allow_nan=False)


def test_disconnected_mesh_is_not_joined_by_ordered_points(config: dict[str, Any]) -> None:
    rows = stair_rows()
    rows[2]["vertices"] = [
        [0, -1, 0],
        [0, 1, 0],
        [0.75, 1, 0.75],
        [0.75, -1, 0.75],
        [1.25, -1, 1.25],
        [1.25, 1, 1.25],
        [2, 1, 2],
        [2, -1, 2],
    ]
    rows[2]["triangles"] = [[0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7]]
    result = review(rows, config)["stair_reviews"][0]
    assert len(result["path_mesh_components"]) == 2
    assert result["component_gap_measurements"][0]["closest_surface_gap_m"] == pytest.approx(
        2**-0.5
    )
    assert result["checks"]["ordered_segment_alignment"] == "REJECTED"
    assert not result["connectivity_created"]


@pytest.mark.parametrize("clearance", [-1, float("nan"), True])
def test_invalid_declared_clearance_rejected(config: dict[str, Any], clearance: Any) -> None:
    rows = stair_rows()
    rows[2]["custom_properties"]["measured_clearance_m"] = clearance
    result = review(rows, config)["stair_reviews"][0]
    assert result["checks"]["clearance"] == "REJECTED"
    json.dumps(result, allow_nan=False)


def test_insufficient_declared_clearance_is_rejected_without_threshold_change(
    config: dict[str, Any],
) -> None:
    rows = stair_rows()
    config["tolerances"]["minimum_clearance_m"] = 1
    rows[2]["custom_properties"]["measured_clearance_m"] = 0.99
    assert review(rows, config)["stair_reviews"][0]["checks"]["clearance"] == "REJECTED"
    rows[2]["custom_properties"]["measured_clearance_m"] = 1
    assert review(rows, config)["stair_reviews"][0]["checks"]["clearance"] == "HUMAN_REVIEW"


def test_config_invalid_and_complexity_guard(config: dict[str, Any]) -> None:
    bad = copy.deepcopy(config)
    bad["tolerances"]["stair_join_distance_m"] = -1
    with pytest.raises(ValueError, match="tolerance"):
        review([obstacle()], bad)
    config["geometry_complexity"]["maximum_mesh_triangles"] = 1
    result = review([obstacle()], config)
    assert result["unmeasured_geometry"][0]["status"] == "HUMAN_REVIEW"
    assert "budget" in result["unmeasured_geometry"][0]["reason"]
    assert result["rejected_geometry"] == []


def test_real_school_evidence_remains_provisional_and_deterministic(config: dict[str, Any]) -> None:
    audit = json.loads((ROOT / "data/scene_audit/school_v3_semantic_audit.json").read_text())
    approved = [row["object"] for row in audit["objects"] if row["object"].startswith("OBSTACLE_")]
    before = copy.deepcopy(audit)
    result = review_physical_geometry(
        audit, config, approved_obstacle_ids=approved, obstacle_review_id="human-2026-10-06"
    )
    assert len(result["obstacle_reviews"]) == 19
    assert all(row["semantic_role_status"] == "APPROVED" for row in result["obstacle_reviews"])
    assert all(
        row["physical_geometry_status"] == "HUMAN_REVIEW" for row in result["obstacle_reviews"]
    )
    assert len(result["stair_reviews"]) == 2
    assert result["measured_geometry_counts"]["walkable_meshes"] == 48
    assert all(len(row["path_mesh_components"]) == 2 for row in result["stair_reviews"])
    assert all(row["status"] == "HUMAN_REVIEW" for row in result["stair_reviews"])
    assert result["stair_reviews"][1]["checks"]["entry_walkable_contact"] == "HIGH_CONFIDENCE"
    assert result["physical_authority_status"] == "PROVISIONAL"
    assert result["rejected_geometry"] == []
    assert result["unmeasured_geometry"] == []
    assert audit == before
    audit["objects"].reverse()
    assert result == review_physical_geometry(
        audit,
        config,
        approved_obstacle_ids=list(reversed(approved)),
        obstacle_review_id="human-2026-10-06",
    )
    json.dumps(result, allow_nan=False)
