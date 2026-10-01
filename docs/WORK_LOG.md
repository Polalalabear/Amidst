# Work log / 已完成工作紀錄

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

本文件保存已完成工作與當時驗證證據。即時待修項目見 [CODEX_HANDOFF](CODEX_HANDOFF.md)，持續適用的規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，實際能力契約見 [DATA_SCHEMA](DATA_SCHEMA.md)／[INTERFACES](INTERFACES.md)。下列內容從既有交接整理，不代表本次重新執行全部測試，也不代表正式 school benchmark 已完成。

### 2026-10-01 — M0–M4：環境、稽核與合成模擬

| 階段 | 已完成內容 | 主要 commit |
| --- | --- | --- |
| M0 | 文件、Git、uv project 與 Blender CLI 檢查；pyproject／uv.lock 初始化 | `3238ec7` |
| M1 | 唯讀 school_v2 scene audit、JSON／摘要、結構幾何補充分析、來源綁定與研究副本 | `ab8a9d9`、`c3638c5`、`7add28b` |
| M2 | 可設定時間路徑、確定性取樣、temporary target proxy 的 Blender world-position 求值、GT JSON／CSV 匯出 | `82fa2a3` |
| M3 | Camera schema、29 台相機的 pose／intrinsics 抽取、world→pixel、FOV／clip 與 Blender parity 檢查 | `251db8f` |
| M4 | evaluated Mesh point raycasts、OBSERVED／GAP 與拒絕原因、來源 SHA 綁定、GT-free 2D evidence 匯出 | `58a8099` |

同期完成單位／相機 convention 記錄 `c3a02c7`、暫時中性材質 override `52b2b6e`，以及將 school 樓梯不確定性限縮到 school 跨樓層配置的文件修正 `2e9dd29`。固定使用 29 台 `CAM_*`、1 unit = 1 metre 的採用決策留在 [ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)，此處只記錄完成事實。

稽核證據存於 [scene audit 摘要](../data/scene_audit/README.md)、[幾何補充](../data/scene_audit/GEOMETRY.md) 與對應 JSON：

- Inventory 為 2,796 objects（2,652 Mesh、30 Camera）、29 collections、260 materials、447 images、489 modifiers、12 actions；其中 imported SketchUp Camera lens 非有限，29 台 `CAM_*` 為研究候選。
- 18 個 imported lights、8 個高面數物件及可能多餘的材質／貼圖只報告，未清理。
- Geometry follow-up 分析 370 個結構 Mesh、25,098 triangles，辨識主要 floor candidates `z≈20.07885`／`161.811096`；庭院另有 `z≈0.000112` 候選。兩個樓梯 annotation regions 未找到 Mesh 支持的連續上升路徑。這不是全場 NavMesh、walkability 或樓梯不存在的證明。
- 研究副本 `blender/working/school_v2_research.blend` 與原檔 byte-identical，沒有 save／render；temporary neutral override 不更改來源 slots、UV、images。
- `configs/trajectory_fixture.json` 為 factory synthetic 設定：0／2／4 秒 keyframes、10 Hz、seed 42，取樣器可產生 41 筆；seed 只記錄，基準取樣器不使用隨機性。這不是 school route 或已保存的 dataset。

### 2026-10-01 — M5–M8：契約、反投影、導航與搜尋

| 階段 | 已完成內容 | Commit |
| --- | --- | --- |
| M5 | Observation、ProjectedPoint、CandidateTrajectory、Event、ReconstructionResult、provenance／termination、nullable Phase 2 欄位、serialization tests 與 protocols | `1dcce12` |
| M6 | 一台 Camera 綁定顯式 unit-normal Plane、ray-plane inverse projection、axial clipping、plane identity／incidence quality 與 typed geometry failures | `7e952ae` |
| M7 | Directed configured navigation 與 Camera Topology 分離、ordered edge cross-validation、node 定位、3D length 與 canonical minimum-distance routing；generic synthetic stair 契約／測試 | `94ee2cd` |
| M8 | Exact topology-authorized routes、continuous anchors、速度／時間／長度／detour 剪枝、bounded Top-K、corridor 去重、candidate identity、搜尋停止狀態與 synthetic major-flow integration | `d6620b4` |

M5 最初交接中的 completion 預設與空 Observation shell 契約問題已收尾；M8 另實作輸入拒絕檢查：

- `ReconstructionResult` 檢查 termination／complete 一致性，`NO_FEASIBLE_PATH` 不接受 candidates。
- 空 OBSERVED shell 可宣告區間，但不等於有效 Evidence；M8 拒絕沒有 PROJECTED endpoints 的輸入。

M8 檢查確認有效 K 採 method／policy 較小值；只在看到 K+1 個 distinct feasible corridors 時回 `MAX_PATHS_REACHED`。Node／branch／timeout 終止標為 incomplete；同 corridor 去重、不加入未授權 connector 或另選 shortcut。這些屬於當時實作驗證事實，完整契約留在 [INTERFACES](INTERFACES.md)。

### 2026-10-01 — 驗證與 Review 證據

| 當時內容／checkpoint | 執行結果 | 說明 |
| --- | --- | --- |
| M5 完整內容；記錄於 `1dcce12` | 106 passed in 23.82s，無 skipped／failed；Ruff、mypy 21 source files、diff check 通過 | 當時 M5 完成驗證，不是 M8 結果 |
| M8 完整內容；記錄於 `d6620b4`／`c04435f` | 219 passed in 25.73s，無 skipped／failed；Ruff、mypy 33 source files、diff check 通過 | 當時 M8 完成驗證 |
| Review 起點 `baf9074`；結果記錄於 `e27d1dd` | 219 passed in 25.02s，無 skipped／failed；Ruff、mypy 33 source files、diff check 通過 | 重新檢查 M5–M8，未修改程式 |

