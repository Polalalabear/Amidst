"""Projection availability is honest and accepted points use ordinary downstream logic."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from test_pilot_downstream_consumer import inputs as inputs

from amidst.datasets.pilot import (
    PILOT_LABEL,
    PilotInferenceContext,
    PilotObservationExport,
    load_pilot_projection,
    project_pilot_observations,
    run_pilot_downstream,
)
from amidst.domain.common import Provenance
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import GapReason, VisibilityStatus
from amidst.domain.stream import OcclusionState


def _module(name: str, filename: str) -> Any:
    script = Path(__file__).resolve().parents[2] / "scripts" / filename
    spec = importlib.util.spec_from_file_location(name, script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


adapter = _module("test_mitigation_adapter", "run_projection_mitigation_downstream.py")
evaluation = _module("test_mitigation_evaluator", "evaluate_pilot_robustness.py")


def _scenario() -> Any:
    return adapter.robustness.RobustnessScenario.model_validate({
        "label": PILOT_LABEL, "scenario_id": "MITIGATION_DIAGNOSTIC_TEST",
        "lateral_offset_scene_units": 12.0, "max_speed_scene_units_s": 32.0,
        "max_candidate_paths": 3, "random_seed": 20261006,
    })


def _decisions(dataset: FrameSampleDataset) -> dict[tuple[str, int, float], bool]:
    return {
        (row.camera_id, row.frame_id, float(row.timestamp)): True
        for row in dataset.samples if row.visibility == VisibilityStatus.OBSERVED
    }


def test_baseline_and_confidence_only_preserve_coordinates_quality_and_ordinary_artifacts(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    projection = load_pilot_projection(*inputs)
    before = projection.frames.model_dump(mode="json")
    adapted = adapter.adapt_projected_frames(projection.frames, _decisions(projection.frames))
    assert adapted.model_dump(mode="json") == before
    ordinary, diagnostic = tmp_path / "ordinary", tmp_path / "diagnostic"
    original_run = run_pilot_downstream(*inputs, ordinary, random_seed=20261006)
    status = adapter.run_projected_downstream(adapted, projection.context, _scenario(), diagnostic)
    assert status["termination_reason"] == "COMPLETE"
    assert status["candidate_count"] == original_run.report["candidate_count"] > 0
    assert status["hypothesis_count"] == original_run.report["hypothesis_count"]
    assert status["ground_truth_read"] is False
    for name in (
        "projected_frames.json", "aggregation.json", "pipeline_config.json",
        "topology_evidence.json",
        "gap_events.json", "candidates.json", "events.json",
    ):
        assert (ordinary / name).read_bytes() == (diagnostic / name).read_bytes()
    assert set(status["available_artifacts"]) == set(adapter.INFERENCE_FILES)
    assert projection.frames.model_dump(mode="json") == before


def test_rejection_is_unknown_geometry_availability_and_preserves_true_gap_records(
    inputs: tuple[Path, Path],
) -> None:
    projection = load_pilot_projection(*inputs)
    decisions = _decisions(projection.frames)
    decisions[("CAM_A", 1, 1.0)] = False
    adapted = adapter.adapt_projected_frames(projection.frames, decisions)
    original = {row.sample_id: row for row in projection.frames.samples}
    for row in adapted.samples:
        source = original[row.sample_id]
        if row.camera_id == "CAM_A" and row.frame_id == 1:
            assert row.visibility == VisibilityStatus.GAP
            assert row.gap_reason == GapReason.GEOMETRY_UNCERTAIN
            assert row.occlusion_state == OcclusionState.UNKNOWN
            assert row.uv is None and row.projected_point is None and row.provenance is None
            assert row.occluder_id is None and row.confidence is None
        else:
            assert row.model_dump(mode="json") == source.model_dump(mode="json")
    assert original[next(row.sample_id for row in adapted.samples
                         if row.camera_id == "CAM_A" and row.frame_id == 1)].uv is not None
    assert len(adapted.samples) == len(projection.frames.samples)


def test_retained_actual_endpoint_changes_gap_window_without_fabrication(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    projection = load_pilot_projection(*inputs)
    decisions = _decisions(projection.frames)
    decisions[("CAM_A", 1, 1.0)] = False
    adapted = adapter.adapt_projected_frames(projection.frames, decisions)
    output = tmp_path / "retained"
    status = adapter.run_projected_downstream(adapted, projection.context, _scenario(), output)
    assert status["evaluation_eligible"] is True
    assert status["gap_window"] == (0, 3)
    assert status["gap_window_state"] == "ACTUAL_RETAINED_PROJECTED_OBSERVATION_ENDPOINTS"
    event = json.loads((output / "gap_events.json").read_text())["gaps"][0]["event"]
    assert event["time_range"] == [0, 3]
    retained = next(row.projected_point for row in adapted.samples
                    if row.camera_id == "CAM_A" and row.timestamp == 0)
    assert event["trajectories"][0]["timed_points"][0]["world_position"] == list(
        retained.world_position
    )


@pytest.mark.parametrize("remove_all", [False, True])
def test_missing_endpoint_stops_search_and_null_metrics_without_truth_access(
    inputs: tuple[Path, Path], tmp_path: Path, remove_all: bool,
) -> None:
    projection = load_pilot_projection(*inputs)
    decisions = _decisions(projection.frames)
    decisions = {key: False if remove_all or key[0] == "CAM_A" else True
                 for key in decisions}
    adapted = adapter.adapt_projected_frames(projection.frames, decisions)
    output = tmp_path / "insufficient"
    status = adapter.run_projected_downstream(adapted, projection.context, _scenario(), output)
    assert status["reason"] == "INSUFFICIENT_PROJECTED_ENDPOINT_EVIDENCE"
    assert status["termination_reason"] == "NOT_RUN"
    assert status["candidate_count_state"] == "NOT_RUN"
    assert status["stage_states"]["TOPOLOGY"] == "NOT_RUN"
    assert status["search_executed"] is False and status["evaluation_eligible"] is False
    assert not (output / "gap_events.json").exists()
    assert (output / "aggregation.json").is_file()
    metrics = evaluation.evaluate_saved_robustness(
        output, tmp_path / "NONEXISTENT_TRUTH.json", tmp_path / "NONEXISTENT_CONTEXT.json",
    )
    assert metrics["status"] == "NOT_COMPUTABLE" and metrics["ground_truth_read"] is False
    assert all(row["coverage_at_k"] is None and row["min_ade_at_k_scene_units"] is None
               for row in metrics["summaries"])


def test_selective_rejection_fragmentation_preserves_prefix_and_stops_before_topology(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    observation = json.loads(inputs[0].read_text())
    for row in observation["frames"]:
        if row["camera_id"] == "CAM_A" and row["frame_id"] == 2:
            row.update(status="OBSERVED", point_2d=[12, 16], provenance="OBSERVED",
                       gap_reason=None, occluder_id=None)
        if row["camera_id"] == "CAM_B" and row["frame_id"] == 3:
            row.update(status="GAP", point_2d=None, provenance=None,
                       gap_reason="OCCLUDED", occluder_id="physical-mesh-id")
    context = PilotInferenceContext.model_validate_json(inputs[1].read_bytes())
    dataset = project_pilot_observations(
        PilotObservationExport.model_validate(observation), context,
    )
    decisions = _decisions(dataset)
    decisions[("CAM_A", 1, 1.0)] = False
    adapted = adapter.adapt_projected_frames(dataset, decisions)
    output = tmp_path / "fragmented"
    status = adapter.run_projected_downstream(adapted, context, _scenario(), output)
    assert status["observation_count"] == 3
    assert status["reason"] == "UNSUPPORTED_FRAGMENTED_PROJECTED_EVIDENCE"
    assert status["stage_states"]["AGGREGATION"] == "PASSED"
    assert status["stage_states"]["TOPOLOGY"] == "NOT_RUN"
    assert status["termination_reason"] == "NOT_RUN"
    assert not (output / "pipeline_config.json").exists()
    assert not (output / "events.json").exists()


@pytest.mark.parametrize("location", ["dataset", "sample", "point", "context", "scenario"])
def test_unchecked_hidden_ground_truth_is_rejected_before_output(
    inputs: tuple[Path, Path], tmp_path: Path, location: str,
) -> None:
    projection = load_pilot_projection(*inputs)
    dataset, context, scenario = projection.frames, projection.context, _scenario()
    if location == "dataset":
        dataset = dataset.model_copy(update={"ground_truth": [99, 99, 99]})
    elif location in {"sample", "point"}:
        sample = next(row for row in dataset.samples if row.projected_point is not None)
        if location == "sample":
            modified = sample.model_copy(update={"ground_truth": [99, 99, 99]})
        else:
            modified = sample.model_copy(update={
                "projected_point": sample.projected_point.model_copy(
                    update={"provenance": Provenance.GROUND_TRUTH},
                ),
            })
        dataset = dataset.model_copy(update={"samples": tuple(
            modified if row.sample_id == sample.sample_id else row for row in dataset.samples
        )})
    elif location == "context":
        camera = context.cameras[0].model_copy(update={"ground_truth": [99, 99, 99]})
        context = context.model_copy(update={"cameras": (camera, *context.cameras[1:])})
    else:
        scenario = scenario.model_copy(update={"ground_truth": [99, 99, 99]})
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        adapter.run_projected_downstream(dataset, context, scenario, output)
    assert not output.exists()
    if location in {"dataset", "sample", "point"}:
        with pytest.raises(ValueError):
            adapter.adapt_projected_frames(dataset, _decisions(projection.frames))


@pytest.mark.parametrize("change", ["missing", "extra", "nonboolean"])
def test_decision_map_requires_complete_observed_keys_and_strict_booleans(
    inputs: tuple[Path, Path], change: str,
) -> None:
    projection = load_pilot_projection(*inputs)
    decisions = _decisions(projection.frames)
    if change == "missing":
        decisions.pop(next(iter(decisions)))
    elif change == "extra":
        decisions[("CAM_A", 99, 99.0)] = True
    else:
        decisions[next(iter(decisions))] = 1
    with pytest.raises(ValueError):
        adapter.adapt_projected_frames(projection.frames, decisions)


def test_binding_mismatch_and_unprojected_visible_evidence_rejected_before_output(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    projection = load_pilot_projection(*inputs)
    context = projection.context.model_copy(update={"source_id": "OTHER"})
    output = tmp_path / "binding-invalid"
    with pytest.raises(ValueError, match="binding"):
        adapter.run_projected_downstream(projection.frames, context, _scenario(), output)
    visible = next(row for row in projection.frames.samples if row.projected_point is not None)
    altered = visible.model_copy(update={"projected_point": None})
    dataset = FrameSampleDataset(samples=tuple(
        altered if row.sample_id == visible.sample_id else row for row in projection.frames.samples
    ))
    with pytest.raises(ValueError, match="projected points"):
        adapter.adapt_projected_frames(dataset, _decisions(dataset))
    assert not output.exists()


def test_repeat_is_byte_identical_and_never_reads_unrelated_input_files(
    inputs: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = load_pilot_projection(*inputs)
    root = tmp_path / "outputs"
    root.mkdir()
    original_open = Path.open

    def guarded(path: Path, *args: Any, **kwargs: Any) -> Any:
        mode = args[0] if args else kwargs.get("mode", "r")
        if mode.startswith("r") and not path.is_relative_to(root):
            pytest.fail(f"already projected inference tried reading unrelated input {path}")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded)
    first, second = root / "first", root / "second"
    adapter.run_projected_downstream(projection.frames, projection.context, _scenario(), first)
    adapter.run_projected_downstream(projection.frames, projection.context, _scenario(), second)
    assert {path.name for path in first.iterdir()} == {path.name for path in second.iterdir()}
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    with pytest.raises(FileExistsError):
        adapter.run_projected_downstream(projection.frames, projection.context, _scenario(), first)


def test_successful_saved_adapter_outputs_use_unchanged_evaluator_after_freeze(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    projection = load_pilot_projection(*inputs)
    output = tmp_path / "evaluation-compatible"
    status = adapter.run_projected_downstream(
        projection.frames, projection.context, _scenario(), output,
    )
    assert status["evaluation_eligible"] is True
    frozen = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    event = json.loads((output / "gap_events.json").read_text())["gaps"][0]["event"]
    points = event["trajectories"][0]["timed_points"]
    samples = []
    # The test reference is created only after frozen ordinary inference exists.
    for timestamp in sorted({row.timestamp for row in projection.frames.samples}):
        if timestamp <= points[0]["timestamp"]:
            position = points[0]["world_position"]
        elif timestamp >= points[-1]["timestamp"]:
            position = points[-1]["world_position"]
        else:
            first, second = next(
                (first, second)
                for first, second in zip(points[:-1], points[1:], strict=True)
                if first["timestamp"] <= timestamp <= second["timestamp"]
            )
            ratio = (timestamp - first["timestamp"]) / (second["timestamp"] - first["timestamp"])
            position = [a + ratio * (b - a) for a, b in zip(
                first["world_position"], second["world_position"], strict=True,
            )]
        samples.append({
            "timestamp": timestamp, "position": position, "floor_id": "1F",
            "trajectory_id": "evaluation-only-fixture",
        })
    truth_path = tmp_path / "ground_truth.json"
    truth_path.write_text(json.dumps({
        "label": PILOT_LABEL, "provenance": "GROUND_TRUTH", "site_id": "TEST",
        "source_asset_sha256": "a" * 64, "trajectory_id": "evaluation-only-fixture",
        "samples": samples,
    }))
    result = evaluation.evaluate_saved_robustness(output, truth_path, inputs[1])
    assert result["status"] == "COMPUTED"
    assert result["coverage_epsilon_scene_units"] == .02
    assert result["inference_artifacts_unchanged_after_evaluation"] is True
    assert all(row["coverage_at_k"] is True for row in result["summaries"])
    assert {name: (output / name).read_bytes() for name in frozen} == frozen
