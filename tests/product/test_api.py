"""Loopback transport over a real small frozen RGB product, without GT reads."""

from __future__ import annotations

import io
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
from amidst.product import api as product_api
from amidst.product.api import ProductApplication
from amidst.product.run import build_product, load_product


@pytest.fixture(scope="module")
def frozen_api_product(tmp_path_factory: pytest.TempPathFactory) -> Path:
    source = tmp_path_factory.mktemp("api-rgb-source")
    config = json.loads(DEFAULT_CONFIG.read_bytes())
    config["duration_s"] = 6.0
    config_path = source.parent / (source.name + "-config.json")
    config_path.write_text(json.dumps(config))
    build_run(source, run_id="api-rgb-fixture-v1", config_path=config_path)
    root = tmp_path_factory.mktemp("api-frozen-product")
    build_product(source, root, video_pool=tmp_path_factory.mktemp("api-video-pool"))
    return root


@pytest.fixture
def app(frozen_api_product: Path, tmp_path: Path) -> Iterator[ProductApplication]:
    root = tmp_path / "product"
    shutil.copytree(frozen_api_product, root)
    with load_product(root) as runtime:
        yield ProductApplication(runtime)


@dataclass
class Response:
    status: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body)


def request(
    app: ProductApplication, path: str, payload: object | None = None, *, method: str | None = None,
    query: str = "", host: str = "127.0.0.1:8020", origin: str | None = None,
    remote: str = "127.0.0.1", extra: dict[str, object] | None = None,
) -> Response:
    encoded = b"" if payload is None else json.dumps(payload).encode()
    environ: dict[str, object] = {
        "REQUEST_METHOD": method or ("GET" if payload is None else "POST"),
        "PATH_INFO": path, "QUERY_STRING": query, "HTTP_HOST": host, "REMOTE_ADDR": remote,
        "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(encoded)),
        "wsgi.input": io.BytesIO(encoded),
    }
    if origin is not None:
        environ["HTTP_ORIGIN"] = origin
    environ.update(extra or {})
    received: list[tuple[str, list[tuple[str, str]]]] = []
    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        received.append((status, headers))
    body = b"".join(app(environ, start_response))
    assert len(received) == 1
    status, headers = received[0]
    response = Response(int(status.split()[0]), dict(headers), body)
    assert int(response.headers["Content-Length"]) == len(body)
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "connect-src 'self'" in response.headers["Content-Security-Policy"]
    return response


def session_payload(app: ProductApplication, index: int = 0) -> dict[str, str]:
    return {"session_ref": app.runtime.services[index].context().session_ref}


def intent_payload(app: ProductApplication) -> dict[str, object]:
    service = app.runtime.services[0]
    event = next(e for e in service.base.events.values() if e["candidates"])
    seed = next(o for o in service.base.observations.values()
                if o["local_track_ref"] in event["local_track_refs"])
    return session_payload(app) | {"intent": {
        "text": "追查目標", "camera_ref": seed["camera_refs"][0], "time_range": [0, 6],
        "seed_refs": [seed["observation_ref"]],
    }}


def test_context_contract_static_allowlist_and_no_private_source_paths(
    app: ProductApplication,
) -> None:
    contexts = request(app, "/product/v1/contexts")
    assert contexts.status == 200
    values = contexts.json()["items"]
    assert len(values) == 2
    assert {v["context"]["observation_mode"] for v in values} == {
        "photos_only", "photos_plus_observations"}
    assert all(v["role"] == "TRUSTED_LOCAL_OPERATOR" and v["operator_ref"] for v in values)
    contract = request(app, "/product/v1/contract")
    assert contract.status == 200
    assert "search_person_appearance" in contract.json()["tools"]
    assert contract.json()["execute_schema"]["additionalProperties"] is False
    assert contract.json()["response_schemas"]["get_observation_detail"][
        "additionalProperties"] is False
    for path, mime in (("/", "text/html"), ("/app.mjs", "text/javascript"),
                       ("/style.css", "text/css"), ("/timeline.mjs", "text/javascript"),
                       ("/vendor/three.module.js", "text/javascript"),
                       ("/vendor/three.core.js", "text/javascript")):
        static = request(app, path)
        assert static.status == 200 and static.headers["Content-Type"].startswith(mime)
    for path in ("/product_manifest.json", "/package.json", "/../catalog.sqlite",
                 "/vendor/../product_manifest.json", "/simulation/export/ground_truth.json"):
        denied = request(app, path)
        assert denied.status == 404 and denied.json() == {"error": "ROUTE_UNAVAILABLE"}
    all_public = contexts.body + contract.body
    for locator in (app.runtime.source, app.runtime.video_pool):
        assert str(locator).encode() not in all_public
    assert b"simulation_export_path" not in all_public and b"OPENAI_API_KEY" not in all_public


