"""Bounded PILOT conditioning comparison: freeze inference before GT evaluation.

Policies never read truth. Original 2D evidence is preserved; projection rejection
is explicitly availability loss rather than simulated camera occlusion. Approved
school surface authority is unavailable, so E/F toy controls are kept separate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import sys
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from amidst.datasets.pilot import (
    PILOT_LABEL,
    PilotInferenceContext,
    PilotObservationExport,
    project_pilot_observations,
)
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.evidence import VisibilityStatus
from amidst.storage.json_files import write_json

SCOPE = "PROJECTION_CONDITIONING_MITIGATION_NOT_FORMAL_CASES_1_3"
NOISE_LEVELS = (0, 0.001, 0.002, 0.004, 0.01, 0.1, 0.25)
SEEDS = (20261006, 42, 20261007)
CALIBRATION_IDS = (
    "joint_focal:-0.001",
    "joint_focal:+0.001",
    "cx:-0.1",
    "cx:+0.1",
    "cy:-0.1",
    "cy:+0.1",
    "local_pitch:-0.01",
    "local_pitch:+0.01",
    "world_z:-0.1",
    "world_z:+0.1",
)
VARIANTS = (
    "A_BASELINE",
    "B_CONFIDENCE",
    "C_REJECT_STANDARD",
    "C_REJECT_EXTREME_ONLY",
    "D_LOCAL_BINDING",
)
UNAVAILABLE = ("E_GEOMETRY_SURFACE", "F_MULTI_SURFACE")
EPSILON = 0.02


@lru_cache
def module(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    if not spec or not spec.loader:
        raise RuntimeError(f"missing experiment helper: {name}")
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def key(sample: Any) -> tuple[str, int, float]:
    return sample.camera_id, sample.frame_id, float(sample.timestamp)


def freeze(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): digest(p) for p in sorted(root.rglob("*")) if p.is_file()}


def stats(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "mean_bu": math.fsum(values) / len(values) if values else None,
        "rms_bu": math.sqrt(math.fsum(x * x for x in values) / len(values)) if values else None,
        "max_bu": max(values) if values else None,
    }


def retained_error_evaluation(
    baseline: dict[tuple[str, int, float], tuple[float, float, float]],
    retained: dict[tuple[str, int, float], tuple[float, float, float]],
    truth: dict[float, tuple[float, float, float]],
) -> dict[str, Any]:
    """Evaluation only: pair identical identities before discussing accuracy gain."""
    if not set(retained) <= set(baseline) or any(k[2] not in truth for k in baseline):
        raise ValueError("evaluation requires original identities and exact timestamp truth")
    all_errors = [math.dist(p, truth[k[2]]) for k, p in baseline.items()]
    kept_errors = [math.dist(p, truth[k[2]]) for k, p in retained.items()]
    paired_errors = [math.dist(baseline[k], truth[k[2]]) for k in retained]
    full, kept, paired = stats(all_errors), stats(kept_errors), stats(paired_errors)
    reduction = None
    if paired["rms_bu"] and kept["rms_bu"] is not None:
        reduction = 100 * (1 - float(kept["rms_bu"]) / float(paired["rms_bu"]))
    return {
        "label": PILOT_LABEL,
        "purpose": "POST_FREEZE_EVALUATION_ONLY",
        "original_visible_count": len(baseline),
        "retained_count": len(retained),
        "availability": len(retained) / len(baseline) if baseline else None,
        "all_original_baseline_error": full,
        "retained_error": kept,
        "baseline_on_identical_retained_cohort": paired,
        "paired_rms_reduction_percent": reduction,
        "deletion_changes_evaluation_cohort": set(retained) != set(baseline),
        "missing_predictions_not_zero_error": True,
    }


def load_sources(inventory_path: Path, output: Path) -> list[dict[str, Any]]:
    inventory = json.loads(inventory_path.read_text())
    if inventory.get("label") != PILOT_LABEL:
        raise ValueError("input inventory must be a labeled pilot")
    evaluation = {s["source_id"]: s for s in inventory["evaluation_inputs_not_inference"]}
    sources = []
    policy = module("projection_mitigation_policy")
    for source in inventory["geometry_diagnostic_inputs"]:
        observed_path, context_path = Path(source["observations"]), Path(source["context"])
        observations = PilotObservationExport.model_validate_json(observed_path.read_bytes())
        context = PilotInferenceContext.model_validate_json(context_path.read_bytes())
        if digest(observed_path) != context.observations_sha256:
            raise ValueError("input observations content binding differs")
        if observations.site_id != context.site_id or (
            observations.source_asset_sha256 != context.source_asset_sha256
        ):
            raise ValueError("input source/site binding differs")
        preparation_path = context_path.parent.parent / "preparation_manifest.json"
        basis = json.loads(preparation_path.read_text())["independent_plane_basis"]
        receipt = policy.LocalPlaneReceipt.model_validate(
            {
                **basis,
                "site_id": context.site_id,
                "floor_id": context.zone.floor_id,
                "zone_id": context.zone.zone_id,
            }
        )
        policy.bind_local_landmark_plane(context, receipt)
        receipt_path = output / "receipts" / (context.site_id + ".json")
        write_json(
            receipt_path,
            {
                "label": PILOT_LABEL,
                "receipt": receipt.model_dump(mode="json"),
                "geometry_metadata_source_sha256": digest(preparation_path),
                "authority": "PILOT_DIAGNOSTIC_ONLY_NOT_PHYSICAL_APPROVAL",
            },
        )
        scenario = None
        if context.site_id in ("office", "corridor"):
            scenario = module("run_pilot_robustness").RobustnessScenario.model_validate_json(
                (context_path.parent / "scenario_config.json").read_bytes()
            )
        sources.append(
            {
                "site_id": context.site_id,
                "observations": observations,
                "context": context,
                "scenario": scenario,
                "receipt": receipt,
                "receipt_path": receipt_path,
                "truth_path": Path(evaluation[source["source_id"]]["evaluation_truth"]),
                "input_digests": {
                    str(p): digest(p) for p in (observed_path, context_path, preparation_path)
                },
            }
        )
    if {s["site_id"] for s in sources} != {"office", "corridor", "auditorium", "classroom101"}:
        raise ValueError("the fixed experiment requires the four existing source streams")
    return sources


def calibration_context(context: PilotInferenceContext, variant: str) -> PilotInferenceContext:
    helper = module("projection_conditioning")
    cameras = []
    for camera in context.cameras:
        alternatives = (
            helper.joint_focal_perturbations(camera)
            if (variant.startswith("joint_focal:"))
            else helper.camera_perturbations(camera)
        )
        cameras.append(
            next(copy for metadata, copy in alternatives if metadata["variant_id"] == variant)
        )
    return PilotInferenceContext.model_validate(
        {**context.model_dump(mode="json"), "cameras": [c.model_dump(mode="json") for c in cameras]}
    )


def cases(source: dict[str, Any]):
    sensitivity = module("sweep_projection_downstream")
    for seed in SEEDS:
        draws = sensitivity.normalized_noise(source["observations"], seed)
        for amount in NOISE_LEVELS:
            name = f"noise_{amount:g}_seed_{seed}".replace(".", "p")
            yield (
                name,
                sensitivity.perturb_pixels(source["observations"], draws, amount),
                source["context"],
                {
                    "kind": "PIXEL_NOISE",
                    "noise_halfwidth_px": amount,
                    "seed": seed,
                    "calibration_variant": None,
                },
            )
    for variant in CALIBRATION_IDS:
        yield (
            "cal_" + variant.replace(":", "_").replace(".", "p"),
            source["observations"],
            calibration_context(source["context"], variant),
            {
                "kind": "CALIBRATION_COPY",
                "noise_halfwidth_px": 0,
                "seed": SEEDS[0],
                "calibration_variant": variant,
            },
        )


def positions(dataset: FrameSampleDataset) -> dict:
    return {
        key(sample): sample.projected_point.world_position
        for sample in dataset.samples
        if sample.projected_point is not None
    }


def point_only_status(site: str) -> dict[str, Any]:
    return {
        "label": PILOT_LABEL,
        "scope": SCOPE,
        "outcome": "POINT_ONLY_DIAGNOSTIC",
        "reason": "SOURCE_TOPOLOGY_NOT_INCLUDED",
        "site_id": site,
        "termination_reason": "NOT_RUN",
        "candidate_count": None,
        "hypothesis_count": None,
        "evaluation_eligible": False,
        "gap_window": None,
        "failed_stage": None,
    }


def run_case(source: dict[str, Any], case: tuple, output: Path) -> list[dict[str, Any]]:
    name, evidence, context, treatment = case
    root = output / "cases" / source["site_id"] / name
    root.mkdir(parents=True, exist_ok=False)
    policy = module("projection_mitigation_policy")
    adapter = module("run_projection_mitigation_downstream")
    sensitivity = module("sweep_projection_downstream")
    observed_path = root / "input" / "observations.json"
    write_json(observed_path, evidence.model_dump(mode="json"))
    context = PilotInferenceContext.model_validate(
        {
            **context.model_dump(mode="json"),
            "observations_sha256": digest(observed_path),
            "source_id": f"pilot_mitigation:{source['site_id']}:{name}",
        }
    )
    context_path, scenario_path = root / "input/projection_context.json", root / "input/config.json"
    write_json(context_path, context.model_dump(mode="json"))
    scenario = None
    if source["scenario"] is not None:
        scenario = module("run_pilot_robustness").RobustnessScenario.model_validate(
            {
                **source["scenario"].model_dump(mode="json"),
                "scenario_id": f"MITIGATION_{source['site_id']}_{name}",
                "random_seed": treatment["seed"],
            }
        )
    write_json(
        scenario_path,
        scenario.model_dump(mode="json")
        if scenario
        else {"label": PILOT_LABEL, "purpose": "POINT_ONLY_NO_DOWNSTREAM_CONFIGURATION"},
    )
    rows = []
    with sensitivity.inference_read_guard(
        (observed_path, context_path, scenario_path, source["receipt_path"]),
        root,
    ) as reads:
        started = time.perf_counter()
        baseline = project_pilot_observations(evidence, context)
        baseline_seconds = time.perf_counter() - started
        started = time.perf_counter()
        camera_map = {camera.camera_id: camera for camera in context.cameras}
        diagnostics = {
            key(frame): policy.diagnose_sample(camera_map[frame.camera_id], context.plane, frame)
            for frame in evidence.frames
            if frame.status == VisibilityStatus.OBSERVED
        }
        diagnostic_seconds = time.perf_counter() - started
        if any(d["status"] != "ACCEPTED" for d in diagnostics.values()):
            raise ValueError("these fixed treatments unexpectedly failed inverse projection")
        local_plane = policy.bind_local_landmark_plane(context, source["receipt"])
        local_context = PilotInferenceContext.model_validate(
            {**context.model_dump(mode="json"), "plane": local_plane.model_dump()}
        )
        started = time.perf_counter()
        local_frames = project_pilot_observations(evidence, local_context)
        local_seconds = time.perf_counter() - started
        write_json(
            root / "conditioning.json",
            {
                "label": PILOT_LABEL,
                "purpose": "GT_FREE_DIAGNOSTIC_CANDIDATES_NOT_ALL_RELIABLE_OUTPUT",
                "treatment": treatment,
                "samples": list(diagnostics.values()),
                "ground_truth_read": False,
                "policy": policy.ConditioningPolicy().model_dump(),
            },
        )
        write_json(
            root / "baseline_projected_reference.json",
            {
                "label": PILOT_LABEL,
                "purpose": "GT_FREE_ORIGINAL_PROJECTED_REFERENCE",
                "dataset": baseline.model_dump(mode="json"),
            },
        )
        for variant in VARIANTS:
            started = time.perf_counter()
            mode = {"C_REJECT_STANDARD": "STANDARD", "C_REJECT_EXTREME_ONLY": "EXTREME_ONLY"}.get(
                variant, "NONE"
            )
            decisions = {k: policy.classify(d, rejection_mode=mode) for k, d in diagnostics.items()}
            if variant in ("A_BASELINE", "D_LOCAL_BINDING"):
                decisions = {
                    k: {
                        **d,
                        "accepted": True,
                        "low_confidence": False,
                        "requires_review": False,
                        "label": "POLICY_NOT_APPLIED",
                    }
                    for k, d in decisions.items()
                }
            candidate_frames = local_frames if variant == "D_LOCAL_BINDING" else baseline
            adapted = adapter.adapt_projected_frames(
                candidate_frames, {k: d["accepted"] for k, d in decisions.items()}
            )
            decision_seconds = time.perf_counter() - started
            run = root / variant / "run_01"
            started = time.perf_counter()
            if scenario is not None:
                status = adapter.run_projected_downstream(adapted, context, scenario, run)
            else:
                run.mkdir(parents=True, exist_ok=False)
                status = point_only_status(source["site_id"])
                write_json(
                    run / "projected_frames.json",
                    {"label": PILOT_LABEL, "dataset": adapted.model_dump(mode="json")},
                )
                write_json(run / "point_only_status.json", status)
            downstream_seconds = time.perf_counter() - started
            predicted = positions(adapted)
            write_json(
                root / variant / "decisions.json",
                {
                    "label": PILOT_LABEL,
                    "purpose": "PROJECTION_AVAILABILITY_NOT_CAMERA_OCCLUSION",
                    "policy_applied": variant not in ("A_BASELINE", "D_LOCAL_BINDING"),
                    "original_2d_preserved": True,
                    "decisions": [
                        {"camera_id": k[0], "frame_id": k[1], "timestamp": k[2], **decision}
                        for k, decision in decisions.items()
                    ],
                },
            )
            cost = local_seconds if variant == "D_LOCAL_BINDING" else baseline_seconds
            if variant not in ("A_BASELINE", "D_LOCAL_BINDING"):
                cost += diagnostic_seconds
            cost += decision_seconds
            rows.append(
                {
                    "label": PILOT_LABEL,
                    "scope": SCOPE,
                    "site_id": source["site_id"],
                    "case_id": name,
                    "variant": variant,
                    "treatment": treatment,
                    "original_visible_count": len(diagnostics),
                    "accepted_count": len(predicted),
                    "rejected_count": sum(not d["accepted"] for d in decisions.values()),
                    "low_confidence_count": sum(d["low_confidence"] for d in decisions.values()),
                    "requires_review_count": sum(d["requires_review"] for d in decisions.values()),
                    "downstream": status,
                    "downstream_available_source": scenario is not None,
                    "inference_artifact_sha256": freeze(run),
                    "runtime": {
                        "baseline_projection_seconds": baseline_seconds,
                        "shared_conditioning_diagnostics_seconds": diagnostic_seconds,
                        "decision_adapter_seconds": decision_seconds,
                        "effective_projection_stage_seconds": cost,
                        "downstream_seconds": downstream_seconds,
                        "cost_model": "SHARED_DIAGNOSTIC_ACCOUNTING_SINGLE_MACHINE_NOT_BENCHMARK",
                    },
                    "run_path": str(run.relative_to(output)),
                    "case_path": str(root.relative_to(output)),
                    "ground_truth_read_during_inference": False,
                }
            )
    for row in rows:
        row["inference_reads_allowlisted"] = True
        row["inference_read_paths"] = sorted(reads)
    write_json(root / "inference_rows.json", {"label": PILOT_LABEL, "rows": rows})
    return rows


def load_evaluation_truth(source: dict[str, Any]) -> dict[float, tuple[float, float, float]]:
    truth = json.loads(source["truth_path"].read_text())
    context = source["context"]
    if (
        truth.get("label") != PILOT_LABEL
        or truth.get("provenance") != "GROUND_TRUTH"
        or truth.get("source_asset_sha256") != context.source_asset_sha256
        or truth.get("site_id") != context.site_id
    ):
        raise ValueError("evaluation truth/source/site binding differs")
    values = {}
    for sample in truth["samples"]:
        if (
            sample["floor_id"] != context.zone.floor_id
            or (sample["trajectory_id"] != truth["trajectory_id"])
            or len(sample["position"]) != 3
            or not all(math.isfinite(v) for v in sample["position"])
        ):
            raise ValueError("evaluation truth has invalid floor/trajectory/finite position")
        timestamp = float(sample["timestamp"])
        if timestamp in values:
            raise ValueError("evaluation truth has duplicate timestamps")
        values[timestamp] = tuple(sample["position"])
    expected = {float(f.timestamp) for f in source["observations"].frames}
    if set(values) != expected:
        raise ValueError("evaluation truth must exactly cover the existing source stream")
    return values


def evaluate_rows(sources: list[dict], rows: list[dict], output: Path) -> None:
    evaluator = module("evaluate_pilot_robustness")
    truth = {s["site_id"]: load_evaluation_truth(s) for s in sources}
    source_map = {s["site_id"]: s for s in sources}
    baseline_cache = {}
    for row in rows:
        case_path, run = output / row["case_path"], output / row["run_path"]
        if freeze(run) != row["inference_artifact_sha256"]:
            raise RuntimeError("inference changed before evaluation")
        if row["case_path"] not in baseline_cache:
            baseline = json.loads((case_path / "baseline_projected_reference.json").read_text())
            baseline_cache[row["case_path"]] = positions(
                FrameSampleDataset.model_validate(baseline["dataset"])
            )
        saved = json.loads((run / "projected_frames.json").read_text())
        retained = positions(FrameSampleDataset.model_validate(saved["dataset"]))
        row["point_error_evaluation"] = retained_error_evaluation(
            baseline_cache[row["case_path"]], retained, truth[row["site_id"]]
        )
        if row["downstream_available_source"]:
            metrics = evaluator.evaluate_saved_robustness(
                run,
                source_map[row["site_id"]]["truth_path"],
                case_path / "input/projection_context.json",
                coverage_epsilon=EPSILON,
            )
            row["metrics_status"], row["metrics"] = metrics["status"], metrics["summaries"]
        else:
            row["metrics_status"], row["metrics"] = "NOT_RUN_POINT_ONLY", None
        after = {name: digest(run / name) for name in row["inference_artifact_sha256"]}
        if after != row["inference_artifact_sha256"]:
            raise RuntimeError("evaluation changed frozen inference artifacts")
        row["inference_unchanged_after_evaluation"] = True
    by_case = {
        r["case_path"]: r["downstream"].get("gap_window")
        for r in rows
        if r["variant"] == "A_BASELINE"
    }
    for row in rows:
        row["original_baseline_gap_window"] = by_case[row["case_path"]]
        actual = row["downstream"].get("gap_window")
        row["gap_window_changed"] = actual != by_case[row["case_path"]]


def representative_checks(sources: list[dict], rows: list[dict], output: Path) -> list[dict]:
    adapter, sensitivity = (
        module("run_projection_mitigation_downstream"),
        module("sweep_projection_downstream"),
    )
    evaluator = module("evaluate_pilot_robustness")
    selection = [
        ("office", "noise_0_seed_20261006", "A_BASELINE"),
        ("office", "noise_0_seed_20261006", "C_REJECT_STANDARD"),
        ("corridor", "noise_0p25_seed_20261006", "D_LOCAL_BINDING"),
    ]
    checks = []
    for site, name, variant in selection:
        row = next(
            r for r in rows if (r["site_id"], r["case_id"], r["variant"]) == (site, name, variant)
        )
        case_path, run = output / row["case_path"], output / row["run_path"]
        paths = tuple(
            case_path / "input" / f
            for f in ("observations.json", "projection_context.json", "config.json")
        )
        context = PilotInferenceContext.model_validate_json(paths[1].read_bytes())
        scenario = module("run_pilot_robustness").RobustnessScenario.model_validate_json(
            paths[2].read_bytes()
        )
        dataset = FrameSampleDataset.model_validate(
            json.loads((run / "projected_frames.json").read_text())["dataset"]
        )
        source = next(s for s in sources if s["site_id"] == site)
        truth_path = source["truth_path"]
        before_truth = digest(truth_path)
        poisoned = json.loads(truth_path.read_text())
        for sample in poisoned["samples"]:
            sample["position"] = [
                v + d for v, d in zip(sample["position"], (10000, -20000, 30000), strict=True)
            ]
        poison_path = case_path / variant / "evaluation_only/poisoned_ground_truth.json"
        write_json(poison_path, poisoned)
        equal = {}
        for kind in ("repeat", "poison"):
            destination = case_path / variant / (kind + "_run")
            with sensitivity.inference_read_guard(paths, destination):
                original_2d = PilotObservationExport.model_validate_json(paths[0].read_bytes())
                replay_context = PilotInferenceContext.model_validate_json(paths[1].read_bytes())
                replay = project_pilot_observations(original_2d, replay_context)
                policy = module("projection_mitigation_policy")
                if variant == "D_LOCAL_BINDING":
                    local = policy.bind_local_landmark_plane(replay_context, source["receipt"])
                    replay_context = PilotInferenceContext.model_validate(
                        {
                            **replay_context.model_dump(mode="json"),
                            "plane": local.model_dump(),
                        }
                    )
                    replay = project_pilot_observations(original_2d, replay_context)
                camera_map = {c.camera_id: c for c in replay_context.cameras}
                mode = {
                    "C_REJECT_STANDARD": "STANDARD",
                    "C_REJECT_EXTREME_ONLY": "EXTREME_ONLY",
                }.get(variant, "NONE")
                mask = {}
                for frame in original_2d.frames:
                    if frame.status != VisibilityStatus.OBSERVED:
                        continue
                    diagnostic = policy.diagnose_sample(
                        camera_map[frame.camera_id], replay_context.plane, frame
                    )
                    decision = policy.classify(diagnostic, rejection_mode=mode)
                    mask[key(frame)] = decision["accepted"]
                replay = adapter.adapt_projected_frames(replay, mask)
                if replay.model_dump(mode="json") != dataset.model_dump(mode="json"):
                    raise RuntimeError("repeat/GT poison changed projection or rejection decisions")
                adapter.run_projected_downstream(replay, context, scenario, destination)
            equal[kind] = freeze(destination) == row["inference_artifact_sha256"]
            if not equal[kind]:
                raise RuntimeError("repeat/GT poison changed inference")
            if kind == "poison":
                evaluator.evaluate_saved_robustness(
                    destination, poison_path, paths[1], coverage_epsilon=EPSILON
                )
                if any(
                    digest(destination / f) != sha
                    for f, sha in row["inference_artifact_sha256"].items()
                ):
                    raise RuntimeError("poison evaluation changed inference")
        if digest(truth_path) != before_truth:
            raise RuntimeError("original evaluation truth changed")
        checks.append(
            {
                "label": PILOT_LABEL,
                "site_id": site,
                "case_id": name,
                "variant": variant,
                "repeat_byte_equal": equal["repeat"],
                "poison_byte_equal": equal["poison"],
                "full_projection_policy_replayed": True,
                "original_truth_unchanged": True,
            }
        )
    return checks


def write_table(rows: list[dict], path: Path) -> None:
    fields = (
        "site",
        "case",
        "variant",
        "kind",
        "noise_px",
        "seed",
        "calibration",
        "original",
        "accepted",
        "rejected",
        "low_confidence",
        "availability",
        "point_rms_bu",
        "point_max_bu",
        "paired_rms_reduction_pct",
        "ade_bu",
        "fde_bu",
        "minade_k3_bu",
        "minfde_k3_bu",
        "coverage_k1",
        "coverage_k2",
        "coverage_k3",
        "candidate_count",
        "termination",
        "failed_layer",
        "metrics_status",
        "gap_window_changed",
        "projection_stage_ms",
        "downstream_ms",
    )
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            errors, metrics = row["point_error_evaluation"], row["metrics"]
            first, third = (metrics[0], metrics[2]) if metrics else ({}, {})
            writer.writerow(
                dict(
                    zip(
                        fields,
                        (
                            row["site_id"],
                            row["case_id"],
                            row["variant"],
                            row["treatment"]["kind"],
                            row["treatment"]["noise_halfwidth_px"],
                            row["treatment"]["seed"],
                            row["treatment"]["calibration_variant"],
                            row["original_visible_count"],
                            row["accepted_count"],
                            row["rejected_count"],
                            row["low_confidence_count"],
                            errors["availability"],
                            errors["retained_error"]["rms_bu"],
                            errors["retained_error"]["max_bu"],
                            errors["paired_rms_reduction_percent"],
                            first.get("ade_first_primary_scene_units"),
                            first.get("fde_first_primary_scene_units"),
                            third.get("min_ade_at_k_scene_units"),
                            third.get("min_fde_at_k_scene_units"),
                            *(
                                (m["coverage_at_k"] for m in metrics)
                                if metrics
                                else (None, None, None)
                            ),
                            row["downstream"]["candidate_count"],
                            row["downstream"]["termination_reason"],
                            row["downstream"].get("failed_stage"),
                            row["metrics_status"],
                            row["gap_window_changed"],
                            row["runtime"]["effective_projection_stage_seconds"] * 1000,
                            row["runtime"]["downstream_seconds"] * 1000,
                        ),
                        strict=True,
                    )
                )
            )


def run_comparison(inventory: Path, output: Path) -> dict[str, Any]:
    if not output.is_dir() or not (output / "protocol.json").is_file():
        raise ValueError("experiment requires an existing predeclared protocol directory")
    if (output / "cases").exists() or (output / "mitigation_results.json").exists():
        raise FileExistsError("never overwrite an existing experiment")
    protocol = json.loads((output / "protocol.json").read_text())
    if (
        protocol.get("label") != PILOT_LABEL
        or protocol["noise_halfwidths_pixels"] != list(NOISE_LEVELS)
        or protocol["seeds"] != list(SEEDS)
    ):
        raise ValueError("predeclared controls differ from fixed experiment")
    # Import every inference dependency before the runtime file-read guard begins.
    for name in (
        "projection_mitigation_policy",
        "run_projection_mitigation_downstream",
        "sweep_projection_downstream",
        "run_pilot_robustness",
        "projection_conditioning",
    ):
        module(name)
    policy_module = module("projection_mitigation_policy")
    declared_policy = policy_module.ConditioningPolicy.model_validate(protocol["policy"])
    if (
        declared_policy != policy_module.ConditioningPolicy()
        or protocol["calibration_variants"] != list(CALIBRATION_IDS)
        or protocol["implemented_variants"] != list(VARIANTS)
        or protocol["school_authority_unavailable_variants"] != list(UNAVAILABLE)
        or protocol["coverage_epsilon_scene_units"] != EPSILON
    ):
        raise ValueError("predeclared policy, calibration, variant or epsilon differs")
    policy_module._conditioning()
    sources = load_sources(inventory, output)
    rows = []
    for source in sources:
        for case in cases(source):
            rows.extend(run_case(source, case, output))
        print(f"PILOT frozen source={source['site_id']} cases=31", flush=True)
    frozen_projection = {
        str(p.relative_to(output)): digest(p)
        for p in sorted((output / "cases").rglob("conditioning.json"))
    }
    frozen_projection.update(
        {
            str(p.relative_to(output)): digest(p)
            for p in sorted((output / "cases").rglob("baseline_projected_reference.json"))
        }
    )
    write_json(
        output / "projection_freeze_before_gt.json",
        {
            "label": PILOT_LABEL,
            "ground_truth_read": False,
            "artifacts": frozen_projection,
            "frozen_variant_count": len(rows),
        },
    )
    # The first evaluation GT access occurs only here, after ALL policies and runs are saved.
    evaluate_rows(sources, rows, output)
    checks = representative_checks(sources, rows, output)
    for source in sources:
        if any(digest(Path(p)) != sha for p, sha in source["input_digests"].items()):
            raise RuntimeError("original source 2D/context/geometry metadata changed")
    if any(digest(output / p) != sha for p, sha in frozen_projection.items()):
        raise RuntimeError("evaluation changed frozen conditioning/projection references")
    synthetic = module("projection_surface_controls").synthetic_surface_controls()
    write_json(output / "synthetic_surface_controls.json", synthetic)
    result = {
        "label": PILOT_LABEL,
        "scope": SCOPE,
        "checkpoint_commit": protocol["checkpoint_commit"],
        "physical_validity": "PARTIAL_PROVISIONAL",
        "coordinate_units": "BLENDER_SCENE_UNITS",
        "coverage_epsilon_scene_units": EPSILON,
        "formal_cases_1_3_executed": False,
        "graph_top_k_metric_or_benchmark_semantics_modified": False,
        "variant_count": len(rows),
        "downstream_attempt_count": sum(r["downstream_available_source"] for r in rows),
        "policy": module("projection_mitigation_policy").ConditioningPolicy().model_dump(),
        "rows": rows,
        "representative_checks": checks,
        "school_surface_variants": [
            {
                "variant": v,
                "status": "UNAVAILABLE_AUTHORITY",
                "point_error": None,
                "metrics": None,
                "rejection_count": None,
                "reason": (
                    "ZERO_APPROVED_SOURCE_BOUND_SCHOOL_SURFACES_AND_TARGET_REFERENCE_BINDINGS"
                ),
            }
            for v in UNAVAILABLE
        ],
        "termination_counts": dict(
            Counter(
                r["downstream"]["termination_reason"]
                for r in rows
                if r["downstream_available_source"]
            )
        ),
        "gt_first_access_after_all_inference_frozen": True,
        "all_projection_references_unchanged_after_evaluation": True,
        "original_input_sha256": {p: sha for s in sources for p, sha in s["input_digests"].items()},
        "implementation_bug_found": False,
    }
    write_json(output / "mitigation_results.json", result)
    write_table(rows, output / "mitigation_table.csv")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_comparison(args.inventory, args.output)
    print(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "variant_count": result["variant_count"],
                "termination_counts": result["termination_counts"],
            }
        )
    )


if __name__ == "__main__":
    main()
