# School v1 Stable-ID Candidate Policy and Readiness Report

Status: `PROPOSED` / `REVIEW_REQUIRED`

Decision gate: **BLOCKED before working-copy creation and registry generation**

This is a candidate-policy report for human approval. It is not an
authoritative registry, does not assign IDs, and does not authorize writing any
Blender custom property.

## Evidence and Current State

| Field | Value |
| --- | --- |
| Branch | `codex/blender-inspection-v1` |
| Scene ID / version | `school` / `v1` |
| Immutable source | `blender/source/school_v1.blend` |
| Source SHA-256 | `cbfef8c84295253323890be5d9ffae186c46481f9dde8a6509ce897c49a34fa1` |
| Inventory objects | 2,778 |
| Existing valid IDs | 0 |
| Existing duplicate IDs | 0 |
| Existing semantic annotations | 0 |
| Missing render resources | 5; all affect render-enabled objects |
| Working copy | Not created |
| Proposed registry | Not created |
| Dry runs | Not executed |

The current repository documents leave namespace conventions, schema
ownership/compatibility, authoritative spatial metadata, and the specific
Blender metadata authority `OPEN` under OQ-004 and OQ-015. The preceding
metadata-governance report also requires explicit approval before
implementation.

## Candidate Namespace

The following exact value is proposed, not approved:

| Field | Candidate value |
| --- | --- |
| ID format | `amidst:school:object:<uuid-v5>` |
| Parent namespace | RFC UUID URL namespace `6ba7b811-9dad-11d1-80b4-00c04fd430c8` |
| Namespace name | `https://github.com/polalabear/amidst#scene/school/object` |
| Derived school-object namespace UUID | `1601a7c1-19ac-555d-9962-05e4503ac6bd` |
| Derivation | UUIDv5(parent namespace, UTF-8 namespace name) |

Once approved, the derived UUID is stored as a literal immutable policy value;
it must not change if the repository URL later changes.

## Candidate Fingerprint Algorithm v1

Policy identifier: `amidst.school.object-id/1.0.0-candidate`

### Eligibility

Candidate scope is every object in `bpy.context.scene.objects`. The observed
v1 types are `MESH`, `ARMATURE`, `CURVE`, `EMPTY`, `CAMERA`, and `FONT`.
Any other type is unsupported until its signature rule is reviewed. Excluding
helper objects instead is an explicit approval choice; the implementation must
not decide semantic importance by name or geometry.

### Canonical identity record

For each object, build this logical record without using traversal order:

```text
policy_id
scene_id
first_seen_scene_version
first_seen_source_sha256
object_type
collection_paths
parent_identity_fingerprint or null
data_signature
matrix_world
dimensions
material_signatures
```

Rules:

1. Object names are locators for reports only and are excluded from the
   identity fingerprint. Data-block and collection names may be supporting
   inputs but are never sufficient identity evidence by themselves.
2. Collection paths use normalized collection display names along each
   structural parent-child path. Normalize strings to Unicode NFC, encode as
   UTF-8, sort paths by encoded byte order, and retain all paths for
   multiply-linked collections.
3. Encode every finite Blender float as its lowercase Python `float.hex()`
   string. Reject NaN and infinity. Preserve matrix row/column order and vector
   component order explicitly.
4. Encode integers and booleans as JSON numbers/booleans; encode absent values
   as JSON `null`. Do not coerce missing data to zero or an empty string.
5. Serialize with JSON object keys sorted by Unicode code point, no
   insignificant whitespace, UTF-8 encoding, and no trailing newline.
6. Compute `identity_fingerprint` as lowercase SHA-256 hex over those bytes.
7. Compute the object UUID as UUIDv5 of the approved school-object namespace
   and the ASCII name
   `amidst.school.object-id/1.0.0:<identity_fingerprint>`.
8. Form `instance_id` as `amidst:school:object:<object-uuid>`.

### Type-specific data signatures

All signatures use local-space source data and canonical encoding above:

| Type | Candidate data signature |
| --- | --- |
| `MESH` | Vertex coordinates, edge vertex indices, polygon loop vertex indices, polygon material indices, and topology counts. |
| `ARMATURE` | Bone structure, parent relationship, head/tail coordinates, roll, connected/deform flags; bone names excluded from the fingerprint. |
| `CURVE` | Curve dimensions/resolution and ordered spline type, cyclic flags, control-point coordinates/weights/handles. |
| `FONT` | Text body bytes plus text-geometry/layout settings; font display name excluded. |
| `EMPTY` | Empty display type/size and referenced data signature when present; otherwise canonical null data. |
| `CAMERA` | Projection type, lens/FOV inputs, sensor fit/size, shifts, clipping values, and orthographic scale where applicable. |

Material signatures hash material/node content and referenced resource content
hashes when available; material display names are excluded. A missing external
resource is represented explicitly as missing with its normalized source-stored
Blender path (for example, a `//` relative path), never a resolved host-absolute
path, and must not be treated as empty content.

### Hierarchy and ambiguity

- Compute parent fingerprints from roots toward leaves; hierarchy cycles are
  fatal.
- Two objects with the same identity fingerprint are an ambiguous identity
  group. Do not use object names, traversal position, or random suffixes to
  separate them.
- Ambiguous objects receive no candidate ID until a human supplies a stable,
  non-semantic disambiguation record.
- A UUID collision between different fingerprints is fatal and preserved in
  the collision report.
- Once issued, an ID is an identity token, not a content hash. Renames,
  transform changes, material changes, and later fingerprint changes do not
  replace it; future versions match the authoritative registry first.

### Registry lifecycle candidate

- Registry location: `data/annotations/instance_registry/school.json`.
- The sidecar registry is authoritative; Blender `instance_id` properties are
  mirrors.
- Existing valid IDs are preserved after registry validation.
- Removed entities become immutable tombstones and their IDs are never reused.
- New objects are matched against prior records before first-seen assignment.
- Rename history is recorded as locator evidence without changing identity.
- Split, merge, duplicate-ID, and conflicting-match cases stop migration and
  require explicit review.
- Registry serialization uses the same canonical JSON rules, with records
  ordered by `instance_id`; timestamps are excluded from deterministic content
  or stored in a separate run envelope.

The registry path, authority, schema, lifecycle fields, and classification all
remain approval decisions.

## Approval Choices Required

Human approval must explicitly confirm or replace each item:

1. Namespace name and literal namespace UUID.
2. Policy identifier and canonical JSON/float/string encoding.
3. Eligible object scope and handling of helper objects.
4. Type-specific data signatures and whether material signatures participate.
5. Exact ambiguity rule and human disambiguation-record format.
6. Sidecar registry path, authority, schema, lifecycle, and publication class.
7. Whether the five missing material resources may participate only as
   explicit missing references during metadata-only ID preparation.

Approval should be recorded by resolving/refining OQ-004 and OQ-015 and by
adding the corresponding ADR/specification changes. This report must not be
treated as approval by itself.

## Phase Readiness

| Phase | Result | Reason |
| --- | --- | --- |
| 1 — Record approved policy | `REVIEW_REQUIRED` | Exact candidate now exists, but no human approval is recorded. |
| 2 — Create working copy | Not started | Blocked by Phase 1 gate. |
| 3 — Implement dry run | Not started | Fingerprint algorithm is not authoritative. |
| 4 — Create registry | Not started | Registry authority/schema remain unresolved. |
| 5 — Assignment reports | Not started | No approved algorithm or registry output exists. |
| 6 — Determinism test | Not started | No dry-run implementation exists. |
| Persistent property writing | Prohibited | Outside this task and blocked by unresolved governance. |

## Current Final-Report Values

| Requested result | Current value |
| --- | --- |
| Source checksum | `cbfef8c84295253323890be5d9ffae186c46481f9dde8a6509ce897c49a34fa1` |
| Working-copy checksum | Not available; copy not created |
| Proposed ID count | 0; assignment not run |
| Duplicate/conflict count | Not evaluated; assignment not run |
| Manual-review count | Not evaluated; assignment not run |
| Deterministic rerun result | Not run |
| Registry location | Candidate only: `data/annotations/instance_registry/school.json` |
| Safe to persist custom properties | **No** |

## Exact Next Step After Approval

Update the authoritative spatial/data-format documentation and ADR with the
approved values, then create
`blender/working/school_v1_working.blend` byte-for-byte without overwrite,
record and compare both checksums, and only then implement the dry-run script
and candidate registry. Do not save Blender custom properties during that
stage.
