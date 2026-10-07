# Phase 1 finalization report / Phase 1 收尾報告

## 2026-10-07 — Human approvals recorded / 人工核准已記錄

Current human-review state: **EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION**.
四項人類 APPROVE 已保存；Case 1–3 的人工未決／blocking IDs 均為空。此狀態只表示
人工決策完成，**human_decisions_recorded=true、human_decisions_applied=false**。
Physical certificate **NOT_RUN**；formal Cases 1–3、Baseline A/B/C、正式 GT-isolation／
determinism／fresh rerun 仍 **NOT_RUN**。Phase 1 exit gate 尚未通過，沒有 freeze tag。

| Item | Approved profile | Bounded meaning |
| --- | --- | --- |
| HR-01 | `LOCAL_SOURCE_SURFACE_ONLY` | 限定 body guard 的 source-surface 語意；指定零面積接縫不占實心體積，不核准整個 component |
| HR-02 | `SOURCE_BOUND_RIGID_LANDMARK_OFFSET` | 目標房間／兩台 source cameras 綁定與固定剛性 landmark 語意；按 context plane − approved support 精確換算 footpoint |
| HR-03 | `ADE_EPSILON_0_50_M` | Coverage D=ADE，嚴格 `< 0.50 m`；formal config 尚待鎖定 |
| HR-04 | `EXISTING_SPEED_WITH_SUPPORTED_DWELL` | 0.7904 m/s，既有 timing slack 與已支援的 departure dwell；不發明新 timing contract |

[Approval record](../human_review/approval_record.json)、
[approval summary](../human_review/APPROVALS.md) 與
[read-only validation](../human_review/approval_validation.json) 保存授權、selected profiles
及 source-bound 核對結果。原 immutable question payload
`e105c3116ebec64e94667f2f863bb0868f4fc34eeeedf1ced0a0b1a931ee1463` 不變；
29 locked inputs、57 original review frames、checkpoint ancestry 與 source hashes 驗證通過。
這不是 authority application 或 physical certificate PASS。

接續工作由 agent 負責：apply decisions、重算 bounded certificates、固定 formal configs、
建立 fresh observations 與獨立 Case 1 uniqueness／Case 2 route diversity／Case 3 timing
inventory，之後才跑正式 dataset、A/B/C、reports、Rerun 與 fresh exit gates。
舊 diagnostic streams／parallel offset routes 不因本次 APPROVE 變成 FORMAL。
只在新的 geometry contradiction、超出已核准 scope 或必要新 landmark 語意時重開人工 gate；
不追加整棟 WALL／portal／stair 審查。Source `.blend`、architectural scale、Phase 2 freeze
與既有 benchmark/projection policy 未改。

本輪批准記錄的驗證：**177 review tests**、repo Ruff、strict mypy **4 review tools** 通過；
沒有重跑下方歷史 full-suite／formal benchmark。完整持久副本已保存於 ignored
`data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review/`，
272 manifest artifacts／130,829,356 bytes、273 complete copy files 逐檔核對 PASS。
Package manifest SHA-256：
`923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187`。
188 個既有 raw media hashes 保留；先前 `hr02_camera_audit` 副本未覆寫。

All four explicit approvals are recorded and immutable inputs validate. There are zero
pending human blockers, but no decisions have been applied and no physical certificate or
formal case has run. Automatic certification, fresh observations, case inventories and the
formal exit gates remain required. Historical diagnostics below retain their original status.

## Historical blocked diagnostic checkpoint — 2026-10-06

Status date: **2026-10-06**. Final state: **PHASE1_FINALIZATION_BLOCKED**.
This is a reproducible blocked checkpoint, not a Phase 1 freeze or formal research result.

## 繁體中文

### Checkpoints 與 scope

Finalization branch：`phase1/finalization-sprint`。已驗證 source milestone：
`e9ade14ffd0838712935f210f17c947563a08a29`；報告／handoff 的 published SHA 以 branch
tip 為準。基底為已發布 physical checkpoint
`f264db1579882e54cecba22db24ec8798822fd0c`。從 projection checkpoint
`8f4055ffcdc3bf6efd723c7956ac685e1fe033f1` 精準複製四組 helper/test closure；
未 merge projection 實驗歷史，未覆寫 physical configs/dependencies。
Report-only CSV LF producer 修正於 `64116c172ad9bc5db9f46c8f491a2014fdbc063b`，
兩份 clean-output report 重新逐 byte 核對；不改 inference 或研究設定。

Source `school_v3.blend` SHA-256：
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
468,300,506 bytes。Architectural scale **APPROVED，1 BU = 0.0247 m**；沒有縮放或儲存
source。Case 4 **DEFERRED**；Phase 2 branch
`phase2/integration-hardening` / `5b51d2c67917ff434f53e12a8af8af3d711d2a19`
**FROZEN**，本 Sprint 不修改、不 merge main。

### 正式結果與唯一 gate

