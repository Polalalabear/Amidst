"""Actual frozen product HTTP composition, optional resources and fixed gallery routes."""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import pytest
from PIL import Image

from amidst.engineering.local_pilot import build_run
from amidst.engineering.research_scene import DEFAULT_CONFIG
from amidst.product.run import build_product, load_product
from amidst.workbench.presentation_gallery import Gallery
from amidst.workbench.product_bridge import ProductBridge
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scenes import load_local_camera
from amidst.workbench.service import Application, Workbench, configure_extensions


@dataclass
class Composition:
    app: Application
    workbench: Workbench
    research: str
    manager: str
    repo: Path


@pytest.fixture(scope="module")
def frozen(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    source = tmp_path_factory.mktemp("application-rgb-source")
    config = json.loads(DEFAULT_CONFIG.read_bytes())
    config["duration_s"] = 6.0
    config_path = source.parent / (source.name + "-config.json")
    config_path.write_text(json.dumps(config))
    build_run(source, run_id="workbench-application-rgb-v1", config_path=config_path)
    output = tmp_path_factory.mktemp("application-frozen-product")
    build_product(source, output, video_pool=tmp_path_factory.mktemp("application-video-pool"))
    return source, output


@pytest.fixture
def composition(frozen: tuple[Path, Path], tmp_path: Path) -> Iterator[Composition]:
    source, output = frozen
    repo = tmp_path / "repo"
    product = repo / "data/product/local_run/operator_v2"
    shutil.copytree(output, product)  # Immutable JSON/SQLite; RGB and MP4 stay at frozen locators.
    scene = load_local_camera(source)
    keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(repo / "reviews.sqlite", {
        scene.scene_id: {key: scene.snapshot()[key] for key in keys},
    })
    gallery_png = repo / "data/engineering/local_run/simulation_v2/presentation/inference.png"
    gallery_png.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (2, 2), (20, 70, 110)).save(gallery_png)
    frontend = repo / "frontend/workbench"
    frontend.mkdir(parents=True)
    for name in ("investigation", "workflow", "gallery"):
        (frontend / (name + ".mjs")).write_text("export const localOnly=true;")
    workbench = Workbench({scene.scene_id: scene}, reviews, gallery=Gallery(repo))
    research = workbench.session({"role": "research"})["session_ref"]
    manager = workbench.session({"role": "management"})["session_ref"]
    with load_product(product) as runtime:
        workbench.product_bridge = ProductBridge(runtime, scene, workbench._session)
        yield Composition(Application(workbench, repo), workbench, research, manager, repo)


def http(
    item: Composition, path: str, fields: dict[str, Any] | None = None, *,
    method: str = "POST", token: str | None = None, range_header: str | None = None,
    query: str = "", origin: str | None = None, host: str = "127.0.0.1:8016",
) -> tuple[str, dict[str, str], bytes]:
    data = json.dumps({"session_ref": item.research if token is None else token,
                       **(fields or {})}).encode()
    environ: dict[str, Any] = {
        "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
        "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(data)),
        "wsgi.input": BytesIO(data), "HTTP_HOST": host, "SERVER_PORT": "8016",
    }
    if range_header is not None:
        environ["HTTP_RANGE"] = range_header
    if origin is not None:
        environ["HTTP_ORIGIN"] = origin
    response: dict[str, Any] = {}

    def start(status: str, headers: list[tuple[str, str]]) -> None:
        response.update(status=status, headers=dict(headers))

    body = b"".join(item.app(environ, start))
    assert int(response["headers"]["Content-Length"]) == len(body)
    assert response["headers"]["Cache-Control"] == "no-store"
    assert str(item.repo).encode() not in body
    return response["status"], response["headers"], body


def product(item: Composition, action: str, **fields: Any) -> Any:
    status, _, body = http(item, "/api/product_" + action,
                           {"scene_id": "local-camera", **fields})
    assert status == "200 OK", body
    return json.loads(body)


