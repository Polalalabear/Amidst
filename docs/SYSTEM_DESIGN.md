## 1. Design Goal

本系統建立一條從 **監控影像、結構化 Observation、物理可行 Candidate Event、Agent 仲裁，到 3D Event Reconstruction** 的完整技術鏈路。整體設計的核心原則，是將不同性質的工作交由最適合的模組處理，使高頻、確定性與數值型運算不依賴 LLM，而 Agent 僅處理需要語意判斷、不確定性比較與 Event-level Reasoning 的部分。

在此架構中，**CV** 負責取得與追蹤人物 Evidence；**Tracklet Stitching** 修復單一 Camera 內因短暫遮擋或 Tracking Loss 所造成的追蹤斷裂；**Geometry** 將 2D Evidence 轉換至實際空間；**Spatiotemporal Graph Engine** 根據 Camera Topology、時間與移動條件建立物理上合理的 Candidate Trajectory；**Agent** 比較候選事件、處理 Evidence 衝突與不確定性；最後由 **Three.js Runtime 與 Global Timeline** 同步呈現 Camera Video、3D Trajectory 與 Provenance。

此責任分離避免讓 LLM 執行高頻影像處理、Geometry Calculation 或 Graph Traversal，同時使各模組具有明確且可獨立驗證的輸入與輸出。

---

## 2. Overall Architecture

整體架構分為五個主要 Layer，資料由左向右流動：

```
[ Video & Perception ]
Camera → Detection → Tracking → Tracklet
                │
                ▼
[ Observation Production ]
Stitching → ReID → Geometry → Observation
                │
                ▼
[ Spatiotemporal Graph ]
Retrieval → Constraints → Candidate Trajectories
                │
                ▼
[ Agent Arbitration ]
Compare Evidence → Inspect Ambiguity → Resolve → Event
                │
                ▼
[ Reconstruction & Presentation ]
Video + Global Timeline + Three.js + Provenance
```

系統同時存在兩條不同時間尺度的 Data Flow。

**Background Evidence Production** 持續執行，與管理員是否正在進行調查無關：

```
Camera → Detection → Tracking → Tracklet Stitching
       → Appearance / Geometry → Observation → Observation Store
```

**Investigation-time Reconstruction** 則只在 Operator 發起查詢時啟動：

```
Operator Query → Appearance Retrieval → Starting Observations
               → Spatiotemporal Graph Engine
               → Top-K Feasible Event Trajectories
               → Agent Arbitration → Event
               → Synchronized 3D Timeline
```

這樣可以讓大量影像處理與幾何計算在背景提前完成，避免每次事件查詢時重新分析原始 Video。

---

## 3. Core Data Abstraction

整體系統以五個核心資料概念組成：

```
Camera → Tracklet → Observation → Candidate Trajectory → Event
```

**Camera** 是固定的空間感測節點。**Tracklet** 代表 Tracker 在單一 Camera 中連續追蹤到的短時間人物片段。經過短時 Stitching、Appearance Processing 與 Spatial Projection 後，Tracklet 被整理為正式的 **Observation**，作為後續檢索與 Event Reconstruction 的 Evidence 單位。

Graph Engine 會將多個 Observation 根據時空與物理限制組合成一條或多條 **Candidate Trajectory**。Agent 再根據 Appearance、Evidence Quality、Continuity 與其他資訊進行仲裁，形成最終的 **Event**。

因此，Camera 是 **感測單位**，Observation 是 **Evidence 單位**，Candidate Trajectory 是 **演算法產生的事件候選路徑**，Event 則是最終的 **Investigation Unit**。

---

## 4. Video & Perception Layer

Camera Ingestion 負責取得 Video Stream，並維持 Camera ID、Timestamp 與 Frame Sampling 等基本資訊。所有 Camera 必須使用一致或至少可轉換的時間基準，使後續 Cross-Camera Association 能以相同 Timeline 進行比較。

CV Pipeline 的基本流程為：

```
Frame → Person Detection → Tracking → Tracklet
```

Tracker 產生的 Tracklet 不會立即被視為完整 Observation，而是先保留在短時間的 **Active Buffer** 中，等待是否需要與後續 Tracklet 重新串接。這樣可以降低因短暫 Detection Loss 所造成的不必要 Observation Fragmentation。

