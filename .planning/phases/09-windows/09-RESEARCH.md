# Phase 9: Windows 打包 - Research

**Researched:** 2026-04-13
**Domain:** Windows 應用程式打包與安裝程式建立
**Confidence:** HIGH (標準工具鏈成熟，官方文檔齊全)

## Summary

本階段目標是將 SoapVoice 醫療語音轉病歷系統打包為 Windows 可執行檔並建立安裝程式，支援離線部署與無訊息安裝。核心技術選用 PyInstaller 生成單一 EXE（all-in-one）並嵌入所有模型與資料檔案，再以 Inno Setup 建立具備管理員權限、桌面捷徑與解除安裝功能的安裝程式。

**Primary recommendation:** 使用 PyInstaller 6.19.0 建立單一 EXE，搭配 Inno Setup 6.3.0 建立安裝程式，實作無訊息安裝參數 (`/SILENT`) 與管理員權限提升。

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- 使用 PyInstaller 生成單一 EXE 可執行檔（all-in-one）
- 支援無訊息安裝（silent install）模式（例如透過命令列參數）
- 管理員權限需求：需要管理員權限以安裝至 Program Files
- 打包策略：單一 EXE 內嵌所有檔案（模型、資料庫、設定檔）

### Claude's Discretion
- 無訊息安裝的具體實作方式（例如使用 PyInstaller 的 --onefile 結合自解壓縮邏輯）
- 安裝目錄的預設路徑（Program Files 下的子目錄命名）
- 桌面與開始功能表捷徑的建立方式
- 解除安裝程式的實作

### Deferred Ideas (OUT OF SCOPE)
無 — 討論範圍保持在此階段內。
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| WIN-01 | 將 SoapVoice 打包為 Windows 單一 EXE 可執行檔 | PyInstaller 標準工作流，spec 檔案配置 |
| WIN-02 | 嵌入所有模型檔案（GGUF, Whisper）與資料庫 | PyInstaller datas 機制，sys._MEIPASS 路徑處理 |
| WIN-03 | 支援無訊息安裝（silent install）模式 | Inno Setup `/SILENT` `/VERYSILENT` 參數 |
| WIN-04 | 安裝至 Program Files 並需管理員權限 | Inno Setup `PrivilegesRequired=admin` |
| WIN-05 | 建立桌面與開始功能表捷徑 | Inno Setup `[Icons]` 區段 |
| WIN-06 | 提供解除安裝程式 | Inno Setup 自動生成 uninstall.exe |
| WIN-07 | 安裝後應用程式可正常執行（包含 GUI 與後端服務） | PyInstaller 隱藏導入處理、DLL 包含、凍結環境偵測 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyInstaller | 6.19.0 (最新穩定版) | 將 Python 應用程式打包為獨立可執行檔 | 最成熟、支援最廣的 Python 打包工具，官方持續維護，支援複雜依賴與資料嵌入 |
| Inno Setup | 6.3.0 (2026-01-10) | 建立 Windows 安裝程式 | 免費、開源、功能完整，支援無訊息安裝、管理員權限、捷徑、解除安裝，被眾多知名專案採用 (VS Code, Git for Windows) |
| UPX | 4.2.0 (可選) | 壓縮可執行檔與 DLL 以減少體積 | PyInstaller 內建支援，可顯著減少 EXE 大小（尤其對 Python 直譯器與標準庫） |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ttkbootstrap | 1.20.2+ | GUI 主題框架 | 需確保 PyInstaller 包含其資源檔案（字型、主題定義） |
| llama-cpp-python | 0.3.20+ | LLM 推理引擎 | 需處理 C 擴展與動態連結庫（.dll）的包含 |
| faster-whisper | 1.0.0+ | ASR 引擎 | 依賴 CTranslate2 與 CUDA/cuDNN（CPU 模式使用 Intel MKL），需包含適當 DLL |
| pyaudio | 0.2.13+ | 音訊錄製 | 需要 PortAudio DLL (`portaudio.dll`) |
| pytesseract | 0.3.13+ | OCR 引擎 | 需要 Tesseract-OCR 二進位檔與語言資料，建議排除安裝程式外以單獨下載 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyInstaller | cx_Freeze, py2exe, Nuitka | PyInstaller 社群最大、hook 系統完善，對複雜依賴（如 PyTorch）支援較佳 |
| Inno Setup | NSIS, WiX, Advanced Installer | Inno Setup 腳本較簡潔，內建 Pascal 腳本引擎，文件完整；NSIS 更輕量但學習曲線較陡 |
| 單一 EXE | 單一目錄（one-folder） | 單一 EXE 更便於分發，但啟動時需解壓縮至臨時目錄（大型模型可能延遲）；單一目錄更適合頻繁更新的場景 |

