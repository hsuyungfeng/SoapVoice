"""
警報持久層模組 — aiosqlite 警報表 Schema 初始化與 CRUD 操作

管理 alerts 表的完整生命週期：
- 自動建表（冪等性）
- 警報的插入、查詢、確認、清除
- 支援依嚴重程度篩選和按天清理舊警報

用途：Phase 12-03 即時警報系統的資料持久層。
"""

import logging
import time
from dataclasses import asdict
from typing import List, Optional

import aiosqlite

from src.utils.alert_manager import Alert

logger = logging.getLogger(__name__)


# ── Schema 初始化 ─────────────────────────────────────────────

async def init_alerts_schema(db: aiosqlite.Connection) -> None:
    """初始化警報表 Schema（冪等性）

    建立 alerts 表與索引（若已存在則跳過）。
    須在 lifespan startup 呼叫。

    Args:
        db: 已連線的 aiosqlite 連線
    """
    try:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id                TEXT PRIMARY KEY,
                type              TEXT NOT NULL,
                severity          TEXT NOT NULL,
                threshold         REAL NOT NULL,
                current_value     REAL NOT NULL,
                triggered_at      REAL NOT NULL,
                acknowledged_at   REAL DEFAULT NULL,
                acknowledged_by   TEXT DEFAULT NULL,
                message           TEXT NOT NULL,
                cleared_at        REAL DEFAULT NULL,
                created_at        REAL DEFAULT (strftime('%s','now') + (strftime('%f','now') - CAST(strftime('%S','now') AS REAL)))
            )
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_triggered_at
            ON alerts (triggered_at DESC)
        """)

        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_alerts_severity
            ON alerts (severity)
        """)

        await db.commit()
        logger.info("警報表 Schema 初始化完成（alerts, 2 indexes）")
    except Exception as e:
        logger.error(f"警報表 Schema 初始化失敗: {e}")
        raise


# ── CRUD 操作 ──────────────────────────────────────────────────

async def insert_alert(db: aiosqlite.Connection, alert: Alert) -> None:
    """插入新警報記錄

    Args:
        db: 已連線的 aiosqlite 連線
        alert: Alert 資料物件
    """
    try:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """
            INSERT OR IGNORE INTO alerts
                (id, type, severity, threshold, current_value, triggered_at,
                 acknowledged_at, acknowledged_by, message, cleared_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.id,
                alert.type,
                alert.severity,
                alert.threshold,
                alert.current_value,
                alert.triggered_at,
                alert.acknowledged_at,
                alert.acknowledged_by,
                alert.message,
                alert.cleared_at,
            ),
        )
        await db.commit()
        logger.debug(f"警報已插入 DB: {alert.id} ({alert.type}:{alert.severity})")
    except Exception as e:
        await db.rollback()
        logger.error(f"插入警報失敗: {e}")
        raise


async def update_alert_acknowledged(
    db: aiosqlite.Connection,
    alert_id: str,
    user: str,
) -> None:
    """更新警報確認狀態

    Args:
        db: 已連線的 aiosqlite 連線
        alert_id: 警報 UUID
        user: 確認者名稱
    """
    try:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """
            UPDATE alerts
            SET acknowledged_at = ?, acknowledged_by = ?
            WHERE id = ? AND acknowledged_at IS NULL
            """,
            (time.time(), user, alert_id),
        )
        await db.commit()
        logger.debug(f"警報確認狀態已更新: {alert_id} by {user}")
    except Exception as e:
        await db.rollback()
        logger.error(f"更新警報確認狀態失敗: {e}")
        raise


async def update_alert_cleared(
    db: aiosqlite.Connection,
    alert_id: str,
) -> None:
    """更新警報清除時間

    Args:
        db: 已連線的 aiosqlite 連線
        alert_id: 警報 UUID
    """
    try:
        await db.execute("BEGIN IMMEDIATE")
        await db.execute(
            """
            UPDATE alerts
            SET cleared_at = ?
            WHERE id = ? AND cleared_at IS NULL
            """,
            (time.time(), alert_id),
        )
        await db.commit()
        logger.debug(f"警報已標記清除: {alert_id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"更新警報清除狀態失敗: {e}")
        raise


async def get_alert_by_id(
    db: aiosqlite.Connection,
    alert_id: str,
) -> Optional[Alert]:
    """依 ID 查詢警報

    Args:
        db: 已連線的 aiosqlite 連線
        alert_id: 警報 UUID

    Returns:
        Alert 物件或 None
    """
    try:
        async with db.execute(
            "SELECT * FROM alerts WHERE id = ?",
            (alert_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return _row_to_alert(row)
    except Exception as e:
        logger.error(f"查詢警報失敗: {e}")
        return None


async def get_active_alerts(db: aiosqlite.Connection) -> List[Alert]:
    """取得所有活躍（未清除）警報

    Args:
        db: 已連線的 aiosqlite 連線

    Returns:
        依觸發時間倒序的未清除警報列表
    """
    try:
        async with db.execute(
            """
            SELECT * FROM alerts
            WHERE cleared_at IS NULL
            ORDER BY triggered_at DESC
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_alert(row) for row in rows]
    except Exception as e:
        logger.error(f"查詢活躍警報失敗: {e}")
        return []


