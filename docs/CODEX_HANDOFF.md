# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

狀態日期：2026-10-08。Branch：`phase1/finalization-sprint`。
**實作 worktree：`/private/tmp/amidst-phase1-finalization`**；canonical checkout
`/Users/polalabear/Developer/amidst` 在另一個 physical branch，只供應 scene/raw artifacts。
不要在 canonical checkout 實作或切換它的 branch。

目前 preparatory scope milestone／publication commit 由 branch tip 取得；collision source 是
`8cb0df3f2a530306e77e730f1a6395e824085e80`；
`e6fbc8fbb3bf8c36355db38c299de5ff37705604` 是歷史 V5 source checkpoint。
原 handoff `62ea9b1` 與 approval `10a3fcc` 是歷史
入口，保留原 hashes，不重新套原人工問題。完整現況見
[final report](PHASE1_FINAL_REPORT.md)、[reviewed benchmark](PHASE1_REVIEWED_BENCHMARK.md)，
重建指令見 [reviewed reproduction](PHASE1_REVIEWED_REPRODUCTION.md)。

原 office 人工 gate **4/4 APPROVE、0 original human blockers**；[approval summary](../human_review/APPROVALS.md)
與 [decisions.json](../human_review/decisions.json) 已提交並 **applied**；bounded office
certificate **PASS**。原問題／profiles／payload、29 inputs、57 original frames 不變。
新增 reference movement policy 已另行明確核准／lock／fresh export／evaluation，不重問
原 HR01–HR04。Phase 1 **PHASE1_FINALIZATION_BLOCKED**；overall **PARTIAL_APPROVED**。

已完成 additive reviewed adapters、GT-free V2 config lock、canonical fresh local
歷史 `data/finalization/reviewed_run_v5/`：Case1／Case3 temporal component 的 A/B/C、27-row
K matrix（9 Case2 N/A）、20 charts、2 RRD+PNG、independent metrics/reference annotations。
Ready Case1/3 的 repeat／fresh-process／ordering／GT/recipe/annotation poison／termination
PASS。完整 source suite **1859 passed、0 skipped**，Ruff／strict mypy PASS。
Fresh checkout 位於 `/private/tmp/amidst-phase1-finalization-fresh-20261007`；物理重建、
同 hash application／dataset、198 code/config/lock files 與 final full delivery comparison
均 PASS；[最終 receipt](../data/finalization/reviewed_checkpoint_v2/fresh_delivery_comparison_final.json)
保留 41 JSON／1 CSV／4 MD／21 non-runtime PNG／2 reader-verified RRD 的核對。

Current V7 collision milestone 使用原25 APPROVED known-collision scopes／58 nonempty
colliders；coverage仍PARTIAL，未新增語意批准。C與可執行 `remove_collision` 保留完整
office domain/body guard與獨立評估；readyCase1/3的 repeat/fresh-process/order/GT-recipe-
annotation poison/termination PASS。另有45列ablation table（30 EVALUATED、15 Case2 BLOCKED）
和17張圖，沒有測到candidate/accuracy差異。見 [collision checkpoint](PHASE1_COLLISION_CONSUMER_CHECKPOINT.md)
及 [curated manifest](../data/finalization/reviewed_checkpoint_v3/manifest.json)。
獨立乾淨 `8cb0df3` checkout 的 V7 collision delivery 已完整比對 PASS：46 JSON、2 CSV、
6 Markdown、37 non-runtime PNG、2 reader-verified RRD；26 protected producers 相同。
精確 receipt 見 [v4 manifest](../data/finalization/reviewed_checkpoint_v4/manifest.json)。

新局部 scope 的 source-only discovery、bounded source/semantic/camera proposal、multi-profile
numerical certifier、連續 union provider、independent route-class lower-bound 已實作。
原 single-profile producers／HR01–HR04／source／protocol 保持 bytes；新 wrapper 支援每 cell
1+ components、空 zero-area list，保留全部 receipts，仍拒絕實際 body collision 與未核准 components。
union coverage 使用 exact rational intervals，不能填 hole 或極小未批准縫隙。

