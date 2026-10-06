# Phase 1 diagnostic demo / 診斷展示

Formal Case 1–3 recordings: **N/A / NOT_RUN** until the
[human gate](../human_review/README.md) passes.

Fresh exported office / corridor / auditorium recordings are local DIAGNOSTIC
artifacts under `data/finalization/local_run/diagnostics/`. Each stream has
`summary.json` and `demo/presentation.json`; its recording and PNG are
`demo/diagnostic.rrd` and `demo/preview.png`. Replay with:

```sh
uv run rerun /absolute/path/to/diagnostic.rrd
```

查看 scene context、校準 cameras、OBSERVED/GAP、projection method/confidence、
configured Top-K/timing（若 legacy Graph contract 可執行）。GT debug 在獨立 entity
layer，初始不顯示；可由 Rerun entity visibility 控制。未取得 authority 的 collider
pruning、floor/scope certification 與 surface-constrained school inference 應顯示
N/A，不得由 annotation box 或空 collider 集合視覺上宣稱 PASS。

The static PNG and canonical presentation JSON are reproducible previews.
Recording-reader checks are saved separately in the checkpoint. A replayable
diagnostic recording is not a formal Case recording or a certified school mesh.
The source Blender file remains unchanged; no new building geometry is invented.
