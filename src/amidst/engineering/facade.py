"""Typed allowlisted local tools over fixed snapshots; no legacy API forwarding."""

from __future__ import annotations

import base64
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from amidst.domain.common import DomainModel, Timestamp
from amidst.domain.trajectory import CandidateTrajectory, TrajectoryHypothesis
from amidst.engineering.access import SessionGuard, Tool
from amidst.engineering.registry import RegistryStore, ResourceRef, ResourceScope, opaque_ref
from amidst.integration.consumer import replay_frame
from amidst.integration.repositories import RepositorySnapshot


class ToolRequest(DomainModel):
    session_ref: str


class ResolveRequest(ToolRequest):
    query: str = Field(min_length=1, max_length=160)


class QueryRequest(ToolRequest):
    time_range: tuple[Timestamp, Timestamp]
    camera_ref: ResourceRef | None = None
    region_id: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator("time_range", mode="before")
    @classmethod
    def numeric_times(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)) or any(isinstance(v, bool) for v in value):
            raise ValueError("numeric configured timestamps required")
        return value

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("invalid time range")
        return self


class EventRequest(ToolRequest):
    event_ref: ResourceRef


class MediaRequest(ToolRequest):
    media_ref: ResourceRef


class ReplayRequest(EventRequest):
    timestamp: Timestamp


class MeasurementView(DomainModel):
    measurement_ref: ResourceRef
    frame_ref: ResourceRef
    timestamp: Timestamp
    bbox: tuple[float, float, float, float]
    point_2d: tuple[float, float]
    visible_features: tuple[float, ...]


class ObservationView(DomainModel):
    observation_ref: ResourceRef
    canonical_observation_id: str
    local_track_ref: ResourceRef
    camera_id: str
    camera_ref: ResourceRef
    time_range: tuple[Timestamp, Timestamp]
    evidence_refs: tuple[ResourceRef, ...]
    media_refs: tuple[ResourceRef, ...]
    measurements: tuple[MeasurementView, ...]
    projected_positions: tuple[tuple[float, float, float], ...] = ()
    region_ids: tuple[str, ...] = ()
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["CONFIGURED_ENGINEERING_ONLY"] = "CONFIGURED_ENGINEERING_ONLY"
    image_measurement: Literal[True] = True
    producer_version: str
    uncertainty: str


class EventView(DomainModel):
    event_ref: ResourceRef
    association_ref: ResourceRef
    canonical_event_id: str | None
    kind: str
    camera_ids: tuple[str, ...]
    camera_refs: tuple[ResourceRef, ...]
    time_range: tuple[Timestamp, Timestamp]
    observation_refs: tuple[ResourceRef, ...]
    evidence_refs: tuple[ResourceRef, ...]
    media_refs: tuple[ResourceRef, ...]
    region_ids: tuple[str, ...]
    candidate_count: int = Field(ge=0)
    hypothesis_count: int = Field(ge=0)
    association_hypothesis_count: int = Field(ge=0)
    termination_reason: str
    complete: bool | None
    uncertainty: str
    detail_ref: ResourceRef
    replay_ref: ResourceRef | None
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["CONFIGURED_ENGINEERING_ONLY"] = "CONFIGURED_ENGINEERING_ONLY"


class EventDetail(DomainModel):
    summary: EventView
    provisional_association_ref: ResourceRef
    original_observation_refs: tuple[ResourceRef, ...]
    canonical_endpoint_ids: tuple[str, ...]
    candidates: tuple[CandidateTrajectory, ...]
    hypotheses: tuple[TrajectoryHypothesis, ...]
    replay_ref: ResourceRef | None


class ToolFailure(ValueError):
    """Fixed safe failure code; raw validation errors never leave the service."""


