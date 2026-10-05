# Semantic completeness diagnostics / 場景語意完整度診斷

Status: **REVIEW_REQUIRED**. Authority: **HEURISTIC / REVIEW** until source-bound approval.

原始場景不修改；不建立 Graph／stair connectivity、不猜測未標記幾何。
Source is preserved; no inferred physical roles or inference topology are created.

## Floor summary / 每層摘要

| Floor | AREA | WALKABLE | WALL | OBSTACLE | STAIR | PORTAL | Components | Isolated | Uncovered | Suspicious portals | Conflicts | Geometry warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1F | 16 | 8 | 0 | 0 | 0 | 16 | 3 | 2 | 14 | 16 | 0 | 81 |
| 2F | 12 | 6 | 0 | 0 | 0 | 12 | 2 | 1 | 12 | 12 | 0 | 61 |
| UNASSIGNED | 2 | 4 | 0 | 0 | 0 | 0 | 4 | 4 | 2 | 0 | 2 | 12 |

## AREA coverage / 區域覆蓋

| AREA | Status | Geometric coverage | Overlap ratio | Uncovered | Nearest WALKABLE | Offset m |
| --- | --- | --- | ---: | ---: | --- | ---: |
| AREA_1F_AUDITORIUM | MISSING | MISSING | 0 | 1 | WALK_1F_SIDE_ENTRANCE | 0 |
| AREA_1F_CLASS101 | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_04 | 0 |
| AREA_1F_CLASS102 | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_04 | 0 |
| AREA_1F_CLASS103 | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_04 | 0 |
| AREA_1F_CLASS104 | MISSING | MISSING | 0 | 1 | WALK_1F_BATHROOM | 0 |
| AREA_1F_COURTYARD | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_03 | 0 |
| AREA_1F_ELEVATOR | REVIEW | PARTIAL | 0.270327 | 0.729673 | WALK_1F_CORRIDOR_01 | 0 |
| AREA_1F_LADYSROOM | MISSING | MISSING | 0 | 1 | WALK_1F_BATHROOM | 0 |
| AREA_1F_MAIN_ENTRANCE | REVIEW | PASS | 0.958123 | 0.0418768 | WALK_1F_MAIN_ENTRANCE | 0 |
| AREA_1F_MEETINGROOM | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_02 | 0 |
| AREA_1F_MENSROOM | MISSING | MISSING | 0 | 1 | WALK_1F_BATHROOM | 0 |
| AREA_1F_OFFICE | REVIEW | PARTIAL | 0.205742 | 0.794258 | WALK_1F_OFFICE | 0 |
| AREA_1F_RESTAURANT_A | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_01 | 0 |
| AREA_1F_RESTAURANT_B | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_01 | 0 |
| AREA_1F_SIDE_ENTRANCE | REVIEW | PASS | 0.917706 | 0.0822937 | WALK_1F_SIDE_ENTRANCE | 0 |
| AREA_1F_STORAGE | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_02 | 0 |
| AREA_2F_BALCONY_LEFT | MISSING | MISSING | 0 | 1 | WALK_2F_CORRIDOR_04 | 0 |
| AREA_2F_BALCONY_RIGHT | MISSING | MISSING | 0 | 1 | WALK_2F_CORRIDOR_02 | 0 |
| AREA_2F_CLASS201 | MISSING | MISSING | 0 | 1 | WALK_2F_CORRIDOR_04 | 0 |
| AREA_2F_CLASS202 | MISSING | MISSING | 0 | 1 | WALK_2F_CORRIDOR_04 | 0 |
| AREA_2F_CLASS203 | MISSING | MISSING | 0 | 1 | WALK_2F_CORRIDOR_04 | 0 |
| AREA_2F_CLASS204 | MISSING | MISSING | 0 | 1 | WALK_2F_BATHROOM | 0 |
| AREA_2F_ELEVATOR | REVIEW | PARTIAL | 0.270327 | 0.729673 | WALK_2F_CORRIDOR_01 | 0 |
| AREA_2F_GALLERY | MISSING | MISSING | 0 | 1 | WALK_2F_CORRIDOR_01 | 0 |
| AREA_2F_LADYSROOM | MISSING | MISSING | 0 | 1 | WALK_2F_BATHROOM | 0 |
| AREA_2F_MEETINGROOM | MISSING | MISSING | 0 | 1 | WALK_2F_CORRIDOR_02 | 0 |
| AREA_2F_MENSROOM | MISSING | MISSING | 0 | 1 | WALK_2F_BATHROOM | 0 |
| AREA_2F_OFFICE | REVIEW | PARTIAL | 0.205742 | 0.794258 | WALK_2F_OFFICE | 0 |
| AREA_STAIR_A | MISSING | MISSING | 0 | 1 | WALK_STAIRS_A_LOWERHALF | 0 |
| AREA_STAIR_B | MISSING | MISSING | 0 | 1 | WALK_1F_CORRIDOR_04 | 0 |

