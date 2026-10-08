# 局部跨鏡頭關聯與行為事件研究交接 / Local camera association and events

日期：2026-10-08。狀態：**RESEARCH_PLAN / NOT_RUN**。本文件提供實作順序、實驗設計與下一個對話 prompt；不是已完成的新 dataset、benchmark、CV 品質或正式 Phase 1 驗收。

## 目前起點與可重用能力

重用 `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`，branch `codex/simulation-engineering`。工程基底 `4271b2bdfb255aa15dcddb25cba31127a6890aa6` 已整合 preview、projection diagnostics 及 frozen Phase 2 mock API/repository/replay/consumer。文件基底為 `31171137fa7ab37c160f6b6dcbbde5018565ff7f`；以當下 HEAD／origin／working tree 為準，不 reset 或切換到舊 branch。

`4271b2b` 的2255 tests／Ruff／mypy／HTTP consumer 是原工程驗證，不是本研究的當次 PASS。完整邊界依 [主續作 prompt](PHASE1_NEXT_CHAT_PROMPT.md)、[Agent 契約](../engineering/AGENT_RETRIEVAL_BOUNDARY.md)、[目前交接](CODEX_HANDOFF.md)。

最初唯讀核對 `3117113` 時，`src/amidst/engineering/`、`configs/engineering/`、`tests/engineering/` 有未提交的並行草稿。交接製作期間，另一個工作陸續提交：

- M1 `0cb2f155ef9338d116e22daef5d2bc90e340ad7e`：source-bound registry／獨立 office recovery importer。已讀 [partial certificate](../../data/engineering/simulation_20261008/reviewed_import_certificate.json)：只認證原office structured Case1/3、4 observations／2 events、4 cameras／193 projections、顯式BU normalization；Case2仍BLOCKED，image_measurement=false，Agent allowlist未認證。該checkpoint工作紀錄報36 tests／Ruff／mypy PASS。
- M2 `6a00541307d788b732811a9335485de394d598d5`：程序式雙鏡頭RGB、pixel producer與server-owned stage guards。該checkpoint工作紀錄報每鏡頭51張5Hz PNG、89 measurements／6 local tracks，以及34 tests／Ruff／mypy PASS。這是synthetic lab量測，不是school場景／行為研究或本交接重跑結果。

本交接只讀指定檔案／證據，未執行上述tests、不修改／stage／commit並行程式；其餘association／facade／UI／evaluation等及既有importer增量仍有未提交工作。下一個對話先核對最新提交／receipt與正在進行的工作，續接可用模組，不覆寫或重做另一個執行中的工作；未提交部分不能以檔案存在宣稱PASS。

此時草稿有兩個需解決的實質限制：

- `association.py` 先以 `combinations(ordered, 2)` 列舉所有 segments，再按 camera/time/appearance 過濾；這不是局部候選產生器。
- `RegistryStore` 的 camera/frame/media lookup 遍歷 catalog tuple；已提交 legacy service 也讀 snapshot 後過濾。沒有 filesystem 掃描不代表沒有全量 records／pairs 掃描。

M2的程序式雙鏡頭平面人物輪廓、RGB 前景／連通元件與草稿provisional bindings 可作最小工程起點，但不是 school 場景、通用人物 detector 或已驗證行為辨識。中位數背景對長停留、同色人物交叉／合併與遮擋後換 ID 的影響須實測，不從範例成功推定效度。既有school diagnostic media由 [media audit](../../data/engineering/simulation_20261008/existing_media_audit.json) 核對58張圖片，但合格未標註camera RGB序列為0，不能拿舊5Hz動畫取代新RGB。

## 判斷方式與可行性

可以共同使用空間、時間與人物連續性；輸出是帶證據的 association hypotheses，而非僅依相近性確認同一人。

| 資訊 | 第一版用法 | 限制 |
| --- | --- | --- |
| Camera 空間關係 | 校正、coverage、門界／區域連通與有向可達路徑，建立局部 camera adjacency | 直線距離近可能隔牆、不同樓層或方向不相容；名稱不是 authority |
| 時間 | 統一 clock；比較 track 離開／進入時刻與物理最低 travel time | 時間最近不一定正確；停留／繞路可造成晚到；查詢窗口上限不是物理不可能證明 |
| 人物連續性 | 從 pixels 取得外觀、方向、速度與 track 狀態，按可用性融合 | 相同衣色、視角、光照及遮擋可能混淆；缺量測不補 GT，不宣稱未校準機率 |
| 多鏡頭重疊 | 依 clock 與校正比較同時可見的局部位置／外觀 | 不把同步重疊誤造為離開→抵達的 blind gap |

