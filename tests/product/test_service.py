"""Product service guards over real RGB descriptors and immutable indexed fixtures.

No simulator sidecar or GT is read. The fixture's calibrated floor and synthetic
routes are configured independently for exercising contracts, never a benchmark.
"""

import json
from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from amidst.domain.trajectory import CandidateTrajectory, Event, TerminationReason
from amidst.engineering.access import FreezeReceipt, RunBinding, SessionGuard, digest
from amidst.engineering.facade import ToolFailure
from amidst.engineering.local_index import CameraLink, CameraRegions, ScopedTopology
from amidst.engineering.local_service import LocalPilotService
from amidst.engineering.perception import RGBFrame, produce_perception
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
    opaque_ref,
    scope_parts,
)
from amidst.product.appearance import build_appearance_bundle
from amidst.product.contracts import EventDetail, ObservationDetail
from amidst.product.service import ProductService
from amidst.product.stitching import build_stitch_bundle
from amidst.product.store import CanonicalRecord, ProductScope, RecordSetReceipt, SQLiteProductStore
from amidst.reconstruction.blind_gap import BlindGapReconstructor


@pytest.fixture
def service_factory(tmp_path: Path):
    scope = ResourceScope(
        place_id="fixture",
        model_id="rgb-fixture",
        model_revision="1",
        run_id="service-v1",
        source_id="rgb-fixture-source",
        source_sha256="a" * 64,
        spatial_context_id="affine-ground",
        spatial_context_sha256="b" * 64,
        clock_id="configured-seconds",
    )
    cameras = tuple(
        CameraEntry(
            scope=scope,
            camera_id=camera,
            camera_ref=opaque_ref("camera", *scope_parts(scope), camera),
            coverage_status="CONFIGURED_SYNTHETIC",
            region_ids=("west",),
            authority="SYNTHETIC_CONFIG",
            affine_calibration=PixelPlaneCalibration(
                camera_id=camera, width=340, height=140, ground_to_pixel=((100, 0, 0), (0, 100, 0))
            ),
            calibration_sha256=digest(
                PixelPlaneCalibration(
                    camera_id=camera,
                    width=340,
                    height=140,
                    ground_to_pixel=((100, 0, 0), (0, 100, 0)),
                )
            ),
        )
        for camera in ("CAM_A", "CAM_B")
    )
    frames, media, links = [], [], {}
    for index in range(10):
        path = tmp_path / f"rgb-{index}.png"
        image = Image.new("RGB", (340, 140), (12, 20, 30))
        draw = ImageDraw.Draw(image)
        for initial in (20, 180):
            x = initial + index * 12
            draw.rectangle((x, 80, x + 10, 110), fill=(200, 45, 45))
        image.save(path)
        fingerprint = sha256(path.read_bytes()).hexdigest()
        ref = opaque_ref("media", *scope_parts(scope), "CAM_A", str(index), fingerprint)
        original = f"frame:{index}"
        links[original] = ref
        frames.append(
            RGBFrame(
                media_ref=original,
                camera_id="CAM_A",
                timestamp=index / 5,
                path=path,
                sha256=fingerprint,
                width=340,
                height=140,
            )
        )
        media.append(
            MediaFrame(
                scope=scope,
                camera_id="CAM_A",
                camera_ref=cameras[0].camera_ref,
                media_ref=ref,
                frame_id=index,
                timestamp=index / 5,
                relative_path=path.name,
                sha256=fingerprint,
                size_bytes=path.stat().st_size,
                width=340,
                height=140,
            )
        )
    model = LocationModel(
        scope=scope,
        display_name="RGB fixture",
        coordinates=CoordinateBinding(
            native_units="METRES",
            metres_per_unit=1,
            normalization_policy="IDENTITY",
            authority="SYNTHETIC_CONFIG",
        ),
        clock=ClockBinding(
            clock_id=scope.clock_id, mapping_sha256="c" * 64, authority="SYNTHETIC_CONFIG"
        ),
        authority="SYNTHETIC_CONFIG",
    )
    registry = LocationRegistry(models=(model,), cameras=cameras, frames=tuple(media))
    store = RegistryStore(registry, tmp_path)
    perception = produce_perception(frames, model_id=scope.model_id, run_id=scope.run_id)
    descriptors = build_appearance_bundle(
        perception, store, scope, links, input_config_sha256="d" * 64
    )
    stitches = build_stitch_bundle(perception, descriptors, scope=scope)
    pixels = {m.observation_id: m for m in perception.measurements}
    observations = []
    for track in perception.tracks:
        rows = [pixels[ref] for ref in track.observation_ids]
        observations.append(
            ObservationDetail(
                observation_ref=opaque_ref(
                    "observation", *scope_parts(scope), track.local_track_id
                ),
                local_track_ref=opaque_ref("track", *scope_parts(scope), track.local_track_id),
                camera_refs=(cameras[0].camera_ref,),
                camera_ids=("CAM_A",),
                time_range=(rows[0].timestamp, rows[-1].timestamp),
                media_refs=tuple(links[m.frame_ref] for m in rows),
                measurements=tuple(
                    {
                        "frame_ref": links[m.frame_ref],
                        "timestamp": m.timestamp,
                        "bbox": m.bbox_xyxy,
                        "point_2d": m.contact_pixel,
                        "visible_features": m.appearance,
                    }
                    for m in rows
                ),
                region_ids=("west",),
                projected_path=tuple(
                    (m.contact_pixel[0] / 100, m.contact_pixel[1] / 100, 0) for m in rows
                ),
                origin="SYNTHETIC",
                image_measurement=True,
                authority="RGB_PIXELS_WITH_SYNTHETIC_CONFIG",
                uncertainty="Configured RGB fixture; local tracks remain provisional.",
            ).model_dump(mode="json")
        )
    assert len(observations) == 2
    candidates = tuple(
        CandidateTrajectory(
            candidate_id=f"candidate:fixture-{index}",
            start_observation_id="start",
            end_observation_id="end",
            polyline=path,
            path_length=length,
            minimum_travel_time=length / 3,
            estimated_travel_time=2,
            spatial_cost=length,
        )
        for index, path, length in (
            (0, ((0, 0, 0), (1, 0, 0)), 1),
            (1, ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)), 3),
        )
    )
    event = BlindGapReconstructor().reconstruct(
        Event(
            event_id="canonical-fixture-gap",
            target_id="provisional-fixture",
            time_range=(0, 2),
            observation_ids=("start", "end"),
            candidates=candidates,
            termination_reason=TerminationReason.COMPLETE,
        )
    )
    detail = EventDetail(
        event_ref=opaque_ref("event", *scope_parts(scope), "gap"),
        event_id="canonical-fixture-gap",
        kind="INFERRED_GAP_ALTERNATIVES",
        time_range=(0, 2),
        local_track_refs=tuple(o["local_track_ref"] for o in observations),
        segment_refs=tuple(opaque_ref("segment", o["observation_ref"]) for o in observations),
        association_refs=(opaque_ref("association", "fixture"),),
        association_states=(),
        source_frames=(),
        missing_evidence=(),
        region_ids=("west",),
        portal_ids=(),
        corner_ids=(),
        rule_version="fixture-v1",
        config_version="fixture-v1",
        config_sha256="d" * 64,
        supports=("CONFIGURED_FIXTURE",),
        conflicts=(),
        alternatives=tuple(c.candidate_id for c in candidates),
        uncertainty="Both configured alternatives retained.",
        evidence_state="INFERRED_GAP",
        canonical_event_id=event.event_id,
        termination_reason="COMPLETE",
        complete=True,
        detail_ref=opaque_ref("event", *scope_parts(scope), "gap"),
        replay_ref=opaque_ref("replay", *scope_parts(scope), "gap"),
        origin="SYNTHETIC",
        authority="CONFIGURED_PIXEL_BEHAVIOR_HYPOTHESIS",
        camera_refs=(cameras[0].camera_ref,),
        camera_ids=("CAM_A",),
        media_refs=(media[0].media_ref,),
        projected_path=(),
        candidates=event.candidates,
        trajectories=event.trajectories,
    ).model_dump(mode="json")
    topology = ScopedTopology(
        scope=scope,
        camera_ids=("CAM_A", "CAM_B"),
        camera_links=(CameraLink(from_camera_id="CAM_A", to_camera_id="CAM_B"),),
        camera_regions=tuple(
            CameraRegions(camera_id=c.camera_id, region_ids=("west",)) for c in cameras
        ),
        topology_complete=True,
    )
    repositories = []

    def factory(mode="photos_only", *, results=True, bundle=None, stitch_data=None, event_count=1):
        binding = RunBinding(
            place_id=scope.place_id,
            model_id=scope.model_id,
            model_revision=scope.model_revision,
            source_ref=opaque_ref("source", scope.source_id, scope.source_sha256),
            spatial_context_id=scope.spatial_context_id,
            run_id=scope.run_id,
            clock_id=scope.clock_id,
            observation_mode=mode,
            dataset_sha256=descriptors.dataset_sha256,
            config_sha256="d" * 64,
            producer_sha256=descriptors.producer_sha256,
            registry_sha256=registry.sha256,
            media_sha256=descriptors.media_sha256,
        )
        receipt = FreezeReceipt.create(
            binding, {"fixture": "inference"}, perception.model_dump(mode="json")
        )
        guard = SessionGuard(binding)
        if results:
            guard.freeze(receipt, {"fixture": "inference"}, perception.model_dump(mode="json"))
        events = tuple(
            detail
            | {
                "event_ref": opaque_ref(
                    "event", *scope_parts(scope), "gap" if n == 0 else f"gap-{n}"
                ),
                "event_id": "canonical-fixture-gap" if n == 0 else f"canonical-fixture-gap-{n}",
                "detail_ref": opaque_ref(
                    "event", *scope_parts(scope), "gap" if n == 0 else f"gap-{n}"
                ),
                "replay_ref": opaque_ref(
                    "replay", *scope_parts(scope), "gap" if n == 0 else f"gap-{n}"
                ),
            }
            for n in range(event_count)
        )
        base = LocalPilotService(store, scope, guard, tuple(observations), events, topology)
        product_scope = ProductScope(
            resource_scope=scope,
            observation_mode=mode,
            dataset_sha256=binding.dataset_sha256,
            config_sha256=binding.config_sha256,
            producer_sha256=binding.producer_sha256,
            registry_sha256=registry.sha256,
            media_sha256=binding.media_sha256,
            inference_sha256=receipt.inference_sha256,
            freeze_sha256=receipt.receipt_sha256,
        )
        repository = SQLiteProductStore(tmp_path / f"store-{len(repositories)}.sqlite")
        repositories.append(repository)
        records = tuple(
            CanonicalRecord.create(
                run_ref=product_scope.run_ref,
                kind="OBSERVATION",
                record_ref=o["observation_ref"],
                camera_ids=("CAM_A",),
                time_range=tuple(o["time_range"]),
                region_ids=("west",),
                payload=o,
            )
            for o in observations
        ) + tuple(
            CanonicalRecord.create(
                run_ref=product_scope.run_ref,
                kind="EVENT",
                record_ref=item["event_ref"],
                camera_ids=("CAM_A",),
                time_range=(0, 2),
                region_ids=("west",),
                payload=item,
            )
            for item in events
        )
        repository.import_records(
            product_scope, records, RecordSetReceipt.create(product_scope, records)
        )
        return ProductService(
            base,
            repository,
            product_scope,
            bundle or descriptors,
            product_freeze_ref="product-freeze-" + "e" * 64,
            stitches=stitch_data or stitches.model_dump(mode="json"),
        )

    factory.observations = observations
    factory.event = detail
    factory.descriptors = descriptors
    factory.stitches = stitches
    yield factory
    for repository in repositories:
        repository.close()


