#!/usr/bin/env python3
"""
WebSocket 音頻串流診斷腳本
"""

import sys
import asyncio
import websockets
import httpx
from pathlib import Path

# 添加專案根目錄到 Python 路徑
sys.path.insert(0, str(Path(__file__).parent.parent))

print("="*60)
print("SoapVoice WebSocket 音頻串流診斷報告")
print("="*60)

# 1. 檢查 Whisper 模型
print("\n1. Whisper 模型檢查")
print("-" * 60)
from src.asr.whisper_model import WhisperModel
try:
    model = WhisperModel(model_id="large-v3", device="cuda", compute_type="float16")
    print("✓ Whisper large-v3 模型載入成功（CUDA）")
    print(f"  - 設備：cuda")
    print(f"  - 計算類型：float16")
except Exception as e:
    print(f"✗ Whisper 模型載入失敗：{e}")

# 2. 檢查 StreamTranscriber
print("\n2. StreamTranscriber 檢查")
print("-" * 60)
from src.asr.stream_transcriber import StreamTranscriber
try:
    transcriber = StreamTranscriber(whisper_model=model, language=None, task="transcribe")
    print("✓ StreamTranscriber 初始化成功")
except Exception as e:
    print(f"✗ StreamTranscriber 初始化失敗：{e}")

# 3. 測試串流
print("\n3. 串流測試")
print("-" * 60)
try:
    result = transcriber.start_stream()
    print(f"✓ 串流開始：{result}")
except Exception as e:
    print(f"✗ 串流開始失敗：{e}")

# 4. API 服務檢查
print("\n4. API 服務檢查")
print("-" * 60)
try:
    response = httpx.get("http://localhost:8000/health", timeout=5)
    print(f"✓ API 健康檢查：{response.json()}")
except Exception as e:
    print(f"✗ API 健康檢查失敗：{e}")

# 5. WebSocket 檢查
print("\n5. WebSocket 檢查")
print("-" * 60)

async def check_ws():
    try:
        async with websockets.connect("ws://localhost:8000/api/v1/ws/transcribe", close_timeout=5) as ws:
            print("✓ WebSocket 連接成功")
            await ws.send('{"type": "start", "client_id": "test"}')
            try:
                resp = await asyncio.wait_for(ws.recv(), timeout=10)
                print(f"✓ 收到回應：{resp[:100]}...")
            except asyncio.TimeoutError:
                print("⚠ 等待回應超時（Whisper 模型初始化中）")
            return True
    except Exception as e:
        print(f"✗ WebSocket 測試失敗：{e}")
        return False

asyncio.run(check_ws())

print("\n" + "="*60)
print("診斷完成")
print("="*60)
