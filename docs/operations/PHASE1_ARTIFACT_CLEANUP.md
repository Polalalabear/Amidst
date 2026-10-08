# Phase 1 artifact cleanup / Artifact 整理

## 2026-10-08 current reviewed artifact inventory / 目前 reviewed 分類

Canonical `reviewed_run_v5` 的結果與重建方式見
[reviewed benchmark](../research/PHASE1_REVIEWED_BENCHMARK.md) 和
[reviewed reproduction](../research/PHASE1_REVIEWED_REPRODUCTION.md)；目前整體仍為
**PHASE1_FINALIZATION_BLOCKED**。本段只更新分類，沒有刪除或移動 artifact。

| Category | Current artifacts and treatment |
| --- | --- |
| KEEP | Curated reports、frozen configs、code/tests/docs、human/reference approval receipts，以及 `data/finalization/reviewed_checkpoint_v2/` 的小型 manifest、freeze、evaluation/reproduction 與 fresh comparison receipts。入口為 [evaluation receipt](../../data/finalization/reviewed_checkpoint_v2/local_evaluation_verification.json)、[reproduction receipt](../../data/finalization/reviewed_checkpoint_v2/local_reproduction_verification.json) 與 [final fresh comparison](../../data/finalization/reviewed_checkpoint_v2/fresh_delivery_comparison_final.json)。 |
| ARCHIVE | 既有 diagnostic/V3、partial V4、failed comparison/trial 與較早 blocked/pending 報告，連同各自 provenance 保留；不改稱目前正式結果。 |
| LOCAL ONLY | 原始 Blender source、大型 raw physical/source evidence、raw datasets、RRD、frame images 與其他 raw media 留在本機並依既有 ignore policy 排除 Git；不刪除、不提交。可重建內容的命令與 source/hash binding 見 reviewed reproduction。 |

沒有選取 DELETE_CANDIDATE。以下既有 inventory、數量與 approval-recording 狀態
保留為歷史 snapshot；目前 certificate／正式局部結果以連結的 V5 curated receipts
為準，原 protocol 不變。

Status: **inventory only** after completed diagnostic verification. Formal validation remains blocked. No artifact was deleted.

2026-10-07 approval-recording update: all four human profiles are APPROVED, with zero
pending human blockers. Decisions are recorded but not applied; physical certificate and
formal Cases remain NOT_RUN. KEEP the explicit approval receipt, read-only validation,
approval summary and integration receipt. Earlier blocked/pending reports and the complete
`hr02_camera_audit` durable package are ARCHIVE/preserved evidence, not deleted or relabelled
as formal results. The new `approvals_recorded/human_review/` durable package is saved and
verified: 272 manifest artifacts / 130829356 bytes and 273 complete copy files; manifest
SHA256 `923eb5f94cbe7bd1e0b45d5185b8189c07f62345c4c067d0fefc148e71e34187`.
Its per-file hashes and copy verification PASS preserve all 188 prior raw media hashes.

保留 source/config/tests/docs、experiment log、reports、manifests/hashes。Raw dataset、RRD、Blender 和大型物理證據只在本機保存。ARCHIVE 是分類，沒有移動或刪除 inherited provenance。

DELETE_CANDIDATE: none selected; no automatic deletion is authorized.

