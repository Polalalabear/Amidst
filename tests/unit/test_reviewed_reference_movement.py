"""Synthetic reference-annotation approval, exact movement and primary-order tests."""

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from amidst.domain.trajectory import (
    CandidateTrajectory,
    Event,
    HypothesisKind,
    SegmentKind,
    TerminationReason,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)
from amidst.finalization.reviewed_reference_movement import (
    EXPECTED_PROPOSAL,
    POLICY_ID,
    ReferenceMovementApproval,
    annotate_reference_movement,
    build_reference_annotation_document,
    evaluate_reference_movement,
    load_reference_movement_approval,
    reference_content_sha256,
)

SOURCE, PROTOCOL, ORIGINAL = "a" * 64, "b" * 64, "c" * 64
VERSION = "SYNTHETIC_FRESH_ANNOTATION_TEST_ONLY"


@pytest.fixture
def approval(tmp_path: Path) -> ReferenceMovementApproval:
    proposal = tmp_path / "proposal.json"
    proposal.write_text(json.dumps(EXPECTED_PROPOSAL, sort_keys=True) + "\n")
    receipt = {
        "schema_version": "phase1-reference-movement-approval-v1", "decision": "APPROVE",
        "policy_id": POLICY_ID, "human_approval_id": "SYNTHETIC_TEST_ONLY_NOT_SCHOOL_APPROVAL",
        "human_approval_text": "SYNTHETIC_ENGINEERING_RECEIPT",
        "approved_at": "2026-10-07T15:35:00Z", "locked_before_simulation_and_evaluation": True,
        "original_hr01_hr04_profiles_modified": False, "old_results_relabelled": False,
        "source_sha256": SOURCE, "protocol_sha256": PROTOCOL,
        "original_human_decisions_sha256": ORIGINAL,
        "proposal_file_sha256": hashlib.sha256(proposal.read_bytes()).hexdigest(),
        "proposal_content_sha256": reference_content_sha256(EXPECTED_PROPOSAL),
    }
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
    return load_reference_movement_approval(
        path, proposal, expected_receipt_content_sha256=reference_content_sha256(receipt),
        expected_source_sha256=SOURCE, expected_protocol_sha256=PROTOCOL,
        expected_original_human_decisions_sha256=ORIGINAL,
    )


def _event(*, gap_start: float = 0, gap_end: float = 10) -> Event:
    duration = gap_end - gap_start
    a, b = (3., 5., 0.), (7., 5., 0.)
    minimum = duration * .6
    slack = duration - minimum
    candidate = CandidateTrajectory(
        candidate_id="direct", start_observation_id="observed-departure",
        end_observation_id="observed-recovery", polyline=(a, b), path_length=4,
        minimum_travel_time=minimum, estimated_travel_time=duration,
    )
    uniform = TrajectoryHypothesis(
        hypothesis_id="primary-uniform", candidate_id="direct", kind=HypothesisKind.SLOWER_MOVEMENT,
        minimum_travel_time=minimum, temporal_slack=slack, movement_duration=duration,
        uncertainty="SYNTHETIC_TIMING", timed_points=(
            TimedTrajectoryPoint(timestamp=gap_start, world_position=a),
            TimedTrajectoryPoint(timestamp=gap_end, world_position=b),
        ), segments=(TrajectorySegment(
            time_range=(gap_start, gap_end), kind=SegmentKind.MOVEMENT,
        ),),
    )
    dwell = TrajectoryHypothesis(
        hypothesis_id="alternative-departure-dwell", candidate_id="direct",
        kind=HypothesisKind.DWELL,
        minimum_travel_time=minimum, temporal_slack=slack, movement_duration=minimum,
        dwell_duration=slack, uncertainty="SYNTHETIC_TIMING", timed_points=(
            TimedTrajectoryPoint(timestamp=gap_start, world_position=a),
            TimedTrajectoryPoint(timestamp=gap_start + slack, world_position=a),
            TimedTrajectoryPoint(timestamp=gap_end, world_position=b),
        ), segments=(
            TrajectorySegment(time_range=(gap_start, gap_start + slack), kind=SegmentKind.DWELL),
            TrajectorySegment(time_range=(gap_start + slack, gap_end), kind=SegmentKind.MOVEMENT),
        ),
    )
    return Event(
        event_id="synthetic-reference-test", target_id="marker",
        observation_ids=("observed-departure", "observed-recovery"),
        time_range=(gap_start, gap_end),
        candidates=(candidate,), trajectories=(uniform, dwell),
        termination_reason=TerminationReason.COMPLETE,
    )


def _document(approval: ReferenceMovementApproval, *, dwell: bool = True) -> dict[str, Any]:
    waypoints = [{"timestamp": 0, "position": (3., 5., 0.)}]
    if dwell:
        waypoints.append({"timestamp": 4, "position": (3., 5., 0.)})
    waypoints.append({"timestamp": 10, "position": (7., 5., 0.)})
    return build_reference_annotation_document(
        waypoints, approval, target_id="marker", trajectory_id="synthetic-explicit-reference",
        dataset_version=VERSION,
    )


def test_departure_dwell_definition_keeps_reference_and_primary_independent(
    approval: ReferenceMovementApproval,
) -> None:
    event, document = _event(), _document(approval)
    before = event.model_dump_json()
    result = evaluate_reference_movement(
        event, document, approval, expected_dataset_version=VERSION,
    )
    assert event.model_dump_json() == before
    assert result["reference_moving_time_s"] == 6
    assert result["reference_dwell_time_s"] == 4
    assert result["primary_candidate_moving_time_s"] == 10
    assert result["travel_time_error_s"] == 4
    assert result["primary_hypothesis_id"] == "primary-uniform"
    assert [row["travel_time_error_s"] for row in result["candidate_moving_times"]] == [4, 0]
    assert result["primary_selection_uses_reference_error"] is False


