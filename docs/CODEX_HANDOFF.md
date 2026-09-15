# Codex Handoff Checkpoint

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Handoff status: `READY_FOR_ACCOUNT_TRANSFER`

Project milestone status: `REVIEW_REQUIRED`

Checkpoint publication status: `APPROVED_FOR_PUBLICATION` for the 50 current
project-relevant paths classified in
`data/reports/codex_handoff_file_classification.md`. Approval is scoped to this
checkpoint and explicitly excludes `local/`, caches, `.DS_Store`, credentials,
and every `.blend` artifact.

Checkpoint date: 2026-09-15

This file records repository-safe, reproducible state only. Machine-specific
details belong in the ignored `local/CODEX_PRIVATE_HANDOFF.md` file.

### Repository state

- Branch: `codex/blender-inspection-v1`
- HEAD: `6a2fb220738c823fdbd361d124c8cf1ca0e08442`
- Working tree: dirty by design; the Blender governance, inspection, and
  first-slice preparation work is not committed.
- Pre-publication staging area: empty. No files were staged, committed, pushed,
  or published by the handoff-preparation task.
- Tracked modifications before this handoff: the dataset, spatial, technical
  decision, data-format, and open-question documents listed in the
  classification report.
- Untracked project files before this handoff: 42 files under `blender/` and
  `data/`. The complete per-file classification is in
  `data/reports/codex_handoff_file_classification.md`.
- Handoff additions: `.gitignore`, this file, the classification report, and an
  ignored local-only note.
- Post-handoff-preparation, pre-publication snapshot: 6 tracked files modified,
  44 non-ignored untracked project files, 0 staged files; the ignored local
  note and four `.blend` artifacts were intentionally absent from `git status`.

At handoff preparation, the branch pointed at the same commit as
`origin/chore/add-gitignore` and had no configured upstream. Human publication
approval was recorded on 2026-09-15. The commit containing this file is the Git
checkpoint; resolve its SHA with `git rev-parse HEAD` rather than embedding a
self-referential commit digest here.

### Current milestone and status

The latest authoritative readiness result is `REVIEW_REQUIRED` in
`data/reports/school_v1_first_slice_readiness.json`, validated at
2026-09-14T11:10:44.928109+00:00 against the stable-ID output scene.

Completed milestones supported by repository evidence:

- immutable `school_v1` source-scene inspection and inventory;
- stable-ID governance under ADR-008 and policy
  `amidst.school.object-id/1.0.1`;
- deterministic ID assignment for 2,777 eligible objects;
- persistent-ID validation with one imported helper camera excluded;
- a category-agnostic semantic baseline with 2,777 `Unknown` objects and no
  inferred named categories;
- confirmed first-slice task contract
  `amidst.school.first-dataset-slice/0.1.0`;
- authoritative metadata schema
  `amidst.first-dataset-slice.metadata/0.1.0`;
- confirmed spatial and visibility contracts;
- deterministic render config `amidst.school.first-slice-render/0.1.0`; and
- confirmed texture-agnostic resource policy in ADR-009 and the task/render
  contracts.

Not completed:

- the texture-agnostic derived scene has not been created;
- its resource-policy sidecar and fresh-process validation report do not exist;
- the readiness report still has seven blockers; and
- no images or dataset samples have been generated.

### Authoritative artifacts

The listed scene-specific JSON, CSV, and report artifacts retain their normal
`REVIEW_REQUIRED` publication classification even when technically
authoritative. Human review explicitly approved the currently classified
versions for this checkpoint on 2026-09-15; later or changed versions require a
new review.

| Role | Path | State |
| --- | --- | --- |
| Scene manifest | `blender/scene_manifest.json` | Latest manifest; source v1 active |
| Stable-ID registry | `data/annotations/instance_registry/school.json` | Authoritative registry v1.1.0; policy 1.0.1; 2,777 records |
| Objective disambiguation | `data/annotations/instance_registry/school_v1_disambiguation.json` | `CONFIRMED`; 5 records |
| Reviewed bootstrap | `data/annotations/instance_registry/school_v1_identity_bootstrap.json` | `CONFIRMED`; 131 records |
| Semantic baseline | `data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json` | `CONFIRMED`; category-agnostic; 0 reviewed named categories |
| Task contract | `data/metadata/first_dataset_slice_tasks_v0_1_0.json` | `CONFIRMED`; seven ID/geometry tasks |
| Metadata schema | `data/metadata/first_dataset_slice_metadata_schema_v0_1_0.json` | Schema ID `amidst.first-dataset-slice.metadata/0.1.0` |
| Render config | `data/metadata/first_dataset_slice_render_config_v0_1_0.json` | `CONFIRMED`; pending derived-scene validation |
| Readiness report | `data/reports/school_v1_first_slice_readiness.json` and `.md` | `REVIEW_REQUIRED`; 7 blockers |
| Persistent-ID report | `data/reports/school_v1_id_persistence.json` and `.md` | `READY_FOR_SEMANTIC_ANNOTATION`; 2,777 IDs verified |
| Stable-ID scene validation | `data/reports/school_v1_ids_validation.json` | 2,778 objects; 2,777 IDs; one approved exclusion |
| ID determinism | `data/reports/school_v1_id_determinism.json` | Latest deterministic-assignment evidence |
| Scene comparison | `data/reports/school_v1_id_scene_comparison.json` | `PASS`; no unauthorized identity-scene changes reported |
| Missing-resource audit | `data/reports/school_v1_missing_resource_audit.json` and `.md` | `REVIEW_REQUIRED`; 5 exact originals not found |
| Source inventory | `data/scene_inventory/school_v1_objects.csv` | Initial immutable-source inventory |
| Stable-ID inventory | `data/scene_inventory/school_v1_ids_objects.csv` | Post-persistence inventory |

