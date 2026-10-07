# Phase 1 核准後實作交接 / Post-approval implementation handoff

Date: 2026-10-07. This checkpoint prepares a new conversation; it does not execute
decision application, certify geometry, publish a freeze, or produce formal results.

## 工作位置與 checkpoint

- **所有 repo 工作使用 `/private/tmp/amidst-phase1-finalization`**，branch
  `phase1/finalization-sprint`。這是同一 Git repo 已存在的 worktree，必須直接續用。
- Approval commit: `10a3fccea609128dc3d7c31062c0bdde9f17b0cb`。交接 commit 是包含
  本文件及 `PHASE1_POST_APPROVAL_CHECKPOINT.json` 的 commit；新對話 prompt 提供精確 SHA。
- Canonical checkout `/Users/polalabear/Developer/amidst` 仍在
  `phase1/physical-policy-approval` / `c5956dc825f669e28e2694578be0fed97432a786`。
  它供應原始 scene 與持久 raw artifacts，**不要 checkout/reset 該 checkout 或在其中實作**。
- Physical baseline `f264db1579882e54cecba22db24ec8798822fd0c`；projection baseline
  `8f4055ffcdc3bf6efd723c7956ac685e1fe033f1` 已 selective integrate，不 merge 實驗 branch 歷史。
- Phase 2 `phase2/integration-hardening` /
  `5b51d2c67917ff434f53e12a8af8af3d711d2a19` **FROZEN**；Case 4 **DEFERRED**。

## 授權與完成定義

使用者授權新對話進行大規模實作，完成原 Phase 1 Finalization Sprint。範圍是現有
架構內的 additive adapters、case inventory、正式 export/inference/evaluation/report/demo
流程與必要測試；不擴大研究題目、不重設架構、不要求整棟 school 完美。
原 Sprint 授權 finalization commits 與 push 此 branch；不 merge main、rewrite history 或
force push。只有原 Exit Gate 全部通過，才建立 annotated Phase 1 freeze tag。

讀取 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)、
[benchmark protocol](PHASE1_BENCHMARK_PROTOCOL.md)、
[decision application](../human_review/DECISION_APPLICATION.md) 與
[approval summary](../human_review/APPROVALS.md)。規則沿用原文件；本交接不另訂 benchmark。
紀錄寫入 WORK_LOG / EXPERIMENT_LOG，持續更新正式結果、reproduction、cleanup 與 handoff。

## 已完成與目前狀態

四項 **APPROVE** 已填入 `human_review/decisions.json`，已驗證 immutable payload、
source、checkpoint ancestry、29 locked inputs 與 57 original frames。全部人工 blocker 為 0。
`human_decisions_recorded=true`；`human_decisions_applied=false`；certificate **NOT_RUN**；
formal Cases 1–3 / A–C / GT isolation / determinism / fresh formal rerun 均 **NOT_RUN**。
Overall physical authority **PARTIAL_APPROVED**，complete local certificates 尚為 0。
目前 Phase 1 狀態仍 **PHASE1_FINALIZATION_BLOCKED**，人工 gate 本身已完成。

| ID | 已核准 profile | 必須保留的範圍／值 |
| --- | --- | --- |
| HR-01 | `LOCAL_SOURCE_SURFACE_ONLY` | 僅既定 office body envelope、`group_0/component-00000000` 和 exact-zero-area faces 1975/2398；不核准整個 component |
| HR-02 | `SOURCE_BOUND_RIGID_LANDMARK_OFFSET` | 房間／兩台 camera 綁定已確認；rigid upright、同 XY、source-bound 固定 landmark→floor offset；office 1.3597349528884888 m；fresh observations 必須生成 |
| HR-03 | `ADE_EPSILON_0_50_M` | D=ADE，嚴格 ADE < 0.50 m；採樣／對齊／K 沿用原 selected profile 與 protocol |
| HR-04 | `EXISTING_SPEED_WITH_SUPPORTED_DWELL` | 最大 32 BU/s = 0.7904 m/s；uniform first，僅既有 departure dwell；direct slack tolerance 1.0 s |

不重問以上人類選值。只在新的 source geometry contradiction、必要 case scope 超出
明示核准 domain，或必要新 landmark 語意時重開**最小**人工 gate；先完成不依賴該決策的工作。
保留舊 review、draft、raw renders、diagnostic dataset 與 provenance，不直接升格為 FORMAL。

## 第一次操作與資產

```sh
cd /private/tmp/amidst-phase1-finalization
git status --short
git branch --show-current
git rev-parse HEAD
PYTHONDONTWRITEBYTECODE=1 uv run python human_review/apply_decisions.py \
  --decisions human_review/decisions.json \
  --source-asset /Users/polalabear/Developer/amidst/blender/school_v3.blend
```

接著直接執行下一步，不需要再要求人類確認：

```sh
PYTHONDONTWRITEBYTECODE=1 uv run python human_review/apply_decisions.py \
  --decisions human_review/decisions.json \
  --source-asset /Users/polalabear/Developer/amidst/blender/school_v3.blend \
  --apply --output data/finalization/human_review_applied_v1
```

