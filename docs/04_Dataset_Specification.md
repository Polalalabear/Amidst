# Dataset Specification Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **What data and ground truth must exist for the approved evaluation
framework to work?** Do not invent dataset size, scenario counts, or split
ratios.

`PROPOSED` planning sequence:

```text
Evaluation Requirement -> Scenario -> Required Ground Truth
-> Data Collection -> Annotation -> Benchmark
```

### Dataset Purpose

- Which requirement and evaluation question does this dataset support?
- Is it for development, benchmarking, demonstration, or regression testing?
- What decisions must its results enable?

Purpose statement: `TODO` (`OPEN`)

### Dataset Scope

| Layer / capability | Included? | Why | Required ground truth | Status |
| --- | --- | --- | --- | --- |
| Object / perception | TODO | TODO | Class, bounding box, TODO | OPEN |
| Tracking | TODO | TODO | Identity across frames, TODO | OPEN |
| Spatial | TODO | TODO | Camera, zone, location, TODO | OPEN |
| Event | TODO | TODO | Type, interval, entities, location, TODO | OPEN |
| Retrieval | TODO | TODO | Request, filters, source, records/evidence | OPEN |
| Agent | TODO | TODO | Intent, parameters, tool/evidence/answer rubric | OPEN |

### Data Sources

| Source ID | Description | Owner | Rights / consent | Sensitivity | Format | Availability | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-SRC-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

### Scenario Definition

Define what makes two scenarios meaningfully different for evaluation: `TODO`.

| Scenario ID | Description | Lighting | Occlusion | Actors | Expected Event | Required Annotation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DATA-SC-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

### Scenario Matrix

| Factor | Values to evaluate | Why | Coverage rule | Status |
| --- | --- | --- | --- | --- |
| Lighting | TODO | TODO | TODO | OPEN |
| Occlusion | TODO | TODO | TODO | OPEN |
| Distance | TODO | TODO | TODO | OPEN |
| Viewpoint | TODO | TODO | TODO | OPEN |
| Crowd density | TODO | TODO | TODO | OPEN |

Add factors only when tied to an approved use case, failure risk, or metric.

### Video Metadata

| Field | Type / format | Required? | Source | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Video ID | TODO | TODO | TODO | TODO | OPEN |
| Timestamp / time base | TODO | TODO | TODO | TODO | OPEN |
| Frame rate / dimensions | TODO | TODO | TODO | TODO | OPEN |
| Camera ID | TODO | TODO | TODO | TODO | OPEN |
| Scenario ID | TODO | TODO | TODO | TODO | OPEN |

### Camera Metadata

| Field | Required? | Source | Spatial reference | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Camera ID | TODO | TODO | TODO | TODO | OPEN |
| Position / rotation | TODO | TODO | TODO | TODO | OPEN |
| FOV / intrinsics | TODO | TODO | TODO | TODO | OPEN |
| Zone coverage | TODO | TODO | TODO | TODO | OPEN |

Align approved fields with `05_Spatial_Model_Specification.md`.

### Environmental Conditions

| Condition | Representation | Annotation method | Unknown handling | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

### Object Annotation

- Class vocabulary and inclusion/exclusion rules: `TODO`.
- Bounding-box format and coordinate convention: `TODO`.
- Occluded/truncated/ambiguous object handling: `TODO`.
- Quality-control sample and reviewer process: `TODO`.

### Tracking Annotation

- Identity scope across frames, cameras, and interruptions: `TODO`.
- Entry/exit, occlusion, merge/split, and re-identification rules: `TODO`.
- Relationship to object/person semantics: `TODO`.

### Spatial Annotation

- Required granularity: Camera / Zone / coordinates / TODO (`OPEN`).
- Boundary and unknown-location rules: `TODO`.
- Spatial model version reference: `TODO`.

### Event Annotation

| Field | Definition needed | Ambiguity rule | Status |
| --- | --- | --- | --- |
| Event type | TODO | TODO | OPEN |
| Start / end | TODO | TODO | OPEN |
| Involved entities | TODO | TODO | OPEN |
| Location | TODO | TODO | OPEN |
| Supporting evidence | TODO | TODO | OPEN |

### Retrieval Query Ground Truth

| Query ID | Natural-language need | Expected request type | Expected filters | Expected source | Expected records / evidence | Empty / ambiguity expectation | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RET-Q-xxx | TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

Questions:

- Are expected records exact, set-based, ordered, or relevance-graded?
- Which source snapshot/version makes the expected result reproducible?
- How are temporal and spatial boundary cases represented?
- What constitutes correct provenance and evidence completeness?

### Agent Query Ground Truth

