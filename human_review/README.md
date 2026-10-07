# Phase 1 最小人工審查

狀態：**HUMAN_REVIEW_PENDING**；4 項決策全部未選擇。推薦值不等於核准。

## HR02 相機／落點核對補充

先看 [HR02 camera audit](frames/hr02_camera_audit/view.html) 與
[核對結果／重現方式](HR02_CAMERA_AUDIT.md)。兩台 source cameras 在數值上位於
`AREA_1F_AUDITORIUM` AABB、OFFICE AABB 之外；物件名稱／外框不能核准 room ownership。
50 timestamps × 2 cameras：原 public 記錄 26 OBSERVED／74 GAP；回推 landmark 射線
26 CLEAR／74 OCCLUDED，候選腳底 10 CLEAR／90 OCCLUDED；16 筆 landmark 通視但腳底被擋。
**1.35973495 m 是待核准 landmark→floor 偏移，不是地板到天花板高度。**
人工只確認目標房間／鏡頭是否正確，以及追蹤點是固定身體 landmark 還是腳底。
fallback 沿用既有 protocol，不新增研究設定問題；原四項 decision 全部保持 null。
人物是 public projection／GAP candidate，不是原始3D軌跡；沒有使用 GT。wide／side
是 display-only cutaway，射線使用完整 allowed source mesh；20／25／45 是獨立代表
camera still，不代表當前連續影格或 CV pixel certification。矛盾未釐清時維持 KEEP_REVIEW。

新增審查辨識補充：空間導覽第 2 步提供完整測試空間與相機定位，第 3 步保持 FRONT／REAR
位置對照，第 5 步與 HR-02 問題區加入實際 source 空間中的示意人物及腳底／landmark 高度。
[獨立補充來源](frames/review_clarity/manifest.json)；舊圖、舊動畫及四項決策全部保留。
**HR-02 的 1.3597 m 是 projected landmark 到候選腳底的垂直偏移，不是地板到天花板。**
目前 landmark Z=75.12885 BU，approved support Z=20.07885 BU；相減 55.05 BU，
以已核准 0.0247 m/BU 換算。人物高 1.70 m、半徑 0.30 m、clearance 0.05 m；
人物落點／語意仍待 HR-02，姿勢沿用 display-only 示意，沒有使用 GT。

Source issue 圖例（原近看圖）：

| 外觀 | 意義 |
| --- | --- |
| 藍色大立體方框 | HR-01 待審 body guard：限定人體占用的審查範圍，並非實體牆 |
| 白色小長方框 | 候選腳底可落點的限定 domain，並非模型物件 |
| 橘色圓柱 | 人體尺寸包絡，半徑 0.30 m／高 1.70 m；位置為候選示意 |
| 淡黃色外圓柱 | clearance 包絡，半徑 0.35 m／高 1.75 m |
| 紫色線／點 | group_0 faces 1975／2398 的同一零面積 floor seam；顯示抬高 1.4 BU |
| 藍色點 | public projected landmark；尚未核准為人物腳底 |
| 黃橘／紅色折線 | 既有 direct／right 候選及自動 floor-clearance 拒絕的 left 路徑 |
| 綠色面／灰色線框 | approved source floor support／來源模型定位 context |

較遠的一樓圖橘框是 AREA_1F_OFFICE annotation context；紫色小框是同一待審 body guard。
不同圖的圖例以該圖標示為準。相機位置導線不是 FOV：逐時可見性由既有 public evidence 顯示，
FRONT 可見至 t=4.0 s，REAR 在 t=9.0 s 恢復；採樣 t=4.2–8.8 s 兩者均無可用觀測。
這是既有 evidence 的 GAP，不能僅由位置圖推斷整個模型的遮蔽情況。

在已物化原 29 frozen inputs 與舊審查媒體的 fresh checkout，重建辨識補充：

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --threads 2 --factory-startup --disable-autoexec /absolute/path/to/school_v3.blend \
  --python-exit-code 2 --python "$PWD/human_review/render_review_clarity.py" -- --frames 25
uv run python human_review/build_spatial_guide.py \
  --clarity-manifest human_review/frames/review_clarity/manifest.json
uv run python human_review/build_dashboard.py \
  --clarity-manifest human_review/frames/review_clarity/manifest.json
