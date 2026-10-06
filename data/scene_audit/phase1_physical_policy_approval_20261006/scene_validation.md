# Semantic completeness diagnostics / 場景語意完整度診斷

Status: **REVIEW_REQUIRED**. Authority: **HEURISTIC / REVIEW** until source-bound approval.

原始場景不修改；不建立 Graph／stair connectivity、不猜測未標記幾何。
Source is preserved; no inferred physical roles or inference topology are created.

## Floor summary / 每層摘要

| Floor | AREA | WALKABLE | WALL | OBSTACLE | STAIR | PORTAL | Components | Isolated | Uncovered | Suspicious portals | Conflicts | Geometry warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1F | 16 | 28 | 0 | 13 | 2 | 16 | 9 | 1 | 5 | 4 | 0 | 128 |
| 2F | 12 | 20 | 0 | 6 | 2 | 12 | 5 | 0 | 4 | 4 | 0 | 92 |
| UNASSIGNED | 2 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 8 |

## AREA coverage / 區域覆蓋

| AREA | Status | Geometric coverage | Overlap ratio | Uncovered | Nearest WALKABLE | Offset m |
| --- | --- | --- | ---: | ---: | --- | ---: |
| AREA_1F_AUDITORIUM | PASS | PASS | 1 | 0 | WALK_1F_AUDITORIUM | 0 |
| AREA_1F_CLASS101 | PASS | PASS | 1 | 0 | WALK_1F_CLASS101 | 0 |
| AREA_1F_CLASS102 | PASS | PASS | 1 | 0 | WALK_1F_CLASS102 | 0 |
| AREA_1F_CLASS103 | PASS | PASS | 1 | 0 | WALK_1F_CLASS103 | 0 |
| AREA_1F_CLASS104 | PASS | PASS | 1 | 0 | WALK_1F_CLASS104 | 0 |
| AREA_1F_COURTYARD | EXCLUDED | EXCLUDED | 0 | N/A | WALK_1F_CORRIDOR_03 | 0 |
| AREA_1F_ELEVATOR | PARTIAL | PARTIAL | 0.270327 | 0.729673 | WALK_1F_CORRIDOR_01 | 0 |
| AREA_1F_LADYSROOM | MISSING | MISSING | 0 | 1 | WALK_1F_BATHROOM | 0 |
| AREA_1F_MAIN_ENTRANCE | PARTIAL | PARTIAL | 0.656214 | 0.343786 | WALK_1F_MAIN_ENTRANCE | 0 |
| AREA_1F_MEETINGROOM | PASS | PASS | 1 | 0 | WALK_1F_MEETINGROOM | 0 |
| AREA_1F_MENSROOM | MISSING | MISSING | 0 | 1 | WALK_1F_BATHROOM | 0 |
| AREA_1F_OFFICE | PARTIAL | PARTIAL | 0.296071 | 0.703929 | WALK_1F_AUDITORIUM_OFFICE_THRESHOLD | 0 |
| AREA_1F_RESTAURANT_A | PASS | PASS | 0.811376 | 0.188624 | WALK_1F_RESTAURANT_A | 0 |
| AREA_1F_RESTAURANT_B | PASS | PASS | 1 | 0 | WALK_1F_RESTAURANT_B | 0 |
| AREA_1F_SIDE_ENTRANCE | PASS | PASS | 0.917706 | 0.0822937 | WALK_1F_SIDE_ENTRANCE | 0 |
| AREA_1F_STORAGE | PASS | PASS | 0.817805 | 0.182195 | WALK_1F_STORAGE | 0 |
| AREA_2F_BALCONY_LEFT | EXCLUDED | EXCLUDED | 0 | N/A | WALK_2F_CORRIDOR_04 | 0 |
| AREA_2F_BALCONY_RIGHT | EXCLUDED | EXCLUDED | 0 | N/A | WALK_2F_CORRIDOR_02 | 0 |
| AREA_2F_CLASS201 | PASS | PASS | 1 | 0 | WALK_2F_CLASS201 | 0 |
| AREA_2F_CLASS202 | PASS | PASS | 1 | 0 | WALK_2F_CLASS202 | 0 |
| AREA_2F_CLASS203 | PASS | PASS | 1 | 0 | WALK_2F_CLASS203 | 0 |
| AREA_2F_CLASS204 | PASS | PASS | 1 | 0 | WALK_2F_CLASS204 | 0 |
| AREA_2F_ELEVATOR | PARTIAL | PARTIAL | 0.270327 | 0.729673 | WALK_2F_CORRIDOR_01 | 0 |
| AREA_2F_GALLERY | PASS | PASS | 0.847347 | 0.152653 | WALK_2F_GALLERY | 0 |
| AREA_2F_LADYSROOM | MISSING | MISSING | 0 | 1 | WALK_2F_BATHROOM | 0 |
| AREA_2F_MEETINGROOM | PASS | PASS | 0.897504 | 0.102496 | WALK_2F_GALLERY | 0 |
| AREA_2F_MENSROOM | MISSING | MISSING | 0 | 1 | WALK_2F_BATHROOM | 0 |
| AREA_2F_OFFICE | PARTIAL | PARTIAL | 0.296071 | 0.703929 | WALK_2F_OFFICE | 0 |
| AREA_STAIR_A | REVIEW | NOT_APPLICABLE | N/A | N/A | N/A | N/A |
| AREA_STAIR_B | REVIEW | NOT_APPLICABLE | N/A | N/A | N/A | N/A |

