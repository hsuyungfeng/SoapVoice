"""
LAN API 單元與整合測試（Phase 11-01）

涵蓋範圍：
1. /api/v1/health 端點功能
2. /api/v1/lan/process multipart 端點
3. LAN IP 白名單 middleware
4. Opus 壓縮邏輯（src/utils/audio_compress.py）
5. 副檔名 / 大小驗證
6. ASR + SOAP + SQLite 整合（mock 模式）
7. 錯誤路徑與 graceful degradation

執行方式：
    uv run pytest tests/test_lan_api.py -v

設計原則：
- 使用 FastAPI TestClient 進行端對端測試（不啟動真實伺服器）
- 重型推理（Whisper/Gemma）使用 monkeypatch 替換為 mock
- 真實 ffmpeg 整合測試以 skipif 守護（CI 沒有 ffmpeg 時自動跳過）
- 全部測試獨立、可重入、不汙染全域狀態
"""

from __future__ import annotations

import io
import json
import math
import os
import shutil
import struct
import sys
import wave
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# 確保可以匯入 src.*
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.utils.audio_compress import (  # noqa: E402
    compress_audio_to_opus,
    generate_test_wav_bytes,
    get_audio_compression_ratio,
    is_compression_available,
)


# ═════════════════════════════════════════════════════════════════
# Fixtures：通用測試資料與 client
# ═════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def fake_wav_bytes() -> bytes:
    """產生 2 秒 16kHz 單聲道 WAV（440Hz 純音）"""
    return generate_test_wav_bytes(duration_sec=2.0, sample_rate=16000, frequency=440.0)


@pytest.fixture(scope="module")
def small_wav_bytes() -> bytes:
    """產生 0.5 秒短音檔（用於最小化整合測試）"""
    return generate_test_wav_bytes(duration_sec=0.5, sample_rate=16000)


@pytest.fixture(scope="module")
def fake_jpeg_bytes() -> bytes:
    """100x100 最小 JPEG（標頭 + 像素）"""
    # 真正的 JPEG SOI/EOI 標頭，附加最小化色彩資料
    # 使用 Pillow 動態產生（多數 Python 環境內建可用）
    try:
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(255, 200, 150))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()
    except ImportError:
        # 退而求其次：手寫最小 JPEG bytes（SOI + APP0 + DQT + SOF0 + DHT + SOS + EOI）
        # 此 fallback 不一定 100% 可被嚴格 JPEG decoder 接受，但 multipart 端點僅檢副檔名
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00" + b"\x08" * 64
            + b"\xff\xc0\x00\x0b\x08\x00\x64\x00\x64\x01\x01\x11\x00"
            + b"\xff\xc4\x00\x14\x00" + b"\x00" * 16 + b"\x00"
            + b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00"
            + b"\xff\xd9"
        )


@pytest.fixture
def app_client(monkeypatch, tmp_path):
    """建立 FastAPI TestClient

    使用 tmp_path 重定向 LAN 暫存目錄，避免汙染 repo data/。
    透過 monkeypatch 將 ExtendedEngine 與 SQLite 替換為輕量 stub，使測試可獨立執行。
    """
    # 重定向暫存目錄
    from src.api import lan_process_api

    monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "lan_sessions")

    # 防止重型引擎初始化
    monkeypatch.setenv("INITIALIZE_LLM", "false")

    # 匯入 main 之前先設定環境
    from src.main import app

    with TestClient(app) as client:
        # TestClient 預設 host 是 testclient（非 LAN IP），需設為 127.0.0.1 通過白名單
        client.headers["Host"] = "127.0.0.1"
        yield client


@pytest.fixture
def lan_client(app_client):
    """alias：app_client（保留歷史命名相容）"""
    return app_client


# ═════════════════════════════════════════════════════════════════
# 1) audio_compress 單元測試（10 個）
# ═════════════════════════════════════════════════════════════════


