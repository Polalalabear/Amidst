# Amidst Project Map

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` planning worksheet

### Purpose

Keep a lightweight view of the project's current phase, known resources,
decision state, blockers, and the document that owns each planning concern.

### Project Summary

`PROPOSED`: Amidst is an evaluation-first intelligent-surveillance Digital
Twin project with AI Agent capabilities. The intended value, users, MVP
boundary, and operating environment still require human confirmation.

### Current Phase

| Field | Value | Status |
| --- | --- | --- |
| Phase | Planning and specification | CONFIRMED |
| Implementation readiness | Not ready; specifications remain open | CONFIRMED |
| Phase owner | Peter (default owner) | CONFIRMED |
| Target review date | TODO | OPEN |

### Current Objective

- Review and edit the planning worksheets in `docs/`.
- Convert only explicitly approved proposals into confirmed decisions.
- Define a small, evaluable first prototype before implementation begins.

### Available Resources

| Resource | What is known | Inspection needed | Status |
| --- | --- | --- | --- |
| Blender environment model | A model with some site annotations exists | Geometry, coordinates, units, zones, cameras, annotations, export suitability | CONFIRMED existence; contents OPEN |
| GitHub repository | Public repository location and publication policy are configured | Individual artifact classification and review ownership | CONFIRMED |
| Dataset | TODO: inventory available recordings and annotations | Ownership, sensitivity, licensing, coverage, quality | OPEN |
| Compute / deployment environment | TODO | Hardware, runtime, networking, privacy constraints | OPEN |

### Document Map

#### Core Specifications

| Document | Responsibility | Review outcome |
| --- | --- | --- |
| [01_PRD.md](01_PRD.md) | Product need, users, MVP, scope, and success | Approved requirements and prototype goal |
| [02_System_Architecture.md](02_System_Architecture.md) | Components, boundaries, entities, and information flow | Approved architecture boundaries |
| [03_Evaluation_Framework.md](03_Evaluation_Framework.md) | Correctness, benchmarks, metrics, and failure attribution | Approved evaluation contract |
| [04_Dataset_Specification.md](04_Dataset_Specification.md) | Data and ground truth needed by evaluation | Approved dataset plan |
| [05_Spatial_Model_Specification.md](05_Spatial_Model_Specification.md) | Physical/digital representation and Blender inventory | Approved spatial contract |
| [06_Retrieval_Specification.md](06_Retrieval_Specification.md) | Grounded access to World State and evidence | Approved retrieval contract |
| [07_Technical_Decisions.md](07_Technical_Decisions.md) | Decision records and revisit conditions | Reviewed ADRs |

#### Project Policy

| Document | Responsibility | Review outcome |
| --- | --- | --- |
| [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) | Authoritative GitHub/private-storage classification and publication controls | Reviewed artifact classifications |

#### Supporting Documents

| Document | Responsibility | Review outcome |
| --- | --- | --- |
| [09_Data_Types_and_Exchange_Formats.md](09_Data_Types_and_Exchange_Formats.md) | Proposed cross-layer data types and interchange-format guidance | Reviewed candidate contracts without prematurely fixing schemas |
| [internal_guide.md](internal_guide.md) | Internal contributor orientation, decision routing, and review workflow | Consistent execution without duplicating authoritative decisions |
| [glossary.md](glossary.md) | Shared vocabulary | Agreed working definitions |
| [open_questions.md](open_questions.md) | Cross-cutting unresolved decisions | Assigned and resolved questions |

Core specifications remain authoritative for their own concerns. Supporting
documents coordinate terminology and unresolved decisions without becoming
additional core specifications.

### Task-to-Document Navigation

| Task concern | Read first | Also consult when relevant |
| --- | --- | --- |
| Requirement, user need, MVP, or scope | [01_PRD.md](01_PRD.md) | [open_questions.md](open_questions.md) |
| System structure, boundary, entity ownership, or data flow | [02_System_Architecture.md](02_System_Architecture.md) | [glossary.md](glossary.md), [open_questions.md](open_questions.md) |
| Correctness, metric, validation, or failure attribution | [03_Evaluation_Framework.md](03_Evaluation_Framework.md) | [glossary.md](glossary.md) |
| Dataset, annotation, Ground Truth, or benchmark data | [04_Dataset_Specification.md](04_Dataset_Specification.md) | [03_Evaluation_Framework.md](03_Evaluation_Framework.md), [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) |
| Blender, camera, zone, coordinate, or spatial mapping | [05_Spatial_Model_Specification.md](05_Spatial_Model_Specification.md) | [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) |
| Blender metadata, video manifest, event record, or exchange format | [09_Data_Types_and_Exchange_Formats.md](09_Data_Types_and_Exchange_Formats.md) | [04_Dataset_Specification.md](04_Dataset_Specification.md), [05_Spatial_Model_Specification.md](05_Spatial_Model_Specification.md), [open_questions.md](open_questions.md) |
| Query, retrieval, evidence, provenance, or result state | [06_Retrieval_Specification.md](06_Retrieval_Specification.md) | [glossary.md](glossary.md), [open_questions.md](open_questions.md) |
| Technology choice or architectural trade-off | [07_Technical_Decisions.md](07_Technical_Decisions.md) | Affected core specification(s) |
| File classification, private storage, sanitization, or publication | [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) | Affected data/spatial specification |
| Shared terminology ambiguity | [glossary.md](glossary.md) | Specification that owns the behavior |
| Cross-document unresolved decision | [open_questions.md](open_questions.md) | All affected specifications |
| Internal workflow, decision status, or information review | [internal_guide.md](internal_guide.md) | [AGENTS.md](../AGENTS.md), affected authoritative document |

Recommended workflow:

```text
Task -> Project Map -> Relevant Core Specification
-> Glossary / Open Questions when needed -> Smallest Safe Change -> Validation
```

### Confirmed Decisions

| ID | Decision | Evidence / owner |
| --- | --- | --- |
| PM-CONF-001 | Documentation is the source of truth for implementation. | Project workflow rule |
| PM-CONF-002 | Unconfirmed requirements must not be implemented. | Project workflow rule |
| PM-CONF-003 | The current deliverables are planning worksheets, not finished specifications. | Documentation task brief |
| PM-CONF-004 | Files must be classified as `PUBLIC_ALLOWED`, `PRIVATE_ONLY`, or `REVIEW_REQUIRED` before being added to Git. | Repository publication policy |
| PM-CONF-005 | Peter is the default responsible person when no different human owner is explicitly assigned. | Project workflow rule |

### Proposed Decisions

| ID | Proposal | Confirm in |
| --- | --- | --- |
| PM-PROP-001 | Develop evaluation-first: build small, evaluate, diagnose, improve, and expand. | `01_PRD.md`, `03_Evaluation_Framework.md`, ADR |
| PM-PROP-002 | Treat Retrieval as a first-class layer distinct from Agent reasoning and storage. | `02_System_Architecture.md`, `06_Retrieval_Specification.md` |
| PM-PROP-003 | Begin spatial mapping at Camera-to-Zone granularity before exact 3D localization. | `05_Spatial_Model_Specification.md`, ADR |

### Open Questions

The cross-document decision register is [open_questions.md](open_questions.md).
Immediate review questions:

1. What single capability must the first prototype prove?
2. Which system and annotation layers are inside the MVP?
3. What usable data and Blender metadata already exist?
4. Who may access raw or identifiable surveillance data?
5. What evidence must an Agent answer expose to be considered grounded?

### Current Blockers

| Blocker | Affected work | Resolution owner | Status |
| --- | --- | --- | --- |
| MVP proof statement is not confirmed | PRD, dataset, evaluation, architecture | Peter | OPEN |
| Existing data/resource inventory is incomplete | Dataset and spatial specifications | Peter | OPEN |
| Evaluation acceptance thresholds are not confirmed | Evaluation framework | Peter | OPEN |

### Current Milestone

| Field | Value |
| --- | --- |
| Milestone | Review and confirm the planning baseline |
| Owner | Peter (default owner) |
| Exit date | TODO |
| Evidence of completion | Reviewed documents, resolved blocking questions, approved decision records |

### Next Review

| Item | Value |
| --- | --- |
| Date | TODO |
| Participants | TODO |
| Documents | TODO |
| Decisions expected | TODO |

### Definition of Current Phase Completion

- [ ] MVP goal and out-of-scope boundary are `CONFIRMED`.
- [ ] Architecture responsibilities and sources of truth are `CONFIRMED`.
- [ ] Required ground truth, benchmark protocol, and first metrics are `CONFIRMED`.
- [ ] Dataset and Blender resource inventories are complete enough to plan work.
- [ ] Retrieval/Agent boundary and evidence contract are `CONFIRMED`.
- [ ] Cross-cutting blockers have owners and resolution dates.
- [ ] No unresolved assumption is represented as a confirmed decision.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 規劃工作表

### 文件目的

用一份精簡地圖整理 Amidst 目前所處階段、已知資源、決策狀態、阻塞事項，
以及各項規劃議題應由哪份文件負責。

### 專案摘要與目前階段

`PROPOSED`：Amidst 是一項以評估為核心、結合 AI Agent 的智慧監控數位
孿生專案。預期價值、使用者、MVP 邊界與運作環境仍待人工確認。

| 項目 | 內容 | 狀態 |
| --- | --- | --- |
| 階段 | 規劃與規格制定 | CONFIRMED |
| 實作準備度 | 尚未就緒，規格仍有待決項目 | CONFIRMED |
| 階段負責人 | Peter（預設負責人） | CONFIRMED |
| 目標審查日期 | TODO | OPEN |

目前目標是審閱 docs/ 工作表、只把明確核准的提案轉為正式決策，並在開始
實作前定義一個小而可評估的第一版原型。

### 已知資源

| 資源 | 已知資訊 | 尚待確認 | 狀態 |
| --- | --- | --- | --- |
| Blender 環境模型 | 已知存在含部分場域標註的模型 | 幾何、座標、單位、區域、攝影機、標註與匯出可行性 | 存在性 CONFIRMED；內容 OPEN |
| GitHub 儲存庫 | 公開位置與發布政策已設定 | 各資產分類與審查權責 | CONFIRMED |
| 資料集 | 尚待盤點錄影與標註 | 權利、敏感性、授權、涵蓋範圍與品質 | OPEN |
| 運算／部署環境 | TODO | 硬體、執行環境、網路與隱私限制 | OPEN |

### 文件地圖

| 文件 | 責任範圍 |
| --- | --- |
| [產品需求](01_PRD.md) | 需求、使用者、MVP、範圍與成功條件 |
| [系統架構](02_System_Architecture.md) | 元件、邊界、實體與資訊流 |
| [評估框架](03_Evaluation_Framework.md) | 正確性、基準測試、指標與失敗歸因 |
| [資料集規格](04_Dataset_Specification.md) | 評估所需資料與真值標註 |
| [空間模型規格](05_Spatial_Model_Specification.md) | 實體／數位表示與 Blender 盤點 |
| [資料檢索規格](06_Retrieval_Specification.md) | 對世界狀態與證據的可靠存取 |
| [技術決策](07_Technical_Decisions.md) | 決策紀錄與重新檢視條件 |
| [發布政策](08_Repository_and_Data_Publication_Policy.md) | 公開／私人分類與發布控制 |
| [資料型別與交換格式](09_Data_Types_and_Exchange_Formats.md) | 跨層資料型別與格式候選方案 |
| [內部專案導讀](internal_guide.md) | 協作、決策分流與審查流程 |
| [術語表](glossary.md) | 共用詞彙 |
| [未決問題](open_questions.md) | 跨文件待決事項 |

核心規格各自負責所屬議題；支援文件只統整詞彙與未決問題，不應成為重複的
規格來源。

### 任務導覽

- 需求、使用者或 MVP：先讀[產品需求](01_PRD.md)。
- 系統邊界、實體或資訊流：先讀[系統架構](02_System_Architecture.md)。
- 指標、驗證或錯誤歸因：先讀[評估框架](03_Evaluation_Framework.md)。
- 資料、標註或真值：先讀[資料集規格](04_Dataset_Specification.md)。
- Blender、攝影機、區域或座標：先讀[空間模型規格](05_Spatial_Model_Specification.md)。
- 影片、事件或交換格式：先讀[資料型別與交換格式](09_Data_Types_and_Exchange_Formats.md)。
- 查詢、證據或來源追溯：先讀[資料檢索規格](06_Retrieval_Specification.md)。
- 公開與私人資料：先讀[發布政策](08_Repository_and_Data_Publication_Policy.md)。
- 跨文件決策：查閱[未決問題](open_questions.md)。

### 決策、阻塞事項與階段完成條件

已確認：文件是實作依據；未確認需求不得實作；目前交付物是規劃工作表；
加入 Git 前必須分類；未另行指定時由 Peter 預設負責。

目前提案包括以評估為先、將 Retrieval 與 Agent／儲存分開，以及先採
Camera-to-Zone 粒度再考慮精確 3D 定位。當前阻塞項目是 MVP 證明目標、
既有資料／資源盤點，以及評估驗收門檻；狀態均為 `OPEN`。

- [ ] MVP 目標與範圍外項目已 `CONFIRMED`。
- [ ] 架構責任與資料依據已 `CONFIRMED`。
- [ ] 真值、基準流程與第一批指標已 `CONFIRMED`。
- [ ] 資料集與 Blender 資源已盤點到足以規劃。
- [ ] Retrieval／Agent 邊界及證據契約已 `CONFIRMED`。
- [ ] 跨領域阻塞事項已有負責人與處理日期。
- [ ] 沒有把未決假設寫成已確認決策。
