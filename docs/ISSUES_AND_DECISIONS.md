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
