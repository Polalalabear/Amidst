# Project Glossary Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Prevent the same term from carrying incompatible meanings across product,
architecture, dataset, evaluation, retrieval, and Agent documents.

### Status Convention

- `CONFIRMED`: a human-confirmed definition supported by an authoritative artifact.
- `PROPOSED`: a candidate definition awaiting confirmation.
- `OPEN`: the definition or boundary is unresolved; use this when uncertain.
- `DEFERRED`: definition work is intentionally postponed.
- `REJECTED`: a definition was explicitly rejected and its rationale is recorded.

### Ownership Boundary

This glossary owns shared terminology. Domain specifications own how a shared
term behaves in their context:

- System Architecture owns which component produces or stores an Event.
- Evaluation Framework owns how Event correctness is evaluated.
- Dataset Specification owns how Event Ground Truth is annotated.
- Retrieval Specification owns how an Event and its Evidence are retrieved.

Specifications should reference shared definitions rather than create competing
ones. If a definition is unresolved, keep it `OPEN` instead of selecting one.

### Editing Rules

- Define a term operationally enough to determine what is and is not an instance.
- Identify the source of truth and related IDs where relevant.
- Link approved definitions to schemas or decision records.
- Use `OPEN` when boundaries are unresolved.

### Terms

| Term | Working definition | Distinguish from | Source of truth / artifact | Status |
| --- | --- | --- | --- | --- |
| Observation | TODO: define captured input unit and time/source identity | Detection, Evidence | TODO | OPEN |
| Detection | TODO: define a per-observation perceived entity candidate | Object, Track | TODO | OPEN |
| Object | TODO: define non-person domain entity, if needed | Detection, Person, Track | TODO | OPEN |
| Person | TODO: define whether this is a class, entity, or privacy-sensitive identity concept | Object, Detection, Track | TODO | OPEN |
| Track | TODO: define temporal identity hypothesis and lifetime | Detection, Object / Person | TODO | OPEN |
| Camera | TODO: define physical device, stream, calibration, or logical source | Observation source | TODO | OPEN |
| Zone | TODO: define semantic spatial region and boundary | Location | TODO | OPEN |
| Location | TODO: define spatial value/granularity | Zone, coordinates | TODO | OPEN |
| Event | TODO: define interpreted occurrence, interval, entities, location, and evidence | Observation, Alert | TODO | OPEN |
| Alert | TODO: define notification/policy outcome | Event | TODO | OPEN |
| World State | TODO: define authoritative structured system knowledge at a version/time | Retrieval result, UI state | TODO | OPEN |
| Evidence | TODO: define traceable support for a record, event, alert, or answer | Prediction, explanation | TODO | OPEN |
| Ground Truth | TODO: define approved reference labels/rubric and version | Prediction, benchmark result | TODO | OPEN |
| Benchmark | TODO: define frozen data, protocol, evaluator, and versions | Dataset, experiment | TODO | OPEN |
| Retrieval | TODO: define grounded execution of an information request | Agent reasoning, storage | TODO | OPEN |
| Structured Retrieval | TODO: define deterministic access using fields, relations, and filters | Semantic Retrieval | TODO | OPEN |
| Semantic Retrieval | TODO: define meaning-based retrieval over approved unstructured content | Structured Retrieval | TODO | OPEN |
| RAG | TODO: define only if generation uses retrieved context | Retrieval in general | TODO | OPEN |
| Tool Call | TODO: define a versioned Agent action/request and its result | Retrieval execution | TODO | OPEN |
| Agent | TODO: define allowed intent interpretation, tool planning, and answer behavior | Retrieval Layer, UI | TODO | OPEN |
| Digital Twin | TODO: define which physical/digital state, time, and interactions it represents | 3D visualization alone | TODO | OPEN |

### Conceptual Distinctions

These boundaries do not finalize the individual term definitions.

| Distinction | Existing authority | Status |
| --- | --- | --- |
| Observation is not inference | Project data-provenance boundary | CONFIRMED |
| Ground Truth is not prediction | Project Ground Truth and benchmark integrity rules | CONFIRMED |
| Detection is not Track | Definitions and precise relationship still require review | OPEN |
| Event is not Alert | Definitions and promotion/notification relationship still require review | OPEN |
| Retrieved Evidence is not Agent Interpretation | Project Retrieval and Agent boundary | CONFIRMED |
| World State is not Agent Answer | Project Retrieval and Agent boundary | CONFIRMED |

