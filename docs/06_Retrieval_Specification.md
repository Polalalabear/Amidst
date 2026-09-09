# Retrieval Specification Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **How does the system retrieve trustworthy data and evidence from World
State for applications and the AI Agent?** Retrieval is not synonymous with
RAG or vector search.

### Retrieval Goals

Questions:

1. What information needs cannot be answered directly by the consumer?
2. Who consumes retrieval and what guarantee does each consumer need?
3. What must be deterministic, reproducible, auditable, and timely?
4. What evidence and provenance must accompany results?

| Goal ID | Consumer need | Guarantee | Verification | Status |
| --- | --- | --- | --- | --- |
| RET-xxx | TODO | TODO | TODO | OPEN |

### Retrieval Scope

| Consumer | Use | Required request types | Required result contract | MVP? | Status |
| --- | --- | --- | --- | --- | --- |
| Agent | Ground tool use and answers | TODO | TODO | TODO | OPEN |
| Digital Twin / UI | Investigation and navigation | TODO | TODO | TODO | OPEN |
| Evaluation | Fetch fixtures, truth, predictions, traces | TODO | TODO | TODO | OPEN |
| Event investigation | Reconstruct event and evidence | TODO | TODO | TODO | OPEN |

Potential consumers are not automatically MVP requirements.

### Source of Truth

| Information | Authoritative owner/store | Read model / index | Freshness | Version / snapshot | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

Retrieval executes access; it does not become the authoritative owner merely by
returning a result.

### Retrievable Entities

| Entity | Source | Queryable Fields | Temporal | Spatial | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Camera | TODO | TODO | TODO | TODO | TODO | OPEN |
| Zone | TODO | TODO | TODO | TODO | TODO | OPEN |
| Detection | TODO | TODO | TODO | TODO | TODO | OPEN |
| Track | TODO | TODO | TODO | TODO | TODO | OPEN |
| Event | TODO | TODO | TODO | TODO | TODO | OPEN |
| Alert | TODO | TODO | TODO | TODO | TODO | OPEN |
| Evidence | TODO | TODO | TODO | TODO | TODO | OPEN |

Confirm which entities exist in the MVP before defining schemas.

### Information Needs

Candidate questions for scenario design:

- What events occurred in a selected zone?
- What happened within a time range?
- Which cameras observed a selected event?
- What evidence supports an alert?
- Which tracks were associated with an event?
- What happened before or after an event?

For each approved question, record the consumer, authoritative source, required
filters, evidence, empty-result behavior, and evaluation case.

### Query Types

| Type | Example need | Required filters | Expected source | Deterministic? | MVP? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Temporal | Records between X and Y | Start/end, timezone, boundary rule | TODO | TODO | TODO | OPEN |
| Spatial | Records associated with Zone A | Zone/camera/location relation | TODO | TODO | TODO | OPEN |
| Event | Events of a selected type | Type, status, interval | TODO | TODO | TODO | OPEN |
| Entity | History or relations for an entity | Entity type/ID | TODO | TODO | TODO | OPEN |
| Evidence | Evidence supporting a result | Source/result IDs | TODO | TODO | TODO | OPEN |
| Combined | Time + zone + event + entity | Composed filters | TODO | TODO | TODO | OPEN |
| Semantic | Unstructured meaning-based need | Query text, corpus, filter | TODO | No | TODO | OPEN |

### Retrieval Request Schema

Define a schema only after approved query types are known.

| Candidate field | Meaning question | Required for which type? | Validation / ambiguity rule | Status |
| --- | --- | --- | --- | --- |
| `intent` / `type` | Which operation is requested? | TODO | TODO | PROPOSED |
| `time_range` | Inclusive/exclusive boundaries and timezone? | TODO | TODO | PROPOSED |
| `zone` | ID, label, or spatial relation? | TODO | TODO | PROPOSED |
| `camera` | Stable camera ID or source stream? | TODO | TODO | PROPOSED |
| `entity` | Entity type, ID, or unresolved reference? | TODO | TODO | PROPOSED |
| `event_type` | Controlled vocabulary and version? | TODO | TODO | PROPOSED |
| `filters` | Allowed operators and composition? | TODO | TODO | PROPOSED |
| `limit` | Safety, pagination, ordering? | TODO | TODO | PROPOSED |

Unresolved request questions:

