# Scene geometry provider / 場景幾何介面

## 繁體中文

`amidst.scene_geometry` 是新增的唯讀幾何 sidecar 契約。Blender adapter 匯出
world-space vertices 與原始 triangle connectivity；provider 不匯入 `bpy`，
不讀 Ground Truth，不修改既有 Observation、Graph、ranking、MetricConfig 或 benchmark。
現有 mock 可建立同一 snapshot；來源名稱不決定 semantic role。

### Authority 與實際幾何分開

| Status | 意義 |
| --- | --- |
| APPROVED | 有明確 `approval_id`、可追溯 evidence 的人工核准 |
| HIGH_CONFIDENCE | 幾何證據達既定分類規則；尚不是人工核准 |
| HUMAN_REVIEW | 語意、連接、physical support 或 authority 仍待確認 |
| REJECTED | 該候選未被接受；保留診斷證據，不作正式 collider |

每個 surface 分別記錄 `semantic_authority`、`physical_authority`、`support`。
已核准的 OBSTACLE role 可以同時是 `FOOTPRINT` 與 physical `HUMAN_REVIEW`；
`blocks_movement`／`occludes_visibility` 是 role policy，不會補造 height 或 volume。
`FOOTPRINT`／`ANNOTATION` 不可宣稱 physical APPROVED／HIGH_CONFIDENCE。
`VOLUME` 要有一致 winding、封閉 two-manifold edges 與非零 signed volume；
這些 guards 不自動批准 clearance，也不宣稱已排除所有 mesh self-intersection。

Floor plane 各自保留 authority，宣告 `unit_scale_m` 與 `scale_authority` 也分開。
沿用既有 conversion 不代表本次批准 physical scale。Physical APPROVED surface
必須引用 APPROVED floor，且 scale 也已批准。`physical_complete=true` 在 floor、scale、
相關 surface、portal 或 stair authority 未解決時會 fail fast；預設為 false。

### Snapshot 與載入

`schema_version="scene-geometry-v1"` 包含以下 frozen／strict models；這是 additive
geometry sidecar，沒有改寫正式 Phase 1 domain schemas。

| Model | 主要內容 |
| --- | --- |
| `SceneGeometrySnapshot` | scene ID、來源 SHA-256、declared units、authority、doorway tolerance |
| `FloorAuthority` | floor ID、plane point／unit normal、authority、evidence／approval IDs |
| `GeometrySurface` | source object／face refs、role、floor IDs、exact vertices／triangles、兩種 authority |
| `PortalGeometry` | actual aperture surface、floor、已知 WALKABLE refs、authority |
| `StairGeometry` | from／to floor、ENTRY／EXIT points、actual PATH refs、connectivity／opening／clearance authority |

Finite coordinates、triangle indices、nondegenerate triangles、unique IDs、role／floor
references 都會驗證。ANNOTATION points 可以沒有 triangles；它們不成為 physical collider。
未知欄位（包括 GT、Blender objects、假造的 protection flag）被拒絕。Python caller
經 `model_construct`／unchecked `model_copy` 建立的模型，provider construction 仍重新驗證。

```python
from pathlib import Path
from amidst.scene_geometry import ReadOnlySceneGeometryProvider

provider = ReadOnlySceneGeometryProvider.from_json(
    Path("scene_geometry.json"),
    expected_source_sha256=independently_verified_source_sha256,
)
walkable = provider.get_walkable("1F")
walls = provider.get_walls("1F")
obstacles = provider.get_obstacles("1F")
portals = provider.get_portals("1F")
stairs = provider.get_stairs()
floors = provider.get_floors()
approved_colliders = provider.get_colliders("1F")
```

Caller 必須提供獨立核對的來源 SHA；provider 核對 binding，**不自行讀 `.blend`**。
Sidecar status 與 approval ID 必須來自受信任的 review/export 流程；此介面沒有以字串
取代人工批准，也不是 approval signature system。資料讀取不需 Blender。

Queries 回傳按 deterministic ID 排序的 immutable tuples，未知 floor 明確報錯。
一般 getters 保留 REVIEW／REJECTED 診斷；`get_colliders` 預設只選 physical APPROVED，
必須顯式指定 `authority=Authority.HIGH_CONFIDENCE` 才會查詢該 evidence level。
目前 school snapshot 的 physical REVIEW 不會因載入而變成正式 collider。

`get_colliders` 只是 inspection filter，空 tuple **不代表空間 collision-free**。
正式 physical consumer 必須先呼叫 `require_approved_physics(floor_id)`；snapshot
`physical_complete=false`、floor／scale 未核准或 collider 尚待審查時，會拋出 typed
`GeometryAuthorityError(ValueError)`，附 deterministic `reasons`。通過後回傳
APPROVED collider input；consumer 仍需執行 route／segment／clearance validation，
這個 gate 本身不判定任何 path 無碰撞。
每個宣告 complete 的 floor 都必須有實際 APPROVED WALKABLE surface；只有 floor／scale
批准而 surface 為空，不能以空集合邏輯宣稱 physical scope 完整。

