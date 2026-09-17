# School v1 Disambiguation and Camera-Eligibility Approval Report

Status: `REVIEW_REQUIRED`

Repository classification: `REVIEW_REQUIRED`

This report proposes a scene-version-specific, non-semantic override layer.
It does not assign an ID, change stable-ID policy v1.0.0, or write Blender data.

## Summary

| Measure | Result |
| --- | ---: |
| Duplicate fingerprint groups | 45 |
| Ambiguous objects | 136 |
| Groups with a deterministic proposed discriminator | 1 |
| Objects automatically resolvable after approval | 5 |
| Groups still requiring manual identity evidence | 44 |
| Objects still requiring manual identity evidence | 131 |

Candidate override: `data/annotations/instance_registry/school_v1_disambiguation.json`

Object and datablock display names are retained only as locators. They do not
participate in any proposed token. The inspected objective evidence covers
object type, collection and parent relationships, local/world transforms,
parent inverse, dimensions, datablock/material sharing, linked-library and
instance sources, children fingerprints, constraint/modifier targets, custom
properties, visibility, render, and animation-use state.

## All Duplicate Groups

| # | Duplicate fingerprint | Object locators | Objective fields that differ | Proposal |
| ---: | --- | --- | --- | --- |
| 1 | `01d45bbc64ccab06b8438a07dc5070f13f060bb00cc1197f18992b472578fa6c` | `Bolt.004`, `Bolt.005`, `Bolt.010` | None | `needs_manual_identity_review` |
| 2 | `04f7e65ad94a647fadb12170e4f674c0556f2f4dfc495042b51eeaf49e7a3afa` | `fenda arredondada`, `fenda arredondada.001`, `fenda arredondada.002` | None | `needs_manual_identity_review` |
| 3 | `073df285235d470395ceb863844ed09f1c4acab4b78d49a88c6d4262f10977c1` | `Plane.097`, `Plane.100`, `Plane.103` | None | `needs_manual_identity_review` |
| 4 | `0f79c2fc088ca7d91ab9231d39e24f0c5b3ce32030d67be600392bb1146baa4b` | `Holder`, `Holder.005`, `Holder.008` | None | `needs_manual_identity_review` |
| 5 | `134fe0c1f1e28ba9c4259fa1db1c472aea8e9fac713da471c52112285907f306` | `Bolt.002`, `Bolt.006`, `Bolt.011` | None | `needs_manual_identity_review` |
| 6 | `141a3ce124fc69a54b728f84365159faed0e27feb628ef2c85ca36c51c9a70c7` | `Discherge_Hose`, `Discherge_Hose.001`, `Discherge_Hose.002` | None | `needs_manual_identity_review` |
| 7 | `1d2b6b06efbefdb6cb69f43803a760c5b1a9764f277698ba336f41ca6603d969` | `Circle.008`, `Circle.014`, `Circle.017` | None | `needs_manual_identity_review` |
| 8 | `224caea03d33c349804b2853cf65983f072f5cceaebf0b231cdee05eb125feb3` | `Belt`, `Belt.001`, `Belt.002` | None | `needs_manual_identity_review` |
| 9 | `33b0876c4f037e3fb7672c90b74fa08e9292a92c7303324e960b8d272b9bd174` | `Cube`, `Cube.027`, `Cube.029` | None | `needs_manual_identity_review` |
| 10 | `369ad74d0b3ec199fd06ec292219973dbea767deed95461a890ea0a5f71d3194` | `Plastic.001`, `Plastic.002`, `Plastic.004` | None | `needs_manual_identity_review` |
| 11 | `3a420dafb74efc86ff8e16f730c11de4d479c76534c361d30453f4a6e9c823db` | `Plane.096`, `Plane.099`, `Plane.102` | None | `needs_manual_identity_review` |
| 12 | `3d1fd729a75693fe359f895fcf678ddfd6d81f506e6a0e532c82d06290ecb03d` | `Cylinder.004`, `Cylinder.008`, `Cylinder.012` | None | `needs_manual_identity_review` |
| 13 | `4945ff6cc1bb26fe4897ee41550f9c376fb577b8819768b92ea1b34a25d77cce` | `Cylinder.005`, `Cylinder.007`, `Cylinder.013` | None | `needs_manual_identity_review` |
| 14 | `4b2f8ae6dc57fa766e1ab74d213be953efbefb3ee134a09dbb4a526b0cce5f0c` | `couch_main_parts`, `pillow_btm`, `pillow_btm_02`, `pillow_btm_03`, `pillows` | `hierarchy.child_fingerprints` | PROPOSED canonical objective-evidence token |
| 15 | `4de7c713fe1e98e8c0cfac8d62b9aab72a99b28a6117cac8c860a4b32852cc98` | `Metal_Light.chain_circle`, `Metal_Light.chain_circle.001`, `Metal_Light.chain_circle.002` | None | `needs_manual_identity_review` |
| 16 | `575b1b906d165634afc8b20b0fb9fa78a1ad6d0499a629da18740f70630a9357` | `Cube.025`, `Cube.026`, `Cube.028` | None | `needs_manual_identity_review` |
| 17 | `5809a562b5d78e5d526f978ccb16027df84a758b29e313cbb1aece4a1e54f019` | `Pressure sensor_metal`, `Pressure sensor_metal.001`, `Pressure sensor_metal.002` | None | `needs_manual_identity_review` |
| 18 | `6943275b96f155b58ff5114ea4d3c76924f2653052d96ef247b17a31c7264051` | `Body`, `Body.001`, `Body.002` | None | `needs_manual_identity_review` |
| 19 | `6d000371e49de91585d2355fec74645c2dc1b163f5d126faff395375a88280a1` | `Plane.098`, `Plane.101`, `Plane.104` | None | `needs_manual_identity_review` |
| 20 | `6f2bce808803ebdf43574e24a3ae3094dc6e1df7bffb743427ae8c4d53777f89` | `Nozzle_1`, `Nozzle_1.001`, `Nozzle_1.002` | None | `needs_manual_identity_review` |
| 21 | `7197940b503a5ce397a50b477f2576691b89ffa17be921383da9e7080eb6d4d5` | `Operating Handle cum Level`, `Operating Handle cum Level.001`, `Operating Handle cum Level.002` | None | `needs_manual_identity_review` |
| 22 | `73e2acf2d8af4dcd5929b3c9ef3d3a86e5e7cee1095941401f5614361dc74d32` | `Circle.001`, `Circle.004`, `Circle.010` | None | `needs_manual_identity_review` |
| 23 | `8a6ad069e6897c1f62ccb494eb72a3148af035b76dc88f5f23b9a1ae5fa28f1a` | `Holder.002`, `Holder.003`, `Holder.006` | None | `needs_manual_identity_review` |
| 24 | `8b27be8644c7582becf2e08835c823018d208d6edd8e9bb1d3dfb1d2c38b7549` | `Cylinder.003`, `Cylinder.006`, `Cylinder.014` | None | `needs_manual_identity_review` |
| 25 | `8ceb5cd7a06f863e3100429798b818b812a8681398eb02ff8933d1863fd83480` | `PORTAL_1F_MENSROOM`, `PORTAL_2F_MENSROOM` | None | `needs_manual_identity_review` |
| 26 | `97591d0bb3d31e4fb6e5217d2542111cde31c240dd0135c6da7dcc6c0bde7525` | `Circle`, `Circle.005`, `Circle.011` | None | `needs_manual_identity_review` |
| 27 | `989390426a594efbb01968034dc82e350c6a4bc4c4515ed0c0f87af47207fbb7` | `Holder.001`, `Holder.004`, `Holder.007` | None | `needs_manual_identity_review` |
| 28 | `9b64b4d056395e1c93dafbf7689129a0afb546633bc3163e25f04cb4f2910090` | `Valve.001`, `Valve.002`, `Valve.004` | None | `needs_manual_identity_review` |
| 29 | `9c7b973f706100f1f578cb74539c8691641fac4ad0367029903c4d334e41071d` | `Circle.007`, `Circle.013`, `Circle.016` | None | `needs_manual_identity_review` |
| 30 | `ab6d9e9d7a768c7e4ed9ba05babc5565be7a454f3ad493492651b9d82b3ce2f9` | `Metal_Light.chain.001`, `Metal_Light.chain.002`, `Metal_Light.chain.003` | None | `needs_manual_identity_review` |
| 31 | `aec00941dcbdb9c9a2c44678c10764d556973cedb2b1ad0b6b078f2c5dfe440e` | `Circle.002`, `Circle.003`, `Circle.009` | None | `needs_manual_identity_review` |
| 32 | `b7abf6fdd3982f751edd9fba0ad181116ff8e898bac682a380aea31cdcb855d3` | `Cylinder.001`, `Cylinder.009`, `Cylinder.011` | None | `needs_manual_identity_review` |
| 33 | `b92ee52726ebed088497a2665b1319b5d8ced7069bfafd02df48a28a55c35e68` | `Handle`, `Handle.001`, `Handle.002` | None | `needs_manual_identity_review` |
| 34 | `cc84e40dc9e21bc2918eb8585931788eaa8225e00149507e893453f51cadc69b` | `Plastic`, `Plastic.003`, `Plastic.005` | None | `needs_manual_identity_review` |
| 35 | `ce4c03282c3296f2eafb523dbae589bea54790adc8521943afa13b7337f3e1e6` | `Valve`, `Valve.003`, `Valve.005` | None | `needs_manual_identity_review` |
| 36 | `ce682d2dbf1280343b2ed4f3b73cce3f1514c59c3aac891bb7e5d902e7fb2c82` | `Inspection`, `Inspection.001`, `Inspection.002` | None | `needs_manual_identity_review` |
| 37 | `d39249f57154919bf24c62509a4cf16d6b01a2042461f123c54fbedd7d8119dd` | `CLASP`, `CLASP.001`, `CLASP.002` | None | `needs_manual_identity_review` |
| 38 | `d9c3771dc9ff1fb448557595c96b1f2b95adbc68edb5f59f3aa67eba93a1bc0b` | `Safely Pin`, `Safely Pin.001`, `Safely Pin.002` | None | `needs_manual_identity_review` |
| 39 | `db7988a565af09548788b40196024d80f5c6f3090dfb7f17c7dd2eaedddb5aff` | `mold`, `mold.001`, `mold.002` | None | `needs_manual_identity_review` |
| 40 | `e01b02b3b92f29953d2bc56afbd24713918247a7f8360d57ccc622f917352583` | `Bolt.001`, `Bolt.008`, `Bolt.012` | None | `needs_manual_identity_review` |
| 41 | `e6f26298aaafcb3b01eb8f0c151bdf061aa3d34083c382d95ebfd6b111d3a5a2` | `Cylinder.002`, `Cylinder.010`, `Cylinder.015` | None | `needs_manual_identity_review` |
| 42 | `e7b126692bea9d0acea4f9416f094ad4f9bc0bae60cfa082b569890a56af9038` | `Arrow`, `Arrow.001`, `Arrow.002` | None | `needs_manual_identity_review` |
| 43 | `eb2da9d328ce5d7fcb1c80afed451fe2f360e9b3654a139a40693261b7ba3bb1` | `Bolt.003`, `Bolt.007`, `Bolt.009` | None | `needs_manual_identity_review` |
| 44 | `ec2fd2b32d02c190a6fb3c07aac7cfc8ef576112e4568d85ed883a93e381e08a` | `Circle.006`, `Circle.012`, `Circle.015` | None | `needs_manual_identity_review` |
| 45 | `fac049401f558fa8dc60636a450cd949c0982dbd3590780d6788d5c8ae2471c1` | `Nozzle_2`, `Nozzle_2.001`, `Nozzle_2.002` | None | `needs_manual_identity_review` |

