# Phase 1 持久 runtime 恢復 / Restored runtime

日期：2026-10-08。目前工作目錄為
`/Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization`，
branch `phase1/finalization-sprint`，恢復起點
`5c2b67b9c48ae4028fd9fb2e7636f6b3af5121c0`。Canonical checkout
`/Users/polalabear/Developer/amidst` 保留原 physical branch，只供應 immutable assets。

**實際 runnable gates 以 [本次 validation receipt](../../data/finalization/recovery_checkpoint_20261008/validation.json)
為準。** 本頁記錄恢復方法與實際重新運行結果；pytest、scope regeneration、primary inference、
evaluation 與 reproduction 的精確證據以新 receipt 為準。歷史 PASS 不代替本次驗證。
下一段研究實作見 [release handoff](PHASE1_RESEARCH_RELEASE_HANDOFF.md) 與
[next-chat prompt](PHASE1_NEXT_CHAT_PROMPT.md)，使用本頁的持久路徑。

## 已確認的恢復 / Confirmed restoration

- Committed `uv.lock` 的 Python 3.12.12 environment 已 offline 安裝；使用 uv 預設 cache。
- 八份原 diagnostic JSON（五份 review pins、三份 topology prerequisites） 在 canonical
  `data/pilot/phase1_finalization_20261006/local_run/` 找到，全部符合原 locked hashes。
  原 diagnostic exporter 亦已實際重跑，office context／observations 的兩個 pins 相符。
- 四個 physical gzip blobs 已複製並驗 hash；`materialize_physical_evidence --verify-only`
  得到 `VERIFIED`。Hydration 驗證 297 files：187 copied、110 existing；29 locked inputs
  和原 review package／57 frames 恢復。原 source bytes 不變。
- 本地 school-v2／v3 symlinks 指向 canonical assets；school-v2 calibration 已複製並驗證
  SHA `5eaa94b97b188514ceb2f2e4cc6c6cc6ab63583c6fb6bb2ebda375d5be296bd7`。
- Fresh reviewed export 已完成：Case1 50 timestamps、Case3 925 timestamps；Case2 BLOCKED。
  本次 raw run 是 `data/finalization/reviewed_run_recovery_20261008/`，**不得覆寫**。
  Ruff、111 package files 的 mypy 與 source CLI 的 strict mypy 已 PASS。
  Primary inference freeze、evaluation、ready-case reproduction 已實際完成；兩個 RRD reader
  verified、primary GT=false。完整 corridor 數值重建 PASS；完整測試 **1978 passed／0 failed／0 skipped** (116.28s)。

原 HR01–HR04、reference MOVING/departure-DWELL policy 與 exact corridor proposal 的核准
和 application receipts 都由 Git 保存，無須重新詢問。Corridor certificate 不使旧 office
CLI 自動支援新 union；Case2／Case3 full stress 與原 full Exit 仍須完成原 gates。

## 恢復原 inputs / Restore original inputs

在此持久 worktree 執行。以下只補 missing bytes，`cp -n` 保留已有檔案；後續驗證遇到
mismatch 必須停止，不能換成新 formal dataset 或改 lock。

```sh
cd /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization
uv sync --locked --offline --python 3.12.12
phase1_canonical=/Users/polalabear/Developer/amidst
phase1_historical="$phase1_canonical/data/pilot/phase1_finalization_20261006/local_run"

for phase1_relative in \
  dataset/inference/office/context.json \
  dataset/inference/office/observations.json \
  diagnostics/office/policy_graph_primary/candidates.json \
  diagnostics/office/policy_graph_primary/projected_frames.json \
  diagnostics/office/primary.json \
  diagnostics/office/policy_graph_primary/pipeline_config.json \
  diagnostics/office/policy_graph_primary/digests.json \
  diagnostics/office/policy_graph_primary/topology_evidence.json
do
  mkdir -p "data/finalization/local_run/${phase1_relative%/*}"
  cp -n "$phase1_historical/$phase1_relative" "data/finalization/local_run/$phase1_relative"
done

phase1_physical=data/scene_audit/phase1_physical_policy_approval_20261006
for phase1_blob in source_evidence.json.gz floor_support_details.json.gz \
  geometry.json.gz obstacle_collider_details.json.gz
do
  cp -n "$phase1_canonical/$phase1_physical/$phase1_blob" "$phase1_physical/$phase1_blob"
done

uv run --offline --no-sync python -m amidst.reviewed_input_hydration \
  --root "$PWD" --historical-root "$PWD" \
  --durable-review "$phase1_canonical/data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review"
uv run --offline --no-sync python -m amidst.materialize_physical_evidence \
  --source-scene "$phase1_canonical/blender/school_v3.blend" --verify-only
```