## Human review queue / 人工審查佇列

### HIGH (49)

- **SV-00001 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_AUDITORIUM — Area has no sufficient same-floor walkable overlap.
- **SV-00002 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS101 — Area has no sufficient same-floor walkable overlap.
- **SV-00003 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS102 — Area has no sufficient same-floor walkable overlap.
- **SV-00004 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS103 — Area has no sufficient same-floor walkable overlap.
- **SV-00005 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS104 — Area has no sufficient same-floor walkable overlap.
- **SV-00006 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_COURTYARD — Area has no sufficient same-floor walkable overlap.
- **SV-00007 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_LADYSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00008 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_MEETINGROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00009 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_MENSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00010 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_RESTAURANT_A — Area has no sufficient same-floor walkable overlap.
- **SV-00011 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_RESTAURANT_B — Area has no sufficient same-floor walkable overlap.
- **SV-00012 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_STORAGE — Area has no sufficient same-floor walkable overlap.
- **SV-00013 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_BALCONY_LEFT — Area has no sufficient same-floor walkable overlap.
- **SV-00014 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_BALCONY_RIGHT — Area has no sufficient same-floor walkable overlap.
- **SV-00015 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS201 — Area has no sufficient same-floor walkable overlap.
- **SV-00016 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS202 — Area has no sufficient same-floor walkable overlap.
- **SV-00017 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS203 — Area has no sufficient same-floor walkable overlap.
- **SV-00018 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS204 — Area has no sufficient same-floor walkable overlap.
- **SV-00019 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_GALLERY — Area has no sufficient same-floor walkable overlap.
- **SV-00020 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_LADYSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00021 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_MEETINGROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00022 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_MENSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00023 AREA_MISSING_WALKABLE** [MISSING] AREA_STAIR_A — Area has no sufficient same-floor walkable overlap.
- **SV-00024 AREA_MISSING_WALKABLE** [MISSING] AREA_STAIR_B — Area has no sufficient same-floor walkable overlap.
- **SV-00025 CONFLICTING_NAME_PREFIX** [ERROR] AREA_STAIR_A — Name contains conflicting semantic tokens.
- **SV-00026 CONFLICTING_NAME_PREFIX** [ERROR] AREA_STAIR_B — Name contains conflicting semantic tokens.
- **SV-00027 FLOOR_PLANE_AUTHORITY_UNRESOLVED** [REVIEW] Scene — No source-bound approved floor-plane configuration; floor results remain HEURISTIC.
- **SV-00028 MISSING_OBSTACLE_LABELS** [MISSING] Scene — No explicit OBSTACLE_* objects or semantic collection members.
- **SV-00029 MISSING_STAIR_LABELS** [MISSING] Scene — No explicit STAIR_* objects or semantic collection members.
- **SV-00030 MISSING_WALL_LABELS** [MISSING] Scene — No explicit WALL_* objects or semantic collection members.
- **SV-00031 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_AUDITORIUM_OFFICE — No nearby same-floor walkable.
- **SV-00032 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS101 — No nearby same-floor walkable.
- **SV-00033 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS102 — No nearby same-floor walkable.
- **SV-00034 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS103 — No nearby same-floor walkable.
- **SV-00035 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS104 — No nearby same-floor walkable.
- **SV-00036 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_LADYSROOM — No nearby same-floor walkable.
- **SV-00037 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MEETINGROOM_01 — No nearby same-floor walkable.
- **SV-00038 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MEETINGROOM_02 — No nearby same-floor walkable.
- **SV-00039 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MENSROOM — No nearby same-floor walkable.
- **SV-00040 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_RESTAURANT_A — No nearby same-floor walkable.
- **SV-00041 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_RESTAURANT_B — No nearby same-floor walkable.
- **SV-00042 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS201 — No nearby same-floor walkable.
- **SV-00043 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS202 — No nearby same-floor walkable.
- **SV-00044 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS203 — No nearby same-floor walkable.
- **SV-00045 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS204 — No nearby same-floor walkable.
- **SV-00046 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_LADYSROOM — No nearby same-floor walkable.
- **SV-00047 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_MEETINGROOM_01 — No nearby same-floor walkable.
- **SV-00048 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_MEETINGROOM_02 — No nearby same-floor walkable.
- **SV-00049 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_MENSROOM — No nearby same-floor walkable.

