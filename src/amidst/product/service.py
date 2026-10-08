"""Guarded local product composition; reads never rerun inference or alter identities."""

from __future__ import annotations

from collections import deque
from typing import Any, Literal

from pydantic import Field

from amidst.domain.common import DomainModel, Timestamp
from amidst.engineering.access import TOOLS, AccessDenied, TaskContext, digest
from amidst.engineering.facade import (
    EventRequest,
    MediaRequest,
    QueryRequest,
    ReplayRequest,
    ResolveRequest,
    ToolFailure,
    ToolRequest,
)
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.registry import ResourceRef, opaque_ref
from amidst.product.appearance import AppearanceHit, AppearanceIndex, DescriptorBundle
from amidst.product.contracts import (
    CameraSummary,
    EventDetail,
    EventSummary,
    MediaResponse,
    ObservationDetail,
    PixelObservation,
    ProductContext,
)
from amidst.product.stitching import StitchBundle, StitchHypothesis
from amidst.product.store import ProductScope, RecordQuery, SQLiteProductStore

EXTRA_TOOLS = (
    "get_observation_detail", "query_reachable_cameras", "propose_feasible_trajectories",
    "search_person_appearance", "get_stitch_hypotheses",
)
PRODUCT_TOOLS = (*TOOLS, *EXTRA_TOOLS)


class ObservationRequest(ToolRequest):
    observation_ref: ResourceRef


class ReachRequest(ToolRequest):
    camera_ref: ResourceRef
    max_hops: int = Field(default=3, ge=0, le=8, strict=True)


class AppearanceRequest(QueryRequest):
    query_track_ref: ResourceRef
    top_k: int = Field(default=5, ge=1, le=32, strict=True)


class StitchRequest(ToolRequest):
    local_track_ref: ResourceRef


class PagedRequest(QueryRequest):
    cursor: str | None = Field(default=None, max_length=4096)
    limit: int = Field(default=128, ge=1, le=128, strict=True)


class ProposeRequest(PagedRequest):
    seed_refs: tuple[ResourceRef, ...] = ()


class PlaceItem(DomainModel):
    place_id: str
    model_id: str
    resource_ref: ResourceRef


class PlacePage(DomainModel):
    scope: TaskContext
    items: tuple[PlaceItem, ...]
    complete: bool


class CameraPage(DomainModel):
    scope: TaskContext
    items: tuple[CameraSummary, ...]


class PageInfo(DomainModel):
    records_read: int = Field(ge=0)
    frames_read: Literal[0] = 0
    bytes_read: Literal[0] = 0
    index_entries_touched: int = Field(ge=0)
    coverage: Literal["EXACT_REGISTERED_BUCKET_WITHIN_WINDOW"] = (
        "EXACT_REGISTERED_BUCKET_WITHIN_WINDOW"
    )
    time_range: tuple[Timestamp, Timestamp]
    truncated: bool
    graph_complete: None = None
    next_cursor: str | None
    record_set_receipt_sha256: str


class ObservationPage(DomainModel):
    scope: TaskContext
    items: tuple[PixelObservation | ObservationDetail, ...]
    retrieval: PageInfo


class EventPage(DomainModel):
    scope: TaskContext
    items: tuple[EventSummary, ...]
    retrieval: PageInfo


class ReachableCamera(DomainModel):
    camera_id: str
    camera_ref: ResourceRef
    hops: int = Field(ge=0)


class ReachablePage(DomainModel):
    scope: TaskContext
    items: tuple[ReachableCamera, ...]
    truncated: bool
    authority: Literal["SYNTHETIC_CONFIG"] = "SYNTHETIC_CONFIG"


