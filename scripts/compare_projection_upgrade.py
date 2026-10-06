"""PILOT preflight-gated additive model comparison; no core replacement or GT selection."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import time
from collections import Counter
from pathlib import Path

import numpy as np

from amidst.datasets.pilot import (
    PILOT_LABEL,
    PilotInferenceContext,
    PilotObservationExport,
    project_pilot_observations,
)
from amidst.domain.evidence import VisibilityStatus
from amidst.storage.json_files import write_json

_compare_spec = importlib.util.spec_from_file_location(
    "model_upgrade_existing_tools", Path(__file__).with_name("compare_projection_mitigations.py")
)
assert _compare_spec and _compare_spec.loader
tools = importlib.util.module_from_spec(_compare_spec)
_compare_spec.loader.exec_module(tools)

SITES = ("office", "corridor", "auditorium", "classroom101")
ENDPOINTS = {"office": (4.0, 9.0), "corridor": (3.4, 9.4), "auditorium": (9.2, 9.6)}


def classify_upgrade(
    *,
    same_evidence_gain: bool,
    authority_sufficient: bool,
    gt_isolation_passed: bool,
    downstream_acceptable: bool,
) -> str:
    """Gate validation on authority, isolation, and usable downstream evidence."""
    if all(
        (
            same_evidence_gain,
            authority_sufficient,
            gt_isolation_passed,
            downstream_acceptable,
        )
    ):
        return "MODEL_UPGRADE_VALIDATED"
    if same_evidence_gain and gt_isolation_passed:
        return "MODEL_UPGRADE_PROMISING"
    return "FIXED_PLANE_ONLY_INSUFFICIENT"


def treatment_cases():
    for seed in tools.SEEDS:
        for amount in tools.NOISE_LEVELS:
            yield (
                f"noise_{amount:g}_seed_{seed}".replace(".", "p"),
                {
                    "kind": "PIXEL_NOISE",
                    "noise_halfwidth_px": amount,
                    "seed": seed,
                    "calibration_variant": None,
                },
            )
    for variant in tools.CALIBRATION_IDS:
        yield (
            "cal_" + variant.replace(":", "_").replace(".", "p"),
            {
                "kind": "CALIBRATION_COPY",
                "noise_halfwidth_px": 0,
                "seed": tools.SEEDS[0],
                "calibration_variant": variant,
            },
        )


def assumptions(treatment: dict) -> dict:
    variant = treatment["calibration_variant"]
    parameter, amount = variant.split(":") if variant else (None, "0")
    return {
        "pixel_sigma_px": treatment["noise_halfwidth_px"] / math.sqrt(3),
        "calibration_parameter": parameter,
        "calibration_sigma": abs(float(amount)) / math.sqrt(3),
    }


def conditional_covariance_evaluation(sidecars: list[dict], truth: dict[float, tuple]) -> dict:
    """Evaluate only modeled covariance support, explicitly excluding full-3D calibration."""
    inside, valid, unsupported, radii = 0, 0, [], []
    thresholds = {1: 3.841458820694124, 2: 5.991464547107979, 3: 7.814727903251179}
    states = Counter()
    for sidecar in sidecars:
        states[sidecar["use_state"]] += 1
        if sidecar["covariance_bu2"] is None or sidecar["covariance_rank"] == 0:
            continue
        covariance = np.asarray(sidecar["covariance_bu2"])
        eigenvalues, basis = np.linalg.eigh(covariance)
        active = eigenvalues > max(float(eigenvalues[-1]) * 1e-10, 1e-24)
        rank = int(np.count_nonzero(active))
        if rank == 0:
            continue
        point = sidecar["projected_point"]
        error = np.asarray(point["world_position"]) - truth[float(point["timestamp"])]
        coefficients = basis[:, active].T @ error
        mahalanobis = float(np.sum(coefficients**2 / eigenvalues[active]))
        valid += 1
        inside += mahalanobis <= thresholds[rank]
        unsupported.append(float(np.linalg.norm(error - basis[:, active] @ coefficients)))
        radii.append(sidecar["tangential_radius_95_bu"])
    return {
        "label": PILOT_LABEL,
        "purpose": "POST_FREEZE_CONDITIONAL_SUBSPACE_EVALUATION",
        "conditional_subspace_95_coverage": inside / valid if valid else None,
        "evaluated_covariance_count": valid,
        "inside_count": inside,
        "use_state_counts": dict(states),
        "unmodeled_residual_stats": tools.stats(unsupported),
        "nominal_radius_stats": tools.stats(radii),
        "full_3d_calibration": "UNVALIDATED_UNMODELED_HEIGHT_AND_UNMEASURED_UNCERTAINTY",
        "plane_normal_uncertainty_modeled": False,
        "zero_covariance_is_not_perfect_certainty": True,
        "coverage_of_3_fixed_seeds_is_not_probability_validation": True,
    }


def multiview_evaluation(
    requests: list[dict],
    baseline: dict,
    truth: dict[float, tuple],
) -> dict:
    individual, mean_errors, triangulated, baseline_means = [], [], [], []
    for request in requests:
        for hypothesis in request["hypotheses"]:
            refs = hypothesis["evidence_refs"]
            keys = [(r["camera_id"], r["frame_id"], float(r["timestamp"])) for r in refs]
            if not all(k in baseline for k in keys):
                raise ValueError("paired evaluation cannot invent missing camera evidence")
            timestamp = float(refs[0]["timestamp"])
            points = [np.asarray(baseline[k]) for k in keys]
            individual.extend(math.dist(p, truth[timestamp]) for p in points)
            mean = np.mean(points, axis=0)
            baseline_means.append(mean.tolist())
            mean_errors.append(math.dist(mean, truth[timestamp]))
            triangulated.append(math.dist(hypothesis["world_position"], truth[timestamp]))
    raw, paired, result = (
        tools.stats(individual),
        tools.stats(mean_errors),
        tools.stats(triangulated),
    )
    reduction = None
    if paired["rms_bu"] and result["rms_bu"] is not None:
        reduction = 100 * (1 - result["rms_bu"] / paired["rms_bu"])
    return {
        "paired_individual_plane_stats": raw,
        "paired_mean_plane_stats": paired,
        "triangulated_stats": result,
        "same_evidence_reduction_vs_pair_mean_pct": reduction,
        "paired_timestamp_count": len(triangulated),
        "baseline_pair_mean_is_predeclared_equal_average_not_gt_camera_selection": True,
    }


def case_inference(
    context: PilotInferenceContext, evidence: PilotObservationExport, treatment: dict
) -> dict:
    baseline = project_pilot_observations(evidence, context)
    policy = tools.module("projection_mitigation_policy")
    multiview = tools.module("projection_multiview_model")
    uncertainty = tools.module("projection_uncertainty_model")
    cameras = {c.camera_id: c for c in context.cameras}
    visible = [f for f in evidence.frames if f.status == VisibilityStatus.OBSERVED]
    diagnostics = [policy.diagnose_sample(cameras[f.camera_id], context.plane, f) for f in visible]
    sidecars = [
        uncertainty.propagate_fixed_plane(
            cameras[f.camera_id], context.plane, f, **assumptions(treatment)
        )
        for f in visible
    ]
    if any(
        s["projected_point"] != d["projected_point"]
        for s, d in zip(sidecars, diagnostics, strict=True)
    ):
        raise RuntimeError("conditioning/uncertainty sidecar changed baseline coordinates")
    grouped = {}
    for frame in evidence.frames:
        grouped.setdefault(float(frame.timestamp), []).append(frame)
    requests = [
        multiview.triangulate_exact_time(context, tuple(frames))
        for _, frames in sorted(grouped.items())
    ]
    return {
        "label": PILOT_LABEL,
        "source_asset_sha256": context.source_asset_sha256,
        "baseline_dataset": baseline.model_dump(mode="json"),
        "conditioning": diagnostics,
        "uncertainty": sidecars,
        "multiview": requests,
        "source_id": context.source_id,
        "site_id": context.site_id,
        "ground_truth_read": False,
        "baseline_coordinates_quality_unchanged": True,
    }


def run_models(input_root: Path, output: Path) -> tuple[list[dict], dict]:
    from amidst.domain.dataset import FrameSampleDataset

    adapter = tools.module("run_projection_mitigation_downstream")
    sensitivity = tools.module("sweep_projection_downstream")
    configuration = tools.module("run_pilot_robustness")
    rows, inputs = [], {}
    for site in SITES:
        for name, treatment in treatment_cases():
            source = input_root / "cases" / site / name / "input"
            paths = tuple(
                source / p for p in ("observations.json", "projection_context.json", "config.json")
            )
            destination = output / "cases" / site / name
            destination.mkdir(parents=True, exist_ok=False)
            for p in paths:
                inputs[str(p)] = tools.digest(p)
            started = time.perf_counter()
            with sensitivity.inference_read_guard(paths, destination) as reads:
                evidence = PilotObservationExport.model_validate_json(paths[0].read_bytes())
                context = PilotInferenceContext.model_validate_json(paths[1].read_bytes())
                if tools.digest(paths[0]) != context.observations_sha256:
                    raise ValueError("strict 2D content binding differs")
                model = case_inference(context, evidence, treatment)
                write_json(destination / "models.json", model)
                if site in ("office", "corridor"):
                    scenario = configuration.RobustnessScenario.model_validate_json(
                        paths[2].read_bytes()
                    )
                    status = adapter.run_projected_downstream(
                        FrameSampleDataset.model_validate(model["baseline_dataset"]),
                        context,
                        scenario,
                        destination / "baseline_downstream",
                    )
                else:
                    status = tools.point_only_status(site)
            duration = time.perf_counter() - started
            grouped_observed = Counter(
                float(f.timestamp) for f in evidence.frames if f.status == VisibilityStatus.OBSERVED
            )
            accepted = [r for r in model["multiview"] if r["hypotheses"]]
            endpoint_times = ENDPOINTS.get(site, ())
            endpoint_usable = sum(
                any(
                    float(r["timestamp"]) == t and r["hypotheses"]
                    for r in model["multiview"]
                    if r["timestamp"] is not None
                )
                for t in endpoint_times
            )
            rows.append(
                {
                    "label": PILOT_LABEL,
                    "site_id": site,
                    "case_id": name,
                    "treatment": treatment,
                    "baseline_downstream": {"status": status},
                    "multiview": {
                        "accepted_timestamp_count": len(accepted),
                        "eligible_timestamp_count": sum(v >= 2 for v in grouped_observed.values()),
                        "original_visible_timestamp_count": len(grouped_observed),
                        "hypothesis_count": sum(len(r["hypotheses"]) for r in accepted),
                        "gap_endpoint_pairs": endpoint_usable,
                        "gap_downstream_status": "NOT_RUN_NO_SYNCHRONIZED_ENDPOINTS",
                        "new_graph_contract_integration": False,
                        "camera_pair_selection_uses_gt": False,
                    },
                    "runtime": {
                        "model_and_baseline_downstream_seconds": duration,
                        "measurement": "SINGLE_MACHINE_DIAGNOSTIC_NOT_BENCHMARK",
                    },
                    "case_path": str(destination.relative_to(output)),
                    "inputs": [str(p) for p in paths],
                    "input_sha256": {str(p): inputs[str(p)] for p in paths},
                    "runtime_reads_allowlisted": True,
                    "runtime_reads": sorted(reads),
                    "frozen_inference_sha256": tools.freeze(destination),
                }
            )
        print(f"PILOT frozen models source={site} cases=31", flush=True)
    return rows, inputs


def load_truth(inventory: Path) -> tuple[dict, dict]:
    inventory = json.loads(inventory.read_text())
    contexts = {x["source_id"]: x for x in inventory["geometry_diagnostic_inputs"]}
    truths, hashes = {}, {}
    for entry in inventory["evaluation_inputs_not_inference"]:
        context = PilotInferenceContext.model_validate_json(
            Path(contexts[entry["source_id"]]["context"]).read_bytes()
        )
        source = {
            "truth_path": Path(entry["evaluation_truth"]),
            "context": context,
            "observations": PilotObservationExport.model_validate_json(
                Path(contexts[entry["source_id"]]["observations"]).read_bytes()
            ),
        }
        truths[context.site_id] = tools.load_evaluation_truth(source)
        hashes[str(source["truth_path"])] = tools.digest(source["truth_path"])
    return truths, hashes


def local_pixel_gains(requests: list[dict], zero_requests: list[dict]) -> dict:
    baseline = {float(r["timestamp"]): r for r in zero_requests if r["hypotheses"]}
    gains = []
    for request in requests:
        if not request["hypotheses"] or float(request["timestamp"]) not in baseline:
            continue
        current = request["hypotheses"][0]
        original = baseline[float(request["timestamp"])]["hypotheses"][0]
        if current["camera_ids"] != original["camera_ids"]:
            raise ValueError("amplification requires exactly the same pair")
        uv = [v for ref in current["evidence_refs"] for v in ref["point_2d"]]
        uv0 = [v for ref in original["evidence_refs"] for v in ref["point_2d"]]
        displacement = math.dist(uv, uv0)
        if displacement:
            gains.append(
                math.dist(current["world_position"], original["world_position"]) / displacement
            )
    return {
        "basis": "SAME_PAIR_3D_DELTA_OVER_FOUR_PIXEL_COORDINATE_NORM",
        "max_bu_per_pixel": max(gains) if gains else None,
        "mean_bu_per_pixel": math.fsum(gains) / len(gains) if gains else None,
    }


def evaluate(rows: list[dict], output: Path, truths: dict) -> None:
    from amidst.domain.dataset import FrameSampleDataset

    evaluator = tools.module("evaluate_pilot_robustness")
    zero_models = {}
    for row in rows:
        if row["case_id"] == "noise_0_seed_20261006":
            zero_models[row["site_id"]] = json.loads(
                (output / row["case_path"] / "models.json").read_text()
            )
    for row in rows:
        root = output / row["case_path"]
        model = json.loads((root / "models.json").read_text())
        baseline = tools.positions(FrameSampleDataset.model_validate(model["baseline_dataset"]))
        errors = [math.dist(p, truths[row["site_id"]][k[2]]) for k, p in baseline.items()]
        row["baseline_stats"] = tools.stats(errors)
        row["multiview"].update(
            multiview_evaluation(model["multiview"], baseline, truths[row["site_id"]])
        )
        row["multiview"]["local_gain"] = local_pixel_gains(
            model["multiview"], zero_models[row["site_id"]]["multiview"]
        )
        row["uncertainty_eval"] = conditional_covariance_evaluation(
            model["uncertainty"], truths[row["site_id"]]
        )
        if row["site_id"] in ("office", "corridor"):
            truth_path = next(p for p, _ in row["_truth_paths"] if _ == row["site_id"])
            metrics = evaluator.evaluate_saved_robustness(
                root / "baseline_downstream",
                Path(truth_path),
                Path(row["inputs"][1]),
                coverage_epsilon=0.02,
            )
            row["baseline_downstream"]["metrics"] = metrics["summaries"]
            row["baseline_downstream"]["metrics_reuse_for_B_F"] = (
                "IDENTICAL_COORDINATES_NO_GRAPH_WEIGHTING_NO_SAMPLE_DELETION"
            )
        else:
            row["baseline_downstream"]["metrics"] = None
        del row["_truth_paths"]
        if any(tools.digest(root / p) != sha for p, sha in row["frozen_inference_sha256"].items()):
            raise RuntimeError("evaluation changed frozen model inference")


def repeat_poison(rows: list[dict], output: Path, truths: dict) -> list[dict]:
    guard = tools.module("sweep_projection_downstream").inference_read_guard
    checks = []
    for site in ("office", "auditorium", "classroom101"):
        row = next(
            r for r in rows if r["site_id"] == site and r["case_id"] == "noise_0p25_seed_20261006"
        )
        paths = tuple(Path(p) for p in row["inputs"])
        results = []
        for kind in ("repeat", "poison"):
            destination = output / "replay" / site / kind
            destination.mkdir(parents=True, exist_ok=False)
            if kind == "poison":
                poisoned = {
                    timestamp: tuple(
                        v + d for v, d in zip(point, (10000, -20000, 30000), strict=True)
                    )
                    for timestamp, point in truths[site].items()
                }
                write_json(
                    destination / "evaluation_only_poison.json",
                    {
                        "label": PILOT_LABEL,
                        "purpose": "GROUND_TRUTH_EVALUATION_ONLY",
                        "positions": list(poisoned.values()),
                    },
                )
            with guard(paths, destination):
                evidence = PilotObservationExport.model_validate_json(paths[0].read_bytes())
                context = PilotInferenceContext.model_validate_json(paths[1].read_bytes())
                actual = case_inference(context, evidence, row["treatment"])
                write_json(destination / "models.json", actual)
            results.append(
                tools.digest(destination / "models.json")
                == tools.digest(output / row["case_path"] / "models.json")
            )
            if not results[-1]:
                raise RuntimeError("repeat/GT poison changed model or uncertainty inference")
        checks.append(
            {
                "label": PILOT_LABEL,
                "site_id": site,
                "full_model_repeat_equal": results[0],
                "gt_poison_model_equal": results[1],
                "pair_surface_hypothesis_gt_selection": False,
            }
        )
    return checks


def surface_evaluation(surface: dict) -> dict:
    """Toy references are evaluation-only declared cases, never surface selectors."""
    cases = surface["controls"]
    unique = cases["unique_surface"]["projection_hypotheses"]
    multi = cases["multiple_surfaces"]["projection_hypotheses"]
    unique_errors = [math.dist(h["projected_point"]["world_position"], (0, 0, -10)) for h in unique]
    multi_errors = [math.dist(h["projected_point"]["world_position"], (0, 0, -20)) for h in multi]
    return {
        "label": PILOT_LABEL,
        "scope": "SYNTHETIC_FIXTURE_ONLY_NOT_SCHOOL_EFFICACY",
        "unique_surface_error_bu": unique_errors[0],
        "unique_hypothesis_count": len(unique),
        "multi_hypothesis_count": len(multi),
        "all_hypotheses_preserved": True,
        "multi_min_error_bu": min(multi_errors),
        "multi_reference_in_retained_hypotheses": 0 in multi_errors,
        "reference_used_only_after_frozen_surface_output": True,
        "same_plane_vs_surface_stability": "IDENTICAL_PLANE_NOT_CONDITIONING_CURE",
        "school_surface_status": "UNAVAILABLE_AUTHORITY",
        "graph_integration": False,
    }


def run(input_root: Path, inventory: Path, output: Path) -> dict:
    if not (output / "protocol.json").exists() or (output / "cases").exists():
        raise ValueError("require predeclared fresh experiment; never overwrite cases")
    protocol = json.loads((output / "protocol.json").read_text())
    preflight = json.loads((output / "authority_preflight.json").read_text())
    if (
        protocol["noise_halfwidths_px"] != list(tools.NOISE_LEVELS)
        or (protocol["seeds"] != list(tools.SEEDS))
        or protocol["coverage_epsilon_bu"] != 0.02
    ):
        raise ValueError("predeclared noise/seed/epsilon differs")
    for name in (
        "projection_multiview_model",
        "projection_uncertainty_model",
        "projection_mitigation_policy",
        "sweep_projection_downstream",
        "run_projection_mitigation_downstream",
        "run_pilot_robustness",
    ):
        tools.module(name)
    tools.module("projection_uncertainty_model")._policy()._conditioning()
    rows, inputs = run_models(input_root, output)
    write_json(output / "inference_rows_before_gt.json", {"label": PILOT_LABEL, "rows": rows})
    surface = tools.module("projection_surface_controls").synthetic_surface_controls()
    write_json(output / "surface_models.json", surface)
    write_json(
        output / "inference_freeze_before_gt.json",
        {
            "label": PILOT_LABEL,
            "ground_truth_read": False,
            "cases": len(rows),
            "artifacts": {str(output / r["case_path"]): r["frozen_inference_sha256"] for r in rows},
            "surface_models_sha256": tools.digest(output / "surface_models.json"),
        },
    )
    # First GT access occurs only after every model and surface hypothesis is frozen.
    truths, truth_hashes = load_truth(inventory)
    original = json.loads(inventory.read_text())
    truth_paths = [
        (x["evaluation_truth"], x["source_id"]) for x in original["evaluation_inputs_not_inference"]
    ]
    for row in rows:
        row["_truth_paths"] = truth_paths
    evaluate(rows, output, truths)
    checks = repeat_poison(rows, output, truths)
    surface_result = surface_evaluation(surface)
    write_json(output / "surface_evaluation.json", surface_result)
    for p, sha in {**inputs, **truth_hashes}.items():
        if tools.digest(Path(p)) != sha:
            raise RuntimeError("source or evaluation truth changed")
    promising = any(
        r["multiview"]["same_evidence_reduction_vs_pair_mean_pct"] is not None
        and r["multiview"]["same_evidence_reduction_vs_pair_mean_pct"] > 0
        for r in rows
    )
    result = {
        "label": PILOT_LABEL,
        "scope": protocol["scope"],
        "checkpoint_commit": protocol["checkpoint_commit"],
        "classification": classify_upgrade(
            same_evidence_gain=promising,
            authority_sufficient=all(item["status"] == "APPROVED" for item in preflight["items"]),
            gt_isolation_passed=bool(checks)
            and all(
                item["gt_poison_model_equal"] and item["full_model_repeat_equal"] for item in checks
            ),
            downstream_acceptable=False,  # No synchronized GAP endpoints or C Graph adapter.
        ),
        "model_upgrade_validated": False,
        "authority_preflight": preflight,
        "rows": rows,
        "representative_checks": checks,
        "surface_control_evaluation": surface_result,
        "all_model_outputs_frozen_before_gt": True,
        "original_inputs_sha256": inputs,
        "evaluation_truth_sha256": truth_hashes,
        "formal_cases_1_3_executed": False,
        "core_observation_graph_metric_contracts_modified": False,
        "coverage_epsilon_bu": 0.02,
        "physical_validity": "PARTIAL_PROVISIONAL",
    }
    write_json(output / "upgrade_results.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mitigation-input", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.mitigation_input, args.inventory, args.output)
    print(
        json.dumps(
            {
                "label": PILOT_LABEL,
                "cases": len(result["rows"]),
                "classification": result["classification"],
            }
        )
    )


if __name__ == "__main__":
    main()
