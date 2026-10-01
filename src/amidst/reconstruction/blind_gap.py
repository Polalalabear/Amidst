"""Time-parametrize graph candidates without inventing routes or behavior probabilities."""

from __future__ import annotations

import hashlib
import json
import math
from itertools import accumulate, pairwise
from typing import Literal

from pydantic import ValidationError

from amidst.domain.common import DomainModel, Provenance, Vec3
from amidst.domain.observation import Observation
from amidst.domain.reconstruction import ReconstructionPolicy as ReconstructionPolicy
from amidst.domain.trajectory import (
    CandidateTrajectory,
    Event,
    HypothesisKind,
    ReconstructionResult,
    SegmentKind,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)


class ReconstructionInputError(ValueError):
    """Evidence or candidates do not satisfy the reconstruction contract."""


def _check_embedded_contract(value: object) -> None:
    if isinstance(value, DomainModel):
        declared = set(type(value).model_fields)
        if set(value.__dict__) - declared or value.model_extra:
            raise ReconstructionInputError("model contains fields outside its declared contract")
        for field in declared:
            _check_embedded_contract(getattr(value, field))
    elif isinstance(value, (tuple, list)):
        for item in value:
            _check_embedded_contract(item)


def _validated[ModelT: DomainModel](model: ModelT, model_type: type[ModelT]) -> ModelT:
    if type(model) is not model_type:
        raise ReconstructionInputError(f"input must be a {model_type.__name__} instance")
    try:
        _check_embedded_contract(model)
        # model_validate(instance) trusts frozen instances. Dumping rechecks nested
        # values created by the deliberately unchecked model_copy/model_construct APIs.
        return model_type.model_validate(model.model_dump(mode="python"))
    except (ValidationError, AttributeError, TypeError, OverflowError) as error:
        raise ReconstructionInputError(
            f"input does not satisfy the {model_type.__name__} contract"
        ) from error


def _path_geometry(candidate: CandidateTrajectory) -> tuple[tuple[Vec3, ...], tuple[float, ...]]:
    points = tuple(
        point
        for index, point in enumerate(candidate.polyline)
        if index == 0 or point != candidate.polyline[index - 1]
    )
    distances = tuple(math.dist(start, end) for start, end in pairwise(points))
    try:
        length = math.fsum(distances)
    except OverflowError as error:
        raise ReconstructionInputError("candidate polyline distance overflowed") from error
    if not math.isfinite(length) or not math.isclose(
        length, float(candidate.path_length), rel_tol=1e-12, abs_tol=1e-9
    ):
        raise ReconstructionInputError("candidate path length must match its full 3D polyline")
    if length > 0 and candidate.minimum_travel_time <= 0:
        raise ReconstructionInputError("moving candidate must have positive minimum travel time")
    if length == 0 and candidate.minimum_travel_time != 0:
        raise ReconstructionInputError("stationary candidate must have zero minimum travel time")
    cumulative = (0.0, *accumulate(distances))
    if len(cumulative) > 1:
        cumulative = (*cumulative[:-1], length)
    return points, cumulative


def _timed_movement(
    points: tuple[Vec3, ...],
    cumulative: tuple[float, ...],
    start_time: float,
    end_time: float,
    *,
    start_provenance: Literal[Provenance.PROJECTED, Provenance.INFERRED_GAP] = Provenance.PROJECTED,
) -> tuple[TimedTrajectoryPoint, ...]:
    length = cumulative[-1]
    if length == 0:
        return (
            TimedTrajectoryPoint(
                timestamp=start_time, world_position=points[0], provenance=start_provenance
            ),
            TimedTrajectoryPoint(
                timestamp=end_time, world_position=points[0], provenance=Provenance.PROJECTED
            ),
        )
    duration = end_time - start_time
    result: list[TimedTrajectoryPoint] = []
    for index, (position, distance) in enumerate(zip(points, cumulative, strict=True)):
        timestamp = (
            end_time if index == len(points) - 1 else start_time + duration * (distance / length)
        )
        if result and timestamp <= result[-1].timestamp:
            raise ReconstructionInputError(
                "time precision cannot represent the candidate waypoints"
            )
        provenance = (
            start_provenance
            if index == 0
            else Provenance.PROJECTED
            if index == len(points) - 1
            else Provenance.INFERRED_GAP
        )
        result.append(
            TimedTrajectoryPoint(
                timestamp=timestamp, world_position=position, provenance=provenance
            )
        )
    return tuple(result)


