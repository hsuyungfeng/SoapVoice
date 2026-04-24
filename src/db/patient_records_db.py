"""
病患記錄持久層模組 — aiosqlite 連線管理、Schema 初始化、CRUD 函式庫

管理 soapvoice_records.db 的完整生命週期：
- 延遲初始化連線單例（WAL 模式、busy_timeout、foreign_keys）
- 四張核心表的自動建表（冪等性）
- 病患記錄、問診記錄、審計追蹤的完整 CRUD 操作

用途：Phase 10 資料持久層的基礎模組，所有後續儲存、搜尋、審計功能依賴於此。
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

# ── 模組層級單例 ──────────────────────────────────────────────

_db: Optional[aiosqlite.Connection] = None
_db_path: Path = Path("data/local_db/soapvoice_records.db")
_write_lock = asyncio.Lock()


# ── 連線管理 ──────────────────────────────────────────────────


async def get_patient_records_db() -> aiosqlite.Connection:
    """取得病患記錄資料庫連線（async singleton）

    延遲初始化連線，設定 WAL 模式、NORMAL synchronous、busy_timeout=5000ms、
    foreign_keys=ON，並回傳可供所有協程共用的單一 aiosqlite 連線。

    Returns:
        已設定 PRAGMA 的 aiosqlite.Connection

    Raises:
        無 — 失敗時記錄 warning 並回傳 None
    """
    global _db
    if _db is None:
        try:
            _db_path.parent.mkdir(parents=True, exist_ok=True)
            _db = await aiosqlite.connect(str(_db_path))
            _db.row_factory = aiosqlite.Row
            await _db.execute("PRAGMA journal_mode=WAL")
            await _db.execute("PRAGMA synchronous=NORMAL")
            await _db.execute("PRAGMA busy_timeout=5000")
            await _db.execute("PRAGMA foreign_keys=ON")
            logger.info(f"病患記錄資料庫已連線: {_db_path} (WAL mode, busy_timeout=5000ms)")
        except Exception as e:
            logger.warning(f"病患記錄資料庫連線失敗: {e}")
            _db = None
            raise
    return _db


async def close_patient_records_db():
    """關閉資料庫連線（在 FastAPI lifespan shutdown 中呼叫）

    關閉全域單例連線並設為 None，釋放資源。
    """
    global _db
    if _db is not None:
        try:
            await _db.close()
            logger.info("病患記錄資料庫已關閉")
        except Exception as e:
            logger.warning(f"病患記錄資料庫關閉失敗: {e}")
        finally:
            _db = None


def set_db_path_for_test(path: Path):
    """測試輔助：設定測試用資料庫路徑並重置連線

    Args:
        path: 測試用資料庫檔案路徑（可為 :memory: 或 tmp_path）
    """
    global _db_path, _db
    _db_path = Path(path)
    _db = None


# ── Schema 初始化 ──────────────────────────────────────────────


async def init_schema(db: aiosqlite.Connection):
    """初始化資料庫 Schema（idempotent — 可重複執行）

    建立四張核心表：
    - patient_records：病患基本資料
    - consultation_records：每次問診記錄（核心表）
    - soap_audit_log：不可變審計追蹤
    - schema_version：Schema 版本管理

    Args:
        db: aiosqlite 連線（由 get_patient_records_db() 提供）
    """
    # ── patient_records ──
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS patient_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            gender      TEXT CHECK(gender IN ('M','F','Other')) DEFAULT NULL,
            birth_date  TEXT DEFAULT NULL,
            medical_id  TEXT DEFAULT NULL,
            notes       TEXT DEFAULT '',
            created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            created_by  TEXT NOT NULL DEFAULT 'system'
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_patient_name ON patient_records(name)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_patient_medical_id ON patient_records(medical_id)"
    )

    # ── consultation_records ──
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS consultation_records (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id        TEXT UNIQUE NOT NULL,
            patient_id        INTEGER DEFAULT NULL,
            patient_name      TEXT NOT NULL,
            doctor_name       TEXT DEFAULT '',
            clinic_name       TEXT DEFAULT '',
            audio_file_path   TEXT DEFAULT NULL,
            audio_duration_ms INTEGER DEFAULT 0,
            audio_format      TEXT DEFAULT 'wav',
            transcript_text   TEXT DEFAULT '',
            transcript_segments_json TEXT DEFAULT '[]',
            soap_json         TEXT DEFAULT '{}',
            status            TEXT NOT NULL DEFAULT 'draft'
                              CHECK(status IN ('draft','completed','cancelled')),
            asr_model         TEXT DEFAULT '',
            asr_time_ms       INTEGER DEFAULT 0,
            llm_model         TEXT DEFAULT '',
            llm_time_ms       INTEGER DEFAULT 0,
            total_time_ms     INTEGER DEFAULT 0,
            created_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            created_by        TEXT NOT NULL DEFAULT 'system',
            updated_at        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (patient_id) REFERENCES patient_records(id) ON DELETE SET NULL
        )
        """
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_consultation_patient_name "
        "ON consultation_records(patient_name)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_consultation_created_at "
        "ON consultation_records(created_at)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_consultation_session_id "
        "ON consultation_records(session_id)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_consultation_status ON consultation_records(status)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_consultation_name_date "
        "ON consultation_records(patient_name, created_at)"
    )

    # ── soap_audit_log ──
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS soap_audit_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id       INTEGER NOT NULL,
            action          TEXT NOT NULL
                            CHECK(action IN ('CREATE','VIEW','AMEND','EXPORT','DELETE')),
            user_id         TEXT NOT NULL DEFAULT 'system',
            action_timestamp TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            before_value    TEXT DEFAULT NULL,
            after_value     TEXT DEFAULT NULL,
            user_agent      TEXT DEFAULT '',
            ip_address      TEXT DEFAULT '',
            FOREIGN KEY (record_id) REFERENCES consultation_records(id) ON DELETE CASCADE
        )
        """
    )
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_record_id ON soap_audit_log(record_id)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_action ON soap_audit_log(action)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON soap_audit_log(action_timestamp)")
    await db.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON soap_audit_log(user_id)")

    # ── schema_version ──
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            description TEXT NOT NULL
        )
        """
    )

    # 寫入初始版本記錄（若不存在）
    cursor = await db.execute("SELECT COUNT(*) FROM schema_version WHERE version = 1")
    row = await cursor.fetchone()
    if row and row[0] == 0:
        await db.execute(
            "INSERT INTO schema_version (version, description) VALUES (?, ?)",
            (1, "Initial schema: patient_records, consultation_records, soap_audit_log, schema_version"),
        )

    await db.commit()
    logger.info("Schema 初始化完成（4 張表，idempotent）")


