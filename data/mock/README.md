# Deterministic downstream fixtures / 確定性後半段測試資料

[繁體中文](#繁體中文) | [English](#english)

## 繁體中文

這四組資料只驗證後半段 interface，不代表 school WALKABLE／STAIR／WALL
語意或 Blender 幾何已通過驗證。固定 seed `20261001`；產生器不消耗隨機狀態。
每組 `inference.json` 是嚴格 `InferenceInput`，使用現有 Observation、navigation、
Camera Topology 與 movement/search schemas。`ground_truth.json` 另存，只供 evaluation
與 debug visualization；Graph 和 reconstruction 不載入它。

| Scenario | 路徑長度（m） | Gap（s） | 驗證用途 |
| --- | --- | --- | --- |
| Single Path | 20 | 20 | 唯一合法路徑、最低時間、direct reconstruction |
| Branching Top-K | 20、30、40 | 40 | 保留三條；GT 為第三條，不是距離第一名 |
| Temporal Slack | 20、40 | 180 | 最短時間 20s、slack 160s；slower/dwell/detour 多假設 |
| Simplified Stair | 7 | 7 | 1F→entry→parameterized stair→exit→2F；僅測 interface |

最大速度固定 `1 m/s`。GT 每秒取樣並保留所有 corner timestamps。Coverage@K 使用
`D=ADE`、epsilon `1e-6 m`，K 計算不同 route，不把 dwell timing alternatives 另算一條；
此設定只適用 regression fixtures，不固定正式 benchmark 的 distance／epsilon。
碰撞評估只支援顯式 AABB 幾何與連續線段；這些 fixtures 不提供 school mesh。
`constraints.json` 有一個不與合法路徑相交的 synthetic wall box；正向碰撞／constraint
違規的 numeric regression cases 另外放在 unit tests。Inference JSON 也保存 timing policy，
runner 會完整儲存 movement／search／reconstruction／evaluation／constraint configs。

在空目錄重新生成，JSON 可逐位元重現，已有檔案會拒絕覆寫：

```sh
uv run python scripts/generate_mock_scenarios.py --output /tmp/amidst-new-fixtures
```

## English

These four fixtures validate downstream interfaces only, with fixed seed `20261001`
and no random state consumption. They do not certify school semantics, walkability,
walls or stairs. Each `inference.json` is a strict producer-independent `InferenceInput`
using existing Observation/navigation/topology/search schemas. Separate
`ground_truth.json` files are restricted to evaluation and debug visualization.

The scenarios have a unique 20m/20s route, three 20/30/40m routes in 40s (truth is
rank three), a 20m shortest route plus 40m detour in a 180s gap, and a 7m/7s
parameterized stair interface. Maximum speed is 1m/s. Ground Truth includes the
1Hz grid and every corner. Synthetic Coverage@K uses ADE distance and epsilon
1e-6m; K counts distinct routes with their primary timing hypothesis. This is
not a formal benchmark choice. Collision checks use explicit AABB obstacles
and continuous segments, not a Blender mesh or clearance certification.
`constraints.json` includes one synthetic wall box clear of authorized routes;
positive collision/constraint examples live in unit tests. Timing policy is
serialized in inference input, and run metadata preserves every effective config.

Regenerate into an empty directory with the command above; existing files are
refused, and JSON bytes are reproducible. Blender-derived producers can replace
the input data without changing graph or reconstruction algorithms, provided
they satisfy the same contracts and explicit anchor/source bindings.
