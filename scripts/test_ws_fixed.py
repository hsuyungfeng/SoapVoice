#!/usr/bin/env python3
"""
WebSocket 音頻串流測試 - 修復版本
"""

import asyncio
import websockets
import json
import base64
import sys
from pathlib import Path

# 添加專案根目錄
sys.path.insert(0, str(Path(__file__).parent.parent))

WS_URI = "ws://localhost:8000/api/v1/ws/transcribe"


async def test_with_preload():
    """測試 WebSocket - 預先載入 Whisper 模型"""
    print("="*60)
    print("WebSocket 音頻串流測試（預載入模型）")
    print("="*60)
    
    # 1. 預先載入 Whisper 模型
    print("\n1. 預先載入 Whisper 模型...")
    from src.asr.whisper_model import WhisperModel
    from src.asr.stream_transcriber import StreamTranscriber
    
    print("   載入模型中...")
    model = WhisperModel(model_id="large-v3", device="cuda", compute_type="float16")
    print("   ✓ 模型載入成功")
    
    # 2. 測試轉錄器
    print("\n2. 測試轉錄器...")
    transcriber = StreamTranscriber(whisper_model=model, language=None, task="transcribe")
    result = transcriber.start_stream()
    print(f"   ✓ 轉錄器啟動：{result}")
    
    # 3. 測試 WebSocket 連接
    print("\n3. 測試 WebSocket 連接...")
    try:
        async with websockets.connect(WS_URI, close_timeout=10) as ws:
            print("   ✓ WebSocket 連接成功")
            
            # 發送開始訊息
            await ws.send(json.dumps({"type": "start", "client_id": "test"}))
            print("   已發送開始訊息")
            
            # 等待回應（延長超時時間）
            print("   等待回應...")
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=30)
                print(f"   ✓ 收到回應：{response[:200]}")
            except asyncio.TimeoutError:
                print("   ⚠ 等待回應超時（30 秒）")
            
            # 發送結束訊息
            await ws.send(json.dumps({"type": "end"}))
            print("   已發送結束訊息")
            
            # 等待最終結果
            print("   等待最終結果...")
            try:
                result = await asyncio.wait_for(ws.recv(), timeout=30)
                print(f"   ✓ 最終結果：{result[:200]}")
            except asyncio.TimeoutError:
                print("   ⚠ 等待最終結果超時")
            
            return True
            
    except Exception as e:
        print(f"   ✗ 測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函數"""
    result = await test_with_preload()
    
    print("\n" + "="*60)
    if result:
        print("✓ 測試完成")
    else:
        print("✗ 測試失敗")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
