# System Architecture Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **What are the system responsibilities, boundaries, sources of truth,
and information flows?** This document does not decide monolith versus
microservices or select a technology stack.

### Architecture Goals

| Goal ID | Goal | Why required | Verification | Status |
| --- | --- | --- | --- | --- |
| ARCH-xxx | TODO | TODO | TODO | OPEN |

### Architecture Principles

| Principle | Rationale | Trade-off | Status |
| --- | --- | --- | --- |
| Evaluation at relevant layers | Diagnose errors before they reach end-to-end output | Requires layer contracts and ground truth | PROPOSED |
| Grounded evidence flow | Preserve traceability from observations to answers | Adds provenance requirements | PROPOSED |
| Replaceable modules | Allow baselines and improved components to be compared | Requires stable interfaces | PROPOSED |
| Structured retrieval first where data is structured | Keep deterministic queries reproducible | Semantic search may still be needed later | PROPOSED |

### System Context

| External actor / system | Sends | Receives | Trust boundary | Status |
| --- | --- | --- | --- | --- |
| Physical environment | Observable activity | None | TODO | PROPOSED |
| Surveillance source | Frames / streams / metadata | Configuration | TODO | PROPOSED |
| Human user | Query / investigation intent | Evidence-backed result | TODO | PROPOSED |
| Evaluation operator | Ground truth / benchmark request | Metrics / errors | TODO | PROPOSED |

### High-Level Architecture

`PROPOSED` conceptual flow for review:

```text
Physical Environment + Surveillance Observation
  -> Perception
  -> Tracking / Temporal
  -> Spatial Mapping
  -> Event Understanding
  -> World State / Storage
  -> Retrieval
  -> Agent / Reasoning
  -> Application / Digital Twin UI

Evaluation observes each relevant boundary, not only the final output.
```

Questions:

- Which layers are required for the first prototype?
- Can any layer be represented by ground truth or a stub in the first benchmark?
- Where are synchronous, asynchronous, batch, or streaming boundaries required?

### Module Boundaries

| Module | Responsibility | Input | Output | Source of Truth | Must Not Own |
| --- | --- | --- | --- | --- | --- |
| Perception | TODO | Observation | Detection | TODO | Track identity unless explicitly combined |
| Tracking / Temporal | TODO | Detection sequence | Track / temporal state | TODO | Physical zone definition |
| Spatial Mapping | TODO | Observation, camera, track | Location / zone association | TODO | Event policy |
| Event Understanding | TODO | Temporal/spatial entities | Event / alert candidate | TODO | Raw evidence storage policy |
| World State / Storage | TODO | Versioned system records | Authoritative stored state | TODO | User-intent interpretation |
| Retrieval | Execute grounded access to data/evidence | Retrieval request | Records, evidence, provenance, result status | World State references | Agent reasoning |
| Agent | Interpret intent and use tools/evidence | User query, tool results | Tool calls, grounded answer | TODO | Authoritative surveillance state |
| Application / Digital Twin UI | TODO | World state / evidence / answer | User interaction | TODO | Hidden inference logic |
| Evaluation | Compare predictions and ground truth | Versions, predictions, ground truth | Metrics, error records | Benchmark definition | Production state |

All rows remain `OPEN` unless a decision record confirms them.

### Perception Layer

- What observations are accepted?
- What classes and outputs are required by the MVP?
- How are model/configuration versions attached to detections?
- What confidence and evidence must be preserved?

### Tracking / Temporal Layer

- What defines identity continuity and track lifetime?
- How are gaps, merges, splits, and ID changes represented?
- Which timestamps are authoritative?
- Is tracking required for the first prototype?

### Spatial Layer

- Is Camera-to-Zone mapping sufficient for the MVP?
- Where do coordinate systems, zones, and camera poses come from?
- How is spatial uncertainty represented?
- Which component owns spatial metadata?

### Event Layer

- What distinguishes an observation, event, and alert?
- How are event start/end, participants, location, and evidence represented?
- Which event definitions are deterministic versus model-derived?
- How are duplicate or overlapping events handled?

### World State / Storage Layer

- Which records are authoritative, derived, mutable, or append-only?
- How are entity relationships and versions stored?
- What retention, privacy, and deletion requirements apply?
- How can a stored answer be traced to source observations and model versions?

### Retrieval Layer

- Which request types and filters are supported?
- Which data sources can retrieval access?
- How does retrieval report success, empty, ambiguous, partial, stale, or unavailable results?
- How are returned evidence and provenance represented?

