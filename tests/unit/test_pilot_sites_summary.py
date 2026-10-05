"""Reports keep camera-record counts, point GAP and body-image diagnostics distinct."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "summarize_pilot_sites.py"
SPEC = importlib.util.spec_from_file_location("pilot_sites_summary", SCRIPT)
assert SPEC and SPEC.loader
summary = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summary)


@pytest.fixture
def pilot(tmp_path: Path) -> Path:
    rows = []
    for index in range(50):
        samples = []
        for camera_id in ("CAM_A", "CAM_B"):
            path = tmp_path / "frames" / camera_id / f"{index}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image = Image.new("RGB", (20, 20), "#808080")
            if not 10 <= index <= 19 or (index == 10 and camera_id == "CAM_A"):
                image.paste("#ff3300", (2, 3, 6, 12))
            image.save(path)
            visible = not 10 <= index <= 19
            samples.append(
                {
                    "camera_id": camera_id,
                    "visibility": "visible"
                    if visible
                    else ("occluded" if camera_id == "CAM_A" else "out_of_FOV"),
                    "render": {
                        "path": path.relative_to(tmp_path).as_posix(),
                        "sha256": summary.digest(path),
                    },
                }
            )
        rows.append(
            {
                "index": index,
                "timestamp": index / 5,
                "gap_state": "GAP" if 10 <= index <= 19 else "OBSERVED",
                "per_camera": samples,
            }
        )
    data = {
        "label": summary.LABEL,
        "source_scene": {"sha256_before": "source-digest"},
        "cameras": [{"camera_id": "CAM_A"}, {"camera_id": "CAM_B"}],
        "trajectory": {"trajectory_id": "FIXTURE_ONLY"},
        "timestamps": rows,
        "duration_seconds": 10,
        "sampling_fps": 5,
        "successful_timestamps": 50,
    }
    (tmp_path / "dataset.json").write_text(json.dumps(data))
    (tmp_path / "validation.json").write_text(
        json.dumps(
            {
                "label": summary.LABEL,
                "dataset_sha256": summary.digest(tmp_path / "dataset.json"),
                "visibility_counts": {"visible": 80, "occluded": 10, "out_of_FOV": 10},
                "timestamp_count": 50,
                "decoded_render_count": 100,
                "expected_camera_frame_count": 100,
                "status": "PASS_WITH_REVIEW",
                "errors": [],
                "warnings": [],
                "source_identity_verified": True,
                "observed_gap_observed_recovery": True,
                "projection": {},
            }
        )
    )
    (tmp_path / "trajectory_plan.json").write_text(
        json.dumps({"source_asset_sha256": "source-digest", "site_id": "TEST_SITE"})
    )
    (tmp_path / "representative_frames.json").write_text(
        json.dumps(
            [
                {
                    "index": index,
                    "timestamp": index / 5,
                    "stage": stage,
                    "path": f"frames/CAM_A/{index}.png",
                }
                for stage, index in zip(
                    ("start", "before", "enter", "middle", "recover"),
                    (0, 9, 10, 15, 20),
                    strict=True,
                )
            ]
        )
    )
    return tmp_path


def test_summary_separates_point_gaps_from_camera_visibility_and_partial_pixels(
    pilot: Path,
) -> None:
    result = summary.summarize_site(pilot)
    assert result["visibility_counts_camera_records"] == {
        "visible": 80,
        "occluded": 10,
        "out_of_FOV": 10,
    }
    gap = result["selected_camera_point_visibility"]
    assert gap["gap_timestamps"] == 10
    assert gap["fully_hidden_marker_gap_timestamps"] == 9
    assert gap["partially_visible_marker_gap_timestamps"] == 1
    assert result["per_camera"]["CAM_A"]["visible_marker_bbox_width_pixels"]["minimum"] == 4
    assert result["per_camera"]["CAM_A"]["visible_marker_bbox_height_pixels"]["minimum"] == 9
    assert result["pilot_suitability"] == "AWAITING_AGENT_IMAGE_REVIEW"
    assert result["full_dataset_ready"] is False


def test_summary_rejects_stale_validator(pilot: Path) -> None:
    path = pilot / "dataset.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="Stale validation"):
        summary.summarize_site(pilot)


def test_summary_rejects_stale_or_unbound_visual_assessment(pilot: Path) -> None:
    with pytest.raises(ValueError, match="not bound"):
        summary.summarize_site(pilot, {"reviewed": True, "dataset_sha256": "old"})


def test_summary_rejects_modified_render(pilot: Path) -> None:
    Image.new("RGB", (20, 20), "white").save(pilot / "frames/CAM_A/0.png")
    with pytest.raises(ValueError, match="Render SHA-256 mismatch"):
        summary.summarize_site(pilot)


def test_summary_rejects_changed_image_review_artifact(pilot: Path) -> None:
    path = pilot / "review_montage.png"
    Image.new("RGB", (20, 20), "gray").save(path)
    assessment = {
        "reviewed": True,
        "dataset_sha256": summary.digest(pilot / "dataset.json"),
        "inspected_artifact_sha256": {path.name: summary.digest(path)},
    }
    Image.new("RGB", (20, 20), "white").save(path)
    with pytest.raises(ValueError, match="changed since visual review"):
        summary.summarize_site(pilot, assessment)


def test_intervals_include_edge_samples_and_leave_control_without_gap() -> None:
    rows = [
        {
            "index": index,
            "timestamp": index / 5,
            "gap_state": "GAP" if index in (0, 1, 4) else "OBSERVED",
        }
        for index in range(5)
    ]
    assert summary.intervals(rows, state="GAP") == [
        {
            "first_index": 0,
            "last_index": 1,
            "first_timestamp": 0.0,
            "last_timestamp": 0.2,
            "timestamp_count": 2,
        },
        {
            "first_index": 4,
            "last_index": 4,
            "first_timestamp": 0.8,
            "last_timestamp": 0.8,
            "timestamp_count": 1,
        },
    ]
    assert summary.intervals([{"gap_state": "OBSERVED"}], state="GAP") == []
