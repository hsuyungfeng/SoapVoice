"""本機暫存管理模組

職責：
- 管理待上傳隊列（音檔 + 截圖 + 患者資訊）
- 持久化為 JSON 檔案，供應用程式重啟後恢復
- 支援新增、移除、查詢、重試計數遞增
- 隊列上限 10 筆，超過時自動刪除最舊項目並記 warning

暫存目錄結構（Windows: %LOCALAPPDATA%/SoapVoice/）：
    cache/                          ← LANConfig.local_cache_dir
        pending/                    ← LocalStorageManager.pending_dir
            queue.json              ← 序列化隊列（單一檔案）

使用：
    >>> from client.local_storage import LocalStorageManager
    >>> mgr = LocalStorageManager("/tmp/cache")
    >>> mgr.add_pending(
    ...     session_id="20260427_103000_a1b2c3d4",
    ...     audio_path="/tmp/audio.wav",
    ...     screenshot_path="/tmp/screenshot.jpg",
    ...     patient_name="王大明",
    ... )
    True
    >>> mgr.get_queue_size()
    1
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# 隊列上限（超過時自動刪除最舊）
MAX_PENDING_UPLOADS = 10


def _now_iso() -> str:
    """產生當前時間的 ISO 8601 字串。"""
    return datetime.now().isoformat()


@dataclass
class PendingUpload:
    """暫存上傳紀錄。

    Attributes:
        session_id: 唯一識別字串（建議 YYYYMMDD_HHMMSS_xxxxxxxx 格式）
        audio_path: 音檔絕對路徑
        screenshot_path: 截圖絕對路徑
        patient_name: 患者姓名（可空）
        doctor_name: 醫師姓名（可空）
        queued_at: 入隊時間戳（ISO 8601）
        retry_count: 已嘗試重試次數（初始為 0）
    """

    session_id: str
    audio_path: str
    screenshot_path: str
    patient_name: str = ""
    doctor_name: str = ""
    queued_at: str = field(default_factory=_now_iso)
    retry_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """序列化為 dict（供 JSON 寫入）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingUpload":
        """從 dict 反序列化（容錯：缺欄位以預設值填補）。"""
        return cls(
            session_id=str(data.get("session_id", "")),
            audio_path=str(data.get("audio_path", "")),
            screenshot_path=str(data.get("screenshot_path", "")),
            patient_name=str(data.get("patient_name", "")),
            doctor_name=str(data.get("doctor_name", "")),
            queued_at=str(data.get("queued_at", _now_iso())),
            retry_count=int(data.get("retry_count", 0)),
        )


