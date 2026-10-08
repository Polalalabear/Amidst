"""Materialize, freeze, reload and demonstrate one local synthetic run."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from amidst.domain.common import DomainModel
from amidst.domain.geometry import Plane
from amidst.engineering.access import FreezeReceipt, Mode, RunBinding, SessionGuard, digest
from amidst.engineering.association import (
    AssociationPolicy,
    ConfiguredRegion,
    GroundCalibration,
    InferenceBundle,
    InferenceScope,
    SyntheticStaticContext,
    build_inference,
)
from amidst.engineering.facade import AgentFacade, EventView, MeasurementView, ObservationView
from amidst.engineering.perception import (
    PerceptionResult,
    RGBFrame,
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
    PixelPlaneCalibration,
    RegistryStore,
    ResourceScope,
    content_hash,
    opaque_ref,
    scope_parts,
)
from amidst.engineering.synthetic import SyntheticPackage, generate_sequence
from amidst.integration.local_repository import InMemoryRepository, LocalJsonRepository


class EngineeringConfig(DomainModel):
    schema_version: Literal["simulation.engineering.config.v1"]
    model_id: str
    frame_count: int = Field(ge=5, le=1000)
    fps: float = Field(gt=0)
    input_modes: tuple[Mode, ...]
    receiver: Literal["LOCAL_DETERMINISTIC_IMAGE_ASSOCIATION"]
    decision_stage: Literal["PIXEL_MEASUREMENT_THEN_PROVISIONAL_ASSOCIATION"]
    external_model_calls: Literal[False]
    formal_phase1_acceptance: Literal[False]


class RunManifest(DomainModel):
    schema_version: Literal["simulation.run.v1"] = "simulation.run.v1"
    scope: ResourceScope
    registry_sha256: str
    source_sha256: str
    model_source_sha256: str
    config_sha256: str
    generator_config_sha256: str
    algorithm_hashes: dict[str, str]
    frame_links: dict[str, str]
    input_envelope_hashes: dict[Mode, str]
    receipts: tuple[FreezeReceipt, ...]
    external_model_calls: Literal[False] = False
    formal_phase1_acceptance: Literal[False] = False


def _write(path: Path, value: DomainModel | object) -> None:
    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    encoded = (json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("existing run receipt differs; choose a new output")
        return
    with path.open("xb") as stream:
        stream.write(encoded)


def algorithm_hashes() -> dict[str, str]:
    """Bind implementations actually used, independently of a working-tree label."""
    source = Path(__file__).parent.parent
    return {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in (
        "engineering/perception.py", "engineering/synthetic.py", "engineering/association.py",
        "pipeline.py", "graph/engine.py", "reconstruction/blind_gap.py",
    )}


def effective_config_hash(config: EngineeringConfig, generator_config_hash: str,
                          context: SyntheticStaticContext, policy: AssociationPolicy,
                          implementations: dict[str, str]) -> str:
    return digest({"engineering": config.model_dump(mode="json"),
                   "generator_config_sha256": generator_config_hash,
                   "static_context": context.model_dump(mode="json"),
                   "association_policy": policy.model_dump(mode="json"),
                   "algorithm_hashes": implementations})


def _catalog(package: SyntheticPackage, root: Path) -> tuple[LocationRegistry, ResourceScope,
                                                           dict[str, str]]:
    scope = ResourceScope(
        place_id="synthetic-lab", model_id=package.model_id, model_revision=package.revision,
        run_id=package.run_id, source_id="procedural-rgb-lab-v1",
        source_sha256=package.source_sha256, spatial_context_id="synthetic-lab-ground-v1",
        spatial_context_sha256=package.context_sha256, clock_id="synthetic-lab-seconds-v1",
    )
    model = LocationModel(
        scope=scope, display_name="Synthetic lab", aliases=("lab", "合成實驗室"),
        coordinates=CoordinateBinding(native_units="METRES", metres_per_unit=1,
                                      normalization_policy="IDENTITY",
                                      authority="SYNTHETIC_CONFIG"),
        clock=ClockBinding(clock_id=scope.clock_id, authority="SYNTHETIC_CONFIG",
                           mapping_sha256=digest({"fps": package.fps, "origin": 0})),
        authority="SYNTHETIC_CONFIG",
    )
    cameras = []
    for camera in package.cameras:
        calibration = PixelPlaneCalibration(
            camera_id=camera.camera_id, width=camera.width, height=camera.height,
            ground_to_pixel=camera.ground_to_pixel, plane_z_m=camera.plane_z_m,
        )
        # Derive partial plane coverage from calibration, never from a camera's name.
        regions = []
        for region in static_context(package).regions:
            x0, y0, x1, y1 = region.bounds_xy_m
            a, b = camera.ground_to_pixel
            uv = [(a[0] * x + a[1] * y + a[2], b[0] * x + b[1] * y + b[2])
                  for x, y in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
            if (max(u for u, _ in uv) >= 0 and min(u for u, _ in uv) < camera.width
                and max(v for _, v in uv) >= 0 and min(v for _, v in uv) < camera.height):
                regions.append(region.region_id)
        cameras.append(CameraEntry(
            scope=scope, camera_id=camera.camera_id,
            camera_ref=opaque_ref("camera", *scope_parts(scope), camera.camera_id),
            group_ids=("lab",), coverage_status="CONFIGURED_SYNTHETIC", region_ids=tuple(regions),
            authority="SYNTHETIC_CONFIG", affine_calibration=calibration,
            calibration_sha256=content_hash(calibration.model_dump(mode="json")),
        ))
    frames, links = [], {}
    for frame in package.frames:
        frame_id = int(round(frame.timestamp * package.fps))
        ref = opaque_ref("media", *scope_parts(scope), frame.camera_id, str(frame_id), frame.sha256)
        links[frame.media_ref] = ref
        frames.append(MediaFrame(
            scope=scope, camera_id=frame.camera_id,
            camera_ref=opaque_ref("camera", *scope_parts(scope), frame.camera_id), media_ref=ref,
            frame_id=frame_id, timestamp=frame.timestamp,
            relative_path=frame.path.relative_to(root).as_posix(), sha256=frame.sha256,
            size_bytes=frame.path.stat().st_size, width=frame.width, height=frame.height,
        ))
    registry = LocationRegistry(models=(model,), cameras=tuple(cameras), frames=tuple(frames))
    return registry, scope, links


def static_context(package: SyntheticPackage) -> SyntheticStaticContext:
    plane = Plane(plane_id="lab-ground", point=(0, 0, 0), normal=(0, 0, 1), floor_id="lab-floor")
    return SyntheticStaticContext(
        spatial_context_id="synthetic-lab-ground-v1", source_sha256=package.source_sha256,
        context_sha256=package.context_sha256,
        ground_plane=plane, walkable_bounds_xy_m=(0, 0, 12, 4),
        calibrations=tuple(GroundCalibration(camera_id=c.camera_id, plane=plane,
                                            affine_ground_to_pixel=c.ground_to_pixel)
                           for c in package.cameras),
        regions=tuple(ConfiguredRegion(region_id=name, floor_id="lab-floor",
                                       bounds_xy_m=bounds) for name, bounds in (
            ("west", (0, 0, 4, 4)), ("central", (4, 0, 8, 4)), ("east", (8, 0, 12, 4)),
        )),
        allowed_camera_pairs=(("CAM_A", "CAM_B"), ("CAM_B", "CAM_A")),
        detour_waypoints_m=((5, 0.8, 0), (5, 3.2, 0)),
    )


def _views(registry: LocationRegistry, manifest: RunManifest, perception: PerceptionResult,
           inference: InferenceBundle) -> tuple[tuple[ObservationView, ...], tuple[EventView, ...]]:
    scope = manifest.scope
    camera_refs = {c.camera_id: c.camera_ref for c in registry.cameras if c.scope == scope}
    pixels = {m.observation_id: m for m in perception.measurements}
    projected = {p.observation_id: p for p in inference.projected_measurements}
    observations = []
    obs_refs = {}
    for record in inference.local_record_maps:
        selected = [pixels[key] for key in record.original_pixel_observation_ids]
        if not selected:
            continue
        obs_ref = opaque_ref("observation", *scope_parts(scope), record.canonical_observation_id)
        obs_refs[record.canonical_observation_id] = obs_ref
        observations.append(ObservationView(
            observation_ref=obs_ref, canonical_observation_id=record.canonical_observation_id,
            local_track_ref=opaque_ref("track", *scope_parts(scope), record.local_track_id),
            camera_id=selected[0].camera_id, camera_ref=camera_refs[selected[0].camera_id],
            time_range=(selected[0].timestamp, selected[-1].timestamp),
            evidence_refs=tuple(opaque_ref("measurement", *scope_parts(scope), m.observation_id)
                                for m in selected),
            media_refs=tuple(dict.fromkeys(manifest.frame_links[m.frame_ref] for m in selected)),
            measurements=tuple(MeasurementView(
                measurement_ref=opaque_ref("measurement", *scope_parts(scope), m.observation_id),
                frame_ref=manifest.frame_links[m.frame_ref], timestamp=m.timestamp,
                bbox=m.bbox_xyxy, point_2d=m.contact_pixel, visible_features=m.appearance,
            ) for m in selected),
            projected_positions=tuple(p.point.world_position for m in selected
                                      if (p := projected.get(m.observation_id)) is not None
                                      and p.point is not None),
            region_ids=tuple(dict.fromkeys(r for m in selected
                                          for r in projected[m.observation_id].region_ids)),
            producer_version=perception.producer_version,
            uncertainty="Pixel components may be partial, merged or locally misassociated.",
        ))
    events = []
    for hypothesis in inference.association_hypotheses:
        event_ref = opaque_ref("event", *scope_parts(scope), hypothesis.hypothesis_id)
        events.append(EventView(
            event_ref=event_ref,
            association_ref=opaque_ref("association", *scope_parts(scope),
                                       hypothesis.hypothesis_id),
            canonical_event_id=hypothesis.event_id, kind=hypothesis.kind,
            camera_ids=hypothesis.camera_ids,
            camera_refs=tuple(camera_refs[c] for c in hypothesis.camera_ids),
            time_range=hypothesis.time_range,
            observation_refs=tuple(obs_refs[o] for o in hypothesis.original_observation_ids
                                   if o in obs_refs),
            evidence_refs=tuple(opaque_ref("measurement", *scope_parts(scope), p)
                                for p in hypothesis.pixel_observation_ids),
            media_refs=tuple(dict.fromkeys(manifest.frame_links[f] for f in hypothesis.frame_refs)),
            region_ids=hypothesis.region_ids, candidate_count=hypothesis.candidate_count,
            hypothesis_count=hypothesis.trajectory_hypothesis_count,
            association_hypothesis_count=len(inference.association_hypotheses),
            termination_reason=(str(hypothesis.termination_reason)
                                if hypothesis.termination_reason else hypothesis.status),
            complete=hypothesis.complete, uncertainty=hypothesis.uncertainty,
            detail_ref=event_ref,
            replay_ref=(opaque_ref("replay", *scope_parts(scope), hypothesis.event_id)
                        if hypothesis.event_id else None),
        ))
    return tuple(observations), tuple(events)


def load_facades(root: Path, *, storage: Literal["MEMORY", "LOCAL_JSON"] = "LOCAL_JSON"
                 ) -> tuple[AgentFacade, ...]:
    """Read frozen inference and snapshots; serving never imports GT or reruns producer."""
    root = root.resolve()
    registry = LocationRegistry.model_validate_json((root / "registry.json").read_bytes())
    manifest = RunManifest.model_validate_json((root / "run_manifest.json").read_bytes())
    if registry.sha256 != manifest.registry_sha256:
        raise ValueError("registry freeze mismatch")
    store = RegistryStore(registry, root)
    if manifest.scope not in tuple(m.scope for m in registry.models):
        raise ValueError("scope is not registered")
    if manifest.source_sha256 != manifest.scope.source_sha256:
        raise ValueError("source scope mismatch")
    if digest({"generator": manifest.algorithm_hashes["engineering/synthetic.py"],
               "model_sha256": manifest.model_source_sha256}) != manifest.source_sha256:
        raise ValueError("model source materialization mismatch")
    for frame in store.query_frames(manifest.scope):
        store.media_bytes(manifest.scope, frame.media_ref)
    frames_by_ref = {f.media_ref: f for f in store.query_frames(manifest.scope)}
    if set(manifest.frame_links.values()) != set(frames_by_ref) or len(
        manifest.frame_links,
    ) != len(frames_by_ref):
        raise ValueError("frame links must preserve the complete camera index")
    bound_frames = tuple(RGBFrame(
        media_ref=original_ref, camera_id=frames_by_ref[media_ref].camera_id,
        timestamp=frames_by_ref[media_ref].timestamp,
        path=root / frames_by_ref[media_ref].relative_path,
        sha256=frames_by_ref[media_ref].sha256, width=frames_by_ref[media_ref].width,
        height=frames_by_ref[media_ref].height,
    ) for original_ref, media_ref in manifest.frame_links.items())
    input_hash = frame_manifest_sha256(bound_frames)
    media_hash = digest([(f.media_ref, f.sha256) for f in store.query_frames(manifest.scope)])
    context = SyntheticStaticContext.model_validate_json(
        (root / "static_context.json").read_bytes(),
    )
    config = EngineeringConfig.model_validate_json((root / "engineering_config.json").read_bytes())
    if manifest.algorithm_hashes != algorithm_hashes():
        raise ValueError("algorithm implementation mismatch")
    if not manifest.receipts or len({r.binding.observation_mode for r in manifest.receipts}) != len(
        manifest.receipts,
    ):
        raise ValueError("run modes require unique freeze receipts")
    if {r.binding.observation_mode for r in manifest.receipts} != set(config.input_modes):
        raise ValueError("configured input modes must match receipts")
    facades = []
    for receipt in manifest.receipts:
        mode = receipt.binding.observation_mode
        envelope = json.loads((root / f"input_{mode}.json").read_bytes())
        if digest(envelope) != manifest.input_envelope_hashes[mode]:
            raise ValueError("input envelope freeze mismatch")
        perception = PerceptionResult.model_validate_json(
            (root / f"perception_{mode}.json").read_bytes(),
        )
        bundle = InferenceBundle.model_validate_json((root / f"inference_{mode}.json").read_bytes())
        if (receipt.binding.registry_sha256 != registry.sha256
            or receipt.binding.dataset_sha256 != perception.input_manifest_sha256
            or receipt.binding.dataset_sha256 != input_hash
            or receipt.binding.producer_sha256 != perception.producer_sha256
            or bundle.producer_sha256 != perception.producer_sha256
            or perception.producer_sha256 != manifest.algorithm_hashes["engineering/perception.py"]
            or (perception.model_id, perception.run_id) != (manifest.scope.model_id,
                                                           manifest.scope.run_id)
            or receipt.binding.config_sha256 != manifest.config_sha256
            or receipt.binding.media_sha256 != media_hash
            or receipt.binding.source_ref != opaque_ref("source", manifest.scope.source_id,
                                                         manifest.scope.source_sha256)
            or bundle.input_manifest_sha256 != perception.input_manifest_sha256
            or bundle.static_context_sha256 != digest(context)
            or bundle.scope.source_ref != receipt.binding.source_ref
            or context.source_sha256 != manifest.scope.source_sha256
            or context.context_sha256 != manifest.scope.spatial_context_sha256
            or effective_config_hash(config, manifest.generator_config_sha256, context,
                                     bundle.policy, manifest.algorithm_hashes)
            != manifest.config_sha256
            or (bundle.scope.place_id, bundle.scope.model_id, bundle.scope.model_revision,
                bundle.scope.run_id, bundle.scope.clock_id, bundle.scope.source_sha256,
                bundle.scope.context_sha256, bundle.scope.spatial_context_id) != (
                    manifest.scope.place_id, manifest.scope.model_id, manifest.scope.model_revision,
                    manifest.scope.run_id, manifest.scope.clock_id, manifest.scope.source_sha256,
                    manifest.scope.spatial_context_sha256, manifest.scope.spatial_context_id)):
            raise ValueError("run input freeze mismatch")
        for measurement in perception.measurements:
            frame = frames_by_ref[manifest.frame_links[measurement.frame_ref]]
            if (measurement.camera_id, measurement.timestamp, measurement.input_sha256,
                measurement.model_id, measurement.run_id) != (
                    frame.camera_id, frame.timestamp, frame.sha256, manifest.scope.model_id,
                    manifest.scope.run_id):
                raise ValueError("pixel measurement source reference mismatch")
        guard = SessionGuard(receipt.binding)
        guard.freeze(receipt, bundle, perception.model_dump(mode="json"))
        path = root / f"snapshot_{mode}.json"
        if not path.is_file():
            raise ValueError("canonical snapshot reference is missing")
        repository = (LocalJsonRepository(path) if storage == "LOCAL_JSON"
                      else InMemoryRepository(bundle.snapshot))
        if repository.snapshot() != bundle.snapshot:
            raise ValueError("canonical snapshot freeze mismatch")
        observations, events = _views(registry, manifest, perception, bundle)
        facades.append(AgentFacade(store, manifest.scope, guard, repository.snapshot(),
                                   observations, events))
    return tuple(facades)


def mock_agent(facade: AgentFacade) -> dict[str, object]:
    """A deterministic typed tool workflow; the service supplies geometry/results."""
    session = {"session_ref": facade.guard.session_ref}
    transcript: list[dict[str, object]] = []

    def call(tool: str, **args: object) -> dict[str, object]:
        response = facade.invoke(tool, session | args)  # type: ignore[arg-type]
        transcript.append({"tool": tool, "request": session | args, "response": response})
        return response

    call("resolve_place", query="Synthetic lab")
    call("list_cameras")
    call("query_observations", time_range=[0, 30])
    call("query_events", time_range=[0, 30])
    # Include an actual reconstructed gap, not just a pre-recorded display.
    event = next((e for e in facade.events if e.replay_ref and e.candidate_count),
                 facade.events[0] if facade.events else None)
    if event:
        call("get_event_summary", event_ref=event.event_ref)
        call("get_event_detail", event_ref=event.event_ref)
        if event.media_refs:
            media = call("get_media", media_ref=event.media_refs[0])
            # Curated tool traces retain image hash and opaque ref, never raw media bytes.
            media.pop("content_base64", None)
        if event.replay_ref:
            call("get_replay", event_ref=event.event_ref,
                 timestamp=sum(event.time_range) / 2)
    return {"context": facade.context(), "transcript": transcript, "logs": facade.logs}


def materialize_run(root: Path, config_path: Path, *, run_id: str) -> RunManifest:
    """Both modes share images/config/population; only photos-only recomputes pixels."""
    config = EngineeringConfig.model_validate_json(config_path.read_bytes())
    root = root.resolve()
    if (root / "run_manifest.json").exists():
        raise ValueError("run already frozen; choose a new run output or use serve/demo")
    package = generate_sequence(root, run_id=run_id, model_id=config.model_id,
                                frame_count=config.frame_count, fps=config.fps)
    registry, scope, links = _catalog(package, root)
    context, policy = static_context(package), AssociationPolicy()
    implementations = algorithm_hashes()
    config_hash = effective_config_hash(config, package.config_sha256, context, policy,
                                        implementations)
    stored = produce_perception(package.frames, model_id=package.model_id, run_id=run_id)
    receipts, mode_metrics = [], []
    input_hashes: dict[Mode, str] = {}
    _write(root / "registry.json", registry)
    _write(root / "static_context.json", context)
    _write(root / "engineering_config.json", config)
    for mode in config.input_modes:
        perception = (produce_perception(package.frames, model_id=package.model_id, run_id=run_id)
                      if mode == "photos_only" else stored)
        inference_scope = InferenceScope(
            place_id=scope.place_id, model_id=scope.model_id, model_revision=scope.model_revision,
            run_id=run_id, clock_id=scope.clock_id, source_ref=opaque_ref("source", scope.source_id,
                                                                      scope.source_sha256),
            source_sha256=scope.source_sha256, spatial_context_id=scope.spatial_context_id,
            context_sha256=scope.spatial_context_sha256,
        )
        binding = RunBinding(
            place_id=scope.place_id, model_id=scope.model_id, model_revision=scope.model_revision,
            source_ref=inference_scope.source_ref, spatial_context_id=scope.spatial_context_id,
            run_id=run_id, clock_id=scope.clock_id, observation_mode=mode,
            registry_version=registry.schema_version,
            dataset_sha256=perception.input_manifest_sha256,
            config_sha256=config_hash, producer_sha256=perception.producer_sha256,
            registry_sha256=registry.sha256,
            media_sha256=digest([(f.media_ref, f.sha256) for f in registry.frames]),
        )
        input_guard = SessionGuard(binding)
        envelope: dict[str, object] = {
            "task_context": input_guard.context(tuple(c.camera_ref for c in registry.cameras))
                .model_dump(mode="json"),
            "photos": [{"media_ref": f.media_ref, "camera_ref": f.camera_ref,
                        "camera_id": f.camera_id, "frame_id": f.frame_id,
                        "timestamp": f.timestamp, "input_sha256": f.sha256,
                        "width": f.width, "height": f.height, "annotations": "NONE"}
                       for f in registry.frames],
            "receiver": config.receiver, "decision_stage": config.decision_stage,
        }
        if mode == "photos_plus_observations":
            envelope["structured_measurements"] = [{
                "measurement_ref": opaque_ref("measurement", *scope_parts(scope), m.observation_id),
                "local_track_ref": opaque_ref("track", *scope_parts(scope), m.local_track_id),
                "media_ref": links[m.frame_ref], "camera_id": m.camera_id,
                "timestamp": m.timestamp, "bbox_xyxy": m.bbox_xyxy,
                "contact_pixel": m.contact_pixel, "appearance": m.appearance,
                "uncertainty": m.uncertainty, "status": m.status,
                "producer_version": m.producer_version, "input_sha256": m.input_sha256,
                "origin": "SYNTHETIC", "measurement_source": "RGB_PIXELS",
                "image_measurement": True,
            } for m in perception.measurements]
        input_hashes[mode] = digest(envelope)
        _write(root / f"input_{mode}.json", envelope)
        inference = build_inference(perception, scope=inference_scope, context=context,
                                    policy=policy)
        receipt = FreezeReceipt.create(binding, inference, perception.model_dump(mode="json"))
        receipts.append(receipt)
        _write(root / f"perception_{mode}.json", perception.model_dump(mode="json"))
        _write(root / f"inference_{mode}.json", inference)
        _write(root / f"snapshot_{mode}.json", inference.snapshot)
        mode_metrics.append({"mode": mode, "input_image_count": len(package.frames),
                             "image_producer_rerun": mode == "photos_only",
                             "measurement_count": len(perception.measurements),
                             "local_track_count": len(perception.tracks),
                             "measurement_sha256": digest(perception.model_dump(mode="json")),
                             "inference_sha256": digest(inference),
                             "canonical_gap_count": len(inference.snapshot.gaps),
                             "association_hypothesis_count": len(inference.association_hypotheses)})
    manifest = RunManifest(scope=scope, registry_sha256=registry.sha256,
                           source_sha256=scope.source_sha256, config_sha256=config_hash,
                           model_source_sha256=package.model_source_sha256,
                           generator_config_sha256=package.config_sha256,
                           algorithm_hashes=implementations,
                           frame_links=links, input_envelope_hashes=input_hashes,
                           receipts=tuple(receipts))
    _write(root / "run_manifest.json", manifest)
    facades = load_facades(root)
    for facade in facades:
        _write(root / f"mock_agent_{facade.guard.binding.observation_mode}.json",
               mock_agent(facade))
    _write(root / "mode_comparison.json", {
        "receiver": config.receiver, "decision_stage": config.decision_stage,
        "same_photos_task_population_static_context": True,
        "camera_retrieval_difference": "NONE_SAME_CAMERA_FRAME_INDEX",
        "observation_mode_difference": "INPUT_STRUCTURED_RGB_MEASUREMENTS_PRESENT_ONLY_IN_PLUS",
        "modes": mode_metrics, "formal_quality_metrics": "N/A",
        "precision": "Independent local evaluation follows inference freeze.",
        "external_model_calls": False,
    })
    return manifest
