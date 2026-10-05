"""Consume one existing Blender pilot through GT-free ordinary downstream APIs."""

from __future__ import annotations

import argparse
from pathlib import Path

from amidst.datasets.pilot import run_pilot_downstream


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True,
                        help="existing sanitized observations.json only")
    parser.add_argument("--context", type=Path, required=True,
                        help="strict GT-free camera/plane/annotation context")
    parser.add_argument("--output", type=Path, required=True, help="fresh output directory")
    parser.add_argument("--lateral-offset-scene-units", type=float, default=12.0)
    parser.add_argument("--max-speed-scene-units-s", type=float, default=32.0)
    parser.add_argument("--max-candidate-paths", type=int, default=3)
    parser.add_argument("--random-seed", type=int, default=42)
    args = parser.parse_args()
    run = run_pilot_downstream(
        args.observations, args.context, args.output,
        lateral_offset_scene_units=args.lateral_offset_scene_units,
        max_speed_scene_units_s=args.max_speed_scene_units_s,
        max_candidate_paths=args.max_candidate_paths, random_seed=args.random_seed,
    )
    print(f"PILOT / SYNTHETIC SAMPLE: {run.report['candidate_count']} routes / "
          f"{run.report['hypothesis_count']} timed hypotheses; "
          f"{run.report['termination_reason']}; no truth read")


if __name__ == "__main__":
    main()
