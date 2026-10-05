"""Pilot quality checks reject corrupted artifacts and prevent truth input leakage."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from amidst.domain.camera import Camera
from amidst.domain.evidence import ObservationFrame
from amidst.domain.geometry import Plane
from amidst.simulation.virtual_camera import project_world

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "validate_blender_pilot.py"
SPEC = importlib.util.spec_from_file_location("pilot_validation", SCRIPT)
assert SPEC and SPEC.loader
validation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validation)


@pytest.fixture
def pilot(tmp_path: Path) -> Path:
    source = tmp_path / "scene.blend"
    source.write_bytes(b"unit-test fixture; not an actual Blender scene")
    stat = source.stat()
    digest = validation.sha256(source)
    camera = Camera(
        camera_id="CAM_TEST_A",
        width=32,
        height=32,
        fx=16,
        fy=16,
        cx=16,
        cy=16,
        camera_to_world=((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 10), (0, 0, 0, 1)),
        clip_start=1,
        clip_end=20,
    )
    cameras = (camera, camera.model_copy(update={"camera_id": "CAM_TEST_B"}))
    rows, frames = [], []
    for index in range(50):
        timestamp = index / 5
        position = (index / 100, 0.0, 0.0)
        visible = not 20 <= index <= 29
        samples = []
        for camera in cameras:
            projection = project_world(camera, position)
            frame = ObservationFrame(
                frame_id=index,
                timestamp=timestamp,
                target_id="synthetic_target",
                camera_id=camera.camera_id,
                status="OBSERVED" if visible else "GAP",
                point_2d=projection.point_2d if visible else None,
                provenance="OBSERVED" if visible else None,
                gap_reason=None if visible else "OCCLUDED",
                occluder_id=None if visible else "fixture_wall",
            ).model_dump(mode="json")
            image_path = tmp_path / "frames" / camera.camera_id / f"frame_{index:03d}.png"
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image = Image.new("RGB", (32, 32), (100 + index, 100 + index, 100 + index))
            if visible:
                image.putpixel(tuple(round(value) for value in projection.point_2d), (255, 50, 0))
            image.save(image_path)
            samples.append(
                {
                    "camera_id": camera.camera_id,
                    "visibility": "visible" if visible else "occluded",
                    "pixel": list(projection.point_2d) if visible else None,
                    "depth": projection.axial_depth,
                    "observation": frame,
                    "blender_projection": {
                        "pixel": list(projection.point_2d),
                        "axial_depth": projection.axial_depth,
                    },
                    "render": {
                        "path": image_path.relative_to(tmp_path).as_posix(),
                        "sha256": validation.sha256(image_path),
                    },
                    "image_diagnostics": {
                        "interpretation": "SYNTHETIC_TEST_IMAGE",
                        "orange_target_pixels": int(visible),
                        "orange_near_projected_landmark": visible,
                    },
                }
            )
            frames.append(frame)
        rows.append(
            {
                "index": index,
                "timestamp": timestamp,
                "ground_truth": {
                    "position": list(position),
                    "trajectory_id": "fixture_trajectory",
                    "floor_id": "TEST",
                    "provenance": "GROUND_TRUTH",
                },
                "per_camera": samples,
                "gap_state": "OBSERVED" if visible else "GAP",
            }
        )
    dataset = {
        "label": validation.LABEL,
        "duration_seconds": 10,
        "sampling_fps": 5,
        "source_scene": {
            "path": str(source),
            "sha256_before": digest,
            "sha256_after": digest,
            "size_before": stat.st_size,
            "size_after": stat.st_size,
            "mtime_ns_before": stat.st_mtime_ns,
            "mtime_ns_after": stat.st_mtime_ns,
        },
        "cameras": [camera.model_dump(mode="json") for camera in cameras],
        "trajectory": {
            "trajectory_id": "fixture_trajectory",
            "length_scene_units": 0.49,
            "floor_id": "TEST",
            "observation_plane_z": 0,
            "scale_authority": "UNVERIFIED",
        },
        "timestamps": rows,
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset))
    (tmp_path / "observations.json").write_text(
        json.dumps(
            {
                "label": validation.LABEL,
                "data_kind": "SYNTHETIC",
                "source_asset_sha256": digest,
                "frames": frames,
            }
        )
    )
    return path


def mutate(path: Path, mutation: Any) -> None:
    data = json.loads(path.read_text())
    mutation(data)
    path.write_text(json.dumps(data))


def test_complete_pilot_verifies_renders_sampling_and_closed_gap(pilot: Path) -> None:
    result = validation.validate_pilot(pilot)
    assert result["status"] == "PASS_WITH_REVIEW"
    assert result["errors"] == []
    assert result["source_identity_verified"]
    assert result["decoded_render_count"] == 100
    assert result["visibility_counts"] == {"visible": 80, "occluded": 20, "out_of_FOV": 0}
    assert result["global_gap_timestamp_count"] == 10
    assert result["projection"]["expected_gap_rejections"] == 20
    assert result["projection"]["pilot_plane_inverse_max_error_scene_units"] < 1e-12
    assert result["render_target_quality"]["visible_landmark_png_verified_count"] == 80
    assert not result["full_dataset_ready"]


def test_missing_timestamp_fails_even_with_decodable_images(pilot: Path) -> None:
    mutate(pilot, lambda data: data["timestamps"].pop(8))
    result = validation.validate_pilot(pilot)
    assert result["status"] == "FAILED"
    assert any("expected 50 timestamps" in error for error in result["errors"])


def test_render_tampering_and_forward_projection_mismatch_are_detected(pilot: Path) -> None:
    frame_path = pilot.parent / "frames" / "CAM_TEST_A" / "frame_000.png"
    Image.new("RGB", (32, 32), "red").save(frame_path)
    mutate(
        pilot,
        lambda data: data["timestamps"][0]["per_camera"][0]["blender_projection"].update(
            pixel=[31, 31]
        ),
    )
    result = validation.validate_pilot(pilot)
    assert any("SHA-256 mismatch" in error for error in result["errors"])
    assert any("pixel residual" in error for error in result["errors"])


def test_truth_field_in_sanitized_observations_is_rejected(pilot: Path) -> None:
    observations = pilot.parent / "observations.json"
    mutate(observations, lambda data: data["frames"][0].update(world_position=[0, 0, 0]))
    result = validation.validate_pilot(pilot)
    assert result["status"] == "FAILED"
    assert any("GT-free ObservationFrame contract" in error for error in result["errors"])


def test_visible_point_without_rendered_target_is_an_image_quality_error(pilot: Path) -> None:
    frame_path = pilot.parent / "frames" / "CAM_TEST_A" / "frame_000.png"
    Image.new("RGB", (32, 32), (100, 100, 100)).save(frame_path)
    mutate(
        pilot,
        lambda data: data["timestamps"][0]["per_camera"][0]["render"].update(
            sha256=validation.sha256(frame_path)
        ),
    )
    result = validation.validate_pilot(pilot)
    assert any("no orange target in PNG nearby" in error for error in result["errors"])


def test_png_provenance_labels_match_manifest_and_detect_wrong_timestamp(pilot: Path) -> None:
    data = validation.read_json(pilot)
    data["render_policy"] = {"png_label_policy": "SYNTHETIC_PROVENANCE_TEXT_CHUNKS"}
    for row in data["timestamps"]:
        for sample in row["per_camera"]:
            path = pilot.parent / sample["render"]["path"]
            labels = PngInfo()
            for key, value in {
                "DatasetLabel": validation.LABEL,
                "DataKind": "SYNTHETIC",
                "SourceAssetSHA256": data["source_scene"]["sha256_before"],
                "SimulationTimestampSeconds": str(row["timestamp"]),
                "TrajectoryID": data["trajectory"]["trajectory_id"],
            }.items():
                labels.add_text(key, value)
            with Image.open(path) as original:
                image = original.copy()
            image.save(path, pnginfo=labels)
            sample["render"]["sha256"] = validation.sha256(path)
    pilot.write_text(json.dumps(data))
    result = validation.validate_pilot(pilot)
    assert result["errors"] == []
    assert result["render_target_quality"]["png_provenance_labels_verified_count"] == 100
    mutate(pilot, lambda data: data["timestamps"][0].update(timestamp=0.1))
    result = validation.validate_pilot(pilot)
    assert any("labels mismatch" in error for error in result["errors"])


def test_projection_inputs_remain_identical_when_evaluation_truth_changes(pilot: Path) -> None:
    observations = validation.read_json(pilot.parent / "observations.json")
    frames = tuple(ObservationFrame.model_validate(raw) for raw in observations["frames"])
    data = validation.read_json(pilot)
    cameras = {
        raw["camera_id"]: Camera.model_validate(raw)
        for raw in data["cameras"]
    }
    plane = Plane(plane_id="pilot", point=(0, 0, 0), normal=(0, 0, 1), floor_id="TEST")
    before = validation.project_sanitized_frames(frames, cameras, plane)
    mutate(pilot, lambda data: data["timestamps"][0]["ground_truth"].update(position=[7, 3, 0]))
    after = validation.project_sanitized_frames(frames, cameras, plane)
    assert before == after
    assert any(
        "projection residual" in error
        for error in validation.validate_pilot(pilot)["errors"]
    )
