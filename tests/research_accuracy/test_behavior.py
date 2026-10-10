"""V2 claims, retained unknowns and source-bound evidence counterexamples."""

from collections.abc import Sequence
from pathlib import Path

import pytest

from amidst.domain.geometry import Plane
from amidst.engineering.association import (
    AssociationPolicy,
    ConfiguredRegion,
    GroundCalibration,
    InferenceScope,
    SyntheticStaticContext,
    build_inference,
    content_sha256,
)
from amidst.engineering.local_behavior import (
    BehaviorConfig,
    BehaviorCorner,
    BehaviorPortal,
    LocalBehaviorBundle,
    compose_local_behaviors,
)
from amidst.engineering.perception import LocalTrack, Measurement, PerceptionResult
from amidst.research_accuracy.behavior import (
    BehaviorEvidencePolicy,
    behavior_config_sha256,
    compose_behaviors_v2,
    event_support_state,
)

HASH = "a" * 64
CONTEXT_HASH = "b" * 64


def setup() -> tuple[InferenceScope, SyntheticStaticContext, BehaviorConfig]:
    scope = InferenceScope(
        place_id="synthetic-lab", model_id="lab", model_revision="1", run_id="test-run",
        clock_id="configured-seconds", source_ref="source:lab", source_sha256=HASH,
        spatial_context_id="context:lab", context_sha256=CONTEXT_HASH)
    plane = Plane(plane_id="floor:lab", point=(0, 0, 0), normal=(0, 0, 1), floor_id="floor:0")
    context = SyntheticStaticContext(
        spatial_context_id="context:lab", source_sha256=HASH, context_sha256=CONTEXT_HASH,
        ground_plane=plane, walkable_bounds_xy_m=(0, 0, 12, 6),
        calibrations=tuple(GroundCalibration(
            camera_id=camera, plane=plane, affine_ground_to_pixel=((1, 0, 0), (0, 1, 0)))
            for camera in ("WEST", "DOOR")),
        allowed_camera_pairs=(("WEST", "DOOR"), ("DOOR", "WEST")),
        detour_waypoints_m=((4, 3, 0), (4, 0.5, 0)),
        regions=(
            ConfiguredRegion(region_id="west", floor_id="floor:0", bounds_xy_m=(0, 0, 6, 4)),
            ConfiguredRegion(region_id="east", floor_id="floor:0", bounds_xy_m=(6, 0, 10.5, 4)),
            ConfiguredRegion(region_id="corner-near", floor_id="floor:0",
                             bounds_xy_m=(9, 1, 11, 3)),
            ConfiguredRegion(region_id="north", floor_id="floor:0", bounds_xy_m=(9, 2, 11, 5))))
    config = BehaviorConfig(
        scope=scope, config_version="development-v2", regions=context.regions,
        portals=(BehaviorPortal(portal_id="door", outside_region_id="west", inside_region_id="east",
                                line_xy_m=((6, 0.5), (6, 3.5)), enter_normal_xy=(1, 0)),),
        corners=(BehaviorCorner(corner_id="corner", approach_region_id="east",
                                departure_region_id="north", near_region_id="corner-near"),),
        revisit_region_ids=("west", "north"))
    return scope, context, config


Row = tuple[str, str, Sequence[float], Sequence[tuple[float, float]]]


def perception(*rows: Row) -> PerceptionResult:
    measurements: list[Measurement] = []
    tracks: list[LocalTrack] = []
    for camera, short_id, times, positions in rows:
        identity = f"lab/test-run/{camera}/{short_id}"
        selected = tuple(Measurement(
            observation_id=f"pixel:{identity}/{index}", local_track_id=identity,
            camera_id=camera, model_id="lab", run_id="test-run", timestamp=timestamp,
            frame_ref=f"frame:{camera}/{timestamp}",
            bbox_xyxy=(point[0] - 0.1, point[1] - 0.2, point[0] + 0.1, point[1] + 0.1),
            contact_pixel=point, appearance=(45, 80, 140), uncertainty=0.2,
            input_sha256=HASH, status="DETECTED", local_alternative_count=0,
            evidence_refs=(f"frame:{camera}/{timestamp}",))
            for index, (timestamp, point) in enumerate(zip(times, positions, strict=True)))
        measurements.extend(selected)
        tracks.append(LocalTrack(
            local_track_id=identity, camera_id=camera, model_id="lab", run_id="test-run",
            observation_ids=tuple(row.observation_id for row in selected), timestamps=tuple(times),
            status="COMPLETE", missing_timestamps=(), termination_reason="SEQUENCE_END"))
    return PerceptionResult(
        model_id="lab", run_id="test-run", measurements=tuple(measurements), tracks=tuple(tracks),
        frame_statuses=(), input_manifest_sha256=HASH, producer_sha256=CONTEXT_HASH, complete=True)


