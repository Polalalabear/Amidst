# Phase 1 experiment log / 實驗紀錄

All experiments below are **PILOT / SYNTHETIC SAMPLE**. Physical validity remains
**PARTIAL / PROVISIONAL**. This is a research finding log; dated engineering checks
and original execution details remain in [WORK_LOG](WORK_LOG.md). Formal Case 1–3
semantics and unresolved research settings are not changed by these experiments.

## Completed Phase 1 experiments / 已完成實驗

| Experiment | Checkpoint / evidence | Finding and limits |
| --- | --- | --- |
| Blender visible → GAP → visible | `fdf9e7e8f2dc695917ba42094a63cc06ca910963`; local `data/pilot/phase1_wall_pilot_20261005/office/` | 10s/5Hz, 50timestamps/100renders;26visible camera records,24global landmark GAP timestamps; recovery observed. Point visibility is not a whole-body CV detector. |
| Downstream Top-K reconstruction | `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e`; local `data/pilot/phase1_downstream_20261005/` | Strict2D→Projection→Observation→configured topology→Graph→3routes/6timed hypotheses;4.0–9.0s gap;COMPLETE. Source-bound planes/annotation AABBs are diagnostic, not certified school navigation. |
| Determinism / GT isolation | Both downstream and robustness evidence | Repeated inference and GT poison preserve inference bytes/order; GT changes only evaluation, never inference/Graph/ranking/reconstruction. GT debug is a separate visualization layer. |
| Controlled robustness | `ce2974b25b31a8cb0ec9bc579a84d708d3356bf7`; local `data/pilot/phase1_robustness_20261006/` | Nine fixed controls over three existing trajectories;27inference invocations;48newtests,943passed at that checkpoint. No new Blender render/physical dataset or formal Cases1–3. |

### Robustness scenarios S01–S09

| Scenario | Control | Routes / hypotheses | Termination / observation |
| --- | --- | ---: | --- |
| S01 office medium | Native5.0s endpoint GAP | 3/6 | COMPLETE;ADE0.000708092424BU/FDE0.000280838027BU;Coverage@1/2/3true. |
| S02 corridor long | Native6.0s GAP;CORRIDOR02/03 pair | 3/6 | COMPLETE;ADE0.000081147488BU/FDE0.000082597284BU;Coveragetrue. |
| S03 auditorium short | Native0.4s GAP within9.0–9.8s window | Search not run | Same-camera recovery;inverse Projection/aggregation passed, pilot topology handoff unsupported. |
| S04 remove front | Delete calibration and all front records | Search not run | INPUT_CONTEXT min2-camera contract rejects. Remaining rear stream also lacks departure. |
| S05 remove rear | Delete calibration and all rear records | Search not run | INPUT_CONTEXT rejects;remaining front stream lacks recovery. No invented GAP/endpoint. |
| S06 pixel noise | Uniformu/v ±0.25px, fixedseed20261006 | 3/6 | COMPLETE;accuracy degraded, Coveragefalse. |
| S07 short tight | Timestamp×0.5,5s/10Hz;2.5s GAP,speed33,offset12 | 1/1 | COMPLETE;feasibility pruning, not Top-K collapse. |
| S08 short ambiguous | Same asS07,offset1 only | 3/3 | COMPLETE;all feasible configured branches retained. |
| S09 short speed failure | Same compressed stream,speed31 | 0/0 | NO_FEASIBLE_PATH;normal search termination, metrics unavailable. |

Four unavailable cases have null ADE/FDE/minima/Coverage, not artificial zeros.
Existing diagnostic Coverage is ADE < **0.02 BU**, not an approved formal epsilon.
The configured graph does not certify WALL/collision, full-body clearance, WALKABLE
holes, floor/plane authority or physical scale. Historical AREA_*_ELEVATOR names
never create elevator transitions. The native auditorium full stream has overlapping
visibility; arbitration and same-camera topology support remain separate open issues.

## Projection sensitivity finding