class LocalStorageManager:
    """本機暫存管理器。

    設計原則：
    1. 單一 queue.json 集中管理（簡化載入邏輯，原子寫入）
    2. 啟動時自動載入既有隊列
    3. 任何狀態變更皆觸發 _save_queue()（持久化）
    4. 隊列上限 MAX_PENDING_UPLOADS = 10，溢出時自動刪除最舊
    5. 載入失敗時記 error 並回傳空隊列（避免崩潰）

    Attributes:
        storage_dir: 根快取目錄（如 ~/AppData/Local/SoapVoice/cache）
        pending_dir: 暫存子目錄（storage_dir/pending）
        queue_file: 隊列序列化檔案（pending_dir/queue.json）
        pending_uploads: 內存中的暫存清單
    """

    def __init__(self, storage_dir: str, max_pending: int = MAX_PENDING_UPLOADS):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.pending_dir = self.storage_dir / "pending"
        self.pending_dir.mkdir(parents=True, exist_ok=True)

        self.queue_file = self.pending_dir / "queue.json"
        self.max_pending = max(1, max_pending)
        self.pending_uploads: List[PendingUpload] = []

        # 啟動時載入既有隊列
        self._load_queue()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------

    def _load_queue(self) -> None:
        """從 queue.json 載入既有隊列。

        失敗時記 error 並回傳空隊列（不丟例外）。
        """
        if not self.queue_file.exists():
            self.pending_uploads = []
            return

        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                logger.error("queue.json content is not a list, resetting")
                self.pending_uploads = []
                return
            self.pending_uploads = [PendingUpload.from_dict(item) for item in data]
            logger.info("Loaded %d pending uploads from queue", len(self.pending_uploads))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.error("Failed to load queue from %s: %s", self.queue_file, exc)
            self.pending_uploads = []

    def _save_queue(self) -> None:
        """將隊列序列化到 queue.json。

        使用「寫入臨時檔 → 替換」原子操作避免半寫狀態。
        """
        tmp_file = self.queue_file.with_suffix(".json.tmp")
        try:
            data = [p.to_dict() for p in self.pending_uploads]
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            # 原子替換（POSIX/Windows 皆支援）
            tmp_file.replace(self.queue_file)
            logger.debug("Queue saved (%d items)", len(self.pending_uploads))
        except OSError as exc:
            logger.error("Failed to save queue to %s: %s", self.queue_file, exc)
            # 清理半寫的臨時檔
            try:
                tmp_file.unlink(missing_ok=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # 隊列操作
    # ------------------------------------------------------------------

    def add_pending(
        self,
        session_id: str,
        audio_path: str,
        screenshot_path: str,
        patient_name: str = "",
        doctor_name: str = "",
    ) -> bool:
        """新增待上傳項目。

        Args:
            session_id: 唯一識別字串
            audio_path: 音檔路徑（必須存在於檔案系統）
            screenshot_path: 截圖路徑（不強制檢查存在性，允許文字記錄）
            patient_name: 患者姓名
            doctor_name: 醫師姓名

        Returns:
            True 成功；False 若音檔不存在或寫入失敗。

        副作用：若隊列已達上限，自動刪除最舊項目並記 warning。
        """
        # 驗證音檔存在（截圖可能在錄音停止時才補拍，故不強制）
        if not Path(audio_path).is_file():
            logger.error("Audio file not found: %s", audio_path)
            return False

        # 隊列上限檢查（先 drop 後 add，避免短暫超限）
        if len(self.pending_uploads) >= self.max_pending:
            self._remove_oldest()

        pending = PendingUpload(
            session_id=session_id,
            audio_path=str(audio_path),
            screenshot_path=str(screenshot_path),
            patient_name=patient_name or "",
            doctor_name=doctor_name or "",
        )
        self.pending_uploads.append(pending)
        self._save_queue()

        logger.info(
            "Added pending upload: session_id=%s, queue_size=%d",
            session_id,
            len(self.pending_uploads),
        )
        return True

    def get_all_pending(self) -> List[PendingUpload]:
        """取得所有待上傳項目（淺拷貝，呼叫端不影響內部狀態）。"""
        return list(self.pending_uploads)

    def get_next_pending(self) -> Optional[PendingUpload]:
        """取得隊列首項（最舊待重試）。隊列空時回傳 None。"""
        return self.pending_uploads[0] if self.pending_uploads else None

    def remove_pending(self, session_id: str) -> bool:
        """移除特定項目（成功上傳後呼叫）。

        Returns:
            True 移除成功；False 找不到該 session_id。
        """
        original_count = len(self.pending_uploads)
        self.pending_uploads = [p for p in self.pending_uploads if p.session_id != session_id]

        if len(self.pending_uploads) < original_count:
            self._save_queue()
            logger.info("Removed pending upload: session_id=%s", session_id)
            return True

        logger.debug("remove_pending: session_id=%s not found", session_id)
        return False

    def increment_retry_count(self, session_id: str) -> bool:
        """增加特定項目的重試計數。

        Returns:
            True 找到並更新；False 找不到該 session_id。
        """
        for pending in self.pending_uploads:
            if pending.session_id == session_id:
                pending.retry_count += 1
                self._save_queue()
                logger.debug(
                    "Incremented retry_count for %s → %d",
                    session_id,
                    pending.retry_count,
                )
                return True
        return False

    def _remove_oldest(self) -> Optional[PendingUpload]:
        """移除最舊的項目（隊列滿時呼叫）。

        Returns:
            被移除的項目；隊列空時回傳 None。
        """
        if not self.pending_uploads:
            return None
        oldest = self.pending_uploads.pop(0)
        logger.warning(
            "Pending queue full (max=%d), removed oldest: session_id=%s",
            self.max_pending,
            oldest.session_id,
        )
        self._save_queue()
        return oldest

    def clear_all(self) -> None:
        """清空所有待上傳項目（測試/管理用，謹慎）。"""
        count = len(self.pending_uploads)
        self.pending_uploads.clear()
        self._save_queue()
        if count:
            logger.warning("Cleared all %d pending uploads", count)

    def get_queue_size(self) -> int:
        """取得當前隊列大小。"""
        return len(self.pending_uploads)

    def find_by_session_id(self, session_id: str) -> Optional[PendingUpload]:
        """以 session_id 查詢項目（找不到回傳 None）。"""
        for pending in self.pending_uploads:
            if pending.session_id == session_id:
                return pending
        return None


__all__ = [
    "LocalStorageManager",
    "PendingUpload",
    "MAX_PENDING_UPLOADS",
]
