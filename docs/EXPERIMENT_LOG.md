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


## 2026-10-06 Projection conditioning mitigation / 預先宣告

Checkpoint `b90e81adb3acc1a0c1e599d488f3113f0842cfb4` on
`phase1/projection-sensitivity` is clean and freshly passes998tests in63.54s, Ruff,
mypy74files and diff check. It is pushed; live origin SHA is identical. New independent
branch `phase1/projection-conditioning-mitigation` starts exactly there. Parallel
physical-authority work in the primary checkout remains untouched.

Projection is the priority because the earlier noise sweep retained healthy Top-K/search
but lost accuracy: peakgain12.604BU/px, remote/grazing geometry, tiny seed-dependent
Coverage boundaries, and consistent baseline numerical checks. GAP length was not
independently controlled. This round does not modify benchmark semantics/Graph/Top-K,
raise Coverage epsilon, change target-reference semantics or select using GT.

### Predeclared controls and authority

- Reuse noise half-widths0/0.001/0.002/0.004/0.01/0.1/0.25px, seeds20261006/42/20261007,
  original office/corridor downstream trajectories and auditorium/classroom visible samples.
- Calibration copies: jointfx/fy±0.1%,cx/cy±0.1px,pitch±0.01°,worldZ±0.1BU.
- A: existing fixed landmark-plane baseline.
- B: confidence labels only; identical projected positions/quality and downstream inputs.
- C-standard: reject if Jacobian maxgain>10BU/px OR normalized incidence<0.1.
  C-extreme-only: gain>20BU/px OR incidence<0.05. Boundary comparisons are explicit.
- B/C review if maxgain>5BU/px OR incidence<0.2. Confidence is the heuristic
  min(1,incidence/0.2)/(1+(gain×0.002px/0.02BU)^2), not a measured probability.
  The0.002px uncertainty radius and0.02BU point budget are synthetic diagnostic assumptions;
  thresholds are fixed before GT evaluation, not an approved physical tolerance.
- D: exact source/floor/zone/landmark binding with local independent mesh-probe anchor.
  It represents the same horizontal landmark plane; it is expected to preserve geometry.
  Body-landmark pixels cannot be rebound directly to a floor/footpoint surface.
- E/F school surface intersection/multiple legitimate surfaces: UNAVAILABLE_AUTHORITY.
  Separate committed provider snapshot `bb66bb74a4a76430f6fa8f79672345385a79e3f0`
  has48WALKABLE surfaces but0physicalAPPROVED surfaces; floor/scale remainHUMAN_REVIEW.
  That source snapshot also differs from the office derived asset. Do not import unrelated
  dirty authority work or promote REVIEW mesh. Any E/F toy controls are separately labeled
  SYNTHETIC_FIXTURE_ONLY and are not school accuracy improvement evidence.

Projection rejection is an availability decision, not camera occlusion. Keep original2D
observations, rejection reasons and diagnostics; the downstream adapter uses null
GEOMETRY_UNCERTAIN availability gaps, without fabricating pixels or endpoints. Report
original observation recall, retained-cohort error, paired baseline error, endpoint/gap-window
changes and downstream completion. Error reductions from deleting bad samples must be
explicitly separated from improvements on the same evidence. Runtime costs are diagnostic
single-machine measurements, not a deployment benchmark.

All inference/projection artifacts are frozen before GT evaluation. Repeat/poison checks
must preserve inference bytes. Physical validity remainsPARTIAL/PROVISIONAL. Final results,
limits and next steps will follow this predeclared section after the bounded comparison.


### Mitigation results / 受控比較結果

**結論：未找到可接受的 accepted-point accuracy mitigation。** B 是可用的
conditioning risk diagnostic，保留 evidence，但不修正 coordinates。C 只拒絕高風險
points；D 強化 source／landmark／local binding 檢查，實際仍是相同平面。
Projection 仍是這些 pilot 的主要 accuracy bottleneck，正式 Cases1–3 未準備完成。

31 treatments/source = seven noise levels × three fixed seeds + ten calibration copies；
four existing streams × five variants = **620 rows**。只 office/corridor 做 downstream，
共 **310 attempts：279 COMPLETE / 31 NOT_RUN**；其餘 auditorium/classroom101
只做 point diagnostic，不列為 downstream failure。179 original visible samples
重複形成5,549 point trials/variant；不是5,549個獨立 physical observations。

