"""Comparison plots preserve provenance, ordering, measurement availability and failures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from amidst.benchmark_report import (
    SCHEMA,
    LoadedComparison,
    ReportRun,
    generate_comparison,
    load_comparison,
    main,
    summarize,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests/fixtures/benchmark_report_comparison.json"


def _write(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _evaluation(*, no_candidates: bool = False) -> dict[str, Any]:
    return {
        "metric_config": {"coverage_epsilon_m": 0.01, "formal_benchmark_status": "UNRESOLVED"},
        "evaluations": [
            {
                "config": {"k_routes": k, "benchmark_kind": "SYNTHETIC_TEST_FIXTURE"},
                "top_k_hypothesis_ids": [] if no_candidates else ["first", "best"],
                "trajectory_metrics": [] if no_candidates else [
                    {"hypothesis_id": "best", "ade_m": 0.0, "fde_m": 0.0},
                    {"hypothesis_id": "first", "ade_m": 2.0, "fde_m": 1.0},
                ],
                "min_ade_at_k_m": None if no_candidates else 0.0,
                "min_fde_at_k_m": None if no_candidates else 0.0,
                "coverage_at_k": not no_candidates and k > 1,
                "collision_rate": None if no_candidates else 0.25,
                "constraint_violation_rate": None if no_candidates else 0.5,
                "total_segment_count": 0 if no_candidates else 4,
                "collision_segment_count": 0 if no_candidates else 1,
                "constraint_violation_segment_count": 0 if no_candidates else 2,
            } for k in (1, 2, 3)
        ],
    }


def _native(root: Path) -> Path:
    _write(root / "metrics.json", {
        "case1": {"gap1": _evaluation()},
        "no_reference": {"gap2": None},
        "empty": {"gap3": _evaluation(no_candidates=True)},
    })
    _write(root / "summary.json", {"cases": [
        {"case_id": "case1", "inference_runtime_s": 0.1, "gaps": [{
            "event_id": "gap1", "candidates": 2, "expanded_nodes": 5,
            "termination_reason": "COMPLETE", "evaluation_status": "EVALUATED",
        }]},
        {"case_id": "no_reference", "inference_runtime_s": 0.2, "gaps": [{
            "event_id": "gap2", "candidates": 1, "expanded_nodes": 2,
            "termination_reason": "COMPLETE", "evaluation_status": "NO_REFERENCE",
        }]},
        {"case_id": "empty", "inference_runtime_s": 0.3, "gaps": [{
            "event_id": "gap3", "candidates": 0, "expanded_nodes": 3,
            "termination_reason": "NO_FEASIBLE_PATH", "evaluation_status": "EVALUATED",
        }]},
    ]})
    _write(root / "experiment.json", {"dataset": {"data_kind": "SYNTHETIC"}})
    return root


def test_native_parsing_keeps_primary_route_order_and_missing_references(tmp_path: Path) -> None:
    loaded = load_comparison(_native(tmp_path / "native"))
    first, missing, empty = loaded.runs
    assert first.metrics["ade_m"] == 2.0  # not the truth-optimal hypothesis
    assert first.metrics["min_ade_at_k_m"] == 0.0
    assert first.coverage_at_k == {1: 0.0, 2: 1.0, 3: 1.0}
    assert first.metrics["runtime_s"] == 0.1
    assert first.metrics["search_nodes"] == 5
    assert missing.status == "NO_REFERENCE"
    assert missing.benchmark_label == "SYNTHETIC REGRESSION"
    assert not missing.coverage_at_k and missing.metrics["ade_m"] is None
    assert empty.status == "NO_FEASIBLE_PATH"
    assert empty.metrics["candidate_count"] == 0
    assert empty.metrics["ade_m"] is None
    assert empty.coverage_at_k[3] == 0


def test_native_plotting_safe_for_empty_and_no_reference_cases(tmp_path: Path) -> None:
    summary = generate_comparison(_native(tmp_path / "native"), tmp_path / "report")
    assert summary["benchmark_label"] == "SYNTHETIC REGRESSION"
    assert "coverage_at_k.png" in summary["generated_charts"]
    assert "physical_validity.png" in summary["generated_charts"]
    assert "termination_categories.png" in summary["generated_charts"]
    assert "travel_time_error.png" in summary["skipped_charts"]
    markdown = (tmp_path / "report/benchmark_summary.md").read_text()
    assert "NO_REFERENCE" in markdown and "NO_FEASIBLE_PATH" in markdown and "N/A" in markdown


def test_fixture_multicase_multimethod_aggregation_and_all_chart_types(tmp_path: Path) -> None:
    summary = generate_comparison(FIXTURE, tmp_path / "report")
    assert summary["benchmark_label"] == "MOCK VALIDATION"
    assert len(summary["rows"]) == 7 * 3
    assert summary["methods"] == ["shortest_path", "geometry", "spatiotemporal"]
    row = summary["rows"][0]
    assert row["metrics"]["ade_m"] == {"mean": 2.0, "available_runs": 2, "total_runs": 2}
    assert row["metrics"]["collision_rate"]["mean"] == 0
    assert row["metrics"]["collision_rate"]["available_runs"] == 1
    assert row["coverage_at_k"]["1"]["mean"] == 0.5
    assert "path_length_error.png" in summary["generated_charts"]
    assert "travel_time_error.png" in summary["generated_charts"]
    assert "impossible_transition_rate.png" in summary["generated_charts"]
    assert not summary["skipped_charts"]
    for name in summary["generated_charts"]:
        assert (tmp_path / "report" / name).read_bytes().startswith(b"\x89PNG")
    persisted = json.loads((tmp_path / "report/benchmark_summary.json").read_text())
    assert persisted == summary
    assert "INPUT_REJECTED" in (tmp_path / "report/benchmark_summary.md").read_text()


def test_native_physical_rates_pool_counts_and_search_sums_without_runtime_double_count(
    tmp_path: Path,
) -> None:
    directory = _native(tmp_path / "native")
    metrics = json.loads((directory / "metrics.json").read_text())
    second = _evaluation()
    for value in second["evaluations"]:
        value.update(total_segment_count=6, collision_segment_count=0,
                     constraint_violation_segment_count=0, collision_rate=0.0,
                     constraint_violation_rate=0.0)
    metrics["case1"]["gap4"] = second
    _write(directory / "metrics.json", metrics)
    summary = json.loads((directory / "summary.json").read_text())
    summary["cases"][0]["gaps"].append({
        "event_id": "gap4", "candidates": 1, "expanded_nodes": 7,
        "termination_reason": "COMPLETE", "evaluation_status": "EVALUATED",
    })
    _write(directory / "summary.json", summary)
    loaded = load_comparison(directory)
    first = loaded.runs[0]
    assert first.metrics["collision_rate"] == 0.1  # 1/10, not mean(.25, 0)
    assert first.metrics["constraint_violation_rate"] == 0.2
    assert first.metrics["search_nodes"] == 12
    assert first.metrics["candidate_count"] == 1.5
    assert first.metrics["runtime_s"] == 0.1
    row = summarize(loaded)["rows"][0]
    assert row["metrics"]["collision_rate"]["aggregation"] == "POOLED_SEGMENT_RATE"
    assert row["metrics"]["collision_rate"]["denominator"] == 10
    assert row["gap_availability"]["native"]["ade_m"]["available_gaps"] == 2


def test_unmeasured_failed_case_generates_summary_without_fabricated_charts(tmp_path: Path) -> None:
    _write(tmp_path / "failed/metrics.json", {"status": "NOT_RUN"})
    _write(tmp_path / "failed/summary.json", {
        "status": "INPUT_REJECTED", "cases": [{"case_id": "failed", "gaps": []}],
    })
    summary = generate_comparison(tmp_path / "failed", tmp_path / "report")
    assert summary["rows"][0]["status_counts"] == {"INPUT_REJECTED": 1}
    assert summary["rows"][0]["metrics"]["candidate_count"]["mean"] is None
    assert not summary["generated_charts"]
    assert summary["skipped_charts"]
    assert summary["benchmark_label"] == "UNVERIFIED INPUT"


def test_unknown_and_unapproved_formal_provenance_never_become_research(tmp_path: Path) -> None:
    for name, provenance in [
        ("unknown", {}),
        ("unapproved", {"benchmark_kind": "BLENDER_RESEARCH_RESULT"}),
    ]:
        path = _write(tmp_path / f"{name}.json", {"schema_version": SCHEMA,
            "provenance": provenance, "runs": [{"case_id": "case1", "method_id": "geometry",
                "run_id": "1", "status": "COMPLETE", "metrics": {"ade_m": 0}}]})
        assert load_comparison(path).runs[0].benchmark_label == "UNVERIFIED INPUT"


def test_declared_missing_cases_are_visible_and_invalid_values_become_na(tmp_path: Path) -> None:
    source = _write(tmp_path / "comparison.json", {"schema_version": SCHEMA,
        "cases": ["case1", "missing"], "methods": ["shortest_path", "geometry"],
        "provenance": {"benchmark_kind": "MOCK_VALIDATION"}, "runs": [
            {"case_id": "case1", "method_id": "geometry", "metrics": {
                "ade_m": -1, "collision_rate": 2, "runtime_s": "missing"},
             "coverage_at_k": {"0": 0, "1": 2, "2": None}},
        ]})
    summary = summarize(load_comparison(source))
    assert len(summary["rows"]) == 4
    assert summary["rows"][0]["status_counts"] == {"MISSING_RUN": 1}
    assert summary["rows"][1]["metrics"]["ade_m"]["mean"] is None
    assert summary["rows"][1]["coverage_at_k"]["1"]["mean"] is None
    assert "0" not in summary["rows"][1]["coverage_at_k"]
    assert summary["rows"][1]["warnings"]


def test_case_method_tree_and_cli_entrypoint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    _native(tmp_path / "inputs/case1/shortest_path/run1")
    _native(tmp_path / "inputs/case1/geometry/run1")
    loaded = load_comparison(tmp_path / "inputs")
    assert {run.method_id for run in loaded.runs} == {"geometry", "shortest_path"}
    assert main(["--input", str(tmp_path / "inputs"), "--output", str(tmp_path / "report")]) == 0
    assert "SYNTHETIC REGRESSION" in capsys.readouterr().out


def test_mixed_k_minimum_metrics_are_not_silently_averaged() -> None:
    rows = [ReportRun("case1", "geometry", str(k), "test", "COMPLETE", "MOCK VALIDATION",
                      metrics={"min_ade_at_k_m": 0.1}, selected_k=k) for k in (1, 3)]
    summary = summarize(LoadedComparison(tuple(rows)))
    row = summary["rows"][0]
    assert row["metrics"]["min_ade_at_k_m"]["mean"] is None
    assert row["selected_k"] is None
    assert any("K differs" in message for message in row["warnings"])


def test_rejects_duplicate_run_identity_and_preserves_existing_output(tmp_path: Path) -> None:
    run = {"case_id": "case1", "method_id": "geometry", "run_id": "1"}
    source = _write(tmp_path / "comparison.json", {"schema_version": SCHEMA, "runs": [run, run]})
    with pytest.raises(ValueError, match="duplicate"):
        load_comparison(source)
    output = tmp_path / "report"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("preserve")
    with pytest.raises(FileExistsError, match="new or empty"):
        generate_comparison(FIXTURE, output)
    assert sentinel.read_text() == "preserve"


def test_incompatible_invariant_settings_suppress_aggregate_to_na() -> None:
    runs = tuple(ReportRun(
        "case1", "geometry", str(seed), "test", "COMPLETE", "MOCK VALIDATION",
        metrics={"ade_m": float(seed)}, coverage_at_k={3: 1.0}, selected_k=3,
        settings={"seed": seed},
    ) for seed in (1, 2))
    summary = summarize(LoadedComparison(runs))
    row = summary["rows"][0]
    assert row["metrics"]["ade_m"]["mean"] is None
    assert row["coverage_at_k"]["3"]["mean"] is None
    assert any("suppressed" in message for message in row["warnings"])
    assert summary["comparison_warnings"]


def test_numeric_bool_is_missing_but_coverage_bool_remains_an_indicator(tmp_path: Path) -> None:
    source = _write(tmp_path / "input.json", {"schema_version": SCHEMA,
        "provenance": {"benchmark_kind": "MOCK_VALIDATION"}, "runs": [{
            "case_id": "case", "method_id": "geometry", "metrics": {"ade_m": False},
            "coverage_at_k": {"1": False, "2": True},
        }]})
    run = load_comparison(source).runs[0]
    assert run.metrics["ade_m"] is None
    assert run.coverage_at_k == {1: 0.0, 2: 1.0}
    assert run.warnings


def test_categories_preserve_measurement_availability_without_acceptance_claim() -> None:
    row = summarize(load_comparison(FIXTURE))["rows"][0]
    categories = row["acceptance_categories"]
    assert len(categories) == 6
    assert all(value["acceptance"] == "NOT_ASSESSED" for value in categories.values())
    assert categories["GEOMETRIC_ACCURACY"]["measurement_status"] == "MEASUREMENTS_AVAILABLE"
    assert categories["SYSTEM_RUNTIME"]["available_metrics"] == ["runtime_s"]


def test_incompatible_native_gap_settings_suppress_case_aggregate(tmp_path: Path) -> None:
    directory = _native(tmp_path / "native")
    metrics = json.loads((directory / "metrics.json").read_text())
    second = _evaluation()
    second["metric_config"]["coverage_epsilon_m"] = 0.3
    metrics["case1"]["gap4"] = second
    _write(directory / "metrics.json", metrics)
    summary = json.loads((directory / "summary.json").read_text())
    summary["cases"][0]["gaps"].append({
        "event_id": "gap4", "candidates": 1, "expanded_nodes": 7,
        "termination_reason": "COMPLETE", "evaluation_status": "EVALUATED",
    })
    _write(directory / "summary.json", summary)
    first = load_comparison(directory).runs[0]
    assert first.metrics["ade_m"] is None
    assert first.coverage_at_k[3] is None
    assert any("suppressed" in message for message in first.warnings)
    assert len(first.settings["metric_config"]["incompatible_gap_metric_configs"]) == 2


def test_physical_rate_aggregation_pools_segments_across_independent_runs() -> None:
    first = ReportRun("case", "geometry", "1", "test", "COMPLETE", "MOCK VALIDATION",
                      metrics={"collision_rate": 0.5}, physical_counts={"collision_rate": (1, 2)})
    second = ReportRun("case", "geometry", "2", "test", "COMPLETE", "MOCK VALIDATION",
                       metrics={"collision_rate": 0.0}, physical_counts={"collision_rate": (0, 8)})
    row = summarize(LoadedComparison((first, second)))["rows"][0]
    assert row["metrics"]["collision_rate"]["mean"] == 0.1
    assert row["metrics"]["collision_rate"]["denominator"] == 10
