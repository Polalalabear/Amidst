"""Independent route and camera-handoff metrics over synthetic source authority."""

import ast
from pathlib import Path
from typing import Any

import pytest
from test_reviewed_authority import CONFIG, _context, _inference, _run
from test_reviewed_authority import authority as authority

from amidst.domain.trajectory import CandidateTrajectory, Event, TerminationReason
from amidst.finalization.reviewed_authority import ReviewedAuthority, ReviewedBaselineRun
from amidst.finalization.reviewed_evaluation_metrics import (
    ReviewedMetricInventory,
    build_reviewed_metric_inventory,
    evaluate_reviewed_inventory_metrics,
)


def _inventory(authority: ReviewedAuthority) -> ReviewedMetricInventory:
    context = _context(authority)
    inputs, aggregation, _ = _inference(authority, context)
    return build_reviewed_metric_inventory(
        aggregation, context, authority, frozen_config_sha256=CONFIG,
        endpoint_tolerance_m=inputs.reconstruction_policy.endpoint_tolerance_m,
    )


def _replace_candidates(
    run: ReviewedBaselineRun, candidates: tuple[CandidateTrajectory, ...],
) -> ReviewedBaselineRun:
    event = Event.model_validate(run.event.model_dump() | {
        "candidates": tuple(candidate.model_dump() for candidate in candidates),
        "trajectories": (), "termination_reason": (
            TerminationReason.COMPLETE if candidates else TerminationReason.NO_FEASIBLE_PATH
        ),
    })
    timed = run.timed_result.model_dump() | {
        "candidates": tuple(candidate.model_dump() for candidate in candidates),
        "termination_reason": event.termination_reason, "complete": True,
    }
    return ReviewedBaselineRun.model_validate(run.model_dump() | {
        "event": event.model_dump(), "timed_result": timed,
    })


