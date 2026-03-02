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


class TestVLLMEngine:
    """測試 vLLM 引擎"""

    @pytest.fixture
    def engine(self):
        return VLLMEngine()

    def test_init(self, engine):
        """測試初始化"""
        assert engine.config is not None
        assert engine._llm is None
        assert engine._initialized is False

    def test_init_with_config(self):
        """測試帶配置初始化"""
        config = ModelConfig(model_id="test-model")
        engine = VLLMEngine(config)
        assert engine.config.model_id == "test-model"

    def test_is_initialized(self, engine):
        """測試初始化狀態"""
        assert engine.is_initialized() is False

    def test_shutdown(self, engine):
        """測試關閉"""
        engine.shutdown()
        assert engine.is_initialized() is False


class TestSingletonEngine:
    """測試單例引擎"""

    def test_get_engine(self):
        """測試取得引擎"""
        eng1 = get_engine()
        eng2 = get_engine()
        assert eng1 is eng2  # 應該是同一個實例

    def test_get_engine_with_config(self):
        """測試帶配置的引擎"""
        config = ModelConfig(model_id="test-model")
        eng = get_engine(config)
        assert eng.config.model_id == "test-model"
