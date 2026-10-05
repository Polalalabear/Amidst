# Work log / 已完成工作紀錄

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

### 2026-10-05 — Checkpoint 後 WALL semantic marking 與單一 pilot 閉環

只在 `phase1/pilot-dataset-and-wall-inference`，由 checkpoint
`91f4ea600805739aa9659dfef6a381d71be9a692` 繼續。重新從原始 school_v3 mesh 提取，
[candidate report](../data/scene_audit/phase1_wall_candidates_20261005.md)／JSON 與先前
結果一致：**81 AUTO_CONFIRMED_WALL patches**（1F49／2F32，7來源objects）、
**1,491 HUMAN_REVIEW patches**（674來源objects；混合object可重疊）。逐patch列出
floor、bounds、AREA／WALKABLE／PORTAL關係、verticality／height／continuity／extent／
parallel thickness evidence與理由；window／door／decoration等歧義保留review。

[Marking report](../data/scene_audit/phase1_wall_markings_20261005.md)／JSON記錄81個
`semantic_class=WALL` annotation meshes，543個既有實際polygons，存至本機ignored
`blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend`。
不重新分類完整group_*、不填rectangle／AABB／doorway、不安裝movement colliders。
保存後獨立重開：2,873原始object fingerprints與evaluated physical geometry一致，
28 PORTAL的實際annotation face intersection area為0。原始source與checkpoint snapshot
SHA均為 `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
468,300,506bytes、mtime_ns1791198236746106977保持不變；衍生scene SHA為
`b4d3394b17626bfdf35ee9b9e35c1f5a4469dd75a3e24b1a4f5f5aa58bdf4d49`。
新增marking recipe可重驗來源、candidate及保存後的faces／props／camera／portal／geometry。

僅生成一組新 **PILOT / SYNTHETIC SAMPLE**，本機ignored
`data/pilot/phase1_wall_pilot_20261005/office/`。使用原pose的
`CAM_1F_AUDITORIUM_FRONT`／`CAM_1F_AUDITORIUM_REAR`，office metadata路線
`PILOT_OFFICE_001`，1F，規劃160／採樣156.800049 scene units；10秒、5FPS、
[0,10)的**50timestamps／100PNG全部成功**。250個支撐probes與radius6／height119
完整continuous swept volume對actual triangles檢查通過。來源lineage同時綁定
衍生scene與原始source／candidate／physical geometry；81個WALL annotation排除於
planner BVH、render snapshots與occlusion rays，既有實體mesh仍提供遮擋。

獨立validation為 **PASS_WITH_REVIEW、errors=[]**：26visible／74occluded／0out-of-FOV
camera records；front21／29，rear5／45。Global body-center GAP為frames21–44
（4.2–8.8s）共24timestamps，其中19個兩視角完全沒有marker pixels、5個仍有partial body。
形成visible→GAP→visible閉環。Forward最大0.000314545px、static diagnostic plane inverse
最大0.001615262units，unexpected Projection failures0；74non-observed inputs按接口拒絕。
純2D ObservationFrame另存，inverse只讀2D／camera／獨立mesh probe固定plane；GT只在
simulation與投影後evaluation讀取。原始source與衍生asset的hash／size／mtime均保留。
獨立audit解碼／核對全部100PNG與labels／hash、100個plan/export states、100個strict2D
ObservationFrame及26個visible-center orange masks。與舊office原source render逐像素
比較，**100／100 decoded RGB完全一致、differing pixels0**，確認新增標記未改physical render。
Dataset SHA為 `77203e33a566f99936e6446133dae245231562b0a64bfc82447e5f1215d5d2df`。

另產生dataset／GT／observations／plan／validation／human-readable sample report、50frame
10秒同步GIF、trajectory map、gallery及五張代表montages：frames0／20／21／32／45
（0／4.0／4.2／6.4／9.0s）。逐張檢查visible、approach、partial-body GAP entry、完全隱藏
GAP middle與rear-camera recovery；不把point GAP宣稱為全身皆隱藏。
完整指定檢查：`uv run pytest` **847 passed in71.83s、無skips**；
`uv run ruff check .`、`uv run mypy`（72sourcefiles）與`git diff --check`均通過。
完整uv／native Blender檢查在sandbox外完成；沒有改benchmark semantics、執行正式Cases1–3、
elevator transition、merge回checkpoint branch或push。本輪到此停止，完整generation仍待
使用者pilot確認、physical scale與formal geometry／floor／camera-plane authority。

### 2026-10-05 — Phase 1 semantic scene checkpoint

使用者明確要求大斷點、push目前branch及從斷點建立新branch。起始working tree clean，
`codex/dataset-infrastructure` HEAD為 `4437ef3e468d3b18181f893906619af021042434`。
本次重新執行指定指令：`uv run pytest` **821 passed in58.64s，無skips**；
`uv run ruff check .`、`uv run mypy`（72sourcefiles）與`git diff --check`均通過。
完整pytest與uv最終檢查在sandbox外完成；uv在sandbox的macOS初始化崩潰於相同命令
rerun消失，沒有刪除或skip測試。

[Checkpoint record](PHASE1_CHECKPOINT.md) 保存branch、已驗證起點、來源fingerprint、
本機資產與續作邊界。建立ignored唯讀 `blender/working/checkpoints/phase1-semantic-scene-20261005/`
scene snapshot，SHA與目前school_v3完全一致；原來源SHA／size／mtime不變。
manifest記錄Git checkpoint SHA與四組pilot檔案hash，raw資產不隨push發布，也沒有重render。
checkpoint commit message為 `checkpoint: preserve phase1 semantic scene state`；
後續branch為 `phase1/pilot-dataset-and-wall-inference`，由相同checkpoint commit建立。
不修改正式benchmark semantics、不執行正式Cases1–3、不merge回checkpoint branch。
精確commit與push結果綁定於本輪完成回報及本機manifest。

### 2026-10-05 — Three-locale Blender PILOT comparison

起點 `c078b89`，使用者追加授權「不同場地的多個資料，並給出判斷」。完成同一
`school_v3.blend` 的 CLASS101／AUDITORIUM／OFFICE 三個不同 metadata 區域，
本機 ignored `data/pilot/school_v3_multisite_20261005/`；不是不同建築或真實場地。
每組10秒、5FPS、[0,10) 的50timestamps／100PNG，合計 **150／300全部成功**。
原 corridor pilot 保留為比較 reference，不計入新生成數量。

教室用 `CAM_1F_CLASS101`／`CAM_1F_CORRIDOR_04`；禮堂與辦公區共用既有
`CAM_1F_AUDITORIUM_FRONT`／`CAM_1F_AUDITORIUM_REAR`，不改 pose／lens。
規劃／採樣長度依序300／294、660／646.800049、160／156.800049 scene units。
三組各驗證50個 timestamp 的5點 WALKABLE containment／physical support，並對完整
radius6／height119 continuous swept volume 做 exact triangle clipping；沒有 collision、
portal crossing、cross-floor 或 elevator transition。Cached search 僅供 hints，最終用
current evaluated physical mesh 重新判斷，拒絕碰撞及不符50點 visibility 的 routes。

| 區域 | Visible / occluded / out-of-FOV camera records | Global point GAP | 雙鏡頭全隱藏 / partial body | 判斷 |
| --- | --- | ---: | --- | --- |
| CLASS101 | 50 / 0 / 50 | 0 | 0 / 0 | 中心點持續可見對照；50個可見影像皆有 body boundary clipping |
| AUDITORIUM | 82 / 2 / 16 | 1 | 0 / 1 | 覆蓋／短暫中斷樣本，不適合作主要長遮擋資料 |
| OFFICE | 26 / 74 / 0 | 24 | 19 / 5 | 最適合本輪 point occlusion，仍有限 camera 配置與短 recovery window |

Auditorium GAP 只有 frame47／9.4s，仍看得到部分 marker。Office GAP 為frames21–44／
t4.2–8.8，完全看不到 marker 為frames23–41／t4.6–8.2，共19個離散樣本；恢復後只有5點。
Classroom corridor camera 全50點 FAR_CLIPPED；office 是不同 WALKABLE／AREA 路徑，
畫面仍是既有 auditorium 視角，不宣稱新增 office interior camera。全場採既有
opaque-gray Workbench／orange-marker policy，地板不規則明暗塊的原因未認證。
Agent 視覺判斷不當作 human authority／完整人體 CV detection readiness。

各組另存 combined evaluation-only dataset、strict 2D observations、GT、source-bound plan、
validation、sample report、50frame同步GIF、trajectory map與5張不同代表 montages。
Control 有明確 `FULLY_OBSERVED_CONTROL` 角色，不能假造 GAP；singleton GAP 的代表
frames 為0／46／47／48／49。跨場地 comparison 將判斷綁定 dataset／reviewed image hashes，
PNG 新增 SiteID，validator 核對 plan／export／PNG／provenance／2D／GT 一致，拒絕混場。

獨立驗證三組均 **PASS_WITH_REVIEW、errors=[]**；300PNG全部解碼、標記／hash核對，
158個 visible landmark 都有實際 orange pixels；全部PNG另做獨立 mask 分析確認上述
hidden／partial split。Forward max0.000638311px、static pilot plane inverse max
0.001787566units，unexpected Projection failure0；142個 non-observed camera inputs
按既有接口拒絕。來源SHA／468,300,506bytes／mtime_ns1791198236746106977不變。
GT僅 simulation/export/evaluation，inverse僅 sanitized2D＋camera＋independent static
pilot plane；沒有 Graph／ranking／reconstruction／Cases1–3 或 benchmark semantics 改動。

完整 regression **821 passed in72.57s、無skips**，Ruff、strict mypy72sourcefiles與diff
check通過。Sandbox內18個native Blender SIGSEGV於sandbox外完整rerun全部消失，
屬既知Metal環境問題，沒有以skip掩蓋。最後報告角色文字修正另通過6個summary tests／Ruff。
到這三組額外pilot停止；完整generation仍待
image policy／physical scale／formal floor-camera-geometry authority，不自動擴充。

### 2026-10-05 — Bounded Blender PILOT / SYNTHETIC SAMPLE

WALL milestone 後依同一授權完成本機 ignored
`data/pilot/school_v3_pilot_20261005/`，到此停止，不擴充完整 dataset。
`CAM_1F_CORRIDOR_02`／`CAM_1F_CORRIDOR_03` 保留來源 pose；1F corridor route 規劃
106 Blender scene units／10s，5 FPS 的 [0,10) 採樣為 **50 timestamps（0.0–9.8s）**，
採樣路段長 **103.880005 units**。實際 mesh floor Z≈20.07885，foot Z≈20.12885，
body-center landmark plane Z≈75.12885；沒有把 annotation Z=25 當作實體地面。
尺度不做猜測換算，marker 不宣稱真實人體尺寸／速度。

Planner 排除 135 annotation meshes（含四個 `Stair Reference Surfaces`），驗證 50 個
timestamp 的 WALKABLE triangle containment／250 physical support probes，以及 radius6／
height119 的完整 continuous swept volume 對 actual triangles intersection 為 0。
曾查出 point-clear route 的側面碰撞並修正路徑後才 render，不把 center ray 當作淨空證明。

Unsaved Blender 使用固定 frame220 的 evaluated VIEWPORT mesh instances，凍結為無
render modifiers 的 render-only copies，排除 non-MESH renderables；Workbench opaque
gray studio／orange marker 為明確 pilot policy。**100／100 PNG** render 成功，raw PNG
加入 PILOT／SYNTHETIC／source／simulation timestamp text metadata；100 個 IDAT payload
均保持不變。PNG hash、decoded dimensions、標記及所有 21 visible landmark 的實際
orange pixels 通過獨立檢查。這是 simulation point producer，不是 CV detector／正式材質驗證。

Camera02 visible3／occluded47，Camera03 visible18／occluded32，合計 **21 visible／79
occluded／0 out-of-FOV camera records**。Selected-camera landmark GAP 為 frames18–46，
**29 timestamps**；其中15仍有 partial body，frames25–38的14timestamps兩台相機都無
marker pixels。代表 frames0／17／18／32／47（0.0／3.4／3.6／6.4／9.4s）輸出雙相機
montages，另有50frame同步GIF、trajectory map、HTML gallery與human-readable sample report。

Independent validation **PASS_WITH_REVIEW、errors=[]**：source SHA／size／mtime 不變；
forward native residual 最大 **0.000114213px**，axial depth 最大0.000112066units；
獨立 mesh/config plane 的21次 inverse diagnostic 最大 **0.000247572units**，79 GAP
全數按既有 interface 拒絕，unexpected failure0。Inverse input 僅 sanitized 2D frame、
camera與explicit static pilot plane；GT只在simulation與後續evaluation讀取。另存
`observations.json`／`ground_truth.json`，combined `dataset.json` 明列 evaluation-only。
未呼叫 Graph／ranking／reconstruction／Cases1–3，不改 benchmark semantics，不建立 elevator。

最後完整 regression **797 passed in 56.90s，無 skips**；14 項 task safety／provenance tests
另外通過。Ruff 與 strict mypy（72 source files）通過。完整 generation 仍待人類 image review、
physical scale 及 formal floor/camera/geometry authority；不把 pilot 技術成功當作 full dataset ready。

### 2026-10-05 — Geometry-derived WALL candidate extraction

起點 `e8b293f`，branch `codex/dataset-infrastructure`，工作目錄原為 clean。
依使用者本輪授權，唯讀提取 `school_v3.blend` evaluated mesh 的 verticality、height、
edge-connected coplanar continuity、thickness／extent，並檢查 AREA、WALKABLE、PORTAL
空間關係。[JSON sidecar](../data/scene_audit/school_v3_wall_candidates.json) 自動確認
**81 WALL patches**（1F 49／2F 32，7 個來源 objects），**1,491 HUMAN_REVIEW patches**
（674 個來源 objects）。計數為連續共平面 surface patch，不是整個 object；四個 objects
混合兩種 status，因此 object totals 重疊。來源 `.blend` 的 WALL labels 仍未改寫。

[Human-readable report](../data/scene_audit/school_v3_wall_candidates.md) 包含 reason breakdown、
object／floor review index、每個候選的 bounds、AREA／WALKABLE／PORTAL 與判斷理由。
實際 polygons 對 28 個 PORTAL boxes 做 clipping；自動確認的 aperture intersection 為 0。
不生成 AABB／矩形牆，不補 doorway，不分類整個混合建築 object；window／door panel／
decoration／弱幾何證據留 HUMAN_REVIEW。WALKABLE intrusion 是 section sampling 診斷，
不是完整 collision certification。

使用者已明確確認只有 stairs、沒有 elevator；`AREA_*_ELEVATOR` 是歷史命名，
本輪沒有也不規劃 elevator transition。原始 asset SHA-256 維持
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
size 468,300,506 bytes、mtime_ns 1791198236746106977 不變。所有幾何數值保留
Blender scene units，METRIC／scale_length=1 不當作真實建築尺度認證。

五個 doorway／surface／thin-panel safety tests 通過；本輪完整 regression
**794 tests passed in 56.48s**、Ruff、strict mypy（72 source files）通過。
GT 未參與提取；未跑正式 Cases 1–3，未改 Graph／ranking／reconstruction／benchmark semantics。

### 2026-10-05 — school_v3 人工授權 semantic 補標與保存後診斷

起點 `a0aa1ea`，branch `codex/dataset-infrastructure`。依本輪人工確認的室內可走、
BLOCK→OBSTACLE/BOTH、courtyard／balcony 不可走與 stair floor 規則，保存同名
`blender/school_v3.blend`；沒有 v4／render。另經明確確認，validator 最小診斷擴充
讀取 source-bound intentional non-walkable／cross-floor AREA metadata，以及已分類且
reviewed 的 WALK_* alias。正式 Phase 1 schema／Graph／benchmark／metric semantics 不變。

[Patch recipe](../data/scene_audit/school_v3_semantic_patch.json) 新增 15 個房間地板、
19 個門檻 surface，14 個既有 floor 扣除實際 same-floor BLOCK polygons（含兩層 OFFICE
延伸）。19 BLOCK 保持 geometry／原 identity，轉為 OBSTACLE；四個原 stair halves
留作 reference，新增 2 PATH meshes／4 ENTRY/EXIT markers，沒有補造 landing／full path。
2F MENSROOM PORTAL 依 2F AREA 明確 bounds 修正 +140 Z。四個廁所扣除 blocker 後為空，
因此不生成 WALKABLE；elevator 仍 HUMAN_REVIEW。

Source SHA-256 依授權由
`26428df2fd395c69673b3e918fb7171b72d77a47d728e6b9cb21bb9da7b8e614` 變為
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`；原始備份與
architecture／obstacle geometry／camera 保持證據見
[update](../data/scene_audit/school_v3_semantic_update.json)。保存後唯讀 audit 的 SHA／size／mtime
不變。`.blend` 沿用 gitignore 留在本機，Git 保存 source-bound recipe／reports／tools。

