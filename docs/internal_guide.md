# Internal Project Guide / 內部專案導讀

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Audience: Amidst project contributors and reviewers

Repository classification: `PUBLIC_ALLOWED`

### Purpose

This guide explains how the team navigates project decisions, reviews
information, and moves a change from an idea to an accepted repository update.
It is an internal-facing orientation document, not a new source of truth.

Do not place secrets, private links, sensitive site details, personal data, or
other `PRIVATE_ONLY` information in this file. Store sensitive internal material
only in an explicitly approved private location.

### Start Here

Use this sequence for project work:

```text
Task
  -> Project Map
  -> Relevant specification(s)
  -> Glossary and Open Questions when needed
  -> Pre-change review
  -> Smallest viable change
  -> Local validation
  -> Publication review when requested
```

The default responsible person is Peter unless another human owner is
explicitly assigned. Default ownership does not grant reviewer or approver
authority and does not resolve an open decision.

### Sources of Truth

| Concern | Authoritative document | Use this guide for |
| --- | --- | --- |
| Current phase, blockers, and document ownership | [Project Map](00_Project_Map.md) | Finding the right starting point |
| Product need, users, MVP, and scope | [PRD](01_PRD.md) | Understanding when product confirmation is needed |
| Components, boundaries, and data flow | [System Architecture](02_System_Architecture.md) | Identifying affected modules |
| Correctness, metrics, and failure attribution | [Evaluation Framework](03_Evaluation_Framework.md) | Identifying evaluation review needs |
| Dataset and annotation design | [Dataset Specification](04_Dataset_Specification.md) | Identifying data and Ground Truth review needs |
| Cameras, zones, and spatial mapping | [Spatial Model Specification](05_Spatial_Model_Specification.md) | Identifying spatial review needs |
| Queries, evidence, and provenance | [Retrieval Specification](06_Retrieval_Specification.md) | Identifying Retrieval and Agent boundaries |
| Technical choices and their rationale | [Technical Decision Register](07_Technical_Decisions.md) | Following the ADR workflow |
| Repository/publication classification | [Repository and Data Publication Policy](08_Repository_and_Data_Publication_Policy.md) | Applying the review checkpoint |
| Candidate cross-layer data contracts | [Data Types and Exchange Formats](09_Data_Types_and_Exchange_Formats.md) | Comparing Blender, video, event, and provenance formats before confirmation |
| Shared terminology | [Glossary](glossary.md) | Resolving terminology before editing |
| Cross-document unresolved decisions | [Open Questions](open_questions.md) | Escalating and tracking unresolved issues |
| Mandatory operating rules | [AGENTS.md](../AGENTS.md) | Understanding the required execution boundary |

If this guide conflicts with an authoritative document, stop and report the
conflict. Do not silently choose one.

### Decision Status

| Status | Meaning | Who may apply it |
| --- | --- | --- |
| `OPEN` | A decision or required evidence is missing | Contributor or reviewer identifying the gap |
| `PROPOSED` | A candidate direction is ready for review | Contributor preparing a supported recommendation |
| `CONFIRMED` | A human explicitly approved the decision or a fact was verified | Authorized human decision-maker |
| `DEFERRED` | The team intentionally postponed the decision | Authorized human decision-maker |
| `REJECTED` | The team explicitly rejected an option and recorded why | Authorized human decision-maker |

Codex may analyze, compare, recommend, and implement confirmed decisions. It
must not independently promote `OPEN` or `PROPOSED` items to `CONFIRMED`.

### Decision Routing

#### Local issue

Keep an unresolved item in its owning specification when it affects only one
document or module. Mark it `TODO` or `OPEN`.

#### Cross-cutting issue

Register the issue in [open_questions.md](open_questions.md) when it affects
multiple documents, architecture, MVP scope, evaluation, dataset policy, or
project-wide behavior. Reference the existing `OQ-xxx` ID instead of copying
the discussion into several documents.

#### Technical trade-off

Use an ADR in [07_Technical_Decisions.md](07_Technical_Decisions.md) when a
material technical choice needs context, alternatives, consequences,
verification evidence, and a revisit condition.

