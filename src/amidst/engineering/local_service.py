"""Indexed, frozen local-pilot tools; the Agent never receives file access."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from amidst.engineering.access import AccessDenied, SessionGuard, Tool, digest
from amidst.engineering.facade import (
    EventRequest,
    MediaRequest,
    QueryRequest,
    ReplayRequest,
    ResolveRequest,
    ToolFailure,
    ToolRequest,
)
from amidst.engineering.local_index import IndexRecord, RecordKind, ScopedLocalIndex, ScopedTopology
from amidst.engineering.registry import RegistryStore, ResourceScope, opaque_ref, scope_parts


class LocalPilotService:
    """All dictionaries and interval buckets are built at load, never in queries."""

    def __init__(
        self,
        store: RegistryStore,
        scope: ResourceScope,
        guard: SessionGuard,
        observations: tuple[dict[str, Any], ...],
        events: tuple[dict[str, Any], ...],
        topology: ScopedTopology,
    ) -> None:
        self.store, self.scope, self.guard = store, scope, guard
        binding = guard.binding
        if (
            binding.place_id,
            binding.model_id,
            binding.model_revision,
            binding.run_id,
            binding.clock_id,
            binding.spatial_context_id,
            binding.registry_sha256,
        ) != (
            scope.place_id,
            scope.model_id,
            scope.model_revision,
            scope.run_id,
            scope.clock_id,
            scope.spatial_context_id,
            store.registry.sha256,
        ):
            raise ToolFailure("SCOPE_DENIED")
        self.cameras = {c.camera_ref: c for c in store.list_cameras(scope)}
        self.frames = {f.media_ref: f for f in store.query_frames(scope)}
        self.observations = {o["observation_ref"]: o for o in observations}
        self.events = {e["event_ref"]: e for e in events}
        self.logs: list[dict[str, object]] = []
        rows: list[IndexRecord] = []
        self._record_links: dict[str, str] = {}
        for kind, records in (("observation", observations), ("event", events)):
            for record in records:
                ref = record[kind + "_ref"]
                start, end = record["time_range"]
                camera_refs = record["camera_refs"]
                if any(c not in self.cameras for c in camera_refs):
                    raise ToolFailure("REFERENCE_DENIED")
                if any(f not in self.frames for f in record["media_refs"]):
                    raise ToolFailure("REFERENCE_DENIED")
                for camera_ref in (*camera_refs, None):
                    index_ref = opaque_ref("indexed", ref, str(camera_ref))
                    self._record_links[index_ref] = ref
                    rows.append(
                        IndexRecord(
                            scope=scope,
                            record_ref=index_ref,
                            kind="OBSERVATION" if kind == "observation" else "EVENT",
                            camera_id=None
                            if camera_ref is None
                            else self.cameras[camera_ref].camera_id,
                            start_time=start,
                            end_time=end,
                            region_ids=tuple(record["region_ids"]) if camera_ref is None else (),
                            portal_refs=tuple(record.get("portal_ids", ()))
                            if camera_ref is None
                            else (),
                        )
                    )
        self.index = ScopedLocalIndex(tuple(rows), (topology,))
        self._place_names = {scope.place_id.casefold(), "lab", "合成實驗室", "local camera lab"}

    def context(self) -> dict[str, object]:
        return self.guard.context(tuple(self.cameras)).model_dump(mode="json")

    def _summary(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            k: v
            for k, v in record.items()
            if k
            not in {
                "projected_path",
                "candidates",
                "trajectories",
                "measurements",
            }
        }

    def call(self, tool: Tool, payload: object) -> dict[str, Any]:
        schemas: dict[Tool, type[ToolRequest]] = {
            "resolve_place": ResolveRequest,
            "list_cameras": ToolRequest,
            "query_observations": QueryRequest,
            "query_events": QueryRequest,
            "get_event_summary": EventRequest,
            "get_event_detail": EventRequest,
            "get_media": MediaRequest,
            "get_replay": ReplayRequest,
        }
        try:
            request = schemas[tool].model_validate(payload)
            self.guard.require(request.session_ref, tool)
            result = self._invoke(tool, request)
        except (AccessDenied, ToolFailure) as error:
            self.logs.append({"tool": tool, "stage": self.guard.stage, "status": str(error)})
            raise ToolFailure(str(error)) from None
        except (ValueError, KeyError, TypeError, OSError):
            self.logs.append(
                {"tool": tool, "stage": self.guard.stage, "status": "INVALID_OR_UNAVAILABLE"}
            )
            raise ToolFailure("INVALID_OR_UNAVAILABLE") from None
        self.logs.append(
            {
                "tool": tool,
                "stage": self.guard.stage,
                "status": "OK",
                "response_sha256": digest(result),
            }
        )
        return result

    def _invoke(self, tool: Tool, request: ToolRequest) -> dict[str, Any]:
        if tool == "resolve_place":
            assert isinstance(request, ResolveRequest)
            found = request.query.casefold() in self._place_names
            return {
                "scope": self.context(),
                "items": (
                    [
                        {
                            "place_id": self.scope.place_id,
                            "model_id": self.scope.model_id,
                            "resource_ref": opaque_ref("place", *scope_parts(self.scope)),
                        }
                    ]
                    if found
                    else []
                ),
                "complete": True,
            }
        if tool == "list_cameras":
            return {
                "scope": self.context(),
                "items": [
                    {
                        "camera_id": c.camera_id,
                        "camera_ref": c.camera_ref,
                        "coverage_status": c.coverage_status,
                        "region_ids": c.region_ids,
                        "origin": c.origin,
                        "authority": c.authority,
                    }
                    for c in self.cameras.values()
                ],
            }
        if tool in ("query_observations", "query_events"):
            assert isinstance(request, QueryRequest)
            if self.guard.stage == "INPUT" and request.region_id is not None:
                raise ToolFailure("STAGE_DENIED")
            if request.camera_ref is None and request.region_id is None:
                raise ToolFailure("LOCAL_ANCHOR_REQUIRED")
            if request.camera_ref is not None and request.camera_ref not in self.cameras:
                raise ToolFailure("SCOPE_DENIED")
            kind = "observation" if tool == "query_observations" else "event"
            query_kind: RecordKind = "OBSERVATION" if kind == "observation" else "EVENT"
            if request.camera_ref is not None:
                selected = self.index.camera_records(
                    self.scope,
                    self.cameras[request.camera_ref].camera_id,
                    *request.time_range,
                    kind=query_kind,
                    limit=128,
                )
            else:
                selected = self.index.region_records(
                    self.scope,
                    str(request.region_id),
                    *request.time_range,
                    kind=query_kind,
                    limit=128,
                )
            refs = tuple(self._record_links[row.record_ref] for row in selected.records)
            records = self.observations if kind == "observation" else self.events
            items = [records[ref] for ref in refs]
            if request.region_id is not None and request.camera_ref is not None:
                items = [row for row in items if request.region_id in row["region_ids"]]
            if kind == "event":
                items = [self._summary(row) for row in items]
            elif self.guard.stage == "INPUT":
                items = [
                    {
                        k: v
                        for k, v in row.items()
                        if k
                        not in {
                            "projected_path",
                            "region_ids",
                            "association_refs",
                        }
                    }
                    for row in items
                ]
            return {
                "scope": self.context(),
                "items": items,
                "retrieval": {
                    "records_read": selected.records_read,
                    "frames_read": 0,
                    "bytes_read": 0,
                    "index_entries_touched": selected.index_entries_touched,
                    "coverage": "EXACT_REGISTERED_BUCKET_WITHIN_WINDOW",
                    "time_range": request.time_range,
                    "truncated": selected.truncated,
                    "graph_complete": None,
                },
            }
        if tool == "get_media":
            assert isinstance(request, MediaRequest)
            frame = self.frames.get(request.media_ref)
            if frame is None:
                raise ToolFailure("REFERENCE_DENIED")
            data = self.store.media_bytes(self.scope, request.media_ref)
            return {
                "media_ref": frame.media_ref,
                "camera_id": frame.camera_id,
                "timestamp": frame.timestamp,
                "sha256": frame.sha256,
                "mime_type": frame.media_type,
                "evidence_state": "RGB_PIXELS",
                "base64": base64.b64encode(data).decode(),
                "bytes_read": len(data),
            }
        assert isinstance(request, EventRequest)
        record = self.events.get(request.event_ref)
        if record is None:
            raise ToolFailure("REFERENCE_DENIED")
        if tool == "get_event_summary":
            return self._summary(record)
        if tool == "get_event_detail":
            return record
        assert isinstance(request, ReplayRequest)
        start, end = record["time_range"]
        if not start <= request.timestamp <= end:
            raise ToolFailure("TIME_OUTSIDE_EVENT")
        return {
            "event_ref": request.event_ref,
            "timestamp": request.timestamp,
            "evidence_state": record["evidence_state"],
            "projected_path": record["projected_path"],
            "candidates": record["candidates"],
            "trajectories": record["trajectories"],
            "uncertainty": record["uncertainty"],
            "presentation_only": True,
            "candidate_order_preserved": True,
        }


def ui_path() -> Path:
    return Path(__file__).with_name("local_pilot.html")