[新報告](../data/scene_audit/school_v3_semantic_validation.md)：30 AREA、48 WALKABLE、
0 WALL、19 OBSTACLE、6 STAIR annotations、28 PORTAL、29 CAM。Coverage PASS/PARTIAL/MISSING
由 2/4/24 到 16/5/4，另 3 EXCLUDED／2 NOT_APPLICABLE；floor 25/165 僅 PROPOSED。
OFFICE 原 AREA denominator coverage 20.5742%→29.6071%，不改為扣 blocker denominator。
Components 9→14（範圍擴大且揭露門外 gaps，非連通改善證明），isolated 7→1。
Queue 49/170/43→33/224/69。原生 20 組雙側 probes 不當作完整連接；獨立 triangle/component
複查確認 6 組 distinct room/corridor 局部接觸，physical approval 仍為 0。

判定 **NEEDS_HUMAN_FIXES**；完整 HIGH／MEDIUM 位置與人工動作見
[位置摘要](../data/scene_audit/school_v3_semantic_locations.md)。缺口包括 bathroom blocker、
門外 seams、stairs landing／endpoint、WALL／3D collider、floor／camera-plane authority、
clearance／opening 與 elevator roles。沒有開始 Graph／collision pruning／benchmark／Agent。

本輪完整 **783 tests passed in 53.62s，0 failed／0 skipped**；Ruff、strict mypy（72 source
files）通過。最終 report replay、local links、source fingerprint 與 diff checks 的結果
保存在 report JSON 的 `semantic_supplement_review.verification`；metadata 未出現時的十組
既有 semantic fixture reports 保持原語意。

