# Evaluation Framework Worksheet

Document status: `PROPOSED` template

## Purpose

Answer: **What does correctness mean, how can it be measured, and where did a
failure originate?** Metrics listed here are candidates until approved against
a defined benchmark.

## Evaluation Philosophy

`PROPOSED` cycle:

```text
Build Small -> Evaluate -> Diagnose -> Improve -> Expand -> Evaluate Again
```

The first useful prototype foundation is proposed to include a dataset, ground
truth, baseline system, evaluation engine, metrics, and error analysis. Ground
truth alone is not a complete prototype.

## Evaluation Scope

| Capability | In MVP evaluation? | Reason | Owner | Status |
| --- | --- | --- | --- | --- |
| Perception | TODO | TODO | TODO | OPEN |
| Tracking | TODO | TODO | TODO | OPEN |
| Spatial mapping | TODO | TODO | TODO | OPEN |
| Event understanding | TODO | TODO | TODO | OPEN |
| Retrieval | TODO | TODO | TODO | OPEN |
| Agent | TODO | TODO | TODO | OPEN |
| End-to-end | TODO | TODO | TODO | OPEN |

## Evaluation Layers

| Layer | Ground Truth | Prediction | Metric | Failure Type | Status |
| --- | --- | --- | --- | --- | --- |
| Perception | Class, bounding box | Detection | Precision, Recall, F1, mAP candidates | Misclassification, localization, miss | PROPOSED |
| Tracking | Identity across frames | Track sequence | IDF1, ID switches, fragmentation, HOTA/MOTA candidates | Identity or continuity error | PROPOSED |
| Spatial | Camera, zone, location | Spatial association | TODO | Wrong/unknown spatial mapping | OPEN |
| Event | Type, start/end, entities, location | Event | Precision, Recall, F1, false alarm, miss, latency candidates | Event classification/timing/association | PROPOSED |
| Retrieval | Request, filters, source, expected records/evidence | Retrieved result | Mechanism-specific correctness | Filter/source/result/provenance error | PROPOSED |
| Agent | Intent, parameters, tool, evidence-supported answer | Tool call and answer | TODO | Intent/tool/grounding/answer error | OPEN |
| End-to-end | Approved scenario outcome | User-visible result | TODO | Cross-layer failure | OPEN |

## Ground Truth Definition

| GT ID | Entity / behavior | Annotation unit | Required fields | Source | Quality check | Status |
| --- | --- | --- | --- | --- | --- | --- |
| EV-GT-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Questions:

- Who creates, reviews, and approves each ground-truth layer?
- How are ambiguity, uncertainty, disagreement, and unknown values represented?
- Which version of ground truth is authoritative for a benchmark run?

## Prediction Definition

| Prediction type | Required fields | Confidence | Version metadata | Matching rule | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Perception Evaluation

- Which classes and bounding-box conventions are in scope?
- What matching thresholds and averaging conventions apply?
- How will performance be sliced by lighting, occlusion, distance, viewpoint,
  and crowd density?
- Which candidate metrics are necessary for the approved use case?

## Tracking Evaluation

- What defines a ground-truth identity and a valid association?
- How are entry, exit, occlusion, and reappearance handled?
- Are IDF1, ID switches, fragmentation, HOTA, or MOTA appropriate for the benchmark?
- Which errors matter most to downstream events and retrieval?

## Spatial Evaluation

- Is the target Camera-to-Zone, Observation-to-Zone, or precise 3D location?
- What tolerance, unknown-zone behavior, and boundary convention apply?
- How are camera calibration and environment versions tied to a result?

## Event Evaluation

- How are event type, interval overlap, participants, and location matched?
- What counts as a false alarm, missed event, duplicate, or late detection?
- Which candidate metrics and latency definitions match operational needs?

## Retrieval Evaluation

Ground-truth form to review:

```text
Query / Retrieval Request -> Expected Filters -> Expected Data Source
-> Expected Records / Evidence
```

| Query ID | Mechanism | Request | Expected source | Expected result | Required evidence | Evaluation rule | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RET-EV-xxx | Structured / semantic / hybrid / TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

Evaluate where applicable:

- request/filter correctness;
- temporal and spatial constraint correctness;
- evidence completeness and relevance;
- provenance correctness;
- deterministic empty-result and ambiguity handling.

Do not use Recall@K, MRR, or similar information-retrieval metrics unless the
retrieval mechanism and benchmark justify them. Structured queries and semantic
retrieval may require different protocols.

## Agent Evaluation

