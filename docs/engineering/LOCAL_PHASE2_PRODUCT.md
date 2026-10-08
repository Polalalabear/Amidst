# Local Phase 2 product / 本機 Phase 2 產品

2026-10-08。狀態：**OPERATING_LOCAL_SYNTHETIC_PRODUCT / NO_EXTERNAL_MODEL_CALLS**。
續接 [M1–M6](SIMULATION_ENGINEERING.md)、[E1 pilot](LOCAL_CAMERA_PILOT.md) 與既有
[Phase 2 canonical contracts](PHASE2_INTEGRATION.md)，在 `codex/simulation-engineering`
完成持久調查控制室。這個 frozen product run 與原 Phase 1 正式研究 freeze 是不同事項。
當次驗證及來源 hashes 見 [product receipts](../../data/product/checkpoint_20261008/validation.json)。

使用者最新決策：**[共用工作台](SHARED_WORKBENCH.md)／8016／frontend/workbench 是統一
網頁主入口**。本文件的8020／frontend/product為已完成的工程lab與待遷移來源，保留原程式／
素材／歷史驗證；其頁面功能後續接入工作台，不再擴張成獨立主要產品前端。Product backend、
freeze、typed tools／workflow／media接口可供adapter接入；目前尚未完成這項遷移。

## 已實作能力

| 段落 | 可操作能力 | 資料邊界 |
| --- | --- | --- |
| P7 | SQLite immutable read model、camera/region/time keyset paging、append-only ledger | 原 canonical IDs/payload/order 保留；cursor 綁完整 scope/filter |
| P8 | RGB crop 的 34 維 handcrafted appearance、quality、代表照片、同分 Top-K；同鏡頭 stitching | 無 trained ReID/global identity；缺失時間、overlap、unmatched 與全部歧義保存 |
| P9 | 中英有限意圖模板、typed dynamic tool plans、TRACE/COMPARE/BEHAVIOR/MULTI_TARGET | 未支援語言回 NEEDS_INPUT；固定工具／局部範圍／預算，無 semantic reranking |
| P10 | 四鏡頭 HTML5 MP4、Three.js Z-up 3D、全域時軸／主鏡頭／速度／seek | 影片重用原 RGB；像素投影保留真來源時間，GAP 插值只是呈現 |
| P11 | 持久案例／stop/resume／報告／operator review／HTML export | server 綁 session/mode/stage/freeze/operator；review 不改 canonical 或確認身分 |
| P12 | 當次 HTTP/browser/regression、獨立 evaluation、fresh-output reproduction | GT 在 freeze 後由獨立 evaluator 讀取，產品 GET/工具不推論、不讀 GT |

完整來源仍為 `SYNTHETIC`。新 appearance、stitch 與產品 scopes/version 另存，原 E1
observations/events、legacy Graph 與 timing candidates 不回寫。SQLite 的 CASE/REPORT/REVIEW
以 optimistic revisions 和完整 prefix hash chain 保存，與 immutable evidence 分離。
Public read model 另加由該 event candidates/trajectories 推得的嚴格 counts；原字段、IDs與
source snapshots 保留，summary 的省略不刪除底層資料。

## 啟動及重現

在既有 checkout 與環境操作，無需新 worktree/clone/venv。既有 E1 source checkpoint 位於
ignored `data/engineering/local_run/local_camera_v1/test/checkpoints/final`；若來源未物化，先照
[E1 操作指南](LOCAL_CAMERA_PILOT.md) 產生自己的同 run freeze，不引用不存在的照片。
首次安裝 optional product dependency 與本機前端 dependency：

```sh
uv sync --extra product
npm --prefix frontend/product ci --ignore-scripts --no-audit --no-fund
```

其後不需外部網路；FFmpeg 和 Three.js 在本機執行／供應，不使用 CDN。

```sh
uv run --offline --no-sync python -m amidst.product build \
  --source data/engineering/local_run/local_camera_v1/test/checkpoints/final \
  --output data/product/local_run/operator_v2 \
  --video-pool data/product/local_run/media_pool
uv run --offline --no-sync python -m amidst.product serve \
  --output data/product/local_run/operator_v2 --port 8020
uv run --offline --no-sync python -m amidst.product demo \
  --output data/product/local_run/operator_v2
uv run --offline --no-sync python -m amidst.product evaluate \
  --output data/product/local_run/operator_v2
uv run --offline --no-sync python scripts/validate_local_product.py \
  --url http://127.0.0.1:8020 \
  --receipt data/product/local_run/operator_v2/http_validation.json
```

