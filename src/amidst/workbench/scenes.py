"""Read-only adapters for existing, frozen engineering scene materializations.

Import validates the original source locks and builds scoped indexes once. No
renderer, producer, truth export or original Blender asset is opened by this
module. Human annotations are overlays owned by the separate review store.
"""

from __future__ import annotations

import copy
import json
import math
from bisect import bisect_left
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from amidst.engineering.association import SyntheticStaticContext
from amidst.engineering.local_behavior import BehaviorConfig
from amidst.engineering.local_index import CameraLink, CameraRegions, ScopedTopology
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.registry import CameraEntry, MediaFrame

Json = dict[str, Any]


def _polygon(bounds: Sequence[float], z: float = 0.0) -> Json:
    x0, y0, x1, y1 = bounds
    return {"type": "polygon", "points": [[x0, y0, z], [x1, y0, z],
                                           [x1, y1, z], [x0, y1, z]]}


def _camera(camera: CameraEntry) -> Json:
    """Affine-only sources have no recoverable physical camera pose."""
    calibration = camera.calibration
    if calibration is not None:
        matrix = calibration.camera_to_world
        position: list[float] | None = [matrix[i][3] for i in range(3)]
        props = {"calibration_kind": "PINHOLE", "position": position,
                 "camera_to_world": [list(row) for row in matrix],
                 "fx": calibration.fx, "fy": calibration.fy,
                 "cx": calibration.cx, "cy": calibration.cy,
                 "width": calibration.width, "height": calibration.height,
                 "convention": calibration.convention}
    elif camera.affine_calibration is not None:
        affine = camera.affine_calibration
        position = None
        props = {"calibration_kind": affine.calibration_kind, "position": None,
                 "ground_to_pixel": [list(row) for row in affine.ground_to_pixel],
                 "plane_z_m": affine.plane_z_m, "width": affine.width,
                 "height": affine.height, "physical_pose_status": "UNKNOWN"}
    else:
        position = None
        props = {"calibration_kind": "UNAVAILABLE", "position": None,
                 "physical_pose_status": "UNKNOWN"}
    return {"camera_id": camera.camera_id, "camera_ref": camera.camera_ref,
            "label": camera.camera_id, "position": position,
            "coverage_status": camera.coverage_status,
            "region_ids": list(camera.region_ids), "authority": camera.authority,
            "calibration_sha256": camera.calibration_sha256, "properties": props}


def baseline_objects(context: SyntheticStaticContext, cameras: Sequence[CameraEntry],
                     behavior: BehaviorConfig | None = None) -> list[Json]:
    """Selectable geometry is drawn only from validated static source authority."""
    z = context.ground_plane.point[2]
    objects: list[Json] = [{
        "object_id": "walkable:" + context.ground_plane.plane_id, "kind": "WALKABLE",
        "label": "Configured walkable plane", "semantic": "WALKABLE",
        "geometry": _polygon(context.walkable_bounds_xy_m, z),
        "properties": {"floor_id": context.ground_plane.floor_id, "plane_z_m": z},
        "editable_fields": ["label", "semantic", "geometry", "properties"],
        "authority": "SYNTHETIC_CONFIG",
    }]
    for region in context.regions:
        objects.append({
            "object_id": "region:" + region.region_id, "kind": "REGION",
            "label": region.region_id, "semantic": "REGION",
            "geometry": _polygon(region.bounds_xy_m, z),
            "properties": {"region_id": region.region_id, "floor_id": region.floor_id},
            "editable_fields": ["label", "semantic", "geometry", "properties"],
            "authority": "SYNTHETIC_CONFIG",
        })
    if behavior is not None:
        for portal in behavior.portals:
            objects.append({
                "object_id": "portal:" + portal.portal_id, "kind": "PORTAL",
                "label": portal.portal_id, "semantic": "DOOR",
                "geometry": {"type": "line", "points": [[x, y, z]
                             for x, y in portal.line_xy_m]},
                "properties": {"inside_region_id": portal.inside_region_id,
                               "outside_region_id": portal.outside_region_id,
                               "enter_normal_xy": list(portal.enter_normal_xy)},
                "editable_fields": ["label", "semantic", "geometry", "properties"],
                "authority": behavior.authority,
            })
    for entry in cameras:
        camera = _camera(entry)
        objects.append({
            "object_id": "camera:" + entry.camera_id, "kind": "CAMERA",
            "label": entry.camera_id, "semantic": "CAMERA",
            "geometry": {"type": "point", "points": [] if camera["position"] is None
                         else [camera["position"]]},
            "properties": camera["properties"],
            "editable_fields": ["label", "properties"] if camera["position"] is None
                               else ["label", "geometry", "properties"],
            "authority": entry.authority,
        })
    return objects


