"""Clarity views must preserve source coordinates, pending binding, and framing."""

from __future__ import annotations

import hashlib
import importlib.util
import itertools
import json
import math
import struct
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"
CLARITY = REVIEW / "frames/review_clarity"
SOURCE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
PAYLOAD_SHA = "e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, REVIEW / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def independent_pixel(point: list[float], view: dict[str, Any]) -> list[float]:
    relative = [point[i] - view["position_bu"][i] for i in range(3)]
    x = sum(relative[i] * view["right"][i] for i in range(3))
    y = sum(relative[i] * view["up"][i] for i in range(3))
    gain = view["width"] / view["ortho_scale_bu"]
    return [view["width"] / 2 + x * gain, view["height"] / 2 - y * gain]


@pytest.fixture
def manifest() -> dict[str, Any]:
    path = CLARITY / "manifest.json"
    if not path.is_file():
        pytest.skip("requires the additive clarity render manifest")
    return read_json(path)


def test_caption_aware_fit_and_offscreen_camera_pointer_keep_real_coordinates() -> None:
    renderer = load_script("render_review_clarity")
    points = [[-150, 0, -100], [170, 0, 110], [200, 0, 5]]
    view = renderer.fit_view([0, -1000, 0], [0, 0, 0], points)
    assert view["right"] == pytest.approx([1, 0, 0])
    assert view["up"] == pytest.approx([0, 0, 1])
    assert view["forward"] == pytest.approx([0, 1, 0])
    assert view["fit_margin"] == {"x": [0.06, 0.94], "y": [0.22, 0.94]}
    for point in points:
        pixel = independent_pixel(point, view)
        assert renderer.project_to_view(point, view) == pytest.approx(pixel)
        assert 0.06 <= pixel[0] / view["width"] <= 0.94
        assert 0.22 <= pixel[1] / view["height"] <= 0.94
    camera = {
        "camera_id": "SYNTHETIC_DISPLAY_TEST",
        "camera_to_world": [[1, 0, 0, 100000], [0, 1, 0, 0], [0, 0, 1, 5], [0, 0, 0, 1]],
    }
    pointer = renderer.camera_marker_records([camera], view)[0]
    assert pointer["source_position_bu"] == [100000, 0, 5]
    assert pointer["uncropped_pixel"] == pytest.approx(independent_pixel([100000, 0, 5], view))
    assert pointer["is_offscreen"] is True
    assert pointer["screen_anchor_pixel"][0] == view["width"] - 45
    assert pointer["uncropped_pixel"][0] > view["width"]
    assert pointer["indicator_purpose"] == "DISPLAY_ONLY_SOURCE_LOCATION_NOT_CAMERA_RELOCATION"


def test_clarity_renderer_refuses_truth_and_unlisted_inputs_before_reading_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    renderer = load_script("render_review_clarity")

    def forbidden_read(_path: Path) -> bytes:
        raise AssertionError("clarity renderer read an input before checking its allowlist")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    for relative in (
        "data/finalization/local_run/dataset/evaluation/office/ground_truth.json",
        "data/finalization/local_run/dataset/simulation/office/recipe.json",
        "data/finalization/local_run/diagnostics/office/projection_evaluation.json",
        "human_review/unlisted_public.json",
        "../escape.json",
    ):
        with pytest.raises(ValueError):
            renderer.read_public(ROOT / relative, repo_root=ROOT)


