# Technical Decision Register

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `PROPOSED` template

### Purpose

Answer: **Why was an approach chosen, what alternatives were considered, and
when should the decision be revisited?** Requirements belong in the PRD;
approved technical trade-offs belong here.

### Status Convention

- `CONFIRMED`: explicitly approved and supported by evidence.
- `PROPOSED`: candidate direction awaiting approval.
- `OPEN`: decision or analysis is incomplete.
- `DEFERRED`: intentionally postponed.
- `REJECTED`: explicitly rejected with rationale.

### Decision Register

| ADR | Decision topic | Status | Owner | Affected artifacts | Review / revisit |
| --- | --- | --- | --- | --- | --- |
| ADR-001 | Evaluation-first development | PROPOSED | TODO | PRD, evaluation, dataset, architecture | TODO |
| ADR-002 | Recorded benchmark video before mandatory real-time processing | PROPOSED | TODO | PRD, dataset, architecture | TODO |
| ADR-003 | Zone-level mapping before exact 3D localization | PROPOSED | TODO | Spatial, dataset, evaluation | TODO |
| ADR-004 | Baseline pretrained perception model before custom training | PROPOSED | TODO | Evaluation, future implementation | TODO |
| ADR-005 | Structured retrieval before unnecessary semantic retrieval | PROPOSED | TODO | Retrieval, architecture | TODO |
| ADR-006 | RAG only where unstructured knowledge justifies it | PROPOSED | TODO | Retrieval, Agent | TODO |
| ADR-007 | Modular architecture before unnecessary distributed architecture | PROPOSED | TODO | Architecture | TODO |
| ADR-008 | Deterministic Blender object IDs with an authoritative sidecar registry | CONFIRMED | Peter | Spatial, data formats, dataset, Blender tooling | New object type or future-version migration |
| ADR-009 | Category-agnostic geometric contract for the school_v1 first synthetic slice | CONFIRMED | Peter | Dataset, spatial, data formats, Blender validation | New task, camera model, visibility model, or incompatible schema change |

Topics marked `PROPOSED` are not confirmed decisions. Human review must either
complete an ADR, keep it `PROPOSED`, defer it, reject it, or remove it.

### ADR-008 — Deterministic Blender Object IDs with an Authoritative Sidecar Registry

Status: `CONFIRMED`

Owner: Peter (default responsible person)

Decision date: 2026-09-13

Affected requirements / artifacts: spatial metadata, dataset provenance,
`blender/scene_manifest.json`, Blender identity tooling, and
`data/annotations/instance_registry/school.json`

#### Context

`school_v1` contains 2,778 objects and no stable object IDs. Display names are
not reliable persistent identity, while future scene versions and ground-truth
records require deterministic references. The source scene remains immutable,
and the five unresolved image resources block rendering but not metadata-only
identity preparation.

#### Decision Drivers

| Driver | Importance | Evidence | Status |
| --- | --- | --- | --- |
| Stable identity across scene versions | Required | Approved stable-ID policy | CONFIRMED |
| Reproducible first assignment | Required | Repeated canonical dry-run requirement | CONFIRMED |
| Independence from object names | Required | Names are diagnostic metadata only | CONFIRMED |
| Auditable lifecycle and tombstones | Required | IDs must never be silently reassigned or reused | CONFIRMED |

#### Options Considered

| Option | Benefits | Costs / risks | Evaluation method | Outcome |
| --- | --- | --- | --- | --- |
| Object names as IDs | Simple | Renames and duplicate-style names break persistence | Inspection inventory | REJECTED by requirement |
| Random assignment | Easy uniqueness | Cannot reproduce an unchanged first assignment | Repeat dry runs | REJECTED for v1 |
| UUIDv5 plus canonical fingerprint and sidecar registry | Deterministic, names excluded, lifecycle auditable | Requires canonical type signatures and strict conflict handling | Two-run canonical comparison | CONFIRMED |

#### Decision

Use policy `amidst.school.object-id/1.0.0`, namespace UUID
`1601a7c1-19ac-555d-9962-05e4503ac6bd`, and IDs formatted as
`amidst:school:object:<uuid-v5>`. Generate UUIDv5 from the approved canonical
fingerprint rules. The supported initial types are `MESH`, `ARMATURE`, `CURVE`,
`EMPTY`, `CAMERA`, and `FONT`; object names do not participate in fingerprint
or UUID generation.

