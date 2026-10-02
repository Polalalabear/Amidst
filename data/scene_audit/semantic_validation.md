# Semantic completeness diagnostics / 場景語意完整度診斷

Status: **REVIEW_REQUIRED**. Authority: **HEURISTIC / REVIEW** until source-bound approval.

原始場景不修改；不建立 Graph／stair connectivity、不猜測未標記幾何。
Source is preserved; no inferred physical roles or inference topology are created.

## Floor summary / 每層摘要

| Floor | AREA | WALKABLE | WALL | OBSTACLE | STAIR | PORTAL | Components | Isolated | Uncovered | Suspicious portals | Conflicts | Geometry warnings |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1F | 16 | 0 | 0 | 0 | 0 | 16 | 0 | 0 | 16 | 16 | 0 | 65 |
| 2F | 12 | 0 | 0 | 0 | 0 | 12 | 0 | 0 | 12 | 12 | 0 | 49 |
| UNASSIGNED | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 4 |

## AREA coverage / 區域覆蓋

| AREA | Status | Geometric coverage | Overlap ratio | Uncovered | Nearest WALKABLE | Offset m |
| --- | --- | --- | ---: | ---: | --- | ---: |
| AREA_1F_AUDITORIUM | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_CLASS101 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_CLASS102 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_CLASS103 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_CLASS104 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_COURTYARD | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_ELEVATOR | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_LADYSROOM | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_MAIN_ENTRANCE | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_MEETINGROOM | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_MENSROOM | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_OFFICE | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_RESTAURANT_A | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_RESTAURANT_B | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_SIDE_ENTRANCE | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_1F_STORAGE | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_BALCONY_LEFT | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_BALCONY_RIGHT | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_CLASS201 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_CLASS202 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_CLASS203 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_CLASS204 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_ELEVATOR | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_GALLERY | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_LADYSROOM | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_MEETINGROOM | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_MENSROOM | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_2F_OFFICE | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_STAIR01 | MISSING | MISSING | 0 | 1 | N/A | N/A |
| AREA_STAIR02 | MISSING | MISSING | 0 | 1 | N/A | N/A |

## Human review queue / 人工審查佇列

### HIGH (63)

