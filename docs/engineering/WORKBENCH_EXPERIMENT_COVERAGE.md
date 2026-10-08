# 工作台實驗展示覆蓋 / Workbench experiment coverage

2026-10-08 在 `codex/simulation-engineering`、checkpoint
`b484a8479461559942f42a5507132254d5c35b4d` 盤點。**實驗展示尚未全部接入主平台。**
8016 是已採用的主要網頁入口；目前只註冊 E1、E0 兩個合成場景的固定結果。
入口決策、素材存在與功能遷移完成是三種不同狀態。

開啟 [本機共用工作台](http://127.0.0.1:8016)，啟動／materialization 指令見
[工作台指南](SHARED_WORKBENCH.md)。本輪實際開啟研究／管理入口、切換兩場景、
查閱局部事件與評估；沒有 render、重新推論、benchmark、人審發布或遷移程式修改。
完整程式測試未重跑，歷史 2,652-test PASS 綁定原
[product validation](../../data/product/checkpoint_20261008/validation.json)，不是本輪 PASS。
本輪證據另存 [website audit receipt](../../data/engineering/workbench_20261008/website_audit.json)。

## 主平台目前可用內容

[catalog](../../configs/engineering/workbench_v1.json) 只有以下兩筆，兩者是不同模型：

| 場景 / model / run | 完整固定包數量 | 主平台讀取範圍 |
| --- | --- | --- |
| `local-camera` / `synthetic-local-camera-v1` / `local-camera-test-v1` | 4 cameras、244 RGB、18 local records、64 events、11 靜態物件 | E1 pinhole、局部事件、RGB、3D 投影與候選、既有評估 JSON |
| `synthetic-lab` / `synthetic-lab-v1` / `simulation-v2` | 2 cameras、102 RGB、6 local records、21 events、6 靜態物件 | E0 affine、局部事件、RGB、3D 投影與候選、既有評估 JSON；實體 camera pose `UNKNOWN` |

數量屬完整包；當前 camera/time 查詢只回傳其局部子集。E0 的 21 events 是 facade
事件集合，不是 21 個 canonical blind gaps；原 M1–M6 的 4 gaps／8 routes 仍保留原意義。
兩個 [loader](../../src/amidst/workbench/scenes.py) 固定選擇凍結的
`photos_plus_observations/RESULTS`。展示／人審／測試是工作模式，不是照片輸入模式切換。

| 能力 | 已接入 8016 的範圍 | 仍缺少的展示／操作 |
| --- | --- | --- |
| 地點、鏡頭與查詢 | server catalog、兩場景、有限 camera/time、事件及 observation 查詢 | 任意其他模型；local-track seed checklist／多目標選擇流程 |
| RGB／時間軸 | 最多四鏡頭、實際 frame refs／timestamp、影格 seek／回放、缺圖狀態 | MP4、master camera、影片速度／seek／media-clock 同步診斷 |
| 局部 3D | 註冊區域／門／可行走面／校準、選定事件的投影與候選路線 | 完整 Blender mesh；產品 case 多事件／多目標 timed hypotheses 展示 |
| 場景與事件人審 | annotation 草案／差異／驗證／發布／歷史／JSON 匯出；獨立事件判定、處理備註 | overlay 一鍵重跑；investigation report hash review／HTML 報告匯出 |
| 工具與調查 | scene/query/event/timeline 及工作台限定操作 | bounded intent、typed plans、execute／stop／resume、保存案例、外觀查找、stitch 工具接入 |
| 測試 | 選定 camera/time 的六項資料／接口檢查、session logs | pytest runner、實驗／消融 runner、reproduction 比較入口 |
| 評估 | 按需閱讀 E0／E1 既有 aggregate JSON | 專用比較表／圖、product appearance／stitch 評估、Office benchmark／Rerun、GT debug |
| 管理 | 事件摘要、必要照片與處理紀錄 | 管理 3D／多鏡頭區仍為明示 placeholder；沒有研究測試／評估權限 |

實作依據：[SceneAdapter](../../src/amidst/workbench/scenes.py) 的 capabilities
（159–165 行）與 loaders（288–315 行）；[service](../../src/amidst/workbench/service.py)
的 action allowlist（174–182 行）及 GET routes（388–428 行）；
[workbench UI](../../frontend/workbench/app.mjs) 的資源列（268–269 行）、評估（364–371 行）、
單事件 3D／影格播放（392–415 行）及 annotation export（527–531 行）。
`video=false`、`inference_execution=false` 是目前實際能力。
未註冊的 Office scene、影片 route 與 product intent action 在實際 HTTP 核對中拒絕。

## 評估顯示的實際意義

E1 JSON 已有 pixel/local identity、association、behavior、retrieval、geometry，
以及固定候選池的 `full/without_appearance/without_space/without_time` 消融。
兩種照片模式的既有量測也在摘要中；這表示能閱讀已存結果，並不表示 8016 可切換輸入
重跑判斷。E1 消融使用八個 eligible queries；產品 appearance 的五個 pure-track queries
是另一 population，不合併成相同實驗。

測試按鈕回傳 `SELECTED_CAMERA_TIME_ONLY`，不重算精度或 formal gates。
沒有樣本保留 `NOT_RUN`；annotation 改變後新檢查回傳 `NEEDS_RERUN`。
評估按鈕不打開 GT sidecar；畫面「GT 與 benchmark」說明不能當作已存在 GT debug。
獨立人類研究評估也不擴張 Agent allowlist。完整 GT 仍在原 simulation/export、
evaluation/debug 邊界；主展示不加入 GT overlay。

## 既有展示家族與素材狀態

此表盤點有文件／來源依據的展示家族，不把任意磁碟圖片當作已認證的實驗。
素材存在只代表本機檔案存在；歷史 reader/hash 驗證仍使用原日期，不冒稱本輪重驗。
未註冊的來源需要獨立 source/context/clock/unit adapter、資料邊界與展示驗證。

`E` 表示本輪工程 checkout，`C` 表示 immutable canonical checkout；C-only 不表示已匯入 E。
以下素材路徑相對於其所屬 checkout，raw／PNG／MP4／RRD 均不隨本輪文件 push。

| 展示家族 | 本輪核對到的素材 | 8016 覆蓋與限制 |
| --- | --- | --- |
| E0 simulation-v2 | E：`data/engineering/local_run/simulation_v2/presentation/inference.{rrd,png}`；102 RGB | 場景已接；離線 RRD／PNG 未登錄展示庫。SYNTHETIC、主展示 GT=false |
| E1 local-camera | E：`data/engineering/local_run/local_camera_v1/test/checkpoints/final/`；244 RGB、`cards/` 7 PNG | 場景／照片／事件已接；cards 未形成展示庫。有限精度的獨立 synthetic pilot |
| P7–P12 product | E：`data/product/local_run/operator_v2/video_manifest.json`；`data/product/local_run/media_pool/` 4 MP4 | 已物化／未接入；現有 8020 功能見產品指南。15fps hold presentation，來源／CV 2.5Hz |
| Reviewed Office recovery demos | E：`data/finalization/reviewed_run_recovery_20261008/evaluation/demos/{case1,case3}/`；2 RRD＋2 PNG＋2 presentation JSON | 已物化／未接入。Case1 與 Case3 temporal 局部結果，primary GT=false；full gates 仍 BLOCKED |
| Recovery benchmark／消融 | 同 recovery 的 `evaluation/benchmark_table.{json,csv,md}`、`charts/` 20 PNG、`ablations/benchmark_table.*` 與 `ablations/charts/` 17 PNG | 已物化／未接入。27 baseline／45 ablation rows，保留 BLOCKED／N/A |
| Historical reviewed V5 | E：`data/finalization/reviewed_run_v5/evaluation/` 的表、20 charts PNG、2 presentation JSON；2 reviewed RRD／preview PNG 與 ablation charts 缺失 | 歷史報表已物化／未接入；raw demo 未物化。現在可用 Office raw 應指 recovery，不能冒稱 V5 raw 存在 |
| Office／auditorium／corridor diagnostic Rerun | C-only：`data/pilot/phase1_finalization_20261006/{local_run,fresh_run}/diagnostics/<stream>/demo/`；6 RRD＋6 PNG 與 presentation JSON；E 的 `data/finalization/local_run/diagnostics/` 缺失 | 已物化／未接入。DIAGNOSTIC、GT debug 層獨立，不是正式 Case demos |
| School downstream 3D pilot | C-only：`data/pilot/phase1_downstream_20261005/run_01/visualization/{debug.rrd,preview_3d.png,review_3d.html}` | 已物化／未接入；含 50 GT debug markers，僅獨立研究 debug，不進主展示／Agent |
| School rendered pilot galleries | C-only：`data/pilot/school_v3_pilot_20261005/{review.html,trajectory_preview.gif}`、`school_v3_multisite_20261005/review.html`、`phase1_wall_pilot_20261005/office/review.html` 及相關 PNG／GIF | 已物化／未接入；marker／PILOT annotations 不是未標註 CV sequence。歷史 raw frame 數未重新枚舉 |
| Human-review／四格 preview | E：`human_review/index.html`、`human_review/playback/{index.html,data.js}`；build manifest 的 58/58 PNG 存在，含 50 格診斷影格；topology PNG 存在 | 已物化／未接入；獨立 8768 路徑。VIEW_ONLY／DIAGNOSTIC，camera stills 4／5／9 s 不是連續 camera video |
| Projection upgrade／mitigation | comparison／report／robustness 工具已存在；`data/pilot/phase1_projection_model_upgrade_20261006/verified_run/` 在 E／C／已知原 worktree 缺失 | 未物化／未接入。Helpers／historical PASS 不代表 plots/results 仍存在；需 exact inputs 重建／驗證 |
| Native／mock benchmark plots | E：`data/reports/benchmark/` 11 PNG＋JSON／MD；`mock_comparison/` 17 PNG＋JSON／MD | 已物化／未接入；分別 SYNTHETIC REGRESSION／MOCK VALIDATION，不是 formal school results |
| 原 blocked checkpoint 圖表 | E：`data/finalization/checkpoint/` 8 PNG、14 JSON、2 CSV、1 MD | 已物化／未接入；只作歷史區。27 rows 的 NOT_RUN／N/A 不覆蓋後續 recovery |
| Legacy four-case Rerun／Phase 2 API | C-only：`data/candidates/fake_downstream_20261001/{single_path,branching_top_k,temporal_slack,simplified_stair}/debug.rrd` 4/4 存在；E 有 mock config／TypeScript consumer | RRD 未接入；8000／consumer 是低階接口，不是 Agent UI。Synthetic target IDs 保持內部隔離；stair fixture 不解鎖 Case4 |

來源／既有使用方法：[simulation](SIMULATION_ENGINEERING.md)、[local camera](LOCAL_CAMERA_PILOT.md)、
[product](LOCAL_PHASE2_PRODUCT.md)、[恢復 runtime](../operations/PHASE1_RESTORED_RUNTIME.md)、
[研究交付 handoff](../operations/PHASE1_RESEARCH_RELEASE_HANDOFF.md)、
[reviewed reproduction](../research/PHASE1_REVIEWED_REPRODUCTION.md)、
[reviewed benchmark](../research/PHASE1_REVIEWED_BENCHMARK.md)、
[diagnostic demo](../research/PHASE1_DEMO.md)、[歷史 final report](../research/PHASE1_FINAL_REPORT.md)、
[preview](../../human_review/playback/README.md)、[資料盤點](../../data/README.md)、
[Phase 2 接口](PHASE2_INTEGRATION.md)。本輪只檢查指定 artifacts／manifests，沒有全目錄掃描
或讀完整 GT。Office／school 等來源仍需核對 native BU／顯式 normalization 與各自 authority；
不能借 E0／E1 校準、名稱或已存在圖片擴張權限。

## 本輪檢視與有效待修

實際瀏覽器確認研究／管理入口、兩個 scene options、E1 局部事件細節、3D，及同一
2.8 s 的四張 240×180 RGB 成功載入。E1 WEST 0–10 s 檢查為 6/6、16 events／2 observations；
E0 CAM_A 0–10 s 為 6/6、15 events／3 observations。兩場景評估按鈕可讀；管理畫面明示
多鏡頭／3D 未接入。本輪沒有寫 draft、decision、note 或 publication。
另完成十次固定預期 HTTP 核對（含預期拒絕），不包含未計數的瀏覽器請求。

以下為待修，這次文件盤點沒有修復它們：

- **評估 payload 邊界：** `SceneAdapter.evaluation()` 核對 run/model/config/dataset/freeze
  headers 後直接返回摘要 JSON，缺少 aggregate DTO allowlist 與內容 digest 認證。
  唯讀 sentinel 驗證只替換複製 adapter 的記憶體摘要，假的 identity/private-path 額外欄位
  可穿過；現有摘要未發現該污染，不代表真實資料已外洩。新增 adapter 前須補此守門。
- **舊測試結果顯示：** UI publish handler 更新人審版本時未清除 `state.test`，先前
  v0 PASS 可能持續顯示；後端重新檢查會正確報 `NEEDS_RERUN`。
  此項以 source inspection 確認，本輪沒有發布版本重現。
- **評估文字：** 改為準確描述「既有 aggregate 摘要」，避免暗示 GT debug 或完整
  benchmark runner 已接入。現有可展開 JSON 也不能代替完整實驗展示頁。

來源： [evaluation loader](../../src/amidst/workbench/scenes.py) 249–285 行；
[publish handler](../../frontend/workbench/app.mjs) 470 行；
[version check](../../src/amidst/workbench/service.py) 326–329 行。

後續把已物化產品功能接入共用入口，再為研究／診斷家族補具 capability 的 adapter。
保留所有替代、原 IDs、來源／時鐘／單位與獨立 GT debug；不以 iframe／舊連結存在代替
共用角色、scope、資料與操作契約的遷移驗證。缺 raw 的家族先照 exact inputs 物化並驗證；
formal Cases 2/3/full Exit 維持 `BLOCKED`，Case 4 `DEFERRED`，原 Phase 2 branch/tag `FROZEN`。
尚未正式的外部模型 API 與 token 章節維持空白。

## English

The primary workbench is operational, but **not all experiment presentations are integrated**.
The 2026-10-08 audit at `b484a84` verifies only two registered frozen synthetic scenes, E1 and E0.
They expose bounded events, source RGB frames, local 3D candidates, human annotations and
preexisting evaluation JSON. Both use `photos_plus_observations/RESULTS`; work modes do not
select the inference input mode. Video and inference execution capabilities are false.

Product investigations, appearance tools, saved cases/reports and MP4 synchronization remain
outside 8016. Existing Office/Rerun, preview and projection presentations need source-bound
adapters; missing historical raw output must not be claimed as available. Aggregate reading
and selected-scope checks are not a complete benchmark, ablation or reproduction runner.

This documentation-only audit includes actual browser operation, ten HTTP assertions and
scoped asset existence checks. No program suite, inference, GT debug or benchmark was rerun.
Evaluation DTO/content authentication, cached checks after annotation publication and misleading
GT wording remain actionable issues; no real data leak is claimed by the sentinel-only probe.
Formal research acceptance and frozen branches remain independent.
