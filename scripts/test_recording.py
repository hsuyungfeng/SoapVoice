#!/usr/bin/env python3
"""
語音錄製測試腳本

測試 SoapVoice 的語音錄製和轉錄功能
"""

import asyncio
import websockets
import json
import base64
import pyaudio
import sys

# 音頻配置
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024

# WebSocket 配置
WS_URI = "ws://localhost:8000/api/v1/ws/transcribe"


async def test_websocket_connection():
    """測試 WebSocket 連接"""
    print("=" * 50)
    print("測試 WebSocket 連接")
    print("=" * 50)

    try:
        async with websockets.connect(WS_URI, close_timeout=5) as websocket:
            print("✓ WebSocket 連接成功")

            # 發送開始訊息
            await websocket.send(json.dumps({
                "type": "start",
                "client_id": "test_001"
            }))
            print("已發送開始訊息")

            # 等待回應（設置超時）
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"✓ 服務器回應：{response}")
            except asyncio.TimeoutError:
                print("⚠ 等待回應超時（可能正在初始化 Whisper 模型）")

            # 發送結束訊息
            await websocket.send(json.dumps({
                "type": "end"
            }))
            print("已發送結束訊息")

            return True
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ WebSocket 連接失敗：HTTP {e.status_code}")
        return False
    except Exception as e:
        print(f"✗ WebSocket 連接失敗：{e}")
        return False


async def test_audio_streaming():
    """測試音頻串流"""
    print("\n" + "=" * 50)
    print("測試音頻串流")
    print("=" * 50)
    
    try:
        async with websockets.connect(WS_URI) as websocket:
            # 發送開始訊息
            await websocket.send(json.dumps({
                "type": "start",
                "client_id": "test_001"
            }))
            
            response = await websocket.recv()
            print(f"✓ 開始錄音：{response}")
            
            # 初始化 PyAudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
            print("🎤 開始錄音... (按 Ctrl+C 停止)")
            
            chunk_count = 0
            try:
                while True:
                    # 讀取音頻數據
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    
                    # 發送音頻塊
                    await websocket.send(json.dumps({
                        "type": "chunk",
                        "data": {
                            "audio": base64.b64encode(data).decode('utf-8')
                        }
                    }))
                    
                    chunk_count += 1
                    
                    # 每 10 個塊顯示一次進度
                    if chunk_count % 10 == 0:
                        print(f"  已發送 {chunk_count} 個音頻塊...")
                    
                    # 檢查是否有轉錄結果
                    try:
                        result = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=0.1
                        )
                        print(f"  轉錄結果：{result}")
                    except asyncio.TimeoutError:
                        pass
                        
            except KeyboardInterrupt:
                print("\n✓ 錄音停止")
            
            # 發送結束訊息
            await websocket.send(json.dumps({
                "type": "end"
            }))
            
            # 接收最終結果
            result = await websocket.recv()
            print(f"✓ 最終轉錄結果：{result}")
            
            # 清理
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            return True
            
    except Exception as e:
        print(f"✗ 音頻串流測試失敗：{e}")
        return False


async def test_text_input():
    """測試文字輸入（模擬語音轉錄結果）"""
    print("\n" + "=" * 50)
    print("測試文字輸入（模擬語音轉錄）")
    print("=" * 50)
    
    test_cases = [
        {
            "name": "門診病歷",
            "text": "病人說他胸悶兩天，還有點喘。血壓 140/90，心跳每分 80 下。"
        },
        {
            "name": "急診病歷",
            "text": "病人跌倒後右膝蓋紅腫疼痛。X 光檢查無骨折。"
        },
        {
            "name": "複雜病歷",
            "text": "病人主訴頭痛三天，伴隨噁心嘔吐。血壓 160/100，有高血壓病史。"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n測試：{test_case['name']}")
        print(f"輸入：{test_case['text']}")
        
        # 測試文本標準化
        import httpx
        
        async with httpx.AsyncClient() as client:
            # 測試標準化
            response = await client.post(
                "http://localhost:8000/api/v1/clinical/normalize",
                json={"text": test_case['text']}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✓ 標準化結果：{result.get('normalized_text', 'N/A')}")
            
            # 測試 ICD-10 分類
            response = await client.post(
                "http://localhost:8000/api/v1/clinical/icd10",
                json={"text": test_case['text']}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✓ ICD-10 代碼：{result.get('primary_code', 'N/A')}")
            
            # 測試 SOAP 分類
            response = await client.post(
                "http://localhost:8000/api/v1/clinical/classify/soap",
                params={"text": test_case['text']}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✓ SOAP 分類：{result.get('category', 'N/A')}")
        
        print("-" * 50)


async def main():
    """主函數"""
    print("\n" + "=" * 50)
    print("SoapVoice 錄音測試")
    print("=" * 50)

    # 選擇測試模式
    print("\n請選擇測試模式:")
    print("1. WebSocket 連接測試")
    print("2. 音頻串流測試（需要麥克風）")
    print("3. 文字輸入測試（模擬）")
    print("4. 完整測試")

    choice = input("\n輸入選項 (1-4): ").strip()

    if choice == "1":
        await test_websocket_connection()
    elif choice == "2":
        await test_audio_streaming()
    elif choice == "3":
        await test_text_input()
    elif choice == "4":
        print("\n執行完整測試...")

        # 測試 1: WebSocket 連接
        print("\n" + "=" * 50)
        print("測試 1: WebSocket 連接")
        print("=" * 50)
        ws_result = await test_websocket_connection()
        if ws_result:
            print("✓ WebSocket 連接測試通過\n")
        else:
            print("⚠ WebSocket 連接測試失敗（可繼續其他測試）\n")

        # 測試 2: 文字輸入
        print("=" * 50)
        print("測試 2: 文字輸入測試")
        print("=" * 50)
        await test_text_input()

        # 測試 3: 音頻串流（可選）
        run_audio_test = input("\n是否執行音頻串流測試？(y/n): ").strip().lower()
        if run_audio_test == "y":
            await test_audio_streaming()
    else:
        print("無效選項")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✓ 測試中斷")
        sys.exit(0)