uv run python human_review/finalize_package.py
```

Renderer 拒絕覆寫 PNG／manifest；可用 `--output /fresh/path` 另存診斷 render。
上列 HTML builder 固定讀 canonical supplement，以 hash 驗證後才嵌入。

審查入口統一為 [原有 dashboard](index.html)。在「共同視覺審查工作區」同頁切換空間定位、
10 秒行走動畫與模型＋拓樸；再依 **HR-01 → HR-02 → HR-03 → HR-04** 開啟決策。
HR-01／HR-02 的 Evidence 也整合相同播放器與各自檢驗重點，先看動作和拓樸，再看
接縫／marker-floor 近圖。原有連續預覽保留於可展開區域，完整獨立頁仍可另開。
切換或關閉觀看區會卸載舊播放器；四項問題、profiles、研究設定與草稿識別都保持不變。
在 repo root 重建補充介面請使用上列 `--clarity-manifest`；不帶此選項只嵌入原證據。
更新 package hashes：`uv run python human_review/finalize_package.py`。

新增：[模型與拓樸對照](frames/topology_context/view.html)；模型與旁邊空白區使用相同
N1／N2、E1–E3 標號，保留 10 秒逐格播放。實心點是 2 個 graph nodes，空心點是
4 個 polyline vertices，三條 directed edges 完整保留。N1 是 FRONT t=4s GAP 前端點，
N2 是 REAR t=9s recovery；E1 direct、E2 left、E3 right。
模型可切換 raw landmark 高度與 pending HR-02 floor footprint；顯示換算不改 raw graph。
**固定 graph 與移動人物分開看：**N1／N2 與四個 vertex 是固定空間位置；P(t) 是
隨影格同步移動的 DISPLAY_ONLY 人物標記，不是新增 graph node。模型腳底圈與右圖
人物使用同一個 frozen frame，並顯示目前 N1／E1／N2 或 GAP graph 範圍外。
t=4s 對應 N1；4.2–8.8s 是既有 inferred E1 candidate；t=9s 對應 N2。
人物在 edge 中間沒有『目前 node』，會顯示 E1、N1→N2 及進度。圖外可見片段
仍顯示實際位置，不吸附到端點。Node association 用原 public double 座標與既有
1e-6m tolerance；模型游標沿用 render float32 座標，未放寬門檻或挪動人物。
Dashboard iframe 以驗證過的 topology view SHA256 固定版本；草稿識別與四項問題不變。
E2 的 floor-review clearance 自動拒絕與 graph pruning 分開記錄。
[靜態對照圖](frames/topology_context/topology_preview.png) 與
[獨立 manifest](frames/topology_context/topology_manifest.json) 保存精確座標及來源。
在具備原 29 frozen inputs、既有 diagnostics 與 135 PNG／GIF 的 fresh checkout 重建：

```sh
uv run python human_review/build_topology_view.py
uv run python human_review/render_topology_preview.py
uv run python human_review/build_motion_player.py \
  --gif-provenance human_review/frames/motion_context/gif_manifest.json \
  --topology-view human_review/frames/topology_context/view.html
uv run python human_review/build_topology_view.py
```

原有預覽與四項決策保留；這是既有 CONFIGURED / DIAGNOSTIC 圖，不證明 formal branching。

2026-10-07 另增：[10 秒模型人物行走](frames/motion_context/player.html)，
可播放、暫停、逐格查看；另有 [GIF 動作預覽](frames/motion_context/motion_preview.gif)。
鏡頭固定，簡化人物在實際 evaluated office 來源模型中移動，包含 body / clearance、
投影點、floor support、待審 body guard 與 OBSERVED → GAP → OBSERVED。
50 frames /5 Hz 的位置、時間與 projection provenance 完全沿用原預覽；
GAP 是既有候選假設，肢體姿態是 DISPLAY_ONLY 示意，不是 measured motion capture。
原有導覽、鏡頭接近動畫、預覽與 85 張圖全部保留；沒有新增路徑或核准 authority。
新段落的獨立來源紀錄：[motion manifest](frames/motion_context/motion_manifest.json)。

在保有原 29 frozen inputs 與 85 舊圖的 fresh checkout 中，可重建新增段落：

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --threads 2 --factory-startup --disable-autoexec /absolute/path/to/school_v3.blend \
  --python-exit-code 2 --python "$PWD/human_review/render_motion_context.py" -- --frames 50 --width 960
uv run python human_review/make_motion_gif.py
uv run python human_review/build_motion_player.py \
  --gif-provenance human_review/frames/motion_context/gif_manifest.json
```

