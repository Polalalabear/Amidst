"""Failure outputs retain evidence and expose rejection without fabricating paths."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import pytest
from pydantic import ValidationError
from rerun.chunk import RrdReader

import amidst.benchmark.runner as benchmark_runner
from amidst.benchmark.runner import run_benchmark
from amidst.graph.engine import GraphInputError
from amidst.observation.aggregation import AggregationInputError

from .benchmark_helpers import (
    BOUNDARY,
    FIXTURES,
    custom_config,
    graph_benchmark_config,
    read_json,
)


def test_disconnected_benchmark_reports_empty_metrics_and_preserves_endpoints(
    tmp_path: Path,
) -> None:
    expected = read_json(BOUNDARY / "benchmark_cases.json")["scenarios"][0]
    pipeline = read_json(FIXTURES / "stream_v1/single_path/pipeline.json")
    pipeline["topology"]["transitions"] = []
    frames = read_json(FIXTURES / "stream_v1/single_path/frames.json")
    for sample in frames["samples"]:
        if sample["visibility"] == "OBSERVED":
            sample.update(uv=[0.25, 0.75], provenance="OBSERVED", occlusion_state="CLEAR")
    config = custom_config(tmp_path / "input", pipeline=pipeline, frames=frames)
    output = tmp_path / "disconnected"
    result = run_benchmark(config, output, search_clock=lambda: 0.0, record_rerun=True)
    gap = result.cases[0].gaps[0]
    assert len(gap.gap.event.candidates) == expected["expected_candidates"]
    assert gap.gap.event.termination_reason == expected["expected_termination"]
    assert gap.gap.event.trajectories == ()
    assert gap.gap.search_result.rejection_reasons == tuple(
        expected["expected_rejected_transitions"]
    )
    assert gap.evaluation is not None
    for metrics in gap.evaluation.evaluations:
        assert metrics.selected_route_count == metrics.evaluated_hypothesis_count == 0
        assert metrics.min_ade_at_k_m is metrics.min_fde_at_k_m is None
        assert metrics.collision_rate is metrics.constraint_violation_rate is None
        assert not metrics.coverage_at_k
    summary = read_json(output / "summary.json")["cases"][0]["gaps"][0]
    assert summary["termination_reason"] == "NO_FEASIBLE_PATH"
    assert summary["rejection_reasons"] == ["NO_FEASIBLE_AUTHORIZED_ROUTE"]
    assert summary["endpoint_camera_ids"] == ["CAM_A", "CAM_B"]
    markdown = (output / "summary.md").read_text()
    assert "NO_FEASIBLE_PATH" in markdown and "NO_FEASIBLE_AUTHORIZED_ROUTE" in markdown
    assert "CAM_A" in markdown and "CAM_B" in markdown
    assert gap.rerun_artifact is not None
    paths = {chunk.entity_path for chunk in RrdReader(output / gap.rerun_artifact).stream()}
    assert sum("/projected/" in path for path in paths) == 2
    assert sum("/observed/" in path for path in paths) == 2
    assert not any("/candidates/" in path or "/hypotheses/" in path for path in paths)


def test_no_ground_truth_benchmark_completes_inference_and_reports_unavailable(
    tmp_path: Path,
) -> None:
    config = custom_config(tmp_path / "input", base_case="branching_top_k", no_truth=True)
    output = tmp_path / "no-reference"
    result = run_benchmark(config, output, search_clock=lambda: 0.0)
    gap = result.cases[0].gaps[0]
    assert len(gap.gap.event.candidates) == 3 and gap.gap.event.trajectories
    assert gap.gap.event.termination_reason == "COMPLETE"
    assert gap.evaluation is None
    row = read_json(output / "summary.json")["cases"][0]["gaps"][0]
    assert row["evaluation_status"] == "NO_REFERENCE" and row["metrics_at_k"] == []
    assert list(read_json(output / "metrics.json")["branching_top_k"].values()) == [None]
    assert "NO_REFERENCE" in (output / "summary.md").read_text()


def test_duplicate_input_keeps_original_exception_and_writes_rejection_report(
    tmp_path: Path,
) -> None:
    frames = read_json(FIXTURES / "stream_v1/single_path/frames.json")
    frames["samples"].append(frames["samples"][0])
    config = custom_config(tmp_path / "input", frames=frames)
    output = tmp_path / "rejected"
    with pytest.raises(AggregationInputError, match="duplicate"):
        run_benchmark(config, output, search_clock=lambda: 0.0)
    summary = read_json(output / "summary.json")
    assert summary["status"] == "INPUT_REJECTED"
    assert summary["termination_reason"] is None
    assert summary["error"]["type"] == "AggregationInputError"
    assert "duplicate" in summary["error"]["message"]
    assert summary["cases"][0]["case_id"] == "single_path"
    assert summary["cases"][0]["gaps"] == []
    assert read_json(output / "metrics.json") == {"status": "NOT_RUN"}
    assert not list(output.rglob("candidates.json"))
    assert not (output / "artifacts.json").exists()


def test_invalid_frame_schema_is_reported_before_inference(tmp_path: Path) -> None:
    frames = read_json(FIXTURES / "stream_v1/single_path/frames.json")
    frames["samples"][0]["uv"] = [-0.1, 0.5]
    config = custom_config(tmp_path / "input", frames=frames)
    output = tmp_path / "invalid-uv"
    with pytest.raises(ValidationError, match="PROJECTED-only"):
        run_benchmark(config, output)
    summary = read_json(output / "summary.json")
    assert summary["status"] == "INPUT_REJECTED"
    assert summary["stage"] == "CASE_INFERENCE"
    assert summary["error"]["type"] == "ValidationError"
    assert summary["error"]["message"]
    assert "INPUT_REJECTED" in (output / "summary.md").read_text()


def test_graph_input_failure_code_is_preserved_in_rejection_report(tmp_path: Path) -> None:
    frames = read_json(FIXTURES / "stream_v1/single_path/frames.json")
    frames["samples"][0]["projected_point"]["world_position"] = [999, 0, 0]
    config = custom_config(tmp_path / "input", frames=frames)
    output = tmp_path / "off-network"
    with pytest.raises(GraphInputError) as rejected:
        run_benchmark(config, output)
    assert rejected.value.failure == "ENDPOINT_OFF_NETWORK"
    assert read_json(output / "summary.json")["error"]["failure"] == "ENDPOINT_OFF_NETWORK"


@pytest.mark.parametrize("error_type", [RuntimeError, ValueError])
def test_unexpected_runtime_error_propagates_without_false_rejection_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error_type: type[Exception],
) -> None:
    config = custom_config(tmp_path / "input", no_truth=True)
    output = tmp_path / "unexpected"

    def broken(*args: object, **kwargs: object) -> None:
        raise error_type("unexpected consumer defect")

    monkeypatch.setattr(benchmark_runner, "reconstruct_gaps", broken)
    with pytest.raises(error_type, match="unexpected consumer defect"):
        run_benchmark(config, output)
    assert not output.exists()


def test_benchmark_metrics_and_rerun_use_only_formal_top_k(tmp_path: Path) -> None:
    config = graph_benchmark_config(tmp_path / "input", "eight_routes_k3")
    output = tmp_path / "top-three"
    result = run_benchmark(config, output, search_clock=lambda: 0.0, record_rerun=True)
    gap = result.cases[0].gaps[0]
    assert gap.gap.event.termination_reason == "MAX_PATHS_REACHED"
    assert [candidate.navmesh_corridor for candidate in gap.gap.event.candidates] == [
        ("route_a",), ("route_b",), ("route_c",),
    ]
    formal_ids = {candidate.candidate_id for candidate in gap.gap.event.candidates}
    assert {trajectory.candidate_id for trajectory in gap.gap.event.trajectories} == formal_ids
    assert gap.evaluation is not None
    for evaluation in gap.evaluation.evaluations:
        assert evaluation.selected_route_count == min(evaluation.config.k_routes, 3)
        assert {metric.candidate_id for metric in evaluation.trajectory_metrics} == formal_ids
    assert gap.rerun_artifact is not None
    paths = {
        unquote(chunk.entity_path.replace("\\", ""))
        for chunk in RrdReader(output / gap.rerun_artifact).stream()
    }
    candidate_paths = {
        path for path in paths if path.startswith("/world/") and "/candidates/" in path
    }
    assert len(candidate_paths) == 3
    for candidate_id in formal_ids:
        assert any(candidate_id in path for path in candidate_paths)
