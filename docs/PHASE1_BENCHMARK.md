# Phase 1 benchmark / Phase 1 實驗執行

[繁體中文](#繁體中文) | [English](#english)

正式 Case 1–4、metric／baseline／ablation 與分項 acceptance specification 見
[BENCHMARK_PROTOCOL](PHASE1_BENCHMARK_PROTOCOL.md)。該 protocol 尚有
`UNRESOLVED_RESEARCH_SETTING`，不能直接作為可執行的 ExperimentConfig。
本頁說明既有 synthetic runner；comparison reporting 的入口為：

```sh
uv run python -m amidst.benchmark_report --input <benchmark-output-root> --output data/reports/benchmark
```

輸出使用新的目錄，含各自獨立的 comparison PNG、`benchmark_summary.json` 與
`benchmark_summary.md`。缺值維持 N/A，失敗與 NO_REFERENCE 保留；不依 GT 誤差
重排 method。既有 fake outputs 的圖表標記為 `SYNTHETIC REGRESSION`，人工建立的
plotting fixture 標記為 `MOCK VALIDATION`，不能當作 Blender research result。

The [formal protocol](PHASE1_BENCHMARK_PROTOCOL.md) specifies Cases 1–4, metrics, baselines,
ablations and separate acceptance categories. It retains unresolved settings and is a
specification, not an executable ExperimentConfig. The comparison command above reads
existing benchmark outputs into a fresh report directory, writes separate PNGs and JSON/
Markdown summaries, preserves missing/failed/no-reference rows, and never orders methods
by Ground Truth error. Synthetic runner results and plotting fixtures remain explicitly
labelled synthetic regression or mock validation.

Normalized multi-method input 使用 `schema_version="benchmark-comparison/v1"`，包含
`cases`／`methods` identity arrays、`provenance.benchmark_kind` 與 `runs`。每筆 run 明列
`case_id`、`method_id`、`run_id`、`status`、`selected_k`、`metrics`、`coverage_at_k`、
`termination_reason` 與 invariant `comparison_settings`（dataset／seed／metric identity）。
完整範例見 [plotting-only fixture](../tests/fixtures/benchmark_report_comparison.json)。
Native runner 的 method 標為 `deterministic_graph`；不擅自將既有 fake run 改稱 A–C。
Multi-method directory 格式為 `results/<case>/<method>/<run>/metrics.json`，搭配原
`summary.json`；method IDs 可用 `shortest_path`、`geometry`、`spatiotemporal`。
缺值使用 JSON null；同一 case／method 的不相容 runs 不平均，會列 N/A／REVIEW。

Normalized comparisons declare the schema version above, case/method identities, explicit
provenance and independent run records with metrics, K, Coverage and comparison invariants.
The linked fixture is a complete plotting-only example. Native outputs retain their actual
configured deterministic method identity. Directory comparisons accept the tree above;
incompatible repeated-run settings produce N/A and REVIEW rather than an aggregate mean.

## 繁體中文

### 執行入口

統一 runner 讀取具版本與內容雜湊的 config／dataset，執行 raw frame aggregation、
獨立 blind-gap Event 建立、Graph Top-K、reconstruction、evaluation 與結果報告。
內建 mock stream 固定 seed `20261001`；這是 regression infrastructure，不是正式
school dataset 或研究驗收結論。[PRD](PRD.md) 定義研究需求，
[核心決策](ISSUES_AND_DECISIONS.md) 定義已採用方案與尚未決定的研究設定。

從 repository root 執行，每次使用尚不存在的 output directory：

```sh
uv run python -m amidst.benchmark --config configs/benchmarks/mock_stream_v1.json --output data/candidates/benchmark/my_new_run
```

需要 Rerun 與明確的 debug GT overlay 時，使用另一個新目錄：

```sh
uv run python -m amidst.benchmark --config configs/benchmarks/mock_stream_v1.json --output data/candidates/benchmark/my_new_debug_run --rerun --debug-ground-truth
```

`--rerun`／`--no-rerun` 覆寫 config 的 recording 設定；`--debug-ground-truth` 必須搭配
啟用 recording。單獨啟用 GT debug 不會自動開啟 Rerun。省略 debug flag 時，GT 仍可供
evaluation 使用，但不顯示 GT overlay。Runner 不替換既有 output directory。

每個 gap 的 `debug.rrd` 路徑記於 `summary.json`。用 Rerun 開啟該路徑：

```sh
uv run rerun path/to/debug.rrd
```

### Input 與版本綁定

[mock experiment config](../configs/benchmarks/mock_stream_v1.json) 引用
[stream dataset manifest](../data/mock/stream_v1/dataset.json) 與獨立的
[metric config](../configs/metrics/synthetic_regression_v1.json)。每個 reference 具有本機
path 與 SHA-256；相對路徑以包含該 reference 的 config／manifest 所在目錄解析。
檔案內容、manifest versions／seed 或 pipeline version 不符時直接拒絕。

ExperimentConfig 明列 `experiment_id`、`dataset_version`、`seed`、`scene_version`、
`camera_config_version`、`topology_version`、`metric_config_version`、`pipeline_version`、
aggregation policy 與 recording/debug 設定。DatasetCase 引用 pipeline、frames、
選用的 constraints／calibration，以及分開的 evaluation references；dataset provider
只載入 sanitized frame samples，不開啟 reference trajectory。

Raw samples 帶有 source／spatial-context binding、target／camera、frame ID／timestamp、
UV、visibility、occlusion、nullable confidence、provenance 與已有的 projected point。
Projected-only mock endpoint 沒有虛構 UV；GAP 沒有 pixels／projection／provenance。
Aggregation 保留短暫的可見恢復，每個相鄰 visible-segment pair 形成獨立 gap，原樣
傳遞 Graph termination。未決的 simultaneous／overlapping visibility 先拒絕，不做
confidence arbitration 或 Semantic Ranking。

### MetricConfig

以下為 model 的 synthetic-regression defaults；實際使用值以 run 的 effective config
為準。正式 benchmark 的 K、D、epsilon、取樣／時間對齊及物理 tolerance 尚未定案。
Policy 欄位只接受目前支援的值；更改名稱不會實作新的 metric。Graph K 與物理限制
仍由 pipeline 的 search／movement config 決定，evaluation tolerance 不放寬 Graph。

| 參數 / Parameter | 預設值／支援語意 / Default and supported policy |
| --- | --- |
| `metric_config_version` | `synthetic-regression-metrics-v1` |
| `k_values` | `[3]`；每個 K 計不同 candidate route，依輸入順序使用第一個 timing |
| `trajectory_distance_metric` | `ADE` |
| `coverage_epsilon_m` | `1e-6 m` |
| `coverage_comparison` | `STRICTLY_LESS_THAN`，即 `D < epsilon` |
| `interpolation_policy` | `PIECEWISE_LINEAR` |
| `temporal_alignment_policy` | `ALL_GROUND_TRUTH_TIMESTAMPS_EXACT_EXTENT` |
| `ade_policy` | `ARITHMETIC_MEAN_3D_EUCLIDEAN`，對全部 reference timestamps 取平均 |
| `fde_policy` | `LAST_GROUND_TRUTH_TIMESTAMP_3D_EUCLIDEAN` |
| `top_k_policy` | `FIRST_HYPOTHESIS_PER_DISTINCT_CANDIDATE_IN_INPUT_ORDER` |
| `collision_tolerance_m` | `0.0 m` |
| `collision_tolerance_policy` | `EXPAND_CLOSED_AABB`；以 tolerance 向外擴張提供的 boxes |
| `collision_boundary_policy` | `CLOSED_AABB_TOUCH_COUNTS`；接觸邊界也計碰撞 |
| `constraint_speed_relative_tolerance` | `1e-12` |
| `constraint_corridor_tolerance_m` | `1e-6 m` |
| `constraint_denominator` | `CONSECUTIVE_TIMED_POINT_PAIRS_INCLUDING_DWELL` |
| `formal_benchmark_status` | `UNRESOLVED` |

內建 `synthetic_regression_v1.json` 明確要求 `k_values=[1, 2, 3]`，用來觀察 route
preservation 隨 K 的變化；沒有指定欄位時的 model default 仍為 `[3]`。

每個 K 都輸出 minADE@K、minFDE@K、Coverage@K 與 route identities；所有 timing
hypotheses 另有 ADE、FDE 與物理 segment counts。無候選時 errors／rates 為 null，
不以零誤差代表成功。Evaluation reference 必須符合 target／context／source hash／seed，
並含每個 gap 的精確起訖 timestamps；不 extrapolate 或以 GT 改變推論邊界。

Collision 檢查連續 timed segments 與提供的封閉 AABBs，分母包含 stationary dwell。
Constraint metrics 檢查 configured speed ceiling 與 directed corridor；沒有障礙物或
只有測試 boxes 的零碰撞結果，不證明 school WALL／OBSTACLE 或 mesh clearance。

### 結果檔案與重播

每次完成的 run 保存以下 artifact；case／event directory 以 `id-` 前綴及 percent
encoding 處理身分，不以任意 ID 當作 filesystem 路徑：

```text
output/
  config.json
  experiment.json
  summary.json
  summary.md
  metrics.json
  artifacts.json
  cases/id-<case>/
    observations.json
    gaps/id-<event>/
      candidates.json
      debug.rrd                 # 啟用 Rerun 時
  replay/
    README.md
    config.json
    dataset.json
    inputs/<sha256>.json
    source.patch
    untracked/                  # 有 untracked source 時
    uv.lock
```

`config.json` 保存 CLI overrides 後的 effective config；`experiment.json` 保存完整
versions／seed、Git commit、dirty source fingerprints、Python／uv lock 與 input hashes。
`candidates.json` 保存各 gap 的 source binding、獨立 endpoints、Graph result、candidates、
timed Event 與 termination。`metrics.json` 保存每個 gap 的 configured K results，
`summary.json` 保存 run／case／gap 摘要與 artifact 路徑；`summary.md` 以表格整理
Scenario／Event、Candidates／Hypotheses、K、minADE、minFDE、Coverage、Collision／
Constraint violations、Termination 與 runtime，不產生研究結論。

表格中的 Coverage 是單個 gap／K 的布林結果；物理 violations 計全部 timed hypotheses，
包含 dwell，不能把重複 K 列相加當成新樣本。Inference runtime 是每個 case 的實測值，
同一 case 的各 gap 列共用該值；不是各 gap 可相加的獨立延遲。`artifacts.json` 以
`status=COMPLETE` 與 file SHA-256 清單記錄已完成輸出；它不把 partial output 冒充完整
run，也不宣告正式研究驗收。

已驗證 experiment config 後，case 載入／aggregation／Graph 的已知 input-contract
拒絕會保存 `summary.json`（`status=INPUT_REJECTED`、case、stage、error type/message／
typed failure code）、`error.json`、`metrics.json`（`status=NOT_RUN`）與 `summary.md`，
並重新拋出原 exception。沒有成功 `artifacts.json`、候選或捏造的 termination；正式
domain schemas 不變。未知 consumer exceptions 仍直接拋出，不冒充 input rejection。
Experiment／MetricConfig 版本或 schema 錯誤維持在 output 建立前 fail fast。
有效空候選仍保存完整結果，errors／rates 為 null、Coverage=false；summary 保留
search completeness、expanded states、rejection reasons、endpoint cameras 與 NO_REFERENCE。

`replay/inputs/` 保存實際使用的原始 JSON bytes，依 SHA-256 命名。Replay config／
manifest 改為引用這些封存檔案；原始 config bytes 也保留，CLI overrides 則保存於
effective config。`source.patch`、`untracked/` 與 `uv.lock` 保留 dirty checkout 所需內容。
依 `replay/README.md`，在對應 commit／Python version 的獨立 checkout 恢復來源與 lock
後，以新的 output directory 執行：

```sh
uv run python -m amidst.benchmark --config /absolute/path/to/previous_run/replay/config.json --output /fresh/output/directory
```

固定 inputs、實作、環境與 deterministic search budgets 時，visible segments、Event
boundaries、candidate order 與 metric values 可重播。Runtime 與 RRD SDK metadata 是
診斷資訊，不要求逐位元相同；operational wall-clock timeout 的觸發點也不以 seed 保證。

### Provider 替換與仍需補齊的場景契約

`MockDataset` 與 `BlenderDataset` 實作同一 raw-frame／ObservationProvider 契約。
後者接收已清理、已投影的 Blender synthetic JSON，要求 source asset SHA-256；
它不直接開啟 `.blend`，也不把 `bpy`／`mathutils` 帶入 domain。更換 provider 只換
dataset／manifest，不改 Graph Engine、Top-K、reconstruction、metrics 或 Rerun consumer。

Actual camera calibration 可獨立抽取，無須等待 WALKABLE／STAIR／WALL：

```sh
uv run python scripts/export_camera_calibration.py --blend blender/school_v2.blend --output data/cameras/my_new_calibration.json --camera-config-version my-camera-config-v1
```

輸出保留 raw／rigid poses、內參、view／projection matrices 與 frustum，以來源／內容
雜湊及 evaluated scene/frame 綁定。抽取只選 29 台 `CAM_*`，不渲染、不儲存來源。
DatasetCase 可引用 calibration JSON；Rerun 將實際 camera poses／frustums 與 configured
navigation anchors 分開呈現。

真正的 Blender dataset 仍需可信任的 visible/projected samples、explicit plane mapping、
source/context binding、configured navigation nodes／edges 與 topology。School walkability、
障礙物／淨空、floor connectivity、stair validity 及基於語意幾何的 endpoint alignment
仍待標記／審核；現有 Camera export 或 provider contract 不補出這些資料。Phase 2
REAL_CV 只保留 producer schema；實際 CV、ReID、Semantic Ranking、DB、Web／Three.js
與高併發 benchmark 不在這個 runner 的範圍。

## English

The versioned command above executes shared dataset loading, visible-segment aggregation,
independent gap inference, Graph Top-K, reconstruction, evaluation and reporting. The bundled
mock stream uses seed `20261001`; it validates interfaces rather than school scene semantics
or formal research acceptance. Use a fresh output directory for each run. Rerun is optional;
Ground Truth overlay requires both recording and explicit debug enablement. Reference geometry
is loaded only after all dataset cases complete inference, never by the provider or inference
consumers.

ExperimentConfig and DatasetManifest bind dataset/scene/camera/topology/metric/pipeline versions
and local artifact SHA-256 references. Paths resolve relative to the containing config or
manifest. Visible samples preserve source/context, camera/target, frame/time, pixels or supplied
projection, visibility, occlusion and nullable confidence. Explicit GAPs contain no coordinates
or evidence provenance. A brief recovery remains visible evidence and separates adjacent gaps;
ambiguous overlapping visibility is rejected pending separate arbitration.

The MetricConfig table specifies supported synthetic-regression defaults, not formal research
thresholds. The bundled metric config requests K values `[1, 2, 3]`, while the model default
is `[3]`. Each K selects distinct routes in input order and their first timing hypothesis;
other timings have separate diagnostic metrics. Piecewise-linear alignment uses all reference
timestamps with exact gap extents. Coverage uses strict ADE distance below epsilon. Empty
candidate sets yield null errors/rates. Collision tolerance expands supplied closed AABBs;
speed and directed-corridor tolerances affect evaluation only. Segment denominators include
stationary dwell. These checks do not certify Blender mesh collision, obstacles or clearance.

The output tree above contains effective configuration, experiment/source identity, all gap
candidates/Events, per-K metrics, JSON and Markdown summaries, optional RRDs, and a completed
artifact digest inventory. The replay package archives exact consumed JSON bytes, relocated
references, the source patch, untracked source contents and uv lock. Restore the recorded commit,
Python version and source/lock state in a separate checkout, then run its replay config into a
fresh output directory. Determinism covers observations, gap boundaries, candidate ordering and
metric values under deterministic search budgets; wall runtimes, operational timeout triggers
and SDK recording metadata remain execution-dependent. Summary physical counts cover all timed
hypotheses and repeat across K rows; inference runtime is per case, not additive per gap.

Known case-input contract rejections save structured JSON/Markdown failure diagnostics
and NOT_RUN metrics, then re-raise the original exception. They produce no successful
artifact inventory, candidates or invented search termination. Unknown consumer exceptions
propagate unclassified. Experiment/metric configuration validation still fails before
creating output. Valid empty results retain null errors/rates and false Coverage; summaries
include rejection reasons, observed endpoint cameras, search metadata and NO_REFERENCE.

MockDataset and BlenderDataset share the same sanitized JSON/provider contract. The Blender
adapter requires an asset digest and does not load a Blender scene. A replacement dataset
therefore does not modify Graph, Top-K, reconstruction, metric or Rerun algorithms. Actual
camera calibration is independently exportable using the command above; Rerun separates its
calibrated poses/frustums from navigation anchors. Trusted projected samples, explicit plane
mapping, source/context bindings and authorized graph/topology data remain producer obligations.
School walkability, stairs, walls/obstacles, clearance, floor connectivity and semantic endpoint
alignment remain blocked on scene annotation/review. Real CV, ReID, Semantic Ranking, databases,
Web/Three.js and high-concurrency testing remain outside this scope.
