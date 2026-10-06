# Phase 1 geometry authority / 場景物理權威

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

本輪從穩定 checkpoint `51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e`，
在 `phase1/geometry-authority` 建立可重驗的幾何 evidence 與
[唯讀 provider](GEOMETRY_PROVIDER.md)。目前 **physical / collision validity = PROVISIONAL**。
[完整分類報告](../data/scene_audit/phase1_geometry_authority_20261006/authority.md)
保留每個 patch 的 source object、位置、檢查及原因；本文件說明使用邊界與重現方式。

最新尺度決策見 [school v3 scale review](SCHOOL_V3_SCALE_REVIEW.md)：使用者明確核准
**1 BU = 0.0247 m**、**APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING**。Mesh 量測只作
sanity-check evidence，不再要求外部尺寸重新推導尺度。新 active
[geometry snapshot](../data/scene_audit/school_v3_approved_scale_20261006/geometry.json) 與
[geometry/scale validation](../data/scene_audit/school_v3_approved_scale_20261006/geometry_scale_validation.md)
使用核准比例；floor、stair、volume、body／clearance authority 仍待核准。
以下分類與舊 snapshot 的 1 m/BU 是 **historical checkpoint evidence**，保留原始 BU
與 provenance，不回寫為新尺度，也不因此升級 physical / collision validity。

### Authority 層級

| 狀態 | 使用含義 |
| --- | --- |
| APPROVED | 明確、source-bound 的人工核准；semantic role 與 physical geometry 分別核准 |
| HIGH_CONFIDENCE | 實際幾何符合固定規則，仍未獲完整人工物理核准 |
| HUMAN_REVIEW | 語意、支援幾何、連接、尺度、opening 或 clearance 證據未解決 |
| REJECTED | 不接受為自動 WALL／physical input；原始 source faces 及拒絕原因仍保留 |

`APPROVED` obstacle role 不會把 footprint 變成已核准的立體 collider。
也不因讀取 snapshot 而提升 authority。正式 consumer 必須先通過 provider 的
`require_approved_physics(floor_id)`；`physical_complete=false`、floor／scale 或 collider
尚待核准時會明確拒絕。空 collider query 不表示空間無碰撞。

### 本輪結果與 hard constraints

原始 **81 HIGH_CONFIDENCE seeds + 1,491 HUMAN_REVIEW patches** 共 1,572 個：

| 最終分類 | 數量 |
| --- | ---: |
| APPROVED | 0 |
| HIGH_CONFIDENCE | 73 |
| HUMAN_REVIEW | 1,422 |
| REJECTED | 77 |

70 個 seeds 保留、11 個降級，原 review 新升級 3 個。五個 seeds 有連續 WALKABLE
穿入，六個缺少足夠的實際平行面 support。分類使用 verticality、height、continuity、
extent、AREA／WALKABLE／PORTAL 關係；不從 `group_*`、`Cube.*` 名稱決定角色。
Window、door panel、decoration 等歧義保留 HUMAN_REVIEW。

原始 `extraction-v1` 候選參數與 threshold policy 維持不變，改動 policy 即拒絕。
AREA／WALKABLE proximity 從 audit 的實際同樓層幾何重算，不信任 legacy nearby lists。
實際 triangles、planar unions 與連續
intervals 取代可能漏掉局部穿入的 sampling 或跨洞 bounding intervals；不以 rectangle、
convex hull 或 AABB 填滿 source mesh holes。**全部 28 PORTAL 都受 hard protection**，
沿用原 `portal_padding=0.28`，包含 triangle 完全落在 aperture 內、交叉及 boundary contact。
檢查不因 declared floor 不同而略過實際接觸；77 patches 被拒絕，accepted contacts 為 0。

19 OBSTACLE 的 movement blocking／visibility occlusion roles 均 APPROVED，
實際 footprint／open-surface physical geometry 均 HUMAN_REVIEW，沒有補造高度。
WALKABLE overlap 超過既有 contact ratio `0.01` 為 0 pairs；PORTAL 衝突有 8 pairs：
四個廁所門、主入口兩個 obstacle、2F MEETINGROOM 兩個門。
這是 footprint／vertical-contact 診斷，並非已完成 3D collision 或 occlusion certification。

