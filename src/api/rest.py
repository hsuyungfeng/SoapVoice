"""
REST API 端點模組

提供醫療文本標準化、ICD-10 分類、SOAP 生成等 RESTful API
"""

import logging
import time
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.nlp.terminology_mapper import MedicalTerminologyMapper, TermMapping
from src.nlp.icd10_classifier import ICD10Classifier, ICD10Match
from src.nlp.soap_classifier import SOAPClassifier, SOAPClassification
from src.soap.soap_generator import SOAPGenerator, SOAPConfig


logger = logging.getLogger(__name__)


# Router
router = APIRouter(prefix="/clinical", tags=["Clinical NLP"])


# 全域實例
_terminology_mapper: Optional[MedicalTerminologyMapper] = None
_icd10_classifier: Optional[ICD10Classifier] = None
_soap_classifier: Optional[SOAPClassifier] = None
_soap_generator: Optional[SOAPGenerator] = None


def get_terminology_mapper() -> MedicalTerminologyMapper:
    """取得術語映射器（單例）"""
    global _terminology_mapper
    if _terminology_mapper is None:
        _terminology_mapper = MedicalTerminologyMapper()
    return _terminology_mapper


def get_icd10_classifier() -> ICD10Classifier:
    """取得 ICD-10 分類器（單例）"""
    global _icd10_classifier
    if _icd10_classifier is None:
        _icd10_classifier = ICD10Classifier()
    return _icd10_classifier


def get_soap_classifier() -> SOAPClassifier:
    """取得 SOAP 分類器（單例）"""
    global _soap_classifier
    if _soap_classifier is None:
        _soap_classifier = SOAPClassifier()
    return _soap_classifier


def get_soap_generator() -> SOAPGenerator:
    """取得 SOAP 生成器（單例）"""
    global _soap_generator
    if _soap_generator is None:
        _soap_generator = SOAPGenerator()
    return _soap_generator


# Request/Response Models
class NormalizeRequest(BaseModel):
    """標準化請求"""
    text: str = Field(..., description="醫療文本（中文或英文）")
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="上下文資訊（年齡、性別、專科等）",
    )


class NormalizedTerm(BaseModel):
    """標準化術語"""
    original: str
    standard: str
    category: str
    confidence: float
    icd10_candidates: Optional[List[str]] = None


class NormalizeResponse(BaseModel):
    """標準化回應"""
    normalized_text: str
    terms: List[NormalizedTerm]
    processing_time_ms: float


class ICD10MatchResponse(BaseModel):
    """ICD-10 匹配回應"""
    code: str
    description: str
    description_zh: str
    category: str
    confidence: float
    matched_keywords: List[str]


class ICD10Response(BaseModel):
    """ICD-10 分類回應"""
    matches: List[ICD10MatchResponse]
    primary_code: Optional[str] = None
    processing_time_ms: float


class SOAPClassifyResponse(BaseModel):
    """SOAP 分類回應"""
    text: str
    category: str
    confidence: float
    matched_keywords: List[str]


class SOAPGenerateRequest(BaseModel):
    """SOAP 生成請求"""
    transcript: str = Field(..., description="醫療對話記錄")
    patient_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="病患背景（年齡、性別、主訴等）",
    )


class SOAPSection(BaseModel):
    """SOAP 段落"""
    subjective: str = ""
    objective: str = ""
    assessment: str = ""
    plan: str = ""
    conversation_summary: str = ""


class SOAPGenerateResponse(BaseModel):
    """SOAP 生成回應"""
    soap: SOAPSection
    metadata: Dict[str, Any]
    processing_time_ms: float


