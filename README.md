# Amidst

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Amidst is an evaluation-first research project exploring how intelligent
surveillance, spatial context, trustworthy retrieval, and AI-assisted reasoning
can support a Digital Twin of a physical environment.

The project is currently in the **planning and specification** phase. This
repository contains the documents, evaluation boundaries, and repository rules
needed to establish a reliable foundation before application development
begins. It does not yet contain a runnable product.

### Quick Links

| Goal | Link |
| --- | --- |
| Understand the project | [Project Map](docs/00_Project_Map.md) |
| Review the proposed data contracts | [Data Types and Exchange Formats](docs/09_Data_Types_and_Exchange_Formats.md) |
| Follow the contributor workflow | [Internal Project Guide](docs/internal_guide.md) |
| Check public/private data boundaries | [Repository and Data Publication Policy](docs/08_Repository_and_Data_Publication_Policy.md) |

### The Problem

Surveillance systems are often assembled as disconnected parts: cameras,
detectors, trackers, databases, 3D models, and conversational interfaces. A
convincing demonstration can still produce an unreliable answer when identities,
timestamps, spatial references, evidence, or evaluation criteria do not line up.

Amidst studies how these parts can be connected without hiding uncertainty or
losing the path from a conclusion back to its supporting evidence.

### Conceptual System

The conceptual system is organized into six layers:

1. **Observation sources** — supply observations from the physical environment.
2. **Perception and temporal understanding** — detect entities and track them over time.
3. **Spatial and event understanding** — associate observations with locations and events.
4. **State and storage** — preserve versioned records and their provenance.
5. **Retrieval and reasoning** — retrieve evidence for the AI Agent to interpret.
6. **Application** — present results through the Digital Twin interface.

Cross-layer evaluation compares outputs with Ground Truth and reports metrics
and failure causes. This remains a planning model; implementation details are
defined in the [System Architecture](docs/02_System_Architecture.md).

### Research Questions

The project is intended to investigate questions such as:

- What happened in a particular zone and time window?
- Which cameras and tracks support an event?
- What happened immediately before or after an observation?
- Can a retrieved result be traced to evidence and its origin?
- Did an incorrect answer come from perception, tracking, spatial mapping,
  retrieval, or Agent interpretation?

These are research directions. Their exact MVP scope and acceptance thresholds
remain governed by the project specifications.

### Evaluation-First Approach

Amidst treats evaluation as part of the system design rather than a final demo
check. The planning baseline separates:

- dataset and Ground Truth design;
- reproducible baseline systems;
- layer-specific evaluation tools and metrics;
- end-to-end tests; and
- error analysis that attributes failures to the responsible layer.

Ground Truth remains independent from implementation output, and evidence
retrieval remains distinct from Agent interpretation.

### What This Repository Contains

- product, architecture, dataset, spatial, retrieval, and evaluation planning;
- shared terminology and cross-document open questions;
- technical-decision and publication-policy documentation;
- contributor guidance; and
- a standard-library validation script with GitHub Actions integration.

It currently does not contain application code, a deployable service, private
datasets, raw surveillance media, or sensitive site assets.

### How to Use This Repository

#### Explore the project

Start with the [Project Map](docs/00_Project_Map.md), then follow the document
that owns your topic:

| Interest | Start here |
| --- | --- |
| Product need, users, MVP, and scope | [Product Requirements](docs/01_PRD.md) |
| Components, boundaries, and information flow | [System Architecture](docs/02_System_Architecture.md) |
| Metrics, benchmarks, and failure attribution | [Evaluation Framework](docs/03_Evaluation_Framework.md) |
| Data, annotation, and Ground Truth | [Dataset Specification](docs/04_Dataset_Specification.md) |
| Cameras, zones, Blender assets, and spatial mapping | [Spatial Model Specification](docs/05_Spatial_Model_Specification.md) |
| Queries, evidence, provenance, and Agent boundaries | [Retrieval Specification](docs/06_Retrieval_Specification.md) |
| Blender, video, event, and exchange-format candidates | [Data Types and Exchange Formats](docs/09_Data_Types_and_Exchange_Formats.md) |

#### Review or extend the documentation

Read [AGENTS.md](AGENTS.md) before making a repository change. Contributors and
reviewers can use the [Internal Project Guide](docs/internal_guide.md) for
decision routing, information review, and the change workflow.

#### Run validation

From the repository root, run:

```bash
python3 -B scripts/check.py
```

The script uses only the Python standard library. It checks repository identity,
required documents and rule markers, non-empty Markdown files, and trailing
whitespace. There is no application startup command yet.

### Documentation Map

