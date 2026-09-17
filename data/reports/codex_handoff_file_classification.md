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

## Post-checkpoint continuation artifacts

The following files were created or changed after commit
`5bd109a4a5a4eb58d8492d093f406d986581b444` while completing the authorized
texture-agnostic derived-scene validation. The earlier scoped publication
approval does not cover these versions; nothing in this section is approved for
commit or push without a new human publication review.

| Path | Handoff class | Publication class | Reason |
| --- | --- | --- | --- |
| `docs/CODEX_HANDOFF.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Current continuation status and validation commands |
| `docs/07_Technical_Decisions.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Records evidence that the confirmed ADR-009 gate passed |
| `blender/scripts/validate_texture_agnostic_scene.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Canonicalizes configured shader inputs to Blender float32 storage |
| `blender/scripts/validate_first_slice_readiness.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Emits an explicit no-blockers summary |
| `blender/scene_manifest.json` | `NEEDS_HUMAN_REVIEW` | `REVIEW_REQUIRED` | Populated derived-scene checksum and readiness state |
| `data/metadata/first_dataset_slice_render_config_v0_1_0.json` | `NEEDS_HUMAN_REVIEW` | `REVIEW_REQUIRED` | Populated current readiness state |
| `data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json` | `NEEDS_HUMAN_REVIEW` | `REVIEW_REQUIRED` | Scene-specific runtime resource policy and checksums |
| `data/reports/school_v1_texture_agnostic_scene_creation.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Machine-readable creation and provenance evidence |
| `data/reports/school_v1_texture_agnostic_scene_creation.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable creation summary |
| `data/reports/school_v1_texture_agnostic_scene_validation.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Authoritative fresh-process invariant validation |
| `data/reports/school_v1_texture_agnostic_scene_validation.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable invariant-validation summary |
| `data/reports/school_v1_texture_agnostic_scene_validation_failed_float32_tolerance_2026_09_15.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Preserved failed validation evidence before validator correction |
| `data/reports/school_v1_texture_agnostic_scene_validation_failed_float32_tolerance_2026_09_15.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable preserved failure evidence |
| `data/reports/school_v1_first_slice_readiness.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Current zero-blocker readiness evidence |
| `data/reports/school_v1_first_slice_readiness.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Current human-readable readiness summary |
| `blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend` | `SHOULD_REMAIN_LOCAL` | `PRIVATE_ONLY` | Validated derived binary scene; identified portably by SHA-256 |

The post-checkpoint derived `.blend` has SHA-256
`e349646c27fb343341a372b1e6d97b1a66f304f52c62721400e1833cdcd4d933` and
must remain untracked under the existing repository policy.

### Pilot-generation continuation

These later versions are also outside the 2026-09-15 checkpoint publication
approval:

