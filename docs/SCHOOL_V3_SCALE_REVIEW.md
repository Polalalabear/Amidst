# School v3 scale and source review / 尺度與來源整理

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

使用者於 2026-10-06 明確核准 **1 BU = 0.0247 m**，architectural scale authority
為 **APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING**。這是研究模型的尺度設定，不是由
mesh 反推的估計值；不再要求外部實測／設計尺寸重新推導比例。既有
[自動量測表](../data/scene_audit/school_v3_scale_calibration_20261006/measurements.md)、
[source endpoints JSON](../data/scene_audit/school_v3_scale_calibration_20261006/measurements.json)
與 [CSV](../data/scene_audit/school_v3_scale_calibration_20261006/measurements.csv)。
量測改列 **sanity-check evidence**；來源 BU 數值與端點保留，meter 值依核准比例換算。
Floor、stair、obstacle volume 與 body／clearance authority 仍各自待核准；尺度核准不會
升級它們。不 rescale／save／render 或改 geometry。

### 量測含義與人工確認

來源為未變更的 `school_v3.blend`，固定 frame/subframe 並核對 SHA／size／mtime。
門洞使用已宣告的水平 normal 決定跨向；無唯一 normal 者列 unresolved，不從 bbox
中挑一個看似合理的尺寸。WALKABLE／AREA 標記尺寸與 actual mesh 截面分列。

實體截面於 source horizontal-support candidate 上方 20／40／60 BU 量測；這些是
診斷取樣高度，不是已核准人體或 clearance policy。BVH 僅讀未分類 source meshes，
排除 semantic annotations 與明列 stair helpers；每個 hit 保存 evaluated polygon
index、世界座標端點／法向與 face vertices。AABB 僅縮小 query 工作量。
最近 source hits 可能是牆、家具或其他 geometry，保持 UNASSIGNED；不能自動當門框。

表內 source length 是可用截面的 median，各高度結果／缺側／不一致皆保留。
這不是全高度 minimum clearance、正式 door aperture 或通行性判定。
Floor height 由兩個 source support candidates 的 Z 差量測，不用標記 25／165 相減。
既有 anchor shortlist 只供核對量測邊界，不再是尺度核准的前置條件。
門洞常見截面約 0.875／1.361／1.750 m、走廊約 3.015–3.598 m、教室約
6.321 × 9.676 m，兩個 source support candidates 的高差約 3.500786 m。
這些支持合理性，沒有用來重新推導或批准比例。

五筆截面需保留 boundary-binding review：1F MEETINGROOM 與兩個 2F MEETINGROOM
PORTAL 約 12.998 m、2F GALLERY PORTAL 約 24.506 m，2F MEETINGROOM X 截面約
0.270 m 且隨高度變化。它們引用的是未分類的最近 source hits，不能宣稱是真實
巨大門洞／極小房間，也不構成尺度錯誤的證據。

### 單位與來源邊界

- [Measurement config](../configs/school_v3_scale_measurement_v1.json) 記錄核准比例與
  approval identity，`known_real_dimensions=[]` 不再阻擋尺度核准；量測不授予其他
  physical authority。
- 正式 calibration schema 目前是 `meters_per_blender_unit: Literal[1]`；既有 builder、
  camera／pilot／synthetic artifacts 的舊單位契約保留。新的 physical-unit adapter
  使用核准尺度一致換算 input 與 physical-unit reporting，保留原始 BU，不把舊資料
  冒充已換算的 meter 值。人體半徑／高度、clearance、門洞寬高、contact tolerance、
  speed 與 ADE／FDE reporting 共用同一尺度；Graph／Top-K、metric 定義與 GT isolation
  保持不變。
  Adapter 是顯式 caller boundary；既有 runner／pilot 不會自動切換單位，接入
  normalization 前仍沿用其 legacy 契約。
- 新 active [geometry snapshot](../data/scene_audit/school_v3_approved_scale_20261006/geometry.json)、
  [physical sidecar](../data/scene_audit/school_v3_approved_scale_20261006/physical_authority.json) 與
  [geometry/scale validation](../data/scene_audit/school_v3_approved_scale_20261006/geometry_scale_validation.md)
  綁定未變來源；舊 checkpoint snapshots、benchmark artifacts 與 BU provenance 不回寫。
