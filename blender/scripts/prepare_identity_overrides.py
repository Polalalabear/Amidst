#!/usr/bin/env python3
"""Build reviewed school_v1 identity-override sidecars without opening Blender."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import unicodedata
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EFFECTIVE_POLICY_ID = "amidst.school.object-id/1.0.1"
EFFECTIVE_POLICY_VERSION = "1.0.1"
BASE_POLICY_ID = "amidst.school.object-id/1.0.0"
NAMESPACE_UUID = uuid.UUID("1601a7c1-19ac-555d-9962-05e4503ac6bd")
SOURCE_SHA256 = "cbfef8c84295253323890be5d9ffae186c46481f9dde8a6509ce897c49a34fa1"
AUTOMATIC_METHOD = "approved_objective_disambiguation"
BOOTSTRAP_METHOD = "human_reviewed_bootstrap"
BOOTSTRAP_RE = re.compile(r"^bootstrap:[0-9]{3}$")


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def canonical_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return normalize_text(value) if isinstance(value, str) else value
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = normalize_text(str(raw_key))
            if key in result:
                raise ValueError(f"Duplicate canonical key: {key!r}")
            result[key] = canonical_value(raw_value)
        return result
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    raise TypeError(f"Unsupported canonical bootstrap value: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_canonical(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def resolved_identity(base_fingerprint: str, method: str, token: str) -> tuple[str, str]:
    resolved_fingerprint = digest(
        {
            "base_fingerprint": base_fingerprint,
            "disambiguation_method": method,
            "disambiguation_token": token,
        }
    )
    object_uuid = uuid.uuid5(NAMESPACE_UUID, f"{BASE_POLICY_ID}:{resolved_fingerprint}")
    return resolved_fingerprint, f"amidst:school:object:{object_uuid}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT / "data/reports/school_v1_disambiguation_evidence.json",
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "data/annotations/instance_registry/school.json",
    )
    parser.add_argument(
        "--automatic-output",
        type=Path,
        default=(ROOT / "data/annotations/instance_registry/school_v1_disambiguation.json"),
    )
    parser.add_argument(
        "--bootstrap-output",
        type=Path,
        default=(ROOT / "data/annotations/instance_registry/school_v1_identity_bootstrap.json"),
    )
    return parser.parse_args()


def object_sort_key(member: dict[str, Any]) -> bytes:
    return normalize_text(member["object_reference"]).encode("utf-8")


def locator(name: str) -> dict[str, Any]:
    return {
        "blender_object_name": normalize_text(name),
        "role": "school_v1_initial_locator_only",
        "participates_in_fingerprint_or_uuid_input": False,
    }


def automatic_records(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for group in groups:
        if not group["all_members_uniquely_discriminated"]:
            continue
        differing_fields = [item["field"] for item in group["differing_objective_fields"]]
        if differing_fields != ["hierarchy.child_fingerprints"]:
            raise ValueError(f"Unapproved automatic discriminator in {group['group_id']}")
        for member in sorted(group["members"], key=object_sort_key):
            token = member["proposed_disambiguation_token"]
            base_fingerprint = group["duplicate_fingerprint"]
            resolved_fingerprint, instance_id = resolved_identity(
                base_fingerprint, AUTOMATIC_METHOD, token
            )
            records.append(
                {
                    "scene_id": "school",
                    "scene_version": "v1",
                    "collision_group_id": group["group_id"],
                    "current_blender_object_locator": locator(member["object_reference"]),
                    "original_canonical_fingerprint": base_fingerprint,
                    "objective_discriminator": {
                        "field": "hierarchy.child_fingerprints",
                        "value": member["objective_evidence"]["hierarchy"]["child_fingerprints"],
                    },
                    "disambiguation_token": token,
                    "resolved_identity_fingerprint": resolved_fingerprint,
                    "final_proposed_instance_id": instance_id,
                    "assignment_method": AUTOMATIC_METHOD,
                    "reviewer_status": "CONFIRMED",
                    "reason": "unique_sorted_child_fingerprint_multiset",
                    "policy_version": EFFECTIVE_POLICY_VERSION,
                    "category": "Unknown",
                    "annotation_status": "needs_review",
                }
            )
    records.sort(key=lambda record: record["final_proposed_instance_id"].encode("ascii"))
    return records


def bootstrap_records(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for group in groups:
        if group["all_members_uniquely_discriminated"]:
            continue
        members = sorted(group["members"], key=object_sort_key)
        for ordinal, member in enumerate(members, start=1):
            token = f"bootstrap:{ordinal:03d}"
            if not BOOTSTRAP_RE.fullmatch(token):
                raise ValueError(f"Invalid bootstrap discriminator: {token}")
            base_fingerprint = group["duplicate_fingerprint"]
            resolved_fingerprint, instance_id = resolved_identity(
                base_fingerprint, BOOTSTRAP_METHOD, token
            )
            records.append(
                {
                    "scene_id": "school",
                    "scene_version": "v1",
                    "collision_group_id": group["group_id"],
                    "current_blender_object_locator": locator(member["object_reference"]),
                    "original_canonical_fingerprint": base_fingerprint,
                    "bootstrap_discriminator": token,
                    "resolved_identity_fingerprint": resolved_fingerprint,
                    "final_proposed_instance_id": instance_id,
                    "assignment_method": BOOTSTRAP_METHOD,
                    "reviewer_status": "CONFIRMED",
                    "reason": "approved_school_v1_initialization_exception",
                    "policy_version": EFFECTIVE_POLICY_VERSION,
                    "category": "Unknown",
                    "annotation_status": "needs_review",
                }
            )
    records.sort(key=lambda record: record["final_proposed_instance_id"].encode("ascii"))
    return records


def validate_records(
    automatic: list[dict[str, Any]], bootstrap: list[dict[str, Any]], registry: dict[str, Any]
) -> None:
    if len(automatic) != 5:
        raise ValueError(f"Expected 5 automatic records, found {len(automatic)}")
    if len(bootstrap) != 131:
        raise ValueError(f"Expected 131 bootstrap records, found {len(bootstrap)}")
    bootstrap_groups = {record["collision_group_id"] for record in bootstrap}
    if len(bootstrap_groups) != 44:
        raise ValueError(f"Expected 44 bootstrap groups, found {len(bootstrap_groups)}")

    for group_id in bootstrap_groups:
        group_records = [record for record in bootstrap if record["collision_group_id"] == group_id]
        tokens = [record["bootstrap_discriminator"] for record in group_records]
        if len(tokens) != len(set(tokens)):
            raise ValueError(f"Duplicate bootstrap discriminator in {group_id}")

    proposed_ids = [record["instance_id"] for record in registry["records"]]
    proposed_ids.extend(record["final_proposed_instance_id"] for record in automatic)
    proposed_ids.extend(record["final_proposed_instance_id"] for record in bootstrap)
    if len(proposed_ids) != 2777 or len(proposed_ids) != len(set(proposed_ids)):
        raise ValueError("Final proposed instance IDs are incomplete or non-unique")


def main() -> None:
    args = parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    if evidence.get("source_sha256") != SOURCE_SHA256:
        raise SystemExit("Disambiguation evidence source checksum mismatch")
    if registry.get("source_sha256") != SOURCE_SHA256:
        raise SystemExit("Registry source checksum mismatch")

    groups = evidence["groups"]
    automatic = automatic_records(groups)
    bootstrap = bootstrap_records(groups)
    validate_records(automatic, bootstrap, registry)

    shared = {
        "repository_classification": "REVIEW_REQUIRED",
        "authority": "approved_school_v1_identity_override",
        "effective_policy_id": EFFECTIVE_POLICY_ID,
        "base_fingerprint_policy_id": BASE_POLICY_ID,
        "namespace_uuid": str(NAMESPACE_UUID),
        "scene_id": "school",
        "scene_version": "v1",
        "source_scene": "school_v1.blend",
        "source_sha256": SOURCE_SHA256,
        "resolved_identity_derivation": {
            "payload_fields": [
                "base_fingerprint",
                "disambiguation_method",
                "disambiguation_token",
            ],
            "payload_serialization": "amidst.school.object-id/1.0.0 canonical JSON",
            "resolved_fingerprint": "SHA-256",
            "uuid5_name": "amidst.school.object-id/1.0.0:<resolved_identity_fingerprint>",
        },
    }
    automatic_output = {
        "schema_name": "amidst.school_object_objective_disambiguation",
        "schema_version": "1.0.0",
        "status": "CONFIRMED",
        **shared,
        "approved_discriminator": "hierarchy.child_fingerprints",
        "records": automatic,
        "record_count": len(automatic),
    }
    bootstrap_output = {
        "schema_name": "amidst.school_object_identity_bootstrap",
        "schema_version": "1.0.0",
        "status": "CONFIRMED",
        **shared,
        "assignment_method": BOOTSTRAP_METHOD,
        "discriminator_format": "bootstrap:<three ASCII decimal digits>",
        "mapping_construction": {
            "member_locator_order": "Unicode NFC UTF-8 byte order within collision group",
            "ordinal_scope": "collision_group",
            "ordinal_start": 1,
            "locator_role": "one-time explicit reviewed binding only",
            "regeneration_after_assignment": "prohibited",
        },
        "eligibility_exclusions": [
            {
                "scene_id": "school",
                "scene_version": "v1",
                "current_blender_object_locator": locator(
                    "skp_camera_Last_Saved_SketchUp_View"
                ),
                "object_type": "CAMERA",
                "reviewer_status": "CONFIRMED",
                "reason": "non_authoritative_imported_saved_view_helper_with_non_finite_lens",
                "policy_version": EFFECTIVE_POLICY_VERSION,
            }
        ],
        "records": bootstrap,
        "record_count": len(bootstrap),
        "collision_group_count": len(
            {record["collision_group_id"] for record in bootstrap}
        ),
    }
    write_canonical(args.automatic_output, automatic_output)
    write_canonical(args.bootstrap_output, bootstrap_output)
    print(
        canonical_bytes(
            {
                "automatic_records": len(automatic),
                "bootstrap_records": len(bootstrap),
                "combined_unique_ids": 2777,
                "status": "CONFIRMED",
            }
        ).decode("utf-8")
    )


if __name__ == "__main__":
    main()
