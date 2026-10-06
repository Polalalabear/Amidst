# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-06。規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，
完成／驗證紀錄見 [WORK_LOG](WORK_LOG.md)，契約見 [DATA_SCHEMA](DATA_SCHEMA.md)
與 [INTERFACES](INTERFACES.md)。

### 目前狀態與續作入口

- 最新使用者設定與 [scale measurement review](SCHOOL_V3_SCALE_REVIEW.md)：school v3
  診斷暫採 0.0247 m/BU，目前無獨立實測／設計尺寸；先確認 3–5 個 source-bound
  anchors，再用至少 2–3 組獨立尺寸交叉驗證。不得自動批准 scale、改正式 calibration、
  rescale 模型或回寫已完成 artifacts。匯入 SketchUp camera 零 active consuming refs，
  從研究 pipeline 忽略但保留原物件；電梯 NOT_APPLICABLE，historical AREA IDs 保留。
  後續只引用 canonical source＋hash；derived measurements 自動產生。

- Repository：`/Users/polalabear/Developer/amidst`。第一個semantic checkpoint保留在
  `codex/dataset-infrastructure`；第二個成功pilot checkpoint
  `fdf9e7e8f2dc695917ba42094a63cc06ca910963` 已push於
  `phase1/pilot-dataset-and-wall-inference`，origin SHA一致。
  Geometry checkpoint `bb66bb74a4a76430f6fa8f79672345385a79e3f0` 已 push 至
  `phase1/geometry-authority`，origin SHA 一致；由它建立目前
  `phase1/physical-authority-resolution`。核對 HEAD／dirty state 與 source hash，
  不 merge 回 checkpoint 或 downstream branch。恢復入口見[第一斷點](PHASE1_CHECKPOINT.md)／
  [第二斷點](PHASE1_PILOT_CHECKPOINT.md)／[geometry 斷點](PHASE1_GEOMETRY_CHECKPOINT.md)。
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
- Geometry authority [目前報告](../data/scene_audit/phase1_geometry_authority_20261006/authority.md)
  與 [portable snapshot](../data/scene_audit/phase1_geometry_authority_20261006/geometry.json)
  保留 1,572 個 WALL patches：73 HIGH_CONFIDENCE／1,422 HUMAN_REVIEW／77 REJECTED，
  0 APPROVED。28 PORTAL hard protection 下 accepted contact 為 0；不靠名稱猜 role，
  不填門洞、不降低閾值。19 OBSTACLE role APPROVED，但 footprint physical HUMAN_REVIEW；
  stair A/B connectivity／opening／clearance 仍 REVIEW，整體 **PROVISIONAL**。
  [Geometry Provider](GEOMETRY_PROVIDER.md) 唯讀、source-bound、platform-neutral；
  正式 physical consumer 必須通過 `require_approved_physics`，當前 snapshot 會 typed refuse。
  Inspection 的空 APPROVED collider 集合不能證明無碰撞。本輪不修改來源 `.blend`、
  GT isolation、Graph、ranking 或 benchmark，不執行正式 Cases 1–3。
- 最新 [physical blocker report](../data/scene_audit/phase1_physical_authority_20261006/resolution.md)
  以實際來源 mesh 重查：8 組 OBSTACLE／PORTAL 保持 REVIEW，其中兩組 MEETINGROOM
  可解釋為 annotation depth overlap；未縮 footprint、移 portal 或批准 volume。
  1F／2F source support 約 Z=20.07885／161.811096，與25／165不一致；38個 local scopes
  有完整量測例外，10個保留 complexity budget 與 partial ray evidence，沒有強制統一。
  A/B 未找到支援兩段 proxy endpoints 的共同 landing，opening／clearance／connectivity
  仍 REVIEW。[用途 scope contract](GEOMETRY_PROVIDER.md) 分別約束 pruning、collision-free、
  topology 與 physical metrics；body／portal／contact policy 的未核准項目保持 null。
  整體仍 PROVISIONAL，四個 formal gates 均拒絕，尚不可開始正式 collision hard-pruning。
