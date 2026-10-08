# Development rules / 開發與文件維護規則

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

本文件整理既有工作規則，不新增研究需求或改變架構。需求依 [PRD](PRD.md)，模組責任依 [SYSTEM_DESIGN](SYSTEM_DESIGN.md)，已採用解法依 [ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)；發現重大衝突先詢問，不自行改寫規格。

### 文件分工

| 文件 | 存放內容 | 不放入 |
| --- | --- | --- |
| `PRD.md` | 研究需求、成功條件、Phase 邊界 | 開發紀錄、一般 TODO |
| `SYSTEM_DESIGN.md` | 架構、模組責任、資料流 | 每次 commit 或測試結果 |
| `ISSUES_AND_DECISIONS.md` | 核心問題 → 已採用解法 | 開發日誌、小 bug、測試紀錄、未採用方案冒充決策 |
| `DEVELOPMENT_RULES.md` | 持續適用的工程與文件維護規則 | 當次工作進度、歷史驗證結果 |
| `WORK_LOG.md` | 日期／checkpoint 綁定的已完成工作與驗證證據 | 即時待辦清單、未完成工作冒充完成 |
| `CODEX_HANDOFF.md` | 當前狀態、有效待修項目、續作入口及階段性暫緩項目 | 已完成細節、已解問題、過期環境問題、完整歷史與重複規則 |
| `DATA_SCHEMA.md` / `INTERFACES.md` | 實際資料契約與模組介面 | 測試成功日誌 |
| `../../data/README.md` | 已物化資料的日期化盤點與發布邊界 | 尚未產生的 dataset 被當成既有資料 |

工作完成並驗證後，把結果記入工作紀錄；已解決或已失效的 handoff 項目移除，不留「已完成 TODO」。有效未解問題不能只因整理文件而消失；若被暫緩，標明暫緩，不標為解決。歷史紀錄使用當時日期／commit／證據，不能改寫成今天重新驗證的結果。

文件正文放在 specs／engineering／research／operations／history；只由 `docs/README.md` 提供總索引，不另建每分類 README 或逐檔轉址文件。根目錄例外只保留實際 hash／runtime 綁定的檔案或必要路徑別名；新增文件直接使用分類路徑。

### 開發與 Git

- 開始先確認實際工作目錄、`git status` 與 `git branch`；保留使用者及其他工作的未提交修改。
- 優先重用既有 checkout／environment 與單一 immutable 資產來源；branch 可在同一 checkout 切換。不要為每個 milestone 建 worktree、clone、venv 或 raw 副本。必要的隔離仍保留，但刪除／archive 既有 checkout 和資產須有對應授權。
- Python 全部使用 uv；主要依賴來源為 `pyproject.toml`、`uv.lock`，不以 requirements.txt 取代。
- 實作以 milestone 為邊界：可執行功能 → unit／major-flow integration validation → 確認既有階段未破壞 → 獨立 commit → 下一階段。
- 只 stage 本任務檔案；不 `reset --hard`、force push、rewrite history 或 rebase 使用者 commit。Push／PR／merge 需要對應明確授權。
- 遇到重大場景語意、walkability、camera convention、公開介面、指標或 GT isolation 問題，先停止該不確定部分並詢問；可依既有規格解決的小問題不必擴張設計。

程式實作的驗證指令：

```sh
uv run pytest
uv run ruff check .
uv run mypy
git diff --check
```

純文件整理只做相稱的 diff、連結與內容一致性檢查；若沒有重跑程式測試，引用既有結果時標明歷史 checkpoint，不宣稱本次執行。

### 共用網頁工作台

- Amidst 網頁以 `frontend/workbench/` 的[共用工作台](../engineering/SHARED_WORKBENCH.md)為主入口；既有及後續需要頁面展示的功能均接入它的導覽、元件及流程。
- 新場景使用 catalog／adapter，新增展示、調查、測試或人審功能擴充共用工作台。研究／管理權限由後端限制，工作模式及產品的輸入模式／凍結階段不改變權限。
- 遷移既有頁面時重用資料與後端服務，保留原介面、來源綁定及歷史驗證；以局部查詢與獨立 milestone 驗證遷移。未遷入的功能在 handoff 明列，不把主入口決策或舊頁面的 PASS 當作遷移完成。

