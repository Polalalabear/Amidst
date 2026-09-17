# Cross-Platform Setup and Testing / 跨平台設定與測試

[English](#english) | [繁體中文](#繁體中文)

<a id="english"></a>

## English

Document status: `CONFIRMED` for the commands and the verified macOS profile;
Windows and Linux runtime verification remain `OPEN` until they pass on each
destination.

### Version matrix

| Profile | OS version | Architecture | Blender | Embedded Python | Status |
| --- | --- | --- | --- | --- | --- |
| macOS source | Darwin 25.6.0 | arm64 | 5.2.1 LTS, build `9e2066aef7ef` | 3.13.13 | `CONFIRMED` |
| Windows target | Record the exact Windows edition and build with `Get-ComputerInfo` | x86_64 | 5.2.1 LTS, build `9e2066aef7ef` required | 3.13.13 required | `OPEN` |
| Linux target | Record distribution and `uname -a` output | x86_64 | 5.2.1 LTS, build `9e2066aef7ef` required | 3.13.13 required | `OPEN` |

The standalone repository tools require Python 3.9 or newer. Exact destination
OS, driver, GPU device, and standalone Python versions are evidence fields, not
assumptions; record them before a diagnostic run.

This guide owns the executable setup and test commands for repository migration.
Repository records continue to use POSIX-style relative paths. Installation
paths and PATH changes are machine-local configuration and must not be stored in
reports, manifests, or committed configuration.

The formal repository suite uses Python's standard-library `unittest`; the
intentionally empty `requirements-dev.lock.txt` confirms that it has no PyPI
dependency. Blender supplies `bpy`, `mathutils`, NumPy, and OpenImageIO through
its embedded Python. Their exact verified versions are locked in
`blender/runtime_dependencies.lock.json`; do not install replacements into the
standalone project Python.

### Shared external Blender roots

Status: the resolver, guards, lock, and manifest v0.2.0 behavior are
`CONFIRMED`; the physical Windows and Linux profiles remain `OPEN` until run on
those systems.

Large private assets may be stored once outside all Git worktrees. Runtime
paths are selected in this order: environment variable, ignored
`local/asset_roots.json`, then the compatible repository-local fallback.

| Logical root | Environment variable | Access |
| --- | --- | --- |
| `blender-source` | `AMIDST_BLENDER_SOURCE_ROOT` | read-only |
| `blender-textures` | `AMIDST_BLENDER_TEXTURE_ROOT` | read-only |
| `blender-working` | `AMIDST_BLENDER_WORK_ROOT` | task-scoped write |
| `blender-output` | `AMIDST_BLENDER_OUTPUT_ROOT` | task-scoped write |

Copy `config/asset_roots.example.json` to ignored
`local/asset_roots.json` only when environment variables are unsuitable, and
replace every placeholder with an absolute local path. Never add the populated
file to Git. A symlink or junction under `local/` is optional for browsing;
scripts use the resolver rather than depending on that link.

Run the health check after configuring all four roots:

```bash
python3 -B scripts/check_asset_roots.py \
  --require-read-only-source \
  --probe-output
```

The output probe acquires an atomic task lock, writes and removes a disposable
probe, and releases the lock. It never prints physical roots. Source tools also
compare SHA-256 before and after writes to derived files. A stale
`.amidst-task.lock` is evidence of an interrupted writer; inspect its process
and run context and do not delete it automatically.

Contract `amidst.migration_manifest/0.2.0` binds logical aliases at runtime and serializes only logical
URIs, root-relative paths, sizes, classifications, and SHA-256 values:

```bash
python3 -B scripts/migration_manifest.py create \
  --source-root repository=. \
  --source-root "blender-source=$AMIDST_BLENDER_SOURCE_ROOT" \
  --git-root . \
  --entry PUBLIC_ALLOWED:docs \
  --logical-entry PRIVATE_ONLY:blender-source:school_v1.blend \
  --output local/migration_manifest_v0_2_0.json

python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_2_0.json \
  --target-root repository=. \
  --target-root "blender-source=$AMIDST_BLENDER_SOURCE_ROOT"
```

Existing v0.1.0 manifests remain supported with the original
`--target-root .` command. A populated manifest remains `REVIEW_REQUIRED`, and
the `.blend` content it identifies remains `PRIVATE_ONLY`.

### macOS

The verified installation is Blender 5.2.1 LTS in the standard application
bundle. Add its executable directory to the user shell configuration:

```zsh
if [[ -d "/Applications/Blender.app/Contents/MacOS" ]]; then
  export PATH="/Applications/Blender.app/Contents/MacOS:$PATH"
fi
```

Choose one private storage root and keep these values only in local shell
configuration:

```zsh
export AMIDST_PRIVATE_STORAGE_ROOT="/path/to/amidst-private/blender"
export AMIDST_BLENDER_SOURCE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/source"
export AMIDST_BLENDER_TEXTURE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/textures"
export AMIDST_BLENDER_WORK_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/working"
export AMIDST_BLENDER_OUTPUT_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/output"
mkdir -p "$AMIDST_BLENDER_WORK_ROOT" "$AMIDST_BLENDER_OUTPUT_ROOT"
chmod -R a-w "$AMIDST_BLENDER_SOURCE_ROOT" "$AMIDST_BLENDER_TEXTURE_ROOT"
```

The source and texture directories must already contain the approved private
assets before the health check. An optional ignored browsing link is:

```zsh
ln -s "$AMIDST_PRIVATE_STORAGE_ROOT" local/blender_assets
```

Open a new shell, or load the updated configuration with `source ~/.zshrc`, then
verify setup and run the repository suite:

```zsh
blender --version
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
python3 -B scripts/check_asset_roots.py --require-read-only-source --probe-output
```

Verify a transferred overlay from the destination repository root:

```zsh
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

### Windows (PowerShell)

Install Blender 5.2.1 LTS. If the installation directory differs, change only
the local `$BlenderDir` value; never serialize it into project evidence. Add the
directory to the user PATH and current PowerShell session:

```powershell
$PSVersionTable.PSVersion
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture
py -3 --version
$BlenderDir = Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2'
if (-not (Test-Path (Join-Path $BlenderDir 'blender.exe'))) { throw 'Blender 5.2 executable not found' }
$UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($UserPath -split ';') -notcontains $BlenderDir) { [Environment]::SetEnvironmentVariable('Path', "$BlenderDir;$UserPath", 'User') }
$env:Path = "$BlenderDir;$env:Path"
blender --version
```

Configure the private roots for the current PowerShell session. Persist them
with the normal user-environment mechanism only after verifying the values:

```powershell
$AssetBase = 'D:\amidst-private\blender'
$env:AMIDST_BLENDER_SOURCE_ROOT = Join-Path $AssetBase 'source'
$env:AMIDST_BLENDER_TEXTURE_ROOT = Join-Path $AssetBase 'textures'
$env:AMIDST_BLENDER_WORK_ROOT = Join-Path $AssetBase 'working'
$env:AMIDST_BLENDER_OUTPUT_ROOT = Join-Path $AssetBase 'output'
New-Item -ItemType Directory -Force -Path $env:AMIDST_BLENDER_WORK_ROOT, $env:AMIDST_BLENDER_OUTPUT_ROOT | Out-Null
if (-not (Test-Path $env:AMIDST_BLENDER_SOURCE_ROOT)) { throw 'Private Blender source root is missing' }
if (-not (Test-Path $env:AMIDST_BLENDER_TEXTURE_ROOT)) { throw 'Private Blender texture root is missing' }
```

Configure the source and texture directories with an explicit read-only NTFS
ACL appropriate to the local account, then inspect it with `Get-Acl`. A Windows
directory junction under `local/` is optional; the resolver does not require
Developer Mode or symlink privileges.

Run the repository suite and verify the Blender-embedded dependencies:

```powershell
py -3 -m pip install --requirement requirements-dev.lock.txt
py -3 -B scripts/check.py
py -3 -B scripts/test.py
$BlenderExe = Join-Path $BlenderDir 'blender.exe'
& $BlenderExe --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
py -3 -B scripts/check_asset_roots.py --require-read-only-source --probe-output
```

Verify a transferred overlay from the destination repository root:

```powershell
py -3 -B scripts/migration_manifest.py verify --manifest local/migration_manifest_v0_1_1.json --target-root .
```

### Linux (Bash)

Use an x86_64 Blender 5.2.1 LTS archive whose runtime matches
`blender/runtime_dependencies.lock.json`. Keep the extracted installation path
in local shell configuration; the example directory may be changed locally:

```bash
uname -a
python3 --version
export BLENDER_DIR="$HOME/opt/blender-5.2.1-linux-x64"
if [[ ! -x "$BLENDER_DIR/blender" ]]; then echo "Blender 5.2 executable not found" >&2; exit 1; fi
export PATH="$BLENDER_DIR:$PATH"
blender --version
```

Configure external private roots and make shared source inputs read-only:

```bash
export AMIDST_PRIVATE_STORAGE_ROOT="/path/to/amidst-private/blender"
export AMIDST_BLENDER_SOURCE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/source"
export AMIDST_BLENDER_TEXTURE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/textures"
export AMIDST_BLENDER_WORK_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/working"
export AMIDST_BLENDER_OUTPUT_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/output"
mkdir -p "$AMIDST_BLENDER_WORK_ROOT" "$AMIDST_BLENDER_OUTPUT_ROOT"
chmod -R a-w "$AMIDST_BLENDER_SOURCE_ROOT" "$AMIDST_BLENDER_TEXTURE_ROOT"
```

Run the repository suite and verify the Blender-embedded dependencies:

```bash
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
python3 -B scripts/check_asset_roots.py --require-read-only-source --probe-output
```

Verify a transferred overlay from the destination repository root:

```bash
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