輸出必須是新位置；不覆寫既有 PNG /GIF。GIF 是獨立縮圖版本，完整圖與逐格來源在播放器中。

2026-10-07 補充：[先看完整空間導覽](frames/spatial_context/guide.html)。
依序看整體 school 中的 office 位置、一樓與 camera 位置、鏡頭推進、原有 10 秒移動，
最後看 HR-01 接縫 / body guard 與 HR-02 landmark→floor 對照。
鏡頭推進只改變觀看位置；人物仍是既有 office 約 3.87 m 的投影 / 候選移動，
沒有增加跨房間路徑或已核准物理範圍。原四項決策、問題 hash 與原 57 張 evidence 保留。
一樓來源座標圖補足 camera 定位；相對位置與 camera 原生高度不構成 FOV 或 binding 證明。
新增 3 張 source context still 與 25 張鏡頭 frame 的獨立 manifest：
[spatial context](frames/spatial_context/spatial_context_manifest.json)。

重建 HTML：`uv run python human_review/build_spatial_guide.py`。
重現已保存的 Blender 圖片時，在已物化原 frozen inputs 的 **fresh checkout** 中先
`cp human_review/history/spatial_context_initial_renderer.py human_review/render_spatial_context.py`，
再執行原 renderer 的 Blender command（`--frames 25`）；不能直接執行 history 路徑，
因為 producer 從 script 位置取得 repo root。該 archive 的 SHA 為 `8a5d52f4...305cd92`。
目前 renderer 含改進構圖與預讀 hash 檢查，但因本機空間不足未成功重繪；
保存圖片的 producer 與未 render 的改進版在獨立 manifest 中分別記錄。

先開 [dashboard](index.html)，依 **HR-01 → HR-02 → HR-03 → HR-04** 審查。
每項只有 APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW；APPROVE 選一個完整 profile。
填審查者並匯出 `decisions.json`；下一輪提供這份檔案即可，無需另整理人工證據。
直接編輯 JSON 時，只改 metadata 的 reviewer / submitted_at 與 item 的
decision / selected_option。其他內容改動會被拒絕。

[10 秒連續預覽 / 50 frames / 5 Hz](frames/player.html) 使用 Blender evaluated source、
public 2D observations、projected points 與 inferred candidate hypotheses。
OBSERVED → GAP → OBSERVED；GAP 中人物位置是候選路徑示範，**不是 GT 或觀測位置**。
WALKABLE、PORTAL context、semantic OBSTACLE、body cylinder / clearance 都有獨立標示。
Office 的 solid obstacle components 尚無 APPROVED，不能把紅色 footprint 當正式 collider。
Camera still 是 bounded evaluated source snapshot，不證明完整 scene occlusion。

只請核准 **1F office 的精確 body guard**；不審整棟、1,422 WALL patches、73 HC WALL、
8 portal conflicts 或 Stair A/B。左路徑違反已核准 clearance，自動排除。
既有圖片中的 face7356 東側牆只作位置 context，位於本次 body guard 之外，沒有另一項決策。

| ID | Human-readable location/problem | Blocks | Recommended | Decision |
|---|---|---|---|---|
| HR-01 | 一樓 office 行走帶：地板接縫與房間內部的物理語意 | Case 1/2/3 | APPROVE / LOCAL_SOURCE_SURFACE_ONLY | 未決定 |
| HR-02 | 可見 landmark 如何對應核准地板上的人物落點 | Case 1/2/3 | APPROVE / SOURCE_BOUND_RIGID_LANDMARK_OFFSET | 未決定 |
| HR-03 | Coverage 的正式 ADE 容差 | Case 1/2/3 | APPROVE / ADE_EPSILON_0_50_M | 未決定 |
| HR-04 | 固定現有速度上限與長 GAP 的 timing 假設 | Case 1/2/3 | APPROVE / EXISTING_SPEED_WITH_SUPPORTED_DWELL | 未決定 |

## Formal setting review

下表只列 Case 1–3 必須固定的設定；已有 authority 或唯一 contract 的直接採用。
沒有用 GT / accuracy 結果選容差，sampling 不丟棄困難 evidence。

