"""GT-free pilot adaptation preserves evidence, bindings and ordinary consumers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from amidst.datasets.pilot import (
    PILOT_LABEL,
    PilotInferenceContext,
    PilotObservationExport,
    load_pilot_projection,
    project_pilot_observations,
    run_pilot_downstream,
)
from amidst.domain.evidence import VisibilityStatus
from amidst.geometry.inverse_projection import InverseProjectionService


@pytest.fixture
def inputs(tmp_path: Path) -> tuple[Path, Path]:
    frames = []
    for index in range(5):
        for camera in ("CAM_A", "CAM_B"):
            visible = index < 2 if camera == "CAM_A" else index >= 3
            frames.append({
                "frame_id": index, "timestamp": float(index), "target_id": "pilot-target",
                "camera_id": camera, "status": "OBSERVED" if visible else "GAP",
                "point_2d": ([10 + index, 16] if camera == "CAM_A"
                             else [18 + index, 14]) if visible else None,
                "provenance": "OBSERVED" if visible else None,
                "gap_reason": None if visible else "OCCLUDED",
                "occluder_id": None if visible else "physical-mesh-id",
                "data_kind": "SYNTHETIC",
            })
    observation_path = tmp_path / "observations.json"
    observation_path.write_text(json.dumps({
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "source_asset_sha256": "a" * 64,
        "site_id": "TEST", "frames": frames,
    }))
    cameras = [{
        "camera_id": camera, "camera_to_world": [
            [1, 0, 0, 0], [0, 1, 0, offset], [0, 0, 1, 10], [0, 0, 0, 1],
        ], "fx": 10, "fy": 10, "cx": 16, "cy": 16, "width": 32, "height": 32,
        "floor_id": "1F", "zone_id": f"SOURCE_{camera}",
    } for camera, offset in (("CAM_A", 0), ("CAM_B", -2))]
    context = PilotInferenceContext.model_validate({
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "site_id": "TEST",
        "source_id": "pilot-test-source", "spatial_context_id": "pilot-test-context",
        "source_asset_sha256": "a" * 64,
        "observations_sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest(),
        "cameras": cameras,
        "plane": {"plane_id": "configured-pilot-plane", "point": [0, 0, 0],
                  "normal": [0, 0, 1], "floor_id": "1F", "zone_id": "TEST_ZONE"},
        "zone": {"floor_id": "1F", "zone_id": "TEST_ZONE", "walkable_object_id": "WALK_TEST",
                 "bounds_min": [-40, -40, -1], "bounds_max": [40, 40, 1],
                 "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL"},
    })
    context_path = tmp_path / "context.json"
    context_path.write_text(context.model_dump_json())
    return observation_path, context_path


def test_visible_projection_and_gap_nulls_preserve_original_2d_evidence(
    inputs: tuple[Path, Path],
) -> None:
    projection = load_pilot_projection(*inputs)
    assert projection.projected_observed_count == 4
    assert projection.gap_without_projection_count == 6
    by_key = {(row.camera_id, row.frame_id): row for row in projection.frames.samples}
    original = PilotObservationExport.model_validate_json(inputs[0].read_bytes())
    for frame in original.frames:
        row = by_key[(frame.camera_id, frame.frame_id)]
        assert row.uv == frame.point_2d
        assert row.timestamp == frame.timestamp
        if frame.status == VisibilityStatus.OBSERVED:
            assert row.projected_point is not None
            assert row.projected_point.provenance == "PROJECTED"
            assert row.projected_point.world_position[2] == 0
        else:
            assert row.projected_point is None and row.uv is None and row.provenance is None
            assert row.occluder_id == "physical-mesh-id"


def test_content_digest_mismatch_fails_before_projection(
    inputs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: object) -> None:
        pytest.fail("binding failure must precede projection")
    monkeypatch.setattr(InverseProjectionService, "project_frame", forbidden)
    inputs[0].write_text(inputs[0].read_text() + " ")
    with pytest.raises(ValueError, match="content SHA-256"):
        load_pilot_projection(*inputs)


@pytest.mark.parametrize("field,value", [
    ("source_asset_sha256", "b" * 64), ("site_id", "OTHER_SITE"),
])
def test_source_site_mismatch_fails_before_projection(
    inputs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, field: str, value: str,
) -> None:
    def forbidden(*_args: object) -> None:
        pytest.fail("source/site failure must precede projection")
    monkeypatch.setattr(InverseProjectionService, "project_frame", forbidden)
    observations = PilotObservationExport.model_validate_json(inputs[0].read_bytes())
    context = PilotInferenceContext.model_validate_json(inputs[1].read_bytes())
    with pytest.raises(ValueError, match="source/site"):
        project_pilot_observations(observations.model_copy(update={field: value}), context)


@pytest.mark.parametrize("location", ["header", "frame", "context", "camera"])
def test_hidden_truth_fields_are_rejected(
    inputs: tuple[Path, Path], location: str,
) -> None:
    path = inputs[0] if location in {"header", "frame"} else inputs[1]
    payload = json.loads(path.read_text())
    selected = payload["frames"][0] if location == "frame" else (
        payload["cameras"][0] if location == "camera" else payload
    )
    selected["ground_truth"] = [123, 456, 789]
    model = PilotObservationExport if location in {"header", "frame"} else PilotInferenceContext
    with pytest.raises(ValueError, match="Extra inputs"):
        model.model_validate(payload)


def test_unchecked_nested_truth_injection_is_rejected(inputs: tuple[Path, Path]) -> None:
    observations = PilotObservationExport.model_validate_json(inputs[0].read_bytes())
    context = PilotInferenceContext.model_validate_json(inputs[1].read_bytes())
    injected = observations.frames[0].model_copy(update={"ground_truth": (123, 456, 789)})
    forged = observations.model_copy(update={"frames": (injected, *observations.frames[1:])})
    with pytest.raises(ValueError, match="outside its declared contract"):
        project_pilot_observations(forged, context)


def test_ordinary_pipeline_outputs_are_labeled_and_source_inputs_preserved(
    inputs: tuple[Path, Path], tmp_path: Path,
) -> None:
    before = tuple(path.read_bytes() for path in inputs)
    output = tmp_path / "inference"
    run = run_pilot_downstream(*inputs, output, lateral_offset_scene_units=2)
    assert len(run.aggregation.observations) == 2
    assert len(run.gaps) == 1 and run.gaps[0].event.time_range == (1, 3)
    assert len(run.gaps[0].search_result.candidates) == 3
    assert run.report["ground_truth_read"] is False
    assert run.report["formal_benchmark_executed"] is False
    assert tuple(path.read_bytes() for path in inputs) == before
    for path in output.glob("*.json"):
        assert json.loads(path.read_text())["label"] == PILOT_LABEL
    assert "GROUND_TRUTH" not in (output / "events.json").read_text()
    assert "source_asset_sha256" in (output / "pipeline_config.json").read_text()
    with pytest.raises(FileExistsError):
        run_pilot_downstream(*inputs, output)


def test_truth_poison_and_missing_mixed_export_do_not_change_any_inference_artifact(
    inputs: tuple[Path, Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden_names = {"ground_truth.json", "dataset.json", "trajectory_plan.json"}
    original_open = Path.open
    def guarded_open(path: Path, *args: object, **kwargs: object):
        if path.name in forbidden_names:
            pytest.fail(f"inference attempted forbidden mixed/truth input {path.name}")
        return original_open(path, *args, **kwargs)
    truth = tmp_path / "ground_truth.json"
    truth.write_text('{"position":[1,2,3]}')
    monkeypatch.setattr(Path, "open", guarded_open)
    first, second = tmp_path / "first", tmp_path / "second"
    run_pilot_downstream(*inputs, first)
    # Change the evaluation-only file without using the guarded consumer file API.
    with original_open(truth, "w") as stream:
        stream.write('{"position":[999999,-999999,123456]}')
    run_pilot_downstream(*inputs, second)
    assert {path.name for path in first.iterdir()} == {path.name for path in second.iterdir()}
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