| Variant | Accepted / original trials | LOW_CONFIDENCE | Downstream COMPLETE / attempts | Same-retained-cohort RMS gain |
| --- | ---: | ---: | ---: | ---: |
| A baseline | 5549/5549 | 0, policy inactive | 62/62 | 0 BU |
| B confidence | 5549/5549 | 3999 | 62/62 | 0 BU |
| C standard | 4987/5549 | 3999 including rejected | 31/62 | 0 BU |
| C extreme-only | 5549/5549 | 3999 | 62/62 | 0 BU |
| D local binding | 5549/5549 | 0, policy inactive | 62/62 | 0 BU |
| E approved school surface | UNAVAILABLE_AUTHORITY | N/A | NOT_RUN | N/A |
| F legal school multi-surface | UNAVAILABLE_AUTHORITY | N/A | NOT_RUN | N/A |

B and D match A's **entire FrameSampleDataset** in all124 source/treatment groups:
positions, service quality, provenance, raw UV/GAP and identities. C's accepted rows
also exactly match the original points. Scores are kept outside existing projection_quality,
Graph/ranking and reconstruction. No implementation/coordinate/plane-binding bug was
found within the tested contracts; no core fix was made.

#### Accuracy versus evidence loss

C-standard rejects **562/5549 =10.13%** point trials. Office loses5/26 visible points
in every treatment: all rear recovery frames45–49/t9.0–9.8 are unavailable. Remaining
21/26 points =80.77% recall, but the closing endpoint is gone, so **31/31 office attempts
stop before search** with INSUFFICIENT_PROJECTED_ENDPOINT_EVIDENCE. Metrics remain null,
not zero or Coverage=false. Corridor loses no points and remains31/31 COMPLETE.
Auditorium rejects13–14/82 points per treatment; classroom rejects none.

Representative office ±0.25px/seed20261006:

| Quantity | A baseline | C standard |
| --- | ---: | ---: |
| Retained points | 26/26 | 21/26 |
| Displayed cohort point RMS BU | 1.267219729 | 1.140864389 |
| Baseline on the identical retained cohort BU | 1.267219729 | 1.140864389 |
| Paired accuracy improvement | 0% | 0% |
| Maximum retained point error BU | 2.549003131 | 1.975700058 |
| GAP ADE/FDE BU | 1.439140813 / 2.549003131 | N/A |
| Coverage@1/2/3 | F/F/F | N/A |
| Top-K / termination | 3 routes / 6 hypotheses / COMPLETE | Search NOT_RUN |

The approximately10% displayed RMS drop is **cohort deletion**, not a corrected
projection. Across all fixed treatments pooled RMS drops0.546492→0.477400BU with
C-standard, while its same-cohort baseline is0.477400BU: paired gain remains0.
C-extreme-only rejects0 points, preserving availability and unchanged noise failures;
zero rejection does not demonstrate an accuracy solution.

A/B/D/C-extreme all have25/62 computed Coverage@1/2/3 true at unchanged ADE<0.02BU;
C-standard has14/31 true among available corridor reconstructions. The latter is a
different set of cases, not better coverage of the original62 attempts. Every completed
run retains3candidate routes/6timed hypotheses. GT is never used to rank/select them.

#### Conditioning policy applicability

The predeclared REVIEW region is gain>5BU/px OR incidence<0.2 (grazing<11.537°).
Standard rejection uses gain>10 OR incidence<0.1 (grazing<5.739°); extreme-only uses
20/0.05 (grazing<2.866°). Equality remains accepted. They are **experimental policies**,
not approved compulsory thresholds, world tolerances or GT-optimized cutoffs.

B flags3999/5549 trials (72.07%): every office/corridor/auditorium point in this matrix,
zero classroom points. The fixed nominal0.002px uncertainty radius is conditional and
unmeasured. Classroom ±0.25px reaches maxerror0.502557BU across three seeds despite
zero geometry flags. A CONDITIONED label therefore does not certify accuracy under
larger pixel/calibration error. Real noise/calibration uncertainty must be measured and
propagated before treating confidence as an acceptance guarantee.

Saved conditioning per observed candidate includes Euclidean camera-point/intersection
distance, axial projected depth, off-axis/ray-normal/grazing angles, signed ray-plane
denominator, normalized incidence,1/incidence indicator, analyticJacobian/SVD gain,
service quality and a separate nonprobabilistic score. Rejected diagnostic candidates
are kept for inspection; they are not emitted as reliable points to Graph consumers.

#### Plane / approved surface controls

