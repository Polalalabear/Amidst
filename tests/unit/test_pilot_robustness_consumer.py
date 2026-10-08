"""Controlled failures retain valid evidence without truth access or invented gaps."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from test_pilot_downstream_consumer import inputs as inputs

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_pilot_robustness.py"
SPEC = importlib.util.spec_from_file_location("controlled_robustness_consumer", SCRIPT)
assert SPEC and SPEC.loader
robust = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = robust
SPEC.loader.exec_module(robust)


def scenario(tmp_path: Path, **changes: object) -> Path:
    config = {
        "label": "PILOT / SYNTHETIC SAMPLE", "scenario_id": "controlled-test",
        "lateral_offset_scene_units": 12.0, "max_speed_scene_units_s": 32.0,
        "max_candidate_paths": 3, "random_seed": 20261006,
    }
    config.update(changes)
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(config))
    return path


def rewrite_inputs(paths: tuple[Path, Path], observation: dict, context: dict) -> None:
    paths[0].write_text(json.dumps(observation))
    context["observations_sha256"] = hashlib.sha256(paths[0].read_bytes()).hexdigest()
    paths[1].write_text(json.dumps(context))


def test_importable_scenario_schema_does_not_require_module_registration(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("robustness_unregistered", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = module.RobustnessScenario.model_validate_json(scenario(tmp_path).read_bytes())
    assert config.scenario_id == "controlled-test"


def test_success_uses_ordinary_runner_and_all_results_are_labeled(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    config = scenario(tmp_path, lateral_offset_scene_units=2)
    output = tmp_path / "run"
    before = [p.read_bytes() for p in (*inputs, config)]
    status = robust.run_robustness(*inputs, output, config)
    assert status["outcome"] == "SUCCESS" and status["evaluation_eligible"]
    assert status["candidate_count"] == 3 and status["search_executed"]
    assert status["stage_states"]["RECONSTRUCTION"] == "PASSED"
    assert set(status["available_artifacts"]) == set(robust.INFERENCE_FILES)
    assert status["source_asset_sha256"] == "a" * 64 and status["site_id"] == "TEST"
    assert status["raw_sample_count"] == 10 and status["timestamp_count"] == 5
    for path in output.glob("*.json"):
        assert json.loads(path.read_text())["label"] == "PILOT / SYNTHETIC SAMPLE"
    assert [p.read_bytes() for p in (*inputs, config)] == before
    with pytest.raises(FileExistsError):
        robust.run_robustness(*inputs, output, config)


@pytest.mark.parametrize("removed", ["CAM_A", "CAM_B"])
def test_camera_removal_is_invalid_context_without_fake_recovery_or_pipeline(
    inputs: tuple[Path, Path], tmp_path: Path, removed: str,
) -> None:
    observations, context = (json.loads(path.read_text()) for path in inputs)
    observations["frames"] = [r for r in observations["frames"] if r["camera_id"] != removed]
    context["cameras"] = [r for r in context["cameras"] if r["camera_id"] != removed]
    rewrite_inputs(inputs, observations, context)
    output = tmp_path / "removed"
    status = robust.run_robustness(*inputs, output, scenario(tmp_path))
    assert status["failed_stage"] == "INPUT_CONTEXT" and status["reason"] == "INVALID_INPUT"
    assert status["termination_reason"] == "NOT_RUN" and not status["search_executed"]
    assert status["candidate_count"] == 0 and status["candidate_count_state"] == "NOT_RUN"
    assert not status["evaluation_eligible"] and not status["binding_validated"]
    assert status["untrusted_binding"]["validated"] is False
    assert "source_asset_sha256" not in status
    assert not (output / "aggregation.json").exists()
    assert not (output / "pipeline_config.json").exists()
    assert not (output / "gap_events.json").exists()


def test_same_camera_short_gap_preserves_valid_prefix_but_does_not_fake_handoff(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    observations, context = (json.loads(path.read_text()) for path in inputs)
    for row in observations["frames"]:
        visible = row["camera_id"] == "CAM_A" and row["frame_id"] != 2
        row.update(status="OBSERVED" if visible else "GAP",
                   point_2d=[10 + row["frame_id"], 16] if visible else None,
                   provenance="OBSERVED" if visible else None,
                   gap_reason=None if visible else "OCCLUDED",
                   occluder_id=None if visible else "physical-mesh-id")
    rewrite_inputs(inputs, observations, context)
    output = tmp_path / "short"
    status = robust.run_robustness(*inputs, output, scenario(tmp_path))
    assert status["failed_stage"] == "TOPOLOGY" and status["reason"] == "UNSUPPORTED_SAME_CAMERA"
    assert status["stage_states"]["PROJECTION"] == status["stage_states"]["AGGREGATION"] == "PASSED"
    assert status["observation_count"] == 2 and status["gap_window"] == (1, 3)
    assert status["candidate_count"] == 0 and status["candidate_count_state"] == "NOT_RUN"
    assert not status["evaluation_eligible"] and not status["search_executed"]
    assert (output / "projected_frames.json").exists() and (output / "aggregation.json").exists()
    assert not (output / "pipeline_config.json").exists() and not (output / "events.json").exists()
    samples = json.loads((output / "projected_frames.json").read_text())["dataset"]["samples"]
    assert all(row["projected_point"] is None and row["uv"] is None
               for row in samples if row["visibility"] == "GAP")


@pytest.mark.parametrize("speed,offset,expected", [(33, 12, 1), (33, 1, 3), (31, 12, 0)])
def test_compressed_gap_speed_and_branch_constraints_use_actual_search_results(
    inputs: tuple[Path, Path], tmp_path: Path, speed: float, offset: float, expected: int,
) -> None:
    observations, context = (json.loads(path.read_text()) for path in inputs)
    for camera in context["cameras"]:
        camera["fx"] = 1
    context["zone"]["bounds_min"] = [-100, -100, -1]
    context["zone"]["bounds_max"] = [100, 100, 1]
    for row in observations["frames"]:
        row["timestamp"] *= 1.25
        if row["camera_id"] == "CAM_A" and row["frame_id"] == 1:
            row["point_2d"] = [12, 16]
        if row["camera_id"] == "CAM_B" and row["frame_id"] == 3:
            row["point_2d"] = [20, 14]
    rewrite_inputs(inputs, observations, context)
    output = tmp_path / "constraint"
    status = robust.run_robustness(*inputs, output, scenario(
        tmp_path, max_speed_scene_units_s=speed, lateral_offset_scene_units=offset,
    ))
    assert status["candidate_count"] == expected
    assert status["candidate_count_state"] == "SEARCH_RESULT"
    assert status["search_executed"] and status["gap_window"] == (1.25, 3.75)
    assert (output / "pipeline_config.json").exists() and (output / "gap_events.json").exists()
    if expected == 0:
        assert status["failed_stage"] == "SEARCH" and status["reason"] == "NO_FEASIBLE_PATH"
        assert status["termination_reason"] == "NO_FEASIBLE_PATH"
        assert not status["evaluation_eligible"] and status["hypothesis_count"] == 0
    else:
        assert status["outcome"] == "SUCCESS" and status["evaluation_eligible"]


@pytest.mark.parametrize("bad_field", ["ground_truth_path", "dataset_path", "trajectory_plan_path"])
def test_configuration_forbids_truth_and_mixed_input_paths(
    inputs: tuple[Path, Path], tmp_path: Path, bad_field: str,
) -> None:
    config = scenario(tmp_path, **{bad_field: "must-not-be-opened.json"})
    with pytest.raises(ValueError, match="Extra inputs"):
        robust.run_robustness(*inputs, tmp_path / "invalid", config)
    assert not (tmp_path / "invalid").exists()


def test_known_truth_filename_is_rejected_before_reading(
    inputs: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_read = Path.read_bytes
    def guarded_read(path: Path) -> bytes:
        assert path.name not in robust.FORBIDDEN_INPUT_NAMES
        return original_read(path)
    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(ValueError, match="forbidden consumer inputs"):
        robust.run_robustness(tmp_path / "ground_truth.json", inputs[1],
                              tmp_path / "invalid", scenario(tmp_path))


def test_repeat_and_truth_poison_are_byte_identical_with_forbidden_file_reads(
    inputs: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = scenario(tmp_path, lateral_offset_scene_units=2)
    original_open = Path.open
    def guarded_open(path: Path, *args: object, **kwargs: object):
        assert path.name not in robust.FORBIDDEN_INPUT_NAMES
        return original_open(path, *args, **kwargs)
    with original_open(tmp_path / "ground_truth.json", "w") as stream:
        stream.write('{"position":[1,2,3]}')
    monkeypatch.setattr(Path, "open", guarded_open)
    first, second = tmp_path / "first", tmp_path / "second"
    robust.run_robustness(*inputs, first, config)
    with original_open(tmp_path / "ground_truth.json", "w") as stream:
        stream.write('{"position":[999999,123456,-654321]}')
    robust.run_robustness(*inputs, second, config)
    for name in robust.INFERENCE_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes()
    status = json.loads((first / "robustness_status.json").read_text())
    assert str(first) not in json.dumps(status) and str(second) not in json.dumps(status)
    assert status["ground_truth_read"] is False