## Human review queue / 人工審查佇列

### HIGH (98)

- **SV-00001 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_LADYSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00002 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_MENSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00003 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_LADYSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00004 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_MENSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00005 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_1F_BATHROOM, PORTAL_1F_LADYSROOM — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00006 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_1F_BATHROOM, PORTAL_1F_MENSROOM — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00007 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_1F_MAIN_ENTRANCE_01, PORTAL_1F_MAIN_ENTRANCE — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00008 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_1F_MAIN_ENTRANCE_02, PORTAL_1F_MAIN_ENTRANCE — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00009 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_2F_BATHROOM, PORTAL_2F_LADYSROOM — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00010 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_2F_BATHROOM, PORTAL_2F_MENSROOM — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00011 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_2F_MEETINGROOM, PORTAL_2F_MEETINGROOM_01 — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00012 COLLIDER_CROSSES_PORTAL** [REVIEW] OBSTACLE_2F_MEETINGROOM, PORTAL_2F_MEETINGROOM_02 — Projected collider overlap crosses portal; review 3D aperture/contact semantics.
- **SV-00013 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_BATHROOM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00014 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_CORRIDOR_01_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00015 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_CORRIDOR_01_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00016 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_MAIN_ENTRANCE_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00017 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_MAIN_ENTRANCE_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00018 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_OFFICE_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00019 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_OFFICE_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00020 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_RESTAURANT_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00021 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_RESTAURANT_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00022 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_RESTAURANT_03 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00023 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_STORAGE01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00024 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_STORAGE02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00025 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_1F_STORAGE03 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00026 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_2F_BATHROOM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00027 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_2F_GALLERY_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00028 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_2F_GALLERY_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00029 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_2F_MEETINGROOM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00030 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_2F_OFFICE_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00031 FLOOR_GEOMETRY_OFFSET** [ERROR] OBSTACLE_2F_OFFICE_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00032 FLOOR_GEOMETRY_OFFSET** [ERROR] STAIR_A_ENTRY — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00033 FLOOR_GEOMETRY_OFFSET** [ERROR] STAIR_A_EXIT — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00034 FLOOR_GEOMETRY_OFFSET** [ERROR] STAIR_B_ENTRY — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00035 FLOOR_GEOMETRY_OFFSET** [ERROR] STAIR_B_EXIT — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00036 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_AUDITORIUM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00037 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_AUDITORIUM_OFFICE_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00038 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_AUDITORIUM_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00039 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_BATHROOM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00040 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS101 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00041 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS101_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00042 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS102 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00043 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS102_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00044 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS103 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00045 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS103_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00046 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS104 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00047 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CLASS104_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00048 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CORRIDOR_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00049 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CORRIDOR_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00050 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CORRIDOR_03 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00051 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_CORRIDOR_04 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00052 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_MAIN_ENTRANCE — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00053 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_MEETINGROOM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00054 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_MEETINGROOM_01_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00055 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_OFFICE — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00056 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_OFFICE_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00057 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_RESTAURANT_A — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00058 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_RESTAURANT_A_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00059 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_RESTAURANT_B — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00060 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_RESTAURANT_B_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00061 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_SIDE_ENTRANCE — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00062 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_STORAGE — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00063 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_1F_STORAGE_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00064 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_BATHROOM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00065 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS201 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00066 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS201_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00067 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS202 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00068 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS202_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00069 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS203 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00070 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS203_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00071 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS204 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00072 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CLASS204_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00073 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CORRIDOR_01 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00074 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CORRIDOR_02 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00075 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CORRIDOR_03 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00076 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_CORRIDOR_04 — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00077 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_GALLERY — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00078 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_GALLERY_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00079 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_MEETINGROOM — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00080 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_MEETINGROOM_01_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00081 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_MEETINGROOM_02_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00082 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_OFFICE — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00083 FLOOR_GEOMETRY_OFFSET** [ERROR] WALK_2F_OFFICE_THRESHOLD — Declared floor and geometry differ beyond configured height tolerance.
- **SV-00084 ISOLATED_STAIR** [REVIEW] STAIR_A_ENTRY, STAIR_A_EXIT, STAIR_A_PATH — No stair endpoint touches any same-floor walkable.
- **SV-00085 MISSING_WALL_LABELS** [MISSING] Scene — No explicit WALL_* objects or semantic collection members.
- **SV-00086 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_LADYSROOM — No nearby same-floor walkable.
- **SV-00087 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MENSROOM — No nearby same-floor walkable.
- **SV-00088 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_LADYSROOM — No nearby same-floor walkable.
- **SV-00089 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_MENSROOM — No nearby same-floor walkable.
- **SV-00090 PORTAL_IN_NONWALKABLE_REGION** [REVIEW] PORTAL_2F_BALCONY_LEFT — Portal is near walkable but its explicit side probes are inaccessible.
- **SV-00091 PORTAL_IN_NONWALKABLE_REGION** [REVIEW] PORTAL_2F_BALCONY_RIGHT — Portal is near walkable but its explicit side probes are inaccessible.
- **SV-00092 STAIR_ENTRY_DISCONNECTED** [MISSING] STAIR_A_ENTRY — Stair endpoint does not touch declared-floor walkable.
- **SV-00093 STAIR_EXIT_DISCONNECTED** [MISSING] STAIR_A_EXIT — Stair endpoint does not touch declared-floor walkable.
- **SV-00094 STAIR_EXIT_DISCONNECTED** [MISSING] STAIR_B_EXIT — Stair endpoint does not touch declared-floor walkable.
- **SV-00095 STAIR_PATH_CONTINUITY_UNRESOLVED** [REVIEW] STAIR_A_ENTRY, STAIR_A_EXIT, STAIR_A_PATH — Mesh/AABB alone does not declare ordered stair traversal; explicit path_points_m required.
- **SV-00096 STAIR_PATH_CONTINUITY_UNRESOLVED** [REVIEW] STAIR_B_ENTRY, STAIR_B_EXIT, STAIR_B_PATH — Mesh/AABB alone does not declare ordered stair traversal; explicit path_points_m required.
- **SV-00097 STAIR_SLAB_OPENING_REVIEW** [REVIEW] STAIR_A_ENTRY, STAIR_A_EXIT, STAIR_A_PATH — Slab opening needs explicit human PASS/FAIL review.
- **SV-00098 STAIR_SLAB_OPENING_REVIEW** [REVIEW] STAIR_B_ENTRY, STAIR_B_EXIT, STAIR_B_PATH — Slab opening needs explicit human PASS/FAIL review.