D verifies independent source SHA, site/floor/zone, mesh-probe anchor and
physical_floor_z + foot_clearance + landmark_offset. Reanchoring along that same
horizontal landmark plane leaves the intersection and Jacobian unchanged. Direct
substitution of foot/floor plane for body-landmark pixels is refused; it would change
reference semantics rather than repair conditioning. No plane is fitted to GT.

Read-only pinned geometry receipt (authority_preflight.json) confirms48WALKABLE surfaces,
all physicalHUMAN_REVIEW,0approved; floors/scaleHUMAN_REVIEW,physical_complete=false.
Original-school provider SHA differs from the derived office source. The provider and
unrelated dirty physical-authority branch are not imported/merged into this experiment.

E/F have **no school accuracy result**. Five separate SYNTHETIC_FIXTURE_ONLY controls
exercise authority/source/floor/target-reference/footprint gates: unique surface1hit,
multiple legal surfaces2hits both retained,review-only/wrongsource/wrongreference0hits.
Stable surface-ID ordering is not GT/nearest selection. These tests demonstrate contracts,
not school surface authority, a physical dataset or downstream multi-surface integration.

#### Calibration / runtime / stability

All ten calibration copies leave source assets unchanged. Same-cohort accuracy gain is
0 for every mitigation; C's smaller retained errors are again deletion. Pooled A point RMS
is about1.26–1.27BU for jointfocal±0.1%,0.639–0.642BU for cy±0.1px,0.777–0.781BU for
pitch±0.01°,0.709–0.710BU for worldZ±0.1BU;cx±0.1px about0.0794–0.0798BU.
These repeated synthetic copies do not measure real calibration uncertainty.

Single-machine diagnostic shared-cost accounting: office median Projection stage
A13.70ms/B20.50ms/C-standard20.09ms/D13.40ms. Confidence diagnostics add about6.8ms
per office case in this accounting; IQR bands describe fixed treatments, not confidence
intervals. C downstream can run faster because its office search is skipped, not because
it reconstructs more efficiently. No deployment/runtime benchmark claim is made.

All620 variants and248 conditioning/reference files are frozen **before any GT access**.
All runtime inference reads are allowlisted. Three representative full Projection/policy/
Graph runs (including a rejected endpoint case) replay and pass GT-poison byte equality;
only evaluation can change. Source verification preserves14 checkpoint file hashes/size/mtime,
12strict2D/context/independent-metadata files,4123frozen inference artifacts and four GTdigests.
Three charts are visually inspected; raw2D evidence and rejected reasons remain available.

#### Artifacts / next steps

Local ignored **PILOT / SYNTHETIC SAMPLE** root:
`data/pilot/phase1_projection_conditioning_mitigation_20261006/`.

- protocol.json / authority_preflight.json / receipts/: predeclared controls and independent bindings.
- cases/: original2D inputs, conditioning, A reference, policy decisions, frozen outputs and metrics.
- mitigation_results.json / summarized_comparison.json / mitigation_table.csv / report.md:
  all controlled point errors,ADE/FDE/minima/Coverage,rejection,availability,termination and runtime.
- noise_error_availability.png / downstream_availability.png / diagnostic_runtime.png:
  three inspected charts; prior layout retained inqa_before_layout/, measured results unchanged.
- synthetic_surface_controls.json / projection_freeze_before_gt.json /
  visualization_qa.json / verification.json: explicitly scoped control and isolation evidence.

Reproduce using the existing sensitivity inventory and a fresh directory containing the
same predeclared protocol (do not overwrite frozen artifacts):

```sh
uv run python scripts/compare_projection_mitigations.py \
  --inventory data/pilot/phase1_projection_sensitivity_20261006/source_inventory.json \
  --output <fresh-directory-with-protocol>
uv run python scripts/report_projection_mitigations.py --experiment <fresh-directory>
```

**Readiness remains NO.** Before formal Cases1–3: establish source-specific approved floor/
landmark/camera and surface bindings, architectural scale/tolerance, measured pixel and
calibration uncertainty, and an evidence policy that preserves or replaces missing departure/
recovery evidence. Review eligible camera geometry, appropriate landmarks and uncertainty
propagation; source-bound multi-view/multi-surface hypotheses need an approved additive
contract. This round does not implement those future strategies, tune epsilon or start
formal cases. WALL/body/collision validity remainsPARTIAL/PROVISIONAL.

Final frozen-code regression: **1091 passed in62.95s,no skips**, repository Ruff and
mypy74files pass;working/staged diff checks pass. An initial full run caught the report
script still changing during a source-snapshot test (1090passed/1snapshot failure); code
was frozen and the complete suite rerun successfully. Independent local commit follows;
no merge or push of the mitigation branch is performed.


