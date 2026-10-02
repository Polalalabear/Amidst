# School semantic integration gate / 場景語意接入條件

2026-10-02 live read-only evidence:
[school_v2_semantic_audit.json](school_v2_semantic_audit.json).
Source `blender/school_v2.blend`, SHA-256
`1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38`.

## 繁體中文

本次 Blender 5.2.1 LTS audit 在來源保存的 frame 220／subframe 0 讀取全部
2,796 objects、2,652 meshes、29 collections。原 `.blend` 的 SHA-256、大小、mtime
在執行前後相同；沒有 save／render，也沒有對 `group_*`／`Cube.*` 猜測物理角色。

| 明示名稱標記 | Objects | Collections | 權威狀態 |
| --- | ---: | ---: | --- |
| AREA_* | 30 | 0 | annotation；不是 walkable surface |
| PORTAL_* | 28 | 0 | annotation；不是合法連通或 collider 證明 |
| WALKABLE_* | 0 | 0 | 沒有可信表面 |
| WALL_* | 0 | 0 | collision／occlusion ownership 未指定 |
| OBSTACLE_* | 0 | 0 | collision／occlusion ownership 未指定 |
| STAIR_* | 0 | 0 | 沒有可信 entry／path／exit |
| CAM_* | 29 | 0 | 與 portable calibration 的 IDs／world matrices 相符 |

場景另有一個非研究用 camera、92 EMPTY、2 CURVE、1 FONT、1 ARMATURE、18 LIGHT。
每個 object／collection 都列出 semantic class、floor、bounding box、centroid、mesh
statistics、candidate role、confidence／trusted status。Mesh bounds 是 evaluated world
vertices 的 AABB；centroid 是 vertex arithmetic mean，不是體積／面積重心。
空 mesh 和非 surface objects 的 origin fallback 明示為非幾何；collection bounds
僅彙總 members，不能用作 navigation surface 或 collider。

所有 physical roles 仍是 unreviewed。名稱中的 1F／2F 只存為 `declared_floor_label`，
`floor` 保持 null；AREA bounding boxes 不決定 floor height。29 個 camera 的 raw
evaluated world matrix 與 `school_v2_calibration_v1.json` 最大差異為 **0**，但這不是
world→image／image→world Projection Error 的量測，也沒有核准 camera→floor plane。
1 Blender unit = 1 metre 沿用既有已確認契約。

結果為 **STOP_REQUIRED_HUMAN_ANNOTATION**，Case 1–3 尚未具備 physical integration
條件。依使用者 stop conditions，未建立 school topology、collision pruning、GT／
observations、Cases 1–3 benchmarks 或 physical Rerun。正式 schemas、Graph／ranking／
reconstruction／metrics／provider 都沒有修改。

人工確認可以使用綁定上述 source SHA 的 sidecar，不必修改原 `.blend`：

| 必要資料 | 人工確認內容 |
| --- | --- |
| WALKABLE | object IDs／face subsets／approved proxies；floor／zone／region；邊界、holes、doorway connectivity、endpoint anchors |
| WALL／OBSTACLE | collider IDs／approved proxies；floor；movement collision、camera occlusion 或兩者；排除 helper／annotation 的 policy |
| Floor／plane | height、normal、extent；所選 camera→plane binding；courtyard 的獨立高度處理 |
| Physical policy | 人物 collision envelope、minimum clearance、接觸判定與 boundary tolerance；不得以 evaluation tolerance 偷代 inference policy |

此表描述待確認內容，不是已實作的 sidecar schema／loader。後續平台無關 geometry
provider 可採 source/context-bound snapshot，提供 trusted walkable／collider／floor／
adjacency／clearance／segment validation；Blender adapter 負責轉換，Graph 不 import bpy。
正式 Top-K 前 pruning、stationary validation 與獨立 evaluation double-check 仍待實作。
端點接入須保持 PROJECTED evidence，遵守既有 explicit-anchor 契約，不能靜默搬移座標。

Case 4 仍暫緩。現有 `AREA_STAIR01/02` 不是 stair path；未來需人工核准
`STAIR_ENTRY`（1F）、含高度變化與 clearance 的 `STAIR_PATH`、`STAIR_EXIT`（2F）、
合法方向與 floor connectivity，以及實際 floor slab opening。

## English

The live audit inventories all 2,796 objects and 29 collections at the saved scene frame,
without saving or rendering. Source SHA-256, size and mtime are unchanged. There are 30
AREA annotations, 28 PORTAL annotations, 29 research cameras, and no explicit WALKABLE,
WALL, OBSTACLE or STAIR object/collection labels. No unlabeled mesh is assigned a role.

Every row includes bounds, centroid method, mesh statistics, candidate role and trust
status. Name-derived floor labels do not approve floor planes. All 29 camera IDs and raw
world matrices match the portable catalog exactly; this does not measure projection error
or establish a camera-to-ground-plane mapping. The existing 1 metre/unit decision is kept.

The physical integration gate is **STOP_REQUIRED_HUMAN_ANNOTATION**. A source-bound human
annotation must identify walkable regions/connectivity/anchors, movement and visibility
colliders, floor planes/camera bindings, and physical clearance/contact policy. Approved
sidecars can preserve the original asset; no sidecar contract or loader is claimed yet.
School topology, pre-Top-K pruning, Cases 1–3, metrics and physical visualizations remain
unimplemented. Existing inference/evaluation schemas and algorithms are unchanged.

Future geometry integration can use an additive platform-independent snapshot/provider
with a Blender adapter, before-search segment validation and pre-Top-K rejection, plus an
independent evaluation check. Projected coordinates and explicit anchors must be preserved.
Case 4 additionally requires approved stair entry/path/exit, directions and slab openings.

## Replay / 重跑

Use a fresh output path; existing reports are never overwritten by the runner:

```bash
uv run python scripts/run_semantic_audit.py \
  --blender /Applications/Blender.app/Contents/MacOS/blender \
  --output /private/tmp/school_v2_semantic_audit_review.json
```

The audit records source and tool hashes, Blender version/frame, calibration version/hash
and source immutability checks. It records no inferred physical authority or GT input.