| Path | Handoff class | Publication class | Reason |
| --- | --- | --- | --- |
| `.gitignore` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Keeps generated pilot datasets local under the raw-experiment-output policy |
| `blender/scripts/generate_first_dataset_slice.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Deterministic bounded pilot generator source; cleanup correction is not yet validated by a second run |
| `data/reports/school_v1_first_slice_pilot_run_pilot_0001.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Machine-readable failed pilot summary |
| `data/reports/school_v1_first_slice_pilot_run_pilot_0001.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable failed pilot summary |
| `data/reports/school_v1_first_slice_pilot_run_pilot_0001_failure_analysis.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Root-cause and next-decision evidence |
| `data/reports/school_v1_first_slice_pilot_run_pilot_0001_failure_analysis.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable failure analysis |
| `data/datasets/school_v1_first_slice_v0_1_0/run_pilot_0001/` | `SHOULD_REMAIN_LOCAL` | `PRIVATE_ONLY` | Raw generated images and frame-level scene/GT evidence; preserved locally and ignored by Git |

The pilot dataset directory must not be staged. A small sanitized example would
require a separate human content review and a public-example location.

### Observation-render diagnostic continuation

These files and later modified versions are outside every prior scoped
publication approval. They must not be staged or pushed without a new human
review.

| Path | Handoff class | Publication class | Reason |
| --- | --- | --- | --- |
| `blender/scripts/diagnose_observation_render.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Reproducible one-camera F12/AOV/state/luminance diagnostic source |
| `blender/scripts/validate_texture_agnostic_scene.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Rejects neutral overrides whose Principled Weight is not 1.0 |
| `blender/scripts/generate_first_dataset_slice.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Refuses generation when the full neutral-material validation fails |
| `docs/open_questions.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | OQ-016 records the unresolved cross-contract render-policy decision |
| `docs/CODEX_HANDOFF.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Warns that the older readiness report predates the invalid observation finding |
| `blender/scene_manifest.json` | `NEEDS_HUMAN_REVIEW` | `REVIEW_REQUIRED` | Records zero valid accepted samples after the scene-specific observation diagnostic |
| `data/reports/school_v1_first_slice_pilot_run_pilot_0001_failure_analysis.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Preserves historical acceptance separately from post-diagnostic invalidity |
| `data/reports/school_v1_first_slice_pilot_run_pilot_0001_failure_analysis.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable post-diagnostic pilot status |
| `data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Machine-readable render state, luminance, controlled checks, and blocker |
| `data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable diagnostic and required decision |
| `data/reports/render_diagnostics/school_v1_camera_0ab45975_separated_pipeline_baseline_v0_1_0/` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Canonical baseline normal/AOV/repeat/state evidence for human review |
| Other `data/reports/render_diagnostics/school_v1_camera_0ab45975_*candidate*` and failed-attempt directories | `INVALID/DEPRECATED_ARTIFACT` | `REVIEW_REQUIRED` | Preserved negative diagnostic evidence; not authoritative pipeline inputs |

The generated render-diagnostic images contain only the synthetic
texture-agnostic scene view, but remain `REVIEW_REQUIRED` because they expose
scene-specific spatial evidence. No diagnostic image or report is approved for
public publication by this classification entry.

### Cross-platform portability continuation

The following new or modified versions are classified but are not approved for
commit or publication by this record:

| Path | Handoff class | Publication class | Reason |
| --- | --- | --- | --- |
| `scripts/migration_manifest.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Generic checksum manifest creation and verification; serializes no physical source roots |
| `scripts/check.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Rejects machine-specific absolute user paths in active source and configuration files |
| `scripts/aggregate_render_policy_v0_1_1.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Emits an explicit repository-root path base for future aggregates |
| `blender/scripts/create_texture_agnostic_scene_v0_1_1.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Emits portable logical scene references for future evidence |
| `blender/scripts/validate_texture_agnostic_scene_v0_1_1.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Emits portable logical scene references for future validation evidence |
| `blender/scripts/diagnose_render_policy_v0_1_1.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Requires formal diagnostic outputs to stay below the repository root |
| `blender/scripts/diagnose_render_policy_v0_1_1_camera.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Emits an explicit repository-root path base for future camera records |
| `docs/04_Dataset_Specification.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Cross-environment dataset and diagnostic provenance boundary |
| `docs/07_Technical_Decisions.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | ADR-010 records the explicitly approved portable migration approach |
| `docs/08_Repository_and_Data_Publication_Policy.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Migration artifact classification and private-transfer boundary |
| `docs/09_Data_Types_and_Exchange_Formats.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Repository-relative path and migration-manifest contract |
| `docs/internal_guide.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Cross-platform continuation procedure |
| `docs/open_questions.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Keeps cross-environment pixel acceptance `OPEN` under OQ-016 |
| `docs/CODEX_HANDOFF.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Records the stopped 16/29 macOS checkpoint and destination boundary |
| `local/migration_inventory_v0_1_1.json` | `SHOULD_REMAIN_LOCAL` | `REVIEW_REQUIRED` | Populated logical transfer inventory; ignored and not approved for publication |
| `local/migration_manifest_v0_1_1.json` | `SHOULD_REMAIN_LOCAL` | `REVIEW_REQUIRED` | Populated checksums and source environment; ignored and not approved for publication |
| `blender/source/school_v1.blend` | `SHOULD_REMAIN_LOCAL` | `PRIVATE_ONLY` | Immutable private source asset |
| `blender/working/school_v1_working.blend` | `SHOULD_REMAIN_LOCAL` | `PRIVATE_ONLY` | Private working asset |
| `blender/output/school_v1_ids_policy_1_0_1_r2.blend` | `SHOULD_REMAIN_LOCAL` | `PRIVATE_ONLY` | Validated stable-ID input required by v0.1.1 validation |
| `blender/output/school_v1_first_slice_texture_agnostic_v0_1_1_r2.blend` | `SHOULD_REMAIN_LOCAL` | `PRIVATE_ONLY` | Validated destination diagnostic scene |

