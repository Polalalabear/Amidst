# Physical evidence materialization / 物理證據重建

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

### Checkpoint 與發布邊界

`phase1/physical-policy-lightweight` 直接以已同步遠端的
`phase1/physical-authority-resolution`、
`0bab8ac262b93f3c8babad69432744e7e4d1c541` 為基底。
原本完整 local evidence checkpoint
`c5956dc825f669e28e2694578be0fed97432a786` 保留為來源 reference，
不是此 branch 的祖先。該 local checkpoint 已產生並保存完整證據；本 checkpoint
選擇性保留 source/config/tests/docs、研究紀錄、摘要與 hashes，未改寫原研究 provenance。

[原始 review manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/manifest.json)
維持原內容；新增的
[canonical artifact manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json)
記錄每個 artifact 的 filename、預期 byte／canonical JSON SHA-256、source scene SHA-256、
generating command、config、producer version／commit 與 semantic role。
大型 generated paths 由精確 `.gitignore` 規則排除：

| Artifact | Semantic role |
| --- | --- |
| `source_evidence.json.gz` | 固定 selection config 抽取的 evaluated source atlas，保留 exact faces／components／hidden geometry |
| `geometry.json.gz` | source-bound geometry snapshot，供 purpose-gated physical consumers 載入 |
| `floor_support_details.json.gz` | 完整 support faces、supported/uncovered 子域與 floor evidence |
| `obstacle_collider_details.json.gz` | 完整 source components、closed-volume guards 與 collider binding witnesses |

這四份 raw generated blobs、local `materialization_receipt.json`、source `.blend`、renders
與 `.rrd` 都不由此 checkpoint 發布。小型 approval summaries、`physical_authority.json`、
`body_clearance_policy.json`、`floor_authority_map.json`、`local_physical_scopes.json`、
`collision_pruning_results.json`、`obstacle_collider_authority.json`、兩份 manifest 與
[authority report](../data/scene_audit/phase1_physical_policy_approval_20261006/authority.md) 保留在 Git。
基底已追蹤的 `source_mesh_evidence.json`、semantic audit 與既有 geometry snapshots
保留原狀；本任務排除的是新 physical-policy bundle 的四份可重建 raw blobs，
不另外清理基底歷史 evidence。

### 明確重建流程

從 repository root 執行 `uv sync --locked --python 3.12.12`，使用 manifest 記錄的
CPython 3.12.12 與固定 `uv.lock`。另外提供未修改的本機 source scene：

- filename：`school_v3.blend`
- SHA-256：`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`
- size：468,300,506 bytes
- 原 full-evidence producer：Blender 5.2.1 LTS、build `9e2066aef7ef`

Materializer 接受外部絕對路徑，不會自動下載 scene 或改動 source。
Integration tests 透過 `AMIDST_PHYSICAL_SOURCE_SCENE` 使用同一外部 source；
未設定時預設讀 ignored `blender/school_v3.blend`。

```sh
uv run python -m amidst.materialize_physical_evidence \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --source-scene /absolute/path/school_v3.blend
```

此單一命令使用 committed exporter／selection config 和原 validation pipeline，
在 temporary workspace 重建四份 artifacts、完整重跑 physical-policy validation、
核對 manifest 中每份 raw artifact 的 byte hash 與 canonical JSON hash，再安裝到 ignored
generated paths。所有摘要的 canonical content 均須符合原 checkpoint；
`collision_pruning_results.json` 的 `runtime_seconds` 只作執行記錄，研究比較明確排除此欄。
原 tracked summaries 與原 manifest 不覆寫。驗證結果與實際 source fingerprint
記入 ignored `materialization_receipt.json`。

Source atlas 的 `source_mtime_ns` 是非幾何 timestamp。相同 SHA／size 的 scene 副本
可能有不同本機 mtime；wrapper 只在 temporary atlas 將此欄正規化為歷史 manifest
已記錄的值，讓固定 geometry evidence 可 byte-identical 重建。
實際副本的完整 before／after fingerprint 另記 receipt，來源檔案本身不修改，
原 provenance 與 producer/config/code identities 不偽造或回寫。

只驗證已 materialize 的 evidence，不生成或寫入：

```sh
uv run python -m amidst.materialize_physical_evidence \
  --source-scene /absolute/path/school_v3.blend \
  --verify-only
```

若另需獨立 report replay，此原 validation CLI 使用 config 中的 ignored
`blender/school_v3.blend`，須先提供相同 SHA／size 的本機副本到此路徑。
使用不同 output，保留歷史 bundle：

```sh
uv run python -m amidst.physical_policy_validation \
  --config configs/physical_policy_validation_school_v3.json \
  --output /tmp/amidst-physical-policy-review
```

### Fresh-clone 測試契約

沒有大型 evidence 時，`uv run pytest` 的 unit tests 與 committed summary／config／hash
assertions 正常執行；需要 scene 或 raw blobs 的 integration tests 使用
`external_physical_evidence` marker，明列 missing prerequisites 與上述 materialization
command 後 skip。Unit tests 使用小型 committed fixtures。測試不偷偷生成或下載 evidence。
CLI 缺 prerequisite 會回報明確 materialization 錯誤，列出 missing source/artifact
與重建命令；沒有本機 source 不是沒有通過研究驗證。
另外，歷史 school-v2 scene／private calibration 測試缺其各自 external fixtures 時仍可
明確 skip；它們不是本輪 physical-policy evidence，完整 materialization 不生成這些舊資產。

