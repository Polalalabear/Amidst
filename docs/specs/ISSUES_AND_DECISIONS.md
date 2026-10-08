## Unified Amidst web workbench / 統一 Amidst 網頁工作台

問題：展示、調查、測試及人審若各自建立頁面，場景更換時會重做介面，
角色限制、時間軸、證據與審查流程也容易分散。

採用解法：依使用者 2026-10-08 明確指示，以已交付的
[`frontend/workbench/`](../../frontend/workbench/index.html) 與
[共用工作台](../engineering/SHARED_WORKBENCH.md)為主要網頁；既有及後續需要頁面展示的功能
均接入共用導覽、元件、場景接口及 human 審查流程。本機主入口為 8016，桌面版維持本輪範圍。
研究／管理決定權限，展示／測試／人審決定工具；產品輸入模式與凍結階段另行綁定。

狀態：**ADOPTED / MIGRATION_PARTIAL**。工作台雙角色、雙場景及標註版本流程已交付；
既有 8010／8012／8020 頁面的全部功能尚未遷入。既有 product 的索引、調查、影片、
案例、報告與 review 由原後端重用，逐項遷入工作台；來源、原接口及歷史 receipt 保留。
工作台的 server-owned session 必須綁定已註冊 scene/run/mode/stage 再呼叫產品服務，
管理 allowlist、GT 隔離、有限鏡頭／時間窗及多解持續有效。
場景 annotation、事件判定與調查報告 review 分別保存並綁定各自來源版本。
此決策不核准未知場景語意、不解除 formal gates，也不把舊頁面驗證冒充遷移驗證。

Decision: The user's 2026-10-08 instruction adopts `frontend/workbench/` as the common
desktop web entry for all existing and future presentation, investigation, tests and human
review. Reuse scene adapters, navigation, components and server-owned role enforcement.
Migration remains partial: older engineering pages and their backend/contracts/history are
preserved until each capability is integrated and validated. Keep product mode/stage bindings,
local retrieval, competing hypotheses, separate review records and GT isolation intact.

## Approved school v3 architectural scale / school v3 建築尺度核准

2026-10-06 explicit user approval: **1 BU = 0.0247 m** is the defined Phase 1
research-model architectural scale, not an estimate inferred from meshes. Authority is
**APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING**. The source-bound
[approval record](../../configs/architectural_scale_school_v3.json) identifies this decision;
[measurements](SCHOOL_V3_SCALE_REVIEW.md) are sanity-check evidence. External dimensions
are not an approval prerequisite and source geometry is never rescaled.

使用者正式核准 **1 BU = 0.0247 m**，作為明確研究模型設定；architectural scale
為 APPROVED，不再要求外部尺寸重新推導。Mesh 量測僅 sanity check，不自動核准
floor、stair、obstacle volume、body／clearance policy。原 `.blend` geometry 保持不變。
BU 坐標保留；長度／半徑／高度／淨空／接觸容差乘尺度，面積／體積用平方／立方，
速度 BU/s 乘尺度；SI physical policy 供 native geometry 時除尺度。Timestamp、normal、
角度、ratio／count 不換算。進入既有 core 的完整空間輸入須先一致正規化成公尺。
ADE／FDE meter reporting 保留原 BU 與不可用值，不重算 Coverage 或偷改 epsilon。
正式 schemas 與 Graph／Top-K 不修改；舊 calibration／pilot／benchmark／snapshots 的
原始契約與 provenance 保留，不能把它們的 Literal[1] 當新 architectural authority。

Imported cameras may be ignored only after zero active consuming references are established;
inventory/exclusion/history mentions are retained. Elevator is `NOT_APPLICABLE`; existing
`AREA_*_ELEVATOR` IDs are preserved and establish no transition. Keep all `group_*`/`Cube.*`
objects without name-based authority. New active references use canonical source plus hashes;
historical identical artifacts and provenance are retained.

匯入 camera 先查 active consuming references，零引用才忽略；inventory／排除／歷史紀錄
保留。電梯 NOT_APPLICABLE，保留既有 AREA IDs，不建立 transition。`group_*`／`Cube.*`
不改名、不刪除、不按名稱定角色。後續 active 資料採 canonical source＋hash reference；
尺寸與重心等衍生資訊自動產生，不人工維護重複表。

## Approved physical policy and scoped geometry authority / 已核准物理政策與局部幾何權威

