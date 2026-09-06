# Spatial Model Specification Worksheet

Document status: `PROPOSED` template

## Purpose

Answer: **How is the physical world represented, versioned, and mapped to
observations and system entities?** The existing Blender resource must be
inspected before its properties are recorded as facts.

## Spatial Model Purpose

- Which approved use cases require spatial information?
- What is the minimum spatial granularity for the first prototype?
- Which component consumes each spatial artifact?

Purpose statement: `TODO` (`OPEN`)

## Blender Resource Inventory

| Item ID | Object / collection | Type | Intended meaning | Existing annotation | Export needed | Verified by | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SP-INV-xxx | TODO after inspection | TODO | TODO | TODO | TODO | TODO | OPEN |

Inspection record:

| Field | Value |
| --- | --- |
| File/version inspected | TODO |
| Inspector | TODO |
| Date | TODO |
| Read-only backup/reference | TODO |
| Known limitations | TODO |

## Coordinate System

| Question | Decision / evidence | Status |
| --- | --- | --- |
| Which coordinate reference is authoritative? | TODO | OPEN |
| Is it local, building-relative, geographic, or another system? | TODO | OPEN |
| How are transforms represented and versioned? | TODO | OPEN |

## Unit / Scale

- Blender scene unit: `TODO after inspection`.
- Physical unit and scale factor: `TODO after verification`.
- Independent scale validation method: `TODO`.
- Tolerance: `TODO`.

## Origin

- Origin definition and physical reference: `TODO`.
- How can the origin be recovered after export? `TODO`.
- Who may change it and what must be revalidated? `TODO`.

## Axis Convention

| Context | Handedness | Up | Forward | Transform to canonical | Status |
| --- | --- | --- | --- | --- | --- |
| Blender source | TODO | TODO | TODO | TODO | OPEN |
| Export format | TODO | TODO | TODO | TODO | OPEN |
| Application / evaluator | TODO | TODO | TODO | TODO | OPEN |

## Environment Geometry

- Which geometry is semantically or visually required?
- Which objects are decorative, collision-relevant, occluding, or sensitive?
- What simplification and export checks are allowed?
- How are geometry versions identified?

## Semantic Zones

| Zone ID | Name | Meaning | Boundary representation | Parent / adjacency | Source | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

## Zone IDs

- Namespace and uniqueness boundary: `TODO`.
- Stability across model revisions: `TODO`.
- Rename, split, merge, and deletion rules: `TODO`.
- Human-readable label versus machine identifier: `TODO`.

## Camera Model

- What does a camera entity represent: physical device, stream, calibration, or view?
- Which camera properties are authoritative in Blender versus external metadata?
- How are camera and stream versions related?

## Camera IDs

| Camera ID | Blender object | Physical/source reference | Stream reference | Verified | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Position / Rotation

| Camera ID | Position | Rotation convention | Coordinate reference | Measurement source | Uncertainty | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

## FOV

| Camera ID | Horizontal FOV | Vertical FOV | Intrinsics / derivation | Verified against | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Camera Coverage

- Is coverage geometric, observed, manually annotated, or empirically measured?
- How are blind spots, occlusion, uncertainty, and dynamic changes represented?
- Which coverage result is suitable for evaluation?

## Camera-to-Zone Mapping

| Camera ID | Zone ID | Relationship | Confidence / evidence | Effective version | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | Observes / located-in / TODO | TODO | TODO | OPEN |

## Observation-to-Zone Mapping

| Mapping input | Method | Output | Unknown / boundary behavior | Evaluation evidence | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

`PROPOSED` MVP candidate: Observation -> Camera -> Zone. Do not treat precise
pixel-to-3D localization as required without an approved use case.

## Physical-to-Digital Mapping

| Physical concept | Digital entity | Identifier link | Transform / mapping | Source of truth | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Spatial Ground Truth

- What is annotated: camera, zone, point, region, path, or relationship?
- What precision and uncertainty are required?
- How is ground truth linked to environment and camera versions?
- How are disputed boundary cases adjudicated?

## Spatial Evaluation

| Capability | Ground truth | Prediction | Match / tolerance | Failure categories | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

## Export Format

Candidate outputs, not confirmed requirements. Before adding any output to Git,
apply
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md);
a filename or export format alone never establishes that an asset is safe.

| Path | Intended role | Consumer | Required fields / checks | Initial repository class | Status |
| --- | --- | --- | --- | --- | --- |
| `data/environment/building.glb` | Exported environment geometry | TODO | Sanitization, real-site sensitivity, rights, size | REVIEW_REQUIRED | PROPOSED |
| `data/environment/environment.json` | Environment metadata | TODO | Sensitive layout/security content review | REVIEW_REQUIRED | PROPOSED |
| `data/environment/zones.json` | Machine-readable zones | TODO | Real-site/restricted-area content review | REVIEW_REQUIRED | PROPOSED |
| `data/environment/cameras.json` | Machine-readable cameras/calibration | TODO | Camera placement and infrastructure review | REVIEW_REQUIRED | PROPOSED |

## Machine-Readable Metadata

| Concept | Required fields | Schema owner | Version link | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Environment | TODO | TODO | TODO | TODO | OPEN |
| Zone | TODO | TODO | TODO | TODO | OPEN |
| Camera | TODO | TODO | TODO | TODO | OPEN |
| Transform | TODO | TODO | TODO | TODO | OPEN |

## Visualization Mapping

- Which stored entities appear in the Digital Twin?
- How are time, coordinates, zone labels, evidence, and selection synchronized?
- What happens when spatial data is missing or stale?
- Which visualization behavior is representational versus authoritative?

## Known Limitations

| Limitation | Affected capability | Workaround | Revisit trigger | Status |
| --- | --- | --- | --- | --- |
| TODO after inspection | TODO | TODO | TODO | OPEN |

## Future Precise Localization

Status: `DEFERRED` unless an approved requirement changes it.

- What use case would justify pixel-to-world or multi-camera localization?
- Which calibration, synchronization, depth, or ground truth would be required?
- What accuracy would matter operationally?

## Open Questions

- What does the Blender model actually contain and which parts are sensitive?
- Which coordinate system and metadata source are authoritative?
- Is zone-level mapping sufficient for the first prototype?
- How are spatial revisions propagated to datasets and evaluations?

## Expected Artifacts

- Reviewed Blender/environment inventory.
- Approved coordinate, unit, axis, ID, and version conventions.
- Camera/zone mapping with evidence and uncertainty.
- Machine-readable export contract.
- Spatial ground-truth and evaluation plan.

## Document Acceptance Checklist

- [ ] No Blender property is claimed without inspection evidence.
- [ ] Coordinate and camera conventions are explicit and testable.
- [ ] Minimum spatial granularity is tied to an approved use case.
- [ ] Exported metadata preserves IDs, version, and provenance.
- [ ] Every spatial artifact has an approved repository classification.
- [ ] Sensitive real-site assets remain `PRIVATE_ONLY`.
