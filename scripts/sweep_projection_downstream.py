"""Fixed PILOT pixel-noise sensitivity sweep over two existing Blender trajectories.

Inference accepts only strict 2D observations, context and numeric configuration.
Saved inference is frozen before the existing evaluator can read Ground Truth.
The point budget, Coverage epsilon, core search, Top-K and metrics stay unchanged.
"""

from __future__ import annotations

import argparse
import builtins
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import random
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NamedTuple
from unittest.mock import patch

from amidst.datasets.pilot import PILOT_LABEL, PilotInferenceContext, PilotObservationExport
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import VisibilityStatus
from amidst.storage.json_files import write_json

NOISE_HALF_WIDTHS_PIXELS = (
    0.0, 0.0005, 0.001, 0.0015, 0.002, 0.0025, 0.003, 0.0035, 0.004,
    0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0,
)
SEEDS = (20261006, 42, 20261007)
COVERAGE_EPSILON_SCENE_UNITS = 0.02
POINT_BUDGET_SCENE_UNITS = 0.02
SOURCE_SCENARIOS = {"office": "S01_office_medium", "corridor": "S02_corridor_long"}
SCOPE = "PILOT_PROJECTION_SENSITIVITY_NOT_FORMAL_CASES_1_3"


def _load_script(name: str, filename: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"existing script {filename} is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


robustness = _load_script("sensitivity_existing_consumer", "run_pilot_robustness.py")
evaluation = _load_script("sensitivity_existing_evaluator", "evaluate_pilot_robustness.py")
INFERENCE_FILES = robustness.INFERENCE_FILES


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


class SourceInputs(NamedTuple):
    scenario_id: str
    root: Path
    observations: PilotObservationExport
    context: PilotInferenceContext
    configuration: Any
    truth_path: Path  # Evaluation capability; never given to the inference consumer.
    input_digests: dict[str, str]


class ProjectedSample(NamedTuple):
    world_position: tuple[float, float, float]
    uv: tuple[float, float]


def _load_source(root: Path) -> SourceInputs:
    inputs = root / "fixture" / "inference"
    observations_bytes = (inputs / "observations.json").read_bytes()
    context_bytes = (inputs / "projection_context.json").read_bytes()
    scenario_bytes = (inputs / "scenario_config.json").read_bytes()
    observations = PilotObservationExport.model_validate_json(observations_bytes)
    context = PilotInferenceContext.model_validate_json(context_bytes)
    configuration = robustness.RobustnessScenario.model_validate_json(scenario_bytes)
    if (
        context.observations_sha256 != _sha(observations_bytes)
        or context.site_id != observations.site_id
        or context.source_asset_sha256 != observations.source_asset_sha256
    ):
        raise ValueError("source strict 2D/context content binding differs")
    if SOURCE_SCENARIOS.get(context.site_id) != configuration.scenario_id:
        raise ValueError("only the existing S01 office and S02 corridor sources are supported")
    if (
        configuration.lateral_offset_scene_units != 12.0
        or configuration.max_speed_scene_units_s != 32.0
        or configuration.max_candidate_paths != 3
        or configuration.random_seed != SEEDS[0]
    ):
        raise ValueError("source search settings must preserve the fixed pilot controls")
    return SourceInputs(
        scenario_id=configuration.scenario_id, root=root,
        observations=observations, context=context, configuration=configuration,
        truth_path=root / "fixture" / "evaluation" / "ground_truth.json",
        input_digests={
            "observations.json": _sha(observations_bytes),
            "projection_context.json": _sha(context_bytes),
            "scenario_config.json": _sha(scenario_bytes),
        },
    )


def normalized_noise(
    observations: PilotObservationExport, seed: int,
) -> tuple[tuple[float, float], ...]:
    """Keep export order and draw only two values per original OBSERVED pixel."""
    generator = random.Random(seed)
    return tuple(
        (generator.uniform(-1.0, 1.0), generator.uniform(-1.0, 1.0))
        for frame in observations.frames if frame.status == VisibilityStatus.OBSERVED
    )


def perturb_pixels(
    observations: PilotObservationExport, draws: tuple[tuple[float, float], ...],
    halfwidth: float,
) -> PilotObservationExport:
    if not math.isfinite(halfwidth) or halfwidth < 0:
        raise ValueError("pixel halfwidth must be finite and nonnegative")
    if len(draws) != sum(row.status == VisibilityStatus.OBSERVED for row in observations.frames):
        raise ValueError("normalized noise must contain exactly one pair per OBSERVED frame")
    iterator = iter(draws)
    payload = observations.model_dump(mode="json")
    for frame in payload["frames"]:
        if frame["status"] == "OBSERVED":
            assert frame["point_2d"] is not None
            delta = next(iterator)
            frame["point_2d"] = [
                value + halfwidth * component
                for value, component in zip(frame["point_2d"], delta, strict=True)
            ]
    return PilotObservationExport.model_validate(payload)


class InferenceReadViolation(RuntimeError):
    """A consumer attempted to read outside its explicit GT-free input capability."""


@contextmanager
def inference_read_guard(inputs: tuple[Path, Path, Path], output: Path) -> Iterator[set[str]]:
    """Enforce the read boundary at runtime, including renamed truth files."""
    allowed = {path.resolve(): path.name for path in inputs}
    output_root = output.resolve()
    reads: set[str] = set()
    original_path_open, original_builtin_open = Path.open, builtins.open
    original_io_open, original_os_open = io.open, os.open

    def check(file: Any, mode: str) -> None:
        if mode.startswith(("w", "a", "x")) and "+" not in mode:
            return
        if isinstance(file, int):
            raise InferenceReadViolation("unbound file-descriptor reads are forbidden")
        path = Path(file).resolve()
        if path in allowed:
            reads.add(allowed[path])
        elif path.is_relative_to(output_root):
            reads.add(f"saved_inference/{path.relative_to(output_root).as_posix()}")
        else:
            raise InferenceReadViolation(f"inference read outside strict inputs: {path.name}")

    def path_open(path: Path, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        check(path, mode)
        return original_path_open(path, mode, *args, **kwargs)

    def builtin_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        check(file, mode)
        return original_builtin_open(file, mode, *args, **kwargs)

    def io_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        check(file, mode)
        return original_io_open(file, mode, *args, **kwargs)

    def os_open(file: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        check(file, "w" if flags & os.O_ACCMODE == os.O_WRONLY else "r")
        return original_os_open(file, flags, *args, **kwargs)

    with (patch.object(Path, "open", path_open), patch.object(builtins, "open", builtin_open),
          patch.object(io, "open", io_open), patch.object(os, "open", os_open)):
        yield reads


def _freeze(root: Path) -> dict[str, str]:
    return {name: _sha((root / name).read_bytes()) for name in INFERENCE_FILES
            if (root / name).is_file()}


def _guarded_inference(
    paths: tuple[Path, Path, Path], output: Path,
) -> tuple[dict[str, Any], list[str]]:
    with inference_read_guard(paths, output) as reads:
        status = robustness.run_robustness(paths[0], paths[1], output, paths[2])
    return status, sorted(reads)


def projected_evidence(root: Path) -> dict[tuple[str, int, float], ProjectedSample]:
    path = root / "projected_frames.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_bytes())
    if payload.get("label") != PILOT_LABEL:
        raise ValueError("saved projection must be labeled PILOT / SYNTHETIC SAMPLE")
    dataset = FrameSampleDataset.model_validate(payload["dataset"])
    result = {}
    for sample in dataset.samples:
        if sample.visibility == VisibilityStatus.GAP:
            if sample.projected_point is not None or sample.uv is not None:
                raise ValueError("GAP must retain null pixels and projected points")
        else:
            if (sample.projected_point is None
                or sample.projected_point.provenance != "PROJECTED" or sample.uv is None):
                raise ValueError("OBSERVED samples require PROJECTED evidence")
            result[(sample.camera_id, sample.frame_id, sample.timestamp)] = (
                ProjectedSample(sample.projected_point.world_position, sample.uv)
            )
    return result


def projected_positions(root: Path) -> dict[tuple[str, int, float], tuple[float, float, float]]:
    return {key: sample.world_position for key, sample in projected_evidence(root).items()}


def projection_displacement(
    baseline: dict[tuple[str, int, float], tuple[float, float, float]],
    noisy: dict[tuple[str, int, float], tuple[float, float, float]],
) -> dict[str, Any]:
    if not noisy:
        return {"status": "NOT_COMPUTABLE", "point_count": 0,
                "max_scene_units": None, "mean_scene_units": None, "rms_scene_units": None}
    if baseline.keys() != noisy.keys():
        raise ValueError("saved projected frame identity sets differ from the zero-noise baseline")
    distances = [math.dist(baseline[key], noisy[key]) for key in baseline]
    return {"status": "COMPUTED", "point_count": len(distances),
            "max_scene_units": max(distances), "mean_scene_units": sum(distances) / len(distances),
            "rms_scene_units": math.sqrt(
                sum(value * value for value in distances) / len(distances))}


def projection_amplification(
    baseline: dict[tuple[str, int, float], ProjectedSample],
    noisy: dict[tuple[str, int, float], ProjectedSample],
) -> dict[str, Any]:
    """Actual saved pixel-vector norms, never the configured noise halfwidth or GT."""
    if not noisy:
        return {"status": "NOT_COMPUTABLE", "point_count": 0,
                "positive_pixel_norm_point_count": 0, "pixel_delta_norm_mean_px": None,
                "pixel_delta_norm_rms_px": None, "pixel_delta_norm_max_px": None,
                "point_amplification_mean_scene_units_per_pixel": None,
                "point_amplification_max_scene_units_per_pixel": None,
                "rms_amplification_scene_units_per_pixel": None,
                "max_amplification_sample": None, "samples": []}
    if baseline.keys() != noisy.keys():
        raise ValueError("saved projection/uv identity sets differ for amplification")
    samples: list[dict[str, Any]] = []
    for key, original in baseline.items():
        pixel_norm = math.dist(original.uv, noisy[key].uv)
        world_norm = math.dist(original.world_position, noisy[key].world_position)
        samples.append({
            "camera_id": key[0], "frame_id": key[1], "timestamp": key[2],
            "pixel_delta_norm_px": pixel_norm, "projected_delta_norm_scene_units": world_norm,
            "amplification_scene_units_per_pixel": (
                world_norm / pixel_norm if pixel_norm > 0 else None),
        })
    pixel_norms = [sample["pixel_delta_norm_px"] for sample in samples]
    pixel_rms = math.sqrt(sum(value * value for value in pixel_norms) / len(samples))
    world_rms = math.sqrt(sum(sample["projected_delta_norm_scene_units"] ** 2
                              for sample in samples) / len(samples))
    positive = [sample for sample in samples if sample["pixel_delta_norm_px"] > 0]
    maximum = max(positive, key=lambda sample: sample["amplification_scene_units_per_pixel"]) if (
        positive) else None
    return {
        "status": "COMPUTED", "point_count": len(samples),
        "positive_pixel_norm_point_count": len(positive),
        "pixel_delta_norm_mean_px": sum(pixel_norms) / len(samples),
        "pixel_delta_norm_rms_px": pixel_rms, "pixel_delta_norm_max_px": max(pixel_norms),
        "point_amplification_mean_scene_units_per_pixel": (
            sum(sample["amplification_scene_units_per_pixel"] for sample in positive)
            / len(positive)
            if positive else None),
        "point_amplification_max_scene_units_per_pixel": (
            maximum["amplification_scene_units_per_pixel"] if maximum is not None else None),
        "rms_amplification_scene_units_per_pixel": world_rms / pixel_rms if pixel_rms > 0 else None,
        "max_amplification_sample": maximum, "samples": samples,
        "basis": "PAIRED_SAVED_ZERO_NOISE_AND_NOISY_PROJECTED_POINTS_AND_UV_GT_FREE",
    }


def classify(status: dict[str, Any], metrics: dict[str, Any], displacement: dict[str, Any]) -> str:
    if not status["evaluation_eligible"] or metrics["status"] != "COMPUTED":
        return "INFERENCE_FAILURE"
    coverage = next(row["coverage_at_k"] for row in metrics["summaries"] if row["k"] == 3)
    if coverage is False:
        return "ACCURACY_FAILURE"
    if coverage is not True or displacement["max_scene_units"] is None:
        raise ValueError("computed inference needs explicit Coverage@3 and projection comparison")
    return ("STABLE" if displacement["max_scene_units"] <= POINT_BUDGET_SCENE_UNITS
            else "DEGRADED")


def _amplitude_token(value: float) -> str:
    return format(value, ".10g").replace(".", "p")


def _prepare_variant(
    source: SourceInputs, root: Path, halfwidth: float, seed: int,
    draws: tuple[tuple[float, float], ...],
) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=False)
    observations = perturb_pixels(source.observations, draws, halfwidth)
    observations_path = root / "observations.json"
    write_json(observations_path, observations.model_dump(mode="json"))
    scenario_id = f"PROJECTION_{source.scenario_id}_seed{seed}_noise{_amplitude_token(halfwidth)}"
    context = PilotInferenceContext.model_validate({
        **source.context.model_dump(mode="json"),
        "source_id": f"pilot_projection_sensitivity:{scenario_id}",
        "observations_sha256": _sha(observations_path.read_bytes()),
    })
    context_path, scenario_path = root / "projection_context.json", root / "scenario_config.json"
    write_json(context_path, context.model_dump(mode="json"))
    scenario = robustness.RobustnessScenario.model_validate({
        **source.configuration.model_dump(mode="json"),
        "scenario_id": scenario_id, "random_seed": seed,
    })
    write_json(scenario_path, scenario.model_dump(mode="json"))
    write_json(root / "treatment.json", {
        "label": PILOT_LABEL, "scope": SCOPE, "site_id": source.context.site_id,
        "source_scenario_id": source.scenario_id, "scenario_id": scenario_id,
        "noise_halfwidth_pixels": halfwidth, "random_seed": seed,
        "normalized_uniform_draws_sha256": _sha(_json_bytes(draws)),
        "source_strict_input_sha256": source.input_digests,
        "changed_fields": ["OBSERVED.point_2d", "context.observations_sha256",
                           "context.source_id", "scenario.scenario_id", "scenario.random_seed"],
        "gap_pixels_and_projected_points_remain_null": True,
        "ground_truth_read_for_treatment": False,
        "camera_calibration_plane_and_navigation_bounds_changed": False,
    })
    return observations_path, context_path, scenario_path


def _run_variant(
    source: SourceInputs, root: Path, halfwidth: float, seed: int,
    draws: tuple[tuple[float, float], ...],
    baseline: dict[tuple[str, int, float], ProjectedSample] | None,
) -> tuple[dict[str, Any], dict[tuple[str, int, float], ProjectedSample]]:
    paths = _prepare_variant(source, root / "input", halfwidth, seed, draws)
    run_root = root / "run_01"
    status, read_paths = _guarded_inference(paths, run_root)
    # Inference is immutable before this function obtains any GT content.
    frozen = _freeze(run_root)
    positions = projected_evidence(run_root)
    if baseline is None:
        if halfwidth != 0 or not positions:
            raise ValueError("each source requires a successful zero-noise projection baseline")
        baseline = positions
    displacement = projection_displacement(
        {key: sample.world_position for key, sample in baseline.items()},
        {key: sample.world_position for key, sample in positions.items()},
    )
    amplification = projection_amplification(baseline, positions)
    metrics = evaluation.evaluate_saved_robustness(
        run_root, source.truth_path, paths[1], coverage_epsilon=COVERAGE_EPSILON_SCENE_UNITS,
    )
    if _freeze(run_root) != frozen:
        raise RuntimeError("evaluation changed frozen sensitivity inference")
    row = {
        "label": PILOT_LABEL, "scope": SCOPE, "scenario_id": status["scenario_id"],
        "source_scenario_id": source.scenario_id, "site_id": source.context.site_id,
        "source_asset_sha256": source.context.source_asset_sha256,
        "noise_halfwidth_pixels": halfwidth, "random_seed": seed,
        "normalized_uniform_draws_sha256": _sha(_json_bytes(draws)),
        "inference_outcome": status["outcome"], "failed_stage": status["failed_stage"],
        "reason": status["reason"], "termination_reason": status["termination_reason"],
        "candidate_count": status["candidate_count"],
        "hypothesis_count": status["hypothesis_count"],
        "candidate_count_state": status["candidate_count_state"],
        "evaluation_status": metrics["status"],
        "evaluation_eligible": status["evaluation_eligible"],
        "inference_complete": status.get("enumeration_complete", False),
        "projected_displacement": displacement, "projection_amplification": amplification,
        "metrics": metrics["summaries"],
        "classification": classify(status, metrics, displacement),
        "inference_read_allowlist_verified": True, "inference_read_paths": read_paths,
        "ground_truth_read_during_inference": False,
        "inference_frozen_before_evaluation": True,
        "inference_artifact_sha256": frozen,
        "physical_validity": "PARTIAL_PROVISIONAL",
        "run_path": f"{source.scenario_id}/seed_{seed}/noise_{_amplitude_token(halfwidth)}/run_01",
    }
    write_json(root / "result.json", row)
    return row, positions


def _repeat_poison_check(source: SourceInputs, root: Path) -> dict[str, Any]:
    """Replay the same pure 2D inputs; poison exists only as an evaluation reference."""
    paths = (root / "input" / "observations.json", root / "input" / "projection_context.json",
             root / "input" / "scenario_config.json")
    original = _freeze(root / "run_01")
    _, repeat_reads = _guarded_inference(paths, root / "repeat_run")
    if _freeze(root / "repeat_run") != original:
        raise RuntimeError("representative inference repeat was not byte identical")
    # Original saved inference and evaluation already exist before a truth file is opened here.
    truth_bytes = source.truth_path.read_bytes()
    truth = json.loads(truth_bytes)
    for sample in truth["samples"]:
        sample["position"] = [value + delta for value, delta in
                              zip(sample["position"], (10000, -20000, 30000), strict=True)]
    poison_path = root / "evaluation_only" / "poisoned_ground_truth.json"
    write_json(poison_path, truth)
    _, poison_reads = _guarded_inference(paths, root / "poison_run")
    if _freeze(root / "poison_run") != original:
        raise RuntimeError("representative GT poison changed inference bytes")
    poison_metrics = evaluation.evaluate_saved_robustness(
        root / "poison_run", poison_path, paths[1], coverage_epsilon=COVERAGE_EPSILON_SCENE_UNITS,
    )
    if _freeze(root / "poison_run") != original:
        raise RuntimeError("poison evaluation changed inference bytes")
    if _sha(source.truth_path.read_bytes()) != _sha(truth_bytes):
        raise RuntimeError("original evaluation GT changed")
    report = {
        "label": PILOT_LABEL, "scope": SCOPE,
        "scenario_id": json.loads(paths[2].read_bytes())["scenario_id"],
        "repeat_inference_byte_equal": True, "poison_inference_byte_equal": True,
        "inference_artifact_sha256": original,
        "repeat_inference_read_paths": repeat_reads, "poison_inference_read_paths": poison_reads,
        "gt_poison_translation_scene_units": [10000, -20000, 30000],
        "poison_used_only_after_inference_for_evaluation": True,
        "poison_coverage_at_3": poison_metrics["summaries"][-1]["coverage_at_k"],
        "original_truth_unchanged": True,
    }
    write_json(root / "isolation_check.json", report)
    return report


def aggregate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    aggregates, transitions = [], []
    for source in sorted({row["source_scenario_id"] for row in rows}):
        selected = [row for row in rows if row["source_scenario_id"] == source]
        for amplitude in sorted({row["noise_halfwidth_pixels"] for row in selected}):
            group = [row for row in selected if row["noise_halfwidth_pixels"] == amplitude]
            ranges: dict[str, dict[str, list[float | None]]] = {}
            for k in (1, 2, 3):
                ranges[str(k)] = {}
                for metric in ("ade_first_primary_scene_units", "fde_first_primary_scene_units",
                               "min_ade_at_k_scene_units", "min_fde_at_k_scene_units"):
                    values = [summary[metric] for row in group for summary in row["metrics"]
                              if summary["k"] == k and summary[metric] is not None]
                    ranges[str(k)][metric] = [min(values), max(values)] if values else [None, None]
            displacement = [row["projected_displacement"]["max_scene_units"] for row in group
                            if row["projected_displacement"]["max_scene_units"] is not None]
            aggregates.append({
                "label": PILOT_LABEL, "source_scenario_id": source,
                "noise_halfwidth_pixels": amplitude, "seed_count": len(group),
                "class_counts": dict(sorted(
                    Counter(row["classification"] for row in group).items())),
                "coverage_at_3_true_count": sum(
                    row["metrics"][-1]["coverage_at_k"] is True for row in group),
                "max_projected_displacement_seed_range_scene_units": (
                    [min(displacement), max(displacement)] if displacement else [None, None]),
                "metric_seed_ranges": ranges,
            })
        for seed in sorted({row["random_seed"] for row in selected}):
            ordered = sorted((row for row in selected if row["random_seed"] == seed),
                             key=lambda row: row["noise_halfwidth_pixels"])
            for first, second in zip(ordered, ordered[1:], strict=False):
                if first["classification"] != second["classification"]:
                    transitions.append({
                        "label": PILOT_LABEL, "source_scenario_id": source, "random_seed": seed,
                        "lower_tested_halfwidth_pixels": first["noise_halfwidth_pixels"],
                        "upper_tested_halfwidth_pixels": second["noise_halfwidth_pixels"],
                        "from": first["classification"], "to": second["classification"],
                        "interpretation": "Adjacent tested states; no monotonicity assumed.",
                    })
    return aggregates, transitions


def _write_table(output: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["label", "source_scenario_id", "noise_halfwidth_pixels", "random_seed",
              "classification", "termination_reason", "candidate_count", "hypothesis_count",
              "projected_max_displacement_scene_units", "physical_validity"]
    amplification_fields = (
        "pixel_delta_norm_mean_px", "pixel_delta_norm_rms_px", "pixel_delta_norm_max_px",
        "point_amplification_mean_scene_units_per_pixel",
        "point_amplification_max_scene_units_per_pixel", "rms_amplification_scene_units_per_pixel",
    )
    fields += list(amplification_fields) + [
        "max_amplification_camera_id", "max_amplification_frame_id",
    ]
    metrics = ("ade_first_primary_scene_units", "fde_first_primary_scene_units",
               "min_ade_at_k_scene_units", "min_fde_at_k_scene_units", "coverage_at_k",
               "selected_route_count")
    fields += [f"k{k}_{metric}" for k in (1, 2, 3) for metric in metrics]
    with (output / "sweep_table.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            flat = {field: row[field] for field in fields if field in row}
            flat["projected_max_displacement_scene_units"] = row["projected_displacement"][
                "max_scene_units"]
            flat.update({field: row["projection_amplification"][field]
                         for field in amplification_fields})
            maximum = row["projection_amplification"]["max_amplification_sample"]
            flat["max_amplification_camera_id"] = maximum["camera_id"] if maximum else None
            flat["max_amplification_frame_id"] = maximum["frame_id"] if maximum else None
            for summary in row["metrics"]:
                flat.update({f"k{summary['k']}_{metric}": summary[metric] for metric in metrics})
            writer.writerow(flat)


def run_sweep(source_roots: list[Path], output: Path) -> dict[str, Any]:
    """Run the fixed 102-cell protocol; neither source assets nor core semantics change."""
    if output.exists():
        raise FileExistsError(output)
    sources = [_load_source(root) for root in source_roots]
    if len(sources) != 2 or {source.scenario_id for source in sources} != set(
        SOURCE_SCENARIOS.values()
    ):
        raise ValueError("provide exactly the existing S01 office and S02 corridor scenario roots")
    output.mkdir(parents=True, exist_ok=False)
    rows, checks = [], []
    for source in sorted(sources, key=lambda item: item.scenario_id):
        for seed in SEEDS:
            draws = normalized_noise(source.observations, seed)
            if draws != normalized_noise(source.observations, seed):
                raise RuntimeError("normalized noise regeneration was not deterministic")
            baseline = None
            for halfwidth in NOISE_HALF_WIDTHS_PIXELS:
                root = output / source.scenario_id / f"seed_{seed}" / (
                    f"noise_{_amplitude_token(halfwidth)}")
                row, positions = _run_variant(source, root, halfwidth, seed, draws, baseline)
                if halfwidth == 0:
                    baseline = positions
                rows.append(row)
                representative = seed == SEEDS[0] and (
                    (source.context.site_id == "office" and halfwidth in (0.0, 0.25))
                    or (source.context.site_id == "corridor" and halfwidth == 0.25))
                if representative:
                    checks.append(_repeat_poison_check(source, root))
            print(f"{PILOT_LABEL}: {source.scenario_id}, seed {seed}, 17 amplitudes saved",
                  flush=True)
        actual = {name: _sha((source.root / "fixture" / "inference" / name).read_bytes())
                  for name in source.input_digests}
        if actual != source.input_digests:
            raise RuntimeError("original strict source input changed during sensitivity sweep")
    aggregate, transitions = aggregate_rows(rows)
    report = {
        "label": PILOT_LABEL, "scope": SCOPE, "data_kind": "SYNTHETIC",
        "variant_count": len(rows), "expected_variant_count": 102,
        "noise_halfwidths_pixels": list(NOISE_HALF_WIDTHS_PIXELS), "random_seeds": list(SEEDS),
        "normalized_uniform_draws_shared_across_amplitudes": True,
        "normalized_noise_regenerated_byte_equal": True,
        "projection_amplification_basis": (
            "ACTUAL_PAIRED_SAVED_PROJECTED_3D_DISPLACEMENT_DIVIDED_BY_PIXEL_VECTOR_NORM_GT_FREE"),
        "coverage_epsilon_scene_units": COVERAGE_EPSILON_SCENE_UNITS,
        "point_budget_scene_units": POINT_BUDGET_SCENE_UNITS,
        "budget_authority": "FIXED_PILOT_DIAGNOSTIC_ONLY_NOT_FORMAL_OR_RETUNED",
        "classification_policy": {
            "STABLE": "Coverage@3 true and max projected displacement <= 0.02 scene units",
            "DEGRADED": "Coverage@3 true and max projected displacement > 0.02 scene units",
            "ACCURACY_FAILURE": "Coverage@3 false; inference may still be COMPLETE",
            "INFERENCE_FAILURE": "Projection/search cannot provide an evaluable prediction",
        },
        "class_counts": dict(sorted(Counter(row["classification"] for row in rows).items())),
        "termination_counts": dict(sorted(
            Counter(row["termination_reason"] for row in rows).items())),
        "sources": [{"scenario_id": source.scenario_id, "site_id": source.context.site_id,
                     "source_asset_sha256": source.context.source_asset_sha256,
                     "strict_input_sha256": source.input_digests} for source in sources],
        "original_inputs_preserved": True,
        "ground_truth_used_only_for_saved_output_evaluation": True,
        "all_variant_inference_reads_allowlisted": True,
        "formal_benchmark_executed": False, "formal_benchmark_semantics_modified": False,
        "core_search_top_k_and_metric_semantics_modified": False,
        "physical_validity": "PARTIAL_PROVISIONAL", "coordinate_units": "BLENDER_SCENE_UNITS",
        "physical_scale_authority": "UNVERIFIED", "new_blender_render_or_trajectory_count": 0,
        "representative_isolation_checks": checks, "results": rows,
        "seed_aggregates": aggregate, "observed_class_transitions": transitions,
        "boundary_by_source": {
            source.scenario_id: [row for row in transitions
                                 if row["source_scenario_id"] == source.scenario_id]
            for source in sources
        },
    }
    write_json(output / "sweep_report.json", report)
    _write_table(output, rows)
    lines = [
        f"# {PILOT_LABEL} — Projection sensitivity", "",
        "Two existing trajectories; 17 fixed pixel halfwidths × three seeds = 102 variants.",
        "Uniform directions repeat across amplitudes; GAP pixels and projected points stay null.",
        "Amplification uses actual per-frame ||Δ3D||/||Δuv|| and RMS3D/RMSΔuv; zero noise is N/A.",
        "Inference reads strict 2D/context/config. GT is read after saved inference is frozen.",
        "Coverage uses unchanged K=1/2/3 and strict ADE < 0.02 native Blender scene units.",
        "Point budget is fixed at 0.02 scene units, diagnostic and unverified in meters.",
        "Physical validity remains PARTIAL / PROVISIONAL; no formal Case 1–3 or new renders.", "",
        f"Class counts: {report['class_counts']}.",
        f"Termination counts: {report['termination_counts']}.",
        "Three representatives pass byte-identical repeat and GT-poison inference checks.", "",
        "| Source | Seed | Lower px | Upper px | Observed transition |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [f"| {row['source_scenario_id']} | {row['random_seed']} | "
              f"{row['lower_tested_halfwidth_pixels']} | {row['upper_tested_halfwidth_pixels']} | "
              f"{row['from']} → {row['to']} |" for row in transitions]
    lines += ["", "Adjacent tested transitions are empirical brackets; no monotonicity assumed.",
              "All per-variant ADE/FDE/minADE@K/minFDE@K/Coverage@K are in sweep_table.csv.", ""]
    (output / "sweep_report.md").write_text("\n".join(lines))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, action="append", required=True,
                        help="S01 or S02 scenario root; specify exactly twice")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_sweep(args.source, args.output)
    print(json.dumps({"label": PILOT_LABEL, "variant_count": report["variant_count"],
                      "class_counts": report["class_counts"]}))


if __name__ == "__main__":
    main()
