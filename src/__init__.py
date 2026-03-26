"""
SoapVoice 醫療語音轉 SOAP 病歷系統
"""

try:
    from src.llm.ollama_engine import OllamaEngine, ModelConfig, get_engine, initialize_engine

    ollama_available = True
except ImportError:
    OllamaEngine = None
    ModelConfig = None
    get_engine = None
    initialize_engine = None
    ollama_available = False

from src.api.websocket import router as websocket_router

__version__ = "1.5.0"
__all__ = [
    "OllamaEngine",
    "ModelConfig",
    "get_engine",
    "initialize_engine",
    "websocket_router",
    "ollama_available",
]
