"""Fail-closed accounting of the original Phase 1 finalization requirements.

Record every gate, while grouping downstream work under its actual prerequisite
blocker. A validated bounded physical certificate cannot enable a whole sprint.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

GATES = (
    "source_and_historical_inputs_verified",
    "bounded_reviewed_certificate_pass",
    "formal_adapters_verified",
    "config_locked_before_simulation",
    "case1_unique_visible_gap_visible",
    "case2_source_distinct_feasible_branches",
    "case3_long_gap_detour_growth_and_budget_stress",
    "fresh_formal_dataset_all_cases",
    "formal_cases_1_3_and_a_b_c_and_ablations",
    "required_metrics_complete",
    "benchmark_tables_and_charts_complete",
    "formal_rerun_png_replay_all_cases",
    "gt_poison_pass",
    "repeated_inference_pass",
    "fresh_process_pass",
    "observation_ordering_pass",
    "bounded_search_termination_pass",
    "fresh_checkout_materialization_export_inference_report_demo_comparison_pass",
    "full_pytest_with_actual_physical_evidence_pass",
    "ruff_pass",
    "strict_mypy_pass",
    "diff_check_pass",
    "local_raw_artifact_policy_pass",
    "phase2_frozen_and_case4_deferred",
)

DEPENDENT_GATES = frozenset({
    "fresh_formal_dataset_all_cases", "formal_cases_1_3_and_a_b_c_and_ablations",
    "required_metrics_complete", "benchmark_tables_and_charts_complete",
    "formal_rerun_png_replay_all_cases",
    "fresh_checkout_materialization_export_inference_report_demo_comparison_pass",
})


def assess_original_exit_gate(
    evidence: Mapping[str, Any], *, source_scope_blockers: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Only explicit PASS for every requirement permits a freeze; no truthy coercion."""
    rows = [
        {"gate": gate, "status": "PASS" if evidence.get(gate) is True else "NOT_COMPLETE"}
        for gate in GATES
    ]
    complete = all(row["status"] == "PASS" for row in rows) and not source_scope_blockers
    blockers = list(dict.fromkeys(source_scope_blockers))
    scope_gates = {
        "case2_source_distinct_feasible_branches",
        "case3_long_gap_detour_growth_and_budget_stress",
    }
    for row in rows:
        if row["status"] == "PASS":
            continue
        if source_scope_blockers and row["gate"] in DEPENDENT_GATES | scope_gates:
            row["dependency"] = "APPROVED_SOURCE_SCOPE_INSUFFICIENT"
            continue
        blockers.append(row["gate"])
    return {
        "schema_version": "phase1-original-exit-gate-v1",
        "status": (
            "PHASE1_EXIT_VALIDATED_FREEZE_PENDING" if complete else "PHASE1_FINALIZATION_BLOCKED"
        ),
        "all_original_exit_gates_complete": complete,
        "freeze_tag_permitted": complete,
        "gates": rows,
        "minimal_real_blockers": blockers,
        "human_approvals_reopened": False,
        "case4": "DEFERRED", "phase2": "FROZEN",
    }
