"""Compare bounded Blender pilots using export/evaluation evidence and reviewed images.

This script is a report producer. It never calls Projection inference, Graph,
ranking, reconstruction or a benchmark. The source datasets and PNGs stay unchanged.
Image metrics describe the orange synthetic marker, not a person detector or an
approved formal image-quality threshold.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

LABEL = "PILOT / SYNTHETIC SAMPLE"
VISIBILITY = ("visible", "occluded", "out_of_FOV")


def read_json(path: Path) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"Nonfinite JSON value {value} in {path}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def ranges(values: list[float | int]) -> dict[str, float | int | None]:
    return {
        "minimum": min(values) if values else None,
        "median": median(values) if values else None,
        "maximum": max(values) if values else None,
        "count": len(values),
    }


def intervals(rows: list[dict[str, Any]], *, state: str) -> list[dict[str, Any]]:
    """Describe contiguous sampled states without claiming continuous-time visibility."""
    result = []
    start = None
    for index, row in enumerate(rows):
        if row["gap_state"] == state and start is None:
            start = index
        if start is not None and (row["gap_state"] != state or index == len(rows) - 1):
            end = index if row["gap_state"] == state else index - 1
            result.append(
                {
                    "first_index": rows[start]["index"],
                    "last_index": rows[end]["index"],
                    "first_timestamp": rows[start]["timestamp"],
                    "last_timestamp": rows[end]["timestamp"],
                    "timestamp_count": end - start + 1,
                }
            )
            start = None
    return result


def image_metrics(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
        width, height = image.size
    orange = (
        (rgb[:, :, 0] > rgb[:, :, 1] * 1.35)
        & (rgb[:, :, 0] > rgb[:, :, 2] * 1.8)
        & (rgb[:, :, 0] > 0.15)
    )
    yy, xx = np.nonzero(orange)
    bbox = [int(xx.min()), int(yy.min()), int(xx.max()) + 1, int(yy.max()) + 1] if xx.size else None
    luminance = rgb.mean(axis=2)
    return {
        "width": width,
        "height": height,
        "orange_target_pixels": int(xx.size),
        "orange_target_bbox_xyxy": bbox,
        "orange_target_bbox_width_pixels": bbox[2] - bbox[0] if bbox else 0,
        "orange_target_bbox_height_pixels": bbox[3] - bbox[1] if bbox else 0,
        "orange_target_bbox_touches_image_boundary": bool(
            bbox and (bbox[0] == 0 or bbox[1] == 0 or bbox[2] == width or bbox[3] == height)
        ),
        "luminance_mean": float(luminance.mean()),
        "luminance_std": float(luminance.std()),
        "method": "INDEPENDENT_PNG_ORANGE_MASK_DIAGNOSTIC_NOT_CV_DETECTION",
    }


def local_artifact(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if Path(relative).is_absolute() or not path.is_relative_to(root):
        raise ValueError(f"Artifact escapes pilot root: {relative}")
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def summarize_site(root: Path, assessment: dict[str, Any] | None = None) -> dict[str, Any]:
    root = root.resolve()
    data = read_json(root / "dataset.json")
    validation = read_json(root / "validation.json")
    plan = read_json(root / "trajectory_plan.json")
    representatives = read_json(root / "representative_frames.json")
    if data["label"] != LABEL or validation["label"] != LABEL:
        raise ValueError(f"Pilot labels missing from {root}")
    if validation["dataset_sha256"] != digest(root / "dataset.json"):
        raise ValueError(f"Stale validation: dataset digest differs in {root}")
    if plan["source_asset_sha256"] != data["source_scene"]["sha256_before"]:
        raise ValueError(f"Trajectory plan source digest differs in {root}")
    rows = data["timestamps"]
    camera_ids = [camera["camera_id"] for camera in data["cameras"]]
    for row in rows:
        sample_ids = [item["camera_id"] for item in row["per_camera"]]
        if len(sample_ids) != len(camera_ids) or set(sample_ids) != set(camera_ids):
            raise ValueError(f"Incomplete or duplicate camera samples at {root}: {row['index']}")
    per_camera = {}
    all_counts: Counter[str] = Counter({key: 0 for key in VISIBILITY})
    image_by_frame = {}
    for camera_id in camera_ids:
        samples = [
            sample
            for row in rows
            for sample in row["per_camera"]
            if sample["camera_id"] == camera_id
        ]
        counts: Counter[str] = Counter({key: 0 for key in VISIBILITY})
        visible_metrics = []
        all_metrics = []
        partial_camera_gaps = 0
        for row in rows:
            sample = next(item for item in row["per_camera"] if item["camera_id"] == camera_id)
            path = local_artifact(root, sample["render"]["path"])
            if digest(path) != sample["render"]["sha256"]:
                raise ValueError(f"Render SHA-256 mismatch: {path}")
            metrics = image_metrics(path)
            image_by_frame[(row["index"], camera_id)] = metrics
            all_metrics.append(metrics)
            counts[sample["visibility"]] += 1
            if sample["visibility"] == "visible":
                visible_metrics.append(metrics)
            elif metrics["orange_target_pixels"]:
                partial_camera_gaps += 1
        all_counts.update(counts)
        per_camera[camera_id] = {
            "record_count": len(samples),
            "visibility_counts": dict(counts),
            "nonvisible_landmark_with_body_pixels_count": partial_camera_gaps,
            "visible_marker_pixels": ranges([m["orange_target_pixels"] for m in visible_metrics]),
            "visible_marker_bbox_width_pixels": ranges(
                [m["orange_target_bbox_width_pixels"] for m in visible_metrics]
            ),
            "visible_marker_bbox_height_pixels": ranges(
                [m["orange_target_bbox_height_pixels"] for m in visible_metrics]
            ),
            "visible_marker_bbox_touches_image_boundary_count": sum(
                m["orange_target_bbox_touches_image_boundary"] for m in visible_metrics
            ),
            "luminance_mean": ranges([m["luminance_mean"] for m in all_metrics]),
            "luminance_std": ranges([m["luminance_std"] for m in all_metrics]),
            "render_resolution": sorted({(m["width"], m["height"]) for m in all_metrics}),
        }
    gaps = [row for row in rows if row["gap_state"] == "GAP"]
    hidden_indices = [
        row["index"]
        for row in gaps
        if all(
            image_by_frame[(row["index"], camera_id)]["orange_target_pixels"] == 0
            for camera_id in camera_ids
        )
    ]
    representative_rows = []
    for record in representatives:
        local_artifact(root, record["path"])
        row = rows[record["index"]]
        representative_rows.append(
            {
                **record,
                "gap_state": row["gap_state"],
                "camera_image_metrics": {
                    camera_id: image_by_frame[(row["index"], camera_id)] for camera_id in camera_ids
                },
            }
        )
    assessment = assessment or {}
    if assessment.get("reviewed") and assessment.get("dataset_sha256") != digest(
        root / "dataset.json"
    ):
        raise ValueError(f"Reviewed assessment is not bound to this dataset in {root}")
    for relative, expected in assessment.get("inspected_artifact_sha256", {}).items():
        if digest(local_artifact(root, relative)) != expected:
            raise ValueError(f"Inspected artifact changed since visual review: {root / relative}")
    if dict(all_counts) != validation["visibility_counts"]:
        raise ValueError(f"Recounted visibility differs from validator in {root}")
    if len(rows) != validation["timestamp_count"] or len(rows) != 50:
        raise ValueError(f"Unexpected timestamp count in {root}")
    if sum(all_counts.values()) != validation["decoded_render_count"]:
        raise ValueError(f"Recounted camera records differ from validator renders in {root}")
    invalid = (
        bool(validation["errors"])
        or validation["status"] == "FAILED"
        or not validation["source_identity_verified"]
    )
    site_id = plan.get("site_id", root.name)
    site_label = assessment.get("site_label", plan.get("site_label", site_id))
    suitability = assessment.get("pilot_suitability", "AWAITING_AGENT_IMAGE_REVIEW")
    if invalid:
        suitability = "FAILED_TECHNICAL_VALIDATION"
    support = plan.get("floor_support_evidence", {})
    return {
        "site_id": site_id,
        "site_label": site_label,
        "sample_role": data.get("sample_role", plan.get("sample_role", "VISIBLE_GAP_VISIBLE")),
        "sample_origin": assessment.get("sample_origin", "NEW_MULTISITE_SAMPLE"),
        "area_id": plan.get("area_id"),
        "run_root": str(root),
        "dataset_sha256": validation["dataset_sha256"],
        "source_asset_sha256": data["source_scene"]["sha256_before"],
        "trajectory": data["trajectory"],
        "sampling": {
            "duration_seconds": data["duration_seconds"],
            "sampling_fps": data["sampling_fps"],
            "timestamp_count": len(rows),
            "successful_timestamps": data["successful_timestamps"],
            "expected_render_count": validation["expected_camera_frame_count"],
            "verified_render_count": validation["decoded_render_count"],
        },
        "technical_status": "FAILED" if invalid else "PASS",
        "validator_status": validation["status"],
        "source_identity_verified": validation["source_identity_verified"],
        "trajectory_plan_binding_validation": validation.get("trajectory_plan_binding", {}),
        "visibility_counts_camera_records": dict(all_counts),
        "per_camera": per_camera,
        "selected_camera_point_visibility": {
            "observed_timestamps": len(rows) - len(gaps),
            "gap_timestamps": len(gaps),
            "fully_hidden_marker_gap_timestamps": len(hidden_indices),
            "partially_visible_marker_gap_timestamps": len(gaps) - len(hidden_indices),
            "fully_hidden_marker_gap_indices": hidden_indices,
            "gap_sample_intervals": intervals(rows, state="GAP"),
            "observed_gap_observed_recovery": validation["observed_gap_observed_recovery"],
            "scope": "ONLY_THE_SELECTED_CAMERAS_NOT_ALL_SCHOOL_CAMERAS",
            "landmark": "SYNTHETIC_TARGET_BODY_CENTER_NOT_WHOLE_BODY_DETECTION",
        },
        "geometry_evidence": {
            "floor_support": support,
            "support_timestamp_count": sum(
                bool(row.get("physical_support")) for row in plan.get("samples", [])
            ),
            "search_evidence": plan.get("search_evidence", {}),
            "authority": "PILOT_GEOMETRY_DIAGNOSTIC_NOT_NAVIGATION_CERTIFICATION",
        },
        "projection_diagnostics": validation["projection"],
        "independent_image_metrics": {
            "method": "READ_ALL_PNGS_RECHECK_HASH_ORANGE_MASK_BOUNDS_AND_BRIGHTNESS",
            "formal_acceptance_thresholds": None,
            "metrics_do_not_certify_materials_or_real_person_detection": True,
        },
        "agent_visual_assessment": {
            "reviewer": "CODEX_AGENT",
            "reviewed": assessment.get("reviewed", False),
            "inspected_representative_stages": assessment.get(
                "inspected_representative_stages", []
            ),
            "inspected_artifact_sha256": assessment.get("inspected_artifact_sha256", {}),
            "findings": assessment.get("findings", []),
            "limitations": assessment.get("limitations", []),
            "judgment": assessment.get("judgment", "尚未完成本次畫面檢查。"),
            "human_acceptance_record": False,
        },
        "pilot_suitability": suitability,
        "full_dataset_ready": False,
        "full_dataset_readiness_reasons": [
            "Physical scale and formal floor/camera-plane authority remain unverified.",
            "Workbench gray mesh and synthetic point observations do not certify photorealistic "
            "or CV detector dataset quality.",
            "Bounded local routes do not establish complete school coverage "
            "or navigation authority.",
        ],
        "artifacts": {
            "dataset": "dataset.json",
            "observations": "observations.json",
            "ground_truth": "ground_truth.json",
            "validation": "validation.json",
            "sample_report": "sample_report.md",
            "review": "review.html",
            "synchronized_preview": "trajectory_preview.gif",
            "trajectory_map": "trajectory_preview.png",
            "representatives": representative_rows,
        },
        "validation_errors": validation["errors"],
        "validation_warnings": validation["warnings"],
    }


def link_path(output_root: Path, site: dict[str, Any], artifact: str) -> str:
    return Path(os.path.relpath(Path(site["run_root"]) / artifact, output_root)).as_posix()


def number(value: float | int | None) -> str:
    return "N/A" if value is None else f"{value:.6g}"


def markdown_report(report: dict[str, Any], output_root: Path) -> str:
    new_labels = "、".join(
        site["site_label"]
        for site in report["sites"]
        if site["sample_origin"] == "NEW_MULTISITE_SAMPLE"
    )
    reference_labels = "、".join(
        site["site_label"]
        for site in report["sites"]
        if site["sample_origin"] == "PREVIOUS_PILOT_REFERENCE"
    )
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — 多場地比較與判斷",
        "",
        "資料來自同一個 school_v3 場景中的不同空間；每組為獨立 10 秒、5 FPS 的小型 pilot。",
        f"新資料：{new_labels or '無'}。先前資料參照：{reference_labels or '無'}。"
        "這些是場景中的不同空間，不代表不同學校或建築。",
        "Camera record 的 visible/occluded/out-of-FOV 與 timestamp 的整體 GAP 使用不同分母。",
        "GAP 依所選相機的身體中心點判定；部分身體仍露出的 GAP 與完全不可見分開記錄。",
        "GT 僅供 simulation/export/evaluation/debug visualization，未跑正式 Cases 1–3；"
        "未啟動 Graph、ranking 或 reconstruction。",
        "",
        "| 場地 | timestamps | camera renders | visible / occluded / out-of-FOV | "
        "point GAP（完全遮擋 / 部分身體）| 技術 | pilot 判斷 |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for site in report["sites"]:
        sample = site["sampling"]
        counts = site["visibility_counts_camera_records"]
        gap = site["selected_camera_point_visibility"]
        lines.append(
            f"| {site['site_label']} | {sample['successful_timestamps']}/50 | "
            f"{sample['verified_render_count']}/{sample['expected_render_count']} | "
            f"{counts['visible']} / {counts['occluded']} / {counts['out_of_FOV']} | "
            f"{gap['gap_timestamps']}（{gap['fully_hidden_marker_gap_timestamps']} / "
            f"{gap['partially_visible_marker_gap_timestamps']}）| "
            f"{site['technical_status']} | {site['pilot_suitability']} |"
        )
    for site in report["sites"]:
        trajectory = site["trajectory"]
        projection = site["projection_diagnostics"]
        gap = site["selected_camera_point_visibility"]
        visual = site["agent_visual_assessment"]
        support = site["geometry_evidence"]["floor_support"]
        support_count = site["geometry_evidence"]["support_timestamp_count"]
        forward_error = projection["native_blender_forward_max_error_pixels"]
        role_note = (
            "控制組檢查中心點持續可見，不要求 GAP。"
            if site["sample_role"] == "FULLY_OBSERVED_CONTROL"
            else "檢查 observed → GAP → observed 的中心點觀測恢復。"
        )
        lines += [
            "",
            f"## {site['site_label']}",
            "",
            f"**判斷：{visual['judgment']}**",
            "",
            f"- Floor `{trajectory['floor_id']}`；trajectory `{trajectory['trajectory_id']}`。",
            f"- Sample role：`{site['sample_role']}`；{role_note}",
            f"- 規劃長 {number(trajectory['configured_length_scene_units'])} scene units；"
            f"實際 50 個採樣點路段長 {number(trajectory['length_scene_units'])} scene units。"
            "10 秒窗口，0.0–9.8 秒；米制尺度與真實人體速度未認證。",
            f"- observed → GAP → observed：`{gap['observed_gap_observed_recovery']}`；"
            f"完全看不到 marker 的 GAP {gap['fully_hidden_marker_gap_timestamps']} timestamps；"
            f"部分身體可見 {gap['partially_visible_marker_gap_timestamps']} timestamps。",
            f"- Mesh support timestamps：{support_count}/50；"
            f"target sweep clear：`{support.get('target_full_sweep_clear', 'N/A')}`。"
            "這是局部幾何診斷，不是完整 navigation 認證。",
            f"- Forward 最大誤差 {number(forward_error)} px；"
            f"inverse 最大誤差 {number(projection['pilot_plane_inverse_max_error_scene_units'])} "
            f"scene units；unexpected failures {len(projection['unexpected_failures'])}。",
            "- 本次由 Codex 檢視代表影格；不記為使用者正式影像驗收。",
            "",
            "| Camera | visible | occluded | out-of-FOV | visible marker 寬 / 高 px（min–max）| "
            "marker 接觸影像邊界 |",
            "| --- | ---: | ---: | ---: | --- | ---: |",
        ]
        for camera_id, camera in site["per_camera"].items():
            c = camera["visibility_counts"]
            w, h = (
                camera["visible_marker_bbox_width_pixels"],
                camera["visible_marker_bbox_height_pixels"],
            )
            lines.append(
                f"| {camera_id} | {c['visible']} | {c['occluded']} | {c['out_of_FOV']} | "
                f"{number(w['minimum'])}–{number(w['maximum'])} / "
                f"{number(h['minimum'])}–{number(h['maximum'])} | "
                f"{camera['visible_marker_bbox_touches_image_boundary_count']} |"
            )
        lines += ["", "畫面檢視："] + [f"- {item}" for item in visual["findings"]]
        lines += ["", "適用限制："] + [f"- {item}" for item in visual["limitations"]]
        lines += ["", "五個代表 frames：", ""]
        for record in site["artifacts"]["representatives"]:
            target = link_path(output_root, site, record["path"])
            lines.append(f"- [{record['stage']} / {record['timestamp']:.1f}s]({target})")
        lines += ["", "資料與預覽：", ""]
        for name, label in [
            ("synchronized_preview", "同步 GIF"),
            ("trajectory_map", "Trajectory 圖"),
            ("dataset", "Dataset JSON"),
            ("observations", "純 2D observations"),
            ("ground_truth", "Evaluation-only GT"),
            ("review", "單組 review"),
        ]:
            lines.append(f"- [{label}]({link_path(output_root, site, site['artifacts'][name])})")
    lines += [
        "",
        "## 完整生成判斷",
        "",
        "本批可作為不同空間的點可見性、遮擋與資料品質 pilot。"
        "各組具體可用性依上述判斷，技術 PASS 不等於完整 dataset readiness。",
        "完整 Blender generation 暫不開始：物理尺度、正式 floor/camera-plane authority、"
        "完整 route coverage 及正式 render/observation policy 尚未成立。"
        "本次止於小型多場地 samples，未擴成完整資料集。",
        "",
    ]
    return "\n".join(lines)


def html_report(report: dict[str, Any], output_root: Path) -> str:
    def anchor(site: dict[str, Any], artifact: str, label: str) -> str:
        return (
            f'<a href="{html.escape(link_path(output_root, site, artifact), quote=True)}">'
            f"{html.escape(label)}</a>"
        )

    cards = []
    for site in report["sites"]:
        gap = site["selected_camera_point_visibility"]
        visual = site["agent_visual_assessment"]
        representatives = []
        for record in site["artifacts"]["representatives"]:
            path = html.escape(link_path(output_root, site, record["path"]), quote=True)
            representatives.append(
                f'<figure><img loading="lazy" src="{path}" alt="{html.escape(record["stage"])}">'
                f"<figcaption>{html.escape(record['stage'])} / {record['timestamp']:.1f}s"
                f" / {record['gap_state']}</figcaption></figure>"
            )
        preview = html.escape(
            link_path(output_root, site, site["artifacts"]["synchronized_preview"]), quote=True
        )
        links = " · ".join(
            anchor(site, site["artifacts"][key], label)
            for key, label in [
                ("dataset", "Dataset JSON"),
                ("observations", "純 2D observations"),
                ("ground_truth", "Evaluation-only GT"),
                ("sample_report", "Sample report"),
                ("review", "單組 review"),
                ("synchronized_preview", "同步 GIF"),
            ]
        )
        counts = site["visibility_counts_camera_records"]
        cards.append(
            f'<section id="{html.escape(site["site_id"], quote=True)}">'
            f"<h2>{html.escape(site['site_label'])}</h2>"
            f'<p class="judgment">{html.escape(visual["judgment"])}</p>'
            f"<p>技術 {site['technical_status']} · {site['sampling']['successful_timestamps']}/50 "
            f"timestamps · visible {counts['visible']} / occluded {counts['occluded']} "
            f"/ out-of-FOV {counts['out_of_FOV']} camera records</p>"
            f"<p>point GAP {gap['gap_timestamps']} timestamps：完全遮擋 "
            f"{gap['fully_hidden_marker_gap_timestamps']} / 部分身體 "
            f"{gap['partially_visible_marker_gap_timestamps']}</p>"
            f'<p>{links}</p><img class="preview" loading="lazy" src="{preview}" '
            f'alt="{html.escape(site["site_label"])} synchronized preview">'
            "<ul>"
            + "".join(f"<li>{html.escape(item)}</li>" for item in visual["findings"])
            + '</ul><details><summary>五個代表 frames</summary><div class="frames">'
            + "".join(representatives)
            + "</div></details></section>"
        )
    return (
        '<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>PILOT / SYNTHETIC SAMPLE 多場地比較</title><style>"
        "body{margin:0;background:#f3f5f7;color:#172033;font:16px/1.6 system-ui}"
        "main{max-width:1260px;margin:auto;padding:28px}section{background:white;"
        "padding:24px;border-radius:12px;margin:24px 0}h1{font-size:28px}h2{font-size:24px}"
        "img{max-width:100%;height:auto}.preview{width:960px}.judgment{font-weight:650}"
        "a{color:#075fa8}summary{cursor:pointer;font-weight:600}.frames{display:grid;"
        "grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}"
        "figure{margin:12px 0}figcaption{font-size:14px}aside{padding:16px;background:#e9eef4}"
        "@media(max-width:520px){main{padding:12px}section{padding:14px}"
        ".frames{grid-template-columns:1fr}}</style><main><h1>"
        + LABEL
        + " — 多場地比較與判斷</h1><aside>同一個 school_v3 場景中的不同空間。"
        "每組 10 秒 / 5 FPS / 50 timestamps。狀態依 body-center landmark，"
        "所選相機的 GAP 不代表全校相機都看不到。GT 只供 simulation/export/evaluation；"
        "未跑正式 benchmark。<br>Codex 畫面檢視是 pilot 可用性判斷，"
        "不是正式人類驗收。完整 dataset generation 尚不開始。</aside>"
        '<p><a href="comparison.md">詳細報告</a> · <a href="comparison.json">比較 JSON</a>'
        "</p>" + "".join(cards) + "</main></html>"
    )


def overview(report: dict[str, Any], output_root: Path) -> None:
    width, row_height = 960, 270
    canvas = Image.new("RGB", (width, 50 + row_height * len(report["sites"])), "#f3f5f7")
    draw = ImageDraw.Draw(canvas)
    font_path = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    font = (
        ImageFont.truetype(str(font_path), 17) if font_path.is_file() else ImageFont.load_default()
    )
    draw.text((16, 14), LABEL + " | distinct school locations", font=font, fill="#172033")
    for index, site in enumerate(report["sites"]):
        records = site["artifacts"]["representatives"]
        gap_records = [record for record in records if record["gap_state"] == "GAP"]
        middle = gap_records[len(gap_records) // 2] if gap_records else records[len(records) // 2]
        after_gap = [
            record
            for record in records
            if record["gap_state"] == "OBSERVED" and record["index"] > middle["index"]
        ]
        end = after_gap[0] if gap_records and after_gap else records[-1]
        chosen = [records[0], middle, end]
        top = 50 + row_height * index
        draw.text((16, top + 8), site["site_id"], font=font, fill="#172033")
        for column, record in enumerate(chosen):
            with Image.open(Path(site["run_root"]) / record["path"]) as image:
                tile = image.convert("RGB")
                tile.thumbnail((310, 216), Image.Resampling.LANCZOS)
            canvas.paste(tile, (column * 320 + 5, top + 37))
    canvas.save(output_root / "overview.png")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--assessment",
        type=Path,
        help="JSON map by run-directory name: agent observations after image inspection",
    )
    parser.add_argument("--refresh-summary", action="store_true")
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    protected = [output_root / name for name in ("comparison.json", "comparison.md", "review.html")]
    if not args.refresh_summary and any(path.exists() for path in protected):
        raise FileExistsError("Comparison exists; choose a fresh output or --refresh-summary")
    assessments = read_json(args.assessment) if args.assessment else {}
    sites = [summarize_site(root, assessments.get(root.name)) for root in args.site]
    if len({site["site_id"] for site in sites}) != len(sites):
        raise ValueError("Distinct site IDs are required")
    report = {
        "schema_version": "blender-pilot-multisite-review-v1",
        "label": LABEL,
        "data_kind": "SYNTHETIC",
        "purpose": "BOUNDED_MULTISITE_PILOT_QUALITY_REVIEW",
        "site_count": len(sites),
        "sites": sites,
        "new_site_count": sum(site["sample_origin"] == "NEW_MULTISITE_SAMPLE" for site in sites),
        "new_sample_successful_timestamps": sum(
            site["sampling"]["successful_timestamps"]
            for site in sites
            if site["sample_origin"] == "NEW_MULTISITE_SAMPLE"
        ),
        "new_sample_verified_renders": sum(
            site["sampling"]["verified_render_count"]
            for site in sites
            if site["sample_origin"] == "NEW_MULTISITE_SAMPLE"
        ),
        "total_successful_timestamps": sum(
            site["sampling"]["successful_timestamps"] for site in sites
        ),
        "total_verified_renders": sum(site["sampling"]["verified_render_count"] for site in sites),
        "full_dataset_ready": False,
        "formal_benchmark_executed": False,
        "gt_isolation": "REPORT_EVALUATION_ONLY_NO_INFERENCE_GRAPH_RANKING_RECONSTRUCTION_CALLS",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output_root / "comparison.md").write_text(
        markdown_report(report, output_root), encoding="utf-8"
    )
    (output_root / "review.html").write_text(html_report(report, output_root), encoding="utf-8")
    overview(report, output_root)
    print(
        json.dumps(
            {
                "site_count": len(sites),
                "timestamps": report["total_successful_timestamps"],
                "renders": report["total_verified_renders"],
                "report": str(output_root / "comparison.md"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
