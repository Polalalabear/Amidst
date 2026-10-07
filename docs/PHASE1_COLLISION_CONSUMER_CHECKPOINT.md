# Collision consumer checkpoint / 碰撞 consumer 檢查點

Recorded 2026-10-08. Overall Phase 1 Exit remains **BLOCKED**.
記錄日期：2026-10-08。整體 Phase 1 Exit 仍為 **BLOCKED**。

## 繁體中文

歷史 V6 已完成 fresh export、inference、evaluation 與 reproduction；PASS 僅涵蓋
已準備好的 Case1 與 Case3 local run。Case2 branching scope 與 Case3 candidate-growth
stress scope 仍未獲批准，不能由這次 PASS 推導整體 Exit。

碰撞 adapter 使用原本 **25 個 APPROVED `KNOWN_COLLISION_PRUNING` scopes**，包含
**58 個非空、來源綁定的已批准 collider components**。每個原 scope 保持獨立，其 coverage
仍為 partial；此 consumer 不提供完整學校 free-space 或 physical-validity authority，
也沒有從物件名稱推導語意或新增批准。

A/B/C 使用同一個額外 collision filter。`remove_collision` 已可執行，只停用這個額外
filter；原完整 local domain/body guard 及獨立 physical evaluation 保留。GT、recipe 與
reference annotations 不進入 inference。V6 的 C 與 `remove_collision` 在 Case1、Case3
都各輸出一個 candidate，accuracy 沒有改變；本 checkpoint 不宣稱改善。

V3 lock 綁定精確原 V2 bytes 與既有 collision manifest。source、protocol、HR01–HR04
和原 29 個 locked inputs 保持不變。V6 evidence 保留於
[`reviewed_run_v6_collision`](../data/finalization/reviewed_run_v6_collision/)，
[reproduction receipt](../data/finalization/reviewed_run_v6_collision/reproduction/verification.json)
確認 repeat、fresh process、ordering、termination 與 GT/annotation poison checks PASS。

目前 V7 的 fresh export、inference、evaluation 與 reproduction 均已 PASS，涵蓋每次
操作一次建構的 consumer 與精確 frozen V3 lock artifact。實際 ablation table 有 45 rows：
30 EVALUATED、15 Case2 BLOCKED，另有 17 ablation charts。每個 ready case 的 C 與
`remove_collision` known-collision rate 都是 0/3 segments；filter enabled 分別為 true/false，
獨立 evaluator 都保留。V6 保持歷史版本，整體 Exit 仍為 false。

獨立乾淨 checkout 的 commit 為 `8cb0df3f2a530306e77e730f1a6395e824085e80`。
正確 fresh output `/private/tmp/amidst-collision-fresh-v7-8cb0df3` 的完整 delivery comparison
已從該 committed checkout 重新計算並 PASS：46 JSON、2 CSV、6 Markdown、37 個非 runtime
PNG、2 個附 reader 驗證記錄的 RRD。26 個 protected producers 在兩個 checkout byte-identical，
原 source `.blend` hash 保持不變。證據保存於
[v4 fresh receipt](../data/finalization/reviewed_checkpoint_v4/fresh_checkout_receipt.json) 與
[comparison](../data/finalization/reviewed_checkpoint_v4/fresh_delivery_comparison.json)，不含 raw bulk 或 RRD。

先前在該 checkout 成功抓取並 checkout 8cb0df3 之前產生的
`data/finalization/reviewed_run_v7_collision` 保留為未驗證歷史 raw，明確排除於本次 fresh proof。
本次 PASS 不涵蓋尚未 commit 的新 scope modules，也不授予 all-case Exit 或 freeze。

## English

Historical V6 completed fresh export, inference, evaluation and reproduction for ready
Case1 and Case3 local runs. This scoped PASS does not complete Phase 1: Case2 branching
authority and Case3 candidate-growth stress authority remain blocked.

The adapter consumes **25 original APPROVED `KNOWN_COLLISION_PRUNING` scopes** containing
**58 nonempty, source-bound approved collider components**. Each original scope remains
intact. Coverage remains partial; the consumer grants no complete school free-space or
physical-validity authority and introduces no new semantic approval.

A/B/C share the additional collision filter. Available `remove_collision` disables only
that filter; the original complete local domain/body guard and independent physical
evaluation remain active. Inference receives no GT, recipes or reference annotations.
V6 C and `remove_collision` each emitted one candidate in Case1 and Case3, with unchanged
accuracy. No measured improvement is claimed.

V3 preserves the exact V2 lock bytes and binds the existing collision manifest. Source,
protocol, HR01–HR04 and the original 29 locked inputs remain unchanged. V6 reproduction
passed repeat, fresh-process, ordering, termination and GT/annotation-poison checks.

Current V7 fresh export, inference, evaluation and reproduction all passed, including
operation-local consumer preparation and the exact frozen V3 lock artifact. Its actual
45-row ablation table contains 30 EVALUATED rows and 15 blocked Case2 rows, with 17 charts.
C and `remove_collision` each have a known-collision rate of 0/3 segments per ready case;
their filter is enabled/disabled respectively and both retain independent evaluation.
V6 remains historical evidence and overall Exit remains false.

The independent clean checkout is pinned to commit
`8cb0df3f2a530306e77e730f1a6395e824085e80`. Its verified output is
`/private/tmp/amidst-collision-fresh-v7-8cb0df3`. Recomputing the complete delivery comparison
from that committed checkout passed: 46 JSON, 2 CSV, 6 Markdown, 37 non-runtime PNGs and
2 RRDs with verified-reader receipts. All 26 protected producers are byte-identical across
checkouts; the pinned source `.blend` hash is unchanged. The small
[v4 checkpoint](../data/finalization/reviewed_checkpoint_v4/manifest.json) retains only the
fresh receipt, comparison and manifest.

The earlier `data/finalization/reviewed_run_v7_collision` export inside the fresh checkout
was produced before 8cb0df3 was successfully fetched and checked out. It remains unverified
historical raw and is excluded from this proof, even though the export manifest matches.
This PASS covers the committed collision checkpoint; it does not cover new uncommitted
scope modules or grant all-case Exit or freeze.

V7 dataset manifest file SHA-256 / V7 dataset manifest 檔案 SHA-256:
`a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5`.
V7 primary inference freeze file SHA-256 / V7 primary inference freeze 檔案 SHA-256:
`add7e6256c8e5d2ab834a00cb147f969bd0f091eb3ac62c34d6170461388c4de`.
V7 [reproduction receipt](../data/finalization/reviewed_run_v7_collision/reproduction/verification.json)
file SHA-256 / 檔案 SHA-256:
`30c882781afffdebcb85b26f5c7a84623939af484f89899317982daf9fef3bb9`.

## Frozen lock identifiers / 凍結 lock 識別

| File | File SHA-256 |
| --- | --- |
| [V3 collision lock](../configs/finalization/reviewed_case_inference_with_collision_v3.json) | `6f1924b3d2836d022004ad76aea0c32808332cbae5b45e93b6419aa01514966c` |
| [Preserved V2 lock](../configs/finalization/reviewed_case_inference_lock_v2.json) | `6507483100dda089341a317bd412946fecafedcfa4c4ac3a6b75d8b7171c8f24` |

Physical manifest file SHA-256 / physical manifest 檔案 SHA-256:
`5622d7ef1a986db34fb9f63baa4b70a3192befcedeebeb053550c470ec300d49`.