### MEDIUM (170)

- **SV-00050 AREA_COVERAGE_AUTHORITY_REVIEW** [REVIEW] AREA_1F_MAIN_ENTRANCE — Coverage evidence requires approved floor authority or a supported geometry representation.
- **SV-00051 AREA_COVERAGE_AUTHORITY_REVIEW** [REVIEW] AREA_1F_SIDE_ENTRANCE — Coverage evidence requires approved floor authority or a supported geometry representation.
- **SV-00052 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_1F_ELEVATOR — Area coverage is below diagnostic pass threshold.
- **SV-00053 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_1F_OFFICE — Area coverage is below diagnostic pass threshold.
- **SV-00054 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_2F_ELEVATOR — Area coverage is below diagnostic pass threshold.
- **SV-00055 AREA_PARTIAL_COVERAGE** [REVIEW] AREA_2F_OFFICE — Area coverage is below diagnostic pass threshold.
- **SV-00056 DUPLICATED_GEOMETRY** [REVIEW] PORTAL_1F_MENSROOM, PORTAL_2F_MENSROOM — Identical evaluated world geometry.
- **SV-00057 ENDPOINT_ACCESSIBILITY_UNRESOLVED** [REVIEW] Scene — No explicit navigation endpoint declarations.
- **SV-00058 GIANT_GEOMETRY** [REVIEW] AREA_1F_AUDITORIUM — Object exceeds configured maximum diagnostic extent.
- **SV-00059 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS101 — Object exceeds configured maximum diagnostic extent.
- **SV-00060 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS102 — Object exceeds configured maximum diagnostic extent.
- **SV-00061 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS103 — Object exceeds configured maximum diagnostic extent.
- **SV-00062 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS104 — Object exceeds configured maximum diagnostic extent.
- **SV-00063 GIANT_GEOMETRY** [REVIEW] AREA_1F_COURTYARD — Object exceeds configured maximum diagnostic extent.
- **SV-00064 GIANT_GEOMETRY** [REVIEW] AREA_1F_ELEVATOR — Object exceeds configured maximum diagnostic extent.
- **SV-00065 GIANT_GEOMETRY** [REVIEW] AREA_1F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00066 GIANT_GEOMETRY** [REVIEW] AREA_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00067 GIANT_GEOMETRY** [REVIEW] AREA_1F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00068 GIANT_GEOMETRY** [REVIEW] AREA_1F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00069 GIANT_GEOMETRY** [REVIEW] AREA_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00070 GIANT_GEOMETRY** [REVIEW] AREA_1F_RESTAURANT_A — Object exceeds configured maximum diagnostic extent.
- **SV-00071 GIANT_GEOMETRY** [REVIEW] AREA_1F_RESTAURANT_B — Object exceeds configured maximum diagnostic extent.
- **SV-00072 GIANT_GEOMETRY** [REVIEW] AREA_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00073 GIANT_GEOMETRY** [REVIEW] AREA_1F_STORAGE — Object exceeds configured maximum diagnostic extent.
- **SV-00074 GIANT_GEOMETRY** [REVIEW] AREA_2F_BALCONY_LEFT — Object exceeds configured maximum diagnostic extent.
- **SV-00075 GIANT_GEOMETRY** [REVIEW] AREA_2F_BALCONY_RIGHT — Object exceeds configured maximum diagnostic extent.
- **SV-00076 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS201 — Object exceeds configured maximum diagnostic extent.
- **SV-00077 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS202 — Object exceeds configured maximum diagnostic extent.
- **SV-00078 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS203 — Object exceeds configured maximum diagnostic extent.
- **SV-00079 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS204 — Object exceeds configured maximum diagnostic extent.
- **SV-00080 GIANT_GEOMETRY** [REVIEW] AREA_2F_ELEVATOR — Object exceeds configured maximum diagnostic extent.
- **SV-00081 GIANT_GEOMETRY** [REVIEW] AREA_2F_GALLERY — Object exceeds configured maximum diagnostic extent.
- **SV-00082 GIANT_GEOMETRY** [REVIEW] AREA_2F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00083 GIANT_GEOMETRY** [REVIEW] AREA_2F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00084 GIANT_GEOMETRY** [REVIEW] AREA_2F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00085 GIANT_GEOMETRY** [REVIEW] AREA_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00086 GIANT_GEOMETRY** [REVIEW] AREA_STAIR_A — Object exceeds configured maximum diagnostic extent.
- **SV-00087 GIANT_GEOMETRY** [REVIEW] AREA_STAIR_B — Object exceeds configured maximum diagnostic extent.
- **SV-00088 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_AUDITORIUM — Object exceeds configured maximum diagnostic extent.
- **SV-00089 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_AUDITORIUM_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00090 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS101 — Object exceeds configured maximum diagnostic extent.
- **SV-00091 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS102 — Object exceeds configured maximum diagnostic extent.
- **SV-00092 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS103 — Object exceeds configured maximum diagnostic extent.
- **SV-00093 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS104 — Object exceeds configured maximum diagnostic extent.
- **SV-00094 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00095 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00096 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MEETINGROOM_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00097 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MEETINGROOM_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00098 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00099 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00100 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_RESTAURANT_A — Object exceeds configured maximum diagnostic extent.
- **SV-00101 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_RESTAURANT_B — Object exceeds configured maximum diagnostic extent.
- **SV-00102 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00103 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_STORAGE — Object exceeds configured maximum diagnostic extent.
- **SV-00104 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_BALCONY_LEFT — Object exceeds configured maximum diagnostic extent.
- **SV-00105 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_BALCONY_RIGHT — Object exceeds configured maximum diagnostic extent.
- **SV-00106 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS201 — Object exceeds configured maximum diagnostic extent.
- **SV-00107 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS202 — Object exceeds configured maximum diagnostic extent.
- **SV-00108 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS203 — Object exceeds configured maximum diagnostic extent.
- **SV-00109 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS204 — Object exceeds configured maximum diagnostic extent.
- **SV-00110 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_GALLERY — Object exceeds configured maximum diagnostic extent.
- **SV-00111 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00112 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MEETINGROOM_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00113 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MEETINGROOM_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00114 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00115 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00116 GIANT_GEOMETRY** [REVIEW] WALK_1F_BATHROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00117 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00118 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00119 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_03 — Object exceeds configured maximum diagnostic extent.
- **SV-00120 GIANT_GEOMETRY** [REVIEW] WALK_1F_CORRIDOR_04 — Object exceeds configured maximum diagnostic extent.
- **SV-00121 GIANT_GEOMETRY** [REVIEW] WALK_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00122 GIANT_GEOMETRY** [REVIEW] WALK_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00123 GIANT_GEOMETRY** [REVIEW] WALK_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00124 GIANT_GEOMETRY** [REVIEW] WALK_2F_BATHROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00125 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00126 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00127 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_03 — Object exceeds configured maximum diagnostic extent.
- **SV-00128 GIANT_GEOMETRY** [REVIEW] WALK_2F_CORRIDOR_04 — Object exceeds configured maximum diagnostic extent.
- **SV-00129 GIANT_GEOMETRY** [REVIEW] WALK_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00130 GIANT_GEOMETRY** [REVIEW] WALK_STAIRS_A_LOWERHALF — Object exceeds configured maximum diagnostic extent.
- **SV-00131 GIANT_GEOMETRY** [REVIEW] WALK_STAIRS_A_UPPERHALF — Object exceeds configured maximum diagnostic extent.
- **SV-00132 GIANT_GEOMETRY** [REVIEW] WALK_STAIRS_B_LOWERHALF — Object exceeds configured maximum diagnostic extent.
- **SV-00133 GIANT_GEOMETRY** [REVIEW] WALK_STAIRS_B_UPPERHALF — Object exceeds configured maximum diagnostic extent.
- **SV-00134 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_AUDITORIUM — Semantic object is hidden or disabled.
- **SV-00135 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS101 — Semantic object is hidden or disabled.
- **SV-00136 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS102 — Semantic object is hidden or disabled.
- **SV-00137 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS103 — Semantic object is hidden or disabled.
- **SV-00138 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS104 — Semantic object is hidden or disabled.
- **SV-00139 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_COURTYARD — Semantic object is hidden or disabled.
- **SV-00140 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_ELEVATOR — Semantic object is hidden or disabled.
- **SV-00141 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00142 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MAIN_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00143 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MEETINGROOM — Semantic object is hidden or disabled.
- **SV-00144 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00145 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_OFFICE — Semantic object is hidden or disabled.
- **SV-00146 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_RESTAURANT_A — Semantic object is hidden or disabled.
- **SV-00147 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_RESTAURANT_B — Semantic object is hidden or disabled.
- **SV-00148 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_SIDE_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00149 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_STORAGE — Semantic object is hidden or disabled.
- **SV-00150 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_BALCONY_LEFT — Semantic object is hidden or disabled.
- **SV-00151 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_BALCONY_RIGHT — Semantic object is hidden or disabled.
- **SV-00152 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS201 — Semantic object is hidden or disabled.
- **SV-00153 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS202 — Semantic object is hidden or disabled.
- **SV-00154 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS203 — Semantic object is hidden or disabled.
- **SV-00155 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS204 — Semantic object is hidden or disabled.
- **SV-00156 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_ELEVATOR — Semantic object is hidden or disabled.
- **SV-00157 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_GALLERY — Semantic object is hidden or disabled.
- **SV-00158 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00159 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_MEETINGROOM — Semantic object is hidden or disabled.
- **SV-00160 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00161 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_OFFICE — Semantic object is hidden or disabled.
- **SV-00162 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_STAIR_A — Semantic object is hidden or disabled.
- **SV-00163 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_STAIR_B — Semantic object is hidden or disabled.
- **SV-00164 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_AUDITORIUM — Semantic object is hidden or disabled.
- **SV-00165 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_AUDITORIUM_OFFICE — Semantic object is hidden or disabled.
- **SV-00166 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS101 — Semantic object is hidden or disabled.
- **SV-00167 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS102 — Semantic object is hidden or disabled.
- **SV-00168 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS103 — Semantic object is hidden or disabled.
- **SV-00169 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS104 — Semantic object is hidden or disabled.
- **SV-00170 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00171 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MAIN_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00172 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MEETINGROOM_01 — Semantic object is hidden or disabled.
- **SV-00173 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MEETINGROOM_02 — Semantic object is hidden or disabled.
- **SV-00174 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00175 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_OFFICE — Semantic object is hidden or disabled.
- **SV-00176 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_RESTAURANT_A — Semantic object is hidden or disabled.
- **SV-00177 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_RESTAURANT_B — Semantic object is hidden or disabled.
- **SV-00178 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00179 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_STORAGE — Semantic object is hidden or disabled.
- **SV-00180 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_BALCONY_LEFT — Semantic object is hidden or disabled.
- **SV-00181 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_BALCONY_RIGHT — Semantic object is hidden or disabled.
- **SV-00182 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS201 — Semantic object is hidden or disabled.
- **SV-00183 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS202 — Semantic object is hidden or disabled.
- **SV-00184 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS203 — Semantic object is hidden or disabled.
- **SV-00185 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS204 — Semantic object is hidden or disabled.
- **SV-00186 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_GALLERY — Semantic object is hidden or disabled.
- **SV-00187 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00188 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MEETINGROOM_01 — Semantic object is hidden or disabled.
- **SV-00189 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MEETINGROOM_02 — Semantic object is hidden or disabled.
- **SV-00190 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00191 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_OFFICE — Semantic object is hidden or disabled.
- **SV-00192 ISOLATED_WALKABLE** [REVIEW] WALK_1F_OFFICE — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00193 ISOLATED_WALKABLE** [REVIEW] WALK_1F_SIDE_ENTRANCE — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00194 ISOLATED_WALKABLE** [REVIEW] WALK_2F_OFFICE — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00195 ISOLATED_WALKABLE** [REVIEW] WALK_STAIRS_A_LOWERHALF — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00196 ISOLATED_WALKABLE** [REVIEW] WALK_STAIRS_A_UPPERHALF — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00197 ISOLATED_WALKABLE** [REVIEW] WALK_STAIRS_B_LOWERHALF — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00198 ISOLATED_WALKABLE** [REVIEW] WALK_STAIRS_B_UPPERHALF — Walkable has no same-floor geometric neighbor; isolation can be intentional.
- **SV-00199 LARGE_SAME_FLOOR_DISCONNECTION** [REVIEW] WALK_1F_BATHROOM, WALK_1F_CORRIDOR_01, WALK_1F_CORRIDOR_02, WALK_1F_CORRIDOR_03, WALK_1F_CORRIDOR_04, WALK_1F_MAIN_ENTRANCE, WALK_1F_OFFICE, WALK_1F_SIDE_ENTRANCE — Large same-floor components are disconnected; not automatically an error.
- **SV-00200 LARGE_SAME_FLOOR_DISCONNECTION** [REVIEW] WALK_2F_BATHROOM, WALK_2F_CORRIDOR_01, WALK_2F_CORRIDOR_02, WALK_2F_CORRIDOR_03, WALK_2F_CORRIDOR_04, WALK_2F_OFFICE — Large same-floor components are disconnected; not automatically an error.
- **SV-00201 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_1F_AUDITORIUM — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00202 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_1F_MAIN_ENTRANCE — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00203 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_1F_OFFICE — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00204 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00205 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_1F_STORAGE — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00206 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_2F_BALCONY_LEFT — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00207 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_2F_BALCONY_RIGHT — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00208 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_2F_GALLERY — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00209 PORTAL_ORIENTATION_UNRESOLVED** [REVIEW] PORTAL_2F_OFFICE — No explicit world-space portal normal; geometry thin axis is not treated as authority.
- **SV-00210 UNRESOLVED_SETTING** [REVIEW] Scene — approved floor planes and geometry authority
- **SV-00211 UNRESOLVED_SETTING** [REVIEW] Scene — physical clearance and contact semantics
- **SV-00212 UNRESOLVED_SETTING** [REVIEW] Scene — camera-plane binding
- **SV-00213 UNRESOLVED_SETTING** [REVIEW] Scene — wall/obstacle movement versus occlusion ownership
- **SV-00214 UNRESOLVED_SETTING** [REVIEW] Scene — portal normal and endpoint declarations
- **SV-00215 UNRESOLVED_SETTING** [REVIEW] Scene — stair path direction, clearance and slab opening evidence
- **SV-00216 WALKABLE_NONPLANAR_EXTENT** [REVIEW] WALK_STAIRS_A_LOWERHALF — Walkable vertical extent exceeds diagnostic plane tolerance; ramps need explicit review.
- **SV-00217 WALKABLE_NONPLANAR_EXTENT** [REVIEW] WALK_STAIRS_A_UPPERHALF — Walkable vertical extent exceeds diagnostic plane tolerance; ramps need explicit review.
- **SV-00218 WALKABLE_NONPLANAR_EXTENT** [REVIEW] WALK_STAIRS_B_LOWERHALF — Walkable vertical extent exceeds diagnostic plane tolerance; ramps need explicit review.
- **SV-00219 WALKABLE_NONPLANAR_EXTENT** [REVIEW] WALK_STAIRS_B_UPPERHALF — Walkable vertical extent exceeds diagnostic plane tolerance; ramps need explicit review.

