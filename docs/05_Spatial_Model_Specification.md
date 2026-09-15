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

### Stable Object Identity

Status: `CONFIRMED` for the `school` scene identity domain.

- Effective policy: `amidst.school.object-id/1.0.1`. The canonical base
  fingerprint algorithm and normal-object UUID derivation remain version
  `1.0.0`.
- Namespace UUID: `1601a7c1-19ac-555d-9962-05e4503ac6bd`; this literal value
  is authoritative and must not be regenerated or replaced.
- Format: `amidst:school:object:<uuid-v5>`; UUIDv5 uses the approved namespace
  and the canonical identity fingerprint defined by the policy.
- Authority: `data/annotations/instance_registry/school.json` is the versioned
  sidecar identity authority. Blender `instance_id` custom properties only
  mirror registry values.
- Blender object names are descriptive metadata and are excluded from the
  canonical identity fingerprint. Renaming does not change an assigned ID.
- The initial eligible scope is the supported `school_v1` objects of types
  `MESH`, `ARMATURE`, `CURVE`, `EMPTY`, `CAMERA`, and `FONT`, except the
  explicitly excluded imported helper camera
  `skp_camera_Last_Saved_SketchUp_View`. The camera remains in the scene but
  is not an identity-eligible dataset entity. Unsupported types require review.
- `data/annotations/instance_registry/school_v1_disambiguation.json` is the
  approved scene-specific objective-disambiguation layer for the five objects
  uniquely distinguished by sorted `hierarchy.child_fingerprints`.
- `data/annotations/instance_registry/school_v1_identity_bootstrap.json` is the
  approved initialization-only mapping for the remaining 131 objects. Each
  `bootstrap:NNN` value is opaque, unique within its collision group, and bound
  once to a current object-name locator by an explicit reviewed record. The
  locator does not enter the canonical fingerprint or UUIDv5 input. After
  assignment, the registry and `instance_id` are authoritative and the mapping
  must never be regenerated from later names or traversal order.
- For an approved override, compute a resolved identity fingerprint as SHA-256
  over canonical JSON containing only `base_fingerprint`,
  `disambiguation_method`, and `disambiguation_token`; use that resolved digest
  in the existing `amidst.school.object-id/1.0.0:<fingerprint>` UUIDv5 input.
  Normal-object IDs therefore remain unchanged.
- Duplicate fingerprints, duplicate IDs, unresolved ambiguity, and
  non-deterministic assignment are fatal validation failures. Do not use names,
  traversal order, random values, or silent reassignment as fallback.
- Removed entities retain permanent registry tombstones; IDs are never reused.
  New objects receive IDs only after prior-version identity matching.
- `school_v1` is the initial registry version. Matching behavior for future
  scene versions must be validated against their actual differences and must
  not introduce unapproved heuristics.

The approved canonicalization and type-specific fingerprint rules are recorded
by ADR-008 and the identity-policy implementation. Other coordinate, camera,
zone, semantic, and export-authority questions remain `OPEN`.

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

For the confirmed `school_v1` first synthetic slice, `visible_objects`, `nearest_object`,
`distance_to_object`, `left_of`, `right_of`, `in_front_of`, and `behind` use
stable object IDs and Blender-derived evaluated geometry under spatial contract
`amidst.school.first-slice-spatial/1.0.0`. The object anchor is the mean of the
eight evaluated bounding-box corners in world space. Distance is Euclidean from
the camera optical centre to that anchor in metres.

The right-handed `camera_cv` frame converts Blender camera-local axes to +X
image-right, +Y image-down, and +Z forward. `left_of`/`right_of` compare anchor
X and `in_front_of`/`behind` compare anchor Z with a `0.0001 m` deadband. A
deadband pair is invalid for that relation task. Distance ties within
`0.000001 m` select the lexicographically smallest stable ID and preserve the
sorted tie set.

Visibility contract `amidst.school.first-slice-visibility/1.0.0` casts one ray
through every final-resolution pixel centre. An object is visible at 16 or more
nearest-hit pixels. Occlusion is the missing fraction of its target-only
projected pixel count. Transparency or another material effect that makes this
geometric result disagree with the rendered observation invalidates the sample.
The generator must record both rule versions and all evidence counts.

For first-slice rendering, policy
`amidst.school.texture-agnostic-render/0.1.0` makes the observation surface
opaque and neutral through a global view-layer material override. Original
material slots, node trees, and missing-image paths remain historical evidence
but are not evaluated by the render layer. This deliberately gives no
authoritative visual-fidelity claim and makes the rendered front surface match
the geometric first-hit visibility model. A missing resource used outside the
overridden object-material path would still invalidate readiness.

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

### 穩定物件識別

狀態：`school` 場景識別 domain 為 `CONFIRMED`。

