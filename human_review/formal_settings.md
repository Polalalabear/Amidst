# 最小 Projection / formal-setting review

狀態：**HUMAN_REVIEW；本輪沒有核准、沒有 formal Case 執行**。
本頁只有 HR-02、HR-03、HR-04；geometry HR-01 決策由首頁另列。每個項目的四種決策均為
**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。APPROVE 選下方一個完整 profile，
不用自行計算。所有 profile 必須在 formal dataset / benchmark 之前鎖定；執行後禁止改值。

[settings_evidence.json](settings_evidence.json) 保存每個 source path / SHA-256、source scene
hash、完整 camera calibration / pose、可見 endpoint frame IDs / UV，以及所有下列換算值。
Inspector 只讀 approved authority、source calibration 與 sanitized inference observations；
不讀 GT、evaluation、simulation recipe 或 trajectory plan。

| Setting | Current status | Existing evidence | Recommended final value | Why |
|---|---|---|---|---|
| Units / physical policy | APPROVED；直接沿用 | architectural_scale + physical_authority_policy | 0.0247 m/BU；radius 0.30 m；height 1.70 m；clearance 0.05 m；portal 0.05 m/側、垂直 0.10 m；contact 0.001 m | 既有明確核准，不重審 |
| K / Top-K population | 使用者固定；直接沿用 | Sprint K；MetricConfig | K=1/2/3；每 distinct route 第一 timing | 不用 GT 選 route / timing |
| Sampling / alignment / interpolation | 自動採目前 evidence grid + 唯一支援 contract | 各 sanitized stream 50 timestamps、步距 0.2 s；MetricConfig | 5 Hz；含 formal GAP 起訖；完整 reference timestamp extent；PIECEWISE_LINEAR | 取樣頻率可直接計算；不丟棄難樣本、不增加演算法 |
| Coverage distance | 自動採現有唯一實作 | MetricConfig trajectory_distance_metric | ADE；3D Euclidean arithmetic mean；嚴格 `< epsilon` | 不新增 distance 定義 |
| Landmark / floor binding | **HR-02** | office context + approved WALK_1F_OFFICE floor | 保留 source-bound marker；每次扣固定 Z offset 到 floor-contact | 解決 elevated marker 不能直接作 body footpoint 的問題 |
| Coverage epsilon | **HR-03** | protocol 0.50 / 1.00 m initial target 尺度 | **0.50 m**；可選 1.00 m | 是研究容差，不能由 synthetic epsilon 或結果自動核准 |
| Speed / timing | **HR-04** | pilot builder 32 BU/s；ReconstructionPolicy | **0.7904 m/s**；slack 1 s；departure dwell 啟用 | 固定既有模型速度上限；它不是實測人物速度 |
| Numeric precision / uncertainty | 直接沿用，無人工 noise 決策 | MetricConfig；physical-collision-numerics；projection policy | corridor 1e-6 m、speed relative 1e-12；現有 physical solver error budget；pixel sigma undeclared→UNAVAILABLE | 數值精度不代替研究容差；不捏造 uncertainty probability |
| Methods / deferred work | 既有 protocol；直接沿用 | protocol_v1 A/B/C masks / supported ablations | A shortest path；B geometry；C spatiotemporal；Case 4 DEFERRED；Phase 2 FROZEN | 不擴大方法、跨 case weighting 或 Stair review |

## HR-02 — 可見 landmark 如何對應地板上的人物落點

Location:

- Floor：1F。
- AREA：AREA_1F_OFFICE；WALKABLE：WALK_1F_OFFICE，限定 geometry 決策核准的 local domain。
- PORTAL：本 binding 不核准任何 portal；是否需門洞由合法 route / endpoint validation 自動判斷。
- nearby object：approved source floor `group_0`；不核准整個 object 作 collider。
- Blender Outliner 搜尋：`WALK_1F_OFFICE`、`AREA_1F_OFFICE`、
  `CAM_1F_AUDITORIUM_FRONT`、`CAM_1F_AUDITORIUM_REAR`。

Why it blocks:

- Case 1–3 的 visible→GAP→visible endpoint 都必須對應核准 floor-contact reference。
- 既有 plane 是 elevated landmark；直接作 footpoint 會讓人物 body 高約 1.36 m，
  floor support、collision、ADE 與 timing 的座標語意失效。Camera 名稱不證明它只看同名 AREA。

Evidence:

- `data/finalization/local_run/dataset/inference/office/context.json`，SHA-256
  `56a131626b7c9382f260cb0d088abf6d38ff13127f76d3b5233dd2abdf87dc70`。
