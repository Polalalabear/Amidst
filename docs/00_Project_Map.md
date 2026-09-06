# Amidst Project Map

Document status: `PROPOSED` planning worksheet

## Purpose

Keep a lightweight view of the project's current phase, known resources,
decision state, blockers, and the document that owns each planning concern.

## Project Summary

`PROPOSED`: Amidst is an evaluation-first intelligent-surveillance Digital
Twin project with AI Agent capabilities. The intended value, users, MVP
boundary, and operating environment still require human confirmation.

## Current Phase

| Field | Value | Status |
| --- | --- | --- |
| Phase | Planning and specification | CONFIRMED |
| Implementation readiness | Not ready; specifications remain open | CONFIRMED |
| Phase owner | Peter (default owner) | CONFIRMED |
| Target review date | TODO | OPEN |

## Current Objective

- Review and edit the planning worksheets in `docs/`.
- Convert only explicitly approved proposals into confirmed decisions.
- Define a small, evaluable first prototype before implementation begins.

## Available Resources

| Resource | What is known | Inspection needed | Status |
| --- | --- | --- | --- |
| Blender environment model | A model with some site annotations exists | Geometry, coordinates, units, zones, cameras, annotations, export suitability | CONFIRMED existence; contents OPEN |
| GitHub repository | Public repository location and publication policy are configured | Individual artifact classification and review ownership | CONFIRMED |
| Dataset | TODO: inventory available recordings and annotations | Ownership, sensitivity, licensing, coverage, quality | OPEN |
| Compute / deployment environment | TODO | Hardware, runtime, networking, privacy constraints | OPEN |

## Document Map

### Core Specifications

| Document | Responsibility | Review outcome |
| --- | --- | --- |
| [01_PRD.md](01_PRD.md) | Product need, users, MVP, scope, and success | Approved requirements and prototype goal |
| [02_System_Architecture.md](02_System_Architecture.md) | Components, boundaries, entities, and information flow | Approved architecture boundaries |
| [03_Evaluation_Framework.md](03_Evaluation_Framework.md) | Correctness, benchmarks, metrics, and failure attribution | Approved evaluation contract |
| [04_Dataset_Specification.md](04_Dataset_Specification.md) | Data and ground truth needed by evaluation | Approved dataset plan |
| [05_Spatial_Model_Specification.md](05_Spatial_Model_Specification.md) | Physical/digital representation and Blender inventory | Approved spatial contract |
| [06_Retrieval_Specification.md](06_Retrieval_Specification.md) | Grounded access to World State and evidence | Approved retrieval contract |
| [07_Technical_Decisions.md](07_Technical_Decisions.md) | Decision records and revisit conditions | Reviewed ADRs |

### Project Policy

| Document | Responsibility | Review outcome |
| --- | --- | --- |
| [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) | Authoritative GitHub/private-storage classification and publication controls | Reviewed artifact classifications |

### Supporting Documents

| Document | Responsibility | Review outcome |
| --- | --- | --- |
| [glossary.md](glossary.md) | Shared vocabulary | Agreed working definitions |
| [open_questions.md](open_questions.md) | Cross-cutting unresolved decisions | Assigned and resolved questions |

Core specifications remain authoritative for their own concerns. Supporting
documents coordinate terminology and unresolved decisions without becoming
additional core specifications.

## Task-to-Document Navigation

