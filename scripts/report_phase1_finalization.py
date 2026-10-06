"""Publish honest Phase 1 exit evidence; never convert a diagnostic run to FORMAL."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_bytes())


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def verify_hashes(root: Path, hashes: dict[str, str]) -> None:
    for relative, expected in hashes.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or sha(path) != expected:
            raise ValueError("artifact missing or changed: " + relative)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", type=Path, required=True)
    parser.add_argument("--fresh", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    protocol = load(root / "configs/benchmarks/protocol_v1.json")
    scopes = load(root / "data/scene_audit/phase1_physical_policy_approval_20261006/"
                  "local_physical_scopes.json")
    if protocol["formal_execution_enabled"] or scopes["approved_scope_count"] != 0:
        raise ValueError("this blocked-checkpoint report requires re-audit after authority changes")
    args.output.mkdir(parents=True, exist_ok=True)
    local_manifest = load(args.local / "dataset/manifest.json")
    fresh_manifest = load(args.fresh / "dataset/manifest.json")
    verify_hashes(args.local / "dataset", local_manifest["artifacts"])
    verify_hashes(args.fresh / "dataset", fresh_manifest["artifacts"])
    dataset_equal = local_manifest == fresh_manifest
    write(args.output / "dataset_manifest.json", local_manifest)
    rows = []
    columns = ["Case", "Method", "K", "Status", "ADE", "FDE", "minADE@K", "minFDE@K",
               "Coverage@K", "Physical validity", "Candidates", "Expanded states", "Runtime",
               "Termination"]
    for case in ("Case 1 — Unique Route", "Case 2 — Branching Top-K",
                 "Case 3 — Long Gap / Timing Ambiguity"):
        for method in ("A — shortest_path", "B — geometry", "C — spatiotemporal"):
            for k in (1, 2, 3):
                rows.append(dict(zip(columns, [case, method, k, "N/A / NOT_RUN",
                                               *(["N/A"] * 5), "NOT_CERTIFIED",
                                               *(["N/A"] * 3), "NOT_RUN"], strict=True)))
    with (args.output / "benchmark_table.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    table = ["# Phase 1 formal benchmark status / 正式 benchmark 狀態", "",
             "Status: **PHASE1_FINALIZATION_BLOCKED**. No formal Case was executed.", "",
             "All requested Case/method/K rows remain visible. N/A is not zero or PASS.", "",
             "| " + " | ".join(columns) + " |",
             "| " + " | ".join(["---"] * len(columns)) + " |"]
    table.extend("| " + " | ".join(str(row[key]) for key in columns) + " |" for row in rows)
    (args.output / "benchmark_table.md").write_text("\n".join(table) + "\n")
    for name, explanation in {
        "accuracy": "ADE / FDE / minADE@K / minFDE@K: no formal measurements",
        "coverage": "Coverage D / epsilon pending; no default substituted",
        "top_k_candidates": "K=1/2/3 requested; no certified Case route inventory",
        "runtime_search": "Runtime / expanded states: no formal inference executed",
        "termination": "NOT_RUN for Cases 1–3; no invented Graph termination",
        "physical_validity": "0 approved local scope certificates; NOT_CERTIFIED",
    }.items():
        figure, axis = plt.subplots(figsize=(9, 3))
        axis.set_axis_off()
        axis.text(0.5, 0.68, "N/A — FORMAL CASES 1–3 NOT RUN", ha="center", fontsize=17)
        axis.text(0.5, 0.40, explanation, ha="center", fontsize=11)
        axis.text(0.5, 0.15, "PHASE1_FINALIZATION_BLOCKED", ha="center", color="darkred")
        figure.tight_layout()
        figure.savefig(args.output / (name + ".png"), dpi=120)
        plt.close(figure)
    local_diagnostics = load(args.local / "diagnostics/verification.json")
    fresh_diagnostics = load(args.fresh / "diagnostics/verification.json")
    verify_hashes(args.local / "diagnostics", local_diagnostics["canonical_artifacts"])
    verify_hashes(args.fresh / "diagnostics", fresh_diagnostics["canonical_artifacts"])
    diagnostics_equal = (local_diagnostics["canonical_artifacts"] ==
                         fresh_diagnostics["canonical_artifacts"])
    technical_pass = all(report["status"] == "DIAGNOSTIC_TECHNICAL_PASS"
                         for report in (local_diagnostics, fresh_diagnostics))
    readers_pass = all(row.get("demo", {}).get("rrd_reader_verified") is True
                       for report in (local_diagnostics, fresh_diagnostics)
                       for row in report["streams"])
    physical_relative = Path("data/scene_audit/phase1_physical_policy_approval_20261006")
    physical_local = root / physical_relative
    physical_fresh = args.fresh.resolve().parents[2] / physical_relative
    receipts = [load(path / "materialization_receipt.json")
                for path in (physical_local, physical_fresh)]
    for path, receipt in zip((physical_local, physical_fresh), receipts, strict=True):
        verify_hashes(path, receipt["artifact_byte_sha256"])
    physical_pass = (
        all(receipt["status"] == "MATERIALIZED_AND_RESEARCH_EQUIVALENT"
            and receipt["source_observed_before"] == receipt["source_observed_after"]
            for receipt in receipts)
        and receipts[0]["artifact_byte_sha256"] == receipts[1]["artifact_byte_sha256"]
        and receipts[0]["research_results"] == receipts[1]["research_results"]
    )
    write(args.output / "physical_reproducibility.json", {
        "status": "PASS" if physical_pass else "FAIL",
        "artifact_byte_sha256": receipts[0]["artifact_byte_sha256"],
        "research_results": receipts[0]["research_results"],
        "both_materializations_research_equivalent": physical_pass,
        "source_preserved": all(receipt["source_observed_before"] ==
                                receipt["source_observed_after"] for receipt in receipts),
        "canonical_manifest_sha256": receipts[0]["canonical_manifest_sha256"],
        "historical_provenance_retained": True,
    })
    for field, filename, title in (
        ("projection_method_counts", "projection_methods.png", "Projection methods"),
        ("projection_state_counts", "projection_confidence.png", "Projection confidence states"),
    ):
        streams = local_diagnostics["streams"]
        labels = sorted({key for row in streams for key in row[field]})
        figure, axis = plt.subplots(figsize=(10, 4))
        bottom = [0] * len(streams)
        for label in labels:
            values = [row[field].get(label, 0) for row in streams]
            axis.bar([row["site"] for row in streams], values, bottom=bottom, label=label)
            bottom = [a + b for a, b in zip(bottom, values, strict=True)]
        axis.set(ylabel="Timestamps", title=title + " / DIAGNOSTIC, NOT FORMAL")
        axis.legend(fontsize=8)
        figure.tight_layout()
        figure.savefig(args.output / filename, dpi=120)
        plt.close(figure)
    reproduction = {"status": "PASS" if all((dataset_equal, diagnostics_equal, technical_pass,
                                             readers_pass, physical_pass)) else "FAIL",
                    "scope": "DIAGNOSTIC_DATASET_AND_REPLAY_NOT_FORMAL_CASES",
                    "dataset_manifest_byte_equal":
                        sha(args.local / "dataset/manifest.json") ==
                        sha(args.fresh / "dataset/manifest.json"),
                    "all_dataset_hashes_equal": dataset_equal,
                    "canonical_diagnostic_hashes_equal": diagnostics_equal,
                    "both_technical_verification_pass": technical_pass,
                    "all_six_rrd_reader_checks_pass": readers_pass,
                    "fresh_physical_materialization_pass": physical_pass,
                    "all_artifact_bytes_verified": True,
                    "local_manifest_sha256": sha(args.local / "dataset/manifest.json"),
                    "fresh_manifest_sha256": sha(args.fresh / "dataset/manifest.json"),
                    "formal_fresh_rerun": "NOT_RUN",
                    "freeze_permitted": False}
    for name, report in (("local", local_diagnostics), ("fresh", fresh_diagnostics)):
        write(args.output / f"verification_{name}.json", report)
    baseline_paths = (args.local / "baseline_regression.json",
                      args.fresh / "baseline_regression.json")
    if all(path.exists() for path in baseline_paths):
        baseline_equal = baseline_paths[0].read_bytes() == baseline_paths[1].read_bytes()
        reproduction["baseline_regression_byte_equal"] = baseline_equal
        if not baseline_equal:
            reproduction["status"] = "FAIL"
        write(args.output / "baseline_regression.json", load(baseline_paths[0]))
    write(args.output / "reproducibility.json", reproduction)
    selected = [root / "configs/phase1_finalization_export_v1.json",
                root / "configs/benchmarks/protocol_v1.json",
                root / "configs/physical_context_school_v3.json",
                root / "configs/physical_authority_policy_school_v3.json",
                root / "configs/physical_policy_runtime_school_v3.json",
                root / "configs/architectural_scale_school_v3.json", root / "uv.lock",
                root / "scripts/export_phase1_finalization_inputs.py",
                root / "scripts/phase1_projection_policy.py",
                root / "scripts/replay_phase1_finalization_diagnostics.py",
                root / "scripts/report_phase1_finalization.py",
                root / "src/amidst/datasets/pilot.py",
                root / "src/amidst/benchmark/baselines.py",
                root / "src/amidst/graph/engine.py"]
    inherited = ("projection_multiview_model", "projection_uncertainty_model",
                 "projection_mitigation_policy", "projection_conditioning")
    snapshot = {"version": "phase1-finalization-input-lock-v1", "date": "2026-10-06",
                "status": "FROZEN_DIAGNOSTIC_INPUTS_FORMAL_SETTINGS_PENDING",
                "physical_checkpoint": "f264db1579882e54cecba22db24ec8798822fd0c",
                "projection_checkpoint": "8f4055ffcdc3bf6efd723c7956ac685e1fe033f1",
                "source_sha256": local_manifest["source_sha256"],
                "dataset_version": local_manifest["dataset_version"],
                "protocol_version": protocol["protocol_version"],
                "formal_execution_enabled": False, "k_values_requested": [1, 2, 3],
                "formal_coverage_settings": protocol["coverage"]["formal_settings"],
                "diagnostic_sampling": "existing pilot 5 Hz, [0,10), 50 timestamps",
                "diagnostic_seed": local_manifest["seed"],
                "input_hashes": {str(p.relative_to(root)): sha(p) for p in selected},
                "selective_projection_files": {f"scripts/{name}.py": sha(
                    root / f"scripts/{name}.py") for name in inherited},
                "excluded": ["unapproved WALLs", "8 portal conflicts", "Stair A/B",
                             "uncertified local navigation", "surface-constrained inference",
                             "Case 4", "Phase 2"],
                "post_benchmark_rule_change": "forbidden; new inputs require new version",
                "formal_baselines": "existing protocol A/B/C; no GT ordering",
                "projection_policy": "EXACT_TIME_MULTIVIEW -> SINGLE_VIEW_FIXED_PLANE; "
                                     "conditioning/uncertainty -> LOW_CONFIDENCE/UNAVAILABLE"}
    write(args.output / "input_lock.json", snapshot)
    write(args.output / "exit_gate.json", {
        "status": "PHASE1_FINALIZATION_BLOCKED", "freeze_allowed": False,
        "formal_cases_1_3": "NOT_RUN", "formal_baselines_A_B_C": "NOT_RUN",
        "formal_dataset": "NOT_CERTIFIED", "formal_gt_isolation": "NOT_RUN",
        "formal_determinism": "NOT_RUN", "formal_rerun_demos": "NOT_RUN",
        "physical_authority": "PARTIAL_APPROVED", "approved_local_scopes": 0,
        "minimal_authority_blockers": [
            "certified local navigation scope and Case route inventory",
            "source-bound camera/landmark-plane and formal metric settings"],
        "human_gate": "human_review/README.md",
        "diagnostic_reproducibility": reproduction,
    })
    write(args.output / "package_hashes.json", {
        "artifacts": {str(p.relative_to(args.output)): sha(p)
                      for p in sorted(args.output.rglob("*"))
                      if p.is_file() and p.name != "package_hashes.json"},
        "hash_excludes": ["package_hashes.json", "runtime and RRD container UUIDs"],
        "status": "BLOCKED_CHECKPOINT_NOT_FROZEN_BENCHMARK"})
    print(json.dumps(reproduction))


if __name__ == "__main__":
    main()
