# Local camera pilot / 局部跨鏡頭人物關聯與行為事件

This is a local **SYNTHETIC RESEARCH EXTENSION**, implementing
[R1–R8](../operations/LOCAL_CAMERA_EVENT_RESEARCH_HANDOFF.md) under the
[versioned protocol](../research/LOCAL_CAMERA_EVENT_PROTOCOL.md). Formal Cases 2/3
and full Exit remain BLOCKED, Case 4 DEFERRED, frozen Phase 2 unchanged.
The existing M1–M6 E0 lab registry, pixel producer, original provisional bindings,
frozen schemas and demo are preserved. New indexed associations use
`simulation.local-association.v1` with independent load/freeze handling.

## Operate

From the existing `phase1-finalization` checkout, the delivered checkpoint reuses
one RGB materialization per split. Its source RGB/GT and earlier diagnostic freezes
remain byte-identical. Operate the current test checkpoint:

```sh
uv run --offline --no-sync python -m amidst.engineering.local_pilot serve \
  --output data/engineering/local_run/local_camera_v1/test/checkpoints/final --port 8012
uv run --offline --no-sync python -m amidst.engineering.local_pilot demo \
  --output data/engineering/local_run/local_camera_v1/test/checkpoints/final
uv run --offline --no-sync python -m amidst.engineering.local_pilot evaluate \
  --output data/engineering/local_run/local_camera_v1/test/checkpoints/final
uv run --offline --no-sync python -m amidst.engineering.local_pilot export-cards \
  --output data/engineering/local_run/local_camera_v1/test/checkpoints/final
```

Rebuild into a new empty output with the same code/config/run ID:

```sh
uv run --offline --no-sync python -m amidst.engineering.local_pilot build \
  --output /private/tmp/amidst-local-camera-rebuild/test \
  --split test --run-id local-camera-test-v1
uv run --offline --no-sync python -m amidst.engineering.local_pilot evaluate \
  --output /private/tmp/amidst-local-camera-rebuild/test
```

Development uses `--split development --run-id local-camera-development-v1`.
To make a new freeze without another RGB/raw copy, choose a **new** checkpoint
below the existing materialization and pass
`--reuse-from data/engineering/local_run/local_camera_v1/test` plus the same run ID.
The loader binds contained media through registry hashes, not an arbitrary path
supplied by an Agent. An existing conflicting checkpoint is rejected.