def test_context_modes_typed_tools_and_existing_scene_remain_available(
    composition: Composition,
) -> None:
    context = product(composition, "context")
    assert context["decision_stage"] == "RESULTS"
    assert context["source"]["camera_count"] == 4
    assert "product_context" in context and "relative_path" not in json.dumps(context)
    assert product(composition, "context", observation_mode="photos_only")[
        "observation_mode"] == "photos_only"
    cameras = product(composition, "tool", tool="list_cameras", params={})
    assert len(cameras["items"]) == 4
    status, _, body = http(composition, "/api/scene", {"scene_id": "local-camera"})
    assert status == "200 OK" and json.loads(body)["snapshot"]["scene_id"] == "local-camera"
    bootstrap = http(composition, "/api/bootstrap", method="GET")
    assert json.loads(bootstrap[2])["scenes"][0]["product_available"] is True
    logs = json.loads(http(composition, "/api/logs", {"scene_id": "local-camera"})[2])["items"]
    assert any(row["action"] == "product_tool" and row["status"] == "OK" for row in logs)
    assert all(set(row) <= {"action", "scene_id", "status", "duration_ms"} for row in logs)
    assert composition.research not in json.dumps(logs)


def test_case_report_export_and_review_are_original_append_only_product_workflow(
    composition: Composition,
) -> None:
    bridge = composition.workbench.product_bridge
    assert bridge is not None
    base = bridge.services["photos_plus_observations"].base
    event = next(e for e in base.events.values() if e["candidates"])
    observation = next(o for o in base.observations.values()
                       if o["local_track_ref"] in event["local_track_refs"])
    before = {mode: s.repository.verify_run(s.scope.run_ref)
              for mode, s in bridge.services.items()}
    plan = product(composition, "intent", intent={"task": "TRACE",
        "camera_ref": observation["camera_refs"][0], "time_range": [0, 6],
        "seed_refs": [observation["observation_ref"]]})["plan"]
    assert product(composition, "plan", plan_ref=plan["plan_ref"]) == plan
    case = product(composition, "execute", plan_ref=plan["plan_ref"])
    assert case["state"] == "COMPLETED"
    assert product(composition, "case", plan_ref=plan["plan_ref"]) == case
    assert product(composition, "cases")["items"][0]["plan_ref"] == plan["plan_ref"]
    report = product(composition, "report", plan_ref=plan["plan_ref"])
    status, headers, body = http(composition, "/api/product_export_report", {
        "scene_id": "local-camera", "report_ref": report["report_ref"],
    })
    assert status == "200 OK" and headers["Content-Type"] == "text/html; charset=utf-8"
    assert b"<!doctype html>" in body.lower()
    assert report["binding"]["run_id"].encode() in body
    assert report["identity_status"].encode() in body
    reviewed = product(composition, "review", review={
        "report_ref": report["report_ref"], "report_sha256": report["report_sha256"],
        "action": "PRESERVE_AMBIGUITY", "reason_code": "AMBIGUOUS_EVIDENCE",
    })
    assert reviewed["request"]["action"] == "PRESERVE_AMBIGUITY"
    assert reviewed["canonical_records_modified"] is False
    assert before == {mode: s.repository.verify_run(s.scope.run_ref)
                      for mode, s in bridge.services.items()}


