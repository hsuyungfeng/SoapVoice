"""
問診儲存端到端整合測試

測試範圍：
- 雙軌寫入：SessionManager.complete_session() 僅寫入 JSON，_save_to_sqlite() 寫入 SQLite
- 完整問診流程模擬（Session → complete_session → _save_to_sqlite）
- 音檔路徑正確寫入 DB
- 患者自動關聯（get_or_create_patient 不重複建立）
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio

from src.consultation.session_manager import SessionManager
from src.consultation.consultation_flow import (
    ConsultationResult,
    SessionSummary,
)
from src.db.patient_records_db import (
    close_patient_records_db,
    get_patient_records_db,
    init_schema,
    get_or_create_patient,
    set_db_path_for_test,
)


# ── 測試輔助函式 ─────────────────────────────────────────────────


def _make_fake_result(
    session_id: str = "test-session-001",
    transcript: str = "頭痛三天，有發燒",
    audio_path: str = "/tmp/test_audio.wav",
    audio_duration_ms: int = 15000,
    asr_model: str = "whisper-medium",
    asr_time_ms: int = 1200,
    llm_model: str = "gemma4:e4b",
    llm_time_ms: int = 3500,
    total_time_ms: int = 5000,
    soap: dict = None,
    patient_context: dict = None,
) -> ConsultationResult:
    """建立假的 ConsultationResult 用於測試"""
    if soap is None:
        soap = {
            "subjective": "患者自述頭痛三天，有發燒",
            "objective": "體溫 38.2°C，咽喉紅腫",
            "assessment": "急性上呼吸道感染（J06.9）",
            "plan": "開立退燒藥、抗生素，建議多休息",
        }
    if patient_context is None:
        patient_context = {"name": "測試病患", "doctor_name": "王醫師", "clinic_name": "測試診所"}

    summary = SessionSummary(
        session_id=session_id,
        patient_context=patient_context,
        transcript=transcript,
        segments=[
            {"start": 0.0, "end": 3.5, "text": "頭痛三天"},
            {"start": 4.0, "end": 7.2, "text": "有發燒"},
        ],
        duration_seconds=15.0,
        icd10_codes=[{"code": "J06.9", "name": "急性上呼吸道感染"}],
        drug_recommendations=[
            {"code": "A01", "name": "退燒藥", "atc_code": "N02BE01"}
        ],
        medical_orders=[{"code": "O01", "name": "血液檢查"}],
        created_at=datetime.now(),
    )

    return ConsultationResult(
        session_id=session_id,
        soap=soap,
        session_summary=summary,
        metadata={
            "transcript": transcript,
            "segments": summary.segments,
            "audio_path": audio_path,
            "audio_duration_ms": audio_duration_ms,
            "asr_model": asr_model,
            "asr_time_ms": asr_time_ms,
            "llm_model": llm_model,
            "llm_time_ms": llm_time_ms,
        },
        processing_time_ms=total_time_ms,
    )


# ── Fixtures ─────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_db():
    """建立暫時測試資料庫，每個測試前後清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_storage.db"
        set_db_path_for_test(db_path)
        db = await get_patient_records_db()
        await init_schema(db)
        yield db
        await close_patient_records_db()


@pytest_asyncio.fixture
async def session_manager_with_db(test_db):
    """建立含暫時儲存目錄的 SessionManager"""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_dir = Path(tmpdir) / "sessions"
        sm = SessionManager(storage_dir=storage_dir)
        yield sm


# ── TestConsultationStorage ──────────────────────────────────────


