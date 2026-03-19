"""
錄音 Session 管理器

負責在每次 WebSocket 轉錄會話中：
- 建立錄音目錄結構 (data/recordings/{session_id}/)
- 累積音頻塊 (PCM/WAV)
- 會話結束時寫入原始音檔 + ASR 逐字稿
"""

import io
import json
import wave
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# 預設錄音儲存根目錄
DEFAULT_RECORDINGS_DIR = Path("data/recordings")


class RecordingSession:
    """單次錄音會話

    Attributes:
        session_id: 唯一會話 ID (UUID)
        created_at: 會話建立時間
        client_id: 客戶端 ID
        audio_bytes: 累積的音頻原始資料
        sample_rate: 音頻採樣率 (Hz)
        sample_width: 音頻樣本位元數 (bytes)
        num_channels: 音頻通道數
        transcript_chunks: 即時轉錄片段列表
        final_transcript: 最終逐字稿 (會話結束後設定)
    """

    def __init__(
        self,
        client_id: str,
        sample_rate: int = 16000,
        sample_width: int = 2,
        num_channels: int = 1,
        recordings_dir: Optional[Path] = None,
    ):
        """初始化錄音會話

        Args:
            client_id: 客戶端 ID
            sample_rate: 採樣率 (Hz)，預設 16000
            sample_width: 樣本位元數，預設 2 bytes (16-bit)
            num_channels: 通道數，預設 1 (單聲道)
            recordings_dir: 儲存目錄，預設 data/recordings
        """
        self.session_id = str(uuid.uuid4())[:8]
        self.created_at = datetime.now()
        self.client_id = client_id
        self.sample_rate = sample_rate
        self.sample_width = sample_width
        self.num_channels = num_channels
        self._recordings_dir = recordings_dir or DEFAULT_RECORDINGS_DIR

        # 音頻緩衝區
        self._audio_buffer = bytearray()

        # 即時轉錄片段（用於疊代式保存）
        self.transcript_chunks: list[dict] = []
        self.final_transcript: Optional[str] = None

        # Session 目錄
        self._session_dir: Optional[Path] = None

    @property
    def session_dir(self) -> Path:
        """取得會話目錄路徑，若尚未建立則建立"""
        if self._session_dir is None:
            timestamp = self.created_at.strftime("%Y%m%d_%H%M%S")
            self._session_dir = self._recordings_dir / f"{timestamp}_{self.session_id}"
            self._session_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"建立錄音目錄：{self._session_dir}")
        return self._session_dir

    @property
    def duration_seconds(self) -> float:
        """根據音頻資料量估算時長（秒）"""
        bytes_per_sample = self.sample_width * self.num_channels
        if bytes_per_sample == 0:
            return 0.0
        return len(self._audio_buffer) / (self.sample_rate * bytes_per_sample)

    def write_audio_chunk(self, audio_chunk: bytes) -> None:
        """寫入音頻塊

        Args:
            audio_chunk: 音頻原始資料 (bytes)
        """
        self._audio_buffer.extend(audio_chunk)

    def add_transcript_segment(self, segment: dict) -> None:
        """新增轉錄片段

        Args:
            segment: 包含 start/end/text 的字典
        """
        self.transcript_chunks.append(segment)

    def save(self, final_text: Optional[str] = None) -> dict:
        """儲存錄音檔案與逐字稿

        會寫入兩個檔案：
        - {session_id}_audio.wav — 原始音檔 (PCM 16-bit, 16kHz, mono)
        - {session_id}_transcript.json — 逐字稿 (含時間戳、分段)

        Args:
            final_text: 最終逐字稿文字（可選，預設取 self.final_transcript）

        Returns:
            包含檔案路徑的字典
        """
        text = final_text or self.final_transcript or ""
        session_path = self.session_dir

        # 1. 儲存音檔 (WAV 格式)
        audio_path = session_path / f"{self.session_id}_audio.wav"
        self._save_wav(audio_path)
        logger.info(f"音檔已儲存：{audio_path} ({len(self._audio_buffer)} bytes)")

        # 2. 儲存逐字稿 (JSON)
        transcript_data = {
            "session_id": self.session_id,
            "client_id": self.client_id,
            "created_at": self.created_at.isoformat(),
            "sample_rate": self.sample_rate,
            "num_channels": self.num_channels,
            "duration_seconds": self.duration_seconds,
            "audio_file": audio_path.name,
            "final_text": text,
            "segments": self.transcript_chunks,
        }
        transcript_path = session_path / f"{self.session_id}_transcript.json"
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_data, f, ensure_ascii=False, indent=2)
        logger.info(f"逐字稿已儲存：{transcript_path}")

        return {
            "session_id": self.session_id,
            "audio_file": str(audio_path),
            "transcript_file": str(transcript_path),
            "duration_seconds": self.duration_seconds,
        }

    def _save_wav(self, path: Path) -> None:
        """將緩衝區音頻寫入 WAV 檔

        Args:
            path: 目標檔案路徑
        """
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(self.num_channels)
            wav_file.setsampwidth(self.sample_width)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(bytes(self._audio_buffer))

    def __repr__(self) -> str:
        ts = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return (
            f"RecordingSession(id={self.session_id}, client={self.client_id}, "
            f"created={ts}, bytes={len(self._audio_buffer)})"
        )


