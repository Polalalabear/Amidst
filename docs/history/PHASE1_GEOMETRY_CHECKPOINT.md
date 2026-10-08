# Phase 1 geometry authority checkpoint / Geometry authority 斷點

Checkpoint date: **2026-10-06**.

| Item | Verified value |
| --- | --- |
| Preserved branch | `phase1/geometry-authority` |
| Checkpoint commit | `bb66bb74a4a76430f6fa8f79672345385a79e3f0` |
| Origin | `https://github.com/Polalalabear/amidst.git` |
| Push | Successful; upstream set |
| Live origin SHA | `bb66bb74a4a76430f6fa8f79672345385a79e3f0` |
| New branch at exact checkpoint | `phase1/physical-authority-resolution` |

Before publication, working tree was clean and HEAD matched the requested SHA.
Fresh checks: **996 pytest tests passed in 85.24s, no failures or skips**;
Ruff, mypy (77 source files), and `git diff --check` passed. After the normal push,
`git ls-remote --heads origin refs/heads/phase1/geometry-authority` returned the
identical full SHA. No force push, merge, rebase or history rewrite occurred.

本文件記錄在續作 branch，不另外修改 checkpoint commit。恢復前先保存目前工作，
再切換 checkpoint branch；不使用 destructive reset。Git 切換不會還原 ignored assets。

## Preserved evidence / 保留證據

- [Per-patch review](../../data/scene_audit/phase1_geometry_authority_20261006/authority.md):
  73 HIGH_CONFIDENCE / 1,422 HUMAN_REVIEW / 77 REJECTED / 0 APPROVED WALL patches.
- [Geometry provider](../specs/GEOMETRY_PROVIDER.md): read-only, source-bound, platform-neutral,
  with explicit refusal of incomplete or unapproved formal physical scope.
- Original `blender/school_v3.blend` SHA-256:
  `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`.
- Derived `blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend` SHA-256:
  `b4d3394b17626bfdf35ee9b9e35c1f5a4469dd75a3e24b1a4f5f5aa58bdf4d49`.

## Continuation / 續作範圍

Resolve the eight OBSTACLE/PORTAL conflicts, inspect source-backed stair landings and
openings, cross-check proposed floor planes, and define config-driven physical policy
and explicit authority scopes. Preserve the 73 HIGH_CONFIDENCE walls as provisional
evidence without forcing the remaining patches into approval. Evidence gaps remain REVIEW.

不開始正式 Case 1–3，不更改 benchmark semantics、ranking 或 GT isolation；不 merge。
本輪工作與最後 commit 僅存在 `phase1/physical-authority-resolution`，checkpoint branch
保持已發布的 SHA。規則見 [DEVELOPMENT_RULES](../specs/DEVELOPMENT_RULES.md)，完成紀錄見
[WORK_LOG](WORK_LOG.md)，當前狀態見 [CODEX_HANDOFF](../operations/CODEX_HANDOFF.md)。
