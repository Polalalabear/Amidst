# Module interfaces / 模組介面

[English](#english) | [繁體中文](#繁體中文)

## English

`domain/interfaces.py` preserves replaceable Phase 1 / Phase 2 contracts without implementing future CV, databases or UI:

- `ObservationProvider.get_observations(camera_id, time_range)`: retrieve evidence; providers define their retrieval interval contract explicitly.
- `ProjectionService.project_frame(frame)`: a service configured with camera/plane data accepts only 2D evidence.
- `TrajectoryGenerator.propose_feasible_trajectories(start, end, max_paths)`: configured topology, navigation and movement/search limits produce physically pruned alternatives.
- `GapReasoner.reconstruct(event)`: reserved for M9 blind-gap completion.
- `EventRepository.save/get`: persistence boundary; production storage is not implemented.
- `VisualizationAdapter.log_event(event)`: presentation boundary; Ground Truth debug rendering is separate.

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

Ground Truth CLI 預設使用新的 Blender factory 場景，不是核准的 school 路徑。school 軌跡必須另提供明確路徑／scene config 與研究副本 `--blend`。Camera CLI 僅抽取研究副本的 29 台 CAM_*；所有輸入資產都不儲存、不渲染。

Observation 匯出需提供 Ground Truth、camera catalog、Blender 場景與輸出路徑；前三者必須具有相同來源 SHA-256。不能把 factory fixture 軌跡混入 school 相機與建築幾何。推論端只收到清理過的 2D Evidence。

輸出預設不覆寫；明確開啟覆寫仍不得取代輸入或 Blender 資產。Blender 讀取前後驗證雜湊、大小與修改時間；生成軌跡、相機與 Evidence 保留本機並由 Git 忽略。M9 重建、M11 視覺化與正式 Phase 2 實作仍在後續里程碑。
