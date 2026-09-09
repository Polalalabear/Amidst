# Evaluation Framework Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **What does correctness mean, how can it be measured, and where did a
failure originate?** Metrics listed here are candidates until approved against
a defined benchmark.

### Evaluation Philosophy

`PROPOSED` cycle:

```text
Build Small -> Evaluate -> Diagnose -> Improve -> Expand -> Evaluate Again
```

The first useful prototype foundation is proposed to include a dataset, ground
truth, baseline system, evaluation engine, metrics, and error analysis. Ground
truth alone is not a complete prototype.

### Evaluation Scope

| Capability | In MVP evaluation? | Reason | Owner | Status |
| --- | --- | --- | --- | --- |
| Perception | TODO | TODO | TODO | OPEN |
| Tracking | TODO | TODO | TODO | OPEN |
| Spatial mapping | TODO | TODO | TODO | OPEN |
| Event understanding | TODO | TODO | TODO | OPEN |
| Retrieval | TODO | TODO | TODO | OPEN |
| Agent | TODO | TODO | TODO | OPEN |
| End-to-end | TODO | TODO | TODO | OPEN |

### Evaluation Layers

| Layer | Ground Truth | Prediction | Metric | Failure Type | Status |
| --- | --- | --- | --- | --- | --- |
| Perception | Class, bounding box | Detection | Precision, Recall, F1, mAP candidates | Misclassification, localization, miss | PROPOSED |
| Tracking | Identity across frames | Track sequence | IDF1, ID switches, fragmentation, HOTA/MOTA candidates | Identity or continuity error | PROPOSED |
| Spatial | Camera, zone, location | Spatial association | TODO | Wrong/unknown spatial mapping | OPEN |
| Event | Type, start/end, entities, location | Event | Precision, Recall, F1, false alarm, miss, latency candidates | Event classification/timing/association | PROPOSED |
| Retrieval | Request, filters, source, expected records/evidence | Retrieved result | Mechanism-specific correctness | Filter/source/result/provenance error | PROPOSED |
| Agent | Intent, parameters, tool, evidence-supported answer | Tool call and answer | TODO | Intent/tool/grounding/answer error | OPEN |
| End-to-end | Approved scenario outcome | User-visible result | TODO | Cross-layer failure | OPEN |

### Ground Truth Definition

| GT ID | Entity / behavior | Annotation unit | Required fields | Source | Quality check | Status |
| --- | --- | --- | --- | --- | --- | --- |
| EV-GT-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Questions:

- Who creates, reviews, and approves each ground-truth layer?
- How are ambiguity, uncertainty, disagreement, and unknown values represented?
- Which version of ground truth is authoritative for a benchmark run?

### Prediction Definition

| Prediction type | Required fields | Confidence | Version metadata | Matching rule | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Perception Evaluation

- Which classes and bounding-box conventions are in scope?
- What matching thresholds and averaging conventions apply?
- How will performance be sliced by lighting, occlusion, distance, viewpoint,
  and crowd density?
- Which candidate metrics are necessary for the approved use case?

### Tracking Evaluation

- What defines a ground-truth identity and a valid association?
- How are entry, exit, occlusion, and reappearance handled?
- Are IDF1, ID switches, fragmentation, HOTA, or MOTA appropriate for the benchmark?
- Which errors matter most to downstream events and retrieval?

### Spatial Evaluation

- Is the target Camera-to-Zone, Observation-to-Zone, or precise 3D location?
- What tolerance, unknown-zone behavior, and boundary convention apply?
- How are camera calibration and environment versions tied to a result?

### Event Evaluation

- How are event type, interval overlap, participants, and location matched?
- What counts as a false alarm, missed event, duplicate, or late detection?
- Which candidate metrics and latency definitions match operational needs?

### Retrieval Evaluation

Ground-truth form to review:

```text
Query / Retrieval Request -> Expected Filters -> Expected Data Source
-> Expected Records / Evidence
```

| Query ID | Mechanism | Request | Expected source | Expected result | Required evidence | Evaluation rule | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RET-EV-xxx | Structured / semantic / hybrid / TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

Evaluate where applicable:

- request/filter correctness;
- temporal and spatial constraint correctness;
- evidence completeness and relevance;
- provenance correctness;
- deterministic empty-result and ambiguity handling.

Do not use Recall@K, MRR, or similar information-retrieval metrics unless the
retrieval mechanism and benchmark justify them. Structured queries and semantic
retrieval may require different protocols.

### Agent Evaluation

