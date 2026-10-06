"""Report saved PILOT mitigation trials without opening GT or original inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABEL = "PILOT / SYNTHETIC SAMPLE"
VARIANTS = (
    "A_BASELINE", "B_CONFIDENCE", "C_REJECT_STANDARD",
    "C_REJECT_EXTREME_ONLY", "D_LOCAL_BINDING",
)
SHORT = {
    "A_BASELINE": "A baseline", "B_CONFIDENCE": "B confidence",
    "C_REJECT_STANDARD": "C standard", "C_REJECT_EXTREME_ONLY": "C extreme only",
    "D_LOCAL_BINDING": "D local binding",
}
COLORS = {
    "A_BASELINE": "#252525", "B_CONFIDENCE": "#d89600",
    "C_REJECT_STANDARD": "#b53037", "C_REJECT_EXTREME_ONLY": "#247aae",
    "D_LOCAL_BINDING": "#27835c",
}


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _weighted_errors(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    summaries = [r["point_error_evaluation"][field] for r in rows]
    count = sum(s["count"] for s in summaries)
    nonempty = [s for s in summaries if s["count"]]
    return {
        "count": count,
        "mean_bu": _ratio(math.fsum(s["mean_bu"] * s["count"] for s in nonempty), count),
        "rms_bu": math.sqrt(
            math.fsum(s["rms_bu"] ** 2 * s["count"] for s in nonempty) / count
        ) if count else None,
        "max_bu": max((s["max_bu"] for s in nonempty), default=None),
        "aggregation": "POINT_TRIAL_COUNT_WEIGHTED_REPEATED_TREATMENTS_NOT_DISTINCT_POINTS",
    }


def _runtime_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "median_ms": None, "q1_ms": None, "q3_ms": None}
    ordered = sorted(values)
    mid = len(ordered) // 2
    return {
        "count": len(ordered), "median_ms": median(ordered) * 1000,
        "q1_ms": median(ordered[:mid] or ordered) * 1000,
        "q3_ms": median(ordered[(mid + len(ordered) % 2):] or ordered) * 1000,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool errors by point count; keep missing downstream metrics unavailable."""
    original = sum(r["original_visible_count"] for r in rows)
    accepted = sum(r["accepted_count"] for r in rows)
    attempted = [r for r in rows if r["downstream_available_source"]]
    computed = [r for r in attempted if r["metrics_status"] == "COMPUTED"]
    coverage = {}
    for k in (1, 2, 3):
        values = [r["metrics"][k - 1]["coverage_at_k"] for r in computed]
        coverage[str(k)] = {
            "true_count": sum(v is True for v in values),
            "false_count": sum(v is False for v in values),
            "computed_count": len(values),
            "unavailable_count": len(attempted) - len(values),
            "true_fraction_among_computed": _ratio(sum(v is True for v in values), len(values)),
        }
    metric_names = {
        "ade": "ade_first_primary_scene_units", "fde": "fde_first_primary_scene_units",
        "min_ade_at_k": "min_ade_at_k_scene_units",
        "min_fde_at_k": "min_fde_at_k_scene_units",
    }
    metrics = {}
    for k in (1, 2, 3):
        metrics[str(k)] = {
            name: {
                "computed_count": len(computed),
                "mean_bu": math.fsum(r["metrics"][k - 1][source_field] for r in computed)
                / len(computed) if computed else None,
                "max_bu": max((r["metrics"][k - 1][source_field] for r in computed), default=None),
            } for name, source_field in metric_names.items()
        }
    retained = _weighted_errors(rows, "retained_error")
    paired = _weighted_errors(rows, "baseline_on_identical_retained_cohort")
    delta = None
    if retained["rms_bu"] is not None and paired["rms_bu"] is not None:
        delta = paired["rms_bu"] - retained["rms_bu"]
    return {
        "row_count": len(rows),
        "original_visible_point_trials": original, "accepted_point_trials": accepted,
        "rejected_point_trials": sum(r["rejected_count"] for r in rows),
        "low_confidence_point_trials": sum(r["low_confidence_count"] for r in rows),
        "requires_review_point_trials": sum(r["requires_review_count"] for r in rows),
        "availability": _ratio(accepted, original),
        "all_original_baseline_error": _weighted_errors(rows, "all_original_baseline_error"),
        "retained_error": retained, "baseline_on_identical_retained_cohort": paired,
        "paired_rms_improvement_bu": delta,
        "paired_rms_reduction_percent": (
            100 * delta / paired["rms_bu"] if delta is not None and paired["rms_bu"] else None
        ),
        "downstream_attempt_count": len(attempted),
        "downstream_complete_count": sum(
            r["downstream"]["termination_reason"] == "COMPLETE" for r in attempted
        ),
        "metrics_computed_count": len(computed),
        "metrics_unavailable_count": len(attempted) - len(computed),
        "termination_counts": dict(Counter(
            r["downstream"]["termination_reason"] for r in attempted
        )),
        "failure_reason_counts": dict(Counter(
            r["downstream"]["reason"] for r in attempted
            if r["downstream"]["termination_reason"] != "COMPLETE"
        )),
        "top_k_candidate_counts": dict(Counter(
            str(r["downstream"]["candidate_count"]) for r in attempted
        )),
        "gap_window_changed_count": sum(r["gap_window_changed"] for r in attempted),
        "coverage": coverage, "metrics_bu_on_computed_runs_only": metrics,
        "metric_comparison_caveat": "RETAINED_GAP_WINDOWS_CAN_DIFFER_NOT_PAIRED_ACCURACY_GAIN",
        "projection_stage_runtime": _runtime_summary([
            r["runtime"]["effective_projection_stage_seconds"] for r in rows
        ]),
        "projection_seconds_per_original_visible_trial": _runtime_summary([
            r["runtime"]["effective_projection_stage_seconds"] / r["original_visible_count"]
            for r in rows if r["original_visible_count"]
        ]),
        "downstream_runtime": _runtime_summary([
            r["runtime"]["downstream_seconds"] for r in attempted
        ]),
    }


