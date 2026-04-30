"""
警報管理 REST API — 查詢、確認、清除警報

提供五個端點：
1. GET    /api/v1/alerts           — 查詢警報（支援分頁與嚴重程度篩選）
2. POST   /api/v1/alerts/{id}/acknowledge — 確認警報
3. DELETE /api/v1/alerts/{id}      — 清除警報
4. GET    /api/v1/alerts/history   — 查詢歷史警報
5. GET    /api/v1/alerts/active    — 取得活躍警報（前端輪詢用）

用途：Phase 12-03 即時警報系統的 REST 介面。
"""

import logging
import math
import time
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


# ── 輔助函式 ───────────────────────────────────────────────────

def _alert_to_dict(alert) -> dict:
    """將 Alert 物件轉為可序列化的字典"""
    return {
        "id": alert.id,
        "type": alert.type,
        "severity": alert.severity,
        "threshold": alert.threshold,
        "current_value": alert.current_value,
        "triggered_at": alert.triggered_at,
        "acknowledged_at": alert.acknowledged_at,
        "acknowledged_by": alert.acknowledged_by,
        "message": alert.message,
        "cleared_at": alert.cleared_at,
    }


def _get_alert_manager(request: Request):
    """從 app.state 取得 AlertManager 實例"""
    manager = getattr(request.app.state, "alert_manager", None)
    if manager is None:
        logger.warning("AlertManager 未在 app.state 中初始化")
    return manager


async def _get_alerts_db(request: Request):
    """從 app.state 取得警報 DB 連線"""
    db = getattr(request.app.state, "alerts_db", None)
    if db is None:
        logger.warning("alerts_db 未在 app.state 中初始化")
    return db


# ── 端點 1：查詢警報列表 ────────────────────────────────────────

@router.get("", name="get_alerts")
async def get_alerts(
    request: Request,
    severity: Optional[str] = Query(
        None,
        description="嚴重程度篩選（warning/critical/all），None 表示全部",
    ),
    page: int = Query(1, ge=1, description="頁碼（從 1 開始）"),
    page_size: int = Query(50, ge=1, le=100, description="每頁筆數（最大 100）"),
    include_history: bool = Query(False, description="是否包含已確認/已清除的警報"),
):
    """查詢警報列表

    Query Parameters:
        severity: 嚴重程度篩選（"warning"/"critical"/"all"），預設返回全部
        page: 頁碼（預設 1）
        page_size: 每頁筆數（預設 50，最大 100）
        include_history: 若 True 則包含已確認/已清除警報（預設 False）

    Returns:
        {"alerts": [...], "total": N, "page": 1, "total_pages": M}
    """
    if severity == "all":
        severity = None

    if severity is not None and severity not in ("warning", "critical"):
        raise HTTPException(status_code=400, detail=f"無效的嚴重程度值：{severity}，允許值：warning、critical、all")

    alert_manager = _get_alert_manager(request)
    db = await _get_alerts_db(request)

    try:
        if include_history and db is not None:
            from src.db.alerts_db import get_alert_history
            all_alerts = await get_alert_history(db, limit=1000, severity=severity, days=365)
        elif alert_manager is not None:
            all_alerts = alert_manager.get_active_alerts()
            if severity is not None:
                all_alerts = [a for a in all_alerts if a.severity == severity]
        else:
            all_alerts = []

        total = len(all_alerts)
        total_pages = max(1, math.ceil(total / page_size))
        start = (page - 1) * page_size
        end = start + page_size
        page_alerts = all_alerts[start:end]

        return {
            "alerts": [_alert_to_dict(a) for a in page_alerts],
            "total": total,
            "page": page,
            "total_pages": total_pages,
        }
    except Exception as e:
        logger.error(f"查詢警報失敗: {e}")
        raise HTTPException(status_code=500, detail=f"查詢警報失敗: {str(e)}")


# ── 端點 2：確認警報 ────────────────────────────────────────────

