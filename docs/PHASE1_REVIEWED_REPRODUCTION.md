# Reviewed Phase 1 reproduction

Use the published `phase1/finalization-sprint` SHA, committed `uv.lock`, Python 3.12.12,
and the preserved school-v3 source (468300506 bytes, SHA256
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`).
The canonical asset checkout supplies source and historical raw inputs; development stays
in `/private/tmp/amidst-phase1-finalization`. Every generated destination below must be new.
Case2 remains blocked; reproduction of ready local cases does not grant the original Exit Gate.

## Clean-checkout prerequisites

Create a clean checkout at the recorded code checkpoint. Install the exact locked environment,
then reconstruct physical evidence from the original scene with the historical materializer.

```sh
uv sync --locked --python 3.12.12
uv run python -m amidst.materialize_physical_evidence \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --source-scene /Users/polalabear/Developer/amidst/blender/school_v3.blend
uv run python -m amidst.reviewed_input_hydration \
  --historical-root /private/tmp/amidst-phase1-finalization \
  --durable-review /Users/polalabear/Developer/amidst/data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review
```

Hydration checks the durable manifest, all package files and the 29 immutable review inputs
before copying anything. Existing matching files remain; a mismatch refuses overwrite.
It restores the original review frames/public inputs, never replacing them with new formal
outputs. The materializer independently checks actual regenerated source/support evidence.
For the optional historical school-v2 tests, supply its unchanged local scene and exact original
`data/cameras/school_v2_calibration_v1.json` (SHA256
`5eaa94b97b188514ceb2f2e4cc6c6cc6ab63583c6fb6bb2ebda375d5be296bd7`).

Recompute the reviewed certificate into a fresh application directory:

```sh
uv run python human_review/apply_decisions.py \
  --decisions human_review/decisions.json \
  --source-asset /Users/polalabear/Developer/amidst/blender/school_v3.blend \
  --apply --output data/finalization/fresh_human_review_applied_v1
```

The frozen configs retain source, protocol, human, semantic receipt, certificate, budgets,
sampling, seed and timing hashes. The V2 extension adds the separately approved reference
movement receipt; its strict inference envelope contains no recipe/annotation positions.
Compare the new application manifest with the committed original application manifest before
executing. A human APPROVE alone never bypasses numerical certification or per-case readiness.

## Fresh reviewed dataset and primary inference

Choose a new run directory, for example `data/finalization/reviewed_fresh_v5`. Use the fresh
application directory above consistently in every command.

```sh
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --disable-autoexec /Users/polalabear/Developer/amidst/blender/school_v3.blend \
  --python scripts/export_phase1_reviewed_inputs.py -- \
  --config configs/finalization/reviewed_case_export_with_movement_v2.json \
  --application data/finalization/fresh_human_review_applied_v1 \
  --output data/finalization/reviewed_fresh_v5/dataset
uv run python scripts/run_phase1_reviewed.py infer \
  --dataset data/finalization/reviewed_fresh_v5/dataset \
  --application data/finalization/fresh_human_review_applied_v1 \
  --config configs/finalization/reviewed_case_inference_lock_v2.json \
  --output data/finalization/reviewed_fresh_v5/inference_primary
```

The exporter uses the unchanged Blender camera/raycaster/projection producer and fresh 2D
visibility; synthetic reference motion comes from the locked configuration sampler, labelled
`CONFIGURATION_SAMPLER`. It does not claim Blender-evaluated actor animation. Sampling is
inclusive 5 Hz without rejection or extrapolation. Evaluation truth, explicit movement
annotations and simulation recipes are separate from strict inference payloads.

All A/B/C and supported single-factor outputs freeze before any reference opens. Projection
methods, conditioning, uncertainty and LOW_CONFIDENCE/UNAVAILABLE remain visible. The approved
rigid offset changes only Z before BU→metre conversion; endpoints are never clipped/snapped.
The reviewed provider retains the complete human semantics/source/scope/certificate wrapper.

## Evaluation, report, demos and verification

```sh
uv run python scripts/run_phase1_reviewed.py evaluate \
  --dataset data/finalization/reviewed_fresh_v5/dataset \
  --application data/finalization/fresh_human_review_applied_v1 \
  --inference data/finalization/reviewed_fresh_v5/inference_primary \
  --output data/finalization/reviewed_fresh_v5/evaluation
uv run python scripts/run_phase1_reviewed.py verify-reproduction \
  --dataset data/finalization/reviewed_fresh_v5/dataset \
  --application data/finalization/fresh_human_review_applied_v1 \
  --config configs/finalization/reviewed_case_inference_lock_v2.json \
  --inference data/finalization/reviewed_fresh_v5/inference_primary \
  --output data/finalization/reviewed_fresh_v5/reproduction
```

Evaluation preserves Case1–3 × A/B/C × K=1/2/3 rows, blocked/empty/N/A records, separate
physical timed-segment populations and independent source-route/handoff inventory. Coverage
is strict ADE <0.50 m at every exact reference timestamp. Reference moving time sums explicit
MOVING annotations intersecting the GAP and excludes departure DWELL. Candidate motion uses
its explicit timed segments; reference annotations never reach inference.

Each ready case has `evaluation/demos/<case>/reviewed.rrd`, `preview.png`, `presentation.json`
and replay instructions. RRD reader verification must pass. Primary recordings include source
cameras, certified bounds, projected observations and all inferred timings in their original
order. GT is absent from the primary recording and stays in the independent evaluation/debug
package, off by default. Open with `uv run rerun <recording.rrd>`.

Compare the complete fresh delivery, not just an inference snapshot:

```sh
uv run python -m amidst.finalization.reviewed_reproduction \
  --local-dataset /private/tmp/amidst-phase1-finalization/data/finalization/reviewed_run_v5/dataset \
  --fresh-dataset data/finalization/reviewed_fresh_v5/dataset \
  --local-inference /private/tmp/amidst-phase1-finalization/data/finalization/reviewed_run_v5/inference_primary \
  --fresh-inference data/finalization/reviewed_fresh_v5/inference_primary \
  --local-evaluation /private/tmp/amidst-phase1-finalization/data/finalization/reviewed_run_v5/evaluation \
  --fresh-evaluation data/finalization/reviewed_fresh_v5/evaluation \
  --output data/finalization/reviewed_fresh_v5/full_delivery_comparison.json
```

All dataset artifact hashes, frozen candidate order/termination/policy, metric records,
report semantics, non-runtime PNGs and canonical demo presentations must agree. Runtime
values/runtime plot pixels and RRD container metadata bytes are explicitly nondeterministic;
their availability, counts and verified recording/presentation content stay required.
No comparison grants a freeze while Case2 branches and Case3 detour/growth remain unavailable.

```sh
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
AMIDST_PHYSICAL_SOURCE_SCENE=/Users/polalabear/Developer/amidst/blender/school_v3.blend \
  uv run pytest --require-physical-evidence -rs
uv run ruff check .
uv run mypy
git diff --check
```

If sandboxed uv fails macOS system-configuration initialization, the existing locked runtime
can use `UV_CACHE_DIR=/private/tmp/amidst-finalization-uv-cache uv run --offline --no-sync`;
Blender subprocesses still require the authorized environment that can execute Blender.
Raw source/evidence/RRD/large renders stay local. Every prior version is retained.
