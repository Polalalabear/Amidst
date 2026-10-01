"""Replayable unified benchmark command and source-independent consumer parity."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from rerun.chunk import RrdReader

import amidst.benchmark.runner as benchmark_runner
import amidst.experiments.versioning as experiment_versioning
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
    directory: Path,
    *,
    case_ids: tuple[str, ...] = ("single_path",),
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


def test_runner_applies_external_metric_config_for_every_requested_k(tmp_path: Path) -> None:
    result = run_benchmark(CONFIG, tmp_path / "multi-k", search_clock=lambda: 0.0)
    for case in result.cases:
        evaluation = case.gaps[0].evaluation
        assert evaluation is not None
        assert (
            evaluation.metric_config.metric_config_version
            == result.record.config.metric_config_version
        )
        assert evaluation.metric_config.formal_benchmark_status == "UNRESOLVED"
        assert tuple(metric.config.k_routes for metric in evaluation.evaluations) == (1, 2, 3)
        assert evaluation.for_k(3).coverage_at_k
        if case.case_id == "branching_top_k":
            assert not evaluation.for_k(1).coverage_at_k
            assert not evaluation.for_k(2).coverage_at_k
    persisted = json.loads((tmp_path / "multi-k" / "metrics.json").read_text())
    for gap in persisted["branching_top_k"].values():
        assert gap["metric_config"]["coverage_epsilon_m"] == 1e-6
        assert [metric["config"]["k_routes"] for metric in gap["evaluations"]] == [1, 2, 3]


def test_metric_config_version_mismatch_fails_before_outputs(tmp_path: Path) -> None:
    config = _custom_config(
        tmp_path / "input", config_updates={"metric_config_version": "wrong-version"}
    )
    output = tmp_path / "wrong-version"
    with pytest.raises(ValueError, match="version"):
        run_benchmark(config, output)
    assert not output.exists()


def test_ground_truth_is_not_read_until_all_cases_finish_inference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed: list[str] = []
    truth_reads: list[Path] = []
    original_reconstruct = benchmark_runner.reconstruct_gaps
    original_open = experiment_versioning.os.open

    def reconstruct(*args: Any, **kwargs: Any) -> Any:
        result = original_reconstruct(*args, **kwargs)
        completed.append(kwargs["dataset_id"])
        return result

    def open_path(path: Any, *args: Any, **kwargs: Any) -> Any:
        source = Path(path)
        if source.name == "ground_truth.json":
            assert len(completed) == 4, (
                "reference geometry was read before every case completed inference"
            )
            truth_reads.append(source)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(benchmark_runner, "reconstruct_gaps", reconstruct)
    monkeypatch.setattr(experiment_versioning.os, "open", open_path)
    run_benchmark(CONFIG, tmp_path / "late-truth", search_clock=lambda: 0.0)
    assert len(set(completed)) == 4
    assert len({path.parent.name for path in truth_reads}) == 4


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_id", "different-target"),
        ("scene_id", "different-context"),
        ("source_asset_sha256", "f" * 64),
        ("random_seed", 123),
    ],
)
def test_wrong_ground_truth_binding_fails_in_evaluation_without_publishing_summary(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    truth = json.loads((FIXTURES / "single_path" / "ground_truth.json").read_text())
    truth[field] = value
    config = _custom_config(tmp_path / "input", truth=truth)
    output = tmp_path / "wrong-truth"
    with pytest.raises(ValueError, match="exactly one evaluation reference"):
        run_benchmark(config, output, search_clock=lambda: 0.0)
    assert not (output / "summary.json").exists()
    assert not (output / "metrics.json").exists()


def test_missing_and_hash_mismatched_reference_files_fail_explicitly(tmp_path: Path) -> None:
    missing = tmp_path / "missing-ground-truth.json"
    config = _custom_config(
        tmp_path / "missing-input",
        case_updates={
            "evaluation_references": [{"path": str(missing), "sha256": "f" * 64}],
        },
    )
    with pytest.raises(FileNotFoundError):
        run_benchmark(config, tmp_path / "missing-result", search_clock=lambda: 0.0)
    truth_path = FIXTURES / "single_path" / "ground_truth.json"
    config = _custom_config(
        tmp_path / "mismatch-input",
        case_updates={
            "evaluation_references": [{"path": str(truth_path), "sha256": "f" * 64}],
        },
    )
    with pytest.raises(ValueError, match="hash mismatch"):
        run_benchmark(config, tmp_path / "mismatch-result", search_clock=lambda: 0.0)


def test_ambiguous_references_and_missing_exact_time_boundaries_are_rejected(
    tmp_path: Path,
) -> None:
    reference = _reference(FIXTURES / "single_path" / "ground_truth.json")
    config = _custom_config(
        tmp_path / "ambiguous-input",
        case_updates={
            "evaluation_references": [reference, reference],
        },
    )
    with pytest.raises(ValueError, match="exactly one evaluation reference"):
        run_benchmark(config, tmp_path / "ambiguous-result", search_clock=lambda: 0.0)
    truth = json.loads((FIXTURES / "single_path" / "ground_truth.json").read_text())
    truth["samples"][0]["timestamp"] = 9.0
    config = _custom_config(tmp_path / "boundary-input", truth=truth)
    with pytest.raises(ValueError, match="exact gap boundaries"):
        run_benchmark(config, tmp_path / "boundary-result", search_clock=lambda: 0.0)


def test_empty_frame_stream_produces_zero_gaps_and_clear_summary(tmp_path: Path) -> None:
    config = _custom_config(
        tmp_path / "empty-input", frames={"schema_version": "1.0", "samples": []}
    )
    output = tmp_path / "empty-result"
    result = run_benchmark(config, output, search_clock=lambda: 0.0)
    assert len(result.cases) == 1
    assert result.cases[0].aggregation.samples == result.cases[0].aggregation.observations == ()
    assert result.cases[0].gaps == ()
    summary = json.loads((output / "summary.json").read_text())
    assert summary["cases"][0]["gap_count"] == 0
    assert json.loads((output / "metrics.json").read_text()) == {"single_path": {}}


def test_inference_only_benchmark_keeps_metrics_explicitly_unevaluated(tmp_path: Path) -> None:
    config = _custom_config(
        tmp_path / "no-reference-input",
        case_updates={
            "evaluation_references": [],
        },
    )
    output = tmp_path / "no-reference-result"
    result = run_benchmark(config, output, search_clock=lambda: 0.0)
    gap = result.cases[0].gaps[0]
    assert len(gap.gap.event.candidates) == 1
    assert gap.evaluation is None
    metrics = json.loads((output / "metrics.json").read_text())
    assert metrics == {"single_path": {gap.gap.event.event_id: None}}
    summary = json.loads((output / "summary.json").read_text())
    assert summary["cases"][0]["gaps"][0]["evaluation_status"] == "NO_REFERENCE"
    assert summary["cases"][0]["gaps"][0]["metrics_at_k"] == []


def test_multi_gap_runner_slices_truth_at_exact_independent_event_boundaries(
    tmp_path: Path,
) -> None:
    frames = json.loads((FIXTURES / "stream_v1" / "single_path" / "frames.json").read_text())
    end_sample = next(sample for sample in frames["samples"] if sample["camera_id"] == "CAM_B")
    recovered = json.loads(json.dumps(end_sample))
    recovered.update(sample_id="recovered:B", frame_id=2, timestamp=40.0)
    recovered["projected_point"].update(point_id="recovered:B:point", timestamp=40.0)
    missing = json.loads(
        json.dumps(next(sample for sample in frames["samples"] if sample["visibility"] == "GAP"))
    )
    missing.update(sample_id="second:gap", camera_id="CAM_B", frame_id=1, timestamp=35.0)
    frames["samples"].extend((recovered, missing))
    truth = json.loads((FIXTURES / "single_path" / "ground_truth.json").read_text())
    final = truth["samples"][-1]
    for timestamp in (35.0, 40.0):
        sample = json.loads(json.dumps(final))
        sample.update(timestamp=timestamp, velocity=[0.0, 0.0, 0.0])
        truth["samples"].append(sample)
    config = _custom_config(tmp_path / "multi-input", frames=frames, truth=truth)
    result = run_benchmark(config, tmp_path / "multi-result", search_clock=lambda: 0.0)
    first, second = result.cases[0].gaps
    assert first.gap.event.time_range == (10, 30)
    assert second.gap.event.time_range == (30, 40)
    assert first.gap.end.observation.observation_id == second.gap.start.observation.observation_id
    assert first.gap.event.event_id != second.gap.event.event_id
    assert _metric(first).coverage_at_k and _metric(second).coverage_at_k
    assert (
        _metric(first).trajectory_metrics[0].ground_truth_sample_count == len(truth["samples"]) - 2
    )
    assert _metric(second).trajectory_metrics[0].ground_truth_sample_count == 3


@pytest.mark.parametrize("case_id", ["..", "../escape", "nested/name"])
def test_untrusted_case_identifiers_cannot_escape_output_directory(
    tmp_path: Path, case_id: str
) -> None:
    config = _custom_config(tmp_path / "safe-input", case_updates={"case_id": case_id})
    output = tmp_path / "safe-result"
    result = run_benchmark(config, output, record_rerun=True, search_clock=lambda: 0.0)
    assert result.cases[0].case_id == case_id
    relative = result.cases[0].gaps[0].rerun_artifact
    assert relative is not None
    assert (output / relative).resolve().is_relative_to(output.resolve())
    assert (output / relative).is_file()
    assert all(path.resolve().is_relative_to(output.resolve()) for path in output.rglob("*"))
    assert not (tmp_path / "escape").exists()


@pytest.mark.parametrize("debug_ground_truth", [False, True])
def test_optional_rerun_artifacts_are_readable_and_truth_overlay_is_opt_in(
    tmp_path: Path,
    debug_ground_truth: bool,
) -> None:
    output = tmp_path / "recording"
    result = run_benchmark(
        CONFIG,
        output,
        record_rerun=True,
        debug_ground_truth=debug_ground_truth,
        search_clock=lambda: 0.0,
    )
    for case in result.cases:
        relative = case.gaps[0].rerun_artifact
        assert relative is not None
        path = output / relative
        assert path.stat().st_size > 1024
        reader = RrdReader(path)
        assert len(reader.recordings()) == 1
        assert len(reader.store()) > 0
        paths = {chunk.entity_path for chunk in reader.stream()}
        assert any("/hypotheses/" in name and name.endswith("/marker") for name in paths)
        assert any("debug_ground_truth" in name for name in paths) is debug_ground_truth
