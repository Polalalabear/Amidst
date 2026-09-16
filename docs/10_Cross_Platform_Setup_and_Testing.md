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

### macOS

The verified installation is Blender 5.2.1 LTS in the standard application
bundle. Add its executable directory to the user shell configuration:

```zsh
if [[ -d "/Applications/Blender.app/Contents/MacOS" ]]; then
  export PATH="/Applications/Blender.app/Contents/MacOS:$PATH"
fi
```

Open a new shell, or load the updated configuration with `source ~/.zshrc`, then
verify setup and run the repository suite:

```zsh
blender --version
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
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

Run the repository suite and verify the Blender-embedded dependencies:

```powershell
py -3 -m pip install --requirement requirements-dev.lock.txt
py -3 -B scripts/check.py
py -3 -B scripts/test.py
$BlenderExe = Join-Path $BlenderDir 'blender.exe'
& $BlenderExe --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
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

Run the repository suite and verify the Blender-embedded dependencies:

```bash
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
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

### macOS 使用方式

已驗證的安裝為標準 application bundle 內的 Blender 5.2.1 LTS。將 executable
directory 加入使用者 shell 設定：

```zsh
if [[ -d "/Applications/Blender.app/Contents/MacOS" ]]; then
  export PATH="/Applications/Blender.app/Contents/MacOS:$PATH"
fi
```

開啟新的 shell，或執行 `source ~/.zshrc` 載入更新，然後驗證設定並執行測試：

```zsh
blender --version
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
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

執行 repository suite 並驗證 Blender embedded dependencies：

```powershell
py -3 -m pip install --requirement requirements-dev.lock.txt
py -3 -B scripts/check.py
py -3 -B scripts/test.py
$BlenderExe = Join-Path $BlenderDir 'blender.exe'
& $BlenderExe --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
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

執行 repository suite 並驗證 Blender embedded dependencies：

```bash
python3 -m pip install --requirement requirements-dev.lock.txt
python3 -B scripts/check.py
python3 -B scripts/test.py
blender --background --factory-startup --python blender/scripts/check_runtime_dependencies.py
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
