# Phase 2 Integration Hardening / Phase 2 整合強化

[繁體中文](#繁體中文) | [English](#english)

> Historical record: local/mock hardening from 2026-10-06. Current additive import checks are recorded in [PHASE2_INTEGRATION](../engineering/PHASE2_INTEGRATION.md); shared current Phase 1 portability code is not replaced by this import.

## 繁體中文

日期：2026-10-06。Branch `phase2/integration-hardening` 從乾淨的 foundation checkpoint
`e4e5afc3ddd19fdb679e5fe0773c3d7f918a3d2b` 建立；基底重新驗證 668 pytest passed、
Ruff／mypy 通過。本輪僅處理 portable local/mock integration，不 merge／push／rewrite。
原架構與凍結證據分別見 [Integration Foundation](../engineering/PHASE2_INTEGRATION.md)、
[Foundation Validation](PHASE2_INTEGRATION_VALIDATION.md)。

### 修正與保留的契約

- Blender discovery 共用 explicit argument → `BLENDER_BIN` → PATH；沒有 macOS executable
  fallback。設定錯誤明確拒絕，不偷偷選另一個 executable。Calibration 載入實際 package
  parent，避免假設 repository `/src`；診斷 scripts 仍可從其他 CWD 以 standalone Python 執行。
- Regular-file reader 使用 host-supported `O_NONBLOCK`／`O_BINARY`，保留 stat→fstat、
  special-file rejection、binary byte identity 與 descriptor cleanup；replay 繼續分塊 hash，
  regular-reader failures 轉為原 `BenchmarkImportError` boundary。
- JSON generated references 使用 POSIX `/`；cross-drive 相對引用明確失敗。Windows drive／UNC
  與 ambiguous paths 依 host 判斷，不能在其他平台被誤當成 CWD-relative input。
- Local repository 在建構時固定 path；service store 依 containing config 解析。搬移 package
  到 Unicode／空白目錄或從其他 CWD 匯入，不需要 Phase 2 查找 repository root。
- Scene／geometry audit staging 改在 destination filesystem；JSON writer 原本已使用相同策略，
  source 保持不變。Injected EXDEV／publication failure 保留原檔並清除 staging，不使用非 atomic copy fallback。
- FIFO／symlink／Node tests 依 host capability 執行；native TypeScript import 採實際 probe。
  支援環境仍跑完整原 assertions，不以移除測試假裝 portability。

Phase 1 domain schemas、graph／Top-K、observation／events、reconstruction、evaluation、
benchmark runner/reporting、dataset provider/loading、geometry 與既有 configs／fixtures、
dependencies／lock 無 diff。Phase 2 API/schema/service/repository port、consumer／TypeScript
契約同樣不變。改動限平台 IO、path/discovery/tool staging adapters 與測試／文件。

### Stress、兼容與檢查

- 96 events／192 observations：MEMORY／LOCAL_JSON 分六批寫入、三輪 idempotent reruns／reopens，
  conflict 不部分發布；原始候選、timing hypotheses、bindings、provenance 與排序保存。
- 1,152 provider samples／768 visible records：三種 ordering、missing／duplicate／ambiguous input
  驗證；不補造 evidence，不靜默 deduplicate 無法判定的輸入。
- Node 實際驗證 96 consumer events／288 replay frames，保存所有 alternatives；不是 renderer
  或 production throughput／high-concurrency benchmark。
- 既有四-case benchmark package 搬移後仍能匯入。Synthetic BlenderDataset producer 使用原
  ObservationAggregation／BoundGapEvent contracts；opaque GT／metrics 只做 hash，不 deserialize
  或進入 API／consumer。未知 schema／不完整 package 繼續拒絕，未認證真實 pilot 資料。
- Fresh results: **723 passed in 80.41s，0 failed／0 skipped**. Focused portability/consumer tests: 120 passed；
  dedicated stress: 19 passed；Ruff passed；strict mypy passed（84 source files）；diff/link checks passed。Targeted counts 已包含在 full total。

### 剩餘平台假設與 deferred items

本輪實測 macOS；Windows／Linux 的 flags、path、EXDEV 行為有針對性模擬，沒有 native OS
certification。Blender／本機資產與支援 native TypeScript 的 Node 必須由環境提供；一般 clone
不含 ignored `.blend`。Exclusive JSON creation 需要 filesystem hard-link support；single-writer、
trusted filesystem 的 storage 不承諾 production concurrency、combined transactions 或 crash durability。
FIFO replacement-race 的 nonblocking guarantee 依 `O_NONBLOCK` capability；缺少該 flag 的
FIFO-capable platform 仍需 native review。Unsupported capability tests 可能 skip，不能當成平台驗收。

Phase 1 benchmark 的 GitRevision/source provenance 與 source-checkout diagnostic defaults 保留；
移除 Git checkout 要求會改變 Phase 1 benchmark 契約，故本輪未改。Scene JSON／README 各檔
atomic publication 不等於整包 transaction。Blender 內嵌歷史資產路徑與 texture dependencies 未修改。

PostgreSQL 維持 factory/settings interface only。Real CV、Detection/Tracking/ReID、Vector DB、
Agent、production UI／Three.js renderer、production infrastructure 均未開始。完成驗證後停止。

## English

`phase2/integration-hardening` starts from the verified `e4e5afc` foundation and changes local/mock
platform adapters only. Blender discovery uses explicit settings, environment and PATH; reads retain
regular-file/binary guarantees; references use POSIX separators with explicit cross-drive rejection;
stores/configs keep their path anchors; diagnostic staging stays on the destination filesystem.

Protected Phase 1 inference/benchmark schemas and logic, configs, fixtures and dependencies retain
identical blobs. Phase 2 API, repository port, consumer/replay payload semantics and PostgreSQL
interface-only status remain intact. Stress covers 96 events, 192 observations, 1,152 samples,
repeated storage and missing/duplicate/order boundaries, plus 96 actual TS consumers/288 frames.
Relocated original benchmark and producer-neutral synthetic outputs import through existing contracts;
GT/metrics remain hash-only. Exact fresh check results are listed above.

Native Windows/Linux certification, unsupported filesystems, FIFO capabilities, configured Blender/assets
and mandatory Node coverage remain environment assumptions. Phase 1 Git provenance and source-only
audit defaults are preserved, not fabricated. No real pilot certification, rendering, geometry changes,
production database/UI/concurrency, semantic ranking, publication or merge occurred. Work stops here.
