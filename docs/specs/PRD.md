**跨視角 2D 轉 3D 空間缺失與盲區軌跡補全系統(Agent AI 驅動之智慧監控數位孿生系統** **)**

## **Research Prototype Edition**

---

## 1. 研究定位與核心問題

在分散式多視角監控環境中，每台攝影機只能觀測有限的空間範圍。當人物離開攝影機 **FOV**、受到牆面或建築結構遮擋，或進入沒有攝影機覆蓋的區域時，跨視角軌跡會產生中斷。原始 PRD 將此問題放在完整的 Cross-Camera Event Reconstruction 中，並透過 **Camera Topology、Spatiotemporal Graph、Agent Arbitration 與 3D Digital Twin** 重建完整事件。    PRD_v2

PRD v3 將研究範圍收斂至一個可獨立驗證的問題：**在已知 3D 場景、攝影機幾何與部分 2D 觀測的條件下，能否重建攝影機不可見區域中的物理可行 3D 軌跡。**

這個問題包含兩個相連但需獨立評估的部分。第一個是 **2D-to-3D Projection**，負責將實際可觀測的 2D 位置映射回世界座標；第二個是 **Blind-area Trajectory Completion**，當直接觀測消失時，利用 NavMesh、Camera Topology、時間限制、人體移動限制與場景語意產生多條可能的 3D 軌跡。

本階段的核心研究問題可表示為：

> **在純 3D 模擬環境中，利用空間拓撲與時空硬約束進行確定性剪枝，再對剩餘的多解情況加入語意多假設推論，能否有效補全跨視角盲區中的 3D 連續軌跡？**
>

Phase 1 是 **Research Prototype**。實體攝影機、商業監控室 UI、人物 ReID、Web 播放、正式資料庫與操作員調查效率等問題保留至後續產品化。原 PRD 將成功條件建立在降低 Control-room Operator 的人工搜尋與跨攝影機推理成本上；這項產品目標仍保留，但不屬於本階段驗收範圍。    PRD_v2

---

## 2. 不可違背的架構核心原則

PRD v3 保留原始架構中最重要的責任分離。**Geometry、Projection、Reachability、NavMesh Search、Travel-time Constraint 與 Collision Constraint** 必須由確定性演算法處理；Agent 或語意推論只處理已通過物理限制後仍存在的歧義、場景語意與多假設排序。原 PRD 同樣限制 Agent 不直接處理 Raw CV、Graph Traversal、Coordinate Projection 或 Shortest-path Calculation。    PRD_v2

所有物理上不可能的候選，例如穿牆、不可達區域、超速移動、時間倒流與不合法樓層轉換，必須由 **Spatiotemporal Graph Engine** 在語意推理之前排除。若存在多條合理路徑，系統必須保留 **Top-K Candidate Trajectories**，不能因展示方便而強迫輸出單一結果。

所有軌跡資料同時必須保有明確的 **Provenance**。`OBSERVED` 表示攝影機直接取得的 2D Evidence，`PROJECTED` 表示將直接觀測映射至 3D 後的結果，`INFERRED_GAP` 表示沒有直接觀測時由系統補全的軌跡，而 `GROUND_TRUTH` 僅存在於 Blender 模擬與 Evaluation 層。原 PRD 已建立 `OBSERVED / PROJECTED / INFERRED_GAP` 三種來源分類。    PRD_v2

---

## 3. Phase Scope

Phase 1 必須形成一條完整且可量化的研究閉環：

```
Blender Ground Truth → Virtual Camera Projection → Partial 2D Observation
→ 2D-to-3D Projection → Spatiotemporal Graph
→ Top-K Feasible Trajectories → Optional Semantic Reasoning
→ Ground Truth Evaluation → Rerun Visualization
```

研究核心包含 **Blender Ground Truth、Virtual Camera、FOV/Occlusion、2D Observation、Inverse Projection、Camera Topology、NavMesh、Graph Candidate Generation、Blind-gap Reconstruction、Stair Transition、Provenance、ADE/FDE/Top-K Coverage 與 Rerun Visualization**。