| Document | Purpose |
| --- | --- |
| [Project Map](docs/00_Project_Map.md) | Current entry point and topic-based navigation |
| [Product Requirements](docs/01_PRD.md) | Problem, users, MVP, scope, and success criteria |
| [System Architecture](docs/02_System_Architecture.md) | Components, boundaries, entities, and information flow |
| [Evaluation Framework](docs/03_Evaluation_Framework.md) | Correctness, metrics, benchmarks, and failure attribution |
| [Dataset Specification](docs/04_Dataset_Specification.md) | Data, annotation, Ground Truth, and benchmark planning |
| [Spatial Model Specification](docs/05_Spatial_Model_Specification.md) | Cameras, zones, assets, and spatial mapping |
| [Retrieval Specification](docs/06_Retrieval_Specification.md) | Queries, evidence, provenance, and result states |
| [Technical Decisions](docs/07_Technical_Decisions.md) | Technical decision records and trade-offs |
| [Repository and Data Publication Policy](docs/08_Repository_and_Data_Publication_Policy.md) | Public/private boundaries for files and data |
| [Data Types and Exchange Formats](docs/09_Data_Types_and_Exchange_Formats.md) | Proposed Blender, video, event, and provenance contracts |
| [Internal Project Guide](docs/internal_guide.md) | Contributor decision and review workflow |
| [Glossary](docs/glossary.md) | Shared terminology |
| [Open Questions](docs/open_questions.md) | Unresolved cross-document questions |

### Repository Structure

```text
amidst/
├── .github/
│   └── workflows/
│       └── check.yml
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
│   ├── 09_Data_Types_and_Exchange_Formats.md
│   ├── glossary.md
│   ├── internal_guide.md
│   └── open_questions.md
└── scripts/
    └── check.py
```

### Contributing

Before proposing a change, read [AGENTS.md](AGENTS.md) and the directly
relevant specifications. Keep changes focused, preserve unresolved decisions,
and run the repository check after every complete step. This repository is
still specification-led, so feature proposals should first identify the
requirement, affected contracts, evaluation evidence, and failure cases.

### Data and Asset Boundaries

This public repository is for source code, documentation, and explicitly
approved sanitized or synthetic artifacts. Raw surveillance data, identifiable
annotations, credentials, private storage links, sensitive real-site assets,
and unreviewed model or experiment artifacts must not be committed.

Before adding data, media, models, experiment outputs, or spatial assets, read
the authoritative
[Repository and Data Publication Policy](docs/08_Repository_and_Data_Publication_Policy.md).

---

<a id="繁體中文"></a>

## 繁體中文

Amidst 是一項以評估為核心的研究專案，探討如何整合智慧監控、空間脈絡、
可追溯的資料檢索與 AI 輔助推理，建立能反映實體場域的數位孿生。

專案目前仍在**規劃與規格制定**階段。這個儲存庫先整理開發前需要的規格、
評估界線與協作規則，讓後續實作能建立在可驗證的基礎上；目前尚未提供可
執行的應用程式。

### 快速連結

| 想做的事 | 前往 |
| --- | --- |
| 了解專案全貌 | [專案地圖](docs/00_Project_Map.md) |
| 查看資料格式建議 | [資料型別與交換格式](docs/09_Data_Types_and_Exchange_Formats.md) |
| 依循專案協作流程 | [內部專案導讀](docs/internal_guide.md) |
| 確認資料能否公開 | [儲存庫與資料發布政策](docs/08_Repository_and_Data_Publication_Policy.md) |

### 想解決的問題

監控系統往往由攝影機、偵測器、追蹤模組、資料庫、3D 模型與對話介面分別
組成。即使展示畫面看起來合理，只要身分、時間、空間位置、佐證資料或評估
標準沒有對齊，系統仍可能給出不可靠的答案。

Amidst 關注的是如何把這些環節連接起來，同時保留不確定性，並讓每項結論
都能回溯到支持它的證據與資料來源。

### 概念架構

系統依職責分成六層：

1. **資料來源**：提供實體場域的監控觀測。
2. **感知與時序**：辨識實體，並追蹤它們隨時間的變化。
3. **空間與事件**：將觀測連結到位置，理解相關事件。
4. **狀態儲存**：保存有版本的紀錄與資料來源。
5. **檢索與推理**：取得佐證資料，供 AI Agent 解讀。
6. **應用介面**：透過數位孿生介面呈現結果。

跨層評估會以真值比對輸出，整理指標與失敗原因。這仍是規劃中的概念架構，
實作細節以[系統架構文件](docs/02_System_Architecture.md)為準。

### 預期探討的研究問題

專案希望逐步釐清：

- 某個區域在指定時段內發生了什麼事？
- 哪些攝影機畫面與追蹤紀錄足以佐證一項事件？
- 某次觀測之前或之後緊接著發生了什麼？
- 檢索結果能否回溯到證據及其來源？
- 錯誤答案究竟來自感知、追蹤、空間映射、資料檢索，還是 Agent 的解讀？

以上是研究方向；實際 MVP 範圍與驗收門檻仍以專案規格為準。

### 以評估為核心

Amidst 不把評估留到展示前才進行，而是將它納入系統設計。現階段的規劃會
分開處理：

- 資料集與真值標註（Ground Truth）的設計；
- 可重現的基準系統；
- 各層的評估工具與指標；
- 端到端測試；以及
- 能將失敗原因歸到正確環節的錯誤分析。

