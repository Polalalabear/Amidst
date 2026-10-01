"""Run the generic downstream pipeline from replaceable strict inference JSON."""

import argparse
from pathlib import Path

from amidst.debug.runner import run_experiment
from amidst.domain.evaluation import ConstraintConfig, EvaluationConfig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path,
                        help="evaluation/debug only, loaded after reconstruction")
    parser.add_argument("--output", type=Path, required=True, help="fresh output directory")
    parser.add_argument("--k", type=int, default=3, help="distinct primary routes for evaluation")
    parser.add_argument("--coverage-epsilon-m", type=float, default=1e-6)
    parser.add_argument("--no-rerun", action="store_true")
    parser.add_argument("--constraints", type=Path,
                        help="explicit physical evaluation config, including optional AABBs")
    args = parser.parse_args()
    result, event, metrics = run_experiment(
        args.input, args.output, ground_truth_path=args.ground_truth,
        evaluation_config=EvaluationConfig(
            k_routes=args.k, coverage_epsilon_m=args.coverage_epsilon_m,
        ), record_rerun=not args.no_rerun,
        constraints=(ConstraintConfig.model_validate_json(args.constraints.read_text())
                     if args.constraints else None),
    )
    print(f"{result.termination_reason}: {len(result.candidates)} routes, "
          f"{len(event.trajectories)} timed hypotheses")
    if metrics is not None:
        print(f"minADE@K={metrics.min_ade_at_k_m}, minFDE@K={metrics.min_fde_at_k_m}, "
              f"Coverage@K={metrics.coverage_at_k}")


if __name__ == "__main__":
    main()
