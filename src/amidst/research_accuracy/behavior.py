"""Versioned visible behavior evidence without truth, identity stitching or intent.

The legacy bundle remains the transport schema. A separately hashed evidence
policy distinguishes this composer and explicit support markers distinguish
claims from unresolved candidates. Weak legacy triggers are retained, so the
evaluator can report unknowns and missed truth on the same population.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from itertools import pairwise
from typing import Annotated, Literal

from pydantic import Field

from amidst.domain.common import DomainModel, PositiveFinite
from amidst.engineering.association import (
    AssociationHypothesis,
    ConfiguredRegion,
    LocalRecordMap,
    ProjectedMeasurement,
    content_sha256,
)
from amidst.engineering.local_behavior import (
    BehaviorConfig,
    BehaviorCorner,
    BehaviorInference,
    BehaviorKind,
    BehaviorPortal,
    LocalBehaviorBundle,
    LocalBehaviorEvent,
    _angle,
    _chunks,
    _declared_only,
    _door_crossings,
    _event,
    _inside,
    _position,
    _signed_side,
    compose_local_behaviors,
)
from amidst.engineering.perception import LocalTrack

SupportState = Literal["SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES"]
SUPPORT_PREFIX = "V2_EVIDENCE_STATE:"


class BehaviorEvidencePolicy(DomainModel):
    """Development policy, not calibrated confidence or formal region authority."""

    composer_version: Literal["local-behavior-evidence-v2"] = "local-behavior-evidence-v2"
    side_min_samples: Annotated[int, Field(ge=2)] = 2
    portal_clearance_m: PositiveFinite = 0.15
    portal_context_window_s: PositiveFinite = 1.2
    corner_context_window_s: PositiveFinite = 2.4
    corner_min_arm_displacement_m: PositiveFinite = 0.5
    region_clearance_m: PositiveFinite = 0.15
    dwell_velocity_window_s: PositiveFinite = 0.8
    revisit_min_outside_clearance_m: PositiveFinite = 0.35
    reversal_min_arm_displacement_m: PositiveFinite = 0.5


def behavior_config_sha256(
    config: BehaviorConfig, policy: BehaviorEvidencePolicy | None = None,
) -> str:
    """Bind the unmodified configured geometry and this version's full policy."""
    policy = policy or BehaviorEvidencePolicy()
    _declared_only(config)
    _declared_only(policy)
    return content_sha256({"config": config.model_dump(mode="json"),
                           "policy": policy.model_dump(mode="json")})


def event_support_state(event: LocalBehaviorEvent) -> SupportState:
    """Read the explicit v2 contract; legacy visible events default to supported."""
    if event.evidence_state == "INFERRED_GAP":
        return "GAP_ALTERNATIVES"
    states = [value.removeprefix(SUPPORT_PREFIX) for value in event.supports
              if value.startswith(SUPPORT_PREFIX)]
    if len(states) > 1 or any(value not in ("SUPPORTED", "UNKNOWN") for value in states):
        raise ValueError("behavior evidence must contain one recognized support state")
    return "UNKNOWN" if states == ["UNKNOWN"] else "SUPPORTED"


def _distance_outside(row: ProjectedMeasurement, region: ConfiguredRegion) -> float:
    x, y, _ = _position(row)
    x0, y0, x1, y1 = region.bounds_xy_m
    return math.hypot(max(x0 - x, 0, x - x1), max(y0 - y, 0, y - y1))


def _exclusive(
    row: ProjectedMeasurement, region: ConfiguredRegion, other: ConfiguredRegion,
    margin: float,
) -> bool:
    # Shared rectangle boundaries/overlap cannot identify a distinct corner arm.
    return _inside(row, region) and _distance_outside(row, other) >= margin


