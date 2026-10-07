# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-08。Branch：`phase1/finalization-sprint`。
**實作 worktree：`/private/tmp/amidst-phase1-finalization`**；canonical checkout
`/Users/polalabear/Developer/amidst` 在另一個 physical branch，只供應 scene/raw artifacts。
不要在 canonical checkout 實作或切換它的 branch。

目前 source checkpoint：`e6fbc8fbb3bf8c36355db38c299de5ff37705604`；最終文件／curated
publication commit 由 branch tip 取得。原 handoff `62ea9b1` 與 approval `10a3fcc` 是歷史
入口，保留原 hashes，不重新套原人工問題。完整現況見
[final report](PHASE1_FINAL_REPORT.md)、[reviewed benchmark](PHASE1_REVIEWED_BENCHMARK.md)，
重建指令見 [reviewed reproduction](PHASE1_REVIEWED_REPRODUCTION.md)。

人工 gate **4/4 APPROVE、0 human blockers**；[approval summary](../human_review/APPROVALS.md)
與 [decisions.json](../human_review/decisions.json) 已提交並 **applied**；bounded office
certificate **PASS**。原問題／profiles／payload、29 inputs、57 original frames 不變。
新增 reference movement policy 已另行明確核准／lock／fresh export／evaluation，不重問
原 HR01–HR04。Phase 1 **PHASE1_FINALIZATION_BLOCKED**；overall **PARTIAL_APPROVED**。

已完成 additive reviewed adapters、GT-free V2 config lock、canonical fresh local
`data/finalization/reviewed_run_v5/`：Case1／Case3 temporal component 的 A/B/C、27-row
K matrix（9 Case2 N/A）、20 charts、2 RRD+PNG、independent metrics/reference annotations。
Ready Case1/3 的 repeat／fresh-process／ordering／GT/recipe/annotation poison／termination
PASS。完整 source suite **1859 passed、0 skipped**，Ruff／strict mypy PASS。
Fresh checkout 位於 `/private/tmp/amidst-phase1-finalization-fresh-20261007`；物理重建、
同 hash application／dataset、198 code/config/lock files 與 final full delivery comparison
均 PASS；[最終 receipt](../data/finalization/reviewed_checkpoint_v2/fresh_delivery_comparison_final.json)
保留 41 JSON／1 CSV／4 MD／21 non-runtime PNG／2 reader-verified RRD 的核對。

**唯一 remaining prerequisite 是新合法 branching scope。** 原 complete convex office
只有 1 major route class／0 branches；Case2 及 Case3 detour/candidate-growth 不能完成。
58 approved components／116 bounded bypass candidates 中 26 有不同 camera endpoint FOV，
0 通過全部 source support/body-clearance；[scope readiness](PHASE1_BRANCH_SCOPE_GATE.md)
是 **PROPOSAL_NOT_AVAILABLE**，不是待點選 APPROVE 的可行新 scope。不要擴原 guard、
把平行偏移／timings 算 branching、修改 source 或升格未知 WALL/portal/stair。
後續只處理能真正提出 source-bound supported branching domain／camera-landmark binding
的最小新範圍；其餘原核准與已完成流程不重做。原 full Exit Gate 未通過，不建 freeze tag。
Collision ablation 缺獨立 purpose-bound consumer，保留 N/A；不填空 collider。

Immutable scene 在 canonical checkout：`blender/school_v3.blend`；scale 0.0247 m/BU。
完整 review/raw media 在 canonical ignored
`data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review/`；
全部舊版本保留。57 original frames +29 review-bound public/physical inputs 必須物化並驗 hash。
已完成展示的細節見 [review README](../human_review/README.md)，完成與歷史驗證見
[WORK_LOG](WORK_LOG.md)、[EXPERIMENT_LOG](EXPERIMENT_LOG.md)、[final report](PHASE1_FINAL_REPORT.md)；
長期規則只留在 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)。

Case 4 **DEFERRED**；Phase 2 `phase2/integration-hardening` /
`5b51d2c67917ff434f53e12a8af8af3d711d2a19` **FROZEN**，不修改、不 merge main。
Phase 1 validated/frozen 只在原正式 Exit Gate 全數通過後成立。

## English

Continue substantial implementation in `/private/tmp/amidst-phase1-finalization` on
`phase1/finalization-sprint`; do not change the canonical asset checkout's branch.
All four original approvals are applied and bounded numerical certification passes. Fresh
formal local Case1/Case3-temporal A/B/C, approved independent moving-time reference metrics,
reports/demos and scoped poison/determinism checks are complete. Read the current report,
benchmark and reproduction links above; the code checkpoint is `e6fbc8f`. Full source validation
passes 1859 tests without skips. The sole remaining source prerequisite is a genuinely supported
branching local domain with valid camera/landmark binding. The bounded candidate audit supplies
exact failed witnesses and no executable approval-only proposal. Keep Case2/Case3-growth blocked,
the original receipts/protocol/source immutable, raw versions preserved, Case4 deferred and
Phase2 frozen. No freeze tag or main merge is authorized by scoped passes.