def summarize(data: dict[str, Any], input_sha256: str) -> dict[str, Any]:
    rows = data["rows"]
    if data.get("label") != LABEL or len(rows) != 620:
        raise ValueError("expected 620 labeled, frozen pilot variant rows")
    if data["variant_count"] != 620 or data["downstream_attempt_count"] != 310:
        raise ValueError("fixed four-source matrix and two-source downstream counts differ")
    if set(r["variant"] for r in rows) != set(VARIANTS):
        raise ValueError("unexpected mitigation variants")
    if any(not r["inference_unchanged_after_evaluation"] for r in rows):
        raise ValueError("inference must remain frozen after evaluation")
    if any(r["ground_truth_read_during_inference"] for r in rows):
        raise ValueError("GT isolation must hold")
    by_variant = {v: aggregate([r for r in rows if r["variant"] == v]) for v in VARIANTS}
    baseline_cost = {
        (r["site_id"], r["case_id"]): r["runtime"]["effective_projection_stage_seconds"]
        for r in rows if r["variant"] == "A_BASELINE"
    }
    for variant in VARIANTS:
        selected = [r for r in rows if r["variant"] == variant]
        deltas = [r["runtime"]["effective_projection_stage_seconds"]
                  - baseline_cost[(r["site_id"], r["case_id"])] for r in selected]
        ratios = [r["runtime"]["effective_projection_stage_seconds"]
                  / baseline_cost[(r["site_id"], r["case_id"])] for r in selected
                  if baseline_cost[(r["site_id"], r["case_id"])] > 0]
        by_variant[variant]["paired_projection_runtime_overhead"] = {
            "case_count": len(selected), "median_extra_ms": median(deltas) * 1000,
            "median_cost_ratio": median(ratios) if ratios else None,
            "scope": "SHARED_ACCOUNTING_SINGLE_MACHINE_NOT_DEPLOYMENT_BENCHMARK",
        }
    representative = next(r for r in rows if (
        r["site_id"] == "office" and r["variant"] == "C_REJECT_STANDARD"
        and r["treatment"]["kind"] == "PIXEL_NOISE"
        and r["treatment"]["noise_halfwidth_px"] == .25
        and r["treatment"]["seed"] == 20261006
    ))
    counterexamples = [r for r in rows if (
        r["site_id"] == "classroom101" and r["variant"] == "B_CONFIDENCE"
        and r["treatment"]["kind"] == "PIXEL_NOISE"
        and r["treatment"]["noise_halfwidth_px"] == .25
    )]
    classroom_example = {
        "site_id": "classroom101", "noise_halfwidth_px": .25,
        "seed_count": len(counterexamples),
        "low_confidence_count": sum(r["low_confidence_count"] for r in counterexamples),
        "max_retained_point_error_bu": max(
            r["point_error_evaluation"]["retained_error"]["max_bu"] for r in counterexamples
        ),
        "purpose": "POST_FREEZE_EVALUATION_COUNTEREXAMPLE_NOT_GT_SELECTED_INFERENCE",
    }
    sites = sorted({r["site_id"] for r in rows})
    if len(sites) != 4 or any(s["row_count"] != 124 for s in by_variant.values()):
        raise ValueError("expected four sources and 31 cases per source/variant")
    noise = sorted({r["treatment"]["noise_halfwidth_px"] for r in rows
                    if r["treatment"]["kind"] == "PIXEL_NOISE"})
    noise_summary = [{
        "noise_halfwidth_px": amount, "variant": variant,
        **aggregate([r for r in rows if r["variant"] == variant
                     and r["treatment"]["kind"] == "PIXEL_NOISE"
                     and r["treatment"]["noise_halfwidth_px"] == amount]),
    } for amount in noise for variant in VARIANTS]
    calibration_ids = sorted({r["treatment"]["calibration_variant"] for r in rows
                              if r["treatment"]["kind"] == "CALIBRATION_COPY"})
    calibration_summary = [{
        "calibration_variant": calibration, "variant": variant,
        **aggregate([r for r in rows if r["variant"] == variant
                     and r["treatment"]["calibration_variant"] == calibration]),
    } for calibration in calibration_ids for variant in VARIANTS]
    largest_delta = max(
        abs(r["point_error_evaluation"]["retained_error"]["rms_bu"]
            - r["point_error_evaluation"]["baseline_on_identical_retained_cohort"]["rms_bu"])
        for r in rows if r["point_error_evaluation"]["retained_count"]
    )
    return {
        "label": LABEL, "scope": data["scope"], "physical_validity": "PARTIAL_PROVISIONAL",
        "input_mitigation_results_sha256": input_sha256,
        "checkpoint_commit": data["checkpoint_commit"],
        "variant_row_count": len(rows), "downstream_attempt_count": 310,
        "sources": sites, "variants": by_variant,
        "noise_summary": noise_summary, "calibration_summary": calibration_summary,
        "per_site_summary": [{
            "site_id": site, "variant": variant,
            **aggregate([r for r in rows if r["site_id"] == site and r["variant"] == variant]),
        } for site in sites for variant in VARIANTS],
        "largest_absolute_per_case_paired_rms_change_bu": largest_delta,
        "office_noise_quarter_px_rejection_example": representative["point_error_evaluation"],
        "confidence_counterexample": classroom_example,
        "school_surface_variants": data["school_surface_variants"],
        "surface_controls": "FIVE_TOY_AUTHORITY_CONTROLS_SEPARATE_NOT_SCHOOL_EFFICACY",
        "policy": data["policy"],
        "coverage_epsilon_scene_units_unchanged": data["coverage_epsilon_scene_units"],
        "representative_checks": data["representative_checks"],
        "best_practical_diagnostic": "B_CONFIDENCE_PRESERVES_EVIDENCE_NOT_POINT_CORRECTION",
        "accepted_point_accuracy_mitigation": (
            "NONE_MATERIAL_IN_TESTED_VARIANTS" if largest_delta <= 1e-8
            else "PAIRED_RESULTS_REQUIRE_REVIEW_NO_AUTOMATIC_BEST_SELECTION"
        ),
        "implementation_bug_found": data["implementation_bug_found"],
        "calibration_uncertainty_measured": False,
        "formal_case_readiness": "NOT_READY_AUTHORITY_AND_UNCERTAINTY_UNRESOLVED",
        "projection_bottleneck": "REMAINS_FOR_TESTED_FIXED_PLANE_PILOT_GEOMETRY",
        "missing_metrics_are_null_not_zero": True,
        "runtime_interpretation": "SHARED_ACCOUNTING_SINGLE_MACHINE_DIAGNOSTIC_NOT_BENCHMARK",
        "confidence_interpretation": "HEURISTIC_NOT_PROBABILITY_OR_ACCURACY_GUARANTEE",
    }