#### Decision lifecycle

```text
OPEN question
  -> Evidence and affected scope identified
  -> PROPOSED answer or ADR
  -> Human review
  -> CONFIRMED / DEFERRED / REJECTED
  -> Directly affected documents updated
  -> Validation run and result recorded
```

### Pre-change Review

Before editing, record:

| Field | Required content |
| --- | --- |
| Requirement | The confirmed outcome requested |
| Impact Scope | Files, modules, schemas, data, and consumers affected |
| Short Plan | The smallest ordered set of changes |
| Acceptance Criteria | Observable conditions that prove completion |
| Failure Cases | Conditions that require stopping or reporting |

Read the relevant specification before completing this record. Do not use the
record to turn an assumption into a decision.

### Information Review Mechanisms

#### Repository file classification

Classify every file before adding it to Git:

- `PUBLIC_ALLOWED`: suitable for the public repository after normal checks;
- `PRIVATE_ONLY`: must not be added to the public repository;
- `REVIEW_REQUIRED`: do not add or publish until a human approves it.

The complete criteria and publication checklist belong to
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md).

#### Review-required information

| Information or change | Review needed before proceeding |
| --- | --- |
| Product, architecture, evaluation, dataset, privacy, or technology decision | Explicit human confirmation |
| Non-source data, media, model, experiment, or spatial artifact | Semantic content classification and, when applicable, publication approval |
| New external service receiving project/private data | Explicit approval before data leaves the local environment |
| Shared schema change | Downstream-consumer and compatibility review |
| Ground Truth correction | Explicit reason, provenance, and separation from model/system changes |
| Benchmark or metric protocol change | Documented rationale and qualified before/after comparison |
| Major dependency or framework | Need, no-dependency option, alternatives, maintenance, and compatibility review |
| Destructive data/schema migration | Explicit approval and recovery/versioning plan |

#### Provenance review

Keep observed data, annotated Ground Truth, model prediction, deterministic
derived state, inferred state, synthetic/generated data, and human-confirmed
data distinguishable. Never relabel generated or inferred information as direct
observation.

### Change Workflow

1. Confirm the repository and working-tree state.
2. Read the Project Map and directly relevant specifications.
3. Check the Glossary and Open Questions when terminology or unresolved scope
   affects the task.
4. Prepare the pre-change review record.
5. Create and switch to a task-specific branch; never edit `main` directly.
6. Make the smallest viable change and preserve unrelated work.
7. After every complete step, run:

   ```bash
   python3 -B scripts/check.py
   ```

8. Report exact failures; do not weaken tests or hide errors with fake success.
9. Commit only files directly related to the task.

### Cross-Platform Continuation

Use [10_Cross_Platform_Setup_and_Testing.md](10_Cross_Platform_Setup_and_Testing.md)
for the platform-specific executable commands, formal test suite, and Blender
runtime lock. This section owns the workflow boundary rather than duplicating
those commands.

For a repository or Blender task that moves to another operating system:

1. Stop writers and record the last complete immutable output.
2. Record the branch, commit, dirty-state digest, logical file inventory,
   classification, byte size, checksum, and source execution environment with
   `scripts/migration_manifest.py`.
3. Clone the repository on the destination. Do not copy a Codex worktree
   `.git` pointer because it refers to the source host's Git metadata.
4. Overlay the recorded uncommitted files and restore private assets under the
   same repository-relative layout through an approved private channel.
5. Verify the manifest from the destination root before resuming work.
6. Treat a new OS, architecture, Blender build, GPU backend/device, or driver as
   a new determinism environment. Keep its results separate until the approved
   comparison passes.

POSIX-style paths in records are portable. Shell or PowerShell launchers may
resolve them from a machine-specific root at runtime, but that absolute root
must stay in ignored local configuration. Historical reports are evidence and
must not be bulk-edited to replace old machine paths.

### Publication Workflow

Publication requires an explicit request. When requested:

1. Confirm every staged artifact is allowed by the publication policy.
2. Run local validation and inspect the staged diff.
3. Push the task branch.
4. Open a pull request.
5. Inspect CI and required review results.
6. Merge only after required checks pass.

Do not force push, rewrite shared history, delete remote branches, or bypass a
failed/missing required check.

### Stop and Escalate

Stop at the smallest meaningful boundary when:

- a confirmed decision would need to change;
- authoritative documents conflict;
- Ground Truth appears incorrect or benchmark integrity may be compromised;
- sensitive data may be published;
- a destructive migration is required;
- a major dependency or architecture component is required;
- implementation depends on an unresolved architecture decision;
- existing user work may be overwritten; or
- the requested change materially exceeds the agreed scope.

Report the blocker, affected scope, available options, trade-offs, and the
recommended minimal option.

### Current Internal Review Focus

The active cross-cutting decision set is maintained in
[open_questions.md](open_questions.md). Review these themes there rather than
duplicating their full text here:

- first-prototype outcome and MVP boundary;
- available data, rights, and Blender resource inventory;
- spatial precision and mapping expectations;
- World State, Retrieval evidence, and Agent boundaries;
- benchmark protocol, metrics, and acceptance thresholds;
- public/private review responsibility and external-service usage.

### Maintaining This Guide

- Keep this document focused on orientation and workflow.
- Update authoritative specifications, ADRs, or Open Questions when the actual
  decision changes.
- Link to authoritative detail instead of copying it here.
- Keep private operational details out of the public repository.
- Run `python3 -B scripts/check.py` after each complete update.

---

<a id="繁體中文"></a>

## 繁體中文

適用對象：Amidst 專案貢獻者與審查者

儲存庫分類：`PUBLIC_ALLOWED`

### 文件目的

這份導讀說明團隊如何找到正確的決策文件、審查資訊，以及讓一項構想成為
可接受的儲存庫變更。它是供內部協作使用的入口，不是新的唯一依據。

請勿在本文件記錄密碼、私人連結、敏感場域細節、個人資料或其他
`PRIVATE_ONLY` 資訊。敏感內部資料只能存放在明確核准的私人位置。

### 從這裡開始

進行專案工作時，依下列順序：

```text
任務
  -> 專案地圖
  -> 直接相關的規格
  -> 視需要查閱術語表與未決問題
  -> 變更前確認
  -> 最小可行修改
  -> 本地驗證
  -> 收到發布要求時進行發布審查
```

除非另有明確指定，預設負責人為 Peter。預設負責不代表擁有審查或核准
權限，也不會讓尚未決定的事項自動定案。

### 文件權責

| 關注事項 | 具約束力的文件 | 本導讀的用途 |
| --- | --- | --- |
| 當前階段、阻塞事項與文件權責 | [專案地圖](00_Project_Map.md) | 找到正確起點 |
| 產品需求、使用者、MVP 與範圍 | [產品需求文件](01_PRD.md) | 判斷何時需要產品決策 |
| 元件、系統邊界與資訊流 | [系統架構](02_System_Architecture.md) | 找出受影響模組 |
| 正確性、評估指標與失敗歸因 | [評估框架](03_Evaluation_Framework.md) | 找出需要審查的評估議題 |
| 資料集與標註設計 | [資料集規格](04_Dataset_Specification.md) | 找出資料與真值標註審查需求 |
| 攝影機、區域與空間映射 | [空間模型規格](05_Spatial_Model_Specification.md) | 找出空間資料審查需求 |
| 查詢、證據與來源追溯 | [資料檢索規格](06_Retrieval_Specification.md) | 釐清資料檢索與 Agent 邊界 |
| 技術選擇及其理由 | [技術決策紀錄](07_Technical_Decisions.md) | 依循 ADR 流程 |
| 儲存庫與發布分類 | [儲存庫與資料發布政策](08_Repository_and_Data_Publication_Policy.md) | 執行資訊審查關卡 |
| 跨層資料契約候選方案 | [資料型別與交換格式](09_Data_Types_and_Exchange_Formats.md) | 定案前比較 Blender、影片、事件與來源追溯格式 |
| 共用詞彙 | [術語表](glossary.md) | 編輯前統一用語 |
| 跨文件未決事項 | [未決問題](open_questions.md) | 提報並追蹤待決問題 |
| 強制工作規則 | [AGENTS.md](../AGENTS.md) | 了解執行界線 |