The retrieval contract is owned by
[06_Retrieval_Specification.md](06_Retrieval_Specification.md).

### Agent Layer

- What user intents are supported?
- Which retrieval or application tools may the Agent call?
- How are parameters validated before tool execution?
- How must the Agent cite or expose supporting evidence?
- What must the Agent do when retrieval is empty or ambiguous?

### Digital Twin / Application Layer

- Which views and interactions are needed for the approved use cases?
- Which state is visualized versus authored in the UI?
- How are time, zone, camera, event, and evidence linked?
- What accessibility and audit needs apply?

### Evaluation Layer

- At which interfaces are predictions and ground truth captured?
- How are evaluator, dataset, model, and configuration versions linked?
- How are component failures distinguished from upstream failures?
- Which regressions prevent release or further expansion?

### Data Flow

| Flow ID | Producer | Payload | Consumer | Ordering / timing | Provenance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Agent-query trace to preserve:

```text
User Query -> Agent Intent -> Retrieval Request -> Retrieved Evidence
-> Agent Answer -> Evaluation
```

### Core Entities

| Entity | Working responsibility | Key relationships to review | MVP? | Status |
| --- | --- | --- | --- | --- |
| Camera | Observation source and spatial reference | Observation, Zone, Evidence | TODO | OPEN |
| Observation | Source media/sample at a time | Camera, Detection, Evidence | TODO | OPEN |
| Detection | Per-frame perceived entity candidate | Observation, Track | TODO | OPEN |
| Object / Person | Domain entity concept | Detection, Track, Event | TODO | OPEN |
| Track | Temporal identity hypothesis | Detection, Event, Zone | TODO | OPEN |
| Zone / Location | Spatial semantic reference | Camera, Track, Event | TODO | OPEN |
| Event / Alert | Interpreted occurrence / notification | Track, Zone, Evidence | TODO | OPEN |
| Evidence | Traceable support for a result or answer | Source record, Event, Query | TODO | OPEN |
| Query / Retrieved Result | Information request and grounded result | Filters, Evidence, Tool Call | TODO | OPEN |
| Agent Tool Call / Answer | Reasoning action and user-facing response | Query, Retrieved Result | TODO | OPEN |

### Module Interfaces

| Interface ID | Producer | Consumer | Request / input | Response / output | Error contract | Version | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ARCH-IF-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

### Failure Boundaries

| Boundary | Example failure | Owning layer | Upstream evidence needed | User-visible behavior | Status |
| --- | --- | --- | --- | --- | --- |
| Agent -> Retrieval | Incorrect filters in an otherwise executable request | Agent / tool planning | Parsed intent and request | TODO | OPEN |
| Retrieval -> Storage | Correct request returns wrong records | Retrieval | Query trace and source snapshot | TODO | OPEN |
| Retrieval -> Agent | Correct evidence is ignored or contradicted | Agent grounding / reasoning | Returned evidence and answer | TODO | OPEN |
| Component -> Evaluation | Version or ground truth cannot be resolved | Evaluation / provenance | Version manifests | TODO | OPEN |

### Observability

| Signal | Question answered | Producer | Retention | Sensitive? | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Replaceability / Modularity

- Which interfaces must allow baseline and candidate implementations to be swapped?
- What fixture or benchmark proves compatibility?
- Which state must remain implementation-independent?
- What coupling is acceptable for the MVP?

### Open Architecture Decisions

- MVP layer boundary and deployment shape.
- Authoritative World State representation.
- Event and evidence lifecycle.
- Offline, streaming, and real-time boundaries.
- Retrieval request/response contract.
- Agent tool and safety boundary.

Track cross-cutting decisions in [open_questions.md](open_questions.md) and
[07_Technical_Decisions.md](07_Technical_Decisions.md).

### Expected Artifacts

- Approved context and layer diagram.
- Responsibility and source-of-truth matrix.
- Versioned interface contracts and error behavior.
- Entity relationship model limited to MVP needs.
- Failure-attribution and observability plan.

### Document Acceptance Checklist

- [ ] Every MVP responsibility has exactly one clear owner.
- [ ] Retrieval is distinct from Agent reasoning and World State ownership.
- [ ] Evaluation can inspect relevant component boundaries.
- [ ] Information and evidence provenance survive each required flow.
- [ ] Architecture style and technology remain open unless explicitly decided.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的與架構原則

