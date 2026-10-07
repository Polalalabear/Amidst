# New local scope implementation / 新局部 scope 實作

Recorded 2026-10-08. **Preparatory capability implemented; no new scope approved and no
all-case readiness claimed.**
記錄日期：2026-10-08。**準備能力已實作；尚未核准新 scope，也未宣稱所有 cases ready。**

## 繁體中文

新增 [scoped_authority.py](../src/amidst/finalization/scoped_authority.py) 與
[scoped_authority_cli.py](../src/amidst/finalization/scoped_authority_cli.py) 提供
`prepare → preview → 明確直接人工 receipt → apply 原數值認證 → verify 重建`。
CLI 沒有自動批准或 `approve` 指令。`prepare` 只產生 `HUMAN_REVIEW` proposal 與
`PENDING` template；`preview` 不建立人工 `APPROVE`、不套用 bounded surface semantics，
不輸出可用 certificate/provider。新人工 `APPROVE` 仍不能令失敗的數值證明通過。

`ScopeAuthorityPins` 由呼叫端獨立固定 source SHA、完整 source evidence content SHA、
原 physical contract（policy、scale、runtime）content SHA、原 collision numerics content SHA、
原 HR01–HR04 decisions SHA、protocol SHA 與原 approved floor content SHA。若請求新
projection authority，還須獨立固定 source camera export content SHA。`ScopeProposal`
保存精確 source mesh／geometry／component／face／triangle 與座標 hash，保留各 cell 的
rectangle、完整 body guard、原完整 atlas region、明確提出的語意，以及 camera calibration、
同 XY landmark offset 與水平 projection plane。支撐與 island 的 disconnected components
各自綁定，不能把 whole object 或 bounding box 當作 collider 或 solid-interior approval。

API 的 `proposal_from_source_discovery(...)` 只複製 source 證據。單一
`BoundedSurfaceSemantics` 可以明確指定給全部 cells；更精確的 input 是
`{"profiles_by_cell_index": {"0": profile, "1": null, ...}}`，必須列出每個 cell index。
`null` 表示不提出該 cell 的 surface-only 語意，沒有自動 fallback。不同 cells 可提出不同
source components。`ScopeCellProposal.surface_semantics` 保留原 primary 預設，
`extra_surface_semantics` 可明確增加 profiles；CLI 的每個 index 也可提供完整 profile list。
新的 [scoped_semantic_cells.py](../src/amidst/finalization/scoped_semantic_cells.py) 保留
一個或多個完整 v2 review receipts／hashes，並逐一驗證同一新人工 decision 與每個 guard。
舊單一 profile producer 保持不動。v2 允許**明確空的 exact-zero-area list**：guard 內沒有
零面時，不能虛構或借用 guard 外的豁免。未提供的其他 component 保持 `REVIEW`。
source role 預設只適用於提出的 body guards 與 cell union；原 HR01–HR04 不重新開啟或擴張。

movement-obstacle binding 可另提出 `source_face_movement_obstacle_bounds_bu`，將具名
source faces 的 `SOURCE_FACE_MOVEMENT_OBSTACLE` ownership 限於此明確範圍；它不是
collider box，也不擴張 path permission。此新範圍須被精確新 proposal／直接人工 receipt
hash 綁定，符合原完整同樓層 atlas，且與實際 source triangles 相交。exact planar bounds
不需人造厚度。bridge 只在 proposal 階段從實際 source-face extrema 提出 bounds；核准後
不能自動重新算 bbox 或擴張。沒有 explicit bound 時保留原 guard／union-only 語意。

`apply_scope_approval(...)` 必須收到 `ScopeHumanDecision`：直接人類 decision 原文、身份、
approval ID、有時區的時間與精確 proposal content SHA，並核對呼叫端獨立提供的
proposal/decision hashes。未 `APPROVE` 即阻塞。核准後仍使用原支撐、body、clearance、
contact、distance budget 與 enclosure checks，任何 cell 失敗均不簽發 union certificate。
通過時 `ScopeUnionCertificate` 保留全部原 cell certificates／semantic wrappers 與 union
WKB/hash。`load_scoped_authority(...)` 再從原 source 重建完整數值證明；回傳的
`ScopedUnionPhysicalProvider.validate_polyline(points_bu)` 檢查連續 segment 的完整 union
coverage，所有 interval arithmetic 使用 exact `Fraction`，不能跨 hole、未批准縫隙或
邊界外，也不把 union 補成外接 rectangle。每次操作先重新驗證完整 receipt／certificate。
局部 physical certificate 不代替 fresh visibility、獨立 route inventory 或 case readiness。

