"""語音錄製模組（PyAudio）

職責：
- 開始/停止錄音（背景線程）
- 自動保存 16 kHz 單聲道 WAV 至指定目錄
- 透過 callback 通知 GUI（on_start/on_stop/on_error）

WAV 格式選擇：16 kHz mono 16-bit PCM —
- Whisper / Funasr 最佳採樣率
- 醫療對話無需立體聲
- 約 32 KB/s，便於 LAN 傳輸（Server 端會再壓 Opus 32 kbps）

使用：
    >>> rec = AudioRecorder("./cache")
    >>> rec.start()
    >>> # ... 錄音中
    >>> path = rec.stop()  # 回傳 .wav 路徑
"""

from __future__ import annotations

import logging
import threading
import uuid
import wave
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

try:
    import pyaudio  # type: ignore
except ImportError:  # 測試/開發環境可能無 PyAudio
    pyaudio = None  # type: ignore

logger = logging.getLogger(__name__)


class AudioRecorder:
    """以 PyAudio 錄製 16 kHz 單聲道 WAV。

    Threading：錄製在背景 daemon thread；start() 立即返回，stop() 會 join 並寫檔。

    Callbacks（同步函式）：
        on_start: 開始錄製時呼叫
        on_stop(path: str): 停止並保存後呼叫
        on_error(message: str): 錯誤時呼叫
    """

    CHUNK = 1024
    CHANNELS = 1  # mono
    RATE = 16000  # Whisper 最佳

    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.is_recording = False
        self.audio_frames: list[bytes] = []
        self.stream = None
        self.audio = None
        self.thread: Optional[threading.Thread] = None
        self._sample_size = 2  # 16-bit PCM 預設

        self.on_start: Optional[Callable[[], None]] = None
        self.on_stop: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None

    @property
    def _format(self):
        """PyAudio 格式（16-bit PCM）。延遲取值便於測試 mock。"""
        if pyaudio is None:
            raise RuntimeError("PyAudio not available")
        return pyaudio.paInt16

    def start(self) -> bool:
        """開始錄製（非阻塞）。

        Returns:
            True 啟動成功，False 已在錄製或無 PyAudio。
        """
        if self.is_recording:
            logger.warning("Already recording, ignoring start()")
            return False

        if pyaudio is None:
            msg = "PyAudio not installed; recording unavailable"
            logger.error(msg)
            if self.on_error:
                self.on_error(msg)
            return False

        try:
            self.audio_frames = []
            self.audio = pyaudio.PyAudio()
            self._sample_size = self.audio.get_sample_size(self._format)
            self.stream = self.audio.open(
                format=self._format,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
            )
            self.is_recording = True
            self.thread = threading.Thread(target=self._record_loop, daemon=True)
            self.thread.start()

            logger.info("Recording started @ %d Hz mono", self.RATE)
            if self.on_start:
                try:
                    self.on_start()
                except Exception:  # noqa: BLE001
                    logger.exception("on_start callback raised")
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to start recording: %s", exc)
            self.is_recording = False
            if self.on_error:
                self.on_error(str(exc))
            return False

    def _record_loop(self) -> None:
        """背景錄製迴圈。"""
        try:
            while self.is_recording:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                self.audio_frames.append(data)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Recording loop error: %s", exc)
            if self.on_error:
                self.on_error(str(exc))

    def stop(self) -> Optional[str]:
        """停止錄製並保存 WAV。

        Returns:
            WAV 檔案完整路徑，未錄製或失敗時為 None。
        """
        if not self.is_recording:
            logger.warning("Not currently recording")
            return None

        # 中止迴圈
        self.is_recording = False

        # 等待背景線程結束
        if self.thread is not None:
            self.thread.join(timeout=2.0)
            self.thread = None

        try:
            if self.stream is not None:
                try:
                    self.stream.stop_stream()
                except Exception:  # noqa: BLE001
                    pass
                try:
                    self.stream.close()
                except Exception:  # noqa: BLE001
                    pass
                self.stream = None
            if self.audio is not None:
                try:
                    self.audio.terminate()
                except Exception:  # noqa: BLE001
                    pass

            # 生成檔名 YYYYMMDD_HHMMSS_<8hex>.wav
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            session_id = uuid.uuid4().hex[:8]
            filename = f"audio_{timestamp}_{session_id}.wav"
            filepath = self.output_dir / filename

            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(self.CHANNELS)
                wav_file.setsampwidth(self._sample_size)
                wav_file.setframerate(self.RATE)
                wav_file.writeframes(b"".join(self.audio_frames))

            logger.info("Recording saved: %s (%d frames)", filepath, len(self.audio_frames))
            self.audio_frames = []
            self.audio = None

            if self.on_stop:
                try:
                    self.on_stop(str(filepath))
                except Exception:  # noqa: BLE001
                    logger.exception("on_stop callback raised")

            return str(filepath)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Save error: %s", exc)
            if self.on_error:
                self.on_error(str(exc))
            return None
