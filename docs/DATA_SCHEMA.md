# Phase 1 data contracts / Phase 1 資料契約

[English](#english) | [繁體中文](#繁體中文)

## English

The authoritative schemas are Pydantic models in `src/amidst/domain/`. Models forbid unknown fields, require finite coordinates/times, retain nullable Phase 2 fields, and serialize enums as strings. Frozen models and tuple sequences prevent accidental in-place mutation.

| Model | Producer and permitted consumers | Key boundary |
| --- | --- | --- |
| `GroundTruthTrajectory` | Simulation/export; evaluation; debug visualization | `SYNTHETIC`, `GROUND_TRUTH`; never inference input |
| `Camera` | Blender calibration; simulation and projection | Normalized world pose, pinhole intrinsics, top-left continuous pixels |
| `Plane` | Explicit projection configuration | Finite point plus unit world normal; labels do not certify walkability |
| `ObservationFrame` | Simulation; observation/projection services | OBSERVED has pixels; GAP has null pixels/provenance and a reason; no 3D truth |
| `ProjectedPoint` | Projection; topology/graph/reconstruction | World position plus explicit `plane_id`; PROJECTED only |
| `Observation` | Evidence aggregation; graph | Observed frames and/or projected path, explicit time window; no GAP frame as evidence |
| `CandidateTrajectory` | Deterministic graph; reconstruction/evaluation | INFERRED_GAP only; polyline, corridor, distance/time/cost and feasibility flags |
| `ReconstructionResult` / `Event` | Graph/reconstruction; storage/presentation | Alternatives and explicit termination; never ground-truth payloads |

Ground Truth JSON and CSV belong in `data/ground_truth/`. `sample_source=BLENDER_EVALUATED` means positions were read from an evaluated Blender proxy; `CONFIGURATION_SAMPLER` is the analytic test helper, not an authoritative Blender export. Configured velocities are piecewise-linear derivatives. Optional source asset SHA-256 binds school motion to calibration/visibility. Seeds are recorded; the baseline sampler itself uses no randomness.

Simulation observation JSON has `{data_kind, scene_id, geometry_policy, frames}` and is stored separately in `data/observations/`. It contains no hidden 3D position or velocity. GAP reasons distinguish FOV/clipping, occlusion, uncertain geometry and budget limits. Geometry is a fixed-frame evaluated VIEWPORT Mesh snapshot; no rendered-image claim is made.

M6 inverse projection binds one calibrated `Camera` to one explicit `Plane`. It rejects GAP evidence, camera mismatch, out-of-image pixels, invalid calibration, invalid planes, parallel/behind-camera intersections and clip violations. Every output records the plane identity and uses ray-plane incidence as a deterministic geometric conditioning quality in `[0, 1]`; this value is neither a probability nor Ground-Truth-derived projection error. Projection Error remains an evaluation-only calculation.

Phase 2 track IDs, stitching/fragment counts, appearance embeddings/labels/qualities, tracking quality, directions and video references remain nullable. They are schemas, not detector/tracker/ReID/database implementations. `projection_quality` is a geometric quality indicator, not a calibrated probability.

The schema deliberately permits an empty `OBSERVED` shell so upstream aggregation can represent a declared interval before evidence is attached. That shell is not valid graph evidence. Projection and graph callers must require the projected endpoint(s) needed by their operation; M8 candidate generation must reject observations without projected endpoints.

All time values are synthetic seconds. World coordinates are right-handed Blender coordinates with Z up and one unit equal to one metre. Camera local axes are +X right, +Y up, -Z forward. Pixels use `0 <= u < width`, `0 <= v < height`; near/far clipping uses axial depth. Schema validation does not certify walkability; deterministic geometry/topology modules must do so.

## 繁體中文

正式欄位定義以 `src/amidst/domain/` 的 Pydantic models 為準。模型拒絕未知欄位、非有限座標／時間，保留 Phase 2 nullable 欄位；enum 序列化為字串，frozen model 與 tuple 防止原地修改。

Ground Truth 僅供 simulation/export、evaluation 與 debug visualization；`BLENDER_EVALUATED` 座標來自 Blender proxy 求值，解析測試取樣器另標為 `CONFIGURATION_SAMPLER`。速度是設定路徑的分段線性導數。基準取樣器不使用隨機性，但仍記錄 seed 與可用的來源資產 SHA-256。

2D Observation 與 Ground Truth 分開儲存。OBSERVED 必須有像素與 OBSERVED provenance；GAP 必須沒有像素／provenance，並記錄 FOV、遮擋、不確定幾何或預算原因。輸出沒有隱藏世界座標或速度。可見性是固定 frame 的 VIEWPORT Mesh 點查詢，並非渲染影像結果。

M6 反投影會把一個校正後 `Camera` 明確綁定至一個 `Plane`。GAP evidence、camera 不一致、超出影像範圍的 pixel、無效校正／平面、平行或位於 camera 後方的交點，以及 clip 違規都會 fail closed。每個輸出都記錄 plane identity，並以 ray-plane incidence 作為 `[0, 1]` 的確定性幾何條件品質；它不是機率，也不是由 Ground Truth 計算的 Projection Error。Projection Error 只屬於 evaluation 邊界。

ProjectedPoint 僅允許 PROJECTED；CandidateTrajectory 僅允許 INFERRED_GAP。Observation 可保留原始 observed frames 與 projected path，但不能把 GAP 當作直接證據。ReconstructionResult／Event 保留多解與停止原因，不接受 Ground Truth payload。

Schema 明確允許空的 `OBSERVED` shell，讓上游 aggregation 表示尚未附加證據的宣告區間；但它不等於有效的 Graph Evidence。Projection／Graph caller 必須要求該操作所需的 projected endpoint；M8 候選生成必須拒絕缺少 projected endpoint 的 Observation。

Tracking、stitching、appearance、quality、方向與 video reference 欄位維持 nullable，不代表已實作 Phase 2。Projection quality 是幾何品質指標，不是校準機率。

時間是合成秒數；世界座標為 Blender 右手座標、Z 向上、1 unit = 1 公尺。Camera local 為 +X 右、+Y 上、-Z 前；像素左上為原點、採半開邊界；clip 使用軸向深度。Schema 驗證不等於可行走認證，仍需確定性的幾何與拓撲檢查。
