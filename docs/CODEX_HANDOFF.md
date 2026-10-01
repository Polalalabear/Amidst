# Conversation handoff / 對話交接

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

更新日期：2026-10-01。已依序完成 M5–M8 收尾、驗證與獨立 commit，並依使用者要求停在 M8；沒有 push、PR 或 render。

### 已驗證的工作位置與 checkpoint

- 實際 repository：`/Users/polalabear/Developer/amidst`。舊環境可能仍顯示 `admist`；不要在舊路徑重建專案。
- Branch：`main`。
- 接續起點 HEAD：`58a809956cdfe444509e0d676ec2e8f6f382370c`（M4）。
- Remote：`https://github.com/Polalalabear/amidst.git`。本輪未 push。
- M5 已提交於 `1dcce12`、M6 已提交於 `7e952ae`、M7 已提交於 `94ee2cd`；M8 deterministic graph engine 為本輪最後一個 milestone。
- 使用 `uv`、`pyproject.toml`、`uv.lock`；不要改用 requirements.txt。
- Blender CLI：`/Applications/Blender.app/Contents/MacOS/blender`，5.2.1 LTS，build `9e2066aef7ef`。
- 舊 sandbox writable root 若仍是 `admist`，相關執行可能需要正常權限升級；這不是產品錯誤。所有 shell 指令明確指定正確 workdir。

### 授權、順序與停點

先完整閱讀 `docs/PRD.md`、`docs/SYSTEM_DESIGN.md`、`docs/ISSUES_AND_DECISIONS.md`，再接續現有程式。上個對話已完整閱讀，但新對話仍須自行確認。

使用者要求 M0、M1 後，若無重大問題便做 M2→M8；每個 milestone 都必須可執行、測試、獨立 commit，然後才進下一階段。完成 M8 就停止，不自動進入 M9 或 Agent Semantic Ranking。Phase 2 僅留 schema/interface。

重大設計、公開介面調整、來源資產改動、不確定 walkability 或 Ground Truth leakage 須詢問。小型工程問題可依現有規格處理。

Ground Truth 僅限 simulation/export、evaluation、debug visualization。不得流入 projection inference、topology/graph 搜尋、candidate ranking、semantic reasoning 或 path score。domain 只放 schema/interface，不能放幾何或搜尋演算法。

只有 29 台 `CAM_*` 參與研究；1 Blender unit = 1 meter。攝影機 local +X 右、+Y 上、-Z 前；左上原點連續像素、半開影像邊界。使用者同意研究副本與中性材質，沒有同意清理來源資產或渲染。

### 現況：M0–M8 已完成

| Milestone | 狀態／內容 |
| --- | --- |
| M0 | uv、Git、文件、Blender CLI 檢查完成 |
| M1 | 唯讀場景盤點與幾何補充 audit；原檔保留，建立 byte-identical 研究副本 |
| M2 | 可設定、確定性取樣；Blender transient target proxy 求值；timestamped GT JSON/CSV、seed 與來源綁定 |
| M3 | Camera schema、29 台實際相機抽取、world→pixel、FOV/clip；與 Blender 投影 parity 驗證 |
| M4 | evaluated Mesh raycast、OBSERVED/GAP、FOV/occlusion/fail-closed 原因、只含 2D 的 observation 匯出與來源 SHA 綁定 |
| M5 | Observation、ProjectedPoint、CandidateTrajectory、Event、ReconstructionResult、Provenance/termination 契約、nullable Phase 2 欄位與 serialization tests 完成；已補 termination/completion 一致性與空 shell 邊界 |
| M6 | 顯式 unit-normal Plane、camera/pixel fail-closed 驗證、ray-plane inverse projection、axial clipping、plane identity 與 incidence quality 完成；不接受 Ground Truth |
| M7 | 分離的 directed Camera Topology 與 configured navigation、3D polyline walkability checks、canonical minimum-distance route、顯式 synthetic parameterized stairs 完成；school 跨樓層維持 disconnected |
| M8 | topology-authorized reachability、minimum travel time、speed/length/detour hard pruning、deterministic Top-K、bounded termination、canonical candidate identity 與 sanitized M6→M8 major-flow integration 完成；Ground Truth／semantic ranking／path score 維持隔離 |

M5 從交接保留並納入本階段 commit 的檔案：

```text
docs/DATA_SCHEMA.md
docs/INTERFACES.md
src/amidst/domain/interfaces.py
src/amidst/domain/observation.py
src/amidst/domain/trajectory.py
tests/unit/test_observation_models.py
```

本交接文件 `docs/CODEX_HANDOFF.md` 也納入 M5 commit。接續時仍須重新 `git status` 確認，不能假設工作樹狀態未變。

