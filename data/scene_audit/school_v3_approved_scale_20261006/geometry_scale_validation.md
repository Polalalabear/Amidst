# Approved school v3 scale validation / 已核准尺度驗證

**PASS — 1 BU = 0.0247 m；APPROVED，使用者定義的研究模型尺度。**

Mesh measurements are sanity-check evidence; external dimensions are not required.
原始 .blend SHA-256／size／mtime、所有 native vertices／faces／planes／ownership 不變。
Checked 285 BU/metre pairs across 37 rows; native surfaces: 1669.
Floor support rise: 141.732246 BU = 3.500786 m.

可靠截面未顯示尺度明顯不合理；以下 5 筆是 nearest-hit binding 異常，
不能宣稱為真實門寬或房間寬，也不以 sanity check 重新推導已核准尺度。

| Measurement | Source section BU | Converted m | Source / annotation |
| --- | ---: | ---: | ---: |
| PORTAL_1F_MEETINGROOM_01:Y | 526.246765 | 12.998295 | 4.784062 |
| PORTAL_2F_GALLERY:X | 992.127472 | 24.505549 | 14.173250 |
| PORTAL_2F_MEETINGROOM_01:Y | 526.246689 | 12.998293 | 26.312334 |
| PORTAL_2F_MEETINGROOM_02:Y | 526.246689 | 12.998293 | 5.262467 |
| WALK_2F_MEETINGROOM:X | 10.912476 | 0.269538 | 0.041971 |

Scale approval removes SCALE_NOT_APPROVED; physical authority remains PROVISIONAL.
Floor／stair／obstacle volume／body／clearance 仍須各自核准，formal scopes 持續拒絕。
原 0.28 BU doorway protection = 0.006916 m；沒有改變原始 BU 邊界或診斷門檻。

[Approved geometry](geometry.json) · [Physical authority](physical_authority.json) ·
[Measurement evidence](../school_v3_scale_calibration_20261006/measurements.md) ·
[Unit contract](../../../docs/GEOMETRY_PROVIDER.md)

SI inputs must use source-bound adapters before the core. Legacy runner/pilot exports
remain historical native inputs until explicitly normalized; no automatic migration.
No Graph/Top-K/GT/metric semantics or historical benchmark artifacts changed.
