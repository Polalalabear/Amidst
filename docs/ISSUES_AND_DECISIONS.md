## Scene unit-to-metre convention / 場景單位與公尺換算

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
