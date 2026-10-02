"""Readable synthetic inputs shared only by the guard regression modules."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from amidst.domain.common import Vec3
from amidst.domain.ground_truth import GroundTruthSample, GroundTruthTrajectory
from amidst.domain.trajectory import (
    HypothesisKind,
    SegmentKind,
    TimedTrajectoryPoint,
    TrajectoryHypothesis,
    TrajectorySegment,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "data" / "mock" / "boundary"


def guards_fixture(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert payload["data_kind"] == "SYNTHETIC_TEST_FIXTURE"
    return payload


def guards_numeric_tokens(value: Any) -> Any:
    """JSON stays standard; invalid IEEE inputs use readable explicit tokens."""
    tokens = {
        "NaN": math.nan,
        "+Infinity": math.inf,
        "-Infinity": -math.inf,
        "NEXT_BELOW_0.625": math.nextafter(0.625, -math.inf),
        "NEXT_ABOVE_0.625": math.nextafter(0.625, math.inf),
    }
    if isinstance(value, str):
        return tokens.get(value, value)
    if isinstance(value, list):
        return [guards_numeric_tokens(item) for item in value]
    if isinstance(value, dict):
        return {key: guards_numeric_tokens(item) for key, item in value.items()}
    return value


def guards_trajectory(y: float = 0) -> TrajectoryHypothesis:
    points: tuple[Vec3, Vec3] = ((0, y, 0), (10, y, 0))
    return TrajectoryHypothesis(
        hypothesis_id="boundary-hypothesis",
        candidate_id="boundary-route",
        kind=HypothesisKind.SLOWER_MOVEMENT,
        timed_points=tuple(
            TimedTrajectoryPoint(timestamp=time, world_position=point)
            for time, point in zip((0, 1), points, strict=True)
        ),
        segments=(TrajectorySegment(time_range=(0, 1), kind=SegmentKind.MOVEMENT),),
        minimum_travel_time=1,
        temporal_slack=0,
        movement_duration=1,
        dwell_duration=0,
        uncertainty="SYNTHETIC_TEST_FIXTURE: adversarial geometry, no mesh certification",
    )


def guards_truth(y: float = 0) -> GroundTruthTrajectory:
    return GroundTruthTrajectory(
        trajectory_id="boundary-reference",
        target_id="boundary-target",
        scene_id="SYNTHETIC_TEST_FIXTURE",
        random_seed=20261002,
        sample_rate_hz=1,
        samples=tuple(
            GroundTruthSample(timestamp=time, position=(x, y, 0), velocity=(10, 0, 0))
            for time, x in ((0, 0), (1, 10))
        ),
    )
