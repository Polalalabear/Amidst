# Agent 檢索定位與資料邊界 / Agent retrieval role and data boundary

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

### 目前範圍與實作狀態

本文件依 2026-10-08 的使用者指示整理後續工程契約，狀態為 **PLANNED / SYNTHETIC_MOCK_ONLY**，不是已完成的服務。本階段不串接 OpenAI 或其他外部模型 API，不送出照片、摘要或模型原始資料；不建立 live provider、SDK 接線或秘密配置。API 接線與大幅減少 token 的兜底演算法尚未正式，文末只保留空章節。

依據：[架構責任](../specs/SYSTEM_DESIGN.md#11-agent-arbitration-layer)、[摘要與 context](../specs/SYSTEM_DESIGN.md#29-token-and-context-control)、[資料契約](../specs/DATA_SCHEMA.md)。工程基底 `4271b2b` 已接入 [Phase 2 mock API/repository/replay](PHASE2_INTEGRATION.md)，但低階 mock 契約尚非 Agent allowlist DTO，新 reviewed/finalization package 的 normalization／匯入認證仍待完成；原 frozen branch/tag 不變。

影像 producer 從未加 GT 標註的 RGB pixels 量測，不讀 simulator object-index／segmentation／depth、GT bbox／身分／位置或 recipe/reference annotations。合成照片經影像演算法處理仍屬 SYNTHETIC 來源，另外保留量測 producer／版本／輸入 hashes；既有模擬 UV 不改稱影像量測。Local tracks 使用 model/run/camera namespace；跨鏡頭身分只形成 provisional hypotheses，adapter 保存原 records 映射，不把 GT actor ID 填入既有 target_id 或回寫 canonical records。

### Agent 定位

Agent 根據調查意圖定位資源、調用查詢工具、取得必要證據並解釋結果。第一版以 MockAgent 和記錄可重播的工具流程展示。Projection、world-to-region、navigation、graph search、collision 與 reconstruction 由確定性服務處理。候選和時間假設保持原順序與原資料；語意判斷不改寫已證明的物理限制。

Agent 不取得 repository、filesystem、任意 SQL、shell 或整個 scene 的掃描入口；不自行發明鏡頭、Evidence IDs、region authority 或唯一真實路徑。證據不足、地點歧義、缺圖與 incomplete search 都是可回傳的結果。

### 任務定位與工具資源

每次任務先提供精簡 `TaskContext`：`place_id`、`model_revision`、source/context binding、`run_id/clock_id`、`observation_mode`、`decision_stage`、registry version、opaque resource references 與 allowed tools。這些是資源定位資料，不是目標身分／位置的隱藏答案。Mode/stage/tool permissions 由服務端綁定 run manifest，不能信任 caller 自行宣告；結果查詢 stage 須核對同 run/mode/input/config 的 inference-freeze receipt/hash，改參數不能跳過守門。

外層 LocationRegistry 明確連接 place → model/source/context → camera groups/regions → media/observations/events。每個模型各自綁定時間、座標和 normalization。原 camera IDs 保留，外層 camera reference 有模型與地點 namespace；名稱本身不證明 coverage。
衍生子模型保留 parent revision/source hash、derivation manifest/hash、顯式 source→submodel transform 與原 camera/calibration correspondence。缺映射不可混用校正／region authority；subset/crop 不自動升級核准範圍。

| Proposed tool | 責任 |
| --- | --- |
| `resolve_place` | 回傳已登錄地點或歧義集合 |
| `list_cameras` | 在固定 place/model/run scope 中列鏡頭、群組與已知 coverage 狀態 |
| `query_observations` | 查 canonical records，不重新聚合或更換 IDs |
| `query_events` | 以明確 scope、時間與已有 region index 查事件 |
| `get_event_summary` | 回傳精簡、可引用的事件摘要 |
| `get_event_detail` | 按 reference 取得完整候選、hypotheses 與證據細節 |
| `get_media` | 取得本機准許的合成照片及必要 frame/time references |
| `get_replay` | 取得事件 replay，顯示插值不改推論資料 |

工具列表為後續契約，尚未全部實作。所有工具由本機服務執行並驗證參數、scope 和 references；MockAgent 不自行掃描資料樹。

### 預設摘要與完整資料

預設摘要包含 query scope、camera/time、evidence/event IDs、來源 references、metadata origin/authority、region 結果來源、candidate/hypothesis 數量、`termination_reason`、`complete`、uncertainty 與 detail/media/replay references。它讓 Agent 用定位好的少量證據判斷，而不是把所有座標、Embedding、NavMesh、camera matrices 或 raw metadata 放進 context。

完整 `BoundObservation`／`BoundGapEvent` 仍由 repository 保存。摘要省略不代表底層資料不存在；`complete` 保留 bounded search 的原意，不表示 API request 成功。來源、空值、候選順序與未成功狀態不能因摘要而消失。詳細資料只透過准許的工具按需讀取。

### 資料輸出與外洩邊界

Agent-facing API/data-export 守門先驗證 mode、decision stage、source/context/run 與 references，再產生 allowlist DTO。低階 legacy mock 開發接口保持內部隔離，不自動列為 Agent allowed tools。本階段系統只在本機 synthetic/mock 環境工作，不向外部模型／服務送出照片、檢索資料或秘密；符合 artifact policy 的已授權 GitHub 普通 push 不受此執行期限制。

- `photos_only`：完整合成照片與必要 camera/frame/time/evidence references，不附觀測答案。
- `photos_plus_observations`：相同照片加上真正影像 producer 產生、來源明確的觀測或幾何衍生資料；模擬投影不改稱影像量測。
- 該 run 的圖片判斷／association 前，`photos_only` 不可透過 summary/detail/query 工具取得既有投影、zone、candidate 或身分答案。完成 inference freeze 後，結果查詢 stage 才可讀准許的已產生事件；輸入比較與結果展示分開。
- 兩模式都完整保存 GT，但 GT actor identity／GT 3D position/path、recipe/reference annotations 不進入 Agent、association、Graph、ranking 或一般 query payload。靜態相機校正與合法 scene 配置可由 registry 提供；合法推論出的投影、區域與候選可由相應服務使用並保留 origin/authority/uncertainty。
- 照片、crop 與資料使用 opaque references；回傳可用證據，避免本機 private paths、secret、完整 source archives 和 evaluation references 外洩。
- Agent／工具／API／export 可見的 DTO 與 logs 一併檢查准許欄位；錯誤不能回傳秘密或 raw payload。後續 external adapter 仍必須沿用這個資料邊界。獨立 local evaluation/debug 可保存 GT 與必要定位資料；immutable 歷史紀錄不清洗或回寫。

完整合成 image/media envelope 使用外層 composition。既有 Phase 1 schema 和歷史 least-data interfaces 保持原語意，不把舊 interface 擴張成任意資料讀取。

### 工程驗收

用本機 mock 證明地點定位 → 鏡頭／時間查詢 → 摘要 → 按需照片／事件細節 → replay 的閉環；覆蓋正常、空結果、歧義、缺失 reference 與越界拒絕。驗證 payload/logs 無 GT、hidden identity、secret 或 private-path 洩漏；只報實際工具與輸入／輸出紀錄，不宣稱已證明 token 降幅或 live API 品質。

### OpenAI API 接線

### Token 兜底演算法

## English

### Scope and implementation status

This document records the user's 2026-10-08 engineering direction as **PLANNED / SYNTHETIC_MOCK_ONLY**. No OpenAI or other external model API is connected. No images, summaries or source data are sent out; no live provider, SDK wiring or secret configuration is created. The API wiring and token fallback algorithm remain empty sections.

Engineering baseline `4271b2b` includes the legacy mock adapters, but Agent-facing DTOs and reviewed-package import certification remain pending. Pixel-derived synthetic measurements retain producer/hash lineage and never substitute simulator truth channels. Camera-scoped local tracks feed provisional association hypotheses, preserving original record mappings without rewriting frozen identities.

### Agent role and resources

The Agent locates resources, calls typed retrieval tools, requests necessary evidence and explains results. A MockAgent demonstrates a recorded, replayable tool flow. Deterministic services own projection, region containment, navigation, graph search, collision and reconstruction. Canonical alternatives, provenance, ordering and search status remain unchanged.

A small `TaskContext` fixes place/model/source/context/run/clock/mode/decision-stage/registry scope and supplies opaque references plus allowed tools. The server owns mode/stage/permissions and verifies the matching run/mode/input/config freeze receipt before result reads; callers cannot select a stage to bypass policy. The proposed tools are `resolve_place`, `list_cameras`, `query_observations`, `query_events`, `get_event_summary`, `get_event_detail`, `get_media` and `get_replay`. They are not all implemented yet. The Agent has no repository scan, filesystem, arbitrary SQL or shell tool. Derived submodels retain parent revision/hash, derivation lineage, an explicit transform and camera/calibration correspondence; cropping does not extend authority.

### Summary and data boundary

Default summaries contain scope, camera/time, evidence/event IDs, source and metadata authority, region-result origin, candidate/hypothesis counts, termination, completeness, uncertainty and detail/media/replay references. Full canonical records remain in storage; omission is not absence, and search completeness is not request success.

Mode/stage-aware allowlist DTOs and Agent/tool/API/export-visible logs exclude GT actor identities/3D paths, recipes, reference annotations, secrets, private paths and source archives. Known calibration/static scene context and legitimate inferred geometry remain usable by scoped services. Full synthetic images are permitted through the new local media envelope; photos-only and photos-plus-observations have distinct visible inputs. Before association/inference decisions, photos-only tools cannot expose stored projected/region/candidate answers; allowed frozen results become available in the result-query stage. Isolated local evaluation/debug may retain GT and necessary local locators. Historical records and contracts remain intact. Runtime data egress to external services is disabled; authorized artifact-policy-compliant Git publication is separate. The internal legacy mock API is not an Agent allowlisted tool.

### Acceptance

Demonstrate local mock place resolution → camera/time query → summary → necessary media/details → replay, including empty, ambiguous, missing-reference and out-of-scope cases. Verify payload and log boundaries. Do not claim a measured token reduction or live API result.

### OpenAI API wiring

### Token fallback algorithm
