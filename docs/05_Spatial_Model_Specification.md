# Spatial Model Specification Worksheet

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **How is the physical world represented, versioned, and mapped to
observations and system entities?** The existing Blender resource must be
inspected before its properties are recorded as facts.

### Spatial Model Purpose

- Which approved use cases require spatial information?
- What is the minimum spatial granularity for the first prototype?
- Which component consumes each spatial artifact?

Purpose statement: `TODO` (`OPEN`)

### Blender Resource Inventory

| Item ID | Object / collection | Type | Intended meaning | Existing annotation | Export needed | Verified by | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SP-INV-xxx | TODO after inspection | TODO | TODO | TODO | TODO | TODO | OPEN |

Inspection record:

| Field | Value |
| --- | --- |
| File/version inspected | TODO |
| Inspector | TODO |
| Date | TODO |
| Read-only backup/reference | TODO |
| Known limitations | TODO |

### Coordinate System

| Question | Decision / evidence | Status |
| --- | --- | --- |
| Which coordinate reference is authoritative? | TODO | OPEN |
| Is it local, building-relative, geographic, or another system? | TODO | OPEN |
| How are transforms represented and versioned? | TODO | OPEN |

### Unit / Scale

- Blender scene unit: `TODO after inspection`.
- Physical unit and scale factor: `TODO after verification`.
- Independent scale validation method: `TODO`.
- Tolerance: `TODO`.

### Origin

- Origin definition and physical reference: `TODO`.
- How can the origin be recovered after export? `TODO`.
- Who may change it and what must be revalidated? `TODO`.

### Axis Convention

| Context | Handedness | Up | Forward | Transform to canonical | Status |
| --- | --- | --- | --- | --- | --- |
| Blender source | TODO | TODO | TODO | TODO | OPEN |
| Export format | TODO | TODO | TODO | TODO | OPEN |
| Application / evaluator | TODO | TODO | TODO | TODO | OPEN |

### Environment Geometry

- Which geometry is semantically or visually required?
- Which objects are decorative, collision-relevant, occluding, or sensitive?
- What simplification and export checks are allowed?
- How are geometry versions identified?

### Semantic Zones

| Zone ID | Name | Meaning | Boundary representation | Parent / adjacency | Source | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

### Zone IDs

- Namespace and uniqueness boundary: `TODO`.
- Stability across model revisions: `TODO`.
- Rename, split, merge, and deletion rules: `TODO`.
- Human-readable label versus machine identifier: `TODO`.

### Camera Model

- What does a camera entity represent: physical device, stream, calibration, or view?
- Which camera properties are authoritative in Blender versus external metadata?
- How are camera and stream versions related?

### Camera IDs

| Camera ID | Blender object | Physical/source reference | Stream reference | Verified | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Position / Rotation

| Camera ID | Position | Rotation convention | Coordinate reference | Measurement source | Uncertainty | Status |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | OPEN |

### FOV

| Camera ID | Horizontal FOV | Vertical FOV | Intrinsics / derivation | Verified against | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Camera Coverage

- Is coverage geometric, observed, manually annotated, or empirically measured?
- How are blind spots, occlusion, uncertainty, and dynamic changes represented?
- Which coverage result is suitable for evaluation?

### Camera-to-Zone Mapping

| Camera ID | Zone ID | Relationship | Confidence / evidence | Effective version | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | Observes / located-in / TODO | TODO | TODO | OPEN |

### Observation-to-Zone Mapping

| Mapping input | Method | Output | Unknown / boundary behavior | Evaluation evidence | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

`PROPOSED` MVP candidate: Observation -> Camera -> Zone. Do not treat precise
pixel-to-3D localization as required without an approved use case.

### Physical-to-Digital Mapping

| Physical concept | Digital entity | Identifier link | Transform / mapping | Source of truth | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Spatial Ground Truth

- What is annotated: camera, zone, point, region, path, or relationship?
- What precision and uncertainty are required?
- How is ground truth linked to environment and camera versions?
- How are disputed boundary cases adjudicated?

### Spatial Evaluation

| Capability | Ground truth | Prediction | Match / tolerance | Failure categories | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Export Format

Candidate outputs, not confirmed requirements. Before adding any output to Git,
apply
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md);
a filename or export format alone never establishes that an asset is safe.

| Path | Intended role | Consumer | Required fields / checks | Initial repository class | Status |
| --- | --- | --- | --- | --- | --- |
| `data/environment/building.glb` | Exported environment geometry | TODO | Sanitization, real-site sensitivity, rights, size | REVIEW_REQUIRED | PROPOSED |
| `data/environment/environment.json` | Environment metadata | TODO | Sensitive layout/security content review | REVIEW_REQUIRED | PROPOSED |
| `data/environment/zones.json` | Machine-readable zones | TODO | Real-site/restricted-area content review | REVIEW_REQUIRED | PROPOSED |
| `data/environment/cameras.json` | Machine-readable cameras/calibration | TODO | Camera placement and infrastructure review | REVIEW_REQUIRED | PROPOSED |

### Machine-Readable Metadata

| Concept | Required fields | Schema owner | Version link | Validation | Status |
| --- | --- | --- | --- | --- | --- |
| Environment | TODO | TODO | TODO | TODO | OPEN |
| Zone | TODO | TODO | TODO | TODO | OPEN |
| Camera | TODO | TODO | TODO | TODO | OPEN |
| Transform | TODO | TODO | TODO | TODO | OPEN |

### Visualization Mapping

- Which stored entities appear in the Digital Twin?
- How are time, coordinates, zone labels, evidence, and selection synchronized?
- What happens when spatial data is missing or stale?
- Which visualization behavior is representational versus authoritative?

