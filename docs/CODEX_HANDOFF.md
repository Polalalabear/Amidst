# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-02。規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，
完成／驗證紀錄見 [WORK_LOG](WORK_LOG.md)，契約見 [DATA_SCHEMA](DATA_SCHEMA.md)
與 [INTERFACES](INTERFACES.md)。

### 目前狀態與續作入口

- Repository：`/Users/polalabear/Developer/amidst`；本輪 branch
  `codex/dataset-infrastructure`。續作時核對實際 HEAD／dirty state。
- 通用 M0–M8 與 deterministic fake-data 後半段閉環已實作。四組 curated fixtures 在
  [`data/mock/`](../data/mock/README.md)，可直接替換符合相同契約的合成 producer。
- 已有 timed blind-gap reconstruction、ADE／FDE／Top-K／physical metrics 與 Rerun
  recording；不等於正式 school dataset／benchmark 或完整 Phase 1 研究驗收。
- Camera extraction、producer-neutral Observation／multi-gap aggregation、benchmark
  runner／MetricConfig／provider contract 與 GT isolation 均已實作；前輪完成
  [140 boundary regressions](../data/mock/boundary/README.md)，共 687 tests。
- Benchmark case-input rejection 保存 structured diagnostics 並重新拋原 exception；
  summaries 保留拒絕原因、端點與 GT unavailable 狀態。正式 schemas 未變更。
- 使用者本輪要求 Blender physical integration／collision Top-K pruning，但
  [live semantic audit](../data/scene_audit/SEMANTICS.md) 確認沒有 WALKABLE／WALL／
  OBSTACLE／STAIR 標記，依指定 stop conditions 暫停 physical integration。
  30 AREA／28 PORTAL 是 annotation；未猜測 `group_*`／`Cube.*`。原 scene 未變更。
- 需人工確認 source-bound walkable／collider roles、floor planes／camera bindings 與
  physical clearance policy，才可續作 Case 1–3。29 camera matrices 與 portable catalog
  完全一致；這不等於 Projection Error 或 ground-plane authority。
- Collision Top-K pruning 仍 unresolved，evaluation-only fake AABB detector 保留。
  正式 schemas/core 未修改，未擴 fake fixtures；epsilon=0 依既有契約拒絕。
- 未進入 Agent／Phase 2，未 push／PR／merge。
- School 樓梯／跨樓層與正式 Case 4 仍暫緩；Simplified Stair 只測後半段 interface。

### Blender-derived dataset 接入缺口

- M6 frame schema bypass 已修；Projection Error 仍需獨立 evaluation。
- 需核准 WALKABLE／STAIR／WALL 與可信任 directed waypoint routes／camera transitions，
  並讓 navigation、topology、GT、camera calibration／visibility 共用 source/context binding。
  Graph `WALKABLE` 目前依顯式 route 設定，不提供 Mesh collision／clearance 證明。
- Projected endpoints 必須對齊 configured nodes；沒有 arbitrary-point snapping／connector。
  Floor／zone／camera-plane mapping 與 courtyard walkability 尚待確認。
- Rerun 已支援 waypoint graph、camera navigation anchors 與 portable calibration
  poses／frustums；仍需接入實際 Mesh。AABB metrics 不代替 Mesh collision certification。
- 正式 benchmark 的 Coverage distance／epsilon、採樣與 collision／constraint protocol、
  baseline／ablation 尚未固定。本輪 D=ADE、epsilon=1e-6m 只用於 fake regression。
- 多段 gaps 已由 `reconstruct_gaps()` 保留為獨立 BoundGapEvents；同時／重疊 visibility
  arbitration 仍暫緩。沒有明確 missing-camera-frame marker 或 coordinate-origin attestation
  schema；目前只保留供應的 Evidence 與 absence，不推定 occlusion／out-of-FOV。

以上是介面／研究缺口，不是新增授權的開發排程。

## English

Status date: 2026-10-02. Resume in `/Users/polalabear/Developer/amidst`, branch
`codex/dataset-infrastructure`, verifying actual HEAD and dirty state.
The four curated deterministic fixtures and generic downstream closed loop are complete:
configured graph/Top-K, timed reconstruction, metrics and saved Rerun recordings.
Camera extraction, producer-neutral aggregation, independent multiple-gap Events, the
benchmark runner, MetricConfig, provider contracts and GT isolation are implemented.
The preceding boundary round completed 140 regressions, for 687 tests, and narrow
benchmark report diagnostics. Formal schemas are unchanged; input exceptions are re-raised.
Zero epsilon is rejected.
M6 full-frame schema revalidation is fixed. See WORK_LOG for evidence and
DATA_SCHEMA/INTERFACES for replaceable contracts.

The user requested Blender physical integration in the current round. The
[fresh semantic audit](../data/scene_audit/SEMANTICS.md) finds no WALKABLE/WALL/OBSTACLE/STAIR
labels. Physical integration is stopped under the explicit user conditions until trusted
source-bound surface/collider roles, floor/camera-plane bindings and clearance policy are
provided. AREA/PORTAL annotations and unlabeled meshes are not promoted to physical
authority. The source is unchanged and all 29 camera matrices match the catalog exactly;
this does not measure Projection Error. No core/schema changes, new fake fixtures, Agent,
Phase 2, school Cases 1–3, publication or merge. Collision pruning remains unresolved.
School stairs/cross-floor/formal Case 4 remain deferred; the simplified stair only tests
a synthetic interface.

Remaining Blender interfaces: approved walkability,
wall/stair geometry and directed route/transition configs; shared source/context
bindings; explicit camera-plane/floor/zone mapping and graph-node anchors; actual mesh
collision/clearance and mesh visualization. Portable calibrated poses/frustums are supported.
No arbitrary point attachment
or approved courtyard interpretation exists. Projection Error,
formal sampling/Coverage/collision protocol and baselines/ablations remain
open. Fake ADE epsilon=1e-6m and AABB tests do not certify a school scene or formal benchmark.
