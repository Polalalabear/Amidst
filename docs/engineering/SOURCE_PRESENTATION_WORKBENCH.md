# 原校園來源展示與評估邊界

主工作台的研究角色新增「實驗展示」，可直接操作原校園 Office 局部模型的人形回放：
旋轉／平移／縮放、播放／暫停、逐格、seek、速度與循環，並查閱原診斷 PNG。
幾何與時間資料由本機服務供應；這個入口沿用歷史公開投影和候選，沒有重新執行推論。
它與 E0／E1 合成 RGB 場景分別綁定 source、model revision、run、clock 和 units，
不把校園校正混入 E1，也不作跨模型 transform。

## 實際可用內容

| 內容 | 本機 materialization / 行為 |
| --- | --- |
| 展示幾何 | 2 個原來源物件、116 個裁切後頂點、276 個三角形 |
| 原始展示對照 | 原 manifest 的 110 個保留三角形，以 `historical_meshes` 另存；原 bytes 不變 |
| 公開時間序列 | 50 幀、5 Hz、步長 0.2 秒、時間範圍 0.0–9.8 秒，約 10 秒展示 |
| 可見／盲區 | 26 幀 `PROJECTED`、24 幀 `INFERRED_GAP`；原 `OBSERVED`／GAP state 與 role 另留 |
| 候選 | 全部 3 條原 GAP 路徑，維持原順序和完整座標序列，以 opaque candidate refs 呈現 |
| 診斷圖 | 50 個原 PNG 的 opaque media refs；這些是模型展示圖，不能當作未標註 camera RGB sequence |
| 人體 | 青色表示公開可見投影，黃色表示 GAP 候選；人體、朝向與步態均為 `DISPLAY_ONLY` |

來源保持 `SYNTHETIC`、`image_measurement=false`。人體位置取自原公開 body-base／landmark
records；人形形狀與關節擺動只供理解畫面，沒有測得骨架、動作、真實人物身分或新的觀測。
UI 以最近的原公開幀選取人體和診斷圖；呈現計時器的更新頻率不新增 observations，
不把顯示速度當作相機或 CV 採樣率。服務輸出的 50 幀時間與位置保持原值的顯式單位換算，
不外推、不回寫歷史 records。

歷史人體尺寸為 radius 0.3 m、height 1.7 m、clearance 0.05 m。原 manifest 的
`PENDING_HR02_NOT_APPROVED` foot binding 與 `PENDING_HR01_NOT_CERTIFIED` scope authority
仍以 historical fields 保留；它們描述原 manifest 的日期基線，不撤銷或重新解釋後續既有核准。

## 幾何衍生與來源認證

來源是 `school_v3.blend` 在 Scene／frame 220／subframe 0 的既有 evaluated geometry archive。
只使用原 motion manifest 指定的兩個來源物件 `group_0`、`group_0.002`，不從名稱推定
wall、walkability、portal、region 或 collision 語意。公共 DTO 使用 opaque mesh refs。

原始 cutaway 保留原頂點、以 triangle AABB 選取局部範圍，再排除越過 Z lid 的面；
因此原 110 個面全為水平面。新展示另作
`SOURCE_TRIANGLE_SIX_PLANE_CLIP_NO_CAPS_V1`：把同兩個物件的真實來源面裁到同一 box，
只切割與三角化已有面，不新增封蓋、牆面或其他物件。276 個展示三角形中，154 個為
非水平面；此數字僅描述幾何方向，不代表已分類或核准牆面。

原 crop 為 BU `[1320, 1880, -1]` 至 `[1500, 2170, 110]`。依已核准尺度
**1 BU = 0.0247 m**，展示 bounds 為公尺 `[32.604, 46.436, -0.0247]` 至
`[37.05, 53.599, 2.717]`。座標採右手 XYZ、Z-up；derivation receipt 保存顯式
native-world-to-metres 矩陣、parent source／revision、archive／geometry／motion hashes、
source triangle selection digest、裁切範圍、producer hash 和衍生 geometry hash。
原歷史 BU 素材不回寫。