def _portal_context(
    rows: tuple[ProjectedMeasurement, ...], portal: BehaviorPortal,
    config: BehaviorConfig, policy: BehaviorEvidencePolicy, start: int, end: int,
) -> tuple[int, int] | None:
    destination_sign = 1 if _signed_side(_position(rows[end])[:2], portal) > 0 else -1
    regions = {region.region_id: region for region in config.regions}
    before_region = regions[portal.outside_region_id if destination_sign == 1
                            else portal.inside_region_id]
    after_region = regions[portal.inside_region_id if destination_sign == 1
                           else portal.outside_region_id]
    left = [index for index in range(start + 1)
            if rows[start].timestamp - rows[index].timestamp <= policy.portal_context_window_s
            and _inside(rows[index], before_region)
            and _signed_side(_position(rows[index])[:2], portal) * destination_sign
            <= -policy.portal_clearance_m]
    right = [index for index in range(end, len(rows))
             if rows[index].timestamp - rows[end].timestamp <= policy.portal_context_window_s
             and _inside(rows[index], after_region)
             and _signed_side(_position(rows[index])[:2], portal) * destination_sign
             >= policy.portal_clearance_m]
    if min(len(left), len(right)) < policy.side_min_samples:
        return None
    lo, hi = left[-policy.side_min_samples], right[policy.side_min_samples - 1]
    # Side corroboration must be a sustained passage, not a one-frame side swap.
    sides = [_signed_side(_position(row)[:2], portal) * destination_sign
             for row in rows[lo:hi + 1]]
    if any(second < first - config.thresholds.portal_side_margin_m
           for first, second in pairwise(sides)):
        return None
    return lo, hi


def _corner_passages(
    rows: tuple[ProjectedMeasurement, ...], corner: BehaviorCorner,
    config: BehaviorConfig, policy: BehaviorEvidencePolicy,
) -> list[tuple[int, int, int, float]]:
    regions = {region.region_id: region for region in config.regions}
    first_arm = regions[corner.approach_region_id]
    second_arm = regions[corner.departure_region_id]
    near = regions[corner.near_region_id]
    result: list[tuple[int, int, int, float]] = []
    last_pivot = -math.inf
    for pivot, row in enumerate(rows):
        if not _inside(row, near) or row.timestamp - last_pivot < (
            config.thresholds.turn_refractory_s
        ):
            continue
        for source, destination in ((first_arm, second_arm), (second_arm, first_arm)):
            before = [index for index in range(pivot)
                      if row.timestamp - rows[index].timestamp <= policy.corner_context_window_s
                      and _exclusive(rows[index], source, destination, policy.region_clearance_m)]
            after = [index for index in range(pivot + 1, len(rows))
                     if rows[index].timestamp - row.timestamp <= policy.corner_context_window_s
                     and _exclusive(rows[index], destination, source, policy.region_clearance_m)]
            if min(len(before), len(after)) < policy.side_min_samples:
                continue
            start, end = before[-policy.side_min_samples], after[policy.side_min_samples - 1]
            a, b, c = _position(rows[start]), _position(row), _position(rows[end])
            angle = _angle(a, b, c)
            if (min(math.dist(a, b), math.dist(b, c)) < policy.corner_min_arm_displacement_m
                or not config.thresholds.turn_min_angle_deg <= angle <= (
                    config.thresholds.turn_max_angle_deg)):
                continue
            # Source and destination support must agree with the two net arms.
            incoming = (b[0] - a[0], b[1] - a[1])
            outgoing = (c[0] - b[0], c[1] - b[1])
            if any(sum((right - left) * direction for right, left, direction in zip(
                _position(rows[j + 1])[:2], _position(rows[j])[:2], incoming, strict=True)) < 0
                   for j in range(start, pivot)) or any(
                       sum((right - left) * direction for right, left, direction in zip(
                           _position(rows[j + 1])[:2], _position(rows[j])[:2], outgoing,
                           strict=True)) < 0 for j in range(pivot, end)):
                continue
            result.append((start, pivot, end, angle))
            last_pivot = row.timestamp
            break
    return result