- How is schema version represented?
- How are natural-language references resolved before execution?
- Which invalid, underspecified, or conflicting filters are rejected?
- How are authorization and data-scope constraints applied?

### Retrieval Response Schema

| Candidate field | Purpose | Required? | Provenance rule | Status |
| --- | --- | --- | --- | --- |
| Result records | Requested structured data | TODO | Link to source IDs/version | PROPOSED |
| Evidence | Support for records/claims | TODO | Link to originating observation/media | PROPOSED |
| Source / provenance | Explain origin and transformations | TODO | Must remain traceable | PROPOSED |
| Timestamp / snapshot | Reproduce time and state | TODO | TODO | PROPOSED |
| Confidence | Only where meaningful | TODO | Identify producer and calibration | PROPOSED |
| Result status | Success/empty/ambiguous/partial/stale/unavailable | TODO | TODO | PROPOSED |
| Pagination / truncation | Make incomplete result sets explicit | TODO | TODO | PROPOSED |

### Filter Representation

| Filter | Type / operators | Boundary semantics | Validation | Example test | Status |
| --- | --- | --- | --- | --- | --- |
| Time | TODO | Inclusive/exclusive, timezone | TODO | TODO | OPEN |
| Zone / location | TODO | Containment/overlap/association | TODO | TODO | OPEN |
| Camera | TODO | ID/alias/source | TODO | TODO | OPEN |
| Event / entity | TODO | Vocabulary/version/relations | TODO | TODO | OPEN |

### Structured Retrieval

Questions:

- Which surveillance state belongs in structured storage?
- Which filters and joins must be deterministic and reproducible?
- How are time, zone, camera, event, and track relationships indexed?
- How are schema and source snapshots versioned?

`PROPOSED`: Prefer structured querying for structured surveillance state such as
camera, zone, timestamp, event, and track unless evidence justifies otherwise.

### Temporal Retrieval

- Which clock/timezone is authoritative?
- Are intervals closed, open, or half-open?
- How are clock drift, missing timestamps, and before/after relationships handled?
- What ordering is guaranteed?

### Spatial Retrieval

- Does a spatial filter mean camera location, camera coverage, observation zone,
  entity zone, or event location?
- How are boundary, unknown, and multi-zone results represented?
- Which spatial model version applies?

### Event and Evidence Retrieval

- How are event definitions and versions selected?
- Can evidence be media, metadata, derived records, or all three?
- How is a chain from result to event, track, detection, observation, camera, and
  timestamp preserved where applicable?
- What redaction or access controls apply to evidence?

### Semantic Retrieval

Questions to answer before introducing vector search:

- What unstructured information exists?
- Which approved query cannot be solved cleanly with structured filters?
- What corpus, chunk, embedding, relevance, freshness, and authorization rules apply?
- Which benchmark justifies the added mechanism?

Semantic retrieval and RAG status: `OPEN`; not assumed for MVP.

### Hybrid Retrieval

Status: `PROPOSED` future design option.

- What sequence or fusion combines deterministic filters and semantic ranking?
- Which stage owns filtering, ranking, evidence assembly, and provenance?
- How is each stage evaluated independently?

### Evidence and Provenance

| Provenance element | Question | Verification | Status |
| --- | --- | --- | --- |
| Source record | Which authoritative ID and version produced this result? | TODO | OPEN |
| Originating camera | Which camera/source captured it? | TODO | OPEN |
| Timestamp | Which clock and precision apply? | TODO | OPEN |
| Event / related entities | Which relationships support the result? | TODO | OPEN |
| Media reference | Where is authorized evidence located and versioned? | TODO | OPEN |
| Observed vs model-generated | How is derivation identified? | TODO | OPEN |
| Confidence | Who produced it and what does it mean? | TODO | OPEN |
| Transformation trace | What filtering/aggregation occurred? | TODO | OPEN |

### Result State and Consumer Behavior

| State | Definition | Retry / clarification | Agent behavior | UI behavior | Status |
| --- | --- | --- | --- | --- | --- |
| Success | TODO | TODO | TODO | TODO | OPEN |
| Empty | No matching result under executed constraints | TODO | Must not invent evidence | TODO | PROPOSED |
| Ambiguous | Multiple interpretations require resolution | TODO | Ask/resolve before unsupported claim | TODO | PROPOSED |
| Partial | Some sources/results unavailable or truncated | TODO | Disclose limitations | TODO | PROPOSED |
| Stale | Freshness requirement not met | TODO | Disclose / retry per policy | TODO | PROPOSED |
| Unavailable | Required source cannot be queried | TODO | Report inability | TODO | PROPOSED |

