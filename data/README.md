# Current data inventory / 目前資料盤點

[English](#english) | [繁體中文](#繁體中文)

Snapshot date: **2026-10-01**. This file records which artifacts are currently
materialized. The authoritative data contracts remain in
[`docs/DATA_SCHEMA.md`](../docs/DATA_SCHEMA.md).

### 2026-10-05 addendum / Checkpoint 後 WALL 標記與單一 PILOT

- [Fresh candidate report](scene_audit/phase1_wall_candidates_20261005.md) / JSON:
  **81 automatic WALL surface patches / 1,491 HUMAN_REVIEW patches** from unchanged
  school_v3 geometry, with source/floor/bounds/AREA/WALKABLE/PORTAL/reason evidence.
- [Saved marking report](scene_audit/phase1_wall_markings_20261005.md) / JSON binds
  81 annotation-only WALL meshes copying 543 existing polygons in the isolated ignored
  `blender/working/phase1_wall_pilot_20261005/school_v3_wall_marked.blend`. Independent
  reopening preserves 2,873 original objects and physical mesh identity. All 28 portals
  have zero actual face intersections; no doorway infill or movement collider is added.
- One new ignored `data/pilot/phase1_wall_pilot_20261005/office/` run is labeled
  **PILOT / SYNTHETIC SAMPLE**: 10s, 5 FPS, 50/50 timestamps and 100/100 camera PNGs,
  existing AUDITORIUM_FRONT/REAR poses, 160 configured / 156.800049 sampled native units.
  Dataset JSON, separate GT/2D observations, sample report, validation, five montages,
  trajectory map, synchronized GIF and gallery are materialized locally.
- Validation: PASS_WITH_REVIEW, zero errors; 26 visible / 74 occluded / 0 out-of-FOV
  camera records; 24 global point GAP timestamps, 19 fully hidden / 5 partial body.
  Visible→GAP→visible recovery succeeds; forward/inverse maxima 0.000314545px /
  0.001615262 native units, no unexpected Projection failure. Source lineage verifies
  both the actual derived asset and unchanged original hash/size/mtime.

GT 僅 simulation/export/evaluation/debug，純2D Observation另存；81個WALL annotations
不進 physical render／raycaster。Formal geometry／scale／camera-plane authority仍待核准。
原始scene與checkpoint保留，沒有Case1–3、elevator transition、benchmark semantics改動、
merge或push；先停在此pilot等使用者檢查，不擴充完整dataset。Raw `.blend`／GT／renders
維持gitignored，本次Git僅保存recipes、tests與source-bound audit/report證據。

### 2026-10-05 addendum / 三個不同區域的 PILOT

Local ignored `data/pilot/school_v3_multisite_20261005/` contains three new
**PILOT / SYNTHETIC SAMPLE** runs in the same school_v3 asset, not separate buildings.
Each run has 10 seconds at 5 FPS, 50 timestamps on [0,10), 100 camera PNGs, source-bound
trajectory/support evidence, separate 2D observations and GT, evaluation-only dataset JSON,
five representative montages, synchronized preview, sample report and independent validation.

| Locale | Configured / sampled scene units | Visible / occluded / out-of-FOV camera records | Global landmark GAP | Judgment |
| --- | ---: | --- | ---: | --- |
| CLASS101 classroom | 300 / 294.000000 | 50 / 0 / 50 | 0 | Center-point visibility control; all 50 visible images have marker boundary clipping |
| Auditorium | 660 / 646.800049 | 82 / 2 / 16 | 1 | Coverage / short-gap sample; partial body remains at its sole GAP timestamp |
| Office | 160 / 156.800049 | 26 / 74 / 0 | 24 | Strongest point-occlusion pilot; 19 GAP timestamps have no marker pixels in either view |

教室使用 `CAM_1F_CLASS101` / `CAM_1F_CORRIDOR_04`；後者全程 FAR_CLIPPED。
禮堂與辦公區共用既有 `CAM_1F_AUDITORIUM_FRONT` / `CAM_1F_AUDITORIUM_REAR`，
不代表三套獨立相機配置。辦公區 GAP 為 frames21–44（t4.2–8.8），其中 frames23–41
（t4.6–8.2）的19個樣本完全沒有 marker；另外5個仍有部分 body pixels。
畫面使用 opaque gray Workbench 與橙色 marker，地板有不規則明暗塊；原因未認證。
可用於 point simulation 品質檢查，尚不足作為完整人體 CV 或正式完整 dataset。

All 150 timestamps / 300 PNGs pass independent source/site/provenance/render validation
with zero errors. Maximum native forward residual is 0.000638311 pixels; static diagnostic
plane inverse residual is 0.001787566 scene units, with no unexpected Projection failures.
`comparison.json` / `comparison.md` / `review.html` include agent image judgments bound to
dataset and reviewed-artifact hashes. The original corridor pilot is retained as a fourth
comparison reference, not counted as a new run. GT stays evaluation-only; no benchmark,
downstream inference or source save is performed. Full generation remains pending image
policy, physical scale and formal authority. Work stops at these three additional pilots.

### 2026-10-05 addendum / WALL 與小型 PILOT

- [WALL report](scene_audit/school_v3_wall_candidates.md) and
  [source-bound sidecar](scene_audit/school_v3_wall_candidates.json) contain **81 automatic
  WALL surface patches / 1,491 HUMAN_REVIEW patches**. No whole objects or source labels
  are rewritten; 28 protected PORTALs have zero automatic face/aperture intersections.
- Local ignored `data/pilot/school_v3_pilot_20261005/` contains **PILOT / SYNTHETIC SAMPLE**:
  50 timestamps, 100 PNG camera renders, combined evaluation-only `dataset.json`, separate
  `ground_truth.json` and sanitized `observations.json`, `sample_report.md`, `review.html`,
  five representative montages, trajectory map and synchronized GIF preview.
- Cameras: `CAM_1F_CORRIDOR_02` and `CAM_1F_CORRIDOR_03`. Planned route 106 native scene
  units over 10s; [0,10) at 5 FPS materializes 103.880005 units from t=0 through 9.8.
  Camera records: 21 visible / 79 occluded / zero out-of-FOV. Selected-camera landmark
  GAP: 29 timestamps; 14 have no marker pixels in either render, 15 retain partial body.
- All 50 timestamps / 100 renders, PNG labels/hashes and unchanged source identity pass
  independent validation. Maximum forward residual 0.000114px and diagnostic inverse
  residual 0.000248 scene units do not certify a formal school floor/camera-plane binding.

原始 `school_v3.blend` SHA-256、size、mtime 不變。GT 僅 simulation/export/evaluation，
不進 Projection inference／Graph／ranking／reconstruction；未跑正式 Cases 1–3，也不改
benchmark semantics。所有 raw PNG 的 text metadata 與 review 圖／JSON／reports 明列
PILOT／SYNTHETIC。使用者已確認沒有 elevator，歷史 AREA 命名不產生 transition。
METRIC／1m-per-unit 與建築尺寸有疑義；實際 floor Z≈20.07885 與 annotation Z=25 不一致。
完整 generation 仍待 image quality review、尺度與正式 authority；本輪停止於小型 pilot。
本機 pilot 含 GT 與生成影像，由 `.gitignore` 排除，不會隨一般 Git push 發布。

### 2026-10-02 addendum / 補充盤點

- [`scene_audit/semantic_validation.json`](scene_audit/semantic_validation.json) and
  [Markdown review queue](scene_audit/semantic_validation.md) are repeatable read-only
  diagnostics of the original source. They retain 30 AREA, 28 PORTAL and 29 CAM objects,
  zero WALKABLE/WALL/OBSTACLE/STAIR, and unresolved floor authority. The source SHA-256,
  size and mtime remain unchanged. These diagnostics do not establish physical authority.
- [`reports/benchmark/benchmark_summary.md`](reports/benchmark/benchmark_summary.md)
  and [JSON](reports/benchmark/benchmark_summary.json) compare the four persisted outputs
  in local ignored `data/candidates/infrastructure_20261002_final/`, with 11 separate
  **SYNTHETIC REGRESSION** charts. Missing metrics are recorded as unavailable.
- [`reports/benchmark/mock_comparison/benchmark_summary.md`](reports/benchmark/mock_comparison/benchmark_summary.md)
  and JSON/17 PNGs validate all supported chart families using the checked-in plotting-only
  fixture `tests/fixtures/benchmark_report_comparison.json`. The label is **MOCK VALIDATION**;
  numeric fixture values are not executions of baseline A–C or school benchmark results.

本輪新增的 semantic report 是來源不變的唯讀診斷與 human review queue，未建立正式
physical topology。11 張既有 fake-output 圖與 17 張 plotting fixture 圖分別明列
`SYNTHETIC REGRESSION`／`MOCK VALIDATION`；沒有 Blender Cases 1–3、正式 Case 4、
rendered images 或 Agent Ranking 結果。正式 protocol 的研究設定仍需核准。

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
no Ground Truth for that factory configuration is currently saved.

### Curated deterministic mock dataset and local downstream outputs

[`mock/`](mock/README.md) is Git-tracked synthetic test data with fixed seed 20261001.
It stores four strict inference inputs, eight PROJECTED endpoint Observations and
four separate CONFIGURATION_SAMPLER GT trajectories: Single Path 21 samples,
Branching Top-K 41, Temporal Slack 181, Simplified Stair 9 (252 total).
The manifest and synthetic-wall constraint config define the regression settings.
This is not Blender-derived data, an approved school route or a formal benchmark.

Local ignored `data/candidates/fake_downstream_20261001/` contains four saved candidate,
Event, metrics, run-config and debug.rrd sets plus summary.json. The runs retain 7
routes and 11 timed hypotheses in total; all terminate COMPLETE. minADE@K is zero
within floating-point tolerance, minFDE@K=0 and synthetic Coverage@K=true in all four.
Collision/constraint rates are zero against the provided AABB/directed graph/speed
contracts; they are not school mesh results. All four RRD recordings were reopened
with the SDK and verified readable. JSON is reproducible; RRD SDK metadata can vary.

`data/ground_truth/`, `data/observations/` and `data/metrics/` still have no formal
school dataset. No rendered-image dataset or authoritative capture times are present.

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
此 factory 設定目前沒有另行保存的 Ground Truth。

### 已物化 mock dataset 與本機後半段輸出

[`mock/`](mock/README.md) 追蹤四組 seed 20261001 的合成測試資料、8 個 PROJECTED
endpoint Observations、4 個另存的 CONFIGURATION_SAMPLER GT trajectories：
Single Path 21 samples、Branching Top-K 41、Temporal Slack 181、Simplified Stair 9，
共252筆。Manifest 與 synthetic wall constraint config 明確保存 regression 設定；
這不是 Blender-derived／正式 school dataset 或核准路徑。

本機 ignored `data/candidates/fake_downstream_20261001/` 含四組 candidates／Event／metrics／
完整 run config／debug.rrd 與 summary.json，共7 routes、11 timed hypotheses，全部 COMPLETE。
四組 minADE@K 在浮點誤差內為0、minFDE@K=0、synthetic Coverage@K=true；顯式 AABB／
directed graph／speed contracts 的 collision／constraint rates=0，不等於 school Mesh 結果。
四份 RRD 皆已用 SDK 重開確認可讀；JSON 可重現，RRD metadata 不保證 byte-identical。

仍沒有正式 school Ground Truth／Observation／metrics、rendered-image dataset，
也沒有真實 capture-time authority。

來源 `blender/school_v2.blend` 與本機研究副本都由 Git 忽略，大小皆為
466,332,340 bytes，且來源 SHA-256 相同。Phase 1 已核准的 convention 是
1 Blender unit = 1 metre；舊自動 audit 的 unit review finding 保留為歷史盤點
脈絡。School walkability、NavMesh 與 stair connectivity 仍未核准。
