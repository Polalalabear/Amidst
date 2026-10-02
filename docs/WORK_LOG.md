# Work log / 已完成工作紀錄

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

### 2026-10-02 — Phase 2 驗證與凍結

從 clean `b839254` 在隔離 `phase2/integration-foundation` 驗證；merge-base 仍為
`b11edb9`。139 個受保護 Phase 1 paths 的 blobs／modes 完全相同，Phase 2 commits
未進入 Phase 1 branches；沒有需要修改 Phase 1 contract 的問題。

只新增兩個回歸測試檔（18 cases）：七個 API route 的 schema/status 與 inclusive point
queries、atomic publication failure、nullable/empty/incomplete TypeScript contracts，
以及 GT／metrics 改變、重複 GET、replay/debug overlays 的 inference/storage isolation。
未修改 production source、既有 configs／fixtures／tests 或 Blender assets。

本輪重跑：既有 Phase 2 integration **14 passed in 3.11s**；Phase 2 unit
**102 passed in 3.11s**；新增兩檔 **18 passed in 4.42s**；完整 pytest
**668 passed in 46.64s，無 skipped／failed**。Ruff、strict mypy（80 source files）、
diff checks 通過；Node 26 執行 TypeScript runtime，既有 Blender tests 在獲准環境
執行，沒有 render／save assets。以上 targeted counts 已包含在 full count，不能相加。

標記 **PHASE2_INTEGRATION_FOUNDATION_VALIDATED**，以最後 validation commit 保存測試與
[凍結紀錄](PHASE2_INTEGRATION_VALIDATION.md)，同步 handoff。無本機 mock portability
blocker；跨 OS／filesystem／Node capability hardening 延後。完成後停止，建議回
Phase 1 Blender research closed loop；本輪沒有 push／PR／merge／history rewrite。

### 2026-10-02 — Phase 2 Integration Foundation

從 `codex/dataset-infrastructure` 的乾淨 checkpoint `b11edb9` 開始；建立前 Ruff、strict
mypy（69 files）與完整 pytest **547 passed**。Sandbox 內既有 Blender tests 出現18個
SIGSEGV，解除 sandbox 後完整重跑通過。驗證期間原 checkout 出現並行工作的 boundary
fixtures/tests；保留原 checkout，改在同一 commit 的乾淨隔離 worktree 再驗證 **547 passed**，
才建立使用者指定的 `phase2/integration-foundation`，沒有 stash／reset／rebase／rewrite。

| 功能 | Commit |
| --- | --- |
| Versioned backend API contracts／Protocol | `36fd908` |
| Snapshot repository abstraction、memory/local mock、PostgreSQL factory interface | `70ccbb9` |
| Lossless Python/TypeScript consumer、display-only replay | `f51bf55` |
| Mock service/provider wiring、config、read-only JSON/WSGI API、verified replay import | `6ff76db` |
| 完整 schema export、canonical URL-safe Event keys、ID/TypeScript parity regressions | `e2da4d8` |
| Provider→repository→API→consumer、既有 benchmark/replay 端到端覆蓋 | `899061f` |

`899061f` 完整程式內容的驗證：**650 passed in 44.53s，無 skipped／failed**；Phase 2 專用
integration **14 passed in 2.24s**、unit tests **89 passed**（在完整 pytest 中執行），Ruff
通過、strict mypy **80 source files** 通過。完整 pytest 包含既有 Blender-backed tests，
沒有 render／save assets。Python 仍由 uv 管理、lock/dependencies 不變；隔離 worktree 使用
原 installed environment，設定 `UV_PROJECT_ENVIRONMENT`／`PYTHONPATH` 指向正確的
environment／隔離 source，以及可寫 `/private/tmp/amidst-phase2-uv-cache`。完整 Blender
pytest 在獲准解除 sandbox 後執行；沒有將 sandbox SIGSEGV 記為產品測試成功。

四組既有 mock fixtures（single_path、branching_top_k、temporal_slack、simplified_stair）
驗證 canonical observations、完整 BoundGapEvent、candidate/hypothesis ordering、nullable
path_score、termination、complete、source/context binding；memory/local JSON adapter 可互換。
原 portable replay 搬移後重新執行原 benchmark，cases 與 metrics JSON 一致；服務／importer
不反序列化 evaluation GT。Node 26 實際執行 TypeScript，驗證四組 API consumer/replay JSON、
finite XYZ/time、provenance、invalid contracts 與 Python/TypeScript URL-key parity。

沒有需要修改 Phase 1 contract 的問題。保留 inclusive configured-time 與 provider window
reaggregation 的既有行為，透過 canonical snapshot 解決 Event ID joins。交叉審查修正了
Phase 2 schema map 漏列自身 response 與 WSGI route ID decoding；未變更任何 Phase 1 code、
benchmark logic、既有 fixture 或 Blender geometry。

