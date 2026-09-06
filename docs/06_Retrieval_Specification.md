# Retrieval Specification Worksheet

Document status: `PROPOSED` template

## Purpose

Answer: **How does the system retrieve trustworthy data and evidence from World
State for applications and the AI Agent?** Retrieval is not synonymous with
RAG or vector search.

## Retrieval Goals

Questions:

1. What information needs cannot be answered directly by the consumer?
2. Who consumes retrieval and what guarantee does each consumer need?
3. What must be deterministic, reproducible, auditable, and timely?
4. What evidence and provenance must accompany results?

| Goal ID | Consumer need | Guarantee | Verification | Status |
| --- | --- | --- | --- | --- |
| RET-xxx | TODO | TODO | TODO | OPEN |

## Retrieval Scope

| Consumer | Use | Required request types | Required result contract | MVP? | Status |
| --- | --- | --- | --- | --- | --- |
| Agent | Ground tool use and answers | TODO | TODO | TODO | OPEN |
| Digital Twin / UI | Investigation and navigation | TODO | TODO | TODO | OPEN |
| Evaluation | Fetch fixtures, truth, predictions, traces | TODO | TODO | TODO | OPEN |
| Event investigation | Reconstruct event and evidence | TODO | TODO | TODO | OPEN |

Potential consumers are not automatically MVP requirements.

## Source of Truth

| Information | Authoritative owner/store | Read model / index | Freshness | Version / snapshot | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

Retrieval executes access; it does not become the authoritative owner merely by
returning a result.

## Retrievable Entities

| Entity | Source | Queryable Fields | Temporal | Spatial | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Camera | TODO | TODO | TODO | TODO | TODO | OPEN |
| Zone | TODO | TODO | TODO | TODO | TODO | OPEN |
| Detection | TODO | TODO | TODO | TODO | TODO | OPEN |
| Track | TODO | TODO | TODO | TODO | TODO | OPEN |
| Event | TODO | TODO | TODO | TODO | TODO | OPEN |
| Alert | TODO | TODO | TODO | TODO | TODO | OPEN |
| Evidence | TODO | TODO | TODO | TODO | TODO | OPEN |

Confirm which entities exist in the MVP before defining schemas.

## Information Needs

Candidate questions for scenario design:

- What events occurred in a selected zone?
- What happened within a time range?
- Which cameras observed a selected event?
- What evidence supports an alert?
- Which tracks were associated with an event?
- What happened before or after an event?

For each approved question, record the consumer, authoritative source, required
filters, evidence, empty-result behavior, and evaluation case.

## Query Types

| Type | Example need | Required filters | Expected source | Deterministic? | MVP? | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Temporal | Records between X and Y | Start/end, timezone, boundary rule | TODO | TODO | TODO | OPEN |
| Spatial | Records associated with Zone A | Zone/camera/location relation | TODO | TODO | TODO | OPEN |
| Event | Events of a selected type | Type, status, interval | TODO | TODO | TODO | OPEN |
| Entity | History or relations for an entity | Entity type/ID | TODO | TODO | TODO | OPEN |
| Evidence | Evidence supporting a result | Source/result IDs | TODO | TODO | TODO | OPEN |
| Combined | Time + zone + event + entity | Composed filters | TODO | TODO | TODO | OPEN |
| Semantic | Unstructured meaning-based need | Query text, corpus, filter | TODO | No | TODO | OPEN |

## Retrieval Request Schema

Define a schema only after approved query types are known.

| Candidate field | Meaning question | Required for which type? | Validation / ambiguity rule | Status |
| --- | --- | --- | --- | --- |
| `intent` / `type` | Which operation is requested? | TODO | TODO | PROPOSED |
| `time_range` | Inclusive/exclusive boundaries and timezone? | TODO | TODO | PROPOSED |
| `zone` | ID, label, or spatial relation? | TODO | TODO | PROPOSED |
| `camera` | Stable camera ID or source stream? | TODO | TODO | PROPOSED |
| `entity` | Entity type, ID, or unresolved reference? | TODO | TODO | PROPOSED |
| `event_type` | Controlled vocabulary and version? | TODO | TODO | PROPOSED |
| `filters` | Allowed operators and composition? | TODO | TODO | PROPOSED |
| `limit` | Safety, pagination, ordering? | TODO | TODO | PROPOSED |

