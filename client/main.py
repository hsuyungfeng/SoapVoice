"""SoapVoice LAN 瘦客戶端應用程式入口

職責：
1. 載入設定（LANConfig）
2. 啟動時呼叫 /api/v1/health 檢查伺服器版本相容性
3. 不相容時彈窗提示，並仍進入 GUI（顯示降級狀態）
4. 初始化 LANClient / AudioRecorder / ScreenshotCapture / GUI
5. 在背景 thread 跑 asyncio 事件迴圈（health monitor + 上傳協程）
6. tkinter mainloop 在主執行緒

Threading 模型：
    主執行緒        : tkinter mainloop（GUI 事件）
    Async thread    : asyncio.run_until_complete(健康監控 + 上傳)
    AudioRecorder   : 自己的 daemon thread（PyAudio 不阻塞）

執行：
    uv run python -m client.main
    SOAPVOICE_SERVER_URL=http://192.168.1.50:8010 uv run python -m client.main
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
from pathlib import Path
from typing import Optional

# 套件相對 import（執行 `python -m client.main`）
from client.audio_recorder import AudioRecorder
from client.gui import SOAPVoiceGUI
from client.lan_client import HEALTH_HEALTHY, LANClient
from client.lan_config import LANConfig
from client.screenshot_capture import ScreenshotCapture

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 日誌設定
# ----------------------------------------------------------------------


def _configure_logging(log_dir: Path, verbose: bool = False) -> None:
    """配置 root logger：同時寫入檔案與 stderr。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "soapvoice_client.log"

    level = logging.DEBUG if verbose else logging.INFO
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    # 清除既有 handler（避免重複輸出，例如 pytest 環境）
    for handler in list(root.handlers):
        root.removeHandler(handler)

    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(fmt)
    stream_handler.setLevel(level)

    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)


# ----------------------------------------------------------------------
# Async 背景執行器
# ----------------------------------------------------------------------


class AsyncRunner:
    """在背景 thread 內運行 asyncio 事件迴圈。

    用途：
    - LANClient.start_health_monitor() 為協程，需要事件迴圈
    - GUI 點擊「停止錄音」後觸發上傳，須以 `submit()` 進入 async 世界

    設計：
    - 一個 thread 一個 loop，主執行緒以 `submit(coro)` 提交工作
    - `stop()` 會 schedule 一個取消任務並 join thread
    """

    def __init__(self) -> None:
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()

    def start(self) -> None:
        """啟動背景事件迴圈（呼叫一次）。"""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="async-runner")
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise RuntimeError("AsyncRunner failed to start within 5s")

    def _run(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        try:
            self.loop.run_forever()
        finally:
            try:
                self.loop.close()
            except Exception:  # noqa: BLE001
                pass

    def submit(self, coro) -> "asyncio.Future":
        """從任意 thread 提交協程到背景 loop。"""
        if self.loop is None or not self.loop.is_running():
            raise RuntimeError("AsyncRunner not running; call start() first")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self, timeout: float = 5.0) -> None:
        """停止背景 loop（取消所有任務後 join）。"""
        if self.loop is None or self._thread is None:
            return
        try:
            self.loop.call_soon_threadsafe(self._cancel_all)
        except RuntimeError:
            pass
        self._thread.join(timeout=timeout)
        self._thread = None

    def _cancel_all(self) -> None:
        """取消所有任務並請 loop 結束。"""
        if self.loop is None:
            return
        for task in asyncio.all_tasks(self.loop):
            task.cancel()
        self.loop.stop()


# ----------------------------------------------------------------------
# 應用程式控制器
# ----------------------------------------------------------------------