class AppearancePage(DomainModel):
    scope: TaskContext
    query_track_ref: ResourceRef
    hits: tuple[AppearanceHit, ...]
    requested_top_k: int
    candidate_tracks_read: int
    eligible_tracks: int
    unavailable_track_refs: tuple[ResourceRef, ...]
    cutoff_tie_extension: int
    truncated: bool
    complete: bool
    source_inputs_complete: bool
    coverage: Literal["CALLER_ALLOWED_LOCAL_POOL_AND_WINDOW"]
    score_meaning: Literal["HANDCRAFTED_SIMILARITY_NOT_IDENTITY_PROBABILITY"]
    local_pool_truncated: bool


class StitchView(DomainModel):
    hypothesis_ref: ResourceRef
    kind: Literal["SHORT_GAP_RECOVERY", "OVERLAPPING_TRACKLETS", "UNMATCHED"]
    status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE", "UNMATCHED"]
    track_refs: tuple[ResourceRef, ...]
    camera_id: str
    time_range: tuple[Timestamp, Timestamp]
    observed_intervals: tuple[tuple[Timestamp, Timestamp], ...]
    missing_intervals: tuple[tuple[Timestamp, Timestamp], ...]
    missing_sample_timestamps: tuple[Timestamp, ...]
    gap_s: float | None
    contact_distance_px: float | None
    appearance_distance: float | None
    alternatives: tuple[ResourceRef, ...]
    reason: str
    authority: Literal["PROVISIONAL_PIXEL_STITCH_ONLY"]
    confirmed_identity: Literal[False]
    creates_observed_gap_samples: Literal[False]


class StitchPage(DomainModel):
    scope: TaskContext
    items: tuple[StitchView, ...]
    provisional_only: Literal[True] = True
    complete: bool


class ObservationResponse(ObservationDetail):
    scope: TaskContext


class SummaryResponse(EventSummary):
    scope: TaskContext


class DetailResponse(EventDetail):
    scope: TaskContext


def response_types() -> dict[str, type[DomainModel]]:
    from amidst.product.contracts import TimelineState
    return {
        "resolve_place": PlacePage, "list_cameras": CameraPage,
        "query_observations": ObservationPage, "query_events": EventPage,
        "propose_feasible_trajectories": EventPage,
        "get_observation_detail": ObservationResponse,
        "get_event_summary": SummaryResponse, "get_event_detail": DetailResponse,
        "get_media": MediaResponse, "get_replay": TimelineState,
        "query_reachable_cameras": ReachablePage, "search_person_appearance": AppearancePage,
        "get_stitch_hypotheses": StitchPage,
    }


