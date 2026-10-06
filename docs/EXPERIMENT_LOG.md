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


## 2026-10-06 — PHASE1_FINALIZATION_SPRINT

**PHASE1_FINALIZATION_BLOCKED / DIAGNOSTIC; formal Cases1–3 NOT_RUN.**
Branch `phase1/finalization-sprint`; source milestone
`e9ade14ffd0838712935f210f17c947563a08a29`. Physical parent
`f264db1579882e54cecba22db24ec8798822fd0c`; selective projection source
`8f4055ffcdc3bf6efd723c7956ac685e1fe033f1`. No experimental-history merge.

Dataset `phase1-finalization-inputs-v1-diagnostic`, manifest SHA256
`2c524e0074d06091aa330e2e0ca3ebf9639761ed96749fde07b0e9ab2fcac417`.
Source unchanged `cd46fa03...e84e`, approved 0.0247m/BU. Fresh original-scene export
of three existing streams yields 300 two-camera records, 150 timestamps.
Office/corridor paired evidence=0; auditorium exact-time pairs=33/49 visible timestamps.
Additive policy and strict optional Graph projector preserve full evidence; no GT camera/pair
selection, sample rejection or Coverage epsilon changes. Covariance stays sidecar.

Two independent physical materializations are research-equivalent:48 supported domains,
58 approved components, diagnostic pruning4→2, PARTIAL_APPROVED, local certificates=0.
Baseline adapters share one traversal; 21 fixture comparisons execute and three collision
ablation reference rows remain N/A. Existing default C artifacts remain compatible.

Repeated, ordering, fresh-process and poisoned GT leave inference/candidate ordering/
termination unchanged; only evaluation changes. All inference freezes before GT/recipe
integrity reads. Clean checkout reproduces15 dataset and217 canonical replay artifacts;
19 report artifacts byte-match. Six RRD reader checks pass, three PNG previews inspected.
Runtime/RRD containers are noncanonical; no inference results excluded.

完整 pytest physical-evidence profile：1532 passed /5 historical school-v2 skips；
Ruff、mypy92 files、diff check通過。Final report/table contains27 explicit N/A formal
case/method/K rows, availability charts and diagnostic method/confidence charts.
Formal physical/local-navigation, camera-landmark/floor semantics and research tolerance
remain one [human gate](../human_review/README.md); post-decision route/clearance/certificate
checks are agent-owned. No WALL/portal/stair authority promotion. Case4 deferred, Phase2 frozen.
Raw local/fresh artifacts retained in ignored `data/pilot/phase1_finalization_20261006/`;
cleanup inventory deletes nothing. No freeze tag while blocked.

中文版與 English 的完整結果、limits 和 command evidence：
[Final report](PHASE1_FINAL_REPORT.md), [reproduction](PHASE1_REPRODUCTION.md),
[reproducibility](../data/finalization/checkpoint/reproducibility.json),
[result table](../data/finalization/checkpoint/benchmark_table.md).

## 2026-10-06 — Minimal Phase 1 Human Review Gate

Blocked checkpoint `85f5e6b055e75d286c1519e6c5ba2f2efc416347` 的 gate 已重整為
**4 個 pending decisions**：[dashboard](../human_review/index.html)、
[decisions](../human_review/decisions.json)、[review text](../human_review/README.md)。
HR-01 合併 1F office bounded source surface/solid ownership 與 exact-zero-area
`group_0` faces1975/2398；HR-02 camera/marker/floor binding；HR-03 Coverage epsilon；
HR-04 speed/timing。Scale、body/clearance/contact、K1/2/3、5 Hz 和現有 alignment /
interpolation 直接採用。Case3 exact duration 在 protocol 未唯一指定，stress instance 是
pre-dataset agent work，不新增第五個人工 duration 決策。

只使用 public observations/projection/candidates 和 approved source authority；50 frames /
5 Hz / 10 s 的 Blender preview、source-camera stills、top/side views 與 exact scope
closeups 已產生。原 source SHA/mtime 保持不變；floor seam 的 display lift 只供定位。
Face7356 東側牆在 body guard 外，只是 context。Left candidate clearance0.18956 m
低於已核准0.35 m，程式自動拒絕，沒有交給人類調 threshold。Office obstacle 語意已核准但
solid components=0，不假造 collider 或 local certificate PASS。

新增 hash-bound scoped semantic receipt、reviewed certificate/provider 和
[application pipeline](../human_review/DECISION_APPLICATION.md)，原 atlas、10 個 pinned
physical producers 與歷史 manifests 不變。Pipeline 拒絕未決/非核准、改動 immutable
questions/profiles/hash/bounds；APPROVE 後仍完整重算原 source proof。只有 synthetic
測試 receipt 被套用；本輪 school approvals=0，formal Cases/A–C=NOT_RUN，沒有 main merge
或 freeze tag。Current parallel direct/right routes 尚未證明 Case2 branching；formal
adapters、Case1 uniqueness、Case2 inventory、Case3 stress feasibility 留待決策後自動工作。

