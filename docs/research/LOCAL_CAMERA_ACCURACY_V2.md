# Local camera accuracy v2 / 研究精度改善

2026-10-10；**MEASURED_SYNTHETIC_RESEARCH_V2_WITH_TRADEOFFS**。使用既有
`phase1-finalization / codex/simulation-engineering`；重用 E1 每 split 244 張 RGB，
無新 scene render、raw 副本或外部 model API。全部結果和來源 hashes 收於
[當次收據](../../data/engineering/accuracy_20261010/validation.json)。

新版本改善了局部 ID 連續性與固定 pool 的檢索排名，但並未全面提高精度。
追蹤的嚴格門檻增加碎片／局部候選讀取量；完整融合不是每項消融的最佳版本；
可見行為仍有漏報，dwell 新增誤報。v1、P8 與原 Graph 路線排序均保留，
新結果只交給版本化研究 adapter，未替換共用工作台的 canonical data。

## 版本、凍結與比較設計

[鎖定政策](../../configs/research/local_camera_accuracy_v2.json) SHA256：
`41aa6f9f69b42ce9a1bbb06af5830f8608f56f7c9d4fb1452199e7b74789ceff`。
Development 的 64 pairs／8 eligible queries 選出 robust RGB + feasibility space +
原 direction/time；速度殘差與低權重融合未穩定改善，所有十個選項／退步收於
[development selection](../../data/engineering/accuracy_20261010/development_selection.json)。
沒有因 test 上 prior-only／motion diagnostic 較好而改選政策。

`accuracy-development-v2-final` 和 `accuracy-test-v2-final` 各先完成八個版本、
兩模式推論凍結，獨立 evaluator 才開 GT。source run ID 仍是 immutable
`local-camera-{development,test}-v1`；新 experiment ID、version、config、
variant/mode receipt 和 opaque refs 另行綁定。固定 pool 保留 source local IDs；
新 pixel producer 使用 `track-v2`／`pixel-v2` namespaces，不回寫舊 IDs。

| 版本 | Pixel | Appearance | Space / time soft prior | Behavior |
| --- | --- | --- | --- | --- |
| baseline | v1 | v1 | v1 | v1 |
| pixel_only | v2 | v1 | v1 | v1 |
| appearance_only | v1 | robust crop | v1 | v1 |
| prior_only | v1 | v1 | feasibility / 原 direction | v1 |
| features_full | v1 | robust crop | feasibility / 原 direction | v1 |
| behavior_only | v1 | v1 | v1 | v2 |
| motion_diagnostic | v1 | robust crop | feasibility / speed residual | v1 |
| end_to_end | v2 | robust crop | feasibility / 原 direction | v2 |

Feature versions固定 RGB、原 tracks、115 pairs、硬 clock/reachability/speed gates
及 Graph snapshot。Pixel versions 改變 segmentation/pool/eligibility，另報分母，
不能把两群視為同一固定實驗。所有分數與 crop quality 未校準，不是機率。
測試集曾供整合回歸；兩個 split 共用 synthetic scene／appearance，**非 sealed
holdout**，沒有 real-camera、trained ReID、跨地點或未檢出人物 recall 證據。

## 重現基線及誤差 taxonomy

V1 development/test 的兩種模式，perception／inference／events 均逐 byte 重現。
Test 的 150 measurements／18 tracks、115 local pairs／153 global diagnostic pairs、
conditional true-next 8/8、precision .350／recall .467、8 local ID switches、
contact recall .900／ground RMS .304511 m 與已交付基線一致。P8 bundle hash 與
5 eligible queries 的 .4/.6/.8 也從相同 RGB/pool 重現。

[版本化 baseline taxonomy](../../data/engineering/accuracy_20261010/baseline_taxonomy.json)
包括 pixel merges、fragmentation、ID switches、appearance confusion、space/time
prior、door approach/crossing、corner turnback、dwell/possible-loitering。Detailed
scoped refs 位於 ignored `accuracy_v2/error_taxonomy.json`，不是全素材巡查。
Development 門口左側新 component 搶走合理延續 track、相似衣色交會／遮擋、
重疊 corner regions 的三點方向 jitter 都有可核對的局部例子。

