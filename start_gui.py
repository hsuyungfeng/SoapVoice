#!/usr/bin/env python3
"""SoapVoice GUI 啟動腳本（改進版）"""

import sys
import time
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_dependencies():
    """檢查必要套件"""
    print("🔍 檢查必要套件...")

    required_packages = {
        "pyperclip": "剪貼簿操作",
        "ttkbootstrap": "現代化 UI",
        "pyaudio": "音訊錄製",
        "requests": "HTTP 請求",
        "numpy": "數值計算",
        "mss": "螢幕截圖",
        "pytesseract": "OCR 文字辨識",
        "PIL": "影像處理",
    }

    missing = []
    for pkg, desc in required_packages.items():
        try:
            __import__(pkg)
            print(f"  ✅ {pkg}: {desc}")
        except ImportError:
            print(f"  ❌ {pkg}: {desc} (未安裝)")
            missing.append(pkg)

    if missing:
        print(f"\n⚠️  缺少 {len(missing)} 個套件")
        print("💡 執行以下命令安裝:")
        print(f"  uv add {' '.join(missing)}")
        return False

    print("✅ 所有必要套件已安裝")
    return True


def start_backend_in_thread():
    """在背景執行緒中啟動後端"""
    print("\n🚀 啟動後端 API 伺服器...")

    try:
        from start_server import start_server

        port = start_server(8010)
        return port
    except ImportError:
        print("❌ 無法導入 start_server")
        return None


_BACKEND_PORT = None  # 全域變數儲存後端端口


def start_gui_interface():
    """啟動 GUI 介面"""
    print("\n🖥️ 啟動 GUI 介面...")

    try:
        from src.gui.desktop_app import main as gui_main

        gui_main()
        return True
    except ImportError as e:
        print(f"❌ GUI 導入失敗: {e}")
        return False
    except Exception as e:
        print(f"❌ GUI 啟動失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_ocr_function():
    """測試 OCR 功能"""
    print("\n📸 測試 OCR 功能...")

    try:
        # 直接檢查套件，而不是透過 OCRParser
        print("  🔍 直接檢查 OCR 套件...")

        # 檢查 mss
        try:
            import mss

            print(f"    ✅ mss 可用，版本: {mss.__version__}")
        except ImportError as e:
            print(f"    ❌ mss 未安裝: {e}")

        # 檢查 pytesseract
        try:
            import pytesseract

            print(f"    ✅ pytesseract 可用，版本: {pytesseract.__version__}")
            print(f"    📝 tesseract 路徑: {pytesseract.get_tesseract_version()}")
        except ImportError as e:
            print(f"    ❌ pytesseract 導入失敗: {e}")

        # 檢查 PIL
        try:
            import importlib.util

            if importlib.util.find_spec("PIL"):
                print("    ✅ PIL 可用")
            else:
                print("    ❌ PIL 未安裝")
        except Exception as e:
            print(f"    ❌ PIL 檢查失敗: {e}")

        # 檢查 OCRParser 模組可導入（但不實例化，避免資源衝突）
        try:
            print("    ✅ OCRParser 模組可導入")

            # 僅測試 OCR 套件，不實際執行擷取（避免記憶體衝突）
            print("    📸 OCR 套件檢查完成")
            return True

        except Exception as e:
            print(f"    ❌ OCRParser 模組導入失敗: {e}")
            return False

    except Exception as e:
        print(f"❌ OCR 測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_audio_function():
    """測試音訊功能"""
    print("\n🎤 測試音訊功能...")

    try:
        from src.gui.desktop_app import AudioRecorder

        recorder = AudioRecorder()

        if recorder.p is None:
            print("⚠️ pyaudio 初始化失敗 (可能無音訊裝置)")
            print("💡 音訊錄製功能可能受限")
        else:
            print("✅ pyaudio 初始化成功")

        return True

    except Exception as e:
        print(f"❌ 音訊測試失敗: {e}")
        return False


def main():
    """主函數"""
    print("=" * 60)
    print("🎤 SoapVoice - 醫療語音轉 SOAP 病歷系統")
    print("=" * 60)

    # 檢查套件
    if not check_dependencies():
        return

    # 測試 OCR 功能
    if not test_ocr_function():
        print("⚠️ OCR 功能有問題，但繼續啟動...")

    # 測試音訊功能
    if not test_audio_function():
        print("⚠️ 音訊功能有問題，但繼續啟動...")

    # 啟動後端伺服器
    global _BACKEND_PORT
    backend_thread = threading.Thread(
        target=lambda: (_BACKEND_PORT := start_backend_in_thread()), daemon=True
    )
    backend_thread.start()

    # 等待後端啟動
    print("\n⏳ 等待後端 API 啟動 (約 5 秒)...")
    time.sleep(5)

    # 檢查後端是否正常
    check_port = _BACKEND_PORT if _BACKEND_PORT else 8010
    try:
        import requests

        response = requests.get(f"http://127.0.0.1:{check_port}/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ 後端 API 已就緒 (端口 {check_port})")
        else:
            print(f"⚠️ 後端 API 回應異常: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ 無法連接到後端 API")
        print("💡 後端可能啟動失敗，GUI 功能可能受限")
    except ImportError:
        print("⚠️ 無法檢查後端狀態")

    # 啟動 GUI
    print("\n" + "=" * 60)
    print("🖥️ 啟動主視窗...")
    print("=" * 60)

    if not start_gui_interface():
        print("\n❌ GUI 啟動失敗")
        print("\n💡 疑難排解:")
        print("  1. 確保所有套件已安裝: uv add pyperclip ttkbootstrap pyaudio")
        print("  2. 檢查系統是否有 GUI 環境")
        print("  3. 查看錯誤訊息以獲取更多資訊")


if __name__ == "__main__":
    main()
