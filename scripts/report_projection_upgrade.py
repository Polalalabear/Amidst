"""Report frozen PILOT model-upgrade results without opening any inference or GT input."""

from __future__ import annotations

import argparse
import csv
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
SITES = ("office", "corridor", "auditorium", "classroom101")
OUTPUTS = (
    "report.md",
    "machine_summary.json",
    "upgrade_table.csv",
    "multiview_error_availability.png",
    "uncertainty_coverage_states.png",
)


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _fmt(value: float | int | None, digits: int = 6) -> str:
    return "N/A" if value is None else f"{value:.{digits}g}"


def _pool(values: list[dict[str, Any]]) -> dict[str, Any]:
    nonempty = [value for value in values if value["count"]]
    count = sum(value["count"] for value in nonempty)
    if any(
        not math.isfinite(float(value[key]))
        for value in nonempty
        for key in ("mean_bu", "rms_bu", "max_bu")
    ):
        raise ValueError("nonempty error summaries must contain finite values")
    return {
        "count": count,
        "mean_bu": math.fsum(value["count"] * value["mean_bu"] for value in nonempty) / count
        if count
        else None,
        "rms_bu": math.sqrt(
            math.fsum(value["count"] * value["rms_bu"] ** 2 for value in nonempty) / count
        )
        if count
        else None,
        "max_bu": max((value["max_bu"] for value in nonempty), default=None),
        "aggregation": "COUNT_WEIGHTED_REPEATED_POINT_TRIALS_NOT_DISTINCT_POINTS",
    }


