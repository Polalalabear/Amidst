"""Robustness displays preserve accepted prefixes and fail closed on rejected inputs."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from rerun.chunk import RrdReader

from amidst.domain.stream import BoundGapEvent


def import_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]
VIS = import_script(ROOT / "scripts" / "visualize_pilot_robustness.py", "robustness_visualization")
FIXTURE = import_script(
    ROOT / "tests" / "unit" / "test_pilot_downstream_visualization.py", "existing_saved_vis_fixture"
)


@pytest.fixture
def inputs():
    return FIXTURE.inputs.__wrapped__()


def status(*, failed_stage: str | None, artifacts: list[str]) -> dict:
    validated = failed_stage != "INPUT_CONTEXT"
    return {
        "label": VIS.LABEL,
        "scenario_id": "PILOT_TEST",
        "outcome": "EXPECTED_FAILURE",
        "failed_stage": failed_stage,
        "reason": "TEST_DIAGNOSTIC",
        "termination_reason": "NOT_RUN",
        "evaluation_eligible": False,
        "stage_states": {"INPUT_CONTEXT": "PASSED" if validated else "FAILED"},
        "available_artifacts": artifacts,
        "binding_validated": validated,
        "physical_validity": "PROVISIONAL",
        "candidate_count_state": "NOT_RUN",
        **(
            {
                "source_asset_sha256": FIXTURE.SOURCE_SHA,
                "source_id": "PILOT_TEST",
                "spatial_context_id": "pilot_context",
                "target_id": "pilot_target",
                "site_id": "test",
            }
            if validated
            else {"untrusted_binding": {"source_asset_sha256": "b" * 64}}
        ),
    }


def save(runroot: Path, metadata: dict, inputs: tuple, *, full: bool) -> None:
    runroot.mkdir()
    (runroot / "robustness_status.json").write_text(json.dumps(metadata))
    (runroot / "aggregation.json").write_text(
        json.dumps(
            {
                "label": VIS.LABEL,
                "aggregation": inputs[0].model_dump(mode="json"),
            }
        )
    )
    if full:
        (runroot / "pipeline_config.json").write_text(
            json.dumps(
                {
                    "label": VIS.LABEL,
                    "pipeline": inputs[1].model_dump(mode="json"),
                }
            )
        )
        (runroot / "gap_events.json").write_text(
            json.dumps(
                {
                    "label": VIS.LABEL,
                    "gaps": [g.model_dump(mode="json") for g in inputs[2]],
                }
            )
        )


def native_truth(path: Path, *, source: str = FIXTURE.SOURCE_SHA, site: str = "test") -> None:
    path.write_text(
        json.dumps(
            {
                "label": VIS.LABEL,
                "provenance": "GROUND_TRUTH",
                "source_asset_sha256": source,
                "site_id": site,
                "trajectory_id": "truth_debug",
                "samples": [
                    {
                        "timestamp": index,
                        "position": [index * 2, 0, 0],
                        "floor_id": "1F",
                        "trajectory_id": "truth_debug",
                        "provenance": "GROUND_TRUTH",
                    }
                    for index in range(6)
                ],
            }
        )
    )


def test_rejected_context_does_not_open_pixels_aggregation_or_gt(
    inputs: tuple,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runroot, truth = tmp_path / "run_01", tmp_path / "ground_truth.json"
    save(
        runroot,
        status(failed_stage="INPUT_CONTEXT", artifacts=["aggregation.json"]),
        inputs,
        full=False,
    )
    truth.write_text("poison: rejected-input scenario must never open truth")
    original = VIS.read_labeled
    opened = []

    def guarded(path: Path) -> dict:
        opened.append(path.name)
        if path.name in {"ground_truth.json", "aggregation.json"}:
            raise AssertionError("rejected evidence was read")
        return original(path)

    monkeypatch.setattr(VIS, "read_labeled", guarded)
    manifest = VIS.create_visualization(runroot, truth)
    assert opened == ["robustness_status.json"]
    assert not manifest["gt_overlay_enabled"]
    assert manifest["counts"] == {
        "candidates": 0,
        "hypotheses": 0,
        "projected_samples": 0,
        "gt_samples": 0,
    }
    core = json.loads((runroot / "visualization" / "presentation.json").read_text())
    assert core["source_asset_sha256"] is None
    assert not core["binding_validated"]
    paths = {c.entity_path for c in RrdReader(runroot / "visualization" / "debug.rrd").stream()}
    assert "/debug/scenario_status" in paths
    assert not any("observed" in p or "inferred" in p or "ground_truth" in p for p in paths)


def test_topology_failure_retains_only_accepted_observed_and_independent_gt(
    inputs: tuple,
    tmp_path: Path,
) -> None:
    runroot, truth = tmp_path / "run_01", tmp_path / "ground_truth.json"
    save(
        runroot, status(failed_stage="TOPOLOGY", artifacts=["aggregation.json"]), inputs, full=False
    )
    native_truth(truth)
    before = (runroot / "aggregation.json").read_bytes()
    manifest = VIS.create_visualization(runroot, truth)
    assert manifest["counts"]["projected_samples"] == 4
    assert manifest["counts"]["gt_samples"] == 6
    core = json.loads((runroot / "visualization" / "presentation.json").read_text())
    assert core["navigation"] == {"nodes": [], "edges": []}
    assert core["events"] == []
    assert "debug_ground_truth" not in core
    assert (runroot / "aggregation.json").read_bytes() == before
    chunks = list(RrdReader(runroot / "visualization" / "debug.rrd").stream())
    paths = {c.entity_path for c in chunks}
    assert any("/accepted_observed/" in p for p in paths)
    assert any("/debug_ground_truth/" in p for p in paths)
    assert not any("/navigation/" in p or "/inferred/" in p for p in paths)
    assert (
        sum(
            c.num_rows
            for c in chunks
            if "/debug_ground_truth/" in c.entity_path and c.entity_path.endswith("/marker")
        )
        == 6
    )
    with pytest.raises(FileExistsError):
        VIS.create_visualization(runroot, truth)


def test_search_empty_result_is_preserved_as_completed_search(
    inputs: tuple, tmp_path: Path
) -> None:
    aggregation, pipeline, (gap,) = inputs
    raw = gap.model_dump(mode="json")
    raw["search_result"].update(
        candidates=[],
        termination_reason="NO_FEASIBLE_PATH",
        complete=True,
        rejection_reasons=["CONFIGURED_TIME_BUDGET"],
    )
    raw["event"].update(candidates=[], trajectories=[], termination_reason="NO_FEASIBLE_PATH")
    empty_gap = BoundGapEvent.model_validate(raw)
    metadata = status(
        failed_stage="SEARCH",
        artifacts=[
            "aggregation.json",
            "pipeline_config.json",
            "gap_events.json",
        ],
    )
    metadata.update(termination_reason="NO_FEASIBLE_PATH", candidate_count_state="SEARCH_RESULT")
    runroot = tmp_path / "run_01"
    save(runroot, metadata, (aggregation, pipeline, (empty_gap,)), full=True)
    manifest = VIS.create_visualization(runroot)
    assert manifest["bounded_gaps"] == 1
    assert manifest["candidates"] == manifest["hypotheses"] == 0
    core = json.loads((runroot / "visualization" / "presentation.json").read_text())
    assert core["events"][0]["enumeration_complete"]
    assert core["events"][0]["rejection_reasons"] == ["CONFIGURED_TIME_BUDGET"]
    assert core["events"][0]["termination_reason"] == "NO_FEASIBLE_PATH"


def test_full_saved_candidate_order_survives_visualization(inputs: tuple, tmp_path: Path) -> None:
    metadata = status(
        failed_stage=None,
        artifacts=[
            "aggregation.json",
            "pipeline_config.json",
            "gap_events.json",
        ],
    )
    metadata["outcome"] = "SUCCESS"
    runroot = tmp_path / "run_01"
    save(runroot, metadata, inputs, full=True)
    manifest = VIS.create_visualization(runroot)
    core = json.loads((runroot / "visualization" / "presentation.json").read_text())
    assert [c["candidate_id"] for c in core["events"][0]["candidates"]] == ["route_0", "route_1"]
    assert manifest["counts"]["candidates"] == manifest["counts"]["hypotheses"] == 2
    assert not core["inference_executed_by_visualizer"]
    assert (runroot / "visualization" / "review_3d.html").is_file()


def test_debug_gt_changes_only_overlay_and_rejects_source_or_site_mismatch(
    inputs: tuple,
    tmp_path: Path,
) -> None:
    metadata = status(failed_stage="TOPOLOGY", artifacts=["aggregation.json"])
    core = VIS.build_prefix(metadata, inputs[0])
    before = json.dumps(core, sort_keys=True)
    truth = tmp_path / "ground_truth.json"
    native_truth(truth)
    first = VIS.load_debug_overlay(truth, core, metadata)
    raw = json.loads(truth.read_text())
    for point in raw["samples"]:
        point["position"][1] = 50
    truth.write_text(json.dumps(raw))
    second = VIS.load_debug_overlay(truth, core, metadata)
    assert first != second
    assert json.dumps(core, sort_keys=True) == before
    native_truth(truth, source="b" * 64)
    with pytest.raises(ValueError, match="lineage"):
        VIS.load_debug_overlay(truth, core, metadata)
    native_truth(truth, site="different_site")
    with pytest.raises(ValueError, match="lineage"):
        VIS.load_debug_overlay(truth, core, metadata)


def test_prefix_rejects_wrong_binding_and_unvalidated_projection(inputs: tuple) -> None:
    metadata = status(failed_stage="TOPOLOGY", artifacts=["aggregation.json"])
    metadata["source_asset_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="source binding"):
        VIS.build_prefix(metadata, inputs[0])
    rejected = status(failed_stage="INPUT_CONTEXT", artifacts=["aggregation.json"])
    with pytest.raises(ValueError, match="cannot be promoted"):
        VIS.build_prefix(rejected, inputs[0])


def test_overview_is_pilot_labeled_and_links_the_actual_scenario(
    inputs: tuple,
    tmp_path: Path,
) -> None:
    runroot = tmp_path / "run_01"
    metadata = status(failed_stage="TOPOLOGY", artifacts=["aggregation.json"])
    metadata["scenario_id"] = "PILOT <test>"
    save(runroot, metadata, inputs, full=False)
    manifest = VIS.create_visualization(runroot)
    output = tmp_path / "overview"
    VIS.create_overview([manifest], output)
    content = (output / "index.html").read_text()
    assert VIS.LABEL in content
    assert "PILOT &lt;test&gt;" in content
    assert "<script" not in content
    assert "../run_01/visualization/review.html" in content
    assert (output / "overview.png").is_file()
