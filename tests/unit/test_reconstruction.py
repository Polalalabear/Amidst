"""Generic blind-gap timing, provenance, Top-K retention and isolation checks."""

from __future__ import annotations

import math
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance, Vec3
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.trajectory import (
    CandidateTrajectory,
    Event,
    HypothesisKind,
    ReconstructionResult,
    SegmentKind,
    TerminationReason,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.reconstruction import (
    BlindGapReconstructor,
    ReconstructionInputError,
    ReconstructionPolicy,
)


def _endpoints(
    gap: float = 20,
    *,
    start_time: float = 10,
    end_position: Vec3 = (20, 0, 0),
) -> tuple[Observation, Observation]:
    result: list[Observation] = []
    for observation_id, camera_id, timestamp, position in (
        ("obs_A", "CAM_A", start_time, (0, 0, 0)),
        ("obs_B", "CAM_B", start_time + gap, end_position),
    ):
        result.append(
            Observation(
                observation_id=observation_id,
                target_id="synthetic_person",
                camera_id=camera_id,
                start_time=timestamp,
                end_time=timestamp,
                floor_id="1F",
                provenance=Provenance.PROJECTED,
                projected_path=(
                    ProjectedPoint(
                        point_id=f"{observation_id}_point",
                        observation_id=observation_id,
                        camera_id=camera_id,
                        plane_id="floor_1F",
                        floor_id="1F",
                        timestamp=timestamp,
                        world_position=position,
                    ),
                ),
            )
        )
    return result[0], result[1]


def _candidate(
    candidate_id: str = "route_direct",
    *,
    polyline: tuple[Vec3, ...] = ((0, 0, 0), (10, 0, 0), (20, 0, 0)),
    minimum_time: float | None = None,
    gap: float = 20,
) -> CandidateTrajectory:
    length = math.fsum(math.dist(a, b) for a, b in zip(polyline[:-1], polyline[1:], strict=True))
    return CandidateTrajectory(
        candidate_id=candidate_id,
        start_observation_id="obs_A",
        end_observation_id="obs_B",
        polyline=polyline,
        path_length=length,
        minimum_travel_time=length if minimum_time is None else minimum_time,
        estimated_travel_time=gap,
    )


def _search_result(
    candidates: tuple[CandidateTrajectory, ...],
    termination: TerminationReason = TerminationReason.COMPLETE,
) -> ReconstructionResult:
    return ReconstructionResult(
        candidates=candidates,
        termination_reason=termination,
        complete=termination in {TerminationReason.COMPLETE, TerminationReason.NO_FEASIBLE_PATH},
        expanded_nodes=7,
    )


def _event(gap: float = 20) -> Event:
    start, end = _endpoints(gap)
    return BlindGapReconstructor().reconstruct_gap(
        start, end, _search_result((_candidate(gap=gap),))
    )


def test_direct_gap_has_exact_waypoint_timing_and_inferred_provenance() -> None:
    event = _event()
    assert len(event.candidates) == len(event.trajectories) == 1
    assert event.termination_reason == TerminationReason.COMPLETE
    trajectory = event.trajectories[0]
    assert trajectory.kind == HypothesisKind.DIRECT_PATH
    assert tuple(point.timestamp for point in trajectory.timed_points) == (10, 20, 30)
    assert tuple(point.provenance for point in trajectory.timed_points) == (
        Provenance.PROJECTED,
        Provenance.INFERRED_GAP,
        Provenance.PROJECTED,
    )
    assert trajectory.provenance == Provenance.INFERRED_GAP
    assert trajectory.temporal_slack == trajectory.dwell_duration == 0
    assert trajectory.movement_duration == trajectory.minimum_travel_time == 20
    assert trajectory.segments[0].provenance == Provenance.INFERRED_GAP
    assert trajectory.segments[0].kind == SegmentKind.MOVEMENT


def test_temporal_slack_exposes_slower_movement_and_explicit_dwell() -> None:
    event = _event(180)
    slower, dwell = event.trajectories
    assert slower.kind == HypothesisKind.SLOWER_MOVEMENT
    assert slower.temporal_slack == dwell.temporal_slack == 160
    assert slower.minimum_travel_time == dwell.minimum_travel_time == 20
    assert slower.movement_duration == 180
    assert slower.dwell_duration == 0
    assert tuple(point.timestamp for point in slower.timed_points) == (10, 100, 190)
    assert dwell.kind == HypothesisKind.DWELL
    assert dwell.movement_duration == 20
    assert dwell.dwell_duration == 160
    assert tuple(point.timestamp for point in dwell.timed_points) == (10, 170, 180, 190)
    assert dwell.timed_points[0].world_position == dwell.timed_points[1].world_position
    assert dwell.timed_points[1].provenance == Provenance.INFERRED_GAP
    assert tuple(segment.kind for segment in dwell.segments) == (
        SegmentKind.DWELL,
        SegmentKind.MOVEMENT,
    )
    assert "not observed behavior" in dwell.uncertainty
    assert "no behavioral probability" in slower.uncertainty
    assert not any("probability" in field for field in TrajectoryHypothesis.model_fields)


def test_top_k_order_routes_and_search_termination_survive_reconstruction() -> None:
    candidates = (
        _candidate("route_long", polyline=((0, 0, 0), (10, 12, 0), (20, 0, 0)), gap=40),
        _candidate("route_direct", gap=40),
        _candidate("route_upper", polyline=((0, 0, 0), (10, 10, 0), (20, 0, 0)), gap=40),
    )
    start, end = _endpoints(40)
    event = BlindGapReconstructor().reconstruct_gap(
        start, end, _search_result(candidates, TerminationReason.MAX_PATHS_REACHED)
    )
    assert event.candidates == candidates
    assert event.termination_reason == TerminationReason.MAX_PATHS_REACHED
    assert len(event.trajectories) == 6
    assert tuple(item.candidate_id for item in event.trajectories[::2]) == tuple(
        item.candidate_id for item in candidates
    )
    assert event.trajectories[0].kind == event.trajectories[4].kind == HypothesisKind.DETOUR
    assert event.trajectories[2].kind == HypothesisKind.SLOWER_MOVEMENT
    assert "relative to retained routes" in event.trajectories[0].uncertainty


@pytest.mark.parametrize("termination", list(TerminationReason))
def test_all_termination_reasons_are_propagated_deterministically(
    termination: TerminationReason,
) -> None:
    start, end = _endpoints()
    candidates = () if termination == TerminationReason.NO_FEASIBLE_PATH else (_candidate(),)
    reconstructor = BlindGapReconstructor()
    result = _search_result(candidates, termination)
    first = reconstructor.reconstruct_gap(start, end, result)
    second = reconstructor.reconstruct_gap(start, end, result)
    assert first.model_dump_json() == second.model_dump_json()
    assert first.termination_reason == termination
    assert first.candidates == candidates
    assert bool(first.trajectories) == bool(candidates)


def test_existing_gap_reasoner_interface_is_idempotent() -> None:
    event = _event(180)
    assert BlindGapReconstructor().reconstruct(event) == event


def test_old_event_shape_remains_valid_and_can_be_reconstructed() -> None:
    event = _event()
    old_payload = event.model_dump()
    del old_payload["trajectories"]
    old_event = Event.model_validate(old_payload)
    assert old_event.trajectories == ()
    assert BlindGapReconstructor().reconstruct(old_event) == event


def test_near_minimum_threshold_is_explicit_and_dwell_can_be_disabled() -> None:
    start, end = _endpoints(20.5)
    result = _search_result((_candidate(gap=20.5),))
    default = BlindGapReconstructor().reconstruct_gap(start, end, result)
    assert default.trajectories[0].kind == HypothesisKind.DIRECT_PATH
    assert default.trajectories[0].temporal_slack == 0.5
    strict = BlindGapReconstructor(
        ReconstructionPolicy(direct_path_slack_tolerance_s=0, include_dwell_hypotheses=False)
    ).reconstruct_gap(start, end, result)
    assert len(strict.trajectories) == 1
    assert strict.trajectories[0].kind == HypothesisKind.SLOWER_MOVEMENT


def test_zero_distance_path_is_a_stationary_hypothesis() -> None:
    start, end = _endpoints(180, end_position=(0, 0, 0))
    candidate = _candidate(polyline=((0, 0, 0), (0, 0, 0)), gap=180)
    event = BlindGapReconstructor().reconstruct_gap(start, end, _search_result((candidate,)))
    assert len(event.trajectories) == 1
    trajectory = event.trajectories[0]
    assert trajectory.kind == HypothesisKind.DWELL
    assert trajectory.temporal_slack == trajectory.dwell_duration == 180
    assert trajectory.movement_duration == trajectory.minimum_travel_time == 0
    assert tuple(point.timestamp for point in trajectory.timed_points) == (10, 190)


def test_time_parametrization_uses_full_3d_arc_length_including_stairs() -> None:
    start, end = _endpoints(13, end_position=(4, 0, 3))
    candidate = _candidate(polyline=((0, 0, 0), (0, 0, 3), (4, 0, 3)), minimum_time=13, gap=13)
    event = BlindGapReconstructor().reconstruct_gap(start, end, _search_result((candidate,)))
    assert event.trajectories[0].timed_points[1].timestamp == pytest.approx(10 + 13 * 3 / 7)
    assert event.trajectories[0].timed_points[1].world_position == (0, 0, 3)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"minimum_travel_time": 21, "estimated_travel_time": 21}, "exceeds the gap"),
        ({"path_length": 19}, "path length"),
        ({"minimum_travel_time": 0}, "positive minimum"),
        ({"start_observation_id": "wrong"}, "observation endpoints"),
        ({"polyline": ((1, 0, 0), (20, 0, 0))}, "projected endpoints"),
    ],
)
def test_invalid_candidate_physics_or_endpoint_binding_are_rejected(
    change: dict[str, Any], message: str
) -> None:
    start, end = _endpoints()
    candidate = _candidate().model_copy(update=change)
    result = _search_result((candidate,))
    with pytest.raises(ReconstructionInputError, match=message):
        BlindGapReconstructor().reconstruct_gap(start, end, result)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"target_id": "other"}, "one target"),
        ({"observation_id": "obs_A", "projected_path": ()}, "Observation contract"),
        ({"provenance": Provenance.OBSERVED, "projected_path": ()}, "PROJECTED evidence"),
        ({"start_time": float("nan")}, "Observation contract"),
    ],
)
def test_malformed_or_nonprojected_observations_are_revalidated(
    change: dict[str, Any], message: str
) -> None:
    start, end = _endpoints()
    with pytest.raises(ReconstructionInputError, match=message):
        BlindGapReconstructor().reconstruct_gap(
            start, end.model_copy(update=change), _search_result((_candidate(),))
        )


