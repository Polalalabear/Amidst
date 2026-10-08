# Local simulation engineering / 本機模擬工程

`amidst.engineering` 是獨立的 **SYNTHETIC_ENGINEERING_ONLY** composition：實際 RGB
照片 → pixel measurements／camera-local tracks → provisional association → projection／
configured regions → canonical Graph/reconstruction snapshots → typed Agent tools。
工程入口不接真攝影機或外部模型，不做 semantic reranking。正式 Phase 1 仍另行驗收。

## 啟動與重現

在工程 checkout 使用既有 locked environment；本機 raw／完整 GT／snapshots／RRD／PNG
放在被 Git 排除的 `data/engineering/local_run/`。Build 選新的 output，不覆寫 frozen run。

```sh
uv run --offline --no-sync python -m amidst.engineering build \
  --config configs/engineering/simulation_v1.json \
  --output data/engineering/local_run/my_simulation_v1 --run-id my-simulation-v1
uv run --offline --no-sync python -m amidst.engineering serve \
  --run data/engineering/local_run/my_simulation_v1 --port 8010
uv run --offline --no-sync python -m amidst.engineering demo \
  --run data/engineering/local_run/my_simulation_v1
```

服務只綁 `127.0.0.1`。瀏覽 `http://127.0.0.1:8010`，依序按地點定位、鏡頭與照片、查事件，
選 CROSS_CAMERA_GAP 的有候選項目，再拖 replay 時間。UNMATCHED、INCOMPATIBLE、
overlap 和 same-camera HOLD 可逐項查細節；沒有 search 的項目 `complete=null`。
MEMORY／LOCAL_JSON 使用同一 canonical snapshot，可加 `--storage MEMORY`。
Serve/demo 不重新量測、關聯、projection 或 inference，不寫永久 IDs。

## 模型、照片與輸入模式

`synthetic-lab-v1` 是新建獨立 procedural engineering model，不是 school 子模型。
它使用明列 affine ground-plane cameras、metres／XYZ Z-up、configured synthetic seconds，
每鏡頭51張照片、兩個鏡頭、實際5Hz。圖片無 GT 身分、路徑或 bbox 標註。
Static coverage mapping 由 calibration 的 plane extent 與 region 相交計算，僅表示configured
partial plane coverage；不保證遮擋時可見，也不提供 school walkability authority。

既有58張圖片均已核對 bytes；50張5Hz圖是 diagnostic overlay，另外8張為代表／模型圖。
它們不是未標註 camera tracking sequence，不能拿 structured 5Hz records 假稱存在照片。
來源判斷見[既有媒體 audit](../../data/engineering/simulation_20261008/existing_media_audit.json)。

同一 run 的 `input_photos_only.json` 與 `input_photos_plus_observations.json` 使用相同102張
完整照片、任務、population 與 static context。完整圖片透過 opaque media refs 取回。
前者不帶 structured observation；後者加上真正 pixel producer 的bbox、contact pixel、
appearance、camera-local track refs、uncertainty／status與來源hash。量測缺失保留。
比較接收端為 `LOCAL_DETERMINISTIC_IMAGE_ASSOCIATION`，判斷階段為
`PIXEL_MEASUREMENT_THEN_PROVISIONAL_ASSOCIATION`。Photos-only 重新從RGB bytes量測，
不讀另一模式的stored measurements。比較分別記錄camera retrieval與observation inputs；
沒有 external model 品質或 token 效益宣稱。

Producer 是temporal median foreground components + nearest pixel history tracking；會漏檢、
合併、partial、fragment或local identity swap。它只解碼核對SHA後的RGB bytes；沒有GT、
object-index、depth、segmentation、recipe／reference annotation入口。
這仍是 SYNTHETIC，`image_measurement=true`／`measurement_source=RGB_PIXELS`另記producer
version／hash。舊UV／`image_measurement=false` records保持原語意。

## 關聯、幾何與 canonical records

Local IDs 使用model/run/camera namespace；pairwise association保留每個segment pair的
feasible／incompatible alternatives和UNMATCHED。它不是確認的global identity或ReID。
Overlap可見段不製造blind gap；same-camera recovery明確source-bound HOLD，沒有假handoff。
Hypothesis-scoped provisional target bindings只用作相容舊Graph／reconstructor，保存
original pixel／local segment／track → derived canonical observation/event映射。
原canonical endpoints、排序、nullable fields、候選與時間hypotheses均完整另存。

Projection與region membership由服務使用合法static calibration計算。Graph路線為凸形lab
中direct或一個configured waypoint的有限grammar；所有connector核對scope。`complete`
只表示該bounded search exhausted，與query成功、全場景exhaustive或formal研究無關。
窄時間查詢選重疊的完整records，不重新聚合／剪裁canonical endpoints。
Replay插值只改presentation，標記INFERRED_GAP，不改inference。

## Typed tools 與守門

每個服務session固定place/model/revision/source/context/run/clock/mode/registry。
Caller只提交 `session_ref` 和該工具typed參數；不能自行宣告mode/stage或permissions。
INPUT stage的photos-only只可resolve/list/media；plus另外准許pixel observations。INPUT拒絕region filter，避免以篩選結果推回尚未准許的區域答案。
RESULTS必須核對同run/mode的input/config/producer/model-registry/media及inference freeze。
Result server只掛已核對的frozen sessions；不混掛input session與其他mode的result sessions。

