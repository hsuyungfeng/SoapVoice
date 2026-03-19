"""
測試錄音 Session 管理模組
"""

import json
import wave
import tempfile
from pathlib import Path

import pytest

from src.asr.recording_session import (
    RecordingSession,
    RecordingSessionManager,
    get_recording_manager,
    set_recording_manager,
)


class TestRecordingSession:
    """測試 RecordingSession 單次會話"""

    @pytest.fixture
    def temp_dir(self):
        """建立臨時錄音目錄"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def session(self, temp_dir):
        """建立測試用 RecordingSession"""
        return RecordingSession(
            client_id="test_client_001",
            sample_rate=16000,
            sample_width=2,
            num_channels=1,
            recordings_dir=temp_dir,
        )

    def test_init(self, session, temp_dir):
        """測試初始化參數"""
        assert session.client_id == "test_client_001"
        assert session.sample_rate == 16000
        assert session.sample_width == 2
        assert session.num_channels == 1
        assert len(session._audio_buffer) == 0
        assert session.final_transcript is None

    def test_session_id_unique(self, temp_dir):
        """測試每次 session_id 唯一"""
        s1 = RecordingSession("client_a", recordings_dir=temp_dir)
        s2 = RecordingSession("client_a", recordings_dir=temp_dir)
        assert s1.session_id != s2.session_id

    def test_session_dir_creation(self, session, temp_dir):
        """測試會話目錄自動建立"""
        path = session.session_dir
        assert path.exists()
        assert path.is_dir()
        assert session.session_id in path.name
        assert temp_dir in path.parents

    def test_write_audio_chunk(self, session):
        """測試音頻塊寫入"""
        fake_audio = b"\x00\x01\x02\x03" * 100  # 400 bytes PCM
        session.write_audio_chunk(fake_audio)
        assert len(session._audio_buffer) == 400

    def test_add_transcript_segment(self, session):
        """測試轉錄片段新增"""
        session.add_transcript_segment({"start": 0.0, "end": 1.5, "text": "胸悶兩天"})
        session.add_transcript_segment({"start": 1.5, "end": 3.0, "text": "呼吸困難"})
        assert len(session.transcript_chunks) == 2
        assert session.transcript_chunks[0]["text"] == "胸悶兩天"

    def test_save_wav_file(self, session, temp_dir):
        """測試 WAV 檔案儲存"""
        # 寫入 1 秒的静音音頻 (16000 Hz, 16-bit, mono)
        silence = b"\x00\x00" * 16000
        session.write_audio_chunk(silence)

        audio_path = session.session_dir / f"{session.session_id}_audio.wav"
        session._save_wav(audio_path)

        assert audio_path.exists()
        # 驗證 WAV 格式
        with wave.open(str(audio_path), "rb") as wav:
            assert wav.getnchannels() == 1
            assert wav.getsampwidth() == 2
            assert wav.getframerate() == 16000
            # 1 秒音頻 = 16000 frames × 2 bytes = 32000 bytes
            assert wav.getnframes() == 16000

    def test_save_full_session(self, session):
        """測試完整 session 儲存（音檔 + JSON）"""
        # 寫入測試音頻
        audio = b"\x00\x01" * 8000  # 0.5 秒
        session.write_audio_chunk(audio)

        # 設定逐字稿
        session.final_transcript = "病患胸悶兩天"
        session.add_transcript_segment({"start": 0.0, "end": 1.0, "text": "病患胸悶兩天"})

        result = session.save()

        assert "session_id" in result
        assert "audio_file" in result
        assert "transcript_file" in result
        assert Path(result["audio_file"]).exists()
        assert Path(result["transcript_file"]).exists()

        # 驗證 JSON 內容
        with open(result["transcript_file"], encoding="utf-8") as f:
            data = json.load(f)
        assert data["session_id"] == session.session_id
        assert data["client_id"] == "test_client_001"
        assert data["final_text"] == "病患胸悶兩天"
        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "病患胸悶兩天"

    def test_duration_seconds(self, session):
        """測試時長估算"""
        # 0.5 秒音頻 (16000 Hz × 0.5s × 2 bytes = 16000 bytes)
        audio = b"\x00\x00" * 8000
        session.write_audio_chunk(audio)
        assert abs(session.duration_seconds - 0.5) < 0.01


class TestRecordingSessionManager:
    """測試 RecordingSessionManager 管理器"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mgr(self, temp_dir):
        """建立測試用 Manager"""
        return RecordingSessionManager(recordings_dir=temp_dir)

    def test_start_session(self, mgr):
        """測試開始會話"""
        session = mgr.start_session("client_abc")
        assert session.client_id == "client_abc"
        assert mgr.is_recording("client_abc")
        assert mgr.get_session("client_abc") == session

    def test_start_session_cleans_old(self, mgr):
        """測試開始新會話時自動清理舊的"""
        s1 = mgr.start_session("client_x")
        assert mgr.is_recording("client_x")
        s2 = mgr.start_session("client_x")  # 同一 client，舊的應被清理
        assert s2.session_id != s1.session_id
        assert mgr.is_recording("client_x")

    def test_end_session_save(self, mgr):
        """測試結束並儲存"""
        mgr.start_session("client_y")
        mgr.get_session("client_y").write_audio_chunk(b"\x00\x01" * 1000)

        result = mgr.end_session("client_y", final_text="測試逐字稿")
        assert result is not None
        assert "audio_file" in result
        assert "transcript_file" in result
        assert not mgr.is_recording("client_y")

    def test_end_session_without_save(self, mgr):
        """測試結束但不儲存"""
        mgr.start_session("client_z")
        mgr.get_session("client_z").write_audio_chunk(b"\x00\x01" * 1000)
        result = mgr.end_session("client_z", save=False)
        assert result is None
        assert not mgr.is_recording("client_z")

    def test_end_nonexistent_session(self, mgr):
        """測試結束不存在的 session"""
        result = mgr.end_session("nonexistent_client")
        assert result is None

    def test_list_recordings(self, mgr, temp_dir):
        """測試列出錄音目錄"""
        # 建立兩個 session
        s1 = mgr.start_session("client_1")
        mgr.get_session("client_1").write_audio_chunk(b"\x00")
        mgr.end_session("client_1")

        s2 = mgr.start_session("client_2")
        mgr.get_session("client_2").write_audio_chunk(b"\x00")
        mgr.end_session("client_2")

        dirs = mgr.list_recordings()
        assert len(dirs) == 2
        # 最新在前
        assert dirs[0].name.startswith("20")  # timestamp prefix


