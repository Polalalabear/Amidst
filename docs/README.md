# 文件導覽 / Documentation

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

先讀 [目前交接](operations/CODEX_HANDOFF.md)；開始實作時使用 [續作 prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md)，並遵守 [開發規則](specs/DEVELOPMENT_RULES.md)。可執行的本機 mock API／replay／consumer 見 [Phase 2 整合](engineering/PHASE2_INTEGRATION.md)；M1–M6 照片到3D事件的操作與重現見 [模擬工程](engineering/SIMULATION_ENGINEERING.md)；Agent 的定位、可用工具與資料邊界見 [工程契約](engineering/AGENT_RETRIEVAL_BOUNDARY.md)。

| 資料夾 | 內容 |
| --- | --- |
| [specs/](specs/) | 需求、架構、資料契約、決策與持續規則 |
| [engineering/](engineering/) | 模擬工程、Agent 工具與資料邊界 |
| [research/](research/) | Benchmark protocol、研究結果、展示與重現 |
| [operations/](operations/) | 目前交接、續作 prompt、runtime 與資產物化 |
| [history/](history/) | 工作、實驗與歷史 checkpoint 紀錄 |

此頁是唯一文件索引。根目錄另保留 exact corridor review 與 runtime 使用的 checkpoint JSON；三個符號連結維持 locked protocol、核准 review 與歷史 geometry reports 的原路徑。正文位於分類資料夾，不另建逐檔轉址文件。

## English

Read the [current handoff](operations/CODEX_HANDOFF.md), use the [continuation prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md) for implementation, and follow the [development rules](specs/DEVELOPMENT_RULES.md). [Phase 2 integration](engineering/PHASE2_INTEGRATION.md) documents the executable local mock API, replay and consumer; [Simulation engineering](engineering/SIMULATION_ENGINEERING.md) documents the operating RGB-to-3D loop; the [Agent contract](engineering/AGENT_RETRIEVAL_BOUNDARY.md) defines roles, tools and data boundaries.

The five folders separate specifications, engineering, research, operations and history. This is the only documentation index. The root retains the exact corridor review, the runtime checkpoint JSON and three symlinks required by locked protocol, review and geometry-report references; maintained text lives in the category folders.
