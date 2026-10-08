"""Visible event evidence, counterexamples, HOLD and blind-gap preservation."""

from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from amidst.domain.geometry import Plane
from amidst.engineering.association import (
    AssociationPolicy,
    ConfiguredRegion,
    GroundCalibration,
    InferenceBundle,
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

HASH = "a" * 64
CONTEXT_HASH = "b" * 64


def scope() -> InferenceScope:
    return InferenceScope(
        place_id="synthetic-lab", model_id="lab", model_revision="1", run_id="test-run",
        clock_id="configured-seconds", source_ref="source:lab", source_sha256=HASH,
        spatial_context_id="context:lab", context_sha256=CONTEXT_HASH,
    )


def context() -> SyntheticStaticContext:
    plane = Plane(plane_id="floor:lab", point=(0, 0, 0), normal=(0, 0, 1), floor_id="floor:0")
    return SyntheticStaticContext(
        spatial_context_id="context:lab", source_sha256=HASH, context_sha256=CONTEXT_HASH,
        ground_plane=plane, walkable_bounds_xy_m=(0, 0, 12, 6),
        calibrations=tuple(GroundCalibration(
            camera_id=camera, plane=plane, affine_ground_to_pixel=((1, 0, 0), (0, 1, 0)),
        ) for camera in ("WEST", "DOOR")),
        allowed_camera_pairs=(("WEST", "DOOR"), ("DOOR", "WEST")),
        detour_waypoints_m=((4, 3, 0), (4, 0.5, 0)),
        regions=(
            ConfiguredRegion(region_id="west", floor_id="floor:0", bounds_xy_m=(0, 0, 6, 4)),
            ConfiguredRegion(region_id="east", floor_id="floor:0", bounds_xy_m=(6, 0, 10.5, 4)),
            ConfiguredRegion(region_id="corner-near", floor_id="floor:0",
                             bounds_xy_m=(9, 1, 11, 3)),
            ConfiguredRegion(region_id="north-branch", floor_id="floor:0",
                             bounds_xy_m=(9, 2, 11, 5)),
        ),
    )


def config() -> BehaviorConfig:
    return BehaviorConfig(
        scope=scope(), config_version="development-v1", regions=context().regions,
        portals=(BehaviorPortal(portal_id="door", outside_region_id="west", inside_region_id="east",
                                line_xy_m=((6, 0.5), (6, 3.5)), enter_normal_xy=(1, 0)),),
        corners=(BehaviorCorner(corner_id="corner", approach_region_id="east",
                                departure_region_id="north-branch", near_region_id="corner-near"),),
        revisit_region_ids=("west", "north-branch"),
    )


Row = tuple[str, str, Sequence[float], Sequence[tuple[float, float]]]


def perception(*rows: Row) -> PerceptionResult:
    measurements: list[Measurement] = []
    tracks: list[LocalTrack] = []
    for camera, short_id, times, positions in rows:
        track_id = f"lab/test-run/{camera}/{short_id}"
        selected: list[Measurement] = []
        for index, (timestamp, pixel) in enumerate(zip(times, positions, strict=True)):
            selected.append(Measurement(
                observation_id=f"pixel:{track_id}/{index}", local_track_id=track_id,
                camera_id=camera, model_id="lab", run_id="test-run", timestamp=timestamp,
                frame_ref=f"frame:{camera}/{timestamp}",
                bbox_xyxy=(pixel[0] - 0.1, pixel[1] - 0.2, pixel[0] + 0.1, pixel[1] + 0.1),
                contact_pixel=pixel, appearance=(45, 80, 140), uncertainty=0.2,
                input_sha256=HASH, status="DETECTED", local_alternative_count=0,
                evidence_refs=(f"frame:{camera}/{timestamp}",),
            ))
        measurements.extend(selected)
        tracks.append(LocalTrack(
            local_track_id=track_id, camera_id=camera, model_id="lab", run_id="test-run",
            observation_ids=tuple(item.observation_id for item in selected),
            timestamps=tuple(times),
            status="COMPLETE", missing_timestamps=(), termination_reason="SEQUENCE_END",
        ))
    return PerceptionResult(
        model_id="lab", run_id="test-run", measurements=tuple(measurements), tracks=tuple(tracks),
        frame_statuses=(), input_manifest_sha256=HASH, producer_sha256=CONTEXT_HASH, complete=True,
    )


def infer(perception_result: PerceptionResult) -> InferenceBundle:
    return build_inference(perception_result, scope=scope(), context=context(),
                           policy=AssociationPolicy(projection_uncertainty_m=0.1))


@pytest.mark.parametrize(("positions", "expected"), [
    (((4, 2), (5, 2), (6, 2), (7, 2), (8, 2)), "ENTER_DOOR"),
    (((8, 2), (7, 2), (6, 2), (5, 2), (4, 2)), "EXIT_DOOR"),
])
def test_oriented_two_side_door_crossing_retains_actual_frames(
    positions: Sequence[tuple[float, float]], expected: str,
) -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4, 0.6, 0.8), positions))
    inference = infer(result)
    before = content_sha256(inference)
    bundle = compose_local_behaviors(inference, config(), tracks=result.tracks)
    door = next(event for event in bundle.events if event.kind == expected)
    assert door.region_ids == ("west", "east") and door.portal_ids == ("door",)
    assert door.evidence_state == "PROJECTED"
    assert 3 <= len(door.source_frames) <= 5
    assert all(frame.frame_ref in {item.frame_ref for item in result.measurements}
               for frame in door.source_frames)
    assert door.projected_path and not door.candidates and not door.trajectories
    assert before == content_sha256(inference)
    assert LocalBehaviorBundle.model_validate_json(bundle.model_dump_json()) == bundle


