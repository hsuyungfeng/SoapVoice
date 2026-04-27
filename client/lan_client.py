"""LAN 客戶端核心邏輯

職責：
- 版本/服務健康檢查（呼叫 /api/v1/health）
- 後台連線狀態輪詢（每 N 秒，更新 GUI 指示燈）
- 上傳問診（multipart：音檔 + 截圖 + 病患/醫師資訊）
- 失敗自動暫存至本機 JSON 隊列（指數退避重試）
- 連線恢復後自動補傳

完全與 GUI 解耦：透過 callback 通知（同步或 awaitable 皆可）。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from client.http_client import AsyncHTTPClient, HTTPClientError
from client.lan_config import LANConfig

logger = logging.getLogger(__name__)


# 連線狀態列舉（字串常數，便於 GUI 對照表）
HEALTH_UNKNOWN = "unknown"
HEALTH_HEALTHY = "healthy"
HEALTH_DEGRADED = "degraded"
HEALTH_OFFLINE = "offline"

ALL_HEALTH_STATES = (HEALTH_UNKNOWN, HEALTH_HEALTHY, HEALTH_DEGRADED, HEALTH_OFFLINE)


# 回調簽名：可接受同步或非同步函式
StatusCallback = Callable[[str], Union[None, Awaitable[None]]]
ResultCallback = Callable[[Dict[str, Any]], Union[None, Awaitable[None]]]


@dataclass
class PendingUpload:
    """本機暫存待重試的上傳項目。"""

    audio_path: str
    screenshot_path: str
    patient_name: str
    doctor_name: str
    queued_at: str
    retry_count: int = 0
    cache_file: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _semver_tuple(version: str) -> tuple:
    """將 SemVer 字串轉為整數 tuple，便於比較。

    無效格式回傳 (0,) 以避免 ValueError。
    """
    if not version:
        return (0,)
    parts = []
    for chunk in version.split("."):
        # 取數字前綴（如 "1.2.0-rc1" → 1, 2, 0）
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts) or (0,)


async def _maybe_await(callback: Optional[Callable], *args) -> None:
    """執行同步或非同步 callback，安全忽略 None。"""
    if callback is None:
        return
    try:
        result = callback(*args)
        if inspect.isawaitable(result):
            await result
    except Exception as exc:  # noqa: BLE001 — 不讓 callback 例外崩潰主流程
        logger.exception("Callback raised exception: %s", exc)


class LANClient:
    """LAN 客戶端核心邏輯。

    設計原則：
    1. 不持有 httpx client（每次請求建立短連線，避免事件循環雜訊）
    2. 健康狀態為純字串，GUI 自行對照顏色
    3. 上傳失敗 → 本機暫存 JSON → 連線恢復後補傳
    """

    def __init__(self, config: LANConfig):
        self.config = config
        self.health_status: str = HEALTH_UNKNOWN
        self.last_health_response: Optional[Dict[str, Any]] = None
        self.last_health_error: Optional[str] = None

        self.connection_status_callback: Optional[StatusCallback] = None
        self.result_callback: Optional[ResultCallback] = None

        # 本機暫存隊列
        self.pending_uploads: List[PendingUpload] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        self._ensure_cache_dir()

    # ------------------------------------------------------------------
    # 內部輔助
    # ------------------------------------------------------------------

    def _ensure_cache_dir(self) -> None:
        Path(self.config.local_cache_dir).mkdir(parents=True, exist_ok=True)

    async def _set_status(self, status: str, *, error: Optional[str] = None) -> None:
        """更新 health_status 並通知 GUI。"""
        if status not in ALL_HEALTH_STATES:
            logger.warning("Unknown health status: %s, falling back to 'unknown'", status)
            status = HEALTH_UNKNOWN
        prev = self.health_status
        self.health_status = status
        self.last_health_error = error
        if prev != status:
            logger.info("Health status: %s → %s", prev, status)
        await _maybe_await(self.connection_status_callback, status)

    # ------------------------------------------------------------------
    # 健康檢查
    # ------------------------------------------------------------------

    async def check_health(self) -> bool:
        """檢查伺服器健康狀態。

        Returns:
            True 若為 healthy；False 若 degraded/offline。

        副作用：更新 self.health_status 與 callback。
        """
        try:
            async with AsyncHTTPClient(
                self.config.server_url,
                timeout=self.config.connection_timeout_sec,
                max_retries=1,  # 健康檢查不重試（避免燃燒事件循環）
            ) as client:
                result = await client.get(self.config.health_endpoint)
                self.last_health_response = result

                version = result.get("version", "")
                if _semver_tuple(version) < _semver_tuple(self.config.min_api_version):
                    msg = f"Server version {version} < required {self.config.min_api_version}"
                    logger.warning(msg)
                    await self._set_status(HEALTH_DEGRADED, error=msg)
                    return False

                # 服務檢查
                services = result.get("services", {}) or {}
                for svc in self.config.required_services:
                    state = services.get(svc)
                    if state != "ready":
                        msg = f"Service {svc} not ready (state={state})"
                        logger.warning(msg)
                        await self._set_status(HEALTH_DEGRADED, error=msg)
                        return False

                await self._set_status(HEALTH_HEALTHY)
                # 連線恢復 → 嘗試補傳暫存
                if self.pending_uploads:
                    asyncio.create_task(self.retry_pending_uploads())
                return True

        except HTTPClientError as exc:
            await self._set_status(HEALTH_OFFLINE, error=str(exc))
            return False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected health check error: %s", exc)
            await self._set_status(HEALTH_OFFLINE, error=str(exc))
            return False

    async def start_health_monitor(self) -> None:
        """後台輪詢健康狀態（迴圈直至 stop()）。"""
        logger.info("Health monitor started (interval=%ds)", self.config.health_check_interval_sec)
        while not self._stop_event.is_set():
            await self.check_health()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.config.health_check_interval_sec,
                )
            except asyncio.TimeoutError:
                continue
        logger.info("Health monitor stopped")

    def stop(self) -> None:
        """請求停止後台監控。"""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # 上傳
    # ------------------------------------------------------------------

    async def upload_consultation(
        self,
        audio_path: str,
        screenshot_path: str,
        patient_name: str = "",
        doctor_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """上傳單次問診。

        Returns:
            伺服器回應 JSON dict（含 SOAP），失敗時 None（已自動暫存）。
        """
        audio_p = Path(audio_path)
        screenshot_p = Path(screenshot_path)

        # 檔案存在性檢查（離線/未錄製情境）
        if not audio_p.is_file():
            logger.error("Audio file not found: %s", audio_path)
            return None
        if not screenshot_p.is_file():
            logger.error("Screenshot file not found: %s", screenshot_path)
            return None

        try:
            audio_bytes = audio_p.read_bytes()
            screenshot_bytes = screenshot_p.read_bytes()

            files = {
                "audio_file": (audio_p.name, audio_bytes, "audio/wav"),
                "screenshot_file": (screenshot_p.name, screenshot_bytes, "image/jpeg"),
            }
            data = {
                "patient_name": patient_name or "",
                "doctor_name": doctor_name or "",
            }

            async with AsyncHTTPClient(
                self.config.server_url,
                timeout=self.config.read_timeout_sec,
                max_retries=self.config.max_retries,
                retry_min_wait=self.config.retry_backoff_base,
            ) as client:
                result = await client.post_multipart(
                    self.config.lan_process_endpoint,
                    files=files,
                    data=data,
                )

            logger.info("Upload successful: session_id=%s", result.get("session_id"))
            await _maybe_await(self.result_callback, result)
            return result

        except HTTPClientError as exc:
            logger.error("Upload failed: %s", exc)
            self._queue_for_retry(audio_path, screenshot_path, patient_name, doctor_name)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected upload error: %s", exc)
            self._queue_for_retry(audio_path, screenshot_path, patient_name, doctor_name)
            return None

    # ------------------------------------------------------------------
    # 暫存佇列
    # ------------------------------------------------------------------

    def _queue_for_retry(
        self,
        audio_path: str,
        screenshot_path: str,
        patient_name: str,
        doctor_name: str,
    ) -> PendingUpload:
        """將失敗的上傳加入本機 JSON 暫存。"""
        if len(self.pending_uploads) >= self.config.max_pending_uploads:
            dropped = self.pending_uploads.pop(0)
            logger.warning("Pending queue full, dropping oldest: %s", dropped.audio_path)
            try:
                if dropped.cache_file:
                    Path(dropped.cache_file).unlink(missing_ok=True)
            except OSError:
                pass

        timestamp = datetime.now().isoformat()
        cache_filename = f"pending_{timestamp.replace(':', '-')}.json"
        cache_path = Path(self.config.local_cache_dir) / cache_filename

        pending = PendingUpload(
            audio_path=audio_path,
            screenshot_path=screenshot_path,
            patient_name=patient_name,
            doctor_name=doctor_name,
            queued_at=timestamp,
            retry_count=0,
            cache_file=str(cache_path),
        )

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(pending.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.error("Failed to write cache file %s: %s", cache_path, exc)

        self.pending_uploads.append(pending)
        logger.info("Queued for retry: %s (queue=%d)", cache_path, len(self.pending_uploads))
        return pending

    async def retry_pending_uploads(self) -> int:
        """連線恢復後重試暫存上傳。

        Returns:
            成功補傳的筆數。
        """
        success = 0
        # 拷貝避免迭代時修改
        items = list(self.pending_uploads)
        for pending in items:
            logger.info("Retrying pending upload: %s", pending.audio_path)
            pending.retry_count += 1

            result = await self.upload_consultation(
                audio_path=pending.audio_path,
                screenshot_path=pending.screenshot_path,
                patient_name=pending.patient_name,
                doctor_name=pending.doctor_name,
            )

            if result is not None:
                # 成功 → 移除暫存
                if pending in self.pending_uploads:
                    self.pending_uploads.remove(pending)
                if pending.cache_file:
                    Path(pending.cache_file).unlink(missing_ok=True)
                success += 1
            else:
                # 仍失敗 → 中斷，等下次健康檢查觸發
                logger.warning("Retry still failing, stopping retry loop")
                break

        return success

    def load_pending_from_disk(self) -> int:
        """啟動時從快取目錄載入未完成的上傳項目。

        Returns:
            載入的項目數。
        """
        cache_dir = Path(self.config.local_cache_dir)
        if not cache_dir.is_dir():
            return 0

        loaded = 0
        for json_file in sorted(cache_dir.glob("pending_*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                pending = PendingUpload(
                    audio_path=raw.get("audio_path", ""),
                    screenshot_path=raw.get("screenshot_path", ""),
                    patient_name=raw.get("patient_name", ""),
                    doctor_name=raw.get("doctor_name", ""),
                    queued_at=raw.get("queued_at", ""),
                    retry_count=raw.get("retry_count", 0),
                    cache_file=str(json_file),
                )
                self.pending_uploads.append(pending)
                loaded += 1
            except (OSError, json.JSONDecodeError, TypeError) as exc:
                logger.warning("Failed to load pending file %s: %s", json_file, exc)

        if loaded:
            logger.info("Loaded %d pending uploads from disk", loaded)
        return loaded
