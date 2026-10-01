"""Export a configurable synthetic path evaluated in a transient Blender scene."""

from __future__ import annotations

import argparse
from pathlib import Path

from amidst.domain.ground_truth import TrajectoryConfig
from amidst.simulation.ground_truth import (
    blender_evaluated_trajectory,
    export_ground_truth_csv,
    export_ground_truth_json,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--json", type=Path, required=True, help="Simulation-only ground-truth JSON"
    )
    parser.add_argument("--csv", type=Path, help="Optional simulation-only ground-truth CSV")
    parser.add_argument("--blender-bin", help="Blender CLI path (otherwise BLENDER_BIN/PATH)")
    parser.add_argument(
        "--blend", type=Path, help="Optional read-only scene; default factory scene"
    )
    parser.add_argument("--frame-rate-hz", type=float, default=30.0)
    parser.add_argument("--max-samples", type=int, default=1_000_000)
    parser.add_argument(
        "--overwrite", action="store_true", help="Explicitly allow output replacement"
    )
    args = parser.parse_args()
    outputs = [path for path in (args.json, args.csv) if path is not None]
    if args.json.suffix.lower() != ".json" or args.json.resolve().suffix.lower() != ".json":
        parser.error("JSON output must use a .json destination; Blender assets are immutable")
    if args.csv is not None and (
        args.csv.suffix.lower() != ".csv" or args.csv.resolve().suffix.lower() != ".csv"
    ):
        parser.error("CSV output must use a .csv destination; Blender assets are immutable")
    inputs = {path.resolve() for path in (args.config, args.blend) if path is not None}
    if any(path.resolve() in inputs for path in outputs):
        parser.error("Output destinations must not overwrite configuration or Blender inputs")
    if len({path.resolve() for path in outputs}) != len(outputs):
        parser.error("JSON and CSV output paths must be different")
    if not args.overwrite and any(path.exists() for path in outputs):
        parser.error("An output already exists; use a new destination or --overwrite")
    config = TrajectoryConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
    trajectory = blender_evaluated_trajectory(
        config,
        blender_binary=args.blender_bin,
        blend_path=args.blend,
        frame_rate_hz=args.frame_rate_hz,
        max_samples=args.max_samples,
    )
    export_ground_truth_json(trajectory, args.json, overwrite=args.overwrite)
    if args.csv is not None:
        export_ground_truth_csv(trajectory, args.csv, overwrite=args.overwrite)
    print(f"Exported {len(trajectory.samples)} BLENDER_EVALUATED SYNTHETIC samples to {args.json}")


if __name__ == "__main__":
    main()
