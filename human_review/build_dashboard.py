"""Build the offline Phase 1 human-review dashboard from pending decisions.

No decisions are approved or applied by this builder. It only embeds the review
payload and preserves current decisions in a local, dependency-free HTML page.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decisions", type=Path, default=ROOT / "human_review/decisions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "human_review/index.html")
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
    args.output.write_text(
        template.replace("__DECISIONS_JSON__", encoded).replace(
            "__REVIEW_PAYLOAD_HASH__", payload_hash(document)
        )
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
