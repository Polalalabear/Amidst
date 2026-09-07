# Amidst

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

Amidst is a `PROPOSED`, evaluation-first intelligent-surveillance Digital Twin
project with AI Agent capabilities. The project is currently in the **planning
and specification** phase: its MVP boundary, detailed architecture, dataset,
evaluation thresholds, and technology stack are not yet confirmed.

This repository currently contains planning worksheets, project policies, and a
lightweight validation script. It does not yet contain an application
implementation.

## Project Direction

The conceptual direction under review is:

```text
Physical Environment + Surveillance Observation
  -> Perception
  -> Tracking / Temporal
  -> Spatial Mapping
  -> Event Understanding
  -> World State / Storage
  -> Retrieval
  -> Agent / Reasoning
  -> Application / Digital Twin UI
```

This is a planning model, not a confirmed MVP architecture. The project aims to
evaluate relevant layers independently so failures can be diagnosed rather than
judged only from a final answer or interface.

## Current Status

- Phase: planning and specification (`CONFIRMED`).
- Implementation readiness: not ready; important decisions remain `OPEN`.
- Default responsible person: Peter, unless another human owner is explicitly
  assigned.
- Current milestone: review and confirm the planning baseline.
- Application code, finalized schemas, and approved dataset contents: not yet
  established in this repository.

See the [Project Map](docs/00_Project_Map.md) for the current milestone,
blockers, confirmed decisions, proposals, and documentation navigation.

## Documentation

Start with [docs/00_Project_Map.md](docs/00_Project_Map.md). It maps task types
to the documents that own each concern.

### Core Specifications

| Document | Responsibility |
| --- | --- |
| [Product Requirements](docs/01_PRD.md) | Problem, users, MVP, scope, and success criteria |
| [System Architecture](docs/02_System_Architecture.md) | Components, boundaries, entities, and information flow |
| [Evaluation Framework](docs/03_Evaluation_Framework.md) | Correctness, metrics, benchmarks, and failure attribution |
| [Dataset Specification](docs/04_Dataset_Specification.md) | Data, annotation, Ground Truth, and benchmark-data planning |
| [Spatial Model Specification](docs/05_Spatial_Model_Specification.md) | Blender resources, cameras, zones, and spatial mapping |
| [Retrieval Specification](docs/06_Retrieval_Specification.md) | Queries, evidence, provenance, result states, and Agent boundary |
| [Technical Decisions](docs/07_Technical_Decisions.md) | ADR templates, trade-offs, and revisit conditions |

### Policy and Supporting Documents

| Document | Responsibility |
| --- | --- |
| [Repository and Data Publication Policy](docs/08_Repository_and_Data_Publication_Policy.md) | Public/private classification and publication controls |
| [Glossary](docs/glossary.md) | Shared terminology and conceptual distinctions |
| [Open Questions](docs/open_questions.md) | Cross-document decisions requiring human confirmation |

## Decision Status

Planning documents use these statuses:

- `CONFIRMED`: explicitly approved or verified.
- `PROPOSED`: a direction awaiting confirmation.
- `OPEN`: a decision is still required.
- `DEFERRED`: intentionally postponed.
- `REJECTED`: explicitly rejected with recorded rationale.

Do not treat a template, example, or TODO as a confirmed project decision.

## Working in This Repository

Before changing the project:

1. Read [AGENTS.md](AGENTS.md).
2. Use the Project Map to identify and read the directly relevant documents.
3. State the requirement, impact scope, short plan, acceptance criteria, and
   failure cases.
4. Work on a new branch rather than modifying `main` directly.
5. Make the smallest viable change and avoid unrelated rewrites.
6. After every complete step, run the repository validation command.

Documentation is the source of truth for future implementation. Human
confirmation is required before an `OPEN` or `PROPOSED` product, architecture,
evaluation, dataset, privacy, or technology decision becomes `CONFIRMED`.

## Validation

Run from the repository root:

```bash
python3 -B scripts/check.py
```