class SceneAdapter:
    """A common desktop view over one immutable model/run with indexed access."""

    def __init__(self, *, scene_id: str, label: str, description: str,
                 service: LocalPilotService, context: SyntheticStaticContext,
                 evidence_level: str, evaluation_path: Path | None = None,
                 behavior: BehaviorConfig | None = None,
                 evaluation_config_hash: str | None = None,
                 evaluation_freeze_hashes: Mapping[str, str] | None = None) -> None:
        if (context.source_sha256 != service.scope.source_sha256
                or context.context_sha256 != service.scope.spatial_context_sha256):
            raise ValueError("SCENE_SOURCE_MISMATCH")
        self.scene_id, self.label, self.description = scene_id, label, description
        self.source_hash = service.scope.source_sha256
        self.model_revision = service.scope.model_revision
        self.run_id = service.scope.run_id
        self.service = service
        self._evaluation_path = evaluation_path
        self._evaluation_config_hash = evaluation_config_hash or service.guard.binding.config_sha256
        self._evaluation_freeze_hashes = dict(evaluation_freeze_hashes or {})
        self._cameras = {camera.camera_id: camera for camera in service.cameras.values()}
        self._frame_buckets: dict[str, tuple[MediaFrame, ...]] = {}
        self._frame_times: dict[str, tuple[float, ...]] = {}
        self._frame_steps: dict[str, float] = {}
        for camera_id in self._cameras:
            frames = tuple(sorted((f for f in service.frames.values()
                                   if f.camera_id == camera_id), key=lambda f: f.timestamp))
            self._frame_buckets[camera_id] = frames
            self._frame_times[camera_id] = tuple(f.timestamp for f in frames)
            differences = [b.timestamp - a.timestamp
                           for a, b in zip(frames, frames[1:], strict=False)
                           if b.timestamp > a.timestamp]
            self._frame_steps[camera_id] = min(differences, default=0.0)
        times = [f.timestamp for f in service.frames.values()]
        model = next(m for m in service.store.registry.models if m.scope == service.scope)
        self._snapshot: Json = {
            "scene_id": scene_id, "label": label, "description": description,
            "model_id": service.scope.model_id, "model_revision": self.model_revision,
            "run_id": self.run_id, "source_hash": self.source_hash,
            "source_ref": service.guard.binding.source_ref,
            "config_sha256": service.guard.binding.config_sha256,
            "registry_sha256": service.store.registry.sha256,
            "freeze_ref": service.context().get("freeze_ref"),
            "clock": model.clock.model_dump(mode="json"),
            "coordinates": model.coordinates.model_dump(mode="json"),
            "evidence_level": evidence_level, "origin": "SYNTHETIC",
            "authority": "CONFIGURED_ENGINEERING_ONLY", "formal_phase1_acceptance": False,
            "capabilities": {
                "images": bool(times), "video": False, "local_3d": True,
                "camera_pose": all(c.calibration is not None for c in self._cameras.values()),
                "events": bool(service.events), "scene_review": True, "result_review": True,
                "evaluation": evaluation_path is not None and evaluation_path.is_file(),
                "inference_execution": False,
            },
            "bounds": list(context.walkable_bounds_xy_m),
            "time_range": [min(times), max(times)] if times else [0, 0],
            "cameras": [_camera(c) for c in self._cameras.values()],
            "objects": baseline_objects(context, tuple(self._cameras.values()), behavior),
            "counts": {"cameras": len(self._cameras), "frames": len(times),
                       "observations": len(service.observations), "events": len(service.events)},
            "limitations": ["Synthetic configured scene; provisional identities and events.",
                            "Reviewed annotations are versioned overlays; frozen outputs retain "
                            "their original config and require an explicit rerun after edits."],
        }

    def summary(self) -> Json:
        return copy.deepcopy({key: value for key, value in self._snapshot.items()
                              if key not in {"objects", "cameras"}})

    def with_display_identity(self, scene_id: str, label: str, description: str) -> SceneAdapter:
        """Server catalog aliases change display metadata, never the frozen source scope."""
        scene = copy.copy(self)
        scene.scene_id, scene.label, scene.description = scene_id, label, description
        scene._snapshot = copy.deepcopy(self._snapshot)
        scene._snapshot.update({"scene_id": scene_id, "label": label, "description": description})
        return scene

    def snapshot(self) -> Json:
        return copy.deepcopy(self._snapshot)

    def query(self, camera_id: str, start: float, end: float) -> Json:
        camera = self._cameras.get(camera_id)
        if camera is None:
            raise ValueError("CAMERA_SCOPE_DENIED")
        if not math.isfinite(start) or not math.isfinite(end) or start < 0 or end < start:
            raise ValueError("INVALID_TIME_RANGE")
        request = {"session_ref": self.service.guard.session_ref,
                   "camera_ref": camera.camera_ref, "time_range": [start, end]}
        events = self.service.call("query_events", request)
        observations = self.service.call("query_observations", request)
        receipts = [events["retrieval"], observations["retrieval"]]
        totals = {key: sum(receipt[key] for receipt in receipts)
                  for key in ("records_read", "index_entries_touched", "frames_read", "bytes_read")}
        return copy.deepcopy({
            "events": events["items"], "observations": observations["items"],
            "retrieval": {**totals, "events": events["retrieval"],
                          "observations": observations["retrieval"],
                          "truncated": any(receipt["truncated"] for receipt in receipts),
                          "time_range": [start, end], "import_built_index": True,
                          "global_scan": False}})

    def event(self, ref: str) -> Json:
        return copy.deepcopy(self.service.call("get_event_detail", {
            "session_ref": self.service.guard.session_ref, "event_ref": ref}))

    def media(self, ref: str) -> tuple[str, bytes]:
        frame = self.service.frames.get(ref)
        if frame is None:
            raise ValueError("MEDIA_SCOPE_DENIED")
        return frame.media_type, self.service.store.media_bytes(self.service.scope, ref)

    def frames(self, camera_ids: Sequence[str], timestamp: float) -> Json:
        if not math.isfinite(timestamp) or timestamp < 0 or len(camera_ids) > 8:
            raise ValueError("INVALID_FRAME_WINDOW")
        if len(set(camera_ids)) != len(camera_ids) or any(c not in self._cameras
                                                         for c in camera_ids):
            raise ValueError("CAMERA_SCOPE_DENIED")
        result = []
        for camera_id in camera_ids:
            times = self._frame_times[camera_id]
            selected: MediaFrame | None = None
            if times and times[0] <= timestamp <= times[-1]:
                i = bisect_left(times, timestamp)
                nearby = [j for j in (i - 1, i) if 0 <= j < len(times)]
                best = min(nearby, key=lambda j: (abs(times[j] - timestamp), times[j]))
                if abs(times[best] - timestamp) <= self._frame_steps[camera_id] * 0.51:
                    selected = self._frame_buckets[camera_id][best]
            result.append({"camera_id": camera_id, "requested_timestamp": timestamp,
                           "timestamp": None if selected is None else selected.timestamp,
                           "media_ref": None if selected is None else selected.media_ref,
                           "status": "MISSING" if selected is None else
                           "EXACT" if selected.timestamp == timestamp else "NEAREST_AVAILABLE",
                           "time_offset_s": None if selected is None else
                           selected.timestamp - timestamp})
        return {"frames": result, "retrieval": {"camera_lookups": len(camera_ids),
                                                "frames_read": 0, "bytes_read": 0}}

    def evaluation(self) -> Json:
        """Dedicated research endpoint only: preexisting aggregate evaluation, never GT."""
        if self._evaluation_path is None or not self._evaluation_path.is_file():
            return {"status": "UNAVAILABLE", "reason": "NO_PREEXISTING_EVALUATION"}
        try:
            value: Json = json.loads(self._evaluation_path.read_text())
        except (OSError, ValueError):
            return {"status": "UNAVAILABLE", "reason": "INVALID_EVALUATION_SUMMARY"}
        if not isinstance(value, dict):
            return {"status": "UNAVAILABLE", "reason": "INVALID_EVALUATION_SUMMARY"}
        rows = {"aggregate": value} if "run_id" in value else value
        binding = self.service.guard.binding
        valid = bool(rows)
        if self._evaluation_freeze_hashes and "aggregate" not in rows:
            if set(rows) != set(self._evaluation_freeze_hashes):
                return {"status": "STALE", "reason": "EVALUATION_BINDING_MISMATCH"}
        for mode, row in rows.items():
            if not isinstance(row, dict) or row.get("run_id") != self.run_id or (
                row.get("model_id") != binding.model_id
                or row.get("config_sha256") != self._evaluation_config_hash
                or row.get("dataset_sha256") != binding.dataset_sha256
            ):
                valid = False
                break
            if self._evaluation_freeze_hashes:
                if mode == "aggregate":
                    hashes = row.get("freeze_receipt_sha256")
                    valid = False
                    if isinstance(hashes, list) and all(isinstance(h, str) for h in hashes):
                        valid = set(hashes) == set(self._evaluation_freeze_hashes.values())
                else:
                    valid = row.get("freeze_sha256") == self._evaluation_freeze_hashes.get(mode)
                if not valid:
                    break
        if not valid:
            return {"status": "STALE", "reason": "EVALUATION_BINDING_MISMATCH"}
        return value


