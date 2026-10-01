"""Versioned dataset benchmark orchestration, separate from inference consumers."""

from amidst.benchmark.runner import BenchmarkResult, run_benchmark

__all__ = ["BenchmarkResult", "run_benchmark"]