2026-10-07 review supplement: `human_review/frames/spatial_context/*.png` contains
28 locally retained source-model diagnostic views (3 stills +25 camera frames), classified
REGENERABLE. Its separate manifest, HTML/template/builder, exact successful producer archive
and current renderer are KEEP. Regeneration uses the archived producer staged at its original
path in a fresh materialized checkout, then `uv run python human_review/build_spatial_guide.py`;
see [review guide](../../human_review/README.md). Original 57 images and all source/decision files
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
| data/finalization/local_run/baseline_regression.json | REGENERABLE | 33402 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/dataset | REGENERABLE | 214602 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/dataset_provenance_draft | ARCHIVE | 214404 | retained pre-final diagnostic draft | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics | REGENERABLE | 15860041 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json_pre_preview | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics.json_pre_reader | REGENERABLE | 26739 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_pre_preview | REGENERABLE | 15899573 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_pre_reader | REGENERABLE | 15899406 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/diagnostics_sidecar_draft | ARCHIVE | 11908099 | retained pre-final diagnostic draft | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/report_lf | REGENERABLE | 317856 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json_pre_preview | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| data/finalization/local_run/verification.json_pre_reader | REGENERABLE | 53933 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/baseline_regression.json | REGENERABLE | 33402 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/dataset | REGENERABLE | 214602 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/diagnostics | REGENERABLE | 15859992 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/diagnostics.json | REGENERABLE | 26850 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/report | REGENERABLE | 317884 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/report_lf | REGENERABLE | 317856 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
| /private/tmp/amidst-phase1-finalization-fresh/data/finalization/fresh_run/verification.json | REGENERABLE | 54044 | local raw diagnostic package; summarized and hash-bound in Git | data/finalization/checkpoint | see docs/research/PHASE1_REPRODUCTION.md |
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
| human_review/frames/review_clarity/*.png | REGENERABLE | 13281548 | complete first-floor context, 25 camera-locator frames and pending HR02 body-height view; every old render retained | frames/review_clarity/manifest.json; spatial guide and dashboard | Blender with unchanged school_v3.blend + render_review_clarity.py --frames 25 in fresh output directory; see human_review/README.md |
| human_review/render_review_clarity.py and frames/review_clarity/manifest.json | KEEP | source and small metadata | fixed source/calibration, public visibility, explicit framing margins and pending body placement | immutable review_template.json and original motion/public inputs | same renderer; HTML builders with --clarity-manifest human_review/frames/review_clarity/manifest.json |
| human_review/clarity_integration_manifest.json | KEEP | small metadata | preserved-input hashes and native browser verification receipt | frames/review_clarity/manifest.json plus original review payload | verify immutable inputs and capture the same review UI; historical receipt remains preserved |
| human_review/frames/dashboard_context/clarity_review.jpg | REGENERABLE | 66884 | actual native browser screenshot of the HR02 body-height review | clarity_integration_manifest.json | capture index.html#visual-review-workspace with HR02 body-height display selected |
| human_review/frames/topology_context/template.html, view.html, topology_data.json and topology_manifest.json | KEEP | source and display metadata | synchronized P(t) marker with unchanged two-node/three-edge graph and existing public coordinates | topology_motion_integration_manifest.json; original static preview remains available | uv run python human_review/build_topology_view.py followed by build_dashboard.py with clarity manifest |
| human_review/topology_motion_integration_manifest.json | KEEP | small metadata | unchanged source, old-media hashes and native frame synchronization verification | prior clarity package plus current topology manifest | verify fixed inputs and repeat display-only checks; preserve historical receipt |
| human_review/frames/dashboard_context/topology_motion_review.jpg | REGENERABLE | 60323 | native browser frame25 showing current person position in both model and graph | topology_motion_integration_manifest.json | capture index.html#visual-review-workspace with model/topology tab at frame25 |
| human_review/topology_playback_integration_manifest.json | KEEP | small metadata | fixed playback layout and native zero-shift measurements; pending review unchanged | existing topology_manifest.json | run playback regressions and native layout sampling; preserve historical receipt |
| human_review/frames/dashboard_context/topology_playback_stable.jpg | REGENERABLE | 58511 | actual native browser screenshot of stable model/topology review | topology_playback_integration_manifest.json | capture index.html with model/topology selected at frame25 |
| human_review/inspect_hr02_camera_binding.py, render_hr02_camera_audit.py, build_hr02_camera_review.py, HR02_CAMERA_AUDIT.md | KEEP | 85759 | reproducible GT-free source-instance evidence and review workflow; remeasured after approval note | frames/hr02_camera_audit manifests | commands in human_review/HR02_CAMERA_AUDIT.md |
| human_review/frames/hr02_camera_audit/*.json, template.html, view.html | KEEP | 683797 | immutable public query, exact fresh-process match, render/UI receipts | original input hashes and review payload | frozen Blender query/render to fresh paths, then build_hr02_camera_review.py |
| human_review/frames/hr02_camera_audit/*.png | REGENERABLE | 10855553 | 8 new 1920x1080 diagnostic views with live-instance source geometry; static bases contain no baked person | renderer_manifest.json and render_verification.json | Blender with unchanged source + render_hr02_camera_audit.py --output /fresh/path |
| human_review/history/hr02_initial_camera_render/ | ARCHIVE | 10910996 PNG bytes plus receipts/view | retain all 8 initial images; initial static actor/rays and unsafe evaluated-reference producer are not canonical playback | frames/hr02_camera_audit; exact initial producer in history/hr02_initial_camera_renderer.py | initial producer archived for provenance; use corrected producer for canonical reproduction |
| human_review/history/hr02_initial_ray_audit/ | ARCHIVE | small JSON; per-file sizes in manifest | noncanonical initial trial explicitly records producer drift; no deletion | immutable canonical audit and final_repeat_verification.json | current frozen inspect_hr02_camera_binding.py to fresh output |
| human_review/frames/dashboard_context/hr02_camera_review.jpg | REGENERABLE | 114494 | native browser proof at frame45 with existing motion and new source rays | hr02_camera_integration_manifest.json and native_ui_verification.json | capture shared HR02 camera-audit tab at frame45 |
| human_review/approval_record.json, approval_validation.json, APPROVALS.md | KEEP | final per-file sizes in package manifest | explicit human choices and immutable/source verification; recorded, not applied | decisions.json plus unchanged review_template.json | preserve approval_record; run apply_decisions.py in default read-only validation mode; regenerate documentation without --apply |
| human_review/approval_integration_manifest.json | KEEP | 3354 | approved interface state, preserved prior evidence and native verification | approval_record.json, approval_validation.json and media manifests | verify immutable inputs and capture approved dashboard; preserve receipt |
| human_review/finalize_package.py, write_review_docs.py, README.md, gate.json, manifest.json | KEEP | final per-file sizes in package manifest | validated current decision state; pending behavior retained; certificate/formal stages not falsely promoted | original selected profiles and immutable question payload | uv run python human_review/write_review_docs.py; uv run python human_review/finalize_package.py |
| human_review/frames/dashboard_context/approvals_recorded.jpg | REGENERABLE | 84378 | native browser proof of four recorded approvals, zero Case 1–3 human blockers and one active iframe | approval_integration_manifest.json | capture approved dashboard; preserve resulting exact file size/hash |
| data/pilot/phase1_finalization_human_review_20261007/hr02_camera_audit/human_review/ | ARCHIVE | 130717159 manifest artifact bytes; original manifest retained | complete preapproval review package preserved independently | approvals_recorded/human_review/ verified durable package | preserve old copy; rebuild corrected diagnostics only in a fresh output path |
| /private/tmp/amidst-review-clarity-qa-v1 | ARCHIVE | local diagnostic trial | unadopted flat-lighting map and its exact producer retained; no source/evidence deletion | final clarity renderer and manifest | initial producer only; intentionally stopped after first map, not canonical evidence |

Detailed machine-readable inventory: [CSV](../../data/finalization/checkpoint/artifact_inventory.csv).
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