## Pixel continuity

V2 重用原 detector 與所有 contact/bbox，改用 frame-wide one-to-one assignment、
velocity prediction、appearance/shape 軟成本、短 gap memory 和 merge quarantine。
沒有用 GT actor IDs 補 track，沒有新增觀測點。

| Split | v1 → v2 switches | Tracks | Fragmented tracks | Mixed known tracks | Contact recall / RMS |
| --- | --- | --- | --- | --- | --- |
| development | 9 → 3 | 14 → 17 | 0 → 2 | 4 → 2 | .947761 / .288620 m，完全不變 |
| test | 8 → 4 | 18 → 21 | 0 → 7 | 6 → 3 | .900 / .304511 m，完全不變 |

Test single-measurement tracks 1→6；不是全面減少 fragmentation。剩餘 switches
位於 CORNER 8.8–9.6s、20.0–21.2s，DOOR 13.2–14.4s、17.2–17.6s；有獨立
`evaluation/scoped_remaining_errors.json` 的原 frame／observation refs。遮擋、
近似外觀與長缺檢仍不能由這個 RGB component detector 解決。
Development 的必要 pixel 消融及 freeze hashes 見
[pixel ablations](../../data/engineering/accuracy_20261010/pixel_ablations.json)。
Global false merge/split、IDF1 仍 N/A，以上 fragmented 狀態只描述已產生的 local tracks。

## 固定候選池關聯與外觀

Test association eligibility：8 queries，15 同身份 physically eligible positive
pairs；所有列使用相同 115 pairs／硬限制／Graph routes。

| 固定 tracks / pool | Recall@1 | @3 | @5 |
| --- | --- | --- | --- |
| baseline | .375 | 1.000 | 1.000 |
| appearance_only | .500 | 1.000 | 1.000 |
| prior_only | .750 | 1.000 | 1.000 |
| features_full（development 選定） | .625 | 1.000 | 1.000 |
| motion_diagnostic | .750 | 1.000 | 1.000 |
| features_full without space | .625 | 1.000 | 1.000 |
| features_full without time | .625 | .750 | 1.000 |
| features_full without appearance | .625 | 1.000 | 1.000 |
| features_full appearance only score | .750 | 1.000 | 1.000 |

新融合沒有勝過 prior-only 或 appearance-only score；完整消融與每列 TP/FP/FN、
unresolved 在收據保留。Soft features 只改 association score／distance，原 hard
status 和 provisional pairs不變，所以這些 fixed-pool 列的 pair precision/recall
仍 .350/.467；ranking 改善不能冒充 link acceptance 改善。

Robust crop 使用 RGB chromatic parts、foreground/quality 與 medoid/outlier aggregation；
原 crop observations 和 rejected/outlier refs仍存在。Pure-track 外觀檢索是另一
population，不和 association 8 queries 混用：

| 同一 P8 produced pure-track pool | Queries | Mean RGB @1/3/5 | P8 handcrafted | Robust crop |
| --- | --- | --- | --- | --- |
| 固定 v1 tracks | 5；排除 6 mixed | .2/.6/.8 | .4/.6/.8 | .8/.8/1.0 |
| 新 v2 tracks，另立實驗 | 13；3 mixed、1 unresolved | .308/.692/.846 | .385/.769/1.0 | .462/.692/.923 |

Pool digest equality逐列驗證；missing descriptor仍計入原 eligible query denominator，
K cutoff ties全部保留。V2 track pool的 robust @3/@5 低於 P8；不是全面外觀提升。
固定 v1 五個 query 全為 HIGH；新 v2 有 LOW population，但這些 quality不是身份純度認證。

## 端到端 pool、讀取與 latency

V2 21 tracks形成29 local segments（原18），pair pool 115→327、eligible positive pairs
15→84、ranking query denominator 8→20。Pair precision/recall .385/.560，ranking
Recall@1/3/5 .850/1/1；只描述**新 produced population**，不能直接當舊八個 query 的 gain。
New pool without-space @1=.900、without-appearance=.800、without-time=.600；完整
融合仍非最佳。Geometry hard speed／configured-region violations 皆 0，並非 school
walkability 或全域 collision 認證。

