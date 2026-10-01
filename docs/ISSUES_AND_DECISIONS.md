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
