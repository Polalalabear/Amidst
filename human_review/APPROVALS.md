# 已完成的人工決策

2026-10-07：使用者先確認「綁對」，再接受 rigid landmark 建議並明示「好，其他全部 approved」。
四項 decision 均已記錄為 **APPROVE**；未新增選項或改動原問題 payload。

| ID | 已選 profile | 核准內容 |
| --- | --- | --- |
| HR-01 | `LOCAL_SOURCE_SURFACE_ONLY` | 既定 office body envelope 內的 source surface 語意；faces 1975／2398 為零面積，不核准整個 component |
| HR-02 | `SOURCE_BOUND_RIGID_LANDMARK_OFFSET` | 目標房間／兩台鏡頭綁定；直立、同 XY、固定高度的 landmark 轉 floor contact；office offset 1.359735 m |
| HR-03 | `ADE_EPSILON_0_50_M` | Coverage D=ADE，嚴格 ADE < 0.50 m |
| HR-04 | `EXISTING_SPEED_WITH_SUPPORTED_DWELL` | 最大速度 32 BU/s＝0.7904 m/s；uniform first，僅 departure dwell，slack tolerance 1.0 s |

[decisions.json](decisions.json) 保存選項與 chat-origin reviewer／記錄時間。
[approval_record.json](approval_record.json) 保存原話、scope、檔案與不可變 payload hashes；
時間代表記錄時間，沒有捏造訊息時間或簽名。
[approval_validation.json](approval_validation.json) 記錄唯讀驗證：source hash、checkpoint ancestry、
29 個固定輸入、57 張原審查影格均通過，pending／blocking 均為空。

目前狀態：**EXPLICIT_APPROVALS_READY_FOR_AUTOMATIC_CERTIFICATION**。
人工 gate 已完成；本輪沒有 `--apply`、certificate regeneration、formal dataset／Cases 或 freeze。
physical certificate 仍為 **NOT_RUN**，`formal_execution_enabled=false`。
兩種追蹤方案都要求 fresh observations；既有 diagnostic 不升為 FORMAL。

下一階段從 [decision application](DECISION_APPLICATION.md) 的 fresh-output `--apply` 開始，
接續 bounded certificate、正式設定與 Case inventory 的自動驗證。只在真正的新 geometry
矛盾或超出本次核准 scope 時重開人工 gate，不要求第二輪人工資料整理。