歷史 `reviewed_branch_scope_proposal_v1`／`reviewed_branch_scope_preview_v1` 使用 source
discovery V4。原 strict preview 的六個 cells 全為 `REVIEW`，原因均為 group_0 的
`UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN`；沒有正式 certificate。這些是保存的歷史
診斷，**v1 packet 不能稱為 approve-ready**。新的 V7 camera source queries 與精確 V2
proposal 已準備，見 [corridor review](PHASE1_CORRIDOR_SCOPE_REVIEW.md)。Actual strict preview
仍有六個 unknown-volume REVIEW，certificate null；fresh 5 Hz 正式 simulation 尚未開始。

已準備的 V2 source proposal 請求的最小新人工語意包括：精確 bounded raw support
faces 的 contact permission、guard 內明確 source component 的 surface-only interior 與
bounded source obstacle surface ownership，以及該新 scope 的 source-camera／landmark
binding。V2 實際 guards 沒有相交的零面，故不請求零面豁免。通用零面豁免不能排除非退化 geometry；實際 source body
contacts 與 clearance 不足繼續拒絕。原 source、HR01–HR04、29 inputs、57 review frames、
protocol、physical policy 與 numerics 保留；新 receipt 不重寫這些批准。

## English

The additive modules provide
`prepare → preview → explicit direct-human receipt → apply original numerical proof → verify
by regeneration`. There is no automatic approval or `approve` command. Preparation emits a
`HUMAN_REVIEW` proposal and a blocked `PENDING` template. Preview creates no human `APPROVE`,
applies no bounded surface semantics and returns no usable certificate/provider. A subsequent
human approval cannot clear a failed numerical proof.

Caller-supplied `ScopeAuthorityPins` independently fix the preserved source, complete source
evidence, original physical contract, original collision numerics, original HR01–HR04 decisions,
protocol and approved floor hashes. Requested projection authority additionally requires an
independently pinned source-camera export. `ScopeProposal` binds exact mesh, geometry,
component, face, triangle and coordinate hashes; cell rectangles and complete body guards;
original complete atlas regions; explicitly proposed semantics; and exact camera calibration,
same-XY landmark offset and horizontal projection plane. Disconnected source components are
bound separately. Names, outer boxes and whole-object membership grant no collider or solid
interior authority.

`proposal_from_source_discovery(...)` copies source evidence without approval. An explicit
shared `BoundedSurfaceSemantics` can be supplied, or
`{"profiles_by_cell_index": {"0": profile, "1": null, ...}}` must cover every cell index.
`null` proposes no surface-only semantics for that cell; there is no implicit fallback.
Different cells may bind different components. `surface_semantics` retains the primary default;
`extra_surface_semantics` explicitly adds profiles. A CLI cell index may contain a complete
profile list. The additive multi-profile module retains one or more complete v2 reviews and
their hashes, validating the same new human decision and each guard. The original single-profile
producer remains unchanged. V2 permits an **explicitly empty exact-zero-area list**: absent
zero-area faces in a guard require no invented or distant exemption. Unsupplied components
remain `REVIEW`. Roles default to the proposed guards and cell union.
Original HR01–HR04 approvals are neither reopened nor expanded.

A movement-obstacle binding may additionally propose
`source_face_movement_obstacle_bounds_bu` for `SOURCE_FACE_MOVEMENT_OBSTACLE` ownership of
the named facets. This explicit semantic scope is neither collider geometry nor extra path
permission. Exact new proposal/direct-human receipt hashes bind it; it must remain within
the original complete same-floor atlas and intersect actual source triangles. Planar bounds
need no invented thickness. The bridge proposes raw face extrema before approval; consumers
cannot derive or enlarge a box afterwards. Absent this field, guard/union-only ownership remains.

`apply_scope_approval(...)` requires a `ScopeHumanDecision` containing the direct human text,
reviewer, approval ID, timezone-aware timestamp and exact proposal hash, plus independently
supplied proposal/decision hashes. An unapproved receipt blocks application. Approved input
still uses the original support, body, clearance, contact, distance-budget and enclosure checks.
Any failed cell prevents a union certificate. Successful `ScopeUnionCertificate` retains every
original cell proof and semantic wrapper plus exact union WKB/hash.
`load_scoped_authority(...)` regenerates all numerical proofs from the original source.
Its `ScopedUnionPhysicalProvider.validate_polyline(points_bu)` checks complete continuous
segment coverage using exact `Fraction` intervals, refusing holes, unapproved gaps and outside
points; every operation revalidates the intact receipts/certificate. It never replaces the
union with an outer rectangle. Local physical approval does not establish fresh visibility,
an independent route inventory or case readiness.

Historical V4 preparation produced the preserved scope proposal/preview v1. All six strict
cell checks returned `REVIEW` for group_0's `UNKNOWN_CLOSED_VOLUME_GEOMETRY_UNCERTAIN`, with
no formal certificate. **The v1 packet is not approve-ready.** V7 source-camera queries and
the exact V2 proposal are now prepared; see the corridor review above. Actual strict preview
retains six unknown-volume REVIEW results and no certificate. Fresh formal 5 Hz simulation
has not begun.