### Relationship Questions

- Can one Observation contain many Detections?
- Can a Track represent a person/object without identifying a real individual?
- Is every Event eligible to become an Alert?
- Is Evidence immutable, versioned, or derived?
- Does World State contain predictions, observations, ground truth, or separate views?
- When does a retrieved record become evidence for an Agent answer?

### Expected Artifacts

- Approved operational definitions for terms used in confirmed requirements.
- Explicit distinctions for commonly conflated concepts.
- Links to authoritative schemas, owners, and decision records.

### Document Acceptance Checklist

- [ ] Definitions are consistent across all planning documents.
- [ ] Privacy-sensitive identity concepts are explicit.
- [ ] Retrieval is not defined as synonymous with RAG.
- [ ] Digital Twin is not reduced to a disconnected 3D model.
- [ ] Unresolved semantic boundaries remain `OPEN`.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的與權責

避免同一術語在產品、架構、資料集、評估、資料檢索與 Agent 文件中出現
互不相容的意思。本術語表負責共用定義；各領域規格負責該術語在自身情境
中的行為。定義尚未釐清時保持 `OPEN`，不要自行選定。

狀態使用 `CONFIRMED`、`PROPOSED`、`OPEN`、`DEFERRED` 與
`REJECTED`。編輯時應提供足以判斷是否屬於該詞的操作性定義，必要時指出
資料依據、相關 ID、schema 或決策紀錄。

### 術語

| 術語 | 待定義的工作含義 | 必須區分 |
| --- | --- | --- |
| Observation／觀測 | 有時間與來源身分的輸入單位 | Detection、Evidence |
| Detection／偵測 | 單次觀測中的感知實體候選 | Object、Track |
| Object／物件 | 非人物領域實體（如有需要） | Detection、Person、Track |
| Person／人物 | 類別、實體或涉及隱私的身分概念 | Object、Detection、Track |
| Track／軌跡 | 隨時間延續的身分假設與生命週期 | Detection、Object／Person |
| Camera／攝影機 | 實體裝置、串流、校正或邏輯來源 | Observation source |
| Zone／區域 | 具有語意與邊界的空間範圍 | Location |
| Location／位置 | 空間值與粒度 | Zone、座標 |
| Event／事件 | 具有區間、實體、位置與證據的解讀結果 | Observation、Alert |
| Alert／警示 | 通知或政策結果 | Event |
| World State／世界狀態 | 特定版本／時間的權威結構化系統知識 | Retrieval result、UI state |
| Evidence／證據 | 支持紀錄、事件、警示或回答的可追溯內容 | Prediction、說明 |
| Ground Truth／真值 | 經核准的參考標註／評分規則與版本 | Prediction、基準結果 |
| Benchmark／基準測試 | 凍結的資料、流程、評估器與版本集合 | Dataset、experiment |
| Retrieval／資料檢索 | 依據資料執行資訊需求 | Agent 推理、儲存 |
| Structured Retrieval／結構化檢索 | 透過欄位、關係與篩選條件確定性存取 | Semantic Retrieval |
| Semantic Retrieval／語意檢索 | 依語意搜尋已核准的非結構化內容 | Structured Retrieval |
| RAG | 只有生成確實使用檢索內容時才定義 | 一般 Retrieval |
| Tool Call／工具呼叫 | 有版本的 Agent 動作／請求與結果 | Retrieval execution |
| Agent | 意圖判讀、工具規劃與回答的核准行為 | Retrieval Layer、UI |
| Digital Twin／數位孿生 | 所代表的實體／數位狀態、時間與互動 | 單獨 3D 視覺化 |

上述工作定義目前仍為 `OPEN`，除非具約束力文件另有確認。

### 必須維持的概念界線

- Observation 不是 inference（`CONFIRMED`）。
- Ground Truth 不是 prediction（`CONFIRMED`）。
- Detection 與 Track 的精確關係仍 `OPEN`。
- Event 與 Alert 的精確關係仍 `OPEN`。
- Retrieved Evidence 不是 Agent Interpretation（`CONFIRMED`）。
- World State 不是 Agent Answer（`CONFIRMED`）。

### 驗收條件

- [ ] 所有規劃文件使用一致定義。
- [ ] 涉及隱私的身分概念有明確界線。
- [ ] Retrieval 不等同於 RAG。
- [ ] Digital Twin 不被簡化成孤立的 3D 模型。
- [ ] 尚未釐清的語意邊界維持 `OPEN`。
