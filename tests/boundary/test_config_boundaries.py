"""Valid extreme metric configuration and explicit invalid-configuration failures."""

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.benchmark.runner import run_benchmark
from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.metric_config import MetricConfig
from amidst.domain.search import GraphSearchPolicy
from amidst.domain.stream import AggregationPolicy
from amidst.evaluation.configured import evaluate_configured_trajectories

from .guards_helpers import (
    ROOT,
    guards_fixture,
    guards_numeric_tokens,
    guards_trajectory,
    guards_truth,
)

FIXTURE = guards_fixture("guards_config.json")


@pytest.mark.parametrize("scenario", FIXTURE["scenarios"], ids=lambda item: item["scenario_id"])
def test_metric_invalid_boundaries_fail_fast_with_field_identification(
    scenario: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError) as captured:
        MetricConfig.model_validate(guards_numeric_tokens(scenario["input"]["metric_patch"]))
    assert scenario["expected"]["failure_field"] in str(captured.value)
    assert scenario["expected"]["candidates"] == []
    assert scenario["expected"]["termination"] == "NOT_STARTED"


@pytest.mark.parametrize(
    "scenario", FIXTURE["valid_boundaries"], ids=lambda item: item["scenario_id"],
)
def test_extreme_valid_k_and_small_epsilon_never_pad_candidate_set(
    scenario: dict[str, Any],
) -> None:
    config = MetricConfig.model_validate(scenario["input"])
    trajectory = guards_trajectory()
    result = evaluate_configured_trajectories(
        (trajectory,), guards_truth(), config, constraints=ConstraintConfig(max_speed_m_s=10),
    ).for_k(config.k_values[0])
    assert result.selected_route_count == result.evaluated_hypothesis_count == 1
    assert result.top_k_hypothesis_ids == (trajectory.hypothesis_id,)
    assert result.min_ade_at_k_m == result.min_fde_at_k_m == 0
    assert result.coverage_at_k
    assert result.constraint_violation_rate == 0
    assert scenario["expected"]["candidates"] == [trajectory.candidate_id]


def test_malformed_metric_json_is_rejected_with_parse_details() -> None:
    with pytest.raises(ValidationError, match="Invalid JSON"):
        MetricConfig.model_validate_json(FIXTURE["malformed_json"]["input"]["config_text"])


@pytest.mark.parametrize(
    "scenario", FIXTURE["invalid_search_and_aggregation"], ids=lambda item: item["scenario_id"],
)
def test_negative_aggregation_and_search_limits_rejected(
    scenario: dict[str, Any],
) -> None:
    model = {
        "AggregationPolicy": AggregationPolicy,
        "GraphSearchPolicy": GraphSearchPolicy,
    }[scenario["input"]["model"]]
    with pytest.raises(ValidationError, match=scenario["expected"]["failure_field"]):
        model.model_validate(scenario["input"]["patch"])


def test_metric_version_mismatch_rejected_before_output_or_inference(tmp_path: Path) -> None:
    original = ROOT / "configs/benchmarks/mock_stream_v1.json"
    config = json.loads(original.read_text(encoding="utf-8"))
    manifest = (original.parent / config["dataset_manifest"]["path"]).resolve()
    config["dataset_manifest"]["path"] = str(manifest)
    metrics = MetricConfig().model_dump(mode="json")
    metrics["metric_config_version"] = FIXTURE["unsupported_version"]["input"][
        "metric_config_version"
    ]
    metric_bytes = (json.dumps(metrics, sort_keys=True) + "\n").encode()
    metric_path = tmp_path / "unsupported-metrics.json"
    metric_path.write_bytes(metric_bytes)
    config["metric_config"] = {
        "path": str(metric_path), "sha256": hashlib.sha256(metric_bytes).hexdigest(),
    }
    config_path = tmp_path / "experiment.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    destination = tmp_path / "must-not-exist"
    with pytest.raises(ValueError, match="metric configuration version must match the experiment"):
        run_benchmark(config_path, destination)
    assert not destination.exists()
