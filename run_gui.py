#!/usr/bin/env python3
"""SoapVoice GUI 啟動腳本"""

import os
import sys
import threading
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def start_backend():
    """啟動後端 API 伺服器"""
    print("🚀 啟動 SoapVoice 後端 API...")

    # 檢查是否已安裝必要套件
    try:
        import uvicorn
        from src.main import app
    except ImportError as e:
        print(f"❌ 缺少必要套件: {e}")
        print("請執行: uv sync")
        return

    # 啟動伺服器
    import uvicorn

    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")


def start_gui():
    """啟動 GUI 介面"""
    print("🖥️ 啟動 SoapVoice GUI...")

    try:
        from src.gui.desktop_app import main as gui_main

        gui_main()
    except ImportError as e:
        print(f"❌ GUI 啟動失敗: {e}")
        print("請確保已安裝必要套件:")
        print("  uv add pyperclip ttkbootstrap pyaudio")
        return
    except Exception as e:
        print(f"❌ GUI 錯誤: {e}")
        import traceback

        traceback.print_exc()


def main():
    """主函數"""
    print("=" * 50)
    print("🎤 SoapVoice - 醫療語音轉 SOAP 病歷系統")
    print("=" * 50)

    # 檢查環境
    print("🔍 檢查環境...")

    # 檢查必要套件
    required_packages = ["pyperclip", "ttkbootstrap", "pyaudio"]
    missing = []
    for pkg in required_packages:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        print(f"❌ 缺少必要套件: {', '.join(missing)}")
        print("請執行以下命令安裝:")
        print(f"  uv add {' '.join(missing)}")
        return

    print("✅ 環境檢查通過")

    # 啟動後端伺服器（在背景執行緒）
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    # 等待後端啟動
    print("⏳ 等待後端 API 啟動...")
    time.sleep(3)

    # 啟動 GUI
    start_gui()


if __name__ == "__main__":
    main()