The script uses only the Python standard library. It checks the repository
location, required documentation, required project-rule markers, non-empty
Markdown files, and trailing whitespace.

## Repository and Data Safety

Files must be classified before they are added to Git:

- `PUBLIC_ALLOWED`
- `PRIVATE_ONLY`
- `REVIEW_REQUIRED`

When uncertain, use `REVIEW_REQUIRED` and do not publish automatically. Raw
surveillance media, identifiable records, sensitive real-site assets, secrets,
private infrastructure details, full private datasets, raw experiment outputs,
and unreviewed model artifacts do not belong in the public repository.

Read the authoritative
[Repository and Data Publication Policy](docs/08_Repository_and_Data_Publication_Policy.md)
before adding data, media, model artifacts, experiment outputs, or spatial
assets.

## Repository Layout

```text
amidst/
├── AGENTS.md
├── README.md
├── docs/
│   ├── 00_Project_Map.md
│   ├── 01_PRD.md
│   ├── 02_System_Architecture.md
│   ├── 03_Evaluation_Framework.md
│   ├── 04_Dataset_Specification.md
│   ├── 05_Spatial_Model_Specification.md
│   ├── 06_Retrieval_Specification.md
│   ├── 07_Technical_Decisions.md
│   ├── 08_Repository_and_Data_Publication_Policy.md
│   ├── glossary.md
│   └── open_questions.md
└── scripts/
    └── check.py
```

No private dataset or environment asset is included in this public project
structure.

## Next Human Review

The smallest set of decisions currently blocking implementation is:

1. What the first prototype must prove.
2. Which layers and entities belong to the MVP.
3. What usable data and Blender metadata already exist.
4. Which evaluation protocol and thresholds define success.
5. Which Retrieval evidence contract and Agent boundary are required.

Track cross-cutting decisions in
[docs/open_questions.md](docs/open_questions.md).

## 繁體中文

Amidst 是一個處於 `PROPOSED` 狀態、以評估優先為原則的智慧監控數位孿生
專案，規劃納入 AI Agent 能力。目前專案仍在**規劃與規格制定**階段；MVP
邊界、詳細架構、資料集、評估門檻與技術棧都尚未確認。

目前 repository 只包含規劃工作表、專案政策與輕量驗證腳本，尚未包含應用
程式實作。

### 專案方向

目前供審查的概念流程為：

```text
實體環境 + 監控觀測
  -> 感知
  -> 追蹤／時間層
  -> 空間映射
  -> 事件理解
  -> 統一世界狀態／儲存
  -> 檢索
  -> Agent／推理
  -> 應用程式／數位孿生 UI
```

這是規劃模型，不是已確認的 MVP 架構。專案目標是讓相關層能被獨立評估，
以便定位失敗原因，而不是只從最終回答或介面判斷整體結果。

### 目前狀態

- 階段：規劃與規格制定（`CONFIRMED`）。
- 實作準備度：尚未就緒；重要決策仍為 `OPEN`。
- 預設負責人：Peter；若明確指定其他人，則以該指定為準。
- 目前里程碑：審查並確認規劃基準。
- 應用程式碼、最終 schema 與核准資料集內容：尚未在此 repository 建立。

請參閱[專案地圖](docs/00_Project_Map.md)，了解目前里程碑、阻塞事項、已確認
決策、提案與文件導覽。

### 文件導覽

請從 [docs/00_Project_Map.md](docs/00_Project_Map.md) 開始；該文件會依任務類型
導向負責該議題的文件。

#### 核心規格