- [Camera reference audit](../data/scene_audit/school_v3_scale_calibration_20261006/camera_references.json)
  區分 active consuming references 與 inventory／exclusion／history mentions。
  匯入 camera 可忽略，原物件不刪除；正式 29 CAM cameras 保留。
- 電梯 `NOT_APPLICABLE`，無 elevator topology；`AREA_*_ELEVATOR` 只保留來源 ID。
- 所有 `group_*`／`Cube.*` 保留；僅 exact object／faces source binding 可授予 authority。
- [Canonical reference index](../data/scene_audit/school_v3_scale_calibration_20261006/canonical_references.json)
  記錄 canonical paths、file／content hashes，保留歷史 artifacts 與 provenance。
  Mesh hash 相同不代表 semantic ownership 可合併；不同 ROI context 不丟棄。
- Bounds、centroid、高度、坡度與尺寸從 source 自動產生，不維護手抄副本；本輪未
  量測的項目仍使用其既有 source-bound 報告，不宣稱全部實體 authority 已補完。

### Replay

使用新輸出目錄；既有 reports 不覆寫：

```sh
/Applications/Blender.app/Contents/MacOS/blender \
  --background --factory-startup --disable-autoexec -noaudio \
  blender/school_v3.blend --python-exit-code 2 \
  --python scripts/measure_school_scale.py -- \
  --config configs/school_v3_scale_measurement_v1.json \
  --output /private/tmp/school-v3-scale-review-new
```

Blender 路徑可替換為該平台 executable；不修改原始資產。

## English

On 2026-10-06 the user explicitly approved **1 BU = 0.0247 m** as
**APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING architectural scale authority**. This is a declared
research-model setting, not a mesh-derived estimate. External measured/design dimensions are
no longer required to rederive it. The measurement table is sanity-check evidence; source BU
coordinates and endpoints remain alongside converted metre values. Floors, stairs, obstacle
volumes and body/clearance policy retain their separate pending authorities. The immutable
source is not scaled, changed, saved or rendered, and no benchmark is started.
JSON/CSV/Markdown are generated from source measurements rather than maintained by hand.

Annotation spans and actual source cross-sections are separate. Portal orientation must
be explicitly declared; unresolved normals remain unresolved. Rays sample 20/40/60 native
units above a horizontal-support candidate and cite evaluated polygon indices, endpoints,
normals and face vertices. Nearest hits retain unassigned semantic roles; they do not certify
walls, aperture, body clearance or connectivity. Summaries use the median of available
samples and preserve incomplete/varying profiles. Floor rise uses source support candidates.

The former anchor shortlist now supports boundary sanity review only. Typical measured source
sections are about 0.875/1.361/1.750 m for doors, 3.015–3.598 m for corridors and
6.321 × 9.676 m for classrooms; source-support floor rise is about 3.500786 m. These are
plausibility checks, not the source of authority. Five records retain unresolved boundary
bindings: three meeting-room portal sections near 12.998 m, the gallery portal near 24.506 m
and a meeting-room X section near 0.270 m. Unassigned nearest ray hits do not establish giant
doorways, a tiny room or an invalid scale.

Legacy formal calibration keeps its unit scalar fixed to one for existing camera/pilot and
synthetic artifacts. The physical-unit adapter consistently converts new inputs and physical
reports using the approved factor while retaining native BU; it never relabels historical
coordinates as converted metres. Body dimensions, clearance, portal width/height, contact
tolerance, speed and ADE/FDE reporting share that boundary without changing Graph/Top-K,
metric definitions or GT isolation. New active geometry and physical sidecars are in
`data/scene_audit/school_v3_approved_scale_20261006/`; historical snapshots, pilot/benchmark
artifacts and BU provenance remain unchanged.
The adapter is an explicit caller boundary. Existing runner/pilot flows stay on their
legacy contracts until their caller invokes normalization; they are not automatically migrated.

The imported SketchUp camera has zero active consuming references and can be ignored while
retaining the source object and all 29 research CAM cameras. Elevator is NOT_APPLICABLE;
historical AREA IDs remain and no elevator transitions are created. Preserve all unclassified
objects without assigning roles from names. Future references use canonical paths and hashes;
historical duplicates and source/context provenance are retained. The replay above writes only
to a fresh directory.
