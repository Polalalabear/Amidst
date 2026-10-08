# Reviewed Phase 1 reproduction

## Current persistent runtime / 目前可執行入口

使用 `/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization` 的
`phase1/finalization-sprint`；恢復起點是 `5c2b67b9c48ae4028fd9fb2e7636f6b3af5121c0`。
Locked Python 3.12.12、原29 inputs／57 frames 與 physical evidence 已恢復。
完整 exact-copy／hydration／physical verification，以及 V2 export + V3 collision
infer/evaluate/reproduction／Rerun 指令，全部使用
[持久 runtime 指南](../operations/PHASE1_RESTORED_RUNTIME.md)。使用 uv 預設 cache，不依賴舊 temporary cache。

目前 raw run 是 `data/finalization/reviewed_run_recovery_20261008/`，不得覆寫。
Office export（Case1 50 timestamps、Case3 925 timestamps）、primary inference freeze、
independent evaluation 已完成；corridor verifier 得到 `PASS_LOCAL_UNION_REGENERATED`。
Ready-case repeat／fresh-process／ordering／GT-recipe-annotation poison／termination
reproduction **PASS**；兩個 RRD reader verification 通過、primary GT=false。
Dataset manifest SHA `a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5`；
primary freeze SHA `add7e6256c8e5d2ab834a00cb147f969bd0f091eb3ac62c34d6170461388c4de`。
Case2、Case3 full stress 和 full Exit 仍 BLOCKED。本次完整 tests **1978 passed／0 failed／0 skipped**，
Ruff/mypy PASS；精確 reproduction evidence 讀
[本次 validation receipt](../../data/finalization/recovery_checkpoint_20261008/validation.json)，
不能把歷史 PASS 當作本次執行。

Former temporary worktrees, V3–V8 raw runs and recordings are no longer on disk. Their
committed receipts remain historical evidence. Every command block below records the
historical V5 workflow; its old hydration root/cache/output paths are not current commands.
For execution, use the persistent runtime guide and a fresh output directory.

## Historical V5 environment / 歷史環境

Use the published `phase1/finalization-sprint` SHA, committed `uv.lock`, Python 3.12.12,
and the preserved school-v3 source (468300506 bytes, SHA256
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`).
The canonical asset checkout supplied source and historical raw inputs; development used
`/private/tmp/amidst-phase1-finalization`, which no longer exists. Historical destinations
below are retained as provenance, not available runtime paths.
Case2 remains blocked; reproduction of ready local cases does not grant the original Exit Gate.

## Historical V5 verified fresh run — 2026-10-08

The final clean-checkout rerun used
`/private/tmp/amidst-phase1-finalization-fresh-20261007` at code SHA
`e6fbc8fbb3bf8c36355db38c299de5ff37705604`. Its new output is
`data/finalization/reviewed_fresh_v5_final`; the local canonical comparison source is
`/private/tmp/amidst-phase1-finalization/data/finalization/reviewed_run_v5`.
The examples below use `reviewed_fresh_v5` as a new destination; the recorded final run
used `reviewed_fresh_v5_final` consistently for dataset, inference, evaluation and reproduction.
Both original temporary output trees are now unavailable; never recreate results and claim
they are the retained original raw bytes. Their curated Git receipts and hashes remain.

The fresh `evaluation/verification.json` reports **PHASE1_FINALIZATION_BLOCKED**:
Case1 executed as a reviewed local formal run, Case3 executed its reviewed local temporal
component, and Case2 remained `N/A_BLOCKED_SCOPE`. Both ready cases have
`per_case_execution_ready=true`; the complete Case3 detour/candidate-growth stress gate and
the full Case2 branching requirement remain unresolved under the single approved route class.
The fresh `reproduction/verification.json` reports **PASS** for repeated inference,
fresh process, ordering, GT poison and termination. Both reference-annotation files were
poisoned without changing inference; evaluation changed when reference positions were poisoned.

The final [complete-delivery comparison receipt](
../data/finalization/reviewed_checkpoint_v2/fresh_delivery_comparison_final.json) is **PASS**,
with no differences or missing required reports. It verifies all dataset artifact hashes,
canonical inference, candidate order/termination, report semantics, canonical demo presentations
and required recording availability. The comparison includes 41 JSON, 1 CSV, 4 Markdown,
21 PNG and 2 RRD artifacts. Measured runtime/runtime plot pixels and RRD container metadata
bytes retain their explicit nondeterministic exclusions; their presence and verification remain
required.

The final fresh dataset manifest SHA256 is
`a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5`, and the frozen
primary inference receipt SHA256 is
`d16708cfb437b6dff2ea06139126d5784a181c547d9dba6d1633068988cf4059`; both match the
local canonical run. Fresh reproduction receipt SHA256 is
`9020af0f8f8e1ac3098096a711a50d8dd927b5d6e3bec1fe96c68d6415d9a4d1`.
This verified ready-case reproduction leaves `overall_formal_execution_enabled=false`,
`formal_dataset_all_cases_validated=false` and `freeze_allowed=false`. It does not certify
formal Cases1–3 as a complete set or grant the original Phase1 Exit Gate.

## Clean-checkout prerequisites

Historical V5 prerequisite commands follow. The old `--historical-root` directory has been
lost; use the current runtime guide's exact-copy plan and restored checkout as hydration root.

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

The historical sandbox workaround used
`UV_CACHE_DIR=/private/tmp/amidst-finalization-uv-cache uv run --offline --no-sync`.
That temporary cache is no longer available; the recovered runtime uses the default uv cache.
Raw source/evidence/RRD/large renders stay local. Prior Git receipts remain preserved;
lost temporary raw versions are explicitly unavailable.
