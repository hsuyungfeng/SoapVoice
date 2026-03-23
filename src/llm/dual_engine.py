"""
雙軌 LLM 引擎模組

整合本地 Llama.cpp 和外部 DoctorConsultation API
自動選擇最適合的 LLM 進行推理
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.llm.llama_engine import LlamaEngine, LlamaConfig
from src.llm.doctor_consultation import (
    DoctorConsultationClient,
    DoctorConsultationConfig,
    DoctorConsultationError,
)


logger = logging.getLogger(__name__)


class LLMPriority(Enum):
    """LLM 優先級"""

    LOCAL_FIRST = "local_first"
    CLOUD_FIRST = "cloud_first"
    LOCAL_ONLY = "local_only"
    CLOUD_ONLY = "cloud_only"


@dataclass
class DualLLMConfig:
    """雙軌 LLM 配置"""

    priority: LLMPriority = LLMPriority.LOCAL_FIRST
    local_config: Optional[LlamaConfig] = None
    cloud_config: Optional[DoctorConsultationConfig] = None
    use_local_for_simple: bool = True
    simple_prompt_threshold: int = 200


class DualLLMEngine:
    """雙軌 LLM 引擎

    自動選擇使用本地或雲端 LLM：
    - 本地 Llama.cpp：即時處理、低延遲、完全離線
    - DoctorConsultation API：複雜推理、高品質、雲端計算

    策略：
    - LOCAL_FIRST：優先使用本地，失敗時 fallback 到雲端
    - CLOUD_FIRST：優先使用雲端，本地作為備用
    - LOCAL_ONLY：僅使用本地
    - CLOUD_ONLY：僅使用雲端
    """

    def __init__(self, config: Optional[DualLLMConfig] = None):
        """初始化雙軌 LLM 引擎

        Args:
            config: 雙軌配置
        """
        self.config = config or DualLLMConfig()
        self._local_engine: Optional[LlamaEngine] = None
        self._cloud_client: Optional[DoctorConsultationClient] = None

    def initialize(self) -> None:
        """初始化引擎"""
        # 初始化本地引擎（如果配置了）
        if self.config.local_config and self.config.priority != LLMPriority.CLOUD_ONLY:
            try:
                self._local_engine = LlamaEngine(self.config.local_config)
                self._local_engine.initialize()
                logger.info("Local LLM engine initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize local LLM: {e}")
                self._local_engine = None

        # 初始化雲端客戶端（如果配置了）
        if self.config.cloud_config and self.config.priority != LLMPriority.LOCAL_ONLY:
            self._cloud_client = DoctorConsultationClient(self.config.cloud_config)
            try:
                if self._cloud_client.health_check():
                    logger.info("Cloud LLM client initialized")
                else:
                    logger.warning("Cloud LLM health check failed")
            except Exception as e:
                logger.warning(f"Failed to initialize cloud LLM: {e}")
                self._cloud_client = None

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        use_cloud: Optional[bool] = None,
        **kwargs,
    ) -> str:
        """生成文字

        Args:
            prompt: 輸入提示詞
            system: 系統提示
            use_cloud: 是否強制使用雲端（None 為自動選擇）
            **kwargs: 其他參數

        Returns:
            生成的文字
        """
        # 自動選擇引擎
        should_use_cloud = self._should_use_cloud(prompt, use_cloud)

        if should_use_cloud and self._cloud_client:
            return self._generate_cloud(prompt, system, **kwargs)
        elif self._local_engine:
            return self._generate_local(prompt, system, **kwargs)
        elif self._cloud_client:
            logger.info("Local LLM not available, falling back to cloud")
            return self._generate_cloud(prompt, system, **kwargs)
        else:
            raise RuntimeError("No LLM engine available")

    def _should_use_cloud(self, prompt: str, use_cloud: Optional[bool] = None) -> bool:
        """判斷是否應該使用雲端

        Args:
            prompt: 提示詞
            use_cloud: 強制指定

        Returns:
            是否使用雲端
        """
        if use_cloud is not None:
            return use_cloud

        if self.config.priority == LLMPriority.LOCAL_ONLY:
            return False
        if self.config.priority == LLMPriority.CLOUD_ONLY:
            return True

        # 根據 prompt 長度和複雜度自動選擇
        prompt_length = len(prompt)

        if self.config.use_local_for_simple and prompt_length < self.config.simple_prompt_threshold:
            return False

        return self.config.priority == LLMPriority.CLOUD_FIRST

    def _generate_local(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """本地生成

        Args:
            prompt: 提示詞
            system: 系統提示
            **kwargs: 其他參數

        Returns:
            生成的文字
        """
        try:
            if self._local_engine is None:
                raise RuntimeError("Local engine not available")
            return self._local_engine.generate(prompt, system=system, **kwargs)
        except Exception as e:
            logger.warning(f"Local generation failed: {e}")
            if self._cloud_client:
                logger.info("Falling back to cloud")
                return self._generate_cloud(prompt, system, **kwargs)
            raise

    def _generate_cloud(self, prompt: str, system: Optional[str] = None, **kwargs) -> str:
        """雲端生成

        Args:
            prompt: 提示詞
            system: 系統提示
            **kwargs: 其他參數

        Returns:
            生成的文字
        """
        if self._cloud_client is None:
            raise RuntimeError("Cloud client not available")

        # 將 prompt 格式化為 SOAP 生成格式
        return (
            self._cloud_client._client.post(
                "/generate",
                json={
                    "prompt": prompt,
                    "system": system,
                    **kwargs,
                },
            )
            .json()
            .get("text", "")
        )

    def generate_soap(
        self,
        transcript: str,
        patient_context: Optional[Dict[str, Any]] = None,
        icd10_codes: Optional[List[str]] = None,
        drug_recommendations: Optional[List[Dict[str, str]]] = None,
        medical_orders: Optional[List[Dict[str, str]]] = None,
        use_cloud: Optional[bool] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """生成 SOAP 病歷

        Args:
            transcript: 對話轉錄
            patient_context: 病患背景
            icd10_codes: ICD-10 建議碼
            drug_recommendations: 藥品建議
            medical_orders: 醫療服務建議
            use_cloud: 是否使用雲端
            **kwargs: 其他參數

        Returns:
            SOAP 病歷字典
        """
        should_use_cloud = self._should_use_cloud(transcript, use_cloud)

        if should_use_cloud and self._cloud_client:
            try:
                return self._cloud_client.generate_soap(
                    transcript=transcript,
                    patient_context=patient_context,
                    icd10_codes=icd10_codes,
                    drug_recommendations=drug_recommendations,
                    medical_orders=medical_orders,
                    **kwargs,
                )
            except DoctorConsultationError as e:
                logger.warning(f"Cloud SOAP generation failed: {e}")
                if self._local_engine:
                    logger.info("Falling back to local LLM for SOAP generation")
                    return self._generate_local_soap(transcript, patient_context, **kwargs)
                raise

        if self._local_engine:
            return self._generate_local_soap(transcript, patient_context, **kwargs)
        elif self._cloud_client:
            return self._cloud_client.generate_soap(
                transcript=transcript,
                patient_context=patient_context,
                icd10_codes=icd10_codes,
                drug_recommendations=drug_recommendations,
                medical_orders=medical_orders,
                **kwargs,
            )
        else:
            raise RuntimeError("No LLM engine available")

    def _generate_local_soap(
        self,
        transcript: str,
        patient_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> Dict[str, str]:
        """使用本地 LLM 生成 SOAP

        Args:
            transcript: 對話轉錄
            patient_context: 病患背景
            **kwargs: 其他參數

        Returns:
            SOAP 病歷字典
        """
        from src.soap.soap_generator import SOAPGenerator, SOAPConfig

        config = SOAPConfig(
            model_id="local",
            max_tokens=kwargs.get("max_tokens", 1024),
            temperature=kwargs.get("temperature", 0.3),
        )

        generator = SOAPGenerator(config)

        # 注入本地引擎
        generator._engine = self._local_engine

        result = generator.generate(
            transcript=transcript,
            patient_context=patient_context,
        )

        return {
            "subjective": result.get("subjective", ""),
            "objective": result.get("objective", ""),
            "assessment": result.get("assessment", ""),
            "plan": result.get("plan", ""),
            "conversation_summary": result.get("conversation_summary", ""),
        }

    def is_local_available(self) -> bool:
        """檢查本地引擎是否可用"""
        return self._local_engine is not None and self._local_engine.is_initialized()

    def is_cloud_available(self) -> bool:
        """檢查雲端引擎是否可用"""
        return self._cloud_client is not None and self._cloud_client.health_check()

    def get_status(self) -> Dict[str, Any]:
        """取得引擎狀態

        Returns:
            狀態字典
        """
        return {
            "local_available": self.is_local_available(),
            "cloud_available": self.is_cloud_available(),
            "priority": self.config.priority.value,
            "local_info": self._local_engine.get_model_info() if self._local_engine else None,
        }

    def shutdown(self) -> None:
        """關閉引擎"""
        if self._local_engine:
            self._local_engine.shutdown()
            self._local_engine = None
        if self._cloud_client:
            self._cloud_client.close()
            self._cloud_client = None


# 全域雙軌引擎實例
_dual_engine: Optional[DualLLMEngine] = None


def get_dual_engine(config: Optional[DualLLMConfig] = None) -> DualLLMEngine:
    """獲取全域雙軌 LLM 引擎實例

    Args:
        config: 雙軌配置

    Returns:
        DualLLMEngine 實例
    """
    global _dual_engine
    if _dual_engine is None:
        _dual_engine = DualLLMEngine(config)
    return _dual_engine


def initialize_dual_engine(config: Optional[DualLLMConfig] = None) -> DualLLMEngine:
    """初始化全域雙軌 LLM 引擎

    Args:
        config: 雙軌配置

    Returns:
        已初始化的 DualLLMEngine 實例
    """
    engine = get_dual_engine(config)
    engine.initialize()
    return engine
