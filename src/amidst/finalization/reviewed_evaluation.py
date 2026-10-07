"""Evaluation-only reviewed adapters; primary inference must freeze before use."""

import math
from itertools import pairwise
from typing import Any

from amidst.domain.evaluation import ConstraintConfig
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.domain.trajectory import Event
from amidst.evaluation.configured import evaluate_configured_trajectories
from amidst.finalization.reviewed_authority import (
    ReviewedAuthority,
    ReviewedMetricConfig,
    reviewed_metric_config,
    reviewed_physical_metrics,
)


def evaluate_reviewed_trajectories(
    event: Event, ground_truth: GroundTruthTrajectory, metric_config: ReviewedMetricConfig, *,
    constraints: ConstraintConfig, authority: ReviewedAuthority,
) -> dict[str, Any]:
    """Retain core metric semantics and expose the distinct reviewed physical proof."""
    expected = reviewed_metric_config(authority)
    if ReviewedMetricConfig.model_validate(metric_config.model_dump()) != expected:
        raise ValueError("reviewed metric config differs from original approved values")
    reference = GroundTruthTrajectory.model_validate(ground_truth.model_dump())
    if (
        reference.source_asset_sha256 != authority.source_sha256
        or reference.sample_rate_hz != metric_config.sampling_hz
        or reference.target_id != event.target_id
        or constraints.max_speed_m_s != authority.approved_input_lock["timing"]["max_speed_m_s"]
        or any(not math.isclose(after.timestamp - before.timestamp, 1 / metric_config.sampling_hz,
                                rel_tol=0, abs_tol=1e-10)
               for before, after in pairwise(reference.samples))
    ):
        raise ValueError("reviewed evaluation reference source/sampling/target binding differs")
    result = evaluate_configured_trajectories(
        event.trajectories, reference, metric_config.computation_config, constraints=constraints,
    )
    return {
        "schema_version": "phase1-reviewed-evaluation-v1", "result_type": "FORMAL",
        "metric_authority": metric_config.model_dump(mode="json"),
        "computation_result": result.model_dump(mode="json"),
        "reviewed_physical": reviewed_physical_metrics(event, authority),
        "core_synthetic_labels_preserved": True,
        "core_aabb_metrics_are_school_collision_authority": False,
    }
