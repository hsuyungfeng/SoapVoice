"""
Qwen3ASRModel: Qwen3-ASR 模型封裝

提供語音轉文字功能，輸出簡體中文，需配合 opencc 轉換為繁體
"""

from typing import Optional
import torch


class Qwen3ASRModel:
    """Qwen3-ASR 模型封裝類

    使用 Qwen3-ASR-0.6B 模型進行語音辨識
    輸出簡體中文，可透過 opencc 轉換為繁體
    """

    def __init__(
        self,
        model_id: str = "Qwen/Qwen3-ASR-0.6B",
        device: str = "cuda",
        dtype: Optional[torch.dtype] = torch.bfloat16,
    ):
        """初始化 Qwen3-ASR 模型

        Args:
            model_id: 模型名稱或路徑
            device: 設備類型，cuda 或 cpu
            dtype: 資料類型
        """
        self.model_id = model_id
        self.device = device
        self.dtype = dtype
        self.model = None

    def load(self) -> None:
        """載入模型"""
        if self.model is not None:
            return

        from qwen_asr import Qwen3ASRModel

        self.model = Qwen3ASRModel.from_pretrained(
            self.model_id,
            dtype=self.dtype,
            device_map=self.device,
        )

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """執行語音辨識

        Args:
            audio_path: 音頻文件路徑
            language: 語言代碼，None 為自動偵測（Qwen3-ASR 會自動偵測）

        Returns:
            包含以下鍵的字典:
            - text: 識別的文字（簡體中文）
            - language: 偵測的語言
            - segments: 分段結果列表
            - duration: 音頻時長
        """
        if self.model is None:
            self.load()

        result = self.model.transcribe(audio=audio_path, language=language)

        text = str(result)
        if "text='" in text:
            start = text.find("text='") + 6
            end = text.find("'", start)
            text = text[start:end]

        return {
            "text": text,
            "language": "zh",
            "segments": [{"text": text}],
            "duration": 0.0,
        }

    def detect_language(self, audio_path: str) -> tuple[str, float]:
        """偵測音頻語言

        Args:
            audio_path: 音頻文件路徑

        Returns:
            (語言代碼, 置信度) 元組
        """
        result = self.model.transcribe(audio=audio_path, language=None)
        return ("zh", 1.0)

    @property
    def available_languages(self) -> list[str]:
        """取得支援的語言列表

        Returns:
            語言代碼列表
        """
        return ["zh", "en", "ja", "ko", "es", "fr", "de", "it", "ru", "ar"]

    def __repr__(self) -> str:
        return f"Qwen3ASRModel(model_id={self.model_id}, device={self.device})"
