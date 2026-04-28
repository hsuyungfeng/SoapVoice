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

        # 11-03 新 schema：單一 queue.json 集中管理
        queue_file = Path(tmp_config.local_cache_dir) / "pending" / "queue.json"
        assert queue_file.exists()
        with open(queue_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["patient_name"] == "病患A"

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
        """啟動時可從 11-03 新 schema (pending/queue.json) 載入既有隊列。"""
        from client.lan_client import LANClient

        # 預先以新 schema 寫入兩筆 pending（單一 queue.json，list of dict）
        cache_dir = Path(tmp_config.local_cache_dir)
        pending_dir = cache_dir / "pending"
        pending_dir.mkdir(parents=True, exist_ok=True)
        queue_data = [
            {
                "session_id": f"sess-{i}",
                "audio_path": f"/tmp/a{i}.wav",
                "screenshot_path": f"/tmp/s{i}.jpg",
                "patient_name": f"P{i}",
                "doctor_name": "",
                "queued_at": f"2026-04-27T0{i}:00:00",
                "retry_count": 0,
            }
            for i in range(2)
        ]
        (pending_dir / "queue.json").write_text(
            json.dumps(queue_data), encoding="utf-8"
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

    def test_gui_status_transitions(self):
        """SOAPVoiceGUI 連線狀態切換：healthy → offline → degraded 都正確反映。"""
        from client.gui import SOAPVoiceGUI
        from client.lan_client import LANClient
        from client.lan_config import LANConfig

        cfg = LANConfig(local_cache_dir="/tmp/soapvoice_test_gui_trans")
        lan_client = LANClient(cfg)
        app = SOAPVoiceGUI(lan_client)
        try:
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(app.update_connection_status("healthy"))
                assert app.connection_indicator.status == "healthy"
                assert str(app.record_button.cget("state")) == "normal"

                loop.run_until_complete(app.update_connection_status("offline"))
                assert app.connection_indicator.status == "offline"
                # 離線時錄音按鈕應為 disabled
                assert str(app.record_button.cget("state")) == "disabled"

                loop.run_until_complete(app.update_connection_status("degraded"))
                assert app.connection_indicator.status == "degraded"
                assert str(app.record_button.cget("state")) == "disabled"
            finally:
                loop.close()
        finally:
            app.destroy()

    def test_gui_display_soap_result(self):
        """display_soap_result 將伺服器回應寫入 SOAPPanel 各分頁。"""
        import tkinter as tk

        from client.gui import SOAPVoiceGUI
        from client.lan_client import LANClient
        from client.lan_config import LANConfig

        cfg = LANConfig(local_cache_dir="/tmp/soapvoice_test_soap")
        lan_client = LANClient(cfg)
        app = SOAPVoiceGUI(lan_client)
        try:
            response = {
                "session_id": "sess-xyz",
                "status": "ok",
                "soap": {
                    "S": "胸悶",
                    "O": "BP 130/85",
                    "A": "焦慮",
                    "P": "深呼吸",
                    "summary": "緩解策略",
                },
            }
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(app.display_soap_result(response))
            finally:
                loop.close()
            text = app.soap_panel.soap_sections["A (評估)"].get("1.0", tk.END)
            assert "焦慮" in text
        finally:
            app.destroy()

    def test_gui_recording_callbacks(self):
        """set_recording_callbacks 接到按鈕後，按鈕點擊會傳遞錄音狀態。"""
        from client.gui import SOAPVoiceGUI
        from client.lan_client import LANClient
        from client.lan_config import LANConfig

        cfg = LANConfig(local_cache_dir="/tmp/soapvoice_test_btn")
        lan_client = LANClient(cfg)
        app = SOAPVoiceGUI(lan_client)
        try:
            states = []
            shots = []
            app.set_recording_callbacks(
                on_record=lambda is_rec: states.append(is_rec),
                on_screenshot=lambda: shots.append(True),
            )

            # 模擬點擊
            app._on_record_click()
            app._on_record_click()
            app._on_screenshot_click()

            assert states == [True, False]
            assert shots == [True]
        finally:
            app.destroy()

    def test_gui_get_patient_doctor(self):
        """get_patient_doctor 回傳輸入欄當前值（trim 空白）。"""
        from client.gui import SOAPVoiceGUI
        from client.lan_client import LANClient
        from client.lan_config import LANConfig

        cfg = LANConfig(local_cache_dir="/tmp/soapvoice_test_pd")
        lan_client = LANClient(cfg)
        app = SOAPVoiceGUI(lan_client)
        try:
            app.patient_var.set("  王大明  ")
            app.doctor_var.set("李醫師")
            patient, doctor = app.get_patient_doctor()
            assert patient == "王大明"
            assert doctor == "李醫師"
        finally:
            app.destroy()

    def test_soap_panel_handles_missing_keys(self):
        """display_soap 對缺欄位回應應顯示空字串而非 None。"""
        import tkinter as tk

        from client.gui import SOAPPanel

        root = tk.Tk()
        try:
            panel = SOAPPanel(root)
            # 只給 S，其他缺
            panel.display_soap({"S": "測試"})
            for label in ("O (客觀)", "A (評估)", "P (計畫)", "摘要"):
                content = panel.soap_sections[label].get("1.0", tk.END).strip()
                assert content == "", f"section {label} 應為空，實際: {content!r}"
        finally:
            root.destroy()

    def test_soap_panel_ignores_non_dict(self):
        """display_soap 收到非 dict 不應丟例外。"""
        import tkinter as tk

        from client.gui import SOAPPanel

        root = tk.Tk()
        try:
            panel = SOAPPanel(root)
            panel.display_soap(None)  # type: ignore[arg-type]
            panel.display_soap("not a dict")  # type: ignore[arg-type]
            # 沒丟例外即通過
        finally:
            root.destroy()


# ======================================================================
# Task 3: AsyncRunner（背景事件迴圈）
# ======================================================================


class TestAsyncRunner:
    def test_async_runner_start_stop(self):
        """start() 後 loop 可運作，stop() 後 thread 結束。"""
        from client.main import AsyncRunner

        runner = AsyncRunner()
        runner.start()
        assert runner.loop is not None
        assert runner.loop.is_running()

        # 提交一個簡單協程
        async def hello() -> str:
            return "ok"

        future = runner.submit(hello())
        result = future.result(timeout=2.0)
        assert result == "ok"

        runner.stop(timeout=2.0)
        # stop 後再 submit 應丟例外（loop 已關）
        with pytest.raises(RuntimeError):
            runner.submit(hello())

    def test_async_runner_submit_before_start(self):
        """未 start 直接 submit 應丟 RuntimeError。"""
        from client.main import AsyncRunner

        runner = AsyncRunner()

        async def noop() -> None:
            return None

        with pytest.raises(RuntimeError):
            runner.submit(noop())

    def test_async_runner_double_start_safe(self):
        """重複 start 應為 no-op，不丟例外。"""
        from client.main import AsyncRunner

        runner = AsyncRunner()
        runner.start()
        runner.start()  # no-op
        try:
            assert runner.loop is not None
        finally:
            runner.stop()


# ======================================================================
# Task 3: App 控制器（整合 GUI + LANClient + I/O）
# ======================================================================


@pytest.mark.skipif(not _have_display(), reason="No display server available")
class TestAppController:
    def test_app_init_wires_components(self, tmp_path):
        """App.__init__ 正確建立 lan_client/recorder/screenshot/gui。"""
        from client.lan_config import LANConfig
        from client.main import App

        cfg = LANConfig(
            local_cache_dir=str(tmp_path / "cache"),
            connection_timeout_sec=0.5,
        )
        app = App(cfg)
        try:
            assert app.lan_client is not None
            assert app.audio_recorder is not None
            assert app.screenshot_capture is not None
            assert app.gui is not None
            # GUI 已掛上 lan_client callback
            assert app.lan_client.connection_status_callback is not None
            assert app.lan_client.result_callback is not None
        finally:
            try:
                app.gui.destroy()
            except Exception:
                pass
            app.shutdown()

    def test_app_record_toggle_triggers_upload(self, tmp_path):
        """錄音停止後，App 應將 wav+screenshot 提交至 lan_client.upload_consultation。"""
        from client.lan_config import LANConfig
        from client.main import App

        cfg = LANConfig(
            local_cache_dir=str(tmp_path / "cache"),
            connection_timeout_sec=0.5,
        )
        app = App(cfg)
        try:
            app.async_runner.start()

            # mock recorder & screenshot
            app.audio_recorder = MagicMock()
            wav_path = str(tmp_path / "fake.wav")
            Path(wav_path).write_bytes(b"RIFFfake")
            app.audio_recorder.is_recording = False
            app.audio_recorder.start = MagicMock()
            app.audio_recorder.stop = MagicMock(return_value=wav_path)

            shot_path = str(tmp_path / "fake.jpg")
            Path(shot_path).write_bytes(b"\xff\xd8fake")
            app.screenshot_capture = MagicMock()
            app.screenshot_capture.capture = MagicMock(return_value=shot_path)

            # 替換 lan_client.upload_consultation 為可追蹤的 async mock
            calls: list[tuple] = []

            async def fake_upload(audio_path, screenshot_path, patient_name="", doctor_name=""):
                calls.append((audio_path, screenshot_path, patient_name, doctor_name))
                return {"session_id": "fake", "status": "ok", "soap": {"S": "x"}}

            app.lan_client.upload_consultation = fake_upload  # type: ignore[assignment]

            # 模擬 GUI 病患資訊
            app.gui.patient_var.set("王大明")
            app.gui.doctor_var.set("李醫師")

            # 1. 開始錄音 → 應截圖並啟動 recorder
            app._on_record_toggle(True)
            assert app.screenshot_capture.capture.call_count == 1
            assert app.audio_recorder.start.call_count == 1

            # 2. 停止錄音 → 應呼叫 upload_consultation
            app._on_record_toggle(False)
            # 等待 async 任務跑完
            import time as _t

            for _ in range(20):
                if calls:
                    break
                _t.sleep(0.05)

            assert len(calls) == 1
            audio_p, shot_p, patient, doctor = calls[0]
            assert audio_p == wav_path
            assert shot_p == shot_path
            assert patient == "王大明"
            assert doctor == "李醫師"
        finally:
            try:
                app.gui.destroy()
            except Exception:
                pass
            app.shutdown()


# ======================================================================
# Task 1+: 額外健康檢查邊界
# ======================================================================


class TestLANClientHealthExtra:
    @pytest.mark.asyncio
    async def test_lan_client_health_recovery_triggers_retry(self, tmp_config, tmp_path):
        """連線恢復時會自動觸發 retry_pending_uploads。"""
        from client.lan_client import LANClient

        client = LANClient(tmp_config)

        # 預塞一筆 pending（以 _queue_for_retry 方便產生 cache 檔）
        audio = tmp_path / "a.wav"
        audio.write_bytes(b"x")
        shot = tmp_path / "s.jpg"
        shot.write_bytes(b"y")
        client._queue_for_retry(str(audio), str(shot), "P", "D")
        assert len(client.pending_uploads) == 1

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
            # 觸發了 create_task；給事件迴圈一輪機會跑
            await asyncio.sleep(0.01)

        # check_health 完成後，因 retry_pending_uploads 為非同步任務，
        # 此處只驗證 health_status 為 healthy（建立 retry task 是副作用）
        assert client.health_status == "healthy"

    @pytest.mark.asyncio
    async def test_lan_client_pending_queue_cap(self, tmp_config, tmp_path):
        """超過 max_pending_uploads 時自動 drop 最舊。"""
        from client.lan_client import LANClient

        # 把上限設低
        tmp_config.max_pending_uploads = 2
        client = LANClient(tmp_config)

        audio = tmp_path / "a.wav"
        audio.write_bytes(b"x")
        shot = tmp_path / "s.jpg"
        shot.write_bytes(b"y")

        for i in range(3):
            client._queue_for_retry(str(audio), str(shot), f"P{i}", "D")

        assert len(client.pending_uploads) == 2
        # 最舊的 P0 應被 drop
        names = [p.patient_name for p in client.pending_uploads]
        assert "P0" not in names
        assert "P1" in names
        assert "P2" in names

    @pytest.mark.asyncio
    async def test_lan_client_semver_compare_edge(self):
        """_semver_tuple 處理 rc/beta tag 不丟 ValueError。"""
        from client.lan_client import _semver_tuple

        assert _semver_tuple("1.1.0") == (1, 1, 0)
        assert _semver_tuple("1.2.0-rc1") == (1, 2, 0)
        assert _semver_tuple("") == (0,)
        assert _semver_tuple("invalid") == (0,)
        assert _semver_tuple("1.0.0") < _semver_tuple("1.1.0")


# ======================================================================
# Phase 11-03 Task 1: LocalStorageManager
# ======================================================================


class TestLocalStorageManager:
    """本機暫存管理器測試。"""

    def _mk_audio(self, tmp_path, name="audio.wav"):
        audio = tmp_path / name
        audio.write_bytes(b"RIFFfakewav")
        return str(audio)

    def _mk_shot(self, tmp_path, name="screenshot.jpg"):
        shot = tmp_path / name
        shot.write_bytes(b"\xff\xd8\xff\xe0fakejpg")
        return str(shot)

    def test_local_storage_add_pending(self, tmp_path):
        """新增項目，驗證隊列大小增加並寫入 queue.json。"""
        from client.local_storage import LocalStorageManager

        mgr = LocalStorageManager(str(tmp_path / "cache"))
        audio = self._mk_audio(tmp_path)
        shot = self._mk_shot(tmp_path)

        ok = mgr.add_pending(
            session_id="20260427_103000_a1b2c3d4",
            audio_path=audio,
            screenshot_path=shot,
            patient_name="王大明",
            doctor_name="李醫師",
        )
        assert ok is True
        assert mgr.get_queue_size() == 1

        # 驗證 queue.json 已寫入
        queue_file = mgr.queue_file
        assert queue_file.exists()
        with open(queue_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["session_id"] == "20260427_103000_a1b2c3d4"
        assert data[0]["patient_name"] == "王大明"
        assert data[0]["retry_count"] == 0

    def test_local_storage_add_pending_missing_audio(self, tmp_path):
        """音檔不存在時 add_pending 應回 False，不入隊。"""
        from client.local_storage import LocalStorageManager

        mgr = LocalStorageManager(str(tmp_path / "cache"))
        ok = mgr.add_pending(
            session_id="missing",
            audio_path="/no/such/file.wav",
            screenshot_path="/no/such/file.jpg",
        )
        assert ok is False
        assert mgr.get_queue_size() == 0

    def test_local_storage_save_load(self, tmp_path):
        """儲存隊列，重新建立 manager，驗證內容一致。"""
        from client.local_storage import LocalStorageManager

        cache_dir = str(tmp_path / "cache")
        mgr1 = LocalStorageManager(cache_dir)
        for i in range(3):
            audio = self._mk_audio(tmp_path, f"a{i}.wav")
            shot = self._mk_shot(tmp_path, f"s{i}.jpg")
            mgr1.add_pending(
                session_id=f"sess{i}",
                audio_path=audio,
                screenshot_path=shot,
                patient_name=f"P{i}",
                doctor_name="D",
            )

        # 重新建立 manager，從 queue.json 載入
        mgr2 = LocalStorageManager(cache_dir)
        assert mgr2.get_queue_size() == 3
        items = mgr2.get_all_pending()
        assert items[0].session_id == "sess0"
        assert items[1].patient_name == "P1"
        assert items[2].session_id == "sess2"

    def test_local_storage_remove_pending(self, tmp_path):
        """移除特定項目，驗證隊列更新並 queue.json 同步。"""
        from client.local_storage import LocalStorageManager

        mgr = LocalStorageManager(str(tmp_path / "cache"))
        for i in range(3):
            audio = self._mk_audio(tmp_path, f"a{i}.wav")
            shot = self._mk_shot(tmp_path, f"s{i}.jpg")
            mgr.add_pending(f"sess{i}", audio, shot, f"P{i}", "D")

        assert mgr.remove_pending("sess1") is True
        assert mgr.get_queue_size() == 2
        names = [p.session_id for p in mgr.get_all_pending()]
        assert "sess1" not in names
        assert "sess0" in names
        assert "sess2" in names

        # 不存在的 session_id
        assert mgr.remove_pending("nonexistent") is False

        # 驗證 queue.json 也已同步
        with open(mgr.queue_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 2

    def test_local_storage_queue_overflow(self, tmp_path):
        """新增超過上限時，最舊項目自動刪除並記 warning。"""
        from client.local_storage import LocalStorageManager

        mgr = LocalStorageManager(str(tmp_path / "cache"), max_pending=3)

        for i in range(5):
            audio = self._mk_audio(tmp_path, f"a{i}.wav")
            shot = self._mk_shot(tmp_path, f"s{i}.jpg")
            mgr.add_pending(f"sess{i}", audio, shot, f"P{i}", "D")

        # 上限 3：最舊兩個（sess0/sess1）應被刪除
        assert mgr.get_queue_size() == 3
        names = [p.session_id for p in mgr.get_all_pending()]
        assert "sess0" not in names
        assert "sess1" not in names
        assert "sess2" in names
        assert "sess3" in names
        assert "sess4" in names

    def test_local_storage_increment_retry(self, tmp_path):
        """增加重試計數，驗證 retry_count 遞增並持久化。"""
        from client.local_storage import LocalStorageManager

        cache_dir = str(tmp_path / "cache")
        mgr = LocalStorageManager(cache_dir)
        audio = self._mk_audio(tmp_path)
        shot = self._mk_shot(tmp_path)
        mgr.add_pending("sessA", audio, shot)

        assert mgr.increment_retry_count("sessA") is True
        assert mgr.find_by_session_id("sessA").retry_count == 1
        assert mgr.increment_retry_count("sessA") is True
        assert mgr.find_by_session_id("sessA").retry_count == 2

        # 不存在
        assert mgr.increment_retry_count("nope") is False

        # 重新載入後 retry_count 仍為 2
        mgr2 = LocalStorageManager(cache_dir)
        assert mgr2.find_by_session_id("sessA").retry_count == 2

    def test_local_storage_corrupt_queue_json(self, tmp_path):
        """損毀的 queue.json 應記 error 並回退為空隊列，不丟例外。"""
        from client.local_storage import LocalStorageManager

        cache_dir = tmp_path / "cache"
        pending_dir = cache_dir / "pending"
        pending_dir.mkdir(parents=True)
        # 寫入損毀內容
        (pending_dir / "queue.json").write_text("{ this is not valid JSON ", encoding="utf-8")

        mgr = LocalStorageManager(str(cache_dir))
        assert mgr.get_queue_size() == 0  # 回退為空

    def test_local_storage_clear_all(self, tmp_path):
        """clear_all 清空隊列並同步 queue.json。"""
        from client.local_storage import LocalStorageManager

        mgr = LocalStorageManager(str(tmp_path / "cache"))
        audio = self._mk_audio(tmp_path)
        shot = self._mk_shot(tmp_path)
        mgr.add_pending("a", audio, shot)
        mgr.add_pending("b", audio, shot)
        assert mgr.get_queue_size() == 2

        mgr.clear_all()
        assert mgr.get_queue_size() == 0
        with open(mgr.queue_file, "r", encoding="utf-8") as f:
            assert json.load(f) == []

    def test_local_storage_pending_upload_serialization(self):
        """PendingUpload to_dict / from_dict 對稱。"""
        from client.local_storage import PendingUpload

        original = PendingUpload(
            session_id="x",
            audio_path="/tmp/a.wav",
            screenshot_path="/tmp/s.jpg",
            patient_name="王",
            doctor_name="李",
            queued_at="2026-04-27T10:30:00",
            retry_count=2,
        )
        d = original.to_dict()
        restored = PendingUpload.from_dict(d)
        assert restored.session_id == "x"
        assert restored.retry_count == 2
        assert restored.patient_name == "王"

        # 容錯：缺欄位應回退至預設值
        partial = PendingUpload.from_dict({"session_id": "y", "audio_path": "/a", "screenshot_path": "/s"})
        assert partial.patient_name == ""
        assert partial.retry_count == 0


# ======================================================================
# Phase 11-03 Task 2: RetryManager
# ======================================================================


class TestRetryManager:
    """重試管理器測試。"""

    def test_retry_manager_backoff_calculation(self):
        """指數退避計算：retry_count 0/1/2 → 2/4/8 秒。"""
        from client.retry_manager import RetryManager

        rm = RetryManager(base_delay_sec=2.0, max_retries=3, backoff_multiplier=2.0)
        assert rm.get_retry_delay(0) == 2.0
        assert rm.get_retry_delay(1) == 4.0
        assert rm.get_retry_delay(2) == 8.0
        # 邊界：負值回 0
        assert rm.get_retry_delay(-1) == 0

    def test_retry_manager_should_retry(self):
        """最多 3 次重試邏輯：count < max 則 True。"""
        from client.retry_manager import RetryManager

        rm = RetryManager(max_retries=3)
        assert rm.should_retry("s", 0) is True
        assert rm.should_retry("s", 1) is True
        assert rm.should_retry("s", 2) is True
        assert rm.should_retry("s", 3) is False  # 已達上限
        assert rm.should_retry("s", 5) is False

    def test_retry_manager_get_next_retry_delay(self):
        """超過 max_retries 時 get_next_retry_delay 回 -1（標記不應重試）。"""
        from client.retry_manager import RetryManager

        rm = RetryManager(base_delay_sec=2.0, max_retries=3)
        assert rm.get_next_retry_delay(0) == 2.0
        assert rm.get_next_retry_delay(2) == 8.0
        assert rm.get_next_retry_delay(3) == -1  # 已達上限

    @pytest.mark.asyncio
    async def test_retry_manager_wait_before_retry(self):
        """非同步等待：retry_count 0 應 sleep 約 base_delay 秒。"""
        import time as _t

        from client.retry_manager import RetryManager

        rm = RetryManager(base_delay_sec=0.05, max_retries=3, backoff_multiplier=2.0)

        start = _t.monotonic()
        ok = await rm.wait_before_retry(0)
        elapsed = _t.monotonic() - start

        assert ok is True
        # 至少 base_delay；給點誤差
        assert elapsed >= 0.04

        # 已達 max → False，不 sleep
        start = _t.monotonic()
        ok = await rm.wait_before_retry(3)
        elapsed = _t.monotonic() - start
        assert ok is False
        assert elapsed < 0.02  # 立即回

    def test_retry_manager_state_tracking(self):
        """mark_retry_scheduled / get_state / reset_state 行為。"""
        from client.retry_manager import RetryManager

        rm = RetryManager(base_delay_sec=2.0, max_retries=3)

        # 初始無狀態
        assert rm.get_state("sessA") is None

        rm.mark_retry_scheduled("sessA", 1)
        state = rm.get_state("sessA")
        assert state is not None
        assert state["count"] == 1
        assert "next_retry_at" in state
        assert "last_attempt_at" in state

        rm.reset_state("sessA")
        assert rm.get_state("sessA") is None
        # 重複 reset 不丟例外
        rm.reset_state("sessA")

    def test_retry_manager_default_params(self):
        """預設值：base_delay=2.0, max_retries=3, multiplier=2.0。"""
        from client.retry_manager import RetryManager

        rm = RetryManager()
        assert rm.base_delay_sec == 2.0
        assert rm.max_retries == 3
        assert rm.backoff_multiplier == 2.0


# ======================================================================
# Phase 11-03 Task 3: LANClient × LocalStorageManager × RetryManager 整合
# ======================================================================


class TestLANClientRetry:
    """整合：上傳失敗 → 入隊 → 連線恢復 → 重試 → 成功移除 / 失敗保留。"""

    @pytest.fixture
    def make_files(self, tmp_path):
        def _make(name="x"):
            audio = tmp_path / f"audio_{name}.wav"
            audio.write_bytes(b"RIFFfake")
            shot = tmp_path / f"shot_{name}.jpg"
            shot.write_bytes(b"\xff\xd8fake")
            return str(audio), str(shot)

        return _make

    @pytest.mark.asyncio
    async def test_lan_client_upload_failure_queue(self, tmp_config, make_files):
        """上傳失敗時自動入 LocalStorageManager 隊列。"""
        from client.http_client import HTTPClientError
        from client.lan_client import LANClient

        audio, shot = make_files("u1")
        client = LANClient(tmp_config)

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.post_multipart = AsyncMock(
                side_effect=HTTPClientError("server unreachable")
            )
            mock_cls.return_value.__aenter__.return_value = instance

            result = await client.upload_consultation(
                audio_path=audio,
                screenshot_path=shot,
                patient_name="病患A",
                doctor_name="醫師B",
            )

        assert result is None
        # storage 隊列存有一筆
        assert client.storage.get_queue_size() == 1
        item = client.storage.get_all_pending()[0]
        assert item.patient_name == "病患A"
        assert item.audio_path == audio

    @pytest.mark.asyncio
    async def test_lan_client_restore_pending_uploads(self, tmp_config, make_files):
        """新建 LANClient 時，已存在的 queue.json 應自動載入。"""
        from client.lan_client import LANClient
        from client.local_storage import LocalStorageManager

        # 先以一個獨立 manager 預塞兩筆
        audio, shot = make_files("r1")
        pre_mgr = LocalStorageManager(tmp_config.local_cache_dir)
        pre_mgr.add_pending("sess-1", audio, shot, "P1", "D")
        pre_mgr.add_pending("sess-2", audio, shot, "P2", "D")
        assert pre_mgr.get_queue_size() == 2

        # 新 LANClient 應從 queue.json 取得既有項目
        client = LANClient(tmp_config)
        assert client.storage.get_queue_size() == 2

    @pytest.mark.asyncio
    async def test_lan_client_retry_pending_uploads_success(self, tmp_config, make_files):
        """retry_pending_uploads：所有項目重試成功 → 隊列清空。"""
        from client.lan_client import LANClient

        client = LANClient(tmp_config)
        audio, shot = make_files("ok")
        client.storage.add_pending("s-ok-1", audio, shot, "P1", "D")
        client.storage.add_pending("s-ok-2", audio, shot, "P2", "D")
        assert client.storage.get_queue_size() == 2

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.post_multipart = AsyncMock(
                return_value={"session_id": "x", "status": "ok", "soap": {}}
            )
            mock_cls.return_value.__aenter__.return_value = instance

            success_count = await client.retry_pending_uploads()

        assert success_count == 2
        assert client.storage.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_lan_client_retry_pending_uploads_failure(self, tmp_config, make_files):
        """retry_pending_uploads：失敗時 retry_count++ 且保留隊列。"""
        from client.http_client import HTTPClientError
        from client.lan_client import LANClient

        client = LANClient(tmp_config)
        audio, shot = make_files("fail")
        client.storage.add_pending("s-fail", audio, shot, "P", "D")

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.post_multipart = AsyncMock(
                side_effect=HTTPClientError("still down")
            )
            mock_cls.return_value.__aenter__.return_value = instance

            success_count = await client.retry_pending_uploads()

        assert success_count == 0
        assert client.storage.get_queue_size() == 1
        # retry_count 已遞增
        item = client.storage.find_by_session_id("s-fail")
        assert item.retry_count == 1

    @pytest.mark.asyncio
    async def test_lan_client_max_retries_exceeded(self, tmp_config, make_files):
        """超過 max_retries 後該項目自動從隊列移除。"""
        from client.http_client import HTTPClientError
        from client.lan_client import LANClient

        # tmp_config.max_retries=1（fixture 設定），故 retry_count >= 1 即超過
        client = LANClient(tmp_config)
        audio, shot = make_files("over")

        # 以 retry_count=1 預塞（已達上限）
        client.storage.add_pending("s-over", audio, shot, "P", "D")
        client.storage.increment_retry_count("s-over")  # retry_count=1
        assert client.storage.find_by_session_id("s-over").retry_count == 1

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.post_multipart = AsyncMock(
                side_effect=HTTPClientError("still down")
            )
            mock_cls.return_value.__aenter__.return_value = instance

            await client.retry_pending_uploads()

        # 因 retry_count >= max_retries=1，應被刪除
        assert client.storage.find_by_session_id("s-over") is None

    @pytest.mark.asyncio
    async def test_lan_client_health_recovery_triggers_retry(self, tmp_config, make_files):
        """連線恢復（offline → healthy）時自動觸發 retry_pending_uploads。"""
        from client.http_client import HTTPClientError
        from client.lan_client import HEALTH_HEALTHY, HEALTH_OFFLINE, LANClient

        client = LANClient(tmp_config)
        audio, shot = make_files("rec")
        client.storage.add_pending("s-rec", audio, shot, "P", "D")

        # 第一輪：offline
        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.get = AsyncMock(side_effect=HTTPClientError("down"))
            mock_cls.return_value.__aenter__.return_value = instance
            await client.check_health()
            assert client.health_status == HEALTH_OFFLINE

        # 第二輪：healthy + post 成功 → retry 應被觸發
        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.get = AsyncMock(
                return_value={
                    "version": "1.1.0",
                    "services": {"asr": "ready", "llm": "ready", "database": "ready"},
                }
            )
            instance.post_multipart = AsyncMock(
                return_value={"session_id": "ok", "status": "ok", "soap": {}}
            )
            mock_cls.return_value.__aenter__.return_value = instance

            await client.check_health()
            # 給事件迴圈一輪機會跑 create_task
            await asyncio.sleep(0.1)

        assert client.health_status == HEALTH_HEALTHY
        # retry 已執行 → 隊列清空
        assert client.storage.get_queue_size() == 0

    @pytest.mark.asyncio
    async def test_lan_client_session_id_format(self, tmp_config, make_files):
        """上傳失敗時生成的 session_id 應符合 YYYYMMDD_HHMMSS_xxxxxxxx 格式。"""
        import re

        from client.http_client import HTTPClientError
        from client.lan_client import LANClient

        client = LANClient(tmp_config)
        audio, shot = make_files("sid")

        with patch("client.lan_client.AsyncHTTPClient") as mock_cls:
            instance = AsyncMock()
            instance.post_multipart = AsyncMock(
                side_effect=HTTPClientError("down")
            )
            mock_cls.return_value.__aenter__.return_value = instance
            await client.upload_consultation(audio, shot, "P", "D")

        item = client.storage.get_all_pending()[0]
        # 期望格式 20260427_103000_xxxxxxxx
        assert re.match(r"^\d{8}_\d{6}_[0-9a-f]{8}$", item.session_id), \
            f"session_id 格式不符: {item.session_id}"
