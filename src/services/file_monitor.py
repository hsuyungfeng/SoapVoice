"""
檔案監控服務模組

監控 watch/ 目錄，自動處理新增的音訊檔案
支援自動轉錄和 SOAP 生成
"""

import os
import logging
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import threading

logger = logging.getLogger(__name__)


class FileStatus(Enum):
    """檔案狀態"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WatchedFile:
    """監控的檔案"""

    file_path: str
    status: FileStatus = FileStatus.PENDING
    created_at: float = field(default_factory=time.time)
    processed_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    file_hash: Optional[str] = None


class FileWatcher:
    """檔案監控器

    監控指定目錄的新增檔案，觸發回調函數處理
    """

    def __init__(
        self,
        watch_dir: str = "watch",
        processed_dir: str = "watch/processed",
        failed_dir: str = "watch/failed",
        extensions: List[str] = None,
        callback: Optional[Callable] = None,
        poll_interval: float = 2.0,
    ):
        """初始化檔案監控器

        Args:
            watch_dir: 監控目錄
            processed_dir: 處理完成目錄
            failed_dir: 處理失敗目錄
            extensions: 監控的檔案副檔名
            callback: 檔案處理回調函數
            poll_interval: 輪詢間隔（秒）
        """
        self.watch_dir = Path(watch_dir)
        self.processed_dir = Path(processed_dir)
        self.failed_dir = Path(failed_dir)
        self.extensions = extensions or [".wav", ".mp3", ".m4a", ".flac", ".ogg"]
        self.callback = callback
        self.poll_interval = poll_interval

        self._watched_files: Dict[str, WatchedFile] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 建立目錄
        self._create_directories()

    def _create_directories(self) -> None:
        """建立必要目錄"""
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.failed_dir.mkdir(parents=True, exist_ok=True)

    def _calculate_hash(self, file_path: Path) -> str:
        """計算檔案雜湊"""
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""

    def _is_watched_file(self, file_path: Path) -> bool:
        """檢查是否為監控的檔案"""
        return file_path.suffix.lower() in self.extensions

    def scan_directory(self) -> List[Path]:
        """掃描目錄中的新檔案

        Returns:
            新檔案列表
        """
        new_files = []

        if not self.watch_dir.exists():
            return new_files

        for file_path in self.watch_dir.iterdir():
            if not file_path.is_file():
                continue

            if not self._is_watched_file(file_path):
                continue

            # 檢查是否已存在於監控列表
            file_key = str(file_path)
            if file_key in self._watched_files:
                continue

            # 計算檔案雜湊
            file_hash = self._calculate_hash(file_path)

            # 建立監控記錄
            watched_file = WatchedFile(
                file_path=file_key,
                file_hash=file_hash,
            )
            self._watched_files[file_key] = watched_file
            new_files.append(file_path)
            logger.info(f"New file detected: {file_path.name}")

        return new_files

    def process_file(self, file_path: Path) -> Dict[str, Any]:
        """處理檔案

        Args:
            file_path: 檔案路徑

        Returns:
            處理結果
        """
        file_key = str(file_path)
        watched_file = self._watched_files.get(file_key)

        if not watched_file:
            return {"error": "File not in watch list"}

        # 更新狀態
        watched_file.status = FileStatus.PROCESSING

        try:
            # 執行回調函數
            if self.callback:
                result = self.callback(file_path)
                watched_file.result = result
                watched_file.status = FileStatus.COMPLETED
                watched_file.processed_at = time.time()

                # 移動到處理完成目錄
                self._move_file(file_path, self.processed_dir)
                logger.info(f"File processed successfully: {file_path.name}")

                return result
            else:
                # 沒有回調函數，返回基本資訊
                result = {
                    "file_name": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "status": "no_callback",
                }
                watched_file.result = result
                watched_file.status = FileStatus.COMPLETED

                return result

        except Exception as e:
            watched_file.status = FileStatus.FAILED
            watched_file.error = str(e)
            logger.error(f"File processing failed: {file_path.name}, error: {e}")

            # 移動到失敗目錄
            self._move_file(file_path, self.failed_dir)

            return {"error": str(e)}

    def _move_file(self, file_path: Path, target_dir: Path) -> None:
        """移動檔案到目標目錄"""
        try:
            target_path = target_dir / file_path.name
            # 如果檔案已存在，加入時間戳
            if target_path.exists():
                target_path = target_dir / f"{int(time.time())}_{file_path.name}"
            file_path.rename(target_path)
        except Exception as e:
            logger.error(f"Failed to move file: {e}")

    def get_status(self) -> Dict[str, Any]:
        """取得監控狀態

        Returns:
            狀態資訊
        """
        status_counts = {
            FileStatus.PENDING: 0,
            FileStatus.PROCESSING: 0,
            FileStatus.COMPLETED: 0,
            FileStatus.FAILED: 0,
        }

        for watched_file in self._watched_files.values():
            status_counts[watched_file.status] += 1

        return {
            "watch_dir": str(self.watch_dir),
            "total_files": len(self._watched_files),
            "pending": status_counts[FileStatus.PENDING],
            "processing": status_counts[FileStatus.PROCESSING],
            "completed": status_counts[FileStatus.COMPLETED],
            "failed": status_counts[FileStatus.FAILED],
        }

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """取得檔案資訊

        Args:
            file_path: 檔案路徑

        Returns:
            檔案資訊
        """
        watched_file = self._watched_files.get(file_path)
        if not watched_file:
            return None

        return {
            "file_path": watched_file.file_path,
            "status": watched_file.status.value,
            "created_at": watched_file.created_at,
            "processed_at": watched_file.processed_at,
            "error": watched_file.error,
            "result": watched_file.result,
        }

    def clear_completed(self) -> int:
        """清除已完成的記錄

        Returns:
            清除的數量
        """
        completed_keys = [
            key
            for key, watched_file in self._watched_files.items()
            if watched_file.status in [FileStatus.COMPLETED, FileStatus.FAILED]
        ]

        for key in completed_keys:
            del self._watched_files[key]

        return len(completed_keys)

    def start(self) -> None:
        """開始監控"""
        if self._running:
            logger.warning("Watcher already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        logger.info(f"File watcher started: {self.watch_dir}")

    def stop(self) -> None:
        """停止監控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("File watcher stopped")

    def _watch_loop(self) -> None:
        """監控迴圈"""
        while self._running:
            try:
                # 掃描新檔案
                new_files = self.scan_directory()

                # 處理新檔案
                for file_path in new_files:
                    self.process_file(file_path)

            except Exception as e:
                logger.error(f"Watch loop error: {e}")

            # 等待下一次掃描
            time.sleep(self.poll_interval)


