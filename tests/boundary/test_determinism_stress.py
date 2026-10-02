"""Process/hash/random/output-directory changes preserve adversarial run semantics."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from amidst.benchmark.runner import run_benchmark

from .benchmark_helpers import (
    graph_benchmark_config,
    inference_semantics,
    read_json,
    report_semantics,
)

PROCESS = """
import json, os, random, sys
from pathlib import Path
from amidst.benchmark.runner import run_benchmark
random.seed(int(os.environ['PYTHONHASHSEED']))
result = run_benchmark(Path(sys.argv[1]), Path(sys.argv[2]), search_clock=lambda: 0.0)
cases = [{'case_id': case.case_id, 'aggregation': case.aggregation.model_dump(mode='json'),
          'gaps': [gap.gap.model_dump(mode='json') for gap in case.gaps]}
         for case in result.cases]
print(json.dumps(cases, sort_keys=True))
"""


def test_repeat_processes_hash_seeds_and_directories_preserve_top_k_and_failure(
    tmp_path: Path,
) -> None:
    for fixture in ("eight_routes_k3", "equal_distance_ties", "uncited_navigation_bridge"):
        config = graph_benchmark_config(tmp_path / fixture / "input", fixture)
        original_output = tmp_path / fixture / "original"
        original = run_benchmark(config, original_output, search_clock=lambda: 0.0)
        expected = inference_semantics(original)
        expected_report = report_semantics(original_output)
        expected_metrics = read_json(original_output / "metrics.json")
        for run in range(3):
            output = tmp_path / fixture / f"same-process-{run}"
            repeated = run_benchmark(config, output, search_clock=lambda: 0.0)
            assert inference_semantics(repeated) == expected
            assert report_semantics(output) == expected_report
            assert read_json(output / "metrics.json") == expected_metrics
        for seed in (1, 17, 101):
            output = tmp_path / fixture / f"process-{seed}"
            workdir = tmp_path / fixture / f"workdir-{seed}"
            workdir.mkdir()
            process = subprocess.run(
                [sys.executable, "-c", PROCESS, str(config), str(output)],
                env=dict(os.environ, PYTHONHASHSEED=str(seed)),
                cwd=workdir, capture_output=True, text=True, check=True, timeout=20,
            )
            assert json.loads(process.stdout) == expected
            assert report_semantics(output) == expected_report
            assert read_json(output / "metrics.json") == expected_metrics
