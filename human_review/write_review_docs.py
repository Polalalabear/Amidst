"""Render the four fixed pending questions and honest automatic continuation gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def lines(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [
            str(row) if isinstance(row, str) else json.dumps(row, ensure_ascii=False)
            for row in value
        ]
    return [json.dumps(value, ensure_ascii=False, indent=2)]


def append_bullets(parts: list[str], value: Any) -> None:
    parts.extend("- " + line for line in lines(value))
    parts.append("")


def main() -> None:
    document = json.loads((HERE / "decisions.json").read_text())
    parts = [
        "# Phase 1 最小人工審查",
        "",
        "狀態：**HUMAN_REVIEW_PENDING**；4 項決策全部未選擇。推薦值不等於核准。",
        "",
        "先開 [dashboard](index.html)，依 **HR-01 → HR-02 → HR-03 → HR-04** 審查。",
        "每項只有 APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW；APPROVE 選一個完整 profile。",
        "填審查者並匯出 `decisions.json`；下一輪提供這份檔案即可，無需另整理人工證據。",
        "直接編輯 JSON 時，只改 metadata 的 reviewer / submitted_at 與 item 的",
        "decision / selected_option。其他內容改動會被拒絕。",
        "",
        "[10 秒連續預覽 / 50 frames / 5 Hz](frames/player.html) 使用 Blender evaluated source、",
        "public 2D observations、projected points 與 inferred candidate hypotheses。",
        "OBSERVED → GAP → OBSERVED；GAP 中人物位置是候選路徑示範，**不是 GT 或觀測位置**。",
        "WALKABLE、PORTAL context、semantic OBSTACLE、body cylinder / clearance 都有獨立標示。",
        "Office 的 solid obstacle components 尚無 APPROVED，不能把紅色 footprint 當正式 collider。",
        "Camera still 是 bounded evaluated source snapshot，不證明完整 scene occlusion。",
        "",
        "只請核准 **1F office 的精確 body guard**；不審整棟、1,422 WALL patches、73 HC WALL、",
        "8 portal conflicts 或 Stair A/B。左路徑違反已核准 clearance，自動排除。",
        "既有圖片中的 face7356 東側牆只作位置 context，位於本次 body guard 之外，沒有另一項決策。",
        "",
        "| ID | Human-readable location/problem | Blocks | Recommended | Decision |",
        "|---|---|---|---|---|",
    ]
    for item in document["items"]:
        parts.append(
            f"| {item['id']} | {item['title']} | Case 1/2/3 | "
            f"APPROVE / {item['recommended_option']} | 未決定 |"
        )
    parts.extend(
        [
            "",
            "## Formal setting review",
            "",
            "下表只列 Case 1–3 必須固定的設定；已有 authority 或唯一 contract 的直接採用。",
            "沒有用 GT / accuracy 結果選容差，sampling 不丟棄困難 evidence。",
            "",
            "| Setting | Current status | Existing evidence | Recommended final value | Why |",
            "|---|---|---|---|---|",
            (
                "| Scale / body / clearance / contact | APPROVED；自動沿用 | approved scale "
                "+ physical policy | 0.0247 m/BU；r0.30 / h1.70 / clearance0.05 m；contac"
                "t0.001 m | 不重審已核准參數 |"
            ),
            (
                "| K / sampling / alignment | 自動採用 | user K + public 0.2 s grid + Metri"
                "cConfig | K1/2/3；5 Hz；完整 timestamp extent；"
                "piecewise linear | 既有支援且可自動推"
                "導 |"
            ),
            (
                "| Projection / reference | HR-02 | source calibration + approved floor"
                " + public endpoint pixels | exact-time multiview → single-view fixed p"
                "lane；exact marker→floor offset | 語意與 fallback 必須核准 |"
            ),
            (
                "| Coverage | HR-03 | protocol initial targets；現有 D=ADE | ADE < 0.50 m；"
                "另可選 <1.00 m | 研究者決定 error tolerance，跑前鎖定 |"
            ),
            (
                "| Speed / timing | HR-04 | existing 32 BU/s + ReconstructionPolicy | 0"
                ".7904 m/s；slack1 s；uniform + supported departure dwell | 明確核准既有運動模型 |"
            ),
            (
                "| Solver precision / uncertainty | 自動沿用 | existing numeric contracts /"
                " sidecar | 不改 solver；sigma 未聲明則 uncertainty UNAVAILABLE / LOW_CONFIDEN"
                "CE | 不能捏造 probability 或放寬 tolerance |"
            ),
            (
                "| Case / baseline definitions | 沿用 protocol；實例待自動 proof | PHASE1_BENCH"
                "MARK_PROTOCOL + A/B/C masks | unique / branching / long-GAP；既有 baselin"
                "es / ablations；Case4 DEFERRED | 不新增 benchmark 或調 threshold |"
            ),
            "",
            "## Case-specific blocker map",
            "",
        ]
    )
    for number, row in document["metadata"]["case_blocker_map"].items():
        parts.extend(
            [
                f"### Case {number}",
                "",
                "- Human blocker 數：4。",
                "- IDs：HR-01 / HR-02 / HR-03 / HR-04（共用項目只列一次）。",
                "- 全部 APPROVE 後可立即 formal run：**否；先完成下列自動認證**。",
            ]
        )
        append_bullets(parts, row["automatic_exit_checks"])
    parts.extend(
        [
            "## 決策後續",
            "",
            "[decision application pipeline](DECISION_APPLICATION.md) 已準備，可驗證完整決策、",
            "重新計算 bounded certificate 並輸出 hash-bound approved input lock。",
            "目前 formal authority adapters 與 Case inventory 仍須由 agent 完成自動工作；",
            "原 diagnostic context / parallel offset routes 不會因 APPROVE 直接變 FORMAL。",
            "之後依 [resume_plan.json](resume_plan.json) 的十個階段續作，只有真正新的 geometry",
            "矛盾或必要 case scope / binding 超出本次核准範圍才重開人工 gate。",
            "",
            "## 固定格式的四項問題",
            "",
        ]
    )
    labels = {
        "floor": "Floor",
        "area": "AREA",
        "portal": "PORTAL",
        "nearby_object": "nearby object",
        "outliner_search": "Blender Outliner 搜尋名稱",
    }
    for item in document["items"]:
        parts.extend([f"### {item['id']} — {item['title']}", "", "Location:", ""])
        for key, label in labels.items():
            parts.append(f"- {label}：" + " / ".join(lines(item["location"][key])))
        parts.extend(["", "Why it blocks:", ""])
        append_bullets(parts, item["why_it_blocks"])
        parts.extend(["Evidence:", ""])
        for image in item["evidence"]["images"]:
            parts.extend([f"![{image['caption']}]({image['path']})", "", image["caption"], ""])
        if item["evidence"].get("sequence"):
            parts.extend(["[10 秒 continuous preview / 逐 frame](frames/player.html)", ""])
        for key in (
            "objects",
            "faces",
            "bounds",
            "centroid",
            "measurements",
            "current_authority",
            "relevant_frames",
        ):
            value = item["evidence"].get(key, "N/A")
            parts.extend([f"{key}:", ""])
            if isinstance(value, dict) or (
                isinstance(value, list) and any(isinstance(v, dict) for v in value)
            ):
                parts.extend(
                    ["```json", json.dumps(value, ensure_ascii=False, indent=2), "```", ""]
                )
            else:
                append_bullets(parts, value)
        parts.extend(["Current machine conclusion:", "", "已確定：", ""])
        append_bullets(parts, item["machine_conclusion"]["known"])
        parts.extend(["尚不能確定：", ""])
        append_bullets(parts, item["machine_conclusion"]["unknown"])
        parts.extend(
            [
                "Recommended decision:",
                "",
                f"**APPROVE / {item['recommended_option']}**。",
                "",
                item["recommendation_reason"],
                "",
                "APPROVE 具體選項：",
                "",
            ]
        )
        for option in item["approve_options"]:
            parts.append(f"- `{option['id']}` — {option['label']}。{option.get('why', '')}")
        parts.extend(["", "Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。", ""])
    parts.extend(
        [
            "## Provenance / reproduction",
            "",
            (
                "- Branch：`phase1/finalization-sprint`；blocked checkpoint：`"
                f"{document['metadata']['checkpoint_sha']}`。"
            ),
            (
                f"- Source .blend SHA-256：`{document['metadata']['source_sha256']}`；"
                "source 未 save / modify。"
            ),
            f"- Immutable question payload SHA-256：`{document['review_payload_sha256']}`。",
            (
                "- [manifest.json](manifest.json)：本 package hashes；[frames/visual_manif"
                "est.json](frames/visual_manifest.json)：source/frames hashes。"
            ),
            (
                "- [geometry_evidence.json](geometry_evidence.json)、[settings_evidence."
                "json](settings_evidence.json)：source-bound measurements / calibration "
                "/ decisions basis。"
            ),
            "- 本輪沒有 formal Cases、GT-assisted decision、核准、main merge 或 freeze tag。",
            (
                "- [history/blocked_checkpoint](history/blocked_checkpoint/) 保存舊 generi"
                "c gate；舊 build_review.py 不再是本 dashboard 的 builder。"
            ),
            "",
            "重建 pending 審查文字 / dashboard：",
            "",
            "```sh",
            "uv run python human_review/assemble_review.py",
            "uv run python human_review/write_review_docs.py",
            "uv run python human_review/build_dashboard.py --decisions human_review/decisions.json",
            "```",
            "",
            "assemble_review 會拒絕覆寫任何已填決策。",
        ]
    )
    (HERE / "README.md").write_text("\n".join(parts) + "\n")


if __name__ == "__main__":
    main()
