"""
病患記錄資料庫模組單元測試

測試範圍：
- Schema 初始化（冪等性、四張表驗證、WAL 模式）
- 病患記錄 CRUD（新增、去重複）
- 問診記錄 CRUD（寫入、UNIQUE 約束、搜尋、分頁）
- 審計追蹤（寫入、查詢、SOAP 修改含 before/after 值）
- 並行寫入（無 SQLITE_BUSY 錯誤）
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from src.db.patient_records_db import (
    close_patient_records_db,
    get_patient_records_db,
    init_schema,
    verify_schema,
    save_patient_record,
    get_or_create_patient,
    save_consultation_record,
    get_consultation_by_id,
    search_consultation_records,
    save_audit_log,
    get_audit_log,
    amend_soap,
    set_db_path_for_test,
)


@pytest_asyncio.fixture
async def test_db():
    """建立暫時測試資料庫，每個測試前後清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_soapvoice.db"
        set_db_path_for_test(db_path)
        db = await get_patient_records_db()
        await init_schema(db)
        yield db
        await close_patient_records_db()


class TestSchemaInit:
    """測試 Schema 初始化功能"""

    @pytest.mark.asyncio
    async def test_init_schema_creates_four_tables(self, test_db):
        """驗證 init_schema 建立四張核心表"""
        tables = await verify_schema(test_db)
        assert tables["patient_records"] is True, "patient_records 表不存在"
        assert tables["consultation_records"] is True, "consultation_records 表不存在"
        assert tables["soap_audit_log"] is True, "soap_audit_log 表不存在"
        assert tables["schema_version"] is True, "schema_version 表不存在"

    @pytest.mark.asyncio
    async def test_init_schema_idempotent(self, test_db):
        """驗證 init_schema 可重複執行不報錯"""
        # 第二次呼叫不應拋出例外
        await init_schema(test_db)
        tables = await verify_schema(test_db)
        assert all(tables.values()), "重複初始化後表格不完整"

    @pytest.mark.asyncio
    async def test_wal_journal_mode_enabled(self, test_db):
        """驗證 WAL journal_mode 已啟用（檔案式 DB）"""
        cursor = await test_db.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0] == "wal", f"預期 wal，實際為 {row[0]}"

    @pytest.mark.asyncio
    async def test_busy_timeout_set(self, test_db):
        """驗證 busy_timeout 設定為 5000ms"""
        cursor = await test_db.execute("PRAGMA busy_timeout")
        row = await cursor.fetchone()
        assert row[0] == 5000, f"預期 busy_timeout=5000，實際為 {row[0]}"

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self, test_db):
        """驗證 foreign_keys 已啟用"""
        cursor = await test_db.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row[0] == 1, "foreign_keys 未啟用"


class TestSavePatient:
    """測試病患記錄寫入"""

    @pytest.mark.asyncio
    async def test_save_new_patient(self, test_db):
        """測試新增病患記錄"""
        pid = await save_patient_record({
            "name": "張三",
            "gender": "M",
            "birth_date": "1980-01-15",
            "medical_id": "HIS-001",
        })
        assert pid > 0, f"預期 pid > 0，實際為 {pid}"

        record = await get_consultation_by_id(pid)
        # pid 指向 patient_records，另須直接查詢
        cursor = await test_db.execute("SELECT name, gender FROM patient_records WHERE id = ?", (pid,))
        row = await cursor.fetchone()
        assert row["name"] == "張三"
        assert row["gender"] == "M"

    @pytest.mark.asyncio
    async def test_duplicate_patient_not_created(self, test_db):
        """測試重複病患名稱不建立重複記錄"""
        pid1 = await save_patient_record({"name": "李四", "medical_id": "HIS-002"})
        pid2 = await save_patient_record({"name": "李四", "medical_id": "HIS-002"})
        assert pid1 > 0
        assert pid2 == pid1, f"重複病患應回傳相同 id，pid1={pid1}, pid2={pid2}"

        # 驗證只有一筆記錄
        cursor = await test_db.execute(
            "SELECT COUNT(*) FROM patient_records WHERE name = ? AND medical_id = ?",
            ("李四", "HIS-002"),
        )
        row = await cursor.fetchone()
        assert row[0] == 1, f"預期 1 筆記錄，實際 {row[0]} 筆"

    @pytest.mark.asyncio
    async def test_get_or_create_patient_new(self, test_db):
        """測試 get_or_create_patient 自動建立新病患"""
        pid = await get_or_create_patient("王五")
        assert pid > 0
        cursor = await test_db.execute("SELECT name FROM patient_records WHERE id = ?", (pid,))
        row = await cursor.fetchone()
        assert row["name"] == "王五"

    @pytest.mark.asyncio
    async def test_get_or_create_patient_existing(self, test_db):
        """測試 get_or_create_patient 回傳已存在的病患"""
        pid1 = await save_patient_record({"name": "趙六"})
        pid2 = await get_or_create_patient("趙六")
        assert pid1 == pid2