def _runtime(values: list[float]) -> dict[str, Any]:
    return {
        "count": len(values),
        "median_ms": median(values) * 1000 if values else None,
        "min_ms": min(values) * 1000 if values else None,
        "max_ms": max(values) * 1000 if values else None,
        "scope": "COMBINED_MODEL_AND_BASELINE_DOWNSTREAM_SINGLE_MACHINE_NOT_BENCHMARK",
        "per_variant_overhead_separable": False,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool only actual accepted same-evidence cohorts; never convert missing errors to zero."""
    multiview = [row["multiview"] for row in rows]
    original = sum(value["original_visible_timestamp_count"] for value in multiview)
    eligible = sum(value["eligible_timestamp_count"] for value in multiview)
    accepted = sum(value["accepted_timestamp_count"] for value in multiview)
    paired = _pool([value["paired_mean_plane_stats"] for value in multiview])
    triangulated = _pool([value["triangulated_stats"] for value in multiview])
    if paired["count"] != triangulated["count"]:
        raise ValueError("same-evidence comparison requires matching hypothesis cohorts")
    paired_rms, upgraded_rms = paired["rms_bu"], triangulated["rms_bu"]
    reduction = (
        100 * (1 - upgraded_rms / paired_rms) if paired_rms and upgraded_rms is not None else None
    )
    uncertainty = [row["uncertainty_eval"] for row in rows]
    covariance_count = sum(value["evaluated_covariance_count"] for value in uncertainty)
    inside_count = sum(value["inside_count"] for value in uncertainty)
    states = Counter()
    for value in uncertainty:
        states.update(value["use_state_counts"])
    computed = [row for row in rows if row["baseline_downstream"]["metrics"] is not None]
    statuses = [row["baseline_downstream"]["status"] for row in rows]
    coverage = {
        str(k): {
            "computed_count": len(computed),
            "true_count": sum(
                row["baseline_downstream"]["metrics"][k - 1]["coverage_at_k"] is True
                for row in computed
            ),
            "false_count": sum(
                row["baseline_downstream"]["metrics"][k - 1]["coverage_at_k"] is False
                for row in computed
            ),
            "unavailable_count": len(rows) - len(computed),
        }
        for k in (1, 2, 3)
    }
    metric_fields = (
        "ade_first_primary_scene_units",
        "fde_first_primary_scene_units",
        "min_ade_at_k_scene_units",
        "min_fde_at_k_scene_units",
    )
    metric_summary = {
        str(k): {
            field: {
                "mean_bu": math.fsum(
                    row["baseline_downstream"]["metrics"][k - 1][field] for row in computed
                )
                / len(computed)
                if computed
                else None,
                "max_bu": max(
                    (row["baseline_downstream"]["metrics"][k - 1][field] for row in computed),
                    default=None,
                ),
            }
            for field in metric_fields
        }
        for k in (1, 2, 3)
    }
    local_gains = [
        value["local_gain"]["max_bu_per_pixel"]
        for value in multiview
        if value["local_gain"]["max_bu_per_pixel"] is not None
    ]
    reductions = [
        value["same_evidence_reduction_vs_pair_mean_pct"]
        for value in multiview
        if value["same_evidence_reduction_vs_pair_mean_pct"] is not None
    ]
    return {
        "case_count": len(rows),
        "baseline_all_observed_point_error": _pool([row["baseline_stats"] for row in rows]),
        "paired_individual_plane_error": _pool(
            [value["paired_individual_plane_stats"] for value in multiview]
        ),
        "paired_mean_plane_error": paired,
        "triangulated_error": triangulated,
        "same_evidence_rms_reduction_percent": reduction,
        "casewise_positive_reduction_count": sum(value > 0 for value in reductions),
        "casewise_nonpositive_reduction_count": sum(value <= 0 for value in reductions),
        "original_visible_timestamp_trials": original,
        "eligible_timestamp_trials": eligible,
        "accepted_timestamp_trials": accepted,
        "availability_among_original_visible_timestamps": _ratio(accepted, original),
        "availability_among_eligible_timestamps": _ratio(accepted, eligible),
        "hypothesis_trial_count": sum(value["hypothesis_count"] for value in multiview),
        "gap_endpoint_pair_count": sum(value["gap_endpoint_pairs"] for value in multiview),
        "multiview_gap_status_counts": dict(
            Counter(value["gap_downstream_status"] for value in multiview)
        ),
        "maximum_local_gain_bu_per_joint_four_pixel_norm": max(local_gains, default=None),
        "uncertainty": {
            "evaluated_covariance_count": covariance_count,
            "inside_count": inside_count,
            "conditional_subspace_95_coverage": _ratio(inside_count, covariance_count),
            "use_state_counts": dict(states),
            "unmodeled_residual_error": _pool(
                [value["unmodeled_residual_stats"] for value in uncertainty]
            ),
            "nominal_radius": _pool([value["nominal_radius_stats"] for value in uncertainty]),
            "full_3d_calibration": "UNVALIDATED_UNMODELED_HEIGHT_AND_UNMEASURED_UNCERTAINTY",
            "coverage_is_empirical_probability_validation": False,
        },
        "baseline_downstream": {
            "metrics_computed_count": len(computed),
            "termination_counts": dict(Counter(value["termination_reason"] for value in statuses)),
            "candidate_counts": dict(Counter(str(value["candidate_count"]) for value in statuses)),
            "hypothesis_counts": dict(
                Counter(str(value["hypothesis_count"]) for value in statuses)
            ),
            "coverage": coverage,
            "metrics": metric_summary,
            "B_F_are_identical_coordinate_references_not_separate_graph_runs": True,
        },
        "runtime": _runtime(
            [row["runtime"]["model_and_baseline_downstream_seconds"] for row in rows]
        ),
    }


def summarize(data: dict[str, Any], input_sha256: str) -> dict[str, Any]:
    rows = data["rows"]
    if data.get("label") != LABEL or len(rows) != 124:
        raise ValueError("expected 124 labeled frozen model-comparison cases")
    if set(row["site_id"] for row in rows) != set(SITES):
        raise ValueError("expected four source-specific pilot contexts")
    if len({(row["site_id"], row["case_id"]) for row in rows}) != len(rows):
        raise ValueError("duplicate source/case identities cannot enter a summary")
    if any(sum(row["site_id"] == site for row in rows) != 31 for site in SITES):
        raise ValueError("expected 31 predeclared treatments per source")
    if not data["all_model_outputs_frozen_before_gt"]:
        raise ValueError("model outputs must freeze before any GT evaluation")
    if data["core_observation_graph_metric_contracts_modified"]:
        raise ValueError("this diagnostic report requires unchanged baseline contracts")
    if data["coverage_epsilon_bu"] != 0.02 or data["formal_cases_1_3_executed"]:
        raise ValueError("formal semantics/epsilon must remain unchanged and Cases1–3 unexecuted")
    if data["model_upgrade_validated"] or data["classification"] == "MODEL_UPGRADE_VALIDATED":
        raise ValueError(
            "this authority-blocked diagnostic cannot claim validated school improvement"
        )
    if any(not row["runtime_reads_allowlisted"] for row in rows):
        raise ValueError("all model inference reads must remain allowlisted")
    for check in data["representative_checks"]:
        if not check["full_model_repeat_equal"] or not check["gt_poison_model_equal"]:
            raise ValueError("representative determinism/GT poison check failed")
        if check["pair_surface_hypothesis_gt_selection"]:
            raise ValueError("GT cannot select a camera pair, surface or hypothesis")
    noise_levels = sorted(
        {
            row["treatment"]["noise_halfwidth_px"]
            for row in rows
            if row["treatment"]["kind"] == "PIXEL_NOISE"
        }
    )
    calibrations = sorted(
        {
            row["treatment"]["calibration_variant"]
            for row in rows
            if row["treatment"]["kind"] == "CALIBRATION_COPY"
        }
    )
    return {
        "label": LABEL,
        "scope": data["scope"],
        "checkpoint_commit": data["checkpoint_commit"],
        "classification": data["classification"],
        "model_upgrade_validated": False,
        "input_upgrade_results_sha256": input_sha256,
        "case_count": len(rows),
        "physical_validity": data["physical_validity"],
        "authority_preflight": data["authority_preflight"],
        "all_cases": aggregate(rows),
        "by_site": {
            site: aggregate([row for row in rows if row["site_id"] == site]) for site in SITES
        },
        "noise_summary": [
            {
                "site_id": site,
                "noise_halfwidth_px": amount,
                **aggregate(
                    [
                        row
                        for row in rows
                        if row["site_id"] == site
                        and row["treatment"]["kind"] == "PIXEL_NOISE"
                        and row["treatment"]["noise_halfwidth_px"] == amount
                    ]
                ),
            }
            for site in SITES
            for amount in noise_levels
        ],
        "calibration_summary": [
            {
                "site_id": site,
                "calibration_variant": variant,
                **aggregate(
                    [
                        row
                        for row in rows
                        if row["site_id"] == site
                        and row["treatment"]["calibration_variant"] == variant
                    ]
                ),
            }
            for site in SITES
            for variant in calibrations
        ],
        "representative_checks": data["representative_checks"],
        "surface_control_evaluation": data["surface_control_evaluation"],
        "same_evidence_comparator": "PREDECLARED_EQUAL_MEAN_OF_ALL_PAIRED_FIXED_PLANE_POINTS",
        "camera_pairs_selected_using_gt": False,
        "surfaces_or_hypotheses_selected_using_gt": False,
        "no_samples_deleted_for_accuracy_claim": True,
        "B_F_coordinate_gain_percent": 0,
        "school_surface_effectiveness": "UNAVAILABLE_AUTHORITY_SYNTHETIC_FIXTURE_ONLY",
        "multiview_gap_reconstruction_effectiveness": "UNAVAILABLE_NO_PAIRED_GAP_ENDPOINTS",
        "conditional_uncertainty_not_full_3d_probability_bound": True,
        "coverage_epsilon_bu_unchanged": data["coverage_epsilon_bu"],
        "formal_case_readiness": "NOT_READY_AUTHORITY_MEASUREMENT_AND_ENDPOINT_AVAILABILITY",
        "runtime_limitation": "COMBINED_COST_ONLY_NO_SEPARATE_PER_VARIANT_OVERHEAD_MEASURED",
    }


def charts(summary: dict[str, Any], output: Path) -> list[str]:
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.6), dpi=160)
    paired_rows = [
        row for row in summary["noise_summary"] if row["paired_mean_plane_error"]["count"]
    ]
    for site in SITES:
        selected = sorted(
            (row for row in paired_rows if row["site_id"] == site),
            key=lambda row: row["noise_halfwidth_px"],
        )
        if not selected:
            continue
        xs = [row["noise_halfwidth_px"] for row in selected]
        for key, label, style in (
            ("paired_mean_plane_error", "fixed-plane mean (same paired evidence)", "o-"),
            ("triangulated_error", "C exact-time triangulation", "s--"),
        ):
            axes[0].plot(
                xs,
                [row[key]["rms_bu"] for row in selected],
                style,
                label=f"{site}: {label}",
                markersize=4,
            )
    axes[0].set_xscale("symlog", linthresh=0.001)
    axes[0].set_xlim(0, max(row["noise_halfwidth_px"] for row in summary["noise_summary"]) * 1.1)
    axes[0].set_yscale("log")
    axes[0].set_xlabel("Uniform half-width per u/v coordinate (px)")
    axes[0].set_ylabel("Paired point RMS error (BU), frozen-output evaluation")
    axes[0].set_title("Count-weighted pooled RMS over 3 fixed seeds")
    axes[0].grid(alpha=0.25)
    if paired_rows:
        axes[0].legend(fontsize=8)
    else:
        axes[0].text(
            0.5,
            0.5,
            "No accepted exact-time pairs; error N/A",
            ha="center",
            transform=axes[0].transAxes,
        )
    values = [summary["by_site"][site] for site in SITES]
    bars = axes[1].bar(
        SITES,
        [row["availability_among_original_visible_timestamps"] for row in values],
        color="#207599",
    )
    axes[1].set_ylim(0, 1.1)
    axes[1].set_ylabel("C availability / original visible timestamps")
    axes[1].set_title("All treatments; zero paired GAP endpoints at every site")
    axes[1].tick_params(axis="x", rotation=20)
    for bar, row in zip(bars, values, strict=True):
        ratio = row["availability_among_original_visible_timestamps"]
        label = "0: no eligible pair" if not row["eligible_timestamp_trials"] else f"{ratio:.1%}"
        axes[1].text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.025,
            label,
            ha="center",
            fontsize=8,
        )
    figure.suptitle(
        LABEL + " · Same-evidence error and evidence availability\n"
        "Error N/A outside paired cohorts; no school authority or GAP efficacy claim"
    )
    figure.tight_layout()
    figure.savefig(output / OUTPUTS[3], metadata={"DatasetLabel": LABEL})
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(13, 5.6), dpi=160)
    for site in SITES:
        selected = sorted(
            (
                row
                for row in summary["noise_summary"]
                if row["site_id"] == site
                and row["uncertainty"]["conditional_subspace_95_coverage"] is not None
            ),
            key=lambda row: row["noise_halfwidth_px"],
        )
        if selected:
            axes[0].plot(
                [row["noise_halfwidth_px"] for row in selected],
                [row["uncertainty"]["conditional_subspace_95_coverage"] for row in selected],
                "o-",
                label=site,
                markersize=4,
            )
    axes[0].axhline(0.95, linestyle=":", color="#777777", label="Nominal ellipsoid level")
    axes[0].set_xscale("symlog", linthresh=0.001)
    axes[0].set_xlim(0, max(row["noise_halfwidth_px"] for row in summary["noise_summary"]) * 1.1)
    axes[0].set_ylim(0, 1.05)
    axes[0].set_xlabel("Uniform half-width per u/v coordinate (px)")
    axes[0].set_ylabel("Conditional modeled-subspace inclusion fraction")
    axes[0].set_title("Zero covariance is N/A; unmodeled height excluded")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.25)
    states = sorted(
        {state for value in values for state in value["uncertainty"]["use_state_counts"]}
    )
    bottoms = [0.0] * len(SITES)
    for state in states:
        fractions = []
        for value in values:
            counts = value["uncertainty"]["use_state_counts"]
            fractions.append(counts.get(state, 0) / sum(counts.values()))
        axes[1].bar(SITES, fractions, bottom=bottoms, label=state.replace("_", " "))
        bottoms = [a + b for a, b in zip(bottoms, fractions, strict=True)]
    axes[1].set_ylim(0, 1.05)
    axes[1].set_ylabel("Fraction of original visible point trials")
    axes[1].set_title("F diagnostic use states; points and evidence unchanged")
    axes[1].tick_params(axis="x", rotation=20)
    axes[1].legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.15))
    figure.suptitle(
        LABEL + " · Conditional uncertainty diagnostics\n"
        "Gaussian-style nominal ellipsoids / bounded controls; full 3D UNVALIDATED"
    )
    figure.tight_layout()
    figure.savefig(output / OUTPUTS[4], metadata={"DatasetLabel": LABEL})
    plt.close(figure)
    return list(OUTPUTS[3:])


def sensitivity_table(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "site_id",
        "case_id",
        "treatment_kind",
        "noise_halfwidth_px",
        "seed",
        "calibration_variant",
        "baseline_point_count",
        "baseline_point_rms_bu",
        "baseline_point_max_bu",
        "paired_mean_rms_bu",
        "triangulated_rms_bu",
        "same_evidence_rms_reduction_percent",
        "original_visible_timestamp_count",
        "eligible_timestamp_count",
        "accepted_timestamp_count",
        "hypothesis_count",
        "gap_endpoint_pairs",
        "gap_downstream_status",
        "conditional_subspace_95_coverage",
        "evaluated_covariance_count",
        "uncertainty_use_state_counts",
        "unmodeled_residual_max_bu",
        "combined_runtime_seconds",
        "baseline_termination",
        "baseline_candidate_count",
        "baseline_hypothesis_count",
    ]
    for k in (1, 2, 3):
        fields.extend(f"{name}_at_{k}" for name in ("ade", "fde", "minade", "minfde", "coverage"))
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            treatment, mv, uncertainty = row["treatment"], row["multiview"], row["uncertainty_eval"]
            downstream = row["baseline_downstream"]
            entry = {
                "site_id": row["site_id"],
                "case_id": row["case_id"],
                "treatment_kind": treatment["kind"],
                **{
                    key: treatment[key]
                    for key in ("noise_halfwidth_px", "seed", "calibration_variant")
                },
                "baseline_point_count": row["baseline_stats"]["count"],
                "baseline_point_rms_bu": row["baseline_stats"]["rms_bu"],
                "baseline_point_max_bu": row["baseline_stats"]["max_bu"],
                "paired_mean_rms_bu": mv["paired_mean_plane_stats"]["rms_bu"],
                "triangulated_rms_bu": mv["triangulated_stats"]["rms_bu"],
                "same_evidence_rms_reduction_percent": mv[
                    "same_evidence_reduction_vs_pair_mean_pct"
                ],
                **{
                    key: mv[key]
                    for key in (
                        "original_visible_timestamp_count",
                        "eligible_timestamp_count",
                        "accepted_timestamp_count",
                        "hypothesis_count",
                        "gap_endpoint_pairs",
                        "gap_downstream_status",
                    )
                },
                "conditional_subspace_95_coverage": uncertainty["conditional_subspace_95_coverage"],
                "evaluated_covariance_count": uncertainty["evaluated_covariance_count"],
                "uncertainty_use_state_counts": json.dumps(
                    uncertainty["use_state_counts"], sort_keys=True
                ),
                "unmodeled_residual_max_bu": uncertainty["unmodeled_residual_stats"]["max_bu"],
                "combined_runtime_seconds": row["runtime"]["model_and_baseline_downstream_seconds"],
                "baseline_termination": downstream["status"]["termination_reason"],
                "baseline_candidate_count": downstream["status"]["candidate_count"],
                "baseline_hypothesis_count": downstream["status"]["hypothesis_count"],
            }
            for k in (1, 2, 3):
                metrics = downstream["metrics"][k - 1] if downstream["metrics"] else None
                for name, key in (
                    ("ade", "ade_first_primary_scene_units"),
                    ("fde", "fde_first_primary_scene_units"),
                    ("minade", "min_ade_at_k_scene_units"),
                    ("minfde", "min_fde_at_k_scene_units"),
                    ("coverage", "coverage_at_k"),
                ):
                    entry[f"{name}_at_{k}"] = metrics[key] if metrics else None
            writer.writerow(entry)


def report(summary: dict[str, Any]) -> str:
    aggregate_all = summary["all_cases"]
    aud = summary["by_site"]["auditorium"]
    surface = summary["surface_control_evaluation"]
    uncertainty = aggregate_all["uncertainty"]
    checks_count = len(summary["representative_checks"])
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — Projection model upgrade",
        "",
        f"Result: **{summary['classification']}**; MODEL_UPGRADE_VALIDATED = False.",
        "",
        "## 結論 / Conclusion",
        "",
        "本輪先完成measurement/authority preflight，再建立additive diagnostic variants。"
        "A fixed-plane仍保留；B conditioning與F uncertainty均不改coordinates/quality"
        "或刪除evidence。"
        "C只處理合法同target/source/exact-time的多camera evidence，缺資料時fail closed。",
        f"124cases、四個既有場地；C只有auditorium可用，其same-evidence pooled RMS變化為 "
        f"{_fmt(aud['same_evidence_rms_reduction_percent'])}%。改善比較採固定的paired-camera "
        "plane-point等權平均，沒有用GT選camera、pair、surface或hypothesis。"
        "正值代表改善，負值代表退化；這是frozen inference後evaluation。",
        f"Auditorium {aud['casewise_positive_reduction_count']}/31 cases改善，"
        f"{aud['casewise_nonpositive_reduction_count']}/31退化或未改善。"
        "C不是通用calibration robustness solution：cx±0.1px共模copies在既有pair geometry下"
        "RMS約0.049→0.105BU，比paired-mean baseline差約113–115%。",
        "C在既有GAP departure/recovery的paired evidence為0，因此沒有C的GAP reconstruction、"
        "ADE/FDE或Coverage gain可宣稱。Approved school surface不足，D/E只跑獨立synthetic controls。"
        "Physical validity保持PARTIAL / PROVISIONAL，正式Cases1–3尚未開始。",
        "",
        "## Authority / measurement preflight",
        "",
        "| Item | Status | Reason |",
        "|---|---|---|",
    ]
    for item in summary["authority_preflight"]["items"]:
        lines.append(f"| {item['item']} | {item['status']} | {item['reason']} |")
    lines += [
        "",
        "Fresh physical-authority snapshot is pinned to "
        f"`{summary['authority_preflight']['physical_authority_commit']}`. "
        "Office uses a derived source hash and cannot borrow original-school authority. "
        "HIGH_CONFIDENCE or semantic role approval does not mean approved physical support; "
        "no REVIEW/WALL geometry is promoted.",
        "",
        "## Additive variants and availability",
        "",
        "| Variant | Actual execution / result |",
        "|---|---|",
        "| A fixed plane | All original visible points; existing baseline downstream "
        "on office/corridor. |",
        "| B conditioning | Diagnostics beside unchanged A point; existing "
        "confidence policy retained. |",
        "| C exact-time multi-view | All eligible pairs; no GT alignment, "
        "interpolation or best-pair choice. |",
        "| D approved surface | School unavailable; unique-hit synthetic fixture only. |",
        "| E multi-surface | School unavailable; all legal fixture hits retain "
        "surface/evidence provenance. |",
        "| F uncertainty | Pixel/calibration Jacobian covariance sidecar conditional "
        "on exact plane. |",
        "",
        "| Site | C accepted / visible timestamp trials | Eligible acceptance | "
        "Paired mean RMS BU | C RMS BU | Change % | GAP endpoint pairs |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for site in SITES:
        value = summary["by_site"][site]
        lines.append(
            f"| {site} | {value['accepted_timestamp_trials']} / "
            f"{value['original_visible_timestamp_trials']} | "
            f"{_fmt(value['availability_among_eligible_timestamps'])} | "
            f"{_fmt(value['paired_mean_plane_error']['rms_bu'])} | "
            f"{_fmt(value['triangulated_error']['rms_bu'])} | "
            f"{_fmt(value['same_evidence_rms_reduction_percent'])} | "
            f"{value['gap_endpoint_pair_count']} |"
        )
    lines += [
        "",
        "Auditorium has33 exact-time pairs at2.0–6.2s and6.6–8.6s. "
        "Its GAP endpoints9.2/9.6s each have only REAR evidence. Office/corridor have "
        "disjoint camera windows; classroom101 has no observed second camera. "
        "Repeated treatments are trials, not new trajectories or independent datasets. "
        "C's unavailable points are not reported as zero error and no hidden fixed-plane fallback "
        "is counted as triangulation success.",
        "",
        "## Noise comparison on identical accepted pairs",
        "",
        "| Site / per-coordinate half-width px | Pair mean RMS BU | C RMS BU | "
        "Change % | C availability | Conditional F inclusion |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in summary["noise_summary"]:
        lines.append(
            f"| {row['site_id']} / {row['noise_halfwidth_px']:g} | "
            f"{_fmt(row['paired_mean_plane_error']['rms_bu'])} | "
            f"{_fmt(row['triangulated_error']['rms_bu'])} | "
            f"{_fmt(row['same_evidence_rms_reduction_percent'])} | "
            f"{_fmt(row['availability_among_original_visible_timestamps'])} | "
            f"{_fmt(row['uncertainty']['conditional_subspace_95_coverage'])} |"
        )
    lines += [
        "",
        "RMS is count-weighted over the same accepted pair cohort and three fixed seeds. "
        "It is distinct from A error over all camera points, whose availability differs. "
        "Joint C amplification divides3D displacement by the norm of four pixel coordinates; "
        "the earlier single-camera Jacobian peak12.604BU/px uses a different input dimension. "
        "These gain values cannot be equated directly.",
        "",
        "## Calibration copies on paired evidence",
        "",
        "Original calibration stays unchanged. Copies: joint focal ±0.1%, cx/cy ±0.1px, "
        "local pitch ±0.01°, world-Z ±0.1BU. These are shared synthetic parameter copies "
        "across cameras, not measured independent calibration noise.",
        "",
        "| Site / calibration copy | Pair mean RMS BU | C RMS BU | Change % |",
        "|---|---:|---:|---:|",
    ]
    for row in summary["calibration_summary"]:
        if row["paired_mean_plane_error"]["count"]:
            lines.append(
                f"| {row['site_id']} / {row['calibration_variant']} | "
                f"{_fmt(row['paired_mean_plane_error']['rms_bu'])} | "
                f"{_fmt(row['triangulated_error']['rms_bu'])} | "
                f"{_fmt(row['same_evidence_rms_reduction_percent'])} |"
            )
    lines += [
        "",
        "## Uncertainty propagation / uncertainty calibration",
        "",
        "F uses declared injected uniform-noise half-width/√3 and first-order pixel/calibration "
        "derivatives. Covariance is conditional on the fixed exact landmark plane and assigned "
        "calibration assumptions; normal-height/plane-binding uncertainty is unmodeled. "
        "A Gaussian-style nominal χ² ellipsoid evaluated against bounded uniform controls is "
        "not empirical probability calibration. Three seeds do not validate a95% "
        "probability bound.",
        f"Conditional inclusion: {_fmt(uncertainty['conditional_subspace_95_coverage'])} "
        f"on{uncertainty['evaluated_covariance_count']} nonzero-covariance trials. "
        f"Use-state counts: `{uncertainty['use_state_counts']}`. "
        f"Maximum residual outside modeled support: "
        f"{_fmt(uncertainty['unmodeled_residual_error']['max_bu'])} BU.",
        "Zero covariance is UNAVAILABLE_ZERO_VARIANCE rather than perfect certainty. "
        "USABLE_WITH_UNCERTAINTY versus REVIEW_REQUIRED uses a fixed diagnostic0.02BU nominal "
        "radius budget; this is neither changed Coverage epsilon nor approved accuracy authority. "
        "F retains original points/evidence and adds machine-readable use states; current Graph "
        "does not consume covariance, weight hypotheses, or reject uncertainty-marked endpoints.",
        "",
        "## Surface controls and hypotheses",
        "",
        f"Unique fixture hit: {surface['unique_hypothesis_count']} hypothesis, "
        f"error{_fmt(surface['unique_surface_error_bu'])}BU. Multi-surface fixture: "
        f"{surface['multi_hypothesis_count']} hypotheses retained; evaluation reference present="
        f"{surface['multi_reference_in_retained_hypotheses']}, min-error="
        f"{_fmt(surface['multi_min_error_bu'])}BU. "
        "The farther legal hypothesis remains present; GT is not used to pick "
        "nearest/best surface. "
        "The unique fixture is the same plane geometry, so it provides no conditioning cure. "
        "Surface provenance retention is not full Graph multi-surface integration or "
        "school efficacy.",
        "",
        "## Downstream metrics and runtime",
        "",
        "Only baseline office/corridor reconstruction is executed. B/F reuse its "
        "unchanged-coordinate "
        "metrics as references; they are not separately executed uncertainty-aware consumers. "
        "C/D/E reconstruction metrics are unavailable because paired "
        "endpoints/authority are absent.",
        "",
        "| Site | A termination | Candidate / hypothesis counts | "
        "Mean ADE / FDE BU | minADE@3 / minFDE@3 BU | Coverage@3 true/computed |",
        "|---|---|---|---:|---:|---:|",
    ]
    for site in SITES:
        downstream = summary["by_site"][site]["baseline_downstream"]
        metrics = downstream["metrics"]["3"]
        coverage = downstream["coverage"]["3"]
        lines.append(
            f"| {site} | {downstream['termination_counts']} | "
            f"{downstream['candidate_counts']} / {downstream['hypothesis_counts']} | "
            f"{_fmt(metrics['ade_first_primary_scene_units']['mean_bu'])} / "
            f"{_fmt(metrics['fde_first_primary_scene_units']['mean_bu'])} | "
            f"{_fmt(metrics['min_ade_at_k_scene_units']['mean_bu'])} / "
            f"{_fmt(metrics['min_fde_at_k_scene_units']['mean_bu'])} | "
            f"{coverage['true_count']} / {coverage['computed_count']} |"
        )
    lines += [
        "",
        "All K1/2/3 ADE/FDE/minADE/minFDE/Coverage values are preserved per case inJSON/CSV. "
        "Missing metrics remain null/N/A. Existing Coverage epsilon0.02BU and metric semantics "
        "are unchanged. Reported means pool heterogeneous controls and are not "
        "formal benchmark results.",
        f"Combined models plus baseline downstream runtime median="
        f"{_fmt(aggregate_all['runtime']['median_ms'])}ms/case, range "
        f"{_fmt(aggregate_all['runtime']['min_ms'])}–{_fmt(aggregate_all['runtime']['max_ms'])}ms. "
        "This one-machine combined measurement cannot isolate individual variant overhead, "
        "and is not a deployment performance claim.",
        "",
        "## GT isolation, bottleneck and readiness",
        "",
        f"All124 model outputs and toy surface hypotheses freeze beforeGT evaluation; "
        f"{checks_count} representative model replay/GT poison checks pass. "
        "Only the saved derived results are opened by this reporter; no paths to "
        "raw2D, calibration, "
        "GT, trajectories or Blender assets are followed.",
        "Fixed-plane conditioning remains a bottleneck where legal multi-view "
        "evidence is unavailable, "
        "including every existing GAP endpoint. Same-evidence C point gains, where measured, are "
        "diagnostic scope only; availability and authority still prevent MODEL_UPGRADE_VALIDATED. "
        "Formal Cases1–3 need source-specific camera/floor/landmark/surface "
        "approvals, architectural "
        "scale/tolerance, measured pixel/calibration/clock uncertainty, sufficient "
        "synchronized endpoint "
        "coverage, and approved downstream hypothesis/uncertainty evidence policies.",
        "",
        "## Artifacts",
        "",
        "- [Frozen evaluated results](upgrade_results.json)",
        "- [Machine summary](machine_summary.json)",
        "- [Sensitivity and downstream table](upgrade_table.csv)",
        "- [Same-evidence error / availability chart](multiview_error_availability.png)",
        "- [Conditional uncertainty / use-state chart](uncertainty_coverage_states.png)",
        "- [Authority preflight](authority_preflight.json)",
        "- [Predeclared protocol](protocol.json)",
        "- [Separate synthetic surface evaluation](surface_evaluation.json)",
        "- [Inference freeze before evaluation](inference_freeze_before_gt.json)",
        "",
    ]
    return "\n".join(lines)


def write_report(experiment: Path) -> dict[str, Any]:
    if any((experiment / name).exists() for name in OUTPUTS):
        raise FileExistsError("refusing to overwrite frozen model-upgrade report artifacts")
    raw = (experiment / "upgrade_results.json").read_bytes()
    summary = summarize(json.loads(raw), hashlib.sha256(raw).hexdigest())
    summary["charts"] = charts(summary, experiment)
    sensitivity_table(json.loads(raw)["rows"], experiment / OUTPUTS[2])
    with (experiment / OUTPUTS[1]).open("x") as stream:
        stream.write(json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n")
    with (experiment / OUTPUTS[0]).open("x") as stream:
        stream.write(report(summary))
    return {"label": LABEL, "case_count": summary["case_count"], "outputs": list(OUTPUTS)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_report(args.experiment)))


if __name__ == "__main__":
    main()