Formal Cases 1–3、formal Baseline A/B/C、正式 GT-isolation/determinism/fresh-rerun
均為 **NOT_RUN**。完整 Case × A/B/C × K=1/2/3 的 27 rows 保留於
[result table](../data/finalization/checkpoint/benchmark_table.md)；accuracy、Coverage、
physical metrics 為 **N/A / NOT_CERTIFIED**，不是零誤差、PASS 或 synthetic 研究結論。
正式圖檔明示未量測狀態；projection method/confidence 圖只統計 DIAGNOSTIC。

唯一人工 gate 見 [human_review](../human_review/README.md)。最低決策是限定 domain / 相關
faces 的語意或 derived geometry 修正、camera landmark / floor semantic binding，以及
正式研究容差。Agent 在決策後負責 clearance/certificate、可達 endpoints、route uniqueness /
branch count、speed/time feasible inventory 和正式設定檔；不要求人工計算這些項目。
只提供 **APPROVE / REJECT / FIX_GEOMETRY / KEEP_REVIEW**。不要求審閱 1,422 WALL patches、
無關 portal conflicts 或 Stair A/B。Coverage D/epsilon/對齊/採樣仍依原 protocol 保留
unresolved，沒有以 regression epsilon 補值，也沒有 benchmark 後改規則。

### 可重現輸入與 Projection

Dataset version：`phase1-finalization-inputs-v1-diagnostic`。從原始 scene fresh export
三條既有 pilot definitions；每條 50 timestamps、兩個 cameras，共 300 records。
Package 分開 inference / simulation / evaluation，包含 source/calibration、timestamps、
2D visibility/occlusion/out-of-FOV、GT sidecar、recipe/seed、hash manifest。Inference
輸入只有 strict observations/context；所有 primary inference 完成後才在獨立 integrity /
evaluation 階段讀取 GT/recipe。這三條 streams **沒有被重新命名為正式 Cases 1–3**。

Additive policy：合法同步 evidence 優先 **EXACT_TIME_MULTIVIEW**，依 conditioning 再以
camera IDs deterministic tie-break；不足時 **SINGLE_VIEW_FIXED_PLANE**。保留全 evidence、
全部 legal pairs/plane sidecars、method/provenance/uncertainty，**LOW_CONFIDENCE** 不刪點，
無有效投影才 **UNAVAILABLE**。不用 GT 選 camera pair/hypothesis，不改 Coverage epsilon。
Optional projector 接入現有 FrameSampleDataset/Graph，共用原 pipeline；未另建 inference
engine。Covariance 仍未供 ranking/pruning 使用；pixel/calibration noise 未量測，confidence
不是機率。Approved school surface authority 不足，surface-constrained inference **N/A**。

| Diagnostic stream | Exact multi-view | Single-view | Unavailable | Policy Graph |
| --- | --- | --- | --- | --- |
| office | 0 | 26 | 24 | 3 routes / 6 timings / 4 expanded / COMPLETE |
| auditorium | 33 | 16 | 1 | INPUT_REJECTED；termination=null |
| corridor | 0 | 21 | 29 | 3 routes / 6 timings / 4 expanded / COMPLETE |

Office/corridor 全部沒有同步雙視角，包含 GAP endpoints。Auditorium 的 33/49 visible
timestamps 有合法 pair，但現有 two-visible-segment topology contract 不接受其完整 stream。
不得把 multiview unavailable 當 inference failure，亦不得假造 Graph termination。
Visible point mean projection error 是 noiseless source/model consistency DIAGNOSTIC：
office `3.06049e-5 m`、auditorium `1.14631e-5 m`、corridor `3.33161e-6 m`；不是 ADE 或
real-image accuracy。原 checkpoint 約 68% same-evidence noisy RMS 改善仍是歷史結果，
本輪沒有重新宣稱或外推該改善。

### Baselines 與物理邊界

A canonical shortest、B multiple geometric routes、C spatiotemporal 使用同一原有 heap
traversal；新增 factor masks 的預設值保留原 C。A/B timing-infeasible geometric ranks
保留 untimed sidecar，timed metrics N/A，不捏造速度或 timestamps、不壓縮 route ranks。
Approved purpose-bound consumers 可在 Top-K 截斷前 hard reject；不由 inspection 空集合
建立 collision-free authority。既有 single-factor ablations 保留同一 protocol。

[Baseline regression](../data/finalization/checkpoint/baseline_regression.json) 有 21 個真正
執行的 DIAGNOSTIC fixture comparisons，另 3 個 remove-collision rows 因缺 reference
approved consumer 為 N/A。不是 formal school Baseline A/B/C。Separate-process default C
與 physical baseline 的四個既有 fixture artifacts 相符；synthetic stair regression 不解除
Case 4 暫緩。

Physical materialization 在兩個獨立 checkout fresh 重建並 research-equivalent：48 supported
subdomains、58 approved components across 5/19 obstacles、collision diagnostic 4→2、
overall **PARTIAL_APPROVED**。Complete local certificates **0**；building physical_complete=false。
73 HIGH_CONFIDENCE / 1,422 HUMAN_REVIEW WALL、8 portal conflicts 和 Stair A/B 沒有升格。
Physical metric 缺完整 authority 時仍 N/A / NOT_CERTIFIED。

