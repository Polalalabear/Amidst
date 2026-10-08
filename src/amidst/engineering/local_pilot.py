"""Build, evaluate and operate a versioned local camera research pilot."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Iterable
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from urllib.parse import parse_qs
from wsgiref.simple_server import WSGIRequestHandler, make_server

from amidst.engineering.access import FreezeReceipt, Mode, RunBinding, SessionGuard, digest
from amidst.engineering.facade import ToolFailure
from amidst.engineering.local_association import (
    AssociationPolicy,
    InferenceBundle,
    build_inference,
    resource_scope,
)
from amidst.engineering.local_behavior import (
    BehaviorConfig,
    BehaviorCorner,
    BehaviorPortal,
    LocalBehaviorBundle,
    compose_local_behaviors,
)
from amidst.engineering.local_index import (
    CameraLink,
    CameraRegions,
    RegionLink,
    RetrievalPolicy,
    ScopedTopology,
)
from amidst.engineering.local_service import LocalPilotService, ui_path
from amidst.engineering.perception import (
    PerceptionResult,
    frame_manifest_sha256,
    produce_perception,
)
from amidst.engineering.registry import (
    CameraEntry,
    ClockBinding,
    CoordinateBinding,
    LocationModel,
    LocationRegistry,
    MediaFrame,
    RegistryStore,
    opaque_ref,
    scope_parts,
)
from amidst.engineering.research_scene import (
    DEFAULT_CONFIG,
    ResearchPackage,
    generate_research_sequence,
)

MODES: tuple[Mode, ...] = ("photos_only", "photos_plus_observations")
ALGORITHMS = (
    "access.py",
    "registry.py",
    "facade.py",
    "perception.py",
    "association.py",
    "local_association.py",
    "local_index.py",
    "local_behavior.py",
    "local_evaluation.py",
    "research_scene.py",
    "local_service.py",
    "local_pilot.py",
    "../graph/engine.py",
    "../reconstruction/blind_gap.py",
    "../pipeline.py",
)


def evaluation_policy() -> dict[str, object]:
    from amidst.engineering.local_evaluation import (
        BEHAVIOR_TIME_TOLERANCE_S,
        CONTACT_TOLERANCE_PX,
        REFERENCE_RETRIEVAL_MAX_HOPS,
        REFERENCE_RETRIEVAL_WINDOW_S,
        SEGMENT_PURITY,
    )

    return {
        "contact_tolerance_px": CONTACT_TOLERANCE_PX,
        "segment_purity": SEGMENT_PURITY,
        "behavior_time_tolerance_s": BEHAVIOR_TIME_TOLERANCE_S,
        "reference_window_s": REFERENCE_RETRIEVAL_WINDOW_S,
        "reference_max_hops": REFERENCE_RETRIEVAL_MAX_HOPS,
        "version": "development-fixed-evaluator-v1",
    }


def algorithm_hashes() -> dict[str, str]:
    return {
        name: sha256((Path(__file__).parent / name).read_bytes()).hexdigest() for name in ALGORITHMS
    }


def _save(path: Path, value: object) -> None:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    data = json.dumps(value, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise ValueError("immutable pilot output differs; select a new run output")
    if not path.exists():
        path.write_bytes(data)


def _catalog(
    package: ResearchPackage, root: Path, static: dict[str, Any]
) -> tuple[LocationRegistry, ScopedTopology, dict[str, str]]:
    scope = resource_scope(package.scope)
    clock_hash = digest(
        {
            "clock": scope.clock_id,
            "fps": package.fps,
            "origin_s": 0,
            "mapping": "CONFIGURED_SYNTHETIC_IDENTITY_SECONDS",
        }
    )
    model = LocationModel(
        scope=scope,
        display_name="Local camera lab",
        aliases=("lab", "合成實驗室"),
        coordinates=CoordinateBinding(
            native_units="METRES",
            metres_per_unit=1,
            normalization_policy="IDENTITY",
            authority="SYNTHETIC_CONFIG",
        ),
        clock=ClockBinding(
            clock_id=scope.clock_id, authority="SYNTHETIC_CONFIG", mapping_sha256=clock_hash
        ),
        authority="SYNTHETIC_CONFIG",
    )
    cameras: list[CameraEntry] = []
    coverage = {row["camera_id"]: row["coverage"] for row in static["cameras"]}
    for camera in package.cameras:
        x0, y0, x1, y1 = coverage[camera.camera_id]
        regions = tuple(
            region.region_id
            for region in package.context.regions
            if region.bounds_xy_m[0] < x1
            and region.bounds_xy_m[2] > x0
            and region.bounds_xy_m[1] < y1
            and region.bounds_xy_m[3] > y0
        )
        cameras.append(
            CameraEntry(
                scope=scope,
                camera_id=camera.camera_id,
                camera_ref=opaque_ref("camera", *scope_parts(scope), camera.camera_id),
                group_ids=("local-lab",),
                coverage_status="CONFIGURED_SYNTHETIC",
                region_ids=regions,
                authority="SYNTHETIC_CONFIG",
                calibration=camera,
                calibration_sha256=digest(camera),
            )
        )
    frames: list[MediaFrame] = []
    links: dict[str, str] = {}
    for frame in package.frames:
        frame_id = round(frame.timestamp * package.fps)
        media_ref = opaque_ref(
            "media", *scope_parts(scope), frame.camera_id, str(frame_id), frame.sha256
        )
        links[frame.media_ref] = media_ref
        frames.append(
            MediaFrame(
                scope=scope,
                camera_id=frame.camera_id,
                camera_ref=opaque_ref("camera", *scope_parts(scope), frame.camera_id),
                media_ref=media_ref,
                frame_id=frame_id,
                timestamp=frame.timestamp,
                relative_path=frame.path.relative_to(root).as_posix(),
                sha256=frame.sha256,
                size_bytes=frame.path.stat().st_size,
                width=frame.width,
                height=frame.height,
            )
        )
    region_links = tuple(
        RegionLink(
            from_region_id=p["outside_region_id"],
            to_region_id=p["inside_region_id"],
            portal_ref=opaque_ref("portal", *scope_parts(scope), p["portal_id"]),
        )
        for p in static["portals"]
    )
    topology = ScopedTopology(
        scope=scope,
        camera_ids=tuple(c.camera_id for c in cameras),
        camera_links=tuple(
            CameraLink(from_camera_id=a, to_camera_id=b) for a, b in package.adjacency
        ),
        camera_regions=tuple(
            CameraRegions(camera_id=c.camera_id, region_ids=c.region_ids) for c in cameras
        ),
        region_links=region_links,
        topology_complete=True,
        clock_mapping_sha256=clock_hash,
    )
    return (
        LocationRegistry(models=(model,), cameras=tuple(cameras), frames=tuple(frames)),
        topology,
        links,
    )


def behavior_config(package: ResearchPackage, static: dict[str, Any]) -> BehaviorConfig:
    return BehaviorConfig(
        scope=package.scope,
        config_version="development-fixed-local-camera-v1",
        regions=package.context.regions,
        portals=tuple(BehaviorPortal.model_validate(p) for p in static["portals"]),
        corners=tuple(BehaviorCorner.model_validate(c) for c in static["corners"]),
        revisit_region_ids=("west", "north-branch"),
    )


def build_run(
    root: Path,
    *,
    split: Literal["development", "test"] = "test",
    run_id: str | None = None,
    config_path: Path = DEFAULT_CONFIG,
    reuse_from: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    media_root = root if reuse_from is None else reuse_from.resolve()
    if reuse_from is None:
        package = generate_research_sequence(
            root, split=split, run_id=run_id, config_path=config_path
        )
    else:
        # New code/config freeze reuses immutable RGB/GT; old snapshots stay byte-identical.
        package = ResearchPackage.model_validate_json((media_root / "package.json").read_bytes())
        if (
            package.split != split
            or (run_id is not None and package.run_id != run_id)
            or package.config_sha256 != digest(json.loads(config_path.read_text()))
            or package.generator_sha256 != algorithm_hashes()["research_scene.py"]
        ):
            raise ValueError("reused RGB source/config/run mismatch")
        root.relative_to(media_root)
    static = {
        key: value for key, value in json.loads(config_path.read_text()).items() if key != "splits"
    }
    registry, topology, links = _catalog(package, media_root, static)
    behavior = behavior_config(package, static)
    policy = AssociationPolicy.model_validate(static["association_policy"])
    retrieval = RetrievalPolicy(
        window_steps_s=(4.0, 8.0, 12.0), max_hops=3, max_cameras=8, max_records=128
    )
    # Nested domain objects use explicit canonical JSON; no recipe is an inference input.
    config_hash = digest(
        {
            "static": static,
            "behavior": behavior.model_dump(mode="json"),
            "association": policy.model_dump(mode="json"),
            "retrieval": retrieval.model_dump(mode="json"),
            "algorithms": algorithm_hashes(),
            "evaluation_policy": evaluation_policy(),
        }
    )
    _save(root / "package.json", package)
    _save(root / "registry.json", registry)
    _save(root / "topology.json", topology)
    _save(root / "runtime_config.json", static)
    _save(root / "behavior_config.json", behavior)
    receipts: dict[str, Any] = {}
    event_hashes: dict[str, str] = {}
    timings: dict[str, dict[str, float]] = {}
    for mode in MODES:
        start = perf_counter()
        # Photos-only is deliberately recomputed, never loaded from the other mode.
        perception = produce_perception(
            package.frames, model_id=package.model_id, run_id=package.run_id
        )
        pixel_duration = perf_counter() - start
        start = perf_counter()
        inference = build_inference(
            perception,
            scope=package.scope,
            context=package.context,
            policy=policy,
            topology=topology,
            retrieval_policy=retrieval,
        )
        inference_duration = perf_counter() - start
        events = compose_local_behaviors(inference, behavior, tracks=perception.tracks)
        binding = RunBinding(
            place_id=package.scope.place_id,
            model_id=package.model_id,
            model_revision=package.revision,
            source_ref=package.scope.source_ref,
            spatial_context_id=package.scope.spatial_context_id,
            run_id=package.run_id,
            clock_id=package.scope.clock_id,
            observation_mode=mode,
            registry_version="local-camera-index.v1",
            dataset_sha256=package.dataset_sha256,
            config_sha256=config_hash,
            producer_sha256=perception.producer_sha256,
            registry_sha256=registry.sha256,
            media_sha256=digest([(f.media_ref, f.sha256) for f in registry.frames]),
        )
        receipt = FreezeReceipt.create(binding, inference, perception.model_dump(mode="json"))
        _save(root / f"perception_{mode}.json", perception)
        _save(root / f"inference_{mode}.json", inference)
        _save(root / f"events_{mode}.json", events)
        receipts[mode] = receipt.model_dump(mode="json")
        event_hashes[mode] = digest(events)
        timings[mode] = {"pixel_seconds": pixel_duration, "inference_seconds": inference_duration}
    manifest: dict[str, Any] = {
        "schema_version": "local.camera.pilot.v1",
        "run_id": package.run_id,
        "split": split,
        "package_sha256": digest(package),
        "config_sha256": config_hash,
        "runtime_config_sha256": digest(static),
        "behavior_config_sha256": digest(behavior),
        "topology_sha256": digest(topology),
        "registry_sha256": registry.sha256,
        "algorithms": algorithm_hashes(),
        "evaluation_policy": evaluation_policy(),
        "frame_links": links,
        "receipts": receipts,
        "event_hashes": event_hashes,
        "association_policy": policy.model_dump(mode="json"),
        "retrieval_policy": retrieval.model_dump(mode="json"),
        "policy_frozen_before_test": True,
        "formal_status": "BLOCKED",
        "media_root_ancestor_depth": len(root.relative_to(media_root).parts),
    }
    _save(root / "manifest.json", manifest)
    # Wall-clock telemetry is deliberately outside deterministic inference/freeze hashes.
    (root / "timings.json").write_text(json.dumps(timings, indent=2) + "\n")
    return manifest


def _media_root(root: Path, manifest: dict[str, Any]) -> Path:
    depth = manifest["media_root_ancestor_depth"]
    if type(depth) is not int or not 0 <= depth <= 8:
        raise ValueError("invalid local media containment")
    return root if depth == 0 else root.parents[depth - 1]


def _load(root: Path) -> tuple[ResearchPackage, LocationRegistry, ScopedTopology, dict[str, Any]]:
    root = root.resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("schema_version") != "local.camera.pilot.v1":
        raise ValueError("pilot version mismatch")
    package = ResearchPackage.model_validate_json((root / "package.json").read_bytes())
    registry = LocationRegistry.model_validate_json((root / "registry.json").read_bytes())
    topology = ScopedTopology.model_validate_json((root / "topology.json").read_bytes())
    static = json.loads((root / "runtime_config.json").read_text())
    behavior = BehaviorConfig.model_validate_json((root / "behavior_config.json").read_bytes())
    policy = AssociationPolicy.model_validate(manifest["association_policy"])
    retrieval = RetrievalPolicy.model_validate(manifest["retrieval_policy"])
    effective_hash = digest(
        {
            "static": static,
            "behavior": behavior.model_dump(mode="json"),
            "association": policy.model_dump(mode="json"),
            "retrieval": retrieval.model_dump(mode="json"),
            "algorithms": algorithm_hashes(),
            "evaluation_policy": evaluation_policy(),
        }
    )
    if (
        manifest["algorithms"] != algorithm_hashes()
        or digest(package) != manifest["package_sha256"]
        or registry.sha256 != manifest["registry_sha256"]
        or digest(topology) != manifest["topology_sha256"]
        or digest(static) != manifest["runtime_config_sha256"]
        or digest(behavior) != manifest["behavior_config_sha256"]
        or topology.scope != resource_scope(package.scope)
        or manifest["config_sha256"] != effective_hash
        or manifest["evaluation_policy"] != evaluation_policy()
        or package.dataset_sha256 != frame_manifest_sha256(package.frames)
        or package.generator_sha256 != algorithm_hashes()["research_scene.py"]
        or package.context.source_sha256 != package.scope.source_sha256
        or package.context.context_sha256 != package.scope.context_sha256
        or package.context_sha256 != package.scope.context_sha256
    ):
        raise ValueError("pilot source/config/index freeze mismatch")
    media_root = _media_root(root, manifest)
    if package.simulation_export_path.parents[2] != media_root:
        raise ValueError("pilot media/export containment mismatch")
    store = RegistryStore(registry, media_root)
    # Explicit manifest verification on import. Queries perform direct scoped lookup.
    for frame in registry.frames:
        store.media_bytes(frame.scope, frame.media_ref)
    if set(manifest["frame_links"]) != {f.media_ref for f in package.frames} or set(
        manifest["frame_links"].values()
    ) != {f.media_ref for f in registry.frames}:
        raise ValueError("pilot frame index mismatch")
    return package, registry, topology, manifest


def frozen_mode(
    root: Path, mode: Mode, manifest: dict[str, Any]
) -> tuple[PerceptionResult, InferenceBundle, LocalBehaviorBundle, FreezeReceipt]:
    perception = PerceptionResult.model_validate_json(
        (root / f"perception_{mode}.json").read_bytes()
    )
    inference = InferenceBundle.model_validate_json((root / f"inference_{mode}.json").read_bytes())
    events = LocalBehaviorBundle.model_validate_json((root / f"events_{mode}.json").read_bytes())
    receipt = FreezeReceipt.model_validate(manifest["receipts"][mode])
    if (
        receipt.binding.observation_mode != mode
        or receipt.binding.run_id != manifest["run_id"]
        or receipt.binding.config_sha256 != manifest["config_sha256"]
        or not receipt.verify(receipt.binding, inference, perception.model_dump(mode="json"))
        or digest(events) != manifest["event_hashes"][mode]
        or events.inference_sha256 != receipt.inference_sha256
        or events.input_manifest_sha256 != receipt.binding.dataset_sha256
        or events.producer_sha256 != receipt.binding.producer_sha256
        or events.scope != inference.scope
        or events.config_sha256 != manifest["behavior_config_sha256"]
    ):
        raise ValueError("same-run mode/inference/event freeze mismatch")
    return perception, inference, events, receipt


def load_services(root: Path, *, input_stage: bool = False) -> tuple[LocalPilotService, ...]:
    root = root.resolve()
    package, registry, topology, manifest = _load(root)
    services = []
    scope = resource_scope(package.scope)
    links = manifest["frame_links"]
    cameras = {c.camera_id: c.camera_ref for c in registry.cameras}
    for mode in MODES:
        perception, inference, behaviors, receipt = frozen_mode(root, mode, manifest)
        if (
            receipt.binding.dataset_sha256 != package.dataset_sha256
            or receipt.binding.registry_sha256 != registry.sha256
            or inference.scope != package.scope
            or receipt.binding.source_ref != package.scope.source_ref
            or inference.policy.model_dump(mode="json") != manifest["association_policy"]
        ):
            raise ValueError("pilot source/registry binding mismatch")
        frames_by_ref = {f.media_ref: f for f in package.frames}
        for measurement in perception.measurements:
            frame = frames_by_ref.get(measurement.frame_ref)
            if frame is None or (
                measurement.camera_id,
                measurement.timestamp,
                measurement.input_sha256,
                measurement.model_id,
                measurement.run_id,
            ) != (frame.camera_id, frame.timestamp, frame.sha256, package.model_id, package.run_id):
                raise ValueError("pilot pixel/frame binding mismatch")
        guard = SessionGuard(receipt.binding)
        if not input_stage:
            guard.freeze(receipt, inference, perception.model_dump(mode="json"))
        by_pixel = {m.observation_id: m for m in perception.measurements}
        by_projection = {p.observation_id: p for p in inference.projected_measurements}
        observations = []
        for mapping in inference.local_record_maps:
            pixels = tuple(by_pixel[p] for p in mapping.original_pixel_observation_ids)
            observations.append(
                {
                    "observation_ref": opaque_ref(
                        "observation", *scope_parts(scope), mapping.segment_id
                    ),
                    "local_track_ref": opaque_ref(
                        "track", *scope_parts(scope), mapping.local_track_id
                    ),
                    "camera_refs": [cameras[pixels[0].camera_id]],
                    "camera_ids": [pixels[0].camera_id],
                    "time_range": [pixels[0].timestamp, pixels[-1].timestamp],
                    "media_refs": [links[p.frame_ref] for p in pixels],
                    "region_ids": list(
                        dict.fromkeys(
                            r for p in pixels for r in by_projection[p.observation_id].region_ids
                        )
                    ),
                    "measurements": [
                        {
                            "frame_ref": links[p.frame_ref],
                            "timestamp": p.timestamp,
                            "bbox": p.bbox_xyxy,
                            "point_2d": p.contact_pixel,
                            "visible_features": p.appearance,
                        }
                        for p in pixels
                    ],
                    "projected_path": [
                        point.world_position
                        for p in pixels
                        if (point := by_projection[p.observation_id].point) is not None
                    ],
                    "origin": "SYNTHETIC",
                    "image_measurement": True,
                    "authority": "RGB_PIXELS_WITH_SYNTHETIC_CONFIG",
                    "uncertainty": "Local IDs and RGB components may merge/swap; no GT correction.",
                }
            )
        events = []
        for event in behaviors.events:
            row = event.model_dump(mode="json")
            row.pop("scope")
            row.pop("local_track_ids")
            row.pop("segment_ids")
            row["local_track_refs"] = [
                opaque_ref("track", *scope_parts(scope), t) for t in event.local_track_ids
            ]
            row["segment_refs"] = [
                opaque_ref("segment", *scope_parts(scope), s) for s in event.segment_ids
            ]
            row["event_ref"] = opaque_ref("event", *scope_parts(scope), event.event_id)
            row["detail_ref"] = row["event_ref"]
            row["replay_ref"] = row["event_ref"]
            row["association_refs"] = [
                opaque_ref("association", *scope_parts(scope), a) for a in event.association_refs
            ]
            row["association_states"] = [
                {
                    "association_ref": opaque_ref(
                        "association", *scope_parts(scope), state.hypothesis_id
                    ),
                    "kind": state.kind,
                    "status": state.status,
                    "reason": state.reason,
                }
                for state in event.association_states
            ]
            row["camera_ids"] = list(dict.fromkeys(f.camera_id for f in event.source_frames))
            row["camera_refs"] = [cameras[c] for c in row["camera_ids"]]
            row["media_refs"] = [links[f.frame_ref] for f in event.source_frames]
            row["source_frames"] = [
                {
                    "frame_ref": links[f.frame_ref],
                    "camera_id": f.camera_id,
                    "timestamp": f.timestamp,
                    "evidence_state": "PROJECTED",
                }
                for f in event.source_frames
            ]
            events.append(row)
        services.append(
            LocalPilotService(
                RegistryStore(registry, _media_root(root, manifest)),
                scope,
                guard,
                tuple(observations),
                tuple(events),
                topology,
            )
        )
    return tuple(services)


class LocalApplication:
    def __init__(self, services: tuple[LocalPilotService, ...]) -> None:
        self.services = {s.guard.binding.observation_mode: s for s in services}

    def __call__(
        self, environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "GET")
        status = "200 OK"
        mime = "application/json"
        try:
            if path == "/" and method == "GET":
                mime, data = "text/html; charset=utf-8", ui_path().read_bytes()
            else:
                query = parse_qs(environ.get("QUERY_STRING", ""))
                if set(query) != {"mode"} or len(query["mode"]) != 1:
                    raise ToolFailure("INVALID_REQUEST")
                service = self.services[query["mode"][0]]
                if path == "/api/context" and method == "GET":
                    result = service.context()
                elif path.startswith("/api/tool/") and method == "POST":
                    name = path.removeprefix("/api/tool/")
                    if name not in service.guard.allowed_tools():
                        raise ToolFailure("STAGE_OR_TOOL_DENIED")
                    size = int(environ.get("CONTENT_LENGTH", "0"))
                    if not 0 < size <= 65536:
                        raise ToolFailure("INVALID_REQUEST")
                    payload = json.loads(environ["wsgi.input"].read(size))
                    result = service.call(name, payload)
                else:
                    raise ToolFailure("METHOD_OR_ROUTE_DENIED")
                data = json.dumps(result, allow_nan=False).encode()
        except (ValueError, KeyError, TypeError, OSError):
            status, data = "400 Bad Request", b'{"error":"INVALID_OR_UNAVAILABLE"}'
        start_response(
            status,
            [
                ("Content-Type", mime),
                ("Content-Length", str(len(data))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [data]


class QuietHandler(WSGIRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def mock_agent(service: LocalPilotService) -> dict[str, Any]:
    session = {"session_ref": service.guard.session_ref}
    service.call("resolve_place", session | {"query": "lab"})
    cameras = service.call("list_cameras", session)["items"]
    cards = []
    for camera in cameras:
        query = service.call(
            "query_events", session | {"camera_ref": camera["camera_ref"], "time_range": [0, 24]}
        )
        for item in query["items"][:3]:
            payload = session | {"event_ref": item["event_ref"]}
            service.call("get_event_summary", payload)
            detail = service.call("get_event_detail", payload)
            for ref in detail["media_refs"]:
                service.call("get_media", session | {"media_ref": ref})
            service.call("get_replay", payload | {"timestamp": sum(item["time_range"]) / 2})
            cards.append(item)
    return {"context": service.context(), "cards": cards, "tools": service.logs}


def export_cards(root: Path) -> dict[str, object]:
    """Static review cards: actual RGB and separate projected/candidate 3D views."""
    import matplotlib

    matplotlib.use("Agg")
    from io import BytesIO

    import matplotlib.pyplot as plt
    from PIL import Image

    service = load_services(root)[0]
    chosen: dict[str, dict[str, Any]] = {}
    for event in service.events.values():
        chosen.setdefault(event["kind"], event)
    outputs = []
    for kind, event in chosen.items():
        figure = plt.figure(figsize=(14, 6), layout="constrained")
        grid = figure.add_gridspec(2, 5, height_ratios=(1, 1.3))
        for index, ref in enumerate(event["media_refs"]):
            frame = service.frames[ref]
            axis = figure.add_subplot(grid[0, index])
            with Image.open(BytesIO(service.store.media_bytes(service.scope, ref))) as image:
                axis.imshow(image)
            axis.set_title(f"{frame.camera_id} / {frame.timestamp:.2f}s / RGB", fontsize=9)
            axis.axis("off")
        axis3d = figure.add_subplot(grid[1, :3], projection="3d")
        axis3d.set(
            xlabel="x (m)", ylabel="y (m)", zlabel="z (m)", xlim=(0, 16), ylim=(0, 8), zlim=(0, 2.5)
        )
        for index, candidate in enumerate(event["candidates"]):
            points = candidate["polyline"]
            axis3d.plot(
                [p[0] for p in points],
                [p[1] for p in points],
                [p[2] for p in points],
                label=f"candidate {index + 1}",
            )
        projected = [p["world_position"] for p in event["projected_path"]]
        if projected:
            axis3d.scatter(
                [p[0] for p in projected],
                [p[1] for p in projected],
                [p[2] for p in projected],
                s=9,
                color="black",
                label="visible pixels projected",
            )
        axis3d.view_init(elev=32, azim=-60)
        axis3d.legend(fontsize=7, loc="upper left")
        info = figure.add_subplot(grid[1, 3:])
        info.axis("off")
        info.text(
            0,
            1,
            f"{kind}\n{event['evidence_state']}\n"
            f"{event['time_range'][0]:.2f}–{event['time_range'][1]:.2f} seconds\n"
            f"{len(event['candidates'])} routes / {len(event['trajectories'])} time hypotheses\n"
            f"rule: {event['rule_version']}\n"
            "Synthetic configured authority; identity provisional.\n"
            "Camera photos above; 3D below is derived geometry.\n"
            "Blind-gap samples are points, never an observed connecting path.",
            va="top",
            fontsize=9,
            wrap=True,
        )
        figure.suptitle("Amidst local camera pilot · " + kind, fontsize=14)
        path = root / "cards" / f"{kind.lower()}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(path, dpi=130)
        plt.close(figure)
        outputs.append(
            {
                "kind": kind,
                "relative_path": path.relative_to(root).as_posix(),
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "media_refs": event["media_refs"],
                "event_ref": event["event_ref"],
            }
        )
    result = {
        "schema_version": "local.camera.cards.v1",
        "run_id": service.scope.run_id,
        "cards": outputs,
        "gt_overlay": False,
    }
    _save(root / "cards_receipt.json", result)
    return result


def benchmark_queries(service: LocalPilotService) -> dict[str, object]:
    """Measure frozen bucket lookups separately from import and pixel processing."""
    samples = []
    reads = []
    entries = []
    session = {"session_ref": service.guard.session_ref}
    for _ in range(10):
        for camera_ref in service.cameras:
            for window in ((0, 2), (8, 10), (14, 16)):
                start = perf_counter()
                response = service.call(
                    "query_events",
                    session
                    | {
                        "camera_ref": camera_ref,
                        "time_range": window,
                    },
                )
                samples.append((perf_counter() - start) * 1000)
                reads.append(response["retrieval"]["records_read"])
                entries.append(response["retrieval"]["index_entries_touched"])
    samples.sort()
    return {
        "run_id": service.scope.run_id,
        "mode": service.guard.binding.observation_mode,
        "stage": "RESULTS",
        "population": "4 cameras × 3 windows × 10 repeats",
        "query_count": len(samples),
        "latency_ms_median": samples[len(samples) // 2],
        "latency_ms_p95": samples[round((len(samples) - 1) * 0.95)],
        "records_read_max": max(reads),
        "index_entries_touched_max": max(entries),
        "frames_read": 0,
        "crops_read": 0,
        "bytes_read": 0,
        "note": "Local frozen event query; media and build costs are separate.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "serve", "demo", "evaluate", "export-cards"))
    parser.add_argument(
        "--output", type=Path, default=Path("data/engineering/local_run/local_camera_v1")
    )
    parser.add_argument("--split", choices=("development", "test"), default="test")
    parser.add_argument("--run-id")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--reuse-from",
        type=Path,
        help="Reuse same-run RGB; output must be a new checkpoint under that root",
    )
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args()
    if args.command == "build":
        manifest = build_run(
            args.output,
            split=args.split,
            run_id=args.run_id,
            config_path=args.config,
            reuse_from=args.reuse_from,
        )
        print(
            json.dumps(
                {
                    "run_id": manifest["run_id"],
                    "config_sha256": manifest["config_sha256"],
                    "freeze_sha256": digest(manifest),
                }
            )
        )
    elif args.command == "serve":
        services = load_services(args.output)
        with make_server(
            "127.0.0.1", args.port, LocalApplication(services), handler_class=QuietHandler
        ) as server:
            print(f"Local camera pilot: http://127.0.0.1:{args.port}", flush=True)
            server.serve_forever()
    elif args.command == "demo":
        services = load_services(args.output)
        results = [mock_agent(s) for s in services]
        _save(args.output / "tool_receipt.json", results)
        performance = [benchmark_queries(s) for s in services]
        (args.output / "performance.json").write_text(json.dumps(performance, indent=2) + "\n")
        print(
            json.dumps({"modes": len(results), "tool_calls": sum(len(r["tools"]) for r in results)})
        )
    elif args.command == "export-cards":
        print(json.dumps(export_cards(args.output)))
    else:
        from amidst.engineering.local_evaluation import evaluate_local_pilot

        package, _, _, manifest = _load(args.output)
        evaluations: dict[str, object] = {}
        for mode in MODES:
            perception, inference, events, receipt = frozen_mode(args.output, mode, manifest)
            evaluations[mode] = evaluate_local_pilot(
                package,
                perception,
                inference,
                receipt=receipt,
                events=events.events,
                events_sha256=digest([event.model_dump(mode="json") for event in events.events]),
                behavior_bundle=events,
            )
        _save(args.output / "evaluation.json", evaluations)
        print(json.dumps(evaluations, indent=2))


if __name__ == "__main__":
    main()
