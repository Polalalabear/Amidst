"""Evaluation-only decomposition after a frozen GT-free projection reference.

GT is never converted into an ObservationFrame or passed to inverse inference.
Forward(GT) residuals and true-ray/plane geometry below are post-freeze evaluation
calculations; they do not choose planes, calibration, thresholds or hypotheses.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, PilotObservationExport
from amidst.domain.evidence import VisibilityStatus
from amidst.geometry.inverse_projection import InverseProjectionService
from amidst.simulation.virtual_camera import project_world


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def freeze_projection_references(
    sources: list[dict[str, Any]],
    output: Path,
) -> list[dict[str, Any]]:
    references = []
    for source in sources:
        observed, context_path = Path(source["observations"]), Path(source["context"])
        context = PilotInferenceContext.model_validate_json(context_path.read_bytes())
        evidence = PilotObservationExport.model_validate_json(observed.read_bytes())
        if (
            context.observations_sha256 != sha256(observed)
            or evidence.source_asset_sha256 != context.source_asset_sha256
            or evidence.site_id != context.site_id
        ):
            raise ValueError("projection evaluation requires strict source/content/site binding")
        cameras = {camera.camera_id: camera for camera in context.cameras}
        if {frame.camera_id for frame in evidence.frames} != set(cameras):
            raise ValueError("projection evaluation camera set differs")
        rows = []
        for frame in evidence.frames:
            if frame.status != VisibilityStatus.OBSERVED:
                continue
            camera = cameras[frame.camera_id]
            point = InverseProjectionService(camera, context.plane).project_frame(frame)
            roundtrip = project_world(camera, point.world_position)
            rows.append(
                {
                    "camera_id": frame.camera_id,
                    "timestamp": frame.timestamp,
                    "frame_id": frame.frame_id,
                    "observed_uv": frame.point_2d,
                    "projected_position": point.world_position,
                    "inverse_forward_roundtrip_pixel_error": math.dist(
                        frame.point_2d,
                        roundtrip.point_2d,
                    )
                    if roundtrip.point_2d is not None
                    else None,
                }
            )
        references.append(
            {
                "label": PILOT_LABEL,
                "source_id": source["source_id"],
                "site_id": context.site_id,
                "source_asset_sha256": context.source_asset_sha256,
                "observations_sha256": sha256(observed),
                "context_sha256": sha256(context_path),
                "timestamps": sorted({float(frame.timestamp) for frame in evidence.frames}),
                "samples": rows,
            }
        )
    write_json(
        output / "frozen_projection_reference.json",
        {
            "label": PILOT_LABEL,
            "purpose": "GT_FREE_ACCEPTED_PROJECTION_REFERENCE",
            "ground_truth_read": False,
            "sources": references,
        },
    )
    return references


def evaluate_projection_layers(sources: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=False)
    references = freeze_projection_references(sources, output)
    frozen_path = output / "frozen_projection_reference.json"
    frozen_sha = sha256(frozen_path)
    groups, all_rows = [], []
    for source, reference in zip(sources, references, strict=True):
        # First GT access occurs only after the entire projection reference is saved.
        truth_path = Path(source["evaluation_truth"])
        truth = json.loads(truth_path.read_text())
        context = PilotInferenceContext.model_validate_json(Path(source["context"]).read_bytes())
        if (
            truth.get("label") != PILOT_LABEL
            or truth.get("provenance") != "GROUND_TRUTH"
            or truth.get("source_asset_sha256") != reference["source_asset_sha256"]
            or truth.get("site_id") != reference["site_id"]
        ):
            raise ValueError("evaluation truth label/source/site differs from frozen reference")
        if [float(row["timestamp"]) for row in truth["samples"]] != reference["timestamps"]:
            raise ValueError("evaluation truth must exactly cover original timestamps")
        cameras = {camera.camera_id: camera for camera in context.cameras}
        truth_by_time = {float(row["timestamp"]): row for row in truth["samples"]}
        normal = np.asarray(context.plane.normal, dtype=np.float64)
        plane_point = np.asarray(context.plane.point, dtype=np.float64)
        rows = []
        for sample in reference["samples"]:
            gt = truth_by_time[sample["timestamp"]]
            if gt["floor_id"] != context.zone.floor_id or (
                gt["trajectory_id"] != truth["trajectory_id"]
            ):
                raise ValueError("evaluation truth trajectory/floor differs")
            world = np.asarray(gt["position"], dtype=np.float64)
            if world.shape != (3,) or not np.isfinite(world).all():
                raise ValueError("evaluation reference must contain finite 3D positions")
            camera = cameras[sample["camera_id"]]
            origin = np.asarray(camera.camera_to_world, dtype=np.float64)[:3, 3]
            true_ray = world - origin
            denominator = float(normal @ true_ray)
            if abs(denominator) <= 1e-12:
                raise ValueError("evaluation-only true ray is parallel to diagnostic plane")
            # Evaluation-only true-ray intersection; no inverse service/GT frame.
            true_ray_plane = (
                origin + float(normal @ (plane_point - origin)) / denominator * true_ray
            )
            projected = np.asarray(sample["projected_position"], dtype=np.float64)
            forward = project_world(camera, tuple(float(v) for v in world))
            export_pixel_delta = (
                math.dist(sample["observed_uv"], forward.point_2d)
                if (forward.point_2d is not None)
                else None
            )
            rows.append(
                {
                    "label": PILOT_LABEL,
                    "purpose": "EVALUATION_ONLY_LAYER_DECOMPOSITION",
                    "source_id": source["source_id"],
                    "camera_id": sample["camera_id"],
                    "timestamp": sample["timestamp"],
                    "frame_id": sample["frame_id"],
                    "forward_export_pixel_residual": export_pixel_delta,
                    "forward_evaluation_state": forward.reason.value,
                    "gt_signed_plane_distance_scene_units": float(normal @ (world - plane_point)),
                    "plane_selection_only_error_scene_units": float(
                        np.linalg.norm(true_ray_plane - world)
                    ),
                    "export_pixel_calibration_residual_scene_units": float(
                        np.linalg.norm(projected - true_ray_plane)
                    ),
                    "total_baseline_inverse_error_vs_gt_scene_units": float(
                        np.linalg.norm(projected - world)
                    ),
                    "inverse_forward_roundtrip_pixel_error": sample[
                        "inverse_forward_roundtrip_pixel_error"
                    ],
                    "error_vector_decomposition_residual_scene_units": float(
                        np.linalg.norm(
                            (projected - world)
                            - ((projected - true_ray_plane) + (true_ray_plane - world))
                        )
                    ),
                }
            )
        numeric = (
            "forward_export_pixel_residual",
            "plane_selection_only_error_scene_units",
            "export_pixel_calibration_residual_scene_units",
            "total_baseline_inverse_error_vs_gt_scene_units",
            "inverse_forward_roundtrip_pixel_error",
            "error_vector_decomposition_residual_scene_units",
        )
        groups.append(
            {
                "source_id": source["source_id"],
                "visible_sample_count": len(rows),
                "ground_truth_sha256": sha256(truth_path),
                "metrics": {
                    key: {"mean": float(np.mean(values)), "max": max(values)}
                    for key in numeric
                    if (values := [r[key] for r in rows if r[key] is not None])
                },
            }
        )
        all_rows.extend(rows)
    if sha256(frozen_path) != frozen_sha:
        raise RuntimeError("GT evaluation changed frozen projection references")
    report = {
        "label": PILOT_LABEL,
        "purpose": "EVALUATION_ONLY_NOT_INFERENCE",
        "physical_validity": "PARTIAL_PROVISIONAL",
        "coordinate_units": "BLENDER_SCENE_UNITS",
        "gt_loaded_only_after_all_projection_frozen": True,
        "gt_pixels_never_passed_to_inverse_service": True,
        "frozen_projection_reference_sha256": frozen_sha,
        "frozen_projection_unchanged": True,
        "source_summaries": groups,
        "samples": all_rows,
        "interpretation": (
            "Export pixel/calibration residual includes independent Blender export rounding; "
            "it is not proof of a calibration bug. True-ray plane mismatch is evaluation-only."
        ),
    }
    write_json(output / "layer_evaluation.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    if inventory.get("label") != PILOT_LABEL:
        raise ValueError("layer evaluation requires a labeled pilot inventory")
    result = evaluate_projection_layers(inventory["evaluation_inputs_not_inference"], args.output)
    print(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "sample_count": len(result["samples"]),
                "frozen_projection_unchanged": result["frozen_projection_unchanged"],
            }
        )
    )


if __name__ == "__main__":
    main()