| 文件 | 責任範圍 |
| --- | --- |
| [產品需求](docs/01_PRD.md) | 問題、使用者、MVP、範圍與成功條件 |
| [系統架構](docs/02_System_Architecture.md) | 元件、邊界、實體與資訊流 |
| [評估框架](docs/03_Evaluation_Framework.md) | 正確性、指標、benchmark 與失敗歸因 |
| [資料集規格](docs/04_Dataset_Specification.md) | 資料、標註、Ground Truth 與 benchmark 資料規劃 |
| [空間模型規格](docs/05_Spatial_Model_Specification.md) | Blender 資源、攝影機、區域與空間映射 |
| [檢索規格](docs/06_Retrieval_Specification.md) | 查詢、證據、來源追蹤、結果狀態與 Agent 邊界 |
| [技術決策](docs/07_Technical_Decisions.md) | ADR 模板、取捨與重新檢視條件 |

#### 政策與支援文件

| 文件 | 責任範圍 |
| --- | --- |
| [Repository 與資料發布政策](docs/08_Repository_and_Data_Publication_Policy.md) | 公開／私人分類與發布控制 |
| [術語表](docs/glossary.md) | 共用術語與概念區分 |
| [未決問題](docs/open_questions.md) | 需要人工確認的跨文件決策 |

### 決策狀態

規劃文件使用以下狀態：

- `CONFIRMED`：已明確核准或驗證。
- `PROPOSED`：等待確認的方向。
- `OPEN`：仍需要決策。
- `DEFERRED`：刻意延後處理。
- `REJECTED`：已明確否決並記錄理由。

不得把模板、範例或 TODO 視為已確認的專案決策。

### 在此 Repository 工作

修改專案前：

1. 閱讀 [AGENTS.md](AGENTS.md)。
2. 使用 Project Map 找出並閱讀與任務直接相關的文件。
3. 說明需求、影響範圍、簡短計畫、驗收條件與失敗情況。
4. 建立新分支，不直接修改 `main`。
5. 進行最小可行變更，避免不相關的重寫。
6. 每個完整步驟後執行 repository 驗證命令。

文件是未來實作的 source of truth。任何 `OPEN` 或 `PROPOSED` 的產品、架構、
評估、資料集、隱私或技術決策，均須經人工確認後才能成為 `CONFIRMED`。

### 驗證

在 repository 根目錄執行：

```bash
python3 -B scripts/check.py
```

此腳本只使用 Python 標準函式庫，會檢查 repository 位置、必要文件、專案規則
標記、空白 Markdown 檔案與行尾空白。

### Repository 與資料安全

檔案加入 Git 前必須分類為：

- `PUBLIC_ALLOWED`
- `PRIVATE_ONLY`
- `REVIEW_REQUIRED`

若無法確定，使用 `REVIEW_REQUIRED`，且不得自動發布。原始監控媒體、可識別
紀錄、敏感真實場域資產、secrets、私人基礎設施資訊、完整私人資料集、原始
實驗輸出與未審查模型資產都不應進入公開 repository。

加入資料、媒體、模型資產、實驗輸出或空間資產前，必須閱讀權威的
[Repository 與資料發布政策](docs/08_Repository_and_Data_Publication_Policy.md)。

### Repository 結構

```text
amidst/
├── AGENTS.md
├── README.md
├── docs/
│   ├── 00_Project_Map.md
│   ├── 01_PRD.md
│   ├── 02_System_Architecture.md
│   ├── 03_Evaluation_Framework.md
│   ├── 04_Dataset_Specification.md
│   ├── 05_Spatial_Model_Specification.md
│   ├── 06_Retrieval_Specification.md
│   ├── 07_Technical_Decisions.md
│   ├── 08_Repository_and_Data_Publication_Policy.md
│   ├── glossary.md
│   └── open_questions.md
└── scripts/
    └── check.py
```

此公開專案結構中不包含私人資料集或環境資產。

### 下一步人工審查

目前阻塞實作的最小決策集合為：

1. 第一個 prototype 必須證明什麼。
2. 哪些層與實體屬於 MVP。
3. 目前有哪些可用資料與 Blender metadata。
4. 哪一套評估協議與門檻定義成功。
5. 需要什麼 Retrieval 證據契約與 Agent 邊界。

跨文件決策統一記錄於
[docs/open_questions.md](docs/open_questions.md)。
