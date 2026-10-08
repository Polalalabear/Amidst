# 下一個工作 prompt / Engineering and research continuation

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

直接複製以下 prompt。既有 mock 接口與診斷工具已接入；以下 M1–M6 仍是後續實作範圍，不由本次整合推定完成。

```text
請完成 Amidst 純模擬環境的第一版可調用、可查找、可展示系統，並建立「2D camera 照片 → local tracks → 跨鏡頭候選關聯 → 3D 區域事件」研究入口。工程可先以有限精度形成閉環，持續改善；保留完整 GT、來源、時間、尺度、候選與不確定性。本階段不接真攝影機，也不串接 OpenAI 或其他外部模型 API。

一、起點、分支與資源

使用既有 checkout /Users/polalabear/Developer/amidst/.local-worktrees/phase1-finalization 和 codex/simulation-engineering；先確認 pwd、git status、branch、HEAD 與 origin。2026-10-08 的恢復 checkpoint 是 883204af854bed301506b39d63ccb33312b79ff2，文件 checkpoint 2c586b1 和 preview merge ded5572 已包含在工程分支。Projection 8f4055f 的相容診斷工具及 Phase 2 5b51d2c 的 additive mock adapters 已接入；讀 data/engineering/integration_20261008/compatibility.json，使用目前 GitHub 工程分支與最新已驗證 checkpoint，不 reset 到舊版本。

依序讀 docs/README.md、docs/specs/DEVELOPMENT_RULES.md、docs/operations/CODEX_HANDOFF.md、docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md、docs/engineering/PHASE2_INTEGRATION.md、docs/operations/PHASE1_RESTORED_RUNTIME.md、docs/operations/PHASE1_RESEARCH_RELEASE_HANDOFF.md、data/finalization/recovery_checkpoint_20261008/validation.json、data/finalization/reviewed_corridor_scope_checkpoint_v1/checkpoint.json；其餘文件按分類與本次問題讀取，不全目錄掃描。

重用這個 checkout 和既有 environment。工程碼使用專用 codex/simulation-engineering 分支（以 GitHub 上該分支或最新已驗證文件 checkpoint 為起點）；codex/docs-agent-handoff 只供本次文件整理。正式研究仍使用 phase1/finalization-sprint。同一 checkout 在工作狀態已保存且 clean 時切換分支，驗證後普通 push 對應 GitHub branch；不要為每個 milestone 建一份新 worktree、clone、venv 或 raw dataset 副本。GitHub branch 是版本入口，本機重型 scene/media 保留單一 immutable 來源。GitHub remote 不能取代本機執行環境或未公開素材；用 manifest、hash、materialization 與 replay refs 接入。分支間文件位置可能不同，依該分支的 docs/README.md 或實際正文路徑讀取。

canonical checkout /Users/polalabear/Developer/amidst 只供應 immutable Blender scene/raw artifacts，不切換它的 branch。保留無關修改與原始資產，不清理／刪除既有 worktree 或 media。phase2/integration-hardening / 5b51d2c 保持 FROZEN；從工程分支已接入的 repository/API/replay/consumer 擴充，不直接在 frozen branch 開發，不 whole-branch merge，不 merge main。
既有低階 API 能以 configs/integration/mock_v1.json 服務四個 synthetic cases，但尚非 Agent allowlist DTO；其 target_id／world coordinates／source references 不直接提供給 Agent。既有 importer 只認 COMPLETE artifacts.json v1.0 package，新 reviewed/finalization package 必須新增獨立 source/clock/unit adapter，核對 BU 與 METRES、顯式 normalization 並完成 import certification。不得用 mock PASS 當正式 package 驗證，也不重新匯入舊 branch 全套 core。可用 uv run python -m amidst.integration --config configs/integration/mock_v1.json --serve --port 8000 驗證本機接口。

二、資料、照片模式與地點模型

完整保存 simulation/GT package；hidden actor identity、3D position/path、recipe/reference annotations 留在獨立 evaluation/debug partition，不進 Agent、association、Graph、ranking 或一般 query payload。

新增外層 media/observation envelopes：
1 photos_only：完整合成照片，加必要 camera/frame/time/evidence references，不附 structured observation 答案。
2 photos_plus_observations：相同照片加上真正從圖片產生、來源明確的 bbox/keypoints/local tracks/可見特徵，以及准許的幾何衍生結果。
模擬投影 UV、image_measurement=false 資料保留原來源，不改称 CV 量測。兩模式共同使用合法 camera calibration、scene geometry、region map；GT 都完整另存。先固定相同照片、判斷階段與 population，再分開評估 camera retrieval 與 observation-mode 差異。TaskContext 固定 decision stage：該 run 判斷／association 前，photos_only 的 summary/detail/query 工具不能旁路取得已存投影、zone、candidate 或身分答案；完成 inference freeze 後才可在結果查詢 stage 回傳准許的事件結果。

建立 LocationRegistry／CameraCatalog：place_id、model_id/revision、source hash、spatial_context、coordinate frame、scale/normalization、run/clock、region geometry、camera groups、coverage mapping 和各項資料 origin/authority。保留原 camera_id，新增地點／模型 namespace；先按模型/run 分隔推論，再查各自 canonical records。名稱不證明 coverage 或 region authority。
第一版接入已有、能核對來源的地點；完成其他模型的匯入介面與 fixture，不虛構未提供資產的地點／鏡頭／跨模型 transform。
衍生子模型另保存 parent model revision/source hash、derivation manifest/hash、顯式 source→submodel transform（可為 identity）和原 camera/calibration correspondence；缺映射不得混用校正或 region 證書，subset/crop 不自動擴大 authority。

三、Agent 定位與可操作資源

先完成 docs/engineering/AGENT_RETRIEVAL_BOUNDARY.md 的角色與資料契約 review，落實為可驗證的 tools/DTO，再用 MockAgent 展示調用。Agent 負責定位資源、調用查詢、取得必要證據與解釋結果；不做 projection、region containment、pathfinding、collision 或 graph traversal。

給 Agent 精簡 TaskContext：place/model/source/context/run/clock/mode/registry 版本、opaque resource refs 和 allowed tools。預设讀 summary，必要時按 reference 取 detail/media/replay，不把整份 scene、NavMesh、camera matrices、所有座標、Embedding 或原始 metadata 注入 context，不提供 repository/filesystem/任意 SQL/shell 掃描工具。

實作 typed tools：resolve_place、list_cameras、query_observations、query_events、get_event_summary、get_event_detail、get_media、get_replay。摘要保留 scope、camera/time、evidence/event IDs、metadata來源與authority、candidate/hypothesis數、termination/complete、uncertainty 和 detail refs。完整 canonical payload 與候選順序另存；省略不表示不存在，search complete 不表示 query 成功。

四、本階段 API 與資料外洩邊界

只做本機 mock service/data-export 邊界，external egress 關閉。完成 mode/stage/source/context/run/reference 檢查與 allowlist DTO；Agent／工具／API／export 可見的 payload 和 logs 不帶 GT、hidden actor答案、secret、private filesystem paths 或完整 source archives。照片用 opaque references 透過本機 media 工具取得。獨立 local evaluation/debug 仍可保存 GT 與必要定位資料；不清洗或改寫 immutable 歷史紀錄。

不新增 OpenAI SDK、live provider、API key 配置或 live smoke call。OpenAI API 接線和大幅減少 token 的兜底演算法尚未正式：對應文件章節只保留空標題，內容挖空，不自行填入 model choice、token數值、壓縮、fallback、降級或重試策略，也不宣稱測得 token 降幅。

五、可一次推進的工程 milestones

M1：LocationRegistry／CameraCatalog／media索引／source-clock-unit bindings；至少能從地點查到真實存在的 camera/frame references。
M2：兩種觀測模式、資料輸出守門、local image perception/tracks；來源明確且不使用 simulator global identity 當跨鏡頭答案。
M3：跨鏡頭 association hypotheses、合法 projection、world-to-region、既有 Graph/reconstructor 的相容 adapter。保留歧義與全部替代候選，避免 fabricated self-camera handoff。
M4：重用已接入的 canonical snapshots、Memory/LOCAL_JSON、camera/time/event reads 與 legacy replay adapter；補 place/region 查詢及 Agent summary/detail/media/replay tools。GET 不重跑推論，不重新聚合來改寫永久 IDs；對新的 package 完成獨立 adapter certification。
M5：MockAgent 調用流程與可操作展示入口：地點定位→鏡頭/時間查詢→摘要→必要照片/細節→3D區域事件/replay。可以使用既有 Rerun 與影片素材，但不能只交預錄影片或接口 scaffold。
M6：共同 run 的 dataset/config/model-registry/media hashes、sample輸入輸出、模式比較、工具紀錄、GT/外洩邊界驗證、可重現命令與必要RRD/PNG；完成新增功能相稱的unit/integration與文件連結檢查。

有依賴就循序實作，獨立資料索引／工具／展示可並行。每個可執行 milestone 驗證後獨立 commit 並普通 push 對應工程 branch，續做下一 milestone；不因等待完整 formal研究而停在規劃或 scaffold。發布前檢查版本差異與 artifact policy，不上傳 LOCAL ONLY／private/secret/raw資產，不 force push 或改寫歷史。

六、正式研究仍需完成的工作

原 HR01–HR04、reference MOVING/departure-DWELL policy 和 exact corridor proposal 7524042121654d399188f52afd2bcfca29effb61287f96eb9f3da2159ddd1bad 已核准，不重問既有核准、不回寫歷史 bytes。office recovery run 是局部能力證據；舊 /tmp worktrees 和歷史 bulk raw 不在時依runtime指南由 exact inputs重建，不引用不存在的檔案。

若本輪使用新 corridor union，完成必要 scoped adapters、source-bound same-camera HOLD 和原 Case2 portal/anchor gate；保留真 recovery與分開GAP，既有route-class lower bound不冒充exhaustive inventory。

正式 Cases1–3/A-B-C/必要消融、相同 eligibility 的獨立 exhaustive inventory、fresh 5Hz frozen run 與完整 clean-checkout reproduction 保持有效待辦並行推進。工程MVP完成不等於 PHASE1_VALIDATED_AND_FROZEN；未量測指標保持N/A，Case2/Case3 full stress未過仍BLOCKED，原full Exit全過才freeze，Case4 DEFERRED。

持續到本輪M1–M6的可操作閉環完成。更新handoff、WORK_LOG與相關契約，清楚區分已實作、已驗證、formal未完成與空白保留章節；保留原source/protocol/checkpoint和所有無關修改，不merge main。
```

## English

The copyable prompt above authorizes a larger local synthetic/mock engineering scope with validated commits and ordinary pushes at executable milestones. Reuse one checkout/environment and shared immutable assets; do not accumulate a worktree or raw-data copy per milestone. Review Agent roles and typed summary/detail/media tools before exposing retrieval resources. OpenAI wiring and the token fallback algorithm stay blank, and no external model calls are made. Formal Phase 1 acceptance remains a separate, unchanged obligation.