### 研究有效性與資產

- 原始 `.blend` 保持不變；研究副本與生成資料依既有隔離決策處理。Audit／export 不儲存來源；清理、刪除、修改來源資產或 render 必須另外明確授權。
- GT 僅供 simulation/export、evaluation、debug visualization；不得進入 inference、graph、candidate ranking、semantic reasoning 或 path score。Domain 只放 schema／interface；Agent 不做 geometry、pathfinding 或 collision checking。
- 依 PRD 保留物理硬限制、多解 Top-K 與 provenance；Phase 2 僅保留 schema／interface，Semantic Ranking 在 deterministic closed loop 完成後才考慮。
- 研究配置與合成 fixture 不等於核准的 school walkability、正式資料集或 benchmark。驗證點可見性、技術 render 成功、影像可用性與正式研究驗收是不同證據，不互相代替。
- 規則與永久決策不要複製到每次 handoff。當前授權範圍／暫緩狀態留在 handoff，完成與驗證紀錄留在 work log；不因文件整理擴大實作或發布權限。
- 依 2026-10-08 指示，工程可先以 synthetic/mock 調用、查找與 replay 並行推進，不以正式 Phase 1 全 Exit 作工程前置；工程通過不改寫正式研究狀態。Agent 的操作資源與輸出契約見 [工程邊界](../engineering/AGENT_RETRIEVAL_BOUNDARY.md)。目前不串接外部模型 API；尚未正式的 API 接線與 token 兜底演算法章節保持空白。

## English

These are existing engineering and documentation rules, not new requirements. [PRD](PRD.md) owns research scope, [SYSTEM_DESIGN](SYSTEM_DESIGN.md) owns architecture, and [ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md) contains only core problems and adopted solutions. Ask before resolving major conflicts through design changes.

Keep durable rules here, dated completed work/evidence in [WORK_LOG](../history/WORK_LOG.md), current unresolved/actionable state in [CODEX_HANDOFF](../operations/CODEX_HANDOFF.md), contracts in DATA_SCHEMA/INTERFACES, and materialized-data inventory in [data/README](../../data/README.md). Move verified completion into the log and remove resolved/stale handoff items. Deferred is not resolved. Preserve genuine open issues and bind historical checks to their original date/checkpoint.

Store maintained text in the five category folders and use only `docs/README.md` as the index. Do not add category READMEs or per-document redirect pages. Root exceptions must serve an actual hash/runtime binding or required path alias; new documents use category paths directly.

Verify workspace, Git status and branch before work; preserve unrelated changes. Use uv, pyproject.toml and uv.lock. Implement, validate and independently commit each milestone before the next. Stage narrowly; do not reset, force-push or rewrite user history. Publication requires explicit authorization. Code checks are listed above; documentation-only changes use proportionate diff/link/consistency checks and must not claim an old test run as new.

Prefer reusing one checkout/environment and shared immutable assets rather than accumulating worktrees, clones or raw copies per milestone. Branches can share the same checkout. Necessary isolation remains available; existing assets/checkouts are not deleted or archived without authorization.

Use `frontend/workbench/` as the primary Amidst web entry for existing and future presentation,
investigation, testing and human review. Extend its shared navigation, components and scene
catalog/adapters. Enforce Research/Management access on the server; work modes and product
input/frozen stages do not grant permissions. Reuse existing backend/data contracts during
migration, preserve source-bound history, validate each bounded migration milestone and keep
unmigrated capabilities explicit in the handoff.

The 2026-10-08 direction permits local synthetic/mock engineering alongside formal Phase 1 research, without turning engineering passes into formal acceptance. Follow the [Agent retrieval boundary](../engineering/AGENT_RETRIEVAL_BOUNDARY.md). No external model API is connected now; API wiring and the token fallback algorithm stay empty.

Preserve source Blender assets and isolated research copies. No cleanup, source modification or rendering without explicit authorization. Keep Ground Truth out of inference, search, ranking and path scores. Domain contains contracts only; deterministic modules handle physics, Top-K and provenance, not an Agent. Phase 2 implementation and semantic ranking remain gated by the research scope. Synthetic/configured routes and technical checks are not school navigation certification, a formal dataset or a successful benchmark. A documentation update does not expand implementation or publishing authority.
