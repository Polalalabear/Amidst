# School v1 Metadata Governance Proposal

Status: `PROPOSED` — requires human approval before implementation

Repository classification: `REVIEW_REQUIRED`

Scope: stable object identity, minimum semantic custom properties, scene-version
migration, and missing-resource gating for `blender/source/school_v1.blend`.
This report is a review artifact, not an authoritative schema. It does not
authorize editing a `.blend` file, assigning an ID, or assigning a category.

## Evidence Baseline

- Scene: `school`, version `v1`, source SHA-256
  `cbfef8c84295253323890be5d9ffae186c46481f9dde8a6509ce897c49a34fa1`.
- Inventory: 2,778 scene objects; no `instance_id` values.
- Semantic fields: no existing `category`, `semantic_category`,
  `annotation_status`, `annotation_source`, or `annotation_version` values.
- Other custom properties exist on 553 objects but are not treated as trusted
  semantic metadata.
- Validation: no duplicate IDs and no structural hierarchy issue can yet be
  evaluated against an identity registry because no registry exists.

## Recommended Stable ID Policy

All rules in this section are `PROPOSED`.

### Format and namespace

- Use an opaque string with the format
  `amidst:school:object:<lowercase-hyphenated-uuid-v5>`.
- Validate it against
  `^amidst:school:object:[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`.
- `amidst` is the project namespace, `school` is the stable scene namespace,
  and `object` is the entity kind. The scene version is deliberately excluded
  so the same entity keeps the same ID across versions.
- Store one approved UUID namespace value for school objects in the scene
  manifest and identity registry. The UUID namespace value itself remains
  `OPEN` until human approval.

### Deterministic first assignment

For a fixed source checksum and approved policy version, assignment must be
repeatable:

1. Build a canonical first-seen record from objective evidence: scene ID,
   first-seen version, source checksum, object type, all collection paths,
   parent evidence, data-block structural fingerprint, exact transform matrix,
   dimensions, and material-slot references.
2. The Blender object name may be included only as the final deterministic
   tie-breaker. It must never be the sole seed or persistent identity.
3. Serialize the record as canonical UTF-8 JSON with sorted keys and normalized
   numeric representation, then hash it with SHA-256.
4. Generate UUIDv5 from the approved school-object namespace UUID and the
   canonical-record digest.
5. If two objects remain indistinguishable or collide, produce a conflict
   report and require human resolution. Do not silently add a random suffix.

The canonicalization algorithm and fingerprint inputs must be versioned. A
change to that algorithm does not rewrite already-issued IDs.

### Registry and uniqueness

- Use a versioned sidecar identity registry as the audit authority; mirror its
  `instance_id` into the working Blender object's custom property.
- Proposed registry path:
  `data/annotations/school_instance_registry.json` (`REVIEW_REQUIRED`).
- Each registry record should retain `instance_id`, lifecycle status,
  first/last-seen scene versions, version-specific object locator, objective
  fingerprints, aliases, assignment policy version, and review provenance.
- IDs must be unique across both active and retired registry records. Retired
  IDs are never reused.
- Validation must reject a missing, malformed, duplicated, or conflicting ID.
  Any such result blocks annotation export and dataset generation.

### Lifecycle rules

| Case | Proposed behavior |
| --- | --- |
| Rename | Preserve `instance_id`; append the new display name to version history. |
| Transform/material change | Preserve `instance_id`; record changed evidence for the new version. |
| Deleted object | Mark the registry record `retired` with `last_seen_version`; never recycle the ID. |
| New object | Match against prior identities first; if unmatched, issue a deterministic new ID using its first-seen version and source checksum. |
| Duplicate ID | Stop migration and all downstream export; preserve evidence and require human resolution. |
| Conflicting evidence | Do not overwrite either record; mark the migration mapping `needs_review`. |
| Split or merge | Never infer continuity automatically; require a human decision and explicit predecessor/successor references. |

### Migration from v1 to later versions

1. Verify both scene files against immutable manifest checksums.
2. Prefer an existing valid `instance_id` match.
3. Otherwise compare the prior registry using multiple objective signals;
   names are supporting evidence only.
4. Classify results as exact carry-forward, proposed match, new object, retired
   candidate, or conflict.
5. Require review for every proposed/ambiguous match and every split/merge.
6. Produce a migration report before writing any new scene or registry version.
7. After approval, update only a working/output copy and append a new registry
   version; never rewrite historical registry entries or source scenes.

Recommended initial scope is all objects in `bpy.context.scene.objects`, because
selecting only “important” objects would currently require unconfirmed semantic
judgment. Whether helper objects should instead be excluded remains an approval
decision.

## Minimum Semantic Custom-Property Schema

The identity property may exist before semantic annotation. Once any semantic
property is written, the four semantic fields below must be written and
validated as one bundle.

