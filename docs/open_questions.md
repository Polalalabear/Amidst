# Cross-Cutting Open Questions

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` decision registry

### Purpose

Track unresolved decisions that affect more than one specification. Keep local,
small TODOs in their owning document rather than duplicating them here.

### Question Status

- `OPEN`: no approved answer exists.
- `PROPOSED`: a candidate answer is under review.
- `CONFIRMED`: a human explicitly approved the resolution.
- `DEFERRED`: resolution is intentionally postponed.
- `REJECTED`: a proposed resolution was explicitly rejected.

This follows the project-wide decision convention; do not introduce a separate
`RESOLVED` status.

### Escalation Rule

```text
Local unresolved issue
  -> Affects one document/module only? Keep it there as TODO/OPEN.
  -> Affects multiple documents, architecture, MVP scope, evaluation,
     dataset policy, or project-wide behavior? Register it here.
```

When a specification depends on a registered question, reference its `OQ-xxx`
ID rather than duplicating the entire discussion.

### Registry

| ID | Question | Why It Matters | Affected Docs | Status | Decision |
| --- | --- | --- | --- | --- | --- |
| OQ-001 | What single capability and measurable outcome must the first prototype prove? | Defines MVP, data, architecture, and evaluation scope | PRD, Architecture, Evaluation, Dataset | OPEN | TODO |
| OQ-002 | Which layers and entities are required by the MVP? | Prevents implementing the full conceptual model prematurely | PRD, Architecture, Evaluation, Dataset, Retrieval | OPEN | TODO |
| OQ-003 | What data, annotations, and usage rights already exist? | Determines feasible benchmark and privacy boundary | Project Map, Dataset, Evaluation | OPEN | TODO |
| OQ-004 | What does the Blender resource contain and which metadata is authoritative? | Determines feasible spatial mapping and export | Project Map, Spatial, Dataset, Architecture | OPEN | TODO |
| OQ-005 | Is Camera-to-Zone / Observation-to-Zone mapping sufficient for the MVP? | Controls spatial ground truth and implementation complexity | PRD, Spatial, Evaluation, ADRs | OPEN | TODO |
| OQ-006 | Which World State records are authoritative and how are they versioned? | Required for retrieval correctness and reproducibility | Architecture, Retrieval, Evaluation, Glossary | OPEN | TODO |
| OQ-007 | Which information needs and query types must Retrieval support first? | Defines request schema, storage access, and benchmark | PRD, Retrieval, Dataset, Evaluation | OPEN | TODO |
| OQ-008 | What evidence/provenance must accompany a result and Agent answer? | Defines grounding, trust, UI, and evaluation | Architecture, Retrieval, Evaluation, Dataset | OPEN | TODO |
| OQ-009 | How must empty, ambiguous, partial, stale, and unavailable retrieval results be handled? | Prevents unsupported Agent answers and inconsistent UI behavior | Retrieval, Agent, Architecture, Evaluation | OPEN | TODO |
| OQ-010 | Is any approved need unsatisfied by structured retrieval and therefore a candidate for semantic retrieval/RAG? | Avoids unnecessary vector/RAG complexity | Retrieval, Architecture, ADRs | OPEN | TODO |
| OQ-011 | Which metrics, matching rules, and thresholds define first-prototype success? | Required for an evaluable milestone | PRD, Evaluation, Dataset | OPEN | TODO |
| OQ-012 | Who reviews `REVIEW_REQUIRED` artifacts and records sanitization/publication approval? | The classification policy is confirmed, but review authority is not assigned | Publication Policy, Dataset, Spatial, Project Map | OPEN | TODO |
| OQ-013 | What may the Agent do, which tools may it call, and how are parameters authorized? | Defines safety and Agent/Retrieval responsibility | PRD, Architecture, Retrieval, Evaluation | OPEN | TODO |
| OQ-014 | What offline, streaming, or real-time behavior is actually required? | Affects architecture, datasets, latency metrics, and ADRs | PRD, Architecture, Evaluation, ADRs | OPEN | TODO |
| OQ-015 | Which machine-readable data contracts, external standards, and time/interval semantics should Amidst adopt? | Shared Blender, video, event, evidence, Retrieval, and evaluation records need compatible versioned contracts | Architecture, Dataset, Spatial, Retrieval, Evaluation, ADRs | OPEN | Peter |

### Decision Record Template

Use this detail block only when the table cannot hold the resolution context.

#### OQ-xxx — Question

- Owner: `Peter` by default; replace only when another human owner is explicitly assigned.
- Due / review date: `TODO`
- Status: `OPEN`
- Options: `TODO`
- Evidence required: `TODO`
- Decision: `TODO`
- Rationale: `TODO`
- Affected IDs/documents: `TODO`
- Follow-up changes: `TODO`

For material technical trade-offs, link an ADR in
[07_Technical_Decisions.md](07_Technical_Decisions.md).

### Review Workflow

1. Assign an owner and evidence needed.
2. Review the owning documents and affected IDs.
3. Record an explicit status and rationale.
4. Update only directly affected documents.
5. Run `python3 -B scripts/check.py`.

### Expected Artifacts

- Owned decisions with evidence and due/review dates.
- Links from resolved questions to updated specifications and ADRs.
- A short, current list of questions blocking the next milestone.

### Document Acceptance Checklist

- [ ] Every entry affects multiple documents or a project-wide decision.
- [ ] Questions have owners before they become milestone blockers.
- [ ] Resolution includes rationale and affected artifacts.
- [ ] Confirmed decisions are propagated without duplicating responsibility.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 決策登記表

### 文件目的

追蹤會影響多份規格的未決事項。只影響單一文件或模組的小型 TODO 應留在
原文件，不要重複登記。狀態只使用 `OPEN`、`PROPOSED`、
`CONFIRMED`、`DEFERRED` 與 `REJECTED`，不另設 `RESOLVED`。

### 何時需要登記

```text
尚未解決的問題
  -> 只影響一份文件或一個模組？留在原處並標示 TODO／OPEN。
  -> 影響多份文件、架構、MVP、評估、資料政策或全專案行為？
     登記在這裡。