| Query ID | Expected intent | Expected parameters | Allowed tool(s) | Required evidence | Answer rubric | Status |
| --- | --- | --- | --- | --- | --- | --- |
| AGENT-Q-xxx | TODO | TODO | TODO | TODO | TODO | OPEN |

Keep the expected Agent request separate from expected Retrieval execution so
failures can be attributed correctly.

### Dataset Splits

| Split | Purpose | Grouping / leakage boundary | Selection rule | Size | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO; do not invent | OPEN |

### Benchmark Set

| Benchmark ID | Dataset version | Included scenarios | Ground-truth layers | Evaluation version | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Versioning

- Dataset identifier format: `TODO`.
- Change log and immutability rules: `TODO`.
- Annotation schema compatibility: `TODO`.
- Benchmark freeze and supersession process: `TODO`.

For synthetic records derived from the `school` Blender scene, the object
identity contract is `amidst.school.object-id/1.0.1`; its canonical base
fingerprint and normal-object UUID derivation remain version `1.0.0`. Every populated record
that refers to a scene object must preserve its `instance_id`, source-scene
version and checksum, and authoritative sidecar-registry version. Blender
custom properties are mirrors and are not the sole identity authority.

For `school_v1`, five legacy external images remain historically unavailable.
They block reconstruction of the imported appearance, but the confirmed
texture-agnostic first-slice policy does not consume them at runtime. The audit
records and original paths remain preserved. A rendered observation whose
scene/resource-policy state does not match its recorded ground-truth provenance
is invalid; do not repair or guess silently.

#### Confirmed first synthetic dataset slice

Status: `CONFIRMED` for `school_v1` contract
`amidst.school.first-dataset-slice/0.1.0`. Each sample contains `image.png`,
authoritative `metadata.json`, and optional `image_gt.png` as a
non-authoritative visualization. The canonical tasks are
`visible_objects`, `nearest_object`, `distance_to_object`, `left_of`,
`right_of`, `in_front_of`, and `behind`.

These tasks reference entities by stable `instance_id` and may derive answers
from Blender camera/geometry state without named semantic categories. Until a
trusted human review assigns a category, the semantic baseline remains
`category = Unknown` and `annotation_status = needs_review`.

The confirmed rules use the evaluated world-space bounding-box centre as the
object anchor and camera-to-anchor Euclidean distance in metres. Camera frame
`camera_cv` is right-handed: +X image-right, +Y image-down, and +Z forward.
Visibility uses one ray through each final-resolution pixel centre and requires
at least 16 nearest-hit pixels. Occlusion compares that visible count with the
target-only projected count. The relation deadband is `0.0001 m`; distance and
ray-hit epsilon are `0.000001 m`. Nearest-distance ties choose the
lexicographically smallest stable ID and record the full sorted tie set.

Schema version is `0.1.0`; deterministic render config is
`amidst.school.first-slice-render/0.1.0`. Valid samples require matching scene,
registry, resource, contract, and render provenance. Unsupported photometric
visibility, deadband relations, missing resources, non-finite values, or any
render/ground-truth mismatch invalidate the sample. Output is versioned under
`school_v1_first_slice_v0_1_0`; frame directories are zero-based
`frame_000000`, never overwritten, and invalid evidence is preserved under a
`rejected/` branch. The populated scene-specific contracts remain
`REVIEW_REQUIRED` for repository publication independently of their confirmed
technical status.

Render-resource policy `amidst.school.texture-agnostic-render/0.1.0` applies one
neutral opaque, non-semantic `ViewLayer.material_override` to every view layer.
It does not edit object material slots or legacy image paths, does not encode
object names, IDs, or categories, and explicitly records
`authoritative_visual_fidelity = false`. The slice is authoritative only for
geometry/spatial ground truth. Readiness requires zero unresolved resources
required by this policy, not zero historical missing image datablocks.

### Annotation Quality Control

| Check | Sampling / coverage | Acceptance rule | Reviewer | Escalation | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Privacy / Sensitive Data

- What personal or site-sensitive information may be present?
- What consent, legal, minimization, access, retention, and deletion rules apply?
- What transformations are required before a sample can be public?
- Who approves a release?

### Data Storage Boundary

The authoritative classification rules are in
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md).
Do not duplicate or weaken them here.

| Dataset artifact | Initial classification | Reason / evidence | Reviewer | Final classification | Status |
| --- | --- | --- | --- | --- | --- |
| Raw surveillance media | PRIVATE_ONLY | Real surveillance/site content | Not publishable | PRIVATE_ONLY | CONFIRMED |
| Full real Ground Truth dataset | PRIVATE_ONLY by default | People, tracks, times, cameras, locations, or events may be sensitive | TODO if an exception is proposed | TODO | CONFIRMED policy; artifact review OPEN |
| Dataset/annotation schemas | PUBLIC_ALLOWED when they contain structure only | Must contain no real records or secrets | TODO | TODO | CONFIRMED policy; artifact review OPEN |
| Synthetic or sanitized sample | REVIEW_REQUIRED until reviewed | Sanitization, rights, and publication intent must be verified | TODO | TODO | OPEN |
| Aggregate evaluation summary | REVIEW_REQUIRED until reviewed | Must exclude sensitive raw evidence | TODO | TODO | OPEN |

