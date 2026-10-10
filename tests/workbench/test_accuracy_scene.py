"""Independent accuracy-v2 scene over frozen E1 RGB, preserving support and scope."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering.facade import ToolFailure
from amidst.engineering.local_pilot import build_run
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.research_accuracy import run as accuracy_run
from amidst.research_accuracy.adapter import load_service
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scenes import (
    load_catalog,
    load_local_camera,
    load_local_camera_accuracy_v2,
)
from amidst.workbench.service import Denied, Workbench


@pytest.fixture(scope="module")
def frozen_accuracy(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    source = tmp_path_factory.mktemp("accuracy-workbench-source")
    config = json.loads(DEFAULT_CONFIG.read_bytes())
    config["duration_s"] = 6.0
    config_path = source.parent / (source.name + "-config.json")
    config_path.write_text(json.dumps(config))
    build_run(source, run_id="accuracy-workbench-source-v1", config_path=config_path)
    root = tmp_path_factory.mktemp("accuracy-workbench-frozen")
    accuracy_run.build(source, root, accuracy_run.default_policy(),
                       experiment_id="accuracy-workbench-fixture-v2")
    return source, root


def test_independent_scene_preserves_original_geometry_rgb_and_separates_freeze_refs(
    frozen_accuracy: tuple[Path, Path],
) -> None:
    source, root = frozen_accuracy
    original, scene = load_local_camera(source), load_local_camera_accuracy_v2(root)
    before, after = original.snapshot(), scene.snapshot()
    assert after["scene_id"] == "local-camera-accuracy-v2"
    assert after["experiment_id"] == "accuracy-workbench-fixture-v2"
    assert after["experiment_version"] == "local-camera-accuracy-v2"
    assert after["variant"] == "end_to_end"
    assert after["observation_mode"] == "photos_plus_observations"
    assert after["decision_stage"] == "RESULTS"
    assert after["source_run_id"] == after["run_id"] == before["run_id"]
    assert after["source_hash"] == before["source_hash"]
    assert after["objects"] == before["objects"] and after["cameras"] == before["cameras"]
    assert scene.service.frames == original.service.frames
    assert after["config_sha256"] != before["config_sha256"]
    assert after["freeze_ref"] != before["freeze_ref"]
    assert set(scene.service.events).isdisjoint(original.service.events)
    assert set(scene.service.observations).isdisjoint(original.service.observations)
    assert after["coordinates"]["normalized_units"] == "METRES"
    assert after["clock"]["unit"] == "SECONDS"
    assert after["formal_phase1_acceptance"] is False
    assert after["capabilities"]["evaluation"] is False
    assert scene.evaluation() == {"status": "UNAVAILABLE", "reason": "NO_PREEXISTING_EVALUATION"}
    public = json.dumps(after)
    assert str(source) not in public and str(root) not in public
    assert "source_locator" not in public and "ground_truth" not in public
    assert original.snapshot() == before


def test_queries_details_media_and_all_eight_original_tools_keep_support_and_alternatives(
    frozen_accuracy: tuple[Path, Path],
) -> None:
    _, root = frozen_accuracy
    scene = load_local_camera_accuracy_v2(root)
    service = scene.service
    sid = service.guard.session_ref
    cameras = service.call("list_cameras", {"session_ref": sid})["items"]
    assert len(cameras) == 4
    assert service.call("resolve_place", {"session_ref": sid, "query": service.scope.place_id})[
        "items"]
    refs = set()
    for camera in cameras:
        query = {"session_ref": sid, "camera_ref": camera["camera_ref"], "time_range": [0, 6]}
        assert service.call("query_observations", query)["retrieval"]["bytes_read"] == 0
        rows = service.call("query_events", query)["items"]
        for summary in rows:
            refs.add(summary["event_ref"])
            canonical = service.events[summary["event_ref"]]
            assert summary["support_state"] == canonical["support_state"]
            assert canonical["support_state"] in {"SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES"}
            event_request = {"session_ref": sid, "event_ref": summary["event_ref"]}
            assert service.call("get_event_summary", event_request)["support_state"] == (
                canonical["support_state"])
            detail = scene.event(summary["event_ref"])
            assert detail == service.call("get_event_detail", event_request)
            replay = service.call("get_replay", {
                **event_request, "timestamp": detail["time_range"][0],
            })
            assert replay["candidates"] == canonical["candidates"]
            assert replay["trajectories"] == canonical["trajectories"]
            assert replay["presentation_only"] is True
            if detail["media_refs"]:
                media_ref = detail["media_refs"][0]
                media = service.call("get_media", {"session_ref": sid, "media_ref": media_ref})
                assert media["evidence_state"] == "RGB_PIXELS"
                assert scene.media(media_ref)[1].startswith(b"\x89PNG")
    assert refs


def test_other_mode_variant_original_refs_and_input_stage_cannot_read_new_results(
    frozen_accuracy: tuple[Path, Path],
) -> None:
    source, root = frozen_accuracy
    scene = load_local_camera_accuracy_v2(root)
    for foreign in (load_local_camera(source).service,
                    load_service(root, variant="baseline", mode="photos_plus_observations"),
                    load_service(root, variant="end_to_end", mode="photos_only")):
        with pytest.raises(ToolFailure, match="^REFERENCE_DENIED$"):
            scene.event(next(iter(foreign.events)))
    input_service = load_service(root, variant="end_to_end", mode="photos_only", input_stage=True)
    with pytest.raises(ToolFailure, match="^STAGE_DENIED$"):
        input_service.call("get_event_detail", {"session_ref": input_service.guard.session_ref,
                                                "event_ref": next(iter(input_service.events))})


def test_workbench_role_and_scene_bounds_keep_accuracy_research_separate(
    frozen_accuracy: tuple[Path, Path], tmp_path: Path,
) -> None:
    _, root = frozen_accuracy
    scene = load_local_camera_accuracy_v2(root)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(tmp_path / "reviews.db", {
        scene.scene_id: {key: scene.snapshot()[key] for key in keys},
    })
    workbench = Workbench({scene.scene_id: scene}, reviews)
    research = workbench.session({"role": "research"})["session_ref"]
    manager = workbench.session({"role": "management"})["session_ref"]
    request = {"session_ref": research, "scene_id": scene.scene_id}
    assert workbench.call("scene", request)["snapshot"]["experiment_version"] == (
        "local-camera-accuracy-v2")
    assert workbench.call("evaluation", request)["evaluation"]["status"] == "UNAVAILABLE"
    with pytest.raises(Denied, match="^ROLE_DENIED$"):
        workbench.call("evaluation", {**request, "session_ref": manager})
    with pytest.raises(Denied, match="^SCENE_DENIED$"):
        workbench.call("scene", {**request, "scene_id": "local-camera"})
    event_ref = next(iter(scene.service.events))
    detail = workbench.call("event", {**request, "event_ref": event_ref})["event"]
    assert detail["support_state"] == scene.service.events[event_ref]["support_state"]


def test_loader_never_calls_producer_or_opens_gt_recipe_evaluation(
    frozen_accuracy: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, root = frozen_accuracy
    before = load_local_camera_accuracy_v2(root).snapshot()
    original_open = Path.open

    def no_truth(path: Path, *args: Any, **kwargs: Any) -> Any:
        assert not {"simulation", "export", "evaluation"} & set(path.parts)
        assert path.name not in {"ground_truth.json", "recipe.json", "reference.json"}
        return original_open(path, *args, **kwargs)

    def no_producer(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("frozen scene must never rerun producer")

    monkeypatch.setattr(Path, "open", no_truth)
    monkeypatch.setattr(accuracy_run, "produce_perception", no_producer)
    monkeypatch.setattr(accuracy_run, "produce_perception_v2", no_producer)
    assert load_local_camera_accuracy_v2(root).snapshot() == before


@pytest.mark.parametrize("field,value", [
    ("unit", "NATIVE_BU"), ("experiment_id", "another-experiment"),
    ("context_sha256", "f" * 64), ("source_manifest_sha256", "f" * 64),
])
def test_manifest_source_unit_config_and_experiment_tamper_fail_closed(
    frozen_accuracy: tuple[Path, Path], tmp_path: Path, field: str, value: str,
) -> None:
    _, original = frozen_accuracy
    root = tmp_path / "frozen"
    shutil.copytree(original, root)  # Only frozen JSON; source RGB are never copied.
    path = root / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest[field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        load_local_camera_accuracy_v2(root)


def test_fixed_catalog_loads_new_adapter_and_keeps_missing_checkpoint_unavailable(
    frozen_accuracy: tuple[Path, Path], tmp_path: Path,
) -> None:
    _, root = frozen_accuracy
    manifest = {"schema_version": "workbench.catalog.v1", "scenes": [{
        "scene_id": "local-camera-accuracy-v2", "adapter": "local_camera_accuracy_v2",
        "checkpoint": "missing-local-freeze", "label": "Independent accuracy v2",
        "description": "Same source, distinct frozen experiment",
    }]}
    config = tmp_path / "catalog.json"
    config.write_text(json.dumps(manifest))
    assert load_catalog(tmp_path, manifest_path=config) == {}
    catalog = load_catalog(tmp_path, {"local-camera-accuracy-v2": root}, manifest_path=config)
    assert list(catalog) == ["local-camera-accuracy-v2"]
    assert catalog["local-camera-accuracy-v2"].snapshot()["experiment_id"] == (
        "accuracy-workbench-fixture-v2")