@router.post("/{alert_id}/acknowledge", name="acknowledge_alert")
async def acknowledge_alert(
    alert_id: str,
    request: Request,
    user: str = Query(..., description="確認者名稱（必填）"),
):
    """確認警報

    將指定警報標記為已確認，記錄確認者與確認時間。

    Args:
        alert_id: 警報 UUID
        user: 確認者名稱（必填）

    Returns:
        {"status": "acknowledged", "acknowledged_at": timestamp}
    """
    if not user or not user.strip():
        raise HTTPException(status_code=400, detail="確認者名稱 (user) 不得為空")

    alert_manager = _get_alert_manager(request)
    db = await _get_alerts_db(request)

    # 先從 alert_manager 確認
    alert = None
    if alert_manager is not None:
        alert = alert_manager.acknowledge_alert(alert_id, user=user.strip())

    # 同步更新 DB
    if db is not None:
        try:
            from src.db.alerts_db import update_alert_acknowledged
            await update_alert_acknowledged(db, alert_id, user=user.strip())
        except Exception as e:
            logger.warning(f"更新 DB 警報確認狀態失敗（非致命）: {e}")

    if alert is None:
        raise HTTPException(status_code=404, detail=f"警報不存在或已清除：{alert_id}")

    return {
        "status": "acknowledged",
        "acknowledged_at": alert.acknowledged_at,
        "acknowledged_by": alert.acknowledged_by,
    }


# ── 端點 3：清除警報 ────────────────────────────────────────────

@router.delete("/{alert_id}", name="clear_alert")
async def clear_alert(
    alert_id: str,
    request: Request,
):
    """清除警報

    從活躍警報中移除指定警報。

    Args:
        alert_id: 警報 UUID

    Returns:
        {"status": "cleared"}
    """
    alert_manager = _get_alert_manager(request)
    db = await _get_alerts_db(request)

    cleared = False
    if alert_manager is not None:
        cleared = alert_manager.clear_alert(alert_id)

    # 同步更新 DB
    if db is not None:
        try:
            from src.db.alerts_db import update_alert_cleared
            await update_alert_cleared(db, alert_id)
        except Exception as e:
            logger.warning(f"更新 DB 警報清除狀態失敗（非致命）: {e}")

    if not cleared:
        raise HTTPException(status_code=404, detail=f"警報不存在或已清除：{alert_id}")

    return {"status": "cleared"}


# ── 端點 4：查詢歷史警報 ─────────────────────────────────────────

@router.get("/history", name="get_alert_history")
async def get_alert_history_endpoint(
    request: Request,
    limit: int = Query(100, ge=1, le=500, description="最多回傳筆數（最大 500）"),
    severity: Optional[str] = Query(
        None,
        description="嚴重程度篩選（warning/critical），None 表示全部",
    ),
    days: int = Query(7, ge=1, le=365, description="查詢天數範圍（1-365）"),
):
    """查詢歷史警報

    Query Parameters:
        limit: 最多回傳筆數（預設 100，最大 500）
        severity: 嚴重程度篩選
        days: 查詢天數範圍（預設 7）

    Returns:
        {"alerts": [...], "total": N, "days": 7}
    """
    if severity is not None and severity not in ("warning", "critical"):
        raise HTTPException(status_code=400, detail=f"無效的嚴重程度值：{severity}")

    db = await _get_alerts_db(request)
    alert_manager = _get_alert_manager(request)

    try:
        if db is not None:
            from src.db.alerts_db import get_alert_history
            alerts = await get_alert_history(db, limit=limit, severity=severity, days=days)
        elif alert_manager is not None:
            alerts = alert_manager.get_history(limit=limit, severity=severity)
        else:
            alerts = []

        return {
            "alerts": [_alert_to_dict(a) for a in alerts],
            "total": len(alerts),
            "days": days,
        }
    except Exception as e:
        logger.error(f"查詢歷史警報失敗: {e}")
        raise HTTPException(status_code=500, detail=f"查詢歷史警報失敗: {str(e)}")


# ── 端點 5：取得活躍警報（前端輪詢） ──────────────────────────────

@router.get("/active", name="get_active_alerts")
async def get_active_alerts_endpoint(request: Request):
    """取得活躍（未確認且未清除）警報

    此端點專為前端 5 秒輪詢設計，無分頁，直接回傳全部活躍警報。

    Returns:
        {"alerts": [...], "total": N, "timestamp": current_unix_timestamp}
    """
    alert_manager = _get_alert_manager(request)

    try:
        if alert_manager is not None:
            # 只回傳未確認的警報
            active = [
                a for a in alert_manager.get_active_alerts()
                if a.acknowledged_at is None
            ]
        else:
            active = []

        return {
            "alerts": [_alert_to_dict(a) for a in active],
            "total": len(active),
            "timestamp": time.time(),
        }
    except Exception as e:
        logger.error(f"取得活躍警報失敗: {e}")
        raise HTTPException(status_code=500, detail=f"取得活躍警報失敗: {str(e)}")
