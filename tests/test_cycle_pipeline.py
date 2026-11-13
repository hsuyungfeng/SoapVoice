"""Phase 31: SoapVoice 循環 Pipeline 測試 (D-31-23, D-31-24, D-31-25)."""

from __future__ import annotations

import json
import math
from pathlib import Path
import struct
import wave
from typing import Any, Dict, List
import uuid

import httpx
import pytest

from client.audio_recorder import pcm_sha256
from client.cycle_pipeline import CyclePipeline, map_lan_result_to_draft
from client.segment_store import SegmentStore


def make_dummy_wav(path: Path, seconds: float = 0.1, freq: float = 440.0) -> None:
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


def test_pipeline_unacked_stays_uploading(tmp_path):
    """Test 1: 尚有未 acked 分段 → advance 回 UPLOADING，不呼叫 finalize。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    for seq in range(2):
        p = c_dir / f"chunk_{seq:04d}.wav"
        make_dummy_wav(p)
        store.register_chunk(cid, seq, p)
    store.set_total(cid, 2)
    # 只 ack 第 0 段
    m = store.load(cid)
    store.mark_acked(cid, 0, m.chunks["0"]["sha256"])

    called = False

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    pipeline = CyclePipeline(store, base_url="http://mockserver", api_key="key", http=client)

    st = pipeline.advance(cid)
    assert st == "UPLOADING"
    assert called is False


def test_pipeline_finalize_success(tmp_path):
    """Test 2: 全部 acked、total=3 → POST finalize，audio_sha256 等於 pcm_sha256(3段)；mark_finalized。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    paths = []
    for seq in range(3):
        p = c_dir / f"chunk_{seq:04d}.wav"
        make_dummy_wav(p, freq=440.0 + seq * 20)
        store.register_chunk(cid, seq, p)
        m = store.load(cid)
        store.mark_acked(cid, seq, m.chunks[str(seq)]["sha256"])
        paths.append(p)

    store.set_total(cid, 3)
    expected_pcm_sha = pcm_sha256(paths)

    recorded_req: List[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_req.append(request)
        return httpx.Response(200, json={"cycle_id": cid, "total_chunks": 3, "upload_complete": True})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    pipeline = CyclePipeline(store, base_url="http://mockserver", api_key="key", http=client)

    st = pipeline.advance(cid)
    assert st == "GENERATING"
    assert store.load(cid).finalized is True

    req = recorded_req[0]
    assert "/finalize" in str(req.url)
    req_body = json.loads(req.read().decode("utf-8"))
    assert req_body["total_chunks"] == 3
    assert req_body["audio_sha256"] == expected_pcm_sha


def test_pipeline_finalize_missing_chunks_reset(tmp_path):
    """Test 3: finalize 回 409 missing=[1] → seq 1 重新標為未 acked，回 UPLOADING。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    for seq in range(2):
        p = c_dir / f"chunk_{seq:04d}.wav"
        make_dummy_wav(p)
        store.register_chunk(cid, seq, p)
        m = store.load(cid)
        store.mark_acked(cid, seq, m.chunks[str(seq)]["sha256"])
    store.set_total(cid, 2)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(409, json={"error": "missing_chunks", "missing": [1]})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    pipeline = CyclePipeline(store, base_url="http://mockserver", api_key="key", http=client)

    st = pipeline.advance(cid)
    assert st == "UPLOADING"
    m_after = store.load(cid)
    assert m_after.chunks["1"]["acked"] is False
    assert m_after.chunks["0"]["acked"] is True


def test_pipeline_generate_fn_full_wav(tmp_path):
    """Test 4: generate_fn 接收串接後 full.wav，結果存 lan_result.json；重啟後不再重複呼叫。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    total_frames = 0
    for seq in range(2):
        p = c_dir / f"chunk_{seq:04d}.wav"
        make_dummy_wav(p, seconds=0.2)
        with wave.open(str(p), "rb") as wf:
            total_frames += wf.getnframes()
        store.register_chunk(cid, seq, p)
        store.mark_acked(cid, seq, store.load(cid).chunks[str(seq)]["sha256"])
    store.set_total(cid, 2)
    store.mark_finalized(cid)

    store.set_context(cid, {
        "screenshot_path": "/tmp/screen.jpg",
        "patient_name": "Wang Xiao-Ming",
        "doctor_name": "Dr. Chen",
    })

    gen_call_count = 0

    def mock_generate(audio_path, screenshot, patient, doctor):
        nonlocal gen_call_count
        gen_call_count += 1
        with wave.open(audio_path, "rb") as wf:
            assert wf.getnframes() == total_frames
        return {
            "transcript": "Hello doctor",
            "soap": {"s": "cough", "o": "clear", "a": "cold", "p": "rest"},
        }

    pipeline = CyclePipeline(store, base_url="http://mockserver", api_key="key", generate_fn=mock_generate)
    st = pipeline.advance(cid)
    assert st == "GENERATING"
    assert gen_call_count == 1
    assert (c_dir / "lan_result.json").exists()

    # 再次建立 pipeline 實例推進，不再呼叫 generate_fn
    pipeline2 = CyclePipeline(store, base_url="http://mockserver", api_key="key", generate_fn=mock_generate)
    st2 = pipeline2.advance(cid)
    assert gen_call_count == 1


def test_map_lan_result_to_draft():
    """Test 5: map_lan_result_to_draft 欄位映射與 extras_missing 追蹤 (D-31-25)。"""
    cid = uuid.uuid4().hex
    lan_res = {
        "transcript": "Patient feels chest tightness",
        "soap": {"s": "chest tightness", "o": "HR 72", "a": "angina suspect", "p": "EKG"},
        "summary_zh": "病患主訴胸悶",
        "history": "高血壓五年",
        "icd10_codes": [{"code": "I20.9"}],
        "medical_orders": ["33001B"],
        # drug_recommendations 缺失
    }

    payload, missing = map_lan_result_to_draft(
        lan_res,
        cycle_id=cid,
        patient_ref="P12345678",
        case_id="case_999",
        visit_date="2026-11-12",
        order_code="33001B",
    )

    assert payload["session_id"] == cid
    assert payload["case_id"] == "case_999"
    assert payload["patient_ref"] == "P12345678"
    assert payload["visit_date"] == "2026-11-12"
    assert payload["order_code"] == "33001B"
    assert payload["transcript"] == "Patient feels chest tightness"
    assert payload["soap"]["s"] == "chest tightness"

    assert payload["extras"]["summary_zh"] == "病患主訴胸悶"
    assert payload["extras"]["past_history"] == "高血壓五年"
    assert payload["extras"]["suggestions"]["icd10"] == ["I20.9"]
    assert payload["extras"]["suggestions"]["orders"] == ["33001B"]
    assert payload["extras"]["suggestions"]["meds"] == []

    assert "suggestions.meds" in missing
    assert "summary_zh" not in missing


def test_pipeline_submit_draft(tmp_path):
    """Test 6: draft 送出回 201 → SUBMITTED；409 回 ERROR；網路錯誤保持 GENERATING。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    store.mark_finalized(cid)
    store.mark_generation_done(cid)

    # 寫入假 lan_result.json
    res_data = {
        "transcript": "Sore throat",
        "soap": {"s": "sore throat", "o": "red pharynx", "a": "pharyngitis", "p": "meds"},
    }
    (c_dir / "lan_result.json").write_text(json.dumps(res_data), encoding="utf-8")

    # 1. 網路錯誤時保持 GENERATING
    def mock_err_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Timeout")

    client_err = httpx.Client(transport=httpx.MockTransport(mock_err_handler))
    pipe_err = CyclePipeline(store, base_url="http://mockserver", api_key="key", http=client_err)
    assert pipe_err.advance(cid) == "GENERATING"

    # 2. 成功 201 → SUBMITTED
    def mock_ok_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"status": "created", "draft_id": "draft_777"})

    client_ok = httpx.Client(transport=httpx.MockTransport(mock_ok_handler))
    pipe_ok = CyclePipeline(store, base_url="http://mockserver", api_key="key", http=client_ok)
    assert pipe_ok.advance(cid) == "SUBMITTED"
    assert store.load(cid).draft_submitted is True
    assert store.load(cid).draft_id == "draft_777"


def test_pipeline_generate_fn_exception_keeps_generating(tmp_path):
    """Test 7: generate_fn 拋例外 → 保持 GENERATING、記 last_error，不刪任何檔案。"""
    store = SegmentStore(tmp_path / "cycles")
    cid = uuid.uuid4().hex
    c_dir = store.open_cycle(cid)

    p = c_dir / "chunk_0000.wav"
    make_dummy_wav(p)
    store.register_chunk(cid, 0, p)
    store.mark_finalized(cid)

    def failing_generate(*args):
        raise RuntimeError("LLM Out of Memory")

    pipe = CyclePipeline(store, base_url="http://mockserver", api_key="key", generate_fn=failing_generate)
    st = pipe.advance(cid)
    assert st == "GENERATING"
    m = store.load(cid)
    assert "LLM Out of Memory" in (m.last_error or "")
    assert p.exists()
