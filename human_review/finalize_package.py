"""Record validated human decisions and package hashes without applying authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from apply_decisions import validate_decisions
from assemble_review import write_json
from build_dashboard import hr02_camera_view_hash

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--durable-copy", type=Path)
    args = parser.parse_args()
    document = json.loads((HERE / "decisions.json").read_text())
    template = json.loads((HERE / "review_template.json").read_text())
    state = validate_decisions(document, template)
    unresolved = set(state["pending"]) | {row["id"] for row in state["blocking"]}
    state_summary = {
        "status": state["status"],
        "human_decision_count": len(document["items"]),
        "pending": state["pending"],
        "blocking": state["blocking"],
        "unresolved_human_decision_count": len(unresolved),
        "human_decisions_recorded": any(item["decision"] is not None for item in document["items"]),
        "human_decisions_applied": False,
        "formal_execution_enabled": False,
        "physical_certificate_status": "NOT_RUN",
        "case_pending_human_blocker_ids": {
            number: [item_id for item_id in row["blocker_ids"] if item_id in unresolved]
            for number, row in document["metadata"]["case_blocker_map"].items()
        },
    }
    approval_path = HERE / "approval_record.json"
    if approval_path.is_file():
        state_summary["approval_record"] = {
            "path": approval_path.name,
            "sha256": hashlib.sha256(approval_path.read_bytes()).hexdigest(),
        }
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
    motion_path = HERE / "frames/motion_context/motion_manifest.json"
    motion_summary = {}
    if motion_path.is_file():
        motion = json.loads(motion_path.read_text())
        motion_summary = {
            "manifest": str(motion_path.relative_to(HERE)),
            "manifest_sha256": hashlib.sha256(motion_path.read_bytes()).hexdigest(),
            "result_type": motion["result_type"],
            "frames": len(motion["frames"]),
            "sampling_hz": motion["sampling_hz"],
            "duration_seconds": motion["duration_seconds"],
            "player": "frames/motion_context/player.html",
        }
    topology_path = HERE / "frames/topology_context/topology_manifest.json"
    topology_summary = {}
    if topology_path.is_file():
        topology = json.loads(topology_path.read_text())
        topology_summary = {
            "manifest": str(topology_path.relative_to(HERE)),
            "manifest_sha256": hashlib.sha256(topology_path.read_bytes()).hexdigest(),
            "result_type": topology["result_type"],
            "nodes": topology["node_count"],
            "edges": topology["edge_count"],
            "polyline_vertices": topology["interior_vertex_count"],
            "view": "frames/topology_context/view.html",
            "static_preview": "frames/topology_context/topology_preview.png",
            "raw_graph_changed": topology["raw_graph_changed"],
        }
        if "person_marker_policy" in topology:
            topology_summary["person_marker_policy"] = topology["person_marker_policy"]
            topology_summary["person_locator_frames"] = 50
    clarity_path = HERE / "frames/review_clarity/manifest.json"
    clarity_summary = {}
    if clarity_path.is_file():
        clarity_summary = {
            "manifest": str(clarity_path.relative_to(HERE)),
            "manifest_sha256": hashlib.sha256(clarity_path.read_bytes()).hexdigest(),
            "result_type": "DIAGNOSTIC",
            "guide": "frames/spatial_context/guide.html",
            "scope": "COMPLETE_TEST_SPACE_CAMERA_LOCATION_AND_PENDING_HR02_BODY_HEIGHT",
            "original_media_preserved": True,
            "human_decisions_applied": False,
        }
    hr02_summary = {}
    hr02_hash = hr02_camera_view_hash(document)
    if hr02_hash:
        audit_path = HERE / "frames/hr02_camera_audit/audit_data.json"
        audit = json.loads(audit_path.read_text())
        hr02_summary = {
            "view": "frames/hr02_camera_audit/view.html",
            "view_sha256": hr02_hash,
            "audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
            "result_type": "DIAGNOSTIC_NOT_CERTIFIED",
            "source_ray_queries": 200,
            "public_record_counts": audit["summary"]["recorded_counts"],
            "landmark_replay_counts": audit["summary"]["replay_counts"],
            "foot_replay_counts": audit["summary"]["foot_replay_counts"],
            "landmark_clear_foot_occluded_count": len(
                audit["summary"]["landmark_clear_foot_occluded"]
            ),
            "room_ownership": "NOT_CERTIFIED",
            "human_decisions_applied": False,
            "formal_execution_enabled": False,
            "original_media_preserved": True,
        }
    write_json(
        HERE / "gate.json",
        {
            "schema_version": "phase1-minimal-human-review-gate-v1",
            **state_summary,
            "checkpoint_sha": document["metadata"]["checkpoint_sha"],
            "source_sha256": document["metadata"]["source_sha256"],
            "review_payload_sha256": document["review_payload_sha256"],
            "geometry_decisions": ["HR-01"],
            "projection_binding_decisions": ["HR-02"],
            "formal_setting_decisions": ["HR-03", "HR-04"],
            "case_blocker_map": document["metadata"]["case_blocker_map"],
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
            **state_summary,
            "case_blocker_map": document["metadata"]["case_blocker_map"],
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
            "body_motion_supplement": motion_summary,
            "topology_supplement": topology_summary,
            "review_clarity_supplement": clarity_summary,
            "hr02_camera_audit_supplement": hr02_summary,
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
                "human_decisions": len(document["items"]),
                "status": state["status"],
                "unresolved_human_decisions": len(unresolved),
                "package": str(HERE),
                "durable_copy": str(args.durable_copy) if args.durable_copy else None,
                "artifact_count": len(artifacts),
                "raw_bytes": sum(row["bytes"] for row in artifacts),
            }
        )
    )


if __name__ == "__main__":
    main()
