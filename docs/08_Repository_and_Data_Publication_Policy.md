# Repository and Data Publication Policy

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `CONFIRMED`

### Purpose and Authority

Amidst is intended to be open source while research continues with private
assets. The public GitHub repository contains the reproducible project, but it
must not become storage for raw surveillance data, sensitive physical-site
information, secrets, or large internal research artifacts.

This document is the single source of truth for classifying files before they
are added to Git or intentionally published. A file is not safe merely because
it already exists inside the working directory.

### Required Classifications

| Classification | Meaning | Required action |
| --- | --- | --- |
| `PUBLIC_ALLOWED` | Generally suitable for the public repository after normal content checks | May be added when the applicable checks pass |
| `PRIVATE_ONLY` | Must remain outside the public repository | Do not add or publish; use approved private storage |
| `REVIEW_REQUIRED` | Safety depends on content, rights, sensitivity, or intent | Do not add or publish until a human explicitly approves it |

When uncertain, use `REVIEW_REQUIRED`.

Classification is semantic: extensions and directory names are signals, not
proof that an artifact is safe.

### `PUBLIC_ALLOWED`

#### Source Code

Source and test directories such as `src/`, `scripts/`, `tests/`, and `tools/`
are generally public when they contain no embedded credentials, private
infrastructure details, private data, or sensitive records.

Potentially allowed examples:

- Python, TypeScript, JavaScript, frontend, and backend source;
- evaluation, inference, and data-processing code;
- tests and utility scripts.

#### Documentation

Documentation may be public when it describes architecture, evaluation
methodology, dataset/annotation formats, APIs, schemas, algorithms, decisions,
workflow, or reproducibility without exposing:

- credentials or private URLs;
- internal infrastructure;
- identifiable surveillance information or personal data;
- sensitive real-site layouts or security details;
- private Google Drive links.

#### Schemas

Schema files may be public when they describe structure rather than contain real
sensitive records. Examples include camera, zone, event, retrieval, and
annotation JSON schemas.

#### Configuration Templates

Example configurations such as `.env.example`, `config.example.yaml`, or
`docker-compose.example.yml` may contain placeholders only. Never copy a real
secret or private connection string into a template.

#### Sanitized Sample Data

Small data under `examples/`, `sample_data/`, `fixtures/`, or `tests/fixtures/`
may be public only when it is synthetic, anonymized, sanitized, or intentionally
created for public demonstration. It should be limited to what tests,
documentation, demonstrations, or reproducibility checks need.

#### Public Evaluation Results

Small aggregate metrics, benchmark summaries, plots, and error-category
summaries may be public after sanitization. Raw evidence containing sensitive
surveillance information remains private.

### `PRIVATE_ONLY`

#### Raw Surveillance Media

Actual surveillance or real-site recordings, including typical `*.mp4`,
`*.mov`, `*.avi`, and `*.mkv` files, must remain in approved private team
storage. Synthetic or explicitly sanitized demonstration video is still
`REVIEW_REQUIRED` before publication.

#### Real Surveillance Images

Real frames or photographs containing identifiable people, private areas,
sensitive environmental details, or operational information are private.
Directories such as `frames/`, `captures/`, `snapshots/`, and `raw_images/` do
not make their contents safe.

#### Full Ground Truth Datasets

Full `dataset/raw/`, `dataset/annotations/`, train, validation, and test data are
private by default, especially when they contain real people, tracks,
timestamps, camera IDs, real locations, or surveillance events.

The public repository may document the expected private layout without
containing it. Only small sanitized samples may be considered for public
examples, and they require review.

#### Sensitive Spatial Assets

Real-site Blender files, floor plans, detailed layouts, security-camera
placements, restricted-area definitions, coverage maps, internal access routes,
and security infrastructure are private by default. Simplified or synthetic
Digital Twin assets are `REVIEW_REQUIRED` before publication.

Raw `*.blend` and `*.blend1` working assets are private by default, particularly
when large, frequently modified, tied to a real site, or internally annotated.
Sanitized `*.glb` or `*.gltf` exports require review.

#### Model Checkpoints and Weights