class TestSaveConsultation:
    """測試問診記錄寫入"""

    @pytest.mark.asyncio
    async def test_save_consultation_record(self, test_db):
        """測試寫入完整問診記錄"""
        rid = await save_consultation_record({
            "session_id": "abc12345",
            "patient_name": "張三",
            "doctor_name": "王醫師",
            "clinic_name": "測試診所",
            "transcript_text": "頭痛三天，有發燒",
            "soap_json": {"subjective": "頭痛三天", "objective": "體溫38.2°C"},
            "status": "completed",
        })
        assert rid > 0, f"預期 rid > 0，實際為 {rid}"

        record = await get_consultation_by_id(rid)
        assert record is not None
        assert record["session_id"] == "abc12345"
        assert record["patient_name"] == "張三"
        assert record["doctor_name"] == "王醫師"
        assert record["status"] == "completed"

    @pytest.mark.asyncio
    async def test_session_id_unique_constraint(self, test_db):
        """測試 session_id UNIQUE 約束"""
        rid1 = await save_consultation_record({
            "session_id": "dup12345",
            "patient_name": "測試病患",
        })
        assert rid1 > 0

        # 相同 session_id 應回傳 0（UNIQUE 約束違反）
        rid2 = await save_consultation_record({
            "session_id": "dup12345",
            "patient_name": "另一個病患",
        })
        assert rid2 == 0, f"重複 session_id 應回傳 0，實際為 {rid2}"


class TestSearchConsultation:
    """測試問診記錄搜尋"""

    @pytest_asyncio.fixture
    async def seeded_db(self, test_db):
        """預先插入 5 筆測試資料"""
        records = [
            {"session_id": f"srch{i:04d}", "patient_name": pname, "status": "completed",
             "created_at": date, "transcript_text": f"test{i}"}
            for i, (pname, date) in enumerate([
                ("張三", "2026-04-01 10:00:00"),
                ("張三", "2026-04-15 14:30:00"),
                ("李四", "2026-04-10 09:00:00"),
                ("王五", "2026-03-20 16:00:00"),
                ("張三六", "2026-04-20 11:00:00"),
            ])
        ]
        for rec in records:
            rid = await save_consultation_record(rec)
            if rid > 0:
                # Override created_at with fixed date for test consistency
                await test_db.execute(
                    "UPDATE consultation_records SET created_at = ?, status = 'completed' WHERE id = ?",
                    (rec["created_at"], rid),
                )
                await test_db.commit()
        return test_db

    @pytest.mark.asyncio
    async def test_search_by_name(self, seeded_db):
        """測試姓名搜尋（LIKE 比對）"""
        result = await search_consultation_records(name="張三")
        assert result["total"] == 3, f"搜尋「張三」預期 3 筆，實際 {result['total']} 筆"
        names = [r["patient_name"] for r in result["records"]]
        assert "張三" in names
        assert "張三六" in names

    @pytest.mark.asyncio
    async def test_search_by_date_range(self, seeded_db):
        """測試日期範圍篩選"""
        result = await search_consultation_records(
            date_from="2026-04-01", date_to="2026-04-15"
        )
        assert result["total"] >= 2, f"日期範圍搜尋預期 >=2 筆，實際 {result['total']} 筆"

    @pytest.mark.asyncio
    async def test_search_pagination(self, seeded_db):
        """測試分頁功能"""
        result = await search_consultation_records(page=1, page_size=2)
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert len(result["records"]) <= 2
        assert result["total_pages"] > 0
        assert result["total"] > 0

    @pytest.mark.asyncio
    async def test_search_no_results(self, seeded_db):
        """測試無結果時回傳空列表"""
        result = await search_consultation_records(name="不存在的病患")
        assert result["total"] == 0
        assert result["records"] == []
        assert result["total_pages"] == 1  # 至少 1 頁

    @pytest.mark.asyncio
    async def test_search_only_completed(self, seeded_db):
        """測試只搜尋 status='completed' 的記錄"""
        # 插入一筆 draft 記錄
        await save_consultation_record({
            "session_id": "draft001",
            "patient_name": "草稿病患",
            "status": "draft",
        })
        result = await search_consultation_records(name="草稿病患")
        assert result["total"] == 0, "草稿記錄不應出現在搜尋結果中"


