"""Separately approved reference movement annotations and evaluation-only timing.

Annotation construction and approval loading use only the Python standard library
so the existing Blender exporter can call them. Reference annotations remain in
simulation/export/evaluation; inference, ranking and pruning never receive them.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from amidst.domain.trajectory import Event

POLICY_ID = "EXPLICIT_SIMULATION_SEGMENT_MOVEMENT_ANNOTATIONS"
EXPECTED_PROPOSAL = {
    "schema_version": "phase1-reference-movement-policy-proposal-v1",
    "status": "PROPOSED_NOT_APPROVED_NOT_EXECUTED", "policy_id": POLICY_ID,
    "scope": "NEW_SOURCE_BOUND_SYNTHETIC_CASE_EXPORTS_ONLY",
    "reference_partition": "evaluation", "annotation_producer_partition": "simulation_export",
    "segment_kinds": ["MOVING", "DWELL"],
    "moving_rule": "EXPLICIT_RECIPE_SEGMENT_WITH_DISTINCT_FLOOR_CONTACT_ENDPOINTS",
    "dwell_rule": "EXPLICIT_RECIPE_SEGMENT_WITH_IDENTICAL_FLOOR_CONTACT_ENDPOINTS",
    "dwell_location": "DEPARTURE_WAYPOINT_ONLY",
    "exact_gap_intersection": "SUM_DURATION_OF_ANNOTATED_MOVING_SEGMENTS_INTERSECTING_OBSERVED_GAP",
    "candidate_moving_time": (
        "SUM_EXPLICIT_TIMED_HYPOTHESIS_MOVING_SEGMENT_DURATIONS_EXCLUDING_DWELL"
    ),
    "travel_time_error": (
        "ABS_PRIMARY_CANDIDATE_MOVING_TIME_MINUS_INDEPENDENT_REFERENCE_MOVING_TIME"
    ),
    "zero_distance_threshold": "EXACT_ENDPOINT_EQUALITY_NO_NEW_EPSILON",
    "inference_can_read_annotations": False, "reference_used_for_ranking_or_pruning": False,
    "original_hr01_hr04_profiles_modified": False,
    "old_datasets_relabelled_or_overwritten": False, "fresh_version_required_after_approval": True,
    "lock_before_simulation_and_evaluation": True,
}


def reference_content_sha256(value: object) -> str:
    """Use the same canonical hash as the versioned finalization config locks."""
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _digest(value: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        char not in "0123456789abcdef" for char in value
    ):
        raise ValueError("reference movement authority requires SHA-256 bindings")


@dataclass(frozen=True, slots=True)
class ReferenceMovementApproval:
    receipt_json: str
    receipt_content_sha256: str
    proposal_file_sha256: str
    proposal_content_sha256: str
    source_sha256: str
    protocol_sha256: str
    original_human_decisions_sha256: str

    def validate(self) -> None:
        receipt = json.loads(self.receipt_json)
        if not isinstance(receipt, dict):
            raise ValueError("reference movement approval receipt must be a JSON object")
        if (
            reference_content_sha256(receipt) != self.receipt_content_sha256
            or receipt.get("schema_version") != "phase1-reference-movement-approval-v1"
            or receipt.get("decision") != "APPROVE" or receipt.get("policy_id") != POLICY_ID
            or receipt.get("locked_before_simulation_and_evaluation") is not True
            or receipt.get("original_hr01_hr04_profiles_modified") is not False
            or receipt.get("old_results_relabelled") is not False
            or receipt.get("source_sha256") != self.source_sha256
            or receipt.get("protocol_sha256") != self.protocol_sha256
            or receipt.get("original_human_decisions_sha256")
            != self.original_human_decisions_sha256
            or receipt.get("proposal_file_sha256") != self.proposal_file_sha256
            or receipt.get("proposal_content_sha256") != self.proposal_content_sha256
            or self.proposal_content_sha256 != reference_content_sha256(EXPECTED_PROPOSAL)
            or not isinstance(receipt.get("human_approval_id"), str)
            or not receipt["human_approval_id"].strip()
            or not isinstance(receipt.get("human_approval_text"), str)
            or not receipt["human_approval_text"].strip()
        ):
            raise ValueError("reference movement approval/proposal/source/protocol binding differs")
        if not isinstance(receipt.get("approved_at"), str):
            raise ValueError("reference movement approval time must be an ISO timestamp")
        approved_at = datetime.fromisoformat(receipt["approved_at"].replace("Z", "+00:00"))
        if approved_at.tzinfo is None:
            raise ValueError("reference movement approval time requires an explicit timezone")
        for digest in (
            self.receipt_content_sha256, self.proposal_file_sha256, self.proposal_content_sha256,
            self.source_sha256, self.protocol_sha256, self.original_human_decisions_sha256,
        ):
            _digest(digest)


def load_reference_movement_approval(
    approval_path: Path, proposal_path: Path, *, expected_receipt_content_sha256: str,
    expected_source_sha256: str, expected_protocol_sha256: str,
    expected_original_human_decisions_sha256: str,
) -> ReferenceMovementApproval:
    """Require independently locked receipt and source/protocol/original approval hashes."""
    proposal_raw = proposal_path.read_bytes()
    proposal = json.loads(proposal_raw)
    if proposal != EXPECTED_PROPOSAL:
        raise ValueError("reference movement proposal differs from the explicitly approved policy")
    receipt = json.loads(approval_path.read_bytes())
    result = ReferenceMovementApproval(
        receipt_json=json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False),
        receipt_content_sha256=expected_receipt_content_sha256,
        proposal_file_sha256=hashlib.sha256(proposal_raw).hexdigest(),
        proposal_content_sha256=reference_content_sha256(proposal),
        source_sha256=expected_source_sha256, protocol_sha256=expected_protocol_sha256,
        original_human_decisions_sha256=expected_original_human_decisions_sha256,
    )
    result.validate()
    return result


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("reference movement " + label + " must be a finite number")
    return float(value)


def _point(value: Any) -> tuple[float, float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError("reference movement floor contact must contain exactly three coordinates")
    return (_number(value[0], "coordinate"), _number(value[1], "coordinate"),
            _number(value[2], "coordinate"))


def annotate_reference_movement(
    waypoints: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], ...]:
    """Explicit recipe segment labels; exact 3D equality is the only zero-distance rule."""
    if len(waypoints) < 2:
        raise ValueError("reference annotations require at least two explicit source waypoints")
    points = [(_number(row["timestamp"], "timestamp"), _point(row["position"]))
              for row in waypoints]
    if points[0][0] < 0:
        raise ValueError("reference timestamps must be nonnegative")
    departure = points[0][1]
    moved = False
    result = []
    for before, after in zip(points[:-1], points[1:], strict=True):
        start, a = before
        end, b = after
        if end <= start:
            raise ValueError("reference source segments must have strictly ordered timestamps")
        dwell = a == b
        if dwell and (moved or a != departure):
            raise ValueError("reference dwell is allowed only at the initial departure waypoint")
        moved |= not dwell
        result.append({
            "kind": "DWELL" if dwell else "MOVING", "start_time_s": start, "end_time_s": end,
            "start_footpoint_bu": list(a), "end_footpoint_bu": list(b), "duration_s": end - start,
        })
    return tuple(result)


def build_reference_annotation_document(
    waypoints: Sequence[Mapping[str, Any]], approval: ReferenceMovementApproval, *,
    target_id: str, trajectory_id: str, dataset_version: str,
) -> dict[str, Any]:
    approval.validate()
    if any(not isinstance(value, str) or not value.strip()
           for value in (target_id, trajectory_id, dataset_version)):
        raise ValueError("fresh reference annotations require target/trajectory/dataset IDs")
    segments = annotate_reference_movement(waypoints)
    return {
        "schema_version": "phase1-reference-movement-annotations-v1",
        "policy_id": POLICY_ID, "source_sha256": approval.source_sha256,
        "protocol_sha256": approval.protocol_sha256,
        "original_human_decisions_sha256": approval.original_human_decisions_sha256,
        "approval_receipt_content_sha256": approval.receipt_content_sha256,
        "proposal_file_sha256": approval.proposal_file_sha256,
        "proposal_content_sha256": approval.proposal_content_sha256,
        "dataset_version": dataset_version, "target_id": target_id, "trajectory_id": trajectory_id,
        "source_extent_s": [segments[0]["start_time_s"], segments[-1]["end_time_s"]],
        "segments": list(segments),
        "annotation_generation": "EXPLICIT_RECIPE_SEGMENTS_DURING_FRESH_EXPORT",
        "reference_partition": "evaluation", "inference_can_read_annotations": False,
        "zero_distance_threshold": "EXACT_ENDPOINT_EQUALITY_NO_NEW_EPSILON",
    }


def _checked_segments(
    document: Mapping[str, Any], approval: ReferenceMovementApproval, dataset_version: str,
) -> tuple[dict[str, Any], ...]:
    approval.validate()
    if (
        document.get("schema_version") != "phase1-reference-movement-annotations-v1"
        or document.get("policy_id") != POLICY_ID
        or document.get("source_sha256") != approval.source_sha256
        or document.get("protocol_sha256") != approval.protocol_sha256
        or document.get("original_human_decisions_sha256")
        != approval.original_human_decisions_sha256
        or document.get("approval_receipt_content_sha256") != approval.receipt_content_sha256
        or document.get("proposal_file_sha256") != approval.proposal_file_sha256
        or document.get("proposal_content_sha256") != approval.proposal_content_sha256
        or document.get("dataset_version") != dataset_version
        or document.get("annotation_generation") != "EXPLICIT_RECIPE_SEGMENTS_DURING_FRESH_EXPORT"
        or document.get("reference_partition") != "evaluation"
        or document.get("inference_can_read_annotations") is not False
        or document.get("zero_distance_threshold") != "EXACT_ENDPOINT_EQUALITY_NO_NEW_EPSILON"
    ):
        raise ValueError("reference annotations differ from fresh approved source/policy binding")
    raw = document["segments"]
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError("reference annotations must explicitly cover the complete source extent")
    waypoints = [{"timestamp": raw[0]["start_time_s"], "position": raw[0]["start_footpoint_bu"]}]
    previous = None
    for row in raw:
        start = _number(row["start_time_s"], "timestamp")
        end = _number(row["end_time_s"], "timestamp")
        a, b = _point(row["start_footpoint_bu"]), _point(row["end_footpoint_bu"])
        if previous is not None and (start != previous[0] or a != previous[1]):
            raise ValueError("reference annotations must have contiguous time and space")
        if _number(row["duration_s"], "duration") != end - start:
            raise ValueError("reference annotation duration differs from explicit time endpoints")
        previous = (end, b)
        waypoints.append({"timestamp": end, "position": b})
    checked = annotate_reference_movement(waypoints)
    if any(original["kind"] != validated["kind"]
           for original, validated in zip(raw, checked, strict=True)):
        raise ValueError("reference MOVING/DWELL labels differ from exact 3D endpoint equality")
    if document.get("source_extent_s") != [checked[0]["start_time_s"], checked[-1]["end_time_s"]]:
        raise ValueError("reference annotation source extent differs from explicit segments")
    return checked


def evaluate_reference_movement(
    event: Event, document: Mapping[str, Any], approval: ReferenceMovementApproval, *,
    expected_dataset_version: str,
) -> dict[str, Any]:
    """Compare primary/all explicit timing movement with independent annotated motion.

    Call only after primary inference artifacts are frozen. Intersections use the
    exact observed GAP extent; source annotation coverage is required, with no
    extrapolation. The first timing of the first candidate stays primary.
    """
    from amidst.domain.trajectory import Event as EventModel

    event = EventModel.model_validate(event.model_dump())
    segments = _checked_segments(document, approval, expected_dataset_version)
    start, end = event.time_range
    if document.get("target_id") != event.target_id or (
        start < segments[0]["start_time_s"] or end > segments[-1]["end_time_s"] or end <= start
    ):
        raise ValueError("reference annotation target/exact observed GAP extent differs")
    moving = math.fsum(
        max(0.0, min(end, row["end_time_s"]) - max(start, row["start_time_s"]))
        for row in segments if row["kind"] == "MOVING"
    )
    dwell = math.fsum(
        max(0.0, min(end, row["end_time_s"]) - max(start, row["start_time_s"]))
        for row in segments if row["kind"] == "DWELL"
    )
    records = []
    primary = None
    primary_candidate = event.candidates[0].candidate_id if event.candidates else None
    for hypothesis in event.trajectories:
        if hypothesis.timed_points[0].timestamp != start or (
            hypothesis.timed_points[-1].timestamp != end
        ):
            raise ValueError("hypothesis timed points must cover the exact observed GAP extent")
        durations = []
        for segment in hypothesis.segments:
            covered = [point for point in hypothesis.timed_points
                       if segment.time_range[0] <= point.timestamp <= segment.time_range[1]]
            for first, last in zip(covered[:-1], covered[1:], strict=True):
                stationary = first.world_position == last.world_position
                if stationary != (segment.kind.value == "DWELL"):
                    raise ValueError("hypothesis MOVEMENT/DWELL violates exact endpoint equality")
                if not stationary:
                    durations.append(last.timestamp - first.timestamp)
        duration = math.fsum(durations)
        record = {"hypothesis_id": hypothesis.hypothesis_id,
                  "candidate_id": hypothesis.candidate_id,
                  "moving_time_s": duration, "travel_time_error_s": abs(duration - moving)}
        records.append(record)
        if primary is None and hypothesis.candidate_id == primary_candidate:
            primary = record
    return {
        "travel_time_error_s": None if primary is None else primary["travel_time_error_s"],
        "travel_time_error_status": "AVAILABLE_APPROVED_REFERENCE_MOVEMENT" if primary else (
            "N/A_NO_PRIMARY_TIMED_HYPOTHESIS"
        ), "reference_moving_time_s": moving, "reference_dwell_time_s": dwell,
        "reference_gap_time_range_s": [start, end],
        "primary_hypothesis_id": None if primary is None else primary["hypothesis_id"],
        "primary_candidate_moving_time_s": None if primary is None else primary["moving_time_s"],
        "candidate_moving_times": records,
        "reference_annotation_content_sha256": reference_content_sha256(document),
        "reference_policy_id": POLICY_ID,
        "reference_approval_receipt_content_sha256": approval.receipt_content_sha256,
        "reference_proposal_file_sha256": approval.proposal_file_sha256,
        "zero_distance_threshold": "EXACT_ENDPOINT_EQUALITY_NO_NEW_EPSILON",
        "annotations_used_for_inference_ranking_or_pruning": False,
        "primary_selection_uses_reference_error": False,
    }