Files such as `*.pt`, `*.pth`, `*.ckpt`, `*.onnx`, and `*.weights` are not added
automatically. Treat them as `REVIEW_REQUIRED` and keep them private or in an
approved artifact registry unless publication is intentional and human review
confirms licensing, redistribution rights, training-data constraints,
sensitivity, and reasonable size.

#### Raw Experiment Outputs

Raw content under `experiments/`, `runs/`, `outputs/`, `predictions/`, `logs/`,
or `artifacts/` is private by default. This includes frame-level predictions,
debug images, intermediate tensors, large logs, generated media, and complete
experiment artifacts. Only small sanitized aggregate summaries may be public.

#### Secrets

Never commit `.env`, `*.pem`, `*.key`, `credentials.json`, `secrets.json`, or
any content containing API keys, tokens, passwords, SSH keys, cloud/database
credentials, camera passwords, authentication cookies, or private connection
strings. Use environment variables or an approved secret-management system.

#### Private Infrastructure

Do not publish security-relevant private IP addresses, camera authentication
endpoints, internal database/server addresses, VPN information, private cloud
resource identifiers, or internal network topology. Use placeholders in public
examples.

### `REVIEW_REQUIRED`

Human review is required before adding a non-source artifact whose safety
depends on its content. Common examples include:

```text
*.glb  *.gltf  *.obj  *.fbx
*.pt   *.pth   *.onnx
*.csv  *.json  *.jsonl
*.jpg  *.jpeg  *.png
*.pdf
```

These extensions are not inherently private. For example, an architecture
diagram or schema can be public, while a camera view or real event export is
private. Always classify semantic content, not just the extension.

### File Decision Process

Before adding a new non-source artifact to Git, apply this order:

```text
Does it contain secrets?
  Yes -> NEVER COMMIT
  No  -> Does it contain real surveillance, person, or site data?
          Yes -> PRIVATE_ONLY
          No  -> Does it expose sensitive spatial/security information?
                  Yes -> PRIVATE_ONLY
                  No  -> Is it a raw dataset, experiment, or model artifact?
                          Yes -> PRIVATE_ONLY or REVIEW_REQUIRED
                          No  -> Is it code, documentation, a schema,
                                 or a reviewed sanitized sample?
                                  Yes -> PUBLIC_ALLOWED
                                  No  -> REVIEW_REQUIRED
```

If classification is uncertain, do not add the file and request human
confirmation.

### `.gitignore` Policy Template

Inspect an existing `.gitignore` before editing it and never replace it blindly.
Prefer directory-based rules and narrowly scoped patterns. Candidate rules for
human review include:

```gitignore
# Secrets
.env
.env.*
!.env.example

# Private datasets
data/raw/
data/private/
dataset/raw/
dataset/private/

# Surveillance media
*.mp4
*.mov
*.avi
*.mkv

# Private environment assets
environment/private/
*.blend
*.blend1

# Model artifacts
models/
checkpoints/
*.pt
*.pth
*.ckpt

# Experiment artifacts
runs/
outputs/
artifacts/

# Local/private configuration
config/local.*
config/private.*
```

Do not add broad ignores such as `*.json`, `*.png`, or `*.glb`; legitimate
public schemas, diagrams, and reviewed demo assets may use those formats.
This template does not itself authorize creating or changing `.gitignore`.

### Public Placeholder Structure

The repository should document private-data interfaces without containing the
private data. A candidate public structure is:

```text
data/
├── README.md
└── examples/
    ├── sample_event.json
    ├── sample_zone.json
    └── sample_annotation.json
```

The README may describe a local private structure such as `data/raw/`,
`data/annotations/`, `data/benchmarks/`, and `data/environment/`, but it must not
contain private storage or Google Drive URLs.

### Local Development Model

`PROPOSED` directory convention for future human review:

```text
amidst/
├── src/                  # public repository
├── docs/                 # public repository
├── tests/                # public repository
├── schemas/              # public repository
├── examples/             # reviewed public samples
├── data/private/         # ignored / private storage
├── models/private/       # ignored / private storage
├── experiments/private/  # ignored / private storage
└── environment/private/  # ignored / private storage
```

Application code must use documented paths and configuration rather than
hard-coded private or Google Drive paths.