### Doorway protection 是 hard guard

所有 semantic APPROVED／HIGH_CONFIDENCE WALL，載入時都重新對每個明確 PORTAL
執行 protection，不信任 caller 提供的「無衝突」宣告。Protection aperture 是
PORTAL exact vertices 的保守 box，加上明確 `portal_protection_tolerance_m`；
以 actual wall triangles 裁切，包含 enclosed triangle、跨面交叉、線／點 boundary contact。
Declared floor label 不可略過實際 Z／XY overlap；只有 geometry disjoint 才能排除 contact。

Protection box 僅用於禁止封門。WALL／OBSTACLE collider 仍是 exact source triangles，
不建立 AABB／convex hull collision fallback，不填補 triangle holes，也不把兩段 stair
PATH 自動連起來。Conservative contact 造成 explicit rejection，交給 review；不放寬 threshold。

Exporter 可共用 `clip_triangle_to_box`、`promoted_wall_portal_conflicts`；
`triangle_distance`／`surface_distance` 是 actual-triangle helpers。
Provider 沒有實作 Graph search、ranking、final route validation 或新 metric semantics；
後續 consumer 必須保持目前 GT isolation 與既有研究閾值。

### Physical authority resolution 與用途 scope

`amidst.physical_authority` 另提供 `physical-authority-v1` sidecar 與
`ReadOnlyPhysicalAuthorityProvider`，保持 `scene-geometry-v1` 不變。
它同時綁定獨立核對的 source SHA 和 geometry snapshot canonical SHA；後者取自
validated model JSON，以 sorted keys／compact separators 計算 SHA-256，與 JSON 空白
或輸出目錄無關。重新標示 authority、修改 vertices 或新增 surface 都會改變 binding。
這個 wrapper 重驗 nested frozen models，不能以 unchecked `model_copy` 偷渡批准。

`PhysicalPolicy` 的 metre 參數均由 config 明確提供；目前未定義的項目保留 `null`
與 `HUMAN_REVIEW`，不以預設人體大小或診斷 tolerance 補值：

- body radius、total height、body clearance 分開。
- portal horizontal clearance、vertical clearance 分開。
- collision contact tolerance 與 numerical epsilon 分開；policy 不接受 numerical epsilon。
- body model（upright cylinder／capsule）與 trajectory 的 floor-contact reference 明列。
- clearance 的 minimum inclusive／exclusive，以及 collision 的 contact inclusive／exclusive
  比較方式由 policy 明列；wrapper 不替現有 MetricConfig 重定義邊界。

APPROVED policy 必須有全部參數、comparison、`approval_id` 和 evidence。
Capsule height 包含兩個半球；body radius／height 必須正值，clearance／contact tolerance
可明確設定為零。Wrapper 本身只提供核准 policy，不執行人體或 segment collision。

每個 `PhysicalScope` 明列 exact surface／portal／stair IDs、floors、用途、coverage、
authority 及尚未解決的原因。不能用一個「物理有效」布林值涵蓋不同用途：

| Purpose | 核准範圍 | 可宣稱的結果 |
| --- | --- | --- |
| `KNOWN_COLLISION_PRUNING` | 可為 PARTIAL；實際 collider、floor、scale、policy 均已核准 | 可對已知 collider 做正向碰撞拒絕；不認證其他位置無碰撞 |
| `COLLISION_FREE_VALIDATION` | COMPLETE 且相關幾何／門洞／樓梯均核准 | 提供完整已核准 input；consumer 仍需檢查 route |
| `TOPOLOGY_VALIDATION` | COMPLETE 且 WALKABLE、相關 PORTAL／STAIR 核准 | 提供 topology 檢查 input；不自動造 adjacency／landing |
| `PHYSICAL_VALIDITY_METRICS` | COMPLETE 且幾何與 policy 核准 | 提供正式 physical-validity metric input；不改 metric semantics |

APPROVED obstacle scope 必須引用 actual closed `VOLUME`，role-approved footprint 不足。
HIGH_CONFIDENCE WALL 仍保留 HIGH_CONFIDENCE，只能顯式讀取 provisional evidence；
不能因需求需要 pruning 而轉成 APPROVED。Complete scope 不能略去該 floor 的已知
non-REJECTED WALKABLE／WALL／OBSTACLE、PORTAL 或相關 STAIR；尚未核准的項目會拒絕
formal consumption。沒有任何 scope 核准時為 `PROVISIONAL`；只有局部 scope 核准時，
整體為 `PARTIAL_APPROVED`；所有 floors 與四種用途都有核准 COMPLETE scope，且原
snapshot 的 `physical_complete=true`，才可宣稱 `APPROVED`。Sidecar 不覆寫全域 incomplete。

