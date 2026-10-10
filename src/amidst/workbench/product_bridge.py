"""Research-only composition over an existing independently frozen E1 product.

Workbench sessions authorize the outer operation; original product bindings and
IDs remain unchanged inside the separate append-only case/report/review ledger.
This module never builds inference, encodes video, opens GT, or grants management
access. The application must supply its server-owned session lookup.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import Field, field_validator

from amidst.domain.common import DomainModel, Timestamp
from amidst.engineering.access import Mode
from amidst.engineering.registry import (
    ClockBinding,
    CoordinateBinding,
    ResourceRef,
    Sha256,
    safe_relative_path,
)
from amidst.product.contracts import CameraSummary, EventDetail, ProductContext
from amidst.product.investigation import (
    InvestigationIntent,
    InvestigationPlan,
    InvestigationPolicy,
    ReviewRequest,
)
from amidst.product.operator import OperatorWorkspace, report_html
from amidst.product.run import FrameMetadata, ProductRuntime, digest
from amidst.product.service import ProductService
from amidst.product.timeline import timeline_state
from amidst.workbench.scenes import SceneAdapter


class SessionAccess(Protocol):
    @property
    def role(self) -> str: ...

    @property
    def scene_ids(self) -> frozenset[str]: ...


SessionLookup = Callable[[str], SessionAccess]


class BridgeDenied(ValueError):
    """Fixed public codes, with no rejected input, source path or raw exception."""


class BridgeRequest(DomainModel):
    session_ref: str = Field(min_length=20, max_length=128, strict=True)
    scene_id: str = Field(min_length=1, max_length=100, strict=True)


class ContextRequest(BridgeRequest):
    observation_mode: Mode | None = None


class ToolRequest(BridgeRequest):
    tool: str = Field(min_length=1, max_length=80, strict=True)
    params: dict[str, Any] = Field(default_factory=dict)


def _window(value: object) -> None:
    if (not isinstance(value, (list, tuple)) or len(value) != 2
        or any(isinstance(t, bool) or not isinstance(t, (int, float))
               or not math.isfinite(t) for t in value)
        or value[0] < 0 or value[1] < value[0] or value[1] - value[0] > 120):
        raise BridgeDenied("FINITE_WINDOW_REQUIRED")


class IntentRequest(BridgeRequest):
    intent: InvestigationIntent

    @field_validator("intent", mode="before")
    @classmethod
    def explicit_window(cls, value: object) -> object:
        if isinstance(value, dict) and value.get("time_range") is not None:
            _window(value["time_range"])
        return value


class PlanRequest(BridgeRequest):
    plan_ref: ResourceRef


class ExecuteRequest(PlanRequest):
    max_new_calls: int | None = Field(default=None, ge=1, le=256, strict=True)
    stop: bool = Field(default=False, strict=True)
    resume: bool = Field(default=False, strict=True)


class CaseListRequest(BridgeRequest):
    limit: int = Field(default=100, ge=1, le=100, strict=True)


class ReviewFields(DomainModel):
    report_ref: ResourceRef
    report_sha256: Sha256
    action: Literal["PRESERVE_AMBIGUITY", "REQUEST_EVIDENCE", "SELECT_PRESENTATION"]
    reason_code: Literal["AMBIGUOUS_EVIDENCE", "MISSING_EVIDENCE", "DISPLAY_PREFERENCE"]
    alternative_ref: ResourceRef | None = None


class ReviewEnvelope(BridgeRequest):
    review: ReviewFields


class ExportRequest(BridgeRequest):
    report_ref: ResourceRef


class TimelineRequest(BridgeRequest):
    timestamp: Timestamp = Field(strict=True)
    event_refs: tuple[ResourceRef, ...] | None = Field(default=None, max_length=128)


class VideosRequest(BridgeRequest):
    camera_refs: tuple[ResourceRef, ...] | None = Field(default=None, max_length=4)


class BridgeCapabilities(DomainModel):
    investigation: Literal[True] = True
    appearance: Literal[True] = True
    stitch: Literal[True] = True
    videos: bool
    timeline: Literal[True] = True
    media: Literal[True] = True
    inference_execution: Literal[False] = False


class SourceMetadata(DomainModel):
    source_ref: str = Field(pattern=r"^source:(?:[0-9a-f]{24}|[0-9a-f]{64})$")
    source_sha256: Sha256
    model_id: str
    model_revision: str
    run_id: str
    clock_id: str
    camera_count: int = Field(ge=1)
    frame_count: int = Field(ge=1)
    time_range: tuple[Timestamp, Timestamp]
    source_rgb_rate_hz: float | None
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"


class BridgeContext(DomainModel):
    scene_id: str
    observation_mode: Mode
    decision_stage: Literal["RESULTS"] = "RESULTS"
    available_modes: tuple[Mode, ...]
    product_context: ProductContext
    policy: InvestigationPolicy
    capabilities: BridgeCapabilities
    source: SourceMetadata
    cameras: tuple[CameraSummary, ...]
    clock: ClockBinding
    coordinates: CoordinateBinding


class CaseItem(DomainModel):
    plan_ref: ResourceRef
    task: Literal["TRACE", "COMPARE", "BEHAVIOR", "MULTI_TARGET"]
    state: str


class CaseList(DomainModel):
    items: tuple[CaseItem, ...]
    truncated: bool


class VideoView(DomainModel):
    """VideoArtifact's complete public metadata, excluding its private locator."""
    video_ref: ResourceRef
    camera_ref: ResourceRef
    camera_id: str
    sha256: Sha256
    byte_count: int = Field(ge=1)
    input_frames_sha256: Sha256
    source_frame_refs: tuple[ResourceRef, ...]
    start_time: Timestamp
    end_time: Timestamp
    frame_count: int = Field(ge=1)
    fps: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    sampling: Literal["NEAREST_REGISTERED_RGB_FRAME_HOLD"]
    origin: Literal["SYNTHETIC"]
    annotations: Literal["NONE"]
    codec: Literal["H264_YUV420P_PRESENTATION_ONLY"]