M5 schemas 已包含時間／camera／identity 一致性、finite values、provenance 限制與 extra／GT 欄位拒絕。空 OBSERVED shell 可存在，但 M8 graph 會拒絕沒有 projected endpoints 的推論輸入。`ReconstructionResult.complete` 表示 configured bounded candidate space 已窮盡，限額終止不可誤標完整。

交接 review 發現的兩項 M5 收尾事項已處理：

- `domain/trajectory.py` 已驗證 reason/complete 一致性，並拒絕 `NO_FEASIBLE_PATH` 攜帶 candidates；相應 schema tests 已加入。
- `DATA_SCHEMA.md` 已註明空 OBSERVED shell 不等於有效 Evidence；M8 入口已另外檢查 projected endpoints。

尚未寫 synthetic frame→Observation aggregation helper；它若需要，屬於 simulation，不是 Phase 2 tracking/stitching。M6 已實作單一 camera／明確 Plane 綁定的 inverse projection；M7 已實作通用的 directed waypoint navigation 與 Camera Topology abstraction。M8 的 `SpatiotemporalGraphEngine` 只列舉每個 Camera Transition 明確引用的 ordered navigation edges；兩端與多跳 anchors 必須連續，不插入未授權 connector，也不改走未引用的短路。相同 ordered corridor 去重；camera return cycle 由正距離、速度、path length、detour、node、branch、time 與 K 限額約束。同 camera／同 node 可產生 stationary candidate；同 camera 不同 node 必須有明確離開／返回 transition cycle。

`max_paths` 與 policy `max_candidate_paths` 取較小值作 effective K，只有找到第 K+1 條不同且可行的 corridor 才回 `MAX_PATHS_REACHED`。Search node、branch 與 timeout 終止均為 `complete=false` 並保留已證明可行的候選。Timeout 使用可注入、有限且不得倒退的 monotonic clock；候選 ID 綁定 source/network、完整 endpoints、實際 route geometry/distance/time 與 movement speed。Graph engine 不讀 Ground Truth、projection quality、semantic fields，也不產生 `path_score`。沒有寫入 school navigation config、floor walkability 或 stair connectivity 宣稱。

### Scene Audit 核心結果與限制

報告：`data/scene_audit/school_v2_scene_audit.json`、`README.md`、`school_v2_geometry_audit.json`、`GEOMETRY.md`。

- 2,796 objects：2,652 Mesh、92 Empty、30 Camera、18 Light，以及少量其他類型；29 collections、260 materials、447 images（441 packed，5 missing）、489 modifiers、12 actions。
- 29 台 `CAM_*` 是有限值 perspective cameras；另有 `skp_camera_Last_Saved_SketchUp_View` 焦距非有限，排除但不刪除。
- 8 個高面數物件、18 個 imported lights、材質／貼圖與裝飾模型只列報告，未清理。neutral override 暫時替換表面材質，不改原始 slots、UV、images；未驗證 render pixels。
- 幾何補充只檢查 370 個結構 Mesh（25,098 triangles），排除 Areas annotation boxes；不是完整場景 NavMesh 認證。
- 主要 floor candidates：`z≈20.07885`、`z≈161.811096`；庭院另有 `z≈0.000112` 候選。候選地板與 raw overlap 不代表 walkability。
- 兩個樓梯標示區沒有找到 Mesh 支持的連續上升路徑；固定網格最高面皆在二樓高度。不能從名稱建立穿越樓板的 school 跨樓層邊。
- school 跨樓層配置維持 fail-closed，等待有效 entry/exit／parameterized path／geometry 確認；通用演算法與明確 `SYNTHETIC_TEST_FIXTURE` 的參數化樓梯測試仍可繼續 M6–M8（PRD §15、SYSTEM_DESIGN §14）。不要因此重開所有 milestone 的廣泛停工 gate。
- visibility 是固定 frame 的 evaluated VIEWPORT Mesh 點查詢，不是 render-pixel equivalence；render-only modifiers、透明度、影像可用性不在驗證範圍。

### 資產保全與資料上下文

原檔：`blender/school_v2.blend`。
研究副本：`blender/working/school_v2_research.blend`（Git ignored）。

交接時兩者 SHA-256 一致：

```text
1332280b8ca24ba8568017a13b666618c93337f32bcc431e59e7db617924fc38
```

本輪未修改、儲存或渲染任一 `.blend`。Blender scripts 使用 `--background --factory-startup --disable-autoexec -noaudio --python-exit-code 2`。整合測試只建立 transient factory fixtures；Blender adapters 使用標準函式庫與 lazy bpy/mathutils，避免依賴 Blender Python 具有 uv 的 Pydantic/NumPy 環境。