### 2026-10-02 — Semantic completeness validator、Benchmark Protocol 與 comparison reporting

起點 `1750e39`，branch `codex/dataset-infrastructure`，起始工作目錄 clean。
本輪依使用者授權新增唯讀診斷與報告工具；未修改原 Blender scene，也未猜測
`group_*`／`Cube.*`，未開始 school formal benchmarks、Agent、完整 reproducibility、
最終 Blender／Rerun presentation 或 Phase 2。正式 Graph／Reconstruction／MetricConfig
與 evaluation semantics 保持不變。

| Milestone | Local commit |
| --- | --- |
| Semantic validator、config、唯讀 extractor、診斷文件／school report | `56040b7` |
| 10 組 synthetic semantic scenes 與 39 個 regression tests | `b29b9aa` |
| Case 1–4、A–E baseline interfaces、single-factor ablation、metric protocol／4 tests | `40bfea1` |
| Matplotlib comparison generator、native／mock charts 與 summary tables | `249615a` |
| Plotting-only multi-method fixture 與 15 個 reporting regressions | `7f7ea71` |

[Semantic report](../data/scene_audit/semantic_validation.md) 由原 scene 在兩個獨立
Blender 5.2.1 LTS processes 唯讀抽取：30 AREA、28 PORTAL、29 CAM，WALKABLE／WALL／
OBSTACLE／STAIR 各 0。兩次 JSON 與 Markdown **byte-identical**；source SHA-256
`1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38`、466,332,340 bytes
與 mtime 均不變，沒有 save／render。Queue 為 HIGH 63／MEDIUM 124／LOW 3；HIGH 包含
30 個 AREA missing coverage、28 個 PORTAL disconnected、四種 missing physical labels
與一個 floor authority unresolved。MEDIUM 的 giant／hidden annotation 是 diagnostic
heuristics，不自動判成場景錯誤。

Validator 驗證 mesh holes／rotated triangles／union 不重複計面積、source-bound floor
authority、malformed/non-finite inputs、contact overlap、geometry budgets、stair path
跨孔洞與 naming／collection ownership。Unsupported geometry、floor-plane authority、
clearance／slab opening 維持 REVIEW；diagnostic adjacency 不建立 navigation 或 stair edges。

[Protocol](PHASE1_BENCHMARK_PROTOCOL.md) 固定問題、指標 populations／units、比較與缺值政策，
正式 D／epsilon／K／時間政策、physical authority 與 final baselines 仍為
`UNRESOLVED_RESEARCH_SETTING`／null，formal execution disabled；epsilon=0 仍拒絕。
PRD targets 是 INITIAL_TARGET，六類 acceptance 分開列出，不宣稱 synthetic 驗收成功。

比較工具載入既有 `data/candidates/infrastructure_20261002_final/`，產生
[11 張 SYNTHETIC REGRESSION 圖](../data/reports/benchmark/benchmark_summary.md)。
Native 未輸出的 projection／recall／impossible transition／path/time error／search
nodes graceful skip 並記理由，不捏造值。新的 plotting-only fixture 產生
[17 張 MOCK VALIDATION 圖](../data/reports/benchmark/mock_comparison/benchmark_summary.md)，
含三個 cases、A–C IDs、repeated／failed／missing／NO_REFERENCE／empty candidate records；
這不是 baseline A–C 實際執行。Physical／accuracy／Coverage 圖經 visual QA，Coverage
footer 重疊已修正。JSON／Markdown 保存 N/A、availability／status、K、六類 acceptance
與 incompatible-settings REVIEW；methods 不按 GT 排序。

本輪 final checks：**745 passed in 58.78s，無 failed/skipped**；repository Ruff 通過；
strict mypy 通過（72 source files）；diff whitespace、新文件 local links、PNG inventories、
source fingerprint 與 report replay 均通過。新增 58 tests（39 semantic／15 reporting／4
protocol）；起始 687 tests 也已重新通過。Local milestone commits 未 push／PR／merge。

### 2026-10-02 — Blender semantic audit；physical integration 等待人工標記

起點 `bd984f2`，branch `codex/dataset-infrastructure`。使用者要求完成 Blender-backed
Phase 1 Case 1–3 milestone，同時明訂遇到不可信 walkable、未明 collision ownership
或 ambiguous floor／camera-plane mapping 時停止並詢問。先 review PRD／System Design／
Issues、既有 provider／benchmark／Graph／reconstruction／metrics 與 configs／mock。
三組唯讀 review 分別檢查 scene evidence、geometry contract seams、dataset／camera 接入。

新增 [live semantic audit](../data/scene_audit/SEMANTICS.md) 與可重跑的 Blender／Python
wrapper，功能 commit `a03f993`。Blender 5.2.1 LTS 在 frame 220／subframe 0 評估全部
2,796 objects、2,652
meshes、29 collections；逐筆保存 BB／centroid 方法、mesh statistics、candidate role
與 trust status。30 AREA、28 PORTAL、29 research CAM；WALKABLE／WALL／OBSTACLE／STAIR
objects／collections 全為 **0**，annotation 未升格為 physical authority。
原 `.blend` SHA-256、466,332,340 bytes 與 mtime 執行前後完全不變，沒有 save／render。
29 camera IDs 與 portable calibration 一致，raw world matrices 最大差異 **0**；
這不是 Projection Error 量測，也不核准 floor plane。所有 floor authority 保持 unknown。