Only group 14 differs on approved non-semantic evidence:
`hierarchy.child_fingerprints`. Its five members have distinct sorted
child-fingerprint multisets. The other 44 groups have no differing approved
objective field; their names alone are insufficient and no token is proposed.

## Camera Recommendation

Recommend **Option A** as `PROPOSED`: explicitly exclude
`skp_camera_Last_Saved_SketchUp_View` from stable-ID eligibility as a
non-authoritative imported saved-view/helper camera.

- Camera type: `PERSP`.
- Lens: positive infinity, which policy canonicalization correctly rejects.
- Active scene camera: `false`.
- Timeline camera markers: `0`.
- Visible in active view layer: `true`.
- It is scene-linked but locally stored, with one camera-datablock user.
- Its object/datablock locator begins `skp_camera_` and contains
  `Last_Saved_SketchUp_View`, objective provenance evidence of an imported
  saved-view artifact rather than an authoritative dataset camera.
- It is the only `skp_camera_` locator among 30 scene cameras; the other 29
  camera locators use the project `CAM_` prefix.
- Current repository camera logic inventories cameras only. No camera dataset
  generator or direct dependency on this locator exists.

Do not synthesize a finite lens and do not repair the scene in this phase.
Because the confirmed v1.0.0 eligibility scope currently includes every
supported `CAMERA`, Option A requires explicit human approval and a versioned
eligibility-contract amendment. The canonical fingerprint algorithm itself
can remain unchanged; the complete v1.0.0 policy contract cannot be claimed
unchanged if this exclusion is adopted.

