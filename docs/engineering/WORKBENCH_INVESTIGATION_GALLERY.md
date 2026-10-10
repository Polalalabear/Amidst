# 工作台人物調查與研究展示庫

2026-10-10 增量接入的主入口仍是 [共用工作台](SHARED_WORKBENCH.md)／8016。
研究角色的「人物調查」重用已凍結 E1 product；「實驗展示」另有來源模型回放與
歷史圖表展示庫。三者分別保存來源與權限，不把歷史診斷圖當成新的 camera observations。
本頁記錄 adapter 契約；當次完整 regression、HTTP 與瀏覽器結果綁定
[整合收據](../../data/engineering/workbench_20261010/integration_validation.json) 及其所在 Git tree。

## 人物調查：既有 product 的外層接入

[`ProductBridge`](../../src/amidst/workbench/product_bridge.py) 將工作台的 server-owned
研究 session 綁到已註冊的 `local-camera` 場景和獨立 product freeze。
它核對兩個已凍結照片模式的 scope、source/model/run、camera calibration、frame metadata、
原 freeze、product record-set receipt 與 video manifest；缺少或失配時不改用其他場景。
E0 的 `synthetic-lab` 沒有這個 E1 product，能力應顯示不可用。

此接入支援以下既有本機操作：

- 有限 camera/time 查詢、局部人物片段、pixel crop 外觀查找、同鏡頭恢復假說。
- `TRACE`／`COMPARE`／`BEHAVIOR`／`MULTI_TARGET` typed plans、逐步執行、停止、續跑、保存案例。
- 全部候選與替代、report hash review、獨立結果判定和 HTML report 匯出。
- 四鏡頭 MP4、主鏡頭、播放速度、seek、soft-sync 診斷與來源影格 offset。

這些操作讀取已凍結結果、執行有限工具計畫及保存調查紀錄；不執行新的 CV、association
或 benchmark。`inference_execution=false`。照片模式選擇只選取各自已驗證的 frozen outputs，
caller 不能宣告 INPUT／RESULTS、替換內部 product session、跨 mode 使用 plan 或繞過 freeze。
場景 annotation、事件人審與 report review 分開保存，不改 canonical observations 或確認人物身分。
查詢完成、plan 結束與完整 exhaustive inventory 是不同狀態，截斷及未完成原因須保留。

外層 action 為 `product_context/tool/intent/execute/plan/case/cases/report/review/videos/timeline/`
`export_report`；binary 路由為 `/api/product_media`、`/api/product_video`。
每次先核對工作台 role/session/scene，再使用原服務允許的 refs 與 tools。
HTTP payload 不包含 product manifest 的本機 source/video-pool locators；影片只返回 opaque refs。
細節見 [既有產品契約](LOCAL_PHASE2_PRODUCT.md)，不是新 Agent semantic reranking。

## 來源 clock 與人體顯示

E1 仍是 `SYNTHETIC`：244 個實際 RGB refs、四鏡頭、來源／CV 2.5 Hz。
15 fps MP4 是既有影格的 hold presentation，不增加照片、量測、可見證據或推論時間點。
同步診斷與 presentation clock 不能替代 source timestamps，也不能用來估計辨識精度。
人形、朝向與步態為 `DISPLAY_ONLY`；它們不表示測得骨架、動作、人物身分或 GT 軌跡。
3D 可見投影、GAP 候選及 HOLD 使用原服務輸出的合法量測／幾何衍生結果，保留所有替代。

原校園 Office「模型與行走」是另一個 source/context/clock/unit binding。
其 50 格、5 Hz、0–9.8 s 公開 body-base／landmark 和三條原 GAP 路徑維持
`image_measurement=false`，不能改稱 pixel-derived CV。模型展示 PNG 和 4／5／9 s camera audit
stills 也不是連續 camera RGB sequence。裁切 mesh 與人體僅供顯示，不擴大 geometry、portal、
walkability 或 collision authority；native BU 的 0.0247 m normalization 不回寫原 bytes。
來源認證與原校園邊界見 [來源展示契約](SOURCE_PRESENTATION_WORKBENCH.md)。

## 展示庫：固定十五家族

[`Gallery`](../../src/amidst/workbench/presentation_gallery.py) 只索引已核對的有限路徑。
`list()` 回固定家族索引、`detail(family_ref)` 回精簡表格／圖 refs／存在狀態，
`media(media_ref)` 只回驗證過的 PNG bytes。根目錄由 server 配置，不接受 caller 路徑。
`gallery_list`、`gallery_detail` 及 `/api/gallery_media` 全部限定人類研究角色；沒有加入 Agent
allowlist，也不提供 filesystem、SQL、shell、source archive 或 arbitrary media 工具。