Audit review 抓到兩個 empty evaluated meshes 的 origin fallback 被誤標為 surface
centroid／AABB；已修正 `Circle.018`／`Plane.110` 的 audit methods，明示 non-surface／
non-geometry，沒有更改場景。修正後兩個獨立 Blender process／fresh outputs 的完整
JSON 語意相同；2,825 object／collection records 的必要欄位、finite bounds／centroids、
tool hashes 與 source immutability 均驗證。既有 output 的 runner guard 明確拒絕、
不覆寫 artifact、不啟動 Blender。

結果 **STOP_REQUIRED_HUMAN_ANNOTATION**；已詢問人工 source-bound WALKABLE surfaces／
connectivity／anchors、WALL／OBSTACLE movement／occlusion ownership、floor planes／camera
binding 與 physical clearance/contact policy。可透過 sidecar 保留原檔；尚未實作
sidecar schema／loader。Geometry provider 可用 additive platform-independent interface，
但本輪僅完成唯讀 review，沒有實作正式 contract、pruning 或 geometry authority。
School Cases 1–3／datasets／benchmarks／metrics／physical Rerun／A–C baselines 仍未建立；
未擴 fake fixtures、未修改 core／正式 schemas，未進入 Agent／Phase 2／Case 4。

完整 regression：**687 passed in 45.61s，無 failed/skipped**；`uv run ruff check .`
通過，`uv run mypy` 通過（69 source files），`git diff --check` 通過。既有 GT poisoning、
isolation、provider、termination、determinism／failure reporting 測試全部維持。
這些結果不代表 school physical integration 已完成；下一步需先取得人工標記。

### 2026-10-02 — Boundary / Failure-mode / Adversarial validation

起點 `b11edb9`，branch `codex/dataset-infrastructure`。先讀 PRD／System Design／
Issues and Decisions、既有 mock／tests／benchmark／metric configs；基線重新驗證
547 passed in 46.98s。本輪只新增小型 boundary fixtures／regressions，沒有一般正常
scenario、Blender scene 修改、render、Agent ranking 或發布；正式 domain schemas 不變。

| 分組 | 新增 tests | Commit |
| --- | --- | --- |
| Reachability／time／speed／floor；Graph fixture adapter | 15 | `f9246b6` |
| Observation duplicate／ordering／short/adjacent/missing gaps | 20 | `a76eb76` |
| Top-K／deterministic equal-distance tie | 17 | `09e6606` |
| Projection／provenance guards | 31 | `dcd7b2e` |
| Config／fake AABB collision boundaries | 24 | `7e59c06` |
| Termination／search guardrails | 20 | `9082528` |
| Four poisoned GT patterns／process determinism | 5 | `1f07701` |
| Benchmark failure reporting／formal Top-K consumers | 8 | `a95b595` |

新增總數 **140**。上述分組包含 parametrized cases，最後以 pytest collection／完整
執行總數核對。23 組 Graph specs 都是 2–3 nodes／最多 8 edges；20 min branching cycle
由 node budget 在 12 expansions 停止，1 hr cycle 由 path-length eligibility 在 15
expansions 窮盡。全部六種既有 termination 已覆蓋；未創造 unsupported hops/window
aliases 或 Agent/runtime reasons。Short recovery 保留獨立 endpoints/source binding；
duplicate policy 明確拒絕，全部 120 input permutations 的 inference semantics 相同。

新 regression 真正抓到的既有缺口集中於 benchmark reporting：invalid case rejection
沒有 structured report、JSON/Markdown summary 遺失 rejection reasons／endpoint 描述，
Markdown 未明示 NO_REFERENCE。Production 只修改 `benchmark/runner.py`／`reporting.py`：
保留 structured diagnostics 與既有 exception re-raise；不捏造 Graph termination，
不產生成功 artifact。未知 consumer RuntimeError／ValueError 仍原樣拋出；已知 contract
errors 才分類為 input rejection。Graph／projection／aggregation／ranking／metric semantics
沒有變更，這些新增測試未發現需要修補的既有核心 bug。

GT poisoning 使用不同 path、超大速度、錯誤 floor 與固定混亂座標，保存相同 reference
binding／time／seed。完整 aggregation／BoundGapEvent（candidates/order/IDs/termination/
timing）與 no-GT/clean-GT inference 相同；只有 evaluation 改變，K=3 Coverage 由 true
變 false、ADE 改變，physical metrics 不變。Determinism stress 三組 adversarial fixtures
各 4 次同 process、3 次新 process，共 21 次執行／9 個新 process，變更 hash/random
seed、CWD/output directory；完整 inference、metrics.json 與 JSON summary semantics
一致。排除 runtime/Git identity/RRD SDK metadata，不要求 binary byte identity。

2026-10-02 使用者確認 collision Top-K pruning **UNRESOLVED**，現階段只做
evaluation-only positive AABB／threshold tests；epsilon=0 明確拒絕，正式 Schema 不變。
沒有逐 transition rejection-log、missing-frame marker、coordinate-origin attestation
或獨立 ImpossibleTransition metric schema；範圍詳見 [boundary fixtures](../data/mock/boundary/README.md)。
ISSUES_AND_DECISIONS 只新增真正影響物理可行性語意的 collision authority 未解問題。

最終 code checkpoint `a95b595`：**687 passed in 48.05s，無 failed/skipped**；
`uv run ruff check .` 通過、`uv run mypy` 通過（69 source files）、`git diff --check`
通過。uv sandbox cache/SystemConfiguration 限制以獲准的 unsandboxed uv checks 解決，
沒有修改 dependencies／uv.lock。其後只更新文件，不把這些結果冒充正式 Blender
walkability/collision certification 或研究 benchmark 驗收。

### 2026-10-01 — Deterministic fake-data 後半段閉環

起點 `2a988df`，branch `codex/deterministic-downstream-scenarios`；使用者授權四組
可替換的 fake scenarios，完成後停止，不進入完整 Agent Semantic Ranking。

| 功能 | Commit |
| --- | --- |
| 固定 seed 20261001 fixtures 與分離 GT／inference JSON | `ef1e1ca` |
| 通用 Graph pipeline、reachability／min time／不可能轉移／Top-K／termination tests | `93a6bee` |
| M6 完整 frame schema 重驗、防止 provenance bypass | `c3387a2` |
| Timed Event hypotheses、direct／slower／dwell／detour 與 temporal slack | `d7db5ca` |
| ADE／FDE／route Top-K Coverage／continuous AABB／speed／directed corridor metrics | `723bbbe` |
| Rerun adapter、所有候選／hypotheses／provenance／GT debug overlay 與1Hz播放 | `737010d` |
| 完整 runner、所有 configs 物化與 Ground Truth isolation integration | `6066c9e` |

`6066c9e` 完整程式內容的驗證：**347 passed in 26.14s，無 skipped／failed**；
Ruff 通過、strict mypy 46 source files 通過、diff check 通過。指令由 uv 管理，使用
`UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync`，沿用 locked installed
environment。Sandbox 內 uv online discovery 會觸發 macOS SystemConfiguration panic，
既有 Blender CLI tests 在 sandbox 內 SIGSEGV；完整 pytest 在獲准解除 sandbox 後通過。
沒有修改 dependencies／lock 或 render／save Blender assets。

四組實際閉環輸出在本機 ignored `data/candidates/fake_downstream_20261001/`：

| Scenario | Routes／hypotheses | Primary ADE（m） | minADE@K（m） | minFDE@K | Coverage@K |
| --- | --- | --- | --- | --- | --- |
| Single Path | 1／1 | 0 | 0 | 0 | true |
| Branching Top-K | 3／5 | 7.8021081352 | 2.7079e-17 | 0 | true |
| Temporal Slack | 2／4 | 0 | 0 | 0 | true |
| Simplified Stair | 1／1 | 0 | 0 | 0 | true |

