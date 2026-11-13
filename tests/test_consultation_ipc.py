"""Tests for ControlServer and SoapVoice IPC Contract (Phase 31 Plan 31-15 Task 1)."""

import json
import os
from pathlib import Path
import stat
import urllib.error
import urllib.request
import pytest

from client.audio_recorder import AudioRecorder
from client.control_server import ControlServer, default_control_token_path, ensure_token
from client.cycle_session import CycleSession
from client.segment_store import SegmentStore

CONTRACT_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase31_contract_v1.json"


def load_fixture() -> dict:
    with open(CONTRACT_FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _request(
    port: int,
    path: str,
    method: str = "GET",
    token: str | None = None,
    host: str | None = None,
    body: dict | str | bytes | None = None,
) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{port}{path}"
    headers = {}
    if host is not None:
        headers["Host"] = host
    else:
        headers["Host"] = f"127.0.0.1:{port}"

    if token is not None:
        headers["X-Local-Token"] = token

    data = None
    if body is not None:
        if isinstance(body, (dict, list)):
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            data = body.encode("utf-8")
        elif isinstance(body, bytes):
            data = body

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return exc.code, parsed


@pytest.fixture
def test_server(tmp_path):
    store = SegmentStore(tmp_path / "cycles")
    recorder = AudioRecorder(str(tmp_path))
    session = CycleSession(recorder=recorder, store=store)
    token = "test-token-1234567890abcdef1234567890abcdef"

    server = ControlServer(
        session=session,
        port=0,
        host="127.0.0.1",
        token=token,
    )
    server.start()
    yield server, server.bound_port, token, session
    server.stop()


def test_ipc_auth_and_host_check(test_server):
    """Test ipc_1: ControlServer 綁定 127.0.0.1;
    無 token 或錯 token -> 401;
    Host: evil.example -> 400;
    正確 -> status 欄位與 fixture 一致。
    """
    _, port, token, session = test_server
    fixture = load_fixture()
    expected_status_example = fixture["ipc"]["status"]["response"]

    # 1. 無 token -> 401
    code, err = _request(port, "/control/v1/status", method="GET")
    assert code == 401
    assert err.get("error") == "unauthorized"

    # 2. 錯誤 token -> 401
    code, err = _request(port, "/control/v1/status", method="GET", token="wrong-token")
    assert code == 401
    assert err.get("error") == "unauthorized"

    # 3. 惡意 Host 標頭 -> 400
    code, err = _request(port, "/control/v1/status", method="GET", token=token, host="evil.example:80")
    assert code == 400
    assert err.get("error") == "invalid_host"

    # 4. 正確請求 -> 200，欄位與契約 fixture 一致
    code, data = _request(port, "/control/v1/status", method="GET", token=token)
    assert code == 200
    assert data["contract"] == expected_status_example["contract"]
    for key in ("state", "cycle_id", "elapsed_seconds", "patient_bound", "chunks_total", "chunks_acked", "chunks_pending", "draft_submitted", "last_error"):
        assert key in data


def test_ipc_rejects_non_loopback(tmp_path):
    """Test ipc_2: control_host='0.0.0.0' 或外部 IP -> 建構時拋 ValueError。"""
    store = SegmentStore(tmp_path / "cycles")
    recorder = AudioRecorder(str(tmp_path))
    session = CycleSession(recorder=recorder, store=store)

    with pytest.raises(ValueError):
        ControlServer(session=session, port=0, host="0.0.0.0", token="dummy")

    with pytest.raises(ValueError):
        ControlServer(session=session, port=0, host="192.168.1.100", token="dummy")


def test_ipc_payload_limits_and_validation(test_server):
    """Test ipc_3: body 超過 4 KB -> 413; 非 JSON -> 422; command_id 不是 32 hex -> 422。"""
    _, port, token, _ = test_server

    # 1. body 超過 4KB -> 413
    huge_body = b"x" * 5000
    code, err = _request(port, "/control/v1/start", method="POST", token=token, body=huge_body)
    assert code == 413
    assert err.get("error") == "payload_too_large"

    # 2. 非 JSON 內文 -> 422
    code, err = _request(port, "/control/v1/start", method="POST", token=token, body="not a json string")
    assert code == 422
    assert err.get("error") == "invalid_json"

    # 3. command_id 非 32 位 hex -> 422
    bad_req = {"command_id": "short", "cycle_id": "a" * 32}
    code, err = _request(port, "/control/v1/start", method="POST", token=token, body=bad_req)
    assert code == 422
    assert err.get("error") == "invalid_field"

    # 4. cycle_id 非 32 位 hex -> 422
    bad_req2 = {"command_id": "a" * 32, "cycle_id": "not-valid-hex!"}
    code, err = _request(port, "/control/v1/start", method="POST", token=token, body=bad_req2)
    assert code == 422
    assert err.get("error") == "invalid_field"


def test_ipc_token_generation_and_permissions(tmp_path):
    """Test ipc_4: token 檔不存在時自動建立（長度 ≥ 43），POSIX 下權限為 0o600；已存在則沿用不覆寫。"""
    token_file = tmp_path / "control_token"
    assert not token_file.exists()

    token1 = ensure_token(token_file)
    assert len(token1) >= 43
    assert token_file.is_file()

    if os.name == "posix":
        mode = stat.S_IMODE(token_file.stat().st_mode)
        assert mode == 0o600

    # 再次呼叫應沿用已有的 token，不覆寫
    token2 = ensure_token(token_file)
    assert token2 == token1
