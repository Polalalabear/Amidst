# Work log / 已完成工作紀錄

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

### 2026-10-08 — View-only synchronized preview workspace

從已發佈 `883204af854bed301506b39d63ccb33312b79ff2` 建立隔離 branch
`codex/phase1-preview-workspace`，新增 `human_review/playback/`。四格同屏呈現人物動畫、
固定拓樸與 P(t)、source 模型／相機射線、側視人物高度；共用播放列、逐格、速度、
循環、單格放大與全螢幕。非同步載圖完成後一起更新，過期請求不能覆蓋新影格。
相機 4／5／9 秒 still 另列明確時間，不當作當前連續影格。

目前狀態讀取八份 pinned checkpoint receipts，清楚顯示 4/4 決策已套用、Case1
局部完成、Case2 blocked、Case3 僅時間分量完成，以及 PARTIAL_APPROVED／尚未 freeze。
歷史 50 格診斷素材、舊 pending 標籤、原頁面與 decisions 保留原 bytes。未進行新審查、
authority application、source 修改、render、GT／formal inference 或 benchmark。

新 builder 驗證四份 display manifests 與 58 張原圖的 SHA256／大小；資料 deterministic
生成為 local ignored `data.js`，small build/status manifests 入 Git。舊頁面其他 129 張
ignored 圖片由原保存套件補回並逐檔比對，未改 tracked historical evidence。
新播放 URL 為 `http://127.0.0.1:8768/playback/`；重建與使用說明見
[playback README](../../human_review/playback/README.md)。

本次實際驗證：12 focused tests PASS；Ruff、兩個新 builder strict mypy、JS syntax、
diff check PASS。原生瀏覽器驗證 1280×720、825×720、390×844 均無頁面捲動，控制列
可見；frame20／30／45 各圖與 marker 使用同一 loaded-frame，放大／返回、播放、
代表 still 與狀態面板可用，console 無 error／warning。先前 1978-test 結果仍是 source
checkpoint 紀錄，本次沒有宣稱重跑完整研究 suite。

English: Added a view-only four-pane player with one shared timeline, atomic frame loading,
focus mode and a bounded current-progress snapshot. Existing research and review evidence
remain unchanged. Twelve focused tests and scoped quality checks passed; desktop/mobile
browser checks confirmed synchronized views with always-accessible playback controls.

### 2026-10-08 — Persistent runtime recovery and actual revalidation

舊 `/private/tmp` sprint/fresh worktrees 與歷史 bulk outputs 目前不存在；Git branch/origin
仍保有5c2b67b。恢復 `phase1/finalization-sprint` 到
`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`，canonical physical
checkout 保持c5956dc及clean。以committed `uv.lock` offline安裝Python3.12.12。
八份原diagnostic/topology JSON由canonical pilot找到並逐檔SHA驗證；四個physical gzip
原檔恢復，14 artifacts全符合original SHA/size。Hydration驗證297 files、187 copied／
110 matching、29 frozen inputs與原review frames保留；未使用new formal inputs取代歷史。

實際執行physical `--verify-only` VERIFIED；完整corridor union原數值重建
PASS_LOCAL_UNION_REGENERATED。新5 Hz office export於
`data/finalization/reviewed_run_recovery_20261008`產生Case1 50timestamps、Case3 925timestamps，
Case2保持BLOCKED。V3 primary inference freeze SHA `add7e625…c4de`、dataset manifest
SHA `a3393f2e…68a5`符合歷史pins。Fresh evaluation產生27列baseline、45列ablation，
兩個RRD與preview PNG；actualreader驗證true、primary GT=false、preview已目視檢查。
Ready-case repeat/fresh-process/order/GT-recipe-annotation poison/termination全部PASS。
沒有產生新的corridor全案例pipeline或第二個clean-checkout complete-delivery comparison。

Ruff、mypy111package files與source CLI strict mypy實際PASS。初次full suite
1977passed／1skip／0fail (208.26s)；skip只因三份原topology prerequisite缺失，找到原檔
並核對SHA後補回，未改測試。補回後full suite實際 **1978passed／0skip／0fail (116.28s)**，結果見
[新validation receipt](../../data/finalization/recovery_checkpoint_20261008/validation.json)。
30 protected producer/config/HR inputs與school-v3 SHA／size／mtime均未變；source未保存。
Case2與Case3 detour-growth、all-case dataset validation、freeze依舊BLOCKED；Case4 DEFERRED，
Phase2 branch/tag仍5b51d2c FROZEN。

更新current handoff／next-chat prompt／runtime/reproduction/release文件到持久可用路徑，
清楚標記已不存在的歷史bulk raw。原approval/checkpoint/preview/protocol保留原bytes。
小型recovery receipts保存本次實際結果；GT/observations/RRD/source.gz保持local ignored。
本地便利入口在canonical `data/pilot/phase1_handoff_20261008/PHASE1_NEXT_CHAT.md`。

English: Restored the published sprint into a persistent checkout, rebuilt the locked
environment and exact inputs, and actually reran physical/corridor verification and the
existing office export/inference/evaluation/reproduction/demos. Current tests are recorded
separately from historical checks. Temporary historical bulk outputs are absent. This
recovery preserves all approvals/source bytes and does not complete the new corridor release.

### 2026-10-08 — Exact corridor approval, numerical regeneration and next-chat checkpoint

使用者直接核准 exact corridor proposal content SHA
`7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad`，並要求準備新對話
完成同一 frozen run 的可重現 dataset、benchmark 表、Rerun 3D demo。另存原始決策原文、
時區時間與 EXACT_PROPOSAL_ONLY receipt；decision content SHA
`702c2f7ca8165fc7669072847e26f38174b6525ed104999e35b467d23cebda09`，未取代原 approvals。
原 pending proposal／strict-preview／V5 packet 與 review document bytes 全保留。

Actual scoped-authority `apply` 重算六個原數值 cells 全通過，status
**APPROVED_LOCAL_PHYSICAL_UNION**，完整 union certificate content SHA
`f8fe588620b4f871d49f6ed50d61d6185c8648b5551d9b7528dfb7c696cb06c5`。
乾淨獨立 `d8b94a6708cfad75d5052f4619ab29b036e10370` checkout actual `verify` 再次重建
全部原數值證明，status **PASS_LOCAL_UNION_REGENERATED**；三個 authority producers bytes
相同，certificate/proposal/decision 使用獨立 pinned content hashes。既有 verified physical
source evidence 重用且驗 hash；本次沒有新 Blender export／simulation／GT／benchmark／RRD。
Source SHA/468300506 bytes/mtime1791198236746106977 未變，30 protected inputs 全匹配。

Curated approval/application/verification 與 machine checkpoint／manifest 保存於
[approved checkpoint](../../data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json)。
本次為實際 authority application/regeneration 與文件／hash/link 驗證；未改程式碼，沒有
重跑 full pytest／Ruff／mypy，1978-test 結果仍明列 historical `d8b94a6` validation。
新 [release handoff](../operations/PHASE1_RESEARCH_RELEASE_HANDOFF.md) 和 [可貼上 prompt](../operations/PHASE1_NEXT_CHAT_PROMPT.md)
提供 continuation 起點、剩餘原因／解法與三項交付驗收；live handoff 縮短，原紀錄保留。

Read-only independent review 確認 old office exporter/pipeline/Rerun 不能直接載入新 union，
需 additive scoped adapters、same-camera HOLD、相同 actual eligibility 的獨立 exhaustive
inventory、config 先鎖定再 fresh5Hz run。另列原 Case2 two-sided portal/anchor evidence
requirement 待 audit；新 approval 不授予 portal role，尚未判定須新增人工 gate。
Case2／Case3 growth 和 full Exit 保持 BLOCKED；Case4 DEFERRED，Phase2仍5b51d2c FROZEN。
不改 source、HR/reference/protocol/locks，不建 freeze tag、不 merge main。

### 2026-10-08 — Source-bound scope preparation and exact operation guards

新增 source-only island discovery、scoped authority/CLI、1+ bounded semantic profiles、
intact multi-profile numerical certificate/provider，以及 independent source route-class
lower-bound。沿用原支撐、完整 body atlas、clearance/GJK、enclosure 與數值 budgets；
新 receipt 只處理自身明確 component/guard，actual nondegenerate contacts 與第三個
未核准 component 仍拒絕。Union path coverage 採 exact Fraction intervals，不跨 hole 或
浮點 parameter rounding 下的極小縫隙。外層與內層 public operation 都重驗完整 receipt。
Independent review 發現的 standalone inner receipt mutation 漏口已修正，新增兩個反例。

實際 V7 六個 source cells 的 body-triangle sweep CLEAR、兩個分開的 source GAP 保留
sample39 recovery；V8 departure 真實遮擋不成立，保留原診斷。新 scope request 收窄到
28 support faces、1 obstacle source face（native triangles0/1；triangle0 exact witness）、
6 cells、兩個 source cameras。group_0 六個 guards／group_0.003 cells2/3/4 bounded interior
需新人工 decision；兩者全域零面1456/104都不與任何 guard 相交，沒有提出零面豁免。
原 strict preview 全六個 cells REVIEW unknown closed-volume geometry，certificate null，
未造 APPROVE。Exact proposal content SHA：
`7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad`。
Review packet 共11 files、378986 bytes（bounded coordinates／校準／map／strict preview／
validation／historical receipt）；大 raw geometry、GT、observations、RRD 不入此 packet。

Exact source commit `d8b94a6708cfad75d5052f4619ab29b036e10370` 的獨立 clean checkout
實際 inspect 與 strict preview 重現完成：proposal／preview bytes、10個testedsource/test
files相同；preview保留六個REVIEW和nullcertificate。V5保存6個smallreceipts/files，
既有verifiedphysicalmaterialization重用，沒有宣稱重跑Blender materialization/source
visibility，沒有新批准或formal結果。Document/evidence-only commit接在該source之後。

最終完整 suite **1978 passed、0 skipped、0 failed、112.04s**，從開始即指定 canonical
source 與 `--require-physical-evidence`。Repo Ruff、strict mypy111 source files、source CLI
mypy PASS。Focused authority/inventory/wrapper60 tests PASS。1976-test／113.72s pre-fix
run 依其原 source hashes 保存 historical，不冒充 final。Exact tested source/test hashes
及30 protected bytes核對見 [validation receipt](../../data/finalization/reviewed_branch_scope_review_v2/code_validation.json)。
Original HR01–HR04／protocol／config locks、原 physical producers 與 `.blend` bytes不變；
Phase2 branch/tag仍 `5b51d2c`。New source-only CLI Vec3 cast 是 type-only 修正，歷史
V7 producer hash與raw outputs保留，不宣稱重跑 source visibility。

另完成 collision `8cb0df3` 的獨立乾淨 clone actual export/infer/eval/reproduction與full
delivery comparison：46JSON、2CSV、6MD、37nonruntimePNG、2reader-verifiedRRD一致，26原
protected producers相同；small V4 receipt共3files／17332bytes。初次 fetch/checkout失敗
前產生的舊版本raw export保留並明確排除於fresh proof，不能只以manifest相同升格。

Case2／Case3 detour-growth仍 BLOCKED；new direct-human scope decision尚未收到。後續
工程包括 same-camera HOLD adapter、相同 actual eligibility 的獨立 exhaustive inventory、
新config先freeze再fresh5Hz正式執行。Simple-cellDFS不等同原可重複edge sequence的Graph；
topological nerve proof不保證metric/speed/camera條件。Lower-boundrecall維持N/A；未建
freeze tag，未改main或source。Current續作入口見 [handoff](../operations/CODEX_HANDOFF.md)。

### 2026-10-08 — Purpose-bound collision execution and frozen V3 lineage

新增 reviewed collision bundle，使用原25 APPROVED KNOWN_COLLISION_PRUNING scopes／58非空
source colliders，保留partial coverage與各scope原purpose/source/geometry/resolution/numerics
hashes。每次run/eval入口完整重驗，僅在單次操作重用consumer；mutation在下次入口拒絕。
A/B/C與 `remove_collision` 共用原graph/reconstructor/masks；該消融只停額外filter，完整
office domain/body guard與獨立physical evaluator保留。V3保留原V2 bytes，精確lock artifact
與binding/receipt一同凍結並於evaluation重驗；原HR/protocol/scene/input locks不變。

Fresh V7 export/infer/eval/reproduction完成；dataset manifest維持 `a3393f2e…`，primaryfreeze
`add7e6256c8e5d2ab834a00cb147f969bd0f091eb3ac62c34d6170461388c4de`。
ReadyCase1/3 repeat/fresh-process/order/GT-recipe-annotation poison/termination PASS。
45 ablation rows（30 evaluated、15 Case2blocked）、17 ablation charts；C/remove_collision
eachcase1candidate與knowncollision0/3segments，沒有量測到消融效益。31份原始curated報表／
plots加codevalidationreceipt保存於 `reviewed_checkpoint_v3/`；rawdatasets/GT/RRD不入Git。

既有與collision suite **1905 passed、3 skipped、0 failed，102.88s**；3skip源於worktree
預設school_v3位置不存在。明確指定canonical source並開 `--require-physical-evidence` 的
physical bundle **9 passed、0 skipped、7.94s**，包含上述3個實際檢查，未修改／補造evidence。
新scope仍在開發的3個testfiles未納入此milestone suite；collision source Ruff／strictmypy PASS。
Code/test hashes及兩組command範圍見curated code_validation.json。原fullallcaseExit仍BLOCKED；
新局部sourcebranch/camera proposal正準備，沒有自動核准或freeze tag。

### 2026-10-08 — Final fresh-checkout evidence and original Exit Gate accounting

Code checkpoint `e6fbc8fbb3bf8c36355db38c299de5ff37705604` 的完整實際 physical suite
**1859 passed in 111.14 s，0 skipped／0 failed**；repo Ruff、strict mypy 104 source files
與3 new CLI、diff check PASS。原 source、29 locked inputs／57 frames、protocol、HR01–HR04
與 V1 configs 不變。Canonical asset checkout 保持 `phase1/physical-policy-approval / c5956dc`；
live Phase2 branch及freeze tag仍指向 `5b51d2c`，Case4 DEFERRED。

獨立 fresh checkout 初始 clean clone `efd2889`，最終 source `e6fbc8f`，locked Python
3.12.12／uv.lock。Actual Blender 重建 physical evidence 為
MATERIALIZED_AND_RESEARCH_EQUIVALENT；四個 raw artifact hashes 全匹配，source hash/size/mtime
不變，原 physical producers 在上述 source checkpoints 間未改。歷史 hydration 首次
verified297／copied192／existing105／overwrite0，最後重驗297／copied0；application manifest
與 committed original 逐 byte 相同。Fresh `reviewed_fresh_v5_final` export／inference／evaluation／
reproduction 已完成；dataset manifest同 `a3393f2e…`，repeat/fresh-process/order/GT-recipe-annotation
poison/termination皆 PASS（只對readyCase1／Case3 temporal）。198 code/config/lock files全部匹配。

完整 delivery comparison 最終 **PASS**，無 differences／missing reports：41 JSON、1 CSV、
4 Markdown、21 non-runtime PNG、2 reader-verified RRD。Runtime數值／圖像、RRD container bytes
及 artifact output locations明示排除；availability/counts、failed/N/A rows、candidate order、
termination保留。最初僅四個 demo output location strings 不同的 FAIL receipt留 ARCHIVE，
normalizer只認可精確 recording/preview root；非 runtime numeric/counts 不被略過。

Curated receipts與report/chart matrix保存於 `data/finalization/reviewed_checkpoint_v2/` 及
`reviewed_run_v5/evaluation/`。原 Exit Gate逐項 fail closed；readyCase1/3 scoped PASS不可升格
all-case PASS。唯一來源 prerequisite為目前 convex complete approved domain只有1 route class／
0 branches，58 components／116 bypass audit的26 distinct-camera FOV pairs中0全部source-supported
body-clear。Case2／Case3 detour-growth仍 BLOCKED，無可直接APPROVE的合法新scope proposal。
Final status **PHASE1_FINALIZATION_BLOCKED**；不建 freeze tag、不 merge main，raw source／
media／所有舊版本保留本機。使用者已授權 sprint branch fast-forward publication；推送另以
live remote SHA核對，不以本記錄當作已推送證據。

### 2026-10-07 — Fresh reviewed local execution, explicit reference metrics and demos

新增 reviewed export／inference／evaluation／reproduction CLI，復用原 camera/raycaster／
projection／FrameSampleDataset／Graph traversal／BlindGapReconstructor／A-B-C masks／
comparison reporting／Rerun adapter，不重建 inference engine。所有正式 primary inference
先凍結，再開 evaluation/reference。新 V2 export/inference locks 在 simulation 前固定，
原 V1 config、29 review-bound inputs、57 frames、原 protocol 保持 bytes。
Canonical local output：`data/finalization/reviewed_run_v5/`；V1–V4 探索結果全部 local ARCHIVE。
Dataset manifest SHA `a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5`，
primary freeze SHA `d16708cfb437b6dff2ea06139126d5784a181c547d9dba6d1633068988cf4059`。
Formal local Case1/3 × A/B/C 已執行，27-row K matrix 包含 9 Case2 BLOCKED/N/A rows。
C Case1 ADE=1.5968095443362998e-5 m、FDE=7.390309426983255e-6 m；
C Case3 ADE=1.4052783774710346e-5 m、FDE=3.15227085453112e-6 m；A/B 同值。
每 Case 1 route／2 timing hypotheses／2 expanded states，COMPLETE；Coverage@1/2/3=true。
獨立 source-class recall=1、approved local handoff impossible-transition=0、certificate內
continuous segments collision=0；不升格全球／中間未觀測 camera sequence authority。
新 explicit reference annotations 產生 primary Travel-time Error=0 s，moving durations
4.4 s／152.4 s；departure-dwell alternatives 保留，error=2.211203 s／150.283315 s。
20 charts、兩份含 source cameras/certificate/body guard/projected/inferred 的 RRD+PNG，
RRD reader verification／視覺 QA PASS，GT primary recording 關閉且未記錄。
Repeat／fresh-process／ordering／GT poison／termination PASS，scope 僅 ready Case1/3；
兩個新 annotation files 用 malformed poison 亦不改 primary inference。
Source motion 是 CONFIGURATION_SAMPLER、camera/visibility 為 Blender source-bound export，
不冒充 Blender actor animation 或真实拍攝；pixel noise 未宣告，uncertainty 保留 unavailable。
130 focused tests、repo Ruff、strict mypy 104 source files＋3 new CLI PASS；最後 pipeline
poison fix 的 10 tests 亦 PASS。完整 suite 與 clean-checkout delivery comparison 待獨立重跑。
Case2 source branching、Case3 detour/growth 不足仍阻塞原 Exit Gate；remove_collision 缺
獨立 purpose-bound consumer，保留 N/A，沒有用空 collider 或放寬 scope 造 PASS。

### 2026-10-07 — Independent reference movement policy approved and locked

原 protocol 要求獨立 reference moving/dwell annotation，原 HR04 只有 inference timing；
提出 exact simulation segment MOVING／departure DWELL annotation profile，附 10 s gap／
4 s dwell／6 s movement 的反例定義，避免用完整 gap duration 製造必然零誤差。
使用者明示「核准此新增 reference policy」，另存
`data/finalization/reference_movement_approved_v1/` receipt／input lock／manifest。
Proposal file SHA256 `85b9467ec8ba18f2ec3fa001e97bec9b4be4185a41a43baed05a849f0bbbdf31`，
receipt content SHA256 `972fc01f5026311de52c934dd8315e1ee35bef9cf800af88b91b07d44e01d5ac`。
時間為 explicit reply 後的記錄時間，未捏造原訊息時間。鎖定發生在新版 fresh simulation／
export／evaluation 前；原四項 APPROVE、immutable questions、protocol、v1 configs 和所有
已存在 datasets/results 不回寫。Annotations 只供 simulation/export/evaluation/debug。
此 milestone 是新增 reference policy 授權，尚非新版 metric 執行或 final Exit Gate PASS。

### 2026-10-07 — Reviewed adapters, GT-free policy lock and route-scope proof

新增 additive reviewed context／rigid landmark→footpoint／metric／A-B-C provider adapters；
實際 application loader 重驗原 29 inputs 與 immutable profiles。保留原 diagnostic producer
bytes/literals，exact-time multiview 保留 NO_PLANE provenance，不偽造 fixed-plane evidence。
Semantic receipt、certificate、source、scope、decision hashes 在所有 consumers 保留。
在 simulation 前凍結 `configs/finalization/reviewed_case_inventory_v1.json`；
另拆 GT-free `reviewed_case_inference_lock_v1.json`，Graph 不讀 simulation waypoints。
原 pilot budgets 正規化成 SI（24.7 m max path、0.7904 m/s）而非換 core defaults。
Actual reviewed rectangle 解析 proof：寬 0.29643439659979187 m、長 3.8729874223411893 m，
只有一個 major source-route class、0 branches/holes/authorized cross-scope portals。
`data/finalization/reviewed_route_inventory_v1/proof.json` 保留原完整 authority hashes；
Case2 需要批准範圍以外的 source-distinct branches，parallel offsets／timing 不增加 route。
Case3 long-GAP 可獨立執行；detour/candidate-growth 完整 stress gate 仍不可滿足。
新增 original Exit Gate accounting，逐項 fail closed 並列 prerequisite blockers，PASS certificate
不開啟 overall freeze。57 focused reviewed/hydration/exit tests、Ruff、strict mypy 4 modules PASS。
Real durable hydration 297 files／29 locked inputs 全部匹配，copied=0、overwritten=0。
修正 review package 與 locked-input 交集的相同 hash 合併，衝突仍在寫入前拒絕。

### 2026-10-07 — Applied approved bounded authority and historical hydration

接管既有 clean worktree `phase1/finalization-sprint / 62ea9b1`，未切換 canonical checkout。
本輪 readonly application verification 核對原 source、29 locked inputs、57 original frames、
immutable decisions 與 checkpoint ancestry PASS；fresh-output application 產生
`data/finalization/human_review_applied_v1/`，bounded reviewed physical certificate **PASS**。
Decision content SHA256 `8df8cda06dd9fd0848bc39395d4c6b5c695aae30b3f5329b4c0d30ff7fea085a`。
仍只授權原 office rectangle/body guard，overall **PARTIAL_APPROVED**；formal readiness 未開啟。
新增 hash-first historical hydration CLI，只複製缺少的原 review files / inputs，拒絕任何
hash drift、overwrite、root escape 或 GT input；新 formal output 不替代 historical evidence。
本輪 53 approval/certificate/receipt/hydration tests PASS，新增工具 Ruff、strict mypy PASS，
diff check PASS。uv 在 sandbox 的 macOS system-configuration 初始化 panic，使用核准的
unsandboxed locked uv runtime 執行相同入口；source/config/protocol 與舊成果未修改。
此 milestone 不是 formal Cases、fresh benchmark 或 Phase1 freeze 證據。

