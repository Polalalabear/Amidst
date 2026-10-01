# Module interfaces / 模組介面

[English](#english) | [繁體中文](#繁體中文)

## English

`domain/interfaces.py` preserves replaceable Phase 1 / Phase 2 contracts without implementing future CV, databases or UI:

- `ObservationProvider.get_observations(camera_id, time_range)`: retrieve evidence; providers define their retrieval interval contract explicitly.
- `ProjectionService.project_frame(frame)`: a service configured with camera/plane data accepts only 2D evidence.
- `NavigationService.locate_node(...) / minimum_path(...)`: exact configured-node lookup and one deterministic minimum-distance route; disconnected pairs return `None`.
- `CameraTopologyService.outgoing_transitions(camera_id) / minimum_hop_transition_path(...)`: stable directed topology transitions and canonical camera-level reachability, separate from navigation distance; hop reachability alone does not prove navigation-anchor continuity.
- `TrajectoryGenerator.propose_feasible_trajectories(start, end, max_paths)`: configured topology, navigation and movement/search limits produce physically pruned alternatives.
- `GapReasoner.reconstruct(event)`: deterministic timed alternatives for a single blind gap.
- `EventRepository.save/get`: persistence boundary; production storage is not implemented.
- `VisualizationAdapter.log_event(event)`: Rerun presentation boundary; Ground Truth debug rendering is separate.

M6 implements `InverseProjectionService`, a concrete `ProjectionService` configured with exactly one calibrated `Camera` and one explicit unit-normal `Plane`. `project_frame(frame)` accepts only an OBSERVED 2D frame from that camera and returns a `PROJECTED` point carrying the configured plane identity. Pixel-to-world conversion uses the Blender -Z-forward pinhole ray and ray-plane intersection; clip comparisons use camera axial depth. Expected invalid inputs raise typed `InverseProjectionError` failures instead of returning partial coordinates.

The reported `projection_quality` is the bounded ray-plane incidence used as a geometric conditioning indicator. It is not a probability. Neither this service nor its interface accepts Ground Truth; Euclidean Projection Error belongs only to a separate evaluation boundary.

M7 implements `NavigationGraph`, `CameraTopologyGraph` and their cross-validating `NavigationNetwork`. The network requires matching graph/context IDs and source digest, and validates each Camera Transition's explicit ordered navigation edge sequence. The navigation graph computes directed 3D polyline lengths internally and selects equal-distance routes by complete edge-ID sequence, independent of configuration order. Parallel edges remain distinct for M8. `locate_node` uses the graph's explicit tolerance on the requested floor; it never nearest-neighbour-snaps an arbitrary point across unverified space. Unknown nodes are errors, while known disconnected nodes return no path. M8 inputs must therefore coincide with an explicitly configured navigation node within that tolerance.

M8 implements `SpatiotemporalGraphEngine`, a concrete `TrajectoryGenerator` bound to a validated `NavigationNetwork`, `MovementConstraints` and `GraphSearchPolicy`. It consumes the last projected point of the start observation and first projected point of the end observation, requires a positive timestamp gap and explicit floor/node alignment, and rejects malformed evidence with typed `GraphInputError`. Valid but unreachable or too-fast pairs produce an exhaustive `NO_FEASIBLE_PATH` result.

Candidate enumeration is uniform-cost over exact Camera Transition routes, ordered by cumulative distance, complete edge-ID sequence and transition identity. Multi-hop anchors must be continuous; no uncited navigation bridge or alternate shortest route is inserted. Equal ordered edge corridors are deduplicated before consuming K. Camera cycles are allowed and remain finite under positive lengths, speed, maximum length, detour, node, branch and time bounds. Same-camera/same-node input yields a stationary zero-distance candidate; moving between different nodes of one camera requires an explicit leave-and-return transition cycle. `expanded_nodes` counts dequeued authorized-route search states. Branch overflow stops before silently discarding children. Timeout is an operational wall-clock bound measured with an injectable, finite, nondecreasing monotonic clock at fixed search boundaries. Candidate IDs are canonical SHA-256 identities over source/network, complete endpoint, route geometry and movement-speed data. Search does not use projection quality, semantic fields, Ground Truth or a path score.

`COMPLETE` and `NO_FEASIBLE_PATH` mean the configured bounded candidate space was exhausted. `MAX_PATHS_REACHED` requires observing one extra feasible route beyond the effective K; the effective K is the smaller of method `max_paths` and policy `max_candidate_paths`. Node, branch and timeout reasons always set `complete=false`, preserving candidates already proven feasible. No school navigation configuration or inferred stair connectivity is supplied.

The producer-independent downstream entry is `pipeline.load_inference_input(path)` followed
by `generate_candidates(inputs)` or `reconstruct_input(inputs) -> (ReconstructionResult, Event)`.
Neither loads GT. `BlindGapReconstructor(policy).reconstruct_gap(start, end, result)` validates
projected endpoints/candidates and implements `reconstruct(event)` for one gap. Longer
retained routes, slower uniform timing and start-dwell alternatives stay separate hypotheses.

`evaluate_trajectories(event.trajectories, truth, EvaluationConfig, constraints=ConstraintConfig)`
is evaluation-only. `RerunDebugVisualizationAdapter` implements `log_event`; call `save(path)`
before logging and `close()` afterward. `log_debug_ground_truth(truth)` requires debug mode.
All Top-K paths, sampled timed markers, provenance, slack, termination and metrics are logged;
camera anchors are configured navigation anchors, not calibrated poses or frustums.

`debug.runner.run_experiment` completes inference before loading optional GT, validates
target/context/source bindings, and saves exclusive output files plus the full run config.
Its generic CLI can run a fixture or a future Blender-derived input without algorithm changes:

```sh
uv run python scripts/run_downstream.py --input data/mock/branching_top_k/inference.json --ground-truth data/mock/branching_top_k/ground_truth.json --constraints data/mock/constraints.json --output data/candidates/my_new_run
uv run rerun data/candidates/my_new_run/debug.rrd
```

`--k` and `--coverage-epsilon-m` configure evaluation; inference K remains in the input's
search policy. Omit `--ground-truth` for inference-only output; `--no-rerun` skips recording.
Use a fresh output directory for every rerun. JSON inference/results are deterministic;
RRD SDK recording/log metadata need not be byte-identical. No Semantic Ranking is implemented.

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

M8 已實作 `SpatiotemporalGraphEngine`，以通過驗證的 `NavigationNetwork`、`MovementConstraints` 與 `GraphSearchPolicy` 實作 `TrajectoryGenerator`。它取 start Observation 最後一個 projected point 與 end Observation 第一個 projected point，要求正時間差以及明確的 floor／node 對齊；不合法 Evidence 以 typed `GraphInputError` 拒絕，合法但不可達或超速的組合則回傳已窮盡的 `NO_FEASIBLE_PATH`。

候選以 uniform-cost 列舉 Camera Transition 明確指定的路徑，依累積距離、完整 edge-ID sequence 與 transition identity 穩定排序。多跳 anchors 必須連續，不會插入未引用的 navigation bridge 或替換為另一條最短路徑；相同 ordered edge corridor 在計入 K 前會去重。Camera cycle 可以存在，並由正距離、速度、最大長度、detour、node、branch 與 time bounds 保證有限。同 camera／同 node 會產生 stationary 零距離候選；同 camera 不同 node 必須有明確的離開／返回 transition cycle。`expanded_nodes` 計算已 dequeue 的 authorized-route search states；branch 超限時在丟棄 child 前停止。Timeout 是 operational wall-clock bound，要求可注入 clock 回傳有限且非倒退的 monotonic 值，並在固定搜尋邊界檢查。Candidate ID 是 source／network、完整 endpoint、route geometry 與 movement speed 資料的 canonical SHA-256；搜尋不讀 projection quality、semantic fields、Ground Truth，也不產生 path score。

`COMPLETE`／`NO_FEASIBLE_PATH` 表示 configured bounded candidate space 已窮盡。只有實際看到有效 K 之外的下一條可行路徑才回 `MAX_PATHS_REACHED`；K 取 method `max_paths` 與 policy `max_candidate_paths` 較小值。Node、branch、timeout 停止一律 `complete=false`，並保留已證明可行的候選。此階段沒有提供 school navigation config，也沒有推定樓梯連通。

Ground Truth CLI 預設使用新的 Blender factory 場景，不是核准的 school 路徑。school 軌跡必須另提供明確路徑／scene config 與研究副本 `--blend`。Camera CLI 僅抽取研究副本的 29 台 CAM_*；所有輸入資產都不儲存、不渲染。

Observation 匯出需提供 Ground Truth、camera catalog、Blender 場景與輸出路徑；前三者必須具有相同來源 SHA-256。不能把 factory fixture 軌跡混入 school 相機與建築幾何。推論端只收到清理過的 2D Evidence。

輸出預設不覆寫；明確開啟覆寫仍不得取代輸入或 Blender 資產。Blender 讀取前後驗證雜湊、大小與修改時間；生成軌跡、相機與 Evidence 保留本機並由 Git 忽略。正式 Phase 2 實作仍在後續里程碑。

通用 `pipeline` 可載入任何符合 `InferenceInput` 的合成 producer，產生 Graph result 與 timed
Event，完全不讀 GT。`BlindGapReconstructor` 保留所有候選並沿 polyline 建立 direct／slower／
start-dwell／detour 假設。Evaluation 另接 GT；Rerun 的 GT overlay 必須啟用 debug mode，
呈現所有 Top-K、具時間取樣的 markers、provenance、slack、termination 與 metrics。
Camera anchors 不冒充 calibrated camera poses／FOV。`run_experiment` 在推論完成後才載入
GT，驗證 target／spatial context／source hash，存完整 config 並拒絕既有 output directory。
上方 CLI 可直接替換 Blender-derived input；`--k`／epsilon 僅設定 evaluation，Graph K 由
inference search policy 決定。省略 GT 可獨立推論；`--no-rerun` 不生成 recording。JSON 可重現，
RRD SDK metadata 不保證 byte-identical。本輪沒有加入 Semantic Ranking。