Important Blender artifacts:

| Scene role | Path | SHA-256 | Disposition |
| --- | --- | --- | --- |
| Immutable source | `blender/source/school_v1.blend` | `cbfef8c84295253323890be5d9ffae186c46481f9dde8a6509ce897c49a34fa1` | Never modify |
| Working scene | `blender/working/school_v1_working.blend` | `3f7aec572938f42444741725116bcfbf941b666eb55c068902e3e31c42a3ba5a` | Local/private; IDs persisted |
| Validated stable-ID output | `blender/output/school_v1_ids_policy_1_0_1_r2.blend` | `532243c70b3cce6d9710a804f29a3ffe76cee779a80a888dc875600fc095beb4` | Current validated input for the next derived-scene task |
| Invalid preserved output | `blender/output/INVALID_school_v1_ids_policy_1_0_1_path_remapped.blend` | `511fc8071746c5ef55e8d5e8cc456195ad928038a4b551c3eb3cedd4e7242838` | Invalid/deprecated; preserve for review, never use as input |
| Planned derived output | `blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend` | Not present | Do not claim or use until created and freshly validated |

### Approved decisions

Only `CONFIRMED` repository decisions are summarized here:

- ADR-008 makes `data/annotations/instance_registry/school.json` the identity
  authority. Blender custom properties are mirrors. IDs use UUIDv5 in the
  `amidst:school:object:<uuid-v5>` format, do not derive from names, are never
  silently reassigned or reused, and retain tombstones after deletion.
- Policy 1.0.1 preserves the 1.0.0 base fingerprint, adds the confirmed
  five-record objective layer and 131-record reviewed bootstrap layer, and
  excludes `skp_camera_Last_Saved_SketchUp_View` as a non-authoritative imported
  saved-view helper.
- ADR-009 confirms the seven first-slice task IDs: `visible_objects`,
  `nearest_object`, `distance_to_object`, `left_of`, `right_of`,
  `in_front_of`, and `behind`. They use stable IDs and Blender-derived geometry;
  named semantic categories are not required.
- Unreviewed semantics remain `category = Unknown` and
  `annotation_status = needs_review`.
- The object anchor is the evaluated world-space bounding-box centre. Distance
  is camera-optical-centre-to-anchor Euclidean metres.
- `camera_cv` is right-handed: +X image-right, +Y image-down, +Z forward.
- Visibility casts one ray through each final-resolution pixel centre and
  requires at least 16 nearest-hit pixels. Occlusion compares visible pixels
  with target-only projected pixels.
- Relation deadband is 0.0001 m. Distance-tie and ray-hit epsilon are 0.000001
  m. Nearest ties choose the lexicographically smallest stable ID and record the
  sorted tie set.
- Render config version is `amidst.school.first-slice-render/0.1.0`; output
  dataset version is `school_v1_first_slice_v0_1_0`. Existing runs/samples are
  never overwritten, and rejected evidence is preserved separately.
- Texture policy `amidst.school.texture-agnostic-render/0.1.0` uses one neutral,
  opaque, non-semantic view-layer material override. It leaves original material
  graphs and five legacy paths untouched, asserts no visual-fidelity authority,
  and requires zero unresolved resources used by the approved runtime policy.

### Current blockers and unresolved items

1. **Derived scene and provenance are absent.** This blocks verification that
   the confirmed texture-agnostic policy has been applied without unauthorized
   mutation. See `docs/07_Technical_Decisions.md` ADR-009 and
   `data/reports/school_v1_first_slice_readiness.json`. A fresh explicit
   authorization to write a derived `.blend` is required in the receiving
   session.
