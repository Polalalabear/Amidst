"""Review orchestration preserves GT isolation, exact extent and failed rows."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.finalization.reviewed_pipeline import (
    ABLATIONS,
    benchmark_rows,
    compare_frozen_runs,
    create_gt_poison_dataset,
    digest,
    evaluate_dataset,
    freeze_inference,
    infer_dataset,
    require_inference_freeze,
    verify_dataset,
    write_json,
)

EXPORTER = Path(__file__).parents[2] / "scripts/export_phase1_reviewed_inputs.py"
SPEC = importlib.util.spec_from_file_location("reviewed_export_test", EXPORTER)
assert SPEC and SPEC.loader
exporter = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = exporter
SPEC.loader.exec_module(exporter)


def test_ablation_table_retains_actual_variant_values_and_blocked_cases() -> None:
    measurements = {"case1": {
        "remove_collision": {"result_type": "FORMAL", "status": "EVALUATED",
                             "candidate_count": 4, "ade_m": .4,
                             "metrics_at_k": {"3": {"coverage_at_k": True}}},
        "remove_travel_time": {"result_type": "FORMAL", "status": "EVALUATED",
                               "candidate_count": 2, "ade_m": .2,
                               "metrics_at_k": {"3": {"coverage_at_k": False}}},
    }}
    rows = benchmark_rows(
        [{"case_id": "case1", "status": "READY"},
         {"case_id": "case2", "status": "BLOCKED", "blockers": ["NO_APPROVED_BRANCH"]}],
        measurements, method_ids=ABLATIONS,
    )
    assert len(rows) == 45
    compared = {r["method_id"]: r for r in rows if r["case_id"] == "case1" and r["k"] == 3}
    assert compared["remove_collision"]["candidate_count"] == 4
    assert compared["remove_travel_time"]["candidate_count"] == 2
    assert compared["remove_collision"]["coverage_at_k"] is True
    assert compared["remove_travel_time"]["coverage_at_k"] is False
    blocked = [r for r in rows if r["case_id"] == "case2"]
    assert len(blocked) == 15
    assert all(r["status"] == "BLOCKED" and r["ade_m"] is None
               and r["blockers"] == ["NO_APPROVED_BRANCH"] for r in blocked)


def test_piecewise_sampling_preserves_inclusive_source_endpoints_and_dwell() -> None:
    waypoints = [{"timestamp": 0, "position": [1, 2, 3]},
                 {"timestamp": 1, "position": [1, 2, 3]},
                 {"timestamp": 2, "position": [3, 4, 5]}]
    assert exporter.inclusive_timestamps(0, 2, 5) == [index / 5 for index in range(11)]
    assert exporter.sample_waypoints(waypoints, 0) == [1, 2, 3]
    assert exporter.sample_waypoints(waypoints, .8) == [1, 2, 3]
    assert exporter.sample_waypoints(waypoints, 1.5) == [2, 3, 4]
    assert exporter.sample_waypoints(waypoints, 2) == [3, 4, 5]
    with pytest.raises(ValueError, match="outside"):
        exporter.sample_waypoints(waypoints, 2.1)
    with pytest.raises(ValueError, match="grid"):
        exporter.inclusive_timestamps(0, 2.1, 5)


def test_inference_manifest_verification_never_opens_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "dataset"
    write_json(root / "inference/case1/observations.json", {"pixels": [1, 2]})
    write_json(root / "evaluation/case1/ground_truth.json", {"secret": [9, 8]})
    write_json(root / "simulation/case1/recipe.json", {"secret": [9, 8]})
    write_json(root / "manifest.json", {
        "schema_version": "phase1-reviewed-dataset-v1",
        "artifacts": {str(path.relative_to(root)): digest(path)
                      for path in root.rglob("*.json")},
    })
    original = Path.open

    def guarded(path: Path, *args: Any, **kwargs: Any) -> Any:
        if {"evaluation", "simulation"} & set(path.parts):
            raise AssertionError("inference read a forbidden reference partition")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    assert verify_dataset(root)["schema_version"] == "phase1-reviewed-dataset-v1"
    with pytest.raises(AssertionError, match="forbidden"):
        verify_dataset(root, inference_only=False)


def test_manifest_cannot_escape_inference_dataset(tmp_path: Path) -> None:
    root = tmp_path / "dataset"
    write_json(root / "manifest.json", {"schema_version": "phase1-reviewed-dataset-v1",
                                         "artifacts": {"../secret.json": "a" * 64}})
    with pytest.raises(ValueError, match="escapes"):
        verify_dataset(root)


@pytest.mark.parametrize("missing", ["observations.json", "context.json"])
def test_every_consumed_case_input_must_be_manifest_listed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str,
) -> None:
    import amidst.finalization.reviewed_authority as authority_module
    import amidst.finalization.reviewed_pipeline as pipeline_module
    import amidst.finalization.route_inventory as inventory_module

    dataset, application = tmp_path / "dataset", tmp_path / "application"
    config_path = tmp_path / "inference_lock.json"
    write_json(config_path, {"cases": [{"case_id": "case1"}]})
    write_json(application / "manifest.json", {})
    for name in ("observations.json", "context.json"):
        write_json(dataset / "inference/case1" / name, {})
    write_json(dataset / "manifest.json", {
        "schema_version": "phase1-reviewed-dataset-v1", "source_sha256": "a" * 64,
        "config_sha256": "b" * 64,
        "application_manifest_sha256": digest(application / "manifest.json"),
        "human_decisions_sha256": "c" * 64,
        "artifacts": {str(path.relative_to(dataset)): digest(path)
                      for path in dataset.rglob("*.json") if path.name != missing},
    })
    monkeypatch.setattr(inventory_module, "load_reviewed_case_inference_config",
                        lambda path: SimpleNamespace(
                            export_config_file_sha256="b" * 64,
                            model_dump=lambda **kwargs: {"cases": [{"case_id": "case1"}]},
                        ))
    monkeypatch.setattr(authority_module, "load_reviewed_authority",
                        lambda *args, **kwargs: SimpleNamespace(source_sha256="a" * 64,
                                                              human_decisions_sha256="c" * 64))
    monkeypatch.setattr(pipeline_module, "_module", lambda *args: None)
    with pytest.raises(ValueError, match="missing from frozen manifest"):
        infer_dataset(dataset, application, config_path, tmp_path / "output", repo_root=tmp_path)


def test_poison_changes_both_gt_partitions_and_preserves_all_inference_bytes(
    tmp_path: Path,
) -> None:
    root, poisoned = tmp_path / "dataset", tmp_path / "poisoned"
    write_json(root / "inference/case1/observations.json", {"pixels": [1, 2]})
    write_json(root / "evaluation/case1/ground_truth.json",
               {"samples": [{"position": [1, 2, 3]}]})
    write_json(root / "simulation/case1/recipe.json", {"waypoints": [{"position": [1, 2, 3]}]})
    write_json(root / "evaluation/case1/reference_movement_annotations.json",
               {"segments": [{"kind": "MOVING", "duration_s": 1}]})
    write_json(root / "manifest.json", {
        "schema_version": "phase1-reviewed-dataset-v1",
        "artifacts": {str(path.relative_to(root)): digest(path)
                      for path in root.rglob("*.json")},
    })
    create_gt_poison_dataset(root, poisoned)
    assert (root / "manifest.json").read_bytes() == (poisoned / "manifest.json").read_bytes()
    assert (root / "inference/case1/observations.json").read_bytes() == (
        poisoned / "inference/case1/observations.json"
    ).read_bytes()
    assert (root / "evaluation/case1/ground_truth.json").read_bytes() != (
        poisoned / "evaluation/case1/ground_truth.json"
    ).read_bytes()
    assert (root / "simulation/case1/recipe.json").read_bytes() != (
        poisoned / "simulation/case1/recipe.json"
    ).read_bytes()
    poisoned_annotations = json.loads(
        (poisoned / "evaluation/case1/reference_movement_annotations.json").read_bytes(),
    )
    assert poisoned_annotations["segments"] == "INVALID"
    verify_dataset(poisoned)
    with pytest.raises(ValueError, match="differs"):
        verify_dataset(poisoned, inference_only=False)


def test_freeze_detects_candidate_change_but_retains_noncanonical_runtime(
    tmp_path: Path,
) -> None:
    root = tmp_path / "inference"
    write_json(root / "case1/candidates.json", {"candidates": ["first", "second"]})
    write_json(root / "case1/runtime.json", {"runtime_s": .1})
    freeze_inference(root, dataset_manifest_sha256="a" * 64, config_sha256="b" * 64)
    (root / "case1/runtime.json").write_text('{"runtime_s": 0.2}\n')
    assert require_inference_freeze(root)["ground_truth_read"] is False
    (root / "case1/candidates.json").write_text('{"candidates": ["second", "first"]}\n')
    with pytest.raises(ValueError, match="changed after freeze"):
        require_inference_freeze(root)


def test_fresh_comparison_includes_order_termination_and_dataset_hash(tmp_path: Path) -> None:
    local, fresh = tmp_path / "local", tmp_path / "fresh"
    for root in (local, fresh):
        write_json(root / "event.json", {"candidates": ["a", "b"], "termination": "EXHAUSTED"})
        freeze_inference(root, dataset_manifest_sha256="a" * 64, config_sha256="b" * 64)
    assert compare_frozen_runs(local, fresh)["status"] == "PASS"
    freeze = json.loads((fresh / "inference_freeze.json").read_bytes())
    freeze["dataset_manifest_sha256"] = "c" * 64
    (fresh / "inference_freeze.json").write_text(json.dumps(freeze))
    assert compare_frozen_runs(local, fresh)["status"] == "FAIL"


def test_evaluation_cannot_open_gt_before_primary_freeze(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="inference_freeze"):
        evaluate_dataset(tmp_path / "dataset", tmp_path / "inference", tmp_path / "authority",
                         tmp_path / "evaluation", repo_root=tmp_path, demos=False)
    assert not (tmp_path / "evaluation").exists()


def test_every_case_method_k_row_retains_nulls_for_blocked_case() -> None:
    rows = benchmark_rows([{"case_id": "case2", "status": "BLOCKED_SCOPE",
                            "blockers": ["NEW_BRANCHING_SCOPE_REQUIRED"]}], {})
    assert len(rows) == 27
    blocked = [row for row in rows if row["case_id"] == "case2"]
    assert len(blocked) == 9
    assert all(row["coverage_at_k"] is None and row["collision_rate"] is None
               and row["candidate_count"] is None for row in blocked)
    assert all(row["blockers"] == ["NEW_BRANCHING_SCOPE_REQUIRED"] for row in blocked)
