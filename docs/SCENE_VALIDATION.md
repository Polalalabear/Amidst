# Semantic validation / 場景語意完整性檢查

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

此工具是可重複執行的唯讀診斷，輸出 coverage、幾何鄰接、語意衝突與人工 review
queue；不建立 inference navigation、stair edges 或 geometry authority。原始
`blender/school_v2.blend` 不會被儲存或渲染，也不由 `group_*`／`Cube.*` 猜測角色。

### 統一入口

從 repository root 執行：

```sh
uv run python -m amidst.scene_validation \
  --blend blender/school_v2.blend \
  --output data/scene_audit/semantic_validation
```

工具會尋找 PATH 上的 Blender 或 macOS Blender app；也可用 `--blender <binary>`
指定。背景抽取停用 autoexec，檢查執行前後 SHA-256、size 與 mtime；結果寫入指定
stem 的 `.json`／`.md`。同一命令可重新產生這兩份報告；output 不可指向 source、
input、config 或原 audit。人工之後若提供另外的已標記場景，改用其明確路徑，並
重新綁定 authority 的 source hash；舊 source 的 approval 不自動沿用。

Portable snapshot 用 `--input <snapshot.json>` 取代 `--blend`。Snapshot 的 objects
保存 object ID、type、collections、custom properties、bounds、centroid，以及可取得的
evaluated vertices／triangles 和 geometry diagnostics。Synthetic fixtures 與其設定
位於 `tests/fixtures/scene_validation/`，只驗證工具，不批准 school geometry。

### 設定與 authority

[School-v3 config](../configs/scene_validation_school_v3.json) 使用明確核准的
**1 BU = 0.0247 m**、**APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING architectural scale**。
原始 BU vertices／量測保留，meter／square-meter 設定依同一比例換算；既有 diagnostic
heuristics 的 native 幾何比較範圍不因單位更新而放寬。Scale-only checkpoint 的
[scene validation](../data/scene_audit/school_v3_approved_scale_20261006/scene_validation.md) 與
[geometry/scale validation](../data/scene_audit/school_v3_approved_scale_20261006/geometry_scale_validation.md)
引用核准尺度；mesh 量測只作 sanity-check，不要求外部尺寸再次核准。當時 floor planes、
stair／volume／body-clearance authorities 仍待核准；本輪分開核准的 policy 與局部
source support 見下節，不回寫該 checkpoint。
舊 school-v2／mock config 與已完成 reports、benchmark BU provenance 保留原契約；
exact historical replay 須使用該版本的 code／config，不用新設定覆寫舊證據。

[scene_validation_v1.json](../configs/scene_validation_v1.json) 將 coverage thresholds、
距離／高度 tolerances、small islands、contact overlap、tiny／giant geometry、scale 與
geometry complexity budgets 外部化。預設 `coverage_pass_ratio=0.8`，AREA 不要求 100%
coverage。這些是 **diagnostic heuristics**，不等於正式 clearance 或 research targets。
Generic config 的 `minimum_clearance_m=null` 不以其他 overlap tolerance 偷代；
本輪已核准的 physical body／clearance policy 由獨立 source-bound config 提供。

`allowed_floors` 檢查 floor tokens；`expected_collections` 可明列每種 role 允許的
collections。不提供 collection policy 時列 REVIEW，不擅自 rename 或移動物件。
Floor plane 設定按 floor ID 放在 `floor_planes`；只有與 snapshot source SHA 相符、
具有 `status=APPROVED`、`review_id` 與有效 `height_m` 的證據，才可用作已審核的
水平 floor 診斷。Synthetic fixture authority 只能用於標記為 synthetic 的輸入。
未核准或不支援的 plane 仍是 HEURISTIC／REVIEW；名稱與 AREA volume bounds 不決定
floor height。`--audit` 預設讀取原 school semantic audit，只在 source 相符時引用
其中明列的 approved floor evidence，不匯入 unreviewed floor candidates。

### 自動檢查與人工判斷

