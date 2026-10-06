"""Refuse unavailable comparison factors without changing inference contracts."""

import json
from pathlib import Path

import pytest
from test_physical_collision import SOURCE, _consumer, _wall

from amidst.benchmark.baselines import (
    BaselineUnavailableError,
    ablation_capabilities,
    baseline_capabilities,
    baseline_capability_manifest,
    require_supported_baseline,
    run_baseline,
)
from amidst.pipeline import reconstruct_input
from amidst.simulation.mock_scenarios import scenario_inputs

ROOT = Path(__file__).resolve().parents[2]


def test_capability_masks_match_existing_protocol_and_do_not_claim_measurements() -> None:
    protocol = json.loads((ROOT / "configs/benchmarks/protocol_v1.json").read_text())
    declared = {item["id"]: item for item in protocol["baselines"]}
    for capability in baseline_capabilities():
        definition = declared[capability.baseline_id]
        assert capability.method_id == definition["method_id"]
        if capability.required_mask is not None:
            assert capability.required_mask.travel_time_filter == definition["travel_time_filter"]
            assert capability.required_mask.camera_topology_filter == (
                definition["camera_topology_filter"]
            )
            assert capability.required_mask.collision_filter
        assert not capability.formal_available
    ablations = {item["id"]: item for item in protocol["ablations"]}
    for capability in ablation_capabilities():
        assert capability.changed_factor == ablations[capability.ablation_id]["changed_factor"]
        assert capability.reference_method == ablations[capability.ablation_id]["reference_method"]
    manifest = baseline_capability_manifest()
    assert not manifest["formal_execution_enabled"]
    assert not manifest["inference_executed"]
    assert not manifest["gt_read"]
    assert json.dumps(manifest, sort_keys=True) == json.dumps(
        baseline_capability_manifest(), sort_keys=True,
    )


def test_ab_preserves_geometric_routes_without_speed_time_or_topology_substitution() -> None:
    inputs = next(item for item in scenario_inputs() if item.dataset_id == "branching_top_k")
    data = inputs.model_dump(mode="python")
    data["movement"]["max_speed_m_s"] = 0.1
    data["topology"]["transitions"] = ()
    inputs = type(inputs).model_validate(data)
    before = inputs.model_dump_json()
    shortest = run_baseline(inputs, "shortest_path", clock=lambda: 0.0)
    geometry = run_baseline(inputs, "geometry", clock=lambda: 0.0)
    full = run_baseline(inputs, "spatiotemporal", clock=lambda: 0.0)
    assert inputs.model_dump_json() == before
    assert shortest.requested_k == geometry.requested_k == full.requested_k == 3
    assert len(shortest.geometric_result.routes) == 1
    assert len(geometry.geometric_result.routes) == 3
    assert not full.geometric_result.routes
    assert len(shortest.timing_unavailable_route_ids) == 1
    assert len(geometry.timing_unavailable_route_ids) == 3
    assert not shortest.event.trajectories and not geometry.event.trajectories
    assert shortest.timed_metrics_status == geometry.timed_metrics_status == (
        "N/A_TIMING_UNAVAILABLE"
    )
    assert all(route.minimum_travel_time > route.observed_gap_duration
               for route in geometry.geometric_result.routes)
    assert all(result.physical_status == "N/A" for result in (shortest, geometry, full))


def test_missing_timing_does_not_compress_geometric_top_k_for_accuracy_metrics() -> None:
    inputs = next(item for item in scenario_inputs() if item.dataset_id == "branching_top_k")
    data = inputs.model_dump(mode="python")
    data["movement"]["max_speed_m_s"] = 0.75
    inputs = type(inputs).model_validate(data)
    result = run_baseline(inputs, "geometry", clock=lambda: 0.0)
    assert len(result.geometric_result.routes) == 3
    assert len(result.timed_result.candidates) == 2
    assert len(result.timing_unavailable_route_ids) == 1
    assert result.timed_metrics_status == "N/A_TIMING_UNAVAILABLE"


@pytest.mark.parametrize("ablation_id", [
    "add_semantic_information", "add_agent_ranking",
])
def test_unimplemented_single_factor_masks_refuse(ablation_id: str) -> None:
    with pytest.raises(BaselineUnavailableError):
        require_supported_baseline("spatiotemporal", ablation_id=ablation_id)


def test_current_c_diagnostic_support_does_not_authorize_full_physical_formal_run() -> None:
    capability = require_supported_baseline("spatiotemporal")
    assert capability.current_mask is not None
    assert capability.current_mask.travel_time_filter
    assert capability.current_mask.camera_topology_filter
    assert not capability.current_mask.collision_filter
    with pytest.raises(BaselineUnavailableError) as failure:
        require_supported_baseline("spatiotemporal", formal=True)
    assert "APPROVED_CASE_LOCAL_PHYSICAL_SCOPE_REQUIRED" in failure.value.reasons