所有 mesh、frame、route 都保存 origin／authority、`source_binding_ref` 及 normalization hash。
`DISPLAY_CONTEXT_ONLY` 幾何只供顯示；`physical_authority_changed=false`、
`semantic_classification_performed=false`、`new_caps_created=false`。
這個裁切不擴大正式 walkability／portal／coverage／collision authority，也不證明全場景遮擋。

| 固定來源 | SHA-256 |
| --- | --- |
| `blender/school_v3.blend` | `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e` |
| `data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz` | `6d30e591d6210707f2b6175bf96dc2fe2395fe0202b24bd0a6df7ee87a5d997c` |
| `human_review/frames/motion_context/motion_manifest.json` | `e77628c145fceb42ae086a76f4de60741147ea525eb12d46e7f23d7ba83d7b69` |
| `human_review/frames/visual_manifest.json` | `f6c4c9fef9dc80fd1717b6a751762b1a09d686b014c1394409b61cb0c9b22d0c` |
| `data/finalization/local_run/dataset/inference/office/context.json` | `56a131626b7c9382f260cb0d088abf6d38ff13127f76d3b5233dd2abdf87dc70` |
| `data/finalization/local_run/diagnostics/office/policy_graph_primary/projected_frames.json` | `0ebdb3762fe181c44ea25456b4525204aaa19dbe957a923c360f2bffdf5d6e48` |
| 同目錄 `candidates.json` | `0212756864986ee5044313058144c7e3fcb56c72e68ebd30b7062e508b9c9b02` |
| `configs/architectural_scale_school_v3.json` | `7e3615a3b0b4485585da9c0f7beefb96955517f7a321910fc008c041f99a3eaf` |

Loader 另驗證原 floor-support receipt，完整 pinned allowlist 見
[`source_presentation.py`](../../src/amidst/workbench/source_presentation.py)。每次載入仍核對
pinned bytes，即使已有解析 cache；任何缺失、hash 不符、非法有限數值、source／scene／scale
不符或輸入 symlink 越界，都拒絕提供展示。PNG 可個別缺失：互動 mesh／motion 仍可用，
該 opaque media ref 回固定 unavailable 錯誤，不以其他影格替代。

原 `.blend` 本輪唯讀核對仍為 468,300,506 bytes，mtime_ns `1791198236746106977`，
SHA 如上。Adapter 不啟動 Blender、不渲染、不儲存來源 scene、不讀 GT／recipe／evaluation。
原素材與 archive 的本機存在不代表可重新上傳；發布仍依 artifact policy，只保留程式、
文件與允許的 curated receipts。

## 本機接口與角色

獨立 provider 為：

```python
load_source_presentation(repo: Path) -> dict
source_presentation_summary(repo: Path) -> dict
source_presentation_media(repo: Path, media_ref: str) -> tuple[str, bytes]
```

工作台使用 `presentations` 列表、`presentation` detail 和 `/api/presentation_media`。
服務端先驗證自己的 role session；三者均限研究角色，detail 再核對當前 opaque
`presentation_ref`。列表或 detail 的來源驗證失敗時回 `UNAVAILABLE`／
`SOURCE_BINDING_UNAVAILABLE`，不換成其他模型。Media 僅允許原 manifest 的 50 個 refs，
核對 hash 和 byte count，拒絕 caller 路徑及未知 refs。

DTO 不帶 private filesystem locators、source archive、GT、hidden actor 或原 target IDs。
這些是人類研究展示接口，沒有加入原 Agent tools allowlist，沒有提供 repository／shell／SQL
入口，也不開放外部模型或服務。啟動與 catalog materialization 依
[共用工作台指南](SHARED_WORKBENCH.md)；缺少固定來源時保留不可用狀態。

## Evaluation 查閱守門

工作台 `evaluation` action 限研究角色，綁定 session 可存取的已註冊 scene。
它只讀預先生成的 aggregate summary，查閱不重新推論、不執行 evaluator、不開 GT。
學校來源展示本身沒有新 accuracy 結果，不能借用 E0／E1 的評估數字，也不能從動畫平順度
推定辨識、關聯或 3D 精度。

[`SceneAdapter.evaluation`](../../src/amidst/workbench/scenes.py) 執行以下既有邊界：