Secrets, private storage URLs, and identifiable or sensitive records must not be
committed.

### Public Sample Data

| Sample | Purpose | Sanitization | License / consent | Reviewer | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

Every candidate sample must record whether it is synthetic, anonymized, or
sanitized and must pass the publication checklist in the authoritative policy.

### Private Dataset

| Collection | Access group | Storage location class | Retention | Audit | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | Do not place private URL here | TODO | TODO | OPEN |

### Coverage Criteria

| Requirement / risk | Required scenario coverage | Evidence | Gap | Status |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

### Open Questions

- Which annotation layers belong to the MVP benchmark?
- What data already exists and can legally be used?
- What grouping prevents train/validation/test leakage?
- What is the smallest dataset that can answer the first evaluation question?
- Which samples can be safely published?

### Expected Artifacts

- Approved data-source inventory and access boundary.
- Scenario and coverage matrices tied to evaluation needs.
- Versioned annotation schemas and guidelines.
- Retrieval and Agent query ground truth separated by layer.
- Benchmark manifest and annotation quality report.

### Document Acceptance Checklist

- [ ] Every included annotation layer supports an approved evaluation need.
- [ ] No dataset size, scenario count, or split ratio was invented.
- [ ] Retrieval and Agent ground truth are represented explicitly.
- [ ] Sensitive data and public samples have distinct controls.
- [ ] Dataset versions can be linked to reproducible evaluation runs.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的與規劃順序

回答：「核准的評估框架需要哪些資料與真值？」不得自行假設資料集大小、
情境數量或切分比例。

```text
評估需求 -> 情境 -> 必要真值 -> 資料蒐集 -> 標註 -> Benchmark
```

資料集用途必須說明它支援哪項需求與評估問題、用於開發／benchmark／展示
或回歸測試，以及結果要支持哪些決策。目前用途與各層是否納入均為
`OPEN`。

### 範圍、來源與情境

感知、追蹤、空間、事件、Retrieval 與 Agent 每一層都要記錄是否納入、
理由與必要真值。資料來源需記錄 ID、描述、負責人、權利／同意、敏感性、
格式、可用性與狀態。

情境要定義哪些差異對評估有意義，並記錄光線、遮擋、參與者、預期事件及
必要標註。光線、遮擋、距離、視角、人群密度等因素，只有連到核准使用
情境、失敗風險或指標時才加入。

### 影片、攝影機與環境中繼資料

影片至少要評估 Video ID、時間戳／time base、影格率／尺寸、Camera ID 與
Scenario ID 是否必填、來源為何及如何驗證。

攝影機需評估 Camera ID、位置／旋轉、FOV／intrinsics、區域涵蓋與空間
參考，並與[空間模型規格](05_Spatial_Model_Specification.md)對齊。環境條件
要說明表示方式、標註方式及未知值處理。

### 標註層

- Object：類別詞彙、納入／排除規則、框格式、座標慣例、遮擋與歧義處理。
- Tracking：跨影格／攝影機的身分範圍、進出、遮擋、合併／分裂與 Re-ID。
- Spatial：Camera／Zone／座標粒度、邊界、未知位置與空間模型版本。
- Event：事件類型、起訖、參與實體、位置、證據及歧義規則。
- Retrieval：自然語言需求、預期請求／篩選／來源／紀錄／證據，以及空結果
  與歧義期待。
- Agent：預期意圖、參數、允許工具、必要證據與回答評分規則。

Agent 的預期請求必須與 Retrieval 的預期執行分開，才能正確歸因失敗。

### 切分、Benchmark、版本與品質

Training、Validation／Development、Benchmark／Test 的用途及資料洩漏邊界
必須明確。切分規則與大小目前為 `OPEN`，不得捏造。

Benchmark manifest 要連結資料集版本、情境、真值層與評估器版本。版本政策
要定義識別方式、不可變性、schema 相容性，以及 benchmark 凍結與取代流程。
標註品質檢查需記錄抽樣／涵蓋範圍、驗收規則、審查者與提報方式。

