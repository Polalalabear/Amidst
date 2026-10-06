# School v3 physical policy authority / 物理權威驗證

**Overall: PARTIAL_APPROVED.** This is source-geometry validation, not a formal
Case 1–3 benchmark. 原始 `school_v3.blend` 未縮放、修改、儲存或渲染；source
SHA-256、468,300,506 bytes 與 mtime 維持不變。

Source SHA-256: `cd46fa03f1875145a047e7e5f882aa97e7b2376de637677bf083bdc671e6e84e`.
Checkpoint `0bab8ac262b93f3c8babad69432744e7e4d1c541` 已驗證並推送；本輪位於
`phase1/physical-policy-approval`，不 merge、不開始正式 benchmark。

## Authority summary / 核准範圍

| Scope | Result | Limit |
| --- | --- | --- |
| Architectural scale | APPROVED: 0.0247 m/BU | 原始 BU 與 source geometry 保留 |
| Body/clearance policy | APPROVED | Config-driven；不替代 geometry evidence |
| Actual floor-supported WALKABLE | 48 supported subdomains APPROVED | 45 whole annotation coverage；3 partial，未支撐部分 REVIEW |
| Known obstacle components | 58 APPROVED across 5/19 OBSTACLE | 19 whole-obstacle volumes 全部 HUMAN_REVIEW |
| WALL classification | 73 HIGH_CONFIDENCE / 1,422 HUMAN_REVIEW / 77 REJECTED | 固定 threshold／doorway protection；沒有升級為正式 WALL collider |
| PORTAL conflicts | 8 HUMAN_REVIEW | Annotation width 不等於 actual aperture |
| Stair A/B | HUMAN_REVIEW | BIDIRECTIONAL 是政策；actual support/opening/body clearance 未批准 |
| Complete local physical islands | 0 APPROVED; 5 regions REVIEW | 不忽略未分類 source enclosure／退化 geometry 取得 PASS |
| Building complete physics | REVIEW | `physical_complete=false`；global purpose gates 拒絕正式認證 |

## Policy / 已核准政策

Upright cylinder：radius 0.30 m、height 1.70 m、body-obstacle extra clearance
0.05 m；portal 每側 extra 0.05 m、vertical extra 0.10 m；contact tolerance 0.001 m。
Foot-ground reference；minimum clearance equality PASS；obstacle contact collision；
APPROVED floor support contact allowed。Body/portal extras 取 maximum，不重複加總。
最小 portal width 0.70 m／height 1.80 m；navigation footprint radius 0.35 m。
數值與 BU 換算見 [body_clearance_policy.json](body_clearance_policy.json)。

Navigation 只允許 APPROVED WALKABLE／STAIR；WALKABLE 外禁止 navigation，但不
自動成為 WALL／occluder。同 floor compatible supports 先 union 再做 clearance；
exact containment／boundary distance 決定通過，buffer contours 只供顯示。
Point／continuous segment 直接比對 actual source support heights，避免 nominal-plane
與 footpoint 各加一次 contact tolerance。沒有 flatten source 或放寬研究門檻。

## Floors / 地板

| Floor | Actual source support Z (BU) | Z (m) |
| --- | --- | --- |
| 1F | 20.07884979248047 | 0.49594758987426757 |
| 2F | 161.81109619140625 | 3.9967340759277343 |

Floor difference：141.73224639892578 BU / 3.5007864860534665 m。
38 個舊 plane-offset diagnostics 已由 source support 解釋；另外 10 個舊 budget-limited
regions 找到可用支持證據。48 個 proxy 的原始 Z 偏移仍保留，沒有移動 annotation。
Main entrance 缺約 0.58043 m²、side entrance 約 0.19348 m²、2F office 約 0.28059 m²；
這些 uncovered 子域沒有批准。Local height variation 與其他高度來源保留，不強制壓平。
見 [floor_authority_map.json](floor_authority_map.json) 及
`floor_support_details.json.gz` 的完整 source-face evidence 依
[materialization contract](../../../docs/PHYSICAL_EVIDENCE_MATERIALIZATION.md) 重建。

一般 [scene validator](scene_validation.md) 仍保留原 annotation proxy 的 plane-offset
與其餘語意診斷（98 HIGH / 208 MEDIUM / 69 LOW）；不能把一般 proxy warning 當成
source floor 已被否決，也不能拿 source floor 批准消除其他 warning。

