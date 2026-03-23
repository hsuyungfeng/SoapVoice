"""
ASR 引擎工廠與簡繁轉換工具

支援 Faster-Whisper 與 Qwen3-ASR 兩種後端
Qwen3-ASR 輸出簡體中文，自動轉換為繁體
"""

from typing import Optional
from enum import Enum


class ASRBackend(Enum):
    """ASR 引擎類型"""

    WHISPER = "whisper"
    QWEN3ASR = "qwen3asr"


class ASRBackendFactory:
    """ASR 引擎工廠

    根據配置創建對應的 ASR 模型實例
    """

    @staticmethod
    def create_backend(
        backend: str = "whisper",
        **kwargs,
    ) -> object:
        """創建 ASR 引擎實例

        Args:
            backend: 引擎類型，"whisper" 或 "qwen3asr"
            **kwargs: 傳遞給模型的額外參數

        Returns:
            ASR 模型實例
        """
        if backend == "qwen3asr":
            from src.asr.qwen3asr_model import Qwen3ASRModel

            return Qwen3ASRModel(
                model_id=kwargs.get("model_id", "Qwen/Qwen3-ASR-0.6B"),
                device=kwargs.get("device", "cuda"),
                dtype=kwargs.get("dtype"),
            )
        else:
            from src.asr.whisper_model import WhisperModel

            return WhisperModel(
                model_id=kwargs.get("model_id", "large-v3"),
                device=kwargs.get("device", "cuda"),
                compute_type=kwargs.get("compute_type", "float16"),
                download_root=kwargs.get("download_root"),
            )

    @staticmethod
    def get_backend_name(backend: str) -> str:
        """取得引擎顯示名稱"""
        names = {
            "whisper": "Faster-Whisper large-v3",
            "qwen3asr": "Qwen3-ASR-0.6B",
        }
        return names.get(backend, backend)


class ChineseConverter:
    """簡繁中文轉換器

    使用 opencc 將簡體中文轉換為繁體中文
    """

    _converter = None

    @classmethod
    def get_converter(cls, mode: str = "s2t") -> object:
        """取得轉換器實例

        Args:
            mode: 轉換模式，"s2t" 為簡體到繁體

        Returns:
            OpenCC 轉換器實例
        """
        if cls._converter is None:
            try:
                import opencc

                cls._converter = opencc.OpenCC(mode)
            except ImportError:
                cls._converter = None
        return cls._converter

    @classmethod
    def convert(cls, text: str) -> str:
        """轉換文字為繁體中文

        Args:
            text: 輸入文字（可能是簡體）

        Returns:
            繁體中文文字
        """
        converter = cls.get_converter()
        if converter is None:
            return text
        return converter.convert(text)

    @classmethod
    def is_available(cls) -> bool:
        """檢查 opencc 是否可用"""
        return cls.get_converter() is not None


def create_asr_model(
    backend: str = "whisper",
    convert_to_traditional: bool = True,
    **kwargs,
) -> tuple[object, bool]:
    """創建 ASR 模型並返回轉換器配置

    Args:
        backend: 引擎類型
        convert_to_traditional: 是否將輸出轉換為繁體

    Returns:
        (模型實例, 是否需要轉換為繁體)
    """
    model = ASRBackendFactory.create_backend(backend, **kwargs)

    needs_conversion = (
        backend == "qwen3asr" and convert_to_traditional and ChineseConverter.is_available()
    )

    return model, needs_conversion
