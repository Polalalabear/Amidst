"""Render validated human-review state and honest automatic continuation gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from apply_decisions import validate_decisions

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
    template = json.loads((HERE / "review_template.json").read_text())
    state = validate_decisions(document, template)
    ready = state["status"] == "EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION"
    unresolved = set(state["pending"]) | {row["id"] for row in state["blocking"]}
    approved = [item for item in document["items"] if item["decision"] == "APPROVE"]
    selected = {
        item["id"]: next(
            profile
            for profile in item["approve_options"]
            if profile["id"] == item["selected_option"]
        )
        for item in approved
    }
    current_status = (
        f"狀態：**{state['status']}**；{len(approved)} 項人類核准已記錄，"
        "人工未決項目 0；尚未 apply、產生 certificate 或執行 formal Case。"
        if ready
        else f"狀態：**{state['status']}**；人工未決／阻擋項目 {len(unresolved)}。"
        "推薦值不等於核准。"
    )
    parts = [
        "# Phase 1 最小人工審查",
        "",
        current_status,
        "",
        "## HR02 相機／落點核對補充",
        "",
        "先看 [HR02 camera audit](frames/hr02_camera_audit/view.html) 與",
        "[核對結果／重現方式](HR02_CAMERA_AUDIT.md)。兩台 source cameras 在數值上位於",
        "`AREA_1F_AUDITORIUM` AABB、OFFICE AABB 之外；物件名稱／外框不能核准 room ownership。",
        "50 timestamps × 2 cameras：原 public 記錄 26 OBSERVED／74 GAP；回推 landmark 射線",
        "26 CLEAR／74 OCCLUDED，候選腳底 10 CLEAR／90 OCCLUDED；16 筆 landmark 通視但腳底被擋。",
        "**1.35973495 m 是待核准 landmark→floor 偏移，不是地板到天花板高度。**",
        "人工只確認目標房間／鏡頭是否正確，以及追蹤點是固定身體 landmark 還是腳底。",
        "fallback 沿用既有 protocol，不新增研究設定問題；原四項 decision 全部保持 null。",
        "人物是 public projection／GAP candidate，不是原始3D軌跡；沒有使用 GT。wide／side",
        "是 display-only cutaway，射線使用完整 allowed source mesh；20／25／45 是獨立代表",
        "camera still，不代表當前連續影格或 CV pixel certification。矛盾未釐清時維持 KEEP_REVIEW。",
        "",
        "新增審查辨識補充：空間導覽第 2 步提供完整測試空間與相機定位，第 3 步保持 FRONT／REAR",
        "位置對照，第 5 步與 HR-02 問題區加入實際 source 空間中的示意人物及腳底／landmark 高度。",
        "[獨立補充來源](frames/review_clarity/manifest.json)；舊圖、舊動畫及四項決策全部保留。",
        "**HR-02 的 1.3597 m 是 projected landmark 到候選腳底的垂直偏移，不是地板到天花板。**",
        "目前 landmark Z=75.12885 BU，approved support Z=20.07885 BU；相減 55.05 BU，",
        "以已核准 0.0247 m/BU 換算。人物高 1.70 m、半徑 0.30 m、clearance 0.05 m；",
        "人物落點／語意仍待 HR-02，姿勢沿用 display-only 示意，沒有使用 GT。",
        "",
        "Source issue 圖例（原近看圖）：",
        "",
        "| 外觀 | 意義 |",
        "| --- | --- |",
        "| 藍色大立體方框 | HR-01 待審 body guard：限定人體占用的審查範圍，並非實體牆 |",
        "| 白色小長方框 | 候選腳底可落點的限定 domain，並非模型物件 |",
        "| 橘色圓柱 | 人體尺寸包絡，半徑 0.30 m／高 1.70 m；位置為候選示意 |",
        "| 淡黃色外圓柱 | clearance 包絡，半徑 0.35 m／高 1.75 m |",
        "| 紫色線／點 | group_0 faces 1975／2398 的同一零面積 floor seam；顯示抬高 1.4 BU |",
        "| 藍色點 | public projected landmark；尚未核准為人物腳底 |",
        "| 黃橘／紅色折線 | 既有 direct／right 候選及自動 floor-clearance 拒絕的 left 路徑 |",
        "| 綠色面／灰色線框 | approved source floor support／來源模型定位 context |",
        "",
        "較遠的一樓圖橘框是 AREA_1F_OFFICE annotation context；紫色小框是同一待審 body guard。",
        "不同圖的圖例以該圖標示為準。相機位置導線不是 FOV：逐時可見性由既有 public evidence 顯示，",
        "FRONT 可見至 t=4.0 s，REAR 在 t=9.0 s 恢復；採樣 t=4.2–8.8 s 兩者均無可用觀測。",
        "這是既有 evidence 的 GAP，不能僅由位置圖推斷整個模型的遮蔽情況。",
        "",
        "在已物化原 29 frozen inputs 與舊審查媒體的 fresh checkout，重建辨識補充：",
        "",
        "```sh",
        "/Applications/Blender.app/Contents/MacOS/Blender \\",
        "  --background --threads 2 --factory-startup --disable-autoexec "
        "/absolute/path/to/school_v3.blend \\",
        '  --python-exit-code 2 --python "$PWD/human_review/render_review_clarity.py" '
        "-- --frames 25",
        "uv run python human_review/build_spatial_guide.py \\",
        "  --clarity-manifest human_review/frames/review_clarity/manifest.json",
        "uv run python human_review/build_dashboard.py \\",
        "  --clarity-manifest human_review/frames/review_clarity/manifest.json",
        "uv run python human_review/finalize_package.py",
        "```",
        "",
        "Renderer 拒絕覆寫 PNG／manifest；可用 `--output /fresh/path` 另存診斷 render。",
        "上列 HTML builder 固定讀 canonical supplement，以 hash 驗證後才嵌入。",
        "",
        "審查入口統一為 [原有 dashboard](index.html)。在「共同視覺審查工作區」同頁切換空間定位、",
        "10 秒行走動畫與模型＋拓樸；再依 **HR-01 → HR-02 → HR-03 → HR-04** 開啟決策。",
        "HR-01／HR-02 的 Evidence 也整合相同播放器與各自檢驗重點，先看動作和拓樸，再看",
        "接縫／marker-floor 近圖。原有連續預覽保留於可展開區域，完整獨立頁仍可另開。",
        "切換或關閉觀看區會卸載舊播放器；四項問題、profiles、研究設定與草稿識別都保持不變。",
        "在 repo root 重建補充介面請使用上列 `--clarity-manifest`；不帶此選項只嵌入原證據。",
        "更新 package hashes：`uv run python human_review/finalize_package.py`。",
        "",
        "新增：[模型與拓樸對照](frames/topology_context/view.html)；模型與旁邊空白區使用相同",
        "N1／N2、E1–E3 標號，保留 10 秒逐格播放。實心點是 2 個 graph nodes，空心點是",
        "4 個 polyline vertices，三條 directed edges 完整保留。N1 是 FRONT t=4s GAP 前端點，",
        "N2 是 REAR t=9s recovery；E1 direct、E2 left、E3 right。",
        "模型可切換 raw landmark 高度與 pending HR-02 floor footprint；顯示換算不改 raw graph。",
        "**固定 graph 與移動人物分開看：**N1／N2 與四個 vertex 是固定空間位置；P(t) 是",
        "隨影格同步移動的 DISPLAY_ONLY 人物標記，不是新增 graph node。模型腳底圈與右圖",
        "人物使用同一個 frozen frame，並顯示目前 N1／E1／N2 或 GAP graph 範圍外。",
        "t=4s 對應 N1；4.2–8.8s 是既有 inferred E1 candidate；t=9s 對應 N2。",
        "人物在 edge 中間沒有『目前 node』，會顯示 E1、N1→N2 及進度。圖外可見片段",
        "仍顯示實際位置，不吸附到端點。Node association 用原 public double 座標與既有",
        "1e-6m tolerance；模型游標沿用 render float32 座標，未放寬門檻或挪動人物。",
        "Dashboard iframe 以驗證過的 topology view SHA256 固定版本；草稿識別與四項問題不變。",
        "E2 的 floor-review clearance 自動拒絕與 graph pruning 分開記錄。",
        "[靜態對照圖](frames/topology_context/topology_preview.png) 與",
        "[獨立 manifest](frames/topology_context/topology_manifest.json) 保存精確座標及來源。",
        "在具備原 29 frozen inputs、既有 diagnostics 與 135 PNG／GIF 的 fresh checkout 重建：",
        "",
        "```sh",
        "uv run python human_review/build_topology_view.py",
        "uv run python human_review/render_topology_preview.py",
        "uv run python human_review/build_motion_player.py \\",
        "  --gif-provenance human_review/frames/motion_context/gif_manifest.json \\",
        "  --topology-view human_review/frames/topology_context/view.html",
        "uv run python human_review/build_topology_view.py",
        "```",
        "",
        "原有預覽與四項決策保留；這是既有 CONFIGURED / DIAGNOSTIC 圖，不證明 formal branching。",
        "",
        "2026-10-07 另增：[10 秒模型人物行走](frames/motion_context/player.html)，",
        "可播放、暫停、逐格查看；另有 [GIF 動作預覽](frames/motion_context/motion_preview.gif)。",
        "鏡頭固定，簡化人物在實際 evaluated office 來源模型中移動，包含 body / clearance、",
        "投影點、floor support、待審 body guard 與 OBSERVED → GAP → OBSERVED。",
        "50 frames /5 Hz 的位置、時間與 projection provenance 完全沿用原預覽；",
        "GAP 是既有候選假設，肢體姿態是 DISPLAY_ONLY 示意，不是 measured motion capture。",
        "原有導覽、鏡頭接近動畫、預覽與 85 張圖全部保留；沒有新增路徑或核准 authority。",
        "新段落的獨立來源紀錄：[motion manifest](frames/motion_context/motion_manifest.json)。",
        "",
        "在保有原 29 frozen inputs 與 85 舊圖的 fresh checkout 中，可重建新增段落：",
        "",
        "```sh",
        "/Applications/Blender.app/Contents/MacOS/Blender \\",
        "  --background --threads 2 --factory-startup --disable-autoexec "
        "/absolute/path/to/school_v3.blend \\",
        '  --python-exit-code 2 --python "$PWD/human_review/render_motion_context.py" '
        "-- --frames 50 --width 960",
        "uv run python human_review/make_motion_gif.py",
        "uv run python human_review/build_motion_player.py \\",
        "  --gif-provenance human_review/frames/motion_context/gif_manifest.json",
        "```",
        "",
        "輸出必須是新位置；不覆寫既有 PNG /GIF。GIF 是獨立縮圖版本，完整圖與逐格來源在播放器中。",
        "",
        "2026-10-07 補充：[先看完整空間導覽](frames/spatial_context/guide.html)。",
        "依序看整體 school 中的 office 位置、一樓與 camera 位置、鏡頭推進、原有 10 秒移動，",
        "最後看 HR-01 接縫 / body guard 與 HR-02 landmark→floor 對照。",
        "鏡頭推進只改變觀看位置；人物仍是既有 office 約 3.87 m 的投影 / 候選移動，",
        "沒有增加跨房間路徑或已核准物理範圍。原四項決策、問題 hash 與原 57 張 evidence 保留。",
        "一樓來源座標圖補足 camera 定位；相對位置與 camera 原生高度不構成 FOV 或 binding 證明。",
        "新增 3 張 source context still 與 25 張鏡頭 frame 的獨立 manifest：",
        "[spatial context](frames/spatial_context/spatial_context_manifest.json)。",
        "",
        "重建 HTML：`uv run python human_review/build_spatial_guide.py`。",
        "重現已保存的 Blender 圖片時，在已物化原 frozen inputs 的 **fresh checkout** 中先",
        "`cp human_review/history/spatial_context_initial_renderer.py "
        "human_review/render_spatial_context.py`，",
        "再執行原 renderer 的 Blender command（`--frames 25`）；不能直接執行 history 路徑，",
        "因為 producer 從 script 位置取得 repo root。該 archive 的 SHA 為 `8a5d52f4...305cd92`。",
        "目前 renderer 含改進構圖與預讀 hash 檢查，但因本機空間不足未成功重繪；",
        "保存圖片的 producer 與未 render 的改進版在獨立 manifest 中分別記錄。",
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
        decision = item["decision"] or "未決定"
        if item["selected_option"] is not None:
            decision += " / " + item["selected_option"]
        parts.append(
            f"| {item['id']} | {item['title']} | Case 1/2/3 | "
            f"APPROVE / {item['recommended_option']} | {decision} |"
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
                "lane；exact marker→floor offset | HR-02 確認房間／marker 語意；"
                "fallback 沿用 protocol |"
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
        ids = [item_id for item_id in row["blocker_ids"] if item_id in unresolved]
        parts.extend(
            [
                f"### Case {number}",
                "",
                f"- 目前 Human blocker 數：{len(ids)}。",
                "- 目前 IDs：" + (" / ".join(ids) if ids else "無") + "。",
                "- 原 checkpoint 共用審查項目：" + " / ".join(row["blocker_ids"]) + "。",
                "- 可立即 formal run：**否；先完成下列自動認證**。",
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
            "## 固定格式的四項問題" + ("（核准前凍結證據）" if ready else ""),
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
        parts.extend(
            [
                "Current machine conclusion:"
                + ("（核准前歷史結論，不是目前人工未決事項）" if ready else ""),
                "",
                "已確定：",
                "",
            ]
        )
        append_bullets(parts, item["machine_conclusion"]["known"])
        parts.extend(["核准前尚不能確定：" if ready else "尚不能確定：", ""])
        append_bullets(parts, item["machine_conclusion"]["unknown"])
        parts.extend(
            [
                "Recommended decision:" + ("（核准前建議）" if ready else ""),
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
        if ready:
            parts.extend(
                [
                    "",
                    f"已記錄人類決策：**{item['decision']} / {item['selected_option']}**。",
                    "",
                ]
            )
        else:
            parts.extend(
                ["", "Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。", ""]
            )
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
            "- 本輪記錄人類核准；未 apply／產生 certificate／執行 formal Cases，"
            "未使用 GT，未 merge 或 freeze。"
            if ready
            else "- 本輪沒有 formal Cases、GT-assisted decision、核准、main merge 或 freeze tag。",
            (
                "- [history/blocked_checkpoint](history/blocked_checkpoint/) 保存舊 generi"
                "c gate；舊 build_review.py 不再是本 dashboard 的 builder。"
            ),
            "",
            "重建目前審查狀態文字 / dashboard：",
            "",
            "```sh",
            "# 已填決策時不要重新 assemble；保留 immutable questions/profile。"
            if ready
            else "uv run python human_review/assemble_review.py",
            "uv run python human_review/write_review_docs.py",
            "uv run python human_review/build_dashboard.py --decisions human_review/decisions.json",
            "```",
            "",
            "assemble_review 會拒絕覆寫任何已填決策。",
        ]
    )
    if ready:
        summary = [
            "## 已記錄的人類核准",
            "",
            "[decisions.json](decisions.json) 保存四項 APPROVE 與完整 selected profile；",
            "[approval_record.json](approval_record.json) 保存明確授權及範圍，"
            "未將口頭核准當成已執行物理認證。",
            "",
            "| ID | Decision | Selected profile |",
            "|---|---|---|",
        ]
        summary.extend(
            f"| {item['id']} | APPROVE | `{item['selected_option']}` |" for item in approved
        )
        summary.extend(
            [
                "",
                "HR-01 的局部 source-surface 語意、HR-02 的目標房間／兩台 source cameras 與",
                "landmark→floor 語意已依 selected profile 核准；"
                "尚未將 profile apply 到 inference。",
                "physical certificate **NOT_RUN**，fresh observations 與自動 scope／visibility "
                "檢查仍必須完成。",
                "**human_decisions_recorded=true；human_decisions_applied=false；formal_execution_enabled=false。**",
                "",
                "下列舊影像保留產生時的待審標籤；固定 questions、machine conclusion 與",
                "historical evidence 不因核准而改寫，也不再要求第二輪人工資料整理。",
                "",
            ]
        )
        parts[4:4] = summary
        replacements = dict(
            [
                (
                    "**1.35973495 m 是待核准 landmark→floor 偏移，不是地板到天花板高度。**",
                    "**1.35973495 m 是歷史 landmark→floor 偏移；HR-02 selected profile 已核准，"
                    "不是地板到天花板高度；自動驗證仍待執行。**",
                ),
                (
                    "人工只確認目標房間／鏡頭是否正確，以及追蹤點是固定身體 landmark 還是腳底。",
                    "人類已確認目標房間／鏡頭綁定，以及 selected profile 的追蹤點語意。",
                ),
                (
                    "fallback 沿用既有 protocol，不新增研究設定問題；"
                    "原四項 decision 全部保持 null。",
                    "fallback 沿用既有 protocol；四項 APPROVE 已記錄，不新增研究設定問題。",
                ),
                (
                    "camera still，不代表當前連續影格或 CV pixel certification。"
                    "矛盾未釐清時維持 KEEP_REVIEW。",
                    "camera still，不代表當前連續影格或 CV pixel certification；"
                    "新的實際 geometry contradiction 才重開人工 gate。",
                ),
                (
                    "人物落點／語意仍待 HR-02，姿勢沿用 display-only 示意，沒有使用 GT。",
                    "HR-02 語意已核准；落點／物理認證待自動檢查，"
                    "姿勢仍為 display-only，未使用 GT。",
                ),
                (
                    "先開 [dashboard](index.html)，依 **HR-01 → HR-02 → HR-03 → HR-04** 審查。",
                    "[dashboard](index.html) 顯示已記錄四項核准，不需要重填人工決策。",
                ),
                (
                    "每項只有 APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW；"
                    "APPROVE 選一個完整 profile。",
                    "既有四選項及完整 profiles 保留供 provenance 查核，selected profiles 已固定。",
                ),
                (
                    "填審查者並匯出 `decisions.json`；下一輪提供這份檔案即可，無需另整理人工證據。",
                    "審查者及 signed-off time 已記錄；下一輪直接驗證決策並續做自動認證。",
                ),
                (
                    "只請核准 **1F office 的精確 body guard**；"
                    "不審整棟、1,422 WALL patches、73 HC WALL、",
                    "核准只涵蓋 **1F office 的精確 body guard**；不擴大到整棟、"
                    "1,422 WALL patches、73 HC WALL、",
                ),
            ]
        )
        parts = [replacements.get(part, part) for part in parts]
        for index, part in enumerate(parts):
            if part.startswith("| Projection / reference |"):
                parts[index] = (
                    "| Projection / reference | HUMAN_APPROVED；自動驗證待執行 | "
                    "source calibration "
                    "+ approved floor + public pixels + HR-02 | exact-time multiview → single-view "
                    f"fixed plane；{selected['HR-02']['id']} | "
                    "房間／camera／marker 語意已核准；fresh observations 必須重建 |"
                )
            elif part.startswith("| Coverage |"):
                parts[index] = (
                    "| Coverage | HUMAN_APPROVED；formal config 待鎖定 | HR-03 explicit profile | "
                    f"D=ADE；ADE < {selected['HR-03']['payload']['epsilon_m']:.2f} m | "
                    "人類已選既有容差，不以 accuracy 調 threshold |"
                )
            elif part.startswith("| Speed / timing |"):
                parts[index] = (
                    "| Speed / timing | HUMAN_APPROVED；formal config 待鎖定 | "
                    "HR-04 explicit profile | "
                    f"{selected['HR-04']['label']} | 人類已核准既有運動模型 |"
                )
    (HERE / "README.md").write_text("\n".join(parts) + "\n")


if __name__ == "__main__":
    main()
