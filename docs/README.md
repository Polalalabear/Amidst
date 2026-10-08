# 文件導覽 / Documentation index

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

先看 [目前交接](operations/CODEX_HANDOFF.md) 與 [下一個工作 prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md)，再依問題讀取下列分類。文件內容、實作狀態與日期化證據分開保存。

| 資料夾 | 用途 | 主要入口 |
| --- | --- | --- |
| [specs](specs/README.md) | 需求、架構、資料契約、持續規則與幾何介面 | [PRD](specs/PRD.md)、[SYSTEM_DESIGN](specs/SYSTEM_DESIGN.md)、[INTERFACES](specs/INTERFACES.md) |
| [engineering](engineering/README.md) | 全模擬工程範圍、Agent 角色、工具與資料邊界 | [Agent 檢索定位](engineering/AGENT_RETRIEVAL_BOUNDARY.md) |
| [research](research/README.md) | Benchmark、研究結果、展示與重現方法 | [研究報告](research/PHASE1_FINAL_REPORT.md)、[reviewed reproduction](research/PHASE1_REVIEWED_REPRODUCTION.md) |
| [operations](operations/README.md) | 有效交接、續作 prompt、runtime 與證據物化 | [續作 prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md)、[runtime](operations/PHASE1_RESTORED_RUNTIME.md) |
| [history](history/README.md) | 已完成工作、實驗與 checkpoint 歷史 | [WORK_LOG](history/WORK_LOG.md)、[EXPERIMENT_LOG](history/EXPERIMENT_LOG.md) |

根目錄的同名入口保留舊連結與 producer 路徑，正文以分類資料夾為準。以下檔案保留原位置與原 bytes，不改寫歷史 hash 或 runtime 入口：

- [PHASE1_BENCHMARK_PROTOCOL.md](PHASE1_BENCHMARK_PROTOCOL.md)：locked protocol。
- [PHASE1_POST_APPROVAL_HANDOFF.md](PHASE1_POST_APPROVAL_HANDOFF.md)：checkpoint 鎖定的歷史交接。
- [PHASE1_CORRIDOR_SCOPE_REVIEW.md](PHASE1_CORRIDOR_SCOPE_REVIEW.md)：人工核准引用的 exact review。
- [PHASE1_POST_APPROVAL_CHECKPOINT.json](PHASE1_POST_APPROVAL_CHECKPOINT.json)：hydration 使用的歷史 checkpoint。
- [PHASE1_ARTIFACT_CLEANUP.md](PHASE1_ARTIFACT_CLEANUP.md)：既有 artifact inventory producer 的輸出位置。

原 protocol 的歷史執行狀態不代替最新交接。本階段只有本機 synthetic/mock 工程；OpenAI API 接線與 token 兜底演算法章節保持空白。

## English

Start with the [current handoff](operations/CODEX_HANDOFF.md) and [continuation prompt](operations/PHASE1_NEXT_CHAT_PROMPT.md), then read the relevant category. Specifications, implementation status and dated evidence have separate owners.

- [specs](specs/README.md): requirements, architecture, contracts, durable rules and geometry interfaces.
- [engineering](engineering/README.md): simulation engineering, Agent roles, tools and data boundaries.
- [research](research/README.md): benchmarks, results, demonstrations and reproduction.
- [operations](operations/README.md): active handoffs, prompts, runtime and evidence materialization.
- [history](history/README.md): completed work, experiments and historical checkpoints.

Root compatibility entries preserve existing links and producer paths. The five original files listed above retain their original paths and bytes because they are pinned, runtime-consumed or producer-generated. Their historical execution status is not the current project status.

Current engineering is local synthetic/mock work. OpenAI API wiring and the token fallback algorithm remain empty sections.