### Publication Review Checklist

Before intentionally publishing any data, media, model artifact, experiment
artifact, or spatial information, verify:

- [ ] No secrets or credentials are present.
- [ ] No private infrastructure information is present.
- [ ] No unintended personal or identifiable information is present.
- [ ] No sensitive real-site information is present.
- [ ] Dataset publication is intentional.
- [ ] Licensing permits publication.
- [ ] Model redistribution is permitted where applicable.
- [ ] File size is reasonable for Git.
- [ ] Sanitization has been reviewed.
- [ ] The public repository remains reproducible without private assets.

If any item cannot be verified, classify the artifact as `REVIEW_REQUIRED` and
do not publish it automatically.

### Review Record Template

| Artifact | Classification | Reason | Reviewer | Review date | Approved action |
| --- | --- | --- | --- | --- | --- |
| TODO | REVIEW_REQUIRED | TODO | TODO | TODO | TODO |

### Policy Acceptance Checks

- [ ] Every staged non-source artifact has an explicit classification.
- [ ] No `PRIVATE_ONLY` artifact is staged or tracked.
- [ ] Every `REVIEW_REQUIRED` artifact has recorded human approval before publication.
- [ ] Example configs contain placeholders only.
- [ ] Samples and reports have documented sanitization and rights review.
- [ ] Private data locations are described without publishing private URLs.

---

<a id="繁體中文"></a>

## 繁體中文

### 文件目的與效力

本政策是 Amidst 儲存庫內容與資料發布分類的唯一依據。它決定哪些內容可
進入公開 GitHub、哪些只能留在核准的私人空間，以及哪些必須先經人工審查。
若其他文件與本政策衝突，以本政策為準並提報衝突。

每個檔案加入 Git 前都必須依實際內容分類，而不是只看副檔名：

- `PUBLIC_ALLOWED`：通過一般檢查後可公開；
- `PRIVATE_ONLY`：不得加入公開儲存庫；
- `REVIEW_REQUIRED`：人工核准前不得加入或發布。

無法確定時一律使用 `REVIEW_REQUIRED`。

### 可以公開的內容

#### 原始碼

可公開的程式碼不得包含帳密、token、私人端點、內部拓撲、真實場域資料或
嵌入式敏感紀錄。測試應使用合成或已核准的去識別化 fixture。

#### 文件

專案規格、公開操作說明、ADR、流程與政策可公開，但不得放入私人儲存連結、
可識別人物資料、原始監控內容、實際攝影機位置、安全配置或秘密。

#### Schema 與設定範本

只描述結構、不含真實敏感紀錄的 camera、zone、event、retrieval 與
annotation schema 可以公開。`.env.example`、範例 YAML 等只能使用
placeholder，不得複製真實連線字串或秘密。

#### 清理後樣本與評估摘要

tests／fixtures、examples 或 sample_data 內的小型資料，只有在合成、匿名、
清理完成或刻意為公開展示製作，且確實為測試、文件、展示或重現所需時，
才可考慮公開。小型彙整指標、圖表與錯誤類別摘要經清理後可公開；含敏感
監控證據的原始結果仍屬私人。

### 只能私人保存的內容

#### 原始監控媒體與影像

真實監控或場域錄影，包括常見 MP4、MOV、AVI、MKV，以及包含可識別人物、
私人區域、敏感環境或作業資訊的影格／照片，都必須留在核准的私人空間。
合成或清理後的示範影片在公開前仍屬 `REVIEW_REQUIRED`。

#### 完整真值資料集

完整 raw、annotations、train、validation 與 test 資料預設為私人，尤其是
包含人物、軌跡、時間、攝影機 ID、真實位置或事件時。公開儲存庫可以描述
私人資料介面與目錄，但不能包含資料本身；小型清理樣本也必須先審查。

#### 敏感空間資產

真實場域 Blender 檔、平面圖、詳細配置、監視器位置、限制區域、涵蓋地圖、
內部動線與安全設施預設為私人。`.blend`／`.blend1` 工作檔尤其如此。
簡化或合成的數位孿生資產，以及 GLB／glTF 匯出，在發布前仍須審查。

#### 模型與實驗產物

