# Product Requirements Document Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **What are we building, for whom, and what must the first prototype
prove?** This document should define outcomes without prematurely selecting the
implementation.

### Problem Statement

- What surveillance or operational problem is not adequately solved today?
- Who experiences the problem, where, and how often?
- What evidence demonstrates the problem?
- What happens if the project does nothing?

Statement: `TODO`

Status: `OPEN`

### Project Vision

`PROPOSED`: Connect physical observations, temporal/spatial understanding,
structured World State, trustworthy retrieval, Agent reasoning, and a Digital
Twin interface into an evaluable system.

Human edits required:

- Define the intended outcome in one sentence.
- Define the time horizon and organizational boundary.
- Identify what the vision intentionally does not promise.

### Stakeholders / Users

| Stakeholder / user | Need | Decision authority | Data access | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

Questions:

- Who investigates events, monitors operations, reviews evaluation, or manages data?
- Who is affected by surveillance but does not operate the system?
- Who approves privacy, security, and deployment decisions?

### Use Cases

| UC ID | Actor | Trigger | Desired outcome | Required evidence | MVP? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| UC-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Candidate prompts for review, not requirements:

- `PROPOSED`: Investigate events in a zone and time range.
- `PROPOSED`: Trace which cameras and records support an alert.
- `PROPOSED`: Ask what occurred before or after a selected event.

### MVP Goal

Complete this sentence:

> The smallest prototype must prove that `TODO`, under `TODO` conditions, with
> correctness measured by `TODO`.

Status: `OPEN`

### Functional Requirements

| ID | Requirement | Status | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-xxx | TODO | OPEN | TODO | TODO |

Requirement-writing checks:

- Is the behavior observable and testable?
- Does it identify the source of truth and evidence when relevant?
- Is it necessary for the MVP rather than only the future vision?
- Does its verification link to `03_Evaluation_Framework.md`?

### Non-Functional Requirements

| ID | Quality / constraint | Target | Conditions | Verification | Status |
| --- | --- | --- | --- | --- | --- |
| NFR-xxx | TODO | TODO | TODO | TODO | OPEN |

Consider only when justified: privacy, security, latency, availability,
auditability, reproducibility, maintainability, and accessibility.

### Scope

| Capability | Why included | Required layer(s) | Verification | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

### Out of Scope

| Capability | Reason excluded | Revisit condition | Status |
| --- | --- | --- | --- |
| TODO | TODO | TODO | OPEN |

Do not label future capabilities `REJECTED` unless they were explicitly
rejected; use `DEFERRED` when intentionally postponed.

### Success Criteria

| Criterion ID | Outcome | Measurement | Threshold | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| SC-xxx | TODO | TODO | TODO | TODO | OPEN |

### Assumptions

| Assumption | How to verify | Owner | Due | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

### Constraints

| Constraint | Source | Impact | Can change? | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

### Dependencies

| Dependency | Needed for | Availability | Fallback | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Risks

| Risk ID | Risk | Likelihood | Impact | Mitigation / experiment | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| RISK-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Include risks involving privacy, dataset bias, false alarms, missed events,
evidence integrity, spatial misalignment, retrieval errors, and unsupported
Agent answers only when relevant to approved use cases.

### Open Questions

- Which user and use case define the first prototype?
- Is the first benchmark offline recorded video, real-time input, or another source?
- Which capabilities require an Agent rather than deterministic application logic?
- What response is safe when evidence is missing or ambiguous?

Cross-cutting decisions belong in [open_questions.md](open_questions.md).

### Future Scope

| Candidate capability | Dependency | Revisit trigger | Status |
| --- | --- | --- | --- |
| Precise pixel-to-3D localization | Confirmed need and spatial ground truth | TODO | DEFERRED |
| Semantic retrieval / RAG | Demonstrated unstructured retrieval need | TODO | PROPOSED |
| Real-time production processing | Offline baseline and latency requirement | TODO | PROPOSED |

### Expected Artifacts

- A one-sentence MVP proof statement.
- A prioritized, testable requirement register.
- Explicit scope and out-of-scope boundaries.
- Measurable success criteria linked to evaluation.
- Owned assumptions, constraints, dependencies, and risks.

### Document Acceptance Checklist