| Dimension | Ground truth / rubric | Observed artifact | Failure boundary | Status |
| --- | --- | --- | --- | --- |
| Intent understanding | TODO | Parsed intent | Agent | OPEN |
| Parameter extraction | TODO | Tool arguments | Agent | OPEN |
| Tool selection | TODO | Tool call | Agent | OPEN |
| Retrieval request correctness | Expected request | Actual request | Agent / tool planning | OPEN |
| Evidence usage / grounding | Approved evidence-to-claim rubric | Answer and citations | Agent reasoning | OPEN |
| Hallucination / answer correctness | TODO | Final answer | Agent reasoning | OPEN |

### End-to-End Evaluation

Flows to test only after their component contracts are defined:

```text
User Query -> Agent -> Retrieval -> World State -> Evidence -> Answer

Physical Event -> Perception -> Tracking -> Spatial -> Event -> Storage
-> Retrieval -> Agent -> User
```

End-to-end results must link to component-level diagnostics; they must not
replace them.

### Scenario-Based Evaluation

| Scenario ID | Capability | Conditions | Expected outcome | Required ground truth | Required slices | Status |
| --- | --- | --- | --- | --- | --- | --- |
| EV-SC-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Potential conditions for review: lighting, occlusion, distance, viewpoint,
crowd density, camera outage, stale data, ambiguous query, and empty result.

### Error Taxonomy

| Error ID | Layer | Definition | Required evidence | Upstream cause possible? | Status |
| --- | --- | --- | --- | --- | --- |
| ERR-PER-xxx | Perception | TODO | Observation, ground truth, detection, versions | TODO | OPEN |
| ERR-TRK-xxx | Tracking | TODO | Detection sequence, track truth/prediction | TODO | OPEN |
| ERR-SP-xxx | Spatial | TODO | Camera/zone metadata and association | TODO | OPEN |
| ERR-EVT-xxx | Event | TODO | Inputs, event truth/prediction | TODO | OPEN |
| ERR-RET-xxx | Retrieval | TODO | Request, source snapshot, result, provenance | TODO | OPEN |
| ERR-AGT-xxx | Agent | TODO | Intent, tool call, evidence, answer | TODO | OPEN |
| ERR-E2E-xxx | End-to-end | TODO | Linked component traces | Yes | OPEN |

### Failure Attribution

| Agent intent/request | Retrieval execution/result | Agent answer | Attribute first to |
| --- | --- | --- | --- |
| Correct | Incorrect | Not evaluated or affected | Retrieval Layer |
| Incorrect | Correct for received request | Not evaluated or affected | Agent / tool planning |
| Correct | Correct | Unsupported or incorrect | Agent grounding / reasoning |

Define how upstream errors are recorded without double-counting downstream
symptoms: `TODO`.

### Benchmark Protocol

| Step | Required input | Procedure | Output | Reproducibility evidence | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | TODO | TODO | TODO | TODO | OPEN |

Specify: eligibility, exclusions, preprocessing, execution order, random seeds,
matching rules, confidence thresholds, repetitions, aggregation, and approval.

### Experiment Reproducibility

| Run ID | Dataset version | Model version | Configuration version | Evaluator version | Environment | Artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO |

#### Dataset Version

- Identifier format: `TODO`
- Immutability / change policy: `TODO`

#### Model Version

- Identifier and artifact provenance: `TODO`

#### Configuration Version

- Captured parameters and secrets boundary: `TODO`

#### Evaluator Version

- Code/version compatibility and result migration: `TODO`

### Reporting Format

| Section | Required content | Audience | Status |
| --- | --- | --- | --- |
| Summary | TODO | TODO | OPEN |
| Per-layer results | TODO | TODO | OPEN |
| Scenario slices | TODO | TODO | OPEN |
| Error analysis | TODO | TODO | OPEN |
| Version manifest | TODO | TODO | OPEN |

### Regression Criteria

| Criterion | Baseline | Allowed change | Blocking? | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Open Questions

- Which layers must the first benchmark evaluate directly?
- Which metrics align with actual prototype decisions?
- What sample or event is the evaluation unit?
- How will ambiguous ground truth be adjudicated?
- Which regressions block expansion or release?

### Expected Artifacts

- Approved ground-truth and prediction contracts.
- Versioned benchmark protocol and test fixtures.
- Per-layer metrics with justified thresholds.
- Error taxonomy and attribution rules.
- Reproducible report format and regression policy.

### Document Acceptance Checklist

- [ ] Every evaluated capability has corresponding ground truth or an approved rubric.
- [ ] Retrieval evaluation is explicit and mechanism-appropriate.
- [ ] Agent failures are distinguishable from Retrieval failures.
- [ ] Scenario slices are derived from approved risks and use cases.
- [ ] Dataset, model, configuration, and evaluator versions are captured.
- [ ] Candidate metrics are not represented as finalized decisions.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的與理念

