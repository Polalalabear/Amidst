"""Review authority, concurrency and immutable-source regression checks."""

from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from amidst.workbench.reviews import ReviewStore


def scene(scene_id: str = "scene-a") -> dict[str, Any]:
    return {
        "scene_id": scene_id, "source_hash": "a" * 64, "model_revision": "model-v1",
        "run_id": "run-" + scene_id,
        "objects": [
            {"object_id": "region-a", "kind": "REGION", "label": "Room", "semantic": "ROOM",
             "geometry": {"type": "polygon", "points": [[0, 0, 0], [4, 0, 0],
                                                        [4, 3, 0], [0, 3, 0]]},
             "properties": {"floor_id": None, "region_id": "A"},
             "editable_fields": ["label", "semantic", "geometry", "properties"],
             "authority": "SYNTHETIC_CONFIG"},
            {"object_id": "portal-a", "kind": "PORTAL", "label": "Door", "semantic": "DOOR",
             "geometry": {"type": "line", "points": [[4, 1, 0], [4, 2, 0]]},
             "properties": {"width": 1, "enter_normal_xy": [1, 0]},
             "editable_fields": ["label", "semantic", "geometry", "properties"],
             "authority": "SYNTHETIC_CONFIG"},
            {"object_id": "camera-a", "kind": "CAMERA", "label": "Camera", "semantic": "CAMERA",
             "geometry": {"type": "point", "points": [[0, 0, 3]]},
             "properties": {
                 "calibration_kind": "PINHOLE", "position": [0, 0, 3],
                 "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 3], [0, 0, 0, 1]],
                 "convention": "BLENDER_NEG_Z_UP_Y", "fx": 500, "fy": 500,
                 "cx": 320, "cy": 240, "width": 640, "height": 480,
             },
             "editable_fields": ["label", "geometry", "properties"],
             "authority": "SYNTHETIC_CONFIG"},
        ],
    }


@pytest.fixture
def store(tmp_path: Path) -> ReviewStore:
    return ReviewStore(tmp_path / "review.sqlite", {"scene-a": scene()})


def draft(store: ReviewStore, changes: dict[str, Any] | None = None,
          object_id: str = "region-a", version: int = 0) -> dict[str, Any]:
    return store.save_draft("scene-a", object_id, changes or {"label": "Reviewed room"},
                            version, "Researcher", "Visible boundary evidence")


def test_publish_requires_validation_and_preserves_every_source_value(
    store: ReviewStore, tmp_path: Path,
) -> None:
    original = scene()
    saved = draft(store)
    with pytest.raises(ValueError, match="VALIDATION_REQUIRED"):
        store.publish_draft(saved["draft_id"], "Reviewer", "Reviewed", 0)
    assert store.validate_draft(saved["draft_id"])["valid"]
    published = store.publish_draft(saved["draft_id"], "Reviewer", "Evidence sufficient", 0)
    state = store.state("scene-a")
    assert state["current_version"] == 1
    assert state["objects"][0]["label"] == "Reviewed room"
    assert state["baseline_objects"] == original["objects"]
    assert published["before"] == original["objects"][0]
    assert published["authority"] == "SYNTHETIC_REVIEW_ONLY"
    assert published["formal_approval"] is False
    assert published["affected_runs"] == [{"run_id": "run-scene-a", "status": "NEEDS_RERUN"}]
    assert state["drafts"][0]["status"] == "PUBLISHED"
    assert [x["status"] for x in state["history"]] == [
        "BASELINE", "DRAFT", "VALIDATED", "PUBLISHED",
    ]
    reopened = ReviewStore(tmp_path / "review.sqlite", {"scene-a": original})
    assert reopened.state("scene-a") == state
    state["baseline_objects"][0]["label"] = "Caller mutation"
    assert store.state("scene-a")["baseline_objects"] == original["objects"]


def test_stale_drafts_cannot_publish_or_silently_rebase(store: ReviewStore) -> None:
    first = draft(store)
    stale = draft(store, {"label": "Other edit"})
    assert store.validate_draft(first["draft_id"])["valid"]
    assert store.validate_draft(stale["draft_id"])["valid"]
    store.publish_draft(first["draft_id"], "Reviewer", "First accepted", 0)
    for expected in (0, 1):
        with pytest.raises(ValueError, match="VERSION_CONFLICT"):
            store.publish_draft(stale["draft_id"], "Reviewer", "Other accepted", expected)
    assert store.validate_draft(stale["draft_id"])["errors"] == ["VERSION_CONFLICT"]
    assert store.state("scene-a")["drafts"][1]["status"] == "STALE"
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        draft(store, {"label": "Late edit"})
    with pytest.raises(ValueError, match="VERSION_INVALID"):
        draft(store, version=True)