Unresolved request questions:

- How is schema version represented?
- How are natural-language references resolved before execution?
- Which invalid, underspecified, or conflicting filters are rejected?
- How are authorization and data-scope constraints applied?

## Retrieval Response Schema

| Candidate field | Purpose | Required? | Provenance rule | Status |
| --- | --- | --- | --- | --- |
| Result records | Requested structured data | TODO | Link to source IDs/version | PROPOSED |
| Evidence | Support for records/claims | TODO | Link to originating observation/media | PROPOSED |
| Source / provenance | Explain origin and transformations | TODO | Must remain traceable | PROPOSED |
| Timestamp / snapshot | Reproduce time and state | TODO | TODO | PROPOSED |
| Confidence | Only where meaningful | TODO | Identify producer and calibration | PROPOSED |
| Result status | Success/empty/ambiguous/partial/stale/unavailable | TODO | TODO | PROPOSED |
| Pagination / truncation | Make incomplete result sets explicit | TODO | TODO | PROPOSED |

## Filter Representation

| Filter | Type / operators | Boundary semantics | Validation | Example test | Status |
| --- | --- | --- | --- | --- | --- |
| Time | TODO | Inclusive/exclusive, timezone | TODO | TODO | OPEN |
| Zone / location | TODO | Containment/overlap/association | TODO | TODO | OPEN |
| Camera | TODO | ID/alias/source | TODO | TODO | OPEN |
| Event / entity | TODO | Vocabulary/version/relations | TODO | TODO | OPEN |

## Structured Retrieval

Questions:

- Which surveillance state belongs in structured storage?
- Which filters and joins must be deterministic and reproducible?
- How are time, zone, camera, event, and track relationships indexed?
- How are schema and source snapshots versioned?

`PROPOSED`: Prefer structured querying for structured surveillance state such as
camera, zone, timestamp, event, and track unless evidence justifies otherwise.

## Temporal Retrieval

- Which clock/timezone is authoritative?
- Are intervals closed, open, or half-open?
- How are clock drift, missing timestamps, and before/after relationships handled?
- What ordering is guaranteed?

## Spatial Retrieval

- Does a spatial filter mean camera location, camera coverage, observation zone,
  entity zone, or event location?
- How are boundary, unknown, and multi-zone results represented?
- Which spatial model version applies?

## Event and Evidence Retrieval

- How are event definitions and versions selected?
- Can evidence be media, metadata, derived records, or all three?
- How is a chain from result to event, track, detection, observation, camera, and
  timestamp preserved where applicable?
- What redaction or access controls apply to evidence?

## Semantic Retrieval

Questions to answer before introducing vector search:

- What unstructured information exists?
- Which approved query cannot be solved cleanly with structured filters?
- What corpus, chunk, embedding, relevance, freshness, and authorization rules apply?
- Which benchmark justifies the added mechanism?

Semantic retrieval and RAG status: `OPEN`; not assumed for MVP.

## Hybrid Retrieval

Status: `PROPOSED` future design option.

- What sequence or fusion combines deterministic filters and semantic ranking?
- Which stage owns filtering, ranking, evidence assembly, and provenance?
- How is each stage evaluated independently?

## Evidence and Provenance

| Provenance element | Question | Verification | Status |
| --- | --- | --- | --- |
| Source record | Which authoritative ID and version produced this result? | TODO | OPEN |
| Originating camera | Which camera/source captured it? | TODO | OPEN |
| Timestamp | Which clock and precision apply? | TODO | OPEN |
| Event / related entities | Which relationships support the result? | TODO | OPEN |
| Media reference | Where is authorized evidence located and versioned? | TODO | OPEN |
| Observed vs model-generated | How is derivation identified? | TODO | OPEN |
| Confidence | Who produced it and what does it mean? | TODO | OPEN |
| Transformation trace | What filtering/aggregation occurred? | TODO | OPEN |

## Result State and Consumer Behavior