def test_complete_floor_fits_required_context_and_tracks_fixed_cameras_during_approach(
    manifest: dict[str, Any],
) -> None:
    floor, bounds = manifest["floor"], manifest["floor_display_bounds_bu"]
    view = floor["review_camera"]
    assert (view["width"], view["height"]) == (1280, 800)
    assert floor["fit_margin"] == {"x": [0.06, 0.94], "y": [0.22, 0.94]}
    points = floor["fit_points_bu"]
    expected_corners = itertools.product(
        *[(bounds["minimum"][i], bounds["maximum"][i]) for i in range(3)]
    )
    assert set(expected_corners).issubset({tuple(point) for point in points})
    calibrations = manifest["camera_calibrations"]
    source_positions = {
        camera["camera_id"]: [camera["camera_to_world"][i][3] for i in range(3)]
        for camera in calibrations
    }
    assert all(position in points for position in source_positions.values())
    audit_path = ROOT / "data/scene_audit/school_v3_semantic_audit.json"
    if audit_path.is_file():
        for area in read_json(audit_path)["objects"]:
            if area["object"].startswith("AREA_1F_"):
                for axis in (0, 1):
                    assert bounds["minimum"][axis] <= area["bounding_box"]["minimum"][axis]
                    assert bounds["maximum"][axis] >= area["bounding_box"]["maximum"][axis]
    for point, pixel in zip(points, floor["projected_fit_pixels"], strict=True):
        assert pixel == pytest.approx(independent_pixel(point, view))
        assert 0.06 <= pixel[0] / view["width"] <= 0.94
        assert 0.22 <= pixel[1] / view["height"] <= 0.94
    assert len(manifest["approach_frames"]) == 25
    assert manifest["approach_fps"] == 5
    for index, row in enumerate([floor, *manifest["approach_frames"]]):
        frame_view = row["review_camera"]
        assert len(row["source_camera_markers"]) == len(source_positions) == 2
        for marker in row["source_camera_markers"]:
            position = source_positions[marker["camera_id"]]
            assert marker["source_position_bu"] == position
            pixel = independent_pixel(position, frame_view)
            assert marker["uncropped_pixel"] == pytest.approx(pixel)
            assert marker["screen_anchor_pixel"] == pytest.approx(
                [
                    max(45, min(frame_view["width"] - 45, pixel[0])),
                    max(150, min(frame_view["height"] - 45, pixel[1])),
                ]
            )
            assert marker["is_offscreen"] is not (
                45 <= pixel[0] <= frame_view["width"] - 45
                and 150 <= pixel[1] <= frame_view["height"] - 45
            )
        if index:
            assert row["frame_id"] == index - 1
            assert row["timestamp"] == (index - 1) / 5
            assert row["person_movement_changed"] is False


def test_hr02_uses_public_frame_and_approved_body_with_pending_semantics(
    manifest: dict[str, Any],
) -> None:
    body = manifest["hr02"]
    visual = read_json(REVIEW / "frames/visual_manifest.json")
    motion = read_json(REVIEW / "frames/motion_context/motion_manifest.json")
    geometry = read_json(REVIEW / "geometry_evidence.json")
    settings = read_json(REVIEW / "settings_evidence.json")
    office = next(stream for stream in settings["streams"] if stream["site_id"] == "office")
    frame = motion["frames"][20]
    assert body["body_frame_id"] == 20
    assert body["footpoint_bu"] == frame["body_base_bu"]
    assert body["public_projected_landmark_bu"] == frame["landmark_position_bu"]
    assert body["landmark_position_bu"][:2] == body["public_projected_landmark_bu"][:2]
    assert body["footpoint_bu"][:2] == body["landmark_position_bu"][:2]
    assert body["floor_z_bu"] == body["footpoint_bu"][2] == visual["approved_support_z_bu"]
    assert body["landmark_z_bu"] == office["landmark_plane"]["point"][2]
    assert body["landmark_position_bu"][2] == body["landmark_z_bu"]
    # The original Blender frame stored the public landmark as a native float32.
    # The new dimension reference retains the exact source-context plane value.
    native_plane_z = struct.unpack("!f", struct.pack("!f", body["landmark_z_bu"]))[0]
    assert body["public_projected_landmark_bu"][2] == native_plane_z
    assert body["offset_bu"] == body["landmark_z_bu"] - body["floor_z_bu"]
    assert body["offset_m"] == pytest.approx(body["offset_bu"] * 0.0247)
    assert body["offset_m"] == pytest.approx(1.3597349528884888)
    assert body["body_policy"] == {
        key: geometry["body_policy_m"][key] for key in ("radius", "height", "clearance")
    }
    assert body["body_policy"] == {"radius": 0.3, "height": 1.7, "clearance": 0.05}
    assert 0 < body["offset_m"] < body["body_policy"]["height"]
    assert body["binding_authority"] == "PENDING_HR02_NOT_APPROVED"
    assert body["joint_pose_authority"] == "DISPLAY_ONLY"
    guide = load_script("build_spatial_guide")
    display = guide.read_clarity_manifest(CLARITY / "manifest.json", REVIEW / "index.html")
    projection = display["hr02"]["display_projection"]
    body_top = [
        *body["footpoint_bu"][:2],
        body["floor_z_bu"] + body["body_policy"]["height"] / 0.0247,
    ]
    assert projection["body_top_bu"] == body_top
    for field, point in (
        ("foot_pixel", body["footpoint_bu"]),
        ("landmark_pixel", body["landmark_position_bu"]),
        ("body_top_pixel", body_top),
    ):
        expected = independent_pixel(point, body["review_camera"])
        assert projection[field] == pytest.approx(expected)
        assert guide.project_clarity_point(point, body["review_camera"]) == pytest.approx(expected)
    assert projection["projection_basis"] == "ACTUAL_RENDER_ORTHOGRAPHIC_RIGHT_UP"
    assert projection["source_coordinates_changed"] is False
    assert projection["gt_used"] is False
    assert projection["binding_authority"] == body["binding_authority"]
    assert manifest["camera_calibrations"] == [
        camera["source_calibration"] for camera in office["cameras"]
    ]
    assert manifest["calibration_context_sha256"] == office["context_sha256"]
    assert manifest["visibility_timeline"] == [
        {key: frame[key] for key in ("frame_id", "timestamp", "state", "camera_evidence")}
        for frame in motion["frames"]
    ]
    for camera, direction in zip(
        manifest["camera_calibrations"], manifest["calibrated_camera_geometry"], strict=True
    ):
        rotation = camera["camera_to_world"]
        expected_corners = [
            (0, 0),
            (camera["width"], 0),
            (camera["width"], camera["height"]),
            (0, camera["height"]),
        ]
        for ray, expected in zip(
            direction["image_corner_unit_rays_world"], expected_corners, strict=True
        ):
            assert math.sqrt(sum(value * value for value in ray)) == pytest.approx(1)
            local = [sum(rotation[i][j] * ray[i] for i in range(3)) for j in range(3)]
            pixel = [
                camera["cx"] + camera["fx"] * local[0] / -local[2],
                camera["cy"] - camera["fy"] * local[1] / -local[2],
            ]
            assert pixel == pytest.approx(expected, abs=0.001)
        assert direction["authority"] == "CALIBRATION_GEOMETRY_ONLY_NOT_FOV_OCCLUSION_CERTIFICATION"


