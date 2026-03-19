"""
Ollama Engine 模組

提供本地 LLM 推理引擎，支援 Qwen3.5 和 GLM-4.7-Flash 模型
使用 Ollama 進行高效推理
"""

import os
import logging
import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """模型配置"""

    model_id: str = "qwen3.5:9b"
    api_base: str = "http://localhost:11434"
    temperature: float = 0.3
    max_tokens: int = 1024
    num_ctx: int = 4096
    num_gpu: int = 1
    num_thread: int = 16


class OllamaEngine:
    """Ollama 推理引擎"""

    def __init__(self, config: Optional[ModelConfig] = None):
        """初始化 Ollama Engine

        Args:
            config: 模型配置，預設使用 qwen3.5:9b
        """
        self.config = config or ModelConfig()
        self._initialized = False
        self._session = requests.Session()

    def initialize(self) -> None:
        """初始化 Ollama 引擎

        檢查 Ollama 服務是否可用
        """
        if self._initialized:
            logger.warning("Engine already initialized")
            return

        logger.info(f"Initializing Ollama engine with model: {self.config.model_id}")

        try:
            # 檢查 Ollama 服務是否運行
            response = self._session.get(f"{self.config.api_base}/api/tags", timeout=5)
            if response.status_code == 200:
                self._initialized = True
                logger.info("Ollama engine initialized successfully")
            else:
                raise RuntimeError(f"Ollama service returned status {response.status_code}")
        except requests.exceptions.ConnectionError as e:
            logger.error("Failed to connect to Ollama service. Is Ollama running?")
            raise RuntimeError(f"Ollama service not available: {e}")
        except Exception as e:
            logger.error(f"Failed to initialize Ollama engine: {e}")
            raise

    def generate(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """生成回應

        Args:
            prompt: 輸入提示詞
            max_tokens: 最大生成 token 數
            temperature: 溫度參數
            stream: 是否串流回應
            **kwargs: 其他參數

        Returns:
            生成的文字回應
        """
        if not self._initialized:
            self.initialize()

        payload = {
            "model": self.config.model_id,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "num_ctx": self.config.num_ctx,
                "num_predict": max_tokens or self.config.max_tokens,
                "temperature": temperature or self.config.temperature,
            },
        }

        try:
            response = self._session.post(
                f"{self.config.api_base}/api/generate",
                json=payload,
                timeout=120,
            )
            response.raise_for_status()

            if stream:
                # 串流模式
                result = ""
                for line in response.iter_lines():
                    if line:
                        data = line.decode("utf-8")
                        import json

                        chunk = json.loads(data)
                        if "response" in chunk:
                            result += chunk["response"]
                        if chunk.get("done", False):
                            break
                return result
            else:
                # 非串流模式
                result = response.json()
                return result.get("response", "")

        except requests.exceptions.Timeout:
            logger.error("Request timeout")
            raise RuntimeError("Model generation timeout")
        except Exception as e:
            logger.error(f"Generation error: {e}")
            raise

    def generate_batch(
        self,
        prompts: List[str],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> List[str]:
        """批次生成回應

        Args:
            prompts: 輸入提示詞列表
            max_tokens: 最大生成 token 數
            temperature: 溫度參數
            **kwargs: 其他參數

        Returns:
            生成的文字回應列表
        """
        if not self._initialized:
            self.initialize()

        results = []
        for prompt in prompts:
            try:
                result = self.generate(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch generation error for prompt: {e}")
                results.append("")

        return results

    def is_initialized(self) -> bool:
        """檢查引擎是否已初始化"""
        return self._initialized

    def list_models(self) -> List[str]:
        """列出可用的模型"""
        try:
            response = self._session.get(f"{self.config.api_base}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def pull_model(self, model_name: str) -> bool:
        """下載模型

        Args:
            model_name: 模型名稱 (e.g., "qwen3.5:9b")

        Returns:
            是否成功
        """
        try:
            logger.info(f"Pulling model: {model_name}")
            response = self._session.post(
                f"{self.config.api_base}/api/pull",
                json={"name": model_name},
                timeout=300,
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False

    def shutdown(self) -> None:
        """關閉引擎，釋放資源"""
        self._session.close()
        self._initialized = False
        logger.info("Ollama engine shutdown")


# 全域引擎實例（單例模式）
_engine: Optional[OllamaEngine] = None


def get_engine(config: Optional[ModelConfig] = None) -> OllamaEngine:
    """獲取全域 Ollama 引擎實例

    Args:
        config: 模型配置

    Returns:
        OllamaEngine 實例
    """
    global _engine
    if _engine is None:
        _engine = OllamaEngine(config)
    return _engine


def initialize_engine(config: Optional[ModelConfig] = None) -> OllamaEngine:
    """初始化全域 Ollama 引擎

    Args:
        config: 模型配置

    Returns:
        已初始化的 OllamaEngine 實例
    """
    engine = get_engine(config)
    if not engine.is_initialized():
        engine.initialize()
    return engine
