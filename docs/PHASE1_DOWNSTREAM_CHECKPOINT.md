# Phase 1 successful downstream checkpoint / 第三個斷點

Checkpoint date: **2026-10-06**. This preserves the completed one-trajectory downstream
PILOT; it does not certify formal geometry, WALL collision or Cases 1–3.

| Item | Verified value |
| --- | --- |
| Checkpoint branch | `phase1/pilot-downstream-reconstruction` |
| Checkpoint commit | `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` |
| Origin branch | `origin/phase1/pilot-downstream-reconstruction` |
| Live remote SHA | `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` |
| Continuation branch | `phase1/pilot-robustness-validation` |
| Continuation starting SHA | `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e` |

Before publication, the working tree was clean and fresh checks passed:
`uv run pytest` **895 passed in 81.15s, no skips**; `uv run ruff check .` passed;
`uv run mypy` passed for **74 source files**; `git diff --check` passed.
Push created the remote branch/upstream, and live `git ls-remote --heads origin`
returned the identical full SHA. The checkpoint commit/branch was not rewritten.

The continuation is isolated at
`/Users/polalabear/.codex/worktrees/pilot-robustness-validation/amidst` after parallel
work switched the shared checkout to `phase1/geometry-authority`. Only task-owned
untracked robustness files were moved, with hash verification. Parallel geometry
files and the shared checkout were preserved; no geometry work enters this commit.

The successful downstream assets remain local/ignored at
`/Users/polalabear/Developer/amidst/data/pilot/phase1_downstream_20261005/`:
one office trajectory, 100 records, 26 inverse projections, one 4.0–9.0s bounded gap,
3 candidate routes / 6 timed hypotheses / COMPLETE, evaluation-only metrics,
GT poison invariance, and inspected PNG/readable Rerun. Original/derived Blender
assets and original pilot data remain unchanged. Recovery also needs these local
ignored assets; Git contains recipes/tests/docs, not private GT/renders/RRD.

回復此斷點前先保存當前 dirty work；核對 branch、HEAD、origin 與本機 ignored assets。
不在 dirty shared checkout 強制切換、reset 或 merge。第三個 checkpoint 保留原本
single-trajectory pilot，九個 robustness controls 與後續 commit 僅在新 branch。

GT remains export/evaluation/debug-only, Top-K remains unranked by GT, and all
physical validity is PARTIAL / PROVISIONAL. Existing benchmark semantics and formal
Case 1–3 execution remain unchanged/deferred. This record is on the continuation
branch and does not add a new commit to the checkpoint branch.