| 檢查 | 自動診斷 | 仍需人工處理 |
| --- | --- | --- |
| AREA coverage | 同層 overlap／uncovered ratio、nearest WALKABLE、floor／Z offset；PASS／PARTIAL／MISSING／REVIEW | AREA 是否本來就不供行走、門檻是否適用 |
| WALKABLE graph | 幾何鄰接 components、isolated／small islands、large same-floor disconnection、declared endpoint access | disconnected component 是否合理；合法 directed topology |
| PORTAL | proximity、兩側／單側／未連 WALKABLE、floor、collider overlap、orientation | 無明確 normal 或 aperture authority 時的方向／合法通行 |
| STAIR | ENTRY→PATH→EXIT completeness、接 WALKABLE、不同 floors、Z direction、ordered path continuity | clearance／slab opening evidence；合法方向與 topology |
| WALL／OBSTACLE | 超過 contact tolerance 的 WALKABLE overlap、跨 PORTAL、floor、giant／decorative／unrelated geometry | movement／occlusion ownership、3D collision／clearance |
| Naming／collections | duplicate IDs、invalid floor tokens、prefix／collection conflicts、incompatible ownership | 正確命名與歸屬；不自動 rename |
| Geometry | empty／zero-area／invalid bounds／non-finite／extreme scale、duplicates、hidden／disabled、non-manifold、tiny／huge | unsupported／complex representation、修復策略；non-manifold 只 report |

Mesh XY footprints 保留由 triangles 表達的 holes；bounds-only evidence 只用於 broad-phase
並標 REVIEW。此工具不做 swept-body clearance certification、NavMesh 建構、school
floor/stair connectivity approval 或 camera-plane binding。超過幾何 budget 的資料也列
REVIEW，不能以 AABB 靜默代替精確表面而判 PASS。無 STAIR 時正常輸出 MISSING。

人工可以明列 `portal_normal=[x,y,z]`（world coordinates）與 `floor_id`。
Stair 診斷欄位包括 `stair_id`、`stair_role=ENTRY/PATH/EXIT`、ordered
`path_points_m`、`floor_from`／`floor_to`、`direction=UP/DOWN`、
`measured_clearance_m` 與 `slab_opening_review=PASS/FAIL`。這些是輸入證據；沒有獨立
source-bound human review 時，不因物件自己宣告 PASS 而授予 inference authority。
`path_points_m` 明確為 SI；source annotation 的 `path_segment_points_json` 為 native BU，
依 approved scale 換算。本輪 runtime 的 BIDIRECTIONAL travel policy 不會把既有
UP／DOWN 的 Z ordering metadata 變成已核准 connectivity。
未明列的 stair vertex ordering 不自行猜測。

AREA 可在頂層 custom properties 明列 `walkable=false`（boolean）、非空
`exclusion_reason` 與 `semantic_review_id`，表示人工決定不納入行走覆蓋。
Validator 回報 `coverage_status=EXCLUDED`，不產生缺 WALKABLE finding；仍用 WALKABLE
完整 Z extents 與 AREA 高度範圍的 conservative overlap 檢查，避免斜面 midpoint 在
AREA 外而漏報。任何非零 XY 重疊列 HIGH，不用 collider contact tolerance 放寬；
nonplanar／unsupported evidence 列 HIGH REVIEW，不認證 3D collision。缺 floor label
仍須 REVIEW；EXCLUDED 不批准 geometry。一般 AREA coverage 維持原本 midpoint-Z 規則。

跨層 AREA 可明列 `coverage_scope=CROSS_FLOOR`、不同且合法的 `floor_from`／`floor_to`、
非空 `stair_id` 與 `semantic_review_id`。其 coverage 為 `NOT_APPLICABLE`、status 為
`REVIEW`，引用對應 stair group 的診斷；沒有對應 group 仍列 HIGH。僅對完整有效的
跨層宣告，不再因缺單一 floor label 或名稱中的 `STAIR` token 報錯，不替它選定單一
floor，也不消除其他 role／collection 衝突。實際 ENTRY／PATH／EXIT、方向、clearance
與 opening 仍由 stair 診斷與獨立人工審查處理。

