"""Tiny fixed manifests exercise read-only scene adaptation without rendering."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from amidst.domain.camera import Camera
from amidst.domain.geometry import Plane
from amidst.engineering.access import FreezeReceipt, RunBinding, SessionGuard, digest
from amidst.engineering.association import ConfiguredRegion, SyntheticStaticContext
from amidst.engineering.local_index import ScopedTopology
from amidst.engineering.local_service import LocalPilotService
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
from amidst.workbench.scenes import SceneAdapter, baseline_objects, load_catalog


def fixture_scene(tmp_path: Path) -> SceneAdapter:
    scope = ResourceScope(place_id="lab", model_id="fixture", model_revision="1", run_id="run",
                          source_id="source", source_sha256="a" * 64,
                          spatial_context_id="ground", spatial_context_sha256="b" * 64,
                          clock_id="seconds")
    affine = PixelPlaneCalibration(camera_id="A", width=10, height=10,
                                   ground_to_pixel=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
    camera = CameraEntry(scope=scope, camera_id="A",
                         camera_ref=opaque_ref("camera", *scope_parts(scope), "A"),
                         authority="SYNTHETIC_CONFIG", affine_calibration=affine,
                         calibration_sha256=content_hash(affine.model_dump(mode="json")))
    # Byte identity is sufficient for adapter tests; no image producer is run.
    payload = b"fixed-rgb-byte-fixture"
    (tmp_path / "rgb.png").write_bytes(payload)
    frames = tuple(MediaFrame(
        scope=scope, camera_id="A", camera_ref=camera.camera_ref,
        media_ref=opaque_ref("media", *scope_parts(scope), "A", str(i),
                             sha256(payload).hexdigest()),
        frame_id=i, timestamp=float(i), relative_path="rgb.png", sha256=sha256(payload).hexdigest(),
        size_bytes=len(payload), width=10, height=10,
    ) for i in (0, 1, 100))
    model = LocationModel(
        scope=scope, display_name="Fixture", authority="SYNTHETIC_CONFIG",
        coordinates=CoordinateBinding(
            native_units="METRES", metres_per_unit=1,
            normalization_policy="IDENTITY", authority="SYNTHETIC_CONFIG"),
        clock=ClockBinding(clock_id="seconds", mapping_sha256="c" * 64,
                           authority="SYNTHETIC_CONFIG"))
    registry = LocationRegistry(models=(model,), cameras=(camera,), frames=frames)
    binding = RunBinding(
        place_id=scope.place_id, model_id=scope.model_id, model_revision=scope.model_revision,
        source_ref=opaque_ref("source", scope.source_id, scope.source_sha256),
        spatial_context_id=scope.spatial_context_id, run_id=scope.run_id, clock_id=scope.clock_id,
        observation_mode="photos_plus_observations", dataset_sha256="d" * 64,
        config_sha256="e" * 64, producer_sha256="f" * 64, registry_sha256=registry.sha256,
        media_sha256=digest([f.sha256 for f in frames]))
    guard = SessionGuard(binding)
    guard.freeze(FreezeReceipt.create(binding, {}, {}), {}, {})
    events = tuple({"event_ref": opaque_ref("event", str(i)), "camera_refs": [camera.camera_ref],
                    "camera_ids": ["A"], "time_range": [float(i), float(i)], "region_ids": [],
                    "media_refs": [frames[0].media_ref], "projected_path": [[1, 1, 0]],
                    "candidates": [], "trajectories": [], "uncertainty": "provisional"}
                   for i in (0, 100))
    service = LocalPilotService(RegistryStore(registry, tmp_path), scope, guard, (), events,
                                ScopedTopology(scope=scope, camera_ids=("A",)))
    context = SyntheticStaticContext(
        spatial_context_id="ground", source_sha256=scope.source_sha256,
        context_sha256=scope.spatial_context_sha256,
        ground_plane=Plane(plane_id="floor", point=(0, 0, 0), normal=(0, 0, 1), floor_id="f"),
        walkable_bounds_xy_m=(0, 0, 5, 5), calibrations=(),
        regions=(ConfiguredRegion(region_id="r", floor_id="f", bounds_xy_m=(0, 0, 5, 5)),),
        allowed_camera_pairs=(), detour_waypoints_m=())
    return SceneAdapter(scene_id="fixture", label="Fixture", description="small fixture",
                        service=service, context=context, evidence_level="E0",
                        evaluation_path=tmp_path / "evaluation.json")


def test_common_snapshot_is_source_bound_and_affine_pose_is_unknown(tmp_path: Path) -> None:
    scene = fixture_scene(tmp_path)
    snapshot = scene.snapshot()
    assert snapshot["coordinates"]["normalized_units"] == "METRES"
    assert snapshot["clock"]["unit"] == "SECONDS"
    assert snapshot["cameras"][0]["position"] is None
    camera = next(o for o in snapshot["objects"] if o["kind"] == "CAMERA")
    assert camera["geometry"]["points"] == []
    assert "geometry" not in camera["editable_fields"]
    exported = json.dumps(snapshot)
    assert str(tmp_path) not in exported
    assert "recipe" not in exported and "actor_identity" not in exported
    snapshot["objects"][0]["label"] = "mutated"
    assert scene.snapshot()["objects"][0]["label"] != "mutated"


def test_queries_use_interval_index_and_detail_media_use_direct_refs(tmp_path: Path) -> None:
    scene = fixture_scene(tmp_path)
    response = scene.query("A", 0, 1)
    assert len(response["events"]) == 1
    assert response["retrieval"]["events"]["records_read"] == 1
    assert response["retrieval"]["records_read"] == 1
    assert response["retrieval"]["truncated"] is False
    assert response["retrieval"]["global_scan"] is False
    event = scene.event(response["events"][0]["event_ref"])
    assert event["projected_path"] == [[1, 1, 0]]
    assert scene.media(event["media_refs"][0]) == ("image/png", b"fixed-rgb-byte-fixture")
    with pytest.raises(ValueError):
        scene.event(opaque_ref("event", "foreign"))
    with pytest.raises(ValueError, match="MEDIA_SCOPE_DENIED"):
        scene.media(opaque_ref("media", "foreign"))
    with pytest.raises(ValueError, match="CAMERA_SCOPE_DENIED"):
        scene.query("foreign", 0, 1)
    with pytest.raises(ValueError, match="INVALID_TIME_RANGE"):
        scene.query("A", 2, 1)


def test_retrieval_totals_retain_truncation_from_either_stream(tmp_path: Path) -> None:
    scene = fixture_scene(tmp_path)
    # Hundreds of independent registered event intervals trigger the real 128-row bound.
    service = scene.service
    camera = next(iter(service.cameras.values()))
    events = tuple({"event_ref": opaque_ref("event", str(i)),
                    "camera_refs": [camera.camera_ref], "camera_ids": ["A"],
                    "time_range": [0.0, 1.0], "region_ids": [], "media_refs": []}
                   for i in range(180))
    scene.service = LocalPilotService(service.store, service.scope, service.guard,
                                      (), events, ScopedTopology(scope=service.scope,
                                                                 camera_ids=("A",)))
    response = scene.query("A", 0, 1)
    receipt = response["retrieval"]
    assert receipt["truncated"] and receipt["events"]["truncated"]
    assert receipt["records_read"] == receipt["events"]["records_read"] == 128
    assert receipt["index_entries_touched"] == receipt["events"]["index_entries_touched"]
    assert receipt["frames_read"] == receipt["bytes_read"] == 0
    assert receipt["time_range"] == [0, 1]


def test_frame_lookup_labels_actual_timestamp_and_missing_data(tmp_path: Path) -> None:
    scene = fixture_scene(tmp_path)
    frame = scene.frames(["A"], 0.4)["frames"][0]
    assert frame["timestamp"] == 0 and frame["requested_timestamp"] == 0.4
    assert frame["status"] == "NEAREST_AVAILABLE"
    assert scene.frames(["A"], 1)["frames"][0]["status"] == "EXACT"
    assert scene.frames(["A"], 101)["frames"][0]["status"] == "MISSING"
    assert scene.frames(["A"], 50)["frames"][0]["status"] == "MISSING"
    with pytest.raises(ValueError, match="CAMERA_SCOPE_DENIED"):
        scene.frames(["A", "A"], 0)


def test_evaluation_stays_optional_and_checks_same_run_binding(tmp_path: Path) -> None:
    scene = fixture_scene(tmp_path)
    assert scene.evaluation()["status"] == "UNAVAILABLE"
    evaluation = {"run_id": "run", "model_id": "fixture", "dataset_sha256": "d" * 64,
                  "config_sha256": "e" * 64, "status": "SYNTHETIC_DIAGNOSTIC"}
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(evaluation))
    assert scene.evaluation() == evaluation
    evaluation["run_id"] = "another"
    path.write_text(json.dumps(evaluation))
    assert scene.evaluation() == {"status": "STALE", "reason": "EVALUATION_BINDING_MISMATCH"}


def test_missing_and_invalid_sources_never_regenerate(tmp_path: Path) -> None:
    assert load_catalog(tmp_path) == {}
    with pytest.raises(ValueError, match="UNKNOWN_SCENE_ADAPTER"):
        load_catalog(tmp_path, {"untrusted": tmp_path})
    bad = tmp_path / "bad"
    bad.mkdir()
    with pytest.raises(ValueError, match="SCENE_SOURCE_UNAVAILABLE:local-camera"):
        load_catalog(tmp_path, {"local-camera": bad})
    assert list(bad.iterdir()) == []


def test_pinhole_geometry_uses_actual_source_pose(tmp_path: Path) -> None:
    scene = fixture_scene(tmp_path)
    scope = scene.service.scope
    camera = Camera(camera_id="P", camera_to_world=((1, 0, 0, 3), (0, 1, 0, 4),
                    (0, 0, 1, 5), (0, 0, 0, 1)), fx=100, fy=101, cx=50, cy=40,
                    width=100, height=80)
    entry = CameraEntry(scope=scope, camera_id="P",
                        camera_ref=opaque_ref("camera", *scope_parts(scope), "P"),
                        authority="SYNTHETIC_CONFIG", calibration=camera,
                        calibration_sha256=content_hash(camera.model_dump(mode="json")))
    context = SyntheticStaticContext(
        spatial_context_id="ground", source_sha256="a" * 64, context_sha256="b" * 64,
        ground_plane=Plane(plane_id="floor", point=(0, 0, 0), normal=(0, 0, 1), floor_id="f"),
        walkable_bounds_xy_m=(0, 0, 5, 5), calibrations=(), regions=(),
        allowed_camera_pairs=(), detour_waypoints_m=())
    obj = baseline_objects(context, (entry,))[-1]
    assert obj["geometry"]["points"] == [[3.0, 4.0, 5.0]]
    assert obj["properties"]["fx"] == 100
    with pytest.raises(ValueError, match="SCENE_SOURCE_MISMATCH"):
        SceneAdapter(scene_id="wrong", label="bad", description="bad", service=scene.service,
                     context=context.model_copy(update={"source_sha256": "f" * 64}),
                     evidence_level="E1")


def test_server_manifest_aliases_reuse_adapter_without_mutating_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = fixture_scene(tmp_path)
    monkeypatch.setattr("amidst.workbench.scenes.load_local_camera", lambda root: source)
    manifest = {"schema_version": "workbench.catalog.v1", "scenes": [
        {"scene_id": name, "adapter": "local_camera", "checkpoint": ".",
         "label": name.upper(), "description": "Configured alternate scene"}
        for name in ("first", "second")
    ]}
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(manifest))
    catalog = load_catalog(tmp_path, manifest_path=path)
    assert list(catalog) == ["first", "second"]
    assert catalog["first"].snapshot()["scene_id"] == "first"
    assert catalog["second"].snapshot()["label"] == "SECOND"
    assert all(s.source_hash == source.source_hash and s.run_id == source.run_id
               for s in catalog.values())
    assert source.scene_id == "fixture"
    assert source.snapshot()["label"] == "Fixture"


@pytest.mark.parametrize("change,expected", [
    ({"adapter": "shell"}, "UNKNOWN_SCENE_ADAPTER"),
    ({"checkpoint": "../outside"}, "INVALID_SCENE_CHECKPOINT"),
    ({"checkpoint": "/private/tmp"}, "INVALID_SCENE_CHECKPOINT"),
    ({"scene_id": "bad/id"}, "INVALID_SCENE_ID"),
])
def test_server_manifest_rejects_invalid_adapter_or_path(
    tmp_path: Path, change: dict[str, Any], expected: str,
) -> None:
    entry = {"scene_id": "one", "adapter": "local_camera", "checkpoint": "unused",
             "label": "One", "description": "One scene"} | change
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": "workbench.catalog.v1", "scenes": [entry]}))
    with pytest.raises(ValueError, match=expected):
        load_catalog(tmp_path, manifest_path=path)


def test_server_manifest_duplicate_and_missing_manifest_fail_closed(tmp_path: Path) -> None:
    entry = {"scene_id": "one", "adapter": "local_camera", "checkpoint": "unused",
             "label": "One", "description": "One scene"}
    path = tmp_path / "catalog.json"
    with pytest.raises(ValueError, match="SCENE_CATALOG_UNAVAILABLE"):
        load_catalog(tmp_path, manifest_path=path)
    path.write_text(json.dumps({"schema_version": "workbench.catalog.v1",
                                "scenes": [entry, entry]}))
    with pytest.raises(ValueError, match="DUPLICATE_SCENE_ID"):
        load_catalog(tmp_path, manifest_path=path)