@pytest.mark.parametrize("positions", [
    ((3, 2), (4, 2), (5, 2)),  # approach without crossing
    ((4, 2), (5, 2), (4, 2)),  # turn back before the door
    ((5, 4), (6, 4), (7, 4)),  # crosses infinite line beyond the finite portal
    ((5.8, 1), (6, 2), (6.2, 3)),  # crossing direction too tangential
])
def test_door_approach_turnback_and_wrong_direction_are_not_crossings(
    positions: Sequence[tuple[float, float]],
) -> None:
    bundle = compose_local_behaviors(infer(perception(("WEST", "a", (0, 0.2, 0.4), positions))),
                                     config())
    assert not any(event.kind in ("ENTER_DOOR", "EXIT_DOOR") for event in bundle.events)


def test_visible_corner_direction_and_both_regions() -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4, 0.6, 0.8),
                         ((8, 2), (9, 2), (10, 2), (10, 3), (10, 4))))
    events = compose_local_behaviors(infer(result), config(), tracks=result.tracks).events
    turn = next(event for event in events if event.kind == "TURN_CORNER")
    assert turn.corner_ids == ("corner",)
    assert turn.region_ids == ("east", "north-branch")
    assert "VISIBLE_DIRECTION_CHANGE_DEG:90.000" in turn.supports
    assert len(turn.source_frames) == 5
    assert not any(event.kind == "LOST_NEAR_CORNER" for event in events)


def test_corner_turnback_has_no_departure_or_loiter_claim() -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4), ((9, 2), (10, 2), (9, 2))))
    events = compose_local_behaviors(infer(result), config(), tracks=result.tracks).events
    assert not any(event.kind in ("TURN_CORNER", "POSSIBLE_LOITERING") for event in events)


def test_lost_near_corner_requires_producer_loss_and_does_not_infer_passage() -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4), ((8, 2), (9, 2), (10, 2))))
    inference = infer(result)
    assert not compose_local_behaviors(inference, config(), tracks=result.tracks).events
    lost = result.tracks[0].model_copy(update={"termination_reason": "LOST_OR_LEFT_VIEW"})
    events = compose_local_behaviors(inference, config(), tracks=(lost,)).events
    assert [event.kind for event in events] == ["LOST_NEAR_CORNER"]
    assert events[0].conflicts == ("NO_VISIBLE_DEPARTURE_SIDE_OR_CROSSING_PROOF",)
    assert "OCCLUSION_OR_MISSED_DETECTION" in events[0].alternatives
    assert events[0].evidence_state == "PROJECTED"