全部 COMPLETE；synthetic wall AABB、directed corridor、max speed 的 collision／constraint
rate=0。Branching GT 是第三條，Coverage@1=false；ADE/FDE 已知 numeric oracle 為1／2。
Temporal Slack 最短時間20s、gap180s、slack160s，保留 slower movement、dwell、detour，
不賦予行為機率。四份實際 RRD 以 SDK RrdReader 重開，確認 footer/store 與 entity data 可讀。
18 個 Rerun tests 另驗證3個Top-K、GT debug labels、provenance與20秒路徑中點播放。

GT isolation integration **12 passed**：禁止真值檔案讀取仍能完成四組推論；改變GT只改變
evaluation，candidate／Event JSON 不變；拒絕 JSON 注入、forged provenance、candidate
truth／probability payload。另有8個M6 copy／construct frame bypass regression cases。
Source／research copy SHA-256 均仍為
`1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38`。

這是 configured synthetic interface regression，不是 school walkability／stair／Mesh collision
驗證、formal benchmark 或完整研究驗收。有效接入缺口留在 handoff；沒有 push／PR／merge。

本文件保存已完成工作與當時驗證證據。即時待修項目見 [CODEX_HANDOFF](CODEX_HANDOFF.md)，持續適用的規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)，實際能力契約見 [DATA_SCHEMA](DATA_SCHEMA.md)／[INTERFACES](INTERFACES.md)。下列內容從既有交接整理，不代表本次重新執行全部測試，也不代表正式 school benchmark 已完成。

### 2026-10-01 — M0–M4：環境、稽核與合成模擬

| 階段 | 已完成內容 | 主要 commit |
| --- | --- | --- |
| M0 | 文件、Git、uv project 與 Blender CLI 檢查；pyproject／uv.lock 初始化 | `3238ec7` |
| M1 | 唯讀 school_v2 scene audit、JSON／摘要、結構幾何補充分析、來源綁定與研究副本 | `ab8a9d9`、`c3638c5`、`7add28b` |
| M2 | 可設定時間路徑、確定性取樣、temporary target proxy 的 Blender world-position 求值、GT JSON／CSV 匯出 | `82fa2a3` |
| M3 | Camera schema、29 台相機的 pose／intrinsics 抽取、world→pixel、FOV／clip 與 Blender parity 檢查 | `251db8f` |
| M4 | evaluated Mesh point raycasts、OBSERVED／GAP 與拒絕原因、來源 SHA 綁定、GT-free 2D evidence 匯出 | `58a8099` |

同期完成單位／相機 convention 記錄 `c3a02c7`、暫時中性材質 override `52b2b6e`，以及將 school 樓梯不確定性限縮到 school 跨樓層配置的文件修正 `2e9dd29`。固定使用 29 台 `CAM_*`、1 unit = 1 metre 的採用決策留在 [ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)，此處只記錄完成事實。

稽核證據存於 [scene audit 摘要](../data/scene_audit/README.md)、[幾何補充](../data/scene_audit/GEOMETRY.md) 與對應 JSON：

- Inventory 為 2,796 objects（2,652 Mesh、30 Camera）、29 collections、260 materials、447 images、489 modifiers、12 actions；其中 imported SketchUp Camera lens 非有限，29 台 `CAM_*` 為研究候選。
- 18 個 imported lights、8 個高面數物件及可能多餘的材質／貼圖只報告，未清理。
- Geometry follow-up 分析 370 個結構 Mesh、25,098 triangles，辨識主要 floor candidates `z≈20.07885`／`161.811096`；庭院另有 `z≈0.000112` 候選。兩個樓梯 annotation regions 未找到 Mesh 支持的連續上升路徑。這不是全場 NavMesh、walkability 或樓梯不存在的證明。
- 研究副本 `blender/working/school_v2_research.blend` 與原檔 byte-identical，沒有 save／render；temporary neutral override 不更改來源 slots、UV、images。
- `configs/trajectory_fixture.json` 為 factory synthetic 設定：0／2／4 秒 keyframes、10 Hz、seed 42，取樣器可產生 41 筆；seed 只記錄，基準取樣器不使用隨機性。這不是 school route 或已保存的 dataset。

### 2026-10-01 — M5–M8：契約、反投影、導航與搜尋

| 階段 | 已完成內容 | Commit |
| --- | --- | --- |
| M5 | Observation、ProjectedPoint、CandidateTrajectory、Event、ReconstructionResult、provenance／termination、nullable Phase 2 欄位、serialization tests 與 protocols | `1dcce12` |
| M6 | 一台 Camera 綁定顯式 unit-normal Plane、ray-plane inverse projection、axial clipping、plane identity／incidence quality 與 typed geometry failures | `7e952ae` |
| M7 | Directed configured navigation 與 Camera Topology 分離、ordered edge cross-validation、node 定位、3D length 與 canonical minimum-distance routing；generic synthetic stair 契約／測試 | `94ee2cd` |
| M8 | Exact topology-authorized routes、continuous anchors、速度／時間／長度／detour 剪枝、bounded Top-K、corridor 去重、candidate identity、搜尋停止狀態與 synthetic major-flow integration | `d6620b4` |

M5 最初交接中的 completion 預設與空 Observation shell 契約問題已收尾；M8 另實作輸入拒絕檢查：

- `ReconstructionResult` 檢查 termination／complete 一致性，`NO_FEASIBLE_PATH` 不接受 candidates。
- 空 OBSERVED shell 可宣告區間，但不等於有效 Evidence；M8 拒絕沒有 PROJECTED endpoints 的輸入。

M8 檢查確認有效 K 採 method／policy 較小值；只在看到 K+1 個 distinct feasible corridors 時回 `MAX_PATHS_REACHED`。Node／branch／timeout 終止標為 incomplete；同 corridor 去重、不加入未授權 connector 或另選 shortcut。這些屬於當時實作驗證事實，完整契約留在 [INTERFACES](INTERFACES.md)。

### 2026-10-01 — 驗證與 Review 證據

| 當時內容／checkpoint | 執行結果 | 說明 |
| --- | --- | --- |
| M5 完整內容；記錄於 `1dcce12` | 106 passed in 23.82s，無 skipped／failed；Ruff、mypy 21 source files、diff check 通過 | 當時 M5 完成驗證，不是 M8 結果 |
| M8 完整內容；記錄於 `d6620b4`／`c04435f` | 219 passed in 25.73s，無 skipped／failed；Ruff、mypy 33 source files、diff check 通過 | 當時 M8 完成驗證 |
| Review 起點 `baf9074`；結果記錄於 `e27d1dd` | 219 passed in 25.02s，無 skipped／failed；Ruff、mypy 33 source files、diff check 通過 | 重新檢查 M5–M8，未修改程式 |

重跑使用 `uv run pytest`、`uv run ruff check .`、`uv run mypy`、`git diff --check`。在上述 review 另確認來源與研究副本 SHA-256 相同：

```text
1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38
```

當時 Blender CLI 為 `/Applications/Blender.app/Contents/MacOS/blender`，5.2.1 LTS，build `9e2066aef7ef`。Blender-backed tests 使用 transient factory fixtures；測試暫存輸出不是 repository 的正式 dataset，沒有產生 render。Blender adapters 使用標準函式庫與 lazy bpy／mathutils，未假設 Blender Python 與 uv 共用套件環境。

Review 的證據範圍：