@pytest.mark.parametrize("change", [
    {"authority": "FORMAL"}, {"object_id": "other"}, {"kind": "WALKABLE"},
    {"editable_fields": ["authority"]},
])
def test_identity_and_authority_cannot_be_edited(
    store: ReviewStore, change: dict[str, Any],
) -> None:
    with pytest.raises(ValueError, match="FIELD_NOT_EDITABLE"):
        draft(store, change)


@pytest.mark.parametrize("points", [
    [[0, 0, 0], [1, 1, 0], [2, 2, 0]],
    [[0, 0, 0], [2, 2, 0], [2, 0, 0], [0, 2, 0]],
    [[0, 0, 0], [2, 0, 0], [2, 2, 1], [0, 2, 0]],
    [[0, 0, 0], [2, 0, 0], [2, 2, 0], [2, 0, 0]],
    [[0, 0, 0], [2, 0, 0]],
])
def test_invalid_polygons_remain_drafts(store: ReviewStore, points: list[list[float]]) -> None:
    saved = draft(store, {"geometry": {"type": "polygon", "points": points}})
    validation = store.validate_draft(saved["draft_id"])
    assert not validation["valid"]
    with pytest.raises(ValueError, match="VALIDATION_FAILED"):
        store.publish_draft(saved["draft_id"], "Reviewer", "Attempt", 0)
    assert store.state("scene-a")["current_version"] == 0


@pytest.mark.parametrize("change,error", [
    ({"semantic": "APPROVED_SAFE"}, "SEMANTIC_UNSUPPORTED"),
    ({"semantic": {}}, "SEMANTIC_UNSUPPORTED"),
    ({"properties": {"execute": "a command"}}, "PROPERTIES_UNSUPPORTED"),
    ({"geometry": {"type": "polygon", "points": [[True, 0, 0]]}},
     "GEOMETRY_COORDINATES_INVALID"),
])
def test_invalid_semantics_and_properties_are_rejected(
    store: ReviewStore, change: dict[str, Any], error: str,
) -> None:
    saved = draft(store, change)
    assert error in store.validate_draft(saved["draft_id"])["errors"]


def test_nonfinite_cannot_enter_persisted_json(store: ReviewStore) -> None:
    with pytest.raises(ValueError):
        draft(store, {"geometry": {"type": "polygon", "points": [[float("nan"), 0, 0]]}})
    assert store.state("scene-a")["drafts"] == []


def test_portal_endpoints_and_normal_checked(store: ReviewStore) -> None:
    saved = draft(store, {"geometry": {"type": "line", "points": [[1, 2, 0], [1, 2, 0]]}},
                  "portal-a")
    assert "PORTAL_ENDPOINTS_INVALID" in store.validate_draft(saved["draft_id"])["errors"]
    saved = draft(store, {"properties": {"enter_normal_xy": [0, 0]}}, "portal-a")
    assert "PORTAL_NORMAL_INVALID" in store.validate_draft(saved["draft_id"])["errors"]


@pytest.mark.parametrize("key,value,error", [
    ("fx", 0, "CAMERA_CALIBRATION_INVALID"),
    ("fy", -1, "CAMERA_CALIBRATION_INVALID"),
    ("width", 640.5, "CAMERA_DIMENSION_INVALID"),
    ("camera_to_world", [[1, 2]], "CAMERA_MATRIX_INVALID"),
    ("position", [1, 2, 3], "CAMERA_POSE_INCONSISTENT"),
    ("convention", "WHATEVER", "PROPERTY_IDENTITY_IMMUTABLE"),
    ("calibration_kind", "UNAVAILABLE", "PROPERTY_IDENTITY_IMMUTABLE"),
])
def test_calibration_edits_validate_physical_metadata(
    store: ReviewStore, key: str, value: object, error: str,
) -> None:
    props = scene()["objects"][2]["properties"]
    props[key] = value
    saved = draft(store, {"properties": props}, "camera-a")
    assert error in store.validate_draft(saved["draft_id"])["errors"]


def test_affine_camera_keeps_unknown_pose_and_invertible_map(tmp_path: Path) -> None:
    snapshot = scene()
    camera = snapshot["objects"][2]
    camera["geometry"]["points"] = []
    camera["editable_fields"] = ["label", "properties"]
    camera["properties"] = {
        "calibration_kind": "AFFINE_GROUND_PLANE_SYNTHETIC", "position": None,
        "ground_to_pixel": [[10, 0, 0], [0, 10, 0]], "plane_z_m": 0,
        "width": 640, "height": 480, "physical_pose_status": "UNKNOWN",
    }
    store = ReviewStore(tmp_path / "affine.sqlite", {"scene-a": snapshot})
    saved = draft(store, {"label": "Affine camera"}, "camera-a")
    assert store.validate_draft(saved["draft_id"])["valid"]
    with pytest.raises(ValueError, match="FIELD_NOT_EDITABLE"):
        draft(store, {"geometry": {"type": "point", "points": [[0, 0, 3]]}}, "camera-a")
    props = copy.deepcopy(camera["properties"])
    props["ground_to_pixel"] = [[10, 0, 0], [20, 0, 0]]
    saved = draft(store, {"properties": props}, "camera-a")
    assert "CAMERA_AFFINE_DEGENERATE" in store.validate_draft(saved["draft_id"])["errors"]


