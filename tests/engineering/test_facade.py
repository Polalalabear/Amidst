import json
import shutil
from pathlib import Path

import pytest

from amidst.engineering.access import SessionGuard
from amidst.engineering.facade import AgentFacade, ToolFailure
from amidst.engineering.run import load_facades, materialize_run


@pytest.fixture(scope="module")
def frozen(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("engineering-frozen")
    materialize_run(root, Path("configs/engineering/simulation_v1.json"), run_id="facade-test-v1")
    return root


@pytest.fixture
def facade(frozen: Path) -> AgentFacade:
    return load_facades(frozen)[0]


def test_same_photo_modes_and_canonical_repositories(frozen: Path) -> None:
    local = load_facades(frozen)
    memory = load_facades(frozen, storage="MEMORY")
    assert local[0].snapshot == local[1].snapshot == memory[0].snapshot
    assert local[0].guard.binding.dataset_sha256 == local[1].guard.binding.dataset_sha256
    assert local[0].guard.binding.observation_mode == "photos_only"
    assert local[1].guard.binding.observation_mode == "photos_plus_observations"
    assert local[0].guard.session_ref != local[1].guard.session_ref


def test_full_tool_flow_and_narrow_query_preserves_endpoints(facade: AgentFacade) -> None:
    session = {"session_ref": facade.guard.session_ref}
    assert facade.invoke("resolve_place", session | {"query": "lab"})["items"]
    assert len(facade.invoke("list_cameras", session)["items"]) == 2
    event = next(e for e in facade.events if e.candidate_count and e.replay_ref)
    summary = facade.invoke("get_event_summary", session | {"event_ref": event.event_ref})
    midpoint = sum(event.time_range) / 2
    queried = facade.invoke("query_events", session | {"time_range": [midpoint, midpoint]})
    assert event.event_ref in [e["event_ref"] for e in queried["items"]]
    detail = facade.invoke("get_event_detail", session | {"event_ref": event.event_ref})
    gap = next(g for g in facade.snapshot.gaps if g.event.event_id == event.canonical_event_id)
    assert detail["canonical_endpoint_ids"] == list(gap.event.observation_ids)
    assert detail["candidates"] == [c.model_dump(mode="json") for c in gap.event.candidates]
    assert detail["hypotheses"] == [h.model_dump(mode="json") for h in gap.event.trajectories]
    replay = facade.invoke("get_replay", session | {"event_ref": event.event_ref,
                                                  "timestamp": midpoint})
    assert len(replay["markers"]) == summary["hypothesis_count"]
    media = facade.invoke("get_media", session | {"media_ref": event.media_refs[0]})
    assert media["annotations"] == "NONE" and media["content_base64"]


def test_empty_ambiguity_hold_and_region_queries(facade: AgentFacade) -> None:
    session = {"session_ref": facade.guard.session_ref}
    assert not facade.invoke("query_events", session | {"time_range": [100, 101]})["items"]
    assert not facade.invoke("resolve_place", session | {"query": "unknown"})["items"]
    assert any(e.kind == "OVERLAPPING_VISIBILITY" for e in facade.events)
    holds = [e for e in facade.events if e.kind == "SAME_CAMERA_RECOVERY"]
    assert holds and all(e.complete is None and e.replay_ref is None for e in holds)
    assert facade.invoke("query_events", session | {"time_range": [0, 10],
                                                    "region_id": "central"})["items"]


@pytest.mark.parametrize("tool,args", [
    ("query_observations", {"time_range": [0, 10]}),
    ("query_events", {"time_range": [0, 10]}),
    ("get_event_summary", {}), ("get_event_detail", {}), ("get_replay", {"timestamp": 3}),
])
def test_input_stage_denies_stored_answers(facade: AgentFacade, tool: str,
                                         args: dict[str, object]) -> None:
    guard = SessionGuard(facade.guard.binding)
    blocked = AgentFacade(facade.store, facade.scope, guard, facade.snapshot,
                          facade.observations, facade.events)
    event = facade.events[0]
    if tool.startswith("get_event") or tool == "get_replay":
        args = args | {"event_ref": event.event_ref}
    with pytest.raises(ToolFailure, match="STAGE_DENIED"):
        blocked.invoke(tool, {"session_ref": guard.session_ref} | args)  # type: ignore[arg-type]
    context = blocked.context()
    assert context["decision_stage"] == "INPUT" and context["freeze_ref"] is None
    assert not any(key in json.dumps(blocked.logs) for key in ("world_position", "region_ids"))


def test_plus_input_measurements_and_photos_remain_allowed(frozen: Path) -> None:
    original = load_facades(frozen)[1]
    guard = SessionGuard(original.guard.binding)
    facade = AgentFacade(original.store, original.scope, guard, original.snapshot,
                         original.observations, original.events)
    result = facade.invoke("query_observations", {"session_ref": guard.session_ref,
                                                  "time_range": [0, 10]})
    assert result["items"] and result["items"][0]["measurements"]
    assert all("projected_positions" not in o and "region_ids" not in o for o in result["items"])


@pytest.mark.parametrize("extra", [
    {"decision_stage": "RESULTS"}, {"observation_mode": "photos_plus_observations"},
    {"run_id": "other"}, {"source_id": "private"}, {"sql": "select * from gt"},
])
def test_caller_cannot_change_bound_manifest(facade: AgentFacade,
                                           extra: dict[str, str]) -> None:
    with pytest.raises(ToolFailure, match="INVALID_OR_UNAVAILABLE"):
        facade.invoke("list_cameras", {"session_ref": facade.guard.session_ref} | extra)


def test_references_errors_logs_and_gt_do_not_leak(facade: AgentFacade) -> None:
    sentinel = "/Users/private/SECRET_GT_ACTOR"
    session = {"session_ref": facade.guard.session_ref}
    with pytest.raises(ToolFailure):
        facade.invoke("query_events", session | {"time_range": [0, 10],
                                                 "camera_ref": "camera:" + "f" * 24})
    with pytest.raises(ToolFailure):
        facade.invoke("get_media", session | {"media_ref": sentinel})
    with pytest.raises(ToolFailure):
        facade.invoke(sentinel, session)  # type: ignore[arg-type]
    results = facade.invoke("query_events", session | {"time_range": [0, 10]})
    encoded = json.dumps({"context": facade.context(), "logs": facade.logs, "results": results})
    assert sentinel not in encoded
    for forbidden in ("actor_identity", "blue-person-a", "blue-person-b", "recipe",
                      "source_video_reference", "simulation_export_path", "/Users/", "navmesh"):
        assert forbidden not in encoded


def test_actual_missing_media_and_snapshot_are_rejected(frozen: Path, tmp_path: Path) -> None:
    root = tmp_path / "run"
    shutil.copytree(frozen, root)
    f = load_facades(root)[0]
    media = f.frames[0]
    (root / media.relative_path).unlink()
    with pytest.raises(ToolFailure):
        f.invoke("get_media", {"session_ref": f.guard.session_ref, "media_ref": media.media_ref})
    with pytest.raises(ValueError):
        load_facades(root)
    shutil.copytree(frozen, root, dirs_exist_ok=True)
    missing = root / "snapshot_photos_only.json"
    missing.unlink()
    with pytest.raises(ValueError, match="snapshot reference is missing"):
        load_facades(root)
    assert not missing.exists()


@pytest.mark.parametrize("file,mutation", [
    ("static_context.json", "context"), ("engineering_config.json", "config"),
    ("run_manifest.json", "links"), ("run_manifest.json", "media"),
])
def test_tampered_bindings_fail_before_result_read(frozen: Path, tmp_path: Path,
                                                file: str, mutation: str) -> None:
    root = tmp_path / "run"
    shutil.copytree(frozen, root)
    path = root / file
    data = json.loads(path.read_bytes())
    if mutation == "context":
        data["detour_waypoints_m"][0][0] += 0.1
    elif mutation == "config":
        data["fps"] += 1
    elif mutation == "links":
        keys = list(data["frame_links"])
        data["frame_links"][keys[0]], data["frame_links"][keys[1]] = (
            data["frame_links"][keys[1]], data["frame_links"][keys[0]],
        )
    else:
        data["receipts"][0]["binding"]["media_sha256"] = "f" * 64
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_facades(root)