目前新人工 gate 是 [corridor review](PHASE1_CORRIDOR_SCOPE_REVIEW.md) 的精確 proposal：
content SHA `7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad`。
六個 cells、28 support faces、1 obstacle source face（native triangles 0/1）、兩個來源
camera/landmark bindings；`group_0` bounded no-solid interior 在六個 guards、`group_0.003`
只在 cells 2/3/4。不請求 zero-area 豁免。Authority **HUMAN_REVIEW**；尚無新 receipt。
原 strict preview 六個 cells 都 REVIEW unknown closed-volume geometry，certificate null。
V7 actual source visibility 有兩個分開的 GAP，sample 39 的短暫 visible recovery 必須保留。
V8 departure 被來源 geometry 遮擋，保留為被排除診斷；不繼續放寬 geometry/camera 搜索。

Case2／Case3 detour-growth 仍 BLOCKED。新核准不能直接使 readiness 通過；後續仍需：
apply/verify 每個原數值 proof；source-bound same-camera HOLD adapter；在相同 length、speed、
detour、camera masks 下建立 canonical directed graph 與獨立 exhaustive inventory；simulation
前固定新 config；fresh 5 Hz export/inference/evaluation/reproduction。原 graph 允許重複
edge sequence，而 CameraTransition 拒絕 self-transition，不能拿 simple-cell DFS 當 exhaustive
或假造 CAM01 handoff。現有 class proof 只給 lower bound，recall N/A、readiness=false。
舊 [scope readiness](PHASE1_BRANCH_SCOPE_GATE.md) 是先前 58-component／116-bypass 失敗
audit 的歷史結果；新 review 取代其「proposal unavailable」作為目前續作入口。
不要擴原 office guard、把平行偏移／timings 算 branching、修改 source 或升格未知 WALL/portal/stair。
原 full Exit Gate 未通過，不建 freeze tag。
Collision ablation 已由 V7 purpose-bound consumer 執行；partial known-collision coverage
不升格完整學校碰撞／free-space authority。

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
All four original approvals are applied and bounded numerical certification passes. Fresh
formal local Case1/Case3-temporal A/B/C, approved independent moving-time reference metrics,
reports/demos and scoped poison/determinism checks are complete. Read the current report,
benchmark and reproduction links above. Historical V5 source checkpoint `e6fbc8f` passed
1859 tests without skips. Current V7 implements purpose-bound collision ablation, freezes exact
V3 lock bytes and passes ready-case reproduction, with 45 ablation rows and 17 charts.
The new collision code/checks are bound by the curated V3 validation receipt.
The independent clean `8cb0df3` checkout reproduces the collision delivery; the V4 receipt
records 46 JSON, 2 CSV, 6 Markdown, 37 non-runtime PNGs and two verified-reader RRDs.
New source-only discovery, exact bounded proposals, 1+ component semantic wrappers, rational
continuous-union coverage and an independent route-class lower-bound are implemented.
The concrete corridor proposal linked above requires a new direct-human decision: six cells,
28 support faces, one obstacle source face, bounded component interior and two source-camera/
landmark bindings, with no zero-area exemptions. Strict preview remains REVIEW without a
certificate. Its V7 visibility preserves sample 39 as a real recovery between separate gaps;
V8 is rejected source-occlusion evidence.
After approval, original numerical regeneration, a same-camera HOLD adapter, metric-preserving
canonical graph/exhaustive inventory, frozen new config and fresh 5 Hz formal execution remain.
The existing graph permits repeated edge sequences and rejects self-camera transitions; a
simple-cell DFS is insufficient and an invented camera handoff is forbidden. Lower-bound
proofs retain N/A recall and false readiness. Keep Case2/Case3-growth blocked,
the original receipts/protocol/source immutable, raw versions preserved, Case4 deferred and
Phase2 frozen. No freeze tag or main merge is authorized by scoped passes.