def args(service, **values):
    return {"session_ref": service.base.guard.session_ref} | values


@pytest.mark.parametrize("mode", ["photos_only", "photos_plus_observations"])
def test_input_old_and_new_tools_follow_stage_allowlist(service_factory, mode):
    service = service_factory(mode, results=False)
    obs = service_factory.observations[0]
    events = (
        "query_events",
        "get_event_summary",
        "get_event_detail",
        "get_replay",
        "get_observation_detail",
        "query_reachable_cameras",
        "propose_feasible_trajectories",
        "search_person_appearance",
        "get_stitch_hypotheses",
    )
    for tool in events:
        payload = {
            "query_events": {"camera_ref": obs["camera_refs"][0], "time_range": [0, 2]},
            "get_event_summary": {"event_ref": service_factory.event["event_ref"]},
            "get_event_detail": {"event_ref": service_factory.event["event_ref"]},
            "get_replay": {"event_ref": service_factory.event["event_ref"], "timestamp": 1},
            "get_observation_detail": {"observation_ref": obs["observation_ref"]},
            "query_reachable_cameras": {"camera_ref": obs["camera_refs"][0]},
            "propose_feasible_trajectories": {
                "camera_ref": obs["camera_refs"][0],
                "time_range": [0, 2],
            },
            "search_person_appearance": {
                "camera_ref": obs["camera_refs"][0],
                "time_range": [0, 2],
                "query_track_ref": obs["local_track_ref"],
            },
            "get_stitch_hypotheses": {"local_track_ref": obs["local_track_ref"]},
        }[tool]
        with pytest.raises(ToolFailure, match="STAGE_DENIED"):
            service.call(tool, args(service, **payload))
    request = args(service, camera_ref=obs["camera_refs"][0], time_range=[0, 2])
    if mode == "photos_only":
        with pytest.raises(ToolFailure, match="STAGE_DENIED"):
            service.call("query_observations", request)
    else:
        result = service.call("query_observations", request)
        assert result["items"]
        assert all(
            "projected_path" not in row and "region_ids" not in row for row in result["items"]
        )
        with pytest.raises(ToolFailure, match="STAGE_DENIED"):
            service.call("query_observations", request | {"region_id": "west"})
    assert "/Users/" not in json.dumps(service.logs)


