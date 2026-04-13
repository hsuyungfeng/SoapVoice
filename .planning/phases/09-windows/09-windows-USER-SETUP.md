# Phase 9: Windows 打包 - 使用者設定指南

**狀態：** 部分完成（需 Windows 環境）

## PyInstaller 打包步驟

### 目的
將 SoapVoice 專案打包為 Windows 單一可執行檔 (`dist\SoapVoice.exe`)，內嵌所有模型與資料檔案。

### 設定步驟

#### 1. 安裝 Python 3.11+
- **下載：** [Python 3.11+ 官方下載頁面](https://www.python.org/downloads/windows/)
- **安裝注意事項：**
  - 安裝時勾選「Add Python to PATH」
  - 建議安裝位置：`C:\Python311`（可自訂）

#### 2. 安裝 uv（現代 Python 套件管理工具）
```cmd
pip install uv
```
- **驗證：** `uv --version` 應顯示版本號

#### 3. 下載專案原始碼
- 從 GitHub 複製或下載 SoapVoice 專案至本機目錄（例如 `C:\SoapVoice`）
- 確保目錄包含 `pyproject.toml`、`soapvoice.spec` 等檔案

#### 4. 安裝專案依賴
```cmd
cd C:\SoapVoice
uv sync
```
- 此命令會根據 `pyproject.toml` 安裝所有必要套件

#### 5. 安裝 PyInstaller（打包工具）
```cmd
uv add --group dev pyinstaller
```

#### 6. 執行打包
```cmd
pyinstaller --clean soapvoice.spec
```
- **輸出：** `dist\SoapVoice.exe`（單一可執行檔，大小約 50–100 MB）
- **時間：** 此過程可能需要 5–15 分鐘，視系統效能而定

#### 7. 驗證打包結果
```cmd
dist\SoapVoice.exe --help
```
- 若出現 SoapVoice 說明文字，表示打包成功
- 若出現錯誤（例如缺少 DLL），請參考「問題排除」章節

### 自動化腳本（推薦）
專案提供自動化 PowerShell 腳本 `scripts\windows_package.ps1`，可一鍵執行上述所有步驟，詳見「使用自動化腳本」章節。

## 使用自動化腳本

### PowerShell 腳本 (`windows_package.ps1`)
此腳本自動執行 Python 檢查、uv 安裝、依賴安裝、PyInstaller 打包與 Inno Setup 編譯（若已安裝）。

#### 執行方式（管理員 PowerShell）
```powershell
# 切換至專案根目錄
cd C:\SoapVoice

# 執行腳本（預設包含 Inno Setup 編譯）
.\scripts\windows_package.ps1

# 跳過 Inno Setup 編譯
.\scripts\windows_package.ps1 -SkipInnoSetup

# 跳過 Python 檢查
.\scripts\windows_package.ps1 -SkipPythonCheck
```

#### 批次檔 (`windows_package.bat`)
若不熟悉 PowerShell，可使用批次檔：
```cmd
cd C:\SoapVoice
scripts\windows_package.bat
```
批次檔會自動呼叫 PowerShell 腳本並處理執行原則。

#### 腳本功能
1. 檢查管理員權限（建議）
2. 檢查 Python 3.11+ 與 uv
3. 安裝缺失工具與依賴
4. 執行 PyInstaller 打包
5. 若 Inno Setup 已安裝，編譯安裝腳本
6. 顯示產生的檔案路徑與後續步驟

## Inno Setup 安裝程式製作

### 目的
編譯 Windows 安裝程式腳本 (`installer/soapvoice.iss`) 以產生 `SoapVoiceSetup.exe`。

### 設定步驟

#### 1. 安裝 Inno Setup
- **下載：** [Inno Setup 6.3.0 或更新版本](https://jrsoftware.org/isdl.php)
- **安裝注意事項：**
  - 安裝時勾選「Install Inno Setup Preprocessor」
  - 勾選「Add Inno Setup to PATH」（方便命令列使用 `iscc`）
  - 預設安裝路徑：`C:\Program Files (x86)\Inno Setup 6`

#### 2. 準備 SoapVoice.exe
- **來源：** 需先完成上述 PyInstaller 打包，產生 `dist\SoapVoice.exe`
- **位置：** 確保 `dist\SoapVoice.exe` 存在且可執行

#### 3. 編譯安裝腳本
```cmd
cd /d C:\path\to\SoapVoice
iscc installer\soapvoice.iss
```
- **輸出：** `installer\SoapVoiceSetup.exe`（或根據腳本的 `OutputDir` 設定）

#### 4. 測試安裝程式
- **無訊息安裝：**
  ```cmd
  SoapVoiceSetup.exe /SILENT /SUPPRESSMSGBOXES
  ```
- **一般安裝：** 直接執行 `SoapVoiceSetup.exe` 並遵循安裝精靈
- **解除安裝：** 透過控制台「解除安裝程式」或執行 `C:\Program Files\SoapVoice\uninstall.exe`

### 環境變數
無需環境變數。

### 儀表板配置
無需儀表板配置。

### 驗證命令
```cmd
# 確認 iscc 可用
iscc --version

# 確認 SoapVoice.exe 存在
dir dist\SoapVoice.exe

# 編譯測試
iscc installer\soapvoice.iss /Q
```

## Wine 交叉編譯（Linux 環境）

### 目的
在 Linux 環境下使用 Wine 進行 Windows 交叉編譯，無需 Windows 作業系統即可產生 `SoapVoice.exe`。

### 前提條件
- **Wine** 已安裝並可執行 Windows 程式
- **Wine Python** 環境（可透過 `winetricks python311` 安裝）
- **Linux 系統**（Ubuntu/Debian/Fedora 等）

### 安裝 Wine
```bash
# Ubuntu/Debian
sudo apt install wine
# Fedora
sudo dnf install wine
```

### 設定 Wine Python 環境
```bash
# 安裝 winetricks（若未安裝）
sudo apt install winetricks
# 建立 32 位元或 64 位元 Wine prefix（建議 64 位元）
export WINEPREFIX="$HOME/.wine-soapvoice"
WINEARCH=win64 wineboot --init
# 安裝 Python 3.11
winetricks python311
```

### 執行交叉編譯腳本
專案提供 `scripts/wine_package.sh` 腳本：
```bash
cd /path/to/SoapVoice
./scripts/wine_package.sh
```
腳本會自動檢查 Wine、安裝 PyInstaller、執行打包。

### 限制與注意事項
1. **DLL 相依性**：Wine 可能缺少某些 Windows DLL（如 Visual C++ Redistributable），導致打包後的 EXE 無法在真實 Windows 執行。
2. **效能**：Wine 執行 Python 與 PyInstaller 較慢。
3. **Inno Setup**：無法透過 Wine 編譯 Inno Setup 安裝腳本，需真實 Windows 環境。
4. **測試**：產生的 EXE 應在真實 Windows 環境測試，確保功能正常。

### 建議
若可能，仍建議使用真實 Windows 環境（實體機、虛擬機、CI/CD Windows runner）進行打包，以確保相容性。

## 目前限制
- **環境：** 當前在 Linux 環境，無法執行 Windows 專屬編譯器
- **EXE 建置：** Phase 9 Plan 1 在 Linux 環境未完成 PyInstaller 打包，需 Windows 環境
- **自動化腳本：** 僅限 Windows 環境執行，需 PowerShell 5.1+

## 後續步驟
1. 在 Windows 機器上安裝 Python 3.11+ 與專案依賴
2. 執行自動化腳本 `windows_package.ps1` 完成打包與安裝程式編譯
3. 測試 `dist\SoapVoice.exe` 可執行性
4. 測試安裝程式安裝、執行、解除安裝流程
5. 若遇到問題，參考下方問題排除章節

## 問題排除

### PyInstaller 打包問題
- **「Hidden import not found」錯誤：** 已於 spec 檔案修正，若仍有錯誤請手動編輯 `soapvoice.spec` 的 `hiddenimports` 清單
- **缺少 DLL 錯誤：** 請確認系統已安裝 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
- **打包後 EXE 無法啟動：** 檢查 `build\soapvoice\warn-soapvoice.txt` 警告檔案，確認所有必要模組已包含

### Inno Setup 編譯問題
- **iscc 命令未找到：** 確認 Inno Setup 安裝時已勾選「Add to PATH」，或使用完整路徑 `"C:\Program Files (x86)\Inno Setup 6\iscc.exe"`
- **編譯錯誤：** 檢查 `installer\soapvoice.iss` 中的路徑是否正確指向 `dist\SoapVoice.exe`
- **安裝後無法啟動：** 確認 PyInstaller 打包包含所有必要資源（模型、資料檔案）

### 自動化腳本問題
- **PowerShell 執行原則錯誤：** 以管理員身分執行 `Set-ExecutionPolicy RemoteSigned` 或使用 `-ExecutionPolicy Bypass` 參數
- **uv 安裝失敗：** 請手動執行 `pip install uv` 並確認網路連線
- **PyInstaller 打包時間過長：** 正常現象，請耐心等候

---

*最後更新：* 2026-04-13  
*狀態：* 待完成（需 Windows 環境）