class AgentFacade:
    """One scope and one server-owned session; GET/read tools never infer."""

    def __init__(self, store: RegistryStore, scope: ResourceScope, guard: SessionGuard,
                 snapshot: RepositorySnapshot, observations: tuple[ObservationView, ...],
                 events: tuple[EventView, ...]) -> None:
        self.store, self.scope, self.guard = store, scope, guard
        self.snapshot = RepositorySnapshot.model_validate(snapshot.model_dump())
        self.observations, self.events = observations, events
        self.logs: list[dict[str, object]] = []
        binding = guard.binding
        if (binding.place_id, binding.model_id, binding.model_revision, binding.run_id,
            binding.clock_id, binding.spatial_context_id) != (
                scope.place_id, scope.model_id, scope.model_revision, scope.run_id,
                scope.clock_id, scope.spatial_context_id):
            raise ToolFailure("SCOPE_DENIED")
        self.cameras = store.list_cameras(scope)
        if (binding.registry_sha256 != store.registry.sha256
            or binding.source_ref != opaque_ref("source", scope.source_id, scope.source_sha256)):
            raise ToolFailure("SOURCE_DENIED")
        self.frames = tuple(f for f in store.query_frames(scope)
                            if f.purpose == "RGB_SEQUENCE" and f.annotations == "NONE")
        known_refs = {c.camera_ref for c in self.cameras}
        known_media = {f.media_ref for f in self.frames}
        if any(o.camera_ref not in known_refs or not set(o.media_refs) <= known_media
               for o in observations) or any(
                   not set(e.camera_refs) <= known_refs or not set(e.media_refs) <= known_media
                   for e in events):
            raise ToolFailure("REFERENCE_DENIED")

    def context(self) -> dict[str, object]:
        return self.guard.context(tuple(c.camera_ref for c in self.cameras)).model_dump(mode="json")

    def _query(self, request: QueryRequest) -> str | None:
        if request.camera_ref is None:
            return None
        for camera in self.cameras:
            if camera.camera_ref == request.camera_ref:
                return camera.camera_id
        raise ToolFailure("REFERENCE_DENIED")

    def _event(self, ref: str) -> EventView:
        for event in self.events:
            if event.event_ref == ref:
                return event
        raise ToolFailure("REFERENCE_UNAVAILABLE")

    def invoke(self, tool: Tool, payload: object) -> dict[str, object]:
        from amidst.engineering.access import TOOLS, AccessDenied, digest
        from amidst.engineering.dto import RESPONSE_TYPES

        if tool not in TOOLS:
            self.logs.append({"tool": "UNKNOWN_TOOL", "stage": self.guard.stage,
                              "status": "TOOL_DENIED"})
            raise ToolFailure("TOOL_DENIED")

        schemas: dict[Tool, type[ToolRequest]] = {
            "resolve_place": ResolveRequest, "list_cameras": ToolRequest,
            "query_observations": QueryRequest, "query_events": QueryRequest,
            "get_event_summary": EventRequest, "get_event_detail": EventRequest,
            "get_media": MediaRequest, "get_replay": ReplayRequest,
        }
        try:
            request = schemas[tool].model_validate(payload)
            self.guard.require(request.session_ref, tool)
            result = RESPONSE_TYPES[tool].model_validate(self._invoke(tool, request))
            exported = result.model_dump(mode="json")
        except (AccessDenied, ToolFailure) as error:
            code = str(error)
            self.logs.append({"tool": tool, "stage": self.guard.stage, "status": code})
            raise ToolFailure(code) from None
        except (ValueError, KeyError, OSError, TypeError):
            self.logs.append({"tool": tool, "stage": self.guard.stage,
                              "status": "INVALID_OR_UNAVAILABLE"})
            raise ToolFailure("INVALID_OR_UNAVAILABLE") from None
        self.logs.append({"tool": tool, "stage": self.guard.stage, "status": "OK",
                          "response_sha256": digest(exported)})
        return exported

    def _invoke(self, tool: Tool, request: ToolRequest) -> dict[str, object]:
        if tool == "resolve_place":
            assert isinstance(request, ResolveRequest)
            matches = tuple(m for m in self.store.resolve_place(request.query)
                            if m.scope == self.scope)
            return {"scope": self.context(),
                    "items": [{"place_id": m.scope.place_id, "display_name": m.display_name,
                               "model_id": m.scope.model_id,
                               "model_revision": m.scope.model_revision,
                               "resource_ref": opaque_ref("place", m.scope.place_id,
                                                          m.scope.model_id)} for m in matches],
                    "ambiguous": len(matches) > 1}
        if tool == "list_cameras":
            return {"scope": self.context(), "items": [{
                "camera_id": c.camera_id, "camera_ref": c.camera_ref,
                "group_ids": c.group_ids, "coverage_status": c.coverage_status,
                "region_ids": c.region_ids, "origin": c.origin, "authority": c.authority,
                "media_refs": [f.media_ref for f in self.frames if f.camera_id == c.camera_id],
                "frames": [{"media_ref": f.media_ref, "frame_id": f.frame_id,
                            "timestamp": f.timestamp} for f in self.frames
                           if f.camera_id == c.camera_id],
                "time_range": self._camera_extent(c.camera_id),
            } for c in self.cameras]}
        if tool in ("query_events", "query_observations"):
            assert isinstance(request, QueryRequest)
            if self.guard.stage == "INPUT" and request.region_id is not None:
                raise ToolFailure("STAGE_DENIED")
            camera_id = self._query(request)
            if request.region_id is not None and request.region_id not in {
                r for c in self.cameras for r in c.region_ids
            }:
                raise ToolFailure("REFERENCE_DENIED")
            if tool == "query_events":
                event_items = [e.model_dump(mode="json") for e in self.events
                               if (camera_id is None or camera_id in e.camera_ids)
                               and self._overlap(e.time_range, request.time_range)
                               and (request.region_id is None or request.region_id in e.region_ids)]
                return {"scope": self.context(), "items": event_items,
                        "association_hypothesis_count": len(self.events)}
            items = []
            for observation in self.observations:
                if (camera_id is None or camera_id == observation.camera_id) and self._overlap(
                    observation.time_range, request.time_range,
                ) and (request.region_id is None or request.region_id in observation.region_ids):
                    value = observation.model_dump(mode="json")
                    if self.guard.stage == "INPUT":
                        value.pop("projected_positions")
                        value.pop("region_ids")
                    items.append(value)
            return {"scope": self.context(), "items": items}
        if tool == "get_media":
            assert isinstance(request, MediaRequest)
            if request.media_ref not in {f.media_ref for f in self.frames}:
                raise ToolFailure("REFERENCE_DENIED")
            frame = self.store.get_frame(self.scope, request.media_ref)
            data = self.store.media_bytes(self.scope, request.media_ref)
            return {"scope": self.context(), "media_ref": frame.media_ref,
                    "camera_ref": frame.camera_ref,
                    "camera_id": frame.camera_id, "frame_id": frame.frame_id,
                    "timestamp": frame.timestamp, "input_sha256": frame.sha256,
                    "origin": "SYNTHETIC", "annotations": "NONE",
                    "mime_type": frame.media_type,
                    "content_base64": base64.b64encode(data).decode("ascii")}
        assert isinstance(request, EventRequest)
        event = self._event(request.event_ref)
        if tool == "get_event_summary":
            return {"scope": self.context(), **event.model_dump(mode="json")}
        gap = next((g for g in self.snapshot.gaps
                    if g.event.event_id == event.canonical_event_id), None)
        if tool == "get_event_detail":
            detail = EventDetail(
                summary=event, provisional_association_ref=event.association_ref,
                original_observation_refs=event.observation_refs,
                canonical_endpoint_ids=() if gap is None else gap.event.observation_ids,
                candidates=() if gap is None else gap.event.candidates,
                hypotheses=() if gap is None else gap.event.trajectories,
                replay_ref=event.replay_ref,
            ).model_dump(mode="json")
            return {"scope": self.context(), **detail}
        assert isinstance(request, ReplayRequest)
        if gap is None or event.replay_ref is None:
            raise ToolFailure("REPLAY_UNAVAILABLE")
        return {"scope": self.context(), "replay_ref": event.replay_ref,
                **replay_frame(gap, request.timestamp).model_dump(mode="json")}

    def _camera_extent(self, camera_id: str) -> tuple[float, float] | None:
        times = [f.timestamp for f in self.frames if f.camera_id == camera_id]
        return (min(times), max(times)) if times else None

    @staticmethod
    def _overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
        return a[0] <= b[1] and a[1] >= b[0]