def test_overlapping_or_zero_time_endpoints_are_rejected() -> None:
    start, end = _endpoints(0)
    with pytest.raises(ReconstructionInputError, match="positive duration"):
        BlindGapReconstructor().reconstruct_gap(start, end, _search_result(()))


def test_model_construct_bypass_is_revalidated_recursively() -> None:
    candidate = CandidateTrajectory.model_construct(
        **(_candidate().model_dump() | {"polyline": ((0, 0, 0), (float("nan"), 0, 0))})
    )
    result = ReconstructionResult.model_construct(
        candidates=(candidate,), termination_reason=TerminationReason.COMPLETE
    )
    start, end = _endpoints()
    with pytest.raises(ReconstructionInputError, match="ReconstructionResult contract"):
        BlindGapReconstructor().reconstruct_gap(start, end, result)


def test_unknown_injected_fields_fail_before_their_values_are_read() -> None:
    class ForbiddenValue:
        def __repr__(self) -> str:
            raise AssertionError("forbidden value was read")

    candidate = _candidate().model_copy(update={"ground_truth_3d": ForbiddenValue()})
    result = _search_result((candidate,))
    start, end = _endpoints()
    with pytest.raises(ReconstructionInputError, match="outside its declared contract"):
        BlindGapReconstructor().reconstruct_gap(start, end, result)