The versioned sidecar at
`data/annotations/instance_registry/school.json` is authoritative. Blender
custom properties mirror registry IDs. Duplicate fingerprints/IDs,
unsupported types, ambiguity, or non-determinism stop assignment. Removed
entities retain permanent tombstones, and IDs are never reused. Future-version
matching requires separate validation against real scene differences.

#### Confirmed school_v1 Amendment — Policy 1.0.1

Policy `amidst.school.object-id/1.0.1` keeps the v1.0.0 canonical base
fingerprint algorithm, namespace, ID format, and normal-object UUIDv5 input.
It adds only the reviewed initial-scene resolution layer:

- five objects in one collision group use their unique sorted
  `hierarchy.child_fingerprints` evidence from
  `school_v1_disambiguation.json`;
- 131 objects in 44 objectively indistinguishable groups use explicit opaque
  `bootstrap:NNN` mappings from `school_v1_identity_bootstrap.json` as a
  one-time human-reviewed initialization exception; and
- `skp_camera_Last_Saved_SketchUp_View` is excluded from eligibility as a
  non-authoritative imported saved-view helper without deleting or changing it.

For either approved disambiguation method, SHA-256 hashes canonical JSON with
the base fingerprint, method, and opaque token. That resolved digest replaces
the ambiguous base digest in the existing v1.0.0 UUID name input. Current
object names identify bootstrap targets only; they never enter the fingerprint,
resolved digest, or UUID input. Once issued, registry IDs and the frozen mapping
are authoritative, and the mapping must not be regenerated from renamed
objects. Any missing, duplicate, stale, or mismatched override stops assignment.

#### Consequences

| Consequence | Positive / negative | Mitigation | Owner |
| --- | --- | --- | --- |
| Deterministic audit trail | Positive | Preserve policy, scene, and registry versions | Peter |
| More expensive fingerprints | Negative | Run offline before annotation/rendering | Peter |
| Identical objective signatures block assignment | Negative | Require explicit human disambiguation; never use names as fallback | Peter |
| Blender properties are not standalone authority | Positive | Validate mirrors against the registry before export | Peter |

#### Risks

| Risk | Trigger | Mitigation / experiment | Residual risk |
| --- | --- | --- | --- |
| Canonicalization drift | Implementation or Blender-version change | Version policy and rerun deterministic fixtures | Platform compatibility needs continued checks |
| Unsupported future data type | New Blender object type | Stop and review a new type signature | Future work remains OPEN until reviewed |
| Incorrect cross-version match | `school_v2` or later | Compare actual versions and require ambiguity review | Matching heuristics are not approved yet |

#### Verification

- Run at least two dry assignments against an unchanged working scene.
- Compare canonical fingerprints, object-to-ID mapping, registry semantic
  content, collision report, and counts.
- Verify source and working checksums remain unchanged and no Blender custom
  properties are written.

#### Revisit Condition

- A new Blender object type must enter the eligible scope.
- The canonical policy requires a new version.
- A later scene version exposes unresolved matching, split, or merge behavior.
- Cross-platform deterministic tests differ.

#### References

- Spatial contract: `05_Spatial_Model_Specification.md`
- Data contract: `09_Data_Types_and_Exchange_Formats.md`
- Dataset provenance: `04_Dataset_Specification.md`
- Review evidence: `data/reports/school_v1_stable_id_candidate_policy.md`

### ADR-009 — Category-Agnostic Geometric Contract for the school_v1 First Synthetic Slice

Status: `CONFIRMED`

Owner: Peter (default responsible person)

Decision date: 2026-09-14

Affected requirements / artifacts: first-slice tasks, spatial and visibility
rules, metadata schema, deterministic render config, semantic sidecar, and
readiness validation

#### Context

Stable IDs exist for 2,777 `school_v1` objects, but named semantic labels are
not reviewed and five material-linked images still block rendering. The first
slice needs a reproducible contract that can be evaluated without inventing
semantic categories and must invalidate any observation/ground-truth mismatch.

#### Options Considered

| Option | Benefits | Costs / risks | Outcome |
| --- | --- | --- | --- |
| Require named categories before any slice | Human-readable labels | Blocks geometry-only tasks and encourages premature ontology work | REJECTED for this slice |
| Infer category from names or geometry | Fast apparent coverage | Untrusted semantics contaminate Ground Truth | REJECTED |
| Use surface-nearest distance and material-aware visual contribution | Potentially closer to perception semantics | Type- and renderer-dependent, complex transparency behavior | DEFERRED |
| Stable IDs, evaluated bounding-box anchors, geometric pixel-centre visibility, and strict invalidation | Deterministic, auditable, category-independent | Transparent/material-dependent cases must be rejected | CONFIRMED |

