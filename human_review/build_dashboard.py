"""Build the offline Phase 1 human-review dashboard from pending decisions.

No decisions are approved or applied by this builder. It only embeds the review
payload and preserves current decisions in a local, dependency-free HTML page.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHOICES = {"APPROVE", "REJECT", "FIX_GEOMETRY", "KEEP_REVIEW"}


def review_identity(document: dict[str, Any]) -> dict[str, Any]:
    identity = copy.deepcopy(document)
    identity.pop("review_payload_sha256", None)
    metadata = identity["metadata"]
    metadata.pop("reviewer", None)
    metadata.pop("submitted_at", None)
    for item in identity["items"]:
        item.pop("decision", None)
        item.pop("selected_option", None)
    return identity


def payload_hash(document: dict[str, Any]) -> str:
    encoded = json.dumps(
        review_identity(document), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def clarity_display_data(path: Path, output: Path) -> dict[str, Any]:
    """Load a separately validated display supplement without modifying decisions."""
    spec = importlib.util.spec_from_file_location(
        "phase1_spatial_review_clarity", ROOT / "human_review/build_spatial_guide.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("review clarity validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.read_clarity_manifest(path, output)
    return {
        key: data[key]
        for key in (
            "schema_version",
            "result_type",
            "source_sha256",
            "gt_used",
            "physical_authority_changed",
            "formal_execution_enabled",
            "floor",
            "office",
            "hr02",
            "manifest_sha256",
            "shape_legend",
        )
    }


def topology_view_hash(document: dict[str, Any]) -> str:
    """Version the local topology frame without adding anything to decisions."""
    directory = ROOT / "human_review/frames/topology_context"
    manifest_path = directory / "topology_manifest.json"
    if not manifest_path.is_file():
        return ""
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["source_sha256"] != document["metadata"]["source_sha256"]
        or manifest["review_payload_sha256"] != document["review_payload_sha256"]
        or manifest["result_type"] != "DIAGNOSTIC"
        or (manifest["node_count"], manifest["edge_count"], manifest["interior_vertex_count"])
        != (2, 3, 4)
        or any(
            manifest[key] is not False
            for key in (
                "gt_used",
                "evaluation_files_read",
                "simulation_recipe_read",
                "physical_authority_changed",
                "formal_execution_enabled",
                "raw_graph_changed",
            )
        )
    ):
        raise ValueError("topology display must retain its source, graph and pending review")
    for key, name in (("view", "view.html"), ("data", "topology_data.json")):
        if manifest[key]["path"] != name:
            raise ValueError("topology display accepts only its canonical local files")
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        if actual != manifest[key]["sha256"]:
            raise ValueError("topology display differs from its hash-bound manifest")
    data = json.loads((directory / "topology_data.json").read_text())
    navigation_hash = hashlib.sha256(
        json.dumps(data["raw_navigation"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if navigation_hash != "9bbedd163e9a195943cfe82f3473a97ac3bc0ff3be31e83d5866cccfba4278fd":
        raise ValueError("topology display must preserve the original configured graph")
    return str(manifest["view"]["sha256"])


def hr02_camera_view_hash(document: dict[str, Any]) -> str:
    """Add hash-versioned diagnostic evidence without changing review choices."""
    directory = ROOT / "human_review/frames/hr02_camera_audit"
    receipt = directory / "view_manifest.json"
    if not receipt.is_file():
        return ""
    manifest = json.loads(receipt.read_text())
    if (
        manifest["source_sha256"] != document["metadata"]["source_sha256"]
        or manifest["review_payload_sha256"] != document["review_payload_sha256"]
        or manifest["result_type"] != "DIAGNOSTIC"
        or (manifest["frame_count"], manifest["fps"]) != (50, 5)
        or manifest["camera_still_frames"] != [20, 25, 45]
        or manifest["separate_public_record_and_projected_replay"] is not True
        or manifest["camera_stills_are_representative_not_current_playback"] is not True
        or any(
            manifest[key] is not False
            for key in (
                "gt_used",
                "evaluation_files_read",
                "simulation_recipe_read",
                "physical_authority_changed",
                "formal_execution_enabled",
                "decisions_changed",
                "projection_changed",
                "raw_graph_changed",
                "original_source_point_available",
            )
        )
    ):
        raise ValueError("HR02 camera evidence must remain diagnostic and pending")
    for key, filename in (
        ("view", "view.html"),
        ("data", "audit_data.json"),
        ("producer", "manifest.json"),
        ("renderer", "renderer_manifest.json"),
    ):
        path = directory / filename
        if (
            manifest[key]["path"] != filename
            or path.resolve().parent != directory.resolve()
            or hashlib.sha256(path.read_bytes()).hexdigest() != manifest[key]["sha256"]
        ):
            raise ValueError("HR02 camera evidence differs from its canonical hash receipt")
    return str(manifest["view"]["sha256"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=ROOT / "human_review/decisions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "human_review/index.html")
    parser.add_argument("--clarity-manifest", type=Path)
    args = parser.parse_args()
    document = json.loads(args.decisions.read_text())
    ids = [item["id"] for item in document["items"]]
    if len(ids) != len(set(ids)):
        raise ValueError("review IDs must be unique")
    for item in document["items"]:
        if item.get("decision") is not None and item["decision"] not in CHOICES:
            raise ValueError("unsupported human choice: " + item["id"])
        if item.get("selected_option") is not None and item["selected_option"] not in {
            option["id"] for option in item.get("approve_options", [])
        }:
            raise ValueError("unsupported approval profile: " + item["id"])
    expected_hash = payload_hash(document)
    if document.get("review_payload_sha256", expected_hash) != expected_hash:
        raise ValueError("review payload hash does not match immutable document")
    document["review_payload_sha256"] = expected_hash
    encoded = json.dumps(document, ensure_ascii=False, allow_nan=False)
    encoded = encoded.replace("</", "<\\/").replace("\u2028", "\\u2028")
    encoded = encoded.replace("\u2029", "\\u2029")
    template = (ROOT / "human_review/dashboard_template.html").read_text()
    clarity = (
        clarity_display_data(args.clarity_manifest, args.output) if args.clarity_manifest else {}
    )
    encoded_clarity = json.dumps(clarity, ensure_ascii=False, allow_nan=False)
    encoded_clarity = encoded_clarity.replace("</", "<\\/").replace("\u2028", "\\u2028")
    encoded_clarity = encoded_clarity.replace("\u2029", "\\u2029")
    args.output.write_text(
        template.replace("__DECISIONS_JSON__", encoded)
        .replace("__REVIEW_PAYLOAD_HASH__", payload_hash(document))
        .replace("__REVIEW_CLARITY_DATA__", encoded_clarity)
        .replace("__REVIEW_TOPOLOGY_VIEW_HASH__", topology_view_hash(document))
        .replace("__HR02_CAMERA_VIEW_HASH__", hr02_camera_view_hash(document))
    )
    print(
        json.dumps(
            {
                "dashboard": str(args.output),
                "items": len(ids),
                "review_hash": payload_hash(document),
            }
        )
    )


if __name__ == "__main__":
    main()
