"""Guard the distinction between unapproved research settings and executable fixtures."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from amidst.domain.metric_config import MetricConfig

REPOSITORY = Path(__file__).resolve().parents[2]
PROTOCOL = REPOSITORY / "configs/benchmarks/protocol_v1.json"


def test_formal_protocol_cannot_promote_fixture_settings_to_approved_research() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["kind"] == "PROTOCOL_SPECIFICATION_NOT_EXPERIMENT_CONFIG"
    assert not protocol["formal_execution_enabled"]
    assert protocol["status"] == "UNRESOLVED_RESEARCH_SETTING"
    assert {
        "SOURCE_BOUND_HUMAN_APPROVED_WALKABLE_AND_COLLIDER_GEOMETRY",
        "APPROVED_FLOOR_PLANES_AND_CAMERA_PLANE_BINDING",
        "APPROVED_CLEARANCE_CONTACT_AND_OBSTACLE_OWNERSHIP",
        "APPROVED_FORMAL_METRIC_CONFIG",
        "FROZEN_BASELINE_AND_ABLATION_PROTOCOL",
        "GROUND_TRUTH_ISOLATED_FROM_INFERENCE_AND_RANKING",
    } <= set(protocol["execution_gates"])
    settings = protocol["coverage"]["formal_settings"]
    assert settings.pop("status") == "UNRESOLVED_RESEARCH_SETTING"
    assert all(value is None for value in settings.values())
    assert all(item["value"] is None for item in protocol["unresolved_settings"])
    assert not protocol["acceptance"]["synthetic_zero_error_is_formal_evidence"]


def test_protocol_coverage_constraints_agree_with_supported_regression_metric_config() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    coverage = protocol["coverage"]
    profile = coverage["synthetic_regression_profile"]
    config_path = PROTOCOL.parent / profile["metric_config_path"]
    config = MetricConfig.model_validate_json(config_path.read_text())
    assert not profile["formal_setting_approved"]
    assert profile["distance_metric"] == config.trajectory_distance_metric
    assert profile["epsilon"] == config.coverage_epsilon_m
    assert profile["k_values"] == list(config.k_values)
    assert profile["temporal_alignment_policy"] == config.temporal_alignment_policy
    assert profile["interpolation_policy"] == config.interpolation_policy
    assert coverage["comparison"] == config.coverage_comparison == "STRICTLY_LESS_THAN"
    assert coverage["parameter_constraints"]["epsilon"]["exclusiveMinimum"] == 0
    for epsilon in (0.0, -0.1, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            MetricConfig.model_validate(config.model_dump() | {"coverage_epsilon_m": epsilon})
    for values in ((0,), (-1,), (1, 1), ()):
        with pytest.raises(ValidationError):
            MetricConfig.model_validate(config.model_dump() | {"k_values": values})


def test_cases_and_acceptance_categories_cover_the_metric_contract_without_execution() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    metrics = protocol["metric_protocol"]["definitions"]
    cases = {item["case_id"]: item for item in protocol["cases"]}
    assert set(cases) == {"case1", "case2", "case3", "case4"}
    for case in cases.values():
        for dimension in (
            "research_question", "required_scene_semantics", "expected_observations",
            "expected_ambiguity", "required_metrics", "failure_conditions",
        ):
            assert case[dimension]
        assert set(case["required_metrics"]) == set(metrics)
    assert cases["case4"]["execution_status"] == "DEFERRED_NOT_EXECUTED_THIS_ROUND"
    categories = protocol["acceptance"]["categories"]
    assert set(categories) == {
        "GEOMETRIC_ACCURACY", "PHYSICAL_VALIDITY", "TOP_K_COVERAGE",
        "TEMPORAL_VALIDITY", "SEARCH_BEHAVIOR", "SYSTEM_RUNTIME",
    }
    assert {metric for members in categories.values() for metric in members} == set(metrics)
    for metric_id, metric in metrics.items():
        assert metric_id in categories[metric["category"]]
    assert not protocol["acceptance"]["overall_pass_fail"]
    assert all(item["status"] == "INITIAL_TARGET"
               for item in protocol["acceptance"]["initial_targets"])


def test_baseline_and_ablation_contract_preserves_controlled_comparison() -> None:
    protocol = json.loads(PROTOCOL.read_text())
    baselines = {item["id"]: item for item in protocol["baselines"]}
    assert set(baselines) == set("ABCDE")
    assert len({item["method_id"] for item in baselines.values()}) == len(baselines)
    assert baselines["D"]["status"] == "INTERFACE_ONLY_NOT_IMPLEMENTED"
    assert baselines["E"]["status"] == "INTERFACE_ONLY_NOT_IMPLEMENTED_AGENT_NOT_STARTED"
    assert baselines["D"]["semantic_policy"] is baselines["E"]["agent_policy"] is None
    comparison = protocol["comparison"]
    assert comparison["single_factor_ablation"]
    assert not comparison["order_by_ground_truth"]
    assert {
        "dataset_content_and_case_gap_ids", "seed", "metric_config_content",
        "candidate_k_values", "evaluation_reference",
    } <= set(comparison["invariants"])
    assert "SUPPRESS_AGGREGATE_NULL_AND_FLAG_REVIEW" in (
        comparison["incompatible_dataset_seed_metric_or_requested_k"]
    )
    factors = [item["changed_factor"] for item in protocol["ablations"]
               if item.get("role") != "REFERENCE"]
    assert all(isinstance(factor, str) for factor in factors)
    assert len(set(factors)) == len(factors)