def test_unknown_tool_bad_reference_and_extra_request_are_fixed_safe_errors(service_factory):
    service = service_factory()
    sentinel = "/Users/private/GT_SECRET"
    for tool, payload in (
        (sentinel, args(service)),
        ("get_media", args(service, media_ref=sentinel)),
        ("list_cameras", args(service, decision_stage="RESULTS", private_path=sentinel)),
        (
            "query_events",
            args(service, camera_ref=opaque_ref("camera", "other"), time_range=[0, 2]),
        ),
    ):
        with pytest.raises(ToolFailure) as error:
            service.call(tool, payload)
        assert sentinel not in str(error.value)
    assert sentinel not in json.dumps(service.logs)
    assert any(row["tool"] == "UNKNOWN_TOOL" for row in service.logs)


def test_local_anchor_and_cross_scope_are_required(service_factory):
    service = service_factory()
    with pytest.raises(ToolFailure, match="LOCAL_ANCHOR_REQUIRED"):
        service.call("query_events", args(service, time_range=[0, 2]))
    with pytest.raises(ToolFailure, match="SCOPE_DENIED"):
        service.call("list_cameras", {"session_ref": "session-" + "f" * 24})
    with pytest.raises(ToolFailure, match="REFERENCE_DENIED|INVALID_OR_UNAVAILABLE"):
        service.call("get_event_detail", args(service, event_ref=opaque_ref("event", "other-run")))


