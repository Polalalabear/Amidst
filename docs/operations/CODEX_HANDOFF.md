# Current handoff / 目前工作交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

日期：2026-10-08。重用 checkout：`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`。
目前工程 branch 為 `codex/simulation-engineering`；文件整理基線 `codex/docs-agent-handoff / 2c586b1` 已包含在其中。研究基線仍是
`phase1/finalization-sprint / 883204af854bed301506b39d63ccb33312b79ff2`，HEAD／origin 以實際 Git 為準。Canonical checkout
`/Users/polalabear/Developer/amidst` 在另一個 physical branch，只供應 immutable scene/raw
artifacts，不在那裡實作或切換 branch。

### 新工程範圍與入口

使用者要求先準備 Agent 操作檢索系統的資源與角色：固定 TaskContext、LocationRegistry、typed tools、summary/detail/media/replay references 與輸出邊界，避免 Agent 掃描整個資料庫或 repository。本階段 **SYNTHETIC_ENGINEERING_ONLY / NO_EXTERNAL_MODEL_CALLS**；OpenAI API 接線與 token 兜底演算法保留空章節，不自行填入。

入口見 [Agent 檢索契約](../engineering/AGENT_RETRIEVAL_BOUNDARY.md) 與 [擴大工程續作 prompt](PHASE1_NEXT_CHAT_PROMPT.md)。可在同一 checkout 連續完成多個可執行 milestones，每段驗證、commit、普通 push 對應工程 branch；不為每段新增 worktree/clone/raw 副本。文件分類見 [導覽](../README.md)；正文按分類存放；必要的機器路徑與不可變核准文件見該頁說明。

工程閉環與原正式研究驗收並行。下方既有 corridor／formal blockers 保持有效。

### 本機 Phase 2 產品續作

最新使用者決策：**frontend/workbench／8016 為唯一主要網頁入口**；既有與後續頁面能力
都接入該工作台。frontend/product／8020 保留為已驗證工程lab／待遷移來源，勿繼續擴張
另一套主要前端。Product後端／資料／typed tools可供工作台adapter使用；目前未完成遷移，
不可把兩個獨立入口說成已統一。工作台相關規則／決策由並行工作階段另行更新。

P7–P12 在同一工程分支接成可操作的 [本機產品](../engineering/LOCAL_PHASE2_PRODUCT.md)：
SQLite immutable read model、RGB-crop appearance／provisional same-camera stitching、有限
中英 intent→typed dynamic plans、多目標 inquiry／衝突與全部替代、四鏡頭影片／Three.js／
soft-sync timeline、持久案例／stop-resume／報告／独立 operator review／HTML export。
新 `product.run.v1` 以 source/dataset/config/producer/registry/media/algorithm/freeze hashes
核對；GET／reload 不重跑推論、不讀 GT。原 M1–M6、E1 canonical IDs/fields/order 及素材保留。

操作：`uv run --offline --no-sync python -m amidst.product serve --output data/product/local_run/operator_v2 --port 8020`，
瀏覽 `http://127.0.0.1:8020`；依賴、build/demo/evaluate/HTTP驗證與新的 empty output 重現命令見產品指南。
原 RGB source/CV 2.5Hz，15fps MP4 只重用實際影格；不是新增15Hz照片／observation。
Agent 的13tools與operator views均受 server-bound scope/stage守門，無任意SQL／shell／archives。

當次 **2592 tests PASS／0 failed／0 skipped**（required physical evidence、明確排除並行
tests/workbench）；Ruff PASS、strict mypy159files PASS。前端13Node tests／actualbrowser、
初次77＋process restart後69真HTTP PASS；新empty output11份fixed documents逐byte一致、
4public query pairs相同。見 [validation](../../data/product/checkpoint_20261008/validation.json)。
2592/159不包含正在獨立開發的workbench；其驗證與文件由該工作階段另存，不混入本次PASS。
並行雙角色／場景切換／人審版本的 [共用工作台](../engineering/SHARED_WORKBENCH.md) 使用8016，
其獨立 [desktop receipt](../../data/engineering/workbench_20261008/desktop_validation.json)
與當次product測試相互排除，未把兩份PASS相加為新的full結果。
最後共享branch另做無排除的實際full整合：**2652passed／0fail／0error／0skip，255.995s**，
Ruff／mypy164files及兩前端28Node PASS。新增product test package namespace修正同名
test_service collection failure；原失敗log保留。此新full結果不來自兩份局部PASS相加。

