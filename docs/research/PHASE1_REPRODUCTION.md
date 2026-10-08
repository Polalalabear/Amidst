# Phase 1 finalization reproduction / 收尾重建

## 2026-10-08 current reviewed reproduction / 目前 reviewed 重建

目前請依 [reviewed reproduction guide](PHASE1_REVIEWED_REPRODUCTION.md) 重建 V5；
設定、case scope 與實際結果見 [reviewed benchmark](PHASE1_REVIEWED_BENCHMARK.md)。
[Curated dataset manifest](../../data/finalization/reviewed_checkpoint_v2/dataset_manifest.json)
綁定 canonical `reviewed_run_v5` 輸入；
[local reproduction receipt](../../data/finalization/reviewed_checkpoint_v2/local_reproduction_verification.json)
記錄 repeat、fresh process、ordering、GT poison 與 annotation isolation PASS；
[complete fresh delivery receipt](../../data/finalization/reviewed_checkpoint_v2/fresh_delivery_comparison_final.json)
記錄 dataset、canonical inference、reports 與 demos 比較 PASS，明列 runtime/RRD
metadata 的排除範圍。

這些 PASS 限於 ready reviewed cases，沒有授予整體 Exit Gate 或 freeze；Case2 與
Case3 full stress 仍 blocked。Source、GT/inference 隔離與新的 output directory 規則
沿用 reviewed guide。以下舊指令與 pending 狀態保留為歷史 diagnostic checkpoint，
目前重建使用上方 reviewed guide；原 protocol 不變。

Status: **PHASE1_FINALIZATION_BLOCKED**. The commands below reproduce the
completed diagnostic checkpoint. They do not execute or certify formal Cases 1–3.

## 繁體中文

從 `phase1/finalization-sprint` 的 published SHA 建立乾淨 checkout。提供本機原始
`school_v3.blend`，SHA-256
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`，
468,300,506 bytes。使用 Blender 5.2.1 LTS build `9e2066aef7ef`，CPython 3.12.12
與 committed `uv.lock`。不縮放或儲存 source；沒有自動下載大型資產。

```sh
uv sync --locked --python 3.12.12
uv run python -m amidst.materialize_physical_evidence \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --source-scene /absolute/path/school_v3.blend

/Applications/Blender.app/Contents/MacOS/Blender \
  --background --disable-autoexec /absolute/path/school_v3.blend \
  --python scripts/export_phase1_finalization_inputs.py -- \
  --config configs/phase1_finalization_export_v1.json \
  --output data/finalization/local_run/dataset

uv run python scripts/replay_phase1_finalization_diagnostics.py \
  --dataset data/finalization/local_run/dataset \
  --output data/finalization/local_run/diagnostics

uv run python - <<'PY'
import json
from pathlib import Path
from amidst.benchmark.baselines import diagnostic_baseline_regression
Path('data/finalization/local_run/baseline_regression.json').write_text(
    json.dumps(diagnostic_baseline_regression(), sort_keys=True, indent=2) + '\n')
PY
```

每次 export / replay 必須使用不存在的新 output。Exporter 只在 simulation/export
讀取既有 pilot trajectory definitions；`inference/<stream>/` 只含 pixels、timestamps、
visibility 和 calibration/independent diagnostic plane。`simulation/` 與 `evaluation/`
分開保存 recipe 和 GT，禁止給 Graph / ranking / reconstruction。Native BU 保留，
距離報告乘以已核准 `0.0247 m/BU`；legacy pilot schema 的 `UNVERIFIED` label 和
`*_m` 欄位不能被當作公尺。Replay 分別跑 legacy fixed-plane 與 optional additive
policy projector，共用原 Graph；covariance 保留 sidecar，不參與 ranking/pruning。

Fresh checkout 使用相同指令與新的 `data/finalization/fresh_run/` paths。
比較 dataset manifest 的全部 artifact hashes、canonical policy sidecars、Graph
candidate order / termination 與 evaluation。Runtime 是實測值，RRD container UUID
和 recording timestamps 不要求 byte-identical；comparison 使用 canonical presentation
與 inference JSON。不能把排除 wall clock 當成排除研究結果。

Local / fresh dataset 和 replay 完成後產生 curated checkpoint：

```sh
uv run python scripts/report_phase1_finalization.py \
  --local data/finalization/local_run \
  --fresh /absolute/path/to/fresh-checkout/data/finalization/fresh_run \
  --output data/finalization/checkpoint
```

```sh
AMIDST_PHYSICAL_SOURCE_SCENE=/absolute/path/school_v3.blend \
  uv run pytest --require-physical-evidence -rs
uv run ruff check .
uv run mypy
git diff --check
```

正式輸入保持 locked/pending，見 [input lock](../../data/finalization/checkpoint/input_lock.json)
和 [human gate](../../human_review/README.md)。核准前沒有正式 metric epsilon；不可替入
pilot/regression epsilon。Case definitions、baseline A/B/C、metric formulas 沿用
[既有 protocol](PHASE1_BENCHMARK_PROTOCOL.md)。Case 4 DEFERRED，Phase 2 FROZEN。
Gate payload 經 source-bound certificate 重跑及正式設定版本化後，再建立新的 formal
dataset version，執行正式 Cases、poison/replay/fresh gates；全部通過才建立 freeze tag。

## English

Use a clean checkout of the published finalization SHA, the exact source hash/size,
Blender build, Python version and lockfile above. The commands reproduce fresh
physical materialization and three existing pilot definitions. Their output remains
DIAGNOSTIC; no school route, camera-plane or formal metric authority is inferred.
Supply a new destination for every run. Preserve native coordinates and explicitly
convert reporting distances to metres. Keep simulation/evaluation directories away
from inference. Replay runs both the legacy fixed-plane projector and the optional
additive policy hook over the existing Graph. Covariance remains a sidecar and is
not used for ranking/pruning. Existing endpoint/topology contracts still apply;
input rejection is recorded without inventing a termination category.

Compare every dataset hash and canonical inference/presentation/evaluation artifact.
Runtime and RRD container metadata are recorded but not deterministic content.
The consolidated human gate must bind a certified local navigation scope,
case-specific routes/cameras/timing and formal metrics before formal execution.
Version those inputs before benchmarking. Case 4 and Phase 2 remain deferred/frozen;
the blocked checkpoint must not receive a Phase 1 freeze tag.