def test_configuration_copy_bypass_is_revalidated_at_construction_and_use() -> None:
    bad_policy = ReconstructionPolicy().model_copy(update={"direct_path_slack_tolerance_s": -1})
    with pytest.raises(ReconstructionInputError, match="ReconstructionPolicy contract"):
        BlindGapReconstructor(bad_policy)
    reconstructor = BlindGapReconstructor()
    reconstructor.policy = bad_policy
    with pytest.raises(ReconstructionInputError, match="ReconstructionPolicy contract"):
        reconstructor.reconstruct(_event())


def test_hypothesis_contract_rejects_false_dwell_and_nonpoint_segment_boundary() -> None:
    dwell = _event(180).trajectories[1]
    payload = dwell.model_dump()
    payload["timed_points"][1]["world_position"] = (1, 0, 0)
    with pytest.raises(ValidationError, match="one position"):
        TrajectoryHypothesis.model_validate(payload)
    payload = dwell.model_dump()
    payload["segments"][0]["time_range"] = (10, 169)
    payload["segments"][1]["time_range"] = (169, 190)
    payload["movement_duration"] = 21
    payload["dwell_duration"] = 159
    with pytest.raises(ValidationError, match="coincide with timed points"):
        TrajectoryHypothesis.model_validate(payload)