- 有效 policy：`amidst.school.object-id/1.0.1`；canonical base fingerprint
  algorithm 與一般物件的 UUID derivation 維持 `1.0.0`。
- Namespace UUID：`1601a7c1-19ac-555d-9962-05e4503ac6bd`；此固定值具有
  權威性，未來不得重新產生或替換。
- 格式：`amidst:school:object:<uuid-v5>`；UUIDv5 使用已核准 namespace 與
  policy 定義的 canonical identity fingerprint。
- 權威來源：`data/annotations/instance_registry/school.json` 是版本化 sidecar
  identity authority；Blender 的 `instance_id` custom property 只鏡像 registry。
- Blender object name 只是描述 metadata，不納入 canonical identity
  fingerprint；重新命名不得改變既有 ID。
- 初始適用範圍是 `school_v1` 中型別為 `MESH`、`ARMATURE`、`CURVE`、
  `EMPTY`、`CAMERA`、`FONT` 的支援物件，但明確排除 imported helper camera
  `skp_camera_Last_Saved_SketchUp_View`。該 camera 保留在場景中，但不是
  identity-eligible dataset entity；其他型別須審查。
- `data/annotations/instance_registry/school_v1_disambiguation.json` 是五個
  可由排序後 `hierarchy.child_fingerprints` 唯一區分之物件的已核准、場景限定
  objective-disambiguation layer。
- `data/annotations/instance_registry/school_v1_identity_bootstrap.json` 是其餘
  131 個物件只用於初始化的已核准 mapping。每個 `bootstrap:NNN` 都是不具
  語意、在 collision group 內唯一的 opaque value，並由明確審閱紀錄一次性
  綁定目前 object-name locator。Locator 不進入 canonical fingerprint 或
  UUIDv5 input；指派後由 registry 與 `instance_id` 擔任權威，且不得依後續
  名稱或走訪順序重新產生 mapping。
- 已核准 override 的 resolved identity fingerprint，是只含
  `base_fingerprint`、`disambiguation_method`、`disambiguation_token` 的
  canonical JSON 之 SHA-256，並將 resolved digest 放入既有
  `amidst.school.object-id/1.0.0:<fingerprint>` UUIDv5 input；一般物件 ID
  因此維持不變。
- 重複 fingerprint、重複 ID、未解歧義與非確定性結果都是致命驗證錯誤；
  不得以名稱、走訪順序、隨機值或靜默重新指派作為 fallback。
- 消失的實體要在 registry 永久保留 tombstone，ID 永不重用；新物件必須先
  與舊版本 identity 比對，才能取得新 ID。
- `school_v1` 是初始 registry 版本；未來場景版本必須依實際差異另行驗證
  matching 行為，不得加入未核准的 heuristic。

已核准的 canonicalization 與各型別 fingerprint 規則由 ADR-008 與 identity
policy implementation 記錄。其他座標、相機、zone、語意與 export authority
問題仍維持 `OPEN`。

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

已確認的 `school_v1` 首批合成資料中，`visible_objects`、`nearest_object`、
`distance_to_object`、`left_of`、`right_of`、`in_front_of` 與 `behind`
使用穩定 object ID 及 Blender-derived evaluated geometry，空間契約為
`amidst.school.first-slice-spatial/1.0.0`。Object anchor 是八個 evaluated
bounding-box corners 在 world space 的平均值；距離是 camera optical center
到 anchor 的公尺制 Euclidean distance。

右手 `camera_cv` 將 Blender camera-local axes 轉成 +X 畫面右、+Y 畫面下、
+Z forward。`left_of`／`right_of` 比較 anchor X，`in_front_of`／`behind`
比較 anchor Z，deadband 為 `0.0001 m`；落在 deadband 的 relation task 失效。
距離在 `0.000001 m` 內平手時，以 stable ID 字典序第一個為答案並保留排序後
tie set。

Visibility 契約 `amidst.school.first-slice-visibility/1.0.0` 對最終解析度每個
pixel center 發射一條 ray；至少 16 個 nearest-hit pixels 才視為可見。
Occlusion 是 target-only projected pixels 中未可見部分的比例。透明或其他
材質效果若讓此幾何結果與 rendered observation 不一致，樣本即失效。
Generator 必須記錄兩個規則版本及全部 evidence counts。

首批 render 採 `amidst.school.texture-agnostic-render/0.1.0`，以全 view-layer
material override 將 observation surface 統一為 opaque neutral。原本 material
slots、node trees 與 missing-image paths 保留為歷史證據，但 render layer 不會
執行它們。此政策明確不宣稱 authoritative visual fidelity，並讓 rendered
front surface 與 geometric first-hit visibility model 一致。若 missing resource
出現在被 override 的 object-material path 以外，readiness 仍必須失效。

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
