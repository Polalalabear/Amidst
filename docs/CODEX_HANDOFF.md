# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-01。規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，
完成／驗證紀錄見 [WORK_LOG](WORK_LOG.md)，契約見 [DATA_SCHEMA](DATA_SCHEMA.md)
與 [INTERFACES](INTERFACES.md)。

### 目前狀態與續作入口

- Repository：`/Users/polalabear/Developer/amidst`；本輪 branch
  `codex/deterministic-downstream-scenarios`。續作時核對實際 HEAD／dirty state。
- 通用 M0–M8 與 deterministic fake-data 後半段閉環已實作。四組 curated fixtures 在
  [`data/mock/`](../data/mock/README.md)，可直接替換符合相同契約的合成 producer。
- 已有 timed blind-gap reconstruction、ADE／FDE／Top-K／physical metrics 與 Rerun
  recording；不等於正式 school dataset／benchmark 或完整 Phase 1 研究驗收。
- 本輪授權到此結束；未進入完整 Agent Semantic Ranking，也未 push／PR／merge。
- School 樓梯／跨樓層與正式 Case 4 仍暫緩；Simplified Stair 只測後半段 interface。

### Blender-derived dataset 接入缺口

- 需 synthetic frame→Observation aggregation helper；保留可見片段、camera／target ID、
  timestamp／plane／floor／zone，以及 schema validation。M6 frame schema bypass 已修，
  不再是有效待修；Projection Error 仍需獨立 evaluation。
- 需核准 WALKABLE／STAIR／WALL 與可信任 directed waypoint routes／camera transitions，
  並讓 navigation、topology、GT、camera calibration／visibility 共用 source/context binding。
  Graph `WALKABLE` 目前依顯式 route 設定，不提供 Mesh collision／clearance 證明。
- Projected endpoints 必須對齊 configured nodes；沒有 arbitrary-point snapping／connector。
  Floor／zone／camera-plane mapping 與 courtyard walkability 尚待確認。
- Rerun 目前是 waypoint graph 與 camera navigation anchors；需接入實際 Mesh、camera
  poses／frustums 才能顯示 Blender scene。AABB metrics 不代替 Mesh collision certification。
- 正式 benchmark 的 Coverage distance／epsilon、採樣與 collision／constraint protocol、
  baseline／ablation 尚未固定。本輪 D=ADE、epsilon=1e-6m 只用於 fake regression。
- `BlindGapReconstructor.reconstruct(event)` 目前以 `Event.time_range` 表示單一 gap；
  多個 observation intervals／多段 gaps 的完整 Event aggregation 仍待實作。

以上是介面／研究缺口，不是新增授權的開發排程。

## English

Status date: 2026-10-01. Resume in `/Users/polalabear/Developer/amidst`, branch
`codex/deterministic-downstream-scenarios`, verifying actual HEAD and dirty state.
The four curated deterministic fixtures and generic downstream closed loop are complete:
configured graph/Top-K, timed reconstruction, metrics and saved Rerun recordings.
M6 full-frame schema revalidation is fixed. See WORK_LOG for evidence and
DATA_SCHEMA/INTERFACES for replaceable contracts.

This round stops here: no full Agent Semantic Ranking, formal school dataset/benchmark,
publication or merge. School stairs/cross-floor/formal Case 4 remain deferred; the
simplified stair only tests a synthetic interface.

Remaining Blender interfaces: frame-to-Observation aggregation; approved walkability,
wall/stair geometry and directed route/transition configs; shared source/context
bindings; explicit camera-plane/floor/zone mapping and graph-node anchors; actual mesh
collision/clearance and camera-pose/frustum visualization. No arbitrary point attachment
or approved courtyard interpretation exists. Projection Error, multiple-gap Event
aggregation, formal sampling/Coverage/collision protocol and baselines/ablations remain
open. Fake ADE epsilon=1e-6m and AABB tests do not certify a school scene or formal benchmark.