| State | Definition | Retry / clarification | Agent behavior | UI behavior | Status |
| --- | --- | --- | --- | --- | --- |
| Success | TODO | TODO | TODO | TODO | OPEN |
| Empty | No matching result under executed constraints | TODO | Must not invent evidence | TODO | PROPOSED |
| Ambiguous | Multiple interpretations require resolution | TODO | Ask/resolve before unsupported claim | TODO | PROPOSED |
| Partial | Some sources/results unavailable or truncated | TODO | Disclose limitations | TODO | PROPOSED |
| Stale | Freshness requirement not met | TODO | Disclose / retry per policy | TODO | PROPOSED |
| Unavailable | Required source cannot be queried | TODO | Report inability | TODO | PROPOSED |

## Retrieval Failure Modes

| Failure ID | Mode | Detection evidence | Expected handling | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| RET-FAIL-001 | No result | Request + source snapshot | Distinguish valid empty from failure | TODO | PROPOSED |
| RET-FAIL-002 | Wrong filter | Expected vs actual request/execution | Attribute to Agent or Retrieval | TODO | PROPOSED |
| RET-FAIL-003 | Stale data | Freshness/version evidence | Mark stale; follow retry policy | TODO | PROPOSED |
| RET-FAIL-004 | Incomplete evidence | Expected evidence set | Mark partial; do not overclaim | TODO | PROPOSED |
| RET-FAIL-005 | Ambiguous query | Multiple valid interpretations | Request clarification or return ambiguity | TODO | PROPOSED |
| RET-FAIL-006 | Wrong time window / zone | Expected vs executed constraints | Reject or flag mismatch | TODO | PROPOSED |
| RET-FAIL-007 | Unavailable source | Source health/error trace | Return unavailable/partial state | TODO | PROPOSED |
| RET-FAIL-008 | Inconsistent records | Cross-source/version conflict | Preserve conflict and provenance | TODO | PROPOSED |

## Retrieval Evaluation

| Query ID | Request | Expected Source | Expected Result | Actual Result | Correct | Failure Type |
| --- | --- | --- | --- | --- | --- | --- |
| RET-EV-xxx | TODO | TODO | TODO | TODO | TODO | TODO |

Questions:

- How is exact or set-based structured correctness measured?
- If semantic retrieval is approved, what relevance judgments and ranking metrics apply?
- How are temporal/spatial filters and provenance verified independently?
- How are correct empty, ambiguous, partial, and unavailable states tested?
- How is evidence completeness defined for each query type?

## Agent Boundary

`PROPOSED` responsibility boundary for human confirmation:

```text
Agent: decides what information is needed and constructs/chooses a tool request.
Retrieval Layer: validates and executes grounded access to data/evidence.
World State / Storage: owns authoritative stored state.
```

Attribution examples:

- Correct Agent request + incorrect result -> Retrieval Layer failure.
- Incorrect request + correct execution -> Agent/tool-planning failure.
- Correct retrieval + unsupported answer -> Agent grounding/reasoning failure.

## Security, Privacy, and Authorization

- Which consumer can retrieve which entity, field, time range, and evidence type?
- Where is authorization enforced and audited?
- How are redaction, retention, deletion, and purpose limitations applied?
- How do evaluation fixtures avoid exposing sensitive data?

## Open Questions

- Which information and query types are required by the MVP?
- Where is each retrievable entity's source of truth?
- What request/response and error contracts should be confirmed first?
- When, if ever, is semantic retrieval necessary?
- What provenance is sufficient for an Agent answer to be grounded?

## Expected Artifacts

- Approved information-needs and retrievable-entity matrix.
- Versioned request, response, filter, and result-state schemas.
- Source-of-truth and authorization map.
- Evidence/provenance contract.
- Mechanism-specific benchmark and failure-attribution cases.

## Document Acceptance Checklist

- [ ] Retrieval is not conflated with RAG, Agent reasoning, or storage ownership.
- [ ] Structured, temporal, spatial, event, evidence, semantic, and hybrid options are distinguished.
- [ ] Empty, ambiguous, partial, stale, and unavailable results are explicit.
- [ ] Results preserve enough provenance for verification.
- [ ] Retrieval evaluation can distinguish request, execution, and grounding failures.
- [ ] Unneeded entities and mechanisms remain `OPEN` or out of MVP scope.
