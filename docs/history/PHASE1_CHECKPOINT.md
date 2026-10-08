# Phase 1 semantic scene checkpoint / 語意場景大斷點

Checkpoint date: **2026-10-05**. This preserves the current Phase 1 implementation,
source-bound semantic evidence and bounded pilot state. It is not formal benchmark
acceptance. Rules remain in [DEVELOPMENT_RULES](../specs/DEVELOPMENT_RULES.md), current work in
[CODEX_HANDOFF](../operations/CODEX_HANDOFF.md), and completed evidence in [WORK_LOG](WORK_LOG.md).

## Git checkpoint and continuation / Git 斷點與續作

| Item | Value |
| --- | --- |
| Checkpoint branch, preserved after publication | `codex/dataset-infrastructure` |
| Validated implementation baseline | `4437ef3e468d3b18181f893906619af021042434` |
| Checkpoint commit message | `checkpoint: preserve phase1 semantic scene state` |
| Origin | `https://github.com/Polalalabear/amidst.git` |
| Branch created from the checkpoint commit | `phase1/pilot-dataset-and-wall-inference` |

The checkpoint commit adds this record and documentation only, after validating the
implementation baseline. Its full SHA is recorded in the local asset manifest and the
completion report; resolve the preserved checkpoint branch with:

```sh
git rev-parse codex/dataset-infrastructure
git log -1 --format='%H %s' codex/dataset-infrastructure
git status --short
```

後續修改只在 `phase1/pilot-dataset-and-wall-inference`，不 merge 回 checkpoint branch。
開始先核對 branch、HEAD、working tree 與來源 hash。若需要回到斷點，先保留任何 dirty
work，再 `git switch codex/dataset-infrastructure`；不使用 destructive reset。

Future changes belong only on the continuation branch and must not merge back into the
checkpoint branch. Preserve any dirty work before switching back. Git checkout restores
tracked code and evidence; it does not restore ignored Blender assets or pilot files.

## Fresh validation / 本次重新驗證

Starting working tree was clean. All requested commands passed:

| Command | Result |
| --- | --- |
| `uv run pytest` | **821 passed in 58.64s**, no skips |
| `uv run ruff check .` | All checks passed |
| `uv run mypy` | No issues in 72 source files |
| `git diff --check` | Passed |

Native Blender tests and uv run outside the sandbox for the final checks. The sandbox's
macOS initialization failure in uv was resolved by rerunning the same commands outside;
no tests were removed or skipped. Documentation added afterward uses diff and link checks.

## Local scene and pilot preservation / 本機場景與資料保存

| Source property | Value |
| --- | --- |
| Asset | `blender/school_v3.blend` |
| SHA-256 | `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e` |
| Bytes | `468300506` |
| Source mtime_ns | `1791198236746106977` |
| Verified read-only snapshot | `blender/working/checkpoints/phase1-semantic-scene-20261005/school_v3.blend` |
| Local manifest with checkpoint SHA and pilot file hashes | `blender/working/checkpoints/phase1-semantic-scene-20261005/asset_manifest.json` |

Source SHA, size and mtime are unchanged after the snapshot. The snapshot is byte-identical
to the current supplemented scene, rather than the earlier pre-supplement backup.
`.blend`, `blender/working/` and `data/pilot/` remain Git-ignored and are not uploaded by
this push. Preserve the local snapshot and datasets separately when moving computers.
Restore the ignored scene from the verified snapshot only as an explicit future asset
restore action; switching Git branches alone does not change it.

已保存狀態：81 個自動 WALL surface patches、1,491 HUMAN_REVIEW patches，28 PORTAL
的自動牆面 aperture intersections 為0。原 corridor pilot 與教室／禮堂／辦公區三組
PILOT / SYNTHETIC SAMPLE 保留在 `data/pilot/`，共200 timestamps／400原始PNG。
各組都有獨立2D observations／GT／plan／validation／代表影格；三組新資料另有 comparison。
Pilot 檔案以本機 manifest hashes 核對，沒有因 checkpoint 重新 render。

The tracked audit evidence records 81 automatic WALL patches and 1,491 review patches,
with all 28 portal apertures protected. Four local pilots retain 200 timestamps and
400 raw camera PNGs, separate 2D/GT exports and diagnostic evidence. They are synthetic
samples; classroom is a center-point control, auditorium has one partial-body GAP,
and office has 24 GAP timestamps, 19 fully hidden. No new rendering occurs for this checkpoint.

## Continuation boundary / 後續範圍

Only on the new branch: WALL candidate extraction, semantic fixes determined by explicit
existing geometry/metadata rules, and bounded 10-second / 5-FPS / 50-timestamp pilots with
2–3 cameras and visible → GAP → visible trajectories. Preserve source/Observation/render
provenance, independent projection/visibility/occlusion checks and human review for ambiguity.

GT 僅 simulation/export/evaluation/debug visualization，不進 Projection inference、Graph、
ranking 或 reconstruction。不得封住 doorway／PORTAL；window／door panel／decoration
歧義保留 HUMAN_REVIEW。只有樓梯，歷史 ELEVATOR AREA 名稱不建立 elevator transition。
不修改正式 benchmark semantics、不執行正式 Case1–3、不 merge 回 checkpoint branch。

GT remains excluded from inference, Graph, ranking and reconstruction. Ambiguous semantics
stay under review; no doorway infill or elevator transition is introduced. Formal benchmark
semantics and Cases 1–3 remain untouched. Existing floor/scale/geometry authority gaps and
full-dataset readiness limitations remain open in the handoff.