def _dwell_windows(
    rows: tuple[ProjectedMeasurement, ...], config: BehaviorConfig,
    policy: BehaviorEvidencePolicy,
) -> list[tuple[int, int]]:
    """Use visible diameter and velocity over a finite window to reject pixel jitter."""
    threshold = config.thresholds

    def stationary(start: int, end: int) -> bool:
        positions = [_position(row) for row in rows[start:end + 1]]
        center = tuple(sum(point[axis] for point in positions) / len(positions)
                       for axis in range(3))
        if max(math.dist(point, center) for point in positions) > threshold.dwell_max_radius_m:
            return False
        velocities = []
        for left in range(start, end):
            right = next((index for index in range(left + 1, end + 1)
                          if rows[index].timestamp - rows[left].timestamp
                          >= policy.dwell_velocity_window_s), None)
            if right is not None:
                velocities.append(math.dist(_position(rows[left]), _position(rows[right])) /
                                  (rows[right].timestamp - rows[left].timestamp))
        return bool(velocities) and max(velocities) <= threshold.dwell_max_speed_m_s

    result: list[tuple[int, int]] = []
    start = 0
    while start < len(rows):
        minimum = next((end for end in range(start + 1, len(rows))
                        if rows[end].timestamp - rows[start].timestamp
                        >= threshold.dwell_min_duration_s), None)
        if minimum is None:
            break
        if not stationary(start, minimum):
            start += 1
            continue
        end = minimum
        while end + 1 < len(rows) and stationary(start, end + 1):
            end += 1
        result.append((start, end))
        start = end + 1
    return result


def _loiter_corroboration(
    rows: tuple[ProjectedMeasurement, ...], config: BehaviorConfig,
    policy: BehaviorEvidencePolicy,
) -> tuple[bool, tuple[str, ...]]:
    threshold = config.thresholds
    reversals: list[int] = []
    last_recovery_index = -1
    for pivot in range(1, len(rows) - 1):
        # Several neighboring pivots can describe one prolonged U-turn. A new
        # reversal needs a subsequent observed recovery leg, not another angle
        # computed against the same returning endpoint.
        if pivot <= last_recovery_index:
            continue
        before = [index for index in range(pivot)
                  if rows[pivot].timestamp - rows[index].timestamp
                  <= threshold.reversal_max_arm_duration_s
                  and math.dist(_position(rows[pivot]), _position(rows[index]))
                  >= policy.reversal_min_arm_displacement_m]
        after = [index for index in range(pivot + 1, len(rows))
                 if rows[index].timestamp - rows[pivot].timestamp
                 <= threshold.reversal_max_arm_duration_s
                 and math.dist(_position(rows[pivot]), _position(rows[index]))
                 >= policy.reversal_min_arm_displacement_m]
        if not before or not after or reversals and (
            rows[pivot].timestamp - rows[reversals[-1]].timestamp
            < threshold.reversal_min_separation_s
        ):
            continue
        if _angle(_position(rows[before[-1]]), _position(rows[pivot]),
                  _position(rows[after[0]])) >= threshold.reversal_min_angle_deg:
            reversals.append(pivot)
            last_recovery_index = after[0]
    visits = 0
    for region in config.regions:
        if region.region_id not in config.revisit_region_ids:
            continue
        entry: int | None = None
        outside: list[int] = []
        for index, row in enumerate(rows):
            if _inside(row, region):
                if entry is not None and outside:
                    first, last = outside[0], outside[-1]
                    travel = sum(math.dist(_position(a), _position(b))
                                 for a, b in pairwise(rows[entry:index + 1]))
                    if (row.timestamp - rows[entry].timestamp >= threshold.revisit_min_elapsed_s
                        and rows[last].timestamp - rows[first].timestamp >= (
                            threshold.revisit_min_outside_duration_s)
                        and travel >= threshold.revisit_min_travel_m
                        and max(_distance_outside(rows[j], region) for j in outside)
                        >= policy.revisit_min_outside_clearance_m
                        and len(outside) >= policy.side_min_samples):
                        visits += 1
                    entry = index
                    outside = []
                elif entry is None:
                    entry = index
            elif entry is not None:
                outside.append(index)
    return (len(reversals) >= threshold.loiter_min_reversals
            or visits >= threshold.loiter_min_revisits), (
                f"V2_NET_DISPLACEMENT_REVERSALS:{len(reversals)}",
                f"V2_CLEAR_REGION_REVISITS:{visits}",
                "LOCAL_VISIBLE_MOTION_ONLY_NO_INTENT_INFERENCE",
            )


