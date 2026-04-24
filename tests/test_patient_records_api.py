"""
病患記錄 REST API 整合測試

測試範圍：
- 搜尋端點（姓名關鍵字、日期範圍、組合條件、分頁）
- 單筆記錄瀏覽端點（完整記錄、404）
- 審計追蹤端點（審計記錄列表、欄位完整性）
- SOAP 修改端點（修改驗證、審計追蹤 before/after 值）

測試策略：直接呼叫 async handler 函式（非透過 FastAPI TestClient），
因為 handlers 依賴 aiosqlite 全域單例，而 TestClient 的 lifespan 無法
在測試環境中正確管理 async DB 連線。
"""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

from src.db.patient_records_db import (
    close_patient_records_db,
    get_patient_records_db,
    init_schema,
    save_consultation_record,
    set_db_path_for_test,
    get_audit_log,
    amend_soap,
)
from src.api.patient_records_api import (
    search_records,
    get_record,
    get_record_audit,
    amend_record_soap,
    SOAPAmendRequest,
)


@pytest_asyncio.fixture
async def test_db():
    """建立暫時測試資料庫，每個測試前後清理"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_soapvoice_api.db"
        set_db_path_for_test(db_path)
        db = await get_patient_records_db()
        await init_schema(db)
        yield db
        await close_patient_records_db()


@pytest_asyncio.fixture
async def seeded_db(test_db):
    """預先插入 5 筆測試問診記錄，供搜尋測試使用"""
    records = [
        {
            "session_id": f"api-srch{i:04d}",
            "patient_name": pname,
            "doctor_name": "王醫師" if i < 3 else "李醫師",
            "status": "completed",
            "transcript_text": f"測試逐字稿{i}",
            "soap_json": {
                "subjective": f"主訴內容{i}",
                "objective": f"客觀檢查{i}",
                "assessment": f"評估摘要{i}",
                "plan": f"治療計畫{i}",
            },
        }
        for i, pname in enumerate([
            "張三", "張三", "李四", "王五", "張三六",
        ])
    ]
    dates = [
        "2026-04-01 10:00:00",
        "2026-04-15 14:30:00",
        "2026-04-10 09:00:00",
        "2026-03-20 16:00:00",
        "2026-04-20 11:00:00",
    ]
    ids = []
    for rec, date in zip(records, dates):
        rid = await save_consultation_record(rec)
        if rid > 0:
            # 覆蓋 created_at 以確保日期一致性
            await test_db.execute(
                "UPDATE consultation_records SET created_at = ?, status = 'completed' WHERE id = ?",
                (date, rid),
            )
            await test_db.commit()
            ids.append(rid)
    await test_db.commit()
    return ids


class TestSearchAPI:
    """測試搜尋問診記錄端點（PERS-02）"""

    @pytest.mark.asyncio
    async def test_search_by_name_zhang(self, seeded_db, test_db):
        """測試依姓名搜尋「張」應回傳相關記錄"""
        result = await search_records(name="張", date_from="", date_to="", page=1, page_size=20)
        assert result.total >= 2, f"預期至少 2 筆，實際 total={result.total}"
        # 驗證所有回傳記錄的 patient_name 皆含「張」
        for rec in result.records:
            assert "張" in rec.patient_name, f"非預期病患: {rec.patient_name}"

    @pytest.mark.asyncio
    async def test_search_by_date_range(self, seeded_db, test_db):
        """測試日期範圍篩選（2026-04-01 至 2026-04-30）"""
        result = await search_records(
            name="", date_from="2026-04-01", date_to="2026-04-30", page=1, page_size=20,
        )
        # 應回傳 4 筆（排除 2026-03-20 的王五）
        assert result.total == 4, f"預期 4 筆，實際 total={result.total}"
        for rec in result.records:
            assert "2026-04" in rec.created_at, f"非預期日期: {rec.created_at}"

    @pytest.mark.asyncio
    async def test_search_combined_name_and_date(self, seeded_db, test_db):
        """測試姓名 + 日期範圍組合搜尋"""
        result = await search_records(
            name="張", date_from="2026-04-01", date_to="2026-04-30", page=1, page_size=20,
        )
        # 張三 x2 + 張三六 x1 = 3 筆
        assert result.total == 3, f"預期 3 筆，實際 total={result.total}"

    @pytest.mark.asyncio
    async def test_search_pagination_page2(self, seeded_db, test_db):
        """測試分頁功能（page_size=2, page=2）"""
        result = await search_records(
            name="", date_from="", date_to="", page=2, page_size=2,
        )
        assert result.page == 2, f"預期 page=2，實際 page={result.page}"
        assert result.total_pages == 3, f"預期 total_pages=3，實際 total_pages={result.total_pages}"
        assert len(result.records) <= 2, f"預期 ≤ 2 筆，實際 {len(result.records)} 筆"

    @pytest.mark.asyncio
    async def test_search_no_results(self, seeded_db, test_db):
        """測試無結果搜尋"""
        result = await search_records(
            name="不存在的名字", date_from="", date_to="", page=1, page_size=20,
        )
        assert result.total == 0, f"預期 total=0，實際 total={result.total}"
        assert result.records == [], f"預期空列表，實際 {result.records}"

    @pytest.mark.asyncio
    async def test_search_default_pagination(self, seeded_db, test_db):
        """測試預設分頁參數"""
        result = await search_records(
            name="", date_from="", date_to="", page=1, page_size=20,
        )
        assert result.page_size == 20, f"預期 page_size=20，實際 page_size={result.page_size}"
        assert result.page == 1

    @pytest.mark.asyncio
    async def test_search_results_desc_order(self, seeded_db, test_db):
        """測試搜尋結果依時間倒序排列"""
        result = await search_records(
            name="", date_from="", date_to="", page=1, page_size=20,
        )
        if len(result.records) >= 2:
            # 第一筆應比第二筆更新
            assert result.records[0].created_at >= result.records[1].created_at, \
                f"未依時間倒序排列: {result.records[0].created_at} < {result.records[1].created_at}"


class TestSingleRecordAPI:
    """測試單筆記錄瀏覽端點"""

    @pytest.mark.asyncio
    async def test_get_record_by_id(self, seeded_db, test_db):
        """測試取得存在的記錄應回傳完整內容"""
        record_id = seeded_db[0]
        record = await get_record(record_id)
        assert record is not None
        assert record["id"] == record_id
        assert record["patient_name"] == "張三"
        assert "transcript_text" in record, "應含 transcript_text"
        assert "soap_json" in record, "應含 soap_json"

    @pytest.mark.asyncio
    async def test_get_record_404(self, test_db):
        """測試不存在的記錄回傳 HTTP 404"""
        import fastapi
        with pytest.raises(fastapi.HTTPException) as exc_info:
            await get_record(99999)
        assert exc_info.value.status_code == 404
        assert "不存在" in exc_info.value.detail


class TestAuditAPI:
    """測試審計追蹤端點（PERS-01）"""

    @pytest.mark.asyncio
    async def test_get_audit_log_with_entries(self, seeded_db, test_db):
        """測試取得含審計記錄的追蹤列表"""
        record_id = seeded_db[0]
        # 先修改 SOAP 以產生審計記錄
        await amend_soap(record_id, {"subjective": "修改後主訴", "assessment": "修改後評估"}, "醫師A")

        response = await get_record_audit(record_id)
        assert response["record_id"] == record_id
        assert response["total"] >= 1, f"預期至少 1 筆審計，實際 {response['total']} 筆"
        audit_logs = response["audit_logs"]
        assert len(audit_logs) >= 1

        # 驗證審計記錄結構
        log = audit_logs[0]
        assert "action" in log
        assert "user_id" in log
        assert "action_timestamp" in log
        assert "before_value" in log or log.get("before_value") is None
        assert "after_value" in log or log.get("after_value") is None

    @pytest.mark.asyncio
    async def test_get_audit_log_404_for_nonexistent(self, test_db):
        """測試不存在的記錄審計追蹤回傳 404"""
        import fastapi
        with pytest.raises(fastapi.HTTPException) as exc_info:
            await get_record_audit(99999)
        assert exc_info.value.status_code == 404


class TestAmendSOAPAPI:
    """測試 SOAP 病歷修改端點（PERS-01 審計追蹤）"""

    @pytest.mark.asyncio
    async def test_amend_soap_success(self, seeded_db, test_db):
        """測試成功修改 SOAP 病歷"""
        record_id = seeded_db[0]
        result = await amend_record_soap(
            record_id,
            SOAPAmendRequest(
                soap={"subjective": "修改後主訴", "assessment": "修改後評估"},
                user_id="測試醫師",
            ),
        )
        assert result.status == "amended"
        assert result.record_id == record_id

    @pytest.mark.asyncio
    async def test_amend_soap_verify_updated_record(self, seeded_db, test_db):
        """測試修改後 GET 記錄回傳更新後的 SOAP"""
        record_id = seeded_db[1]
        new_soap = {"subjective": "新主訴", "assessment": "新評估"}

        await amend_record_soap(
            record_id,
            SOAPAmendRequest(soap=new_soap, user_id="醫師B"),
        )
        updated = await get_record(record_id)
        assert updated["soap_json"] == new_soap, \
            f"預期 {new_soap}，實際 {updated['soap_json']}"

    @pytest.mark.asyncio
    async def test_amend_soap_creates_audit_trail(self, seeded_db, test_db):
        """測試修改 SOAP 後審計記錄含 before/after 值"""
        record_id = seeded_db[2]
        new_soap = {"subjective": "第三次修改", "assessment": "第三次評估"}

        await amend_record_soap(
            record_id,
            SOAPAmendRequest(soap=new_soap, user_id="醫師C"),
        )
        logs = await get_audit_log(record_id)
        amend_logs = [log for log in logs if log["action"] == "AMEND"]
        assert len(amend_logs) >= 1, "應有至少 1 筆 AMEND 審計記錄"

        amend = amend_logs[0]
        assert amend["user_id"] == "醫師C"
        assert amend["before_value"] is not None, "應有 before_value"
        assert amend["after_value"] is not None, "應有 after_value"
        assert "第三次修改" in amend["after_value"]

    @pytest.mark.asyncio
    async def test_amend_soap_404_for_nonexistent(self, test_db):
        """測試修改不存在的記錄回傳 404"""
        import fastapi
        with pytest.raises(fastapi.HTTPException) as exc_info:
            await amend_record_soap(
                99999,
                SOAPAmendRequest(soap={"test": True}, user_id="醫師D"),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_amend_soap_audit_immutable(self, seeded_db, test_db):
        """測試 SOAP 修改不可逆：before_value 保留原始值"""
        record_id = seeded_db[0]
        # 第一次修改
        await amend_record_soap(
            record_id,
            SOAPAmendRequest(soap={"subjective": "第一次修改"}, user_id="醫師E"),
        )
        # 第二次修改
        await amend_record_soap(
            record_id,
            SOAPAmendRequest(soap={"subjective": "第二次修改"}, user_id="醫師F"),
        )

        logs = await get_audit_log(record_id)
        amend_logs = [log for log in logs if log["action"] == "AMEND"]
        assert len(amend_logs) == 2, f"應有 2 筆 AMEND 記錄，實際 {len(amend_logs)} 筆"
        # 第一筆的 after 應為第一次修改的值
        assert "第一次修改" in amend_logs[0]["after_value"]
        # 第二筆的 before 應含第一次修改的值
        assert "第一次修改" in amend_logs[1]["before_value"]
        assert "第二次修改" in amend_logs[1]["after_value"]