Existing populated reports, metadata, and diagnostic images retain
`REVIEW_REQUIRED`; existing `.blend` files retain `PRIVATE_ONLY`. The migration
does not grant publication approval or authorize an external upload.

### Cross-platform test and dependency continuation

The following source, lock, test, and documentation files contain no populated
scene evidence and are classified `PUBLIC_ALLOWED`:

| Path | Handoff class | Publication class | Reason |
| --- | --- | --- | --- |
| `requirements-dev.lock.txt` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Explicitly locks the formal suite to zero third-party Python packages |
| `scripts/test.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Standard-library formal test entry point |
| `tests/test_migration_manifest.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Synthetic temporary-file tests for path and checksum behavior |
| `tests/test_repository_contracts.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Repository setup, documentation, and lock contract tests |
| `blender/runtime_dependencies.lock.json` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Version-only Blender embedded-runtime lock without machine or scene data |
| `blender/scripts/check_runtime_dependencies.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Read-only exact runtime verifier |
| `docs/10_Cross_Platform_Setup_and_Testing.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Separate macOS, Windows, and Linux version, setup, test, and verification commands |
| `docs/00_Project_Map.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Routes setup and testing work to the new supporting document |
| `docs/internal_guide.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Links the continuation workflow to executable platform instructions |
| `docs/CODEX_HANDOFF.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Separates shell and PowerShell verification syntax and records the incomplete image |

The user-local `~/.zshrc` PATH entry is machine configuration, stays outside
the repository and migration manifest, and is not a publication artifact.

### Completed macOS r2 diagnostic and destination handoff

| Path | Handoff class | Publication class | Reason |
| --- | --- | --- | --- |
| `scripts/finalize_render_policy_v0_1_1.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Generic non-overwriting sweep/repeat finalizer with no populated scene data |
| `tests/test_render_policy_review.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Synthetic test preserving proposal status and human decision authority |
| `blender/runtime_dependencies.lock.json` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Adds an unverified Linux target profile without machine data |
| `tests/test_repository_contracts.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Checks Windows and Linux setup/profile markers |
| `scripts/check.py` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Requires the finalizer, its test, and Linux documentation markers |
| `docs/04_Dataset_Specification.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Records completed evidence collection and failed strict determinism without changing the dataset contract |
| `docs/open_questions.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Keeps the repeat and proposed composition decisions open under OQ-016 |
| `docs/CODEX_HANDOFF.md` | `SHOULD_COMMIT` | `PUBLIC_ALLOWED` | Records the completed macOS diagnostic and Windows/Linux handoff boundary |
| `data/reports/render_diagnostics/school_v1_render_policy_v0_1_1_r2/` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | 29 primary camera records, preserved incomplete image, retry, and three repeat records/images |
| `data/reports/school_v1_render_policy_v0_1_1_camera_statistics_raw.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Complete raw 29-camera aggregate and repeat selection |
| `data/reports/school_v1_render_policy_v0_1_1_camera_statistics.json` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Formal completed diagnostic with strict determinism failure |
| `data/reports/school_v1_render_policy_v0_1_1_diagnostic.md` | `GENERATED_BUT_PROJECT_RELEVANT` | `REVIEW_REQUIRED` | Human-readable result and proposed composition threshold |

The explicit push request authorizes the task-related `PUBLIC_ALLOWED` source,
tests, locks, and documentation. It does not authorize committing or publishing
the populated `REVIEW_REQUIRED` reports or images listed above.