| Setting | Current status | Existing evidence | Recommended final value | Why |
|---|---|---|---|---|
| Scale / body / clearance / contact | APPROVED；自動沿用 | approved scale + physical policy | 0.0247 m/BU；r0.30 / h1.70 / clearance0.05 m；contact0.001 m | 不重審已核准參數 |
| K / sampling / alignment | 自動採用 | user K + public 0.2 s grid + MetricConfig | K1/2/3；5 Hz；完整 timestamp extent；piecewise linear | 既有支援且可自動推導 |
| Projection / reference | HR-02 | source calibration + approved floor + public endpoint pixels | exact-time multiview → single-view fixed plane；exact marker→floor offset | HR-02 確認房間／marker 語意；fallback 沿用 protocol |
| Coverage | HR-03 | protocol initial targets；現有 D=ADE | ADE < 0.50 m；另可選 <1.00 m | 研究者決定 error tolerance，跑前鎖定 |
| Speed / timing | HR-04 | existing 32 BU/s + ReconstructionPolicy | 0.7904 m/s；slack1 s；uniform + supported departure dwell | 明確核准既有運動模型 |
| Solver precision / uncertainty | 自動沿用 | existing numeric contracts / sidecar | 不改 solver；sigma 未聲明則 uncertainty UNAVAILABLE / LOW_CONFIDENCE | 不能捏造 probability 或放寬 tolerance |
| Case / baseline definitions | 沿用 protocol；實例待自動 proof | PHASE1_BENCHMARK_PROTOCOL + A/B/C masks | unique / branching / long-GAP；既有 baselines / ablations；Case4 DEFERRED | 不新增 benchmark 或調 threshold |

## Case-specific blocker map

### Case 1

- Human blocker 數：4。
- IDs：HR-01 / HR-02 / HR-03 / HR-04（共用項目只列一次）。
- 全部 APPROVE 後可立即 formal run：**否；先完成下列自動認證**。
- bounded certificate PASS
- 合法 visibility→GAP→visibility
- school route inventory 的唯一主要可行 route proof

### Case 2

- Human blocker 數：4。
- IDs：HR-01 / HR-02 / HR-03 / HR-04（共用項目只列一次）。
- 全部 APPROVE 後可立即 formal run：**否；先完成下列自動認證**。
- bounded certificate PASS
- 至少兩條真正可行且有 route diversity 的 school routes；目前 direct/right 平行 offset 不足以證明 branching

### Case 3

- Human blocker 數：4。
- IDs：HR-01 / HR-02 / HR-03 / HR-04（共用項目只列一次）。
- 全部 APPROVE 後可立即 formal run：**否；先完成下列自動認證**。
- bounded certificate PASS
- 現有 protocol 長 GAP stress instance 的 speed/time feasibility、候選增長與 termination proof

## 決策後續

[decision application pipeline](DECISION_APPLICATION.md) 已準備，可驗證完整決策、
重新計算 bounded certificate 並輸出 hash-bound approved input lock。
目前 formal authority adapters 與 Case inventory 仍須由 agent 完成自動工作；
原 diagnostic context / parallel offset routes 不會因 APPROVE 直接變 FORMAL。
之後依 [resume_plan.json](resume_plan.json) 的十個階段續作，只有真正新的 geometry
矛盾或必要 case scope / binding 超出本次核准範圍才重開人工 gate。

## 固定格式的四項問題

### HR-01 — 一樓 office 行走帶：地板接縫與房間內部的物理語意

Location:

- Floor：1F
- AREA：AREA_1F_OFFICE / WALK_1F_OFFICE
- PORTAL：無；本次候選在 office 內，不核准任何門洞或跨區路徑
- nearby object：group_0；office obstacle 僅供位置辨認
- Blender Outliner 搜尋名稱：group_0 / AREA_1F_OFFICE / WALK_1F_OFFICE

Why it blocks:

- Case 1–3 的 local scope certificate 目前被 group_0 的零面積接縫與未知 enclosure ownership 阻塞。
- 不處理時可以保留診斷候選，但不能宣稱 floor/body collision 或局部物理有效性已正式認證。
- 只核准下列 body guard 範圍內的 source-surface 語意；不核准整個 group_0、其他房間、WALL 或 portal。

Evidence:

![HR-01 範圍近看：紫色 1975/2398 接縫、blue body guard、人物 cylinder / clearance；畫面只有候選 hypothesis。](frames/office_scope_closeup.png)