class BlindGapReconstructor:
    """Preserve every supplied route and express its unobserved timing uncertainty."""

    def __init__(self, policy: ReconstructionPolicy | None = None) -> None:
        self.policy = _validated(policy or ReconstructionPolicy(), ReconstructionPolicy)

    def reconstruct_gap(
        self,
        start: Observation,
        end: Observation,
        result: ReconstructionResult,
        *,
        event_id: str | None = None,
    ) -> Event:
        start = _validated(start, Observation)
        end = _validated(end, Observation)
        result = _validated(result, ReconstructionResult)
        if start.target_id != end.target_id or start.observation_id == end.observation_id:
            raise ReconstructionInputError(
                "gap endpoints require one target and distinct observations"
            )
        if (
            start.provenance != Provenance.PROJECTED
            or end.provenance != Provenance.PROJECTED
            or not start.projected_path
            or not end.projected_path
        ):
            raise ReconstructionInputError("gap endpoints require PROJECTED evidence")
        start_point, end_point = start.projected_path[-1], end.projected_path[0]
        time_range = (float(start_point.timestamp), float(end_point.timestamp))
        if time_range[1] <= time_range[0]:
            raise ReconstructionInputError("gap must have positive duration")
        for candidate in result.candidates:
            if (
                candidate.start_observation_id != start.observation_id
                or candidate.end_observation_id != end.observation_id
            ):
                raise ReconstructionInputError(
                    "candidate observation endpoints do not match the gap"
                )
            if (
                math.dist(candidate.polyline[0], start_point.world_position)
                > self.policy.endpoint_tolerance_m
                or math.dist(candidate.polyline[-1], end_point.world_position)
                > self.policy.endpoint_tolerance_m
            ):
                raise ReconstructionInputError(
                    "candidate positions do not match projected endpoints"
                )
        if event_id is None:
            identity = json.dumps(
                {
                    "target_id": start.target_id,
                    "observation_ids": [start.observation_id, end.observation_id],
                    "time_range": time_range,
                },
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            event_id = f"event_{hashlib.sha256(identity).hexdigest()[:24]}"
        return self.reconstruct(
            Event(
                event_id=event_id,
                target_id=start.target_id,
                time_range=time_range,
                observation_ids=(start.observation_id, end.observation_id),
                candidates=result.candidates,
                termination_reason=result.termination_reason,
            )
        )

    def reconstruct(self, event: Event) -> Event:
        """Implement GapReasoner for an Event whose time_range is one blind gap."""
        event = _validated(event, Event)
        policy = _validated(self.policy, ReconstructionPolicy)
        start_time, end_time = map(float, event.time_range)
        duration = end_time - start_time
        if duration <= 0:
            raise ReconstructionInputError("gap must have positive duration")
        if not event.candidates:
            return Event.model_validate(event.model_dump() | {"trajectories": ()})
        shortest_length = min(float(candidate.path_length) for candidate in event.candidates)
        hypotheses: list[TrajectoryHypothesis] = []
        for candidate in event.candidates:
            points, cumulative = _path_geometry(candidate)
            minimum = float(candidate.minimum_travel_time)
            if minimum > duration:
                raise ReconstructionInputError("candidate minimum travel time exceeds the gap")
            slack = duration - minimum
            stationary = candidate.path_length == 0
            is_detour = float(candidate.path_length) - shortest_length > policy.endpoint_tolerance_m
            kind = (
                HypothesisKind.DWELL
                if stationary
                else HypothesisKind.DETOUR
                if is_detour
                else HypothesisKind.SLOWER_MOVEMENT
                if slack > policy.direct_path_slack_tolerance_s
                else HypothesisKind.DIRECT_PATH
            )
            hypotheses.append(
                TrajectoryHypothesis(
                    hypothesis_id=f"{candidate.candidate_id}:continuous",
                    candidate_id=candidate.candidate_id,
                    kind=kind,
                    timed_points=_timed_movement(points, cumulative, start_time, end_time),
                    segments=(
                        TrajectorySegment(
                            time_range=(start_time, end_time),
                            kind=SegmentKind.DWELL if stationary else SegmentKind.MOVEMENT,
                        ),
                    ),
                    minimum_travel_time=minimum,
                    temporal_slack=slack,
                    movement_duration=0.0 if stationary else duration,
                    dwell_duration=duration if stationary else 0.0,
                    uncertainty=(
                        "A longer supplied route is a possible detour relative to retained routes. "
                        if is_detour
                        else ""
                    )
                    + "Uniform timing is one admissible hypothesis; no behavioral probability is "
                    "calibrated or assigned.",
                )
            )
            if (
                stationary
                or not policy.include_dwell_hypotheses
                or slack <= policy.direct_path_slack_tolerance_s
            ):
                continue
            movement_start = start_time + slack
            if movement_start <= start_time or movement_start >= end_time:
                raise ReconstructionInputError("time precision cannot represent dwell and movement")
            moving = _timed_movement(
                points,
                cumulative,
                movement_start,
                end_time,
                start_provenance=Provenance.INFERRED_GAP,
            )
            hypotheses.append(
                TrajectoryHypothesis(
                    hypothesis_id=f"{candidate.candidate_id}:dwell_at_start",
                    candidate_id=candidate.candidate_id,
                    kind=HypothesisKind.DWELL,
                    timed_points=(
                        TimedTrajectoryPoint(
                            timestamp=start_time,
                            world_position=points[0],
                            provenance=Provenance.PROJECTED,
                        ),
                        *moving,
                    ),
                    segments=(
                        TrajectorySegment(
                            time_range=(start_time, movement_start), kind=SegmentKind.DWELL
                        ),
                        TrajectorySegment(
                            time_range=(movement_start, end_time), kind=SegmentKind.MOVEMENT
                        ),
                    ),
                    minimum_travel_time=minimum,
                    temporal_slack=slack,
                    movement_duration=minimum,
                    dwell_duration=slack,
                    uncertainty="Dwell at the departure waypoint is a deterministic timing "
                    "alternative, not observed behavior; no behavioral probability is calibrated "
                    "or assigned.",
                )
            )
        return Event.model_validate(
            event.model_dump() | {"trajectories": [item.model_dump() for item in hypotheses]}
        )