Do not continue a macOS diagnostic run by appending Windows or Linux output. A change in
OS, architecture, Blender build, backend, device, or driver creates a distinct
determinism environment and requires a new output directory and a complete
approved comparison run.

<a id="繁體中文"></a>

## 繁體中文

文件狀態：指令與已驗證的 macOS profile 為 `CONFIRMED`；Windows 與 Linux
runtime 必須在各自目標機器通過檢查後才能確認，目前維持 `OPEN`。

### 版本矩陣

| Profile | OS 版本 | Architecture | Blender | Embedded Python | 狀態 |
| --- | --- | --- | --- | --- | --- |
| macOS 來源 | Darwin 25.6.0 | arm64 | 5.2.1 LTS，build `9e2066aef7ef` | 3.13.13 | `CONFIRMED` |
| Windows 目標 | 以 `Get-ComputerInfo` 記錄實際 edition 與 build | x86_64 | 必須為 5.2.1 LTS，build `9e2066aef7ef` | 必須為 3.13.13 | `OPEN` |
| Linux 目標 | 記錄 distribution 與 `uname -a` | x86_64 | 必須為 5.2.1 LTS，build `9e2066aef7ef` | 必須為 3.13.13 | `OPEN` |

獨立 repository 工具需要 Python 3.9 以上。目標 OS、driver、GPU device 與獨立
Python 的精確版本都屬於證據欄位，不得預先假設；diagnostic 前必須記錄。

