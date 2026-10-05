# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-05。規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，
完成／驗證紀錄見 [WORK_LOG](WORK_LOG.md)，契約見 [DATA_SCHEMA](DATA_SCHEMA.md)
與 [INTERFACES](INTERFACES.md)。

### 目前狀態與續作入口

- Repository：`/Users/polalabear/Developer/amidst`；branch
  `codex/dataset-infrastructure`。續作先核對 HEAD／dirty state 與來源 hash。
- 通用 M0–M8 deterministic 閉環、camera extraction、producer-neutral aggregation、
  multi-gap Events、benchmark runner／MetricConfig／provider contract、GT isolation、
  fake／boundary／reporting regression 均已實作。Evidence 在 WORK_LOG，合成 fixtures
  在 [data/mock](../data/mock/README.md)；不等於正式 school benchmark 或研究驗收。
- 目前 scene 為使用者已授權補標並保存的 `school_v3.blend`；
  [保存後報告](../data/scene_audit/school_v3_semantic_validation.md) 與
  [具體待補位置](../data/scene_audit/school_v3_semantic_locations.md) 判定
  **NEEDS_HUMAN_FIXES**。新 source SHA 及原始備份證據見
  [update](../data/scene_audit/school_v3_semantic_update.json)。`.blend` gitignored，
  本機保存；Git 的 patch／audit／reports 綁定新 hash，不能套用 v2 authority。
- 三個明確不可走 AREA 已 EXCLUDED，兩個 stair AREA 改為 cross-floor 診斷。
  1F=25／2F=165 僅 PROPOSED。已補的 WALKABLE、19 個 OBSTACLE/BOTH 與六個
  stair annotations 都不能替代 physical／floor／camera-plane authority。
- 本輪只完成 semantic supplementation 與最小診斷 metadata 擴充；沒有開始
  geometry integration、collision pruning、benchmark、Agent／Phase 2 或 Case 4。
  未標記 group_*／Cube.* 不自動分類。續作需新的明確授權。

### 仍需人工與 geometry integration 處理

- 四個男女廁 AREA 被 BATHROOM obstacle footprint 蓋滿；保留已確認 OBSTACLE/BOTH
  角色，人工核對實際 blocking 佔地，不把整個 room 填回 WALKABLE。
- 教室／餐廳／部分 meeting room、AUDITORIUM_OFFICE 與 SIDE_ENTRANCE 門外 seams
  仍未連接。六組局部 room/corridor contact 不等於合法通行；雙側 probe 落地
  也不代表連到不同區域。PORTAL 位置／normal 例外及 obstacle aperture overlap
  見位置摘要；陽台目的地保持不可走。
- Stair A/B 缺可信連續 landing；A ENTRY 與 A/B EXIT 未接相應 floor。Slab opening／
  clearance 尚待人工審查。只有角色／方向 annotation，沒有 stair navigation edges。
  正式跨樓層 Case 4 暫緩，不以它展開 benchmark。
- WALL 標記仍缺。OBSTACLE 是原 footprint proxy，沒有已核准的 3D 高度／occlusion
  volume；人工核准 physical geometry、floor planes／例外與 camera-plane bindings。
  Elevator lobby/cabin/shaft 角色待定，沒有 elevator transition。
- Collision Top-K pruning ownership contract 仍 unresolved；現有 evaluation-only fake
  AABB detector 不代替 mesh certification。Graph WALKABLE 仍依 explicit route 設定；
  projected endpoints 需對齊 configured nodes，尚無 arbitrary-point snapping／connector。
- 後續 dataset／geometry／navigation／GT export／camera visibility 需共同 source/context
  binding；GT 不能進 inference。Projection Error 需獨立 evaluation；29 camera pose
  存在或校正矩陣比對不等於 plane mapping 或 error measurement。
- Rerun 已支援合成 waypoint graph、navigation anchors、portable calibrated poses／
  frustums；實際 mesh integration 與學校正式視覺化仍未完成。
- [Phase 1 Benchmark Protocol](PHASE1_BENCHMARK_PROTOCOL.md) 已定義 Cases 1–4、A–E
  baseline interfaces／single-factor ablation／六類 acceptance；正式 Coverage D／epsilon、
  K／採樣／physical tolerance／time policy 等保持 UNRESOLVED_RESEARCH_SETTING。
  Formal execution disabled；A–C 尚未實作，fake epsilon 不當作研究設定，epsilon=0 仍拒絕。
- `amidst.benchmark_report` 已能保留 missing／failed／NO_REFERENCE，輸出 charts／summary；
  目前 synthetic／plotting-only fixtures 不當作 Blender Cases 1–3 或 baseline 成果。
- 多段 gap 保持 BoundGapEvents。重疊 visibility arbitration 暫緩；尚無明確 missing-frame
  marker／coordinate-origin attestation schema，absence 不自動解讀成 occlusion／out-of-FOV。

以上是目前缺口，不是新的實作、render 或發布授權。

## English

Status date: 2026-10-05. Resume in `/Users/polalabear/Developer/amidst` on
`codex/dataset-infrastructure`, checking actual HEAD, dirty state and source identity.
Durable rules live in DEVELOPMENT_RULES; completed regression evidence belongs to WORK_LOG.
The generic deterministic loop, camera extraction, replaceable observation/aggregation
contracts, multi-gap Events, benchmark runner/MetricConfig, GT isolation, fake/boundary
validation and reporting are implemented. They do not constitute a formal school benchmark.

The current source is the explicitly authorized supplemented school_v3.blend. The
[post-save report](../data/scene_audit/school_v3_semantic_validation.md) concludes
NEEDS_HUMAN_FIXES; the [location summary](../data/scene_audit/school_v3_semantic_locations.md)
identifies concrete objects and required human actions. The source hash and verified backup
are bound in the update artifact. The ignored asset is saved locally; portable recipes and
audit/report evidence refer to the new source, without transferring v2 authority.
Three intentional nonwalkable areas are excluded; stair areas defer to cross-floor checks.
Floors 25/165 are only proposed. Semantic metadata and annotations do not grant physical,
floor or camera-plane authority. No geometry integration, collision pruning, benchmark,
Agent, Phase 2 or formal Case 4 is started. Unlabeled group_*/Cube.* are not classified.

Human work remains: correct fully blocking bathroom footprints while retaining OBSTACLE/BOTH
roles; confirm real doorway seams/portal positions/normals and aperture conflicts; provide
continuous stair landings and floor endpoint contacts plus opening/clearance review; mark
trusted walls and 3D collider/occlusion volumes; approve source-bound floor/camera planes and
exceptions; identify elevator lobby/cabin/shaft roles. Six local contacts are diagnostic,
not approved passage, and two-sided probes can land on the same small threshold.

Collision Top-K pruning remains unresolved; evaluation AABB checks do not certify meshes.
Graph routes and projected node anchors still require explicit configs, with no arbitrary
point attachment. Future dataset/geometry/navigation/GT/camera adapters need shared source
bindings; GT remains excluded from inference. Projection Error requires independent evaluation.
Portable Rerun poses/frustums are supported, while real mesh visualization remains pending.
The Phase 1 protocol specifies comparison interfaces and acceptance, but formal settings are
unresolved/execution disabled and A–C algorithms are not implemented. Zero epsilon remains
invalid. Comparison charts retain unavailable/failed/no-reference data without inventing
metrics. Multi-gap Events exist; overlapping visibility arbitration and explicit missing-frame
or coordinate-origin schemas remain deferred. These are gaps, not new implementation,
rendering or publication authorization.
