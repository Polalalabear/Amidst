# Codex Handoff File Classification

Checkpoint date: 2026-09-15

This report applies `docs/08_Repository_and_Data_Publication_Policy.md`. The
handoff class answers what to do at this checkpoint; the publication class is
the policy classification. `REVIEW_REQUIRED` files must not be staged or
published until a human reviewer approves their content. At handoff preparation
time, no file had been deleted, staged, committed, or pushed.

Checkpoint publication decision: `APPROVED_FOR_PUBLICATION` on 2026-09-15 for
all 50 current paths in `SHOULD_COMMIT`, `NEEDS_HUMAN_REVIEW`, and
`GENERATED_BUT_PROJECT_RELEVANT`. This scoped human approval satisfies OQ-012
for these exact reviewed versions only. It does not approve later changes or
anything in `SHOULD_REMAIN_LOCAL` or `INVALID/DEPRECATED_ARTIFACT`.

## SHOULD_COMMIT

These are repository-safe source, documentation, schema, or ignore rules after
normal content review. This is a recommendation only; the handoff task did not
stage them.

| Path | Publication class | Reason |
| --- | --- | --- |
| `.gitignore` | `PUBLIC_ALLOWED` | Minimal local-only handoff ignore rule |
| `docs/CODEX_HANDOFF.md` | `PUBLIC_ALLOWED` | Repository-safe reproducibility checkpoint |
| `docs/04_Dataset_Specification.md` | `PUBLIC_ALLOWED` | Confirmed dataset contract documentation |
| `docs/05_Spatial_Model_Specification.md` | `PUBLIC_ALLOWED` | Confirmed scoped spatial/identity documentation |
| `docs/07_Technical_Decisions.md` | `PUBLIC_ALLOWED` | ADR-008 and ADR-009 decision records |
| `docs/09_Data_Types_and_Exchange_Formats.md` | `PUBLIC_ALLOWED` | Scoped exchange-contract documentation |
| `docs/open_questions.md` | `PUBLIC_ALLOWED` | Decision registry with unresolved items explicit |
| `blender/scripts/analyze_id_collisions.py` | `PUBLIC_ALLOWED` | Deterministic Blender inspection/analysis source |
| `blender/scripts/assign_instance_ids.py` | `PUBLIC_ALLOWED` | Stable-ID dry-run assignment source |
| `blender/scripts/audit_missing_render_resources.py` | `PUBLIC_ALLOWED` | Read-only resource-audit source |
| `blender/scripts/compare_id_persistence_inventories.py` | `PUBLIC_ALLOWED` | Identity-persistence comparison source |
| `blender/scripts/create_texture_agnostic_scene.py` | `PUBLIC_ALLOWED` | Prepared bounded derived-scene creator; not executed at checkpoint |
| `blender/scripts/inspect_scene.py` | `PUBLIC_ALLOWED` | Read-only scene inventory source |
| `blender/scripts/persist_instance_ids.py` | `PUBLIC_ALLOWED` | Versioned ID-persistence source |
| `blender/scripts/prepare_identity_overrides.py` | `PUBLIC_ALLOWED` | Disambiguation/bootstrap preparation source |
| `blender/scripts/prepare_semantic_baseline.py` | `PUBLIC_ALLOWED` | Category-agnostic sidecar preparation source |
| `blender/scripts/validate_first_slice_readiness.py` | `PUBLIC_ALLOWED` | Readiness validator source |
| `blender/scripts/validate_scene.py` | `PUBLIC_ALLOWED` | General inspection validator source |
| `blender/scripts/validate_texture_agnostic_scene.py` | `PUBLIC_ALLOWED` | Prepared fresh-process validator; not yet run on a derived scene |
| `data/metadata/first_dataset_slice_metadata_schema_v0_1_0.json` | `PUBLIC_ALLOWED` | Structural JSON Schema, not a populated scene record |
| `data/reports/codex_handoff_file_classification.md` | `PUBLIC_ALLOWED` | Sanitized classification and staging guidance |

## NEEDS_HUMAN_REVIEW

These are authoritative or important project records, but they contain
populated scene-specific identity, configuration, or site evidence. Their
normal policy classification remains `REVIEW_REQUIRED`; the exact versions
below are approved for this checkpoint and should be staged.

| Path | Publication class | Reason |
| --- | --- | --- |
| `blender/scene_manifest.json` | `REVIEW_REQUIRED` | Populated scene/version/checksum record |
| `data/annotations/instance_registry/school.json` | `REVIEW_REQUIRED` | Authoritative populated stable-ID registry |
| `data/annotations/instance_registry/school_v1_disambiguation.json` | `REVIEW_REQUIRED` | Scene-specific identity evidence |
| `data/annotations/instance_registry/school_v1_identity_bootstrap.json` | `REVIEW_REQUIRED` | Scene-specific reviewed bootstrap bindings |
| `data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json` | `REVIEW_REQUIRED` | Populated scene semantic sidecar, even though category-agnostic |
| `data/metadata/first_dataset_slice_tasks_v0_1_0.json` | `REVIEW_REQUIRED` | Populated school_v1 contract explicitly self-classified for review |
| `data/metadata/first_dataset_slice_render_config_v0_1_0.json` | `REVIEW_REQUIRED` | Scene checksum and machine/render provenance |

## GENERATED_BUT_PROJECT_RELEVANT

These files are useful evidence for reproducibility and continuation, but their
scene-specific contents are `REVIEW_REQUIRED`. Human publication review has
approved the exact versions below for this checkpoint, so they should be
staged.

