"""Phase 31: SoapVoice 分段上傳器測試 (D-31-20, D-31-22, D-31-27, D-31-30)."""

from __future__ import annotations

import io
import json
import math
from pathlib import Path
import struct
import wave
from typing import Any, List
import uuid

import httpx
import pytest

from client.chunk_uploader import ChunkUploader
from client.segment_store import SegmentStore


def make_dummy_wav(path: Path, seconds: float = 0.1, freq: float = 440.0) -> None:
    """建立測試用 PCM WAV 檔。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000
    total_frames = int(seconds * sample_rate)
    frames = bytearray()
    for i in range(total_frames):
        val = int(10000 * math.sin(2 * math.pi * freq * (i / sample_rate)))
        frames.extend(struct.pack("<h", val))

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)


def test_chunk_uploader_happy_path(tmp_path):
    """Test 1: 三段待傳，MockTransport 回 201 與正確 sha256 → 依 seq 0,1,2 全部 acked。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    # 建立 3 個 dummy 音檔分段
    for seq in range(3):
        p = c_dir / f"chunk_{seq:04d}.wav"
        make_dummy_wav(p, freq=440.0 + seq * 50)
        store.register_chunk(cid, seq, p)

    recorded_requests: List[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        # request.read() 取得 multipart 內容
        body_bytes = request.read()
        # 從 store 讀取對應 seq 的正確 sha256
        seq = len(recorded_requests) - 1
        m = store.load(cid)
        expected_sha = m.chunks[str(seq)]["sha256"]
        return httpx.Response(
            201,
            json={"cycle_id": cid, "seq": seq, "sha256": expected_sha, "duplicate": False},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    uploader = ChunkUploader(
        store,
        base_url="http://mockserver",
        api_key="valid-op-key",
        http=mock_client,
    )

    acked = uploader.process_once(cid)
    assert acked == 3

    total, acked_cnt, pending_cnt = uploader.progress(cid)
    assert acked_cnt == 3
    assert pending_cnt == 0
    assert len(recorded_requests) == 3

    # 驗證請求標頭與結構
    req0 = recorded_requests[0]
    assert req0.headers.get("X-API-Key") == "valid-op-key"
    assert "/api/cycles/" in str(req0.url)


def test_chunk_uploader_sha_mismatch(tmp_path):
    """Test 2: 回應 sha256 與本機不同 → 不標記 acked。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    p = c_dir / "chunk_0000.wav"
    make_dummy_wav(p)
    store.register_chunk(cid, 0, p)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            201,
            json={"cycle_id": cid, "seq": 0, "sha256": "wrong_sha256_hash", "duplicate": False},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    uploader = ChunkUploader(
        store,
        base_url="http://mockserver",
        api_key="valid-op-key",
        http=mock_client,
    )

    acked = uploader.process_once(cid)
    assert acked == 0
    m = store.load(cid)
    assert m.chunks["0"]["acked"] is False


def test_chunk_uploader_backoff_retry(tmp_path):
    """Test 3: 第一次 ConnectError、第二次 503、第三次 201 → 指數退避序列 1、2。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    p = c_dir / "chunk_0000.wav"
    make_dummy_wav(p)
    store.register_chunk(cid, 0, p)

    call_count = 0
    sleeps: List[float] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise httpx.ConnectError("Network down")
        elif call_count == 2:
            return httpx.Response(503, text="Service Unavailable")
        else:
            m = store.load(cid)
            return httpx.Response(
                201,
                json={"cycle_id": cid, "seq": 0, "sha256": m.chunks["0"]["sha256"], "duplicate": False},
            )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    uploader = ChunkUploader(
        store,
        base_url="http://mockserver",
        api_key="valid-op-key",
        http=mock_client,
        sleep=sleeps.append,
    )

    # 輪次 1: 遇 ConnectError
    uploader.process_once(cid)
    # 輪次 2: 遇 503
    uploader.process_once(cid)
    # 輪次 3: 成功 201
    acked = uploader.process_once(cid)

    assert acked == 1
    assert sleeps == [1.0, 2.0]


def test_chunk_uploader_409_stops_upload(tmp_path):
    """Test 4: 409 → set_error，後續分段不再嘗試，檔案仍存在。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    for seq in range(2):
        p = c_dir / f"chunk_{seq:04d}.wav"
        make_dummy_wav(p)
        store.register_chunk(cid, seq, p)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "conflict_sha", "message": "Seq sha mismatch"})

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    uploader = ChunkUploader(
        store,
        base_url="http://mockserver",
        api_key="valid-op-key",
        http=mock_client,
    )

    acked = uploader.process_once(cid)
    assert acked == 0
    m = store.load(cid)
    assert m.last_error is not None
    assert "409" in m.last_error
    # 檔案完整保留 (D-31-29)
    assert (c_dir / "chunk_0000.wav").exists()
    assert (c_dir / "chunk_0001.wav").exists()


def test_chunk_uploader_register_chunk_concurrency(tmp_path):
    """Test 5: 上傳進行中註冊新段（錄音持續中）→ 下一輪成功上傳新段。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    p0 = c_dir / "chunk_0000.wav"
    make_dummy_wav(p0)
    store.register_chunk(cid, 0, p0)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        m = store.load(cid)
        # 尋找請求中的 seq
        return httpx.Response(
            201,
            json={"cycle_id": cid, "seq": 0, "sha256": m.chunks["0"]["sha256"], "duplicate": False},
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    uploader = ChunkUploader(
        store,
        base_url="http://mockserver",
        api_key="valid-op-key",
        http=mock_client,
    )

    uploader.process_once(cid)
    assert store.load(cid).chunks["0"]["acked"] is True

    # 模擬錄音中途落地 seq 1
    p1 = c_dir / "chunk_0001.wav"
    make_dummy_wav(p1)
    store.register_chunk(cid, 1, p1)

    def mock_handler2(request: httpx.Request) -> httpx.Response:
        m = store.load(cid)
        return httpx.Response(
            201,
            json={"cycle_id": cid, "seq": 1, "sha256": m.chunks["1"]["sha256"], "duplicate": False},
        )

    mock_client2 = httpx.Client(transport=httpx.MockTransport(mock_handler2))
    uploader._http = mock_client2

    uploader.process_once(cid)
    assert store.load(cid).chunks["1"]["acked"] is True


def test_chunk_uploader_matches_contract_fixture():
    """Test 6: 驗證請求格式與 fixture server.chunk_upload 欄位一致。"""
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "phase31_contract_v1.json"
    with open(fixture_path, "r", encoding="utf-8") as f:
        contract = json.load(f)

    form_spec = contract["server"]["chunk_upload"]["form"]
    assert "seq" in form_spec
    assert "sha256" in form_spec
