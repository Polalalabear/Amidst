# Phase 1 reviewed local benchmark

Date: 2026-10-07. This additive document preserves
[the original protocol](PHASE1_BENCHMARK_PROTOCOL.md) and its machine-readable
bytes. The canonical fresh run is `reviewed_run_v5`, with the unchanged frozen
V2 configuration and newly approved reference movement policy. Its dataset,
primary inference, evaluation and ready-case reproduction checks are complete.
Overall status remains **PHASE1_FINALIZATION_BLOCKED**: Case 2 lacks approved
branching scope and Case 3's full detour/candidate-growth stress is unavailable.
Earlier diagnostic/V3 outputs and the preserved partial V4 export are historical
records.

## Research population and authority

Cases 1 and 3 use **FORMAL local synthetic evidence** after their per-case
automatic readiness proofs pass. Frozen configuration waypoints are sampled against the
unchanged source cameras and actual Blender mesh raycaster to produce strict 2D
evidence. They are configuration-sampled source-camera observations, not real
capture, CV detections, or an animated Blender actor. Source geometry, source
cameras and their poses remain unchanged. GT belongs only to simulation/export,
independent evaluation and the optional, initially hidden debug layer.

The reviewed physical scope is
`school-v3:reviewed-physical-island:450c93b7752f1677b305`, within
`WALK_1F_OFFICE` on 1F. Its XY footpoint bounds are
X=[1399.9985317206952, 1411.9999242955855] BU and
Y=[1939.9994361310253, 2096.8005463472678] BU; the approved source support height
is 20.07884979248047 BU. The complete local certificate retains the original
bounded human semantic receipt. Whole-school physical authority remains
**PARTIAL_APPROVED**. Unknown walls, portal conflicts, stair paths and whole
obstacle ownership are not upgraded by these results.

## Frozen settings

| Setting | Reviewed value |
| --- | --- |
| Protocol | `phase1-benchmark-protocol-v1` |
| Scale | 1 BU = 0.0247 m |
| Source scene | `school_v3.blend`; unchanged; 468,300,506 bytes |
| Export / inference seeds | 20261005 / 42 |
| Source sampling | 5 Hz; source endpoints inclusive; no rejection |
| Coverage | D=ADE; strict ADE < 0.50 m; K=[1,2,3] |
| Evaluation alignment | Piecewise-linear at every reference timestamp; exact extent; no clipping/extrapolation |
| Primary route and Top-K timing | First timing per distinct route in deterministic caller order |
| Physical-rate population | All emitted timing hypotheses, including explicit dwell; counted once independently of K rows |
| Maximum speed / direct slack | 32 BU/s = 0.7904 m/s / 1.0 s |
| Timing alternatives | Uniform continuous first; departure waypoint dwell only |
| Eligibility | One canonical direct representative per source-distinct route class |
| Search budget | 3 candidates; 1000 expanded states; 24.7 m maximum path length; 10 s search time; branch factor 3; detour ratio 2 |
| Pixel-noise sigma | Unavailable (`null`); no claimed pixel-noise accuracy model |
| Cross-case aggregation | None; no overall Coverage target PASS claimed |

The V2 export envelope adds only the newly approved reference movement policy;
the original V1 routes, schedules, sampling, seeds and budgets remain unchanged.
Its separate GT-free V2 inference lock contains source/receipt hashes and
inference settings, with reference-policy lineage hashes. It excludes source
waypoints, reference positions and movement annotation values.

The approved reference policy is
`EXPLICIT_SIMULATION_SEGMENT_MOVEMENT_ANNOTATIONS`: distinct floor-contact recipe
endpoints are explicitly **MOVING**; exactly identical endpoints are **DWELL**.
Reference moving time sums the durations of annotated MOVING segments intersected
with the exact observed gap. Candidate moving time excludes its explicit dwell.
Travel-time Error is the absolute difference of those independently computed
moving times; it is not inferred solely from shared gap start/end times. The
approval receipt, rather than the immutable proposal's old `PROPOSED` label,
authorizes the new versioned export. Earlier N/A results remain historical.