- 先拒絕 symlink 或 `ground_truth.json` reference；讀取上限為 256 KiB。
- JSON 拒絕 duplicate keys 和 NaN／Infinity；strict aggregate DTO 限制欄位、深度、節點、
  array、有限分類鍵、數值、整數 count、hash 與文字，不接受額外 metadata／identity／raw labels。
  不符合條件的內容回 `INVALID_EVALUATION_SUMMARY`，不把 rejected payload 放進錯誤。
- 比對同一 model／run／dataset／config；E0／E1 freeze receipt 與模式集合亦須相符。
  不符回 `STALE`／`EVALUATION_BINDING_MISMATCH`。
- 量測 aggregate 的 canonical content digest 須匹配已發布 immutable receipt 或服務端明確
  設定的 certificate；不能從請求中的 summary 自行產生 certificate 來認證它。
  缺少 certificate 或內容被改動分別回 missing-certificate／content-hash-mismatch。
- 僅為相容而允許無量測數字的有限 `SYNTHETIC_DIAGNOSTIC` 舊摘要；此例外不接受任意 data maps，
  不代表新量測已取得認證。

獨立 evaluation/debug 可以在 inference freeze 之後使用 GT；其 aggregate 的人類查閱權限
不會擴大 Agent 的照片／觀測／事件 tools。原 evaluation records 不清洗或回寫。
新增或變更 summary 即使保留正確 headers，也不能通過內容 digest 和 DTO allowlist 守門。

## 歷史證據與正式待辦

展示來源 checkpoint 為 `883204af854bed301506b39d63ccb33312b79ff2`。
本輪只是把原公開 evidence 與 evaluated source mesh 接成互動研究入口，沒有產生新的正式
Office／corridor dataset、GT annotations、benchmark 或 inference freeze。
原 recovery 的 tests／benchmark／RRD 紀錄仍屬其日期基線；本輪測試不得沿用其 PASS。

正式 Phase 1 仍依 [CODEX_HANDOFF](../operations/CODEX_HANDOFF.md) 為
`PHASE1_FINALIZATION_BLOCKED / PARTIAL_APPROVED`。Cases 1–3 × A/B/C × K、必要消融、
相同 eligibility 的獨立 exhaustive inventory、fresh 5 Hz frozen dataset／inference、
independent evaluation 與 clean-checkout reproduction 必須另續作；Case2／Case3 full gates
未過仍 BLOCKED，Case4 DEFERRED。這個展示不變更原核准、不 thaw frozen Phase 2，
不標成 `PHASE1_VALIDATED_AND_FROZEN`。

## 本輪驗證

P14 綁定 [source validation](../../data/engineering/workbench_20261010/source_validation.json)
與其所在 Git tree／逐檔 code hashes。當次 workbench 122 tests（排除尚未整合的 product bridge
與 gallery）全通過，零失敗／跳過；owned Ruff、workbench strict mypy、19 Node tests 通過。
16 次實際 HTTP 包含 research／management／unknown session／缺失 ref、兩場景認證評估，
重複來源 GET-equivalent reads 逐資料一致。來源 provider 本輪 16 tests 與 evaluation 42 cases
已包含在 122 中，不相加作另一個測試總數。

瀏覽器實際確認 276 面局部模型、人形、0.2 s 逐格、5.0 s 盲區 seek、9.8 s 尾段停止、
2× 與循環控制。三條原候選保留；穿透深度的 dashed route 是展示層，不是可見性量測。
Canonical source SHA／size／mtime、原 frozen records／historical pending labels 均保留。
本段尚未重跑全 repository regression；後續主平台整合會另存當次 receipt，歷史 2652
不視作本輪 PASS。未知的並行 research_accuracy 修改未纳入此 milestone。

2026-10-10 後續 P15 整合另存
[integration validation](../../data/engineering/workbench_20261010/integration_validation.json)：
無排除完整 2873 tests、58 Node tests、Ruff／mypy 183 source files 與 63 次實際 HTTP 通過。
前端用沿原 route points 的 0.018 m 半徑 tube 提高三候選可見性；這是 presentation 層，
保留原 landmark 高度，不改成 body-base 路徑或新的導航證據。Office 獨立來源／公尺標示
避免與 E1 context 混用。原 P14 數字及 receipt 仍是該 milestone 的歷史證據。
