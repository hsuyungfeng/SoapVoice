"""
DoctorConsultation API 客戶端模組

整合 doctor-toolbox.com 的 DoctorConsultation LLM API
提供雲端醫療 SOAP 病歷生成功能
"""

import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class DoctorConsultationConfig:
    """DoctorConsultation API 配置"""

    api_key: str = ""
    base_url: str = "https://doctor-toolbox.com/DoctorConsultation"
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0
    temperature: float = 0.3
    max_tokens: int = 2048


class DoctorConsultationError(Exception):
    """DoctorConsultation API 錯誤"""

    def __init__(
        self, message: str, status_code: Optional[int] = None, details: Optional[Dict] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class DoctorConsultationClient:
    """DoctorConsultation API 客戶端

    使用外部 LLM API 生成醫療 SOAP 病歷
    適用於複雜病例、需要更高推理品質的場景
    """

    def __init__(self, config: Optional[DoctorConsultationConfig] = None):
        """初始化 DoctorConsultation 客戶端

        Args:
            config: API 配置
        """
        self.config = config or DoctorConsultationConfig()
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        """取得 HTTP 客戶端"""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        return self._client

    def close(self) -> None:
        """關閉客戶端"""
        if self._client:
            self._client.close()
            self._client = None

    def generate_soap(
        self,
        transcript: str,
        patient_context: Optional[Dict[str, Any]] = None,
        icd10_codes: Optional[List[str]] = None,
        drug_recommendations: Optional[List[Dict[str, str]]] = None,
        medical_orders: Optional[List[Dict[str, str]]] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """生成 SOAP 病歷

        Args:
            transcript: 醫療對話轉錄文字
            patient_context: 病患背景（年齡、性別、過敏史等）
            icd10_codes: ICD-10 建議碼列表
            drug_recommendations: 藥品建議列表
            medical_orders: 醫療服務建議列表

        Returns:
            SOAP 病歷字典 {
                "subjective": "...",
                "objective": "...",
                "assessment": "...",
                "plan": "...",
                "conversation_summary": "..."
            }
        """
        start_time = time.time()
        client = self._get_client()

        payload = {
            "transcript": transcript,
            "patient_context": patient_context or {},
            "icd10_codes": icd10_codes or [],
            "drug_recommendations": [
                {
                    "code": d.get("code", ""),
                    "name": d.get("name", ""),
                    "atc_code": d.get("atc_code", ""),
                }
                for d in (drug_recommendations or [])
            ],
            "medical_orders": [
                {
                    "code": o.get("code", ""),
                    "name": o.get("name", ""),
                    "category": o.get("category", ""),
                }
                for o in (medical_orders or [])
            ],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
        }

        for attempt in range(self.config.max_retries):
            try:
                response = client.post("/generate", json=payload)
                response.raise_for_status()

                result = response.json()
                elapsed = time.time() - start_time
                logger.info(f"SOAP generated successfully in {elapsed:.2f}s")

                return self._parse_soap_response(result)

            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.config.max_retries - 1:
                    logger.warning(f"Server error ({e.response.status_code}), retrying...")
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise DoctorConsultationError(
                    message=f"HTTP error: {e.response.status_code}",
                    status_code=e.response.status_code,
                    details={"response": e.response.text},
                )
            except httpx.RequestError as e:
                if attempt < self.config.max_retries - 1:
                    logger.warning(f"Request error: {e}, retrying...")
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue
                raise DoctorConsultationError(
                    message=f"Request error: {e}",
                    details={"type": type(e).__name__},
                )

        raise DoctorConsultationError("Max retries exceeded")

    def enhance_soap(
        self,
        soap: Dict[str, str],
        transcript: str,
        focus: str = "assessment",
    ) -> Dict[str, str]:
        """增強現有 SOAP 病歷

        Args:
            soap: 現有 SOAP 病歷
            transcript: 原始對話轉錄
            focus: 專注領域（assessment, plan, both）

        Returns:
            增強後的 SOAP 病歷
        """
        client = self._get_client()

        payload = {
            "action": "enhance",
            "soap": soap,
            "transcript": transcript,
            "focus": focus,
        }

        response = client.post("/enhance", json=payload)
        response.raise_for_status()

        return self._parse_soap_response(response.json())

    def validate_diagnosis(
        self,
        icd10_code: str,
        symptoms: str,
        patient_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """驗證診斷

        Args:
            icd10_code: ICD-10 診斷碼
            symptoms: 症狀描述
            patient_context: 病患背景

        Returns:
            驗證結果
        """
        client = self._get_client()

        payload = {
            "action": "validate_diagnosis",
            "icd10_code": icd10_code,
            "symptoms": symptoms,
            "patient_context": patient_context or {},
        }

        response = client.post("/validate", json=payload)
        response.raise_for_status()

        return response.json()

    def suggest_treatment(
        self,
        diagnosis: str,
        icd10_code: str,
        patient_context: Optional[Dict[str, Any]] = None,
        drug_recommendations: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """建議治療方案

        Args:
            diagnosis: 診斷描述
            icd10_code: ICD-10 診斷碼
            patient_context: 病患背景
            drug_recommendations: 已有的藥品建議

        Returns:
            治療建議
        """
        client = self._get_client()

        payload = {
            "action": "suggest_treatment",
            "diagnosis": diagnosis,
            "icd10_code": icd10_code,
            "patient_context": patient_context or {},
            "drug_recommendations": drug_recommendations or [],
        }

        response = client.post("/treatment", json=payload)
        response.raise_for_status()

        return response.json()

    def check_drug_interactions(
        self,
        drugs: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """檢查藥物交互作用

        Args:
            drugs: 藥品列表 [{"code": "...", "name": "..."}]

        Returns:
            交互作用列表
        """
        client = self._get_client()

        payload = {
            "action": "drug_interactions",
            "drugs": drugs,
        }

        response = client.post("/interactions", json=payload)
        response.raise_for_status()

        return response.json().get("interactions", [])

    def summarize_consultation(
        self,
        transcript: str,
        language: str = "zh-TW",
    ) -> str:
        """總結諮詢內容

        Args:
            transcript: 對話轉錄
            language: 輸出語言

        Returns:
            總結文字
        """
        client = self._get_client()

        payload = {
            "action": "summarize",
            "transcript": transcript,
            "language": language,
        }

        response = client.post("/summarize", json=payload)
        response.raise_for_status()

        return response.json().get("summary", "")

    def _parse_soap_response(self, response: Dict[str, Any]) -> Dict[str, str]:
        """解析 SOAP 回應

        Args:
            response: API 回應

        Returns:
            SOAP 病歷字典
        """
        if "soap" in response:
            return response["soap"]

        if "data" in response:
            response = response["data"]

        return {
            "subjective": response.get("subjective", ""),
            "objective": response.get("objective", ""),
            "assessment": response.get("assessment", ""),
            "plan": response.get("plan", ""),
            "conversation_summary": response.get("conversation_summary", ""),
        }

    def health_check(self) -> bool:
        """健康檢查

        Returns:
            API 是否可用
        """
        try:
            client = self._get_client()
            response = client.get("/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def __enter__(self):
        """上下文管理器入口"""
        self._get_client()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 全域客戶端實例
_client: Optional[DoctorConsultationClient] = None


def get_doctor_client(
    config: Optional[DoctorConsultationConfig] = None,
) -> DoctorConsultationClient:
    """獲取全域 DoctorConsultation 客戶端實例

    Args:
        config: API 配置

    Returns:
        DoctorConsultationClient 實例
    """
    global _client
    if _client is None:
        _client = DoctorConsultationClient(config)
    return _client


def initialize_doctor_client(
    config: Optional[DoctorConsultationConfig] = None,
) -> DoctorConsultationClient:
    """初始化全域 DoctorConsultation 客戶端

    Args:
        config: API 配置

    Returns:
        已初始化的 DoctorConsultationClient 實例
    """
    client = get_doctor_client(config)
    if client.config.api_key:
        try:
            client.health_check()
        except Exception as e:
            logger.warning(f"DoctorConsultation API health check failed: {e}")
    return client