Phase 2 則保留原產品架構位置，但暫不進行實際開發。原本的 **Detection、Tracking、Tracklet Stitching、ReID 與 Appearance Retrieval** 由 Blender Target ID 與 Synthetic Observation 暫代；原本的 **PostgreSQL、Vector DB、Object Storage 與 Topology Cache** 由本機 JSON、SQLite 或記憶體結構暫代；Three.js、HTML5 Video Player、Global Timeline 與 Soft Synchronization 則由 **Rerun SDK** 暫代。原 PRD 對上述 CV、Storage 與 Presentation 元件已有完整位置定義，因此新版只延後實作，不移除其 Interface。    PRD_v2     PRD_v2

---

## 4. Blender 模擬環境與 Ground Truth

Blender 同時作為 **Digital Twin、Simulation Environment 與 Ground Truth Source**。場景至少包含 Building Geometry、Floor、Zone、Walls、Static Obstacles、Walkable Area、NavMesh、Stair、Camera Position、Camera Direction、Camera FOV 與必要的 Semantic Regions。這些空間資訊原本已存在於 PRD v2 的 3D Digital Twin 定義中。    PRD_v2

人物沿預先定義或程序生成的路徑移動，每個時間點保存完整世界座標與場景資訊：

```
GroundTruthTrajectory
├── trajectory_id
├── target_id
├── timestamp
├── X / Y / Z
├── velocity
├── floor_id
├── zone_id
└── semantic_region
```

**Ground Truth 必須與 Reconstruction Pipeline 隔離。** Graph Engine、Agent、Candidate Ranking 與 Path Score 都不能讀取 `ground_truth_3d` 或未來真值位置；這些資料只供 Evaluation 與 Debug Visualization 使用。

---

## 5. Virtual Camera 與模擬觀測

每台虛擬攝影機保存 Camera ID、Floor、Zone、Position、Rotation、Intrinsic / Extrinsic Parameters、Resolution、FOV、Adjacent Cameras 與 Walkable Connections。Camera Topology 的基本資訊沿用原 PRD 中 Camera ID、Floor、Zone、3D Position、Viewing Direction、FOV、Adjacent Cameras、Transition Type 與 Walkable Connection 的定義。    PRD_v2

Blender 將世界座標：

\[
(X,Y,Z)
\]

正向投影成：

\[
(u,v)
\]

並透過 **Camera Frustum、Depth 與 Raycast** 判斷目標是否真正可見。可見時輸出 `OBSERVED`，超出 FOV 或受到幾何遮擋時輸出 `GAP`。

模擬資料的最小格式為：

```
{
  "frame_id": 120,
  "timestamp": 12.0,
  "target_id": "sim_person_01",
  "camera_id": "cam_1f_hallway",
  "status": "OBSERVED",
  "point_2d": [320, 480],
  "ground_truth_3d": [12.5, 4.2, 0.0]
}
```

當 `status = "GAP"` 時，`point_2d = null`。`ground_truth_3d` 仍存在於 Benchmark Record 中，但不進入 Reconstruction Pipeline。

---

## 6. Observation Abstraction

為了讓 Phase 1 能直接銜接未來產品化，系統仍採用原 PRD 的 **Observation** 概念。原設計將 Observation 定義為人物在特定 Camera、特定時間區間內形成的穩定 Evidence Unit。    PRD_v2

```
{
  "observation_id": "obs_101",
  "target_id": "sim_person_01",
  "camera_id": "cam_01",
  "floor_id": "1F",
  "zone_id": "corridor_A",
  "start_time": 10.0,
  "end_time": 25.0,
  "track_ids": ["sim_track_1"],
  "appearance_embedding": null,
  "appearance_quality": null,
  "projected_path": [
    [12.1, 4.0, 0.0],
    [14.5, 4.0, 0.0]
  ],
  "projection_quality": 0.98,
  "tracking_quality": null,
  "stitching_count": 0,
  "provenance": "PROJECTED"
}
```

Phase 1 尚未實際使用的 Appearance、Tracking 與 Stitching 欄位保留為 `null`，藉此維持未來 Interface 相容性。

---

