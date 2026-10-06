# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-06。規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，
完成／驗證紀錄見 [WORK_LOG](WORK_LOG.md)，契約見 [DATA_SCHEMA](DATA_SCHEMA.md)
與 [INTERFACES](INTERFACES.md)。

### 目前狀態與續作入口

- Repository：`/Users/polalabear/Developer/amidst`。第一個semantic checkpoint保留在
  `codex/dataset-infrastructure`；第二個成功pilot checkpoint
  `fdf9e7e8f2dc695917ba42094a63cc06ca910963` 已push於
  `phase1/pilot-dataset-and-wall-inference`，origin SHA一致。
  第三個downstream checkpoint `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` 已push於
  `phase1/pilot-downstream-reconstruction`，origin SHA一致。現在只在
  `phase1/pilot-robustness-validation` 的隔離worktree
  `/Users/polalabear/.codex/worktrees/pilot-robustness-validation/amidst`；
  並行geometry-authority工作保留於shared checkout，不混入robustness。
  核對HEAD／dirty state與source hash，不merge回checkpoint。恢復入口見
  [第一](PHASE1_CHECKPOINT.md)／[第二](PHASE1_PILOT_CHECKPOINT.md)／
  [第三斷點](PHASE1_DOWNSTREAM_CHECKPOINT.md)。
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
- Checkpoint `91f4ea600805739aa9659dfef6a381d71be9a692` 後新 extraction／
  [candidate report](../data/scene_audit/phase1_wall_candidates_20261005.md) 與
  [saved marking report](../data/scene_audit/phase1_wall_markings_20261005.md) 已完成：
  81個WALL surface patches正式標在本機衍生scene，1,491個候選留HUMAN_REVIEW。
  `blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend` 保存／重開驗證
  原始objects與physical geometry未變，28 PORTAL實際相交為0；不改原source或整個group_*。
  WALL為annotation-only selections，未核准movement/navigation collider。
- 本次只生成一組新 `data/pilot/phase1_wall_pilot_20261005/office/`
  **PILOT / SYNTHETIC SAMPLE**：10秒、5FPS、50timestamps／100PNG全部驗證成功。
  原pose的AUDITORIUM_FRONT／REAR cameras，office metadata路線160scene units，
  visible→GAP→visible成立；24個point GAP中19個marker全隱藏、5個partial body。
  先看`sample_report.md`／`review.html`、五張代表montages與同步preview，
  dataset與plan同時綁定衍生SHA及未變原source。原先corridor／三區pilot保留作歷史比較。
  原pilot資料與source保持不變；正式geometry/navigation、collision pruning、benchmark、
  Agent／Phase2或Case4未開始，不擴充完整dataset。
- 現有office一條trajectory的bounded downstream閉環已驗證，入口為本機ignored
  `data/pilot/phase1_downstream_20261005/verification.md`與`run_01/`。
  100records→26inverse PROJECTED＋74null GAP→兩段Observation→一個4.0–9.0s Event→
  3candidate routes／6timing hypotheses／COMPLETE；24個GAP samples為4.2–8.8s。
  `run_pilot_downstream.py`只讀純2D與strict context，三條configured local routes取
  projected endpoints與明示offset，不讀GT／mixed export／plan。Topology與collision
  PARTIAL／PROVISIONAL，沒有升格WALL或完整school navigation authority。
  Repeated run與GT poison的10份inference artifacts逐byte一致；GT只在結果保存後evaluation。
  Rerun／3D PNG保留observed、全部Top-K與獨立GTdebug；HTML已產出、UI未驗證。
  這一條existing trajectory的結果保留於第三checkpoint；controlled robustness如下。

- Controlled robustness已停在固定9scenarios／3existing trajectories；入口為本機ignored
  `data/pilot/phase1_robustness_20261006/robustness_summary.md`／`verification.json`。
  Office中GAP與corridor長GAP完整閉環；compressed office短GAP由1route到3feasible
  branches，Top-K保持多解。±0.25px noise仍COMPLETE但ADE/FDE為1.43914081/
  2.54900313BU、Coverage@1/2/3false；saved projected點對比不用GT就看出noise放大。
  Native auditorium短GAP的same-camera topology、camera removal min2input contract、
  speed31短GAP search空解均明示首個失效層，不補造prediction／metrics。四個失敗case
  metrics/Coverage為null；27次baseline/repeat/poison inference逐byte一致。
  Nine readableRRDs與PNGoverview含acceptedobserved、全部inferred與獨立GTdebug；
  invalidcontext只diagnostic，±1BU支路全圖接近重疊需zoom。Physical仍PARTIAL/PROVISIONAL，
  沒改core/formalbenchmarksemantics，不新增physicaldataset／render，完成後停止。

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
- 衍生scene WALL markings 尚未接入 formal geometry/navigation，仍有 1,491 候選需 review。
  OBSTACLE 是原 footprint proxy，沒有已核准的 3D 高度／occlusion volume；physical
  geometry、floor planes／例外與 camera-plane bindings 待核准。使用者已確認只有 stairs、
  沒有 elevator；`AREA_*_ELEVATOR` 只是歷史命名，不建立 transition。
- Collision Top-K pruning ownership contract 仍 unresolved；現有 evaluation-only fake
  AABB detector 不代替 mesh certification。Graph WALKABLE 仍依 explicit route 設定；
  projected endpoints 需對齊 configured nodes，尚無 arbitrary-point snapping／connector。
