# Dataset Specification Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **What data and ground truth must exist for the approved evaluation
framework to work?** Do not invent dataset size, scenario counts, or split
ratios.

`PROPOSED` planning sequence:

```text
Evaluation Requirement -> Scenario -> Required Ground Truth
-> Data Collection -> Annotation -> Benchmark
```

### Dataset Purpose

- Which requirement and evaluation question does this dataset support?
- Is it for development, benchmarking, demonstration, or regression testing?
- What decisions must its results enable?

Purpose statement: `TODO` (`OPEN`)

### Dataset Scope

| Layer / capability | Included? | Why | Required ground truth | Status |
| --- | --- | --- | --- | --- |
| Object / perception | TODO | TODO | Class, bounding box, TODO | OPEN |
| Tracking | TODO | TODO | Identity across frames, TODO | OPEN |
| Spatial | TODO | TODO | Camera, zone, location, TODO | OPEN |
| Event | TODO | TODO | Type, interval, entities, location, TODO | OPEN |
| Retrieval | TODO | TODO | Request, filters, source, records/evidence | OPEN |
| Agent | TODO | TODO | Intent, parameters, tool/evidence/answer rubric | OPEN |

### Data Sources

| Source ID | Description | Owner | Rights / consent | Sensitivity | Format | Availability | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-SRC-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

### Scenario Definition

Define what makes two scenarios meaningfully different for evaluation: `TODO`.

| Scenario ID | Description | Lighting | Occlusion | Actors | Expected Event | Required Annotation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-SC-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

### Scenario Matrix

| Factor | Values to evaluate | Why | Coverage rule | Status |
| --- | --- | --- | --- | --- |
| Lighting | TODO | TODO | TODO | OPEN |
| Occlusion | TODO | TODO | TODO | OPEN |
| Distance | TODO | TODO | TODO | OPEN |
| Viewpoint | TODO | TODO | TODO | OPEN |
| Crowd density | TODO | TODO | TODO | OPEN |

Add factors only when tied to an approved use case, failure risk, or metric.

### Video Metadata

| Field | Type / format | Required? | Source | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Video ID | TODO | TODO | TODO | TODO | OPEN |
| Timestamp / time base | TODO | TODO | TODO | TODO | OPEN |
| Frame rate / dimensions | TODO | TODO | TODO | TODO | OPEN |
| Camera ID | TODO | TODO | TODO | TODO | OPEN |
| Scenario ID | TODO | TODO | TODO | TODO | OPEN |

### Camera Metadata

| Field | Required? | Source | Spatial reference | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Camera ID | TODO | TODO | TODO | TODO | OPEN |
| Position / rotation | TODO | TODO | TODO | TODO | OPEN |
| FOV / intrinsics | TODO | TODO | TODO | TODO | OPEN |
| Zone coverage | TODO | TODO | TODO | TODO | OPEN |

Align approved fields with `05_Spatial_Model_Specification.md`.

### Environmental Conditions

| Condition | Representation | Annotation method | Unknown handling | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

### Object Annotation

- Class vocabulary and inclusion/exclusion rules: `TODO`.
- Bounding-box format and coordinate convention: `TODO`.
- Occluded/truncated/ambiguous object handling: `TODO`.
- Quality-control sample and reviewer process: `TODO`.

### Tracking Annotation

- Identity scope across frames, cameras, and interruptions: `TODO`.
- Entry/exit, occlusion, merge/split, and re-identification rules: `TODO`.
- Relationship to object/person semantics: `TODO`.

### Spatial Annotation

- Required granularity: Camera / Zone / coordinates / TODO (`OPEN`).
- Boundary and unknown-location rules: `TODO`.
- Spatial model version reference: `TODO`.

### Event Annotation

| Field | Definition needed | Ambiguity rule | Status |
| --- | --- | --- | --- |
| Event type | TODO | TODO | OPEN |
| Start / end | TODO | TODO | OPEN |
| Involved entities | TODO | TODO | OPEN |
| Location | TODO | TODO | OPEN |
| Supporting evidence | TODO | TODO | OPEN |

### Retrieval Query Ground Truth

