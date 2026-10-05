"""Multi-site pilot checks protect control policy and source-bound export identity."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from test_blender_pilot_validation import mutate, validation
from test_blender_pilot_validation import pilot as pilot

REVIEW_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_pilot_review.py"
REVIEW_SPEC = importlib.util.spec_from_file_location("multi_site_pilot_review", REVIEW_SCRIPT)
assert REVIEW_SPEC and REVIEW_SPEC.loader
review = importlib.util.module_from_spec(REVIEW_SPEC)
REVIEW_SPEC.loader.exec_module(review)


def make_fully_observed(pilot: Path) -> None:
    data = validation.read_json(pilot)
    frames = []
    for row in data["timestamps"]:
        row["gap_state"] = "OBSERVED"
        for sample in row["per_camera"]:
            pixel = sample["blender_projection"]["pixel"]
            sample.update(visibility="visible", pixel=pixel)
            sample["observation"].update(
                status="OBSERVED", point_2d=pixel, provenance="OBSERVED",
                gap_reason=None, occluder_id=None,
            )
            image = Image.new("RGB", (32, 32), (100, 100, 100))
            image.putpixel(tuple(round(value) for value in pixel), (255, 50, 0))
            path = pilot.parent / sample["render"]["path"]
            image.save(path)
            sample["render"]["sha256"] = validation.sha256(path)
            sample["image_diagnostics"].update(
                orange_target_pixels=1, orange_near_projected_landmark=True
            )
            frames.append(sample["observation"])
    pilot.write_text(json.dumps(data))
    observations = validation.read_json(pilot.parent / "observations.json")
    observations["frames"] = frames
    (pilot.parent / "observations.json").write_text(json.dumps(observations))


def add_bound_plan(pilot: Path) -> Path:
    data = validation.read_json(pilot)
    data.update(site_id="TEST_ROOM", sample_role="VISIBLE_GAP_VISIBLE")
    trajectory = data["trajectory"]
    plan = {
        "label": validation.LABEL,
        "source_asset_sha256": data["source_scene"]["sha256_before"],
        "site_id": data["site_id"],
        "sample_role": data["sample_role"],
        "trajectory_id": trajectory["trajectory_id"],
        "floor_id": trajectory["floor_id"],
        "camera_ids": [camera["camera_id"] for camera in data["cameras"]],
        "observation_plane_z": trajectory["observation_plane_z"],
        "samples": [
            {"timestamp": row["timestamp"], "probe_position": row["ground_truth"]["position"]}
            for row in data["timestamps"]
        ],
        "floor_support_evidence": {
            "support_probes_per_timestamp": 5,
            "target_full_sweep_clear": True,
            "physical_support_objects": ["TEST_FLOOR"],
        },
    }
    path = pilot.parent / "trajectory_plan.json"
    path.write_text(json.dumps(plan))
    trajectory["plan_path"] = "trajectory_plan.json"
    for row in data["timestamps"]:
        for sample in row["per_camera"]:
            sample["observation_provenance"] = {
                "producer": "BLENDER_SIMULATION_POINT_RAYCAST",
                "data_kind": "SYNTHETIC",
                "label": validation.LABEL,
                "source_asset_sha256": data["source_scene"]["sha256_before"],
                "image_measurement": False,
                "site_id": data["site_id"],
            }
            image_path = pilot.parent / sample["render"]["path"]
            with Image.open(image_path) as image:
                rendered = image.copy()
            labels = PngInfo()
            labels.add_text("SiteID", data["site_id"])
            rendered.save(image_path, pnginfo=labels)
            sample["render"]["sha256"] = validation.sha256(image_path)
    observations = validation.read_json(pilot.parent / "observations.json")
    observations["site_id"] = data["site_id"]
    (pilot.parent / "observations.json").write_text(json.dumps(observations))
    (pilot.parent / "ground_truth.json").write_text(json.dumps({
        "label": validation.LABEL,
        "site_id": data["site_id"],
        "source_asset_sha256": data["source_scene"]["sha256_before"],
        "trajectory_id": trajectory["trajectory_id"],
        "provenance": "GROUND_TRUTH",
        "samples": [
            {"timestamp": row["timestamp"], **row["ground_truth"]}
            for row in data["timestamps"]
        ],
    }))
    pilot.write_text(json.dumps(data))
    return path


def test_no_gap_control_requires_explicit_role(pilot: Path) -> None:
    make_fully_observed(pilot)
    legacy = validation.validate_pilot(pilot)
    assert any("observed -> global GAP" in error for error in legacy["errors"])
    mutate(pilot, lambda data: data.update(sample_role="FULLY_OBSERVED_CONTROL"))
    control = validation.validate_pilot(pilot)
    assert control["errors"] == []
    assert control["global_observed_timestamp_count"] == 50
    assert control["global_gap_timestamp_count"] == 0
    assert not control["observed_gap_observed_recovery"]
    assert control["projection"]["pilot_plane_inverse_projected_count"] == 100


def test_control_with_global_gap_fails(pilot: Path) -> None:
    mutate(pilot, lambda data: data.update(sample_role="FULLY_OBSERVED_CONTROL"))
    result = validation.validate_pilot(pilot)
    assert any("control requires all 50" in error for error in result["errors"])


def test_unknown_sample_role_fails(pilot: Path) -> None:
    mutate(pilot, lambda data: data.update(sample_role="UNDECLARED_FALLBACK"))
    result = validation.validate_pilot(pilot)
    assert any("sample role must declare" in error for error in result["errors"])


@pytest.mark.parametrize("changed_key", ["source_asset_sha256", "site_id", "sample_role"])
def test_mixed_plan_source_or_site_is_rejected(pilot: Path, changed_key: str) -> None:
    plan = add_bound_plan(pilot)
    assert validation.validate_pilot(pilot)["errors"] == []
    mutate(plan, lambda data: data.update({changed_key: "OTHER_SITE_OR_SOURCE"}))
    result = validation.validate_pilot(pilot)
    assert not result["trajectory_plan_binding"]["verified"]
    assert any("trajectory plan binding" in error for error in result["errors"])


def test_plan_position_mismatch_is_evaluation_failure(pilot: Path) -> None:
    plan = add_bound_plan(pilot)
    mutate(plan, lambda data: data["samples"][0].update(probe_position=[5, 5, 0]))
    result = validation.validate_pilot(pilot)
    assert any(
        "exported landmark differs from planned geometry" in error
        for error in result["errors"]
    )
    assert result["projection"]["unexpected_failures"] == []


@pytest.mark.parametrize("artifact", ["observations.json", "ground_truth.json"])
def test_separate_export_site_mixup_is_rejected(pilot: Path, artifact: str) -> None:
    add_bound_plan(pilot)
    mutate(pilot.parent / artifact, lambda data: data.update(site_id="OTHER_SITE"))
    result = validation.validate_pilot(pilot)
    assert any("site" in error and "differs from dataset" in error for error in result["errors"])


def test_png_site_mixup_fails_even_after_manifest_hash_update(pilot: Path) -> None:
    add_bound_plan(pilot)
    data = validation.read_json(pilot)
    sample = data["timestamps"][0]["per_camera"][0]
    path = pilot.parent / sample["render"]["path"]
    with Image.open(path) as image:
        rendered = image.copy()
    labels = PngInfo()
    labels.add_text("SiteID", "OTHER_SITE")
    rendered.save(path, pnginfo=labels)
    sample["render"]["sha256"] = validation.sha256(path)
    pilot.write_text(json.dumps(data))
    result = validation.validate_pilot(pilot)
    assert any("PNG SiteID differs" in error for error in result["errors"])


def test_per_camera_provenance_site_mixup_is_rejected(pilot: Path) -> None:
    add_bound_plan(pilot)
    mutate(
        pilot,
        lambda data: data["timestamps"][0]["per_camera"][0]["observation_provenance"].update(
            site_id="OTHER_SITE"
        ),
    )
    result = validation.validate_pilot(pilot)
    assert any("provenance site differs" in error for error in result["errors"])


@pytest.mark.parametrize("changed_key", ["source_asset_sha256", "producer", "label"])
def test_observation_provenance_mismatch_is_rejected(pilot: Path, changed_key: str) -> None:
    data = validation.read_json(pilot)
    sample = data["timestamps"][0]["per_camera"][0]
    sample["observation_provenance"] = {
        "producer": "BLENDER_SIMULATION_POINT_RAYCAST",
        "data_kind": "SYNTHETIC",
        "label": validation.LABEL,
        "source_asset_sha256": data["source_scene"]["sha256_before"],
        "image_measurement": False,
    }
    pilot.write_text(json.dumps(data))
    assert validation.validate_pilot(pilot)["errors"] == []
    mutate(
        pilot,
        lambda data: data["timestamps"][0]["per_camera"][0]["observation_provenance"].update(
            {changed_key: "FORGED"}
        ),
    )
    result = validation.validate_pilot(pilot)
    assert any("observation provenance differs" in error for error in result["errors"])


def representative_rows(gap_indices: tuple[int, ...] = ()) -> list[dict]:
    return [
        {"index": index, "gap_state": "GAP" if index in gap_indices else "OBSERVED"}
        for index in range(50)
    ]


def test_visible_control_representatives_show_start_middle_and_end() -> None:
    rows = representative_rows()
    representatives = review.representative_indices(rows, "FULLY_OBSERVED_CONTROL")
    indices = [index for _stage, index in representatives]
    assert len(indices) == len(set(indices)) == 5
    assert indices == sorted(indices)
    assert indices[0] == 0 and indices[-1] == 49
    assert any(20 <= index <= 30 for index in indices)
    assert all(rows[index]["gap_state"] == "OBSERVED" for index in indices)
    assert all("gap" not in stage for stage, _index in representatives)


@pytest.mark.parametrize("bad_input", ["missing_timestamp", "global_gap"])
def test_visible_control_review_rejects_incomplete_or_gapped_sequence(bad_input: str) -> None:
    rows = representative_rows((24,)) if bad_input == "global_gap" else representative_rows()[:-1]
    with pytest.raises(ValueError, match="all 50 timestamps observed"):
        review.representative_indices(rows, "FULLY_OBSERVED_CONTROL")


def test_single_timestamp_gap_review_preserves_distinct_before_gap_and_recovery_frames() -> None:
    rows = representative_rows((47,))
    representatives = review.representative_indices(rows)
    by_stage = dict(representatives)
    indices = list(by_stage.values())
    assert indices == [0, 46, 47, 48, 49]
    assert len(set(indices)) == 5
    assert rows[by_stage["02_before_short_gap"]]["gap_state"] == "OBSERVED"
    assert rows[by_stage["03_short_gap"]]["gap_state"] == "GAP"
    assert rows[by_stage["04_visible_again"]]["gap_state"] == "OBSERVED"