def load_local_camera(root: Path) -> SceneAdapter:
    """Reuse the verified E1 checkpoint; opening the scene never generates data."""
    from amidst.engineering.local_pilot import _load, load_services

    services = load_services(root)
    service = next(s for s in services
                   if s.guard.binding.observation_mode == "photos_plus_observations")
    package, _, _, _ = _load(root)
    behavior = BehaviorConfig.model_validate_json((root / "behavior_config.json").read_bytes())
    return SceneAdapter(scene_id="local-camera", label="局部多鏡頭研究場景",
                        description="E1 · 四鏡頭透視 RGB、門口與轉角事件研究",
                        service=service, context=package.context,
                        evidence_level="E1_CONFIGURED_PINHOLE_RGB", behavior=behavior,
                        evaluation_path=root / "evaluation.json",
                        evaluation_config_hash=package.config_sha256,
                        evaluation_freeze_hashes={
                            s.guard.binding.observation_mode:
                            str(s.context()["freeze_ref"]).removeprefix("freeze-")
                            for s in services})


def load_synthetic_lab(root: Path) -> SceneAdapter:
    """Normalize E0 frozen results once; subsequent queries use the same interval index."""
    from amidst.engineering.run import load_facades

    facades = load_facades(root)
    facade = next(f for f in facades
                  if f.guard.binding.observation_mode == "photos_plus_observations")
    context = SyntheticStaticContext.model_validate_json(
        (root / "static_context.json").read_bytes())
    observations = []
    for original in facade.observations:
        row = original.model_dump(mode="json")
        row["camera_ids"] = [row.pop("camera_id")]
        row["camera_refs"] = [row.pop("camera_ref")]
        row["projected_path"] = row.pop("projected_positions")
        observations.append(row)
    by_observation = {o["observation_ref"]: o for o in observations}
    gaps = {g.event.event_id: g.event for g in facade.snapshot.gaps}
    frames = {f.media_ref: f for f in facade.frames}
    events = []
    for original_event in facade.events:
        row = original_event.model_dump(mode="json")
        row["camera_ids"] = list(dict.fromkeys(row["camera_ids"]))
        row["camera_refs"] = list(dict.fromkeys(row["camera_refs"]))
        gap = gaps.get(original_event.canonical_event_id or "")
        row["evidence_state"] = "INFERRED_GAP" if gap else "PROJECTED"
        row["candidates"] = [] if gap is None else [c.model_dump(mode="json")
                                                   for c in gap.candidates]
        row["trajectories"] = [] if gap is None else [t.model_dump(mode="json")
                                                     for t in gap.trajectories]
        row["projected_path"] = [p for ref in original_event.observation_refs
                                 for p in by_observation[ref]["projected_path"]]
        # Keep the registered source order; the UI can request a small evidence subset.
        row["source_frames"] = [{"frame_ref": ref, "camera_id": frames[ref].camera_id,
                                 "timestamp": frames[ref].timestamp}
                                for ref in original_event.media_refs]
        row["status"] = original_event.termination_reason
        row["support"] = []
        row["conflicts"] = []
        row["alternatives"] = [original_event.uncertainty]
        events.append(row)
    model = next(m for m in facade.store.registry.models if m.scope == facade.scope)
    topology = ScopedTopology(
        scope=facade.scope, camera_ids=tuple(c.camera_id for c in facade.cameras),
        camera_links=tuple(CameraLink(from_camera_id=a, to_camera_id=b)
                           for a, b in context.allowed_camera_pairs),
        camera_regions=tuple(CameraRegions(camera_id=c.camera_id, region_ids=c.region_ids)
                             for c in facade.cameras),
        topology_complete=False, clock_mapping_sha256=model.clock.mapping_sha256,
    )
    service = LocalPilotService(facade.store, facade.scope, facade.guard,
                                tuple(observations), tuple(events), topology)
    return SceneAdapter(scene_id="synthetic-lab", label="雙鏡頭基礎實驗室",
                        description="E0 · 仿射地面投影與盲區候選診斷；無實體鏡頭姿態",
                        service=service, context=context, evidence_level="E0_AFFINE_RGB_FIXTURE",
                        evaluation_path=root / "evaluation" / "summary.json",
                        evaluation_freeze_hashes={
                            f.guard.binding.observation_mode:
                            str(f.context()["freeze_ref"]).removeprefix("freeze-")
                            for f in facades})


