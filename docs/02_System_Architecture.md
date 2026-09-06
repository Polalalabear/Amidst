# System Architecture Worksheet

Document status: `PROPOSED` template

## Purpose

Answer: **What are the system responsibilities, boundaries, sources of truth,
and information flows?** This document does not decide monolith versus
microservices or select a technology stack.

## Architecture Goals

| Goal ID | Goal | Why required | Verification | Status |
| --- | --- | --- | --- | --- |
| ARCH-xxx | TODO | TODO | TODO | OPEN |

## Architecture Principles

| Principle | Rationale | Trade-off | Status |
| --- | --- | --- | --- |
| Evaluation at relevant layers | Diagnose errors before they reach end-to-end output | Requires layer contracts and ground truth | PROPOSED |
| Grounded evidence flow | Preserve traceability from observations to answers | Adds provenance requirements | PROPOSED |
| Replaceable modules | Allow baselines and improved components to be compared | Requires stable interfaces | PROPOSED |
| Structured retrieval first where data is structured | Keep deterministic queries reproducible | Semantic search may still be needed later | PROPOSED |

## System Context

| External actor / system | Sends | Receives | Trust boundary | Status |
| --- | --- | --- | --- | --- |
| Physical environment | Observable activity | None | TODO | PROPOSED |
| Surveillance source | Frames / streams / metadata | Configuration | TODO | PROPOSED |
| Human user | Query / investigation intent | Evidence-backed result | TODO | PROPOSED |
| Evaluation operator | Ground truth / benchmark request | Metrics / errors | TODO | PROPOSED |

## High-Level Architecture

`PROPOSED` conceptual flow for review:

```text
Physical Environment + Surveillance Observation
  -> Perception
  -> Tracking / Temporal
  -> Spatial Mapping
  -> Event Understanding
  -> World State / Storage
  -> Retrieval
  -> Agent / Reasoning
  -> Application / Digital Twin UI

Evaluation observes each relevant boundary, not only the final output.
```

Questions:

- Which layers are required for the first prototype?
- Can any layer be represented by ground truth or a stub in the first benchmark?
- Where are synchronous, asynchronous, batch, or streaming boundaries required?

## Module Boundaries

| Module | Responsibility | Input | Output | Source of Truth | Must Not Own |
| --- | --- | --- | --- | --- | --- |
| Perception | TODO | Observation | Detection | TODO | Track identity unless explicitly combined |
| Tracking / Temporal | TODO | Detection sequence | Track / temporal state | TODO | Physical zone definition |
| Spatial Mapping | TODO | Observation, camera, track | Location / zone association | TODO | Event policy |
| Event Understanding | TODO | Temporal/spatial entities | Event / alert candidate | TODO | Raw evidence storage policy |
| World State / Storage | TODO | Versioned system records | Authoritative stored state | TODO | User-intent interpretation |
| Retrieval | Execute grounded access to data/evidence | Retrieval request | Records, evidence, provenance, result status | World State references | Agent reasoning |
| Agent | Interpret intent and use tools/evidence | User query, tool results | Tool calls, grounded answer | TODO | Authoritative surveillance state |
| Application / Digital Twin UI | TODO | World state / evidence / answer | User interaction | TODO | Hidden inference logic |
| Evaluation | Compare predictions and ground truth | Versions, predictions, ground truth | Metrics, error records | Benchmark definition | Production state |

All rows remain `OPEN` unless a decision record confirms them.

## Perception Layer

- What observations are accepted?
- What classes and outputs are required by the MVP?
- How are model/configuration versions attached to detections?
- What confidence and evidence must be preserved?

## Tracking / Temporal Layer

- What defines identity continuity and track lifetime?
- How are gaps, merges, splits, and ID changes represented?
- Which timestamps are authoritative?
- Is tracking required for the first prototype?

## Spatial Layer

- Is Camera-to-Zone mapping sufficient for the MVP?
- Where do coordinate systems, zones, and camera poses come from?
- How is spatial uncertainty represented?
- Which component owns spatial metadata?

## Event Layer

- What distinguishes an observation, event, and alert?
- How are event start/end, participants, location, and evidence represented?
- Which event definitions are deterministic versus model-derived?
- How are duplicate or overlapping events handled?

## World State / Storage Layer

- Which records are authoritative, derived, mutable, or append-only?
- How are entity relationships and versions stored?
- What retention, privacy, and deletion requirements apply?
- How can a stored answer be traced to source observations and model versions?

## Retrieval Layer

