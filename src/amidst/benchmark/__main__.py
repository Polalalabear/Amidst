"""Run a content-bound experiment with optional Rerun recording."""

import argparse
from pathlib import Path

from amidst.benchmark.runner import run_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="fresh output directory")
    recording = parser.add_mutually_exclusive_group()
    recording.add_argument("--rerun", action="store_const", const=True, default=None)
    recording.add_argument("--no-rerun", action="store_const", const=False, dest="rerun")
    parser.add_argument("--debug-ground-truth", action="store_const", const=True, default=None)
    args = parser.parse_args()
    result = run_benchmark(args.config, args.output, record_rerun=args.rerun,
                           debug_ground_truth=args.debug_ground_truth)
    gap_count = sum(len(case.gaps) for case in result.cases)
    print(f"{result.record.config.experiment_id}: {len(result.cases)} cases, {gap_count} gaps")
    print(f"Results: {args.output.resolve()}")


if __name__ == "__main__":
    main()