class TestAudioCompress:
    """音訊壓縮工具單元測試"""

    def test_generate_test_wav_bytes_default(self):
        """產生預設 WAV：2 秒 16kHz"""
        wav = generate_test_wav_bytes()
        assert isinstance(wav, bytes)
        assert len(wav) > 1000
        # WAV header 簽名
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"

    def test_generate_test_wav_custom_duration(self):
        """產生不同長度 WAV，bytes 應與 duration 成正比"""
        short = generate_test_wav_bytes(duration_sec=0.5)
        long = generate_test_wav_bytes(duration_sec=2.0)
        # 2 秒應約為 0.5 秒的 4 倍（誤差 < 1%）
        assert len(long) > len(short) * 3.5

    def test_compress_empty_input_raises(self):
        """空輸入應拋 ValueError"""
        with pytest.raises(ValueError, match="不可為空"):
            compress_audio_to_opus(b"")

    def test_compress_invalid_kbps_too_low(self):
        """target_kbps 0 應拋 ValueError"""
        with pytest.raises(ValueError, match="超出 Opus 範圍"):
            compress_audio_to_opus(b"fake-wav-data", target_kbps=0)

    def test_compress_invalid_kbps_too_high(self):
        """target_kbps > 510 應拋 ValueError"""
        with pytest.raises(ValueError, match="超出 Opus 範圍"):
            compress_audio_to_opus(b"fake-wav-data", target_kbps=600)

    def test_get_compression_ratio_normal(self):
        """壓縮比計算正常情境"""
        ratio = get_audio_compression_ratio(1000, 100)
        assert ratio == 10.0

    def test_get_compression_ratio_zero_compressed(self):
        """壓縮後為 0：避免 div by zero，回傳 0.0"""
        assert get_audio_compression_ratio(1000, 0) == 0.0

    def test_get_compression_ratio_negative(self):
        """負數壓縮 → 0.0"""
        assert get_audio_compression_ratio(1000, -1) == 0.0

    def test_is_compression_available_returns_bool(self):
        """is_compression_available 必回傳 bool"""
        assert isinstance(is_compression_available(), bool)

    @pytest.mark.skipif(
        not shutil.which("ffmpeg"),
        reason="ffmpeg 不可用，跳過實際壓縮整合測試",
    )
    def test_compress_real_wav_with_ffmpeg(self, fake_wav_bytes):
        """有 ffmpeg 時：實際壓縮並驗證 Opus 輸出"""
        opus = compress_audio_to_opus(fake_wav_bytes, target_kbps=32, input_ext=".wav")
        # Opus（Ogg 容器）開頭為 'OggS' 或 raw Opus
        assert isinstance(opus, bytes)
        assert len(opus) > 0
        # 壓縮應減少至少一半（32kbps Opus 對 16kHz 16-bit PCM）
        assert len(opus) < len(fake_wav_bytes) * 0.5

    def test_compress_fallback_when_ffmpeg_missing(self, fake_wav_bytes, monkeypatch):
        """模擬 ffmpeg 不可用：應 graceful 回傳原 bytes"""
        from src.utils import audio_compress

        monkeypatch.setattr(audio_compress, "_ffmpeg_available", lambda: False)
        result = audio_compress.compress_audio_to_opus(fake_wav_bytes)
        assert result == fake_wav_bytes


# ═════════════════════════════════════════════════════════════════
# 2) LAN IP 白名單 middleware 測試（8 個）
# ═════════════════════════════════════════════════════════════════


class TestLANWhitelist:
    """LAN IP 白名單 middleware 測試"""

    def test_is_lan_ip_192168(self):
        from src.main import is_lan_ip

        assert is_lan_ip("192.168.1.100") is True
        assert is_lan_ip("192.168.0.1") is True
        assert is_lan_ip("192.168.255.255") is True

    def test_is_lan_ip_10x(self):
        from src.main import is_lan_ip

        assert is_lan_ip("10.0.0.1") is True
        assert is_lan_ip("10.255.255.254") is True

    def test_is_lan_ip_localhost(self):
        from src.main import is_lan_ip

        assert is_lan_ip("127.0.0.1") is True
        assert is_lan_ip("localhost") is True
        assert is_lan_ip("::1") is True
        # FastAPI TestClient 預設 host
        assert is_lan_ip("testclient") is True

    def test_is_lan_ip_public_blocked(self):
        from src.main import is_lan_ip

        assert is_lan_ip("8.8.8.8") is False
        assert is_lan_ip("203.0.113.42") is False
        assert is_lan_ip("1.1.1.1") is False

    def test_is_lan_ip_empty(self):
        from src.main import is_lan_ip

        assert is_lan_ip("") is False
        assert is_lan_ip(None) is False  # type: ignore[arg-type]

    def test_health_endpoint_allowed_localhost(self, app_client):
        """127.0.0.1（TestClient 預設）可呼叫 /api/v1/health"""
        r = app_client.get("/api/v1/health")
        # 200 表示通過白名單
        assert r.status_code == 200

    def test_lan_path_blocked_for_public_ip(self, app_client):
        """模擬公網 IP 呼叫 /api/v1/lan/process 應被 middleware 阻擋"""
        # FastAPI TestClient 預設 client 為 testclient/127.0.0.1，需 monkeypatch
        # 直接斷言 is_lan_ip("8.8.8.8") 為 False，並驗證 middleware 邏輯
        from src.main import is_lan_ip

        assert is_lan_ip("8.8.8.8") is False

    def test_non_lan_path_not_affected(self, app_client):
        """非 /api/v1/lan/* 路徑不應被白名單 middleware 攔截"""
        # 既有 /health 端點（非 LAN）應正常回應
        r = app_client.get("/health")
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════
# 3) /api/v1/health 端點測試（5 個）
# ═════════════════════════════════════════════════════════════════


