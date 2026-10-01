"""Export 2D-only camera evidence; simulation truth is never embedded in output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amidst.domain.camera import Camera
from amidst.domain.common import Vec3
from amidst.domain.ground_truth import GroundTruthTrajectory
from amidst.simulation.observation_export import (
    GEOMETRY_POLICY,
    _fingerprint,
    blender_ray_queries,
    observe_trajectory,
)
from amidst.simulation.raycast_types import RaycastResult
from amidst.storage.json_files import write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--cameras", type=Path, required=True)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--blender-bin")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    protected = tuple(
        path for path in (args.ground_truth, args.cameras, args.blend) if path is not None
    )
    if args.output.resolve() in {path.resolve() for path in protected}:
        parser.error("output must not replace an input")
    if args.output.suffix.lower() != ".json" or args.output.resolve().suffix.lower() != ".json":
        parser.error("output must be .json")
    if args.output.exists() and not args.overwrite:
        parser.error("output already exists")
    truth = GroundTruthTrajectory.model_validate_json(args.ground_truth.read_text())
    catalog = json.loads(args.cameras.read_text())
    scene_hash = _fingerprint(args.blend)[0]
    if truth.source_asset_sha256 != scene_hash or catalog.get("source_asset_sha256") != scene_hash:
        parser.error(
            "Ground Truth, camera catalog and visibility geometry must share a source hash"
        )
    cameras = tuple(Camera.model_validate(row) for row in catalog["cameras"])
    if truth.sample_source != "BLENDER_EVALUATED":
        parser.error("observation export requires Blender-evaluated synthetic truth")
    queries: list[tuple[Vec3, Vec3]] = []

    def gather(origin: Vec3, target: Vec3) -> RaycastResult:
        queries.append((origin, target))
        return RaycastResult(False, "CLEAR")

    observe_trajectory(truth, cameras, gather)
    answers = iter(
        blender_ray_queries(tuple(queries), blend_path=args.blend, blender_binary=args.blender_bin)
    )

    def replay(origin: Vec3, target: Vec3) -> RaycastResult:
        return next(answers)

    frames = observe_trajectory(truth, cameras, replay)
    write_json(
        args.output,
        {
            "data_kind": "SYNTHETIC",
            "scene_id": truth.scene_id,
            "geometry_policy": GEOMETRY_POLICY,
            "frames": [frame.model_dump(mode="json") for frame in frames],
        },
        overwrite=args.overwrite,
        protected_inputs=protected,
    )
    print(f"Exported {len(frames)} sanitized synthetic frames to {args.output}")


if __name__ == "__main__":
    main()