控制室：<http://127.0.0.1:8020>。選 mode → camera/time → local seeds → 意圖 → 建立計畫 →
分步執行／停止／續跑 → 必要照片及全部路線 → 報告與独立 review；已存案例可在重啟後載入，
報告可輸出 HTML。CASE 狀態 `COMPLETED` 指有限工作流程完成；detail/media 預算耗盡仍列入
未解項目，不能據此聲稱證據全知、Graph exhaustive、人物確認或查詢成功。

`build` 驗證 RGB/hash、原 freeze 與 source documents，photos-only 自 pixels 重算且必須
與自己的已 freeze producer output 一致。photos-plus 使用該模式自己的已驗證量測。
同照片／producer/config/static context 下結果一致，這是本機接收端與 stage 比較，無 GPT
品質或 token 結論。`load/serve` 只驗證 fixed artifacts；模型／source/media/config/producer
變動須新 output/freeze，既有衝突拒絕覆寫。重現時用新的 empty output，重用同一 video pool：

```sh
uv run --offline --no-sync python -m amidst.product build \
  --source data/engineering/local_run/local_camera_v1/test/checkpoints/final \
  --output data/product/local_run/reproduction_v2 \
  --video-pool data/product/local_run/media_pool
uv run --offline --no-sync python -m amidst.product evaluate \
  --output data/product/local_run/reproduction_v2
pytest -q --require-physical-evidence
ruff check src tests scripts
mypy src/amidst
node --test frontend/product/timeline.test.mjs
```

workbench milestone 的驗證有独立 receipt；最後共享 branch 整合已實際運行 **2652 tests，
0 failures/errors/skips，沒有排除任何 tests**；Ruff／mypy164 files及兩前端28Node tests PASS。
原兩份局部PASS不相加作full結果。2652結果來自新的完整JUnit；product測試namespace
修正同名test_service收集撞名，沒有刪除cache或改workbench程式。
這次 fresh output 重現不是原 all-case formal clean-checkout reproduction。

## 本機 API 與 typed resources

`GET /product/v1/contexts` 取得 server-owned session、精簡 TaskContext、product run/freeze
及操作員 opaque ref。角色固定 `TRUSTED_LOCAL_OPERATOR`，不能用 request 宣告角色或 stage。
`GET /product/v1/contract` 提供 13 個 tools 與 strict response/intent/execute/review schemas。
`POST /product/v1/tools/<tool>` body 必須有 `session_ref`：

- `resolve_place`、`list_cameras`、`query_observations`、`query_events`。
- `get_event_summary`、`get_event_detail`、`get_media`、`get_replay`。
- `get_observation_detail`、`query_reachable_cameras`、`propose_feasible_trajectories`。
- `search_person_appearance`、`get_stitch_hypotheses`。

查詢必須有局部 camera/region anchor 和 time range；appearance 的 public 單次查詢是指定
camera pool，evaluation 的 reachable-camera kernel pool 接收端另行明定，兩者不混稱。
Proposal 先由 seed→track→event ref index 取範圍，再做 SQL paging；不先截斷全事件才過濾。
summary 保留來源、scope、camera/time、evidence/detail/media/replay refs、候選/時間假說
counts、termination/complete、uncertainty。Detail 保留全部 canonical candidates 與排序。

操作員 workflow endpoints：`intent`、`execute`、`plan`、`case`、`cases`、`report`、`review`、
`export-report`；view endpoints：`view/scene`、`view/videos`、`view/timeline`。
View 只提供該 synthetic run 的必要 region floor rectangles、推論位置與 refs，不提供
全 scene、NavMesh、matrices、raw metadata、feature vectors 或 source archive。
照片和影片由 `media/<opaque_ref>?session_ref=...`／`video/<opaque_ref>?session_ref=...`
取得；影片支援 validated byte ranges。所有 payload/errors/logs 都不回 private locators。
只接受 localhost/127.0.0.1 Host、loopback peer 和 matching origin，不信任 forwarded headers。

INPUT 的 photos-only 禁止 stored observations/regions/projections/events/appearance/stitch/
scene/video/timeline/reports；photos-plus 只得 pixel measurements，無 geometry defaults。
已存結果只有在同 run/mode/input/config 的 freeze 被驗證後，才由 server 轉 RESULTS。
更改 caller 參數、跨 mode plan、錯 ref／source／hash／cursor 均不能跳過守門。

## 時間與呈現

本次 244 張真實存在的 RGB 為 **2.5 Hz source/CV**，四支 MP4 為 **15 fps presentation**。
每個 video frame 選原 RGB 中最近的影格，沒有新增 observation；不把 presentation fps
宣稱為 camera 或測量頻率。Timeline 回各 camera 的實際 frame timestamp、offset 或缺圖。
可見 3D marker 只保持該真影格的像素投影、原 timestamp/ref；不外插或製造新 observed點。
GAP 全部原 timing hypotheses 依 frozen timing 插值，仍為 `INFERRED_GAP`。

