"""Robustness failures report honest N/A; truth never reorders saved inference."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from bisect import bisect_right
from pathlib import Path
from typing import Any

import pytest

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, run_pilot_downstream


def evaluation_module() -> Any:
    path = Path(__file__).parents[2] / "scripts/evaluate_pilot_robustness.py"
    spec = importlib.util.spec_from_file_location("pilot_robustness_evaluation", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


evaluation = evaluation_module()


def status_payload(
    *,
    eligible: bool,
    termination: str = "NOT_RUN",
    candidate_count: int = 0,
    hypothesis_count: int = 0,
) -> dict[str, Any]:
    return {
        "label": PILOT_LABEL,
        "scenario_id": "TEST_ROBUSTNESS",
        "outcome": "SUCCESS" if eligible else "EXPECTED_FAILURE",
        "failed_stage": None
        if eligible
        else ("INPUT_CONTEXT" if termination == "NOT_RUN" else "SEARCH"),
        "reason": "NONE"
        if eligible
        else ("INVALID_INPUT" if termination == "NOT_RUN" else "NO_FEASIBLE_PATH"),
        "termination_reason": termination,
        "evaluation_eligible": eligible,
        "candidate_count": candidate_count,
        "hypothesis_count": hypothesis_count,
        "candidate_count_state": "NOT_RUN" if termination == "NOT_RUN" else "SEARCH_RESULT",
        "available_artifacts": [],
        "stage_states": {
            "INPUT_CONTEXT": "PASSED" if eligible else "FAILED",
            "SEARCH": "NOT_RUN" if termination == "NOT_RUN" else "PASSED",
        },
        "physical_validity": {"status": "PARTIAL_PROVISIONAL"},
    }


@pytest.fixture
def completed(tmp_path: Path) -> tuple[Path, Path, Path]:
    observations = tmp_path / "observations.json"
    frames = [
        {
            "frame_id": index,
            "timestamp": float(index),
            "target_id": "target",
            "camera_id": camera,
            "status": "OBSERVED" if visible else "GAP",
            "point_2d": [14 + index, 16] if visible else None,
            "provenance": "OBSERVED" if visible else None,
            "gap_reason": None if visible else "OCCLUDED",
            "data_kind": "SYNTHETIC",
        }
        for index in range(5)
        for camera, visible in (
            ("CAM_A", index < 2),
            ("CAM_B", index >= 3),
        )
    ]
    observations.write_text(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "data_kind": "SYNTHETIC",
                "site_id": "TEST",
                "source_asset_sha256": "a" * 64,
                "frames": frames,
            }
        )
    )
    context = PilotInferenceContext.model_validate(
        {
            "label": PILOT_LABEL,
            "data_kind": "SYNTHETIC",
            "site_id": "TEST",
            "source_id": "source",
            "spatial_context_id": "scene",
            "source_asset_sha256": "a" * 64,
            "observations_sha256": hashlib.sha256(observations.read_bytes()).hexdigest(),
            "cameras": [
                {
                    "camera_id": camera,
                    "camera_to_world": [
                        [1, 0, 0, 0],
                        [0, 1, 0, 0],
                        [0, 0, 1, 10],
                        [0, 0, 0, 1],
                    ],
                    "fx": 10,
                    "fy": 10,
                    "cx": 16,
                    "cy": 16,
                    "width": 32,
                    "height": 32,
                    "floor_id": "1F",
                    "zone_id": camera,
                }
                for camera in ("CAM_A", "CAM_B")
            ],
            "plane": {
                "plane_id": "plane",
                "point": [0, 0, 0],
                "normal": [0, 0, 1],
                "floor_id": "1F",
                "zone_id": "zone",
            },
            "zone": {
                "floor_id": "1F",
                "zone_id": "zone",
                "walkable_object_id": "walk",
                "bounds_min": [-20, -20, -1],
                "bounds_max": [20, 20, 1],
                "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL",
            },
        }
    )
    context_path, root = tmp_path / "context.json", tmp_path / "run"
    context_path.write_text(context.model_dump_json())
    run = run_pilot_downstream(observations, context_path, root, lateral_offset_scene_units=0.5)
    (root / "robustness_status.json").write_text(
        json.dumps(
            status_payload(
                eligible=True,
                termination="COMPLETE",
                candidate_count=3,
                hypothesis_count=len(run.gaps[0].event.trajectories),
            )
        )
    )
    # Evaluation-only fixture: the third route is compatible, after inference was fixed.
    event = run.gaps[0].event
    candidate_id = event.candidates[-1].candidate_id
    points = next(t for t in event.trajectories if t.candidate_id == candidate_id).timed_points
    samples = []
    for timestamp in range(5):
        if timestamp <= points[0].timestamp:
            position = points[0].world_position
        elif timestamp >= points[-1].timestamp:
            position = points[-1].world_position
        else:
            index = bisect_right([point.timestamp for point in points], timestamp) - 1
            first, second = points[index : index + 2]
            fraction = (timestamp - first.timestamp) / (second.timestamp - first.timestamp)
            position = tuple(
                a + fraction * (b - a)
                for a, b in zip(
                    first.world_position,
                    second.world_position,
                    strict=True,
                )
            )
        samples.append(
            {
                "timestamp": float(timestamp),
                "position": position,
                "floor_id": "1F",
                "trajectory_id": "fixture-trajectory",
            }
        )
    truth = tmp_path / "evaluation_reference.json"
    truth.write_text(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "provenance": "GROUND_TRUTH",
                "source_asset_sha256": "a" * 64,
                "site_id": "TEST",
                "trajectory_id": "fixture-trajectory",
                "samples": samples,
            }
        )
    )
    return root, truth, context_path


def assert_null_metrics(report: dict[str, Any]) -> None:
    assert report["status"] == "NOT_COMPUTABLE"
    assert report["configured_evaluation"] is None
    assert report["ground_truth_read"] is False
    assert report["ground_truth_sha256"] is None
    assert [row["k"] for row in report["summaries"]] == [1, 2, 3]
    for row in report["summaries"]:
        for key in (
            "ade_first_primary_scene_units",
            "fde_first_primary_scene_units",
            "min_ade_at_k_scene_units",
            "min_fde_at_k_scene_units",
            "coverage_at_k",
        ):
            assert row[key] is None


@pytest.mark.parametrize("termination", ["NOT_RUN", "NO_FEASIBLE_PATH"])
def test_failure_has_honest_nulls_and_never_opens_truth_or_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    termination: str,
) -> None:
    root = tmp_path / "failed"
    root.mkdir()
    status = root / "robustness_status.json"
    status.write_text(json.dumps(status_payload(eligible=False, termination=termination)))
    truth, context = tmp_path / "truth-never-created.json", tmp_path / "context-never-created.json"
    before = status.read_bytes()
    original_open = Path.open

    def guarded_open(path: Path, *args: object, **kwargs: object):
        if path in {truth, context}:
            pytest.fail("ineligible evaluation must not open truth or context")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    report = evaluation.evaluate_saved_robustness(root, truth, context)
    assert_null_metrics(report)
    assert report["saved_search_result_available"] == (termination != "NOT_RUN")
    assert report["candidate_count_state"] == (
        "NOT_RUN" if termination == "NOT_RUN" else "SEARCH_RESULT"
    )
    assert status.read_bytes() == before
    assert report["physical_validity"]["blender_mesh_collision_rate"] is None
    assert json.loads((root / "metrics.json").read_text())["summaries"] == report["summaries"]
    assert "N/A" in (root / "metrics.md").read_text()


def test_success_preserves_existing_three_k_metrics_and_third_route_is_only_evaluation_compatible(
    completed: tuple[Path, Path, Path],
) -> None:
    root, truth, context = completed
    snapshot = evaluation.frozen_digests(root, root / "robustness_status.json")
    report = evaluation.evaluate_saved_robustness(root, truth, context)
    assert report["status"] == "COMPUTED"
    assert report["ground_truth_read"] is True
    one, _, three = report["summaries"]
    assert one["ade_first_primary_scene_units"] > 0.1 and one["coverage_at_k"] is False
    assert three["min_ade_at_k_scene_units"] < 1e-9 and three["coverage_at_k"] is True
    assert [row["k"] for row in report["summaries"]] == [1, 2, 3]
    assert three["ade_first_primary_scene_units"] == one["ade_first_primary_scene_units"]
    assert report["physical_validity"]["status"] == "PARTIAL_PROVISIONAL"
    assert report["physical_validity"]["blender_mesh_collision_rate"] is None
    assert evaluation.frozen_digests(root, root / "robustness_status.json") == snapshot


def test_gt_poison_changes_metrics_only_and_never_the_saved_candidates_or_order(
    completed: tuple[Path, Path, Path],
) -> None:
    root, truth, context = completed
    second = root.with_name("poison_run")
    shutil.copytree(root, second)
    baseline = evaluation.evaluate_saved_robustness(root, truth, context)
    payload = json.loads(truth.read_text())
    for sample in payload["samples"]:
        sample["position"] = [value + 10000 for value in sample["position"]]
    truth.write_text(json.dumps(payload))
    changed = evaluation.evaluate_saved_robustness(second, truth, context)
    assert baseline["summaries"] != changed["summaries"]
    assert baseline["ground_truth_sha256"] != changed["ground_truth_sha256"]
    assert changed["summaries"][-1]["coverage_at_k"] is False
    assert evaluation.downstream.artifact_digests(root) == evaluation.downstream.artifact_digests(
        second
    )
    assert (
        baseline["summaries"][-1]["selected_hypothesis_ids"]
        == (changed["summaries"][-1]["selected_hypothesis_ids"])
    )


def test_eligibility_claim_does_not_make_empty_saved_hypotheses_evaluable(
    completed: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, truth, context = completed
    path = root / "gap_events.json"
    payload = json.loads(path.read_text())
    payload["gaps"][0]["event"]["trajectories"] = []
    path.write_text(json.dumps(payload))
    original_open = Path.open

    def guarded_open(path: Path, *args: object, **kwargs: object):
        if path == truth:
            pytest.fail("no timed prediction must be rejected before truth access")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    report = evaluation.evaluate_saved_robustness(root, truth, context)
    assert_null_metrics(report)
    assert report["reason_code"] == "ELIGIBILITY_HAS_NO_TIMED_PREDICTION"


def test_wrong_prediction_count_and_wrong_gt_binding_are_rejected_before_metric_output(
    completed: tuple[Path, Path, Path],
) -> None:
    root, truth, context = completed
    path = root / "robustness_status.json"
    original_status = path.read_text()
    status = json.loads(original_status)
    status["candidate_count"] += 1
    path.write_text(json.dumps(status))
    with pytest.raises(ValueError, match="prediction counts"):
        evaluation.evaluate_saved_robustness(root, truth, context)
    assert not (root / "metrics.json").exists()
    path.write_text(original_status)
    wrong_truth = json.loads(truth.read_text())
    wrong_truth["source_asset_sha256"] = "f" * 64
    truth.write_text(json.dumps(wrong_truth))
    with pytest.raises(ValueError, match="source/site/provenance"):
        evaluation.evaluate_saved_robustness(root, truth, context)
    assert not (root / "metrics.json").exists()


def test_truth_time_alignment_contract_is_reused_without_extrapolation(
    completed: tuple[Path, Path, Path],
) -> None:
    root, truth, context = completed
    payload = json.loads(truth.read_text())
    payload["samples"].pop()
    truth.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="ordered pilot timestamps"):
        evaluation.evaluate_saved_robustness(root, truth, context)
    assert not (root / "metrics.json").exists()


@pytest.mark.parametrize("key,value", [("label", "UNLABELED"), ("evaluation_eligible", "yes")])
def test_invalid_status_is_rejected_without_reporting_false_metrics(
    tmp_path: Path,
    key: str,
    value: object,
) -> None:
    status = status_payload(eligible=False)
    status[key] = value
    path = tmp_path / "robustness_status.json"
    path.write_text(json.dumps(status))
    with pytest.raises(ValueError):
        evaluation.evaluate_saved_robustness(tmp_path, tmp_path / "GT", tmp_path / "context")
    assert not (tmp_path / "metrics.json").exists()


def test_existing_metric_files_are_never_replaced(tmp_path: Path) -> None:
    (tmp_path / "robustness_status.json").write_text(json.dumps(status_payload(eligible=False)))
    path = tmp_path / "metrics.md"
    path.write_text("preserved review")
    with pytest.raises(FileExistsError):
        evaluation.evaluate_saved_robustness(tmp_path, tmp_path / "GT", tmp_path / "context")
    assert path.read_text() == "preserved review"
