"""
WhisperModel: Faster-Whisper 模型封裝

提供語音轉文字功能，支援中英文自動偵測
"""

import os
from typing import Optional

import faster_whisper


class WhisperModel:
    """Faster-Whisper 模型封裝類

    使用 CTranslate2 優化的 Whisper 模型進行語音辨識
    支援中英文自動偵測
    """

    def __init__(
        self,
        model_id: str = "large-v3",
        device: Optional[str] = None,
        compute_type: Optional[str] = None,
        download_root: Optional[str] = None,
    ):
        """初始化 Whisper 模型

        Args:
            model_id: 模型大小，可選 tiny, base, small, medium, large-v2, large-v3
            device: 設備類型，cuda 或 cpu（預設從環境變數 WHISPER_DEVICE 讀取，若無則為 cuda）
            compute_type: 計算精度，float16, int8, int8_float16（預設從環境變數 WHISPER_COMPUTE_TYPE 讀取，若無則為 float16）
            download_root: 模型下載目錄
        """
        # 從環境變數讀取預設值（支援 CPU fallback）
        self.device = device or os.environ.get("WHISPER_DEVICE", "cuda")
        self.compute_type = compute_type or os.environ.get("WHISPER_COMPUTE_TYPE", "float16")
        self.model_id = model_id
        self.download_root = download_root

        # 初始化 Faster-Whisper 模型
        # 支援本地模型路徑或 HuggingFace 模型 ID
        self.model = faster_whisper.WhisperModel(
            model_size_or_path=model_id,
            device=self.device,
            compute_type=self.compute_type,
            download_root=download_root,
        )

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = "zh",
        task: str = "transcribe",
        beam_size: int = 10,
        vad_filter: bool = True,
    ) -> dict:
        """執行語音辨識

        Args:
            audio_path: 音頻文件路徑
            language: 語言代碼，預設為 "zh" (繁體中文)
            task: 任務類型，transcribe 或 translate
            beam_size: Beam search 大小 (提升至 10 以增加準確度)
            vad_filter: 是否啟用語音活動檢測

        Returns:
            包含以下鍵的字典:
            - text: 識別的文字
            - language: 偵測/指定的語言
            - segments: 分段結果列表
            - duration: 音頻時長
        """
        # 執行轉錄
        # 設定繁體中文醫療對話的提示，並關閉依賴前文以減少幻覺循環
        segments, info = self.model.transcribe(
            audio_path,
            language=language,
            task=task,
            beam_size=beam_size,
            vad_filter=vad_filter,
            initial_prompt="這是一段繁體中文的醫療看診對話記錄。醫師與病患進行問診。對話內容包含：發燒、咳嗽、抽菸、心臟病、胸悶。",
            condition_on_previous_text=False,
            # 增加一些對中文友好的參數
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
        )

        # 收集所有分段文字
        segments_list = []
        full_text_parts = []
        
        # 擴大的幻覺黑名單與過濾邏輯
        hallucination_blacklist = [
            "谢谢", "謝謝", "字幕", "志愿者", "感謝", "感谢", "Watching", "Amara.org", 
            "李宗盛", "杨茜茜", "楊茜茜", "訂閱", "订阅", "剧场", "劇場", "MING PAO", 
            "CANADA", "TORONTO", "明報", "多倫多", "Zhang", "Today", "Kyi-day", 
            "killed", "Sysh", "recently", "you're-must", "fashow", "chou yin", "chowl",
            "jank", "tureen", "tut-tut", "hush-x", "gawonged"
        ]

        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
                
            # 檢查是否為重複的標點符號幻覺 (如 ". . . . .")
            import re
            if re.match(r'^[\.\s。，,！？!\?\-]+$', text):
                continue
                
            # 檢查是否包含黑名單中的片段
            is_hallucination = False
            for black_word in hallucination_blacklist:
                if black_word.lower() in text.lower():
                    is_hallucination = True
                    break
                    
            if is_hallucination:
                continue

            segments_list.append(
                {
                    "start": segment.start,
                    "end": segment.end,
                    "text": text,
                }
            )
            full_text_parts.append(text)

        # 組合完整文字
        # 對於中文，不使用空格連接
        detected_language = info.language if info.language else language or "auto"
        if detected_language in ["zh", "ja"]:
            full_text = "".join(full_text_parts)
        else:
            full_text = " ".join(full_text_parts)

        return {
            "text": full_text,
            "language": detected_language,
            "language_probability": info.language_probability,
            "segments": segments_list,
            "duration": info.duration,
        }

    def detect_language(self, audio_path: str) -> tuple[str, float]:
        """偵測音頻語言

        Args:
            audio_path: 音頻文件路徑

        Returns:
            (語言代碼，置信度) 元組
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
        return f"WhisperModel(model_id={self.model_id}, device={self.device}, compute_type={self.compute_type})"
