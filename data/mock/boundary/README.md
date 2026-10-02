# Boundary fixtures / 邊界測試資料

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

本組只驗證錯誤、邊界、多解與搜尋停止，不新增一般正常情境。全部是小型、可讀、
deterministic `SYNTHETIC_TEST_FIXTURE`；不使用 Blender scene 或 Agent ranking。
Fixture recipes 由 test-only adapters 轉為現有正式 models，沒有 scenario-specific
production logic。每例明列 Input、candidates、termination、rejections、provenance、
metric behavior 與 success/failure state；沒有 GT 的 subgroup 明列 evaluation 不執行。

```sh
uv run pytest tests/boundary
```

| 類別 | Fixture / regression | Expected behavior |
| --- | --- | --- |
| 不可達／isolated endpoint | `graph_cases.json`; no-feasible suite | 0 candidates；`NO_FEASIBLE_PATH`；保留端點、不畫 inferred path |
| 不足時間／超速 | Graph temporal suite | Graph 先剪枝；`PHYSICALLY_IMPOSSIBLE_SPEED`；不靠 interpolation 製造可行路徑 |
| Reverse／duplicate／zero time | Graph temporal + observation suites | Schema／typed guard 拒絕；無 negative travel time |
| Top-K／完全等距 tie | Graph Top-K suite | 8 routes 截為 K=1／3，K=12 只得 8；距離、完整 edge IDs、transition identity 決勝 |
| Duplicate／亂序 observation | `observation_scenarios.json` | 重複拒絕；全部 120 permutations 的 aggregation／Events／IDs 相同 |
| 短 gap／相鄰 gaps | Observation gap suite | sampling threshold 採嚴格 `>`；1／2-frame recovery 保留，獨立 endpoints／binding |
| 20 min／1 hr gap／search explosion | Graph guardrail suite | 3 nodes／4 edges；node／length／branch／time／K bounds 有限停止 |
| Missing camera frames | Observation gap suite | absence 維持 absence；不虛構 frames、occlusion 或 out-of-FOV reason |
| Invalid projection | `guards_projection.json` | NaN／Infinity／bounds／depth／calibration／matrix／camera errors 在 Graph 前拒絕 |
| 非法樓層轉換 | Graph floor suite | 無 stair 不可直達；直接 WALK／ADJACENT teleport 拒絕 |
| Positive collision／clearance | `guards_collision.json` | continuous AABB 穿牆被標 violation；threshold 接觸算碰撞，ULP 邊界一致 |
| Termination | Graph termination suite | 六種既有 reasons 有最小 fixture；incomplete 搜尋保留已證明的 candidates |
| No GT／四種 poisoned GT | `benchmark_cases.json`; GT poisoning suite | GT absent 仍可推論；不同 path／速度／floor／座標只改 evaluation |
| Provenance forgery | `guards_provenance.json` | 非法 label、hidden GT fields、copy／construct bypass 拒絕 |
| Determinism stress | Benchmark stress suite | 三組 fixtures 各 4 次同 process、3 次新 process；hash／random seed、output/CWD 改變不改 semantics |
| Config boundaries | `guards_config.json` | 合法 K／極小正 epsilon 可用；0 epsilon、負值／非有限值／unsupported policies／版本不符／malformed JSON fail fast |
| Failure reporting | Benchmark failure suite | 空候選 metrics 回 null／false；NO_REFERENCE 明示；invalid case 保存 structured report 並重新拋原 exception |

範圍限制：

- 依 2026-10-02 使用者確認，**collision Top-K pruning 為 unresolved**；本輪只測
  evaluation-only fake AABB positive detector。正式 Graph 尚無 obstacle authority/input。
- epsilon=0 按現有 `epsilon > 0`／`D < epsilon` 契約拒絕。`metric_config_version`
  是 content identity label；拒絕版本不符／unsupported policies，沒有 version registry。
- 支援 `COMPLETE`、`NO_FEASIBLE_PATH`、`MAX_PATHS_REACHED`、`MAX_SEARCH_NODES`、
  `MAX_BRANCH_FACTOR`、`SEARCH_TIMEOUT`。`COMPLETE_EVENT`、`SEARCH_WINDOW_EXCEEDED`、
  `MAX_HOPS_EXCEEDED` 尚未定義；LOW_CONFIDENCE／TOOL_BUDGET_EXCEEDED／USER_TERMINATED
  留在 Agent/runtime scope，不硬造實作或新 Schema。
- 拒絕原因是現有 result-level `rejection_reasons`；沒有逐 transition rejection-log Schema。
  Impossible floor transition 由 navigation/topology guards 拒絕；沒有獨立
  `ImpossibleTransition` metric，不能把拒絕計數冒充已實作的 rate。
- Missing-frame absence 可測；明確 dropout marker 與觀測來源 attestation 尚無正式 Schema。
  完全重新貼標且移除原 GT fields 的座標不能僅靠 provenance label 識別來源。
- Timeout fixture 使用注入的固定 monotonic clock；operational wall-clock 超時切點可隨
  負載改變。Stress 比對完整 inference、metrics／JSON report semantics，排除 runtime、
  Git identity 與 RRD SDK metadata，不要求 binary byte identity。
- Mesh clearance、school WALKABLE／WALL／STAIR／OBSTACLE authority、真實樓梯／電梯
  連接與 geometry collision 必須等待 Blender semantic geometry 與相關契約核准。

## English

These tiny deterministic synthetic fixtures exercise boundaries, failures and retained
ambiguity. Every scenario declares input and expected candidates, termination, rejection,
provenance, metrics and state. Test adapters instantiate existing formal schemas; there
is no production special-casing, Blender asset edit or semantic ranking.

Coverage includes unreachable/speed/time/floor guards, isolated endpoints, 8-route Top-K,
equal-distance tie ordering, duplicate rejection, all 120 input permutations, short and
adjacent gaps, missing-frame absence, projection/provenance/config guards, positive AABB
collision and tolerance boundaries, all six current termination reasons, long-gap search
bounds, no truth, four poisoned-truth patterns and 21 benchmark determinism invocations
(nine separate processes). Metrics and Rerun consume only official output routes.

User-confirmed scope preserves formal schemas: collision remains evaluation-only and
Graph collision pruning is unresolved; zero epsilon fails validation. Version labels are
identities with consistency checks, not a registry. Missing-frame markers, coordinate-origin
attestation, per-transition rejection logs, the three unsupported termination names and
a separate ImpossibleTransition metric are not invented. Wall-clock runtimes and RRD
metadata are not semantic determinism promises. Actual school geometry remains future work.