| Tool | 額外參數 | 結果 |
| --- | --- | --- |
| resolve_place | query | scope、已登錄地點／空結果 |
| list_cameras | 無 | camera refs、原IDs、configured／unknown coverage、media refs |
| query_observations | time_range、optional camera_ref／region_id | original canonical local segments與evidence |
| query_events | 同上 | 所有provisional association summaries／空結果 |
| get_event_summary | event_ref | scope、camera/time、evidence、counts、termination、complete、uncertainty、refs |
| get_event_detail | event_ref | original refs／canonical endpoint IDs、全部candidates／hypotheses |
| get_media | media_ref | hash核對完整PNG、camera/frame/time refs，base64本機transport |
| get_replay | event_ref、timestamp | 所有hypothesis markers、明列interpolation |

HTTP入口 `POST /agent/v1/{tool}`；`GET /agent/v1/contexts`／`contract`提供精簡context／request
與response schemas。Request及nested response均strict allowlist驗證。無repository/filesystem/SQL/shell tools；既有 `/v1/...` legacy development API
沒有掛入Agent app。所有正常、錯誤與logs只產生allowlisted資料／固定code；不回傳raw
validation內容、private paths、GT、secret或source archive。Photos-only pre-freeze的
summary/detail/query/replay／diagnostic media皆不能旁路露出已存答案。

Freeze核對實際media bytes、完整original frame refs與camera/time/hash對照、effective config、
static context、producer與algorithm hashes、registry、immutable snapshot、receipt與input
envelope hashes。服務read不需要GT；GT污染／刪除不能改推論或一般tool輸出。

## 既有 reviewed package 的獨立認證

新adapter與legacy COMPLETE `artifacts.json` importer分開。實際認證existing office recovery
的12 dataset／34 inference files、4校正鏡頭、193投影、4 observations／2 events。
Native BU records不回寫；校正顯式source Z offset後以 **0.0247 m/BU** normalization。
Certificate：**CERTIFIED_STRUCTURED_RECOVERY_PARTIAL_SCOPE**。
它不是RGB tracking、Agent DTO、new corridor union或full Case2／Case3認證。

```sh
uv run --offline --no-sync python -m amidst.engineering.importer \
  --run data/finalization/reviewed_run_recovery_20261008 \
  --source-scene /Users/polalabear/Developer/amidst/blender/school_v3.blend \
  --scale configs/architectural_scale_school_v3.json \
  --dataset-sha256 a3393f2ed29666b8aa1ea61263bb7c46f1d952b44bd89551863c7d24794f68a5 \
  --freeze-sha256 add7e6256c8e5d2ab834a00cb147f969bd0f091eb3ac62c34d6170461388c4de \
  --receipt /private/tmp/amidst-reviewed-import.json
```

Generic registry支援其他模型及derived fixtures，要求parent revision/hash、derivation hash、
可逆transform與camera/calibration correspondence。沒有新school照片序列或跨模型transform；
缺映射拒絕混用校正，subset不擴大authority。當前Agent photo loop僅接synthetic lab；reviewed
structured registry／snapshot由獨立adapter提供給內部developer，沒有直接暴露legacy身分。

## Independent evaluation 與展示匯出

```sh
uv run --offline --no-sync python -m amidst.engineering evaluate \
  --run data/engineering/local_run/my_simulation_v1
uv run --offline --no-sync python -m amidst.engineering export-demo \
  --run data/engineering/local_run/my_simulation_v1
uv run --offline --no-sync rerun \
  data/engineering/local_run/my_simulation_v1/presentation/inference.rrd
```

Evaluation核對freeze後才讀完整GT sidecar。Aggregate metrics另存evaluation/summary，
actor匹配細節只在local evaluation/debug；不排序或選關聯winner。主PNG／RRD只含frozen
pixel projection／所有inferred routes，無GT overlay。互動service仍是主要操作入口。
未量測的detection precision、association identity accuracy和formal指標維持N/A。

當次驗證、精度、失敗與reproduction receipts保存在
[curated工程證據](../../data/engineering/simulation_20261008/validation.json)。
本輪目前source的2351 tests全部PASS／0 failed／0 skipped，含required physical evidence；
Ruff與strict mypy138 source files PASS（只排除另一chat並行local research草稿）。36真HTTP
requests、4新canonical events／12個TypeScript replay samples、兩模式MockAgent及browser
3routes／6hypotheses操作通過。13個frozen JSON與102RGB在獨立fresh output逐byte一致。
Source inventory／config／run／freeze hashes一併綁定receipt，不沿用基底2255作本次PASS。

Independent evaluation：eligible contact recall83/129＝64.34%（24px一對一匹配）；
83樣本mean pixel contact error3.092px、mean ground error0.102m。28merged／partial
measurements、28NO_DETECTION frames與1OUTSIDE_STATIC_SCOPE projection保留。Association
identity precision／recall、detection precision與formal metrics未量測，均N/A。

Raw照片／GT／canonical local snapshots／RRD／PNG不進Git；不刪除既有素材。

## English

The local composition provides actual unannotated RGB sequences, pixel measurements/local
tracks, provisional association alternatives, configured ground projection/regions, canonical
Graph/reconstruction snapshots and eight typed Agent tools. Build performs inference; serve
and demo read frozen snapshots. The browser provides place/camera/time lookup, summary,
necessary full images/details and all-alternative replay. All runtime operations stay local.

Photos-only receives the full image index and recomputes pixels; plus receives the same images
and genuine producer measurements. Server-owned sessions bind modes/stages; frozen result
reads verify all input, source, clock, config, registry, media and algorithm bindings. GT and
recipes stay in simulation/export and independent evaluation/debug. Existing structured BU
records keep their meaning and bytes; reviewed import certification covers the office partial
scope only. The synthetic lab does not expand school, portal or walkability authority.

Commands and schemas above are reproducible from the locked environment. Publication keeps
only code, contracts and curated receipts. Formal Cases1–3, ablations, exhaustive inventory,
fresh frozen research dataset and clean-checkout research reproduction remain independent;
Case2／Case3 full gates BLOCKED, Case4 DEFERRED, original Phase2 FROZEN.