`get_scopes(...)` 供診斷；正式 caller 必須明列用途並呼叫 gate：

```python
from amidst.physical_authority import (
    PhysicalPurpose,
    ReadOnlyPhysicalAuthorityProvider,
)

physical = ReadOnlyPhysicalAuthorityProvider.from_json(
    geometry_path,
    resolution_path,
    expected_source_sha256=independently_verified_source_sha256,
    expected_geometry_sha256=independently_verified_geometry_sha256,
)
inputs = physical.require_scope(
    "approved-local-colliders",
    purpose=PhysicalPurpose.KNOWN_COLLISION_PRUNING,
)
```

Gate 回傳 immutable `ApprovedPhysicalInputs`，其中含 policy、scope 和 exact geometry。
未核准／pending policy、scope 未核准、purpose 不符、footprint、HIGH_CONFIDENCE collider、
不完整 coverage 都產生帶 deterministic reasons 的 `GeometryAuthorityError`；沒有 silent
fallback、空 collider certification 或 geometry authority 覆寫。來源 review/export 的
批准 identity 必須由可信外部流程取得；SHA binding 不等於 approval signature。

## English

`amidst.scene_geometry` is an additive immutable sidecar contract, independent of Blender,
GT and existing Phase 1 domain schemas. Exporters retain world-space vertices and exact
triangle connectivity. No wall hull, aperture infill or inferred stair landing is created.

Semantic approval and physical support are separate. APPROVED requires explicit review
identity and traceable evidence; HIGH_CONFIDENCE records rule-supported evidence without
human approval. Footprints and annotations remain physical HUMAN_REVIEW. Floor and scale
authority are independent; incomplete geometry cannot claim `physical_complete=true`.

Loading requires the caller's independently verified source SHA-256. Models reject extra
fields, non-finite/degenerate geometry, invalid references and unchecked Python model
mutations. The provider verifies the source binding; it does not open the Blender asset
or authenticate approval signatures. Review/export provenance must be trusted externally.

Read-only getters return stable ID-sorted tuples. Diagnostic getters retain all statuses;
the default collider query admits only physical APPROVED surfaces. An explicit query is
required for HIGH_CONFIDENCE evidence. No read operation upgrades authority.
An empty inspection result never certifies collision-free space. Formal consumers must
call `require_approved_physics(floor_id)` first: incomplete physical scope, unapproved
floor/scale or unresolved colliders raise `GeometryAuthorityError` with deterministic
reason codes. A successful gate supplies approved collider inputs and still requires
actual route/clearance validation by the consumer.
Every floor in a complete snapshot must contain actual APPROVED WALKABLE support;
approved floor/scale declarations with an empty surface scope cannot claim completeness.

Every promoted WALL is checked against every declared PORTAL aperture volume using actual
wall triangles, including contained surfaces and boundary contact. Incorrect floor labels
cannot bypass real geometry overlap. Conservative portal bounds protect doorways only and
are never used as wall collision envelopes. Thresholds, Graph semantics, ranking and GT
isolation remain unchanged.

The additive `amidst.physical_authority` wrapper binds a `physical-authority-v1` sidecar
to both the independently verified source SHA and the canonical validated geometry-model
SHA. It does not change `scene-geometry-v1`, upgrade provisional geometry, or authenticate
approval signatures. Nested models are revalidated at the provider boundary.

The config-driven policy separates body radius, total height and clearance; horizontal
and vertical portal clearances; and collision contact tolerance. Body shape, floor-contact
reference and inclusive/exclusive comparisons are explicit. Missing values remain null
and HUMAN_REVIEW. Numerical epsilon is not a physical policy substitute. An APPROVED policy
requires all values, comparison choices and traceable approval. No body geometry or route
validation is implemented by this contract, and MetricConfig is unchanged.

Purpose scopes reference exact immutable surface/portal/stair IDs and floors. A PARTIAL
`KNOWN_COLLISION_PRUNING` scope may supply approved colliders for positive rejection only;
it never certifies free space. Approved obstacle inputs require actual closed volumes.
COLLISION_FREE_VALIDATION, TOPOLOGY_VALIDATION and PHYSICAL_VALIDITY_METRICS require COMPLETE
approved scope, including relevant walkable, colliders, portals and stairs. HIGH_CONFIDENCE
walls remain provisional evidence. Getters are diagnostic; formal consumption calls
`require_scope(scope_id, purpose=...)`, which returns approved inputs or deterministic
typed refusal reasons. Consumers still perform actual collision/topology/metric computation.

No approved scope means PROVISIONAL. Some approved scope means PARTIAL_APPROVED. APPROVED
requires approved COMPLETE scope for all floors and all four purposes, plus the underlying
snapshot's `physical_complete=true`; a sidecar cannot overwrite global incompleteness.
Scope completeness cannot omit known non-rejected geometry. No GT, Blender objects,
invented landing or silent fallback enters this platform-neutral interface.
