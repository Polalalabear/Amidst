# Amidst 共用工作台 / Shared desktop workbench

這是 `codex/simulation-engineering` 的桌面版第一版工作台。研究與管理共用入口、
場景切換及事件元件；研究角色另外提供局部 3D、場景人審、測試與評估。
目前支援兩個已凍結的合成研究場景，重用既有影像、registry 與研究結果。
手機版不在本輪範圍內。

## 統一網頁入口

依使用者 2026-10-08 指示，這套工作台是 Amidst 網頁的主要入口。
既有及後續需要網頁展示的場景、影片、事件、調查、測試、評估與 human 審查，
都接入 `frontend/workbench/` 的共用導覽、元件與流程。研究／管理決定資料與操作權限；
展示／測試／人審決定工具與排版。新增場景以 catalog／adapter 接入。

既有 `frontend/product/` 控制室是可遷移的功能與驗證來源；其後端、資料契約、
freeze 及歷史證據繼續保留。主入口使用本機 8016；8010／8012／8020 的既有頁面
與歷史驗證尚未全部遷入工作台，不能因入口決策而宣稱功能遷移已完成。

遷移的對應位置：

| 既有能力 | 工作台中的位置 |
| --- | --- |
| 人物片段、RGB 外觀查找與關聯假說 | 左側資源與右側證據／替代解釋 |
| typed investigation plans、執行／停止／續跑、保存案例 | 研究角色的調查工具區 |
| MP4、主鏡頭、速度、seek、同步診斷 | 中央展示與共用時間軸 |
| 多目標、衝突、報告、HTML 匯出與結果 review | 事件／調查資訊區與共用結果審查 |
| 模式比較、benchmark、工具紀錄 | 研究角色的測試／獨立評估面板 |

工作台後端必須將 server-owned role session 綁到已註冊 scene/run/mode/stage，
再重用現有產品服務。舊 product operator session 不能直接取得工作台研究或管理權限。
管理回傳依既有 allowlist；GT 評估仍在獨立端點，Agent 維持限定範圍。
每個遷移 milestone 以共用入口的操作驗證、版本／來源綁定與原功能回歸確認完成。
產品的輸入模式與 INPUT／RESULTS 階段和工作模式分開；場景 annotation、事件判定、
調查報告 review 也分別保存。影片與調查沿用工作台的相關鏡頭／有限時間窗，
保留多解、截斷及缺圖狀態；E0 或其他場景未提供的能力依 capability 顯示缺失。

## 啟動與重現

在現有工程 checkout 執行：

```sh
cd /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization
npm ci --prefix frontend/workbench
uv run --offline --no-sync python -m amidst.workbench --port 8016
```