#### Decision

Use contract `amidst.school.first-dataset-slice/0.1.0` for
`visible_objects`, `nearest_object`, `distance_to_object`, `left_of`,
`right_of`, `in_front_of`, and `behind`. Eligible task objects are renderable
`MESH`, `CURVE`, or `FONT` entities with stable IDs, finite evaluated bounding
boxes, and confirmed visibility. Unreviewed semantics remain `Unknown` /
`needs_review`.

Spatial contract `amidst.school.first-slice-spatial/1.0.0` uses the evaluated
world-space bounding-box centre, camera-to-anchor Euclidean metres, and a
right-handed camera-CV frame (+X right, +Y down, +Z forward). Relations use a
`0.0001 m` deadband; ray and distance-tie epsilon are `0.000001 m`. Nearest
ties select the lexicographically first stable ID and preserve the sorted tie
set.

Visibility contract `amidst.school.first-slice-visibility/1.0.0` casts one ray
per final-resolution pixel centre and requires 16 nearest-hit pixels. Occlusion
compares visible pixels with target-only projected pixels. Unsupported
photometric effects or any rendered-observation mismatch invalidate the sample.

Because `school_v1` has no authoritative/default texture set, resource policy
`amidst.school.texture-agnostic-render/0.1.0` uses one neutral opaque,
non-semantic material override on every view layer. Original material graphs
and the five unresolved image paths remain unmodified historical evidence but
are not runtime dependencies. `authoritative_visual_fidelity` is false; only
geometry/spatial ground truth is authoritative.

The authoritative metadata schema is
`amidst.first-dataset-slice.metadata/0.1.0`; render config is
`amidst.school.first-slice-render/0.1.0`, tied to Blender 5.2.1 build
`9e2066aef7ef` and recorded platform/device provenance. Output version is
`school_v1_first_slice_v0_1_0`, with immutable zero-based six-digit frame
directories and separate rejected evidence. Confirmed contracts do not bypass
the readiness gate or publication review.

#### Consequences and Verification

- Geometry-only questions can proceed without semantic-category approval.
- Transparent, refractive, holdout, or otherwise visually inconsistent samples
  are invalid until a later material-aware visibility contract is approved.
- Readiness requires zero unresolved resources required by the approved render
  policy. The five preserved legacy image references need not be reconstructed.
- Generation remains blocked until the derived texture-agnostic scene passes a
  fresh-process invariant and runtime-dependency validation.
- Verification checks exact contract versions, 2,777 stable IDs, 29 valid
  eligible cameras, locked render settings, resource records, scene checksums,
  and authorized path-change provenance.

#### Revisit Condition

- A new task changes object eligibility, anchor, visibility, or relation meaning.
- Material-aware transparency or another renderer becomes required.
- Blender build/platform pixel validation fails.
- An incompatible metadata or output-layout change is required.

#### References

- Dataset contract: `04_Dataset_Specification.md`
- Spatial contract: `05_Spatial_Model_Specification.md`
- Machine schema: `09_Data_Types_and_Exchange_Formats.md`
- Open decision scope: `open_questions.md` OQ-015

### ADR Template

#### ADR-xxx — Decision Title

Status: `OPEN`

Owner: `TODO`

Decision date: `TODO`

Affected requirements / artifacts: `TODO`

#### Context

- What problem or constraint requires a decision?
- Which confirmed requirements and evidence apply?
- What remains uncertain?

`TODO`

#### Decision Drivers

| Driver | Importance | Evidence | Status |
| --- | --- | --- | --- |
| TODO | TODO | TODO | OPEN |

#### Options Considered

| Option | Benefits | Costs / risks | Evaluation method | Outcome |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | OPEN |

#### Decision

`TODO`; do not complete until explicitly approved.

#### Consequences

| Consequence | Positive / negative | Mitigation | Owner |
| --- | --- | --- | --- |
| TODO | TODO | TODO | TODO |

#### Risks

| Risk | Trigger | Mitigation / experiment | Residual risk |
| --- | --- | --- | --- |
| TODO | TODO | TODO | TODO |

#### Verification

- What result would show the decision works? `TODO`
- Which benchmark/test provides that evidence? `TODO`
- Which versioned artifacts must be recorded? `TODO`

#### Revisit Condition

- New requirement or scale threshold: `TODO`.
- Failed metric or operational condition: `TODO`.
- Scheduled review: `TODO`.

#### References

- Requirements: `TODO`
- Architecture: `TODO`
- Evaluation / experiment: `TODO`
- Supersedes / superseded by: `TODO`