回答：「什麼叫正確、如何衡量，以及失敗發生在哪一層？」所有指標在對照
明確 benchmark 核准前都只是候選。

```text
小規模建置 -> 評估 -> 診斷 -> 改進 -> 擴大 -> 再次評估
```

第一個有用原型的候選基礎包括資料集、真值、基準系統、評估引擎、指標與
錯誤分析；只有 Ground Truth 並不構成完整原型。

### 評估範圍與層級

感知、追蹤、空間映射、事件理解、Retrieval、Agent 與端到端是否屬於 MVP
評估，目前都為 `OPEN`。

| 層 | 真值與預測 | 候選衡量／錯誤 |
| --- | --- | --- |
| 感知 | 類別／框與 Detection | Precision、Recall、F1、mAP；分類、定位、漏檢 |
| 追蹤 | 跨影格身分與 Track 序列 | IDF1、ID switch、fragmentation、HOTA／MOTA |
| 空間 | Camera／Zone／Location 與空間關聯 | 錯誤或未知映射；指標 OPEN |
| 事件 | 類型、起訖、實體、位置與 Event | Precision、Recall、F1、誤報、漏報、延遲 |
| Retrieval | 請求、篩選、來源、預期紀錄／證據 | 依機制定義的正確性與來源錯誤 |
| Agent | 意圖、參數、工具、證據支持回答 | 意圖／工具／grounding／回答錯誤 |
| 端到端 | 核准情境結果與使用者可見結果 | 跨層錯誤；指標 OPEN |

### 真值、預測與各層評估

每個 Ground Truth 層都要定義實體／行為、標註單位、必要欄位、來源、
品質檢查與版本權威，並說明歧義、不確定、意見分歧及未知值如何表示。

預測契約需包含必要欄位、confidence、版本資訊與比對規則。

- 感知：確認類別、框座標、比對門檻與光線／遮擋／距離／視角切片。
- 追蹤：定義身分、進出、遮擋、再次出現，以及對下游影響最大的錯誤。
- 空間：確認目標粒度、容差、未知區域、邊界與相機／環境版本。
- 事件：定義類型、區間重疊、參與者、位置、誤報、漏報、重複與延遲。

### Retrieval 與 Agent 評估

```text
查詢／Retrieval 請求 -> 預期篩選 -> 預期資料來源
-> 預期紀錄／證據
```

Retrieval 應依實際機制評估請求與篩選、時空限制、證據完整性／相關性、
來源正確性，以及空結果與歧義處理。結構化查詢與語意檢索可能需要不同
流程；沒有依據時不得直接套用 Recall@K 或 MRR。

Agent 評估需分開觀察意圖理解、參數抽取、工具選擇、Retrieval 請求、
證據使用／grounding，以及幻覺與回答正確性。

### 端到端、情境與錯誤歸因

只有元件契約完成後才測試：

```text
使用者查詢 -> Agent -> Retrieval -> 世界狀態 -> 證據 -> 回答

實體事件 -> 感知 -> 追蹤 -> 空間 -> 事件 -> 儲存
-> Retrieval -> Agent -> 使用者
```

端到端結果必須連回元件診斷。情境切片可包含光線、遮擋、距離、視角、
人群密度、相機中斷、資料過期、歧義查詢與空結果，但只有與核准風險及
情境相關者才納入。

錯誤分類需涵蓋感知、追蹤、空間、事件、Retrieval、Agent 與端到端，並
保留判斷所需證據。若 Agent 請求正確而 Retrieval 結果錯誤，先歸於
Retrieval；若 Agent 請求錯誤但 Retrieval 正確執行收到的請求，先歸於
Agent／工具規劃；若證據正確而回答無依據，歸於 Agent grounding／推理。

### Benchmark 與可重現性

基準流程需明列資格、排除項目、前處理、執行順序、隨機種子、比對規則、
confidence 門檻、重複次數、彙整方式及核准。每次實驗至少保留資料集、
模型、設定、評估器與環境版本及其產物。

報告應包含摘要、各層結果、情境切片、錯誤分析與版本 manifest。回歸條件
則需記錄基準、允許變化、是否阻擋及負責人。

### 未決問題與驗收

- 哪些層必須由第一個 benchmark 直接評估？
- 哪些指標符合實際原型決策？
- 評估單位是樣本、事件或其他單位？
- 如何裁決有歧義的真值？
- 哪些回歸會阻擋擴大或發布？

- [ ] 每項能力都有真值或核准的評分規則。
- [ ] Retrieval 評估清楚且符合所採機制。
- [ ] Agent 與 Retrieval 失敗可以區分。
- [ ] 情境切片源自核准風險與使用情境。
- [ ] 保存資料集、模型、設定與評估器版本。
- [ ] 候選指標沒有被寫成已定案。