五個 eligible pure-track appearance queries 的Recall@1/3/5=.4/.6/.8（同pool baseline=.2/.6/.8）；
六個mixedtracks排除、stitch TP1/FP2、四組unknown保留，global IDF1 N/A。這是有限synthetic
diagnostic。Full formal／新school攝影機／trainedReID／PostgreSQL或vector部署／external model
仍未交付，原Cases2/3/fullExit BLOCKED、Case4 DEFERRED、原Phase2 branch/tag FROZEN。

### 局部跨鏡頭與行為研究續作

[局部 pilot](../engineering/LOCAL_CAMERA_PILOT.md) 已依 [R1–R8 交接](LOCAL_CAMERA_EVENT_RESEARCH_HANDOFF.md) 完成可操作的 E1 synthetic extension；[protocol](../research/LOCAL_CAMERA_EVENT_PROTOCOL.md) 與 [curated receipt](../../data/engineering/local_camera_20261008/validation.json) 固定scope、版本、同run hashes及當次驗證。原 M1–M6 registry／RGB tracks／provisional v1／simulation-v2 不變，新 `local_association` 與 `local_behavior` 是外層版本化composition，不改原BoundGapEvent／Graph排序。

目前 `local-camera-test-v1` checkpoint：4 cameras／244 pinhole RGB／150 measurements／18 local tracks；真正scope/ref／camera-time／region/portal index在形成pairs前沿可達拓樸擴查。115 local pairs對照153 global diagnostic pairs，獨立條件式next-segment reference 8/8取回；不是未檢出人物的整段recall。Pair precision/recall 0.35/0.467；轉角／可能遊蕩仍有誤報，進出門在bounded identity評估仍未定。完整feature消融、混淆／缺失與限制見receipt；不宣稱唯一人物身分或行為意圖。

可直接開啟loopback8012（原8010保留）查局部camera/time事件卡、3–5實際RGB、局部3D候選與replay；操作／重建命令見pilot文件。Final artifacts位於ignored `data/engineering/local_run/local_camera_v1/test/checkpoints/final`，同一RGB materialization被development/test各自新freeze重用。2427 full tests／Ruff／mypy145files、34真HTTP、378MockAgent calls、瀏覽器操作、同run GT poisoning與empty-output hash reproduction當次PASS；formal clean-checkout與school authority未因此解鎖。

有效後續：以development改善pixel merges/ID switches、appearance與soft priors／可見行為precision，再用新frozen run评估；原Cases2/3、full Exit BLOCKED、Case4 DEFERRED及frozenPhase2繼續有效。原研究交接的NOT_RUN標頭是交接日期基線，實作狀態以本節與pilot checkpoint為準。

### 已接入的工程能力與續作邊界

`codex/phase1-preview-workspace / 04c699d` 已以 merge commit `ded5572` 接入目前工程分支；50 frames／58 verified images 的 view-only playback 可由原 exact inputs 重建。Projection branch `8f4055f` 的四個 model helpers 已在研究基底中；本次僅補相容的 comparison／surface-control／downstream／robustness 診斷工具，保留 sidecars，不改 Graph 權重或 domain schema。

