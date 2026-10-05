"""Safety regression checks for formal patch marking without source/doorway mutation."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
from typing import Any

import pytest


def marking_module() -> Any:
    path = Path(__file__).parents[2] / "scripts" / "apply_wall_candidate_markings.py"
    spec = importlib.util.spec_from_file_location("wall_candidate_markings", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def document_fixture() -> dict[str, Any]:
    row = {
        "candidate_id": "WALL-PATCH-00001",
        "floor": "1F",
        "object": "mixed_group",
        "status": "AUTO_CONFIRMED_WALL",
        "semantic_class": "WALL",
        "protected_portal_conflicts": [],
        "walkable_relation": {"interior_conflicts": []},
        "material_review_flags": [],
        "hidden_render": False,
        "hidden_viewport": False,
        "evaluated_face_indices": [3, 5],
        "annotation": {
            "evaluated_face_indices": [3, 5],
            "create_or_fill_geometry": False,
            "movement_collider_installed": False,
        },
        "nearby_area": [{"object": "AREA_1F_TEST"}],
        "nearby_portal": [],
        "reasons": ["VERTICAL_CONTINUOUS_OPAQUE_FULL_HEIGHT_SURFACE_WITH_FLOOR_CONTACT"],
        "bounds": {"minimum": [0, 0, 0], "maximum": [0, 100, 140]},
    }
    review = copy.deepcopy(row)
    review.update(
        candidate_id="WALL-PATCH-00002",
        status="HUMAN_REVIEW",
        semantic_class="WALL_CANDIDATE",
        evaluated_face_indices=[7],
    )
    review["annotation"]["evaluated_face_indices"] = []
    return {
        "schema_version": "source-bound-wall-candidates-pilot-v1",
        "label": "PILOT / SYNTHETIC SAMPLE",
        "authority": "GEOMETRY_DERIVED_PATCH_SIDECAR",
        "policy": {"gt_used": False, "whole_objects_reclassified": False},
        "summary": {"auto_confirmed_wall_patches": 1, "human_review_patches": 1},
        "candidates": [row, review],
        "source": {"sha256": "a" * 64},
        "evaluated_scene": {"frame": 220, "subframe": 0.0},
    }


def test_only_confirmed_patch_marked_without_reclassifying_mixed_object() -> None:
    marking = marking_module()
    document = document_fixture()
    assert marking.validate_document(document) == [document["candidates"][0]]
    assert marking.annotation_name(document["candidates"][0]) == "WALL_1F_PATCH_00001"
    props = marking.annotation_properties(document["candidates"][0], document, "b" * 64)
    assert props["semantic_class"] == "WALL"
    assert props["source_object"] == "mixed_group"
    assert props["source_face_indices"] == [3, 5]
    assert props["annotation_only"] is True
    assert props["physical_role_approved"] is False
    assert props["movement_collider_installed"] is False


@pytest.mark.parametrize("conflict", ["portal", "walkable", "material", "hidden", "infill"])
def test_unsafe_confirmed_candidate_never_creates_marking(conflict: str) -> None:
    marking = marking_module()
    document = document_fixture()
    row = document["candidates"][0]
    if conflict == "portal":
        row["protected_portal_conflicts"] = ["PORTAL_1F_TEST"]
    elif conflict == "walkable":
        row["walkable_relation"]["interior_conflicts"] = [{"object": "WALK_1F_TEST"}]
    elif conflict == "material":
        row["material_review_flags"] = ["TRANSMISSIVE_SHADER"]
    elif conflict == "hidden":
        row["hidden_render"] = True
    else:
        row["annotation"]["create_or_fill_geometry"] = True
    with pytest.raises(ValueError, match="unsafe confirmed"):
        marking.validate_document(document)


def test_human_review_face_selection_and_duplicate_ids_rejected() -> None:
    marking = marking_module()
    document = document_fixture()
    document["candidates"][1]["annotation"]["evaluated_face_indices"] = [7]
    with pytest.raises(ValueError, match="HUMAN_REVIEW"):
        marking.validate_document(document)
    document = document_fixture()
    document["candidates"][1]["candidate_id"] = document["candidates"][0]["candidate_id"]
    with pytest.raises(ValueError, match="duplicate"):
        marking.validate_document(document)


def test_live_geometry_drift_rejects_stale_source_bound_candidate() -> None:
    marking = marking_module()
    original = document_fixture()["candidates"][0]
    live = copy.deepcopy(original)
    marking.verify_live_candidate(original, live)
    live["bounds"]["maximum"][1] += 0.1
    with pytest.raises(ValueError, match="live candidate differs"):
        marking.verify_live_candidate(original, live)


def test_actual_face_copy_keeps_door_gap_despite_overlapping_combined_bounds() -> None:
    marking = marking_module()
    extraction = marking.extraction_module()
    left = [[0, 0, 0], [0, 30, 0], [0, 30, 100], [0, 0, 100]]
    right = [[0, 70, 0], [0, 100, 0], [0, 100, 100], [0, 70, 100]]
    vertices, faces = marking.polygons_to_mesh([left, right])
    copied = [[vertices[i] for i in face] for face in faces]
    assert copied == [left, right]
    portal = {"minimum": [-1, 40, 0], "maximum": [1, 60, 100]}
    assert extraction.bounds(vertices)["maximum"][1] == 100
    assert sum(extraction.polygon_area(extraction.clip_polygon_box(p, portal)) for p in copied) == 0


def test_invalid_source_polygons_rejected() -> None:
    marking = marking_module()
    with pytest.raises(ValueError, match="invalid evaluated"):
        marking.polygons_to_mesh([[[0, 0, 0], [0, 1, 0], [0, 1, float("nan")]]])
    with pytest.raises(ValueError, match="empty geometry"):
        marking.polygons_to_mesh([])


def test_inherited_nonfinite_camera_is_preserved_as_distinct_snapshot_identity() -> None:
    marking = marking_module()
    state = {"camera": {"lens": float("inf"), "clip_end": float("-inf")}}
    encoded = marking.snapshot_value(state)
    assert encoded["camera"]["lens"] == {"inherited_nonfinite_float": "inf"}
    assert encoded["camera"]["clip_end"] == {"inherited_nonfinite_float": "-inf"}
    assert state["camera"]["lens"] == float("inf")
    assert marking.json_digest(encoded) != marking.json_digest(
        marking.snapshot_value({"camera": {"lens": 50.0, "clip_end": float("-inf")}})
    )


def test_current_fresh_source_bound_candidates_pass_document_preflight() -> None:
    # A regression check on the actual tracked evidence, separate from Blender live checks.
    import json

    marking = marking_module()
    path = Path(__file__).parents[2] / "data/scene_audit/school_v3_wall_candidates.json"
    confirmed = marking.validate_document(json.loads(path.read_text()))
    assert len(confirmed) == 81
    assert len({row["object"] for row in confirmed}) == 7
