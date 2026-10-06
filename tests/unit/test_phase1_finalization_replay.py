"""Technical replay enforces the GT boundary and reproducible policy/Graph outputs."""

from __future__ import annotations

import builtins
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from amidst.datasets.pilot import (
    PilotInferenceContext,
    PilotObservationExport,
    load_pilot_projection,
    project_pilot_observations,
)
from amidst.domain.camera import Camera
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import ObservationFrame
from amidst.domain.stream import RawProjectedFrameSample
from amidst.simulation.virtual_camera import project_world
from amidst.storage.json_files import write_json

SCRIPT = Path(__file__).parents[2] / "scripts" / "replay_phase1_finalization_diagnostics.py"
SPEC = importlib.util.spec_from_file_location("phase1_finalization_replay_tests", SCRIPT)
assert SPEC and SPEC.loader
replay = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = replay
SPEC.loader.exec_module(replay)


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    cameras = []
    for identity, x in (("a", -5), ("b", 5)):
        matrix = np.eye(4)
        matrix[0, 3] = x
        cameras.append(Camera(
            camera_id=identity, camera_to_world=matrix.tolist(), fx=500, fy=510,
            cx=640, cy=360, width=1280, height=720, clip_start=.1, clip_end=1000,
            floor_id="1F",
        ))
    frames = []
    truth_rows = []
    for index in range(5):
        position = (index - 2, .4, -10)
        truth_rows.append({"timestamp": float(index), "position": position,
                           "trajectory_id": "fixture", "floor_id": "1F"})
        for cam in cameras:
            visible = index < 2 if cam.camera_id == "a" else index > 2
            frames.append(ObservationFrame(
                frame_id=index, timestamp=float(index), target_id="target", camera_id=cam.camera_id,
                status="OBSERVED" if visible else "GAP",
                point_2d=project_world(cam, position).point_2d if visible else None,
                provenance="OBSERVED" if visible else None,
                gap_reason=None if visible else "OCCLUDED",
            ))
    observations = PilotObservationExport(
        label="PILOT / SYNTHETIC SAMPLE", data_kind="SYNTHETIC", site_id="fixture",
        source_asset_sha256="a" * 64, frames=tuple(frames),
    )
    observation_path = root / "inference/fixture/observations.json"
    write_json(observation_path, observations.model_dump(mode="json"))
    context = PilotInferenceContext.model_validate({
        "label": observations.label, "data_kind": "SYNTHETIC", "site_id": "fixture",
        "source_id": "fixture", "spatial_context_id": "context", "source_asset_sha256": "a" * 64,
        "observations_sha256": hashlib.sha256(observation_path.read_bytes()).hexdigest(),
        "cameras": cameras,
        "plane": {"plane_id": "landmark", "point": (0, 0, -10), "normal": (0, 0, 1),
                  "floor_id": "1F", "zone_id": "LOCAL"},
        "zone": {"floor_id": "1F", "zone_id": "LOCAL", "walkable_object_id": "fixture",
                 "bounds_min": (-40, -40, -11), "bounds_max": (40, 40, -9),
                 "authority": "ANNOTATION_AABB_ONLY_PROVISIONAL"},
    })
    write_json(root / "inference/fixture/context.json", context.model_dump(mode="json"))
    write_json(root / "evaluation/fixture/ground_truth.json", {
        "provenance": "GROUND_TRUTH", "site_id": "fixture", "source_asset_sha256": "a" * 64,
        "samples": truth_rows, "trajectory_id": "fixture",
    })
    write_json(root / "simulation/fixture/recipe.json", {"hidden_waypoints": truth_rows})
    write_json(root / "manifest.json", {
        "dataset_version": "fixture-v1", "source_sha256": "a" * 64,
        "config_sha256": "c" * 64, "streams": [{"stream": "fixture"}],
        "artifacts": {str(path.relative_to(root)): replay.digest(path)
                      for path in sorted(root.rglob("*.json"))},
    })
    return root


