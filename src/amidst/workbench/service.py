"""Same-origin desktop UI, server-owned role sessions and bounded scene tools.

Role selection is intentionally a trusted local demo, not authenticated identity.
Human-only evaluation and review never extend the existing Agent tool allowlist.
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import secrets
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from amidst.product.run import load_product
from amidst.workbench.presentation_gallery import Gallery, GalleryError
from amidst.workbench.product_bridge import (
    BinaryResponse,
    BridgeDenied,
    BridgeRequest,
    ContextRequest,
    ProductBridge,
)
from amidst.workbench.reviews import ReviewStore
from amidst.workbench.scenes import SceneAdapter, load_catalog

VERSION = "amidst-workbench.v1"
Role = Literal["research", "management"]
PUBLIC_EVENT_KEYS = (
    "event_ref", "kind", "time_range", "camera_ids", "media_refs", "uncertainty",
    "evidence_state", "missing_evidence", "support_state",
)
PRODUCT_ACTIONS = frozenset({
    "context", "tool", "intent", "execute", "plan", "case", "cases", "report", "review",
    "videos", "timeline", "export_report",
})


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    session_ref: str = Field(min_length=20, max_length=128)


class SceneRequest(Request):
    scene_id: str = Field(min_length=1, max_length=100)


class QueryRequest(SceneRequest):
    camera_id: str = Field(min_length=1, max_length=150)
    start: float = Field(ge=0)
    end: float = Field(ge=0)


class EventRequest(SceneRequest):
    event_ref: str = Field(min_length=1, max_length=160)


class VersionRequest(SceneRequest):
    version: int = Field(ge=0, strict=True)


class TimelineRequest(SceneRequest):
    camera_ids: list[str] = Field(min_length=1, max_length=4)
    timestamp: float = Field(ge=0)


class PresentationRequest(Request):
    presentation_ref: str = Field(min_length=1, max_length=160)


class GalleryRequest(Request):
    family_ref: str = Field(pattern=r"^gallery-family:[0-9a-f]{24}$", strict=True)


class DraftRequest(SceneRequest):
    object_id: str = Field(min_length=1, max_length=200)
    changes: dict[str, Any]
    base_version: int = Field(ge=0, strict=True)
    reviewer: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)


class ValidateRequest(Request):
    draft_id: str = Field(min_length=1, max_length=160)


class PublishRequest(ValidateRequest):
    expected_version: int = Field(ge=0, strict=True)
    reviewer: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=2000)


class ResultRequest(EventRequest):
    decision: Literal["SUPPORT", "REJECT", "UNKNOWN", "MORE_EVIDENCE"]
    reason: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=100)


class NoteRequest(EventRequest):
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED"]
    note: str = Field(min_length=1, max_length=2000)
    reviewer: str = Field(min_length=1, max_length=100)


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role


@dataclass
class Session:
    role: Role
    scene_ids: frozenset[str]
    media: dict[str, set[str]] = field(default_factory=dict)
    draft_scenes: dict[str, str] = field(default_factory=dict)
    logs: list[dict[str, Any]] = field(default_factory=list)


class Denied(ValueError):
    """Fixed public errors intentionally contain no source paths or raw payloads."""


class Workbench:
    def __init__(self, catalog: dict[str, SceneAdapter], reviews: ReviewStore, *,
                 presentation: Callable[[], dict[str, Any]] | None = None,
                 presentation_media: Callable[[str], tuple[str, bytes]] | None = None,
                 product_bridge: ProductBridge | None = None,
                 gallery: Gallery | None = None) -> None:
        self.catalog, self.reviews = catalog, reviews
        self.presentation_provider = presentation
        self.presentation_media_provider = presentation_media
        self.product_bridge, self.gallery = product_bridge, gallery
        self.sessions: dict[str, Session] = {}

    def bootstrap(self) -> dict[str, Any]:
        return {"version": VERSION, "scenes": [
            {"scene_id": s.scene_id, "label": s.label, "description": s.description,
             "product_available": self.product_bridge is not None
             and self.product_bridge.scene.scene_id == s.scene_id}
            for s in self.catalog.values()
        ], "identity": "LOCAL_ROLE_SELECTION", "desktop_only": True}

    def session(self, payload: object) -> dict[str, Any]:
        request = SessionRequest.model_validate(payload)
        token = secrets.token_urlsafe(32)
        self.sessions[token] = Session(request.role, frozenset(self.catalog))
        return {"session_ref": token, "role": request.role, "version": VERSION}

    def _session(self, token: str) -> Session:
        if token not in self.sessions:
            raise Denied("SESSION_DENIED")
        return self.sessions[token]

    def _scene(self, session: Session, scene_id: str) -> SceneAdapter:
        if scene_id not in session.scene_ids or scene_id not in self.catalog:
            raise Denied("SCENE_DENIED")
        return self.catalog[scene_id]

    @staticmethod
    def _research(session: Session) -> None:
        if session.role != "research":
            raise Denied("ROLE_DENIED")

    @staticmethod
    def _issue_media(session: Session, scene_id: str, event: dict[str, Any]) -> None:
        session.media.setdefault(scene_id, set()).update(event.get("media_refs", []))

    @staticmethod
    def _public_event(event: dict[str, Any]) -> dict[str, Any]:
        result = {key: event[key] for key in PUBLIC_EVENT_KEYS if key in event}
        # Exact frame provenance is necessary to label evidence, even in a summary view.
        result["source_frames"] = [
            {key: frame[key] for key in ("frame_ref", "camera_id", "timestamp") if key in frame}
            for frame in event.get("source_frames", [])
            if frame.get("frame_ref") in event.get("media_refs", [])
        ]
        result["uncertainty"] = (
            "此路線為盲區推論，保留多種可能；尚未確認人物身分或行為意圖。"
            if event.get("evidence_state") == "INFERRED_GAP" else
            "此為待確認的事件候選，請結合來源影像檢視；尚未確認人物身分或行為意圖。"
        )
        if event.get("missing_evidence"):
            result["uncertainty"] += " 部分來源證據缺失。"
        if event.get("support_state") == "UNKNOWN":
            result["uncertainty"] += " 可見證據不足，行為候選仍未定。"
        return result

    def _notes(self, scene_id: str, event_ref: str, role: Role) -> list[dict[str, Any]]:
        notes = self.reviews.state(scene_id).get("notes", [])
        found = [{**n, "record_status": n["status"], "status": n["handling_status"]}
                 for n in notes if n.get("event_ref") == event_ref]
        if role == "research":
            return found
        return [{k: n[k] for k in ("status", "note", "reviewer", "created_at") if k in n}
                for n in found]

    def call(self, action: str, payload: object) -> dict[str, Any]:
        schemas: dict[str, type[Request]] = {
            "scene": SceneRequest, "query": QueryRequest, "event": EventRequest,
            "timeline": TimelineRequest, "review_state": SceneRequest, "draft": DraftRequest,
            "validate": ValidateRequest, "publish": PublishRequest,
            "result_review": ResultRequest, "note": NoteRequest, "test": QueryRequest,
            "evaluation": SceneRequest, "logs": SceneRequest,
            "export": VersionRequest,
            "presentations": Request, "presentation": PresentationRequest,
            "gallery_list": Request, "gallery_detail": GalleryRequest,
        }
        if action not in schemas:
            raise Denied("ACTION_DENIED")
        request = schemas[action].model_validate(payload)
        session = self._session(request.session_ref)
        started = time.perf_counter()
        try:
            result = self._invoke(action, request, session)
        except Exception:
            session.logs.append({"action": action, "status": "REJECTED"})
            session.logs[:] = session.logs[-200:]
            raise
        scene_id = getattr(request, "scene_id", None)
        session.logs.append({"action": action, "scene_id": scene_id, "status": "OK",
                             "duration_ms": round((time.perf_counter() - started) * 1000, 3)})
        session.logs[:] = session.logs[-200:]
        return result

    def _invoke(self, action: str, request: Request, session: Session) -> dict[str, Any]:
        if action not in {"scene", "query", "event", "note"}:
            self._research(session)
        if action in {"gallery_list", "gallery_detail"}:
            if self.gallery is None:
                return {"items": [], "status": "UNAVAILABLE", "reason": "NO_REGISTERED_GALLERY"}
            if action == "gallery_list":
                return self.gallery.list()
            assert isinstance(request, GalleryRequest)
            return {"family": self.gallery.detail(request.family_ref)}
        if action in {"presentations", "presentation"}:
            if self.presentation_provider is None:
                return {"items": [], "status": "UNAVAILABLE"}
            try:
                presentation = self.presentation_provider()
            except (OSError, ValueError):
                return {"items": [], "status": "UNAVAILABLE",
                        "reason": "SOURCE_BINDING_UNAVAILABLE"}
            if action == "presentations":
                keys = ("presentation_ref", "label", "binding", "origin", "image_measurement",
                        "authority")
                return {"items": [{key: presentation[key] for key in keys}], "status": "AVAILABLE"}
            assert isinstance(request, PresentationRequest)
            if request.presentation_ref != presentation["presentation_ref"]:
                raise Denied("REFERENCE_DENIED")
            return {"presentation": presentation}
        if isinstance(request, ValidateRequest):
            scene_id = session.draft_scenes.get(request.draft_id)
            if scene_id is None:
                # Existing drafts may be resumed, but only from an allowed scene.
                for allowed in session.scene_ids:
                    drafts = self.reviews.state(allowed)["drafts"]
                    if any(d["draft_id"] == request.draft_id for d in drafts):
                        scene_id = allowed
                        break
            if scene_id is None:
                raise Denied("DRAFT_DENIED")
            self._scene(session, scene_id)
            if isinstance(request, PublishRequest):
                publication = self.reviews.publish_draft(
                    request.draft_id, request.reviewer, request.reason, request.expected_version
                )
                return {"publication": publication, "review_state": self.reviews.state(scene_id)}
            return {"validation": self.reviews.validate_draft(request.draft_id)}
        assert isinstance(request, SceneRequest)
        scene = self._scene(session, request.scene_id)
        if action == "scene":
            snapshot = scene.snapshot()
            if session.role == "management":
                snapshot = {k: snapshot[k] for k in
                            ("scene_id", "label", "description", "time_range") if k in snapshot}
                snapshot.update({"objects": [], "capabilities": {
                    "images": True, "scene_review": False, "evaluation": False,
                    "multicamera_3d": False,
                }, "cameras": [{"camera_id": c["camera_id"],
                                  "label": c.get("label", c["camera_id"])}
                                 for c in scene.snapshot()["cameras"]]})
                return {"snapshot": snapshot, "review_state": None}
            return {"snapshot": snapshot, "review_state": self.reviews.state(scene.scene_id)}
        if action in {"query", "test"}:
            assert isinstance(request, QueryRequest)
            if request.start > request.end or request.end - request.start > 120:
                raise Denied("FINITE_WINDOW_REQUIRED")
            result = scene.query(request.camera_id, request.start, request.end)
            if action == "test":
                return self._test(scene, result)
            for event in result["events"]:
                self._issue_media(session, scene.scene_id, event)
            if session.role == "management":
                return {"events": [self._public_event(e) for e in result["events"]],
                        "observations": [], "retrieval": {
                            "truncated": result.get("retrieval", {}).get("truncated", False),
                            "time_range": [request.start, request.end],
                        }}
            return result
        if action in {"event", "result_review", "note"}:
            assert isinstance(request, EventRequest)
            event = scene.event(request.event_ref)
            self._issue_media(session, scene.scene_id, event)
            if isinstance(request, ResultRequest):
                return {"review": self.reviews.record_result(
                    scene.scene_id, request.event_ref, request.decision, request.reason,
                    request.reviewer, scene.run_id,
                )}
            if isinstance(request, NoteRequest):
                record = self.reviews.record_note(
                    scene.scene_id, request.event_ref, request.status, request.note,
                    request.reviewer, scene.run_id,
                )
                record = {**record, "record_status": record["status"],
                          "status": record["handling_status"]}
                return {"note": record if session.role == "research" else {
                    k: record[k] for k in ("status", "note", "reviewer", "created_at")
                    if k in record
                }}
            return {"event": event if session.role == "research" else self._public_event(event),
                    "notes": self._notes(scene.scene_id, request.event_ref, session.role)}
        if action == "timeline":
            assert isinstance(request, TimelineRequest)
            return scene.frames(request.camera_ids, request.timestamp)
        if action == "draft":
            assert isinstance(request, DraftRequest)
            draft = self.reviews.save_draft(
                scene.scene_id, request.object_id, request.changes, request.base_version,
                request.reviewer, request.reason,
            )
            session.draft_scenes[draft["draft_id"]] = scene.scene_id
            return {"draft": draft}
        if action == "review_state":
            return self.reviews.state(scene.scene_id)
        if action == "export":
            assert isinstance(request, VersionRequest)
            state = self.reviews.state(scene.scene_id)
            version = next((v for v in state["versions"] if v["version"] == request.version), None)
            if version is None:
                raise Denied("VERSION_DENIED")
            return {"filename": f"{scene.scene_id}-annotation-v{request.version}.json",
                    "annotation": version.get("overlay", version), "receipt": version}
        if action == "evaluation":
            return {"evaluation": scene.evaluation()}
        if action == "logs":
            return {"items": [row for row in session.logs if row.get("scene_id") == scene.scene_id],
                    "identity": "SELF_DECLARED_LOCAL_OPERATOR"}
        raise Denied("ACTION_DENIED")

    def _test(self, scene: SceneAdapter, result: dict[str, Any]) -> dict[str, Any]:
        """A bounded live data check, distinct from model accuracy or full test suite."""
        checks: list[dict[str, Any]] = []
        def check(name: str, passed: bool, detail: str) -> None:
            checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})
        snapshot = scene.snapshot()
        check("場景來源綁定", bool(scene.source_hash), "已由原場景 loader 核對來源與 freeze")
        objects = snapshot["objects"]
        check("物件索引唯一", len({o["object_id"] for o in objects}) == len(objects),
              f"{len(objects)} 個已登錄物件")
        finite = all(math.isfinite(float(x)) for o in objects
                     for p in o.get("geometry", {}).get("points", []) for x in p)
        check("展示座標有效", finite, "已登錄靜態幾何使用有限座標")
        receipt = result.get("retrieval", {})
        check("局部查詢完成", not receipt.get("truncated", False),
              "只檢查所選鏡頭／時間窗；截斷不代表全域完成")
        events = result["events"]
        media = next((r for e in events for r in e.get("media_refs", [])), None)
        if media:
            _, data = scene.media(media)
            check("來源影像讀取", bool(data), "按 reference 核對並讀取一張來源影像")
        else:
            checks.append({"name": "來源影像讀取", "status": "NOT_RUN",
                           "detail": "此範圍沒有事件媒體，未假造測試樣本"})
        state = self.reviews.state(scene.scene_id)
        checks.append({"name": "標註與凍結結果版本", "status":
                       "NEEDS_RERUN" if state["current_version"] else "PASS",
                       "detail": "已發布標註另存；舊結果仍綁定原設定"})
        return {"checks": checks, "summary": {
            "passed": sum(c["status"] == "PASS" for c in checks), "total": len(checks),
            "events": len(events), "observations": len(result.get("observations", [])),
            "scope": "SELECTED_CAMERA_TIME_ONLY", "formal_acceptance": False,
        }, "retrieval": receipt}

    def media(self, token: str, scene_id: str, ref: str) -> tuple[str, bytes]:
        session = self._session(token)
        scene = self._scene(session, scene_id)
        if session.role == "management" and ref not in session.media.get(scene_id, set()):
            raise Denied("MEDIA_DENIED")
        return scene.media(ref)

    def presentation_media(self, token: str, ref: str) -> tuple[str, bytes]:
        self._research(self._session(token))
        if self.presentation_media_provider is None:
            raise Denied("RESOURCE_UNAVAILABLE")
        return self.presentation_media_provider(ref)


    def gallery_media(self, token: str, ref: str) -> tuple[str, bytes]:
        self._research(self._session(token))
        if self.gallery is None:
            raise RuntimeError("RESOURCE_UNAVAILABLE")
        return self.gallery.media(ref)

    def _product_access(self, payload: object) -> BridgeRequest:
        if not isinstance(payload, dict):
            raise ValueError("INVALID_REQUEST")
        request = BridgeRequest.model_validate({key: payload.get(key)
                                               for key in ("session_ref", "scene_id")})
        session = self._session(request.session_ref)
        self._research(session)
        self._scene(session, request.scene_id)
        return request

    def product_call(self, action: str, payload: object) -> dict[str, Any] | BinaryResponse:
        if action not in PRODUCT_ACTIONS:
            raise Denied("ACTION_DENIED")
        request = self._product_access(payload)
        session, started = self._session(request.session_ref), time.perf_counter()
        log = {"action": "product_" + action, "scene_id": request.scene_id, "status": "REJECTED"}
        try:
            if (self.product_bridge is None
                or request.scene_id != self.product_bridge.scene.scene_id):
                if action != "context":
                    raise RuntimeError("RESOURCE_UNAVAILABLE")
                # A missing optional product never replaces an existing scene.
                ContextRequest.model_validate(payload)
                result: dict[str, Any] | BinaryResponse = {
                    "scene_id": request.scene_id, "status": "UNAVAILABLE",
                    "reason": "NO_CERTIFIED_PRODUCT",
                    "capabilities": {"investigation": False, "inference_execution": False}}
            else:
                result = self.product_bridge.call(action, payload)
            log["status"] = "OK"
            return result
        finally:
            session.logs.append({**log, "duration_ms": round(
                (time.perf_counter() - started) * 1000, 3)})
            session.logs[:] = session.logs[-200:]

    def product_media(self, token: str, scene_id: str, ref: str) -> BinaryResponse:
        self._product_access({"session_ref": token, "scene_id": scene_id})
        if self.product_bridge is None:
            raise RuntimeError("RESOURCE_UNAVAILABLE")
        return self.product_bridge.media(token, scene_id, ref)

    def product_video(self, token: str, scene_id: str, ref: str,
                      range_header: str | None = None) -> BinaryResponse:
        self._product_access({"session_ref": token, "scene_id": scene_id})
        if self.product_bridge is None:
            raise RuntimeError("RESOURCE_UNAVAILABLE")
        return self.product_bridge.video(token, scene_id, ref, range_header)


def _json(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")


class Application:
    def __init__(self, workbench: Workbench, repo: Path) -> None:
        self.workbench, self.repo = workbench, repo
        self.frontend = repo / "frontend/workbench"

    def __call__(
        self, environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        status = "200 OK"
        content_type = "application/json; charset=utf-8"
        additional_headers: tuple[tuple[str, str], ...] = ()
        try:
            response = self._dispatch(environ)
            if isinstance(response, BinaryResponse):
                code = HTTPStatus(response.status)
                if not 200 <= code.value <= 599:
                    raise ValueError("INVALID_RESPONSE_STATUS")
                status = f"{code.value} {code.phrase}"
                content_type, body = response.mime_type, response.body
                if any(name.lower() not in {"accept-ranges", "content-range", "content-disposition"}
                       or "\r" in value or "\n" in value for name, value in response.headers):
                    raise ValueError("INVALID_RESPONSE_HEADERS")
                additional_headers = response.headers
            else:
                content_type, body = response
        except (Denied, BridgeDenied, GalleryError) as error:
            status = "403 Forbidden"
            content_type, additional_headers = "application/json; charset=utf-8", ()
            body = _json({"error": {"code": str(error),
                                    "message": "此操作或資料不在目前角色範圍內。"}})
        except (ValidationError, ValueError, TypeError, KeyError):
            status = "400 Bad Request"
            content_type, additional_headers = "application/json; charset=utf-8", ()
            body = _json({"error": {"code": "INVALID_OR_STALE_REQUEST",
                                    "message": "資料無效或版本已更新，請重新載入並核對輸入。"}})
        except (OSError, RuntimeError):
            status = "503 Service Unavailable"
            content_type, additional_headers = "application/json; charset=utf-8", ()
            body = _json({"error": {"code": "RESOURCE_UNAVAILABLE",
                                    "message": "所需資料目前無法讀取，請查看場景能力與來源狀態。"}})
        start_response(status, [("Content-Type", content_type), ("Content-Length", str(len(body))),
                                ("Cache-Control", "no-store"),
                                ("X-Content-Type-Options", "nosniff"),
                                ("Referrer-Policy", "no-referrer"), ("X-Frame-Options", "DENY"),
                                *additional_headers])
        return [body]

    def _dispatch(self, environ: dict[str, Any]) -> tuple[str, bytes] | BinaryResponse:
        host = environ.get("HTTP_HOST", "")
        parsed_host = urlsplit("//" + host)
        if (parsed_host.hostname not in {"127.0.0.1", "localhost"}
                or parsed_host.username or parsed_host.password or parsed_host.path
                or parsed_host.query or parsed_host.fragment
                or (environ.get("SERVER_PORT") and
                    (parsed_host.port or 80) != int(environ["SERVER_PORT"]))):
            raise Denied("HOST_DENIED")
        method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/")
        if method == "GET":
            if path == "/api/bootstrap":
                return "application/json; charset=utf-8", _json(self.workbench.bootstrap())
            if path in {"/api/product_media", "/api/product_video"}:
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "scene_id", "ref"} or any(
                    len(v) != 1 for v in query.values()
                ):
                    raise ValueError("INVALID_QUERY")
                token, scene_id, ref = (query[key][0] for key in ("session_ref", "scene_id", "ref"))
                if path == "/api/product_media":
                    return self.workbench.product_media(token, scene_id, ref)
                return self.workbench.product_video(token, scene_id, ref, environ.get("HTTP_RANGE"))
            if path == "/api/gallery_media":
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "ref"} or any(len(v) != 1 for v in query.values()):
                    raise ValueError("INVALID_QUERY")
                return self.workbench.gallery_media(query["session_ref"][0], query["ref"][0])
            if path == "/api/presentation_media":
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "ref"} or any(len(v) != 1 for v in query.values()):
                    raise ValueError("invalid query")
                return self.workbench.presentation_media(query["session_ref"][0], query["ref"][0])
            if path == "/api/media":
                query = parse_qs(environ.get("QUERY_STRING", ""), strict_parsing=True)
                if set(query) != {"session_ref", "scene_id", "ref"} or any(
                    len(value) != 1 for value in query.values()
                ):
                    raise ValueError("invalid query")
                return self.workbench.media(query["session_ref"][0], query["scene_id"][0],
                                            query["ref"][0])
            assets = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css",
                      "/app.mjs": "app.mjs", "/scene.mjs": "scene.mjs",
                      "/geometry.mjs": "geometry.mjs", "/motion.mjs": "motion.mjs",
                      "/presentation.mjs": "presentation.mjs",
                      "/investigation.mjs": "investigation.mjs", "/workflow.mjs": "workflow.mjs",
                      "/gallery.mjs": "gallery.mjs"}
            if path == "/product/timeline.mjs":
                return "text/javascript", (self.repo / "frontend/product/timeline.mjs").read_bytes()
            if path in assets:
                name = assets[path]
                mime = "text/javascript" if name.endswith(".mjs") else (
                    mimetypes.guess_type(name)[0] or "application/octet-stream")
                return mime, (self.frontend / name).read_bytes()
            vendor = {"/vendor/three.module.js": "build/three.module.js",
                      "/vendor/three.core.js": "build/three.core.js",
                      "/vendor/OrbitControls.js": "examples/jsm/controls/OrbitControls.js"}
            if path in vendor:
                root = self.repo / "frontend/workbench/node_modules/three"
                return "text/javascript", (root / vendor[path]).read_bytes()
            raise Denied("ROUTE_DENIED")
        if method != "POST" or not path.startswith("/api/"):
            raise Denied("ROUTE_DENIED")
        origin = environ.get("HTTP_ORIGIN")
        if origin and origin != f"http://{host}":
            raise Denied("ORIGIN_DENIED")
        if environ.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
            raise Denied("JSON_REQUIRED")
        length = int(environ.get("CONTENT_LENGTH", "0"))
        if not 0 < length <= 65536:
            raise Denied("REQUEST_SIZE_DENIED")
        payload = json.loads(environ["wsgi.input"].read(length))
        action = path.removeprefix("/api/")
        if action.startswith("product_"):
            result = self.workbench.product_call(action.removeprefix("product_"), payload)
            return result if isinstance(result, BinaryResponse) else (
                "application/json; charset=utf-8", _json(result))
        data = self.workbench.session(payload) if action == "session" else (
            self.workbench.call(action, payload))
        return "application/json; charset=utf-8", _json(data)


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Media query strings contain local session tokens; do not log them.
        pass


def configure_extensions(
    workbench: Workbench, repo: Path, *,
    canonical_root: Path | None = None,
) -> None:
    """Server-owned fixed sources; invalid optional products fail closed independently."""
    runtime = None
    try:
        scene = workbench.catalog.get("local-camera")
        if scene is not None:
            runtime = load_product(repo / "data/product/local_run/operator_v2")
            workbench.product_bridge = ProductBridge(runtime, scene, workbench._session)
    except (ValueError, OSError, KeyError, TypeError):
        if runtime is not None:
            runtime.close()
        workbench.product_bridge = None
    try:
        workbench.gallery = Gallery(repo, canonical_root)
    except (GalleryError, OSError, ValueError, TypeError):
        workbench.gallery = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Amidst shared desktop workbench")
    parser.add_argument("--port", type=int, default=8016)
    parser.add_argument("--state", type=Path)
    parser.add_argument("--catalog", type=Path,
                        help="Server-owned scene catalog; browser callers cannot supply paths")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--canonical-root", type=Path,
                        help="Read-only historical gallery source; server configuration only")
    args = parser.parse_args()
    repo = args.repo.resolve()
    state = args.state or repo / "data/engineering/local_run/workbench_v1/reviews.sqlite3"
    catalog = load_catalog(repo, manifest_path=args.catalog)
    if not catalog:
        parser.error("No verified scenes; materialize the documented checkpoints.")
    review_keys = ("scene_id", "source_hash", "model_revision", "run_id", "objects")
    reviews = ReviewStore(state, {
        key: {field: scene.snapshot()[field] for field in review_keys}
        for key, scene in catalog.items()
    })
    from amidst.workbench.source_presentation import (
        load_source_presentation,
        source_presentation_media,
    )
    workbench = Workbench(catalog, reviews,
        presentation=lambda: load_source_presentation(repo),
        presentation_media=lambda ref: source_presentation_media(repo, ref))
    canonical_root = args.canonical_root or (
        repo.parent.parent if repo.parent.name == ".local-worktrees" else repo)
    configure_extensions(workbench, repo, canonical_root=canonical_root)
    app = Application(workbench, repo)
    print(f"Amidst workbench: http://127.0.0.1:{args.port} "
          f"({len(catalog)} verified scenes)", flush=True)
    try:
        with make_server("127.0.0.1", args.port, app, handler_class=QuietHandler) as server:
            server.serve_forever()
    finally:
        if workbench.product_bridge is not None:
            workbench.product_bridge.runtime.close()


if __name__ == "__main__":
    main()
