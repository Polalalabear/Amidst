# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-07。Branch：`phase1/finalization-sprint`。
**實作 worktree：`/private/tmp/amidst-phase1-finalization`**；canonical checkout
`/Users/polalabear/Developer/amidst` 在另一個 physical branch，只供應 scene/raw artifacts。
不要在 canonical checkout 實作或切換它的 branch。

使用者已要求 checkpoint／commit 後，交給新對話進行**大規模續作實作**。
精確入口、授權範圍、automatic blockers、指令與 Exit Gate 見
[post-approval implementation handoff](PHASE1_POST_APPROVAL_HANDOFF.md)；
[source/config/approval checkpoint](PHASE1_POST_APPROVAL_CHECKPOINT.json) 保存 hashes。
Approval commit：`10a3fccea609128dc3d7c31062c0bdde9f17b0cb`；handoff commit 精確 SHA
由新對話初始 prompt 提供。本 checkpoint 不是 freeze tag。

人工 gate **4/4 APPROVE、0 human blockers**；[approval summary](../human_review/APPROVALS.md)
與 [decisions.json](../human_review/decisions.json) 已提交。原問題／profiles／payload 不變，
不重問同樣決策。尚未 `--apply`、重算 certificate 或執行 formal Cases。
Phase 1 仍 **PHASE1_FINALIZATION_BLOCKED**；physical overall **PARTIAL_APPROVED**。

直接續作：apply decisions → bounded certificate → additive formal authority/marker/
metric/provider adapters → GT-free Case 1 unique／Case 2 real branches／Case 3 long-GAP
inventory → frozen formal configs → fresh dataset → Cases／A–C／supported ablations →
report/charts／Rerun → GT poison/determinism/fresh rerun → all Exit Gates → freeze。
舊 diagnostic contracts/hash-bound producers 不放寬或改寫，candidate ordering 不接觸 GT。
只有真正新 source contradiction 或必要 domain 超出明示核准，才重開最小 human gate。

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
All four original human approvals are recorded and read-only verified, but not yet applied.
Physical certification and every formal Case/benchmark/reproduction gate remain pending.
Read the focused implementation handoff and hash-bound checkpoint linked above; the new
conversation prompt supplies the exact handoff commit SHA. Reuse existing algorithms with
additive reviewed formal adapters; preserve pinned diagnostics, source and GT isolation.
Apply decisions and perform automatic readiness proofs without repeating settled human
questions. Only a new genuine geometry contradiction or indispensable out-of-scope domain
reopens human review. Preserve raw evidence. Freeze only after all original exit gates;
Case 4 stays deferred, Phase 2 frozen, and main unmerged. Dated evidence belongs to the logs.