Source enclosure ownership remains **UNRESOLVED**: `group_0 / component-00000000` has
zero boundary edges but 1,456 degenerate triangles and 11,635 non-manifold edges.
It cannot establish a usable solid interior, nor be silently interpreted as surface-only
by its name. All five searched complete local islands remain REVIEW. Face/component
binding or traceable derived collider repair is required before complete certification;
this does not prevent positive rejection against the separately approved 58 components.

未分類 source component 的 surface／solid ownership 仍 **UNRESOLVED**；不可只因
boundary-edge=0 或名稱把它當可用 closed volume，也不可因未見 triangle contact 就
略過 enclosure uncertainty。五個完整局部 scope 皆 REVIEW；仍需明確 face/component
binding 或可追溯 derived collider evidence。58 個已批准 components 的正向拒絕可獨立
驗證，但正式局部／inference pruning 未開放，完整 physical island 目標尚未達成。

Contact tolerance applies once against actual source support height, including analytic
segment partitions; nominal-plane and footpoint bands cannot add to twice the tolerance.
Local certificates use the intersection of actual contact bands. This repairs an
implementation bug without changing the approved 1 mm policy or clearance threshold.
Collision consumers also refuse trajectories outside their approved floor-plane scope.

2026-10-06 explicit user approval: the source-bound
[policy](../../configs/physical_authority_policy_school_v3.json) and
[runtime contract](../../configs/physical_policy_runtime_school_v3.json) define an upright
cylinder at a floor-contact footpoint: radius 0.30 m, height 1.70 m, extra body clearance
0.05 m, portal margin 0.05 m per side and 0.10 m above, and obstacle-contact tolerance
0.001 m. Minimum-clearance equality passes; obstacle contact is inclusive. Body and portal
clearance combine by maximum, never double addition. Only legal APPROVED support contact
is exempted from obstacle contact; penetration remains invalid. These are approved physical
model settings, not new MetricConfig definitions or formal benchmark acceptance thresholds.

使用者另外核准上述 physical policy，不再將人體／淨空數值列為待選。
Trajectory reference 是接地 footpoint；合法核准 support contact 可通行，不能穿入地板。
Portal 與 body margin 取較嚴的最大值，避免同一淨空需求重複相加。全數 SI quantities
由同一 APPROVED 0.0247 m/BU authority 換算，原 source vertices／歷史 BU provenance 保留。
這項決策不改 MetricConfig、Graph／Top-K、ranking 或 GT isolation。

Decision: WALKABLE represents raw source support. Union same-floor supported domains
before erosion and verify clearance against the original boundary; do not inset adjacent
annotation objects separately. Navigation is allowed only within approved WALKABLE/STAIR
support. Other space is forbidden for navigation without acquiring WALL or visibility
occlusion ownership. BIDIRECTIONAL is the intended stair policy; actual cross-floor travel
still requires source support, opening and full-body evidence in both directions.

決策：同層 actual support 先 union 再 erosion，避免逐 annotation inset 製造假裂縫；
WALKABLE／STAIR 外禁止導航，不把未知空間改成牆或 occluder。樓梯預設可雙向通行是
policy，仍須逐方向證明支撐、開口、人體淨空；不得用 ENTRY／PATH／EXIT proxy 補造 landing。

Decision: physical approval is source-bound and component/domain-specific. Approved closed
components do not approve their complete obstacle object; approved supported subdomains do
not approve whole-floor geometry. Unclassified source geometry may block certification but
never gains a semantic role from names or proximity. The
[current evidence](../../data/scene_audit/phase1_physical_policy_approval_20261006/manifest.json)
and [experiment record](../history/EXPERIMENT_LOG.md) retain exact source/face IDs and unresolved reviews.

決策：closed component 與 supported 子域分別核准，不擴成 whole obstacle／whole floor。
未知 geometry 可以阻擋認證，但不能因需要 collider 而從名稱／鄰近關係升級。
HIGH_CONFIDENCE WALL 與 REVIEW portal／stair 均保留其權威等級；本輪未改原 `.blend`。

The additive physical consumer hard-prunes known source-bound collision/clearance violations
before final K truncation, preserving candidate relative order and IDs without GT or scoring.
Distance or budget uncertainty is explicit UNVALIDATED. A partial collider scope never proves
free space. A local collision/topology certificate instead requires complete source screening
inside an explicitly bounded footpoint domain and refuses validation outside that domain.
Local-scope result: **0 complete physical islands; 5 searched regions remain REVIEW (unclassified group_0 enclosure / degenerate source geometry)**. Global `physical_complete=false` remains
fail-closed; complete school physical validity, unresolved portals/stairs, camera-plane binding
and formal metric/baseline decisions remain separate prerequisites for Cases 1–3.

