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

    # 檢查 PyAudio
    try:
        import pyaudio
        p = pyaudio.PyAudio()
        device_count = p.get_device_count()
        print(f"✓ 找到 {device_count} 個音頻設備")

        # 尋找輸入設備
        input_device = None
        for i in range(device_count):
            try:
                info = p.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    input_device = i
                    print(f"✓ 找到輸入設備：{info['name']}")
                    break
            except:
                pass

        if input_device is None:
            print("⚠ 未找到麥克風設備，跳過音頻串流測試")
            p.terminate()
            return False

        p.terminate()
    except Exception as e:
        print(f"⚠ PyAudio 初始化失敗：{e}")
        print("  跳過音頻串流測試")
        return False

    websocket = None
    stream = None
    p = None

    try:
        # 連接 WebSocket
        websocket = await websockets.connect(WS_URI, ping_timeout=10, close_timeout=10)
        print("✓ WebSocket 連接成功")

        # 等待連接確認
        print("等待連接確認...")
        try:
            conn_resp = await asyncio.wait_for(websocket.recv(), timeout=10)
            print(f"✓ 連接確認：{conn_resp[:100]}")
        except asyncio.TimeoutError:
            print("⚠ 等待連接確認超時")

        # 發送開始訊息
        start_msg = json.dumps({
            "type": "start",
            "client_id": "test_001"
        })
        print(f"發送：{start_msg}")
        await websocket.send(start_msg)

        # 等待 stream_started 回應（重要！）
        print("等待 stream_started 回應（Whisper 模型載入中，可能需要 10-20 秒）...")
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=60)
            print(f"✓ 服務器回應：{response}")

            # 檢查是否為 stream_started
            resp_data = json.loads(response)
            resp_type = resp_data.get('type')
            resp_status = resp_data.get('data', {}).get('status')

            # 支援兩種格式：{"type":"stream_started"} 或 {"type":"status","data":{"status":"stream_started"}}
            # 如果收到的是 "connected"，繼續等待 "stream_started"
            if resp_status == 'connected':
                print("⚠ 收到 connected，繼續等待 stream_started...")
                response = await asyncio.wait_for(websocket.recv(), timeout=60)
                print(f"✓ 服務器回應：{response}")
                resp_data = json.loads(response)
                resp_type = resp_data.get('type')
                resp_status = resp_data.get('data', {}).get('status')

            if resp_type == 'stream_started' or resp_status == 'stream_started':
                print("✓ 串流已開始")
            else:
                print(f"⚠ 預期 stream_started，但收到：type={resp_type}, status={resp_status}")
                # 繼續執行，因為可能是正常的
        except asyncio.TimeoutError:
            print("✗ 等待 stream_started 超時（60 秒）")
            return False

        # 初始化 PyAudio
        p = pyaudio.PyAudio()
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )

        print("🎤 開始錄音... (錄音 10 秒，按 Ctrl+C 可提前停止)")
        print("📊 轉錄結果將顯示如下：")

        chunk_count = 0
        max_chunks = 150  # 增加錄音長度（約 10 秒，150 * 1024 / 16000 ≈ 9.6 秒）
        transcripts = []  # 存儲所有轉錄結果

        try:
            while chunk_count < max_chunks:
                # 讀取音頻數據
                data = stream.read(1024, exception_on_overflow=False)

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
                    print(f"  已發送 {chunk_count}/{max_chunks} 個音頻塊...")

                # 檢查是否有轉錄結果
                try:
                    result = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=0.1
                    )
                    result_data = json.loads(result)
                    transcript = result_data.get('data', {}).get('text', '')
                    if transcript:
                        print(f"  📝 轉錄：{transcript}")
                        transcripts.append(transcript)
                except asyncio.TimeoutError:
                    pass

        except KeyboardInterrupt:
            print("\n✓ 錄音停止")

        print("\n" + "=" * 50)
        print("正在結束錄音...")

        # 發送結束訊息
        try:
            await websocket.send(json.dumps({
                "type": "end"
            }))
            print("✓ 已發送結束訊息")
        except Exception as e:
            print(f"⚠ 發送結束訊息失敗：{e}")

        # 接收最終結果
        print("等待最終轉錄結果...")
        try:
            result = await asyncio.wait_for(websocket.recv(), timeout=30)
            print(f"\n{'='*50}")
            print("📋 最終轉錄結果")
            print("="*50)
            print(f"{result}")
            print("="*50)
        except asyncio.TimeoutError:
            print("⚠ 等待最終結果超時")
        except Exception as e:
            print(f"⚠ 接收最終結果失敗：{e}")

        # 顯示所有轉錄文本
        if transcripts:
            print("\n" + "=" * 50)
            print("📝 所有轉錄文本")
            print("=" * 50)
            for i, t in enumerate(transcripts, 1):
                print(f"{i}. {t}")
            print("=" * 50)
        else:
            print("\n⚠ 未收到轉錄文本（可能是正常的，Whisper 需要足夠的音頻數據）")

        print("\n✓ 音頻串流測試完成")
        return True

    except websockets.exceptions.ConnectionClosed as e:
        print(f"⚠ WebSocket 連接已關閉：{e}")
        return False
    except Exception as e:
        print(f"✗ 音頻串流測試失敗：{e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 清理資源
        print("\n正在清理資源...")

        if stream:
            try:
                stream.stop_stream()
                stream.close()
                print("✓ 音頻流已關閉")
            except:
                pass

        if p:
            try:
                p.terminate()
                print("✓ PyAudio 已終止")
            except:
                pass

        if websocket:
            try:
                await websocket.close()
                print("✓ WebSocket 已關閉")
            except:
                pass

        print("✓ 資源清理完成")


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