- Pilot source/context、GT／camera／visibility／render binding 與獨立投影驗證已完成，
  純2D與strict metadata context現可經ordinary downstream consumers形成小型閉環；
  GT不能進inference。正式adapters仍需共同authority。Downstream diagnostic ADE/FDE為
  0.000708092424／0.000280838027BU，minADE@3／minFDE@3相同；Coverage@3在ADE<0.02BU
  下成立，僅evaluation判定，不以GT選候選、不認證formal epsilon或metric scale。
  本次pilot forward residual最大0.000314545px、固定診斷plane inverse residual最大
  0.001615262scene units，沒有異常；這不是formal floor/camera-plane認證。實際地面
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

Status date: 2026-10-06. The first semantic checkpoint remains on
`codex/dataset-infrastructure`; the successful-pilot checkpoint
`fdf9e7e8f2dc695917ba42094a63cc06ca910963` is published on
`phase1/pilot-dataset-and-wall-inference` with identical origin SHA. The downstream
checkpoint `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` is published
on `phase1/pilot-downstream-reconstruction` with identical live origin SHA. Resume only
on `phase1/pilot-robustness-validation` in the isolated managed worktree; parallel
geometry-authority files/shared checkout are preserved. Check HEAD/dirty/source identity,
and do not merge into checkpoints. [First](PHASE1_CHECKPOINT.md),
[second](PHASE1_PILOT_CHECKPOINT.md) and [third](PHASE1_DOWNSTREAM_CHECKPOINT.md)
records bind recovery and local assets.
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
floor or camera-plane authority. Post-checkpoint extraction and saved marking reports
confirm 81 WALL surface patches, retaining 1,491 HUMAN_REVIEW patches. The ignored
blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend stores exact
existing face selections with annotation-only WALL semantics. Independent reopening
preserves original objects/physical geometry and all 28 portals, with zero actual
annotation intersections. Original source and whole mixed group_* objects stay unchanged;
navigation/movement colliders remain unapproved.
Exactly one new ignored PILOT / SYNTHETIC SAMPLE at
data/pilot/phase1_wall_pilot_20261005/office/ has all 50 timestamps / 100 PNGs verified:
10s at 5 FPS, existing AUDITORIUM_FRONT/REAR poses and a 160-unit 1F office metadata
route. Visible→GAP→visible succeeds, with 24 landmark GAP samples, 19 fully hidden
and 5 partially visible. Review sample_report.md, review.html, five representative
montages and synchronized preview. Export/plan lineage binds the actual derived asset
and preserved original source. Earlier corridor/three-locale pilots remain historical
references. Original pilot/source remain unchanged; no full dataset expansion, formal
geometry/navigation integration, collision pruning, benchmark, Agent, Phase2 or Case4.
One existing office trajectory now passes bounded downstream verification at
data/pilot/phase1_downstream_20261005/verification.md and run_01/:100raw records,
26inverse projections/74nullGAPs, two Observations, one4.0–9.0s Event and3routes/
6timing hypotheses with COMPLETE termination. Missing timestamps remain4.2–8.8s.
The consumer reads only strict2D/context inputs; projected endpoint/configured-offset
routes have partial/provisional topology and collision validity. No GT/mixed export/
plan enters inference, and no school/WALL authority is promoted. Two runs and GT poison
have byte-identical10inference artifacts. GT loads only after saved inference for
evaluation/debug. Rerun and inspected3DPNG retain observed/allTop-K/separateGT;
standalone HTML is produced but not UI-verified. The original single-route run remains
at its checkpoint. Controlled robustness
now stops at nine cases over three existing trajectories, documented in local ignored
data/pilot/phase1_robustness_20261006/robustness_summary.md. Medium/long cases complete;
Compressed short controls retain one versus three feasible routes. Pixel noise preserves inference
completion but degrades metrics/Coverage. Native same-camera topology, single-camera
input and infeasible speed expose separate failed layers with honest nullmetrics.
All 27 inference runs are repeat/GT-poison invariant; nine PNG/Rerun presentations verified.
Physical validity stays partial/provisional, core/formal semantics unchanged, no new
physical dataset/render, and no formal Cases1–3.

Human work remains: correct fully blocking bathroom footprints while retaining OBSTACLE/BOTH
roles; confirm real doorway seams/portal positions/normals and aperture conflicts; provide
continuous stair landings and floor endpoint contacts plus opening/clearance review; review
remaining WALL candidates and 3D collider/occlusion volumes; approve source-bound floor/camera
planes and exceptions. The user confirms stairs only and no elevator; historical
AREA_*_ELEVATOR names never create an elevator transition. Six local contacts are diagnostic,
not approved passage, and two-sided probes can land on the same small threshold.

Collision Top-K pruning remains unresolved; evaluation AABB checks do not certify meshes.
Graph routes and projected node anchors still require explicit configs, with no arbitrary
point attachment. Strict pilot2D/context can now use ordinary consumers for the bounded
loop; formal adapters still require shared authority. Diagnostic downstream ADE/FDE and
minADE@3/minFDE@3 are0.000708092424/0.000280838027native units; Coverage@3true at
ADE<0.02units is evaluation-only, not formal epsilon/scale authority or GT selection.
GT stays excluded from inference. This pilot's forward/inverse errors are at most
0.000314545 pixels / 0.001615262
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
