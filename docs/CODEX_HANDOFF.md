# Codex Handoff Checkpoint

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Handoff status: `ACCOUNT_TRANSFER_COMPLETED` (human-confirmed 2026-09-15)

Project milestone status: `REVIEW_REQUIRED`

Checkpoint publication status: `APPROVED_FOR_PUBLICATION` for the 50 current
project-relevant paths classified in
`data/reports/codex_handoff_file_classification.md`. Approval is scoped to this
checkpoint and explicitly excludes `local/`, caches, `.DS_Store`, credentials,
and every `.blend` artifact.

Checkpoint date: 2026-09-16

This file records repository-safe, reproducible state only. Machine-specific
details belong in the ignored `local/CODEX_PRIVATE_HANDOFF.md` file.

### Repository state

- Branch: `codex/blender-inspection-v1`
- Published handoff checkpoint before this task: `5bd109a4a5a4eb58d8492d093f406d986581b444`.
- Portable setup/test base awaiting the authorized push at task start:
  `a467336644486b94419cf9f904a6840bc67e0145`.
- Upstream: `origin/codex/blender-inspection-v1`.
- Working tree: dirty by design with post-handoff derived-scene validation
  records; no current change is staged.
- Local/private notes and every `.blend` remain outside Git.
- The complete per-file publication classification is in
  `data/reports/codex_handoff_file_classification.md`.

### Cross-platform migration checkpoint

Status: `REVIEW_REQUIRED`; no dataset generation is authorized.

- The macOS v0.1.1 r2 sweep is complete with 29 of 29 unique immutable
  `statistics.json` records under
  `data/reports/render_diagnostics/school_v1_render_policy_v0_1_1_r2/`.
- The pre-resume image without a record remains preserved. Its successful retry
  is stored in a separate non-overwriting directory.
- The raw aggregate is
  `data/reports/school_v1_render_policy_v0_1_1_camera_statistics_raw.json`.
  All 29 renders succeeded and every record preserves the scene checksum and
  runtime invariants.
- Three fresh-process repeats are complete. Strict decoded-pixel identity passes
  for 1 of 3 cameras and fails for 2: one camera differs at 1 pixel and the
  other at 2 pixels, with maximum channel difference `1/255`. The confirmed
  exact decoded-pixel requirement is therefore not satisfied.
- The formal result is `DIAGNOSTIC_COMPLETE_DETERMINISM_FAILED` in
  `data/reports/school_v1_render_policy_v0_1_1_camera_statistics.json`, with a
  human report in `data/reports/school_v1_render_policy_v0_1_1_diagnostic.md`.
- A composition threshold is only `PROPOSED`: occupancy below `0.95` and at
  least 3 visible stable-ID objects. It flags the same 7 cameras under both
  clauses and has no decision effect until Peter confirms it.
- The validated private r2 derived scene is
  `blender/output/school_v1_first_slice_texture_agnostic_v0_1_1_r2.blend`,
  SHA-256
  `5aa0e4a54f20b9dba0d79067562711677b897ea6e246ed03e9aa8c0782cd2fed`.
- Preserve the macOS directory as one environment-scoped completed diagnostic. A
  destination with a different OS, architecture, Blender build, backend,
  device, or driver must use a new output directory and rerun all 29 cameras;
  do not append Windows or Linux results to the macOS records.
- New v0.1.1 records use repository-relative POSIX paths with
  `path_base = repository_root`. Existing reports containing historical
  machine paths remain unchanged.
- Local inventory `local/migration_inventory_v0_1_1.json` expands to 293
  non-cache file records in `local/migration_manifest_v0_1_1.json`. The
  manifest passed verification against the current repository/private overlay
  with zero failures; both files remain ignored and `REVIEW_REQUIRED`.

Create a local, non-overwriting transfer inventory with
`scripts/migration_manifest.py create`, using the current repository worktree
as the first `--source-root` and the private Blender layout as an additional
root. Classify code and documentation as `PUBLIC_ALLOWED`, populated reports
and metadata as `REVIEW_REQUIRED`, and every `.blend` as `PRIVATE_ONLY`.
After cloning on the destination, run `verify` against its repository root.
Never copy the Codex worktree `.git` pointer.

