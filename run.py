#!/usr/bin/env python3
"""
SoapVoice 自動啟動腳本
- 啟動 API 伺服器於背景
- 自動開啟瀏覽器
- 顯示即時日誌
"""

import os
import sys
import time
import subprocess
import webbrowser
from pathlib import Path

PORT = 8010
HOST = "0.0.0.0"


def check_port():
    """檢查端口是否已被佔用"""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(("localhost", PORT))
    sock.close()
    return result == 0


def start_server():
    """啟動伺服器"""
    project_root = Path(__file__).parent
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
        "--log-level",
        "info",
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)

    return subprocess.Popen(
        cmd,
        cwd=project_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )


def wait_for_server(max_wait=30):
    """等待伺服器啟動"""
    import socket

    start = time.time()
    while time.time() - start < max_wait:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", PORT))
            sock.close()
            if result == 0:
                return True
        except:
            pass
        time.sleep(1)
    return False


def main():
    print("=" * 50)
    print("🩺 SoapVoice 醫療語音轉 SOAP 系統")
    print("=" * 50)

    # 檢查端口
    if check_port():
        print(f"⚠️  端口 {PORT} 已被佔用，嘗試關閉現有程序...")
        os.system(f"fuser -k {PORT}/tcp 2>/dev/null")
        time.sleep(2)

    # 啟動伺服器
    print(f"🚀 啟動伺服器 on http://localhost:{PORT}")
    process = start_server()

    # 等待伺服器就緒
    print("⏳ 等待伺服器就緒...")
    if wait_for_server(30):
        print(f"✅ 伺服器已啟動!")

        # 自動開啟瀏覽器
        url = f"http://localhost:{PORT}/static/test.html"
        print(f"🌐 開啟瀏覽器: {url}")
        webbrowser.open(url)
    else:
        print("❌ 伺服器啟動失敗")
        process.terminate()
        return

    print("\n" + "=" * 50)
    print("📝 即時日誌 (Ctrl+C 停止):")
    print("=" * 50 + "\n")

    try:
        for line in process.stdout:
            print(line, end="")
    except KeyboardInterrupt:
        print("\n\n🛑 停止伺服器...")
        process.terminate()
        process.wait()
        print("✅ 已停止")


if __name__ == "__main__":
    main()
