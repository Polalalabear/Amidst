# Phase 1 研究成果續作交接 / Research release continuation

日期：2026-10-08。實作位置：`/private/tmp/amidst-phase1-finalization`，
branch：`phase1/finalization-sprint`。先驗 HEAD、origin 與工作目錄；canonical checkout
`/Users/polalabear/Developer/amidst` 只供應來源 scene/raw artifacts。

使用者已核准精確 corridor proposal，並要求在新對話完成一個可重現 dataset、
一份 benchmark 結果表、一個 Rerun 3D demo。這三項交付必須使用同一份 frozen
dataset/config/run。可直接貼上 [下一對話 prompt](PHASE1_NEXT_CHAT_PROMPT.md)。

## 已固定的起點

- 原 HR01–HR04 已 applied；獨立 MOVING/departure-DWELL reference policy 已另行核准。
- 新 proposal content SHA：`7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad`。
  [直接人工 receipt](../data/finalization/reviewed_corridor_scope_approval_v1/human_decision.json)
  content SHA：`702c2f7ca8165fc7669072847e26f38174b6525ed104999e35b467d23cebda09`。
  核准只限六個 exact cells、28 support faces、一個 obstacle source face 的兩個 native
  triangles、逐 guard bounded component interior、CAM01/CAM03 calibration/landmark binding。
  Zero-area exemption 為空；原核准未被取代。
- [Current checkpoint](../data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json)
  保存 application、獨立 numeric regeneration、source/protected bytes 與 producer hashes。
  六個 cells application 通過；乾淨 `d8b94a6` checkout 實際重建原數值證明得到
  **PASS_LOCAL_UNION_REGENERATED**。歷史 review/strict-preview/V5 packet 保留原 bytes。
- 不再重問上述核准。局部 physical authority 不等同 Case2 readiness 或全校 navigation
  authority；Phase1 overall Exit 仍 BLOCKED，Case4 DEFERRED、Phase2 FROZEN。

來源 scene 是 `blender/school_v3.blend`，SHA
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
scale 0.0247 m/BU。Locked Python 3.12.12；Blender 5.2.1 LTS 位於
`/Applications/Blender.app/Contents/MacOS/Blender`。本地已備妥 `.venv` 與 physical evidence：

```sh
cd /private/tmp/amidst-phase1-finalization
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/phase1/finalization-sprint
UV_CACHE_DIR=/private/tmp/amidst-finalization-uv-cache uv run --offline --no-sync python --version
```

## 尚未完成的原因與實作順序

1. **新 union 尚未接進既有資料流程。** Office exporter 仍綁定原 receipt/input lock，
   `reviewed_pipeline` 仍載入 office authority，報表/Rerun 仍宣告 office rectangle。
   新增 scoped export/infer/evaluate/reproduction adapters，接回既有 deterministic modules，
   同時保留舊 office producer bytes。不能把新 application 目錄直接傳給舊 office CLI。
2. **同鏡頭 recovery 沒有 adapter。** `CameraTransition` 拒絕 self-transition；原 Graph
   沿 camera transitions 展開。實作 source-bound same-camera HOLD consumer；不造 camera
   aliases 或不存在的 CAM01 handoff。V7 sample39 的實際 recovery 必須保留，兩段 GAP 分開。
3. **現有 route proof 只有 lower bound。** 建立 source-canonical directed graph、exact
   cell/geometry mapping 與獨立 exhaustive inventory，使用實際相同 length、speed、detour、
   camera masks。原 Graph 允許 repeated edge sequences；simple-cell DFS 不能取代 exhaustive
   proof。Topological equivalence 也不保證 metric eligibility。完成前 recall N/A/readiness=false。
   原 Case2 protocol 另要求 `PORTALS_WITH_TWO_SIDED_ACCESS`；先核對既有 approved
   portal/anchor 證據是否涵蓋所選端點與路徑。新 corridor receipt 未授予 portal role，
   HOLD／兩條 winding classes 不能代替這項 gate。此為待 audit 條件，尚未判定須新增核准。
   Fresh 5 Hz run 依實際 visibility 保留 recovery，不強套歷史 V7 sample index。
4. **新的正式 run 尚未產生。** 先完成 GT-free case inventory/readiness，固定新版本 config
   和全部 source/approval/certificate/camera/clock/seed/budget pins，再 fresh 5 Hz export。
   原 V1–V3 configs/locks、29 inputs、57 original frames 保留，不回寫歷史結果。
