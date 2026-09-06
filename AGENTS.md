# Project Instructions

These instructions apply to the entire `amidst` repository.

## Required workflow

1. Before modifying the project, read the directly relevant documents under
   `docs/`.
2. Before each change, state the requirement, impact scope, short plan,
   acceptance criteria, and failure cases.
3. Prefer the smallest viable modification. Avoid unrelated redesign,
   refactoring, dependencies, or application code.
4. After every complete step, run `python3 -B scripts/check.py`. Do not bypass
   failures; fix them or report the exact unresolved failure.
5. Create and switch to a new Git branch before modifying repository files.
6. Never modify `main` directly.
7. Only when publication is explicitly requested: push the branch, open a pull
   request, inspect CI, and merge only after CI passes.
8. Update only documentation directly related to the current change.
9. Do not use Computer Use unless it is genuinely necessary.
10. Documentation is the source of truth for implementation.
11. Do not implement unconfirmed requirements.
12. Do not silently convert assumptions into project decisions.
13. Prefer explicit `TODO`, `OPEN`, and `PROPOSED` markers over invented
    answers.
14. Before adding any file to Git, classify it under
    `docs/08_Repository_and_Data_Publication_Policy.md` as `PUBLIC_ALLOWED`,
    `PRIVATE_ONLY`, or `REVIEW_REQUIRED`. When uncertain, do not add the file;
    use `REVIEW_REQUIRED` and request human confirmation.
15. Unless a task or document explicitly assigns a different human owner, the
    default responsible person is Peter. This default does not assign reviewer
    or approver authority, does not define a component's source-of-truth owner,
    and does not change a decision's status.

## Decision status convention

Use only these statuses for planning decisions:

- `CONFIRMED`: verified project facts or explicit decisions.
- `PROPOSED`: a direction under consideration but not finalized.
- `OPEN`: a decision is still required; use this when uncertain.
- `DEFERRED`: intentionally postponed beyond the current scope.
- `REJECTED`: explicitly considered and rejected.

## Pre-change record

Before editing, provide a short record with these headings:

- **Requirement**
- **Impact Scope**
- **Short Plan**
- **Acceptance Criteria**
- **Failure Cases**

Stop and request human direction when the repository is not `amidst`, branch
creation is unsafe, relevant documents conflict, or an unresolved validation
failure prevents a reliable result.

## Documentation boundaries

- Planning documents are worksheets for human review, not finished
  specifications.
- Keep unknown quantities, schemas, metrics, technologies, and architecture
  choices `OPEN` unless evidence supports another status.
- Keep public documentation free of secrets, private storage links, raw
  surveillance data, identifiable annotations, and sensitive site assets.
- Do not implement the system while preparing or reviewing planning templates.

### Documentation navigation

1. When documentation ownership or relevant specifications are unclear, start
   with `docs/00_Project_Map.md`.
2. Read the core specification(s) directly related to the task.
3. Consult `docs/glossary.md` when shared terminology affects the change.
4. Consult `docs/open_questions.md` when work may depend on an unresolved
   cross-document decision.
5. Do not read or rewrite unrelated documents without a task-specific reason.

`docs/glossary.md` owns shared terminology. Keep a local unresolved issue in its
own specification when it affects only that document or module; register or
reference it in `docs/open_questions.md` when it affects multiple documents,
architecture, MVP scope, evaluation, dataset policy, or project-wide behavior.
Reference an existing question ID instead of duplicating its discussion.

## Operational boundaries

These boundaries apply to all future work in this repository.

### Decision authority

- Codex may analyze, recommend, compare, and implement confirmed decisions.
- Codex must not independently promote `OPEN` or `PROPOSED` decisions to
  `CONFIRMED`.
- Product, architecture, evaluation, dataset, privacy, and technology decisions
  require explicit human confirmation.
- When implementation depends on an unresolved decision, stop at the smallest
  meaningful boundary and report the decision required.

### Scope control

- Do not implement adjacent features merely because they may be useful.
- Detection does not imply tracking; tracking does not imply Re-ID; spatial
  mapping does not imply precise 3D localization; Retrieval does not imply RAG
  or a vector database; Agent work does not imply autonomous action; offline
  evaluation does not imply real-time infrastructure.
- Implement only the smallest change that satisfies the confirmed requirement.

### Dependency boundary

Before adding, replacing, or significantly upgrading a dependency, report:

- why it is needed;
- whether the requirement can be satisfied without it;
- alternatives considered;
- maintenance impact; and
- compatibility impact.

Do not introduce a framework merely to simplify a small implementation.

### Schema stability

- Treat shared schemas as contracts.
- Before changing Detection, Track, Camera, Zone, Event, Evidence, Retrieval,
  Ground Truth, or World State schemas, identify downstream consumers and the
  compatibility impact.
