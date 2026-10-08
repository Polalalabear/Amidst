"""Assemble a view-only player from frozen display evidence; never run research."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from human_review.build_playback_status import build_status

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    "motion": (
        "human_review/frames/motion_context/motion_manifest.json",
        "e77628c145fceb42ae086a76f4de60741147ea525eb12d46e7f23d7ba83d7b69",
    ),
    "topology": (
        "human_review/frames/topology_context/topology_data.json",
        "c8a1a46b74837651e280660f1c380c1eae869b1d028630b5a85ff4808723c952",
    ),
    "audit": (
        "human_review/frames/hr02_camera_audit/audit_data.json",
        "5bda3a45843649ec2a3074bda87694847534a7401dd51e084a48b9cfac332035",
    ),
    "renderer": (
        "human_review/frames/hr02_camera_audit/renderer_manifest.json",
        "70998fdb1fe6a0fbfaafb7d7c1a8817e79a74913e8ea9658f4f8f69fdb8e2260",
    ),
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _documents(root: Path) -> dict[str, Any]:
    documents = {}
    for name, (relative, expected) in SOURCE_FILES.items():
        raw = (root / relative).read_bytes()
        if _sha(raw) != expected:
            raise ValueError(f"Frozen preview source changed: {relative}")
        documents[name] = json.loads(raw)
    scene_hashes = {doc["source_sha256"] for doc in documents.values()}
    if len(scene_hashes) != 1:
        raise ValueError("Preview source scene hashes disagree")
    for name, doc in documents.items():
        for key in ("gt_used", "evaluation_files_read", "simulation_recipe_read",
                    "physical_authority_changed", "formal_execution_enabled"):
            if doc[key] is not False:
                raise ValueError(f"Preview evidence boundary changed: {name}.{key}")
    motion = documents["motion"]
    if len(motion["frames"]) != 50 or motion["fps"] != 5:
        raise ValueError("Expected frozen 50-frame, 5 Hz display sequence")
    for name in ("topology", "audit"):
        frames = documents[name]["frames"]
        if len(frames) != len(motion["frames"]):
            raise ValueError(f"Frame count mismatch: {name}")
        for index, (frame, original) in enumerate(zip(frames, motion["frames"], strict=True)):
            if frame["frame_id"] != original["frame_id"] or frame["frame_id"] != index:
                raise ValueError(f"Frame identity mismatch: {name}, {index}")
            if frame["timestamp"] != original["timestamp"]:
                raise ValueError(f"Frame time mismatch: {name}, {index}")
            if name == "topology" and frame["sha256"] != original["sha256"]:
                raise ValueError(f"Motion hash mismatch: {index}")
    return documents


def _assets(documents: dict[str, Any]) -> list[dict[str, Any]]:
    assets = []
    renderer = documents["renderer"]
    for directory, rows in (
        ("motion_context", documents["motion"]["frames"]),
        ("hr02_camera_audit", [renderer["wide"], renderer["side"],
                               *renderer["camera_stills"]]),
    ):
        for row in rows:
            path = Path(row["path"])
            if path.name != row["path"] or path.suffix != ".png":
                raise ValueError(f"Unsafe preview asset path: {path}")
            assets.append({"path": f"frames/{directory}/{path.name}",
                           "sha256": row["sha256"], "bytes": row["bytes"]})
    return assets


def _verify_asset(path: Path, row: dict[str, Any]) -> bytes:
    raw = path.read_bytes()
    if len(raw) != row["bytes"] or _sha(raw) != row["sha256"]:
        raise ValueError(f"Preview image does not match frozen evidence: {path}")
    return raw


def build_payload(root: Path, verify_assets: bool = True) -> dict[str, Any]:
    """Return aligned display data, with no camera rebinding or new interpolation."""
    documents = _documents(root)
    if verify_assets:
        for row in _assets(documents):
            _verify_asset(root / "human_review" / row["path"], row)
    audit = copy.deepcopy(documents["audit"])
    renderer = documents["renderer"]
    audit["images"] = copy.deepcopy({key: renderer[key]
                                      for key in ("wide", "side", "camera_stills")})
    # Fit points are renderer setup data; the fixed transform already encodes them.
    for kind in ("wide", "side"):
        audit["images"][kind]["view"].pop("fit_points_bu", None)
    return {
        "schema_version": "phase1-view-only-playback-v1",
        "status": build_status(root),
        "motion": documents["motion"],
        "topology": documents["topology"],
        "audit": audit,
        "basePaths": {"motion": "../frames/motion_context/",
                      "camera": "../frames/hr02_camera_audit/"},
    }


def build_workspace(root: Path, media_root: Path | None = None) -> dict[str, Any]:
    """Verify or copy existing local images, then write only new viewer outputs."""
    documents = _documents(root)
    assets = _assets(documents)
    review = root / "human_review"
    # Validate the complete input set before writing any file. Existing mismatched
    # files always fail closed; a media root never authorizes overwriting evidence.
    pending = []
    for row in assets:
        target = review / row["path"]
        if target.exists():
            _verify_asset(target, row)
        elif media_root is not None:
            pending.append((target, _verify_asset(media_root / row["path"], row)))
        else:
            raise FileNotFoundError(f"Missing {target}; supply --media-root with existing images")
    payload = build_payload(root, verify_assets=False)
    for target, raw in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    output = review / "playback"
    output.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    script = f"window.PHASE1_PREVIEW_DATA = {serialized};\n".encode()
    (output / "data.js").write_bytes(script)
    sources = [{"path": path, "sha256": sha} for path, sha in SOURCE_FILES.values()]
    manifest = {
        "schema_version": "phase1-playback-build-v1",
        "mode": "VIEW_ONLY",
        "research_rerun": False,
        "source_sha256": documents["motion"]["source_sha256"],
        "checkpoint_sha": payload["status"]["checkpoint_sha"],
        "frame_count": len(documents["motion"]["frames"]),
        "fps": documents["motion"]["fps"],
        "source_files": sources + payload["status"]["sources"],
        "media_files": assets,
        "media_count": len(assets),
        "data_sha256": _sha(script),
    }
    (output / "build_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-root", type=Path,
                        help="Existing human_review folder containing the original PNGs")
    args = parser.parse_args()
    result = build_workspace(ROOT, args.media_root)
    print(json.dumps({"mode": result["mode"], "frames": result["frame_count"],
                      "verified_images": result["media_count"],
                      "data_sha256": result["data_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