### LOW (43)

- **SV-00220 COLLECTION_POLICY_UNRESOLVED** [REVIEW] Scene — No approved expected-collection mapping; explicit incompatible ownership is checked.
- **SV-00221 MISSING_FLOOR_LABEL** [REVIEW] AREA_STAIR_A — No unambiguous explicit floor label.
- **SV-00222 MISSING_FLOOR_LABEL** [REVIEW] AREA_STAIR_B — No unambiguous explicit floor label.
- **SV-00223 MISSING_FLOOR_LABEL** [REVIEW] WALK_STAIRS_A_LOWERHALF — No unambiguous explicit floor label.
- **SV-00224 MISSING_FLOOR_LABEL** [REVIEW] WALK_STAIRS_A_UPPERHALF — No unambiguous explicit floor label.
- **SV-00225 MISSING_FLOOR_LABEL** [REVIEW] WALK_STAIRS_B_LOWERHALF — No unambiguous explicit floor label.
- **SV-00226 MISSING_FLOOR_LABEL** [REVIEW] WALK_STAIRS_B_UPPERHALF — No unambiguous explicit floor label.
- **SV-00227 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_BATHROOM — Explicit collection/property role exists without matching object prefix.
- **SV-00228 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_CORRIDOR_01 — Explicit collection/property role exists without matching object prefix.
- **SV-00229 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_CORRIDOR_02 — Explicit collection/property role exists without matching object prefix.
- **SV-00230 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_CORRIDOR_03 — Explicit collection/property role exists without matching object prefix.
- **SV-00231 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_CORRIDOR_04 — Explicit collection/property role exists without matching object prefix.
- **SV-00232 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_MAIN_ENTRANCE — Explicit collection/property role exists without matching object prefix.
- **SV-00233 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_OFFICE — Explicit collection/property role exists without matching object prefix.
- **SV-00234 NAMING_INCONSISTENCY** [REVIEW] WALK_1F_SIDE_ENTRANCE — Explicit collection/property role exists without matching object prefix.
- **SV-00235 NAMING_INCONSISTENCY** [REVIEW] WALK_2F_BATHROOM — Explicit collection/property role exists without matching object prefix.
- **SV-00236 NAMING_INCONSISTENCY** [REVIEW] WALK_2F_CORRIDOR_01 — Explicit collection/property role exists without matching object prefix.
- **SV-00237 NAMING_INCONSISTENCY** [REVIEW] WALK_2F_CORRIDOR_02 — Explicit collection/property role exists without matching object prefix.
- **SV-00238 NAMING_INCONSISTENCY** [REVIEW] WALK_2F_CORRIDOR_03 — Explicit collection/property role exists without matching object prefix.
- **SV-00239 NAMING_INCONSISTENCY** [REVIEW] WALK_2F_CORRIDOR_04 — Explicit collection/property role exists without matching object prefix.
- **SV-00240 NAMING_INCONSISTENCY** [REVIEW] WALK_2F_OFFICE — Explicit collection/property role exists without matching object prefix.
- **SV-00241 NAMING_INCONSISTENCY** [REVIEW] WALK_STAIRS_A_LOWERHALF — Explicit collection/property role exists without matching object prefix.
- **SV-00242 NAMING_INCONSISTENCY** [REVIEW] WALK_STAIRS_A_UPPERHALF — Explicit collection/property role exists without matching object prefix.
- **SV-00243 NAMING_INCONSISTENCY** [REVIEW] WALK_STAIRS_B_LOWERHALF — Explicit collection/property role exists without matching object prefix.
- **SV-00244 NAMING_INCONSISTENCY** [REVIEW] WALK_STAIRS_B_UPPERHALF — Explicit collection/property role exists without matching object prefix.
- **SV-00245 NON_MANIFOLD** [REVIEW] WALK_1F_BATHROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00246 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00247 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00248 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_03 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00249 NON_MANIFOLD** [REVIEW] WALK_1F_CORRIDOR_04 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00250 NON_MANIFOLD** [REVIEW] WALK_1F_MAIN_ENTRANCE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00251 NON_MANIFOLD** [REVIEW] WALK_1F_OFFICE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00252 NON_MANIFOLD** [REVIEW] WALK_1F_SIDE_ENTRANCE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00253 NON_MANIFOLD** [REVIEW] WALK_2F_BATHROOM — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00254 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_01 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00255 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_02 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00256 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_03 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00257 NON_MANIFOLD** [REVIEW] WALK_2F_CORRIDOR_04 — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00258 NON_MANIFOLD** [REVIEW] WALK_2F_OFFICE — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00259 NON_MANIFOLD** [REVIEW] WALK_STAIRS_A_LOWERHALF — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00260 NON_MANIFOLD** [REVIEW] WALK_STAIRS_A_UPPERHALF — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00261 NON_MANIFOLD** [REVIEW] WALK_STAIRS_B_LOWERHALF — Non-manifold edges reported; this does not invalidate a surface.
- **SV-00262 NON_MANIFOLD** [REVIEW] WALK_STAIRS_B_UPPERHALF — Non-manifold edges reported; this does not invalidate a surface.

