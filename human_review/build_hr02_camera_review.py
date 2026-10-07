"""Build a GT-free diagnostic camera/binding view from hash-bound audit evidence.

The builder reads only the new audit receipts, their rendered images, and the
unchanged existing motion PNGs. It does not calculate visibility, apply human
decisions, change binding, or read the Blender scene or simulation/evaluation.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "human_review/frames/hr02_camera_audit"
SOURCE_SHA256 = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
REVIEW_HASH = "e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463"
FALSE_FLAGS = (
    "gt_used",
    "evaluation_files_read",
    "simulation_recipe_read",
    "physical_authority_changed",
    "formal_execution_enabled",
    "source_saved",
    "source_modified",
    "human_decisions_applied",
)
CAMERA_IDS = ("CAM_1F_AUDITORIUM_FRONT", "CAM_1F_AUDITORIUM_REAR")
RENDERER_FALSE_FLAGS = tuple(key for key in FALSE_FLAGS if key != "human_decisions_applied") + (
    "native_source_camera_poses_changed",
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def finite_vector(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 3
        and all(isinstance(number, int | float) and math.isfinite(number) for number in value)
    )


def audit_file(path: Path, directory: Path, names: set[str]) -> Path:
    """Reject other source packages before reading JSON or template bytes."""
    if path.name not in names or path.resolve().parent != directory.resolve():
        raise ValueError("camera review accepts only named local audit evidence")
    return path


def local_image(relative: str, directory: Path, *, motion: bool = False) -> Path:
    """Bound images to the new renderer output or original motion folder."""
    path = Path(relative)
    if (
        path.is_absolute()
        or "\\" in relative
        or any(character in relative for character in (":", "?", "#", "\x00"))
        or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}
    ):
        raise ValueError("camera review accepts local raster image paths only")
    resolved = (directory / path).resolve()
    boundary = directory.parent / "motion_context" if motion else directory
    if not resolved.is_relative_to(boundary.resolve()):
        raise ValueError("camera review image leaves its declared evidence folder")
    if not resolved.is_file():
        raise ValueError("camera review image is missing")
    return resolved


def validate_replay(row: dict[str, Any]) -> None:
    if not isinstance(row.get("in_frustum"), bool) or not isinstance(row.get("ray_reason"), str):
        raise ValueError("camera replay must expose separate FOV and source raycast results")
    pixel = row.get("pixel")
    if pixel is not None and (
        not isinstance(pixel, list)
        or len(pixel) != 2
        or any(not isinstance(value, int | float) or not math.isfinite(value) for value in pixel)
    ):
        raise ValueError("camera replay pixel must be finite or unavailable")
    hit = row.get("hit")
    if hit is not None:
        if (
            not isinstance(hit.get("object_id"), str)
            or not isinstance(hit.get("evaluated_face_index"), int)
            or not finite_vector(hit.get("position_bu"))
            or any(
                not isinstance(hit.get(key), int | float) or not math.isfinite(hit[key])
                for key in ("distance_bu", "distance_m")
            )
        ):
            raise ValueError("camera replay hit must preserve source object/face/measurements")


def validate_data(data: dict[str, Any]) -> dict[str, Any]:
    """Validate display boundaries without interpreting scene semantics."""
    if (
        data.get("source_sha256") != SOURCE_SHA256
        or data.get("review_payload_sha256") != REVIEW_HASH
        or data.get("result_type") != "DIAGNOSTIC"
        or any(data.get(key) is not False for key in FALSE_FLAGS)
    ):
        raise ValueError("camera review must preserve source, pending questions and GT isolation")
    summary = data.get("summary", {})
    if summary.get("original_source_point_available") is not False:
        raise ValueError("camera review may not present original 3D or GT as decision evidence")
    if (
        any(
            not isinstance(summary.get(key), dict)
            for key in ("recorded_counts", "replay_counts", "foot_replay_counts")
        )
        or any(
            not isinstance(summary.get(key), list)
            for key in ("observed_replay_mismatches", "landmark_clear_foot_occluded")
        )
        or not isinstance(summary.get("foot_uv_shift_range_px"), list)
        or len(summary["foot_uv_shift_range_px"]) != 2
    ):
        raise ValueError("camera review requires separate landmark and foot replay summaries")
    cameras = data.get("cameras", [])
    if tuple(camera.get("camera_id") for camera in cameras) != CAMERA_IDS:
        raise ValueError("camera review must preserve the existing FRONT and REAR cameras")
    for camera in cameras:
        if (
            not finite_vector(camera.get("position_bu"))
            or not finite_vector(camera.get("position_m"))
            or camera.get("calibration_identical") is not True
            or not isinstance(camera.get("office_aabb_contains_camera"), bool)
            or camera.get("ownership_authority") != "NOT_CERTIFIED"
            or not isinstance(camera.get("annotation_containments"), list)
        ):
            raise ValueError(
                "camera review requires unchanged calibration and unresolved ownership"
            )
    binding = data.get("binding", {})
    if (
        binding.get("authority") != "PENDING_HR02"
        or binding.get("body_height_m") != 1.7
        or binding.get("body_radius_m") != 0.3
        or binding.get("clearance_m") != 0.05
    ):
        raise ValueError("camera view may show only the current pending diagnostic body binding")
    for key in ("floor_z_bu", "landmark_z_bu", "offset_bu", "offset_m"):
        if not isinstance(binding.get(key), int | float) or not math.isfinite(binding[key]):
            raise ValueError("pending binding must retain finite source-derived values")
    frames = data.get("frames", [])
    if len(frames) != 50:
        raise ValueError("camera review requires all fifty existing motion samples")
    for index, frame in enumerate(frames):
        if (
            frame.get("frame_id") != index
            or not isinstance(frame.get("timestamp"), int | float)
            or not math.isclose(frame["timestamp"], index / 5, rel_tol=0, abs_tol=1e-9)
            or not finite_vector(frame.get("landmark_position_bu"))
            or not finite_vector(frame.get("foot_position_bu"))
            or not isinstance(frame.get("role"), str)
        ):
            raise ValueError(
                "camera review must preserve frame order, timestamps and display positions"
            )
        if tuple(row.get("camera_id") for row in frame.get("cameras", [])) != CAMERA_IDS:
            raise ValueError("each camera review frame must retain both camera results")
        for row in frame["cameras"]:
            if not isinstance(row.get("public_record", {}).get("status"), str):
                raise ValueError("original public visibility must remain separately available")
            validate_replay(row["landmark_replay"])
            validate_replay(row["foot_replay"])
    images = data.get("images", {})
    for name in ("wide", "side"):
        image = images.get(name, {})
        view = image.get("view", {})
        if (
            (image.get("width"), image.get("height")) != (1920, 1080)
            or any(
                not finite_vector(view.get(key))
                for key in ("position_bu", "right", "up", "forward")
            )
            or not isinstance(view.get("ortho_scale_bu"), int | float)
            or not math.isfinite(view["ortho_scale_bu"])
            or view["ortho_scale_bu"] <= 0
        ):
            raise ValueError("model overlays require source-bound fixed orthographic views")
    stills = images.get("camera_stills", [])
    expected = {(frame, camera) for frame in (20, 25, 45) for camera in CAMERA_IDS}
    if (
        len(stills) != 6
        or {(still["frame_id"], still["camera_id"]) for still in stills} != expected
    ):
        raise ValueError("source camera stills must cover both cameras at the three labelled times")
    for still in stills:
        if (still.get("width"), still.get("height"), still.get("pixel_scale")) != (
            1920,
            1080,
            2,
        ) or not math.isclose(still["timestamp"], still["frame_id"] / 5, rel_tol=0, abs_tol=1e-9):
            raise ValueError("source camera still pixels must retain their explicit scale and time")
        validate_replay(still["landmark_replay"])
        validate_replay(still["foot_replay"])
    return data


def renderer_records(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept the renderer's explicit image receipt, never other source paths."""
    if (
        not isinstance(document.get("wide"), dict)
        or not isinstance(document.get("side"), dict)
        or not isinstance(document.get("camera_stills"), list)
    ):
        raise ValueError("renderer receipt must list its wide, side and source-camera images")
    return [document["wide"], document["side"], *document["camera_stills"]]


