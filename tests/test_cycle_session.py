"""Tests for CycleSession (Phase 31 Plan 31-15 Task 1)."""

import os
from pathlib import Path
import time
import pytest

from client.audio_recorder import AudioRecorder
from client.cycle_session import CycleSession, CycleSessionError
from client.segment_store import SegmentStore


class FakeAudioStream:
    """可控制的假音訊串流。"""

    def __init__(self, frame_chunk_size: int = 1024):
        self.frame_chunk_size = frame_chunk_size
        self.is_stopped = False
        self.is_closed = False
        self.read_count = 0

    def read(self, n: int, exception_on_overflow: bool = False) -> bytes:
        if self.is_stopped or self.is_closed:
            return b""
        self.read_count += 1
        time.sleep(0.005)
        return bytes([self.read_count % 256, 0]) * n

    def stop_stream(self) -> None:
        self.is_stopped = True

    def close(self) -> None:
        self.is_closed = True


class FakeUploader:
    def __init__(self):
        self.notified_cycles: list[str] = []

    def notify(self, cycle_id: str) -> None:
        self.notified_cycles.append(cycle_id)


def test_session_start_and_status(tmp_path):
    """Test session_1: start(cmd1, c1) -> RECORDING, recorder.start_cycle called,
    capture_patient called once and set_context; status.patient_bound is True;
    status dict does NOT contain patient_name or any PHI.
    """
    cycles_dir = tmp_path / "cycles"
    store = SegmentStore(cycles_dir)
    stream = FakeAudioStream()
    recorder = AudioRecorder(str(tmp_path), frames_per_segment=4096, stream_factory=lambda: stream)

    capture_calls = []

    def mock_capture():
        capture_calls.append(1)
        return {
            "patient_name": "王大明",
            "doctor_name": "李醫師",
            "screenshot_path": str(tmp_path / "screen.png"),
            "case_id": "case-123",
        }

    session = CycleSession(
        recorder=recorder,
        store=store,
        uploader=FakeUploader(),
        capture_patient=mock_capture,
    )

    cmd1 = "a" * 32
    c1 = "1" * 32
    res = session.start(cmd1, c1)
    assert res["state"] == "RECORDING"
    assert res["cycle_id"] == c1
    assert recorder.is_recording is True
    assert len(capture_calls) == 1

    # 驗證 context 已儲存於 store
    ctx = store.get_context(c1)
    assert ctx["patient_name"] == "王大明"

    # 驗證 status 脫敏與欄位
    st = session.status()
    assert st["state"] == "RECORDING"
    assert st["cycle_id"] == c1
    assert st["patient_bound"] is True
    # 絕不包含病人 PHI
    assert "patient_name" not in st
    assert "doctor_name" not in st
    assert "case_id" not in st
    assert "screenshot_path" not in st

    recorder.stop()


def test_session_start_busy_and_idempotent(tmp_path):
    """Test session_2: 錄音中 start(cmd2, c2) -> 409 busy, recorder 未被重設；
    start(cmd1, c1) 重送 -> 200 相同結果。
    """
    cycles_dir = tmp_path / "cycles"
    store = SegmentStore(cycles_dir)
    stream = FakeAudioStream()
    recorder = AudioRecorder(str(tmp_path), frames_per_segment=4096, stream_factory=lambda: stream)

    session = CycleSession(recorder=recorder, store=store)

    cmd1 = "a" * 32
    c1 = "1" * 32
    res1 = session.start(cmd1, c1)
    assert res1["state"] == "RECORDING"

    # 重送同一命令 -> 200
    res1_replay = session.start(cmd1, c1)
    assert res1_replay["state"] == "RECORDING"
    assert res1_replay["cycle_id"] == c1

    # 錄音中以不同 cycle_id 開始 -> 409 busy
    cmd2 = "b" * 32
    c2 = "2" * 32
    with pytest.raises(CycleSessionError) as exc_info:
        session.start(cmd2, c2)
    assert exc_info.value.status == 409
    assert exc_info.value.error == "busy"

    # 確認錄音未被重設或中斷
    assert recorder.is_recording is True
    assert session._active_cycle_id == c1

    recorder.stop()