## 7. 2D-to-3D Projection

Phase 1 先採用 **Piecewise Planar Assumption**，每個主要樓層具有獨立 Ground Plane。Observed 2D Point 透過 Camera Geometry 映射回世界座標：

\[
(u,v)\xrightarrow{\text{Camera Geometry}}(\hat X,\hat Y,\hat Z)
\]

可使用 **Homography、Projection Matrix 或 Ray-plane Intersection**，這些方法同樣存在於原 PRD 的 Projection 設計中。    PRD_v2

每個結果需保存 World Position、Projection Quality 與 `PROJECTED` Provenance。投影誤差定義為：

\[
E_{\text{projection}}
=
\left\|
\hat p_t-p_t^{GT}
\right\|_2
\]

**Projection Error 必須與 Blind-gap Reconstruction Error 分開統計**，避免將幾何投影誤差與盲區推論誤差混為同一問題。

---

## 8. Camera Topology 與 NavMesh

系統同時維護 **Camera Topology** 與 **Walkable Geometry**。Camera Topology 描述 Camera Adjacent Relationship、Floor / Zone Transition 與可能的移動方向；NavMesh 描述實際可行走區域、牆面與障礙限制、真實 Walkable Distance 與 Stair Connection。

兩者共同提供 Graph Engine 所需的空間限制：

```
Camera Topology + NavMesh + Time Constraint + Movement Constraint
→ Physically Feasible Candidate Space
```

---

## 9. Spatiotemporal Graph Engine

Graph Engine 的核心責任只有一項：**產生符合所有空間與時間硬約束的 Top-K Candidate Trajectories。**

原 PRD 已要求 Graph Engine 處理 Reachability、Minimum Travel Time、Timestamp Continuity、Direction、Blind Gap 與 Path Quality，並在 Agent 取得候選之前確定性排除不可能路徑。    PRD_v2

Graph Engine 的主要輸入為 Start Observation、End Observation、Camera Topology、NavMesh、Time Gap 與 Movement Constraints。最短物理移動時間定義為：

\[
\Delta T_{\min}
=
\frac{D_{\text{NavMesh}}}{V_{\max}}
\]

當：

\[
\Delta T_{\text{actual}} < \Delta T_{\min}
\]

該候選直接被判定為 `PHYSICALLY_IMPOSSIBLE`。

候選生成可使用 **Dijkstra、A*、K-Shortest Paths 或 Constrained BFS**。PRD 不固定演算法，實際方法依 Prototype Benchmark 決定，此原則亦沿用原設計。    PRD_v2

---

## 10. Candidate Trajectory

每個候選軌跡至少保存：

```
CandidateTrajectory
├── candidate_id
├── start_observation_id
├── end_observation_id
├── polyline[]
├── navmesh_corridor[]
├── path_length
├── minimum_travel_time
├── estimated_travel_time
├── spatial_cost
├── temporal_cost
├── semantic_regions[]
├── feasibility_flags[]
├── path_score
└── provenance = INFERRED_GAP
```

只有通過所有 Hard Constraint 的 Candidate 才能送往後續排序或語意推論。

---

## 11. Search Safety 與 Termination

所有 Graph Search 必須具有 deterministic termination。原 PRD 已使用 `max_search_hops`、`max_event_duration`、`max_candidate_paths`、`max_branch_factor` 與 `path_score_pruning` 控制搜尋複雜度。    PRD_v2

Phase 1 對應使用 `max_candidate_paths`、`max_search_nodes`、`max_path_length`、`max_search_time`、`max_branch_factor` 與 `max_detour_ratio`。搜尋結果需明確保存 `COMPLETE`、`NO_FEASIBLE_PATH`、`MAX_PATHS_REACHED`、`SEARCH_TIMEOUT` 等 Termination Reason。

---

## 12. Blind-area Trajectory Completion

Blind Gap 定義為：

```
Observed A → Missing Interval → Observed B
```

其可觀測時間差為：

\[
\Delta T_{\text{actual}}=T_B-T_A
\]

