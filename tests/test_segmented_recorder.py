"""Tests for segmented streaming AudioRecorder (Phase 31 Plan 31-07)."""

import os
from pathlib import Path
import time
import wave
import pytest

from client.audio_recorder import (
    AudioRecorder,
    concat_segments,
    pcm_sha256,
    recover_partial,
)


class FakeAudioStream:
    """可控制的假音訊串流，每次 read 回傳固定大小之 PCM 資料。"""

    def __init__(self, frame_chunk_size: int = 1024, max_reads: int | None = None):
        self.frame_chunk_size = frame_chunk_size
        self.max_reads = max_reads
        self.read_count = 0
        self.is_stopped = False
        self.is_closed = False

    def read(self, n: int, exception_on_overflow: bool = False) -> bytes:
        if self.is_stopped or self.is_closed:
            return b""
        if self.max_reads is not None and self.read_count >= self.max_reads:
            time.sleep(0.005)
            return b""
        self.read_count += 1
        time.sleep(0.001)
        sample_val = (self.read_count % 256)
        return bytes([sample_val, 0]) * n

    def stop_stream(self) -> None:
        self.is_stopped = True

    def close(self) -> None:
        self.is_closed = True


def test_segmented_recording_chunks(tmp_path):
    """Test 1: 假串流讀 10 次 (每次 1024 frames)，frames_per_segment=4096。
    封段產生 chunk_000000.wav (4096 frames), chunk_000001.wav (4096 frames),
    stop 後封最後一段 chunk_000002.wav (2048 frames)，共 10240 frames。
    """
    stream = FakeAudioStream(frame_chunk_size=1024, max_reads=10)
    cycle_dir = tmp_path / "cycle_test_1"
    cycle_dir.mkdir()

    segments_received: list[tuple[int, str]] = []

    def on_seg(seq: int, path: str):
        segments_received.append((seq, path))

    rec = AudioRecorder(
        str(tmp_path),
        frames_per_segment=4096,
        stream_factory=lambda: stream,
    )
    rec.on_segment = on_seg

    ok = rec.start_cycle(cycle_dir)
    assert ok is True

    # 等待讀滿 10 次
    while stream.read_count < 10:
        time.sleep(0.01)

    result_path = rec.stop()
    assert result_path == str(cycle_dir)
    assert rec.last_total_segments == 3

    # 驗證產生的 3 個 wav 檔案
    wavs = sorted(cycle_dir.glob("chunk_*.wav"))
    assert len(wavs) == 3
    assert [w.name for w in wavs] == ["chunk_000000.wav", "chunk_000001.wav", "chunk_000002.wav"]

    # 驗證 on_segment 回呼順序
    assert [s[0] for s in segments_received] == [0, 1, 2]

    # 驗證各段 frames 數與音訊規格 (16 kHz, mono, 16-bit)
    expected_frames = [4096, 4096, 2048]
    for i, w in enumerate(wavs):
        with wave.open(str(w), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 16000
            assert wf.getnframes() == expected_frames[i]


def test_streaming_disk_flush_and_zero_memory_leak(tmp_path):
    """Test 2: 錄音中 .pcm.part 隨 read 增長，且 AudioRecorder 無隨時間增長之記憶體串列。"""
    stream = FakeAudioStream(frame_chunk_size=1024)
    cycle_dir = tmp_path / "cycle_test_2"
    cycle_dir.mkdir()

    rec = AudioRecorder(
        str(tmp_path),
        frames_per_segment=100000,  # 設極大，確保不封段
        stream_factory=lambda: stream,
    )

    rec.start_cycle(cycle_dir)
    while stream.read_count < 3:
        time.sleep(0.01)

    # 檢查 .pcm.part 存在且大小大於 0
    part_files = list(cycle_dir.glob("chunk_*.pcm.part"))
    assert len(part_files) == 1
    size_after_3 = part_files[0].stat().st_size
    assert size_after_3 >= 3 * 1024 * 2

    # 檢查 audio_frames 串列長度恆為 0 (D-31-21)
    assert len(rec.audio_frames) == 0

    rec.stop()


def test_crash_recovery_partial(tmp_path):
    """Test 3: 模擬寫入一半未正常 stop 崩潰，recover_partial 轉為完整 WAV。"""
    cycle_dir = tmp_path / "cycle_test_3"
    cycle_dir.mkdir()

    # 人工建立一個寫入 3000 frames (6000 bytes) 的 .pcm.part
    part_file = cycle_dir / "chunk_000003.pcm.part"
    raw_pcm = b"\x2a\x00" * 3000
    part_file.write_bytes(raw_pcm)

    # 執行恢復
    recovered = recover_partial(cycle_dir)
    assert recovered == [3]

    # .pcm.part 應被清除，產生對應 .wav
    assert not part_file.exists()
    wav_file = cycle_dir / "chunk_000003.wav"
    assert wav_file.is_file()

    with wave.open(str(wav_file), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 3000


def test_on_segment_callback_exception_isolation(tmp_path):
    """Test 4: on_segment 拋例外不中斷錄音，on_error 收到訊息，後續分段正常產生。"""
    stream = FakeAudioStream(frame_chunk_size=1024, max_reads=6)
    cycle_dir = tmp_path / "cycle_test_4"
    cycle_dir.mkdir()

    errors_received: list[str] = []

    def bad_on_segment(seq: int, path: str):
        if seq == 0:
            raise RuntimeError("on_segment crash simulation")

    rec = AudioRecorder(
        str(tmp_path),
        frames_per_segment=2048,
        stream_factory=lambda: stream,
    )
    rec.on_segment = bad_on_segment
    rec.on_error = lambda msg: errors_received.append(msg)

    rec.start_cycle(cycle_dir)
    while stream.read_count < 6:
        time.sleep(0.01)

    rec.stop()

    assert len(errors_received) >= 1
    assert any("on_segment" in err for err in errors_received)

    # 後續分段正常產生
    wavs = sorted(cycle_dir.glob("chunk_*.wav"))
    assert len(wavs) >= 2


def test_segment_seconds_clamping(tmp_path):
    """Test 5: segment_seconds 夾在 15–30 秒之間。"""
    rec_low = AudioRecorder(str(tmp_path), segment_seconds=5.0)
    assert rec_low.segment_seconds == 15.0
    assert rec_low.frames_per_segment == 15 * 16000

    rec_high = AudioRecorder(str(tmp_path), segment_seconds=60.0)
    assert rec_high.segment_seconds == 30.0
    assert rec_high.frames_per_segment == 30 * 16000

    rec_mid = AudioRecorder(str(tmp_path), segment_seconds=20.0)
    assert rec_mid.segment_seconds == 20.0
    assert rec_mid.frames_per_segment == 20 * 16000


def test_legacy_mode_start_stop_concat(tmp_path):
    """Test 6: 舊模式 start()／stop() 回傳單一 WAV，frames 等於所有分段總和，pcm_sha256 一致。"""
    stream = FakeAudioStream(frame_chunk_size=1024, max_reads=6)

    rec = AudioRecorder(
        str(tmp_path),
        frames_per_segment=4096,
        stream_factory=lambda: stream,
    )

    ok = rec.start()
    assert ok is True

    while stream.read_count < 6:
        time.sleep(0.01)

    out_path = rec.stop()
    assert out_path is not None
    assert Path(out_path).is_file()
    assert Path(out_path).name.startswith("audio_")
    assert Path(out_path).name.endswith(".wav")

    with wave.open(out_path, "rb") as wf:
        total_frames = wf.getnframes()
        assert total_frames == stream.read_count * 1024

    # 驗證 concat 結果之 pcm_sha256 等於各分段串接之 pcm_sha256
    segment_wavs = sorted(rec._cycle_dir.glob("chunk_*.wav"))
    assert pcm_sha256([out_path]) == pcm_sha256(segment_wavs)


def test_start_cycle_resumes_next_seq(tmp_path):
    """Test 7: start_cycle 對已有 chunk_000000、chunk_000001 的目錄從 seq 2 接續。"""
    cycle_dir = tmp_path / "cycle_test_7"
    cycle_dir.mkdir()

    # 建立既有的 seq 0 與 seq 1
    for seq in (0, 1):
        wav_path = cycle_dir / f"chunk_{seq:06d}.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00\x00" * 100)

    stream = FakeAudioStream(frame_chunk_size=512, max_reads=3)
    rec = AudioRecorder(
        str(tmp_path),
        frames_per_segment=1024,
        stream_factory=lambda: stream,
    )

    rec.start_cycle(cycle_dir)
    while stream.read_count < 3:
        time.sleep(0.01)

    rec.stop()

    wavs = sorted(cycle_dir.glob("chunk_*.wav"))
    seqs = [int(w.stem.split("_")[1]) for w in wavs]
    assert 0 in seqs and 1 in seqs and 2 in seqs