缺 review、空白文字、非 boolean `walkable`、錯誤 floor／scope 或互相矛盾的宣告，
都保留一般 coverage／naming 檢查並新增 HIGH REVIEW，不能靜默略過。JSON 保存完整
宣告與當次 source SHA；即使幾何 budget 中止，仍保存宣告 evidence。Review ID 是
輸入的語意決定識別，不自動成為 floor／physical／topology authority。EXCLUDED 與
NOT_APPLICABLE 不計入 floor summary 的 uncovered AREA，也不可納入行走覆蓋率分母。
沒有這些新欄位的輸入維持原本結果。

已明確分類為 WALKABLE、且有非空 `semantic_review_id` 的 `WALK_*` 名稱，可作人工
核准 alias，不列 naming inconsistency。未分類的 `WALK_*` 仍不由名稱自動分類；
沒有 review 的舊命名仍維持原本警訊。Blender properties 應放頂層，避免 extractor
不支援的巢狀 property group。

### 2026-10-06 physical policy／source validation

Semantic diagnostics 與 physical approval 是不同入口。Lightweight fresh clone 不包含
raw exact mesh evidence；先依 [materialization contract](PHYSICAL_EVIDENCE_MATERIALIZATION.md)
提供 hash-bound source scene，明確重建並完整重跑本輪 physical review：

```sh
uv run python -m amidst.materialize_physical_evidence \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --source-scene /absolute/path/to/checkout/blender/school_v3.blend
```

原 source 不修改或儲存；tracked summaries／原 manifest 不覆寫。若另需 report replay，
先 materialize，並使用契約中獨立 `/tmp` output 命令。Missing-evidence skip／strict fail
與原始／regenerated hashes 的比較邊界見同一契約。

[Manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/manifest.json)
保存 source before／after、input／code／artifact hashes、版本、runtime 與 git commit。
原 `.blend` 不修改；source evidence 保留 exact source faces／components、hidden geometry
及 BU coordinates，不按 `group_*`／`Cube.*` 名稱賦予角色。

| Report | 核准範圍與剩餘限制 |
| --- | --- |
| [Body policy](../data/scene_audit/phase1_physical_policy_approval_20261006/body_clearance_policy.json) | Upright cylinder／footpoint；0.30 m radius、1.70 m height、0.05 m body clearance、portal 每側 0.05 m／垂直 0.10 m、0.001 m contact tolerance；minimum equality PASS |
| [Floor map](../data/scene_audit/phase1_physical_policy_approval_20261006/floor_authority_map.json) | 48 個 supported subdomains：45 whole／3 partial；38 個舊 plane-offset 警訊由 actual source support 解決；不認證整層完整性或 body／ceiling clearance |
| [Obstacle volumes](../data/scene_audit/phase1_physical_policy_approval_20261006/obstacle_collider_authority.json) | 5/19 obstacles 中 58 個 closed source components APPROVED；19 whole-object scopes 均 REVIEW，不能把 component 結果擴成完整物件 |
| [Portal clearance](../data/scene_audit/phase1_physical_policy_approval_20261006/portal_clearance.json) | 8 組衝突仍 REVIEW；annotation aperture 不能代替 actual clear opening evidence |
| [Stairs](../data/scene_audit/phase1_physical_policy_approval_20261006/stair_authority.json) | A/B 均無可核准 intermediate landing；source slab point headroom 約 0.194 m，support chain／opening／雙向 full-body clearance 尚未證明 |
| [Local physical scopes](../data/scene_audit/phase1_physical_policy_approval_20261006/local_physical_scopes.json) | **0 complete physical islands; 5 searched regions remain REVIEW (unclassified group_0 enclosure / degenerate source geometry)** |

WALL 分類仍 73 HIGH_CONFIDENCE／1,422 HUMAN_REVIEW／77 REJECTED，不放寬 threshold 或
doorway protection。Policy 不需要再次人工選值；剩餘 review 是未完整 volume、門洞、
樓梯與未核准 geometry coverage。WALKABLE／STAIR 外不可導航，但不新增 collider／occluder。
可核准的 local island 須完整檢查限定域 source geometry，離開域就拒絕 validation；
partial collider pruning 只排除已知 violation。Global `physical_complete=false` gate
仍拒絕全域 collision-free／topology／physical-metric 認證。
[Geometry contract](GEOMETRY_PROVIDER.md) 與 [experiment record](EXPERIMENT_LOG.md) 詳列
scope semantics；本輪不是正式 Case 1–3 benchmark，也不開始 Agent。

