"""Public synthetic observation flow never publishes hidden motion coordinates."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from amidst.domain.camera import Camera
from amidst.domain.ground_truth import PathKeyframe, TrajectoryConfig
from amidst.portability.blender import resolve_blender_executable
from amidst.simulation.ground_truth import sample_trajectory
from amidst.simulation.observation_export import blender_ray_queries, observe_trajectory
from amidst.simulation.raycast_types import RaycastResult


def test_simulated_partial_2d_evidence_has_observed_and_gap_without_truth() -> None:
    truth = sample_trajectory(
        TrajectoryConfig(
            sample_rate_hz=1,
            keyframes=(
                PathKeyframe(timestamp=0, position=(0, 0, 0)),
                PathKeyframe(timestamp=4, position=(20, 0, 0)),
            ),
        )
    )
    camera = Camera(
        camera_id="CAM_FIXTURE",
        width=100,
        height=100,
        fx=50,
        fy=50,
        cx=50,
        cy=50,
        camera_to_world=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1)),
    )
    frames = observe_trajectory(
        truth, (camera,), lambda origin, target: RaycastResult(False, "CLEAR")
    )
    assert frames[0].status == "OBSERVED"
    assert frames[-1].status == "GAP" and frames[-1].point_2d is None
    serialized = json.dumps([frame.model_dump(mode="json") for frame in frames])
    assert "GROUND_TRUTH" not in serialized
    assert "position" not in serialized and "velocity" not in serialized


def test_cli_rejects_mismatched_source_before_geometry(tmp_path: Path) -> None:
    source = tmp_path / "fixture.blend"
    source.write_bytes(b"non executable test sentinel")
    truth = sample_trajectory(
        TrajectoryConfig(
            sample_rate_hz=1,
            keyframes=(
                PathKeyframe(timestamp=0, position=(0, 0, 0)),
                PathKeyframe(timestamp=1, position=(1, 0, 0)),
            ),
        )
    )
    truth_path, cameras_path = tmp_path / "truth.json", tmp_path / "cameras.json"
    truth_path.write_text(truth.model_dump_json())
    cameras_path.write_text(json.dumps({"source_asset_sha256": "mismatch", "cameras": []}))
    output = tmp_path / "observations.json"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/export_observations.py",
            "--ground-truth",
            str(truth_path),
            "--cameras",
            str(cameras_path),
            "--blend",
            str(source),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        timeout=30,
    )
    assert result.returncode == 2 and "share a source hash" in result.stderr
    assert not output.exists()


def test_blender_ray_batch_roundtrip_never_requires_truth_schema_in_blender() -> None:
    try:
        blender = resolve_blender_executable()
    except FileNotFoundError:
        if os.environ.get("BLENDER_BIN"):
            raise
        pytest.skip("Blender CLI unavailable; configure BLENDER_BIN or PATH")
    results = blender_ray_queries(
        (((0, 0, 10), (0, 0, -2)), ((10, 0, 10), (10, 0, 0))), blender_binary=blender
    )
    assert results[0].occluded and results[0].reason == "OCCLUDED"
    assert not results[1].occluded and results[1].reason == "CLEAR"
