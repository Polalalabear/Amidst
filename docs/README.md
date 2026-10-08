# 文件導覽 / Documentation

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

先讀 [目前交接](operations/CODEX_HANDOFF.md)；開始實作時使用 [續作 prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md)，並遵守 [開發規則](specs/DEVELOPMENT_RULES.md)。可執行的本機 mock API／replay／consumer 見 [Phase 2 整合](engineering/PHASE2_INTEGRATION.md)；M1–M6 照片到3D事件的操作與重現見 [模擬工程](engineering/SIMULATION_ENGINEERING.md)；局部跨鏡頭索引、事件卡與當次消融見 [局部 pilot](engineering/LOCAL_CAMERA_PILOT.md) 與 [protocol](research/LOCAL_CAMERA_EVENT_PROTOCOL.md)；Agent 的定位、可用工具與資料邊界見 [工程契約](engineering/AGENT_RETRIEVAL_BOUNDARY.md)。

持久調查、RGB 外觀查找、四鏡頭影片與 Three.js 回放、案例／人審／報告匯出的操作入口，見
[本機 Phase 2 產品](engineering/LOCAL_PHASE2_PRODUCT.md)；當次結果與正式待辦分開記錄。
並行的雙角色／場景 catalog／人審版本入口見 [共用工作台](engineering/SHARED_WORKBENCH.md)，
它的本機8016及驗證 receipt 與產品8020分開。

使用者最新決策：**8016／frontend/workbench 為統一網頁主入口**。既有與後續頁面能力
接入共用工作台；8020／frontend/product 保留既有工程證據及待遷移功能來源，不再擴張成
另一個主要前端。Product 後端／資料／typed interfaces 可供接入，尚未宣稱遷移完成。

[實驗展示覆蓋表](engineering/WORKBENCH_EXPERIMENT_COVERAGE.md) 記錄本輪實際網站盤點：
主平台只有 E1／E0；已有但未接入、缺少素材、formal BLOCKED 及待修項目分開列出。

| 資料夾 | 內容 |
| --- | --- |
| [specs/](specs/) | 需求、架構、資料契約、決策與持續規則 |
| [engineering/](engineering/) | 模擬工程、Agent 工具與資料邊界 |
| [research/](research/) | Benchmark protocol、研究結果、展示與重現 |
| [operations/](operations/) | 目前交接、續作 prompt、runtime 與資產物化 |
| [history/](history/) | 工作、實驗與歷史 checkpoint 紀錄 |

此頁是唯一文件索引。根目錄另保留 exact corridor review 與 runtime 使用的 checkpoint JSON；三個符號連結維持 locked protocol、核准 review 與歷史 geometry reports 的原路徑。正文位於分類資料夾，不另建逐檔轉址文件。

## English

Read the [current handoff](operations/CODEX_HANDOFF.md), use the [continuation prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md) for implementation, and follow the [development rules](specs/DEVELOPMENT_RULES.md). [Phase 2 integration](engineering/PHASE2_INTEGRATION.md) documents the executable local mock API, replay and consumer; [Simulation engineering](engineering/SIMULATION_ENGINEERING.md) documents the operating RGB-to-3D loop; [Local camera pilot](engineering/LOCAL_CAMERA_PILOT.md) documents indexed association/event cards and evaluation; the [Agent contract](engineering/AGENT_RETRIEVAL_BOUNDARY.md) defines roles, tools and data boundaries.

[Local Phase 2 product](engineering/LOCAL_PHASE2_PRODUCT.md) documents durable investigations,
RGB appearance retrieval, four-camera video/Three.js playback, saved cases, reviews and reports.
[Shared workbench](engineering/SHARED_WORKBENCH.md) documents the independently validated
local research/admin scene and review workspace.
The user's latest decision makes workbench/8016 the unified primary web UI. Existing and
future presentation capabilities belong there; product/8020 remains a preserved engineering
lab and migration source. Backend interfaces are available; migration is not yet complete.
[Experiment coverage](engineering/WORKBENCH_EXPERIMENT_COVERAGE.md) records the actual
two-scene UI, unmigrated presentations, local asset availability and actionable audit findings.

The five folders separate specifications, engineering, research, operations and history. This is the only documentation index. The root retains the exact corridor review, the runtime checkpoint JSON and three symlinks required by locked protocol, review and geometry-report references; maintained text lives in the category folders.
