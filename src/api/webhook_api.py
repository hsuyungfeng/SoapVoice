"""
Webhook API 模組

提供事件驅動整合的 Webhook 端點
支援外部服務透過 Webhook 觸發 SOAP 處理
"""

import logging
import hashlib
import hmac
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Header, Request, Depends
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@dataclass
class WebhookEvent:
    """Webhook 事件"""

    event_id: str
    event_type: str
    timestamp: float
    source: str
    payload: Dict[str, Any]
    retry_count: int = 0
    status: str = "pending"


@dataclass
class WebhookConfig:
    """Webhook 配置"""

    secret: str = ""
    enabled: bool = True
    max_retries: int = 3
    timeout: int = 30
    allowed_sources: List[str] = field(default_factory=lambda: ["*"])


class WebhookManager:
    """Webhook 管理器"""

    def __init__(self, config: Optional[WebhookConfig] = None):
        self.config = config or WebhookConfig()
        self._events: Dict[str, WebhookEvent] = {}
        self._subscribers: Dict[str, List[str]] = {}

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """驗證 Webhook 簽名

        Args:
            payload: 請求內容
            signature: 簽名字串

        Returns:
            驗證是否成功
        """
        if not self.config.secret or signature == "":
            return True

        expected = hmac.new(
            self.config.secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def create_event(self, event_type: str, source: str, payload: Dict[str, Any]) -> str:
        """建立 Webhook 事件

        Args:
            event_type: 事件類型
            source: 來源
            payload: 事件資料

        Returns:
            事件 ID
        """
        event_id = f"{event_type}_{int(time.time() * 1000)}"
        event = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=time.time(),
            source=source,
            payload=payload,
        )
        self._events[event_id] = event
        logger.info(f"Created webhook event: {event_id}")
        return event_id

    def get_event(self, event_id: str) -> Optional[WebhookEvent]:
        """取得事件

        Args:
            event_id: 事件 ID

        Returns:
            事件物件
        """
        return self._events.get(event_id)

    def update_event_status(self, event_id: str, status: str) -> None:
        """更新事件狀態

        Args:
            event_id: 事件 ID
            status: 狀態
        """
        if event_id in self._events:
            self._events[event_id].status = status

    def subscribe(self, event_type: str, callback_url: str) -> None:
        """訂閱事件

        Args:
            event_type: 事件類型
            callback_url: 回調 URL
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if callback_url not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback_url)
            logger.info(f"Subscribed to {event_type}: {callback_url}")


# Webhook 請求模型
class WebhookTriggerRequest(BaseModel):
    """Webhook 觸發請求"""

    event_type: str = Field(
        ..., description="事件類型 (audio_received, transcription_complete, soap_generated)"
    )
    source: str = Field(..., description="來源識別")
    payload: Dict[str, Any] = Field(default_factory=dict, description="事件資料")
    callback_url: Optional[str] = Field(None, description="回調 URL")


class WebhookSubscriptionRequest(BaseModel):
    """Webhook 訂閱請求"""

    event_type: str = Field(..., description="要訂閱的事件類型")
    callback_url: str = Field(..., description="回調 URL")


class WebhookTestRequest(BaseModel):
    """Webhook 測試請求"""

    test_type: str = Field(..., description="測試類型 (health, echo)")


# 全域 Webhook 管理器
_webhook_manager: Optional[WebhookManager] = None


def get_webhook_manager() -> WebhookManager:
    """取得 Webhook 管理器"""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager


# Webhook 端點
@router.post("/trigger")
async def trigger_webhook(
    request: WebhookTriggerRequest,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_source: Optional[str] = Header(None, alias="X-Source"),
) -> Dict[str, Any]:
    """觸發 Webhook 事件

    用於外部服務觸發 SOAP 處理流程
    """
    manager = get_webhook_manager()

    if not manager.config.enabled:
        raise HTTPException(status_code=503, detail="Webhook service disabled")

    # 驗證來源
    if x_source and manager.config.allowed_sources != ["*"]:
        if x_source not in manager.config.allowed_sources:
            raise HTTPException(status_code=403, detail="Source not allowed")

    # 建立事件
    event_id = manager.create_event(
        event_type=request.event_type,
        source=request.source,
        payload=request.payload,
    )

    # 處理不同事件類型
    result = await _process_webhook_event(
        event_id=event_id,
        event_type=request.event_type,
        payload=request.payload,
    )

    # 更新事件狀態
    manager.update_event_status(event_id, "completed")

    return {
        "event_id": event_id,
        "status": "success",
        "result": result,
    }


async def _process_webhook_event(
    event_id: str,
    event_type: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """處理 Webhook 事件

    Args:
        event_id: 事件 ID
        event_type: 事件類型
        payload: 事件資料

    Returns:
        處理結果
    """
    manager = get_webhook_manager()

    if event_type == "audio_received":
        # 音訊已接收，觸發轉錄
        return await _handle_audio_received(payload)
    elif event_type == "transcription_complete":
        # 轉錄完成，觸發 SOAP 生成
        return await _handle_transcription_complete(payload)
    elif event_type == "soap_generated":
        # SOAP 已生成，觸發回調
        return await _handle_soap_generated(payload)
    else:
        logger.warning(f"Unknown event type: {event_type}")
        return {"status": "unknown_event_type"}


async def _handle_audio_received(payload: Dict[str, Any]) -> Dict[str, Any]:
    """處理音訊接收事件"""
    audio_path = payload.get("audio_path")
    if not audio_path:
        return {"error": "No audio_path in payload"}

    # TODO: 觸發轉錄流程
    logger.info(f"Audio received: {audio_path}")
    return {"status": "queued", "next_action": "transcription"}


async def _handle_transcription_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    """處理轉錄完成事件"""
    transcript = payload.get("transcript")
    if not transcript:
        return {"error": "No transcript in payload"}

    # TODO: 觸發 SOAP 生成
    logger.info(f"Transcription complete: {transcript[:100]}...")
    return {"status": "queued", "next_action": "soap_generation"}


async def _handle_soap_generated(payload: Dict[str, Any]) -> Dict[str, Any]:
    """處理 SOAP 生成完成事件"""
    soap_result = payload.get("soap_result")
    if not soap_result:
        return {"error": "No soap_result in payload"}

    logger.info(f"SOAP generated successfully")
    return {"status": "completed", "soap": soap_result}


@router.post("/subscribe")
async def subscribe_webhook(
    request: WebhookSubscriptionRequest,
) -> Dict[str, Any]:
    """訂閱 Webhook 事件"""
    manager = get_webhook_manager()
    manager.subscribe(request.event_type, request.callback_url)

    return {
        "status": "subscribed",
        "event_type": request.event_type,
        "callback_url": request.callback_url,
    }


@router.get("/events/{event_id}")
async def get_event_status(event_id: str) -> Dict[str, Any]:
    """取得事件狀態"""
    manager = get_webhook_manager()
    event = manager.get_event(event_id)

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "status": event.status,
        "source": event.source,
    }


@router.get("/health")
async def webhook_health() -> Dict[str, str]:
    """Webhook 健康檢查"""
    return {"status": "healthy", "service": "webhook"}


@router.post("/test")
async def webhook_test(request: WebhookTestRequest) -> Dict[str, Any]:
    """Webhook 測試端點"""
    if request.test_type == "health":
        return {"status": "ok", "message": "Webhook service is running"}
    elif request.test_type == "echo":
        return {"status": "ok", "message": "Echo test successful"}
    else:
        raise HTTPException(status_code=400, detail="Invalid test type")


# Webhook 配置端點
@router.get("/config")
async def get_webhook_config() -> Dict[str, Any]:
    """取得 Webhook 配置"""
    manager = get_webhook_manager()
    return {
        "enabled": manager.config.enabled,
        "max_retries": manager.config.max_retries,
        "timeout": manager.config.timeout,
        "allowed_sources": manager.config.allowed_sources,
    }


@router.post("/config")
async def update_webhook_config(
    enabled: bool = True,
    max_retries: int = 3,
    timeout: int = 30,
    allowed_sources: List[str] = ["*"],
) -> Dict[str, str]:
    """更新 Webhook 配置"""
    manager = get_webhook_manager()
    manager.config.enabled = enabled
    manager.config.max_retries = max_retries
    manager.config.timeout = timeout
    manager.config.allowed_sources = allowed_sources

    return {"status": "updated"}


# 自動註冊路由到主應用
def register_webhook_router(app):
    """註冊 Webhook 路由到 FastAPI 應用"""
    from src.main import app as main_app

    if hasattr(main_app, "include_router"):
        main_app.include_router(router)
        logger.info("Webhook router registered")
