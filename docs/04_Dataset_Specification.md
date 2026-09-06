# Dataset Specification Worksheet

Document status: `PROPOSED` template

## Purpose

Answer: **What data and ground truth must exist for the approved evaluation
framework to work?** Do not invent dataset size, scenario counts, or split
ratios.

`PROPOSED` planning sequence:

```text
Evaluation Requirement -> Scenario -> Required Ground Truth
-> Data Collection -> Annotation -> Benchmark
```

## Dataset Purpose

- Which requirement and evaluation question does this dataset support?
- Is it for development, benchmarking, demonstration, or regression testing?
- What decisions must its results enable?

Purpose statement: `TODO` (`OPEN`)

## Dataset Scope

| Layer / capability | Included? | Why | Required ground truth | Status |
| --- | --- | --- | --- | --- |
| Object / perception | TODO | TODO | Class, bounding box, TODO | OPEN |
| Tracking | TODO | TODO | Identity across frames, TODO | OPEN |
| Spatial | TODO | TODO | Camera, zone, location, TODO | OPEN |
| Event | TODO | TODO | Type, interval, entities, location, TODO | OPEN |
| Retrieval | TODO | TODO | Request, filters, source, records/evidence | OPEN |
| Agent | TODO | TODO | Intent, parameters, tool/evidence/answer rubric | OPEN |

## Data Sources

| Source ID | Description | Owner | Rights / consent | Sensitivity | Format | Availability | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-SRC-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

## Scenario Definition

Define what makes two scenarios meaningfully different for evaluation: `TODO`.

| Scenario ID | Description | Lighting | Occlusion | Actors | Expected Event | Required Annotation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-SC-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

## Scenario Matrix

| Factor | Values to evaluate | Why | Coverage rule | Status |
| --- | --- | --- | --- | --- |
| Lighting | TODO | TODO | TODO | OPEN |
| Occlusion | TODO | TODO | TODO | OPEN |
| Distance | TODO | TODO | TODO | OPEN |
| Viewpoint | TODO | TODO | TODO | OPEN |
| Crowd density | TODO | TODO | TODO | OPEN |

Add factors only when tied to an approved use case, failure risk, or metric.

## Video Metadata

| Field | Type / format | Required? | Source | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Video ID | TODO | TODO | TODO | TODO | OPEN |
| Timestamp / time base | TODO | TODO | TODO | TODO | OPEN |
| Frame rate / dimensions | TODO | TODO | TODO | TODO | OPEN |
| Camera ID | TODO | TODO | TODO | TODO | OPEN |
| Scenario ID | TODO | TODO | TODO | TODO | OPEN |

## Camera Metadata

| Field | Required? | Source | Spatial reference | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Camera ID | TODO | TODO | TODO | TODO | OPEN |
| Position / rotation | TODO | TODO | TODO | TODO | OPEN |
| FOV / intrinsics | TODO | TODO | TODO | TODO | OPEN |
| Zone coverage | TODO | TODO | TODO | TODO | OPEN |

Align approved fields with `05_Spatial_Model_Specification.md`.

## Environmental Conditions

| Condition | Representation | Annotation method | Unknown handling | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

## Object Annotation

- Class vocabulary and inclusion/exclusion rules: `TODO`.
- Bounding-box format and coordinate convention: `TODO`.
- Occluded/truncated/ambiguous object handling: `TODO`.
- Quality-control sample and reviewer process: `TODO`.

## Tracking Annotation

- Identity scope across frames, cameras, and interruptions: `TODO`.
- Entry/exit, occlusion, merge/split, and re-identification rules: `TODO`.
- Relationship to object/person semantics: `TODO`.

## Spatial Annotation

- Required granularity: Camera / Zone / coordinates / TODO (`OPEN`).
- Boundary and unknown-location rules: `TODO`.
- Spatial model version reference: `TODO`.

## Event Annotation

| Field | Definition needed | Ambiguity rule | Status |
| --- | --- | --- | --- |
| Event type | TODO | TODO | OPEN |
| Start / end | TODO | TODO | OPEN |
| Involved entities | TODO | TODO | OPEN |
| Location | TODO | TODO | OPEN |
| Supporting evidence | TODO | TODO | OPEN |

