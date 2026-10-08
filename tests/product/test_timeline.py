"""Actual-frame presentation sampling and all canonical GAP alternatives.

Small configured fixtures exercise presentation contracts without pixel inference,
GT, files or any expansion of scene/region authority.
"""

import math

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance, Vec3
from amidst.domain.trajectory import (
    CandidateTrajectory,
    HypothesisKind,
    SegmentKind,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.engineering.registry import MediaFrame, ResourceScope, opaque_ref, scope_parts
from amidst.product.contracts import EventDetail, EventSummary, ProjectedPoint, SourceFrame
from amidst.product.timeline import timeline_state

SCOPE = ResourceScope(
    place_id="presentation-fixture", model_id="synthetic-timeline", model_revision="1",
    run_id="timeline-v1", source_id="configured-rgb", source_sha256="a" * 64,
    spatial_context_id="timeline-context", spatial_context_sha256="b" * 64,
    clock_id="synthetic-seconds",
)
RUN_REF = opaque_ref("run", *scope_parts(SCOPE))


def frame(camera_id: str, frame_id: int, timestamp: float) -> MediaFrame:
    fingerprint = "c" * 64
    return MediaFrame(
        scope=SCOPE, camera_id=camera_id,
        camera_ref=opaque_ref("camera", *scope_parts(SCOPE), camera_id),
        media_ref=opaque_ref("media", *scope_parts(SCOPE), camera_id, str(frame_id), fingerprint),
        frame_id=frame_id, timestamp=timestamp, relative_path=f"rgb/{camera_id}/{frame_id}.png",
        sha256=fingerprint, size_bytes=100, width=640, height=360,
    )


def point(camera_id: str, timestamp: float, position: Vec3) -> ProjectedPoint:
    return ProjectedPoint(
        observation_id=f"measurement-{camera_id}-{timestamp}", local_track_id=f"local-{camera_id}",
        camera_id=camera_id, timestamp=timestamp, world_position=position,
        uncertainty_m=0.3, evidence_state="PROJECTED",
    )


def event(
    *, name: str = "observed", projected_path: tuple[ProjectedPoint, ...] = (),
    frames: tuple[MediaFrame, ...] = (), candidates: tuple[CandidateTrajectory, ...] = (),
    hypotheses: tuple[TrajectoryHypothesis, ...] = (),
) -> EventDetail:
    reference = opaque_ref("event", *scope_parts(SCOPE), name)
    camera_ids = tuple(dict.fromkeys(f.camera_id for f in frames))
    return EventDetail(
        event_ref=reference, event_id=f"canonical-{name}",
        kind="INFERRED_GAP_ALTERNATIVES" if hypotheses else "REGION_OBSERVATION",
        time_range=(0, 4), local_track_refs=(), segment_refs=(), association_refs=(),
        association_states=(), source_frames=tuple(SourceFrame(
            frame_ref=f.media_ref, camera_id=f.camera_id, timestamp=f.timestamp,
            evidence_state="PROJECTED",
        ) for f in frames), missing_evidence=(), region_ids=(), portal_ids=(), corner_ids=(),
        rule_version="fixture-v1", config_version="fixture-v1", config_sha256="d" * 64,
        supports=("CONFIGURED_PRESENTATION_FIXTURE",), conflicts=(),
        alternatives=tuple(c.candidate_id for c in candidates),
        uncertainty="All configured alternatives retained; presentation only.",
        evidence_state="INFERRED_GAP" if hypotheses else "PROJECTED",
        canonical_event_id=f"canonical-{name}",
        termination_reason="MAX_PATHS_REACHED" if hypotheses else None,
        complete=False if hypotheses else None,
        candidate_count=len(candidates), hypothesis_count=len(hypotheses),
        detail_ref=reference, replay_ref=opaque_ref("replay", *scope_parts(SCOPE), name),
        origin="SYNTHETIC", authority="CONFIGURED_PIXEL_BEHAVIOR_HYPOTHESIS",
        camera_refs=tuple(opaque_ref("camera", *scope_parts(SCOPE), c) for c in camera_ids),
        camera_ids=camera_ids, media_refs=tuple(f.media_ref for f in frames),
        projected_path=projected_path, candidates=candidates, trajectories=hypotheses,
    )


@pytest.fixture
def projected_event() -> tuple[EventDetail, tuple[MediaFrame, ...]]:
    frames = (frame("CAM_A", 0, 0), frame("CAM_A", 1, 0.2),
              frame("CAM_B", 0, 0.08), frame("CAM_B", 1, 0.28))
    points = (point("CAM_A", 0, (0, 0, 0)), point("CAM_A", 0.2, (10, 0, 0)),
              point("CAM_B", 0.08, (0, 4, 0)), point("CAM_B", 0.28, (10, 4, 0)))
    return event(projected_path=points, frames=frames), frames


@pytest.fixture
def gap_event() -> EventDetail:
    candidates = tuple(CandidateTrajectory(
        candidate_id=name, start_observation_id="endpoint-start", end_observation_id="endpoint-end",
        polyline=path, path_length=length, minimum_travel_time=1, estimated_travel_time=2,
    ) for name, path, length in (
        ("straight", ((1, 0, 0), (3, 0, 0)), 2),
        ("detour", ((1, 0, 0), (2, 2, 0), (3, 0, 0)), 2 * math.sqrt(5)),
    ))

    def timed(timestamp: float, position: Vec3, *, endpoint: bool = False) -> TimedTrajectoryPoint:
        return TimedTrajectoryPoint(
            timestamp=timestamp, world_position=position,
            provenance=Provenance.PROJECTED if endpoint else Provenance.INFERRED_GAP,
        )

    def hypothesis(
        name: str, candidate: str, kind: HypothesisKind,
        points: tuple[TimedTrajectoryPoint, ...], *, dwell: bool = False,
    ) -> TrajectoryHypothesis:
        segments = ((TrajectorySegment(time_range=(1, 2), kind=SegmentKind.DWELL),
                     TrajectorySegment(time_range=(2, 3), kind=SegmentKind.MOVEMENT)) if dwell else
                    (TrajectorySegment(time_range=(1, 3), kind=SegmentKind.MOVEMENT),))
        return TrajectoryHypothesis(
            hypothesis_id=name, candidate_id=candidate, kind=kind, timed_points=points,
            segments=segments, minimum_travel_time=1, temporal_slack=1,
            movement_duration=1 if dwell else 2, dwell_duration=1 if dwell else 0,
            uncertainty="Configured timing alternative; no probability or identity confirmation.",
        )

    endpoints = (timed(1, (1, 0, 0), endpoint=True), timed(3, (3, 0, 0), endpoint=True))
    hypotheses = (
        hypothesis("straight-direct", "straight", HypothesisKind.DIRECT_PATH, endpoints),
        hypothesis("straight-dwell", "straight", HypothesisKind.DWELL,
                   (endpoints[0], timed(2, (1, 0, 0)), endpoints[1]), dwell=True),
        hypothesis("detour-direct", "detour", HypothesisKind.DETOUR,
                   (endpoints[0], timed(2, (2, 2, 0)), endpoints[1])),
    )
    return event(name="gap", candidates=candidates, hypotheses=hypotheses)


@pytest.mark.parametrize("requested,source_time,position", [
    (0.1, 0.0, (0, 0, 0)), (0.16, 0.2, (10, 0, 0)),
])
def test_projected_markers_hold_actual_frame_measurement_with_original_time_ref_and_offset(
    projected_event: tuple[EventDetail, tuple[MediaFrame, ...]],
    requested: float, source_time: float, position: Vec3,
) -> None:
    observed, frames = projected_event
    state = timeline_state(RUN_REF, requested, frames, (observed,))
    selection = next(item for item in state.frames if item.camera_id == "CAM_A")
    marker = next(item for item in state.markers if item.camera_id == "CAM_A")
    source = next(f for f in frames if f.camera_id == "CAM_A" and f.timestamp == source_time)
    assert state.timestamp == requested and state.presentation_only
    assert state.synchronization == "SOFT_SYNCHRONIZATION"
    assert selection.status == "AVAILABLE"
    assert selection.requested_timestamp == requested
    assert selection.frame_timestamp == source_time and selection.media_ref == source.media_ref
    assert selection.offset_seconds == pytest.approx(source_time - requested)
    assert marker.timestamp == source_time and marker.source_frame_ref == source.media_ref
    assert marker.sample_offset_seconds == pytest.approx(source_time - requested)
    assert marker.world_position == position
    assert marker.evidence_state == "PROJECTED" and not marker.interpolated
    assert marker.hypothesis_ref is None and marker.candidate_ref is None
    assert marker.world_position != (requested * 50, 0, 0)


def test_nearest_frame_ties_choose_earlier_even_if_input_order_is_reversed(
    projected_event: tuple[EventDetail, tuple[MediaFrame, ...]],
) -> None:
    observed, frames = projected_event
    state = timeline_state(RUN_REF, 0.1, tuple(reversed(frames)), (observed,))
    selections = {item.camera_id: item for item in state.frames}
    assert selections["CAM_A"].frame_timestamp == 0
    assert selections["CAM_B"].frame_timestamp == 0.08
    assert selections["CAM_B"].offset_seconds == pytest.approx(-0.02)
    assert {marker.camera_id: marker.timestamp for marker in state.markers} == {
        "CAM_A": 0.0, "CAM_B": 0.08,
    }


def test_missing_frame_tolerance_does_not_synthesize_a_projected_marker(
    projected_event: tuple[EventDetail, tuple[MediaFrame, ...]],
) -> None:
    observed, frames = projected_event
    camera_a = tuple(f for f in frames if f.camera_id == "CAM_A")
    missing = timeline_state(RUN_REF, 0.1, camera_a, (observed,), tolerance_s=0.099)
    assert len(missing.frames) == 1 and missing.markers == ()
    selection = missing.frames[0]
    assert selection.status == "NO_FRAME_WITHIN_TOLERANCE"
    assert selection.media_ref is None and selection.frame_timestamp is None
    assert selection.offset_seconds is None and selection.requested_timestamp == 0.1
    boundary = timeline_state(RUN_REF, 0.1, camera_a, (observed,), tolerance_s=0.1)
    assert boundary.frames[0].status == "AVAILABLE"
    assert len(boundary.markers) == 1
    empty = timeline_state(RUN_REF, 0.1, (), (observed,))
    assert empty.frames == () and empty.markers == ()


def test_rgb_without_a_matching_measurement_never_acquires_projection(
    projected_event: tuple[EventDetail, tuple[MediaFrame, ...]],
) -> None:
    observed, _ = projected_event
    source = frame("CAM_A", 3, 0.1)
    state = timeline_state(RUN_REF, 0.1, (source,), (observed,), tolerance_s=0)
    assert state.frames[0].status == "AVAILABLE"
    assert state.frames[0].media_ref == source.media_ref
    assert state.markers == ()


def test_all_gap_candidates_and_timing_hypotheses_remain_distinct(gap_event: EventDetail) -> None:
    state = timeline_state(RUN_REF, 2.5, (), (gap_event,))
    assert state.frames == ()
    assert len(state.markers) == gap_event.hypothesis_count == 3
    assert {m.hypothesis_ref for m in state.markers} == {
        hypothesis.hypothesis_id for hypothesis in gap_event.trajectories
    }
    assert {m.candidate_ref for m in state.markers} == {
        candidate.candidate_id for candidate in gap_event.candidates
    }
    positions = {m.hypothesis_ref: m.world_position for m in state.markers}
    assert positions == {"straight-direct": (2.5, 0, 0), "straight-dwell": (2, 0, 0),
                         "detour-direct": (2.5, 1, 0)}
    assert len({m.marker_ref for m in state.markers}) == 3
    assert all(m.timestamp == 2.5 and m.interpolated and m.evidence_state == "INFERRED_GAP"
               for m in state.markers)
    assert all(m.source_frame_ref is None and m.sample_offset_seconds is None
               for m in state.markers)
    assert gap_event.complete is False and gap_event.termination_reason == "MAX_PATHS_REACHED"


@pytest.mark.parametrize("timestamp", [1.0, 3.0])
def test_exact_gap_endpoints_keep_their_canonical_projected_provenance(
    gap_event: EventDetail, timestamp: float,
) -> None:
    state = timeline_state(RUN_REF, timestamp, (), (gap_event,))
    assert len(state.markers) == 3
    assert all(m.timestamp == timestamp and not m.interpolated and m.evidence_state == "PROJECTED"
               for m in state.markers)
    assert {m.world_position for m in state.markers} == {(timestamp, 0, 0)}


def test_exact_inferred_waypoints_stay_inferred_without_interpolation(
    gap_event: EventDetail,
) -> None:
    state = timeline_state(RUN_REF, 2.0, (), (gap_event,))
    markers = {marker.hypothesis_ref: marker for marker in state.markers}
    assert markers["straight-direct"].interpolated
    assert not markers["straight-dwell"].interpolated
    assert not markers["detour-direct"].interpolated
    assert all(marker.evidence_state == "INFERRED_GAP" for marker in markers.values())
    assert markers["straight-dwell"].world_position == (1, 0, 0)
    assert markers["detour-direct"].world_position == (2, 2, 0)


@pytest.mark.parametrize("timestamp", [0.5, 0.999, 3.001, 3.5, 4.1])
def test_gap_sampling_never_extrapolates_before_or_after_each_hypothesis(
    gap_event: EventDetail, timestamp: float,
) -> None:
    assert timeline_state(RUN_REF, timestamp, (), (gap_event,)).markers == ()


def test_timeline_deduplicates_same_rgb_measurement_and_never_mutates_canonical_records(
    projected_event: tuple[EventDetail, tuple[MediaFrame, ...]], gap_event: EventDetail,
) -> None:
    observed, frames = projected_event
    repeated = event(name="same-evidence", projected_path=observed.projected_path, frames=frames)
    originals = tuple(item.model_dump_json() for item in (observed, repeated, gap_event, *frames))
    state = timeline_state(RUN_REF, 0.1, frames, (observed, repeated))
    assert len(state.markers) == 2
    for timestamp in (1.0, 1.75, 2.0, 2.5, 3.0, 4.1):
        timeline_state(RUN_REF, timestamp, frames, (observed, repeated, gap_event))
    assert originals == tuple(item.model_dump_json() for item in
                              (observed, repeated, gap_event, *frames))


def test_canonical_detail_counts_derive_exactly_and_summary_keeps_them(
    gap_event: EventDetail,
) -> None:
    raw = gap_event.model_dump(mode="json")
    raw.pop("candidate_count")
    raw.pop("hypothesis_count")
    detail = EventDetail.model_validate(raw)
    assert detail.candidate_count == len(detail.candidates) == 2
    assert detail.hypothesis_count == len(detail.trajectories) == 3
    summary = EventSummary.model_validate(detail.model_dump(mode="json", exclude={
        "projected_path", "candidates", "trajectories",
    }))
    assert summary.candidate_count == 2 and summary.hypothesis_count == 3
    assert summary.complete is False and summary.termination_reason == "MAX_PATHS_REACHED"


@pytest.mark.parametrize("field,wrong_count", [
    ("candidate_count", 0), ("candidate_count", 1), ("candidate_count", 3),
    ("hypothesis_count", 0), ("hypothesis_count", 2), ("hypothesis_count", 4),
])
def test_detail_cannot_hide_canonical_candidates_or_hypotheses_by_rewriting_summary_counts(
    gap_event: EventDetail, field: str, wrong_count: int,
) -> None:
    raw = gap_event.model_dump(mode="json") | {field: wrong_count}
    with pytest.raises(ValidationError, match="summary count differs from canonical detail"):
        EventDetail.model_validate(raw)


@pytest.mark.parametrize("field,value", [
    ("candidate_count", 2.0), ("candidate_count", "2"), ("candidate_count", True),
    ("hypothesis_count", 3.0), ("hypothesis_count", "3"), ("hypothesis_count", False),
])
def test_detail_and_summary_counts_require_actual_integers_without_coercion(
    gap_event: EventDetail, field: str, value: object,
) -> None:
    raw = gap_event.model_dump(mode="json") | {field: value}
    with pytest.raises(ValidationError):
        EventDetail.model_validate(raw)
    summary = {name: item for name, item in raw.items()
               if name not in ("projected_path", "candidates", "trajectories")}
    with pytest.raises(ValidationError):
        EventSummary.model_validate(summary)


@pytest.mark.parametrize("field", ["candidate_count", "hypothesis_count"])
def test_boolean_zero_cannot_replace_empty_canonical_detail_counts(field: str) -> None:
    raw = event().model_dump(mode="json") | {field: False}
    with pytest.raises(ValidationError):
        EventDetail.model_validate(raw)