開啟 [http://127.0.0.1:8016](http://127.0.0.1:8016)。`npm ci` 使用工作台自己的
`package-lock.json` 安裝固定版本的 Three.js；這一步可能下載 npm 套件，
不呼叫外部模型 API。瀏覽器資產由本機服務提供，沒有執行期 CDN 依賴。
Python 指令使用已準備好的本機環境；`--offline --no-sync` 不安裝缺少的依賴。

可另指定伺服器的場景清單與人審資料庫：

```sh
uv run --offline --no-sync python -m amidst.workbench \
  --port 8016 \
  --catalog configs/engineering/workbench_v1.json \
  --state data/engineering/local_run/workbench_v1/reviews.sqlite3
```

`--repo` 可指定資料與前端所在的 repository。預設 catalog 是
[`configs/engineering/workbench_v1.json`](../../configs/engineering/workbench_v1.json)，
預設人審資料庫是 `data/engineering/local_run/workbench_v1/reviews.sqlite3`。
審查紀錄保存在被 Git 忽略的本機 SQLite；重新開啟同一資料庫會續用紀錄。
展示演練與自動測試應使用自己的 `--state`，例如 `/private/tmp/amidst-workbench-qa.sqlite3`，
保留正式操作紀錄。資料庫來源與重新載入的 scene/run 不相符時會拒絕接續，
請核對場景清單或使用新的資料庫，不要覆寫舊紀錄。

工作台不會自動產生缺少的 scene、RGB 或推論。以下 materialization 必須已存在；
它們沒有包含在可發布的程式碼中。新環境準備資料時，依
[局部鏡頭 pilot](LOCAL_CAMERA_PILOT.md) 與
[模擬工程操作文件](SIMULATION_ENGINEERING.md) 的原有流程建立獨立輸出，
再以 catalog 指向經驗證的 checkpoint。不要把新的輸出覆寫到歷史 checkpoint。

## 目前接入的兩個場景

| 場景 | 固定資料來源 | 共用畫面可用內容 |
| --- | --- | --- |
| 局部多鏡頭研究場景 `local-camera` | `local_camera_v1/test/checkpoints/final`；model `synthetic-local-camera-v1`，run `local-camera-test-v1` | E1 pinhole；4 鏡頭、244 張 RGB、11 個場景物件、局部行為及盲區候選 |
| 雙鏡頭基礎實驗室 `synthetic-lab` | `simulation_v2`；model `synthetic-lab-v1`，run `simulation-v2` | E0 affine；2 鏡頭、102 張 RGB、6 個場景物件、人物片段及盲區候選 |

上述來源路徑皆位於 `data/engineering/local_run/`。兩者是不同模型，
不是同一模型的 development/test 分割。loader 在匯入時核對原有來源、演算法、
媒體與凍結結果綁定；查詢再使用已建立的局部索引。

共用 3D 顯示的是來源明確提供的區域多邊形、門線段、可行走面、鏡頭與研究候選。
它不是原始 Blender 的完整建築 mesh，也不表示已取得完整物理或語意權限。
座標為公尺、時間為來源的合成秒數；畫面保留 scene/run 與凍結版本的來源資訊。

E1 提供實際配置的 pinhole 鏡頭位置與內參。E0 只有地面仿射校準，
實體鏡頭姿態為 `UNKNOWN`，不會捏造位置或焦距，也不開放以不存在的 pose 編輯幾何。
兩個場景都使用既有靜態 RGB 影格序列；時間軸回放不是新產生的影片。

## 操作流程

1. 進入首頁，直接選擇「研究」或「管理」。左側導覽保持固定，右側內容可向下捲動。
   「切換身份」會回到角色入口。
2. 在主控板查看目前場景、鏡頭、局部事件與標註版本；從右上角切換場景。
   所有場景使用同一套前端，不需要重做頁面。
3. 開啟「共用工作區」，選定鏡頭與有限時間窗。事件與人物片段按局部索引取回，
   不會在每次查詢枚舉全量 records。收據顯示讀取數、索引觸及數及是否截斷。
4. 研究角色可切換「展示／人審／測試」。點選資源列或 3D 物件查看詳情；
   點選事件查看來源、候選及研究判定。展開技術資訊可看到 ID、來源與診斷。
5. 研究展示中可選擇少量鏡頭，拖曳時間軸或回放，查看相同來源時間附近的 RGB。
   實際影格時間與缺圖狀態需保留；沒有資料時不複製其他時間影像冒充當前畫面。
   3D 中的可見觀測與盲區候選分開呈現，盲區端點不當成已觀測的連續軌跡。
6. 管理角色查看事件摘要、必要影像、備註與 `OPEN／IN_PROGRESS／RESOLVED` 處理狀態。
   管理主控板下方的 3D 與多鏡頭展示區刻意保留空位。

角色由伺服器建立 session，後端限制管理角色可取得的欄位與可執行操作。
這是可信本機使用的免登入角色切換，任何本機操作者都能重新選擇研究角色；
它不提供帳號、身分驗證或多人部署的真實授權管理。
「展示／測試／人審」是工作模式，不是權限升級途徑。

## 共用人審與版本

場景人審流程是「選取對象 → 編輯草案 → 查看差異 → 驗證 → 人工核准發布」。
可編輯欄位由物件能力決定；第一版以表單及幾何 JSON 編輯，沒有完整 mesh 建模工具。
驗證包含允許的語意、有限與有效幾何、關聯區域，以及相機校準欄位的相容性。

發布時另存 `workbench.scene-overlay.v1` 標註版本。紀錄包含來源 hash、model revision、
run、修改前後值、理由、操作者、時間、驗證與前一版本 hash；資料庫採追加紀錄，
並檢查草案的基底版本，避免用舊草案覆蓋新版本。審查者名稱由本機操作者自行填寫。

人審面板可切換歷史版本預覽，並匯出選定版本的 annotation JSON 與來源收據。
切換到歷史版本不會回滾目前版本；原始 v0 baseline 也能回看。
研究結果另存「支持／否定／未知／需要更多證據」，不修改演算法原有假說、排序或結果。

**發布標註後，既有推論仍是舊設定的凍結結果。** 影響清單會把相關 run 標為
`NEEDS_RERUN`。人審模式預覽新標註；展示模式保留來源 baseline 與原凍結推論，
避免把新幾何與舊推論混成同一次計算。此版本不會自動重跑演算法，也未提供
從 overlay 一鍵執行新推論的功能；後續新 run 必須明確接入新 annotation/config。

表單驗證通過與本機發布均不是 formal 語意核准。自動測試／UI 演練中的假名審查者
及測試資料庫，只驗證流程，不能充當使用者對真實場景的人工審查證據。

## 新增場景與接口

新增相同來源格式的場景時，先準備經原 loader 驗證的 checkpoint，再在伺服器 catalog
新增一筆設定，無需修改前端：

```json
{
  "schema_version": "workbench.catalog.v1",
  "scenes": [
    {
      "scene_id": "another-local-scene",
      "adapter": "local_camera",
      "checkpoint": "data/engineering/local_run/another_scene/checkpoints/final",
      "label": "另一個研究場景",
      "description": "已驗證的局部鏡頭研究 checkpoint"
    }
  ]
}
```

`adapter` 目前支援 `local_camera` 與 `synthetic_lab`；checkpoint 是 repository 內的
相對路徑。scene ID 必須唯一，未知 adapter、絕對路徑、跳出 repository 的路徑及重複 ID
會拒絕載入。尚未存在的 checkpoint 不加入目錄；存在但驗證失敗的 checkpoint 會使
啟動失敗，不會降級成未驗證資料。catalog 是本機伺服器設定，瀏覽器不能傳入任意路徑。

catalog 的 scene ID、名稱與說明只調整展示識別，來源 model/run/hash 維持原有綁定。
新的來源格式需要新增一次 adapter，提供下列共用接口，前端即可依能力顯示：

- `summary()`、`snapshot()`：場景、來源、座標／時間、能力、鏡頭、靜態可審查物件。
- `query(camera_id, start, end)`：有限鏡頭／時間範圍的事件、觀測與檢索收據。
- `event(ref)`、`media(ref)`：同場景直接 reference 查詢，影像 bytes 保留原來源。
- `frames(camera_ids, timestamp)`：少量鏡頭的來源影格或明確缺失狀態。
- `evaluation()`：獨立研究端點使用的既有評估摘要。

共用物件包括 `REGION／PORTAL／WALKABLE／CAMERA`，帶有來源識別、語意、
幾何、屬性、允許編輯欄位及 authority。能力缺失時保留缺失狀態，
不從名稱猜測校準、物理幾何或語意。

## 測試與資料邊界

畫面中的「執行目前範圍檢查」檢查來源綁定、靜態物件、有限座標、
局部查詢是否截斷、可用時讀取一張來源影像，以及標註／推論版本狀態。
這是選定鏡頭與時間窗的資料／接口檢查，不會執行整套 pytest、重新產生推論、
重算 benchmark 或證明人物關聯精度。無樣本會顯示 `NOT_RUN`，標註已改但未重跑
則顯示 `NEEDS_RERUN`。

「查看已凍結評估」只讀既有 aggregate evaluation summary，並核對來源 run、model、
dataset、相應 config 與 freeze receipt。缺少評估顯示 `UNAVAILABLE`；
綁定失配顯示 `STALE`。E1 摘要中的 config hash 是 package config，
與整體推論 effective config 的含義不同，另以逐模式 freeze receipt 核對同一次結果。

GT／recipe sidecar 仍留在原 generator／evaluator 邊界，工作台常規場景與展示工具
不開啟它們。研究人的評估面板不擴張 Agent 的權限；原有 Agent 仍使用有限範圍、
排除 GT 的工具。管理 API 不提供評估、原始診斷、人審發布或技術 log。

工作台不接真 camera、不呼叫外部模型 API，不寫入原 Blender、既有 RGB、
registry、歷史 run 或凍結推論。Formal Cases 2/3 與 full Exit 仍為 `BLOCKED`，
Case 4 為 `DEFERRED`；frozen Phase 2 保持有效。此工作限工程分支，未合併 main。

## 已記錄驗證範圍

後端 checkpoint `7e17688af427d6d9a0ff9538a385e848036d7d40` 已普通 push，
記錄了 60 個工作台測試、103 個既有回歸測試，以及 29 次實際 HTTP 請求驗證。
這些數字只描述該後端 checkpoint。第一版桌面交付另外記錄於
[`desktop_validation.json`](../../data/engineering/workbench_20261008/desktop_validation.json)：

- 原生 Blender physical-evidence 回歸與工作台合計 **2,487 passed、0 failed、0 skipped**；
  指令 `pytest --require-physical-evidence --ignore=tests/product -rs`，排除由並行 chat
  獨立驗證及提交的 product suite。這不是全 repository 統一驗證數。
- 最後服務調整後重跑工作台 **60 passed**；前端 Node **15 passed**；
  Ruff `src tests` 與 mypy `src/amidst`（164 source files）通過。
- 實際桌面瀏覽器驗收：研究／管理入口、兩場景切換、局部查詢、3D 與來源 RGB、
  時間軸、管理備註、測試與獨立評估面板、console 無 error／warning。
- 獨立測試資料庫完成草案、差異、驗證、發布 v1、歷史 v0 唯讀預覽及 JSON 匯出；
  重啟服務後版本仍存在。展示保留來源基線 v0，並提示新標註尚未重跑。

UI 演練使用 `/private/tmp` 的獨立 SQLite，不會把演練中的人工核准混入預設操作資料庫。
實際截圖保存在被忽略的 `data/engineering/local_run/workbench_v1/`；不發布 RGB 或 SQLite。

可重跑的工作台檢查：

```sh
uv run --offline --no-sync pytest tests/workbench
uv run --offline --no-sync ruff check src/amidst/workbench tests/workbench
uv run --offline --no-sync mypy src/amidst/workbench
npm test --prefix frontend/workbench
```

## English operator notes

This desktop-only local workbench reuses two distinct frozen synthetic models:
the E1 four-camera pinhole scene and the E0 two-camera affine lab. Install the
locked frontend dependency with `npm ci --prefix frontend/workbench`, then run
`uv run --offline --no-sync python -m amidst.workbench --port 8016`.

By the user's 2026-10-08 decision, this is the primary web entry for existing and future
presentation, investigation, testing and human review. Reuse its navigation, components,
role enforcement and scene adapters. Existing product backend/contracts and historical
receipts remain reusable; older pages have not all been migrated. Product operator sessions
must be mapped through workbench-owned role and scene/run/mode/stage bindings before reuse.

Select Research or Management without a password. This is trusted local role
selection, not authenticated identity. Research exposes scene review, bounded
checks, diagnostics and a separate preexisting-evaluation panel. Management
receives a reduced server response and keeps the future multi-camera/3D area empty.

Use the server-owned catalog to add another compatible checkpoint without UI
changes. A new source format needs an adapter. Static review geometry is configured
scene data, not the original Blender mesh; E0 has no known physical camera pose.

Reviews append source-bound drafts, validations and annotation versions to an
ignored SQLite database. Publishing preserves the original sources and frozen
results, marks affected runs `NEEDS_RERUN`, and supports historical preview/export.
Automatic inference reruns are not implemented. Test reviewers are flow-test data,
not human semantic authority. UI checks are scoped data checks, not pytest,
benchmark accuracy or formal acceptance. GT sidecars remain outside runtime tools;
formal gates remain blocked and frozen Phase 2 is preserved.