- [ ] Target users and decision-makers are identified.
- [ ] Every MVP requirement has a verification method.
- [ ] Success criteria have approved conditions and thresholds.
- [ ] Scope does not assume every conceptual system entity is required.
- [ ] Open decisions are not presented as facts.
- [ ] Architecture or technology choices are not silently embedded in requirements.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的

回答：「我們要做什麼、為誰而做，以及第一版原型必須證明什麼？」本文件
先定義成果，不要過早選定實作方式。

### 問題、願景與使用者

問題陳述應說明目前未被妥善解決的監控或作業問題、受影響的人與情境、
支持問題存在的證據，以及不處理的後果。目前陳述為 `TODO`，狀態
`OPEN`。

`PROPOSED` 願景：把實體觀測、時空理解、結構化世界狀態、可信資料檢索、
Agent 推理與數位孿生介面連成可評估的系統。仍須由人員補上單句成果、
時間與組織邊界，以及願景刻意不承諾的事項。

| 利害關係人／使用者 | 需求 | 決策權限 | 資料存取 | 狀態 |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

需要確認誰負責事件調查、作業監控、評估與資料管理，誰受到監控影響，以及
誰能核准隱私、安全與部署決策。

### 使用情境與 MVP

| 情境 ID | 使用者 | 觸發條件 | 預期結果 | 必要證據 | MVP？ | 狀態 |
| --- | --- | --- | --- | --- | --- | --- |
| UC-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

可供審查、但尚非需求的方向包括：查詢指定區域與時段的事件、追溯哪些
攝影機與紀錄支持警示，以及詢問事件前後發生的事情。

> 最小原型必須在 `TODO` 條件下證明 `TODO`，並以 `TODO` 衡量正確性。

MVP 目標目前為 `OPEN`。

### 需求與範圍

功能需求需包含 ID、可觀察的行為、狀態、優先順序與驗證方法，並確認它是
MVP 必要內容、能指出資料依據與證據，且驗證能連到
[評估框架](03_Evaluation_Framework.md)。

非功能需求只在有依據時納入，例如隱私、安全、延遲、可用性、可稽核性、
可重現性、可維護性與無障礙。

| 類型 | 必須記錄 |
| --- | --- |
| 範圍內能力 | 納入原因、所需層、驗證方法與狀態 |
| 範圍外能力 | 排除原因、重新檢視條件與狀態 |
| 成功條件 | 成果、衡量方式、門檻、證據與狀態 |

未明確否決的未來能力不要標為 `REJECTED`；刻意延後時使用
`DEFERRED`。

### 假設、限制、依賴與風險

每項假設應有驗證方法、負責人、期限與狀態；限制要記錄來源、影響與是否
可變更；依賴要記錄用途、可用性、替代方案與負責人。

風險只有在與核准情境相關時才納入，包括隱私、資料偏差、誤報、漏報、
證據完整性、空間錯位、資料檢索錯誤及 Agent 無依據回答。

### 未決問題與未來範圍

- 哪個使用者與情境定義第一版原型？
- 第一個基準採離線錄影、即時輸入，還是其他來源？
- 哪些能力確實需要 Agent，而不是確定性的應用邏輯？
- 證據不足或語意不明時，什麼回應才安全？

跨文件決策統一放在 [open_questions.md](open_questions.md)。

| 未來候選能力 | 前提 | 狀態 |
| --- | --- | --- |
| 精確像素到 3D 定位 | 已確認需求與空間真值 | DEFERRED |
| 語意檢索／RAG | 證明有非結構化檢索需求 | PROPOSED |
| 即時正式環境處理 | 完成離線基準並確認延遲需求 | PROPOSED |

### 預期產出與驗收

預期產出包括單句 MVP 證明目標、可測試且有優先順序的需求清單、明確範圍
界線、連結評估的成功條件，以及有負責人的假設、限制、依賴與風險。

- [ ] 已找出目標使用者與決策者。
- [ ] 每項 MVP 需求都有驗證方法。
- [ ] 成功條件已有核准的情境與門檻。
- [ ] 範圍沒有預設概念架構中的所有實體都必須納入。
- [ ] 未決事項沒有被當成事實。
- [ ] 需求中沒有暗藏架構或技術選擇。
