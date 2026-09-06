# Technical Decision Register

Document status: `PROPOSED` template

## Purpose

Answer: **Why was an approach chosen, what alternatives were considered, and
when should the decision be revisited?** Requirements belong in the PRD;
approved technical trade-offs belong here.

## Status Convention

- `CONFIRMED`: explicitly approved and supported by evidence.
- `PROPOSED`: candidate direction awaiting approval.
- `OPEN`: decision or analysis is incomplete.
- `DEFERRED`: intentionally postponed.
- `REJECTED`: explicitly rejected with rationale.

## Decision Register

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

## ADR Template

### ADR-xxx — Decision Title

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

## Decision Review Queue

| Priority | ADR | Missing evidence / decision | Blocking work | Reviewer | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Expected Artifacts

- One ADR per material and reversible/revisitable technical choice.
- Evidence and alternatives sufficient to understand the trade-off.
- Explicit consequences, verification, and revisit conditions.
- Links to affected requirements, architecture, dataset, and evaluation artifacts.

## Document Acceptance Checklist

- [ ] No candidate decision is marked `CONFIRMED` without explicit approval.
- [ ] Each confirmed ADR records alternatives and consequences.
- [ ] Verification and revisit conditions are actionable.
- [ ] Requirements are not replaced by implementation preferences.
- [ ] Superseded or rejected decisions retain rationale and traceability.