新增 [雙語架構文件](PHASE2_INTEGRATION.md)，並同步 README 導覽與目前 handoff。
PostgreSQL／Three.js UI renderer／Real CV 等仍只在明確界線內保留 interface 或延後；
本輪沒有 production deployment、Semantic Ranking、push／PR／merge，也不 merge 回 Phase 1。

### 2026-10-01 — Deterministic fake-data 後半段閉環

起點 `2a988df`，branch `codex/deterministic-downstream-scenarios`；使用者授權四組
可替換的 fake scenarios，完成後停止，不進入完整 Agent Semantic Ranking。

| 功能 | Commit |
| --- | --- |
| 固定 seed 20261001 fixtures 與分離 GT／inference JSON | `ef1e1ca` |
| 通用 Graph pipeline、reachability／min time／不可能轉移／Top-K／termination tests | `93a6bee` |
| M6 完整 frame schema 重驗、防止 provenance bypass | `c3387a2` |
| Timed Event hypotheses、direct／slower／dwell／detour 與 temporal slack | `d7db5ca` |
| ADE／FDE／route Top-K Coverage／continuous AABB／speed／directed corridor metrics | `723bbbe` |
| Rerun adapter、所有候選／hypotheses／provenance／GT debug overlay 與1Hz播放 | `737010d` |
| 完整 runner、所有 configs 物化與 Ground Truth isolation integration | `6066c9e` |

`6066c9e` 完整程式內容的驗證：**347 passed in 26.14s，無 skipped／failed**；
Ruff 通過、strict mypy 46 source files 通過、diff check 通過。指令由 uv 管理，使用
`UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync`，沿用 locked installed
environment。Sandbox 內 uv online discovery 會觸發 macOS SystemConfiguration panic，
既有 Blender CLI tests 在 sandbox 內 SIGSEGV；完整 pytest 在獲准解除 sandbox 後通過。
沒有修改 dependencies／lock 或 render／save Blender assets。

四組實際閉環輸出在本機 ignored `data/candidates/fake_downstream_20261001/`：

| Scenario | Routes／hypotheses | Primary ADE（m） | minADE@K（m） | minFDE@K | Coverage@K |
| --- | --- | --- | --- | --- | --- |
| Single Path | 1／1 | 0 | 0 | 0 | true |
| Branching Top-K | 3／5 | 7.8021081352 | 2.7079e-17 | 0 | true |
| Temporal Slack | 2／4 | 0 | 0 | 0 | true |
| Simplified Stair | 1／1 | 0 | 0 | 0 | true |

全部 COMPLETE；synthetic wall AABB、directed corridor、max speed 的 collision／constraint
rate=0。Branching GT 是第三條，Coverage@1=false；ADE/FDE 已知 numeric oracle 為1／2。
Temporal Slack 最短時間20s、gap180s、slack160s，保留 slower movement、dwell、detour，
不賦予行為機率。四份實際 RRD 以 SDK RrdReader 重開，確認 footer/store 與 entity data 可讀。
18 個 Rerun tests 另驗證3個Top-K、GT debug labels、provenance與20秒路徑中點播放。

GT isolation integration **12 passed**：禁止真值檔案讀取仍能完成四組推論；改變GT只改變
evaluation，candidate／Event JSON 不變；拒絕 JSON 注入、forged provenance、candidate
truth／probability payload。另有8個M6 copy／construct frame bypass regression cases。
Source／research copy SHA-256 均仍為
`1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38`。

這是 configured synthetic interface regression，不是 school walkability／stair／Mesh collision
驗證、formal benchmark 或完整研究驗收。有效接入缺口留在 handoff；沒有 push／PR／merge。

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

### 2026-10-02 — Phase 2 validation and freeze

Validation started from clean `b839254` on the isolated Phase 2 branch. Merge-base remained
`b11edb9`; 139 protected Phase 1 blobs/modes were identical and Phase 2 commits stayed outside
Phase 1 branches. Only two new regression files (18 cases) and validation/handoff/log docs
were added, covering API/status, atomic failure, TypeScript preservation and GT/metrics/read
isolation. Full pytest: **668 passed in 46.64s, no skips/failures**; targeted integration 14,
unit 102 and new-file coverage 18 all passed (already included in the full total). Ruff, strict
mypy for 80 source files and diff checks passed; Node runtime and existing Blender tests ran.

**PHASE2_INTEGRATION_FOUNDATION_VALIDATED**. See the
[freeze record](PHASE2_INTEGRATION_VALIDATION.md) for scope and limitations. No local mock
portability blocker, Phase 1 contract change, production feature, asset save/render,
publication, merge or history rewrite occurred. Work stops here; returning to the separately
owned Phase 1 Blender research closed loop is recommended.

### 2026-10-02 — Phase 2 Integration Foundation

Starting checkpoint `b11edb9` was clean, with **547 pytest passed**, Ruff passed and strict mypy
passed across 69 files. Existing Blender subprocesses failed with sandbox SIGSEGV; the authorized
unsandboxed full run passed. Concurrent unrelated boundary files appeared in the original checkout,
so a clean isolated worktree at the same commit was independently verified before creating
`phase2/integration-foundation`. Original changes were preserved; no history rewrite or rebase occurred.