- **SV-00001 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_AUDITORIUM — Area has no sufficient same-floor walkable overlap.
- **SV-00002 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS101 — Area has no sufficient same-floor walkable overlap.
- **SV-00003 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS102 — Area has no sufficient same-floor walkable overlap.
- **SV-00004 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS103 — Area has no sufficient same-floor walkable overlap.
- **SV-00005 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_CLASS104 — Area has no sufficient same-floor walkable overlap.
- **SV-00006 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_COURTYARD — Area has no sufficient same-floor walkable overlap.
- **SV-00007 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_ELEVATOR — Area has no sufficient same-floor walkable overlap.
- **SV-00008 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_LADYSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00009 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_MAIN_ENTRANCE — Area has no sufficient same-floor walkable overlap.
- **SV-00010 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_MEETINGROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00011 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_MENSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00012 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_OFFICE — Area has no sufficient same-floor walkable overlap.
- **SV-00013 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_RESTAURANT_A — Area has no sufficient same-floor walkable overlap.
- **SV-00014 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_RESTAURANT_B — Area has no sufficient same-floor walkable overlap.
- **SV-00015 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_SIDE_ENTRANCE — Area has no sufficient same-floor walkable overlap.
- **SV-00016 AREA_MISSING_WALKABLE** [MISSING] AREA_1F_STORAGE — Area has no sufficient same-floor walkable overlap.
- **SV-00017 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_BALCONY_LEFT — Area has no sufficient same-floor walkable overlap.
- **SV-00018 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_BALCONY_RIGHT — Area has no sufficient same-floor walkable overlap.
- **SV-00019 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS201 — Area has no sufficient same-floor walkable overlap.
- **SV-00020 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS202 — Area has no sufficient same-floor walkable overlap.
- **SV-00021 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS203 — Area has no sufficient same-floor walkable overlap.
- **SV-00022 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_CLASS204 — Area has no sufficient same-floor walkable overlap.
- **SV-00023 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_ELEVATOR — Area has no sufficient same-floor walkable overlap.
- **SV-00024 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_GALLERY — Area has no sufficient same-floor walkable overlap.
- **SV-00025 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_LADYSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00026 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_MEETINGROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00027 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_MENSROOM — Area has no sufficient same-floor walkable overlap.
- **SV-00028 AREA_MISSING_WALKABLE** [MISSING] AREA_2F_OFFICE — Area has no sufficient same-floor walkable overlap.
- **SV-00029 AREA_MISSING_WALKABLE** [MISSING] AREA_STAIR01 — Area has no sufficient same-floor walkable overlap.
- **SV-00030 AREA_MISSING_WALKABLE** [MISSING] AREA_STAIR02 — Area has no sufficient same-floor walkable overlap.
- **SV-00031 FLOOR_PLANE_AUTHORITY_UNRESOLVED** [REVIEW] Scene — No source-bound approved floor-plane configuration; floor results remain HEURISTIC.
- **SV-00032 MISSING_OBSTACLE_LABELS** [MISSING] Scene — No explicit OBSTACLE_* objects or semantic collection members.
- **SV-00033 MISSING_STAIR_LABELS** [MISSING] Scene — No explicit STAIR_* objects or semantic collection members.
- **SV-00034 MISSING_WALKABLE_LABELS** [MISSING] Scene — No explicit WALKABLE_* objects or semantic collection members.
- **SV-00035 MISSING_WALL_LABELS** [MISSING] Scene — No explicit WALL_* objects or semantic collection members.
- **SV-00036 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_AUDITORIUM — No nearby same-floor walkable.
- **SV-00037 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_AUDITORIUM_OFFICE — No nearby same-floor walkable.
- **SV-00038 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS101 — No nearby same-floor walkable.
- **SV-00039 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS102 — No nearby same-floor walkable.
- **SV-00040 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS103 — No nearby same-floor walkable.
- **SV-00041 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_CLASS104 — No nearby same-floor walkable.
- **SV-00042 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_LADYSROOM — No nearby same-floor walkable.
- **SV-00043 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MAIN_ENTRANCE — No nearby same-floor walkable.
- **SV-00044 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MEETINGROOM_01 — No nearby same-floor walkable.
- **SV-00045 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MEETINGROOM_02 — No nearby same-floor walkable.
- **SV-00046 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_MENSROOM — No nearby same-floor walkable.
- **SV-00047 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_OFFICE — No nearby same-floor walkable.
- **SV-00048 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_RESTAURANT_A — No nearby same-floor walkable.
- **SV-00049 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_RESTAURANT_B — No nearby same-floor walkable.
- **SV-00050 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_SIDE_ENTRANCE — No nearby same-floor walkable.
- **SV-00051 PORTAL_DISCONNECTED** [MISSING] PORTAL_1F_STORAGE — No nearby same-floor walkable.
- **SV-00052 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_BALCONY_LEFT — No nearby same-floor walkable.
- **SV-00053 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_BALCONY_RIGHT — No nearby same-floor walkable.
- **SV-00054 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS201 — No nearby same-floor walkable.
- **SV-00055 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS202 — No nearby same-floor walkable.
- **SV-00056 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS203 — No nearby same-floor walkable.
- **SV-00057 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_CLASS204 — No nearby same-floor walkable.
- **SV-00058 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_GALLERY — No nearby same-floor walkable.
- **SV-00059 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_LADYSROOM — No nearby same-floor walkable.
- **SV-00060 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_MEETINGROOM_01 — No nearby same-floor walkable.
- **SV-00061 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_MEETINGROOM_02 — No nearby same-floor walkable.
- **SV-00062 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_MENSROOM — No nearby same-floor walkable.
- **SV-00063 PORTAL_DISCONNECTED** [MISSING] PORTAL_2F_OFFICE — No nearby same-floor walkable.