**Installation:**
```bash
# 安裝 PyInstaller（使用 uv 或 pip）
uv add pyinstaller
# 或
pip install pyinstaller

# Inno Setup 需從官網下載安裝：https://jrsoftware.org/isdl.php
# UPX 可選：https://upx.github.io/
```

## Architecture Patterns

### Recommended Project Structure
```
soapvoice/
├── build/                    # PyInstaller 建置暫存目錄
├── dist/                     # 輸出目錄（EXE 與支援檔案）
├── installer/                # Inno Setup 腳本與資源
│   ├── soapvoice.iss         # 主要安裝腳本
│   ├── license.txt           # 安裝程式授權文字
│   └── banner.bmp            # 安裝程式橫幅圖片（可選）
├── models/                   # 模型檔案（GGUF, Whisper）
├── data/                     # 資料庫與其他資料
└── src/                      # 原始碼
```

### Pattern 1: PyInstaller Spec 檔案配置
**What:** 使用 `.spec` 檔案定義打包配置，而非命令列參數，以確保可重現性與複雜設定。
**When to use:** 專案包含大量資料檔案、隱藏導入、或需要自訂 hook。
**Example:**
```python
# soapvoice.spec（簡化版本）
a = Analysis(
    ['src/gui/desktop_app.py'],  # 進入點
    pathex=[ROOT_DIR],
    binaries=[
        # 手動加入必要 DLL
        ('C:\\Python311\\Lib\\site-packages\\pyaudio\\portaudio.dll', '.'),
    ],
    datas=[
        (str(ROOT_DIR / 'models'), 'models'),
        (str(ROOT_DIR / 'data'), 'data'),
        (str(ROOT_DIR / '.env'), '.'),
    ],
    hiddenimports=[
        'llama_cpp', 'llama_cpp.llama', 'llama_cpp._internals',
        'faster_whisper', 'ctranslate2',
        'ttkbootstrap', 'tkinter', 'PIL',
        'pyaudio', 'pyperclip', 'mss',
        'sentence_transformers', 'chromadb',
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'torch'],  # 移除未使用的大型套件
    noarchive=False,
)
```

### Pattern 2: 凍結環境偵測與路徑處理
**What:** 在應用程式啟動時檢查 `sys.frozen` 與 `sys._MEIPASS`，正確定位嵌入資源與使用者資料目錄。
**When to use:** 任何使用 PyInstaller `--onefile` 打包的應用程式。
**Example:**
```python
import sys
import os
from pathlib import Path

def get_resource_path(relative_path):
    """取得打包資源的絕對路徑"""
    if getattr(sys, 'frozen', False):
        # 如果是打包後的執行檔
        base_path = getattr(sys, '_MEIPASS', Path(sys.executable).parent)
    else:
        base_path = Path(__file__).parent.parent
    return Path(base_path) / relative_path

def get_user_data_dir():
    """取得使用者資料目節錄（可寫入）"""
    app_name = "SoapVoice"
    if os.name == "nt":
        base = Path(os.getenv("APPDATA")) / app_name
    else:
        base = Path.home() / f".{app_name}"
    base.mkdir(parents=True, exist_ok=True)
    return base

# 使用範例
model_path = get_resource_path("models/qwen2.5-7b-instruct-q4_k_m.gguf")
recording_dir = get_user_data_dir() / "recordings"
```