### 報告與續作

JSON 保存 effective config、source／audit binding、每層 counts、coverage／connectivity／
portal／stair results、geometry warnings 和 findings。Markdown 整理相同結果，review queue
分為 HIGH、MEDIUM、LOW，附 object IDs 與證據。HIGH 優先處理缺 WALKABLE、未連 PORTAL、
明顯 floor conflict、大面積 collider overlap 與缺 stair endpoints；MEDIUM 包含 partial
coverage、islands、疑似 overlap／geometry；LOW 包含 naming 與 non-manifold 警訊。

標記後先重跑 validator 並人工處理 queue；再核准 source-bound surfaces／colliders、
floor／camera bindings、clearance／contact／ownership 與 explicit topology。正式 benchmark
還須完成 [BENCHMARK_PROTOCOL](PHASE1_BENCHMARK_PROTOCOL.md) 的 unresolved settings。Validator
報告完成本身不啟動 school benchmark、Agent Ranking 或最終 presentation pipeline。

## English

Run the command above for a repeatable read-only diagnostic. Blender autoexec is disabled;
the source SHA-256, size and mtime are checked before/after extraction, with no save or render.
Use `--input` for a portable snapshot, `--config` for diagnostic policy, `--audit` for existing
source-bound floor evidence, and `--blender` to override binary discovery. Re-running replaces
only the chosen JSON/Markdown report pair; inputs and source assets cannot be report targets.

The config controls coverage, adjacency, portal/stair distances, contact overlap, geometry
anomalies and complexity budgets. AREA does not require 100% coverage. Defaults are diagnostic
heuristics, not approved clearance or benchmark criteria. Floor authority requires explicit
source/review binding and valid supported plane evidence; otherwise results are HEURISTIC/REVIEW.
School-v3 config uses explicit **APPROVED / USER_DEFINED_RESEARCH_MODEL_SETTING** architectural scale,
**1 BU = 0.0247 m**. Original BU coordinates/measurements remain; metre and square-metre
settings are converted consistently without changing native diagnostic comparison ranges.
Mesh measurements are sanity checks and do not require external dimensions to reapprove
scale. Other physical authorities were separately pending at the scale-only checkpoint.
Its retained scene and geometry/scale validation are in `school_v3_approved_scale_20261006`;
the new physical-policy/source-scope approvals are recorded below, without rewriting that checkpoint.
historical reports and benchmark provenance remain unchanged. Exact historical replay requires
the matching historical code/config. The generic mock/school-v2 config keeps its own contract.
Collection policy is configurable. No objects are renamed, reclassified from unlabeled names,
or moved. New source content requires renewed source binding.

Reports cover AREA overlap/uncovered ratios and offsets; walkable components/islands/endpoints;
portal two-sided/one-sided/disconnected geometry and orientation; stair entry/path/exit,
floor/Z/continuity, declared clearance/opening evidence; wall/obstacle overlap and relevance;
naming/ownership conflicts; and geometry sanity. Non-manifold geometry is reported for review,
not automatically invalidated. Missing stairs produce MISSING without a crash. Mesh footprints
retain triangle-defined holes; bounds-only or unsupported/over-budget geometry requires REVIEW.
Diagnostic adjacency never creates or approves inference topology or stair connectivity.

