# Phase 1 下一個對話續作 prompt

直接複製以下內容到新對話：

```text
請繼續完成 Amidst Phase 1 第一版可展示、可驗證的研究成果：一個可重現 dataset、一份 benchmark 結果表、一個 Rerun 3D 視覺化 demo，三者必須綁定同一份 frozen dataset/config/run。

實作 worktree 是 /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization，branch 是 phase1/finalization-sprint。先確認 pwd、git status、HEAD 與 origin，再讀 docs/DEVELOPMENT_RULES.md、docs/CODEX_HANDOFF.md、docs/PHASE1_RESEARCH_RELEASE_HANDOFF.md、docs/PHASE1_RESTORED_RUNTIME.md、data/finalization/recovery_checkpoint_20261008/validation.json 和 data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json。canonical checkout /Users/polalabear/Developer/amidst 只供應 immutable Blender scene 與原 raw artifacts，不在那裡實作或切換 branch。

2026-10-08 已從發布的5c2b67b恢復至持久worktree，完整pytest1978passed／0failed／0skip、Ruff/mypy PASS；完成locked environment、29輸入與297 review package驗證、physical evidence驗證、既有office fresh 5 Hz export/inference/evaluation/ready-case reproduction與兩個reader-verified Rerun demos。新輸出在 data/finalization/reviewed_run_recovery_20261008；此為office能力重新驗證，不等同新corridor全案例Exit。原/tmp worktrees與歷史V3–V8 bulk raw已不存在，curated receipts仍在；需要時依runtime指南從原exact inputs重建，不引用不存在的raw作當前證據。

原 HR01–HR04、獨立 reference MOVING/departure-DWELL policy，以及 exact corridor proposal 7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad 均已明確核准；依 checkpoint 的 application/verification 結果續作，不重問既有核准。保留原數值證明與所有研究條件，inference 不讀 GT、recipe 或 reference annotations。

從 additive scoped export/infer/evaluate/reproduction adapters、source-bound same-camera HOLD 與相同 eligibility 下的獨立 exhaustive route inventory 開始，接回原 Graph/reconstructor/masks。舊 office CLI 不能直接接入新 union application。既有 route-class proof 只是 lower bound；不能用 simple-cell DFS 冒充 exhaustive，也不能假造 CAM01 handoff。先完成 GT-free case readiness（含原 Case2 PORTALS_WITH_TWO_SIDED_ACCESS 的既有 approved portal/anchor evidence audit）與新版本 config lock，再 fresh 5 Hz export → inference freeze → independent evaluation → benchmark/Rerun → fresh-checkout reproduction。

完成每個可執行 milestone 的相稱驗證、獨立 commit 與已授權的普通 push；保留所有歷史版本。交付可重建命令、manifest/hashes、Case1–3 × A/B/C × K 結果與必要消融、RRD/PNG/reader replay 證據。Case2 和 Case3 detour-growth 未通過前保持 BLOCKED；原 full Exit Gates 全過才 freeze。Case4 DEFERRED、Phase2 FROZEN，不 merge main、不改 Blender source、不擴大任何已核准 scope。直接開始實作並持續到上述交付完成。
```
