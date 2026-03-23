"""
擴展版 REST API 端點

提供完整 Pipeline：語音轉錄 → 症狀提取 → ICD-10 → 醫囑 → 藥物 → SOAP
"""

import logging
import time
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
import tempfile
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/extended", tags=["Extended Pipeline"])

_extended_engine = None


def get_extended_engine():
    """取得擴展引擎"""
    global _extended_engine
    if _extended_engine is None:
        from scripts.extended_soapvoice import ExtendedSoapVoiceEngine

        _extended_engine = ExtendedSoapVoiceEngine(whisper_model="medium", llm_model="qwen2.5:14b")
    return _extended_engine


class ExtendedProcessRequest(BaseModel):
    """擴展處理請求"""

    transcript: str = Field(..., description="醫療對話文字")
    include_symptoms: bool = Field(True, description="包含症狀提取")
    include_icd10: bool = Field(True, description="包含 ICD-10 分類")
    include_orders: bool = Field(True, description="包含醫囑建議")
    include_drugs: bool = Field(True, description="包含藥物建議")
    output_lang: str = Field("en", description="輸出語言 (en/zh)")


class ExtendedProcessResponse(BaseModel):
    """擴展處理回應"""

    transcript: str
    symptoms: List[str]
    icd10_codes: List[Dict[str, Any]]
    medical_orders: List[str]
    drug_recommendations: List[Dict[str, str]]
    soap: Dict[str, str]
    processing_time: float
    model: str


@router.post("/process", response_model=ExtendedProcessResponse)
async def extended_process(request: ExtendedProcessRequest):
    """
    完整擴展 Pipeline

    輸入文字，輸出：
    - 症狀列表
    - ICD-10 代碼
    - 醫囑建議
    - 藥物建議
    - SOAP 病歷
    """
    start = time.time()

    engine = get_extended_engine()

    try:
        # 症狀提取
        symptoms = []
        if request.include_symptoms:
            symptoms = engine.extract_symptoms(request.transcript)

        # ICD-10 分類
        icd10_codes = []
        if request.include_icd10:
            icd10_codes = engine.classify_icd10(request.transcript)

        # 醫囑建議
        medical_orders = []
        if request.include_orders:
            medical_orders = engine.get_medical_orders(symptoms, [c["code"] for c in icd10_codes])

        # 藥物建議
        drug_recommendations = []
        if request.include_drugs:
            drug_recommendations = engine.get_drug_recommendations(
                symptoms, [c["code"] for c in icd10_codes]
            )

        # 生成 SOAP
        soap_result = engine.generate_extended_soap(
            request.transcript, symptoms, icd10_codes, medical_orders, drug_recommendations
        )

        processing_time = time.time() - start

        return ExtendedProcessResponse(
            transcript=request.transcript,
            symptoms=symptoms,
            icd10_codes=icd10_codes,
            medical_orders=medical_orders,
            drug_recommendations=drug_recommendations,
            soap=soap_result,
            processing_time=processing_time,
            model=engine.llm_model,
        )

    except Exception as e:
        logger.error(f"擴展處理錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    音訊轉文字

    上傳音訊檔案，輸出轉錄結果
    """
    engine = get_extended_engine()

    # 保存上傳的檔案
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        transcript = engine.transcribe(tmp_path)
        return {"transcript": transcript, "language": "zh"}
    finally:
        os.unlink(tmp_path)


@router.get("/symptoms/{text}")
async def extract_symptoms(text: str):
    """症狀提取"""
    engine = get_extended_engine()
    symptoms = engine.extract_symptoms(text)
    return {"symptoms": symptoms}


@router.get("/icd10/{text}")
async def classify_icd10(text: str):
    """ICD-10 分類"""
    engine = get_extended_engine()
    icd10_codes = engine.classify_icd10(text)
    return {"icd10_codes": icd10_codes}


@router.get("/orders")
async def get_orders(symptoms: str, icd10_codes: str):
    """醫囑建議"""
    engine = get_extended_engine()
    symptoms_list = symptoms.split(",")
    icd_list = icd10_codes.split(",")
    orders = engine.get_medical_orders(symptoms_list, icd_list)
    return {"medical_orders": orders}


@router.get("/drugs")
async def get_drugs(symptoms: str, icd10_codes: str):
    """藥物建議"""
    engine = get_extended_engine()
    symptoms_list = symptoms.split(",")
    icd_list = icd10_codes.split(",")
    drugs = engine.get_drug_recommendations(symptoms_list, icd_list)
    return {"drug_recommendations": drugs}