Historical robustness comparison, **not a fresh run in this section**:

| Quantity | Baseline S01 | ±0.25px S06 |
| --- | ---: | ---: |
| ADE (BU) | 0.000708092424 | 1.439140812588 |
| FDE (BU) | 0.000280838027 | 2.549003130929 |
| minADE@3 / minFDE@3 | same as primary | same as primary |
| Coverage@1/2/3 | True / True / True | False / False / False |
| Routes / timed hypotheses | 3 / 6 | 3 / 6 |
| Search termination | COMPLETE | COMPLETE |

Direct comparison of saved PROJECTED points, **without GT**, finds maximum
3D displacement **2.548758485436 BU** at rear camera frame45/t9.0, with pixel-vector
perturbation **0.316362775880px** and local amplification **8.056442412815 BU/px**.
The ±0.25px bound applies to each coordinate; the vector norm can exceed0.25px.
8.06 is the amplification at the maximum-displacement sample, not the maximum
ratio over all samples (historical maximum ratio was10.80641985BU/px).

Failure is **inverse Projection accuracy degradation**, not a Graph/Search
termination failure. Current hypothesis:

> 在現有 pilot geometry 下，Projection 對 pixel noise 的敏感度比 GAP 長度本身更可能成為 accuracy bottleneck。

This is a scoped hypothesis from these controlled pilots, not a general proof or
an approved physical accuracy claim. Its cause is not yet established: camera
viewing angle, camera-plane geometry, ray-plane intersection conditioning, camera
distance, plane orientation, calibration/intrinsic/extrinsic perturbation and
numerical precision require independent checks in this round.

## 2026-10-06 Projection sensitivity experiment / 預先宣告

Branch `phase1/projection-sensitivity` starts at robustness checkpoint
`ce2974b25b31a8cb0ec9bc579a84d708d3356bf7`, with a clean isolated worktree.
The robustness branch, source Blender scenes, calibration and existing pilot files
remain unchanged. No Graph/Top-K logic, metric definition or Coverage epsilon is tuned.

- Pixel noise per coordinate: required0,±0.05,±0.1,±0.25,±0.5,±1.0px; additional fixed
  fine levels around0.0005–0.02px to resolve the existing diagnostic boundary.
  Seeds20261006/42/20261007; the same normalized draws are scaled across amplitudes.
- Camera comparisons: original office/auditorium front/rear, corridor02/03, CLASS101
  where reliable visible pilot evidence exists. Cameras without visible samples
  remain explicitly unavailable. Overlapping observations are analyzed per frame,
  never silently arbitrated or used to fabricate a downstream handoff.
- Geometry per sample: Euclidean camera-point/intersection distance, axial depth,
  optical-axis ray angle, acute ray-normal angle, complementary grazing angle,
  normalized incidence, analyticpixelJacobian/SVD and finite perturbation gain.
- Calibration diagnostic copies: focalfx/fy ±0.1%,principalpoint ±0.1px,
  pitch/yaw ±0.01deg,worldtranslation ±0.1BU. Originals are never edited; variants
  are explicitly synthetic and do not attest source-scene calibration authority.
- Plane height/orientation and synthetic distance/grazing controls separate geometry
  conditioning from implementation. Pivots are explicit; no plane is fitted to GT.
- Numerical decomposition: independent high-precision ray-plane reference,
  float32/float64 comparison, roundtrip from accepted PROJECTED points, analytic
  versus finite-difference Jacobian, followed by evaluation-only GT residuals.

### Boundary definitions / 診斷分類

Inference state and accuracy state are reported separately. The existing Coverage
criterion remains ADE <0.02BU for K1/2/3. An explicit **diagnostic point-displacement
budget of0.02BU** reuses that magnitude to flag outliers; it does not change metrics
or establish formal research tolerance.