# 整合 FastAPI 的檔案監控服務
class FileMonitorService:
    """檔案監控服務

    提供 FastAPI 整合的檔案監控功能
    """

    def __init__(self):
        self._watcher: Optional[FileWatcher] = None
        self._callbacks: Dict[str, Callable] = {}

    def initialize(
        self,
        watch_dir: str = "watch",
        processed_dir: str = "watch/processed",
        failed_dir: str = "watch/failed",
    ) -> None:
        """初始化監控服務

        Args:
            watch_dir: 監控目錄
            processed_dir: 處理完成目錄
            failed_dir: 處理失敗目錄
        """
        self._watcher = FileWatcher(
            watch_dir=watch_dir,
            processed_dir=processed_dir,
            failed_dir=failed_dir,
            callback=self._default_callback,
        )
        logger.info(f"File monitor service initialized: {watch_dir}")

    def _default_callback(self, file_path: Path) -> Dict[str, Any]:
        """預設回調函數

        Args:
            file_path: 檔案路徑

        Returns:
            處理結果
        """
        return {
            "file_name": file_path.name,
            "file_size": file_path.stat().st_size,
            "status": "queued",
            "message": "File detected, ready for processing",
        }

    def register_callback(self, event: str, callback: Callable) -> None:
        """註冊回調函數

        Args:
            event: 事件類型
            callback: 回調函數
        """
        self._callbacks[event] = callback

    def start(self) -> None:
        """開始監控"""
        if self._watcher:
            self._watcher.start()

    def stop(self) -> None:
        """停止監控"""
        if self._watcher:
            self._watcher.stop()

    def get_status(self) -> Dict[str, Any]:
        """取得狀態"""
        if self._watcher:
            return self._watcher.get_status()
        return {"error": "Watcher not initialized"}

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """取得檔案資訊"""
        if self._watcher:
            return self._watcher.get_file_info(file_path)
        return None


# 全域監控服務實例
_file_monitor: Optional[FileMonitorService] = None


def get_file_monitor() -> FileMonitorService:
    """取得檔案監控服務"""
    global _file_monitor
    if _file_monitor is None:
        _file_monitor = FileMonitorService()
    return _file_monitor


def initialize_file_monitor(
    watch_dir: str = "watch",
    processed_dir: str = "watch/processed",
    failed_dir: str = "watch/failed",
) -> FileMonitorService:
    """初始化檔案監控服務

    Args:
        watch_dir: 監控目錄
        processed_dir: 處理完成目錄
        failed_dir: 處理失敗目錄

    Returns:
        檔案監控服務
    """
    monitor = get_file_monitor()
    monitor.initialize(watch_dir, processed_dir, failed_dir)
    return monitor
