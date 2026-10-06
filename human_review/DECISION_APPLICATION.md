# 決策套用與續作入口

這輪只準備，沒有套用任何 school APPROVE，沒有 formal Case 執行。

Dashboard 可匯出部分草稿；只有四項都完成、審查者非空、submitted_at 有 timezone，
application 才視為完成。JSON 只有四種 choices；APPROVE 必須選原 package 的 profile ID。
REJECT / FIX_GEOMETRY / KEEP_REVIEW 都保持 blocker，不會換成建議值或偷偷跳過。

下一輪只需將 dashboard 匯出的 `decisions.json` 放回本 package，或提供它的路徑，
並指示續作。唯讀驗證指令：

```sh
cd /private/tmp/amidst-phase1-finalization
uv run python human_review/apply_decisions.py \
  --decisions human_review/decisions.json \
  --source-asset /Users/polalabear/Developer/amidst/blender/school_v3.blend
```

完成且四項 APPROVE 後，下一輪套用到 fresh output：

```sh
uv run python human_review/apply_decisions.py \
  --decisions human_review/decisions.json \
  --source-asset /Users/polalabear/Developer/amidst/blender/school_v3.blend \
  --apply --output data/finalization/human_review_applied_v1
```

套用程序依序驗證 immutable review payload、blocked checkpoint ancestry、source .blend
hash、所有 public inputs 與每張 frame 的 hash；拒絕改 threshold / camera / face / body
bounds / profile payload。沒有讀取 evaluation、GT 或 simulation recipe。

輸出 `human_decisions.json`、`review_receipt.json`、`certificate_result.json`、
`approved_input_lock.json`、`resume_plan.json` 與 manifest。Output 必須不存在，不能覆寫舊
authority；原 `.blend`、原 protocol、原 physical atlas / 10 個 pinned producers 全部不變。

Geometry receipt 只綁定原 source / mesh / evidence hash、指定 body guard、
`group_0/component-00000000`、exact-zero-area faces 1975/2398。Additive certifier
先跑原 strict atlas/domain/policy 檢查，再對所有其餘 source surfaces 做既有完整 physical
proof；只允許本次明確核准的 bounded surface semantics。**APPROVE 不是 PASS**；
新的 source intersection、contact 或 envelope contradiction 保持 NOT_CERTIFIED。
取得 wrapper 後 downstream 必須使用 reviewed restricted provider，不能取出內部 certificate
繞過 semantic receipt / scope hash 檢查。`EXACT_DERIVED_SURFACE_REPAIR` 是精確衍生修復
授權；本 pipeline 的數值 certificate 仍使用原 atlas，沒有儲存或修改 `.blend`。

`approved_input_lock.json` 凍結已選研究值，但仍 `formal_execution_enabled=false`，
直到以下 automatic preflight 完成：bounded certificate、合法端點/可見性、Case1 unique
route、Case2 至少兩條真正可行且 distinct routes、Case3 protocol long-GAP stress
instance、正式 source-bound marker→footpoint/context/metric authority adapters。

目前 office direct/right 是 configured 平行 offset hypotheses，不能代替 branching proof；
10 秒 preview 中的 5 秒 GAP 不能代替 Case3 long-GAP。這些是後續 agent 的自動工作，
不請你自行計算或另準備資料。若必要合法 case scope 超出本次 bounded approval，
或 source geometry 出現真正矛盾，才會以新證據重開人工 gate；不以空間裁切假造 PASS。

[resume_plan.json](resume_plan.json) 保存十個續作階段：apply → certificates →
formal configs → fresh dataset → Cases1–3 → A/B/C → report/charts → Rerun → fresh
rerun → freeze。第 1–2 階段已有 executable entry；其餘依現有模組續作，部分 formal
adapter 與 case inventory 尚待實作。這不是目前已能一鍵完成 formal/freeze 的宣告。

只要 decisions 完成，下一輪可直接進入上述自動續作，不需第二輪人工資料整理。
只有 Phase1 全部 Exit Gate 通過後才能建立 freeze tag；本輪停止在 human gate。
