from .ollama_engine import OllamaEngine, ModelConfig, get_engine, initialize_engine
from .llama_engine import LlamaEngine, LlamaConfig, get_llama_engine, initialize_llama_engine
from .doctor_consultation import (
    DoctorConsultationClient,
    DoctorConsultationConfig,
    DoctorConsultationError,
    get_doctor_client,
    initialize_doctor_client,
)
from .dual_engine import DualLLMEngine, get_dual_engine, LLMPriority

# 向後相容
VLLMEngine = OllamaEngine

__all__ = [
    # Ollama
    "OllamaEngine",
    "VLLMEngine",
    "ModelConfig",
    "get_engine",
    "initialize_engine",
    # Llama.cpp
    "LlamaEngine",
    "LlamaConfig",
    "get_llama_engine",
    "initialize_llama_engine",
    # DoctorConsultation
    "DoctorConsultationClient",
    "DoctorConsultationConfig",
    "DoctorConsultationError",
    "get_doctor_client",
    "initialize_doctor_client",
    # Dual Engine
    "DualLLMEngine",
    "get_dual_engine",
    "LLMPriority",
]