def load_catalog(repo: Path, overrides: Mapping[str, Path] | None = None,
                 *, manifest_path: Path | None = None
                 ) -> dict[str, SceneAdapter]:
    """Resolve a fixed local manifest allowlist. Missing assets stay unavailable.

    Explicit overrides are server configuration, never browser-supplied paths.
    Invalid existing freezes fail closed; no fallback or automatic regeneration.
    """
    repo = repo.resolve()
    default_path = repo / "configs/engineering/workbench_v1.json"
    selected_path = manifest_path if manifest_path is not None else default_path
    if not selected_path.is_absolute():
        selected_path = repo / selected_path
    if selected_path.is_file():
        try:
            manifest = json.loads(selected_path.read_text())
        except (OSError, ValueError) as error:
            raise ValueError("INVALID_SCENE_CATALOG") from error
    elif manifest_path is not None:
        raise ValueError("SCENE_CATALOG_UNAVAILABLE")
    else:
        # A repository without a local manifest still has the two documented defaults.
        manifest = {"schema_version": "workbench.catalog.v1", "scenes": [
            {"scene_id": "local-camera", "adapter": "local_camera",
             "checkpoint": "data/engineering/local_run/local_camera_v1/test/checkpoints/final",
             "label": "局部多鏡頭研究場景",
             "description": "E1 · 四鏡頭透視 RGB、門口與轉角事件研究"},
            {"scene_id": "synthetic-lab", "adapter": "synthetic_lab",
             "checkpoint": "data/engineering/local_run/simulation_v2",
             "label": "雙鏡頭基礎實驗室", "description": "E0 · 仿射地面投影與盲區候選診斷"},
        ]}
    entries = _catalog_entries(repo, manifest)
    if overrides is not None:
        if not set(overrides) <= {entry["scene_id"] for entry in entries}:
            raise ValueError("UNKNOWN_SCENE_ADAPTER")
    loaders = {"local_camera": load_local_camera, "synthetic_lab": load_synthetic_lab}
    catalog = {}
    for entry in entries:
        scene_id = entry["scene_id"]
        root = (overrides or {}).get(scene_id, repo / entry["checkpoint"])
        if not root.exists():
            continue
        try:
            scene = loaders[entry["adapter"]](root.resolve())
            catalog[scene_id] = scene.with_display_identity(
                scene_id, entry["label"], entry["description"])
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
            raise ValueError("SCENE_SOURCE_UNAVAILABLE:" + scene_id) from error
    return catalog