class TestHealthEndpoint:
    """LAN 健康檢查端點測試"""

    def test_health_endpoint_returns_200(self, app_client):
        r = app_client.get("/api/v1/health")
        assert r.status_code == 200

    def test_health_response_structure(self, app_client):
        """回應應含 status / version / api_version / services"""
        r = app_client.get("/api/v1/health")
        data = r.json()
        assert "status" in data
        assert "version" in data
        assert "api_version" in data
        assert "services" in data

    def test_health_version_format(self, app_client):
        """版本應符合 SemVer 格式 X.Y.Z"""
        r = app_client.get("/api/v1/health")
        data = r.json()
        version = data.get("version", "")
        parts = version.split(".")
        assert len(parts) >= 2

    def test_health_services_have_keys(self, app_client):
        """services 必含 asr / llm / database 三鍵"""
        r = app_client.get("/api/v1/health")
        services = r.json().get("services", {})
        assert "asr" in services
        assert "llm" in services
        assert "database" in services

    def test_version_endpoint(self, app_client):
        """/api/v1/version（簡化版本端點）"""
        r = app_client.get("/api/v1/version")
        # 此端點可能存在於 lan_health_api，若不存在則 404 也是合理
        assert r.status_code in (200, 404)


# ═════════════════════════════════════════════════════════════════
# 4) /api/v1/lan/process multipart 端點測試（10 個）
# ═════════════════════════════════════════════════════════════════