async def verify_schema(db: aiosqlite.Connection) -> Dict[str, bool]:
    """驗證四張表是否存在

    Args:
        db: aiosqlite 連線

    Returns:
        表名→存在與否的字典
    """
    expected = {"patient_records", "consultation_records", "soap_audit_log", "schema_version"}
    result: Dict[str, bool] = {}
    for table in expected:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        )
        row = await cursor.fetchone()
        result[table] = row is not None
    return result


# ── 輔助函式 ──────────────────────────────────────────────────


def _row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
    """將 aiosqlite.Row 轉換為 dict"""
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


# ── CRUD: 病患記錄 ───────────────────────────────────────────


async def save_patient_record(patient_data: dict) -> int:
    """新增或取得病患記錄（INSERT OR IGNORE 防重複）

    使用 name + medical_id 組合辨識重複。

    Args:
        patient_data: 至少含 `name` 欄位的病患資料字典

    Returns:
        新增的 id 或已存在的 id（透過二次查詢取得）
    """
    try:
        db = await get_patient_records_db()
        name = patient_data.get("name", "")
        if not name:
            logger.warning("save_patient_record: name 為空，略過")
            return 0

        medical_id = patient_data.get("medical_id", "")
        gender = patient_data.get("gender")
        birth_date = patient_data.get("birth_date")
        notes = patient_data.get("notes", "")
        created_by = patient_data.get("created_by", "system")

        async with _write_lock:
            cursor = await db.execute(
                """INSERT OR IGNORE INTO patient_records
                   (name, gender, birth_date, medical_id, notes, created_by)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, gender, birth_date, medical_id, notes, created_by),
            )
            await db.commit()
            if cursor.lastrowid and cursor.lastrowid > 0:
                logger.info(f"新增病患記錄: {name} (id={cursor.lastrowid})")
                return cursor.lastrowid

            # INSERT OR IGNORE 未插入新列 → 查詢已存在的 id
            cursor2 = await db.execute(
                "SELECT id FROM patient_records WHERE name = ? AND medical_id = ?",
                (name, medical_id),
            )
            row = await cursor2.fetchone()
            if row:
                logger.debug(f"病患記錄已存在: {name} (id={row['id']})")
                return row["id"]
            return 0
    except Exception as e:
        logger.warning(f"save_patient_record 失敗: {e}")
        return 0


async def get_or_create_patient(name: str) -> int:
    """依姓名查詢 patient_id，不存在則自動建立

    Args:
        name: 病患姓名

    Returns:
        patient_records.id（成功）或 0（失敗）
    """
    try:
        db = await get_patient_records_db()
        cursor = await db.execute(
            "SELECT id FROM patient_records WHERE name = ? LIMIT 1", (name,)
        )
        row = await cursor.fetchone()
        if row:
            return row["id"]
        # 不存在 → 自動建立
        return await save_patient_record({"name": name})
    except Exception as e:
        logger.warning(f"get_or_create_patient 失敗: {e}")
        return 0


# ── CRUD: 問診記錄 ────────────────────────────────────────────


async def save_consultation_record(record_data: dict) -> int:
    """安全寫入問診記錄（WAL + busy_timeout + 寫入鎖）

    Args:
        record_data: 問診記錄字典，至少需含 session_id、patient_name

    Returns:
        新增記錄的 id（成功）或 0（失敗）
    """
    try:
        db = await get_patient_records_db()
        async with _write_lock:
            cursor = await db.execute(
                """INSERT INTO consultation_records
                   (session_id, patient_id, patient_name, doctor_name, clinic_name,
                    audio_file_path, audio_duration_ms, audio_format,
                    transcript_text, transcript_segments_json,
                    soap_json, status,
                    asr_model, asr_time_ms, llm_model, llm_time_ms, total_time_ms,
                    created_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record_data.get("session_id", ""),
                    record_data.get("patient_id"),
                    record_data.get("patient_name", ""),
                    record_data.get("doctor_name", ""),
                    record_data.get("clinic_name", ""),
                    record_data.get("audio_file_path"),
                    record_data.get("audio_duration_ms", 0),
                    record_data.get("audio_format", "wav"),
                    record_data.get("transcript_text", ""),
                    record_data.get("transcript_segments_json", "[]"),
                    json.dumps(record_data.get("soap_json", {}), ensure_ascii=False),
                    record_data.get("status", "draft"),
                    record_data.get("asr_model", ""),
                    record_data.get("asr_time_ms", 0),
                    record_data.get("llm_model", ""),
                    record_data.get("llm_time_ms", 0),
                    record_data.get("total_time_ms", 0),
                    record_data.get("created_by", "system"),
                ),
            )
            await db.commit()
            row_id = cursor.lastrowid
            logger.info(
                f"寫入問診記錄: session_id={record_data.get('session_id')}, "
                f"patient={record_data.get('patient_name')}, id={row_id}"
            )
            return row_id or 0
    except aiosqlite.IntegrityError as e:
        logger.warning(f"save_consultation_record UNIQUE 約束違反（session_id 重複）: {e}")
        return 0
    except Exception as e:
        logger.warning(f"save_consultation_record 失敗: {e}")
        return 0