PT、PTH、CKPT、ONNX、weights 等模型檔不得自動加入。除非發布是刻意行為，
且已確認授權、再散布權、訓練資料限制、敏感性與大小，否則應放在私人或
核准的 artifact registry。

runs、outputs、predictions、logs、artifacts 下的逐影格預測、debug 圖、
中間張量、大型 log、生成媒體與完整實驗輸出預設為私人；只有清理後的小型
彙整摘要可考慮公開。

#### 秘密與私人基礎設施

絕不可提交 `.env`、PEM／KEY、credentials、secrets，或任何 API key、
token、密碼、SSH key、雲端／資料庫／攝影機憑證、cookie 與私人連線字串。
私人 IP、認證端點、內部伺服器、VPN、雲端資源 ID 與網路拓撲也不得公開。
公開範例只能使用 placeholder。

### 必須人工審查的內容

非原始碼資產若安全性取決於內容，就必須人工審查。常見副檔名包括：

```text
*.glb  *.gltf  *.obj  *.fbx
*.pt   *.pth   *.onnx
*.csv  *.json  *.jsonl
*.jpg  *.jpeg  *.png
*.pdf
```

副檔名本身不代表私人或公開。例如架構圖與 schema 可公開，但相機畫面或
真實事件匯出不可。必須審查語意內容。

### 檔案判定流程

```text
是否含有秘密？
  是 -> 絕不可提交
  否 -> 是否含真實監控、人物或場域資料？
          是 -> PRIVATE_ONLY
          否 -> 是否暴露敏感空間或安全資訊？
                  是 -> PRIVATE_ONLY
                  否 -> 是否為原始資料集、實驗或模型產物？
                          是 -> PRIVATE_ONLY 或 REVIEW_REQUIRED
                          否 -> 是否為程式碼、文件、schema，
                                或已審查的清理樣本？
                                  是 -> PUBLIC_ALLOWED
                                  否 -> REVIEW_REQUIRED
```

### .gitignore 原則

編輯前先檢查既有 `.gitignore`，不得整份覆蓋。優先使用明確目錄與窄範圍
規則，例如秘密檔、私人資料目錄、監控影片、私人環境模型、checkpoint、
實驗輸出與本地設定。不得廣泛忽略所有 JSON、PNG 或 GLB，因為合法的公開
schema、圖表或審查後資產也可能使用這些格式。政策中的範本不代表已授權
修改 `.gitignore`。

### 公開占位結構與本地開發

公開儲存庫可以提供 data README 及合成的 sample_event、sample_zone、
sample_annotation，並描述本地可能有 raw、annotations、benchmarks 與
environment 等私人目錄；不得寫入私人儲存或 Google Drive URL。

原始碼、文件、schema 與小型合成 fixture 可由 Git 管理；大型／敏感資料、
真實 Blender 檔、模型與原始輸出留在核准的私人儲存。設定只能透過環境
變數、秘密管理工具或未追蹤的本地檔提供。

### 發布審查清單

刻意發布資料、媒體、模型、實驗產物或空間資訊前確認：

- [ ] 沒有秘密或憑證。
- [ ] 沒有私人基礎設施資訊。
- [ ] 沒有非預期的個人或可識別資訊。
- [ ] 沒有敏感真實場域資訊。
- [ ] 資料集發布是刻意行為。
- [ ] 授權允許發布。
- [ ] 適用時，模型允許再散布。
- [ ] 檔案大小適合 Git。
- [ ] 清理結果已經審查。
- [ ] 沒有私人資產時，公開儲存庫仍可重現必要行為。

任一項無法確認時，分類為 `REVIEW_REQUIRED`，不得自動發布。

審查紀錄需包含資產、分類、理由、審查者、日期與核准動作。

### 政策驗收

- [ ] 每個 staged 非原始碼資產都有明確分類。
- [ ] 沒有 `PRIVATE_ONLY` 資產被 staged 或追蹤。
- [ ] 每個 `REVIEW_REQUIRED` 資產發布前都有人工核准紀錄。
- [ ] 設定範例只有 placeholder。
- [ ] 樣本與報告有清理及使用權審查紀錄。
- [ ] 描述私人資料位置時沒有公開私人 URL。
