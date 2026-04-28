"""LAN 客戶端核心邏輯（整合本機暫存與指數退避重試）

職責：
- 版本/服務健康檢查（呼叫 /api/v1/health）
- 後台連線狀態輪詢（每 N 秒，更新 GUI 指示燈）
- 上傳問診（multipart：音檔 + 截圖 + 病患/醫師資訊）
- 失敗自動暫存至 LocalStorageManager（queue.json 持久化）
- 連線恢復後自動補傳（指數退避 2-4-8 秒，最多 3 次）

設計原則：
1. 不持有 httpx client（每次請求建立短連線，避免事件循環雜訊）
2. 健康狀態為純字串，GUI 自行對照顏色
3. 上傳失敗 → 本機暫存 → 連線恢復後自動補傳
4. 應用程式重啟時，建構子自動載入 queue.json，等候連線後重試

完全與 GUI 解耦：透過 callback 通知（同步或 awaitable 皆可）。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional, Union

from client.http_client import AsyncHTTPClient, HTTPClientError
from client.lan_config import LANConfig
from client.local_storage import LocalStorageManager, PendingUpload
from client.retry_manager import RetryManager

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


def _generate_session_id() -> str:
    """生成 YYYYMMDD_HHMMSS_xxxxxxxx 格式的 session_id。

    8 碼 hex 後綴避免同秒衝突。
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = uuid.uuid4().hex[:8]
    return f"{ts}_{suffix}"


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
    """LAN 客戶端核心邏輯（整合本機暫存 + 重試）。

    Attributes:
        config: LAN 設定
        health_status: 當前連線狀態（unknown/healthy/degraded/offline）
        last_health_response: 最近一次 /health 回應 JSON
        last_health_error: 最近一次健康檢查失敗訊息
        storage: LocalStorageManager（queue.json 持久化）
        retry_manager: RetryManager（指數退避）
        pending_uploads: 向後相容屬性（透過 storage.get_all_pending() 取得）
    """

    def __init__(self, config: LANConfig):
        self.config = config
        self.health_status: str = HEALTH_UNKNOWN
        self.last_health_response: Optional[Dict[str, Any]] = None
        self.last_health_error: Optional[str] = None

        self.connection_status_callback: Optional[StatusCallback] = None
        self.result_callback: Optional[ResultCallback] = None

        # 確保快取目錄存在
        Path(self.config.local_cache_dir).mkdir(parents=True, exist_ok=True)

        # 本機暫存管理（自動載入既有 queue.json）
        self.storage = LocalStorageManager(
            self.config.local_cache_dir,
            max_pending=self.config.max_pending_uploads,
        )

        # 重試策略
        self.retry_manager = RetryManager(
            base_delay_sec=self.config.retry_backoff_base,
            max_retries=self.config.max_retries,
        )

        # 後台輪詢控制
        self._monitor_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()

        # 防止同時多個 retry 流程
        self._retry_in_progress = False

    # ------------------------------------------------------------------
    # 向後相容
    # ------------------------------------------------------------------

    @property
    def pending_uploads(self) -> list:
        """向後相容：原本 list[PendingUpload]，現透過 storage 取得。"""
        return self.storage.get_all_pending()

    def load_pending_from_disk(self) -> int:
        """向後相容：建構子已自動載入，此處僅回傳當前隊列大小。"""
        return self.storage.get_queue_size()

    # ------------------------------------------------------------------
    # 內部輔助
    # ------------------------------------------------------------------

    async def _set_status(self, status: str, *, error: Optional[str] = None) -> None:
        """更新 health_status 並通知 GUI。

        副作用：當狀態從 offline 轉為 healthy 時，觸發 retry_pending_uploads（背景任務）。
        """
        if status not in ALL_HEALTH_STATES:
            logger.warning("Unknown health status: %s, falling back to 'unknown'", status)
            status = HEALTH_UNKNOWN
        prev = self.health_status
        self.health_status = status
        self.last_health_error = error
        if prev != status:
            logger.info("Health status: %s → %s", prev, status)

        await _maybe_await(self.connection_status_callback, status)

        # 連線恢復（offline → healthy）時，自動觸發重試
        if (
            prev == HEALTH_OFFLINE
            and status == HEALTH_HEALTHY
            and self.storage.get_queue_size() > 0
            and not self._retry_in_progress
        ):
            logger.info(
                "Connection restored; scheduling retry of %d pending uploads",
                self.storage.get_queue_size(),
            )
            asyncio.create_task(self.retry_pending_uploads())
        # 首次健康檢查為 healthy 時也補傳（覆蓋應用啟動情境）
        elif (
            prev == HEALTH_UNKNOWN
            and status == HEALTH_HEALTHY
            and self.storage.get_queue_size() > 0
            and not self._retry_in_progress
        ):
            logger.info(
                "Initial healthy check; scheduling retry of %d pending uploads",
                self.storage.get_queue_size(),
            )
            asyncio.create_task(self.retry_pending_uploads())

    # ------------------------------------------------------------------
    # 健康檢查
    # ------------------------------------------------------------------

    async def check_health(self) -> bool:
        """檢查伺服器健康狀態。

        Returns:
            True 若為 healthy；False 若 degraded/offline。

        副作用：更新 self.health_status 與 callback；offline → healthy 時觸發補傳。
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
        logger.info(
            "Health monitor started (interval=%ds)", self.config.health_check_interval_sec
        )
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

    async def _do_upload(
        self,
        audio_path: str,
        screenshot_path: str,
        patient_name: str,
        doctor_name: str,
    ) -> Optional[Dict[str, Any]]:
        """實際發送 multipart POST。失敗丟出 HTTPClientError。

        Returns:
            伺服器回應 JSON dict。
        """
        audio_p = Path(audio_path)
        screenshot_p = Path(screenshot_path)

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
            return await client.post_multipart(
                self.config.lan_process_endpoint,
                files=files,
                data=data,
            )

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

        副作用：失敗時將項目加入 LocalStorageManager 隊列（queue.json 持久化）。
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
            result = await self._do_upload(
                audio_path, screenshot_path, patient_name, doctor_name
            )
            logger.info("Upload successful: session_id=%s", result.get("session_id"))
            await _maybe_await(self.result_callback, result)
            return result

        except HTTPClientError as exc:
            logger.error("Upload failed: %s", exc)
            self._enqueue_failed(audio_path, screenshot_path, patient_name, doctor_name)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected upload error: %s", exc)
            self._enqueue_failed(audio_path, screenshot_path, patient_name, doctor_name)
            return None

    # ------------------------------------------------------------------
    # 暫存佇列
    # ------------------------------------------------------------------

    def _enqueue_failed(
        self,
        audio_path: str,
        screenshot_path: str,
        patient_name: str,
        doctor_name: str,
    ) -> Optional[str]:
        """將失敗的上傳加入 LocalStorageManager。

        Returns:
            session_id（成功入隊）或 None（音檔不存在等失敗情境）。
        """
        session_id = _generate_session_id()
        ok = self.storage.add_pending(
            session_id=session_id,
            audio_path=audio_path,
            screenshot_path=screenshot_path,
            patient_name=patient_name,
            doctor_name=doctor_name,
        )
        if not ok:
            logger.error("Failed to enqueue upload: session_id=%s", session_id)
            return None
        logger.info(
            "Queued failed upload: session_id=%s queue_size=%d",
            session_id,
            self.storage.get_queue_size(),
        )
        return session_id

    # 向後相容別名
    def _queue_for_retry(
        self,
        audio_path: str,
        screenshot_path: str,
        patient_name: str,
        doctor_name: str,
    ) -> Optional[PendingUpload]:
        """向後相容：呼叫 _enqueue_failed 並回傳 PendingUpload。"""
        sid = self._enqueue_failed(audio_path, screenshot_path, patient_name, doctor_name)
        if sid is None:
            return None
        return self.storage.find_by_session_id(sid)

    async def retry_pending_uploads(self) -> int:
        """連線恢復後重試暫存上傳。

        策略：
        - 依 retry_count 計算指數退避延遲（首次 retry_count=0 不等待）
        - 重試成功 → 從 queue.json 移除
        - 重試失敗（仍 raise HTTPClientError）→ retry_count+1，保留隊列
        - 超過 max_retries → 刪除隊列項目
        - 任一項仍失敗時中斷迴圈，等待下次健康檢查觸發

        Returns:
            成功補傳的筆數。
        """
        if self._retry_in_progress:
            logger.debug("Retry already in progress, skipping")
            return 0

        self._retry_in_progress = True
        success = 0
        try:
            while True:
                pending = self.storage.get_next_pending()
                if pending is None:
                    logger.debug("No more pending uploads to retry")
                    break

                # 已超過 max_retries → 直接移除
                if not self.retry_manager.should_retry(
                    pending.session_id, pending.retry_count
                ):
                    logger.error(
                        "Max retries (%d) reached for session_id=%s, removing from queue",
                        self.retry_manager.max_retries,
                        pending.session_id,
                    )
                    self.storage.remove_pending(pending.session_id)
                    self.retry_manager.reset_state(pending.session_id)
                    continue

                # 等待指數退避（retry_count > 0 時）
                if pending.retry_count > 0:
                    proceed = await self.retry_manager.wait_before_retry(
                        pending.retry_count
                    )
                    if not proceed:
                        # should_retry 已過但 wait_before_retry 又拒絕 → 視為已達上限
                        self.storage.remove_pending(pending.session_id)
                        continue

                logger.info(
                    "Retrying session_id=%s (attempt %d/%d)",
                    pending.session_id,
                    pending.retry_count + 1,
                    self.retry_manager.max_retries,
                )

                # 嘗試上傳
                try:
                    result = await self._do_upload(
                        audio_path=pending.audio_path,
                        screenshot_path=pending.screenshot_path,
                        patient_name=pending.patient_name,
                        doctor_name=pending.doctor_name,
                    )
                except HTTPClientError as exc:
                    logger.warning(
                        "Retry failed for session_id=%s: %s",
                        pending.session_id,
                        exc,
                    )
                    result = None
                except FileNotFoundError as exc:
                    # 檔案被刪 → 清出隊列（無法復原）
                    logger.error(
                        "File missing for session_id=%s: %s, removing from queue",
                        pending.session_id,
                        exc,
                    )
                    self.storage.remove_pending(pending.session_id)
                    self.retry_manager.reset_state(pending.session_id)
                    continue
                except Exception as exc:  # noqa: BLE001
                    logger.exception(
                        "Unexpected retry error for session_id=%s: %s",
                        pending.session_id,
                        exc,
                    )
                    result = None

                if result is not None:
                    # 成功 → 移除暫存
                    self.storage.remove_pending(pending.session_id)
                    self.retry_manager.reset_state(pending.session_id)
                    success += 1
                    logger.info(
                        "Pending upload succeeded: session_id=%s", pending.session_id
                    )
                    await _maybe_await(self.result_callback, result)
                else:
                    # 失敗 → retry_count++，保留待下次
                    self.storage.increment_retry_count(pending.session_id)
                    self.retry_manager.mark_retry_scheduled(
                        pending.session_id, pending.retry_count + 1
                    )
                    # 若 +1 後已達上限，下一輪會清出隊列；中斷此輪等下次健康檢查
                    logger.warning(
                        "Retry still failing for session_id=%s; will retry later",
                        pending.session_id,
                    )
                    break
        finally:
            self._retry_in_progress = False

        if success:
            logger.info("retry_pending_uploads completed: %d succeeded", success)
        return success


__all__ = [
    "LANClient",
    "PendingUpload",
    "HEALTH_UNKNOWN",
    "HEALTH_HEALTHY",
    "HEALTH_DEGRADED",
    "HEALTH_OFFLINE",
    "ALL_HEALTH_STATES",
    "_semver_tuple",
]