## 2026-10-06 Projection model upgrade / measurement-authority preflight

Published clean mitigation checkpoint `5f020b075d4a670f60007eab7baeb12055f2f5d9` freshly
passes1091tests in66.00s,Ruff,mypy74files anddiffcheck. Live origin SHA matches.
New independent branch `phase1/projection-model-upgrade` starts exactly there.

### Preflight completed before model implementation

Fresh pinned physical-authority snapshot `cdeee3e316e88c87ab63cdcf3acb360485f00dd6` was
read without merging/importing it. Camera binding, floor/landmark plane, WALKABLE/surface,
architectural scale and departure/recovery policy are **PROVISIONAL**. Real pixel-noise
and calibration-uncertainty estimates are **MISSING**. Zero APPROVED physical surfaces;
48 WALKABLE physical HUMAN_REVIEW, floor/scale approval IDs absent. Office uses derived
b4d3394 source, so original cd46fa03 authority cannot be borrowed. A reviewed external
v2 camera calibration is also not a v3 pilot camera approval.

Strict2D audit:office/corridor/classroom have0same-time camera pairs;auditorium has33
same-target/source/exact-timestamp FRONT+REAR pairs (2.0–6.2s,6.6–8.6s). Synthetic
exporter samples all cameras inside the same timestamp loop;this is synthetic sync,
not physical clock authority. Existing auditorium departure9.2/recovery9.6 are single
REAR observations. No multi-view repair of existing GAP endpoints is promised.

### Predeclared additive controls

Reuse the31treatments/source from mitigation:7noiselevels×3seeds+10calibrationcopies.
A fixed-plane remains intact;B diagnostic-only preserves points. C uses all exact-time
pairs, closest-ray least squares with acute angle≥1°,positive/clip checks and explicit
fail-closed insufficient evidence;no asynchronous interpolation,GT alignment or GT pair
selection. D/E school surfaces remainUNAVAILABLE_AUTHORITY;separate synthetic approved
fixtures demonstrate unique/all-hit behavior without school efficacy claims.
F adds sidecar uncertainty contracts,not Observation/Graph changes:known injected uniform
pixel/control sigma=halfwidth/√3;calibration common-mode covariance matches the assigned
synthetic perturbation only. Planar covariance is conditional on exact plane and lacks
unmeasured landmark-height/plane uncertainty. Tangential coverage must not be called
full3D calibration. Zero/noise covariance and missing uncertainty remain explicit.

GT is inaccessible to pair/surface/model/hypothesis selection. Freeze every model output
before evaluation;paired comparison uses exactly the same camera evidence/timestamps,
with duplicate camera rays not counted as independent fused target points. No epsilon
change,deletion-based improvement,core model replacement,new render or formalCases1–3.
Only same-evidence gain plus GT isolation,sufficient authority and acceptable downstream
availability can yieldMODEL_UPGRADE_VALIDATED;otherwise reportPROMISING orINSUFFICIENT.
### Frozen results / bounded model comparison

**Classification: MODEL_UPGRADE_PROMISING, not MODEL_UPGRADE_VALIDATED.** The authority
preflight is still insufficient for formal accuracy claims. This is **PILOT / SYNTHETIC
SAMPLE** only. There is same-evidence point improvement on eligible auditorium pairs;
there is no measured improvement to existing GAP reconstruction.

Projection became the priority because S06 and the sensitivity round showed healthy
Graph/Search termination with inaccurate inverse-projected endpoints. Far-distance/grazing
ray-plane conditioning and calibration copies amplified noise; no implementation bug was
found. Conditioning mitigation did not repair coordinates: B was a warning, D was the same
plane, and C's lower retained RMS discarded evidence. C-standard lost every office recovery
segment, preventing downstream reconstruction. Model upgrades must preserve evidence counts
and measure point gains on identical inputs, rather than lower error through endpoint loss.

#### Actual variants and same-evidence comparison

Four existing streams, 31 controls each: **124 frozen model cases**. A/B/F keep all5,549
observed point trials (179original points repeated under fixed controls), identical A
coordinates/quality, and unchanged Coverage epsilon0.02BU. A executes62office/corridor
reconstructions, allCOMPLETE with3routes/6timing hypotheses each. B/F cite those exact-coordinate
metrics; no uncertainty-aware Graph consumer is claimed. Per-case ADE/FDE/minADE@K/minFDE@K/
Coverage@K forK1/2/3 are inJSON/CSV. Auditorium/classroom baseline GAP metrics areN/A;
C/D/E reconstruction metrics areN/A, not fabricated zero or comparison wins.

