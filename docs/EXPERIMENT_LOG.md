# Phase 1 experiment log / Phase 1 研究實驗紀錄

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

2026-10-07 post-approval milestone：四項決策已套用到新的
`data/finalization/human_review_applied_v1/`；原 numerical proof 重算後 bounded certificate
**PASS**，只有 `BODY:WALK_1F_OFFICE` 原 guard，whole component/building 不升格。
正式 Case inventory/adapters 仍待驗證；`formal_execution_enabled=false` 保留。
53 focused tests/Ruff/strict mypy 是本輪結果，與 approval checkpoint 177 tests 分開。

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

## 2026-10-07 — Node/edge model locator

**DIAGNOSTIC / HUMAN_REVIEW_PENDING**；base `346124510727e06ed68745197b1eeb32358617f7`。
新增 [模型與拓樸對照](../human_review/frames/topology_context/view.html)：既有
`projected_departure`／`projected_recovery` 對應 N1／N2，`pilot_route:direct/left/right`
對應 E1–E3。全部三條 N1→N2 edges 保留；4 個 corners 是 polyline vertices，不是假節點。
模型疊圖由既有 review camera 正交投影；可切 raw landmark 高度或既有 HR-02 待審 floor
換算。E2 的獨立 support rejection 不是 Graph pruning，三條 configured hypotheses
不構成 formal school branching proof。原 135PNG、GIF、13 protected core files、29 inputs
與四項 pending questions 保留。66相關 tests、Ruff、review-tools strict mypy、diff check 通過。
模型 player 全50格、raw/floor mode 與並排圖視覺 QA 通過。無 GT、source modification、
human approval、formal Case 執行、push/merge/tag。
完整新副本保存於 canonical checkout 的 ignored
`data/pilot/phase1_finalization_human_review_20261007/topology/human_review/`；舊副本保留。
189個artifact hashes全部核對一致；package manifest SHA256：
`55f3a8e9bd035f0fbb70665bb2e313e472b41423a2099a032a4a588f0f05b551`。
靜態 PNG 511,640 bytes，SHA256
`e092393cfbad9206998c824f70d2f52bb13152a99f28f9bea459f20405f4cea1`；未採用的本輪 QA
版本另存 private temporary archive，沒有刪除既有 artifacts。

## 2026-10-07 — Integrate displays into the original human gate

