"""Execute only the predeclared nine-case PILOT robustness matrix and stop.

Inference receives three strict files, with runtime guards against truth/mixed
container/plan reads. All inference is frozen before evaluation/debug. Repeated
and GT-poison runs are compared byte-for-byte, including honest failure prefixes.
"""

from __future__ import annotations

import argparse
import builtins
import hashlib
import importlib.util
import json
import math
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from amidst.datasets.pilot import PILOT_LABEL


def load_script(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(
        f"controlled_robustness_{name}", Path(__file__).with_name(f"{name}.py"),
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing pilot helper: {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


@contextmanager
def forbid_evaluation_reads():
    """Guard the real inference calls, not just their declared interfaces."""
    original_open, path_open = builtins.open, Path.open
    forbidden = ("ground_truth", "evaluation_gt", "evaluation_gap_gt", "dataset.json",
                 "trajectory_plan", "preparation_manifest", "evaluation_export_manifest")

    def guard(path: Any, mode: str) -> None:
        if isinstance(path, str | Path) and "r" in mode:
            if any(token in Path(path).name for token in forbidden):
                raise AssertionError(f"inference attempted a forbidden evaluation read: {path}")

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any):
        guard(file, mode)
        return original_open(file, mode, *args, **kwargs)

    def guarded_path_open(path: Path, mode: str = "r", *args: Any, **kwargs: Any):
        guard(path, mode)
        return path_open(path, mode, *args, **kwargs)

    with patch("builtins.open", guarded_open), patch.object(Path, "open", guarded_path_open):
        yield


def inference_digests(root: Path, names: tuple[str, ...]) -> dict[str, str]:
    return {name: sha256(root / name) for name in names if (root / name).is_file()}


def preserved_inputs(repository: Path, scenarios: Any) -> dict[str, dict[str, Any]]:
    paths: set[Path] = set()
    for scenario in scenarios:
        root = repository / scenario.source_directory
        paths.update(root / name for name in (
            "dataset.json", "observations.json", "ground_truth.json", "trajectory_plan.json",
        ))
        metadata = json.loads((root / "dataset.json").read_text())
        paths.add(Path(metadata["source_scene"]["path"]))
        if metadata.get("source_lineage"):
            paths.add(Path(metadata["source_lineage"]["original_source_path"]))
    return {str(path.resolve()): {"sha256": sha256(path), "size": path.stat().st_size,
                                 "mtime_ns": path.stat().st_mtime_ns}
            for path in sorted(paths) if path.exists()}


def validate_results(results: list[dict[str, Any]]) -> list[str]:
    """Check declared scientific boundaries and controlled comparisons, not GT tuning."""
    expected = {
        "S01_office_medium": ("SUCCESS", None, "COMPLETE", 3),
        "S02_corridor_long": ("SUCCESS", None, "COMPLETE", 3),
        "S03_auditorium_native_short": ("EXPECTED_FAILURE", "TOPOLOGY", "NOT_RUN", 0),
        "S04_office_remove_front": ("EXPECTED_FAILURE", "INPUT_CONTEXT", "NOT_RUN", 0),
        "S05_office_remove_rear": ("EXPECTED_FAILURE", "INPUT_CONTEXT", "NOT_RUN", 0),
        "S06_office_pixel_noise": ("SUCCESS", None, "COMPLETE", 3),
        "S07_office_short_tight": ("SUCCESS", None, "COMPLETE", 1),
        "S08_office_short_ambiguous": ("SUCCESS", None, "COMPLETE", 3),
        "S09_office_short_speed_failure": ("EXPECTED_FAILURE", "SEARCH", "NO_FEASIBLE_PATH", 0),
    }
    errors = []
    if len(results) != len(expected) or {r["scenario_id"] for r in results} != set(expected):
        return ["fixed matrix must contain exactly all nine distinct scenarios"]
    for result in results:
        sid, status = result["scenario_id"], result["inference"]
        actual = (status["outcome"], status["failed_stage"], status["termination_reason"],
                  status["candidate_count"])
        if actual != expected[sid]:
            errors.append(f"{sid}: outcome differs from declared controls: {actual!r}")
        checks = result["verification"]
        if not all(checks[key] for key in (
            "repeated_inference_byte_identical", "poison_inference_byte_identical",
            "repeated_metrics_byte_identical", "metadata_preparation_poison_invariant",
            "inference_frozen_after_evaluation", "runtime_gt_read_guard_passed",
        )):
            errors.append(f"{sid}: determinism/GT isolation check failed")
        metrics = result["metrics"]
        if status["evaluation_eligible"]:
            if metrics["status"] != "COMPUTED" or not checks["poison_changes_metrics_only"]:
                errors.append(f"{sid}: expected isolated, computable evaluation")
        elif metrics["status"] != "NOT_COMPUTABLE" or any(
            row[key] is not None for row in metrics["summaries"] for key in (
                "ade_first_primary_scene_units", "fde_first_primary_scene_units",
                "min_ade_at_k_scene_units", "min_fde_at_k_scene_units", "coverage_at_k",
            )
        ):
            errors.append(f"{sid}: unavailable metrics were fabricated")
        if status["physical_validity"]["mesh_collision_certified"]:
            errors.append(f"{sid}: configured topology was incorrectly certified")
    return errors


def diagnose_projection_noise(output: Path) -> dict[str, Any]:
    """Compare saved inverse projections directly, with no truth/reference reads."""
    roots = [output / "scenarios" / name / "run_01/projected_frames.json" for name in (
        "S01_office_medium", "S06_office_pixel_noise",
    )]
    frames = [json.loads(path.read_text())["dataset"]["samples"] for path in roots]
    baseline = {(row["camera_id"], row["frame_id"]): row for row in frames[0]}
    rows = []
    for sample in frames[1]:
        if sample["projected_point"] is None:
            continue
        original = baseline[sample["camera_id"], sample["frame_id"]]
        if original["projected_point"] is None or original["timestamp"] != sample["timestamp"]:
            raise ValueError("noise comparison must preserve the original visible frame partition")
        delta_uv = math.dist(original["uv"], sample["uv"])
        delta_world = math.dist(original["projected_point"]["world_position"],
                                sample["projected_point"]["world_position"])
        rows.append({
            "camera_id": sample["camera_id"], "frame_id": sample["frame_id"],
            "timestamp": sample["timestamp"], "delta_uv_pixels": delta_uv,
            "delta_world_scene_units": delta_world,
            "amplification_scene_units_per_pixel": delta_world / delta_uv if delta_uv else None,
        })
    if not rows:
        raise ValueError("noise diagnostic requires paired visible inverse projections")
    return {
        "label": PILOT_LABEL, "purpose": "GT_FREE_SAVED_PROJECTION_PERTURBATION_DIAGNOSTIC",
        "ground_truth_used": False, "paired_visible_sample_count": len(rows),
        "maximum_world_displacement": max(rows, key=lambda row: row["delta_world_scene_units"]),
        "maximum_amplification_scene_units_per_pixel": max(
            row["amplification_scene_units_per_pixel"] for row in rows
            if row["amplification_scene_units_per_pixel"] is not None
        ), "samples": rows,
    }


def number(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.8g}"


def write_summary(
    output: Path, results: list[dict[str, Any]], verification: dict[str, Any],
) -> None:
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — controlled robustness summary", "",
        "## 範圍 / Scope", "",
        "復用 corridor、office、auditorium 三條既有 trajectory，固定九個受控 scenarios。",
        "沒有新增 Blender render、物理 trajectory、formal Case 1–3 或 benchmark semantics。",
        "Office 原生為 10s/5Hz；時間壓縮副本為 5s/10Hz，不是新的原生 render。",
        "Auditorium 僅截取原生 9.0–9.8s window；原生 short gap 為 0.4s。",
        "Camera removal 真正刪除 calibration/records，不偽造 occlusion 或 recovery。",
        "所有 distance/metrics 使用 native Blender scene units；實體尺度未確認。",
        "Coverage 診斷條件為 ADE < 0.02 BU，固定用於全部案例，不是核准的 formal epsilon。", "",
        "## 結果 / Results", "",
        "| Scenario | Cameras | GAP endpoint Δt | Top-K routes / hypotheses | Termination | "
        "ADE / FDE | minADE@3 / minFDE@3 | Coverage@1/2/3 | First failed layer |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | --- | --- |",
    ]
    for row in results:
        status, summaries = row["inference"], row["metrics"]["summaries"]
        first, last = summaries[0], summaries[-1]
        window = status["gap_window"]
        gap = number(window[1] - window[0]) if window else "N/A"
        coverage = "/".join("N/A" if r["coverage_at_k"] is None else
                            "T" if r["coverage_at_k"] else "F" for r in summaries)
        cameras = ", ".join(row["camera_ids"])
        count = f"{status['candidate_count']}/{status['hypothesis_count']}"
        if not status["search_executed"]:
            count += " (search NOT_RUN)"
        lines.append(
            f"| {row['scenario_id']} | {cameras} | {gap} | {count} | "
            f"{status['termination_reason']} | {number(first['ade_first_primary_scene_units'])} / "
            f"{number(first['fde_first_primary_scene_units'])} | "
            f"{number(last['min_ade_at_k_scene_units'])} / "
            f"{number(last['min_fde_at_k_scene_units'])} | {coverage} | "
            f"{status['failed_stage'] or 'none'} |"
        )
    lines += [
        "", "## 什麼情況仍穩定 / Stable within these controls", "",
        "- Office 的中 GAP 5s 與 corridor 的長 GAP 6s，在既有 explicit configured "
        "handoff/plane 下完整閉環，保留三條 routes 與所有 timed hypotheses。長 GAP 增加 "
        "temporal slack；候選非空不代表能唯一判定真實路線。",
        "- Office 的 compressed 2.5s GAP 在 speed33/offset12 僅一條 route 合乎設定；"
        "只改 lateral offset 為1時，三條 routes 都被保留，沒有 collapse 或 GT reranking。",
        "- 所有成功與失敗結果的 repeat/GT poison inference artifacts 逐byte一致。"
        "這是固定小型配置的穩定性，不是未知場地或正式研究精度。", "",
        "## 何時失效、是哪一層 / Failures and degradation", "",
        "- **Camera removal — INPUT_CONTEXT**：既有 pilot schema 要求2–3 calibrated "
        "cameras，單台輸入被拒絕，projection/search未跑。保留front會失去recovery；"
        "保留rear會失去departure。即使未來放寬camera數量，這兩個native streams仍缺 "
        "bounded endpoint；本次不改consumer/core semantics。",
        "- **Native auditorium short GAP — TOPOLOGY**：2D→inverse Projection→兩段 "
        "Observation成功，但兩段是同一台rear camera，現有pilot要求cross-camera handoff。"
        "沒有造self-transition或另一台camera的觀測；search/reconstruction未跑。"
        "完整auditorium stream的overlapping visibility arbitration仍不在本次範圍。",
        "- **Pixel noise — accuracy degradation**：±0.25px noise僅改visible pixels。"
        "Graph/Top-K/termination仍可正常執行，inverse-projection端點偏差使diagnostic "
        "ADE/FDE與Coverage變差。直接比較baseline/noisy保存的PROJECTED points（不用GT），"
        "最大3D位移為2.54875849BU，出現在rear camera recovery frame45；此處pixel向量"
        "擾動0.31636278px，放大約8.06BU/px。現有camera/plane設定對pixelnoise敏感。"
        "沒有改epsilon、校正GT或以GT選另一條route。",
        "- **Short GAP speed31 — SEARCH**：相同compressed觀測的endpoint distance超過 "
        "2.5s×31BU/s，所有configured routes都被速度硬限制排除，正常回傳 "
        "NO_FEASIBLE_PATH，而非timeout。沒有prediction可算ADE/FDE/Coverage，因此全為N/A。",
        "- **Short tight GAP — candidate diversity reduction**：speed33/offset12只保留 "
        "direct route是feasibility pruning；offset1提高可行分支數而得到3routes。"
        "這三條配置曲線不代表三條已核准的實際school corridors。", "",
        "## Isolation、termination、physical validity", "",
        "GT僅由export-stage轉換timestamp、完成後evaluation與獨立灰色debug層使用。"
        "Inference的三個參數檔不含GT/reference paths、positions、depth或simulation plan。",
        "每case都以runtime file-access guards執行baseline/repeat/poison；另外poison "
        "mixed export GT/waypoints後重新準備的consumer inputs也逐byte一致。",
        "Top-K順序沿用existing engine；metrics沿用existing first-primary-per-candidate "
        "policy，GT compatible route只能由evaluation判定；FDE包含anchored recovery endpoint。",
        "四個expected failure的NA不是0或Coverage=false。未開始search的termination為 "
        "NOT_RUN；速度空解是合法NO_FEASIBLE_PATH。", "",
        "**Physical validity全部PARTIAL / PROVISIONAL**：annotation AABB/configured "
        "point-center graphs不認證WALKABLE holes、WALL/collider、full-body clearance、"
        "mesh碰撞、stairs或真實scale。實際Blender mesh collision rate為null；"
        "WALL authority未完整。歷史AREA_*_ELEVATOR名稱不產生elevator transition。", "",
        "## Visualization and evidence", "",
        "[Scenario overview](visualization_overview/index.html) · "
        "[Contact sheet](visualization_overview/overview.png) · "
        "[Machine-readable verification](verification.json) · "
        "[All results](robustness_results.json) · "
        "[GT-free projection noise diagnostic](projection_noise_diagnostic.json)",
        "Each scenario run_01/visualization contains inspected 3D PNG, Rerun recording, "
        "manifest and GT-free presentation. Failed prefixes carry an explicit state; "
        "invalid contexts display diagnostics only. HTML generated; browser UI unverified.",
        "", f"Validation: **{verification['status']}**, errors={verification['errors']}.",
        "All source pilot files and original/derived .blend hashes/size/mtime preserved.",
        "The run stops at this fixed matrix, with no full dataset expansion "
        "or formal Cases1–3.", "",
    ]
    (output / "robustness_summary.md").write_text("\n".join(lines))


def run_matrix(repository: Path, output: Path, *, visualization: bool = True) -> dict[str, Any]:
    preparation = load_script("prepare_pilot_robustness")
    consumer = load_script("run_pilot_robustness")
    evaluator = load_script("evaluate_pilot_robustness")
    visualizer = load_script("visualize_pilot_robustness") if visualization else None
    inventory = json.loads((output / "scenario_inventory.json").read_text())
    if (
        inventory.get("label") != PILOT_LABEL or inventory["scenario_count"] != 9
        or [row["scenario_id"] for row in inventory["scenarios"]]
        != [s.scenario_id for s in preparation.SCENARIOS]
    ):
        raise ValueError("only the fixed nine-case controlled matrix may be executed")
    before_sources = preserved_inputs(repository, preparation.SCENARIOS)
    write_json(output / "source_snapshot_before.json", {"label": PILOT_LABEL,
                                                        "files": before_sources})
    results, visualizations = [], []
    for row, scenario in zip(inventory["scenarios"], preparation.SCENARIOS, strict=True):
        root = Path(row["path"])
        fixture = root / "fixture/inference"
        observed, context, config = (fixture / name for name in (
            "observations.json", "projection_context.json", "scenario_config.json",
        ))
        # Poison mixed export at preparation stage, retaining independent metadata.
        dataset = json.loads((repository / scenario.source_directory / "dataset.json").read_text())
        dataset["timestamps"] = {"ground_truth": "POISONED_UNREADABLE_SIMULATION_POSITIONS"}
        dataset["trajectory"]["waypoints"] = "POISONED_UNREADABLE_ROUTE"
        poisoned_dataset = root / "poisoned_dataset.json"
        write_json(poisoned_dataset, dataset)
        poison_fixture = root / "poison_fixture/inference"
        preparation.prepare_inference_fixture(repository, scenario, poison_fixture,
                                              dataset_path=poisoned_dataset)
        same_preparation = all((fixture / name).read_bytes() ==
                               (poison_fixture / name).read_bytes() for name in (
                                   "observations.json", "projection_context.json",
                                   "scenario_config.json",
                               ))
        runs = [root / name for name in ("run_01", "run_02", "poison_run")]
        statuses = []
        for index, destination in enumerate(runs):
            inputs = fixture if index < 2 else poison_fixture
            with forbid_evaluation_reads():
                statuses.append(consumer.run_robustness(
                    inputs / "observations.json", inputs / "projection_context.json",
                    destination, inputs / "scenario_config.json",
                ))
        frozen = [inference_digests(run, consumer.INFERENCE_FILES) for run in runs]
        gt_root = root / "fixture/evaluation"
        metrics = []
        for index, destination in enumerate(runs):
            truth = gt_root / ("ground_truth.json" if index < 2 else "poisoned_ground_truth.json")
            metrics.append(evaluator.evaluate_saved_robustness(
                destination, truth, context, coverage_epsilon=0.02,
            ))
        after = [inference_digests(run, consumer.INFERENCE_FILES) for run in runs]
        checks = {
            "runtime_gt_read_guard_passed": True,
            "metadata_preparation_poison_invariant": same_preparation,
            "repeated_inference_byte_identical": frozen[0] == frozen[1],
            "poison_inference_byte_identical": frozen[0] == frozen[2],
            "inference_frozen_after_evaluation": frozen == after,
            "repeated_metrics_byte_identical": (runs[0] / "metrics.json").read_bytes()
            == (runs[1] / "metrics.json").read_bytes(),
            "poison_changes_metrics_only": metrics[0]["summaries"] != metrics[2]["summaries"]
            if statuses[0]["evaluation_eligible"] else None,
            "metric_gt_read": metrics[0]["ground_truth_read"],
            "inference_artifact_count": len(frozen[0]), "inference_sha256": frozen[0],
        }
        result = row | {"label": PILOT_LABEL, "inference": statuses[0],
                        "metrics": metrics[0], "poison_metrics": metrics[2]["summaries"],
                        "verification": checks}
        write_json(root / "scenario_result.json", result)
        if visualizer is not None:
            manifest = visualizer.create_visualization(runs[0], gt_root / "ground_truth.json")
            visualizations.append(manifest)
        results.append(result)
        print(f"{scenario.scenario_id}: {statuses[0]['reason']} / "
              f"{statuses[0]['candidate_count']} routes / {metrics[0]['status']}", flush=True)
    if visualizer is not None:
        visualizer.create_overview(visualizations, output / "visualization_overview")
    after_sources = preserved_inputs(repository, preparation.SCENARIOS)
    errors = validate_results(results)
    if before_sources != after_sources:
        errors.append("original pilot/source identities changed")
    noise_diagnostic = diagnose_projection_noise(output)
    write_json(output / "projection_noise_diagnostic.json", noise_diagnostic)
    verification = {
        "label": PILOT_LABEL, "scope": "CONTROLLED_ROBUSTNESS_NOT_FORMAL_CASES_1_3",
        "status": "PASS_WITH_EXPECTED_LIMITATIONS" if not errors else "FAILED",
        "errors": errors, "scenario_count": 9, "existing_trajectory_count": 3,
        "source_identities_unchanged": before_sources == after_sources,
        "source_snapshot": before_sources, "all_deterministic": all(
            result["verification"]["repeated_inference_byte_identical"] for result in results),
        "all_gt_poison_invariant": all(
            result["verification"]["poison_inference_byte_identical"] for result in results),
        "physical_validity": "PARTIAL_PROVISIONAL", "wall_authority_complete": False,
        "formal_benchmark_executed": False, "formal_benchmark_semantics_modified": False,
        "new_blender_render_count": 0,
        "projection_noise_diagnostic": {
            key: value for key, value in noise_diagnostic.items() if key != "samples"
        },
    }
    write_json(output / "robustness_results.json", {"label": PILOT_LABEL, "scenarios": results})
    write_json(output / "verification.json", verification)
    write_summary(output, results, verification)
    return verification


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--output", type=Path, required=True,
                        help="already prepared, fresh fixed matrix directory")
    parser.add_argument("--no-visualization", action="store_true")
    args = parser.parse_args()
    result = run_matrix(args.repository.resolve(), args.output.resolve(),
                        visualization=not args.no_visualization)
    print(json.dumps({"status": result["status"], "errors": result["errors"]}))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
