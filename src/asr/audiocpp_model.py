"""
AudioCppModel: audio.cpp 伺服器模型封裝

透過 HTTP 請求呼叫本地的 audiocpp_server，提供更快的 CPU 離線推論效能。
"""

import os
import requests
from typing import Optional

from src.asr.utils import filter_hallucinations


class AudioCppModel:
    """audio.cpp 模型封裝類

    透過 HTTP 與常駐的 audiocpp_server 溝通，
    將語音檔案傳送至伺服器進行辨識，並套用幻覺過濾邏輯。
    """

    def __init__(self, server_url: Optional[str] = None):
        """初始化 AudioCpp 模型

        Args:
            server_url: audiocpp_server 的 API 端點。
                        若未提供，則優先讀取環境變數 AUDIOCPP_SERVER_URL，
                        預設值為 "http://127.0.0.1:8080/inference"。
        """
        self.server_url = server_url or os.environ.get(
            "AUDIOCPP_SERVER_URL", "http://127.0.0.1:8080/inference"
        )

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = "zh",
        **kwargs,
    ) -> dict:
        """執行語音辨識

        透過 HTTP POST 請求將音檔送至 audiocpp_server 進行推論，
        並對回傳的文字結果套用幻覺黑名單過濾。

        Args:
            audio_path: 音頻文件路徑
            language: 語言代碼，預設為 "zh" (繁體中文)
            **kwargs: 其他參數（將作為表單資料傳送）

        Returns:
            包含以下鍵的字典:
            - text: 識別並過濾後的文字
            - language: 語言代碼
            - segments: 分段結果列表
            - duration: 音頻時長 (目前預設為 0.0)
        """
        # 準備請求參數
        data = {"language": language}
        # 將 kwargs 參數加入表單
        for key, value in kwargs.items():
            if value is not None:
                data[key] = str(value)

        # 讀取音檔並發送請求
        with open(audio_path, "rb") as f:
            files = {"file": (os.path.basename(audio_path), f)}
            try:
                response = requests.post(self.server_url, data=data, files=files, timeout=300)
                response.raise_for_status()
                result = response.json()
            except Exception as e:
                raise RuntimeError(f"呼叫 audiocpp_server 失敗: {e}")

        # 解析伺服器回傳的分段
        segments = result.get("segments", [])
        raw_text = result.get("text", "")

        # 如果沒有分段但有文字，自己造一個分段來過濾
        if not segments and raw_text:
            segments = [{"text": raw_text}]

        # 過濾分段中的幻覺字詞
        filtered_segments = []
        for segment in segments:
            seg_text = segment.get("text", "")
            cleaned = filter_hallucinations(seg_text)
            if cleaned:
                segment["text"] = cleaned
                filtered_segments.append(segment)

        # 重建完整文字
        filtered_text = "".join(seg.get("text", "") for seg in filtered_segments)

        return {
            "text": filtered_text,
            "language": language or "zh",
            "segments": filtered_segments,
            "duration": result.get("duration", 0.0),
        }

    def detect_language(self, audio_path: str) -> tuple[str, float]:
        """偵測音頻語言

        Args:
            audio_path: 音頻文件路徑

        Returns:
            (語言代碼，置信度) 元組
        """
        # 預設直接回傳 zh，因為 audiocpp_server 可能未提供此端點
        return ("zh", 1.0)

    @property
    def available_languages(self) -> list[str]:
        """取得支援的語言列表

        Returns:
            語言代碼列表
        """
        return ["zh", "en", "ja", "ko"]

    def __repr__(self) -> str:
        return f"AudioCppModel(server_url={self.server_url})"
