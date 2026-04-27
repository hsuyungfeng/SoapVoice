"""
LAN 處理 API（Phase 11-01 — `/api/v1/lan/process`）

伺服器端的瘦客戶端入口：
- 接收 multipart/form-data（語音 wav + 截圖 jpg/png + 中繼資料）
- 將 WAV 壓縮為 Opus 32kbps（節省頻寬與儲存）
- 落地至 `data/lan_sessions/{session_id}/`（暫存目錄結構）
- 觸發 ASR 轉錄與 SOAP 生成
- 寫入 SQLite consultation_records 表（持久化）

設計重點：
- 嚴格驗證副檔名與檔案大小（防止 multipart 攻擊面，見 threat_model T-11-02、T-11-05）
- 任何下游失敗（ASR/SOAP/SQLite）皆走 graceful degradation，回傳部分結果
- 完整的繁體中文 docstring，便於後續維運
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── 路由 ─────────────────────────────────────────────────────
# 不附加 prefix，由 main.py 統一掛上 /api/v1
router = APIRouter(prefix="/lan", tags=["LAN Processing"])


# ── 配置常數 ────────────────────────────────────────────────────
# 檔案大小上限（bytes）— 對應 threat_model T-11-05 DoS 緩解
MAX_AUDIO_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024  # 10 MB

# 允許的副檔名（白名單）— 對應 threat_model T-11-02 Tampering 緩解
ALLOWED_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".flac"}
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# 暫存目錄（每個 session 一個子目錄）
LAN_SESSIONS_DIR = Path("data/lan_sessions")

# Opus 編碼參數（32kbps，AGC + VBR）— 約 10:1 壓縮比 vs 16kHz 16-bit PCM
OPUS_BITRATE_KBPS = 32


# ── 回應模型 ────────────────────────────────────────────────────


class LANProcessResponse(BaseModel):
    """`/api/v1/lan/process` 完整回應（含 ASR + SOAP）"""

    session_id: str = Field(..., description="伺服器產生的 session UUID")
    status: str = Field(..., description="received / completed / partial / failed")
    patient_name: str = Field(default="", description="病患姓名")
    doctor_name: str = Field(default="", description="醫師姓名")

    audio_original_bytes: int = Field(..., description="上傳的原始 WAV 大小")
    audio_compressed_bytes: int = Field(..., description="壓縮後 Opus 大小")
    compression_ratio: str = Field(..., description="壓縮比（例如 '10.2x'）")
    screenshot_bytes: int = Field(..., description="截圖大小")

    transcript: str = Field(default="", description="ASR 轉錄結果")
    soap: Dict[str, Any] = Field(default_factory=dict, description="SOAP 結果 dict")

    record_id: int = Field(default=0, description="SQLite consultation_records.id（0 表未持久化）")
    received_at: str = Field(..., description="ISO 8601 UTC 時間戳")
    processing_time_ms: Dict[str, int] = Field(
        default_factory=dict, description="ASR/LLM/total 處理時間（ms）"
    )
    warnings: list = Field(default_factory=list, description="非致命警告列表")


# ── 輔助函式 ────────────────────────────────────────────────────


def _validate_extension(filename: str, allowed: set) -> str:
    """驗證副檔名（小寫比對）

    Returns:
        小寫副檔名（含 dot）

    Raises:
        HTTPException 400 — 不在白名單內
    """
    if not filename:
        raise HTTPException(status_code=400, detail="檔名為空")
    ext = Path(filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不允許的副檔名 {ext}；允許：{sorted(allowed)}",
        )
    return ext


async def _read_upload_with_limit(upload: UploadFile, max_bytes: int, label: str) -> bytes:
    """讀取上傳檔案並驗證大小

    Args:
        upload: FastAPI UploadFile
        max_bytes: 最大允許 bytes
        label: 錯誤訊息中的識別字串（"audio" / "screenshot"）

    Raises:
        HTTPException 400 — 超過大小限制
    """
    data = await upload.read()
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"{label} 檔案過大：{len(data)} bytes > 上限 {max_bytes} bytes",
        )
    if len(data) == 0:
        raise HTTPException(status_code=400, detail=f"{label} 檔案為空")
    return data


def _compute_ratio(original: int, compressed: int) -> str:
    """計算壓縮比，格式 'N.Nx'"""
    if compressed <= 0:
        return "0.0x"
    return f"{original / compressed:.1f}x"


def _make_session_dir(session_id: str) -> Path:
    """建立 session 暫存目錄

    結構：data/lan_sessions/{session_id}/
        - audio.opus（壓縮後）
        - audio.wav（原始；可選保留）
        - screenshot.jpg
        - metadata.json
    """
    session_dir = LAN_SESSIONS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


# ── 主處理端點 ────────────────────────────────────────────────


@router.post("/process", response_model=LANProcessResponse)
async def process_lan_consultation(
    audio_file: UploadFile = File(..., description="語音 WAV/MP3 檔案"),
    screenshot_file: UploadFile = File(..., description="病歷截圖 JPG/PNG"),
    patient_name: Optional[str] = Form(default="", description="病患姓名"),
    doctor_name: Optional[str] = Form(default="", description="醫師姓名"),
    clinic_name: Optional[str] = Form(default="", description="診所名稱"),
) -> LANProcessResponse:
    """LAN 主處理端點：接收語音 + 截圖 → Opus 壓縮 → ASR → SOAP → SQLite

    僅供 LAN 客戶端使用（須通過 LANWhitelistMiddleware）。處理流程：

    1. 驗證副檔名與大小（threat_model T-11-02 / T-11-05）
    2. 將 audio 從原始格式壓縮為 Opus 32kbps（節省頻寬，保留音質）
    3. 寫入暫存目錄 `data/lan_sessions/{session_id}/`
    4. 呼叫 ExtendedSoapVoiceEngine 執行 ASR + SOAP（耗時 5-10 秒）
    5. 將完整結果寫入 SQLite consultation_records
    6. 回傳結構化結果（含 record_id 供客戶端追蹤）

    錯誤處理：
    - 任何 4xx 錯誤直接拋出（檔案問題使用者可修正）
    - ASR 失敗 → 回傳 status="partial"，warnings 含原因
    - SOAP 失敗 → 回傳 status="partial"
    - SQLite 失敗 → 回傳 200 + warning（業務優先於儲存）

    Args:
        audio_file: WAV/MP3 等語音檔案（≤ 100MB）
        screenshot_file: JPG/PNG 截圖（≤ 10MB）
        patient_name: 選填病患姓名
        doctor_name: 選填醫師姓名
        clinic_name: 選填診所名稱

    Returns:
        LANProcessResponse 含 session_id、SOAP 結果與時間戳
    """
    start_time = time.time()
    session_id = str(uuid.uuid4())
    received_at = datetime.now(timezone.utc).isoformat()
    warnings: list = []

    # 1. 驗證副檔名
    audio_ext = _validate_extension(audio_file.filename or "", ALLOWED_AUDIO_EXTS)
    image_ext = _validate_extension(screenshot_file.filename or "", ALLOWED_IMAGE_EXTS)

    # 2. 讀取並驗證大小
    audio_bytes = await _read_upload_with_limit(audio_file, MAX_AUDIO_BYTES, "audio")
    image_bytes = await _read_upload_with_limit(
        screenshot_file, MAX_SCREENSHOT_BYTES, "screenshot"
    )

    # 3. 建立 session 目錄並落地原始檔案
    session_dir = _make_session_dir(session_id)
    raw_audio_path = session_dir / f"audio{audio_ext}"
    raw_audio_path.write_bytes(audio_bytes)
    screenshot_path = session_dir / f"screenshot{image_ext}"
    screenshot_path.write_bytes(image_bytes)

    # 4. Opus 壓縮（延遲 import 避免 lan_health_api 也載入 audio_compress）
    from src.utils.audio_compress import compress_audio_to_opus

    opus_bytes: bytes
    try:
        opus_bytes = await asyncio.to_thread(
            compress_audio_to_opus, audio_bytes, OPUS_BITRATE_KBPS, audio_ext
        )
        opus_path = session_dir / "audio.opus"
        opus_path.write_bytes(opus_bytes)
    except Exception as e:
        logger.warning(f"Opus 壓縮失敗，保留原始 WAV：{e}")
        warnings.append(f"opus_compression_failed: {e}")
        opus_bytes = audio_bytes  # graceful fallback

    compressed_size = len(opus_bytes)
    ratio = _compute_ratio(len(audio_bytes), compressed_size)

    # 5. 寫入 metadata.json
    metadata = {
        "session_id": session_id,
        "received_at": received_at,
        "patient_name": patient_name,
        "doctor_name": doctor_name,
        "clinic_name": clinic_name,
        "audio_original_bytes": len(audio_bytes),
        "audio_compressed_bytes": compressed_size,
        "compression_ratio": ratio,
        "screenshot_bytes": len(image_bytes),
    }
    (session_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 6. ASR + SOAP（Task 3 整合）— 容錯
    transcript_text = ""
    soap_result: Dict[str, Any] = {}
    asr_time_ms = 0
    llm_time_ms = 0
    overall_status = "completed"

    try:
        from src.api.extended_api import get_extended_engine

        engine = await get_extended_engine()

        # ASR：使用本地檔案路徑（部分 backend 不接受 bytes）
        asr_start = time.time()
        try:
            transcript_text = await asyncio.to_thread(engine.transcribe, str(raw_audio_path))
            asr_time_ms = int((time.time() - asr_start) * 1000)
        except Exception as e:
            logger.error(f"ASR 失敗：{e}")
            warnings.append(f"asr_failed: {e}")
            overall_status = "partial"

        # SOAP 生成（僅在 ASR 成功時執行）
        if transcript_text:
            llm_start = time.time()
            try:
                # 提取症狀 → ICD-10 → 醫囑 → 藥物 → SOAP（同 extended_api 流程）
                symptoms = await asyncio.to_thread(engine.extract_symptoms, transcript_text)
                icd10_codes = await asyncio.to_thread(engine.classify_icd10, transcript_text)
                medical_orders = await asyncio.to_thread(
                    engine.get_medical_orders, symptoms, [c["code"] for c in icd10_codes]
                )
                drug_recs = await asyncio.to_thread(
                    engine.get_drug_recommendations, symptoms, [c["code"] for c in icd10_codes]
                )
                soap_result = await asyncio.to_thread(
                    engine.generate_extended_soap,
                    transcript_text,
                    symptoms,
                    icd10_codes,
                    medical_orders,
                    drug_recs,
                    "zh",
                )
                llm_time_ms = int((time.time() - llm_start) * 1000)
            except Exception as e:
                logger.error(f"SOAP 生成失敗：{e}")
                warnings.append(f"soap_failed: {e}")
                overall_status = "partial"
    except Exception as e:
        # ExtendedEngine 取得失敗（測試環境常見）
        logger.warning(f"無法取得 ExtendedSoapVoiceEngine（可能測試模式）：{e}")
        warnings.append(f"engine_unavailable: {e}")
        overall_status = "partial"

    total_time_ms = int((time.time() - start_time) * 1000)

    # 7. 寫入 SQLite（容錯：失敗不阻擋回應）
    record_id = 0
    try:
        from src.db.patient_records_db import save_consultation_record

        record_data = {
            "session_id": session_id,
            "patient_name": patient_name or "Unnamed",
            "doctor_name": doctor_name or "",
            "clinic_name": clinic_name or "",
            "audio_file_path": str(opus_path) if "opus_path" in locals() else str(raw_audio_path),
            "audio_format": "opus",
            "transcript_text": transcript_text,
            "transcript_segments_json": "[]",
            "soap_json": soap_result,
            "status": "completed" if overall_status == "completed" else "draft",
            "asr_model": os.getenv("ASR_MODEL", "faster-whisper"),
            "asr_time_ms": asr_time_ms,
            "llm_model": os.getenv("LLM_MODEL", "gemma3:e4b"),
            "llm_time_ms": llm_time_ms,
            "total_time_ms": total_time_ms,
            "created_by": "lan_client",
        }
        record_id = await save_consultation_record(record_data)
        if record_id == 0:
            warnings.append("sqlite_save_returned_zero")
    except Exception as e:
        logger.warning(f"SQLite 寫入失敗：{e}")
        warnings.append(f"sqlite_failed: {e}")

    return LANProcessResponse(
        session_id=session_id,
        status=overall_status,
        patient_name=patient_name or "",
        doctor_name=doctor_name or "",
        audio_original_bytes=len(audio_bytes),
        audio_compressed_bytes=compressed_size,
        compression_ratio=ratio,
        screenshot_bytes=len(image_bytes),
        transcript=transcript_text,
        soap=soap_result,
        record_id=record_id,
        received_at=received_at,
        processing_time_ms={
            "asr": asr_time_ms,
            "llm": llm_time_ms,
            "total": total_time_ms,
        },
        warnings=warnings,
    )


__all__ = [
    "router",
    "process_lan_consultation",
    "MAX_AUDIO_BYTES",
    "MAX_SCREENSHOT_BYTES",
    "ALLOWED_AUDIO_EXTS",
    "ALLOWED_IMAGE_EXTS",
    "OPUS_BITRATE_KBPS",
]
