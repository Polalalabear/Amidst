"""Fixture-to-event-to-metrics-to-Rerun closed loop, with generic input APIs."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from amidst.debug.runner import run_experiment
from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig
from amidst.domain.trajectory import HypothesisKind, TerminationReason

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "mock"


@pytest.mark.parametrize("name,route_count,hypothesis_count", [
    ("single_path", 1, 1), ("branching_top_k", 3, 5),
    ("temporal_slack", 2, 4), ("simplified_stair", 1, 1),
])
def test_entire_downstream_flow(
    tmp_path: Path, name: str, route_count: int, hypothesis_count: int,
) -> None:
    folder = FIXTURES / name
    output = tmp_path / name
    result, event, metrics = run_experiment(
        folder / "inference.json", output, ground_truth_path=folder / "ground_truth.json",
        constraints=ConstraintConfig.model_validate_json(
            (FIXTURES / "constraints.json").read_text(),
        ),
    )
    assert result.termination_reason == event.termination_reason == TerminationReason.COMPLETE
    assert len(result.candidates) == route_count
    assert len(event.trajectories) == hypothesis_count
    assert metrics is not None
    assert metrics.selected_route_count == route_count
    assert metrics.min_ade_at_k_m == pytest.approx(0.0, abs=1e-12)
    assert metrics.min_fde_at_k_m == 0.0
    assert metrics.coverage_at_k
    assert metrics.collision_rate == metrics.constraint_violation_rate == 0.0
    run_config = json.loads((output / "run_config.json").read_text())
    assert run_config["reconstruction_policy"]["direct_path_slack_tolerance_s"] == 1.0
    assert run_config["evaluation_config"]["k_routes"] == 3
    assert len(run_config["constraint_config"]["obstacles"]) == 1
    assert (output / "debug.rrd").stat().st_size > 1000
    assert "GROUND_TRUTH" not in (output / "event.json").read_text()
    if name == "single_path":
        assert event.trajectories[0].kind == HypothesisKind.DIRECT_PATH
    if name == "temporal_slack":
        assert event.trajectories[0].temporal_slack == 160.0
        assert {trajectory.kind for trajectory in event.trajectories} == {
            HypothesisKind.SLOWER_MOVEMENT, HypothesisKind.DWELL, HypothesisKind.DETOUR,
        }
        assert any(trajectory.dwell_duration == 160.0 for trajectory in event.trajectories)
        assert all(candidate.path_score is None for candidate in result.candidates)
    with pytest.raises(FileExistsError):
        run_experiment(folder / "inference.json", output, record_rerun=False)


def test_branching_coverage_at_one_fails_and_at_three_passes(tmp_path: Path) -> None:
    folder = FIXTURES / "branching_top_k"
    result, event, metric = run_experiment(
        folder / "inference.json", tmp_path / "one",
        ground_truth_path=folder / "ground_truth.json",
        evaluation_config=EvaluationConfig(k_routes=1), record_rerun=False,
    )
    assert len(result.candidates) == 3 and len(event.trajectories) == 5
    assert metric is not None and not metric.coverage_at_k
    assert metric.min_ade_at_k_m is not None and metric.min_ade_at_k_m > 1.0
    assert metric.min_fde_at_k_m == 0.0


def test_inference_only_runner_needs_no_truth_and_outputs_are_repeatable(tmp_path: Path) -> None:
    source = FIXTURES / "temporal_slack" / "inference.json"
    first, second = tmp_path / "one", tmp_path / "two"
    run_experiment(source, first, record_rerun=False)
    run_experiment(source, second, record_rerun=False)
    for name in ("candidates.json", "event.json", "run_config.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert not (first / "metrics.json").exists()


@pytest.mark.parametrize("field,value", [
    ("target_id", "wrong-target"), ("scene_id", "wrong-context"),
    ("source_asset_sha256", "f" * 64),
])
def test_wrong_truth_binding_rejected_before_outputs(
    tmp_path: Path, field: str, value: str,
) -> None:
    folder = FIXTURES / "single_path"
    truth = json.loads((folder / "ground_truth.json").read_text())
    truth[field] = value
    input_truth = tmp_path / "wrong_truth.json"
    input_truth.write_text(json.dumps(truth))
    with pytest.raises(ValueError):
        run_experiment(folder / "inference.json", tmp_path / "output",
                       ground_truth_path=input_truth, record_rerun=False)
    assert not (tmp_path / "output").exists()


def test_generic_cli_persists_explicit_metric_config(tmp_path: Path) -> None:
    folder = FIXTURES / "branching_top_k"
    output = tmp_path / "cli"
    root = FIXTURES.parents[1]
    process = subprocess.run([
        sys.executable, str(root / "scripts" / "run_downstream.py"),
        "--input", str(folder / "inference.json"),
        "--ground-truth", str(folder / "ground_truth.json"),
        "--constraints", str(FIXTURES / "constraints.json"),
        "--output", str(output), "--k", "1", "--coverage-epsilon-m", "0.01", "--no-rerun",
    ], capture_output=True, text=True, check=True)
    assert "3 routes" in process.stdout and "Coverage@K=False" in process.stdout
    config = json.loads((output / "run_config.json").read_text())
    assert config["evaluation_config"]["k_routes"] == 1
    assert config["evaluation_config"]["coverage_epsilon_m"] == 0.01
    assert config["constraint_config"]["obstacles"][0]["obstacle_id"] == "SYNTHETIC_WALL"