FROZEN Phase 2 checkpoint `5b51d2c` 的 repository、read-only API、legacy replay importer 與 TypeScript consumer 已選擇性接入。使用 [Phase 2 整合](../engineering/PHASE2_INTEGRATION.md) 的本機啟動命令與 [本次驗證 receipt](../../data/engineering/integration_20261008/compatibility.json)。這是 SYNTHETIC_MOCK_ONLY 接口：GET 讀固定 snapshot、保留 canonical observation/event IDs 與候選順序，不重跑 inference。

工程基底 `4271b2b` 的完整測試 **2255 passed／0 failed／0 skipped**，含 Blender／physical evidence；Ruff PASS，strict mypy PASS（125 source files）。該checkpoint的25次實際loopback HTTP requests與Node consumer／replay驗證通過，既有318個核心／腳本／測試檔、29 inputs、297 review records及immutable source不變；這不是後續M1/M2或目前草稿的全測試重跑。

M1–M6 已實作：source/context/clock/unit registry／media、真實未標註 RGB 與 pixel local tracks、兩種輸入與 stage/freeze 守門、provisional associations／Graph adapter、八個 strict typed Agent tools、MEMORY／LOCAL_JSON fixed reads、MockAgent／互動照片與3D alternatives replay、independent evaluation／reproduction。操作與完整界限見 [模擬工程](../engineering/SIMULATION_ENGINEERING.md)，本輪 [validation receipt](../../data/engineering/simulation_20261008/validation.json) 綁定 source hashes／run／config。

當次2351 tests PASS／0 failed／0 skipped（required physical evidence），Ruff／strict mypy138 files PASS，36真HTTP及4events／12TypeScript replay PASS；只排除並行local research草稿，詳見receipt。

目前 local run `data/engineering/local_run/simulation_v2`：2 cameras／102張5Hz RGB、89量測／6tracks、21association records、4canonical gaps／8routes。使用既有環境執行 `uv run --offline --no-sync python -m amidst.engineering serve --run data/engineering/local_run/simulation_v2 --port 8010`；瀏覽 `http://127.0.0.1:8010`。完整GT只在simulation/export與local evaluation/debug；photo入口只有獨立synthetic-lab-v1，沒有虛構school RGB tracking sequence。Office importer certificate僅為structured recovery partial，native BU不回寫，0.0247 m/BU顯式normalize。

Pixel recall為83/129（64.34%，24px eligibility matching），mean contact error3.09px／ground error0.102m；這些是獨立fixture診斷，association identity accuracy及formal指標N/A。Same-camera為HOLD，overlap不偽造gap，全部歧義／incompatible alternatives均保留。兩模式使用相同照片，photos-only從pixels重算；未使用GT兜底或external model。

原 `phase2/integration-hardening` 與 tag 保持 FROZEN；新增碼只在工程分支。不 merge `main`，不改原 Blender/source、locked inputs 或正式研究狀態；外部模型 API 與 token 兜底章節仍空白。

### 恢復 checkpoint 的既有證據

以下是 `883204a` 所記錄的 runtime 恢復工作；本次工程整合的測試另見上方 receipt，不與恢復紀錄混用。
該恢復工作因舊 `/private/tmp` worktree 與 raw outputs 已不存在，從已發布
`5c2b67b9c48ae4028fd9fb2e7636f6b3af5121c0` 恢復到上述持久路徑。
使用 locked Python 3.12.12；29 個原鎖定輸入與297份 review package 檔案均驗證，
physical evidence 為 VERIFIED。完整測試 **1978 passed／0 failed／0 skipped**，
Ruff、mypy 與 source CLI strict mypy 全 PASS。執行指令見 [恢復後運行指南](PHASE1_RESTORED_RUNTIME.md)，
該恢復工作的實際檢查見 [recovery receipt](../../data/finalization/recovery_checkpoint_20261008/validation.json)。
新的 office 5 Hz export → V3 inference freeze → evaluation → ready-case reproduction
已實際完成；27列 baseline、45列 ablation、兩個 reader-verified RRD／PNG 在
`data/finalization/reviewed_run_recovery_20261008/`。這是既有核准 office 流程的重新運行，
新 corridor 全案例研究交付仍待下列工程。原 source/核准/config/producer bytes 保留。
歷史 V3–V8 bulk raw 與舊獨立 `/tmp` 輸出目前不存在；Git 中 curated receipts 仍在。

