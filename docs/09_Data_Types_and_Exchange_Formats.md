# Data Types and Exchange Formats

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` design guide

Repository classification: `PUBLIC_ALLOWED`

### Purpose

Define a reviewable starting point for the data contracts that may connect
spatial assets, video observations, detections, tracks, events, evidence,
Retrieval, and evaluation.

This document recommends fields and boundaries. It does not confirm the MVP
schema, storage technology, event vocabulary, or adoption of an external
standard. Those decisions remain `OPEN` under
[OQ-015](open_questions.md).

When a candidate is confirmed, its normative requirements must be recorded in
the core specification that owns the behavior. This guide should then link to
that requirement instead of becoming a duplicate source of truth.

### Scope

This guide covers:

- common identifiers, versions, timestamps, and provenance;
- Blender source-scene inventory and runtime spatial exports;
- video asset and stream metadata;
- event records and their links to observations, tracks, zones, and evidence;
- serialization and validation considerations; and
- candidate alignment with glTF 2.0 and ASAM OpenLABEL 1.0.

It does not define database tables, APIs, transport protocols, model outputs,
retention rules, or a complete annotation ontology.

### Design Principles

1. Use stable machine identifiers separately from human-readable names.
2. Version schemas, controlled vocabularies, datasets, spatial models, and
   producers independently.
3. Preserve the distinction between observation, annotation, model prediction,
   deterministic derivation, inference, and human confirmation.
4. Keep time, coordinate system, units, uncertainty, and provenance explicit.
5. Reference large or private media by an authorized opaque identifier; do not
   embed private locations in public records.
6. Preserve empty, unknown, ambiguous, partial, stale, and unavailable states.
7. Prefer backward-compatible extension fields over silent reinterpretation.

### Candidate Artifact Set

| Artifact | Candidate serialization | Role | Initial repository class | Status |
| --- | --- | --- | --- | --- |
| Spatial source | `.blend` | Authoring file and inspection source | `PRIVATE_ONLY` by default | PROPOSED |
| Runtime scene | `.glb` or `.gltf` | Interchange geometry and scene graph | `REVIEW_REQUIRED` | PROPOSED |
| Spatial manifest | JSON | Versions, coordinates, units, cameras, zones, checksums | Structure may be `PUBLIC_ALLOWED`; populated real-site record requires review | PROPOSED |
| Video manifest | JSON or JSONL | Video identity, stream, timing, encoding, and provenance | Schema may be `PUBLIC_ALLOWED`; real records are `PRIVATE_ONLY` by default | PROPOSED |
| Event records | JSONL for exchange; another store may be selected later | One independently readable event per line | Schema may be `PUBLIC_ALLOWED`; real records are `PRIVATE_ONLY` by default | PROPOSED |
| Evidence manifest | JSON or JSONL | Trace from a claim to authorized source material | Real records are `PRIVATE_ONLY` by default | PROPOSED |
| JSON Schema | JSON | Machine validation of public structures | `PUBLIC_ALLOWED` when it contains no real data | PROPOSED |

The publication class depends on content, not the extension. Apply
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md)
before adding any populated artifact.

### Common Record Envelope

The following fields are candidates for records that cross module boundaries:

| Field | Candidate type | Meaning | Status |
| --- | --- | --- | --- |
| `schema_name` | string | Stable contract name | PROPOSED |
| `schema_version` | semantic-version string | Contract version used to encode the record | PROPOSED |
| `record_id` | string | Stable identifier within the declared namespace | PROPOSED |
| `record_kind` | controlled string | Observation, detection, track, event, evidence, or another approved type | PROPOSED |
| `created_at` | RFC 3339 timestamp | Time the record was created, not necessarily observation time | PROPOSED |
| `producer` | object | Component, model, configuration, and version that produced it | PROPOSED |
| `provenance` | object | Source identifiers and transformation lineage | PROPOSED |
| `quality_flags` | string array | Explicit missing, ambiguous, partial, stale, or review-needed conditions | PROPOSED |

Namespace convention, identifier format, schema registry, and compatibility
policy remain `OPEN` generally. The confirmed `school` Blender-object identity
contract below is a scoped exception and does not settle other record types.

### Time Representation

#### Candidate rules

- Use RFC 3339 timestamps with an explicit offset; normalize exchange records
  to UTC when the source clock can support it.
- Preserve the original clock source, time base, synchronization method, and
  uncertainty rather than implying false precision.
- Store frame indices as integers and define whether indexing begins at zero.
- For variable-frame-rate video, do not derive authoritative timestamps from a
  nominal frame rate alone.
- Carry both event time and record-processing time when both matter.

#### Decisions still required

| Question | Status |
| --- | --- |
| Are event intervals closed, open, or half-open? | OPEN |
| What clock is authoritative across cameras? | OPEN |
| How are clock drift and synchronization uncertainty represented? | OPEN |
| Is a frame index, presentation timestamp, UTC timestamp, or combination authoritative? | OPEN |

### Blender and Spatial Data

#### Source-scene inventory

Before using a Blender file, record:

| Group | Candidate fields or checks | Status |
| --- | --- | --- |
| Identity | `environment_id`, source filename alias, content checksum, spatial-model version | PROPOSED |
| Authoring | Blender version, exporter version, inspection date, inspector | PROPOSED |
| Units | unit system, unit scale, independently verified physical scale | PROPOSED |
| Coordinates | origin definition, handedness, up/forward axes, transform to canonical coordinates | PROPOSED |
| Collections | stable collection ID, purpose, visibility/export rule | PROPOSED |
| Objects | stable object ID, semantic type, parent, transform, geometry role | PROPOSED |
| Zones | stable zone ID, label, boundary representation, parent/adjacency, version | PROPOSED |
| Cameras | stable camera ID, transform, projection type, lens/FOV data, calibration source | PROPOSED |
| Sensitivity | real-site content, restricted areas, camera placement, publication class | PROPOSED |

Blender scene units affect displayed values and must not be treated as proof of
physical scale without independent verification.

#### Confirmed school object identity contract

The `school` Blender-object identity contract is
`amidst.school.object-id/1.0.1`; the canonical base fingerprint and normal-ID
derivation remain `1.0.0`:

- authoritative namespace UUID:
  `1601a7c1-19ac-555d-9962-05e4503ac6bd`;
- identifier format: `amidst:school:object:<uuid-v5>`;
- UUID input: the policy's canonical SHA-256 identity fingerprint, encoded as
  `amidst.school.object-id/1.0.0:<fingerprint>`;
- canonical encoding: Unicode NFC strings in UTF-8; finite floats encoded as
  lowercase `float.hex()` strings; explicit nulls; deterministic arrays;
  JSON keys sorted by Unicode code point, no insignificant whitespace, and no
  trailing newline;
- eligible `school_v1` types: `MESH`, `ARMATURE`, `CURVE`, `EMPTY`, `CAMERA`,
  and `FONT`, using the type-specific signatures approved by ADR-008;
- object names are excluded from fingerprint and UUID generation;
- duplicate fingerprints, duplicate IDs, ambiguity, unsupported types, and
  non-determinism are fatal validation results; and
- canonical registry path:
  `data/annotations/instance_registry/school.json`.

The `school_v1` amendment adds two canonical, scene-version-specific inputs:

- `school_v1_disambiguation.json` contains the five approved
  `hierarchy.child_fingerprints` records;
- `school_v1_identity_bootstrap.json` contains 131 reviewed opaque mappings
  with discriminator format `bootstrap:` plus exactly three ASCII decimal
  digits, unique within each duplicate-fingerprint group.

Bootstrap locators are NFC UTF-8 sorted only to construct and serialize the
explicit initial mapping; locator text is excluded from the resolved-identity
payload. The resolved fingerprint is SHA-256 over canonical JSON with exactly
`base_fingerprint`, `disambiguation_method`, and `disambiguation_token`.
UUIDv5 then uses the unchanged name
`amidst.school.object-id/1.0.0:<resolved-fingerprint>`. Missing or conflicting
records invalidate assignment. The imported saved-view camera
`skp_camera_Last_Saved_SketchUp_View` is an explicit policy-1.0.1 eligibility
exclusion and remains unmodified in the Blender scene.

Registry identity records are authoritative and versioned. Blender
`instance_id` custom properties are mirrors, not independent identity records.
Registry serialization is canonical; deterministic identity content excludes
run timestamps. Retired IDs remain as permanent tombstones and are never
reused.

#### Confirmed school_v1 first-slice contracts

The following artifacts are `CONFIRMED` for the scoped `school_v1` first
synthetic dataset slice. Their repository-publication classification remains
`REVIEW_REQUIRED`; this confirmation does not authorize Git publication:

- `data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json` keeps
  all unreviewed entities at `Unknown` / `needs_review` and defines the required
  fields for a future human-reviewed record; its schema and annotation version
  are `0.1.0` / `school.v1.semantic/0.1.0`;
- `data/metadata/first_dataset_slice_tasks_v0_1_0.json` defines the seven
  canonical task identifiers, object eligibility, spatial/visibility versions,
  tolerances, ties, invalidation, and output naming under contract
  `amidst.school.first-dataset-slice/0.1.0`;
- `data/metadata/first_dataset_slice_metadata_schema_v0_1_0.json` makes
  `metadata.json` authoritative for scene checksums, camera pose/intrinsics,
  visible IDs, distances, relations, task answers, validity, and provenance;
  and
- `data/metadata/first_dataset_slice_render_config_v0_1_0.json` records current
  and locked Blender 5.2.1 build, EEVEE, output, colour, seed, platform, and
  camera settings under `amidst.school.first-slice-render/0.1.0`; and
- `data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json`
  records policy `amidst.school.texture-agnostic-render/0.1.0`, source/input/
  derived checksums, the neutral material override, preserved unavailable
  legacy resources, authorized datablock changes, and
  `authoritative_visual_fidelity = false`.

The authoritative schema ID is
`amidst.first-dataset-slice.metadata/0.1.0`. Output dataset version is
`school_v1_first_slice_v0_1_0`; directories use zero-based six-digit
`frame_000000` names, are immutable once written, and preserve rejected sample
evidence separately. A generator may run only after the full readiness report
has zero blockers, regardless of these files' confirmed status.
For this policy the resource gate is "zero unresolved resources required by the
approved render policy". Historical image datablocks may remain missing when
they are preserved, recorded, and unreachable from the active overridden render
path.

#### Camera fields

For each camera, consider:

- `camera_id` and the corresponding Blender object ID;
- position and rotation with an explicit coordinate reference;
- projection type;
- focal length, horizontal and vertical field of view;
- sensor width, sensor height, and sensor-fit mode;
- render width and height;
- lens shifts and near/far clipping distances;
- intrinsic matrix and distortion coefficients when real calibration exists;
- calibration source, date, version, uncertainty, and verification evidence;
- covered or associated zone IDs; and
- stream IDs, without embedding private stream URLs.

Do not calculate or claim real calibration merely from a visually aligned
Blender camera.

#### Runtime export

`PROPOSED`: Use glTF 2.0 (`.glb` or `.gltf`) as a candidate runtime
geometry format and keep project semantics in a versioned sidecar manifest.

The glTF 2.0 specification defines a right-handed coordinate system, metres for
linear distance, and radians for angles. Blender can export custom properties
to glTF `extras`, but `extras` has no project-wide namespace or schema.
Therefore:

- record the Blender-to-glTF axis and unit conversion;
- verify node transforms, camera references, materials, visibility, and scale
  after export;
- use stable IDs rather than display names as cross-file keys;
- reserve a project prefix such as `amidst_*` for Blender custom properties;
- keep the sidecar manifest authoritative for Amidst semantics unless a later
  decision explicitly adopts `extras`; and
- record source and export checksums so geometry and metadata cannot be mixed
  across versions silently.

The canonical export format and location of authoritative spatial metadata are
`OPEN`.

### Video Asset and Stream Metadata

Keep the video bytes separate from their manifest. Candidate manifest fields:

| Field | Candidate type | Purpose | Status |
| --- | --- | --- | --- |
| `video_id` | string | Stable identity independent of filename | PROPOSED |
| `camera_id` / `stream_id` | string | Link to source and spatial metadata | PROPOSED |
| `media_ref` | opaque string | Authorized lookup key; never a public private-storage URL | PROPOSED |
| `content_hash` | algorithm + digest | Integrity and reproducibility | PROPOSED |
| `container` / `video_codec` | string | Decode requirements | PROPOSED |
| `width` / `height` | integer | Frame dimensions in pixels | PROPOSED |
| `pixel_format` / `color_space` | string | Image interpretation | PROPOSED |
| `frame_rate` | rational or explicit variable-rate marker | Nominal sampling description | PROPOSED |
| `time_base` | rational | Interpretation of presentation timestamps | PROPOSED |
| `frame_count` / `duration` | integer / duration | Coverage and validation | PROPOSED |
| `start_time` | RFC 3339 timestamp or explicit unknown | Link to external time | PROPOSED |
| `clock_source` | controlled string | Clock authority and synchronization | PROPOSED |
| `dataset_version` / `scenario_id` | string | Evaluation context | PROPOSED |
| `provenance` | object | Capture, sanitization, transcoding, and derivation history | PROPOSED |

The manifest should make `unknown` explicit instead of filling unavailable
capture metadata with guessed values.

### Video Event Record

`PROPOSED`: Represent exchange events as independently readable JSON objects;
JSONL is a practical candidate when records are appended or streamed. A
candidate event includes:

| Field | Candidate type | Purpose | Status |
| --- | --- | --- | --- |
| `event_id` | string | Stable event identity | PROPOSED |
| `event_type` | controlled string | Event category | PROPOSED |
| `event_type_version` | string | Vocabulary version | PROPOSED |
| `source_kind` | enum | `annotation`, `prediction`, `derived`, or `human_confirmed` | PROPOSED |
| `start_time` / `end_time` | RFC 3339 timestamp or null | Absolute interval when known | PROPOSED |
| `start_frame` / `end_frame` | integer or null | Frame interval in the referenced video | PROPOSED |
| `video_id` / `camera_ids` | string / string array | Observation sources | PROPOSED |
| `track_ids` / `entity_refs` | string arrays | Involved temporal or domain entities | PROPOSED |
| `zone_ids` | string array | Spatial association | PROPOSED |
| `confidence` | object or null | Value, producer, meaning, and calibration reference | PROPOSED |
| `evidence_refs` | string array | Traceable supporting records or media segments | PROPOSED |
| `provenance` | object | Producer, source records, transformations, and versions | PROPOSED |
| `attributes` | object | Vocabulary-controlled event-specific values | PROPOSED |
| `quality_flags` | string array | Ambiguity, truncation, missing source, or review state | PROPOSED |

Synthetic structural example:

```json
{
  "schema_name": "amidst.video_event",
  "schema_version": "0.1.0-proposed",
  "event_id": "synthetic-event-001",
  "event_type": "zone_entry",
  "event_type_version": "synthetic-v1",
  "source_kind": "annotation",
  "start_time": "2026-01-01T00:00:10Z",
  "end_time": "2026-01-01T00:00:12Z",
  "start_frame": 250,
  "end_frame": 300,
  "video_id": "synthetic-video-001",
  "camera_ids": ["synthetic-camera-001"],
  "track_ids": ["synthetic-track-001"],
  "entity_refs": [],
  "zone_ids": ["synthetic-zone-001"],
  "confidence": null,
  "evidence_refs": ["synthetic-evidence-001"],
  "provenance": {
    "dataset_version": "synthetic-demo-001",
    "producer": "human_annotation"
  },
  "attributes": {},
  "quality_flags": []
}
```

This example demonstrates structure only. Its field names, interval semantics,
and vocabulary are not a confirmed contract.

### Detection, Track, and Evidence Links

Avoid nesting an entire history into every event. Prefer references to
versioned records:

```text
Video / Observation
  -> Detection
  -> Track
  -> Event
  -> Evidence
  -> Retrieved Result
  -> Agent Interpretation