```

規格依賴已登記問題時，應引用 `OQ-xxx`，不要複製整段討論。

### 問題清單

| ID | 待確認事項 | 狀態 | 預設負責 |
| --- | --- | --- | --- |
| OQ-001 | 第一版原型要證明哪一項能力與可衡量成果？ | OPEN | Peter |
| OQ-002 | MVP 需要哪些層與實體？ | OPEN | Peter |
| OQ-003 | 已有哪些資料、標註與使用權？ | OPEN | Peter |
| OQ-004 | Blender 資源包含什麼，哪些中繼資料具權威性？ | OPEN | Peter |
| OQ-005 | MVP 是否只需 Camera-to-Zone／Observation-to-Zone？ | OPEN | Peter |
| OQ-006 | 哪些世界狀態紀錄具權威性，如何版本化？ | OPEN | Peter |
| OQ-007 | Retrieval 應先支援哪些資訊需求與查詢型別？ | OPEN | Peter |
| OQ-008 | 結果與 Agent 回答必須附哪些證據與來源資訊？ | OPEN | Peter |
| OQ-009 | 如何處理空結果、歧義、不完整、過期與無法使用？ | OPEN | Peter |
| OQ-010 | 是否有結構化檢索無法滿足、值得採語意檢索／RAG 的需求？ | OPEN | Peter |
| OQ-011 | 哪些指標、比對規則與門檻定義第一版成功？ | OPEN | Peter |
| OQ-012 | 誰負責審查 `REVIEW_REQUIRED` 資產並記錄發布核准？ | OPEN | Peter |
| OQ-013 | Agent 可以做什麼、使用哪些工具、參數如何授權？ | OPEN | Peter |
| OQ-014 | 實際需要離線、串流還是即時行為？ | OPEN | Peter |
| OQ-015 | Amidst 應採用哪些資料契約、外部標準與時間區間語意？ | OPEN | Peter |

### 決策紀錄與審查流程

需要詳細背景時，記錄負責人、審查日期、狀態、選項、所需證據、決策、
理由、受影響文件及後續修改。重大技術取捨應連到
[技術決策紀錄](07_Technical_Decisions.md)。

1. 指派負責人並列出所需證據。
2. 審閱主責文件與受影響 ID。
3. 明確記錄狀態及理由。
4. 只更新直接受影響的文件。
5. 執行 `python3 -B scripts/check.py`。

### 驗收條件

- [ ] 每個問題都影響多份文件或全專案決策。
- [ ] 成為里程碑阻塞項目前已有負責人。
- [ ] 解決紀錄包含理由與受影響產物。
- [ ] 已確認決策會更新到主責文件，不重複建立責任來源。
