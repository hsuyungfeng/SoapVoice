from .ollama_engine import OllamaEngine, ModelConfig, get_engine, initialize_engine

# 向後相容
VLLMEngine = OllamaEngine

__all__ = ["OllamaEngine", "VLLMEngine", "ModelConfig", "get_engine", "initialize_engine"]