```

Candidate minimum links:

- Detection: observation/video ID, frame or timestamp, class, geometry,
  confidence, producer/model version.
- Track: track ID, detection references, lifespan, identity scope, tracker
  version, discontinuity flags.
- Evidence: evidence ID, source record IDs, authorized media segment reference,
  time/spatial scope, derivation and redaction metadata.

Whether Detection, Track, Event, and Evidence share one envelope or separate
schemas is `OPEN`.

### ASAM OpenLABEL Compatibility Candidate

ASAM OpenLABEL 1.0 defines a JSON schema for multi-sensor labeling and scenario
tagging, including streams, coordinate systems, frames, objects, actions,
events, contexts, relations, and frame intervals.

`PROPOSED`: Perform a small fit assessment before designing a custom
annotation format:

| Amidst concern | OpenLABEL area to evaluate |
| --- | --- |
| Camera/video source | Streams |
| Per-frame content | Frames |
| Detections and tracks | Objects and frame intervals |
| Activities and occurrences | Actions and events |
| Spatial references | Coordinate systems |
| Entity relationships | Relations |
| Vocabulary governance | Ontologies and types |

Adoption is not automatic. The assessment must consider surveillance-specific
event semantics, privacy, tool support, transformation cost, schema complexity,
and whether a smaller internal contract is sufficient. Selecting OpenLABEL,
adapting a subset, or defining an Amidst schema requires human confirmation and
an ADR.

### Validation Recommendations

`PROPOSED` validation layers:

1. syntax validation for JSON or JSONL;
2. JSON Schema validation for field types and required values;
3. referential checks for video, camera, zone, track, event, and evidence IDs;
4. temporal checks for ordering, time base, frame range, and duration;
5. spatial checks for units, transforms, coordinate references, and export
   version alignment;
6. provenance checks for producer and source references;
7. classification checks before any populated artifact enters Git; and
8. fixture tests using only synthetic or approved sanitized data.

No validation dependency is selected by this document.

### Decisions Required Before Implementation

| Decision | Affected documents | Status |
| --- | --- | --- |
| MVP entities and required relationships | PRD, Architecture, Dataset, Retrieval | OPEN |
| Canonical schema names, owners, and compatibility rules | Architecture, ADR | OPEN |
| OpenLABEL adoption or custom schema | Dataset, Architecture, ADR | OPEN |
| Event vocabulary and interval semantics | Dataset, Evaluation, Retrieval | OPEN |
| Authoritative timestamp and synchronization rules | Dataset, Architecture, Evaluation | OPEN |
| Authoritative spatial metadata location and export format | Spatial, Architecture, ADR | OPEN |
| Required evidence chain and authorization behavior | Retrieval, Dataset, Architecture | OPEN |

### References

- [Blender Manual: Scene Properties and Units](https://docs.blender.org/manual/en/5.0/scene_layout/scene/properties.html)
- [Blender Python API: Camera](https://docs.blender.org/api/5.0/bpy.types.Camera.html)
- [Blender Manual: glTF 2.0 import and export](https://docs.blender.org/manual/en/5.0/addons/import_export/scene_gltf2.html)
- [Khronos glTF 2.0 specification](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- [ASAM OpenLABEL overview](https://www.asam.net/standards/detail/openlabel/)
- [ASAM OpenLABEL 1.0 schema and examples](https://openlabel.asam.net/)

External references inform the recommendations above but do not override Amidst
project decisions or publication policy.

### Document Acceptance Checklist

- [ ] Required types are limited to an approved MVP and evaluation need.
- [ ] Schema ownership and compatibility policy are confirmed.
- [ ] Time, units, coordinates, uncertainty, and provenance are testable.
- [ ] Annotation, prediction, derivation, and human confirmation remain distinct.
- [ ] External-format adoption has a documented fit assessment and ADR.
- [ ] Populated artifacts have an approved repository classification.
- [ ] Examples are synthetic or explicitly reviewed and sanitized.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 設計導讀

儲存庫分類：`PUBLIC_ALLOWED`

### 文件目的與範圍

提供一套可審查的資料契約起點，讓空間資產、影片觀測、Detection、Track、
Event、Evidence、Retrieval 與評估可以互相連接。

本文件只提出欄位與邊界建議，不會定案 MVP schema、儲存技術、事件詞彙或
外部標準。相關決策仍依 [OQ-015](open_questions.md) 維持 `OPEN`。候選
方案確認後，具規範性的要求必須寫回主責核心規格，本導讀只保留連結，避免
形成重複的唯一依據。

涵蓋範圍包括共用 ID／版本／時間／provenance、Blender 與 runtime 空間
匯出、影片與 stream 中繼資料、事件與證據關係、序列化與驗證，以及 glTF
2.0 與 ASAM OpenLABEL 1.0 的候選對應。不包含資料庫、API、傳輸協定、
模型輸出、保存政策或完整 ontology。

### 設計原則

1. 機器穩定 ID 與人類顯示名稱分開。
2. Schema、詞彙、資料集、空間模型與 producer 各自版本化。
3. 清楚區分觀測、人工標註、模型預測、確定性衍生、推論與人工確認。
4. 時間、座標、單位、不確定性與來源追溯都要明示。
5. 大型或私人媒體只使用授權的 opaque ID，不把私人位置放進公開紀錄。
6. 保留 unknown、ambiguous、partial、stale 與 unavailable。
7. 優先以向後相容的擴充欄位演進，不得默默改變既有語意。

### 候選產物

| 產物 | 候選格式 | 初始分類 | 狀態 |
| --- | --- | --- | --- |
| 空間原始檔 | `.blend` | 預設 PRIVATE_ONLY | PROPOSED |
| Runtime 場景 | `.glb`／`.gltf` | REVIEW_REQUIRED | PROPOSED |
| 空間 manifest | JSON | 結構可公開；真實場域內容須審查 | PROPOSED |
| 影片 manifest | JSON／JSONL | Schema 可公開；真實紀錄預設私人 | PROPOSED |
| 事件紀錄 | 交換用 JSONL | Schema 可公開；真實紀錄預設私人 | PROPOSED |
| 證據 manifest | JSON／JSONL | 真實紀錄預設私人 | PROPOSED |
| JSON Schema | JSON | 不含真實資料時 PUBLIC_ALLOWED | PROPOSED |

分類取決於內容，不取決於副檔名；加入實際資料前須依
[發布政策](08_Repository_and_Data_Publication_Policy.md)審查。

### 共用紀錄外框

跨模組候選欄位包括 `schema_name`、`schema_version`、`record_id`、
`record_kind`、`created_at`、`producer`、`provenance` 與
`quality_flags`。命名空間、ID 格式、schema registry 與相容政策仍為
整體 `OPEN`；下方已確認的 `school` Blender 物件識別契約是限定範圍的例外，
不代表其他 record type 已定案。

### 時間表示

- 使用含明確 offset 的 RFC 3339；來源時鐘允許時，交換資料正規化為 UTC。
- 保留原始 clock source、time base、同步方法與不確定性，不假裝精度更高。
- Frame index 使用整數，並明確定義是否從零開始。
- 可變影格率影片不得只靠名義 frame rate 推導權威時間。
- 必要時分開事件時間與紀錄處理時間。

Event interval 開閉、跨相機權威時鐘、漂移／同步誤差，以及 frame index、
PTS、UTC 的權威組合都維持 `OPEN`。

### Blender 與空間資料

使用 Blender 檔前，盤點：

- 環境 ID、來源別名、checksum 與空間模型版本；
- Blender／exporter 版本、檢查日期與檢查者；
- unit system、unit scale 與獨立驗證的實體比例；
- 原點、handedness、up／forward 軸與 canonical transform；
- Collection／Object 的穩定 ID、用途、父子關係、transform 與匯出規則；
- Zone ID、名稱、邊界、相鄰關係與版本；
- Camera ID、投影、transform、lens／FOV、校正來源與 stream ID；以及
- 真實場域、限制區域及攝影機位置的敏感性。

Blender 顯示單位本身不能證明實體比例。相機資料可評估 focal length、
水平／垂直 FOV、sensor size／fit、render size、lens shift、clip distance、
intrinsic matrix、distortion、校正日期／證據與 zone 關聯；視覺對齊不能
冒充真實校正。

#### 已確認的 school 物件識別契約

`school` Blender 物件識別契約為 `amidst.school.object-id/1.0.1`；canonical
base fingerprint 與一般 ID derivation 維持 `1.0.0`：

- 權威 namespace UUID：`1601a7c1-19ac-555d-9962-05e4503ac6bd`；
- 識別碼格式：`amidst:school:object:<uuid-v5>`；
- UUID 輸入為 policy 的 canonical SHA-256 identity fingerprint，字串格式是
  `amidst.school.object-id/1.0.0:<fingerprint>`；
- canonical encoding 採 Unicode NFC UTF-8 字串、有限 float 的小寫
  `float.hex()` 字串、明確 null、確定性 array；JSON key 依 Unicode code
  point 排序，不含無意義空白及結尾換行；
- `school_v1` 適用型別為 `MESH`、`ARMATURE`、`CURVE`、`EMPTY`、
  `CAMERA`、`FONT`，並使用 ADR-008 核准的各型別 signature；
- object name 不得參與 fingerprint 或 UUID 產生；
- 重複 fingerprint、重複 ID、歧義、不支援型別與非確定性都是致命驗證
  結果；以及
- canonical registry path 為
  `data/annotations/instance_registry/school.json`。

`school_v1` 修正新增兩個 canonical、場景版本限定 input：

- `school_v1_disambiguation.json` 保存五筆已核准的
  `hierarchy.child_fingerprints` 紀錄；
- `school_v1_identity_bootstrap.json` 保存 131 筆已審閱 opaque mapping；
  discriminator 格式固定為 `bootstrap:` 加三位 ASCII 十進位數字，並在各
  duplicate-fingerprint group 內唯一。

Bootstrap locator 只在建立與序列化初始明示 mapping 時以 NFC UTF-8 排序，
locator 文字不進入 resolved-identity payload。Resolved fingerprint 是恰含
`base_fingerprint`、`disambiguation_method`、`disambiguation_token` 的
canonical JSON 之 SHA-256；UUIDv5 使用不變的
`amidst.school.object-id/1.0.0:<resolved-fingerprint>` name。紀錄缺漏或衝突
都會使指派無效。Imported saved-view camera
`skp_camera_Last_Saved_SketchUp_View` 是 policy 1.0.1 明確 eligibility exclusion，
Blender 場景內的 camera 本身維持不變。

Registry identity record 具有權威性且需版本化；Blender `instance_id` custom
property 只是鏡像，不是獨立 identity record。Registry 使用 canonical
serialization，確定性 identity 內容不含執行 timestamp。已退役 ID 永久保留
tombstone，不得重用。

#### 已確認的 school_v1 首批資料契約

以下產物在 `school_v1` 首批合成資料的限定範圍內為 `CONFIRMED`；其 Git 發布
分類仍為 `REVIEW_REQUIRED`，技術確認不等於授權發布：

- `data/annotations/semantic/school_v1_semantic_baseline_v0_1_0.json` 讓所有
  未審閱實體維持 `Unknown`／`needs_review`，並列出未來人工審閱紀錄的必要
  欄位；schema／annotation 版本為 `0.1.0`／`school.v1.semantic/0.1.0`；
- `data/metadata/first_dataset_slice_tasks_v0_1_0.json` 定義七個 canonical
  task identifier、物件 eligibility、空間／visibility 版本、tolerance、tie、
  invalidation 與輸出命名，契約為
  `amidst.school.first-dataset-slice/0.1.0`；
- `data/metadata/first_dataset_slice_metadata_schema_v0_1_0.json` 規定
  `metadata.json` 承載場景 checksum、camera pose／intrinsics、visible ID、
  距離、關係、task answer、validity 與 provenance 的權威資料；以及
- `data/metadata/first_dataset_slice_render_config_v0_1_0.json` 將場景現值、
  Blender 5.2.1 build、EEVEE、輸出、色彩、seed、平台與 camera 設定鎖定在
  `amidst.school.first-slice-render/0.1.0`；以及
- `data/metadata/first_dataset_slice_render_resource_policy_v0_1_0.json` 記錄
  `amidst.school.texture-agnostic-render/0.1.0`、source／input／derived checksum、
  neutral material override、保留的 unavailable legacy resources、核准的
  datablock changes 與 `authoritative_visual_fidelity = false`。

權威 schema ID 為 `amidst.first-dataset-slice.metadata/0.1.0`，輸出 dataset
version 為 `school_v1_first_slice_v0_1_0`。目錄採從零開始的六位數
`frame_000000`，寫入後不可覆寫，失效樣本證據另行保存。不論契約狀態是否
已確認，完整 readiness report 未達零 blocker 前，generator 都不得執行。
此政策的資源 gate 是「approved render policy 所需資源無未解項目」。歷史
image datablock 可維持 missing，但必須保留、記錄，且 active overridden render
path 不可到達它們。

`PROPOSED`：以 glTF 2.0 作為 runtime geometry 候選，Amidst 語意放在
有版本的 sidecar manifest。glTF 2.0 使用右手座標、線性單位為公尺、角度
為弧度。Blender custom properties 可匯出到 glTF `extras`，但該欄位沒有
專案 schema，因此需驗證軸向／單位轉換、node transform、camera、material、
visibility 與比例，跨檔引用使用穩定 ID，custom property 採 `amidst_*`
前綴，並保存來源與匯出 checksum。正式匯出格式與權威中繼資料位置仍
`OPEN`。

### 影片與 Stream 中繼資料

影片檔與 manifest 分開。候選欄位包括：

- `video_id`、`camera_id`、`stream_id`；
- 不含私人 URL 的 `media_ref` 及 `content_hash`；
- container、codec、width、height、pixel format、color space；
- rational frame rate、variable-rate 標記、time base、frame count、duration；
- start time、clock source、dataset version、scenario ID；以及
- 擷取、清理、轉碼與衍生 provenance。

無法取得的 metadata 應明確標為 unknown，不得猜測。

### 影片事件紀錄

`PROPOSED`：交換事件使用可獨立讀取的 JSON object；需要附加或串流時，
JSONL 是候選。事件欄位包括：

- event ID、event type 與詞彙版本；
- source kind：annotation、prediction、derived 或 human confirmed；
- start／end time 與 start／end frame；
- video、camera、track、entity 與 zone 參考；
- confidence 的值、生產者、語意與校正依據；
- evidence references、provenance、attributes 與 quality flags。

英文段落中的 JSON 僅為合成結構範例；欄位名稱、interval 語意與詞彙都
不是已確認契約。

### Detection、Track 與 Evidence

```text
Video／Observation -> Detection -> Track -> Event -> Evidence
-> Retrieved Result -> Agent Interpretation
```

Detection 至少連回影片／觀測、frame／timestamp、類別、geometry、
confidence 與模型版本；Track 連回 Detection、生命週期、身分範圍與 tracker
版本；Evidence 連回來源紀錄、授權媒體片段、時空範圍、衍生與遮蔽資訊。
共用單一 envelope 或拆成多個 schema 仍為 `OPEN`。

### OpenLABEL 候選相容性

ASAM OpenLABEL 1.0 提供多感測器標註與情境 tagging 的 JSON Schema，包括
streams、coordinate systems、frames、objects、actions、events、contexts、
relations 與 frame intervals。

`PROPOSED`：設計自訂格式前先做小型 fit assessment，比較 Camera／video
與 Streams、逐影格資料與 Frames、Detection／Track 與 Objects、活動與
Actions／Events、空間與 Coordinate Systems、實體關係與 Relations。

是否採用、只取子集或自行設計 Amidst schema，必須評估監控事件語意、
隱私、工具支援、轉換成本與複雜度，並經人工確認及 ADR。

### 驗證、待決事項與驗收

候選驗證層包括 JSON／JSONL 語法、JSON Schema、ID 引用、時間順序與範圍、
座標／單位／transform、provenance、發布分類，以及只使用合成或核准清理
資料的 fixture。此文件不選擇驗證依賴。

MVP 實體、schema 主責與相容政策、OpenLABEL 採用、事件詞彙與區間語意、
權威時鐘、空間中繼資料位置及證據鏈全部維持 `OPEN`。

- [ ] 必要型別只涵蓋核准 MVP 與評估需求。
- [ ] Schema 主責與相容政策已確認。
- [ ] 時間、單位、座標、不確定性與 provenance 可測試。
- [ ] 標註、預測、衍生與人工確認保持分開。
- [ ] 外部格式已有 fit assessment 與 ADR。
- [ ] 實際資料已有核准的儲存庫分類。
- [ ] 範例是合成資料，或已明確審查及清理。

### 參考資料

- [Blender：Scene Properties 與 Units](https://docs.blender.org/manual/en/5.0/scene_layout/scene/properties.html)
- [Blender Python API：Camera](https://docs.blender.org/api/5.0/bpy.types.Camera.html)
- [Blender：glTF 2.0 匯入／匯出](https://docs.blender.org/manual/en/5.0/addons/import_export/scene_gltf2.html)
- [Khronos glTF 2.0 規格](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- [ASAM OpenLABEL](https://www.asam.net/standards/detail/openlabel/)
