"""Local product materialization, operation and independent evaluation."""

import argparse
import json
from pathlib import Path

from amidst.product.api import serve
from amidst.product.investigation import InvestigationIntent
from amidst.product.operator import OperatorWorkspace
from amidst.product.run import build_product, load_product


def main() -> None:
    parser = argparse.ArgumentParser(description="Amidst local synthetic Phase 2 operator product")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--source", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--video-pool", type=Path, required=True)
    for name in ("serve", "demo", "evaluate"):
        command = commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name == "serve":
            command.add_argument("--port", type=int, default=8020)
    args = parser.parse_args()
    if args.command == "build":
        manifest = build_product(args.source, args.output, video_pool=args.video_pool)
        print(json.dumps({"status": "FROZEN_LOCAL_PRODUCT", "manifest_sha256":
                          manifest.manifest_sha256, "modes": [m.product_freeze_ref
                                                              for m in manifest.modes]}))
    elif args.command == "serve":
        with load_product(args.output) as runtime:
            serve(runtime, args.port)
    elif args.command == "evaluate":
        from amidst.product.evaluation import evaluate_product
        print(json.dumps(evaluate_product(args.output), indent=2))
    else:
        with load_product(args.output) as runtime:
            results: list[dict[str, object]] = []
            for service in runtime.services:
                camera = next(iter(service.base.cameras.values()))
                observations = service.call("query_observations", {
                    "session_ref": service.context().session_ref, "camera_ref": camera.camera_ref,
                    "time_range": [0, 24]})["items"]
                seeds = tuple(item["observation_ref"] for item in observations[:2])
                if not seeds:
                    results.append({"status": "EMPTY_STARTING_OBSERVATIONS"})
                    continue
                workspace = OperatorWorkspace(service)
                compiled = workspace.compile(InvestigationIntent(
                    task="MULTI_TARGET" if len(seeds) == 2 else "TRACE",
                    camera_ref=camera.camera_ref, time_range=(0, 24), seed_refs=seeds))
                assert compiled.plan is not None
                case = workspace.execute(compiled.plan.plan_ref)
                report = workspace.report(compiled.plan.plan_ref)
                results.append({"context": service.context().model_dump(mode="json"),
                    "plan_ref": compiled.plan.plan_ref, "state": case.state,
                    "tool_calls": len(case.receipts), "subjects": len(case.subjects),
                    "report": report.model_dump(mode="json")})
            print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
