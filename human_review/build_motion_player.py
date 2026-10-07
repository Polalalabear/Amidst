"""Build the additive, GT-free source-model body-motion player.

Only the new player HTML is written. Existing guide files, PNGs, question payloads,
source geometry, and original animation players remain unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "human_review"
MOTION = HERE / "frames/motion_context"
SOURCE_SHA256 = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"
FROZEN_FRAME_KEYS = (
    "frame_id",
    "timestamp",
    "role",
    "body_base_bu",
    "landmark_position_bu",
    "camera_evidence",
    "projection_method",
    "confidence_state",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_image(base: Path, value: str) -> Path:
    if not isinstance(value, str):
        raise ValueError("motion image path must be a local PNG string")
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or any(character in value for character in ":\\%?#")
        or path.suffix.lower() != ".png"
    ):
        raise ValueError("motion image path must stay inside its PNG directory")
    resolved = (base / path).resolve()
    if base.resolve() not in resolved.parents:
        raise ValueError("motion image path escapes the manifest directory")
    return resolved


def validate_manifest(manifest: dict[str, Any], base: Path) -> dict[str, Any]:
    """Reject truth/authority changes before opening any motion image bytes."""
    if manifest.get("schema_version") != "phase1-human-review-body-motion-v1":
        raise ValueError("unsupported body-motion manifest")
    if manifest.get("result_type") != "DIAGNOSTIC":
        raise ValueError("body-motion evidence must remain DIAGNOSTIC")
    for key in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "source_saved",
        "physical_authority_changed",
        "formal_execution_enabled",
    ):
        if manifest.get(key) is not False:
            raise ValueError("body-motion display violates the evidence contract: " + key)
    if manifest.get("source_preserved") is not True:
        raise ValueError("body-motion display requires source preservation")
    if manifest.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("body-motion source hash differs from school_v3")
    if manifest.get("trajectory_basis") != "EXISTING_PUBLIC_PROJECTIONS_AND_INFERRED_CANDIDATE":
        raise ValueError("body-motion positions must reuse frozen public/inferred evidence")
    if manifest.get("joint_pose_authority") != "DISPLAY_ONLY":
        raise ValueError("joint poses must remain display-only")
    frames = manifest.get("frames", [])
    fps = manifest.get("fps", manifest.get("frame_rate_hz"))
    if len(frames) != 50 or fps != 5:
        raise ValueError("body-motion player requires 50 frames at 5 Hz")
    for index, frame in enumerate(frames):
        if frame["frame_id"] != index or not math.isclose(
            frame["timestamp"], index / 5, abs_tol=1e-9
        ):
            raise ValueError("motion frame order/timestamps differ from the frozen sequence")
        for key in ("body_base_bu", "landmark_position_bu"):
            point = frame[key]
            if len(point) != 3 or not all(math.isfinite(value) for value in point):
                raise ValueError("motion positions must be finite public/inferred 3D points")
    paths = [(safe_image(base, row["path"]), row["sha256"]) for row in frames]
    for path, expected in paths:
        if digest(path) != expected:
            raise ValueError("motion PNG hash mismatch: " + path.name)
    return manifest


def frozen_files() -> list[Path]:
    paths = [
        HERE / "decisions.json",
        HERE / "review_template.json",
        HERE / "frames/visual_manifest.json",
        HERE / "frames/player.html",
        HERE / "frames/player_template.html",
        HERE / "build_frame_player.py",
        HERE / "build_spatial_guide.py",
        HERE / "frames/spatial_context/guide.html",
        HERE / "frames/spatial_context/guide_template.html",
        HERE / "frames/spatial_context/spatial_context_manifest.json",
        *sorted((HERE / "frames").glob("*.png")),
        *sorted((HERE / "frames/spatial_context").glob("*.png")),
    ]
    return [path for path in paths if path.is_file()]


def relative_path(path: Path, output: Path) -> str:
    return Path(os.path.relpath(path, output.parent)).as_posix()


def build_player(
    manifest_path: Path,
    output_path: Path,
    *,
    gif_provenance: Path | None = None,
    topology_view: Path | None = None,
) -> dict[str, Any]:
    """Create the new player without altering the old guide or original animations."""
    manifest = validate_manifest(json.loads(manifest_path.read_text()), manifest_path.parent)
    protected = {path: digest(path) for path in frozen_files()}
    original = json.loads((HERE / "frames/visual_manifest.json").read_text())
    if original.get("gt_used") is not False:
        raise ValueError("body-motion player cannot use a Ground Truth preview")
    for current, old in zip(manifest["frames"], original["frames"], strict=True):
        if any(current[key] != old[key] for key in FROZEN_FRAME_KEYS):
            raise ValueError("motion display changed frozen public/inferred frame evidence")
    questions = json.loads((HERE / "decisions.json").read_text())
    frames = [
        {**frame, "path": relative_path(manifest_path.parent / frame["path"], output_path)}
        for frame in manifest["frames"]
    ]
    data = {
        "schema_version": "phase1-human-review-motion-player-v1",
        "result_type": "DIAGNOSTIC",
        "gt_used": False,
        "source_sha256": manifest["source_sha256"],
        "source_opened_by_player_builder": False,
        "manifest_sha256": digest(manifest_path),
        "review_payload_sha256": questions["review_payload_sha256"],
        "trajectory_basis": manifest["trajectory_basis"],
        "joint_pose_authority": manifest["joint_pose_authority"],
        "fps": 5,
        "duration_seconds": 10,
        "frames": frames,
        "old_guide": relative_path(HERE / "frames/spatial_context/guide.html", output_path),
        "old_public_player": relative_path(HERE / "frames/player.html", output_path),
        "body_dimensions_m": original["approved_body_dimensions_m"],
        "protected_original_file_count": len(protected),
    }
    if gif_provenance is not None:
        receipt = json.loads(gif_provenance.read_text())
        if (
            receipt.get("schema_version") != "phase1-human-review-motion-gif-v1"
            or receipt.get("result_type") != "DIAGNOSTIC"
            or receipt.get("gt_used") is not False
            or receipt.get("physical_authority_changed") is not False
            or receipt.get("position_or_timing_changed") is not False
            or receipt.get("source_motion_manifest_sha256") != data["manifest_sha256"]
            or receipt.get("source_frame_count") != 50
            or receipt.get("source_sampling_hz") != 5
            or receipt.get("encoded_duration_seconds") != 10
        ):
            raise ValueError("derived GIF receipt differs from the frozen motion evidence")
        asset = receipt["artifact"]
        relative = Path(asset["path"])
        if (
            relative.is_absolute()
            or len(relative.parts) != 1
            or relative.suffix.lower() != ".gif"
            or any(character in asset["path"] for character in ":\\%?#")
        ):
            raise ValueError("derived GIF must remain inside its local motion directory")
        gif_path = (gif_provenance.parent / relative).resolve()
        if gif_path.parent != gif_provenance.parent.resolve():
            raise ValueError("derived GIF path escapes the receipt directory")
        if digest(gif_path) != asset["sha256"] or gif_path.stat().st_size != asset["bytes"]:
            raise ValueError("derived GIF bytes differ from the encoder receipt")
        data["gif_asset"] = {
            **asset,
            "path": relative_path(gif_path, output_path),
            "lossy_palette_preview": receipt["lossy_palette_preview"],
            "encoded_duration_seconds": receipt["encoded_duration_seconds"],
            "result_type": "DIAGNOSTIC",
        }
    if topology_view is not None:
        expected = HERE / "frames/topology_context/view.html"
        if topology_view.resolve() != expected.resolve() or not topology_view.is_file():
            raise ValueError("topology link requires the separate local topology review page")
        topology_manifest = topology_view.parent / "topology_manifest.json"
        receipt = json.loads(topology_manifest.read_text())
        if (
            receipt.get("schema_version") != "phase1-human-review-topology-manifest-v1"
            or receipt.get("result_type") != "DIAGNOSTIC"
            or receipt.get("gt_used") is not False
            or receipt.get("physical_authority_changed") is not False
            or receipt.get("formal_execution_enabled") is not False
            or receipt.get("raw_graph_changed") is not False
            or receipt.get("source_sha256") != data["source_sha256"]
            or receipt.get("review_payload_sha256") != data["review_payload_sha256"]
            or receipt.get("view", {}).get("sha256") != digest(topology_view)
        ):
            raise ValueError("topology page receipt differs from the frozen review evidence")
        data["topology_view"] = relative_path(topology_view, output_path)
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    encoded = encoded.replace("</", "<\\/").replace("\u2028", "\\u2028")
    encoded = encoded.replace("\u2029", "\\u2029")
    template = (MOTION / "player_template.html").read_text()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template.replace("__MOTION_PLAYER_DATA__", encoded))
    if any(digest(path) != expected for path, expected in protected.items()):
        raise RuntimeError("new player generation changed existing review evidence")
    return {
        "player": str(output_path),
        "player_sha256": digest(output_path),
        "frame_count": len(frames),
        "review_payload_sha256": data["review_payload_sha256"],
        "protected_original_file_count": len(protected),
        "gt_used": False,
        "result_type": "DIAGNOSTIC",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MOTION / "motion_manifest.json")
    parser.add_argument("--output", type=Path, default=MOTION / "player.html")
    parser.add_argument("--gif-provenance", type=Path)
    parser.add_argument("--topology-view", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            build_player(
                args.manifest,
                args.output,
                gif_provenance=args.gif_provenance,
                topology_view=args.topology_view,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