當 \(\Delta T_{\text{actual}}\) 接近 \(\Delta T_{\min}\) 時，系統採用 NavMesh 最短或近最短路徑進行時間參數化補全，產生 `INFERRED_GAP / DIRECT_PATH`。

當場景中存在多個可行走廊時，系統保留 Top-K，而不提前選定單一路徑。

若：

\[
\Delta T_{\text{actual}}\gg\Delta T_{\min}
\]

則定義額外時間：

\[
\Delta T_{\text{slack}}
=
\Delta T_{\text{actual}}
-
\Delta T_{\min}
\]

這段時間可能由 detour、dwell、slower movement 或其他合理路徑造成。系統可以建立多種假設，但**不能直接把 Temporal Slack 解釋成某種確定的人類行為**。

---

## 13. Semantic Gap Reasoning

Semantic Reasoning 在 Phase 1 屬於 **Optional Research Extension**。它接收已通過 Graph Hard Pruning 的 Top-K Candidate、Time Slack 與 Semantic Regions，並提供候選之間的語意排序與說明。

例如：

```
Candidate A: Corridor → Restroom Region → Corridor
Candidate B: Corridor → Waiting Area → Corridor
Candidate C: Direct Corridor
```

Agent 可以說明某條路徑為何能較合理地解釋 Temporal Slack，但不能自行產生「80% 進入洗手間」這類沒有校準依據的機率。輸出只需保存 `semantic_rank`、`explanation`、`supporting_context`、`conflicts` 與 `uncertainty`。

Phase 1 的 Agent Interface 因此縮減為：

```
propose_feasible_trajectories(...) → rank_gap_hypotheses(...)
```

完整 Tool-calling Agent 保留至 Phase 2。

---

## 14. Event / Reconstruction Result

原 PRD 將 **Event** 定義為包含 Observations、Transitions、Alternative Candidate Paths、3D Trajectory、Inferred Gaps、Provenance 與 Termination Reason 的最終單位。    PRD_v2

PRD v3 保留這個資料抽象，但將其用途改為 Research Reconstruction Result：

```
{
  "event_id": "evt_001",
  "target_id": "sim_person_01",
  "time_range": [10.0, 85.0],
  "observations": ["obs_101", "obs_102"],
  "trajectories": [
    {
      "hypothesis_id": "path_01",
      "path_score": 0.85,
      "segments": [
        {
          "type": "PROJECTED",
          "camera_id": "cam_01",
          "time": [10.0, 25.0]
        },
        {
          "type": "INFERRED_GAP",
          "semantic_reason": "possible_dwell_region",
          "time": [25.1, 65.0]
        },
        {
          "type": "PROJECTED",
          "camera_id": "cam_02",
          "time": [65.1, 85.0]
        }
      ]
    }
  ],
  "termination_reason": "COMPLETE"
}
```

---

## 15. Stair Representation

樓梯維持原 PRD 的 Parameterized Transition：

```
Stair Entry → Parameterized Stair Path → Stair Exit
```

它負責樓層連通、Vertical Position、Travel Time、Graph Search、Candidate Generation 與 Visualization。Phase 1 不要求對完整人體在樓梯中的移動進行自由形式 3D Reconstruction。原 PRD 已以相同方式將樓梯視為明確的空間 Transition。    PRD_v2

---

## 16. Provenance 與 Ground Truth Isolation

完整資料來源關係為：

```
OBSERVED → PROJECTED → INFERRED_GAP
                     ↘ Evaluation ↔ GROUND_TRUTH
```

`GROUND_TRUTH` 只能進入 **Evaluation 與 Debug Visualization**，禁止進入 Graph Engine、Candidate Ranking、Agent Prompt 或 Path Score。任何 Ground Truth Leakage 都視為 Benchmark Invalid。

---

## 17. Synthetic Benchmark

Phase 1 使用四種標準情境：

| **測試** | **場景** | **驗證重點** |
| --- | --- | --- |
| **Case 1：直線盲區** | Cam A → 30 m Corridor → Cam B | Projection、Direct Path、ADE/FDE |
| **Case 2：分歧盲區** | Cam A → T-junction → Multiple Routes → Cam B | Top-K Candidate Preservation |
| **Case 3：時間異常** | 最短約 20 s，實際 Gap 約 180 s | Temporal Slack、Semantic Hypothesis |
| **Case 4：跨樓層** | Cam A 1F → Stair → Cam B 2F | Vertical Continuity、Stair Constraint |

