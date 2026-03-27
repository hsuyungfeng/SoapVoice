"""
WhisperModel: Faster-Whisper 模型封裝

提供語音轉文字功能，支援中英文自動偵測
"""

from typing import Optional
from pathlib import Path

import faster_whisper


class WhisperModel:
    """Faster-Whisper 模型封裝類

    使用 CTranslate2 優化的 Whisper 模型進行語音辨識
    支援中英文自動偵測
    """

    def __init__(
        self,
        model_id: str = "large-v3",
        device: str = "cuda",
        compute_type: str = "float16",
        download_root: Optional[str] = None,
    ):
        """初始化 Whisper 模型

        Args:
            model_id: 模型大小，可選 tiny, base, small, medium, large-v2, large-v3
            device: 設備類型，cuda 或 cpu
            compute_type: 計算精度，float16, int8, int8_float16
            download_root: 模型下載目錄
        """
        self.model_id = model_id
        self.device = device
        self.compute_type = compute_type
        self.download_root = download_root

        # 初始化 Faster-Whisper 模型
        # 支援本地模型路徑或 HuggingFace 模型 ID
        model_path = download_root if download_root else model_id
        self.model = faster_whisper.WhisperModel(
            model_size_or_path=model_path,
            device=device,
            compute_type=compute_type,
            download_root=download_root,
        )

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        vad_filter: bool = True,
    ) -> dict:
        """執行語音辨識

        Args:
            audio_path: 音頻文件路徑
            language: 語言代碼，None 為自動偵測
            task: 任務類型，transcribe 或 translate
            beam_size: Beam search 大小
            vad_filter: 是否啟用語音活動檢測

        Returns:
            包含以下鍵的字典:
            - text: 識別的文字
            - language: 偵測/指定的語言
            - segments: 分段結果列表
            - duration: 音頻時長
        """
        # 執行轉錄
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            task=task,
            beam_size=beam_size,
            vad_filter=vad_filter,
        )

        # 收集所有分段文字
        segments_list = []
        full_text_parts = []

        for segment in segments:
            segments_list.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                }
            )
            full_text_parts.append(segment.text.strip())

        # 組合完整文字
        full_text = " ".join(full_text_parts)

        return {
            "text": full_text,
            "language": info.language if info.language else language or "auto",
            "language_probability": info.language_probability,
            "segments": segments_list,
            "duration": info.duration,
        }

    def detect_language(self, audio_path: str) -> tuple[str, float]:
        """偵測音頻語言

        Args:
            audio_path: 音頻文件路徑

        Returns:
            (語言代碼, 置信度) 元組
        """
        _, info = self.model.transcribe(
            audio_path,
            language=None,
            beam_size=1,
            vad_filter=False,
        )

        return (info.language, info.language_probability)

    @property
    def available_languages(self) -> list[str]:
        """取得支援的語言列表

        Returns:
            語言代碼列表
        """
        return [
            "en",
            "zh",
            "es",
            "fr",
            "de",
            "it",
            "ja",
            "ko",
            "ru",
            "ar",
            "pt",
            "tr",
            "pl",
            "nl",
            "sv",
            "da",
            "no",
            "fi",
            "el",
            "he",
            "hi",
            "th",
            "vi",
            "id",
            "ms",
            "cs",
            "ro",
            "hu",
            "uk",
            "bg",
            "hr",
            "sk",
            "sl",
            "ca",
            "et",
            "lv",
            "lt",
            "bn",
            "ta",
            "te",
            "mr",
            "gu",
            "ml",
            "kn",
            "pa",
            "ml",
            "ne",
            "si",
            "am",
            "sw",
            "az",
            "be",
            "bs",
            "cy",
            "eo",
            "fa",
            "fy",
            "ga",
            "gd",
            "ha",
            "hy",
            "ig",
            "is",
            "ka",
            "kk",
            "km",
            "ku",
            "ky",
            "lb",
            "mg",
            "mi",
            "mk",
            "ml",
            "mn",
            "my",
            "nb",
            "nn",
            "ps",
            "sd",
            "sm",
            "sn",
            "so",
            "sq",
            "ss",
            "st",
            "su",
            "ta",
            "tg",
            "tk",
            "tl",
            "tn",
            "tt",
            "ug",
            "uz",
            "wo",
            "xh",
            "yi",
            "yo",
            "zu",
        ]

    def __repr__(self) -> str:
        return f"WhisperModel(model_id={self.model_id}, device={self.device})"