### Retrieval Failure Modes

| Failure ID | Mode | Detection evidence | Expected handling | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| RET-FAIL-001 | No result | Request + source snapshot | Distinguish valid empty from failure | TODO | PROPOSED |
| RET-FAIL-002 | Wrong filter | Expected vs actual request/execution | Attribute to Agent or Retrieval | TODO | PROPOSED |
| RET-FAIL-003 | Stale data | Freshness/version evidence | Mark stale; follow retry policy | TODO | PROPOSED |
| RET-FAIL-004 | Incomplete evidence | Expected evidence set | Mark partial; do not overclaim | TODO | PROPOSED |
| RET-FAIL-005 | Ambiguous query | Multiple valid interpretations | Request clarification or return ambiguity | TODO | PROPOSED |
| RET-FAIL-006 | Wrong time window / zone | Expected vs executed constraints | Reject or flag mismatch | TODO | PROPOSED |
| RET-FAIL-007 | Unavailable source | Source health/error trace | Return unavailable/partial state | TODO | PROPOSED |
| RET-FAIL-008 | Inconsistent records | Cross-source/version conflict | Preserve conflict and provenance | TODO | PROPOSED |

### Retrieval Evaluation

| Query ID | Request | Expected Source | Expected Result | Actual Result | Correct | Failure Type |
| --- | --- | --- | --- | --- | --- | --- |
| RET-EV-xxx | TODO | TODO | TODO | TODO | TODO | TODO |

Questions:

- How is exact or set-based structured correctness measured?
- If semantic retrieval is approved, what relevance judgments and ranking metrics apply?
- How are temporal/spatial filters and provenance verified independently?
- How are correct empty, ambiguous, partial, and unavailable states tested?
- How is evidence completeness defined for each query type?

### Agent Boundary

`PROPOSED` responsibility boundary for human confirmation:

```text
Agent: decides what information is needed and constructs/chooses a tool request.
Retrieval Layer: validates and executes grounded access to data/evidence.
World State / Storage: owns authoritative stored state.
```

Attribution examples:

- Correct Agent request + incorrect result -> Retrieval Layer failure.
- Incorrect request + correct execution -> Agent/tool-planning failure.
- Correct retrieval + unsupported answer -> Agent grounding/reasoning failure.

### Security, Privacy, and Authorization

- Which consumer can retrieve which entity, field, time range, and evidence type?
- Where is authorization enforced and audited?
- How are redaction, retention, deletion, and purpose limitations applied?
- How do evaluation fixtures avoid exposing sensitive data?

### Open Questions

- Which information and query types are required by the MVP?
- Where is each retrievable entity's source of truth?
- What request/response and error contracts should be confirmed first?
- When, if ever, is semantic retrieval necessary?
- What provenance is sufficient for an Agent answer to be grounded?

### Expected Artifacts

- Approved information-needs and retrievable-entity matrix.
- Versioned request, response, filter, and result-state schemas.
- Source-of-truth and authorization map.
- Evidence/provenance contract.
- Mechanism-specific benchmark and failure-attribution cases.

### Document Acceptance Checklist

- [ ] Retrieval is not conflated with RAG, Agent reasoning, or storage ownership.
- [ ] Structured, temporal, spatial, event, evidence, semantic, and hybrid options are distinguished.
- [ ] Empty, ambiguous, partial, stale, and unavailable results are explicit.
- [ ] Results preserve enough provenance for verification.
- [ ] Retrieval evaluation can distinguish request, execution, and grounding failures.
- [ ] Unneeded entities and mechanisms remain `OPEN` or out of MVP scope.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的與範圍

回答：「系統如何從世界狷取得可信資料與證據，供應用程式及 AI Agent
使用？」Retrieval 不等於 RAG 或向量搜尋。

每項目標需說明資訊需求、使用端、保證與驗證方法。候選使用端包括 Agent、
數位孿生介面、評估與事件調查；它們不會自動成為 MVP 需求。

### 資料依據與可檢索實體

Retrieval 只負責執行存取，不會因為回傳資料就成為權威來源。每類資訊都要
記錄權威 owner／store、read model／index、新鮮度及版本／snapshot。