class VideoList(DomainModel):
    items: tuple[VideoView, ...]
    source_rgb_rate_hz: float | None
    cv_rate_hz: float | None
    presentation_video_rate_hz: Literal[15] = 15
    presentation_only: Literal[True] = True


@dataclass(frozen=True)
class BinaryResponse:
    status: int
    mime_type: str
    headers: tuple[tuple[str, str], ...]
    body: bytes


_REQUESTS: dict[str, type[BridgeRequest]] = {
    "context": ContextRequest, "tool": ToolRequest, "intent": IntentRequest,
    "execute": ExecuteRequest, "plan": PlanRequest, "case": PlanRequest,
    "cases": CaseListRequest, "report": PlanRequest, "review": ReviewEnvelope,
    "videos": VideosRequest, "timeline": TimelineRequest, "export_report": ExportRequest,
}


class ProductBridge:
    def __init__(self, runtime: ProductRuntime, scene: SceneAdapter,
                 session_lookup: SessionLookup, policy: InvestigationPolicy | None = None) -> None:
        self.runtime, self.scene, self.session_lookup = runtime, scene, session_lookup
        self.policy = (InvestigationPolicy() if policy is None else
                       InvestigationPolicy.model_validate_json(policy.model_dump_json()))
        self._modes: dict[str, Mode] = {}
        try:
            base = scene.service
            snapshot = scene.snapshot()
            if (snapshot["evidence_level"] != "E1_CONFIGURED_PINHOLE_RGB"
                or base.guard.stage != "RESULTS"
                or base.guard.binding.observation_mode != "photos_plus_observations"
                or not base.cameras or any(c.calibration is None for c in base.cameras.values())):
                raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
            self.services = {s.scope.observation_mode: s for s in runtime.services}
            modes: tuple[Mode, ...] = tuple(m.observation_mode for m in runtime.manifest.modes)
            if modes != ("photos_only", "photos_plus_observations") or (
                len(runtime.services) != 2 or set(self.services) != set(modes)
                or runtime.source.resolve() != runtime.manifest.source.resolve()
                or runtime.video_pool.resolve() != runtime.manifest.video_pool.resolve()
                or (runtime.video_manifest is None) != (
                    runtime.manifest.video_manifest_sha256 is None)
            ):
                raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
            self.available_modes: tuple[Mode, ...] = tuple(m.observation_mode
                                                           for m in runtime.manifest.modes)
            self._scene_binding = digest(base.guard.binding)
            self._bindings: dict[Mode, str] = {}
            for saved in runtime.manifest.modes:
                service = self.services[saved.observation_mode]
                if (service.scope != saved.scope or service.scope.resource_scope != base.scope
                    or service.base.scope != base.scope or service.base.guard.stage != "RESULTS"
                    or service.base.guard.binding != saved.base_receipt.binding
                    or digest(service.base.guard.binding.model_dump(exclude={"observation_mode"}))
                    != digest(base.guard.binding.model_dump(exclude={"observation_mode"}))
                    or service.product_freeze_ref != saved.product_freeze_ref
                    or service.repository.verify_run(service.scope.run_ref)
                    != saved.record_set_receipt
                    or digest(service.base.cameras) != digest(base.cameras)
                    or self._frame_hash(service) != self._frame_hash_scene()
                ):
                    raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
                self._bindings[saved.observation_mode] = digest(service.base.guard.binding)
            self.workspaces = {mode: OperatorWorkspace(service, self.policy)
                               for mode, service in self.services.items()}
            model = next(m for m in base.store.registry.models if m.scope == base.scope)
            self.clock, self.coordinates = model.clock, model.coordinates
            data = (runtime.source / "package.json").read_bytes()
            if hashlib.sha256(data).hexdigest() != runtime.manifest.source_documents[
                "package.json"]:
                raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
            raw = json.loads(data)
            fps = raw["fps"]
            if (isinstance(fps, bool) or not isinstance(fps, (int, float))
                or not math.isfinite(fps) or fps <= 0):
                raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
            frames = tuple(base.frames.values())
            scope = base.scope
            self.source = SourceMetadata(source_ref=base.guard.binding.source_ref,
                source_sha256=scope.source_sha256, model_id=scope.model_id,
                model_revision=scope.model_revision, run_id=scope.run_id, clock_id=scope.clock_id,
                camera_count=len(base.cameras), frame_count=len(frames),
                time_range=(min(f.timestamp for f in frames), max(f.timestamp for f in frames)),
                source_rgb_rate_hz=float(fps))
            if runtime.video_manifest is not None:
                self._validate_video_metadata()
        except (ValueError, KeyError, TypeError, OSError, StopIteration):
            raise BridgeDenied("PRODUCT_SCOPE_MISMATCH") from None

    @staticmethod
    def _frame_hash(service: ProductService) -> str:
        return ProductBridge._frames_hash(service.base.frames)

    def _frame_hash_scene(self) -> str:
        return self._frames_hash(self.scene.service.frames)

    @staticmethod
    def _frames_hash(frames: dict[str, Any]) -> str:
        rows = tuple(FrameMetadata.model_validate({field: getattr(frame, field)
                     for field in FrameMetadata.model_fields})
                     for _, frame in sorted(frames.items()))
        if not rows:
            raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
        return digest(rows)

    def _validate_video_metadata(self) -> None:
        manifest = self.runtime.video_manifest
        assert manifest is not None
        base = self.scene.service
        if (manifest.scope != base.scope or manifest.registry_sha256 != base.store.registry.sha256
            or digest(manifest) != self.runtime.manifest.video_manifest_sha256 or manifest.fps != 15
            or len(manifest.artifacts) != len(base.cameras)
            or {a.camera_ref for a in manifest.artifacts} != set(base.cameras)):
            raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
        for artifact in manifest.artifacts:
            frames = sorted((f for f in base.frames.values()
                             if f.camera_ref == artifact.camera_ref), key=lambda f: f.timestamp)
            if (artifact.source_frame_refs != tuple(f.media_ref for f in frames)
                or artifact.input_frames_sha256 != digest([
                    (f.media_ref, f.timestamp, f.sha256) for f in frames])
                or artifact.start_time != frames[0].timestamp
                or artifact.end_time != frames[-1].timestamp or artifact.fps != 15):
                raise BridgeDenied("PRODUCT_SCOPE_MISMATCH")
            VideoView.model_validate(artifact.model_dump(exclude={"relative_path"}))

    def _access(self, request: BridgeRequest) -> tuple[ProductService, OperatorWorkspace]:
        try:
            session = self.session_lookup(request.session_ref)
        except (ValueError, KeyError):
            raise BridgeDenied("SESSION_DENIED") from None
        if session.role != "research":
            raise BridgeDenied("ROLE_DENIED")
        if request.scene_id != self.scene.scene_id or request.scene_id not in session.scene_ids:
            raise BridgeDenied("SCENE_DENIED")
        mode = self._modes.get(request.session_ref, "photos_plus_observations")
        service = self.services[mode]
        if (self.scene.service.guard.stage != "RESULTS" or service.base.guard.stage != "RESULTS"
            or service.base.scope != self.scene.service.scope
            or digest(self.scene.service.guard.binding) != self._scene_binding
            or digest(service.base.guard.binding) != self._bindings[mode]
            or service.context().product_freeze_ref != self.workspaces[mode].binding.freeze_ref):
            raise BridgeDenied("PRODUCT_BINDING_DENIED")
        return service, self.workspaces[mode]

    def call(self, action: str, payload: object) -> dict[str, Any] | BinaryResponse:
        if action not in _REQUESTS:
            raise BridgeDenied("ACTION_DENIED")
        try:
            request = _REQUESTS[action].model_validate(payload)
            service, workspace = self._access(request)
            if isinstance(request, ContextRequest):
                if request.observation_mode is not None:
                    self._modes[request.session_ref] = request.observation_mode
                    service, workspace = self._access(request)
                return self._context(service).model_dump(mode="json")
            result = self._invoke(action, request, service, workspace)
            return result if isinstance(result, (dict, BinaryResponse)) else result.model_dump(
                mode="json")
        except BridgeDenied:
            raise
        except (ValueError, KeyError, TypeError, OSError, StopIteration):
            raise BridgeDenied("INVALID_OR_UNAVAILABLE") from None

    def _context(self, service: ProductService) -> BridgeContext:
        cameras = service.call("list_cameras", {"session_ref": service.context().session_ref})
        return BridgeContext(scene_id=self.scene.scene_id,
            observation_mode=service.scope.observation_mode, available_modes=self.available_modes,
            product_context=service.context(), policy=self.policy,
            capabilities=BridgeCapabilities(videos=self.runtime.video_manifest is not None),
            source=self.source, cameras=tuple(CameraSummary.model_validate(c)
                                             for c in cameras["items"]),
            clock=self.clock, coordinates=self.coordinates)

    def _invoke(self, action: str, request: BridgeRequest, service: ProductService,
                workspace: OperatorWorkspace) -> Any:
        if isinstance(request, ToolRequest):
            if "session_ref" in request.params:
                raise BridgeDenied("PRODUCT_SESSION_OVERRIDE_DENIED")
            if "time_range" in request.params:
                _window(request.params["time_range"])
            return service.call(request.tool, {"session_ref": service.context().session_ref,
                                               **request.params})
        if isinstance(request, IntentRequest):
            if request.intent.time_range is not None:
                _window(request.intent.time_range)
            return workspace.compile(request.intent)
        if isinstance(request, ExecuteRequest):
            return workspace.execute(request.plan_ref, max_new_calls=request.max_new_calls,
                                     stop=request.stop, resume=request.resume)
        if isinstance(request, PlanRequest):
            if action == "plan":
                return workspace.store.get_plan(request.plan_ref)
            if action == "report":
                return workspace.report(request.plan_ref)
            case = workspace.store.get_case(request.plan_ref)
            if case is None:
                raise BridgeDenied("CASE_UNAVAILABLE")
            return case
        if isinstance(request, CaseListRequest):
            rows = service.repository.list_latest_revisions(service.scope.run_ref, "CASE",
                                                            limit=request.limit + 1)
            items = []
            for row in rows:
                first = service.repository.get_revision(service.scope.run_ref, "CASE",
                                                        row.entity_ref, version=1)
                if first is None or first.payload.get("type") != "PLAN":
                    raise BridgeDenied("CASE_UNAVAILABLE")
                plan = InvestigationPlan.model_validate(first.payload.get("plan"))
                if plan.binding != workspace.binding:
                    continue
                case = workspace.store.get_case(plan.plan_ref)
                items.append(CaseItem(plan_ref=plan.plan_ref, task=plan.task,
                                      state="READY" if case is None else case.state))
            return CaseList(items=tuple(items[:request.limit]), truncated=len(rows) > request.limit)
        if isinstance(request, ReviewEnvelope):
            review = ReviewRequest(**request.review.model_dump(),
                                   operator_ref=service.context().operator_ref)
            return workspace.review(review)
        if isinstance(request, VideosRequest):
            manifest = self.runtime.video_manifest
            selected = request.camera_refs
            if selected is not None and (len(set(selected)) != len(selected)
                                         or not set(selected) <= set(service.base.cameras)):
                raise BridgeDenied("REFERENCE_DENIED")
            videos = () if manifest is None else tuple(VideoView.model_validate(
                a.model_dump(exclude={"relative_path"})) for a in manifest.artifacts
                if selected is None or a.camera_ref in selected)
            return VideoList(items=videos, source_rgb_rate_hz=self.source.source_rgb_rate_hz,
                             cv_rate_hz=self.source.source_rgb_rate_hz)
        if isinstance(request, TimelineRequest):
            refs = tuple(service.base.events) if request.event_refs is None else request.event_refs
            if len(refs) > 128 or any(ref not in service.base.events for ref in refs):
                raise BridgeDenied("REFERENCE_DENIED")
            events = tuple(EventDetail.model_validate(service.base.events[ref]) for ref in refs)
            return timeline_state(service.scope.run_ref, request.timestamp,
                                  tuple(service.base.frames.values()), events)
        assert isinstance(request, ExportRequest)
        report_row = service.repository.get_revision(service.scope.run_ref, "REPORT",
                                                     request.report_ref)
        if report_row is None:
            raise BridgeDenied("REPORT_UNAVAILABLE")
        from amidst.product.investigation import InvestigationReport
        report = InvestigationReport.model_validate(report_row.payload)
        if report.binding != workspace.binding:
            raise BridgeDenied("PRODUCT_BINDING_DENIED")
        return BinaryResponse(200, "text/html; charset=utf-8", (), report_html(report).encode())

    def media(self, session_ref: str, scene_id: str, media_ref: str) -> BinaryResponse:
        try:
            request = BridgeRequest(session_ref=session_ref, scene_id=scene_id)
            service, _ = self._access(request)
            result = service.call("get_media", {"session_ref": service.context().session_ref,
                                                "media_ref": media_ref})
            data = base64.b64decode(result["base64"], validate=True)
            if hashlib.sha256(data).hexdigest() != result["sha256"]:
                raise BridgeDenied("MEDIA_HASH_MISMATCH")
            return BinaryResponse(200, result["mime_type"], (), data)
        except BridgeDenied:
            raise
        except (ValueError, KeyError, TypeError, OSError):
            raise BridgeDenied("INVALID_OR_UNAVAILABLE") from None

    def video(self, session_ref: str, scene_id: str, video_ref: str,
              range_header: str | None = None) -> BinaryResponse:
        try:
            self._access(BridgeRequest(session_ref=session_ref, scene_id=scene_id))
            manifest = self.runtime.video_manifest
            if manifest is None:
                raise BridgeDenied("VIDEO_NOT_MATERIALIZED")
            artifact = next((a for a in manifest.artifacts if a.video_ref == video_ref), None)
            if artifact is None:
                raise BridgeDenied("REFERENCE_DENIED")
            pool = self.runtime.video_pool.resolve()
            destination = pool.joinpath(*safe_relative_path(artifact.relative_path).parts)
            if destination.is_symlink() or not destination.resolve().is_relative_to(pool):
                raise BridgeDenied("REFERENCE_DENIED")
            data = destination.read_bytes()
            if (hashlib.sha256(data).hexdigest() != artifact.sha256
                or len(data) != artifact.byte_count):
                raise BridgeDenied("MEDIA_HASH_MISMATCH")
            headers = (("Accept-Ranges", "bytes"),)
            if range_header is not None:
                match = re.fullmatch(r"bytes=(\d{1,20})-(\d{0,20})", range_header)
                if match is not None:
                    first, last = int(match[1]), int(match[2]) if match[2] else len(data) - 1
                    if 0 <= first <= last < len(data):
                        return BinaryResponse(206, "video/mp4", headers + (("Content-Range",
                            f"bytes {first}-{last}/{len(data)}"),), data[first:last + 1])
                return BinaryResponse(416, "application/json", (("Content-Range",
                    f"bytes */{len(data)}"),), b'{"error":"RANGE_DENIED"}')
            return BinaryResponse(200, "video/mp4", headers, data)
        except BridgeDenied:
            raise
        except (ValueError, KeyError, TypeError, OSError):
            raise BridgeDenied("INVALID_OR_UNAVAILABLE") from None
