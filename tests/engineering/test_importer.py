"""Reviewed adapter certification tests use a tiny explicit synthetic package."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.domain.camera import Camera
from amidst.domain.observation import ProjectedPoint
from amidst.domain.stream import RawProjectedFrameSample
from amidst.engineering import importer
from amidst.engineering.registry import IDENTITY4
from amidst.observation.aggregation import aggregate_frames


def write(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True))
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def package(tmp_path: Path) -> dict[str, Any]:
    root = tmp_path / "reviewed-synthetic-fixture"
    source = tmp_path / "test-source.blend"
    source.write_bytes(b"explicit synthetic adapter test source; not a school model")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    scale = tmp_path / "scale.json"
    write(scale, {"source_asset_sha256": source_hash, "metres_per_blender_unit": 0.0247,
                  "authority": "APPROVED", "approval_id": "synthetic-fixture-approval",
                  "evidence_ids": ["test-fixture-only"]})
    cameras = [Camera(camera_id=identity, camera_to_world=IDENTITY4, fx=100, fy=100,
                      cx=160, cy=120, width=320, height=240).model_dump(mode="json")
               for identity in ("CAM_A", "CAM_B")]
    dataset_artifacts = {}
    dataset_artifacts["inference/case1/observations.json"] = write(
        root / "dataset/inference/case1/observations.json", {"image_measurement": False}
    )
    native = {"source_asset_sha256": source_hash, "source_id": "reviewed:fixture",
              "spatial_context_id": "fixture-office", "cameras": cameras,
              "observations_sha256": dataset_artifacts["inference/case1/observations.json"]}
    dataset_artifacts["inference/case1/context.json"] = write(
        root / "dataset/inference/case1/context.json", native
    )
    dataset_artifacts["evaluation/ground_truth.json"] = write(
        root / "dataset/evaluation/ground_truth.json", {"do_not_deserialize_gt": "actor-secret"}
    )
    samples = tuple(RawProjectedFrameSample(
        sample_id=f"sample:{i}", source_id=native["source_id"],
        spatial_context_id=native["spatial_context_id"], source_asset_sha256=source_hash,
        target_id="historical-structured-fixture-target", camera_id=cameras[i]["camera_id"],
        timestamp=float(i), frame_id=i * 5, uv=(120, 150), visibility="OBSERVED",
        provenance="OBSERVED", projected_point=ProjectedPoint(
            point_id=f"point:{i}", camera_id=cameras[i]["camera_id"], plane_id="fixture-plane",
            timestamp=float(i), world_position=(1, 2, 0.247)),
    ) for i in range(2))
    aggregation = aggregate_frames(samples)
    inference_artifacts = {}
    inference_artifacts["case1/aggregation.json"] = write(
        root / "inference_primary/case1/aggregation.json", aggregation.model_dump(mode="json")
    )
    inference_artifacts["case1/reviewed_context.json"] = write(
        root / "inference_primary/case1/reviewed_context.json", {
            "computation_context": native, "coordinate_units": "METRES_AFTER_NATIVE_PROJECTION",
            "conversion": "SUBTRACT_SOURCE_BOUND_Z_OFFSET_KEEP_XY", "offset_bu": 2,
            "offset_m": 2 * 0.0247,
        }
    )
    inference_artifacts["case1/projection.json"] = write(
        root / "inference_primary/case1/projection.json", {
            "ground_truth_read": False, "source_asset_sha256": source_hash,
            "observations_sha256": native["observations_sha256"], "rows": [{
                "timestamp": sample.timestamp, "frame_id": sample.frame_id,
                "target_id": sample.target_id, "ground_truth_read": False,
                "selection_uses_ground_truth": False,
                "selected_world_position": [1 / 0.0247, 2 / 0.0247, 12],
            } for sample in samples],
        }
    )
    inference_artifacts["case1/full_deterministic_graph.json"] = write(
        root / "inference_primary/case1/full_deterministic_graph.json", {
            "event": {"event_id": "canonical:event-unchanged", "target_id": samples[0].target_id,
                      "time_range": [0, 1], "observation_ids": [
                          item.observation.observation_id for item in aggregation.observations
                      ], "candidates": [], "termination_reason": "NO_FEASIBLE_PATH"},
            "timed_result": {"candidates": [], "complete": True, "expanded_nodes": 0,
                             "rejection_reasons": [], "termination_reason": "NO_FEASIBLE_PATH"},
        }
    )
    dataset_hash = write(root / "dataset/manifest.json", {
        "schema_version": "phase1-reviewed-dataset-v1",
        "coordinate_storage": "BLENDER_NATIVE_UNITS",
        "scale_authority": "APPROVED", "metres_per_blender_unit": 0.0247, "sampling_fps": 5,
        "source_sha256": source_hash, "source_size_bytes": source.stat().st_size,
        "cases": [{"case_id": "case1", "status": "EXPORTED"},
                  {"case_id": "case2", "status": "BLOCKED"}], "artifacts": dataset_artifacts,
    })
    freeze_hash = write(root / "inference_primary/inference_freeze.json", {
        "schema_version": "phase1-reviewed-inference-freeze-v1",
        "status": "FROZEN_BEFORE_EVALUATION",
        "ground_truth_read": False, "dataset_manifest_sha256": dataset_hash,
        "config_sha256": "a" * 64, "artifacts": inference_artifacts,
    })
    return {"run_root": root, "source_scene": source, "scale_path": scale,
            "expected_dataset_sha256": dataset_hash, "expected_freeze_sha256": freeze_hash}


def alter_inference(package: dict[str, Any], relative: str, changes: dict[str, Any]) -> None:
    root = package["run_root"] / "inference_primary"
    path = root / relative
    value = json.loads(path.read_bytes())
    value.update(changes)
    digest = write(path, value)
    freeze = json.loads((root / "inference_freeze.json").read_bytes())
    freeze["artifacts"][relative] = digest
    package["expected_freeze_sha256"] = write(root / "inference_freeze.json", freeze)


def test_reviewed_import_preserves_canonical_records_and_normalizes_calibration(
    package: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_parser = importer._json_object

    def guarded_parse(data: bytes) -> dict[str, Any]:
        assert b"do_not_deserialize_gt" not in data
        return original_parser(data)

    monkeypatch.setattr(importer, "_json_object", guarded_parse)
    result = importer.certify_reviewed_package(**package)
    assert result.certificate.event_count == 1
    assert result.certificate.checked_projection_count == 2
    assert result.certificate.blocked_cases == ("case2",)
    assert result.certificate.image_measurement is False
    assert result.snapshot.gaps[0].event.event_id == "canonical:event-unchanged"
    assert result.snapshot.gaps[0].search_result.complete is True
    assert result.registry.cameras[0].coverage_status == "UNKNOWN"
    assert result.registry.cameras[0].calibration.clip_start == pytest.approx(0.00247)
    assert result.registry.cameras[0].calibration.clip_end == pytest.approx(24.7)
    certificate = result.certificate.model_dump_json()
    assert "actor-secret" not in certificate and str(package["run_root"]) not in certificate


def test_reviewed_package_requires_exact_checkpoint(package: dict[str, Any]) -> None:
    package["expected_dataset_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="checkpoint"):
        importer.certify_reviewed_package(**package)


def test_reviewed_source_and_artifact_bytes_are_verified(package: dict[str, Any]) -> None:
    package["source_scene"].write_bytes(b"changed source")
    with pytest.raises(ValueError, match="source bytes"):
        importer.certify_reviewed_package(**package)


def test_reviewed_projection_cannot_skip_explicit_bu_conversion(package: dict[str, Any]) -> None:
    root = package["run_root"] / "inference_primary"
    projection = json.loads((root / "case1/projection.json").read_bytes())
    projection["rows"][0]["selected_world_position"][0] += 1
    alter_inference(package, "case1/projection.json", projection)
    with pytest.raises(ValueError, match="normalized native projection"):
        importer.certify_reviewed_package(**package)


def test_reviewed_ground_truth_selection_is_rejected_even_with_consistent_hashes(
    package: dict[str, Any],
) -> None:
    root = package["run_root"] / "inference_primary"
    projection = json.loads((root / "case1/projection.json").read_bytes())
    projection["rows"][0]["selection_uses_ground_truth"] = True
    alter_inference(package, "case1/projection.json", projection)
    with pytest.raises(ValueError, match="isolation"):
        importer.certify_reviewed_package(**package)


def test_reviewed_camera_mapping_cannot_mix_contexts(package: dict[str, Any]) -> None:
    root = package["run_root"] / "inference_primary"
    reviewed = json.loads((root / "case1/reviewed_context.json").read_bytes())
    reviewed["computation_context"]["cameras"][0]["fx"] = 12
    alter_inference(package, "case1/reviewed_context.json", reviewed)
    with pytest.raises(ValueError, match="calibration conversion"):
        importer.certify_reviewed_package(**package)


def test_reviewed_hash_manifest_path_cannot_escape(package: dict[str, Any]) -> None:
    root = package["run_root"] / "inference_primary"
    freeze = json.loads((root / "inference_freeze.json").read_bytes())
    freeze["artifacts"]["../secret.json"] = "f" * 64
    package["expected_freeze_sha256"] = write(root / "inference_freeze.json", freeze)
    with pytest.raises(ValueError, match="contained relative path"):
        importer.certify_reviewed_package(**package)