若本導讀與具約束力的文件不一致，請停止並回報，不要自行選擇其中一方。

### 決策狀態

| 狀態 | 意義 | 誰可以使用 |
| --- | --- | --- |
| `OPEN` | 尚缺決策或必要證據 | 發現缺口的貢獻者或審查者 |
| `PROPOSED` | 已提出有依據、可供審查的候選方向 | 準備建議的貢獻者 |
| `CONFIRMED` | 已由人員明確核准，或事實已經查證 | 有權決策的人員 |
| `DEFERRED` | 團隊刻意延後處理 | 有權決策的人員 |
| `REJECTED` | 團隊明確否決，並留下原因 | 有權決策的人員 |

Codex 可以分析、比較、提出建議，並執行已確認的決策；不得自行把
`OPEN` 或 `PROPOSED` 項目改成 `CONFIRMED`。

### 決策如何分流

#### 單一文件或模組的問題

若未決事項只影響一份文件或一個模組，請留在該規格內，並標記為
`TODO` 或 `OPEN`。

#### 跨領域問題

若問題牽涉多份文件、架構、MVP 範圍、評估、資料集政策或全專案行為，
請登記在 [open_questions.md](open_questions.md)。已有 `OQ-xxx` 編號時，
直接引用該編號，不要在各處重複同一段討論。

#### 技術取捨

重大技術選擇應在 [07_Technical_Decisions.md](07_Technical_Decisions.md)
建立 ADR，記錄背景、替代方案、影響、驗證證據與重新檢視條件。

#### 決策流程

```text
OPEN 問題
  -> 找出所需證據與影響範圍
  -> 提出 PROPOSED 答案或 ADR
  -> 人員審查
  -> CONFIRMED / DEFERRED / REJECTED
  -> 更新直接受影響的文件
  -> 執行驗證並記錄結果
```

### 變更前確認

編輯前應先記錄：

| 欄位 | 必要內容 |
| --- | --- |
| Requirement／需求 | 已確認要達成的結果 |
| Impact Scope／影響範圍 | 受影響的檔案、模組、schema、資料與使用端 |
| Short Plan／簡短計畫 | 能完成需求的最少步驟與順序 |
| Acceptance Criteria／驗收條件 | 可觀察、足以證明完成的條件 |
| Failure Cases／失敗情況 | 必須停止或回報的情況 |

填寫前先讀相關規格，不得藉由這份紀錄把假設變成正式決策。

### 資訊審查機制

#### 儲存庫檔案分類

每個檔案加入 Git 前都要分類：

- `PUBLIC_ALLOWED`：通過一般檢查後，可放入公開儲存庫；
- `PRIVATE_ONLY`：不得加入公開儲存庫；
- `REVIEW_REQUIRED`：須經人員核准，否則不得加入或發布。

完整判定原則與發布檢查表以
[08_Repository_and_Data_Publication_Policy.md](08_Repository_and_Data_Publication_Policy.md)
為準。

#### 哪些資訊需要先審查

| 資訊或變更 | 繼續前需要的審查 |
| --- | --- |
| 產品、架構、評估、資料集、隱私或技術決策 | 人員明確確認 |
| 非原始碼的資料、媒體、模型、實驗或空間資產 | 依實際內容分類，必要時取得發布核准 |
| 會接收專案或私人資料的新外部服務 | 資料離開本機前取得明確核准 |
| 共用 schema 變更 | 下游使用端與相容性審查 |
| 真值標註修正 | 明確理由、來源紀錄，並與模型或系統修改分開 |
| 基準測試或指標流程變更 | 記錄理由，並限定前後結果如何比較 |
| 重大依賴或框架 | 說明需求、無依賴方案、替代選項、維護與相容性影響 |
| 破壞性的資料或 schema 遷移 | 明確核准及復原／版本計畫 |