def compose(result: PerceptionResult) -> LocalBehaviorBundle:
    scope, context, config = setup()
    inference = build_inference(result, scope=scope, context=context,
                                policy=AssociationPolicy(projection_uncertainty_m=0.1))
    return compose_behaviors_v2(inference, config, tracks=result.tracks)


@pytest.mark.parametrize(("positions", "kind"), [
    (((4, 2), (5, 2), (6, 2), (7, 2), (8, 2)), "ENTER_DOOR"),
    (((8, 2), (7, 2), (6, 2), (5, 2), (4, 2)), "EXIT_DOOR"),
])
def test_repeated_visible_two_side_portal_passage(
    positions: Sequence[tuple[float, float]], kind: str,
) -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4, 0.6, 0.8), positions))
    bundle = compose(result)
    door = next(event for event in bundle.events if event.kind == kind)
    assert event_support_state(door) == "SUPPORTED"
    assert door.time_range == (0, 0.8)
    assert door.portal_ids == ("door",) and door.region_ids == ("west", "east")
    assert len(door.source_frames) == 5
    assert LocalBehaviorBundle.model_validate_json(bundle.model_dump_json()) == bundle


def test_two_frame_side_swap_is_retained_unknown_without_claim() -> None:
    bundle = compose(perception(("WEST", "a", (0, 0.2), ((5, 2), (7, 2)))))
    door = next(event for event in bundle.events if event.kind == "ENTER_DOOR")
    assert event_support_state(door) == "UNKNOWN"
    assert "INSUFFICIENT_REPEATED_CLEAR_DOOR_SIDE_EVIDENCE" in door.conflicts
    assert "DOOR_APPROACH_OR_RETREAT" in door.alternatives
    assert len(door.source_frames) == 2


@pytest.mark.parametrize("positions", [
    ((3, 2), (4, 2), (5, 2)),
    ((4, 2), (5, 2), (4, 2)),
    ((5, 4.5), (6, 4.5), (7, 4.5)),
])
def test_approach_turnback_and_infinite_line_crossing_do_not_claim_door(
    positions: Sequence[tuple[float, float]],
) -> None:
    events = compose(perception(("WEST", "a", (0, 0.2, 0.4), positions))).events
    assert not any(event.kind in ("ENTER_DOOR", "EXIT_DOOR")
                   and event_support_state(event) == "SUPPORTED" for event in events)


def test_corner_uses_extended_exclusive_arm_evidence() -> None:
    result = perception(("WEST", "a", (0, 0.4, 0.8, 1.2, 1.6, 2, 2.4),
                         ((7.5, 1.8), (8, 1.8), (9, 1.8), (10, 1.8),
                          (10, 2.5), (10, 4.5), (10, 5))))
    turns = [event for event in compose(result).events
             if event.kind == "TURN_CORNER" and event_support_state(event) == "SUPPORTED"]
    assert turns
    assert all("V2_REPEATED_EXCLUSIVE_CORNER_ARM_SAMPLES" in event.supports for event in turns)
    assert all(event.time_range[1] - event.time_range[0] > 0.8 for event in turns)


def test_overlapping_corner_regions_and_jitter_retain_legacy_unknown() -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4), ((9.8, 2.2), (10, 2), (10.2, 2.2))))
    scope, context, config = setup()
    inference = build_inference(result, scope=scope, context=context)
    legacy = compose_local_behaviors(inference, config, tracks=result.tracks)
    assert any(event.kind == "TURN_CORNER" for event in legacy.events)
    turns = [event for event in compose_behaviors_v2(inference, config).events
             if event.kind == "TURN_CORNER"]
    assert turns and all(event_support_state(event) == "UNKNOWN" for event in turns)
    assert all("STRAIGHT_MOTION_OR_JITTER" in event.alternatives for event in turns)


def test_corner_turnback_is_not_a_through_turn() -> None:
    result = perception(("WEST", "a", (0, 0.4, 0.8, 1.2, 1.6),
                         ((8, 1.8), (9, 1.8), (10, 1.8), (9, 1.8), (8, 1.8))))
    assert not any(event.kind == "TURN_CORNER" and event_support_state(event) == "SUPPORTED"
                   for event in compose(result).events)


def test_stationary_pixel_jitter_is_dwell_without_loitering() -> None:
    times = tuple(index * 0.2 for index in range(11))
    points = tuple((4 + (index % 2) * 0.06, 2.0) for index in range(11))
    events = compose(perception(("WEST", "a", times, points))).events
    assert [event.kind for event in events] == ["DWELL"]
    assert event_support_state(events[0]) == "SUPPORTED" and events[0].time_range == (0, 2)


def test_slow_transit_above_window_speed_does_not_become_dwell() -> None:
    times = tuple(index * 0.2 for index in range(11))
    points = tuple((3 + index * 0.08, 2.0) for index in range(11))
    assert not any(event.kind == "DWELL" and event_support_state(event) == "SUPPORTED"
                   for event in compose(perception(("WEST", "a", times, points))).events)


