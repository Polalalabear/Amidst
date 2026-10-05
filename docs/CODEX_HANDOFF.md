# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-05。規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，
完成／驗證紀錄見 [WORK_LOG](WORK_LOG.md)，契約見 [DATA_SCHEMA](DATA_SCHEMA.md)
與 [INTERFACES](INTERFACES.md)。

### 目前狀態與續作入口

- Repository：`/Users/polalabear/Developer/amidst`。Phase 1 大斷點保留在
  `codex/dataset-infrastructure`；後續只在 `phase1/pilot-dataset-and-wall-inference`。
  [Checkpoint record](PHASE1_CHECKPOINT.md) 包含驗證、來源快照與回復入口。
  續作先核對 HEAD／dirty state 與來源 hash；不 merge 回 checkpoint branch。
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
- 新授權的 geometry-derived WALL extraction 已完成：
  [report](../data/scene_audit/school_v3_wall_candidates.md)／
  [sidecar](../data/scene_audit/school_v3_wall_candidates.json) 標記 81 個 WALL surface
  patches（7 source objects），1,491 patches 留 HUMAN_REVIEW（674 objects，totals 重疊）。
  28 PORTAL 的自動確認牆面相交為 0；不改 source、不分類整個混合 object。
- 本機 ignored `data/pilot/school_v3_multisite_20261005/` 已完成同一 school_v3 的
  教室／禮堂／辦公區三組 **PILOT / SYNTHETIC SAMPLE**，150 timestamps／300 PNG
  全數獨立驗證成功。先看 root `comparison.md`／`review.html`，各子目錄的
  `dataset.json`、五張代表 montages 與同步 preview。原 corridor pilot 保留作比較。
  教室是中心點可見對照（完整 body 全程有邊界裁切）；禮堂只有一個且仍有 partial body
  的 GAP 樣本；辦公區24個 GAP 中19個完全隱藏，最適合目前 point occlusion 檢查。
  禮堂與辦公區共用既有 FRONT／REAR cameras，不是三套獨立相機配置。
  已停止於這三組額外 pilot；未開始 formal geometry/navigation integration、collision
  pruning、benchmark、Agent／Phase 2 或 Case 4。

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
- WALL sidecar 尚未接入 formal geometry/navigation，仍有 1,491 候選需 review。
  OBSTACLE 是原 footprint proxy，沒有已核准的 3D 高度／occlusion volume；physical
  geometry、floor planes／例外與 camera-plane bindings 待核准。使用者已確認只有 stairs、
  沒有 elevator；`AREA_*_ELEVATOR` 只是歷史命名，不建立 transition。
- Collision Top-K pruning ownership contract 仍 unresolved；現有 evaluation-only fake
  AABB detector 不代替 mesh certification。Graph WALKABLE 仍依 explicit route 設定；
  projected endpoints 需對齊 configured nodes，尚無 arbitrary-point snapping／connector。
- Pilot source/context、GT／camera／visibility／render binding 與獨立投影驗證已完成，
  純 2D `observations.json` 另存，GT 不能進 inference。正式 adapters 仍需共同 authority。
  三組新 pilot forward residual 最大 0.000638311px、固定診斷 plane inverse residual 最大
  0.001787566 scene units，沒有異常；這不是 formal floor/camera-plane 認證。實際地面
  Z≈20.07885，比 WALKABLE Z=25 低 4.92115；marker plane Z≈75.12885。
  METRIC／1m-per-unit 有建築尺度疑義，不猜測換算比例。完整 generation 待 image policy、
  physical scale 與正式 authority；marker 裁切、地板明暗塊、短 GAP／恢復視窗與 camera
  coverage 限制已在 comparison 記錄，agent 判斷不替代人類 authority。
  點可見性不當作整個人體 CV detection。
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

Status date: 2026-10-05. The Phase 1 checkpoint is preserved on
`codex/dataset-infrastructure`. Resume in `/Users/polalabear/Developer/amidst` only on
`phase1/pilot-dataset-and-wall-inference`, checking actual HEAD, dirty state and source
identity; do not merge back into the checkpoint branch. The
[checkpoint record](PHASE1_CHECKPOINT.md) binds validation and the local source snapshot.
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
floor or camera-plane authority. Authorized WALL extraction labels 81 connected surface
patches in a source-bound sidecar, retaining 1,491 HUMAN_REVIEW patches (7 automatic /
674 review objects, with overlap). All 28 PORTALs are protected; automatic aperture
intersections are zero. Whole mixed objects and saved source labels are unchanged.
The local ignored `data/pilot/school_v3_multisite_20261005/` contains three additional
PILOT / SYNTHETIC SAMPLE locales within the same school_v3 asset: classroom, auditorium
and office, with all 150 timestamps / 300 PNGs independently verified. Review comparison.md
and review.html, then each site's dataset, five representative montages and synchronized
preview. The original corridor pilot is retained as a comparison reference. Classroom is a
center-point control with body clipping in all visible images; auditorium has one partially
visible GAP sample; office has 24 GAP samples, 19 fully hidden, making it the strongest
current point-occlusion sample. Auditorium/office reuse the existing FRONT/REAR cameras,
not separate installations. Work stops at these three additional pilots; no formal
geometry/navigation integration, collision pruning, benchmark, Agent, Phase 2 or Case 4
is started.

Human work remains: correct fully blocking bathroom footprints while retaining OBSTACLE/BOTH
roles; confirm real doorway seams/portal positions/normals and aperture conflicts; provide
continuous stair landings and floor endpoint contacts plus opening/clearance review; review
remaining WALL candidates and 3D collider/occlusion volumes; approve source-bound floor/camera
planes and exceptions. The user confirms stairs only and no elevator; historical
AREA_*_ELEVATOR names never create an elevator transition. Six local contacts are diagnostic,
not approved passage, and two-sided probes can land on the same small threshold.

Collision Top-K pruning remains unresolved; evaluation AABB checks do not certify meshes.
Graph routes and projected node anchors still require explicit configs, with no arbitrary
point attachment. Pilot source/context bindings, render hashes and separate 2D/GT exports
are verified, while formal adapters still need shared authority. GT stays excluded from
inference. The three new pilots' forward/inverse errors are at most 0.000638311 pixels / 0.001787566
scene units, with no unexpected failures; the static landmark plane is diagnostic only.
Actual 1F support is Z≈20.07885, 4.92115 below the WALKABLE annotation; landmark plane
Z≈75.12885. Declared metric scale is not certified architectural scale. Full generation
awaits image policy and physical scale/plane authority. Boundary clipping, floor appearance,
short gap/recovery windows and limited camera coverage are documented in comparison;
agent judgments do not grant human authority. Point visibility is not whole-body CV.
Portable Rerun poses/frustums are supported, while real mesh visualization remains pending.
The Phase 1 protocol specifies comparison interfaces and acceptance, but formal settings are
unresolved/execution disabled and A–C algorithms are not implemented. Zero epsilon remains
invalid. Comparison charts retain unavailable/failed/no-reference data without inventing
metrics. Multi-gap Events exist; overlapping visibility arbitration and explicit missing-frame
or coordinate-origin schemas remain deferred. These are gaps, not new implementation,
rendering or publication authorization.