真值標註不會由實作結果反向決定；檢索到的證據也會與 Agent 的解讀明確
區分。

### 儲存庫目前包含什麼

- 產品、架構、資料集、空間模型、資料檢索與評估規劃；
- 共用術語與跨文件的未決問題；
- 技術決策與資料發布政策文件；
- 貢獻者工作指引；以及
- 使用 Python 標準函式庫撰寫、並整合 GitHub Actions 的驗證腳本。

目前尚未包含應用程式碼、可部署服務、私人資料集、原始監控影像或敏感場域
資產。

### 如何使用這個儲存庫

#### 了解專案

建議先讀[專案地圖](docs/00_Project_Map.md)，再依關注主題前往對應文件：

| 想了解的內容 | 建議起點 |
| --- | --- |
| 產品需求、使用者、MVP 與範圍 | [產品需求文件](docs/01_PRD.md) |
| 元件、系統邊界與資訊流 | [系統架構](docs/02_System_Architecture.md) |
| 評估指標、基準測試與失敗歸因 | [評估框架](docs/03_Evaluation_Framework.md) |
| 資料、標註與真值標註 | [資料集規格](docs/04_Dataset_Specification.md) |
| 攝影機、區域、Blender 資產與空間映射 | [空間模型規格](docs/05_Spatial_Model_Specification.md) |
| 查詢、證據、資料來源與 Agent 邊界 | [資料檢索規格](docs/06_Retrieval_Specification.md) |
| Blender、影片、事件與交換格式候選方案 | [資料型別與交換格式](docs/09_Data_Types_and_Exchange_Formats.md) |

#### 閱讀或補充文件

修改儲存庫前，請先閱讀 [AGENTS.md](AGENTS.md)。貢獻者與審查者可參考
[內部專案導讀](docs/internal_guide.md)，了解決策如何分流、哪些資訊需要
審查，以及完整的變更流程。

#### 執行驗證

在儲存庫根目錄執行：

```bash
python3 -B scripts/check.py
```

腳本只使用 Python 標準函式庫，會確認儲存庫身分、必要文件與規則標記、
Markdown 文件是否有內容，以及是否出現行尾空白。目前還沒有應用程式啟動
指令。

### 文件索引

| 文件 | 用途 |
| --- | --- |
| [專案地圖](docs/00_Project_Map.md) | 專案入口與依主題分類的文件導覽 |
| [產品需求文件](docs/01_PRD.md) | 問題、使用者、MVP、範圍與成功條件 |
| [系統架構](docs/02_System_Architecture.md) | 元件、邊界、實體與資訊流 |
| [評估框架](docs/03_Evaluation_Framework.md) | 正確性、評估指標、基準測試與失敗歸因 |
| [資料集規格](docs/04_Dataset_Specification.md) | 資料、標註、真值標註與基準資料規劃 |
| [空間模型規格](docs/05_Spatial_Model_Specification.md) | 攝影機、區域、資產與空間映射 |
| [資料檢索規格](docs/06_Retrieval_Specification.md) | 查詢、證據、資料來源與結果狀態 |
| [技術決策](docs/07_Technical_Decisions.md) | 技術決策紀錄與取捨 |
| [儲存庫與資料發布政策](docs/08_Repository_and_Data_Publication_Policy.md) | 檔案與資料的公開／私人界線 |
| [資料型別與交換格式](docs/09_Data_Types_and_Exchange_Formats.md) | Blender、影片、事件與來源追溯的建議格式 |
| [內部專案導讀](docs/internal_guide.md) | 貢獻者的決策與審查流程 |
| [術語表](docs/glossary.md) | 全專案共用術語 |
| [未決問題](docs/open_questions.md) | 尚待確認的跨文件問題 |

### 檔案結構

```text
amidst/
├── .github/
│   └── workflows/
│       └── check.yml
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
│   ├── 09_Data_Types_and_Exchange_Formats.md
│   ├── glossary.md
│   ├── internal_guide.md
│   └── open_questions.md
└── scripts/
    └── check.py
```

### 參與專案

提出變更前，請先閱讀 [AGENTS.md](AGENTS.md) 與直接相關的規格。修改內容應
聚焦於已確認的需求，不要自行替未決事項定案，並在每個完整步驟後執行專案
驗證。現階段仍以規格為主；提出功能方向時，應先交代需求、受影響的資料
契約、評估證據與失敗情況。

### 資料與資產界線

這個公開儲存庫只收錄原始碼、文件，以及已明確核准的去識別化或合成素材。
原始監控資料、可識別個人的標註、帳密、私人儲存位置連結、敏感實際場域
資產，以及尚未審查的模型或實驗產物，都不得提交到此處。

加入資料、媒體、模型、實驗輸出或空間資產前，請先閱讀具約束力的
[儲存庫與資料發布政策](docs/08_Repository_and_Data_Publication_Policy.md)。
