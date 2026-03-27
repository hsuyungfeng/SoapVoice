"""
檔案監控 API 端點

提供 REST API 介面控制檔案監控服務
"""

import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pydantic import BaseModel

from src.services.file_monitor import get_file_monitor, initialize_file_monitor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/file-monitor", tags=["File Monitor"])


# 請求模型
class FileMonitorInitRequest(BaseModel):
    """初始化請求"""

    watch_dir: str = Field("watch", description="監控目錄")
    processed_dir: str = Field("watch/processed", description="處理完成目錄")
    failed_dir: str = Field("watch/failed", description="處理失敗目錄")


class FileProcessRequest(BaseModel):
    """檔案處理請求"""

    file_path: str = Field(..., description="檔案路徑")


# 端點
@router.post("/init")
async def init_file_monitor(request: FileMonitorInitRequest) -> Dict[str, Any]:
    """初始化檔案監控服務"""
    try:
        monitor = initialize_file_monitor(
            watch_dir=request.watch_dir,
            processed_dir=request.processed_dir,
            failed_dir=request.failed_dir,
        )
        return {
            "status": "initialized",
            "watch_dir": request.watch_dir,
            "processed_dir": request.processed_dir,
            "failed_dir": request.failed_dir,
        }
    except Exception as e:
        logger.error(f"Failed to initialize file monitor: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_file_monitor() -> Dict[str, str]:
    """啟動檔案監控"""
    monitor = get_file_monitor()
    monitor.start()
    return {"status": "started"}


@router.post("/stop")
async def stop_file_monitor() -> Dict[str, str]:
    """停止檔案監控"""
    monitor = get_file_monitor()
    monitor.stop()
    return {"status": "stopped"}


@router.get("/status")
async def get_monitor_status() -> Dict[str, Any]:
    """取得監控狀態"""
    monitor = get_file_monitor()
    return monitor.get_status()


@router.get("/files/{file_path:path}")
async def get_file_info(file_path: str) -> Dict[str, Any]:
    """取得檔案資訊"""
    monitor = get_file_monitor()
    info = monitor.get_file_info(file_path)

    if not info:
        raise HTTPException(status_code=404, detail="File not found")

    return info


@router.post("/clear")
async def clear_completed() -> Dict[str, Any]:
    """清除已完成的記錄"""
    monitor = get_file_monitor()
    if hasattr(monitor, "_watcher") and monitor._watcher:
        count = monitor._watcher.clear_completed()
        return {"cleared": count}
    return {"cleared": 0}


@router.get("/health")
async def file_monitor_health() -> Dict[str, str]:
    """健康檢查"""
    return {"status": "healthy", "service": "file-monitor"}


# 自動初始化
def init_file_monitor_on_startup():
    """啟動時自動初始化"""
    try:
        initialize_file_monitor()
        logger.info("File monitor auto-initialized")
    except Exception as e:
        logger.warning(f"Failed to auto-initialize file monitor: {e}")
