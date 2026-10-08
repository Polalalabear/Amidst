# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

日期：2026-10-08。實作 worktree：`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`，branch：
`phase1/finalization-sprint`；HEAD／origin 以實際 Git 為準。Canonical checkout
`/Users/polalabear/Developer/amidst` 在另一個 physical branch，只供應 immutable scene/raw
artifacts，不在那裡實作或切換 branch。

本次因舊 `/private/tmp` worktree 與 raw outputs 已不存在，從已發布
`5c2b67b9c48ae4028fd9fb2e7636f6b3af5121c0` 恢復到上述持久路徑。
使用 locked Python 3.12.12；29 個原鎖定輸入與297份 review package 檔案均驗證，
physical evidence 為 VERIFIED。完整測試 **1978 passed／0 failed／0 skipped**，
Ruff、mypy 與 source CLI strict mypy 全 PASS。執行指令見 [恢復後運行指南](PHASE1_RESTORED_RUNTIME.md)，
本次實際檢查見 [recovery receipt](../data/finalization/recovery_checkpoint_20261008/validation.json)。
新的 office 5 Hz export → V3 inference freeze → evaluation → ready-case reproduction
已實際完成；27列 baseline、45列 ablation、兩個 reader-verified RRD／PNG 在
`data/finalization/reviewed_run_recovery_20261008/`。這是既有核准 office 流程的重新運行，
新 corridor 全案例研究交付仍待下列工程。原 source/核准/config/producer bytes 保留。
歷史 V3–V8 bulk raw 與舊獨立 `/tmp` 輸出目前不存在；Git 中 curated receipts 仍在。

使用者已核准精確 corridor proposal，要求準備新對話，完成一個可重現 dataset、
一份 benchmark 結果表、一個 Rerun 3D demo，綁定同一 frozen run。直接使用
[下一對話 prompt](PHASE1_NEXT_CHAT_PROMPT.md)；完整實作起點、原因／解法與交付驗收見
[研究成果續作交接](PHASE1_RESEARCH_RELEASE_HANDOFF.md)。

原 HR01–HR04 4/4 APPROVE 且 applied；獨立 reference MOVING/departure-DWELL policy
已核准並在既有 office run 中使用。新 corridor proposal content SHA
`7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad` 已直接人工核准，
[receipt](../data/finalization/reviewed_corridor_scope_approval_v1/human_decision.json) content SHA
`702c2f7ca8165fc7669072847e26f38174b6525ed104999e35b467d23cebda09`。
六個 cells 原數值 application 全通過，完整 union certificate SHA
`f8fe588620b4f871d49f6ed50d61d6185c8648b5551d9b7528dfb7c696cb06c5`。
Historical independent clean `d8b94a6` regeneration **PASS_LOCAL_UNION_REGENERATED**；
本次恢復後再執行原完整數值重建亦通過；原 hashes 見
[current checkpoint](../data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json)。
不重問既有核准；歷史 review/strict-preview/V5 packet 保留原 bytes。

Phase1 仍 **PHASE1_FINALIZATION_BLOCKED / PARTIAL_APPROVED**。Case2／Case3 detour-growth
尚缺 scoped pipeline adapters、source-bound same-camera HOLD、相同 actual eligibility 的
canonical directed graph 與獨立 exhaustive inventory、新版本 config freeze、fresh 5 Hz
export/inference/evaluation/benchmark/demo、完整 clean-checkout reproduction。
舊 office CLI 不能直接消費新 union application。原 Graph 允許 repeated edge sequences、
CameraTransition 拒絕 self-transition；不能用 simple-cell DFS 冒充 exhaustive 或假造
CAM01 handoff。Lower-bound proof 的 recall N/A/readiness=false；V7 sample39 的真實 recovery
與兩段分開 GAP 必須保留。
原 Case2 `PORTALS_WITH_TWO_SIDED_ACCESS` 仍須查核既有 approved portal/anchor 證據；
新 corridor receipt 不新增 portal role，不能由 HOLD／分支數代替此 gate。

本次 fresh office 局部成果：Case1／Case3 temporal A/B/C、27列 baseline、45列
ablation、RRD/PNG 與 ready-case reproduction；Case2 BLOCKED rows 保留。
[Collision V4 fresh receipt](../data/finalization/reviewed_checkpoint_v4/manifest.json) 僅證明
`8cb0df3` 的既有 delivery。Source preparation `d8b94a6` 的1978 tests／zero skips、Ruff/mypy
是歷史 code validation；本次重新運行的測試、資料流程與數值重建另存 recovery receipt。

完成／歷史證據見 [WORK_LOG](WORK_LOG.md)、[final report](PHASE1_FINAL_REPORT.md)；
持續規則只留在 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)。原29 inputs／57 frames、
HR／reference policy／protocol／V1–V3 locks、source asset 全部保留。
Case4 **DEFERRED**；Phase2 `phase2/integration-hardening / 5b51d2c` **FROZEN**。
原 full Exit Gates 全過才 freeze，不 merge main。

## English

Continue in the sprint worktree above. The human approved the exact corridor proposal and
requests a new-chat continuation to finish one reproducible dataset, benchmark table and
Rerun 3D demo tied to one frozen run. Use the linked prompt and release handoff.
Original HR01–HR04 and the independent reference movement policy are approved and applied;
the new exact scope has a direct-human receipt and six passing numerical cell certificates.
Independent clean-checkout regeneration passes; read the current checkpoint for precise hashes. Do not repeat
approval questions or rewrite historical review/preview packets.
Case2 and Case3 detour-growth remain blocked pending additive scoped pipeline adapters,
source-bound same-camera HOLD, unchanged-eligibility independent exhaustive inventory,
new config freeze, fresh 5 Hz execution and complete delivery reproduction. The old office
CLI cannot consume the new union directly. Preserve repeated-edge graph semantics and the
actual sample39 recovery; lower-bound proofs do not establish recall/readiness.
Audit the original Case2 two-sided-portal requirement against existing approved evidence;
the new corridor receipt grants no portal role.
The persistent recovery rebuild actually reruns the existing office dataset/inference/evaluation,
reader-verified demos, ready-case reproduction and corridor numerical verification. Read the
recovery receipt and runtime guide for current results; old temporary bulk outputs are absent.
This does not complete the new corridor release. Case4 stays deferred, Phase2
frozen, and a Phase1 freeze requires every original full Exit Gate.
