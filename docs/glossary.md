# Project Glossary Worksheet

Document status: `PROPOSED` template

## Purpose

Prevent the same term from carrying incompatible meanings across product,
architecture, dataset, evaluation, retrieval, and Agent documents.

## Status Convention

- `CONFIRMED`: a human-confirmed definition supported by an authoritative artifact.
- `PROPOSED`: a candidate definition awaiting confirmation.
- `OPEN`: the definition or boundary is unresolved; use this when uncertain.
- `DEFERRED`: definition work is intentionally postponed.
- `REJECTED`: a definition was explicitly rejected and its rationale is recorded.

## Ownership Boundary

This glossary owns shared terminology. Domain specifications own how a shared
term behaves in their context:

- System Architecture owns which component produces or stores an Event.
- Evaluation Framework owns how Event correctness is evaluated.
- Dataset Specification owns how Event Ground Truth is annotated.
- Retrieval Specification owns how an Event and its Evidence are retrieved.

Specifications should reference shared definitions rather than create competing
ones. If a definition is unresolved, keep it `OPEN` instead of selecting one.

## Editing Rules

- Define a term operationally enough to determine what is and is not an instance.
- Identify the source of truth and related IDs where relevant.
- Link approved definitions to schemas or decision records.
- Use `OPEN` when boundaries are unresolved.

## Terms

| Term | Working definition | Distinguish from | Source of truth / artifact | Status |
| --- | --- | --- | --- | --- |
| Observation | TODO: define captured input unit and time/source identity | Detection, Evidence | TODO | OPEN |
| Detection | TODO: define a per-observation perceived entity candidate | Object, Track | TODO | OPEN |
| Object | TODO: define non-person domain entity, if needed | Detection, Person, Track | TODO | OPEN |
| Person | TODO: define whether this is a class, entity, or privacy-sensitive identity concept | Object, Detection, Track | TODO | OPEN |
| Track | TODO: define temporal identity hypothesis and lifetime | Detection, Object / Person | TODO | OPEN |
| Camera | TODO: define physical device, stream, calibration, or logical source | Observation source | TODO | OPEN |
| Zone | TODO: define semantic spatial region and boundary | Location | TODO | OPEN |
| Location | TODO: define spatial value/granularity | Zone, coordinates | TODO | OPEN |
| Event | TODO: define interpreted occurrence, interval, entities, location, and evidence | Observation, Alert | TODO | OPEN |
| Alert | TODO: define notification/policy outcome | Event | TODO | OPEN |
| World State | TODO: define authoritative structured system knowledge at a version/time | Retrieval result, UI state | TODO | OPEN |
| Evidence | TODO: define traceable support for a record, event, alert, or answer | Prediction, explanation | TODO | OPEN |
| Ground Truth | TODO: define approved reference labels/rubric and version | Prediction, benchmark result | TODO | OPEN |
| Benchmark | TODO: define frozen data, protocol, evaluator, and versions | Dataset, experiment | TODO | OPEN |
| Retrieval | TODO: define grounded execution of an information request | Agent reasoning, storage | TODO | OPEN |
| Structured Retrieval | TODO: define deterministic access using fields, relations, and filters | Semantic Retrieval | TODO | OPEN |
| Semantic Retrieval | TODO: define meaning-based retrieval over approved unstructured content | Structured Retrieval | TODO | OPEN |
| RAG | TODO: define only if generation uses retrieved context | Retrieval in general | TODO | OPEN |
| Tool Call | TODO: define a versioned Agent action/request and its result | Retrieval execution | TODO | OPEN |
| Agent | TODO: define allowed intent interpretation, tool planning, and answer behavior | Retrieval Layer, UI | TODO | OPEN |
| Digital Twin | TODO: define which physical/digital state, time, and interactions it represents | 3D visualization alone | TODO | OPEN |

## Conceptual Distinctions

These boundaries do not finalize the individual term definitions.

| Distinction | Existing authority | Status |
| --- | --- | --- |
| Observation is not inference | Project data-provenance boundary | CONFIRMED |
| Ground Truth is not prediction | Project Ground Truth and benchmark integrity rules | CONFIRMED |
| Detection is not Track | Definitions and precise relationship still require review | OPEN |
| Event is not Alert | Definitions and promotion/notification relationship still require review | OPEN |
| Retrieved Evidence is not Agent Interpretation | Project Retrieval and Agent boundary | CONFIRMED |
| World State is not Agent Answer | Project Retrieval and Agent boundary | CONFIRMED |

## Relationship Questions

- Can one Observation contain many Detections?
- Can a Track represent a person/object without identifying a real individual?
- Is every Event eligible to become an Alert?
- Is Evidence immutable, versioned, or derived?
- Does World State contain predictions, observations, ground truth, or separate views?
- When does a retrieved record become evidence for an Agent answer?

## Expected Artifacts

- Approved operational definitions for terms used in confirmed requirements.
- Explicit distinctions for commonly conflated concepts.
- Links to authoritative schemas, owners, and decision records.

## Document Acceptance Checklist

- [ ] Definitions are consistent across all planning documents.
- [ ] Privacy-sensitive identity concepts are explicit.
- [ ] Retrieval is not defined as synonymous with RAG.
- [ ] Digital Twin is not reduced to a disconnected 3D model.
- [ ] Unresolved semantic boundaries remain `OPEN`.