下表是本次實際 assembly 的數量，不是重新跑實驗。`E` 是工程 checkout，`C` 是唯讀原素材
來源；C-only 素材沒有複製進 E。未提供 canonical root 時，其入口明示不可用。

| 家族 | 已核對展示素材 | 表格／限制 |
| --- | --- | --- |
| E0 simulation-v2 | E：1 PNG、1 RRD 狀態 | 兩照片模式的兩列工程摘要；affine camera pose 仍 UNKNOWN |
| E1 local-camera | E：7 cards PNG | 兩模式 × 四個固定候選池消融，共八列；不能與 product population 混算 |
| P7–P12 product | E：4 MP4 狀態 | 兩模式 appearance／stitch aggregate，共兩列；互動影片走人物調查 |
| Reviewed Office recovery demos | E：2 PNG、2 RRD 狀態 | Case1／Case3 局部 temporal 結果，full gates 仍 BLOCKED |
| Recovery benchmark／消融 | E：37 PNG | 27 baseline＋45 ablation rows，保留原 BLOCKED／N/A |
| Historical reviewed V5 | E：20 PNG | 27 rows；兩 preview PNG＋兩 RRD 缺失，PARTIAL |
| Office／auditorium／corridor diagnostic | C：6 PNG、6 RRD 狀態 | GT_DEBUG_ONLY；不讀其含 debug 資料的 presentation JSON |
| School downstream 3D pilot | C：1 PNG、1 RRD 狀態 | GT_DEBUG_ONLY；歷史圖片含 GT debug markers，不能進主展示 |
| School rendered pilot | C：16 PNG、2 GIF 狀態 | GT_DEBUG_ONLY；人工／軌跡標記不是未標註 CV input |
| Human-review／四格 preview | E：59 PNG | 原 50 sequence PNG＋八 audit stills＋一 topology；VIEW_ONLY |
| Projection upgrade／mitigation | 無可用 plots/results | 兩個固定 verified-run 位置缺失；存在空目錄也不算結果已物化 |
| Native／mock benchmark | E：28 PNG | native 四列與 mock 21 列分開；SYNTHETIC REGRESSION／MOCK VALIDATION |
| 原 blocked checkpoint | E：8 PNG | 27 historical NOT_RUN／N/A rows，不覆蓋 recovery 結果 |
| Legacy four-case Rerun | C：4 RRD 狀態 | GT_DEBUG_ONLY；低階 mock IDs 不公開，stair fixture 不解鎖 Case4 |
| Research accuracy v2 | E：7 cards PNG | 三列 published test comparison；end_to_end/photos_only 卡片、SUPPORTED／UNKNOWN／GAP_ALTERNATIVES 保留 |

原十四家族 **185 PNG** 完整保留；新增七張 v2 cards 後，總數為 **192 PNG、14 RRD
存在狀態、4 MP4 存在狀態**，另有兩筆 GIF 狀態。
原 preview manifest 的 58 張圖片全部驗證，其中原 sequence 50 格完整；topology 圖獨立計數。
各 PNG 在 assembly 保存實際 SHA，media 每次重驗 hash。未知 model/source/authority 保持
`null`；名稱、檔案存在或灰色 mesh 不構成 calibration／coverage／region authority。
RRD／MP4／GIF 不在 Gallery 開啟、解析或提供 bytes，只有 `EXISTENCE_ONLY/STATUS_ONLY`。

`complete=true` 只表示這十五個固定家族的索引完整，不表示所有素材存在、query 成功、
dataset／benchmark 完整或正式研究通過。`MATERIALIZED` 描述展示素材存在；`PARTIAL`、
`NOT_MATERIALIZED` 和 `CANONICAL_ROOT_UNAVAILABLE` 保留缺項。CSV 超過 128 列明示截斷；
原完整 canonical 表與結果仍另存。

Research accuracy v2 使用已發布的
[curated validation](../../data/engineering/accuracy_20261010/validation.json)，固定 content SHA 為
`01639e15c8ca3a7d66c36ffaf2e464e2180189b737cfe8a9625b072b2dc21555`，由 server code 認證。
Gallery 核對新 experiment `accuracy-test-v2-final`、原 source run `local-camera-test-v1`、
dataset/source/context/config/clock、八 variants × 兩 modes 的原 freeze receipts，
以及 published evidence 與 cards manifest 的 content hash。缺失或失配明示 PARTIAL；
不 follow manifest 的 private `source_locator`，不讀 GT、完整 evaluation/debug 或 remaining errors。

