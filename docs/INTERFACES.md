# Module interfaces / 模組介面

[English](#english) | [繁體中文](#繁體中文)

## English

`domain/interfaces.py` preserves replaceable Phase 1 / Phase 2 contracts without implementing future CV, databases or UI:

- `ObservationProvider.get_observations(camera_id, time_range)`: retrieve evidence; providers define their retrieval interval contract explicitly.
- `ProjectionService.project_frame(frame)`: a service configured with camera/plane data accepts only 2D evidence.
- `NavigationService.locate_node(...) / minimum_path(...)`: exact configured-node lookup and one deterministic minimum-distance route; disconnected pairs return `None`.
- `CameraTopologyService.outgoing_transitions(camera_id)`: stable directed topology transitions, separate from navigation distance.
- `TrajectoryGenerator.propose_feasible_trajectories(start, end, max_paths)`: configured topology, navigation and movement/search limits produce physically pruned alternatives.
- `GapReasoner.reconstruct(event)`: reserved for M9 blind-gap completion.
- `EventRepository.save/get`: persistence boundary; production storage is not implemented.
- `VisualizationAdapter.log_event(event)`: presentation boundary; Ground Truth debug rendering is separate.

M6 implements `InverseProjectionService`, a concrete `ProjectionService` configured with exactly one calibrated `Camera` and one explicit unit-normal `Plane`. `project_frame(frame)` accepts only an OBSERVED 2D frame from that camera and returns a `PROJECTED` point carrying the configured plane identity. Pixel-to-world conversion uses the Blender -Z-forward pinhole ray and ray-plane intersection; clip comparisons use camera axial depth. Expected invalid inputs raise typed `InverseProjectionError` failures instead of returning partial coordinates.

The reported `projection_quality` is the bounded ray-plane incidence used as a geometric conditioning indicator. It is not a probability. Neither this service nor its interface accepts Ground Truth; Euclidean Projection Error belongs only to a separate evaluation boundary.

M7 implements `NavigationGraph`, `CameraTopologyGraph` and their cross-validating `NavigationNetwork`. The network requires matching graph/context IDs and source digest, and validates each Camera Transition's explicit ordered navigation edge sequence. The navigation graph computes directed 3D polyline lengths internally and selects equal-distance routes by complete edge-ID sequence, independent of configuration order. Parallel edges remain distinct for M8. `locate_node` uses the graph's explicit tolerance on the requested floor; it never nearest-neighbour-snaps an arbitrary point across unverified space. Unknown nodes are errors, while known disconnected nodes return no path. M8 inputs must therefore coincide with an explicitly configured navigation node within that tolerance.

M7 does not calculate speed, travel time, temporal feasibility, Top-K candidates or reconstruction termination. M8 owns those concerns. No school navigation configuration or inferred stair connectivity is supplied.

Implemented simulation entry points:

```sh
uv run python scripts/export_ground_truth.py --config configs/trajectory_fixture.json --json data/ground_truth/fixture.json --csv data/ground_truth/fixture.csv
uv run python scripts/export_cameras.py --output data/cameras/school_v2_cameras.json
```

The first command uses a fresh Blender factory scene, not an approved school route. To generate school motion, supply an explicit scene/path config and `--blend blender/working/school_v2_research.blend`. Camera export selects only the 29 CAM_* objects from that copy. No command saves or renders the input asset.

`export_observations.py` requires `--ground-truth`, `--cameras`, `--blend`, and `--output`. All three inputs must share a source asset SHA-256. The analytic/factory fixture above must not be combined with school calibration and geometry. Output is sanitized 2D evidence only.

JSON publication refuses existing files by default; an explicit `--overwrite` never permits replacing an input or a Blender asset. Source hash, size and mtime are checked after Blender reads. Generated motion/camera/evidence data remain local and Git-ignored.

## 繁體中文

`domain/interfaces.py` 保留可替換的 ObservationProvider、ProjectionService、TrajectoryGenerator、GapReasoner、EventRepository 與 VisualizationAdapter 契約，不代表已實作 Phase 2 CV、DB 或 UI。

M7 另保留 `NavigationService` 與 `CameraTopologyService` 契約：前者只做 configured node 定位與一條確定性最短距離路徑，後者只回傳穩定排序的有方向 camera transitions。Camera topology permission 與 navigation distance 不混為同一層。

M6 已實作 `InverseProjectionService`：每個 service 明確綁定一個校正後 `Camera` 與一個 unit-normal `Plane`。`project_frame(frame)` 只接受同一台 camera 的 OBSERVED 2D frame，並輸出含 plane identity 的 `PROJECTED` point。轉換採 Blender -Z-forward pinhole ray 與 ray-plane intersection，clip 使用 camera axial depth；無效輸入以 typed `InverseProjectionError` fail closed，不回傳局部座標。

`projection_quality` 是有界的 ray-plane incidence 幾何條件指標，不是機率。此 service 與 interface 都不接受 Ground Truth；歐氏 Projection Error 僅屬於獨立 evaluation 邊界。

M7 已實作 `NavigationGraph`、`CameraTopologyGraph` 與交叉驗證兩者的 `NavigationNetwork`。Network 要求一致的 graph/context ID 與來源 digest，並驗證每個 Camera Transition 明確引用的 ordered navigation edge sequence。Navigation graph 內部計算有方向 3D polyline 長度；等距路徑以完整 edge-ID sequence 決勝，不受設定順序影響，平行 edge 也不合併。`locate_node` 只在指定樓層以 graph 明確設定的 tolerance 比對 configured node，不會把任意點最近鄰吸附到未驗證空間。未知 node 是錯誤，已知但 disconnected 的 node 則沒有路徑；因此 M8 輸入必須在該 tolerance 內對齊顯式 navigation node。

M7 不計算速度、travel time、時間可行性、Top-K candidate 或 reconstruction termination；這些屬於 M8。此階段沒有提供 school navigation config，也沒有推定樓梯連通。

Ground Truth CLI 預設使用新的 Blender factory 場景，不是核准的 school 路徑。school 軌跡必須另提供明確路徑／scene config 與研究副本 `--blend`。Camera CLI 僅抽取研究副本的 29 台 CAM_*；所有輸入資產都不儲存、不渲染。

Observation 匯出需提供 Ground Truth、camera catalog、Blender 場景與輸出路徑；前三者必須具有相同來源 SHA-256。不能把 factory fixture 軌跡混入 school 相機與建築幾何。推論端只收到清理過的 2D Evidence。

輸出預設不覆寫；明確開啟覆寫仍不得取代輸入或 Blender 資產。Blender 讀取前後驗證雜湊、大小與修改時間；生成軌跡、相機與 Evidence 保留本機並由 Git 忽略。M9 重建、M11 視覺化與正式 Phase 2 實作仍在後續里程碑。