| Query ID | Natural-language need | Expected request type | Expected filters | Expected source | Expected records / evidence | Empty / ambiguity expectation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RET-Q-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

Questions:

- Are expected records exact, set-based, ordered, or relevance-graded?
- Which source snapshot/version makes the expected result reproducible?
- How are temporal and spatial boundary cases represented?
- What constitutes correct provenance and evidence completeness?

### Agent Query Ground Truth

| Query ID | Expected intent | Expected parameters | Allowed tool(s) | Required evidence | Answer rubric | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AGENT-Q-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Keep the expected Agent request separate from expected Retrieval execution so
failures can be attributed correctly.

### Dataset Splits

| Split | Purpose | Grouping / leakage boundary | Selection rule | Size | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO; do not invent | OPEN |

### Benchmark Set

| Benchmark ID | Dataset version | Included scenarios | Ground-truth layers | Evaluation version | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Versioning

- Dataset identifier format: `TODO`.
- Change log and immutability rules: `TODO`.
- Annotation schema compatibility: `TODO`.
- Benchmark freeze and supersession process: `TODO`.

### Annotation Quality Control

| Check | Sampling / coverage | Acceptance rule | Reviewer | Escalation | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Privacy / Sensitive Data

- What personal or site-sensitive information may be present?
- What consent, legal, minimization, access, retention, and deletion rules apply?
- What transformations are required before a sample can be public?
- Who approves a release?

### Data Storage Boundary

The authoritative classification rules are in
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md).
Do not duplicate or weaken them here.

| Dataset artifact | Initial classification | Reason / evidence | Reviewer | Final classification | Status |
| --- | --- | --- | --- | --- | --- |
| Raw surveillance media | PRIVATE_ONLY | Real surveillance/site content | Not publishable | PRIVATE_ONLY | CONFIRMED |
| Full real Ground Truth dataset | PRIVATE_ONLY by default | People, tracks, times, cameras, locations, or events may be sensitive | TODO if an exception is proposed | TODO | CONFIRMED policy; artifact review OPEN |
| Dataset/annotation schemas | PUBLIC_ALLOWED when they contain structure only | Must contain no real records or secrets | TODO | TODO | CONFIRMED policy; artifact review OPEN |
| Synthetic or sanitized sample | REVIEW_REQUIRED until reviewed | Sanitization, rights, and publication intent must be verified | TODO | TODO | OPEN |
| Aggregate evaluation summary | REVIEW_REQUIRED until reviewed | Must exclude sensitive raw evidence | TODO | TODO | OPEN |

Secrets, private storage URLs, and identifiable or sensitive records must not be
committed.

### Public Sample Data

| Sample | Purpose | Sanitization | License / consent | Reviewer | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

Every candidate sample must record whether it is synthetic, anonymized, or
sanitized and must pass the publication checklist in the authoritative policy.

### Private Dataset

| Collection | Access group | Storage location class | Retention | Audit | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | Do not place private URL here | TODO | TODO | OPEN |

### Coverage Criteria

| Requirement / risk | Required scenario coverage | Evidence | Gap | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

### Open Questions

- Which annotation layers belong to the MVP benchmark?
- What data already exists and can legally be used?
- What grouping prevents train/validation/test leakage?
- What is the smallest dataset that can answer the first evaluation question?
- Which samples can be safely published?

### Expected Artifacts

- Approved data-source inventory and access boundary.
- Scenario and coverage matrices tied to evaluation needs.
- Versioned annotation schemas and guidelines.
- Retrieval and Agent query ground truth separated by layer.
- Benchmark manifest and annotation quality report.

### Document Acceptance Checklist

- [ ] Every included annotation layer supports an approved evaluation need.
- [ ] No dataset size, scenario count, or split ratio was invented.
- [ ] Retrieval and Agent ground truth are represented explicitly.
- [ ] Sensitive data and public samples have distinct controls.
- [ ] Dataset versions can be linked to reproducible evaluation runs.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的與規劃順序

回答：「核准的評估框架需要哪些資料與真值？」不得自行假設資料集大小、
情境數量或切分比例。