使用者已核准精確 corridor proposal，要求準備新對話，完成一個可重現 dataset、
一份 benchmark 結果表、一個 Rerun 3D demo，綁定同一 frozen run。直接使用
[下一對話 prompt](PHASE1_NEXT_CHAT_PROMPT.md)；完整實作起點、原因／解法與交付驗收見
[研究成果續作交接](PHASE1_RESEARCH_RELEASE_HANDOFF.md)。

原 HR01–HR04 4/4 APPROVE 且 applied；獨立 reference MOVING/departure-DWELL policy
已核准並在既有 office run 中使用。新 corridor proposal content SHA
`7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad` 已直接人工核准，
[receipt](../../data/finalization/reviewed_corridor_scope_approval_v1/human_decision.json) content SHA
`702c2f7ca8165fc7669072847e26f38174b6525ed104999e35b467d23cebda09`。
六個 cells 原數值 application 全通過，完整 union certificate SHA
`f8fe588620b4f871d49f6ed50d61d6185c8648b5551d9b7528dfb7c696cb06c5`。
Historical independent clean `d8b94a6` regeneration **PASS_LOCAL_UNION_REGENERATED**；
該恢復工作再執行原完整數值重建亦通過；原 hashes 見
[current checkpoint](../../data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json)。
不重問既有核准；歷史 review/strict-preview/V5 packet 保留原 bytes。

Phase1 仍 **PHASE1_FINALIZATION_BLOCKED / PARTIAL_APPROVED**。Case2／Case3 detour-growth
尚缺 scoped pipeline adapters、source-bound same-camera HOLD、相同 actual eligibility 的
canonical directed graph 與獨立 exhaustive inventory、新版本 config freeze、fresh 5 Hz
export/inference/evaluation/benchmark/demo、完整 clean-checkout reproduction。
舊 office CLI 不能直接消費新 union application。原 Graph 允許 repeated edge sequences、
CameraTransition 拒絕 self-transition；不能用 simple-cell DFS 冒充 exhaustive 或假造
CAM01 handoff。Lower-bound proof 的 recall N/A/readiness=false；V7 sample39 的真實 recovery
與兩段分開 GAP 必須保留。
原 Case2 `PORTALS_WITH_TWO_SIDED_ACCESS` 仍須查核既有 approved portal/anchor 證據；
新 corridor receipt 不新增 portal role，不能由 HOLD／分支數代替此 gate。

恢復 checkpoint 的 fresh office 局部成果：Case1／Case3 temporal A/B/C、27列 baseline、45列
ablation、RRD/PNG 與 ready-case reproduction；Case2 BLOCKED rows 保留。
[Collision V4 fresh receipt](../../data/finalization/reviewed_checkpoint_v4/manifest.json) 僅證明
`8cb0df3` 的既有 delivery。Source preparation `d8b94a6` 的1978 tests／zero skips、Ruff/mypy
是歷史 code validation；恢復工作重新運行的測試、資料流程與數值重建另存 recovery receipt。

完成／歷史證據見 [WORK_LOG](../history/WORK_LOG.md)、[final report](../research/PHASE1_FINAL_REPORT.md)；
持續規則只留在 [DEVELOPMENT_RULES](../specs/DEVELOPMENT_RULES.md)。原29 inputs／57 frames、
HR／reference policy／protocol／V1–V3 locks、source asset 全部保留。
Case4 **DEFERRED**；Phase2 `phase2/integration-hardening / 5b51d2c` **FROZEN**。
原 full Exit Gates 全過才 freeze，不 merge main。

## English