def test_existing_shortest_only_diagnostic_keeps_inputs_and_primary_order() -> None:
    require_supported_baseline("spatiotemporal", ablation_id="shortest_path_only")
    inputs = next(item for item in scenario_inputs() if item.dataset_id == "branching_top_k")
    before = inputs.model_dump_json()
    full, full_event = reconstruct_input(inputs, clock=lambda: 0.0)
    shortest, shortest_event = reconstruct_input(inputs, max_paths=1, clock=lambda: 0.0)
    assert inputs.model_dump_json() == before
    assert shortest.candidates == full.candidates[:1]
    assert len(full.candidates) == 3
    assert len(shortest.candidates) == 1
    assert shortest_event.time_range == full_event.time_range
    assert shortest_event.candidates[0].feasibility_flags == (
        full_event.candidates[0].feasibility_flags
    )


def test_adapters_match_default_c_and_keep_single_factor_ablation_masks() -> None:
    inputs = next(item for item in scenario_inputs() if item.dataset_id == "branching_top_k")
    expected, expected_event = reconstruct_input(inputs, clock=lambda: 0.0)
    full = run_baseline(inputs, "spatiotemporal", clock=lambda: 0.0)
    assert full.timed_result == expected and full.event == expected_event
    time_removed = run_baseline(
        inputs, "spatiotemporal", ablation_id="remove_travel_time", clock=lambda: 0.0,
    )
    topology_removed = run_baseline(
        inputs, "spatiotemporal", ablation_id="remove_topology", clock=lambda: 0.0,
    )
    assert not time_removed.factors.travel_time_filter
    assert time_removed.factors.camera_topology_filter
    assert topology_removed.factors.travel_time_filter
    assert not topology_removed.factors.camera_topology_filter
    with pytest.raises(BaselineUnavailableError, match="APPROVED_COLLISION_CONSUMER"):
        run_baseline(inputs, "spatiotemporal", ablation_id="remove_collision")


def test_ab_ranking_independent_of_configuration_input_order() -> None:
    inputs = next(item for item in scenario_inputs() if item.dataset_id == "branching_top_k")
    data = inputs.model_dump(mode="python")
    data["navigation"]["edges"] = tuple(reversed(data["navigation"]["edges"]))
    data["navigation"]["nodes"] = tuple(reversed(data["navigation"]["nodes"]))
    data["topology"]["transitions"] = tuple(reversed(data["topology"]["transitions"]))
    reversed_inputs = type(inputs).model_validate(data)
    for method in ("shortest_path", "geometry", "spatiotemporal"):
        assert run_baseline(inputs, method, clock=lambda: 0.0) == run_baseline(
            reversed_inputs, method, clock=lambda: 0.0,
        )


def test_approved_partial_collision_filter_runs_before_shortest_route_truncation() -> None:
    inputs = next(item for item in scenario_inputs() if item.dataset_id == "branching_top_k")
    data = inputs.model_dump(mode="python")
    data["navigation"]["source_asset_sha256"] = SOURCE
    data["topology"]["source_asset_sha256"] = SOURCE
    inputs = type(inputs).model_validate(data)
    wall = _wall(10.0)
    wall["vertices"] = [[10.0, -1.0, -1.0], [10.0, 1.0, -1.0],
                        [10.0, 1.0, 4.0], [10.0, -1.0, 4.0]]
    consumer = _consumer([wall])
    filtered = run_baseline(inputs, "shortest_path", collision_consumer=consumer,
                            clock=lambda: 0.0)
    assert len(filtered.geometric_result.routes) == 1
    assert filtered.geometric_result.routes[0].navmesh_corridor == ("upper",)
    assert filtered.physical_records[0].state == "REJECTED"
    assert any(record.state == "RETAINED" for record in filtered.physical_records)
    assert filtered.physical_status == "PARTIAL_APPROVED"
    removed = run_baseline(inputs, "spatiotemporal", ablation_id="remove_collision",
                           collision_consumer=consumer, clock=lambda: 0.0)
    assert removed.geometric_result.routes[0].navmesh_corridor == ("direct",)
    assert not removed.physical_records
    assert removed.physical_status == "N/A"


def test_physical_approval_cannot_be_transferred_to_another_source_asset() -> None:
    inputs = next(item for item in scenario_inputs() if item.dataset_id == "branching_top_k")
    with pytest.raises(ValueError, match="same navigation source asset"):
        run_baseline(inputs, "geometry", collision_consumer=_consumer([_wall(10.0)]))


@pytest.mark.parametrize("method_id,ablation_id", [
    ("invented", None), ("spatiotemporal", "invented"),
    ("semantic", None), ("agent", None),
])
def test_unknown_and_interface_only_requests_refuse(
    method_id: str, ablation_id: str | None,
) -> None:
    with pytest.raises(BaselineUnavailableError):
        require_supported_baseline(method_id, ablation_id=ablation_id)