def _finite(value: float | None) -> float:
    return value if value is not None else float("nan")


def _save_plot(fig: Any, path: Path) -> None:
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def charts(summary: dict[str, Any], output: Path) -> list[str]:
    files = []
    fig, axes = plt.subplots(2, 1, figsize=(10.5, 8), sharex=True)
    for variant in ("A_BASELINE", "C_REJECT_STANDARD", "C_REJECT_EXTREME_ONLY"):
        selected = [s for s in summary["noise_summary"] if s["variant"] == variant]
        x = [s["noise_halfwidth_px"] for s in selected]
        axes[0].plot(x, [_finite(s["retained_error"]["rms_bu"]) for s in selected],
                     marker="o", color=COLORS[variant], label=SHORT[variant])
        axes[1].plot(x, [_finite(s["availability"]) for s in selected],
                     marker="o", color=COLORS[variant], label=SHORT[variant])
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Retained point RMS error (BU)")
    axes[0].set_title("PILOT / SYNTHETIC SAMPLE — error and evidence availability")
    axes[0].legend(loc="upper left")
    axes[0].text(.99, .03, "B/D overlap A; C changes the retained cohort, not positions",
                 transform=axes[0].transAxes, ha="right", fontsize=9)
    axes[1].set_ylim(-.03, 1.08)
    axes[1].set_ylabel("Accepted / original visible point trials")
    axes[1].set_xlabel("Independent u/v noise half-width (px);3 fixed seeds;4 sources")
    for ax in axes:
        ax.set_xscale("symlog", linthresh=.001)
        ax.set_xlim(left=0)
        ax.grid(True, which="both", alpha=.25)
    fig.text(.5, .005, "PARTIAL / PROVISIONAL; count-weighted repeated trials; BU scale unverified",
             ha="center", fontsize=9)
    path = output / "noise_error_availability.png"
    _save_plot(fig, path)
    files.append(path.name)

    fig, ax = plt.subplots(figsize=(11, 5.8))
    series = (
        ("Downstream COMPLETE", "downstream_complete_count", "#47729e"),
        ("Metrics available", "metrics_computed_count", "#52976e"),
        ("Available and Coverage@3 True", None, "#b89039"),
    )
    width = .25
    for offset, (label, field, color) in enumerate(series):
        values = [summary["variants"][v][field] if field else
                  summary["variants"][v]["coverage"]["3"]["true_count"] for v in VARIANTS]
        positions = [i + (offset - 1) * width for i in range(len(VARIANTS))]
        ax.bar(positions, values, width=width, label=label, color=color)
        for x, value in zip(positions, values, strict=True):
            ax.text(x, value + 1, str(value), ha="center", fontsize=8)
    ax.set_xticks(range(len(VARIANTS)), [SHORT[v] for v in VARIANTS])
    ax.set_ylim(0, 90)
    ax.set_ylabel("Case counts /62 downstream attempts per variant")
    ax.set_title("PILOT / SYNTHETIC SAMPLE — completion and metric availability")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(axis="y", alpha=.25)
    fig.text(.5, .01,
             "Office/corridor only; missing Coverage is unavailable, never a zero-error metric.\n"
             "PARTIAL / PROVISIONAL; rejected endpoints may change the reconstructed GAP window.",
             ha="center", fontsize=9)
    fig.subplots_adjust(bottom=.18)
    path = output / "downstream_availability.png"
    _save_plot(fig, path)
    files.append(path.name)

    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    for ax, field, title in zip(axes, (
        "projection_seconds_per_original_visible_trial", "downstream_runtime",
    ), ("Projection stage per original visible trial", "Downstream per attempted case"),
        strict=True,
    ):
        values = [summary["variants"][v][field] for v in VARIANTS]
        mid = [_finite(s["median_ms"]) for s in values]
        lower = [m - _finite(s["q1_ms"]) for m, s in zip(mid, values, strict=True)]
        upper = [_finite(s["q3_ms"]) - m for m, s in zip(mid, values, strict=True)]
        ax.bar(range(len(VARIANTS)), mid, yerr=[lower, upper], capsize=4,
               color=[COLORS[v] for v in VARIANTS])
        ax.set_xticks(range(len(VARIANTS)), [SHORT[v] for v in VARIANTS], rotation=28, ha="right")
        ax.set_ylabel("Median milliseconds; error bars = IQR")
        ax.set_title(title, fontsize=10)
        ax.grid(axis="y", alpha=.25)
    fig.suptitle("PILOT / SYNTHETIC SAMPLE — diagnostic runtime accounting")
    fig.text(.5, .005,
             "Single machine; shared diagnostics charged to B/C; "
             "runtime is not benchmark evidence.\n"
             "Projection denominator uses original evidence; "
             "rejection does not artificially reduce that denominator.",
             ha="center", fontsize=9)
    fig.subplots_adjust(bottom=.25, top=.86, wspace=.3)
    path = output / "diagnostic_runtime.png"
    _save_plot(fig, path)
    files.append(path.name)
    return files


