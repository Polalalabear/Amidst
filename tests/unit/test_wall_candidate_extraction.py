"""Meaningful regression guards for actual face/portal and thin-panel classification."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def extraction_module() -> Any:
    path = Path(__file__).parents[2] / "scripts" / "extract_wall_candidates.py"
    spec = importlib.util.spec_from_file_location("wall_candidate_extraction", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_actual_face_clipping_does_not_treat_aabb_as_door_infill() -> None:
    extraction = extraction_module()
    portal = {"minimum": [-1, 40, 0], "maximum": [1, 60, 100]}
    left_wall = [[0, 0, 0], [0, 30, 0], [0, 30, 100], [0, 0, 100]]
    right_wall = [[0, 70, 0], [0, 100, 0], [0, 100, 100], [0, 70, 100]]
    # Combined wall bounds contain the entire door, while neither actual face does.
    assert extraction.polygon_area(extraction.clip_polygon_box(left_wall, portal)) == 0
    assert extraction.polygon_area(extraction.clip_polygon_box(right_wall, portal)) == 0
    panel_across_door = [[0, 0, 0], [0, 100, 0], [0, 100, 100], [0, 0, 100]]
    assert extraction.polygon_area(extraction.clip_polygon_box(panel_across_door, portal)) == 2000


def test_backface_polygon_area_is_independent_of_winding() -> None:
    extraction = extraction_module()
    polygon = [[0, 0, 0], [0, 40, 0], [0, 40, 100], [0, 0, 100]]
    assert extraction.polygon_area(polygon) == extraction.polygon_area(polygon[::-1]) == 4000


def test_horizontal_sections_preserve_actual_doorway_gap() -> None:
    extraction = extraction_module()
    polygons = [
        [[0, 0, 0], [0, 30, 0], [0, 30, 100], [0, 0, 100]],
        [[0, 70, 0], [0, 100, 0], [0, 100, 100], [0, 70, 100]],
    ]
    assert extraction.horizontal_sections(polygons, 20, [0, 1, 0]) == [[0, 30], [70, 100]]


def classify_fixture(with_portal: bool = False, narrow: bool = False) -> dict[str, Any]:
    extraction = extraction_module()
    extent = 60 if narrow else 400
    polygon = [[0, 0, 0], [0, extent, 0], [0, extent, 140], [0, 0, 140]]
    patch = {
        "candidate_id": "WALL-TEST",
        "object": "architectural_mesh",
        "bounds": extraction.bounds(polygon),
        "normal": [1, 0, 0],
        "plane": 0,
        "tangent": [0, 1, 0],
        "tangent_interval": [0, extent],
        "height": 140,
        "extent": extent,
        "rectangular_fill_ratio": 1,
        "polygons": [polygon],
        "material_review_flags": [],
        "hidden_render": False,
        "hidden_viewport": False,
        "evaluated_face_indices": [0],
    }
    region = {"minimum": [1, 0, 0], "maximum": [100, 400, 0]}
    semantic = {
        "AREA": [{"object": "AREA_1F_TEST", "floor": "1F", "bounds": region}],
        "WALKABLE": [
            {
                "object": "WALK_1F_TEST",
                "floor": "1F",
                "bounds": region,
                "triangles": [
                    [[1, 0, 0], [100, 0, 0], [100, 400, 0]],
                    [[1, 0, 0], [100, 400, 0], [1, 400, 0]],
                ],
            }
        ],
        "PORTAL": (
            [
                {
                    "object": "PORTAL_1F_TEST",
                    "floor": "1F",
                    "bounds": {"minimum": [-2, 100, 0], "maximum": [2, 150, 140]},
                }
            ]
            if with_portal
            else []
        ),
    }
    params = {
        "near_distance": 35,
        "portal_padding": 0.28,
        "weld_epsilon": 0.0014,
        "section_above_floor": 21,
        "walk_probe_offset": 0.7,
        "thickness_min": 2.1,
        "thickness_max": 28,
        "auto_min_height": 105,
        "auto_max_height": 161,
        "auto_min_extent": 105,
        "floor_contact_tolerance": 9.8,
        "broad_sheet_min_extent": 280,
    }
    extraction.classify(patch, [patch], semantic, {"1F": 0, "2F": 140}, params)
    return patch


def test_portal_conflict_never_creates_wall_annotation() -> None:
    clear = classify_fixture()
    assert clear["status"] == "AUTO_CONFIRMED_WALL"
    assert clear["annotation"]["evaluated_face_indices"] == [0]
    conflict = classify_fixture(with_portal=True)
    assert conflict["status"] == "HUMAN_REVIEW"
    assert conflict["protected_portal_conflicts"] == ["PORTAL_1F_TEST"]
    assert conflict["annotation"]["evaluated_face_indices"] == []


def test_narrow_thin_panel_is_retained_for_human_review() -> None:
    panel = classify_fixture(narrow=True)
    assert panel["status"] == "HUMAN_REVIEW"
    assert "NARROW_DOOR_PANEL_COLUMN_OR_DECOR_REVIEW" in panel["reasons"]
    assert panel["annotation"]["evaluated_face_indices"] == []