## Obstacle volumes / 障礙實體

| OBSTACLE | Approved exact source components |
| --- | --- |
| OBSTACLE_1F_CORRIDOR_01_01 | 6 |
| OBSTACLE_1F_CORRIDOR_01_02 | 4 |
| OBSTACLE_1F_RESTAURANT_01 | 14 |
| OBSTACLE_1F_RESTAURANT_02 | 16 |
| OBSTACLE_1F_STORAGE03 | 18 |

其餘 14 個 obstacle 沒有可批准的 components。APPROVED components 經完整 source
binding、actual footprint containment、closed two-manifold／winding／nonzero volume、
shared-feature／non-adjacent self-intersection、floor/body-envelope 檢查。
17 個 self-intersection positives 拒絕；2 個 self-intersection guard-budget 結果 REVIEW。
沒有 extrude footprint、用 hull／AABB 替代 collider、任意縮 obstacle 或猜來源名稱。
Movement/visibility ownership 僅由原 19 個 approved roles 與 exact source binding 承接。
見 [component authority](obstacle_collider_authority.json)；完整 parent indices 在
`obstacle_collider_details.json.gz`／`source_evidence.json.gz`，兩者依
[materialization contract](../../../docs/PHYSICAL_EVIDENCE_MATERIALIZATION.md) 重建。

## Eight portal pairs / 八組門洞衝突

| PORTAL | OBSTACLE | Result / evidence |
| --- | --- | --- |
| 1F LADYSROOM | 1F BATHROOM | REVIEW：未宣告 normal，actual aperture/height 未核准 |
| 1F MENSROOM | 1F BATHROOM | REVIEW：同上 |
| 2F LADYSROOM | 2F BATHROOM | REVIEW：同上 |
| 2F MENSROOM | 2F BATHROOM | REVIEW：同上 |
| 1F MAIN_ENTRANCE | MAIN_ENTRANCE_01 | REVIEW：annotation union leaves 1.63767 m；actual aperture 未證明 |
| 1F MAIN_ENTRANCE | MAIN_ENTRANCE_02 | REVIEW：同一 union gap，不將兩 obstacle 分別當無阻擋 |
| 2F MEETINGROOM_01 | 2F MEETINGROOM | REVIEW：annotation width 0.494 m < 0.70 m；actual binding 未證明 |
| 2F MEETINGROOM_02 | 2F MEETINGROOM | REVIEW：annotation width 2.47 m；actual aperture/body sweep 未證明 |

主入口 proxy plane 與來源 façade 約差 1.03 m，不能用 annotation width 宣稱門洞通過。
沒有自動移 portal、改 original mesh 或宣告真實通道被堵。每組 floor、bounds BU/m、
source object/face、location 和 screenshot-ready review 見
[portal_clearance.json](portal_clearance.json)。Actual clear width/height 未知時保留 null。

## Stairs / 樓梯

A：2,572 valid triangles、38 invalid faces、35 horizontal layers、576 inclined faces。
B：1,338 valid triangles、34 invalid faces、17 horizontal layers、208 inclined faces。
兩者皆未找到可用 intermediate landing，亦未證明 lower→landing→upper→exit chain。
2F slab underside 候選向上約 0.19449 m 即遇 source slab，不能把這個下表面當 landing；
這不是對整條樓梯 headroom 的測量結論。Opening 與 bidirectional cylinder sweep 仍 REVIEW。
[stair_authority.json](stair_authority.json) 保留 face witnesses／layer progression／理由。
「未找到完整支持證據」不等於斷言原場景完全沒有樓梯，也不授權補造 geometry。

## Local physical islands / 局部完整範圍

搜尋 corridor01、corridor02、1F office、2F class201、2F corridor03，對半邊長
2／1／0.5 m windows、每種最多 60 個 deterministic centers 嘗試 certification。
5 區都 REVIEW，不能批准完整 local physical island。搜尋有限，沒有宣稱已窮舉全場。

共同 blocker：`group_0 / component-00000000` 有 17,596 triangles、1,456 degenerates、
11,635 non-manifold edges；boundary-edge=0 不足以證明可用 closed solid。
其 solid interior／surface ownership 未知，不能忽略 enclosure risk。部分 windows 另有
`group_0.003`／`group_0` 的 actual body intersection 或退化 source triangles。
[local_physical_scopes.json](local_physical_scopes.json) 提供各區 object/face/location witnesses。
Provider 拒絕未註冊 certificate、hash/domain mismatch、scope 外位置及未知 floor transition。