def test_canonical_paging_and_proposal_keep_ids_alternative_order(service_factory):
    service = service_factory()
    camera = service_factory.observations[0]["camera_refs"][0]
    first = service.call(
        "query_observations", args(service, camera_ref=camera, time_range=[0, 2], limit=1)
    )
    assert first["retrieval"]["truncated"] and first["retrieval"]["next_cursor"]
    second = service.call(
        "query_observations",
        args(
            service,
            camera_ref=camera,
            time_range=[0, 2],
            limit=1,
            cursor=first["retrieval"]["next_cursor"],
        ),
    )
    assert first["items"][0]["observation_ref"] != second["items"][0]["observation_ref"]
    summary = service.call(
        "propose_feasible_trajectories",
        args(
            service,
            camera_ref=camera,
            time_range=[1, 1],
            seed_refs=[first["items"][0]["observation_ref"]],
        ),
    )
    assert summary["items"][0]["event_id"] == service_factory.event["event_id"]
    assert summary["items"][0]["time_range"] == service_factory.event["time_range"]
    assert summary["items"][0]["alternatives"] == service_factory.event["alternatives"]
    detail = service.call(
        "get_event_detail", args(service, event_ref=service_factory.event["event_ref"])
    )
    assert detail["candidates"] == service_factory.event["candidates"]
    assert detail["trajectories"] == service_factory.event["trajectories"]