---

## 5. Intra-Camera Tracklet Stitching

在真實 Camera 畫面中，同一人物可能因 **Pillar Occlusion、Person Overlap、Temporary Detection Loss 或 Pose Change** 被 Tracker 分裂為多個 Tracklet。例如：

```
Tracklet A → Short Gap → Tracklet B
```

若這些 Tracklet 未經處理便直接送入 Graph Engine，同一人物在單一 Camera 中可能被錯誤視為多個不同事件節點，增加後續 Candidate Path 數量並造成錯誤的停留或重新進入判斷。

因此，正式產生 Observation 前需先進行 **Intra-Camera Tracklet Stitching**。合併判斷可綜合 Appearance、Position、Velocity、Direction 與 Time：

w_aS_{\text{appearance}}

+

w_pS_{\text{position}}

+

w_vS_{\text{velocity}}

+

w_dS_{\text{direction}}

+

w_tS_{\text{time}}

]

當兩個 Tracklet 在時間、位置、移動方向與人物外觀上皆具有足夠一致性時，可被合併為同一 Observation。**Stitching Window、Maximum Spatial Gap、Appearance Threshold 與 Direction Threshold** 均屬於 Prototype Parameter，後續應由 Dataset 與 Benchmark 校準。

Observation 需額外保存 `stitching_count`、`fragment_count` 與 `observation_quality`。若某 Camera 中的 Observation 經常需要多次 Stitching，可將其 Tracking Quality 降低，使後續 Agent 與 Ranking 能理解該段 Evidence 的可靠程度。

---

## 6. Observation Schema

Observation 是整個系統最主要的 Evidence 資料結構，其概念 Schema 為：

```
Observation
├── observation_id
├── camera_id
├── floor_id
├── zone_id
├── start_time / end_time
├── track_ids[]
├── stitching_count / fragment_count
├── appearance_embedding / appearance_labels
├── appearance_quality
├── entry_direction / exit_direction
├── projected_path
├── projection_quality
├── occlusion_quality
├── tracking_quality
├── observation_quality
└── source_video_reference
```

完整 Embedding、逐幀 Position 與高頻 Coordinate 保留在底層 Storage。Agent 僅取得經摘要後的 Observation Information，以降低 Context Size 與不必要的 Token 使用。

---

## 7. Camera Graph

Camera Topology 以 Graph 表示，其中 **Camera 為 Node，Camera 之間可能的移動關係為 Edge**。

Node 至少包含 `Camera ID、Floor、Zone、Position、FOV`。Edge 則包含 `From Camera、To Camera、Transition Type、Minimum Travel Time、Expected Travel Time、Direction Constraint、Walkable Path Reference`。

主要 Transition Type 包括：

- `ADJACENT`
- `OVERLAPPING_FOV`
- `SAME_ZONE`
- `STAIR_UP`
- `STAIR_DOWN`
- `RETURN_TRIP`

其中 `RETURN_TRIP` 並非固定的 Camera Topology Edge，而是 Event Path 中的 Transition Attribute，表示人物在合理時間與物理條件下重新回到先前出現過的 Camera。

---

## 8. Spatiotemporal Graph Engine

Graph Engine 從一個或多個 Starting Observation 出發，根據 Camera Topology 與 Observation Data 建立完整的 **Candidate Event Trajectory**。

它負責處理 Reachability、Minimum Travel Time、Time Constraint、Direction Constraint、Observation Matching、Duplicate Prevention、Return-trip Handling、Candidate Branch Pruning、Search-depth Control 與 Gap Analysis。

其核心目標不是只回答「下一個 Camera 是哪一台」，而是直接產生：

**Top-K Physically Feasible Event Trajectories**

概念上：

```
Starting Observation
        → Physical / Temporal Constraints
        → Candidate Observation Graph
        → Path Pruning
        → Top-K Candidate Event Trajectories
```

底層可依 Graph 規模與 Prototype 結果選擇 *Constrained BFS、Dijkstra、A、K-Shortest Paths 或 Precomputed Reachability**。System Design 不固定單一演算法，最終選擇以正確性、Search Latency 與實作複雜度為準。

---

