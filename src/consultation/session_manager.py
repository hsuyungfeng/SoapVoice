"""
諮詢會話管理模組

管理多個諮詢會話的狀態和歷史
"""

import logging
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.consultation.consultation_flow import ConsultationFlow, ConsultationResult


logger = logging.getLogger(__name__)


class SessionStatus(Enum):
    """會話狀態"""

    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class Session:
    """諮詢會話"""

    session_id: str
    flow: ConsultationFlow
    patient_context: Dict[str, Any]
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[ConsultationResult] = None
    notes: str = ""


class SessionManager:
    """諮詢會話管理器

    管理多個同時進行的諮詢會話
    """

    def __init__(self, storage_dir: Optional[Path] = None):
        """初始化會話管理器

        Args:
            storage_dir: 會話存儲目錄（可選）
        """
        self.storage_dir = storage_dir or Path("data/sessions")
        self._sessions: Dict[str, Session] = {}
        self._session_timeout = timedelta(hours=24)

    def create_session(
        self,
        patient_context: Optional[Dict[str, Any]] = None,
        config: Optional[Any] = None,
    ) -> Session:
        """建立新的諮詢會話

        Args:
            patient_context: 病患背景
            config: 諮詢配置

        Returns:
            新建的 Session
        """
        flow = ConsultationFlow(config)
        if patient_context:
            flow.set_patient_context(patient_context)

        session_id = flow.session_id or self._generate_session_id()
        now = datetime.now()

        session = Session(
            session_id=session_id,
            flow=flow,
            patient_context=patient_context or {},
            status=SessionStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

        self._sessions[session_id] = session
        logger.info(f"新建會話: {session_id}")

        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """取得會話

        Args:
            session_id: 會話 ID

        Returns:
            Session 或 None
        """
        return self._sessions.get(session_id)

    def get_active_sessions(self) -> List[Session]:
        """取得所有活躍會話

        Returns:
            活躍會話列表
        """
        return [s for s in self._sessions.values() if s.status == SessionStatus.ACTIVE]

    def complete_session(self, session_id: str, result: ConsultationResult) -> bool:
        """完成會話

        Args:
            session_id: 會話 ID
            result: 諮詢結果

        Returns:
            是否成功
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = SessionStatus.COMPLETED
        session.result = result
        session.completed_at = datetime.now()
        session.updated_at = datetime.now()

        # 保存到磁盤
        self._save_session(session)

        logger.info(f"會話已完成: {session_id}")
        return True

    def cancel_session(self, session_id: str) -> bool:
        """取消會話

        Args:
            session_id: 會話 ID

        Returns:
            是否成功
        """
        session = self._sessions.get(session_id)
        if not session:
            return False

        session.status = SessionStatus.CANCELLED
        session.updated_at = datetime.now()

        logger.info(f"會話已取消: {session_id}")
        return True

    def remove_session(self, session_id: str) -> bool:
        """移除會話

        Args:
            session_id: 會話 ID

        Returns:
            是否成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"會話已移除: {session_id}")
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """清理過期會話

        Returns:
            清理的會話數量
        """
        now = datetime.now()
        expired = []

        for session_id, session in self._sessions.items():
            if (
                session.status == SessionStatus.ACTIVE
                and now - session.updated_at > self._session_timeout
            ):
                session.status = SessionStatus.EXPIRED
                expired.append(session_id)

        if expired:
            logger.info(f"清理了 {len(expired)} 個過期會話")

        return len(expired)

    def get_statistics(self) -> Dict[str, Any]:
        """取得統計資訊

        Returns:
            統計字典
        """
        total = len(self._sessions)
        active = sum(1 for s in self._sessions.values() if s.status == SessionStatus.ACTIVE)
        completed = sum(1 for s in self._sessions.values() if s.status == SessionStatus.COMPLETED)

        return {
            "total_sessions": total,
            "active_sessions": active,
            "completed_sessions": completed,
            "session_timeout_hours": self._session_timeout.total_seconds() / 3600,
        }

    def _generate_session_id(self) -> str:
        """生成唯一會話 ID"""
        import uuid

        return str(uuid.uuid4())[:8]

    def _save_session(self, session: Session) -> None:
        """保存會話到磁盤

        Args:
            session: 會話
        """
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

            filepath = self.storage_dir / f"{session.session_id}.json"

            data = {
                "session_id": session.session_id,
                "patient_context": session.patient_context,
                "status": session.status.value,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "notes": session.notes,
                "result": {
                    "session_id": session.result.session_id if session.result else None,
                    "soap": session.result.soap if session.result else None,
                    "metadata": session.result.metadata if session.result else None,
                    "processing_time_ms": session.result.processing_time_ms
                    if session.result
                    else None,
                }
                if session.result
                else None,
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"會話已保存: {filepath}")

        except Exception as e:
            logger.error(f"保存會話失敗: {e}")

    def load_session(self, session_id: str) -> Optional[Session]:
        """從磁盤載入會話

        Args:
            session_id: 會話 ID

        Returns:
            Session 或 None
        """
        filepath = self.storage_dir / f"{session_id}.json"

        if not filepath.exists():
            return None

        try:
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            # 建立 flow（需要重新初始化）
            from src.consultation.consultation_flow import ConsultationFlow, ConsultationConfig

            config = ConsultationConfig()
            flow = ConsultationFlow(config)
            flow.set_patient_context(data.get("patient_context", {}))

            session = Session(
                session_id=data["session_id"],
                flow=flow,
                patient_context=data.get("patient_context", {}),
                status=SessionStatus(data.get("status", "completed")),
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                completed_at=datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None,
                notes=data.get("notes", ""),
            )

            self._sessions[session_id] = session
            return session

        except Exception as e:
            logger.error(f"載入會話失敗: {e}")
            return None

    def list_saved_sessions(self) -> List[Dict[str, Any]]:
        """列出所有已保存的會話

        Returns:
            會話摘要列表
        """
        sessions = []

        for filepath in self.storage_dir.glob("*.json"):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)

                sessions.append(
                    {
                        "session_id": data["session_id"],
                        "status": data.get("status", "unknown"),
                        "created_at": data.get("created_at", ""),
                        "completed_at": data.get("completed_at"),
                        "has_result": data.get("result") is not None,
                    }
                )
            except Exception as e:
                logger.warning(f"讀取會話檔案失敗 {filepath}: {e}")

        sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return sessions