Stair A/B 各有 ENTRY → PATH → EXIT 與 1F → 2F／UP metadata，但 PATH 各含兩個
disconnected surface components。最近實際 3D surface gaps 分別為 **4.769402／4.896199**；
它們與 annotated centerline joins 約 57.58／57.55 不同。A ENTRY／EXIT 和 B EXIT
尚未接到 declared-floor WALKABLE；landing、slab opening、clearance 均 HUMAN_REVIEW。
本場景只有樓梯，沒有電梯；未生成跨層 connector。

### 來源、尺度與重現

來源為 `blender/school_v3.blend`，SHA-256：
`cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`。
本輪 export／review 不 save、render 或修改 `.blend`。World-space source vertices 與
triangle connectivity 原樣保留；geometry provider 不需要 `bpy`。

Historical checkpoint 的 1 Blender unit = 1 公尺與 `scale_authority=HUMAN_REVIEW`
只描述原輸出，不是目前 architectural scale authority；舊 artifact 與來源 geometry
均不 rescale。目前核准比例為 0.0247 m/BU。Floor planes 仍需核准：WALKABLE Z=25／165 BU
與 actual mesh floor candidates 約 20.07885／161.81110 的差異要由人工確認。

從 repository root 執行下方入口，使用新的暫存輸出目錄；CLI 拒絕覆寫既有 artifact。
目前 school-v3 config 使用核准尺度，因此會產生新尺度 review；若要 exact replay
historical checkpoint，須使用該 checkpoint 的 code 與 config，不能用目前設定宣稱
重現舊 hashes。這只重算幾何 review，不執行 benchmark、Graph、ranking 或 GT inference：

```sh
geometry_review_output=$(mktemp -d "${TMPDIR:-/tmp}/amidst-geometry-authority.XXXXXX")
uv run python -m amidst.geometry_authority \
  --candidates data/scene_audit/phase1_wall_candidates_20261005.json \
  --meshes data/scene_audit/phase1_geometry_authority_20261006/wall_meshes.json \
  --audit data/scene_audit/school_v3_semantic_audit.json \
  --config configs/scene_validation_school_v3.json \
  --expected-source-sha256 cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e \
  --obstacle-authorization data/scene_audit/phase1_geometry_authority_20261006/role_authorization.json \
  --baseline-git-commit 51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e \
  --output "$geometry_review_output"
```

輸出 `authority.json`、`authority.md`、`geometry.json`、`manifest.json`。
[Manifest](../data/scene_audit/phase1_geometry_authority_20261006/manifest.json)
記錄 input content hashes、artifact hashes 及 exporter／review／provider code hashes；
mesh evidence 同時綁 `candidate_content_sha256` 與 `audit_content_sha256`；
read-only exporter 明確接收 `--audit`。Caller 必須獨立核對 source SHA，
source、content、authorization scope 不相符即拒絕；approval ID 不是數位簽章。
比較同一輸入／程式下的分類、geometry、reason codes 與 binding，不把 temporary path
或執行時間當成研究語意。

### 升級 physical authority 前的人類工作

- 審查剩餘牆／窗／門片／裝飾物角色，確認十一個 seed 的幾何邊界及整體牆體完整性。
- 修正廁所、主入口、2F MEETINGROOM 的 obstacle／PORTAL 衝突；保留 19 個 BOTH roles。
- 補充或確認 obstacle 的 source-bound 3D height／volume 與 visibility evidence。
- 核准 floor authority 與 physical clearance／contact policy；architectural scale 已核准。
- 提供 stair landing、入口／出口接地、slab opening／clearance 的完整幾何與核准證據。

本輪沒有修改正式 Phase 1 schemas、benchmark semantics、ranking 或 GT isolation，
也未開始正式 benchmark、Graph／collision integration、Agent 或 Phase 2。

## English

The [school-v3 scale review](SCHOOL_V3_SCALE_REVIEW.md) records explicit user approval of
**1 BU = 0.0247 m**, **APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING**. Mesh measurements are
sanity-check evidence, with no external-dimension requirement to rederive the declared scale.
New active geometry and scale validation live in `school_v3_approved_scale_20261006`.
The classification results and 1 m/BU values below describe historical checkpoint evidence;
historical BU/provenance are preserved. Floors, stairs, volumes and body/clearance policy
remain pending, so overall physical/collision validity stays PROVISIONAL.

Branch `phase1/geometry-authority` starts from checkpoint
`51f1ec7c34b8766b44ce2bb2ba98bdb8c9ca321e`. The
[read-only provider contract](GEOMETRY_PROVIDER.md) and
[per-patch report](../data/scene_audit/phase1_geometry_authority_20261006/authority.md)
support source-bound review. **Physical / collision validity remains PROVISIONAL.**

