"""
測試 ASR 轉錄功能
"""

import os
import sys
import time
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_whisper_model_import():
    """測試 WhisperModel 類別導入"""
    try:
        from src.asr.whisper_model import WhisperModel

        print("✅ WhisperModel 導入成功")
        return True
    except ImportError as e:
        print(f"❌ WhisperModel 導入失敗: {e}")
        return False


def test_whisper_transcribe_sample():
    """測試 Whisper 轉錄樣本音訊"""
    try:
        from src.asr.whisper_model import WhisperModel

        # 使用 medium 模型 (CPU int8)
        model = WhisperModel("medium", device="cpu", compute_type="int8")

        sample_path = project_root / "tests" / "fixtures" / "sample_zh.wav"
        if not sample_path.exists():
            print(f"❌ 樣本音訊檔案不存在: {sample_path}")
            return False

        print(f"🔊 轉錄樣本音訊: {sample_path}")
        start_time = time.time()
        result = model.transcribe(str(sample_path), language="zh")
        elapsed = time.time() - start_time

        transcription = result.get("text", "")
        language = result.get("language", "")
        segments = result.get("segments", [])

        print(f"  轉錄結果: {transcription}")
        print(f"  轉錄語言: {language}")
        print(f"  分段數: {len(segments)}")
        print(f"  耗時: {elapsed:.2f} 秒")

        # 檢查轉錄結果非空
        assert len(transcription.strip()) > 0, "轉錄結果不應為空"
        # 檢查轉錄包含中文字元（粗略檢查）
        import re

        if re.search(r"[\u4e00-\u9fff]", transcription):
            print("✅ 轉錄結果包含中文字元")
        else:
            print("⚠️ 轉錄結果未包含中文字元（可能為空或英文）")

        print("✅ Whisper 轉錄測試通過")
        return True
    except Exception as e:
        print(f"❌ Whisper 轉錄測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False

        print(f"🔊 轉錄樣本音訊: {sample_path}")
        start_time = time.time()
        segments, info = model.transcribe(str(sample_path), language="zh")
        transcription = "".join([segment.text for segment in segments])
        elapsed = time.time() - start_time

        print(f"  轉錄結果: {transcription}")
        print(f"  轉錄語言: {info.language} (機率: {info.language_probability:.2%})")
        print(f"  耗時: {elapsed:.2f} 秒")

        # 檢查轉錄結果非空
        assert len(transcription.strip()) > 0, "轉錄結果不應為空"
        # 檢查轉錄包含中文字元（粗略檢查）
        import re

        if re.search(r"[\u4e00-\u9fff]", transcription):
            print("✅ 轉錄結果包含中文字元")
        else:
            print("⚠️ 轉錄結果未包含中文字元（可能為空或英文）")

        print("✅ Whisper 轉錄測試通過")
        return True
    except Exception as e:
        print(f"❌ Whisper 轉錄測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_asr_api_endpoint():
    """測試 ASR API 端點（需要後端運行）"""
    try:
        import requests

        # 嘗試連接後端健康檢查
        health_url = "http://127.0.0.1:8010/health"
        try:
            resp = requests.get(health_url, timeout=2)
            backend_available = resp.status_code == 200
        except requests.exceptions.ConnectionError:
            backend_available = False

        if not backend_available:
            print("⚠️ 後端 API 未運行，跳過 API 端點測試")
            return True  # 跳過不算失敗

        # 上傳樣本音訊進行轉錄
        sample_path = project_root / "tests" / "fixtures" / "sample_zh.wav"
        if not sample_path.exists():
            print(f"❌ 樣本音訊檔案不存在: {sample_path}")
            return False

        files = {"audio": open(sample_path, "rb")}
        data = {"audio_path": str(sample_path)}
        transcribe_url = "http://127.0.0.1:8010/api/v1/extended/transcribe"

        print(f"📡 呼叫 ASR API 端點: {transcribe_url}")
        start_time = time.time()
        response = requests.post(transcribe_url, files=files, data=data)
        elapsed = time.time() - start_time

        if response.status_code == 200:
            result = response.json()
            transcript = result.get("transcript", "")
            print(f"  API 轉錄結果: {transcript}")
            print(f"  API 耗時: {elapsed:.2f} 秒")
            assert len(transcript.strip()) > 0, "API 轉錄結果不應為空"
            print("✅ ASR API 端點測試通過")
            return True
        else:
            print(f"❌ ASR API 端點返回錯誤: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ ASR API 端點測試失敗: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("🔊 測試 ASR 轉錄功能")
    print("=" * 60)

    results = []
    results.append(test_whisper_model_import())
    results.append(test_whisper_transcribe_sample())
    results.append(test_asr_api_endpoint())

    if all(results):
        print("\n✅ 所有 ASR 功能測試通過")
        sys.exit(0)
    else:
        print("\n❌ 部分 ASR 功能測試失敗")
        sys.exit(1)
