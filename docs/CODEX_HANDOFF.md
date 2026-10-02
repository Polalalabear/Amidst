# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-02。規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，
完成／驗證紀錄見 [WORK_LOG](WORK_LOG.md)，契約見 [DATA_SCHEMA](DATA_SCHEMA.md)
與 [INTERFACES](INTERFACES.md)。

### 目前狀態與續作入口

- 本輪 branch：`phase2/integration-foundation`，基底 `b11edb9`；使用隔離 worktree。
  以 `git worktree list` 找到該 branch 的 checkout，再核對 HEAD／dirty state。原 Phase 1
  checkout 的並行修改不屬於本 branch，不能搬入或一併 stage。
- 新增 [Phase 2 Integration Foundation](PHASE2_INTEGRATION.md)：backend API contracts、
  mock providers/service、memory/local JSON repositories、PostgreSQL factory interface、
  TypeScript/Three.js consumer contract 與 benchmark/replay importer。只允許 synthetic/mock。
- 通用 M0–M8 與 deterministic fake-data 後半段閉環已實作。四組 curated fixtures 在
  [`data/mock/`](../data/mock/README.md)，可直接替換符合相同契約的合成 producer。
- 已有 timed blind-gap reconstruction、ADE／FDE／Top-K／physical metrics 與 Rerun
  recording；不等於正式 school dataset／benchmark 或完整 Phase 1 研究驗收。
- 本輪 Integration Foundation 到此結束；未進入 Real CV、production storage/deployment、
  高併發測試或 Agent Semantic Ranking；未 push／PR／merge，不 merge 回 Phase 1。
- School 樓梯／跨樓層與正式 Case 4 仍暫緩；Simplified Stair 只測後半段 interface。

### Blender-derived dataset 接入缺口

- Phase 1 已有 source-bound raw frames→Observation aggregation、independent multi-gap Events、
  content-bound benchmark/replay。需真實 producer 提供符合相同契約的資料與核准 bindings；
  不能由 mock fixtures 推定已完成 school 接入。Projection Error 仍需獨立 evaluation。
- 需核准 WALKABLE／STAIR／WALL 與可信任 directed waypoint routes／camera transitions，
  並讓 navigation、topology、GT、camera calibration／visibility 共用 source/context binding。
  Graph `WALKABLE` 目前依顯式 route 設定，不提供 Mesh collision／clearance 證明。
- Projected endpoints 必須對齊 configured nodes；沒有 arbitrary-point snapping／connector。
  Floor／zone／camera-plane mapping 與 courtyard walkability 尚待確認。
- Rerun 目前是 waypoint graph 與 camera navigation anchors；需接入實際 Mesh、camera
  poses／frustums 才能顯示 Blender scene。AABB metrics 不代替 Mesh collision certification。
- 正式 benchmark 的 Coverage distance／epsilon、採樣與 collision／constraint protocol、
  baseline／ablation 尚未固定。本輪 D=ADE、epsilon=1e-6m 只用於 fake regression。
- 每個 `BoundGapEvent` 仍表示一段獨立 gap；已採用的 multi-gap aggregation 不改成跨多段
  的單一 Event。若後續產品整合要求修改 Phase 1 contract，先停止該部分並回報。

以上是介面／研究缺口，不是新增授權的開發排程。

## English

Status date: 2026-10-02. Resume `phase2/integration-foundation`, based on `b11edb9`, in its
isolated worktree from `git worktree list`; verify actual HEAD and dirty state. Preserve unrelated
concurrent changes in the original Phase 1 checkout.
The four curated deterministic fixtures and generic downstream closed loop are complete:
configured graph/Top-K, timed reconstruction, metrics and saved Rerun recordings.
M6 full-frame schema revalidation is fixed. See WORK_LOG for evidence and
DATA_SCHEMA/INTERFACES for replaceable contracts. The additive
[Integration Foundation](PHASE2_INTEGRATION.md) supplies mock API/service/storage, PostgreSQL
factory interface, TypeScript consumer contracts and verified benchmark/replay import.

This foundation stops here: no Real CV, production database/deployment, concurrency load tests,
Agent Semantic Ranking, formal school dataset/benchmark, publication or merge into Phase 1.
School stairs/cross-floor/formal Case 4 remain deferred; the
simplified stair only tests a synthetic interface.

Phase 1 raw-frame aggregation, independent multi-gap Events and benchmark/replay contracts already
exist. Remaining Blender interfaces: producer data with approved bindings; approved walkability,
wall/stair geometry and directed route/transition configs; shared source/context
bindings; explicit camera-plane/floor/zone mapping and graph-node anchors; actual mesh
collision/clearance and camera-pose/frustum visualization. No arbitrary point attachment
or approved courtyard interpretation exists. Projection Error,
formal sampling/Coverage/collision protocol and baselines/ablations remain
open. Each BoundGapEvent remains one independent gap. Stop and report before any future Phase 1
contract change. Fake ADE epsilon=1e-6m and AABB tests do not certify a school scene or formal benchmark.
