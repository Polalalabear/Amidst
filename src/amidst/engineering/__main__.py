"""Explicit build versus frozen read/demo; no external model provider."""

import argparse
import json
from pathlib import Path

from amidst.engineering.api import serve
from amidst.engineering.run import load_facades, materialize_run, mock_agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Amidst local synthetic engineering")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="generate RGB and freeze independent mode runs")
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--run-id", required=True)
    build.add_argument("--config", type=Path,
                       default=Path("configs/engineering/simulation_v1.json"))
    for name in ("serve", "demo", "evaluate", "export-demo"):
        command = commands.add_parser(name)
        command.add_argument("--run", type=Path, required=True)
        if name == "serve":
            command.add_argument("--port", type=int, default=8010)
            command.add_argument("--storage", choices=("MEMORY", "LOCAL_JSON"),
                                 default="LOCAL_JSON")
    args = parser.parse_args()
    if args.command == "build":
        receipt = materialize_run(args.output, args.config, run_id=args.run_id)
        print(json.dumps({"run_id": receipt.scope.run_id,
                          "registry_sha256": receipt.registry_sha256,
                          "freeze_hashes": [r.receipt_sha256 for r in receipt.receipts]}))
    elif args.command == "serve":
        serve(load_facades(args.run, storage=args.storage), args.port)
    elif args.command == "demo":
        print(json.dumps([mock_agent(f) for f in load_facades(args.run)], indent=2))
    elif args.command == "evaluate":
        from amidst.engineering.evaluation import evaluate_frozen_run
        print(json.dumps(evaluate_frozen_run(args.run), indent=2))
    elif args.command == "export-demo":
        from amidst.engineering.evaluation import export_inference_demo
        print(json.dumps(export_inference_demo(args.run), indent=2))


if __name__ == "__main__":
    main()