def _catalog_entries(repo: Path, manifest: object) -> list[dict[str, str]]:
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "scenes"}:
        raise ValueError("INVALID_SCENE_CATALOG")
    if manifest["schema_version"] != "workbench.catalog.v1" or not isinstance(
        manifest["scenes"], list
    ):
        raise ValueError("INVALID_SCENE_CATALOG")
    entries: list[dict[str, str]] = []
    known: set[str] = set()
    for row in manifest["scenes"]:
        if not isinstance(row, dict) or set(row) != {
            "scene_id", "adapter", "checkpoint", "label", "description"
        } or any(not isinstance(value, str) or not value.strip() for value in row.values()):
            raise ValueError("INVALID_SCENE_CATALOG")
        scene_id = row["scene_id"]
        if not scene_id.isascii() or not all(c.isalnum() or c in "-_" for c in scene_id):
            raise ValueError("INVALID_SCENE_ID")
        if scene_id in known:
            raise ValueError("DUPLICATE_SCENE_ID")
        known.add(scene_id)
        if row["adapter"] not in {"local_camera", "synthetic_lab"}:
            raise ValueError("UNKNOWN_SCENE_ADAPTER")
        checkpoint = PurePosixPath(row["checkpoint"])
        if checkpoint.is_absolute() or ".." in checkpoint.parts or "\\" in row["checkpoint"]:
            raise ValueError("INVALID_SCENE_CHECKPOINT")
        try:
            (repo / row["checkpoint"]).resolve().relative_to(repo)
        except (ValueError, OSError) as error:
            raise ValueError("INVALID_SCENE_CHECKPOINT") from error
        entries.append(dict(row))
    return entries