@pytest.mark.parametrize("host", ["attacker.example", "127.0.0.1.attacker.example", "0.0.0.0:8020",
                                 "127.0.0.1:0", "localhost:65536", "localhost:8020@evil"])
def test_host_dns_rebinding_is_denied_even_with_matching_origin(
    app: ProductApplication, host: str,
) -> None:
    response = request(app, "/product/v1/contexts", host=host, origin="http://" + host)
    assert response.status == 403 and response.json() == {"error": "LOCAL_TRANSPORT_REQUIRED"}


def test_origin_and_remote_are_restricted_to_local_transport(app: ProductApplication) -> None:
    for origin in ("https://attacker.example", "null", "http://localhost:8020"):
        response = request(app, "/product/v1/contexts", origin=origin)
        assert response.status == 403 and response.json() == {"error": "ORIGIN_DENIED"}
    for remote in ("192.0.2.42", "127.0.0.2", "127.0.0.1.attacker"):
        response = request(app, "/product/v1/contexts", remote=remote)
        assert response.status == 403 and response.json() == {"error": "LOCAL_TRANSPORT_REQUIRED"}
    assert request(app, "/product/v1/contexts", host="localhost:8020",
                   origin="http://localhost:8020").status == 200
    assert request(app, "/product/v1/contexts", origin="http://127.0.0.1:8020").status == 200


