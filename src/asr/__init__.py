"""
ASR (Automatic Speech Recognition) 模組

提供語音轉文字功能
支援 Faster-Whisper 與 Qwen3-ASR 兩種後端
"""

from src.asr.whisper_model import WhisperModel
from src.asr.qwen3asr_model import Qwen3ASRModel
from src.asr.asr_factory import ASRBackendFactory, ChineseConverter, create_asr_model, ASRBackend
from src.asr.vocabulary import MedicalVocabulary

__all__ = [
    "WhisperModel",
    "Qwen3ASRModel",
    "ASRBackendFactory",
    "ChineseConverter",
    "create_asr_model",
    "ASRBackend",
    "MedicalVocabulary",
]