## 9. Anti-Cycle and Return-trip Strategy

搜尋防重複的主要 Identity 採用：

```
observation_id
```

同一個 Observation 不得在相同 Candidate Path 中重複使用，但同一 Camera 可以在不同時間重新出現。

例如：

```
Cam A / Obs 01 → Cam B / Obs 09 → Cam A / Obs 23
```

若兩段 Transition 都符合 Travel Time、Direction 與其他 Physical Constraint，則第二次進入 Cam A 是合法事件，並可標記為：

```
transition_type = RETURN_TRIP
```

因此系統不使用固定 `Max Revisit = 2` 作為事件語意規則。搜尋複雜度應由 **max_search_hops、max_event_duration、max_candidate_paths、max_branch_factor 與 path_score_pruning** 等演算法參數控制。

---

## 10. Candidate Trajectory Generation

Graph Engine 對 Agent 暴露的主要高階工具為：

```
propose_feasible_trajectories(
    start_observation_id,
    time_range,
    max_paths,
    constraints
)
```

輸出 Candidate Trajectory 時需保留完整 Path 結構，但 Agent 所取得的內容以摘要為主：

```
CandidateTrajectory
├── path_id
├── observations[]
├── transitions[]
├── camera_sequence[]
├── appearance_summary
├── continuity_summary
├── quality_summary
├── inferred_gaps[]
├── path_score
└── warning_metadata
```

Graph Engine 應完成大部分 **物理、時間與 Graph 結構剪枝**，再將少量 Candidate Path 交給 Agent，避免 Agent 逐 Camera 執行低效率的 Traversal。

---

## 11. Agent Arbitration Layer

Agent 的角色定位為 **Event Arbitration Agent**。其主要工作是理解查詢語意與處理 Graph Engine 無法單純透過物理條件解決的不確定性。

主要流程為：

```
Search Intent → Starting Observations → Candidate Trajectories
              → Evidence Comparison
              → Ambiguous Node Inspection
              → Select / Preserve Candidate Paths
              → Event
```

Agent 可處理相似人物衝突、Appearance Quality 差異、Occlusion Evidence、Multiple Candidate Paths、Ambiguous Gap 與 Event Explanation。如果 Candidate Path 中某個 Observation 的可信度不足，Agent 可再要求該 Observation 的細節，而不需要重新遍歷整張 Camera Graph。

---

## 12. Supporting Agent Tools

Agent 主要使用四類工具：

- **`search_person_appearance(...)`**：取得符合 Search Condition 的 Starting Observation。
- **`propose_feasible_trajectories(...)`**：取得 Graph Engine 已經剪枝後的主要 Cross-Camera Candidate Path。
- **`get_observation_detail(...)`**：只在模糊節點需要更多 Evidence 時調用。
- **`query_reachable_cameras(...)` / `verify_spatiotemporal_plausibility(...)`**：作為局部調查、Debug 或特殊事件驗證工具。

因此，`propose_feasible_trajectories()` 是正常事件調查的主要 Graph Tool，而其他工具主要作為 Supporting Tools。

---

## 13. Camera Calibration and Geometry

MVP 採用 **piecewise planar assumption**。1F 與 2F 分別建立 Ground Plane Calibration，使 Camera 中的 2D Position 能轉換至統一 World Coordinate。

人物 Bounding Box 底部中心：

[

(u_b,v_b)

]

作為初始 **Ground Contact Estimate**。其轉換方式可使用 Homography、Camera Projection Matrix 或 Ray-plane Intersection，最終方法以 Calibration Accuracy 與 Prototype Complexity 為判斷依據。

投影結果至少應保存：

```
world_position
projection_quality
```

由於 Ground Contact Estimate 可能受到 Occlusion、Bounding Box Noise、Perspective 與 Detection Drift 影響，因此 Projection Result 必須包含 Quality，而不能視為完全精確的 Ground Truth。

---

## 14. Stair Representation

樓梯不使用與一般水平 Ground Plane 完全相同的 Mapping。MVP 以預先定義的 **Parameterized Stair Path** 表達樓層之間的 Connection：

```
Stair Entry → Parameterized Stair Path → Stair Exit
```

