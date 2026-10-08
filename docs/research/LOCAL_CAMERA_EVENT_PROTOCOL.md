# Local camera event pilot protocol / 局部跨鏡頭事件 pilot 契約

Version `local-camera-v1`, 2026-10-08. Status: **SYNTHETIC RESEARCH EXTENSION**.
This protocol implements [R1–R8](../operations/LOCAL_CAMERA_EVENT_RESEARCH_HANDOFF.md)
on `codex/simulation-engineering`. It grants no school geometry, portal, clock,
identity, behavioral intent, formal benchmark or Phase 2 authority.

## Scope and units

Every registry, index, inference, event and freeze receipt binds place, model,
revision, source SHA, spatial context SHA, run and clock. Units are metres and
configured synthetic seconds in a right-handed XYZ Z-up scene. Pinhole calibration,
regions, portals and directed camera links have `SYNTHETIC_CONFIG` authority.
The new scene is independent of the school Blender scene. Existing E0 RGB tracks,
registry and provisional bindings remain reusable; the E1 software-rendered scene
adds perspective, person geometry, camera viewpoint and visibility changes.
Neither scene proves general person detection or real-camera performance.

## Candidate and index contracts

The candidate unit is an ordered pair of original camera-local segments, each
preserving the producer's local IDs and pixel observations. Import/build may
read one explicit manifest once to validate and build dictionaries/time indexes.
Queries resolve a scope and anchor reference before selecting camera/time buckets.
Directed bounded multi-hop expansion precedes pair formation. No query scans the
catalog, repository, all records or all segment pairs; missing clock, coverage,
index or scope is an explicit unresolved result, never a global fallback.

Finite windows, hop and read budgets limit retrieval coverage. They do not prove
that a late/unretrieved continuation is physically impossible. `graph.complete`
retains its canonical finite-route search meaning; retrieval coverage and truncation
are separate. Missing appearance is uncertainty, and appearance distance is a
soft score rather than a physics rejection. Hard clock/reachability/speed gates
remain in every feature ablation. Same-camera recovery is source-bound HOLD;
simultaneous overlap never manufactures a blind gap or handoff.

## Pixel and identity evidence

Only SHA-verified unannotated RGB pixels and explicit camera calibration enter
measurement and projection. Simulator identity, position, bbox, depth,
segmentation, recipes and reference annotations enter generation or evaluation
only. Pixels may merge, miss or swap people. Preserve alternatives, unmatched,
HOLD, missing evidence and provisional bindings. Scores are uncalibrated ranking
values, not identity probabilities. Association ranking never reranks the original
Graph routes or trajectories. Photos-only recomputes the same pixel producer and
cannot read another mode's stored answer before its own freeze.

## Event definitions

| Event | Required evidence | Refusal / alternative |
| --- | --- | --- |
| Enter / exit door | Continuous projected visible samples on the two configured sides, segment crossing the bounded portal, signed direction | Approaching, dwelling or disappearing near a door is insufficient |
| Turn corner | Visible change of direction and both configured approach/departure regions | Loss near corner remains `LOST_NEAR_CORNER`; turnback is not through-turn |
| Dwell | Visible samples below configured speed for the configured duration | No inference of human intent |
| Possible loitering / revisit | Measured separated local revisit or repeated reversal above configured displacement/duration | One stop or blind gap alone is insufficient |
| Blind-gap alternatives | Frozen provisional association and canonical Graph candidates/trajectories | Retain all alternatives and uncertain identity; no invented camera photo |

Event composition is outside `BoundGapEvent` and `TrajectoryHypothesis`. It carries
scope, interval, track/association/region/portal refs, rule/config hashes, supporting
and conflicting evidence, uncertainty, details and replay refs. Cards show up to
five actual indexed RGB frames with camera/time/evidence refs, or explicit missing
media. Local 3D geometry is labeled PROJECTED or INFERRED_GAP. Main output has no GT
overlay; a generated 3D visualization is never called camera evidence.

## Development, freeze and test evaluation

`configs/engineering/local_camera_v1.json` freezes weights, thresholds, time windows
and appearance policy before test evaluation. Development and test are separate
whole run/trajectory recipes, never adjacent-frame splits. Shared synthetic scene,
camera geometry and similar actor appearances mean this pilot makes no appearance
or cross-scene generalization claim. Thresholds are engineering defaults fixed
before test; no claim of statistical calibration is made.

Build writes dataset/media/registry/context/config/producer hashes, per-mode pixel
output and inference, local events and a same-run freeze. Test evaluator validates
that freeze before opening the isolated GT sidecar. Evaluate indexed retrieval
against an independent same-scope offline complete segment inventory, then rank the
fixed retrieved pool using full fusion and single removal of spatial soft prior,
temporal score or appearance. Preserve all hard gates and Graph ordering.

Report link precision/recall, false merge/split, ID switches, identity-candidate
Recall@K, ambiguity/unmatched rates, behavior confusion/false positives/unresolved,
retrieval recall/misses/reads/pairs/latency and geometry/physics checks. Denominators
and truth-label matching rules belong in the evaluation receipt. Missing authority,
reference or meaningful population is N/A, including full identity IDF1. These
metrics are not the formal route Coverage@K or original A/B/C benchmark.

Poison/remove GT, recipe and reference sidecars while keeping pixels, calibration,
configuration and visible inputs fixed; pixel/index/association/event hashes must
stay unchanged. RGB changes may change inference. Exercise wrong scope/ref, missing
clock/coverage/media, finite windows, empty/ambiguous input, mode/stage/cross-run
freeze and invalid requests. Never tune against test truth.

## Local tools and publication

Reuse server-owned `SessionGuard`/`RunBinding`/`FreezeReceipt` and the typed eight-tool
allowlist. Index observation/event time and region buckets and opaque direct refs
once on load. GET/query/detail/media/replay read frozen results only. Agent has no
filesystem, arbitrary SQL, shell, scene scan or semantic reranking capability.
Validate source/run/mode/config/media hashes before serving, retain safe fixed
error codes, and log tool/scope/result hashes without GT or private locators.

Generated RGB, truth, run snapshots, evaluation detail and demo PNG stay beneath
ignored `data/engineering/local_run/`. Git stores code, config, documentation and
curated counts/hash receipts only. Each executable milestone has current validation
and a narrow independent commit/ordinary push. Preserve concurrent work, immutable
source/history, main and frozen Phase 2. Formal Cases 2/3 and full Exit remain
BLOCKED; Case 4 remains DEFERRED.

## OpenAI API wiring

## Token fallback algorithm
