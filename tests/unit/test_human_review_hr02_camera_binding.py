"""Camera-binding evidence must distinguish annotation, projection and visibility."""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import math
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "human_review"
INFERENCE = "data/finalization/local_run/dataset/inference/office"
PROJECTED = (
    "data/finalization/local_run/diagnostics/office/policy_graph_primary/projected_frames.json"
)
SOURCE_SHA = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
CAMERA_IDS = ("CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR")
BOXES = [
    {
        "object_id": "AREA_1F_OFFICE",
        "bounds_min": [1145.0, 1710.0, 15.0],
        "bounds_max": [1495.0, 2310.0, 155.0],
    },
    {
        "object_id": "AREA_1F_AUDITORIUM",
        "bounds_min": [1520.0, 1575.0, 15.0],
        "bounds_max": [2030.0, 2315.0, 155.0],
    },
]


@pytest.fixture
def audit() -> Any:
    spec = importlib.util.spec_from_file_location(
        "hr02_camera_binding_audit", REVIEW / "inspect_hr02_camera_binding.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def camera_builder() -> Any:
    spec = importlib.util.spec_from_file_location(
        "hr02_camera_review_builder", REVIEW / "build_hr02_camera_review.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def renderer() -> Any:
    spec = importlib.util.spec_from_file_location(
        "hr02_camera_audit_renderer", REVIEW / "render_hr02_camera_audit.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def public_inputs() -> list[Any]:
    paths = [
        ROOT / INFERENCE / "context.json",
        ROOT / INFERENCE / "observations.json",
        ROOT / INFERENCE / "visibility.json",
        ROOT / PROJECTED,
        REVIEW / "frames/motion_context/motion_manifest.json",
    ]
    if not all(path.is_file() for path in paths):
        pytest.skip("requires materialized frozen public camera evidence")
    return [json.loads(path.read_text()) for path in paths]


@pytest.fixture
def audit_artifacts() -> tuple[dict[str, Any], dict[str, Any]]:
    directory = REVIEW / "frames/hr02_camera_audit"
    paths = (directory / "audit_data.json", directory / "manifest.json")
    if not all(path.is_file() for path in paths):
        pytest.skip("requires the additive source-ray diagnostic evidence")
    return json.loads(paths[0].read_text()), json.loads(paths[1].read_text())


@pytest.fixture
def display_contract(
    audit_artifacts: tuple[dict[str, Any], dict[str, Any]],
) -> dict[str, Any]:
    """Exercise the builder without requiring a renderer to run inside a unit test."""
    data = copy.deepcopy(audit_artifacts[0])
    if not data["images"]:
        view = {
            "position_bu": [0, 0, 0],
            "right": [1, 0, 0],
            "up": [0, 0, 1],
            "forward": [0, 1, 0],
            "ortho_scale_bu": 2000,
        }
        data["images"] = {
            name: {"width": 1920, "height": 1080, "view": view}
            for name in ("wide", "side")
        }
        data["images"]["camera_stills"] = [
            {
                "frame_id": frame_id,
                "camera_id": camera["camera_id"],
                "timestamp": frame_id / 5,
                "width": 1920,
                "height": 1080,
                "pixel_scale": 2,
                "landmark_replay": camera["landmark_replay"],
                "foot_replay": camera["foot_replay"],
            }
            for frame_id in (20, 25, 45)
            for camera in data["frames"][frame_id]["cameras"]
        ]
    return data


@pytest.mark.parametrize(
    "relative",
    [
        "data/finalization/local_run/dataset/evaluation/office/ground_truth.json",
        "data/finalization/local_run/dataset/simulation/office/recipe.json",
        "data/finalization/local_run/diagnostics/office/projection_evaluation.json",
        "human_review/unlisted_public.json",
        "../escape.json",
        f"../amidst-phase1-finalization/{INFERENCE}/context.json",
    ],
)
def test_forbidden_inputs_are_rejected_before_reading(
    audit: Any,
    relative: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_read(_path: Path) -> bytes:
        raise AssertionError("opened non-allowlisted camera evidence")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    with pytest.raises(ValueError):
        audit.read_public(relative, repo_root=ROOT)


def test_allowed_name_cannot_redirect_to_unlisted_evidence(
    audit: Any,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "unlisted.json"
    target.write_text('{"private_fixture": true}\n')
    allowed_name = tmp_path / INFERENCE / "context.json"
    allowed_name.parent.mkdir(parents=True)
    allowed_name.symlink_to(target)

    def forbidden_read(_path: Path) -> bytes:
        raise AssertionError("an allowlisted filename followed a forbidden symlink")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read)
    with pytest.raises(ValueError):
        audit.read_public(f"{INFERENCE}/context.json", repo_root=tmp_path)


def test_public_reader_preserves_object_and_visibility_list_shapes(
    audit: Any, tmp_path: Path
) -> None:
    path = tmp_path / INFERENCE / "context.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"public_fixture": true}\n')
    assert audit.read_public(f"{INFERENCE}/context.json", repo_root=tmp_path) == {
        "public_fixture": True
    }
    visibility_path = path.with_name("visibility.json")
    visibility_path.write_text('[{"public_fixture": true}]\n')
    assert audit.read_public(f"{INFERENCE}/visibility.json", repo_root=tmp_path) == [
        {"public_fixture": True}
    ]


@pytest.mark.parametrize(
    "position",
    [
        [2025.24267578125, 2314.5078125, 153.21405029296875],
        [2024.8048095703125, 1580.67431640625, 153.23199462890625],
    ],
)
def test_source_camera_centres_match_annotation_without_certifying_ownership(
    audit: Any, position: list[float]
) -> None:
    result = audit.annotation_membership(position, BOXES)
    assert result["contains"] == ["AREA_1F_AUDITORIUM"]
    assert result["ownership_authority"] == "NOT_CERTIFIED"
    rows = {row["object_id"]: row for row in result["bounds_comparison"]}
    for box in BOXES:
        row = rows[box["object_id"]]
        # Independent point-to-AABB distance, including the rear camera's Y gap.
        displacement = [
            max(
                box["bounds_min"][axis] - position[axis],
                0,
                position[axis] - box["bounds_max"][axis],
            )
            for axis in range(3)
        ]
        distance = math.hypot(*displacement)
        assert row["nearest_distance_bu"] == pytest.approx(distance)
        assert row["nearest_distance_m"] == pytest.approx(distance * 0.0247)
        assert row["contains"] is (distance == 0)


def test_annotation_boundary_is_explicit_and_does_not_expand_for_nearby_points(
    audit: Any,
) -> None:
    corner = BOXES[0]["bounds_max"]
    on_boundary = audit.annotation_membership(corner, BOXES)
    outside = audit.annotation_membership([corner[0] + 0.001, *corner[1:]], BOXES)
    assert on_boundary["contains"] == ["AREA_1F_OFFICE"]
    assert outside["contains"] == []
    assert outside["ownership_authority"] == "NOT_CERTIFIED"
    office = next(
        row for row in outside["bounds_comparison"] if row["object_id"] == "AREA_1F_OFFICE"
    )
    assert office["nearest_distance_m"] == pytest.approx(0.001 * 0.0247)


@pytest.mark.parametrize(
    "point",
    [[math.nan, 0, 0], [0, math.inf, 0], [0, 0], [0, 0, 0, 0]],
)
def test_invalid_annotation_point_fails_closed(audit: Any, point: list[float]) -> None:
    with pytest.raises(ValueError):
        audit.annotation_membership(point, BOXES)


def test_reversed_annotation_bounds_fail_closed(audit: Any) -> None:
    boxes = copy.deepcopy(BOXES)
    boxes[0]["bounds_min"][0] = boxes[0]["bounds_max"][0] + 1
    with pytest.raises(ValueError):
        audit.annotation_membership([1400, 2000, 75], boxes)


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_nonfinite_annotation_bounds_fail_closed(audit: Any, invalid: float) -> None:
    boxes = copy.deepcopy(BOXES)
    boxes[0]["bounds_min"][0] = invalid
    with pytest.raises(ValueError):
        audit.annotation_membership([1400, 2000, 75], boxes)


def test_public_frame_join_preserves_visibility_and_separates_candidate_gap_positions(
    audit: Any, public_inputs: list[Any]
) -> None:
    context, observations, visibility, projected, motion = public_inputs
    before = copy.deepcopy(public_inputs)
    frames = audit.build_public_frames(context, observations, visibility, projected, motion)
    assert public_inputs == before
    assert len(frames) == 50
    assert [frame["frame_id"] for frame in frames] == list(range(50))
    assert [frame["timestamp"] for frame in frames] == [i / 5 for i in range(50)]
    points_by_frame = {
        sample["frame_id"]: sample["projected_point"]["world_position"]
        for sample in projected["dataset"]["samples"]
        if sample["projected_point"] is not None
    }
    assert len(points_by_frame) == 26
    for frame, original in zip(frames, motion["frames"], strict=True):
        frame_id = frame["frame_id"]
        assert frame["role"] == original["role"]
        assert frame["foot_position_bu"] == original["body_base_bu"]
        assert frame["old_motion_path"] == f"../motion_context/motion_{frame_id:03d}.png"
        assert frame["landmark_position_bu"] == points_by_frame.get(
            frame_id, original["landmark_position_bu"]
        )
        source = sorted(
            (row for row in observations["frames"] if row["frame_id"] == frame_id),
            key=lambda row: row["camera_id"],
        )
        assert [row["camera_id"] for row in frame["public_records"]] == list(CAMERA_IDS)
        for record, original_observation in zip(frame["public_records"], source, strict=True):
            assert record == {
                "camera_id": original_observation["camera_id"],
                "status": original_observation["status"],
                "uv": original_observation["point_2d"],
                "gap_reason": original_observation["gap_reason"],
                "occluder_id": original_observation["occluder_id"],
            }
    assert context["source_asset_sha256"] == observations["source_asset_sha256"] == SOURCE_SHA
    assert frames[20]["public_records"][0]["status"] == "OBSERVED"
    assert all(
        all(row["status"] == "GAP" and row["uv"] is None for row in frame["public_records"])
        for frame in frames[21:45]
    )
    assert frames[45]["public_records"][1]["status"] == "OBSERVED"


@pytest.mark.parametrize(
    "corruption",
    [
        "source_identity",
        "observation_timestamp",
        "visibility_timestamp",
        "visibility_status",
        "visibility_occluder",
        "duplicate_observation",
        "missing_projection",
        "projection_timestamp",
        "changed_uv",
        "gap_with_projected_point",
        "motion_timestamp",
        "motion_position",
        "motion_gt_flag",
        "motion_authority_flag",
    ],
)
def test_corrupted_or_promoted_public_frame_inputs_fail_closed(
    audit: Any, public_inputs: list[Any], corruption: str
) -> None:
    context, observations, visibility, projected, motion = copy.deepcopy(public_inputs)
    if corruption == "source_identity":
        context["source_asset_sha256"] = "0" * 64
    elif corruption == "observation_timestamp":
        observations["frames"][0]["timestamp"] = 0.01
    elif corruption == "visibility_timestamp":
        visibility[0]["timestamp"] = 0.01
    elif corruption == "visibility_status":
        visibility[0]["status"] = "GAP"
    elif corruption == "visibility_occluder":
        visibility[1]["occluder_id"] = "unrelated"
    elif corruption == "duplicate_observation":
        observations["frames"][1] = copy.deepcopy(observations["frames"][0])
    elif corruption == "missing_projection":
        projected["dataset"]["samples"].pop()
    elif corruption == "projection_timestamp":
        projected["dataset"]["samples"][0]["timestamp"] = 0.01
    elif corruption == "changed_uv":
        projected["dataset"]["samples"][0]["uv"][0] += 1
    elif corruption == "gap_with_projected_point":
        projected["dataset"]["samples"][1]["projected_point"] = copy.deepcopy(
            projected["dataset"]["samples"][0]["projected_point"]
        )
    elif corruption == "motion_timestamp":
        motion["frames"][0]["timestamp"] = 0.01
    elif corruption == "motion_position":
        motion["frames"][0]["landmark_position_bu"][0] += 1
    elif corruption == "motion_gt_flag":
        motion["gt_used"] = True
    elif corruption == "motion_authority_flag":
        motion["physical_authority_changed"] = True
    with pytest.raises(ValueError):
        audit.build_public_frames(context, observations, visibility, projected, motion)


def test_audit_receipt_keeps_pending_semantics_and_source_visibility_separate(
    audit_artifacts: tuple[dict[str, Any], dict[str, Any]], public_inputs: list[Any]
) -> None:
    data, receipt = audit_artifacts
    context, observations, _, _, motion = public_inputs
    assert data["schema_version"] == "phase1-hr02-camera-binding-audit-v1"
    assert data["result_type"] == receipt["result_type"] == "DIAGNOSTIC"
    assert data["source_sha256"] == receipt["source_sha256"] == SOURCE_SHA
    assert data["review_payload_sha256"] == receipt["review_payload_sha256"] == (
        "e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463"
    )
    for key in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "physical_authority_changed",
        "formal_execution_enabled",
        "human_decisions_applied",
        "source_saved",
        "source_modified",
    ):
        assert data[key] is receipt[key] is False
    assert receipt["source_preserved"] is True
    assert receipt["data"]["path"] == "audit_data.json"
    raw = (REVIEW / "frames/hr02_camera_audit/audit_data.json").read_bytes()
    assert receipt["data"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert not any(
        forbidden in row["path"]
        for row in receipt["inputs"]
        for forbidden in ("evaluation/", "simulation/", "ground_truth")
    )
    assert [camera["calibration"] for camera in data["cameras"]] == context["cameras"]
    assert all(camera["calibration_identical"] is True for camera in data["cameras"])
    assert all(camera["ownership_authority"] == "NOT_CERTIFIED" for camera in data["cameras"])
    assert data["binding"]["authority"] == "PENDING_HR02"
    assert data["summary"]["original_source_point_available"] is False
    assert data["summary"]["room_ownership"] == "NOT_CERTIFIED"
    assert data["summary"]["suggested_review_state"] == "KEEP_REVIEW"
    assert data["summary"]["decision_written"] is False
    protocol = data["diagnostic_protocol"]
    assert protocol["scale_m_per_bu"] == 0.0247
    assert protocol["numeric_policy"] == "EXISTING_RAYCASTER_NATIVE_BU_UNCHANGED"
    assert protocol["ray_endpoint_tolerance_bu"] == 0.001
    assert protocol["ray_endpoint_tolerance_m"] == 0.001 * 0.0247
    assert protocol["sourcegeometryscope"] == "FULL_EVALUATED_VIEWPORT_ALLOWED_MESH"
    assert protocol["annotation_meshes_excluded"] is True
    assert protocol["hide_render_materials_do_not_remove_blockers"] is True
    assert data["summary"]["recorded_counts"] == {"OBSERVED": 26, "GAP": 74}
    assert data["summary"]["replay_counts"] == {"CLEAR": 26, "OCCLUDED": 74}
    assert data["summary"]["foot_replay_counts"] == {"CLEAR": 10, "OCCLUDED": 90}
    assert data["summary"]["observed_replay_mismatches"] == []
    mixed_visibility = [
        {"frame_id": frame["frame_id"], "camera_id": camera["camera_id"]}
        for frame in data["frames"]
        for camera in frame["cameras"]
        if camera["landmark_replay"]["ray_reason"] == "CLEAR"
        and camera["foot_replay"]["ray_reason"] == "OCCLUDED"
    ]
    assert data["summary"]["landmark_clear_foot_occluded"] == mixed_visibility
    assert len(mixed_visibility) == 16
    assert len(data["frames"]) == 50
    for frame, frozen in zip(data["frames"], motion["frames"], strict=True):
        assert frame["frame_id"] == frozen["frame_id"]
        assert frame["timestamp"] == frozen["timestamp"]
        assert frame["role"] == frozen["role"]
        assert frame["foot_position_bu"] == frozen["body_base_bu"]
        for replay in frame["cameras"]:
            original = next(
                row for row in observations["frames"]
                if row["camera_id"] == replay["camera_id"]
                and row["frame_id"] == frame["frame_id"]
            )
            assert replay["public_record"] == {
                "camera_id": original["camera_id"],
                "status": original["status"],
                "uv": original["point_2d"],
                "gap_reason": original["gap_reason"],
                "occluder_id": original["occluder_id"],
            }
            for key in ("landmark_replay", "foot_replay"):
                assert replay[key]["authority"] == (
                    "SOURCE_RAY_TO_PUBLIC_PROJECTION_OR_CANDIDATE_NOT_ORIGINAL_3D"
                )


def test_replayed_pixel_depth_and_blocker_are_geometrically_consistent(
    audit_artifacts: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    data, _ = audit_artifacts
    cameras = {row["camera_id"]: row for row in data["cameras"]}
    shifts = []
    for frame in data["frames"]:
        for row in frame["cameras"]:
            camera = cameras[row["camera_id"]]
            calibration = camera["calibration"]
            matrix = np.asarray(calibration["camera_to_world"], dtype=float)
            origin = np.asarray(camera["position_bu"])
            assert origin.tolist() == matrix[:3, 3].tolist()
            assert camera["position_m"] == pytest.approx((origin * 0.0247).tolist())
            for label in ("landmark", "foot"):
                target = np.asarray(frame[f"{label}_position_bu"])
                replay = row[f"{label}_replay"]
                # Independent double-precision inverse, rather than calling the
                # producer's Blender float32 forward-project helper again.
                local = np.linalg.solve(matrix, np.r_[target, 1])
                depth = -local[2]
                expected_uv = [
                    calibration["fx"] * local[0] / depth + calibration["cx"],
                    calibration["cy"] - calibration["fy"] * local[1] / depth,
                ]
                # This accounts only for native float32 arithmetic, not accuracy
                # acceptance, Coverage epsilon, or camera/landmark authority.
                assert replay["pixel"] == pytest.approx(expected_uv, abs=0.002)
                assert replay["axial_depth_bu"] == pytest.approx(depth, abs=0.002)
                expected_frustum = (
                    calibration["clip_start"] <= depth <= calibration["clip_end"]
                    and 0 <= expected_uv[0] < calibration["width"]
                    and 0 <= expected_uv[1] < calibration["height"]
                )
                assert replay["in_frustum"] is bool(expected_frustum)
                hit = replay["hit"]
                if hit is not None:
                    assert replay["ray_reason"] == "OCCLUDED"
                    assert hit["object_id"] == replay["occluder_id"]
                    assert hit["face_id_authority"] == (
                        "EVALUATED_VIEWPORT_POLYGON_NOT_AUTOMATIC_ORIGINAL_FACE_BINDING"
                    )
                    assert isinstance(hit["evaluated_face_index"], int)
                    direction = (target - origin) / np.linalg.norm(target - origin)
                    hit_position = np.asarray(hit["position_bu"])
                    along = float(np.dot(hit_position - origin, direction))
                    assert hit["distance_bu"] == pytest.approx(along)
                    assert hit["distance_m"] == pytest.approx(along * 0.0247)
                    assert 0 <= along < float(np.linalg.norm(target - origin)) - 0.001
                    # Native mesh queries use float32; the explanatory hit must
                    # still be on that camera-to-display-point ray.
                    residual = np.linalg.norm(hit_position - origin - along * direction)
                    assert residual <= max(np.abs(hit_position)) * 2**-19
            if row["public_record"]["status"] == "OBSERVED":
                shifts.append(math.dist(row["public_record"]["uv"], row["foot_replay"]["pixel"]))
    assert data["summary"]["foot_uv_shift_range_px"] == [min(shifts), max(shifts)]
    assert min(shifts) > 40  # Body-base UV cannot silently replace the recorded landmark UV.
    binding = data["binding"]
    assert binding["offset_bu"] == binding["landmark_z_bu"] - binding["floor_z_bu"]
    assert binding["offset_m"] == pytest.approx(binding["offset_bu"] * 0.0247)
    assert binding["offset_m"] == pytest.approx(1.3597349528884888)


def test_camera_view_accepts_complete_diagnostic_contract_without_mutation(
    camera_builder: Any, display_contract: dict[str, Any]
) -> None:
    original = copy.deepcopy(display_contract)
    assert camera_builder.validate_data(display_contract) == original
    assert display_contract == original


@pytest.mark.parametrize(
    "promotion",
    [
        "gt_used",
        "human_decisions_applied",
        "source_saved",
        "source_modified",
        "original_source_3d",
        "camera_ownership",
        "body_binding",
        "source_sha",
        "review_identity",
        "camera_order",
        "missing_frame",
        "frame_timestamp",
        "nonfinite_landmark",
        "fov_type",
        "nonfinite_pixel",
        "missing_hit_face",
    ],
)
def test_camera_view_rejects_promoted_authority_or_incoherent_display_data(
    camera_builder: Any, display_contract: dict[str, Any], promotion: str
) -> None:
    # Verify the positive contract first, so missing render receipts cannot make
    # all of the distinct negative cases pass for an unrelated reason.
    camera_builder.validate_data(display_contract)
    changed = copy.deepcopy(display_contract)
    if promotion in {"gt_used", "human_decisions_applied", "source_saved", "source_modified"}:
        changed[promotion] = True
    elif promotion == "original_source_3d":
        changed["summary"]["original_source_point_available"] = True
    elif promotion == "camera_ownership":
        changed["cameras"][0]["ownership_authority"] = "APPROVED"
    elif promotion == "body_binding":
        changed["binding"]["authority"] = "APPROVED"
    elif promotion == "source_sha":
        changed["source_sha256"] = "0" * 64
    elif promotion == "review_identity":
        changed["review_payload_sha256"] = "0" * 64
    elif promotion == "camera_order":
        changed["cameras"].reverse()
    elif promotion == "missing_frame":
        changed["frames"].pop()
    elif promotion == "frame_timestamp":
        changed["frames"][0]["timestamp"] = 0.01
    elif promotion == "nonfinite_landmark":
        changed["frames"][0]["landmark_position_bu"][0] = math.nan
    elif promotion == "fov_type":
        changed["frames"][0]["cameras"][0]["landmark_replay"]["in_frustum"] = "true"
    elif promotion == "nonfinite_pixel":
        changed["frames"][0]["cameras"][0]["landmark_replay"]["pixel"][0] = math.nan
    elif promotion == "missing_hit_face":
        replay = next(
            replay
            for frame in changed["frames"]
            for camera in frame["cameras"]
            for replay in (camera["landmark_replay"], camera["foot_replay"])
            if replay["hit"] is not None
        )
        del replay["hit"]["evaluated_face_index"]
    with pytest.raises(ValueError):
        camera_builder.validate_data(changed)


@pytest.mark.parametrize(
    "relative",
    [
        "data/finalization/local_run/dataset/evaluation/office/ground_truth.json",
        "data/finalization/local_run/dataset/simulation/office/recipe.json",
        "human_review/unlisted_public.json",
    ],
)
def test_renderer_cannot_open_non_allowlisted_inputs(
    renderer: Any, relative: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden_read(_path: Path, *_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("renderer opened a non-allowlisted diagnostic input")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    with pytest.raises(ValueError):
        renderer.read_public(relative)


def test_renderer_rejects_symlink_into_unlisted_file_before_reading(
    renderer: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "unlisted.json"
    target.write_text('{"private_fixture": true}\n')
    allowed_name = tmp_path / INFERENCE / "context.json"
    allowed_name.parent.mkdir(parents=True)
    allowed_name.symlink_to(target)
    monkeypatch.setattr(renderer, "ROOT", tmp_path)

    def forbidden_read(_path: Path, *_args: Any, **_kwargs: Any) -> str:
        raise AssertionError("renderer followed an allowlisted name into unlisted evidence")

    monkeypatch.setattr(Path, "read_text", forbidden_read)
    with pytest.raises(ValueError):
        renderer.read_public(f"{INFERENCE}/context.json")


@pytest.mark.parametrize(
    "change",
    [
        "source_frame",
        "scale",
        "ray_numeric",
        "clearance",
        "body_radius",
        "camera_pose",
        "camera_calibration",
        "body_floor",
    ],
)
def test_renderer_cannot_change_source_frame_physical_policy_or_camera_binding(
    renderer: Any,
    audit_artifacts: tuple[dict[str, Any], dict[str, Any]],
    public_inputs: list[Any],
    change: str,
) -> None:
    data, context = copy.deepcopy(audit_artifacts[0]), public_inputs[0]
    renderer.verify_data(data, context)
    if change == "source_frame":
        data["source_scene"]["frame"] += 1
    elif change == "scale":
        data["diagnostic_protocol"]["scale_m_per_bu"] = 1
    elif change == "ray_numeric":
        data["diagnostic_protocol"]["ray_endpoint_tolerance_bu"] = 0.01
    elif change == "clearance":
        data["binding"]["clearance_m"] = 0
    elif change == "body_radius":
        data["binding"]["body_radius_m"] = 0.1
    elif change == "camera_pose":
        data["cameras"][0]["position_bu"][0] += 1
    elif change == "camera_calibration":
        data["cameras"][0]["calibration"]["fx"] += 1
    elif change == "body_floor":
        data["frames"][0]["foot_position_bu"][2] += 1
    with pytest.raises(ValueError):
        renderer.verify_data(data, context)


def test_wide_context_fit_has_real_orthographic_axes_and_caption_safe_bounds(
    renderer: Any,
) -> None:
    points = [[-150, 0, -100], [170, 0, 110], [200, 0, 5], [-300, 150, -40]]
    view = renderer.fit_view([0, -1000, 0], [0, 0, 0], points)
    assert (view["width"], view["height"]) == (1920, 1080)
    assert view["right"] == pytest.approx([1, 0, 0])
    assert view["up"] == pytest.approx([0, 0, 1])
    assert view["forward"] == pytest.approx([0, 1, 0])
    for point in points:
        relative = np.asarray(point) - np.asarray(view["position_bu"])
        x = float(np.dot(relative, view["right"]))
        y = float(np.dot(relative, view["up"]))
        gain = view["width"] / view["ortho_scale_bu"]
        pixel = [view["width"] / 2 + x * gain, view["height"] / 2 - y * gain]
        assert 0.08 <= pixel[0] / view["width"] <= 0.92
        assert 0.22 <= pixel[1] / view["height"] <= 0.94


def test_rendered_camera_evidence_preserves_hashes_resolution_source_pose_and_frame_labels(
    renderer: Any,
    audit_artifacts: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    directory = REVIEW / "frames/hr02_camera_audit"
    manifest_path = directory / "renderer_manifest.json"
    if not manifest_path.is_file():
        pytest.skip("requires the additive eight-image camera render receipt")
    receipt = json.loads(manifest_path.read_text())
    data, _ = audit_artifacts
    assert receipt["source_sha256"] == receipt["source_sha256_after"] == SOURCE_SHA
    assert receipt["result_type"] == "DIAGNOSTIC_NOT_CERTIFIED"
    for key in (
        "source_saved",
        "source_modified",
        "native_source_camera_poses_changed",
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "physical_authority_changed",
        "formal_execution_enabled",
    ):
        assert receipt[key] is False
    assert receipt["source_scene"] == data["source_scene"]
    assert receipt["source_mesh_instances"] == data["diagnostic_protocol"]["raycast_mesh_instances"]
    assert receipt["renderer_sha256"] == hashlib.sha256(
        (REVIEW / "render_hr02_camera_audit.py").read_bytes()
    ).hexdigest()
    inputs = {row["path"]: row["sha256"] for row in receipt["input_hashes"]}
    assert len(inputs) == len(receipt["input_hashes"])
    assert set(inputs) == renderer.INPUTS
    for relative, expected in inputs.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == expected
    records = [receipt["wide"], receipt["side"], *receipt["camera_stills"]]
    assert len({row["path"] for row in records}) == len(records) == 8
    for row in records:
        assert (row["width"], row["height"]) == (1920, 1080)
        path = directory / row["path"]
        raw = path.read_bytes()
        assert raw.startswith(b"\x89PNG\r\n\x1a\n")
        assert struct.unpack(">II", raw[16:24]) == (1920, 1080)
        assert row["sha256"] == hashlib.sha256(raw).hexdigest()
        assert row["bytes"] == len(raw)
    for row in (receipt["wide"], receipt["side"]):
        assert row["geometry_scope"] == "DISPLAY_ONLY_CUTAWAY"
        assert row["static_context_only"] is True
        assert row["baked_person_or_frame_rays"] is False
        assert "frame_id" not in row and "timestamp" not in row
        view = row["view"]
        for point in view["fit_points_bu"]:
            relative = np.asarray(point) - np.asarray(view["position_bu"])
            gain = view["width"] / view["ortho_scale_bu"]
            pixel = [
                view["width"] / 2 + float(np.dot(relative, view["right"])) * gain,
                view["height"] / 2 - float(np.dot(relative, view["up"])) * gain,
            ]
            assert 0.08 <= pixel[0] / view["width"] <= 0.92
            assert 0.22 <= pixel[1] / view["height"] <= 0.94
    assert {(row["frame_id"], row["camera_id"]) for row in receipt["camera_stills"]} == {
        (frame_id, camera_id) for frame_id in (20, 25, 45) for camera_id in CAMERA_IDS
    }
    cameras = {row["camera_id"]: row["calibration"] for row in data["cameras"]}
    for row in receipt["camera_stills"]:
        assert row["geometry_scope"] == "FULL_SOURCE_UNCUT_EVALUATED_VIEWPORT_ALLOWED_MESH"
        assert row["body_placement_authority"] == "PENDING_HR02_DISPLAY_ONLY"
        assert row["rendered_pixel_visibility_certification"] is False
        assert row["timestamp"] == row["frame_id"] / 5
        frame = data["frames"][row["frame_id"]]
        replay = next(item for item in frame["cameras"] if item["camera_id"] == row["camera_id"])
        for field in ("landmark_position_bu", "foot_position_bu"):
            assert row[field] == frame[field]
        for field in ("landmark_replay", "foot_replay", "public_record"):
            assert row[field] == replay[field]
        assert row["source_calibration"] == cameras[row["camera_id"]]
        assert row["pixel_scale"] == 2
        assert row["scaled_intrinsics"] == pytest.approx(
            {key: cameras[row["camera_id"]][key] * 2 for key in ("fx", "fy", "cx", "cy")},
            abs=0.001,
        )


def test_renderer_input_receipt_supports_actual_list_without_mutating_hashes(
    camera_builder: Any,
) -> None:
    hashes = {
        "human_review/frames/hr02_camera_audit/audit_data.json": "a" * 64,
        "human_review/frames/hr02_camera_audit/manifest.json": "b" * 64,
    }
    document = {"input_hashes": [{"path": path, "sha256": value} for path, value in hashes.items()]}
    original = copy.deepcopy(document)
    assert camera_builder.renderer_inputs(document) == hashes
    assert document == original
    assert camera_builder.renderer_inputs({"input_hashes": hashes}) == hashes


@pytest.mark.parametrize("change", ["duplicate", "parent_path", "absolute_path", "bad_sha"])
def test_renderer_input_receipt_rejects_ambiguous_or_unsafe_hash_records(
    camera_builder: Any, change: str
) -> None:
    record = {
        "path": "human_review/frames/hr02_camera_audit/audit_data.json",
        "sha256": "a" * 64,
    }
    records = [record]
    if change == "duplicate":
        records.append(copy.deepcopy(record))
    elif change == "parent_path":
        record["path"] = "../unlisted.json"
    elif change == "absolute_path":
        record["path"] = "/tmp/unlisted.json"
    elif change == "bad_sha":
        record["sha256"] = "not-a-source-hash"
    with pytest.raises(ValueError):
        camera_builder.renderer_inputs({"input_hashes": records})


def test_context_base_does_not_render_a_fixed_actor_or_frame_specific_rays(
    renderer: Any,
    audit_artifacts: tuple[dict[str, Any], dict[str, Any]],
    public_inputs: list[Any],
) -> None:
    """Execute the actual static drawing helper with a recording render surface."""
    tree = ast.parse((REVIEW / "render_hr02_camera_audit.py").read_text())
    helper = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "add_context"
    )
    surface: list[Any] = []

    def record(kind: str) -> Any:
        def callback(name: str, *args: Any, **kwargs: Any) -> None:
            surface.append(copy.deepcopy([kind, name, args, kwargs]))

        return callback

    def forbidden_actor(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("a static background rendered a fixed frame's actor")

    data = copy.deepcopy(audit_artifacts[0])
    context = public_inputs[0]
    environment = {
        "Any": Any,
        "data": data,
        "office_lo": context["zone"]["bounds_min"],
        "office_hi": context["zone"]["bounds_max"],
        "COLORS": renderer.COLORS,
        "line": record("line"),
        "sphere": record("sphere"),
        "text": record("text"),
        "add_body": forbidden_actor,
    }
    module = ast.fix_missing_locations(ast.Module(body=[helper], type_ignores=[]))
    exec(compile(module, "actual-static-context-helper", "exec"), environment)
    draw = environment["add_context"]
    result = draw({"synthetic_review_camera": True}, {"ortho_scale_bu": 1000})
    initial = copy.deepcopy(surface)
    for frame in data["frames"]:
        frame["landmark_position_bu"] = [99999, 99999, 99999]
        frame["foot_position_bu"] = [-99999, -99999, -99999]
        frame["cameras"] = []
    surface.clear()
    assert draw({"synthetic_review_camera": True}, {"ortho_scale_bu": 1000}) == result
    assert surface == initial
    assert len(surface) == 7  # Office outline, two camera origins/directions/labels.
    assert all(
        name.startswith(
            (
                "OFFICE_ANNOTATION_OUTLINE",
                "EXACT_SOURCE_CAMERA_ORIGIN",
                "CAMERA_DIRECTION",
                "SOURCE_CAMERA_LABEL",
            )
        )
        for _, name, _, _ in surface
    )
    rendered_origins = [args[0] for kind, _, args, _ in surface if kind == "sphere"]
    assert rendered_origins == [camera["position_bu"] for camera in data["cameras"]]


class FakeMeshColumn:
    def __init__(self, fields: dict[str, Any]) -> None:
        self.fields = {
            name: np.asarray(value, dtype=float if name in {"co", "vector"} else None).copy()
            for name, value in fields.items()
        }

    def __len__(self) -> int:
        return len(next(iter(self.fields.values())))

    def foreach_get(self, field: str, output: Any) -> None:
        output[:] = self.fields[field].ravel()


class FakeConvertedMesh:
    """A tiny triangular font conversion with full mesh data and a recycled ID."""

    def __init__(self, x_offset: float = 0) -> None:
        self.vertices = FakeMeshColumn(
            {"co": [[x_offset, 0, 0], [x_offset + 1, 0, 0], [x_offset, 1, 0]]}
        )
        self.edges = FakeMeshColumn(
            {"vertices": [[0, 1], [1, 2], [2, 0]], "use_edge_sharp": [False, True, False]}
        )
        self.loops = FakeMeshColumn({"vertex_index": [0, 1, 2]})
        self.polygons = FakeMeshColumn(
            {"loop_start": [0], "loop_total": [3], "use_smooth": [True]}
        )
        self.loop_triangles = FakeMeshColumn({"vertices": [[0, 1, 2]]})
        self.corner_normals = FakeMeshColumn({"vector": [[0, 0, 1]] * 3})
        self.has_custom_normals = True

    def as_pointer(self) -> int:
        return 17  # Blender can recycle temporary conversion mesh pointers.

    def calc_loop_triangles(self) -> None:
        pass


class StaleMeshInstance:
    def __init__(self, name: str, x_translation: float = 0) -> None:
        self.object_name = name
        self.matrix = np.eye(4)
        self.matrix[0, 3] = x_translation

    @property
    def obj(self) -> Any:
        raise AssertionError("cached evaluated RNA was accessed after its graph lifetime")


class LiveInstanceObject:
    """An evaluated object whose RNA geometry is valid only during its yield."""

    def __init__(self, graph: EphemeralInstanceGraph) -> None:
        self.graph = graph

    def require_live(self) -> None:
        if not self.graph.live:
            raise ReferenceError("dependency-graph iterator invalidated the evaluated geometry")

    @property
    def type(self) -> str:
        self.require_live()
        return "MESH"  # FONT or hidden prototypes can produce an actual allowed mesh instance.

    @property
    def original(self) -> Any:
        self.require_live()
        return self.graph.original

    @property
    def data(self) -> FakeConvertedMesh:
        self.require_live()
        return self.graph.mesh


class EphemeralInstanceGraph:
    mode = "VIEWPORT"

    def __init__(self, specifications: list[tuple[str, float, float]]) -> None:
        self.specifications = specifications
        self.mesh, self.matrix = FakeConvertedMesh(), np.eye(4)
        self.live, self.invalid_geometry = False, False
        self.original: Any = None
        self.current_object = LiveInstanceObject(self)

    @property
    def object_instances(self) -> Any:
        for index, (name, x_offset, x_translation) in enumerate(self.specifications):
            self.live = True
            self.original = SimpleNamespace(name=name, type="FONT" if index == 0 else "MESH")
            self.original.as_pointer = lambda index=index: index + 501
            self.original.original = self.original
            self.mesh.vertices.fields["co"][:] = [
                [x_offset, 0, 0], [x_offset + 1, 0, 0], [x_offset, 1, 0]
            ]
            if self.invalid_geometry:
                self.mesh.vertices.fields["co"][0, 0] = math.nan
            self.matrix[:] = np.eye(4)
            self.matrix[0, 3] = x_translation
            yield SimpleNamespace(
                object=self.current_object,
                matrix_world=self.matrix,
                parent=None,
                show_self=True,
            )
        self.live = False
        self.mesh.vertices.fields["co"][:] = 99999
        self.matrix[:] = 777


def fake_ephemeral_raycaster(graph: EphemeralInstanceGraph) -> Any:
    return SimpleNamespace(
        _meshes=[StaleMeshInstance("Text"), StaleMeshInstance("Plane.110", 20)],
        _depsgraph=graph,
        excluded_objects=(),
    )


def test_geometry_capture_owns_live_font_and_hidden_prototype_instances_before_advance(
    renderer: Any,
) -> None:
    graph = EphemeralInstanceGraph([("Text", 0, 0), ("Plane.110", 30, 20)])
    raycaster = fake_ephemeral_raycaster(graph)
    snapshots, fingerprint = renderer.capture_source_geometry(raycaster, np, {})
    assert len(snapshots) == 2
    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)
    assert graph.live is False
    with pytest.raises(ReferenceError):
        _ = graph.current_object.data
    by_name = {snapshot["object_name"]: snapshot for snapshot in snapshots}
    assert set(by_name) == {"Text", "Plane.110"}
    assert by_name["Text"]["geometry"]["coordinates"].tolist() == [
        [0, 0, 0], [1, 0, 0], [0, 1, 0]
    ]
    assert by_name["Text"]["geometry"]["triangles"].tolist() == [[0, 1, 2]]
    assert by_name["Text"]["geometry"]["custom_normals"].tolist() == [[0, 0, 1]] * 3
    np.testing.assert_array_equal(by_name["Text"]["matrix"], np.eye(4))
    expected_second_matrix = np.eye(4)
    expected_second_matrix[0, 3] = 20
    np.testing.assert_array_equal(by_name["Plane.110"]["matrix"], expected_second_matrix)
    before = copy.deepcopy(snapshots)
    graph.mesh.vertices.fields["co"] += 100
    graph.matrix[0, 3] += 50
    for snapshot, original in zip(snapshots, before, strict=True):
        np.testing.assert_array_equal(snapshot["matrix"], original["matrix"])
        for key in snapshot["geometry"]:
            np.testing.assert_array_equal(snapshot["geometry"][key], original["geometry"][key])
    _, repeated_fingerprint = renderer.capture_source_geometry(raycaster, np, {})
    assert repeated_fingerprint == fingerprint


def test_reused_instance_mesh_buffer_cannot_alias_distinct_source_geometry(
    renderer: Any,
) -> None:
    graph = EphemeralInstanceGraph([("Text", 0, 0), ("Plane.110", 30, 20)])
    snapshots, _ = renderer.capture_source_geometry(fake_ephemeral_raycaster(graph), np, {})
    by_name = {snapshot["object_name"]: snapshot for snapshot in snapshots}
    np.testing.assert_array_equal(
        by_name["Plane.110"]["geometry"]["coordinates"], [[30, 0, 0], [31, 0, 0], [30, 1, 0]]
    )
    assert not np.shares_memory(
        by_name["Text"]["geometry"]["coordinates"],
        by_name["Plane.110"]["geometry"]["coordinates"],
    )
    assert not any(
        np.shares_memory(snapshot["geometry"]["coordinates"], graph.mesh.vertices.fields["co"])
        or np.shares_memory(snapshot["matrix"], graph.matrix)
        for snapshot in snapshots
    )


@pytest.mark.parametrize("failure", ["inventory_mismatch", "invalid_geometry"])
def test_source_capture_rejects_missing_or_invalid_blocker_instead_of_dropping_it(
    renderer: Any, failure: str
) -> None:
    graph = EphemeralInstanceGraph([("Text", 0, 0), ("Plane.110", 30, 20)])
    raycaster = fake_ephemeral_raycaster(graph)
    if failure == "inventory_mismatch":
        graph.specifications.pop()
    else:
        graph.invalid_geometry = True
    with pytest.raises(ValueError):
        renderer.capture_source_geometry(raycaster, np, {})