本文件負責 repository 遷移時的可執行設定與測試指令。Repository 紀錄仍使用
POSIX-style 相對路徑。安裝路徑與 PATH 調整屬於機器本機設定，不得寫入 report、
manifest 或已提交的設定。

正式 repository 測試套件使用 Python 標準庫 `unittest`；刻意不含套件項目的
`requirements-dev.lock.txt` 表示沒有 PyPI 依賴。`bpy`、`mathutils`、NumPy 與
OpenImageIO 由 Blender embedded Python 提供；精確版本鎖定於
`blender/runtime_dependencies.lock.json`，不得在獨立的專案 Python 中另外安裝
替代版本。

### 共用的外部Blender根目錄

Resolver、guard、lock與manifest v0.2.0行為為`CONFIRMED`；Windows與Linux的
實體profile仍須在各目標系統實際執行後才能確認，目前維持`OPEN`。

大型私人資產可以只保存一份並置於所有Git worktree之外。Runtime依序使用
環境變數、ignored的`local/asset_roots.json`，最後才使用相容的repository內
fallback。

| Logical root | 環境變數 | 存取模式 |
| --- | --- | --- |
| `blender-source` | `AMIDST_BLENDER_SOURCE_ROOT` | 唯讀 |
| `blender-textures` | `AMIDST_BLENDER_TEXTURE_ROOT` | 唯讀 |
| `blender-working` | `AMIDST_BLENDER_WORK_ROOT` | task-scoped write |
| `blender-output` | `AMIDST_BLENDER_OUTPUT_ROOT` | task-scoped write |