| 指標 | v1 原 tracks | v2 tracks |
| --- | --- | --- |
| 獨立 fixed-policy inventory取回 | 115/115 | 327/327 |
| conditional true-next | 8/8 | 21/21 |
| association index records read / entries touched | 161 / 143 | 411 / 382 |

沒有全 runtime pair scan；候選形成前仍用原 scoped index。上面條件只涵蓋已檢出、
可被 evaluator標記的 segments，不代表未檢出人物 recall。原 global diagnostic
153 pairs也不和新 segment denominator混比。當次 120 frozen camera/time queries
的 median/p95 為 .616/1.507 ms（photos-only）、.600/1.440 ms（plus）；最大
records read=70、entries touched=75，無RGB bytes讀取。完整 telemetry 在 adapter/evidence
receipts；import、RGB/CV、crop
及 index build 成本另存 `timings.json`，不塞進 inference hashes。

## 可見行為，全部保留失敗與未定

V2 要求重複清楚 portal 兩側樣本、exclusive corner arms及較長方向／位移支持。
Dwell 使用 radius + windowed velocity；revisit要求實際離區／回訪，重複 reversal
須有新 recovery leg。弱 v1 candidates保留 `support_state=UNKNOWN`，不能從
disappearance 或單次 stop推論進門／轉角／人的意圖。全部盲區候選、timings與順序保留。

Test recipe reference是 ENTER3、EXIT2、CORNER1、DWELL1、POSSIBLE_WANDERING1。
下表順序 **TP / FP / FN / unresolved**；unknown保留 candidate和完整 truth FN分母。

| Kind | v1 | behavior_only（固定原 tracks） | end_to_end（新 tracks） |
| --- | --- | --- | --- |
| ENTER | 0/0/3/2 | 0/0/3/2 | 1/0/2/1 |
| EXIT | 0/0/2/4 | 0/0/2/4 | 1/0/1/0 |
| CORNER | 0/5/1/1 | 0/0/1/6 | 0/0/1/4 |
| DWELL | 1/0/0/0 | 1/1/0/1 | 1/1/0/1 |
| POSSIBLE_WANDERING | 0/1/1/3 | 0/0/1/4 | 0/0/1/0 |

Fixed behavior v2 visible candidates 18→20，其中13/20 evidence UNKNOWN；end-to-end
12 candidates，7/12 UNKNOWN（另外身份 unresolved在class表獨立保留）。End-to-end
ENTER recall1/3，EXIT1/2，DWELL1/1但precision1/2；CORNER與wandering recall仍0。
弱 corner／wandering 改為unknown使supported FP減少，precision為 N/A，**不是已解決
識別能力或提高precision的證明**。Development 的 corner TP1也轉unknown，door
recall有退步；完整per-kind表、confusion與未mask的candidate diagnostic保留。
沒有獨立 labeled blind-gap behavior population，其 class precision/recall仍N/A。

## Adapter、實際照片與 replay

Factory：`amidst.research_accuracy.adapter.load_service(frozen_root, variant=..., mode=...)`。
它只驗證／讀 frozen artifacts，重用既有 `LocalPilotService`／8 typed tools和 scoped
interval index；GET／query不重跑 inference或讀GT。Config/producer/media/source/context/
clock/variant/mode綁 receipt；opaque event/observation refs包含 experiment、variant、mode
及 binding hash。`SUPPORTED / UNKNOWN / GAP_ALTERNATIVES`是新外層契約，adapter
consumer應呈現此狀態；v1 transport schema/rule literal保留，composer/config version另綁v2。
沒有改共用前端、人審 backend或其並行草稿，也沒有宣稱遷移已完成。

Ignored `test/final/cards_review/` 有七類/狀態的3–5張實際source RGB +3D卡片與
`.replay.json`：supported/unknown door、unknown corner/loss、dwell、具三條路線／六種
timing的blind alternatives。照片不是新生成的camera evidence；3D點是PROJECTED，
路線是INFERRED，無GT overlay／observed跨盲區連線。Runtime typed replay保留完整
refs、routes/timings；圖形只簡短呈現。已實際開圖核對door／corner／gap card。

## 重建與驗證

