"""Pixels, local namespace and isolated GT are independent testable boundaries."""

from hashlib import sha256
from pathlib import Path

import pytest
from PIL import Image

from amidst.engineering.perception import RGBFrame, produce_perception
from amidst.engineering.synthetic import generate_sequence


def test_actual_rgb_sequence_and_separate_full_gt(tmp_path: Path) -> None:
    package = generate_sequence(tmp_path)
    assert len(package.frames) == 102
    assert {row.camera_id for row in package.frames} == {"CAM_A", "CAM_B"}
    assert len({row.sha256 for row in package.frames}) > 50
    assert package.simulation_export_path.relative_to(tmp_path).parts[:2] == (
        "simulation", "export",
    )
    assert "blue-person-a" in package.simulation_export_path.read_text()
    assert all("actor" not in row.model_dump_json() for row in package.frames)
    with Image.open(package.frames[0].path) as image:
        assert image.mode == "RGB"
        assert image.size == (320, 240)


def test_rgb_measurements_tracks_occlusion_and_ambiguity(tmp_path: Path) -> None:
    package = generate_sequence(tmp_path)
    result = produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)
    assert result.complete
    assert result.input_manifest_sha256 == package.dataset_sha256
    assert len(result.measurements) > 50
    assert {row.camera_id for row in result.measurements} == {"CAM_A", "CAM_B"}
    assert len(result.tracks) >= 5
    assert any(row.status == "NO_DETECTION" for row in result.frame_statuses)
    assert any(row.status == "AMBIGUOUS_COMPONENT" for row in result.frame_statuses)
    assert any(row.status == "DETECTED" for row in result.measurements)
    assert all(row.measurement_source == "RGB_PIXELS" and row.image_measurement
               for row in result.measurements)
    assert all(row.local_track_id.startswith(
        f"track:{package.model_id}:{package.run_id}:{row.camera_id}:",
    ) for row in result.measurements)
    cam_a = [row for row in result.tracks if row.camera_id == "CAM_A"]
    assert any(row.timestamps[0] > 3 for row in cam_a), "occlusion produces recovery fragment"
    assert "blue-person" not in result.model_dump_json()


def test_png_byte_and_measurement_reproduction(tmp_path: Path) -> None:
    first = generate_sequence(tmp_path / "first")
    second = generate_sequence(tmp_path / "second")
    assert first.dataset_sha256 == second.dataset_sha256
    assert first.config_sha256 == second.config_sha256
    assert [row.sha256 for row in first.frames] == [row.sha256 for row in second.frames]
    assert produce_perception(first.frames, model_id=first.model_id, run_id=first.run_id) == (
        produce_perception(second.frames, model_id=second.model_id, run_id=second.run_id)
    )
    other_run = generate_sequence(tmp_path / "third", run_id="independent-run")
    assert first.source_sha256 == other_run.source_sha256
    assert first.context_sha256 == other_run.context_sha256
    assert first.config_sha256 != other_run.config_sha256
    assert first.dataset_sha256 != other_run.dataset_sha256


def test_gt_pollution_cannot_change_measurement_inference(tmp_path: Path) -> None:
    package = generate_sequence(tmp_path)
    frozen = produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)
    package.simulation_export_path.write_text(
        '{"actor_identity":"different","position_xyz_m":[9999,-9999,100],'
        '"answers":{"camera":"HIDDEN","path":"invented"}}',
    )
    repeated = produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)
    assert frozen == repeated
    package.simulation_export_path.unlink()
    assert frozen == produce_perception(
        package.frames, model_id=package.model_id, run_id=package.run_id,
    )


def test_missing_and_hash_mismatch_are_explicit_no_fallback(tmp_path: Path) -> None:
    package = generate_sequence(tmp_path)
    missing, corrupt = package.frames[:2]
    missing.path.unlink()
    corrupt.path.write_bytes(b"invalid altered pixels")
    result = produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)
    statuses = {row.frame_ref: row for row in result.frame_statuses}
    assert statuses[missing.media_ref].status == "MISSING_IMAGE"
    assert statuses[corrupt.media_ref].status == "HASH_MISMATCH"
    assert not result.complete
    assert not any(row.frame_ref in {missing.media_ref, corrupt.media_ref}
                   for row in result.measurements)
    assert all(str(tmp_path) not in row.model_dump_json() for row in result.frame_statuses)


def test_invalid_image_and_pixels_only_empty_result(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"not an RGB image")
    frame = RGBFrame(media_ref="media:invalid", camera_id="CAM_A", timestamp=0,
                     path=invalid, sha256=sha256(invalid.read_bytes()).hexdigest(),
                     width=320, height=240)
    result = produce_perception([frame], model_id="fixture", run_id="empty")
    assert result.frame_statuses[0].status == "INVALID_IMAGE"
    assert not result.complete and not result.measurements
    blank = tmp_path / "blank.png"
    Image.new("RGB", (320, 240), (0, 0, 0)).save(blank)
    clean = frame.model_copy(update={"path": blank,
                                    "sha256": sha256(blank.read_bytes()).hexdigest()})
    empty = produce_perception([clean], model_id="fixture", run_id="empty")
    assert empty.complete and not empty.measurements and not empty.tracks
    assert empty.frame_statuses[0].status == "NO_DETECTION"


def test_generator_rejects_conflicting_run_without_overwriting(tmp_path: Path) -> None:
    package = generate_sequence(tmp_path)
    original = package.frames[0].path.read_bytes()
    with pytest.raises(ValueError, match="existing run GT differs"):
        generate_sequence(tmp_path, run_id="different-run")
    assert package.frames[0].path.read_bytes() == original


def test_duplicate_reference_or_camera_time_rejected(tmp_path: Path) -> None:
    package = generate_sequence(tmp_path, frame_count=5)
    with pytest.raises(ValueError, match="duplicate frame"):
        produce_perception([package.frames[0], package.frames[0]], model_id="model", run_id="run")