## Documentation and Implementation Changes Required After Approval

1. Update ADR-008 with the approved override authority, token derivation,
   lifecycle, and helper-camera exclusion; decide whether the eligibility
   amendment requires policy `1.0.1` or another explicitly approved version.
2. Update `docs/05_Spatial_Model_Specification.md` with the override layer,
   accepted objective evidence, and non-authoritative helper-camera rule.
3. Update `docs/09_Data_Types_and_Exchange_Formats.md` with the override schema,
   version, canonical token fields, and registry linkage.
4. Update `docs/open_questions.md` only for the newly approved portions of
   OQ-004/OQ-015 and camera authority; keep unrelated camera questions open.
5. Update `blender/scene_manifest.json` with the approved override version and
   explicit camera eligibility disposition.
6. Only after those decisions, extend `assign_instance_ids.py` to validate and
   consume approved overrides; rerun the two-pass determinism test before any
   persistent custom-property assignment.

## Approval Decision Needed

- Approve or reject the five hierarchy-based proposed records.
- Supply independent stable non-semantic evidence for the remaining 131
  objects, or explicitly decide that those coincident duplicates are not
  separately eligible entities. Object names cannot be the sole evidence.
- Approve or reject camera Option A and choose the eligibility-contract version.

Until all three decisions are complete, persistent ID assignment remains blocked.