# API Endpoints
@router.post("/normalize", response_model=NormalizeResponse)
async def normalize_text(
    request: NormalizeRequest,
    mapper: MedicalTerminologyMapper = Depends(get_terminology_mapper),
):
    """
    醫療文本標準化

    將口語中文/英文轉換為標準醫療英文術語

    **範例:**
    ```
    POST /api/v1/clinical/normalize
    {
        "text": "病人說他胸悶兩天還有點喘",
        "context": {"specialty": "general"}
    }
    ```
    """
    start_time = time.time()

    try:
        # 執行映射
        normalized_text, mappings = mapper.map_text(request.text)

        # 轉換為回應格式
        terms = [
            NormalizedTerm(
                original=m.original,
                standard=m.standard,
                category=m.category,
                confidence=m.confidence,
                icd10_candidates=m.icd10_candidates,
            )
            for m in mappings
        ]

        processing_time = (time.time() - start_time) * 1000

        return NormalizeResponse(
            normalized_text=normalized_text,
            terms=terms,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        logger.error(f"Normalization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/icd10", response_model=ICD10Response)
async def classify_icd10(
    request: NormalizeRequest,
    classifier: ICD10Classifier = Depends(get_icd10_classifier),
):
    """
    ICD-10 代碼分類

    根據症狀描述自動映射到 ICD-10 代碼

    **範例:**
    ```
    POST /api/v1/clinical/icd10
    {
        "text": "病人胸悶兩天，呼吸困難",
        "context": {"age": 45, "gender": "M"}
    }
    ```
    """
    start_time = time.time()

    try:
        # 取得病患背景
        context = request.context or {}
        age = context.get("age")
        gender = context.get("gender")

        # 執行分類
        if age is not None or gender is not None:
            matches = classifier.classify_with_context(
                request.text,
                patient_age=age,
                patient_gender=gender,
            )
        else:
            matches = classifier.classify(request.text)

        # 轉換為回應格式
        match_responses = [
            ICD10MatchResponse(
                code=m.code,
                description=m.description,
                description_zh=m.description_zh,
                category=m.category,
                confidence=m.confidence,
                matched_keywords=m.matched_keywords,
            )
            for m in matches
        ]

        processing_time = (time.time() - start_time) * 1000

        return ICD10Response(
            matches=match_responses,
            primary_code=match_responses[0].code if match_responses else None,
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        logger.error(f"ICD-10 classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/classify/soap", response_model=SOAPClassifyResponse)
async def classify_soap(
    request: NormalizeRequest,
    classifier: SOAPClassifier = Depends(get_soap_classifier),
):
    """
    SOAP 分類

    將醫療文本分類為 S/O/A/P 類別

    **範例:**
    ```
    POST /api/v1/clinical/classify/soap
    {"text": "病人說他頭痛"}
    ```
    """
    try:
        result = classifier.classify(request.text)

        return SOAPClassifyResponse(
            text=result.text,
            category=result.category,
            confidence=result.confidence,
            matched_keywords=result.matched_keywords,
        )

    except Exception as e:
        logger.error(f"SOAP classification error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/soap/generate", response_model=SOAPGenerateResponse)
async def generate_soap(
    request: SOAPGenerateRequest,
    generator: SOAPGenerator = Depends(get_soap_generator),
):
    """
    SOAP 病歷生成

    從醫療對話記錄生成完整的 SOAP 病歷

    **範例:**
    ```
    POST /api/v1/clinical/soap/generate
    {
        "transcript": "病人胸悶兩天伴隨呼吸困難",
        "patient_context": {
            "age": 45,
            "gender": "M",
            "chief_complaint": "chest pain"
        }
    }
    ```
    """
    start_time = time.time()

    try:
        # 生成 SOAP
        soap_dict = generator.generate(
            transcript=request.transcript,
            patient_context=request.patient_context,
        )

        processing_time = (time.time() - start_time) * 1000

        return SOAPGenerateResponse(
            soap=SOAPSection(
                subjective=soap_dict.get("subjective", ""),
                objective=soap_dict.get("objective", ""),
                assessment=soap_dict.get("assessment", ""),
                plan=soap_dict.get("plan", ""),
                conversation_summary=soap_dict.get("conversation_summary", ""),
            ),
            metadata={
                "confidence": soap_dict.get("classification_confidence", {}),
                "model_version": generator.config.model_id,
                "normalized_terms": soap_dict.get("normalized_terms", []),
            },
            processing_time_ms=round(processing_time, 2),
        )

    except Exception as e:
        logger.error(f"SOAP generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def clinical_health():
    """
    臨床 NLP 服務健康檢查
    """
    return {
        "status": "healthy",
        "service": "clinical-nlp",
        "components": {
            "terminology_mapper": "initialized" if _terminology_mapper else "not_initialized",
            "icd10_classifier": "initialized" if _icd10_classifier else "not_initialized",
            "soap_classifier": "initialized" if _soap_classifier else "not_initialized",
            "soap_generator": "initialized" if _soap_generator else "not_initialized",
        },
    }