HR-01 範圍近看：紫色 1975/2398 接縫、blue body guard、人物 cylinder / clearance；畫面只有候選 hypothesis。

![HR-01 俯視近看：exact body guard 與 footpoint domain；左路徑 AUTO_REJECT，direct/right 仍 NOT_CERTIFIED。](frames/office_scope_top_closeup.png)

HR-01 俯視近看：exact body guard 與 footpoint domain；左路徑 AUTO_REJECT，direct/right 仍 NOT_CERTIFIED。

![Blender evaluated source 俯視；紅線是接縫，紅色左路徑已自動淘汰。](frames/office_top.png)

Blender evaluated source 俯視；紅線是接縫，紅色左路徑已自動淘汰。

![側視：approved source floor、landmark projected dots 與待核准 offset；cylinder / clearance 請看連續 frames。](frames/office_side.png)

側視：approved source floor、landmark projected dots 與待核准 offset；cylinder / clearance 請看連續 frames。

![局部 source geometry、WALKABLE、PORTAL context 與候選行走帶。](frames/office_oblique.png)

局部 source geometry、WALKABLE、PORTAL context 與候選行走帶。

[10 秒 continuous preview / 逐 frame](frames/player.html)

objects:

- group_0 / component-00000000
- WALK_1F_OFFICE
- AREA_1F_OFFICE

faces:

```json
[
  {
    "object": "group_0",
    "evaluated_source_face": 1975,
    "evaluated_triangle": 1975,
    "mesh_sha256": "9867422c383ce56b83048239a672fc9f0bb6224e7d6403b43487f9e783d24704",
    "machine_status": "EXACT_ZERO_AREA_DEGENERATE"
  },
  {
    "object": "group_0",
    "evaluated_source_face": 2398,
    "evaluated_triangle": 2398,
    "mesh_sha256": "9867422c383ce56b83048239a672fc9f0bb6224e7d6403b43487f9e783d24704",
    "machine_status": "EXACT_ZERO_AREA_DEGENERATE"
  }
]
```

bounds:

```json
{
  "footpoint_bu": [
    [
      1399.9985317206952,
      1939.9994361310253,
      20.07884979248047
    ],
    [
      1411.9999242955855,
      2096.8005463472678,
      20.07884979248047
    ]
  ],
  "footpoint_m": [
    [
      34.57996373350117,
      47.91798607243632,
      0.49594758987426757
    ],
    [
      34.87639813010096,
      51.79097349477751,
      0.49594758987426757
    ]
  ],
  "body_guard_bu": [
    [
      1385.8284912348652,
      1925.8293956451953,
      18.014072464545244
    ],
    [
      1426.1699647814155,
      2110.9705868330975,
      90.96953805158978
    ]
  ],
  "body_guard_m": [
    [
      34.22996373350117,
      47.56798607243633,
      0.4449475898742675
    ],
    [
      35.22639813010096,
      52.140973494777505,
      2.2469475898742677
    ]
  ],
  "seam_bounds_bu": [
    [
      1396.8341979980469,
      1713.4693145751953,
      20.07884979248047
    ],
    [
      1396.8341979980469,
      2123.0493927001953,
      20.07884979248047
    ]
  ],
  "seam_bounds_m": [
    [
      34.50180469055176,
      42.32269207000732,
      0.49594758987426757
    ],
    [
      34.50180469055176,
      52.439319999694824,
      0.49594758987426757
    ]
  ]
}
```

centroid:

```json
{
  "bu": [
    1396.8341979980469,
    1982.585688273112,
    20.07884979248047
  ],
  "m": [
    34.50180469055176,
    48.969866500345866,
    0.49594758987426757
  ]
}
```

measurements:

- radius 0.30 m = 12.145749 BU；height 1.70 m = 68.825911 BU；clearance 0.05 m = 2.024291 BU（既有 APPROVED）。
- 左側 route 最小 support clearance 7.674678 BU / 0.189565 m < 14.170040 BU / 0.35 m：AUTO_REJECT，不需人工決策。
- direct / right support clearance >= 19.674678 BU / 0.485965 m；完整 body/source certificate 仍 NOT_CERTIFIED。
- body guard 相交 source triangles 共 12：10 個已核准支撐三角形，2 個 exact-zero-area seams。

current_authority:

- Architectural scale / body policy / WALK_1F_OFFICE source support：APPROVED。
- source seams / component interior：HUMAN_REVIEW；local certificate：REVIEW / DEGENERATE_SOURCE_BODY_CONTEXT_TRIANGLE。
- OBSTACLE_1F_OFFICE_01 / 02 的語意已核准，但 approved solid components = 0；不把它們當 hard collider。

relevant_frames:

- Front frame 20 / t=4.0 s → 全視角 GAP → Rear frame 45 / t=9.0 s；10 秒 preview 只顯示 public observations / inferred candidates。

Current machine conclusion:

已確定：

- 兩個 source faces 1975 / 2398 精確為零面積；floor 高度、body guard 與 support clearance 可自動計算。
- source atlas / mesh hashes 已固定；沒有缺省擴充整棟 authority。

尚不能確定：

- 請確認這條接縫不代表實際佔用體積，且這個 bounded room interior 是由 source boundary surfaces 表示的自由空間。
- 數值上的零面積不能自行代替 physical semantics；APPROVE 不會自動產生 PASS。

Recommended decision:

**APPROVE / LOCAL_SOURCE_SURFACE_ONLY**。

若畫面與 source scene 一致，採最小範圍 surface 語意即可；所有非零面積 source surfaces 仍照原 collision / support 檢查。

APPROVE 具體選項：

- `LOCAL_SOURCE_SURFACE_ONLY` — 局部 boundary surfaces；零面積接縫不佔體積（建議）。只聲明 body guard 內 group_0/component-00000000 的 interior 不作實心 collider，與指定兩個接縫沒有 solid ownership。
- `EXACT_DERIVED_SURFACE_REPAIR` — 相同局部語意；另允許精確接縫的 derived repair。只允許在衍生 surface context 中排除這兩個 exact-zero-area faces；原 .blend 與非零面積 geometry 保持原樣。

Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。

### HR-02 — 可見 landmark 如何對應核准地板上的人物落點

Location:

- Floor：1F
- AREA：AREA_1F_OFFICE / WALK_1F_OFFICE
- PORTAL：無；本次候選在 office 內，不核准任何門洞或跨區路徑
- nearby object：group_0；office obstacle 僅供位置辨認
- Blender Outliner 搜尋名稱：group_0 / AREA_1F_OFFICE / WALK_1F_OFFICE / CAM_1F_AUDITORIUM_FRONT / CAM_1F_AUDITORIUM_REAR

Why it blocks:

- Case 1–3 需要 camera → 可見 landmark → approved floor contact 的正式綁定。
- 目前 projected marker 位於地板上方約 1.36 m；直接當人物落點會破壞 support、collision 與 metric reference。
- Office 合法同步雙視角為 0/50；若不允許有 provenance 的 single-view fallback，GAP endpoints 無法正式提供。

Evidence:

![CAM_1F_AUDITORIUM_FRONT：frame 20 / t=4.0 s；bounded source snapshot，不是整場景 occlusion proof。](frames/camera_cam_1f_auditorium_front_frame20.png)

CAM_1F_AUDITORIUM_FRONT：frame 20 / t=4.0 s；bounded source snapshot，不是整場景 occlusion proof。

![CAM_1F_AUDITORIUM_REAR：frame 46 / t=9.2 s；bounded source snapshot，不是整場景 occlusion proof。](frames/camera_cam_1f_auditorium_rear_frame46.png)

CAM_1F_AUDITORIUM_REAR：frame 46 / t=9.2 s；bounded source snapshot，不是整場景 occlusion proof。

![Landmark 與 approved floor 高度差；cylinder placement 是待核准的 hypothesis。](frames/office_side.png)

Landmark 與 approved floor 高度差；cylinder placement 是待核准的 hypothesis。

[10 秒 continuous preview / 逐 frame](frames/player.html)

objects:

- group_0
- AREA_1F_OFFICE
- WALK_1F_OFFICE
- CAM_1F_AUDITORIUM_FRONT
- CAM_1F_AUDITORIUM_REAR

faces:

- group_0 的 approved source floor binding：完整 source faces / hashes 在 floor_support_details 與 geometry_evidence.json；camera 不是 mesh face。

bounds:

```json
{
  "approved_local_footpoint_bu": [
    [
      1399.9985317206952,
      1939.9994361310253,
      20.07884979248047
    ],
    [
      1411.9999242955855,
      2096.8005463472678,
      20.07884979248047
    ]
  ],
  "approved_local_footpoint_m": [
    [
      34.57996373350117,
      47.91798607243632,
      0.49594758987426757
    ],
    [
      34.87639813010096,
      51.79097349477751,
      0.49594758987426757
    ]
  ]
}
```

