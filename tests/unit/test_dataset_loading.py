"""Sanitized providers use content-bound files and never consume evaluation geometry."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from amidst.datasets.loading import load_case_calibration, load_dataset_case
from amidst.domain.calibration import CameraCalibrationCatalog
from amidst.domain.camera import Camera
from amidst.domain.experiment import ArtifactReference, DatasetCase, DatasetManifest
from amidst.geometry.calibration import (
    calibration_content_sha256,
    frustum_geometry,
    image_fov_radians,
    pinhole_projection_matrix,
)
from amidst.simulation.stream_fixture import export_stream_dataset

ROOT = Path(__file__).resolve().parents[2]


def _catalog(camera_ids: tuple[str, ...], version: str) -> CameraCalibrationCatalog:
    identity = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, 1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    cameras: list[dict[str, Any]] = []
    for camera_id in sorted(camera_ids):
        camera = Camera(
            camera_id=camera_id,
            camera_to_world=identity,
            fx=100,
            fy=100,
            cx=100,
            cy=50,
            width=200,
            height=100,
            clip_start=1,
            clip_end=10,
        )
        projection = pinhole_projection_matrix(100, 100, 100, 50, 200, 100, 1, 10)
        cameras.append(
            {
                "camera_name": camera_id,
                "camera": camera.model_dump(),
                "pose": {
                    "evaluated_world_matrix": identity,
                    "evaluated_world_inverse": identity,
                    "rigid_camera_to_world": identity,
                    "world_to_camera": identity,
                    "position_world": (0, 0, 0),
                    "rotation_quaternion_wxyz": (1, 0, 0, 0),
                    "rotation_euler_xyz_radians": (0, 0, 0),
                    "evaluated_axis_scale": (1, 1, 1),
                },
                "intrinsic_matrix": ((100, 0, 100), (0, 100, 50), (0, 0, 1)),
                "focal_length_mm": 45,
                "sensor_width_mm": 36,
                "sensor_height_mm": 24,
                "sensor_fit": "HORIZONTAL",
                "pixel_aspect_xy": (1, 1),
                "shift_xy": (0, 0),
                "image_fov_xy_radians": image_fov_radians(100, 100, 100, 50, 200, 100),
                "blender_sensor_angle_xy_radians": (0.76, 0.52),
                "projection_matrix": projection,
                "view_projection_matrix": projection,
                "frustum": frustum_geometry(identity, 100, 100, 100, 50, 200, 100, 1, 10),
            }
        )
    catalog = CameraCalibrationCatalog.model_validate(
        {
            "camera_config_version": version,
            "calibration_content_sha256": "0" * 64,
            "source_asset_name": "SYNTHETIC_TEST_FIXTURE.blend",
            "source_asset_sha256": "a" * 64,
            "scene_name": "SYNTHETIC_TEST_FIXTURE",
            "scene_frame": 1,
            "scene_subframe": 0,
            "source_scene_unit_system": "METRIC",
            "source_scene_scale_length": 1,
            "cameras": cameras,
        }
    )
    return CameraCalibrationCatalog.model_validate(
        catalog.model_dump()
        | {
            "calibration_content_sha256": calibration_content_sha256(
                catalog.model_dump(mode="json")
            ),
        }
    )


def _reference(path: Path, payload: dict[str, Any]) -> ArtifactReference:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return ArtifactReference(path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def _calibrated_case(
    tmp_path: Path,
    *,
    camera_ids: tuple[str, ...] = ("CAM_A", "CAM_B", "CAM_UNUSED"),
) -> tuple[DatasetManifest, DatasetCase]:
    dataset = export_stream_dataset(ROOT / "data" / "mock", tmp_path)
    case = dataset.cases[0]
    pipeline_path = tmp_path / case.pipeline.path
    pipeline = json.loads(pipeline_path.read_text())
    pipeline["navigation"]["source_asset_sha256"] = "a" * 64
    pipeline["topology"]["source_asset_sha256"] = "a" * 64
    pipeline_ref = _reference(pipeline_path, pipeline).model_copy(
        update={"path": case.pipeline.path}
    )
    frames_path = tmp_path / case.frames.path
    frames = json.loads(frames_path.read_text())
    for sample in frames["samples"]:
        sample["source_asset_sha256"] = "a" * 64
    frames_ref = _reference(frames_path, frames).model_copy(update={"path": case.frames.path})
    catalog = _catalog(camera_ids, dataset.camera_config_version)
    calibration_ref = _reference(tmp_path / "calibration.json", catalog.model_dump(mode="json"))
    case = DatasetCase.model_validate(
        case.model_dump()
        | {
            "source_asset_sha256": "a" * 64,
            "pipeline": pipeline_ref,
            "frames": frames_ref,
            "camera_calibration": calibration_ref,
        }
    )
    dataset = DatasetManifest.model_validate(
        dataset.model_dump()
        | {
            "cases": (case, *dataset.cases[1:]),
        }
    )
    return dataset, case


def test_stream_fixture_generation_and_loading(tmp_path: Path) -> None:
    manifest = export_stream_dataset(ROOT / "data" / "mock", tmp_path)
    assert len(manifest.cases) == 4
    provider, pipeline = load_dataset_case(manifest, manifest.cases[0], tmp_path / "dataset.json")
    samples = provider.get_frame_samples(None, (0.0, 1000.0))
    assert len(samples) == 3
    assert pipeline.navigation.spatial_context_id == manifest.cases[0].spatial_context_id
    assert len(provider.aggregate((0.0, 1000.0)).observations) == 2
    assert len(provider.get_observations("CAM_A", (0.0, 1000.0))) == 1
    with pytest.raises(FileExistsError):
        export_stream_dataset(ROOT / "data" / "mock", tmp_path)


def test_frame_hash_tampering_rejected(tmp_path: Path) -> None:
    manifest = export_stream_dataset(ROOT / "data" / "mock", tmp_path)
    case = manifest.cases[0]
    (tmp_path / case.frames.path).write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_dataset_case(manifest, case, tmp_path / "dataset.json")


def test_context_tampering_rejected_before_provider_reads(tmp_path: Path) -> None:
    manifest = export_stream_dataset(ROOT / "data" / "mock", tmp_path)
    case = manifest.cases[0].model_copy(update={"spatial_context_id": "wrong"})
    manifest = DatasetManifest.model_validate(manifest.model_dump() | {"cases": (case,)})
    with pytest.raises(ValueError, match="source/context"):
        load_dataset_case(manifest, case, tmp_path / "dataset.json")


def test_optional_calibration_preserves_existing_uncalibrated_mock_contract(tmp_path: Path) -> None:
    dataset = export_stream_dataset(ROOT / "data" / "mock", tmp_path)
    assert load_case_calibration(dataset, dataset.cases[0], tmp_path / "dataset.json") is None


def test_calibration_loads_valid_catalog_and_allows_unused_catalog_cameras(tmp_path: Path) -> None:
    dataset, case = _calibrated_case(tmp_path)
    catalog = load_case_calibration(dataset, case, tmp_path / "dataset.json")
    assert catalog is not None and len(catalog.cameras) == 3
    provider, _ = load_dataset_case(dataset, case, tmp_path / "dataset.json")
    assert provider.binding.source_asset_sha256 == catalog.source_asset_sha256


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("source_asset_sha256", "b" * 64, "source asset SHA-256"),
        ("camera_config_version", "wrong-version", "calibration version"),
    ],
)
def test_declared_calibration_source_and_version_must_match(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    dataset, case = _calibrated_case(tmp_path)
    catalog = _catalog(("CAM_A", "CAM_B"), dataset.camera_config_version).model_dump(mode="json")
    catalog[field] = value
    catalog["calibration_content_sha256"] = calibration_content_sha256(catalog)
    reference = _reference(tmp_path / "calibration.json", catalog)
    case = DatasetCase.model_validate(case.model_dump() | {"camera_calibration": reference})
    dataset = DatasetManifest.model_validate(dataset.model_dump() | {"cases": (case,)})
    with pytest.raises(ValueError, match=message):
        load_dataset_case(dataset, case, tmp_path / "dataset.json")


def test_declared_calibration_outer_hash_and_internal_digest_are_checked(tmp_path: Path) -> None:
    dataset, case = _calibrated_case(tmp_path)
    assert case.camera_calibration is not None
    path = tmp_path / case.camera_calibration.path
    payload = json.loads(path.read_text())
    payload["camera_config_version"] = "tampered"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="hash mismatch"):
        load_dataset_case(dataset, case, tmp_path / "dataset.json")
    reference = ArtifactReference(
        path=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest()
    )
    case = DatasetCase.model_validate(case.model_dump() | {"camera_calibration": reference})
    dataset = DatasetManifest.model_validate(dataset.model_dump() | {"cases": (case,)})
    with pytest.raises(ValueError, match="digest mismatch"):
        load_case_calibration(dataset, case, tmp_path / "dataset.json")


def test_calibration_geometry_is_checked_even_with_valid_digests(tmp_path: Path) -> None:
    dataset, case = _calibrated_case(tmp_path)
    assert case.camera_calibration is not None
    path = tmp_path / case.camera_calibration.path
    payload = json.loads(path.read_text())
    payload["cameras"][0]["intrinsic_matrix"][0][0] = 101
    payload["calibration_content_sha256"] = calibration_content_sha256(payload)
    reference = _reference(path, payload)
    case = DatasetCase.model_validate(case.model_dump() | {"camera_calibration": reference})
    dataset = DatasetManifest.model_validate(dataset.model_dump() | {"cases": (case,)})
    with pytest.raises(ValueError, match="inconsistent"):
        load_dataset_case(dataset, case, tmp_path / "dataset.json")


def test_all_raw_frame_camera_ids_and_topology_ids_require_catalog_entries(tmp_path: Path) -> None:
    dataset, case = _calibrated_case(tmp_path, camera_ids=("CAM_A",))
    with pytest.raises(ValueError, match="frame and topology cameras"):
        load_dataset_case(dataset, case, tmp_path / "dataset.json")


@pytest.mark.parametrize("unknown_source", ["frames", "topology"])
def test_gap_only_and_topology_only_camera_ids_are_also_required(
    tmp_path: Path,
    unknown_source: str,
) -> None:
    dataset, case = _calibrated_case(tmp_path)
    if unknown_source == "frames":
        path = tmp_path / case.frames.path
        payload = json.loads(path.read_text())
        gap = next(sample for sample in payload["samples"] if sample["visibility"] == "GAP")
        gap["camera_id"] = "CAM_MISSING"
        reference = _reference(path, payload).model_copy(update={"path": case.frames.path})
        case = DatasetCase.model_validate(case.model_dump() | {"frames": reference})
    else:
        path = tmp_path / case.pipeline.path
        payload = json.loads(path.read_text())
        payload["topology"]["nodes"].append({"camera_id": "CAM_MISSING", "floor_id": "1F"})
        reference = _reference(path, payload).model_copy(update={"path": case.pipeline.path})
        case = DatasetCase.model_validate(case.model_dump() | {"pipeline": reference})
    dataset = DatasetManifest.model_validate(dataset.model_dump() | {"cases": (case,)})
    with pytest.raises(ValueError, match="frame and topology cameras"):
        load_dataset_case(dataset, case, tmp_path / "dataset.json")


def test_missing_declared_calibration_is_not_silently_ignored(tmp_path: Path) -> None:
    dataset, case = _calibrated_case(tmp_path)
    assert case.camera_calibration is not None
    case = DatasetCase.model_validate(
        case.model_dump()
        | {
            "camera_calibration": case.camera_calibration.model_copy(
                update={"path": "missing.json"}
            ),
        }
    )
    dataset = DatasetManifest.model_validate(dataset.model_dump() | {"cases": (case,)})
    with pytest.raises(FileNotFoundError):
        load_dataset_case(dataset, case, tmp_path / "dataset.json")
