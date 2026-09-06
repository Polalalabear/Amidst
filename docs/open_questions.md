# Cross-Cutting Open Questions

Document status: `PROPOSED` decision registry

## Purpose

Track unresolved decisions that affect more than one specification. Keep local,
small TODOs in their owning document rather than duplicating them here.

## Question Status

- `OPEN`: no approved answer exists.
- `PROPOSED`: a candidate answer is under review.
- `CONFIRMED`: a human explicitly approved the resolution.
- `DEFERRED`: resolution is intentionally postponed.
- `REJECTED`: a proposed resolution was explicitly rejected.

This follows the project-wide decision convention; do not introduce a separate
`RESOLVED` status.

## Escalation Rule

```text
Local unresolved issue
  -> Affects one document/module only? Keep it there as TODO/OPEN.
  -> Affects multiple documents, architecture, MVP scope, evaluation,
     dataset policy, or project-wide behavior? Register it here.
```

When a specification depends on a registered question, reference its `OQ-xxx`
ID rather than duplicating the entire discussion.

## Registry

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

## Decision Record Template

Use this detail block only when the table cannot hold the resolution context.

### OQ-xxx — Question

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

## Review Workflow

1. Assign an owner and evidence needed.
2. Review the owning documents and affected IDs.
3. Record an explicit status and rationale.
4. Update only directly affected documents.
5. Run `python3 -B scripts/check.py`.

## Expected Artifacts

- Owned decisions with evidence and due/review dates.
- Links from resolved questions to updated specifications and ADRs.
- A short, current list of questions blocking the next milestone.

## Document Acceptance Checklist

- [ ] Every entry affects multiple documents or a project-wide decision.
- [ ] Questions have owners before they become milestone blockers.
- [ ] Resolution includes rationale and affected artifacts.
- [ ] Confirmed decisions are propagated without duplicating responsibility.