centroid:

- N/A（camera / plane binding）；floor plane normal = (0,0,1)。

measurements:

- landmark Z=75.12884788513183 BU / 1.8556825427627563 m。
- floor Z=20.07884979248047 BU / 0.49594758987426757 m。
- 精確 offset=55.049998092651364 BU / 1.3597349528884888 m；由已核准 support 與 inference plane 相減，不由 GT 求值。
- Camera calibration / pose / pixel UV 保存在 settings_evidence.json；以 source hash + observations hash 綁定。

current_authority:

- floor / scale APPROVED；camera intrinsics/pose SOURCE_BOUND；camera-landmark-floor semantics HUMAN_REVIEW；legacy context DIAGNOSTIC。

relevant_frames:

```json
[
  {
    "camera_id": "CAM_1F_AUDITORIUM_FRONT",
    "frame_id": 20,
    "timestamp": 4.0,
    "public_uv": [
      838.4602382939759,
      86.52395569480393
    ]
  },
  {
    "camera_id": "CAM_1F_AUDITORIUM_REAR",
    "frame_id": 46,
    "timestamp": 9.2,
    "public_uv": [
      285.075031753748,
      67.286656808141
    ]
  }
]
```

Current machine conclusion:

已確定：

- 固定 calibration、offset、timestamp 與單視角 availability 都已算出。
- 不用 GT 選 pair 或 hypothesis；multiview unavailable 不等於 inference failure。

尚不能確定：

- 請核准所觀測 marker 的正式語意，以及這兩個 camera 對 bounded office floor 的綁定與 fallback。
- 新 dataset 的 FOV / occlusion / scope containment 仍須自動驗證。

Recommended decision:

**APPROVE / SOURCE_BOUND_RIGID_LANDMARK_OFFSET**。

保留 source-bound marker 與現有 observation producer，只新增精確 landmark→footpoint adapter；新 formal observations 必須 fresh export。

APPROVE 具體選項：

- `SOURCE_BOUND_RIGID_LANDMARK_OFFSET` — 保留固定 marker；精確扣 Z offset 到地板（建議）。保留 XY 與 calibration；inference 的位置語意統一為 FLOOR_CONTACT_POINT；single-view fallback 保留 method / confidence / uncertainty。
- `FLOOR_CONTACT_MARKER` — 改用可見足點 marker；offset=0，重新 export。足點不可見就保留 GAP；不得從其他 marker 或 GT 偽造觀测。

Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。

### HR-03 — Coverage 的正式 ADE 容差

Location:

- Floor：N/A；Case 1–3 共用研究設定
- AREA：N/A；Case 1–3 共用研究設定
- PORTAL：N/A；Case 1–3 共用研究設定
- nearby object：N/A；Case 1–3 共用研究設定
- Blender Outliner 搜尋名稱：N/A；Case 1–3 共用研究設定

Why it blocks:

- Case 1–3 的 Coverage@K 必須預先固定 epsilon；目前 formal epsilon=null，未決定只能報 N/A。

Evidence:

objects:

- N/A

faces:

- N/A

bounds:

- N/A

centroid:

- N/A

measurements:

- 兩個研究選項：ADE < 0.50 m（20.242915 BU）或 < 1.00 m（40.485830 BU）；不是實測結果。

current_authority:

- UNRESOLVED_RESEARCH_SETTING；protocol Case1 initial target 0.50 m / Case3 FDE initial target 1.00 m 只提供尺度依據，沒有 Coverage approval。

relevant_frames:

- N/A；不需要視覺或 GT 來決定研究容差。

Current machine conclusion:

已確定：

- 現有唯一支援 D=ADE、3D Euclidean arithmetic mean、strictly < epsilon；K=1/2/3。

尚不能確定：

- 研究者接受的正式 Coverage 容差；不能從 accuracy 結果反推。

Recommended decision:

**APPROVE / ADE_EPSILON_0_50_M**。

0.50 m 與既有 Case1 target 尺度一致；所有 Case / method / K 共用，執行後不可改。

APPROVE 具體選項：

- `ADE_EPSILON_0_50_M` — 全體 ADE < 0.50 m（建議）。
- `ADE_EPSILON_1_00_M` — 全體 ADE < 1.00 m。

Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。