## Limits / 診斷限制

- Diagnostic graph never creates or approves inference topology, stair edges or floor authority.
- XY mesh footprints preserve holes but cannot certify swept-body clearance or 3D collision.
- AABB-only representations are broad-phase evidence and require human review.
- All thresholds are diagnostic heuristics until adopted by explicit research review.


## school_v3 readiness assessment / 接入判斷

**NEEDS_HUMAN_FIXES**. This is an interpretation of the existing diagnostic report;
validator status and native HIGH/MEDIUM/LOW findings are unchanged. It does not define a
new engine status or approve geometry. 完成 audit 不代表可直接開始 Graph／collision／benchmark。

[Source audit / 原始盤點](school_v3_semantic_audit.json) preserves all 2,833 objects and
31 collections in `full_scene_inventory`, and the 105 explicitly labeled semantic objects,
including 76 evaluated meshes and 29 cameras, in the replay snapshot. No v2
approval/calibration was transferred.
The existing 1 Blender unit = 1 metre decision is retained; diagnostic giant thresholds
are not a reason to invent a different conversion.

### Coverage scope / 覆蓋率範圍

30 AREA: **24 MISSING / 4 PARTIAL / 2 geometric PASS**. The six nonmissing results remain
REVIEW because floor authority is unapproved. The area-weighted eligible XY coverage is
**5.6245%**, uncovered **94.3755%**, over 28 supported positive-area 1F/2F AREA footprints.
The two unassigned stair AREAs are excluded from this weighted denominator. These values
are not whole-floor coverage or approved walkability. 1F coverage: 6.1571%; 2F: 4.6985%.