Use the platform-specific setup, test, Blender runtime, and migration commands
in [10_Cross_Platform_Setup_and_Testing.md](10_Cross_Platform_Setup_and_Testing.md).
The destination verification commands are intentionally separate because shell
continuation syntax is not portable.

macOS:

```sh
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

Windows (PowerShell):

```powershell
py -3 -B scripts/migration_manifest.py verify --manifest local/migration_manifest_v0_1_1.json --target-root .
```

Linux (Bash):

```bash
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

### Current milestone and status

The latest authoritative readiness result is `READY_FOR_FIRST_DATASET_SLICE`
in `data/reports/school_v1_first_slice_readiness.json`, validated in a fresh
Blender process against the texture-agnostic derived scene on 2026-09-15.

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
  contracts;
- validated diagnostic-only v0.1.1 r2 render policy and derived scene, with no
  dataset or Ground Truth change;
- a versioned derived scene with recorded source/input/output provenance;
- fresh-process invariant validation with zero unauthorized scene changes; and
- full readiness validation with zero blockers, 2,777 stable IDs, and 29 valid
  eligible cameras; and
- first deterministic generator implementation plus a preserved bounded pilot
  run with one historically schema-valid accepted sample that a later render
  diagnostic invalidated for observation use.

Not completed:

- the authorized pilot did not reach 10 accepted samples within 50 attempts;
- the one historically accepted image is pixel-identical to a fresh render but
  is `OBSERVATION_RENDER_INVALID`, leaving zero valid accepted samples;
- the v0.1.1 r2 diagnostic evidence collection is complete, but strict decoded-
  pixel determinism passed only 1 of 3 repeats and the threshold is still
  `PROPOSED`;
- two target-only occlusion count mismatches and one AOV/ray audit mismatch
  require review; and
- the corrected cleanup path has not been executed in a new run because the
  authorized attempt limit was exhausted.

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
| Render config | `data/metadata/first_dataset_slice_render_config_v0_1_0.json` | `CONFIRMED`; readiness gate passed |
| Render-resource policy | `data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json` | `CONFIRMED`; texture-agnostic runtime policy |
| Derived-scene creation | `data/reports/school_v1_texture_agnostic_scene_creation.json` and `.md` | Created from the validated stable-ID output |
| Derived-scene validation | `data/reports/school_v1_texture_agnostic_scene_validation.json` and `.md` | `PASS`; no unauthorized scene changes |
| Readiness report | `data/reports/school_v1_first_slice_readiness.json` and `.md` | `READY_FOR_FIRST_DATASET_SLICE`; 0 blockers |
| Pilot generation | `data/reports/school_v1_first_slice_pilot_run_pilot_0001.json` and `.md` | `REVIEW_REQUIRED`; 1 accepted, 49 rejected, 50 attempts |
| Pilot failure analysis | `data/reports/school_v1_first_slice_pilot_run_pilot_0001_failure_analysis.json` and `.md` | Cleanup defect corrected but not rerun; GT mismatches unresolved |
| Observation render diagnostic | `data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.json` and `.md` | `OBSERVATION_RENDER_INVALID`; v0.1.1 replacement is diagnostic-only and incomplete; OQ-016 still blocks a pilot |
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
| Validated stable-ID output | `blender/output/school_v1_ids_policy_1_0_1_r2.blend` | `532243c70b3cce6d9710a804f29a3ffe76cee779a80a888dc875600fc095beb4` | Validated input used for the derived scene |
| Invalid preserved output | `blender/output/INVALID_school_v1_ids_policy_1_0_1_path_remapped.blend` | `511fc8071746c5ef55e8d5e8cc456195ad928038a4b551c3eb3cedd4e7242838` | Invalid/deprecated; preserve for review, never use as input |
| Validated texture-agnostic derived output | `blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend` | `e349646c27fb343341a372b1e6d97b1a66f304f52c62721400e1833cdcd4d933` | Local/private; first-slice readiness input |

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