class RecordingSessionManager:
    """錄音 Session 管理器（每個 client_id 一個 session）"""

    def __init__(self, recordings_dir: Optional[Path] = None):
        """初始化

        Args:
            recordings_dir: 儲存根目錄，預設 data/recordings
        """
        self._sessions: dict[str, RecordingSession] = {}
        self._recordings_dir = recordings_dir or DEFAULT_RECORDINGS_DIR
        # 確保根目錄存在
        self._recordings_dir.mkdir(parents=True, exist_ok=True)

    def start_session(
        self,
        client_id: str,
        sample_rate: int = 16000,
        sample_width: int = 2,
        num_channels: int = 1,
    ) -> RecordingSession:
        """開始新的錄音會話

        Args:
            client_id: 客戶端 ID
            sample_rate: 採樣率
            sample_width: 樣本位元數
            num_channels: 通道數

        Returns:
            RecordingSession 實例
        """
        # 結束舊 session（防止洩漏）
        if client_id in self._sessions:
            self.end_session(client_id, save=False)

        session = RecordingSession(
            client_id=client_id,
            sample_rate=sample_rate,
            sample_width=sample_width,
            num_channels=num_channels,
            recordings_dir=self._recordings_dir,
        )
        self._sessions[client_id] = session
        logger.info(f"錄音會話已建立：{session}")
        return session

    def get_session(self, client_id: str) -> Optional[RecordingSession]:
        """取得現有會話

        Args:
            client_id: 客戶端 ID

        Returns:
            RecordingSession 或 None
        """
        return self._sessions.get(client_id)

    def end_session(
        self,
        client_id: str,
        final_text: Optional[str] = None,
        save: bool = True,
    ) -> Optional[dict]:
        """結束錄音會話並（可選）儲存檔案

        Args:
            client_id: 客戶端 ID
            final_text: 最終逐字稿
            save: 是否立即儲存（預設 True）

        Returns:
            儲存結果 dict 或 None
        """
        session = self._sessions.pop(client_id, None)
        if session is None:
            logger.warning(f"嘗試結束不存在的錄音會話：{client_id}")
            return None

        logger.info(f"錄音會話結束：{session}")
        if save:
            session.final_transcript = final_text
            return session.save()
        return None

    def is_recording(self, client_id: str) -> bool:
        """檢查是否正在錄音

        Args:
            client_id: 客戶端 ID

        Returns:
            是否正在錄音
        """
        return client_id in self._sessions

    def list_recordings(self) -> list[Path]:
        """列出所有錄音目錄

        Returns:
            Session 目錄路徑列表（依時間排序，最新在前）
        """
        if not self._recordings_dir.exists():
            return []
        dirs = sorted(
            [p for p in self._recordings_dir.iterdir() if p.is_dir()],
            key=lambda p: p.name,
            reverse=True,
        )
        return dirs


# 全域單例
_recording_manager: Optional[RecordingSessionManager] = None


def get_recording_manager() -> RecordingSessionManager:
    """取得全域 RecordingSessionManager 單例"""
    global _recording_manager
    if _recording_manager is None:
        _recording_manager = RecordingSessionManager()
    return _recording_manager


def set_recording_manager(manager: RecordingSessionManager) -> None:
    """設定全域 RecordingSessionManager（用於測試）"""
    global _recording_manager
    _recording_manager = manager