### Human review focus / 人工優先事項

- **HIGH (native 49):** 24 AREA coverage gaps; 19 portals without nearby WALKABLE; two
  AREA_STAIR naming conflicts; unresolved floor authority; missing WALL/OBSTACLE/STAIR roles.
- **MEDIUM (native 170):** partial coverage/authority, seven islands/two same-floor
  disconnections, nine unresolved portal normals, endpoints, duplicate men's-room portals,
  nonplanar stair-half patches, hidden/giant geometry and unresolved policies.
- **LOW (native 43):** WALK_* names, missing floors, open-surface non-manifold warnings
  and unspecified collection policy. A one-face WALKABLE plane has open boundary edges;
  non-manifold does not by itself prove the proxy is invalid.

19 `BLOCK_*` meshes belong to collection `BLOCK`, outside the current recognized role
prefixes. They remain UNCLASSIFIED: **請人工確認 WALL／OBSTACLE／其他，以及 movement／occlusion
ownership**. This inventory observation is associated with the native missing-collider
HIGH findings; it does not add or relabel native queue entries. With no declared colliders,
wall/obstacle overlap and portal collision are **not assessed**, rather than collision-free.

All 28 portals lack explicit normals: 19 MISSING, nine REVIEW. There is no verified
one-sided/two-sided passage. `PORTAL_1F_MENSROOM` and `PORTAL_2F_MENSROOM` have identical
evaluated world geometry and need placement/floor review.

