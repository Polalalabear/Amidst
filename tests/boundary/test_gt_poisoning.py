"""Adversarial truth is evaluation-only, including implausible speed and floor."""

from __future__ import annotations

from pathlib import Path

import pytest

from amidst.benchmark.runner import run_benchmark

from .benchmark_helpers import (
    BOUNDARY,
    FIXTURES,
    custom_config,
    inference_semantics,
    read_json,
)

PATTERNS = tuple(read_json(BOUNDARY / "benchmark_cases.json")["poison_patterns"])


@pytest.mark.parametrize("pattern", PATTERNS)
def test_poisoned_truth_changes_only_evaluation(pattern: str, tmp_path: Path) -> None:
    spec = read_json(BOUNDARY / "benchmark_cases.json")["poison_patterns"][pattern]
    truth = read_json(FIXTURES / "branching_top_k/ground_truth.json")
    for index, sample in enumerate(truth["samples"]):
        if "position_offset" in spec:
            sample["position"] = [
                value + delta
                for value, delta in zip(sample["position"], spec["position_offset"], strict=True)
            ]
        if "alternating_x" in spec:
            sample["position"][0] = spec["alternating_x"][index % 2]
            sample["velocity"] = spec["velocity"]
        if "z" in spec:
            sample["position"][2] = spec["z"]
            sample["floor_id"] = spec["floor_id"]
        if "cycle" in spec:
            sample["position"] = spec["cycle"][index % len(spec["cycle"])][:]
    clean_config = custom_config(tmp_path / "clean-input", base_case="branching_top_k")
    poison_config = custom_config(
        tmp_path / "poison-input", base_case="branching_top_k", truth=truth,
    )
    clean = run_benchmark(clean_config, tmp_path / "clean", search_clock=lambda: 0.0)
    poisoned = run_benchmark(poison_config, tmp_path / "poisoned", search_clock=lambda: 0.0)
    assert inference_semantics(clean) == inference_semantics(poisoned)
    clean_metrics = clean.cases[0].gaps[0].evaluation
    poison_metrics = poisoned.cases[0].gaps[0].evaluation
    assert clean_metrics is not None and poison_metrics is not None
    assert clean_metrics.for_k(3).coverage_at_k
    assert not poison_metrics.for_k(3).coverage_at_k
    assert clean_metrics.for_k(3).min_ade_at_k_m != poison_metrics.for_k(3).min_ade_at_k_m
    for original, altered in zip(
        clean_metrics.for_k(3).trajectory_metrics,
        poison_metrics.for_k(3).trajectory_metrics,
        strict=True,
    ):
        assert original.candidate_id == altered.candidate_id
        assert original.hypothesis_id == altered.hypothesis_id
        assert original.physical == altered.physical
    unavailable_config = custom_config(tmp_path / "no-gt-input", base_case="branching_top_k",
                                       no_truth=True)
    unavailable = run_benchmark(unavailable_config, tmp_path / "no-gt", search_clock=lambda: 0.0)
    assert inference_semantics(clean) == inference_semantics(unavailable)
    assert unavailable.cases[0].gaps[0].evaluation is None