這條路徑主要提供 **Graph Connectivity、Travel Time Estimation 與 3D Visualization**。因此在 MVP 中，樓梯首先被視為一個具有高度變化的已知 Transition，而非要求對整段樓梯進行完整自由形式 3D Reconstruction。

---

## 15. Trajectory Smoothing

Projected Path 可能因 Detection 或 Ground Contact Estimate 產生抖動，因此可加入 Temporal Smoothing。候選方法包括 **Kalman Filter、Exponential Smoothing 或 Tracker-native Filtering**。

具體方法不屬於固定 Requirement，應透過 Projection Error、Trajectory Stability 與 Runtime Cost Benchmark 決定。

---

## 16. Inferred Gap

當事件存在 Camera Coverage Gap 時：

```
Observed A → Unknown Area → Observed B
```

Graph 與 Geometry Layer 可利用 Walkable Geometry、NavMesh、Travel Time 與 Direction 建立一條或多條 **Feasible Route**。

若存在多條合理路徑，Event 可保存：

```
Primary Inferred Path
Alternative Paths
Path Confidence
```

NavMesh 所產生的 Shortest Route 僅代表一條 **物理上合理的可能路徑**，不可被視為人物實際行走的 Ground Truth。

---

## 17. Playback Synchronization

Prototype 階段採用 **Soft Synchronization**。Video Presentation Time 作為主要 Playback Reference，3D Scene 依照相同 Global Event Time 更新：

```
Video Presentation Time → Master Playback Clock
                        → Global Event Time
                        → 3D Trajectory Interpolation
                        → Three.js Rendering
```

Web Runtime 優先使用 `HTMLVideoElement.requestVideoFrameCallback()` 取得接近實際呈現 Video Frame 的 Media Time。

使用者 Seek Timeline 時，系統先暫停 3D Trajectory Advancement，在 Video 完成 Seek 並取得可用 Frame 後重新計算 Global Event Time，再更新 3D Marker 並恢復 Playback。真正的 Camera Hard Synchronization 則保留至後續真實部署。

---

## 18. Synchronization Benchmark

Prototype 應量測 **Average Sync Error、p95 Sync Error、Seek Recovery Time 與 Dropped Video Frames**。

可先使用：

```
Prototype Sync Error Target ≤ ±250 ms
```

作為初始實驗目標，但此值需透過實際測試驗證，不能直接視為正式系統保證。

Prototype UI 或測試報告中應清楚標註：

**Prototype uses soft synchronization rather than frame-locked synchronization.**

---

## 19. Three.js Runtime

Three.js 是 **Presentation Runtime**，主要負責 Digital Twin Rendering、Camera Node、Trajectory、Marker Animation、FOV、Provenance 與 Timeline-linked Playback。

Camera Calibration、World Coordinate Calculation 與其他 Geometry Logic 應保留於獨立 Geometry Layer，使 3D Rendering Engine 不成為系統中的 Spatial Ground Truth。

Blender 則作為 Offline Asset Preparation Tool：

```
Blender Asset
(Building + Camera Transform + Walkable Geometry)
        → Export
        → Three.js Runtime
```

---

## 20. Rendering Performance

系統將以下三個 FPS 概念明確分開：

```
Recorded Video FPS | CV Inference FPS | 3D Rendering FPS
```

Prototype 初始測試資料設定為 **1920 × 1080、15 fps、30-minute Window**。3D Rendering 則可分別測試 24 fps、30 fps 與 60 fps，最後依 Target Hardware 選擇穩定方案。

為降低 Rendering Cost，可依需要關閉或簡化 Dynamic Shadows、Post-processing、High-cost Materials 與不必要 Geometry。Performance Optimization 的目標應是維持穩定的 Video Playback 與 Operator Interaction，而非追求特定 FPS 數字。

---

## 21. Runtime Performance Metrics

Development 與 Benchmark Mode 應至少收集：

- **Average UI FPS / p95 Frame Time**
- **Dropped Video Frames**
- **Draw Calls / Triangles / Textures**
- **Active Video Count**
- **Memory Usage**

系統不預先固定 `Draw Calls < 50` 等跨環境門檻，而應在標準測試 Scene 與 Target Hardware 上建立可比較的 Benchmark Baseline。

---