- M7／M8 在 configured-route 契約內未發現新的可操作正確性問題，正常推論 imports／scoring 未發現 GT 讀取。
- Walkability／collision safety 來自受信任的顯式 route 設定，不是 Mesh 障礙／淨空檢查；`WALKABLE` flag 不證明 school collision rate = 0。
- M8 integration 為 synthetic camera／2D evidence→plane projection→configured graph，不是 school Blender trajectory→evaluation 的正式閉環。
- Projected endpoints 要對齊 configured nodes；沒有 arbitrary-point connector。Wall-clock timeout 結果可能因負載不同而改變，不等於所有 timeout outputs 可重現。
- Review 找到 M6 `project_frame()` 未重驗完整 ObservationFrame 的 provenance bypass：`model_copy` 產生非法 provenance 仍可被投影。當時僅記錄、未修程式；有效待修狀態在 [handoff](CODEX_HANDOFF.md)。這不是已確認的正常流程 GT 座標洩漏。
- Projection Error evaluation、M9 reconstruction、M10 metrics、M11 visualization、formal benchmark 均未在這些檢查中完成。

### 2026-10-01 — 資料盤點、發布與交接整理

- `74c66bd` 新增日期化 [data inventory](../data/README.md)。當時 Git 追蹤的是 audit bundle；唯一已物化 runtime artifact 為本機、ignored 的 29-camera catalog，GT／Observation／candidate／metric／`.rrd`／rendered-image dataset 均未物化。
- `baf9074` 記錄先前經明確授權的 GitHub 發布；`83ca3f8` 新增 project README。後續 review 沒有重新透過網路驗證 GitHub，不把本機 remote reference 當永遠有效的遠端狀態。
- `e27d1dd` 更新 M5–M8 review handoff，記錄使用者暫緩 school 樓梯／跨樓層／正式 Case 4、保留 generic synthetic tests；沒有修改程式、資產或 push。
- 本次以 `e27d1dd9494c921aa34027012e7b6e693dc6a5ba` 為文件整理起點，將歷史完成／驗證移至此紀錄、持續規則移至 DEVELOPMENT_RULES，精簡 CODEX_HANDOFF，並補文件導覽。沒有開始 M9、修補 M6、生成資料或渲染；本次僅做文件內容／連結／diff 檢查，不重跑上述歷史測試。
- 本次文件驗證：4 份雙語 Markdown、57 個本機連結與 fence／有效待修／暫緩狀態檢查通過；diff check 通過。歷史測試數字另以對應 commit 保存的 handoff 核對，不沿用未核實的快照。

## English

### 2026-10-05 — Post-checkpoint WALL markings and one bounded pilot loop

Work continues only on phase1/pilot-dataset-and-wall-inference from checkpoint
91f4ea600805739aa9659dfef6a381d71be9a692. Fresh original-source extraction confirms
81 WALL surface patches (49 on 1F, 32 on 2F, 7 source objects), retaining 1,491
HUMAN_REVIEW patches across 674 objects; object counts overlap for mixed meshes.
The dated candidate report records bounds, floors, nearby AREA/PORTAL, WALKABLE
relations and verticality/height/continuity/extent/parallel-thickness reasoning.
Ambiguous windows, doors and decoration remain under review.

The saved isolated school_v3_wall_marked.blend contains 81 WALL semantic selection
meshes copying 543 actual existing polygons. No whole group_* is reclassified, no
doorway is filled and no movement collider is installed. Independent reopening verifies
all 2,873 original object identities and evaluated physical geometry, with zero actual
face intersections against 28 protected portals. Original/source-checkpoint SHA remains
cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e, with unchanged
468,300,506 bytes and mtime_ns1791198236746106977. Derived SHA is
b4d3394b17626bfdf35ee9b9e35c1f5a4469dd75a3e24b1a4f5f5aa58bdf4d49. The new
marking recipe and dated audit artifacts bind source, candidate and reopened selections.

Exactly one new ignored PILOT / SYNTHETIC SAMPLE is materialized at
data/pilot/phase1_wall_pilot_20261005/office/. Existing AUDITORIUM_FRONT/REAR cameras
retain source poses on the 1F office metadata route PILOT_OFFICE_001: 160 configured /
156.800049 sampled native units, 10s at 5 FPS, all 50 timestamps and 100 PNGs successful.
The route passes 250 support probes and continuous full-marker swept-volume checks.
The plan/export lineage binds the real derived asset and preserved original/candidate/
physical geometry. All 81 WALL annotations are excluded from physical BVH, render
snapshots and rays; original physical surfaces still supply occlusion.

Independent validation is PASS_WITH_REVIEW with zero errors: 26 visible, 74 occluded,
zero out-of-FOV camera records; FRONT 21/29 and REAR 5/45. The visible→GAP→visible
loop has 24 global landmark GAP timestamps at frames21–44 (4.2–8.8s), including
19 fully marker-hidden samples and 5 with partial body. Forward/inverse maxima are
0.000314545px / 0.001615262 native units, with no unexpected Projection failures;
74 non-observed inputs are rejected as expected. Inverse inputs contain only sanitized
2D frames, calibration and an independent mesh-probed static diagnostic plane. GT
is used only by simulation and post-projection evaluation, never downstream inference.
Original and derived hashes, sizes and mtimes remain unchanged.
An independent audit verifies all 100 decoded PNGs and provenance labels/hashes, 100
planned/exported states and strict 2D frames, plus all 26 visible landmark orange masks.
All 100 decoded RGB renders are exactly pixel-identical to the previous original-source
office renders, with zero differing pixels. Dataset SHA is
77203e33a566f99936e6446133dae245231562b0a64bfc82447e5f1215d5d2df.

Outputs include separate GT/2D observations, evaluation-only dataset, plan, validation,
sample report, gallery, trajectory map, 50-frame ten-second GIF and five inspected
representative montages at frames0/20/21/32/45 (0/4.0/4.2/6.4/9.0s), explicitly
distinguishing partial-body GAP entry from fully hidden middle and rear-camera recovery.
Fresh requested checks pass: 847 pytest tests in71.83s without skips, Ruff, mypy for
72 source files and diff check. Final uv/native Blender checks run outside the sandbox.
No benchmark semantics, formal Cases1–3, elevator transition, merge or push occurs.
Work stops here; full generation awaits user pilot review, physical scale and formal
geometry/floor/camera-plane authority.

### 2026-10-05 — Phase 1 semantic scene checkpoint

The user explicitly authorizes a major checkpoint, publishing the current branch and
creating a continuation branch from it. The starting tree is clean on
codex/dataset-infrastructure at 4437ef3e468d3b18181f893906619af021042434. Fresh requested
checks pass: uv run pytest has 821 passed in 58.64s without skips; Ruff, mypy for 72 source files
and git diff --check pass. Final native Blender/uv checks run outside the sandbox;
uv's sandbox macOS initialization failure disappears on the same-command rerun, without
removing or skipping tests. The checkpoint record preserves branch/source/validation and
continuation boundaries. A verified, ignored read-only snapshot matches the current
school_v3 hash; original hash/size/mtime are unchanged. The local manifest records the
checkpoint SHA and four pilot file hashes; raw assets are not pushed and no new rendering
occurs. The marker commit is checkpoint: preserve phase1 semantic scene state. Subsequent
work belongs on phase1/pilot-dataset-and-wall-inference, created at the same checkpoint
commit, with no formal benchmark semantic changes, Cases1–3 execution or merge back.
Exact commit/publication evidence is in the completion report and local manifest.

### 2026-10-05 — Three-locale Blender PILOT comparison

Starting at c078b89, the user's follow-up authorizes several locales and judgments.
Three new ignored PILOT / SYNTHETIC SAMPLE runs in school_v3 cover CLASS101, AUDITORIUM
and OFFICE metadata regions, not separate buildings or real sites. Each has 10s at 5 FPS,
50 timestamps on [0,10) and 100 PNGs: all 150 timestamps / 300 renders succeed. The
original corridor pilot remains a reference and is not counted as newly generated.
Classroom uses CLASS101/CORRIDOR_04; auditorium/office reuse AUDITORIUM_FRONT/REAR without
camera changes. Configured / sampled lengths are 300/294, 660/646.800049 and 160/156.800049
native scene units. Every route passes 250 physical/WALKABLE support probes and exact
continuous full-marker swept-volume triangle checks. Cached grids are hints only;
current geometry rejects colliding or mismatched-visibility routes. No portal, floor or
elevator transition is introduced.