### MEDIUM (208)

- **SV-00099 AREA_CROSS_FLOOR_REVIEW** [REVIEW] AREA_STAIR_A — Cross-floor AREA defers traversal to explicit stair diagnostics; semantic intent does not approve floor or stair connectivity.
- **SV-00100 AREA_CROSS_FLOOR_REVIEW** [REVIEW] AREA_STAIR_B — Cross-floor AREA defers traversal to explicit stair diagnostics; semantic intent does not approve floor or stair connectivity.
- **SV-00101 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_1F_ELEVATOR — Area coverage is below diagnostic pass threshold.
- **SV-00102 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_1F_MAIN_ENTRANCE — Area coverage is below diagnostic pass threshold.
- **SV-00103 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_1F_OFFICE — Area coverage is below diagnostic pass threshold.
- **SV-00104 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_2F_ELEVATOR — Area coverage is below diagnostic pass threshold.
- **SV-00105 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_2F_OFFICE — Area coverage is below diagnostic pass threshold.
- **SV-00106 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_AUDITORIUM_FRONT — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00107 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_AUDITORIUM_REAR — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00108 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_BATHROOM — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00109 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CLASS101 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00110 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CLASS102 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00111 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CLASS103 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00112 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CLASS104 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00113 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CORRIDOR_01 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00114 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CORRIDOR_02 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00115 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CORRIDOR_03 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00116 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_CORRIDOR_04 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00117 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_MAIN_ENTRANCE — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00118 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_MEETINGROOM — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00119 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_RESTAURANT_01 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00120 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_RESTAURANT_02 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00121 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_SIDE_ENTRANCE — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00122 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_1F_STORAGE — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00123 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_BATHROOM — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00124 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CLASS201 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00125 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CLASS202 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00126 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CLASS203 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00127 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CLASS204 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00128 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CORRIDOR_01 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00129 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CORRIDOR_02 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00130 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CORRIDOR_03 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00131 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_CORRIDOR_04 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00132 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_GALLERY_01 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00133 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_GALLERY_02 — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00134 CAMERA_PLANE_BINDING_REVIEW** [REVIEW] CAM_2F_MEETINGROOM — Floor label and camera position do not approve camera-to-plane binding.
- **SV-00135 ENDPOINT_ACCESSIBILITY_UNRESOLVED** [REVIEW] Scene — No explicit navigation endpoint declarations.
- **SV-00136 GIANT_GEOMETRY** [REVIEW] AREA_1F_AUDITORIUM — Object exceeds configured maximum diagnostic extent.
- **SV-00137 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS101 — Object exceeds configured maximum diagnostic extent.
- **SV-00138 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS102 — Object exceeds configured maximum diagnostic extent.
- **SV-00139 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS103 — Object exceeds configured maximum diagnostic extent.
- **SV-00140 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS104 — Object exceeds configured maximum diagnostic extent.
- **SV-00141 GIANT_GEOMETRY** [REVIEW] AREA_1F_COURTYARD — Object exceeds configured maximum diagnostic extent.
- **SV-00142 GIANT_GEOMETRY** [REVIEW] AREA_1F_ELEVATOR — Object exceeds configured maximum diagnostic extent.
- **SV-00143 GIANT_GEOMETRY** [REVIEW] AREA_1F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00144 GIANT_GEOMETRY** [REVIEW] AREA_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00145 GIANT_GEOMETRY** [REVIEW] AREA_1F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00146 GIANT_GEOMETRY** [REVIEW] AREA_1F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00147 GIANT_GEOMETRY** [REVIEW] AREA_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00148 GIANT_GEOMETRY** [REVIEW] AREA_1F_RESTAURANT_A — Object exceeds configured maximum diagnostic extent.
- **SV-00149 GIANT_GEOMETRY** [REVIEW] AREA_1F_RESTAURANT_B — Object exceeds configured maximum diagnostic extent.
- **SV-00150 GIANT_GEOMETRY** [REVIEW] AREA_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00151 GIANT_GEOMETRY** [REVIEW] AREA_1F_STORAGE — Object exceeds configured maximum diagnostic extent.
- **SV-00152 GIANT_GEOMETRY** [REVIEW] AREA_2F_BALCONY_LEFT — Object exceeds configured maximum diagnostic extent.
- **SV-00153 GIANT_GEOMETRY** [REVIEW] AREA_2F_BALCONY_RIGHT — Object exceeds configured maximum diagnostic extent.
- **SV-00154 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS201 — Object exceeds configured maximum diagnostic extent.
- **SV-00155 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS202 — Object exceeds configured maximum diagnostic extent.
- **SV-00156 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS203 — Object exceeds configured maximum diagnostic extent.
- **SV-00157 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS204 — Object exceeds configured maximum diagnostic extent.
- **SV-00158 GIANT_GEOMETRY** [REVIEW] AREA_2F_ELEVATOR — Object exceeds configured maximum diagnostic extent.
- **SV-00159 GIANT_GEOMETRY** [REVIEW] AREA_2F_GALLERY — Object exceeds configured maximum diagnostic extent.
- **SV-00160 GIANT_GEOMETRY** [REVIEW] AREA_2F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00161 GIANT_GEOMETRY** [REVIEW] AREA_2F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00162 GIANT_GEOMETRY** [REVIEW] AREA_2F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00163 GIANT_GEOMETRY** [REVIEW] AREA_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00164 GIANT_GEOMETRY** [REVIEW] AREA_STAIR_A — Object exceeds configured maximum diagnostic extent.
- **SV-00165 GIANT_GEOMETRY** [REVIEW] AREA_STAIR_B — Object exceeds configured maximum diagnostic extent.
- **SV-00166 GIANT_GEOMETRY** [REVIEW] OBSTACLE_1F_BATHROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00167 GIANT_GEOMETRY** [REVIEW] OBSTACLE_1F_MAIN_ENTRANCE_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00168 GIANT_GEOMETRY** [REVIEW] OBSTACLE_1F_OFFICE_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00169 GIANT_GEOMETRY** [REVIEW] OBSTACLE_1F_OFFICE_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00170 GIANT_GEOMETRY** [REVIEW] OBSTACLE_1F_RESTAURANT_03 — Object exceeds configured maximum diagnostic extent.
- **SV-00171 GIANT_GEOMETRY** [REVIEW] OBSTACLE_2F_BATHROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00172 GIANT_GEOMETRY** [REVIEW] OBSTACLE_2F_GALLERY_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00173 GIANT_GEOMETRY** [REVIEW] OBSTACLE_2F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00174 GIANT_GEOMETRY** [REVIEW] OBSTACLE_2F_OFFICE_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00175 GIANT_GEOMETRY** [REVIEW] OBSTACLE_2F_OFFICE_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00176 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_AUDITORIUM — Object exceeds configured maximum diagnostic extent.
- **SV-00177 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_AUDITORIUM_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00178 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS101 — Object exceeds configured maximum diagnostic extent.
- **SV-00179 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS102 — Object exceeds configured maximum diagnostic extent.
- **SV-00180 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS103 — Object exceeds configured maximum diagnostic extent.
- **SV-00181 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS104 — Object exceeds configured maximum diagnostic extent.
- **SV-00182 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00183 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00184 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MEETINGROOM_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00185 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MEETINGROOM_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00186 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00187 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00188 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_RESTAURANT_A — Object exceeds configured maximum diagnostic extent.
- **SV-00189 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_RESTAURANT_B — Object exceeds configured maximum diagnostic extent.
- **SV-00190 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00191 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_STORAGE — Object exceeds configured maximum diagnostic extent.
- **SV-00192 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_BALCONY_LEFT — Object exceeds configured maximum diagnostic extent.
- **SV-00193 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_BALCONY_RIGHT — Object exceeds configured maximum diagnostic extent.
- **SV-00194 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS201 — Object exceeds configured maximum diagnostic extent.
- **SV-00195 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS202 — Object exceeds configured maximum diagnostic extent.
- **SV-00196 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS203 — Object exceeds configured maximum diagnostic extent.
- **SV-00197 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS204 — Object exceeds configured maximum diagnostic extent.
- **SV-00198 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_GALLERY — Object exceeds configured maximum diagnostic extent.
- **SV-00199 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00200 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MEETINGROOM_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00201 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MEETINGROOM_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00202 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00203 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00204 GIANT_GEOMETRY** [REVIEW] STAIR_A_PATH — Object exceeds configured maximum diagnostic extent.
- **SV-00205 GIANT_GEOMETRY** [REVIEW] STAIR_B_PATH — Object exceeds configured maximum diagnostic extent.
- **SV-00206 GIANT_GEOMETRY** [REVIEW] WALK_1F_AUDITORIUM — Object exceeds configured maximum diagnostic extent.
- **SV-00207 GIANT_GEOMETRY** [REVIEW] WALK_1F_BATHROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00208 GIANT_GEOMETRY** [REVIEW] WALK_1F_CLASS101 — Object exceeds configured maximum diagnostic extent.
- **SV-00209 GIANT_GEOMETRY** [REVIEW] WALK_1F_CLASS102 — Object exceeds configured maximum diagnostic extent.
- **SV-00210 GIANT_GEOMETRY** [REVIEW] WALK_1F_CLASS103 — Object exceeds configured maximum diagnostic extent.
- **SV-00211 GIANT_GEOMETRY** [REVIEW] WALK_1F_CLASS104 — Object exceeds configured maximum diagnostic extent.
- **SV-00212 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00213 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00214 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_03 — Object exceeds configured maximum diagnostic extent.
- **SV-00215 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_04 — Object exceeds configured maximum diagnostic extent.
- **SV-00216 GIANT_GEOMETRY** [REVIEW] WALK_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00217 GIANT_GEOMETRY** [REVIEW] WALK_1F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00218 GIANT_GEOMETRY** [REVIEW] WALK_1F_MEETINGROOM_01_THRESHOLD — Object exceeds configured maximum diagnostic extent.
- **SV-00219 GIANT_GEOMETRY** [REVIEW] WALK_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00220 GIANT_GEOMETRY** [REVIEW] WALK_1F_RESTAURANT_A — Object exceeds configured maximum diagnostic extent.
- **SV-00221 GIANT_GEOMETRY** [REVIEW] WALK_1F_RESTAURANT_B — Object exceeds configured maximum diagnostic extent.
- **SV-00222 GIANT_GEOMETRY** [REVIEW] WALK_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00223 GIANT_GEOMETRY** [REVIEW] WALK_1F_STORAGE — Object exceeds configured maximum diagnostic extent.
- **SV-00224 GIANT_GEOMETRY** [REVIEW] WALK_2F_BATHROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00225 GIANT_GEOMETRY** [REVIEW] WALK_2F_CLASS201 — Object exceeds configured maximum diagnostic extent.
- **SV-00226 GIANT_GEOMETRY** [REVIEW] WALK_2F_CLASS202 — Object exceeds configured maximum diagnostic extent.
- **SV-00227 GIANT_GEOMETRY** [REVIEW] WALK_2F_CLASS203 — Object exceeds configured maximum diagnostic extent.
- **SV-00228 GIANT_GEOMETRY** [REVIEW] WALK_2F_CLASS204 — Object exceeds configured maximum diagnostic extent.
- **SV-00229 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00230 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00231 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_03 — Object exceeds configured maximum diagnostic extent.
- **SV-00232 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_04 — Object exceeds configured maximum diagnostic extent.
- **SV-00233 GIANT_GEOMETRY** [REVIEW] WALK_2F_GALLERY — Object exceeds configured maximum diagnostic extent.
- **SV-00234 GIANT_GEOMETRY** [REVIEW] WALK_2F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00235 GIANT_GEOMETRY** [REVIEW] WALK_2F_MEETINGROOM_02_THRESHOLD — Object exceeds configured maximum diagnostic extent.
- **SV-00236 GIANT_GEOMETRY** [REVIEW] WALK_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00237 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_AUDITORIUM — Semantic object is hidden or disabled.
- **SV-00238 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS101 — Semantic object is hidden or disabled.
- **SV-00239 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS102 — Semantic object is hidden or disabled.
- **SV-00240 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS103 — Semantic object is hidden or disabled.
- **SV-00241 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS104 — Semantic object is hidden or disabled.
- **SV-00242 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_COURTYARD — Semantic object is hidden or disabled.
- **SV-00243 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_ELEVATOR — Semantic object is hidden or disabled.
- **SV-00244 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00245 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MAIN_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00246 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MEETINGROOM — Semantic object is hidden or disabled.
- **SV-00247 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00248 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_OFFICE — Semantic object is hidden or disabled.
- **SV-00249 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_RESTAURANT_A — Semantic object is hidden or disabled.
- **SV-00250 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_RESTAURANT_B — Semantic object is hidden or disabled.
- **SV-00251 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_SIDE_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00252 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_STORAGE — Semantic object is hidden or disabled.
- **SV-00253 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_BALCONY_LEFT — Semantic object is hidden or disabled.
- **SV-00254 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_BALCONY_RIGHT — Semantic object is hidden or disabled.
- **SV-00255 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS201 — Semantic object is hidden or disabled.
- **SV-00256 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS202 — Semantic object is hidden or disabled.
- **SV-00257 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS203 — Semantic object is hidden or disabled.
- **SV-00258 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS204 — Semantic object is hidden or disabled.
- **SV-00259 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_ELEVATOR — Semantic object is hidden or disabled.
- **SV-00260 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_GALLERY — Semantic object is hidden or disabled.
- **SV-00261 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00262 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_MEETINGROOM — Semantic object is hidden or disabled.
- **SV-00263 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00264 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_OFFICE — Semantic object is hidden or disabled.
- **SV-00265 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_STAIR_A — Semantic object is hidden or disabled.
- **SV-00266 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_STAIR_B — Semantic object is hidden or disabled.
- **SV-00267 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_AUDITORIUM — Semantic object is hidden or disabled.
- **SV-00268 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_AUDITORIUM_OFFICE — Semantic object is hidden or disabled.
- **SV-00269 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS101 — Semantic object is hidden or disabled.
- **SV-00270 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS102 — Semantic object is hidden or disabled.
- **SV-00271 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS103 — Semantic object is hidden or disabled.
- **SV-00272 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS104 — Semantic object is hidden or disabled.
- **SV-00273 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00274 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MAIN_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00275 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MEETINGROOM_01 — Semantic object is hidden or disabled.
- **SV-00276 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MEETINGROOM_02 — Semantic object is hidden or disabled.
- **SV-00277 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00278 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_OFFICE — Semantic object is hidden or disabled.
- **SV-00279 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_RESTAURANT_A — Semantic object is hidden or disabled.
- **SV-00280 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_RESTAURANT_B — Semantic object is hidden or disabled.
- **SV-00281 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00282 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_STORAGE — Semantic object is hidden or disabled.
- **SV-00283 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_BALCONY_LEFT — Semantic object is hidden or disabled.
- **SV-00284 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_BALCONY_RIGHT — Semantic object is hidden or disabled.
- **SV-00285 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS201 — Semantic object is hidden or disabled.
- **SV-00286 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS202 — Semantic object is hidden or disabled.
- **SV-00287 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS203 — Semantic object is hidden or disabled.
- **SV-00288 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS204 — Semantic object is hidden or disabled.
- **SV-00289 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_GALLERY — Semantic object is hidden or disabled.
- **SV-00290 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00291 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MEETINGROOM_01 — Semantic object is hidden or disabled.
- **SV-00292 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MEETINGROOM_02 — Semantic object is hidden or disabled.
- **SV-00293 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00294 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_OFFICE — Semantic object is hidden or disabled.
- **SV-00295 ISOLATED_WALKABLE** [REVIEW] WALK_1F_SIDE_ENTRANCE — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00296 LARGE_SAME_FLOOR_DISCONNECTION** [REVIEW] WALK_1F_AUDITORIUM, WALK_1F_AUDITORIUM_OFFICE_THRESHOLD, WALK_1F_AUDITORIUM_THRESHOLD, WALK_1F_BATHROOM, WALK_1F_CORRIDOR_01, WALK_1F_CORRIDOR_02, WALK_1F_CORRIDOR_03, WALK_1F_CORRIDOR_04, WALK_1F_MAIN_ENTRANCE, WALK_1F_OFFICE, WALK_1F_OFFICE_THRESHOLD, WALK_1F_STORAGE, WALK_1F_STORAGE_THRESHOLD, WALK_1F_CLASS101, WALK_1F_CLASS101_THRESHOLD, WALK_1F_CLASS102, WALK_1F_CLASS102_THRESHOLD, WALK_1F_CLASS103, WALK_1F_CLASS103_THRESHOLD, WALK_1F_CLASS104, WALK_1F_CLASS104_THRESHOLD, WALK_1F_MEETINGROOM, WALK_1F_MEETINGROOM_01_THRESHOLD, WALK_1F_RESTAURANT_A, WALK_1F_RESTAURANT_A_THRESHOLD, WALK_1F_RESTAURANT_B, WALK_1F_RESTAURANT_B_THRESHOLD, WALK_1F_SIDE_ENTRANCE — Large same-floor components are disconnected; not automatically an error.
- **SV-00297 LARGE_SAME_FLOOR_DISCONNECTION** [REVIEW] WALK_2F_BATHROOM, WALK_2F_CORRIDOR_01, WALK_2F_CORRIDOR_02, WALK_2F_CORRIDOR_03, WALK_2F_CORRIDOR_04, WALK_2F_GALLERY, WALK_2F_GALLERY_THRESHOLD, WALK_2F_MEETINGROOM, WALK_2F_MEETINGROOM_01_THRESHOLD, WALK_2F_MEETINGROOM_02_THRESHOLD, WALK_2F_OFFICE, WALK_2F_OFFICE_THRESHOLD, WALK_2F_CLASS201, WALK_2F_CLASS201_THRESHOLD, WALK_2F_CLASS202, WALK_2F_CLASS202_THRESHOLD, WALK_2F_CLASS203, WALK_2F_CLASS203_THRESHOLD, WALK_2F_CLASS204, WALK_2F_CLASS204_THRESHOLD — Large same-floor components are disconnected; not automatically an error.
- **SV-00298 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_1F_MEETINGROOM_02 — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00299 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00300 STAIR_CLEARANCE_UNRESOLVED** [REVIEW] STAIR_A_ENTRY, STAIR_A_EXIT, STAIR_A_PATH — Physical clearance policy/measurement is missing; no mesh-derived clearance claimed.
- **SV-00301 STAIR_CLEARANCE_UNRESOLVED** [REVIEW] STAIR_B_ENTRY, STAIR_B_EXIT, STAIR_B_PATH — Physical clearance policy/measurement is missing; no mesh-derived clearance claimed.
- **SV-00302 UNRESOLVED_SETTING** [REVIEW] Scene — building-wide collider completeness and physical authority
- **SV-00303 UNRESOLVED_SETTING** [REVIEW] Scene — camera-plane binding
- **SV-00304 UNRESOLVED_SETTING** [REVIEW] Scene — unclassified source movement/occlusion ownership
- **SV-00305 UNRESOLVED_SETTING** [REVIEW] Scene — portal source aperture/normal and endpoint declarations
- **SV-00306 UNRESOLVED_SETTING** [REVIEW] Scene — stair actual run/landing/opening and bidirectional body-clearance evidence