### Known Limitations

| Limitation | Affected capability | Workaround | Revisit trigger | Status |
| --- | --- | --- | --- | --- |
| TODO after inspection | TODO | TODO | TODO | OPEN |

### Future Precise Localization

Status: `DEFERRED` unless an approved requirement changes it.

- What use case would justify pixel-to-world or multi-camera localization?
- Which calibration, synchronization, depth, or ground truth would be required?
- What accuracy would matter operationally?

### Open Questions

- What does the Blender model actually contain and which parts are sensitive?
- Which coordinate system and metadata source are authoritative?
- Is zone-level mapping sufficient for the first prototype?
- How are spatial revisions propagated to datasets and evaluations?

### Expected Artifacts

- Reviewed Blender/environment inventory.
- Approved coordinate, unit, axis, ID, and version conventions.
- Camera/zone mapping with evidence and uncertainty.
- Machine-readable export contract.
- Spatial ground-truth and evaluation plan.

### Document Acceptance Checklist

- [ ] No Blender property is claimed without inspection evidence.
- [ ] Coordinate and camera conventions are explicit and testable.
- [ ] Minimum spatial granularity is tied to an approved use case.
- [ ] Exported metadata preserves IDs, version, and provenance.
- [ ] Every spatial artifact has an approved repository classification.
- [ ] Sensitive real-site assets remain `PRIVATE_ONLY`.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的

回答：「實體世界如何被表示、版本化，並與觀測及系統實體建立映射？」在
實際檢查既有 Blender 資源前，不得把其屬性寫成事實。空間用途與第一版
原型需要的最小粒度目前為 `OPEN`。

### Blender 資源盤點

每個物件／Collection 都要記錄項目 ID、型別、預期意義、既有標註、是否
需要匯出、查驗人員與狀態。檢查紀錄需包含檔案／版本、檢查者、日期、
唯讀備份／參考及已知限制。

### 座標、單位、原點與軸向

- 明確指定權威座標參考，以及它是本地、建築相對、地理或其他系統。
- 記錄並版本化所有 transform。
- 查驗 Blender scene unit、實體單位與比例，並用獨立方法驗證尺度與容差。
- 定義原點的實體參考、匯出後如何復原，以及變更後要重驗哪些內容。
- Blender、匯出格式與應用／評估器都要記錄 handedness、up、forward 與
  轉換到 canonical 座標的方法。

以上在查驗或決策前均為 `OPEN`。

### 幾何、區域與識別碼

需要區分語意／視覺必要、裝飾、碰撞、遮擋與敏感幾何，並記錄簡化、
匯出檢查與版本。每個 Zone 要有穩定 ID、名稱、意義、邊界表示、父子／
相鄰關係、來源與狀態。

Zone ID 規則需涵蓋命名空間、唯一性、跨版本穩定性，以及重新命名、分割、
合併與刪除；顯示名稱不得取代機器識別碼。

### 攝影機模型

需先確認 Camera 代表實體裝置、stream、校正還是視角，以及哪些屬性由
Blender 或外部中繼資料負責。每台攝影機應評估：

- Camera ID、Blender 物件、實體／來源與 stream 參考；
- 位置、旋轉慣例、座標參考、量測來源與不確定性；
- 水平／垂直 FOV、intrinsics、推導方式與驗證依據；以及
- 涵蓋範圍是幾何推算、觀測、人工標註或實測，如何表示盲區與遮擋。

### 空間映射與真值

Camera-to-Zone 要記錄關係、信心／證據與生效版本；Observation-to-Zone
則要記錄輸入、方法、輸出、未知／邊界行為與評估證據。

`PROPOSED` MVP 候選：

```text
Observation -> Camera -> Zone
```

沒有核准需求時，不得把精確 pixel-to-3D 定位視為必要。

實體到數位的映射需指出實體概念、數位實體、ID 連結、transform 與資料
依據。空間 Ground Truth 必須定義標註粒度、精度、不確定性、環境／相機
版本及爭議邊界裁決方式。

### 匯出與機器可讀資料

候選輸出包括 environment `.glb`、environment／zones／cameras JSON；
這些格式不代表可公開。真實場域幾何、配置、攝影機位置及限制區域都須依
[發布政策](08_Repository_and_Data_Publication_Policy.md)審查，初始分類為
`REVIEW_REQUIRED` 或 `PRIVATE_ONLY`。

Environment、Zone、Camera 與 Transform 的機器資料需定義必要欄位、
schema 主責、版本連結與驗證方法，目前仍為 `OPEN`。

### 視覺化、限制與未來定位

需說明哪些實體出現在數位孿生中，時間、座標、區域、證據與選取如何同步，
資料缺漏／過期時如何呈現，以及哪些畫面只是表現、哪些具權威性。

已知限制應記錄影響、替代方式與重新檢視條件。精確定位維持
`DEFERRED`，除非核准需求改變，並且已有校正、同步、深度、真值與可衡量
精度要求。

### 未決問題與驗收

- Blender 模型實際包含什麼，哪些部分敏感？
- 哪套座標與中繼資料具權威性？
- 第一版原型是否只需區域層級映射？
- 空間版本如何傳遞到資料集與評估？

- [ ] 沒有未經查驗就宣稱 Blender 屬性。
- [ ] 座標與攝影機慣例明確且可測試。
- [ ] 最小空間粒度連到核准使用情境。
- [ ] 匯出資料保留 ID、版本與 provenance。
- [ ] 每項空間資產都有核准的儲存庫分類。
- [ ] 敏感真實場域資產維持 `PRIVATE_ONLY`。