新增 consumer 在 final K 截斷前 hard-prune 已知 source-bound collision／clearance violation，
保留順序與 IDs，不改 score／GT；不確定距離與 budget 明列 UNVALIDATED。
Partial collision scope 不證明無碰撞；local certificate 必須完整檢查限定域 source geometry，
離開域就拒絕。Local-scope 結果：**0 complete physical islands; 5 searched regions remain REVIEW (unclassified group_0 enclosure / degenerate source geometry)**。
全域 snapshot 仍 `physical_complete=false`，不以局部批准跳過 complete school authority、
門洞／樓梯、camera-plane 或正式 metric／baseline 設定；本輪不開始 Cases 1–3／Agent。

## Historical scene unit-to-metre convention / 既有 checkpoint 的單位換算

Decision: Use `meters_per_blender_unit = 1.0`: one Blender unit is one metre, as confirmed by the user. Preserve the scene coordinates for Phase 1 distance, speed, and error calculations.

決策：依使用者確認，1 Blender unit = 1 公尺。Phase 1 距離、速度與誤差計算沿用原始場景座標，不套用額外縮放。

## Research camera selection / 研究用攝影機選擇

Decision: Use only the 29 `CAM_*` camera objects. Exclude `skp_camera_Last_Saved_SketchUp_View` from simulation and projection; its lens is non-finite. Preserve all camera objects in the original `.blend`.

決策：只使用 29 台 `CAM_*` 攝影機。焦距為非有限值的 `skp_camera_Last_Saved_SketchUp_View` 不參與模擬與投影；原始 `.blend` 的攝影機物件保留。

## Appearance assets in Phase 1 / Phase 1 材質與紋理

Decision: Use texture-free, opaque neutral gray surface materials for Phase 1 synthetic rendering. Apply a temporary view-layer override in the simulation process; restore original overrides afterward. Keep source material slots, shader graphs, UVs and image assets intact. Lighting/world settings remain a separate rendering concern.

決策：Phase 1 合成渲染採用無紋理、不透明的中性灰表面材質，以模擬程序內的暫時 View Layer Override 套用，結束後恢復。來源材質槽、shader、UV 與影像資產保留；燈光與 World 設定另行處理。

## Floor candidates do not establish stair connectivity / 地板候選不等於樓梯連通

Decision: Infer floor-surface candidates from evaluated mesh geometry, not object names alone. The two school stair annotation regions lack a mesh-supported continuous ascent; fail closed on school cross-floor traversal until a valid stair representation is confirmed. Continue generic algorithms with explicitly synthetic fixtures and parameterized stair paths. Never use annotation boxes as collision surfaces or invent school connections through floor slabs; preserve the source `.blend`.

決策：以求值後的 Mesh 幾何辨識地板候選，不只依賴名稱。school 兩處樓梯標示區未找到實體 Mesh 支持的連續上升路徑；在有效表示確認前，不開放 school 跨樓層通行。通用演算法以明確標記的合成 fixture 與參數化樓梯路徑繼續驗證。語意 box 不當作碰撞面，也不虛構穿越 school 樓板的連接；原始 `.blend` 保留。

## Research asset isolation / 研究資產隔離

Decision: Keep `blender/school_v2.blend` immutable. Use a separate local, Git-ignored research copy at `blender/working/school_v2_research.blend`. Creating the copy does not approve stair geometry or cross-floor connectivity; record approved derivative changes separately from source evidence.

決策：`blender/school_v2.blend` 保持不變；研究用副本置於 `blender/working/school_v2_research.blend`，只存本機並由 Git 忽略。建立副本不代表樓梯幾何或跨樓層連通已核准；核准後的衍生修改須與來源證據分開記錄。

## Camera coordinate and image-frame convention / 攝影機座標與影像框架

Decision: Use Blender camera local +X right, +Y up, -Z forward and top-left continuous pixels with half-open image bounds. Extract a normalized rigid world pose and intrinsics from `view_frame(scene)` with actual resolution, pixel aspect, sensor fit and shift; audit sensor-angle fields are not image calibration.

決策：採 Blender Camera local +X 向右、+Y 向上、-Z 向前，以及左上原點、半開影像邊界的連續像素座標。由 `view_frame(scene)` 配合實際解析度、pixel aspect、sensor fit、shift 抽取內參，並正規化剛體世界姿態；audit 的感光器角度不直接當作影像校正值。