在既有 checkout／uv環境執行。所有輸出須新空目錄；completed build/evaluation/cards
禁止覆寫。RGB仍只在原E1 source，每次build獨立重算兩模式。以下`NEW_*`由操作者指定：

```sh
UV_CACHE_DIR=/private/tmp/amidst-uv-cache uv run --offline --no-sync \
  python -m amidst.research_accuracy.baseline \
  --source data/engineering/local_run/local_camera_v1/test/checkpoints/final \
  --output NEW_BASELINE_OUTPUT
uv run --offline --no-sync python -m amidst.research_accuracy.development \
  --source data/engineering/local_run/local_camera_v1/development/checkpoints/final \
  --output NEW_DEVELOPMENT_SELECTION
uv run --offline --no-sync python -m amidst.research_accuracy.development_pixel build \
  --source data/engineering/local_run/local_camera_v1/development/checkpoints/final \
  --output NEW_PIXEL_ABLATION_OUTPUT
uv run --offline --no-sync python -m amidst.research_accuracy.development_pixel evaluate \
  --output NEW_PIXEL_ABLATION_OUTPUT
uv run --offline --no-sync python -m amidst.research_accuracy.run build \
  --source data/engineering/local_run/local_camera_v1/test/checkpoints/final \
  --output NEW_FROZEN_OUTPUT --config configs/research/local_camera_accuracy_v2.json \
  --experiment-id accuracy-test-v2-final
uv run --offline --no-sync python -m amidst.research_accuracy.run verify --output NEW_FROZEN_OUTPUT
uv run --offline --no-sync python -m amidst.research_accuracy.run evaluate --output NEW_FROZEN_OUTPUT
uv run --offline --no-sync python -m amidst.research_accuracy.presentation --source NEW_FROZEN_OUTPUT
uv run --offline --no-sync python -m amidst.research_accuracy.validation \
  --source NEW_FROZEN_OUTPUT --receipt NEW_ADAPTER_RECEIPT
uv run --offline --no-sync python -m amidst.research_accuracy.verify \
  --source NEW_FROZEN_OUTPUT --output NEW_REPRODUCTION_OUTPUT
```

Frozen current data位於 ignored `data/engineering/local_run/accuracy_v2/{development,test}/final`。
詳盡 taxonomy可用`python -m amidst.research_accuracy.taxonomy --source-root
.../local_camera_v1 --baseline-root .../accuracy_v2/baseline/replay-v1 --output
NEW_DETAIL_JSON --receipt NEW_CURATED_JSON`重建。

當次 research／相關legacy scope回歸170 tests PASS（不是全repo），Ruff／strict mypy
和diff checks見收據。Adapter兩模式實際typed major-flow與14negative checks PASS。
GT/recipe/reference採exact-path虛擬replacement/removal，immutable source原bytes不動；
兩個fresh outputs所有variant/mode pixel/inference/events/receipts hashes相同，runtime
sidecar read attempts=0。Removal rebuild再獨立evaluate後，完整comparison.json逐byte相同。
這不等於formal clean-checkout reproduction。Initial摘要reader的欄位KeyError已修正並
以相同政策重凍結；test GT是在最終freeze後才開，draft目錄未覆寫或當成final。

Git僅發布code/config/docs和curated counts/hashes；RGB、GT、完整debug、descriptors、
PNG/replay snapshots仍LOCAL ONLY。原Blender/source、v1/P8 frozen bytes、main和frozen
Phase2不變。Case2/Case3/full Exit仍BLOCKED，Case4 DEFERRED，Phase2/tag 5b51d2c FROZEN。

## English conclusion

V2 improves fixed-pool appearance retrieval and association ranking, and reduces local
identity switches on the same detected RGB contacts. It also increases fragmentation,
indexed pair volume and read cost. Development-selected fusion is not best on every test
ablation; the policy remains unchanged. Weak corner/wandering candidates become UNKNOWN,
without removing reference false negatives; recall remains zero. Dwell gains a false positive.
The changed producer population is reported separately. Reproducibility and truth isolation
are verified locally, with no sealed-holdout, trained ReID, global identity, real-camera,
cross-place or formal acceptance claim.
