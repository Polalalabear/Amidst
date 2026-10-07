# Phase 1 branching scope readiness

2026-10-07. Status: **PROPOSAL_NOT_AVAILABLE**. HR-01–HR-04 remain approved and
their original payloads are unchanged. No new physical scope or camera-landmark
authority has been applied by this audit.

The existing reviewed office certificate covers a complete, convex footpoint
rectangle of 0.2964343966 m × 3.8729874223 m. Every permitted path between fixed
endpoints can be continuously deformed to the straight connector within that
free rectangle. It has one major source-distinct route class, zero approved
branching islands, and zero approved portal/cross-scope transitions. Parallel
offsets and alternate timings cannot satisfy Case 2. This is an analytic
restricted-domain proof, not an enumeration of every geometric curve.

The same restriction prevents the original Case 3 detour/candidate-growth stress
gate from completing. Its independent long-GAP, speed/slack/departure-dwell and
bounded-search measurements may run, but cannot certify missing route growth.

## Automatic scope audit

The audit examined the 58 approved closed components associated with five 1F
obstacle roles. It preserved actual source object/component IDs, source mesh and
geometry hashes, source face indices, and the unchanged physical policy. It also
extracted all 29 actual source cameras in an unsaved Blender process; source
SHA-256, size and mtime were checked before and after. The source camera catalog
content SHA-256 is
`a851ffebe3d6a6b71789a9afcfc2355c16d75603ef97d814d4d5bd4d5bc22b8e`.

For each component the bounded candidate family uses two travel axes and two
rectangular bypass sides, with shared source endpoints. Each bypass sits
14.6700404858 BU outside the component's source bounds: the existing required
0.35 m footprint clearance plus a 0.5 BU numerical placement margin. This is
explicit case discovery configuration, not a reduced physical clearance.

| Automatic evidence | Result |
| --- | --- |
| Closed components / approved obstacle roles | 58 / 5 |
| Configured two-sided candidate pairs | 116 |
| Distinct source departure/recovery cameras framing endpoints | 26 |
| All six route segments pass approved source WALKABLE support/body clearance | 0 |
| Combined support plus distinct-camera FOV readiness | 0 |
| Original office cameras exclude all nearby component candidate boxes | 58 / 58 |
| Shortest office→island→office length lower bound | 65.8284486695 m |
| Maximum existing office direct-route detour budget | 7.7686304907 m |

Camera exclusion uses a separating halfspace for the entire candidate marker
box, not individually sampled corners. Candidate camera inclusion only checks
FOV; it does not establish occlusion, camera-landmark semantics, or a formal
visible→GAP→visible sequence. Support already fails, so this bounded audit did not
continue to source occlusion or free-space certification for an unusable domain.

The current physical authority does not provide an automatically certifiable
branching case. The 116-candidate family is finite and reproducible; it is **not**
a global exhaustive search of all curves, camera combinations or school domains.
No whole obstacle, unknown wall, portal, stair, source component, or unannotated
support patch was promoted to authority.

## Concrete source witnesses

These examples are locators for the failed proposals, **HUMAN_REVIEW** /
**NOT_CERTIFIED**, not new cases awaiting an approval-only switch. All routes and
candidate source hashes are retained in the curated
[candidate summary](../data/finalization/reviewed_route_inventory_v1/candidate_audit_summary.json).
Their complete source face lists and source camera projections remain local raw
artifacts, bound by the
[raw artifact manifest](../data/finalization/reviewed_route_inventory_v1/candidate_raw_manifest.json).

| Approved role / source component | Actual source bounds, BU | Existing source cameras framing endpoints | Automatic support blocker |
| --- | --- | --- | --- |
| `OBSTACLE_1F_CORRIDOR_01_01`; `Rust Cabinet-Freepoly.org.001/component-00000000` | X 912.948380–941.936624; Y 503.557775–529.916996; Z 82.101355–83.824340 | `CAM_1F_RESTAURANT_01` → `CAM_1F_CORRIDOR_02` | OUTSIDE_APPROVED_WALKABLE; INSUFFICIENT_WALKABLE_CLEARANCE |
| `OBSTACLE_1F_CORRIDOR_01_02`; `trash can02/component-00000036` | X 843.853472–845.787219; Y 697.962669–700.281871; Z 53.462631–54.673848 | `CAM_1F_RESTAURANT_01` → `CAM_1F_CORRIDOR_02` | OUTSIDE_APPROVED_WALKABLE; INSUFFICIENT_WALKABLE_CLEARANCE |
| `OBSTACLE_1F_STORAGE03`; `Tool_cart/component-00006410` | X 1690.803271–1695.099876; Y 565.369794–570.953883; Z 23.349586–32.299576 | `CAM_1F_CORRIDOR_02` → `CAM_1F_MEETINGROOM` | OUTSIDE_APPROVED_WALKABLE; INSUFFICIENT_WALKABLE_CLEARANCE |

The cabinet witness has exact source faces 0–11, mesh SHA-256
`ae17d9e21a62cbb97cebc52ac3d70759be98baf1f630da0a1b6d96e2e467a10e`
and source geometry SHA-256
`c165f5ea5b84443cec9a0e7b50badbe3936e9a2e0683867615ac3f2635886529`.
The trash witness's complete 18-face list has canonical SHA-256
`28174297232c3e147948d0052acf5f29834a91b3f55b8b07f12e94fdd58a7d77`.
The cart witness's complete 1428-face list has canonical SHA-256
`e98e2abb865f7453167f4210bd45c973680ae53c06bf1bb14117cd5bb70cf671`.

A future new-scope gate requires a source-bound contact domain that actually
supports both sides of a real island, a complete local body/source proof, and
valid source-camera landmark binding and visibility. None of the failed boxes
above can become a formal branching case simply by reapproving HR-01 or
relabeling a diagnostic route. This audit supplies the coordinates and hashes;
it does not ask the researcher to calculate or organize another dataset.

## Reproduction and publication

From the existing finalization worktree, after materializing the original
hash-matching physical evidence and reviewed application:

```sh
UV_CACHE_DIR=/private/tmp/amidst-finalization-uv-cache uv run python \
  scripts/audit_reviewed_branch_scope.py \
  --source-catalog data/finalization/reviewed_route_inventory_v1/source_camera_catalog.json \
  --output <fresh-local-output>
```

The source catalog can be freshly regenerated with the existing
`amidst.simulation.camera_calibration.read_camera_calibration_catalog` and
`export_camera_calibration_json`, using the unchanged source scene, 29 CAM_*
cameras and config version `phase1-branch-scope-proposal-source-cameras-v1`.
Do not overwrite an existing catalog or audit output. The raw manifest records
exact input/output SHA-256, byte counts and producer hashes. Only the curated
summary, manifest, source code/tests and this document belong in Git; the source
catalog and full face/projection inventories remain local.

English: The original four approvals remain valid. The approved office rectangle
proves one major route class. The bounded 58-component, 116-bypass audit found no
pair satisfying existing approved contact/body clearance and distinct-camera
endpoint FOV. A new minimal executable branching-scope proposal is unavailable;
the source-bound failed candidates are documented without granting authority or
claiming an exhaustive whole-school search.