def test_clarity_preserves_source_review_inputs_and_existing_evidence_authority(
    manifest: dict[str, Any],
) -> None:
    template = read_json(REVIEW / "review_template.json")
    decisions = read_json(REVIEW / "decisions.json")
    builder = load_script("build_dashboard")
    assert builder.review_identity(decisions) == builder.review_identity(template)
    assert builder.payload_hash(template) == PAYLOAD_SHA
    assert len(template["items"]) == 4
    assert manifest["schema_version"] == "phase1-human-review-clarity-v1"
    assert manifest["result_type"] == "DIAGNOSTIC"
    assert manifest["source_sha256"] == manifest["source_sha256_after"] == SOURCE_SHA
    assert manifest["source_preserved"] is True
    for key in (
        "source_saved",
        "source_modified",
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "physical_authority_changed",
        "formal_execution_enabled",
        "person_movement_changed",
        "new_route_generated",
    ):
        assert manifest[key] is False
    assert manifest["render_policy"]["cutaway_purpose"] == "DISPLAY_ONLY"
    assert manifest["render_policy"]["native_camera_positions_changed"] is False
    assert manifest["render_policy"]["visibility_or_collision_proof"] is False
    assert manifest["tested_scope_authority"] == "PENDING_HR01_NOT_CERTIFIED"
    frozen = template["metadata"]["input_hashes"]
    assert len(frozen) == 29
    protected = manifest["preserved_existing_hashes"]
    for row in frozen:
        assert protected[row["path"]] == row["sha256"]
    for relative, expected in protected.items():
        # Real human decisions are editable; preserve their immutable questions.
        if relative == "human_review/decisions.json":
            continue
        path = ROOT / relative
        if path.is_file():
            assert digest(path) == expected, relative
    renderer = load_script("render_review_clarity")
    assert {row["path"] for row in manifest["inputs"]} == renderer.INPUT_RELATIVE
    for row in manifest["inputs"]:
        assert not any(
            word in row["path"].lower() for word in ("ground_truth", "evaluation", "simulation")
        )
        path = ROOT / row["path"]
        if path.is_file():
            assert digest(path) == row["sha256"]
    assert manifest["renderer_sha256"] == digest(REVIEW / "render_review_clarity.py")
    for row in [
        manifest["floor"],
        manifest["office"],
        manifest["hr02"],
        *manifest["approach_frames"],
    ]:
        path = CLARITY / row["path"]
        if path.is_file():
            assert digest(path) == row["sha256"]
