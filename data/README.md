# Current data inventory / 目前資料盤點

[English](#english) | [繁體中文](#繁體中文)

Snapshot date: **2026-10-01**. This file records which artifacts are currently
materialized. The authoritative data contracts remain in
[`docs/DATA_SCHEMA.md`](../docs/DATA_SCHEMA.md).

## English

### Git-tracked audit evidence

`data/scene_audit/` is a read-only inspection bundle, not an Observation,
Ground Truth, image, or benchmark dataset.

| Artifact | Bytes | SHA-256 | Current meaning |
| --- | ---: | --- | --- |
| [`scene_audit/README.md`](scene_audit/README.md) | 8,251 | `3600dd132dc589ed7f74fb3d3e26d7c0d887de40f283e63603c0f616df179fb6` | Human-readable scene inventory and limitations |
| [`scene_audit/GEOMETRY.md`](scene_audit/GEOMETRY.md) | 3,268 | `aa6613944091f874f933de3adbfbbe613c260dbb0e53da6edb7b32af3803f173` | Human-readable geometry follow-up |
| `scene_audit/school_v2_scene_audit.json` | 6,750,115 | `18bf77255ea36868d8dbcc2d71a0a03a76541c46173464fd0d5c5d1d5de709a2` | Schema `1.0.0` read-only scene audit generated at `2026-10-01T12:07:31.071695Z` |
| `scene_audit/school_v2_geometry_audit.json` | 196,194 | `8c5e3fcb1024e60746d7378e961916e43841d8258bfd36246db4dbae7a5a406b` | Schema `1.0.0` geometry diagnostic |
| `scene_audit/school_v2_research_copy.json` | 1,434 | `bfd85de690542774c8becb9d87f512c41e7efaa5c914de71dffefb08386d519b` | Source/copy provenance; no save or render |

The scene audit reports 2,796 objects, including 2,652 Mesh objects and 30
cameras. Twenty-nine `CAM_*` cameras are eligible for research; the imported
SketchUp camera has a non-finite lens and is excluded. The geometry diagnostic
covers 370 structural Mesh objects, 25,098 evaluated triangles, 30 AREA evidence
regions and two stair regions. It does **not** approve navigation geometry or a
school cross-floor route.

### Local generated artifact, not published by Git

`data/cameras/school_v2_cameras.json` exists locally and is excluded by
`.gitignore`.

| Property | Inspected value |
| --- | --- |
| File size / SHA-256 | 28,446 bytes / `79a7d44276cbd05c8019534475e96f745e3e7903c0fe83829e3e1c23700d5816` |
| Data label | `SYNTHETIC` |
| Source binding | `school_v2_research.blend`, SHA-256 `1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38` |
| Cameras | 29 unique `CAM_*`: 17 on 1F and 12 on 2F |
| Calibration | All 1920×1080; `BLENDER_NEG_Z_UP_Y`; `TOP_LEFT_CONTINUOUS`; clip `0.1–1000` |
| Missing domains | No timestamp, target, Observation, Ground Truth, image, candidate, or metric records |

This catalog is scene-derived synthetic calibration metadata. It is not a
FORMAL observation source, a captured-image dataset, or evidence of real capture
time. A normal GitHub push does not include it.

### Tracked fixture configuration

[`configs/trajectory_fixture.json`](../configs/trajectory_fixture.json) is an
input configuration, not a materialized dataset or approved school route. It
is 608 bytes with SHA-256
`e986cdf0b98353c17d54f2b89b3e463e6a02cef0018bedaff61ed9f29b2cb0e4`, and
defines one `SYNTHETIC_TEST_FIXTURE` target, three keyframes at 0, 2 and 4
seconds, a 10 Hz sample rate and random seed 42. Running the current sampler
would deterministically yield 41 samples from 0.0 through 4.0 seconds inclusive;
the materialized Ground Truth record count remains zero.

### Currently absent

There are currently no materialized files in `data/ground_truth/`,
`data/observations/`, `data/candidates/` or `data/metrics/`, and no `.rrd` or
rendered-image dataset. Therefore there is no current Observation/target record
count, capture-time coverage, reconstruction result, or benchmark metric to
report.

The source `blender/school_v2.blend` and local research copy are both Git-ignored,
466,332,340 bytes, and byte-identical at the source SHA-256 above. The approved
Phase 1 convention is one Blender unit per metre; the older automatic audit's
unit-review finding remains historical inventory context. School walkability,
NavMesh and stair connectivity remain unapproved.

### Local inspection commands

```sh
git ls-files data
git status --ignored --short data
jq '{data_kind, camera_count, source_asset_sha256}' data/cameras/school_v2_cameras.json
jq '{schema_version, audit_kind, generated_at_utc, counts}' data/scene_audit/school_v2_scene_audit.json
```

## 繁體中文

### Git 已追蹤的稽核證據

`data/scene_audit/` 是唯讀場景檢查 bundle，不是 Observation、Ground Truth、
影像或 benchmark dataset。它包含：

- 場景盤點摘要與 JSON：2,796 個 objects、2,652 個 Mesh、30 台 cameras；研究範圍只取 29 台 `CAM_*`。
- 幾何補充摘要與 JSON：370 個結構 Mesh、25,098 個 evaluated triangles、30 個 AREA evidence regions、兩個 stair regions。
- 研究副本 provenance：來源與副本初始 byte-identical，沒有 save 或 render。

上述五個檔案的大小與 SHA-256 列於英文表格。這些 audit 證據不核准 school
walkability、NavMesh 或跨樓層樓梯路徑。

### 本機生成、Git 不發布的資料

`data/cameras/school_v2_cameras.json` 存在於本機，但由 `.gitignore` 排除：

- 28,446 bytes；SHA-256：`79a7d44276cbd05c8019534475e96f745e3e7903c0fe83829e3e1c23700d5816`。
- `data_kind=SYNTHETIC`，綁定 `school_v2_research.blend` 與來源 SHA-256 `1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38`。
- 29 個唯一 `CAM_*`：1F 17 台、2F 12 台；全部 1920×1080，使用 `BLENDER_NEG_Z_UP_Y` 與 `TOP_LEFT_CONTINUOUS`，clip 為 `0.1–1000`。
- 不含 timestamp、target、Observation、Ground Truth、影像、candidate 或 metric records。

這是由場景唯讀抽取的合成校正 metadata，不是 FORMAL Observation source、
實拍影像 dataset 或真實 capture-time 證據。一般 GitHub push 不會包含此檔。

### 已追蹤的 fixture 設定

[`configs/trajectory_fixture.json`](../configs/trajectory_fixture.json) 是輸入設定，
不是已物化 dataset 或核准的 school route。它為 608 bytes，SHA-256 是
`e986cdf0b98353c17d54f2b89b3e463e6a02cef0018bedaff61ed9f29b2cb0e4`，並描述一個
`SYNTHETIC_TEST_FIXTURE` target、0／2／4 秒三個 keyframes、10 Hz 與 seed 42；
目前 sampler 若執行，會從 0.0 到 4.0 秒（含端點）確定性產生 41 筆 samples，
但目前實際物化的 Ground Truth records 仍為零。

### 目前不存在的資料

目前沒有 `data/ground_truth/`、`data/observations/`、`data/candidates/`、
`data/metrics/`、`.rrd` 或 rendered-image dataset。因此沒有可報告的
Observation／target record count、capture-time coverage、reconstruction result
或 benchmark metrics。

來源 `blender/school_v2.blend` 與本機研究副本都由 Git 忽略，大小皆為
466,332,340 bytes，且來源 SHA-256 相同。Phase 1 已核准的 convention 是
1 Blender unit = 1 metre；舊自動 audit 的 unit review finding 保留為歷史盤點
脈絡。School walkability、NavMesh 與 stair connectivity 仍未核准。