| Path | Publication class | Reason |
| --- | --- | --- |
| `data/reports/school_v1_disambiguation_approval.md` | `REVIEW_REQUIRED` | Approval summary tied to scene identity evidence |
| `data/reports/school_v1_disambiguation_evidence.json` | `REVIEW_REQUIRED` | Detailed object collision evidence |
| `data/reports/school_v1_first_slice_readiness.json` | `REVIEW_REQUIRED` | Latest machine-readable readiness evidence |
| `data/reports/school_v1_first_slice_readiness.md` | `REVIEW_REQUIRED` | Latest human-readable readiness summary |
| `data/reports/school_v1_id_assignment.json` | `REVIEW_REQUIRED` | Populated assignment evidence |
| `data/reports/school_v1_id_assignment.md` | `REVIEW_REQUIRED` | Populated assignment summary |
| `data/reports/school_v1_id_collisions.json` | `REVIEW_REQUIRED` | Detailed collision groups and object locators |
| `data/reports/school_v1_id_determinism.json` | `REVIEW_REQUIRED` | Determinism evidence tied to populated scene |
| `data/reports/school_v1_id_persistence.json` | `REVIEW_REQUIRED` | Persistence evidence with local historical paths |
| `data/reports/school_v1_id_persistence.md` | `REVIEW_REQUIRED` | Persistence summary with local historical paths |
| `data/reports/school_v1_id_scene_comparison.json` | `REVIEW_REQUIRED` | Scene-specific invariant comparison |
| `data/reports/school_v1_ids_validation.json` | `REVIEW_REQUIRED` | Populated Blender validation result |
| `data/reports/school_v1_metadata_governance_proposal.md` | `REVIEW_REQUIRED` | Scene-specific governance analysis |
| `data/reports/school_v1_missing_resource_audit.json` | `REVIEW_REQUIRED` | Material/object usage plus historical absolute paths |
| `data/reports/school_v1_missing_resource_audit.md` | `REVIEW_REQUIRED` | Missing-resource summary |
| `data/reports/school_v1_semantic_baseline.md` | `REVIEW_REQUIRED` | Scene-specific semantic-baseline report |
| `data/reports/school_v1_semantic_coverage.json` | `REVIEW_REQUIRED` | Populated semantic coverage counts |
| `data/reports/school_v1_stable_id_candidate_policy.md` | `REVIEW_REQUIRED` | Scene-specific ID-policy evidence |
| `data/reports/school_v1_validation.json` | `REVIEW_REQUIRED` | Initial scene inventory/validation evidence |
| `data/reports/school_v1_working_copy_provenance.json` | `REVIEW_REQUIRED` | Working-copy checksum/provenance evidence |
| `data/scene_inventory/school_v1_ids_objects.csv` | `REVIEW_REQUIRED` | Detailed populated layout/identity inventory |
| `data/scene_inventory/school_v1_objects.csv` | `REVIEW_REQUIRED` | Detailed populated source-scene inventory |

## SHOULD_REMAIN_LOCAL

| Path | Publication class | Reason |
| --- | --- | --- |
| `local/CODEX_PRIVATE_HANDOFF.md` | `PRIVATE_ONLY` | Machine/account-specific continuation context; ignored by Git |
| `blender/source/school_v1.blend` | `PRIVATE_ONLY` | Immutable raw spatial source asset |
| `blender/working/school_v1_working.blend` | `PRIVATE_ONLY` | Mutable/derived working asset with persisted IDs |
| `blender/output/school_v1_ids_policy_1_0_1_r2.blend` | `PRIVATE_ONLY` | Validated generated Blender output; required locally for continuation |
| `.DS_Store` | `PRIVATE_ONLY` | Machine-generated filesystem metadata; ignored |
| `blender/scripts/__pycache__/` | `PRIVATE_ONLY` | Generated Python bytecode; ignored and reproducible |

## INVALID/DEPRECATED_ARTIFACT

| Path | Publication class | Reason |
| --- | --- | --- |
| `blender/output/INVALID_school_v1_ids_policy_1_0_1_path_remapped.blend` | `PRIVATE_ONLY` | Fresh validation failed after 441 path remaps; preserve only as review evidence and never use as input |

No current file is unclassified. No file was deleted automatically.

## Portability and secret review

- `docs/CODEX_HANDOFF.md` uses repository-relative paths and contains no
  machine-specific absolute path.
- Historical generated reports containing `/Users/...` paths are retained as
  objective evidence. Their locations and field contexts were explicitly
  flagged before the scoped 2026-09-15 publication approval; they are not
  credential or private-note content and must not be rewritten blindly.
- The private handoff stores the local executable/repository paths and is
  ignored by Git.
- A high-confidence credential-pattern scan produced only `sk-...` false
  positives inside historical external-resource path fields and serialized
  scene custom properties. A key/context review found no AWS-key, GitHub-token,
  private-key-header, or credential-bearing field match. No candidate value is
  reproduced here. This is not a human publication approval.

## Recommended Git checkpoint

Recommended checkpoint commit set: all 50 paths in `SHOULD_COMMIT`,
`NEEDS_HUMAN_REVIEW`, and `GENERATED_BUT_PROJECT_RELEVANT`. This recommendation
depends on the scoped 2026-09-15 approval and does not apply to later file
versions.

Suggested first commit message:

```text
checkpoint Blender first-slice pipeline handoff
```

The `.blend` files, private note, cache, and `.DS_Store` must remain untracked.
The invalid output must not be included in any implementation or dataset input.
