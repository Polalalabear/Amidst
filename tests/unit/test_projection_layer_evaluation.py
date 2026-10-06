"""Post-freeze GT decomposition never injects GT pixels into inverse inference."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext
from amidst.geometry.inverse_projection import InverseProjectionService

spec = importlib.util.spec_from_file_location(
    "projection_layer_evaluation",
    Path(__file__).parents[2] / "scripts/evaluate_projection_layers.py",
)
assert spec and spec.loader
layers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layers)


@pytest.fixture
def fixture(tmp_path):
    observed = tmp_path / "observations.json"
    frames = [
        {
            "frame_id": i,
            "timestamp": i / 5,
            "target_id": "target",
            "camera_id": camera,
            "status": "OBSERVED" if camera == "CAM_A" else "GAP",
            "point_2d": [50, 50] if camera == "CAM_A" else None,
            "provenance": "OBSERVED" if camera == "CAM_A" else None,
            "gap_reason": None if camera == "CAM_A" else "OCCLUDED",
            "data_kind": "SYNTHETIC",
        }
        for i in range(2)
        for camera in ("CAM_A", "CAM_B")
    ]
    observed.write_text(
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
            "spatial_context_id": "context",
            "source_asset_sha256": "a" * 64,
            "observations_sha256": hashlib.sha256(observed.read_bytes()).hexdigest(),
            "cameras": [
                {
                    "camera_id": camera,
                    "camera_to_world": [
                        [1, 0, 0, 0],
                        [0, 1, 0, 0],
                        [0, 0, 1, 10],
                        [0, 0, 0, 1],
                    ],
                    "fx": 100,
                    "fy": 100,
                    "cx": 50,
                    "cy": 50,
                    "width": 100,
                    "height": 100,
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
    context_path = tmp_path / "context.json"
    context_path.write_text(context.model_dump_json())
    truth = tmp_path / "ground_truth.json"
    truth.write_text(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "provenance": "GROUND_TRUTH",
                "source_asset_sha256": "a" * 64,
                "site_id": "TEST",
                "trajectory_id": "trajectory",
                "samples": [
                    {
                        "timestamp": i / 5,
                        "position": [0, 0, 0.0001],
                        "floor_id": "1F",
                        "trajectory_id": "trajectory",
                    }
                    for i in range(2)
                ],
            }
        )
    )
    return {
        "source_id": "fixture",
        "observations": str(observed),
        "context": str(context_path),
        "evaluation_truth": str(truth),
    }, truth


def test_gt_opens_after_frozen_projection_and_never_generates_inverse_frames(
    fixture,
    tmp_path,
    monkeypatch,
):
    source, truth = fixture
    out = tmp_path / "evaluation"
    original_read, original_project = Path.read_text, InverseProjectionService.project_frame
    calls = []

    def guarded_read(path, *args, **kwargs):
        if path == truth:
            assert (out / "frozen_projection_reference.json").is_file()
        return original_read(path, *args, **kwargs)

    def guarded_project(service, frame):
        assert frame.point_2d == (50.0, 50.0)
        calls.append(frame.frame_id)
        return original_project(service, frame)

    monkeypatch.setattr(Path, "read_text", guarded_read)
    monkeypatch.setattr(InverseProjectionService, "project_frame", guarded_project)
    report = layers.evaluate_projection_layers([source], out)
    assert calls == [0, 1]
    assert report["gt_pixels_never_passed_to_inverse_service"]
    assert report["frozen_projection_unchanged"]
    for row in report["samples"]:
        assert row["forward_export_pixel_residual"] == 0
        assert row["plane_selection_only_error_scene_units"] == pytest.approx(0.0001)
        assert row["export_pixel_calibration_residual_scene_units"] == 0
        assert row["total_baseline_inverse_error_vs_gt_scene_units"] == pytest.approx(0.0001)


def test_gt_poison_changes_evaluation_only_preserving_reference_bytes(fixture, tmp_path):
    source, truth = fixture
    first = layers.evaluate_projection_layers([source], tmp_path / "first")
    payload = json.loads(truth.read_text())
    for row in payload["samples"]:
        row["position"][0] += 10
    truth.write_text(json.dumps(payload))
    second = layers.evaluate_projection_layers([source], tmp_path / "second")
    assert (tmp_path / "first/frozen_projection_reference.json").read_bytes() == (
        tmp_path / "second/frozen_projection_reference.json"
    ).read_bytes()
    assert first["source_summaries"] != second["source_summaries"]


@pytest.mark.parametrize("key,value", [("site_id", "WRONG"), ("source_asset_sha256", "b" * 64)])
def test_wrong_gt_binding_rejected_after_freeze_without_evaluation(fixture, tmp_path, key, value):
    source, truth = fixture
    payload = json.loads(truth.read_text())
    payload[key] = value
    truth.write_text(json.dumps(payload))
    out = tmp_path / "rejected"
    with pytest.raises(ValueError, match="label/source/site"):
        layers.evaluate_projection_layers([source], out)
    assert (out / "frozen_projection_reference.json").exists()
    assert not (out / "layer_evaluation.json").exists()
