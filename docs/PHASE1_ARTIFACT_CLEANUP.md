# Phase 1 artifact cleanup / Artifact 整理

Status: **inventory only** after completed diagnostic verification. Formal validation remains blocked. No artifact was deleted.

保留 source/config/tests/docs、experiment log、reports、manifests/hashes。Raw dataset、RRD、Blender 和大型物理證據只在本機保存。ARCHIVE 是分類，沒有移動或刪除 inherited provenance。

DELETE_CANDIDATE: none selected; no automatic deletion is authorized.

2026-10-07 review supplement: `human_review/frames/spatial_context/*.png` contains
28 locally retained source-model diagnostic views (3 stills +25 camera frames), classified
REGENERABLE. Its separate manifest, HTML/template/builder, exact successful producer archive
and current renderer are KEEP. Regeneration uses the archived producer staged at its original
path in a fresh materialized checkout, then `uv run python human_review/build_spatial_guide.py`;
see [review guide](../human_review/README.md). Original 57 images and all source/decision files
remain unchanged. Only this task's generated mypy/pytest caches were discarded after a
storage error; no source, render, evidence or DELETE_CANDIDATE item was deleted.

| Path | Category | Size (bytes) | Reason | Canonical replacement | Regeneration |
| --- | --- | --- | --- | --- | --- |
| src | KEEP | 2193916 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| scripts | KEEP | 1151850 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| configs | KEEP | 46797 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| tests | KEEP | 4134870 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| docs | KEEP | 417549 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| human_review | KEEP | 379737 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| data/finalization/checkpoint | KEEP | 344150 | source/config/tests/docs or checkpoint evidence | this published finalization branch | git checkout <published-finalization-SHA> |
| data/finalization/local_run/baseline_regression.json | REGENERABLE | 33402 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/dataset | REGENERABLE | 214602 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/dataset_provenance_draft | ARCHIVE | 214404 | retained pre-final diagnostic draft | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics | REGENERABLE | 15860041 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json_pre_preview | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json_pre_reader | REGENERABLE | 26739 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_pre_preview | REGENERABLE | 15899573 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_pre_reader | REGENERABLE | 15899406 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_sidecar_draft | ARCHIVE | 11908099 | retained pre-final diagnostic draft | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/report_lf | REGENERABLE | 317856 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json_pre_preview | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json_pre_reader | REGENERABLE | 53933 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/baseline_regression.json | REGENERABLE | 33402 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/dataset | REGENERABLE | 214602 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/diagnostics | REGENERABLE | 15859992 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/diagnostics.json | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/report | REGENERABLE | 317884 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/report_lf | REGENERABLE | 317856 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/verification.json | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/PHASE1_REPRODUCTION.md |
| data/scene_audit/phase1_physical_policy_approval_20261006/floor_support_details.json.gz | REGENERABLE | 469557 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_physical_policy_approval_20261006/geometry.json.gz | REGENERABLE | 2130611 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_physical_policy_approval_20261006/obstacle_collider_details.json.gz | REGENERABLE | 10448625 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz | REGENERABLE | 35313518 | large approved evidence kept locally, excluded from Git | data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json | uv run python -m amidst.materialize_physical_evidence --source-scene <source> |
| data/scene_audit/phase1_geometry_authority_20261006 | ARCHIVE | 15426622 | inherited historical provenance; retained unchanged | active physical context plus finalization input lock | git checkout f264db1579882e54cecba22db24ec8798822fd0c -- data/scene_audit/phase1_geometry_authority_20261006 |
| data/scene_audit/phase1_physical_authority_20261006 | ARCHIVE | 11940265 | inherited historical provenance; retained unchanged | active physical context plus finalization input lock | git checkout f264db1579882e54cecba22db24ec8798822fd0c -- data/scene_audit/phase1_physical_authority_20261006 |
| data/scene_audit/school_v3_approved_scale_20261006 | ARCHIVE | 11256456 | inherited historical provenance; retained unchanged | active physical context plus finalization input lock | git checkout f264db1579882e54cecba22db24ec8798822fd0c -- data/scene_audit/school_v3_approved_scale_20261006 |
| blender/school_v3.blend (external local source) | KEEP | 468300506 | immutable private/local research source | SHA256 cd46fa03...e84e; no regenerated replacement | supply exact source; never synthesize or rescale |
| human_review/frames/spatial_context/*.png | REGENERABLE | 29517434 | 28 diagnostic source context views retained locally | spatial_context_manifest.json; no replacement of original 57 images | archived producer at original path in fresh checkout; --frames 25 |
| human_review/history/spatial_context_initial_renderer.py | KEEP | 24686 | exact successful producer provenance | SHA256 8a5d52f4...305cd92 | git checkout finalization review commit |
| human_review/frames/motion_context/*.png | REGENERABLE | 19765351 | new 50-frame source-model body-motion review; older 85 images retained | motion_manifest.json and player.html | source Blender +render_motion_context.py --frames 50 --width 960 in fresh materialized checkout |
| human_review/frames/motion_context/motion_preview.gif | REGENERABLE | 8505740 | independent 10-second palette preview; original PNGs retained | gif_manifest.json; full-resolution player.html | uv run python human_review/make_motion_gif.py |
| human_review/frames/topology_context/topology_preview.png | REGENERABLE | 511640 | model/node/edge comparison from existing motion_025 image; original135PNG/GIF retained | topology_manifest.json and preview_manifest.json | uv run python human_review/render_topology_preview.py in fresh review checkout |
| human_review/frames/topology_context/ template/view/data/manifests | KEEP | small metadata | exact raw graph, display coordinates and hashes | source-bound topology_data.json | uv run python human_review/build_topology_view.py |
| human_review/frames/dashboard_context/integrated_review.jpg | REGENERABLE | 69496 | actual native browser proof of the integrated review workspace | dashboard_integration_manifest.json; original displays retained | capture index.html#visual-review-workspace with topology tab selected; 824x720 viewport |
| human_review/dashboard_template.html and dashboard_integration_manifest.json | KEEP | small source/metadata | inline media navigation with immutable decision payload | original review_template.json and media manifests | uv run python human_review/build_dashboard.py |

Detailed machine-readable inventory: [CSV](../data/finalization/checkpoint/artifact_inventory.csv).
The two later human-review supplements above have their own hash-bound manifests;
their source/templates/scripts/small metadata are KEEP and raw renders remain local ignored.
Only generated bytecode caches and an untracked fresh-validation mypy cache were removed
to finish the motion supplement after storage exhaustion. No source, evidence, preview,
decision or DELETE_CANDIDATE item was deleted.

Rebuild this inventory after reproduction:

```sh
uv run python scripts/inventory_phase1_finalization_artifacts.py \
  --local data/finalization/local_run \
  --fresh /absolute/path/to/fresh-checkout/data/finalization/fresh_run
```