The older scene-level readiness report remains
`READY_FOR_FIRST_DATASET_SLICE`, but it predates the rendered-image diagnostic
and must not be used to authorize generation. Run `run_pilot_0001` reached its
50-attempt limit with 1 historically accepted and 49 rejected samples; the
accepted image is now `OBSERVATION_RENDER_INVALID`, so valid accepted count is
zero. The v0.1.1 replacement render policy is approved for diagnostic use and
its derived scene passed fresh-process validation. The sweep and repeat
collection are complete, but exact decoded-pixel determinism failed and the
composition threshold remains proposed; cross-environment acceptance remains
open under OQ-016. Two
target-only occlusion-count mismatches and one AOV/ray audit mismatch remain unresolved. A
generator cleanup defect caused the later 46 pre-render rejections; the code is
corrected but has not been rerun because the attempt authorization is
exhausted. See the pilot failure analysis and
`data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.json`.

Five historical originals remain unavailable, but their unchanged paths are
recorded legacy evidence and are not dependencies of the confirmed
texture-agnostic runtime policy. They must not be silently replaced.

#### Expected GUI/render difference

The current `.blend` saves the Layout viewport in Material Preview with the
viewport-only `forest.exr` studio light and with scene lights and scene World
disabled. A GUI automation that selects a camera and takes an operating-system
screenshot would capture that viewport state, including possible overlays,
selection/UI state, window scaling, and display behaviour. It would not prove
equivalence to the deterministic EEVEE F12 render or to the scene state used for
Ground Truth. Such screenshots are diagnostic-only; authoritative `image.png`
must be produced by the recorded Blender render path. The confirmed diagnosis
and exact measurements are in
`data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.json`.

Publication review authority for later changed scene-specific artifacts remains
`OPEN` under OQ-012. The post-checkpoint artifacts listed in the classification
report require a new human publication decision before commit or push.

### Exact next authorized task

