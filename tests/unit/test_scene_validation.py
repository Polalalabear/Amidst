"""Semantic diagnostics using explicit synthetic mesh snapshots, never the saved school asset."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.scene_validation import load_config, validate_scene, write_report

FIXTURES = Path(__file__).parents[1] / "fixtures/scene_validation/cases.json"


def config(*, approved: bool = True) -> dict[str, Any]:
    result = load_config()
    if approved:
        result["floor_planes"] = {
            "1F": {"status": "SYNTHETIC_FIXTURE", "height_m": 0, "normal": [0, 0, 1]},
            "2F": {"status": "SYNTHETIC_FIXTURE", "height_m": 3, "normal": [0, 0, 1]},
        }
    return result


def fixture(name: str) -> dict[str, Any]:
    return json.loads(FIXTURES.read_text())[name]  # type: ignore[no-any-return]


def codes(report: dict[str, Any]) -> set[str]:
    return {row["code"] for row in report["findings"]}


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("missing_walkable", "AREA_MISSING_WALKABLE"),
        ("isolated_walkable", "SMALL_WALKABLE_ISLAND"),
        ("one_sided_portal", "PORTAL_ONE_SIDED"),
        ("semantic_conflict", "INCOMPATIBLE_SEMANTIC_OWNERSHIP"),
        ("invalid_floor", "INVALID_FLOOR_PREFIX"),
        ("missing_stair_entry", "STAIR_MISSING_ENTRY"),
        ("stair_wrong_floor", "STAIR_WRONG_FLOOR"),
        ("wall_walkable_overlap", "WALKABLE_COLLIDER_OVERLAP"),
        ("suspicious_geometry", "GIANT_GEOMETRY"),
    ],
)
def test_required_anomaly_fixtures(case: str, expected: str, tmp_path: Path) -> None:
    report = validate_scene(fixture(case), config())
    assert expected in codes(report)
    paths = write_report(report, tmp_path / case)
    assert json.loads(paths[0].read_text())["schema_version"] == "scene-validation-v1"
    assert "Human review queue" in paths[1].read_text()


def test_complete_walkable_and_missing_stairs() -> None:
    report = validate_scene(fixture("complete_walkable"), config())
    assert report["area_coverage"][0]["status"] == "PASS"
    assert report["area_coverage"][0]["walkable_overlap_ratio"] == pytest.approx(1)
    assert report["stair_validation"]["status"] == "MISSING"
    assert report["walkable_connectivity"]["stair_edges_created"] is False


def test_coverage_threshold_does_not_require_one_hundred_percent() -> None:
    scene = fixture("complete_walkable")
    walkable = scene["objects"][1]
    walkable["vertices"][1][0] = walkable["vertices"][2][0] = 9
    report = validate_scene(scene, config())
    assert report["area_coverage"][0]["walkable_overlap_ratio"] == pytest.approx(0.9)
    assert report["area_coverage"][0]["status"] == "PASS"
    strict = config()
    strict["tolerances"]["coverage_pass_ratio"] = 0.95
    assert validate_scene(scene, strict)["area_coverage"][0]["coverage_status"] == "PARTIAL"


def test_unapproved_floors_are_heuristic_even_with_complete_geometry() -> None:
    report = validate_scene(fixture("complete_walkable"), config(approved=False))
    assert report["area_coverage"][0]["coverage_status"] == "PASS"
    assert report["area_coverage"][0]["status"] == "REVIEW"
    assert report["floor_consistency"]["1F"]["authority"] == "HEURISTIC"


def test_source_mismatch_cannot_approve_floor() -> None:
    settings = config()
    settings["floor_planes"]["1F"] = {
        "status": "APPROVED",
        "height_m": 0,
        "normal": [0, 0, 1],
        "review_id": "human-1",
        "source_sha256": "other-scene",
    }
    report = validate_scene(fixture("complete_walkable"), settings)
    assert "FLOOR_AUTHORITY_SOURCE_MISMATCH" in codes(report)
    assert report["area_coverage"][0]["status"] == "REVIEW"


def test_floor_wrong_height_is_error_with_synthetic_authority() -> None:
    scene = fixture("complete_walkable")
    scene["objects"][1]["bounding_box"]["minimum"][2] = 3
    scene["objects"][1]["bounding_box"]["maximum"][2] = 3
    for p in scene["objects"][1]["vertices"]:
        p[2] = 3
    report = validate_scene(scene, config())
    assert "FLOOR_GEOMETRY_OFFSET" in codes(report)
    assert any(
        r["code"] == "FLOOR_GEOMETRY_OFFSET" and r["status"] == "ERROR" for r in report["findings"]
    )


def test_mesh_holes_preserved_and_overlapping_surfaces_not_double_counted() -> None:
    scene = fixture("complete_walkable")
    walkable = scene["objects"][1]
    # Four strips around a 6x6 hole: union area 64, not the AABB's 100.
    vertices = []
    triangles = []
    for x, y, w, h in ((0, 0, 10, 2), (0, 8, 10, 2), (0, 2, 2, 6), (8, 2, 2, 6)):
        start = len(vertices)
        vertices.extend([[x, y, 0], [x + w, y, 0], [x + w, y + h, 0], [x, y + h, 0]])
        triangles.extend([[start, start + 1, start + 2], [start, start + 2, start + 3]])
    walkable["vertices"], walkable["triangles"] = vertices, triangles
    scene["objects"].append({**copy.deepcopy(walkable), "object": "WALKABLE_1F_DUPLICATE"})
    report = validate_scene(scene, config())
    assert report["area_coverage"][0]["walkable_overlap_ratio"] == pytest.approx(0.64)
    assert report["area_coverage"][0]["status"] == "PARTIAL"


def test_rotated_triangle_does_not_fill_its_bounding_box() -> None:
    scene = fixture("complete_walkable")
    scene["objects"][1]["triangles"] = [[0, 1, 2]]
    report = validate_scene(scene, config())
    assert report["area_coverage"][0]["walkable_overlap_ratio"] == pytest.approx(0.5)


def test_connectivity_checks_z_and_never_assumes_all_disconnections_errors() -> None:
    scene = fixture("isolated_walkable")
    report = validate_scene(scene, config())
    assert report["walkable_connectivity"]["connected_component_count"] == 2
    assert all(
        r["status"] != "ERROR"
        for r in report["findings"]
        if "ISLAND" in r["code"] or "DISCONNECTION" in r["code"]
    )


def test_small_contact_overlap_allowed() -> None:
    scene = fixture("wall_walkable_overlap")
    wall = scene["objects"][2]
    wall["vertices"][1][0] = wall["vertices"][2][0] = 0.01
    assert "WALKABLE_COLLIDER_OVERLAP" not in codes(validate_scene(scene, config()))


def test_collection_only_roles_and_wrong_collection() -> None:
    scene = fixture("complete_walkable")
    walkable = scene["objects"][1]
    walkable["object"] = "Cube.001"
    walkable["collections"] = ["WALKABLE_1F_NAV"]
    settings = config()
    settings["expected_collections"] = {"WALKABLE": ["ApprovedWalkables"]}
    report = validate_scene(scene, settings)
    assert report["semantic_counts"]["WALKABLE"] == 1
    assert {"NAMING_INCONSISTENCY", "WRONG_COLLECTION"} <= codes(report)


def test_unlabeled_group_cube_never_classified() -> None:
    scene = fixture("complete_walkable")
    scene["objects"].append({**scene["objects"][1], "object": "Cube.777"})
    scene["objects"].append({**scene["objects"][1], "object": "group_1234"})
    assert validate_scene(scene, config())["semantic_counts"]["WALKABLE"] == 1


@pytest.mark.parametrize("bad", [None, float("nan"), "bad", True])
def test_invalid_area_coordinates_serialize_without_infinity(bad: Any, tmp_path: Path) -> None:
    scene = fixture("complete_walkable")
    area = scene["objects"][0]
    area["vertices"][0][0] = bad
    area.pop("bounding_box")
    report = validate_scene(scene, config())
    assert report["area_coverage"][0]["status"] == "REVIEW"
    assert report["area_coverage"][0]["nearest_distance_m"] is None
    write_report(report, tmp_path / "invalid")


def test_negative_triangle_indices_rejected() -> None:
    scene = fixture("complete_walkable")
    scene["objects"][0]["triangles"] = [[-1, 0, 1]]
    assert "INVALID_OR_UNSUPPORTED_GEOMETRY" in codes(validate_scene(scene, config()))


def test_complex_geometry_budget_has_explicit_incomplete_review(tmp_path: Path) -> None:
    settings = config()
    settings["geometry_complexity"]["maximum_union_polygons"] = 1
    report = validate_scene(fixture("complete_walkable"), settings)
    assert report["status"] == "INCOMPLETE_REVIEW_REQUIRED"
    assert "GEOMETRY_COMPLEXITY_REVIEW" in codes(report)
    write_report(report, tmp_path / "complex")


def test_nonmanifold_report_only_and_output_repeatable(tmp_path: Path) -> None:
    scene = fixture("complete_walkable")
    scene["objects"][1]["non_manifold_edges"] = 4
    report = validate_scene(scene, config())
    item = next(f for f in report["findings"] if f["code"] == "NON_MANIFOLD")
    assert item["status"] == "REVIEW" and item["priority"] == "LOW"
    assert report["area_coverage"][0]["status"] == "PASS"
    assert write_report(report, tmp_path / "repeat") == write_report(report, tmp_path / "repeat")


def test_floor_height_missing_or_tilted_cannot_be_approved() -> None:
    for height, normal in ((None, [0, 0, 1]), (0, [0.1, 0, 0.99])):
        settings = config()
        settings["floor_planes"]["1F"] = {
            "status": "APPROVED",
            "height_m": height,
            "normal": normal,
            "review_id": "review1",
            "source_sha256": "synthetic-fixture",
        }
        report = validate_scene(fixture("complete_walkable"), settings)
        assert report["floor_consistency"]["1F"]["approved"] is False


def test_duplicate_geometry_and_duplicate_semantic_id() -> None:
    scene = fixture("complete_walkable")
    scene["objects"][1]["geometry_sha256"] = "actual-mesh-fingerprint"
    scene["objects"].append({**scene["objects"][1], "object": "WALKABLE_1F_ROOM.001"})
    assert {"DUPLICATE_SEMANTIC_ID", "DUPLICATED_GEOMETRY"} <= codes(
        validate_scene(scene, config())
    )


@pytest.mark.parametrize("scale", [[None, 1, 1], [float("nan"), 1, 1], [1, 1], 1])
def test_malformed_scale_is_reported_and_serializable(scale: Any, tmp_path: Path) -> None:
    scene = fixture("complete_walkable")
    scene["objects"][1]["scale"] = scale
    report = validate_scene(scene, config())
    assert "EXTREME_SCALE" in codes(report)
    write_report(report, tmp_path / "scale")


@pytest.mark.parametrize("normal", [1, [1, 0], [None, 0, 0], [True, 0, 0]])
def test_malformed_portal_orientation_is_review(normal: Any, tmp_path: Path) -> None:
    scene = fixture("one_sided_portal")
    scene["objects"][2]["custom_properties"]["portal_normal"] = normal
    report = validate_scene(scene, config())
    assert "PORTAL_INVALID_ORIENTATION" in codes(report)
    write_report(report, tmp_path / "portal")


def test_malformed_matrix_without_scale_is_review() -> None:
    scene = fixture("complete_walkable")
    scene["objects"][1]["matrix_world"] = [[None] * 4 for _ in range(4)]
    assert "EXTREME_SCALE" in codes(validate_scene(scene, config()))


def test_stair_path_cannot_cross_projected_mesh_hole() -> None:
    from amidst.scene_validation import _segment_in_footprints

    polygons = [[(0, 0), (1, 0), (1, 1), (0, 1)], [(2, 0), (3, 0), (3, 1), (2, 1)]]
    assert not _segment_in_footprints([0.5, 0.5, 0], [2.5, 0.5, 3], polygons, 1e-9)
    assert _segment_in_footprints([0.1, 0.5, 0], [0.9, 0.5, 1], polygons, 1e-9)
