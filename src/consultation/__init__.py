"""
門診諮詢流程模組

整合語音轉文字、資料庫查詢、LLM 生成的一站式門診諮詢流程
"""

from .consultation_flow import (
    ConsultationFlow,
    ConsultationState,
    ConsultationConfig,
    ConsultationResult,
    SessionSummary,
)
from .session_manager import SessionManager, Session, SessionStatus
from .realtime_search import RealtimeSearch

__all__ = [
    # 主要流程
    "ConsultationFlow",
    "ConsultationState",
    "ConsultationConfig",
    "ConsultationResult",
    "SessionSummary",
    # 階段管理
    "SessionManager",
    "Session",
    "SessionStatus",
    # 即時搜尋
    "RealtimeSearch",
]
