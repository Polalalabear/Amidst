"""A source-model motion preview must preserve evidence and pending authority."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"
MOTION = REVIEW / "frames/motion_context"
SPATIAL = REVIEW / "frames/spatial_context"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, REVIEW / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def original_images() -> dict[str, str]:
    visuals = read_json(REVIEW / "frames/visual_manifest.json")
    spatial = read_json(SPATIAL / "spatial_context_manifest.json")
    rows = sum(
        (
            visuals[key]
            for key in (
                "frames",
                "still_frames",
                "camera_stills",
                "closeup_frames",
            )
        ),
        [],
    )
    images = {"human_review/" + row["path"]: row["sha256"] for row in rows}
    rows = [spatial[key] for key in ("overview", "floor", "office")]
    rows += spatial["approach_frames"]
    images.update(
        {"human_review/frames/spatial_context/" + row["path"]: row["sha256"] for row in rows}
    )
    return images


def require_preview_images(manifest: dict[str, Any]) -> None:
    paths = [MOTION / row["path"] for row in manifest["frames"]]
    paths += [ROOT / relative for relative in original_images()]
    if any(not path.is_file() for path in paths):
        pytest.skip("requires locally regenerated motion PNGs and the preserved 85 original PNGs")


def test_motion_renderer_rejects_truth_and_recipes_before_opening_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renderer = load_script("render_motion_context")

    def unexpected_read(_path: Path) -> bytes:
        raise AssertionError("motion renderer opened forbidden source evidence")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    for relative in (
        "data/finalization/local_run/dataset/evaluation/office/ground_truth.json",
        "data/finalization/local_run/dataset/simulation/office/recipe.json",
        "data/finalization/local_run/diagnostics/office/projection_evaluation.json",
    ):
        with pytest.raises(ValueError):
            renderer.read_public(ROOT / relative, repo_root=ROOT)


def test_50_body_motion_frames_reuse_exact_frozen_public_and_candidate_evidence() -> None:
    manifest = read_json(MOTION / "motion_manifest.json")
    visuals = read_json(REVIEW / "frames/visual_manifest.json")
    assert len(manifest["frames"]) == len(visuals["frames"]) == 50
    for actual, frozen in zip(manifest["frames"], visuals["frames"], strict=True):
        for field in (
            "frame_id",
            "timestamp",
            "role",
            "body_base_bu",
            "landmark_position_bu",
            "camera_evidence",
            "projection_method",
            "confidence_state",
            "uncertainty",
        ):
            assert actual[field] == frozen[field], (actual["frame_id"], field)
    scale = read_json(ROOT / "configs/architectural_scale_school_v3.json")[
        "metres_per_blender_unit"
    ]
    points = [frame["body_base_bu"] for frame in visuals["frames"]]
    distance = sum(math.dist(a, b) for a, b in zip(points, points[1:], strict=False)) * scale
    assert manifest["total_body_distance_m"] == pytest.approx(distance)
    assert distance == pytest.approx(3.87, abs=0.01)
    assert manifest["vertical_coordinate_conversion_m"] == pytest.approx(
        visuals["proposed_exact_landmark_offset_m"],
    )
    assert manifest["total_body_distance_m"] != pytest.approx(
        manifest["vertical_coordinate_conversion_m"],
    )
    assert manifest["trajectory_basis"] == "EXISTING_PUBLIC_PROJECTIONS_AND_INFERRED_CANDIDATE"
    assert manifest["joint_pose_authority"] == "DISPLAY_ONLY"
    assert manifest["fps"] == manifest["sampling_hz"] == 5
    assert manifest["duration_seconds"] == 10
    assert manifest["body_motion_reused_exactly"] is True
    assert manifest["body_motion_changed"] is False
    assert manifest["fixed_review_camera"] is True
    assert manifest["display_only_camera_approach"] is False
    assert manifest["new_route_generated"] is False


def test_motion_preview_preserves_source_85_images_and_formal_input_authority() -> None:
    manifest = read_json(MOTION / "motion_manifest.json")
    template = read_json(REVIEW / "review_template.json")
    assert len(template["items"]) == 4
    assert manifest["result_type"] == "DIAGNOSTIC"
    assert manifest["source_sha256"] == template["metadata"]["source_sha256"]
    assert manifest["source_preserved"] is True
    assert manifest["source_sha256_after"] == manifest["source_sha256"]
    assert manifest["source_modified"] is False
    for field in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "source_saved",
        "physical_authority_changed",
        "formal_execution_enabled",
    ):
        assert manifest[field] is False
    assert manifest["render_policy"]["engine"] == "BLENDER_WORKBENCH"
    assert manifest["render_policy"]["source_evaluation"] == (
        "FROZEN_EVALUATED_VIEWPORT_LOCAL_TRIANGLES"
    )
    assert manifest["render_policy"]["whole_scene_occlusion_proof"] is False
    assert manifest["foot_binding_authority"] == "PENDING_HR02_NOT_APPROVED"
    assert manifest["scope_authority"] == "PENDING_HR01_NOT_CERTIFIED"
    policy = read_json(ROOT / "configs/physical_authority_policy_school_v3.json")
    assert manifest["approved_body_dimensions_m"] == {
        "radius": policy["body_radius_m"],
        "height": policy["body_height_m"],
        "clearance": policy["body_clearance_m"],
    }
    preserved = manifest["preserved_inputs_and_85_old_images"]
    images = original_images()
    assert len(images) == 85
    frozen = {row["path"]: row["sha256"] for row in template["metadata"]["input_hashes"]}
    assert len(frozen) == 29
    frozen["human_review/review_template.json"] = digest(REVIEW / "review_template.json")
    for path, expected in (frozen | images).items():
        assert preserved[path] == expected
        if (ROOT / path).is_file():
            assert digest(ROOT / path) == expected, path


def test_motion_player_refuses_gt_or_authority_promotion_before_reading_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_script("build_motion_player")
    original = read_json(MOTION / "motion_manifest.json")

    def unexpected_read(_path: Path) -> bytes:
        raise AssertionError("invalid motion manifest opened image evidence")

    monkeypatch.setattr(Path, "read_bytes", unexpected_read)
    for field in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "physical_authority_changed",
        "formal_execution_enabled",
    ):
        manifest = copy.deepcopy(original)
        manifest[field] = True
        with pytest.raises(ValueError):
            module.validate_manifest(manifest, MOTION)


def test_new_motion_player_keeps_all_existing_review_and_guide_files_intact(tmp_path: Path) -> None:
    manifest = read_json(MOTION / "motion_manifest.json")
    require_preview_images(manifest)
    protected = [
        REVIEW / name
        for name in (
            "decisions.json",
            "review_template.json",
            "geometry_evidence.json",
            "settings_evidence.json",
            "frames/visual_manifest.json",
            "frames/player.html",
            "frames/player_template.html",
            "build_frame_player.py",
            "frames/spatial_context/spatial_context_manifest.json",
            "frames/spatial_context/guide.html",
            "frames/spatial_context/guide_template.html",
            "build_spatial_guide.py",
            "gate.json",
        )
    ]
    protected += [ROOT / relative for relative in original_images()]
    before = {path: digest(path) for path in protected}
    module = load_script("build_motion_player")
    output = tmp_path / "motion-player.html"
    module.build_player(MOTION / "motion_manifest.json", output)
    assert {path: digest(path) for path in protected} == before
    text = output.read_text()
    assert "localStorage" not in text
    assert "DIAGNOSTIC" in text
    assert read_json(REVIEW / "review_template.json")["review_payload_sha256"] in text