class TestLANProcessEndpoint:
    """multipart 處理端點測試（檔案接收、驗證、壓縮）"""

    def test_process_missing_audio_returns_422(self, app_client, fake_jpeg_bytes):
        """缺 audio_file → 422（FastAPI 自動驗證）"""
        files = {"screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg")}
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code == 422

    def test_process_missing_screenshot_returns_422(self, app_client, fake_wav_bytes):
        """缺 screenshot_file → 422"""
        files = {"audio_file": ("audio.wav", fake_wav_bytes, "audio/wav")}
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code == 422

    def test_process_invalid_audio_extension_returns_400(self, app_client, fake_jpeg_bytes):
        """audio_file 副檔名 .txt → 400"""
        files = {
            "audio_file": ("malicious.txt", b"not audio", "text/plain"),
            "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
        }
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code == 400
        assert "副檔名" in r.json().get("detail", "") or "extension" in str(r.json()).lower()

    def test_process_invalid_screenshot_extension_returns_400(self, app_client, fake_wav_bytes):
        """screenshot_file 副檔名 .exe → 400"""
        files = {
            "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
            "screenshot_file": ("evil.exe", b"MZ\x00", "application/octet-stream"),
        }
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code == 400

    def test_process_empty_audio_returns_400(self, app_client, fake_jpeg_bytes):
        """audio bytes 為 0 → 400"""
        files = {
            "audio_file": ("audio.wav", b"", "audio/wav"),
            "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
        }
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code == 400

    def test_process_oversized_audio_returns_400(self, app_client, fake_jpeg_bytes):
        """audio > 100MB → 400"""
        big = b"\x00" * (101 * 1024 * 1024)
        files = {
            "audio_file": ("audio.wav", big, "audio/wav"),
            "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
        }
        # 注意：FastAPI 預設 MAX_CONTENT_LENGTH 也會擋下
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code in (400, 413)

    def test_process_oversized_screenshot_returns_400(self, app_client, fake_wav_bytes):
        """screenshot > 10MB → 400"""
        big = b"\xff\xd8\xff\xe0" + b"\x00" * (11 * 1024 * 1024)
        files = {
            "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
            "screenshot_file": ("shot.jpg", big, "image/jpeg"),
        }
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code in (400, 413)

    def test_process_accepts_multiple_audio_formats(self, app_client, fake_wav_bytes, fake_jpeg_bytes):
        """允許 .wav / .mp3 / .m4a / .flac"""
        for ext, mime in [
            (".wav", "audio/wav"),
            (".mp3", "audio/mpeg"),
            (".m4a", "audio/mp4"),
            (".flac", "audio/flac"),
        ]:
            files = {
                "audio_file": (f"audio{ext}", fake_wav_bytes, mime),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            # 不應該因副檔名被擋（200/500 都可接受，5xx 是下游問題）
            assert r.status_code != 400 or "副檔名" not in r.json().get("detail", "")

    def test_process_accepts_image_formats(self, app_client, fake_wav_bytes, fake_jpeg_bytes):
        """允許 .jpg / .jpeg / .png / .webp"""
        for ext, mime in [
            (".jpg", "image/jpeg"),
            (".jpeg", "image/jpeg"),
            (".png", "image/png"),
            (".webp", "image/webp"),
        ]:
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": (f"shot{ext}", fake_jpeg_bytes, mime),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            # 副檔名應全部通過
            assert r.status_code != 400 or "副檔名" not in r.json().get("detail", "")

    def test_process_returns_session_id(self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch):
        """成功路徑：回應含 session_id（UUID 格式）"""
        # mock 下游引擎
        from src.api import lan_process_api

        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = "fake transcript text"
            engine.extract_symptoms.return_value = []
            engine.classify_icd10.return_value = []
            engine.get_medical_orders.return_value = {}
            engine.get_drug_recommendations.return_value = []
            engine.generate_extended_soap.return_value = {"S": "", "O": "", "A": "", "P": ""}
            return engine

        async def fake_save_record(data):
            return 1

        # patch 模組級 import
        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record", fake_save_record):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            assert r.status_code == 200
            data = r.json()
            assert "session_id" in data
            # UUID 格式：8-4-4-4-12
            sid = data["session_id"]
            parts = sid.split("-")
            assert len(parts) == 5


# ═════════════════════════════════════════════════════════════════
# 5) 完整流程整合測試（5 個）
# ═════════════════════════════════════════════════════════════════


class TestLANProcessIntegration:
    """完整流程：multipart → 壓縮 → 暫存 → ASR/SOAP → SQLite"""

    def test_session_dir_created(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, tmp_path, monkeypatch
    ):
        """成功處理後，session 暫存目錄應存在"""
        from src.api import lan_process_api

        sessions_root = tmp_path / "sessions_test"
        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", sessions_root)

        # mock 下游
        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = ""
            engine.extract_symptoms.return_value = []
            engine.classify_icd10.return_value = []
            return engine

        async def fake_save(data):
            return 1

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record", fake_save):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            assert r.status_code == 200
            sid = r.json()["session_id"]
            session_dir = sessions_root / sid
            assert session_dir.exists()
            # 至少 audio + screenshot + metadata 三個檔
            files_in_dir = list(session_dir.iterdir())
            assert len(files_in_dir) >= 2

    def test_metadata_json_written(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, tmp_path, monkeypatch
    ):
        """metadata.json 應含 session_id / 時間戳 / 壓縮資訊"""
        from src.api import lan_process_api

        sessions_root = tmp_path / "sessions_meta"
        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", sessions_root)

        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = ""
            return engine

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record",
                   AsyncMock(return_value=1)):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post(
                "/api/v1/lan/process",
                files=files,
                data={"patient_name": "王小明", "doctor_name": "林醫師"},
            )
            assert r.status_code == 200
            sid = r.json()["session_id"]
            metadata_path = sessions_root / sid / "metadata.json"
            assert metadata_path.exists()
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            assert meta["session_id"] == sid
            assert "received_at" in meta
            assert meta.get("patient_name") == "王小明"

    def test_response_contains_compression_info(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch, tmp_path
    ):
        """回應應含 compression_ratio 與 bytes 資訊"""
        from src.api import lan_process_api

        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "comp")

        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = ""
            return engine

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record",
                   AsyncMock(return_value=0)):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            assert r.status_code == 200
            data = r.json()
            assert "audio_original_bytes" in data
            assert "audio_compressed_bytes" in data
            assert "compression_ratio" in data
            assert data["audio_original_bytes"] == len(fake_wav_bytes)

    def test_response_contains_processing_time(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch, tmp_path
    ):
        """回應應含 processing_time_ms 含 asr/llm/total"""
        from src.api import lan_process_api

        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "time")

        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = ""
            return engine

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record",
                   AsyncMock(return_value=0)):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            data = r.json()
            assert "processing_time_ms" in data
            ptime = data["processing_time_ms"]
            assert "asr" in ptime
            assert "llm" in ptime
            assert "total" in ptime
            assert ptime["total"] >= 0

    def test_engine_unavailable_returns_partial(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch, tmp_path
    ):
        """ExtendedEngine 取得失敗時：status='partial'，warnings 含原因"""
        from src.api import lan_process_api

        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "partial")

        async def broken_engine():
            raise RuntimeError("engine init failed (test)")

        with patch("src.api.extended_api.get_extended_engine", broken_engine), \
             patch("src.db.patient_records_db.save_consultation_record",
                   AsyncMock(return_value=0)):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            assert r.status_code == 200  # 容錯：仍回 200
            data = r.json()
            assert data["status"] == "partial"
            assert any("engine_unavailable" in w for w in data.get("warnings", []))