## Case readiness and result identity

| Case | Canonical V5 execution | Original case scope |
| --- | --- | --- |
| 1 — Single Feasible Route | FORMAL / EVALUATED local run | One major source-distinct route; fresh visible→GAP→visible proved at t=4.2→8.6 s |
| 2 — Branching | BLOCKED_SCOPE / N/A | Approved rectangle has one route class and zero branches; configured offsets/timing duplicates do not supply the required ≥2 distinct routes |
| 3 — Temporal Slack / Long Gap | FORMAL / EVALUATED temporal component | Actual source gap t=14.0→166.4 s =152.4 s; minimum travel 2.1166854064 s; ratio 71.99936 |
| 3 — Full detour/candidate-growth stress | BLOCKED_SCOPE | No approved distinct detour branch exists in the complete office rectangle |
| 4 — Cross-floor / Stair | DEFERRED | Phase 2 remains FROZEN |

Case 2's precise blocker is
`CASE2_REQUIRES_SOURCE_DISTINCT_BRANCHES_OUTSIDE_APPROVED_RECTANGLE`.
The [bounded source-scope audit](PHASE1_BRANCH_SCOPE_GATE.md) tested 116 explicit
two-sided proposals around 58 approved closed components. Twenty-six had
distinct source cameras framing endpoints, but none passed all approved contact
and body-clearance segments. This finite candidate family is not a global
exhaustive school search. Its `PROPOSAL_NOT_AVAILABLE` status supplies concrete
source coordinates/hashes without granting another scope or asking the user to
organize a new dataset.

The formal A/B/C comparison retains A=`shortest_path`, B=`geometry`, and
C=`spatiotemporal`. Executed single-factor variants are `remove_travel_time`,
`remove_topology`, and `shortest_path_only`; the `full_deterministic_graph` row
reproduces the deterministic reference. `remove_collision` remains an explicit
**N/A / UNAVAILABLE** row because no separate approved collision consumer was
supplied for that ablation; the full reviewed physical scope is preserved. Every row
keeps its case/method/ablation/K identity and the same input/metric population.
Blocked, empty and unavailable rows remain visible as JSON null / table N/A.
The single approved route class cannot demonstrate Top-K branching diversity or
meaningful candidate growth; available K never receives duplicate padding.

## Canonical V5 measurements and bindings

The dataset manifest records 50 timestamps / 100 camera records for Case 1
(29 observed, 71 GAP), and 925 timestamps / 1850 records for Case 3 (164 observed,
1686 GAP). Each case uses two source cameras; the GAP record counts include each
camera separately and do not mean that every timestamp is jointly blind.

Primary inference was frozen before evaluation: 32 canonical artifact hashes,
`ground_truth_read=false`. Both executed cases emitted one distinct direct route
with two admissible timings: uniform continuous first and departure dwell second.
All A/B/C runs and executed variants expanded two states and terminated
**COMPLETE** within the frozen eligibility/budgets. This is complete for the
declared local representative, not an exhaustive whole-school route search.

| Case | Observed gap, s | Primary route, m | Minimum travel, s | Slack / alternate departure dwell, s | Distinct routes / timing hypotheses |
| --- | --- | --- | --- | --- | --- |
| 1 | 4.4 | 1.7300252052 | 2.1887970714 | 2.2112029286 | 1 / 2 |
| 3 temporal component | 152.4 | 1.6730281453 | 2.1166854064 | 150.2833145936 | 1 / 2 |

| Method | Case 1 measured inference call, s | Case 3 measured inference call, s |
| --- | --- | --- |
| A — shortest_path | 0.028417166 | 0.082836000 |
| B — geometry | 0.028515750 | 0.083858458 |
| C — spatiotemporal | 0.028301417 | 0.084497916 |

These are the method adapter/search/reconstruction call measurements in the
primary `runtime.json`; shared projection preprocessing, export, evaluation and
report generation are outside this timer. Runtime and RRD container metadata are
not canonical determinism comparisons. Candidate growth is N/A because there
are no approved branching routes; many input timestamps or alternate timings do
not supply a growth experiment.