Classroom has 50 visible / 0 occluded / 50 out-of-FOV records and no global GAP: it is a
center-point control, with marker boundary clipping in all 50 visible images and all
CORRIDOR_04 samples FAR_CLIPPED. Auditorium has 82/2/16 records and one GAP at 9.4s with
partial body still visible: useful coverage/brief-interruption data, not the main long-gap
sample. Office has 26/74/0 records and 24 GAP samples at 4.2–8.8s: 19 at 4.6–8.2s show no
marker in either view and five retain partial body. It is the strongest current point-gap
sample, with reused auditorium views and only five recovery samples. Existing opaque-gray
Workbench/orange-marker rendering has irregular floor appearance of unverified cause.
Agent image judgments do not grant human authority or whole-body detector readiness.

Each run saves separate strict 2D observations/GT, evaluation-only combined JSON, source-bound
plan, validation, report, 50-frame synchronized GIF, trajectory map and five distinct review
montages. Explicit FULLY_OBSERVED_CONTROL never fabricates a GAP; singleton GAP representatives
are 0/46/47/48/49. Comparison binds judgments to dataset and inspected-image hashes. SiteID
is verified across plans, PNGs, provenance and both exports; mixed-site corruption is rejected.
All three independent validations are PASS_WITH_REVIEW with no errors; all 300 PNGs are
decoded/hashed/labeled, all 158 visible landmarks have orange pixels, and independent masks
confirm the full-hidden/partial split. Forward error is at most 0.000638311 pixels and static
pilot-plane inverse error at most 0.001787566 scene units, with zero unexpected failures;
all 142 non-observed camera inputs are correctly rejected. Source hash/size/mtime are unchanged.
GT is used only for simulation/export/evaluation; inverse receives sanitized 2D, camera and
an independent configured plane. Graph, ranking, reconstruction and formal benchmarks are
not run or changed. Full regression passes 821 tests in 72.57s without skips, plus Ruff,
strict mypy for 72 source files and diff checks. Eighteen native Blender crashes in the
sandbox disappear in the full outside-sandbox rerun, without skipping tests. Work stops at
these three pilots; the final report-role wording adjustment also passes six summary tests
and Ruff. Full generation still awaits image policy, scale and formal authority.

The bounded 2026-10-05 PILOT / SYNTHETIC SAMPLE is materialized locally in ignored
`data/pilot/school_v3_pilot_20261005/`. CAM_1F_CORRIDOR_02/03 retain their source poses;
the 1F route is planned at 106 native scene units over 10s, with 50 timestamps at 5 FPS on
[0,10), sampled length 103.880005. Actual floor support Z≈20.07885 differs from annotation 25;
feet and landmark are Z≈20.12885/75.12885. No physical-scale conversion or human-size claim
is invented. All 50 samples pass WALKABLE containment, 250 physical support probes and exact
continuous radius6/height119 swept-volume triangle checks. A point-clear side collision
was corrected before rendering. Annotation/reference geometry is excluded.

Frozen frame 220 evaluated VIEWPORT mesh instances are rendered without modifiers in an
unsaved process, using the explicit opaque-gray Workbench studio/orange-marker pilot policy.
All 100 PNG renders, hashes, dimensions and synthetic/source/timestamp provenance labels
verify; metadata labeling preserves all 100 compressed IDAT pixel payloads. All 21 visible
landmarks independently show orange image pixels. Camera02 has 3 visible/47 occluded records;
Camera03 has 18/32, totaling 21 visible/79 occluded/zero out-of-FOV. Global landmark GAP has
29 timestamps (frames 18–46); 15 retain partial body and 14 show no marker in either render.
Representative frames 0/17/18/32/47, a synchronized 50-frame GIF, trajectory map, HTML gallery
and sample report are saved. This is point simulation, not whole-body CV or formal shading.

Independent validation is PASS_WITH_REVIEW with no errors. Source SHA/size/mtime are
unchanged; forward residual ≤0.000114213 pixels, axial-depth residual ≤0.000112066 scene units,
and 21 diagnostic inverse projections differ by at most 0.000247572 scene units. All 79 GAP
inputs are correctly rejected with no unexpected failures. Inverse inputs contain only
sanitized 2D evidence, camera calibration and an independent static mesh/config plane;
truth is evaluated afterward. GT and observations are separate, combined data is
evaluation-only, and no Graph/ranking/reconstruction/formal benchmark/elevator transition
is run or changed. Final regression passes 797 tests in 56.90s with no skips, 14 targeted
safety/provenance tests, Ruff and strict mypy for 72 source files. Work stops at this pilot;
full generation remains pending human image review and physical scale/formal authority.

The 2026-10-05 WALL extraction starts at clean `e8b293f` on
`codex/dataset-infrastructure`. Source-bound evaluated surface analysis confirms
81 WALL patches (49 on 1F, 32 on 2F, 7 source objects) and retains 1,491 HUMAN_REVIEW
patches (674 source objects). Four objects contain both statuses; counts are connected
coplanar surface patches, without whole-object classification or saved source labels.
The report includes review reason counts, an object/floor index, bounds and nearby
AREA/WALKABLE/PORTAL evidence. Exact face clipping protects all 28 PORTAL boxes;
confirmed aperture intersections are zero. No rectangle/AABB walls or doorway infill
are created. Ambiguous panels, glass, decoration and weak evidence stay review; sampled
WALKABLE checks are not complete collision certification.

The user confirms stairs only and no elevators; historical AREA_*_ELEVATOR names do not
create transitions. Source SHA-256, 468,300,506-byte size and nanosecond mtime are unchanged.
Native scene units remain explicit; declared metric scale is not physical certification.
Five targeted safety tests and the complete 794-test regression (56.48s), Ruff and strict
mypy for 72 source files pass. Ground Truth, formal Cases 1–3 and downstream inference
semantics are untouched.

### 2026-10-05 — Authorized school_v3 semantic supplement and post-save diagnostics

Starting at `a0aa1ea` on `codex/dataset-infrastructure`, explicit human policies authorize
saving the same school_v3.blend, without v4 or rendering. The reviewed recipe adds 15 room
floors and 19 aperture-only thresholds, subtracts same-floor blocking polygons from 14
existing floors, extends both offices, preserves all 19 obstacle meshes while assigning
OBSTACLE/BOTH roles, corrects the 2F MENSROOM portal by +140 Z, and annotates two stairs
without inventing landings or full paths. Four fully blocked bathrooms remain without room
floors; elevator roles remain unresolved. The separately approved validator extension reads
intentional exclusions/cross-floor AREA metadata and reviewed explicit WALKABLE aliases;
formal Phase 1 schemas, Graph, benchmark and metric semantics stay unchanged.

Source SHA changes intentionally from `26428df2fd395c69673b3e918fb7171b72d77a47d728e6b9cb21bb9da7b8e614`
to `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`.
The verified original backup and unchanged architectural/obstacle meshes/cameras are recorded
in [update evidence](../data/scene_audit/school_v3_semantic_update.json). The subsequent
read-only audit preserves hash, size and mtime. The ignored Blender asset stays local;
source-bound recipes, reports and tools are committed.

The updated inventory is 30 AREA, 48 WALKABLE, zero WALL, 19 OBSTACLE, 6 stair annotations,
28 PORTAL and 29 CAM. Coverage PASS/PARTIAL/MISSING moves from 2/4/24 to 16/5/4, plus three
EXCLUDED and two NOT_APPLICABLE declarations. Floors 25/165 remain proposed. Office coverage
uses the unchanged raw AREA denominator: 20.5742% to 29.6071%. Diagnostic components grow
9 to 14 as newly marked rooms reveal unresolved seams; isolated objects fall 7 to 1.
Queues change 49/170/43 to 33/224/69. Independent component checks confirm six local contacts
between distinct room/corridor surfaces, not 20 connected doors from two-sided probes;
none grants physical authority. Readiness is NEEDS_HUMAN_FIXES. The
[location summary](../data/scene_audit/school_v3_semantic_locations.md) identifies every
remaining HIGH/MEDIUM object, coordinates and required human action. No physical integration,
collision pruning, benchmark or Agent work starts.