class App:
    """應用程式控制器：把 GUI / LANClient / I/O 模組黏合起來。

    生命週期：
        1. __init__()        — 初始化所有元件
        2. perform_health_check() — 啟動時版本相容性驗證
        3. run()             — 顯示 GUI、進入 mainloop
        4. shutdown()        — 停止背景 loop、AudioRecorder
    """

    def __init__(self, config: LANConfig):
        self.config = config

        # 確保快取目錄存在
        self.cache_dir = Path(config.local_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 核心元件
        self.lan_client = LANClient(config)
        self.audio_recorder = AudioRecorder(str(self.cache_dir))
        self.screenshot_capture = ScreenshotCapture(str(self.cache_dir))

        # 事件迴圈（背景）
        self.async_runner = AsyncRunner()

        # GUI（最後建立，需綁定 lan_client）
        self.gui = SOAPVoiceGUI(self.lan_client)
        self.gui.set_recording_callbacks(
            on_record=self._on_record_toggle,
            on_screenshot=self._on_screenshot_request,
        )

        # 載入先前未上傳的暫存
        loaded = self.lan_client.load_pending_from_disk()
        if loaded > 0:
            logger.info("Restored %d pending uploads from disk", loaded)
            self.gui._set_status_message(f"已載入 {loaded} 筆未上傳問診，待連線後自動補傳")

        # 紀錄上次自動截圖路徑（錄音停止 → 上傳時使用）
        self._last_screenshot_path: Optional[str] = None

    # ------------------------------------------------------------------
    # 啟動健康檢查
    # ------------------------------------------------------------------

    def perform_health_check(self) -> bool:
        """同步呼叫一次健康檢查，並在版本不相容時彈窗。

        Returns:
            True 若伺服器健康；False 若降級或離線（仍會進 GUI，使用者自行重試）。
        """
        future = self.async_runner.submit(self.lan_client.check_health())
        try:
            healthy = future.result(timeout=self.config.connection_timeout_sec + 2.0)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Initial health check failed: %s", exc)
            return False

        # 不論結果，根據 last_health_response 決定是否彈版本不相容警告
        response = self.lan_client.last_health_response or {}
        server_version = str(response.get("version", ""))
        if response and server_version and self._version_below(server_version, self.config.min_api_version):
            logger.warning(
                "Server version %s < required %s — showing version mismatch dialog",
                server_version,
                self.config.min_api_version,
            )
            self.gui.show_version_mismatch(server_version, self.config.min_api_version)

        if not healthy:
            error = self.lan_client.last_health_error or "伺服器未回應"
            self.gui._set_status_message(f"⚠ 啟動健康檢查失敗：{error}")
            return False

        return self.lan_client.health_status == HEALTH_HEALTHY

    @staticmethod
    def _version_below(actual: str, required: str) -> bool:
        """簡易 SemVer 比較（與 lan_client._semver_tuple 對齊）。"""
        from client.lan_client import _semver_tuple

        return _semver_tuple(actual) < _semver_tuple(required)

    # ------------------------------------------------------------------
    # 錄音/截圖事件
    # ------------------------------------------------------------------

    def _on_record_toggle(self, is_recording: bool) -> None:
        """GUI 錄音按鈕切換 → 控制 AudioRecorder。"""
        if is_recording:
            # 錄音開始 — 同時截圖
            screenshot_path = self.screenshot_capture.capture()
            self._last_screenshot_path = screenshot_path
            if screenshot_path:
                logger.info("Auto-screenshot saved: %s", screenshot_path)
            else:
                logger.warning("Auto-screenshot failed; will use empty placeholder")

            # 啟動錄音
            self.audio_recorder.on_error = self._on_audio_error
            self.audio_recorder.start()
        else:
            # 錄音停止 → 取得 wav 路徑 → 上傳
            audio_path = self.audio_recorder.stop()
            if audio_path is None:
                logger.warning("Recording stop returned None")
                return
            screenshot_path = self._last_screenshot_path
            self._last_screenshot_path = None
            if not screenshot_path:
                # 補一張截圖以滿足伺服器 multipart 必填
                screenshot_path = self.screenshot_capture.capture()

            if not screenshot_path:
                self.gui._set_status_message("✗ 截圖失敗，無法上傳")
                return

            patient, doctor = self.gui.get_patient_doctor()
            self.async_runner.submit(
                self.lan_client.upload_consultation(
                    audio_path=audio_path,
                    screenshot_path=screenshot_path,
                    patient_name=patient,
                    doctor_name=doctor,
                )
            )

    def _on_screenshot_request(self) -> None:
        """GUI 立即截圖按鈕 → 單純截圖一張到快取目錄。"""
        path = self.screenshot_capture.capture()
        if path:
            logger.info("Manual screenshot saved: %s", path)
        else:
            logger.error("Manual screenshot failed")

    def _on_audio_error(self, message: str) -> None:
        """AudioRecorder 錯誤時，反映到 GUI 狀態列。"""
        try:
            self.gui.after(0, lambda: self.gui._set_status_message(f"✗ 錄音錯誤：{message}"))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------

    def run(self) -> None:
        """進入 GUI mainloop（阻塞至視窗關閉）。"""
        # 1. 啟動 async runner
        self.async_runner.start()

        # 2. 啟動健康監控（後台輪詢）
        self.async_runner.submit(self.lan_client.start_health_monitor())

        # 3. 同步執行一次健康檢查並驗證版本
        try:
            self.perform_health_check()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Initial health check raised: %s", exc)

        # 4. tkinter mainloop（主執行緒）
        try:
            self.gui.mainloop()
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """關閉應用程式：停止背景 loop、釋放錄音資源。"""
        logger.info("Shutting down App")
        try:
            if self.audio_recorder.is_recording:
                self.audio_recorder.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.lan_client.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.async_runner.stop()
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------------
# CLI 入口
# ----------------------------------------------------------------------


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SoapVoice LAN 瘦客戶端",
        prog="soapvoice-client",
    )
    parser.add_argument(
        "--server-url",
        default=None,
        help="伺服器 URL（覆蓋 SOAPVOICE_SERVER_URL 環境變數）",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="本機暫存目錄（預設 %%LOCALAPPDATA%%/SoapVoice/cache）",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG 等級日誌")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """應用程式進入點。

    Returns:
        0 正常結束；1 啟動失敗。
    """
    args = _parse_args(argv)

    # 構建設定
    config = LANConfig.from_env()
    if args.server_url:
        config.server_url = args.server_url
    if args.cache_dir:
        config.local_cache_dir = args.cache_dir

    # 日誌（log file 放在快取目錄旁）
    log_dir = Path(config.local_cache_dir).parent / "logs"
    _configure_logging(log_dir, verbose=args.verbose)

    logger.info("=" * 60)
    logger.info("SoapVoice LAN Client starting")
    logger.info("Server URL : %s", config.server_url)
    logger.info("Cache Dir  : %s", config.local_cache_dir)
    logger.info("Min API ver: %s", config.min_api_version)
    logger.info("=" * 60)

    try:
        app = App(config)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to initialise App: %s", exc)
        return 1

    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in mainloop: %s", exc)
        return 1
    finally:
        try:
            app.shutdown()
        except Exception:  # noqa: BLE001
            pass

    logger.info("SoapVoice LAN Client exited")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = ["App", "AsyncRunner", "main"]
