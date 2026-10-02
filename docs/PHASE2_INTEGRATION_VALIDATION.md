# Phase 2 Integration Validation / Phase 2 整合驗證與凍結

## 繁體中文

**狀態：`PHASE2_INTEGRATION_FOUNDATION_VALIDATED`。** 日期：2026-10-02。
本輪只驗證既有 mock Integration Foundation，新增回歸測試與文件後停止擴張。
架構契約見 [PHASE2_INTEGRATION](PHASE2_INTEGRATION.md)。

### Branch / commit 與 Phase 1 邊界

- Branch：`phase2/integration-foundation`；開始驗證時工作樹 clean。
- Phase 1 checkpoint／merge-base：`b11edb9d6157699d395c112298f8fab518f202a6`。
- 驗證起點：`b839254bdae8275c9aa5340b2ed60af375cf585e`；本文件與兩個新增測試檔
  由最後一個 validation commit 保存，SHA 可用 `git log -1 --format=%H -- docs/PHASE2_INTEGRATION_VALIDATION.md` 查得。
- 原 Phase 1 branch `codex/dataset-infrastructure` 當時 tip 為
  `bd984f2d5a68d259195dc713812a7be388ba9723`，在另一 checkout 獨立前進。
- 139 個受保護 Phase 1 paths 的 Git blob／mode 與基底相同。Domain schemas、
  Observation/Event/BoundGapEvent/CandidateTrajectory、Graph、Top-K、Reconstruction、
  Metrics、benchmark、既有 fixtures、dependencies／lock 未改動；沒有 contract 問題。
- 原七個 Phase 2 commits：`36fd908`、`70ccbb9`、`f51bf55`、`6ff76db`、`e2da4d8`、
  `899061f`、`b839254`。本輪只增加 validation commit；不 rewrite／rebase／reset／force-push，
  不 merge 或 push。Phase 2 commits 未進入 Phase 1 local branches；本輪沒有查詢遠端狀態。

### 驗證範圍與結果

| 範圍 | 結果 |
| --- | --- |
| Mock end-to-end | 四組既有 fixtures 通過 provider→aggregation→reconstruction→snapshot→service→API→consumer→replay；GET 不重新推論。 |
| API | 七個 GET route 的 response/schema 一致；400/404/405、Unicode/slash/percent IDs、canonical keys、inclusive/point queries 通過。 |
| Repository | MEMORY／LOCAL_JSON 保留 immutable canonical records、idempotence、conflict rejection、corrupt-disk rejection、config-relative paths；注入 atomic publication failure 後原 bytes／snapshot 不變且清除暫存檔。 |
| PostgreSQL | 只有 factory/settings interface；選用時明確 NotImplementedError，沒有 driver／migration／deployment。 |
| Replay | 原 keyframes/provenance 與全部 alternatives 保留；插值僅 display INFERRED_GAP；越界拒絕、NO_FEASIBLE 空結果與 incomplete 狀態保留，儲存資料不變。 |
| GT isolation | 暫存 replay 分別改變 GT／metric config，實際 evaluation 輸出改變，但 repository 與全部 GET 推論 payload 相同。Debug GT／metrics overlays 不改寫 Event、hypotheses 或 local bytes。 |
| Consumer | Node 26 實際執行 TypeScript validators/key helper；nullable fields、ordering、uncertainty、termination、complete、XYZ/Z-up 與空／incomplete 結果保留。 |

Mock wiring 不 deserialize evaluation geometry；replay importer 只 hash GT／metrics bytes
來驗證完整性，不將其解析為 inference inputs。此驗證不是 school dataset 或研究驗收。

### 本輪實際檢查

| 指令／覆蓋 | 結果 |
| --- | --- |
| `uv run pytest tests/integration/test_phase2_integration.py` | 14 passed in 3.11s |
| `uv run pytest tests/unit/test_phase2_*.py` | 102 passed in 3.11s；含新增 13 cases |
| 兩個新增 validation 檔一起執行 | 18 passed in 4.42s；含 5 個 GT／read-only/debug cases |
| `uv run pytest` | **668 passed in 46.64s，無 skipped／failed** |
| `uv run ruff check .` | Passed |
| `uv run mypy` | Passed，80 source files |
| `git diff --check` | Passed |

沿用 locked installed uv environment，以 offline/frozen/no-sync、明確 Phase 2 PYTHONPATH
與暫存 cache 執行；Python 3.12.12、Node 26.0.0。完整 pytest 在可正常啟動 Blender 的
獲准環境執行，包含既有 Blender 與 TypeScript runtime tests；沒有 render／save assets。

### Portability、known limitations 與 deferred items

- **SAFE NOW**：tracked Phase 2 code 無本機絕對路徑；pathlib/config-relative paths、argv
  subprocess、replay logical POSIX paths 與 root-containment checks 已驗證。
- **NEEDS LATER HARDENING**：Node native type-stripping capability/version gate；Windows／特殊
  filesystem 的既有 O_NONBLOCK／hard-link/atomic writer 行為；跨平台 Blender discovery 與資產搬移。
  本機 ignored `.blend` symlinks 是 checkout 配置，不能當成可發布的 portable package。
- **BLOCKING**：目前本機 mock foundation 無 blocking issue；未宣稱跨 OS certification。
- LOCAL_JSON 為 single-writer；API 無 production auth/server、pagination 或 concurrency 保證。
  Manifest hashes 驗證內部一致性，不能替代外部權威或正式 calibrated data。
- Deferred：Real CV、production Detection/Tracking、ReID、PostgreSQL／Vector DB production、
  Three.js renderer／production UI、load tests、Agent Semantic Ranking、Blender semantic geometry、
  Phase 1 schema／benchmark semantic changes。

下一步建議回 Phase 1 完成 Blender research closed loop：核准 producer/source-context bindings、
walkability／routes／camera calibration，補 projection evaluation、scene visualization 與正式
benchmark protocol／baselines。實際未決項目見 [CODEX_HANDOFF](CODEX_HANDOFF.md)；此建議不構成新開發授權。

## English

**`PHASE2_INTEGRATION_FOUNDATION_VALIDATED`**, 2026-10-02. The branch, checkpoint and audited
commit are recorded above. Protected Phase 1 blobs/modes and semantics remain unchanged. This
validation adds tests/documentation only and stops here, without publication or merge into Phase 1.

The four mock cases pass the full provider-to-replay chain. All seven read-only API contracts,
memory/local repository semantics, atomic failure handling, replay provenance/alternatives and
TypeScript consumer preservation pass. Changing temporary GT or metric configuration changes
evaluation outputs while every canonical inference/API payload stays identical. Debug overlays and
seeks leave stored records/bytes unchanged; GETs do not rerun inference.

Fresh checks: **668 pytest passed, no skips/failures**, Ruff passed, strict mypy passed for 80 source
files, and diff checks passed. The table records targeted coverage and exact execution conditions.
PostgreSQL remains interface-only; storage is single-writer and the API is mock/local. No local
portability blocker was found; Node capability gating, Windows/filesystem behavior and Blender asset
packaging require later hardening. No cross-platform or production certification is claimed.

Recommend returning to the separately owned Phase 1 Blender research closed loop using the existing
handoff decisions. Real CV, production databases/UI, ranking, load testing and semantic/schema
changes remain deferred and require a new scope.
