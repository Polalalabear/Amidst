"""Completed inference is frozen before GT evaluation and never reordered by it."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from bisect import bisect_right
from pathlib import Path

import pytest

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, run_pilot_downstream

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location(
    "evaluate_pilot_downstream", ROOT / "scripts/evaluate_pilot_downstream.py",
)
assert spec and spec.loader
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


@pytest.fixture
def completed(tmp_path: Path):
    observations = tmp_path / "observations.json"
    frames = []
    for index in range(5):
        for camera in ("CAM_A", "CAM_B"):
            visible = index < 2 if camera == "CAM_A" else index >= 3
            frames.append({
                "frame_id": index, "timestamp": float(index), "target_id": "target",
                "camera_id": camera, "status": "OBSERVED" if visible else "GAP",
                "point_2d": [16 + index - 2, 16] if visible else None,
                "provenance": "OBSERVED" if visible else None,
                "gap_reason": None if visible else "OCCLUDED", "data_kind": "SYNTHETIC",
            })
    observations.write_text(json.dumps({
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "site_id": "TEST",
        "source_asset_sha256": "a" * 64, "frames": frames,
    }))
    context = PilotInferenceContext.model_validate({
        "label": PILOT_LABEL, "data_kind": "SYNTHETIC", "site_id": "TEST",
        "source_id": "source", "spatial_context_id": "scene", "source_asset_sha256": "a" * 64,
        "observations_sha256": hashlib.sha256(observations.read_bytes()).hexdigest(),
        "cameras": [{
            "camera_id": camera, "camera_to_world": [
                [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 10], [0, 0, 0, 1],
            ], "fx": 10, "fy": 10, "cx": 16, "cy": 16, "width": 32, "height": 32,
            "floor_id": "1F", "zone_id": camera,
        } for camera in ("CAM_A", "CAM_B")],
        "plane": {"plane_id": "plane", "point": [0, 0, 0], "normal": [0, 0, 1],
                  "floor_id": "1F", "zone_id": "zone"},
        "zone": {"floor_id": "1F", "zone_id": "zone", "walkable_object_id": "walk",
                 "bounds_min": [-20, -20, -1], "bounds_max": [20, 20, 1],
                 "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL"},
    })
    context_path, output = tmp_path / "context.json", tmp_path / "run"
    context_path.write_text(context.model_dump_json())
    run = run_pilot_downstream(observations, context_path, output, lateral_offset_scene_units=0.5)
    # Build an evaluation reference matching the third route AFTER inference.
    # This deliberately makes the first primary route worse than minADE@3.
    event = run.gaps[0].event
    assert len(event.candidates) == 3
    final_candidate = event.candidates[-1].candidate_id
    third = next(t for t in event.trajectories if t.candidate_id == final_candidate)
    points = third.timed_points
    samples = []
    for timestamp in range(5):
        if timestamp <= points[0].timestamp:
            position = points[0].world_position
        elif timestamp >= points[-1].timestamp:
            position = points[-1].world_position
        else:
            index = bisect_right([p.timestamp for p in points], timestamp) - 1
            first, second = points[index:index + 2]
            fraction = (timestamp - first.timestamp) / (second.timestamp - first.timestamp)
            position = tuple(a + fraction * (b - a) for a, b in zip(
                first.world_position, second.world_position, strict=True,
            ))
        samples.append({"timestamp": float(timestamp), "position": position,
                        "floor_id": "1F", "trajectory_id": "test-trajectory"})
    truth = tmp_path / "ground_truth.json"
    truth.write_text(json.dumps({
        "label": PILOT_LABEL, "provenance": "GROUND_TRUTH", "source_asset_sha256": "a" * 64,
        "site_id": "TEST", "trajectory_id": "test-trajectory", "samples": samples,
    }))
    return output, truth, context_path, event


def test_gt_compatible_third_route_changes_metrics_only_never_top_k_order(completed):
    output, truth, context, event = completed
    before = evaluation.artifact_digests(output)
    report = evaluation.evaluate_saved_pilot(output, truth, context)
    one, _, three = report["summaries"]
    assert one["ade_first_primary_scene_units"] > 0.1
    assert not one["coverage_at_k"]
    assert three["min_ade_at_k_scene_units"] < 1e-9 and three["coverage_at_k"]
    assert three["ade_first_primary_scene_units"] == one["ade_first_primary_scene_units"]
    assert evaluation.artifact_digests(output) == before
    metrics = report["configured_evaluation"]["evaluations"][-1]
    selected = metrics["top_k_hypothesis_ids"]
    primary = []
    seen = set()
    for hypothesis in event.trajectories:
        if hypothesis.candidate_id not in seen:
            seen.add(hypothesis.candidate_id)
            primary.append(hypothesis.hypothesis_id)
    assert selected == primary
    assert report["physical_validity"]["blender_mesh_collision_rate"] is None
    assert report["physical_validity"]["status"] == "PARTIAL_PROVISIONAL"


def test_poisoned_gt_changes_evaluation_only_and_preserves_all_inference_bytes(completed):
    output, truth, context, _ = completed
    second = output.with_name("poisoned_run")
    shutil.copytree(output, second)
    baseline = evaluation.evaluate_saved_pilot(output, truth, context)
    payload = json.loads(truth.read_text())
    for sample in payload["samples"]:
        sample["position"] = [v + 10000 for v in sample["position"]]
    truth.write_text(json.dumps(payload))
    changed = evaluation.evaluate_saved_pilot(second, truth, context)
    assert baseline["summaries"] != changed["summaries"]
    assert changed["summaries"][-1]["ade_first_primary_scene_units"] > 10000
    assert evaluation.artifact_digests(output) == evaluation.artifact_digests(second)


@pytest.mark.parametrize("field,value", [
    ("source_asset_sha256", "b" * 64), ("site_id", "WRONG"),
])
def test_wrong_gt_binding_rejected_without_metric_outputs(completed, field, value):
    output, truth, context, _ = completed
    payload = json.loads(truth.read_text())
    payload[field] = value
    truth.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="source/site/provenance"):
        evaluation.evaluate_saved_pilot(output, truth, context)
    assert not (output / "metrics.json").exists()


def test_wrong_gt_time_extent_rejected_instead_of_extrapolating(completed):
    output, truth, context, _ = completed
    payload = json.loads(truth.read_text())
    payload["samples"].pop()
    truth.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="ordered pilot timestamps"):
        evaluation.evaluate_saved_pilot(output, truth, context)
    assert not (output / "metrics.json").exists()


def test_invalid_inference_fails_before_opening_truth(completed, monkeypatch):
    output, truth, context, _ = completed
    gap_file = output / "gap_events.json"
    gap_payload = json.loads(gap_file.read_text())
    gap_payload["label"] = "UNLABELED"
    gap_file.write_text(json.dumps(gap_payload))
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if path == truth:
            pytest.fail("invalid saved inference must be rejected before GT access")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    with pytest.raises(ValueError, match="must be labeled"):
        evaluation.evaluate_saved_pilot(output, truth, context)
