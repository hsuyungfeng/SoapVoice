#!/usr/bin/env python3
"""簡單啟動後端伺服器並等待健康檢查"""

import sys
import time
import subprocess
import signal
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def kill_existing(port=8010):
    """殺死佔用端口的進程"""
    import subprocess

    try:
        # 使用 lsof 尋找 PID
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        if result.stdout.strip():
            pids = result.stdout.strip().split()
            for pid in pids:
                os.kill(int(pid), signal.SIGTERM)
            time.sleep(2)
    except Exception:
        pass


def main():
    port = 8010
    kill_existing(port)

    # 啟動 uvicorn
    cmd = [
        "uv",
        "run",
        "uvicorn",
        "src.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--log-level",
        "warning",
    ]
    print(f"🚀 啟動後端伺服器: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # 等待啟動
    import requests

    max_attempts = 30
    for i in range(max_attempts):
        time.sleep(2)
        # 檢查進程是否存活
        if proc.poll() is not None:
            stdout, _ = proc.communicate()
            print(f"❌ 伺服器進程已退出: {proc.returncode}")
            print(stdout[:500])
            sys.exit(1)

        try:
            resp = requests.get(f"http://127.0.0.1:{port}/health", timeout=2)
            if resp.status_code == 200:
                print(f"✅ 後端伺服器啟動成功，端口 {port}")
                # 寫入 PID 檔案
                with open(project_root / "server.pid", "w") as f:
                    f.write(str(proc.pid))
                # 保持執行
                while True:
                    time.sleep(1)
        except requests.exceptions.ConnectionError:
            print(f"⏳ 等待伺服器啟動... ({i + 1}/{max_attempts})")

    print("❌ 伺服器啟動超時")
    proc.terminate()
    sys.exit(1)


if __name__ == "__main__":
    main()