### 2026-10-07 — Post-approval implementation handoff checkpoint

使用者要求保存 checkpoint／commit 並交給新對話，可大規模實作剩餘原 Phase 1 收尾。
新增 PHASE1_POST_APPROVAL_HANDOFF.md 與 hash-bound CHECKPOINT.json；current handoff
只保留有效續作入口，舊展示／驗證細節留在原 README、logs 與 Git 歷史。
實作位置明定 /private/tmp/amidst-phase1-finalization，canonical asset checkout 不變。
本次重新核對 source hash、29 review-bound inputs、57 original frames、完整 submitted
決策與 durable copy 一致、Phase2 frozen ref；全部 PASS。只有文件／checkpoint變更，
未 apply、run certificate、formal Cases、render、push、merge 或建 freeze tag。
177 review tests／Ruff／4-tool mypy 是 10a3fcc 的歷史結果，本次沒有重跑程式測試。
交接 commit 保存可查的新對話起點；新對話在派送後依該 handoff 自主續作。

### 2026-10-07 — Four explicit human approvals recorded

使用者確認房間／鏡頭「綁對」，接受 rigid landmark→floor 建議並明示其餘全部 APPROVE。
記錄原四項 recommended profiles：bounded source-surface、rigid offset、ADE<0.50m、
0.7904m/s與既有departure dwell；只改decision/selected_option與chat-origin reviewer/time。
Immutable e105 payload及原review template保持不變。唯讀驗證source、checkpoint ancestry、
29inputs及57frames通過；status為EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION。
Dashboard显示4/4approved、0human blockers，completedsource優先且不讀／改／刪舊cache。
177相關tests、repoRuff、4reviewtools strictmypy與diff gate通過；沒有apply authority、
certificate regeneration、formal Cases、render、source修改或發布。

### 2026-10-07 — HR02 source-camera and landmark/foot evidence

在 `7140062019a00256df0543d7dc3e513c53090d9d` 上補齊 HR02 的自動證據。唯讀 source
frame220／subframe0、原 calibration、public projection／既有 GAP candidate 與完整
allowed evaluated VIEWPORT meshes，共200次 landmark／候選腳底射線。26原OBSERVED
landmark通視一致，腳底為10CLEAR／90OCCLUDED，16筆landmark可見但腳底被擋。
兩鏡頭在AUDITORIUM annotation AABB而非OFFICE；不据外框認證真實room ownership。
1.3597349529m是pending landmark→floor差，不是樓高。HR02只待確認目標房間／鏡頭及
追蹤點語意；fallback既有protocol不新增人工問題。四項decision仍null，未apply decisions。
重複source query的50frame與2camera資料精確一致；不是formal fresh benchmark gate。
新相機／遮擋頁整合原dashboard，保留所有舊render；灰模stills不是CVpixel認證。
沒有GT／evaluation／recipe reads、原blend修改、authority升級、formal Cases或發布。
8張新1920x1080圖使用完整2,576instances／5,585,184triangles；舊图全部保留。
172相關tests、repoRuff、mypy93core＋6reviewtools與diff gate通過。Native50格同步、
版面只有一組geometry，完整播放正常終止；原payload與4pending choices不變。

### 2026-10-07 — Stable model/topology playback layout

在 `095af134dfb22eab51277e7affcce1198f67b0fd` 修正每影格loading文字切換造成的重排；
提示浮在model內，狀態／control尺寸固定。Native在717／1124px content widths各核對
50影格及70個播放samples，model／graph／controls／current panel座標與尺寸零變化。
原renders、人物／graph資料、33既有hash-bound inputs與四項pending decisions保留。
15相關tests、repo Ruff、mypy93core、diff gate通過；未重跑formal／GT benchmark。

### 2026-10-07 — Synchronized person position in model/topology review

在 `e4b7821f1e6c282ff571f6d56322b74e6354a958` 上補齊人物與拓樸對照：每個既有
影格新增 P(t) 腳底游標、L(t) landmark及模型／拓樸同步位置。固定N1／N2與四個vertex
不隨人移動；人物在t=4s標為N1、GAP中標E1與進度、t=9s標N2，前後可見片段明標
graph範圍外。Marker保留原50影格float32座標，node association用原public double
projection與既有1e-6m tolerance，未放寬門檻或吸附人物。Image load就緒才提交畫面／
游標／時間，過期load不覆蓋新影格。全部三條原edges、所有raw renders及四項決策保留。

新增5tests驗證50影格同步、fixed topology、端點／edge／範圍外、raw/floor mode與stale
image callbacks；79相關tests、repo Ruff、mypy93corefiles及5reviewtools通過。
Source／protocol／authority不變，沒有GT讀取、正式Cases、push、merge或freeze tag。

### 2026-10-07 — Complete framing, source cameras and HR02 body-height clarity

在 `92366d882a23c356f56ea87830463d6417576875` 上補強原人工審查介面：完整一樓與
FRONT／REAR source camera 定位、25格接近 office 導覽、public observation 時段表，
以及 HR02 人物、精確投影的候選腳底標記與獨立1.70m身高尺。1.359735m是 landmark
到候選腳底的垂直差，不是樓高；人物 placement／binding仍待HR02決策。攝像頭視野線與
超出畫面的定位箭頭只供空間辨識，未認證完整場景可視性或遮擋。舊裁切圖、所有舊動畫
與近看圖保留；context iframe採已驗證manifest hash版本避免瀏覽器讀到舊guide。

新增28PNG共13,281,548bytes；181個原artifacts（含138PNG、1GIF、1JPEG）、29frozen
inputs、四項pending decisions及e105 payload全數hash一致，source SHA256亦不變。
Native browser已核對完整地圖、最後一格camera離屏箭頭／XY定位、HR02人物與腳底標記；
另保存實際UI JPEG及 clarity_integration_manifest.json。74相關tests、repo Ruff、
mypy93corefiles與4reviewtools、diffcheck通過。未採用的flat-lighting試作另存temporary
archive。無GT／recipe／evaluation reads、source修改、authority升級、formal Cases或發布。

### 2026-10-07 — Integrated human-review media workspace

