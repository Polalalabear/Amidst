# Phase 1 finalization package / 收尾 package

Status: **PHASE1_FINALIZATION_BLOCKED**. Curated evidence is in `checkpoint/`.
Formal Cases 1–3 have not executed; the result matrix retains 27 N/A rows.

| Artifact | Role |
| --- | --- |
| [dataset_manifest.json](checkpoint/dataset_manifest.json) | 15 hash-bound diagnostic source-export artifacts; simulation/GT isolated |
| [input_lock.json](checkpoint/input_lock.json) | Pinned physical/projection/source/config/policy identities; formal settings pending |
| [benchmark_table.md](checkpoint/benchmark_table.md) | All Case/method/K rows, explicit N/A/NOT_CERTIFIED |
| [baseline_regression.json](checkpoint/baseline_regression.json) | 21 executed fixture comparisons, 3 N/A ablation-reference rows; not school results |
| [reproducibility.json](checkpoint/reproducibility.json) | Fresh physical/dataset/inference/baseline/reader comparison |
| [fresh_report_reproducibility.json](checkpoint/fresh_report_reproducibility.json) | 19 generated report artifacts byte-identical |
| [physical_reproducibility.json](checkpoint/physical_reproducibility.json) | Four raw physical hashes and unchanged partial authority |
| [exit_gate.json](checkpoint/exit_gate.json) | Blocked exit with the minimum authority gate |
| [package_hashes.json](checkpoint/package_hashes.json) | Curated artifact hashes; self hash explicitly excluded |
| [artifact_inventory.csv](checkpoint/artifact_inventory.csv) | KEEP/ARCHIVE/REGENERABLE; no deletion |

Formal accuracy/Coverage/search/physical charts show N/A because there are no formal
measurements. `projection_methods.png` and `projection_confidence.png` show only
diagnostic timestamp populations; LOW_CONFIDENCE never removes observations.

Raw `local_run/` and `fresh_run/` are ignored. Durable local copies, including the
three recordings/previews and historical drafts, are saved under the canonical repo's
ignored `data/pilot/phase1_finalization_20261006/`. Source `.blend` and large physical
evidence remain local. No dataset blob, RRD or large render is published.

見 [final report](../../docs/PHASE1_FINAL_REPORT.md)、
[reproduction](../../docs/PHASE1_REPRODUCTION.md)、
[human review](../../human_review/README.md)。Physical/local-navigation、camera-landmark/floor
語意與正式研究容差須先經唯一 gate；agent 再計算 certificate/route/time inventory。
Case4 DEFERRED，Phase2 FROZEN，blocked checkpoint 不建 freeze tag。