def test_media_and_mp4_ranges_preserve_mime_status_and_exact_bytes(
    composition: Composition,
) -> None:
    context = product(composition, "context")
    bridge = composition.workbench.product_bridge
    assert bridge is not None
    frame = next(iter(bridge.scene.service.frames))
    query = {"session_ref": composition.research, "scene_id": "local-camera", "ref": frame}
    status, headers, body = http(composition, "/api/product_media", method="GET",
                                 query=urlencode(query))
    assert status == "200 OK" and headers["Content-Type"] == "image/png"
    assert body.startswith(b"\x89PNG")
    video = product(composition, "videos")["items"][0]
    query["ref"] = video["video_ref"]
    full = http(composition, "/api/product_video", method="GET", query=urlencode(query))
    ranged = http(composition, "/api/product_video", method="GET", query=urlencode(query),
                   range_header="bytes=0-63")
    assert full[0] == "200 OK" and full[1]["Content-Type"] == "video/mp4"
    assert len(full[2]) == video["byte_count"]
    assert ranged[0] == "206 Partial Content" and ranged[2] == full[2][:64]
    assert ranged[1]["Content-Range"] == f"bytes 0-63/{len(full[2])}"
    invalid = http(composition, "/api/product_video", method="GET", query=urlencode(query),
                    range_header="bytes=999999999999-")
    assert invalid[0].startswith("416 ") and invalid[1]["Content-Type"] == "application/json"
    assert invalid[1]["Content-Range"] == f"bytes */{len(full[2])}"
    timeline = product(composition, "timeline", timestamp=0.0, event_refs=[])
    assert timeline["run_ref"] == context["product_context"]["run_ref"]


