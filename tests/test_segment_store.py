"""Tests for SegmentStore, CycleManifest, and LANConfig additions (Phase 31 Task 1)."""

import hashlib
import os
from pathlib import Path
import threading
import pytest

from client.lan_config import LANConfig
from client.segment_store import CycleManifest, SegmentStore


def test_register_chunk_sha256(tmp_path):
    """Test 1: register_chunk 記錄的 sha256 等於 hashlib.sha256(檔案位元組)。"""
    store = SegmentStore(tmp_path)
    cycle_dir = store.open_cycle("cycle_001")

    chunk_file = cycle_dir / "chunk_000000.wav"
    chunk_data = b"RIFF....test_pcm_bytes...."
    chunk_file.write_bytes(chunk_data)

    expected_sha = hashlib.sha256(chunk_data).hexdigest()
    recorded_sha = store.register_chunk("cycle_001", 0, chunk_file)

    assert recorded_sha == expected_sha

    m = store.load("cycle_001")
    assert m is not None
    assert "0" in m.chunks
    assert m.chunks["0"]["sha256"] == expected_sha
    assert m.chunks["0"]["size"] == len(chunk_data)
    assert m.chunks["0"]["acked"] is False


def test_mark_acked_sha256_verification(tmp_path):
    """Test 2: mark_acked 以錯誤 sha256 → False 且 acked 仍為 False；正確 → True。"""
    store = SegmentStore(tmp_path)
    cycle_dir = store.open_cycle("cycle_002")

    chunk_file = cycle_dir / "chunk_000000.wav"
    chunk_data = b"some_audio_bytes"
    chunk_file.write_bytes(chunk_data)
    correct_sha = store.register_chunk("cycle_002", 0, chunk_file)

    # 錯誤 sha256
    wrong_ok = store.mark_acked("cycle_002", 0, "wrong_hash_1234567890")
    assert wrong_ok is False
    m_after_wrong = store.load("cycle_002")
    assert m_after_wrong.chunks["0"]["acked"] is False

    # 正確 sha256
    right_ok = store.mark_acked("cycle_002", 0, correct_sha)
    assert right_ok is True
    m_after_right = store.load("cycle_002")
    assert m_after_right.chunks["0"]["acked"] is True
    assert m_after_right.chunks["0"]["server_sha256"] == correct_sha


def test_pending_chunks_and_reset_ack_and_context(tmp_path):
    """Test 3: pending_chunks 升冪且排除已 acked；reset_ack 重置；context 讀寫一致。"""
    store = SegmentStore(tmp_path)
    cycle_dir = store.open_cycle("cycle_003")

    for seq in (2, 0, 1):
        f = cycle_dir / f"chunk_{seq:06d}.wav"
        f.write_bytes(f"pcm_{seq}".encode())
        store.register_chunk("cycle_003", seq, f)

    # 升冪排序
    assert store.pending_chunks("cycle_003") == [0, 1, 2]

    # ack seq 1
    m = store.load("cycle_003")
    store.mark_acked("cycle_003", 1, m.chunks["1"]["sha256"])
    assert store.pending_chunks("cycle_003") == [0, 2]

    # reset_ack seq 1
    store.reset_ack("cycle_003", [1])
    assert store.pending_chunks("cycle_003") == [0, 1, 2]

    # set_context / get_context
    ctx = {"patient_id": "P123", "doctor": "Dr. Wang"}
    store.set_context("cycle_003", ctx)
    assert store.get_context("cycle_003") == ctx


def test_restart_persistence_and_unfinished_cycles(tmp_path):
    """Test 4: 重新建立 SegmentStore 後 load 讀回相同狀態；unfinished_cycles 列出未封存循環。"""
    store1 = SegmentStore(tmp_path)
    c1 = store1.open_cycle("c1")
    c2 = store1.open_cycle("c2")

    store1.mark_archived("c1")
    store1.set_total("c2", 5)

    # 重建模擬重啟
    store2 = SegmentStore(tmp_path)
    m1 = store2.load("c1")
    m2 = store2.load("c2")
    assert m1.archived is True
    assert m2.archived is False
    assert m2.total_chunks == 5

    unfinished = store2.unfinished_cycles()
    assert [c.cycle_id for c in unfinished] == ["c2"]


def test_concurrency_thread_safety(tmp_path):
    """Test 5: 兩個執行緒同時 register_chunk 與 mark_acked，manifest 仍為合法 JSON 且無遺失。"""
    store = SegmentStore(tmp_path)
    cycle_dir = store.open_cycle("concurrent_cycle")

    # 事先建立 100 個假 chunk 檔案
    sha_map: dict[int, str] = {}
    for i in range(100):
        f = cycle_dir / f"chunk_{i:06d}.wav"
        data = f"data_{i}".encode()
        f.write_bytes(data)
        sha_map[i] = hashlib.sha256(data).hexdigest()

    def worker_register():
        for i in range(100):
            f = cycle_dir / f"chunk_{i:06d}.wav"
            store.register_chunk("concurrent_cycle", i, f)

    def worker_ack():
        for i in range(100):
            # 輪詢等待 chunk 出現在 manifest 中後 ack
            for _ in range(50):
                if store.mark_acked("concurrent_cycle", i, sha_map[i]):
                    break
                import time
                time.sleep(0.002)

    t1 = threading.Thread(target=worker_register)
    t2 = threading.Thread(target=worker_ack)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    final_m = store.load("concurrent_cycle")
    assert final_m is not None
    assert len(final_m.chunks) == 100


def test_lan_config_fields(monkeypatch):
    """Test 6: LANConfig() 預設值、環境變數覆蓋與秒數夾取。"""
    cfg_default = LANConfig()
    assert cfg_default.chunk_seconds == 20
    assert cfg_default.temp_cache_max_mb == 2048
    assert cfg_default.control_port == 18765
    assert cfg_default.control_host == "127.0.0.1"
    assert "ElcSoapVoice" in cfg_default.control_token_path
    assert cfg_default.cycles_dir == Path(cfg_default.local_cache_dir) / "cycles"

    # 環境變數覆蓋
    monkeypatch.setenv("SOAPVOICE_TEMP_CACHE_MAX_MB", "512")
    monkeypatch.setenv("SOAPVOICE_CONTROL_PORT", "19999")
    cfg_env = LANConfig.from_env()
    assert cfg_env.temp_cache_max_mb == 512
    assert cfg_env.control_port == 19999

    # chunk_seconds 夾取 (15-30)
    cfg_low = LANConfig(chunk_seconds=5)
    assert cfg_low.chunk_seconds == 15

    cfg_high = LANConfig(chunk_seconds=60)
    assert cfg_high.chunk_seconds == 30