class TestAuditLog:
    """測試審計追蹤功能"""

    @pytest.mark.asyncio
    async def test_save_and_get_audit_log(self, test_db):
        """測試寫入與讀取審計記錄"""
        rid = await save_consultation_record({
            "session_id": "audit001",
            "patient_name": "審計病患",
        })
        assert rid > 0

        aid = await save_audit_log(rid, "CREATE", "醫師A")
        assert aid > 0

        logs = await get_audit_log(rid)
        assert len(logs) == 1
        assert logs[0]["action"] == "CREATE"
        assert logs[0]["user_id"] == "醫師A"

    @pytest.mark.asyncio
    async def test_amend_soap_with_audit(self, test_db):
        """測試 SOAP 修改含完整審計追蹤"""
        original_soap = {"subjective": "原始主訴"}
        rid = await save_consultation_record({
            "session_id": "amend001",
            "patient_name": "修改病患",
            "soap_json": original_soap,
        })
        assert rid > 0

        new_soap = {"subjective": "修改後主訴"}
        success = await amend_soap(rid, new_soap, "醫師B")
        assert success is True

        # 驗證 SOAP 已更新
        record = await get_consultation_by_id(rid)
        assert record is not None
        soap_data = json.loads(record["soap_json"]) if isinstance(record.get("soap_json"), str) else record.get("soap_json")
        assert soap_data == new_soap

        # 驗證審計記錄含 before/after 值
        logs = await get_audit_log(rid)
        assert len(logs) >= 1
        amend_logs = [l for l in logs if l["action"] == "AMEND"]
        assert len(amend_logs) >= 1
        assert amend_logs[0]["user_id"] == "醫師B"
        assert "原始主訴" in amend_logs[0]["before_value"]
        assert "修改後主訴" in amend_logs[0]["after_value"]

    @pytest.mark.asyncio
    async def test_amend_nonexistent_record(self, test_db):
        """測試修改不存在的記錄回傳 False"""
        success = await amend_soap(99999, {"test": True}, "醫師C")
        assert success is False

    @pytest.mark.asyncio
    async def test_get_audit_log_empty(self, test_db):
        """測試無審計記錄時回傳空列表"""
        logs = await get_audit_log(99999)
        assert logs == []


class TestConcurrency:
    """測試並行寫入"""

    @pytest.mark.asyncio
    async def test_concurrent_writes_no_busy(self, test_db):
        """使用 asyncio.gather() 同時寫入 3 筆記錄，驗證無錯誤"""
        async def write_one(sid: str, pname: str):
            return await save_consultation_record({
                "session_id": sid,
                "patient_name": pname,
            })

        results = await asyncio.gather(
            write_one("conc001", "並行1"),
            write_one("conc002", "並行2"),
            write_one("conc003", "並行3"),
        )
        # 全部成功（rid > 0）
        for i, rid in enumerate(results):
            assert rid > 0, f"並行寫入 {i+1} 失敗，rid={rid}"

        # 驗證總記錄數
        cursor = await test_db.execute("SELECT COUNT(*) FROM consultation_records")
        row = await cursor.fetchone()
        assert row[0] == 3, f"預期 3 筆記錄，實際 {row[0]} 筆"

    @pytest.mark.asyncio
    async def test_concurrent_writes_unique_sessions(self, test_db):
        """測試並行寫入不同 session_id 不衝突"""
        async def write_one(sid: str):
            return await save_consultation_record({
                "session_id": sid,
                "patient_name": f"病患{sid}",
            })

        results = await asyncio.gather(*[
            write_one(f"conc_a_{i}") for i in range(5)
        ])
        assert all(r > 0 for r in results), f"部分並行寫入失敗: {results}"