The [complete JSON table](../../data/finalization/reviewed_run_v5/evaluation/benchmark_table.json)
and [CSV](../../data/finalization/reviewed_run_v5/evaluation/benchmark_table.csv) retain
all 27 Case 1–3 × A/B/C × K rows: 18 FORMAL/EVALUATED local rows and nine
Case 2 BLOCKED/N/A rows. Within each executed case the A/B/C accuracy and
Coverage values coincide because the eligible source inventory contains one
route. The compact table below groups those equal values; it does not average
methods, cases or K.

| Case / methods / K | ADE, m | FDE, m | minADE@K, m | minFDE@K, m | Coverage@K |
| --- | --- | --- | --- | --- | --- |
| 1 / A, B, C / each K=1,2,3 | 1.5968095443e-5 | 7.3903094270e-6 | 1.5968095443e-5 | 7.3903094270e-6 | true |
| 2 / A, B, C / each K=1,2,3 | N/A | N/A | N/A | N/A | N/A |
| 3 temporal / A, B, C / each K=1,2,3 | 1.4052783775e-5 | 3.1522708545e-6 | 1.4052783775e-5 | 3.1522708545e-6 | true |

Reference error uses all 23 exact gap timestamps in Case 1 and all 763 in Case 3.
There is one selected route for every K; the dwell alternative does not become a
second route or enter the Top-K oracle minima. These small errors measure
configuration-sampled source geometry/projection parity, without a real sensor,
CV uncertainty model or a branching generalization experiment.

| Case / A,B,C | Mean projection error, m / matched samples | Path-length error, m | Feasible candidate recall | Local collision / constraint violations | Impossible local handoffs |
| --- | --- | --- | --- | --- | --- |
| 1 | 2.5567980915e-5 / 29 | 1.7041931752e-5 | 1/1 = 1 | 0/3 = 0 / 0/3 = 0 | 0/1 = 0 |
| 3 temporal | 2.0172611977e-5 / 164 | 1.4811918098e-5 | 1/1 = 1 | 0/3 = 0 / 0/3 = 0 | 0/1 = 0 |

The three physical segments per method/run cover both timings, including the
stationary dwell segment; K rows do not multiply that denominator. Blender
physical validity comes from the retained reviewed provider/certificate and
`reviewed_physical`, not the preserved core computation payload's empty AABB
list. Legacy synthetic computation labels are retained inside that payload;
the additive reviewed authority supplies the approved metric/physical scope.
Feasible recall uses the independent source-distinct-class denominator under
the frozen eligibility, not emitted corridors or GT. Impossible Transition Rate
counts the one observed directed endpoint-camera handoff per distinct route;
hidden intermediate camera sequences and school-wide portals are outside this
schema and authority.

### Approved moving-time measurements

Both fresh references explicitly annotate movement throughout the observed gap
and no reference dwell. The first uniform timing therefore has moving-time
error zero. The alternate departure dwell has a different independently
measured error despite sharing the same gap extent:

| Case | Reference MOVING / DWELL, s | Primary MOVING / Travel-time Error, s | Alternate DWELL hypothesis MOVING / Travel-time Error, s |
| --- | --- | --- | --- |
| 1 | 4.4 / 0 | 4.4 / 0 | 2.1887970714 / 2.2112029286 |
| 3 temporal | 152.4 / 0 | 152.4 / 0 | 2.1166854064 / 150.2833145936 |

The values are `AVAILABLE_APPROVED_REFERENCE_MOVEMENT`, bound to the new receipt
and fresh reference annotation hashes. Primary selection remains the first
timing; reference errors did not choose, rank or prune a timing. Both timings
remain deterministic admissible hypotheses without calibrated behavioral
probabilities. Per-hypothesis values are retained in each case's
`spatiotemporal_additional_metrics.json`.

### Projection limits, charts and verification

