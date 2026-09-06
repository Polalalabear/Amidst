# Product Requirements Document Worksheet

Document status: `PROPOSED` template

## Purpose

Answer: **What are we building, for whom, and what must the first prototype
prove?** This document should define outcomes without prematurely selecting the
implementation.

## Problem Statement

- What surveillance or operational problem is not adequately solved today?
- Who experiences the problem, where, and how often?
- What evidence demonstrates the problem?
- What happens if the project does nothing?

Statement: `TODO`

Status: `OPEN`

## Project Vision

`PROPOSED`: Connect physical observations, temporal/spatial understanding,
structured World State, trustworthy retrieval, Agent reasoning, and a Digital
Twin interface into an evaluable system.

Human edits required:

- Define the intended outcome in one sentence.
- Define the time horizon and organizational boundary.
- Identify what the vision intentionally does not promise.

## Stakeholders / Users

| Stakeholder / user | Need | Decision authority | Data access | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

Questions:

- Who investigates events, monitors operations, reviews evaluation, or manages data?
- Who is affected by surveillance but does not operate the system?
- Who approves privacy, security, and deployment decisions?

## Use Cases

| UC ID | Actor | Trigger | Desired outcome | Required evidence | MVP? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| UC-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Candidate prompts for review, not requirements:

- `PROPOSED`: Investigate events in a zone and time range.
- `PROPOSED`: Trace which cameras and records support an alert.
- `PROPOSED`: Ask what occurred before or after a selected event.

## MVP Goal

Complete this sentence:

> The smallest prototype must prove that `TODO`, under `TODO` conditions, with
> correctness measured by `TODO`.

Status: `OPEN`

## Functional Requirements

| ID | Requirement | Status | Priority | Verification |
| --- | --- | --- | --- | --- |
| FR-xxx | TODO | OPEN | TODO | TODO |

Requirement-writing checks:

- Is the behavior observable and testable?
- Does it identify the source of truth and evidence when relevant?
- Is it necessary for the MVP rather than only the future vision?
- Does its verification link to `03_Evaluation_Framework.md`?

## Non-Functional Requirements

| ID | Quality / constraint | Target | Conditions | Verification | Status |
| --- | --- | --- | --- | --- | --- |
| NFR-xxx | TODO | TODO | TODO | TODO | OPEN |

Consider only when justified: privacy, security, latency, availability,
auditability, reproducibility, maintainability, and accessibility.

## Scope

| Capability | Why included | Required layer(s) | Verification | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

## Out of Scope

| Capability | Reason excluded | Revisit condition | Status |
| --- | --- | --- | --- |
| TODO | TODO | TODO | OPEN |

Do not label future capabilities `REJECTED` unless they were explicitly
rejected; use `DEFERRED` when intentionally postponed.

## Success Criteria

| Criterion ID | Outcome | Measurement | Threshold | Evidence | Status |
| --- | --- | --- | --- | --- | --- |
| SC-xxx | TODO | TODO | TODO | TODO | OPEN |

## Assumptions

| Assumption | How to verify | Owner | Due | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

## Constraints

| Constraint | Source | Impact | Can change? | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

## Dependencies

| Dependency | Needed for | Availability | Fallback | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Risks

| Risk ID | Risk | Likelihood | Impact | Mitigation / experiment | Owner | Status |
| --- | --- | --- | --- | --- | --- | --- |
| RISK-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Include risks involving privacy, dataset bias, false alarms, missed events,
evidence integrity, spatial misalignment, retrieval errors, and unsupported
Agent answers only when relevant to approved use cases.

## Open Questions

- Which user and use case define the first prototype?
- Is the first benchmark offline recorded video, real-time input, or another source?
- Which capabilities require an Agent rather than deterministic application logic?
- What response is safe when evidence is missing or ambiguous?

Cross-cutting decisions belong in [open_questions.md](open_questions.md).

## Future Scope

| Candidate capability | Dependency | Revisit trigger | Status |
| --- | --- | --- | --- |
| Precise pixel-to-3D localization | Confirmed need and spatial ground truth | TODO | DEFERRED |
| Semantic retrieval / RAG | Demonstrated unstructured retrieval need | TODO | PROPOSED |
| Real-time production processing | Offline baseline and latency requirement | TODO | PROPOSED |

## Expected Artifacts

- A one-sentence MVP proof statement.
- A prioritized, testable requirement register.
- Explicit scope and out-of-scope boundaries.
- Measurable success criteria linked to evaluation.
- Owned assumptions, constraints, dependencies, and risks.

## Document Acceptance Checklist

- [ ] Target users and decision-makers are identified.
- [ ] Every MVP requirement has a verification method.
- [ ] Success criteria have approved conditions and thresholds.
- [ ] Scope does not assume every conceptual system entity is required.
- [ ] Open decisions are not presented as facts.
- [ ] Architecture or technology choices are not silently embedded in requirements.
