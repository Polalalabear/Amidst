"""Build a display-only, offline school→floor→office review guide.

The guide reuses public projection/inference evidence. It never opens the source
Blender asset, changes review decisions, or creates an inferred route.
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
SPATIAL = HERE / "frames/spatial_context"
SCALE = 0.0247
SOURCE_SHA256 = "cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_asset(base: Path, value: str) -> Path:
    if not isinstance(value, str):
        raise ValueError("spatial image path must be a local PNG string")
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or ".." in path.parts
        or ":" in value
        or "\\" in value
        or any(character in value for character in "%?#")
        or path.suffix.lower() != ".png"
    ):
        raise ValueError("spatial image path must stay inside its local PNG directory")
    resolved = (base / path).resolve()
    if base.resolve() not in resolved.parents:
        raise ValueError("spatial image path escapes the manifest directory")
    return resolved


def validate_manifest(manifest: dict[str, Any], base: Path) -> dict[str, Any]:
    """Validate diagnostic lineage and all image paths before reading any images."""
    if manifest.get("schema_version") != "phase1-human-review-spatial-context-v1":
        raise ValueError("unsupported spatial-context manifest")
    if manifest.get("result_type") != "DIAGNOSTIC":
        raise ValueError("spatial views must remain DIAGNOSTIC")
    for key in (
        "gt_used",
        "evaluation_files_read",
        "simulation_recipe_read",
        "source_saved",
        "physical_authority_changed",
    ):
        if manifest.get(key) is not False:
            raise ValueError("spatial guide violates the read-only evidence contract: " + key)
    if manifest.get("source_preserved") is not True:
        raise ValueError("spatial guide requires preservation of the original source")
    if manifest.get("display_only_camera_approach") is not True:
        raise ValueError("camera approach must be explicitly display-only")
    if manifest.get("source_sha256") != SOURCE_SHA256:
        raise ValueError("spatial source hash differs from the approved school_v3 asset")
    records = [manifest[key] for key in ("overview", "floor", "office")]
    approach = manifest.get("approach_frames", [])
    if not approach or manifest.get("approach_fps") != 5:
        raise ValueError("the spatial guide requires the declared 5 fps camera approach")
    records.extend(approach)
    paths = [(safe_asset(base, row["path"]), row["sha256"]) for row in records]
    for path, expected in paths:
        if digest(path) != expected:
            raise ValueError("spatial image hash mismatch: " + path.name)
    return manifest


def movement_span(visuals: dict[str, Any]) -> dict[str, Any]:
    """Compute the endpoint displacement of the existing public/inferred preview."""
    if visuals.get("gt_used") is not False:
        raise ValueError("preview movement cannot be derived from Ground Truth")
    first, last = visuals["frames"][0], visuals["frames"][-1]
    start, end = first["body_base_bu"], last["body_base_bu"]
    if len(start) != 3 or len(end) != 3 or not all(math.isfinite(v) for v in start + end):
        raise ValueError("public preview endpoints must be finite 3D coordinates")
    distance = math.dist(start, end)
    return {
        "start_timestamp_seconds": first["timestamp"],
        "end_timestamp_seconds": last["timestamp"],
        "start_footpoint_bu": start,
        "end_footpoint_bu": end,
        "distance_bu": distance,
        "distance_m": distance * SCALE,
        "status": "PUBLIC_PROJECTION_AND_EXISTING_INFERRED_GAP_DIAGNOSTIC",
    }


def semantic_binding(visuals: dict[str, Any]) -> dict[str, Any]:
    """Keep the vertical coordinate conversion distinct from person displacement."""
    if visuals.get("gt_used") is not False:
        raise ValueError("landmark semantics cannot be derived from Ground Truth")
    landmark = visuals["landmark_z_bu"]
    floor = visuals["approved_support_z_bu"]
    offset = landmark - floor
    if not math.isclose(
        offset, visuals["proposed_exact_landmark_offset_bu"], abs_tol=1e-9, rel_tol=1e-12
    ):
        raise ValueError("source-bound landmark conversion differs from recorded evidence")
    body = visuals["approved_body_dimensions_m"]
    return {
        "landmark_z_bu": landmark,
        "floor_z_bu": floor,
        "offset_bu": offset,
        "offset_m": offset * SCALE,
        "body_radius_m": body["radius"],
        "body_height_m": body["height"],
        "clearance_m": body["clearance"],
        "authority": "PENDING_HR02_SEMANTIC_BINDING",
    }


def relative_path(path: Path, output: Path) -> str:
    return Path(os.path.relpath(path, output.parent)).as_posix()


def build_guide(manifest_path: Path, output_path: Path) -> dict[str, Any]:
    """Render the offline guide while leaving all existing review evidence untouched."""
    manifest = validate_manifest(json.loads(manifest_path.read_text()), manifest_path.parent)
    original_paths = [
        HERE / "decisions.json",
        HERE / "review_template.json",
        HERE / "frames/visual_manifest.json",
        HERE / "frames/player.html",
        *sorted((HERE / "frames").glob("*.png")),
    ]
    protected = {path: digest(path) for path in original_paths}
    visuals = json.loads((HERE / "frames/visual_manifest.json").read_text())
    if visuals.get("source_asset_sha256") != manifest["source_sha256"]:
        raise ValueError("existing route preview has a different source lineage")
    original_images = visuals["frames"] + visuals["still_frames"] + visuals["camera_stills"]
    original_images += visuals.get("closeup_frames", [])
    for row in original_images:
        if digest(HERE / row["path"]) != row["sha256"]:
            raise ValueError("an existing preview image differs from its frozen manifest")
    decisions = json.loads((HERE / "decisions.json").read_text())
    data = {
        "schema_version": "phase1-human-review-spatial-guide-v1",
        "result_type": "DIAGNOSTIC",
        "gt_used": False,
        "source_asset_sha256": manifest["source_sha256"],
        "source_opened_by_guide_builder": False,
        "review_payload_sha256": decisions["review_payload_sha256"],
        "protected_original_files_sha256": {
            relative_path(path, output_path): value for path, value in protected.items()
        },
        "context_manifest_sha256": digest(manifest_path),
        "overview": {
            **manifest["overview"],
            "path": relative_path(manifest_path.parent / manifest["overview"]["path"], output_path),
        },
        "floor": {
            **manifest["floor"],
            "path": relative_path(manifest_path.parent / manifest["floor"]["path"], output_path),
        },
        "office": {
            **manifest["office"],
            "path": relative_path(manifest_path.parent / manifest["office"]["path"], output_path),
        },
        "approach_frames": [
            {
                **row,
                "path": relative_path(manifest_path.parent / row["path"], output_path),
            }
            for row in manifest["approach_frames"]
        ],
        "approach_fps": manifest["approach_fps"],
        "camera_approach_duration_seconds": len(manifest["approach_frames"])
        / manifest["approach_fps"],
        "display_roi_bu": manifest["display_roi_bu"],
        "office_context": manifest["office_context"],
        "review_body_scope_bounds_bu": manifest["review_body_scope_bounds_bu"],
        "camera_locations": manifest["camera_locations"],
        "position_map": {
            "classification": "DIAGNOSTIC",
            "display_only": True,
            "authority": "DISPLAY_POSITION_CONTEXT_NOT_FOV_OR_BINDING_APPROVAL",
            "axes": "BLENDER_NATIVE_XY_NOT_GEOGRAPHIC_NORTH",
            "gt_used": False,
        },
        "movement": movement_span(visuals),
        "binding": semantic_binding(visuals),
        "existing_route_player": relative_path(HERE / "frames/player.html", output_path),
        "issue_closeup": relative_path(HERE / "frames/office_scope_closeup.png", output_path),
        "issue_top_closeup": relative_path(
            HERE / "frames/office_scope_top_closeup.png", output_path
        ),
        "source_sha256_unchanged": True,
    }
    template_path = SPATIAL / "guide_template.html"
    encoded = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    encoded = encoded.replace("</", "<\\/").replace("\u2028", "\\u2028")
    encoded = encoded.replace("\u2029", "\\u2029")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(template_path.read_text().replace("__SPATIAL_GUIDE_DATA__", encoded))
    if any(digest(path) != value for path, value in protected.items()):
        raise RuntimeError("guide generation altered existing review evidence")
    return {
        "guide": str(output_path),
        "guide_sha256": digest(output_path),
        "review_payload_sha256": data["review_payload_sha256"],
        "protected_original_file_count": len(protected),
        "gt_used": False,
        "result_type": "DIAGNOSTIC",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=SPATIAL / "spatial_context_manifest.json")
    parser.add_argument("--output", type=Path, default=SPATIAL / "guide.html")
    args = parser.parse_args()
    print(json.dumps(build_guide(args.manifest, args.output), ensure_ascii=False))


if __name__ == "__main__":
    main()