Implementation commits are listed in the Traditional Chinese table above. At code checkpoint
`899061f`, full pytest was **650 passed in 44.53s**, with no skips/failures; the new Phase 2 suite
included **14 integration** and **89 unit** tests. Ruff passed and strict mypy passed across
**80 source files**. Blender tests ran without rendering/saving assets. The locked existing uv
environment and isolated source path were selected explicitly; dependencies and lockfile were unchanged.

All four existing mock cases traverse providers, bound snapshots, memory/local storage, JSON API,
Python/TypeScript consumer contracts and display replay. Relocated portable replay runs the unchanged
benchmark with identical cases/metrics. Node 26 executed actual API consumer/replay JSON and rejected
corrupt contracts, preserving finite XYZ/time, provenance, alternatives and special Event identities.
Service/importer never deserialize evaluation truth.

No Phase 1 contract change was required. Canonical snapshots retain existing inclusive/window-query
behavior; additive API schema/routing defects found by peer review were fixed. Core Phase 1 code,
benchmark logic, existing fixtures and Blender geometry were untouched. Architecture/navigation/handoff
documentation now describes only the authorized mock foundation. No production deployment, Semantic
Ranking, push, PR or merge into Phase 1 occurred.

The 2026-10-01 fake-data round started at `2a988df` and completed the generic downstream
loop on `codex/deterministic-downstream-scenarios`, with implementation commits listed
above through `6066c9e`. Full validation passed 347 tests in 26.14s, no skips/failures,
Ruff, strict mypy for 46 source files and diff checks. uv used the installed locked
environment with offline/no-sync and a writable cache; existing Blender tests required
approved unsandboxed execution. No dependencies, source assets, render, semantic ranking
or publication changed.

All four fixtures generated real candidate/Event/metric/RRD outputs, totaling 7 routes
and 11 timing hypotheses. All terminated COMPLETE; minADE@K≈0, minFDE@K=0, Coverage@K=true,
and supplied-AABB/speed/corridor violations=0. Branching primary ADE=7.8021081352m and
Coverage@1=false, with true route retained at rank three. Temporal slack is160s for20s
minimum travel in180s. Four RRD files were reopened successfully; 18 visualization tests
include midpoint playback. Twelve GT isolation integration cases and eight new M6 bypass
cases passed. Blender source/copy hashes match the unchanged digest above. These are fake
interface results, not school mesh certification or a formal benchmark. Remaining
producer/scene/multiple-gap/benchmark interfaces are in CODEX_HANDOFF.

This is a dated completion/evidence log, not a live TODO list. [CODEX_HANDOFF](CODEX_HANDOFF.md) owns current unresolved work; [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md) owns durable rules; DATA_SCHEMA/INTERFACES own contracts. Historical results are not new test runs or formal benchmark acceptance.

On 2026-10-01, M0–M4 delivered uv/environment inspection, read-only scene/geometry audits and an identical research copy, deterministic Blender-evaluated Ground Truth export, 29-camera calibration/forward projection, and point visibility with sanitized 2D evidence. Main commits were `3238ec7`, `ab8a9d9`, `c3638c5`, `7add28b`, `82fa2a3`, `251db8f`, `58a8099`. Audit diagnostics identified floor candidates but did not certify school walkability or stairs; assets remained unchanged and no render was performed.

M5–M8 were independently committed as `1dcce12`, `7e952ae`, `94ee2cd`, `d6620b4`: strict domain/contracts, explicit-plane inverse projection, separate configured navigation/camera topology, and bounded topology-authorized Top-K search. M5 completion and empty-shell issues were resolved before commit. Exact route continuity, distinct-corridor K+1 truncation and incomplete search-limit reporting were reviewed.

Historical committed evidence: M5 `1dcce12` records 106 tests in 23.82s and mypy for 21 source files; M8 `d6620b4`/`c04435f` records 219 in 25.73s; a later review starting from `baf9074`, recorded in `e27d1dd`, passed 219 in 25.02s (no skips/failures), Ruff, strict mypy for 33 source files and diff checks. Source/copy hashes matched the digest above. These checks do not establish mesh collision/clearance, school navigation, Projection Error evaluation or a formal dataset/benchmark. The M6 schema-bypass finding was recorded, not fixed at that review.

`74c66bd` inventoried audit evidence and a local ignored camera catalog, with no materialized GT/observations/candidates/metrics/images. `baf9074` recorded an earlier authorized publication; `83ca3f8` added the README. `e27d1dd` recorded review results and the user's temporary school-stair deferral without code/asset/publishing changes. This documentation-only reorganization started from `e27d1dd`; it moves completed history here, durable rules to their own document and preserves actual open handoff items. Four bilingual Markdown files, 57 local links and state/fence/diff checks passed; historical counts were checked against their committed records, not rerun. No M9, M6 fix, data generation or rendering was started.
