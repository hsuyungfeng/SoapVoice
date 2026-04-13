#!/bin/bash
# SoapVoice Wine 跨平台打包腳本
#
# 此腳本嘗試在 Linux 環境下使用 Wine 進行 Windows 交叉編譯。
# 前提：已安裝 Wine 並設定好 Windows Python 環境（例如透過 winetricks）。
#
# 警告：Wine 交叉編譯複雜且可能失敗，建議直接使用 Windows 環境進行打包。

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WINE_PYTHON="${WINE_PYTHON:-wine python}"
WINE_PYINSTALLER="${WINE_PYINSTALLER:-wine pyinstaller}"

echo "=== SoapVoice Wine 交叉編譯 ==="
echo "專案根目錄: $PROJECT_ROOT"

# 檢查 Wine 是否安裝
if ! command -v wine &> /dev/null; then
    echo "錯誤: Wine 未安裝。請先安裝 Wine。"
    echo "Ubuntu/Debian: sudo apt install wine"
    echo "Fedora: sudo dnf install wine"
    echo "或參考 https://wiki.winehq.org/Download"
    exit 1
fi

# 檢查 Wine Python 是否可用
if ! $WINE_PYTHON --version &> /dev/null; then
    echo "錯誤: Wine Python 不可用。請確保 Wine 已安裝 Python。"
    echo "可嘗試: winetricks python311"
    echo "或手動在 Wine 環境安裝 Python 與 PyInstaller。"
    exit 1
fi

# 檢查專案依賴是否安裝（透過 uv）
echo "檢查專案依賴..."
cd "$PROJECT_ROOT"
if ! command -v uv &> /dev/null; then
    echo "uv 未安裝，嘗試安裝..."
    pip install uv
fi

# 安裝 PyInstaller 到 Wine Python 環境
echo "安裝 PyInstaller 至 Wine Python 環境..."
$WINE_PYTHON -m pip install pyinstaller

# 執行 PyInstaller dry-run 驗證 spec
echo "執行 PyInstaller dry-run 驗證..."
$WINE_PYTHON -m PyInstaller --dry-run soapvoice.spec
if [ $? -ne 0 ]; then
    echo "警告: dry-run 失敗，可能需要調整 spec 或安裝額外依賴。"
    exit 1
fi

echo "開始打包..."
$WINE_PYTHON -m PyInstaller --clean soapvoice.spec

if [ -f "$PROJECT_ROOT/dist/SoapVoice.exe" ]; then
    EXE_SIZE=$(stat -c%s "$PROJECT_ROOT/dist/SoapVoice.exe")
    echo "打包成功！SoapVoice.exe 大小: $((EXE_SIZE / 1024 / 1024)) MB"
else
    echo "打包可能失敗，未找到 dist/SoapVoice.exe。"
    exit 1
fi

echo "=== 完成 ==="
echo "產生的 EXE: $PROJECT_ROOT/dist/SoapVoice.exe"
echo "注意：此 EXE 在 Wine 環境下可能仍需要額外 DLL，建議在真實 Windows 環境測試。"