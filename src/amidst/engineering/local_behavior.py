"""Visible local behavior composition over pixel projections and canonical gaps.

This extension is a configured synthetic experiment. It neither confirms global
identity nor changes frozen gap/trajectory semantics. Import builds reference
maps once; composition follows each original segment rather than joining tracks
through an association or inspecting a truth/recipe sidecar.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Sequence
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, FiniteFloat, model_validator

from amidst.domain.common import DomainModel, PositiveFinite, Timestamp, Vec3
from amidst.domain.trajectory import CandidateTrajectory, TrajectoryHypothesis
from amidst.engineering.association import (
    AssociationHypothesis,
    ConfiguredRegion,
    InferenceBundle,
    InferenceScope,
    LocalRecordMap,
    ProjectedMeasurement,
    content_sha256,
)
from amidst.engineering.local_association import InferenceBundle as LocalInferenceBundle
from amidst.engineering.perception import LocalTrack

RULE_VERSION: Literal["local-behavior-rules-v1"] = "local-behavior-rules-v1"
BehaviorInference = InferenceBundle | LocalInferenceBundle
BehaviorKind = Literal[
    "ENTER_DOOR", "EXIT_DOOR", "TURN_CORNER", "DWELL", "POSSIBLE_LOITERING",
    "LOST_NEAR_CORNER", "INFERRED_GAP_ALTERNATIVES",
]
XY = tuple[FiniteFloat, FiniteFloat]
NonNegativeFinite = Annotated[FiniteFloat, Field(ge=0)]


class BehaviorPortal(DomainModel):
    portal_id: str = Field(min_length=1)
    outside_region_id: str = Field(min_length=1)
    inside_region_id: str = Field(min_length=1)
    line_xy_m: tuple[XY, XY]
    enter_normal_xy: XY

    @model_validator(mode="after")
    def oriented_portal(self) -> Self:
        a, b = self.line_xy_m
        tangent = (b[0] - a[0], b[1] - a[1])
        normal_length = math.hypot(*self.enter_normal_xy)
        tangent_length = math.hypot(*tangent)
        if not tangent_length or not math.isclose(normal_length, 1.0, abs_tol=1e-9):
            raise ValueError("portal needs a finite segment and a unit entering normal")
        if abs(sum(x * y for x, y in zip(tangent, self.enter_normal_xy, strict=True))) > (
            1e-9 * tangent_length
        ):
            raise ValueError("entering normal must be perpendicular to the portal")
        if self.outside_region_id == self.inside_region_id:
            raise ValueError("door crossing requires two distinct regions")
        return self


class BehaviorCorner(DomainModel):
    corner_id: str = Field(min_length=1)
    approach_region_id: str = Field(min_length=1)
    departure_region_id: str = Field(min_length=1)
    near_region_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def two_regions(self) -> Self:
        if self.approach_region_id == self.departure_region_id:
            raise ValueError("visible corner passage requires two distinct arm regions")
        return self


class BehaviorThresholds(DomainModel):
    """Fixed development rules; values and scores are not calibrated probabilities."""

    max_visible_sample_gap_s: PositiveFinite = 0.6
    portal_side_margin_m: NonNegativeFinite = 0.02
    portal_min_direction_cosine: Annotated[FiniteFloat, Field(gt=0, le=1)] = 0.5
    turn_min_displacement_m: PositiveFinite = 0.04
    turn_min_angle_deg: Annotated[FiniteFloat, Field(gt=0, lt=180)] = 50.0
    turn_max_angle_deg: Annotated[FiniteFloat, Field(gt=0, lt=180)] = 140.0
    turn_refractory_s: PositiveFinite = 1.0
    dwell_min_duration_s: PositiveFinite = 1.2
    dwell_max_radius_m: PositiveFinite = 0.3
    dwell_max_speed_m_s: PositiveFinite = 0.25
    reversal_min_displacement_m: PositiveFinite = 0.4
    reversal_min_angle_deg: Annotated[FiniteFloat, Field(gt=90, le=180)] = 150.0
    reversal_max_arm_duration_s: PositiveFinite = 2.0
    reversal_min_separation_s: PositiveFinite = 1.0
    loiter_min_reversals: Annotated[int, Field(ge=2)] = 2
    loiter_min_revisits: Annotated[int, Field(ge=1)] = 1
    revisit_min_elapsed_s: PositiveFinite = 2.0
    revisit_min_outside_duration_s: PositiveFinite = 0.6
    revisit_min_travel_m: PositiveFinite = 1.0

    @model_validator(mode="after")
    def angle_interval(self) -> Self:
        if self.turn_max_angle_deg <= self.turn_min_angle_deg:
            raise ValueError("corner angle interval must have positive extent")
        return self


class BehaviorConfig(DomainModel):
    schema_version: Literal["simulation.local-behavior-config.v1"] = (
        "simulation.local-behavior-config.v1"
    )
    scope: InferenceScope
    config_version: str = Field(min_length=1)
    regions: tuple[ConfiguredRegion, ...]
    portals: tuple[BehaviorPortal, ...] = ()
    corners: tuple[BehaviorCorner, ...] = ()
    revisit_region_ids: tuple[str, ...] = ()
    thresholds: BehaviorThresholds = BehaviorThresholds()
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["SYNTHETIC_CONFIG"] = "SYNTHETIC_CONFIG"
    units: Literal["METRES"] = "METRES"
    rule_version: Literal["local-behavior-rules-v1"] = RULE_VERSION

    @model_validator(mode="after")
    def registered_rules(self) -> Self:
        regions = {region.region_id: region for region in self.regions}
        if len(regions) != len(self.regions):
            raise ValueError("behavior region identities must be unique")
        if len({item.portal_id for item in self.portals}) != len(self.portals) or len(
            {item.corner_id for item in self.corners}
        ) != len(self.corners):
            raise ValueError("behavior portal/corner identities must be unique")
        if len(set(self.revisit_region_ids)) != len(self.revisit_region_ids):
            raise ValueError("revisit region identities must be unique")
        refs = list(self.revisit_region_ids)
        for portal in self.portals:
            refs.extend((portal.outside_region_id, portal.inside_region_id))
            outside, inside = regions.get(portal.outside_region_id), regions.get(
                portal.inside_region_id
            )
            if outside is not None and inside is not None:
                if outside.floor_id != inside.floor_id:
                    raise ValueError("portal sides must share one configured floor")
                for region, expected_sign in ((outside, -1), (inside, 1)):
                    x0, y0, x1, y1 = region.bounds_xy_m
                    center = ((x0 + x1) / 2, (y0 + y1) / 2)
                    if _signed_side(center, portal) * expected_sign <= 0:
                        raise ValueError("portal region centers must agree with entering normal")
        for corner in self.corners:
            refs.extend((corner.approach_region_id, corner.departure_region_id,
                         corner.near_region_id))
        if any(ref not in regions for ref in refs):
            raise ValueError("behavior rules require explicitly registered regions")
        return self


class BehaviorSourceFrame(DomainModel):
    frame_ref: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    camera_id: str = Field(min_length=1)
    timestamp: Timestamp
    evidence_state: Literal["PROJECTED"] = "PROJECTED"


class BehaviorProjectedPoint(DomainModel):
    observation_id: str
    local_track_id: str
    camera_id: str
    timestamp: Timestamp
    world_position: Vec3
    uncertainty_m: PositiveFinite
    evidence_state: Literal["PROJECTED"] = "PROJECTED"


class BehaviorAssociationState(DomainModel):
    hypothesis_id: str
    kind: str
    status: Literal["PROVISIONAL", "HOLD", "INCOMPATIBLE", "UNMATCHED"]
    reason: str


class LocalBehaviorEvent(DomainModel):
    event_id: str
    kind: BehaviorKind
    scope: InferenceScope
    time_range: tuple[Timestamp, Timestamp]
    local_track_ids: tuple[str, ...]
    segment_ids: tuple[str, ...]
    association_refs: tuple[str, ...]
    association_states: tuple[BehaviorAssociationState, ...]
    source_frames: tuple[BehaviorSourceFrame, ...] = Field(min_length=1, max_length=5)
    missing_evidence: tuple[str, ...] = ()
    region_ids: tuple[str, ...] = ()
    portal_ids: tuple[str, ...] = ()
    corner_ids: tuple[str, ...] = ()
    rule_version: Literal["local-behavior-rules-v1"] = RULE_VERSION
    config_version: str
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    supports: tuple[str, ...]
    conflicts: tuple[str, ...] = ()
    alternatives: tuple[str, ...] = ()
    uncertainty: str
    evidence_state: Literal["PROJECTED", "INFERRED_GAP"]
    projected_path: tuple[BehaviorProjectedPoint, ...]
    candidates: tuple[CandidateTrajectory, ...] = ()
    trajectories: tuple[TrajectoryHypothesis, ...] = ()
    canonical_event_id: str | None = None
    termination_reason: str | None = None
    complete: bool | None = None
    detail_ref: str
    replay_ref: str | None = None
    origin: Literal["SYNTHETIC"] = "SYNTHETIC"
    authority: Literal["CONFIGURED_PIXEL_BEHAVIOR_HYPOTHESIS"] = (
        "CONFIGURED_PIXEL_BEHAVIOR_HYPOTHESIS"
    )

    @model_validator(mode="after")
    def consistent_composition(self) -> Self:
        if self.time_range[1] < self.time_range[0]:
            raise ValueError("behavior event time range must be ordered")
        if len({frame.frame_ref for frame in self.source_frames}) != len(self.source_frames):
            raise ValueError("event cards must not duplicate actual frame references")
        if tuple(item.hypothesis_id for item in self.association_states) != self.association_refs:
            raise ValueError("association references must preserve their original states")
        gap = self.kind == "INFERRED_GAP_ALTERNATIVES"
        if gap != (self.evidence_state == "INFERRED_GAP"):
            raise ValueError("only a canonical blind-gap composition has inferred evidence")
        if gap and self.canonical_event_id is None:
            raise ValueError("blind-gap alternatives require their canonical event")
        if not gap and (self.candidates or self.trajectories or self.canonical_event_id):
            raise ValueError("visible behavior must not create gap trajectories")
        if self.kind in ("ENTER_DOOR", "EXIT_DOOR") and (
            not self.portal_ids or len(self.region_ids) < 2
        ):
            raise ValueError("door crossing must retain its oriented portal and both regions")
        if self.kind in ("TURN_CORNER", "LOST_NEAR_CORNER") and not self.corner_ids:
            raise ValueError("corner behavior requires its configured corner reference")
        return self


class LocalBehaviorBundle(DomainModel):
    schema_version: Literal["simulation.local-behavior.v1"] = "simulation.local-behavior.v1"
    scope: InferenceScope
    inference_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    config_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    input_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    producer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    track_state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    events: tuple[LocalBehaviorEvent, ...]
    measurements_indexed: int = Field(ge=0)
    segments_visited: int = Field(ge=0)
    limitations: tuple[str, ...] = (
        "Configured synthetic regions and pixel projections are uncertain, not school authority.",
        "Events follow original visible segments; provisional association never confirms identity.",
        "Possible loitering describes local motion/revisit evidence without inferring intent.",
        "Missing images or projections never supply a door/corner crossing or stationary interval.",
        "Gap routes and timings retain canonical order; they are alternatives, not photographs.",
    )

    @model_validator(mode="after")
    def source_bound_events(self) -> Self:
        if len({event.event_id for event in self.events}) != len(self.events):
            raise ValueError("behavior event identities must be unique")
        if any(event.scope != self.scope or event.config_sha256 != self.config_sha256
               for event in self.events):
            raise ValueError("behavior events must retain one source/config scope")
        return self


def _declared_only(value: object) -> None:
    # Check unchecked copies before a serializer can silently omit undeclared data.
    if isinstance(value, BaseModel):
        fields = set(type(value).model_fields)
        if set(value.__dict__) - fields or value.model_extra:
            raise ValueError("behavior inputs must not contain undeclared or truth fields")
        for name in fields:
            _declared_only(getattr(value, name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            _declared_only(item)


def _signed_side(point: XY, portal: BehaviorPortal) -> float:
    a = portal.line_xy_m[0]
    return sum((point[i] - a[i]) * portal.enter_normal_xy[i] for i in (0, 1))


def _inside(item: ProjectedMeasurement, region: ConfiguredRegion) -> bool:
    if item.status != "PROJECTED" or item.point is None:
        return False
    if item.point.floor_id != region.floor_id:
        return False
    x, y, _ = item.point.world_position
    x0, y0, x1, y1 = region.bounds_xy_m
    return x0 <= x <= x1 and y0 <= y <= y1


def _position(item: ProjectedMeasurement) -> Vec3:
    assert item.point is not None and item.status == "PROJECTED"
    return item.point.world_position


def _angle(a: Vec3, b: Vec3, c: Vec3) -> float:
    before, after = (b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1])
    denominator = math.hypot(*before) * math.hypot(*after)
    if denominator == 0:
        return 0.0
    cosine = sum(x * y for x, y in zip(before, after, strict=True)) / denominator
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _chunks(rows: tuple[ProjectedMeasurement, ...], gap_s: float
            ) -> tuple[tuple[ProjectedMeasurement, ...], ...]:
    chunks: list[list[ProjectedMeasurement]] = []
    broken = True
    for row in rows:
        if row.status != "PROJECTED" or row.point is None:
            broken = True
            continue
        if broken or row.timestamp - chunks[-1][-1].timestamp > gap_s:
            chunks.append([])
        chunks[-1].append(row)
        broken = False
    return tuple(tuple(chunk) for chunk in chunks)


def _frames(rows: Sequence[ProjectedMeasurement], anchors: Sequence[int]
            ) -> tuple[BehaviorSourceFrame, ...]:
    """At most five actual measurements, retaining trigger plus before/after context."""
    unique = sorted({max(0, min(index, len(rows) - 1)) for index in anchors})
    selected = list(unique)
    if len(selected) > 5:
        selected = [selected[round(index * (len(selected) - 1) / 4)] for index in range(5)]
    for index in sorted({i for anchor in unique for i in (anchor - 1, anchor + 1)
                         if 0 <= i < len(rows)}):
        if len(selected) >= 5:
            break
        if index not in selected:
            selected.append(index)
    refs: set[str] = set()
    result: list[BehaviorSourceFrame] = []
    for index in sorted(selected):
        row = rows[index]
        if row.frame_ref in refs:
            continue
        refs.add(row.frame_ref)
        result.append(BehaviorSourceFrame(frame_ref=row.frame_ref,
                                         observation_id=row.observation_id,
                                         camera_id=row.camera_id, timestamp=row.timestamp))
    return tuple(result)


def _event(*, inference: BehaviorInference, config: BehaviorConfig, config_sha: str,
           mapping: LocalRecordMap, associations: tuple[AssociationHypothesis, ...],
           rows: tuple[ProjectedMeasurement, ...], kind: BehaviorKind, start: int, end: int,
           anchors: Sequence[int], supports: tuple[str, ...], region_ids: tuple[str, ...] = (),
           portal_ids: tuple[str, ...] = (), corner_ids: tuple[str, ...] = (),
           conflicts: tuple[str, ...] = (), alternatives: tuple[str, ...] = (),
           ) -> LocalBehaviorEvent:
    frames = _frames(rows, anchors)
    digest = content_sha256([config_sha, mapping.segment_id, kind, rows[start].observation_id,
                             rows[end].observation_id, region_ids, portal_ids, corner_ids])
    event_id = f"local-behavior:{digest}"
    refs = tuple(item.hypothesis_id for item in associations)
    return LocalBehaviorEvent(
        event_id=event_id, kind=kind, scope=inference.scope,
        time_range=(rows[start].timestamp, rows[end].timestamp),
        local_track_ids=(mapping.local_track_id,), segment_ids=(mapping.segment_id,),
        association_refs=refs,
        association_states=tuple(BehaviorAssociationState(
            hypothesis_id=item.hypothesis_id, kind=item.kind, status=item.status,
            reason=item.reason) for item in associations),
        source_frames=frames,
        missing_evidence=("FEWER_THAN_THREE_AVAILABLE_VISIBLE_FRAMES",) if len(frames) < 3 else (),
        region_ids=region_ids, portal_ids=portal_ids, corner_ids=corner_ids,
        config_version=config.config_version, config_sha256=config_sha, supports=supports,
        conflicts=conflicts + tuple(
            f"ASSOCIATION_{item.status}:{item.hypothesis_id}" for item in associations
            if item.status in ("HOLD", "INCOMPATIBLE")),
        alternatives=tuple(dict.fromkeys((*alternatives, *refs))),
        uncertainty=("Visible pixel-derived projection supports the configured local rule; "
                     "projection error, partial components and local ID switches remain possible. "
                     "No behavioral probability, global identity or human intent is assigned."),
        evidence_state="PROJECTED",
        projected_path=tuple(BehaviorProjectedPoint(
            observation_id=row.observation_id, local_track_id=row.local_track_id,
            camera_id=row.camera_id, timestamp=row.timestamp, world_position=_position(row),
            uncertainty_m=row.uncertainty_m) for row in rows[start:end + 1]),
        detail_ref=event_id,
    )


def _door_crossings(rows: tuple[ProjectedMeasurement, ...], portal: BehaviorPortal,
                    regions: dict[str, ConfiguredRegion], thresholds: BehaviorThresholds,
                    ) -> list[tuple[BehaviorKind, int, int]]:
    crossings: list[tuple[BehaviorKind, int, int]] = []
    previous_index: int | None = None
    previous_side = 0
    for index, row in enumerate(rows):
        point = _position(row)
        side_distance = _signed_side((point[0], point[1]), portal)
        side = (-1 if side_distance < -thresholds.portal_side_margin_m else
                1 if side_distance > thresholds.portal_side_margin_m else 0)
        if side == 0:
            continue
        if previous_index is not None and previous_side != side:
            first, second = rows[previous_index], row
            before, after = _position(first), point
            displacement = math.dist(before, after)
            directed = abs(_signed_side((after[0], after[1]), portal)
                           - _signed_side((before[0], before[1]), portal))
            fraction = -_signed_side((before[0], before[1]), portal) / (
                _signed_side((after[0], after[1]), portal)
                - _signed_side((before[0], before[1]), portal)
            )
            intersection = (before[0] + fraction * (after[0] - before[0]),
                            before[1] + fraction * (after[1] - before[1]))
            a, b = portal.line_xy_m
            tangent = (b[0] - a[0], b[1] - a[1])
            along = sum((intersection[i] - a[i]) * tangent[i] for i in (0, 1)) / (
                math.hypot(*tangent) ** 2
            )
            source = regions[portal.outside_region_id if side == 1 else portal.inside_region_id]
            destination = regions[
                portal.inside_region_id if side == 1 else portal.outside_region_id]
            # Intermediate boundary-margin samples must continue in the crossing direction.
            monotone = all(
                (_signed_side((_position(right)[0], _position(right)[1]), portal)
                 - _signed_side((_position(left)[0], _position(left)[1]), portal)) * side >= 0
                for left, right in pairwise(rows[previous_index:index + 1])
            )
            if (0 <= along <= 1 and _inside(first, source) and _inside(second, destination)
                and displacement > 0 and directed / displacement >= (
                    thresholds.portal_min_direction_cosine) and monotone):
                crossings.append(("ENTER_DOOR" if side == 1 else "EXIT_DOOR",
                                  previous_index, index))
        previous_index, previous_side = index, side
    return crossings


def _dwell_intervals(rows: tuple[ProjectedMeasurement, ...], thresholds: BehaviorThresholds
                     ) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    start = 0
    for end in range(1, len(rows) + 1):
        stationary = False
        if end < len(rows):
            duration = rows[end].timestamp - rows[end - 1].timestamp
            stationary = (
                math.dist(_position(rows[start]), _position(rows[end])) <= (
                    thresholds.dwell_max_radius_m)
                and math.dist(_position(rows[end - 1]), _position(rows[end])) / duration <= (
                    thresholds.dwell_max_speed_m_s)
            )
        if not stationary:
            if rows[end - 1].timestamp - rows[start].timestamp >= thresholds.dwell_min_duration_s:
                result.append((start, end - 1))
            start = end
    return result


def _loiter_pattern(rows: tuple[ProjectedMeasurement, ...], config: BehaviorConfig,
                    regions: dict[str, ConfiguredRegion],
                    ) -> tuple[list[int], tuple[str, ...]]:
    thresholds = config.thresholds
    arc = [0.0]
    for first, second in pairwise(rows):
        arc.append(arc[-1] + math.dist(_position(first), _position(second)))
    reversal_anchors: list[int] = []
    last_reversal = -math.inf
    for index, row in enumerate(rows):
        left = bisect_right(arc, arc[index] - thresholds.reversal_min_displacement_m) - 1
        right = bisect_left(arc, arc[index] + thresholds.reversal_min_displacement_m)
        if left < 0 or right >= len(rows):
            continue
        if (row.timestamp - rows[left].timestamp > thresholds.reversal_max_arm_duration_s
            or rows[right].timestamp - row.timestamp > thresholds.reversal_max_arm_duration_s
            or row.timestamp - last_reversal < thresholds.reversal_min_separation_s):
            continue
        a, b, c = _position(rows[left]), _position(row), _position(rows[right])
        if (min(math.dist(a, b), math.dist(b, c)) >= thresholds.reversal_min_displacement_m
            and _angle(a, b, c) >= thresholds.reversal_min_angle_deg):
            reversal_anchors.append(index)
            last_reversal = row.timestamp
    revisit_anchors: list[int] = []
    revisit_regions: list[str] = []
    for region_id in config.revisit_region_ids:
        region = regions[region_id]
        previous_entry: int | None = None
        exit_index: int | None = None
        was_inside = False
        for index, row in enumerate(rows):
            inside = _inside(row, region)
            if inside and not was_inside:
                if (previous_entry is not None and exit_index is not None
                    and row.timestamp - rows[previous_entry].timestamp >= (
                        thresholds.revisit_min_elapsed_s)
                    and row.timestamp - rows[exit_index].timestamp >= (
                        thresholds.revisit_min_outside_duration_s)
                    and arc[index] - arc[previous_entry] >= thresholds.revisit_min_travel_m):
                    revisit_anchors.extend((previous_entry, exit_index, index))
                    revisit_regions.append(region_id)
                previous_entry, exit_index = index, None
            elif was_inside and not inside:
                exit_index = index
            was_inside = inside
    qualifies = (len(reversal_anchors) >= thresholds.loiter_min_reversals
                 or len(revisit_regions) >= thresholds.loiter_min_revisits)
    if not qualifies:
        return [], ()
    supports = (f"VISIBLE_REVERSALS:{len(reversal_anchors)}",
                f"MEASURED_REGION_REVISITS:{len(revisit_regions)}",
                "OPERATIONAL_LOCAL_MOTION_PATTERN_NO_INTENT_INFERENCE")
    return sorted(set((*reversal_anchors, *revisit_anchors))), supports


def compose_local_behaviors(inference: BehaviorInference, config: BehaviorConfig, *,
                            tracks: tuple[LocalTrack, ...] = (),
                            ) -> LocalBehaviorBundle:
    """Build local events once from source-bound inferred evidence, without a GT input.

    Optional producer track states distinguish lost visibility from sequence end.
    They do not supply missing pixels, recovered identity or inferred crossings.
    """
    _declared_only(inference)
    _declared_only(config)
    _declared_only(tracks)
    config = BehaviorConfig.model_validate(config.model_dump())
    if inference.scope != config.scope:
        raise ValueError("behavior configuration must match exact inference scope")
    if any(track.model_id != config.scope.model_id or track.run_id != config.scope.run_id
           for track in tracks):
        raise ValueError("behavior track states cannot cross model/run scope")
    track_states = {track.local_track_id: track for track in tracks}
    if len(track_states) != len(tracks):
        raise ValueError("behavior track states must have unique local IDs")
    pixels = {row.observation_id: row for row in inference.projected_measurements}
    pixels_by_track: dict[str, list[ProjectedMeasurement]] = defaultdict(list)
    for row in inference.projected_measurements:
        pixels_by_track[row.local_track_id].append(row)
    for track in tracks:
        expected = sorted(pixels_by_track.get(track.local_track_id, ()),
                          key=lambda row: row.timestamp)
        if (not expected or track.observation_ids != tuple(row.observation_id for row in expected)
            or track.timestamps != tuple(row.timestamp for row in expected)
            or any(row.camera_id != track.camera_id for row in expected)):
            raise ValueError("behavior track state must retain exact pixel evidence and camera")
    regions = {region.region_id: region for region in config.regions}
    associations: dict[str, list[AssociationHypothesis]] = defaultdict(list)
    for association in inference.association_hypotheses:
        for segment_id in association.segment_ids:
            associations[segment_id].append(association)
    config_sha = content_sha256(config)
    events: list[LocalBehaviorEvent] = []
    threshold = config.thresholds
    segments = {mapping.segment_id: mapping for mapping in inference.local_record_maps}
    for mapping in inference.local_record_maps:
        selected = tuple(pixels[key] for key in mapping.original_pixel_observation_ids)
        if any(row.local_track_id != mapping.local_track_id for row in selected) or any(
            b.timestamp <= a.timestamp or b.camera_id != a.camera_id for a, b in pairwise(selected)
        ):
            raise ValueError("behavior segments must preserve visible camera-local ordering")
        local_associations = tuple(associations[mapping.segment_id])
        for rows in _chunks(selected, threshold.max_visible_sample_gap_s):
            def make(kind: BehaviorKind, start: int, end: int, anchors: Sequence[int],
                     supports: tuple[str, ...], region_ids: tuple[str, ...] = (),
                     portal_ids: tuple[str, ...] = (), corner_ids: tuple[str, ...] = (),
                     conflicts: tuple[str, ...] = (), alternatives: tuple[str, ...] = (),
                     mapping: LocalRecordMap = mapping,
                     local_associations: tuple[AssociationHypothesis, ...] = local_associations,
                     rows: tuple[ProjectedMeasurement, ...] = rows,
                     ) -> LocalBehaviorEvent:
                return _event(inference=inference, config=config, config_sha=config_sha,
                              mapping=mapping, associations=local_associations, rows=rows,
                              kind=kind, start=start, end=end, anchors=anchors, supports=supports,
                              region_ids=region_ids, portal_ids=portal_ids, corner_ids=corner_ids,
                              conflicts=conflicts, alternatives=alternatives)

            for portal in config.portals:
                for kind, start, end in _door_crossings(rows, portal, regions, threshold):
                    events.append(make(kind, start, end, (start, end),
                                       ("BOTH_CONFIGURED_DOOR_SIDES_VISIBLE",
                                        "ORIENTED_FINITE_PORTAL_CROSSED_WITH_CONTINUOUS_PIXELS"),
                                       (portal.outside_region_id, portal.inside_region_id),
                                       (portal.portal_id,)))
            for corner in config.corners:
                last_turn = -math.inf
                for index in range(1, len(rows) - 1):
                    first, pivot, after = rows[index - 1:index + 2]
                    if not (_inside(pivot, regions[corner.near_region_id])
                            and ((_inside(first, regions[corner.approach_region_id])
                                  and _inside(after, regions[corner.departure_region_id]))
                                 or (_inside(first, regions[corner.departure_region_id])
                                     and _inside(after, regions[corner.approach_region_id])))):
                        continue
                    positions = tuple(_position(row) for row in (first, pivot, after))
                    angle = _angle(*positions)
                    if (min(math.dist(positions[0], positions[1]),
                            math.dist(positions[1], positions[2])) >= (
                                threshold.turn_min_displacement_m)
                        and threshold.turn_min_angle_deg <= angle <= threshold.turn_max_angle_deg
                        and pivot.timestamp - last_turn >= threshold.turn_refractory_s):
                        events.append(make("TURN_CORNER", index - 1, index + 1,
                                           (index - 1, index, index + 1),
                                           ("BOTH_CONFIGURED_CORNER_REGIONS_VISIBLE",
                                            f"VISIBLE_DIRECTION_CHANGE_DEG:{angle:.3f}"),
                                           (corner.approach_region_id, corner.departure_region_id),
                                           corner_ids=(corner.corner_id,)))
                        last_turn = pivot.timestamp
            for start, end in _dwell_intervals(rows, threshold):
                duration = rows[end].timestamp - rows[start].timestamp
                events.append(make("DWELL", start, end, (start, (start + end) // 2, end),
                                   ("CONTINUOUS_VISIBLE_LOW_MOTION_INTERVAL",
                                    f"VISIBLE_DURATION_S:{duration:.3f}"),
                                   tuple(dict.fromkeys(r for row in rows[start:end + 1]
                                                       for r in row.region_ids))))
            anchors, supports = _loiter_pattern(rows, config, regions)
            if anchors:
                start, end = max(0, anchors[0] - 1), min(len(rows) - 1, anchors[-1] + 1)
                events.append(make("POSSIBLE_LOITERING", start, end, anchors, supports,
                                   tuple(dict.fromkeys(r for row in rows[start:end + 1]
                                                       for r in row.region_ids))))
            producer_track = track_states.get(mapping.local_track_id)
            if (producer_track is not None
                and producer_track.termination_reason == "LOST_OR_LEFT_VIEW"
                and rows[-1].observation_id == producer_track.observation_ids[-1]
                and rows[-1].observation_id == selected[-1].observation_id):
                for corner in config.corners:
                    if _inside(rows[-1], regions[corner.near_region_id]):
                        start, end = max(0, len(rows) - 3), len(rows) - 1
                        events.append(make("LOST_NEAR_CORNER", start, end,
                                           tuple(range(start, end + 1)),
                                           ("LAST_VISIBLE_PIXEL_PROJECTION_NEAR_CONFIGURED_CORNER",
                                            "PRODUCER_REPORTED_LOST_OR_LEFT_VIEW"),
                                           (corner.near_region_id,), corner_ids=(corner.corner_id,),
                                           conflicts=("NO_VISIBLE_DEPARTURE_SIDE_OR_CROSSING_PROOF",),
                                           alternatives=("OCCLUSION_OR_MISSED_DETECTION",
                                                         "LEFT_CONFIGURED_CAMERA_VIEW")))
    gaps = {gap.event.event_id: gap for gap in inference.snapshot.gaps}
    for association in inference.association_hypotheses:
        if association.event_id is None:
            continue
        if association.kind != "CROSS_CAMERA_GAP":
            raise ValueError("same-camera recovery and overlap cannot become behavior blind gaps")
        gap = gaps[association.event_id]
        original_rows = [
            tuple(pixels[key] for key in segments[segment_id].original_pixel_observation_ids)
            for segment_id in association.segment_ids]
        # Actual visible endpoint photos, never a fabricated blind-gap image.
        selected = tuple(row for rows in original_rows for row in rows[-2:] if row.point is not None
                         and row.status == "PROJECTED")
        if len(original_rows) == 2:
            selected = tuple(row for row in (*original_rows[0][-2:], *original_rows[1][:2])
                             if row.point is not None and row.status == "PROJECTED")
        if not selected:
            raise ValueError("canonical gaps require visible projected endpoint evidence")
        event = _event(inference=inference, config=config, config_sha=config_sha,
                       mapping=segments[association.segment_ids[0]], associations=(association,),
                       rows=selected, kind="DWELL", start=0, end=len(selected) - 1,
                       anchors=tuple(range(len(selected))),
                       supports=("CANONICAL_GAP_ENDPOINTS_VISIBLE",))
        digest = content_sha256(
            [config_sha, "INFERRED_GAP_ALTERNATIVES", association.hypothesis_id])
        event_id = f"local-behavior:{digest}"
        events.append(LocalBehaviorEvent.model_validate(event.model_dump() | {
            "event_id": event_id, "kind": "INFERRED_GAP_ALTERNATIVES",
            "time_range": association.time_range, "local_track_ids": association.local_track_ids,
            "segment_ids": association.segment_ids, "region_ids": association.region_ids,
            "evidence_state": "INFERRED_GAP", "candidates": gap.event.candidates,
            "trajectories": gap.event.trajectories, "canonical_event_id": gap.event.event_id,
            "termination_reason": str(gap.event.termination_reason),
            "complete": gap.search_result.complete,
            "alternatives": tuple(candidate.candidate_id for candidate in gap.event.candidates),
            "uncertainty": (association.uncertainty + " Blind-gap route/timing alternatives are "
                            "not visible behavior or intent; canonical order is retained."),
            "detail_ref": event_id, "replay_ref": gap.event.event_id,
            "missing_evidence": (*event.missing_evidence, "NO_CAMERA_PHOTOGRAPHS_INSIDE_BLIND_GAP"),
        }))
    events.sort(key=lambda event: (event.time_range[0], event.time_range[1], event.event_id))
    return LocalBehaviorBundle(
        scope=inference.scope, inference_sha256=content_sha256(inference),
        config_sha256=config_sha, input_manifest_sha256=inference.input_manifest_sha256,
        producer_sha256=inference.producer_sha256,
        track_state_sha256=content_sha256([track.model_dump(mode="json") for track in tracks]),
        events=tuple(events), measurements_indexed=len(pixels),
        segments_visited=len(inference.local_record_maps),
    )