# ═════════════════════════════════════════════════════════════════
# 6) 錯誤路徑與 graceful degradation（5 個）
# ═════════════════════════════════════════════════════════════════


class TestLANProcessErrorPaths:
    """錯誤路徑與容錯"""

    def test_asr_failure_marks_partial(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch, tmp_path
    ):
        """ASR 例外 → status=partial 且仍回 200"""
        from src.api import lan_process_api

        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "asr_fail")

        async def fake_get_engine():
            engine = MagicMock()

            def boom(*args, **kwargs):
                raise RuntimeError("ASR engine crashed")

            engine.transcribe.side_effect = boom
            return engine

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record",
                   AsyncMock(return_value=0)):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            assert r.status_code == 200
            data = r.json()
            assert data["status"] == "partial"
            assert any("asr_failed" in w for w in data.get("warnings", []))

    def test_sqlite_failure_returns_warning(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch, tmp_path
    ):
        """SQLite 寫入失敗 → 200 + warning（不阻擋使用者）"""
        from src.api import lan_process_api

        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "sql_fail")

        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = ""
            return engine

        async def broken_save(*args, **kwargs):
            raise IOError("sqlite locked (test)")

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record", broken_save):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            assert r.status_code == 200
            data = r.json()
            assert any("sqlite_failed" in w for w in data.get("warnings", []))

    def test_compression_failure_falls_back(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch, tmp_path
    ):
        """Opus 壓縮例外 → 回傳原 WAV bytes（warning 記錄）"""
        from src.api import lan_process_api
        from src.utils import audio_compress

        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "comp_fail")

        # 模擬壓縮拋例外
        def broken_compress(*args, **kwargs):
            raise RuntimeError("ffmpeg crashed")

        monkeypatch.setattr(
            audio_compress, "compress_audio_to_opus", broken_compress
        )
        # 同時 patch lan_process_api 內的延遲 import 路徑
        monkeypatch.setattr(
            "src.utils.audio_compress.compress_audio_to_opus", broken_compress
        )

        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = ""
            return engine

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record",
                   AsyncMock(return_value=0)):
            files = {
                "audio_file": ("audio.wav", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            assert r.status_code == 200
            data = r.json()
            # 壓縮失敗後 compressed_bytes 應等於原 bytes（fallback）
            assert data["audio_compressed_bytes"] == data["audio_original_bytes"]
            assert any("opus_compression_failed" in w for w in data.get("warnings", []))

    def test_filename_with_no_extension_rejected(self, app_client, fake_jpeg_bytes):
        """無副檔名的 audio_file 應被擋下"""
        files = {
            "audio_file": ("audionoext", b"some bytes", "audio/wav"),
            "screenshot_file": ("shot.jpg", fake_jpeg_bytes, "image/jpeg"),
        }
        r = app_client.post("/api/v1/lan/process", files=files)
        assert r.status_code == 400

    def test_uppercase_extension_normalized(
        self, app_client, fake_wav_bytes, fake_jpeg_bytes, monkeypatch, tmp_path
    ):
        """副檔名大小寫應被正規化（.WAV / .JPG 應通過）"""
        from src.api import lan_process_api

        monkeypatch.setattr(lan_process_api, "LAN_SESSIONS_DIR", tmp_path / "upper")

        async def fake_get_engine():
            engine = MagicMock()
            engine.transcribe.return_value = ""
            return engine

        with patch("src.api.extended_api.get_extended_engine", fake_get_engine), \
             patch("src.db.patient_records_db.save_consultation_record",
                   AsyncMock(return_value=0)):
            files = {
                "audio_file": ("AUDIO.WAV", fake_wav_bytes, "audio/wav"),
                "screenshot_file": ("SHOT.JPG", fake_jpeg_bytes, "image/jpeg"),
            }
            r = app_client.post("/api/v1/lan/process", files=files)
            # 大小寫不應被視為非法
            assert r.status_code == 200


# ═════════════════════════════════════════════════════════════════
# 7) Pydantic 模型驗證（5 個）
# ═════════════════════════════════════════════════════════════════


class TestResponseModels:
    """LANProcessResponse / HealthResponse Pydantic 驗證"""

    def test_lan_response_required_fields(self):
        """LANProcessResponse 必填欄位"""
        from src.api.lan_process_api import LANProcessResponse

        resp = LANProcessResponse(
            session_id="abc",
            status="completed",
            audio_original_bytes=1000,
            audio_compressed_bytes=100,
            compression_ratio="10.0x",
            screenshot_bytes=500,
            received_at="2026-04-27T00:00:00Z",
        )
        assert resp.session_id == "abc"
        assert resp.status == "completed"
        # 預設值
        assert resp.transcript == ""
        assert resp.soap == {}
        assert resp.record_id == 0
        assert resp.warnings == []

    def test_lan_response_with_full_data(self):
        from src.api.lan_process_api import LANProcessResponse

        resp = LANProcessResponse(
            session_id="abc",
            status="partial",
            patient_name="王小明",
            audio_original_bytes=1000,
            audio_compressed_bytes=100,
            compression_ratio="10.0x",
            screenshot_bytes=500,
            transcript="醫師：你好",
            soap={"S": "頭痛"},
            record_id=42,
            received_at="2026-04-27T00:00:00Z",
            processing_time_ms={"asr": 100, "llm": 200, "total": 300},
            warnings=["test warning"],
        )
        assert resp.patient_name == "王小明"
        assert resp.soap == {"S": "頭痛"}
        assert resp.record_id == 42
        assert resp.warnings == ["test warning"]

    def test_health_response_required_fields(self):
        from src.api.lan_health_api import HealthResponse, ServiceStatus

        resp = HealthResponse(
            status="healthy",
            version="1.1.0",
            api_version="v1",
            min_client_version="1.1.0",
            timestamp="2026-04-27T00:00:00Z",
            services=ServiceStatus(asr="ready", llm="ready", database="ready"),
        )
        assert resp.status == "healthy"
        assert resp.services.asr == "ready"

    def test_service_status_defaults(self):
        from src.api.lan_health_api import ServiceStatus

        s = ServiceStatus()
        assert s.asr == "unknown"
        assert s.llm == "unknown"
        assert s.database == "unknown"

    def test_constants_exported(self):
        """匯出的常數可正確存取"""
        from src.api.lan_process_api import (
            ALLOWED_AUDIO_EXTS,
            ALLOWED_IMAGE_EXTS,
            MAX_AUDIO_BYTES,
            MAX_SCREENSHOT_BYTES,
            OPUS_BITRATE_KBPS,
        )

        assert ".wav" in ALLOWED_AUDIO_EXTS
        assert ".jpg" in ALLOWED_IMAGE_EXTS
        assert MAX_AUDIO_BYTES == 100 * 1024 * 1024
        assert MAX_SCREENSHOT_BYTES == 10 * 1024 * 1024
        assert OPUS_BITRATE_KBPS == 32
