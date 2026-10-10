"""Versioned local continuity from the unchanged RGB component detector.

No identity, simulator, recipe or annotation is an input.  The detector and its
contact measurements stay fixed so assignment ablations have one population.
An unresolved merged component is retained as a measurement; it cannot update
the motion or appearance history of either possible predecessor.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, FiniteFloat

from amidst.engineering import perception as detector
from amidst.engineering.access import digest
from amidst.engineering.perception import (
    LocalTrack,
    Measurement,
    PerceptionResult,
    PixelModel,
    RGBFrame,
)

PRODUCER_VERSION = "rgb-global-continuity-v2"


class PixelContinuityConfig(PixelModel):
    """Development-fixed soft assignment policy; scores are not probabilities."""

    config_version: Literal["pixel-continuity-development-v2"] = "pixel-continuity-development-v2"
    assignment: Literal["global", "greedy"] = "global"
    use_velocity: bool = True
    appearance_weight: Annotated[FiniteFloat, Field(ge=0)] = 0.25
    shape_weight: Annotated[FiniteFloat, Field(ge=0)] = 0.10
    merge_quarantine: bool = True
    max_gap_s: Annotated[FiniteFloat, Field(gt=0)] = 1.21
    max_prediction_error_px: Annotated[FiniteFloat, Field(gt=0)] = 24.0
    appearance_scale: Annotated[FiniteFloat, Field(gt=0)] = 64.0
    unmatched_cost: Annotated[FiniteFloat, Field(gt=0)] = 1.05
    merge_contact_padding_px: Annotated[FiniteFloat, Field(ge=0)] = 3.0


@dataclass(frozen=True)
class _Candidate:
    cost: float
    track_id: str
    predicted_contact: tuple[float, float]


def producer_sha256(config: PixelContinuityConfig) -> str:
    """Bind both implementation sources and the complete assignment policy."""
    return digest({
        "version": PRODUCER_VERSION,
        "continuity_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "detector_source_sha256": sha256(Path(detector.__file__).read_bytes()).hexdigest(),
        "config": config.model_dump(mode="json"),
    })


def _prediction(history: list[Measurement], timestamp: float,
                config: PixelContinuityConfig) -> tuple[float, float]:
    last = history[-1]
    if not config.use_velocity or len(history) < 2:
        return last.contact_pixel
    # Use only measured contacts, never extrapolate across a long hidden interval.
    previous = history[-2]
    interval = last.timestamp - previous.timestamp
    if not 0 < interval <= config.max_gap_s:
        return last.contact_pixel
    dt = timestamp - last.timestamp
    return (
        last.contact_pixel[0] + (last.contact_pixel[0] - previous.contact_pixel[0]) * dt / interval,
        last.contact_pixel[1] + (last.contact_pixel[1] - previous.contact_pixel[1]) * dt / interval,
    )


def _candidates(measurement: Measurement, histories: dict[str, list[Measurement]],
                config: PixelContinuityConfig) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for track_id, history in histories.items():
        last = history[-1]
        dt = measurement.timestamp - last.timestamp
        if not 0 < dt <= config.max_gap_s:
            continue
        # Preserve the inherited displacement bound as well as a prediction gate.
        displacement = math.dist(measurement.contact_pixel, last.contact_pixel)
        if displacement > 28.0 * max(1.0, dt / 0.2):
            continue
        predicted = _prediction(history, measurement.timestamp, config)
        residual = math.dist(measurement.contact_pixel, predicted)
        if residual > config.max_prediction_error_px:
            continue
        colors = [row.appearance for row in history[-3:]]
        mean_color = tuple(math.fsum(c[channel] for c in colors) / len(colors)
                           for channel in range(3))
        appearance_cost = math.dist(measurement.appearance, mean_color) / config.appearance_scale
        width, height = (measurement.bbox_xyxy[2] - measurement.bbox_xyxy[0],
                         measurement.bbox_xyxy[3] - measurement.bbox_xyxy[1])
        previous_width = last.bbox_xyxy[2] - last.bbox_xyxy[0]
        previous_height = last.bbox_xyxy[3] - last.bbox_xyxy[1]
        shape_cost = (abs(math.log(width / previous_width))
                      + abs(math.log(height / previous_height))) / 2.0
        cost = (residual / config.max_prediction_error_px
                + config.appearance_weight * appearance_cost + config.shape_weight * shape_cost)
        if cost < config.unmatched_cost:
            candidates.append(_Candidate(cost, track_id, predicted))
    return sorted(candidates, key=lambda row: (row.cost, row.track_id))


def _merged(measurement: Measurement, candidates: list[_Candidate],
            config: PixelContinuityConfig) -> bool:
    if not config.merge_quarantine:
        return False
    if measurement.status == "MERGED_OR_PARTIAL":
        return True
    xmin, _, xmax, ymax = measurement.bbox_xyxy
    padding = config.merge_contact_padding_px
    # Two independently predicted feet entering one connected RGB component are
    # merge evidence.  Do not split its pixels or choose a hidden identity.
    inside = [candidate for candidate in candidates
              if xmin - padding <= candidate.predicted_contact[0] < xmax + padding
              and abs(candidate.predicted_contact[1] - (ymax - 1)) <= padding]
    return len(inside) > 1


def _minimum_assignment(costs: list[list[float]]) -> list[int]:
    """Deterministic rectangular Hungarian assignment, rows <= columns."""
    if not costs:
        return []
    rows, columns = len(costs), len(costs[0])
    row_potential = [0.0] * (rows + 1)
    column_potential = [0.0] * (columns + 1)
    matching = [0] * (columns + 1)
    previous = [0] * (columns + 1)
    for row in range(1, rows + 1):
        matching[0] = row
        column = 0
        minimum = [math.inf] * (columns + 1)
        used = [False] * (columns + 1)
        while True:
            used[column] = True
            current_row = matching[column]
            delta, next_column = math.inf, 0
            for candidate in range(1, columns + 1):
                if used[candidate]:
                    continue
                reduced = (costs[current_row - 1][candidate - 1]
                           - row_potential[current_row] - column_potential[candidate])
                if reduced < minimum[candidate]:
                    minimum[candidate] = reduced
                    previous[candidate] = column
                if minimum[candidate] < delta:
                    delta, next_column = minimum[candidate], candidate
            for candidate in range(columns + 1):
                if used[candidate]:
                    row_potential[matching[candidate]] += delta
                    column_potential[candidate] -= delta
                else:
                    minimum[candidate] -= delta
            column = next_column
            if matching[column] == 0:
                break
        while column:
            next_column = previous[column]
            matching[column] = matching[next_column]
            column = next_column
    assignments = [-1] * rows
    for column in range(1, columns + 1):
        if matching[column]:
            assignments[matching[column] - 1] = column - 1
    return assignments


def _assign(options: list[list[_Candidate]], quarantined: list[bool],
            config: PixelContinuityConfig) -> list[str | None]:
    if config.assignment == "greedy":
        used: set[str] = set()
        greedy: list[str | None] = []
        for candidates, quarantine in zip(options, quarantined, strict=True):
            selected = next((row.track_id for row in candidates if row.track_id not in used), None)
            if quarantine:
                selected = None
            greedy.append(selected)
            if selected is not None:
                used.add(selected)
        return greedy
    tracks = sorted({row.track_id for candidates in options for row in candidates})
    blocked_cost = config.unmatched_cost + 1.0
    costs = []
    for candidates, quarantine in zip(options, quarantined, strict=True):
        lookup = {} if quarantine else {row.track_id: row.cost for row in candidates}
        # Every component can independently start a new track; no forced match.
        costs.append([lookup.get(track_id, blocked_cost) for track_id in tracks]
                     + [config.unmatched_cost] * len(options))
    return [tracks[column] if column < len(tracks) else None
            for column in _minimum_assignment(costs)]


def reassociate_perception_v2(
    perception: PerceptionResult, *, config: PixelContinuityConfig | None = None,
) -> PerceptionResult:
    """Reassign a frozen v1 detector population for single-feature ablations.

    Bboxes, contacts, appearances, frames and input hashes remain exactly fixed.
    New track/observation namespaces and producer lineage distinguish this result.
    The input must come from the currently bound unchanged detector.
    """
    config = config or PixelContinuityConfig()
    inherited_hash = sha256(Path(detector.__file__).read_bytes()).hexdigest()
    if (perception.producer_version != detector.PRODUCER_VERSION
            or perception.producer_sha256 != inherited_hash):
        raise ValueError("v2 continuity requires the bound v1 RGB detector result")
    grouped: dict[str, dict[float, list[Measurement]]] = defaultdict(lambda: defaultdict(list))
    for measurement in perception.measurements:
        grouped[measurement.camera_id][measurement.timestamp].append(measurement)
    measurements: list[Measurement] = []
    tracks: list[LocalTrack] = []
    ambiguous_frames: set[str] = set()
    for camera_id, camera_rows in sorted(grouped.items()):
        histories: dict[str, list[Measurement]] = {}
        reliable: dict[str, list[Measurement]] = {}
        for _timestamp, rows in sorted(camera_rows.items()):
            rows.sort(key=lambda row: (row.bbox_xyxy[0], row.bbox_xyxy[1], row.observation_id))
            options = [_candidates(row, reliable, config) for row in rows]
            quarantined = [_merged(row, candidates, config)
                           for row, candidates in zip(rows, options, strict=True)]
            assignments = _assign(options, quarantined, config)
            for row, candidates, quarantine, selected in zip(
                rows, options, quarantined, assignments, strict=True,
            ):
                track_id = selected
                if track_id is None:
                    track_id = (f"track-v2:{perception.model_id}:{perception.run_id}:"
                                f"{camera_id}:{len(histories):04d}")
                    histories[track_id] = []
                alternative_count = max(row.local_alternative_count, len(candidates) - 1,
                                        len(candidates) if quarantine else 0)
                updated = row.model_copy(update={
                    "observation_id": row.observation_id.replace("pixel:", "pixel-v2:", 1),
                    "local_track_id": track_id,
                    "producer_version": PRODUCER_VERSION,
                    "status": "MERGED_OR_PARTIAL" if quarantine else row.status,
                    "uncertainty": max(row.uncertainty, 0.75 if quarantine else
                                       0.40 if alternative_count else 0.25),
                    "local_alternative_count": alternative_count,
                })
                histories[track_id].append(updated)
                measurements.append(updated)
                if quarantine:
                    ambiguous_frames.add(row.frame_ref)
                else:
                    reliable.setdefault(track_id, []).append(updated)
        camera_timestamps = [row.timestamp for row in perception.frame_statuses
                             if row.camera_id == camera_id]
        for track_id, history in histories.items():
            timestamps = tuple(row.timestamp for row in history)
            observed = set(timestamps)
            missing = tuple(t for t in camera_timestamps
                            if timestamps[0] < t < timestamps[-1] and t not in observed)
            tracks.append(LocalTrack(
                local_track_id=track_id, camera_id=camera_id, run_id=perception.run_id,
                model_id=perception.model_id,
                observation_ids=tuple(row.observation_id for row in history), timestamps=timestamps,
                status="FRAGMENTED" if missing else "COMPLETE", missing_timestamps=missing,
                termination_reason=("SEQUENCE_END" if timestamps[-1] == max(camera_timestamps)
                                    else "LOST_OR_LEFT_VIEW"),
            ))
    statuses = tuple(row.model_copy(update={
        "status": "AMBIGUOUS_COMPONENT", "issue": "multiple or partial RGB contact evidence",
    }) if row.frame_ref in ambiguous_frames else row for row in perception.frame_statuses)
    return perception.model_copy(update={
        "measurements": tuple(measurements), "tracks": tuple(tracks),
        "frame_statuses": statuses, "producer_version": PRODUCER_VERSION,
        "producer_sha256": producer_sha256(config),
    })


def produce_perception_v2(
    frames: Sequence[RGBFrame], *, model_id: str, run_id: str,
    config: PixelContinuityConfig | None = None,
) -> PerceptionResult:
    """Recompute verified RGB components, then apply the versioned continuity policy."""
    return reassociate_perception_v2(
        detector.produce_perception(frames, model_id=model_id, run_id=run_id), config=config,
    )
