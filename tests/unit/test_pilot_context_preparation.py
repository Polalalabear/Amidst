"""Metadata preparation must never fit inference context to hidden GT."""

from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location(
    "prepare_pilot_downstream", ROOT / "scripts/prepare_pilot_downstream.py",
)
assert spec and spec.loader
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@pytest.fixture
def metadata_inputs(tmp_path: Path):
    original, derived = tmp_path / "original.blend", tmp_path / "derived.blend"
    original.write_bytes(b"immutable original geometry")
    derived.write_bytes(b"immutable geometry plus WALL selections")
    original_sha, derived_sha = prepare.sha256(original), prepare.sha256(derived)
    observations = {
        "label": prepare.LABEL, "data_kind": "SYNTHETIC", "site_id": "office",
        "source_asset_sha256": derived_sha,
        "frames": [{
            "frame_id": index, "timestamp": float(index), "target_id": "target",
            "camera_id": camera, "status": "OBSERVED", "point_2d": [50, 50],
            "provenance": "OBSERVED", "data_kind": "SYNTHETIC",
        } for index, camera in enumerate(("front", "rear"))],
    }
    obs_path, audit_path, dataset_path = (
        tmp_path / "observations.json", tmp_path / "audit.json", tmp_path / "dataset.json",
    )
    obs_path.write_text(json.dumps(observations))
    audit = {
        "source_sha256": original_sha, "geometry_objects": [
            {"id": "AREA_1F_OFFICE", "kind": "AREA", "floor": "1F",
             "bounds": [[-10, -10, -1], [10, 10, 1]]},
            {"id": "WALK_1F_OFFICE", "kind": "WALKABLE", "floor": "1F",
             "bounds": [[-10, -10, 0], [10, 10, 0]]},
        ],
    }
    audit_path.write_text(json.dumps(audit))
    dataset = {
        "label": prepare.LABEL, "site_id": "office",
        "source_scene": {
            "path": str(derived), "sha256_before": derived_sha, "sha256_after": derived_sha,
            "size_before": derived.stat().st_size, "mtime_ns_before": derived.stat().st_mtime_ns,
        },
        "source_lineage": {
            "original_source_path": str(original), "original_source_sha256": original_sha,
            "original_source_size": original.stat().st_size,
            "original_source_mtime_ns": original.stat().st_mtime_ns,
            "original_source_identity_verified": True,
            "wall_semantic_marking_policy": "ANNOTATION_ONLY_PHYSICAL_ROLE_NOT_APPROVED",
        },
        "trajectory": {
            "observation_plane_z": 0.0, "projection_plane_basis": {
                "purpose": "PILOT_DIAGNOSTIC_ONLY", "source_asset_sha256": derived_sha,
                "physical_floor_z": -0.1, "foot_clearance_units": 0.1,
                "landmark_offset_units": 0.0,
            },
        },
        "cameras": [{
            "camera_id": camera, "width": 100, "height": 100,
            "fx": 50, "fy": 50, "cx": 50, "cy": 50,
            "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 10], [0, 0, 0, 1]],
            "clip_start": 1, "clip_end": 20, "floor_id": "1F", "zone_id": camera,
        } for camera in ("front", "rear")],
        "timestamps": [{"ground_truth": {"position": [999, 998, 997]}}],
    }
    dataset_path.write_text(json.dumps(dataset))
    return dataset_path, obs_path, audit_path, dataset, observations, audit


def test_poisoning_or_removing_gt_does_not_change_exported_inference_context(metadata_inputs):
    dataset_path, obs_path, audit_path, dataset, _, _ = metadata_inputs
    baseline = prepare.prepare_context(dataset_path, obs_path, audit_path,
                                       dataset_path.parent / "baseline" / "context.json")
    poisoned = deepcopy(dataset)
    poisoned["timestamps"] = [{"ground_truth": "deliberately unreadable hidden positions"}]
    poisoned["trajectory"]["waypoints"] = [[-1e20, 1e20, -1e20]]
    dataset_path.write_text(json.dumps(poisoned))
    variant = prepare.prepare_context(dataset_path, obs_path, audit_path,
                                      dataset_path.parent / "poison" / "context.json")
    assert baseline == variant
    poisoned.pop("timestamps")
    dataset_path.write_text(json.dumps(poisoned))
    absent = prepare.prepare_context(dataset_path, obs_path, audit_path,
                                     dataset_path.parent / "absent" / "context.json")
    assert baseline == absent
    assert "ground_truth" not in baseline.model_dump_json()
    assert "waypoints" not in baseline.model_dump_json()


@pytest.mark.parametrize("change,match", [
    ("audit_source", "semantic metadata"),
    ("plane_source", "independent diagnostic"),
    ("plane_height", "independent mesh"),
    ("observation_source", "identities differ"),
    ("original_asset", "hash/size/mtime"),
])
def test_wrong_source_or_independent_plane_rejected_before_output(metadata_inputs, change, match):
    dataset_path, obs_path, audit_path, dataset, observations, audit = metadata_inputs
    if change == "audit_source":
        audit["source_sha256"] = "f" * 64
    elif change == "plane_source":
        dataset["trajectory"]["projection_plane_basis"]["source_asset_sha256"] = "f" * 64
    elif change == "plane_height":
        dataset["trajectory"]["observation_plane_z"] = 999
    elif change == "observation_source":
        observations["source_asset_sha256"] = "f" * 64
    elif change == "original_asset":
        Path(dataset["source_lineage"]["original_source_path"]).write_bytes(b"changed")
    dataset_path.write_text(json.dumps(dataset))
    obs_path.write_text(json.dumps(observations))
    audit_path.write_text(json.dumps(audit))
    output = dataset_path.parent / "new" / "context.json"
    with pytest.raises(ValueError, match=match):
        prepare.prepare_context(dataset_path, obs_path, audit_path, output)
    assert not output.exists()


def test_context_preparation_never_overwrites_prior_success(metadata_inputs):
    dataset_path, obs_path, audit_path, *_ = metadata_inputs
    output = dataset_path.parent / "context.json"
    prepare.prepare_context(dataset_path, obs_path, audit_path, output)
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        prepare.prepare_context(dataset_path, obs_path, audit_path, output)
    assert output.read_bytes() == before