def test_independent_convex_inventory_makes_required_metrics_available(
    authority: ReviewedAuthority,
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    result = evaluate_reviewed_inventory_metrics(run, inventory, authority)
    assert inventory.eligible_feasible_route_classes == 1
    assert result["feasible_candidate_recall"] == 1
    assert result["feasible_candidate_recall_numerator"] == 1
    assert result["feasible_candidate_recall_denominator"] == 1
    assert result["impossible_transition_rate"] == 0
    assert result["transition_count"] == 1
    assert result["ground_truth_used_for_inventory"] is False
    assert result["engine_corridor_or_topology_used_for_inventory"] is False
    assert result["travel_time_error_s"] is None
    assert "NOT_APPROVED" in result["travel_time_error_status"]


def test_alternate_timings_and_duplicate_emitted_class_do_not_inflate_recall(
    authority: ReviewedAuthority,
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    assert len(run.event.trajectories) == 2
    result = evaluate_reviewed_inventory_metrics(run, inventory, authority)
    assert result["transition_count"] == 1
    second = run.event.candidates[0].model_copy(update={"candidate_id": "other-id-same-route"})
    duplicated_class = _replace_candidates(run, (run.event.candidates[0], second))
    result = evaluate_reviewed_inventory_metrics(duplicated_class, inventory, authority)
    assert result["feasible_candidate_recall"] == 1
    assert result["feasible_candidate_recall_numerator"] == 1
    assert result["transition_count"] == 2
    assert result["impossible_transition_rate"] == 0


def test_empty_output_is_zero_recall_and_na_transition_denominator(
    authority: ReviewedAuthority,
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    result = evaluate_reviewed_inventory_metrics(_replace_candidates(run, ()), inventory, authority)
    assert result["feasible_candidate_recall"] == 0
    assert result["feasible_candidate_recall_denominator"] == 1
    assert result["impossible_transition_rate"] is None
    assert result["transition_count"] == 0


def test_metrics_validate_physical_handoff_independently_of_engine_corridor_ids(
    authority: ReviewedAuthority,
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    unrelated_name = run.event.candidates[0].model_copy(update={
        "navmesh_corridor": ("NO_MATCH_IN_THE_ENGINE_CONFIG",),
    })
    result = evaluate_reviewed_inventory_metrics(
        _replace_candidates(run, (unrelated_name,)), inventory, authority,
    )
    assert result["feasible_candidate_recall"] == 1
    assert result["impossible_transition_rate"] == 0


@pytest.mark.parametrize("mutation", ["direction", "anchor", "outside_scope", "too_long"])
def test_source_invalid_candidate_is_not_recalled_and_has_impossible_local_handoff(
    authority: ReviewedAuthority, mutation: str,
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    candidate = run.event.candidates[0]
    values = candidate.model_dump()
    if mutation == "direction":
        values.update(start_observation_id=candidate.end_observation_id,
                      end_observation_id=candidate.start_observation_id)
    elif mutation == "anchor":
        values["polyline"] = ((3.1, 5., 0.), (7., 5., 0.))
    elif mutation == "outside_scope":
        values["polyline"] = ((3., 5., 0.), (1., 5., 0.), (7., 5., 0.))
    else:
        values["polyline"] = ((3., 5., 0.), (3., 7.9, 0.), (7., 7.9, 0.), (7., 5., 0.))
    candidate = CandidateTrajectory.model_validate(values)
    result = evaluate_reviewed_inventory_metrics(
        _replace_candidates(run, (candidate,)), inventory, authority,
    )
    assert result["feasible_candidate_recall"] == 0
    assert result["impossible_transition_rate"] == 1
    assert result["impossible_transition_count"] == 1
    assert result["transition_failures"]


def test_noncanonical_feasible_curve_is_not_a_second_eligible_route(
    authority: ReviewedAuthority,
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    candidate = run.event.candidates[0].model_copy(update={
        "polyline": ((3., 5., 0.), (5., 5.2, 0.), (7., 5., 0.)),
    })
    result = evaluate_reviewed_inventory_metrics(
        _replace_candidates(run, (candidate,)), inventory, authority,
    )
    assert result["feasible_candidate_recall"] == 0
    assert result["feasible_candidate_recall_denominator"] == 1
    assert result["impossible_transition_rate"] == 0


def test_collinear_subdivision_preserves_the_canonical_direct_class(
    authority: ReviewedAuthority,
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    candidate = run.event.candidates[0].model_copy(update={
        "polyline": ((3., 5., 0.), (5., 5., 0.), (7., 5., 0.)),
    })
    result = evaluate_reviewed_inventory_metrics(
        _replace_candidates(run, (candidate,)), inventory, authority,
    )
    assert result["feasible_candidate_recall"] == 1
    assert result["impossible_transition_rate"] == 0


@pytest.mark.parametrize("change", [
    {"source_sha256": "a" * 64}, {"human_decisions_sha256": "a" * 64},
    {"certificate_content_sha256": "a" * 64}, {"frozen_config_sha256": "a" * 64},
    {"source_camera_calibration_content_sha256": "a" * 64},
    {"source_route_proof_content_sha256": "a" * 64},
])
def test_metric_receipts_cannot_transfer_inventory_to_other_source_or_config(
    authority: ReviewedAuthority, change: dict[str, Any],
) -> None:
    inventory, run = _inventory(authority), _run(authority)
    with pytest.raises(ValueError, match="binding differs"):
        evaluate_reviewed_inventory_metrics(run, inventory.model_copy(update=change), authority)


def test_independent_inventory_and_evaluator_never_open_files_or_import_truth(
    authority: ReviewedAuthority, monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory, run = _inventory(authority), _run(authority)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("independent metric inventory must not open any GT or recipe file")

    monkeypatch.setattr(Path, "open", forbidden)
    assert evaluate_reviewed_inventory_metrics(run, inventory, authority)[
        "feasible_candidate_recall"
    ] == 1
    assert _inventory(authority).ground_truth_read is False


def test_inventory_module_has_no_gt_recipe_or_engine_topology_dependency() -> None:
    path = Path(__file__).parents[2] / "src/amidst/finalization/reviewed_evaluation_metrics.py"
    tree = ast.parse(path.read_text())
    imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not any(name and any(token in name for token in (
        "ground_truth", "simulation", "graph.engine", "navigation.topology",
    )) for name in imported)
