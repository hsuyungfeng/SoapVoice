#!/usr/bin/env python3
"""
WebSocket 調試腳本
"""

import asyncio
import websockets
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

WS_URI = "ws://localhost:8000/api/v1/ws/transcribe"


async def debug_test():
    """調試 WebSocket 連接"""
    print("="*60)
    print("WebSocket 調試測試")
    print("="*60)
    
    try:
        async with websockets.connect(WS_URI, close_timeout=10) as ws:
            print("\n✓ WebSocket 連接成功")
            
            # 等待連接確認
            print("\n等待連接確認...")
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                print(f"✓ 收到：{msg}")
            except asyncio.TimeoutError:
                print("⚠ 超時")
            
            # 發送 start
            print("\n發送 start 訊息...")
            await ws.send(json.dumps({"type": "start", "client_id": "debug"}))
            
            # 等待回應
            print("等待回應（最多 30 秒）...")
            for i in range(30):
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1)
                    print(f"✓ 收到 [{i}s]: {msg}")
                    
                    # 檢查是否為 stream_started
                    data = json.loads(msg)
                    if data.get('type') == 'status' and data.get('data', {}).get('status') == 'stream_started':
                        print("\n✓ 串流已開始！測試成功")
                        break
                except asyncio.TimeoutError:
                    print(f".", end="", flush=True)
            
            # 發送 end
            print("\n\n發送 end 訊息...")
            await ws.send(json.dumps({"type": "end"}))
            
            print("\n✓ 測試完成")
            return True
            
    except Exception as e:
        print(f"\n✗ 測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(debug_test())
    sys.exit(0 if result else 1)