5. **三項交付要共同重現。** 新 run 執行原 A/B/C、K=[1,2,3] 與必要 single-factor ablations；
   primary inference freeze 後才讀 GT/reference 做 independent evaluation，再產生報表與 demo。
   完成 repeat/fresh-process/order/GT-recipe-annotation poison/termination，以及 clean-checkout
   materialization → export → inference → evaluation → full delivery comparison。

## 三項交付的驗收

| 交付 | 可檢查的完成證據 |
| --- | --- |
| 可重現 dataset | 版本、manifest/package hashes、source/config/authority lineage、5 Hz source observations、獨立 GT/MOVING-DWELL partition、fresh output 重建命令與 comparison receipt |
| Benchmark 結果表 | 同一 dataset 的 Case1–3 × A/B/C × K JSON/CSV/Markdown 與必要消融；原 accuracy/Coverage/recall/physical/projection/search/termination metrics；failed/BLOCKED/N/A 原因保留，不補值或跨 Case 偷換 population |
| Rerun 3D demo | 同一 run 的來源校準、核准 geometry/body scope、observations、inferred candidates/timings；RRD、static PNG、reader/replay receipt 與使用說明；primary GT=false，GT 只在獨立 evaluation/debug partition |

完整正式範圍與驗收仍依原 [post-approval Exit Gates](PHASE1_POST_APPROVAL_HANDOFF.md#最終交付與-exit-gate)
與 [benchmark protocol](PHASE1_BENCHMARK_PROTOCOL.md)。三項展示不取代原 full Exit Gate；只有原
全部 gates 通過才建立 Phase1 validated/frozen checkpoint。每個 milestone 驗證後獨立
commit，沿既有授權普通 push sprint branch，不 merge main。

## 可重用的既有證據

最新 office 局部成果在 `data/finalization/reviewed_run_v7_collision/`：
`evaluation/benchmark_table.{json,csv,md}`、`evaluation/ablations/benchmark_table.*`、
`evaluation/demos/case1|case3/reviewed.rrd` 與 `preview.png`。已有18 evaluated baseline rows
和9 Case2 BLOCKED rows；45 ablation rows 有30 evaluated、15 Case2 BLOCKED。這些可作
已有能力的重現與視覺範例，不能標成新 corridor/完整 Cases1–3 結果。

乾淨 `8cb0df3` 的完整 collision delivery comparison 見 [V4 receipt](../data/finalization/reviewed_checkpoint_v4/manifest.json)；
verified output 是 `/private/tmp/amidst-collision-fresh-v7-8cb0df3`。
Fresh clone 內早期錯誤版本 export 保留且排除，不能因 manifest 相同拿來替代。
`d8b94a6` 的1978 tests／zero skips、Ruff/mypy 是歷史 code validation，見
[精確 receipt](../data/finalization/reviewed_branch_scope_review_v2/code_validation.json)。
本次新增批准與數值重建的實際證據另存 current checkpoint，不冒充新 full-suite run。

Fresh checkout 的 immutable evidence/input materialization 指令見
[reproduction prerequisites](PHASE1_REVIEWED_REPRODUCTION.md#clean-checkout-prerequisites)。
舊 office export 命令只適用其原 application；新 scope 必須先完成上述 adapters。
已完成／歷史紀錄見 [WORK_LOG](WORK_LOG.md)，持續規則見 [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md)。

## English

The human explicitly approved the exact corridor proposal and requests a new conversation
to finish one reproducible dataset, benchmark table and Rerun 3D demo tied to one frozen run.
Read the current checkpoint for actual application/regeneration status. Original HR01–HR04,
reference movement policy and this exact proposal require no repeated approval questions.
Continue in the sprint worktree. Integrate additive scoped pipeline adapters, source-bound
same-camera HOLD, and an independent exhaustive inventory under unchanged actual eligibility;
the old office CLI cannot directly consume the new union application. Freeze the new config
before fresh 5 Hz export, freeze inference before independent evaluation, then reproduce the
complete delivery in a clean checkout. Preserve historical bytes and sample39 recovery.
Existing office results demonstrate partial capability; Case2/Case3-growth and original full
Exit remain incomplete. Case4 stays deferred and Phase2 frozen.
