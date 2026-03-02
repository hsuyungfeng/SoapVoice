"""
VLLM Engine 模組

提供本地 LLM 推理引擎，支援 Qwen3-32B 和 GLM-4.7-Flash 模型
使用 vLLM 進行高效推理
"""

import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from vllm import LLM, SamplingParams


logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型配置"""

    model_id: str
    trust_remote_code: bool = True
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.9
    max_model_len: int = 4096
    dtype: str = "float16"
    enforce_eager: bool = False
    quantization: Optional[str] = None


class VLLMEngine:
    """vLLM 推理引擎"""

    def __init__(self, config: Optional[ModelConfig] = None):
        """初始化 VLLM Engine

        Args:
            config: 模型配置，預設使用 Qwen3-32B-Instruct
        """
        self.config = config or ModelConfig(
            model_id="Qwen/Qwen3-32B-Instruct",
            trust_remote_code=True,
            tensor_parallel_size=1,
            gpu_memory_utilization=0.9,
            max_model_len=4096,
            dtype="float16",
            enforce_eager=False,
        )
        self._llm: Optional[LLM] = None
        self._initialized = False

    def initialize(self) -> None:
        """初始化 vLLM 引擎

        載入模型到 GPU 記憶體
        """
        if self._initialized:
            logger.warning("Engine already initialized")
            return

        logger.info(f"Initializing vLLM engine with model: {self.config.model_id}")

        # 設置環境變數
        os.environ.setdefault("VLLM_ATTENTION_BACKEND", "FLASH_ATTN")

        try:
            self._llm = LLM(
                model=self.config.model_id,
                trust_remote_code=self.config.trust_remote_code,
                tensor_parallel_size=self.config.tensor_parallel_size,
                gpu_memory_utilization=self.config.gpu_memory_utilization,
                max_model_len=self.config.max_model_len,
                dtype=self.config.dtype,
                enforce_eager=self.config.enforce_eager,
                quantization=self.config.quantization,
            )
            self._initialized = True
            logger.info("vLLM engine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize vLLM engine: {e}")
            raise

    def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> str:
        """生成回應

        Args:
            prompt: 輸入提示詞
            max_tokens: 最大生成 token 數
            temperature: 溫度參數
            top_p: Top-p 採樣參數
            stop: 停止 token 列表
            **kwargs: 其他參數

        Returns:
            生成的文字回應
        """
        if not self._initialized:
            self.initialize()

        sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
            **kwargs,
        )

        try:
            outputs = self._llm.generate([prompt], sampling_params)
            return outputs[0].outputs[0].text
        except Exception as e:
            logger.error(f"Generation error: {e}")
            raise

    def generate_batch(
        self,
        prompts: List[str],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> List[str]:
        """批次生成回應

        Args:
            prompts: 輸入提示詞列表
            max_tokens: 最大生成 token 數
            temperature: 溫度參數
            top_p: Top-p 採樣參數
            stop: 停止 token 列表
            **kwargs: 其他參數

        Returns:
            生成的文字回應列表
        """
        if not self._initialized:
            self.initialize()

        sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop,
            **kwargs,
        )

        try:
            outputs = self._llm.generate(prompts, sampling_params)
            return [output.outputs[0].text for output in outputs]
        except Exception as e:
            logger.error(f"Batch generation error: {e}")
            raise

    def is_initialized(self) -> bool:
        """檢查引擎是否已初始化"""
        return self._initialized

    def shutdown(self) -> None:
        """關閉引擎，釋放資源"""
        if self._llm is not None:
            del self._llm
            self._llm = None
        self._initialized = False
        logger.info("vLLM engine shutdown")


# 全域引擎實例（單例模式）
_engine: Optional[VLLMEngine] = None


def get_engine(config: Optional[ModelConfig] = None) -> VLLMEngine:
    """獲取全域 VLLM 引擎實例

    Args:
        config: 模型配置

    Returns:
        VLLMEngine 實例
    """
    global _engine
    if _engine is None:
        _engine = VLLMEngine(config)
    return _engine


def initialize_engine(config: Optional[ModelConfig] = None) -> VLLMEngine:
    """初始化全域 VLLM 引擎

    Args:
        config: 模型配置

    Returns:
        已初始化的 VLLMEngine 實例
    """
    engine = get_engine(config)
    if not engine.is_initialized():
        engine.initialize()
    return engine