2. **Resource-policy sidecar and fresh validation are absent.** Expected paths
   are `data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json`
   and `data/reports/school_v1_texture_agnostic_scene_validation.json`. Their
   absence accounts for the current provenance/resource blockers.
3. **Latest readiness has seven blockers:**
   `derived_scene_render_policy_provenance_recorded`,
   `five_legacy_resources_remain_recorded_unavailable`,
   `object_transforms_and_inventory_unchanged`,
   `raw_external_resource_paths_approved_intentional`,
   `render_resource_policy_authoritative`,
   `source_output_provenance_recorded`, and
   `zero_unresolved_resources_required_by_approved_render_policy`.
4. **Five historical original images are unavailable.** The latest audit found
   no exact original in the approved repository search root. They affect
   render-enabled objects under the imported material graphs. ADR-009 permits
   them to remain unavailable only after the derived texture-agnostic runtime
   path and preserved provenance pass validation. No silent replacement is
   allowed.
5. **Future publication review authority remains OPEN.** OQ-012 has not assigned
   a general reviewer for later artifacts. This does not block the present
   checkpoint: the human authorization recorded on 2026-09-15 satisfies review
   for the 50 current project paths only. Any later or changed
   `REVIEW_REQUIRED` artifact needs a new human decision.
6. **The Git checkpoint must be identified externally.** A commit cannot safely
   embed its own SHA. The receiving agent must verify that the local and remote
   `codex/blender-inspection-v1` refs both point to the commit containing this
   file.

The project must remain `REVIEW_REQUIRED` and dataset generation prohibited
until the full readiness report has zero blockers.

### Exact next authorized task

Do not render or generate samples. After independently rerunning the validation
commands below and obtaining fresh explicit authorization for derived-scene
mutation, perform only this bounded task:

> Use `blender/output/school_v1_ids_policy_1_0_1_r2.blend` as the validated
> input. Run `blender/scripts/create_texture_agnostic_scene.py` to create the
> versioned texture-agnostic derived scene and its resource-policy/provenance
> records. Then open the derived output in a fresh Blender process, run
> `blender/scripts/validate_texture_agnostic_scene.py`, and rerun
> `blender/scripts/validate_first_slice_readiness.py`. Confirm 2,777 stable IDs,
> 29 valid eligible cameras, zero runtime-required missing resources, unchanged
> object transforms/material structure/stable IDs, preserved five legacy image
> paths, exact before/after checksums, and zero unauthorized scene changes. Do
> not render images or generate dataset samples. Stop with `REVIEW_REQUIRED` on
> any mismatch.

The prepared commands, using a locally resolved `blender` executable, are:

```sh
blender --background blender/output/school_v1_ids_policy_1_0_1_r2.blend --python blender/scripts/create_texture_agnostic_scene.py
blender --background blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend --python blender/scripts/validate_texture_agnostic_scene.py
blender --background blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend --python blender/scripts/validate_first_slice_readiness.py
```

### Safety boundaries

- Never modify, rename, delete, or overwrite `blender/source/` or any source
  `.blend`.
- All Blender mutations require an authorized derived/working copy. Never
  overwrite validated historical outputs.
- Do not use the invalid path-remapped output as an input or repair it silently.
- Never infer semantic category from geometry or names. Preserve `Unknown` /
  `needs_review` without trusted approval.
- Never replace a missing resource silently. Preserve exact provenance and
  checksum for any approved original or replacement.
- The stable-ID sidecar registry is authoritative; Blender custom properties
  are mirrors. Do not regenerate bootstrap bindings from names or reuse IDs.
- Do not modify geometry, transforms, material slots/graphs, UVs, modifiers,
  rigs, armatures, or constraints unless separately and explicitly authorized.
- Any observation/scene/ground-truth inconsistency invalidates the sample;
  preserve evidence and report the reason.
- Keep `.blend` files and machine/private notes outside Git. Apply
  `docs/08_Repository_and_Data_Publication_Policy.md` before adding any
  scene-specific record.

### Validation commands

Run these first from the repository root:

```sh
python3 -B scripts/check.py
git diff --check
find blender data -type f -name '*.json' -print0 | xargs -0 -n1 python3 -m json.tool >/dev/null
shasum -a 256 blender/source/school_v1.blend blender/working/school_v1_working.blend blender/output/school_v1_ids_policy_1_0_1_r2.blend blender/output/INVALID_school_v1_ids_policy_1_0_1_path_remapped.blend
git status --short
git diff --cached --name-status
```

For a non-mutating current readiness refresh, use the validated stable-ID
output. This is expected to remain `REVIEW_REQUIRED` until the derived-scene
artifacts exist:

```sh
blender --background blender/output/school_v1_ids_policy_1_0_1_r2.blend --python blender/scripts/validate_first_slice_readiness.py
```

<a id="繁體中文"></a>

## 繁體中文

Handoff 狀態：`READY_FOR_ACCOUNT_TRANSFER`

專案里程碑狀態：`REVIEW_REQUIRED`

Checkpoint publication 狀態：目前分類報告中的 50 個 project-relevant paths
已獲 `APPROVED_FOR_PUBLICATION`。核准只適用本 checkpoint，且明確排除
`local/`、cache、`.DS_Store`、credential 與全部 `.blend`。

Checkpoint 日期：2026-09-15

本檔只記錄可安全進入 repository、可重現的資訊。機器限定內容放在被忽略的
`local/CODEX_PRIVATE_HANDOFF.md`。

### Repository 狀態

- Branch：`codex/blender-inspection-v1`
- HEAD：`6a2fb220738c823fdbd361d124c8cf1ca0e08442`
- Working tree：刻意保持 dirty；Blender governance、inspection 與 first-slice
  preparation 尚未 commit。
- Staging area：空白。本 handoff 未 stage、commit、push 或發布任何檔案。
- Handoff 前有 5 份 tracked docs 修改，以及 `blender/`、`data/` 下 42 個
  untracked project files；逐檔分類見
  `data/reports/codex_handoff_file_classification.md`。
- 本次只新增／修改 `.gitignore`、本檔、分類報告與被 ignore 的 local note。
- Handoff preparation 完成、publication 開始前的 snapshot 共有 6 個 tracked
  modified files、44 個未被 ignore 的 untracked project files、0 個 staged
  files；local note 與四個 `.blend` 因規則刻意不出現在 `git status`。

Handoff 準備時 branch 尚無自己的 upstream；2026-09-15 已取得本 checkpoint
的 human publication approval。包含本檔的 commit 即是 Git checkpoint；為避免
self-referential digest，本檔不內嵌該 commit SHA，應以 `git rev-parse HEAD`
核對。

### 目前里程碑與權威產物

最新 readiness 是 `data/reports/school_v1_first_slice_readiness.json` 的
`REVIEW_REQUIRED`。已完成 immutable source inspection、2,777 個 stable ID 的
治理／確定性指派／持久化驗證、category-agnostic semantic baseline、七項
first-slice task、metadata schema、spatial／visibility contracts、deterministic
render config 與已確認的 texture-agnostic policy。

權威路徑、逐項狀態與四個 `.blend` SHA-256 以上方 English tables 為準；其中
source、working、validated output 與 invalid preserved output 已明確區分。
Planned derived output、resource-policy sidecar 與 fresh validation report 都尚未
存在，也沒有產生任何 image 或 dataset sample。

### 已核准決策

- ADR-008 確認 sidecar registry 為 stable-ID 權威；Blender property 只是鏡像。
  名稱不進入 ID，ID 不可靜默重派或重用，刪除後保留 tombstone。
- Policy 1.0.1 保留 1.0.0 base fingerprint，加入 5 筆 objective
  disambiguation、131 筆 reviewed bootstrap，並排除 imported saved-view helper
  camera。
- ADR-009 確認七項 stable-ID／geometry task；未審語意保持 `Unknown`／
  `needs_review`。
- Anchor、distance、`camera_cv`、visibility／occlusion、tolerance、tie-break、
  render/output version 與 texture-agnostic override 規則均依上方 English
  summary 及權威 contract 執行，不得自行改寫。

### 阻擋項與下一步

目前缺少 derived scene、resource-policy sidecar 與 fresh-process validation；
readiness 仍有七項 blocker。五個 legacy original image 仍未找到，只能在已核准
texture-agnostic runtime path 完成且驗證後，視為非 runtime dependency。
OQ-012 對未來產物的一般 publication reviewer authority 仍為 `OPEN`，但本次
已由 human authorization 明確核准目前 50 個 project paths；任何後續新增或
修改的 `REVIEW_REQUIRED` artifact 都必須重新審查。

接手 agent 應先執行上方 validation commands，取得新的 derived-scene mutation
明確授權後，僅建立 texture-agnostic derived scene、fresh validate 並重跑
readiness；不可 render 或生成 dataset。任何 mismatch 都維持
`REVIEW_REQUIRED`。

### 安全界線

不得修改 `blender/source/`、覆寫歷史 output、猜測 semantic category、靜默替換
resource、從名稱重建 ID、或未經獨立授權變更 geometry／transform／material
structure／UV／modifier／rig／constraint。Observation、Blender state 與 Ground
Truth 不一致時必須使 sample invalid，保留證據並記錄原因。
