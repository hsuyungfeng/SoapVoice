#!/usr/bin/env python3
"""SoapVoice 後端伺服器啟動腳本（處理端口衝突）"""

import socket
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_port_available(port=8000):
    """檢查端口是否可用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result != 0  # 0 表示端口已被佔用
    except Exception:
        return True


def find_available_port(start_port=8000, max_attempts=10):
    """尋找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        if check_port_available(port):
            return port
    return None


def start_server(port=8010):
    """啟動後端伺服器"""
    print(f"🚀 啟動 SoapVoice 後端 API (端口: {port})...")

    try:
        import uvicorn
        from src.main import app
    except ImportError as e:
        print(f"❌ 缺少必要套件: {e}")
        print("請執行: uv sync")
        return None

    try:
        # 啟動伺服器
        _host = os.environ.get("HOST", "0.0.0.0")
        config = uvicorn.Config(
            "src.main:app", host=_host, port=port, reload=False, log_level="info"
        )
        server = uvicorn.Server(config)

        # 在背景執行緒中啟動
        import threading

        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        # 等待伺服器啟動
        time.sleep(3)

        # 檢查伺服器是否正常運行
        import requests

        try:
            response = requests.get(f"http://127.0.0.1:{port}/health", timeout=5)
            if response.status_code == 200:
                print(f"✅ 後端 API 啟動成功: http://127.0.0.1:{port}")
                return port
            else:
                print(f"❌ 後端 API 啟動失敗: {response.status_code}")
                return None
        except requests.exceptions.ConnectionError:
            print("❌ 無法連接到後端 API")
            return None

    except Exception as e:
        print(f"❌ 伺服器啟動失敗: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """主函數"""
    print("=" * 50)
    print("🔧 SoapVoice 後端伺服器啟動工具")
    print("=" * 50)

    # 檢查端口 8010 是否可用
    if not check_port_available(8010):
        print("⚠️ 端口 8010 已被佔用，尋找可用端口...")
        port = find_available_port(8010)
        if port is None:
            print("❌ 找不到可用端口 (8000-8010)")
            print("💡 請關閉其他佔用端口的程式")
            return
        print(f"✅ 找到可用端口: {port}")
    else:
        port = 8000
        print(f"✅ 端口 {port} 可用")

    # 啟動伺服器
    actual_port = start_server(port)

    if actual_port:
        print("\n" + "=" * 50)
        print(f"🎉 後端伺服器運行中")
        print(f"📡 網址: http://127.0.0.1:{actual_port}")
        print(f"🔍 健康檢查: http://127.0.0.1:{actual_port}/health")
        print("=" * 50)
        print("\n💡 按 Ctrl+C 停止伺服器")

        # 保持程式運行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 停止伺服器")
    else:
        print("\n❌ 伺服器啟動失敗")


if __name__ == "__main__":
    main()
