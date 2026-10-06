# School v3 scale and source review / 尺度與來源整理

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

使用者暫定 **1 BU ≈ 0.0247 m**。目前沒有可靠實測／設計尺寸；本輪只產生
[自動量測表](../data/scene_audit/school_v3_scale_calibration_20261006/measurements.md)、
[source endpoints JSON](../data/scene_audit/school_v3_scale_calibration_20261006/measurements.json)
與 [CSV](../data/scene_audit/school_v3_scale_calibration_20261006/measurements.csv)。
Scale／floor／physical authority 仍 HUMAN_REVIEW，不 rescale／save／render 或改 geometry。

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
建議 anchors 見報告 shortlist；人工需先確認對應室內邊界，再提供至少 2–3 組
獨立真實尺寸。既有比例換算值、相同門型在另一樓層重複，不能用作獨立證據。

### 單位與來源邊界

- 新 [diagnostic config](../configs/school_v3_scale_measurement_v1.json) 保存暫定比例，
  `known_real_dimensions=[]`、`HUMAN_REVIEW`、formal physical use denied。
- 正式 calibration schema 目前是 `meters_per_blender_unit: Literal[1]`；既有 builder、
  floor planes、padding、pilot、benchmark 都有舊單位契約。本輪不修改正式 schema／
  runner／metrics。未來接入比例須另行核准完整換算，不只替換一個 scalar。
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

The user proposes **0.0247 m/BU** for new diagnostics. No reliable measured/design
dimensions are available, so architectural scale remains HUMAN_REVIEW. The immutable
source is surveyed without scaling, geometry changes, saving, rendering or benchmark runs.
JSON/CSV/Markdown are generated from source measurements rather than maintained by hand.

Annotation spans and actual source cross-sections are separate. Portal orientation must
be explicitly declared; unresolved normals remain unresolved. Rays sample 20/40/60 native
units above a horizontal-support candidate and cite evaluated polygon indices, endpoints,
normals and face vertices. Nearest hits retain unassigned semantic roles; they do not certify
walls, aperture, body clearance or connectivity. Summaries use the median of available
samples and preserve incomplete/varying profiles. Floor rise uses source support candidates.

Confirm the shortlisted mesh boundaries and provide at least 2–3 independent real dimensions
before approving scale. Repeated door types and values derived from this proposed ratio are
not independent evidence. Formal calibration currently fixes its unit scalar to one; changing
that contract and converting all planes/tolerances is a separate approved integration task.
Historical pilot/benchmark/provenance artifacts remain unchanged.

The imported SketchUp camera has zero active consuming references and can be ignored while
retaining the source object and all 29 research CAM cameras. Elevator is NOT_APPLICABLE;
historical AREA IDs remain and no elevator transitions are created. Preserve all unclassified
objects without assigning roles from names. Future references use canonical paths and hashes;
historical duplicates and source/context provenance are retained. The replay above writes only
to a fresh directory.