完整測試還使用歷史 school-v2 asset/calibration；本次用 symlinks 保留原場景而未複製
大型 `.blend`。新 checkout 可按下列方式補 missing links，已有路徑不可覆寫：

```sh
mkdir -p blender data/cameras
for phase1_scene in school_v2.blend school_v3.blend
do
  if [ ! -e "blender/$phase1_scene" ] && [ ! -L "blender/$phase1_scene" ]; then
    ln -s "$phase1_canonical/blender/$phase1_scene" "blender/$phase1_scene"
  fi
done
cp -n "$phase1_canonical/data/cameras/school_v2_calibration_v1.json" data/cameras/
BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender \
AMIDST_PHYSICAL_SOURCE_SCENE="$phase1_canonical/blender/school_v3.blend" \
uv run --offline --no-sync pytest --require-physical-evidence -rs
uv run --offline --no-sync ruff check .
uv run --offline --no-sync mypy
uv run --offline --no-sync mypy --strict scripts/discover_source_branch_scope.py
```

Historical root 指向此 exact restored checkout；canonical physical branch 的部分 source
files 不同，不能直接當完整 hydration root。若 raw blobs 缺失，可用原 materializer
配合 `--blender /Applications/Blender.app/Contents/MacOS/Blender` 重建，仍須符合原 manifest。

## Fresh reviewed run / 可執行主流程

以下選用**尚不存在的新版本目錄**；不要重跑到 recorded recovery run 或任何歷史輸出。
使用已保存的 office application、V2 export config 與 V3 collision inference lock。

```sh
phase1_run=data/finalization/reviewed_run_replay_20261008_v1
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --disable-autoexec /Users/polalabear/Developer/amidst/blender/school_v3.blend \
  --python scripts/export_phase1_reviewed_inputs.py -- \
  --config configs/finalization/reviewed_case_export_with_movement_v2.json \
  --application data/finalization/human_review_applied_v1 \
  --output "$phase1_run/dataset"
uv run --offline --no-sync python scripts/run_phase1_reviewed.py infer \
  --dataset "$phase1_run/dataset" --application data/finalization/human_review_applied_v1 \
  --config configs/finalization/reviewed_case_inference_with_collision_v3.json \
  --output "$phase1_run/inference_primary"
uv run --offline --no-sync python scripts/run_phase1_reviewed.py evaluate \
  --dataset "$phase1_run/dataset" --application data/finalization/human_review_applied_v1 \
  --inference "$phase1_run/inference_primary" --output "$phase1_run/evaluation"
uv run --offline --no-sync python scripts/run_phase1_reviewed.py verify-reproduction \
  --dataset "$phase1_run/dataset" --application data/finalization/human_review_applied_v1 \
  --config configs/finalization/reviewed_case_inference_with_collision_v3.json \
  --inference "$phase1_run/inference_primary" --output "$phase1_run/reproduction"
```

完成後讀 `evaluation/verification.json`、`reproduction/verification.json`；benchmark 在
`evaluation/benchmark_table.{json,csv,md}`，消融在 `evaluation/ablations/`。
Ready-case demo 位於 `evaluation/demos/case1/` 和 `case3/`：RRD、preview PNG、presentation
與 reader/replay 證據。Primary GT=false；GT/reference 只供 freeze 後的獨立 evaluation。

```sh
uv run --offline --no-sync rerun "$phase1_run/evaluation/demos/case1/reviewed.rrd"
```

舊 temporary worktrees、fresh outputs 與 RRD 已遺失；Git 的 historical receipts、表格和
curated evidence 仍在。舊 `/private/tmp` 地址僅是歷史記錄，不表示目前檔案可用。
恢復 runtime 不授予新 scope、Case readiness、整體 Exit 或 freeze；Case4 DEFERRED、Phase2 FROZEN。

## English

Use the persistent sprint checkout above. The locked Python environment, exact historical
inputs and physical evidence were restored; source and approval bytes remain unchanged.
Read the current recovery validation receipt for actual test, regeneration, inference,
evaluation and reproduction outcomes. All prior approvals persist without repeated questions.

The commands restore surviving original bytes and run the existing office pipeline with its
preserved application and V3 collision lock. Choose a new output directory; never overwrite
the recorded recovery run. Dataset, frozen inference, benchmark and Rerun demo must refer to
the same run. The new corridor union still needs the additive adapters and readiness work
listed in the release handoff. Lost temporary raw outputs are historical; preserved Git
receipts do not imply their current availability or grant the full Phase 1 Exit Gate.