def test_single_dwell_is_visible_low_motion_without_possible_loitering() -> None:
    times = tuple(index * 0.2 for index in range(11))
    points = tuple((4 + (index % 2) * 0.01, 2.0) for index in range(11))
    result = perception(("WEST", "a", times, points))
    events = compose_local_behaviors(infer(result), config(), tracks=result.tracks).events
    assert [event.kind for event in events] == ["DWELL"]
    assert events[0].time_range == (0.0, 2.0)
    assert len(events[0].source_frames) == 5


def test_repeated_visible_reversal_is_possible_loitering_without_intent_claim() -> None:
    result = perception(("WEST", "a", (0, 0.5, 1, 1.5, 2),
                         ((3, 2), (4, 2), (3, 2), (4, 2), (3, 2))))
    events = compose_local_behaviors(infer(result), config(), tracks=result.tracks).events
    loiter = next(event for event in events if event.kind == "POSSIBLE_LOITERING")
    assert "VISIBLE_REVERSALS:2" in loiter.supports
    assert "OPERATIONAL_LOCAL_MOTION_PATTERN_NO_INTENT_INFERENCE" in loiter.supports
    assert "intent" in loiter.uncertainty
    assert not any(event.kind == "DWELL" for event in events)


def test_separated_region_revisit_has_measurable_departure_and_travel() -> None:
    result = perception(("WEST", "a", (0, 0.5, 1, 1.5, 2),
                         ((5, 2), (7, 2), (8, 2), (7, 2), (5, 2))))
    events = compose_local_behaviors(infer(result), config(), tracks=result.tracks).events
    loiter = next(event for event in events if event.kind == "POSSIBLE_LOITERING")
    assert "MEASURED_REGION_REVISITS:1" in loiter.supports
    assert "west" in loiter.region_ids
    assert loiter.time_range == (0, 2)


def test_lookup_gap_cannot_create_door_crossing_or_join_a_stationary_interval() -> None:
    result = perception(("WEST", "a", (0, 0.2, 1.6, 1.8), ((5, 2), (5.5, 2), (6.5, 2), (7, 2))))
    inference = infer(result)
    assert len(inference.local_record_maps) == 2
    assert all(item.status == "HOLD" for item in inference.association_hypotheses
               if item.kind == "SAME_CAMERA_RECOVERY")
    assert not compose_local_behaviors(inference, config(), tracks=result.tracks).events


def test_invalid_projection_between_door_sides_does_not_supply_a_crossing() -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4), ((5, 2), (14, 2), (7, 2))))
    inference = infer(result)
    assert inference.projected_measurements[1].status == "OUTSIDE_STATIC_SCOPE"
    assert not compose_local_behaviors(inference, config(), tracks=result.tracks).events


def test_same_camera_recovery_hold_is_retained_without_handoff_or_gap() -> None:
    result = perception(
        ("WEST", "a", (0, 0.2, 0.4), ((5, 2), (6, 2), (7, 2))),
        ("WEST", "b", (2, 2.2), ((8, 2), (9, 2))),
    )
    inference = infer(result)
    events = compose_local_behaviors(inference, config(), tracks=result.tracks).events
    door = next(event for event in events if event.kind == "ENTER_DOOR")
    recovery = next(item for item in door.association_states if item.kind == "SAME_CAMERA_RECOVERY")
    assert recovery.status == "HOLD"
    assert recovery.hypothesis_id in door.alternatives
    assert not any(event.kind == "INFERRED_GAP_ALTERNATIVES" for event in events)
    assert not inference.snapshot.gaps


def test_gap_alternatives_keep_canonical_candidate_timing_order_and_actual_endpoints() -> None:
    result = perception(
        ("WEST", "a", (0, 0.2), ((2, 2), (3, 2))),
        ("DOOR", "b", (3, 3.2), ((7, 2), (8, 2))),
        ("DOOR", "c", (3, 3.2), ((7, 2.4), (8, 2.4))),
    )
    inference = infer(result)
    before = content_sha256(inference)
    events = compose_local_behaviors(inference, config(), tracks=result.tracks).events
    gaps = [event for event in events if event.kind == "INFERRED_GAP_ALTERNATIVES"]
    assert len(gaps) == len(inference.snapshot.gaps) == 2
    canonical = {gap.event.event_id: gap for gap in inference.snapshot.gaps}
    for event in gaps:
        gap = canonical[event.canonical_event_id]
        assert event.candidates == gap.event.candidates
        assert event.trajectories == gap.event.trajectories
        assert event.alternatives == tuple(
            candidate.candidate_id for candidate in gap.event.candidates)
        assert event.complete == gap.search_result.complete
        assert event.termination_reason == str(gap.event.termination_reason)
        assert len(event.source_frames) == 4
        assert event.evidence_state == "INFERRED_GAP"
        assert "NO_CAMERA_PHOTOGRAPHS_INSIDE_BLIND_GAP" in event.missing_evidence
        assert not event.portal_ids and not event.corner_ids
    assert before == content_sha256(inference)