## Synthetic visibility and source binding / 合成可見性與來源綁定

Decision: Use point raycasts against a fixed-frame evaluated VIEWPORT Mesh snapshot, excluding only annotation geometry and explicitly owned proxies. Query allowed colliders directly, preserving thin obstacles. This is not rendered-pixel equivalence: render-only modifiers, transparency and image usability are outside this validation. Bind motion, camera catalog and visibility geometry to the same source asset SHA-256 before exporting observations; publish 2D evidence separately from Ground Truth.

決策：以固定 frame 的 evaluated VIEWPORT Mesh 快照進行點 raycast，只排除語意幾何與明確自有 proxy；直接查詢可用碰撞物，保留薄障礙物。此驗證不等於渲染像素結果，render-only modifier、透明度與影像可用性不在本次驗證範圍。匯出前以相同來源 SHA-256 綁定軌跡、相機與可見性場景，2D Evidence 與 Ground Truth 分開儲存。

## Explicit planar inverse projection / 顯式平面反投影

Decision: Bind each Phase 1 inverse-projection service to one calibrated camera and one explicit unit-normal plane. Use the unnormalized Blender -Z-forward camera ray so the intersection parameter remains axial depth for clipping. Record the plane identity and ray-plane incidence quality on PROJECTED output; fail closed on invalid evidence, calibration, geometry or intersection. Ground Truth and Projection Error remain outside the inference interface.

決策：Phase 1 每個反投影 service 明確綁定一個校正 camera 與一個 unit-normal plane。使用未正規化的 Blender -Z-forward camera ray，使交點參數維持可供 clipping 的 axial depth。`PROJECTED` 輸出記錄 plane identity 與 ray-plane incidence quality；無效 evidence、校正、幾何或交點皆 fail closed。Ground Truth 與 Projection Error 維持在 inference interface 之外。

## Directed configured navigation / 有方向的顯式導航設定

Decision: Represent Phase 1 walkability as explicit directed waypoint polylines, separately from directed Camera Topology. Bind both configurations to the same spatial context/source, and make each Camera Transition cite its ordered navigation edge sequence. Compute and validate 3D path lengths internally and choose a canonical minimum-distance route by full edge-ID sequence. Cross-floor movement is disconnected by default and requires an explicit parameterized stair in each permitted direction. Projected endpoints must align with explicit configured nodes; there is no nearest-space snapping. Configured graph membership is not school NavMesh certification; no school edge may be inferred from names, floor candidates or annotation boxes.

決策：Phase 1 walkability 以顯式、有方向的 waypoint polyline 表示，並與有方向的 Camera Topology 分離。兩份設定綁定至相同 spatial context／source，每個 Camera Transition 明確引用 ordered navigation edge sequence。3D path length 由系統內部計算並驗證；等距時以完整 edge-ID sequence 選擇 canonical 最短距離路徑。跨樓層預設 disconnected，每個允許方向都必須有顯式 parameterized stair；Projected endpoint 必須對齊顯式 configured node，不做 nearest-space snapping。Configured graph membership 不等於 school NavMesh 認證；不得從名稱、floor candidate 或 annotation box 推定 school edge。

## Top-K uses topology-authorized routes / Top-K 僅使用拓撲授權路徑

Decision: Enumerate M8 candidates from directed Camera Transition sequences and preserve each transition's exact ordered navigation edges. Require endpoint and intermediate navigation anchors to be continuous; never insert an uncited connector or replace a designated route with a shorter graph route. Deduplicate identical ordered edge corridors. Allow bounded camera-return cycles; same-camera movement between distinct nodes therefore requires an explicit leave-and-return cycle, while the same node permits a stationary candidate. Treat maximum path length and detour ratio as candidate-space eligibility bounds, while node, branch and timeout limits are incomplete termination. Report `MAX_PATHS_REACHED` only after finding an additional distinct feasible candidate beyond the effective K. Keep Ground Truth, semantic ranking and path scores outside this engine.

決策：M8 候選由有方向的 Camera Transition sequences 列舉，並原樣保留每個 transition 指定的 ordered navigation edges。兩端與中間 navigation anchors 都必須連續；不插入未引用的 connector，也不把 designated route 替換成較短的 graph route；相同 ordered edge corridor 會去重。允許受限的 camera-return cycle，因此同 camera 不同 node 必須有明確離開／返回 cycle，同一 node 則可用 stationary candidate。最大 path length 與 detour ratio 定義候選空間；node、branch 與 timeout 則是 incomplete termination。只有找到超過 effective K 的下一條不同可行候選才回 `MAX_PATHS_REACHED`。Ground Truth、semantic ranking 與 path score 維持在此 engine 之外。

