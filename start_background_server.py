#!/usr/bin/env python3
"""啟動後端伺服器於背景，用於功能測試"""

import sys
import time
import threading
import socket
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn
from src.main import app


def check_port_available(port=8010):
    """檢查端口是否可用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        return result != 0
    except Exception:
        return True


def start_server(port=8010):
    """啟動後端伺服器"""
    print(f"🚀 啟動 SoapVoice 後端 API (端口: {port})...")

    try:
        config = uvicorn.Config(
            "src.main:app", host="127.0.0.1", port=port, reload=False, log_level="warning"
        )
        server = uvicorn.Server(config)

        # 在背景執行緒中啟動
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
    port = 8010
    if not check_port_available(port):
        print(f"⚠️ 端口 {port} 已被佔用，嘗試關閉現有程序...")
        import os
        import signal
        import subprocess

        # 使用 lsof 找到佔用端口的 PID
        try:
            result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
            if result.stdout.strip():
                pids = result.stdout.strip().split()
                for pid in pids:
                    os.kill(int(pid), signal.SIGTERM)
                time.sleep(2)
        except Exception:
            pass

    actual_port = start_server(port)
    if actual_port:
        print(f"\n🎉 後端伺服器運行中，端口 {actual_port}")
        print("💡 按 Ctrl+C 停止伺服器")
        try:
            # 保持主執行緒運行
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 停止伺服器")
    else:
        print("\n❌ 伺服器啟動失敗")
        sys.exit(1)


if __name__ == "__main__":
    main()
