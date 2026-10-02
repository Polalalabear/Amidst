# MOCK VALIDATION — Benchmark Comparison

Equal-run means use only measured values. Every value has available/total run counts in JSON; missing values remain N/A. Failed and missing cases stay visible. Method order follows input identities and never Ground Truth accuracy.

| Case | Method | Status | Runs | K | ADE (m) | FDE (m) | minADE@K (m) | minFDE@K (m) | Coverage@K | Collision | Constraint | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case1 | Shortest Path | COMPLETE:2 | 2 | 3 | 2 | 1.25 | 0.4 | 0.25 | 1 | 0 | 0.1 | 0.075 |
| case1 | Geometry Graph | COMPLETE:1 | 1 | 3 | 2 | 1 | 0.4 | 0.2 | 1 | 0.2 | 0 | 0.1 |
| case1 | Spatiotemporal Graph | COMPLETE:1 | 1 | 3 | 3 | 1.5 | 0.6 | 0.3 | 1 | 0.1 | 0.3 | 0.15 |
| case2 | Shortest Path | COMPLETE:1 | 1 | 3 | 2 | 1 | 0.4 | 0.2 | 1 | 0 | 0.1 | 0.1 |
| case2 | Geometry Graph | COMPLETE:1 | 1 | 3 | 3 | 1.5 | 0.6 | 0.3 | 1 | 0.2 | 0 | 0.15 |
| case2 | Spatiotemporal Graph | COMPLETE:1 | 1 | 3 | 4 | 2 | 0.8 | 0.4 | 1 | 0.1 | 0.3 | 0.2 |
| case3 | Shortest Path | COMPLETE:1 | 1 | 3 | 3 | 1.5 | 0.6 | 0.3 | 1 | 0 | 0.1 | 0.15 |
| case3 | Geometry Graph | COMPLETE:1 | 1 | 3 | 4 | 2 | 0.8 | 0.4 | 1 | 0.2 | 0 | 0.2 |
| case3 | Spatiotemporal Graph | COMPLETE:1 | 1 | 3 | 5 | 2.5 | 1 | 0.5 | 1 | 0.1 | 0.3 | 0.25 |
| no_reference | Shortest Path | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| no_reference | Geometry Graph | NO_REFERENCE:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0.02 |
| no_reference | Spatiotemporal Graph | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| failed | Shortest Path | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| failed | Geometry Graph | INPUT_REJECTED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| failed | Spatiotemporal Graph | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| empty_candidates | Shortest Path | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| empty_candidates | Geometry Graph | NO_FEASIBLE_PATH:1 | 1 | 3 | N/A | N/A | N/A | N/A | 0 | N/A | N/A | 0.03 |
| empty_candidates | Spatiotemporal Graph | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| missing_case | Shortest Path | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| missing_case | Geometry Graph | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| missing_case | Spatiotemporal Graph | MISSING_RUN:1 | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

## Acceptance categories

| Category | Available rows | Partial rows | Missing rows | Acceptance |
| --- | --- | --- | --- | --- |
| GEOMETRIC_ACCURACY | 9 | 0 | 12 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| PHYSICAL_VALIDITY | 9 | 0 | 12 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TOP_K_COVERAGE | 10 | 0 | 11 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TEMPORAL_VALIDITY | 9 | 0 | 12 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SEARCH_BEHAVIOR | 9 | 2 | 10 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SYSTEM_RUNTIME | 11 | 0 | 10 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |

## Availability and review

- case1 / Shortest Path: projection_error_m=1/2, ade_m=2/2, fde_m=2/2, min_ade_at_k_m=2/2, min_fde_at_k_m=2/2, feasible_candidate_recall=1/2, collision_rate=1/2, constraint_violation_rate=1/2, impossible_transition_rate=1/2, path_length_error_m=1/2, travel_time_error_s=1/2, runtime_s=2/2, candidate_count=2/2, search_nodes=2/2; Coverage@1=2/2, Coverage@2=2/2, Coverage@3=2/2
- case1 / Geometry Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / Spatiotemporal Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case2 / Shortest Path: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case2 / Geometry Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case2 / Spatiotemporal Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / Shortest Path: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / Geometry Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / Spatiotemporal Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- no_reference / Shortest Path: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- no_reference / Geometry Graph: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1
- no_reference / Spatiotemporal Graph: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- failed / Shortest Path: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- failed / Geometry Graph: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1
- failed / Spatiotemporal Graph: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- empty_candidates / Shortest Path: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- empty_candidates / Geometry Graph: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- empty_candidates / Spatiotemporal Graph: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- missing_case / Shortest Path: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- missing_case / Geometry Graph: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0
- missing_case / Spatiotemporal Graph: projection_error_m=0/0, ade_m=0/0, fde_m=0/0, min_ade_at_k_m=0/0, min_fde_at_k_m=0/0, feasible_candidate_recall=0/0, collision_rate=0/0, constraint_violation_rate=0/0, impossible_transition_rate=0/0, path_length_error_m=0/0, travel_time_error_s=0/0, runtime_s=0/0, candidate_count=0/0, search_nodes=0/0

## Chart artifacts

- [projection_error.png](projection_error.png)
- [accuracy_ade.png](accuracy_ade.png)
- [accuracy_fde.png](accuracy_fde.png)
- [accuracy_minade_at_k.png](accuracy_minade_at_k.png)
- [accuracy_minfde_at_k.png](accuracy_minfde_at_k.png)
- [feasible_recall.png](feasible_recall.png)
- [collision_rate.png](collision_rate.png)
- [constraint_rate.png](constraint_rate.png)
- [impossible_transition_rate.png](impossible_transition_rate.png)
- [path_length_error.png](path_length_error.png)
- [travel_time_error.png](travel_time_error.png)
- [runtime.png](runtime.png)
- [candidate_count.png](candidate_count.png)
- [search_nodes.png](search_nodes.png)
- [coverage_at_k.png](coverage_at_k.png)
- [physical_validity.png](physical_validity.png)
- [termination_categories.png](termination_categories.png)

## Skipped charts


Native metrics reflect configured synthetic AABB/corridor checks; they do not certify Blender mesh physics. Missing Projection Error, impossible transitions, feasible recall, path/time errors are never inferred from other measurements.
Formal Coverage distance/epsilon, clearance and contact semantics require an approved protocol. A supplied provenance label is not independent certification.
