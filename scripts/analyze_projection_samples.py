"""PILOT pixel/calibration sensitivity relative to an existing PROJECTED baseline.

Only strict 2D evidence and independently bound context are read. RMS/max values
measure displacement from PROJECTED baseline, not Ground Truth accuracy. Native
Blender scene units have PROVISIONAL scale; no inference/graph/benchmark is run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, PilotObservationExport
from amidst.domain.camera import Camera
from amidst.domain.evidence import ObservationFrame, VisibilityStatus
from amidst.domain.geometry import Plane
from amidst.geometry.inverse_projection import InverseProjectionError, InverseProjectionService

AMPLITUDES = (0.0, 0.001, 0.002, 0.003, 0.004, 0.005, 0.05, 0.1, 0.25, 0.5, 1.0)
SEEDS = (20261006, 42, 20261007)
REFERENCE = "DISPLACEMENT_FROM_EXISTING_PROJECTED_BASELINE_NOT_GT_ACCURACY"
GEOMETRY_JACOBIAN_KEY = "analytic_scene_units_per_pixel"
GEOMETRY_INCIDENCE_KEY = "normalized_incidence"
GEOMETRY_DISTANCE_KEY = "intersection_euclidean_distance_scene_units"
GEOMETRY_JNORM_KEY = "max_scene_units_per_pixel"


def _helper() -> Any:
    path = Path(__file__).with_name("projection_conditioning.py")
    spec = importlib.util.spec_from_file_location("pilot_projection_conditioning", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("projection conditioning helper is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")


def load_source(observations_path: Path, context_path: Path) -> tuple:
    """Do not call aggregation or load any neighboring export/evaluation files."""
    observation_bytes, context_bytes = observations_path.read_bytes(), context_path.read_bytes()
    observations = PilotObservationExport.model_validate_json(observation_bytes)
    context = PilotInferenceContext.model_validate_json(context_bytes)
    if (
        _sha(observation_bytes) != context.observations_sha256
        or observations.source_asset_sha256 != context.source_asset_sha256
        or observations.site_id != context.site_id
        or {frame.camera_id for frame in observations.frames}
        != {camera.camera_id for camera in context.cameras}
    ):
        raise ValueError("strict evidence/context content, source, site and camera binding differs")
    keys = [(f.camera_id, f.frame_id) for f in observations.frames]
    times = [(f.camera_id, f.timestamp) for f in observations.frames]
    if len(set(keys)) != len(keys) or len(set(times)) != len(times):
        raise ValueError("duplicate camera frame/time identities are ambiguous")
    # Validate the explicit camera/plane contracts even for cameras with no visible pixels.
    for camera in context.cameras:
        InverseProjectionService(camera, context.plane)
    return (
        observations,
        context,
        {
            str(observations_path.resolve()): _sha(observation_bytes),
            str(context_path.resolve()): _sha(context_bytes),
        },
    )


def project(camera: Camera, plane: Plane, frame: ObservationFrame) -> tuple[list | None, str]:
    try:
        result = InverseProjectionService(camera, plane).project_frame(frame)
        return list(result.world_position), "PROJECTED"
    except InverseProjectionError as error:
        return None, error.failure.value


def noise_result(
    camera: Camera,
    plane: Plane,
    frame: ObservationFrame,
    baseline: list | None,
    jacobian: list | None,
    delta: tuple[float, float],
) -> dict[str, Any]:
    assert frame.point_2d is not None
    noisy_pixel = [original + shift for original, shift in zip(frame.point_2d, delta, strict=True)]
    noisy_frame = ObservationFrame.model_validate(frame.model_dump() | {"point_2d": noisy_pixel})
    position, state = project(camera, plane, noisy_frame)
    pixel_norm = float(np.linalg.norm(delta))
    displacement = None
    if position is not None and baseline is not None:
        displacement = np.asarray(position) - np.asarray(baseline)
    predicted = np.asarray(jacobian) @ np.asarray(delta) if jacobian is not None else None
    norm = float(np.linalg.norm(displacement)) if displacement is not None else None
    return {
        "delta_uv_pixels": list(delta),
        "pixel_noise_vector_norm": pixel_norm,
        "perturbed_pixel": noisy_pixel,
        "projection_state": state,
        "projected_position": position,
        "world_displacement_vector_bu": displacement.tolist() if displacement is not None else None,
        "world_displacement_norm_bu": norm,
        "local_amplification_bu_per_pixel": norm / pixel_norm
        if norm is not None and pixel_norm
        else None,
        "directional_jacobian_prediction_bu": predicted.tolist() if predicted is not None else None,
        "directional_prediction_residual_norm_bu": (
            float(np.linalg.norm(displacement - predicted))
            if displacement is not None and predicted is not None
            else None
        ),
    }


def summarize(rows: list[dict], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    result = []
    for identity, selected in sorted(groups.items()):
        values = [
            r["world_displacement_norm_bu"]
            for r in selected
            if r["world_displacement_norm_bu"] is not None
        ]
        result.append(
            {
                "label": PILOT_LABEL,
                "reference": REFERENCE,
                **dict(zip(keys, identity, strict=True)),
                "coordinate_units": "BLENDER_SCENE_UNITS",
                "physical_scale_authority": "PROVISIONAL",
                "sample_count": len(selected),
                "comparison_count": len(values),
                "rms_vector_displacement_bu": math.sqrt(
                    math.fsum(v * v for v in values) / len(values)
                )
                if values
                else None,
                "mean_vector_displacement_bu": math.fsum(values) / len(values) if values else None,
                "max_vector_displacement_bu": max(values) if values else None,
                "projection_states": dict(Counter(r["projection_state"] for r in selected)),
            }
        )
    return result


def _table(output: Path, stem: str, rows: list[dict]) -> None:
    _write_json(
        output / (stem + ".json"),
        {
            "label": PILOT_LABEL,
            "reference": REFERENCE,
            "coordinate_units": "BLENDER_SCENE_UNITS",
            "physical_scale_authority": "PROVISIONAL",
            "rows": rows,
        },
    )
    if rows:
        with (output / (stem + ".csv")).open("x", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {k: json.dumps(v) if isinstance(v, dict | list) else v for k, v in row.items()}
                )


def _geometry_value(row: dict, key: str) -> float | None:
    diagnostic = row.get("conditioning", {})
    group = "jacobian" if key == GEOMETRY_JNORM_KEY else "geometry"
    value = diagnostic.get(group, {}).get(key)
    return float(value) if isinstance(value, int | float) and math.isfinite(value) else None


def _diagnostic_max(rows: list[dict], group: str, key: str) -> float | None:
    values = [(row.get("conditioning", {}).get(group) or {}).get(key) for row in rows]
    finite = [
        float(value) for value in values if isinstance(value, int | float) and math.isfinite(value)
    ]
    return max(finite) if finite else None


def charts(
    output: Path, noise_rows: list[dict], baseline_rows: list[dict], cameras: list[dict]
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    metadata = {
        "DatasetLabel": PILOT_LABEL,
        "Reference": REFERENCE,
        "ScaleAuthority": "PROVISIONAL",
    }
    title = (
        PILOT_LABEL + " · PROJECTED-baseline displacement; NOT GT accuracy\nBU scale PROVISIONAL"
    )
    grouped = summarize(noise_rows, ("site_id", "camera_id", "amplitude_half_width_pixels"))
    figure, axis = plt.subplots(figsize=(12, 7), dpi=140)
    identities = sorted({(r["site_id"], r["camera_id"]) for r in grouped})
    for site, camera in identities:
        selected = [
            r
            for r in grouped
            if r["site_id"] == site
            and r["camera_id"] == camera
            and r["rms_vector_displacement_bu"] is not None
        ]
        if selected:
            axis.plot(
                [r["amplitude_half_width_pixels"] for r in selected],
                [r["rms_vector_displacement_bu"] for r in selected],
                marker=".",
                label=site + ": " + camera,
            )
    axis.set_xscale("symlog", linthresh=0.001)
    axis.set_yscale("symlog", linthresh=0.0001)
    axis.set(
        xlabel="Uniform u/v noise half-width (pixels), same draws at each amplitude",
        ylabel="RMS 3D vector displacement (BU) from PROJECTED baseline",
        title=title,
    )
    if identities:
        axis.legend(fontsize=7, loc="best")
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(output / "noise_vs_3d_error.png", metadata=metadata)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(15, 7), dpi=140)
    labels = [r["site_id"] + "\n" + r["camera_id"] for r in cameras]
    x = np.arange(len(cameras))
    norms = [r["mean_jacobian_spectral_norm_bu_per_pixel"] for r in cameras]
    rms = [r["quarter_pixel_seed_20261006_rms_displacement_bu"] for r in cameras]
    for axis, values, ylabel in zip(
        axes,
        (norms, rms),
        (
            "Mean local Jacobian spectral norm (BU/pixel)",
            "RMS displacement at ±0.25px (BU), seed 20261006",
        ),
        strict=True,
    ):
        valid = [(i, value) for i, value in enumerate(values) if value is not None]
        if valid:
            axis.bar([p[0] for p in valid], [p[1] for p in valid], color="#3b8dbd")
        axis.set_xticks(x, labels, rotation=65, ha="right", fontsize=7)
        axis.set_ylabel(ylabel)
        for i, value in enumerate(values):
            if value is None:
                axis.text(i, 0, "NO VISIBLE\nSAMPLES", ha="center", va="bottom", fontsize=7)
        axis.grid(axis="y", alpha=0.2)
    figure.suptitle(title)
    figure.tight_layout()
    figure.savefig(output / "per_camera_sensitivity.png", metadata=metadata)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(13, 6), dpi=140)
    for site, camera in sorted({(r["site_id"], r["camera_id"]) for r in baseline_rows}):
        selected = [r for r in baseline_rows if r["site_id"] == site and r["camera_id"] == camera]
        for axis, key in zip(axes, (GEOMETRY_INCIDENCE_KEY, GEOMETRY_DISTANCE_KEY), strict=True):
            pairs = [
                (_geometry_value(r, key), _geometry_value(r, GEOMETRY_JNORM_KEY)) for r in selected
            ]
            pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
            if pairs:
                axis.scatter(
                    [p[0] for p in pairs],
                    [p[1] for p in pairs],
                    s=16,
                    alpha=0.6,
                    label=site + ": " + camera,
                )
    axes[0].set_xlabel("Absolute normal · unit ray (1=normal incidence; 0=grazing)")
    axes[1].set_xlabel("Ray intersection distance (BU)")
    for axis in axes:
        axis.set_ylabel("Local Jacobian spectral norm (BU/pixel)")
        axis.grid(alpha=0.2)
        if axis.get_legend_handles_labels()[0]:
            axis.legend(fontsize=6)
    figure.suptitle(PILOT_LABEL + " · Baseline geometric conditioning\nBU scale PROVISIONAL")
    figure.tight_layout()
    figure.savefig(output / "geometry_conditioning.png", metadata=metadata)
    plt.close(figure)


def analyze_sources(sources: list[dict[str, Path]], output: Path) -> dict[str, Any]:
    """Only {'observations': Path, 'context': Path} inputs; all variants are copies."""
    if not sources or any(set(source) != {"observations", "context"} for source in sources):
        raise ValueError("analysis accepts only explicit strict 2D/context source pairs")
    if output.exists():
        raise FileExistsError(output)
    helper = _helper()
    baseline_rows, noise_rows, calibration_rows = [], [], []
    inputs: dict[str, str] = {}
    camera_inventory: dict[tuple[str, str], dict] = {}
    seen_sources: set[str] = set()
    for source in sources:
        observations, context, digests = load_source(
            Path(source["observations"]), Path(source["context"])
        )
        if context.source_id in seen_sources:
            raise ValueError("source identities must be unique in the sensitivity inventory")
        seen_sources.add(context.source_id)
        inputs.update(digests)
        cameras = {camera.camera_id: camera for camera in context.cameras}
        units = {seed: random.Random(seed) for seed in SEEDS}
        for camera in context.cameras:
            camera_inventory[(context.site_id, camera.camera_id)] = {
                "site_id": context.site_id,
                "camera_id": camera.camera_id,
                "source_id": context.source_id,
                "source_asset_sha256": context.source_asset_sha256,
                "spatial_context_id": context.spatial_context_id,
                "visible_pixel_samples": 0,
            }
        for frame in observations.frames:
            if frame.status != VisibilityStatus.OBSERVED:
                continue
            camera = cameras[frame.camera_id]
            camera_inventory[(context.site_id, camera.camera_id)]["visible_pixel_samples"] += 1
            baseline, baseline_state = project(camera, context.plane, frame)
            geometry = (
                helper.diagnose_projection(camera, context.plane, frame)
                if baseline is not None
                else {"status": "REJECTED", "reason": baseline_state}
            )
            jacobian = (geometry.get("jacobian") or {}).get(GEOMETRY_JACOBIAN_KEY)
            if baseline is not None and (
                jacobian is None
                or np.asarray(jacobian).shape != (3, 2)
                or not np.isfinite(np.asarray(jacobian, dtype=float)).all()
            ):
                raise ValueError("accepted conditioning diagnostic requires a finite 3x2 Jacobian")
            identity = {
                "label": PILOT_LABEL,
                "reference": REFERENCE,
                "coordinate_units": "BLENDER_SCENE_UNITS",
                "physical_scale_authority": "PROVISIONAL",
                "source_id": context.source_id,
                "site_id": context.site_id,
                "spatial_context_id": context.spatial_context_id,
                "source_asset_sha256": context.source_asset_sha256,
                "target_id": frame.target_id,
                "camera_id": camera.camera_id,
                "frame_id": frame.frame_id,
                "timestamp": frame.timestamp,
                "original_pixel": list(frame.point_2d),
                "baseline_position": baseline,
                "baseline_projection_state": baseline_state,
            }
            baseline_rows.append(identity | {"conditioning": geometry})
            for seed, rng in units.items():
                unit_delta = (rng.uniform(-1, 1), rng.uniform(-1, 1))
                for amplitude in AMPLITUDES:
                    delta = tuple(amplitude * value for value in unit_delta)
                    noise_rows.append(
                        identity
                        | {
                            "seed": seed,
                            "amplitude_half_width_pixels": amplitude,
                            "common_unit_random_draw": list(unit_delta),
                            "conditioning": geometry,
                        }
                        | noise_result(camera, context.plane, frame, baseline, jacobian, delta)
                    )
            variants = [
                ("camera", metadata, variant, context.plane)
                for metadata, variant in helper.camera_perturbations(camera)
            ] + [
                ("plane", metadata, camera, variant)
                for metadata, variant in helper.plane_perturbations(
                    context.plane, projected_anchor=baseline
                )
            ]
            for kind, metadata, variant_camera, variant_plane in variants:
                position, state = project(variant_camera, variant_plane, frame)
                displacement = (
                    np.asarray(position) - np.asarray(baseline)
                    if position is not None and baseline is not None
                    else None
                )
                variant_id = metadata["variant_id"]
                variant_geometry = (
                    helper.diagnose_projection(variant_camera, variant_plane, frame)
                    if position is not None
                    else {"status": "REJECTED", "failure": state}
                )
                calibration_rows.append(
                    identity
                    | {
                        "perturbation_kind": kind,
                        "variant_id": variant_id,
                        "variant": metadata,
                        "conditioning": variant_geometry,
                        "projection_state": state,
                        "projected_position": position,
                        "original_pixels_preserved": True,
                        "world_displacement_vector_bu": displacement.tolist()
                        if displacement is not None
                        else None,
                        "world_displacement_norm_bu": float(np.linalg.norm(displacement))
                        if displacement is not None
                        else None,
                    }
                )
    noise_summary = summarize(
        noise_rows, ("site_id", "camera_id", "seed", "amplitude_half_width_pixels")
    )
    calibration_summary = summarize(
        calibration_rows, ("site_id", "camera_id", "perturbation_kind", "variant_id")
    )
    camera_summary = []
    for key, inventory in sorted(camera_inventory.items()):
        geometry = [r for r in baseline_rows if (r["site_id"], r["camera_id"]) == key]
        norms = [_geometry_value(r, GEOMETRY_JNORM_KEY) for r in geometry]
        norms = [v for v in norms if v is not None]
        quarter = [
            r
            for r in noise_summary
            if (r["site_id"], r["camera_id"]) == key
            and r["seed"] == 20261006
            and r["amplitude_half_width_pixels"] == 0.25
        ]
        camera_summary.append(
            {
                "label": PILOT_LABEL,
                "reference": REFERENCE,
                **inventory,
                "coordinate_units": "BLENDER_SCENE_UNITS",
                "physical_scale_authority": "PROVISIONAL",
                "baseline_projection_states": dict(
                    Counter(r["baseline_projection_state"] for r in geometry)
                ),
                "mean_jacobian_spectral_norm_bu_per_pixel": math.fsum(norms) / len(norms)
                if norms
                else None,
                "max_jacobian_spectral_norm_bu_per_pixel": max(norms) if norms else None,
                "max_float64_vs_decimal60_difference_bu": _diagnostic_max(
                    geometry, "high_precision", "difference_from_service_scene_units"
                ),
                "max_float32_vs_service_difference_bu": _diagnostic_max(
                    geometry, "float32_diagnostic", "difference_from_service_scene_units"
                ),
                "max_roundtrip_pixel_error": _diagnostic_max(geometry, "roundtrip", "pixel_error"),
                "max_jacobian_central_difference_relative_error": _diagnostic_max(
                    geometry, "jacobian", "central_difference_relative_frobenius_error"
                ),
                "quarter_pixel_seed_20261006_rms_displacement_bu": quarter[0][
                    "rms_vector_displacement_bu"
                ]
                if quarter
                else None,
            }
        )
    # Detect input changes before saving any result; no data files are overwritten.
    for path, digest in inputs.items():
        if _sha(Path(path).read_bytes()) != digest:
            raise RuntimeError("2D/context input changed during analysis")
    output.mkdir(parents=True, exist_ok=False)
    _write_jsonl(output / "baseline_geometry.jsonl", baseline_rows)
    _write_jsonl(output / "per_sample.jsonl", noise_rows)
    _write_jsonl(output / "calibration_samples.jsonl", calibration_rows)
    _table(output, "noise_summary", noise_summary)
    _table(output, "camera_summary", camera_summary)
    _table(output, "calibration_summary", calibration_summary)
    charts(output, noise_rows, baseline_rows, camera_summary)
    summary = {
        "label": PILOT_LABEL,
        "reference": REFERENCE,
        "physical_scale_authority": "PROVISIONAL",
        "noise_distribution": "INDEPENDENT_UNIFORM_U_V_SAME_SEEDED_UNIT_DRAW_ACROSS_AMPLITUDES",
        "amplitudes_half_width_pixels": list(AMPLITUDES),
        "seeds": list(SEEDS),
        "source_count": len(sources),
        "baseline_visible_samples": len(baseline_rows),
        "noise_rows": len(noise_rows),
        "calibration_rows": len(calibration_rows),
        "cameras": camera_summary,
        "inputs_sha256": inputs,
        "ground_truth_read": False,
        "aggregation_graph_ranking_reconstruction_executed": False,
        "scene_or_camera_asset_modified": False,
        "files_sha256": {p.name: _sha(p.read_bytes()) for p in output.iterdir()},
    }
    _write_json(output / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        type=Path,
        required=True,
        help="JSON list of explicit observations/context paths; no metadata sources",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = json.loads(args.sources.read_text())
    pairs = [{key: Path(value) for key, value in source.items()} for source in inventory]
    summary = analyze_sources(pairs, args.output)
    print(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "baseline_visible_samples": summary["baseline_visible_samples"],
                "noise_rows": summary["noise_rows"],
                "output": str(args.output.resolve()),
            }
        )
    )


if __name__ == "__main__":
    main()
