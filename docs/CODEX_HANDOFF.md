# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-07。Branch：`phase1/finalization-sprint`。
目前狀態：**PHASE1_FINALIZATION_BLOCKED**；沒有 freeze tag，不 merge main。
已驗證 source milestone：`e9ade14ffd0838712935f210f17c947563a08a29`。
完成證據見 [final report](PHASE1_FINAL_REPORT.md) 和 [experiment log](EXPERIMENT_LOG.md)；
持續規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)。

唯一續作入口是 [human_review](../human_review/README.md)：限定 domain/相關 face 的
語意或 derived correction、camera landmark/floor semantic binding、正式研究容差。
最小審查已產生 [dashboard](../human_review/index.html) 和
[decisions.json](../human_review/decisions.json)，共 **4** 個 pending：HR-01 office bounded
source semantics、HR-02 marker/floor binding、HR-03 Coverage epsilon、HR-04 speed/timing。
審查統一入口為原 dashboard 的 [共同視覺工作區](../human_review/index.html#visual-review-workspace)：
定位、行走、模型／拓樸及問題近看同頁切換。HR01/02dialog內同樣可看；原圖／舊預覽保留。
只有active player載入，四項決策、profiles及draft/import/export identity保持原樣。
附 10 秒 GT-free 連續 frames 與 exact scope closeups；先審 HR-01→02→03→04。
HR-01/02 另附 [完整空間導覽](../human_review/frames/spatial_context/guide.html)：
school 定位、1F/camera 座標、5 秒鏡頭接近、原有 10 秒局部移動、問題近看。
新增 display context 不改四項問題、原 57 張 evidence 或使用者 browser draft；
鏡頭移動不是新增人物路徑，HR-02 的 1.3597 m 是 landmark→floor offset。
審查辨識補充在同一導覽提供完整一樓測試空間、FRONT／REAR 原座標定位與 public visibility
時間對照，以及 HR-02 source 側視人物／腳底／landmark 量尺。1.3597 m 不是樓高；camera
方向／frustum 是 calibration 的顯示參考，不證明完整 source occlusion。舊圖／動畫保留。
人物拓樸定位另以 P(t) 隨既有影格同步更新；N1／N2及四個vertex固定，顯示目前N1、E1
進度、N2或GAP graph外。播放載入提示浮在模型內，動態狀態與控制列保留固定尺寸，避免每格重排。
Body位置／binding仍為pending HR02；沒有新增Graph nodes。
另有 [新增 10 秒模型人物動作](../human_review/frames/motion_context/player.html)：
固定鏡頭下，人物在 actual bounded source model 內移動，含 body /clearance 與 GAP。
50 frames 的位置 /time /camera /projection 全部沿用原預覽，joint pose 只供顯示；
原 85 張圖、原 guide/player 與四項問題均保留，不是 school approval 或 formal run。
另增 [模型／拓樸對照](../human_review/frames/topology_context/view.html)：N1／N2、E1–E3
在模型與空白圖例一致；只有2個registered nodes，4個折點不加入Graph。raw graph全3邊保留，
floor定位仍pending HR-02，configured parallel routes不證明Case2 branching。
只提供 APPROVE/REJECT/FIX_GEOMETRY/KEEP_REVIEW；不要求人工計算 clearance、certificate、
route uniqueness/branch count 或 feasible inventory，這些由 agent 在語意決策後重跑。
不審 1,422 WALL patches、無關 portal conflicts 或 Stair A/B。

Approved scale 0.0247 m/BU、body/clearance、48 floor-supported subdomains、58 approved
components 保留；overall PARTIAL_APPROVED，complete local certificates=0。
正式 Coverage/MetricConfig 和 Case-specific navigation/camera authority 未定案；
formal Cases1–3/A–C/GT isolation/determinism/fresh benchmark 均 NOT_RUN。
不能由 diagnostic PASS、annotation AABB 或空 collider 集合解除 gate。
[Decision application](../human_review/DECISION_APPLICATION.md) 可驗證 hashes、完整 explicit
decisions、重新計算 bounded certificate 並鎖定選定值；本輪未套用 school approval。
全部 APPROVE 後先完成 agent-owned formal adapters / case inventory：現有 office direct/right
平行 offset 不能代替 Case2 branching proof，Case1 uniqueness / Case3 stress instance 亦待證明。
不能承諾立即 formal run；不用人類再整理資料，只有真正新矛盾或超出核准 domain 才重開 gate。

[Input lock](../data/finalization/checkpoint/input_lock.json) 固定本輪 diagnostic inputs/code；
[reproduction guide](PHASE1_REPRODUCTION.md) 重建資料、physical evidence、projection/Graph、
baseline regression、RRD 和 report。Optional additive projection 優先 exact-time multiview，
不足時 fixed-plane fallback；保留全 evidence 和 uncertainty sidecars。Office/corridor 沒有
同步雙視角 endpoints；auditorium 因原 topology contract INPUT_REJECTED。Covariance 未進入
ranking/pruning，surface-constrained inference N/A。Formal 設定須另行版本化後才執行。

Raw local/fresh data 與 demos 持久保存在 ignored
`data/pilot/phase1_finalization_20261006/`；source Blender 不變。
含 spatial guide 的完整 review 本機副本在 canonical checkout 的
`data/pilot/phase1_finalization_human_review_20261007/human_review/`。
新增模型動作的完整副本另存
`data/pilot/phase1_finalization_human_review_20261007/body_motion/human_review/`；上一版保留。
拓樸補充的完整副本另存
`data/pilot/phase1_finalization_human_review_20261007/topology/human_review/`。
整合介面的完整副本另存
`data/pilot/phase1_finalization_human_review_20261007/dashboard/human_review/`。
辨識補充完整副本另存
`data/pilot/phase1_finalization_human_review_20261007/clarity/human_review/`。
人物同步拓樸版本另存於
`data/pilot/phase1_finalization_human_review_20261007/topology_motion/human_review/`；前版保留。
穩定播放版另存於
`data/pilot/phase1_finalization_human_review_20261007/topology_playback_stable/human_review/`。
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
The new offline dashboard contains four pending decisions (geometry, marker/floor binding,
Coverage epsilon, speed/timing), a GT-free 10-second sequence and bounded scope closeups.
The [shared visual workspace](../human_review/index.html#visual-review-workspace) now embeds
location, body motion, topology and issue views in the original dashboard and HR01/02 dialogs.
It loads one player at a time and retains old evidence and the decision/draft identity.
The [spatial guide](../human_review/frames/spatial_context/guide.html) adds school/floor/camera
location, a five-second camera approach and the unchanged local movement/issue views.
Its display context preserves the four questions, original image hashes and browser drafts.
The clarity supplement fits the complete first-floor test context and both native camera
locations, pairs them with public visibility times, and adds an HR-02 source-side body,
footpoint and landmark ruler. The 1.3597 m value is a pending marker-to-foot offset, not
floor-to-ceiling height. Calibration frusta are display references, not occlusion proof;
all earlier views remain available.
The topology locator synchronizes P(t) with each existing motion frame while nodes and
vertices remain fixed; it identifies N1, E1 progress, N2 or positions outside the GAP graph.
Loading status overlays the model, and fixed status/control dimensions prevent per-frame
layout shifts. Person placement remains pending HR02, with no additional graph nodes.
The separate [ten-second body-motion player](../human_review/frames/motion_context/player.html)
adds a moving illustrated body in actual local source geometry with a fixed camera.
It preserves all 85 older images and every existing trajectory/evidence field; joints are display-only.
The [model/topology locator](../human_review/frames/topology_context/view.html) uses matching
N1/N2 and E1–E3 labels. Four polyline corners are not registered nodes. All three raw graph
edges remain; floor mapping is pending HR-02 and configured routes do not prove Case2 branches.
The application pipeline validates explicit decisions and hashes, regenerates the bounded
certificate and locks inputs. No school decision has been applied. Formal adapters and an
independent case inventory still need automatic completion; current parallel routes do not
establish Case2 branching. Resume directly from completed decisions, without another manual
evidence-organization round; reopen only for a real contradiction or an unapproved domain.

The input lock and reproduction guide bind the diagnostic package and code. Optional
projection uses legal exact-time multiview then fixed-plane fallback, preserving all evidence
and uncertainty. Office/corridor lack paired endpoints; auditorium has a typed topology
input rejection. Covariance ranking and approved school surface inference are unavailable.
Persistent raw data and demos are local under the ignored path above. No cleanup deletion
was performed. Endpoint attachment, visibility arbitration and origin/missing-frame
attestation remain deferred. Case4 is deferred and Phase2 remains frozen at its exact SHA.
Resume at the human gate, version formal settings before execution, and freeze only after
all original exit gates pass.