只有在環境變數不合適時，才把`config/asset_roots.example.json`複製為ignored的
`local/asset_roots.json`，並把所有placeholder替換成該機器的absolute path；
填入後的檔案不得加入Git。`local/`下的symlink或junction只供人工瀏覽，腳本
使用resolver，不依賴該link。

設定四個root後執行：

```bash
python3 -B scripts/check_asset_roots.py \
  --require-read-only-source \
  --probe-output
```

Output probe會取得atomic task lock、寫入並刪除一次性probe，再釋放lock，且不
輸出任何實體root。Source工具另外以寫入derived file前後的SHA-256確認source
未變。Stale `.amidst-task.lock`代表writer曾中斷；必須先檢查process與run
context，不得自動刪除。

契約`amidst.migration_manifest/0.2.0`只序列化logical URI、root-relative
path、大小、分類與SHA-256：

```bash
python3 -B scripts/migration_manifest.py create \
  --source-root repository=. \
  --source-root "blender-source=$AMIDST_BLENDER_SOURCE_ROOT" \
  --git-root . \
  --entry PUBLIC_ALLOWED:docs \
  --logical-entry PRIVATE_ONLY:blender-source:school_v1.blend \
  --output local/migration_manifest_v0_2_0.json

python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_2_0.json \
  --target-root repository=. \
  --target-root "blender-source=$AMIDST_BLENDER_SOURCE_ROOT"
```

既有v0.1.0 manifest繼續支援原本的`--target-root .`。填入內容的manifest仍為
`REVIEW_REQUIRED`，其所識別的`.blend`內容仍為`PRIVATE_ONLY`。

### macOS 使用方式

已驗證的安裝為標準 application bundle 內的 Blender 5.2.1 LTS。將 executable
directory 加入使用者 shell 設定：

```zsh
if [[ -d "/Applications/Blender.app/Contents/MacOS" ]]; then
  export PATH="/Applications/Blender.app/Contents/MacOS:$PATH"
fi
```

選擇單一私人儲存root，以下值只放在本機shell設定：

```zsh
export AMIDST_PRIVATE_STORAGE_ROOT="/path/to/amidst-private/blender"
export AMIDST_BLENDER_SOURCE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/source"
export AMIDST_BLENDER_TEXTURE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/textures"
export AMIDST_BLENDER_WORK_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/working"
export AMIDST_BLENDER_OUTPUT_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/output"
mkdir -p "$AMIDST_BLENDER_WORK_ROOT" "$AMIDST_BLENDER_OUTPUT_ROOT"
chmod -R a-w "$AMIDST_BLENDER_SOURCE_ROOT" "$AMIDST_BLENDER_TEXTURE_ROOT"
```

執行health check前，source與texture目錄必須已有核准的私人資產。可選的ignored
瀏覽link為：

```zsh
ln -s "$AMIDST_PRIVATE_STORAGE_ROOT" local/blender_assets
```

開啟新的 shell，或執行 `source ~/.zshrc` 載入更新，然後驗證設定並執行測試：

```zsh
blender --version
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
python3 -B scripts/check_asset_roots.py --require-read-only-source --probe-output
```

從目標 repository root 驗證搬運後的 overlay：