## Temporal slack does not determine behavior / 額外時間不決定人類行為

Problem: A physically feasible route can consume much less time than the observed gap;
neither that slack nor the shortest route identifies what the person actually did.
Decision: Preserve every graph candidate and parameterize its full polyline in time.
Store slack explicitly; retain uniform slower movement and deterministic start-dwell
alternatives, and label longer retained routes as possible detours. These are admissible
hypotheses with uncertainty, not behavioral probabilities. Never use Ground Truth to
choose route or timing. Serialize the timing policy alongside movement/search config.

問題：合法路徑所需最低時間可能遠小於 observation gap；slack 或最短路徑都無法確定
人物的實際行為。採用解法：保留全部 Graph candidates，沿完整 polyline 做時間參數化，
明確儲存 slack，保留較慢的等速移動與 departure waypoint dwell alternatives；較長的
既有候選可標為 possible detour。這些都是帶有不確定性的可行假設，不賦予行為機率，
也不以 GT 選擇 route／timing；timing policy 與 movement／search config 一起儲存。

## Separate route coverage from timing alternatives / 路徑覆蓋與時間假設分離

Problem: Counting multiple timings of one route as Top-K, or choosing its best timing
using truth, can inflate route coverage. Decision: K counts distinct candidate IDs in
the supplied order and scores the first timing of each route. Score other timings
individually for debugging only. Align every trajectory at all GT sample timestamps,
reject mismatched extents, and expose ADE/FDE minima plus Coverage using explicit
distance/epsilon config. The fake regression setting is D=ADE, epsilon=1e-6m; formal
benchmark settings remain open. Collision rates use continuous segments against supplied
closed AABBs; configured directed corridor/speed checks do not certify Blender mesh clearance.

問題：把同一路徑的多種 timing 算成 Top-K，或用真值挑選最佳 timing，會高估 route
coverage。採用解法：K 依輸入順序計算不同 candidate ID，只評各 route 第一個 timing；
其他 timing 另提供 debug metrics。所有 GT timestamps 都做線性插值對齊，時間範圍
不一致就拒絕，輸出 ADE／FDE minima 與有明確 distance／epsilon 的 Coverage。
Fake regression 使用 D=ADE、epsilon=1e-6m，正式 benchmark 尚未定案。碰撞率計算
連續線段對顯式封閉 AABB；directed corridor／速度檢查不代表 Blender Mesh 淨空認證。

## Portable calibration preserves evaluated transforms / 可攜校正保留求值後的原始 Transform

Problem: A normalized camera pose alone loses Blender object scale, while sensor-angle
fields alone do not describe the rendered image frame. Decision: Export the evaluated
world matrix separately from the normalized proper rigid pose and its view matrix.
Preserve position, quaternion WXYZ, Euler XYZ, basis scale, pinhole intrinsics, effective
image FOV, clipping, Blender projection matrix, and eight near/far frustum corners with
twelve boundary edges. Keep Blender sensor angles separately. Use OpenGL NDC for the
projection matrix and an explicit axis conversion for the CV intrinsic matrix. Reject
unsupported projection, shear, reflection or inconsistent geometry. Bind the portable
JSON catalog to the source SHA-256, evaluated scene/frame, declared camera-config version
and calibration-content digest; extraction never renders or saves the source.

問題：只有正規化 pose 會遺失 Blender object scale，感光器角度也不能完整代表實際
影像框架。採用解法：原始 evaluated world matrix 與正規化 proper rigid pose／view
matrix 分別保存，匯出 position、WXYZ quaternion、XYZ Euler、basis scale、pinhole
內參、effective image FOV、clipping、Blender projection matrix，以及近／遠平面的
八個角點與十二條 frustum 邊。感光器角度另存；projection matrix 明定 OpenGL NDC，
CV intrinsic matrix 明定軸向轉換。不支援的 projection、shear、reflection 或不一致
幾何皆拒絕。JSON catalog 同時綁定來源 SHA-256、scene／frame、明定的 camera-config
version 與 calibration-content digest；抽取程序不渲染、不儲存來源。

## Producer-neutral visible segments and independent gaps / Producer 共用可見片段與獨立 Gap