def test_inference_stage_and_preflight_never_read_gt_or_simulation(
    dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden = ("evaluation", "simulation")
    original_bytes, original_open = Path.read_bytes, Path.open
    original_builtin_open = builtins.open

    def reject(path: Any) -> None:
        if isinstance(path, (str, Path)) and any(part in Path(path).parts for part in forbidden):
            raise AssertionError("GT/simulation file entered inference boundary")

    def read_bytes(path: Path) -> bytes:
        reject(path)
        return original_bytes(path)

    def path_open(path: Path, *args: Any, **kwargs: Any) -> Any:
        reject(path)
        return original_open(path, *args, **kwargs)

    def builtin_open(path: Any, *args: Any, **kwargs: Any) -> Any:
        reject(path)
        return original_builtin_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(Path, "open", path_open)
    monkeypatch.setattr(builtins, "open", builtin_open)
    replay.verify_dataset(dataset)
    frozen = replay.infer_site(dataset, tmp_path / "inference_only", "fixture")
    assert frozen["graphs"]["policy"]["status"] == "DIAGNOSTIC"
    assert frozen["graphs"]["policy"]["projection_adapter_applied"] is True


def test_manifest_tampering_and_external_integrity_are_separate(dataset: Path) -> None:
    gt_path = dataset / "evaluation/fixture/ground_truth.json"
    gt_path.write_text("{}")
    replay.verify_dataset(dataset)
    with pytest.raises(ValueError, match="frozen manifest"):
        replay.verify_dataset(dataset, inference_only=False)
    (dataset / "inference/fixture/observations.json").write_text("{}")
    with pytest.raises(ValueError, match="frozen manifest"):
        replay.verify_dataset(dataset)


def test_policy_hook_preserves_default_and_rejects_evidence_rejection(dataset: Path) -> None:
    observations = dataset / "inference/fixture/observations.json"
    context = dataset / "inference/fixture/context.json"
    composer = replay.module("phase1_projection_policy")
    legacy = load_pilot_projection(observations, context)
    current = load_pilot_projection(observations, context, projector=composer.project_policy_frames)
    assert current.frames == legacy.frames

    def reject_one(
        inputs: PilotObservationExport, binding: PilotInferenceContext,
    ) -> FrameSampleDataset:
        frames = project_pilot_observations(inputs, binding)
        return FrameSampleDataset(samples=frames.samples[1:])

    with pytest.raises(ValueError, match="every original evidence"):
        load_pilot_projection(observations, context, projector=reject_one)

    def alter_pixels(
        inputs: PilotObservationExport, binding: PilotInferenceContext,
    ) -> FrameSampleDataset:
        frames = project_pilot_observations(inputs, binding)
        changed = RawProjectedFrameSample.model_validate(frames.samples[0].model_dump() | {
            "uv": (1, 2),
        })
        return FrameSampleDataset(samples=(changed, *frames.samples[1:]))

    with pytest.raises(ValueError, match="raw evidence"):
        load_pilot_projection(observations, context, projector=alter_pixels)


def test_complete_replay_fresh_process_poison_and_canonical_equality(
    dataset: Path, tmp_path: Path,
) -> None:
    first = replay.run(dataset, tmp_path / "first/replay", demos=False)
    second = replay.run(dataset, tmp_path / "second/replay", demos=False)
    assert first == second
    assert first["status"] == "DIAGNOSTIC_TECHNICAL_PASS"
    row = first["streams"][0]
    assert row["projection_byte_identical"] is True
    assert row["gt_poison_changes_only_evaluation"] is True
    assert row["legacy_graph"]["byte_identical"] is True
    assert row["policy_graph"]["byte_identical"] is True
    assert row["policy_graph"]["termination"] == "COMPLETE"
    assert row["policy_graph"]["projection_adapter_applied"] is True
    assert row["formal_cases_executed"] is False
    assert all("runtime.json" not in path and not path.endswith(".rrd")
               for path in first["canonical_artifacts"])
    assert (tmp_path / "first/verification.json").exists()
    assert (tmp_path / "first/diagnostics.json").exists()


def test_demo_saves_hidden_gt_and_preview_from_frozen_inference(
    dataset: Path, tmp_path: Path,
) -> None:
    frozen = replay.infer_site(dataset, tmp_path / "demo_site", "fixture")
    result = replay.evaluate_site(dataset, tmp_path / "demo_site", "fixture", frozen)
    assert result["demo"]["rrd_saved"] is True
    assert result["demo"]["gt_default_visible"] is False
    output = tmp_path / "demo_site/demo"
    assert (output / "diagnostic.rrd").stat().st_size > 1000
    assert (output / "preview.png").stat().st_size > 1000
    presentation = json.loads((output / "presentation.json").read_bytes())
    assert presentation["gt_debug_default_visible"] is False
    assert presentation["authority"] == "PROVISIONAL_NOT_CERTIFIED"
    assert presentation["full_school_mesh_displayed"] is False
    assert presentation["collision_pruned_candidate"].startswith("N/A")


def test_wrong_reference_binding_is_rejected(dataset: Path, tmp_path: Path) -> None:
    replay.infer_site(dataset, tmp_path / "bound_site", "fixture")
    sidecar = json.loads((tmp_path / "bound_site/primary.json").read_bytes())
    gt = json.loads((dataset / "evaluation/fixture/ground_truth.json").read_bytes())
    with pytest.raises(ValueError, match="source and GT provenance"):
        replay.projection_error(sidecar, gt | {"site_id": "other"})