Do not run a dataset pilot. Peter must decide whether to keep or change the
confirmed decoded-pixel identity requirement and must accept, revise, or reject
the proposed composition threshold. For Windows or Linux handoff, clone the
branch, restore the private r2 scene and `REVIEW_REQUIRED` overlay, verify the
migration manifest and runtime lock, and record the exact destination OS,
architecture, Blender build, backend, device, and driver. Any destination
diagnostic must use a new environment-scoped output directory. The substantive
GT mismatches remain outside this migration task; a later pilot still requires
separate authorization and a new immutable run ID.

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
shasum -a 256 blender/source/school_v1.blend blender/working/school_v1_working.blend blender/output/school_v1_ids_policy_1_0_1_r2.blend blender/output/INVALID_school_v1_ids_policy_1_0_1_path_remapped.blend blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend
git status --short
git diff --cached --name-status
```

For a non-mutating current readiness refresh, use the validated texture-agnostic
derived output. It is expected to remain `READY_FOR_FIRST_DATASET_SLICE`:

```sh
blender --background blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend --python blender/scripts/validate_texture_agnostic_scene.py
blender --background blender/output/school_v1_first_slice_texture_agnostic_v0_1_0.blend --python blender/scripts/validate_first_slice_readiness.py
```

<a id="繁體中文"></a>

## 繁體中文

Handoff 狀態：`ACCOUNT_TRANSFER_COMPLETED`（human 已於 2026-09-15 確認）

專案里程碑狀態：`REVIEW_REQUIRED`

Checkpoint publication 狀態：目前分類報告中的 50 個 project-relevant paths
已獲 `APPROVED_FOR_PUBLICATION`。核准只適用本 checkpoint，且明確排除
`local/`、cache、`.DS_Store`、credential 與全部 `.blend`。

Checkpoint 日期：2026-09-15

本檔只記錄可安全進入 repository、可重現的資訊。機器限定內容放在被忽略的
`local/CODEX_PRIVATE_HANDOFF.md`。

### Repository 狀態

- Branch：`codex/blender-inspection-v1`
- 已發布 checkpoint：`5bd109a4a5a4eb58d8492d093f406d986581b444`。
- Upstream：`origin/codex/blender-inspection-v1`。
- Working tree 刻意保留接手後的 derived-scene validation 變更，目前無 staged
  files。
- Local/private note 與所有 `.blend` 仍不進 Git；完整分類見
  `data/reports/codex_handoff_file_classification.md`。

### 跨平台遷移 checkpoint

狀態：`REVIEW_REQUIRED`；未授權 dataset generation。

- macOS v0.1.1 r2 sweep 已完成，29 台 camera 都有唯一且不可覆寫的
  `statistics.json`，位於
  `data/reports/render_diagnostics/school_v1_render_policy_v0_1_1_r2/`。
- 續跑前只有 image、沒有 record 的失敗證據維持不變；成功 retry 存在另一個
  不覆寫的 directory。
- Raw aggregate 為
  `data/reports/school_v1_render_policy_v0_1_1_camera_statistics_raw.json`；29 次
  render 全部成功，scene checksum 與 runtime invariants 皆未變。
- 三次 fresh-process repeat 已完成；嚴格 decoded-pixel identity 只有 1/3 通過。
  兩筆失敗分別只有 1 與 2 個 pixel 不同，最大 channel 差異為 `1/255`，但仍不
  符合已確認的 exact decoded-pixel requirement。
- 正式結果為
  `data/reports/school_v1_render_policy_v0_1_1_camera_statistics.json` 的
  `DIAGNOSTIC_COMPLETE_DETERMINISM_FAILED`；人類可讀報告為
  `data/reports/school_v1_render_policy_v0_1_1_diagnostic.md`。
- Composition threshold 只維持 `PROPOSED`：largest occupancy 小於 `0.95` 且
  至少 3 個可見 stable-ID objects。兩個條件在本次都標出相同 7 台 camera；
  Peter 確認前沒有決策效力。
- 已驗證的私人 r2 derived scene 為
  `blender/output/school_v1_first_slice_texture_agnostic_v0_1_1_r2.blend`，
  SHA-256 為
  `5aa0e4a54f20b9dba0d79067562711677b897ea6e246ed03e9aa8c0782cd2fed`。
- macOS directory 應保存為單一 environment-scoped 完整診斷。目標機器的
  OS、architecture、Blender build、backend、device 或 driver 不同時，必須在
  新 output directory 重跑全部 29 台 camera；不得把 Windows 或 Linux 結果接到
  macOS record 後面。
- 新的 v0.1.1 record 使用 repository-relative POSIX path 與
  `path_base = repository_root`；含歷史 machine path 的舊報告維持不變。
- 本機 inventory `local/migration_inventory_v0_1_1.json` 展開後，在
  `local/migration_manifest_v0_1_1.json` 形成 293 筆非 cache 檔案紀錄；
  manifest 已針對目前 repository／private overlay 驗證，0 failure。兩者維持
  ignored 且為 `REVIEW_REQUIRED`。

以 `scripts/migration_manifest.py create` 建立不覆寫的 local transfer
inventory：第一個 `--source-root` 指向目前 repository worktree，另一個 root
指向私人 Blender layout。Code／documentation 分類為 `PUBLIC_ALLOWED`，填入
實際內容的 report／metadata 為 `REVIEW_REQUIRED`，所有 `.blend` 為
`PRIVATE_ONLY`。在目標機器 clone 後，從其 repository root 執行 `verify`；
不得複製 Codex worktree 的 `.git` pointer。

平台限定的設定、測試、Blender runtime 與遷移指令以
[10_Cross_Platform_Setup_and_Testing.md](10_Cross_Platform_Setup_and_Testing.md)
為準。Shell continuation syntax 並不相容，因此目標驗證指令明確分開。

macOS：

```sh
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

Windows（PowerShell）：

```powershell
py -3 -B scripts/migration_manifest.py verify --manifest local/migration_manifest_v0_1_1.json --target-root .
```

Linux（Bash）：