- `floor_authority_map.json`：WALK_1F_OFFICE source support **APPROVED**，
  Z=**20.07884979248047 BU / 0.49594758987426757 m**；normal `(0,0,1)`。
- Existing landmark plane：Z=**75.12884788513183 BU / 1.8556825427627563 m**；
  差值 **55.049998092651364 BU / 1.3597349528884888 m**。
- Office annotation bounds：BU min `(1145,1710,15)`、max `(1495,2310,155)`；
  這是 annotation extent，不能代替 physical certificate。
- Front camera：BU `(2025.24267578125,2314.5078125,153.21405029296875)`；
  Rear camera：BU `(2024.8048095703125,1580.67431640625,153.23199462890625)`。
  Exact intrinsics / pose / meters、每 camera observed frame IDs / UV 在 evidence JSON。
- Office 50 個 exact timestamp groups：Front 21 observed、Rear 5 observed；
  **同步雙視角 0**。Corridor 0/50、Auditorium 33/50 僅為歷史 limitation evidence，
  這個 approval **不核准那兩個 stream 的 binding 或 routes**。
- Source `blender/school_v3.blend` SHA-256
  `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`；468,300,506 bytes。
  Frames / continuous geometry preview 由 review 首頁與 `frames/` 提供；不是 GT overlay。

Current machine conclusion:

- 已確定：source calibration、pixel observations、approved floor height、offset 均可獨立算出；
  offset 小於已核准 1.70 m body height。雙視角缺失可合法 fallback，不能標 inference failure。
- 尚未確定：marker 與人物落點的語意、camera 對所選 local domain 的正式 binding、
  GAP endpoints 的 exact scope certificate。既有 context 的 authority 是 diagnostic。

Recommended decision:

**APPROVE / SOURCE_BOUND_RIGID_LANDMARK_OFFSET（建議）**：把 marker 定義為 upright
research cylinder 上的固定 source-bound marker；單視角對 landmark plane 投影、雙視角
對同一 marker triangulate，兩者都以固定 offset 轉成 floor-contact，保留 XY、source
calibration、method、confidence、uncertainty、provenance。所有新 formal observations 重新產生；
footpoint 使用 exact approved source support，**不沿用 legacy foot margin**。

另一個 APPROVE profile：**FLOOR_CONTACT_MARKER**，marker offset=0 BU / 0 m，
新 2D observations 直接觀測足點並重新 raycast / export。若足點不可見，保持 GAP；
不得由另一 marker 或 GT 偽造可見 evidence。

兩個 profile 都允許 **EXACT_TIME_MULTIVIEW → SINGLE_VIEW_FIXED_PLANE** fallback，
保留 LOW_CONFIDENCE / UNAVAILABLE，沒有 confidence sample rejection；surface-constrained
school inference 保持 N/A。source/derived-scene calibration、FOV、endpoint containment、
topology、camera→scope 與 body support 由程式驗證；APPROVE 不覆蓋失敗。

Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。

## HR-03 — Coverage 的正式 ADE 容差

Location:

- Floor / AREA / PORTAL / nearby object / Outliner：N/A；這是 Case 1–3 共用的 protocol 設定。

Why it blocks:

- Case 1–3 的 Coverage@K 必須預先固定 finite strictly-positive epsilon。
  未固定時 formal Coverage 只能 N/A；不能用 diagnostic/synthetic 的 1e-6 m 補值。

Evidence:

- `configs/benchmarks/protocol_v1.json` Coverage formal epsilon=null，status=UNRESOLVED。
- 同一 protocol 的 Case 1 ADE/FDE INITIAL_TARGET=0.50 m、Case 3 FDE INITIAL_TARGET=1.00 m。
  這是提案尺度依據，**不是既有 Coverage approval、也不是測量結果**。
- `src/amidst/domain/metric_config.py` 目前唯一支援 D=ADE、嚴格 `<`。
- 項目是研究尺度，不適用 screenshot / face / location measurements。

Current machine conclusion:

- 已確定：D、units、comparison、K、alignment / interpolation 支援範圍。
- 尚未確定：研究者接受的 Coverage error tolerance；沒有以 accuracy score 選 epsilon。

Recommended decision:

**APPROVE / ADE_EPSILON_0_50_M（建議）**：全 Case / method / K 共用 ADE **< 0.50 m**，
與既有 Case 1 目標尺度一致。另一 profile **ADE_EPSILON_1_00_M**：全體共用 **< 1.00 m**。
兩個都是新增明確研究 approval，不改其他 metric 公式或 initial targets，不推導 overall PASS。
Case 1–3 跑完後不得換 profile；變更須新 dataset/protocol version。

Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。