Camera、Zone、Detection、Track、Event、Alert 與 Evidence 都只是可檢索
候選；應先確認 MVP 實體，再定義 schema。

### 資訊需求與查詢型別

候選問題包括：指定區域有哪些事件、某時段發生什麼、哪些攝影機看見事件、
警示由哪些證據支持、哪些軌跡與事件有關，以及事件前後發生什麼。

| 查詢型別 | 必須釐清 |
| --- | --- |
| 時間 | 起訖、時區、邊界與資料來源 |
| 空間 | Zone／Camera／Location 關係 |
| 事件 | 類型、狀態與區間 |
| 實體 | 實體型別、ID 與關係 |
| 證據 | 支持結果的來源與紀錄 |
| 組合 | 時間、區域、事件與實體的組合篩選 |
| 語意 | 查詢文字、語料、篩選與非確定性 |

每個核准問題都要記錄使用端、權威來源、必要篩選、證據、空結果行為與
評估案例。

### 請求、回應與篩選契約

只有核准查詢型別後才定義正式 request schema。候選欄位包括 `intent/type`、
`time_range`、`zone`、`camera`、`entity`、`event_type`、
`filters` 與 `limit`；版本、自然語言指涉、衝突篩選與授權仍待決。

候選 response 應包含結果紀錄、Evidence、來源／provenance、時間／snapshot、
有意義時的 confidence、明確 result status，以及 pagination／truncation。
每個 filter 都要定義型別、運算子、邊界語意、驗證與測試案例。

### 各種檢索機制

`PROPOSED`：Camera、Zone、timestamp、Event、Track 等結構化監控狀態，優先
使用可重現的結構化查詢。時間檢索需明確時鐘、時區、區間開閉、漂移與排序；
空間檢索需區分攝影機位置、涵蓋範圍、觀測／實體／事件所在區域。

事件與證據檢索要保留 result -> event -> track -> detection -> observation ->
camera／timestamp 的關係及必要的遮蔽與存取控制。

導入向量搜尋前，必須證明存在無法由結構化篩選妥善回答的非結構化需求，
並定義語料、切塊、embedding、相關性、新鮮度、授權與 benchmark。語意
檢索／RAG 目前為 `OPEN`；hybrid retrieval 僅是未來 `PROPOSED` 選項。

### 證據、來源與結果狀態

Provenance 至少要評估來源紀錄、攝影機、時間戳、事件／關聯實體、媒體參考、
觀測或模型生成的區別、confidence 生產者，以及篩選／彙整轉換。

| 狀態 | 必須表達的意思 |
| --- | --- |
| Success | 符合契約並完成查詢 |
| Empty | 在已執行條件下沒有符合紀錄，不能捏造證據 |
| Ambiguous | 有多種合理解讀，需要釐清 |
| Partial | 部分來源不可用或結果遭截斷 |
| Stale | 未達新鮮度要求 |
| Unavailable | 必要來源無法查詢 |

使用端不得把這些狀態全部當成空陣列或成功。

### 失敗、安全與評估

必須區分無結果、篩選錯誤、資料過期、證據不完整、查詢歧義、時間／區域
錯誤、來源不可用、紀錄不一致、語意排名錯誤及授權拒絕。

- Agent 請求正確但結果錯誤：Retrieval Layer failure。
- 請求錯誤但 Retrieval 正確執行：Agent／tool-planning failure。
- Retrieval 正確但回答無依據：Agent grounding／reasoning failure。

授權需限制每個使用端可取用的實體、欄位、時間範圍與證據型別，並說明
稽核、遮蔽、保存、刪除及目的限制。評估 fixture 不得暴露敏感資料。

### 未決問題與驗收

- MVP 需要哪些資訊與查詢型別？
- 每種實體的權威來源在哪裡？
- 應先確認哪些 request／response／error 契約？
- 何時才真的需要語意檢索？
- Agent 回答需要多少 provenance 才算有依據？

- [ ] Retrieval 不與 RAG、Agent 推理或儲存權責混為一談。
- [ ] 結構化、時間、空間、事件、證據、語意與混合選項有清楚區分。
- [ ] Empty、Ambiguous、Partial、Stale、Unavailable 明確可見。
- [ ] 結果保留足以驗證的來源資訊。
- [ ] 評估能區分請求、執行與 grounding 失敗。
- [ ] 不需要的實體與機制維持 `OPEN` 或排除於 MVP。