本次完整驗證：`AMIDST_PHYSICAL_SOURCE_SCENE=<unchanged school_v3.blend> uv run pytest
--require-physical-evidence -rs` **1580 passed /5 historical school-v2 prerequisite skips**；
Ruff passed；mypy **93 source files** passed；diff check passed。Pending application 的
source/public-input/57 PNG hashes 驗證通過。Dashboard 預設未選決策、closeup 圖片、
連續 player 與最後 frame49 已實際開啟檢查；前端 import tamper guards 通過。
最後再加 canonical JSON 型別/hash guard（避免 bool/int 相等比較繞過）；
受影響的 review/synthetic certificate tests **49 passed**，strict typing 額外8個 review
scripts 通過，原 Phase1 inference source 無改動。

Raw review renders 保留 local ignored；package hashes、reproduction scripts、texts 和
pending decision template 保留。舊 generic gate 另存 human_review/history/blocked_checkpoint，
沒有刪除任何 source 或 DELETE_CANDIDATE。

## 2026-10-07 — Human Review spatial context supplement

**DIAGNOSTIC / HUMAN_REVIEW_PENDING**；沿用 `ef0f88ad373373c3a8222d510772440103839f2a`。
HR-01/02 新增 [school→office 五步導覽](../human_review/frames/spatial_context/guide.html)：
全校 /1F /camera 位置、5 秒 camera-only approach、原 10 秒移動、source face /landmark
近看。3 張 still +25 camera frames 共29,517,434 bytes，source XY 圖使用原 manifest
座標；camera 圖示不證明 FOV，剖視只供顯示。人物原首末位移3.872988342 m；1.359734953 m
只表示 landmark→floor offset，沒有增加較長的人物軌跡或改 certified scope。

新 evidence 用獨立 spatial manifest 保留來源與 producer hash。成功初版 renderer 已 exact
封存（`8a5d52f4...305cd92`）；改進版構圖因磁碟不足未完成 render，沒有冒稱已產生圖片。
來源 Blender/hash、29 frozen inputs、57 原 PNG、四項問題/e105 payload 逐項保持不變。
既有 browser decision draft 未重新載入；disk 全部 pending，application readonly 驗證通過。
未讀 GT/recipe/evaluation，未套用人工核准、執行 formal Cases、push/merge/tag。

本輪56 tests通過、Ruff全 repo、mypy93 core +4 review tools、diff check通過。
原1580-test全套屬2026-10-06 evidence，本輪未重跑。只清除本輪 generated validation caches
以完成小檔保存；來源、raw evidence、既有 renders 與 DELETE_CANDIDATE 全保留。

完整 local package 保存於 canonical checkout 的 ignored
`data/pilot/phase1_finalization_human_review_20261007/human_review/`；採 APFS copy-on-write
獨立檔案副本，123 個 manifest artifacts 全部 hash 核對一致。Package manifest SHA256：
`a42feef8adc07ab6e4b718907bd716a74dfe855c0658dec4a8c2b99a9026e8a7`。

## 2026-10-07 — Additive source-model body motion preview

**DIAGNOSTIC / HUMAN_REVIEW_PENDING**；base `5ea82587fa205d8ce4d7bec7288ca7bf0b8055a5`。
保留舊 guide/player/85PNG，新增 [10 秒模型人物動作](../human_review/frames/motion_context/player.html)。
Fixed review camera、actual audited source110 triangles、50frames /5Hz；body/clearance、
public projections、floor/body guard、OBSERVED→GAP→OBSERVED 連續可見。人體位移約3.873m，
舊 positions/time/camera/method/confidence/uncertainty 逐值完全沿用；joint swing 是DISPLAY_ONLY
示意，GAP仍是existing inferred candidate，不是假造真實隱藏動作或formal physical PASS。

Renderer SHA256 `94664643b90772011e182b38e8ce403bdbd654d1b5a06493d24ad92af82b140f`。
Source `.blend` hash/size/mtime、29frozen inputs、原85PNG/11guide-decision檔均保留。
First/mid/final PNG視覺QA通過，browser實際播放到50/50與GAP逐格檢查通過。Pillow12.3
derivedGIF實際50格、200ms/frame、10s/loop，SHA256
`c066c0a55e248bdd0e74f1ca6b3ef2be8e47af9b4764cdd1994da337b421056b`；full-resolution PNG
保留，GIF palette/resize明標preview。原ImageMagick嘗試cache不足且未留下輸出。

61相關tests通過；repo Ruff、review工具 strict mypy、diff gate通過。只清除可重建task bytecode
與untracked fresh-validation mypy cache來完成保存，不刪任何source/evidence/render/decision。
No GT/recipe/evaluation reads、school approvals、formal Cases、push、merge 或freeze tag。

獨立 local APFS copy-on-write 副本：canonical checkout 的
`data/pilot/phase1_finalization_human_review_20261007/body_motion/human_review/`。
181個manifest artifacts全部hash一致，上一版package未覆寫。新package manifest SHA256：
`db61758c2daf9701fa40a77936941274b60ffa6f03f6d083e3c742c493852214`。
