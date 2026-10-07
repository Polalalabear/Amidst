# HR02 相機／人物落點核對

2026-10-07 更新：房間／鏡頭綁定與 `SOURCE_BOUND_RIGID_LANDMARK_OFFSET` 已由使用者明示核准，
見 [已記錄批准](APPROVALS.md)。下文與圖像保留核准前的診斷狀態；physical certificate 尚未重算。

狀態：**DIAGNOSTIC / NOT_CERTIFIED / KEEP_REVIEW 建議**。這份補充沒有填寫決策；原 HR-01–04 的 decision 均為 null。

先開 [相機核對頁](frames/hr02_camera_audit/view.html)，連續回放核對位置與射線，再看 frame 20／25／45 的兩台 source-camera 代表 still。still 的時間與連續回放分開標示。

## 已核對的事實

| 項目 | 機器核對結果 | 證據的限制 |
| --- | --- | --- |
| FRONT／REAR | 原 source 位置、旋轉與校準一致；兩台 camera 的點落在 `AREA_1F_AUDITORIUM` AABB，均在 `AREA_1F_OFFICE` AABB 之外 | AABB 是數值外框。名稱／containment 不能核准房間語意或可見域；room ownership 仍 NOT_CERTIFIED |
| 原 public visibility | 50 timestamps × 2 cameras，共 26 OBSERVED／74 GAP | 只有既有 2D landmark 紀錄；沒有讀取原始 3D 點 |
| 回推 landmark 射線 | 26 CLEAR／74 OCCLUDED；原 OBSERVED 與 replay 的不一致為 0 | 只證明這套 public projection／GAP candidate 在 source raycast 下相容，不證明原始真實人物位置 |
| 候選腳底射線 | 10 CLEAR／90 OCCLUDED；16 筆 landmark CLEAR 但腳底 OCCLUDED | FRONT 0.4–2.4 s 共 11 筆，REAR 9.0–9.8 s 共 5 筆。不能把 landmark 的 visibility 套用到腳底 |
| 像素位置 | landmark 改成候選腳底，影像位置移動 48.14–60.33 px | 原 landmark 的 2D observation 不能直接當腳底 observation |
| 高度提案 | landmark Z=75.1288478851 BU；support floor Z=20.0788497925 BU；差 55.0499980927 BU，即 **1.3597349529 m** | 這是待核准的 landmark→floor 偏移，**不是地板到天花板高度** |

換算沿用 APPROVED `1 BU = 0.0247 m`；display body 沿用高 1.70 m、半徑 0.30 m、clearance 0.05 m。數值不是本輪新增研究選項，人物／腳底 binding 仍 `PENDING_HR02`。

## 人工只確認兩件語意

1. **房間／鏡頭對象是否正確**：黃色 OFFICE annotation 是否是你指定的真實教室；這兩台 source cameras 是否就是觀察該教室的鏡頭。你的條件「只在該教室被兩台鏡頭看到」仍需要對照 source 空間。不能靠物件名字認定 ownership，也不能用核准高度偏移修復錯誤的房間／鏡頭 binding。
2. **追蹤點代表什麼**：人物身上的固定 landmark，或腳底。若應追蹤腳底，現有非零偏移及 landmark 像素不能直接當作合法腳底綁定。

camera 座標、FOV、最近遮擋 object／evaluated face、BU／meter 值與射線結果都由機器產生，不交給人估算。Evaluated face index 是本次求交網格的 ID，不等於已完成原 Blender polygon binding。

決策仍只有 **APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**，在 [原 dashboard](index.html) 的 HR02 填寫。本補充不新增 decision、approval profile 或 threshold；fallback 沿用已存在的 projection protocol。房間／marker 語意矛盾未釐清時維持 KEEP_REVIEW，推薦值不等於核准。

## 圖像與 authority 邊界

- 50 張行走影格保持原樣；人物來自 public projection，GAP 段來自既有 candidate。不是原始3D人物軌跡，也不是 motion capture。
- wide／side 在 Z=145 BU 切頂，屬 `DISPLAY_ONLY_CUTAWAY` 導覽。可見性射線另使用完整 allowed evaluated VIEWPORT source meshes，不採裁切後的導覽底圖。
- source-camera still 使用原校準，輸出 1920×1080；原 960×540 像素座標明確乘 2。兩台各有 frame 20／25／45，即 4.0／5.0／9.0 s。
- still 是灰模診斷 render，沒有 CV pixel visibility certification。診斷 overlay 的點可能在牆後；圖上出現點，不等於 camera 看到了它。
- 本輪未讀 GT、evaluation 或 simulation recipe，未修改／儲存原 `.blend`，未變動 graph、projection、camera pose、physical authority 或研究設定，未執行 formal Cases。