重跑使用 `uv run pytest`、`uv run ruff check .`、`uv run mypy`、`git diff --check`。在上述 review 另確認來源與研究副本 SHA-256 相同：

```text
1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38
```

當時 Blender CLI 為 `/Applications/Blender.app/Contents/MacOS/blender`，5.2.1 LTS，build `9e2066aef7ef`。Blender-backed tests 使用 transient factory fixtures；測試暫存輸出不是 repository 的正式 dataset，沒有產生 render。Blender adapters 使用標準函式庫與 lazy bpy／mathutils，未假設 Blender Python 與 uv 共用套件環境。

Review 的證據範圍：

- M7／M8 在 configured-route 契約內未發現新的可操作正確性問題，正常推論 imports／scoring 未發現 GT 讀取。
- Walkability／collision safety 來自受信任的顯式 route 設定，不是 Mesh 障礙／淨空檢查；`WALKABLE` flag 不證明 school collision rate = 0。
- M8 integration 為 synthetic camera／2D evidence→plane projection→configured graph，不是 school Blender trajectory→evaluation 的正式閉環。
- Projected endpoints 要對齊 configured nodes；沒有 arbitrary-point connector。Wall-clock timeout 結果可能因負載不同而改變，不等於所有 timeout outputs 可重現。
- Review 找到 M6 `project_frame()` 未重驗完整 ObservationFrame 的 provenance bypass：`model_copy` 產生非法 provenance 仍可被投影。當時僅記錄、未修程式；有效待修狀態在 [handoff](CODEX_HANDOFF.md)。這不是已確認的正常流程 GT 座標洩漏。
- Projection Error evaluation、M9 reconstruction、M10 metrics、M11 visualization、formal benchmark 均未在這些檢查中完成。

### 2026-10-01 — 資料盤點、發布與交接整理

- `74c66bd` 新增日期化 [data inventory](../data/README.md)。當時 Git 追蹤的是 audit bundle；唯一已物化 runtime artifact 為本機、ignored 的 29-camera catalog，GT／Observation／candidate／metric／`.rrd`／rendered-image dataset 均未物化。
- `baf9074` 記錄先前經明確授權的 GitHub 發布；`83ca3f8` 新增 project README。後續 review 沒有重新透過網路驗證 GitHub，不把本機 remote reference 當永遠有效的遠端狀態。
- `e27d1dd` 更新 M5–M8 review handoff，記錄使用者暫緩 school 樓梯／跨樓層／正式 Case 4、保留 generic synthetic tests；沒有修改程式、資產或 push。
- 本次以 `e27d1dd9494c921aa34027012e7b6e693dc6a5ba` 為文件整理起點，將歷史完成／驗證移至此紀錄、持續規則移至 DEVELOPMENT_RULES，精簡 CODEX_HANDOFF，並補文件導覽。沒有開始 M9、修補 M6、生成資料或渲染；本次僅做文件內容／連結／diff 檢查，不重跑上述歷史測試。
- 本次文件驗證：4 份雙語 Markdown、57 個本機連結與 fence／有效待修／暫緩狀態檢查通過；diff check 通過。歷史測試數字另以對應 commit 保存的 handoff 核對，不沿用未核實的快照。

## English

This is a dated completion/evidence log, not a live TODO list. [CODEX_HANDOFF](CODEX_HANDOFF.md) owns current unresolved work; [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md) owns durable rules; DATA_SCHEMA/INTERFACES own contracts. Historical results are not new test runs or formal benchmark acceptance.

On 2026-10-01, M0–M4 delivered uv/environment inspection, read-only scene/geometry audits and an identical research copy, deterministic Blender-evaluated Ground Truth export, 29-camera calibration/forward projection, and point visibility with sanitized 2D evidence. Main commits were `3238ec7`, `ab8a9d9`, `c3638c5`, `7add28b`, `82fa2a3`, `251db8f`, `58a8099`. Audit diagnostics identified floor candidates but did not certify school walkability or stairs; assets remained unchanged and no render was performed.

M5–M8 were independently committed as `1dcce12`, `7e952ae`, `94ee2cd`, `d6620b4`: strict domain/contracts, explicit-plane inverse projection, separate configured navigation/camera topology, and bounded topology-authorized Top-K search. M5 completion and empty-shell issues were resolved before commit. Exact route continuity, distinct-corridor K+1 truncation and incomplete search-limit reporting were reviewed.

Historical committed evidence: M5 `1dcce12` records 106 tests in 23.82s and mypy for 21 source files; M8 `d6620b4`/`c04435f` records 219 in 25.73s; a later review starting from `baf9074`, recorded in `e27d1dd`, passed 219 in 25.02s (no skips/failures), Ruff, strict mypy for 33 source files and diff checks. Source/copy hashes matched the digest above. These checks do not establish mesh collision/clearance, school navigation, Projection Error evaluation or a formal dataset/benchmark. The M6 schema-bypass finding was recorded, not fixed at that review.

`74c66bd` inventoried audit evidence and a local ignored camera catalog, with no materialized GT/observations/candidates/metrics/images. `baf9074` recorded an earlier authorized publication; `83ca3f8` added the README. `e27d1dd` recorded review results and the user's temporary school-stair deferral without code/asset/publishing changes. This documentation-only reorganization started from `e27d1dd`; it moves completed history here, durable rules to their own document and preserves actual open handoff items. Four bilingual Markdown files, 57 local links and state/fence/diff checks passed; historical counts were checked against their committed records, not rerun. No M9, M6 fix, data generation or rendering was started.