- Which request types and filters are supported?
- Which data sources can retrieval access?
- How does retrieval report success, empty, ambiguous, partial, stale, or unavailable results?
- How are returned evidence and provenance represented?

The retrieval contract is owned by
[06_Retrieval_Specification.md](06_Retrieval_Specification.md).

## Agent Layer

- What user intents are supported?
- Which retrieval or application tools may the Agent call?
- How are parameters validated before tool execution?
- How must the Agent cite or expose supporting evidence?
- What must the Agent do when retrieval is empty or ambiguous?

## Digital Twin / Application Layer

- Which views and interactions are needed for the approved use cases?
- Which state is visualized versus authored in the UI?
- How are time, zone, camera, event, and evidence linked?
- What accessibility and audit needs apply?

## Evaluation Layer

- At which interfaces are predictions and ground truth captured?
- How are evaluator, dataset, model, and configuration versions linked?
- How are component failures distinguished from upstream failures?
- Which regressions prevent release or further expansion?

## Data Flow

| Flow ID | Producer | Payload | Consumer | Ordering / timing | Provenance | Status |
| --- | --- | --- | --- | --- | --- | --- |
| FLOW-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Agent-query trace to preserve:

```text
User Query -> Agent Intent -> Retrieval Request -> Retrieved Evidence
-> Agent Answer -> Evaluation
```

## Core Entities

| Entity | Working responsibility | Key relationships to review | MVP? | Status |
| --- | --- | --- | --- | --- |
| Camera | Observation source and spatial reference | Observation, Zone, Evidence | TODO | OPEN |
| Observation | Source media/sample at a time | Camera, Detection, Evidence | TODO | OPEN |
| Detection | Per-frame perceived entity candidate | Observation, Track | TODO | OPEN |
| Object / Person | Domain entity concept | Detection, Track, Event | TODO | OPEN |
| Track | Temporal identity hypothesis | Detection, Event, Zone | TODO | OPEN |
| Zone / Location | Spatial semantic reference | Camera, Track, Event | TODO | OPEN |
| Event / Alert | Interpreted occurrence / notification | Track, Zone, Evidence | TODO | OPEN |
| Evidence | Traceable support for a result or answer | Source record, Event, Query | TODO | OPEN |
| Query / Retrieved Result | Information request and grounded result | Filters, Evidence, Tool Call | TODO | OPEN |
| Agent Tool Call / Answer | Reasoning action and user-facing response | Query, Retrieved Result | TODO | OPEN |

## Module Interfaces

| Interface ID | Producer | Consumer | Request / input | Response / output | Error contract | Version | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ARCH-IF-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

## Failure Boundaries

| Boundary | Example failure | Owning layer | Upstream evidence needed | User-visible behavior | Status |
| --- | --- | --- | --- | --- | --- |
| Agent -> Retrieval | Incorrect filters in an otherwise executable request | Agent / tool planning | Parsed intent and request | TODO | OPEN |
| Retrieval -> Storage | Correct request returns wrong records | Retrieval | Query trace and source snapshot | TODO | OPEN |
| Retrieval -> Agent | Correct evidence is ignored or contradicted | Agent grounding / reasoning | Returned evidence and answer | TODO | OPEN |
| Component -> Evaluation | Version or ground truth cannot be resolved | Evaluation / provenance | Version manifests | TODO | OPEN |

## Observability

| Signal | Question answered | Producer | Retention | Sensitive? | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Replaceability / Modularity

- Which interfaces must allow baseline and candidate implementations to be swapped?
- What fixture or benchmark proves compatibility?
- Which state must remain implementation-independent?
- What coupling is acceptable for the MVP?

## Open Architecture Decisions

- MVP layer boundary and deployment shape.
- Authoritative World State representation.
- Event and evidence lifecycle.
- Offline, streaming, and real-time boundaries.
- Retrieval request/response contract.
- Agent tool and safety boundary.

Track cross-cutting decisions in [open_questions.md](open_questions.md) and
[07_Technical_Decisions.md](07_Technical_Decisions.md).

## Expected Artifacts

- Approved context and layer diagram.
- Responsibility and source-of-truth matrix.
- Versioned interface contracts and error behavior.
- Entity relationship model limited to MVP needs.
- Failure-attribution and observability plan.

## Document Acceptance Checklist

- [ ] Every MVP responsibility has exactly one clear owner.
- [ ] Retrieval is distinct from Agent reasoning and World State ownership.
- [ ] Evaluation can inspect relevant component boundaries.
- [ ] Information and evidence provenance survive each required flow.
- [ ] Architecture style and technology remain open unless explicitly decided.
