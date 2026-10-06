# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-06。Branch：`phase1/finalization-sprint`。
目前狀態：**PHASE1_FINALIZATION_BLOCKED**；沒有 freeze tag，不 merge main。
已驗證 source milestone：`e9ade14ffd0838712935f210f17c947563a08a29`。
完成證據見 [final report](PHASE1_FINAL_REPORT.md) 和 [experiment log](EXPERIMENT_LOG.md)；
持續規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)。

唯一續作入口是 [human_review](../human_review/README.md)：限定 domain/相關 face 的
語意或 derived correction、camera landmark/floor semantic binding、正式研究容差。
只提供 APPROVE/REJECT/FIX_GEOMETRY/KEEP_REVIEW；不要求人工計算 clearance、certificate、
route uniqueness/branch count 或 feasible inventory，這些由 agent 在語意決策後重跑。
不審 1,422 WALL patches、無關 portal conflicts 或 Stair A/B。

Approved scale 0.0247 m/BU、body/clearance、48 floor-supported subdomains、58 approved
components 保留；overall PARTIAL_APPROVED，complete local certificates=0。
正式 Coverage/MetricConfig 和 Case-specific navigation/camera authority 未定案；
formal Cases1–3/A–C/GT isolation/determinism/fresh benchmark 均 NOT_RUN。
不能由 diagnostic PASS、annotation AABB 或空 collider 集合解除 gate。

[Input lock](../data/finalization/checkpoint/input_lock.json) 固定本輪 diagnostic inputs/code；
[reproduction guide](PHASE1_REPRODUCTION.md) 重建資料、physical evidence、projection/Graph、
baseline regression、RRD 和 report。Optional additive projection 優先 exact-time multiview，
不足時 fixed-plane fallback；保留全 evidence 和 uncertainty sidecars。Office/corridor 沒有
同步雙視角 endpoints；auditorium 因原 topology contract INPUT_REJECTED。Covariance 未進入
ranking/pruning，surface-constrained inference N/A。Formal 設定須另行版本化後才執行。

Raw local/fresh data 與 demos 持久保存在 ignored
`data/pilot/phase1_finalization_20261006/`；source Blender 不變。
[Artifact inventory](PHASE1_ARTIFACT_CLEANUP.md) 沒有刪除或移動來源資產。
既有任意 endpoint snapping/connectors、visibility arbitration 與 missing-frame/origin
attestation 仍暫緩；未由本輪診斷結果升格 school topology。

Case4 **DEFERRED**；Phase2 `phase2/integration-hardening` /
`5b51d2c67917ff434f53e12a8af8af3d711d2a19` **FROZEN**，不修改、不 merge。
人工 gate 後沿既有 protocol 執行正式 Cases、baselines、poison/replay/fresh gates；
exit gate 全部通過後才允許 PHASE1_VALIDATED_AND_FROZEN 與 annotated tag。

## English

Current branch is `phase1/finalization-sprint`, status PHASE1_FINALIZATION_BLOCKED.
Source milestone `e9ade14ffd0838712935f210f17c947563a08a29` is validated. No freeze tag or
main merge. Completed evidence belongs to the final report and experiment log; durable
rules remain in DEVELOPMENT_RULES.

The single human gate concerns bounded relevant-face semantics/derived corrections,
camera-landmark/floor semantics and formal research tolerance. Subsequent clearance,
certification and route/time inventory checks belong to the agent. Existing scale, policy,
floor support and approved components remain PARTIAL_APPROVED with zero complete local
certificates. Formal Cases1–3 and A/B/C are NOT_RUN; diagnostics do not authorize them.

The input lock and reproduction guide bind the diagnostic package and code. Optional
projection uses legal exact-time multiview then fixed-plane fallback, preserving all evidence
and uncertainty. Office/corridor lack paired endpoints; auditorium has a typed topology
input rejection. Covariance ranking and approved school surface inference are unavailable.
Persistent raw data and demos are local under the ignored path above. No cleanup deletion
was performed. Endpoint attachment, visibility arbitration and origin/missing-frame
attestation remain deferred. Case4 is deferred and Phase2 remains frozen at its exact SHA.
Resume at the human gate, version formal settings before execution, and freeze only after
all original exit gates pass.
