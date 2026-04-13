# Wine 交叉編譯指南

## 概述

本文件描述如何在 Linux 環境下使用 Wine 進行 SoapVoice Windows 可執行檔交叉編譯，作為無法取得 Windows 環境時的替代方案。

## 快速開始

1. 安裝 Wine（參見下文）
2. 設定 Wine Python 環境
3. 執行自動化腳本：
   ```bash
   ./scripts/wine_package.sh
   ```

## 詳細步驟

### 1. 安裝 Wine

#### Ubuntu/Debian
```bash
sudo apt update
sudo apt install wine
```

#### Fedora
```bash
sudo dnf install wine
```

#### 透過 Snap（無需 sudo）
```bash
snap install wine-platform-5-stable --classic
```

### 2. 設定 Wine Python 環境

建議使用獨立的 Wine prefix 避免污染系統 Wine 設定：

```bash
export WINEPREFIX="$HOME/.wine-soapvoice"
export WINEARCH=win64
wineboot --init
```

安裝 winetricks 工具：
```bash
sudo apt install winetricks
```

安裝 Python 3.11：
```bash
winetricks python311
```

驗證 Wine Python：
```bash
wine python --version
```

### 3. 準備專案環境

確保專案依賴已安裝（uv）：
```bash
pip install uv
cd /path/to/SoapVoice
uv sync
```

### 4. 執行交叉編譯

專案提供自動化腳本 `scripts/wine_package.sh`：
```bash
./scripts/wine_package.sh
```

或手動步驟：
```bash
# 安裝 PyInstaller 到 Wine Python 環境
wine python -m pip install pyinstaller

# 驗證 spec 檔案
wine python -m PyInstaller --dry-run soapvoice.spec

# 執行打包
wine python -m PyInstaller --clean soapvoice.spec
```

### 5. 驗證輸出

腳本成功後，產生的 EXE 位於 `dist/SoapVoice.exe`。請注意：
- 檔案大小應大於 50MB（包含模型）
- 此 EXE 仍需在真實 Windows 環境測試功能

## 已知限制

### 技術限制
1. **DLL 相依性**：Wine 可能缺少 Windows 系統 DLL（如 `msvcp140.dll`, `vcruntime140.dll`），需手動安裝 Visual C++ Redistributable 至 Wine prefix。
2. **效能**：Wine 執行 Python 與 PyInstaller 較慢，打包時間可能延長 2-3 倍。
3. **相容性**：某些 Python C 擴展可能無法在 Wine 下正確編譯或執行。

### 功能限制
1. **Inno Setup 編譯**：無法透過 Wine 編譯 Inno Setup 安裝腳本（`iscc` 為 Windows 原生工具）。
2. **安裝程式測試**：無法測試安裝流程與捷徑建立。
3. **防毒軟體誤報**：Wine 產生的 EXE 可能更容易觸發防毒軟體誤報。

## 疑難排解

### Wine Python 無法執行
```bash
# 檢查 Wine 設定
winecfg
# 重新建立 prefix
rm -rf "$HOME/.wine-soapvoice"
```

### PyInstaller 找不到模組
確保 Wine Python 環境已安裝專案依賴：
```bash
wine python -m pip install -r requirements.txt
```

### EXE 在 Windows 無法啟動
1. 檢查 Dependency Walker 或 `dumpbin /dependents` 確認缺失 DLL
2. 安裝 Visual C++ Redistributable 至目標 Windows 系統
3. 考慮使用 `--onedir` 模式（單一目錄）而非 `--onefile`，以簡化 DLL 包含

## 建議

### 短期方案
- 使用 Wine 交叉編譯產生 EXE，在 Windows 虛擬機中測試
- 將 Wine 編譯步驟整合至 CI/CD（如 GitHub Actions 的 ubuntu-latest + Wine）

### 長期方案
- 設定 Windows CI runner（GitHub Actions Windows runner, AppVeyor, Azure Pipelines）
- 建立 Windows 虛擬機快照，定期執行打包驗證

## 相關資源

- [WineHQ Wiki](https://wiki.winehq.org/Main_Page)
- [Winetricks](https://wiki.winehq.org/Winetricks)
- [PyInstaller Cross-Compilation](https://pyinstaller.readthedocs.io/en/stable/cross-compilation.html)

---

*文件版本：1.0*  
*最後更新：2026-04-13*  
*狀態：實驗性*