- 歷史 checkpoint `91f4ea600805739aa9659dfef6a381d71be9a692` 後的 extraction／
  [candidate report](../data/scene_audit/phase1_wall_candidates_20261005.md) 與
  [saved marking report](../data/scene_audit/phase1_wall_markings_20261005.md) 已完成：
  曾將 81 個 WALL surface patches 標在本機衍生 scene，1,491 個候選留 HUMAN_REVIEW；
  這是前一 marking 版本，不是目前 physical APPROVED 數量。
  `blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend` 保存／重開驗證
  原始objects與physical geometry未變，28 PORTAL實際相交為0；不改原source或整個group_*。
  WALL為annotation-only selections，未核准movement/navigation collider。
- 2026-10-05 pilot 只生成一組 `data/pilot/phase1_wall_pilot_20261005/office/`
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
  已停止於這一條existing trajectory，不生成新dataset、不開始formal Cases1–3。

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
- 最新 authority 有 1,422 個 WALL patches 需 review、77 個不能升級 WALL；
  11 個 seed 降級（5 個 continuous WALKABLE intrusion、6 個 actual support 不足），
  3 個原 review patches 升為 HIGH_CONFIDENCE。衍生標記未回寫，尚未接入 formal geometry/navigation。
  OBSTACLE 是原 footprint proxy，沒有已核准的 3D 高度／occlusion volume；physical
  geometry、floor planes／例外與 camera-plane bindings 待核准。使用者已確認只有 stairs、
  沒有 elevator；`AREA_*_ELEVATOR` 只是歷史命名，不建立 transition。
- 19 個 OBSTACLE 與 PORTAL 有 8 個 conflict pairs；WALKABLE overlap 超過既有
  contact ratio 的 pair 為 0。Stair A/B PATH 各有兩個 components，nearest 3D gap
  為 4.769402／4.896199（保留現有 1 m／BU conversion，非另行尺度核准）；
  ENTRY／EXIT 接地、landing／opening／clearance 與 floor authority 仍待人工證據。
- Collision Top-K pruning ownership contract 仍 unresolved；現有 evaluation-only fake
  AABB detector 不代替 mesh certification。Graph WALKABLE 仍依 explicit route 設定；
  projected endpoints 需對齊 configured nodes，尚無 arbitrary-point snapping／connector。
- Pilot source/context、GT／camera／visibility／render binding 與獨立投影驗證已完成，
  純2D與strict metadata context現可經ordinary downstream consumers形成小型閉環；
  GT不能進inference。正式adapters仍需共同authority。Downstream diagnostic ADE/FDE為
  0.000708092424／0.000280838027BU，minADE@3／minFDE@3相同；Coverage@3在ADE<0.02BU
  下成立，僅evaluation判定，不以GT選候選、不認證formal epsilon或metric scale。
  既有pilot forward residual最大0.000314545px、固定診斷plane inverse residual最大
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

Latest user update: see the [scale measurement review](SCHOOL_V3_SCALE_REVIEW.md).
School-v3 diagnostics propose 0.0247 m/BU without independent real dimensions; confirm
3–5 source-bound anchors and cross-check at least 2–3 independent dimensions before
architectural-scale approval. Preserve the model, formal calibration and completed artifacts.
The imported SketchUp camera has zero active consuming references and may be ignored;
retain all 29 CAM cameras and the source object. Elevator is NOT_APPLICABLE, historical
AREA IDs remain, and future active references use canonical source plus hashes.

