"""Inventory finalization artifacts without deleting, moving or cleaning anything."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) if path.is_dir() \
        else path.stat().st_size if path.exists() else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--fresh", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows: list[dict[str, Any]] = []

    def add(path: Path, category: str, reason: str, replacement: str, command: str) -> None:
        label = str(path.relative_to(root)) if path.is_relative_to(root) else str(path)
        rows.append({"path": label, "category": category, "size_bytes": size(path),
                     "reason": reason, "canonical_replacement": replacement,
                     "regeneration_command": command})

    for relative in ("src", "scripts", "configs", "tests", "docs", "human_review",
                     "data/finalization/checkpoint"):
        add(root / relative, "KEEP", "source/config/tests/docs or checkpoint evidence",
            "this published finalization branch", "git checkout <published-finalization-SHA>")
    for run in (args.local, args.fresh):
        for path in sorted(run.iterdir()):
            draft = "draft" in path.name
            add(path, "ARCHIVE" if draft else "REGENERABLE",
                "retained pre-final diagnostic draft" if draft else
                "local raw diagnostic package; summarized and hash-bound in Git",
                "data/finalization/checkpoint", "see docs/PHASE1_REPRODUCTION.md")
    physical = root / "data/scene_audit/phase1_physical_policy_approval_20261006"
    for path in sorted(physical.glob("*.gz")):
        add(path, "REGENERABLE", "large approved evidence kept locally, excluded from Git",
            str((physical / "artifact_manifest.json").relative_to(root)),
            "uv run python -m amidst.materialize_physical_evidence --source-scene <source>")
    for relative in ("data/scene_audit/phase1_geometry_authority_20261006",
                     "data/scene_audit/phase1_physical_authority_20261006",
                     "data/scene_audit/school_v3_approved_scale_20261006"):
        add(root / relative, "ARCHIVE", "inherited historical provenance; retained unchanged",
            "active physical context plus finalization input lock",
            "git checkout f264db1579882e54cecba22db24ec8798822fd0c -- " + relative)
    rows.append({"path": "blender/school_v3.blend (external local source)", "category": "KEEP",
                 "size_bytes": 468300506, "reason": "immutable private/local research source",
                 "canonical_replacement": "SHA256 cd46fa03...e84e; no regenerated replacement",
                 "regeneration_command": "supply exact source; never synthesize or rescale"})
    checkpoint = root / "data/finalization/checkpoint"
    checkpoint.mkdir(parents=True, exist_ok=True)
    with (checkpoint / "artifact_inventory.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (checkpoint / "artifact_inventory.json").write_text(json.dumps({
        "status": "INVENTORY_ONLY_NO_DELETION", "formal_validation": "BLOCKED",
        "delete_candidates": [], "rows": rows,
    }, sort_keys=True, indent=2) + "\n")
    lines = ["# Phase 1 artifact cleanup / Artifact 整理", "",
             "Status: **inventory only** after completed diagnostic verification. "
             "Formal validation remains blocked. No artifact was deleted.", "",
             "保留 source/config/tests/docs、experiment log、reports、manifests/hashes。"
             "Raw dataset、RRD、Blender 和大型物理證據只在本機保存。"
             "ARCHIVE 是分類，沒有移動或刪除 inherited provenance。", "",
             "DELETE_CANDIDATE: none selected; no automatic deletion is authorized.", "",
             "| Path | Category | Size (bytes) | Reason | Canonical replacement | Regeneration |",
             "| --- | --- | --- | --- | --- | --- |"]
    lines.extend("| " + " | ".join(str(row[key]).replace("|", "\\|") for key in rows[0])
                 + " |" for row in rows)
    lines.extend(["", "Detailed machine-readable inventory: "
                  "[CSV](../data/finalization/checkpoint/artifact_inventory.csv).",
                  "", "Rebuild this inventory after reproduction:", "", "```sh",
                  "uv run python scripts/inventory_phase1_finalization_artifacts.py \\",
                  "  --local data/finalization/local_run \\",
                  "  --fresh /absolute/path/to/fresh-checkout/data/finalization/fresh_run",
                  "```", ""])
    (root / "docs/PHASE1_ARTIFACT_CLEANUP.md").write_text("\n".join(lines))


if __name__ == "__main__":
    main()
