# Phase 1 benchmark protocol / Phase 1 正式實驗協定

[繁體中文](#繁體中文) | [English](#english)

Protocol version: `phase1-benchmark-protocol-v1`.
Machine-readable specification: [protocol_v1.json](../configs/benchmarks/protocol_v1.json).
Formal setting status: **UNRESOLVED_RESEARCH_SETTING**; formal execution is disabled.

## 繁體中文

### 協定範圍與執行條件

本文件先固定 Case 的問題、比較單位、指標定義、資料缺失處理與圖表格式，讓人工標記
完成後沿用同一套協定。尚未核准的研究參數在 config 保持 `null`，不能用 regression
預設值補上。`protocol_v1.json` 是 protocol specification，不能直接當作
`amidst.benchmark --config` 的 `ExperimentConfig`；runner 的現有操作見
[BENCHMARK](BENCHMARK.md)。本輪未執行 Blender Cases 1–3；Case 4 保留定義並暫緩。

正式執行前須確認以下 source-bound 證據：人工核准的 WALKABLE 與 collider geometry、
floor planes、camera→plane binding、clearance／contact／ownership policy，以及明確的
navigation／camera topology、正式 MetricConfig 和 baseline／ablation 設定。Validator
發現名稱與幾何問題供人工審查；沒有自動賦予 floor／geometry authority。AREA 與 PORTAL
annotation 不代替可信實體表面；不由 `group_*`／`Cube.*` 推定角色，不由 stair box
建立跨樓層連通。現有 school gate 見 [SEMANTICS](../data/scene_audit/SEMANTICS.md)。

同一個 case、method、run 以獨立 gap 為 reference metrics 的量測單位，case inference
runtime 則以整個 case 為量測單位。每次比較必須保留 case／event／method／run identity、
結果種類及 effective MetricConfig，不能混合 mock 與 Blender research results。GT 只在
獨立 evaluation 讀取，禁止進入 provider、Graph、route/timing 選擇、baseline 排序或 Agent。
GT poisoning 導致 inference 改變時，該 run 為 invalid，與一般 metric target miss 分開記錄。

### Cases 1–4

| Case | 研究問題 | 必要場景語意 | 預期 observations／ambiguity | 失敗或阻塞條件 |
| --- | --- | --- | --- | --- |
| **1 — Single Feasible Route** | 可否由兩端的可見證據重建唯一合法 blind-gap route？ | 同層 WALKABLE；相關 WALL／OBSTACLE ownership；可接近的 PORTAL／anchors；已核准 camera-plane；唯一合法 route／topology | Cam A gap 前 samples → 無座標 GAP → Cam B gap 後 samples；route 唯一，但 timing 可不唯一 | 已知有可行路徑卻 `NO_FEASIBLE_PATH`；端點／floor 錯誤；物理違規；initial target miss；未完成 search 必須標原因 |
| **2 — Branching / Multi-Hypothesis** | Top-K 是否保留與 reference 相容的合法分支路徑？ | 有分歧的 WALKABLE；WALL／OBSTACLE／clearance authority；兩側可達 PORTAL；多條明定 directed routes；camera-plane | 方法共用可見入口／出口；分支內部無 observation；相同端點可有多條 route；同一路徑多種 timing 不增加 K | 指定 K 未保留相容 route；把 timing duplicate 當 route；把 bounded search 當 exhaustive；物理違規 |
| **3 — Temporal Slack / Long Gap** | gap 遠長於最低行走時間時，是否保留合法 timing、detour、dwell alternatives？ | WALKABLE 與合法 detour routes；collider／clearance authority；可達端點；speed／timing policy；camera-plane | 兩端 timestamp 差距長；不虛構 gap evidence；慢速、departure dwell、已有長 route 都可是假設，不能宣稱行為機率 | speed／temporal violation；靜默只留最短 route；以 GT 挑 timing；將固定 gap duration 誤當零 travel-time error；物理違規 |
| **4 — Cross-floor / Stair** | 是否只經核准且連續的樓梯，連接不同樓層？ | floor_from ≠ floor_to；接 WALKABLE 的 STAIR_ENTRY／STAIR_EXIT；連續 STAIR_PATH；合法升降方向；clearance、slab opening、cross-floor topology 與 camera-plane | 不同樓層的可見端點，中間 position-free gap；僅保留人工核准的 stair route／timing ambiguity | entry／path／exit 缺失；無核准 stair 的 cross-floor edge；Z 不連續／方向錯；淨空不足／無 slab opening；物理違規 |

每個 Case 都要求 Projection Error、ADE、FDE、minADE@K、minFDE@K、Coverage@K、
Candidate Count、Feasible Candidate Recall、Collision Rate、Constraint Violation Rate、
Impossible Transition Rate、Path Length Error、Travel-time Error、Runtime、Termination
Reason，以及已有的 Search Nodes／expanded states。未實作或缺 authority／reference 的
required metric 顯示 `N/A`／`NOT_EVALUATED`，不能當成驗收通過。

PRD 的 30 m corridor、20 s／180 s gap 是 case 意圖的示例，不是已存在的 school route。
實際長度、timestamp、branch inventory 與 observation samples 必須由之後核准的 dataset
明定。Cases 1–3 目前狀態是 `BLOCKED_SCENE_SEMANTICS_AND_FORMAL_SETTINGS`；Case 4 是
`DEFERRED_NOT_EXECUTED_THIS_ROUND`，synthetic stair regression 也不解除此暫緩。

### 指標定義與可取得性

所有距離用 3D Euclidean distance，座標單位為公尺、時間為秒；沿用已確認的
1 Blender unit = 1 m。`P_1` 指 deterministic 輸入順序第一條 distinct route 的第一個
timing；不使用 GT 挑 route 或 timing。Top-K 同樣只選每個 distinct candidate 的第一個
timing。ADE／FDE 對 primary route 的量測與 minADE／minFDE 的 evaluation oracle minima
分開呈現；後者不得用於 inference 或 baseline 排序。

| Metric | 定義／分母／單位 | 現有 runner 可取得性 |
| --- | --- | --- |
| Projection Error | matched visible `PROJECTED` sample 的 `‖projected_t − reference_t‖₂`，表格用其 arithmetic mean；保留 samples count，m | 尚未輸出 benchmark metric；camera export pose parity 不能代替 |
| ADE | 對全部對齊 reference timestamps 的 3D error 取 arithmetic mean，m | primary trajectory metrics 可取得 |
| FDE | reference 最後 timestamp 的 primary trajectory 3D error，m | primary trajectory metrics 可取得 |
| minADE@K／minFDE@K | 至多 K 個 distinct primary routes 的各自 ADE／FDE minimum，m | 已輸出；兩個 minima 可能來自不同 route |
| Coverage@K | `1[min D(P_k, P_GT) < epsilon]`，每 gap 為 indicator，aggregate 為 fraction | 已輸出 synthetic 設定；正式 D／epsilon 未核准 |
| Candidate Count | timing 展開前 emitted distinct candidate IDs 數，routes | 已輸出；empty result 為 0 |
| Feasible Candidate Recall | emitted route set 與獨立可行 route inventory 的交集數／該 inventory 數，fraction | 未輸出；需同 eligibility bounds 下的 exhaustive inventory；inventory 不完整或分母為 0 時 N/A |
| Collision Rate | 與至少一個 authorized collider 相交的 continuous timed segments／所有 consecutive timed-point pairs，包含 stationary dwell，fraction | 僅 supplied closed AABB；不代表 Blender mesh clearance |
| Constraint Violation Rate | collision **或** speed **或** directed corridor violation 的 segments／同一 segment 分母，fraction；同段不重複加算 | 已輸出 configured constraints；未核准 Blender authority |
| Impossible Transition Rate | 不被 authority 允許的 directed camera／floor transitions／distinct emitted routes 的全部 declared transitions，fraction | 未輸出；不以 corridor rate 代替；沒有 transition 或 authority 時 N/A |
| Path Length Error | `abs(L(P_1) − L(P_GT))`；L 為完整 3D polyline 各段長度總和，m | 未輸出；須一致的時間 extent／reference sampling |
| Travel-time Error | `abs(T_moving(P_1) − T_moving(P_GT))`，排除 explicit dwell，s | 未輸出；需另核准 reference movement／dwell annotation policy；不以固定 gap 起訖時間差產生必然為 0 的指標 |
| Runtime | 實測 case inference wall time，s；與 run total runtime 分開 | 已輸出；排除 evaluation／reporting；同 case 各 gap 重複的值不能相加 |
| Termination Reason | 原始 Graph termination category，附 search complete | 已輸出；input rejection 是獨立 status，不能虛構 Graph termination |
| Search Nodes | `expanded_nodes`，expanded states；不是 generated／visited states 的估計 | 已輸出；其他 diagnostics 若無則 N/A |

現有 physical rates 量測所有 emitted timing hypotheses，包含 alternate timing；reference
Top-K 指標只量測 primary timings。Report 必須保留這兩個 population，不能把各 K 重複
列的 physical counts 再相加。正式 collision/contact/clearance 與 corridor/speed tolerance
仍需核准；MetricConfig tolerance 不放寬 Graph 可行性條件，也不建立 inference ownership。

### Coverage 與時間對齊

正式 config 的 D、epsilon、epsilon unit、K values、temporal alignment、interpolation
與 reference sampling 均保持 `null`／`UNRESOLVED_RESEARCH_SETTING`，正式執行前必須
固定並版本化。`epsilon` 只接受 finite、**strictly positive** 數值，不支援 epsilon = 0；
Coverage 使用嚴格 `<`，不改成 `≤`。D 的 unit 必須與 epsilon 一致。K 是正整數、不可
重複；K 大於 available routes 時使用已有 distinct routes，不補 duplicate。

現有 [synthetic MetricConfig](../configs/metrics/synthetic_regression_v1.json) 用於 plotting
regression：D=ADE、epsilon=1e-6 m、K=[1, 2, 3]；piecewise-linear interpolation 到**全部**
GT timestamps，candidate/reference 起訖時間須精確一致，禁止 clipping／extrapolation。
這是既有支援的 policy，不是正式研究選擇；policy string 改名不等於實作新算法。不支援
的設定應拒絕，不能自行替換為最接近的已有設定。若正式選擇不同 D／alignment 等 policy，
須先作獨立、明確授權的實作與驗證；本輪不修改正式 evaluation semantics。

Valid reference + empty candidate set：Coverage=0，ADE／FDE／min errors／physical rates
為 `N/A`，Candidate Count=0，保留 `NO_FEASIBLE_PATH` 等實際 termination。沒有 reference
時 reference metrics（含 Coverage）為 `N/A`，保留 `NO_REFERENCE`；不可把未評估當
Coverage=0。Input rejection／failed case 保留 row 與原因，未量測欄位為 `N/A`，不當成
零誤差或完整搜尋。Missing metric 使用 JSON `null` 和表格 `N/A`，不 fabricated value。

### Baseline 與未來 interface

| ID／method_id | 比較定義 | 本輪／下一階段狀態 |
| --- | --- | --- |
| A／`shortest_path` | 在相同 authorized geometric graph 找一條 canonical shortest route；共用 timing policy，不套 elapsed-time 或 camera-topology filter | 下一階段 deterministic baseline；collision filtering 仍需 inference authority |
| B／`geometry` | 在同一 directed geometric graph deterministic 列舉多條 route；共用 timing，不套 elapsed-time／camera-topology filter | 下一階段 deterministic baseline；不得創造未核准 floor／stair edge |
| C／`spatiotemporal` | Full deterministic graph：同一 geometry，加 explicit directed camera topology、travel-time constraints 與核准的 collision filter | 下一階段 deterministic baseline；目前 Graph 沒有 inference collision authority，不能宣稱已完成 full physical baseline |
| D／`semantic` | C 加 source-bound、approved semantic features；physical hard constraints 保留 | 只定義 interface／比較；semantic policy 與權重未定案，不實作 |
| E／`agent` | 在 D 的 deterministic feasible candidates 上由 Agent rerank，不能生成 geometry、放寬 physics 或讀 GT | 只定義 interface；不開始 Agent Semantic Ranking |

A/B 在比較中保留 geometric floor／stair authorization，移除 camera-topology filter 不等於
建立任意房間／樓層捷徑。A 的 requested K 不變，但實際至多一條 route；不得補同一路徑
來湊 K。C 的 collision authority 未完成時，只能標明實際 configured-constraint regression
的能力，不能冠名為通過正式全物理限制的結果。D/E interface 接收 source/context-bound
observations、feasible candidates、公開 semantic features、政策版本；輸出 candidate-ID
permutation／可追蹤 scoring provenance。GT、evaluation metrics、隱藏 trajectory 都不輸入。
上述 A–C 定義可作下一階段起點；演算法、排序／tie break 與詳細 mask 尚需 freeze。

### Single-factor ablation

所有 ablation 以 C 為 reference，只有一個主要因素改變；保留相同 dataset bytes、case／
gap IDs、source／authority snapshot、camera／plane、seed、metric config bytes、requested
candidate K、observations／endpoints、reference、其餘 movement／timing／eligibility／
search budgets，以及 runtime 的 hardware 與量測邊界。因指定 factor 導致的實際 candidate
count、search nodes 與 timing 是量測結果，不能人為調整。

| Ablation | 唯一改變 | 明確保留／gate |
| --- | --- | --- |
| remove travel-time constraints | 關閉 travel-time eligibility filter | 相同 timing policy、topology、collision、K／budgets |
| remove collision constraints | 關閉 inference collision filter | 須先有已核准且已實作的 inference collider authority；其他物理／time／topology 不變；independent evaluator 仍量測 collision |
| remove topology constraints | 關閉 **camera-topology** filter | authorized geometric adjacency、floor／stair connectivity、collision／time 不變 |
| shortest-path only | 將 candidate enumerator 換為 canonical shortest route | C 的其他 filters 不變，requested K 不變；實際可少於 K；與多因素的 Baseline A 分開 |
| full deterministic graph | 不改 factor，作為 reference | 保留完整 C 設定 |
| + semantic information（未來） | C 加一份核准 semantic policy | 本輪 interface only；weights／policy 未定案 |
| + Agent ranking（未來） | D 只替換 ranking policy | 同一份 feasible candidates、semantic features 與硬限制；本輪不實作 |

Baseline A–C 是方法比較，可有多個**明列**因素不同，不能偽裝成 single-factor ablation。
Run 必須記 method／ablation ID 與 changed factor；一個 ablation 同時更改 time、collision
和 topology 不符合 protocol。

### 分類驗收與 INITIAL_TARGET

分別報告 `GEOMETRIC_ACCURACY`、`PHYSICAL_VALIDITY`、`TOP_K_COVERAGE`、
`TEMPORAL_VALIDITY`、`SEARCH_BEHAVIOR`、`SYSTEM_RUNTIME`。每類列 actual metrics、
sample/missing counts、authority／setting status、適用 target，以及 failure／incomplete
diagnostics；不合併成單一 overall PASS／FAIL。Missing required metric 為 `NOT_EVALUATED`；
未核准研究參數維持 `UNRESOLVED_RESEARCH_SETTING`。低幾何誤差不能抵銷碰撞／錯誤樓層。

[PRD §19](PRD.md#19-initial-acceptance-criteria) 的值保留為 **INITIAL_TARGET**：Case 1
ADE/FDE ≤ 0.5 m；Case 3 FDE ≤ 1.0 m；overall Coverage@3 ≥ 0.9；每個正式輸出的 candidate
Collision Rate=0、Impossible Transition Rate=0。Overall 的 case/run weighting 尚未核准，
不能先把不同 case 的 mean 平均後宣稱達標。後續 threshold 校準須保留理由、protocol／
metric version 及前後結果。Fake 0-error／zero-collision 是 regression evidence，不是正式
研究結果；缺 collider 或僅 AABB fixture 的零碰撞不能符合 Blender physical acceptance。

### 統一比較輸入、聚合與圖表

使用既有 runner output 的 `metrics.json` 與 `summary.json`，或明列 case／method／run／
metric identity 的 normalized result，從共用 root 執行：

```sh
uv run python -m amidst.benchmark_report \
  --input <benchmark-output-root> \
  --output data/reports/benchmark
```

Multi-method 可按 `results/<case>/<method>/<run>/` 放置各 run；不要在 path 裡放 GT
排名。單一既有 run 可以含多 case。Case 數量、method 數量與 K 從 inputs 讀取，不固定
Case 1–3 或 K=3。Report 資料契約與 CLI 支援細節以 generator 的說明為準。

同 case／method／K 的 ADE／FDE／min errors／Coverage 按可評估 gap records 取 mean，
多 runs 時保留 run／gap counts。Physical rates 有 numerator／denominator 時 pooled
counts；只有 rate 而無 counts 時明列 `mean_of_reported_rates`，不偽稱 pooled rate。
Candidate count 每 run 對 measured gaps 取 mean；search expansions 每 run 對獨立 gaps 加總；
runtime 每 run 只取一次 case inference value，再於 matched runs 取 mean。Termination
categories 每 gap 只計一次。不同 case 維持分別呈現，不靜默選 cross-case weighting。
Missing-reference gaps 不參與 reference metric mean，顯示 `NO_REFERENCE` 與分母；有
reference 的空候選 Coverage=0。Failed／missing cases 仍列出 status 和 N/A。不同 K 的
minima 不混合；run 缺少指定 K 時顯示 N/A 與 warning，不能代用另一個 K。
同一 aggregate group 的 dataset、seed、metric settings 或 requested K 不相容時，結果
抑制為 N/A 並標 `REVIEW`；這些 runs 不能當成受控比較，也不能只在註腳警告後照常平均。

每張圖單獨輸出，不使用 subplot 拼圖。輸出 ADE、FDE、minADE@K、minFDE@K bar charts；
Coverage@K 用 K 為 x-axis、coverage fraction 為 y-axis；physical rates、path/time errors、
candidate count、expanded states、runtime、termination categories 各自輸出。每張 title
含 `SYNTHETIC REGRESSION`、`MOCK VALIDATION` 或經核准的 `BLENDER RESEARCH RESULT`；
axes 明列 units。若整個 metric 無資料，可 graceful skip 並記理由；部分資料缺失時顯示
N/A，不能補 0。圖表順序按固定 baseline ID／method identity，不依 GT accuracy 排序，
不手動調整數據；使用 matplotlib 預設配色。

Report 同時輸出 `benchmark_summary.md` 與 machine-readable `benchmark_summary.json`。
至少包含 `Case | Method | ADE | FDE | minADE@K | minFDE@K | Coverage@K | Collision |
Constraint | Runtime`，附 K、result kind、status／missing counts。Physical violations 與
geometric accuracy 必須同時可見，避免只看低 error。不存在的 Projection Error、Feasible
Recall、Impossible Transition、Path／Travel-time Error 不由其他欄位猜出。

### 未定研究設定

以下全部為 **UNRESOLVED_RESEARCH_SETTING**，沒有本輪自動採用的值：

| Setting | 人工／研究決定內容 |
| --- | --- |
| formal Coverage D | distance 定義、單位；現有實作只支援 ADE，不默認為正式選擇 |
| formal Coverage epsilon | strictly positive threshold 與尺度依據；禁止 0 |
| formal K／sampling／alignment／interpolation | K、reference sampling、完整時間 extent 與 interpolation policy |
| physical clearance | 人物 collision envelope、minimum clearance 與 tolerance |
| contact semantics | 邊界接觸算 collision、可容許的 surface contact／floor contact |
| geometry authority | source/context-bound objects／faces／proxies、floor planes、可信幾何範圍 |
| camera-plane binding | 每台 camera 對應的核准 plane、height／normal／extent；calibration parity 不代替 binding |
| obstacle ownership | movement collision、camera occlusion 或兩者；helper／annotation／decorative exclusions |
| final baseline protocol | A–C 的 algorithms、tie breaks、constraint masks、search budgets 與 timing；D/E 只保留 interface |
| feasible route inventory／travel-time reference | recall 的 exhaustive feasibility inventory；moving-time／dwell annotation 定義 |
| overall weighting／acceptance calibration | 跨 case/run weighting、initial targets 是否需校準 |

核心語意邊界記於 [ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)。圖表與 validator
infrastructure 完成不會解決這些 research choices，也不啟動 Agent、Phase 2、完整
Experiment Reproducibility 工程或最終 Blender／Rerun presentation pipeline。

## English

### Scope and gates

This protocol defines reusable questions, measurement populations, comparisons, missing-data
behavior and report format. The JSON is a protocol specification, not an executable
ExperimentConfig. All unapproved formal settings stay null with
`UNRESOLVED_RESEARCH_SETTING`; formal execution remains disabled. Blender Cases 1–3 have
not been executed, and Case 4 is explicitly deferred. Synthetic fixtures validate tools
without establishing school geometry or research success.

Formal runs require source-bound human-approved walkable/collider geometry, floor planes,
camera-plane bindings, clearance/contact/ownership policy, authorized navigation and camera
topology, an approved MetricConfig and frozen baseline/ablation definitions. Annotation
boxes, name heuristics and validator proximity graphs do not grant authority. Preserve the
original scene. Ground Truth belongs only to independent evaluation/debug consumers and
must not influence inference, route/timing selection, baseline ordering or Agent input.

### Cases and measures

**Case 1** asks whether observed endpoints recover the single authorized same-floor route.
It requires approved walkability, relevant colliders, accessible portals/anchors, camera-plane
bindings and explicit single-route topology. Visible entry/exit samples surround a position-free
gap. Route ambiguity is absent, while timing ambiguity may remain. Known-feasible empty search,
wrong endpoints/floor, physical violations and target misses are separately reported.

**Case 2** asks whether Top-K retains a reference-compatible route among authorized branches.
It requires branched walkability, collider/clearance authority, two-sided portals and multiple
directed routes. All methods receive the same visible endpoints without branch-interior evidence.
Timing alternatives do not count as distinct routes. Missing reference-compatible routes,
duplicate inflation, physical violations and incomplete-search misrepresentation are failures.

**Case 3** asks whether long gaps retain admissible slower movement, detours and explicit dwell.
It requires approved routes, colliders, endpoint access, camera bindings and declared speed/timing
policy. Shared endpoint times do not identify actual behavior. Speed/time violations, silently
collapsing ambiguity, truth-selected timing and tautological zero travel-time errors are failures.

**Case 4** asks whether different floors connect only through an approved continuous stair.
It requires connected entry/path/exit, different approved floors, explicit ascent/descent
directions, clearance, slab openings and cross-floor topology. Missing stair authority,
discontinuous/wrong-direction Z, slab traversal and physical violations fail validation.
The protocol is retained but no formal Case 4 run is authorized this round.

All cases require the metrics in the Chinese definition table and JSON. Displacement errors
and path-length error use metres; travel-time error and runtime use seconds; rates use fractions;
counts identify routes or expanded states. Primary ADE/FDE score the first timing of the first
distinct route in caller order. Minima score up to K primary distinct routes and are evaluation
diagnostics, never ranking inputs. Collision and constraint rates use all emitted timed
hypotheses and consecutive timed-point pairs including dwell; overlapping constraint violations
count once per segment. Do not multiply physical counts by repeated K rows.

Projection error needs matched visible reference points, not calibration-matrix parity. Feasible
candidate recall requires an independently exhaustive feasible-route inventory with the same
eligibility bounds. Impossible-transition rate needs an authorized directed-transition inventory
and counts distinct-route transitions, not corridor violations. Path-length error compares full
3D polyline lengths. Travel-time error compares moving-time durations excluding explicit dwell;
an independently approved dwell/reference policy is required because exact gap extents alone
would produce tautological zero duration error. These additional metrics are not exported by
the current runner and must remain N/A until independently supplied. Runtime is measured once
per case, excluding evaluation/reporting; expanded nodes use the actual exported counter.

### Coverage, baselines and ablations

Coverage is `1[min D(P_k, P_GT) < epsilon]`. D, epsilon and its unit, K, temporal alignment,
interpolation and reference sampling are config-driven and unresolved for formal research.
Epsilon must be finite and strictly positive; zero is unsupported. K contains unique positive
integers and counts distinct routes, never duplicated timings. The separate synthetic profile
uses ADE, 1e-6 m, K=[1,2,3], piecewise-linear alignment at every reference timestamp and exact
time extents without clipping/extrapolation. Unsupported policies require separate implementation;
renaming a config string cannot implement them.

Baseline **A** (`shortest_path`) selects one canonical shortest authorized geometric route;
**B** (`geometry`) enumerates deterministic geometric routes; both share timing policy and omit
elapsed-time/camera-topology filters. **C** (`spatiotemporal`) adds explicit camera topology,
travel-time and approved inference collision constraints. Geometric floor/stair authorization
is preserved in every method. Current Graph inputs have no approved collider authority, so C
cannot yet be described as a complete physical school baseline. **D** (`semantic`) adds approved
source-bound semantic features, and **E** (`agent`) reranks deterministic feasible candidates;
both are interface definitions only. No Agent work starts here, no new geometry is generated,
and hard feasibility/GT isolation remain intact. Algorithms, tie breaks, masks and budgets await
final approval rather than being silently chosen by this document.

Single-factor ablations independently remove travel-time, collision or camera-topology filters;
the collision experiment is gated on approved implemented inference authority. The shortest-only
ablation changes only C's enumerator, preserving C's other filters and requested K. It is distinct
from Baseline A. Full deterministic C is the reference. Future semantic and Agent variants each
change only their named policy. Dataset bytes, case/gap IDs, scene/authority, calibration/planes,
seed, metric bytes, requested K, observations, reference, other timing/eligibility/budgets and
runtime boundary/hardware stay fixed. A–C method comparisons may change multiple declared
factors and must not be presented as single-factor ablations.

### Acceptance and reports

Report `GEOMETRIC_ACCURACY`, `PHYSICAL_VALIDITY`, `TOP_K_COVERAGE`, `TEMPORAL_VALIDITY`,
`SEARCH_BEHAVIOR` and `SYSTEM_RUNTIME` separately, with measurements, missing/sample counts,
authority/settings and termination diagnostics. There is no overall PASS/FAIL. PRD values remain
`INITIAL_TARGET`: Case 1 ADE/FDE ≤0.5 m, Case 3 FDE ≤1 m, overall Coverage@3 ≥0.9, and zero
collision/impossible transitions for every formal output candidate. Overall weighting and
calibration remain unresolved. Missing required metrics are NOT_EVALUATED, and synthetic zero
errors/zero AABB collisions cannot establish Blender research acceptance.

The report command above accepts existing runner outputs or explicit normalized records.
Case/method/run grouping and K come from inputs. Use one chart per metric, clear units and a
title declaring SYNTHETIC REGRESSION, MOCK VALIDATION or approved BLENDER RESEARCH RESULT.
Cases/methods with missing data or failures remain visible; wholly unavailable metrics may be
skipped with recorded reasons. Never fill missing values with zero, order methods by Ground Truth,
adjust measurements for appearance or prescribe colors beyond matplotlib defaults.

Reference errors and Coverage use evaluated gap records with explicit counts; physical rates
pool provided numerators/denominators, or explicitly label means of reported rates when counts
are absent. Keep case inference runtime once per run, independent gap search counts once, and
termination counts independent of K. Candidate counts are averaged over measured gaps per run,
then across matched runs. Show run/gap counts and missing/failure counts; do not silently
combine different cases. A valid reference with no candidates has Coverage=0 and N/A errors/rates;
NO_REFERENCE or failed/unevaluated records have N/A Coverage, not an invented zero. Summary JSON
and Markdown include Case, Method, ADE, FDE, minADE@K, minFDE@K, Coverage@K, Collision,
Constraint and Runtime, with K, result kind and status. Never mix minima measured at different K;
missing requested K remains N/A with a warning.
Incompatible dataset, seed, metric settings or requested K within an aggregate group suppress
the aggregate to N/A with REVIEW rather than yielding an ordinary controlled comparison.

Formal Coverage D/epsilon, K/sampling/alignment/interpolation, physical clearance, contact
semantics, geometry authority, camera-plane binding, obstacle ownership and the final baseline
protocol remain unresolved. Feasible-route inventory, moving-time reference annotations and
overall weighting/calibration also need approval. Tooling completion does not resolve these
choices or authorize Phase 2, Agent Semantic Ranking, a complete reproducibility engineering
project, or a final Blender/Rerun presentation pipeline.