def test_all_moving_reference_can_equal_gap_only_through_explicit_annotations(
    approval: ReferenceMovementApproval,
) -> None:
    result = evaluate_reference_movement(
        _event(), _document(approval, dwell=False), approval, expected_dataset_version=VERSION,
    )
    assert result["reference_moving_time_s"] == 10
    assert result["reference_dwell_time_s"] == 0
    assert result["travel_time_error_s"] == 0


def test_exact_gap_intersection_subtracts_only_annotated_overlap(
    approval: ReferenceMovementApproval,
) -> None:
    result = evaluate_reference_movement(
        _event(gap_start=2, gap_end=8), _document(approval), approval,
        expected_dataset_version=VERSION,
    )
    assert result["reference_moving_time_s"] == 4
    assert result["reference_dwell_time_s"] == 2
    assert result["primary_candidate_moving_time_s"] == 6
    assert result["travel_time_error_s"] == 2


def test_exact_three_dimensional_equality_introduces_no_distance_epsilon() -> None:
    segments = annotate_reference_movement([
        {"timestamp": 0, "position": (0, 0, 0)},
        {"timestamp": 1, "position": (0, 0, 1e-30)},
    ])
    assert segments[0]["kind"] == "MOVING"
    assert annotate_reference_movement([
        {"timestamp": 0, "position": (0, 0, 0)},
        {"timestamp": 1, "position": (0, 0, 0)},
    ])[0]["kind"] == "DWELL"


def test_dwell_after_movement_or_at_other_waypoint_is_rejected() -> None:
    with pytest.raises(ValueError, match="initial departure"):
        annotate_reference_movement([
            {"timestamp": 0, "position": (0, 0, 0)},
            {"timestamp": 1, "position": (1, 0, 0)},
            {"timestamp": 2, "position": (1, 0, 0)},
        ])


@pytest.mark.parametrize("change", [
    {"source_sha256": "d" * 64}, {"protocol_sha256": "d" * 64},
    {"original_human_decisions_sha256": "d" * 64},
    {"proposal_file_sha256": "d" * 64}, {"receipt_content_sha256": "d" * 64},
])
def test_separate_approval_cannot_transfer_to_another_source_protocol_or_proposal(
    approval: ReferenceMovementApproval, change: dict[str, str],
) -> None:
    with pytest.raises(ValueError, match="binding differs"):
        replace(approval, **change).validate()


@pytest.mark.parametrize("change", [
    {"decision": "KEEP_REVIEW"}, {"locked_before_simulation_and_evaluation": False},
    {"original_hr01_hr04_profiles_modified": True}, {"old_results_relabelled": True},
    {"human_approval_id": ""}, {"human_approval_text": ""},
])
def test_mutating_even_rehashed_receipt_cannot_bypass_explicit_approval_boundary(
    approval: ReferenceMovementApproval, change: dict[str, Any],
) -> None:
    receipt = json.loads(approval.receipt_json) | change
    changed = replace(approval, receipt_json=json.dumps(receipt),
                      receipt_content_sha256=reference_content_sha256(receipt))
    with pytest.raises(ValueError, match="binding differs"):
        changed.validate()


@pytest.mark.parametrize("mutation", ["kind", "time_gap", "spatial_gap", "duration", "extent"])
def test_reference_annotations_must_preserve_exact_labels_and_complete_partition(
    approval: ReferenceMovementApproval, mutation: str,
) -> None:
    document = deepcopy(_document(approval))
    if mutation == "kind":
        document["segments"][0]["kind"] = "MOVING"
    elif mutation == "time_gap":
        document["segments"][1]["start_time_s"] = 4.1
    elif mutation == "spatial_gap":
        document["segments"][1]["start_footpoint_bu"][0] += 1e-12
    elif mutation == "duration":
        document["segments"][1]["duration_s"] = 7
    else:
        document["source_extent_s"] = [1, 10]
    with pytest.raises(ValueError):
        evaluate_reference_movement(_event(), document, approval, expected_dataset_version=VERSION)


@pytest.mark.parametrize("mutation", ["source", "target", "dataset", "approval"])
def test_wrong_source_target_fresh_version_or_policy_receipt_is_rejected(
    approval: ReferenceMovementApproval, mutation: str,
) -> None:
    document = deepcopy(_document(approval))
    field = {"source": "source_sha256", "target": "target_id", "dataset": "dataset_version",
             "approval": "approval_receipt_content_sha256"}[mutation]
    document[field] = "WRONG_BINDING"
    with pytest.raises(ValueError):
        evaluate_reference_movement(_event(), document, approval, expected_dataset_version=VERSION)


def test_no_reference_clipping_or_extrapolation(approval: ReferenceMovementApproval) -> None:
    with pytest.raises(ValueError, match="GAP extent"):
        evaluate_reference_movement(
            _event(gap_end=12), _document(approval), approval, expected_dataset_version=VERSION,
        )


def test_annotation_producer_is_importable_without_third_party_runtime() -> None:
    root = Path(__file__).parents[2]
    script = (
        "import sys; sys.path.insert(0, sys.argv[1]); "
        "from amidst.finalization.reviewed_reference_movement import annotate_reference_movement; "
        "assert annotate_reference_movement([{'timestamp':0,'position':[0,0,0]},"
        "{'timestamp':1,'position':[1,0,0]}])[0]['kind']=='MOVING'"
    )
    result = subprocess.run([sys.executable, "-S", "-c", script, str(root / "src")],
                            capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode()
