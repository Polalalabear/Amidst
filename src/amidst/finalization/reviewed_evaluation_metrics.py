"""Independent local route and directed-handoff inventories for reviewed metrics.

The denominator comes from the complete source certificate and observed endpoints,
never from emitted corridors, Ground Truth, simulation recipes or engine topology.
The frozen eligibility counts one canonical direct representative of the single
source-distinct class. It does not enumerate every curve in the office or certify
unapproved school transitions.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from amidst.domain.common import DomainModel, Vec3
from amidst.domain.observation import Observation
from amidst.domain.stream import ObservationAggregation
from amidst.domain.trajectory import CandidateTrajectory
from amidst.finalization.reviewed_authority import (
    ReviewedAuthority,
    ReviewedBaselineRun,
    ReviewedInferenceContext,
    validate_reviewed_endpoints,
)
from amidst.finalization.route_inventory import reviewed_rectangle_inventory
from amidst.obstacle_volume_authority import content_sha256
from amidst.scene_geometry import GeometryAuthorityError


class ReviewedMetricInventory(DomainModel):
    schema_version: Literal["phase1-reviewed-independent-metric-inventory-v1"] = (
        "phase1-reviewed-independent-metric-inventory-v1"
    )
    result_type: Literal["FORMAL"] = "FORMAL"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    human_decisions_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    certificate_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_review_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_route_proof_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_camera_calibration_content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    frozen_config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope_id: str
    floor_id: str
    zone_id: str
    start_observation: Observation
    end_observation: Observation
    canonical_direct_polyline_m: tuple[Vec3, Vec3]
    canonical_route_class_id: str
    directed_local_handoff_id: str
    eligibility: Literal["ONE_CANONICAL_DIRECT_ROUTE_PER_SOURCE_DISTINCT_CLASS"] = (
        "ONE_CANONICAL_DIRECT_ROUTE_PER_SOURCE_DISTINCT_CLASS"
    )
    source_distinct_route_classes: Literal[1] = 1
    eligible_feasible_route_classes: Literal[0, 1]
    max_speed_m_s: float = Field(gt=0)
    gap_duration_s: float = Field(gt=0)
    minimum_travel_time_s: float = Field(gt=0)
    endpoint_tolerance_m: float = Field(gt=0)
    ground_truth_read: Literal[False] = False
    simulation_recipe_read: Literal[False] = False
    engine_corridor_or_topology_used_for_inventory: Literal[False] = False
    all_geometric_curves_enumerated: Literal[False] = False
    approved_portal_or_cross_floor_transitions: Literal[0] = 0

    @model_validator(mode="after")
    def consistent_observed_connector(self) -> Self:
        start, end = self.start_observation, self.end_observation
        if not start.projected_path or not end.projected_path or (
            start.target_id != end.target_id or start.camera_id == end.camera_id
            or start.end_time >= end.start_time
            or self.canonical_direct_polyline_m != (
                start.projected_path[-1].world_position, end.projected_path[0].world_position,
            )
            or self.gap_duration_s != end.start_time - start.end_time
            or self.minimum_travel_time_s != (
                math.dist(*self.canonical_direct_polyline_m) / self.max_speed_m_s
            )
            or self.eligible_feasible_route_classes != int(
                self.minimum_travel_time_s <= self.gap_duration_s
            )
            or any(not math.isfinite(value) for value in (
                self.max_speed_m_s, self.gap_duration_s, self.minimum_travel_time_s,
                self.endpoint_tolerance_m,
            ))
        ):
            raise ValueError("independent metric inventory differs from its observed connector")
        return self


def build_reviewed_metric_inventory(
    aggregation: ObservationAggregation, context: ReviewedInferenceContext,
    authority: ReviewedAuthority, *, frozen_config_sha256: str,
    endpoint_tolerance_m: float,
) -> ReviewedMetricInventory:
    """Exhaust the declared route class and directed endpoint-camera population.

    A convex complete free rectangle has one fixed-endpoint homotopy class. Its
    direct connector is the frozen canonical representative. Approved maximum
    speed independently determines whether that representative is feasible in
    this observed GAP. Two fresh source-bound camera observations establish the
    ordered local handoff; no FOV overlap, portal or floor-transition is inferred.
    """
    start, end = validate_reviewed_endpoints(aggregation, context, authority)
    proof = reviewed_rectangle_inventory(authority.provider)
    if proof["status"] != "PASS_SINGLE_MAJOR_ROUTE_CLASS" or proof[
        "source_distinct_route_classes"
    ] != 1:
        raise ValueError("independent route metric requires the complete single-class source proof")
    native = context.computation_context
    a, b = start.projected_path[-1].world_position, end.projected_path[0].world_position
    speed = float(authority.approved_input_lock["timing"]["max_speed_m_s"])
    minimum = math.dist(a, b) / speed
    gap = end.start_time - start.end_time
    identities = {
        "source_sha256": authority.source_sha256,
        "certificate_content_sha256": authority.certificate_content_sha256,
        "scope_id": proof["scope_id"], "frozen_config_sha256": frozen_config_sha256,
        "start_observation": start.model_dump(mode="json"),
        "end_observation": end.model_dump(mode="json"),
    }
    token = content_sha256(identities)
    return ReviewedMetricInventory(
        source_sha256=authority.source_sha256,
        human_decisions_sha256=authority.human_decisions_sha256,
        certificate_content_sha256=authority.certificate_content_sha256,
        semantic_review_content_sha256=authority.semantic_review_content_sha256,
        source_route_proof_content_sha256=content_sha256(proof),
        source_camera_calibration_content_sha256=content_sha256([
            camera.model_dump(mode="json") for camera in sorted(
                native.cameras, key=lambda camera: camera.camera_id,
            )
        ]), frozen_config_sha256=frozen_config_sha256,
        scope_id=str(proof["scope_id"]), floor_id=native.zone.floor_id,
        zone_id=native.zone.zone_id, start_observation=start, end_observation=end,
        canonical_direct_polyline_m=(a, b),
        canonical_route_class_id="reviewed-direct-class:" + token,
        directed_local_handoff_id="reviewed-local-handoff:" + token,
        eligible_feasible_route_classes=1 if minimum <= gap else 0, max_speed_m_s=speed,
        gap_duration_s=gap, minimum_travel_time_s=minimum,
        endpoint_tolerance_m=endpoint_tolerance_m,
    )


def _canonical_direct(
    points: tuple[Vec3, ...], inventory: ReviewedMetricInventory,
) -> bool:
    a, b = inventory.canonical_direct_polyline_m
    tolerance = inventory.endpoint_tolerance_m
    if math.dist(points[0], a) > tolerance or math.dist(points[-1], b) > tolerance:
        return False
    direction = tuple(last - first for first, last in zip(a, b, strict=True))
    length_squared = math.fsum(value * value for value in direction)
    previous_fraction = -math.inf
    for point in points:
        fraction = math.fsum((value - first) * delta for value, first, delta in zip(
            point, a, direction, strict=True,
        )) / length_squared
        closest: Vec3 = tuple(first + fraction * delta for first, delta in zip(
            a, direction, strict=True,
        ))  # type: ignore[assignment]
        if (
            fraction < 0 or fraction > 1 or fraction < previous_fraction
            or math.dist(point, closest) > tolerance
        ):
            return False
        previous_fraction = fraction
    return True


def evaluate_reviewed_inventory_metrics(
    run: ReviewedBaselineRun, inventory: ReviewedMetricInventory,
    authority: ReviewedAuthority,
) -> dict[str, Any]:
    """Count source-authorized candidates and camera handoffs without reading GT.

    Each distinct candidate contributes one observed endpoint-camera handoff.
    Alternate uniform/dwell hypotheses never inflate either denominator. This
    cannot measure hidden intermediate-camera sequences absent from the existing
    CandidateTrajectory schema, and does not claim whole-school topology coverage.
    """
    authority.validate()
    inventory = ReviewedMetricInventory.model_validate(inventory.model_dump())
    run = ReviewedBaselineRun.model_validate(run.model_dump())
    proof = reviewed_rectangle_inventory(authority.provider)
    approved_cameras = sorted(authority.historical_context.cameras,
                              key=lambda camera: camera.camera_id)
    if (
        inventory.source_route_proof_content_sha256 != content_sha256(proof)
        or inventory.source_sha256 != authority.source_sha256
        or inventory.human_decisions_sha256 != authority.human_decisions_sha256
        or inventory.certificate_content_sha256 != authority.certificate_content_sha256
        or inventory.semantic_review_content_sha256 != authority.semantic_review_content_sha256
        or inventory.scope_id != proof["scope_id"]
        or inventory.source_camera_calibration_content_sha256 != content_sha256([
            camera.model_dump(mode="json") for camera in approved_cameras
        ])
        or inventory.max_speed_m_s != authority.approved_input_lock["timing"]["max_speed_m_s"]
        or run.frozen_config_sha256 != inventory.frozen_config_sha256
        or run.human_decisions_sha256 != authority.human_decisions_sha256
        or run.certificate_content_sha256 != authority.certificate_content_sha256
        or run.semantic_review_content_sha256 != authority.semantic_review_content_sha256
    ):
        raise ValueError("reviewed metrics source/receipt/frozen-config binding differs")
    ratio = authority.provider.contract.scale.metres_per_blender_unit
    physical = authority.certificate.physical_certificate
    start, end = inventory.start_observation, inventory.end_observation
    if (
        inventory.floor_id != physical.floor_id
        or start.camera_id not in {camera.camera_id for camera in approved_cameras}
        or end.camera_id not in {camera.camera_id for camera in approved_cameras}
        or any(point.floor_id != inventory.floor_id or point.zone_id != inventory.zone_id
               for point in (start.projected_path[-1], end.projected_path[0]))
        or run.event.observation_ids != (start.observation_id, end.observation_id)
        or run.event.target_id != start.target_id
        or run.event.time_range != (start.end_time, end.start_time)
        or run.event.candidates != run.timed_result.candidates
        or run.event.termination_reason != run.timed_result.termination_reason
    ):
        raise ValueError("independent reviewed metric endpoint floor/zone/identity differs")
    candidates = tuple(CandidateTrajectory.model_validate(candidate.model_dump())
                       for candidate in run.event.candidates)
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ValueError("candidate identities must remain distinct for reviewed metrics")
    eligible_emitted = False
    failures = []
    impossible = 0
    for candidate in candidates:
        reasons = []
        a, b = inventory.canonical_direct_polyline_m
        if (
            candidate.start_observation_id != start.observation_id
            or candidate.end_observation_id != end.observation_id
            or math.dist(candidate.polyline[0], a) > inventory.endpoint_tolerance_m
            or math.dist(candidate.polyline[-1], b) > inventory.endpoint_tolerance_m
        ):
            reasons.append("UNAUTHORIZED_OBSERVED_ENDPOINT_CAMERA_DIRECTION_OR_ANCHORS")
        native_points = tuple((point[0] / ratio, point[1] / ratio, point[2] / ratio)
                              for point in candidate.polyline)
        try:
            authority.provider.validate_polyline(native_points)
        except GeometryAuthorityError as error:
            reasons.extend(error.reasons)
        # A local camera handoff must be physically possible inside this approved
        # source scope during the exact observed GAP, independent of reported costs.
        length = math.fsum(math.dist(first, last)
                           for first, last in pairwise(candidate.polyline))
        if length / inventory.max_speed_m_s > inventory.gap_duration_s:
            reasons.append("SOURCE_LOCAL_HANDOFF_EXCEEDS_APPROVED_SPEED_TIME")
        if reasons:
            impossible += 1
            failures.append({"candidate_id": candidate.candidate_id, "reasons": reasons})
        elif inventory.eligible_feasible_route_classes and _canonical_direct(
            candidate.polyline, inventory,
        ):
            eligible_emitted = True
    denominator = inventory.eligible_feasible_route_classes
    count = len(candidates)
    return {
        "feasible_candidate_recall": int(eligible_emitted) / denominator if denominator else None,
        "feasible_candidate_recall_status": (
            "AVAILABLE_EXHAUSTIVE_DECLARED_SOURCE_CLASS"
            if denominator else "N/A_NO_FEASIBLE_ELIGIBLE_SOURCE_CLASS"
        ),
        "feasible_candidate_recall_numerator": int(eligible_emitted),
        "feasible_candidate_recall_denominator": denominator,
        "feasible_candidate_recall_eligibility": inventory.eligibility,
        "feasible_inventory_exhaustive_for_declared_eligibility": True,
        "source_route_inventory_proof_content_sha256": inventory.source_route_proof_content_sha256,
        "canonical_route_class_id": inventory.canonical_route_class_id,
        "all_geometric_curves_enumerated": False,
        "impossible_transition_rate": impossible / count if count else None,
        "impossible_transition_status": (
            "AVAILABLE_REVIEWED_DIRECTED_LOCAL_HANDOFFS"
            if count else "N/A_NO_EMITTED_CAMERA_HANDOFFS"
        ),
        "impossible_transition_count": impossible,
        "transition_count": count,
        "transition_population": "ONE_OBSERVED_ENDPOINT_CAMERA_HANDOFF_PER_DISTINCT_CANDIDATE",
        "transition_authority": "INDEPENDENT_SOURCE_BOUND_COMPLETE_SAME_FLOOR_LOCAL_HANDOFF",
        "directed_local_handoff_id": inventory.directed_local_handoff_id,
        "from_camera_id": start.camera_id, "to_camera_id": end.camera_id,
        "internal_camera_transition_sequence_available": False,
        "engine_corridor_or_topology_used_for_inventory": False,
        "approved_portal_or_cross_floor_transitions": 0,
        "transition_failures": failures,
        "metric_inventory_content_sha256": content_sha256(inventory.model_dump(mode="json")),
        "source_sha256": authority.source_sha256,
        "certificate_content_sha256": authority.certificate_content_sha256,
        "semantic_review_content_sha256": authority.semantic_review_content_sha256,
        "ground_truth_used_for_inventory": False,
        "travel_time_error_s": None,
        "travel_time_error_status": "N/A_REFERENCE_MOVING_TIME_DWELL_ANNOTATION_NOT_APPROVED",
    }