| Task concern | Read first | Also consult when relevant |
| --- | --- | --- |
| Requirement, user need, MVP, or scope | [01_PRD.md](01_PRD.md) | [open_questions.md](open_questions.md) |
| System structure, boundary, entity ownership, or data flow | [02_System_Architecture.md](02_System_Architecture.md) | [glossary.md](glossary.md), [open_questions.md](open_questions.md) |
| Correctness, metric, validation, or failure attribution | [03_Evaluation_Framework.md](03_Evaluation_Framework.md) | [glossary.md](glossary.md) |
| Dataset, annotation, Ground Truth, or benchmark data | [04_Dataset_Specification.md](04_Dataset_Specification.md) | [03_Evaluation_Framework.md](03_Evaluation_Framework.md), [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) |
| Blender, camera, zone, coordinate, or spatial mapping | [05_Spatial_Model_Specification.md](05_Spatial_Model_Specification.md) | [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) |
| Query, retrieval, evidence, provenance, or result state | [06_Retrieval_Specification.md](06_Retrieval_Specification.md) | [glossary.md](glossary.md), [open_questions.md](open_questions.md) |
| Technology choice or architectural trade-off | [07_Technical_Decisions.md](07_Technical_Decisions.md) | Affected core specification(s) |
| File classification, private storage, sanitization, or publication | [08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md) | Affected data/spatial specification |
| Shared terminology ambiguity | [glossary.md](glossary.md) | Specification that owns the behavior |
| Cross-document unresolved decision | [open_questions.md](open_questions.md) | All affected specifications |

Recommended workflow:

```text
Task -> Project Map -> Relevant Core Specification
-> Glossary / Open Questions when needed -> Smallest Safe Change -> Validation
```

## Confirmed Decisions

| ID | Decision | Evidence / owner |
| --- | --- | --- |
| PM-CONF-001 | Documentation is the source of truth for implementation. | Project workflow rule |
| PM-CONF-002 | Unconfirmed requirements must not be implemented. | Project workflow rule |
| PM-CONF-003 | The current deliverables are planning worksheets, not finished specifications. | Documentation task brief |
| PM-CONF-004 | Files must be classified as `PUBLIC_ALLOWED`, `PRIVATE_ONLY`, or `REVIEW_REQUIRED` before being added to Git. | Repository publication policy |
| PM-CONF-005 | Peter is the default responsible person when no different human owner is explicitly assigned. | Project workflow rule |

## Proposed Decisions

| ID | Proposal | Confirm in |
| --- | --- | --- |
| PM-PROP-001 | Develop evaluation-first: build small, evaluate, diagnose, improve, and expand. | `01_PRD.md`, `03_Evaluation_Framework.md`, ADR |
| PM-PROP-002 | Treat Retrieval as a first-class layer distinct from Agent reasoning and storage. | `02_System_Architecture.md`, `06_Retrieval_Specification.md` |
| PM-PROP-003 | Begin spatial mapping at Camera-to-Zone granularity before exact 3D localization. | `05_Spatial_Model_Specification.md`, ADR |

## Open Questions

The cross-document decision register is [open_questions.md](open_questions.md).
Immediate review questions:

1. What single capability must the first prototype prove?
2. Which system and annotation layers are inside the MVP?
3. What usable data and Blender metadata already exist?
4. Who may access raw or identifiable surveillance data?
5. What evidence must an Agent answer expose to be considered grounded?

## Current Blockers

| Blocker | Affected work | Resolution owner | Status |
| --- | --- | --- | --- |
| MVP proof statement is not confirmed | PRD, dataset, evaluation, architecture | Peter | OPEN |
| Existing data/resource inventory is incomplete | Dataset and spatial specifications | Peter | OPEN |
| Evaluation acceptance thresholds are not confirmed | Evaluation framework | Peter | OPEN |

## Current Milestone

| Field | Value |
| --- | --- |
| Milestone | Review and confirm the planning baseline |
| Owner | Peter (default owner) |
| Exit date | TODO |
| Evidence of completion | Reviewed documents, resolved blocking questions, approved decision records |

## Next Review

| Item | Value |
| --- | --- |
| Date | TODO |
| Participants | TODO |
| Documents | TODO |
| Decisions expected | TODO |

## Definition of Current Phase Completion

- [ ] MVP goal and out-of-scope boundary are `CONFIRMED`.
- [ ] Architecture responsibilities and sources of truth are `CONFIRMED`.
- [ ] Required ground truth, benchmark protocol, and first metrics are `CONFIRMED`.
- [ ] Dataset and Blender resource inventories are complete enough to plan work.
- [ ] Retrieval/Agent boundary and evidence contract are `CONFIRMED`.
- [ ] Cross-cutting blockers have owners and resolution dates.
- [ ] No unresolved assumption is represented as a confirmed decision.
