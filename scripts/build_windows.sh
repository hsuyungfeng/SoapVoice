#!/bin/bash
# SoapVoice Windows EXE 建置腳本
# 在 Windows 環境執行

set -e

echo "========================================"
echo "SoapVoice Windows EXE 建置腳本"
echo "========================================"

# 檢查環境
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    echo "OS: Windows"
else
    echo "警告: 此腳本預計在 Windows 環境執行"
fi

# 1. 安裝依賴
echo "[1/5] 安裝依賴..."
uv sync
uv sync --group dev

# 2. 清理舊建置
echo "[2/5] 清理舊建置..."
rm -rf build dist
rm -f SoapVoice.spec

# 3. 建立 spec 檔案
echo "[3/5] 建立 spec 檔案..."
cat > SoapVoice.spec << 'SPEC_EOF'
# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from pathlib import Path

block_cipher = None
ROOT_DIR = Path(SPECPATH)

a = Analysis(
    ["src/main.py"],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=[
        (str(ROOT_DIR / "static"), "static"),
        (str(ROOT_DIR / "medical.db"), "."),
    ],
    hiddenimports=[
        "fastapi", "uvicorn", "starlette",
        "pydantic", "pydantic_settings",
        "sentence_transformers", "chromadb",
        "httpx", "numpy", "torch",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="SoapVoice",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, upx_exclude=[],
    name="SoapVoice",
)
SPEC_EOF

# 4. 執行建置
echo "[4/5] 執行 PyInstaller 建置..."
pyinstaller SoapVoice.spec --clean --noconfirm

# 5. 完成
echo "[5/5] 建置完成！"
echo ""
echo "產出位置: dist/SoapVoice/"
echo "執行檔: dist/SoapVoice/SoapVoice.exe"
echo ""
echo "使用方式:"
echo "  1. 將整個 SoapVoice 資料夾複製到 Windows"
echo "  2. 執行 SoapVoice.exe"
echo "  3. 開啟瀏覽器 http://localhost:8000"
echo ""
echo "注意: 需要 Ollama 運行才能使用 LLM 功能"
echo "========================================"