## 22. CV Sampling Strategy

**Recorded Video FPS** 與 **CV Inference FPS** 採獨立設定。Prototype Video 可維持 15 fps / 1080p，而 Detection 與 ReID 可先測試較低的 Sample Rate，例如 3–5 fps。

這類降頻屬於 Performance Optimization，必須同時觀察 Person Recall、Tracking Quality 與 ReID Availability。Skipped Frame 中的人物位置可透過 Tracking Prediction 或 Interpolation 改善視覺軌跡，但未實際執行 Appearance Analysis 的 Frame 不可被標記為 Observed Appearance Evidence。

---

## 23. Detector and ReID Processing

候選影像處理流程為：

```
1080p Source → Resize for Detection → Person Bounding Box
             → High-quality Person Crop → ReID Feature
```

Detector Input Resolution 為可調整參數，不固定為特定尺寸。

ReID 也不需要對每個 Frame 重複執行。系統可以從每個 Observation 中選取若干品質較高的 Person Crop，建立代表性的 Appearance Feature，使資料庫保留更有價值的視覺證據，而不是大量相似或低品質 Embedding。

---

## 24. Feature Quality Gating

Appearance Feature 需附帶 Quality Metadata。Quality 可以由 **Occlusion、Blur、Lighting、Pose、Tracking Stability 與 Crop Resolution** 綜合估計。

低品質 Feature 仍可被保存，但其在 Retrieval、Candidate Ranking 或 Agent Arbitration 中的 Weight 應降低，以避免被遮擋或模糊的 Evidence 對人物關聯造成過度影響。

---

## 25. Global Timeline

整個 Event Replay 使用單一：

```
Global Event Time
```

控制 Video Frame、3D Marker、Camera Activation、Trajectory Segment 與 Provenance State。

因此 Operator 在拖動 Timeline、切換 Camera 或改變播放速度時，Camera Video 與 3D Scene 仍基於同一事件時間進行更新。

---

## 26. Provenance

所有 Event Data 必須保留來源類型：

- **OBSERVED**：直接來自 Camera Evidence。
- **PROJECTED**：Observed Evidence 經 Geometry Mapping 所得到的 3D Result。
- **INFERRED_GAP**：Camera 無法直接觀測時，由時空與 Walkable Constraint 建立的可能路徑。

三種類型在 UI 上必須具備明確可辨識差異，避免 Operator 將 Inference 視為原始 Evidence。

---

## 27. Logging

系統 Logging 分為三層。

**Agent Log** 保存 Agent 收到哪些 Candidate Path、額外要求哪些 Observation Detail、如何處理 Alternative Path，以及最終的 Arbitration 與 Termination Reason。

**Graph Intervention Log** 保存被 Graph Engine 接受或排除的 Transition Evidence，例如 `from_observation、to_observation、actual_time_delta、minimum_required_time、direction、decision、reason_code`。

**System Log** 則保存 Camera、CV、Tracking、Calibration、Database、Playback Synchronization 與 Runtime Error 等系統狀態。

這樣可以將「Agent 判斷」、「Graph Algorithm 判斷」與「Infrastructure Error」分離，提升 Debugging 與 Benchmark 可解釋性。

---

## 28. Search Termination

Event Search 必須具備 deterministic termination condition。主要狀態包括：

```
COMPLETE_EVENT
NO_FEASIBLE_PATH
LOW_CONFIDENCE
SEARCH_WINDOW_EXCEEDED
MAX_HOPS_EXCEEDED
MAX_PATHS_REACHED
TOOL_BUDGET_EXCEEDED
USER_TERMINATED
```

Termination Reason 會被保存在 Event Result 中，使系統能說明事件為何停止繼續延伸。

---

## 29. Token and Context Control

Agent 只需要接收 **Search Intent、Starting Observation Summary、Top-K Candidate Trajectory Summary、必要的 Ambiguous Observation Detail 與 Current Decision State**。

Raw Embedding、Full Camera Graph、Full NavMesh、Every-frame Coordinate 與完整 Video Metadata 不直接送入 Agent Context。

因此 LLM 處理的是經過壓縮的 **Event Evidence**，而非底層高頻 Sensor Data。

---

## 30. Storage and Observation Benchmark

