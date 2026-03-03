"""
StreamTranscriber: 即時語音串流轉文字處理器

使用 Faster-Whisper 實現即時語音辨識
支援 chunked 處理模式，即時回傳辨識結果
"""

import io
import numpy as np
from typing import Optional
from collections import deque

import faster_whisper
from faster_whisper import WhisperModel


class StreamTranscriber:
    """即時語音串流轉文字處理器

    使用 Faster-Whisper 的 streaming 模式支援即時語音辨識
    適用於 WebSocket 即時音頻串流處理

    Attributes:
        model: Faster-Whisper 模型實例
        language: 語言設定，None 為自動偵測
        task: 任務類型，transcribe 或 translate
        beam_size: Beam search 大小
    """

    def __init__(
        self,
        whisper_model: Optional[WhisperModel] = None,
        language: Optional[str] = None,
        task: str = "transcribe",
        beam_size: int = 5,
        chunk_size: int = 1024,
    ):
        """初始化串流辨識器

        Args:
            whisper_model: WhisperModel 實例（可為 None，延遲載入）
            language: 語言代碼，None 為自動偵測
            task: 任務類型
            beam_size: Beam search 大小
            chunk_size: 音頻塊大小
        """
        self._model_instance = whisper_model
        self.model = whisper_model.model if whisper_model else None
        self.language = language
        self.task = task
        self.beam_size = beam_size
        self.chunk_size = chunk_size

        # 串流狀態
        self._is_streaming = False
        self._audio_buffer = io.BytesIO()
        self._segments_buffer = deque()
        self._current_text = ""
        self._total_duration = 0.0

        # 用於即時處理的變數
        self._temp_file = None
        self._last_result = ""

    def load_model(self, whisper_model: WhisperModel) -> None:
        """載入 Whisper 模型

        Args:
            whisper_model: WhisperModel 實例
        """
        self._model_instance = whisper_model
        self.model = whisper_model.model
        print(f"✓ Whisper 模型已載入：{whisper_model.model_id}")
        print(f"  model 屬性：{self.model}")
        print(f"  _model_instance: {self._model_instance}")

    def start_stream(self) -> dict:
        """開始新的串流識別會話

        Returns:
            包含會話資訊的字典
        """
        # 檢查模型是否已載入
        if self.model is None:
            raise RuntimeError("Whisper 模型未載入，請先呼叫 load_model()")

        if self._is_streaming:
            raise RuntimeError("串流會話已在進行中，請先結束當前會話")

        # 重置狀態
        self._audio_buffer = io.BytesIO()
        self._segments_buffer.clear()
        self._current_text = ""
        self._total_duration = 0.0
        self._last_result = ""

        # 創建臨時文件用於流式處理
        self._temp_file = io.BytesIO()

        self._is_streaming = True

        return {
            "status": "stream_started",
            "message": "串流識別會話已開始",
            "language": self.language or "auto",
        }

    def process_chunk(self, audio_chunk: bytes) -> dict:
        """處理音頻塊並即時返回辨識結果

        Args:
            audio_chunk: 音頻數據 (bytes)

        Returns:
            包含即時辨識結果的字典
        """
        if not self._is_streaming:
            raise RuntimeError("串流會話未開始，請先調用 start_stream()")

        # 將音頻塊寫入緩衝區
        self._audio_buffer.write(audio_chunk)

        # 獲取當前音頻數據
        audio_data = self._audio_buffer.getvalue()

        if len(audio_data) < self.chunk_size * 2:
            # 數據量不足，跳過處理
            return {
                "status": "insufficient_data",
                "text": self._current_text,
                "is_final": False,
            }

        try:
            # 將 bytes 轉換為 numpy array
            audio_array = self._bytes_to_audio_array(audio_data)

            if audio_array is None or len(audio_array) == 0:
                return {
                    "status": "no_audio",
                    "text": self._current_text,
                    "is_final": False,
                }

            # 執行即時轉錄
            segments, info = self.model.transcribe(
                audio_array,
                language=self.language,
                task=self.task,
                beam_size=self.beam_size,
                vad_filter=False,  # 流式處理時關閉 VAD
            )

            # 收集分段結果
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
                self._segments_buffer.append(
                    {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text.strip(),
                    }
                )

            # 更新當前文字
            if text_parts:
                self._current_text = " ".join(text_parts)
                self._last_result = self._current_text

            # 更新總時長
            if info.duration:
                self._total_duration = info.duration

            return {
                "status": "interim",
                "text": self._current_text,
                "language": info.language or self.language or "auto",
                "duration": self._total_duration,
                "is_final": False,
            }

        except Exception as e:
            return {
                "status": "error",
                "text": self._current_text,
                "error": str(e),
                "is_final": False,
            }

    def end_stream(self) -> dict:
        """結束串流會話並返回最終結果

        Returns:
            包含最終辨識結果的字典
        """
        if not self._is_streaming:
            raise RuntimeError("串流會話未開始")

        self._is_streaming = False

        # 獲取最終音頻數據
        audio_data = self._audio_buffer.getvalue()

        if len(audio_data) < self.chunk_size:
            return {
                "status": "stream_ended",
                "text": self._current_text,
                "segments": list(self._segments_buffer),
                "duration": self._total_duration,
                "is_final": True,
            }

        try:
            # 執行最終轉錄
            audio_array = self._bytes_to_audio_array(audio_data)

            if audio_array is not None and len(audio_array) > 0:
                segments, info = self.model.transcribe(
                    audio_array,
                    language=self.language,
                    task=self.task,
                    beam_size=self.beam_size,
                    vad_filter=True,  # 最終結果啟用 VAD
                )

                final_text_parts = []
                final_segments = []

                for segment in segments:
                    text = segment.text.strip()
                    final_text_parts.append(text)
                    final_segments.append(
                        {
                            "start": segment.start,
                            "end": segment.end,
                            "text": text,
                        }
                    )

                final_text = " ".join(final_text_parts)

                # 更新總時長
                if info.duration:
                    self._total_duration = info.duration

                return {
                    "status": "stream_ended",
                    "text": final_text,
                    "segments": final_segments,
                    "language": info.language or self.language or "auto",
                    "duration": self._total_duration,
                    "is_final": True,
                }

        except Exception as e:
            return {
                "status": "stream_ended_with_error",
                "text": self._current_text,
                "segments": list(self._segments_buffer),
                "duration": self._total_duration,
                "error": str(e),
                "is_final": True,
            }

        # 清理資源
        self._cleanup()

        return {
            "status": "stream_ended",
            "text": self._current_text,
            "segments": list(self._segments_buffer),
            "duration": self._total_duration,
            "is_final": True,
        }

    def _bytes_to_audio_array(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """將音頻 bytes 轉換為 numpy array

        Args:
            audio_bytes: 音頻數據

        Returns:
            numpy array 或 None
        """
        try:
            # 嘗試解析為 WAV 格式
            import wave

            # 將 bytes 包裝為 BytesIO
            audio_io = io.BytesIO(audio_bytes)

            try:
                with wave.open(audio_io, "rb") as wav:
                    # 讀取 WAV 数据
                    frames = wav.readframes(wav.getnframes())
                    # 轉換為 numpy array (假設 16-bit PCM)
                    audio_array = np.frombuffer(frames, dtype=np.int16)
                    # 轉換為 float32 (-1 到 1)
                    audio_array = audio_array.astype(np.float32) / 32768.0
                    return audio_array
            except:
                # 如果不是 WAV 格式，嘗試作為原始 PCM 處理
                audio_array = np.frombuffer(audio_bytes, dtype=np.int16)
                audio_array = audio_array.astype(np.float32) / 32768.0
                return audio_array

        except Exception:
            return None

    def _cleanup(self) -> None:
        """清理資源"""
        if self._temp_file:
            try:
                self._temp_file.close()
            except:
                pass
            self._temp_file = None

        self._audio_buffer = io.BytesIO()

    @property
    def is_streaming(self) -> bool:
        """檢查是否正在串流"""
        return self._is_streaming

    def __repr__(self) -> str:
        return f"StreamTranscriber(language={self.language}, task={self.task}, streaming={self._is_streaming})"
