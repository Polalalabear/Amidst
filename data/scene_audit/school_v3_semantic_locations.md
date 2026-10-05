# school_v3：剩餘問題的具體位置

2026-10-05，來源 SHA-256 `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`。結論：**NEEDS_HUMAN_FIXES**。

只整理保存後的幾何診斷；位置是 evaluated world centroid，門口 Z 通常是 volume 中心，
不等於 floor height。距離沿用目前配置 1 Blender unit = 1 m 與 0.05 m contact tolerance；
未改比例或研究閾值。Floor 1F=25／2F=165 尚為 PROPOSED，所有接觸仍無 physical authority。

對照 [完整原生報告](school_v3_semantic_validation.md)、[audit](school_v3_semantic_audit.json)、
[修改 recipe](school_v3_semantic_patch.json) 與 [保存／局部 component 複查](school_v3_semantic_update.json)。

## 優先人工補充

先處理下列真實邊界；不要為消除警訊而把 obstacle 內部、陽台或未知門外缺口填成 WALKABLE。

| Floor → AREA / PORTAL | 約略 XYZ | 問題 | 人工需要做什麼 |
| --- | --- | --- | --- |
| 1F / LADYSROOM / `PORTAL_1F_LADYSROOM` | (326.000, 1975.000, 85.000) | `OBSTACLE_1F_BATHROOM` 覆蓋整個 room AREA 並穿過 portal footprint；沒有可建立的 room floor | 保持 OBSTACLE/BOTH 分類，人工修正 footprint 只佔真正 blocking geometry；確認實際門洞和 corridor/bathroom lobby 連接後再補 floor/normal |
| 1F / MENSROOM / `PORTAL_1F_MENSROOM` | (396.000, 1975.000, 90.000) | `OBSTACLE_1F_BATHROOM` 覆蓋整個 room AREA 並穿過 portal footprint；沒有可建立的 room floor | 保持 OBSTACLE/BOTH 分類，人工修正 footprint 只佔真正 blocking geometry；確認實際門洞和 corridor/bathroom lobby 連接後再補 floor/normal |
| 2F / LADYSROOM / `PORTAL_2F_LADYSROOM` | (326.000, 1975.000, 230.000) | `OBSTACLE_2F_BATHROOM` 覆蓋整個 room AREA 並穿過 portal footprint；沒有可建立的 room floor | 保持 OBSTACLE/BOTH 分類，人工修正 footprint 只佔真正 blocking geometry；確認實際門洞和 corridor/bathroom lobby 連接後再補 floor/normal |
| 2F / MENSROOM / `PORTAL_2F_MENSROOM` | (396.000, 1975.000, 230.000) | `OBSTACLE_2F_BATHROOM` 覆蓋整個 room AREA 並穿過 portal footprint；沒有可建立的 room floor | 保持 OBSTACLE/BOTH 分類，人工修正 footprint 只佔真正 blocking geometry；確認實際門洞和 corridor/bathroom lobby 連接後再補 floor/normal |
| 1F / CLASS101 前 / `PORTAL_1F_CLASS101` | (501.000, 533.000, 85.000) | 房間及門檻已接；門檻到 `WALK_1F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 1F / CLASS102 前 / `PORTAL_1F_CLASS102` | (501.000, 935.000, 85.000) | 房間及門檻已接；門檻到 `WALK_1F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 1F / CLASS103 前 / `PORTAL_1F_CLASS103` | (501.000, 1340.000, 85.000) | 房間及門檻已接；門檻到 `WALK_1F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 1F / CLASS104 前 / `PORTAL_1F_CLASS104` | (501.000, 1742.000, 85.000) | 房間及門檻已接；門檻到 `WALK_1F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 2F / CLASS201 前 / `PORTAL_2F_CLASS201` | (501.000, 533.000, 230.000) | 房間及門檻已接；門檻到 `WALK_2F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 2F / CLASS202 前 / `PORTAL_2F_CLASS202` | (501.000, 935.000, 230.000) | 房間及門檻已接；門檻到 `WALK_2F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 2F / CLASS203 前 / `PORTAL_2F_CLASS203` | (501.000, 1340.000, 230.000) | 房間及門檻已接；門檻到 `WALK_2F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 2F / CLASS204 前 / `PORTAL_2F_CLASS204` | (501.000, 1742.000, 230.000) | 房間及門檻已接；門檻到 `WALK_2F_CORRIDOR_04` 尚有約 4.991 m XY gap | 對照真實門洞，確認 gap 是缺地板標記還是不可通行邊界；只在確認可走後補門外這段 WALKABLE |
| 1F / RESTAURANT_A / `PORTAL_1F_RESTAURANT_A` | (806.000, 496.000, 85.000) | 門檻到 CORRIDOR_01 約 2.968 m gap | 人工確認門外地板／牆界，再補可走 polygon；不要把跨牆線段當 connector |
| 1F / RESTAURANT_B / `PORTAL_1F_RESTAURANT_B` | (1242.000, 496.000, 85.000) | 門檻到 CORRIDOR_01 約 2.968 m gap | 人工確認門外地板／牆界，再補可走 polygon；不要把跨牆線段當 connector |
| 1F / `PORTAL_1F_AUDITORIUM_OFFICE` | (1505.000, 2025.000, 85.000) | threshold 接 OFFICE，但到 AUDITORIUM 約 5.000 m；需確認兩房間間真實門洞與地板 | 確認門洞、另一側區域、floor edge 及 blocking footprint；保留 unresolved direction，未確認前不建立 bridge |
| 1F / `PORTAL_1F_MEETINGROOM_01` | (1529.000, 825.000, 85.000) | threshold 到 CORRIDOR_02 約 2.588 m；確認門外 floor 後補 gap | 確認門洞、另一側區域、floor edge 及 blocking footprint；保留 unresolved direction，未確認前不建立 bridge |
| 1F / `PORTAL_1F_MEETINGROOM_02` | (1736.000, 880.000, 85.000) | portal 到 CORRIDOR_02 約 224.588 m，無唯一 normal／threshold；先確認此門實際另一側，不能沿最短線補 224 m floor | 確認門洞、另一側區域、floor edge 及 blocking footprint；保留 unresolved direction，未確認前不建立 bridge |
| 2F / `PORTAL_2F_MEETINGROOM_01` | (1740.000, 654.000, 230.000) | threshold 到 CORRIDOR_02 約 268.588 m（portal footprint 距離 226.588 m），並與 OBSTACLE 重疊；先確認真實出口與另一側區域 | 確認門洞、另一側區域、floor edge 及 blocking footprint；保留 unresolved direction，未確認前不建立 bridge |
| 2F / `PORTAL_2F_MEETINGROOM_02` | (1532.000, 707.000, 230.000) | threshold 到 CORRIDOR_02 約 5.588 m，並與 OBSTACLE 重疊；確認 door/obstacle 及可走地板邊界 | 確認門洞、另一側區域、floor edge 及 blocking footprint；保留 unresolved direction，未確認前不建立 bridge |
| 1F / `PORTAL_1F_SIDE_ENTRANCE` | (1636.000, 1505.000, 85.000) | portal 在房間內，距 CORRIDOR_02 約 134.588 m，無唯一 normal；SIDE_ENTRANCE 與 corridor 最近 floor edges 只有約 4.979 m，兩種距離不同；先確認門口標記應位於哪個邊界 | 確認門洞、另一側區域、floor edge 及 blocking footprint；保留 unresolved direction，未確認前不建立 bridge |
| 1F / `PORTAL_1F_MAIN_ENTRANCE` | (1070.000, 446.000, 85.000) | 局部 floor 已接 CORRIDOR_01，但兩個 MAIN_ENTRANCE obstacle 穿 portal footprint；人工核對 3D aperture/contact，不自動批准通行 | 確認門洞、另一側區域、floor edge 及 blocking footprint；保留 unresolved direction，未確認前不建立 bridge |
| 1F→2F / STAIR A lower→upper | ENTRY (1524.647, 1401.739, 22.862)；EXIT (1519.514, 1344.156, 161.000) | 原 halves 不連續；中心線 landing 端點相距約 57.584 m（不是 mesh 最短間距） | 標記真實 landing、floor 接口與連續有序 PATH；A ENTRY 及 A/B EXIT 必須確認接對樓層；人工審查 slab opening／clearance，不把 REVIEW 改 PASS |
| 1F→2F / STAIR B lower→upper | ENTRY (567.904, 1923.730, 25.126)；EXIT (625.412, 1921.099, 158.750) | 原 halves 不連續；中心線 landing 端點相距約 57.548 m（不是 mesh 最短間距） | 標記真實 landing、floor 接口與連續有序 PATH；A ENTRY 及 A/B EXIT 必須確認接對樓層；人工審查 slab opening／clearance，不把 REVIEW 改 PASS |
| 1F / STORAGE / `OBSTACLE_1F_STORAGE02` | (1689.501, 489.499, 25.842)；Z [25.655, 26.030] | 相對 proposed Z=25 超出現有 floor tolerance；已保持原幾何 | 人工確認傾斜／偏高 footprint 是否合理，不只因 proposed plane 自動平移 |
| 1F / STORAGE / `OBSTACLE_1F_STORAGE03` | (1713.746, 603.239, 24.577)；Z [24.577, 24.577] | 相對 proposed Z=25 超出現有 floor tolerance；已保持原幾何 | 人工確認傾斜／偏高 footprint 是否合理，不只因 proposed plane 自動平移 |
| 1F / ELEVATOR / `AREA_1F_ELEVATOR` | (1010.000, 800.000, 85.000) | 目前只有約 27.033% AREA 被既有 corridor 覆蓋，無法區分 lobby/cabin/shaft | 人工指明三者的實際範圍；確認 lobby 才可補 WALKABLE，shaft 不可填，暫不建立 elevator transition |
| 2F / ELEVATOR / `AREA_2F_ELEVATOR` | (1010.000, 800.000, 230.000) | 目前只有約 27.033% AREA 被既有 corridor 覆蓋，無法區分 lobby/cabin/shaft | 人工指明三者的實際範圍；確認 lobby 才可補 WALKABLE，shaft 不可填，暫不建立 elevator transition |
| 全場景 / WALL、floor/camera authority | 全場景 | WALL=0；19 個 obstacle 是無已核准高度的 footprint proxies；camera-plane binding 尚待 review | 人工標記可信牆體與 blocking/occlusion volumes，核准 source-bound floor planes、camera binding、clearance／opening policy；不推測 group_*／Cube.* |

## 已確認的局部地面接觸

以下 6 個已以不同 room/corridor surfaces 及同一 threshold component 複查；不等於合法路徑、body clearance 或 3D collision 認證。

| PORTAL | 另一側地面 | 狀態 |
| --- | --- | --- |
| `PORTAL_1F_AUDITORIUM` | `WALK_1F_CORRIDOR_02` | 局部接觸；physical approval 尚無 |
| `PORTAL_1F_MAIN_ENTRANCE` | `WALK_1F_CORRIDOR_01` | 局部接觸；仍有 collider/portal REVIEW |
| `PORTAL_1F_OFFICE` | `WALK_1F_CORRIDOR_03` | 局部接觸；physical approval 尚無 |
| `PORTAL_1F_STORAGE` | `WALK_1F_CORRIDOR_02` | 局部接觸；physical approval 尚無 |
| `PORTAL_2F_GALLERY` | `WALK_2F_CORRIDOR_01` | 局部接觸；physical approval 尚無 |
| `PORTAL_2F_OFFICE` | `WALK_2F_CORRIDOR_03` | 局部接觸；physical approval 尚無 |

其餘 20 個 portal 為 local HUMAN_REVIEW，2 個陽台 portal 是 intentional nonwalkable destination；
四個廁所 room floor 缺失也包含在 20 個 review。原生 validator 的 20 個雙側 probe
可能都位於同一 threshold，所以原生 REVIEW 24／MISSING 4／PASS 0 保留，不改為 20 connected。

Courtyard、左右陽台 coverage EXCLUDED 已生效；陽台 portal 的 HIGH warning 是不可走目的地
的門口可達性提醒，不要求把陽台補成 WALKABLE。AREA_STAIR_A/B 為 cross-floor NOT_APPLICABLE。

## 完整 HIGH / MEDIUM 定位清單

以下保留全部原生 review IDs，未抑制警訊。GIANT／HIDDEN 常見於 annotation proxies，
人工核對是否刻意即可；不是建議把已確認 obstacle 重新分類或移動所有大物件。
NON_MANIFOLD 69 個 LOW 保留在完整報告，不自動修復。

### HIGH (33)

| ID / issue | Floor → AREA / PORTAL / object | 約略 XYZ | 人工動作 |
| --- | --- | --- | --- |
| SV-00001 / AREA_MISSING_WALKABLE | 1F → `AREA_1F_LADYSROOM` | AREA_1F_LADYSROOM: (295.000, 2103.000, 85.000) | 確認 BATHROOM blocking footprint；保留 obstacle 分類，修正實際佔地後才補 room floor。 |
| SV-00002 / AREA_MISSING_WALKABLE | 1F → `AREA_1F_MENSROOM` | AREA_1F_MENSROOM: (427.000, 2103.000, 90.000) | 確認 BATHROOM blocking footprint；保留 obstacle 分類，修正實際佔地後才補 room floor。 |
| SV-00003 / AREA_MISSING_WALKABLE | 2F → `AREA_2F_LADYSROOM` | AREA_2F_LADYSROOM: (295.000, 2103.000, 230.000) | 確認 BATHROOM blocking footprint；保留 obstacle 分類，修正實際佔地後才補 room floor。 |
| SV-00004 / AREA_MISSING_WALKABLE | 2F → `AREA_2F_MENSROOM` | AREA_2F_MENSROOM: (427.000, 2103.000, 230.000) | 確認 BATHROOM blocking footprint；保留 obstacle 分類，修正實際佔地後才補 room floor。 |
| SV-00005 / COLLIDER_CROSSES_PORTAL | 1F → `OBSTACLE_1F_BATHROOM`, `PORTAL_1F_LADYSROOM` | OBSTACLE_1F_BATHROOM: (355.338, 2099.913, 25.000)；PORTAL_1F_LADYSROOM: (326.000, 1975.000, 85.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00006 / COLLIDER_CROSSES_PORTAL | 1F → `OBSTACLE_1F_BATHROOM`, `PORTAL_1F_MENSROOM` | OBSTACLE_1F_BATHROOM: (355.338, 2099.913, 25.000)；PORTAL_1F_MENSROOM: (396.000, 1975.000, 90.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00007 / COLLIDER_CROSSES_PORTAL | 1F → `OBSTACLE_1F_MAIN_ENTRANCE_01`, `PORTAL_1F_MAIN_ENTRANCE` | OBSTACLE_1F_MAIN_ENTRANCE_01: (1003.294, 439.027, 25.000)；PORTAL_1F_MAIN_ENTRANCE: (1070.000, 446.000, 85.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00008 / COLLIDER_CROSSES_PORTAL | 1F → `OBSTACLE_1F_MAIN_ENTRANCE_02`, `PORTAL_1F_MAIN_ENTRANCE` | OBSTACLE_1F_MAIN_ENTRANCE_02: (1152.243, 439.027, 25.000)；PORTAL_1F_MAIN_ENTRANCE: (1070.000, 446.000, 85.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00009 / COLLIDER_CROSSES_PORTAL | 2F → `OBSTACLE_2F_BATHROOM`, `PORTAL_2F_LADYSROOM` | OBSTACLE_2F_BATHROOM: (355.338, 2099.913, 165.000)；PORTAL_2F_LADYSROOM: (326.000, 1975.000, 230.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00010 / COLLIDER_CROSSES_PORTAL | 2F → `OBSTACLE_2F_BATHROOM`, `PORTAL_2F_MENSROOM` | OBSTACLE_2F_BATHROOM: (355.338, 2099.913, 165.000)；PORTAL_2F_MENSROOM: (396.000, 1975.000, 230.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00011 / COLLIDER_CROSSES_PORTAL | 2F → `OBSTACLE_2F_MEETINGROOM`, `PORTAL_2F_MEETINGROOM_01` | OBSTACLE_2F_MEETINGROOM: (1635.591, 681.830, 165.000)；PORTAL_2F_MEETINGROOM_01: (1740.000, 654.000, 230.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00012 / COLLIDER_CROSSES_PORTAL | 2F → `OBSTACLE_2F_MEETINGROOM`, `PORTAL_2F_MEETINGROOM_02` | OBSTACLE_2F_MEETINGROOM: (1635.591, 681.830, 165.000)；PORTAL_2F_MEETINGROOM_02: (1532.000, 707.000, 230.000) | 核對原 obstacle footprint 與實際門洞／高度；確認 3D aperture/contact，勿直接穿牆補地板。 |
| SV-00013 / FLOOR_GEOMETRY_OFFSET | 1F → `OBSTACLE_1F_STORAGE02` | OBSTACLE_1F_STORAGE02: (1689.501, 489.499, 25.842) | 核對 proposed plane 與原 Z range；不自動移動物件。 |
| SV-00014 / FLOOR_GEOMETRY_OFFSET | 1F → `OBSTACLE_1F_STORAGE03` | OBSTACLE_1F_STORAGE03: (1713.746, 603.239, 24.577) | 核對 proposed plane 與原 Z range；不自動移動物件。 |
| SV-00015 / FLOOR_GEOMETRY_OFFSET | 1F → `STAIR_A_ENTRY` | STAIR_A_ENTRY: (1524.647, 1401.739, 22.862) | 核對 proposed plane 與原 Z range；不自動移動物件。 |
| SV-00016 / FLOOR_GEOMETRY_OFFSET | 2F → `STAIR_A_EXIT` | STAIR_A_EXIT: (1519.514, 1344.156, 161.000) | 核對 proposed plane 與原 Z range；不自動移動物件。 |
| SV-00017 / FLOOR_GEOMETRY_OFFSET | 2F → `STAIR_B_EXIT` | STAIR_B_EXIT: (625.412, 1921.099, 158.750) | 核對 proposed plane 與原 Z range；不自動移動物件。 |
| SV-00018 / FLOOR_PLANE_AUTHORITY_UNRESOLVED | 全場景／跨層 → Scene | 全場景／configuration | 人工核准 source-bound 1F=25／2F=165 或明列例外；目前維持 PROPOSED。 |
| SV-00019 / ISOLATED_STAIR | 1F、2F、1F→2F → `STAIR_A_ENTRY`, `STAIR_A_EXIT`, `STAIR_A_PATH` | STAIR_A_ENTRY: (1524.647, 1401.739, 22.862)；STAIR_A_EXIT: (1519.514, 1344.156, 161.000)；STAIR_A_PATH: (1581.507, 1372.947, 91.500) | 標記真實 landing 與兩層接口，確認 endpoint 接觸；不生成不存在的 stair edge。 |
| SV-00020 / MISSING_WALL_LABELS | 全場景／跨層 → Scene | 全場景／configuration | 人工標記實際 WALL 與阻擋／遮擋 ownership；不猜 group_*／Cube.*。 |
| SV-00021 / PORTAL_DISCONNECTED | 1F → `PORTAL_1F_LADYSROOM` | PORTAL_1F_LADYSROOM: (326.000, 1975.000, 85.000) | 廁所 obstacle 目前蓋滿 room；修正 footprint 與實際門洞後再確認兩側。 |
| SV-00022 / PORTAL_DISCONNECTED | 1F → `PORTAL_1F_MENSROOM` | PORTAL_1F_MENSROOM: (396.000, 1975.000, 90.000) | 廁所 obstacle 目前蓋滿 room；修正 footprint 與實際門洞後再確認兩側。 |
| SV-00023 / PORTAL_DISCONNECTED | 2F → `PORTAL_2F_LADYSROOM` | PORTAL_2F_LADYSROOM: (326.000, 1975.000, 230.000) | 廁所 obstacle 目前蓋滿 room；修正 footprint 與實際門洞後再確認兩側。 |
| SV-00024 / PORTAL_DISCONNECTED | 2F → `PORTAL_2F_MENSROOM` | PORTAL_2F_MENSROOM: (396.000, 1975.000, 230.000) | 廁所 obstacle 目前蓋滿 room；修正 footprint 與實際門洞後再確認兩側。 |
| SV-00025 / PORTAL_IN_NONWALKABLE_REGION | 2F → `PORTAL_2F_BALCONY_LEFT` | PORTAL_2F_BALCONY_LEFT: (798.000, 767.000, 230.000) | 陽台已明確不可走；確認此門應封閉／不供 navigation，不補陽台 WALKABLE。 |
| SV-00026 / PORTAL_IN_NONWALKABLE_REGION | 2F → `PORTAL_2F_BALCONY_RIGHT` | PORTAL_2F_BALCONY_RIGHT: (1224.000, 767.000, 230.000) | 陽台已明確不可走；確認此門應封閉／不供 navigation，不補陽台 WALKABLE。 |
| SV-00027 / STAIR_ENTRY_DISCONNECTED | 1F → `STAIR_A_ENTRY` | STAIR_A_ENTRY: (1524.647, 1401.739, 22.862) | 對照 ENTRY 的實際高度與 1F floor 邊界，確認真實入口平台。 |
| SV-00028 / STAIR_EXIT_DISCONNECTED | 2F → `STAIR_A_EXIT` | STAIR_A_EXIT: (1519.514, 1344.156, 161.000) | 對照 EXIT 的實際高度與 2F floor 邊界，確認真實出口平台。 |
| SV-00029 / STAIR_EXIT_DISCONNECTED | 2F → `STAIR_B_EXIT` | STAIR_B_EXIT: (625.412, 1921.099, 158.750) | 對照 EXIT 的實際高度與 2F floor 邊界，確認真實出口平台。 |
| SV-00030 / STAIR_PATH_CONTINUITY_UNRESOLVED | 1F、2F、1F→2F → `STAIR_A_ENTRY`, `STAIR_A_EXIT`, `STAIR_A_PATH` | STAIR_A_ENTRY: (1524.647, 1401.739, 22.862)；STAIR_A_EXIT: (1519.514, 1344.156, 161.000)；STAIR_A_PATH: (1581.507, 1372.947, 91.500) | 原 halves 不連續；標記真實 landing 後才提供 ordered full path。 |
| SV-00031 / STAIR_PATH_CONTINUITY_UNRESOLVED | 1F、2F、1F→2F → `STAIR_B_ENTRY`, `STAIR_B_EXIT`, `STAIR_B_PATH` | STAIR_B_ENTRY: (567.904, 1923.730, 25.126)；STAIR_B_EXIT: (625.412, 1921.099, 158.750)；STAIR_B_PATH: (596.658, 1979.680, 91.500) | 原 halves 不連續；標記真實 landing 後才提供 ordered full path。 |
| SV-00032 / STAIR_SLAB_OPENING_REVIEW | 1F、2F、1F→2F → `STAIR_A_ENTRY`, `STAIR_A_EXIT`, `STAIR_A_PATH` | STAIR_A_ENTRY: (1524.647, 1401.739, 22.862)；STAIR_A_EXIT: (1519.514, 1344.156, 161.000)；STAIR_A_PATH: (1581.507, 1372.947, 91.500) | 人工核對樓板開口，提供 source-bound PASS/FAIL，未核准保持 REVIEW。 |
| SV-00033 / STAIR_SLAB_OPENING_REVIEW | 1F、2F、1F→2F → `STAIR_B_ENTRY`, `STAIR_B_EXIT`, `STAIR_B_PATH` | STAIR_B_ENTRY: (567.904, 1923.730, 25.126)；STAIR_B_EXIT: (625.412, 1921.099, 158.750)；STAIR_B_PATH: (596.658, 1979.680, 91.500) | 人工核對樓板開口，提供 source-bound PASS/FAIL，未核准保持 REVIEW。 |

### MEDIUM (224)

| ID / issue | Floor → AREA / PORTAL / object | 約略 XYZ | 人工動作 |
| --- | --- | --- | --- |
| SV-00034 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_AUDITORIUM` | AREA_1F_AUDITORIUM: (1775.000, 1945.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00035 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_CLASS101` | AREA_1F_CLASS101: (360.000, 430.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00036 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_CLASS102` | AREA_1F_CLASS102: (360.000, 835.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00037 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_CLASS103` | AREA_1F_CLASS103: (360.000, 1240.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00038 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_CLASS104` | AREA_1F_CLASS104: (360.000, 1640.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00039 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_MEETINGROOM` | AREA_1F_MEETINGROOM: (1630.000, 1030.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00040 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_RESTAURANT_A` | AREA_1F_RESTAURANT_A: (720.000, 402.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00041 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_RESTAURANT_B` | AREA_1F_RESTAURANT_B: (1340.000, 402.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00042 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_SIDE_ENTRANCE` | AREA_1F_SIDE_ENTRANCE: (1600.000, 1505.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00043 / AREA_COVERAGE_AUTHORITY_REVIEW | 1F → `AREA_1F_STORAGE` | AREA_1F_STORAGE: (1630.000, 545.000, 85.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00044 / AREA_COVERAGE_AUTHORITY_REVIEW | 2F → `AREA_2F_CLASS201` | AREA_2F_CLASS201: (360.000, 430.000, 230.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00045 / AREA_COVERAGE_AUTHORITY_REVIEW | 2F → `AREA_2F_CLASS202` | AREA_2F_CLASS202: (360.000, 835.000, 230.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00046 / AREA_COVERAGE_AUTHORITY_REVIEW | 2F → `AREA_2F_CLASS203` | AREA_2F_CLASS203: (360.000, 1240.000, 230.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00047 / AREA_COVERAGE_AUTHORITY_REVIEW | 2F → `AREA_2F_CLASS204` | AREA_2F_CLASS204: (360.000, 1640.000, 230.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00048 / AREA_COVERAGE_AUTHORITY_REVIEW | 2F → `AREA_2F_GALLERY` | AREA_2F_GALLERY: (1000.000, 400.000, 230.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00049 / AREA_COVERAGE_AUTHORITY_REVIEW | 2F → `AREA_2F_MEETINGROOM` | AREA_2F_MEETINGROOM: (1630.000, 500.000, 230.000) | floor 尚未核准；確認 source-bound floor／polygon evidence，幾何 PASS 不代表 physical PASS。 |
| SV-00050 / AREA_CROSS_FLOOR_REVIEW | 1F→2F → `AREA_STAIR_A` | AREA_STAIR_A: (1600.000, 1370.000, 85.000) | 依 STAIR group 審查跨層 PATH／端點；不要套單層 coverage。 |
| SV-00051 / AREA_CROSS_FLOOR_REVIEW | 1F→2F → `AREA_STAIR_B` | AREA_STAIR_B: (575.000, 2070.000, 85.000) | 依 STAIR group 審查跨層 PATH／端點；不要套單層 coverage。 |
| SV-00052 / AREA_PARTIAL_COVERAGE | 1F → `AREA_1F_ELEVATOR` | AREA_1F_ELEVATOR: (1010.000, 800.000, 85.000) | 依具體位置核對：OFFICE 缺口多為 blocker 佔地；ELEVATOR 角色待定；MAIN_ENTRANCE 已扣 blocker。不要為 ratio 填 obstacle。 |
| SV-00053 / AREA_PARTIAL_COVERAGE | 1F → `AREA_1F_MAIN_ENTRANCE` | AREA_1F_MAIN_ENTRANCE: (1060.000, 400.000, 85.000) | 依具體位置核對：OFFICE 缺口多為 blocker 佔地；ELEVATOR 角色待定；MAIN_ENTRANCE 已扣 blocker。不要為 ratio 填 obstacle。 |
| SV-00054 / AREA_PARTIAL_COVERAGE | 1F → `AREA_1F_OFFICE` | AREA_1F_OFFICE: (1320.000, 2010.000, 85.000) | 依具體位置核對：OFFICE 缺口多為 blocker 佔地；ELEVATOR 角色待定；MAIN_ENTRANCE 已扣 blocker。不要為 ratio 填 obstacle。 |
| SV-00055 / AREA_PARTIAL_COVERAGE | 2F → `AREA_2F_ELEVATOR` | AREA_2F_ELEVATOR: (1010.000, 800.000, 230.000) | 依具體位置核對：OFFICE 缺口多為 blocker 佔地；ELEVATOR 角色待定；MAIN_ENTRANCE 已扣 blocker。不要為 ratio 填 obstacle。 |
| SV-00056 / AREA_PARTIAL_COVERAGE | 2F → `AREA_2F_OFFICE` | AREA_2F_OFFICE: (1320.000, 2010.000, 230.000) | 依具體位置核對：OFFICE 缺口多為 blocker 佔地；ELEVATOR 角色待定；MAIN_ENTRANCE 已扣 blocker。不要為 ratio 填 obstacle。 |
| SV-00057 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_AUDITORIUM_FRONT` | CAM_1F_AUDITORIUM_FRONT: (2025.243, 2314.508, 153.214) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00058 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_AUDITORIUM_REAR` | CAM_1F_AUDITORIUM_REAR: (2024.805, 1580.674, 153.232) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00059 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_BATHROOM` | CAM_1F_BATHROOM: (645.225, 1875.940, 152.487) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00060 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CLASS101` | CAM_1F_CLASS101: (237.559, 235.540, 152.308) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00061 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CLASS102` | CAM_1F_CLASS102: (242.302, 639.085, 143.453) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00062 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CLASS103` | CAM_1F_CLASS103: (236.646, 1042.642, 152.538) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00063 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CLASS104` | CAM_1F_CLASS104: (237.308, 1446.188, 151.307) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00064 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CORRIDOR_01` | CAM_1F_CORRIDOR_01: (1470.292, 508.209, 143.863) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00065 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CORRIDOR_02` | CAM_1F_CORRIDOR_02: (526.378, 562.959, 153.399) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00066 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CORRIDOR_03` | CAM_1F_CORRIDOR_03: (1483.136, 504.439, 153.001) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00067 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_CORRIDOR_04` | CAM_1F_CORRIDOR_04: (1495.627, 1687.900, 153.700) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00068 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_MAIN_ENTRANCE` | CAM_1F_MAIN_ENTRANCE: (1152.242, 382.189, 132.064) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00069 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_MEETINGROOM` | CAM_1F_MEETINGROOM: (1747.301, 1296.639, 151.791) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00070 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_RESTAURANT_01` | CAM_1F_RESTAURANT_01: (930.664, 316.620, 151.871) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00071 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_RESTAURANT_02` | CAM_1F_RESTAURANT_02: (1186.764, 319.533, 151.621) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00072 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_SIDE_ENTRANCE` | CAM_1F_SIDE_ENTRANCE: (1778.826, 1561.729, 141.486) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00073 / CAMERA_PLANE_BINDING_REVIEW | 1F → `CAM_1F_STORAGE` | CAM_1F_STORAGE: (1522.403, 647.171, 148.503) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00074 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_BATHROOM` | CAM_2F_BATHROOM: (645.224, 1839.434, 291.770) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00075 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CLASS201` | CAM_2F_CLASS201: (242.731, 235.545, 294.411) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00076 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CLASS202` | CAM_2F_CLASS202: (242.995, 639.091, 294.264) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00077 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CLASS203` | CAM_2F_CLASS203: (243.846, 1042.633, 294.089) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00078 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CLASS204` | CAM_2F_CLASS204: (253.603, 1446.172, 292.301) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00079 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CORRIDOR_01` | CAM_2F_CORRIDOR_01: (1479.522, 504.439, 295.106) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00080 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CORRIDOR_02` | CAM_2F_CORRIDOR_02: (1495.627, 1681.646, 294.774) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00081 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CORRIDOR_03` | CAM_2F_CORRIDOR_03: (524.297, 1704.783, 295.362) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00082 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_CORRIDOR_04` | CAM_2F_CORRIDOR_04: (526.384, 512.932, 293.209) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00083 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_GALLERY_01` | CAM_2F_GALLERY_01: (1491.695, 480.173, 288.733) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00084 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_GALLERY_02` | CAM_2F_GALLERY_02: (502.768, 479.886, 294.178) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00085 / CAMERA_PLANE_BINDING_REVIEW | 2F → `CAM_2F_MEETINGROOM` | CAM_2F_MEETINGROOM: (1743.375, 235.544, 292.163) | 確認此 camera 的 source-bound floor／plane mapping；pose 存在不等於 projection authority。 |
| SV-00086 / ENDPOINT_ACCESSIBILITY_UNRESOLVED | 全場景／跨層 → Scene | 全場景／configuration | 選定實際 observation/navigation endpoints 後核准 accessibility；本輪未建立 Graph endpoints。 |
| SV-00087 / GIANT_GEOMETRY | 1F → `AREA_1F_AUDITORIUM` | AREA_1F_AUDITORIUM: (1775.000, 1945.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00088 / GIANT_GEOMETRY | 1F → `AREA_1F_CLASS101` | AREA_1F_CLASS101: (360.000, 430.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00089 / GIANT_GEOMETRY | 1F → `AREA_1F_CLASS102` | AREA_1F_CLASS102: (360.000, 835.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00090 / GIANT_GEOMETRY | 1F → `AREA_1F_CLASS103` | AREA_1F_CLASS103: (360.000, 1240.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00091 / GIANT_GEOMETRY | 1F → `AREA_1F_CLASS104` | AREA_1F_CLASS104: (360.000, 1640.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00092 / GIANT_GEOMETRY | 1F → `AREA_1F_COURTYARD` | AREA_1F_COURTYARD: (1010.000, 1250.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00093 / GIANT_GEOMETRY | 1F → `AREA_1F_ELEVATOR` | AREA_1F_ELEVATOR: (1010.000, 800.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00094 / GIANT_GEOMETRY | 1F → `AREA_1F_LADYSROOM` | AREA_1F_LADYSROOM: (295.000, 2103.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00095 / GIANT_GEOMETRY | 1F → `AREA_1F_MAIN_ENTRANCE` | AREA_1F_MAIN_ENTRANCE: (1060.000, 400.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00096 / GIANT_GEOMETRY | 1F → `AREA_1F_MEETINGROOM` | AREA_1F_MEETINGROOM: (1630.000, 1030.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00097 / GIANT_GEOMETRY | 1F → `AREA_1F_MENSROOM` | AREA_1F_MENSROOM: (427.000, 2103.000, 90.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00098 / GIANT_GEOMETRY | 1F → `AREA_1F_OFFICE` | AREA_1F_OFFICE: (1320.000, 2010.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00099 / GIANT_GEOMETRY | 1F → `AREA_1F_RESTAURANT_A` | AREA_1F_RESTAURANT_A: (720.000, 402.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00100 / GIANT_GEOMETRY | 1F → `AREA_1F_RESTAURANT_B` | AREA_1F_RESTAURANT_B: (1340.000, 402.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00101 / GIANT_GEOMETRY | 1F → `AREA_1F_SIDE_ENTRANCE` | AREA_1F_SIDE_ENTRANCE: (1600.000, 1505.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00102 / GIANT_GEOMETRY | 1F → `AREA_1F_STORAGE` | AREA_1F_STORAGE: (1630.000, 545.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00103 / GIANT_GEOMETRY | 2F → `AREA_2F_BALCONY_LEFT` | AREA_2F_BALCONY_LEFT: (800.000, 840.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00104 / GIANT_GEOMETRY | 2F → `AREA_2F_BALCONY_RIGHT` | AREA_2F_BALCONY_RIGHT: (1230.000, 840.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00105 / GIANT_GEOMETRY | 2F → `AREA_2F_CLASS201` | AREA_2F_CLASS201: (360.000, 430.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00106 / GIANT_GEOMETRY | 2F → `AREA_2F_CLASS202` | AREA_2F_CLASS202: (360.000, 835.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00107 / GIANT_GEOMETRY | 2F → `AREA_2F_CLASS203` | AREA_2F_CLASS203: (360.000, 1240.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00108 / GIANT_GEOMETRY | 2F → `AREA_2F_CLASS204` | AREA_2F_CLASS204: (360.000, 1640.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00109 / GIANT_GEOMETRY | 2F → `AREA_2F_ELEVATOR` | AREA_2F_ELEVATOR: (1010.000, 800.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00110 / GIANT_GEOMETRY | 2F → `AREA_2F_GALLERY` | AREA_2F_GALLERY: (1000.000, 400.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00111 / GIANT_GEOMETRY | 2F → `AREA_2F_LADYSROOM` | AREA_2F_LADYSROOM: (295.000, 2103.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00112 / GIANT_GEOMETRY | 2F → `AREA_2F_MEETINGROOM` | AREA_2F_MEETINGROOM: (1630.000, 500.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00113 / GIANT_GEOMETRY | 2F → `AREA_2F_MENSROOM` | AREA_2F_MENSROOM: (427.000, 2103.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00114 / GIANT_GEOMETRY | 2F → `AREA_2F_OFFICE` | AREA_2F_OFFICE: (1320.000, 2010.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00115 / GIANT_GEOMETRY | 1F→2F → `AREA_STAIR_A` | AREA_STAIR_A: (1600.000, 1370.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00116 / GIANT_GEOMETRY | 1F→2F → `AREA_STAIR_B` | AREA_STAIR_B: (575.000, 2070.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00117 / GIANT_GEOMETRY | 1F → `OBSTACLE_1F_BATHROOM` | OBSTACLE_1F_BATHROOM: (355.338, 2099.913, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00118 / GIANT_GEOMETRY | 1F → `OBSTACLE_1F_MAIN_ENTRANCE_01` | OBSTACLE_1F_MAIN_ENTRANCE_01: (1003.294, 439.027, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00119 / GIANT_GEOMETRY | 1F → `OBSTACLE_1F_OFFICE_01` | OBSTACLE_1F_OFFICE_01: (1328.730, 2217.148, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00120 / GIANT_GEOMETRY | 1F → `OBSTACLE_1F_OFFICE_02` | OBSTACLE_1F_OFFICE_02: (1272.193, 1920.837, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00121 / GIANT_GEOMETRY | 1F → `OBSTACLE_1F_RESTAURANT_03` | OBSTACLE_1F_RESTAURANT_03: (655.600, 366.355, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00122 / GIANT_GEOMETRY | 2F → `OBSTACLE_2F_BATHROOM` | OBSTACLE_2F_BATHROOM: (355.338, 2099.913, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00123 / GIANT_GEOMETRY | 2F → `OBSTACLE_2F_GALLERY_02` | OBSTACLE_2F_GALLERY_02: (1057.188, 352.047, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00124 / GIANT_GEOMETRY | 2F → `OBSTACLE_2F_MEETINGROOM` | OBSTACLE_2F_MEETINGROOM: (1635.591, 681.830, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00125 / GIANT_GEOMETRY | 2F → `OBSTACLE_2F_OFFICE_01` | OBSTACLE_2F_OFFICE_01: (1328.730, 2217.148, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00126 / GIANT_GEOMETRY | 2F → `OBSTACLE_2F_OFFICE_02` | OBSTACLE_2F_OFFICE_02: (1272.193, 1920.837, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00127 / GIANT_GEOMETRY | 1F → `PORTAL_1F_AUDITORIUM` | PORTAL_1F_AUDITORIUM: (1506.000, 1648.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00128 / GIANT_GEOMETRY | 1F → `PORTAL_1F_AUDITORIUM_OFFICE` | PORTAL_1F_AUDITORIUM_OFFICE: (1505.000, 2025.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00129 / GIANT_GEOMETRY | 1F → `PORTAL_1F_CLASS101` | PORTAL_1F_CLASS101: (501.000, 533.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00130 / GIANT_GEOMETRY | 1F → `PORTAL_1F_CLASS102` | PORTAL_1F_CLASS102: (501.000, 935.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00131 / GIANT_GEOMETRY | 1F → `PORTAL_1F_CLASS103` | PORTAL_1F_CLASS103: (501.000, 1340.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00132 / GIANT_GEOMETRY | 1F → `PORTAL_1F_CLASS104` | PORTAL_1F_CLASS104: (501.000, 1742.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00133 / GIANT_GEOMETRY | 1F → `PORTAL_1F_LADYSROOM` | PORTAL_1F_LADYSROOM: (326.000, 1975.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00134 / GIANT_GEOMETRY | 1F → `PORTAL_1F_MAIN_ENTRANCE` | PORTAL_1F_MAIN_ENTRANCE: (1070.000, 446.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00135 / GIANT_GEOMETRY | 1F → `PORTAL_1F_MEETINGROOM_01` | PORTAL_1F_MEETINGROOM_01: (1529.000, 825.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00136 / GIANT_GEOMETRY | 1F → `PORTAL_1F_MEETINGROOM_02` | PORTAL_1F_MEETINGROOM_02: (1736.000, 880.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00137 / GIANT_GEOMETRY | 1F → `PORTAL_1F_MENSROOM` | PORTAL_1F_MENSROOM: (396.000, 1975.000, 90.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00138 / GIANT_GEOMETRY | 1F → `PORTAL_1F_OFFICE` | PORTAL_1F_OFFICE: (1432.000, 1708.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00139 / GIANT_GEOMETRY | 1F → `PORTAL_1F_RESTAURANT_A` | PORTAL_1F_RESTAURANT_A: (806.000, 496.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00140 / GIANT_GEOMETRY | 1F → `PORTAL_1F_RESTAURANT_B` | PORTAL_1F_RESTAURANT_B: (1242.000, 496.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00141 / GIANT_GEOMETRY | 1F → `PORTAL_1F_SIDE_ENTRANCE` | PORTAL_1F_SIDE_ENTRANCE: (1636.000, 1505.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00142 / GIANT_GEOMETRY | 1F → `PORTAL_1F_STORAGE` | PORTAL_1F_STORAGE: (1498.000, 574.000, 85.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00143 / GIANT_GEOMETRY | 2F → `PORTAL_2F_BALCONY_LEFT` | PORTAL_2F_BALCONY_LEFT: (798.000, 767.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00144 / GIANT_GEOMETRY | 2F → `PORTAL_2F_BALCONY_RIGHT` | PORTAL_2F_BALCONY_RIGHT: (1224.000, 767.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00145 / GIANT_GEOMETRY | 2F → `PORTAL_2F_CLASS201` | PORTAL_2F_CLASS201: (501.000, 533.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00146 / GIANT_GEOMETRY | 2F → `PORTAL_2F_CLASS202` | PORTAL_2F_CLASS202: (501.000, 935.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00147 / GIANT_GEOMETRY | 2F → `PORTAL_2F_CLASS203` | PORTAL_2F_CLASS203: (501.000, 1340.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00148 / GIANT_GEOMETRY | 2F → `PORTAL_2F_CLASS204` | PORTAL_2F_CLASS204: (501.000, 1742.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00149 / GIANT_GEOMETRY | 2F → `PORTAL_2F_GALLERY` | PORTAL_2F_GALLERY: (1090.000, 490.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00150 / GIANT_GEOMETRY | 2F → `PORTAL_2F_LADYSROOM` | PORTAL_2F_LADYSROOM: (326.000, 1975.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00151 / GIANT_GEOMETRY | 2F → `PORTAL_2F_MEETINGROOM_01` | PORTAL_2F_MEETINGROOM_01: (1740.000, 654.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00152 / GIANT_GEOMETRY | 2F → `PORTAL_2F_MEETINGROOM_02` | PORTAL_2F_MEETINGROOM_02: (1532.000, 707.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00153 / GIANT_GEOMETRY | 2F → `PORTAL_2F_MENSROOM` | PORTAL_2F_MENSROOM: (396.000, 1975.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00154 / GIANT_GEOMETRY | 2F → `PORTAL_2F_OFFICE` | PORTAL_2F_OFFICE: (1432.000, 1708.000, 230.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00155 / GIANT_GEOMETRY | 1F→2F → `STAIR_A_PATH` | STAIR_A_PATH: (1581.507, 1372.947, 91.500) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00156 / GIANT_GEOMETRY | 1F→2F → `STAIR_B_PATH` | STAIR_B_PATH: (596.658, 1979.680, 91.500) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00157 / GIANT_GEOMETRY | 1F → `WALK_1F_AUDITORIUM` | WALK_1F_AUDITORIUM: (1775.000, 1945.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00158 / GIANT_GEOMETRY | 1F → `WALK_1F_BATHROOM` | WALK_1F_BATHROOM: (460.391, 1936.349, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00159 / GIANT_GEOMETRY | 1F → `WALK_1F_CLASS101` | WALK_1F_CLASS101: (360.000, 430.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00160 / GIANT_GEOMETRY | 1F → `WALK_1F_CLASS102` | WALK_1F_CLASS102: (360.000, 835.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00161 / GIANT_GEOMETRY | 1F → `WALK_1F_CLASS103` | WALK_1F_CLASS103: (360.000, 1240.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00162 / GIANT_GEOMETRY | 1F → `WALK_1F_CLASS104` | WALK_1F_CLASS104: (360.000, 1640.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00163 / GIANT_GEOMETRY | 1F → `WALK_1F_CORRIDOR_01` | WALK_1F_CORRIDOR_01: (838.920, 653.804, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00164 / GIANT_GEOMETRY | 1F → `WALK_1F_CORRIDOR_02` | WALK_1F_CORRIDOR_02: (1435.643, 1104.254, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00165 / GIANT_GEOMETRY | 1F → `WALK_1F_CORRIDOR_03` | WALK_1F_CORRIDOR_03: (1011.577, 1641.058, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00166 / GIANT_GEOMETRY | 1F → `WALK_1F_CORRIDOR_04` | WALK_1F_CORRIDOR_04: (586.760, 1251.751, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00167 / GIANT_GEOMETRY | 1F → `WALK_1F_MAIN_ENTRANCE` | WALK_1F_MAIN_ENTRANCE: (1066.507, 455.758, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00168 / GIANT_GEOMETRY | 1F → `WALK_1F_MEETINGROOM` | WALK_1F_MEETINGROOM: (1630.000, 1030.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00169 / GIANT_GEOMETRY | 1F → `WALK_1F_MEETINGROOM_01_THRESHOLD` | WALK_1F_MEETINGROOM_01_THRESHOLD: (1497.000, 825.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00170 / GIANT_GEOMETRY | 1F → `WALK_1F_OFFICE` | WALK_1F_OFFICE: (1285.909, 2018.516, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00171 / GIANT_GEOMETRY | 1F → `WALK_1F_RESTAURANT_A` | WALK_1F_RESTAURANT_A: (687.194, 405.312, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00172 / GIANT_GEOMETRY | 1F → `WALK_1F_RESTAURANT_B` | WALK_1F_RESTAURANT_B: (1340.000, 402.000, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00173 / GIANT_GEOMETRY | 1F → `WALK_1F_SIDE_ENTRANCE` | WALK_1F_SIDE_ENTRANCE: (1607.482, 1504.217, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00174 / GIANT_GEOMETRY | 1F → `WALK_1F_STORAGE` | WALK_1F_STORAGE: (1661.345, 550.919, 25.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00175 / GIANT_GEOMETRY | 2F → `WALK_2F_BATHROOM` | WALK_2F_BATHROOM: (460.391, 1936.349, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00176 / GIANT_GEOMETRY | 2F → `WALK_2F_CLASS201` | WALK_2F_CLASS201: (360.000, 430.000, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00177 / GIANT_GEOMETRY | 2F → `WALK_2F_CLASS202` | WALK_2F_CLASS202: (360.000, 835.000, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00178 / GIANT_GEOMETRY | 2F → `WALK_2F_CLASS203` | WALK_2F_CLASS203: (360.000, 1240.000, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00179 / GIANT_GEOMETRY | 2F → `WALK_2F_CLASS204` | WALK_2F_CLASS204: (360.000, 1640.000, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00180 / GIANT_GEOMETRY | 2F → `WALK_2F_CORRIDOR_01` | WALK_2F_CORRIDOR_01: (1011.577, 631.517, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00181 / GIANT_GEOMETRY | 2F → `WALK_2F_CORRIDOR_02` | WALK_2F_CORRIDOR_02: (1435.643, 1104.254, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00182 / GIANT_GEOMETRY | 2F → `WALK_2F_CORRIDOR_03` | WALK_2F_CORRIDOR_03: (1011.577, 1641.058, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00183 / GIANT_GEOMETRY | 2F → `WALK_2F_CORRIDOR_04` | WALK_2F_CORRIDOR_04: (586.760, 1251.751, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00184 / GIANT_GEOMETRY | 2F → `WALK_2F_GALLERY` | WALK_2F_GALLERY: (1020.265, 416.404, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00185 / GIANT_GEOMETRY | 2F → `WALK_2F_MEETINGROOM` | WALK_2F_MEETINGROOM: (1626.378, 641.004, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00186 / GIANT_GEOMETRY | 2F → `WALK_2F_OFFICE` | WALK_2F_OFFICE: (1285.909, 2018.516, 165.000) | 核對尺度、annotation footprint／volume 是否刻意；保留現有 unit 配置，不自動 rescale。 |
| SV-00187 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_AUDITORIUM` | AREA_1F_AUDITORIUM: (1775.000, 1945.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00188 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_CLASS101` | AREA_1F_CLASS101: (360.000, 430.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00189 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_CLASS102` | AREA_1F_CLASS102: (360.000, 835.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00190 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_CLASS103` | AREA_1F_CLASS103: (360.000, 1240.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00191 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_CLASS104` | AREA_1F_CLASS104: (360.000, 1640.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00192 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_COURTYARD` | AREA_1F_COURTYARD: (1010.000, 1250.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00193 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_ELEVATOR` | AREA_1F_ELEVATOR: (1010.000, 800.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00194 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_LADYSROOM` | AREA_1F_LADYSROOM: (295.000, 2103.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00195 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_MAIN_ENTRANCE` | AREA_1F_MAIN_ENTRANCE: (1060.000, 400.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00196 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_MEETINGROOM` | AREA_1F_MEETINGROOM: (1630.000, 1030.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00197 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_MENSROOM` | AREA_1F_MENSROOM: (427.000, 2103.000, 90.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00198 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_OFFICE` | AREA_1F_OFFICE: (1320.000, 2010.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00199 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_RESTAURANT_A` | AREA_1F_RESTAURANT_A: (720.000, 402.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00200 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_RESTAURANT_B` | AREA_1F_RESTAURANT_B: (1340.000, 402.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00201 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_SIDE_ENTRANCE` | AREA_1F_SIDE_ENTRANCE: (1600.000, 1505.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00202 / HIDDEN_DISABLED_OBJECT | 1F → `AREA_1F_STORAGE` | AREA_1F_STORAGE: (1630.000, 545.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00203 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_BALCONY_LEFT` | AREA_2F_BALCONY_LEFT: (800.000, 840.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00204 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_BALCONY_RIGHT` | AREA_2F_BALCONY_RIGHT: (1230.000, 840.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00205 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_CLASS201` | AREA_2F_CLASS201: (360.000, 430.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00206 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_CLASS202` | AREA_2F_CLASS202: (360.000, 835.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00207 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_CLASS203` | AREA_2F_CLASS203: (360.000, 1240.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00208 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_CLASS204` | AREA_2F_CLASS204: (360.000, 1640.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00209 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_ELEVATOR` | AREA_2F_ELEVATOR: (1010.000, 800.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00210 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_GALLERY` | AREA_2F_GALLERY: (1000.000, 400.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00211 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_LADYSROOM` | AREA_2F_LADYSROOM: (295.000, 2103.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00212 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_MEETINGROOM` | AREA_2F_MEETINGROOM: (1630.000, 500.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00213 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_MENSROOM` | AREA_2F_MENSROOM: (427.000, 2103.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00214 / HIDDEN_DISABLED_OBJECT | 2F → `AREA_2F_OFFICE` | AREA_2F_OFFICE: (1320.000, 2010.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00215 / HIDDEN_DISABLED_OBJECT | 1F→2F → `AREA_STAIR_A` | AREA_STAIR_A: (1600.000, 1370.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00216 / HIDDEN_DISABLED_OBJECT | 1F→2F → `AREA_STAIR_B` | AREA_STAIR_B: (575.000, 2070.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00217 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_AUDITORIUM` | PORTAL_1F_AUDITORIUM: (1506.000, 1648.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00218 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_AUDITORIUM_OFFICE` | PORTAL_1F_AUDITORIUM_OFFICE: (1505.000, 2025.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00219 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_CLASS101` | PORTAL_1F_CLASS101: (501.000, 533.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00220 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_CLASS102` | PORTAL_1F_CLASS102: (501.000, 935.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00221 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_CLASS103` | PORTAL_1F_CLASS103: (501.000, 1340.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00222 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_CLASS104` | PORTAL_1F_CLASS104: (501.000, 1742.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00223 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_LADYSROOM` | PORTAL_1F_LADYSROOM: (326.000, 1975.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00224 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_MAIN_ENTRANCE` | PORTAL_1F_MAIN_ENTRANCE: (1070.000, 446.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00225 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_MEETINGROOM_01` | PORTAL_1F_MEETINGROOM_01: (1529.000, 825.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00226 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_MEETINGROOM_02` | PORTAL_1F_MEETINGROOM_02: (1736.000, 880.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00227 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_MENSROOM` | PORTAL_1F_MENSROOM: (396.000, 1975.000, 90.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00228 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_OFFICE` | PORTAL_1F_OFFICE: (1432.000, 1708.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00229 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_RESTAURANT_A` | PORTAL_1F_RESTAURANT_A: (806.000, 496.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00230 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_RESTAURANT_B` | PORTAL_1F_RESTAURANT_B: (1242.000, 496.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00231 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_SIDE_ENTRANCE` | PORTAL_1F_SIDE_ENTRANCE: (1636.000, 1505.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00232 / HIDDEN_DISABLED_OBJECT | 1F → `PORTAL_1F_STORAGE` | PORTAL_1F_STORAGE: (1498.000, 574.000, 85.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00233 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_BALCONY_LEFT` | PORTAL_2F_BALCONY_LEFT: (798.000, 767.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00234 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_BALCONY_RIGHT` | PORTAL_2F_BALCONY_RIGHT: (1224.000, 767.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00235 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_CLASS201` | PORTAL_2F_CLASS201: (501.000, 533.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00236 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_CLASS202` | PORTAL_2F_CLASS202: (501.000, 935.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00237 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_CLASS203` | PORTAL_2F_CLASS203: (501.000, 1340.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00238 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_CLASS204` | PORTAL_2F_CLASS204: (501.000, 1742.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00239 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_GALLERY` | PORTAL_2F_GALLERY: (1090.000, 490.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00240 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_LADYSROOM` | PORTAL_2F_LADYSROOM: (326.000, 1975.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00241 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_MEETINGROOM_01` | PORTAL_2F_MEETINGROOM_01: (1740.000, 654.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00242 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_MEETINGROOM_02` | PORTAL_2F_MEETINGROOM_02: (1532.000, 707.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00243 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_MENSROOM` | PORTAL_2F_MENSROOM: (396.000, 1975.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00244 / HIDDEN_DISABLED_OBJECT | 2F → `PORTAL_2F_OFFICE` | PORTAL_2F_OFFICE: (1432.000, 1708.000, 230.000) | 確認 hidden/disabled 是 annotation 顯示安排或實際禁用；不自動開啟所有物件。 |
| SV-00245 / ISOLATED_WALKABLE | 1F → `WALK_1F_SIDE_ENTRANCE` | WALK_1F_SIDE_ENTRANCE: (1607.482, 1504.217, 25.000) | SIDE_ENTRANCE 尚未接 corridor；人工確認 PORTAL 位置及實際 floor gap。 |
| SV-00246 / LARGE_SAME_FLOOR_DISCONNECTION | 1F → `WALK_1F_AUDITORIUM`, `WALK_1F_AUDITORIUM_OFFICE_THRESHOLD`, `WALK_1F_AUDITORIUM_THRESHOLD`, `WALK_1F_BATHROOM`, `WALK_1F_CORRIDOR_01`, `WALK_1F_CORRIDOR_02`, `WALK_1F_CORRIDOR_03`, `WALK_1F_CORRIDOR_04`, `WALK_1F_MAIN_ENTRANCE`, `WALK_1F_OFFICE`, `WALK_1F_OFFICE_THRESHOLD`, `WALK_1F_STORAGE`, `WALK_1F_STORAGE_THRESHOLD`, `WALK_1F_CLASS101`, `WALK_1F_CLASS101_THRESHOLD`, `WALK_1F_CLASS102`, `WALK_1F_CLASS102_THRESHOLD`, `WALK_1F_CLASS103`, `WALK_1F_CLASS103_THRESHOLD`, `WALK_1F_CLASS104`, `WALK_1F_CLASS104_THRESHOLD`, `WALK_1F_MEETINGROOM`, `WALK_1F_MEETINGROOM_01_THRESHOLD`, `WALK_1F_RESTAURANT_A`, `WALK_1F_RESTAURANT_A_THRESHOLD`, `WALK_1F_RESTAURANT_B`, `WALK_1F_RESTAURANT_B_THRESHOLD`, `WALK_1F_SIDE_ENTRANCE` | WALK_1F_AUDITORIUM: (1775.000, 1945.000, 25.000)；WALK_1F_AUDITORIUM_OFFICE_THRESHOLD: (1505.000, 2025.000, 25.000)；WALK_1F_AUDITORIUM_THRESHOLD: (1505.706, 1648.000, 25.000)；WALK_1F_BATHROOM: (460.391, 1936.349, 25.000)；WALK_1F_CORRIDOR_01: (838.920, 653.804, 25.000)；WALK_1F_CORRIDOR_02: (1435.643, 1104.254, 25.000)；WALK_1F_CORRIDOR_03: (1011.577, 1641.058, 25.000)；WALK_1F_CORRIDOR_04: (586.760, 1251.751, 25.000)；WALK_1F_MAIN_ENTRANCE: (1066.507, 455.758, 25.000)；WALK_1F_OFFICE: (1285.909, 2018.516, 25.000)；WALK_1F_OFFICE_THRESHOLD: (1432.000, 1704.811, 25.000)；WALK_1F_STORAGE: (1661.345, 550.919, 25.000)；WALK_1F_STORAGE_THRESHOLD: (1495.706, 584.462, 25.000)；WALK_1F_CLASS101: (360.000, 430.000, 25.000)；WALK_1F_CLASS101_THRESHOLD: (507.000, 533.000, 25.000)；WALK_1F_CLASS102: (360.000, 835.000, 25.000)；WALK_1F_CLASS102_THRESHOLD: (507.000, 935.000, 25.000)；WALK_1F_CLASS103: (360.000, 1240.000, 25.000)；WALK_1F_CLASS103_THRESHOLD: (507.000, 1340.000, 25.000)；WALK_1F_CLASS104: (360.000, 1640.000, 25.000)；WALK_1F_CLASS104_THRESHOLD: (507.000, 1742.000, 25.000)；WALK_1F_MEETINGROOM: (1630.000, 1030.000, 25.000)；WALK_1F_MEETINGROOM_01_THRESHOLD: (1497.000, 825.000, 25.000)；WALK_1F_RESTAURANT_A: (687.194, 405.312, 25.000)；WALK_1F_RESTAURANT_A_THRESHOLD: (806.000, 499.000, 25.000)；WALK_1F_RESTAURANT_B: (1340.000, 402.000, 25.000)；WALK_1F_RESTAURANT_B_THRESHOLD: (1242.000, 499.000, 25.000)；WALK_1F_SIDE_ENTRANCE: (1607.482, 1504.217, 25.000) | 依上方房間門口 gap 表確認真實門外 WALKABLE，不以 component 數減少作為唯一目標。 |
| SV-00247 / LARGE_SAME_FLOOR_DISCONNECTION | 2F → `WALK_2F_BATHROOM`, `WALK_2F_CORRIDOR_01`, `WALK_2F_CORRIDOR_02`, `WALK_2F_CORRIDOR_03`, `WALK_2F_CORRIDOR_04`, `WALK_2F_GALLERY`, `WALK_2F_GALLERY_THRESHOLD`, `WALK_2F_MEETINGROOM`, `WALK_2F_MEETINGROOM_01_THRESHOLD`, `WALK_2F_MEETINGROOM_02_THRESHOLD`, `WALK_2F_OFFICE`, `WALK_2F_OFFICE_THRESHOLD`, `WALK_2F_CLASS201`, `WALK_2F_CLASS201_THRESHOLD`, `WALK_2F_CLASS202`, `WALK_2F_CLASS202_THRESHOLD`, `WALK_2F_CLASS203`, `WALK_2F_CLASS203_THRESHOLD`, `WALK_2F_CLASS204`, `WALK_2F_CLASS204_THRESHOLD` | WALK_2F_BATHROOM: (460.391, 1936.349, 165.000)；WALK_2F_CORRIDOR_01: (1011.577, 631.517, 165.000)；WALK_2F_CORRIDOR_02: (1435.643, 1104.254, 165.000)；WALK_2F_CORRIDOR_03: (1011.577, 1641.058, 165.000)；WALK_2F_CORRIDOR_04: (586.760, 1251.751, 165.000)；WALK_2F_GALLERY: (1020.265, 416.404, 165.000)；WALK_2F_GALLERY_THRESHOLD: (1090.000, 504.484, 165.000)；WALK_2F_MEETINGROOM: (1626.378, 641.004, 165.000)；WALK_2F_MEETINGROOM_01_THRESHOLD: (1761.000, 654.000, 165.000)；WALK_2F_MEETINGROOM_02_THRESHOLD: (1498.500, 714.975, 165.000)；WALK_2F_OFFICE: (1285.909, 2018.516, 165.000)；WALK_2F_OFFICE_THRESHOLD: (1432.000, 1704.811, 165.000)；WALK_2F_CLASS201: (360.000, 430.000, 165.000)；WALK_2F_CLASS201_THRESHOLD: (507.000, 533.000, 165.000)；WALK_2F_CLASS202: (360.000, 835.000, 165.000)；WALK_2F_CLASS202_THRESHOLD: (507.000, 935.000, 165.000)；WALK_2F_CLASS203: (360.000, 1240.000, 165.000)；WALK_2F_CLASS203_THRESHOLD: (507.000, 1340.000, 165.000)；WALK_2F_CLASS204: (360.000, 1640.000, 165.000)；WALK_2F_CLASS204_THRESHOLD: (507.000, 1742.000, 165.000) | 依上方房間門口 gap 表確認真實門外 WALKABLE，不以 component 數減少作為唯一目標。 |
| SV-00248 / PORTAL_ORIENTATION_UNRESOLVED | 1F → `PORTAL_1F_MEETINGROOM_02` | PORTAL_1F_MEETINGROOM_02: (1736.000, 880.000, 85.000) | 確認門位於哪個 AREA 邊界、另一側 region 與 normal；不由 nearest corridor 自動猜方向。 |
| SV-00249 / PORTAL_ORIENTATION_UNRESOLVED | 1F → `PORTAL_1F_SIDE_ENTRANCE` | PORTAL_1F_SIDE_ENTRANCE: (1636.000, 1505.000, 85.000) | 確認門位於哪個 AREA 邊界、另一側 region 與 normal；不由 nearest corridor 自動猜方向。 |
| SV-00250 / STAIR_CLEARANCE_UNRESOLVED | 1F、2F、1F→2F → `STAIR_A_ENTRY`, `STAIR_A_EXIT`, `STAIR_A_PATH` | STAIR_A_ENTRY: (1524.647, 1401.739, 22.862)；STAIR_A_EXIT: (1519.514, 1344.156, 161.000)；STAIR_A_PATH: (1581.507, 1372.947, 91.500) | 人工核對 body clearance 與評估 policy；footprint 接觸不足以批准。 |
| SV-00251 / STAIR_CLEARANCE_UNRESOLVED | 1F、2F、1F→2F → `STAIR_B_ENTRY`, `STAIR_B_EXIT`, `STAIR_B_PATH` | STAIR_B_ENTRY: (567.904, 1923.730, 25.126)；STAIR_B_EXIT: (625.412, 1921.099, 158.750)；STAIR_B_PATH: (596.658, 1979.680, 91.500) | 人工核對 body clearance 與評估 policy；footprint 接觸不足以批准。 |
| SV-00252 / UNRESOLVED_SETTING | 全場景／跨層 → Scene | 全場景／configuration；approved floor planes and geometry authority | 人工核准此列 setting 的 source-bound 定義／policy；本輪不調整研究閾值。 |
| SV-00253 / UNRESOLVED_SETTING | 全場景／跨層 → Scene | 全場景／configuration；physical clearance and contact semantics | 人工核准此列 setting 的 source-bound 定義／policy；本輪不調整研究閾值。 |
| SV-00254 / UNRESOLVED_SETTING | 全場景／跨層 → Scene | 全場景／configuration；camera-plane binding | 人工核准此列 setting 的 source-bound 定義／policy；本輪不調整研究閾值。 |
| SV-00255 / UNRESOLVED_SETTING | 全場景／跨層 → Scene | 全場景／configuration；wall/obstacle movement versus occlusion ownership | 19 個 OBSTACLE/BOTH 已人工確認，不重新分類；此提醒留給尚未標記的 WALL ownership 與實際 3D 阻擋／遮擋 volume，待人工補充。 |
| SV-00256 / UNRESOLVED_SETTING | 全場景／跨層 → Scene | 全場景／configuration；portal normal and endpoint declarations | 人工核准此列 setting 的 source-bound 定義／policy；本輪不調整研究閾值。 |
| SV-00257 / UNRESOLVED_SETTING | 全場景／跨層 → Scene | 全場景／configuration；stair path direction, clearance and slab opening evidence | 人工核准此列 setting 的 source-bound 定義／policy；本輪不調整研究閾值。 |

## 驗證與資產保存

pytest 783 passed／0 failed／0 skipped（53.62s）；Ruff、strict mypy（72 source files）通過。
最終 native replay／link／diff check 保存在 [report JSON](school_v3_semantic_validation.json)
的 `semantic_supplement_review.verification`。正式 schema／Graph／benchmark 未修改。

同名 school_v3.blend 已依授權保存，沒有 v4／render；來源 before→after SHA 與原始備份
在 update JSON。保存後 audit/read-only fingerprint 不變。`.blend` 依原 .gitignore 留在本機，
Git 只保存 source-bound patch、audit／report、診斷程式／tests／文件。