```text
評估需求 -> 情境 -> 必要真值 -> 資料蒐集 -> 標註 -> Benchmark
```

資料集用途必須說明它支援哪項需求與評估問題、用於開發／benchmark／展示
或回歸測試，以及結果要支持哪些決策。目前用途與各層是否納入均為
`OPEN`。

### 範圍、來源與情境

感知、追蹤、空間、事件、Retrieval 與 Agent 每一層都要記錄是否納入、
理由與必要真值。資料來源需記錄 ID、描述、負責人、權利／同意、敏感性、
格式、可用性與狀態。

情境要定義哪些差異對評估有意義，並記錄光線、遮擋、參與者、預期事件及
必要標註。光線、遮擋、距離、視角、人群密度等因素，只有連到核准使用
情境、失敗風險或指標時才加入。

### 影片、攝影機與環境中繼資料

影片至少要評估 Video ID、時間戳／time base、影格率／尺寸、Camera ID 與
Scenario ID 是否必填、來源為何及如何驗證。

攝影機需評估 Camera ID、位置／旋轉、FOV／intrinsics、區域涵蓋與空間
參考，並與[空間模型規格](05_Spatial_Model_Specification.md)對齊。環境條件
要說明表示方式、標註方式及未知值處理。

### 標註層

- Object：類別詞彙、納入／排除規則、框格式、座標慣例、遮擋與歧義處理。
- Tracking：跨影格／攝影機的身分範圍、進出、遮擋、合併／分裂與 Re-ID。
- Spatial：Camera／Zone／座標粒度、邊界、未知位置與空間模型版本。
- Event：事件類型、起訖、參與實體、位置、證據及歧義規則。
- Retrieval：自然語言需求、預期請求／篩選／來源／紀錄／證據，以及空結果
  與歧義期待。
- Agent：預期意圖、參數、允許工具、必要證據與回答評分規則。

Agent 的預期請求必須與 Retrieval 的預期執行分開，才能正確歸因失敗。

### 切分、Benchmark、版本與品質

Training、Validation／Development、Benchmark／Test 的用途及資料洩漏邊界
必須明確。切分規則與大小目前為 `OPEN`，不得捏造。

Benchmark manifest 要連結資料集版本、情境、真值層與評估器版本。版本政策
要定義識別方式、不可變性、schema 相容性，以及 benchmark 凍結與取代流程。
標註品質檢查需記錄抽樣／涵蓋範圍、驗收規則、審查者與提報方式。

### 隱私、儲存與公開樣本

需確認個人或場域敏感資訊、同意與法規、資料最小化、存取、保存、刪除及
發布核准權責。具約束力的分類規則在
[發布政策](08_Repository_and_Data_Publication_Policy.md)。

| 資產 | 初始分類 |
| --- | --- |
| 原始監控媒體 | PRIVATE_ONLY |
| 完整真實 Ground Truth | 預設 PRIVATE_ONLY |
| 只含結構的 schema | 無真實紀錄或秘密時可 PUBLIC_ALLOWED |
| 合成或去識別化樣本 | 審查前 REVIEW_REQUIRED |
| 彙整評估摘要 | 審查前 REVIEW_REQUIRED |

公開候選樣本必須記錄是合成、匿名或清理後資料，並通過發布檢查；私人資料表
不得記錄私人儲存網址。

### 未決問題、產出與驗收

- MVP benchmark 包含哪些標註層？
- 已有哪些資料且可合法使用？
- 如何分組才能避免 train／validation／test 洩漏？
- 能回答第一個評估問題的最小資料集是什麼？
- 哪些樣本可以安全公開？

預期產出包括資料來源盤點、情境／涵蓋矩陣、版本化標註 schema 與指引、
分層的 Retrieval／Agent 真值、benchmark manifest 與標註品質報告。

- [ ] 每個標註層都支持核准的評估需求。
- [ ] 沒有捏造資料量、情境數或切分比例。
- [ ] Retrieval 與 Agent 真值分開表示。
- [ ] 敏感資料與公開樣本採不同控制。
- [ ] 資料版本可連到可重現的評估。