def _fmt(value: float | None, digits: int = 6) -> str:
    return "N/A" if value is None else f"{value:.{digits}g}"


def report(summary: dict[str, Any]) -> str:
    variants, policy = summary["variants"], summary["policy"]
    cohort_example = summary["office_noise_quarter_px_rejection_example"]
    text = [
        "# PILOT / SYNTHETIC SAMPLE — Projection conditioning mitigation",
        "", "Physical validity: **PARTIAL / PROVISIONAL**; units: native BU.", "",
        "B confidence is the useful diagnostic: it exposes unreliable geometry while preserving "
        "the existing coordinates, quality scores and all evidence. It does not correct projection "
        "error. C rejection changes availability and the evaluation cohort; retained coordinates "
        "are unchanged. D local binding is the same geometric landmark plane. "
        "No material accepted-point accuracy mitigation was found in the tested variants.", "",
        "620 rows = 4 sources × 31 treatments × 5 variants; 310 downstream attempts. "
        "Auditorium/classroom101 are point-only diagnostics, not downstream failure cases.", "",
        "## Accuracy versus availability", "",
        "Errors below are point-trial-count-weighted across repeated treatments. They are not "
        "distinct-point counts or a physical accuracy certification. The paired column compares "
        "exactly the same retained identities; any apparent improvement against all baseline "
        "points can arise solely from deleting difficult evidence.", "",
        "| Variant | Accepted / original | Low confidence | Retained RMS BU | "
        "Baseline on same cohort BU | Paired RMS gain BU |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for v in VARIANTS:
        a = variants[v]
        text.append(
            f"| {SHORT[v]} | {a['accepted_point_trials']}/{a['original_visible_point_trials']} "
            f"({_fmt(100 * a['availability'], 4)}%) | {a['low_confidence_point_trials']} | "
            f"{_fmt(a['retained_error']['rms_bu'])} | "
            f"{_fmt(a['baseline_on_identical_retained_cohort']['rms_bu'])} | "
            f"{_fmt(a['paired_rms_improvement_bu'])} |"
        )
    text += [
        "", f"Largest absolute per-case paired RMS change: "
        f"{_fmt(summary['largest_absolute_per_case_paired_rms_change_bu'])} BU. "
        "Rejection does not move any accepted point. Missing predictions remain unavailable "
        "and are never assigned zero error.", "",
        "## Representative cohort-loss example", "",
        "Office, ±0.25px, seed 20261006: C standard reduces the displayed cohort RMS from "
        f"{_fmt(cohort_example['all_original_baseline_error']['rms_bu'])} "
        f"to {_fmt(cohort_example['retained_error']['rms_bu'])} BU. "
        "Baseline evaluated on the identical retained cohort is "
        f"{_fmt(cohort_example['baseline_on_identical_retained_cohort']['rms_bu'])} "
        "BU as well. This is evidence deletion, not a corrected projection.", "",
        "| Source | B LOW_CONFIDENCE / original | C standard accepted / original | "
        "C downstream COMPLETE / attempted |",
        "|---|---:|---:|---:|",
    ]
    for site in summary["sources"]:
        b = next(r for r in summary["per_site_summary"] if
                 r["site_id"] == site and r["variant"] == "B_CONFIDENCE")
        c = next(r for r in summary["per_site_summary"] if
                 r["site_id"] == site and r["variant"] == "C_REJECT_STANDARD")
        downstream = (f"{c['downstream_complete_count']}/{c['downstream_attempt_count']}"
                      if c["downstream_attempt_count"] else "N/A — point only")
        text.append(
            f"| {site} | {b['low_confidence_point_trials']}/{b['original_visible_point_trials']} | "
            f"{c['accepted_point_trials']}/{c['original_visible_point_trials']} | {downstream} |"
        )
    text += [
        "", "## Downstream evidence sufficiency", "",
        "| Variant | COMPLETE / attempts | Metrics available | Coverage@1/2/3 True / computed | "
        "Changed GAP windows | Candidate count distribution |",
        "|---|---:|---:|---|---:|---|",
    ]
    for v in VARIANTS:
        a = variants[v]
        cov = "/".join(str(a["coverage"][str(k)]["true_count"]) for k in (1, 2, 3))
        text.append(
            f"| {SHORT[v]} | {a['downstream_complete_count']}/{a['downstream_attempt_count']} | "
            f"{a['metrics_computed_count']} | {cov} /{a['metrics_computed_count']} | "
            f"{a['gap_window_changed_count']} | {a['top_k_candidate_counts']} |"
        )
    text += [
        "", "Coverage uses the unchanged diagnostic ADE epsilon of0.02 BU. It is only computed "
        "when a reconstruction exists. Rejection can remove an endpoint, shift the observed "
        "recovery window, or fragment projected evidence. ADE/FDE on changed windows are not "
        "paired improvement over the original GAP. Original2D evidence is preserved; projection "
        "rejection is not relabeled as camera occlusion.", "",
    ]
    for v in VARIANTS:
        a = variants[v]
        text.append(f"- {SHORT[v]} termination: `{a['termination_counts']}`; "
                    f"unavailable reasons: `{a['failure_reason_counts']}`.")
    text += [
        "", "## Predeclared confidence / rejection policy", "",
        f"Review: gain >{policy['review_gain_bu_per_px']} BU/px OR normalized incidence "
        f"<{policy['review_incidence']} (grazing angle "
        f"<{math.degrees(math.asin(policy['review_incidence'])):.3f}°). "
        "STANDARD rejection: gain >10 BU/px OR incidence <0.1 (angle <5.739°). "
        "EXTREME_ONLY: gain >20 BU/px OR incidence <0.05 (angle <2.866°). "
        "Equality remains accepted/unflagged. These are independent engineering policy "
        "assumptions, not thresholds fitted to GT or formal authority.", "",
        "Confidence score = min(1, incidence/0.2) / "
        "[1 + (gain ×0.002px /0.02BU)²]. The assumed0.002px radius is not measured noise, "
        "a probability, a confidence interval, or a strict accuracy guarantee. Calibration "
        "uncertainty is separate. B flags quality "
        "without rewriting the service's projection_quality.", "",
        "Counterexample: classroom101 is not geometry-flagged at ±0.25px, yet post-freeze "
        "evaluation measures a maximum point error of "
        f"{_fmt(summary['confidence_counterexample']['max_retained_point_error_bu'])} BU across "
        f"{summary['confidence_counterexample']['seed_count']} fixed seeds. The same0.002px "
        "assumption is used throughout the sweep; a CONDITIONED label cannot promise accuracy "
        "under larger pixel noise or calibration perturbation. C thresholds remain experimental "
        "until noise, scale and physical policy authority are established; zero rejection by "
        "C extreme-only is not evidence of an accuracy solution.",
        "", "## Calibration controls", "",
        "Copies perturb all source cameras with the same selected parameter variant: joint focal "
        "±0.1%, principal point cx/cy ±0.1px, local pitch ±0.01°, or world Z translation ±0.1BU. "
        "Original calibration is unchanged; real calibration uncertainty was not measured. "
        "Different units do not form an intrinsic risk ranking.", "",
        "| Calibration copy | A point RMS BU | C standard retained RMS BU | "
        "C availability | C paired RMS gain BU |",
        "|---|---:|---:|---:|---:|",
    ]
    calibrations = sorted({r["calibration_variant"] for r in summary["calibration_summary"]})
    for cal in calibrations:
        a = next(r for r in summary["calibration_summary"] if
                 r["calibration_variant"] == cal and r["variant"] == "A_BASELINE")
        c = next(r for r in summary["calibration_summary"] if
                 r["calibration_variant"] == cal and r["variant"] == "C_REJECT_STANDARD")
        text.append(
            f"| {cal} | {_fmt(a['retained_error']['rms_bu'])} | "
            f"{_fmt(c['retained_error']['rms_bu'])} | {_fmt(c['availability'])} | "
            f"{_fmt(c['paired_rms_improvement_bu'])} |"
        )
    text += [
        "", "## Plane and surface authority limits", "",
        "D rebinds an independently mesh-probed horizontal BODY-landmark plane to a local "
        "source-specific anchor, preserving the floor+clearance+landmark offset. Moving an "
        "origin along the same plane cannot change grazing conditioning. Projecting BODY pixels "
        "directly onto a foot/floor plane would change the target reference "
        "and is not a mitigation.",
        "", "E/F school variants are **UNAVAILABLE_AUTHORITY**: no approved source-bound "
        "school surface and target-reference bindings. Five separate toy E/F controls show "
        "unique-hit acceptance, retention of two legal surfaces, and refusal of review/source/"
        "target-reference mismatch. They do not demonstrate school accuracy improvement "
        "or Graph integration, and do not promote ambiguous WALL/HUMAN_REVIEW geometry.", "",
        "## Remaining bottleneck and readiness", "",
        "Geometry conditioning remains the accuracy bottleneck for these fixed-plane pilots. "
        "No implementation bug was found and no core fix is claimed. B is useful for triage; "
        "C requires an explicit evidence-loss decision and cannot substitute for accurate "
        "projection. Formal Cases1–3 are not ready: source-specific floor/landmark/camera "
        "bindings, usable surface authority, architectural scale/tolerance, observed pixel "
        "and calibration uncertainty, and downstream handling "
        "of unavailable evidence remain unresolved.",
        "", "No formal Cases1–3, Graph/Top-K ranking change, benchmark semantic change, "
        "Coverage epsilon change, or GT-selected solution was introduced. Policies and all "
        "inference artifacts were frozen before evaluation; repeat/GT poison checks replay "
        "full projection policy and compare inference bytes.", "", "## Artifacts", "",
        "- [Full variant results](mitigation_results.json)",
        "- [Comparison summary](summarized_comparison.json)",
        "- [Full sensitivity table](mitigation_table.csv)",
        "- [Error / availability chart](noise_error_availability.png)",
        "- [Downstream availability chart](downstream_availability.png)",
        "- [Diagnostic runtime chart](diagnostic_runtime.png)",
        "- [Separate synthetic E/F authority controls](synthetic_surface_controls.json)",
        "", "Runtime charts use shared diagnostic accounting on one machine, not a performance "
        "benchmark; projection costs use original visible evidence as denominator. Missing "
        "metrics remain null in machine outputs.", "",
    ]
    return "\n".join(text)


def write_report(experiment: Path) -> dict[str, Any]:
    names = (
        "report.md", "summarized_comparison.json", "noise_error_availability.png",
        "downstream_availability.png", "diagnostic_runtime.png",
    )
    if any((experiment / name).exists() for name in names):
        raise FileExistsError("refusing to overwrite mitigation report artifacts")
    # Only this saved derived result is read. No input path in its metadata is followed.
    raw = (experiment / "mitigation_results.json").read_bytes()
    data = json.loads(raw)
    summary = summarize(data, hashlib.sha256(raw).hexdigest())
    summary["charts"] = charts(summary, experiment)
    with (experiment / "summarized_comparison.json").open("x") as stream:
        stream.write(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with (experiment / "report.md").open("x") as stream:
        stream.write(report(summary))
    return {"label": LABEL, "outputs": list(names), "variant_row_count": len(data["rows"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_report(args.experiment)))


if __name__ == "__main__":
    main()
