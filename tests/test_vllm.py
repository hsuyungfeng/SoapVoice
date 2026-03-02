"""
測試 VLLM 引擎模組
"""

import pytest
from src.llm.vllm_engine import (
    VLLMEngine,
    ModelConfig,
    get_engine,
    initialize_engine,
)


class TestModelConfig:
    """測試模型配置"""

    def test_default_config(self):
        """測試預設配置"""
        config = ModelConfig()
        assert config.model_id == "Qwen/Qwen3-32B-Instruct"
        assert config.trust_remote_code is True
        assert config.tensor_parallel_size == 1
        assert config.gpu_memory_utilization == 0.9
        assert config.dtype == "float16"

    def test_custom_config(self):
        """測試自定義配置"""
        config = ModelConfig(
            model_id="test-model",
            tensor_parallel_size=2,
            gpu_memory_utilization=0.8,
        )
        assert config.model_id == "test-model"
        assert config.tensor_parallel_size == 2
        assert config.gpu_memory_utilization == 0.8
