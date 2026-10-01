"""Replayable unified benchmark command and source-independent consumer parity."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from amidst.benchmark.runner import BenchmarkResult, GapResult, run_benchmark
from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig, EvaluationResult
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.trajectory import TerminationReason
from amidst.evaluation import evaluate_trajectories
from amidst.experiments.versioning import load_experiment, resolve_reference
from amidst.pipeline import load_inference_input, reconstruct_input

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "benchmarks" / "mock_stream_v1.json"
FIXTURES = ROOT / "data" / "mock"


def _metric(gap: GapResult) -> EvaluationResult:
    assert gap.evaluation is not None
    return gap.evaluation.for_k(3)


def _reference(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _custom_config(
    directory: Path, *, case_ids: tuple[str, ...] = ("single_path",),
    case_updates: dict[str, Any] | None = None,
    frames: dict[str, Any] | None = None,
    truth: dict[str, Any] | None = None,
    config_updates: dict[str, Any] | None = None,
) -> Path:
    """Rebind content hashes for local test mutations without changing source inputs."""
    config, dataset, manifest_path = load_experiment(CONFIG)
    directory.mkdir(parents=True, exist_ok=True)
    payload = dataset.model_dump(mode="json")
    payload["cases"] = [case for case in payload["cases"] if case["case_id"] in case_ids]
    for case in payload["cases"]:
        for name in ("pipeline", "frames", "constraints", "camera_calibration"):
            if case[name] is not None:
                case[name]["path"] = str((manifest_path.parent / case[name]["path"]).resolve())
        for reference in case["evaluation_references"]:
            reference["path"] = str((manifest_path.parent / reference["path"]).resolve())
        if frames is not None:
            frame_path = directory / "frames.json"
            frame_path.write_text(json.dumps(frames))
            case["frames"] = _reference(frame_path)
        if truth is not None:
            truth_path = directory / "ground_truth.json"
            truth_path.write_text(json.dumps(truth))
            case["evaluation_references"] = [_reference(truth_path)]
        if case_updates:
            case.update(case_updates)
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps(payload))
    config_payload = config.model_dump(mode="json")
    config_payload["dataset_manifest"] = _reference(manifest)
    config_payload["metric_config"]["path"] = str(resolve_reference(config.metric_config, CONFIG))
    if config_updates:
        config_payload.update(config_updates)
    target = directory / "experiment.json"
    target.write_text(json.dumps(config_payload))
    return target


def _deterministic_cases(result: BenchmarkResult) -> list[dict[str, object]]:
    return [case.model_dump(mode="json", exclude={"inference_runtime_s"}) for case in result.cases]


def test_four_scenarios_run_end_to_end_and_persist_bound_outputs(tmp_path: Path) -> None:
    output = tmp_path / "benchmark"
    result = run_benchmark(CONFIG, output, search_clock=lambda: 0.0)
    expected = {
        "single_path": (1, 1),
        "branching_top_k": (3, 5),
        "temporal_slack": (2, 4),
        "simplified_stair": (1, 1),
    }
    assert len(result.cases) == 4
    assert result.record.config.seed == result.record.dataset.seed == 20261001
    assert result.record.config.dataset_version == result.record.dataset.dataset_version
    assert len(result.record.git.commit) == 40
    assert result.record.inputs
    for case in result.cases:
        assert len(case.aggregation.observations) == 2
        assert len(case.gaps) == 1
        gap = case.gaps[0]
        assert (len(gap.gap.event.candidates), len(gap.gap.event.trajectories)) == expected[
            case.case_id
        ]
        assert (
            gap.gap.search_result.termination_reason
            == gap.gap.event.termination_reason
            == (TerminationReason.COMPLETE)
        )
        evaluation = _metric(gap)
        assert evaluation.min_ade_at_k_m == pytest.approx(0, abs=1e-12)
        assert evaluation.min_fde_at_k_m == 0
        assert evaluation.coverage_at_k
        assert evaluation.collision_rate == evaluation.constraint_violation_rate == 0
        assert gap.rerun_artifact is None
    for filename in ("config.json", "experiment.json", "summary.json", "metrics.json"):
        assert json.loads((output / filename).read_text())
    summary = json.loads((output / "summary.json").read_text())
    assert summary["seed"] == 20261001
    assert summary["git_commit"] == result.record.git.commit
    assert len(summary["cases"]) == 4
    assert len(list((output / "cases").rglob("candidates.json"))) == 4
    assert len(list((output / "cases").rglob("observations.json"))) == 4


def test_benchmark_replay_preserves_all_geometry_timing_and_metrics(tmp_path: Path) -> None:
    first = run_benchmark(CONFIG, tmp_path / "first", search_clock=lambda: 0.0)
    second = run_benchmark(CONFIG, tmp_path / "second", search_clock=lambda: 0.0)
    # Runtime and concurrently changing Git dirty-state metadata are diagnostic identity.
    assert _deterministic_cases(first) == _deterministic_cases(second)
    assert first.record.config_sha256 == second.record.config_sha256
    assert first.record.inputs == second.record.inputs
    for directory in sorted((tmp_path / "first" / "cases").rglob("*.json")):
        relative = directory.relative_to(tmp_path / "first")
        assert directory.read_bytes() == (tmp_path / "second" / relative).read_bytes()


def test_stream_pipeline_matches_legacy_candidate_geometry_timing_and_numeric_metrics(
    tmp_path: Path,
) -> None:
    result = run_benchmark(CONFIG, tmp_path / "parity", search_clock=lambda: 0.0)
    for case in result.cases:
        inputs = load_inference_input(FIXTURES / case.case_id / "inference.json")
        original_search, original_event = reconstruct_input(inputs, clock=lambda: 0.0)
        streamed = case.gaps[0]
        assert original_search.termination_reason == streamed.gap.search_result.termination_reason
        assert tuple(
            candidate.model_dump(
                exclude={"candidate_id", "start_observation_id", "end_observation_id"}
            )
            for candidate in original_search.candidates
        ) == tuple(
            candidate.model_dump(
                exclude={"candidate_id", "start_observation_id", "end_observation_id"}
            )
            for candidate in streamed.gap.search_result.candidates
        )
        assert tuple(
            hypothesis.model_dump(exclude={"hypothesis_id", "candidate_id"})
            for hypothesis in original_event.trajectories
        ) == tuple(
            hypothesis.model_dump(exclude={"hypothesis_id", "candidate_id"})
            for hypothesis in streamed.gap.event.trajectories
        )
        truth = GroundTruthTrajectory.model_validate_json(
            (FIXTURES / case.case_id / "ground_truth.json").read_text()
        )
        constraints = ConstraintConfig.model_validate_json(
            (FIXTURES / "constraints.json").read_text()
        )
        constraints = constraints.model_copy(
            update={
                "max_speed_m_s": inputs.movement.max_speed_m_s,
                "navigation_graph": inputs.navigation,
            }
        )
        original_metric = evaluate_trajectories(
            original_event.trajectories,
            truth,
            EvaluationConfig(),
            constraints=constraints,
        )
        streamed_metric = _metric(streamed)
        assert original_metric.min_ade_at_k_m == streamed_metric.min_ade_at_k_m
        assert original_metric.min_fde_at_k_m == streamed_metric.min_fde_at_k_m
        assert original_metric.coverage_at_k == streamed_metric.coverage_at_k
        assert tuple(
            metric.model_dump(exclude={"hypothesis_id", "candidate_id"})
            for metric in original_metric.trajectory_metrics
        ) == tuple(
            metric.model_dump(exclude={"hypothesis_id", "candidate_id"})
            for metric in streamed_metric.trajectory_metrics
        )


def test_benchmark_cli_runs_real_subprocess_using_generic_config(tmp_path: Path) -> None:
    output = tmp_path / "cli"
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "amidst.benchmark",
            "--config",
            str(CONFIG),
            "--output",
            str(output),
            "--no-rerun",
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=ROOT,
    )
    assert "4 cases, 4 gaps" in process.stdout
    assert str(output) in process.stdout
    assert (output / "metrics.json").is_file()
    assert not list(output.rglob("*.rrd"))


def test_benchmark_requires_fresh_output_and_preserves_existing_files(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("preserve existing benchmark outputs")
    with pytest.raises(FileExistsError, match="must be new"):
        run_benchmark(CONFIG, output)
    assert sentinel.read_text() == "preserve existing benchmark outputs"
    assert sorted(path.name for path in output.iterdir()) == ["keep.txt"]