| Dimension | Ground truth / rubric | Observed artifact | Failure boundary | Status |
| --- | --- | --- | --- | --- |
| Intent understanding | TODO | Parsed intent | Agent | OPEN |
| Parameter extraction | TODO | Tool arguments | Agent | OPEN |
| Tool selection | TODO | Tool call | Agent | OPEN |
| Retrieval request correctness | Expected request | Actual request | Agent / tool planning | OPEN |
| Evidence usage / grounding | Approved evidence-to-claim rubric | Answer and citations | Agent reasoning | OPEN |
| Hallucination / answer correctness | TODO | Final answer | Agent reasoning | OPEN |

## End-to-End Evaluation

Flows to test only after their component contracts are defined:

```text
User Query -> Agent -> Retrieval -> World State -> Evidence -> Answer

Physical Event -> Perception -> Tracking -> Spatial -> Event -> Storage
-> Retrieval -> Agent -> User
```

End-to-end results must link to component-level diagnostics; they must not
replace them.

## Scenario-Based Evaluation

| Scenario ID | Capability | Conditions | Expected outcome | Required ground truth | Required slices | Status |
| --- | --- | --- | --- | --- | --- | --- |
| EV-SC-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Potential conditions for review: lighting, occlusion, distance, viewpoint,
crowd density, camera outage, stale data, ambiguous query, and empty result.

## Error Taxonomy

| Error ID | Layer | Definition | Required evidence | Upstream cause possible? | Status |
| --- | --- | --- | --- | --- | --- |
| ERR-PER-xxx | Perception | TODO | Observation, ground truth, detection, versions | TODO | OPEN |
| ERR-TRK-xxx | Tracking | TODO | Detection sequence, track truth/prediction | TODO | OPEN |
| ERR-SP-xxx | Spatial | TODO | Camera/zone metadata and association | TODO | OPEN |
| ERR-EVT-xxx | Event | TODO | Inputs, event truth/prediction | TODO | OPEN |
| ERR-RET-xxx | Retrieval | TODO | Request, source snapshot, result, provenance | TODO | OPEN |
| ERR-AGT-xxx | Agent | TODO | Intent, tool call, evidence, answer | TODO | OPEN |
| ERR-E2E-xxx | End-to-end | TODO | Linked component traces | Yes | OPEN |

## Failure Attribution

| Agent intent/request | Retrieval execution/result | Agent answer | Attribute first to |
| --- | --- | --- | --- |
| Correct | Incorrect | Not evaluated or affected | Retrieval Layer |
| Incorrect | Correct for received request | Not evaluated or affected | Agent / tool planning |
| Correct | Correct | Unsupported or incorrect | Agent grounding / reasoning |

Define how upstream errors are recorded without double-counting downstream
symptoms: `TODO`.

## Benchmark Protocol

| Step | Required input | Procedure | Output | Reproducibility evidence | Status |
| --- | --- | --- | --- | --- | --- |
| 1 | TODO | TODO | TODO | TODO | OPEN |

Specify: eligibility, exclusions, preprocessing, execution order, random seeds,
matching rules, confidence thresholds, repetitions, aggregation, and approval.

## Experiment Reproducibility

| Run ID | Dataset version | Model version | Configuration version | Evaluator version | Environment | Artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO |

### Dataset Version

- Identifier format: `TODO`
- Immutability / change policy: `TODO`

### Model Version

- Identifier and artifact provenance: `TODO`

### Configuration Version

- Captured parameters and secrets boundary: `TODO`

### Evaluator Version

- Code/version compatibility and result migration: `TODO`

## Reporting Format

| Section | Required content | Audience | Status |
| --- | --- | --- | --- |
| Summary | TODO | TODO | OPEN |
| Per-layer results | TODO | TODO | OPEN |
| Scenario slices | TODO | TODO | OPEN |
| Error analysis | TODO | TODO | OPEN |
| Version manifest | TODO | TODO | OPEN |

## Regression Criteria

| Criterion | Baseline | Allowed change | Blocking? | Owner | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Open Questions

- Which layers must the first benchmark evaluate directly?
- Which metrics align with actual prototype decisions?
- What sample or event is the evaluation unit?
- How will ambiguous ground truth be adjudicated?
- Which regressions block expansion or release?

## Expected Artifacts

- Approved ground-truth and prediction contracts.
- Versioned benchmark protocol and test fixtures.
- Per-layer metrics with justified thresholds.
- Error taxonomy and attribution rules.
- Reproducible report format and regression policy.

## Document Acceptance Checklist

- [ ] Every evaluated capability has corresponding ground truth or an approved rubric.
- [ ] Retrieval evaluation is explicit and mechanism-appropriate.
- [ ] Agent failures are distinguishable from Retrieval failures.
- [ ] Scenario slices are derived from approved risks and use cases.
- [ ] Dataset, model, configuration, and evaluator versions are captured.
- [ ] Candidate metrics are not represented as finalized decisions.
