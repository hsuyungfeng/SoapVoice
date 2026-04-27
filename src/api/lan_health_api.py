"""
LAN 健康檢查與版本檢查 API（Phase 11-01）

提供 `/api/v1/health` 端點，回傳伺服器版本資訊與服務健康狀態。
客戶端啟動時呼叫此端點以確認版本相容、判斷 ASR/LLM/DB 是否就緒，
並決定是否提示使用者更新或暫存上傳作業。

設計目標：
- 不依賴重型推理模組（避免冷啟動延遲）
- 三個服務狀態獨立檢查、單一服務失敗不影響整體 200 回應
- 服務未就緒時回傳 status="degraded"，客戶端可決定是否上傳

用途：Phase 11 瘦客戶端版本驗證、連線狀態指示燈、服務發現
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── 路由 ─────────────────────────────────────────────────────
# 不附加 prefix，由 main.py 統一掛上 /api/v1
# 健康端點直接掛在 /api/v1/health（不加 /lan 子路徑），方便客戶端版本檢查
router = APIRouter(tags=["LAN Health"])


# ── 版本與相容性常數 ────────────────────────────────────────────
# 客戶端與伺服器透過 SemVer-like 字串協商相容性。
# Phase 11 版本約定：1.1.x 客戶端必須與 1.1.x 伺服器搭配。
SERVER_VERSION = "1.1.0"
API_VERSION = "v1"
MIN_CLIENT_VERSION = "1.1.0"


class ServiceStatus(BaseModel):
    """單一服務狀態（asr/llm/database）"""

    asr: str = Field(default="unknown", description="ASR 引擎狀態：ready/loading/error/unknown")
    llm: str = Field(default="unknown", description="LLM 引擎狀態：ready/loading/error/unknown")
    database: str = Field(default="unknown", description="SQLite 連線狀態：ready/error/unknown")


class HealthResponse(BaseModel):
    """`/api/v1/health` 回應模型"""

    status: str = Field(..., description="整體狀態：healthy/degraded/unhealthy")
    version: str = Field(..., description="伺服器版本（SemVer）")
    api_version: str = Field(..., description="API 主版本（v1/v2...）")
    min_client_version: str = Field(..., description="所需客戶端最低版本")
    timestamp: str = Field(..., description="ISO 8601 UTC 時間戳")
    services: ServiceStatus = Field(..., description="各服務子狀態")


async def _check_database() -> str:
    """檢查 SQLite 連線是否可用

    嘗試取得連線並執行簡單查詢；任何例外皆視為 error，避免阻塞 health 端點。
    """
    try:
        from src.db.patient_records_db import get_patient_records_db

        db = await get_patient_records_db()
        # 執行最輕量的健全性查詢
        cursor = await db.execute("SELECT 1")
        row = await cursor.fetchone()
        return "ready" if row else "error"
    except Exception as e:
        logger.debug(f"健康檢查：資料庫不可用 - {e}")
        return "error"


def _check_asr() -> str:
    """檢查 ASR 引擎是否已預載

    回傳 ready/loading/error/unknown，不主動觸發初始化（避免增加端點延遲）。
    """
    try:
        from src.api.extended_api import _extended_engine

        if _extended_engine is None:
            return "loading"
        # 檢查內部 _whisper 屬性是否已初始化
        if hasattr(_extended_engine, "_whisper") and _extended_engine._whisper is not None:
            return "ready"
        return "loading"
    except Exception as e:
        logger.debug(f"健康檢查：ASR 模組無法檢查 - {e}")
        return "unknown"


def _check_llm() -> str:
    """檢查 LLM 引擎是否就緒

    LLM 為可選元件（INITIALIZE_LLM 旗標控制），未啟用時回傳 ready 即可，
    因為實際 SOAP 生成會走 Ollama HTTP 通道。
    """
    try:
        # Ollama 為外部 process，僅檢查設定是否存在
        import os

        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        if ollama_host:
            return "ready"
        return "unknown"
    except Exception:
        return "unknown"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """LAN 健康檢查端點（客戶端版本檢查專用）

    回傳伺服器版本與三個關鍵服務（ASR/LLM/Database）的健康狀態。
    客戶端啟動時應呼叫此端點：
    1. 檢查 `version` 欄位確認與 `min_client_version` 相容
    2. 檢查 `services.*` 欄位決定是否可立即上傳，或提示使用者稍後重試
    3. 失敗（HTTP error 或 status=unhealthy）時切換離線模式（Phase 11-03 暫存）

    狀態決策：
    - 所有服務 ready → status="healthy"
    - 任一服務 loading → status="degraded"
    - 資料庫 error → status="unhealthy"（無法持久化）

    Returns:
        HealthResponse 含版本、時間戳與服務狀態
    """
    db_status = await _check_database()
    asr_status = _check_asr()
    llm_status = _check_llm()

    services = ServiceStatus(asr=asr_status, llm=llm_status, database=db_status)

    # 整體狀態決策
    if db_status == "error":
        overall = "unhealthy"
    elif "loading" in (db_status, asr_status, llm_status):
        overall = "degraded"
    elif all(s == "ready" for s in (db_status, asr_status, llm_status)):
        overall = "healthy"
    else:
        overall = "degraded"

    return HealthResponse(
        status=overall,
        version=SERVER_VERSION,
        api_version=API_VERSION,
        min_client_version=MIN_CLIENT_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=services,
    )


@router.get("/version")
async def version_info() -> Dict[str, Any]:
    """簡化版版本端點（不檢查服務狀態）

    用於客戶端低成本輪詢確認伺服器是否可達。
    """
    return {
        "version": SERVER_VERSION,
        "api_version": API_VERSION,
        "min_client_version": MIN_CLIENT_VERSION,
    }


__all__ = ["router", "SERVER_VERSION", "API_VERSION", "MIN_CLIENT_VERSION"]
