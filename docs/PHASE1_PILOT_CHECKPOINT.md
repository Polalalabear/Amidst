# Phase 1 successful pilot checkpoint / 第二個斷點

Checkpoint date: **2026-10-05**. This preserves the successful WALL-marked bounded
Blender pilot before downstream work. It is PILOT / SYNTHETIC SAMPLE evidence,
with no formal Case 1–3 or physical/navigation acceptance.

| Item | Verified value |
| --- | --- |
| Preserved checkpoint branch | `phase1/pilot-dataset-and-wall-inference` |
| Checkpoint commit | `fdf9e7e8f2dc695917ba42094a63cc06ca910963` |
| Origin | `https://github.com/Polalalabear/amidst.git` |
| Push | Successful; upstream set |
| Live origin SHA from `git ls-remote --heads` | `fdf9e7e8f2dc695917ba42094a63cc06ca910963` |
| New branch, created at the exact checkpoint | `phase1/pilot-downstream-reconstruction` |
| Earlier semantic scene checkpoint | `91f4ea600805739aa9659dfef6a381d71be9a692` |

Working tree was clean and HEAD matched the requested SHA before publication.
Fresh requested checks all pass: **847 pytest tests in55.97s**, no skips; Ruff;
mypy for72sourcefiles; git diff --check. Native Blender/uv checks run outside the
sandbox, without removing or skipping tests. The checkpoint branch stays at this
published commit; subsequent implementation and its final commit belong only to
the new downstream branch. No merge back or downstream-branch push is performed.

本次在原branch確認clean與完整檢查，push後直接查詢origin SHA完全一致，再建立新branch。
這份記錄存於續作branch，不另改寫第二個checkpoint commit。回到斷點前先保存dirty work，
再 `git switch phase1/pilot-dataset-and-wall-inference`；不使用destructive reset。

## Preserved local assets / 本機資料

- Original `blender/school_v3.blend`: SHA
  `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`.
- Derived `blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend`:
  SHA `b4d3394b17626bfdf35ee9b9e35c1f5a4469dd75a3e24b1a4f5f5aa58bdf4d49`.
- 81 saved exact-face WALL annotations / 1,491 HUMAN_REVIEW patches. All28portals
  have zero actual face intersections; original object/physical geometry is unchanged.
  WALL selections do not grant complete collision/navigation authority.
- Existing ignored `data/pilot/phase1_wall_pilot_20261005/office/`: one route,
  10s / 5FPS / 50timestamps / 100cameraPNGs, evaluation-only combined dataset,
  separate GT/2D observations, reports, representative frames and preview.
  Dataset SHA `77203e33a566f99936e6446133dae245231562b0a64bfc82447e5f1215d5d2df`.

Raw `.blend`, GT and PNG assets remain at their existing ignored local paths; Git
preserves code, recipes and source-bound audit evidence. Switching branches does
not restore ignored assets. Downstream work uses fresh output directories and
preserves this original pilot, including input/source hashes, sizes and mtimes.

## Continuation / 續作範圍

Only a bounded downstream validation on existing1–3smalltrajectories:
Observation → inverse Projection → provisional Topology → Graph candidates →
Top-K gap reconstruction → evaluation → Rerun/3D visualization. Preserve GT isolation
and every candidate in deterministic prior order. GT enters evaluation/debug only,
after inference; it never chooses the best candidate. Physical/collision validity
is partial/provisional, not a school mesh or complete WALL certification.

不生成新dataset、不改正式benchmark semantics、不開始Case1–3。歷史ELEVATOR AREA
名稱不產生transition。完成小型閉環、determinism、GT poison與visualization驗證後先停。
Durable rules remain in [DEVELOPMENT_RULES](DEVELOPMENT_RULES.md), completed work in
[WORK_LOG](WORK_LOG.md), and current status in [CODEX_HANDOFF](CODEX_HANDOFF.md).
