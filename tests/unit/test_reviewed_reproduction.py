"""Fresh comparison excludes clocks without masking semantic/count changes."""

import json
from pathlib import Path

from amidst.finalization.reviewed_reproduction import _canonical, _markdown


def test_runtime_values_excluded_counts_and_availability_retained(tmp_path: Path) -> None:
    first = {"runtime_s": {"mean": .1, "count": 2}, "ade_m": .4, "termination": "COMPLETE"}
    second = {"runtime_s": {"mean": .2, "count": 2}, "ade_m": .4, "termination": "COMPLETE"}
    assert _canonical(first, tmp_path) == _canonical(second, tmp_path)
    second["runtime_s"]["count"] = 3  # type: ignore[index]
    assert _canonical(first, tmp_path) != _canonical(second, tmp_path)
    assert _canonical({"runtime_s": None}, tmp_path) != _canonical({"runtime_s": .1}, tmp_path)
    assert _canonical({"max_search_time_s": 1}, tmp_path) != (
        _canonical({"max_search_time_s": 2}, tmp_path)
    )
    assert _canonical({"runtime_s": {"mean": .1, "available_runs": 1}}, tmp_path) != (
        _canonical({"runtime_s": {"mean": .2, "available_runs": 2}}, tmp_path)
    )


def test_output_root_normalized_without_erasing_other_paths(tmp_path: Path) -> None:
    assert _canonical(str(tmp_path / "comparison.json"), tmp_path) == (
        "<EVALUATION>/comparison.json"
    )
    assert _canonical("reviewed_route:case1:direct", tmp_path) == "reviewed_route:case1:direct"
    assert _canonical(["candidate_b", "candidate_a"], tmp_path) != (
        _canonical(["candidate_a", "candidate_b"], tmp_path)
    )


def test_markdown_runtime_column_only(tmp_path: Path) -> None:
    first, second = tmp_path / "one.md", tmp_path / "two.md"
    header = "| Case | ADE (m) | Runtime (s) |\n| --- | --- | --- |\n"
    first.write_text(header + "| case1 | 0.4 | 0.1 |\n| case2 | N/A | N/A |\n")
    second.write_text(header + "| case1 | 0.4 | 0.2 |\n| case2 | N/A | N/A |\n")
    assert _markdown(first, tmp_path) == _markdown(second, tmp_path)
    second.write_text(header + "| case1 | 0.5 | 0.2 |\n| case2 | N/A | N/A |\n")
    assert _markdown(first, tmp_path) != _markdown(second, tmp_path)


def test_semantic_changes_and_na_not_removed(tmp_path: Path) -> None:
    value = json.loads('{"coverage_at_k":null,"candidate_count":0,"physical_scope":"office"}')
    canonical = _canonical(value, tmp_path)
    assert canonical == value
    assert canonical != _canonical(value | {"coverage_at_k": False}, tmp_path)


def test_relative_demo_locations_normalized_without_changing_route_strings(tmp_path: Path) -> None:
    local = tmp_path / "repo" / "data/local/evaluation"
    fresh = tmp_path / "fresh" / "data/fresh/evaluation"
    a = {"recording": "data/local/evaluation/demos/case1/reviewed.rrd"}
    b = {"recording": "data/fresh/evaluation/demos/case1/reviewed.rrd"}
    assert _canonical(a, local) == _canonical(b, fresh)
    assert _canonical({"navmesh_corridor": a["recording"]}, local) != (
        _canonical({"navmesh_corridor": b["recording"]}, fresh)
    )
    assert _canonical({"recording": "/outside/evaluation/demo.rrd"}, local) == {
        "recording": "/outside/evaluation/demo.rrd"
    }