### Pattern 3: Inno Setup 腳本基礎結構
**What:** 使用 Inno Setup Script (ISS) 定義安裝程式行為，包括檔案複製、捷徑建立、註冊表項與無訊息安裝支援。
**When to use:** 需要建立專業 Windows 安裝程式的任何專案。
**Example:**
```innosetup
; soapvoice.iss
[Setup]
AppName=SoapVoice
AppVersion=0.8.0
DefaultDirName={pf}\SoapVoice
DefaultGroupName=SoapVoice
UninstallDisplayIcon={app}\SoapVoice.exe
Compression=lzma2/ultra64
SolidCompression=yes
OutputDir=installer\
PrivilegesRequired=admin
; 無訊息安裝參數
SetupLogging=yes

[Files]
Source: "dist\SoapVoice.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "models\*"; DestDir: "{app}\models"; Flags: ignoreversion recursesubdirs
Source: "data\*"; DestDir: "{app}\data"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\SoapVoice"; Filename: "{app}\SoapVoice.exe"
Name: "{group}\Uninstall SoapVoice"; Filename: "{uninstallexe}"
Name: "{commondesktop}\SoapVoice"; Filename: "{app}\SoapVoice.exe"

[Run]
Filename: "{app}\SoapVoice.exe"; Description: "Launch SoapVoice"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\SoapVoice"
```

### Anti-Patterns to Avoid
- **直接使用 `__file__` 定位資源**：在凍結環境中 `__file__` 可能指向暫存目錄，應改用 `sys._MEIPASS`。
- **將大型模型打包進單一 EXE 而不測試啟動時間**：數 GB 的模型會使解壓縮時間長達數十秒，應考慮部分外部化或提供進度提示。
- **忽略 DLL 相依性**：`pyaudio`、`llama_cpp`、`faster-whisper` 依賴特定 DLL，必須明確包含在 `binaries` 中或確保系統已安裝。
- **使用絕對路徑引用使用者目錄**：應使用 Windows API（如 `SHGetFolderPath`）或環境變數（`APPDATA`）以支援多使用者環境。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 執行檔壓縮 | 自行實作解壓縮邏輯 | PyInstaller 內建 onefile 解壓縮 | 處理邊界情況（防毒軟體干擾、暫存目錄權限、清理）複雜且易出錯 |
| 安裝程式 GUI | 手寫 Win32 API 安裝介面 | Inno Setup（或 NSIS） | 提供標準安裝精靈、多語言支援、回滾機制、解除安裝生成 |
| DLL 相依性掃描 | 手動追蹤 DLL 依賴 | PyInstaller 自動分析 + 手動補充 | 複雜的遞迴依賴（如 CUDA、MKL）容易遺漏，導致執行時崩潰 |
| 無訊息安裝參數解析 | 自訂命令列解析 | Inno Setup `/SILENT` `/VERYSILENT` `/DIR=` | 標準參數已被廣泛支援，且與 Windows 安裝慣例一致 |
| 捷徑建立 | 直接操作 Shell 物件 | Inno Setup `[Icons]` 區段 | 處理所有 Shell 資料夾（開始功能表、桌面、快速啟動）與使用者/全域模式 |

**Key insight:** Windows 打包生態系統已高度工具化，自訂實作不僅耗時且容易引入相容性問題，尤其涉及 UAC、防毒軟體、暫存檔案清理等系統層級行為。

## Common Pitfalls

### Pitfall 1: 隱藏導入（Hidden Imports）缺失
**What goes wrong:** 應用程式在打包後執行時出現 `ModuleNotFoundError`，尤其是動態導入的模組（如 `llama_cpp` 的子模組）。
**Why it happens:** PyInstaller 靜態分析無法偵測 `importlib.import_module()` 或 `__import__()` 動態載入的模組。
**How to avoid:** 在 spec 檔案的 `hiddenimports` 中明確列出所有動態導入的模組，並使用 `pyi‑modulegraph` 工具檢查覆蓋率。
**Warning signs:** 打包過程出現「missing module named ...」警告。

