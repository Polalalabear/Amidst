# Phase 1 experiment log / Phase 1 研究實驗紀錄

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

此索引記錄 source geometry／physical-policy 驗證，與正式 Cases 1–3 research benchmark
分開。執行 gates 與 Git checkpoint 的完整紀錄見 [WORK_LOG](WORK_LOG.md)；
長期契約見 [GEOMETRY_PROVIDER](GEOMETRY_PROVIDER.md)，決策見
[ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md)。不回寫歷史 artifact 或 provenance。

| Experiment | 證據／範圍 |
| --- | --- |
| 2026-10-06 approved architectural scale checkpoint | [Scale review](SCHOOL_V3_SCALE_REVIEW.md)；user-defined 0.0247 m/BU，mesh 量測僅 sanity check |
| PHASE1_PHYSICAL_POLICY_APPROVAL_20261006 | [Manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/manifest.json)；approved policy、source-bound support／components、受限 physical scopes |

### PHASE1_PHYSICAL_POLICY_APPROVAL_20261006

**GEOMETRY SOURCE VALIDATION／研究模型驗證；不是正式 Case 1–3 結果。**
Branch：`phase1/physical-policy-approval`；起點是已驗證 checkpoint
`0bab8ac262b93f3c8babad69432744e7e4d1c541`。目的為解除可由 source evidence 證明的
physical blocker，明確保留尚未完整支撐的幾何範圍。

Input 是未修改的 `blender/school_v3.blend`，source SHA-256：
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`。
使用 [review config](../configs/physical_policy_validation_school_v3.json)、
[physical policy](../configs/physical_authority_policy_school_v3.json)、
[runtime contract](../configs/physical_policy_runtime_school_v3.json) 與
[collision numerics](../configs/physical_collision_numerics_v1.json)。Architectural scale
APPROVED **1 BU = 0.0247 m**；source vertices 保留 BU，policy 使用 SI。
Exact evaluated source faces／closed components 與 hidden geometry 綁定同一 source；
不依未分類 object 名稱賦予語意。

已核准 upright-cylinder 人體為 radius 0.30 m／height 1.70 m，body clearance 0.05 m；
portal 每側 0.05 m／垂直 0.10 m，contact tolerance 0.001 m。
Minimum equality PASS；portal／body margin 取 `max`，不重複加總。
允許合法 APPROVED support contact，WALKABLE／STAIR 外禁止 navigation。
BIDIRECTIONAL stair policy 不取代 actual connectivity／opening／full-body evidence。
自動 BU 換算與設定原始值見
[body-clearance report](../data/scene_audit/phase1_physical_policy_approval_20261006/body_clearance_policy.json)。

| Observation | Result／限制 |
| --- | --- |
| Actual floor support | 48 supported 子域：45 whole annotation coverage／3 partial；38 舊 plane-offset 警訊以 source support 解決，未移動／flatten source |
| Obstacle collider authority | 5/19 obstacles 中 58 closed components APPROVED；19 whole-object scope 全部 HUMAN_REVIEW |
| WALL | 73 HIGH_CONFIDENCE／1,422 HUMAN_REVIEW／77 REJECTED；固定 thresholds 與 doorway protection 保留 |
| Obstacle／portal conflicts | 8 組 REVIEW；未任意縮 obstacle 或移 portal |
| Stair A/B | 0 usable intermediate landing；source slab 點 headroom 約 0.194 m，support chain／opening／雙向 body clearance 尚未證明 |
| Local physical islands | **0 complete physical islands; 5 searched regions remain REVIEW (unclassified group_0 enclosure / degenerate source geometry)** |

資料入口： [floor map](../data/scene_audit/phase1_physical_policy_approval_20261006/floor_authority_map.json)、
[obstacle components](../data/scene_audit/phase1_physical_policy_approval_20261006/obstacle_collider_authority.json)、
[portal review](../data/scene_audit/phase1_physical_policy_approval_20261006/portal_clearance.json)、
[stair review](../data/scene_audit/phase1_physical_policy_approval_20261006/stair_authority.json)、
[local scopes](../data/scene_audit/phase1_physical_policy_approval_20261006/local_physical_scopes.json)。
原 full local evidence commit
`c5956dc825f669e28e2694578be0fed97432a786` 保存完整 gzip JSON evidence。
Lightweight checkpoint 直接以 `0bab8ac262b93f3c8babad69432744e7e4d1c541` 為基底，
不把該 full-evidence commit 作祖先；只保留 summaries／hashes 與原 review manifest。
大型 geometry／source／component blobs 依
[materialization contract](PHYSICAL_EVIDENCE_MATERIALIZATION.md) 在 ignored paths 重建，
由 canonical artifact manifest 驗證 byte／content hashes。原 manifest 的 input、code、
source integrity、runtime 與 git commit provenance 不回寫。

Additive cylinder consumer 只取得 purpose gate 核准的 exact colliders，對整段 sweep
檢查 source triangles／closed interior；距離不確定或超出 budget 明列 UNVALIDATED。
Known collision／clearance violation 在 final K 截斷前排除；candidate IDs、相對順序、
ranking、GT isolation 與既有 core／MetricConfig schemas 保留。
Retained 只代表核准 collider scope 未發現 violation，不是 global collision-free PASS。
Local certificate 須完整篩查限定 footpoint 域並拒絕域外 validation。
Global `physical_complete=false` gate 仍拒絕全域 physical validation；formal metrics／
Cases 1–3／Case 4／Agent 均未由本輪開放。

Fresh clone 先明確 materialize；該單一命令已完整重跑 physical-policy validation，
歷史 summaries／manifest 不覆寫：

```sh
uv run python -m amidst.materialize_physical_evidence \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --source-scene /absolute/path/to/checkout/blender/school_v3.blend
```

若另需獨立 report，使用 materialization contract 中不同 `/tmp` output 的 replay 命令。
Lightweight／strict external-evidence test profiles 與 timestamp 正規化邊界見同一契約。

Comparison 應使用 report semantics、canonical hashes 與 bound config；runtime 另行記錄，
不要求每次 run 的所有 binary／manifest bytes 相同。剩餘人工問題為 whole-object volume
證據、8 組 portal opening／衝突與 A/B actual stair support／opening／clearance，
不是再次選擇已核准 physical-policy 數值。最終 pytest／Ruff／mypy／diff gates 記於
[WORK_LOG](WORK_LOG.md)。

## English

This index records geometry-source and physical-policy experiments separately from formal
Case 1–3 research benchmarks. [WORK_LOG](WORK_LOG.md) retains execution gates and Git
checkpoints; [GEOMETRY_PROVIDER](GEOMETRY_PROVIDER.md) defines durable contracts and
[ISSUES_AND_DECISIONS](ISSUES_AND_DECISIONS.md) records semantic decisions. Historical
artifacts and provenance are not rewritten.

| Experiment | Evidence / scope |
| --- | --- |
| 2026-10-06 approved architectural-scale checkpoint | [Scale review](SCHOOL_V3_SCALE_REVIEW.md); user-defined 0.0247 m/BU, mesh measurements used only for sanity checks |
| PHASE1_PHYSICAL_POLICY_APPROVAL_20261006 | [Manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/manifest.json); approved policy, source-bound support/components and restricted physical scopes |

### PHASE1_PHYSICAL_POLICY_APPROVAL_20261006

**GEOMETRY SOURCE VALIDATION; not formal Case 1–3 results.** The experiment runs on
`phase1/physical-policy-approval` from validated checkpoint
`0bab8ac262b93f3c8babad69432744e7e4d1c541`, resolving only blockers supported by source evidence.
The unchanged `blender/school_v3.blend` SHA-256 is
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`.
The linked review config, physical policy, runtime contract and numerical solver config
bind exact evaluated faces, components and hidden geometry to that source. Names do not
confer semantic roles. APPROVED scale is **1 BU = 0.0247 m**; source geometry remains BU
and physical policy is SI.