## HR-04 — 固定速度上限與長 GAP 的 timing 假設

Location:

- Floor：核准的 1F local domain；AREA：AREA_1F_OFFICE；PORTAL：只使用另行核准的 route。
- nearby object / Outliner：N/A；這是 source-bound movement/timing policy。

Why it blocks:

- Case 1/2 的 travel-time feasibility 與 Case 3 的 long-GAP、detour、temporal slack
  需要一個正式 speed ceiling；未核准時不能聲稱 speed pruning 或 timing 合法。
- 既有 32 BU/s 是 diagnostic model setting，不是量測人物速度。

Evidence:

- `src/amidst/datasets/pilot_topology.py`：configured `max_speed_scene_units_s=32.0`。
- 乘已核准 architectural scale，得到 **0.7904 m/s**；不由 trajectory 或結果估計。
- `src/amidst/domain/reconstruction.py`：slack=1.0 s、include_dwell_hypotheses=True；
  existing `blind_gap.py` 只提供均速 primary，以及 departure waypoint dwell alternative。
- `protocol_v1.json` Case 3 允許慢速、已有長 route、explicit dwell；沒有行為機率。

Current machine conclusion:

- 已確定：現有兩個 timing profiles 都有 contract 支援；同一 GAP timestamps 不改，
  dwell 不增加 distinct route K；取樣 5 Hz 由 timestamp grid 自動鎖定。
- 尚未確定：是否核准這個 diagnostic ceiling 為 formal research model；不聲稱人體真實上限。

Recommended decision:

**APPROVE / EXISTING_SPEED_WITH_SUPPORTED_DWELL（建議）**：max speed=**0.7904 m/s**、
slack tolerance=**1 s**、uniform continuous primary、departure dwell alternative 啟用。
detour 僅保留已核准 routes，不生成新 geometry；不賦予機率。

另一 profile：**EXISTING_SPEED_UNIFORM_ONLY**，同樣 **0.7904 m/s / 1 s**，
include_dwell_hypotheses=False；保留慢速 / detour continuous timing，停留假設明確不評估。
不是另一個數字速度，也不依 accuracy 選 profile。Travel-time error 仍必須排除 explicit dwell；
無獨立 movement annotation 時 N/A，不用固定 GAP duration 製造零誤差。

Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。

## 全部決策後的自動工作

Owner：**agent**；以下不增加 human blocker 數，也不要求人計算 routes 或 certificates。

1. Apply bounded geometry HR-01 decisions；重新計算 exact local certificate / clearance / floor support。
2. 由 authorized geometry 證明 Case 1 route uniqueness、Case 2 多條 feasible branches、
   Case 3 speed/time feasibility；核對 camera FOV / occlusion / endpoint domain。
3. 加 additive landmark→footpoint、multi-view endpoint、formal authority wrappers。
   目前 PilotInferenceContext 為 UNVERIFIED / diagnostic-only；MetricConfig status literal
   仍是 UNRESOLVED。不能直接改名稱把歷史 artifacts 升級。
4. Case 3 的 exact GAP schedule 不是 protocol 固定數字；20 s / 180 s 是 PRD 意圖示例。
   Agent 依核准 route / speed / timing、實際 visibility 與最低 travel-time / slack 證明，
   在 dataset / metrics 前宣告並鎖定 source-bound long-GAP instance；不新增 duration 人工選擇、
   不宣稱存在唯一 duration 公式。現在的 preview 不能代替 formal long-GAP 證明。
5. 將本輪完整選擇寫入新正式 config / source-bound approval manifest，鎖 hashes；
   fresh export formal dataset，然後再 run A/B/C / supported ablations / reports / demos / fresh rerun。

**全部 APPROVE 後可直接啟動上述續跑 pipeline；舊 artifacts 尚不能立即 formal run。**
Certificate、branch inventory、可見 GAP endpoints 的任何反例都由程式回報。只有遇到真正
新的 geometry contradiction 才重新提出最少人工 gate；REJECT / KEEP_REVIEW 不解除 blocker。

Read-only evidence 重建（只會把 JSON 印到 stdout）：

```sh
.venv/bin/python human_review/inspect_review_settings.py \
  --source-asset /Users/polalabear/Developer/amidst/blender/school_v3.blend
```

若 inference evidence 位於本機 archive，另加 `--inference-root <sanitized inference directory>`；
不要指定 evaluation 或 simulation 資料夾。Inspector 不改 protocol / decisions / authority / `.blend`。