### Pitfall 2: DLL 遺漏或版本衝突
**What goes wrong:** 應用程式啟動時崩潰或出現「The code execution cannot proceed because XXX.dll was not found」錯誤。
**Why it happens:** PyInstaller 未自動抓取某些 C 擴展的相依 DLL（如 `portaudio.dll`、`ctranslate2` 的 MKL DLL）。
**How to avoid:** 使用 `depends.exe` 或 `dumpbin` 分析 EXE 相依性，手動將缺失 DLL 加入 `binaries` 清單，並確保使用與 Python 環境一致的版本（如 VS Redistributable）。
**Warning signs:** 打包後 EXE 在本機運行正常，但在乾淨 Windows 虛擬機中失敗。

### Pitfall 3: 防毒軟體誤報與阻擋
**What goes wrong:** 打包後的 EXE 被 Windows Defender 或其他防毒軟體標記為威脅並隔離。
**Why it happens:** PyInstaller 產生的自解壓縮執行檔行為類似打包器（packer），觸發啟發式偵測。
**How to avoid:** 使用 UPX 壓縮可能加重誤報，可考慮不加壓縮；對正式分發版本進行數位簽章；提交至防毒軟體廠商白名單。
**Warning signs:** 使用者回報「檔案被刪除」或「無法下載」。

### Pitfall 4: 大型模型解壓縮時間過長
**What goes wrong:** 單一 EXE 啟動時需將數 GB 模型解壓至臨時目錄，導致啟動延遲 30 秒以上。
**Why it happens:** PyInstaller onefile 在每次啟動時都會解壓縮所有內嵌檔案。
**How to avoid:** 考慮將模型外部化為獨立檔案，僅在首次執行時解壓縮至使用者目錄；或顯示進度提示；或改用單一目錄（one-folder）分發。
**Warning signs:** 使用者抱怨啟動緩慢，工作管理員顯示高磁碟活動。

### Pitfall 5: 管理員權限與使用者資料夾權限
**What goes wrong:** 應用程式安裝至 `Program Files` 後無法寫入設定檔或記錄檔（權限不足）。
**Why it happens:** `Program Files` 受 Windows UAC 保護，一般使用者無寫入權限。
**How to avoid:** 將可寫入資料（設定、記錄、暫存檔）儲存於使用者目錄（如 `%APPDATA%\\SoapVoice`），並在應用程式啟動時偵測並遷移現有資料。
**Warning signs:** 應用程式崩潰或功能異常，事件檢視器顯示「Access denied」。

## Code Examples

### 打包命令列範例
```bash
# 產生 spec 檔案（初次）
pyi-makespec --onefile --name SoapVoice src/gui/desktop_app.py

# 使用 spec 建置
pyinstaller SoapVoice.spec --clean

# 建置單一目錄版本（測試用）
pyinstaller --onedir --name SoapVoice src/gui/desktop_app.py
```

### 檢查遺失模組
```python
# 使用 PyInstaller 工具檢查隱藏導入
from PyInstaller.utils.hooks import collect_submodules
hidden = collect_submodules('llama_cpp')
print(hidden)
```

