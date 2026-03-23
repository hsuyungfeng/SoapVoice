"""
諮詢流程 API 端點模組

提供門診諮詢流程的 RESTful API
"""

import logging
import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from src.consultation import (
    ConsultationFlow,
    ConsultationConfig,
    ConsultationState,
    SessionManager,
)


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/consultation", tags=["Consultation Flow"])


_consultation_flow: Optional[ConsultationFlow] = None
_session_manager: Optional[SessionManager] = None


def get_consultation_flow() -> ConsultationFlow:
    """取得諮詢流程實例"""
    global _consultation_flow
    if _consultation_flow is None:
        _consultation_flow = ConsultationFlow()
    return _consultation_flow


def get_session_manager() -> SessionManager:
    """取得會話管理器實例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


# Request/Response Models
class StartConsultationRequest(BaseModel):
    """開始諮詢請求"""

    patient_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="病患背景（年齡、性別、主訴等）",
    )
    whisper_model_size: str = Field(default="medium", description="Whisper 模型大小")
    max_duration_seconds: int = Field(default=600, description="最大錄音時長（秒）")


class StartConsultationResponse(BaseModel):
    """開始諮詢回應"""

    session_id: str
    status: str
    message: str
    patient_context: Dict[str, Any]


class TranscriptUpdateRequest(BaseModel):
    """轉文字更新請求"""

    session_id: str
    action: str = Field(..., description="操作：start, pause, resume, end")
    patient_context: Optional[Dict[str, Any]] = Field(default=None, description="病患背景")


class EndConsultationResponse(BaseModel):
    """結束諮詢回應"""

    session_id: str
    status: str
    elapsed_seconds: float
    transcript: str
    segments_count: int
    message: str


class SOAPGenerateResponse(BaseModel):
    """SOAP 生成回應"""

    session_id: str
    soap: Dict[str, str]
    metadata: Dict[str, Any]
    session_summary: Dict[str, Any]
    processing_time_ms: float


class RealtimeSearchRequest(BaseModel):
    """即時搜尋請求"""

    text: str = Field(..., description="搜尋文字")
    categories: Optional[list[str]] = Field(
        default=None,
        description="搜尋類別：icd10, drug, order",
    )
    limit: int = Field(default=10, description="最大結果數")


class RealtimeSearchResponse(BaseModel):
    """即時搜尋回應"""

    results: Dict[str, list]
    processing_time_ms: float


class ConsultationStatsResponse(BaseModel):
    """諮詢統計回應"""

    state: str
    session_id: Optional[str]
    elapsed_seconds: float
    transcript_length: int
    segments_count: int


# API Endpoints
@router.post("/start", response_model=StartConsultationResponse)
async def start_consultation(request: StartConsultationRequest):
    """
    開始新的諮詢會話

    **範例:**
    ```
    POST /api/v1/consultation/start
    {
        "patient_context": {
            "age": 45,
            "gender": "M",
            "chief_complaint": "胸悶兩天"
        }
    }
    ```
    """
    try:
        flow = get_consultation_flow()

        # 如果已有進行中的會話，先重置
        if flow.state in (ConsultationState.RECORDING, ConsultationState.PAUSED):
            flow.reset()

        # 設定配置
        config = ConsultationConfig(
            whisper_model_size=request.whisper_model_size,
            max_duration_seconds=request.max_duration_seconds,
        )
        flow.config = config

        # 設定病患背景
        if request.patient_context:
            flow.set_patient_context(request.patient_context)

        # 開始諮詢
        result = flow.start_consultation()

        return StartConsultationResponse(
            session_id=result["session_id"],
            status=result["status"],
            message=result["message"],
            patient_context=result["patient_context"],
        )

    except Exception as e:
        logger.error(f"開始諮詢失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/end", response_model=EndConsultationResponse)
async def end_consultation():
    """
    結束諮詢會話

    結束後可以呼叫 /soap/generate 生成 SOAP 病歷
    """
    try:
        flow = get_consultation_flow()

        if flow.state not in (ConsultationState.RECORDING, ConsultationState.PAUSED):
            raise HTTPException(status_code=400, detail="沒有正在進行或已暫停的諮詢會話")

        result = flow.end_consultation()

        return EndConsultationResponse(
            session_id=result["session_id"],
            status=result["status"],
            elapsed_seconds=result["elapsed_seconds"],
            transcript=result["transcript"],
            segments_count=result["segments_count"],
            message=result["message"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"結束諮詢失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/soap/generate", response_model=SOAPGenerateResponse)
async def generate_soap():
    """
    生成 SOAP 病歷

    必須先結束諮詢會話才能呼叫此端點
    """
    start_time = time.time()

    try:
        flow = get_consultation_flow()

        if flow.state != ConsultationState.PROCESSING:
            raise HTTPException(
                status_code=400,
                detail="請先結束諮詢會話",
            )

        # 生成 SOAP
        result = flow.generate_soap()

        # 保存會話
        session_manager = get_session_manager()
        session_manager.complete_session(result.session_id, result)

        processing_time = (time.time() - start_time) * 1000

        return SOAPGenerateResponse(
            session_id=result.session_id,
            soap=result.soap,
            metadata=result.metadata,
            session_summary={
                "session_id": result.session_summary.session_id,
                "patient_context": result.session_summary.patient_context,
                "duration_seconds": result.session_summary.duration_seconds,
                "icd10_codes": [
                    {"code": c["code"], "name": c["name"], "symptom": c.get("symptom", "")}
                    for c in result.session_summary.icd10_codes
                ],
                "drug_recommendations": [
                    {"code": d["code"], "name": d["name"], "atc_code": d.get("atc_code", "")}
                    for d in result.session_summary.drug_recommendations
                ],
                "medical_orders": [
                    {"code": o["code"], "name": o["name"], "category": o.get("category", "")}
                    for o in result.session_summary.medical_orders
                ],
                "created_at": result.session_summary.created_at.isoformat(),
            },
            processing_time_ms=round(processing_time, 2),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成 SOAP 失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=RealtimeSearchResponse)
async def search(request: RealtimeSearchRequest):
    """
    即時搜尋 ICD-10、藥品、醫療服務

    **範例:**
    ```
    POST /api/v1/consultation/search
    {
        "text": "病人咳嗽兩天，有痰",
        "categories": ["icd10", "drug"],
        "limit": 5
    }
    ```
    """
    start_time = time.time()

    try:
        from src.consultation.realtime_search import RealtimeSearch

        searcher = RealtimeSearch()

        categories = request.categories or ["icd10", "drug", "order"]
        limit = request.limit

        results = {}
        for cat in categories:
            if cat == "icd10":
                cat_results = searcher.search_icd10(request.text, limit)
                results["icd10"] = [
                    {
                        "code": r.code,
                        "name": r.name,
                        "description": r.description,
                        "confidence": r.confidence,
                    }
                    for r in cat_results
                ]
            elif cat == "drug":
                cat_results = searcher.search_drugs(request.text, limit)
                results["drug"] = [
                    {
                        "code": r.code,
                        "name": r.name,
                        "description": r.description,
                        "atc_code": r.metadata.get("atc_code", ""),
                        "price": r.metadata.get("price", 0),
                    }
                    for r in cat_results
                ]
            elif cat == "order":
                cat_results = searcher.search_medical_orders(request.text, limit)
                results["order"] = [
                    {
                        "code": r.code,
                        "name": r.name,
                        "description": r.description,
                        "category": r.metadata.get("category", ""),
                        "fee_points": r.metadata.get("fee_points", 0),
                    }
                    for r in cat_results
                ]

        processing_time = (time.time() - start_time) * 1000

        return RealtimeSearchResponse(
            results=results,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        logger.error(f"搜尋失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ConsultationStatsResponse)
async def get_stats():
    """
    取得當前諮詢統計資訊
    """
    try:
        flow = get_consultation_flow()
        stats = flow.get_realtime_stats()

        return ConsultationStatsResponse(
            state=stats["state"],
            session_id=stats.get("session_id"),
            elapsed_seconds=stats["elapsed_seconds"],
            transcript_length=stats["transcript_length"],
            segments_count=stats["segments_count"],
        )

    except Exception as e:
        logger.error(f"取得統計失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_consultation():
    """
    重置諮詢流程
    """
    try:
        flow = get_consultation_flow()
        flow.reset()

        return {
            "status": "reset",
            "message": "諮詢流程已重置",
        }

    except Exception as e:
        logger.error(f"重置失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions():
    """
    列出所有會話
    """
    try:
        session_manager = get_session_manager()

        return {
            "sessions": session_manager.list_saved_sessions(),
            "statistics": session_manager.get_statistics(),
        }

    except Exception as e:
        logger.error(f"列出會話失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    取得特定會話
    """
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)

        if not session:
            session = session_manager.load_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="會話不存在")

        return {
            "session_id": session.session_id,
            "patient_context": session.patient_context,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "notes": session.notes,
            "has_result": session.result is not None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得會話失敗: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket 端點
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端點，用於即時音頻串流處理

    用戶端應發送音頻數據，伺服器返回轉錄結果
    """
    await websocket.accept()

    flow = get_consultation_flow()

    try:
        # 等待客戶端開始指令
        data = await websocket.receive_json()

        if data.get("action") == "start":
            # 設定病患背景
            if "patient_context" in data:
                flow.set_patient_context(data["patient_context"])

            # 開始諮詢
            result = flow.start_consultation()
            await websocket.send_json(
                {
                    "type": "started",
                    "session_id": result["session_id"],
                    "message": result["message"],
                }
            )

        elif data.get("action") == "end":
            # 結束諮詢
            result = flow.end_consultation()
            await websocket.send_json(
                {
                    "type": "ended",
                    "session_id": result["session_id"],
                    "transcript": result["transcript"],
                    "elapsed_seconds": result["elapsed_seconds"],
                }
            )

        elif data.get("action") == "generate_soap":
            # 生成 SOAP
            result = flow.generate_soap()
            await websocket.send_json(
                {
                    "type": "soap_generated",
                    "soap": result.soap,
                    "metadata": result.metadata,
                    "processing_time_ms": result.processing_time_ms,
                }
            )

        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "未知動作",
                }
            )

    except WebSocketDisconnect:
        logger.info("WebSocket 連線已斷開")

    except Exception as e:
        logger.error(f"WebSocket 錯誤: {e}")
        await websocket.send_json(
            {
                "type": "error",
                "message": str(e),
            }
        )

    finally:
        # 重置流程
        flow.reset()


@router.get("/health")
async def consultation_health():
    """
    諮詢流程服務健康檢查
    """
    flow = get_consultation_flow()

    return {
        "status": "healthy",
        "service": "consultation-flow",
        "state": flow.state.value if flow else "not_initialized",
        "components": {
            "consultation_flow": "initialized" if flow else "not_initialized",
            "session_manager": "initialized" if _session_manager else "not_initialized",
        },
    }
