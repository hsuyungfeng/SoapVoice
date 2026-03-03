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
import contextlib
import os
import time

# 隱藏 ALSA 錯誤訊息
@contextlib.contextmanager
def ignore_stderr():
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(sys.stderr.fileno())
    os.dup2(devnull, sys.stderr.fileno())
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, sys.stderr.fileno())
        os.close(old_stderr)

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
        with ignore_stderr():
            p = pyaudio.PyAudio()
            device_count = p.get_device_count()
        print(f"✓ 找到 {device_count} 個音頻設備")

        # 尋找輸入設備
        input_device = None
        for i in range(device_count):
            try:
                with ignore_stderr():
                    info = p.get_device_info_by_index(i)
                if info.get('maxInputChannels', 0) > 0:
                    print(f"  輸入設備 {i}: {info['name']} (channels: {info['maxInputChannels']})")
                    if input_device is None:
                        input_device = i  # 使用第一個找到的輸入設備
                    # 優先選擇 pipewire/default（支援原生 16kHz，品質更好）
                    name_lower = info.get('name', '').lower()
                    if 'pipewire' in name_lower or info['name'] == 'default':
                        input_device = i
            except:
                pass

        if input_device is None:
            print("⚠ 未找到麥克風設備，跳過音頻串流測試")
            with ignore_stderr():
                p.terminate()
            return False

        print(f"✓ 使用輸入設備：{input_device}")
        with ignore_stderr():
            p.terminate()
    except Exception as e:
        print(f"⚠ PyAudio 初始化失敗：{e}")
        print("  跳過音頻串流測試")
        return False

    try:
        # 使用 ignore_stderr 隱藏 ALSA 噪音
        with ignore_stderr():
            # 連接 WebSocket
            websocket = await websockets.connect(WS_URI, ping_timeout=10, close_timeout=10)
        print("✓ WebSocket 連接成功")

        # 發送客戶端識別資訊（服務器期望）
        print("發送客戶端識別資訊...")
        await websocket.send(json.dumps({"client_id": "test_001"}))

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
        with ignore_stderr():
            p = pyaudio.PyAudio()

        # Whisper 模型需要 16000Hz
        target_rate = 16000

        try:
            with ignore_stderr():
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=target_rate,
                    input=True,
                    frames_per_buffer=1024,
                    input_device_index=input_device
                )
            actual_rate = target_rate
            print(f"✓ PyAudio 串流已初始化（採樣率：{target_rate}Hz）")
        except Exception as e:
            print(f"⚠ {target_rate}Hz 初始化失敗：{e}")
            print("💡 嘗試使用系統預設採樣率並進行轉換...")

            # 使用系統預設採樣率
            with ignore_stderr():
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=48000,  # 使用更常見的採樣率
                    input=True,
                    frames_per_buffer=1024,
                    input_device_index=input_device
                )
            actual_rate = 48000
            print(f"✓ PyAudio 串流已初始化（採樣率：48000Hz，將轉換為 16000Hz）")

        # 實際採樣率已在上方設定
        
        # 設置採樣率轉換
        import numpy as np
        import math

        def resample_audio(data, from_rate, to_rate):
            """採樣率轉換 (16-bit PCM)，優先使用 scipy 抗混疊重採樣"""
            if from_rate == to_rate:
                return data
            audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            try:
                from scipy.signal import resample_poly
                g = math.gcd(from_rate, to_rate)
                up, down = to_rate // g, from_rate // g
                resampled = resample_poly(audio_np, up, down)
            except ImportError:
                # Fallback: 平均抽樣（box filter）提供基本抗混疊
                ratio = from_rate // to_rate
                n = len(audio_np) - len(audio_np) % ratio
                resampled = audio_np[:n].reshape(-1, ratio).mean(axis=1)
            return resampled.clip(-32768, 32767).astype(np.int16).tobytes()
        
        # 根據採樣率調整讀取塊大小，確保每次傳送給伺服器的是 1024 samples (16k)
        read_chunk_size = 1024
        if actual_rate == 48000:
            read_chunk_size = 3072
        
        max_chunks = int(10 * actual_rate / read_chunk_size)
        print(f"📊 設定讀取塊大小：{read_chunk_size}，總塊數：{max_chunks} (採樣率：{actual_rate}Hz)")

        print("🎤 開始錄音... (錄音 10 秒，按 Ctrl+C 可提前停止)")
        print("📊 轉錄結果將顯示如下：")
        print("💡 提示：請對著麥克風**清楚說話**以測試轉錄功能")
        print("💡 例如：'病人胸悶兩天，呼吸困難'")
        print("")

        chunk_count = 0
        transcripts = []  # 存儲所有轉錄結果
        audio_level_sum = 0  # 音頻電平總和
        speech_detected = False  # 是否檢測到語音

        try:
            while chunk_count < max_chunks:
                # 讀取音頻數據
                raw_data = stream.read(read_chunk_size, exception_on_overflow=False)
                
                # 進行採樣率轉換
                data = resample_audio(raw_data, actual_rate, 16000)
                
                # 客戶端音訊正規化 (讓 Whisper 聽清楚)
                audio_np = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                current_max = np.abs(audio_np).max()
                if current_max > 100: # 稍微提高門檻
                    # 嘗試將音量拉到 70% 的最大量程 (0.7 * 32768 = 22938)
                    scale = 22938.0 / current_max
                    # 限制最大增益為 20 倍，支援安靜麥克風場景
                    scale = min(scale, 20.0)
                    audio_np = (audio_np * scale).clip(-32768, 32767).astype(np.int16)
                    data = audio_np.tobytes()

                # 計算音頻電平
                import struct
                audio_level = sum([abs(struct.unpack('<h', raw_data[i:i+2])[0]) for i in range(0, len(raw_data), 2)]) / (len(raw_data) // 2)
                
                audio_level_sum += audio_level

                # 簡單的語音檢測（電平 > 500 認為有語音）
                if audio_level > 500:
                    speech_detected = True

                # 發送音頻塊
                await websocket.send(json.dumps({
                    "type": "chunk",
                    "data": {
                        "audio": base64.b64encode(data).decode('utf-8')
                    }
                }))

                chunk_count += 1

                # 每 5 個塊更新一次 UI
                if chunk_count % 5 == 0:
                    peak_amp = np.abs(audio_np).max()
                    progress = int(chunk_count / max_chunks * 30)
                    bar = "#" * progress + "-" * (30 - progress)
                    speech_indicator = "🎤 語音" if peak_amp > 1000 else "🔇 安靜"
                    print(f"\r  傳送中: {chunk_count:3d}/{max_chunks} [{bar}] 峰值: {peak_amp:5.0f} {speech_indicator}", end="", flush=True)

                # 檢查是否有轉錄結果
                try:
                    result = await asyncio.wait_for(websocket.recv(), timeout=0.01)
                    result_data = json.loads(result)
                    if result_data.get('type') == 'result':
                        transcript = result_data.get('data', {}).get('text', '')
                        if transcript:
                            if not transcripts or transcript != transcripts[-1]:
                                transcripts.append(transcript)
                                print(f"\n  📝 轉錄：{transcript}")
                except asyncio.TimeoutError:
                    pass

        except KeyboardInterrupt:
            print("\n✓ 錄音停止")

        # 計算平均音頻電平
        avg_audio_level = audio_level_sum / max_chunks if max_chunks > 0 else 0
        print(f"\n平均音頻電平：{avg_audio_level:.0f}")

        # 語音檢測報告
        if speech_detected:
            print("✓ 檢測到語音活動")
        else:
            print("⚠ 未檢測到語音活動（電平 < 500）")
            print("💡 請確認麥克風已連接並**對著麥克風清楚說話**")

        if avg_audio_level < 100:
            print("⚠ 音頻電平過低，可能麥克風未正確收音")
            print("💡 請確認麥克風已連接並正確配置")
        elif not speech_detected:
            print("⚠ 有音頻輸入但未檢測到語音")
            print("💡 可能是背景噪音，請對著麥克風清楚說話")
        else:
            print("✓ 麥克風收音正常")

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
        print("\n" + "=" * 50)
        print("📋 最終轉錄結果")
        print("=" * 50)
        final_text = ""
        try:
            while True:
                try:
                    # 取得所有待處理消息，直到收到最終結果
                    msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(msg)
                    if data.get("type") == "result":
                        text = data.get("data", {}).get("text", "")
                        if text:
                            final_text = text
                        if data.get("data", {}).get("is_final"):
                            print(json.dumps(data, indent=2, ensure_ascii=False))
                            break
                except asyncio.TimeoutError:
                    break
        except Exception as e:
            print(f"⚠ 接收結果失敗：{e}")

        # 顯示所有轉錄文本
        if transcripts or final_text:
            if not transcripts and final_text:
                transcripts.append(final_text)
                
            print("\n" + "=" * 50)
            print("📝 所有轉錄文本")
            print("=" * 50)
            for i, t in enumerate(transcripts, 1):
                print(f"{i}. {t}")
            print("=" * 50)

            # 💡 自動呼叫醫療標準化服務 (Medical Translation)
            if final_text:
                print("\n🚀 正在執行醫療語意標準化 (Medical Translation)...")
                import httpx
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            "http://localhost:8000/api/v1/clinical/normalize",
                            json={"text": final_text},
                            timeout=5.0
                        )
                        if response.status_code == 200:
                            norm_data = response.json()
                            print("\n" + "=" * 50)
                            print("🏥 醫療標準化結果 (Standardized Medical Text)")
                            print("=" * 50)
                            print(f"原始文字：{final_text}")
                            print(f"標準英文：{norm_data.get('normalized_text')}")
                            print("-" * 30)
                            print("檢測到的醫療術語：")
                            for term in norm_data.get("terms", []):
                                print(f"  • {term['original']} -> {term['standard']} ({term['category']})")
                            
                            # 儲存結果到檔案
                            result_file = "latest_result.json"
                            with open(result_file, "w", encoding="utf-8") as f:
                                json.dump({
                                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                                    "raw_text": final_text,
                                    "normalization": norm_data
                                }, f, indent=2, ensure_ascii=False)
                            print(f"\n✅ 結果已儲存至：{os.path.abspath(result_file)}")
                            print("=" * 50)
                except Exception as e:
                    print(f"⚠ 標準化服務呼叫失敗: {e}")
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