async def get_consultation_by_id(record_id: int) -> Optional[Dict[str, Any]]:
    """依 ID 查詢單筆完整問診記錄

    Args:
        record_id: consultation_records.id

    Returns:
        問診記錄 dict（成功）或 None（失敗/無記錄）
    """
    try:
        db = await get_patient_records_db()
        cursor = await db.execute(
            """SELECT id, session_id, patient_id, patient_name, doctor_name, clinic_name,
                      audio_file_path, audio_duration_ms, audio_format,
                      transcript_text, transcript_segments_json,
                      soap_json, status,
                      asr_model, asr_time_ms, llm_model, llm_time_ms, total_time_ms,
                      created_at, created_by, updated_at
               FROM consultation_records
               WHERE id = ?""",
            (record_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    except Exception as e:
        logger.warning(f"get_consultation_by_id 失敗: {e}")
        return None


async def search_consultation_records(
    name: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """搜尋問診記錄（支援姓名 + 日期範圍 + 分頁）

    只搜尋 status='completed' 的記錄。姓名使用 LIKE 模糊比對，
    日期範圍使用字串比較（created_at 格式為 YYYY-MM-DD HH:MM:SS）。

    Args:
        name: 病患姓名關鍵字（選填，LIKE %keyword%）
        date_from: 開始日期（選填，格式 YYYY-MM-DD）
        date_to: 結束日期（選填，格式 YYYY-MM-DD）
        page: 頁碼（1-indexed）
        page_size: 每頁筆數

    Returns:
        {total, page, page_size, total_pages, records}
    """
    try:
        db = await get_patient_records_db()

        # 建構 WHERE 子句
        conditions = ["status = 'completed'"]
        params: list = []

        if name:
            conditions.append("patient_name LIKE ?")
            params.append(f"%{name}%")

        if date_from:
            conditions.append("created_at >= ?")
            params.append(f"{date_from} 00:00:00")

        if date_to:
            conditions.append("created_at <= ?")
            params.append(f"{date_to} 23:59:59")

        where_clause = " AND ".join(conditions)

        # 計算總數
        count_sql = f"SELECT COUNT(*) FROM consultation_records WHERE {where_clause}"
        cursor = await db.execute(count_sql, params)
        row = await cursor.fetchone()
        total = row[0] if row else 0

        # 分頁查詢
        offset = (page - 1) * page_size
        query_sql = f"""
            SELECT id, session_id, patient_id, patient_name, doctor_name,
                   audio_file_path, audio_duration_ms,
                   transcript_text, soap_json,
                   status, asr_model, asr_time_ms, llm_model, llm_time_ms,
                   total_time_ms, created_at, created_by
            FROM consultation_records
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor = await db.execute(query_sql, params + [page_size, offset])
        rows = await cursor.fetchall()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
            "records": [_row_to_dict(r) for r in rows],
        }
    except Exception as e:
        logger.warning(f"search_consultation_records 失敗: {e}")
        return {"total": 0, "page": page, "page_size": page_size, "total_pages": 0, "records": []}


# ── CRUD: 審計追蹤 ────────────────────────────────────────────


async def save_audit_log(
    record_id: int,
    action: str,
    user_id: str = "system",
    before_value: Optional[str] = None,
    after_value: Optional[str] = None,
) -> int:
    """寫入審計記錄

    Args:
        record_id: 對應的 consultation_records.id
        action: 操作類型（CREATE/VIEW/AMEND/EXPORT/DELETE）
        user_id: 操作者 ID
        before_value: 修改前的值（AMEND 時使用）
        after_value: 修改後的值（AMEND 時使用）

    Returns:
        新增審計記錄的 id（成功）或 0（失敗）
    """
    try:
        db = await get_patient_records_db()
        async with _write_lock:
            cursor = await db.execute(
                """INSERT INTO soap_audit_log
                   (record_id, action, user_id, before_value, after_value)
                   VALUES (?, ?, ?, ?, ?)""",
                (record_id, action, user_id, before_value, after_value),
            )
            await db.commit()
            logger.info(f"審計記錄: record_id={record_id}, action={action}, user={user_id}")
            return cursor.lastrowid or 0
    except Exception as e:
        logger.warning(f"save_audit_log 失敗: {e}")
        return 0


async def get_audit_log(record_id: int) -> List[Dict[str, Any]]:
    """查詢特定記錄的所有審計記錄

    Args:
        record_id: consultation_records.id

    Returns:
        審計記錄 dict 列表（依時間遞增排序）
    """
    try:
        db = await get_patient_records_db()
        cursor = await db.execute(
            """SELECT id, record_id, action, user_id, action_timestamp,
                      before_value, after_value, user_agent, ip_address
               FROM soap_audit_log
               WHERE record_id = ?
               ORDER BY action_timestamp ASC""",
            (record_id,),
        )
        rows = await cursor.fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        logger.warning(f"get_audit_log 失敗: {e}")
        return []


async def amend_soap(record_id: int, new_soap: dict, user_id: str) -> bool:
    """修改 SOAP 病歷（含完整審計追蹤）

    1. 讀取現有 SOAP
    2. 寫入審計記錄（含 before_value 和 after_value）
    3. UPDATE soap_json + updated_at

    全程在 _write_lock 內執行，確保原子性。

    Args:
        record_id: consultation_records.id
        new_soap: 新的 SOAP dict
        user_id: 操作者 ID

    Returns:
        True（成功）或 False（失敗）
    """
    try:
        db = await get_patient_records_db()
        new_soap_str = json.dumps(new_soap, ensure_ascii=False)

        async with _write_lock:
            # 1. 讀取現有 SOAP
            cursor = await db.execute(
                "SELECT soap_json FROM consultation_records WHERE id = ?",
                (record_id,),
            )
            row = await cursor.fetchone()
            if not row:
                logger.warning(f"amend_soap: record_id={record_id} 不存在")
                return False
            old_soap_str = row["soap_json"] or "{}"

            # 2. 寫入審計記錄
            await db.execute(
                """INSERT INTO soap_audit_log
                   (record_id, action, user_id, before_value, after_value)
                   VALUES (?, 'AMEND', ?, ?, ?)""",
                (record_id, user_id, old_soap_str, new_soap_str),
            )

            # 3. 更新 SOAP
            await db.execute(
                """UPDATE consultation_records
                   SET soap_json = ?, updated_at = datetime('now', 'localtime')
                   WHERE id = ?""",
                (new_soap_str, record_id),
            )
            await db.commit()
            logger.info(f"SOAP 已修改: record_id={record_id}, user={user_id}")
            return True
    except Exception as e:
        logger.warning(f"amend_soap 失敗: {e}")
        return False


# ── 模組匯出概覽 ──────────────────────────────────────────────

__all__ = [
    "get_patient_records_db",
    "close_patient_records_db",
    "set_db_path_for_test",
    "init_schema",
    "verify_schema",
    "save_patient_record",
    "get_or_create_patient",
    "save_consultation_record",
    "get_consultation_by_id",
    "search_consultation_records",
    "save_audit_log",
    "get_audit_log",
    "amend_soap",
]