### MEDIUM (124)

- **SV-00064 DUPLICATED_GEOMETRY** [REVIEW] PORTAL_1F_MENSROOM, PORTAL_2F_MENSROOM — Identical evaluated world geometry.
- **SV-00065 ENDPOINT_ACCESSIBILITY_UNRESOLVED** [REVIEW] Scene — No explicit navigation endpoint declarations.
- **SV-00066 GIANT_GEOMETRY** [REVIEW] AREA_1F_AUDITORIUM — Object exceeds configured maximum diagnostic extent.
- **SV-00067 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS101 — Object exceeds configured maximum diagnostic extent.
- **SV-00068 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS102 — Object exceeds configured maximum diagnostic extent.
- **SV-00069 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS103 — Object exceeds configured maximum diagnostic extent.
- **SV-00070 GIANT_GEOMETRY** [REVIEW] AREA_1F_CLASS104 — Object exceeds configured maximum diagnostic extent.
- **SV-00071 GIANT_GEOMETRY** [REVIEW] AREA_1F_COURTYARD — Object exceeds configured maximum diagnostic extent.
- **SV-00072 GIANT_GEOMETRY** [REVIEW] AREA_1F_ELEVATOR — Object exceeds configured maximum diagnostic extent.
- **SV-00073 GIANT_GEOMETRY** [REVIEW] AREA_1F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00074 GIANT_GEOMETRY** [REVIEW] AREA_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00075 GIANT_GEOMETRY** [REVIEW] AREA_1F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00076 GIANT_GEOMETRY** [REVIEW] AREA_1F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00077 GIANT_GEOMETRY** [REVIEW] AREA_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00078 GIANT_GEOMETRY** [REVIEW] AREA_1F_RESTAURANT_A — Object exceeds configured maximum diagnostic extent.
- **SV-00079 GIANT_GEOMETRY** [REVIEW] AREA_1F_RESTAURANT_B — Object exceeds configured maximum diagnostic extent.
- **SV-00080 GIANT_GEOMETRY** [REVIEW] AREA_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00081 GIANT_GEOMETRY** [REVIEW] AREA_1F_STORAGE — Object exceeds configured maximum diagnostic extent.
- **SV-00082 GIANT_GEOMETRY** [REVIEW] AREA_2F_BALCONY_LEFT — Object exceeds configured maximum diagnostic extent.
- **SV-00083 GIANT_GEOMETRY** [REVIEW] AREA_2F_BALCONY_RIGHT — Object exceeds configured maximum diagnostic extent.
- **SV-00084 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS201 — Object exceeds configured maximum diagnostic extent.
- **SV-00085 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS202 — Object exceeds configured maximum diagnostic extent.
- **SV-00086 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS203 — Object exceeds configured maximum diagnostic extent.
- **SV-00087 GIANT_GEOMETRY** [REVIEW] AREA_2F_CLASS204 — Object exceeds configured maximum diagnostic extent.
- **SV-00088 GIANT_GEOMETRY** [REVIEW] AREA_2F_ELEVATOR — Object exceeds configured maximum diagnostic extent.
- **SV-00089 GIANT_GEOMETRY** [REVIEW] AREA_2F_GALLERY — Object exceeds configured maximum diagnostic extent.
- **SV-00090 GIANT_GEOMETRY** [REVIEW] AREA_2F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00091 GIANT_GEOMETRY** [REVIEW] AREA_2F_MEETINGROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00092 GIANT_GEOMETRY** [REVIEW] AREA_2F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00093 GIANT_GEOMETRY** [REVIEW] AREA_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00094 GIANT_GEOMETRY** [REVIEW] AREA_STAIR01 — Object exceeds configured maximum diagnostic extent.
- **SV-00095 GIANT_GEOMETRY** [REVIEW] AREA_STAIR02 — Object exceeds configured maximum diagnostic extent.
- **SV-00096 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_AUDITORIUM — Object exceeds configured maximum diagnostic extent.
- **SV-00097 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_AUDITORIUM_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00098 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS101 — Object exceeds configured maximum diagnostic extent.
- **SV-00099 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS102 — Object exceeds configured maximum diagnostic extent.
- **SV-00100 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS103 — Object exceeds configured maximum diagnostic extent.
- **SV-00101 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_CLASS104 — Object exceeds configured maximum diagnostic extent.
- **SV-00102 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00103 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MAIN_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00104 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MEETINGROOM_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00105 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MEETINGROOM_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00106 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00107 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00108 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_RESTAURANT_A — Object exceeds configured maximum diagnostic extent.
- **SV-00109 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_RESTAURANT_B — Object exceeds configured maximum diagnostic extent.
- **SV-00110 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — Object exceeds configured maximum diagnostic extent.
- **SV-00111 GIANT_GEOMETRY** [REVIEW] PORTAL_1F_STORAGE — Object exceeds configured maximum diagnostic extent.
- **SV-00112 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_BALCONY_LEFT — Object exceeds configured maximum diagnostic extent.
- **SV-00113 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_BALCONY_RIGHT — Object exceeds configured maximum diagnostic extent.
- **SV-00114 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS201 — Object exceeds configured maximum diagnostic extent.
- **SV-00115 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS202 — Object exceeds configured maximum diagnostic extent.
- **SV-00116 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS203 — Object exceeds configured maximum diagnostic extent.
- **SV-00117 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_CLASS204 — Object exceeds configured maximum diagnostic extent.
- **SV-00118 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_GALLERY — Object exceeds configured maximum diagnostic extent.
- **SV-00119 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_LADYSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00120 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MEETINGROOM_01 — Object exceeds configured maximum diagnostic extent.
- **SV-00121 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MEETINGROOM_02 — Object exceeds configured maximum diagnostic extent.
- **SV-00122 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_MENSROOM — Object exceeds configured maximum diagnostic extent.
- **SV-00123 GIANT_GEOMETRY** [REVIEW] PORTAL_2F_OFFICE — Object exceeds configured maximum diagnostic extent.
- **SV-00124 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_AUDITORIUM — Semantic object is hidden or disabled.
- **SV-00125 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS101 — Semantic object is hidden or disabled.
- **SV-00126 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS102 — Semantic object is hidden or disabled.
- **SV-00127 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS103 — Semantic object is hidden or disabled.
- **SV-00128 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_CLASS104 — Semantic object is hidden or disabled.
- **SV-00129 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_COURTYARD — Semantic object is hidden or disabled.
- **SV-00130 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_ELEVATOR — Semantic object is hidden or disabled.
- **SV-00131 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00132 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MAIN_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00133 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MEETINGROOM — Semantic object is hidden or disabled.
- **SV-00134 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00135 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_OFFICE — Semantic object is hidden or disabled.
- **SV-00136 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_RESTAURANT_A — Semantic object is hidden or disabled.
- **SV-00137 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_RESTAURANT_B — Semantic object is hidden or disabled.
- **SV-00138 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_SIDE_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00139 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_1F_STORAGE — Semantic object is hidden or disabled.
- **SV-00140 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_BALCONY_LEFT — Semantic object is hidden or disabled.
- **SV-00141 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_BALCONY_RIGHT — Semantic object is hidden or disabled.
- **SV-00142 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS201 — Semantic object is hidden or disabled.
- **SV-00143 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS202 — Semantic object is hidden or disabled.
- **SV-00144 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS203 — Semantic object is hidden or disabled.
- **SV-00145 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_CLASS204 — Semantic object is hidden or disabled.
- **SV-00146 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_ELEVATOR — Semantic object is hidden or disabled.
- **SV-00147 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_GALLERY — Semantic object is hidden or disabled.
- **SV-00148 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00149 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_MEETINGROOM — Semantic object is hidden or disabled.
- **SV-00150 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00151 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_2F_OFFICE — Semantic object is hidden or disabled.
- **SV-00152 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_STAIR01 — Semantic object is hidden or disabled.
- **SV-00153 HIDDEN_DISABLED_OBJECT** [REVIEW] AREA_STAIR02 — Semantic object is hidden or disabled.
- **SV-00154 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_AUDITORIUM — Semantic object is hidden or disabled.
- **SV-00155 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_AUDITORIUM_OFFICE — Semantic object is hidden or disabled.
- **SV-00156 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS101 — Semantic object is hidden or disabled.
- **SV-00157 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS102 — Semantic object is hidden or disabled.
- **SV-00158 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS103 — Semantic object is hidden or disabled.
- **SV-00159 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_CLASS104 — Semantic object is hidden or disabled.
- **SV-00160 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00161 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MAIN_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00162 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MEETINGROOM_01 — Semantic object is hidden or disabled.
- **SV-00163 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MEETINGROOM_02 — Semantic object is hidden or disabled.
- **SV-00164 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00165 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_OFFICE — Semantic object is hidden or disabled.
- **SV-00166 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_RESTAURANT_A — Semantic object is hidden or disabled.
- **SV-00167 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_RESTAURANT_B — Semantic object is hidden or disabled.
- **SV-00168 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_SIDE_ENTRANCE — Semantic object is hidden or disabled.
- **SV-00169 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_1F_STORAGE — Semantic object is hidden or disabled.
- **SV-00170 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_BALCONY_LEFT — Semantic object is hidden or disabled.
- **SV-00171 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_BALCONY_RIGHT — Semantic object is hidden or disabled.
- **SV-00172 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS201 — Semantic object is hidden or disabled.
- **SV-00173 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS202 — Semantic object is hidden or disabled.
- **SV-00174 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS203 — Semantic object is hidden or disabled.
- **SV-00175 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_CLASS204 — Semantic object is hidden or disabled.
- **SV-00176 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_GALLERY — Semantic object is hidden or disabled.
- **SV-00177 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_LADYSROOM — Semantic object is hidden or disabled.
- **SV-00178 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MEETINGROOM_01 — Semantic object is hidden or disabled.
- **SV-00179 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MEETINGROOM_02 — Semantic object is hidden or disabled.
- **SV-00180 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_MENSROOM — Semantic object is hidden or disabled.
- **SV-00181 HIDDEN_DISABLED_OBJECT** [REVIEW] PORTAL_2F_OFFICE — Semantic object is hidden or disabled.
- **SV-00182 UNRESOLVED_SETTING** [REVIEW] Scene — approved floor planes and geometry authority
- **SV-00183 UNRESOLVED_SETTING** [REVIEW] Scene — physical clearance and contact semantics
- **SV-00184 UNRESOLVED_SETTING** [REVIEW] Scene — camera-plane binding
- **SV-00185 UNRESOLVED_SETTING** [REVIEW] Scene — wall/obstacle movement versus occlusion ownership
- **SV-00186 UNRESOLVED_SETTING** [REVIEW] Scene — portal normal and endpoint declarations
- **SV-00187 UNRESOLVED_SETTING** [REVIEW] Scene — stair path direction, clearance and slab opening evidence

### LOW (3)

- **SV-00188 COLLECTION_POLICY_UNRESOLVED** [REVIEW] Scene — No approved expected-collection mapping; explicit incompatible ownership is checked.
- **SV-00189 MISSING_FLOOR_LABEL** [REVIEW] AREA_STAIR01 — No unambiguous explicit floor label.
- **SV-00190 MISSING_FLOOR_LABEL** [REVIEW] AREA_STAIR02 — No unambiguous explicit floor label.

## Limits / 診斷限制

- Diagnostic graph never creates or approves inference topology, stair edges or floor authority.
- XY mesh footprints preserve holes but cannot certify swept-body clearance or 3D collision.
- AABB-only representations are broad-phase evidence and require human review.
- All thresholds are diagnostic heuristics until adopted by explicit research review.