## 來源

[audit_data.json](frames/hr02_camera_audit/audit_data.json) 與 [producer manifest](frames/hr02_camera_audit/manifest.json) 保存 100 組 camera／timestamp 記錄、完整 source ray hit 與自動量測。原 audit JSON 保持不變；HTML builder 只在記憶體補入 [renderer manifest](frames/hr02_camera_audit/renderer_manifest.json) 的 8 張新圖，再生成 [view manifest](frames/hr02_camera_audit/view_manifest.json)。

Source SHA-256：`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`。Source scene 固定 `Scene / frame 220 / subframe 0`。Immutable question payload：`e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463`。

完整來源快照包含 2,576 個 allowed mesh instances、5,585,184 triangles。在 depsgraph iterator 前進或建立導覽物件之前保存每個 live instance 的幾何；包含轉為 mesh 的 FONT 與 hidden prototypes。完整 name／matrix 清單須與原 raycaster 相同，不略過失效物件。

最初 8 張圖、view、receipt 與精確 producer 留在 `history/hr02_initial_camera_render/`、`history/hr02_initial_camera_renderer.py`。新的 wide／side 底圖不烘入固定影格人物或射線，只有一組同步 overlay。修正來源快照後，6 張 camera still 的圖像 hashes 也改變；[render verification](frames/hr02_camera_audit/render_verification.json) 如實記錄，沒有宣稱兩個不同 renderer producer 的像素結果相同。新图仍是 DIAGNOSTIC，不替代原 public visibility 或正式證據。

凍結 query producer 在 fresh process／output 重跑後，audit JSON 與 producer receipt 的 bytes／hashes 完全一致，見 [final repeat verification](frames/hr02_camera_audit/final_repeat_verification.json)。這是診斷射線的重現，並非 formal benchmark fresh rerun。

## Fresh output 重現

在 repo root、已物化原 frozen public inputs／既有 motion evidence 的 checkout 執行。使用相同 source hash、當前 producer source 與既有 4-question payload。新輸出位置必須沒有既有 audit JSON、PNG 或 renderer receipt；producer 拒絕覆寫。

```sh
HR02_BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
HR02_SOURCE=/absolute/path/to/school_v3.blend
HR02_QUERY_OUTPUT=$(mktemp -d /private/tmp/amidst-hr02-query.XXXXXX)
HR02_RENDER_OUTPUT=$(mktemp -d /private/tmp/amidst-hr02-render.XXXXXX)

"$HR02_BLENDER_BIN" --background --threads 2 --factory-startup --disable-autoexec \
  "$HR02_SOURCE" --python-exit-code 2 \
  --python "$PWD/human_review/inspect_hr02_camera_binding.py" -- \
  --output "$HR02_QUERY_OUTPUT"

uv run python - "$HR02_QUERY_OUTPUT" <<'PY'
import hashlib
import sys
from pathlib import Path

canonical = Path("human_review/frames/hr02_camera_audit")
fresh = Path(sys.argv[1])
for name in ("audit_data.json", "manifest.json"):
    expected = hashlib.sha256((canonical / name).read_bytes()).hexdigest()
    actual = hashlib.sha256((fresh / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit("STOP: fresh source audit differs: " + name)
print("Fresh query matches canonical audit and receipt")
PY

"$HR02_BLENDER_BIN" --background --threads 2 --factory-startup --disable-autoexec \
  "$HR02_SOURCE" --python-exit-code 2 \
  --python "$PWD/human_review/render_hr02_camera_audit.py" -- \
  --output "$HR02_RENDER_OUTPUT"
```

Renderer 固定讀 hash-bound canonical audit／producer receipt；上面的 fresh query 必須先與它們一致。新 render directory 保存 8 張圖片與 renderer receipt；核對 source flags、camera calibration、input hashes 與每張圖片 hash。既有檔案全部保留，不以 fresh 診斷產物取代 formal evidence。

需要更新 canonical 圖片時，先封存舊 8 PNG／renderer receipt／view 與 view receipt，保留原 audit JSON／producer receipt。再把經驗證的新 render 產物發布到 canonical folder，並重新生成相關 HTML／package hashes：

```sh
uv run python human_review/build_hr02_camera_review.py
uv run python human_review/write_review_docs.py
uv run python human_review/build_dashboard.py \
  --clarity-manifest human_review/frames/review_clarity/manifest.json
uv run python human_review/finalize_package.py
```

此流程只重建人工審查診斷補充；不 apply decisions、不開始 formal Case 1–3、不建立 freeze tag。
