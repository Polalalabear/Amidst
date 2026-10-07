"""Run the additive reviewed Phase 1 inference, evaluation and reproduction stages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amidst.finalization.reviewed_pipeline import (
    compare_frozen_runs,
    evaluate_dataset,
    infer_dataset,
    verify_reproduction,
    write_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("infer", "evaluate", "verify-reproduction", "compare"))
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--application", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--inference", type=Path)
    parser.add_argument("--other-inference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reordered", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.stage == "compare":
        if args.inference is None or args.other_inference is None:
            parser.error("comparison requires --inference and --other-inference")
        result = compare_frozen_runs(args.inference, args.other_inference)
        write_json(args.output, result)
        print(json.dumps(result))
        return
    if args.dataset is None or args.application is None:
        parser.error("execution requires --dataset and --application")
    if args.stage == "infer":
        if args.config is None:
            parser.error("inference requires --config")
        result = infer_dataset(args.dataset, args.application, args.config, args.output,
                               repo_root=root, reordered=args.reordered)
    elif args.stage == "evaluate":
        if args.inference is None:
            parser.error("evaluation requires --inference")
        result = evaluate_dataset(args.dataset, args.inference, args.application, args.output,
                                  repo_root=root)
    else:
        if args.inference is None or args.config is None:
            parser.error("reproduction requires --inference and --config")
        result = verify_reproduction(args.dataset, args.inference, args.application, args.config,
                                     args.output, repo_root=root)
    print(json.dumps({"status": result["status"]}))


if __name__ == "__main__":
    main()