Problem: Producer-specific evidence or merging a brief recovery can change the event
boundaries and leak hidden coordinates into inference. Decision: Aggregate only validated
`RawProjectedFrameSample` records, preserving source/context, target/camera, timestamp,
frame identity, available pixels/projection, visibility, occlusion and nullable confidence.
Projected-only mock endpoints keep null pixels; explicit GAP records contain no position
or evidence provenance. Split on GAP, handoff and binding/evidence changes; preserve
every visible sample exactly once, including a one-sample recovery. Reconstruct each
adjacent nonoverlapping visible-segment pair as a separate `BoundGapEvent`, retaining
its own endpoints and search termination. Binding changes break the chain; simultaneous
or overlapping visible segments fail closed pending a separate arbitration decision.
`MockDataset` and `BlenderDataset` share this contract; the latter requires a source hash
and accepts sanitized export JSON, not Blender objects. Real CV retains the producer
schema only. Neither aggregation nor Event inference accepts Ground Truth geometry.

問題：producer 專用 Evidence 或把短暫恢復可見的片段合併，會改變 Event 邊界，甚至
把隱藏座標帶入推論。採用解法：只聚合通過驗證的 `RawProjectedFrameSample`，保留
source／context、target／camera、timestamp、frame identity、已有的 pixels／projection、
visibility、occlusion 與 nullable confidence。Mock 的 projected-only endpoint 維持
null pixels；顯式 GAP 不攜帶 position 或 evidence provenance。遇到 GAP、camera
handoff、binding／evidence 改變就分段；每個可見 sample 恰好保留一次，單一 sample
的短暫恢復也保留。每對相鄰且不重疊的 visible segments 各自建立 `BoundGapEvent`，
保存獨立 endpoints 與 search termination。Binding 改變就斷鏈；同時或重疊可見的
片段先拒絕，留待另外的 arbitration 決策。`MockDataset` 與 `BlenderDataset` 共用
契約；後者須有 source hash，接收清理過的 export JSON，不接收 Blender objects。
Real CV 只保留 producer schema。Aggregation 與 Event inference 都不接收 GT geometry。

## Experiment identity includes content / 實驗身分同時包含內容

Problem: A version label or seed alone cannot identify changed inputs or implementation.
Decision: Keep a versioned ExperimentConfig and DatasetManifest with source/context bindings
and SHA-256 local artifact references. Record dataset, scene, camera, topology, metric and
pipeline versions, seed, effective configuration, input fingerprints, Git commit and dirty
source fingerprints, Python version and uv lock digest. Preserve candidates, metrics and
optional Rerun artifacts under a fresh output directory. Archive original consumed input
bytes, a relocated replay config/manifest, uv lock, tracked source patch and untracked
source contents. Runtime and SDK recording metadata are execution evidence, separate from
deterministic inference/evaluation JSON. A replay requires the matching implementation
and archived bytes, not only a version label.

問題：只有版本名稱或 seed，無法辨識內容或程式已經改變。採用解法：使用具版本的
ExperimentConfig／DatasetManifest，保存 source／context binding 與本機 artifact 的
SHA-256 references。記錄 dataset、scene、camera、topology、metric、pipeline versions、
seed、實際 config、input fingerprints、Git commit／dirty source fingerprints、Python
version 與 uv lock digest。Candidates、metrics 與選用的 Rerun artifacts 寫入新的
output directory；保存實際讀取的原始 input bytes、改用封存 references 的 replay
config／manifest、uv lock、tracked source patch 及 untracked source contents。
Runtime 與 SDK recording metadata 屬於當次執行證據，與 deterministic inference／
evaluation JSON 分開；重播需相符的實作與封存 bytes，不能只靠版本名稱。

## Formal metric configuration remains unresolved / 正式指標設定尚未定案

Problem: Fixture thresholds can be mistaken for adopted research criteria. Decision:
Externalize K, distance D, Coverage epsilon/comparison, temporal alignment, interpolation,
ADE/FDE, route-selection and collision/constraint tolerance policies in a versioned
`MetricConfig`. Preserve the existing regression semantics and reject unsupported policies
rather than giving a new policy name an unimplemented meaning. Metric tolerances do not
relax Graph feasibility constraints. Formal research K, D, epsilon, sampling/alignment
choice and collision/constraint tolerances remain unresolved; the current defaults are
synthetic regression settings, not benchmark acceptance thresholds.