---

## 18. Quantitative Evaluation

對 `PROJECTED` Evidence 先獨立量測 Projection Error：

\[
E_t=\|\hat p_t-p_t^{GT}\|_2
\]

Blind-gap Reconstruction 則使用 **ADE**：

\[
ADE=
\frac{1}{T}
\sum_{t=1}^{T}
\|\hat p_t-p_t^{GT}\|_2
\]

以及 **FDE**：

\[
FDE=
\|\hat p_T-p_T^{GT}\|_2
\]

當輸出包含 \(K\) 條 Candidate 時，另外使用：

\[
minADE@K=\min_{k\leq K}ADE(P_k,P_{GT})
\]\[
minFDE@K=\min_{k\leq K}FDE(P_k,P_{GT})
\]

Top-K Coverage 定義為：

\[
Coverage@K=
\mathbf{1}
\left[
\min_{k\leq K}D(P_k,P_{GT})<\epsilon
\right]
\]

其中 \(D\) 與 \(\epsilon\) 必須在正式 Benchmark 前固定。

除了幾何誤差，系統必須同步記錄 **Collision Rate、Constraint Violation Rate、Impossible Transition Rate、Path Length Error、Travel-time Error 與 Feasible Candidate Recall**，避免出現幾何距離小但實際穿牆的假性良好結果。

---

## 19. Initial Acceptance Criteria

Phase 1 的初始目標為：Case 1 的 **ADE 與 FDE 均不高於 0.5 m**；Case 3 的終點 **FDE 不高於 1.0 m**；整體 **Coverage@3 至少 90%**；所有正式輸出的 Candidate 必須維持 **Collision Rate = 0** 與 **Impossible Transition Rate = 0**。

這些數值屬於 **Prototype Initial Target**。若實際場景尺度、Camera Configuration 或 Simulation Resolution 顯示門檻不合理，可在首輪 Benchmark 後重新校準，但必須保留調整理由與前後結果。

---

## 20. Baseline 與 Ablation

Research Prototype 將原 PRD 的 Baseline Evaluation 轉換成針對重建演算法的消融比較。原 PRD 已採用分層 Baseline 來分析各模組真正帶來的增益。    PRD_v2

| **Configuration** | **功能差異** | **驗證用途** |
| --- | --- | --- |
| **Shortest Path** | NavMesh 最短路徑 | 最簡單幾何基準 |
| **Graph-Geometric** | NavMesh + Speed + Time | 硬約束增益 |
| **Graph + Semantic** | 加入 Semantic Regions | 場景語意增益 |
| **Graph + Agent** | 加入 Agent Ranking | Agent 額外價值 |

Case 3 的初始研究目標為：

\[
ADE_{\text{Proposed}}
\leq
0.7\,ADE_{\text{Baseline}}
\]

也就是相對 Baseline 至少改善 **30%**。

---

## 21. Rerun Visualization

Phase 1 使用 **Python Rerun SDK** 顯示 Building Geometry、Camera Position、Camera Frustum、Observed Evidence、Projected Evidence、Top-K Candidate Paths、Selected Hypothesis 與 Ground Truth。

Provenance 使用固定視覺語意：

| **來源** | **呈現** |
| --- | --- |
| **OBSERVED** | 綠色 |
| **PROJECTED** | 藍色 |
| **INFERRED_GAP** | 橘色虛線 |
| **GROUND_TRUTH** | 灰色點線 |

`GROUND_TRUTH` 僅在 Debug / Evaluation Mode 顯示。

---

## 22. Edge Cases