def test_result_reviews_and_notes_never_change_scene_or_algorithm(store: ReviewStore) -> None:
    baseline = store.state("scene-a")["objects"]
    result = store.record_result("scene-a", "event-1", "MORE_EVIDENCE", "Occluded", "A",
                                 "run-scene-a")
    note = store.record_note("scene-a", "event-1", "IN_PROGRESS", "Checking camera", "B",
                             "run-scene-a")
    state = store.state("scene-a")
    assert state["current_version"] == 0
    assert state["objects"] == baseline
    assert state["result_reviews"] == [result]
    assert state["notes"] == [note]
    assert not result["algorithm_result_modified"] and not note["algorithm_result_modified"]
    assert "decision" not in note
    with pytest.raises(ValueError, match="RESULT_RUN_MISMATCH"):
        store.record_result("scene-a", "event-1", "SUPPORT", "Reason", "A", "other-run")
    with pytest.raises(ValueError, match="RESULT_DECISION_INVALID"):
        store.record_result("scene-a", "event-1", "FORMAL_PASS", "Reason", "A", "run-scene-a")


def test_scene_registration_is_immutable_and_scene_scope_isolated(tmp_path: Path) -> None:
    scenes = {"scene-a": scene(), "scene-b": scene("scene-b")}
    store = ReviewStore(tmp_path / "reviews.sqlite", scenes)
    saved = draft(store)
    assert store.state("scene-b")["drafts"] == []
    only_b = ReviewStore(tmp_path / "reviews.sqlite", {"scene-b": scenes["scene-b"]})
    with pytest.raises(ValueError, match="SCENE_NOT_FOUND"):
        only_b.validate_draft(saved["draft_id"])
    changed = scene()
    changed["source_hash"] = "b" * 64
    with pytest.raises(ValueError, match="SCENE_REGISTRATION_MISMATCH"):
        ReviewStore(tmp_path / "reviews.sqlite", {"scene-a": changed})


def test_sql_append_only_triggers_and_corruption_detection(store: ReviewStore) -> None:
    saved = draft(store)
    with sqlite3.connect(store.db_path) as db:
        for statement in ("DELETE FROM drafts", "UPDATE scenes SET hash='bad'"):
            with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY_REVIEW_STORE"):
                db.execute(statement)
        # External file tampering must still be detected if a trigger is removed.
        db.execute("DROP TRIGGER drafts_no_update")
        db.execute("UPDATE drafts SET payload=? WHERE id=?",
                   (json.dumps({"tampered": True}), saved["draft_id"]))
    with pytest.raises(ValueError, match="REVIEW_INTEGRITY_MISMATCH"):
        ReviewStore(store.db_path, {"scene-a": scene()})


def test_reopened_writer_observes_committed_version_conflict(store: ReviewStore) -> None:
    second = ReviewStore(store.db_path, {"scene-a": scene()})
    saved = draft(store)
    second.validate_draft(saved["draft_id"])
    second.publish_draft(saved["draft_id"], "Other reviewer", "Accepted", 0)
    with pytest.raises(ValueError, match="VERSION_CONFLICT"):
        draft(store)
    assert store.state("scene-a")["current_version"] == 1


def test_portal_region_references_and_calibration_capabilities_cannot_be_invented(
    store: ReviewStore,
) -> None:
    saved = draft(store, {"properties": {
        "inside_region_id": "A", "outside_region_id": "missing", "enter_normal_xy": [1, 0],
    }}, "portal-a")
    assert "PORTAL_REGION_REFERENCE_INVALID" in store.validate_draft(saved["draft_id"])["errors"]
    props = scene()["objects"][2]["properties"]
    props["calibration_kind"] = ["PINHOLE"]
    saved = draft(store, {"properties": props}, "camera-a")
    assert not store.validate_draft(saved["draft_id"])["valid"]


def test_arbitrary_large_coordinates_fail_validation(store: ReviewStore) -> None:
    saved = draft(store, {"geometry": {"type": "line", "points": [
        [10 ** 500, 0, 0], [0, 0, 0],
    ]}}, "portal-a")
    assert "GEOMETRY_COORDINATES_INVALID" in store.validate_draft(saved["draft_id"])["errors"]