```sh
# Lightweight profile; skips 的理由可用 -rs 顯示。
uv run pytest -rs
uv run ruff check .
uv run mypy
git diff --check

# Fully materialized profile; 缺 evidence 視為明確失敗。
AMIDST_PHYSICAL_SOURCE_SCENE=/absolute/path/school_v3.blend \
  uv run pytest --require-physical-evidence -rs
```

只驗證外部 evidence bundle 也可執行：

```sh
AMIDST_PHYSICAL_SOURCE_SCENE=/absolute/path/school_v3.blend \
  uv run pytest --require-physical-evidence \
  tests/integration/test_physical_policy_authority_bundle.py -rs
```

### 固定研究結果

重建必須保持 architectural scale **APPROVED**、physical policy **APPROVED**、
48 supported floor subdomains、58 approved components across 5/19 obstacles、
8 portal conflicts **HUMAN_REVIEW**、Stair A/B **REVIEW**、overall **PARTIAL_APPROVED**，
以及 collision diagnostic **4 → 2**。Local complete islands 仍為 0，global
`physical_complete=false`。不調 threshold、不升格 retained probes 為正式 navigation
候選、不開啟 Cases 1–3、Agent 或 Finalization Sprint。

## English

### Checkpoint and publication boundary

`phase1/physical-policy-lightweight` starts directly from the synchronized
`phase1/physical-authority-resolution` commit
`0bab8ac262b93f3c8babad69432744e7e4d1c541`.
The full local evidence checkpoint
`c5956dc825f669e28e2694578be0fed97432a786` remains a source reference, rather than an
ancestor of this branch. That local checkpoint produced and retained the full evidence.
This checkpoint selectively retains source/config/tests/docs, experiment records, summaries
and hashes while preserving historical research provenance.

The [original review manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/manifest.json)
is unchanged. The added
[canonical artifact manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/artifact_manifest.json)
records filenames, expected byte and canonical JSON SHA-256 hashes, source-scene hashes,
generating commands, configs, producer versions/commits and semantic roles.
The four generated gzip paths in the table above are precisely gitignored. The local
receipt, source `.blend`, renders and `.rrd` are also excluded. Git retains the small
approval summaries, physical authority, policy, floor map, local scopes, collision result,
obstacle authority, both manifests and the linked authority report.
Previously tracked source-mesh evidence, semantic audits and geometry snapshots inherited
from the base remain intact. The exclusion applies to the four new physical-policy raw
blobs; this task does not clean up historical base evidence.

### Explicit reproduction workflow

Run `uv sync --locked --python 3.12.12` from the repository root, using the manifest
recorded CPython 3.12.12 and committed `uv.lock`. Supply an unchanged local
`school_v3.blend` with SHA-256
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`
and size 468,300,506 bytes. The original full-evidence producer used Blender 5.2.1 LTS,
build `9e2066aef7ef`. The materializer accepts an external absolute source path. Integration
tests use that same path through `AMIDST_PHYSICAL_SOURCE_SCENE`, defaulting to the ignored
`blender/school_v3.blend` when unset. Neither workflow downloads or modifies the scene.

Use the materialization command above. It runs the committed exporter/selection config and
original validation pipeline in a temporary workspace, reconstructs all four raw artifacts,
reruns the complete physical-policy validation, verifies both byte and canonical JSON hashes,
then installs only the ignored artifacts. Regenerated report canonical content must match
the checkpoint; only `runtime_seconds` in collision results is explicitly excluded from the
research comparison. Tracked historical summaries and the original manifest remain unchanged.
An ignored `materialization_receipt.json` records verification and the actual source fingerprint.

The atlas's `source_mtime_ns` is a non-geometric timestamp. A byte-identical source copy can
have another local mtime. The wrapper normalizes only this temporary atlas field to the
historical manifest value for deterministic evidence bytes, records the actual before/after
source fingerprint separately in the receipt, and never changes the scene. Historical
provenance and producer/config/code identities remain intact.

The `--verify-only` command above verifies already materialized evidence without generation
or writes. For an independent report replay, the original validator uses the config's ignored
`blender/school_v3.blend` path; supply a matching local copy there and use the separate `/tmp`
output shown above. The single materialization command already performs full policy replay
and accepts an external scene without this extra copy.

### Fresh-clone test contract and research equivalence

Without raw evidence, the default pytest profile runs unit tests and committed
summary/config/hash assertions. Tests marked `external_physical_evidence` explicitly report
missing scene/artifact prerequisites and the materialization command, then skip. Unit tests
use small committed fixtures; tests never generate or download evidence. Missing CLI
prerequisites produce explicit errors listing the missing source/artifacts and materialization
command. Missing a local source does not mean the research validation failed.
`--require-physical-evidence` makes
missing prerequisites fail, either for the full suite or the focused bundle command above.
Run Ruff, mypy and `git diff --check` in either profile.
Historical school-v2 scene/private-calibration tests may separately skip when their own
external fixtures are absent. They are not current physical-policy prerequisites and are
not generated by physical-evidence materialization.

Regeneration must preserve architectural scale **APPROVED**, physical policy **APPROVED**,
48 supported floor subdomains, 58 approved components across 5/19 obstacles, 8 portal conflicts
**HUMAN_REVIEW**, Stair A/B **REVIEW**, overall **PARTIAL_APPROVED**, and collision diagnostic
**4 → 2**. Complete local islands remain 0 and `physical_complete=false`. Thresholds and
research conclusions remain fixed; retained probes do not become formal navigation candidates.
This checkpoint does not open Cases 1–3, Agent work or the Finalization Sprint.