- STABLE: Coverage@3true and maximum baseline-to-noisy projected displacement≤0.02BU.
- DEGRADED: Coverage@3true, but maximum projected displacement exceeds0.02BU.
- ACCURACY_FAILURE: Coverage@3false even if inference remains COMPLETE.
- INFERENCE_FAILURE: projection/input/search cannot produce a reconstruction;
  unavailable metrics stay null and the actual failed layer/reason is preserved.

No inference settings, candidates, plane bindings or best hypotheses are selected using GT.
Accuracy boundaries are evaluation-only measurements of already frozen inference outputs.
Geometry diagnostics consume only2D/context; GT is opened only after frozen inference
for evaluation/debug. A detected implementation bug requires a minimal reproduction
and regression before a minimal fix, with before/after evidence. Conditioning alone
will be documented rather than patched or concealed by epsilon.

### Results / 結論

本輪量化了 Projection sensitivity，在所測 metadata、樣本及數值合約範圍，
未找到 implementation bug 證據；這不認證真實校準或 world accuracy。現有
固定高度／直線 pilot 下，camera-plane geometry conditioning 是主要 accuracy
bottleneck；這支持優先研究 Projection 的原假說。**本輪未獨立控制 GAP 長度**，
不能把 office/corridor 跨場地結果當成 GAP 長度的因果比較，也不證明一般 trajectory
的 GAP 誤差不重要。

#### Protocol and evidence

- Two existing downstream trajectories × 17 pixel half-widths × three fixed seeds:
  **102 variants**, all **COMPLETE**, each preserving **3 routes / 6 timed hypotheses**.
  **37 STABLE / 22 DEGRADED / 43 ACCURACY_FAILURE**, zero INFERENCE_FAILURE.
- Four existing source streams supply **179 visible samples**, **5,907 pixel trials**,
  **5,370 camera/plane diagnostic trials**, plus **358 joint-focal trials**. Eight
  camera-region groups are reported; CORRIDOR04 has no visible sample and stays N/A.
- All 102 inference runs pass an allowlisted read guard. Exactly three representatives
  (office zero / office ±0.25px / corridor ±0.25px, seed20261006) additionally pass
  byte-identical repeat and GT-poison checks. These six extra calls are not extra
  experimental variants. GT is loaded only after saved inference is frozen.
- A 27-cell synthetic factorial isolates camera distance (100/300/800 BU) and grazing
  angle at fixed focal/clip. Near-parallel directional probes can fail closed via
  FAR_CLIPPED, INTERSECTION_BEHIND_CAMERA or RAY_PARALLEL_TO_PLANE. These are toy
  controls, not new school routes or physical validity evidence.

#### Noise boundary

Brackets below are adjacent tested **per-coordinate** half-widths. They are empirical
transitions for a seed, not a continuous threshold, a probability bound or an accepted
formal tolerance. Perturbation directions repeat across amplitudes; no monotonicity is
assumed outside the observations.

| Source | Seed | STABLE → DEGRADED ±px | DEGRADED → ACCURACY_FAILURE ±px |
| --- | ---: | --- | --- |
| office | 42 | (0.002, 0.0025] | (0.003, 0.0035] |
| office | 20261006 | (0.0015, 0.002] | (0.0035, 0.004] |
| office | 20261007 | (0.002, 0.0025] | (0.01, 0.02] |
| corridor | 42 | (0.003, 0.0035] | (0.02, 0.05] |
| corridor | 20261006 | (0.0035, 0.004] | (0.005, 0.01] |
| corridor | 20261007 | (0.0035, 0.004] | (0.01, 0.02] |

The earliest observed Coverage failure is office (0.003,0.0035]px / corridor
(0.005,0.01]px; endpoint noise directions materially shift these brackets. Interior
projected outliers can exceed the point budget before endpoint-conditioned gap ADE
fails. All required nonzero levels (±0.05/0.1/0.25/0.5/1px) fail Coverage@1/2/3
in both sources for seed20261006, while Top-K and termination remain normal.
Office ±0.25px reproduces ADE1.4391408126 / FDE2.5490031309 BU and max displacement
2.5487584854 BU; this confirms the historical finding without adjusting epsilon.
Complete ADE/FDE/minADE@K/minFDE@K/Coverage and actual vector gains are in the CSV.

