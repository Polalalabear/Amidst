"""Loopback operator/API transport; no filesystem, truth or external provider tools."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler, make_server

from pydantic import Field

from amidst.domain.common import DomainModel, Timestamp
from amidst.engineering.facade import ToolFailure, ToolRequest
from amidst.engineering.registry import ResourceRef
from amidst.product.contracts import EventDetail
from amidst.product.investigation import InvestigationIntent, ReviewRequest
from amidst.product.operator import OperatorWorkspace, report_html
from amidst.product.run import ProductRuntime
from amidst.product.service import ProductService, response_types
from amidst.product.timeline import timeline_state


class IntentEnvelope(ToolRequest):
    intent: InvestigationIntent


class ExecuteEnvelope(ToolRequest):
    plan_ref: ResourceRef
    max_new_calls: int | None = Field(default=None, ge=1, le=256, strict=True)
    stop: bool = Field(default=False, strict=True)
    resume: bool = Field(default=False, strict=True)


class PlanEnvelope(ToolRequest):
    plan_ref: ResourceRef


class ReviewEnvelope(ToolRequest):
    review: ReviewRequest


class TimelineEnvelope(ToolRequest):
    timestamp: Timestamp = Field(strict=True)
    event_refs: tuple[ResourceRef, ...] | None = None


class ReportEnvelope(ToolRequest):
    report_ref: ResourceRef


class SceneRegion(DomainModel):
    region_id: str
    bounds_xy_m: tuple[float, float, float, float]
    floor_z_m: float


class SceneCamera(DomainModel):
    camera_id: str
    camera_ref: ResourceRef


class SceneResponse(DomainModel):
    run_ref: ResourceRef
    model_id: str
    model_revision: str
    regions: tuple[SceneRegion, ...]
    cameras: tuple[SceneCamera, ...]
    units: str = "METRES"
    coordinate_system: str = "BLENDER_RIGHT_HANDED_Z_UP"
    origin: str = "SYNTHETIC"
    authority: str = "SYNTHETIC_CONFIG"
    synchronization: str = "SOFT_SYNCHRONIZATION"


class ProductApplication:
    def __init__(self, runtime: ProductRuntime, *, frontend: Path | None = None) -> None:
        self.runtime = runtime
        self.services = {s.context().session_ref: s for s in runtime.services}
        self.workspaces = {key: OperatorWorkspace(service)
                           for key, service in self.services.items()}
        self.frontend = (frontend if frontend is not None else
                         Path(__file__).resolve().parents[3] / "frontend" / "product")
        from amidst.engineering.research_scene import ResearchPackage
        self.package = ResearchPackage.model_validate_json(
            (runtime.source / "package.json").read_bytes())

    @staticmethod
    def _results(service: ProductService) -> None:
        if service.base.guard.stage != "RESULTS":
            raise ToolFailure("STAGE_DENIED")

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]
                 ) -> Iterable[bytes]:
        def respond(status: str, value: object, mime: str = "application/json",
                    extra: list[tuple[str, str]] | None = None) -> list[bytes]:
            body = value if isinstance(value, bytes) else json.dumps(
                value, allow_nan=False, separators=(",", ":")).encode()
            headers = [("Content-Type", mime), ("Content-Length", str(len(body))),
                       ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                       ("Content-Security-Policy", "default-src 'self'; script-src 'self'; "
                        "style-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
                        "connect-src 'self'; object-src 'none'; frame-ancestors 'none'; "
                        "base-uri 'none'")]
            start_response(status, headers + (extra or []))
            return [body]

        path, method = environ.get("PATH_INFO", ""), environ.get("REQUEST_METHOD", "")
        host = environ.get("HTTP_HOST", "")
        matched_host = re.fullmatch(r"(?:127\.0\.0\.1|localhost)(?::([0-9]{1,5}))?", host)
        if (matched_host is None or (matched_host[1] is not None
            and not 1 <= int(matched_host[1]) <= 65535)
            or environ.get("REMOTE_ADDR", "127.0.0.1") not in ("127.0.0.1", "::1")):
            return respond("403 Forbidden", {"error": "LOCAL_TRANSPORT_REQUIRED"})
        origin = environ.get("HTTP_ORIGIN")
        if origin is not None and origin != "http://" + host:
            return respond("403 Forbidden", {"error": "ORIGIN_DENIED"})
        try:
            static = {"/": ("index.html", "text/html; charset=utf-8"),
                      "/style.css": ("style.css", "text/css"),
                      "/app.mjs": ("app.mjs", "text/javascript"),
                      "/timeline.mjs": ("timeline.mjs", "text/javascript")}
            if method == "GET" and path in static:
                name, mime = static[path]
                return respond("200 OK", (self.frontend / name).read_bytes(), mime)
            if method == "GET" and path in (
                "/vendor/three.module.js", "/vendor/three.core.js",
            ):
                name = path.removeprefix("/vendor/")
                return respond("200 OK", (self.frontend / "node_modules" / "three" / "build" /
                                           name).read_bytes(), "text/javascript")
            if method == "GET" and path == "/product/v1/contexts":
                return respond("200 OK", {"items": [s.context().model_dump(mode="json")
                                                     for s in self.services.values()]})
            if method == "GET" and path == "/product/v1/contract":
                return respond("200 OK", {"version": "local-product.v1",
                    "tools": list(response_types()),
                    "response_schemas": {name: model.model_json_schema()
                                         for name, model in response_types().items()},
                    "intent_schema": IntentEnvelope.model_json_schema(),
                    "execute_schema": ExecuteEnvelope.model_json_schema(),
                    "review_schema": ReviewEnvelope.model_json_schema()})
            if method == "GET" and path.startswith(("/product/v1/media/", "/product/v1/video/")):
                query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True)
                if set(query) != {"session_ref"} or len(query["session_ref"]) != 1:
                    raise ToolFailure("INVALID_REQUEST")
                service = self.services.get(query["session_ref"][0])
                if service is None:
                    raise ToolFailure("SCOPE_DENIED")
                ref = path.rsplit("/", 1)[-1]
                if path.startswith("/product/v1/media/"):
                    service.call("get_media", {"session_ref": service.context().session_ref,
                                               "media_ref": ref})
                    data = service.base.store.media_bytes(service.base.scope, ref)
                    return respond("200 OK", data, service.base.frames[ref].media_type)
                self._results(service)
                video = self.runtime.video_manifest
                if video is None:
                    raise ToolFailure("VIDEO_NOT_MATERIALIZED")
                artifact = next((a for a in video.artifacts if a.video_ref == ref), None)
                if artifact is None:
                    raise ToolFailure("REFERENCE_DENIED")
                destination = (self.runtime.video_pool / artifact.relative_path).resolve()
                destination.relative_to(self.runtime.video_pool.resolve())
                data = destination.read_bytes()
                if hashlib.sha256(data).hexdigest() != artifact.sha256:
                    raise ToolFailure("MEDIA_HASH_MISMATCH")
                range_header = environ.get("HTTP_RANGE")
                if range_header is not None:
                    match = re.fullmatch(r"bytes=(\d+)-(\d*)", range_header)
                    if match is None:
                        return respond("416 Range Not Satisfiable", {"error": "RANGE_DENIED"})
                    first = int(match[1])
                    last = int(match[2]) if match[2] else len(data) - 1
                    if not 0 <= first <= last < len(data):
                        return respond("416 Range Not Satisfiable", {"error": "RANGE_DENIED"})
                    return respond("206 Partial Content", data[first:last + 1], "video/mp4",
                        [("Content-Range", f"bytes {first}-{last}/{len(data)}"),
                         ("Accept-Ranges", "bytes")])
                return respond("200 OK", data, "video/mp4", [("Accept-Ranges", "bytes")])
            if method != "POST" or not path.startswith("/product/v1/"):
                return respond("404 Not Found", {"error": "ROUTE_UNAVAILABLE"})
            if environ.get("CONTENT_TYPE", "").split(";")[0] != "application/json":
                raise ToolFailure("INVALID_REQUEST")
            size = int(environ.get("CONTENT_LENGTH", "0"))
            if not 0 < size <= 65536 or environ.get("QUERY_STRING"):
                raise ToolFailure("INVALID_REQUEST")
            payload = json.loads(environ["wsgi.input"].read(size))
            if not isinstance(payload, dict) or not isinstance(payload.get("session_ref"), str):
                raise ToolFailure("INVALID_REQUEST")
            service = self.services.get(payload["session_ref"])
            if service is None:
                raise ToolFailure("SCOPE_DENIED")
            workspace = self.workspaces[payload["session_ref"]]
            if path.startswith("/product/v1/tools/"):
                return respond("200 OK", service.call(path.removeprefix("/product/v1/tools/"),
                                                      payload))
            if path == "/product/v1/intent":
                request = IntentEnvelope.model_validate(payload)
                return respond("200 OK", workspace.compile(request.intent).model_dump(mode="json"))
            self._results(service)
            if path == "/product/v1/execute":
                execute = ExecuteEnvelope.model_validate(payload)
                return respond("200 OK", workspace.execute(execute.plan_ref,
                    max_new_calls=execute.max_new_calls, stop=execute.stop,
                    resume=execute.resume).model_dump(mode="json"))
            if path in ("/product/v1/report", "/product/v1/case", "/product/v1/plan"):
                plan = PlanEnvelope.model_validate(payload)
                result = (workspace.report(plan.plan_ref) if path.endswith("/report") else
                          workspace.store.get_plan(plan.plan_ref) if path.endswith("/plan") else
                          workspace.store.get_case(plan.plan_ref))
                if result is None:
                    raise ToolFailure("CASE_UNAVAILABLE")
                return respond("200 OK", result.model_dump(mode="json"))
            if path == "/product/v1/review":
                review = ReviewEnvelope.model_validate(payload)
                return respond("200 OK", workspace.review(review.review).model_dump(mode="json"))
            if path == "/product/v1/export-report":
                export = ReportEnvelope.model_validate(payload)
                record = service.repository.get_revision(service.scope.run_ref, "REPORT",
                                                         export.report_ref)
                if record is None:
                    raise ToolFailure("REPORT_UNAVAILABLE")
                from amidst.product.investigation import InvestigationReport
                result = InvestigationReport.model_validate(record.payload)
                if result.binding != workspace.binding:
                    raise ToolFailure("SCOPE_DENIED")
                return respond("200 OK", report_html(result).encode(), "text/html; charset=utf-8")
            envelope = (ToolRequest.model_validate(payload)
                        if not path.endswith("/timeline") else None)
            if path == "/product/v1/view/scene":
                package = self.package
                scene = SceneResponse(run_ref=service.scope.run_ref,
                    model_id=service.base.scope.model_id,
                    model_revision=service.base.scope.model_revision,
                    regions=tuple(SceneRegion(region_id=r.region_id, bounds_xy_m=r.bounds_xy_m,
                                              floor_z_m=package.context.ground_plane.point[2])
                                  for r in package.context.regions
                                  if r.floor_id == package.context.ground_plane.floor_id),
                    cameras=tuple(SceneCamera(camera_id=c.camera_id, camera_ref=c.camera_ref)
                                  for c in service.base.cameras.values()))
                return respond("200 OK", scene.model_dump(mode="json"))
            if path == "/product/v1/view/videos":
                video = self.runtime.video_manifest
                return respond("200 OK", {"items": [] if video is None else [
                    a.model_dump(mode="json", exclude={"relative_path"}) for a in video.artifacts],
                    "source_rgb_rate_hz": self.package.fps, "cv_rate_hz": self.package.fps,
                    "presentation_video_rate_hz": 15, "presentation_only": True})
            if path == "/product/v1/view/timeline":
                seek = TimelineEnvelope.model_validate(payload)
                refs = tuple(service.base.events) if seek.event_refs is None else seek.event_refs
                if any(ref not in service.base.events for ref in refs):
                    raise ToolFailure("REFERENCE_DENIED")
                events = tuple(EventDetail.model_validate(service.base.events[ref]) for ref in refs)
                timeline = timeline_state(service.scope.run_ref, seek.timestamp,
                                        tuple(service.base.frames.values()), events)
                return respond("200 OK", timeline.model_dump(mode="json"))
            if path == "/product/v1/cases":
                assert envelope is not None
                records = service.repository.list_latest_revisions(
                    service.scope.run_ref, "CASE", limit=101)
                items = []
                for record in records:
                    stored = workspace.store.get_plan(record.entity_ref)
                    if stored.binding == workspace.binding:
                        case = workspace.store.get_case(stored.plan_ref)
                        items.append({"plan_ref": stored.plan_ref, "task": stored.task,
                                      "state": "READY" if case is None else case.state})
                return respond("200 OK", {"items": items[:100], "truncated": len(items) > 100})
            return respond("404 Not Found", {"error": "ROUTE_UNAVAILABLE"})
        except ToolFailure as error:
            return respond("403 Forbidden", {"error": str(error)})
        except (ValueError, KeyError, TypeError, OSError, StopIteration):
            return respond("400 Bad Request", {"error": "INVALID_OR_UNAVAILABLE"})


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def serve(runtime: ProductRuntime, port: int = 8020) -> None:
    with make_server("127.0.0.1", port, ProductApplication(runtime),
                     handler_class=QuietHandler) as server:
        print(f"Amidst local Phase 2 operator: http://127.0.0.1:{port}", flush=True)
        server.serve_forever()