async def get_alert_history(
    db: aiosqlite.Connection,
    limit: int = 100,
    severity: Optional[str] = None,
    days: int = 7,
) -> List[Alert]:
    """取得警報歷史記錄

    Args:
        db: 已連線的 aiosqlite 連線
        limit: 最多回傳筆數（預設 100）
        severity: 篩選嚴重程度（"warning"/"critical"），None 表示全部
        days: 查詢天數範圍（預設 7 天）

    Returns:
        依觸發時間倒序的警報歷史列表
    """
    try:
        cutoff = time.time() - (days * 86400)

        if severity is not None:
            async with db.execute(
                """
                SELECT * FROM alerts
                WHERE triggered_at >= ? AND severity = ?
                ORDER BY triggered_at DESC
                LIMIT ?
                """,
                (cutoff, severity, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT * FROM alerts
                WHERE triggered_at >= ?
                ORDER BY triggered_at DESC
                LIMIT ?
                """,
                (cutoff, limit),
            ) as cursor:
                rows = await cursor.fetchall()

        return [_row_to_alert(row) for row in rows]
    except Exception as e:
        logger.error(f"查詢警報歷史失敗: {e}")
        return []


async def clear_old_alerts(db: aiosqlite.Connection, days: int = 7) -> int:
    """清除超過指定天數的舊警報

    Args:
        db: 已連線的 aiosqlite 連線
        days: 保留天數（超過此天數的記錄將被刪除）

    Returns:
        刪除的記錄數量
    """
    try:
        cutoff = time.time() - (days * 86400)
        await db.execute("BEGIN IMMEDIATE")
        cursor = await db.execute(
            "DELETE FROM alerts WHERE triggered_at < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount
        await db.commit()
        logger.info(f"已清除 {deleted} 筆超過 {days} 天的舊警報")
        return deleted
    except Exception as e:
        await db.rollback()
        logger.error(f"清除舊警報失敗: {e}")
        raise


# ── 輔助函式 ───────────────────────────────────────────────────

def _row_to_alert(row) -> Alert:
    """將 DB row 轉換為 Alert 資料物件

    相容 aiosqlite.Row（支援索引存取）與一般 tuple。
    """
    if hasattr(row, "keys"):
        # aiosqlite.Row（dict-like）
        return Alert(
            id=row["id"],
            type=row["type"],
            severity=row["severity"],
            threshold=row["threshold"],
            current_value=row["current_value"],
            triggered_at=row["triggered_at"],
            acknowledged_at=row["acknowledged_at"],
            acknowledged_by=row["acknowledged_by"],
            message=row["message"],
            cleared_at=row["cleared_at"],
        )
    else:
        # tuple 形式
        return Alert(
            id=row[0],
            type=row[1],
            severity=row[2],
            threshold=row[3],
            current_value=row[4],
            triggered_at=row[5],
            acknowledged_at=row[6],
            acknowledged_by=row[7],
            message=row[8],
            cleared_at=row[9],
        )