### Decision Review Queue

| Priority | ADR | Missing evidence / decision | Blocking work | Reviewer | Status |
| --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | OPEN |

### Expected Artifacts

- One ADR per material and reversible/revisitable technical choice.
- Evidence and alternatives sufficient to understand the trade-off.
- Explicit consequences, verification, and revisit conditions.
- Links to affected requirements, architecture, dataset, and evaluation artifacts.

### Document Acceptance Checklist

- [ ] No candidate decision is marked `CONFIRMED` without explicit approval.
- [ ] Each confirmed ADR records alternatives and consequences.
- [ ] Verification and revisit conditions are actionable.
- [ ] Requirements are not replaced by implementation preferences.
- [ ] Superseded or rejected decisions retain rationale and traceability.

---

<a id="繁體中文"></a>

## 繁體中文

文件狀態：`PROPOSED` 範本

### 文件目的

回答：「為何選擇這個方案、考慮過哪些替代方案，以及何時應重新檢視？」
需求屬於 PRD；經核准的技術取捨才記錄在此。

### 狀態慣例

- `CONFIRMED`：已有明確核准與證據。
- `PROPOSED`：等待核准的候選方向。
- `OPEN`：決策或分析尚未完成。
- `DEFERRED`：刻意延後處理。
- `REJECTED`：已明確否決並留下理由。

### 決策清單

| ADR | 議題 | 狀態 |
| --- | --- | --- |
| ADR-001 | 以評估為核心的開發方式 | PROPOSED |
| ADR-002 | 強制即時處理前，先使用錄影建立基準 | PROPOSED |
| ADR-003 | 精確 3D 定位前，先採區域層級映射 | PROPOSED |
| ADR-004 | 自訂訓練前，先建立預訓練感知模型基準 | PROPOSED |
| ADR-005 | 不必要的語意檢索前，先採結構化檢索 | PROPOSED |
| ADR-006 | 只有非結構化知識確有需要時才使用 RAG | PROPOSED |
| ADR-007 | 不必要的分散式架構前，先採模組化架構 | PROPOSED |
| ADR-008 | 使用權威 sidecar registry 的確定性 Blender 物件 ID | CONFIRMED |
| ADR-009 | school_v1 首批合成資料採 category-agnostic 幾何契約 | CONFIRMED |

標示為 `PROPOSED` 的項目都不是已確認決策。人員審查後應完成 ADR、維持
提案、延後、否決或移除。

### ADR-008 — 使用權威 Sidecar Registry 的確定性 Blender 物件 ID

狀態：`CONFIRMED`

負責人：Peter（預設負責人）

決策日期：2026-09-13

`school_v1` 有 2,778 個物件但沒有穩定 ID；display name 無法作為可靠的長期
identity。決議採用 `amidst.school.object-id/1.0.0`、namespace UUID
`1601a7c1-19ac-555d-9962-05e4503ac6bd`，以及
`amidst:school:object:<uuid-v5>` 格式。UUIDv5 依已核准的 canonical
fingerprint 規則產生，object name 不參與 fingerprint 或 UUID。

初始支援 `MESH`、`ARMATURE`、`CURVE`、`EMPTY`、`CAMERA`、`FONT`。
`data/annotations/instance_registry/school.json` 是版本化權威來源，Blender
custom property 只鏡像 registry。重複 fingerprint／ID、不支援型別、歧義
或非確定性結果都必須停止指派；消失實體永久保留 tombstone，ID 永不重用。
未來版本 matching 必須依實際差異另行驗證。

採 object name 作 ID 會因改名與重複式名稱失效；隨機 ID 無法重現第一次
指派，因此本版採可重現且可稽核的 UUIDv5 + canonical fingerprint +
sidecar registry。驗證方式是對未變動 working scene 至少 dry-run 兩次，
比較 fingerprints、mapping、registry、collision report 與 counts，並確認
source／working checksum 不變且沒有寫入 Blender custom property。

新物件型別、policy 新版本、未來場景的 match／split／merge，或跨平台結果
不一致時，必須重新檢視本決策。

#### 已確認的 school_v1 修正 — Policy 1.0.1

`amidst.school.object-id/1.0.1` 保留 v1.0.0 的 canonical base fingerprint
algorithm、namespace、ID 格式與一般物件 UUIDv5 input，只新增已審閱的初始
場景解歧層：一組中的五個物件使用唯一的排序後
`hierarchy.child_fingerprints`；其餘 44 組／131 個客觀上無法區分的物件使用
`school_v1_identity_bootstrap.json` 中明示且 opaque 的 `bootstrap:NNN`
mapping；`skp_camera_Last_Saved_SketchUp_View` 則只從 eligibility 排除，場景
物件本身不得刪除或修改。