三列比較取自已存 `photos_only` 評估。Baseline／features_full 保持原 tracks、115 pairs；
end_to_end 是新 21 tracks／327 pairs 的另一 population。Recall@1 的 .375／.625／.850
不能合併宣稱同一 population gain；pair precision／recall、contact error、UNKNOWN 和候選數
亦保留原量測。V2 不是 sealed holdout、trained ReID 或 formal research freeze。
七張 cards 綁 end_to_end/photos_only freeze；每張含三至五個已有 source RGB 和合法 3D
投影／候選，`gt_overlay=false`，卡片本身是 presentation，不是新的 CV input。
研究設計、消融與退步見 [Accuracy v2](../research/LOCAL_CAMERA_ACCURACY_V2.md)。

## GT debug、錯誤與發布邊界

所有 Gallery 家族皆為 `normal_presentation_allowed=false`。
預設研究診斷頁排除 `GT_DEBUG_ONLY`；使用者需另選「GT debug（獨立）」才看歷史 debug PNG。
這些圖片可能含 GT／人工標記，僅供人類理解歷史研究，不進來源模型主展示、人物調查、
pixel producer、association 或 Agent tools。圖片標註未知時不宣稱無 GT overlay。
Gallery 不開 GT sidecar、完整 presentation JSON、source archives 或 raw media container。

允許回傳的表格欄位與 aggregate DTO 有明確白名單；額外 identity、private locator 或 raw
metadata 不返回。PNG／JSON／表格有 byte、尺寸、列數與總圖片 budget；未知 refs、路徑逸出、
symlink、非法素材及 media hash 改變均 fail closed，錯誤不帶本機路徑。
前端轉義 metadata／表格文字，research/debug detail 以同一 serial ticket 控制；切 audience、
更換 family、離開頁面或 session 變更後的成功／失敗回應均不能覆蓋當前顯示。

發布只保留允許的程式、文件與 curated receipts。192 張 PNG、MP4、RRD、GIF、source archives
和 GT debug assets 的本機存在不授權上傳、copy 或 rerender。本輪保持原素材 bytes。
原 Phase 1 formal Cases 1–3、fresh 5 Hz frozen dataset、獨立 exhaustive inventory、full evaluation
與 clean-checkout reproduction 仍是獨立研究工作；未量測為 N/A，Case4 DEFERRED。

## 已驗證與待證

原十四家族 Gallery 專項 16 tests 通過。Accuracy v2 增量後，當次專項 **30 tests PASS**，
Ruff／mypy PASS；污染、缺失、scope/mode/variant/card manifest 和 GT poison 邊界均涵蓋。
實際 assembly 在禁止 GT sidecar／debug JSON／archive bytes 讀取的 guard 下核對十五家族／
192 PNG，每張 media hash 重驗成功；歷史 GT_DEBUG_ONLY PNG 仍只屬獨立人類診斷分類。
前端 Gallery 的三個 Node tests 通過，另以 deferred harness 核對：較晚成功回應與較晚錯誤
回應均不能覆蓋新的 family／audience。這些是 adapter／UI 邊界證據，不是 benchmark 重跑。

最終無排除 `pytest --require-physical-evidence -rs` 為 **2873 passed／0 failed／0 errors／0 skipped**。
Ruff src/tests、strict mypy 183 source files、workbench 45＋product 13 Node tests 均 PASS。
63 次實際 HTTP 涵蓋三場景、兩照片模式、角色／stage／ref／scope 拒絕、影片 Range、
十二個 product actions、展示庫與來源模型；逐檔 code/config/source hashes 見整合收據。

實際瀏覽器確認原模型／人體／三候選、逐格／seek／尾段／速度／循環、四鏡頭影片，
以及雙 seed MULTI_TARGET plan 的停止／續跑／完成與 HTML 匯出。此 plan 執行十八次有限工具，
保留四十二替代、九衝突與 UNRESOLVED_PROVISIONAL 身分。Recovery 表格 27／45 列、
v2 三列比較與七 cards 實際顯示。影片同步為 soft-sync，來源仍 2.5 Hz，未據此宣稱精度提升。
原 Blender SHA／size／mtime 不變；先前失敗測試與 P14 receipt 保留，未回寫歷史 PASS。
舊盤點日期的功能缺口見 [實驗展示覆蓋表](WORKBENCH_EXPERIMENT_COVERAGE.md)，本頁是其增量接入契約。

## English scope note

The shared workbench composes the independently frozen E1 product for human research investigation
and a bounded, read-only fifteen-family gallery. It preserves source clocks, modes, IDs and
alternatives. The original 185 PNGs remain; seven certified v2 review cards bring the total to 192.
Legacy RRD/MP4/GIF entries expose existence status only. V2 comparison uses photos_only and reports
the changed end-to-end population separately.
GT debug remains a separate human diagnostic view, with no Agent or inference access. These adapter
checks and the full 2873-test integration run do not certify formal Phase 1 research. Exact code,
configuration, HTTP and browser evidence are bound by the integration receipt above.