Status date: 2026-10-06. The first semantic checkpoint remains on
`codex/dataset-infrastructure`; the successful-pilot checkpoint
`fdf9e7e8f2dc695917ba42094a63cc06ca910963` is published on
`phase1/pilot-dataset-and-wall-inference` with identical origin SHA. Resume only on
`phase1/physical-authority-resolution`, created from the published geometry checkpoint
`bb66bb74a4a76430f6fa8f79672345385a79e3f0` on `phase1/geometry-authority`, whose live
origin SHA matches. Check HEAD/dirty state/source identity;
do not merge into checkpoint or downstream branches. [First](PHASE1_CHECKPOINT.md) and
[second checkpoint records](PHASE1_PILOT_CHECKPOINT.md), plus the
[geometry checkpoint](PHASE1_GEOMETRY_CHECKPOINT.md), bind recovery and local assets.
Durable rules live in DEVELOPMENT_RULES; completed regression evidence belongs to WORK_LOG.
The latest [physical blocker report](../data/scene_audit/phase1_physical_authority_20261006/resolution.md)
keeps all eight obstacle/portal pairs REVIEW, with two meeting-room annotation-depth
overlaps explained without scene edits. Actual floor support near20.07885/161.811096
does not match proposed25/165:38 local scopes have measured exceptions, ten retain
complexity limits and partial rays. A/B have no shared source-supported landing near
the proxy joins; opening, clearance and full connectivity remain REVIEW. Purpose-specific
provider scopes and nullable body/portal/contact policy preserve typed formal refusal.
Overall remains PROVISIONAL; formal collision hard-pruning is not ready.
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
floor or camera-plane authority. The current [authority report](../data/scene_audit/phase1_geometry_authority_20261006/authority.md)
retains 1,572 WALL patches: 73 HIGH_CONFIDENCE, 1,422 HUMAN_REVIEW, 77 REJECTED and
0 APPROVED. Eleven seeds are downgraded (five continuous WALKABLE intrusions and six
insufficient actual support); three former review patches become HIGH_CONFIDENCE.
All 28 portals remain hard protected, with zero accepted contacts. Nineteen OBSTACLE
roles are APPROVED, while their footprint physical support remains HUMAN_REVIEW.
Stair connectivity/opening/clearance and overall physical validity remain PROVISIONAL.
The [read-only provider](GEOMETRY_PROVIDER.md) is platform-neutral/source-bound;
`require_approved_physics` refuses the current incomplete scope. An empty inspection
collider set never certifies clearance. Source assets, GT isolation, Graph, ranking and
benchmark semantics stay unchanged; no formal Cases 1–3 are run.

Historical post-checkpoint extraction and saved marking reports
recorded 81 WALL surface patches, retaining 1,491 HUMAN_REVIEW patches. These are prior
marking counts, not current physical approvals. The ignored
blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend stores exact
existing face selections with annotation-only WALL semantics. Independent reopening
preserves original objects/physical geometry and all 28 portals, with zero actual
annotation intersections. Original source and whole mixed group_* objects stay unchanged;
navigation/movement colliders remain unapproved.
Exactly one ignored PILOT / SYNTHETIC SAMPLE was generated on 2026-10-05 at
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
standaloneHTML is produced but not UI-verified. Work stops here on one existing route.

Human work remains: correct fully blocking bathroom footprints while retaining OBSTACLE/BOTH
roles; confirm real doorway seams/portal positions/normals and aperture conflicts; provide
continuous stair landings and floor endpoint contacts plus opening/clearance review; review
remaining WALL candidates and 3D collider/occlusion volumes; approve source-bound floor/camera
planes and exceptions. The user confirms stairs only and no elevator; historical
AREA_*_ELEVATOR names never create an elevator transition. Six local contacts are diagnostic,
not approved passage, and two-sided probes can land on the same small threshold.
Current obstacle checks retain eight PORTAL conflict pairs and zero WALKABLE overlaps
above the existing contact ratio. A/B PATH each has two components, with nearest 3D
gaps of 4.769402/4.896199 under the existing 1 m/BU conversion; this does not approve
architectural scale. Landing, entry/exit floor connections and opening/clearance remain REVIEW.

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
