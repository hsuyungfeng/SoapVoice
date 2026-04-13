<# 
SoapVoice Windows 自動打包腳本

此 PowerShell 腳本自動執行以下步驟：
1. 檢查 Python 3.11+ 是否安裝，若未安裝則提示使用者手動安裝。
2. 檢查 uv 是否可用，若未安裝則透過 `pip install uv` 安裝。
3. 執行 `uv sync` 安裝專案依賴。
4. 安裝 PyInstaller（若未安裝）：`uv add --group dev pyinstaller`。
5. 執行 `pyinstaller --clean soapvoice.spec` 產生 `dist\SoapVoice.exe`。
6. 檢查 Inno Setup 是否安裝（透過 `iscc --version`），若已安裝則編譯安裝腳本：`iscc installer\soapvoice.iss`。
7. 顯示產生的檔案路徑與後續步驟。

注意：腳本需以管理員權限執行，以確保 PyInstaller 與 Inno Setup 編譯正常。
若缺少管理員權限，腳本會提示使用者以管理員身份重新執行。
#>

param(
    [switch]$SkipInnoSetup,
    [switch]$SkipPythonCheck,
    [switch]$Help
)

if ($Help) {
    Write-Host "使用方法: .\windows_package.ps1 [-SkipInnoSetup] [-SkipPythonCheck] [-Help]"
    Write-Host "  -SkipInnoSetup     跳過 Inno Setup 編譯步驟"
    Write-Host "  -SkipPythonCheck   跳過 Python 版本檢查"
    Write-Host "  -Help              顯示此說明"
    exit 0
}

$ErrorActionPreference = "Stop"
$script:ScriptPath = $PSScriptRoot
$script:ProjectRoot = if ($ScriptPath) { $ScriptPath } else { Get-Location }
$script:DistExe = Join-Path $ProjectRoot "dist\SoapVoice.exe"
$script:IssFile = Join-Path $ProjectRoot "installer\soapvoice.iss"
$script:InnoSetupInstalled = $false

function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Cyan
}

function Write-Success($message) {
    Write-Host "[SUCCESS] $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor Yellow
}

function Write-ErrorAndExit($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
    Write-Host "打包失敗，請檢查上述錯誤訊息。"
    exit 1
}

function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# 檢查管理員權限
if (-not (Test-Administrator)) {
    Write-Warning "建議以管理員權限執行此腳本，以確保 PyInstaller 與 Inno Setup 編譯正常。"
    Write-Warning "請以管理員身份開啟 PowerShell 並重新執行。"
    $confirm = Read-Host "仍要繼續嗎？ (y/N)"
    if ($confirm -ne 'y' -and $confirm -ne 'Y') {
        exit 1
    }
}

# 步驟 1：檢查 Python 3.11+
if (-not $SkipPythonCheck) {
    Write-Info "步驟 1：檢查 Python 3.11+ 安裝"
    $pythonVersion = (python --version 2>&1) | Out-String
    if ($LASTEXITCODE -ne 0 -or -not $pythonVersion -match "Python (\d+)\.(\d+)") {
        Write-ErrorAndExit "Python 未安裝或不在 PATH 中。請手動安裝 Python 3.11+ 並將其加入 PATH。"
    }
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 11)) {
        Write-ErrorAndExit "偵測到 Python $major.$minor，需要 Python 3.11+。請升級 Python 版本。"
    }
    Write-Success "Python $major.$minor 已安裝"
} else {
    Write-Info "跳過 Python 檢查"
}

# 步驟 2：檢查 uv 並安裝
Write-Info "步驟 2：檢查 uv 工具"
$uvVersion = (uv --version 2>&1) | Out-String
if ($LASTEXITCODE -ne 0) {
    Write-Info "uv 未安裝，正在透過 pip 安裝 uv..."
    pip install uv
    if ($LASTEXITCODE -ne 0) {
        Write-ErrorAndExit "安裝 uv 失敗，請手動執行 'pip install uv'。"
    }
    Write-Success "uv 安裝完成"
} else {
    Write-Success "uv 已安裝 ($uvVersion)"
}