Four `WALK_STAIRS_*` halves are WALKABLE collection members with no floor assignments,
not approved STAIR entry/path/exit. Their isolation partly follows missing floor labels.
STAIR traversal/direction, clearance and slab opening remain **REVIEW / unmeasured**;
no stair or portal edges were created. Endpoint accessibility remains unresolved.

### Geometry scope / 幾何檢查範圍

Triangle/sanity validation covers 76 explicitly semantic meshes, all within the existing
256-triangle budget. The remaining 2,613 meshes are inventory-only, not certified by the
validator. Full inventory records two empty evaluated meshes (`Circle.018`, `Plane.110`)
and 115 additional vertex/edge-only meshes with no polygons. Their group/instance names
are not assigned physical roles. Non-manifold is report-only; hidden/disabled and giant
findings require context review. Floors, camera-plane bindings, contact and clearance
policy still need source-bound human approval.

### BLOCK IDs requiring ownership review / 待確認阻擋物角色

- `BLOCK_1F_BATHROOM`
- `BLOCK_1F_CORRIDOR_01_01`
- `BLOCK_1F_CORRIDOR_01_02`
- `BLOCK_1F_MAIN_ENTRANCE_01`
- `BLOCK_1F_MAIN_ENTRANCE_02`
- `BLOCK_1F_OFFICE_01`
- `BLOCK_1F_OFFICE_02`
- `BLOCK_1F_RESTAURANT_01`
- `BLOCK_1F_RESTAURANT_02`
- `BLOCK_1F_RESTAURANT_03`
- `BLOCK_1F_STORAGE01`
- `BLOCK_1F_STORAGE02`
- `BLOCK_1F_STORAGE03`
- `BLOCK_2F_BATHROOM`
- `BLOCK_2F_GALLERY_01`
- `BLOCK_2F_GALLERY_02`
- `BLOCK_2F_MEETINGROOM`
- `BLOCK_2F_OFFICE_01`
- `BLOCK_2F_OFFICE_02`

## Verification / 驗證結果

- Existing validator CLI: exit 0; native JSON/Markdown replay agrees; 262 unique review IDs.
- Full regression: `uv run pytest` — 745 passed, 0 failed, 0 skipped (55.43 s).
- `uv run ruff check .` — passed; `uv run mypy` — passed (72 source files).
- Report links and audit hash binding — passed; `git diff --check` — passed.
- Source SHA-256, 467,890,973-byte size and mtime unchanged after regression; no save/render.
- Source SHA-256: `26428df2fd395c69673b3e918fb7171b72d77a47d728e6b9cb21bb9da7b8e614`.
- Only audit/report artifacts changed; no Graph/collision/benchmark implementation started.
