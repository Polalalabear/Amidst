"""Fixed pixel controls, actual saved consumers and GT isolation stay independently testable."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import io
import json
import os
import random
from bisect import bisect_right
from pathlib import Path
from typing import Any

import pytest
from test_pilot_downstream_consumer import inputs as inputs

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, PilotObservationExport

SCRIPT = Path(__file__).parents[2] / "scripts" / "sweep_projection_downstream.py"
SPEC = importlib.util.spec_from_file_location("projection_sensitivity_test", SCRIPT)
assert SPEC and SPEC.loader
sweep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sweep)


def test_fixed_protocol_includes_fine_boundary_and_required_coarse_levels() -> None:
    assert sweep.NOISE_HALF_WIDTHS_PIXELS == (
        0.0, .0005, .001, .0015, .002, .0025, .003, .0035, .004,
        .005, .01, .02, .05, .1, .25, .5, 1.0,
    )
    assert sweep.SEEDS == (20261006, 42, 20261007)
    assert len(sweep.NOISE_HALF_WIDTHS_PIXELS) * len(sweep.SEEDS) * 2 == 102
    assert sweep.COVERAGE_EPSILON_SCENE_UNITS == sweep.POINT_BUDGET_SCENE_UNITS == .02


def test_shared_draws_preserve_export_order_nulls_and_exact_existing_s06_noise(
    inputs: tuple[Path, Path],
) -> None:
    export = PilotObservationExport.model_validate_json(inputs[0].read_bytes())
    # Deliberately reverse export order to guard against canonical sorting before RNG.
    export = PilotObservationExport.model_validate({
        **export.model_dump(mode="json"), "frames": list(reversed(export.frames)),
    })
    draws = sweep.normalized_noise(export, 20261006)
    assert draws == sweep.normalized_noise(export, 20261006)
    assert draws != sweep.normalized_noise(export, 42)
    quarter = sweep.perturb_pixels(export, draws, .25)
    half = sweep.perturb_pixels(export, draws, .5)
    zero = sweep.perturb_pixels(export, draws, 0)
    assert zero == export
    existing_generator = random.Random(20261006)
    for original, noisy, scaled in zip(export.frames, quarter.frames, half.frames, strict=True):
        if original.status == "GAP":
            assert noisy == scaled == original
            assert noisy.point_2d is None and noisy.provenance is None
        else:
            assert original.point_2d is not None and noisy.point_2d is not None
            assert scaled.point_2d is not None
            assert noisy.point_2d == tuple(
                value + existing_generator.uniform(-.25, .25) for value in original.point_2d
            )
            for value, first, second in zip(
                original.point_2d, noisy.point_2d, scaled.point_2d, strict=True,
            ):
                assert second - value == pytest.approx(2 * (first - value), abs=1e-14)


@pytest.mark.parametrize("amplitude", [-1.0, float("nan"), float("inf")])
def test_invalid_noise_amplitudes_are_rejected(inputs: tuple[Path, Path], amplitude: float) -> None:
    export = PilotObservationExport.model_validate_json(inputs[0].read_bytes())
    with pytest.raises(ValueError, match="finite and nonnegative"):
        sweep.perturb_pixels(export, sweep.normalized_noise(export, 42), amplitude)


def test_hidden_truth_fields_are_rejected_before_treatment(inputs: tuple[Path, Path]) -> None:
    payload = json.loads(inputs[0].read_bytes())
    payload["frames"][0]["world_position"] = [1, 2, 3]
    with pytest.raises(ValueError, match="Extra inputs"):
        PilotObservationExport.model_validate(payload)


@pytest.mark.parametrize("reader", ["path_open", "path_read", "builtin_open", "io_open", "os_open"])
def test_runtime_read_allowlist_rejects_renamed_truth_and_mixed_exports(
    tmp_path: Path, reader: str,
) -> None:
    files = tuple(tmp_path / name for name in (
        "observations.json", "context.json", "scenario.json",
    ))
    for path in files:
        path.write_text("{}")
    renamed_truth = tmp_path / "innocent_name.json"
    renamed_truth.write_text('{"position":[1,2,3]}')
    with sweep.inference_read_guard(files, tmp_path / "output") as reads:
        assert files[0].read_text() == "{}"
        with pytest.raises(sweep.InferenceReadViolation, match="strict inputs"):
            if reader == "path_open":
                renamed_truth.open().close()
            elif reader == "path_read":
                renamed_truth.read_bytes()
            elif reader == "builtin_open":
                builtins.open(renamed_truth).close()
            elif reader == "io_open":
                io.open(renamed_truth).close()  # noqa: UP020 - exercise io.open capability.
            else:
                os.close(os.open(renamed_truth, os.O_RDONLY))
        assert reads == {"observations.json"}
    assert renamed_truth.read_text() == '{"position":[1,2,3]}'


@pytest.mark.parametrize("coverage,displacement,eligible,expected", [
    (True, .02, True, "STABLE"),
    (True, .020000001, True, "DEGRADED"),
    (False, 0.0, True, "ACCURACY_FAILURE"),
    (None, None, False, "INFERENCE_FAILURE"),
])
def test_predeclared_classification_separates_accuracy_from_complete_inference(
    coverage: bool | None, displacement: float | None, eligible: bool, expected: str,
) -> None:
    status = {"evaluation_eligible": eligible, "termination_reason": "COMPLETE"}
    metrics = {"status": "COMPUTED" if eligible else "NOT_COMPUTABLE",
               "summaries": [{"k": 3, "coverage_at_k": coverage}]}
    assert sweep.classify(status, metrics, {"max_scene_units": displacement}) == expected


def test_projection_comparison_uses_saved_points_and_rejects_mismatched_identity() -> None:
    baseline = {("CAM_A", 0, 0.0): (1, 2, 3), ("CAM_B", 3, 3.0): (4, 5, 6)}
    noisy = {("CAM_A", 0, 0.0): (1.003, 2.004, 3), ("CAM_B", 3, 3.0): (4, 5, 6)}
    result = sweep.projection_displacement(baseline, noisy)
    assert result["point_count"] == 2
    assert result["max_scene_units"] == pytest.approx(.005)
    assert result["rms_scene_units"] == pytest.approx(.005 / 2**.5)
    with pytest.raises(ValueError, match="identity"):
        sweep.projection_displacement(baseline, {("CAM_A", 1, 1.0): (1, 2, 3)})
    assert sweep.projection_displacement(baseline, {})["max_scene_units"] is None


def test_amplification_uses_actual_pixel_vector_norm_and_zero_noise_is_null() -> None:
    key, unchanged = ("CAM_A", 0, 0.0), ("CAM_B", 3, 3.0)
    baseline = {key: sweep.ProjectedSample((0, 0, 0), (0, 0)),
                unchanged: sweep.ProjectedSample((2, 3, 4), (5, 6))}
    noisy = {key: sweep.ProjectedSample((1, 0, 0), (.1, 0)), unchanged: baseline[unchanged]}
    report = sweep.projection_amplification(baseline, noisy)
    assert report["point_count"] == 2 and report["positive_pixel_norm_point_count"] == 1
    assert report["pixel_delta_norm_mean_px"] == pytest.approx(.05)
    assert report["pixel_delta_norm_rms_px"] == pytest.approx(.1 / 2**.5)
    assert report["pixel_delta_norm_max_px"] == pytest.approx(.1)
    assert report["point_amplification_mean_scene_units_per_pixel"] == 10
    assert report["point_amplification_max_scene_units_per_pixel"] == 10
    assert report["rms_amplification_scene_units_per_pixel"] == pytest.approx(10)
    assert report["max_amplification_sample"]["camera_id"] == "CAM_A"
    assert report["max_amplification_sample"]["frame_id"] == 0
    zero = sweep.projection_amplification(baseline, baseline)
    assert zero["positive_pixel_norm_point_count"] == 0
    assert zero["pixel_delta_norm_max_px"] == 0
    assert zero["point_amplification_mean_scene_units_per_pixel"] is None
    assert zero["point_amplification_max_scene_units_per_pixel"] is None
    assert zero["rms_amplification_scene_units_per_pixel"] is None
    assert zero["max_amplification_sample"] is None


def _fixture_source(inputs: tuple[Path, Path], tmp_path: Path) -> Any:
    source_root = tmp_path / "S01_office_medium"
    inputs_root = source_root / "fixture" / "inference"
    inputs_root.mkdir(parents=True)
    observations = json.loads(inputs[0].read_bytes())
    observations["site_id"] = "office"
    obs_path = inputs_root / "observations.json"
    obs_path.write_text(json.dumps(observations))
    context = json.loads(inputs[1].read_bytes())
    context["site_id"] = "office"
    context["observations_sha256"] = hashlib.sha256(obs_path.read_bytes()).hexdigest()
    (inputs_root / "projection_context.json").write_text(json.dumps(context))
    (inputs_root / "scenario_config.json").write_text(json.dumps({
        "label": PILOT_LABEL, "scenario_id": "S01_office_medium",
        "lateral_offset_scene_units": 12.0, "max_speed_scene_units_s": 32.0,
        "max_candidate_paths": 3, "random_seed": 20261006,
    }))
    return sweep._load_source(source_root)


def _write_evaluation_fixture_after_saved_inference(source: Any, run: Path) -> None:
    """A unit-test reference is constructed only after ordinary inference is frozen."""
    event = json.loads((run / "gap_events.json").read_bytes())["gaps"][0]["event"]
    points = event["trajectories"][0]["timed_points"]
    samples = []
    for timestamp in sorted({row.timestamp for row in source.observations.frames}):
        if timestamp <= points[0]["timestamp"]:
            position = points[0]["world_position"]
        elif timestamp >= points[-1]["timestamp"]:
            position = points[-1]["world_position"]
        else:
            index = bisect_right([row["timestamp"] for row in points], timestamp) - 1
            first, second = points[index:index + 2]
            ratio = (timestamp - first["timestamp"]) / (second["timestamp"] - first["timestamp"])
            position = [a + ratio * (b - a) for a, b in
                        zip(first["world_position"], second["world_position"], strict=True)]
        samples.append({"timestamp": timestamp, "position": position, "floor_id": "1F",
                        "trajectory_id": "evaluation-only-test-reference"})
    source.truth_path.parent.mkdir(parents=True)
    source.truth_path.write_text(json.dumps({
        "label": PILOT_LABEL, "provenance": "GROUND_TRUTH", "site_id": "office",
        "source_asset_sha256": "a" * 64, "trajectory_id": "evaluation-only-test-reference",
        "samples": samples,
    }))


def test_real_consumer_evaluator_repeat_poison_and_projection_prefix_are_preserved(
    inputs: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _fixture_source(inputs, tmp_path)
    draws = sweep.normalized_noise(source.observations, 20261006)
    # Seed the evaluation-only fixture from an already completed inference, not a fake runner.
    paths = sweep._prepare_variant(source, tmp_path / "reference-input", 0, 20261006, draws)
    status, read_paths = sweep._guarded_inference(paths, tmp_path / "reference-run")
    assert status["outcome"] == "SUCCESS" and status["candidate_count"] > 0
    assert "ground_truth.json" not in read_paths
    _write_evaluation_fixture_after_saved_inference(source, tmp_path / "reference-run")
    original_inputs = tuple((source.root / "fixture/inference" / name).read_bytes()
                            for name in source.input_digests)
    original_truth = source.truth_path.read_bytes()
    original_evaluator = sweep.evaluation.evaluate_saved_robustness
    calls = []

    def verify_frozen_first(run: Path, truth: Path, context: Path, **kwargs: Any) -> Any:
        assert sweep._freeze(run)["robustness_status.json"]
        assert (run / "events.json").is_file()
        calls.append(truth.name)
        return original_evaluator(run, truth, context, **kwargs)

    monkeypatch.setattr(sweep.evaluation, "evaluate_saved_robustness", verify_frozen_first)
    root = tmp_path / "variant"
    row, points = sweep._run_variant(source, root, 0, 20261006, draws, None)
    assert row["classification"] == "STABLE" and row["termination_reason"] == "COMPLETE"
    assert row["projected_displacement"]["max_scene_units"] == 0
    assert row["projection_amplification"]["point_amplification_max_scene_units_per_pixel"] is None
    assert row["metrics"][-1]["coverage_at_k"] is True
    assert len(points) == 4
    context = PilotInferenceContext.model_validate_json(
        (root / "input/projection_context.json").read_bytes())
    assert context.cameras == source.context.cameras and context.plane == source.context.plane
    assert context.zone == source.context.zone
    check = sweep._repeat_poison_check(source, root)
    assert check["repeat_inference_byte_equal"] and check["poison_inference_byte_equal"]
    assert check["poison_coverage_at_3"] is False
    assert calls == ["ground_truth.json", "poisoned_ground_truth.json"]
    assert source.truth_path.read_bytes() == original_truth
    assert tuple((source.root / "fixture/inference" / name).read_bytes()
                 for name in source.input_digests) == original_inputs
    for output in (root / "run_01", root / "repeat_run", root / "poison_run"):
        assert sweep.projected_evidence(output) == points
        assert len(points) == 4  # Six saved GAP samples are excluded from amplification.
        for path in output.glob("*.json"):
            assert json.loads(path.read_bytes())["label"] == PILOT_LABEL


def test_actual_search_failure_preserves_saved_projection_and_honest_null_metrics(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    source = _fixture_source(inputs, tmp_path)
    # Baseline points are read from a completed consumer; no GT exists for this case.
    draws = sweep.normalized_noise(source.observations, 42)
    paths = sweep._prepare_variant(source, tmp_path / "baseline-input", 0, 42, draws)
    sweep._guarded_inference(paths, tmp_path / "baseline-run")
    points = sweep.projected_evidence(tmp_path / "baseline-run")
    source = source._replace(configuration=source.configuration.model_copy(
        update={"max_speed_scene_units_s": .01}))
    row, projected = sweep._run_variant(source, tmp_path / "failure", 0, 42, draws, points)
    assert not source.truth_path.exists()
    assert row["classification"] == "INFERENCE_FAILURE"
    assert row["termination_reason"] == "NO_FEASIBLE_PATH" and row["failed_stage"] == "SEARCH"
    assert row["candidate_count"] == row["hypothesis_count"] == 0
    assert row["candidate_count_state"] == "SEARCH_RESULT"
    assert row["projected_displacement"]["status"] == "COMPUTED" and projected == points
    assert all(summary["coverage_at_k"] is None and summary["min_ade_at_k_scene_units"] is None
               for summary in row["metrics"])
    metrics = json.loads((tmp_path / "failure/run_01/metrics.json").read_bytes())
    assert metrics["ground_truth_read"] is False


def test_aggregations_keep_nonmonotonic_transitions_and_metric_ranges() -> None:
    rows = []
    for amplitude, classification, ade in ((0, "STABLE", .001), (.05, "ACCURACY_FAILURE", .1),
                                          (.1, "DEGRADED", .005)):
        rows.append({
            "source_scenario_id": "S01_office_medium", "noise_halfwidth_pixels": amplitude,
            "random_seed": 42, "classification": classification,
            "projected_displacement": {"max_scene_units": amplitude},
            "metrics": [{"k": k, "ade_first_primary_scene_units": ade,
                         "fde_first_primary_scene_units": ade,
                         "min_ade_at_k_scene_units": ade, "min_fde_at_k_scene_units": ade,
                         "coverage_at_k": classification != "ACCURACY_FAILURE"} for k in (1, 2, 3)],
        })
    aggregate, transitions = sweep.aggregate_rows(rows)
    assert len(aggregate) == 3
    assert aggregate[1]["metric_seed_ranges"]["3"]["min_ade_at_k_scene_units"] == [.1, .1]
    assert [(row["from"], row["to"]) for row in transitions] == [
        ("STABLE", "ACCURACY_FAILURE"), ("ACCURACY_FAILURE", "DEGRADED"),
    ]