- Prefer backward-compatible changes. Never silently rename, delete, or
  reinterpret an existing field.

### Ground Truth and benchmark integrity

- Ground Truth is an evaluation authority, not implementation output. Never
  alter it merely to pass tests, improve metrics, match predictions, or improve
  a demo.
- Ground Truth corrections need an explicit reason and must remain
  distinguishable from model or system changes.
- Keep Training, Validation/Development, and Benchmark/Test conceptually
  separate. Do not train or tune on the benchmark/test set unless the approved
  evaluation protocol explicitly permits it.
- Do not repeatedly tune against a final benchmark while representing it as an
  unbiased test result.
- Do not silently change metrics, thresholds, matching criteria, filters,
  ignored samples, evaluation windows, or benchmark composition after poor
  results. Document protocol changes, and qualify before/after comparisons.

### Experiment reproducibility

- Important experiments should preserve, where applicable, dataset version,
  model/version, configuration, random seed, evaluator version, relevant code
  revision, and resulting metrics.
- Do not overwrite important results when comparison is required.

### Data provenance and synthetic data

- Keep observed data, annotated Ground Truth, model predictions, deterministic
  derived state, inferred state, synthetic/generated data, and human-confirmed
  data distinguishable.
- Never silently treat generated or inferred information as direct observation.
- Label synthetic or AI-generated data explicitly and record provenance before
  mixing it with any real dataset or Ground Truth collection.

### Retrieval and Agent boundaries

- Retrieval returns grounded results from defined data sources and preserves
  no-result, incomplete, ambiguous, and unavailable states.
- Never fabricate a missing record for a convenient Agent answer.
- Prefer authoritative structured sources for structured facts; do not add
  semantic/vector retrieval when deterministic structured retrieval is enough.
- Keep `Observation -> Stored/Derived State -> Retrieved Evidence -> Agent
  Interpretation` distinct.
- An Agent interpretation is not automatically authoritative World State. When
  grounding is required, Agent claims must remain traceable to evidence.

### Failure visibility and tests

- Do not hide a failure behind fallback behavior merely to keep a demo running.
- Make fallbacks explicit and observable. Distinguish expected empty results,
  unsupported features, unavailable dependencies, invalid input, system
  failures, and evaluation failures.
- Do not weaken, delete, skip, or rewrite valid tests only to make an
  implementation pass.
- When a confirmed requirement makes a test obsolete, identify the conflict,
  explain it, and update the test with the requirement change.

### Data mutation boundary

- Avoid destructive changes to datasets, annotations, benchmark sets,
  experiment results, environment metadata, and model artifacts.
- Prefer versioned or reversible changes. Destructive migrations require
  explicit approval.

### Git safety

- Do not force push, rewrite shared history, delete remote branches, discard or
  reset away user work, commit unrelated files, or merge into `main` outside
  the required publication workflow.
- Never use destructive Git commands merely to obtain a clean working tree.
- Preserve unrelated user changes and work around them.

### Private data and external services

- Follow `docs/08_Repository_and_Data_Publication_Policy.md` as the single
  source of truth for repository/publication classification.
- Do not copy private assets into public directories to simplify tests, demos,
  fixtures, or CI; use synthetic or sanitized fixtures instead.
- Do not upload private assets to an external service without explicit approval.
- Do not introduce or send project/private data to a new external API, hosted
  model, telemetry platform, or cloud provider without explicit approval when
  data would leave the local environment.

### Logging boundary

- Logs must not expose secrets, credentials, private URLs, unnecessary personal
  information, or raw sensitive surveillance content.
- Prefer identifiers and sanitized metadata where sufficient.

### Performance boundary

Use this order: correctness, verification, baseline, profiling, then
optimization. Do not optimize prematurely, and preserve evaluation correctness
through performance changes.

### Documentation boundary

- Documentation describes confirmed behavior and explicitly marked proposals.
- Do not restyle or rewrite unrelated documents during implementation work.
- Do not create duplicate sources of truth.
- When documentation and implementation conflict, report the conflict instead
  of silently choosing one.

## Mandatory stop conditions

Stop and request a human decision when:

1. the task would change a `CONFIRMED` project decision;
2. authoritative documents contradict one another;
3. Ground Truth appears incorrect;
4. benchmark integrity may be compromised;
5. sensitive data may be published;
6. a destructive data or schema migration is required;
7. a major new dependency or architecture component is required;
8. implementation requires resolving an `OPEN` architecture decision;
9. existing user work may be overwritten; or
10. the requested change would materially exceed agreed scope.

When stopping, report the blocking issue, affected scope, available options,
trade-offs, and the recommended minimal option. Never continue by making an
implicit project decision.