class TestRecordingIntegration:
    """整合測試：驗證完整錄音流程"""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_full_recording_flow(self, temp_dir):
        """模擬完整 WebSocket 錄音流程"""
        mgr = RecordingSessionManager(recordings_dir=temp_dir)

        # 模擬 start
        session = mgr.start_session("patient_001")

        # 模擬多個 chunk（相當於 0.5 秒音頻 × 2）
        # 0.5s @ 16kHz @ 16-bit = 16000 bytes per chunk
        chunk1 = b"\x00\x01" * 8000  # 0.5 秒
        chunk2 = b"\x02\x03" * 8000  # 0.5 秒
        session.write_audio_chunk(chunk1)
        session.write_audio_chunk(chunk2)

        # 模擬即時轉錄片段
        session.add_transcript_segment({"start": 0.0, "end": 0.5, "text": "病患主訴胸悶"})
        session.add_transcript_segment({"start": 0.5, "end": 1.0, "text": "伴隨呼吸困難"})

        # 模擬 end
        result = mgr.end_session("patient_001", final_text="病患主訴胸悶伴隨呼吸困難")

        # 驗證
        assert result is not None
        audio_path = Path(result["audio_file"])
        transcript_path = Path(result["transcript_file"])

        assert audio_path.exists()
        assert transcript_path.exists()
        assert abs(result["duration_seconds"] - 1.0) < 0.1

        with open(transcript_path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["final_text"] == "病患主訴胸悶伴隨呼吸困難"
        assert len(data["segments"]) == 2