本文件回答系統責任、邊界、資料依據與資訊流；不決定單體／微服務，也不
指定技術棧。候選原則包括分層評估、保留證據來源、模組可替換，以及結構化
資料優先採可重現的結構化檢索，狀態均為 `PROPOSED`。

外部參與者可能包括實體場域、監控來源、使用者與評估操作人員；它們交換的
資料及信任邊界仍待確認。

### 高階架構

```text
實體場域與監控觀測
  -> 感知
  -> 追蹤／時序
  -> 空間映射
  -> 事件理解
  -> 世界狀態／儲存
  -> 資料檢索
  -> Agent／推理
  -> 應用程式／數位孿生介面

評估應觀察每個必要邊界，而不只看最後輸出。
```

哪些層屬於第一版原型、哪些可由真值或 stub 代替，以及何處需要同步、
非同步、批次或串流，全部維持 `OPEN`。

### 模組責任

| 模組 | 工作責任 | 不應自行擁有 |
| --- | --- | --- |
| 感知 | 從 Observation 產生 Detection | Track 身分（除非明確合併） |
| 追蹤／時序 | 從偵測序列產生 Track 與時序狀態 | 實體區域定義 |
| 空間映射 | 建立觀測、攝影機、軌跡與位置／區域關聯 | 事件政策 |
| 事件理解 | 由時空實體產生 Event／Alert 候選 | 原始證據保存政策 |
| 世界狀態／儲存 | 保存有版本的系統紀錄 | 使用者意圖解讀 |
| Retrieval | 執行有依據的資料／證據存取 | Agent 推理 |
| Agent | 解讀意圖、使用工具與證據 | 權威監控狀態 |
| 數位孿生介面 | 呈現世界狀態、證據與回答 | 隱藏式推論邏輯 |
| 評估 | 比較預測與真值，產生指標與錯誤紀錄 | 正式環境狀態 |

各列仍為 `OPEN`，除非已有決策紀錄。

### 各層待確認事項

- 感知：輸入觀測、類別、MVP 輸出、模型／設定版本與信心資訊。
- 追蹤：身分連續性、生命週期、缺口／合併／分裂與權威時間戳。
- 空間：Camera-to-Zone 是否足夠、座標來源、不確定性及中繼資料權責。
- 事件：Observation、Event、Alert 的界線，以及時間、參與者與證據。
- 世界狀態：權威／衍生／可變／附加式紀錄及保存、隱私與追溯。
- Retrieval：請求、篩選、資料來源、結果狀態、證據與 provenance。
- Agent：支援意圖、可用工具、參數驗證、證據引用及歧義處理。
- 介面：必要畫面、時間／區域／攝影機／事件同步與無障礙需求。
- 評估：要擷取的介面、版本關聯、失敗區分與回歸阻擋條件。

### 資訊流與核心實體

每條資料流需記錄生產者、內容、使用端、順序／時間、來源資訊與狀態。
Agent 查詢必須保留：

```text
使用者查詢 -> Agent 意圖 -> Retrieval 請求 -> 取回的證據
-> Agent 回答 -> 評估
```

候選核心實體包括 Camera、Observation、Detection、Object／Person、
Track、Zone／Location、Event／Alert、Evidence、Query／Retrieved Result，
以及 Agent Tool Call／Answer。是否進入 MVP 仍為 `OPEN`。

### 介面、失敗與可觀測性

模組介面需明列生產者、使用端、輸入、輸出、錯誤契約與版本。系統必須能
區分 Agent 給錯篩選條件、Retrieval 回錯紀錄、Agent 忽略正確證據，以及
評估找不到版本或真值等不同失敗。

可觀測訊號需回答明確問題，並記錄生產者、保存期限與敏感性。可替換性則應
由介面契約與 fixture／benchmark 證明，而不是預設所有模組都需獨立服務。

### 未決架構決策與驗收

MVP 層級、部署形式、權威世界狀態、事件與證據生命週期、離線／串流／即時
邊界、Retrieval 契約及 Agent 工具安全邊界仍待確認。

- [ ] 每項 MVP 責任只有一個清楚的主責。
- [ ] Retrieval 與 Agent 推理、世界狀態權責分開。
- [ ] 評估能觀察必要的元件邊界。
- [ ] 資訊與證據來源能通過每條必要資料流。
- [ ] 架構形式與技術在明確決定前維持開放。
