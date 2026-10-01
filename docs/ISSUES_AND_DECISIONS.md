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

Decision: Infer floor-surface candidates from evaluated mesh geometry, not object names alone. The two stair annotation regions lack a mesh-supported continuous ascent; fail closed on cross-floor traversal until a valid stair representation is confirmed. Never use annotation boxes as collision surfaces or invent connections through floor slabs; preserve the source `.blend`.

決策：以求值後的 Mesh 幾何辨識地板候選，不只依賴名稱。兩處樓梯標示區未找到實體 Mesh 支持的連續上升路徑；在有效樓梯表示確認前，不開放跨樓層通行。語意 box 不當作碰撞面，也不虛構穿越樓板的連接；原始 `.blend` 保留。
