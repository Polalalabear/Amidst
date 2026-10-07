# MIXED INPUT — BLENDER RESEARCH RESULT (SUPPLIED PROVENANCE); UNVERIFIED INPUT — Benchmark Comparison

Equal-run means use only measured values. Every value has available/total run counts in JSON; missing values remain N/A. Failed and missing cases stay visible. Method order follows input identities and never Ground Truth accuracy.

| Case | Method | Status | Runs | K | ADE (m) | FDE (m) | minADE@K (m) | minFDE@K (m) | Coverage@K | Collision | Constraint | Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| case1 | Spatiotemporal Graph | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 1.75354 |
| case1 | remove_travel_time | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 1.76605 |
| case1 | remove_collision | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 1.69072 |
| case1 | remove_topology | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 1.76603 |
| case1 | shortest_path_only | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 1.78717 |
| case1 | full_deterministic_graph | EVALUATED:1 | 1 | 3 | 1.59681e-05 | 7.39031e-06 | 1.59681e-05 | 7.39031e-06 | 1 | 0 | 0 | 1.81154 |
| case2 | Spatiotemporal Graph | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case2 | remove_travel_time | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case2 | remove_collision | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case2 | remove_topology | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case2 | shortest_path_only | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case2 | full_deterministic_graph | BLOCKED:1 | 1 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| case3 | Spatiotemporal Graph | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 1.83214 |
| case3 | remove_travel_time | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 1.85137 |
| case3 | remove_collision | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 1.82214 |
| case3 | remove_topology | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 1.84815 |
| case3 | shortest_path_only | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 1.84343 |
| case3 | full_deterministic_graph | EVALUATED:1 | 1 | 3 | 1.40528e-05 | 3.15227e-06 | 1.40528e-05 | 3.15227e-06 | 1 | 0 | 0 | 1.84627 |

## Acceptance categories

| Category | Available rows | Partial rows | Missing rows | Acceptance |
| --- | --- | --- | --- | --- |
| GEOMETRIC_ACCURACY | 12 | 0 | 6 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| PHYSICAL_VALIDITY | 12 | 0 | 6 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TOP_K_COVERAGE | 12 | 0 | 6 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| TEMPORAL_VALIDITY | 12 | 0 | 6 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SEARCH_BEHAVIOR | 12 | 0 | 6 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |
| SYSTEM_RUNTIME | 12 | 0 | 6 | NOT_ASSESSED / UNRESOLVED_RESEARCH_SETTING |

## Availability and review

- case1 / Spatiotemporal Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / remove_travel_time: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / remove_collision: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / remove_topology: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / shortest_path_only: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case1 / full_deterministic_graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case2 / Spatiotemporal Graph: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case2 / remove_travel_time: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case2 / remove_collision: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case2 / remove_topology: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case2 / shortest_path_only: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case2 / full_deterministic_graph: projection_error_m=0/1, ade_m=0/1, fde_m=0/1, min_ade_at_k_m=0/1, min_fde_at_k_m=0/1, feasible_candidate_recall=0/1, collision_rate=0/1, constraint_violation_rate=0/1, impossible_transition_rate=0/1, path_length_error_m=0/1, travel_time_error_s=0/1, runtime_s=0/1, candidate_count=0/1, search_nodes=0/1; Coverage@1=0/1, Coverage@2=0/1, Coverage@3=0/1
  - REVIEW: Benchmark provenance is missing or lacks formal approval evidence
- case3 / Spatiotemporal Graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / remove_travel_time: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / remove_collision: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / remove_topology: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / shortest_path_only: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1
- case3 / full_deterministic_graph: projection_error_m=1/1, ade_m=1/1, fde_m=1/1, min_ade_at_k_m=1/1, min_fde_at_k_m=1/1, feasible_candidate_recall=1/1, collision_rate=1/1, constraint_violation_rate=1/1, impossible_transition_rate=1/1, path_length_error_m=1/1, travel_time_error_s=1/1, runtime_s=1/1, candidate_count=1/1, search_nodes=1/1; Coverage@1=1/1, Coverage@2=1/1, Coverage@3=1/1

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
