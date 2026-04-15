"""
ASR (Automatic Speech Recognition) 模組

提供語音轉文字功能
支援 Faster-Whisper 與 Qwen3-ASR 兩種後端
"""

# 使用延遲 import 避免 torch 在啟動時載入 CUDA 庫
# 只在需要時才 import Qwen3ASRModel


def __getattr__(name):
    """延遲 import - 只在訪問時才載入模組"""
    if name == "WhisperModel":
        from src.asr.whisper_model import WhisperModel

        return WhisperModel
    elif name == "Qwen3ASRModel":
        from src.asr.qwen3asr_model import Qwen3ASRModel

        return Qwen3ASRModel
    elif name == "ASRBackendFactory":
        from src.asr.asr_factory import ASRBackendFactory

        return ASRBackendFactory
    elif name == "ChineseConverter":
        from src.asr.asr_factory import ChineseConverter

        return ChineseConverter
    elif name == "create_asr_model":
        from src.asr.asr_factory import create_asr_model

        return create_asr_model
    elif name == "ASRBackend":
        from src.asr.asr_factory import ASRBackend

        return ASRBackend
    elif name == "MedicalVocabulary":
        from src.asr.vocabulary import MedicalVocabulary

        return MedicalVocabulary
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# 為了相容性，仍然定義 __all__
__all__ = [
    "WhisperModel",
    "Qwen3ASRModel",
    "ASRBackendFactory",
    "ChineseConverter",
    "create_asr_model",
    "ASRBackend",
    "MedicalVocabulary",
]
