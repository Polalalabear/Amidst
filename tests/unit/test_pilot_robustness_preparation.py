"""Controlled export transformations preserve the inference/GT boundary."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts/prepare_pilot_robustness.py"
spec = importlib.util.spec_from_file_location("pilot_robustness_preparation", SCRIPT)
assert spec and spec.loader
preparation = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = preparation
spec.loader.exec_module(preparation)


@pytest.fixture
def source_fixture(tmp_path: Path):
    repository = tmp_path / "repository"
    source = repository / "blender/test.blend"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"asset identity fixture, never loaded by Blender")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    stat = source.stat()
    root = repository / "data/pilot/existing"
    root.mkdir(parents=True)
    cameras = [{
        "camera_id": camera, "camera_to_world": [
            [1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 10], [0, 0, 0, 1],
        ], "fx": 100, "fy": 100, "cx": 50, "cy": 50,
        "width": 100, "height": 100, "floor_id": "1F", "zone_id": camera,
    } for camera in ("CAM_A", "CAM_B")]
    frames = []
    for index in range(5):
        for camera in ("CAM_A", "CAM_B"):
            visible = index < 2 if camera == "CAM_A" else index >= 3
            frames.append({
                "frame_id": index, "timestamp": index / 5, "target_id": "target",
                "camera_id": camera, "status": "OBSERVED" if visible else "GAP",
                "point_2d": [45 + index, 50] if visible else None,
                "provenance": "OBSERVED" if visible else None,
                "gap_reason": None if visible else "OCCLUDED", "data_kind": "SYNTHETIC",
            })
    label = preparation.PILOT_LABEL
    (root / "observations.json").write_text(json.dumps({
        "label": label, "data_kind": "SYNTHETIC", "source_asset_sha256": digest,
        "frames": frames,  # Deliberate legacy no-site container.
    }))
    basis = {"source_asset_sha256": digest, "purpose": "PILOT_DIAGNOSTIC_ONLY",
             "physical_floor_z": 0, "foot_clearance_units": 0, "landmark_offset_units": 0}
    dataset = {
        "label": label,
        "source_scene": {"path": str(source), "sha256_before": digest, "sha256_after": digest,
                         "size_before": stat.st_size, "mtime_ns_before": stat.st_mtime_ns},
        "cameras": cameras,
        "trajectory": {"projection_plane_basis": basis, "observation_plane_z": 0,
                       "waypoints": [[999999, 999999, 999999]]},
        "timestamps": [{"ground_truth": "SECRET_MIXED_CONTAINER"}],
    }
    (root / "dataset.json").write_text(json.dumps(dataset))
    audit = repository / "data/scene_audit/school_v3_semantic_validation.json"
    audit.parent.mkdir(parents=True)
    audit.write_text(json.dumps({"source_sha256": digest, "geometry_objects": [
        {"id": name, "kind": kind, "floor": "1F", "bounds": [[-20, -20, -1], [20, 20, 1]]}
        for name, kind in (("AREA", "AREA"), ("WALK", "WALKABLE"))
    ]}))
    (root / "ground_truth.json").write_text(json.dumps({
        "label": label, "provenance": "GROUND_TRUTH", "source_asset_sha256": digest,
        "trajectory_id": "existing-trajectory", "samples": [
            {"timestamp": index / 5, "position": [index, 0, 0], "floor_id": "1F",
             "trajectory_id": "existing-trajectory"} for index in range(5)
        ],
    }))
    scenario = preparation.Scenario(
        "TEST", "site", "data/pilot/existing", "AREA", "WALK", "strict export fixture",
    )
    return repository, root, source, scenario


def test_preparation_never_opens_gt_and_drops_mixed_positions(
    source_fixture, tmp_path, monkeypatch,
):
    repository, root, _, scenario = source_fixture
    original = Path.read_text

    def guarded(path, *args, **kwargs):
        if path == root / "ground_truth.json":
            raise AssertionError("GT opened during inference preparation")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    out = tmp_path / "safe/inference"
    preparation.prepare_inference_fixture(repository, scenario, out)
    text = (out / "projection_context.json").read_text()
    assert "SECRET" not in text and "999999" not in text and "waypoints" not in text
    assert json.loads((out / "observations.json").read_text())["site_id"] == "site"


def test_poisoned_mixed_gt_cannot_change_any_consumer_input(source_fixture, tmp_path):
    repository, root, _, scenario = source_fixture
    first, second = tmp_path / "first/inference", tmp_path / "second/inference"
    preparation.prepare_inference_fixture(repository, scenario, first)
    payload = json.loads((root / "dataset.json").read_text())
    payload["trajectory"]["waypoints"] = "UNREADABLE_POISON"
    payload["timestamps"] = {"ground_truth": [1e30, -1e30, 1e30]}
    poisoned = tmp_path / "poisoned_mixed_dataset.json"
    poisoned.write_text(json.dumps(payload))
    preparation.prepare_inference_fixture(repository, scenario, second, dataset_path=poisoned)
    for name in ("observations.json", "projection_context.json", "scenario_config.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_seeded_noise_changes_only_visible_pixels_and_is_reproducible(source_fixture, tmp_path):
    repository, root, _, scenario = source_fixture
    noisy = replace(scenario, noise_half_width_pixels=0.25)
    first, second = tmp_path / "first/inference", tmp_path / "second/inference"
    preparation.prepare_inference_fixture(repository, noisy, first)
    preparation.prepare_inference_fixture(repository, noisy, second)
    assert (first / "observations.json").read_bytes() == (second / "observations.json").read_bytes()
    original = json.loads((root / "observations.json").read_text())["frames"]
    changed = json.loads((first / "observations.json").read_text())["frames"]
    for before, after in zip(original, changed, strict=True):
        if before["point_2d"] is None:
            assert after["point_2d"] is None and before["gap_reason"] == after["gap_reason"]
        else:
            assert any(a != b for a, b in zip(before["point_2d"], after["point_2d"], strict=True))
            assert all(abs(a - b) <= 0.25 for a, b in
                       zip(before["point_2d"], after["point_2d"], strict=True))


def test_true_camera_removal_deletes_records_and_calibration_without_faking_gaps(
    source_fixture, tmp_path,
):
    repository, _, _, scenario = source_fixture
    out = tmp_path / "removed/inference"
    preparation.prepare_inference_fixture(
        repository, replace(scenario, removed_camera="CAM_A"), out,
    )
    rows = json.loads((out / "observations.json").read_text())["frames"]
    context = json.loads((out / "projection_context.json").read_text())
    assert len(rows) == 5 and {r["camera_id"] for r in rows} == {"CAM_B"}
    assert len(context["cameras"]) == 1
    with pytest.raises(ValueError):
        preparation.PilotInferenceContext.model_validate(context)


def test_time_compression_is_predeclared_and_gt_export_is_separate(source_fixture, tmp_path):
    repository, root, source, scenario = source_fixture
    before = (source.read_bytes(), source.stat().st_mtime_ns)
    compressed = replace(scenario, time_scale=0.5)
    out = tmp_path / "compressed"
    preparation.prepare_inference_fixture(repository, compressed, out / "inference")
    preparation.prepare_evaluation_fixture(repository, compressed, out / "evaluation")
    rows = json.loads((out / "inference/observations.json").read_text())["frames"]
    gt = json.loads((out / "evaluation/ground_truth.json").read_text())["samples"]
    original = json.loads((root / "ground_truth.json").read_text())["samples"]
    assert sorted({r["timestamp"] for r in rows}) == [s["timestamp"] for s in gt]
    assert [s["timestamp"] for s in gt] == [s["timestamp"] * 0.5 for s in original]
    assert [s["position"] for s in gt] == [s["position"] for s in original]
    assert before == (source.read_bytes(), source.stat().st_mtime_ns)


@pytest.mark.parametrize("mutation", ["source", "plane", "hidden_observation"])
def test_source_plane_or_hidden_coordinate_drift_is_rejected(source_fixture, tmp_path, mutation):
    repository, root, source, scenario = source_fixture
    if mutation == "source":
        source.write_bytes(b"changed asset")
    elif mutation == "plane":
        dataset = json.loads((root / "dataset.json").read_text())
        dataset["trajectory"]["projection_plane_basis"]["source_asset_sha256"] = "f" * 64
        (root / "dataset.json").write_text(json.dumps(dataset))
    else:
        observations = json.loads((root / "observations.json").read_text())
        observations["frames"][0]["hidden_position"] = [1, 2, 3]
        (root / "observations.json").write_text(json.dumps(observations))
    with pytest.raises(ValueError):
        preparation.prepare_inference_fixture(repository, scenario, tmp_path / "rejected/inference")