```zsh
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

### Windows 使用方式（PowerShell）

安裝 Blender 5.2.1 LTS。若實際安裝位置不同，只調整本機 `$BlenderDir`，不得把
該絕對路徑序列化進專案證據。把目錄加入使用者 PATH 與目前 PowerShell session：

```powershell
$PSVersionTable.PSVersion
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsBuildNumber, OsArchitecture
py -3 --version
$BlenderDir = Join-Path $env:ProgramFiles 'Blender Foundation\Blender 5.2'
if (-not (Test-Path (Join-Path $BlenderDir 'blender.exe'))) { throw 'Blender 5.2 executable not found' }
$UserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($UserPath -split ';') -notcontains $BlenderDir) { [Environment]::SetEnvironmentVariable('Path', "$BlenderDir;$UserPath", 'User') }
$env:Path = "$BlenderDir;$env:Path"
blender --version
```

為目前PowerShell session設定私人root；確認內容無誤後，才使用一般user
environment機制保存：

```powershell
$AssetBase = 'D:\amidst-private\blender'
$env:AMIDST_BLENDER_SOURCE_ROOT = Join-Path $AssetBase 'source'
$env:AMIDST_BLENDER_TEXTURE_ROOT = Join-Path $AssetBase 'textures'
$env:AMIDST_BLENDER_WORK_ROOT = Join-Path $AssetBase 'working'
$env:AMIDST_BLENDER_OUTPUT_ROOT = Join-Path $AssetBase 'output'
New-Item -ItemType Directory -Force -Path $env:AMIDST_BLENDER_WORK_ROOT, $env:AMIDST_BLENDER_OUTPUT_ROOT | Out-Null
if (-not (Test-Path $env:AMIDST_BLENDER_SOURCE_ROOT)) { throw 'Private Blender source root is missing' }
if (-not (Test-Path $env:AMIDST_BLENDER_TEXTURE_ROOT)) { throw 'Private Blender texture root is missing' }
```

Source與texture目錄要依本機account設定明確的唯讀NTFS ACL，並以`Get-Acl`
檢查。`local/`下的Windows directory junction是選配；resolver不要求Developer
Mode或symlink權限。

執行 repository suite 並驗證 Blender embedded dependencies：

```powershell
py -3 -m pip install --requirement requirements-dev.lock.txt
py -3 -B scripts/check.py
py -3 -B scripts/test.py
$BlenderExe = Join-Path $BlenderDir 'blender.exe'
& $BlenderExe --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
py -3 -B scripts/check_asset_roots.py --require-read-only-source --probe-output
```

從目標 repository root 驗證搬運後的 overlay：

```powershell
py -3 -B scripts/migration_manifest.py verify --manifest local/migration_manifest_v0_1_1.json --target-root .
```

### Linux 使用方式（Bash）

使用 x86_64 Blender 5.2.1 LTS archive，且 runtime 必須符合
`blender/runtime_dependencies.lock.json`。解壓縮位置屬本機 shell 設定；範例
directory 可依實際安裝位置調整：

```bash
uname -a
python3 --version
export BLENDER_DIR="$HOME/opt/blender-5.2.1-linux-x64"
if [[ ! -x "$BLENDER_DIR/blender" ]]; then echo "Blender 5.2 executable not found" >&2; exit 1; fi
export PATH="$BLENDER_DIR:$PATH"
blender --version
```

設定外部私人root，並把共用source input設成唯讀：

```bash
export AMIDST_PRIVATE_STORAGE_ROOT="/path/to/amidst-private/blender"
export AMIDST_BLENDER_SOURCE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/source"
export AMIDST_BLENDER_TEXTURE_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/textures"
export AMIDST_BLENDER_WORK_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/working"
export AMIDST_BLENDER_OUTPUT_ROOT="$AMIDST_PRIVATE_STORAGE_ROOT/output"
mkdir -p "$AMIDST_BLENDER_WORK_ROOT" "$AMIDST_BLENDER_OUTPUT_ROOT"
chmod -R a-w "$AMIDST_BLENDER_SOURCE_ROOT" "$AMIDST_BLENDER_TEXTURE_ROOT"
```

執行 repository suite 並驗證 Blender embedded dependencies：

```bash
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
python3 -B scripts/check_asset_roots.py --require-read-only-source --probe-output
```

從目標 repository root 驗證搬運後的 overlay：

```bash
python3 -B scripts/migration_manifest.py verify \
  --manifest local/migration_manifest_v0_1_1.json \
  --target-root .
```

不得以 Windows 或 Linux output 接續 macOS diagnostic run。OS、architecture、Blender
build、backend、device 或 driver 任一改變，都形成新的 determinism environment；
必須使用新的 output directory，並重新執行完整且已核准的比較流程。
