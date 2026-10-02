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

[scene_validation_v1.json](../configs/scene_validation_v1.json) 將 coverage thresholds、
距離／高度 tolerances、small islands、contact overlap、tiny／giant geometry、scale 與
geometry complexity budgets 外部化。預設 `coverage_pass_ratio=0.8`，AREA 不要求 100%
coverage。這些是 **diagnostic heuristics**，不等於正式 clearance 或 research targets。
`minimum_clearance_m=null` 表示尚未決定，不以其他 overlap tolerance 偷代。

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
未明列的 stair vertex ordering 不自行猜測。

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
Collection policy is configurable. No objects are renamed, reclassified from unlabeled names,
or moved. New source content requires renewed source binding.

Reports cover AREA overlap/uncovered ratios and offsets; walkable components/islands/endpoints;
portal two-sided/one-sided/disconnected geometry and orientation; stair entry/path/exit,
floor/Z/continuity, declared clearance/opening evidence; wall/obstacle overlap and relevance;
naming/ownership conflicts; and geometry sanity. Non-manifold geometry is reported for review,
not automatically invalidated. Missing stairs produce MISSING without a crash. Mesh footprints
retain triangle-defined holes; bounds-only or unsupported/over-budget geometry requires REVIEW.
Diagnostic adjacency never creates or approves inference topology or stair connectivity.

Explicit portal normals and the stair custom properties listed above provide diagnostic
evidence. The validator does not infer an ordered stair path or certify body clearance, slab
openings, camera-plane binding or semantic ownership. JSON/Markdown preserve counts, diagnostics,
effective config, source identity and HIGH/MEDIUM/LOW review queues. Resolve human review and
approve authority/policies before geometry integration; resolve the formal protocol settings
before school benchmarks. Tool completion does not authorize Agent work or presentation work.