def test_repeated_reversal_supported_and_one_stop_kept_distinct() -> None:
    result = perception(("WEST", "a", (0, 0.5, 1, 1.5, 2),
                         ((3, 2), (4, 2), (3, 2), (4, 2), (3, 2))))
    loiter = next(event for event in compose(result).events if event.kind == "POSSIBLE_LOITERING")
    assert event_support_state(loiter) == "SUPPORTED"
    assert "V2_NET_DISPLACEMENT_REVERSALS:2" in loiter.supports
    assert "LOCAL_VISIBLE_MOTION_ONLY_NO_INTENT_INFERENCE" in loiter.supports


def test_shallow_region_boundary_revisit_remains_unknown() -> None:
    result = perception(("WEST", "a", (0, 0.5, 1, 1.5, 2),
                         ((5.7, 2), (6.2, 2), (6.25, 2), (6.2, 2), (5.7, 2))))
    loiter = next(event for event in compose(result).events if event.kind == "POSSIBLE_LOITERING")
    assert event_support_state(loiter) == "UNKNOWN"
    assert "V2_CLEAR_REGION_REVISITS:0" in loiter.supports
    assert "NO_CLEAR_SEPARATED_REVISIT_OR_NET_REVERSAL" in loiter.conflicts


def test_separated_visible_revisit_requires_duration_travel_and_clear_departure() -> None:
    result = perception(("WEST", "a", (0, 0.5, 1, 1.5, 2),
                         ((5, 2), (7, 2), (8, 2), (7, 2), (5, 2))))
    loiter = next(event for event in compose(result).events if event.kind == "POSSIBLE_LOITERING")
    assert event_support_state(loiter) == "SUPPORTED"
    assert "V2_CLEAR_REGION_REVISITS:1" in loiter.supports
    assert "LOCAL_REVISIT" in loiter.alternatives


def test_visible_gaps_do_not_bridge_door_or_dwell_evidence() -> None:
    result = perception(("WEST", "a", (0, 0.2, 1.6, 1.8),
                         ((5, 2), (5.5, 2), (6.5, 2), (7, 2))))
    assert not compose(result).events


def test_blind_gap_order_and_original_inference_are_immutable() -> None:
    result = perception(
        ("WEST", "a", (0, 0.2), ((2, 2), (3, 2))),
        ("DOOR", "b", (3, 3.2), ((7, 2), (8, 2))))
    scope, context, config = setup()
    inference = build_inference(result, scope=scope, context=context)
    before = content_sha256(inference)
    legacy = compose_local_behaviors(inference, config, tracks=result.tracks)
    v2 = compose_behaviors_v2(inference, config, tracks=result.tracks)
    old = {event.canonical_event_id: event for event in legacy.events
           if event.evidence_state == "INFERRED_GAP"}
    new = {event.canonical_event_id: event for event in v2.events
           if event.evidence_state == "INFERRED_GAP"}
    assert old.keys() == new.keys() and old
    for identity, event in new.items():
        assert event.candidates == old[identity].candidates
        assert event.trajectories == old[identity].trajectories
        assert event.alternatives == old[identity].alternatives
        assert event.source_frames == old[identity].source_frames
        assert event_support_state(event) == "GAP_ALTERNATIVES"
    assert content_sha256(inference) == before


def test_version_policy_scope_and_track_bytes_bind_outputs() -> None:
    scope, context, config = setup()
    result = perception(("WEST", "a", (0, 0.2), ((5, 2), (7, 2))))
    inference = build_inference(result, scope=scope, context=context)
    v2 = compose_behaviors_v2(inference, config, tracks=result.tracks)
    assert v2.config_sha256 == behavior_config_sha256(config)
    assert v2.config_sha256 != content_sha256(config)
    assert all(event.config_version.endswith(":local-behavior-evidence-v2") for event in v2.events)
    alternate = BehaviorEvidencePolicy(portal_clearance_m=0.2)
    assert behavior_config_sha256(config, alternate) != v2.config_sha256
    assert v2.track_state_sha256 == content_sha256([
        track.model_dump(mode="json") for track in result.tracks])
    with pytest.raises(ValueError, match="exact inference scope"):
        compose_behaviors_v2(inference, config.model_copy(update={
            "scope": scope.model_copy(update={"clock_id": "other"})}))
    with pytest.raises(ValueError, match="undeclared or truth fields"):
        compose_behaviors_v2(inference.model_copy(update={"actor_id": "truth"}), config)


def test_no_sidecar_or_media_read_and_repeatability(monkeypatch: pytest.MonkeyPatch) -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4, 0.6, 0.8),
                         ((4, 2), (5, 2), (6, 2), (7, 2), (8, 2))))
    expected = compose(result)

    def denied(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("behavior composer must not open truth, recipe or media")

    monkeypatch.setattr(Path, "read_bytes", denied)
    monkeypatch.setattr(Path, "read_text", denied)
    assert compose(result) == expected
    assert compose(result).model_dump_json() == expected.model_dump_json()
