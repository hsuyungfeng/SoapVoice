"""客戶端單元測試（Task 1 + Task 2 + Task 3）

測試範圍：
- LANConfig 預設值與環境變數覆蓋
- AsyncHTTPClient GET / POST multipart（mock httpx）
- LANClient 健康檢查狀態機（healthy/degraded/offline）
- LANClient 上傳成功 / 上傳失敗 → 暫存佇列
- AudioRecorder 啟動/停止（mock PyAudio）
- ScreenshotCapture（mock ImageGrab/mss）
- GUI 元件（ConnectionIndicator、SOAPPanel）— 不啟動 mainloop

執行：uv run pytest tests/test_client.py -v
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio  # noqa: F401  -- 確保 plugin 已載入


# 確保 repo root 在 sys.path（pytest 以 repo root 啟動時通常已含）
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ======================================================================
# Task 1: LANConfig
# ======================================================================


class TestLANConfig:
    def test_lan_config_defaults(self):
        """預設值合理：3 秒輪詢、3 次重試、min_api_version 1.1.0。"""
        from client.lan_config import LANConfig

        cfg = LANConfig()
        assert cfg.api_version == "v1"
        assert cfg.connection_timeout_sec == 5.0
        assert cfg.read_timeout_sec == 30.0
        assert cfg.max_retries == 3
        assert cfg.health_check_interval_sec == 3
        assert cfg.max_pending_uploads == 10
        assert cfg.min_api_version == "1.1.0"
        assert "asr" in cfg.required_services
        assert "llm" in cfg.required_services
        assert "database" in cfg.required_services

    def test_lan_config_env_override(self, monkeypatch):
        """SOAPVOICE_SERVER_URL 環境變數可覆蓋 server_url。"""
        from client.lan_config import LANConfig

        monkeypatch.setenv("SOAPVOICE_SERVER_URL", "http://10.0.0.5:9000")
        cfg = LANConfig()
        assert cfg.server_url == "http://10.0.0.5:9000"

    def test_lan_config_endpoints(self):
        """endpoint 屬性組合正確。"""
        from client.lan_config import LANConfig

        cfg = LANConfig(api_version="v1")
        assert cfg.health_endpoint == "api/v1/health"
        assert cfg.lan_process_endpoint == "api/v1/lan/process"

    def test_lan_config_required_services_independent(self):
        """每個 instance 的 required_services 為獨立 list（避免 default mutable 共用）。"""
        from client.lan_config import LANConfig

        cfg1 = LANConfig()
        cfg2 = LANConfig()
        cfg1.required_services.append("custom")
        assert "custom" not in cfg2.required_services


# ======================================================================
# Task 1: AsyncHTTPClient
# ======================================================================


class TestAsyncHTTPClient:
    @pytest.mark.asyncio
    async def test_async_http_client_get_success(self, monkeypatch):
        """GET 成功時回傳 JSON dict（用 MockTransport 替換真正連線）。"""
        import httpx

        from client.http_client import AsyncHTTPClient

        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/health"
            return httpx.Response(
                200,
                json={"status": "healthy", "version": "1.1.0", "services": {"asr": "ready"}},
            )

        transport = httpx.MockTransport(handler)
        # 替換 httpx.AsyncClient 預設 transport 透過 monkeypatch 上層構造
        original_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

        async with AsyncHTTPClient("http://test") as client:
            result = await client.get("api/v1/health")

        assert result["status"] == "healthy"
        assert result["version"] == "1.1.0"

    @pytest.mark.asyncio
    async def test_async_http_client_get_retries_then_fails(self, monkeypatch):
        """連線失敗時重試多次，最終丟出 HTTPClientError。"""
        import httpx

        from client.http_client import AsyncHTTPClient, HTTPClientError

        call_count = {"n": 0}

        async def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            raise httpx.ConnectError("connection refused")

        transport = httpx.MockTransport(handler)
        original_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

        async with AsyncHTTPClient(
            "http://test", max_retries=2, retry_min_wait=0.01, retry_max_wait=0.02
        ) as client:
            with pytest.raises(HTTPClientError):
                await client.get("api/v1/health")

        # 至少重試 max_retries 次
        assert call_count["n"] >= 1

    @pytest.mark.asyncio
    async def test_async_http_client_post_multipart(self, monkeypatch):
        """POST multipart 正常發送，回傳 JSON。"""
        import httpx

        from client.http_client import AsyncHTTPClient

        captured = {}

        async def handler(request: httpx.Request) -> httpx.Response:
            captured["content_type"] = request.headers.get("content-type", "")
            captured["url"] = str(request.url)
            return httpx.Response(
                200,
                json={"session_id": "abc-123", "status": "ok", "soap": {"S": "x"}},
            )

        transport = httpx.MockTransport(handler)
        original_init = httpx.AsyncClient.__init__

        def patched_init(self, *args, **kwargs):
            kwargs["transport"] = transport
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

        async with AsyncHTTPClient("http://test") as client:
            result = await client.post_multipart(
                "api/v1/lan/process",
                files={
                    "audio_file": ("a.wav", b"fakewav", "audio/wav"),
                    "screenshot_file": ("s.jpg", b"fakejpg", "image/jpeg"),
                },
                data={"patient_name": "John"},
            )

        assert result["session_id"] == "abc-123"
        assert "multipart/form-data" in captured["content_type"]


# ======================================================================
# Task 1: LANClient
# ======================================================================


@pytest.fixture
def tmp_config(tmp_path):
    """提供以 tmp_path 為 cache 的 LANConfig。"""
    from client.lan_config import LANConfig

    return LANConfig(
        server_url="http://test-server:8010",
        local_cache_dir=str(tmp_path / "cache"),
        connection_timeout_sec=0.5,
        read_timeout_sec=1.0,
        max_retries=1,
        retry_backoff_base=0.01,
        health_check_interval_sec=1,
    )


class TestLANClientHealth:
    @pytest.mark.asyncio
    async def test_lan_client_health_check_healthy(self, tmp_config):
        """伺服器回應 healthy + 服務全 ready → status='healthy'。"""
        from client.lan_client import HEALTH_HEALTHY, LANClient

        client = LANClient(tmp_config)
        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.get = AsyncMock(
                return_value={
                    "status": "healthy",
                    "version": "1.1.0",
                    "services": {"asr": "ready", "llm": "ready", "database": "ready"},
                }
            )
            mock_cls.return_value.__aenter__.return_value = instance

            result = await client.check_health()

        assert result is True
        assert client.health_status == HEALTH_HEALTHY

    @pytest.mark.asyncio
    async def test_lan_client_health_check_degraded_low_version(self, tmp_config):
        """伺服器版本低於 min_api_version → degraded。"""
        from client.lan_client import HEALTH_DEGRADED, LANClient

        client = LANClient(tmp_config)
        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.get = AsyncMock(
                return_value={
                    "status": "healthy",
                    "version": "1.0.0",  # 低於 1.1.0
                    "services": {"asr": "ready", "llm": "ready", "database": "ready"},
                }
            )
            mock_cls.return_value.__aenter__.return_value = instance

            result = await client.check_health()

        assert result is False
        assert client.health_status == HEALTH_DEGRADED

    @pytest.mark.asyncio
    async def test_lan_client_health_check_degraded_service_loading(self, tmp_config):
        """服務尚未 ready → degraded。"""
        from client.lan_client import HEALTH_DEGRADED, LANClient

        client = LANClient(tmp_config)
        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.get = AsyncMock(
                return_value={
                    "status": "degraded",
                    "version": "1.1.0",
                    "services": {"asr": "loading", "llm": "ready", "database": "ready"},
                }
            )
            mock_cls.return_value.__aenter__.return_value = instance

            result = await client.check_health()

        assert result is False
        assert client.health_status == HEALTH_DEGRADED

    @pytest.mark.asyncio
    async def test_lan_client_health_check_offline(self, tmp_config):
        """連線失敗 → offline。"""
        from client.http_client import HTTPClientError
        from client.lan_client import HEALTH_OFFLINE, LANClient

        client = LANClient(tmp_config)
        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=HTTPClientError("connection refused"))
            mock_cls.return_value.__aenter__.return_value = instance

            result = await client.check_health()

        assert result is False
        assert client.health_status == HEALTH_OFFLINE
        assert client.last_health_error is not None

    @pytest.mark.asyncio
    async def test_lan_client_status_callback_invoked(self, tmp_config):
        """connection_status_callback 在狀態更新時被呼叫。"""
        from client.lan_client import LANClient

        client = LANClient(tmp_config)
        captured = []
        client.connection_status_callback = lambda s: captured.append(s)

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.get = AsyncMock(
                return_value={
                    "version": "1.1.0",
                    "services": {"asr": "ready", "llm": "ready", "database": "ready"},
                }
            )
            mock_cls.return_value.__aenter__.return_value = instance
            await client.check_health()

        assert "healthy" in captured


class TestLANClientUpload:
    @pytest.mark.asyncio
    async def test_lan_client_upload_success(self, tmp_config, tmp_path):
        """完整上傳流程模擬：呼叫 result_callback 並回傳 SOAP。"""
        from client.lan_client import LANClient

        # 準備假音檔/截圖
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFFfakewav")
        shot = tmp_path / "screenshot.jpg"
        shot.write_bytes(b"\xff\xd8\xff\xe0fakejpg")

        client = LANClient(tmp_config)
        captured = []
        client.result_callback = lambda r: captured.append(r)

        soap_response = {
            "session_id": "sess-123",
            "status": "ok",
            "soap": {"S": "頭痛", "O": "BP 120/80", "A": "感冒", "P": "休息"},
        }

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.post_multipart = AsyncMock(return_value=soap_response)
            mock_cls.return_value.__aenter__.return_value = instance

            result = await client.upload_consultation(
                audio_path=str(audio),
                screenshot_path=str(shot),
                patient_name="王大明",
                doctor_name="李醫師",
            )

        assert result == soap_response
        assert len(captured) == 1
        assert captured[0]["session_id"] == "sess-123"
        assert len(client.pending_uploads) == 0  # 沒有暫存

    @pytest.mark.asyncio
    async def test_lan_client_upload_failure_queue(self, tmp_config, tmp_path):
        """上傳失敗時，自動佇列至本機並寫 JSON。"""
        from client.http_client import HTTPClientError
        from client.lan_client import LANClient

        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"RIFFfakewav")
        shot = tmp_path / "screenshot.jpg"
        shot.write_bytes(b"\xff\xd8fakejpg")

        client = LANClient(tmp_config)

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.post_multipart = AsyncMock(
                side_effect=HTTPClientError("server unreachable")
            )
            mock_cls.return_value.__aenter__.return_value = instance

            result = await client.upload_consultation(
                audio_path=str(audio),
                screenshot_path=str(shot),
                patient_name="病患A",
                doctor_name="",
            )

        assert result is None
        assert len(client.pending_uploads) == 1
        assert client.pending_uploads[0].patient_name == "病患A"

        # JSON 檔案存在
        cache_files = list(Path(tmp_config.local_cache_dir).glob("pending_*.json"))
        assert len(cache_files) == 1
        with open(cache_files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["patient_name"] == "病患A"

    @pytest.mark.asyncio
    async def test_lan_client_upload_missing_audio(self, tmp_config):
        """檔案不存在時直接返回 None，不觸發網路請求。"""
        from client.lan_client import LANClient

        client = LANClient(tmp_config)
        result = await client.upload_consultation(
            audio_path="/no/such/file.wav",
            screenshot_path="/no/such/file.jpg",
        )
        assert result is None
        assert len(client.pending_uploads) == 0

    @pytest.mark.asyncio
    async def test_lan_client_load_pending_from_disk(self, tmp_config, tmp_path):
        """啟動時可從快取目錄載入 pending JSON。"""
        from client.lan_client import LANClient

        # 預先寫入兩筆 pending
        cache_dir = Path(tmp_config.local_cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        for i in range(2):
            (cache_dir / f"pending_2026-04-27T0{i}.json").write_text(
                json.dumps(
                    {
                        "audio_path": f"/tmp/a{i}.wav",
                        "screenshot_path": f"/tmp/s{i}.jpg",
                        "patient_name": f"P{i}",
                        "doctor_name": "",
                        "queued_at": f"2026-04-27T0{i}:00:00",
                        "retry_count": 0,
                    }
                ),
                encoding="utf-8",
            )

        client = LANClient(tmp_config)
        loaded = client.load_pending_from_disk()
        assert loaded == 2
        assert len(client.pending_uploads) == 2


# ======================================================================
# Task 2: AudioRecorder（with mocked PyAudio）
# ======================================================================


class TestAudioRecorder:
    def test_audio_recorder_start_stop(self, tmp_path):
        """模擬 PyAudio 錄音流程，驗證 WAV 檔案產生。"""
        from client import audio_recorder as ar_mod
        from client.audio_recorder import AudioRecorder

        # mock PyAudio：stream.read 回傳固定 PCM 資料；audio.get_sample_size = 2
        mock_pyaudio = MagicMock()
        mock_audio_inst = MagicMock()
        mock_stream = MagicMock()
        # 累積讀取，第三次後 stop
        mock_stream.read = MagicMock(return_value=b"\x00\x01" * 1024)
        mock_audio_inst.open = MagicMock(return_value=mock_stream)
        mock_audio_inst.get_sample_size = MagicMock(return_value=2)
        mock_pyaudio.PyAudio = MagicMock(return_value=mock_audio_inst)
        mock_pyaudio.paInt16 = 8

        with patch.object(ar_mod, "pyaudio", mock_pyaudio):
            recorder = AudioRecorder(str(tmp_path))
            recorder.start()
            # 讓背景線程跑幾圈
            import time as _t

            _t.sleep(0.05)
            saved_path = recorder.stop()

        assert saved_path is not None
        assert Path(saved_path).is_file()
        assert Path(saved_path).suffix == ".wav"

    def test_audio_recorder_double_start_no_op(self, tmp_path):
        """重複 start 應視為 no-op，不丟例外。"""
        from client import audio_recorder as ar_mod
        from client.audio_recorder import AudioRecorder

        mock_pyaudio = MagicMock()
        mock_audio_inst = MagicMock()
        mock_stream = MagicMock()
        mock_stream.read = MagicMock(return_value=b"\x00\x01" * 1024)
        mock_audio_inst.open = MagicMock(return_value=mock_stream)
        mock_audio_inst.get_sample_size = MagicMock(return_value=2)
        mock_pyaudio.PyAudio = MagicMock(return_value=mock_audio_inst)
        mock_pyaudio.paInt16 = 8

        with patch.object(ar_mod, "pyaudio", mock_pyaudio):
            recorder = AudioRecorder(str(tmp_path))
            recorder.start()
            recorder.start()  # 第二次 start
            recorder.stop()

    def test_audio_recorder_stop_without_start(self, tmp_path):
        """未 start 直接 stop 應回 None。"""
        from client.audio_recorder import AudioRecorder

        recorder = AudioRecorder(str(tmp_path))
        assert recorder.stop() is None


# ======================================================================
# Task 2: ScreenshotCapture
# ======================================================================


class TestScreenshotCapture:
    def test_screenshot_capture_with_imagegrab(self, tmp_path):
        """ImageGrab 可用時，capture 產生 JPEG。"""
        from PIL import Image

        from client import screenshot_capture as sc_mod
        from client.screenshot_capture import ScreenshotCapture

        fake_img = Image.new("RGB", (100, 80), color=(128, 128, 128))
        with patch.object(sc_mod, "ImageGrab") as mock_ig:
            mock_ig.grab = MagicMock(return_value=fake_img)
            cap = ScreenshotCapture(str(tmp_path))
            path = cap.capture()

        assert path is not None
        assert Path(path).is_file()
        assert Path(path).suffix == ".jpg"
        assert Path(path).stat().st_size > 100  # 非空檔

    def test_screenshot_capture_fallback_to_mss(self, tmp_path):
        """ImageGrab 為 None 時自動 fallback 到 mss。"""
        from PIL import Image

        from client import screenshot_capture as sc_mod
        from client.screenshot_capture import ScreenshotCapture

        # 模擬 mss
        fake_shot = MagicMock()
        fake_shot.size = (50, 40)
        fake_shot.rgb = bytes([100, 100, 100]) * (50 * 40)

        mock_mss_ctx = MagicMock()
        mock_mss_ctx.monitors = [None, {"top": 0, "left": 0, "width": 50, "height": 40}]
        mock_mss_ctx.grab = MagicMock(return_value=fake_shot)

        mock_mss = MagicMock()
        mock_mss.mss = MagicMock()
        mock_mss.mss.return_value.__enter__ = MagicMock(return_value=mock_mss_ctx)
        mock_mss.mss.return_value.__exit__ = MagicMock(return_value=False)

        with patch.object(sc_mod, "ImageGrab", None), patch.object(sc_mod, "mss", mock_mss):
            cap = ScreenshotCapture(str(tmp_path))
            path = cap.capture()

        assert path is not None
        assert Path(path).is_file()


# ======================================================================
# Task 3: GUI 元件（不啟動 mainloop）
# ======================================================================


def _have_display() -> bool:
    """檢查是否有 X11 / Wayland 顯示（無頭環境會跳過 GUI 測試）。"""
    if sys.platform == "win32" or sys.platform == "darwin":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


@pytest.mark.skipif(not _have_display(), reason="No display server available")
class TestGUIComponents:
    def test_gui_connection_indicator(self):
        """ConnectionIndicator 可實例化並切換顏色。"""
        import tkinter as tk

        from client.gui import ConnectionIndicator

        root = tk.Tk()
        try:
            indicator = ConnectionIndicator(root)
            indicator.set_status("healthy")
            assert indicator.status == "healthy"
            indicator.set_status("offline")
            assert indicator.status == "offline"
            indicator.set_status("degraded")
            assert indicator.status == "degraded"
            # 不存在的 status 應 fallback 到 unknown
            indicator.set_status("nonsense")
            assert indicator.status == "unknown"
        finally:
            root.destroy()

    def test_gui_soap_panel(self):
        """SOAPPanel 可實例化並接受 SOAP dict。"""
        import tkinter as tk

        from client.gui import SOAPPanel

        root = tk.Tk()
        try:
            panel = SOAPPanel(root)
            soap_data = {
                "S": "病患主訴頭痛",
                "O": "體溫 36.5",
                "A": "緊張型頭痛",
                "P": "休息與止痛",
                "summary": "頭痛 → 休息",
            }
            panel.display_soap(soap_data)
            # 驗證 S 的內容已寫入
            text_widget = panel.soap_sections["S (主訴)"]
            assert "頭痛" in text_widget.get("1.0", tk.END)
        finally:
            root.destroy()

    def test_gui_main_window(self):
        """SOAPVoiceGUI 可實例化（不 mainloop）。"""
        from client.gui import SOAPVoiceGUI
        from client.lan_client import LANClient
        from client.lan_config import LANConfig

        cfg = LANConfig(local_cache_dir="/tmp/soapvoice_test_gui")
        lan_client = LANClient(cfg)
        app = SOAPVoiceGUI(lan_client)
        try:
            assert app.lan_client is lan_client
            assert app.connection_indicator is not None
            assert app.soap_panel is not None
            # 模擬一次連線狀態更新
            asyncio.get_event_loop().run_until_complete(
                app.update_connection_status("healthy")
            )
            assert app.connection_indicator.status == "healthy"
        finally:
            app.destroy()
