"""Runtime file isolation and GT-free projection sensitivity evidence."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "robustness_validation_checks",
    Path(__file__).parents[2] / "scripts/validate_pilot_robustness.py",
)
assert spec and spec.loader
validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validation)


@pytest.mark.parametrize("name", [
    "ground_truth.json", "poisoned_ground_truth.json", "dataset.json", "trajectory_plan.json",
])
@pytest.mark.parametrize("reader", ["path", "builtin"])
def test_real_inference_guard_blocks_truth_plan_and_mixed_reads(tmp_path, name, reader):
    path = tmp_path / name
    path.write_text("private evaluation-only fixture")
    observed = tmp_path / "observations.json"
    observed.write_text("pure 2D evidence")
    with validation.forbid_evaluation_reads():
        assert observed.read_text() == "pure 2D evidence"
        with pytest.raises(AssertionError, match="forbidden evaluation read"):
            if reader == "path":
                path.read_bytes()
            else:
                with open(path) as stream:
                    stream.read()
    assert path.read_text() == "private evaluation-only fixture"


def test_noise_layer_diagnostic_pairs_saved_projection_without_any_gt(tmp_path):
    names = ("S01_office_medium", "S06_office_pixel_noise")
    for index, name in enumerate(names):
        path = tmp_path / "scenarios" / name / "run_01/projected_frames.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"dataset": {"samples": [
            {"camera_id": "CAM_A", "frame_id": 3, "timestamp": 0.6,
             "uv": [10.0 + 0.1 * index, 10.0],
             "projected_point": {"world_position": [float(index), 0.0, 0.0]}},
            {"camera_id": "CAM_A", "frame_id": 4, "timestamp": 0.8,
             "uv": None, "projected_point": None},
        ]}}))
    with validation.forbid_evaluation_reads():
        result = validation.diagnose_projection_noise(tmp_path)
    assert result["ground_truth_used"] is False
    assert result["paired_visible_sample_count"] == 1
    assert result["maximum_world_displacement"]["delta_world_scene_units"] == 1.0
    assert result["maximum_amplification_scene_units_per_pixel"] == pytest.approx(10.0)


def test_fixed_matrix_cannot_claim_pass_after_missing_scenarios():
    assert validation.validate_results([]) == [
        "fixed matrix must contain exactly all nine distinct scenarios",
    ]