在 `753ec2889320f82b6e2bdaca987765bfc154062b` 上，將空間導覽、10秒行走與模型／拓樸
整合到 [原 dashboard](../../human_review/index.html#visual-review-workspace) 的同頁 tabs。
HR-01／HR-02 Evidence 亦可切換播放器、查看既有檢驗重點及全部原近看圖；舊 sequence
保留於 lazy展開區域。一次最多一個 active iframe，切換／modal close會卸載舊播放器。
四項 questions/profiles、e105 payload、storage key、restore/import/export/save guards不變；
合成 Node VM tests 驗證草稿相容性，不讀使用者 browser storage或選擇人工決策。
原136PNG（含拓樸靜態圖）/GIF、來源 metadata和29frozen inputs逐檔hash一致。
Native browser實測行走播放、拓樸切換、HR01/02dialog與close cleanup，另存實際UI JPEG。
69相關tests、repo Ruff、mypy93sourcefiles與3review tools、diffcheck通過。
無 source/Graph/authority/config changes、formal Cases、push/merge/tag。

### 2026-10-07 — Model/topology location supplement

在 `346124510727e06ed68745197b1eeb32358617f7` 上新增
[模型＋拓樸對照](../../human_review/frames/topology_context/view.html)。模型與空白圖例採用
N1／N2、E1–E3 相同標號；2 registered nodes、3 directed parallel edges 原樣保留，
4 個 polyline vertices 使用空心點，不加入 Graph。沿用原 50 張動畫，另輸出靜態 PNG。
疊圖用原 review camera 矩陣，raw landmark / pending HR-02 floor footprint 可切換。
沒有新路徑、Graph pruning、GT 使用或 physical authority 升級；E2 floor-review rejection
與 raw edge retention 分開記錄。原135PNG、GIF、13個既有 evidence/decision/guide檔與
29 frozen inputs 全部 hash 一致。只加 review links，四項決策仍 pending。
66相關 tests、全repo Ruff、新增 review tools strict mypy、diff gate 通過。
瀏覽器並排版面、完整50格播放、兩種高度顯示已檢查；不執行 formal Cases/push/merge/tag。

### 2026-10-07 — Additive ten-second source-model body motion

在 `5ea82587fa205d8ce4d7bec7288ca7bf0b8055a5` 上另加
[模型人物行走播放器](../../human_review/frames/motion_context/player.html) 與獨立 10 秒 GIF。
Blender unsaved process 產生50 frames /5 Hz，固定鏡頭下顯示移動的人物、body/clearance、
投影點、floor/body guard 與 OBSERVED/GAP。Actual local source110 triangles 來自
`group_0` /`group_0.002` 的 audited evaluated frame；display crop/cutaway 不改 source。
50 個位置/time/camera/method/confidence/uncertainty 完整複用既有 trace；joint pose 只供顯示。
第0、25、49格已視覺檢查，播放器實際播至50/50；GIF decode50格、每格200ms、總10秒。

新增 PNG 共19,765,351 bytes、GIF8,505,740 bytes；原85PNG、11個既有guide/decision檔與
29 frozen inputs 不變。Source hash/size/mtime 不變；4項仍pending，無GT/recipe/evaluation，
未改 physical authority、未跑formal Cases。ImageMagick optional編碼因cache資源失敗且無輸出，
改用既有Pillow12.3的indexed frames成功。僅清除task bytecode及fresh-validation mypy caches，
沒有刪除來源、任何 preview、decision 或研究 evidence。61相關tests、全repo Ruff與review工具
strict typing通過；完整1580-suite仍是前checkpoint歷史證據，這次沒有重跑。無push/merge/tag。

### 2026-10-07 — Human review spatial context supplement

在 `ef0f88ad373373c3a8222d510772440103839f2a` 延續 HR-01/02 review，新增
[五步空間導覽](../../human_review/frames/spatial_context/guide.html)：school、1F/cameras、
office 鏡頭接近、原有 10 秒 public observation / GAP candidate 移動、exact source issue。
來源模型產生 3 張 stills 與 25 張 camera-only frames（5 Hz、5 秒）；29,517,434 bytes
的新 PNG 留在本機。Source XY 圖保留完整 camera/office/body guard 座標，不作 FOV proof。
人物原首末位移約 3.873 m；HR-02 的 1.3597 m 是 landmark→floor conversion。

Source Blender 未保存或改動；29 個 frozen inputs、57 張既有圖與四項 immutable questions
保持原 hash，disk decisions 全部 pending。未讀 GT/recipe/evaluation、未改 authority、
未執行 formal Cases。成功 renderer 的 exact archive / SHA 與未成功 render 的改進版分開
記錄；空間不足後僅清除本輪 validation caches，沒有刪除來源或 evidence。
本次 **56 passed**（21 spatial +35 existing review guards）；repository Ruff、strict mypy
93 core files +4 review tools、diff check 通過。1580-test full suite 是前一 checkpoint 的
歷史結果，本次未重跑。無 push、merge 或 freeze tag。

### 2026-10-06 — Minimal Human Review Gate

已產生 [4 項 pending review dashboard](../../human_review/index.html)、固定格式證據、
10 秒 GT-free frame player、精確 office scope closeups、decisions.json 和 hash-bound
decision application pipeline。完整 regression **1580 passed /5 既有 school-v2 skips**；
Ruff、mypy93 files、diff check 通過。沒有套用 school approval、執行 formal Case、修改
source Blender、merge main 或建立 tag。證據與限制記於
[experiment log](EXPERIMENT_LOG.md#2026-10-06--minimal-phase-1-human-review-gate)。

### 2026-10-06 — Finalization blocked checkpoint

已在 `phase1/finalization-sprint` selective integrate exact physical/projection
checkpoints，source milestone `e9ade14ffd0838712935f210f17c947563a08a29`。
已完成 fresh物化／source export、additive projector、共用 traversal 的 A/B/C、
GT poison／ordering／fresh-process replay、六份 RRD reader checks、三份 PNG QA。
獨立 clean checkout 的15 dataset、217 canonical replay、19 report artifacts
及 baseline regression 完全一致。1532 pytest passed、5 historical school-v2
prerequisite skips；Ruff、mypy92 source files、diff check通過。

正式 Cases1–3 沒有執行，27 rows 明示 N/A/NOT_CERTIFIED。
唯一 [human gate](../../human_review/README.md) pending；
[final report](../research/PHASE1_FINAL_REPORT.md)／[experiment record](EXPERIMENT_LOG.md)
保存具體數值與限制，[cleanup](../operations/PHASE1_ARTIFACT_CLEANUP.md)只有inventory，沒有刪除。
已準備任務限定 publication；不 merge main、Phase2保持FROZEN、不建立freeze tag。


### 2026-10-06 — Lightweight physical-policy checkpoint

`phase1/physical-policy-lightweight` 直接由已同步遠端的
`0bab8ac262b93f3c8babad69432744e7e4d1c541` 建立；full local evidence commit
`c5956dc825f669e28e2694578be0fed97432a786` 保留為 reference，不作祖先。
選擇性保留 code/config/tests/docs、experiment log 與小型 summaries；原 producer、
config、`uv.lock`、12 份 historical JSON（包含原 manifest）bytes 保留。
沒有 rewrite／rebase／amend／force push／merge，也不開始 Finalization Sprint。

[Materialization contract](../operations/PHYSICAL_EVIDENCE_MATERIALIZATION.md) 與
[artifact manifest](../../data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json)
明列 source、byte/content hashes、command/config、producer 與 semantic role。
四份 raw gzip 共 **48,362,311 bytes**，以 exact paths gitignored；receipt 也 ignored。
Wrapper 以 CPython 3.12.12、固定 lock、Blender 5.2.1 LTS build `9e2066aef7ef` 在隔離
workspace 執行未改動的 exporter／validation pipeline，檢查全部結果後才安裝 raw blobs。
Atlas timestamp 只作已揭露的 historical replay metadata 正規化，actual source before/after
fingerprints 獨立記錄；原 scene 的 bytes／size／mtime 不變，原 provenance 不回寫。

乾淨 independent temporary clone 從基底建立 candidate tree，full commit object 不存在；
`uv sync --frozen` 通過。Without-artifacts `uv run pytest -rs`：**1365 passed / 8 skipped**
（88.70 s）；3 個 current physical-evidence checks 明確 skip，其餘是 historical school-v2
source/calibration prerequisites。Strict missing-evidence profile：6 passed／3 explicit
prerequisite setup errors，符合契約，沒有模糊 FileNotFound 或偷偷下載／生成。
既有 historical hash unit 的 local-camera 依賴已分開，3 份原 config 的 committed fixtures
共 4,140 bytes，仍逐 byte SHA 核對原 manifest；不依賴 Git history 或放寬 hash assertion。
隔離 branch 的指定 `uv run pytest`：1365 passed／8 skipped（75.54 s）。

Fresh-clone materialization 確實由 preserved scene 重新抽取 atlas，而非複製 full commit blobs：
660 objects、1,548,921 triangles、26 complete selections。四份 raw artifact 的 byte SHA 與
canonical JSON hashes **全部完全相同**；完整 physical-policy replay 207.46 s。
Architectural scale／physical policy APPROVED；floor supported=48；58 approved components
across 5/19 obstacles；8 portals HUMAN_REVIEW；Stair A/B HUMAN_REVIEW；overall
PARTIAL_APPROVED；collision diagnostic 4→2。Complete local islands=0、global physics gate
仍關閉；沒有調 threshold、使用 GT 或改研究結論。

Fully materialized fresh clone 的完整 strict profile：**1368 passed / 5 skipped**
（79.88 s）；current physical bundle 的 9 checks 全通，remaining skips 僅 historical
school-v2 fixtures。`--verify-only` 通過，fresh checkout 在 materialization 後仍 clean。
兩個 profiles 的 Ruff／mypy（91 source files）全通；`git diff --check` 與 13 份
文件的 216 local links／anchors 檢查通過，沒有 absent-artifact links。

Candidate size/provenance audit（本 log entry 加入前的 clean tree）：新增 unique reachable
blob payload **2,609,291 bytes**，原 full checkpoint 是 **50,897,608 bytes**，減少 **94.87%**。
Non-thin single-thread pack（candidate minus base reachability）522,863 bytes，原 full
checkpoint 同方法為 32,076,978 bytes；不是總 repo size 或依網路 negotiation 改變的 wire size。
沒有新增／追蹤 `.blend`、`.rrd`、renders 或四份 raw gzip；基底既有 evidence 保留。

| Largest newly tracked artifact | Bytes |
| --- | ---: |
| `obstacle_collider_authority.json` | 487,046 |
| `scene_validation.json` | 444,882 |
| `stair_authority.json` | 351,042 |
| `portal_clearance.json` | 153,679 |
| `walkable_clearance_1F.json` | 82,780 |

全 repo 最大 tracked files 均繼承自基底：`phase1_physical_authority_20261006/source_mesh_evidence.json`
10,996,697 bytes、`school_v2_scene_audit.json` 6,750,115 bytes、`school_v3_semantic_audit.json`
6,617,918 bytes、approved-scale `geometry.json` 6,496,240 bytes、geometry-authority
`geometry.json` 6,496,191 bytes。既有 benchmark PNG 是 plots，沒有新增 scene renders。

### 2026-10-06 — Physical policy 核准與 source-bound partial authority

從 clean scale-approved checkpoint `0bab8ac262b93f3c8babad69432744e7e4d1c541`
重跑 1199 pytest、Ruff、mypy（83 files）、diff check 全通，push
`phase1/physical-authority-resolution` 並確認 live origin SHA 完全一致，再建立
`phase1/physical-policy-approval`，沒有 merge／rebase／history rewrite。

[Authority report](../../data/scene_audit/phase1_physical_policy_approval_20261006/authority.md)
與 [experiment log](EXPERIMENT_LOG.md) 保存新 evidence。Physical policy APPROVED；
source support Z=20.0788497925／161.8110961914 BU；48 supported 子域（45 whole／3 partial），
38 舊偏移例外解釋、10 舊 budget-limited regions 恢復可用證據。
5/19 OBSTACLE 中 58 exact components APPROVED；whole volumes 仍 REVIEW。
WALL 維持 73 HIGH／1422 REVIEW／77 REJECTED；8 portal 與 Stair A/B 仍 REVIEW。
5 個局部區域皆因 unclassified enclosure／degenerate geometry 保留 REVIEW，完整 islands=0。
整體 PARTIAL_APPROVED；positive component probes 4→2，formal local/inference pruning 關閉。

修復凹形 closed-volume ray tangency 漏判、雙重 floor-contact tolerance，新增
floor-scope refusal 與 before-K provenance/order guards。完整 source geometry 為
660 objects／1,548,921 triangles／26 complete selections；含 hidden/enclosing geometry。
Source SHA／468300506 bytes／mtime 全維持，沒有修改或縮放 `.blend`、guess roles、
造 geometry、使用 GT、調 MetricConfig／benchmark／ranking 或啟動 Cases 1–3。

最終 **uv run pytest: 1352 passed，0 failed／0 skipped（94.81 s）**；新增153 tests，
原1199均未退化。`uv run ruff check .`、`uv run mypy`（90 files）、diff check 全通。
第一輪新增tests暴露報告把48proxy偏移誤算為38舊例外，及stair fixture缺enclosure契約欄位；
修正後完整重跑通過，沒有降低threshold。Task docs175 internal links確認有效。
Historical artifacts／provenance 保留；active context 指向新 source-bound gzip bundle。


### 2026-10-06 — 正式核准 Phase 1 architectural scale

於 `phase1/physical-authority-resolution`，由 checkpoint
`7798f0cfd0b4501d0831c82b06d35ddf21d8da29` 接受使用者正式核准
**1 BU = 0.0247 m**。核准依據為 **USER_DEFINED_RESEARCH_MODEL_SETTING**，
[source-bound authority record](../../configs/architectural_scale_school_v3.json) 為 APPROVED；
不再要求外部尺寸重新推導。下面先前的暫定尺度與 1:1 checkpoint 記錄保留為歷史。

[Active physical context](../../configs/physical_context_school_v3.json)、school-v3 validation／
measurement configs、provider authority 與驗證文件同步更新。[新 geometry／scale validation](../../data/scene_audit/school_v3_approved_scale_20261006/geometry_scale_validation.md)
核對 **1,669 surfaces** 的原始 BU vertices／faces／planes／ownership 完全不變；
原 doorway margin 0.28 BU 換算為0.006916 m，原始診斷邊界不變。
新增 source-bound 單位 adapter，一致處理 camera／plane／PROJECTED／navigation、
速度與 distance bounds；SI body／clearance／contact policy 可換回 BU，pending null
與 authority 不變。ADE／FDE scalar reporting 保留 BU 並加 meter，不重算 Coverage／epsilon。
既有 runner／pilot 不會自動遷移；新 native inputs 必須由 caller 顯式 normalization。
沒有修改正式 domain schemas、Graph／Top-K／benchmark／GT isolation。

Read-only Blender 量測重新產生 **37 筆 SANITY_CHECK_EVIDENCE**，285 組 BU／meter
換算通過；floor support rise141.732246 BU＝3.500786 m。可靠門洞截面約0.875–1.750 m、
走廊3.015–3.598 m、教室6.321×9.676 m，未找到支持明顯尺度錯誤的可靠尺寸。
5筆 meeting-room／gallery nearest-hit 截面保持 boundary-binding review，不宣稱為
真實巨門或極小房間。原 v3 SHA-256／size／mtime 前後相同，geometry 不縮放／save／render。
原 benchmark／pilot／camera／geometry checkpoint artifacts 與 BU provenance 保留。
Scale APPROVED 不核准 floor、stair、obstacle volume、body／clearance；四種 formal scope
仍 typed refuse，整體 physical authority 為 PROVISIONAL，沒有開始正式 benchmark。

驗證抓到 stair source `path_segment_points_json` 是 BU、卻與 meter mesh 直接比較的
診斷錯誤；只修正這個單位邊界，明確 `path_points_m`／clearance_m 保持 SI。
新增 alignment／direction／anchor／join 與 source-binding guard regressions。
第一輪完整 pytest 的3個 fake obstacle assertions 因共用 active school scale失敗；
將合成 fixture 明確綁至原1:1通用 config，保留原 assertions／production 計算後重跑。
最終 `uv run pytest` **1199 passed in91.34s，0 failed／0 skipped**；
`uv run ruff check .`／`uv run mypy`（83 source files）／兩支 scripts strict mypy／
`git diff --check` 通過。所有新 evidence 的 input／code／artifact hashes 核對通過。
本輪只建立獨立核准 commit，不 merge／rebase／改寫歷史，不開始 Case 1–3 或 Agent。

### 2026-10-06 — school v3 暫定尺度量測與來源整理

於 `phase1/physical-authority-resolution`／checkpoint
`cdeee3e316e88c87ab63cdcf3acb360485f00dd6` 接受使用者更新：新診斷暫採
**0.0247 m/BU**。使用者確認目前無可靠實測／設計尺寸，因此 scale authority 保持
HUMAN_REVIEW，正式 calibration／舊 units config／benchmark／pilot／snapshots 不回寫。
沒有修改正式 schema、Graph／ranking／metric semantics 或 GT isolation。

[Scale review](../specs/SCHOOL_V3_SCALE_REVIEW.md) 與新唯讀 Blender measurement script 產生
**37 筆量測、6 個未宣告唯一方向的 PORTAL、5 個人工確認 anchors**。Annotation 與
actual source cross-sections 分列，保留 248 個 hits 的 source object／evaluated polygon／
vertices／端點、不同高度 profile、confidence 與 ambiguity。餐廳 A 約0.875198 m、
Office 約1.750392 m、CLASS201 Y 約9.675786 m、CORRIDOR03 的 profile 約3.030764–3.131431 m；
source support 高差141.732246 BU，暫換算約3.500786 m。未把截面當 approved aperture，
沒有以合理性批准 architectural scale。三個取樣高度不代表人體／clearance policy。
兩次獨立 Blender invocation／不同 output directory 的量測 semantics 一致；
最終 input／script hash bindings 核對通過，原 v3 SHA／size／mtime 前後相同。

Live Blender＋repository camera reference audit：29 CAM research cameras 全保留，
匯入 SketchUp camera active consuming references=0，可忽略但未刪除原物件。
Inventory／exclusion／history references 不移除。Active config／schema 無 elevator 規格；
新 config／index 明列 NOT_APPLICABLE，保留 AREA_*_ELEVATOR，不建立 transition。
Canonical reference index 保留 byte-identical WALL Markdown 與 content-identical JSON
的歷史 aliases；1,669 portable surfaces 沒有 exact geometry duplicate groups，未刪資料。
Bounds／尺寸從 source 自動產生，不新增人工手抄表；group_*／Cube.* 保留且不按名稱定角色。

本次完整 `uv run pytest` **1131 passed in84.83s，0 failed／0 skipped**；Ruff 通過，
`uv run mypy` 通過（81 source files），另對新 measurement script 的 strict mypy 通過。
新增11個 diagnosis／source-bound report regressions，targeted run **11 passed in0.05s**。
52個更新文件的 internal file links 與 diff check 通過。此輪沒有 render／正式 benchmark、
geometry integration、模型縮放／修改、merge 或 push；physical authority 仍 PROVISIONAL。

後續 staged diff check 抓到 CSV 預設 CRLF 被判 trailing whitespace；先前已建立的
`84ff020` 保留，追加 LF writer／regression guard 修正，不改寫 commit 歷史。
重新唯讀產生報告，所有 source measurements 完全相同，JSON 僅 producer script hash
更新；manifest 保留前版 JSON／CSV hash 與 commit reference。修正後完整重跑
**1131 passed in85.57s，0 failed／0 skipped**，Ruff／mypy／script mypy／diff check 通過；
最終92個 internal links有效，原 v3 與既有 benchmark／pilot artifacts 不變。

### 2026-10-06 — Geometry checkpoint 發布與 physical authority blocker 審查

使用者指定的 `bb66bb74a4a76430f6fa8f79672345385a79e3f0` 在
`phase1/geometry-authority` 起始 working tree clean。重新執行完整 gates：pytest
**996 passed in 85.24s，無 failed／skipped**，Ruff、mypy（77 source files）、diff check
通過。正常 push 後，live `git ls-remote` 的 origin SHA 完全一致；由這個確切 commit
建立獨立 `phase1/physical-authority-resolution`，沒有修改 checkpoint／merge／rebase。
恢復入口見 [geometry checkpoint](PHASE1_GEOMETRY_CHECKPOINT.md)。

[Physical blocker report](../../data/scene_audit/phase1_physical_authority_20261006/resolution.md)
及 JSON／sidecar／manifest 綁定來源與兩種 config。Read-only Blender survey 選取
69 個局部 regions／157,589 個三角面 records，保留 source object／face identity；bbox
僅篩選 evidence，不當 collider、不依 `group_*` 名稱猜 role，不 save／render。
三個非衝突餐廳／storage obstacle regions 達 export budget，明確標 selection incomplete。

8 組 OBSTACLE／PORTAL 均保持 physical HUMAN_REVIEW；兩組 2F MEETINGROOM 已確認
annotation depth margin overlap、declared center plane 未被 footprint 擋住，但不核准
aperture／body clearance。廁所四組完全覆蓋，主入口兩組仍無法可靠判別實體 blocker、
footprint 過大或 portal 位置。19 個 role approval 保留，volume／height 仍未批准；
局部 source meshes 沒有一對一 collider ownership，未以 proximity／closed fragment
自動配對。**0 scene repairs**；沒有任意縮 obstacle 或移 portal。

48 個 WALKABLE floor scopes 保持 HUMAN_REVIEW：38 個精確量測到 proposed plane
與 source support 的例外，10 個保留既有 complexity limits 與 partial ray evidence。
主要 actual support 為1F Z≈20.07885、2F≈161.811096，與25／165相差約4.92115／3.188904。
AREA／PORTAL 是 annotation context；v2 calibration 不給 v3 physical floor-plane authority。
沿用已確認 1 BU = 1 m 計算 convention，不自行 rescale 或強制統一 floor。
Stair A/B 的 actual ROI 各有932／422 triangles，找不到支援兩個 proxy half endpoints
的共同 landing；ENTRY／EXIT 對 actual horizontal support 距離 A2.783161／0.811096、
B5.047535／3.061096，皆超出既有0.25 join tolerance。Opening／clearance／connectivity
仍 REVIEW；未造 landing 或 connector，也未修改原始／衍生 `.blend`。

新增 `physical-authority-v1` purpose-specific sidecar／read-only wrapper，沒有修改
`scene-geometry-v1`、正式 Phase 1 domain schemas 或 Graph。Policy config 明列 body
model／reference、radius／height、body clearance、portal horizontal／vertical clearance、
contact tolerance 與比較方式；未核准欄位為 null／HUMAN_REVIEW，沒有自行採用研究數值。
四種 formal purposes 的 scope、coverage、exact IDs、source／canonical geometry hashes
分開驗證。當前全部 typed refuse，整體 **PROVISIONAL**；沒有可開始正式 hard-pruning、
collision-free／topology certification 或 physical-validity metrics 的 scope。
73 HIGH_CONFIDENCE WALL 只作 provisional evidence；原 doorway protection／threshold
保留，沒有升級剩餘1,422 patches。沒有變更 benchmark、ranking、GT isolation，也未開始
正式 Case 1–3、Agent 或 Phase 2。

最終 `uv run pytest` **1120 passed in 86.99s，0 failed／0 skipped**；Ruff、mypy
（81 source files）、diff check 通過。新增124個 physical policy／scope／source evidence／
report regressions，包括 forgery、GT guards、partial scope 不認證完整無碰撞、source mesh
budget、actual floors／stairs／8 pairs，以及錯誤報告呈現修正。獨立 report replay 保持
authority decision／source measurements一致；原 `.blend` SHA／size／mtime 不變。

### 2026-10-06 — 獨立 Phase 1 geometry authority milestone

由穩定 checkpoint `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` 建立
`phase1/geometry-authority`；來源與既有 checkpoint 不改寫、不 merge。
[Authority report](../../data/scene_audit/phase1_geometry_authority_20261006/authority.md)
及同目錄 source-bound manifest／exact mesh／portable geometry 記錄 81 seeds + 1,491
review patches 的重驗：**73 HIGH_CONFIDENCE／1,422 HUMAN_REVIEW／77 REJECTED／0 APPROVED**。
11 seeds 降級（5 continuous WALKABLE intrusion、6 actual support 不足），3 review 升級。
保留原 threshold；actual triangle unions／continuous intervals 補強舊 sampling／bounds
漏掉的穿入及缺面。28 PORTAL hard protection 的 accepted contacts 為 0；包含錯誤 floor
label 的真實相交，禁止封門，未用 `group_*` 名稱猜 role 或回寫 source／衍生 `.blend`。

19 OBSTACLE 的已確認 role APPROVED，movement／visibility 均 true；footprint／open
surface physical authority 保持 HUMAN_REVIEW，不擠出高度。PORTAL conflicts 為 8 pairs；
WALKABLE overlap 大於既有 contact ratio 的 pairs 為 0。Stair A/B 各有兩個 PATH
components，nearest 3D gaps 為 **4.769402／4.896199**，沿用現有 1 m／BU conversion；
不把它當另行 physical scale 核准。Connectivity／landing／opening／clearance 仍 REVIEW，
只有樓梯，沒有電梯，也未建立跨層 connector。

新增 [platform-neutral read-only geometry contract](../specs/GEOMETRY_PROVIDER.md)：frozen／strict
models、source SHA binding、exact triangles、role／physical support／floor／scale authority
分離。無 bpy／GT dependency；unknown fields 與 unchecked model mutation 拒絕。
`require_approved_physics` 對 incomplete scope、未核准 floor／scale／collider typed fail closed；
空 inspection collider 集合不能證明無碰撞，沒有 WALKABLE support 的 floor 不能宣稱完整。
整體 **physical/collision validity = PROVISIONAL**；未修改 Graph、ranking、GT isolation、
benchmark／metric semantics，未執行正式 Case 1–3、render、merge 或 push。

本次最終驗證：`uv run pytest` **996 passed in 84.79s，0 failed／0 skipped**；
`uv run ruff check .` 通過，`uv run mypy` 通過（77 source files），`git diff --check`
通過。包含既有完整 regression 與新增 101 個 authority/provider/physical-review tests；
跨 process／不同 output directory 的 review artifacts 一致，兩次獨立 read-only Blender
export 證據一致。Manifest input／code／artifact hashes 核對通過，90 個本輪文件 local
links 有效。Original source SHA／size／mtime 完全不變；既有衍生 `.blend` SHA／size
仍與 saved-marking evidence 相同。1,572 個 patches 的 actual welded triangle components
均為 1；沒有把整體 geometry completeness 或 stair connectivity 升為 APPROVED。

### 2026-10-05 — 第二個 checkpoint 與 bounded pilot downstream 閉環

使用者明確要求將成功pilot `fdf9e7e8f2dc695917ba42094a63cc06ca910963` 作第二斷點。
起始 `phase1/pilot-dataset-and-wall-inference` working tree clean、HEAD完全相符；重新跑
`uv run pytest` **847 passed in55.97s、無skips**，Ruff、mypy72sourcefiles、diff check通過。
Push該branch成功，`git ls-remote --heads origin` 回傳相同完整SHA；從它建立
`phase1/pilot-downstream-reconstruction`，後續只在新branch。[Checkpoint record](PHASE1_PILOT_CHECKPOINT.md)
記錄恢復入口、原始／衍生assets及本機ignored資料。不另改checkpoint commit或merge回去。

只接現有office **1條trajectory**，不新增Blender render／dataset。新增GT-free strict
pilot context／Observation consumer、provisional topology與小型CLI，復用既有
InverseProjectionService、BlenderDataset、aggregation、reconstruct_gaps、Graph Top-K、
BlindGapReconstructor與configured metrics。沒有改core engine、正式benchmark或metric semantics。
輸出位於本機ignored `data/pilot/phase1_downstream_20261005/`，全部標示
**PILOT / SYNTHETIC SAMPLE**；strict domain結果以label wrapper保存。

Export preparation只從existing mixed export allowlist 960×540camera calibration、
source identity、independent mesh-probed static landmark plane與原audit AREA bounds。
Container digest在獨立preparation manifest，不進inference identity；不copy GT positions、
plan waypoints、per-frame depth或GT速度。Consumer只讀 `observations.json`＋strict
`projection_context.json`，拒絕hidden字段、未檢查model_copy注入與source/site/contentSHA錯配。
100／100 camera records、50／50timestamps完整接入；26 OBSERVED反投影、74 GAP保持null。
聚合front0.0–4.0與rear9.0–9.8兩段PROJECTED Observation，形成一個4.0→9.0s Event；
24個global GAP samples為4.2–8.8s，端點window與GAP samples明確區分。

Graph只以PROJECTED departure/recovery anchors與明示±12BU lateral offset，限制於
source AREA_1F_OFFICE annotation AABB；保留來源camera zone IDs，以3個configured
ADJACENT transitions建立direct/left/right路徑。這是local provisional scaffold，
不是完整WALKABLE polygon、school camera adjacency或WALL／mesh certification。
候選長度80.00083961／104.00083961／104.00083961BU，3routes／6timing hypotheses，
`COMPLETE`、search exhaustive=True、rejections=[]、path_score全部None。所有Top-K保留，
不以GT、confidence或behavioral probability排序；physical/collision validity為
PARTIAL／PROVISIONAL，actual mesh collision rate=null。空obstacles的raw0不是clearance證據。

Inference全部寫完後才載入GT，僅對4.0–9.0s的26個GT timestamps（含visible endpoints）
使用既有metric semantics。首個primary route ADE **0.000708092424BU**、FDE
**0.000280838027BU**；minADE@3／minFDE@3相同，Coverage@1/2/3皆True，門檻為
diagnostic ADE<0.02BU，非正式epsilon／米制認證。Near-zero FDE是anchored endpoints的
診斷結果，不宣稱研究accuracy；GT-compatible route只由evaluation判定，候選order不變。

`run_01`／`run_02`的10份inference artifacts與metrics逐byte一致。將50個GTpositions
大幅移位並污染simulation waypoints後重新export，context與`poison_run`的10份inference
artifacts仍逐byte一致；只有metrics改變（ADE約37416.574BU、Coverage@3=False）。另有
file-access poison、GT缺席、extra字段／unchecked nested injection、GT第三路徑相符而
第一候選不變、錯GT binding／time extent與inference先於GT載入等meaningful tests。
完整source original／derived hash、size、mtime，原pilot dataset／2D／GT／plan均未改動。

Rerun／3D呈現只讀saved outputs，再載入GT獨立debug overlay；保留3candidate paths、
6hypotheses、26observed及50GT markers。產生readable `debug.rrd`、standalone
`review_3d.html`、`preview_3d.png`與hash manifest；實際目視PNG，RRD readback41chunks／
33entities與各路徑sample counts通過。Browser policy拒絕file://，未做HTML UI驗證或繞過。
總驗證 `verification.json/md` 為 **PASS_WITH_PROVISIONAL_PHYSICS、errors=[]**。

Final完整檢查：**895 pytest passed in57.58s、無skips**，Ruff、strict mypy74sourcefiles、
diff check通過；uv/native Blender檢查於sandbox外完成。新branch只做本機milestone commit，
沒有push新branch、merge、正式Case1–3、elevator transition或dataset擴充。本輪到此停止。

### 2026-10-05 — Checkpoint 後 WALL semantic marking 與單一 pilot 閉環

只在 `phase1/pilot-dataset-and-wall-inference`，由 checkpoint
`91f4ea600805739aa9659dfef6a381d71be9a692` 繼續。重新從原始 school_v3 mesh 提取，
[candidate report](../../data/scene_audit/phase1_wall_candidates_20261005.md)／JSON 與先前
結果一致：**81 AUTO_CONFIRMED_WALL patches**（1F49／2F32，7來源objects）、
**1,491 HUMAN_REVIEW patches**（674來源objects；混合object可重疊）。逐patch列出
floor、bounds、AREA／WALKABLE／PORTAL關係、verticality／height／continuity／extent／
parallel thickness evidence與理由；window／door／decoration等歧義保留review。

[Marking report](../../data/scene_audit/phase1_wall_markings_20261005.md)／JSON記錄81個
`semantic_class=WALL` annotation meshes，543個既有實際polygons，存至本機ignored
`blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend`。
不重新分類完整group_*、不填rectangle／AABB／doorway、不安裝movement colliders。
保存後獨立重開：2,873原始object fingerprints與evaluated physical geometry一致，
28 PORTAL的實際annotation face intersection area為0。原始source與checkpoint snapshot
SHA均為 `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
468,300,506bytes、mtime_ns1791198236746106977保持不變；衍生scene SHA為
`b4d3394b17626bfdf35ee9b9e35c1f5a4469dd75a3e24b1a4f5f5aa58bdf4d49`。
新增marking recipe可重驗來源、candidate及保存後的faces／props／camera／portal／geometry。

僅生成一組新 **PILOT / SYNTHETIC SAMPLE**，本機ignored
`data/pilot/phase1_wall_pilot_20261005/office/`。使用原pose的
`CAM_1F_AUDITORIUM_FRONT`／`CAM_1F_AUDITORIUM_REAR`，office metadata路線
`PILOT_OFFICE_001`，1F，規劃160／採樣156.800049 scene units；10秒、5FPS、
[0,10)的**50timestamps／100PNG全部成功**。250個支撐probes與radius6／height119
完整continuous swept volume對actual triangles檢查通過。來源lineage同時綁定
衍生scene與原始source／candidate／physical geometry；81個WALL annotation排除於
planner BVH、render snapshots與occlusion rays，既有實體mesh仍提供遮擋。

獨立validation為 **PASS_WITH_REVIEW、errors=[]**：26visible／74occluded／0out-of-FOV
camera records；front21／29，rear5／45。Global body-center GAP為frames21–44
（4.2–8.8s）共24timestamps，其中19個兩視角完全沒有marker pixels、5個仍有partial body。
形成visible→GAP→visible閉環。Forward最大0.000314545px、static diagnostic plane inverse
最大0.001615262units，unexpected Projection failures0；74non-observed inputs按接口拒絕。
純2D ObservationFrame另存，inverse只讀2D／camera／獨立mesh probe固定plane；GT只在
simulation與投影後evaluation讀取。原始source與衍生asset的hash／size／mtime均保留。
獨立audit解碼／核對全部100PNG與labels／hash、100個plan/export states、100個strict2D
ObservationFrame及26個visible-center orange masks。與舊office原source render逐像素
比較，**100／100 decoded RGB完全一致、differing pixels0**，確認新增標記未改physical render。
Dataset SHA為 `77203e33a566f99936e6446133dae245231562b0a64bfc82447e5f1215d5d2df`。

另產生dataset／GT／observations／plan／validation／human-readable sample report、50frame
10秒同步GIF、trajectory map、gallery及五張代表montages：frames0／20／21／32／45
（0／4.0／4.2／6.4／9.0s）。逐張檢查visible、approach、partial-body GAP entry、完全隱藏
GAP middle與rear-camera recovery；不把point GAP宣稱為全身皆隱藏。
完整指定檢查：`uv run pytest` **847 passed in71.83s、無skips**；
`uv run ruff check .`、`uv run mypy`（72sourcefiles）與`git diff --check`均通過。
完整uv／native Blender檢查在sandbox外完成；沒有改benchmark semantics、執行正式Cases1–3、
elevator transition、merge回checkpoint branch或push。本輪到此停止，完整generation仍待
使用者pilot確認、physical scale與formal geometry／floor／camera-plane authority。

### 2026-10-05 — Phase 1 semantic scene checkpoint

使用者明確要求大斷點、push目前branch及從斷點建立新branch。起始working tree clean，
`codex/dataset-infrastructure` HEAD為 `4437ef3e468d3b18181f893906619af021042434`。
本次重新執行指定指令：`uv run pytest` **821 passed in58.64s，無skips**；
`uv run ruff check .`、`uv run mypy`（72sourcefiles）與`git diff --check`均通過。
完整pytest與uv最終檢查在sandbox外完成；uv在sandbox的macOS初始化崩潰於相同命令
rerun消失，沒有刪除或skip測試。

[Checkpoint record](PHASE1_CHECKPOINT.md) 保存branch、已驗證起點、來源fingerprint、
本機資產與續作邊界。建立ignored唯讀 `blender/working/checkpoints/phase1-semantic-scene-20261005/`
scene snapshot，SHA與目前school_v3完全一致；原來源SHA／size／mtime不變。
manifest記錄Git checkpoint SHA與四組pilot檔案hash，raw資產不隨push發布，也沒有重render。
checkpoint commit message為 `checkpoint: preserve phase1 semantic scene state`；
後續branch為 `phase1/pilot-dataset-and-wall-inference`，由相同checkpoint commit建立。
不修改正式benchmark semantics、不執行正式Cases1–3、不merge回checkpoint branch。
精確commit與push結果綁定於本輪完成回報及本機manifest。

### 2026-10-05 — Three-locale Blender PILOT comparison

起點 `c078b89`，使用者追加授權「不同場地的多個資料，並給出判斷」。完成同一
`school_v3.blend` 的 CLASS101／AUDITORIUM／OFFICE 三個不同 metadata 區域，
本機 ignored `data/pilot/school_v3_multisite_20261005/`；不是不同建築或真實場地。
每組10秒、5FPS、[0,10) 的50timestamps／100PNG，合計 **150／300全部成功**。
原 corridor pilot 保留為比較 reference，不計入新生成數量。

教室用 `CAM_1F_CLASS101`／`CAM_1F_CORRIDOR_04`；禮堂與辦公區共用既有
`CAM_1F_AUDITORIUM_FRONT`／`CAM_1F_AUDITORIUM_REAR`，不改 pose／lens。
規劃／採樣長度依序300／294、660／646.800049、160／156.800049 scene units。
三組各驗證50個 timestamp 的5點 WALKABLE containment／physical support，並對完整
radius6／height119 continuous swept volume 做 exact triangle clipping；沒有 collision、
portal crossing、cross-floor 或 elevator transition。Cached search 僅供 hints，最終用
current evaluated physical mesh 重新判斷，拒絕碰撞及不符50點 visibility 的 routes。

| 區域 | Visible / occluded / out-of-FOV camera records | Global point GAP | 雙鏡頭全隱藏 / partial body | 判斷 |
| --- | --- | ---: | --- | --- |
| CLASS101 | 50 / 0 / 50 | 0 | 0 / 0 | 中心點持續可見對照；50個可見影像皆有 body boundary clipping |
| AUDITORIUM | 82 / 2 / 16 | 1 | 0 / 1 | 覆蓋／短暫中斷樣本，不適合作主要長遮擋資料 |
| OFFICE | 26 / 74 / 0 | 24 | 19 / 5 | 最適合本輪 point occlusion，仍有限 camera 配置與短 recovery window |

Auditorium GAP 只有 frame47／9.4s，仍看得到部分 marker。Office GAP 為frames21–44／
t4.2–8.8，完全看不到 marker 為frames23–41／t4.6–8.2，共19個離散樣本；恢復後只有5點。
Classroom corridor camera 全50點 FAR_CLIPPED；office 是不同 WALKABLE／AREA 路徑，
畫面仍是既有 auditorium 視角，不宣稱新增 office interior camera。全場採既有
opaque-gray Workbench／orange-marker policy，地板不規則明暗塊的原因未認證。
Agent 視覺判斷不當作 human authority／完整人體 CV detection readiness。

各組另存 combined evaluation-only dataset、strict 2D observations、GT、source-bound plan、
validation、sample report、50frame同步GIF、trajectory map與5張不同代表 montages。
Control 有明確 `FULLY_OBSERVED_CONTROL` 角色，不能假造 GAP；singleton GAP 的代表
frames 為0／46／47／48／49。跨場地 comparison 將判斷綁定 dataset／reviewed image hashes，
PNG 新增 SiteID，validator 核對 plan／export／PNG／provenance／2D／GT 一致，拒絕混場。

獨立驗證三組均 **PASS_WITH_REVIEW、errors=[]**；300PNG全部解碼、標記／hash核對，
158個 visible landmark 都有實際 orange pixels；全部PNG另做獨立 mask 分析確認上述
hidden／partial split。Forward max0.000638311px、static pilot plane inverse max
0.001787566units，unexpected Projection failure0；142個 non-observed camera inputs
按既有接口拒絕。來源SHA／468,300,506bytes／mtime_ns1791198236746106977不變。
GT僅 simulation/export/evaluation，inverse僅 sanitized2D＋camera＋independent static
pilot plane；沒有 Graph／ranking／reconstruction／Cases1–3 或 benchmark semantics 改動。

完整 regression **821 passed in72.57s、無skips**，Ruff、strict mypy72sourcefiles與diff
check通過。Sandbox內18個native Blender SIGSEGV於sandbox外完整rerun全部消失，
屬既知Metal環境問題，沒有以skip掩蓋。最後報告角色文字修正另通過6個summary tests／Ruff。
到這三組額外pilot停止；完整generation仍待
image policy／physical scale／formal floor-camera-geometry authority，不自動擴充。

### 2026-10-05 — Bounded Blender PILOT / SYNTHETIC SAMPLE

WALL milestone 後依同一授權完成本機 ignored
`data/pilot/school_v3_pilot_20261005/`，到此停止，不擴充完整 dataset。
`CAM_1F_CORRIDOR_02`／`CAM_1F_CORRIDOR_03` 保留來源 pose；1F corridor route 規劃
106 Blender scene units／10s，5 FPS 的 [0,10) 採樣為 **50 timestamps（0.0–9.8s）**，
採樣路段長 **103.880005 units**。實際 mesh floor Z≈20.07885，foot Z≈20.12885，
body-center landmark plane Z≈75.12885；沒有把 annotation Z=25 當作實體地面。
尺度不做猜測換算，marker 不宣稱真實人體尺寸／速度。

Planner 排除 135 annotation meshes（含四個 `Stair Reference Surfaces`），驗證 50 個
timestamp 的 WALKABLE triangle containment／250 physical support probes，以及 radius6／
height119 的完整 continuous swept volume 對 actual triangles intersection 為 0。
曾查出 point-clear route 的側面碰撞並修正路徑後才 render，不把 center ray 當作淨空證明。

Unsaved Blender 使用固定 frame220 的 evaluated VIEWPORT mesh instances，凍結為無
render modifiers 的 render-only copies，排除 non-MESH renderables；Workbench opaque
gray studio／orange marker 為明確 pilot policy。**100／100 PNG** render 成功，raw PNG
加入 PILOT／SYNTHETIC／source／simulation timestamp text metadata；100 個 IDAT payload
均保持不變。PNG hash、decoded dimensions、標記及所有 21 visible landmark 的實際
orange pixels 通過獨立檢查。這是 simulation point producer，不是 CV detector／正式材質驗證。

Camera02 visible3／occluded47，Camera03 visible18／occluded32，合計 **21 visible／79
occluded／0 out-of-FOV camera records**。Selected-camera landmark GAP 為 frames18–46，
**29 timestamps**；其中15仍有 partial body，frames25–38的14timestamps兩台相機都無
marker pixels。代表 frames0／17／18／32／47（0.0／3.4／3.6／6.4／9.4s）輸出雙相機
montages，另有50frame同步GIF、trajectory map、HTML gallery與human-readable sample report。

Independent validation **PASS_WITH_REVIEW、errors=[]**：source SHA／size／mtime 不變；
forward native residual 最大 **0.000114213px**，axial depth 最大0.000112066units；
獨立 mesh/config plane 的21次 inverse diagnostic 最大 **0.000247572units**，79 GAP
全數按既有 interface 拒絕，unexpected failure0。Inverse input 僅 sanitized 2D frame、
camera與explicit static pilot plane；GT只在simulation與後續evaluation讀取。另存
`observations.json`／`ground_truth.json`，combined `dataset.json` 明列 evaluation-only。
未呼叫 Graph／ranking／reconstruction／Cases1–3，不改 benchmark semantics，不建立 elevator。

最後完整 regression **797 passed in 56.90s，無 skips**；14 項 task safety／provenance tests
另外通過。Ruff 與 strict mypy（72 source files）通過。完整 generation 仍待人類 image review、
physical scale 及 formal floor/camera/geometry authority；不把 pilot 技術成功當作 full dataset ready。

### 2026-10-05 — Geometry-derived WALL candidate extraction

起點 `e8b293f`，branch `codex/dataset-infrastructure`，工作目錄原為 clean。
依使用者本輪授權，唯讀提取 `school_v3.blend` evaluated mesh 的 verticality、height、
edge-connected coplanar continuity、thickness／extent，並檢查 AREA、WALKABLE、PORTAL
空間關係。[JSON sidecar](../../data/scene_audit/school_v3_wall_candidates.json) 自動確認
**81 WALL patches**（1F 49／2F 32，7 個來源 objects），**1,491 HUMAN_REVIEW patches**
（674 個來源 objects）。計數為連續共平面 surface patch，不是整個 object；四個 objects
混合兩種 status，因此 object totals 重疊。來源 `.blend` 的 WALL labels 仍未改寫。

[Human-readable report](../../data/scene_audit/school_v3_wall_candidates.md) 包含 reason breakdown、
object／floor review index、每個候選的 bounds、AREA／WALKABLE／PORTAL 與判斷理由。
實際 polygons 對 28 個 PORTAL boxes 做 clipping；自動確認的 aperture intersection 為 0。
不生成 AABB／矩形牆，不補 doorway，不分類整個混合建築 object；window／door panel／
decoration／弱幾何證據留 HUMAN_REVIEW。WALKABLE intrusion 是 section sampling 診斷，
不是完整 collision certification。

使用者已明確確認只有 stairs、沒有 elevator；`AREA_*_ELEVATOR` 是歷史命名，
本輪沒有也不規劃 elevator transition。原始 asset SHA-256 維持
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
size 468,300,506 bytes、mtime_ns 1791198236746106977 不變。所有幾何數值保留
Blender scene units，METRIC／scale_length=1 不當作真實建築尺度認證。

五個 doorway／surface／thin-panel safety tests 通過；本輪完整 regression
**794 tests passed in 56.48s**、Ruff、strict mypy（72 source files）通過。
GT 未參與提取；未跑正式 Cases 1–3，未改 Graph／ranking／reconstruction／benchmark semantics。

### 2026-10-05 — school_v3 人工授權 semantic 補標與保存後診斷

起點 `a0aa1ea`，branch `codex/dataset-infrastructure`。依本輪人工確認的室內可走、
BLOCK→OBSTACLE/BOTH、courtyard／balcony 不可走與 stair floor 規則，保存同名
`blender/school_v3.blend`；沒有 v4／render。另經明確確認，validator 最小診斷擴充
讀取 source-bound intentional non-walkable／cross-floor AREA metadata，以及已分類且
reviewed 的 WALK_* alias。正式 Phase 1 schema／Graph／benchmark／metric semantics 不變。

[Patch recipe](../../data/scene_audit/school_v3_semantic_patch.json) 新增 15 個房間地板、
19 個門檻 surface，14 個既有 floor 扣除實際 same-floor BLOCK polygons（含兩層 OFFICE
延伸）。19 BLOCK 保持 geometry／原 identity，轉為 OBSTACLE；四個原 stair halves
留作 reference，新增 2 PATH meshes／4 ENTRY/EXIT markers，沒有補造 landing／full path。
2F MENSROOM PORTAL 依 2F AREA 明確 bounds 修正 +140 Z。四個廁所扣除 blocker 後為空，
因此不生成 WALKABLE；elevator 仍 HUMAN_REVIEW。

Source SHA-256 依授權由
`26428df2fd395c69673b3e918fb7171b72d77a47d728e6b9cb21bb9da7b8e614` 變為
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`；原始備份與
architecture／obstacle geometry／camera 保持證據見
[update](../../data/scene_audit/school_v3_semantic_update.json)。保存後唯讀 audit 的 SHA／size／mtime
不變。`.blend` 沿用 gitignore 留在本機，Git 保存 source-bound recipe／reports／tools。

[新報告](../../data/scene_audit/school_v3_semantic_validation.md)：30 AREA、48 WALKABLE、
0 WALL、19 OBSTACLE、6 STAIR annotations、28 PORTAL、29 CAM。Coverage PASS/PARTIAL/MISSING
由 2/4/24 到 16/5/4，另 3 EXCLUDED／2 NOT_APPLICABLE；floor 25/165 僅 PROPOSED。
OFFICE 原 AREA denominator coverage 20.5742%→29.6071%，不改為扣 blocker denominator。
Components 9→14（範圍擴大且揭露門外 gaps，非連通改善證明），isolated 7→1。
Queue 49/170/43→33/224/69。原生 20 組雙側 probes 不當作完整連接；獨立 triangle/component
複查確認 6 組 distinct room/corridor 局部接觸，physical approval 仍為 0。

判定 **NEEDS_HUMAN_FIXES**；完整 HIGH／MEDIUM 位置與人工動作見
[位置摘要](../../data/scene_audit/school_v3_semantic_locations.md)。缺口包括 bathroom blocker、
門外 seams、stairs landing／endpoint、WALL／3D collider、floor／camera-plane authority、
clearance／opening 與 elevator roles。沒有開始 Graph／collision pruning／benchmark／Agent。

本輪完整 **783 tests passed in 53.62s，0 failed／0 skipped**；Ruff、strict mypy（72 source
files）通過。最終 report replay、local links、source fingerprint 與 diff checks 的結果
保存在 report JSON 的 `semantic_supplement_review.verification`；metadata 未出現時的十組
既有 semantic fixture reports 保持原語意。

### 2026-10-02 — Semantic completeness validator、Benchmark Protocol 與 comparison reporting

起點 `1750e39`，branch `codex/dataset-infrastructure`，起始工作目錄 clean。
本輪依使用者授權新增唯讀診斷與報告工具；未修改原 Blender scene，也未猜測
`group_*`／`Cube.*`，未開始 school formal benchmarks、Agent、完整 reproducibility、
最終 Blender／Rerun presentation 或 Phase 2。正式 Graph／Reconstruction／MetricConfig
與 evaluation semantics 保持不變。

| Milestone | Local commit |
| --- | --- |
| Semantic validator、config、唯讀 extractor、診斷文件／school report | `56040b7` |
| 10 組 synthetic semantic scenes 與 39 個 regression tests | `b29b9aa` |
| Case 1–4、A–E baseline interfaces、single-factor ablation、metric protocol／4 tests | `40bfea1` |
| Matplotlib comparison generator、native／mock charts 與 summary tables | `249615a` |
| Plotting-only multi-method fixture 與 15 個 reporting regressions | `7f7ea71` |

[Semantic report](../../data/scene_audit/semantic_validation.md) 由原 scene 在兩個獨立
Blender 5.2.1 LTS processes 唯讀抽取：30 AREA、28 PORTAL、29 CAM，WALKABLE／WALL／
OBSTACLE／STAIR 各 0。兩次 JSON 與 Markdown **byte-identical**；source SHA-256
`1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38`、466,332,340 bytes
與 mtime 均不變，沒有 save／render。Queue 為 HIGH 63／MEDIUM 124／LOW 3；HIGH 包含
30 個 AREA missing coverage、28 個 PORTAL disconnected、四種 missing physical labels
與一個 floor authority unresolved。MEDIUM 的 giant／hidden annotation 是 diagnostic
heuristics，不自動判成場景錯誤。

Validator 驗證 mesh holes／rotated triangles／union 不重複計面積、source-bound floor
authority、malformed/non-finite inputs、contact overlap、geometry budgets、stair path
跨孔洞與 naming／collection ownership。Unsupported geometry、floor-plane authority、
clearance／slab opening 維持 REVIEW；diagnostic adjacency 不建立 navigation 或 stair edges。

[Protocol](../research/PHASE1_BENCHMARK_PROTOCOL.md) 固定問題、指標 populations／units、比較與缺值政策，
正式 D／epsilon／K／時間政策、physical authority 與 final baselines 仍為
`UNRESOLVED_RESEARCH_SETTING`／null，formal execution disabled；epsilon=0 仍拒絕。
PRD targets 是 INITIAL_TARGET，六類 acceptance 分開列出，不宣稱 synthetic 驗收成功。

比較工具載入既有 `data/candidates/infrastructure_20261002_final/`，產生
[11 張 SYNTHETIC REGRESSION 圖](../../data/reports/benchmark/benchmark_summary.md)。
Native 未輸出的 projection／recall／impossible transition／path/time error／search
nodes graceful skip 並記理由，不捏造值。新的 plotting-only fixture 產生
[17 張 MOCK VALIDATION 圖](../../data/reports/benchmark/mock_comparison/benchmark_summary.md)，
含三個 cases、A–C IDs、repeated／failed／missing／NO_REFERENCE／empty candidate records；
這不是 baseline A–C 實際執行。Physical／accuracy／Coverage 圖經 visual QA，Coverage
footer 重疊已修正。JSON／Markdown 保存 N/A、availability／status、K、六類 acceptance
與 incompatible-settings REVIEW；methods 不按 GT 排序。

本輪 final checks：**745 passed in 58.78s，無 failed/skipped**；repository Ruff 通過；
strict mypy 通過（72 source files）；diff whitespace、新文件 local links、PNG inventories、
source fingerprint 與 report replay 均通過。新增 58 tests（39 semantic／15 reporting／4
protocol）；起始 687 tests 也已重新通過。Local milestone commits 未 push／PR／merge。

### 2026-10-02 — Blender semantic audit；physical integration 等待人工標記

起點 `bd984f2`，branch `codex/dataset-infrastructure`。使用者要求完成 Blender-backed
Phase 1 Case 1–3 milestone，同時明訂遇到不可信 walkable、未明 collision ownership
或 ambiguous floor／camera-plane mapping 時停止並詢問。先 review PRD／System Design／
Issues、既有 provider／benchmark／Graph／reconstruction／metrics 與 configs／mock。
三組唯讀 review 分別檢查 scene evidence、geometry contract seams、dataset／camera 接入。

新增 [live semantic audit](../../data/scene_audit/SEMANTICS.md) 與可重跑的 Blender／Python
wrapper，功能 commit `a03f993`。Blender 5.2.1 LTS 在 frame 220／subframe 0 評估全部
2,796 objects、2,652
meshes、29 collections；逐筆保存 BB／centroid 方法、mesh statistics、candidate role
與 trust status。30 AREA、28 PORTAL、29 research CAM；WALKABLE／WALL／OBSTACLE／STAIR
objects／collections 全為 **0**，annotation 未升格為 physical authority。
原 `.blend` SHA-256、466,332,340 bytes 與 mtime 執行前後完全不變，沒有 save／render。
29 camera IDs 與 portable calibration 一致，raw world matrices 最大差異 **0**；
這不是 Projection Error 量測，也不核准 floor plane。所有 floor authority 保持 unknown。

Audit review 抓到兩個 empty evaluated meshes 的 origin fallback 被誤標為 surface
centroid／AABB；已修正 `Circle.018`／`Plane.110` 的 audit methods，明示 non-surface／
non-geometry，沒有更改場景。修正後兩個獨立 Blender process／fresh outputs 的完整
JSON 語意相同；2,825 object／collection records 的必要欄位、finite bounds／centroids、
tool hashes 與 source immutability 均驗證。既有 output 的 runner guard 明確拒絕、
不覆寫 artifact、不啟動 Blender。

結果 **STOP_REQUIRED_HUMAN_ANNOTATION**；已詢問人工 source-bound WALKABLE surfaces／
connectivity／anchors、WALL／OBSTACLE movement／occlusion ownership、floor planes／camera
binding 與 physical clearance/contact policy。可透過 sidecar 保留原檔；尚未實作
sidecar schema／loader。Geometry provider 可用 additive platform-independent interface，
但本輪僅完成唯讀 review，沒有實作正式 contract、pruning 或 geometry authority。
School Cases 1–3／datasets／benchmarks／metrics／physical Rerun／A–C baselines 仍未建立；
未擴 fake fixtures、未修改 core／正式 schemas，未進入 Agent／Phase 2／Case 4。

完整 regression：**687 passed in 45.61s，無 failed/skipped**；`uv run ruff check .`
通過，`uv run mypy` 通過（69 source files），`git diff --check` 通過。既有 GT poisoning、
isolation、provider、termination、determinism／failure reporting 測試全部維持。
這些結果不代表 school physical integration 已完成；下一步需先取得人工標記。

### 2026-10-02 — Boundary / Failure-mode / Adversarial validation

起點 `b11edb9`，branch `codex/dataset-infrastructure`。先讀 PRD／System Design／
Issues and Decisions、既有 mock／tests／benchmark／metric configs；基線重新驗證
547 passed in 46.98s。本輪只新增小型 boundary fixtures／regressions，沒有一般正常
scenario、Blender scene 修改、render、Agent ranking 或發布；正式 domain schemas 不變。

| 分組 | 新增 tests | Commit |
| --- | --- | --- |
| Reachability／time／speed／floor；Graph fixture adapter | 15 | `f9246b6` |
| Observation duplicate／ordering／short/adjacent/missing gaps | 20 | `a76eb76` |
| Top-K／deterministic equal-distance tie | 17 | `09e6606` |
| Projection／provenance guards | 31 | `dcd7b2e` |
| Config／fake AABB collision boundaries | 24 | `7e59c06` |
| Termination／search guardrails | 20 | `9082528` |
| Four poisoned GT patterns／process determinism | 5 | `1f07701` |
| Benchmark failure reporting／formal Top-K consumers | 8 | `a95b595` |

新增總數 **140**。上述分組包含 parametrized cases，最後以 pytest collection／完整
執行總數核對。23 組 Graph specs 都是 2–3 nodes／最多 8 edges；20 min branching cycle
由 node budget 在 12 expansions 停止，1 hr cycle 由 path-length eligibility 在 15
expansions 窮盡。全部六種既有 termination 已覆蓋；未創造 unsupported hops/window
aliases 或 Agent/runtime reasons。Short recovery 保留獨立 endpoints/source binding；
duplicate policy 明確拒絕，全部 120 input permutations 的 inference semantics 相同。

新 regression 真正抓到的既有缺口集中於 benchmark reporting：invalid case rejection
沒有 structured report、JSON/Markdown summary 遺失 rejection reasons／endpoint 描述，
Markdown 未明示 NO_REFERENCE。Production 只修改 `benchmark/runner.py`／`reporting.py`：
保留 structured diagnostics 與既有 exception re-raise；不捏造 Graph termination，
不產生成功 artifact。未知 consumer RuntimeError／ValueError 仍原樣拋出；已知 contract
errors 才分類為 input rejection。Graph／projection／aggregation／ranking／metric semantics
沒有變更，這些新增測試未發現需要修補的既有核心 bug。

GT poisoning 使用不同 path、超大速度、錯誤 floor 與固定混亂座標，保存相同 reference
binding／time／seed。完整 aggregation／BoundGapEvent（candidates/order/IDs/termination/
timing）與 no-GT/clean-GT inference 相同；只有 evaluation 改變，K=3 Coverage 由 true
變 false、ADE 改變，physical metrics 不變。Determinism stress 三組 adversarial fixtures
各 4 次同 process、3 次新 process，共 21 次執行／9 個新 process，變更 hash/random
seed、CWD/output directory；完整 inference、metrics.json 與 JSON summary semantics
一致。排除 runtime/Git identity/RRD SDK metadata，不要求 binary byte identity。

2026-10-02 使用者確認 collision Top-K pruning **UNRESOLVED**，現階段只做
evaluation-only positive AABB／threshold tests；epsilon=0 明確拒絕，正式 Schema 不變。
沒有逐 transition rejection-log、missing-frame marker、coordinate-origin attestation
或獨立 ImpossibleTransition metric schema；範圍詳見 [boundary fixtures](../../data/mock/boundary/README.md)。
ISSUES_AND_DECISIONS 只新增真正影響物理可行性語意的 collision authority 未解問題。

最終 code checkpoint `a95b595`：**687 passed in 48.05s，無 failed/skipped**；
`uv run ruff check .` 通過、`uv run mypy` 通過（69 source files）、`git diff --check`
通過。uv sandbox cache/SystemConfiguration 限制以獲准的 unsandboxed uv checks 解決，
沒有修改 dependencies／uv.lock。其後只更新文件，不把這些結果冒充正式 Blender
walkability/collision certification 或研究 benchmark 驗收。

### 2026-10-01 — Deterministic fake-data 後半段閉環

起點 `2a988df`，branch `codex/deterministic-downstream-scenarios`；使用者授權四組
可替換的 fake scenarios，完成後停止，不進入完整 Agent Semantic Ranking。

| 功能 | Commit |
| --- | --- |
| 固定 seed 20261001 fixtures 與分離 GT／inference JSON | `ef1e1ca` |
| 通用 Graph pipeline、reachability／min time／不可能轉移／Top-K／termination tests | `93a6bee` |
| M6 完整 frame schema 重驗、防止 provenance bypass | `c3387a2` |
| Timed Event hypotheses、direct／slower／dwell／detour 與 temporal slack | `d7db5ca` |
| ADE／FDE／route Top-K Coverage／continuous AABB／speed／directed corridor metrics | `723bbbe` |
| Rerun adapter、所有候選／hypotheses／provenance／GT debug overlay 與1Hz播放 | `737010d` |
| 完整 runner、所有 configs 物化與 Ground Truth isolation integration | `6066c9e` |

`6066c9e` 完整程式內容的驗證：**347 passed in 26.14s，無 skipped／failed**；
Ruff 通過、strict mypy 46 source files 通過、diff check 通過。指令由 uv 管理，使用
`UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync`，沿用 locked installed
environment。Sandbox 內 uv online discovery 會觸發 macOS SystemConfiguration panic，
既有 Blender CLI tests 在 sandbox 內 SIGSEGV；完整 pytest 在獲准解除 sandbox 後通過。
沒有修改 dependencies／lock 或 render／save Blender assets。

四組實際閉環輸出在本機 ignored `data/candidates/fake_downstream_20261001/`：

| Scenario | Routes／hypotheses | Primary ADE（m） | minADE@K（m） | minFDE@K | Coverage@K |
| --- | --- | --- | --- | --- | --- |
| Single Path | 1／1 | 0 | 0 | 0 | true |
| Branching Top-K | 3／5 | 7.8021081352 | 2.7079e-17 | 0 | true |
| Temporal Slack | 2／4 | 0 | 0 | 0 | true |
| Simplified Stair | 1／1 | 0 | 0 | 0 | true |

全部 COMPLETE；synthetic wall AABB、directed corridor、max speed 的 collision／constraint
rate=0。Branching GT 是第三條，Coverage@1=false；ADE/FDE 已知 numeric oracle 為1／2。
Temporal Slack 最短時間20s、gap180s、slack160s，保留 slower movement、dwell、detour，
不賦予行為機率。四份實際 RRD 以 SDK RrdReader 重開，確認 footer/store 與 entity data 可讀。
18 個 Rerun tests 另驗證3個Top-K、GT debug labels、provenance與20秒路徑中點播放。

GT isolation integration **12 passed**：禁止真值檔案讀取仍能完成四組推論；改變GT只改變
evaluation，candidate／Event JSON 不變；拒絕 JSON 注入、forged provenance、candidate
truth／probability payload。另有8個M6 copy／construct frame bypass regression cases。
Source／research copy SHA-256 均仍為
`1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38`。

這是 configured synthetic interface regression，不是 school walkability／stair／Mesh collision
驗證、formal benchmark 或完整研究驗收。有效接入缺口留在 handoff；沒有 push／PR／merge。

本文件保存已完成工作與當時驗證證據。即時待修項目見 [CODEX_HANDOFF](../operations/CODEX_HANDOFF.md)，持續適用的規則見 [DEVELOPMENT_RULES](../specs/DEVELOPMENT_RULES.md)，實際能力契約見 [DATA_SCHEMA](../specs/DATA_SCHEMA.md)／[INTERFACES](../specs/INTERFACES.md)。下列內容從既有交接整理，不代表本次重新執行全部測試，也不代表正式 school benchmark 已完成。

### 2026-10-01 — M0–M4：環境、稽核與合成模擬

| 階段 | 已完成內容 | 主要 commit |
| --- | --- | --- |
| M0 | 文件、Git、uv project 與 Blender CLI 檢查；pyproject／uv.lock 初始化 | `3238ec7` |
| M1 | 唯讀 school_v2 scene audit、JSON／摘要、結構幾何補充分析、來源綁定與研究副本 | `ab8a9d9`、`c3638c5`、`7add28b` |
| M2 | 可設定時間路徑、確定性取樣、temporary target proxy 的 Blender world-position 求值、GT JSON／CSV 匯出 | `82fa2a3` |
| M3 | Camera schema、29 台相機的 pose／intrinsics 抽取、world→pixel、FOV／clip 與 Blender parity 檢查 | `251db8f` |
| M4 | evaluated Mesh point raycasts、OBSERVED／GAP 與拒絕原因、來源 SHA 綁定、GT-free 2D evidence 匯出 | `58a8099` |

同期完成單位／相機 convention 記錄 `c3a02c7`、暫時中性材質 override `52b2b6e`，以及將 school 樓梯不確定性限縮到 school 跨樓層配置的文件修正 `2e9dd29`。固定使用 29 台 `CAM_*`、1 unit = 1 metre 的採用決策留在 [ISSUES_AND_DECISIONS](../specs/ISSUES_AND_DECISIONS.md)，此處只記錄完成事實。

稽核證據存於 [scene audit 摘要](../../data/scene_audit/README.md)、[幾何補充](../../data/scene_audit/GEOMETRY.md) 與對應 JSON：

- Inventory 為 2,796 objects（2,652 Mesh、30 Camera）、29 collections、260 materials、447 images、489 modifiers、12 actions；其中 imported SketchUp Camera lens 非有限，29 台 `CAM_*` 為研究候選。
- 18 個 imported lights、8 個高面數物件及可能多餘的材質／貼圖只報告，未清理。
- Geometry follow-up 分析 370 個結構 Mesh、25,098 triangles，辨識主要 floor candidates `z≈20.07885`／`161.811096`；庭院另有 `z≈0.000112` 候選。兩個樓梯 annotation regions 未找到 Mesh 支持的連續上升路徑。這不是全場 NavMesh、walkability 或樓梯不存在的證明。
- 研究副本 `blender/working/school_v2_research.blend` 與原檔 byte-identical，沒有 save／render；temporary neutral override 不更改來源 slots、UV、images。
- `configs/trajectory_fixture.json` 為 factory synthetic 設定：0／2／4 秒 keyframes、10 Hz、seed 42，取樣器可產生 41 筆；seed 只記錄，基準取樣器不使用隨機性。這不是 school route 或已保存的 dataset。

### 2026-10-01 — M5–M8：契約、反投影、導航與搜尋

| 階段 | 已完成內容 | Commit |
| --- | --- | --- |
| M5 | Observation、ProjectedPoint、CandidateTrajectory、Event、ReconstructionResult、provenance／termination、nullable Phase 2 欄位、serialization tests 與 protocols | `1dcce12` |
| M6 | 一台 Camera 綁定顯式 unit-normal Plane、ray-plane inverse projection、axial clipping、plane identity／incidence quality 與 typed geometry failures | `7e952ae` |
| M7 | Directed configured navigation 與 Camera Topology 分離、ordered edge cross-validation、node 定位、3D length 與 canonical minimum-distance routing；generic synthetic stair 契約／測試 | `94ee2cd` |
| M8 | Exact topology-authorized routes、continuous anchors、速度／時間／長度／detour 剪枝、bounded Top-K、corridor 去重、candidate identity、搜尋停止狀態與 synthetic major-flow integration | `d6620b4` |

M5 最初交接中的 completion 預設與空 Observation shell 契約問題已收尾；M8 另實作輸入拒絕檢查：

- `ReconstructionResult` 檢查 termination／complete 一致性，`NO_FEASIBLE_PATH` 不接受 candidates。
- 空 OBSERVED shell 可宣告區間，但不等於有效 Evidence；M8 拒絕沒有 PROJECTED endpoints 的輸入。

M8 檢查確認有效 K 採 method／policy 較小值；只在看到 K+1 個 distinct feasible corridors 時回 `MAX_PATHS_REACHED`。Node／branch／timeout 終止標為 incomplete；同 corridor 去重、不加入未授權 connector 或另選 shortcut。這些屬於當時實作驗證事實，完整契約留在 [INTERFACES](../specs/INTERFACES.md)。

### 2026-10-01 — 驗證與 Review 證據

| 當時內容／checkpoint | 執行結果 | 說明 |
| --- | --- | --- |
| M5 完整內容；記錄於 `1dcce12` | 106 passed in 23.82s，無 skipped／failed；Ruff、mypy 21 source files、diff check 通過 | 當時 M5 完成驗證，不是 M8 結果 |
| M8 完整內容；記錄於 `d6620b4`／`c04435f` | 219 passed in 25.73s，無 skipped／failed；Ruff、mypy 33 source files、diff check 通過 | 當時 M8 完成驗證 |
| Review 起點 `baf9074`；結果記錄於 `e27d1dd` | 219 passed in 25.02s，無 skipped／failed；Ruff、mypy 33 source files、diff check 通過 | 重新檢查 M5–M8，未修改程式 |

重跑使用 `uv run pytest`、`uv run ruff check .`、`uv run mypy`、`git diff --check`。在上述 review 另確認來源與研究副本 SHA-256 相同：

```text
1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38
```

當時 Blender CLI 為 `/Applications/Blender.app/Contents/MacOS/blender`，5.2.1 LTS，build `9e2066aef7ef`。Blender-backed tests 使用 transient factory fixtures；測試暫存輸出不是 repository 的正式 dataset，沒有產生 render。Blender adapters 使用標準函式庫與 lazy bpy／mathutils，未假設 Blender Python 與 uv 共用套件環境。

Review 的證據範圍：

- M7／M8 在 configured-route 契約內未發現新的可操作正確性問題，正常推論 imports／scoring 未發現 GT 讀取。
- Walkability／collision safety 來自受信任的顯式 route 設定，不是 Mesh 障礙／淨空檢查；`WALKABLE` flag 不證明 school collision rate = 0。
- M8 integration 為 synthetic camera／2D evidence→plane projection→configured graph，不是 school Blender trajectory→evaluation 的正式閉環。
- Projected endpoints 要對齊 configured nodes；沒有 arbitrary-point connector。Wall-clock timeout 結果可能因負載不同而改變，不等於所有 timeout outputs 可重現。
- Review 找到 M6 `project_frame()` 未重驗完整 ObservationFrame 的 provenance bypass：`model_copy` 產生非法 provenance 仍可被投影。當時僅記錄、未修程式；有效待修狀態在 [handoff](../operations/CODEX_HANDOFF.md)。這不是已確認的正常流程 GT 座標洩漏。
- Projection Error evaluation、M9 reconstruction、M10 metrics、M11 visualization、formal benchmark 均未在這些檢查中完成。

### 2026-10-01 — 資料盤點、發布與交接整理

- `74c66bd` 新增日期化 [data inventory](../../data/README.md)。當時 Git 追蹤的是 audit bundle；唯一已物化 runtime artifact 為本機、ignored 的 29-camera catalog，GT／Observation／candidate／metric／`.rrd`／rendered-image dataset 均未物化。
- `baf9074` 記錄先前經明確授權的 GitHub 發布；`83ca3f8` 新增 project README。後續 review 沒有重新透過網路驗證 GitHub，不把本機 remote reference 當永遠有效的遠端狀態。
- `e27d1dd` 更新 M5–M8 review handoff，記錄使用者暫緩 school 樓梯／跨樓層／正式 Case 4、保留 generic synthetic tests；沒有修改程式、資產或 push。
- 本次以 `e27d1dd9494c921aa34027012e7b6e693dc6a5ba` 為文件整理起點，將歷史完成／驗證移至此紀錄、持續規則移至 DEVELOPMENT_RULES，精簡 CODEX_HANDOFF，並補文件導覽。沒有開始 M9、修補 M6、生成資料或渲染；本次僅做文件內容／連結／diff 檢查，不重跑上述歷史測試。
- 本次文件驗證：4 份雙語 Markdown、57 個本機連結與 fence／有效待修／暫緩狀態檢查通過；diff check 通過。歷史測試數字另以對應 commit 保存的 handoff 核對，不沿用未核實的快照。

## English

### 2026-10-08 — Exact corridor approval and independent numerical regeneration

The direct human reply approves exact proposal `752404…1bad`; a separate immutable receipt
binds the original reply, recording timestamp and exact scope without superseding approvals.
Actual application passes all six original numerical cells, issuing union certificate
`f8fe588620b4f871d49f6ed50d61d6185c8648b5551d9b7528dfb7c696cb06c5`.
A clean independent `d8b94a6` checkout regenerates the complete proofs and passes
PASS_LOCAL_UNION_REGENERATED; three producer files match and all expected hashes are pinned.
Source hash/size/mtime, 30 protected inputs and the historical review/preview packet remain
unchanged. Verified physical evidence is reused; no new Blender export, simulation, GT,
benchmark or RRD is generated. No code edits or full-suite rerun are claimed in this turn.
Current approval/application/verification evidence and the next-chat release handoff are linked
in the Chinese entry above. Existing office CLIs require additive scoped adapters; same-camera
HOLD, identical-eligibility exhaustive inventory and frozen fresh 5 Hz execution remain.
Audit the original Case2 two-sided-portal requirement against existing approved evidence;
no portal role is added by the corridor receipt. Full Exit stays blocked, Case4 deferred and
Phase2 frozen, with no freeze tag or main merge.

### 2026-10-07 — Post-approval implementation handoff checkpoint

The user authorized a new conversation for substantial implementation of the remaining
original Phase 1 sprint. Added a focused handoff and hash-bound checkpoint; shortened the
current handoff to active work. Verified source SHA, 29 locked inputs, 57 original frames,
submitted/durable decision equality and the frozen Phase 2 ref. Documentation/checkpoint
changes only: no application, certificate, formal run, render, push, merge or freeze tag.
The 177 tests/Ruff/4-tool mypy record belongs to historical approval commit 10a3fcc and was
not rerun here. The new task receives the exact handoff commit and continues autonomously.

### 2026-10-07 — Four explicit human approvals recorded

The user confirmed the room/cameras, accepted the rigid marker recommendation and approved
the remaining items. Recorded the four existing profiles: bounded source surface, rigid
offset, ADE<0.50m and0.7904m/s with supported departure dwell. Only editable decision and
reviewer/time fields changed; immutable e105 payload and original template remain.
Read-only source/ancestry/29inputs/57frames validation passes. The dashboard shows4/4
approvals and0human blockers; completed source decisions supersede stale cache without
reading, deleting or writing that cache.177related tests, repoRuff, four strict review-tool
typing checks and diff gate pass. No authority application, certificate regeneration,
formal Cases, render, source changes or publication occurred.

### 2026-10-07 — HR02 source-camera and landmark/foot evidence

Added read-only HR02 evidence from base `7140062019a00256df0543d7dc3e513c53090d9d`:
source frame220/subframe0, unchanged calibration, public projections/frozen GAP candidate
and 200 full allowed evaluated VIEWPORT landmark/foot ray queries. All26observed landmarks
are clear; feet have10CLEAR/90OCCLUDED, including16clear-landmark/occluded-foot records.
Both cameras lie within the AUDITORIUM annotation AABB and outside OFFICE, which does not
certify actual room ownership. The pending1.3597349529m offset is not ceiling height.
Only intended room/cameras and tracked body-point semantics remain human questions;
existing fallback adds no decision. All four choices remain null. Repeated source queries
match exactly, without claiming the formal fresh benchmark gate. The diagnostic viewer
is additive; old renders remain. No GT/evaluation/recipe reads, original scene changes,
authority promotion, formal Cases or publication occurred. Grey stills do not certify CV pixels.
Eight new1920x1080views retain all2,576instances/5,585,184triangles. All older images remain.
172related tests, repoRuff, mypy93core/six review tools and diff gate pass. Native50frame
scrubbing is synchronized with one layout geometry; full playback terminates normally.
The original payload and all four pending choices remain unchanged.

### 2026-10-07 — Stable model/topology playback layout

From `095af134dfb22eab51277e7affcce1198f67b0fd`, loading status overlays the model,
and status/control dimensions remain fixed. At both717/1124px content widths,
50scrubbed frames and70playback samples retain identical model/graph/control/card
rectangles. All original renders, graph/person data,33existing hash-bound inputs and
pending decisions remain unchanged.15related tests, Ruff, mypy93core and diff checks
pass; formal/GT benchmark tests were not rerun.

### 2026-10-07 — Synchronized person position in model/topology review

Starting from `e4b7821f1e6c282ff571f6d56322b74e6354a958`, each existing motion frame
now locates the person as P(t) at the frozen footpoint, with a separate L(t) landmark.
The model and fixed world-XY diagram identify N1 at4s, the existing E1 candidate
during GAP, N2 at9s, and positions outside this GAP graph before/after those endpoints.
Nodes and vertices remain fixed. Original float32 render positions stay unchanged;
node association uses public double projections and the existing1e-6m tolerance.
Images, markers and status commit together after load, with stale-load protection.
All original edges, renders and pending decisions are preserved.

Five new regressions cover all50positions, graph preservation, relation labels,
height modes, playback and asynchronous loads.79related tests, repository Ruff,
mypy for93corefiles and5reviewtools pass. No GT access, source/authority/protocol
changes, formal execution or publication occurred.

### 2026-10-07 — Complete framing, source cameras and HR02 body-height clarity

Starting from `92366d882a23c356f56ea87830463d6417576875`, the existing review UI now
fits the complete first-floor context, locates both native source cameras through a
25-frame office approach, and distinguishes public observation availability from
display camera guides. HR02 adds an illustrative person, an exactly projected foot
callout and a separate 1.70m body-height ruler. Its 1.359735m offset is landmark-to-
prospective-footpoint, not floor-to-ceiling; placement and binding remain pending.
All older displays are retained, with a manifest-versioned iframe preventing stale
browser content. Native UI checks cover the map, camera edge indicators and HR02 body.

The 28 new PNGs total 13,281,548 bytes. All 181 preserved artifacts, 29 frozen inputs,
four pending decisions, the payload and original source hash remain unchanged.
74 related tests, repository Ruff, mypy for 93 core files and four review tools, and
diff checks pass. A native UI JPEG and integration receipt record the verification;
an unadopted lighting trial remains separately archived. No GT access, source edits,
authority promotion, formal execution, push, merge or tag occurred.

### 2026-10-06 — Finalization blocked checkpoint

The exact physical/projection checkpoints are selectively integrated; source milestone
`e9ade14ffd0838712935f210f17c947563a08a29`. Fresh materialization/export, shared A/B/C
adapters, optional projection hook, GT poison/order/fresh-process checks and six RRD
reader checks pass diagnostically. The clean checkout matches15 dataset,217 replay,
19 report artifacts and baseline regression. Tests1532 passed/5 historical school-v2
skips; Ruff, mypy92 files and diff check pass. Formal Cases1–3 remain NOT_RUN;
the single human gate is pending. The final report/experiment log own details;
cleanup is inventory-only, Phase2 frozen and no freeze tag or main merge.


### 2026-10-06 — Lightweight physical-policy checkpoint

`phase1/physical-policy-lightweight` starts directly from synchronized base
`0bab8ac262b93f3c8babad69432744e7e4d1c541`. Full local evidence commit
`c5956dc825f669e28e2694578be0fed97432a786` is a provenance reference, not an ancestor.
Code/config/tests/docs, experiments and summaries were selectively retained. Historical
producer/config/lock bytes and 12 historical JSON documents, including the original manifest,
remain unchanged.
No rewrite, rebase, amend, force push, merge or Finalization Sprint was performed.

The [materialization contract](../operations/PHYSICAL_EVIDENCE_MATERIALIZATION.md) and
[artifact manifest](../../data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json)
bind source, byte/content hashes, commands/configs, producers and semantic roles. Four raw gzip
files totaling **48,362,311 bytes** and the local receipt are precisely ignored. The wrapper
runs unchanged producers in an isolated workspace with CPython 3.12.12, the committed lock,
and Blender 5.2.1 LTS build `9e2066aef7ef`; only fully verified raw evidence is installed.
Historical atlas timestamp normalization is explicitly recorded separately from the actual
unchanged source before/after fingerprint. Scene bytes/size/mtime and original provenance
remain unchanged.

An independent clean temporary clone from the base contained no full-commit object.
Install via `uv sync --frozen` passed. Without-artifacts pytest: **1365 passed / 8 skipped**
(88.70 s), including 3 explicit physical-evidence skips and optional historical school-v2
source/calibration skips. Strict missing-evidence profile: 6 passed / 3 explicit prerequisite
setup errors, as designed. Tests never download or generate evidence. Historical unit hash
checks now use 4,140 bytes of exact committed config fixtures; optional ignored camera
provenance is checked separately without weakening hashes or requiring Git history.
The isolated branch's requested `uv run pytest` passed: 1365 passed / 8 skipped (75.54 s).

Fresh-clone materialization regenerated the atlas from the preserved scene, rather than copying
full-commit blobs: 660 objects, 1,548,921 triangles, 26 complete selections. All four raw byte
and canonical JSON hashes exactly matched. Complete policy replay took 207.46 s and preserved
scale/policy APPROVED, 48 supported subdomains, 58 approved components across 5/19 obstacles,
8 HUMAN_REVIEW portals, Stair A/B HUMAN_REVIEW, overall PARTIAL_APPROVED and collision 4→2.
Complete local islands remain 0 and global gates remain closed; thresholds, GT isolation and
research conclusions were unchanged.

The complete fully materialized strict profile passed: **1368 passed / 5 skipped**
(79.88 s). All 9 current physical-bundle checks passed; remaining skips concern only
historical school-v2 fixtures. Read-only `--verify-only` passed and materialization left
the fresh checkout clean. Ruff and mypy (91 source files) passed in both profiles.
Diff checks and 216 local links/anchors across 13 documents passed with no missing-artifact links.

Before this log entry, candidate unique reachable blob payload was **2,609,291 bytes** versus
**50,897,608 bytes** for the full checkpoint (**94.87% smaller**). Non-thin single-thread
candidate-minus-base pack was 522,863 bytes versus 32,076,978 bytes by the same method.
These are incremental payload metrics, not total repository size or negotiated wire traffic.
The largest added files are listed above; largest whole-tree files are inherited base artifacts:
source mesh evidence 10,996,697 bytes, school-v2 scene audit 6,750,115, school-v3 semantic audit
6,617,918, approved-scale geometry 6,496,240 and original geometry-authority geometry 6,496,191.
No `.blend`, `.rrd`, renders or excluded raw gzip are tracked. Existing benchmark PNGs are plots.

### 2026-10-06 — Approved physical policy and source-bound partial authority

The clean scale-approved checkpoint `0bab8ac262b93f3c8babad69432744e7e4d1c541` passed
1199 tests, Ruff, mypy (83 files) and diff checks. The existing
`phase1/physical-authority-resolution` branch was pushed and live origin SHA verified;
`phase1/physical-policy-approval` was created without merge, rebase or history rewrite.

The [authority report](../../data/scene_audit/phase1_physical_policy_approval_20261006/authority.md)
and [experiment log](EXPERIMENT_LOG.md) retain current evidence. Approved policy, actual
source floor supports and 58 exact components across five obstacles yield PARTIAL_APPROVED.
Forty-eight supported subdomains include 45 fully covered annotations and three partial
ones; 38 historical offset diagnostics are explained and ten budget-limited regions recovered.
Whole obstacle volumes, eight portal pairs and both stairs remain REVIEW. WALL classification
stays 73 HIGH / 1422 REVIEW / 77 REJECTED. All five searched complete local islands remain
REVIEW due to unknown enclosure/degenerate source geometry. Positive component probes filter
4→2 before K; formal local/inference pruning stays disabled.

Fixed concave closed-volume ray tangency and double floor-contact tolerance; added floor
scope, provenance and order guards. The full atlas has 660 objects, 1,548,921 triangles and
26 complete selections, including hidden/enclosing geometry. Source SHA, 468300506 bytes
and mtime remain unchanged. No scene scaling/modification, guessed roles, fabricated geometry,
GT input, MetricConfig/benchmark/ranking change or Case 1–3 execution occurred.

Final **uv run pytest: 1352 passed, zero failures/skips, 94.81 s**; 153 new tests and all
1199 baseline checks pass. Ruff, mypy (90 files) and diff checks pass. The initial new-test
failures exposed an incorrect historical offset count and a missing enclosure-selection
fixture field; both were repaired and the full suite rerun without lowered thresholds.
The 175 checked task-document internal links are valid. Historical artifacts/provenance
remain intact; active context points to the new bound gzip bundle.


### 2026-10-06 — Approved Phase 1 architectural scale

On `phase1/physical-authority-resolution` from checkpoint
7798f0cfd0b4501d0831c82b06d35ddf21d8da29, the user explicitly approves
**1 BU = 0.0247 m**, **APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING**. The
[source-bound record](../../configs/architectural_scale_school_v3.json) defines a research-model
setting; external dimensions are no longer an approval prerequisite. Earlier provisional
and 1:1 checkpoint entries below remain historical records.

The [active physical context](../../configs/physical_context_school_v3.json), school-v3 configs,
provider authority, measurements and validation docs use the approved ratio. The
[geometry/scale validation](../../data/scene_audit/school_v3_approved_scale_20261006/geometry_scale_validation.md)
confirms all 1,669 surfaces retain identical native vertices, faces, planes and ownership.
The 0.28 BU doorway guard becomes 0.006916 m with unchanged native diagnostic boundaries.
Source-bound adapters normalize camera/plane/projected/navigation inputs, speeds and length
bounds; SI body/clearance/contact policy converts to BU without filling pending values or
approving authority. Scalar ADE/FDE reports retain BU and add metres without recomputing
Coverage or epsilon. Existing runner/pilot flows keep legacy contracts until callers explicitly
normalize complete native inputs. Formal schemas, Graph/Top-K, benchmark semantics and GT
isolation remain intact.

Read-only Blender measurement produces 37 SANITY_CHECK_EVIDENCE rows and 285 consistent
BU/metre pairs. Floor support rise 141.732246 BU becomes 3.500786 m. Reliable sections show
roughly 0.875–1.750 m doors, 3.015–3.598 m corridors and 6.321×9.676 m classrooms, without reliable
evidence of implausible scale. Five meeting-room/gallery nearest-hit anomalies retain boundary
review and are not confirmed giant doors or tiny rooms. Original v3 SHA/size/mtime stay
identical; no geometry scaling, save or render occurs. Historical artifacts and BU provenance
remain. Scale approval does not approve floors, stairs, obstacle volumes or body/clearance
policy; all four formal scopes still refuse consumption and physical authority stays PROVISIONAL.

Validation catches a diagnostic unit bug: native stair `path_segment_points_json` was compared
directly with metre meshes. Only this unit boundary is fixed; explicit `path_points_m` and
clearance_m stay SI. New regressions cover alignment/direction/anchors/joins and authority
binding. The first full run finds 3 synthetic obstacle assertions coupled to the active school
scale; binding those fixtures to their original generic 1:1 context preserves every assertion
and production calculation. Final `uv run pytest`: **1199 passed in 91.34s, zero failures/skips**;
Ruff, mypy 83 files, strict mypy for both scripts and diff check pass. Input/code/artifact hashes
are verified. This approval is an independent commit without merge/rebase/history rewrite,
formal Cases 1–3, Agent work or benchmark execution.

### 2026-10-06 — Provisional school-v3 scale measurements and source review

On `phase1/physical-authority-resolution` from `cdeee3e316e88c87ab63cdcf3acb360485f00dd6`,
the user proposed 0.0247 m/BU and confirmed no reliable measured/design dimensions exist.
Architectural scale remains HUMAN_REVIEW. [Scale review](../specs/SCHOOL_V3_SCALE_REVIEW.md) adds
37 automatic measurements, six unresolved portal normals and five human-review anchors.
Annotation spans and source cross-sections are separate; 248 hits cite object/evaluated polygon
identity, vertices, endpoints and height-profile ambiguities. Proposed sizes include restaurant A
0.875198 m, office 1.750392 m, CLASS201 Y 9.675786 m, corridor03 3.030764–3.131431 m,
and source floor rise 141.732246 BU / 3.500786 m. None approves physical aperture or scale.
Two independent Blender invocations/output directories reproduce measurement semantics;
input/code hashes and original source SHA/size/mtime are preserved.

The imported camera has zero active consuming references; ignore it while retaining the
object and all 29 CAM cameras. Elevator is NOT_APPLICABLE with historical AREA IDs retained.
Canonical path/hash references preserve historical duplicates and provenance; 1,669 geometry
surfaces contain no exact duplicate groups. Measurements are generated, and unclassified names
grant no authority. Formal schemas/configs, core inference, metrics, prior artifacts and GT
isolation remain unchanged; no model mutation, rendering, formal benchmark, merge or push.

Fresh validation: pytest **1131 passed in84.83s, zero failures/skips**; Ruff, mypy81 files,
standalone strict mypy for the new script and diff check pass. Eleven targeted diagnostic tests
pass in0.05s; 52 internal file links pass. Physical authority remains PROVISIONAL.

The subsequent staged check caught CSV CRLF as trailing whitespace. Retain `84ff020` and
append an LF-writer fix with a regression assertion; do not rewrite history. Fresh read-only
exports preserve every measurement value; JSON changes only its producer-script hash.
The manifest retains the previous JSON/CSV hashes and commit reference. Final rerun:
**1131 passed in85.57s, zero failures/skips**; Ruff, mypy, script mypy and diff check pass.
All92 internal file links pass; source and previous benchmark/pilot artifacts remain unchanged.

### 2026-10-06 — Published geometry checkpoint and physical blocker review

The requested geometry-authority checkpoint bb66bb74a4a76430f6fa8f79672345385a79e3f0
starts clean. Fresh validation passes996pytest tests in85.24s without failures/skips,
Ruff, mypy77sourcefiles and diff check. A normal push publishes phase1/geometry-authority;
live origin SHA matches exactly. The independent phase1/physical-authority-resolution
branch starts from that exact commit without changing the checkpoint or merging/rebasing.
The [checkpoint record](PHASE1_GEOMETRY_CHECKPOINT.md) binds recovery and local assets.

The [physical report](../../data/scene_audit/phase1_physical_authority_20261006/resolution.md)
and source-bound artifacts review157,589 selected triangle records in69 spatial regions.
Selection boxes never become colliders. Three unrelated obstacle regions retain explicit
export-budget limits. All eight obstacle/portal pairs remain physical REVIEW: two
meeting-room overlaps are explained by annotation depth margins, while bathroom/main
entrance blocker identity, footprint extent or portal placement remain unresolved.
The19 approved roles retain unapproved footprint volumes; no reliable one-to-one source
mesh ownership is inferred. Zero scene repairs are applied; footprints/portals stay intact.

All48 floor scopes remain REVIEW:38 measured source-support exceptions and ten bounded
measurement cases with partial rays. Dominant1F/2F source support is near20.07885/161.811096,
not proposed25/165. Annotation volumes and v2 camera calibration do not approve v3 physical
planes. The accepted1BU=1m computation convention remains unchanged. Actual stair A/B
context contains932/422triangles but no shared landing supporting the proxy-half endpoints.
ENTRY/EXIT source-horizontal distances are2.783161/.811096 for A and5.047535/3.061096 for B,
above the existing.25join tolerance. Openings, clearance and complete connectivity remain
REVIEW; no landing/connector or original/derived asset changes are invented.

An additive physical-authority-v1 sidecar separates policy and purpose-specific scopes
without altering geometry-v1 or formal domain schemas. Pending body/reference/dimensions,
body/portal clearances and contact comparisons remain nullable, config-driven and REVIEW.
All four formal gates refuse; overall authority stays PROVISIONAL and formal hard-pruning,
free-space/topology certification and physical-validity metrics are not ready. The73HIGH
walls remain provisional with doorway protection and original thresholds;1422ambiguous
patches are not forcibly approved. Benchmark, ranking, GT isolation, formal Cases1–3,
Agent and Phase2 remain unchanged or unstarted.

Fresh final checks pass **1120pytest tests in86.99s**, no failures/skips; Ruff; mypy81source
files; diff check. The124new regressions cover policy/scope/source forgery, GT guards,
partial versus complete authority, actual floor/stair/conflict evidence, budget protection
and report formatting. Independent replay preserves measurements and authority decisions;
the original source hash/size/mtime remains unchanged.

### 2026-10-06 — Independent Phase 1 geometry authority milestone

The independent `phase1/geometry-authority` branch starts from stable checkpoint
`51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e`, without rewriting or merging history.
The [authority report](../../data/scene_audit/phase1_geometry_authority_20261006/authority.md)
and source-bound manifest/exact mesh/portable geometry revalidate 81 seeds plus 1,491
review patches: **73 HIGH_CONFIDENCE / 1,422 HUMAN_REVIEW / 77 REJECTED / 0 APPROVED**.
Eleven seeds are downgraded (five continuous WALKABLE intrusions, six insufficient actual
supports), while three reviewed patches are promoted. Original thresholds remain intact.
Actual triangle unions and continuous intervals catch intrusion/absent support missed by
the previous sampled/bounding evidence. All 28 portals are hard protected, with zero
accepted contacts; incorrect floor labels cannot bypass real intersections. No doorway
infill, source/derived asset save or naming-based role inference occurs.

All 19 confirmed OBSTACLE roles remain APPROVED and movement/visibility blocking true;
footprint/open-surface physical support remains HUMAN_REVIEW, without invented extrusion.
Eight obstacle/PORTAL conflict pairs remain; zero WALKABLE pairs exceed the existing
contact ratio. Stair A/B each has two PATH components, with nearest 3D gaps of
**4.769402 / 4.896199** under the existing 1 m/BU conversion, not a new architectural-scale
approval. Connectivity, landings, openings and clearance remain REVIEW. There are stairs
only, no elevator and no new cross-floor connector.

The new [read-only geometry contract](../specs/GEOMETRY_PROVIDER.md) separates role, physical support,
floor and scale authority through source-bound frozen/strict exact-triangle models.
There is no bpy/GT dependency; unknown fields and unchecked mutations are rejected.
`require_approved_physics` raises a typed refusal for incomplete or unapproved physical
scope; empty inspection collider results cannot certify clearance, and floors without
actual WALKABLE support cannot claim completeness. Overall physical/collision validity
remains **PROVISIONAL**. Graph, ranking, GT isolation and benchmark/metric semantics stay
unchanged; no formal Cases 1–3, rendering, merging or pushing are performed.

Fresh final checks: `uv run pytest` **996 passed in 84.79s, no failures or skips**;
`uv run ruff check .`, `uv run mypy` (77 source files) and `git diff --check` pass.
The full existing regression suite and 101 new authority/provider/physical-review tests
pass. Separate processes/output directories reproduce review artifacts; two independent
read-only Blender exports reproduce identical evidence. All manifest input/code/artifact
hashes and 90 local documentation links validate. Original source hash/size/mtime stay
unchanged; the existing derived scene still matches its saved hash/size evidence. All
1,572 wall patches have one actual welded triangle component. Geometry completeness and
stair connectivity remain unapproved.

### 2026-10-05 — Second checkpoint and bounded pilot downstream loop

The requested successful-pilot checkpoint fdf9e7e8f2dc695917ba42094a63cc06ca910963 starts
clean on phase1/pilot-dataset-and-wall-inference. Fresh checks pass: 847pytest tests
in55.97s without skips, Ruff, mypy72sourcefiles and diff check. Push succeeds and live
git ls-remote returns the identical SHA. The new phase1/pilot-downstream-reconstruction
branch starts there; the checkpoint is neither rewritten nor merged into. The new
checkpoint record preserves Git/local-asset recovery and scope boundaries.

Exactly one existing office trajectory is consumed, with no new Blender dataset/render.
Strict GT-free pilot context/adaptation and a provisional topology scaffold reuse the
ordinary inverse projection, BlenderDataset, aggregation, gap-event Graph Top-K,
reconstruction and configured evaluation APIs, without changing core/benchmark semantics.
All outputs under ignored data/pilot/phase1_downstream_20261005 are labelled
PILOT / SYNTHETIC SAMPLE, including wrappers around strict domain results.
Export preparation allowlists render-resolution cameras, source identity, an independent
mesh-probed static plane and source AREA bounds. GT positions, waypoints, hidden depths
and GT speeds are absent from context. The mixed-container digest is separate audit data.
Consumers read only 2D observations and strict context, with source/site/content and
schema-bypass guards. All100camera records / 50timestamps survive: 26visible projections,
74nullGAPs, two projected Observation segments and one4.0–9.0s gap Event. The24missing
timestamps are4.2–8.8s; reconstruction endpoints and missing samples are distinguished.

Exact PROJECTED endpoints plus configured ±12native-unit offsets produce three routes
within an annotation-AABB envelope. Original camera home-zone IDs are retained;
configured ADJACENT transitions demonstrate this local provisional handoff only.
Route lengths80.00083961/104.00083961/104.00083961BU yield3routes/6timing hypotheses,
COMPLETE/exhaustive termination, no rejections and null path scores. Every alternative
is retained without GT ranking. Mesh/WALL/metric authority remains unverified, physical
validity partial/provisional and actual mesh collision rate unavailable. Zero rates
from an empty obstacle config never certify clearance.

GT loads after frozen inference only. Existing metrics score26GTtimestamps over the
exact4.0–9.0s extent. First-primary ADE/FDE are0.000708092424/0.000280838027native
units; minADE@3/minFDE@3 match, Coverage@1/2/3true at diagnostic ADE<0.02units.
The threshold is not formal epsilon or physical metre certification; low anchored FDE
is diagnostic, not research accuracy. GT compatibility is evaluated without reordering.
Two runs have byte-identical10inference artifacts and metrics. Poisoning GT positions
and simulation waypoints leaves exported context and all10inference artifacts identical;
only evaluation changes (ADE≈37416.574units, Coverage@3false). Tests cover forbidden GT
access, missing GT, schema-bypass injections, incompatible bindings/time extents and a
GT-compatible third route that never replaces the first prior candidate. Original and
derived Blender identity and original dataset/observations/GT/plan remain unchanged.

Saved-output Rerun/3D visualization retains all3routes/6hypotheses,26observed and50GT
debug samples. Readable RRD, standalone interactive HTML, inspected3DPNG and manifests
are produced; RRD readback has41chunks/33entities with correct samples. Browser policy
blocks file:// UI inspection; no workaround is attempted. Final verification is
PASS_WITH_PROVISIONAL_PHYSICS with zero errors. Fresh final checks pass895tests
in57.58s without skips, Ruff, mypy74sourcefiles and diff check outside the native sandbox.
Work stops after the local downstream commit: no new-branch push, merge, formal
Cases1–3, elevator transition or dataset expansion.

### 2026-10-05 — Post-checkpoint WALL markings and one bounded pilot loop

Work continues only on phase1/pilot-dataset-and-wall-inference from checkpoint
91f4ea600805739aa9659dfef6a381d71be9a692. Fresh original-source extraction confirms
81 WALL surface patches (49 on 1F, 32 on 2F, 7 source objects), retaining 1,491
HUMAN_REVIEW patches across 674 objects; object counts overlap for mixed meshes.
The dated candidate report records bounds, floors, nearby AREA/PORTAL, WALKABLE
relations and verticality/height/continuity/extent/parallel-thickness reasoning.
Ambiguous windows, doors and decoration remain under review.

The saved isolated school_v3_wall_marked.blend contains 81 WALL semantic selection
meshes copying 543 actual existing polygons. No whole group_* is reclassified, no
doorway is filled and no movement collider is installed. Independent reopening verifies
all 2,873 original object identities and evaluated physical geometry, with zero actual
face intersections against 28 protected portals. Original/source-checkpoint SHA remains
cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e, with unchanged
468,300,506 bytes and mtime_ns1791198236746106977. Derived SHA is
b4d3394b17626bfdf35ee9b9e35c1f5a4469dd75a3e24b1a4f5f5aa58bdf4d49. The new
marking recipe and dated audit artifacts bind source, candidate and reopened selections.

Exactly one new ignored PILOT / SYNTHETIC SAMPLE is materialized at
data/pilot/phase1_wall_pilot_20261005/office/. Existing AUDITORIUM_FRONT/REAR cameras
retain source poses on the 1F office metadata route PILOT_OFFICE_001: 160 configured /
156.800049 sampled native units, 10s at 5 FPS, all 50 timestamps and 100 PNGs successful.
The route passes 250 support probes and continuous full-marker swept-volume checks.
The plan/export lineage binds the real derived asset and preserved original/candidate/
physical geometry. All 81 WALL annotations are excluded from physical BVH, render
snapshots and rays; original physical surfaces still supply occlusion.

Independent validation is PASS_WITH_REVIEW with zero errors: 26 visible, 74 occluded,
zero out-of-FOV camera records; FRONT 21/29 and REAR 5/45. The visible→GAP→visible
loop has 24 global landmark GAP timestamps at frames21–44 (4.2–8.8s), including
19 fully marker-hidden samples and 5 with partial body. Forward/inverse maxima are
0.000314545px / 0.001615262 native units, with no unexpected Projection failures;
74 non-observed inputs are rejected as expected. Inverse inputs contain only sanitized
2D frames, calibration and an independent mesh-probed static diagnostic plane. GT
is used only by simulation and post-projection evaluation, never downstream inference.
Original and derived hashes, sizes and mtimes remain unchanged.
An independent audit verifies all 100 decoded PNGs and provenance labels/hashes, 100
planned/exported states and strict 2D frames, plus all 26 visible landmark orange masks.
All 100 decoded RGB renders are exactly pixel-identical to the previous original-source
office renders, with zero differing pixels. Dataset SHA is
77203e33a566f99936e6446133dae245231562b0a64bfc82447e5f1215d5d2df.

Outputs include separate GT/2D observations, evaluation-only dataset, plan, validation,
sample report, gallery, trajectory map, 50-frame ten-second GIF and five inspected
representative montages at frames0/20/21/32/45 (0/4.0/4.2/6.4/9.0s), explicitly
distinguishing partial-body GAP entry from fully hidden middle and rear-camera recovery.
Fresh requested checks pass: 847 pytest tests in71.83s without skips, Ruff, mypy for
72 source files and diff check. Final uv/native Blender checks run outside the sandbox.
No benchmark semantics, formal Cases1–3, elevator transition, merge or push occurs.
Work stops here; full generation awaits user pilot review, physical scale and formal
geometry/floor/camera-plane authority.

### 2026-10-05 — Phase 1 semantic scene checkpoint

The user explicitly authorizes a major checkpoint, publishing the current branch and
creating a continuation branch from it. The starting tree is clean on
codex/dataset-infrastructure at 4437ef3e468d3b18181f893906619af021042434. Fresh requested
checks pass: uv run pytest has 821 passed in 58.64s without skips; Ruff, mypy for 72 source files
and git diff --check pass. Final native Blender/uv checks run outside the sandbox;
uv's sandbox macOS initialization failure disappears on the same-command rerun, without
removing or skipping tests. The checkpoint record preserves branch/source/validation and
continuation boundaries. A verified, ignored read-only snapshot matches the current
school_v3 hash; original hash/size/mtime are unchanged. The local manifest records the
checkpoint SHA and four pilot file hashes; raw assets are not pushed and no new rendering
occurs. The marker commit is checkpoint: preserve phase1 semantic scene state. Subsequent
work belongs on phase1/pilot-dataset-and-wall-inference, created at the same checkpoint
commit, with no formal benchmark semantic changes, Cases1–3 execution or merge back.
Exact commit/publication evidence is in the completion report and local manifest.

### 2026-10-05 — Three-locale Blender PILOT comparison

Starting at c078b89, the user's follow-up authorizes several locales and judgments.
Three new ignored PILOT / SYNTHETIC SAMPLE runs in school_v3 cover CLASS101, AUDITORIUM
and OFFICE metadata regions, not separate buildings or real sites. Each has 10s at 5 FPS,
50 timestamps on [0,10) and 100 PNGs: all 150 timestamps / 300 renders succeed. The
original corridor pilot remains a reference and is not counted as newly generated.
Classroom uses CLASS101/CORRIDOR_04; auditorium/office reuse AUDITORIUM_FRONT/REAR without
camera changes. Configured / sampled lengths are 300/294, 660/646.800049 and 160/156.800049
native scene units. Every route passes 250 physical/WALKABLE support probes and exact
continuous full-marker swept-volume triangle checks. Cached grids are hints only;
current geometry rejects colliding or mismatched-visibility routes. No portal, floor or
elevator transition is introduced.

Classroom has 50 visible / 0 occluded / 50 out-of-FOV records and no global GAP: it is a
center-point control, with marker boundary clipping in all 50 visible images and all
CORRIDOR_04 samples FAR_CLIPPED. Auditorium has 82/2/16 records and one GAP at 9.4s with
partial body still visible: useful coverage/brief-interruption data, not the main long-gap
sample. Office has 26/74/0 records and 24 GAP samples at 4.2–8.8s: 19 at 4.6–8.2s show no
marker in either view and five retain partial body. It is the strongest current point-gap
sample, with reused auditorium views and only five recovery samples. Existing opaque-gray
Workbench/orange-marker rendering has irregular floor appearance of unverified cause.
Agent image judgments do not grant human authority or whole-body detector readiness.

Each run saves separate strict 2D observations/GT, evaluation-only combined JSON, source-bound
plan, validation, report, 50-frame synchronized GIF, trajectory map and five distinct review
montages. Explicit FULLY_OBSERVED_CONTROL never fabricates a GAP; singleton GAP representatives
are 0/46/47/48/49. Comparison binds judgments to dataset and inspected-image hashes. SiteID
is verified across plans, PNGs, provenance and both exports; mixed-site corruption is rejected.
All three independent validations are PASS_WITH_REVIEW with no errors; all 300 PNGs are
decoded/hashed/labeled, all 158 visible landmarks have orange pixels, and independent masks
confirm the full-hidden/partial split. Forward error is at most 0.000638311 pixels and static
pilot-plane inverse error at most 0.001787566 scene units, with zero unexpected failures;
all 142 non-observed camera inputs are correctly rejected. Source hash/size/mtime are unchanged.
GT is used only for simulation/export/evaluation; inverse receives sanitized 2D, camera and
an independent configured plane. Graph, ranking, reconstruction and formal benchmarks are
not run or changed. Full regression passes 821 tests in 72.57s without skips, plus Ruff,
strict mypy for 72 source files and diff checks. Eighteen native Blender crashes in the
sandbox disappear in the full outside-sandbox rerun, without skipping tests. Work stops at
these three pilots; the final report-role wording adjustment also passes six summary tests
and Ruff. Full generation still awaits image policy, scale and formal authority.

The bounded 2026-10-05 PILOT / SYNTHETIC SAMPLE is materialized locally in ignored
`data/pilot/school_v3_pilot_20261005/`. CAM_1F_CORRIDOR_02/03 retain their source poses;
the 1F route is planned at 106 native scene units over 10s, with 50 timestamps at 5 FPS on
[0,10), sampled length 103.880005. Actual floor support Z≈20.07885 differs from annotation 25;
feet and landmark are Z≈20.12885/75.12885. No physical-scale conversion or human-size claim
is invented. All 50 samples pass WALKABLE containment, 250 physical support probes and exact
continuous radius6/height119 swept-volume triangle checks. A point-clear side collision
was corrected before rendering. Annotation/reference geometry is excluded.

Frozen frame 220 evaluated VIEWPORT mesh instances are rendered without modifiers in an
unsaved process, using the explicit opaque-gray Workbench studio/orange-marker pilot policy.
All 100 PNG renders, hashes, dimensions and synthetic/source/timestamp provenance labels
verify; metadata labeling preserves all 100 compressed IDAT pixel payloads. All 21 visible
landmarks independently show orange image pixels. Camera02 has 3 visible/47 occluded records;
Camera03 has 18/32, totaling 21 visible/79 occluded/zero out-of-FOV. Global landmark GAP has
29 timestamps (frames 18–46); 15 retain partial body and 14 show no marker in either render.
Representative frames 0/17/18/32/47, a synchronized 50-frame GIF, trajectory map, HTML gallery
and sample report are saved. This is point simulation, not whole-body CV or formal shading.

Independent validation is PASS_WITH_REVIEW with no errors. Source SHA/size/mtime are
unchanged; forward residual ≤0.000114213 pixels, axial-depth residual ≤0.000112066 scene units,
and 21 diagnostic inverse projections differ by at most 0.000247572 scene units. All 79 GAP
inputs are correctly rejected with no unexpected failures. Inverse inputs contain only
sanitized 2D evidence, camera calibration and an independent static mesh/config plane;
truth is evaluated afterward. GT and observations are separate, combined data is
evaluation-only, and no Graph/ranking/reconstruction/formal benchmark/elevator transition
is run or changed. Final regression passes 797 tests in 56.90s with no skips, 14 targeted
safety/provenance tests, Ruff and strict mypy for 72 source files. Work stops at this pilot;
full generation remains pending human image review and physical scale/formal authority.

The 2026-10-05 WALL extraction starts at clean `e8b293f` on
`codex/dataset-infrastructure`. Source-bound evaluated surface analysis confirms
81 WALL patches (49 on 1F, 32 on 2F, 7 source objects) and retains 1,491 HUMAN_REVIEW
patches (674 source objects). Four objects contain both statuses; counts are connected
coplanar surface patches, without whole-object classification or saved source labels.
The report includes review reason counts, an object/floor index, bounds and nearby
AREA/WALKABLE/PORTAL evidence. Exact face clipping protects all 28 PORTAL boxes;
confirmed aperture intersections are zero. No rectangle/AABB walls or doorway infill
are created. Ambiguous panels, glass, decoration and weak evidence stay review; sampled
WALKABLE checks are not complete collision certification.

The user confirms stairs only and no elevators; historical AREA_*_ELEVATOR names do not
create transitions. Source SHA-256, 468,300,506-byte size and nanosecond mtime are unchanged.
Native scene units remain explicit; declared metric scale is not physical certification.
Five targeted safety tests and the complete 794-test regression (56.48s), Ruff and strict
mypy for 72 source files pass. Ground Truth, formal Cases 1–3 and downstream inference
semantics are untouched.

### 2026-10-05 — Authorized school_v3 semantic supplement and post-save diagnostics

Starting at `a0aa1ea` on `codex/dataset-infrastructure`, explicit human policies authorize
saving the same school_v3.blend, without v4 or rendering. The reviewed recipe adds 15 room
floors and 19 aperture-only thresholds, subtracts same-floor blocking polygons from 14
existing floors, extends both offices, preserves all 19 obstacle meshes while assigning
OBSTACLE/BOTH roles, corrects the 2F MENSROOM portal by +140 Z, and annotates two stairs
without inventing landings or full paths. Four fully blocked bathrooms remain without room
floors; elevator roles remain unresolved. The separately approved validator extension reads
intentional exclusions/cross-floor AREA metadata and reviewed explicit WALKABLE aliases;
formal Phase 1 schemas, Graph, benchmark and metric semantics stay unchanged.

Source SHA changes intentionally from `26428df2fd395c69673b3e918fb7171b72d77a47d728e6b9cb21bb9da7b8e614`
to `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`.
The verified original backup and unchanged architectural/obstacle meshes/cameras are recorded
in [update evidence](../../data/scene_audit/school_v3_semantic_update.json). The subsequent
read-only audit preserves hash, size and mtime. The ignored Blender asset stays local;
source-bound recipes, reports and tools are committed.

The updated inventory is 30 AREA, 48 WALKABLE, zero WALL, 19 OBSTACLE, 6 stair annotations,
28 PORTAL and 29 CAM. Coverage PASS/PARTIAL/MISSING moves from 2/4/24 to 16/5/4, plus three
EXCLUDED and two NOT_APPLICABLE declarations. Floors 25/165 remain proposed. Office coverage
uses the unchanged raw AREA denominator: 20.5742% to 29.6071%. Diagnostic components grow
9 to 14 as newly marked rooms reveal unresolved seams; isolated objects fall 7 to 1.
Queues change 49/170/43 to 33/224/69. Independent component checks confirm six local contacts
between distinct room/corridor surfaces, not 20 connected doors from two-sided probes;
none grants physical authority. Readiness is NEEDS_HUMAN_FIXES. The
[location summary](../../data/scene_audit/school_v3_semantic_locations.md) identifies every
remaining HIGH/MEDIUM object, coordinates and required human action. No physical integration,
collision pruning, benchmark or Agent work starts.

Full regression passes 783 tests in 53.62s with no failures/skips, repository Ruff and strict
mypy for 72 source files. Final native replay, local links, source fingerprint and diff
evidence is stored in the report JSON; ten pre-existing metadata-free semantic fixtures
retain their prior report semantics.

The 2026-10-02 validator/protocol/reporting round starts at clean `1750e39` on
`codex/dataset-infrastructure`. Local commits `56040b7`, `b29b9aa`, `40bfea1`, `249615a`,
and `7f7ea71` add read-only scene diagnostics, synthetic semantic tests, the formal protocol
specification, matplotlib comparison reporting and plotting regressions. No original scene,
formal Graph/Reconstruction/evaluation semantics, school benchmark, Agent or presentation work
changes. No publication is performed.

Two independent Blender processes produce byte-identical semantic JSON/Markdown: 30 AREA,
28 PORTAL, 29 CAM and zero physical labels. Source SHA-256, size and mtime remain unchanged.
The review queue has 63 HIGH, 124 MEDIUM and 3 LOW findings; unsupported geometry and absent
floor/clearance/opening authority retain REVIEW rather than creating navigation/stair edges.
The protocol defines Cases 1–4, baseline/ablation interfaces, metric populations and six
acceptance categories, while formal settings remain unresolved and execution disabled.

Persisted native fake outputs yield 11 SYNTHETIC REGRESSION charts; unavailable metrics skip
with reasons. The explicit plotting-only fixture yields all 17 MOCK VALIDATION chart families,
including failed/missing/no-reference/empty records and repeated runs. Visual QA corrected the
Coverage footer layout. Missing values remain N/A; incompatible aggregates require REVIEW;
GT never orders methods. Final checks: 745 tests in 58.78s, no skips/failures, Ruff, strict mypy
for 72 source files, diff/local-link/chart inventories, report replay and source immutability
all pass. The 58 new tests consist of 39 semantic, 15 reporting and 4 protocol regressions.

The 2026-10-02 Blender milestone begins at `bd984f2`. A fresh read-only source-bound audit
inventories 2,796 objects, 2,652 meshes and 29 collections: 30 AREA annotations, 28 PORTAL
annotations, 29 research cameras, and no WALKABLE/WALL/OBSTACLE/STAIR labels. All 29 raw
camera world matrices match the portable calibration exactly; floor-plane authority is
still unreviewed. Source SHA-256, size and mtime are unchanged; no save or render occurred.
Two empty-mesh origin fallback descriptions were corrected in the new audit. Two fresh
Blender processes produced identical JSON semantics; all 2,825 rows and tool/source hashes
were checked. The existing-output guard rejects without overwrite or Blender launch.

Under the user's explicit stop conditions, physical integration waits for source-bound
human walkable/collider ownership, floor/camera-plane bindings and clearance policy.
An additive geometry interface was reviewed, not implemented. No school Cases 1–3,
datasets, physical metrics/visualizations or A–C baselines are claimed. Existing schemas,
core, fake fixtures, Agent and Phase 2 remain untouched. Final regression: 687 passed in
45.61s, Ruff passed, mypy passed for 69 source files, and diff checks passed.

The 2026-10-02 boundary round starts at `b11edb9` on `codex/dataset-infrastructure` and
adds 140 tests across the eight commits above. Final code `a95b595` passes 687 tests
in 48.05s with no skips/failures, repository Ruff, strict mypy for 69 source files and
diff checks. Only benchmark reporting production code changes: structured known-input
rejections retain their original exception, and summaries expose endpoints/reasons and
NO_REFERENCE. No formal schemas, core inference/metric semantics, Blender assets,
dependencies, rendering, Agent ranking or publication change.

Four poisoned-truth patterns and absent truth preserve full inference; only evaluation
changes. Three adversarial fixtures replay across 21 invocations, including nine fresh
processes with varied hash/random seeds, CWD and output directories. All 120 observation
permutations and equal-distance route permutations retain ordering and IDs. All six
current search reasons, partial-candidate preservation, short/adjacent gaps and tiny
long-gap branching bounds are tested. User-confirmed scope keeps collision pruning
unresolved/evaluation-only and rejects zero epsilon. Actual school geometry, clearance
and obstacle authority remain future work, not a claim established by these fixtures.

The 2026-10-01 fake-data round started at `2a988df` and completed the generic downstream
loop on `codex/deterministic-downstream-scenarios`, with implementation commits listed
above through `6066c9e`. Full validation passed 347 tests in 26.14s, no skips/failures,
Ruff, strict mypy for 46 source files and diff checks. uv used the installed locked
environment with offline/no-sync and a writable cache; existing Blender tests required
approved unsandboxed execution. No dependencies, source assets, render, semantic ranking
or publication changed.

All four fixtures generated real candidate/Event/metric/RRD outputs, totaling 7 routes
and 11 timing hypotheses. All terminated COMPLETE; minADE@K≈0, minFDE@K=0, Coverage@K=true,
and supplied-AABB/speed/corridor violations=0. Branching primary ADE=7.8021081352m and
Coverage@1=false, with true route retained at rank three. Temporal slack is160s for20s
minimum travel in180s. Four RRD files were reopened successfully; 18 visualization tests
include midpoint playback. Twelve GT isolation integration cases and eight new M6 bypass
cases passed. Blender source/copy hashes match the unchanged digest above. These are fake
interface results, not school mesh certification or a formal benchmark. Remaining
producer/scene/multiple-gap/benchmark interfaces are in CODEX_HANDOFF.

This is a dated completion/evidence log, not a live TODO list. [CODEX_HANDOFF](../operations/CODEX_HANDOFF.md) owns current unresolved work; [DEVELOPMENT_RULES](../specs/DEVELOPMENT_RULES.md) owns durable rules; DATA_SCHEMA/INTERFACES own contracts. Historical results are not new test runs or formal benchmark acceptance.

On 2026-10-01, M0–M4 delivered uv/environment inspection, read-only scene/geometry audits and an identical research copy, deterministic Blender-evaluated Ground Truth export, 29-camera calibration/forward projection, and point visibility with sanitized 2D evidence. Main commits were `3238ec7`, `ab8a9d9`, `c3638c5`, `7add28b`, `82fa2a3`, `251db8f`, `58a8099`. Audit diagnostics identified floor candidates but did not certify school walkability or stairs; assets remained unchanged and no render was performed.

M5–M8 were independently committed as `1dcce12`, `7e952ae`, `94ee2cd`, `d6620b4`: strict domain/contracts, explicit-plane inverse projection, separate configured navigation/camera topology, and bounded topology-authorized Top-K search. M5 completion and empty-shell issues were resolved before commit. Exact route continuity, distinct-corridor K+1 truncation and incomplete search-limit reporting were reviewed.

Historical committed evidence: M5 `1dcce12` records 106 tests in 23.82s and mypy for 21 source files; M8 `d6620b4`/`c04435f` records 219 in 25.73s; a later review starting from `baf9074`, recorded in `e27d1dd`, passed 219 in 25.02s (no skips/failures), Ruff, strict mypy for 33 source files and diff checks. Source/copy hashes matched the digest above. These checks do not establish mesh collision/clearance, school navigation, Projection Error evaluation or a formal dataset/benchmark. The M6 schema-bypass finding was recorded, not fixed at that review.

`74c66bd` inventoried audit evidence and a local ignored camera catalog, with no materialized GT/observations/candidates/metrics/images. `baf9074` recorded an earlier authorized publication; `83ca3f8` added the README. `e27d1dd` recorded review results and the user's temporary school-stair deferral without code/asset/publishing changes. This documentation-only reorganization started from `e27d1dd`; it moves completed history here, durable rules to their own document and preserves actual open handoff items. Four bilingual Markdown files, 57 local links and state/fence/diff checks passed; historical counts were checked against their committed records, not rerun. No M9, M6 fix, data generation or rendering was started.

## 2026-10-08 — 文件分類、MockAgent 範圍與分支發布 / Documentation and mock retrieval handoff

本次從 `883204af854bed301506b39d63ccb33312b79ff2` 重用既有 checkout，在 `codex/docs-agent-handoff` 完成30份正文分類，新增 `docs/README.md` 和 specs/research/engineering/operations/history 入口。原 root paths/anchors 以兼容入口保留；三份 hash-pinned Markdown、hydration checkpoint JSON、producer-generated artifact inventory 與 locked protocol config，共六份 bytes 保持不變。沒有新增 worktree/clone/environment、修改程式或 source/media。

新增 `AGENT_RETRIEVAL_BOUNDARY` 審查角色、TaskContext、typed tools、summary/detail/media/replay、mode/stage 守門及 Agent/API-visible logs。修改續作 prompt，擴大為 M1–M6 可操作工程閉環並要求每個 executable milestone 驗證、commit、普通 push。OpenAI API 接線與 token 兜底演算法保持空章節；沒有外部模型調用或宣稱 token 降幅。既有1978測試屬恢復 checkpoint 證據，本次未重跑程式測試。

文件驗證：113份 Markdown、1,145個 relative links 檢查，沒有新增失效 path/anchor；16個先前已有的失效引用保持同一集合。Protected bytes 全部相符，staged diff check PASS。歷史正文只更新分類後的相對連結，必要 current handoff/rules/prompt 依新授權更新；immutable receipts/config/producers 不改寫。

第一個文件 checkpoint `8798bcc54f2226537f0d11cbf91e3612f20b68d0` 已推到 `codex/docs-agent-handoff`，並在 GitHub 建立同 SHA 的 `codex/simulation-engineering`。`codex/deterministic-downstream-scenarios / c0717ae7c3655799aa11e779248cec1e670387d1` 和 `phase1/pilot-robustness-validation / ce2974b25b31a8cb0ec9bc579a84d708d3356bf7` 的同名 remote refs 已建立。`git ls-remote` 實際核對相符；main 與 frozen Phase 2 未變動。其餘既有本機 commits 已由 remote ancestry 覆蓋。

唯一未發布 commit 是 `phase1/physical-policy-approval / c5956dc825f669e28e2694578be0fed97432a786`，含50,897,608 bytes 新 blobs，其中四份 raw source/physical evidence 已由 [artifact inventory](../operations/PHASE1_ARTIFACT_CLEANUP.md) 列為 LOCAL ONLY。Repository visibility 實查為 PUBLIC；該分支保持 HOLD，不因推送其他分支而發布原始證據，不改寫或刪除其本機歷史。完成上傳全部 commits 仍需對這份 LOCAL ONLY bundle 的明確發布例外。

English: Reused the existing checkout to classify 30 maintained documents, retain compatibility links and preserve six protected files/configs byte-for-byte. Added a planned local MockAgent retrieval contract and an expanded M1–M6 prompt. API wiring and token fallback sections remain empty; no external model call or code-test rerun occurred. Relative-link validation found no new failures. The documentation checkpoint and engineering startup branch were published and exact SHAs verified, together with the two missing historical branch refs. Main and frozen Phase 2 remained unchanged. Only `c5956dc` is unpublished: it contains raw evidence explicitly classified LOCAL ONLY in this public repository and remains HOLD pending a specific publication exception.

## 2026-10-08 — 根目錄與導覽精簡 / Root and navigation cleanup

本次承接 `32667254a0eb5bb1f3ad299eef9952145382c2c6`，依使用者指示移除30份 root 轉址正文與5份分類 README。`docs/README.md` 成為唯一索引，只列四個工作入口與五分類；專案 README 的文件導覽保留索引與交接兩個連結。Protocol 正文搬至 research、歷史 post-approval handoff 搬至 history、artifact inventory 搬至 operations；其他正文維持分類位置。

Root 由36個檔案降至6個：索引、exact corridor review、hydration checkpoint JSON，以及 DEVELOPMENT_RULES／GEOMETRY_PROVIDER／benchmark protocol 三個必要 symlinks。Corridor question 的實際 manifest hash、原 checkpoint JSON、locked protocol config、其餘 tracked JSON 與 hash-bound Markdown 共298份 bytes 全部相符。歷史 checkpoint 內 protocol／handoff 的 SHA 記錄仍指當時版本；新位置只修連結，不把歷史文件 SHA 或歷史 PASS 當成本次 bytes／研究驗收。

可維護的資料盤點、交接、prompt 與文件連結改為分類位置。三個 future report producers 只修文件輸出／連結路徑，避免重建後把文件重新寫回 root。沒有重跑或覆寫歷史 inventory／source／media。首頁同步修正已過期的「尚無 projection／baseline／ablation／rendered images」敘述，區分已存在的 office 局部結果與未完成的正式全案例驗收。

本次驗證：15個既有 scale／hydration tests PASS；修改 producer 的 Ruff PASS；mypy 111 source files PASS。Inventory producer 在隔離的 temporary fixture 確認新輸出位置與 CSV 連結，scene-audit summary 確認分類後的決策連結。Actual historical hydration 再驗297份現存檔案、29 locked inputs，copied=0，沒有替換舊 inputs。相對連結與 anchors 無新增斷鏈，原16項失效引用未增加；三個 symlink 目標與四個 API／token 空章節驗證相符。完整1978測試仍是先前 recovery checkpoint 的紀錄，本次未重跑。

English: Removed thirty redirect bodies and five category indexes, leaving one documentation index and six root files/aliases. Maintained text uses the five category folders. Kept 298 JSON/manifest-bound evidence files unchanged, preserved real corridor approval and runtime bindings, and updated only navigation in the moved historical documents. Three future report producers now emit category paths; existing historical artifacts were not regenerated or overwritten. Fifteen targeted tests, Ruff, mypy, isolated producer checks and exact 297-file/29-input hydration passed. No new relative-link failures or external model calls were introduced; API/token sections remain empty. Historical full-suite evidence is not a test rerun or new formal acceptance.

## 2026-10-08 — 預覽合併與 projection 診斷接入 / Preview and projection integration

依使用者授權在既有 checkout 使用 `codex/simulation-engineering`，保留 `codex/docs-agent-handoff / 2c586b1`、canonical source checkout 與 frozen Phase 2。先將 `codex/phase1-preview-workspace / 04c699d8473235392eb18be483766bcc4de42a58` 合入，merge commit `ded5572e29896d624c650d7117321d05af447759`；Git 自動把 WORK_LOG 增量放至 history 分類，修正該新紀錄的相對連結。預覽12 tests PASS、Ruff／mypy PASS、JavaScript syntax PASS；實際 builder 從 exact inputs 再核對50 frames／58 images，data SHA `d3c31f7cd64baeb920ee308c7b7d4b70206e8fd80f93db8799b5503bd5595783`。既有8768預覽服務與其 clean worktree 沒有切換或停止。

Projection donor `phase1/projection-model-upgrade / 8f4055ffcdc3bf6efd723c7956ac685e1fe033f1` 的四個 conditioning／mitigation／multiview／uncertainty helpers 已與研究基底相同。僅補8個 comparison／report／surface-control／downstream／robustness scripts 與7個相應 tests，15檔與 donor bytes 相同；不 whole-branch merge，不匯入舊報告、inventory 或原 branch 的 core。Sidecars 不進入 Graph 權重、BoundObservation 或 API，不新增 GT 推論輸入。完整比較仍需 exact inventory／已物化 mitigation artifacts，本次不重跑歷史實驗或宣稱新增正式研究結果。

12份相關 test files 驗證全過；本次完整整合 XML 核對該範圍246 passed，其中新增7份 tests 共115 passed。Ruff PASS；6個 comparison/report/robustness/sweep/evaluation CLI `--help` exit0。此 projection checkpoint 的 existing core／依賴／lock 保留；完整相容整合結果記於後續 checkpoint 與 engineering receipt。

English: Merged the view-only preview with ancestry preserved, then imported only fifteen compatible projection diagnostic/test files from `8f4055f`; existing model helpers were already present. Playback rebuilt50 frames/58 verified images and passed twelve tests. Projection coverage contains246 passing tests, including115 new cases; Ruff and six CLI entry checks passed. Core contracts, Graph scoring and truth isolation remain unchanged. This does not rerun historical experiments or establish formal readiness.

## 2026-10-08 — 相容 Phase 2 mock 接口整合 / Compatible Phase 2 mock adapters

從 projection checkpoint `f58157f` 選擇性新增 frozen donor `phase2/integration-hardening / 5b51d2c67917ff434f53e12a8af8af3d711d2a19` 的17個 source/config/frontend files，bytes 均與 donor 相同；新增 scoped `tests/phase2/`（10份 donor tests 與局部 conftest）、分類後工程文件與2份明確標示 historical 的紀錄。不 whole-branch merge，不帶入舊 shared Graph／schema／dataset／Blender／environment 改動。文件保持唯一索引、6個 root entries 與3個必要 aliases。

現可由現有 mock config 執行 Memory／LOCAL_JSON canonical repository、read-only JSON API、legacy COMPLETE package replay importer 與 TypeScript consumer。25次實際 CLI loopback HTTP 調用驗證8 observations、4 events、11 hypotheses；重複 GET 不重新 inference／修改 snapshot，canonical IDs／候選順序保留，錯誤與 method gates 通過。Node 實際驗證4 events 的 consumer／replay。Receipt 只保存 hashes、計數與檢查結果，沒有 raw payload、GT、private source archives 或外部模型調用。

本次完整 actual checks：**2255 passed in160.21s，0 failed／0 skipped**，要求並使用實際 Blender／physical evidence；Ruff PASS、strict mypy PASS（125 source files）。其中 Phase 2 scoped150 tests PASS。137個必需 existing Git files、181個 existing scripts/tests、29 locked inputs、297 unique frozen review records、原 corridor proposal／protocol config／source SHA與size 均不變；另驗298份 JSON／hash-bound records、707相對連結，原16項失效引用未增加。API／token 四個空章節仍空白。完整來源與驗證摘要見 [compatibility receipt](../../data/engineering/integration_20261008/compatibility.json)，實際調用證據見 [HTTP receipt](../../data/engineering/integration_20261008/http_smoke.json)。

本 checkpoint 支援 mock 工程續作，不認證新 reviewed/finalization importer：固定 METRES 不能覆蓋 historical native BU，需獨立 source/context/clock/scale adapter與顯式normalization。低階 mock API 仍非 Agent allowlist DTO；LocationRegistry／照片模式／image perception／association／Agent tools與UI尚待M1–M6。原 formal Cases2／Case3和 full Exit保持 BLOCKED，Case4 DEFERRED。`main`、原 Phase2 frozen branch/tag 與8768原預覽服務沒有變動。完成 commit 後普通 push僅發佈 `codex/simulation-engineering`，不發布 canonical `c5956dc` LOCAL ONLY ancestor。

English: Imported seventeen byte-identical frozen mock source/config/frontend files and scoped their tests without replacing current Phase 1 core or dependencies. The actual loopback API and TypeScript consumers passed, followed by2255 full tests with zero failures/skips, Ruff and strict mypy. Existing core, locks, inputs, review evidence, source assets and document layout were preserved; no new link failures or external model calls were introduced. Reviewed-package normalization/import certification and Agent-facing DTOs/tools remain pending. Original formal gates, main and frozen Phase 2 remain unchanged.

## 2026-10-08 — 最終續作 prompt / Final continuation prompt

依使用者要求重寫續作 prompt，固定已整合工程基底 `4271b2b` 與單一工程分支，移除回退文件 checkpoint／自動切換研究分支的歧義。明定真正 RGB 量測、SYNTHETIC 來源與舊模擬 UV 的區別、local track／association hypothesis／既有 target_id adapter 映射、服務端 mode/stage 與 freeze 認證，以及 GT 3D 與合法推論結果的邊界。Agent facade 與內部 legacy mock 契約分開，執行期資料外送限制不阻擋已授權且合規的 Git push；工程低精度可逐步改善，正式研究義務與 full Exit 保留獨立驗收。

同步相同澄清至 Agent 工程契約，四個 OpenAI／token 空章節保持空白。只修改兩份文件與本紀錄，不執行 prompt 內 M1–M6、不改程式或資料、不重跑2255 tests。文件相對連結／anchors、diff 與既有 protected bytes 使用相稱檢查；歷史測試仍明確綁定原工程 checkpoint。

English: Rewrote the copyable prompt around the verified integrated baseline, real pixel-derived synthetic observations, provisional association bindings, server-owned stage authorization and a scoped Agent facade. Preserved blank API/token sections and independent formal obligations; this is a documentation revision, not M1–M6 implementation or a test rerun.

## 2026-10-08 — 局部跨鏡頭與行為研究交接 / Local camera and behavior research plan

依使用者要求查核 primary research（AAAI st-ReID／Deep SORT），整理 camera 可達拓樸＋clock/time＋pixel人物連續性的可行判斷、限制與 R1–R8 下一對話交接。以局部 indexed retrieval 與固定 candidate pool 的 association feature 消融分開評估；定義同色多人／不可達／轉角門口反例、長 gap、same-camera復現與缺失情境，以及檢索漏取／讀取量、association、behavior與geometry指標。主展示保留實際多影格、局部3D候選與不確定性，不把盲區唯一行為／意圖或未校準分數當已知答案。

只讀指定規格與並行草稿；此時 src/configs/tests 的 engineering 目錄未提交，未修改／stage其內容或執行tests。讀到的全pair列舉／catalog遍歷限制以日期化觀察記入交接，下一個對話核對live狀態，先續接與補索引，不用本次文件或歷史2255 tests宣稱草稿PASS。僅新增一份operations研究交接、更新主prompt入口／current handoff與本紀錄；未跑實驗、未新增dataset／render／benchmark，formal gates與空API/token章節不變。

English: Prepared a research-only handoff grounded in primary literature and bounded source reads. Separate indexed retrieval evaluation from fixed-pool association ablations, preserve ambiguous behavior hypotheses and define operational multi-frame event output. Concurrent uncommitted prototypes were preserved, not tested or certified. No new experiment, dataset or formal acceptance was produced.

## 2026-10-08 — Simulation engineering M1

在 `codex/simulation-engineering` / `3117113` 上新增 source/context/model/run/clock 綁定的
LocationRegistry、CameraCatalog、opaque media refs、hash/containment 驗證與衍生模型對應契約。
獨立 recovery importer 核對實際 school-v3 source、12 dataset files、34 inference files、
4 cameras 與193投影；明確保留 native BU，校正執行 source Z offset 後乘0.0247 m/BU。
只認證既有 office structured partial scope，4 observations／2 events 的 canonical records
保持原值；不是 RGB、Agent DTO、corridor 或 formal full Exit 認證。

本次36 tests PASS（22新 registry/importer + 14既有 Phase2 integration）、Ruff與strict mypy
PASS。58既有圖片 hash/size 驗證，包含50 diagnostic overlay frames與8代表／模型圖；
可直接用作未標註 RGB tracking sequence 的數量為0。Curated receipts 見
[import certification](../../data/engineering/simulation_20261008/reviewed_import_certificate.json)
與[existing media audit](../../data/engineering/simulation_20261008/existing_media_audit.json)。
本機新 RGB／GT／snapshot／debug outputs 依 artifact policy 排除 Git；沒有修改原 scene或歷史輸入。

English: M1 adds source-bound local resource indexing and independently certifies the existing
reviewed structured office recovery with explicit BU normalization. Thirty-six current tests,
lint and strict types pass. Existing diagnostic media was verified and is insufficient as an
unannotated tracking sequence. Formal research gates remain separate and blocked.

## 2026-10-08 — Simulation engineering M2

新增獨立 procedural synthetic lab：2 cameras、每鏡頭51張真實存在的5Hz PNG，沒有
GT身分／路徑／bbox標註；完整GT／recipe另存 simulation/export。離線 pixel producer只讀
SHA核對過的RGB bytes，使用temporal background/components與camera-local tracking，
目前量得89 records／6 local tracks，漏檢、merged/partial、missing/hash/error均明示。
新增server-owned mode/stage與綁定run/input/config/producer/registry/media的freeze契約；
photos-only在freeze前不能查observation/event/detail/replay，plus僅准許量測入口。

本次34 tests PASS（8 perception、12 access、14 Phase2 compatibility），scoped Ruff與
strict mypy PASS。GT污染／刪除不改pixel輸出，固定輸入可重現，原場景、舊UV records與
依賴鎖檔不變。低精度屬SYNTHETIC RGB measurement，不宣稱REAL_CV或formal驗收。

English: M2 provides actual unannotated RGB sequences, pixel-derived local tracks and
server-owned mode/stage freeze guards. Thirty-four current tests, lint and strict types pass;
truth remains isolated and missing or uncertain measurements are retained.

### 局部研究交接的後續核對

交接製作期間已有並行M1 `0cb2f15`／M2 `6a00541`提交；本次只讀其commit、工作紀錄與partial office certificate／media audit，未重跑36／34 tests。研究交接同步指出這些可重用增量及其範圍，剩餘association／facade／UI等工作仍以live狀態核對，原全pair／catalog掃描觀察不因草稿存在而宣稱已解決。文件diff／links與原protected evidence檢查通過，無新增失效引用，API/token空章節不變；本輪只提交研究交接及相關文件，不納入並行程式／test修改。

## 2026-10-08 — Simulation engineering M3

新增pixel-derived ground projection／configured region membership與pairwise provisional
association。保留original local pixel／segment／track IDs，另建每個hypothesis的provisional
binding、canonical derived endpoints/events及映射。所有segment pairs與UNMATCHED alternatives
均保存，不選GT actor身分。Cross-camera gap呼叫既有Graph／reconstructor，保留完整候選／
時間假設／termination／complete；其complete僅屬明列有限lab route grammar。
重疊可見段不虛構gap，same-camera recovery為source-bound HOLD，不偽造handoff。

本次27 tests PASS（13 association + 14 Phase2 compatibility），Ruff／strict mypy PASS。
Persisted bundle核對source/context/model/run／全部local與derived record lineage；GT污染
不改inference hash。只使用獨立configured synthetic lab，不套用school或新corridor authority。

English: M3 preserves provisional association alternatives and immutable local-to-canonical
maps while reusing the existing Graph/reconstructor. Overlap and same-camera recovery are
explicit unresolved results. Twenty-seven current tests, lint and strict types pass.

## 2026-10-08 — Simulation engineering M4

新增AgentFacade八個typed read tools、server-owned session scope與allowlist DTO。
Photos-only input封裝包含所有照片refs且不含structured observations；plus使用同照片及
真實pixel measurements。Run loader核對input envelopes、frame links的camera/time/hash、
source/context/clock、effective config／static context／algorithm hashes、registry/media與
freeze receipt；跨mode/run、caller改stage、錯reference、錯誤logs皆fail closed。
MEMORY／LOCAL_JSON讀同一完整canonical snapshot，窄window不改endpoints；GET不重跑inference。
補reviewed importer CLI與registry可逆derivation／finite time guards。

當次63 tests PASS（20 facade、28 registry/importer、14既有Phase2 compatibility及1transport
smoke），scoped Ruff PASS、strict mypy137 source files PASS。更廣的完整驗證於後續M6綁定。
實際 `simulation-v2` 兩模式freeze完成：102照片、89量測、6tracks、21association records、
4canonical gaps／8routes。完整GT只在simulation/export，low-level legacy API不掛入facade。

English: M4 adds typed scoped tools, genuine mode inputs and fully verified frozen reads,
including immutable canonical joins and safe errors/logs. Sixty-three current checks pass.
The local synthetic run operates independently of reviewed/formal research acceptance.

## 2026-10-08 — Simulation engineering M5

新增loopback typed HTTP transport／schema入口、MockAgent CLI與可操作browser研究介面。
可定位地點、列camera/frame index、選完整RGB照片、查時間／region events、取摘要／細節、
显示全部3D候選與seek所有時間hypotheses。不是單交預錄影像；每次操作經typed工具讀固定
snapshot。主照片、viewer與replay無GT overlay，inferred／projected與presentation interpolation
明示。UI切session清空舊結果並拒絕stale async response，transport不記raw URLs／bad payloads。

當次35 tests PASS（21 facade/transport + 14既有Phase2 compatibility），Ruff PASS、
strict mypy137 source files PASS；真實loopback36 requests PASS，保存
[HTTP receipt](../../data/engineering/simulation_20261008/http_smoke.json)。
實際browser操作核對照片與3routes／6hypotheses，seek8.79s顯示所有INFERRED_GAP markers。
並行R1–R8工作改採獨立新版local association模組，原v1與simulation-v2 frozen bytes保留。

English: M5 provides an operating local browser and MockAgent workflow, including full
images and all-alternative replay. Thirty-five current checks and thirty-six real HTTP
requests pass. The live viewer was operated and inspected; truth is absent from the main UI.


## 2026-10-08 — Simulation engineering M6

完成獨立evaluation與inference-only PNG／reader-verified RRD、fresh output重現、兩種mode
comparison、八工具sample I/O及hash-bound curated receipts。Evaluation在freeze/source/config/
lineage核對後才讀完整GT；actor matching/debug留本機，不選association winner。兩模式相同
102張RGB，photos-only從pixels重新量測，89measurements／6tracks／21associations，4canonical
gaps／8routes保持canonical IDs、ordering、bindings、nullable、termination與complete。

最後補nested strict response allowlists及published response schemas；INPUT plus不補空geometry
欄位，並拒絕region filter，避免藉查詢篩選反推隱藏region答案。Injection／private-ref／stage／
cross-run／GT污染與缺失情境均通過。Main UI照片／projection／all-alternative replay沒有GT。
Office nativeBU僅由獨立partial adapter顯式0.0247 m/BU normalize，原scene與historical records不改。

**本輪當次2351 tests PASS，0 failed／0 skipped**，完整執行required physical-evidence入口；
包含96個M1–M6 tests與全部既有階段相容tests。Ruff PASS、strict mypy138source files PASS；
兩者及full pytest只排除同checkout另一chat未交付的local research草稿。當次36真loopback
requests、4個新canonical events／12Node26replay samples、兩mode MockAgent與browser實際操作
PASS；3routes／6hypotheses在8.79s均顯示INFERRED_GAP。13個frozen JSON及102張RGB於獨立fresh
output逐byte相同。驗證parent `1eb1ba0` 加actual source inventory／config／run／freeze hashes，
見[current validation](../../data/engineering/simulation_20261008/validation.json)；不是歷史2255的重述。

獨立synthetic fixture evaluation：83/129 eligible contact recall＝64.34%（24px threshold）、
mean pixel contact error3.092px、mean ground error0.102m。保留28merged/partial measurements、
28NO_DETECTION frames與1out-of-static-scope projection。Association identity accuracy及未量測
formal指標維持N/A；有限grammar complete不冒充exhaustive。Formal Cases1–3／A/B/C×K、消融、
相同eligibility independent inventory、fresh research dataset與完整clean-checkout reproduction
仍是獨立待辦，Case2／Case3 full gates BLOCKED，Case4 DEFERRED，原Phase2 branch/tag FROZEN。

只發布code/docs/curated receipts；raw RGB／GT／snapshots／debug／RRD／PNG排除Git且不刪除。
30prior-checkpoint protected files與school source hash/size/mtime重新核對，既有core／integration／
locked inputs／review／protocol與依賴bytes不變。保留並行local_*工作與其文件，不混stage。
更新CODEX_HANDOFF、Agent契約、simulation操作與data inventory，四個API/token空章節仍空白。

English: M6 completes independent evaluation, truth-free presentations, exact fresh-output
reproduction and curated source/run/config-bound receipts. All 2351 current tests pass with
required physical evidence and zero failures/skips; lint, 138-file strict types, 36 actual
HTTP calls and 12 TypeScript replay samples pass. Strict response validation and INPUT
region-filter denial close the final answer-leak paths. Low-precision fixture results retain
failures/ambiguity; formal research and concurrent R1–R8 work remain independently pending.

## 2026-10-08 — Local camera R1–R2 indexed checkpoint

從live `b234968` 續接，與並行 M1–M6 約定檔案／Git index 時段；保留其所有提交、registry、RGB tracks、v1 provisional bindings 與 frozen run。新增獨立 `simulation.local-association.v1`，source-bound scope/ref dictionaries、camera/time interval trees、region/portal adjacency、有界多跳／時間擴查與讀取／truncation receipts；候選取出後才形成pairs，沒有全pair／catalog query fallback。原 Graph routes／timing／排序、same-camera HOLD 與 overlap語意不變；appearance與pixel-derived motion只作未校準soft ranking。

當次40 tests PASS（27 indexed extension＋13原v1）、scoped Ruff／strict mypy PASS。16000無關records仍維持3筆讀取／2 index entries與相同receipt；5000歷史長區間overlap probe命中2筆且觸及少於40 entries。缺clock/coverage、window/hop/read budgets、錯scope與最低合法路程／速度gate已驗證。Curated [index receipt](../../data/engineering/local_camera_20261008/index_validation.json) 綁定實際source hashes；新protocol固定R1邊界，完整RGB／事件／評估／UI後續checkpoint另驗。不是formal研究驗收，Phase2／main與原資產不變。

English: A separate versioned local association composes genuine scoped interval/ref/adjacency indices before pairing. Forty current tests, lint and strict types pass, including unrelated-record and long-overlap scaling. Existing v1 schemas, RGB/provisional records and concurrent checkpoints are preserved. Formal gates remain unchanged.

## 2026-10-08 — Local camera R3–R8 operating pilot

接續indexed checkpoint `3df3ccd`，新增独立E1 pinhole software-rendered RGB、原producer的150 pixel measurements／18 local tracks、versioned local behavior composition與frozen scoped本機tools/UI。保留並行M1–M6 `b234968`、原102 RGB／v1 snapshot／8010服務；不覆寫registry、producer、legacy associations或原來源。新test run `local-camera-test-v1` 為4 cameras／244 RGB，兩模式各自從pixels重算，GT／recipe不進runtime。新freeze重用同一materialization，不複製重型asset或建立worktree。

輸出2進門／4出門／6轉角／4可能遊蕩／1停留／1轉角附近失去可見性卡，以及46 blind-gap cards、78原Graph routes／146 timing alternatives。每卡最多5實際RGB／missing證據與局部3D；白色blind endpoints只畫點，不冒充可見連線。服務端stage／same-run receipt／scope／reference guards、INPUT region-filter拒絕與typed八工具保持有效。Agent不獲GT、recipe、private path、任意filesystem／SQL／shell。

當次full **2427 passed in206.06s，0failed／0skipped**（required physical evidence），Ruff PASS、strict mypy145sources PASS；103 scoped tests含新76／legacy13／Phase2 14。沙箱內首次full有18項Blender相關失敗，14直接報SIGSEGV及4CLI衍生失敗；使用批准的原驗證入口／可寫cache在沙箱外重跑後全過，不修改原scene。34實際loopbackHTTP、378MockAgent calls、瀏覽器actual RGB／3D/replay與7種PNG卡驗證。完整source／同run dataset/config/media/registry/producer/freeze/event/evaluator hashes見 [curated validation](../../data/engineering/local_camera_20261008/validation.json)，操作見 [pilot](../engineering/LOCAL_CAMERA_PILOT.md)。

檢索：115 pairs、161 record reads／143 index entries、18局部seedqueries，對照獨立固定12s／3hop inventory115/115；無window/hop/budget的條件式next reference 8/8。不是未檢出人物recall。已知identity pair precision0.35／recall0.467，wrong-pair13／missed-pair8，within-local ID switches8；global merges/splits與IDF1 N/A。Full identity Recall@1/3/5為0.375/1/1，去SPACE為0.75/1/1，去TIME為0.625/0.75/0.875，去APPEARANCE為0.375/1/1；完整fusion不優於所有消融，未依test調門檻。Visible corner／possible-loitering有5／1誤報，enter/exit未定，dwell1命中；blind-gap class metrics因缺獨立標註N/A。Ground RMS0.305m、configured speed／region violations0；不認證school/global collision。Frozen event query120samples/mode的median約0.216/0.217ms，p95約0.438ms，pixel/import/media費用分開。

同run替換及移除GT／recipe/reference，pixel／inference／behavior／tool hashes不变；另一empty output重建registry/media/config／兩種freeze／inference/events／evaluation hashes一致。Local package/manifest含locators，跨output其hash不同；wall-clock telemetry不進推論hash。此為synthetic fixture／當前environment重現，不宣稱原formal clean-checkout benchmark、appearance/place泛化、真camera或full Phase1 Exit。原formal Cases2/3/fullExit BLOCKED、Case4 DEFERRED、main／frozenPhase2／原Blender／locked/history資料不變，沒有外部model API。

English: The operating E1 extension delivers genuine indexed local association, pixel-derived behavior hypotheses, actual multi-frame RGB cards and preserved 3D alternatives. Current full tests/lint/types, loopback/UI, same-run truth isolation and independent output reproduction pass. Low association precision, behavior false positives and N/A global/gap metrics are recorded without test tuning. Original source, v1 lab, concurrent work and formal/frozen gates remain unchanged.


## 2026-10-08 — Local Phase 2 product P7

在已發布E1 `2db6709` 上新增独立product SQLite read model與strict pixel/event DTO。
實際匯入已核對freeze的18 observations／64 events（82records），按CORNER/time索引取5筆，
重啟後page逐值一致。Immutable transactional import保存canonical IDs/payload/order，範圍cursor
綁run/kind/filter；CASE／REPORT／REVIEW以optimistic append-only revision/hash chain另存。
無任意SQL/檔案工具，GT/privatepath/secret禁止进入repository payload。

當次35個新store/DTO tests、14既有Phase2 integration tests PASS；scoped Ruff／strict mypy
PASS。Record/index/ledger corruption、rollback、conflict、cursor tamper與restart皆覆蓋。
本機db排除Git；curated receipt見[data/product](../../data/product/checkpoint_20261008/p7.json)。
此為新純模擬產品續作，不解鎖school/fullExit、live攝影機、外部模型或frozenPhase2。


## 2026-10-08 — Local Phase 2 product P8

新增34維handcrafted RGB-crop appearance、quality/代表照片refs、bounded同分Top-K retrieval與
camera-local short-gap provisional stitching。實際E1 frozen pixels產生150 descriptors／18tracks，
31 stitch hypotheses；保留所有eligible pairs、unmatched、overlap、不確定HOLD與缺失時間，
不用GT、trainedReID或globalidentity，不寫原observations/events或虛构handoff。

當次38 tests（12新product＋既有pixel/localassociation）PASS；Ruff／strict mypy PASS。
RGB/hash/source/run/frame/track lineage、missing/partial、GT污染與alternatives mapping覆蓋。
Actual hashes/counts見[p8 receipt](../../data/product/checkpoint_20261008/p8.json)；完整featurevectors
與maps留local，publichits只返refs/quality與未校準similarity，不宣稱精度改善。


## 2026-10-08 — Local Phase 2 product P9

新增 bounded 中文／英文意圖模板與 typed dynamic investigation plans，服務依檢索結果安排
局部鏡頭／摘要／必要細節／照片工具。單目標、比較、行為及多目標 inquiry 保留原種子、
provisional track、shared-segment conflicts、全部替代 refs；Agent 不做 semantic reranking。
有限呼叫／camera／detail／media budgets與可保存的 stop／resume不重置原預算。
Report分開 workflow／retrieval／Graph complete，操作員review只另存呈現／歧義決策。

當次17 tests PASS，Ruff／strict mypy PASS；fake-tool GT污染、錯stage／scope、失敗、
歧義及全部候選保留覆蓋。見[p9 receipt](../../data/product/checkpoint_20261008/p9.json)。
本段為可調用本機engine，持久化HTTP／真RGB控制室接合另段實驗，沒有任意語言模型、
外部provider或正式研究解鎖。