Output 必須不存在；若已存在，讀取並驗證既有 receipt，或使用新的版本化 output，不能覆寫。
入口會輸出 review receipt、certificate_result、approved_input_lock、resume_plan 與 manifest。
**APPROVE 不保證 certificate PASS；此工具不會自動開啟 formal_execution_enabled。**

原 scene `/Users/polalabear/Developer/amidst/blender/school_v3.blend`：468300506 bytes，SHA-256
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`。
Scale **1 BU = 0.0247 m**，不改／儲存／縮放原 scene。
Blender executable `/Applications/Blender.app/Contents/MacOS/Blender`。
本 worktree 已有 `.venv` 與 physical evidence；fresh checkout 仍須以現有 materializer
重建，實際 CLI 見 [reproduction guide](PHASE1_REPRODUCTION.md)。Python 使用 uv。

已核准完整 review 的持久副本：
`/Users/polalabear/Developer/amidst/data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review/`。
272 manifest artifacts / 130829356 bytes；273 complete copy files 核對 PASS。
Manifest SHA-256 `923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187`。
若新 checkout 缺 ignored media，從此副本複製缺少且 hash 相符的 raw inputs，不覆寫 source
或已提交 decisions。Canonical ignored `data/pilot/phase1_finalization_20261006/` 保留
diagnostic dataset/RRD；同日期其他 review versions 全部保留。
Review 的 29 inputs 還包括 ignored `data/finalization/local_run` public dataset/graph 和
materialized physical evidence；57 原影格同樣必須齊全。先還原／重建 historical inputs
並核對原 hash，再 apply；不能用新 formal output 取代這些審查輸入。

## 實作順序與關鍵缺口

1. **套用決策／重算 bounded certificate。** 使用 `human_review/certificate_application.py`
   與既有 `local_physical_scopes`。全量 source/support/body/clearance/collision proof 必須
   維持既有 numerics；若不是 PASS，定位真實原因，不換空 collider 或裁切來通過。
2. **Additive formal adapters。** 將 reviewed restricted provider、source-bound rigid
   marker→floor contact、合法 camera/context/metric authority 接入現有 pipeline。
   `benchmark/baselines.py::run_baseline` 目前只接受 legacy restricted provider 並讀其
   certificate 欄位；reviewed wrapper 必須保留 semantic receipt / scope / source hash
   驗證，不能 unwrap physical_certificate 來繞過 authority。
   Exact multiview 目前使用 `EXACT_TIME_MULTIVIEW_NO_PLANE_ASSUMPTION`；處理既有 topology
   plane binding 相容性，保留 method/provenance/uncertainty，不強迫換成 fixed-plane 證據。
   `PilotInferenceContext` 的 PILOT/SYNTHETIC、UNVERIFIED scale／diagnostic plane／
   ANNOTATION_AABB_ONLY_PROVISIONAL literals，`MetricConfig` 的 UNRESOLVED status 及
   baseline 的 formal_available=false 都是既有 diagnostic contracts。正式 authority
   要以 additive 介面／receipt 實作，不能全域放寬這些 literals 冒充 formal。
3. **GT-free case inventory 與 formal config lock。** 在既有批准 domain 內證明：Case 1
   visible→GAP→visible 且唯一主要 feasible route；Case 2 至少 2–3 條真正 distinct feasible
   routes，保留 K=1/2/3；Case 3 具有原 protocol 的 long-GAP／時間速度歧義。
   原 office direct/right 平行 offset 不是 branching proof，舊 5 秒 GAP 不是 long-gap proof。
   Approved footpoint domain 約 X=[1399.9985317,1411.9999243] BU（寬 0.296434 m）、
   Y=[1939.9994361,2096.8005463] BU、Z=20.07884979 BU；精確值以 immutable profile 為準。
   不能擴張 guard 或把小偏移當分支來通過 Case 2；若合法 inventory 不足，提出精確的
   automatic blocker，分開必要 scope 與可繼續的實作，不先猜新人工語意。
   路徑 eligibility、seed、schedule、alignment、sampling、metrics、baseline 與 ablations
   都在 simulation/evaluation 前固定；不根據 GT 或結果挑 route／調規則。
4. **Fresh formal dataset 與正式執行。** 沿用 Blender exporter、`phase1_projection_policy`、
   `FrameSampleDataset`、Graph engine 與 `BlindGapReconstructor`，不複製 inference engine。
   Additive reviewed configs / adapters 另版本化；不要修改 29 review-bound inputs、immutable
   profiles、原 `configs/benchmarks/protocol_v1.json` 或歷史 diagnostic input lock。
   Review 綁定的 `baselines.py`、`datasets/pilot.py`、`pilot_topology.py`、metric config、
   search/reconstruction 與 semantic/projection producers 也保留原 bytes；formal wrappers
   另加模組。Budget lineage 先檢查原 pilot 的 maxCandidate=3、nodes=1000、maxPath=1000 BU、
   time=10 s、branch=3、detour=2（單位依原 schema），不要默默改用不同 core defaults。
5. **A/B/C 與 supported ablations／完整評估。** 沿用 `src/amidst/benchmark/baselines.py`
   的 traversal/factor masks，`benchmark_report`、report producer 與 Rerun adapter。
   報告保留失敗、empty、N/A rows；同一 metrics/K/input population。候選排序／pruning
   不能接觸 GT；Coverage 與 moving-time policy 必須依 protocol。
6. **Reproducibility／freeze。** Repeated inference、fresh process、GT poison、ordering、
   termination、source/config hashes；fresh checkout/output 完整重建 materialization →
   dataset → Cases → report/charts → demo。對照 canonical hashes、metrics、candidate order、
   termination；runtime/RRD 容器非 deterministic 部分沿既有定義分開。差異未定位先不 freeze。

Projection policy 保持 EXACT_TIME_MULTIVIEW 優先，合法同步 evidence 不足時
SINGLE_VIEW_FIXED_PLANE；保留 conditioning / uncertainty、LOW_CONFIDENCE、UNAVAILABLE。
不以 GT 選 camera pair／hypothesis、不 sample rejection 造 accuracy、不調 Coverage epsilon。
School surface authority 不足時 surface-constrained inference **N/A**，正式量化限制。
73 HC WALL、1422 HUMAN_REVIEW WALL、8 portal conflicts、Stair A/B 不升格。

## 最終交付與 Exit Gate

交付 reproducible formal dataset／manifest/hashes、Case 1–3 × A/B/C × K 的完整結果表，
accuracy／Coverage／Top-K／candidate／runtime／search／termination／physical／projection
圖表與 status、每 Case 正式 RRD + static PNG + replay 說明、final report、reproduction guide、
experiment log、benchmark docs、handoff、cleanup 分類。Raw `.blend`／RRD／render／large
evidence 保持本機，不帶進 Git；不要自動刪 DELETE_CANDIDATE。

每個可執行 milestone 驗證後獨立 commit。最終 gates 使用完整 pytest（需實際 physical
evidence）、Ruff、strict mypy、diff check，以及原 Sprint 全部 formal/reproduction gates。
全部成立才標 **PHASE1_VALIDATED_AND_FROZEN**，push `phase1/finalization-sprint` 並建立
dated annotated freeze tag（含 SHA、dataset/protocol version、package hash、result/authority
status、projection policy、limitations、Case4/Phase2 deferred）。否則保持
**PHASE1_FINALIZATION_BLOCKED**，只列最少的實際 blockers；不得虛構 PASS。

## 歷史驗證，非本次重跑

Approval checkpoint `10a3fcc`：177 review tests、repo Ruff、strict mypy 4 review tools、diff
check 通過。早期 diagnostic checkpoint 已有 materialization/export/replay/GT poison/
fresh evidence，見 [final report](PHASE1_FINAL_REPORT.md)；不取代正式 Case Exit Gate。
本次交接只做 checkpoint/hash/文件一致性驗證，不執行 application 或 formal Cases。

已核准的 metric profile 固定 5 Hz、source endpoints inclusive、piecewise-linear 到
**全部** reference timestamps、exact extent，不 clipping/extrapolation、不 rejection；
K=[1,2,3] 的 distinct routes 第一個 timing。Inference 不讀 reference，此對齊只在 evaluation。
Body/contact values 依原 policy；pixel_sigma_px=null，不能捏造 pixel-noise accuracy。
Export seed lineage=20261005、downstream lineage=42；formal 各用途 seed 明示鎖定。
原始權重未核准，不跨 Case 平均宣稱 overall Coverage target PASS。

可復用的其他入口：`amidst.physical_units.native_*_to_metres` 正規化所有 BU contracts；
`amidst.domain.stream` 的 StreamBinding / RawProjectedFrameSample / BoundObservation /
BoundGapEvent；`amidst.evaluation.configured`；`amidst.benchmark.runner`；
`python -m amidst.benchmark_report`；`amidst.visualization.rerun_adapter.RerunDebugVisualizationAdapter`。
Frozen runtime 使用 committed uv.lock、Python 3.12.12；僅需要時 `uv sync --locked`。

```sh
AMIDST_PHYSICAL_SOURCE_SCENE=/Users/polalabear/Developer/amidst/blender/school_v3.blend \
  uv run pytest --require-physical-evidence -rs
uv run ruff check .
uv run mypy
git diff --check
```

English: Continue in the existing finalization worktree from the exact handoff SHA supplied
in the new task. All four original human approvals are final; apply them, regenerate bounded
certification, implement additive formal authority/binding/case adapters, and finish the
original formal sprint autonomously. Preserve immutable source/protocol/GT boundaries.
Freeze only after every formal exit gate passes; reopen human review only for a real new
geometry contradiction or an indispensable scope outside the existing approval.