```bash
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

### 目前里程碑與權威產物

最新 readiness 是 `data/reports/school_v1_first_slice_readiness.json` 的
`READY_FOR_FIRST_DATASET_SLICE`。已完成 immutable source inspection、2,777 個 stable ID 的
治理／確定性指派／持久化驗證、category-agnostic semantic baseline、七項
first-slice task、metadata schema、spatial／visibility contracts、deterministic
render config、已確認的 texture-agnostic policy、versioned derived scene、
fresh-process invariant validation、零 blocker readiness validation，以及 first
dataset generator。Bounded pilot 已保存；唯一歷史上 schema-valid 的 accepted
image 已由後續 render diagnostic 判定不適合作 observation。
Diagnostic-only v0.1.1 r2 render policy 與 derived scene 已通過驗證，未產生
dataset，也未修改 Ground Truth。

權威路徑、逐項狀態與五個 `.blend` SHA-256 以上方 English tables 為準；其中
source、working、validated output 與 invalid preserved output 已明確區分。
Derived output、resource-policy sidecar 與 fresh validation report 已存在且通過。
Pilot `run_pilot_0001` 已產生 evidence，但在 50 attempts 內只有 1 筆歷史
accepted、49 rejected；該 accepted image 現為 `OBSERVATION_RENDER_INVALID`，
有效 accepted 數為 0，因此不是完成的 10-sample pilot。

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

舊的 scene-level readiness report 仍沒有 blocker，但它早於 rendered-image
diagnostic，不能用來授權 generation。Pilot milestone 為 `REVIEW_REQUIRED`：
唯一歷史 accepted image 現為 `OBSERVATION_RENDER_INVALID`。v0.1.1 replacement
render policy 已核准供 diagnostic 使用，derived scene 也已通過 fresh-process
validation；但 sweep、threshold 與跨環境驗收證據依 OQ-016 尚未完成。兩個 target-only occlusion count mismatch、一個
AOV/ray audit mismatch 尚未解決；另有 cleanup defect 造成後續 46 次在 render 前被拒絕。
程式修正已完成，但因 50-attempt 授權上限用完而未以新 run 驗證。五個 legacy
original image 仍未找到，但不是已核准 texture-agnostic runtime policy 的
dependency；不得靜默替換。
OQ-012 對未來產物的一般 publication reviewer authority 仍為 `OPEN`，但本次
已由 human authorization 明確核准目前 50 個 project paths；任何後續新增或
修改的 `REVIEW_REQUIRED` artifact 都必須重新審查。

#### GUI 與正式 render 的預期差異

目前 `.blend` 的 Layout viewport 儲存為 Material Preview，使用 viewport-only
`forest.exr` studio light，並關閉 scene lights 與 scene World。若以 GUI
automation 點選 camera 後取得作業系統截圖，捕捉到的是該 viewport 狀態，且可能
包含 overlay、selection／UI state、視窗縮放與 display 行為；它不能證明與
deterministic EEVEE F12 render 或 Ground Truth 使用的 scene state 相同。此類
截圖只能作為 diagnostic evidence；權威 `image.png` 必須由有完整紀錄的 Blender
render path 產生。已確認診斷與量測位於
`data/reports/render_diagnostics/school_v1_observation_render_diagnostic_v0_1_0.json`。

下一步不得執行 dataset pilot。Peter 必須決定是否維持已確認的 decoded-pixel
identity requirement，並接受、修改或拒絕 proposed composition threshold。
Windows／Linux 交接時，應 clone branch、恢復私人 r2 scene 與 `REVIEW_REQUIRED`
overlay、驗證 migration manifest 與 runtime lock，並記錄目標 OS、architecture、
Blender build、backend、device 與 driver。任何目標端 diagnostic 都必須使用新的
environment-scoped output directory。三筆 substantive GT mismatch 不在本遷移
任務內；新 pilot 仍需另行授權並使用新的 immutable run ID。

### 安全界線

不得修改 `blender/source/`、覆寫歷史 output、猜測 semantic category、靜默替換
resource、從名稱重建 ID、或未經獨立授權變更 geometry／transform／material
structure／UV／modifier／rig／constraint。Observation、Blender state 與 Ground
Truth 不一致時必須使 sample invalid，保留證據並記錄原因。