問題：Fixture threshold 容易被誤認為已採用的研究標準。採用解法：以具版本的
`MetricConfig` 明列 K、distance D、Coverage epsilon／比較方式、時間對齊、插值、
ADE／FDE、route selection，以及 collision／constraint tolerance policies。保留既有
regression semantics；不支援的 policy 直接拒絕，不讓名稱變更冒充已實作的新定義。
Metric tolerance 不放寬 Graph 的物理可行性限制。正式研究的 K、D、epsilon、取樣／
時間對齊選擇及 collision／constraint tolerances 尚未定案；目前預設值只重播合成
regression，不是 benchmark 驗收門檻。

## Historical Graph collision-authority checkpoints / Graph 碰撞權威歷史 checkpoint

The following records preserve the 2026-10-02 boundary-round decision and later scale-only
checkpoint. Their pending-policy/pruning status is superseded only within the explicitly
approved policy and local/component scopes above; global completeness remains unresolved.

下列保留 boundary round 與 scale-only checkpoint 原決策；當時待核准 policy／pruning
的狀態，只在上方明列的本輪 policy／component／local scopes 被更新，不改寫歷史證據。
全域完整性仍未解決。

Problem: Configured route membership cannot prove obstacle-free movement. Current Graph
inputs have no obstacle geometry or collision-authority binding; supplied closed AABBs
belong to evaluation. Detecting a known collision after candidate generation therefore
does not establish the PRD requirement that formal output candidates have zero collisions.

Status: **UNRESOLVED**. On 2026-10-02 the user explicitly limited this validation round to
evaluation-only positive collision/tolerance tests and deferred collision Top-K pruning.
Preserve formal schemas. Approved inference obstacle input, source/context binding,
ownership and deterministic pruning policy are required before claiming that Graph
excludes known-collision routes. Do not import evaluation/GT geometry into inference or
turn synthetic AABB tests into Blender mesh clearance certification.

問題：Configured route membership 不能證明路徑無障礙；目前 Graph 沒有 obstacle geometry
或 collision authority binding，封閉 AABB 屬於 evaluation。候選產生後抓到碰撞，不能
宣稱已滿足 PRD「正式輸出的候選 collision rate = 0」。

狀態：**UNRESOLVED**。2026-10-02 使用者明確確認，本輪維持 evaluation-only positive
collision／tolerance tests，暫緩 collision Top-K pruning 並保持正式 Schema 不變。
後續須先核准 inference obstacle input、source／context binding、ownership 與 deterministic
pruning policy；不能把 evaluation／GT geometry 偷渡入 inference，也不能把 fake AABB
測試當成 Blender mesh clearance certification。

Current milestone status / 本輪 milestone 狀態：使用者後續要求解決 collision ownership
並完成 Blender Cases 1–3。2026-10-02 的
[live semantic audit](../../data/scene_audit/SEMANTICS.md) 確認沒有 WALKABLE／WALL／OBSTACLE／
STAIR object 或 collection 標記，亦沒有批准的 camera→floor plane binding。
依使用者明訂 stop conditions，physical integration 暫停；需人工指定 source-bound
walkable／collider objects、faces 或 proxies，以及 movement／occlusion ownership、
floor planes／camera binding 與 physical clearance policy。原 `.blend` 保持不變。
平台無關 geometry provider 可走 additive interface，但未實作或核准 geometry authority；
不得把 annotation boxes、name heuristics 或 evaluation obstacles 升格為 inference authority。

The later milestone requests collision ownership and Blender Cases 1–3. The live audit
finds no approved physical surface/collider labels or camera-plane bindings. Under the
user's explicit stop conditions, integration awaits source-bound human annotations and
physical clearance/contact policy. An additive geometry interface is feasible, but is
not implemented or approved. The original asset and formal schemas remain unchanged.

2026-10-06 historical checkpoint authority update (its scale convention is superseded by
the approved architectural-scale decision above): The additive
[read-only geometry provider](GEOMETRY_PROVIDER.md)
is now implemented. Geometry producers own source-bound exact meshes and review evidence;
Blender objects, names and evaluation/GT geometry do not become Graph authority. Semantic
role approval is distinct from physical support, floor/scale approval and complete scope.
Footprints remain review-only without approved volume evidence. A formal physical consumer
must call `require_approved_physics`; inspection filters, including empty APPROVED results,
cannot certify collision-free space. Every complete floor needs approved WALKABLE support.
All promoted WALL surfaces undergo actual triangle/PORTAL protection regardless of declared
floor. Original extraction-v1 thresholds remain fixed and source/content-bound.
The [current evidence](GEOMETRY_AUTHORITY.md) remains **PROVISIONAL**; this interface decision
does not resolve Graph pruning, stair connectivity, clearance policy or formal benchmark
authority. The previously accepted 1 BU = 1 m calculation convention is unchanged.