The approved cylinder has radius 0.30 m, height 1.70 m and extra body clearance 0.05 m;
portal margins are 0.05 m per side and 0.10 m vertically, with 0.001 m obstacle-contact
tolerance. Minimum equality passes and margins combine by maximum. Legal APPROVED support
contact is permitted; navigation outside approved WALKABLE/STAIR is forbidden.
BIDIRECTIONAL stair intent still requires actual traversal evidence. The linked
body-clearance report retains original SI settings and automatic BU conversions.

The review finds 48 supported walkable subdomains (45 whole/3 partial), resolving 38 old
annotation-plane offsets through source support rather than moving or flattening geometry.
Fifty-eight closed components in 5 of 19 obstacles are approved; every whole-obstacle
scope remains HUMAN_REVIEW. WALL classification stays 73 HIGH_CONFIDENCE, 1,422 HUMAN_REVIEW
and 77 REJECTED with unchanged thresholds/doorway protection. Eight obstacle/portal conflicts
remain REVIEW. Both stairs have zero usable intermediate landings in the selected source:
a slab gives about 0.194 m point headroom, and support, opening and bidirectional body
clearance remain unproven. Local physical islands: **0 complete physical islands; 5 searched regions remain REVIEW (unclassified group_0 enclosure / degenerate source geometry)**.

The floor, obstacle, portal, stair and local-scope JSON reports above provide review
witnesses. Full gzip evidence was produced and retained at local commit
`c5956dc825f669e28e2694578be0fed97432a786`. The lightweight branch starts directly from
`0bab8ac262b93f3c8babad69432744e7e4d1c541`, retaining that full-evidence commit as a
reference rather than an ancestor. Its generated geometry/source/component blobs are excluded
from Git and recreated through the
[materialization contract](PHYSICAL_EVIDENCE_MATERIALIZATION.md). The added canonical artifact
manifest verifies exact raw bytes and canonical content hashes; original review-manifest
provenance stays intact. The command above performs complete policy replay without overwriting
historical summaries/manifest. Use a separate `/tmp` report output for additional replay.
The contract documents lightweight/strict evidence profiles, source timestamp normalization
and the explicitly excluded collision runtime field.

The additive full-segment cylinder consumer uses approved purpose-gated exact colliders,
reports uncertain distances/budget failures as UNVALIDATED, and removes known violations
before final K truncation. IDs, relative order, ranking, GT isolation and existing core/
MetricConfig schemas are preserved. Retention proves no detected violation within that
collider scope, not global free space. Local certification requires complete source screening
within a restricted footpoint domain and refuses outside-domain validation.
Global `physical_complete=false` still blocks global physical validation. Formal metrics,
Cases 1–3, Case 4 and Agent work are not opened by this experiment.

Remaining human review concerns whole-object volume evidence, the eight portal openings/
conflicts, and A/B actual support/opening/body-clearance evidence, rather than selecting
the already-approved policy values again. Final pytest/Ruff/mypy/diff gates are recorded
in [WORK_LOG](WORK_LOG.md).