Full regression passes 783 tests in 53.62s with no failures/skips, repository Ruff and strict
mypy for 72 source files. Final native replay, local links, source fingerprint and diff
evidence is stored in the report JSON; ten pre-existing metadata-free semantic fixtures
retain their prior report semantics.

The 2026-10-02 validator/protocol/reporting round starts at clean `1750e39` on
`codex/dataset-infrastructure`. Local commits `56040b7`, `b29b9aa`, `40bfea1`, `249615a`,
and `7f7ea71` add read-only scene diagnostics, synthetic semantic tests, the formal protocol
specification, matplotlib comparison reporting and plotting regressions. No original scene,
formal Graph/Reconstruction/evaluation semantics, school benchmark, Agent or presentation work
changes. No publication is performed.

Two independent Blender processes produce byte-identical semantic JSON/Markdown: 30 AREA,
28 PORTAL, 29 CAM and zero physical labels. Source SHA-256, size and mtime remain unchanged.
The review queue has 63 HIGH, 124 MEDIUM and 3 LOW findings; unsupported geometry and absent
floor/clearance/opening authority retain REVIEW rather than creating navigation/stair edges.
The protocol defines Cases 1–4, baseline/ablation interfaces, metric populations and six
acceptance categories, while formal settings remain unresolved and execution disabled.

Persisted native fake outputs yield 11 SYNTHETIC REGRESSION charts; unavailable metrics skip
with reasons. The explicit plotting-only fixture yields all 17 MOCK VALIDATION chart families,
including failed/missing/no-reference/empty records and repeated runs. Visual QA corrected the
Coverage footer layout. Missing values remain N/A; incompatible aggregates require REVIEW;
GT never orders methods. Final checks: 745 tests in 58.78s, no skips/failures, Ruff, strict mypy
for 72 source files, diff/local-link/chart inventories, report replay and source immutability
all pass. The 58 new tests consist of 39 semantic, 15 reporting and 4 protocol regressions.

The 2026-10-02 Blender milestone begins at `bd984f2`. A fresh read-only source-bound audit
inventories 2,796 objects, 2,652 meshes and 29 collections: 30 AREA annotations, 28 PORTAL
annotations, 29 research cameras, and no WALKABLE/WALL/OBSTACLE/STAIR labels. All 29 raw
camera world matrices match the portable calibration exactly; floor-plane authority is
still unreviewed. Source SHA-256, size and mtime are unchanged; no save or render occurred.
Two empty-mesh origin fallback descriptions were corrected in the new audit. Two fresh
Blender processes produced identical JSON semantics; all 2,825 rows and tool/source hashes
were checked. The existing-output guard rejects without overwrite or Blender launch.

Under the user's explicit stop conditions, physical integration waits for source-bound
human walkable/collider ownership, floor/camera-plane bindings and clearance policy.
An additive geometry interface was reviewed, not implemented. No school Cases 1–3,
datasets, physical metrics/visualizations or A–C baselines are claimed. Existing schemas,
core, fake fixtures, Agent and Phase 2 remain untouched. Final regression: 687 passed in
45.61s, Ruff passed, mypy passed for 69 source files, and diff checks passed.

The 2026-10-02 boundary round starts at `b11edb9` on `codex/dataset-infrastructure` and
adds 140 tests across the eight commits above. Final code `a95b595` passes 687 tests
in 48.05s with no skips/failures, repository Ruff, strict mypy for 69 source files and
diff checks. Only benchmark reporting production code changes: structured known-input
rejections retain their original exception, and summaries expose endpoints/reasons and
NO_REFERENCE. No formal schemas, core inference/metric semantics, Blender assets,
dependencies, rendering, Agent ranking or publication change.

Four poisoned-truth patterns and absent truth preserve full inference; only evaluation
changes. Three adversarial fixtures replay across 21 invocations, including nine fresh
processes with varied hash/random seeds, CWD and output directories. All 120 observation
permutations and equal-distance route permutations retain ordering and IDs. All six
current search reasons, partial-candidate preservation, short/adjacent gaps and tiny
long-gap branching bounds are tested. User-confirmed scope keeps collision pruning
unresolved/evaluation-only and rejects zero epsilon. Actual school geometry, clearance
and obstacle authority remain future work, not a claim established by these fixtures.

The 2026-10-01 fake-data round started at `2a988df` and completed the generic downstream
loop on `codex/deterministic-downstream-scenarios`, with implementation commits listed
above through `6066c9e`. Full validation passed 347 tests in 26.14s, no skips/failures,
Ruff, strict mypy for 46 source files and diff checks. uv used the installed locked
environment with offline/no-sync and a writable cache; existing Blender tests required
approved unsandboxed execution. No dependencies, source assets, render, semantic ranking
or publication changed.

All four fixtures generated real candidate/Event/metric/RRD outputs, totaling 7 routes
and 11 timing hypotheses. All terminated COMPLETE; minADE@K≈0, minFDE@K=0, Coverage@K=true,
and supplied-AABB/speed/corridor violations=0. Branching primary ADE=7.8021081352m and
Coverage@1=false, with true route retained at rank three. Temporal slack is160s for20s
minimum travel in180s. Four RRD files were reopened successfully; 18 visualization tests
include midpoint playback. Twelve GT isolation integration cases and eight new M6 bypass
cases passed. Blender source/copy hashes match the unchanged digest above. These are fake
interface results, not school mesh certification or a formal benchmark. Remaining
producer/scene/multiple-gap/benchmark interfaces are in CODEX_HANDOFF.

This is a dated completion/evidence log, not a live TODO list. [CODEX_HANDOFF](CODEX_HANDOFF.md) owns current unresolved work; [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md) owns durable rules; DATA_SCHEMA/INTERFACES own contracts. Historical results are not new test runs or formal benchmark acceptance.

On 2026-10-01, M0–M4 delivered uv/environment inspection, read-only scene/geometry audits and an identical research copy, deterministic Blender-evaluated Ground Truth export, 29-camera calibration/forward projection, and point visibility with sanitized 2D evidence. Main commits were `3238ec7`, `ab8a9d9`, `c3638c5`, `7add28b`, `82fa2a3`, `251db8f`, `58a8099`. Audit diagnostics identified floor candidates but did not certify school walkability or stairs; assets remained unchanged and no render was performed.

M5–M8 were independently committed as `1dcce12`, `7e952ae`, `94ee2cd`, `d6620b4`: strict domain/contracts, explicit-plane inverse projection, separate configured navigation/camera topology, and bounded topology-authorized Top-K search. M5 completion and empty-shell issues were resolved before commit. Exact route continuity, distinct-corridor K+1 truncation and incomplete search-limit reporting were reviewed.

Historical committed evidence: M5 `1dcce12` records 106 tests in 23.82s and mypy for 21 source files; M8 `d6620b4`/`c04435f` records 219 in 25.73s; a later review starting from `baf9074`, recorded in `e27d1dd`, passed 219 in 25.02s (no skips/failures), Ruff, strict mypy for 33 source files and diff checks. Source/copy hashes matched the digest above. These checks do not establish mesh collision/clearance, school navigation, Projection Error evaluation or a formal dataset/benchmark. The M6 schema-bypass finding was recorded, not fixed at that review.

`74c66bd` inventoried audit evidence and a local ignored camera catalog, with no materialized GT/observations/candidates/metrics/images. `baf9074` recorded an earlier authorized publication; `83ca3f8` added the README. `e27d1dd` recorded review results and the user's temporary school-stair deferral without code/asset/publishing changes. This documentation-only reorganization started from `e27d1dd`; it moves completed history here, durable rules to their own document and preserves actual open handoff items. Four bilingual Markdown files, 57 local links and state/fence/diff checks passed; historical counts were checked against their committed records, not rerun. No M9, M6 fix, data generation or rendering was started.
