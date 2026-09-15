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
| OQ-016 | Which deterministic texture-agnostic shading/illumination, observation-usability, and cross-environment pixel rules should govern the first slice? | The v0.1.1 diagnostic is environment-sensitive; migration adds a new OS/backend tuple that must not be mixed with the source run without an approved comparison | Dataset, Spatial, Data Formats, Render Config, ADRs | OPEN | Peter |

### Confirmed Partial Resolutions

- OQ-004: `CONFIRMED` only for stable `school` object identity. The versioned
  sidecar registry is authoritative and Blender `instance_id` properties are
  mirrors. Policy 1.0.1 also confirms the `school_v1` objective-disambiguation
  and reviewed-bootstrap sidecars plus exclusion of the imported saved-view
  helper camera. Other Blender semantic, coordinate, camera, and export
  authorities remain `OPEN`.
- OQ-015: `CONFIRMED` only for contract
  `amidst.school.object-id/1.0.1`, its unchanged base-fingerprint algorithm
  v1.0.0, namespace UUID
  `1601a7c1-19ac-555d-9962-05e4503ac6bd`, UUIDv5 format, canonical
  fingerprinting, approved override/bootstrap resolution, remaining
  collision/ambiguity failure, and permanent tombstones. The scoped
  `school_v1` first-slice contracts are also `CONFIRMED`: task contract
  `amidst.school.first-dataset-slice/0.1.0`, metadata schema
  `amidst.first-dataset-slice.metadata/0.1.0`, spatial/visibility contracts
  `amidst.school.first-slice-spatial/1.0.0` and
  `amidst.school.first-slice-visibility/1.0.0`, render config
  `amidst.school.first-slice-render/0.1.0`, and category-agnostic semantic
  baseline `school.v1.semantic/0.1.0`. Resource policy
  `amidst.school.texture-agnostic-render/0.1.0` confirms that the five preserved
  legacy missing images are not runtime requirements and that visual fidelity
  is non-authoritative. Other schemas, external-standard choices,
  and general time/interval semantics remain `OPEN`; this partial resolution
  does not close OQ-015.
- OQ-016 blocks a second pilot. Diagnostic
  `data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.json`
  proves that the prior accepted image is pixel-identical to a fresh render but
  has no pixels above the proposed 0.10 visibility threshold and only
  0.011764705 P1-P99 luminance range. The v0.1.1 render-only policy and derived
  scene were subsequently authorized for diagnostic evidence, but its
  29-camera sweep and thresholds are not yet complete. Treatment of nearly
  single-object camera views and the acceptance boundary for pixel, PNG-byte,
  and cross-environment determinism remain `OPEN`. Whether decoded pixels must
  match exactly across different OS, architecture, Blender build, backend,
  device, or driver tuples is not yet authoritative; source-host and
  destination-host statistics must remain separate.

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
| OQ-016 | 首批資料應採哪些 deterministic texture-agnostic shading／illumination、observation-usability 與跨環境 pixel 規則？ | OPEN | Peter |

### 已確認的部分決議

- OQ-004：只有 `school` 穩定物件 identity 子範圍為 `CONFIRMED`。版本化
  sidecar registry 是權威來源，Blender `instance_id` property 是鏡像；policy
  1.0.1 也確認 `school_v1` objective-disambiguation／reviewed-bootstrap sidecar
  及 imported saved-view helper camera 排除。其他 Blender 語意、座標、相機
  與 export authority 仍為 `OPEN`。
- OQ-015：只有 `amidst.school.object-id/1.0.1` 契約、不變的 base-fingerprint
  algorithm v1.0.0、namespace UUID
  `1601a7c1-19ac-555d-9962-05e4503ac6bd`、UUIDv5 格式、canonical
  fingerprint、已核准 override／bootstrap 解歧、剩餘 collision／ambiguity
  失敗規則與永久 tombstone 為 `CONFIRMED`。限定 `school_v1` 的首批資料契約
  也已確認：task contract `amidst.school.first-dataset-slice/0.1.0`、metadata
  schema `amidst.first-dataset-slice.metadata/0.1.0`、spatial／visibility contract
  `amidst.school.first-slice-spatial/1.0.0` 與
  `amidst.school.first-slice-visibility/1.0.0`、render config
  `amidst.school.first-slice-render/0.1.0`，以及 category-agnostic semantic
  baseline `school.v1.semantic/0.1.0`。Resource policy
  `amidst.school.texture-agnostic-render/0.1.0` 確認保留的五個 legacy missing
  images 不是 runtime requirements，且 visual fidelity 不具權威性。其他
  schema、外部標準選擇與一般時間／
  區間語意仍為 `OPEN`，此部分決議不關閉 OQ-015。
- OQ-016 會阻擋第二次 pilot。診斷
  `data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.json`
  證明先前 accepted image 與 fresh render 的 pixels 完全相同，但沒有 pixels
  高於 proposed `0.10` 可視門檻，且 P1-P99 luminance range 只有
  `0.011764705`。其後已核准 v0.1.1 render-only policy 與 derived scene 供
  diagnostic evidence，但 29-camera sweep 與門檻尚未完成。幾乎由單一物件
  佔滿畫面的 camera 處理方式，以及 pixel、PNG bytes 與跨環境 determinism
  的驗收邊界皆維持 `OPEN`。不同 OS、architecture、Blender build、backend、
  device 或 driver tuple 的 decoded pixels 是否必須完全相同尚不具權威性；
  來源與目標主機的 statistics 必須分開。

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