class TestConsultationStorage:
    """測試完整問診流程中的儲存行為"""

    @pytest.mark.asyncio
    async def test_save_to_sqlite_writes_consultation_record(self, test_db, session_manager_with_db):
        """驗證 _save_to_sqlite() 正確寫入 consultation_records 表"""
        sm = session_manager_with_db

        # 建立會話
        patient_ctx = {"name": "張三", "doctor_name": "李醫師", "clinic_name": "健康診所"}
        session = sm.create_session(patient_context=patient_ctx)

        # 建立假的諮詢結果
        result = _make_fake_result(
            session_id=session.session_id,
            transcript="咳嗽兩天，痰多",
            patient_context=patient_ctx,
        )

        # 完成會話（JSON 持久化）
        sm.complete_session(session.session_id, result)

        # 寫入 SQLite
        saved = await sm._save_to_sqlite(session)
        assert saved is True, "_save_to_sqlite 應回傳 True"

        # 驗證資料庫中有記錄
        cursor = await test_db.execute(
            "SELECT * FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None, f"consultation_records 應有 session_id={session.session_id} 的記錄"
        assert row["patient_name"] == "張三"
        assert row["doctor_name"] == "李醫師"
        assert row["clinic_name"] == "健康診所"
        assert row["transcript_text"] == "咳嗽兩天，痰多"
        assert row["status"] == "completed"
        assert row["audio_file_path"] == "/tmp/test_audio.wav"
        assert row["audio_duration_ms"] == 15000
        assert row["asr_model"] == "whisper-medium"
        assert row["asr_time_ms"] == 1200
        assert row["llm_model"] == "gemma4:e4b"
        assert row["llm_time_ms"] == 3500
        assert row["total_time_ms"] == 5000

        # 驗證 SOAP JSON 正確
        soap = json.loads(row["soap_json"])
        assert soap["subjective"] == "患者自述頭痛三天，有發燒"
        assert soap["assessment"] == "急性上呼吸道感染（J06.9）"

    @pytest.mark.asyncio
    async def test_save_to_sqlite_returns_false_when_no_result(self, session_manager_with_db):
        """驗證 result 為 None 時 _save_to_sqlite 回傳 False"""
        sm = session_manager_with_db
        session = sm.create_session({"name": "無結果病患"})
        # session.result 為 None（未呼叫 complete_session）
        saved = await sm._save_to_sqlite(session)
        assert saved is False

    @pytest.mark.asyncio
    async def test_save_to_sqlite_handles_unknown_patient_name(self, test_db, session_manager_with_db):
        """驗證未知病患名稱仍可正常寫入（name 取預設值，不拋出例外）"""
        sm = session_manager_with_db

        # 不設定 patient_context（空 dict）
        session = sm.create_session(patient_context={})
        result = _make_fake_result(
            session_id=session.session_id,
            patient_context={},
        )
        sm.complete_session(session.session_id, result)

        saved = await sm._save_to_sqlite(session)
        assert saved is True

        # 驗證使用了預設值
        cursor = await test_db.execute(
            "SELECT patient_name FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        # 預設值應為 "未知病患"（_save_to_sqlite 中取 patient_ctx.get("name", "未知病患")）
        assert row["patient_name"] == "未知病患"


# ── TestDualTrackWrite ───────────────────────────────────────────


class TestDualTrackWrite:
    """驗證 JSON 與 SQLite 雙軌寫入的獨立性"""

    @pytest.mark.asyncio
    async def test_complete_session_writes_json_only(
        self, test_db, session_manager_with_db
    ):
        """完成會話後 JSON 檔案存在，但 SQLite 無記錄（直到呼叫 _save_to_sqlite）"""
        sm = session_manager_with_db
        session = sm.create_session({"name": "雙軌測試"})
        session_id = session.session_id

        result = _make_fake_result(session_id=session_id)
        sm.complete_session(session_id, result)

        # 驗證 JSON 檔案存在
        json_path = sm.storage_dir / f"{session_id}.json"
        assert json_path.exists(), f"JSON 檔案不存在: {json_path}"

        # 讀取 JSON 內容驗證
        with open(json_path, encoding="utf-8") as f:
            json_data = json.load(f)
        assert json_data["session_id"] == session_id
        assert json_data["status"] == "completed"
        assert json_data["result"] is not None
        assert json_data["result"]["soap"] is not None

        # 驗證 SQLite 尚無記錄（complete_session 不自動寫入 SQLite）
        cursor = await test_db.execute(
            "SELECT COUNT(*) FROM consultation_records WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        assert row[0] == 0, (
            "complete_session 不應自動寫入 SQLite，但 consultation_records 有記錄"
        )

    @pytest.mark.asyncio
    async def test_save_to_sqlite_writes_after_complete_session(
        self, test_db, session_manager_with_db
    ):
        """complete_session 後呼叫 _save_to_sqlite 寫入 SQLite"""
        sm = session_manager_with_db
        session = sm.create_session({"name": "雙軌測試2"})
        result = _make_fake_result(session_id=session.session_id)
        sm.complete_session(session.session_id, result)

        # 寫入 SQLite
        saved = await sm._save_to_sqlite(session)
        assert saved is True

        # 驗證 SQLite 記錄存在且欄位正確
        cursor = await test_db.execute(
            "SELECT * FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["patient_name"] == "雙軌測試2"
        assert row["status"] == "completed"
        assert row["soap_json"] is not None

        # 驗證 JSON 檔案依然存在（雙軌並存）
        json_path = sm.storage_dir / f"{session.session_id}.json"
        assert json_path.exists()

    @pytest.mark.asyncio
    async def test_session_id_unique_prevents_duplicate_write(
        self, test_db, session_manager_with_db
    ):
        """驗證重複寫入相同 session_id 不回傳 False（UNIQUE 約束保護）"""
        sm = session_manager_with_db
        session = sm.create_session({"name": "唯一測試"})
        result = _make_fake_result(session_id=session.session_id)
        sm.complete_session(session.session_id, result)

        # 第一次寫入
        saved1 = await sm._save_to_sqlite(session)
        assert saved1 is True

        # 第二次寫入相同 session_id
        saved2 = await sm._save_to_sqlite(session)
        assert saved2 is False, "重複寫入應回傳 False（UNIQUE 約束違反）"

        # 驗證只有一筆記錄
        cursor = await test_db.execute(
            "SELECT COUNT(*) FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row[0] == 1, f"預期 1 筆記錄，實際 {row[0]} 筆"


# ── TestAudioPathStorage ────────────────────────────────────────


class TestAudioPathStorage:
    """驗證音檔路徑正確儲存於資料庫"""

    @pytest.mark.asyncio
    async def test_audio_path_stored_correctly(self, test_db, session_manager_with_db):
        """驗證 audio_file_path 欄位正確寫入"""
        sm = session_manager_with_db
        session = sm.create_session({"name": "音檔測試"})

        audio_file = "/recordings/20260424_103000_abc123.wav"
        result = _make_fake_result(
            session_id=session.session_id,
            audio_path=audio_file,
            audio_duration_ms=32000,
        )
        sm.complete_session(session.session_id, result)
        await sm._save_to_sqlite(session)

        cursor = await test_db.execute(
            "SELECT audio_file_path, audio_duration_ms FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["audio_file_path"] == audio_file
        assert row["audio_duration_ms"] == 32000

    @pytest.mark.asyncio
    async def test_empty_audio_path_handled(self, test_db, session_manager_with_db):
        """驗證空白音檔路徑可正常寫入"""
        sm = session_manager_with_db
        session = sm.create_session({"name": "無音檔測試"})

        result = _make_fake_result(
            session_id=session.session_id,
            audio_path="",
            audio_duration_ms=0,
        )
        sm.complete_session(session.session_id, result)
        await sm._save_to_sqlite(session)

        cursor = await test_db.execute(
            "SELECT audio_file_path, audio_duration_ms FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["audio_file_path"] == ""
        assert row["audio_duration_ms"] == 0


# ── TestPatientAutoLink ─────────────────────────────────────────


class TestPatientAutoLink:
    """驗證病患自動關聯與不重複建立"""

    @pytest.mark.asyncio
    async def test_get_or_create_creates_new_patient(self, test_db):
        """首次查詢時自動建立病患記錄"""
        pid = await get_or_create_patient("新病患")
        assert pid > 0

        cursor = await test_db.execute(
            "SELECT name FROM patient_records WHERE id = ?", (pid,)
        )
        row = await cursor.fetchone()
        assert row["name"] == "新病患"

    @pytest.mark.asyncio
    async def test_get_or_create_does_not_duplicate(self, test_db):
        """相同姓名第二次呼叫不重複建立"""
        pid1 = await get_or_create_patient("重複病患")
        pid2 = await get_or_create_patient("重複病患")
        assert pid1 == pid2, f"pid1={pid1}, pid2={pid2} 應相同"

        cursor = await test_db.execute(
            "SELECT COUNT(*) FROM patient_records WHERE name = ?", ("重複病患",)
        )
        row = await cursor.fetchone()
        assert row[0] == 1, f"預期 1 筆記錄，實際 {row[0]} 筆"

    @pytest.mark.asyncio
    async def test_save_to_sqlite_auto_links_patient(
        self, test_db, session_manager_with_db
    ):
        """_save_to_sqlite 自動關聯 patient_id"""
        sm = session_manager_with_db

        # 第一次問診
        session1 = sm.create_session({"name": "自動關聯病患"})
        result1 = _make_fake_result(session_id=session1.session_id)
        sm.complete_session(session1.session_id, result1)
        await sm._save_to_sqlite(session1)

        # 查詢 patient_id 已關聯
        cursor = await test_db.execute(
            "SELECT patient_id FROM consultation_records WHERE session_id = ?",
            (session1.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["patient_id"] is not None and row["patient_id"] > 0, (
            "patient_id 應已自動關聯"
        )

        # 第二次問診（相同病患名稱）
        session2 = sm.create_session({"name": "自動關聯病患"})
        result2 = _make_fake_result(session_id=session2.session_id)
        sm.complete_session(session2.session_id, result2)
        await sm._save_to_sqlite(session2)

        # 驗證兩次問診指向相同 patient_id
        cursor2 = await test_db.execute(
            "SELECT patient_id FROM consultation_records WHERE session_id = ?",
            (session2.session_id,),
        )
        row2 = await cursor2.fetchone()
        assert row2["patient_id"] == row["patient_id"], (
            f"相同病患應指向相同 patient_id，session1={row['patient_id']}, session2={row2['patient_id']}"
        )

        # 驗證 patient_records 只有一筆
        cursor3 = await test_db.execute(
            "SELECT COUNT(*) FROM patient_records WHERE name = ?", ("自動關聯病患",)
        )
        row3 = await cursor3.fetchone()
        assert row3[0] == 1, f"病患記錄不應重複，實際 {row3[0]} 筆"

    @pytest.mark.asyncio
    async def test_empty_patient_name_uses_default(self, test_db, session_manager_with_db):
        """驗證空白病患名稱使用預設值「未知病患」"""
        sm = session_manager_with_db
        session = sm.create_session(patient_context={})
        result = _make_fake_result(
            session_id=session.session_id,
            patient_context={},
        )
        sm.complete_session(session.session_id, result)
        await sm._save_to_sqlite(session)

        cursor = await test_db.execute(
            "SELECT patient_name FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["patient_name"] == "未知病患"

        # 驗證 patient_records 有「未知病患」記錄
        cursor2 = await test_db.execute(
            "SELECT COUNT(*) FROM patient_records WHERE name = ?", ("未知病患",)
        )
        row2 = await cursor2.fetchone()
        assert row2[0] == 1


# ── TestGracefulDegradation ──────────────────────────────────────


class TestGracefulDegradation:
    """驗證 SQLite 寫入失敗不影響其他流程"""

    @pytest.mark.asyncio
    async def test_missing_metadata_fields_handled(
        self, test_db, session_manager_with_db
    ):
        """驗證 metadata 缺欄位時使用預設值，不回傳例外"""
        sm = session_manager_with_db
        session = sm.create_session({"name": "缺欄位病患"})

        # 建立 metadata 缺少部分欄位的 result
        summary = SessionSummary(
            session_id=session.session_id,
            patient_context={"name": "缺欄位病患"},
            transcript="測試",
            segments=[],
            duration_seconds=5.0,
            icd10_codes=[],
            drug_recommendations=[],
            medical_orders=[],
            created_at=datetime.now(),
        )
        result = ConsultationResult(
            session_id=session.session_id,
            soap={"S": "test"},
            session_summary=summary,
            metadata={},  # 全部欄位為空
            processing_time_ms=100.0,
        )

        sm.complete_session(session.session_id, result)
        saved = await sm._save_to_sqlite(session)
        assert saved is True

        cursor = await test_db.execute(
            "SELECT asr_model, asr_time_ms, llm_model, llm_time_ms, audio_file_path, audio_duration_ms "
            "FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        assert row["asr_model"] == "", "預設應為空字串"
        assert row["asr_time_ms"] == 0, "預設應為 0"
        assert row["llm_model"] == ""
        assert row["llm_time_ms"] == 0
        assert row["audio_file_path"] == ""
        assert row["audio_duration_ms"] == 0


class TestWebSocketSOAPStorage:
    """驗證 WebSocket 路徑 SOAP 儲存（gap closure）"""

    @pytest.mark.asyncio
    async def test_websocket_soap_storage(self, test_db, session_manager_with_db):
        """驗證 WebSocket generate_soap 動作儲存 SOAP 記錄至 SQLite

        模擬 WebSocket handler 邏輯：
        1. flow.generate_soap() 生成結果
        2. session_manager.complete_session() 保存 JSON
        3. session_manager._save_to_sqlite() 寫入 SQLite
        """
        sm = session_manager_with_db
        session = sm.create_session({"name": "WebSocket 測試病患", "doctor_name": "李醫師"})

        # 模擬 flow.generate_soap() 結果
        result = _make_fake_result(
            session_id=session.session_id,
            transcript="咳嗽一週，有痰，呼吸困難",
            soap={
                "S": "患者主訴咳嗽一週，有痰，呼吸困難",
                "O": "體溫 37.5°C，心率 88 bpm",
                "A": "支氣管炎",
                "P": "開立抗生素處方",
            },
        )

        # WebSocket handler 邏輯：complete_session + _save_to_sqlite
        sm.complete_session(session.session_id, result)
        session_after_complete = sm.get_session(session.session_id)
        assert session_after_complete is not None
        assert session_after_complete.result is not None

        # 呼叫 _save_to_sqlite（與 REST 端點相同的邏輯）
        saved = await sm._save_to_sqlite(session_after_complete)
        assert saved is True, "WebSocket SOAP 應該成功寫入 SQLite"

        # 驗證 consultation_records 表含新記錄
        cursor = await test_db.execute(
            "SELECT session_id, patient_name, soap_json, doctor_name, status "
            "FROM consultation_records WHERE session_id = ?",
            (session.session_id,),
        )
        row = await cursor.fetchone()
        assert row is not None, "WebSocket SOAP 記錄應在 consultation_records 中"
        assert row["patient_name"] == "WebSocket 測試病患"
        assert row["doctor_name"] == "李醫師"
        assert row["status"] == "completed"

        # 驗證 SOAP 內容正確
        soap_json = json.loads(row["soap_json"])
        assert soap_json["S"] == "患者主訴咳嗽一週，有痰，呼吸困難"
        assert soap_json["A"] == "支氣管炎"
        assert soap_json["O"] == "體溫 37.5°C，心率 88 bpm"
        assert soap_json["P"] == "開立抗生素處方"