## Retrieval Query Ground Truth

| Query ID | Natural-language need | Expected request type | Expected filters | Expected source | Expected records / evidence | Empty / ambiguity expectation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RET-Q-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

Questions:

- Are expected records exact, set-based, ordered, or relevance-graded?
- Which source snapshot/version makes the expected result reproducible?
- How are temporal and spatial boundary cases represented?
- What constitutes correct provenance and evidence completeness?

## Agent Query Ground Truth

| Query ID | Expected intent | Expected parameters | Allowed tool(s) | Required evidence | Answer rubric | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AGENT-Q-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Keep the expected Agent request separate from expected Retrieval execution so
failures can be attributed correctly.

## Dataset Splits

| Split | Purpose | Grouping / leakage boundary | Selection rule | Size | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO; do not invent | OPEN |

## Benchmark Set

| Benchmark ID | Dataset version | Included scenarios | Ground-truth layers | Evaluation version | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Versioning

- Dataset identifier format: `TODO`.
- Change log and immutability rules: `TODO`.
- Annotation schema compatibility: `TODO`.
- Benchmark freeze and supersession process: `TODO`.

## Annotation Quality Control

| Check | Sampling / coverage | Acceptance rule | Reviewer | Escalation | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Privacy / Sensitive Data

- What personal or site-sensitive information may be present?
- What consent, legal, minimization, access, retention, and deletion rules apply?
- What transformations are required before a sample can be public?
- Who approves a release?

## Data Storage Boundary

The authoritative classification rules are in
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md).
Do not duplicate or weaken them here.

| Dataset artifact | Initial classification | Reason / evidence | Reviewer | Final classification | Status |
| --- | --- | --- | --- | --- | --- |
| Raw surveillance media | PRIVATE_ONLY | Real surveillance/site content | Not publishable | PRIVATE_ONLY | CONFIRMED |
| Full real Ground Truth dataset | PRIVATE_ONLY by default | People, tracks, times, cameras, locations, or events may be sensitive | TODO if an exception is proposed | TODO | CONFIRMED policy; artifact review OPEN |
| Dataset/annotation schemas | PUBLIC_ALLOWED when they contain structure only | Must contain no real records or secrets | TODO | TODO | CONFIRMED policy; artifact review OPEN |
| Synthetic or sanitized sample | REVIEW_REQUIRED until reviewed | Sanitization, rights, and publication intent must be verified | TODO | TODO | OPEN |
| Aggregate evaluation summary | REVIEW_REQUIRED until reviewed | Must exclude sensitive raw evidence | TODO | TODO | OPEN |

Secrets, private storage URLs, and identifiable or sensitive records must not be
committed.

## Public Sample Data

| Sample | Purpose | Sanitization | License / consent | Reviewer | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

Every candidate sample must record whether it is synthetic, anonymized, or
sanitized and must pass the publication checklist in the authoritative policy.

## Private Dataset

| Collection | Access group | Storage location class | Retention | Audit | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | Do not place private URL here | TODO | TODO | OPEN |

## Coverage Criteria

| Requirement / risk | Required scenario coverage | Evidence | Gap | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

## Open Questions

- Which annotation layers belong to the MVP benchmark?
- What data already exists and can legally be used?
- What grouping prevents train/validation/test leakage?
- What is the smallest dataset that can answer the first evaluation question?
- Which samples can be safely published?

## Expected Artifacts

- Approved data-source inventory and access boundary.
- Scenario and coverage matrices tied to evaluation needs.
- Versioned annotation schemas and guidelines.
- Retrieval and Agent query ground truth separated by layer.
- Benchmark manifest and annotation quality report.

## Document Acceptance Checklist

- [ ] Every included annotation layer supports an approved evaluation need.
- [ ] No dataset size, scenario count, or split ratio was invented.
- [ ] Retrieval and Agent ground truth are represented explicitly.
- [ ] Sensitive data and public samples have distinct controls.
- [ ] Dataset versions can be linked to reproducible evaluation runs.