Base `753ec2889320f82b6e2bdaca987765bfc154062b`；status仍 **HUMAN_REVIEW_PENDING**。
原 [dashboard](../human_review/index.html#visual-review-workspace) 新增共同 visual tabs：
定位→行走→模型／拓樸→HR01/02問題近看；兩項 dialog內同樣inline查看，原images與sequence
保留。播放器切換與modal close/cancel停止舊實例，避免同時播放。全部display-only metadata
與原payload、profiles、decision handlers及draft key分離。GT/evaluation/recipe未讀。
新增3個Node VM behavior tests覆蓋實際guards、activeiframe lifecycle及legacy evidence；
合併69tests通過，Ruff/mypy93corefiles及3tools/diffcheck通過。Native browser播放與兩項
dialog、inline拓樸及close後零iframe通過。136PNG/GIF、29inputs和四項pending decisions
原hash保留；source模型、推論、protocol、physical authority沒有變動。
本機完整副本：`data/pilot/phase1_finalization_human_review_20261007/dashboard/human_review/`。
前次三份副本保留；未執行formal Cases、push、merge或freeze tag。

整合版191個artifact hashes全部一致；package manifest SHA256：
`fa31c7577665a9f7f799f0f10a55f9e55a2f57ccaf9a45bf3ea8b909dd320ee4`。原review副本及使用者決策未覆寫。

## 2026-10-07 — Review framing, native camera location and HR02 body-height clarity

**DIAGNOSTIC / HUMAN_REVIEW_PENDING**；base `92366d882a23c356f56ea87830463d6417576875`。
新增完整一樓fit、25格office approach source-camera定位（含離屏箭頭與native XY圖）、
public visibility時段，以及HR02人物／精確腳底callout／1.70m身高尺。1.359735m為
landmark→候選脚底的垂直差，並非樓高；binding仍pending。所有舊圖及動畫保留。
FRONT public evidence為0–4.0s、REAR為9.0–9.8s；兩者均無資料的frames21–44為
4.2–8.8s。Camera geometry guides未轉成完整FOV／occlusion認證；5s viewer approach
與10s public trajectory時軸分開。Context iframe使用固定manifest hash以避開舊browser cache。

28PNG共13,281,548bytes；renderer SHA256
`2d2832a86442d13955ef58f45af6b52fa9b2aaa3f3ff641ef64c10dc4d179b6f`，新增manifest SHA256
`107d128a637978ee5b00a188e721b3d4fefc9a2b5ab129cab331e6177006c2a4`。
181原artifacts含138PNG／1GIF／1JPEG、29frozen inputs、decisions/template bytes及source
hash全數核對不變；四項decisions仍null、e105 payload保留。Native UI QA通過完整地圖、
frame24離屏camera定位及HR02人物/腳底/雙尺；實際JPEG與integration receipt保留。
74相關tests、Ruff、mypy93core＋4reviewtools、diffcheck通過。早先flat-lighting試作另存
`/private/tmp/amidst-review-clarity-qa-v1/`，不屬canonical evidence；沒有刪除舊artifacts。
原1580-test全套屬2026-10-06 evidence，本輪未重跑。無GT／recipe／evaluation、source
修改、human approval、formal Cases、push、merge或freeze tag。

本輪完整獨立APFS副本保存於canonical checkout的ignored
`data/pilot/phase1_finalization_human_review_20261007/clarity/human_review/`；前四份副本保留。
223個manifest artifacts共107,121,780bytes，source／副本每項hash與完整file inventory一致。
Package manifest SHA256：`e09e86998bed4248bcc9950084233a1ea141f1bf785f52176177e3c13a416bc5`；
copy_verification.json另記錄核對結果，四項決策仍pending。

## 2026-10-07 — Person position synchronized with fixed model/topology

**DIAGNOSTIC / HUMAN_REVIEW_PENDING**；base `e4b7821f1e6c282ff571f6d56322b74e6354a958`。
原50張行走render上新增同步P(t)候選腳底游標與L(t) landmark、右圖小人物及目前關係。
N1／N2與4個vertices固定；t=4s是N1、4.2–8.8s沿既有E1 candidate並顯示進度、t=9s是
N2，前後public片段顯示GAP graph外。Raw／floor mode只改fixed graph顯示高度；人物
floor marker保留原render座標。Node association採原public double projection與既有
1e-6m tolerance，未放寬matching門檻，也未snap float32人物座標。未重建或排序候選。

UI僅在image載入後共同更新人物、diagram、time／state，拒絕stalecallbacks；播放控制
移至圖上方。Native browser確認N1／N2、frame25 E1進度20%、完整播至frame49後自動停、
raw／floor切換時foot pixel同為[472.1593683200794,415.5180004800999]。Fixed graph、
nodes／edges／vertices與前版deep equality，212原files及166PNG／1GIF／2JPEG、29inputs、
source SHA256與四項pending decisions全部保留；前版clarity package223artifact hashes
仍相符。新的UI JPEG60,323bytes；view SHA256
`9b6c675b519052b7d4f9f32d8cdcbbc49dd651c2c1047fad720ea4fd8666c153`。

79相關tests通過；控制項移位後13項相關tests再驗證通過，repo Ruff、mypy93core＋5review
tools、diff gate通過。本輪沒有Blender render、GT／evaluation／recipe reads、source或
physical authority／protocol修改、formal Cases、push、merge或freeze tag。

完整獨立APFS副本保存於canonical checkout的ignored
`data/pilot/phase1_finalization_human_review_20261007/topology_motion/human_review/`；
225個manifest artifacts共107,304,824bytes，source／副本每項hash與完整file inventory一致。
Package manifest SHA256：`c60c8193747039e25891a63ad2be5b04878c0f487f870b4345cd791ed2e8a06c`；
copy_verification.json另記錄核對結果。所有舊副本保留，localhost preview改指向新副本。

## 2026-10-07 — Stable topology playback layout

**DIAGNOSTIC / HUMAN_REVIEW_PENDING**；base `095af134dfb22eab51277e7affcce1198f67b0fd`。
修正每格 loading paragraph 在空／非空切換造成的版面重排：提示改為 model 內的 absolute
overlay，狀態欄保留固定兩行、play/time 固定寬度及穩定 scrollbar。原播放時序、50 renders、
人物座標、graph、projection、authority與四項pending decisions保持原樣。
Native browser 在 717及1124px content widths各核對50影格，layout/model/graph/controls/
current panel rectangles完全相同；各70個連續播放samples（含loading）也只有一組geometry。
221原files、166PNG／1GIF／3JPEG、33個既有hash-bound inputs及source SHA256核對不變。
新增58511-byte native JPEG及 `topology_playback_integration_manifest.json`。15項相關tests、
repo Ruff、mypy93core、diff check通過；全套舊benchmark/GT tests未重跑。無source修改、
GT、render、formal Cases、decision application、push、merge或freeze tag。

完整APFS獨立副本保存於canonical checkout的ignored
`data/pilot/phase1_finalization_human_review_20261007/topology_playback_stable/human_review/`。
227個artifacts共107,368,346bytes，逐檔hash／大小及完整inventory一致；前版225artifacts仍
逐檔hash相符。Package manifest SHA256：
`c7c3abc17c65b449b33558400bcb177edb46c351c3520351ddbed054902b3a72`。
8768 loopback preview指向新副本；copy_verification.json保存核對結果。

## 2026-10-07 — HR02 source-camera visibility and pending body-point binding

**DIAGNOSTIC / HUMAN_REVIEW_PENDING**；base `7140062019a00256df0543d7dc3e513c53090d9d`。
固定 Scene/frame220/subframe0、原校準、0.0247m/BU、public observations／投影與既有
GAP candidate；未讀原始3D點、GT、evaluation或recipe。完整source射線200次：landmark
26 CLEAR／74 OCCLUDED，與26原OBSERVED相容；候選腳底10 CLEAR／90 OCCLUDED，
16筆landmark通視但腳底被擋。Foot像素與原landmark差48.14–60.33px；1.3597349529m
仍是pending landmark→floor offset，不是ceiling。兩camera在AUDITORIUM annotation
AABB、OFFICE AABB之外，不據此認定room ownership。人工只確認目標房間／鏡頭與
追蹤點語意；fallback沿既有protocol，不新增人工設定。四項decisions及e105payload保留。

Frozen query producer `5efab2df3097b31f8a5a0e1d7439d6f426e79704f48e4e75016f76a7b0da65b6`
在 fresh process/output 重跑，audit JSON與producer receipt bytes/hash完全一致：
`5bda3a45843649ec2a3074bda87694847534a7401dd51e084a48b9cfac332035`／
`6105a46a1d753c94ab4e0083d2c59b01fb16c27d04abeb0dcf3b9fd22570d51f`。
這是source診斷重現，不是formal benchmark fresh gate。

Renderer以live VIEWPORT instance在iterator前進／任何BlenderID建立前保存owned arrays，
保留converted FONT及hidden prototypes；2,576instances、5,585,184triangles，完整
name/matrix inventory與原raycaster相同。先前cached evaluated RNA或original-name
lookup會失效／缺hidden prototype，失敗run未產生canonical PNG，未skip blockers。
Successful producer `1132d68ffa969196f640708f7635c0ada669663b6b379d3c37ae5e3a27b9d87e`
生成8張1920x1080PNG，共10,855,553bytes；wide/side無固定人物／ray，50frame overlay
單獨同步。最初8PNG共10,910,996bytes及精確producer/receipts/view另外保留。
六張camera still也因snapshot修正而hash改變，render_verification如實記錄；未宣稱不同
producer的像素完全一致。灰模render不是CV pixel或physical certification。

新頁整合原dashboard/HR02dialog，display-only recommendation為KEEP_REVIEW；原
APPROVE profiles與payload不變。Native IAB核對50格motion/wide/side同步、唯一一組
layout geometry、獨立代表stills、完整播放至49停止，HR02defaultaudit/HR01defaultmotion
及單一iframe/close cleanup。172相關tests（78既有＋94新增/整合）、repoRuff、mypy
93core＋6reviewtools、diffcheck通過。220個prior artifacts未改，7個明確UI/source/docs
更新；166舊PNG／1GIF／4JPEG、32frozen inputs、decisions/template及source hashes保留。
沒有authority升級、source保存、formal Cases、push、merge或freeze tag。

完整獨立副本保存於 canonical checkout ignored
`data/pilot/phase1_finalization_human_review_20261007/hr02_camera_audit/human_review/`。
267個artifacts共130,717,159bytes，source／副本逐檔hash、大小與inventory一致；前版227個
artifacts仍逐檔hash相符。Package manifest SHA256：
`b58ab23c76ad19e9997a337f4547d59c296e869c4e0da1369034a96277facdeb`。
同一8768 loopback網址指向新副本，copy_verification.json保存核對結果。

## 2026-10-07 — Explicit approvals recorded; automatic certification not run

Current human gate：**EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION**。
人類已確認房間／兩台 source cameras 綁定，接受剛性 landmark 建議，並核准其餘三項。
保存四項 APPROVE 與原先定義的 profiles：HR-01 `LOCAL_SOURCE_SURFACE_ONLY`、HR-02
`SOURCE_BOUND_RIGID_LANDMARK_OFFSET`、HR-03 `ADE_EPSILON_0_50_M`、HR-04
`EXISTING_SPEED_WITH_SUPPORTED_DWELL`。人工 pending／blocking 為空，Case 1–3 共用
人工 blockers 各 0；原 checkpoint 四項 blocker map 保留為歷史，另產生目前空的 IDs。

[approval_record.json](../human_review/approval_record.json) 保存直接人類授權與限定 scope；
[APPROVALS.md](../human_review/APPROVALS.md) 區分 semantic approval 和自動認證。
[approval_validation.json](../human_review/approval_validation.json) 的唯讀核對通過：
29 locked inputs、57 original frames、checkpoint ancestry、source hash 與 immutable
`e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463` payload 保留。
未使用 GT／recipe／evaluation 幫助決策；未改 source、物理 config、研究門檻或原問題內容。

README／dashboard／package 狀態反映實際四項核准；Coverage 選定 **ADE < 0.50 m**、
speed/timing 選定 **0.7904 m/s + supported departure dwell**。旧圖與機器結論保留為
核准前證據，不再把目前人工狀態標成 null／KEEP_REVIEW。
**human_decisions_recorded=true；human_decisions_applied=false；certificate NOT_RUN；
formal execution disabled。** 沒有 apply、certificate generation、formal Case 1–3、
Baseline A/B/C、formal dataset、freeze tag 或 main merge。

177 review tests、repo Ruff、strict mypy 4 review tools 通過。這是批准記錄／介面的驗證，
不替代 formal exit gates。下一階段由 agent 完成 bounded certificate、formal adapters、
fresh observation 與 case inventory；原 diagnostic routes 不會直接變正式 Cases。
先前 blocked diagnostic／pending review checkpoint、raw previews 與獨立副本全部保留。
新版完整持久副本已存於 canonical checkout ignored
`data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review/`；
272 manifest artifacts／130,829,356 bytes、273 complete copy files 全部核對 PASS。
Package manifest SHA-256：
`923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187`。
188 個 prior raw media hashes 未改；四個 APPROVE 與 immutable/source hashes 在副本一致。
8768 loopback server 已改指 approved copy，HTTP 核對與 native UI 均通過。
Native dashboard 已核對 4/4 HUMAN_APPROVED、四個 APPROVE/profile rows、Total 與 Case 1–3
human blockers 均 0，active iframe 仍為 1。實際原生截圖
`human_review/frames/dashboard_context/approvals_recorded.jpg` 為 84,378 bytes，分類為
REGENERABLE；先前 267-artifact／130,717,159-byte preapproval package 保留不變。

## 2026-10-08 — Final reviewed clean-checkout rerun verified

最終 fresh checkout：`/private/tmp/amidst-phase1-finalization-fresh-20261007`，code SHA
`e6fbc8fbb3bf8c36355db38c299de5ff37705604`。新輸出為
`data/finalization/reviewed_fresh_v5_final/`；local canonical 保持
`/private/tmp/amidst-phase1-finalization/data/finalization/reviewed_run_v5/`。
原 source、HR01–HR04 payload、舊 review／dataset／demo／各次 fresh outputs 全部保留。
新增 reference movement policy 沿獨立批准 receipt 在 fresh export 前鎖定，沒有回寫舊結果。

Fresh `evaluation/verification.json` 如實記錄 **PHASE1_FINALIZATION_BLOCKED**：Case1 是
`FORMAL_REVIEWED_LOCAL_RUN`，Case3 是 `FORMAL_REVIEWED_LOCAL_TEMPORAL_COMPONENT`，
兩者 execution ready；Case2 為 `N/A_BLOCKED_SCOPE`。目前完整批准 domain 只有一個主要
source-distinct route class；Case2 的真正 branching 與 Case3 detour／candidate-growth
完整 stress gate 仍依賴合法新增 branching scope，不把平行 offset 或 timing duplicates
當成不同分支。Overall formal execution／all-case dataset validation／freeze 仍為 false。

Fresh `verify-reproduction` **PASS**：repeat、fresh process、observation ordering、GT poison
及 bounded termination 全部通過。Poison 同時改 evaluation GT、simulation recipe 和兩份
reference movement annotations；malformed annotations 沒有改變 primary inference，
poisoned positions 改變 evaluation。Ready Case1／3 的推論順序與 termination 保持相同。

[最終完整交付對照 receipt](../data/finalization/reviewed_checkpoint_v2/fresh_delivery_comparison_final.json)
為 **PASS**，differences 與 missing required reports 均為空。Dataset 全部 artifact hashes、
canonical inference／candidate order／termination、metrics／report semantics、非 runtime
PNG 與 canonical demo presentations 一致；核對 41 JSON、1 CSV、4 Markdown、21 PNG、
2 RRD。實測 runtime／runtime plot pixels 與 RRD container metadata bytes 明確排除
byte equality，但仍要求 artifacts 的 availability、counts 和 recording verification。

Final fresh dataset manifest SHA256：
`a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5`；primary inference
freeze SHA256：`d16708cfb437b6dff2ea06139126d5784a181c547d9dba6d1633068988cf4059`，
兩者與 local canonical 相同。Fresh reproduction receipt SHA256：
`9020af0f8f8e1ac3098096a711a50d8dd927b5d6e3bec1fe96c68d6415d9a4d1`。
本項記錄是 ready local cases 的實際 fresh delivery evidence；不宣稱完整 Case2 已解決，
不宣稱原 Phase1 Exit Gate／全部 formal Cases 通過，不授予 freeze tag。
