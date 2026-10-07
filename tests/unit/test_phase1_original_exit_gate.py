"""A partial certificate or missing evidence never grants a Phase 1 freeze."""

import pytest

from amidst.finalization.exit_gate import GATES, assess_original_exit_gate


def test_all_original_gates_required() -> None:
    for omitted in GATES:
        evidence = dict.fromkeys(GATES, True)
        del evidence[omitted]
        result = assess_original_exit_gate(evidence)
        assert result["status"] == "PHASE1_FINALIZATION_BLOCKED"
        assert result["freeze_tag_permitted"] is False
        assert result["minimal_real_blockers"] == [omitted]


@pytest.mark.parametrize("value", [False, None, 1, "PASS", [], {}])
def test_no_truthy_or_status_string_coercion(value: object) -> None:
    evidence = dict.fromkeys(GATES, True)
    evidence[GATES[0]] = value  # type: ignore[assignment]
    assert assess_original_exit_gate(evidence)["freeze_tag_permitted"] is False


def test_source_scope_blocker_groups_dependent_deliverables() -> None:
    result = assess_original_exit_gate({
        name: True for name in GATES
        if name not in {
            "case2_source_distinct_feasible_branches",
            "case3_long_gap_detour_growth_and_budget_stress",
            "fresh_formal_dataset_all_cases",
            "formal_cases_1_3_and_a_b_c_and_ablations",
        }
    }, source_scope_blockers=("ONE_CLASS_APPROVED_DOMAIN",))
    assert result["minimal_real_blockers"] == ["ONE_CLASS_APPROVED_DOMAIN"]
    assert result["freeze_tag_permitted"] is False
    assert sum("dependency" in row for row in result["gates"]) == 4


def test_complete_gate_and_unresolved_scope_conflict_refuses_freeze() -> None:
    evidence = dict.fromkeys(GATES, True)
    assert assess_original_exit_gate(evidence)["freeze_tag_permitted"] is True
    assert assess_original_exit_gate(
        evidence, source_scope_blockers=("SCOPE_CONTRADICTION",)
    )["freeze_tag_permitted"] is False