The current engineering branch is `codex/simulation-engineering`, reusing the existing checkout and including documentation checkpoint `2c586b1`; the research baseline remains `phase1/finalization-sprint / 883204a`. Preview checkpoint `04c699d` was merged as `ded5572`. Compatible projection diagnostics and the frozen `5b51d2c` mock repository/API/replay/TypeScript adapters were imported selectively, preserving current core contracts and dependencies. See the integration document and current receipt above. This is **SYNTHETIC_ENGINEERING_ONLY / NO_EXTERNAL_MODEL_CALLS**; API wiring and the token fallback algorithm remain empty.

M1–M6 now provide an operating synthetic RGB-to-local-track-to-provisional-association-to-3D-event composition, strict typed tools, immutable repositories, a browser/MockAgent workflow and independent evaluation/reproduction. See the simulation engineering document and current validation receipt. The local run has 102 images, 89 measurements, six tracks, 21 association records and four canonical gaps with eight alternatives. The separate office certificate covers structured partial recovery only; school RGB, arbitrary corridor packages and formal gates remain uncertified.

R1–R8 now provides an operating, separately versioned indexed synthetic pilot. See the local pilot guide and curated receipt for current metrics, 2427 full passing tests and scoped photo/3D/replay operation. Low pair accuracy and behavior false positives remain explicit; the original lab, formal gates, main and frozen Phase 2 are preserved.

P7–P12 now provide an operating [local synthetic Phase 2 product](../engineering/LOCAL_PHASE2_PRODUCT.md):
durable scoped SQLite retrieval, handcrafted pixel appearance, provisional stitching, bounded
intent-driven multi-subject plans, four-camera video/Three.js playback, saved cases, independent
reviews and exported reports. The current 2592-test regression, lint, 159-file types, 13 frontend
tests, 146 actual HTTP calls including process restart, browser operation and identical fresh-output
reproduction have separate source/run-bound receipts. Concurrent workbench validation is excluded.
Small conditional appearance/stitch populations and failures remain explicit. Original formal
research, production/live capabilities, source assets and frozen branches are not promoted.

The latest human decision selects frontend/workbench/8016 as the unified primary web UI.
Preserve product/8020 as an engineering lab/migration source and integrate existing/future
page capabilities into workbench. Backend adapters can use the product interfaces; the UI
migration is not yet complete. Do not describe the independent entries as already unified.
A subsequent actual full run with no exclusions passes 2652 tests in255.995s, with zero
failures/errors/skips; lint, 164-file types and28 frontend tests pass. The product test
package namespace fixes a collection collision; prior failed collection evidence is retained.

Continue in the sprint worktree above. The human approved the exact corridor proposal and
requests a new-chat continuation to finish one reproducible dataset, benchmark table and
Rerun 3D demo tied to one frozen run. Use the linked prompt and release handoff.
Original HR01–HR04 and the independent reference movement policy are approved and applied;
the new exact scope has a direct-human receipt and six passing numerical cell certificates.
Independent clean-checkout regeneration passes; read the current checkpoint for precise hashes. Do not repeat
approval questions or rewrite historical review/preview packets.
Case2 and Case3 detour-growth remain blocked pending additive scoped pipeline adapters,
source-bound same-camera HOLD, unchanged-eligibility independent exhaustive inventory,
new config freeze, fresh 5 Hz execution and complete delivery reproduction. The old office
CLI cannot consume the new union directly. Preserve repeated-edge graph semantics and the
actual sample39 recovery; lower-bound proofs do not establish recall/readiness.
Audit the original Case2 two-sided-portal requirement against existing approved evidence;
the new corridor receipt grants no portal role.
The earlier `883204a` recovery checkpoint reran the existing office dataset/inference/evaluation;
the current integration checks have their own receipt. That recovery checkpoint includes
reader-verified demos, ready-case reproduction and corridor numerical verification. Read the
recovery receipt and runtime guide for current results; old temporary bulk outputs are absent.
This does not complete the new corridor release. Case4 stays deferred, Phase2
frozen, and a Phase1 freeze requires every original full Exit Gate.
