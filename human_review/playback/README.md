# Phase 1 playback workspace

查看與播放入口：`http://127.0.0.1:8768/playback/`。桌面視窗同時呈現人物動畫、拓樸、
模型／相機與側視高度，共用一條時間軸。每格右上角可放大，返回後仍保留相同時間。
Space 播放／暫停，左右方向鍵逐格；支援 0.5×／1×／2×、循環與全螢幕。
小視窗也保留四格與共同控制，細節可個別放大。

本頁沒有人工審查操作。原 `human_review/index.html` 與所有舊證據／播放器保留原始
內容。既有 50 格、5 Hz、10 秒素材是 **DIAGNOSTIC**；最後一格為 9.8 秒。
原影像中的 pending 標籤描述影像產生時的狀態，不能代替目前的套用結果。
目前狀態由 2026-10-08 checkpoint `883204af854bed301506b39d63ccb33312b79ff2`
的八份固定 receipt 建立，來源 SHA256 保存在 `status_snapshot.json`。

- HR01–HR04 已核准並套用。局部 physical authority 為 `PARTIAL_APPROVED`。
- Case 1：核准 Office 局部正式執行完成。
- Case 2：新 corridor 已核准；所需 adapters、route inventory 與完整 fresh run 未完成。
- Case 3：Office 時間分量完成；detour／candidate-growth 驗證未完成。
- Phase 1 仍為 `PHASE1_FINALIZATION_BLOCKED`。原驗證紀錄與本次 UI 檢查分開記錄。

拓樸 node／vertex 保持固定；P(t) 才是人物位置。GAP 內顯示既有 candidate，沒有新增
路徑、移動節點或改變 camera binding。模型射線沿用原 source mesh 求交診斷。
相機代表影格只有 4／5／9 秒，另開面板明確標示時間，不冒充連續相機影片。

## Rebuild and serve

在此 branch 的 repo root 執行（Python 3.12）：

```sh
uv sync --locked
uv run python -m human_review.build_playback_workspace \
  --media-root /absolute/path/to/existing/human_review
uv run python -m http.server 8768 --bind 127.0.0.1 --directory human_review
```

`--media-root` 指向已保存原始圖片的 `human_review/`，只補缺少的 58 張播放器圖片；
所有圖片比對原 manifest 的 SHA256 與大小，已存在但不一致的檔案會拒絕覆寫。
本機已具備原圖時可省略參數。工具不啟動 Blender、不讀 GT、不執行 inference。
GitHub 保存程式、狀態摘要與 hash manifest；PNG 與生成的 `data.js` 保留本地。
因此 fresh clone 仍需原本的 local media package，GitHub branch 本身不是公開影片網站。

這次本機可用的原素材位置（只作操作便利，並非新的 provenance）：
`/Users/polalabear/Developer/amidst/data/pilot/phase1_finalization_human_review_20261007/approvals_recorded/human_review`。
舊頁面的其他 129 張 ignored 圖片亦從同一保存位置逐檔比對後補回，未變動來源。

`build_manifest.json` 記錄 12 份輸入／receipt 與 58 張原圖的 hashes；`data.js`
可確定性重建。若研究狀態有更新，須明確更新 receipt pins 並重建，不會在瀏覽器內
自動套用任何新決策。播放器載入失敗時保留上一個完整同步影格並顯示錯誤。

## UI validation

```sh
uv run pytest tests/unit/test_playback_workspace.py
uv run ruff check human_review/build_playback_workspace.py \
  human_review/build_playback_status.py tests/unit/test_playback_workspace.py
uv run mypy --strict --explicit-package-bases \
  human_review/build_playback_workspace.py human_review/build_playback_status.py
node --check human_review/playback/player.js
git diff --check
```

English: A view-only, synchronized four-pane workspace over existing diagnostic media.
Current project progress is sourced from pinned receipts and remains separate from historical
display evidence. No decisions, research thresholds, source geometry or formal outputs change.