def renderer_inputs(document: dict[str, Any]) -> dict[str, str]:
    """Index explicit producer hashes, rejecting ambiguous duplicate records."""
    records = document.get("input_hashes")
    if isinstance(records, dict):
        records = [{"path": path, "sha256": value} for path, value in records.items()]
    if not isinstance(records, list):
        raise ValueError("renderer input hashes must be explicit path/hash records")
    result: dict[str, str] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("renderer input hash record must be an object")
        path, value = record.get("path"), record.get("sha256")
        if (
            not isinstance(path, str)
            or not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
            or Path(path).is_absolute()
            or ".." in Path(path).parts
            or "\\" in path
            or ":" in path
            or path in result
        ):
            raise ValueError(
                "renderer input hashes must be unique relative paths and SHA-256 values"
            )
        result[path] = value
    return result


def build_view(
    data_path: Path, manifest_path: Path, renderer_path: Path, output: Path
) -> dict[str, Any]:
    directory = output.parent
    audit_file(data_path, directory, {"audit_data.json"})
    audit_file(manifest_path, directory, {"manifest.json", "audit_manifest.json"})
    audit_file(renderer_path, directory, {"renderer_manifest.json"})
    audit_file(output, directory, {"view.html"})
    template_path = audit_file(directory / "template.html", directory, {"template.html"})
    manifest = cast(dict[str, Any], json.loads(manifest_path.read_text()))
    if (
        manifest.get("source_sha256") != SOURCE_SHA256
        or manifest.get("review_payload_sha256") != REVIEW_HASH
        or manifest.get("result_type") != "DIAGNOSTIC"
        or any(manifest.get(key) is not False for key in FALSE_FLAGS)
    ):
        raise ValueError(
            "camera producer receipt must retain diagnostic source and isolation flags"
        )
    record = manifest.get("data", {})
    if record.get("path") != data_path.name or record.get("sha256") != digest(data_path):
        raise ValueError("camera audit differs from its producer receipt")
    original_data = cast(dict[str, Any], json.loads(data_path.read_text()))
    renderer = cast(dict[str, Any], json.loads(renderer_path.read_text()))
    if (
        renderer.get("source_sha256") != SOURCE_SHA256
        or renderer.get("result_type") != "DIAGNOSTIC_NOT_CERTIFIED"
        or any(renderer.get(key) is not False for key in RENDERER_FALSE_FLAGS)
    ):
        raise ValueError(
            "renderer must preserve source cameras, geometry and diagnostic boundaries"
        )
    input_hashes = renderer_inputs(renderer)
    if input_hashes.get("human_review/frames/hr02_camera_audit/audit_data.json") != digest(
        data_path
    ) or input_hashes.get("human_review/frames/hr02_camera_audit/manifest.json") != digest(
        manifest_path
    ):
        raise ValueError("renderer must consume the unchanged hash-bound camera audit and receipt")
    data = copy.deepcopy(original_data)
    data["images"] = {
        "wide": renderer["wide"],
        "side": renderer["side"],
        "camera_stills": renderer["camera_stills"],
    }
    validate_data(data)
    receipts = renderer_records(renderer)
    expected_images = [data["images"][name]["path"] for name in ("wide", "side")]
    expected_images.extend(still["path"] for still in data["images"]["camera_stills"])
    by_path = {row["path"]: row for row in receipts}
    rendered = []
    for relative in expected_images:
        path = local_image(relative, directory)
        if relative not in by_path or by_path[relative].get("sha256") != digest(path):
            raise ValueError("camera audit image differs from its renderer receipt")
        rendered.append(
            {"path": relative, "sha256": digest(path), "size_bytes": path.stat().st_size}
        )
    motion = []
    for frame in data["frames"]:
        path = local_image(frame["old_motion_path"], directory, motion=True)
        motion.append(
            {
                "path": frame["old_motion_path"],
                "sha256": digest(path),
                "size_bytes": path.stat().st_size,
            }
        )
    encoded = json.dumps(data, ensure_ascii=False, allow_nan=False)
    encoded = (
        encoded.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    )
    output.write_text(template_path.read_text().replace("__HR02_CAMERA_AUDIT_DATA__", encoded))
    receipt = {
        "schema_version": "phase1-hr02-camera-audit-view-v1",
        "result_type": "DIAGNOSTIC",
        "source_sha256": SOURCE_SHA256,
        "review_payload_sha256": REVIEW_HASH,
        **dict.fromkeys(FALSE_FLAGS, False),
        "decisions_changed": False,
        "projection_changed": False,
        "raw_graph_changed": False,
        "original_source_point_available": False,
        "frame_count": 50,
        "fps": 5,
        "camera_still_frames": [20, 25, 45],
        "separate_public_record_and_projected_replay": True,
        "camera_stills_are_representative_not_current_playback": True,
        "original_audit_data_changed": False,
        "embedded_data": {
            "renderer_image_records_added_for_display_only": True,
            "sha256": hashlib.sha256(
                json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
            ).hexdigest(),
        },
        "data": {"path": data_path.name, "sha256": digest(data_path)},
        "producer": {"path": manifest_path.name, "sha256": digest(manifest_path)},
        "renderer": {"path": renderer_path.name, "sha256": digest(renderer_path)},
        "template": {"path": template_path.name, "sha256": digest(template_path)},
        "view": {"path": output.name, "sha256": digest(output)},
        "images": rendered,
        "unchanged_motion_images": motion,
    }
    (directory / "view_manifest.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=OUT / "audit_data.json")
    parser.add_argument("--manifest", type=Path, default=OUT / "manifest.json")
    parser.add_argument("--renderer-manifest", type=Path, default=OUT / "renderer_manifest.json")
    parser.add_argument("--output", type=Path, default=OUT / "view.html")
    args = parser.parse_args()
    receipt = build_view(args.data, args.manifest, args.renderer_manifest, args.output)
    print(
        json.dumps(
            {
                "view": str(args.output),
                "frames": receipt["frame_count"],
                "sha256": receipt["view"]["sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