Explicit AREA declarations may exclude walking coverage with boolean `walkable=false`, a
nonempty `exclusion_reason` and `semantic_review_id`. Coverage becomes `EXCLUDED`, while any
WALKABLE overlap with conservatively intersecting Z extents produces a HIGH finding. A ramp
cannot escape detection because its midpoint lies outside the AREA. Nonplanar or unsupported
overlap evidence remains HIGH REVIEW and does not certify 3D collision; ordinary coverage
retains its midpoint-Z rule. Unresolved floor labels still require review. No physical
authority is granted.
Cross-floor AREA declarations require `coverage_scope=CROSS_FLOOR`, two distinct configured
`floor_from`/`floor_to` values, and nonempty `stair_id`/`semantic_review_id`. Coverage becomes
`NOT_APPLICABLE` with status `REVIEW`, referring to existing stair diagnostics; a missing
matching group remains HIGH. Only valid declarations exempt a missing single-floor label and
the name's `STAIR` token, without resolving other ownership conflicts or creating topology.
Malformed or incomplete declarations retain ordinary checks and receive HIGH REVIEW.
JSON preserves declarations bound to the current source identity, including complexity
fallback reports. EXCLUDED and NOT_APPLICABLE are omitted from uncovered AREA counts and
walking coverage denominators. Inputs without the new fields retain their prior results.
Explicitly classified WALKABLE objects with nonempty `semantic_review_id` may retain a
reviewed `WALK_*` name alias. Unclassified names never acquire a role from this alias rule.

### Current physical-policy/source validation — 2026-10-06

The explicit `amidst.materialize_physical_evidence` command above reconstructs excluded
source-bound exact mesh evidence and replays the complete policy validation using
[the review config](../configs/physical_policy_validation_school_v3.json). Follow the
[materialization contract](PHYSICAL_EVIDENCE_MATERIALIZATION.md) for source prerequisites,
hash checks, missing-evidence skip/strict-failure behavior and separate report output.
Tests do not generate or download local evidence.
The [manifest](../data/scene_audit/phase1_physical_policy_approval_20261006/manifest.json)
binds source integrity, inputs, code, artifacts, versions, runtime and git commit.
The original Blender geometry and historical reports remain unchanged; object names never
establish roles. Policy approval is distinct from source completeness and formal benchmarks.

The approved cylinder policy uses a 0.30 m radius, 1.70 m height, 0.05 m body clearance,
0.05 m portal margin per side, 0.10 m vertical portal margin and 0.001 m obstacle-contact
tolerance. Minimum-clearance equality passes; body/portal margins combine by maximum.
Only legal APPROVED support contact is permitted. Raw same-floor support is unioned before
erosion; outside approved WALKABLE/STAIR navigation is forbidden without creating occluders.
The floor review approves 48 supported subdomains (45 whole/3 partial), resolving 38 old
annotation-plane offsets; it does not certify whole-floor or body/ceiling clearance.
Fifty-eight closed components within 5 of 19 obstacles are approved, while all 19 whole
obstacle scopes remain REVIEW. The eight obstacle/portal conflicts remain REVIEW.
WALL status remains 73 HIGH_CONFIDENCE, 1,422 HUMAN_REVIEW and 77 REJECTED with unchanged
doorway protection. Stair A/B each have zero usable intermediate landings in the selected
source evidence: a slab gives about 0.194 m point headroom, and continuous support, opening
and full-body bidirectional travel remain unproven. BIDIRECTIONAL is the approved intended
travel policy; existing UP/DOWN metadata describes Z ordering, not approved connectivity.
Explicit `path_points_m` remains SI; native `path_segment_points_json` uses the approved BU scale.

Local physical islands: **0 complete physical islands; 5 searched regions remain REVIEW (unclassified group_0 enclosure / degenerate source geometry)**.
Local certificates require complete source screening within a restricted footpoint domain;
validation outside it is refused. Partial collision pruning only rejects known violations.
Global `physical_complete=false` still refuses global collision-free, topology and physical
metric certification. See [provider documentation](GEOMETRY_PROVIDER.md) and the bilingual
[experiment record](EXPERIMENT_LOG.md). No formal Case 1–3 benchmark or Agent work starts here.

Explicit portal normals and the stair custom properties listed above provide diagnostic
evidence. The validator does not infer an ordered stair path or certify body clearance, slab
openings, camera-plane binding or semantic ownership. JSON/Markdown preserve counts, diagnostics,
effective config, source identity and HIGH/MEDIUM/LOW review queues. Resolve human review and
approve authority/policies before geometry integration; resolve the formal protocol settings
before school benchmarks. Tool completion does not authorize Agent work or presentation work.
