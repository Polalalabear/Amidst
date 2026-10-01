# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-01。此文件僅保留當前有效狀態與續作事項；規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，已完成內容與歷史驗證見 [WORK_LOG](WORK_LOG.md)，不在此重複。

### 目前狀態與續作入口

- Repository：`/Users/polalabear/Developer/amidst`，branch `main`；實際 HEAD／dirty state 依接續時的 Git 檢查，不以舊對話 checkpoint 取代。
- M0–M8 通用 prototype 已實作並提交；完整 Phase 1 研究閉環尚未完成。M9–M13、semantic ranking 與正式 school dataset／benchmark 尚未開始。
- 最新授權範圍是文件整理，不包含修程式、進入 M9 或產生資料。下一個實作範圍尚待使用者指定。
- school 樓梯／跨樓層配置與正式 Case 4 暫緩；不是同樓層工作的阻塞條件。既有 generic stair interfaces／synthetic regression tests 保留。
- 需求／架構／採用決策入口：[PRD](PRD.md)、[SYSTEM_DESIGN](SYSTEM_DESIGN.md)、[ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)。目前資料可用性見 [data inventory](../data/README.md)；推論／導航限制見 [INTERFACES](INTERFACES.md) 與 [DATA_SCHEMA](DATA_SCHEMA.md)。

### 有效待修：M6 frame 入口完整 schema 重驗證（Review priority P2）

位置：[InverseProjectionService.project_frame](../src/amidst/geometry/inverse_projection.py)。該入口檢查 status、pixels、camera ID，沒有重驗完整 ObservationFrame；合法 frame 經 `model_copy(update={"provenance": Provenance.GROUND_TRUTH})` 繞過 schema 後仍可被轉成 PROJECTED。正常 constructor／JSON validation 會拒絕此 provenance；這是 object-input 防護缺口，不是已確認的正常流程 GT 座標洩漏。

狀態：未修。若授權修補，在 service 入口重驗 frame、以 typed projection failure 拒絕，加入 `model_copy`／`model_construct`／非法 provenance regression tests。既有測試通過不代表這項防護已完成。

### 後續實作需處理的缺口

- 尚無 synthetic frame→Observation aggregation helper 或正式 school end-to-end pipeline；已通過的 integration 是合成 Evidence→projection→configured graph。
- 若要產生同樓層 school 資料，先確立可信任路徑、floor／zone、camera-plane mapping 與 configured waypoint anchors。現有導航只驗證顯式 polyline 契約，不計算 Mesh 障礙／碰撞／clearance；任意 projected point 也不會自動吸附或連接至 graph。庭院 floor／walkability 尚未核准。
- Projection Error evaluation、blind-gap time parameterization、metrics、Rerun、formal cases 與 baseline 尚未實作；正式 Coverage@K 的 distance D／epsilon 要在 M10 benchmark 前固定，不是本次文件整理阻塞。

以上是有效未完成／暫緩項目，不是已授權的開發排程。

## English

Status date: 2026-10-01. This is live handoff state only. Read [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md) for rules, [WORK_LOG](WORK_LOG.md) for dated completed work and checks, PRD/SYSTEM_DESIGN/ISSUES_AND_DECISIONS for specifications/decisions, and [data inventory](../data/README.md) for availability. Resume in `/Users/polalabear/Developer/amidst`, branch `main`, verifying actual HEAD and dirty files rather than trusting historical checkpoints.

M0–M8 generic implementations are committed; the full research loop and M9–M13 are not complete. Current authority is documentation reorganization only. School stairs/cross-floor configuration/formal Case 4 are deferred, not prerequisites for separately authorized same-floor work; existing generic contracts and synthetic tests remain.

One active M6 issue remains (review priority P2): `project_frame` does not revalidate the full ObservationFrame. Schema-bypassing `model_copy` can supply invalid GROUND_TRUTH provenance and still produce PROJECTED output. Normal schema validation rejects it; no normal-pipeline GT-coordinate consumption was confirmed. A future authorized fix needs typed rejection and bypass regression tests.

Other live gaps: no synthetic-frame aggregation helper or formal school end-to-end dataset; same-floor work needs trusted routes, camera-plane bindings and configured-node anchors. Navigation is an explicit-polyline contract, not mesh collision/clearance certification or arbitrary-point attachment. Courtyard interpretation is unapproved. Projection Error evaluation, time-parameterized reconstruction, metrics, Rerun, formal cases/baselines and fixed Coverage@K D/epsilon remain downstream work, not a new authorized plan.