對非重疊 track 設 `delta_t = next.start - current.end`。合法路徑長度與最大速度形成最低 travel time，考慮 clock／投影不確定性後作物理可行性 gate；不要把 RGB 距離、較晚抵達或 retrieval budget 直接當物理拒絕原因。重疊可見、same-camera recovery、cross-camera gap 分別處理。

剩餘候選可使用明確版本的空間 soft prior、時間殘差／連續性與外觀距離排序；只排序 association hypotheses，不修改原 Graph route score／候選順序。未有校準的分數不是機率；保留 alternatives、unmatched、missing、HOLD、scope-limited 及不確定性。任何 finite window／鄰接集合須說明涵蓋範圍，不聲稱排除所有未檢索的接續。

文獻支持融合方向：[Spatial-Temporal Person Re-Identification（AAAI 2019）](https://ojs.aaai.org/index.php/AAAI/article/view/4921) 將外觀與時空資訊結合以縮小檢索候選；[Deep SORT](https://arxiv.org/abs/1703.07402) 將外觀加入單鏡頭追蹤以改善遮擋期間的身分連續性。這支持方法選擇，不證明本專案的準確率，也不要求本階段安裝其模型或接外部 API。

本計畫對可控 synthetic 閉環、局部檢索與有向區域事件具實作可行性；多人外觀相近／長 blind gap 的唯一身分與行為判定仍有不可辨識情況。研究問題宜聚焦：**少讀取局部資源能否保留接續召回率？時空與外觀各帶來多少增益？不確定的2D證據如何形成保留歧義的3D區域事件？** 單純融合三種資訊本身已有研究先例。

## 避免全域 runtime 掃描

匯入時按明確 manifest 建索引，不以查詢觸發遞迴掃描素材／repository。至少建立：

- scope（place/model/revision/source/context/run/clock）→ camera／region／portal adjacency。
- scope + camera → 依時間排序的 frames／local segments，支援區間 lookup。
- scope + region／portal + time → observation／event refs。
- scope + opaque media/event/track ref → record，按 reference 直接取用。

查詢先固定 scope、起始 track／區域與時間窗，從 index 找命中資料，再沿已定義可達 camera 分批擴查。候選 retrieval 在 pair 形成前完成，禁止先建立所有 segments 的笛卡兒積／兩兩組合才過濾。Registry／snapshot 也不能先全量讀回再假稱局部 lookup；先用小型 scoped in-memory 索引證明，storage port 可後續替換，不要求本輪部署 production DB。

無明確地點／區域／時間的任務先 resolve scope；coverage／clock／index 缺失時明示，不偷偷退回全域掃描。時空 constraints 使用可達路徑，不以固定一跳或直線最近鏡頭保證完整性；允許有界多跳／延長時間窗，公開擴查策略與停止原因。

實測 touched cameras、records/frames/crops/bytes read、pairs considered、延遲、擴查次數及被排除候選。另存 query scope／retrieval coverage／truncation status；`graph.complete` 仍只表示其原搜尋列舉是否 exhausted。局部 inventory 完整性不代替原正式 exhaustive route proof。

## 最小實驗集合

先使用少量局部鏡頭與角色完成可重現 pilot；至少包含以下情境，數量／時間／速度／門檻寫入新的 extension config，不更動 frozen formal configs。

| 組別 | 情境 | 要驗證的失敗／歧義 |
| --- | --- | --- |
| 基本動作 | 直走、過轉角、進門、出門、短停留、折返／局部重訪 | 門界方向、觸發時間、支持畫面及3D區域結果 |
| 相似多人 | 同色／近似外觀，接近時間到達相鄰鏡頭；交叉或同時遮擋 | False merge、false split、ID switch、unmatched與多假說 |
| 不可達負例 | 外觀相似但時間超速／隔牆不可達；外觀不同但時空很近 | 正確物理 gate、外觀增益，不靠外觀唯一編碼答案 |
| 行為反例 | 靠近門不進去、轉角前折返、正常通過但暫時遮擋 | 不把消失當進門／轉角穿行，不把停留當遊蕩 |
| 同端點不同中段 | 相同可見端點與近似時間，盲區中慢走／停留／繞路 | 無法區分時保留不同可行假說；不得用 GT 挑唯一答案 |
| Recovery／缺失 | 同鏡頭復現、另一人替代出現、漏影格／漏檢、碎片 tracks | HOLD adapter、不造 handoff、不補 GT／缺圖 |
| Coverage／clock | 未知或漏 coverage、時鐘偏差、缺 clock mapping、超出 lookup window | 不確定／scope-limited 結果與漏取率，不誤宣稱完整 |

人物類別數量不是第一個瓶頸，先解決可見 RGB、遮擋、時間同步與外觀歧義。程序式輪廓是 E0 diagnostic；之後以新 run 的較真實 pinhole camera／RGB scene序列（E1）驗證視角、光照及背景變動。保持原 Blender/source 不變，合法地點／門界不足時使用明確 SYNTHETIC_CONFIG fixture，不冒充核准 school portal 或學校正式 benchmark。

## 兩層實驗與指標

**檢索實驗：**固定 scene/run/clock/query scope/eligibility，以局部 index 查候選，對照 evaluator 中獨立建立的同 scope 完整候選 inventory。量測真實接續 retrieval recall、候選量、讀取量、延遲及擴查停止原因。Offline inventory／GT 只供評估，不回流 runtime；不能只以少讀資料宣稱成功，須同時報漏取率。

**Association feature 消融：**在相同 RGB／local tracks／候選 pool／硬限制下，比較 full fusion，以及分別拿掉空間 soft prior、時間殘差 score、外觀連續性三個單因素版本。合法 clock、reachability、速度／物理限制與 GT 隔離不移除；這不是改動原正式 Baseline A/B/C 或 Graph ranking。先隔離 feature 增益，再量測檢索與關聯一起運行的完整 pipeline。

| 層 | 指標／結果 |
| --- | --- |
| Association | Link precision/recall、false merge/split、ID switches、identity-candidate Recall@K、歧義／未定比例；按 same-camera／cross-camera／overlap 分組 |
| Behavior | 每類 precision/recall、混淆矩陣、誤報、觸發時間／方向誤差與無法判定比例；可見支持事件與 blind-gap 假說分開 |
| Retrieval | 接續漏取率、cameras／records／frames／bytes read、pairs considered、query latency、擴查次數／停止原因 |
| Geometry | 合法 authority／單位下的 projection／region／物理違規、候選數與termination；缺reference或authority標N/A |

Identity-candidate Recall@K 與原 route Coverage@K 是不同指標。不要沿用名稱混淆母體；未有整段身分軌跡與可核對 evaluator 時，不補造 IDF1。採用原正式 metric 時仍依原 [benchmark protocol](../research/PHASE1_BENCHMARK_PROTOCOL.md)，不自行放寬公式／tolerance／authority。

以完整 run／trajectory 分 development/test，不把同一軌跡相鄰影格拆到兩邊。先用 development 固定 weights／thresholds／time windows／appearance policy，再 freeze config及推論，最後 evaluator 讀 test GT。若聲稱外觀泛化要持出 actor/appearance；跨地點泛化要持出 camera pair／scene；否則只報該 synthetic pilot 範圍。低精度可公開，不能看 test GT 後調門檻。

GT poisoning 保持 pixels、校正、配置與可見輸入固定，只替換／移除 GT／recipe/reference sidecars；檢索、關聯及推論 hashes 不變。RGB 不同可改變推論，不要求生成新影像後結果仍相同。

## 行為層與多畫面交付

新增外層 `LocalBehaviorEvent` 或相當 composition，不改原 `BoundGapEvent`／`TrajectoryHypothesis` 語意。至少保存 event kind、time range、scope、local track／association refs、來源 frames、region／portal refs、rule/config version、支持／衝突、alternatives、不確定性和detail/replay refs。

進／出門用已定義兩側 region 與有向門界穿越；轉角用可見方向／合法投影與另一側支持。只看到消失時輸出「轉角附近失去可見性」，不能自動判成已過轉角。遊蕩先操作化為反覆折返／局部重訪／繞行模式，文字標「可能遊蕩」；長 gap 或DWELL／DETOUR本身不代表人的意圖。必要門檻由development配置，不發明已校準行為機率。

每個事件卡按時間展示至多3–5張實際RGB（前／觸發／後、必要時跨鏡頭），附camera/time/evidence refs，區分pixel measurement、PROJECTED與INFERRED_GAP。缺照片標缺失，blind gap用局部3D候選畫面表示，不生成照片冒充camera證據。主展示無GT overlay，debug獨立；候選順序不因摘要或MockAgent解釋改寫。

## 下一個對話可直接貼上的 prompt

```text
請在 Amidst 接續局部跨鏡頭人物關聯與行為事件研究，完成可操作的純模擬 pilot：用 camera 可達拓樸、clock/time、pixel-derived 人物外觀／方向／運動連續性建立 association hypotheses，輸出進門、出門、轉角、停留與「可能遊蕩／局部重訪」的多影格事件卡。第一版精度可低，但須如實量測、保留歧義與可重現證據；不接真camera、OpenAI或其他外部模型API。

使用既有 checkout /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization，branch codex/simulation-engineering。先核對pwd/status/HEAD/origin，從包含4271b2b工程基底與3117113文件基底的最新已驗證checkpoint續作；不reset、不切研究/frozen/main分支。交接期間已見M1 registry/office partial importer提交0cb2f15與M2 RGB/perception/stage提交6a00541；依live狀態與receipts重用，不重做。其餘association/facade/UI/evaluation及importer增量有未提交並行工作；先確認當下是否已完成/提交或仍由其他工作執行，保留並續接，不覆寫，不以檔案存在宣稱PASS。

先讀 docs/operations/LOCAL_CAMERA_EVENT_RESEARCH_HANDOFF.md、docs/operations/PHASE1_NEXT_CHAT_PROMPT.md、docs/operations/CODEX_HANDOFF.md、docs/specs/DEVELOPMENT_RULES.md、docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md。只讀指定入口與必要模組，不全repo/素材掃描。此局部研究是既有M1–M6的具體化；原formal研究義務仍保留。

依序實作並驗證：
R1. 核對草稿與可用RGB素材；固定新的extension protocol：事件定義、候選單位、scope/clock/unit/authority、missing政策、split與未校準分數語意，沿用原formal契約與核准邊界。
R2. 優先完成scoped camera/region/portal adjacency、camera-time索引與opaque-ref直接lookup；在形成pairs之前以起始track＋可達camera＋合法時間窗取局部候選。禁止combinations全片段/全snapshot/catalog枚舉後才過濾；缺index/coverage明示，不fallback全域掃描。記錄讀取量、pairs、scope、擴查與截斷；retrieval coverage和graph.complete分開。
R3. 核對/完成真正RGB-derived local tracks與圖像／GT隔離；程序式silhouette是diagnostic，再接較真實camera/RGB序列，保留source/calibration/producer/config/media hashes。GT與recipe只供生成/評估，不用作外觀或global actor identity；photos-only不讀預存另一模式答案。
R4. 實作/驗證多假說association與provisional target binding adapter，保留原local IDs映射；overlap、same-camera recovery與cross-camera gap分開。Camera位置近/時間最近/同色不等於同一人；晚到、缺外觀或lookup窗口外不直接當物理不可達；合法Graph/reconstructor保留原physics、排序與termination。
R5. 新增局部行為事件層及多畫面UI；進出門需兩側region/方向，轉角消失不自動等於穿行，遊蕩定義為可量測折返/重訪模式，盲區保留alternatives。每卡3–5實際照片或如實缺失、局部3D候選、行為假說/支持/衝突/uncertainty與detail/replay refs；不得只交預錄影片或用生成圖冒充camera證據。
R6. 建立交接中的基本案例、相似多人、不可達/行為負例、same-camera復現、缺圖與clock/coverage案例。Development校準後freeze；先跑局部retrieval漏取/讀取量實驗，再固定candidate pool做full fusion及去除空間soft prior/時間score/appearance的單因素消融，原hard physics與GT隔離不拿掉。Test GT只在inference freeze後讀；不修改原正式A/B/C或把pilot當full Exit。
R7. 報association precision/recall、false merge/split、ID switches、identity-candidate Recall@K、行為混淆與誤報/未定、retrieval recall/reads/latency、projection/物理檢查。缺metric/reference標N/A。保持RGB/calibration/config不變做GT/recipe/reference poisoning與邊界/錯scope/mode/stage測試；只報實際結果。
R8. 接回typed本機tools與MockAgent可操作閉環，服務端授權mode/stage並核對同run freeze receipt；交付同run dataset/config/media/registry/inference/evaluation hashes、結果表、工具紀錄、必要RRD/PNG、重建命令及milestone驗證。每個可執行milestone獨立commit/普通push codex/simulation-engineering；不stage別人的並行工作。

保留immutable Blender/source、locked inputs與歷史資料，原phase2/integration-hardening/tag FROZEN，不merge main。重用一份checkout/environment和單一重型素材，不累積worktrees/raw副本。OpenAI接線與token兜底章節維持空白；Agent只能用scoped tools，不給repository/filesystem/任意SQL/shell。Runtime不外送照片/檢索資料；Git push仍依既有授權與artifact policy，不上傳LOCAL ONLY/raw/private/secret。

Formal Cases2/Case3/full Exit仍BLOCKED、Case4 DEFERRED；新corridor需原scoped adapters、source-bound HOLD、portal/anchor evidence gate與相同eligibility的獨立exhaustive route inventory。工程pilot不解除原研究gate。遇到缺資產/缺authority，寫具體blocker並續做獨立mock工作，不假造完成；更新handoff、WORK_LOG及相應契約，持續至可操作pilot與當次評估交付完成。
```

## English

This is a proposed local synthetic association/event experiment, not new validation. Combine physically reachable camera topology, clock-aware temporal feasibility and pixel-derived appearance/motion while retaining ambiguous hypotheses. First implement indexed candidate retrieval before pair enumeration; evaluate retrieval recall/reads separately from association feature ablations on fixed candidates. Preserve independent formal gates, truth isolation and server-owned Agent boundaries. Existing concurrent prototype files were read only and are not certified by this handoff.
