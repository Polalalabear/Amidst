"""Evidence loss cannot masquerade as an accuracy fix in mitigation evaluation."""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "mitigation_comparison_tests",
    Path(__file__).parents[2] / "scripts/compare_projection_mitigations.py",
)
assert spec and spec.loader
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def test_discarding_bad_samples_has_no_paired_improvement():
    good, bad = ("camera", 0, 0.0), ("camera", 1, 1.0)
    baseline = {good: (0.0, 0.0, 0.0), bad: (10.0, 0.0, 0.0)}
    truth = {0.0: (1.0, 0.0, 0.0), 1.0: (0.0, 0.0, 0.0)}
    result = comparison.retained_error_evaluation(baseline, {good: baseline[good]}, truth)
    assert result["retained_error"]["rms_bu"] == 1
    assert result["all_original_baseline_error"]["rms_bu"] > 7
    assert result["paired_rms_reduction_percent"] == 0
    assert result["deletion_changes_evaluation_cohort"] is True
    assert result["availability"] == 0.5


def test_real_improvement_uses_same_identities():
    identity = ("camera", 0, 0.0)
    result = comparison.retained_error_evaluation(
        {identity: (10.0, 0.0, 0.0)},
        {identity: (5.0, 0.0, 0.0)},
        {0.0: (0.0, 0.0, 0.0)},
    )
    assert result["paired_rms_reduction_percent"] == 50
    assert result["availability"] == 1
    assert result["deletion_changes_evaluation_cohort"] is False


def test_all_rejected_has_null_error_not_perfect_accuracy():
    result = comparison.retained_error_evaluation(
        {("camera", 0, 0.0): (10.0, 0.0, 0.0)},
        {},
        {0.0: (0.0, 0.0, 0.0)},
    )
    assert result["availability"] == 0
    assert result["retained_error"] == {"count": 0, "mean_bu": None, "rms_bu": None, "max_bu": None}
    assert result["paired_rms_reduction_percent"] is None


@pytest.mark.parametrize(
    "retained,truth",
    [
        ({("new_camera", 0, 0.0): (0.0, 0.0, 0.0)}, {0.0: (0.0, 0.0, 0.0)}),
        ({("camera", 0, 0.0): (0.0, 0.0, 0.0)}, {1.0: (0.0, 0.0, 0.0)}),
    ],
)
def test_unmatched_cohorts_cannot_be_evaluated(retained, truth):
    with pytest.raises(ValueError, match="original identities"):
        comparison.retained_error_evaluation({("camera", 0, 0.0): (0.0, 0.0, 0.0)}, retained, truth)


def test_changed_gt_changes_only_evaluation_metrics():
    identity = ("camera", 0, 0.0)
    baseline = {identity: (1.0, 0.0, 0.0)}
    before = comparison.retained_error_evaluation(baseline, baseline, {0.0: (1.0, 0.0, 0.0)})
    after = comparison.retained_error_evaluation(baseline, baseline, {0.0: (10001.0, 0.0, 0.0)})
    assert before["retained_error"]["max_bu"] == 0
    assert after["retained_error"]["max_bu"] == 10000
    assert baseline == {identity: (1.0, 0.0, 0.0)}
    assert after["paired_rms_reduction_percent"] == 0


def test_refuses_existing_experiment_without_reading_inventory(tmp_path):
    (tmp_path / "protocol.json").write_text("{}")
    (tmp_path / "cases").mkdir()
    with pytest.raises(FileExistsError):
        comparison.run_comparison(tmp_path / "unavailable_inventory.json", tmp_path)
    assert list((tmp_path / "cases").iterdir()) == []


def test_protocol_noise_change_rejected_before_sources(tmp_path):
    (tmp_path / "protocol.json").write_text(
        json.dumps(
            {
                "label": "PILOT / SYNTHETIC SAMPLE",
                "noise_halfwidths_pixels": [0, 2],
                "seeds": list(comparison.SEEDS),
            }
        )
    )
    with pytest.raises(ValueError, match="predeclared"):
        comparison.run_comparison(tmp_path / "unavailable_inventory.json", tmp_path)
    assert not (tmp_path / "cases").exists()


def test_point_only_table_preserves_unavailable_metrics(tmp_path):
    identity = ("camera", 0, 0.0)
    evaluation = comparison.retained_error_evaluation(
        {identity: (1.0, 0.0, 0.0)},
        {identity: (1.0, 0.0, 0.0)},
        {0.0: (1.0, 0.0, 0.0)},
    )
    row = {
        "site_id": "classroom101",
        "case_id": "control",
        "variant": "A_BASELINE",
        "treatment": {
            "kind": "PIXEL_NOISE",
            "noise_halfwidth_px": 0,
            "seed": 42,
            "calibration_variant": None,
        },
        "original_visible_count": 1,
        "accepted_count": 1,
        "rejected_count": 0,
        "low_confidence_count": 0,
        "point_error_evaluation": evaluation,
        "metrics": None,
        "downstream": comparison.point_only_status("classroom101"),
        "metrics_status": "NOT_RUN_POINT_ONLY",
        "gap_window_changed": False,
        "runtime": {"effective_projection_stage_seconds": 0.001, "downstream_seconds": 0.002},
    }
    path = tmp_path / "table.csv"
    comparison.write_table([row], path)
    with path.open() as stream:
        saved = next(csv.DictReader(stream))
    assert saved["point_rms_bu"] == "0.0"
    assert saved["ade_bu"] == saved["coverage_k3"] == saved["candidate_count"] == ""
    assert saved["termination"] == "NOT_RUN"


@pytest.mark.parametrize(
    "changed",
    [
        {"coverage_epsilon_scene_units": 0.03},
        {"policy": {"pixel_uncertainty_radius_px": 0.002, "point_budget_bu": 0.2}},
        {"calibration_variants": []},
        {"implemented_variants": ["A_BASELINE"]},
    ],
)
def test_non_noise_protocol_changes_cannot_silently_tune_experiment(tmp_path, changed):
    declared = {
        "label": "PILOT / SYNTHETIC SAMPLE",
        "noise_halfwidths_pixels": list(comparison.NOISE_LEVELS),
        "seeds": list(comparison.SEEDS),
        "policy": comparison.module("projection_mitigation_policy")
        .ConditioningPolicy()
        .model_dump(),
        "calibration_variants": list(comparison.CALIBRATION_IDS),
        "implemented_variants": list(comparison.VARIANTS),
        "school_authority_unavailable_variants": list(comparison.UNAVAILABLE),
        "coverage_epsilon_scene_units": comparison.EPSILON,
    }
    declared.update(changed)
    (tmp_path / "protocol.json").write_text(json.dumps(declared))
    with pytest.raises(ValueError, match="predeclared policy"):
        comparison.run_comparison(tmp_path / "unavailable_inventory.json", tmp_path)
    assert not (tmp_path / "cases").exists()
