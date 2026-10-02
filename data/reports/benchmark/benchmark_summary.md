# SYNTHETIC REGRESSION — Benchmark Comparison

Equal-run means use only measured values. Every value has available/total run counts in JSON; missing values remain N/A. Failed and missing cases stay visible. Method order follows input identities and never Ground Truth accuracy.

| Case | Method | Status | Runs | K | ADE (m) | FDE (m) | minADE@K (m) | minFDE@K (m) | Coverage@K | Collision | Constraint | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| branching_top_k | Configured Deterministic Graph | COMPLETE:1 | 1 | 3 | 7.80211 | 0 | 2.70786e-17 | 0 | 1 | 0 | 0 | 0.00365883 |
| simplified_stair | Configured Deterministic Graph | COMPLETE:1 | 1 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0.00220367 |
| single_path | Configured Deterministic Graph | COMPLETE:1 | 1 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0.00208796 |
| temporal_slack | Configured Deterministic Graph | COMPLETE:1 | 1 | 3 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0.00236542 |

## Acceptance categories

| Category | Available rows | Partial rows | Missing rows | Acceptance |
| --- | --- | --- | --- | --- |
| GEOMETRIC_ACCURACY | 0 | 4 | 0 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| PHYSICAL_VALIDITY | 0 | 4 | 0 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TOP_K_COVERAGE | 4 | 0 | 0 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TEMPORAL_VALIDITY | 0 | 0 | 4 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SEARCH_BEHAVIOR | 0 | 4 | 0 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SYSTEM_RUNTIME | 4 | 0 | 0 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |

## Availability and review

- branching_top_k / Configured Deterministic Graph: projection_error_m=0/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=0/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=1/1, candidate_count=1/1, search_nodes=0/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- simplified_stair / Configured Deterministic Graph: projection_error_m=0/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=0/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=1/1, candidate_count=1/1, search_nodes=0/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- single_path / Configured Deterministic Graph: projection_error_m=0/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=0/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=1/1, candidate_count=1/1, search_nodes=0/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- temporal_slack / Configured Deterministic Graph: projection_error_m=0/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=0/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=1/1, candidate_count=1/1, search_nodes=0/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1

## Chart artifacts

- [accuracy_ade.png](accuracy_ade.png)
- [accuracy_fde.png](accuracy_fde.png)
- [accuracy_minade_at_k.png](accuracy_minade_at_k.png)
- [accuracy_minfde_at_k.png](accuracy_minfde_at_k.png)
- [collision_rate.png](collision_rate.png)
- [constraint_rate.png](constraint_rate.png)
- [runtime.png](runtime.png)
- [candidate_count.png](candidate_count.png)
- [coverage_at_k.png](coverage_at_k.png)
- [physical_validity.png](physical_validity.png)
- [termination_categories.png](termination_categories.png)

## Skipped charts

- projection_error.png: projection_error_m: no measured values; all rows are N/A
- feasible_recall.png: feasible_candidate_recall: no measured values; all rows are N/A
- impossible_transition_rate.png: impossible_transition_rate: no measured values; all rows are N/A
- path_length_error.png: path_length_error_m: no measured values; all rows are N/A
- travel_time_error.png: travel_time_error_s: no measured values; all rows are N/A
- search_nodes.png: search_nodes: no measured values; all rows are N/A

Native metrics reflect configured synthetic AABB/corridor checks; they do not certify Blender mesh physics. Missing Projection Error, impossible transitions, feasible recall, path/time errors are never inferred from other measurements.
Formal Coverage distance/epsilon, clearance and contact semantics require an approved protocol. A supplied provenance label is not independent certification.
