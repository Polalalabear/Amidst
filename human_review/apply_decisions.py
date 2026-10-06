"""Validate explicit review decisions, regenerate bounded authority and lock inputs.

Default is read-only validation. --apply is fail-closed: pending/rejected decisions
produce no files, original configs/assets stay unchanged, and formal execution is
never enabled merely by a human APPROVE receipt.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from assemble_review import content_hash, immutable_document, write_json

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / "human_review"
CHOICES = {"APPROVE", "REJECT", "FIX_GEOMETRY", "KEEP_REVIEW"}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_input_path(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("review input must be a repository-relative path")
    if any(part.lower() in {"evaluation", "ground_truth", "simulation"} for part in relative.parts):
        raise ValueError("decision application cannot read GT/evaluation/simulation")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("review input escapes repository")
    return path


def validate_decisions(document: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    """Only identity, signed-off time, four choices and defined option IDs are editable."""
    if immutable_document(document) != immutable_document(template):
        raise ValueError("immutable source/checkpoint/questions/profiles were changed")
    expected_hash = content_hash(immutable_document(template))
    if content_hash(immutable_document(document)) != expected_hash:
        raise ValueError("immutable submitted question payload hash mismatch")
    if template.get("review_payload_sha256") != expected_hash:
        raise ValueError("review template payload hash mismatch")
    if document.get("review_payload_sha256") != expected_hash:
        raise ValueError("submitted review payload hash mismatch")
    pending, blocking = [], []
    for item, base in zip(document["items"], template["items"], strict=True):
        if set(item) != set(base):
            raise ValueError("decision fields must match review template")
        choice, option = item["decision"], item["selected_option"]
        if choice is None:
            if option is not None:
                raise ValueError("unselected decision cannot carry an approval profile")
            pending.append(item["id"])
        elif choice not in CHOICES:
            raise ValueError("unsupported human choice")
        elif choice == "APPROVE":
            if option not in {profile["id"] for profile in item["approve_options"]}:
                raise ValueError("APPROVE requires a defined explicit profile")
        else:
            if option is not None:
                raise ValueError("non-approval cannot carry an approval profile")
            blocking.append({"id": item["id"], "decision": choice})
    reviewer = document["metadata"]["reviewer"]
    submitted = document["metadata"]["submitted_at"]
    if not isinstance(reviewer, str):
        raise ValueError("reviewer must be a string")
    if submitted is not None:
        if not isinstance(submitted, str):
            raise ValueError("submitted_at must be an ISO timestamp")
        instant = datetime.fromisoformat(submitted.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError("submitted_at requires an explicit timezone")
    if pending:
        status = "HUMAN_REVIEW_PENDING"
    elif not reviewer.strip() or submitted is None:
        raise ValueError("completed human decisions require reviewer and submitted_at")
    elif blocking:
        status = "HUMAN_REVIEW_BLOCKED"
    else:
        status = "EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION"
    return {
        "status": status,
        "pending": pending,
        "blocking": blocking,
        "formal_execution_enabled": False,
    }


def verify_inputs(root: Path, template: dict[str, Any], source_asset: Path) -> None:
    metadata = template["metadata"]
    if file_hash(source_asset) != metadata["source_sha256"]:
        raise ValueError("source school asset SHA mismatch")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", metadata["checkpoint_sha"], "HEAD"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("checkout does not descend from the reviewed checkpoint")
    for row in metadata["input_hashes"]:
        if file_hash(safe_input_path(root, row["path"])) != row["sha256"]:
            raise ValueError("review input hash mismatch: " + row["path"])
    visual = json.loads((root / "human_review/frames/visual_manifest.json").read_text())
    for row in (
        visual["still_frames"]
        + visual["camera_stills"]
        + visual["frames"]
        + visual.get("closeup_frames", [])
    ):
        if file_hash(safe_input_path(root, "human_review/" + row["path"])) != row["sha256"]:
            raise ValueError("review frame hash mismatch: " + row["path"])


def chosen_payload(item: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(
        next(
            option["payload"]
            for option in item["approve_options"]
            if option["id"] == item["selected_option"]
        )
    )


def approved_input_lock(document: dict[str, Any], certificate_status: str) -> dict[str, Any]:
    by_id = {item["id"]: item for item in document["items"]}
    return {
        "schema_version": "phase1-reviewed-input-lock-v1",
        "status": "HUMAN_APPROVED_INPUTS_AUTOMATIC_CASE_READINESS_PENDING",
        "protocol_base": "configs/benchmarks/protocol_v1.json",
        "protocol_extension": "phase1-human-approved-local-office-v1",
        "source_sha256": document["metadata"]["source_sha256"],
        "review_payload_sha256": document["review_payload_sha256"],
        "human_decisions_sha256": content_hash(document),
        "automatic_settings": document["metadata"]["automatic_settings"],
        "geometry_semantics": chosen_payload(by_id["HR-01"]),
        "projection_binding": chosen_payload(by_id["HR-02"]),
        "coverage": chosen_payload(by_id["HR-03"]),
        "timing": chosen_payload(by_id["HR-04"]),
        "physical_certificate_status": certificate_status,
        "physical_authority": "BOUNDED_OFFICE_ONLY_IF_CERTIFICATE_PASS",
        "legacy_diagnostic_artifacts_promoted": False,
        "formal_execution_enabled": False,
        "further_required_automatic_proofs": document["metadata"]["case_blocker_map"],
    }


def apply_completed(
    document: dict[str, Any],
    template: dict[str, Any],
    *,
    root: Path,
    output: Path,
) -> dict[str, Any]:
    """Persist a receipt only after explicit decisions; no formal run or source mutation."""
    state = validate_decisions(document, template)
    if state["status"] != "EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION":
        raise ValueError("no application while decisions are pending or blocking")
    if output.exists():
        raise ValueError("application output must be fresh; existing authority is not overwritten")
    from certificate_application import regenerate_from_completed_review

    geometry = json.loads((root / "human_review/geometry_evidence.json").read_text())
    decisions_sha = content_hash(document)
    result = regenerate_from_completed_review(
        root,
        geometry,
        document["items"][0]["selected_option"],
        "HUMAN_REVIEW_" + decisions_sha[:16],
        decisions_sha,
    )
    certificate_status = "PASS" if result["certificate"] is not None else "NOT_CERTIFIED"
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix="review-staging-") as temporary:
        stage = Path(temporary)
        write_json(stage / "human_decisions.json", document)
        write_json(
            stage / "review_receipt.json",
            {
                "schema_version": "phase1-human-review-receipt-v1",
                "human_decisions_sha256": decisions_sha,
                "review_payload_sha256": document["review_payload_sha256"],
                "reviewer": document["metadata"]["reviewer"],
                "submitted_at": document["metadata"]["submitted_at"],
                "source_sha256": document["metadata"]["source_sha256"],
                "certificate_status": certificate_status,
                "formal_execution_enabled": False,
            },
        )
        write_json(stage / "certificate_result.json", result)
        write_json(
            stage / "approved_input_lock.json", approved_input_lock(document, certificate_status)
        )
        write_json(stage / "resume_plan.json", json.loads((HERE / "resume_plan.json").read_text()))
        write_json(
            stage / "manifest.json",
            {
                "schema_version": "phase1-human-review-application-v1",
                "artifacts": [
                    {"path": path.name, "sha256": file_hash(path)}
                    for path in sorted(stage.iterdir())
                ],
            },
        )
        stage.rename(output)
    return {
        "status": "INPUTS_APPLIED_AUTOMATIC_CASE_READINESS_PENDING",
        "certificate_status": certificate_status,
        "output": str(output),
        "human_decisions_sha256": decisions_sha,
        "formal_execution_enabled": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=HERE / "decisions.json")
    parser.add_argument("--source-asset", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = json.loads(args.decisions.read_text())
    template = json.loads((HERE / "review_template.json").read_text())
    state = validate_decisions(document, template)
    verify_inputs(ROOT, template, args.source_asset)
    if args.apply:
        if args.output is None:
            parser.error("--apply requires a fresh --output path")
        state = apply_completed(document, template, root=ROOT, output=args.output)
    print(json.dumps(state, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