## Pruning experiment / 碰撞拒絕原型

[collision_pruning_results.json](collision_pruning_results.json)：只使用 source-bound
APPROVED known-component scope，對 actual cabinet component 的幾何診斷 probes
做完整 cylinder sweep；4 probes → 2 retained，2 collision-contact positives hard reject，
IDs／scores／relative order 保留，多次結果一致，GT 未使用。

這是 isolated **positive component diagnostic**，不是 Observation/Graph 輸出的正式
candidate set；未認證 retained probes 的 WALKABLE/navigation 或 temporal feasibility。
完整 approved local island 為 0，因此正式局部/inference collision hard-pruning 未啟用；
Graph、ranking、Top-K、MetricConfig、benchmark semantics 和 GT isolation 均未修改。
Global collision-free／topology／physical-validity metrics gates 仍拒絕。
Cases 1–3 另外還需 camera-plane／formal research settings，不由此原型開放。

## Remaining review / 人工與幾何缺口

- 人工/source binding：確認 `group_0` 混合 component 中哪些 faces 為 surface、哪些有
  solid interior；不能把整個 object 直接猜成 WALL。可能需可追溯的 derived collider
  cleanup/binding，但本輪沒有修改場景或自行刪除退化／重複 geometry。
- 人工：八組 portal 的 actual opening/normal/ownership、meetingroom01 proxy 寬度
  與主入口 proxy plane；現有 source faces 已列出供定位。
- 幾何證據仍缺：三塊 uncovered support、A/B 連續 landing/run/opening/body-clearance
  chain、其餘 whole-obstacle usable volumes，以及 global collider completeness。
- WALL：73 HIGH_CONFIDENCE 僅 provisional evidence；不要求人工審全部 1,422 patches。
- 研究設定：formal camera-plane binding、Coverage/epsilon/K/sampling/baseline 等原未決
  選擇未由本輪改定。沒有 Agent、Case 4、benchmark 或 geometry fabrication。

## Replay / 重現

完整 local evidence 曾由 checkpoint
`c5956dc825f669e28e2694578be0fed97432a786` 產生並保存。
Lightweight branch 直接以 `0bab8ac262b93f3c8babad69432744e7e4d1c541` 為基底，
該 full-evidence commit 為 provenance reference，並非祖先。
原 [manifest.json](manifest.json) 保持原始內容；新增
[artifact_manifest.json](artifact_manifest.json) 為 raw artifacts 的 canonical
materialization contract，記錄 expected byte／content hashes、source/config/producer。
四份大型 gzip JSON 由精確 generated paths 忽略，不放入 Git。

從 repository root 明確重建並完整重跑 physical review：

```sh
uv run python -m amidst.materialize_physical_evidence \
  --blender /Applications/Blender.app/Contents/MacOS/Blender \
  --source-scene /absolute/path/to/checkout/blender/school_v3.blend
```

此命令在 temporary workspace 用固定 exporter／config 重建，安裝前核對所有 raw
artifact bytes 與 canonical hashes；tracked summary／原 manifest 不覆寫。
Source atlas 只在 temporary document 正規化非幾何 `source_mtime_ns` 為歷史值；
actual before／after fingerprint 另記 ignored receipt，source scene 不修改。
Full producer/source/config provenance 保留；SHA binding 不是簽章批准。

Full local evidence was produced and retained at `c5956dc825f669e28e2694578be0fed97432a786`.
The lightweight branch starts directly from `0bab8ac262b93f3c8babad69432744e7e4d1c541`;
that full-evidence commit remains a reference rather than an ancestor. The original manifest
is unchanged. The added artifact manifest validates regenerated raw bytes and canonical
content, with source/config/producer identity. Generated blobs are excluded from Git.
The explicit command above performs complete replay while preserving tracked summaries.
Only the temporary atlas's non-geometric source timestamp is normalized to its historical
value; the receipt retains actual before/after fingerprints without changing the scene.

Source prerequisites、verify-only／獨立 report replay、missing-evidence test profiles
與 collision runtime 比較邊界見
[完整雙語 workflow](../../../docs/PHYSICAL_EVIDENCE_MATERIALIZATION.md)。
