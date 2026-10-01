"""Determinism, explicit metadata and non-overwriting simulation export."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.common import Provenance
from amidst.domain.ground_truth import GroundTruthTrajectory, PathKeyframe, TrajectoryConfig
from amidst.simulation.ground_truth import (
    blender_evaluated_trajectory,
    export_ground_truth_csv,
    export_ground_truth_json,
    sample_trajectory,
)


def _config() -> TrajectoryConfig:
    return TrajectoryConfig(
        random_seed=42,
        sample_rate_hz=2,
        keyframes=(
            PathKeyframe(timestamp=0, position=(0, 0, 0), floor_id="F1", zone_id="corridor"),
            PathKeyframe(timestamp=1, position=(2, 0, 0), floor_id="F1", zone_id="corner"),
            PathKeyframe(timestamp=2, position=(2, 2, 0), floor_id="F1", zone_id="exit"),
        ),
    )


def test_piecewise_position_velocity_metadata_and_seed() -> None:
    trajectory = sample_trajectory(_config())
    assert [sample.timestamp for sample in trajectory.samples] == [0, 0.5, 1, 1.5, 2]
    assert [sample.position for sample in trajectory.samples] == [
        (0, 0, 0),
        (1, 0, 0),
        (2, 0, 0),
        (2, 1, 0),
        (2, 2, 0),
    ]
    assert trajectory.samples[0].velocity == (2, 0, 0)
    assert trajectory.samples[2].velocity == (0, 2, 0)
    assert trajectory.samples[-1].velocity == (0, 2, 0)
    assert [sample.zone_id for sample in trajectory.samples] == [
        "corridor",
        "corridor",
        "corner",
        "corner",
        "exit",
    ]
    assert trajectory.random_seed == 42
    assert trajectory.data_kind == "SYNTHETIC"
    assert trajectory.sample_source == "CONFIGURATION_SAMPLER"
    assert all(sample.provenance == Provenance.GROUND_TRUTH for sample in trajectory.samples)
    assert trajectory == sample_trajectory(_config())


def test_off_grid_keyframes_and_final_endpoint_are_included_exactly_once() -> None:
    config = TrajectoryConfig(
        sample_rate_hz=2,
        keyframes=(
            PathKeyframe(timestamp=0.1, position=(0, 0, 0)),
            PathKeyframe(timestamp=0.4, position=(3, 0, 0)),
            PathKeyframe(timestamp=1.15, position=(3, 3, 0)),
        ),
    )
    samples = sample_trajectory(config).samples
    assert [sample.timestamp for sample in samples] == [0.1, 0.4, 0.6, 1.1, 1.15]
    assert samples[1].position == (3, 0, 0)
    assert samples[-1].position == (3, 3, 0)


def test_decimal_grid_does_not_duplicate_matching_keyframes() -> None:
    config = TrajectoryConfig(
        sample_rate_hz=10,
        keyframes=(
            PathKeyframe(timestamp=0.1, position=(0, 0, 0)),
            PathKeyframe(timestamp=0.3, position=(1, 0, 0)),
            PathKeyframe(timestamp=0.4, position=(2, 0, 0)),
        ),
    )
    assert [sample.timestamp for sample in sample_trajectory(config).samples] == [
        0.1,
        0.2,
        0.3,
        0.4,
    ]


def test_dwell_is_explicit_zero_velocity_without_invented_metadata() -> None:
    config = TrajectoryConfig(
        sample_rate_hz=1,
        keyframes=(
            PathKeyframe(timestamp=0, position=(1, 2, 3)),
            PathKeyframe(timestamp=2, position=(1, 2, 3)),
        ),
    )
    samples = sample_trajectory(config).samples
    assert all(sample.velocity == (0, 0, 0) for sample in samples)
    assert all(sample.floor_id is None and sample.zone_id is None for sample in samples)


@pytest.mark.parametrize("timestamps", [(1, 1), (2, 1), (0, float("inf"))])
def test_invalid_time_order_and_nonfinite_timestamps_are_rejected(
    timestamps: tuple[float, float],
) -> None:
    with pytest.raises(ValidationError):
        TrajectoryConfig(
            keyframes=tuple(PathKeyframe(timestamp=t, position=(0, 0, 0)) for t in timestamps)
        )


def test_sampling_limit_fails_before_large_allocation() -> None:
    with pytest.raises(ValueError, match="max_samples"):
        sample_trajectory(_config(), max_samples=3)
    with pytest.raises(ValueError, match="at least two"):
        sample_trajectory(_config(), max_samples=1)


def test_json_csv_serialization_and_no_overwrite(tmp_path: Path) -> None:
    trajectory = sample_trajectory(_config())
    json_path, csv_path = tmp_path / "ground_truth.json", tmp_path / "ground_truth.csv"
    export_ground_truth_json(trajectory, json_path)
    export_ground_truth_csv(trajectory, csv_path)
    assert GroundTruthTrajectory.model_validate_json(json_path.read_text()) == trajectory
    assert json.loads(json_path.read_text())["sample_source"] == "CONFIGURATION_SAMPLER"
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 5
    assert rows[0]["X"] == "0.0"
    assert rows[0]["provenance"] == "GROUND_TRUTH"
    assert rows[0]["data_kind"] == "SYNTHETIC"
    contents_before = json_path.read_bytes()
    with pytest.raises(FileExistsError):
        export_ground_truth_json(trajectory, json_path)
    assert json_path.read_bytes() == contents_before
    export_ground_truth_json(trajectory, json_path, overwrite=True)
    assert json_path.read_bytes() == contents_before
    assert {path.name for path in tmp_path.iterdir()} == {json_path.name, csv_path.name}


@pytest.mark.parametrize("exporter", [export_ground_truth_json, export_ground_truth_csv])
def test_export_never_overwrites_blender_asset_even_with_overwrite(
    tmp_path: Path,
    exporter: object,
) -> None:
    destination = tmp_path / "school_v2.blend"
    destination.write_bytes(b"immutable source sentinel")
    with pytest.raises(ValueError, match="destination"):
        exporter(sample_trajectory(_config()), destination, overwrite=True)  # type: ignore[operator]
    assert destination.read_bytes() == b"immutable source sentinel"


def test_blender_frame_domain_is_rejected_before_subprocess() -> None:
    config = TrajectoryConfig(
        sample_rate_hz=1,
        keyframes=(
            PathKeyframe(timestamp=50_000, position=(0, 0, 0)),
            PathKeyframe(timestamp=50_001, position=(1, 0, 0)),
        ),
    )
    with pytest.raises(ValueError, match="supported frame domain"):
        blender_evaluated_trajectory(config, blender_binary="does-not-exist")