Open [the local pilot](http://127.0.0.1:8012). Select a mode, resolve the lab, choose
a camera and a finite time interval, then query events. Each card reads its actual
RGB source images, local 3D projected evidence, provisional blind-gap candidates,
supports/conflicts/alternatives, detail and replay. White points in a blind-gap card
are only visible evidence; colored routes are inferred alternatives. No line
connecting blind endpoints is called an observed trajectory. Up to twelve cards
are shown per view; narrow the camera/time query to inspect the remainder. The
underlying scoped tool returns truncation independently of Graph completeness.

The service binds each mode/session/stage. `photos_only` recomputes pixels before
freeze. INPUT stage permits photos, and plus mode permits pixel measurements;
region filtering and projected/association/result reads remain unavailable there.
RESULTS requires same-run dataset/config/registry/media/producer/inference receipt
and event/config hashes. Caller-supplied stage or extra scope fields are rejected.
Tools and errors contain no filesystem access, arbitrary SQL/shell, GT or recipe.

## Evidence and replay

Each split has four configured perspective cameras and 244 unannotated RGB frames
at 2.5 Hz. It covers enter/exit, corner/revisit/dwell, similar people, occlusion,
door approach, corner turnback, disconnected lookalikes, deliberately excessive
speed and delayed blind-gap endpoints. This is E1 configured pinhole rendering of
faceted people, not a general detector, school render or real-camera benchmark.

`registry.json` and `topology.json` bind cameras/media, metres, synthetic clock,
source/context and directed region/portal reachability. Import builds scope/ref
dictionaries and interval trees once. Association selects bounded reachable
camera-time candidates before pairs; queries never load a full snapshot/catalog
to filter records. Missing clock/coverage and finite windows/hops/budgets are
explicit. Unretrieved late arrivals are not physics rejections. Same-camera
recovery is HOLD; overlap creates no blind gap. Original Graph candidate and
trajectory order remains intact.

Every run saves `manifest.json`, `package.json`, runtime and behavior configs,
two pixel/inference/event outputs, freeze receipts, isolated `simulation/export`,
evaluation, tool receipts, timing telemetry and PNG cards. Source, algorithm,
evaluation-policy, dataset/media/registry/config/producer/inference/event hashes
bind the same run. Import and byte verification are separate from measured query
latency. Photos-only and plus modes use identical photos; both recompute the local
producer, and this comparison is no claim about an external model.

Full GT stays in generator/evaluator boundaries. The evaluator validates freeze
and event lineage before opening GT, then labels detected segments using declared
pixel-contact/overlap/purity rules. Its independent complete eligible inventory
uses a fixed 12-second/3-hop reference policy. Conditional next-segment recall uses
whole-scope reachability and physical speed with **no retrieval window/hop/budget**;
it is conditional on produced GT-labeled segments, not recall of undetected people.
Pair precision/recall and pair error counts describe provisional hypotheses.
Global false merge/split and IDF1 are N/A because no global identity assignment is
produced. Ranked identity-candidate Recall@K includes unresolved hypotheses and is
distinct from accepted PROVISIONAL links and formal route Coverage@K.

Full fusion and SPACE/TIME/APPEARANCE removals use the same frozen pool and hard
physics; scores are not probabilities. Time continuity includes projected
departure/arrival velocity and direction from pixels. Development/test use whole
distinct trajectories with shared scene/appearances. Config defaults are fixed
before test freeze; these fixtures also support integration regressions, so no
sealed-holdout, appearance or cross-place generalization claim is made. Low accuracy
and cases where removing a feature improves rank are reported without test tuning.

## Validate and reproduce

```sh
uv run --offline --no-sync pytest tests/engineering/test_local_*.py \
  tests/engineering/test_association.py tests/phase2/test_phase2_integration.py
uv run --offline --no-sync ruff check .
uv run --offline --no-sync mypy
git diff --check
```

Tests include 16,000 unrelated indexed records, long-interval overlap, budgets and
windows, wrong scope, missing coverage/clock/media, same-camera HOLD, false behavior
triggers, source mappings, both input modes, stage and region-filter bypasses,
cross-run freeze and GT/recipe/reference poisoning. A paired blind example has
identical pixels with different feasible hidden middle trajectories; inference
cannot select their truth by looking at a recipe.

Rebuild into a new empty output with the **same run ID/config/code**, compare
dataset, registry, media, config, pixel, inference, event and evaluation hashes.
Internal `package.json` includes local locators; its hash and the enclosing manifest
hash can differ with output path. Freeze receipt content and inference hashes are
portable. Query latency is wall-clock telemetry and does not enter inference hashes.
Conflicting existing inputs or frozen outputs are rejected rather than overwritten.

Generated raw RGB/GT, snapshots, detailed evaluator labels and PNG stay under ignored
`data/engineering/local_run/`. Only code/config/docs and curated hash/count receipts
are published. The curated receipt and dated validation are linked from the current
handoff and WORK_LOG. Ordinary push updates only `codex/simulation-engineering`.

## OpenAI API wiring

## Token fallback algorithm

## Measured checkpoint, 2026-10-08

The [curated receipt](../../data/engineering/local_camera_20261008/validation.json)
binds actual source hashes, 2427 passing full tests (required Blender/physical
evidence, zero failures/skips), Ruff, strict mypy (145 source files), 34 real
loopback HTTP requests, 378 MockAgent calls and browser photo/3D/replay operation.
The final source required an unsandboxed test rerun after Blender crashed in the
sandbox; this was an environment failure, not a new formal acceptance.

| Measurement | Actual test result |
| --- | --- |
| Indexed / global diagnostic segment pairs | 115 / 153 |
| Independent fixed-policy candidate inventory coverage | 115 / 115 |
| Conditional true-next retrieval | 8 / 8; zero misses |
| Association pairs inspected / index records read / entries touched | 115 / 161 / 143 |
| Provisional known-identity pair precision / recall | 0.350 / 0.467 |
| Wrong-identity / missed eligible pair hypotheses | 13 / 8; global merges/splits N/A |
| Within-local pixel identity switches | 8 |
| Pixel visible-contact recall / ground RMS | 0.900 / 0.305 m |
| Frozen event query latency, photos-only | median 0.216 ms / p95 0.438 ms; 120 queries |
| Graph speed / configured region violations | 0 / 0; no school/global collision certification |

| Fixed pool | Identity-candidate Recall@1 | @3 | @5 |
| --- | --- | --- | --- |
| Full fusion | 0.375 | 1.000 | 1.000 |
| Without spatial soft prior | 0.750 | 1.000 | 1.000 |
| Without temporal/motion score | 0.625 | 0.750 | 0.875 |
| Without appearance | 0.375 | 1.000 | 1.000 |

Full fusion does not dominate these ablations. Scores and thresholds were not
retuned against these results. Event output includes 2 enter, 4 exit, 6 turn,
4 possible-loitering, 1 dwell and 1 loss-near-corner cards, plus 46 gap cards with
78 canonical routes / 146 timing alternatives. These are detections/hypotheses,
not confirmed actions. In the bounded known-identity visible evaluation, enter/exit
remain unresolved, corner has five false positives (precision/recall 0), possible
loitering has one false positive (precision/recall 0), and one dwell matches.
Blind-gap behavior lacks a separate labeled population: its class metrics are N/A.
See the receipt for full confusion, denominators, unmatched/unknown counts and scope.

Same-run GT/recipe/reference replacement and removal preserved pixel, inference,
behavior and tool hashes. An independent empty-output rebuild reproduced registry,
media links, config, both freeze receipts, inference/events and evaluation hashes.
Only local package/manifest locator hashes differ with output path. This proves
local synthetic reproducibility, not the separately blocked formal clean-checkout
benchmark, school geometry, real camera or global person identity accuracy.
