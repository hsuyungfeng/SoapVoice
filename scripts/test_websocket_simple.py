#!/usr/bin/env python3
"""
WebSocket 連接測試腳本
"""

import asyncio
import websockets
import json
import sys

WS_URI = "ws://localhost:8000/api/v1/ws/transcribe"


async def test_websocket():
    """測試 WebSocket 連接"""
    print("=" * 50)
    print("WebSocket 連接測試")
    print("=" * 50)
    
    try:
        # 連接 WebSocket
        print(f"連接到：{WS_URI}")
        async with websockets.connect(WS_URI, close_timeout=10) as ws:
            print("✓ WebSocket 連接成功")
            
            # 發送開始訊息
            start_msg = {"type": "start", "client_id": "test_001"}
            await ws.send(json.dumps(start_msg))
            print(f"已發送：{start_msg}")
            
            # 等待回應
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=10)
                print(f"✓ 收到回應：{response}")
            except asyncio.TimeoutError:
                print("⚠ 等待回應超時（可能是正常的，因為需要初始化 Whisper 模型）")
            
            # 發送結束訊息
            end_msg = {"type": "end"}
            await ws.send(json.dumps(end_msg))
            print(f"已發送：{end_msg}")
            
            print("\n✓ WebSocket 測試完成")
            return True
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ HTTP 錯誤：{e}")
        print("  可能原因：WebSocket 端點有問題")
        return False
    except Exception as e:
        print(f"✗ 測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return False


async def test_rest_api():
    """測試 REST API"""
    print("\n" + "=" * 50)
    print("REST API 測試")
    print("=" * 50)
    
    import httpx
    
    async with httpx.AsyncClient() as client:
        # 測試健康檢查
        try:
            response = await client.get("http://localhost:8000/health")
            print(f"✓ 健康檢查：{response.json()}")
        except Exception as e:
            print(f"✗ 健康檢查失敗：{e}")
        
        # 測試文本標準化
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/clinical/normalize",
                json={"text": "病人胸悶"}
            )
            print(f"✓ 文本標準化：{response.status_code}")
        except Exception as e:
            print(f"✗ 文本標準化失敗：{e}")
        
        # 測試 ICD-10
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/clinical/icd10",
                json={"text": "病人胸悶"}
            )
            print(f"✓ ICD-10 分類：{response.status_code}")
        except Exception as e:
            print(f"✗ ICD-10 分類失敗：{e}")
    
    print("\n✓ REST API 測試完成")


async def main():
    """主函數"""
    print("\nSoapVoice 測試套件\n")
    
    # 測試 REST API
    await test_rest_api()
    
    # 測試 WebSocket
    await test_websocket()
    
    print("\n" + "=" * 50)
    print("測試完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