### LOW (69)

- **SV-00307 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_BATHROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00308 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_CORRIDOR_01_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00309 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_CORRIDOR_01_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00310 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_MAIN_ENTRANCE_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00311 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_MAIN_ENTRANCE_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00312 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_OFFICE_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00313 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_OFFICE_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00314 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_RESTAURANT_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00315 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_RESTAURANT_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00316 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_RESTAURANT_03 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00317 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_STORAGE01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00318 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_STORAGE02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00319 NON_MANIFOLD** [REVIEW] OBSTACLE_1F_STORAGE03 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00320 NON_MANIFOLD** [REVIEW] OBSTACLE_2F_BATHROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00321 NON_MANIFOLD** [REVIEW] OBSTACLE_2F_GALLERY_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00322 NON_MANIFOLD** [REVIEW] OBSTACLE_2F_GALLERY_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00323 NON_MANIFOLD** [REVIEW] OBSTACLE_2F_MEETINGROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00324 NON_MANIFOLD** [REVIEW] OBSTACLE_2F_OFFICE_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00325 NON_MANIFOLD** [REVIEW] OBSTACLE_2F_OFFICE_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00326 NON_MANIFOLD** [REVIEW] STAIR_A_PATH — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00327 NON_MANIFOLD** [REVIEW] STAIR_B_PATH — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00328 NON_MANIFOLD** [REVIEW] WALK_1F_AUDITORIUM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00329 NON_MANIFOLD** [REVIEW] WALK_1F_AUDITORIUM_OFFICE_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00330 NON_MANIFOLD** [REVIEW] WALK_1F_AUDITORIUM_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00331 NON_MANIFOLD** [REVIEW] WALK_1F_BATHROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00332 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS101 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00333 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS101_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00334 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS102 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00335 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS102_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00336 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS103 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00337 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS103_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00338 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS104 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00339 NON_MANIFOLD** [REVIEW] WALK_1F_CLASS104_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00340 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00341 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00342 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_03 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00343 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_04 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00344 NON_MANIFOLD** [REVIEW] WALK_1F_MAIN_ENTRANCE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00345 NON_MANIFOLD** [REVIEW] WALK_1F_MEETINGROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00346 NON_MANIFOLD** [REVIEW] WALK_1F_MEETINGROOM_01_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00347 NON_MANIFOLD** [REVIEW] WALK_1F_OFFICE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00348 NON_MANIFOLD** [REVIEW] WALK_1F_OFFICE_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00349 NON_MANIFOLD** [REVIEW] WALK_1F_RESTAURANT_A — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00350 NON_MANIFOLD** [REVIEW] WALK_1F_RESTAURANT_A_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00351 NON_MANIFOLD** [REVIEW] WALK_1F_RESTAURANT_B — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00352 NON_MANIFOLD** [REVIEW] WALK_1F_RESTAURANT_B_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00353 NON_MANIFOLD** [REVIEW] WALK_1F_SIDE_ENTRANCE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00354 NON_MANIFOLD** [REVIEW] WALK_1F_STORAGE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00355 NON_MANIFOLD** [REVIEW] WALK_1F_STORAGE_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00356 NON_MANIFOLD** [REVIEW] WALK_2F_BATHROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00357 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS201 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00358 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS201_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00359 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS202 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00360 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS202_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00361 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS203 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00362 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS203_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00363 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS204 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00364 NON_MANIFOLD** [REVIEW] WALK_2F_CLASS204_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00365 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00366 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00367 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_03 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00368 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_04 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00369 NON_MANIFOLD** [REVIEW] WALK_2F_GALLERY — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00370 NON_MANIFOLD** [REVIEW] WALK_2F_GALLERY_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00371 NON_MANIFOLD** [REVIEW] WALK_2F_MEETINGROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00372 NON_MANIFOLD** [REVIEW] WALK_2F_MEETINGROOM_01_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00373 NON_MANIFOLD** [REVIEW] WALK_2F_MEETINGROOM_02_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00374 NON_MANIFOLD** [REVIEW] WALK_2F_OFFICE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00375 NON_MANIFOLD** [REVIEW] WALK_2F_OFFICE_THRESHOLD — Non-manifold edges reported; this does not invalidate a surface.

## Limits / 診斷限制

- Diagnostic graph never creates or approves inference topology, stair edges or floor authority.
- XY mesh footprints preserve holes but cannot certify swept-body clearance or 3D collision.
- AABB-only representations are broad-phase evidence and require human review.
- All thresholds are diagnostic heuristics until adopted by explicit research review.