| Property | Type | Proposed rule |
| --- | --- | --- |
| `instance_id` | string | Required stable ID governed by the policy above. Never derived from object name alone. |
| `category` | string | Exact member of the approved, versioned category vocabulary. `Unknown` is the only value authorized by the current uncertainty rule without a confirmed vocabulary. |
| `annotation_status` | string enum | Minimum values: `needs_review`, `verified`. Only authorized human review or explicitly trusted metadata may produce `verified`. |
| `annotation_source` | string reference | Non-empty provenance reference such as `human_review:<record-id>`. Additional source kinds require approval before use. |
| `annotation_version` | string | Version of the approved semantic policy/vocabulary bundle used for the value; proposed form `school-semantics@<semver>`. |

Required invariants:

- If semantic identity is uncertain, set exactly `category = "Unknown"` and
  `annotation_status = "needs_review"`.
- `category = "Unknown"` must not be marked `verified`.
- A non-`Unknown` category must come from the vocabulary version referenced by
  `annotation_version`.
- `verified` requires traceable `annotation_source` evidence.
- Missing semantic properties mean “not annotated”; they must not be converted
  silently to a category.
- Migration preserves the original annotation source and version unless a new
  review explicitly changes the annotation.

### Minimum vocabulary governance

- Do not infer categories from geometry, object names, collection names, or
  materials.
- Keep `Unknown` as the required fallback.
- Add a category only when it supports an approved evaluation task and has a
  written inclusion/exclusion definition plus examples and ambiguity handling.
- Version the vocabulary; do not silently rename or reinterpret a value.
- Record aliases separately from canonical categories.
- Category additions, merges, splits, and deprecations require human approval
  and a migration impact review.

No Chair/Table/Door/Room ontology is proposed by this report.

## Missing-Resource Assessment

All five references are `FILE` image datablocks, are not packed, are used by a
material node, and reach render-enabled mesh objects. Counts below may overlap
because an object can use more than one affected material.

| Image datablock | Referenced filepath | Material datablock | Render-enabled objects | Affects render output | Block image dataset generation |
| --- | --- | --- | ---: | --- | --- |
| `__Brick-antique_.jpg` | `//../../../../../school/model/__Brick-antique_.jpg` | `__Brick-antique_` | 3 | Yes | Yes |
| `__Brick-antique__1.jpg` | `//../../../../../school/model/__Brick-antique__1.jpg` | `__Brick-antique__1` | 247 | Yes | Yes |
| `__Glass_Sky_Reflection_.jpg` | `//../../../../../school/model/__Glass_Sky_Reflection_.jpg` | `__Glass_Sky_Reflection_` | 568 | Yes | Yes |
| `__Wood-cherry_1.jpg` | `//../../../../../school/model/__Wood-cherry_1.jpg` | `__Wood-cherry_1` | 744 | Yes | Yes |
| `__Wood-cherry_1_0.jpg` | `//../../../../../school/model/__Wood-cherry_1_0.jpg` | `__Wood-cherry_1_0` | 670 | Yes | Yes |

The Blender datablock user count is 1 for each image. No world, light, or scene
compositor usage was detected. Detailed material nodes and representative
objects are preserved in `school_v1_validation.json`.

Recommendation: block all camera-image dataset generation until the exact
resources are restored and hashed, or a human approves explicit replacements;
then require a zero-missing-resource preflight and a reviewed test render.
Restricting only affected views would require additional visibility evidence
and is not the recommended minimum. This block does not prevent identity-policy
review or other read-only metadata preparation.

## Documentation Updates Needed After Approval

| Document | Required authoritative update |
| --- | --- |
| `docs/05_Spatial_Model_Specification.md` | Confirm ID namespace, lifecycle, registry authority, assignment scope, and cross-version migration. |
| `docs/09_Data_Types_and_Exchange_Formats.md` | Confirm custom-property field semantics, policy/vocabulary versioning, provenance, and compatibility rules. |
| `docs/04_Dataset_Specification.md` | Confirm missing-resource/render preflight as a dataset validity gate and record required scene/registry versions. |
| `docs/07_Technical_Decisions.md` | Record the approved deterministic-ID/sidecar-registry trade-off and alternatives in an ADR. |
| `docs/open_questions.md` | Resolve or refine existing OQ-004 and OQ-015; resolve OQ-012 before any `REVIEW_REQUIRED` publication. Do not add a duplicate question. |
| `blender/scene_manifest.json` | Record the approved namespace UUID, ID-policy version, registry reference, and resource-resolution status. |

## Human Approvals Required

1. ID format and the permanent school-object UUID namespace value.
2. Canonical fingerprint/collision algorithm and assignment scope.
3. Sidecar registry as identity authority and its publication classification.
4. Semantic status values, `annotation_source` reference convention, and the
   meaning of `annotation_version`.
5. Initial task-driven category vocabulary beyond `Unknown` and its reviewer.
6. Missing-texture restoration or replacement evidence and render acceptance.
7. Reviewer/approver for `REVIEW_REQUIRED` spatial artifacts (OQ-012).

## Exact Next Step After Approval

Create `blender/working/school_v1_working.blend` as a byte-for-byte copy of the
verified source, verify both checksums, add the approved policy version and
namespace to the manifest, and implement a dry-run ID-assignment script that
produces a proposed registry plus collision report without saving the working
scene. Review that mapping before any custom property is written.