#### Geometry and layered diagnosis

Peak local Jacobian spectral norm is **12.60410293 BU/px** at
`CAM_1F_AUDITORIUM_FRONT`, auditorium frame0/t0.0: camera distance835.1364 BU,
axial depth792.5899 BU, grazing angle5.364988°, acute ray-normal84.635012°,
optical off-axis18.36756°, normalized incidence0.09349994. Its minimum directional
gain1.23510847 BU/px shows anisotropy. Office-region rear has the highest mean gain
11.4390 BU/px; mean and peak rankings differ. Camera comparisons are confounded by
sample geometry, not evidence of hardware/calibration quality.

For X=C+t d and t=n·(P−C)/(n·d), the analytic pixel Jacobian is
J=t[A−d(n·A)/(n·d)]. Distance and small ray-plane denominator amplify perturbations;
controlled factorials and analytic/finite-difference agreement support this explanation.

The first four precision rows below cover **179 unperturbed baseline OBSERVED samples**,
not all calibration copies or near-parallel toy controls.

| Layer / check | Maximum observed residual | Interpretation |
| --- | ---: | --- |
| Accepted inverse versus independent Decimal60 | 6.4311e−13 BU | No observed float64 precision defect. |
| Analytic versus central-difference Jacobian | 2.3682e−10 relative | Conditioning derivative agrees with implementation. |
| PROJECTED inverse → forward roundtrip | 8.1387e−13 px | Forward/inverse convention internally consistent. |
| float32 diagnostic versus actual service | 0.000258985 BU | Diagnostic copy only; cannot explain BU-scale noise error. |
| Blender exported pixel versus simulation forward(GT) | 0.000497228 px | Evaluation-only export/calibration residual, including rounding. |
| Baseline inverse versus GT | 0.00178757 BU | Small baseline residual, separate from noisy accuracy degradation. |
| GT true-ray versus fixed landmark plane | 0.0000513107 BU | Tiny height mismatch in these samples; not formal plane authority. |

Across5,370 calibration/plane copies, Float64/Decimal60 maximum is8.1993e−13 BU,
float32 diagnostic0.000452066 BU and roundtrip1.3880e−12 px. The toy grid has maximum
analytic/central-difference relative residual8.0153e−5: its fixed0.001px finite step
is affected by near-grazing nonlinearity. This is distinct from a numeric bug claim;
the precision table is not a global bound on all diagnostic geometries.

The entire GT-free projection reference is saved before GT access. Evaluation-only
true-ray/plane algebra never passes GT pixels into InverseProjectionService and never
fits a plane/calibration to GT. Forward export residuals do not prove a calibration
bug. Tested numerical/convention/plane residuals are much smaller than the observed
noise displacement. Main evidence is **inverse ray-plane geometry conditioning and
calibration sensitivity**. No core fix or metric/Graph/Top-K change was made.

#### Calibration and plane copies

| Diagnostic perturbation | Maximum point displacement BU |
| --- | ---: |
| Joint fx/fy ±0.1% | 2.616400 |
| fx only ±0.1% / fy only ±0.1% | 0.333341 / 2.611045 |
| cx ±0.1px / cy ±0.1px | 0.123842 / 1.262217 |
| Local pitch / yaw ±0.01° | 1.557335 / 0.238296 |
| World X/Y/Z translation ±0.1 BU | about0.1 / about0.1 / 1.064834 |
| Plane height ±0.01 / ±0.1 BU | 0.106952 / 1.069519 |

Tilt ±0.01° around metadata plane origin produces up to3.99198 BU displacement,
but includes a long lever arm and local plane-height change. Tilting around the
baseline PROJECTED anchor holds the intersection and only diagnoses Jacobian change;
neither pivot uses GT. Do not attribute origin-pivot displacement to orientation alone.
These assigned perturbations do not measure real calibration uncertainty or establish
that the original calibration is wrong. Differently dimensioned deltas are not a risk ranking.