def test_fewer_actual_frames_are_reported_without_fabrication() -> None:
    result = perception(("WEST", "a", (0, 0.2), ((5, 2), (7, 2))))
    event = compose_local_behaviors(infer(result), config()).events[0]
    assert len(event.source_frames) == 2
    assert event.missing_evidence == ("FEWER_THAN_THREE_AVAILABLE_VISIBLE_FRAMES",)


def test_scope_extra_truth_fields_and_invalid_config_are_rejected() -> None:
    inference = infer(perception(("WEST", "a", (0, 0.2), ((5, 2), (7, 2)))))
    wrong_scope = config().model_copy(update={
        "scope": scope().model_copy(update={"clock_id": "wrong-clock"}),
    })
    with pytest.raises(ValueError, match="exact inference scope"):
        compose_local_behaviors(inference, wrong_scope)
    with pytest.raises(ValueError, match="undeclared or truth fields"):
        compose_local_behaviors(inference.model_copy(update={"ground_truth": {"actor": "answer"}}),
                                config())
    with pytest.raises(ValidationError):
        BehaviorConfig.model_validate(config().model_dump() | {"ground_truth": {}})
    with pytest.raises(ValidationError, match="unit entering normal"):
        BehaviorPortal(portal_id="door", outside_region_id="west", inside_region_id="east",
                       line_xy_m=((6, 0.5), (6, 3.5)), enter_normal_xy=(2, 0))
    with pytest.raises(ValidationError, match="registered regions"):
        BehaviorConfig.model_validate(config().model_dump() | {"revisit_region_ids": ("unknown",)})


def test_no_file_truth_recipe_or_reference_input_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    result = perception(("WEST", "a", (0, 0.2, 0.4), ((5, 2), (6, 2), (7, 2))))
    inference = infer(result)
    expected = compose_local_behaviors(inference, config(), tracks=result.tracks)

    def denied(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("behavior must not open sidecars or media")

    monkeypatch.setattr(Path, "read_bytes", denied)
    monkeypatch.setattr(Path, "read_text", denied)
    actual = compose_local_behaviors(inference, config(), tracks=result.tracks)
    assert actual == expected
    assert actual.measurements_indexed == len(inference.projected_measurements)
    assert actual.segments_visited == len(inference.local_record_maps)


def test_indexed_bundle_preserves_new_schema_hash_without_legacy_conversion() -> None:
    from amidst.engineering.local_association import build_inference as build_indexed_inference

    result = perception(("WEST", "a", (0, 0.2, 0.4), ((5, 2), (6, 2), (7, 2))))
    inference = build_indexed_inference(result, scope=scope(), context=context())
    bundle = compose_local_behaviors(inference, config(), tracks=result.tracks)
    assert inference.schema_version == "simulation.local-association.v1"
    assert bundle.inference_sha256 == content_sha256(inference)
    assert [event.kind for event in bundle.events] == ["ENTER_DOOR"]


def test_loss_state_cannot_substitute_unknown_track_or_camera_evidence() -> None:
    result = perception(("WEST", "a", (0, 0.2, 0.4), ((8, 2), (9, 2), (10, 2))))
    inference = infer(result)
    for update in ({"observation_ids": ()}, {"camera_id": "DOOR"},
                   {"timestamps": (0.0, 0.3, 0.4)}, {"local_track_id": "unknown"}):
        bad = result.tracks[0].model_copy(
            update=update | {"termination_reason": "LOST_OR_LEFT_VIEW"})
        with pytest.raises(ValueError, match="exact pixel evidence and camera"):
            compose_local_behaviors(inference, config(), tracks=(bad,))