#### 資料來源審查

觀測資料、人工標註的真值、模型預測、確定性衍生狀態、推論狀態、
合成／生成資料與人工確認資料必須能彼此區分。不得把生成或推論結果標示成
直接觀測。

### 變更流程

1. 確認儲存庫與工作樹狀態。
2. 閱讀專案地圖與直接相關的規格。
3. 當術語或未決範圍會影響任務時，查閱術語表與未決問題。
4. 完成變更前確認紀錄。
5. 建立並切換到任務專用分支；不得直接修改 `main`。
6. 只做最小可行修改，並保留不相關的既有工作。
7. 每個完整步驟後執行：

   ```bash
   python3 -B scripts/check.py
   ```

8. 如實回報錯誤；不得弱化測試或用假成功掩蓋問題。
9. 只提交與任務直接相關的檔案。

### 跨平台接續

平台限定的可執行指令、正式測試套件與 Blender runtime lock 以
[10_Cross_Platform_Setup_and_Testing.md](10_Cross_Platform_Setup_and_Testing.md)
為準；本節只負責工作流程邊界，不重複維護指令。

當 repository 或 Blender 任務要移到另一個作業系統：

1. 停止仍在寫入的程序，記錄最後一個完整且不可變的輸出。
2. 以 `scripts/migration_manifest.py` 記錄 branch、commit、dirty-state digest、
   logical file inventory、分類、byte size、checksum 與來源執行環境。
3. 在目標機器重新 clone；不得複製 Codex worktree 的 `.git` pointer，因為它
   指向來源主機的 Git metadata。
4. 覆蓋清單中的未提交檔案，並透過核准的私人管道，把私人資產放回相同的
   repository-relative layout。
5. 從目標 repository root 驗證 manifest，通過後才繼續工作。
6. 新的 OS、architecture、Blender build、GPU backend／device 或 driver 都視為
   新的 determinism environment；通過核准的比較前，不得混合兩邊結果。

紀錄內使用 POSIX-style 相對路徑。Shell／PowerShell 可在 runtime 從機器限定
root 解析，但該絕對 root 只能放在 ignored local config。歷史報告屬證據，
不得批次替換其中的舊 machine path。

### 發布流程

只有收到明確發布要求時，才進行以下步驟：

1. 確認每項準備提交的內容都符合發布政策。
2. 執行本地驗證並檢查 staged diff。
3. 推送任務分支。
4. 建立 Pull Request。
5. 檢查 CI 與必要審查結果。
6. 必要檢查全部通過後才能合併。

不得強制推送、重寫共用歷史、刪除遠端分支，或略過失敗／缺少的必要檢查。

### 何時必須停止並提報

遇到以下情況，應停在最小且仍有意義的邊界：

- 需要改變已確認的決策；
- 具約束力的文件互相矛盾；
- 真值標註可能有誤，或基準測試的完整性可能受損；
- 可能發布敏感資料；
- 需要破壞性遷移；
- 需要重大依賴或架構元件；
- 實作取決於尚未決定的架構議題；
- 可能覆蓋使用者既有工作；或
- 變更明顯超出已同意的範圍。

回報時應說明阻塞原因、影響範圍、可選方案、各自取捨，以及建議的最小方案。

### 目前內部審查重點

跨領域待決事項統一維護在 [open_questions.md](open_questions.md)，請直接在
該處檢視以下主題，不要在本導讀重複完整內容：

- 第一版原型要證明什麼，以及 MVP 邊界；
- 現有資料、使用權與 Blender 資源盤點；
- 空間精度與映射需求；
- 世界狀態、資料檢索證據與 Agent 邊界；
- 基準測試流程、評估指標與驗收門檻；
- 公開／私人內容的審查權責，以及外部服務使用方式。

### 維護原則

- 本文件只負責提供方向與流程。
- 實際決策變更時，應更新對應規格、ADR 或未決問題。
- 以連結指向具約束力的細節，不要在此重建一份重複的規格。
- 公開儲存庫不得出現私人作業細節。
- 每個完整更新後執行 `python3 -B scripts/check.py`。
