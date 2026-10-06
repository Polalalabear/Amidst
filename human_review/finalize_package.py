"""Record the minimal pending review and package hashes; preserve all decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from assemble_review import write_json

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--durable-copy", type=Path)
    args = parser.parse_args()
    document = json.loads((HERE / "decisions.json").read_text())
    if any(item["decision"] is not None for item in document["items"]):
        raise ValueError("package finalization cannot rewrite completed human decisions")
    spatial_path = HERE / "frames/spatial_context/spatial_context_manifest.json"
    spatial_summary = {}
    if spatial_path.is_file():
        spatial = json.loads(spatial_path.read_text())
        spatial_summary = {
            "manifest": str(spatial_path.relative_to(HERE)),
            "manifest_sha256": hashlib.sha256(spatial_path.read_bytes()).hexdigest(),
            "result_type": spatial["result_type"],
            "camera_approach_frames": len(spatial["approach_frames"]),
            "camera_approach_fps": spatial["approach_fps"],
            "static_frames": 3,
            "person_movement_changed": spatial["person_movement_changed"],
            "guide": "frames/spatial_context/guide.html",
        }
    write_json(
        HERE / "gate.json",
        {
            "schema_version": "phase1-minimal-human-review-gate-v1",
            "status": "HUMAN_REVIEW_PENDING",
            "checkpoint_sha": document["metadata"]["checkpoint_sha"],
            "source_sha256": document["metadata"]["source_sha256"],
            "review_payload_sha256": document["review_payload_sha256"],
            "human_decision_count": 4,
            "geometry_decisions": ["HR-01"],
            "projection_binding_decisions": ["HR-02"],
            "formal_setting_decisions": ["HR-03", "HR-04"],
            "case_blocker_map": document["metadata"]["case_blocker_map"],
            "formal_execution_enabled": False,
            "human_decisions_applied": False,
            "source_geometry_modified": False,
        },
    )
    artifacts = []
    for path in sorted(HERE.rglob("*")):
        if (
            not path.is_file()
            or "__pycache__" in path.parts
            or path == HERE / "manifest.json"
            or path.name == ".DS_Store"
        ):
            continue
        artifacts.append(
            {
                "path": str(path.relative_to(HERE)),
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    write_json(
        HERE / "manifest.json",
        {
            "schema_version": "phase1-minimal-human-review-package-v1",
            "checkpoint_sha": document["metadata"]["checkpoint_sha"],
            "source_sha256": document["metadata"]["source_sha256"],
            "review_payload_sha256": document["review_payload_sha256"],
            "status": "HUMAN_REVIEW_PENDING",
            "human_decision_count": 4,
            "frames": {
                "duration_seconds": 10,
                "sampling_hz": 5,
                "sequence_frames": 50,
                "static_frames": 7,
                "raw_render_storage": "LOCAL_IGNORED",
            },
            "gt_used_for_review": False,
            "formal_cases_run": False,
            "spatial_context_supplement": spatial_summary,
            "artifacts": artifacts,
        },
    )
    if args.durable_copy:
        destination = args.durable_copy.resolve()
        if destination.exists():
            raise ValueError("durable review copy must be fresh to preserve human edits")
        shutil.copytree(
            HERE, destination, ignore=shutil.ignore_patterns("__pycache__", ".DS_Store")
        )
    print(
        json.dumps(
            {
                "human_decisions": 4,
                "package": str(HERE),
                "durable_copy": str(args.durable_copy) if args.durable_copy else None,
                "artifact_count": len(artifacts),
                "raw_bytes": sum(row["bytes"] for row in artifacts),
            }
        )
    )


if __name__ == "__main__":
    main()