@pytest.mark.parametrize("action", [
    "context", "tool", "intent", "execute", "plan", "case", "cases", "report", "review",
    "videos", "timeline", "export_report",
])
def test_all_product_actions_reject_management_before_any_product_method(
    composition: Composition, action: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = composition.workbench.product_bridge
    assert bridge is not None

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("product must not be entered by management")

    monkeypatch.setattr(bridge, "call", never)
    status, _, body = http(composition, "/api/product_" + action,
                           {"scene_id": "local-camera"}, token=composition.manager)
    assert status == "403 Forbidden" and json.loads(body)["error"]["code"] == "ROLE_DENIED"


def test_product_wrong_scope_stale_mode_extra_keys_and_get_queries_are_closed(
    composition: Composition,
) -> None:
    for fields in ({"scene_id": "other-run"},
                   {"scene_id": "local-camera", "decision_stage": "INPUT"},
                   {"scene_id": "local-camera", "observation_mode": "GT"}):
        status, _, body = http(composition, "/api/product_context", fields)
        assert status.startswith(("400 ", "403 "))
        assert "private" not in body.decode()
    query = urlencode({"session_ref": composition.research, "scene_id": "local-camera",
                       "ref": "../ground_truth.json", "path": "/private/truth"})
    assert http(composition, "/api/product_media", method="GET", query=query)[0] == (
        "400 Bad Request")
    duplicate = f"session_ref={composition.research}&scene_id=local-camera&ref=a&ref=b"
    assert http(composition, "/api/product_video", method="GET", query=duplicate)[0] == (
        "400 Bad Request")
    assert http(composition, "/api/product_shell", {"scene_id": "local-camera"})[0] == (
        "403 Forbidden")
    assert http(composition, "/api/product_context", {"scene_id": "local-camera"},
                origin="http://outside.invalid")[0] == "403 Forbidden"


def test_fixed_main_extension_wiring_loads_product_without_producer_or_gt(
    composition: Composition, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import amidst.product.run as product_run
    original = composition.workbench.product_bridge
    assert original is not None
    original_open = Path.open

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("a loader must not re-run perception")

    def no_truth(path: Path, *args: Any, **kwargs: Any) -> Any:
        assert path.name != "ground_truth.json", "a workbench must not open GT"
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(product_run, "produce_perception", never)
    monkeypatch.setattr(Path, "open", no_truth)
    try:
        configure_extensions(composition.workbench, composition.repo, canonical_root=None)
        assert composition.workbench.product_bridge is not None
        assert product(composition, "context")["source"]["run_id"] == (
            "workbench-application-rgb-v1")
        assert composition.workbench.gallery is not None
    finally:
        attached = composition.workbench.product_bridge
        if attached is not None and attached is not original:
            attached.runtime.close()
        composition.workbench.product_bridge = original


@pytest.mark.parametrize("path", ["/api/product_media", "/api/product_video"])
def test_binary_product_resources_deny_management_before_any_bytes(
    composition: Composition, path: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = composition.workbench.product_bridge
    assert bridge is not None

    def never(*args: object, **kwargs: object) -> None:
        raise AssertionError("a manager must not enter the binary product provider")

    monkeypatch.setattr(bridge, "media", never)
    monkeypatch.setattr(bridge, "video", never)
    query = urlencode({"session_ref": composition.manager, "scene_id": "local-camera",
                       "ref": "opaque-unavailable"})
    status, _, body = http(composition, path, method="GET", query=query)
    assert status == "403 Forbidden" and json.loads(body)["error"]["code"] == "ROLE_DENIED"


def test_optional_product_unavailable_and_startup_failure_keep_existing_scene_usable(
    composition: Composition, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import amidst.workbench.service as service
    composition.workbench.product_bridge = None
    assert product(composition, "context")["reason"] == "NO_CERTIFIED_PRODUCT"
    assert http(composition, "/api/product_cases", {"scene_id": "local-camera"})[0] == (
        "503 Service Unavailable")

    def invalid(_: Path) -> None:
        raise ValueError("private /Users/source/frozen mismatch")

    monkeypatch.setattr(service, "load_product", invalid)
    configure_extensions(composition.workbench, composition.repo, canonical_root=None)
    assert composition.workbench.product_bridge is None
    assert http(composition, "/api/scene", {"scene_id": "local-camera"})[0] == "200 OK"
    assert json.loads(http(composition, "/api/bootstrap", method="GET")[2])["scenes"][0][
        "product_available"] is False


def test_gallery_routes_are_research_only_fixed_family_and_hash_bound_pngs(
    composition: Composition,
) -> None:
    status, _, body = http(composition, "/api/gallery_list")
    assert status == "200 OK"
    listing = json.loads(body)
    assert len(listing["items"]) == 15 and listing["complete"] is True
    assert any(item["family_id"] == "research-accuracy-v2" for item in listing["items"])
    ref = listing["items"][0]["family_ref"]
    detail = http(composition, "/api/gallery_detail", {"family_ref": ref})
    family = json.loads(detail[2])["family"]
    assert family["normal_presentation_allowed"] is False
    image = family["images"][0]
    query = urlencode({"session_ref": composition.research, "ref": image["media_ref"]})
    media = http(composition, "/api/gallery_media", method="GET", query=query)
    assert media[0] == "200 OK" and media[1]["Content-Type"] == "image/png"
    for action, fields in (("gallery_list", {}), ("gallery_detail", {"family_ref": ref})):
        assert http(composition, "/api/" + action, fields, token=composition.manager)[0] == (
            "403 Forbidden")
    denied = urlencode({"session_ref": composition.manager, "ref": image["media_ref"]})
    assert http(composition, "/api/gallery_media", method="GET", query=denied)[0] == "403 Forbidden"
    for invalid in ("gallery-family:" + "f" * 24, "/private/archive.json"):
        assert http(composition, "/api/gallery_detail", {"family_ref": invalid})[0].startswith(
            ("400 ", "403 "))
    png = composition.repo / "data/engineering/local_run/simulation_v2/presentation/inference.png"
    png.write_bytes(b"tampered")
    changed = http(composition, "/api/gallery_media", method="GET", query=query)
    assert changed[0] == "403 Forbidden"
    assert json.loads(changed[2])["error"]["code"] == "GALLERY_MEDIA_CONTENT_CHANGED"


@pytest.mark.parametrize("path", ["/investigation.mjs", "/workflow.mjs", "/gallery.mjs"])
def test_fixed_local_static_modules_and_host_limit(composition: Composition, path: str) -> None:
    status, headers, body = http(composition, path, method="GET")
    assert status == "200 OK" and headers["Content-Type"] == "text/javascript"
    assert body == b"export const localOnly=true;"
    assert http(composition, path, method="GET", host="outside.invalid:8016")[0] == "403 Forbidden"