### Reproducibility、展示與驗證

乾淨 temporary checkout 在 source milestone，使用相同 locked CPython/runtime（為節省
磁碟共用已安裝 uv environment，PYTHONPATH 明確指向 fresh checkout source），重新
materialize、export、replay、baseline regression、report。Dataset manifest SHA-256：
`2c524e0074d06091aa330e2e0ca3ebf9639761ed96749fde07b0e9ab2fcac417`。
15 dataset artifacts、217 canonical replay artifacts、19 fresh-generated report artifacts
全部 byte-identical；baseline regression 一致。Repeated / reversed ordering / fresh-process /
GT poison 通過，poison 只改 evaluation。這些 PASS 的範圍為 DIAGNOSTIC，正式 Cases 尚未跑。

六份 local/fresh RRD 通過 reader interpretation/footer verification；三份診斷 demo 與
PNG 已產出，GT 是預設隱藏的獨立 layer。Demo 有校準 cameras、observed/gap、projection
method/confidence、configured Top-K/timings 與 provisional scope。沒有完整 school mesh 或
正式 collision-pruned example，**不宣稱已完成 formal Case demo**。
Runtime/RRD container metadata 非 deterministic；canonical inference/presentation/evaluation
hashes 未排除任何研究結果。見 [reproduction](PHASE1_REPRODUCTION.md)、[demo](PHASE1_DEMO.md)、
[repro evidence](../data/finalization/checkpoint/reproducibility.json)。

完整 `pytest --require-physical-evidence`：**1532 passed、5 skipped**，skip 全為歷史
school-v2 asset/calibration prerequisites。Ruff、strict mypy **92 files**、diff check 通過。
Source changes 驗證後建立 milestone；後續僅補 report/docs/curated summaries。

Raw datasets、RRD、PNG 和 drafts 另持久保存在 canonical repo 的 ignored
`data/pilot/phase1_finalization_20261006/`；大型 scene/evidence 保持本機。
[Cleanup inventory](PHASE1_ARTIFACT_CLEANUP.md) 只分類 KEEP/ARCHIVE/REGENERABLE，
DELETE_CANDIDATE 尚未選取，**沒有刪除**。Published blocked checkpoint 保存 source/config/tests/docs、
logs、summaries 和 hashes；不建立 `phase1-frozen-20261006`。

## English

The finalization branch starts at the exact physical checkpoint and selectively copies
the projection helper/test closure from the pinned projection SHA. Source milestone
`e9ade14ffd0838712935f210f17c947563a08a29` is validated; later commits publish the report
and curated evidence. The immutable school source and approved 0.0247 m/BU scale remain
unchanged. Phase 2 is frozen; Case 4 is deferred; main is not merged.

Formal Cases 1–3 and A/B/C results remain NOT_RUN. All 27 requested case/method/K rows
are retained as N/A/NOT_CERTIFIED. One consolidated human gate covers bounded local
geometry semantics/corrections, camera-landmark/floor semantics and formal research
tolerance. Clearance, certificates, reachable endpoints and route/timing inventories are
agent-owned checks after that decision. No unapproved walls, portals or stairs are promoted.

The diagnostic dataset contains three existing pilot definitions freshly exported from
the exact source: 300 two-camera records across 150 timestamps. Pure inference evidence
is isolated from simulation recipes and evaluation truth. The additive projector uses legal
exact-time multi-view, then fixed-plane fallback, with explicit provenance and retained
conditioning/uncertainty. Confidence never rejects samples; covariance is not consumed
by ranking/pruning. Office/corridor have no synchronized dual evidence, including their
GAP endpoints. Auditorium has 33 paired timestamps but its full stream is rejected by
the existing topology contract. Noiseless projection residuals are model-consistency
diagnostics, not formal ADE or image accuracy; the earlier 68% noisy RMS improvement
remains historical evidence.

A/B/C and existing ablations share the original bounded traversal. Untimed geometric
ranks remain N/A, preserving their ordering. Twenty-one fixture comparisons are executed;
three collision-removal rows are N/A without a reference approved consumer. Fresh physical
materialization preserves all approved partial authority and zero complete local scopes.

The independent clean source checkout reproduces all 15 dataset artifacts, 217 canonical
replay artifacts and 19 generated report artifacts byte-for-byte. Baseline regression,
ordering, termination, repeated/fresh-process inference and GT poison checks pass within
their diagnostic scope. Six RRD reader checks pass; three diagnostic previews and demos
are available with an initially hidden GT layer. Full school mesh and formal collision-pruned
demonstrations remain unavailable. Tests: 1532 passed, five historical school-v2 prerequisites
skipped; Ruff, mypy (92 source files) and diff checks pass. Raw assets remain local, cleanup
is inventory-only, and no freeze tag is created while the human gate is pending.
