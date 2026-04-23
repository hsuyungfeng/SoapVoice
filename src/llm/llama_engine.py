"""
Llama.cpp LLM 推理引擎模組

使用 llama-cpp-python 提供本地 LLM 推理能力
支援 GGUF 格式模型（Q4_K_M 量化）
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator
import os
from dataclasses import dataclass, field
from src.utils.resource_path import get_resource_path

logger = logging.getLogger(__name__)


def _get_default_model_path() -> str:
    """取得預設模型路徑，優先使用環境變數 LLAMA_MODEL_PATH"""
    env_path = os.getenv("LLAMA_MODEL_PATH")
    if env_path:
        return env_path
    # 使用資源路徑偵測工具解析預設相對路徑
    return str(get_resource_path("models/qwen2.5-3b-instruct-q4_k_m.gguf"))


@dataclass
class LlamaConfig:
    """Llama.cpp 模型配置"""

    model_path: str = field(default_factory=_get_default_model_path)
    n_gpu_layers: int = field(default_factory=lambda: int(os.getenv("LLAMA_N_GPU_LAYERS", "0")))
    n_ctx: int = 4096
    n_threads: int = 8
    n_threads_batch: int = 8
    n_batch: int = 512
    n_ubatch: int = 512
    flash_attn: bool = True
    temperature: float = 0.3
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    max_tokens: int = 2048
    rope_freq_base: float = 0.0
    rope_freq_scale: float = 0.0
    use_mmap: bool = True
    use_mlock: bool = False
    verbose: bool = False


class LlamaEngine:
    """Llama.cpp LLM 推理引擎

    使用 llama-cpp-python 提供高效的本地 LLM 推理
    支援 GGUF 格式模型、GPU offload、串流生成
    """

    def __init__(self, config: Optional[LlamaConfig] = None):
        """初始化 Llama Engine

        Args:
            config: 模型配置
        """
        self.config = config or LlamaConfig()
        self._model = None
        self._initialized = False

    def _load_model(self) -> None:
        """載入模型"""
        if self._model is not None:
            return

        try:
            from llama_cpp import Llama
        except ImportError:
            logger.error(
                "llama-cpp-python not installed. Install with: pip install llama-cpp-python"
            )
            raise ImportError(
                "llama-cpp-python is required for local LLM inference. "
                "Install with: pip install llama-cpp-python"
            )

        model_path = Path(self.config.model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {model_path}\n"
                f"Download from: huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF"
            )

        logger.info(f"Loading LLM model: {model_path}")
        logger.info(f"  n_gpu_layers: {self.config.n_gpu_layers}")
        logger.info(f"  n_ctx: {self.config.n_ctx}")
        logger.info(f"  n_threads: {self.config.n_threads}")

        self._model = Llama(
            model_path=str(model_path.resolve()),
            n_gpu_layers=self.config.n_gpu_layers,
            n_ctx=self.config.n_ctx,
            n_threads=self.config.n_threads,
            n_threads_batch=self.config.n_threads_batch,
            n_batch=self.config.n_batch,
            n_ubatch=self.config.n_ubatch,
            flash_attn=self.config.flash_attn,
            rope_freq_base=self.config.rope_freq_base,
            rope_freq_scale=self.config.rope_freq_scale,
            use_mmap=self.config.use_mmap,
            use_mlock=self.config.use_mlock,
            verbose=self.config.verbose,
        )
        self._initialized = True
        logger.info("LLM model loaded successfully")

    def initialize(self) -> None:
        """初始化引擎"""
        if self._initialized:
            logger.warning("Engine already initialized")
            return
        self._load_model()

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        repeat_penalty: Optional[float] = None,
        stop: Optional[List[str]] = None,
        echo: bool = False,
        **kwargs,
    ) -> str:
        """同步生成文字

        Args:
            prompt: 輸入提示詞
            system: 系統提示（可選）
            max_tokens: 最大生成 token 數
            temperature: 生成溫度
            top_p: Top-p 採樣
            top_k: Top-k 採樣
            repeat_penalty: 重複懲罰
            stop: 停止關鍵字列表
            echo: 是否回顯輸入

        Returns:
            生成的文字
        """
        if not self._initialized:
            self._load_model()

        if self._model is None:
            raise RuntimeError("Model not loaded")

        # 建構完整 prompt
        full_prompt = self._build_prompt(prompt, system)

        output = self._model(
            full_prompt,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=top_p or self.config.top_p,
            top_k=top_k or self.config.top_k,
            repeat_penalty=repeat_penalty or self.config.repeat_penalty,
            stop=stop or [],
            echo=echo,
        )

        return output["choices"][0]["text"].strip()

    def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """串流生成文字

        Args:
            prompt: 輸入提示詞
            system: 系統提示（可選）
            max_tokens: 最大生成 token 數
            temperature: 生成溫度
            stop: 停止關鍵字列表

        Yields:
            生成的文字片段
        """
        if not self._initialized:
            self._load_model()

        if self._model is None:
            raise RuntimeError("Model not loaded")

        full_prompt = self._build_prompt(prompt, system)

        for output in self._model(
            full_prompt,
            max_tokens=max_tokens or self.config.max_tokens,
            temperature=temperature if temperature is not None else self.config.temperature,
            top_p=self.config.top_p,
            repeat_penalty=self.config.repeat_penalty,
            stop=stop or [],
            stream=True,
        ):
            chunk = output["choices"][0]["text"]
            if chunk:
                yield chunk

    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs,
    ) -> str:
        """聊天模式生成

        Args:
            messages: 訊息列表 [{"role": "user", "content": "..."}]
            max_tokens: 最大生成 token 數
            temperature: 生成溫度

        Returns:
            生成的回應
        """
        if not self._initialized:
            self._load_model()

        if self._model is None:
            raise RuntimeError("Model not loaded")

        # 檢查是否支援 chat 格式
        try:
            from llama_cpp import LlamaRole  # noqa: F401

            # 使用 chat 格式
            output = self._model.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens or self.config.max_tokens,
                temperature=temperature if temperature is not None else self.config.temperature,
            )
            return output["choices"][0]["message"]["content"]
        except (ImportError, AttributeError):
            logger.warning("Chat format not available, using prompt format")
            prompt = self._messages_to_prompt(messages)
            return self.generate(prompt, max_tokens=max_tokens, temperature=temperature)

    def _build_prompt(self, prompt: str, system: Optional[str] = None) -> str:
        """建構完整 prompt (根據模型類型調整)"""
        # 檢查是否為 Gemma 4
        is_gemma = "gemma" in self.config.model_path.lower()

        if is_gemma:
            if system:
                return f"<start_of_turn>user\n{system}\n\n{prompt}<end_of_turn>\n<start_of_turn>model\n"
            return f"<start_of_turn>user\n{prompt}<end_of_turn>\n<start_of_turn>model\n"

        # 預設 (Qwen/通用)
        if system:
            return f"【系統】{system}\n\n【使用者】{prompt}\n\n【助理】"
        return f"【使用者】{prompt}\n\n【助理】"

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """將訊息列表轉換為 prompt

        Args:
            messages: 訊息列表

        Returns:
            prompt 字串
        """
        parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                parts.append(f"【系統】{content}")
            elif role == "user":
                parts.append(f"【使用者】{content}")
            elif role == "assistant":
                parts.append(f"【助理】{content}")

        parts.append("【助理】")
        return "\n\n".join(parts)

    def is_initialized(self) -> bool:
        """檢查引擎是否已初始化"""
        return self._initialized

    def get_model_info(self) -> Dict[str, Any]:
        """取得模型資訊

        Returns:
            模型資訊字典
        """
        return {
            "model_path": self.config.model_path,
            "n_gpu_layers": self.config.n_gpu_layers,
            "n_ctx": self.config.n_ctx,
            "n_threads": self.config.n_threads,
            "initialized": self._initialized,
        }

    def shutdown(self) -> None:
        """關閉引擎，釋放資源"""
        self._model = None
        self._initialized = False
        logger.info("Llama engine shutdown")


# 全域引擎實例
_engine: Optional[LlamaEngine] = None


def get_llama_engine(config: Optional[LlamaConfig] = None) -> LlamaEngine:
    """獲取全域 Llama 引擎實例

    Args:
        config: 模型配置

    Returns:
        LlamaEngine 實例
    """
    global _engine
    if _engine is None:
        _engine = LlamaEngine(config)
    return _engine


def initialize_llama_engine(config: Optional[LlamaConfig] = None) -> LlamaEngine:
    """初始化全域 Llama 引擎

    Args:
        config: 模型配置

    Returns:
        已初始化的 LlamaEngine 實例
    """
    engine = get_llama_engine(config)
    if not engine.is_initialized():
        engine.initialize()
    return engine
