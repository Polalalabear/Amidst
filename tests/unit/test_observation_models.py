"""Domain-only provenance, nullable compatibility and serialization invariants."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance
from amidst.domain.evidence import GapReason, ObservationFrame, VisibilityStatus
from amidst.domain.observation import Observation, ProjectedPoint
from amidst.domain.trajectory import (
    CandidateTrajectory,
    Event,
    ReconstructionResult,
    TerminationReason,
)


def _frame(timestamp: float = 1, **updates: Any) -> ObservationFrame:
    payload = dict(
        frame_id=int(timestamp),
        timestamp=timestamp,
        target_id="target",
        camera_id="CAM_A",
        status=VisibilityStatus.OBSERVED,
        point_2d=(10, 20),
        provenance=Provenance.OBSERVED,
    )
    payload.update(updates)
    return ObservationFrame.model_validate(payload)


def _point(timestamp: float = 1, **updates: Any) -> ProjectedPoint:
    payload = dict(
        point_id=f"point_{timestamp}",
        camera_id="CAM_A",
        plane_id="floor_1",
        timestamp=timestamp,
        world_position=(1, 2, 0),
        observation_id="obs_a",
    )
    payload.update(updates)
    return ProjectedPoint.model_validate(payload)


def _observation(**updates: Any) -> Observation:
    payload = dict(
        observation_id="obs_a",
        target_id="target",
        camera_id="CAM_A",
        start_time=1,
        end_time=2,
        frames=(_frame(1), _frame(2)),
    )
    payload.update(updates)
    return Observation.model_validate(payload)


def _candidate(**updates: Any) -> CandidateTrajectory:
    payload = dict(
        candidate_id="path_a",
        start_observation_id="obs_a",
        end_observation_id="obs_b",
        polyline=((0, 0, 0), (2, 0, 0)),
        path_length=2,
        minimum_travel_time=1,
        estimated_travel_time=2,
    )
    payload.update(updates)
    return CandidateTrajectory.model_validate(payload)


def test_observation_nullable_phase2_fields_are_preserved_in_json() -> None:
    observed = _observation()
    payload = observed.model_dump(mode="json")
    nullable = (
        "track_ids",
        "stitching_count",
        "fragment_count",
        "appearance_embedding",
        "appearance_labels",
        "appearance_quality",
        "tracking_quality",
        "source_video_reference",
        "entry_direction",
        "exit_direction",
        "projection_quality",
        "occlusion_quality",
        "observation_quality",
    )
    assert all(field in payload and payload[field] is None for field in nullable)
    assert Observation.model_validate_json(observed.model_dump_json()) == observed
    assert observed.provenance == Provenance.OBSERVED


def test_projected_observation_retains_original_pixels_and_roundtrips() -> None:
    projected = _observation(provenance=Provenance.PROJECTED, projected_path=(_point(1), _point(2)))
    assert all(frame.provenance == Provenance.OBSERVED for frame in projected.frames)
    assert all(point.provenance == Provenance.PROJECTED for point in projected.projected_path)
    assert Observation.model_validate_json(projected.model_dump_json()) == projected
    assert ProjectedPoint.model_validate_json(_point().model_dump_json()) == _point()


@pytest.mark.parametrize(
    "updates",
    [
        {"end_time": 0},
        {"frames": (_frame(2), _frame(1))},
        {"frames": (_frame(1), _frame(1))},
        {"frames": (_frame(1, camera_id="CAM_B"),)},
        {"frames": (_frame(1, target_id="other_target"),)},
        {"frames": (_frame(3),)},
        {
            "frames": (
                _frame(
                    1,
                    status=VisibilityStatus.GAP,
                    point_2d=None,
                    provenance=None,
                    gap_reason=GapReason.OCCLUDED,
                ),
            )
        },
        {"projected_path": (_point(),)},
        {"provenance": Provenance.PROJECTED},
        {"provenance": Provenance.GROUND_TRUTH},
        {"ground_truth_3d": (1, 2, 0)},
    ],
)
def test_observation_rejects_invalid_time_identity_gap_and_truth(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _observation(**updates)


@pytest.mark.parametrize(
    "path",
    [
        (_point(2), _point(1)),
        (_point(1), _point(1)),
        (_point(1, camera_id="CAM_B"),),
        (_point(1, observation_id="other_obs"),),
        (_point(3),),
        (_point(1, point_id="same"), _point(2, point_id="same")),
    ],
)
def test_projected_observation_rejects_inconsistent_path(path: tuple[ProjectedPoint, ...]) -> None:
    with pytest.raises(ValidationError):
        _observation(provenance=Provenance.PROJECTED, projected_path=path)


@pytest.mark.parametrize(
    "updates",
    [
        {"projection_quality": -0.1},
        {"projection_quality": 1.1},
        {"projection_quality": float("nan")},
        {"timestamp": float("inf")},
        {"world_position": (0, float("inf"), 0)},
        {"plane_id": ""},
        {"provenance": "GROUND_TRUTH"},
        {"ground_truth_3d": (0, 0, 0)},
    ],
)
def test_projected_point_rejects_nonfinite_quality_truth_and_wrong_provenance(
    updates: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        _point(**updates)


def test_single_instant_and_empty_observed_shell_schema_are_explicitly_allowed() -> None:
    assert _observation(end_time=1, frames=(_frame(1),)).start_time == 1
    assert _observation(frames=()).frames == ()


def test_nullable_phase2_fields_accept_explicit_future_interface_values() -> None:
    observation = _observation(
        track_ids=("track_1",),
        stitching_count=0,
        fragment_count=1,
        appearance_embedding=(0.2, 0.3),
        appearance_labels=("blue",),
        appearance_quality=0.8,
        entry_direction=(1, 0, 0),
        tracking_quality=1,
    )
    assert observation.track_ids == ("track_1",)
    assert observation.appearance_quality == 0.8
    with pytest.raises(ValidationError):
        _observation(stitching_count=-1)
    with pytest.raises(ValidationError):
        _observation(appearance_embedding=(float("nan"),))


def test_candidate_result_and_event_roundtrip_and_termination_state() -> None:
    candidate = _candidate()
    result = ReconstructionResult(
        candidates=(candidate,),
        termination_reason=TerminationReason.MAX_PATHS_REACHED,
        complete=False,
        expanded_nodes=5,
    )
    event = Event(
        event_id="evt_a",
        target_id="target",
        time_range=(1, 4),
        observation_ids=("obs_a", "obs_b"),
        candidates=(candidate,),
        termination_reason=TerminationReason.MAX_PATHS_REACHED,
    )
    assert candidate.provenance == Provenance.INFERRED_GAP
    assert CandidateTrajectory.model_validate_json(candidate.model_dump_json()) == candidate
    assert ReconstructionResult.model_validate_json(result.model_dump_json()) == result
    assert Event.model_validate_json(event.model_dump_json()) == event
    assert result.complete is False
    assert result.termination_reason.value == "MAX_PATHS_REACHED"


@pytest.mark.parametrize(
    ("termination_reason", "complete"),
    [
        (TerminationReason.COMPLETE, False),
        (TerminationReason.NO_FEASIBLE_PATH, False),
        (TerminationReason.MAX_PATHS_REACHED, True),
        (TerminationReason.MAX_SEARCH_NODES, True),
        (TerminationReason.MAX_BRANCH_FACTOR, True),
        (TerminationReason.SEARCH_TIMEOUT, True),
    ],
)
def test_reconstruction_result_rejects_inconsistent_completion_state(
    termination_reason: TerminationReason, complete: bool
) -> None:
    with pytest.raises(ValidationError):
        ReconstructionResult(termination_reason=termination_reason, complete=complete)


def test_no_feasible_path_requires_an_exhaustive_empty_result() -> None:
    result = ReconstructionResult(termination_reason=TerminationReason.NO_FEASIBLE_PATH)
    assert result.complete is True
    assert result.candidates == ()
    with pytest.raises(ValidationError):
        ReconstructionResult(
            candidates=(_candidate(),),
            termination_reason=TerminationReason.NO_FEASIBLE_PATH,
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"polyline": ((0, 0, 0),)},
        {"polyline": ((0, 0, 0), (float("inf"), 0, 0))},
        {"path_length": -1},
        {"minimum_travel_time": float("inf")},
        {"estimated_travel_time": 0.5},
        {"temporal_cost": float("nan")},
        {"provenance": "GROUND_TRUTH"},
        {"ground_truth_3d": (0, 0, 0)},
    ],
)
def test_candidate_rejects_invalid_structure_nonfinite_and_truth(updates: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _candidate(**updates)


def test_event_rejects_invalid_time_and_unbound_or_repeated_identities() -> None:
    payload = dict(
        event_id="evt",
        target_id="target",
        time_range=(1, 2),
        observation_ids=("obs_a", "obs_b"),
        candidates=(_candidate(),),
        termination_reason=TerminationReason.COMPLETE,
    )
    for updates in (
        {"time_range": (2, 1)},
        {"observation_ids": ("obs_a",)},
        {"observation_ids": ("obs_a", "obs_a", "obs_b")},
        {"candidates": (_candidate(), _candidate())},
        {"ground_truth_3d": (0, 0, 0)},
    ):
        with pytest.raises(ValidationError):
            Event.model_validate(payload | updates)
    with pytest.raises(ValidationError):
        ReconstructionResult(
            candidates=(_candidate(), _candidate()), termination_reason=TerminationReason.COMPLETE
        )