兩種 override 都以只含 base fingerprint、method 與 opaque token 的 canonical
JSON 計算 SHA-256 resolved digest，再放入既有 v1.0.0 UUID name input。
Object name 只用來在初始審閱時定位 bootstrap target，不進入 fingerprint、
resolved digest 或 UUID input。ID 產生後由 registry 與凍結 mapping 擔任權威，
不得依改名後物件重新建立 mapping；override 缺漏、重複、過期或不相符時都
必須停止指派。

### ADR-009 — school_v1 首批合成資料採 Category-Agnostic 幾何契約

狀態：`CONFIRMED`

負責人：Peter（預設負責人）

決策日期：2026-09-14

首批 task 採 `amidst.school.first-dataset-slice/0.1.0`，涵蓋
`visible_objects`、`nearest_object`、`distance_to_object`、`left_of`、
`right_of`、`in_front_of` 與 `behind`。任務只使用 stable ID 與 Blender
evaluated geometry，不要求具名類別；未審閱語意維持 `Unknown`／
`needs_review`，不得由名稱或幾何推測。

空間契約 `amidst.school.first-slice-spatial/1.0.0` 採 evaluated world-space
bounding-box center、camera-to-anchor Euclidean 公尺，以及 +X 右、+Y 下、+Z
forward 的右手 `camera_cv`。關係 deadband 為 `0.0001 m`，ray／distance tie
epsilon 為 `0.000001 m`；最近距離平手時選 stable ID 字典序第一個並保存完整
tie set。

Visibility 契約 `amidst.school.first-slice-visibility/1.0.0` 對每個最終 pixel
center 發射一條 ray，至少 16 個 nearest-hit pixels 才算可見；occlusion 比較
visible 與 target-only projected pixels。透明、折射、holdout 或其他材質效果
若造成 rendered observation 不一致，樣本即失效。

由於 `school_v1` 沒有 authoritative/default texture set，resource policy
`amidst.school.texture-agnostic-render/0.1.0` 對每個 view layer 使用同一個
neutral opaque、無語意 material override。原 material graphs 與五條 unresolved
image paths 不修改並保留為歷史證據，但不再是 runtime dependencies。
`authoritative_visual_fidelity` 為 false，只有 geometry／spatial ground truth
具權威性。

權威 metadata schema 為 `amidst.first-dataset-slice.metadata/0.1.0`，render
config 為 `amidst.school.first-slice-render/0.1.0`，綁定 Blender 5.2.1 build
`9e2066aef7ef` 並記錄平台／device provenance。輸出版本
`school_v1_first_slice_v0_1_0` 使用不可覆寫的六位數 frame 目錄及獨立 rejected
證據。Readiness 改為檢查 approved render policy 所需資源無未解項目；五條
legacy image references 不需重建，但 derived texture-agnostic scene 必須先
通過 fresh-process invariant 與 runtime-dependency validation。契約確認也不
等同 Git 發布核准。

若新增 task、改變 anchor／visibility／relation 語意、需要 material-aware
transparency、Blender build／platform 驗證失敗，或 schema／輸出 layout 發生
不相容變更，必須重新檢視此決策。

### ADR 應記錄的內容

- 標題、狀態、負責人、決策日期與受影響需求／產物；
- 問題背景、已確認限制、證據與仍不確定的部分；
- 決策驅動因素及其重要性；
- 各候選方案的效益、成本、風險與評估方法；
- 經明確核准的決策內容；
- 正面／負面後果、緩解方式與負責人；
- 風險觸發條件、實驗與殘餘風險；
- 能證明決策有效的結果、測試與版本化證據；
- 重新檢視門檻、失敗條件與預定日期；以及
- 需求、架構、評估與取代關係的連結。

在明確核准前，Decision 欄保持 `TODO`，狀態維持 `OPEN` 或
`PROPOSED`。

### 審查佇列與驗收

審查佇列應記錄優先順序、ADR、缺少的證據、阻塞工作、審查者與狀態。

- [ ] 候選決策未經明確核准，不得標為 `CONFIRMED`。
- [ ] 每項已確認 ADR 都記錄替代方案與後果。
- [ ] 驗證方法與重新檢視條件可以實際執行。
- [ ] 不以實作偏好取代需求。
- [ ] 被取代或否決的決策仍保留理由與追溯關係。