C closest-ray triangulation accepts33/33eligible auditorium pairs in every treatment:
33/49visible timestamps (67.35%),66/82camera observations; other three sites have0pairs.
All legal pairs retain evidence refs, source/target/exact-time/pixels and diagnostic hypothesis
provenance; deterministic pair IDs do not select a GT-best pair. No asynchronous matching,
GT alignment, fixed-plane fallback or evidence deletion is counted as a triangulation success.
Every existing GAP endpoint lacks paired evidence, so C downstream is fail-closed
NOT_RUN_NO_SYNCHRONIZED_ENDPOINTS. No new Graph projection adapter was introduced.

The comparison baseline is a **predeclared equal mean of the two fixed-plane predictions**,
using the same33timestamp pairs and both camera observations as C. Thus improvement is beyond
merely averaging two camera points. Pooled three fixed seeds (repeated trials, not independent
captures) give:

| Pixel half-width per u/v, px | Same-pair plane mean RMS, BU | C RMS, BU | Reduction |
| --- | ---: | ---: | ---: |
| 0 | 0.000603103 | 0.000175249 | 70.94% |
| 0.001 | 0.00254587 | 0.000809531 | 68.20% |
| 0.002 | 0.00496549 | 0.00158571 | 68.07% |
| 0.004 | 0.00985779 | 0.00315219 | 68.02% |
| 0.01 | 0.0245785 | 0.00786321 | 68.01% |
| 0.1 | 0.245555 | 0.0785704 | 68.00% |
| 0.25 | **0.613887** | **0.196418** | **68.004%** |

Seed20261006 at±0.25px:0.590293→0.192536BU (67.383%). All33eligible pairs remain
available. The joint four-coordinate pixel gain peaks1.016866BU/px over pixel controls;
its input norm differs from the earlier single-camera2D Jacobian peak12.604BU/px. The
old worst point at auditoriumt0 has no eligible pair; this experiment does not demonstrate
its repair or a global conditioning guarantee. Absolute±0.25px C error still exceeds the
unchanged0.02BU diagnostic tolerance. No formal Coverage improvement is inferred from RMS.

29/31auditorium controls improve; **cx±0.1px common-mode calibration copies degrade**:
0.0492675→0.105105BU (113.335%worse),0.0489112→0.105350BU (115.389%worse). The equal-plane
mean cancels part of this particular directional error; C is not universally calibration
robust. Other copies improve on this cohort: jointfocal±0.1% about75.98–76.08%,cy±0.1px
82.59–82.64%,pitch±0.01°83.11–83.16%,worldZ±0.1BU82.44%. These are shared parameter
copies of existing calibrations, not measured independent-camera uncertainty or a diagnosis
of original calibration error. No GT camera/pair/model selection is performed.

#### Approved surfaces / hypothesis availability

D/E cannot run school inference: approved physical surface count0; WALKABLE roles, WALL
annotations and HUMAN_REVIEW support geometry are not physical approval. Office's derived
asset cannot borrow original-scene authority. Read-only cdeee3e receipts bind the preflight;
parallel physical-authority code/working changes remain outside this branch.

Five separate SYNTHETIC_FIXTURE_ONLY controls reuse approved/source/floor/reference/footprint
gates. Unique hit1; multiple legal surfaces2hits retained with surface/evidence provenance;
review-only/wrongsource/wrongreference0hits. Frozen output retains the farther reference
hypothesis (post-freeze evaluation min-error0BU), without GT choosing a surface. Same approved
plane versus fixed plane has identical conditioning; there is no measured school accuracy
advantage or full downstream multi-surface integration. Hypothesis preservation is a contract
result, not evidence that Graph currently consumes multiple surfaces.

#### Additive uncertainty contract / limits

F emits analytic pixel-Jacobian and calibration-derivative covariance beside the unchanged
baseline point. Known injected uniform controls use sigma=halfwidth/√3; assigned calibration
copies use that diagnostic assumption. Source pixel/calibration measurements remain missing.
Plane/landmark-height uncertainty is unmodeled. Zero covariance isUNAVAILABLE_ZERO_VARIANCE,
not certainty; absent real sigma isUNMEASURED_ASSUMPTION. Calibration-only copies have rank1,
pixel controls rank2: these are conditional modeled subspaces, not full3D uncertainty.

