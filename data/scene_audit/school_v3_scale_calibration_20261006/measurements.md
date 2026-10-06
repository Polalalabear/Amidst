# School v3 scale-calibration measurements / 尺度量測

Architectural scale: **0.0247 m/BU — APPROVED**.
Basis: USER_DEFINED_RESEARCH_MODEL_SETTING; measurements: SANITY_CHECK_EVIDENCE.
尺度由使用者明確核准；mesh 只作合理性檢查，不要求外部尺寸重新推導。
不縮放、不修改／儲存模型、不執行 benchmark；幾何邊界仍待各自核准。
Annotation 是標記尺寸；source 是指定高度的最近實體 mesh 兩側截面，
不自動證明牆、門框、全高度淨寬或通行性。完整端點／source polygons 見 JSON。

## Measurement table / 自動量測表

| Object / axis | Kind | Floor | Annotation BU | Source BU | Source m | Boundary |
| --- | --- | --- | ---: | ---: | ---: | --- |
| PORTAL_1F_AUDITORIUM:Y | DOOR | 1F | 72.000000 | 70.866211 | 1.750395 | HUMAN_REVIEW |
| PORTAL_1F_AUDITORIUM_OFFICE:Y | DOOR | 1F | 70.000000 | 70.865967 | 1.750389 | HUMAN_REVIEW |
| PORTAL_1F_CLASS101:Y | DOOR | 1F | 40.000000 | 55.118103 | 1.361417 | HUMAN_REVIEW |
| PORTAL_1F_CLASS102:Y | DOOR | 1F | 40.000000 | 55.118164 | 1.361419 | HUMAN_REVIEW |
| PORTAL_1F_CLASS103:Y | DOOR | 1F | 40.000000 | 55.118042 | 1.361416 | HUMAN_REVIEW |
| PORTAL_1F_CLASS104:Y | DOOR | 1F | 40.000000 | 55.118896 | 1.361437 | HUMAN_REVIEW |
| PORTAL_1F_MAIN_ENTRANCE:X | DOOR | 1F | 160.000000 | 142.663452 | 3.523787 | HUMAN_REVIEW |
| PORTAL_1F_MEETINGROOM_01:Y | DOOR | 1F | 110.000000 | 526.246765 | 12.998295 | HUMAN_REVIEW |
| PORTAL_1F_OFFICE:X | DOOR | 1F | 70.000000 | 70.866089 | 1.750392 | HUMAN_REVIEW |
| PORTAL_1F_RESTAURANT_A:X | DOOR | 1F | 40.000000 | 35.433105 | 0.875198 | HUMAN_REVIEW |
| PORTAL_1F_RESTAURANT_B:X | DOOR | 1F | 40.000000 | 35.432983 | 0.875195 | HUMAN_REVIEW |
| PORTAL_1F_STORAGE:Y | DOOR | 1F | 70.000000 | 70.866150 | 1.750394 | HUMAN_REVIEW |
| PORTAL_2F_BALCONY_LEFT:X | DOOR | 2F | 70.000000 | 67.747131 | 1.673354 | HUMAN_REVIEW |
| PORTAL_2F_BALCONY_RIGHT:X | DOOR | 2F | 70.000000 | 67.747192 | 1.673356 | HUMAN_REVIEW |
| PORTAL_2F_CLASS201:Y | DOOR | 2F | 40.000000 | 55.118103 | 1.361417 | HUMAN_REVIEW |
| PORTAL_2F_CLASS202:Y | DOOR | 2F | 40.000000 | 55.118164 | 1.361419 | HUMAN_REVIEW |
| PORTAL_2F_CLASS203:Y | DOOR | 2F | 40.000000 | 55.118042 | 1.361416 | HUMAN_REVIEW |
| PORTAL_2F_CLASS204:Y | DOOR | 2F | 40.000000 | 55.118896 | 1.361437 | HUMAN_REVIEW |
| PORTAL_2F_GALLERY:X | DOOR | 2F | 70.000000 | 992.127472 | 24.505549 | HUMAN_REVIEW |
| PORTAL_2F_MEETINGROOM_01:Y | DOOR | 2F | 20.000000 | 526.246689 | 12.998293 | HUMAN_REVIEW |
| PORTAL_2F_MEETINGROOM_02:Y | DOOR | 2F | 100.000000 | 526.246689 | 12.998293 | HUMAN_REVIEW |
| PORTAL_2F_OFFICE:X | DOOR | 2F | 70.000000 | 70.866089 | 1.750392 | HUMAN_REVIEW |
| WALK_1F_CLASS101:X | ROOM | 1F | 256.000000 | 255.905563 | 6.320867 | HUMAN_REVIEW |
| WALK_1F_CLASS101:Y | ROOM | 1F | 390.000000 | 391.732239 | 9.675786 | HUMAN_REVIEW |
| WALK_1F_CLASS102:X | ROOM | 1F | 256.000000 | 255.905579 | 6.320868 | HUMAN_REVIEW |
| WALK_1F_CLASS102:Y | ROOM | 1F | 390.000000 | 391.732361 | 9.675789 | HUMAN_REVIEW |
| WALK_1F_CORRIDOR_02:X | CORRIDOR | 1F | 111.538574 | 122.046997 | 3.014561 | HUMAN_REVIEW |
| WALK_1F_CORRIDOR_03:Y | CORRIDOR | 1F | 117.127686 | 126.778564 | 3.131431 | HUMAN_REVIEW |
| WALK_1F_CORRIDOR_04:X | CORRIDOR | 1F | 111.538574 | 145.667419 | 3.597985 | HUMAN_REVIEW |
| WALK_1F_OFFICE:X | ROOM | 1F | 350.000000 | 333.981995 | 8.249355 | HUMAN_REVIEW |
| WALK_1F_OFFICE:Y | ROOM | 1F | 600.000000 | 307.873901 | 7.604485 | HUMAN_REVIEW |
| WALK_2F_CLASS201:X | ROOM | 2F | 256.000000 | 255.905548 | 6.320867 | HUMAN_REVIEW |
| WALK_2F_CLASS201:Y | ROOM | 2F | 390.000000 | 391.732239 | 9.675786 | HUMAN_REVIEW |
| WALK_2F_CORRIDOR_02:X | CORRIDOR | 2F | 111.538574 | 122.046997 | 3.014561 | HUMAN_REVIEW |
| WALK_2F_CORRIDOR_03:Y | CORRIDOR | 2F | 117.127686 | 126.778564 | 3.131431 | HUMAN_REVIEW |
| WALK_2F_MEETINGROOM:X | ROOM | 2F | 260.000000 | 10.912476 | 0.269538 | HUMAN_REVIEW |
| WALK_2F_MEETINGROOM:Y | ROOM | 2F | 520.000000 | 297.631638 | 7.351501 | HUMAN_REVIEW |

