"""Actual small frozen RGB product joined to server-owned workbench research roles."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering.access import SessionGuard
from amidst.engineering.local_pilot import build_run
from amidst.engineering.registry import opaque_ref
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.product import run as product_run
from amidst.product.run import build_product, load_product
from amidst.workbench.product_bridge import BinaryResponse, BridgeDenied, ProductBridge
from amidst.workbench.scenes import load_local_camera

RESEARCH = "workbench-research-session-" + "a" * 24
SECOND = "workbench-second-session-" + "b" * 24
MANAGER = "workbench-manager-session-" + "c" * 24


@dataclass
class Access:
    role: str
    scene_ids: frozenset[str]


@pytest.fixture(scope="module")
def frozen_product(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    source = tmp_path_factory.mktemp("bridge-rgb-source")
    config = json.loads(DEFAULT_CONFIG.read_bytes())
    config["duration_s"] = 6.0
    config_path = source.parent / (source.name + "-config.json")
    config_path.write_text(json.dumps(config))
    build_run(source, run_id="workbench-bridge-rgb-v1", config_path=config_path)
    output = tmp_path_factory.mktemp("bridge-frozen-product")
    build_product(source, output, video_pool=tmp_path_factory.mktemp("bridge-video-pool"))
    return source, output


@pytest.fixture
def bridge(frozen_product: tuple[Path, Path], tmp_path: Path) -> Iterator[ProductBridge]:
    source, original = frozen_product
    output = tmp_path / "product"
    shutil.copytree(original, output)  # Frozen JSON/catalog only; no RGB or video copies.
    with load_product(output) as runtime:
        scene = load_local_camera(source)
        accesses = {
            RESEARCH: Access("research", frozenset({scene.scene_id})),
            SECOND: Access("research", frozenset({scene.scene_id})),
            MANAGER: Access("management", frozenset({scene.scene_id})),
        }
        def lookup(token: str) -> Access:
            if token not in accesses:
                raise ValueError("private /Users/local/source identity unavailable")
            return accesses[token]
        result = ProductBridge(runtime, scene, lookup)
        result.test_accesses = accesses  # type: ignore[attr-defined]
        result.test_output = output  # type: ignore[attr-defined]
        yield result


def payload(bridge: ProductBridge, token: str = RESEARCH, **fields: object) -> dict[str, Any]:
    return {"session_ref": token, "scene_id": bridge.scene.scene_id, **fields}


def call(bridge: ProductBridge, action: str, token: str = RESEARCH, **fields: object) -> Any:
    return bridge.call(action, payload(bridge, token, **fields))


def intent(bridge: ProductBridge) -> dict[str, object]:
    service = bridge.services["photos_plus_observations"]
    event = next(e for e in service.base.events.values() if e["candidates"])
    observation = next(o for o in service.base.observations.values()
                       if o["local_track_ref"] in event["local_track_refs"])
    return {"task": "TRACE", "camera_ref": observation["camera_refs"][0], "time_range": [0, 6],
            "seed_refs": [observation["observation_ref"]]}


def complete_case(bridge: ProductBridge) -> tuple[dict[str, Any], dict[str, Any]]:
    plan = call(bridge, "intent", intent=intent(bridge))["plan"]
    case = call(bridge, "execute", plan_ref=plan["plan_ref"])
    assert case["state"] == "COMPLETED"
    return plan, case


def test_context_uses_original_frozen_source_clock_camera_refs_without_private_locators(
    bridge: ProductBridge,
) -> None:
    context = call(bridge, "context")
    assert context["observation_mode"] == "photos_plus_observations"
    assert context["decision_stage"] == "RESULTS"
    assert context["available_modes"] == ["photos_only", "photos_plus_observations"]
    assert context["capabilities"]["videos"] and not context["capabilities"]["inference_execution"]
    assert context["source"]["source_rgb_rate_hz"] == 2.5
    assert context["source"]["camera_count"] == 4
    assert context["clock"]["unit"] == "SECONDS"
    assert context["coordinates"]["normalized_units"] == "METRES"
    assert context["policy"]["max_tool_calls"] == 32
    public = json.dumps(context)
    assert str(bridge.runtime.source) not in public
    assert str(bridge.runtime.video_pool) not in public
    assert "relative_path" not in public and "ground_truth" not in public
    assert context["product_context"] == bridge.services[
        "photos_plus_observations"].context().model_dump(mode="json")


@pytest.mark.parametrize("action,fields", [
    ("context", {}), ("tool", {"tool": "list_cameras"}),
    ("intent", {"intent": {"task": "BEHAVIOR"}}),
    ("plan", {"plan_ref": opaque_ref("plan", "missing")}),
    ("case", {"plan_ref": opaque_ref("plan", "missing")}), ("cases", {}),
    ("execute", {"plan_ref": opaque_ref("plan", "missing")}),
    ("report", {"plan_ref": opaque_ref("plan", "missing")}),
    ("videos", {}), ("timeline", {"timestamp": 0.0}),
    ("export_report", {"report_ref": opaque_ref("report", "missing")}),
    ("review", {"review": {"report_ref": opaque_ref("report", "missing"),
        "report_sha256": "a" * 64, "action": "PRESERVE_AMBIGUITY",
        "reason_code": "AMBIGUOUS_EVIDENCE"}}),
])
def test_management_is_denied_for_every_action(
    bridge: ProductBridge, action: str, fields: dict[str, object],
) -> None:
    with pytest.raises(BridgeDenied, match="^ROLE_DENIED$"):
        call(bridge, action, MANAGER, **fields)


def test_management_source_media_and_video_are_denied_before_bytes(bridge: ProductBridge) -> None:
    frame = next(iter(bridge.scene.service.frames))
    manifest = bridge.runtime.video_manifest
    assert manifest is not None
    with pytest.raises(BridgeDenied, match="^ROLE_DENIED$"):
        bridge.media(MANAGER, bridge.scene.scene_id, frame)
    with pytest.raises(BridgeDenied, match="^ROLE_DENIED$"):
        bridge.video(MANAGER, bridge.scene.scene_id, manifest.artifacts[0].video_ref)


def test_role_revocation_scene_revocation_and_product_token_never_authorize_workbench(
    bridge: ProductBridge,
) -> None:
    accesses = bridge.test_accesses  # type: ignore[attr-defined]
    context = call(bridge, "context")
    product_token = context["product_context"]["session_ref"]
    with pytest.raises(BridgeDenied, match="^SESSION_DENIED$"):
        call(bridge, "context", product_token)
    accesses[RESEARCH].role = "management"
    with pytest.raises(BridgeDenied, match="^ROLE_DENIED$"):
        call(bridge, "context")
    accesses[RESEARCH].role = "research"
    accesses[RESEARCH].scene_ids = frozenset()
    with pytest.raises(BridgeDenied, match="^SCENE_DENIED$"):
        call(bridge, "context")
    with pytest.raises(BridgeDenied, match="^SCENE_DENIED$"):
        bridge.call("context", payload(bridge, SECOND) | {"scene_id": "synthetic-lab"})


def test_modes_are_selected_server_side_and_cross_mode_plans_do_not_execute(
    bridge: ProductBridge,
) -> None:
    plan = call(bridge, "intent", intent=intent(bridge))["plan"]
    context = call(bridge, "context", observation_mode="photos_only")
    assert context["product_context"]["context"]["observation_mode"] == "photos_only"
    assert call(bridge, "context", SECOND)["observation_mode"] == "photos_plus_observations"
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        call(bridge, "execute", plan_ref=plan["plan_ref"])
    assert call(bridge, "cases")["items"] == []
    call(bridge, "context", observation_mode="photos_plus_observations")
    assert call(bridge, "plan", plan_ref=plan["plan_ref"]) == plan
    for extra in ({"role": "research"}, {"decision_stage": "RESULTS"},
                  {"mode": "photos_only"}, {"config_sha256": "f" * 64}):
        with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
            bridge.call("context", payload(bridge) | extra)
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        call(bridge, "plan", plan_ref=plan["plan_ref"], observation_mode="photos_only")


def test_durable_pause_stop_resume_restart_report_review_preserve_all_alternatives(
    bridge: ProductBridge,
) -> None:
    service = bridge.services["photos_plus_observations"]
    before = service.repository.verify_run(service.scope.run_ref)
    plan = call(bridge, "intent", intent=intent(bridge))["plan"]
    initial = call(bridge, "execute", plan_ref=plan["plan_ref"], max_new_calls=3)
    assert initial["state"] == "PAUSED" and len(initial["receipts"]) == 3
    assert call(bridge, "execute", plan_ref=plan["plan_ref"]) == initial
    stopped = call(bridge, "execute", plan_ref=plan["plan_ref"], stop=True)
    assert stopped["state"] == "STOPPED" and stopped["receipts"] == initial["receipts"]
    # New bridge on a reloaded repository restores the original product binding/ledger.
    with load_product(bridge.test_output) as runtime:  # type: ignore[attr-defined]
        restarted = ProductBridge(runtime, bridge.scene, bridge.session_lookup)
        assert call(restarted, "case", plan_ref=plan["plan_ref"]) == stopped
        case = call(restarted, "execute", plan_ref=plan["plan_ref"], resume=True)
        assert case["state"] == "COMPLETED" and case["receipts"][:3] == initial["receipts"]
        report = call(restarted, "report", plan_ref=plan["plan_ref"])
        assert report["all_alternative_refs"]
        assert report["identity_status"] == "UNRESOLVED_PROVISIONAL"
        assert report["workflow_complete"] and report["graph_complete"] is not None
        assert call(restarted, "report", plan_ref=plan["plan_ref"]) == report
        review = {"report_ref": report["report_ref"], "report_sha256": report["report_sha256"],
            "action": "SELECT_PRESENTATION", "reason_code": "DISPLAY_PREFERENCE",
            "alternative_ref": report["all_alternative_refs"][0]}
        receipt = call(restarted, "review", review=review)
        assert receipt["request"]["operator_ref"] == service.context().operator_ref
        assert receipt["canonical_records_modified"] is False
        assert receipt["confirmed_global_identity"] is False
        assert call(restarted, "review", review=review) == receipt
        exported = call(restarted, "export_report", report_ref=report["report_ref"])
        assert isinstance(exported, BinaryResponse) and exported.status == 200
        assert report["report_sha256"].encode() in exported.body
        assert str(runtime.source).encode() not in exported.body
        assert service.repository.verify_run(service.scope.run_ref) == before


def test_tools_keep_camera_anchor_paging_order_appearance_stitch_and_original_ids(
    bridge: ProductBridge,
) -> None:
    service = bridge.services["photos_plus_observations"]
    selected = intent(bridge)
    camera = selected["camera_ref"]
    query = {"camera_ref": camera, "time_range": [0, 6], "limit": 1}
    response = call(bridge, "tool", tool="query_observations", params=query)
    original = service.call("query_observations", {"session_ref": service.context().session_ref,
                                                   **query})
    assert response == original
    track = response["items"][0]["local_track_ref"]
    appearance = call(bridge, "tool", tool="search_person_appearance", params={
        "camera_ref": camera, "time_range": [0, 6], "query_track_ref": track, "top_k": 2})
    assert appearance["score_meaning"] == "HANDCRAFTED_SIMILARITY_NOT_IDENTITY_PROBABILITY"
    stitches = call(bridge, "tool", tool="get_stitch_hypotheses", params={"local_track_ref": track})
    assert stitches["provisional_only"]
    assert all("original_track_ids" not in item for item in stitches["items"])
    page = call(bridge, "tool", tool="propose_feasible_trajectories", params={
        "camera_ref": camera, "time_range": [0, 6], "seed_refs": selected["seed_refs"]})
    for summary in page["items"]:
        detail = call(bridge, "tool", tool="get_event_detail", params={
            "event_ref": summary["event_ref"]})
        assert detail == service.call("get_event_detail", {
            "session_ref": service.context().session_ref, "event_ref": summary["event_ref"]})
        assert detail["canonical_event_id"] == summary["canonical_event_id"]
    assert page["items"]


@pytest.mark.parametrize("window", [[0, 121], [3, 2], [True, 2], ["0", 2], [0, float("nan")]])
def test_investigation_and_tool_windows_are_bounded_before_core_calls(
    bridge: ProductBridge, window: list[object],
) -> None:
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        call(bridge, "intent", intent={**intent(bridge), "time_range": window})
    with pytest.raises(BridgeDenied, match="^FINITE_WINDOW_REQUIRED$"):
        call(bridge, "tool", tool="query_events", params={
            "camera_ref": intent(bridge)["camera_ref"], "time_range": window})


def test_step_session_operator_and_private_tool_injection_are_denied(bridge: ProductBridge) -> None:
    private = "/Users/private/source SECRET_GT_ID"
    with pytest.raises(BridgeDenied, match="^PRODUCT_SESSION_OVERRIDE_DENIED$"):
        call(bridge, "tool", tool="list_cameras", params={"session_ref": private})
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        call(bridge, "tool", tool=private)
    assert bridge.services["photos_plus_observations"].logs[-1]["tool"] == "UNKNOWN_TOOL"
    plan = call(bridge, "intent", intent=intent(bridge))["plan"]
    for fields in ({"steps": [{"tool": "shell", "path": private}]},
                   {"max_new_calls": True}, {"resume": "true"}, {"stop": 1}):
        with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
            call(bridge, "execute", plan_ref=plan["plan_ref"], **fields)
    review = {"report_ref": opaque_ref("report", "missing"), "report_sha256": "a" * 64,
              "action": "PRESERVE_AMBIGUITY", "reason_code": "AMBIGUOUS_EVIDENCE",
              "operator_ref": opaque_ref("operator", "forged")}
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        call(bridge, "review", review=review)
    assert private not in json.dumps(bridge.services["photos_plus_observations"].logs)


def test_constructor_rejects_different_run_source_frame_and_unfrozen_scene(
    bridge: ProductBridge,
) -> None:
    scene = bridge.scene.with_display_identity("alias", "alias", "same source")
    changed = scene.service.scope.model_copy(update={"run_id": "another-run"})
    original = scene.service.scope
    try:
        scene.service.scope = changed
        with pytest.raises(BridgeDenied, match="^PRODUCT_SCOPE_MISMATCH$"):
            ProductBridge(bridge.runtime, scene, bridge.session_lookup)
    finally:
        scene.service.scope = original
    guard = scene.service.guard
    try:
        scene.service.guard = SessionGuard(guard.binding)
        with pytest.raises(BridgeDenied, match="^PRODUCT_SCOPE_MISMATCH$"):
            ProductBridge(bridge.runtime, scene, bridge.session_lookup)
    finally:
        scene.service.guard = guard
    ref, frame = next(iter(scene.service.frames.items()))
    try:
        scene.service.frames[ref] = frame.model_copy(update={"sha256": "f" * 64})
        with pytest.raises(BridgeDenied, match="^PRODUCT_SCOPE_MISMATCH$"):
            ProductBridge(bridge.runtime, scene, bridge.session_lookup)
    finally:
        scene.service.frames[ref] = frame


def test_stage_or_freeze_change_denies_requests_even_after_original_context(
    bridge: ProductBridge,
) -> None:
    call(bridge, "context")
    service = bridge.services["photos_plus_observations"]
    previous = service.base.guard
    try:
        service.base.guard = SessionGuard(previous.binding)
        with pytest.raises(BridgeDenied, match="^PRODUCT_BINDING_DENIED$"):
            call(bridge, "cases")
    finally:
        service.base.guard = previous
    freeze = service.product_freeze_ref
    try:
        service.product_freeze_ref = opaque_ref("freeze", "changed")
        with pytest.raises(BridgeDenied, match="^PRODUCT_BINDING_DENIED$"):
            call(bridge, "context")
    finally:
        service.product_freeze_ref = freeze
    scene_guard = bridge.scene.service.guard
    scene_binding = scene_guard.binding
    try:
        scene_guard.binding = scene_binding.model_copy(update={"config_sha256": "f" * 64})
        assert scene_guard.stage == "RESULTS"
        with pytest.raises(BridgeDenied, match="^PRODUCT_BINDING_DENIED$"):
            call(bridge, "context")
    finally:
        scene_guard.binding = scene_binding


def test_video_metadata_ranges_hashes_scope_and_media_pixel_bytes(bridge: ProductBridge) -> None:
    videos = call(bridge, "videos")
    assert len(videos["items"]) == 4 and videos["presentation_video_rate_hz"] == 15
    assert videos["source_rgb_rate_hz"] == videos["cv_rate_hz"] == 2.5
    assert all("relative_path" not in item for item in videos["items"])
    first = videos["items"][0]
    selected = call(bridge, "videos", camera_refs=[first["camera_ref"]])
    assert selected["items"] == [first]
    with pytest.raises(BridgeDenied, match="^REFERENCE_DENIED$"):
        call(bridge, "videos", camera_refs=[opaque_ref("camera", "another-run")])
    whole = bridge.video(RESEARCH, bridge.scene.scene_id, first["video_ref"])
    assert whole.status == 200 and whole.mime_type == "video/mp4"
    assert hashlib.sha256(whole.body).hexdigest() == first["sha256"]
    ranged = bridge.video(RESEARCH, bridge.scene.scene_id, first["video_ref"], "bytes=2-11")
    assert ranged.status == 206 and ranged.body == whole.body[2:12]
    assert dict(ranged.headers)["Content-Range"] == f"bytes 2-11/{len(whole.body)}"
    invalid = bridge.video(RESEARCH, bridge.scene.scene_id, first["video_ref"], "bytes=-20")
    assert invalid.status == 416 and json.loads(invalid.body) == {"error": "RANGE_DENIED"}
    with pytest.raises(BridgeDenied, match="^REFERENCE_DENIED$"):
        bridge.video(RESEARCH, bridge.scene.scene_id, opaque_ref("video", "another-run"))
    with pytest.raises(BridgeDenied, match="^SCENE_DENIED$"):
        bridge.video(RESEARCH, "synthetic-lab", first["video_ref"])
    frame = next(iter(bridge.scene.service.frames.values()))
    image = bridge.media(RESEARCH, bridge.scene.scene_id, frame.media_ref)
    assert image.status == 200 and image.body.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(image.body).hexdigest() == frame.sha256
    with pytest.raises(BridgeDenied, match="^INVALID_OR_UNAVAILABLE$"):
        bridge.media(RESEARCH, bridge.scene.scene_id, "../../ground_truth.json")


def test_video_changes_are_denied_and_restoring_fixture_bytes_keeps_freeze(
    bridge: ProductBridge,
) -> None:
    manifest = bridge.runtime.video_manifest
    assert manifest is not None
    artifact = manifest.artifacts[0]
    file = bridge.runtime.video_pool / artifact.relative_path
    original = file.read_bytes()
    try:
        file.write_bytes(original + b"changed")
        with pytest.raises(BridgeDenied, match="^MEDIA_HASH_MISMATCH$"):
            bridge.video(RESEARCH, bridge.scene.scene_id, artifact.video_ref)
    finally:
        file.write_bytes(original)
    assert bridge.video(RESEARCH, bridge.scene.scene_id, artifact.video_ref).body == original


def test_unmaterialized_video_is_explicit_and_never_triggers_encoding(
    bridge: ProductBridge, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "no-video-product"
    build_product(bridge.runtime.source, output, video_pool=tmp_path / "pool", encode_video=False)
    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("bridge must not encode missing presentation media")
    monkeypatch.setattr(product_run, "encode_videos", forbidden)
    with load_product(output) as runtime:
        absent = ProductBridge(runtime, bridge.scene, bridge.session_lookup)
        assert not call(absent, "context")["capabilities"]["videos"]
        assert call(absent, "videos")["items"] == []
        with pytest.raises(BridgeDenied, match="^VIDEO_NOT_MATERIALIZED$"):
            absent.video(RESEARCH, bridge.scene.scene_id, opaque_ref("video", "missing"))


def test_timeline_preserves_original_source_samples_and_all_frozen_candidates(
    bridge: ProductBridge,
) -> None:
    plan, _ = complete_case(bridge)
    report = call(bridge, "report", plan_ref=plan["plan_ref"])
    refs = [e["record_ref"] for e in report["evidence"] if e["kind"] == "EVENT"]
    timeline = call(bridge, "timeline", timestamp=5.55, event_refs=refs)
    assert timeline["presentation_only"] and timeline["synchronization"] == "SOFT_SYNCHRONIZATION"
    assert timeline["markers"]
    for marker in timeline["markers"]:
        if marker["source_frame_ref"] is not None:
            frame = bridge.scene.service.frames[marker["source_frame_ref"]]
            assert marker["timestamp"] == frame.timestamp and not marker["interpolated"]
    with pytest.raises(BridgeDenied, match="^REFERENCE_DENIED$"):
        call(bridge, "timeline", timestamp=1.0, event_refs=[opaque_ref("event", "another-run")])


def test_gets_restart_and_planning_do_not_open_gt_or_rerun_any_producer(
    bridge: ProductBridge, monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_bytes = Path.read_bytes
    def no_truth(path: Path) -> bytes:
        assert "simulation" not in path.parts, "GT sidecars cannot enter the bridge"
        return read_bytes(path)
    def forbidden(*args: object, **kwargs: object) -> object:
        raise AssertionError("bridge called a producer or encoder")
    monkeypatch.setattr(Path, "read_bytes", no_truth)
    for name in ("produce_perception", "build_appearance_bundle", "build_stitch_bundle",
                 "encode_videos"):
        monkeypatch.setattr(product_run, name, forbidden)
    original_hashes = product_run.algorithm_hashes()
    restarted = ProductBridge(bridge.runtime, bridge.scene, bridge.session_lookup)
    plan, _ = complete_case(restarted)
    assert call(restarted, "report", plan_ref=plan["plan_ref"])["all_alternative_refs"]
    assert call(restarted, "videos")["items"]
    assert product_run.algorithm_hashes() == original_hashes