The prepared V2 source proposal requests a minimal new human decision covering bounded
contact permission for exact raw support faces; explicit surface-only component interior and
bounded source-obstacle surface ownership; and the new source-camera/landmark binding.
V2 guards intersect no zero-area source faces, so it requests no zero-area exemptions.
The generic exemption mechanism cannot remove a nondegenerate triangle.
Actual source body contacts and insufficient clearance remain rejected. The original source,
HR01–HR04, 29 inputs, 57 review frames, protocol, physical policy and numerics remain intact.

## CLI workflow / CLI 流程

The following paths are **future placeholders**, not a claim that a complete packet exists.
Each stage needs a fresh output directory. Content hashes use `content_sha256`, not file hashes.
以下路徑是**未來 placeholder**，不表示完整 packet 已存在。每個 stage 使用新輸出目錄；
receipt 的 hashes 使用 `content_sha256`，不能混用 file SHA。

```bash
scope_common=(
  --source /Users/polalabear/Developer/amidst/blender/school_v3.blend
  --evidence data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz
  --runtime configs/physical_policy_runtime_school_v3.json
  --numerics configs/physical_collision_numerics_v1.json
  --pins data/finalization/new_scope_inputs_vN/pins.json
  --camera-export data/finalization/new_scope_inputs_vN/source_cameras.json
)

.venv/bin/python -m amidst.finalization.scoped_authority_cli prepare "${scope_common[@]}" \
  --discovery data/finalization/new_source_discovery_vN/source_supported_proposal.json \
  --scope-id school-v3-new-local-branch-vN \
  --floor data/finalization/new_scope_inputs_vN/original_floor.json \
  --surface-semantics data/finalization/new_scope_inputs_vN/proposed_profiles_by_cell.json \
  --camera-bindings data/finalization/new_scope_inputs_vN/proposed_camera_landmarks.json \
  --output data/finalization/new_scope_packet_vN

.venv/bin/python -m amidst.finalization.scoped_authority_cli preview "${scope_common[@]}" \
  --proposal data/finalization/new_scope_packet_vN/proposal.json \
  --output data/finalization/new_scope_preview_vN

# Only after an explicit direct-human decision; the PENDING template does not approve.
# 僅在明確直接人工 decision 之後；PENDING template 不是批准。
.venv/bin/python -m amidst.finalization.scoped_authority_cli apply "${scope_common[@]}" \
  --proposal data/finalization/new_scope_packet_vN/proposal.json \
  --decision data/finalization/new_scope_approved_vN/direct_human_decision.json \
  --expected-proposal-sha256 "$SCOPE_PROPOSAL_CONTENT_SHA256" \
  --expected-decision-sha256 "$SCOPE_HUMAN_DECISION_CONTENT_SHA256" \
  --output data/finalization/new_scope_application_vN

.venv/bin/python -m amidst.finalization.scoped_authority_cli verify "${scope_common[@]}" \
  --proposal data/finalization/new_scope_packet_vN/proposal.json \
  --decision data/finalization/new_scope_approved_vN/direct_human_decision.json \
  --expected-proposal-sha256 "$SCOPE_PROPOSAL_CONTENT_SHA256" \
  --expected-decision-sha256 "$SCOPE_HUMAN_DECISION_CONTENT_SHA256" \
  --certificate data/finalization/new_scope_application_vN/certificate.json \
  --expected-certificate-sha256 "$SCOPE_UNION_CERTIFICATE_CONTENT_SHA256" \
  --output data/finalization/new_scope_verification_vN
```

Use `--help` for the actual arguments. Source authority inputs reject GT/evaluation/simulation
partitions. Physical-only preparation may omit camera arguments and cannot request projection
authority. Independent pins and human hashes must be supplied from reviewed evidence; the CLI
does not choose or approve them.
使用 `--help` 查看實際參數。source authority inputs 拒絕 GT／evaluation／simulation
partition。physical-only 準備可省略相機參數，但不能請求 projection authority。獨立 pins
與人類 receipt hashes 由審閱證據提供，CLI 不替人選擇或批准。

Final validation on 2026-10-08: **1978 passed, zero skipped/failed**, with original physical
evidence required from the start; repo Ruff, strict mypy for 111 source files and the source
CLI passed. The 60 focused authority/inventory/wrapper tests include two new inner public
operation receipt-mutation regressions. The [validation receipt](../data/finalization/reviewed_branch_scope_review_v2/code_validation.json)
pins tested source hashes; the earlier 1976-test pre-fix receipt remains historical.
These engineering tests do not approve the pending school scope or complete its formal cases.
2026-10-08 最終驗證 **1978 passed、零 skip／fail**；從一開始要求原實際 physical evidence。
Repo Ruff、111 source files 及 CLI 的 strict mypy 通過。60 個 focused tests 包含兩個新的
內層 public operation receipt mutation 反例；source hashes 與歷史結果見上述 receipt。
這些工程檢查不是待審 school scope 的批准或正式 case 完成。