MVP 不預先限制固定的 Observation 數量或 Vector Database Size，例如 `100–300 Observations / camera` 或 `<50 MB`。

實際測試應量測：

- **Observations / minute / camera**
- **Tracklets / Observation**
- **Embeddings / Observation**
- **Storage / hour / camera**
- **Vector Index Size**
- **Retrieval Latency**

再根據實際數據決定是否需要額外 Aggregation、Compression 或 Retention Policy。

---

## 31. Cache Strategy

快取策略維持簡單且以實際 Bottleneck 為依據。

**Topology Cache** 長期保存 Adjacency、Transition Time、Reachability 與 Walkable Path，只有空間配置或 Camera Topology 發生變化時才更新。

**Retrieval Cache** 只有在 Profiling 顯示 Vector Retrieval 成為主要 Bottleneck 時加入。

**Prompt Cache** 則使用 Model Provider 所支援的原生 Prompt Caching 機制。MVP 不建立 Agent Decision Semantic Cache，避免過去的 Agent Judgment 汙染新的 Event。

---

## 32. Benchmark Structure

Benchmark 分成四個主要面向：

- **Accuracy**：Detection Recall、Tracking Quality、Tracklet Stitching Accuracy、ReID Retrieval Accuracy、Cross-Camera Association Accuracy、Event Reconstruction Accuracy。
- **Latency**：Appearance Retrieval、Graph Trajectory Generation、Agent Arbitration、Total Investigation Search。
- **Runtime**：UI FPS、Dropped Video Frames、Sync Error、Memory Usage、CV Throughput。
- **Operator Evaluation**：Investigation Time、Camera Views Inspected、Operator Corrections、Successful Event Understanding。

這些指標共同用於判斷系統是否真正降低 Operator 調查成本，而非只提升單一模型的 Accuracy。

---

## 33. Baseline Comparison

Prototype 至少建立四組 Baseline：

| **Baseline** | **功能範圍** | **主要用途** |
| --- | --- | --- |
| **Manual** | Operator 手動查看 Camera | 建立傳統調查基準 |
| **Retrieval-only** | Appearance Retrieval | 評估人物搜尋本身的價值 |
| **Graph-only** | Retrieval + Deterministic Graph Path | 評估 Camera Topology 與 Graph Engine 的增益 |
| **Agent + Graph** | 完整系統 | 評估 Agent Arbitration 是否額外改善 Event Understanding |

此比較可以分離觀察 **CV / Retrieval、Graph Engine 與 Agent** 各自真正帶來的效益。

---

## 34. Prototype Priority

### P0

P0 聚焦完整事件鏈路能否成功運作：

```
Camera Topology | Detection / Tracking | Tracklet Stitching
Observation Schema | Appearance Retrieval
Graph Candidate Trajectory Generation | Agent Arbitration
2D → 3D Projection | Soft Video / 3D Synchronization
Timeline Playback
```

### P1

P1 主要提升事件重建的可視性與展示能力：

```
NavMesh Gap Visualization | Event Video Export
Advanced Occlusion Quality | Alternative Path Visualization
Performance Dashboard
```

### Future

後續再加入：

```
Hard Camera Synchronization | Natural Language Search
Multi-target Events | Anomaly Detection
Automatic Event Report | Advanced Agent Planning
```

---

## 35. Core Architecture Summary

整體系統最終可濃縮為一條由左至右的 Evidence Processing Chain：

```
Physical Space
      → Cameras
      → Detection / Tracking
      → Tracklet Stitching
      → Observation
      → Spatiotemporal Graph Engine
      → Candidate Event Trajectories
      → Agent Arbitration
      → Event
      → Synchronized 3D Digital Twin
      → Control-room Operator
```

其中，**CV 負責取得人物 Evidence；Tracklet Stitching 修復局部追蹤斷裂；Geometry 將 Evidence 放入真實空間；Graph Engine 建立物理可行的完整 Candidate Event Path；Agent 處理 Candidate 之間的語意衝突與不確定性；Three.js 與 Global Timeline 則負責將 Event 同步呈現給 Operator。**

這樣的責任分離使每一層都能被獨立測試、替換與優化，同時保留完整的 Evidence Provenance 與系統可解釋性。