`configs/trajectory_fixture.json` 是 factory-scene synthetic fixture，不是核准的 school route。`data/cameras/school_v2_cameras.json` 是本機生成的真實 29 台校正資料，Git ignored。factory GT 不得混入 school camera/visibility 場景；school observation 匯出須有 BLENDER_EVALUATED GT 且三者來源 SHA 相同。生成 GT、camera、observations/candidates/metrics/.rrd 維持本機並 ignored。

### 最新驗證

於 M8 完整內容執行：

```sh
uv run pytest
uv run ruff check .
uv run mypy
git diff --check
shasum -a 256 blender/school_v2.blend blender/working/school_v2_research.blend
```

結果：**219 passed in 25.73s**，沒有 skipped／failed；Ruff 全通過；mypy 33 source files 無問題；diff check 無問題；兩個 `.blend` 雜湊一致。M8 直接 targeted tests 28 個通過。這證明目前 M0–M8 程式檢查通過，不代表 M9、school walkability、Projection Error evaluation 或 formal benchmark 已完成。

### Git commits（皆為本機）

```text
3238ec7 chore: initialize uv project
ab8a9d9 chore: add blender scene audit
c3a02c7 docs: confirm phase 1 camera and unit conventions
52b2b6e feat: add neutral surface material override
c3638c5 chore: add read-only floor and stair geometry audit
7add28b chore: record isolated research scene copy
2e9dd29 docs: scope stair gate to school cross-floor configuration
82fa2a3 feat: add blender ground truth export
251db8f feat: add virtual camera projection
58a8099 feat: add visibility and occlusion detection
1dcce12 feat: add observation domain models
7e952ae feat: add planar inverse projection
94ee2cd feat: add deterministic navigation topology
```

### 接續順序與待決策事項

M8 stop point 已到達；M9 blind-gap completion、Agent Semantic Ranking、evaluation 與 visualization 均未開始。除非使用者另行授權，不再向後執行 milestone。

待使用者確認的 school-specific 問題：實際樓梯 entry/exit 與路徑表示、庭院 floor／walkability 語意。Coverage@K 的 epsilon/正式定義需在 M10 benchmark 前確認；目前不因此阻塞通用 M6–M8。任何清理／修改來源資產、render、push/PR 或正式 Phase 2 都需要額外明確授權。

`ISSUES_AND_DECISIONS.md` 僅記錄核心問題→採用解法；不要放進 commit log、測試紀錄或一般 TODO。本交接狀態留在此文件，不改 PRD/SYSTEM_DESIGN。

## English

Resume in `/Users/polalabear/Developer/amidst`, branch `main`; the continuation started from M4 HEAD `58a809956cdfe444509e0d676ec2e8f6f382370c`. M0–M8 are complete and the requested M8 stop point has been reached. M5 schemas enforce termination/completion and empty-shell boundaries. M6 implements auditable explicit-plane inverse projection without Ground Truth input. M7 adds explicit directed topology/navigation and deterministic minimum-distance routing while leaving school cross-floor movement disconnected. M8 adds bounded topology-authorized Top-K generation, physical/time pruning and explicit termination without Ground Truth or semantic ranking. No push, PR, render, or asset modification occurred.

Read PRD, SYSTEM_DESIGN, ISSUES_AND_DECISIONS and the audit before any future work. Do not start M9 or later work without new authorization. Use uv. Domain contains contracts only. Ground Truth never enters inference, navigation/search, ranking or path scoring. Phase 2 and semantic ranking remain deferred.

Use only 29 CAM_* cameras and one unit per metre. The source and ignored research copy have identical SHA-256 shown above. Neutral materials use a reversible temporary surface override; no rendered-pixel claim is validated. Factory trajectory fixtures are not approved school routes and must not be mixed with school camera/geometry contexts.

M8 candidates preserve exact transition-authorized navigation edges and continuous anchors; no uncited connector or alternate shortcut is inserted. Equal physical corridors are deduplicated, return cycles remain bounded, and same-camera movement between distinct nodes needs an explicit leave-and-return cycle. `complete` is exhaustive only for the configured bounded candidate space; effective K is the smaller of request and policy cap, and truncation requires observing K+1 feasible corridors. Candidate identity includes the bound source/network, endpoints, physical route and speed. Ground Truth, semantic ranking and path score remain outside the engine.

Latest full checks: 219 tests passed (no skips), Ruff passed, strict mypy passed for 33 source files, diff check passed, both asset hashes match. School floor heights are candidates, not navigation certification. School stairs lack a confirmed mesh-supported ascent and remain disconnected until entry/exit/path representation is confirmed. Explicitly synthetic parameterized stair fixtures validate generic algorithms without inventing school connectivity. Courtyard interpretation and formal Coverage@K thresholds remain open, scoped to their relevant downstream work.