Of5,549sidecars:3,863REVIEW_REQUIRED,1,149USABLE_WITH_UNCERTAINTY,537ZERO_VARIANCE.
Nominal radius≤0.02BU is a fixed **diagnostic** use-state budget, not a new Coverage threshold
or approved physical tolerance. All observations/points are retained; Graph does not yet
consume covariance, reweight candidates or reject endpoints. The additive state can express
usable-but-uncertain versus review/unavailable; downstream policy integration is still needed.

Conditional ellipsoid inclusion5011/5012≈99.980% is explicitly **not empirical95% probability
calibration**: Gaussian-style χ² ellipsoids tested against bounded controls and three fixed
seeds are conservative, partial and unmeasured. Maximum unsupported residual0.00178228BU
is separately reported. Full3D calibration remainsUNVALIDATED. No accuracy gain is claimed
for F; the improvement is diagnostic uncertainty/provenance, not changed point coordinates.

#### Reproducibility, runtime and preservation

All124cases/868inference artifacts plus surface hypotheses freeze before any GT access;
GT is then evaluation/debug-only. Three representative office/auditorium/classroom model
replays and GT poison are byte-identical, including uncertainty and camera-pair hypotheses.
Runtime inference reads are allowlisted. No GT fits planes/calibration or ranks/selects
models, cameras, pairs, surfaces, hypotheses or routes. The classification gate separately
requires same-evidence gain, GT isolation, authority and acceptable downstream availability.

An initial replay harness compared Python tuples with JSON-loaded lists and falsely reported
a mismatch. The saved model files were already byte-identical. Regression now compares
canonical persisted model SHA-256; this is a serialization-check fix, not a Projection bug.
The first run remains preserved; the same bounded controls were rerun inverified_run/, and
all124original/retry model file bytes match. Final explicit grade gate replay over frozen
results yieldsPROMISING. No sample or mathematical result changed to make validation pass.

Single-machine combined model+baseline-downstream runtime: median82.23ms/case,
range62.17–144.14ms. Per-variant overhead was not separately measured; this is not formal
runtime performance. Fourteen original source/pilot hash/size/mtime receipts,372pure input
hashes,4GTdigests and868frozen inference hashes are unchanged. Two saved charts were visually
inspected; all Fsidecars were independently revalidated against their strict additive schema.

#### Artifacts, blockers and next step

Local ignored root:
`data/pilot/phase1_projection_model_upgrade_20261006/verified_run/`.

- authority_preflight.json / protocol.json / receipts/: predeclared scope and pinned authority.
- cases/ / replay/ / inference_rows_before_gt.json / inference_freeze_before_gt.json:
  pure-source model outputs, unchanged baseline Top-K and isolation receipts.
- upgrade_results.json / machine_summary.json / upgrade_table.csv / report.md:
  same-evidence point errors, all baseline Kmetrics, availability, uncertainty and limitations.
- surface_models.json / surface_evaluation.json: separate frozen synthetic hypotheses/evaluation.
- multiview_error_availability.png / uncertainty_coverage_states.png / visualization_qa.json /
  verification.json: two inspected charts and preservation receipts.

Reproduce only into a fresh directory containing the sameprotocol/preflight:

```sh
uv run python scripts/compare_projection_upgrade.py \
  --mitigation-input data/pilot/phase1_projection_conditioning_mitigation_20261006 \
  --inventory data/pilot/phase1_projection_sensitivity_20261006/source_inventory.json \
  --output <fresh-directory-with-protocol-and-preflight>
uv run python scripts/report_projection_upgrade.py --experiment <fresh-directory>
```

**Projection remains the bottleneck where pairs are absent, including all existing GAP
endpoints. Case1–3 readiness remainsNO.** Source-specific camera/floor/landmark/approved
surfaces and architectural scale/tolerance must be approved; pixel/calibration/clock
uncertainty must be measured; synchronized departure/recovery evidence and a GT-free
hypothesis/uncertainty downstream policy must be validated. Multi-view point gains are
promising synthetic diagnostics, with principal-point degradation and availability limits.
Do not markMODEL_UPGRADE_VALIDATED until the four completion gates hold. No formal cases,
core replacement,metric/epsilon change,newdataset/render,merge or checkpoint rewrite.

Final frozen-code regression: **1166 passed in61.51s,no skips**; repositoryRuff and
mypy74sourcefiles pass. Working/stageddiffchecks and81localdocumentationlinks pass.
Only this independent branch is committed; checkpoint/origin5f020b0 remain unchanged.
No merge,newbranch push,formalCases1–3 or dataset expansion.