| **情境** | **系統行為** |
| --- | --- |
| **No Blind Gap** | 不啟動 Gap Inference |
| **Single Feasible Path** | 直接輸出 deterministic candidate |
| **Multiple Feasible Paths** | 保留 Top-K |
| **Impossible Transition** | 回傳 `NO_FEASIBLE_PATH` |
| **Insufficient Travel Time** | 排除候選 |
| **Large Temporal Slack** | 允許 detour / dwell hypotheses |
| **Occluded Observation** | 標記為 `GAP` |
| **Cross-floor Movement** | 只能經合法 Stair Connection |
| **Search Limit Reached** | Deterministic termination |
| **Agent Ranking Conflict** | 同時保存 Graph 與 Agent Ranking |
| **Ground Truth Leakage** | Benchmark Invalid |

原 PRD 同樣要求 Impossible Transition 在 Agent 前被排除、Missing Data 不得當成 Observation，且 Blind Area 必須帶有明確 uncertainty。    PRD_v2

---

## 23. Local Storage 與 Preserved Interfaces

Phase 1 使用本機資料儲存即可，資料可放置於：

```
/scenes /cameras /topology /navmesh /ground_truth
/observations /events /candidates /metrics /configs
```

底層可使用 JSON、SQLite、CSV 或 NumPy，但上層 Interface 保留產品化抽象：

```
ObservationProvider → ProjectionService → TrajectoryGenerator
→ GapReasoner → EventRepository → VisualizationAdapter
```

未來可以直接將：

```
BlenderObservationProvider → RealCVObservationProvider
```

以及：

```
LocalEventRepository → PostgreSQLEventRepository
```

替換，而不修改 Graph / Event 的核心邏輯。

---

## 24. Phase 1 開發順序

Phase 1 的實作順序保持單一資料流：

```
Blender Scene → Ground Truth Trajectory → Virtual Camera
→ Visibility/Occlusion → Observation → 2D-to-3D Projection
→ NavMesh/Topology → Graph Candidate Generation
→ Blind-gap Reconstruction → Metrics → Rerun → Baseline/Ablation
```

**Agent Semantic Ranking 放在上述閉環完成之後再加入。**

---

## 25. Phase 2 Product Integration Backlog

Phase 2 恢復原產品架構中的 **Detection / Tracking、Tracklet Stitching、ReID、Appearance Retrieval、Natural-language Search、PostgreSQL、Vector DB、Object Storage、Backend API、Three.js Digital Twin、HTML5 Video Player、Soft Synchronization、Control-room UI、Operator Evaluation、Multi-target Events、Anomaly Detection、Automatic Reports 與 Advanced Agent Planning**。

這些模組目前只保留 **Interface 與資料 Schema**，不占用 Phase 1 的核心研發時間。

---

## 26. Research Prototype Success Definition

Phase 1 完成時，Blender 必須能產生具有完整 Ground Truth 的 3D Trajectory，Virtual Camera 能根據 FOV 與 Occlusion 產生部分 2D Observation，Projection Module 能將可見 Evidence 映射回 3D，而 Graph Engine 能在 Observed Segment 之間識別 Blind Gap 並產生符合空間與時間限制的 Top-K Candidate Trajectories。

整個閉環必須能將重建結果與隱藏的 Ground Truth 比較，輸出 **Projection Error、ADE、FDE、minADE@K、minFDE@K、Coverage@K 與 Physical Constraint Metrics**。最後透過 Baseline / Ablation 分離 **Shortest Path、Spatiotemporal Constraint、Semantic Information 與 Agent Reasoning** 各自帶來的實際增益。

---

## 27. 核心研究價值

PRD v3 最終可以濃縮成：

```
Known 3D Ground Truth → Partial Multi-camera 2D Observation
→ 2D-to-3D Projection → Blind-area Evidence Loss
→ Deterministic Spatiotemporal Constraints
→ Top-K Physically Feasible Trajectories
→ Optional Semantic Reasoning
→ Quantitative Ground-truth Evaluation
```

這一階段的目的，是先在完全可控制的 **Blender Digital Twin** 中確認盲區軌跡補全方法本身是否成立，再將 Real Camera、CV、ReID、Storage、Agent Tool Loop 與 Three.js Control-room 等產品模組逐步接回。原 PRD 所定義的完整產品鏈仍可作為 Phase 2 的整合方向。
