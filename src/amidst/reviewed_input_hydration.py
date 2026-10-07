"""Restore hash-bound historical review inputs without replacing any existing file.

This is an explicit local copy boundary, not a dataset producer. New formal outputs
are never used to satisfy old review hashes. Verify the complete copy plan before
writing, including the durable package manifest pinned by the handoff checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _inside(root: Path, relative: str) -> Path:
    name = Path(relative)
    if name.is_absolute() or ".." in name.parts or ".git" in name.parts:
        raise ValueError("historical input must be a safe repository-relative path")
    result = root / name
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError("historical input escapes its root")
    return result


def hydrate_historical_inputs(
    root: Path, *, historical_root: Path, durable_review: Path
) -> dict[str, Any]:
    """Copy only missing exact historical bytes; a mismatch writes nothing."""
    checkpoint = json.loads((root / "docs/PHASE1_POST_APPROVAL_CHECKPOINT.json").read_bytes())
    manifest_path = durable_review / "manifest.json"
    expected_manifest = checkpoint["durable_review"]["manifest_sha256"]
    if file_sha256(manifest_path) != expected_manifest:
        raise ValueError("durable historical review manifest SHA mismatch")
    manifest = json.loads(manifest_path.read_bytes())
    if (
        manifest["source_sha256"] != checkpoint["source"]["sha256"]
        or manifest["review_payload_sha256"] != checkpoint["review_payload_sha256"]
    ):
        raise ValueError("historical review source/payload binding differs")
    records: dict[str, tuple[Path, str]] = {}
    for item in manifest["artifacts"]:
        source = _inside(durable_review, item["path"])
        records["human_review/" + item["path"]] = (source, item["sha256"])
    records["human_review/manifest.json"] = (manifest_path, expected_manifest)
    for item in checkpoint["review_bound_inputs"]:
        relative = item["path"]
        forbidden = {"evaluation", "simulation", "ground_truth"}
        if any(part in forbidden for part in Path(relative).parts):
            raise ValueError("review hydration cannot read GT/evaluation/simulation")
        if relative in records:
            raise ValueError("duplicate historical review input")
        records[relative] = (_inside(historical_root, relative), item["sha256"])

    missing: list[tuple[Path, Path, str]] = []
    for relative, (source, expected) in sorted(records.items()):
        target = _inside(root, relative)
        if not source.is_file() or file_sha256(source) != expected:
            raise ValueError("historical input source SHA mismatch: " + relative)
        if target.exists():
            if not target.is_file() or file_sha256(target) != expected:
                raise ValueError(
                    "existing historical input differs; refusing overwrite: " + relative
                )
        else:
            missing.append((source, target, expected))

    # Exclusive creation preserves an intervening writer; never overwrite authority.
    for source, target, expected in missing:
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as reader, target.open("xb") as writer:
            shutil.copyfileobj(reader, writer)
        if file_sha256(target) != expected:
            raise ValueError("historical input changed while copying: " + str(target))
    return {
        "schema_version": "phase1-historical-review-hydration-v1",
        "status": "PASS",
        "review_manifest_sha256": expected_manifest,
        "review_bound_input_count": len(checkpoint["review_bound_inputs"]),
        "verified_file_count": len(records),
        "copied_file_count": len(missing),
        "existing_matching_file_count": len(records) - len(missing),
        "historical_inputs_replaced": False,
        "formal_outputs_used": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--historical-root", type=Path, required=True)
    parser.add_argument("--durable-review", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(hydrate_historical_inputs(
        args.root, historical_root=args.historical_root, durable_review=args.durable_review
    ), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
