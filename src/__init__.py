"""
SoapVoice 醫療語音轉 SOAP 病歷系統
"""

try:
    from src.llm.vllm_engine import VLLMEngine, ModelConfig, get_engine, initialize_engine

    vllm_available = True
except ImportError:
    VLLMEngine = None
    ModelConfig = None
    get_engine = None
    initialize_engine = None
    vllm_available = False

from src.api.websocket import router as websocket_router

__version__ = "0.1.0"
__all__ = [
    "VLLMEngine",
    "ModelConfig",
    "get_engine",
    "initialize_engine",
    "websocket_router",
    "vllm_available",
]