class ProductService:
    def __init__(self, base: LocalPilotService, repository: SQLiteProductStore,
                 scope: ProductScope, descriptors: DescriptorBundle, *,
                 product_freeze_ref: str, stitches: dict[str, object]) -> None:
        self.base, self.repository, self.scope = base, repository, scope
        self.descriptors = DescriptorBundle.model_validate_json(descriptors.model_dump_json())
        self.appearance = AppearanceIndex(self.descriptors)
        self.stitches = StitchBundle.model_validate(stitches)
        self.product_freeze_ref = product_freeze_ref
        self.logs: list[dict[str, object]] = []
        if (scope.resource_scope != base.scope or scope.observation_mode !=
            base.guard.binding.observation_mode or repository.get_scope(scope.run_ref) != scope
            or descriptors.scope != base.scope
            or descriptors.dataset_sha256 != scope.dataset_sha256
            or descriptors.producer_sha256 != scope.producer_sha256
            or descriptors.registry_sha256 != scope.registry_sha256
            or descriptors.input_config_sha256 != base.guard.binding.config_sha256
            or scope.media_sha256 != base.guard.binding.media_sha256
            or descriptors.media_sha256 != digest([
                (f.media_ref, f.sha256) for f in base.store.query_frames(base.scope)])
            or self.stitches.scope != base.scope
            or self.stitches.dataset_sha256 != descriptors.dataset_sha256
            or self.stitches.producer_sha256 != descriptors.producer_sha256
            or self.stitches.perception_sha256 != descriptors.perception_sha256
            or self.stitches.appearance_sha256 != digest(descriptors)):
            raise ToolFailure("PRODUCT_BINDING_DENIED")
        repository.verify_run(scope.run_ref)
        # Validate every source dictionary once before it can be summarized or exported.
        for record in base.observations.values():
            ObservationDetail.model_validate(record)
        for record in base.events.values():
            EventDetail.model_validate(record)
        self._events_by_track: dict[str, list[str]] = {}
        for ref, raw in base.events.items():
            event = EventDetail.model_validate(raw)
            for track in event.local_track_refs:
                self._events_by_track.setdefault(track, []).append(ref)

    def context(self) -> ProductContext:
        allowed: tuple[str, ...] = tuple(self.base.guard.allowed_tools())
        if self.base.guard.stage == "RESULTS":
            allowed += EXTRA_TOOLS
        return ProductContext(session_ref=self.base.guard.session_ref, run_ref=self.scope.run_ref,
                              context=self.base.guard.context(tuple(self.base.cameras)),
                              product_freeze_ref=self.product_freeze_ref, allowed_tools=allowed,
                              operator_ref=opaque_ref("operator", self.scope.run_ref,
                                                      "local-operator-v1"))

    def _guard(self, request: ToolRequest, tool: str) -> None:
        if request.session_ref != self.base.guard.session_ref:
            raise ToolFailure("SCOPE_DENIED")
        if tool not in self.context().allowed_tools:
            raise ToolFailure("STAGE_DENIED")

    def call(self, tool: str, payload: object) -> dict[str, Any]:
        schemas: dict[str, type[ToolRequest]] = {
            "resolve_place": ResolveRequest, "list_cameras": ToolRequest,
            "query_observations": PagedRequest, "query_events": PagedRequest,
            "get_event_summary": EventRequest, "get_event_detail": EventRequest,
            "get_media": MediaRequest, "get_replay": ReplayRequest,
            "get_observation_detail": ObservationRequest,
            "query_reachable_cameras": ReachRequest,
            "propose_feasible_trajectories": ProposeRequest,
            "search_person_appearance": AppearanceRequest,
            "get_stitch_hypotheses": StitchRequest,
        }
        if tool not in schemas:
            self.logs.append({"tool": "UNKNOWN_TOOL", "status": "TOOL_DENIED"})
            raise ToolFailure("TOOL_DENIED")
        try:
            request = schemas[tool].model_validate(payload)
            self._guard(request, tool)
            response = response_types()[tool].model_validate(
                self._invoke(tool, request)).model_dump(mode="json")
        except (ToolFailure, AccessDenied) as error:
            self.logs.append({"tool": tool, "stage": self.base.guard.stage,
                              "status": str(error)})
            raise ToolFailure(str(error)) from None
        except (ValueError, TypeError, KeyError, OSError):
            self.logs.append({"tool": tool, "stage": self.base.guard.stage,
                              "status": "INVALID_OR_UNAVAILABLE"})
            raise ToolFailure("INVALID_OR_UNAVAILABLE") from None
        self.logs.append({"tool": tool, "stage": self.base.guard.stage,
                          "status": "OK", "response_sha256": digest(response)})
        return response

    def _invoke(self, tool: str, request: ToolRequest) -> dict[str, Any]:
        context = self.base.guard.context(tuple(self.base.cameras))
        if tool == "resolve_place":
            raw = self.base.call("resolve_place", request.model_dump(mode="json"))
            return PlacePage.model_validate(raw).model_dump(mode="json")
        if tool == "list_cameras":
            raw = self.base.call("list_cameras", request.model_dump(mode="json"))
            return CameraPage.model_validate(raw).model_dump(mode="json")
        if tool in ("query_observations", "query_events", "propose_feasible_trajectories"):
            assert isinstance(request, QueryRequest)
            if request.region_id is not None and self.base.guard.stage == "INPUT":
                raise ToolFailure("STAGE_DENIED")
            camera_id = self._camera(request.camera_ref)
            if camera_id is None and request.region_id is None:
                raise ToolFailure("LOCAL_ANCHOR_REQUIRED")
            if request.region_id is not None and request.region_id not in {
                region for camera in self.base.cameras.values() for region in camera.region_ids
            }:
                raise ToolFailure("REFERENCE_DENIED")
            kind: Literal["OBSERVATION", "EVENT"] = (
                "OBSERVATION" if tool == "query_observations" else "EVENT")
            selected_refs: tuple[str, ...] | None = None
            if isinstance(request, ProposeRequest) and request.seed_refs:
                tracks = self._seed_tracks(request.seed_refs)
                selected_refs = tuple(sorted({ref for track in tracks
                                             for ref in self._events_by_track.get(track, ())}))
            page = self.repository.query_records(RecordQuery(
                run_ref=self.scope.run_ref, kind=kind, camera_id=camera_id,
                time_range=request.time_range, region_id=request.region_id,
                limit=request.limit if isinstance(request, PagedRequest) else 128,
                cursor=request.cursor if isinstance(request, PagedRequest) else None,
                record_refs=selected_refs,
            ))
            info = PageInfo(records_read=len(page.records), index_entries_touched=len(page.records),
                            time_range=request.time_range, truncated=not page.query_complete,
                            next_cursor=page.next_cursor,
                            record_set_receipt_sha256=page.record_set_receipt_sha256)
            if kind == "OBSERVATION":
                observations: list[PixelObservation | ObservationDetail] = []
                for record in page.records:
                    value = ObservationDetail.model_validate(record.payload)
                    if self.base.guard.stage == "INPUT":
                        pixels = value.model_dump(mode="json", exclude={"region_ids",
                                                                       "projected_path"})
                        observations.append(PixelObservation.model_validate(pixels))
                    else:
                        observations.append(value)
                return ObservationPage(scope=context, items=tuple(observations),
                                       retrieval=info).model_dump(mode="json")
            events = [self._summary(EventDetail.model_validate(row.payload))
                      for row in page.records]
            return EventPage(scope=context, items=tuple(events), retrieval=info).model_dump(
                mode="json")
        if tool == "get_observation_detail":
            assert isinstance(request, ObservationRequest)
            record = self.repository.get_record(self.scope.run_ref, "OBSERVATION",
                                                request.observation_ref)
            if record is None:
                raise ToolFailure("REFERENCE_DENIED")
            value = ObservationDetail.model_validate(record.payload)
            return {"scope": context.model_dump(mode="json"), **value.model_dump(mode="json")}
        if tool == "query_reachable_cameras":
            assert isinstance(request, ReachRequest)
            camera_id = self._camera(request.camera_ref)
            assert camera_id is not None
            topology = self.base.index.topology(self.base.scope)
            adjacency: dict[str, list[str]] = {}
            for link in topology.camera_links:
                adjacency.setdefault(link.from_camera_id, []).append(link.to_camera_id)
            queue = deque([(camera_id, 0)])
            visited = {camera_id}
            items = []
            while queue:
                camera, hops = queue.popleft()
                registered = next(c for c in self.base.cameras.values() if c.camera_id == camera)
                items.append(ReachableCamera(camera_id=camera, camera_ref=registered.camera_ref,
                                             hops=hops))
                if hops == request.max_hops:
                    continue
                for neighbor in sorted(adjacency.get(camera, [])):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, hops + 1))
            return ReachablePage(scope=context, items=tuple(items), truncated=False).model_dump(
                mode="json")
        if tool == "search_person_appearance":
            assert isinstance(request, AppearanceRequest)
            camera_id = self._camera(request.camera_ref)
            if camera_id is None:
                raise ToolFailure("LOCAL_ANCHOR_REQUIRED")
            page = self.repository.query_records(RecordQuery(
                run_ref=self.scope.run_ref, kind="OBSERVATION", camera_id=camera_id,
                time_range=request.time_range, region_id=request.region_id, limit=128,
            ))
            allowed = tuple(ObservationDetail.model_validate(r.payload).local_track_ref
                            for r in page.records)
            result = self.appearance.search(
                request.query_track_ref, scope=self.scope.resource_scope,
                allowed_track_refs=allowed, camera_id=camera_id,
                time_range=request.time_range, top_k=request.top_k)
            exported = result.model_dump(mode="json", exclude={"scope"})
            return AppearancePage.model_validate({"scope": context.model_dump(mode="json"),
                **exported, "local_pool_truncated": not page.query_complete}).model_dump(
                    mode="json")
        if tool == "get_stitch_hypotheses":
            assert isinstance(request, StitchRequest)
            if request.local_track_ref not in {
                t.track_ref for t in self.descriptors.track_descriptors
            }:
                raise ToolFailure("REFERENCE_DENIED")
            bundle = StitchBundle.model_validate_json(self.stitches.model_dump_json())
            # A separate stitch view; canonical observations and events stay immutable.
            selected = [self._stitch_view(h) for h in bundle.hypotheses
                        if request.local_track_ref in h.track_refs]
            return StitchPage(scope=context, items=tuple(selected),
                              complete=bundle.complete).model_dump(mode="json")
        if tool == "get_media":
            assert isinstance(request, MediaRequest)
            frame = self.base.frames.get(request.media_ref)
            if frame is None or frame.purpose != "RGB_SEQUENCE" or frame.annotations != "NONE":
                raise ToolFailure("REFERENCE_DENIED")
            return MediaResponse.model_validate(self.base.call(
                "get_media", request.model_dump(mode="json"))).model_dump(mode="json")
        assert isinstance(request, EventRequest)
        record = self.repository.get_record(self.scope.run_ref, "EVENT", request.event_ref)
        if record is None:
            raise ToolFailure("REFERENCE_DENIED")
        event = EventDetail.model_validate(record.payload)
        if tool == "get_event_summary":
            return {"scope": context.model_dump(mode="json"),
                    **self._summary(event).model_dump(mode="json")}
        if tool == "get_event_detail":
            return {"scope": context.model_dump(mode="json"), **event.model_dump(mode="json")}
        assert isinstance(request, ReplayRequest)
        if not event.time_range[0] <= request.timestamp <= event.time_range[1]:
            raise ToolFailure("TIME_OUTSIDE_EVENT")
        from amidst.product.timeline import timeline_state
        return timeline_state(self.scope.run_ref, request.timestamp,
                              tuple(self.base.frames.values()), (event,)).model_dump(mode="json")

    @staticmethod
    def _summary(event: EventDetail) -> EventSummary:
        return EventSummary.model_validate(event.model_dump(mode="json", exclude={
            "projected_path", "candidates", "trajectories"}))

    def _camera(self, ref: str | None) -> str | None:
        if ref is None:
            return None
        camera = self.base.cameras.get(ref)
        if camera is None:
            raise ToolFailure("SCOPE_DENIED")
        return camera.camera_id

    @staticmethod
    def _stitch_view(hypothesis: StitchHypothesis) -> StitchView:
        return StitchView.model_validate(hypothesis.model_dump(mode="json", exclude={
            "original_track_ids", "original_observation_ids"}))

    def _seed_tracks(self, refs: tuple[str, ...]) -> set[str]:
        tracks = {t.track_ref for t in self.descriptors.track_descriptors}
        selected = set()
        for ref in refs:
            if ref in tracks:
                selected.add(ref)
            else:
                record = self.repository.get_record(self.scope.run_ref, "OBSERVATION", ref)
                if record is None:
                    raise ToolFailure("REFERENCE_DENIED")
                selected.add(ObservationDetail.model_validate(record.payload).local_track_ref)
        return selected