| Case | SINGLE_VIEW_FIXED_PLANE / LOW_CONFIDENCE timestamps | Projection UNAVAILABLE timestamps | Uncertainty available |
| --- | --- | --- | --- |
| 1 | 29 / 29 | 21 | 0/50 |
| 3 temporal | 164 / 164 | 761 | 0/925 |

The policy still prefers legal exact-time multiview; these office runs have no
selected usable multiview timestamps. Pixel sigma remains null, confidence is
not a calibrated probability, and all raw camera records remain present. The
absence of usable multiview does not invalidate the approved single-view
fallback. Surface-constrained inference is explicitly
`N/A_UNAPPROVED_SCHOOL_SURFACE_AUTHORITY`.

Twenty plots cover projection error/method/confidence/uncertainty, ADE/FDE and
Top-K minima/Coverage, physical rates, feasible recall, path/moving-time error,
candidates, search expansions, runtime and termination. Each ready case has a
reader-verified RRD, static preview and replay instructions; GT debug is
independent and initially off. There is no Case 2 formal demo.

The canonical [reproduction receipt](../../data/finalization/reviewed_run_v5/reproduction/verification.json)
records actual **PASS** for repeat, fresh process, reordered observations,
GT poison and bounded termination. Both movement annotation files were also
malformed during poison testing; inference remained unchanged, while the
separate poisoned GT changed evaluated errors. Those comparisons include
candidate order and termination; measured runtime/RRD container bytes are
excluded. They apply to ready Cases 1 and 3, and do not enable an overall freeze
or replace the original clean-checkout/full-sprint Exit Gate.

| Immutable binding | SHA-256 |
| --- | --- |
| Source `.blend` | `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e` |
| Original protocol file | `2f88aabe108c217aac43466b118de75fbed53ba16c6068cb24bf082bae714ac7` |
| HR-01–HR-04 decision content | `8df8cda06dd9fd0848bc39395d4c6b5c695aae30b3f5329b4c0d30ff7fea085a` |
| Reviewed physical certificate content | `7c068355477603f5456498222f9576970aaf7c7f43674f972910d43e5a0d23b1` |
| Bounded semantic review content | `a945047cd46a44eaa0eaf25526628a770aa849b75bb85ddd038a5093510366d5` |
| New movement-policy content | `f7452152ff8981287033aa9b75c8faab1841df2981fe59de74a54e5403f45c73` |
| New movement approval receipt content | `972fc01f5026311de52c934dd8315e1ee35bef9cf800af88b91b07d44e01d5ac` |
| V2 export file | `3afd62816463896259bc9b2a2c54889a761ee1665a9e6933173213a51c2d2223` |
| V2 GT-free inference lock file | `6507483100dda089341a317bd412946fecafedcfa4c4ac3a6b75d8b7171c8f24` |
| Canonical V5 dataset manifest file | `a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5` |
| Canonical V5 primary inference freeze file | `d16708cfb437b6dff2ea06139126d5784a181c547d9dba6d1633068988cf4059` |
| Canonical V5 benchmark JSON file | `9f660a7ae0d1024937a9885c9314dea6d343dcf4a2351ce3d14fb96afce501fa` |
| Canonical V5 benchmark CSV file | `ee20af76e9ad3b4f197f7982658413a08317b10b806081acfeb8f6df1a0d75b7` |
| Canonical V5 evaluation verification file | `3d513ef039008ad038a540cf185a62c0f8c558a07f2cba46a03f28ae742aaa56` |
| Canonical V5 dataset acceptance file | `56e135edd33cc92d8c133885b449d3c4b292fb85c27063bae3f5579a2ca840a7` |
| Canonical V5 reproduction verification file | `9020af0f8f8e1ac3098096a711a50d8dd927b5d6e3bec1fe96c68d6415d9a4d1` |

Reproduction entrypoints and local raw artifact boundaries are maintained in
[the reviewed reproduction guide](PHASE1_REVIEWED_REPRODUCTION.md). The source,
raw dataset, RRD and full physical/render evidence remain local; curated tables,
charts and hash manifests are the publication evidence.