### HR-04 — 固定現有速度上限與長 GAP 的 timing 假設

Location:

- Floor：1F
- AREA：AREA_1F_OFFICE / WALK_1F_OFFICE
- PORTAL：無；本次候選在 office 內，不核准任何門洞或跨區路徑
- nearby object：N/A；運動模型 research setting
- Blender Outliner 搜尋名稱：group_0 / AREA_1F_OFFICE / WALK_1F_OFFICE

Why it blocks:

- Case1/2 travel-time pruning、Case3 長 GAP / detour / slack 需要正式 speed ceiling 與已支援的 timing hypothesis policy。32 BU/s 目前只是 diagnostic setting。

Evidence:

![t=6.0 s 的 GAP；人物與路徑均是 public candidate hypothesis，不是 GT。](frames/sequence_030.png)

t=6.0 s 的 GAP；人物與路徑均是 public candidate hypothesis，不是 GT。

[10 秒 continuous preview / 逐 frame](frames/player.html)

objects:

- WALK_1F_OFFICE

faces:

- N/A；timing contract

bounds:

```json
{
  "candidate_footpoint_bu": [
    [
      1399.9985317206952,
      1939.9994361310253,
      20.07884979248047
    ],
    [
      1411.9999242955855,
      2096.8005463472678,
      20.07884979248047
    ]
  ],
  "candidate_footpoint_m": [
    [
      34.57996373350117,
      47.91798607243632,
      0.49594758987426757
    ],
    [
      34.87639813010096,
      51.79097349477751,
      0.49594758987426757
    ]
  ]
}
```

centroid:

- N/A

measurements:

- 最大速度 32 BU/s = 0.7904 m/s；direct slack 1.0 s。
- departure waypoint dwell 是現有唯一 waiting alternative；uniform continuous timing 仍第一順位。
- preview 的 GAP endpoint duration=5.0 s；它不是正式 Case3 長 GAP。

current_authority:

- Speed ceiling：PROPOSED；dwell/uniform：EXISTING_SUPPORTED_CONTRACT；沒有 measured-person speed authority。

relevant_frames:

- Office t=4.0→9.0 s GAP endpoint evidence；正式 Case3 必須另由 protocol stress inventory 固定並 fresh export。

Current machine conclusion:

已確定：

- 現有速度上限、scale 換算、slack 與 timing supported variants 已確認。
- 5 Hz 可由公開 timestamps 推導，直接沿用，不需人工算。

尚不能確定：

- 是否正式採用這個 research speed ceiling，以及是否保留 existing departure dwell alternative。
- 正式 Case3 stress instance 必須通過凍結前自動 timing feasibility / termination proof。

Recommended decision:

**APPROVE / EXISTING_SPEED_WITH_SUPPORTED_DWELL**。

沿用現有 32 BU/s ceiling、1 s slack 與 supported dwell；不新增速度或 waiting model。

APPROVE 具體選項：

- `EXISTING_SPEED_WITH_SUPPORTED_DWELL` — 0.7904 m/s；均速 + 已支援 departure dwell（建議）。
- `EXISTING_SPEED_UNIFORM_ONLY` — 0.7904 m/s；只保留均速 timing。

Human choices：**APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。

## Provenance / reproduction

- Branch：`phase1/finalization-sprint`；blocked checkpoint：`85f5e6b055e75d286c1519e6c5ba2f2efc416347`。
- Source .blend SHA-256：`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`；source 未 save / modify。
- Immutable question payload SHA-256：`e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463`。
- [manifest.json](manifest.json)：本 package hashes；[frames/visual_manifest.json](frames/visual_manifest.json)：source/frames hashes。
- [geometry_evidence.json](geometry_evidence.json)、[settings_evidence.json](settings_evidence.json)：source-bound measurements / calibration / decisions basis。
- 本輪沒有 formal Cases、GT-assisted decision、核准、main merge 或 freeze tag。
- [history/blocked_checkpoint](history/blocked_checkpoint/) 保存舊 generic gate；舊 build_review.py 不再是本 dashboard 的 builder。

重建 pending 審查文字 / dashboard：

```sh
uv run python human_review/assemble_review.py
uv run python human_review/write_review_docs.py
uv run python human_review/build_dashboard.py --decisions human_review/decisions.json
```

assemble_review 會拒絕覆寫任何已填決策。