#### Artifacts and reproduction

All generated evidence is local/ignored **PILOT / SYNTHETIC SAMPLE** under
`data/pilot/phase1_projection_sensitivity_20261006/`; source scenes/calibration/old pilots
are preserved. `verification.json` checks14 checkpoint sources (hash/size/mtime),
8 strict inputs, all1,224 inference artifacts and four evaluation truth digests.

- `experiment_results.json`, `report.md`, `verification.json`: machine and human summaries.
- `downstream_sweep/sweep_report.json`, `sweep_table.csv`: all variants and boundaries.
- `sample_analysis/baseline_geometry.jsonl`, `per_sample.jsonl`, `calibration_samples.jsonl`:
  per-sample geometry, actual noise vectors/amplification and calibration results.
- `sample_analysis/{camera,noise,calibration}_summary.{json,csv}`: sensitivity tables.
- `sample_analysis/{noise_vs_3d_error,per_camera_sensitivity,geometry_conditioning}.png`
  and `noise_to_downstream_metrics.png`: four inspected charts; range bands are fixed-seed
  ranges, not confidence intervals. Displacement charts are relative to PROJECTED baseline.
- `joint_focal_diagnostic.json`, `synthetic_conditioning_grid.json`: diagnostic controls.
- `layer_evaluation/frozen_projection_reference.json`, `layer_evaluation.json`: frozen
  GT-free reference followed by explicitly evaluation-only decomposition.

Reproduce in **fresh output paths**, preserving the original artifacts. Use the source
inventory's `geometry_diagnostic_inputs` to create a JSON list containing ONLY the
`observations`/`context` pair for each stream; do not pass the mixed inventory to analysis.

```sh
uv run python scripts/analyze_projection_samples.py --sources <pure-2d-pairs.json> --output <fresh-analysis>
uv run python scripts/sweep_projection_downstream.py \
  --source data/pilot/phase1_robustness_20261006/scenarios/S01_office_medium \
  --source data/pilot/phase1_robustness_20261006/scenarios/S02_corridor_long \
  --output <fresh-sweep>
uv run python scripts/evaluate_projection_layers.py --inventory <source_inventory.json> --output <fresh-layer-evaluation>
uv run python scripts/report_projection_sensitivity.py --experiment <assembled-fresh-experiment>
```

`projection_conditioning.synthetic_conditioning_grid()` creates the GT-free factorial;
`joint_focal_perturbations(camera)` provides two focal copies. For each original OBSERVED
frame, project its unchanged pixel with each copy and compare against its PROJECTED
baseline; save179×2 labeled rows, without loading GT. The report consumes these saved
supplements plus the QA record; it never runs/tunes inference. Helpers and tests are
tracked; private raw pilot inputs, GT, charts and inference artifacts remain ignored.

#### Unresolved issues / next steps

1. Bind source-specific camera/floor/landmark planes and establish architectural scale
   and physical tolerances. Point/landmark visibility is not whole-body CV evidence.
2. Measure real 2D detection and calibration uncertainty. This sweep has only three
   fixed seeds, constant-height/linear synthetic routes and diagnostic calibration copies.
3. Review view conditioning / uncertainty propagation and future robust estimation
   approaches using those measurements; this round does not implement them or tune epsilon.
4. Preserve WALL/navigation/full-body collision validity as **PARTIAL / PROVISIONAL**.
   Same-camera topology, overlapping visibility and single-camera contracts remain open.
5. Formal Cases1–3 remain unexecuted. These accuracy failures should be resolved or
   explicitly scoped before formal results; healthy search alone is insufficient.

Fresh final regression: **998 passed in61.60s, no skips**, repository Ruff passed,
`uv run mypy` passed for74 source files. Final diff and local commit verification are
recorded in WORK_LOG; no push or merge is performed for this experiment.