def test_session_stop(tmp_path):
    """Test session_3: stop(cmd3, c1) -> set_total、uploader.notify, state 變 UPLOADING;
    stop 以錯誤 cycle_id -> 409 cycle_mismatch; 未錄音且非重送 -> 409 not_recording.
    """
    cycles_dir = tmp_path / "cycles"
    store = SegmentStore(cycles_dir)
    stream = FakeAudioStream()
    recorder = AudioRecorder(str(tmp_path), frames_per_segment=4096, stream_factory=lambda: stream)
    uploader = FakeUploader()

    session = CycleSession(recorder=recorder, store=store, uploader=uploader)

    cmd1 = "a" * 32
    c1 = "1" * 32
    session.start(cmd1, c1)

    # 以錯誤 cycle_id 停止 -> 409 cycle_mismatch
    wrong_c = "9" * 32
    cmd_err = "e" * 32
    with pytest.raises(CycleSessionError) as exc_info:
        session.stop(cmd_err, wrong_c)
    assert exc_info.value.status == 409
    assert exc_info.value.error == "cycle_mismatch"

    # 正常停止
    cmd_stop = "b" * 32
    res_stop = session.stop(cmd_stop, c1)
    assert res_stop["state"] == "UPLOADING"
    assert recorder.is_recording is False
    assert c1 in uploader.notified_cycles

    manifest = store.load(c1)
    assert manifest.total_chunks is not None

    # 重送同一 stop 指令 -> 200
    res_stop_replay = session.stop(cmd_stop, c1)
    assert res_stop_replay["state"] == "UPLOADING"

    # 未錄音且無相應循環 -> 409 not_recording
    cmd_unused = "f" * 32
    c_unused = "8" * 32
    with pytest.raises(CycleSessionError) as exc_info:
        session.stop(cmd_unused, c_unused)
    assert exc_info.value.status == 409
    assert exc_info.value.error == "not_recording"


def test_session_archived(tmp_path):
    """Test session_4: archived(c1): server_check 回 ARCHIVED -> mark_archived 且呼叫 cleanup,
    回 cleanup_eligible; 回 RECORDING 或 None -> 不標記，回 409 / 503.
    """
    cycles_dir = tmp_path / "cycles"
    store = SegmentStore(cycles_dir)
    recorder = AudioRecorder(str(tmp_path))

    c1 = "1" * 32
    c2 = "2" * 32
    c_none = "3" * 32

    server_status = {c1: "ARCHIVED", c2: "RECORDING"}
    cleaned = []

    def mock_server_check(cid: str):
        return server_status.get(cid)

    def mock_cleanup():
        cleaned.append(1)

    session = CycleSession(
        recorder=recorder,
        store=store,
        server_check=mock_server_check,
        cleanup=mock_cleanup,
    )

    store.open_cycle(c1)
    store.open_cycle(c2)
    store.open_cycle(c_none)

    # 1. 伺服器已封存 -> 標記本機並執行 cleanup
    res = session.archived(c1)
    assert res["cleanup_eligible"] is True
    manifest1 = store.load(c1)
    assert manifest1.archived is True
    assert len(cleaned) == 1

    # 2. 伺服器未封存 (RECORDING) -> 409 not_archived_on_server，本機不標記
    with pytest.raises(CycleSessionError) as exc_info:
        session.archived(c2)
    assert exc_info.value.status == 409
    assert exc_info.value.error == "not_archived_on_server"
    manifest2 = store.load(c2)
    assert manifest2.archived is False

    # 3. 伺服器無法連線 (None) -> 503 server_unavailable
    with pytest.raises(CycleSessionError) as exc_info:
        session.archived(c_none)
    assert exc_info.value.status == 503
    assert exc_info.value.error == "server_unavailable"


def test_session_recover_on_startup_and_abandoned(tmp_path):
    """Test session_5: 模擬重啟：manifest 有未 stop 的循環與 .pcm.part ->
    啟動時 recover_partial、狀態 ERROR recording_interrupted;
    server_check 回 ABANDONED 後 -> IDLE 且可 start 新循環；該循環檔案仍保留 (D-31-33).
    """
    cycles_dir = tmp_path / "cycles"
    store = SegmentStore(cycles_dir)
    recorder = AudioRecorder(str(tmp_path))

    c1 = "1" * 32
    c_dir = store.open_cycle(c1)

    # 模擬寫入一半未正常停止的 .pcm.part
    part_file = c_dir / "chunk_000000.pcm.part"
    part_file.write_bytes(b"\x00\x00" * 1000)

    server_status = {c1: "RECORDING"}

    session = CycleSession(
        recorder=recorder,
        store=store,
        server_check=lambda cid: server_status.get(cid),
    )

    # 執行重啟恢復
    session.recover_on_startup()

    # 驗證 recover_partial 已把 .pcm.part 轉為 .wav
    assert not part_file.exists()
    assert (c_dir / "chunk_000000.wav").is_file()

    # 狀態應為 ERROR recording_interrupted
    st = session.status()
    assert st["state"] == "ERROR"
    assert st["last_error"] == "recording_interrupted"

    # 模擬伺服器端標記放棄 ABANDONED，背景輪詢推進
    server_status[c1] = "ABANDONED"
    session.advance_unfinished()

    # 本機標記封存，狀態恢復為 IDLE
    st_after = session.status()
    assert st_after["state"] == "IDLE"

    # 循環目錄與音檔仍然保留，零刪除 (D-31-33)
    assert (c_dir / "chunk_000000.wav").is_file()