### Inno Setup 無訊息安裝參數
```batch
# 完全無訊息安裝（不顯示任何視窗）
SoapVoiceSetup.exe /SILENT /SUPPRESSMSGBOXES

# 指定安裝目錄
SoapVoiceSetup.exe /DIR="C:\\Program Files\\SoapVoice" /SILENT

# 包含除錯日誌
SoapVoiceSetup.exe /LOG="install.log" /SILENT
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| py2exe (Python 2 era) | PyInstaller (Python 3) | 2010 年代後期 | 更好的依賴分析、跨平台支援、活躍社群 |
| NSIS 為主 | Inno Setup 與 NSIS 並存 | 2010 年代 | Inno Setup 提供更現代化的腳本語言與內建功能 |
| 手動複製 DLL | PyInstaller 自動分析 + 手動補充 | 持續演進 | 減少遺漏，但複雜 C 擴展仍需手動介入 |
| 單一 EXE 內嵌所有資源 | 混合式（EXE + 外部資源包） | 近年趨勢 | 平衡啟動速度與分發便利性，適用於大型機器學習模型 |

**Deprecated/outdated:**
- **py2exe**：不再活躍維護，不支援 Python 3.8+ 新特性。
- **cx_Freeze**：仍維護但社群規模較小，對複雜依賴支援較弱。
- **手寫安裝程式**：專業工具已成熟，自訂實作成本過高。

## Open Questions

1. **pyaudio DLL 的處理方式**
   - What we know: `pyaudio` 依賴 `portaudio.dll`，通常位於 `site-packages\\pyaudio` 目錄。
   - What's unclear: 是否需要同時包含 `libportaudio-2.dll` 或其他變體，以及如何在 spec 中正確引用。
   - Recommendation: 實作測試腳本，在乾淨 Windows 環境驗證錄音功能，並根據錯誤訊息補充 DLL。

2. **faster-whisper 的 CPU 模式 DLL 相依性**
   - What we know: faster-whisper 依賴 CTranslate2，後者使用 Intel MKL 或 OpenBLAS。
   - What's unclear: 在 Windows CPU 模式下需要哪些具體的 DLL 檔案，以及如何取得它們。
   - Recommendation: 檢視 `ctranslate2` 套件安裝目錄，收集所有 `.dll` 檔案，並在 spec 的 `binaries` 中加入。

3. **數位簽章與防毒軟體白名單**
   - What we know: 未簽章的 EXE 容易被防毒軟體誤報。
   - What's unclear: 專案預算是否允許購買程式碼簽章憑證，或是否採用免費替代方案（如 SignPath）。
   - Recommendation: 若為內部使用可暫時跳過簽章；若為公開分發，建議申請 [Open Source Code Signing](https://ssl.com/code-signing-certificate/open-source/) 或使用社區簽章服務。

4. **模型版權與分發合法性**
   - What we know: GGUF 模型通常為開源授權（如 Llama 2, Qwen），但需確認特定模型的分發條款。
   - What's unclear: 是否可將模型檔案嵌入商業安裝程式中分發。
   - Recommendation: 檢查各模型檔案的授權文件，必要時在安裝程式加入授權同意頁面。

## Sources

### Primary (HIGH confidence)
- [PyInstaller Manual](https://pyinstaller.org/en/stable/) - 官方文檔，涵蓋 spec 檔案、hiddenimports、資料檔案、凍結環境偵測。
- [Inno Setup Documentation](https://jrsoftware.org/ishelp.php) - 官方說明文件，包含無訊息安裝參數、權限設定、捷徑建立。

### Secondary (MEDIUM confidence)
- [RealPython: PyInstaller Guide](https://realpython.com/pyinstaller-python/) - 實用教學，涵蓋常見陷阱與解決方案。
- [Stack Overflow: PyInstaller tags](https://stackoverflow.com/questions/tagged/pyinstaller) - 社群問答，針對特定錯誤的解決方法。

### Tertiary (LOW confidence)
- 個人經驗與專案現有 spec 檔案 - 需進一步驗證在 SoapVoice 專案中的適用性。

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - PyInstaller 與 Inno Setup 為業界標準，官方文檔完整。
- Architecture: MEDIUM - 模式來自官方文件與社群最佳實踐，但需針對專案特定依賴調整。
- Pitfalls: MEDIUM - 基於常見問題與社群回饋，但某些 DLL 相依性需實測驗證。

**Research date:** 2026-04-13
**Valid until:** 2026-05-13（Windows 打包工具變動較慢，30 天有效）