@pytest.mark.parametrize(
    "change",
    [
        {"temporal_slack": -1},
        {"minimum_travel_time": float("inf")},
        {"movement_duration": 19},
        {"provenance": Provenance.GROUND_TRUTH},
        {"kind": HypothesisKind.DWELL},
    ],
)
def test_hypothesis_timing_and_provenance_validation(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        TrajectoryHypothesis.model_validate(_event().trajectories[0].model_dump() | change)


def test_event_contract_checks_hypothesis_ids_candidates_and_time_extent() -> None:
    event = _event()
    payload = event.model_dump()
    payload["trajectories"] *= 2
    with pytest.raises(ValidationError, match="hypothesis identities"):
        Event.model_validate(payload)
    payload = event.model_dump()
    payload["trajectories"][0]["candidate_id"] = "wrong"
    with pytest.raises(ValidationError, match="reference an event candidate"):
        Event.model_validate(payload)
    payload = event.model_dump()
    payload["time_range"] = (11, 30)
    with pytest.raises(ValidationError, match="outside event time_range"):
        Event.model_validate(payload)


def test_timed_points_and_segments_reject_ground_truth_provenance() -> None:
    with pytest.raises(ValidationError):
        TimedTrajectoryPoint(
            timestamp=1, world_position=(0, 0, 0), provenance=Provenance.GROUND_TRUTH
        )
    with pytest.raises(ValidationError):
        TrajectorySegment(
            time_range=(1, 2), kind=SegmentKind.DWELL, provenance=Provenance.GROUND_TRUTH
        )


def test_time_precision_and_nonfinite_polyline_distance_fail_closed() -> None:
    start, end = _endpoints(20, start_time=1e16)
    candidate = _candidate(polyline=((0, 0, 0), (1e-20, 0, 0), (20, 0, 0)), minimum_time=20)
    with pytest.raises(ReconstructionInputError, match="time precision"):
        BlindGapReconstructor().reconstruct_gap(start, end, _search_result((candidate,)))
    event = Event(
        event_id="overflow",
        target_id="synthetic_person",
        time_range=(0, 20),
        observation_ids=("obs_A", "obs_B"),
        candidates=(
            _candidate().model_copy(
                update={"polyline": ((-1e308, 0, 0), (1e308, 0, 0)), "path_length": 1e308}
            ),
        ),
        termination_reason=TerminationReason.COMPLETE,
    )
    with pytest.raises(ReconstructionInputError, match="path length"):
        BlindGapReconstructor().reconstruct(event)
