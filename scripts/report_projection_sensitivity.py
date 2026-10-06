"""Summarize saved PILOT sensitivity evidence without rerunning or tuning inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

LABEL = "PILOT / SYNTHETIC SAMPLE"


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    if data.get("label") != LABEL:
        raise ValueError("sensitivity evidence must have PILOT / SYNTHETIC SAMPLE label")
    return data


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def maximum(rows: list[dict[str, Any]], field: str) -> dict[str, Any]:
    finite = [row for row in rows if row[field] is not None and math.isfinite(row[field])]
    if not finite:
        raise ValueError(f"no finite diagnostic evidence for {field}")
    return max(finite, key=lambda row: row[field])


def downstream_chart(root: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(12, 5), dpi=160)
    for site in sorted({row["site_id"] for row in rows}):
        amplitudes = sorted(
            {row["noise_halfwidth_pixels"] for row in rows if row["site_id"] == site}
        )
        for axis, key in zip(
            axes, ("ade_first_primary_scene_units", "fde_first_primary_scene_units"), strict=True
        ):
            values = [
                [
                    row["metrics"][0][key]
                    for row in rows
                    if row["site_id"] == site and row["noise_halfwidth_pixels"] == amplitude
                ]
                for amplitude in amplitudes
            ]
            means = [sum(group) / len(group) for group in values]
            (line,) = axis.plot(amplitudes, means, marker=".", label=site + " (3 fixed seeds)")
            axis.fill_between(
                amplitudes,
                [min(group) for group in values],
                [max(group) for group in values],
                color=line.get_color(),
                alpha=0.15,
            )
            axis.set_xscale("symlog", linthresh=0.001)
            axis.set_yscale("log")
            axis.set_xlabel("Uniform noise half-width per coordinate (pixels)")
            axis.grid(alpha=0.2)
            axis.legend(fontsize=8)
    axes[0].set_ylabel("Primary ADE (BU), saved-output GT evaluation only")
    axes[1].set_ylabel("Primary FDE (BU), recovery endpoint anchored")
    axes[0].axhline(0.02, color="#b04444", linestyle=":", label="Unchanged pilot ADE budget")
    axes[0].legend(fontsize=8)
    figure.suptitle(
        LABEL + " · Inference COMPLETE can coexist with accuracy failure\n"
        "BU physical scale PROVISIONAL; bands are 3-seed ranges, not confidence intervals"
    )
    figure.tight_layout()
    figure.savefig(root / "noise_to_downstream_metrics.png", metadata={"DatasetLabel": LABEL})
    plt.close(figure)


def create_report(root: Path) -> dict[str, Any]:
    if (root / "experiment_results.json").exists() or (root / "report.md").exists():
        raise FileExistsError("completed sensitivity summary already exists")
    analysis = read_json(root / "sample_analysis/summary.json")
    sweep = read_json(root / "downstream_sweep/sweep_report.json")
    layer = read_json(root / "layer_evaluation/layer_evaluation.json")
    cameras = read_json(root / "sample_analysis/camera_summary.json")["rows"]
    calibration = read_json(root / "sample_analysis/calibration_summary.json")["rows"]
    baseline = [
        json.loads(line)
        for line in (root / "sample_analysis/baseline_geometry.jsonl").read_text().splitlines()
    ]
    peak = max(
        baseline, key=lambda row: row["conditioning"]["jacobian"]["max_scene_units_per_pixel"]
    )
    joint = read_json(root / "joint_focal_diagnostic.json")
    grid = read_json(root / "synthetic_conditioning_grid.json")
    qa = read_json(root / "sample_analysis/visualization_qa.json")
    if sweep["variant_count"] != 102 or sweep["termination_counts"] != {"COMPLETE": 102}:
        raise ValueError("saved sweep differs from the declared experiment outcomes")
    if any(row["candidate_count"] != 3 for row in sweep["results"]):
        raise ValueError("reported all-Top-K outcome needs explicit saved evidence")
    if qa["errors"] or any(
        not check[key]
        for check in sweep["representative_isolation_checks"]
        for key in ("repeat_inference_byte_equal", "poison_inference_byte_equal")
    ):
        raise ValueError("visual or GT isolation evidence failed")
    camera_peaks = {
        key: maximum(cameras, key)[key]
        for key in (
            "max_float64_vs_decimal60_difference_bu",
            "max_float32_vs_service_difference_bu",
            "max_roundtrip_pixel_error",
            "max_jacobian_central_difference_relative_error",
        )
    }
    calibration_peaks = {
        variant: maximum(
            [row for row in calibration if row["variant_id"] == variant],
            "max_vector_displacement_bu",
        )
        for variant in sorted({row["variant_id"] for row in calibration})
    }
    grid_failures = Counter(
        row.get("failure")
        for cell in grid["cells"]
        for row in cell.get("directional_pixel_perturbations", [])
        if row["status"] == "REJECTED"
    )
    report = {
        "label": LABEL,
        "scope": "CONTROLLED_PROJECTION_SENSITIVITY_NOT_FORMAL_CASES_1_3",
        "checkpoint_commit": "ce2974b25b31a8cb0ec9bc579a84d708d3356bf7",
        "physical_validity": "PARTIAL_PROVISIONAL",
        "coordinate_units": "BLENDER_SCENE_UNITS",
        "core_or_benchmark_semantics_modified": False,
        "coverage_epsilon_scene_units": 0.02,
        "point_budget_authority": "PREDECLARED_DIAGNOSTIC_ONLY_NOT_FORMAL_ACCEPTANCE",
        "sample_analysis_counts": {
            key: analysis[key]
            for key in (
                "source_count",
                "baseline_visible_samples",
                "noise_rows",
                "calibration_rows",
            )
        },
        "variant_count": sweep["variant_count"],
        "classification_counts": sweep["class_counts"],
        "termination_counts": sweep["termination_counts"],
        "boundary_by_source": sweep["boundary_by_source"],
        "most_sensitive_sample_by_jacobian": peak,
        "camera_summary": cameras,
        "numerical_consistency": camera_peaks,
        "calibration_variant_peaks": calibration_peaks,
        "joint_focal_maximum": joint["max"],
        "joint_focal_trial_count": joint["sample_count"],
        "layer_decomposition": layer["source_summaries"],
        "synthetic_directional_failure_counts": dict(grid_failures),
        "implementation_bug_found": False,
        "main_source": "CAMERA_PLANE_GEOMETRY_CONDITIONING_AND_CALIBRATION_SENSITIVITY",
        "hypothesis_supported_in_this_pilot_only": True,
        "causal_scope": (
            "Distance/grazing are isolated in synthetic factorial controls. Camera-region "
            "comparisons alone are confounded by geometry, not hardware-quality rankings."
        ),
        "remaining_issues": [
            "Formal camera/floor/landmark binding, metric scale and physical tolerance unresolved.",
            "Three fixed seeds are not a probability bound; endpoint noise directions matter.",
            "No real calibration uncertainty or CV detection noise was measured.",
            "Original constant-height/linear pilot routes do not prove GAP-length irrelevance.",
            "Mesh/WALL/full-body collision authority remains incomplete.",
        ],
        "inputs_sha256": {
            str(p.relative_to(root)): digest(p)
            for p in (
                root / "source_inventory.json",
                root / "sample_analysis/summary.json",
                root / "downstream_sweep/sweep_report.json",
                root / "layer_evaluation/layer_evaluation.json",
                root / "joint_focal_diagnostic.json",
                root / "synthetic_conditioning_grid.json",
            )
        },
    }
    downstream_chart(root, sweep["results"])
    g, j = peak["conditioning"]["geometry"], peak["conditioning"]["jacobian"]
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — Projection sensitivity report",
        "",
        "## 結論 / Conclusion",
        "",
        "本輪支持既有假說：在目前固定高度、直線pilot geometry中，pixel noise經inverse "
        "ray-plane intersection放大，是已量化的accuracy bottleneck。GAP長度的獨立影響"
        "尚未由本輪noise單因素sweep比較；歷史GAP controls僅供背景。",
        "在本輪metadata、樣本與數值合約範圍，未找到Projection implementation bug證據；"
        "沒有改Graph、Top-K、正式 "
        "benchmark semantics、epsilon或原始camera/plane calibration。Physical validity "
        "仍PARTIAL / PROVISIONAL，實際尺度未核准。",
        "",
        "## Noise → accuracy boundary",
        "",
        "每座標uniformnoise，common unit draws×amplitude；17levels×3fixedseeds×2existing "
        "trajectories=102variants。全部COMPLETE、3candidate routes/6timed hypotheses。",
        f"Accuracy classes: {sweep['class_counts']}。因此search正常不等於Projection accuracy合格。",
        "Coverage沿用ADE<0.02BU；point displacement budget0.02BU僅是事先固定診斷，"
        "不改metric semantics，也不是正式研究容忍度。STABLE/DEGRADED/ACCURACY_FAILURE "
        "分開於INFERENCE_FAILURE；本輪實際synthetic pilot sweep沒有inference failure。",
        "",
        "| Source | Seed | Stable → degraded bracket ±px | "
        "Degraded → accuracy-failure bracket ±px |",
        "| --- | ---: | --- | --- |",
    ]
    for source in sorted(sweep["boundary_by_source"]):
        transitions = sweep["boundary_by_source"][source]
        for seed in sweep["random_seeds"]:
            subset = [row for row in transitions if row["random_seed"] == seed]
            bounds = {
                row["to"]: f"({row['lower_tested_halfwidth_pixels']}, "
                f"{row['upper_tested_halfwidth_pixels']}]"
                for row in subset
            }
            lines.append(
                f"| {source} | {seed} | {bounds.get('DEGRADED', 'not observed')} | "
                f"{bounds.get('ACCURACY_FAILURE', 'not observed')} |"
            )
    lines += [
        "",
        "括號為相鄰已測amplitude，不是精確連續閾值或confidence interval。最早office "
        "Coverage失效介於±0.003–0.0035px；corridor最早介於±0.005–0.01px，但seed差異很大。"
        "某些interiorpoints已明顯移位，gap-endpoint噪聲仍因方向小而讓ADE過關。",
        "",
        "### 必測六個noise levels / seed20261006",
        "",
        "| Source | ±px | ADE / FDE BU | max projected displacement BU | "
        "max point gain BU/px | Coverage1/2/3 |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in sweep["results"]:
        if row["random_seed"] != 20261006 or row["noise_halfwidth_pixels"] not in (
            0,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
        ):
            continue
        first = row["metrics"][0]
        amp = row["projection_amplification"]["point_amplification_max_scene_units_per_pixel"]
        cov = "/".join("T" if r["coverage_at_k"] else "F" for r in row["metrics"])
        lines.append(
            f"| {row['site_id']} | {row['noise_halfwidth_pixels']} | "
            f"{first['ade_first_primary_scene_units']:.8g} / "
            f"{first['fde_first_primary_scene_units']:.8g} | "
            f"{row['projected_displacement']['max_scene_units']:.8g} | "
            f"{amp if amp is not None else 'N/A'} | {cov} |"
        )
    lines += [
        "",
        "minADE@K/minFDE@K與所有seed數值完整保存於downstream_sweep/sweep_table.csv。"
        "不以GT選best candidate；evaluation minimum只是一個metric。",
        "",
        "## Camera / geometry conditioning",
        "",
        f"Peak analyticgain：**{peak['camera_id']} / {peak['site_id']} frame{peak['frame_id']}**，"
        f"{j['max_scene_units_per_pixel']:.8g}BU/px；最低方向gain"
        f"{j['min_scene_units_per_pixel']:.8g}BU/px，顯示強方向性。",
        f"此點camera-distance {g['camera_point_euclidean_distance_scene_units']:.8g}BU；"
        f"axialdepth {g['intersection_axial_depth_scene_units']:.8g}BU；grazing"
        f" {g['grazing_angle_degrees']:.8g}°、ray-normal"
        f" {g['acute_ray_normal_angle_degrees']:.8g}°；off-axis"
        f" {g['optical_off_axis_ray_angle_degrees']:.8g}°；incidence"
        f" {g['normalized_incidence']:.8g}。",
        "Office-region平均最敏感為rear（meanJ≈11.439BU/px）；pooled/peak排序不同，"
        "不能把samplegeometry差異當camera型號優劣。CLASS101較低；CORRIDOR04沒有visible "
        "sample，數值N/A。歷史8.06是最大位移sample的方向gain，不是全域最大gain。",
        "",
        "27個distance/grazing factorial cells固定focal及clip，隔離distance與incidence："
        "遠距離／接近parallel更容易放大pixel擾動。近paralleltoy controls會觸發既有 "
        f"fail-closed合約，directional failures={dict(grid_failures)}。這不是school dataset。",
        "",
        "解析式：X=C+t d，t=n·(P−C)/(n·d)；J=t[A−d(n·A)/(n·d)]。"
        "小n·d讓微小pixel/intrinsic/extrinsic改動被放大；SVD量出最敏感方向。",
        "",
        "## 分層定位 / Layer evidence",
        "",
        "- Float64 versus Decimal60最大差："
        f"{camera_peaks['max_float64_vs_decimal60_difference_bu']:.8g}BU。",
        "- float32 diagnostic versus actualservice："
        f"{camera_peaks['max_float32_vs_service_difference_bu']:.8g}BU；"
        "是診斷副本，不是實際consumer精度。",
        "- PROJECTED inverse→forward roundtrip最大："
        f"{camera_peaks['max_roundtrip_pixel_error']:.8g}px。",
        f"- AnalyticJ versus centraldifference最大relativeerror："
        f"{camera_peaks['max_jacobian_central_difference_relative_error']:.8g}。",
        "- Blenderexport pixels與simulationforward(GT) residual最多約0.000497px；"
        "baseline inverse-GT residual最多約0.001788BU。這個export/calibration residual "
        "包含independent Blender rounding，未證明正式calibration有bug。",
        "- 固定landmarkplane與GT height錯位造成的evaluation-only true-ray mismatch "
        "最多約0.00005131BU，遠小於2.5488BUnoise displacement。這不認證真人/地面plane selection。",
        "- 所有GT檢查僅在projection reference與inference凍結後；GT pixels從未傳進 "
        "inverse service，沒有用GT fitplane或改calibration。",
        "因而主因有geometry-conditioning與calibration-sensitivity證據；forward export "
        "rounding與float32誤差會影響baseline小殘差，但不能解釋主要noise放大量。",
        "",
        "## Calibration / plane diagnostic sensitivity",
        "",
        f"同步fx/fy±0.1%共{joint['sample_count']}trials：最大"
        f" {joint['max']['world_displacement_scene_units']:.8g}BU，全部副本、原始pixels不變。",
        "| Diagnostic change | Maximum displacement BU |",
        "| --- | ---: |",
    ]
    for label, variants in (
        ("fx only ±0.1%", ["fx:-0.001", "fx:+0.001"]),
        ("fy only ±0.1%", ["fy:-0.001", "fy:+0.001"]),
        ("cx ±0.1px", ["cx:-0.1", "cx:+0.1"]),
        ("cy ±0.1px", ["cy:-0.1", "cy:+0.1"]),
        ("local pitch ±0.01°", ["local_pitch:-0.01", "local_pitch:+0.01"]),
        ("local yaw ±0.01°", ["local_yaw:-0.01", "local_yaw:+0.01"]),
        ("world Z translation ±0.1BU", ["world_z:-0.1", "world_z:+0.1"]),
        ("plane height ±0.1BU", ["height:-0.1", "height:+0.1"]),
    ):
        value = max(calibration_peaks[v]["max_vector_displacement_bu"] for v in variants)
        lines.append(f"| {label} | {value:.8g} |")
    lines += [
        "",
        "XYtranslation±0.1BU傳到point約0.1BU。Plane tilt±0.01°繞metadata "
        "origin可產生約3.99BU位移，但含長lever arm與局部plane-height變化；不能全算成 "
        "orientation alone。繞baselinePROJECTEDanchor的tilt保留原交點，位移近0，"
        "只比較Jacobian變化；pivot明示且不用GT。",
        "這些是指定擾動下的敏感度，沒有量測真實calibration uncertainty，不能宣稱 "
        "原calibration錯誤或把不同單位delta直接當風險排名。",
        "",
        "## 下一步與正式Case1–3影響",
        "",
        "Projection仍是這些pilot的主要accuracy bottleneck；GAP影響可行性和多解，"
        "本輪不證明一般非線性/變高度trajectory的GAP誤差較小。正式Cases1–3仍暫緩。",
        "下一步應先審核source-bound landmark/plane/camera bindings與physical scale，"
        "量測真實pixel/calibration uncertainty，建立獨立的view-conditioning/uncertainty "
        "診斷，再決定可用view或robust estimation策略；本輪沒有實作這些策略或放寬epsilon。",
        "WALL/navigation/mesh/full-body authority仍未完整；不以這輪數學一致性取代human authority。",
        "",
        "## Outputs",
        "",
        "[Machine summary](experiment_results.json) · "
        "[Full sweep table](downstream_sweep/sweep_table.csv) · "
        "[Per-camera table](sample_analysis/camera_summary.csv) · "
        "[Geometry samples](sample_analysis/baseline_geometry.jsonl)",
        "[Noise → point error](sample_analysis/noise_vs_3d_error.png) · "
        "[Camera sensitivity](sample_analysis/per_camera_sensitivity.png) · "
        "[Geometry conditioning](sample_analysis/geometry_conditioning.png) · "
        "[Noise → ADE/FDE](noise_to_downstream_metrics.png)",
        "",
        "Three fixed representatives retain byte-identical inference under repeat and GT poison; "
        "all102inference reads allowlisted. Original files/calibration/scenes preserved. "
        "No implementation fix, threshold tuning, rendering or formal Cases1–3.",
        "",
    ]
    (root / "report.md").write_text("\n".join(lines))
    (root / "experiment_results.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", type=Path, required=True)
    args = parser.parse_args()
    report = create_report(args.experiment)
    print(
        json.dumps(
            {
                "label": LABEL,
                "variant_count": report["variant_count"],
                "main_source": report["main_source"],
            }
        )
    )


if __name__ == "__main__":
    main()
