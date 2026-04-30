"""
病患記錄 API 端點模組 — 搜尋、瀏覽、審計追蹤

提供醫師查詢歷史問診記錄的 REST API：
- 依病患姓名 / 日期範圍搜尋（含分頁）
- 查看單筆完整問診記錄
- 查看審計追蹤（不可變修改記錄）
- 修改 SOAP 病歷（自動寫入審計日誌）
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.db.patient_records_db import (
    search_consultation_records,
    get_consultation_by_id,
    get_audit_log,
    amend_soap,
    get_patient_records_db,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/records", tags=["Patient Records"])


# ── Request / Response Models ──────────────────────────────────


class SOAPAmendRequest(BaseModel):
    """SOAP 修改請求"""

    soap: Dict[str, Any] = Field(..., description="修改後的 SOAP 內容")
    user_id: str = Field(default="system", description="操作者 ID")


class SearchRecord(BaseModel):
    """搜尋結果中的單筆記錄摘要"""

    id: int
    session_id: str
    patient_name: str
    patient_id: Optional[int] = None
    created_at: str
    status: str
    soap_summary: str = ""
    audio_duration_ms: int = 0
    doctor_name: str = ""


class SearchResponse(BaseModel):
    """搜尋問診記錄回應"""

    total: int
    page: int
    page_size: int
    total_pages: int
    records: List[SearchRecord]


class AuditEntry(BaseModel):
    """審計記錄項目"""

    id: int
    record_id: int
    action: str
    user_id: str
    action_timestamp: str
    before_value: Optional[str] = None
    after_value: Optional[str] = None
    user_agent: str = ""
    ip_address: str = ""


class AmendResponse(BaseModel):
    """SOAP 修改回應"""

    status: str
    record_id: int


# ── 輔助函式 ──────────────────────────────────────────────────


def _extract_soap_summary(soap_json_str: Optional[str]) -> str:
    """從 SOAP JSON 中提取摘要文字（前 100 字）

    優先取 assessment，其次 conversation_summary。

    Args:
        soap_json_str: SOAP 的 JSON 字串

    Returns:
        摘要文字（最多 100 字）
    """
    if not soap_json_str:
        return ""
    try:
        soap_dict = json.loads(soap_json_str) if isinstance(soap_json_str, str) else soap_json_str
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(soap_dict, dict):
        return ""
    # 優先取 assessment，其次 conversation_summary
    summary = soap_dict.get("assessment") or soap_dict.get("conversation_summary") or ""
    # 轉為字串並截斷
    if isinstance(summary, dict):
        summary = summary.get("content") or summary.get("text") or json.dumps(summary, ensure_ascii=False)
    if not isinstance(summary, str):
        summary = str(summary)
    return summary[:100] if len(summary) > 100 else summary


def _build_search_record(row: Dict[str, Any]) -> SearchRecord:
    """將 DB row dict 轉換為 SearchRecord pydantic model

    同時從 soap_json 提取 soap_summary 摘要。
    """
    return SearchRecord(
        id=row.get("id", 0),
        session_id=row.get("session_id", ""),
        patient_name=row.get("patient_name", ""),
        patient_id=row.get("patient_id"),
        created_at=row.get("created_at", ""),
        status=row.get("status", ""),
        soap_summary=_extract_soap_summary(row.get("soap_json")),
        audio_duration_ms=row.get("audio_duration_ms", 0),
        doctor_name=row.get("doctor_name", ""),
    )


# ── REST 端點 ─────────────────────────────────────────────────


@router.get("/search", response_model=SearchResponse)
async def search_records(
    name: str = Query(default="", description="病患姓名關鍵字（模糊比對）"),
    date_from: str = Query(default="", description="開始日期（YYYY-MM-DD）"),
    date_to: str = Query(default="", description="結束日期（YYYY-MM-DD）"),
    page: int = Query(default=1, ge=1, description="頁碼（1-indexed）"),
    page_size: int = Query(default=20, ge=1, le=100, description="每頁筆數（1-100）"),
):
    """搜尋歷史問診記錄（PERS-02）

    支援病患姓名模糊比對、日期範圍篩選、分頁瀏覽。
    只回傳 status='completed' 的記錄，結果依時間倒序排列。

    **範例:**
    ```
    GET /api/v1/records/search?name=張三&date_from=2026-04-01&date_to=2026-04-30&page=1&page_size=20
    ```
    """
    try:
        result = await search_consultation_records(
            name=name,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        records = [_build_search_record(r) for r in result.get("records", [])]
        return SearchResponse(
            total=result.get("total", 0),
            page=result.get("page", page),
            page_size=result.get("page_size", page_size),
            total_pages=result.get("total_pages", 0),
            records=records,
        )
    except Exception as e:
        logger.error(f"搜詢問診記錄失敗: name={name}, date_from={date_from}, date_to={date_to}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{record_id}")
async def get_record(record_id: int):
    """取得單筆問診完整記錄

    回傳所有欄位，含 transcript_text、soap_json、metadata。

    **範例:**
    ```
    GET /api/v1/records/1
    ```
    """
    try:
        record = await get_consultation_by_id(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"問診記錄不存在: id={record_id}")

        # 解析 JSON 欄位以便客戶端使用
        try:
            record["soap_json"] = json.loads(record.get("soap_json", "{}"))
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            record["transcript_segments_json"] = json.loads(
                record.get("transcript_segments_json", "[]")
            )
        except (json.JSONDecodeError, TypeError):
            pass

        return record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得問診記錄失敗: record_id={record_id}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{record_id}/audit")
async def get_record_audit(record_id: int):
    """取得問診記錄的審計追蹤（PERS-01）

    回傳該記錄的所有操作記錄，依時間遞增排序。

    **範例:**
    ```
    GET /api/v1/records/1/audit
    ```
    """
    try:
        # 先確認記錄存在
        record = await get_consultation_by_id(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"問診記錄不存在: id={record_id}")

        audit_logs = await get_audit_log(record_id)
        return {
            "record_id": record_id,
            "total": len(audit_logs),
            "audit_logs": audit_logs,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"取得審計記錄失敗: record_id={record_id}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{record_id}/soap", response_model=AmendResponse)
async def amend_record_soap(record_id: int, request: SOAPAmendRequest):
    """修改 SOAP 病歷（PERS-01 審計追蹤）

    修改前後值自動記錄至 soap_audit_log，記錄不可被刪除。
    審計日誌保留 before_value 和 after_value 以利比對。

    **範例:**
    ```
    PATCH /api/v1/records/1/soap
    {
        "soap": {"subjective": "修改後的主訴內容", "objective": "...", "assessment": "...", "plan": "..."},
        "user_id": "doctor_wang"
    }
    ```
    """
    try:
        success = await amend_soap(
            record_id=record_id,
            new_soap=request.soap,
            user_id=request.user_id,
        )
        if not success:
            raise HTTPException(status_code=404, detail=f"問診記錄不存在: id={record_id}")

        logger.info(
            f"SOAP 已修改: record_id={record_id}, user={request.user_id}"
        )
        return AmendResponse(status="amended", record_id=record_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"修改 SOAP 失敗: record_id={record_id}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── 患者身份驗證端點 (LINE 外掛用) ──────────────────────────────


class PatientVerifyResponse(BaseModel):
    """患者身份驗證回應"""

    verified: bool
    patient_id: Optional[int] = None


@router.get("/patient/verify", response_model=PatientVerifyResponse)
async def verify_patient_identity(
    name: str = Query(..., min_length=1, description="患者姓名"),
    birth_year: str = Query(..., pattern=r"^\d{4}$", description="出生年份（YYYY）"),
):
    """患者身份驗證端點 (LINE 外掛用)

    LINE 患者帳號連結時，透過姓名 + 出生年份驗證患者身份。
    僅返回 {verified, patient_id}，不洩露病歷內容。

    **設計理由:**
    - 隱私保護：患者身份驗證與病歷查詢分離
    - LINE userId 永不存入醫療資料庫
    - 驗證成功後，外掛在本地 SQLite 記錄 LINE userId ↔ patient_id 映射

    **範例:**
    ```
    GET /api/v1/patient/verify?name=王小明&birth_year=1975
    Response: {"verified": true, "patient_id": 123}
    ```
    """
    try:
        db = await get_patient_records_db()
        cursor = await db.execute(
            """
            SELECT id FROM patient_records
            WHERE name = ? AND birth_date LIKE ?
            LIMIT 1
            """,
            (name, f"{birth_year}%"),
        )
        row = await cursor.fetchone()

        if row:
            patient_id = row[0]
            logger.info(f"患者身份驗證成功: name={name}, birth_year={birth_year}, patient_id={patient_id}")
            return PatientVerifyResponse(verified=True, patient_id=patient_id)
        else:
            logger.warning(f"患者身份驗證失敗: name={name}, birth_year={birth_year}")
            return PatientVerifyResponse(verified=False, patient_id=None)

    except Exception as e:
        logger.error(f"患者身份驗證異常: name={name}, birth_year={birth_year}, error={e}")
        raise HTTPException(status_code=500, detail=str(e))
