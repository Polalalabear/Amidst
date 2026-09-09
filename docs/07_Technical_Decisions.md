# Technical Decision Register

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **Why was an approach chosen, what alternatives were considered, and
when should the decision be revisited?** Requirements belong in the PRD;
approved technical trade-offs belong here.

### Status Convention

- `CONFIRMED`: explicitly approved and supported by evidence.
- `PROPOSED`: candidate direction awaiting approval.
- `OPEN`: decision or analysis is incomplete.
- `DEFERRED`: intentionally postponed.
- `REJECTED`: explicitly rejected with rationale.

### Decision Register

| ADR | Decision topic | Status | Owner | Affected artifacts | Review / revisit |
| --- | --- | --- | --- | --- | --- |
| ADR-001 | Evaluation-first development | PROPOSED | TODO | PRD, evaluation, dataset, architecture | TODO |
| ADR-002 | Recorded benchmark video before mandatory real-time processing | PROPOSED | TODO | PRD, dataset, architecture | TODO |
| ADR-003 | Zone-level mapping before exact 3D localization | PROPOSED | TODO | Spatial, dataset, evaluation | TODO |
| ADR-004 | Baseline pretrained perception model before custom training | PROPOSED | TODO | Evaluation, future implementation | TODO |
| ADR-005 | Structured retrieval before unnecessary semantic retrieval | PROPOSED | TODO | Retrieval, architecture | TODO |
| ADR-006 | RAG only where unstructured knowledge justifies it | PROPOSED | TODO | Retrieval, Agent | TODO |
| ADR-007 | Modular architecture before unnecessary distributed architecture | PROPOSED | TODO | Architecture | TODO |

Candidate topics are not confirmed decisions. Human review must either complete
an ADR, keep it `PROPOSED`, defer it, reject it, or remove it.

### ADR Template

#### ADR-xxx — Decision Title

Status: `OPEN`

Owner: `TODO`

Decision date: `TODO`

Affected requirements / artifacts: `TODO`

#### Context

- What problem or constraint requires a decision?
- Which confirmed requirements and evidence apply?
- What remains uncertain?

`TODO`

#### Decision Drivers

| Driver | Importance | Evidence | Status |
| --- | --- | --- | --- |
| TODO | TODO | TODO | OPEN |

#### Options Considered

| Option | Benefits | Costs / risks | Evaluation method | Outcome |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

#### Decision

`TODO`; do not complete until explicitly approved.

#### Consequences

| Consequence | Positive / negative | Mitigation | Owner |
| --- | --- | --- | --- |
| TODO | TODO | TODO | TODO |

#### Risks

| Risk | Trigger | Mitigation / experiment | Residual risk |
| --- | --- | --- | --- |
| TODO | TODO | TODO | TODO |

#### Verification

- What result would show the decision works? `TODO`
- Which benchmark/test provides that evidence? `TODO`
- Which versioned artifacts must be recorded? `TODO`

#### Revisit Condition

- New requirement or scale threshold: `TODO`.
- Failed metric or operational condition: `TODO`.
- Scheduled review: `TODO`.

#### References

- Requirements: `TODO`
- Architecture: `TODO`
- Evaluation / experiment: `TODO`
- Supersedes / superseded by: `TODO`

### Decision Review Queue

| Priority | ADR | Missing evidence / decision | Blocking work | Reviewer | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Expected Artifacts

- One ADR per material and reversible/revisitable technical choice.
- Evidence and alternatives sufficient to understand the trade-off.
- Explicit consequences, verification, and revisit conditions.
- Links to affected requirements, architecture, dataset, and evaluation artifacts.

### Document Acceptance Checklist

- [ ] No candidate decision is marked `CONFIRMED` without explicit approval.
- [ ] Each confirmed ADR records alternatives and consequences.
- [ ] Verification and revisit conditions are actionable.
- [ ] Requirements are not replaced by implementation preferences.
- [ ] Superseded or rejected decisions retain rationale and traceability.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的

回答：「為何選擇這個方案、考慮過哪些替代方案，以及何時應重新檢視？」
需求屬於 PRD；經核准的技術取捨才記錄在此。

### 狀態慣例

- `CONFIRMED`：已有明確核准與證據。
- `PROPOSED`：等待核准的候選方向。
- `OPEN`：決策或分析尚未完成。
- `DEFERRED`：刻意延後處理。
- `REJECTED`：已明確否決並留下理由。

### 決策清單

| ADR | 議題 | 狀態 |
| --- | --- | --- |
| ADR-001 | 以評估為核心的開發方式 | PROPOSED |
| ADR-002 | 強制即時處理前，先使用錄影建立基準 | PROPOSED |
| ADR-003 | 精確 3D 定位前，先採區域層級映射 | PROPOSED |
| ADR-004 | 自訂訓練前，先建立預訓練感知模型基準 | PROPOSED |
| ADR-005 | 不必要的語意檢索前，先採結構化檢索 | PROPOSED |
| ADR-006 | 只有非結構化知識確有需要時才使用 RAG | PROPOSED |
| ADR-007 | 不必要的分散式架構前，先採模組化架構 | PROPOSED |

以上都不是已確認決策。人員審查後應完成 ADR、維持提案、延後、否決或移除。

### ADR 應記錄的內容

- 標題、狀態、負責人、決策日期與受影響需求／產物；
- 問題背景、已確認限制、證據與仍不確定的部分；
- 決策驅動因素及其重要性；
- 各候選方案的效益、成本、風險與評估方法；
- 經明確核准的決策內容；
- 正面／負面後果、緩解方式與負責人；
- 風險觸發條件、實驗與殘餘風險；
- 能證明決策有效的結果、測試與版本化證據；
- 重新檢視門檻、失敗條件與預定日期；以及
- 需求、架構、評估與取代關係的連結。

在明確核准前，Decision 欄保持 `TODO`，狀態維持 `OPEN` 或
`PROPOSED`。

### 審查佇列與驗收

審查佇列應記錄優先順序、ADR、缺少的證據、阻塞工作、審查者與狀態。

- [ ] 候選決策未經明確核准，不得標為 `CONFIRMED`。
- [ ] 每項已確認 ADR 都記錄替代方案與後果。
- [ ] 驗證方法與重新檢視條件可以實際執行。
- [ ] 不以實作偏好取代需求。
- [ ] 被取代或否決的決策仍保留理由與追溯關係。