APPROVED records explicit human approval separately for semantic roles and physical geometry.
HIGH_CONFIDENCE records geometry satisfying fixed rules without full human certification.
HUMAN_REVIEW retains unresolved semantics, geometry, connectivity, scale, opening or clearance.
REJECTED excludes unsafe candidates from automatic wall/physical installation while preserving
their source faces and reasons. Loading never upgrades authority. Formal consumers must use
`require_approved_physics(floor_id)`; incomplete physical scope or unresolved authority fails
closed. An empty collider query does not establish collision-free space.

The 81 seeds plus 1,491 reviewed patches become **0 APPROVED, 73 HIGH_CONFIDENCE,
1,422 HUMAN_REVIEW, 77 REJECTED**. Seventy seeds remain, eleven are downgraded and three
reviewed patches are promoted. Five seeds intrude into WALKABLE interiors; six lack sufficient
actual parallel-face support. Classification uses geometric and AREA/WALKABLE/PORTAL evidence,
not object-name guesses. Ambiguous windows, panels and decoration remain HUMAN_REVIEW.

Original `extraction-v1` parameters and threshold policy remain frozen; policy changes are
rejected. Same-floor AREA/WALKABLE proximity is recomputed from actual audit geometry rather
than trusted legacy nearby lists. Exact triangles, planar unions and
continuous intervals avoid sampling misses or artificial support across openings. No rectangle,
convex hull or AABB infill replaces source collider geometry. All **28 portals** receive hard
protection with the original `0.28` padding, including enclosed triangles, intersections and
boundary contact. Incorrect floor labels cannot bypass real aperture contact. Seventy-seven
patches are rejected; accepted contacts are zero.

All **19 obstacle roles** are APPROVED for movement blocking and visibility occlusion;
their physical footprints/open surfaces remain HUMAN_REVIEW, without height extrusion.
No WALKABLE overlap exceeds the existing `0.01` contact ratio; eight portal pairs conflict:
four bathroom doors, two main-entrance obstacles and two 2F meeting-room doors. These footprint
and vertical-contact measurements do not certify full 3D collision or occlusion behavior.

Stairs A/B have ENTRY/PATH/EXIT and 1F→2F/UP metadata but each PATH has two disconnected
components. Closest actual 3D gaps are **4.769402/4.896199**, distinct from the approximately
57.58/57.55 annotated centerline gaps. A entry/exit and B exit lack declared-floor WALKABLE
contact. Landing, opening and clearance remain HUMAN_REVIEW; no cross-floor connector is
invented. The scene has stairs and no elevator.

The source SHA and shared replay command above bind this review to `school_v3.blend`.
Export/review preserves the asset without save or render. Exact world-space vertices and
triangle connectivity are portable without `bpy`. Historical outputs preserve their
**1 Blender unit = 1 metre** calculation convention and pending-scale status; these are
not the current authority. New active outputs use approved **0.0247 m/BU** without scaling
source geometry. Floor
authority must reconcile WALKABLE Z=25/165 with mesh floor candidates around 20.07885/161.81110.

The entry point above with the current config produces a new approved-scale review. Exact
historical replay requires the checkpoint's own code and config; current settings do not
reproduce old artifact hashes. Replay into a fresh temporary directory creates
`authority.json`, `authority.md`,
`geometry.json` and `manifest.json`. The manifest binds input, artifact and code hashes;
mesh evidence binds both `candidate_content_sha256` and `audit_content_sha256`, and the
read-only exporter explicitly requires `--audit`. Callers independently verify source SHA;
mismatched source/content/authorization scope is rejected. Approval IDs are traceable review
identities, not cryptographic signatures. Reproducibility concerns classifications, exact
geometry, reasons and bindings, excluding temporary paths and execution timing.

Before physical approval, humans must resolve remaining wall/window/panel roles and downgraded
seeds, confirm geometry completeness, reconcile obstacle/portal conflicts while retaining BOTH
roles, supply obstacle 3D/visibility evidence, approve floors and physical contact/clearance
policy, and provide stair landing, endpoint, opening and clearance evidence. This work does not
change formal Phase 1 schemas, benchmark semantics, ranking or GT isolation and does not start
formal benchmarking, Graph/collision integration, Agent work or Phase 2.
