# Amidst

**Physically constrained blind-gap trajectory reconstruction in a synthetic Blender environment.**

**在 Blender 合成環境中，以物理限制進行跨攝影機盲區軌跡重建。**

[繁體中文](#繁體中文) | [English](#english)

> **研究狀態：**Phase 1 prototype，版本 `0.1.0`。M0–M8 與 fake-data 後半段閉環已實作並測試；本
> repository 不含正式監控資料、真實攝影機 Observation 或具權威性的 capture time。
>
> **Research status:** Phase 1 prototype, version `0.1.0`. M0–M8 and the fake-data downstream loop are implemented
> and tested. This repository does not contain production surveillance data,
> real-camera observations, or authoritative capture times.

## 繁體中文

### 專案定位

Amidst 是一個 Phase 1 研究原型：在已知 3D 場景、攝影機幾何與部分 2D
合成觀測下，以確定性的幾何、導航拓撲與時空限制，產生攝影機盲區期間物理
可行的 Top-K 3D 軌跡候選。

目前專案專注於研究管線與可驗證契約，不是正式監控產品。真實攝影機串流、
Detection／Tracking／ReID、正式資料庫與操作介面屬於後續 Phase 2；Agent 語意
排序是延後的 optional Phase 1 extension，完整 tool-calling Agent 才屬 Phase 2。

### 目前完成範圍

- **M0–M4 — 合成模擬基礎：**唯讀 Blender 場景與幾何稽核、研究副本隔離、
  synthetic Ground Truth exporter、29 台 `CAM_*` 校正與正向投影、FOV／遮擋判斷，
  以及不含 3D 真值的 2D Observation exporter。
- **M5 — 資料契約：**以嚴格 Pydantic models 定義 Observation、Projected Point、
  Candidate、Event、Reconstruction Result、Provenance 與 termination 邊界。
- **M6 — 2D-to-3D 反投影：**將單一校正 camera 綁定至明確 plane，採 Blender
  camera ray 與 ray-plane intersection，無效輸入 fail closed。
- **M7 — 導航與拓撲：**分離有方向的 Camera Topology 與 navigation graph，要求
  transition 明確引用連續的 navigation edges。
- **M8 — Top-K 候選搜尋：**在有界、明確設定的候選空間中，依距離、時間、速度
  與拓撲授權路徑，確定性列舉物理可行候選。

- **Fake-data 後半段閉環：**四組固定 seed fixtures，具時間參數的 blind-gap hypotheses、
  ADE／FDE／Top-K Coverage、AABB／速度／corridor metrics 與 Rerun debug recording。

尚未完成正式 school end-to-end dataset／benchmark、semantic ranking、Projection Error、
baseline／ablation，以及正式 Phase 2 實作。
School walkability、NavMesh、樓梯與跨樓層路徑也尚未核准；跨樓層預設維持
`DISCONNECTED`。

### 核心資料流

```text
Blender / synthetic configuration
  -> Ground Truth (simulation and evaluation only)
  -> Virtual-camera 2D OBSERVED / GAP evidence
  -> Explicit-plane inverse projection
  -> Camera topology + directed navigation
  -> Bounded Top-K physically feasible candidates
  -> Timed blind-gap hypotheses
  -> Separate Ground Truth evaluation + Rerun debug recording
```

Ground Truth 只供 simulation/export、evaluation 與 debug visualization，不能進入
反投影 inference、graph search、candidate ranking 或 path score。Graph Engine 只保證
候選在 configured bounded space 內符合已設定的硬限制，不會自行選出唯一真值。

### 快速開始

需求：Python `>=3.12` 與 [`uv`](https://docs.astral.sh/uv/)。

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
uv run pytest tests/unit
```

完整程式檢查：

```sh
uv run pytest
uv run ruff check .
uv run mypy
git diff --check
```

Blender-backed integration tests 需要 Blender CLI，可透過 `BLENDER_BIN` 指定：

```sh
export BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/blender
uv run pytest tests/integration
```

目前稽核環境使用 Blender 5.2.1 LTS。一般 GitHub clone 不含本機 `.blend`；缺少
Blender 或所需本機資產時，相關 integration tests 可能跳過。

### 資料與資產

- Git 追蹤 [`data/scene_audit/`](data/scene_audit/) 的唯讀場景／幾何稽核 bundle，
  以及 [`configs/trajectory_fixture.json`](configs/trajectory_fixture.json) 合成 fixture
  設定。兩者都不是 Observation、Ground Truth、影像或 benchmark dataset。
- 本機 `data/cameras/school_v2_cameras.json` 含 29 台研究用 `CAM_*`，標記為
  `SYNTHETIC`，並由 Git 忽略。
- `blender/school_v2.blend` 與研究副本都只存本機並由 Git 忽略；來源資產不得因
  export 或 audit 被儲存、覆寫或渲染。
- [`data/mock/`](data/mock/README.md) 追蹤四組合成 fixture、8 個 PROJECTED Observations、
  4 個獨立 GT trajectories（252 samples）與完整 config，不代表 Blender scene 已驗證。
- 本機 ignored 的 `data/candidates/fake_downstream_20261001/` 有四組 Event／metrics／Rerun
  recordings；沒有正式 school dataset 或專案產生的 Blender rendered images。
- 座標採 Blender 右手座標、Z 向上，且 1 Blender unit = 1 metre。只有 29 台
  `CAM_*` 可用於研究；imported SketchUp camera 因 lens 為非有限值而排除。

精確檔案、雜湊、筆數與目前 materialization 狀態請見
[`data/README.md`](data/README.md)。

### 專案結構

```text
src/amidst/domain/      嚴格資料契約與 interface
src/amidst/geometry/    明確平面反投影
src/amidst/navigation/  有方向 navigation 與 camera topology
src/amidst/graph/       有界 Top-K 時空 graph search
src/amidst/reconstruction/ 時間參數化 blind-gap hypotheses
src/amidst/evaluation/  真值評估與 physical metrics
src/amidst/visualization/ Rerun debug adapter
src/amidst/debug/       通用實驗 runner
src/amidst/simulation/  Blender／synthetic exporters 與 visibility
src/amidst/storage/     本機 JSON 邊界
scripts/                唯讀稽核與資料匯出入口
tests/                  unit 與 Blender-backed integration tests
docs/                   產品、設計、契約、決策與交接文件
```

### 文件導覽

- [Phase 2 Integration Foundation 架構與 mock API](docs/PHASE2_INTEGRATION.md)
- [Phase 2 Integration Validation 整合驗證與凍結](docs/PHASE2_INTEGRATION_VALIDATION.md)
- [Phase 1 research benchmark 研究實驗執行](docs/BENCHMARK.md)
- [研究範圍與需求](docs/PRD.md)
- [系統設計](docs/SYSTEM_DESIGN.md)
- [資料契約](docs/DATA_SCHEMA.md)
- [模組介面與 export 指令](docs/INTERFACES.md)
- [已確認決策與開放邊界](docs/ISSUES_AND_DECISIONS.md)
- [開發與文件維護規則](docs/DEVELOPMENT_RULES.md)
- [已完成工作紀錄](docs/WORK_LOG.md)
- [目前資料盤點](data/README.md)
- [最新開發交接](docs/CODEX_HANDOFF.md)

## English

### Project scope

Amidst is a Phase 1 research prototype. Given a known 3D scene, calibrated
cameras and partial synthetic 2D observations, it uses deterministic geometry,
navigation topology and spatiotemporal constraints to generate physically
feasible Top-K 3D trajectory candidates across camera blind gaps.

The project currently focuses on a testable research pipeline and strict
contracts, not a production monitoring product. Real camera ingestion,
detection/tracking/ReID, production storage and operator UI remain Phase 2.
Agent-based semantic ranking is a deferred optional Phase 1 extension; a full
tool-calling Agent belongs to Phase 2.

### Implemented scope

- **M0–M4 — Synthetic simulation foundation:** read-only Blender scene and
  geometry audits, isolated research copy, synthetic Ground Truth export,
  calibration and forward projection for 29 `CAM_*` cameras, FOV/occlusion, and
  a sanitized 2D Observation exporter with no hidden 3D truth.
- **M5 — Data contracts:** strict Pydantic models for Observation, Projected
  Point, Candidate, Event, Reconstruction Result, Provenance and termination
  boundaries.
- **M6 — 2D-to-3D inverse projection:** one calibrated camera bound to one
  explicit plane, using Blender camera rays and ray-plane intersection with
  fail-closed validation.
- **M7 — Navigation and topology:** separate directed Camera Topology and
  navigation graphs, with every transition citing continuous navigation edges.
- **M8 — Top-K candidate search:** deterministic enumeration using distance,
  time, speed and topology-authorized routes within an explicitly configured
  bounded candidate space.

- **Fake-data downstream loop:** four fixed-seed fixtures, timed blind-gap hypotheses,
  ADE/FDE/route Coverage, AABB/speed/corridor metrics and Rerun debug recordings.

Formal school end-to-end data/benchmark, semantic ranking, Projection Error,
baselines/ablations and production Phase 2 are not implemented. School walkability, NavMesh, stairs and cross-floor routes are
also unapproved; cross-floor movement remains `DISCONNECTED` by default.

### Core data flow

```text
Blender / synthetic configuration
  -> Ground Truth (simulation and evaluation only)
  -> Virtual-camera 2D OBSERVED / GAP evidence
  -> Explicit-plane inverse projection
  -> Camera topology + directed navigation
  -> Bounded Top-K physically feasible candidates
  -> Timed blind-gap hypotheses
  -> Separate Ground Truth evaluation + Rerun debug recording
```

Ground Truth is restricted to simulation/export, evaluation and debug
visualization. It never enters inverse-projection inference, graph search,
candidate ranking or path scoring. The Graph Engine proves feasibility only
within the configured bounded space; it does not select a single true path.

### Quick start

Requirements: Python `>=3.12` and [`uv`](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/Polalalabear/amidst.git
cd amidst
uv sync --frozen
uv run pytest tests/unit
```

Full code checks:

```sh
uv run pytest
uv run ruff check .
uv run mypy
git diff --check
```

Blender-backed integration tests require the Blender CLI. Set `BLENDER_BIN` when
needed:

```sh
export BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/blender
uv run pytest tests/integration
```

The current audited environment uses Blender 5.2.1 LTS. A normal GitHub clone
does not include local `.blend` assets; tests that require Blender or an absent
local asset may skip.

### Data and assets

- Git tracks the read-only scene/geometry audit bundle in
  [`data/scene_audit/`](data/scene_audit/) and the synthetic fixture configuration
  in [`configs/trajectory_fixture.json`](configs/trajectory_fixture.json).
  Neither is an Observation, Ground Truth, image or benchmark dataset.
- The local `data/cameras/school_v2_cameras.json` contains 29 research `CAM_*`
  cameras, is labelled `SYNTHETIC`, and is Git-ignored.
- `blender/school_v2.blend` and its research copy remain local and Git-ignored;
  export and audit operations must not save, overwrite or render the source.
- [`data/mock/`](data/mock/README.md) tracks four synthetic fixtures, eight PROJECTED
  observations, four separate GT trajectories (252 samples) and full config.
  These do not certify a Blender scene.
- Local ignored `data/candidates/fake_downstream_20261001/` contains four Event/metric/Rerun
  output sets. No formal school dataset or project-generated Blender rendered images exist.
- Coordinates use Blender's right-handed, Z-up world with one Blender unit per
  metre. Only the 29 `CAM_*` cameras are research-eligible; the imported SketchUp
  camera is excluded because its lens is non-finite.

See [`data/README.md`](data/README.md) for exact files, hashes, counts and current
materialization status.

### Project layout

```text
src/amidst/domain/      Strict data contracts and interfaces
src/amidst/geometry/    Explicit-plane inverse projection
src/amidst/navigation/  Directed navigation and camera topology
src/amidst/graph/       Bounded Top-K spatiotemporal graph search
src/amidst/reconstruction/ Timed blind-gap hypotheses
src/amidst/evaluation/  Truth evaluation and physical metrics
src/amidst/visualization/ Rerun debug adapter
src/amidst/debug/       Generic experiment runner
src/amidst/simulation/  Blender/synthetic exporters and visibility
src/amidst/storage/     Local JSON boundary
scripts/                Read-only audits and data-export entry points
tests/                  Unit and Blender-backed integration tests
docs/                   Product, design, contract, decision and handoff docs
```

### Documentation

- [Phase 2 Integration Foundation architecture and mock API](docs/PHASE2_INTEGRATION.md)
- [Phase 2 Integration Validation and freeze](docs/PHASE2_INTEGRATION_VALIDATION.md)
- [Phase 1 research benchmark](docs/BENCHMARK.md)
- [Research scope and requirements](docs/PRD.md)
- [System design](docs/SYSTEM_DESIGN.md)
- [Data contracts](docs/DATA_SCHEMA.md)
- [Module interfaces and export commands](docs/INTERFACES.md)
- [Accepted decisions and open boundaries](docs/ISSUES_AND_DECISIONS.md)
- [Development and documentation rules](docs/DEVELOPMENT_RULES.md)
- [Completed work log](docs/WORK_LOG.md)
- [Current data inventory](data/README.md)
- [Latest development handoff](docs/CODEX_HANDOFF.md)
