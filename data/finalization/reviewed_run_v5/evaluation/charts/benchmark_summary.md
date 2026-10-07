# MIXED INPUT — BLENDER RESEARCH RESULT (SUPPLIED PROVENANCE); UNVERIFIED INPUT — Benchmark Comparison

Equal-run means use only measured values. Every value has available/total run counts in JSON; missing values remain N/A. Failed and missing cases stay visible. Method order follows input identities and never Ground Truth accuracy.

| Case | Method | Status | Runs | K | ADE (m) | FDE (m) | minADE@K (m) | minFDE@K (m) | Coverage@K | Collision | Constraint | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case1 | Shortest Path | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 0.0284172 |
| case1 | Geometry Graph | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 0.0285158 |
| case1 | Spatiotemporal Graph | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 0.0283014 |
| case2 | Shortest Path | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case2 | Geometry Graph | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case2 | Spatiotemporal Graph | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case3 | Shortest Path | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 0.082836 |
| case3 | Geometry Graph | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 0.0838585 |
| case3 | Spatiotemporal Graph | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 0.0844979 |

## Acceptance categories

| Category | Available rows | Partial rows | Missing rows | Acceptance |
| --- | --- | --- | --- | --- |
| GEOMETRIC_ACCURACY | 6 | 0 | 3 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| PHYSICAL_VALIDITY | 6 | 0 | 3 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TOP_K_COVERAGE | 6 | 0 | 3 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TEMPORAL_VALIDITY | 6 | 0 | 3 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SEARCH_BEHAVIOR | 6 | 0 | 3 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SYSTEM_RUNTIME | 6 | 0 | 3 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |

## Availability and review

- case1 / Shortest Path: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / Geometry Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / Spatiotemporal Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case2 / Shortest Path: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case2 / Geometry Graph: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case2 / Spatiotemporal Graph: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case3 / Shortest Path: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / Geometry Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / Spatiotemporal Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1

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
