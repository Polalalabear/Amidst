"""Evaluate transient target geometry in Blender without rendering or saving."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from amidst.domain.ground_truth import GroundTruthTrajectory, TrajectoryConfig
from amidst.simulation.ground_truth import blender_evaluated_trajectory, sample_trajectory

REPO_ROOT = Path(__file__).resolve().parents[2]


def _blender() -> str:
    executable = os.environ.get("BLENDER_BIN") or shutil.which("blender")
    if executable is None:
        installed = Path("/Applications/Blender.app/Contents/MacOS/blender")
        executable = str(installed) if installed.is_file() else None
    if executable is None:
        pytest.skip("Blender CLI unavailable")
    return executable


def _config() -> TrajectoryConfig:
    return TrajectoryConfig.model_validate_json(
        (REPO_ROOT / "configs/trajectory_fixture.json").read_text(encoding="utf-8")
    )


def test_blender_evaluated_export_matches_configured_path_and_is_deterministic() -> None:
    analytic = sample_trajectory(_config())
    first = blender_evaluated_trajectory(_config(), blender_binary=_blender())
    second = blender_evaluated_trajectory(_config(), blender_binary=_blender())
    assert first == second
    assert first.sample_source == "BLENDER_EVALUATED"
    assert first.scene_id == "SYNTHETIC_TEST_FIXTURE"
    assert len(first.samples) == 41
    for evaluated, expected in zip(first.samples, analytic.samples, strict=True):
        assert evaluated.timestamp == expected.timestamp
        assert evaluated.position == pytest.approx(expected.position, abs=1e-5)
        assert evaluated.velocity == expected.velocity


def test_proxy_linear_interpolation_foot_anchor_and_exception_cleanup() -> None:
    code = f"""
import sys
from types import SimpleNamespace
sys.path.insert(0, {str(REPO_ROOT / "src")!r})
import bpy
from amidst.simulation.blender_target import animated_target_proxy, evaluated_proxy_positions
scene = bpy.context.scene
scene.frame_set(7, subframe=0.25)
objects_before = set(bpy.data.objects.keys())
meshes_before = set(bpy.data.meshes.keys())
actions_before = set(bpy.data.actions.keys())
trajectory = SimpleNamespace(samples=[
    SimpleNamespace(timestamp=0.0, position=(0, 0, 0)),
    SimpleNamespace(timestamp=2.0, position=(2, 0, 0)),
    SimpleNamespace(timestamp=4.0, position=(2, 2, 0))])
for should_fail in (False, True):
    try:
        with animated_target_proxy(scene, trajectory) as proxy:
            assert min(vertex.co.z for vertex in proxy.data.vertices) == 0
            assert abs(max(vertex.co.z for vertex in proxy.data.vertices) - 1.7) < 1e-6
            actual = evaluated_proxy_positions(scene, proxy, [0, 0.5, 1, 2, 3, 4])
            expected = [(0,0,0), (0.5,0,0), (1,0,0), (2,0,0), (2,1,0), (2,2,0)]
            assert all(abs(a-b) < 1e-5 for p,q in zip(actual,expected) for a,b in zip(p,q))
            assert scene.frame_current == 7 and abs(scene.frame_subframe - 0.25) < 1e-6
            if should_fail:
                raise RuntimeError('test exception')
    except RuntimeError:
        assert should_fail
    assert set(bpy.data.objects.keys()) == objects_before
    assert set(bpy.data.meshes.keys()) == meshes_before
    assert set(bpy.data.actions.keys()) == actions_before
print('BLENDER_TARGET_LIFECYCLE_OK')
"""
    result = subprocess.run(
        [
            _blender(),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "-noaudio",
            "--python-exit-code",
            "2",
            "--python-expr",
            code,
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert "BLENDER_TARGET_LIFECYCLE_OK" in result.stdout


def test_cli_exports_json_csv_and_refuses_overwrite(tmp_path: Path) -> None:
    json_path, csv_path = tmp_path / "ground_truth.json", tmp_path / "ground_truth.csv"
    command = [
        "uv",
        "run",
        "python",
        "scripts/export_ground_truth.py",
        "--config",
        "configs/trajectory_fixture.json",
        "--blender-bin",
        _blender(),
        "--json",
        str(json_path),
        "--csv",
        str(csv_path),
    ]
    completed = subprocess.run(
        command, cwd=REPO_ROOT, check=True, capture_output=True, text=True, timeout=60
    )
    assert "41 BLENDER_EVALUATED SYNTHETIC samples" in completed.stdout
    result = GroundTruthTrajectory.model_validate_json(json_path.read_text())
    assert result.sample_source == "BLENDER_EVALUATED"
    with csv_path.open(newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 41
    original = json_path.read_bytes()
    rejected = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert rejected.returncode == 2
    assert "already exists" in rejected.stderr
    assert json_path.read_bytes() == original


@pytest.mark.parametrize("destination", ["asset.blend", "configuration.json"])
def test_cli_rejects_asset_and_configuration_overwrite(
    tmp_path: Path,
    destination: str,
) -> None:
    configuration = tmp_path / "configuration.json"
    configuration.write_text((REPO_ROOT / "configs/trajectory_fixture.json").read_text())
    target = tmp_path / destination
    if target != configuration:
        target.write_bytes(b"immutable Blender sentinel")
    original = target.read_bytes()
    completed = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/export_ground_truth.py",
            "--config",
            str(configuration),
            "--json",
            str(target),
            "--overwrite",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 2
    assert target.read_bytes() == original