def test_appearance_public_scope_is_task_context_and_vectors_are_not_exported(service_factory):
    service = service_factory()
    obs = service_factory.observations[0]
    result = service.call(
        "search_person_appearance",
        args(
            service,
            camera_ref=obs["camera_refs"][0],
            time_range=[0, 2],
            query_track_ref=obs["local_track_ref"],
        ),
    )
    assert result["scope"]["session_ref"] == service.base.guard.session_ref
    assert "source_id" not in result["scope"]
    assert "vector" not in json.dumps(result)


def test_stitch_public_mappings_use_refs_and_do_not_export_internal_original_ids(service_factory):
    service = service_factory()
    track = service_factory.observations[0]["local_track_ref"]
    result = service.call("get_stitch_hypotheses", args(service, local_track_ref=track))
    assert result["items"] and result["provisional_only"]
    assert all(track in row["track_refs"] for row in result["items"])
    assert all(
        "original_track_ids" not in row and "original_observation_ids" not in row
        for row in result["items"]
    )
    assert all(
        row["confirmed_identity"] is False and row["creates_observed_gap_samples"] is False
        for row in result["items"]
    )


def test_descriptor_media_binding_is_checked_before_export(service_factory):
    bad = service_factory.descriptors.model_copy(update={"media_sha256": "f" * 64})
    stitched = service_factory.stitches.model_copy(update={"appearance_sha256": digest(bad)})
    with pytest.raises(ToolFailure, match="BINDING_DENIED"):
        service_factory(bundle=bad, stitch_data=stitched.model_dump(mode="json"))


def test_descriptor_input_config_is_bound_to_original_run(service_factory):
    bad = service_factory.descriptors.model_copy(update={"input_config_sha256": "f" * 64})
    stitched = service_factory.stitches.model_copy(update={"appearance_sha256": digest(bad)})
    with pytest.raises(ToolFailure, match="BINDING_DENIED"):
        service_factory(bundle=bad, stitch_data=stitched.model_dump(mode="json"))


def test_response_extra_fields_are_not_exported(service_factory, monkeypatch):
    service = service_factory()
    sentinel = "/Users/private/GT_SECRET"
    monkeypatch.setattr(
        service,
        "_invoke",
        lambda tool, request: {
            "scope": service.context().context.model_dump(mode="json"),
            "items": [],
            "complete": True,
            "private_source_archive": sentinel,
        },
    )
    with pytest.raises(ToolFailure, match="INVALID_OR_UNAVAILABLE"):
        service.call("resolve_place", args(service, query="lab"))
    assert sentinel not in json.dumps(service.logs)


def test_proposal_seed_filter_precedes_paging_and_cursor_keeps_scope(service_factory):
    service = service_factory(event_count=3)
    observation = service_factory.observations[0]
    payload = args(
        service,
        camera_ref=observation["camera_refs"][0],
        time_range=[0, 2],
        seed_refs=[observation["observation_ref"]],
        limit=1,
    )
    collected = []
    while True:
        page = service.call("propose_feasible_trajectories", payload)
        collected.extend(page["items"])
        if page["retrieval"]["next_cursor"] is None:
            break
        with pytest.raises(ToolFailure):
            service.call(
                "propose_feasible_trajectories",
                payload
                | {
                    "camera_ref": opaque_ref("camera", "other-run"),
                    "cursor": page["retrieval"]["next_cursor"],
                },
            )
        payload = payload | {"cursor": page["retrieval"]["next_cursor"]}
    assert len(collected) == 3 and len({row["event_ref"] for row in collected}) == 3
    assert all(row["alternatives"] == service_factory.event["alternatives"] for row in collected)