2026-10-06 歷史 checkpoint 權威更新（其中尺度慣例已由上方正式核准決策取代）：
新增唯讀 geometry sidecar 已實作；producer 負責 source-bound
實際 mesh 與審查證據，Graph 不直接依賴 bpy，亦不拿名稱或 evaluation／GT 當權威。
Semantic role、physical support、floor／scale 及 scope 完整性分開核准；footprint 沒有
可信 volume 時保持 REVIEW。正式 consumer 必須通過 `require_approved_physics`；空
inspection collider 集合不代表無碰撞，complete floor 必須有核准 WALKABLE。升級 WALL
均以實際 triangles 保護全部 PORTAL，floor label 不得繞過。固定 extraction-v1 閾值與
內容綁定，不降低門檻。當前證據仍 PROVISIONAL；不將新增介面冒充 Graph pruning、
stair connectivity、clearance policy 或正式 benchmark 已完成，既有 1 BU = 1 m 換算不變。

## Protocol definitions do not approve research settings / 協定定義不核准研究參數

This protocol checkpoint's pending physical-policy choices are now separately approved
above. That approval does not adopt final MetricConfig tolerances, certify whole-school
geometry or approve the remaining formal benchmark settings. The retained text below
records the earlier protocol scope and its research-setting boundaries.

此 protocol checkpoint 當時待選的 physical policy 已由上方獨立決策核准；不等於採用
正式 MetricConfig tolerance、全校 geometry 認證或其他正式 benchmark 設定。
下方保留先前 protocol scope 與研究參數邊界的紀錄。

Problem: Reusable case and comparison definitions can be mistaken for approved school
geometry, formal metric choices or an executed research benchmark. Decision: Separate the
versioned [Phase 1 protocol](../research/PHASE1_BENCHMARK_PROTOCOL.md) from executable ExperimentConfig and
synthetic MetricConfig. Report geometric accuracy, physical validity, Top-K coverage,
temporal validity, search behavior and runtime separately. Preserve PRD values only as
`INITIAL_TARGET`. Keep formal execution disabled while research settings or scene authority
are unresolved; Cases 1–3 have no formal Blender results, and Case 4 remains deferred.

Status: **UNRESOLVED_RESEARCH_SETTING** for formal Coverage D and strictly positive epsilon;
formal K, reference sampling, alignment and interpolation; physical clearance/collision
envelope and contact semantics; source-bound geometry/floor authority and camera-plane
binding; movement/occlusion obstacle ownership; and the final A–C baseline algorithms,
constraint masks, tie breaks and budgets. D/E remain interface-only, without Agent work.
Feasible Candidate Recall also requires an independent exhaustive route inventory;
Travel-time Error requires an approved moving-time/dwell reference policy. Overall case/run
weighting and target calibration remain open. Null or unavailable metrics are not zero or
acceptance success; reference-present empty candidate sets retain zero Coverage. These are
open research choices, not adopted values or an expansion of Graph/Reconstruction semantics.

問題：Case 與比較協定完成，容易被誤認為 school geometry、正式 metric 已核准，或已執行
研究 benchmark。採用解法：具版本的 protocol specification 與可執行 ExperimentConfig、
synthetic MetricConfig 分開；幾何、物理、Top-K、時間、search、runtime 六類分別呈現，
PRD 數值只保留 `INITIAL_TARGET`。Research settings／scene authority 未核准時不開放正式
執行；Cases 1–3 沒有正式 Blender results，Case 4 維持暫緩。

狀態：正式 Coverage D／strictly positive epsilon、K／取樣／對齊／插值、physical
clearance／collision envelope／contact semantics、source-bound geometry／floor authority、
camera-plane binding、movement／occlusion obstacle ownership、A–C 的最終算法／constraint
mask／tie break／budgets 皆為 **UNRESOLVED_RESEARCH_SETTING**。D/E 只定義 interface，
不開始 Agent。Recall 另需獨立 exhaustive route inventory；Travel-time Error 另需核准
moving-time／dwell reference policy；overall weighting／target 校準仍未定案。Null／未量測
不當成零或通過；有 reference 的空候選 Coverage 仍為 0。這些列為真正影響研究語意的
未決事項，不填入自行選的值，也不變更正式 Graph／Reconstruction semantics。