def _rebind(
    event: LocalBehaviorEvent, config_sha: str, config_version: str,
    state: SupportState, *, supports: tuple[str, ...] = (), conflicts: tuple[str, ...] = (),
    alternatives: tuple[str, ...] = (),
) -> LocalBehaviorEvent:
    event_id = "local-behavior-v2:" + content_sha256([config_sha, event.event_id, state])
    return LocalBehaviorEvent.model_validate(event.model_dump() | {
        "event_id": event_id, "config_sha256": config_sha, "config_version": config_version,
        "detail_ref": event_id,
        "supports": (*event.supports, f"{SUPPORT_PREFIX}{state}", *supports),
        "conflicts": tuple(dict.fromkeys((*event.conflicts, *conflicts))),
        "alternatives": tuple(dict.fromkeys((*event.alternatives, *alternatives))),
        "uncertainty": (event.uncertainty + " V2 local evidence is " + state + ". "
                        + ("This candidate is retained without a behavioral claim."
                           if state == "UNKNOWN" else "Scores are not probabilities.")),
    })


def compose_behaviors_v2(
    inference: BehaviorInference, config: BehaviorConfig, *, tracks: tuple[LocalTrack, ...] = (),
    policy: BehaviorEvidencePolicy | None = None,
) -> LocalBehaviorBundle:
    """Compose reproducible visible claims and explicit unresolved candidates.

    All inputs are typed visible projections, source track states and configured
    geometry. No file, recipe, GT actor, global identity or hidden route is read.
    """
    policy = policy or BehaviorEvidencePolicy()
    _declared_only(policy)
    policy = BehaviorEvidencePolicy.model_validate(policy.model_dump())
    baseline = compose_local_behaviors(inference, config, tracks=tracks)
    config_sha = behavior_config_sha256(config, policy)
    version = f"{config.config_version}:{policy.composer_version}"
    pixels = {row.observation_id: row for row in inference.projected_measurements}
    associations: dict[str, list[AssociationHypothesis]] = defaultdict(list)
    baseline_by_segment: dict[str, list[LocalBehaviorEvent]] = defaultdict(list)
    for association in inference.association_hypotheses:
        for segment_id in association.segment_ids:
            associations[segment_id].append(association)
    for event in baseline.events:
        if event.evidence_state == "PROJECTED":
            baseline_by_segment[event.segment_ids[0]].append(event)
    events: list[LocalBehaviorEvent] = [
        _rebind(event, config_sha, version, "GAP_ALTERNATIVES")
        for event in baseline.events if event.evidence_state == "INFERRED_GAP"]
    regions = {region.region_id: region for region in config.regions}
    for mapping in inference.local_record_maps:
        selected = tuple(pixels[key] for key in mapping.original_pixel_observation_ids)
        supported: list[LocalBehaviorEvent] = []
        for rows in _chunks(selected, config.thresholds.max_visible_sample_gap_s):
            def make(
                kind: BehaviorKind, start: int, end: int, anchors: Sequence[int],
                supports: tuple[str, ...], region_ids: tuple[str, ...] = (),
                portal_ids: tuple[str, ...] = (), corner_ids: tuple[str, ...] = (),
                mapping: LocalRecordMap = mapping,
                rows: tuple[ProjectedMeasurement, ...] = rows,
            ) -> LocalBehaviorEvent:
                original = _event(
                    inference=inference, config=config, config_sha=config_sha, mapping=mapping,
                    associations=tuple(associations[mapping.segment_id]), rows=rows,
                    kind=kind, start=start, end=end, anchors=anchors, supports=supports,
                    region_ids=region_ids, portal_ids=portal_ids, corner_ids=corner_ids)
                return _rebind(original, config_sha, version, "SUPPORTED")

            for portal in config.portals:
                for kind, start, end in _door_crossings(rows, portal, regions, config.thresholds):
                    context = _portal_context(rows, portal, config, policy, start, end)
                    if context is not None:
                        lo, hi = context
                        supported.append(make(
                            kind, lo, hi, (lo, start, end, hi),
                            ("V2_REPEATED_CLEAR_PORTAL_SIDE_SAMPLES",
                             "CONTINUOUS_FINITE_PORTAL_AND_SIGNED_DIRECTION"),
                            (portal.outside_region_id, portal.inside_region_id),
                            (portal.portal_id,)))
            for corner in config.corners:
                for start, pivot, end, angle in _corner_passages(rows, corner, config, policy):
                    supported.append(make(
                        "TURN_CORNER", start, end, (start, pivot, end),
                        ("V2_REPEATED_EXCLUSIVE_CORNER_ARM_SAMPLES",
                         f"V2_NET_DIRECTION_CHANGE_DEG:{angle:.3f}"),
                        (corner.approach_region_id, corner.departure_region_id),
                        corner_ids=(corner.corner_id,)))
            for start, end in _dwell_windows(rows, config, policy):
                supported.append(make(
                    "DWELL", start, end, (start, (start + end) // 2, end),
                    ("V2_CONTINUOUS_VISIBLE_RADIUS_AND_WINDOW_VELOCITY",
                     f"VISIBLE_DURATION_S:{rows[end].timestamp - rows[start].timestamp:.3f}"),
                    tuple(dict.fromkeys(region for row in rows[start:end + 1]
                                        for region in row.region_ids))))
        events.extend(supported)
        for original in baseline_by_segment[mapping.segment_id]:
            if original.kind == "LOST_NEAR_CORNER":
                events.append(_rebind(original, config_sha, version, "UNKNOWN", alternatives=(
                    "THROUGH_TURN_WITHOUT_VISIBLE_PROOF", "CORNER_TURNBACK")))
                continue
            if original.kind == "POSSIBLE_LOITERING":
                rows = tuple(pixels[point.observation_id] for point in original.projected_path)
                confirmed, evidence = _loiter_corroboration(rows, config, policy)
                events.append(_rebind(
                    original, config_sha, version, "SUPPORTED" if confirmed else "UNKNOWN",
                    supports=evidence,
                    conflicts=() if confirmed else ("NO_CLEAR_SEPARATED_REVISIT_OR_NET_REVERSAL",),
                    alternatives=("LOCAL_REVISIT", "REVERSAL", "PROJECTION_OR_LOCAL_ID_ERROR")))
                continue
            matches = [event for event in supported
                       if event.kind == original.kind and event.portal_ids == original.portal_ids
                       and event.corner_ids == original.corner_ids
                       and max(event.time_range[0], original.time_range[0])
                       <= min(event.time_range[1], original.time_range[1])]
            if not matches:
                reason = {"ENTER_DOOR": "INSUFFICIENT_REPEATED_CLEAR_DOOR_SIDE_EVIDENCE",
                          "EXIT_DOOR": "INSUFFICIENT_REPEATED_CLEAR_DOOR_SIDE_EVIDENCE",
                          "TURN_CORNER": "INSUFFICIENT_EXCLUSIVE_ARM_AND_NET_TURN_EVIDENCE",
                          "DWELL": "INSUFFICIENT_CONTINUOUS_RADIUS_AND_WINDOW_VELOCITY"}
                alternatives = {"TURN_CORNER": ("CORNER_TURNBACK", "STRAIGHT_MOTION_OR_JITTER"),
                                "DWELL": ("SLOW_TRANSIT", "PROJECTION_OR_LOCAL_ID_ERROR")}
                events.append(_rebind(
                    original, config_sha, version, "UNKNOWN",
                    conflicts=(reason[original.kind],),
                    alternatives=alternatives.get(original.kind, (
                        "DOOR_APPROACH_OR_RETREAT", "PROJECTION_OR_LOCAL_ID_ERROR"))))
    unique = {event.event_id: event for event in events}
    return LocalBehaviorBundle.model_validate(baseline.model_dump() | {
        "config_sha256": config_sha,
        "events": tuple(sorted(unique.values(), key=lambda event: (
            event.time_range[0], event.time_range[1], event.event_id))),
        "limitations": (*baseline.limitations,
                        "V2_EVIDENCE_STATE:UNKNOWN retains a candidate without asserting its kind.",
                        "Legacy rule/schema literals are transport; v2 policy hashes bind logic.",
                        "Evaluation must count unknown candidates and all unmatched truth events."),
    })