def test_serve_explicitly_binds_loopback_without_access_log_payloads(
    app: ProductApplication, monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[tuple[str, int, object]] = []
    class Server:
        def __enter__(self) -> Server:
            return self
        def __exit__(self, *args: object) -> None:
            pass
        def serve_forever(self) -> None:
            raise RuntimeError("finish fake server")
    def local_server(host: str, port: int, application: object, **kwargs: object) -> Server:
        called.append((host, port, kwargs["handler_class"]))
        assert isinstance(application, ProductApplication)
        return Server()
    monkeypatch.setattr(product_api, "make_server", local_server)
    with pytest.raises(RuntimeError, match="finish fake server"):
        product_api.serve(app.runtime, port=8023)
    assert called == [("127.0.0.1", 8023, product_api.QuietHandler)]


def test_durable_plan_case_report_review_and_html_export_roundtrip(app: ProductApplication) -> None:
    compiled = request(app, "/product/v1/intent", intent_payload(app))
    assert compiled.status == 200 and compiled.json()["status"] == "READY"
    plan = compiled.json()["plan"]
    plan_payload = session_payload(app) | {"plan_ref": plan["plan_ref"]}
    assert request(app, "/product/v1/plan", plan_payload).json() == plan
    assert request(app, "/product/v1/case", plan_payload).json() == {"error": "CASE_UNAVAILABLE"}
    history = request(app, "/product/v1/cases", session_payload(app))
    assert history.status == 200 and history.json()["items"] == [
        {"plan_ref": plan["plan_ref"], "task": "TRACE", "state": "READY"}]
    paused = request(app, "/product/v1/execute", plan_payload | {"max_new_calls": 3})
    assert paused.status == 200 and paused.json()["state"] == "PAUSED"
    restarted = ProductApplication(app.runtime)
    assert request(restarted, "/product/v1/case", plan_payload).json() == paused.json()
    stopped = request(restarted, "/product/v1/execute", plan_payload | {"stop": True})
    assert stopped.status == 200 and stopped.json()["state"] == "STOPPED"
    case = request(restarted, "/product/v1/execute", plan_payload | {
        "resume": True, "max_new_calls": 6}).json()
    while case["state"] == "PAUSED":
        case = request(restarted, "/product/v1/execute", plan_payload | {
            "resume": True, "max_new_calls": 6}).json()
    assert case["state"] == "COMPLETED"
    report_response = request(restarted, "/product/v1/report", plan_payload)
    assert report_response.status == 200
    report = report_response.json()
    assert report["all_alternative_refs"] and report["identity_status"] == "UNRESOLVED_PROVISIONAL"
    review = session_payload(app) | {"review": {
        "report_ref": report["report_ref"], "report_sha256": report["report_sha256"],
        "operator_ref": app.runtime.services[0].context().operator_ref,
        "action": "PRESERVE_AMBIGUITY", "reason_code": "AMBIGUOUS_EVIDENCE",
    }}
    reviewed = request(restarted, "/product/v1/review", review)
    assert reviewed.status == 200 and reviewed.json()["canonical_records_modified"] is False
    assert request(restarted, "/product/v1/review", review).json() == reviewed.json()
    forged = json.loads(json.dumps(review))
    forged["review"]["operator_ref"] = opaque_ref("operator", "forged")
    rejected = request(restarted, "/product/v1/review", forged)
    assert rejected.status == 400 and rejected.json() == {"error": "INVALID_OR_UNAVAILABLE"}
    export = request(restarted, "/product/v1/export-report", session_payload(app) | {
        "report_ref": report["report_ref"]})
    assert export.status == 200 and export.headers["Content-Type"] == "text/html; charset=utf-8"
    assert report["report_sha256"].encode() in export.body
    assert str(app.runtime.source).encode() not in export.body
    other_mode = session_payload(app, 1) | {"plan_ref": plan["plan_ref"]}
    assert request(app, "/product/v1/plan", other_mode).status == 400
    assert request(app, "/product/v1/cases", session_payload(app, 1)).json()["items"] == []
    assert request(app, "/product/v1/export-report", session_payload(app, 1) | {
        "report_ref": report["report_ref"]}).status == 403


def test_strict_envelopes_unsupported_intent_and_errors_do_not_echo_payload(
    app: ProductApplication,
) -> None:
    private = "/Users/private/raw SECRET_GT_42"
    payload = intent_payload(app)
    unknown = request(app, "/product/v1/tools/" + private, session_payload(app))
    assert unknown.status == 403 and unknown.json() == {"error": "TOOL_DENIED"}
    assert app.runtime.services[0].logs[-1] == {"tool": "UNKNOWN_TOOL", "status": "TOOL_DENIED"}
    malicious = payload | {"steps": [{"tool": "shell", "path": private}]}
    assert request(app, "/product/v1/intent", malicious).json() == {
        "error": "INVALID_OR_UNAVAILABLE"}
    unsupported = payload | {"intent": dict(payload["intent"]) | {"text": private}}
    response = request(app, "/product/v1/intent", unsupported)
    assert response.status == 200 and response.json()["status"] == "NEEDS_INPUT"
    assert private.encode() not in response.body
    plan = request(app, "/product/v1/intent", payload).json()["plan"]
    for update in ({"stop": "false"}, {"resume": 1}, {"max_new_calls": True},
                   {"max_new_calls": 0}, {"max_new_calls": 1.0}, {"steps": []},
                   {"decision_stage": "RESULTS"}, {"config_sha256": "f" * 64}):
        rejected = request(app, "/product/v1/execute", session_payload(app) | {
            "plan_ref": plan["plan_ref"]} | update)
        assert rejected.status == 400 and rejected.json() == {"error": "INVALID_OR_UNAVAILABLE"}
    for invalid in ([], None, {"session_ref": "session-" + "f" * 24}):
        rejected = request(app, "/product/v1/tools/list_cameras", invalid, method="POST")
        assert rejected.status == 403 and set(rejected.json()) == {"error"}
    for extra in ({"CONTENT_TYPE": "text/plain"}, {"CONTENT_LENGTH": "65537"},
                  {"CONTENT_LENGTH": "-1"}, {"CONTENT_LENGTH": "invalid"},
                  {"QUERY_STRING": "source=" + private}):
        rejected = request(app, "/product/v1/intent", payload, extra=extra)
        assert rejected.status in (400, 403) and set(rejected.json()) == {"error"}
        assert private.encode() not in rejected.body
    assert private not in json.dumps(app.runtime.services[0].logs)


def test_results_view_canonical_timeline_and_source_frame_offsets(app: ProductApplication) -> None:
    service = app.runtime.services[0]
    original = json.dumps(service.base.events, sort_keys=True)
    scene = request(app, "/product/v1/view/scene", session_payload(app))
    assert scene.status == 200 and scene.json()["units"] == "METRES"
    assert scene.json()["coordinate_system"] == "BLENDER_RIGHT_HANDED_Z_UP"
    assert "camera_matrices" not in scene.json()
    videos = request(app, "/product/v1/view/videos", session_payload(app))
    assert videos.status == 200 and len(videos.json()["items"]) == 4
    assert videos.json()["presentation_only"] is True
    assert videos.json()["source_rgb_rate_hz"] == videos.json()["cv_rate_hz"] == 2.5
    assert videos.json()["presentation_video_rate_hz"] == 15
    assert all("relative_path" not in v for v in videos.json()["items"])
    timeline = request(app, "/product/v1/view/timeline", session_payload(app) | {"timestamp": 5.55})
    assert timeline.status == 200
    body = timeline.json()
    assert body["presentation_only"] and body["synchronization"] == "SOFT_SYNCHRONIZATION"
    assert body["markers"]
    for frame in body["frames"]:
        assert frame["status"] == "AVAILABLE"
        assert frame["offset_seconds"] == pytest.approx(frame["frame_timestamp"] - 5.55)
    for marker in body["markers"]:
        if marker["evidence_state"] == "PROJECTED" and marker["source_frame_ref"] is not None:
            registered = service.base.frames[marker["source_frame_ref"]]
            assert marker["timestamp"] == registered.timestamp
            assert not marker["interpolated"]
            assert marker["sample_offset_seconds"] == pytest.approx(marker["timestamp"] - 5.55)
    missing = request(app, "/product/v1/view/timeline", session_payload(app) | {"timestamp": 100.0})
    assert missing.status == 200 and missing.json()["markers"] == []
    assert all(f["status"] == "NO_FRAME_WITHIN_TOLERANCE" and f["media_ref"] is None
               for f in missing.json()["frames"])
    denied = request(app, "/product/v1/view/timeline", session_payload(app) | {
        "timestamp": 0.0, "event_refs": [opaque_ref("event", "other-run")]})
    assert denied.status == 403 and denied.json() == {"error": "REFERENCE_DENIED"}
    assert json.dumps(service.base.events, sort_keys=True) == original
    for response in (scene, videos, timeline, missing, denied):
        assert str(app.runtime.source).encode() not in response.body
        assert str(app.runtime.video_pool).encode() not in response.body


@pytest.mark.parametrize("mode_index", [0, 1])
def test_input_stage_cannot_use_views_or_hidden_result_tools(
    app: ProductApplication, mode_index: int,
) -> None:
    service = app.runtime.services[mode_index]
    service.base.guard = SessionGuard(service.base.guard.binding)
    input_app = ProductApplication(app.runtime)
    session = session_payload(input_app, mode_index)
    for path, params in (
        ("view/scene", {}), ("view/videos", {}), ("view/timeline", {"timestamp": 0.0}),
        ("cases", {}), ("plan", {"plan_ref": opaque_ref("plan", "unavailable")}),
        ("tools/query_events", {"camera_ref": next(iter(service.base.cameras)),
                                 "time_range": [0, 6]}),
        ("tools/query_reachable_cameras", {"camera_ref": next(iter(service.base.cameras))}),
        ("tools/search_person_appearance", {
            "camera_ref": next(iter(service.base.cameras)), "time_range": [0, 6],
            "query_track_ref": service.descriptors.track_descriptors[0].track_ref}),
    ):
        denied = request(input_app, "/product/v1/" + path, session | params)
        assert denied.status == 403 and denied.json() == {"error": "STAGE_DENIED"}
    pixels = request(input_app, "/product/v1/tools/query_observations", session | {
        "camera_ref": next(iter(service.base.cameras)), "time_range": [0, 6]})
    if mode_index == 0:
        assert pixels.status == 403 and pixels.json() == {"error": "STAGE_DENIED"}
    else:
        assert pixels.status == 200
        assert all("region_ids" not in item and "projected_path" not in item
                   for item in pixels.json()["items"])
    video = app.runtime.video_manifest
    assert video is not None
    denied = request(input_app, "/product/v1/video/" + video.artifacts[0].video_ref,
                     query="session_ref=" + session["session_ref"])
    assert denied.status == 403 and denied.json() == {"error": "STAGE_DENIED"}
    frame_ref = next(iter(service.base.frames))
    image = request(input_app, "/product/v1/media/" + frame_ref,
                    query="session_ref=" + session["session_ref"])
    assert image.status == 200 and image.headers["Content-Type"] == "image/png"


def test_media_refs_session_queries_and_unknown_source_paths_are_guarded(
    app: ProductApplication,
) -> None:
    service = app.runtime.services[0]
    frame = next(iter(service.base.frames.values()))
    endpoint = "/product/v1/media/" + frame.media_ref
    query = "session_ref=" + service.context().session_ref
    media = request(app, endpoint, query=query)
    assert media.status == 200 and media.body.startswith(b"\x89PNG\r\n\x1a\n")
    assert media.body == service.base.store.media_bytes(service.base.scope, frame.media_ref)
    for wrong in ("", query + "&source=/Users/private", query + "&" + query,
                  "session_ref=", "session_ref=session-" + "f" * 24):
        denied = request(app, endpoint, query=wrong)
        assert denied.status == 403 and set(denied.json()) == {"error"}
    for ref in (opaque_ref("media", "other-run"), "../../manifest.json", "ground_truth.json"):
        denied = request(app, "/product/v1/media/" + ref, query=query)
        assert denied.status == 403 and set(denied.json()) == {"error"}
        assert b"/Users/" not in denied.body


def test_video_ranges_are_exact_and_unknown_hash_or_scope_is_denied(
    app: ProductApplication,
) -> None:
    video = app.runtime.video_manifest
    assert video is not None
    artifact = video.artifacts[0]
    endpoint = "/product/v1/video/" + artifact.video_ref
    query = "session_ref=" + app.runtime.services[0].context().session_ref
    whole = request(app, endpoint, query=query)
    assert whole.status == 200 and len(whole.body) == artifact.byte_count
    assert whole.headers["Accept-Ranges"] == "bytes"
    part = request(app, endpoint, query=query, extra={"HTTP_RANGE": "bytes=2-15"})
    assert part.status == 206 and part.body == whole.body[2:16]
    assert part.headers["Content-Range"] == f"bytes 2-15/{artifact.byte_count}"
    tail = request(app, endpoint, query=query, extra={"HTTP_RANGE": "bytes=16-"})
    assert tail.status == 206 and tail.body == whole.body[16:]
    for value in ("bytes=-10", "bytes=9-2", "bytes=0-99999999", "bytes=0-1,4-5", "items=0-5"):
        rejected = request(app, endpoint, query=query, extra={"HTTP_RANGE": value})
        assert rejected.status == 416 and rejected.json() == {"error": "RANGE_DENIED"}
    for ref in (opaque_ref("video", "other-run"), "../../package.json"):
        rejected = request(app, "/product/v1/video/" + ref, query=query)
        assert rejected.status == 403 and rejected.json() == {"error": "REFERENCE_DENIED"}
    destination = app.runtime.video_pool / artifact.relative_path
    original = destination.read_bytes()
    try:
        destination.write_bytes(original + b"changed")
        rejected = request(app, endpoint, query=query)
        assert rejected.status == 403 and rejected.json() == {"error": "MEDIA_HASH_MISMATCH"}
    finally:
        destination.write_bytes(original)


def test_http_transport_never_reads_the_gt_sidecar(
    app: ProductApplication, monkeypatch: pytest.MonkeyPatch,
) -> None:
    read_bytes = Path.read_bytes
    def no_truth(path: Path) -> bytes:
        assert "simulation" not in path.parts, "API must not open GT"
        return read_bytes(path)
    monkeypatch.setattr(Path, "read_bytes", no_truth)
    reloaded = ProductApplication(app.runtime)
    for path in ("/product/v1/contexts", "/product/v1/contract"):
        assert request(reloaded, path).status == 200
    assert request(reloaded, "/product/v1/view/scene", session_payload(app)).status == 200
    assert request(reloaded, "/product/v1/view/timeline", session_payload(app) | {
        "timestamp": 4.8}).status == 200