主時鐘由 HTML5 `requestVideoFrameCallback` 的實際 media time 驅動；各鏡頭 soft sync。
UI 量測 media-to-3D skew、p95、seek recovery、實際影格 callbacks，無 samples 時 N/A。
量測是當次本機 UI/HTTP 端到端呈現延遲，與 source frame quantization、推論精度、正式
benchmark 分開；切 mode/session 會終止 fetch、decoder callbacks 與清除舊 scope 結果。

## 當次精度與未完成範圍

仍使用 E1 的 150 measurements／18 tracks／64 events／78 routes／146 timing alternatives。
新的 appearance 有 150 crop descriptors，stitch 有 31 hypotheses（7 provisional short gaps、
6 incompatible overlaps、18 unmatched）。五個 produced pure-track eligible queries 的
handcrafted Recall@1/3/5 = **0.4/0.6/0.8**；同一固定 pool 的 component-mean-RGB baseline
= **0.2/0.6/0.8**。只五個 eligible queries，六個混合 tracks 被排除；沒有 LOW/MEDIUM
quality 的 measured eligible population，不宣稱泛化、trained ReID 或未檢出人物 recall。

同鏡頭 stitch 在已知 eligible pairs 中 TP1／FP2、precision **0.333**；獨立 positive
reference 只有1組、recall1；另外4個 provisional pairs仍 unresolved。Global IDF1、
false merge/split N/A。既有行為誤報／漏報只在 source evaluation dataset/recipe config/
inference/freeze/truth 全部匹配時引用；optional quote 不匹配回 N/A，不補造新標註。

可改善項目：development 上的 pixel merges／ID switches、品質與外觀排名、獨立多 run
資料及時序壓力測試。PostgreSQL／vector DB／部署認證、trained detector/ReID、真攝影機及
live model 尚未交付。原正式 Cases1–3×A/B/C×K、必要消融、相同 eligibility 的 independent
exhaustive inventory、fresh 5Hz school research 與 clean-checkout reproduction 另行續作；
Case2/Case3 full gates BLOCKED、Case4 DEFERRED，原 Phase2 branch/tag FROZEN。不 merge main。

## 發布資料

Git 只保存程式、依賴 lock、文件與 curated counts/hashes/驗證摘要。
ignored `data/product/local_run/` 保存 SQLite、完整 descriptors/stitches、frozen product
documents、MP4、HTML reports、evaluation/debug mappings、UI PNG；RGB／GT 仍在原 E1
materialization，沒有新增 raw 副本。Product manifest 的 source/video-pool locators 只屬
本機 administration，Agent DTO/export 不包含它們。原 scene／locked inputs／歷史 bytes 保留。

## OpenAI API 接線

## 大幅減少 token 的兜底演算法

## English

The operating local synthetic product adds durable immutable SQLite retrieval, RGB-crop
handcrafted appearance, provisional camera-local stitching, bounded Chinese/English intent
templates and dynamic typed investigation plans. A local control room presents four actual
source-derived videos and all frozen 3D alternatives, with a master media clock, explicit
source-frame offsets and measured soft-sync telemetry. Cases, stop/resume, reports and
independent operator reviews persist across restart; HTML reports can be exported locally.

The user's latest decision makes workbench/8016 the unified primary web UI. Product/8020
is preserved as the existing engineering lab and migration source. Existing/future page
capabilities move into workbench; the backend interfaces are available, but migration is
not yet complete. Historical results and implementation remain intact.

Source RGB/CV runs at 2.5Hz; 15fps MP4 presentation holds existing images. No extra observed
positions, identity confirmations or synthetic camera handoffs are created. Product build
recomputes photos-only pixels against its own freeze; loading and querying never rerun
inference or read truth. Server-bound mode/stage/source/config/freeze/operator scope, strict
DTOs, keyset cursors, reference allowlists and loopback Host/origin checks enforce boundaries.

Current aggregate evaluation has only five eligible pure-track appearance queries, with
Recall@1/3/5 of .4/.6/.8 versus .2/.6/.8 for the identical-pool mean-RGB baseline. Stitching
has one known positive and two false positives; other pairs remain unresolved. These are
conditional local synthetic diagnostics, not trained ReID or full-actor recall. Formal
school/all-case acceptance, external models, real cameras and production deployment remain
separate and incomplete. Original research/frozen branches and source artifacts are preserved.

## OpenAI API wiring

## Token fallback algorithm