由 `school` Blender 場景產生的合成紀錄，物件識別契約採
`amidst.school.object-id/1.0.1`；canonical base fingerprint 與一般物件的
UUID derivation 仍維持 `1.0.0`。每筆引用場景物件的實際紀錄都必須保留
`instance_id`、來源場景版本與 checksum，以及權威 sidecar registry 版本；
Blender custom property 只是鏡像，不是唯一的識別權威。

`school_v1` 的五個 legacy 外部影像仍是歷史缺失；它們阻擋 imported
appearance 的重建，但已確認的 texture-agnostic first-slice policy 不會在
runtime 消耗它們。稽核紀錄與原始路徑必須保留。rendered observation 的
場景／resource policy 狀態若與 Ground Truth provenance 不一致，樣本即
無效；不得靜默修復或猜測。

#### 已確認的首批合成資料集

`school_v1` 契約 `amidst.school.first-dataset-slice/0.1.0` 狀態為
`CONFIRMED`。每筆樣本包含 `image.png`、具權威性的 `metadata.json`，以及只供
閱讀、非權威的選用 `image_gt.png`。canonical task 為 `visible_objects`、
`nearest_object`、
`distance_to_object`、`left_of`、`right_of`、`in_front_of` 與 `behind`。

這些 task 以穩定 `instance_id` 引用實體，答案可直接由 Blender camera／
geometry state 推導，不必先有具名語意類別。可信人工審閱前，semantic
baseline 維持 `category = Unknown` 與 `annotation_status = needs_review`。

物件 anchor 採 evaluated world-space bounding-box center，距離是 camera
optical center 到 anchor 的公尺制 Euclidean distance。右手 `camera_cv` 採
+X 畫面右、+Y 畫面下、+Z camera forward。Visibility 對最終解析度每個 pixel
center 發射一條 ray，物件至少有 16 個 nearest-hit pixels 才可見；occlusion
由 visible count 與 target-only projected count 的比例定義。關係 deadband
為 `0.0001 m`，distance／ray-hit epsilon 為 `0.000001 m`。最近距離平手時依
stable ID 字典序選第一個，並記錄完整排序後 tie set。

Metadata schema 版本為 `0.1.0`，render config 為
`amidst.school.first-slice-render/0.1.0`。場景、registry、資源、契約與 render
provenance 必須一致；不支援的 photometric visibility、deadband 關係、資源
缺漏、非有限值或 render／ground-truth 不一致都使樣本失效。輸出版本為
`school_v1_first_slice_v0_1_0`，frame 目錄從 `frame_000000` 起且不得覆寫，
失效證據保存在 `rejected/`。場景專屬契約的技術狀態雖已確認，Git 發布分類仍
獨立維持 `REVIEW_REQUIRED`。

Render-resource policy `amidst.school.texture-agnostic-render/0.1.0` 對每個
view layer 套用單一 neutral opaque、無語意的
`ViewLayer.material_override`。它不改 object material slots 或 legacy image
paths，不以 object name／ID／category 編碼外觀，並明確記錄
`authoritative_visual_fidelity = false`。此 slice 只對 geometry／spatial
ground truth 具權威性。Readiness 要求的是 approved policy 所需資源無未解
項目，而不是歷史 missing image datablock 必須為零。

### 隱私、儲存與公開樣本

需確認個人或場域敏感資訊、同意與法規、資料最小化、存取、保存、刪除及
發布核准權責。具約束力的分類規則在
[發布政策](08_Repository_and_Data_Publication_Policy.md)。

| 資產 | 初始分類 |
| --- | --- |
| 原始監控媒體 | PRIVATE_ONLY |
| 完整真實 Ground Truth | 預設 PRIVATE_ONLY |
| 只含結構的 schema | 無真實紀錄或秘密時可 PUBLIC_ALLOWED |
| 合成或去識別化樣本 | 審查前 REVIEW_REQUIRED |
| 彙整評估摘要 | 審查前 REVIEW_REQUIRED |

公開候選樣本必須記錄是合成、匿名或清理後資料，並通過發布檢查；私人資料表
不得記錄私人儲存網址。

### 未決問題、產出與驗收

- MVP benchmark 包含哪些標註層？
- 已有哪些資料且可合法使用？
- 如何分組才能避免 train／validation／test 洩漏？
- 能回答第一個評估問題的最小資料集是什麼？
- 哪些樣本可以安全公開？

預期產出包括資料來源盤點、情境／涵蓋矩陣、版本化標註 schema 與指引、
分層的 Retrieval／Agent 真值、benchmark manifest 與標註品質報告。

- [ ] 每個標註層都支持核准的評估需求。
- [ ] 沒有捏造資料量、情境數或切分比例。
- [ ] Retrieval 與 Agent 真值分開表示。
- [ ] 敏感資料與公開樣本採不同控制。
- [ ] 資料版本可連到可重現的評估。