## Vertical height / 樓層高差

```json
{
  "support_candidates": [
    {
      "floor": "1F",
      "object": "WALK_1F_CLASS101",
      "source_hit": {
        "object": "group_0",
        "evaluated_polygon_index": 2174,
        "endpoint_bu": [
          360.0,
          430.0,
          20.07884979248047
        ],
        "normal_world": [
          0.0,
          0.0,
          -1.0
        ],
        "distance_bu": 9.92115024112293,
        "source_polygon_vertices_bu": [
          [
            249.19427490234375,
            625.674072265625,
            20.07884979248047
          ],
          [
            489.351806640625,
            625.674072265625,
            20.07884979248047
          ],
          [
            280.6903381347656,
            233.94183349609375,
            20.07884979248047
          ]
        ],
        "hidden_render": false,
        "hidden_viewport": false,
        "semantic_role": "UNASSIGNED_SOURCE_GEOMETRY"
      }
    },
    {
      "floor": "2F",
      "object": "WALK_2F_CLASS201",
      "source_hit": {
        "object": "group_0",
        "evaluated_polygon_index": 2632,
        "endpoint_bu": [
          360.0,
          430.0,
          161.81109619140625
        ],
        "normal_world": [
          0.0,
          0.0,
          -1.0
        ],
        "distance_bu": 13.188904023119385,
        "source_polygon_vertices_bu": [
          [
            505.0603942871094,
            218.1938018798828,
            161.81109619140625
          ],
          [
            217.69821166992188,
            218.1938018798828,
            161.81109619140625
          ],
          [
            253.13128662109375,
            1852.012451171875,
            161.81109619140625
          ]
        ],
        "hidden_render": false,
        "hidden_viewport": false,
        "semantic_role": "UNASSIGNED_SOURCE_GEOMETRY"
      }
    }
  ],
  "vertical_height_bu": 141.73224639892578,
  "vertical_height_m": 3.5007864860534665,
  "authority": "HUMAN_REVIEW"
}
```

## Boundary sanity-check shortlist / 邊界合理性檢查候選

| Anchor | Source BU / range | m / range | Limitation |
| --- | --- | --- | --- |
| PORTAL_1F_RESTAURANT_A:X | [35.43310546875, 35.43310546875] | [0.875197705078125, 0.875197705078125] | Stable sampled cross-section; confirm physical boundary ownership |
| PORTAL_1F_OFFICE:X | [70.8660888671875, 70.8660888671875] | [1.7503923950195313, 1.7503923950195313] | Stable sampled cross-section; confirm physical boundary ownership |
| WALK_2F_CLASS201:Y | [391.73223876953125, 391.7322540283203] | [9.675786297607422, 9.675786674499511] | Stable sampled cross-section; confirm physical boundary ownership |
| WALK_1F_CORRIDOR_03:Y | [122.7030029296875, 126.77856445318376] | [3.0307641723632814, 3.131430541993639] | Variable/incomplete profile; confirm which cited boundaries define actual clear width |
| FLOOR_1F_TO_2F:Z | 141.73224639892578 | 3.5007864860534665 | Two horizontal-support candidates; floor authority remains separate |

若作為正式通行／碰撞資料，仍需確認來源面的角色與室內邊界。
這與已核准的 research architectural scale 是獨立的 authority。
缺法向門洞保留 unresolved；不從 bbox 中挑看起來像門寬的一邊。

## Missing portal orientation / 門洞方向待確認

- PORTAL_1F_LADYSROOM: PORTAL_NORMAL_NOT_UNIQUELY_DECLARED
- PORTAL_1F_MEETINGROOM_02: PORTAL_NORMAL_NOT_UNIQUELY_DECLARED
- PORTAL_1F_MENSROOM: PORTAL_NORMAL_NOT_UNIQUELY_DECLARED
- PORTAL_1F_SIDE_ENTRANCE: PORTAL_NORMAL_NOT_UNIQUELY_DECLARED
- PORTAL_2F_LADYSROOM: PORTAL_NORMAL_NOT_UNIQUELY_DECLARED
- PORTAL_2F_MENSROOM: PORTAL_NORMAL_NOT_UNIQUELY_DECLARED
