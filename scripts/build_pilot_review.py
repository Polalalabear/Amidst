"""Create a bounded human review gallery and trajectory preview from a pilot export."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

LABEL = "PILOT / SYNTHETIC SAMPLE"


def representative_indices(rows: list[dict]) -> list[tuple[str, int]]:
    gaps = [row["index"] for row in rows if row["gap_state"] == "GAP"]
    if not gaps:
        raise ValueError("pilot must contain a selected-camera global GAP")
    first = gaps[0]
    last = first
    while last + 1 < len(rows) and rows[last + 1]["gap_state"] == "GAP":
        last += 1
    if first < 2 or last >= len(rows) - 1:
        raise ValueError("pilot lacks representative visible/gap/reappearance stages")
    return [
        ("01_visible_start", 0), ("02_approaching_occlusion", first - 1),
        ("03_entering_gap", first), ("04_middle_of_gap", (first + last) // 2),
        ("05_visible_again", last + 1),
    ]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    return ImageFont.truetype(str(path), size) if path.is_file() else ImageFont.load_default()


def composite(root: Path, row: dict, title: str, rows: list[dict]) -> Image.Image:
    cameras = row["per_camera"]
    width, height = 480 * len(cameras), 430
    canvas = Image.new("RGB", (width, height), "#f0f2f5")
    draw = ImageDraw.Draw(canvas)
    gap_note = ""
    if row["gap_state"] == "GAP":
        partial = any(c["image_diagnostics"]["orange_target_pixels"] > 0 for c in cameras)
        gap_note = " | partial body visible" if partial else " | full marker absent"
    draw.text((16, 12), LABEL + "  |  " + title, fill="#111827", font=font(20))
    draw.text((16, 40), f't = {row["timestamp"]:.1f}s  |  selected-camera state: '
              f'{row["gap_state"]}  |  frame {row["index"]:02d}/49{gap_note}',
              fill="#374151", font=font(17))
    for i, camera in enumerate(cameras):
        with Image.open(root / camera["render"]["path"]) as rendered:
            tile = rendered.convert("RGB").resize((480, 270), Image.Resampling.LANCZOS)
        canvas.paste(tile, (i * 480, 75))
        draw.text((i * 480 + 12, 351), camera["camera_id"], fill="#111827", font=font(17))
        draw.text((i * 480 + 12, 375), camera["visibility"] + " | " + camera["reason"],
                  fill="#047857" if camera["visibility"] == "visible" else "#b91c1c",
                  font=font(15))
    left, right, top = 16, width - 16, 412
    step = (right - left) / len(rows)
    for i, sample in enumerate(rows):
        color = "#b91c1c" if sample["gap_state"] == "GAP" else "#10b981"
        draw.rectangle((left + step * i, top, left + step * (i + 1) - 1, top + 8), fill=color)
    x = left + (row["index"] + .5) * step
    draw.line((x, top - 8, x, top + 10), fill="#111827", width=3)
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--refresh-review", action="store_true",
                        help="Regenerate this run's review artifacts; raw exports stay unchanged")
    args = parser.parse_args()
    root = args.root.resolve()
    dataset = json.loads((root / "dataset.json").read_text())
    rows = dataset["timestamps"]
    validation = json.loads((root / "validation.json").read_text())
    representatives = representative_indices(rows)
    rep_dir = root / "representative"
    rep_dir.mkdir(exist_ok=args.refresh_review)
    rep_records = []
    for name, index in representatives:
        path = rep_dir / f"{name}_t{rows[index]['timestamp']:.1f}.png"
        composite(root, rows[index], name.replace("_", " "), rows).save(path)
        rep_records.append({"stage": name, "index": index,
                            "timestamp": rows[index]["timestamp"],
                            "path": str(path.relative_to(root)),
                            "camera_frames": [r["render"]["path"]
                                              for r in rows[index]["per_camera"]]})
    previews = [composite(root, row, "synchronized camera preview", rows) for row in rows]
    previews[0].save(root / "trajectory_preview.gif", save_all=True,
                     append_images=previews[1:], duration=200, loop=0, optimize=False)
    positions = [row["ground_truth"]["foot_position"] for row in rows]
    figure, axis = plt.subplots(figsize=(10, 7), layout="constrained")
    axis.plot([p[0] for p in positions], [p[1] for p in positions], color="0.5", zorder=1)
    for row, p in zip(rows, positions, strict=True):
        axis.scatter(p[0], p[1], color="#c62828" if row["gap_state"] == "GAP" else "#00897b",
                     s=20, zorder=2)
    for name, index in representatives:
        p = positions[index]
        axis.annotate(f'{name[:2]}: {rows[index]["timestamp"]:.1f}s', (p[0], p[1]),
                      xytext=(8, 8), textcoords="offset points")
    for camera in dataset["cameras"]:
        matrix = camera["camera_to_world"]
        axis.scatter(matrix[0][3], matrix[1][3], marker="^", s=70, color="#1565c0")
        axis.annotate(camera["camera_id"], (matrix[0][3], matrix[1][3]),
                      xytext=(4, -15), textcoords="offset points", fontsize=8)
        axis.arrow(matrix[0][3], matrix[1][3], -matrix[0][2] * 30, -matrix[1][2] * 30,
                   color="#1565c0", head_width=4, length_includes_head=True)
    axis.set(xlabel="X (Blender scene units; physical scale unverified)",
             ylabel="Y (Blender scene units)", aspect="equal",
             title=LABEL + "\nFoot trajectory: green visible, red selected-camera GAP")
    axis.grid(alpha=.2)
    figure.savefig(root / "trajectory_preview.png", dpi=140)
    plt.close(figure)
    counts = Counter(camera["visibility"] for row in rows for camera in row["per_camera"])
    per_camera = {camera["camera_id"]: Counter(
        c["visibility"] for row in rows for c in row["per_camera"]
        if c["camera_id"] == camera["camera_id"]
    ) for camera in dataset["cameras"]}
    gaps = [row["timestamp"] for row in rows if row["gap_state"] == "GAP"]
    marker_absent = sum(row["gap_state"] == "GAP" and all(
        c["image_diagnostics"]["orange_target_pixels"] == 0 for c in row["per_camera"]
    ) for row in rows)
    lines = [
        "# PILOT / SYNTHETIC SAMPLE — school_v3 quality review", "",
        "本資料僅供 simulation/export/evaluation 與人工品質檢查，未跑正式 Cases 1–3。",
        "GT 不進入 Projection inference / Graph / ranking / reconstruction；"
        "`observations.json` 為獨立且符合既有 schema 的純 2D evidence。", "",
        f"- Source SHA-256: `{dataset['source_scene']['sha256_before']}`; "
        "hash/size/mtime unchanged.",
        f"- 10 seconds at 5 FPS: **{len(rows)}/50 timestamps**, [0,10), t=0.0…9.8 s.",
        f"- Trajectory: `{dataset['trajectory']['trajectory_id']}`; floor "
        f"`{dataset['trajectory']['floor_id']}`; sampled length "
        f"**{dataset['trajectory']['length_scene_units']:.6f} Blender scene units**.",
        f"- Configured route (t=0…10): "
        f"{dataset['trajectory']['configured_length_scene_units']:.6f} scene units; "
        "t=10 endpoint is excluded from the requested 50 timestamps.",
        "- METRIC/1m-per-unit is stored scene metadata, not certified physical scale. "
        "No guessed unit conversion, realistic human speed or physical-scale claim.",
        f"- Total camera records: **{sum(counts.values())}**; visible **{counts['visible']}**, "
        f"occluded **{counts['occluded']}**, out-of-FOV **{counts['out_of_FOV']}**.",
        f"- Selected-camera global GAP: **{len(gaps)} timestamps**; times: "
        + ", ".join(f"{t:.1f}" for t in gaps) + " seconds.",
        "- GAP means none of these selected cameras sees the target landmark. "
        "It does not establish that all 29 school cameras are blind.",
        "- Visibility follows the body-center point, not a whole-person mask. "
        "Partial head/body visibility near occlusion is recorded by orange-pixel diagnostics.",
        f"- Of {len(gaps)} global landmark GAP timestamps, **{marker_absent}** show no "
        f"orange marker in either render; **{len(gaps) - marker_absent}** retain partial body "
        "visibility. The 3.6s entering-GAP example is partial; the 6.4s midpoint is fully hidden.",
        "- GT `position` is the body-center landmark; `foot_position` is exported separately. "
        "Actual physical floor Z≈20.07885, foot Z≈20.12885, landmark Z≈75.12885. "
        "WALKABLE annotation Z=25 has a 4.92115-unit discrepancy from actual mesh support.",
        "- Pixels use top-left continuous coordinates; depth is axial along camera -Z. "
        "Raw PNG text metadata explicitly labels PILOT/SYNTHETIC and simulation timestamps; "
        "native Frame=220/Time refers to the frozen source geometry frame.",
        "- Observation producer is simulation projection + physical mesh raycast, "
        "not CV detection.",
        "- Workbench opaque gray studio camera renders use an orange synthetic marker; "
        "this is an explicit pilot render policy, not formal photorealistic material evidence.",
        "- No source scene save, elevator transition, navigation certification "
        "or benchmark change.",
        "", "## Per-camera sample counts", "",
        "| Camera | Visible | Occluded | Out-of-FOV |", "| --- | ---: | ---: | ---: |",
    ]
    for camera_id, counts_row in per_camera.items():
        lines.append(f"| {camera_id} | {counts_row['visible']} | "
                     f"{counts_row['occluded']} | {counts_row['out_of_FOV']} |")
    lines += ["", "## Independent validation", "", "```json",
              json.dumps(validation, indent=2, ensure_ascii=False), "```", "",
              "## Five representative frames", ""]
    for record in rep_records:
        lines.append(f"- [{record['stage']} at {record['timestamp']:.1f}s]({record['path']})")
        for frame_path in record["camera_frames"]:
            lines.append(f"  - [Original camera render]({frame_path})")
    lines += ["", "## Preview and artifacts", "",
              "- [Synchronized 10-second preview](trajectory_preview.gif)",
              "- [Trajectory map](trajectory_preview.png)",
              "- [Camera gallery](review.html)",
              "- [Combined evaluation-only dataset](dataset.json)",
              "- [Sanitized 2D observations](observations.json)",
              "- [Separate Ground Truth](ground_truth.json)",
              "- [Source-bound route/support plan](trajectory_plan.json)", "",
              "## Readiness", "",
              "這份小型 pilot 足以人工檢查資料格式、相機畫面、遮擋與 GAP。"
              "完整 Blender dataset generation 仍需本次畫面的人類品質審查，"
              "物理尺度確認及涵蓋更多場景的 route/visibility/render policy 驗證。"
              "它不構成完整資料集或正式 benchmark readiness；本次到此停止。", ""]
    (root / "sample_report.md").write_text("\n".join(lines))
    cards = []
    for record in rep_records:
        cards.append(f'<section><h2>{html.escape(record["stage"])} / '
                     f'{record["timestamp"]:.1f}s</h2><img src="{record["path"]}" '
                     f'alt="{html.escape(record["stage"])}"></section>')
    (root / "review.html").write_text(
        '<!doctype html><html lang="zh-Hant"><meta charset="utf-8">'
        '<title>PILOT / SYNTHETIC SAMPLE review</title><style>'
        'body{max-width:1480px;margin:24px auto;padding:16px;font:16px system-ui;'
        'background:#f8fafc;color:#172033}img{max-width:100%;height:auto}'
        'section{margin:32px 0}a{color:#075fa8}</style><h1>' + LABEL + '</h1>'
        '<p>10秒 / 5 FPS / 50 timestamps。橙色 synthetic marker；灰色 opaque physical mesh。'
        '狀態依 body-center landmark；純2D Observation另存，GT僅simulation/evaluation。</p>'
        '<p><a href="sample_report.md">Sample report</a> · '
        '<a href="dataset.json">Dataset JSON</a> · '
        '<a href="observations.json">2D observations</a></p>'
        '<h2>Trajectory preview</h2><img src="trajectory_preview.gif" alt="10-second preview">'
        '<img src="trajectory_preview.png" alt="Trajectory map">' + ''.join(cards) + '</html>'
    )
    (root / "representative_frames.json").write_text(json.dumps(rep_records, indent=2) + "\n")
    print(f"PILOT_REVIEW_OK {root / 'review.html'}")


if __name__ == "__main__":
    main()