# 步驟 3：安裝專案依賴
Write-Info "步驟 3：安裝專案依賴 (uv sync)"
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-ErrorAndExit "uv sync 失敗，請檢查網路連線或專案設定。"
}
Write-Success "專案依賴安裝完成"

# 步驟 4：安裝 PyInstaller（若未安裝）
Write-Info "步驟 4：安裝 PyInstaller"
uv add --group dev pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-ErrorAndExit "安裝 PyInstaller 失敗。"
}
Write-Success "PyInstaller 安裝完成"

# 步驟 5：執行 PyInstaller 打包
Write-Info "步驟 5：執行 PyInstaller 打包"
Write-Info "此步驟可能需要數分鐘，請稍候..."
pyinstaller --clean soapvoice.spec
if ($LASTEXITCODE -ne 0) {
    Write-ErrorAndExit "PyInstaller 打包失敗，請檢查 soapvoice.spec 配置。"
}
if (-not (Test-Path $DistExe)) {
    Write-ErrorAndExit "打包後未找到 $DistExe，請檢查 PyInstaller 輸出。"
}
$exeSize = (Get-Item $DistExe).Length / 1MB
Write-Success "打包完成！$DistExe ($exeSize MB)"

# 步驟 6：檢查 Inno Setup 並編譯安裝腳本（可選）
if (-not $SkipInnoSetup) {
    Write-Info "步驟 6：檢查 Inno Setup 安裝"
    $isccVersion = (iscc --version 2>&1) | Out-String
    if ($LASTEXITCODE -eq 0) {
        $script:InnoSetupInstalled = $true
        Write-Success "Inno Setup 已安裝 ($isccVersion)"
    } else {
        Write-Warning "Inno Setup 未安裝或不在 PATH 中。跳過安裝程式編譯。"
        Write-Warning "請從 https://jrsoftware.org/isdl.php 下載安裝 Inno Setup。"
        $script:InnoSetupInstalled = $false
    }

    if ($script:InnoSetupInstalled) {
        if (-not (Test-Path $IssFile)) {
            Write-Warning "安裝腳本 $IssFile 不存在，跳過編譯。"
        } else {
            Write-Info "編譯 Inno Setup 安裝腳本..."
            iscc $IssFile
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Inno Setup 編譯失敗，請檢查 $IssFile 內容。"
            } else {
                $setupExe = Join-Path $ProjectRoot "installer\SoapVoiceSetup.exe"
                if (Test-Path $setupExe) {
                    $setupSize = (Get-Item $setupExe).Length / 1MB
                    Write-Success "安裝程式編譯完成！$setupExe ($setupSize MB)"
                } else {
                    Write-Success "安裝程式編譯完成，檔案可能位於 installer\ 目錄。"
                }
            }
        }
    }
} else {
    Write-Info "跳過 Inno Setup 編譯"
}

# 步驟 7：顯示後續步驟
Write-Info "打包流程完成！"
Write-Host "`n========== 後續步驟 ==========" -ForegroundColor Magenta
Write-Host "1. 可執行檔位置：$DistExe" -ForegroundColor Yellow
Write-Host "2. 若要測試執行，請執行: $DistExe" -ForegroundColor Yellow
if ($script:InnoSetupInstalled -and (Test-Path (Join-Path $ProjectRoot "installer\SoapVoiceSetup.exe"))) {
    Write-Host "3. 安裝程式位置：$(Join-Path $ProjectRoot "installer\SoapVoiceSetup.exe")" -ForegroundColor Yellow
    Write-Host "   無訊息安裝命令：SoapVoiceSetup.exe /SILENT /SUPPRESSMSGBOXES" -ForegroundColor Yellow
} else {
    Write-Host "3. 安裝程式未產生，請確認 Inno Setup 已安裝並重新執行腳本（不加 -SkipInnoSetup）。" -ForegroundColor Yellow
}
Write-Host "4. 若遇到執行問題，請參考專案文件與 .planning/phases/09-windows/09-windows-USER-SETUP.md" -ForegroundColor Yellow
Write-Host "`n感謝使用 SoapVoice 打包腳本！" -ForegroundColor Cyan