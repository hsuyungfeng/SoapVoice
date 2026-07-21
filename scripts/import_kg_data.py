"""將 baiyang2464/chatbot-base-on-Knowledge-Graph 的 medical.json 匯入 SoapVoice SQLite

資料來源：https://github.com/baiyang2464/chatbot-base-on-Knowledge-Graph
8,808 筆疾病資料，含 44K 實體、294K 關係（症狀/藥品/食物/檢查/科室）
"""

import json
import sqlite3
import logging
import time
from pathlib import Path
from opencc import OpenCC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = Path("data/local_db/medical.db")
KG_JSON_PATH = Path("data/kg_import/medical.json")

cc = OpenCC("s2t")


def s2t(text: str) -> str:
    """簡體中文→繁體中文"""
    return cc.convert(text) if text else ""


def parse_record(d: dict) -> dict:
    """Parse a single JSON record from the knowledge graph."""
    name = s2t(d.get("name", ""))

    return {
        "name": name,
        "desc": s2t(d.get("desc", "")),
        "cause": s2t(d.get("cause", "")),
        "prevent": s2t(d.get("prevent", "")),
        "cure_way": "、".join(s2t(w) for w in d.get("cure_way", [])),
        "cure_lasttime": d.get("cure_lasttime", ""),
        "cured_prob": d.get("cured_prob", ""),
        "get_prob": d.get("get_prob", ""),
        "cost_money": s2t(d.get("cost_money", "")),
        "yibao_status": d.get("yibao_status", ""),
        "symptoms": [s2t(s) for s in d.get("symptom", [])],
        "acompany": [s2t(a) for a in d.get("acompany", [])],
        "common_drugs": [s2t(dd) for dd in d.get("common_drug", [])],
        "recommand_drugs": [s2t(dd) for dd in d.get("recommand_drug", [])],
        "checks": [s2t(c) for c in d.get("check", [])],
        "departments": [s2t(dp) for dp in d.get("cure_department", [])],
        "do_eat": [s2t(f) for f in d.get("do_eat", [])],
        "not_eat": [s2t(f) for f in d.get("not_eat", [])],
        "recommand_eat": [s2t(f) for f in d.get("recommand_eat", [])],
        "drug_detail": d.get("drug_detail", []),
    }


def create_tables(conn: sqlite3.Connection):
    """Create new tables for knowledge graph data."""
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS disease_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            cause TEXT,
            prevent TEXT,
            cure_way TEXT,
            cure_lasttime TEXT,
            cured_prob TEXT,
            get_prob TEXT,
            cost_money TEXT,
            yibao_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_disease_info_name ON disease_info(name);

        CREATE TABLE IF NOT EXISTS disease_symptoms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_name TEXT NOT NULL,
            symptom_name TEXT NOT NULL,
            FOREIGN KEY (disease_name) REFERENCES disease_info(name)
        );

        CREATE INDEX IF NOT EXISTS idx_ds_disease ON disease_symptoms(disease_name);
        CREATE INDEX IF NOT EXISTS idx_ds_symptom ON disease_symptoms(symptom_name);

        CREATE TABLE IF NOT EXISTS disease_drugs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_name TEXT NOT NULL,
            drug_name TEXT NOT NULL,
            drug_type TEXT NOT NULL DEFAULT 'common',
            FOREIGN KEY (disease_name) REFERENCES disease_info(name)
        );

        CREATE INDEX IF NOT EXISTS idx_dd_disease ON disease_drugs(disease_name);
        CREATE INDEX IF NOT EXISTS idx_dd_drug ON disease_drugs(drug_name);

        CREATE TABLE IF NOT EXISTS disease_foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_name TEXT NOT NULL,
            food_name TEXT NOT NULL,
            food_type TEXT NOT NULL,
            FOREIGN KEY (disease_name) REFERENCES disease_info(name)
        );

        CREATE INDEX IF NOT EXISTS idx_df_disease ON disease_foods(disease_name);
        CREATE INDEX IF NOT EXISTS idx_df_food ON disease_foods(food_name);

        CREATE TABLE IF NOT EXISTS disease_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_name TEXT NOT NULL,
            check_name TEXT NOT NULL,
            FOREIGN KEY (disease_name) REFERENCES disease_info(name)
        );

        CREATE INDEX IF NOT EXISTS idx_dc_disease ON disease_checks(disease_name);
        CREATE INDEX IF NOT EXISTS idx_dc_check ON disease_checks(check_name);

        CREATE TABLE IF NOT EXISTS disease_departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_name TEXT NOT NULL,
            department_name TEXT NOT NULL,
            FOREIGN KEY (disease_name) REFERENCES disease_info(name)
        );

        CREATE INDEX IF NOT EXISTS idx_ddep_disease ON disease_departments(disease_name);

        CREATE TABLE IF NOT EXISTS disease_acompany (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            disease_name TEXT NOT NULL,
            acompany_name TEXT NOT NULL,
            FOREIGN KEY (disease_name) REFERENCES disease_info(name)
        );

        CREATE INDEX IF NOT EXISTS idx_da_disease ON disease_acompany(disease_name);
        CREATE INDEX IF NOT EXISTS idx_da_acompany ON disease_acompany(acompany_name);
    """)

    conn.commit()
    logger.info("Tables created/verified successfully")


def import_data(conn: sqlite3.Connection):
    """Import medical.json into the new tables."""
    cursor = conn.cursor()

    total = 0
    disease_count = 0
    symptom_count = 0
    drug_count = 0
    food_count = 0
    check_count = 0
    dept_count = 0
    acompany_count = 0

    with open(KG_JSON_PATH, "r", encoding="utf-8") as f:
        for line in f:
            total += 1
            d = json.loads(line)
            rec = parse_record(d)

            # Insert disease_info
            try:
                cursor.execute(
                    """INSERT OR IGNORE INTO disease_info
                       (name, description, cause, prevent, cure_way,
                        cure_lasttime, cured_prob, get_prob, cost_money, yibao_status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec["name"], rec["desc"], rec["cause"],
                        rec["prevent"], rec["cure_way"],
                        rec["cure_lasttime"], rec["cured_prob"],
                        rec["get_prob"], rec["cost_money"],
                        rec["yibao_status"],
                    ),
                )
                if cursor.rowcount > 0:
                    disease_count += 1
            except Exception as e:
                logger.warning(f"Error inserting disease {rec['name']}: {e}")

            # Insert symptoms
            for symptom in rec["symptoms"]:
                if symptom:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_symptoms (disease_name, symptom_name) VALUES (?, ?)",
                            (rec["name"], symptom),
                        )
                        symptom_count += cursor.rowcount
                    except Exception:
                        pass

            # Insert drugs (common + recommand)
            for drug in rec["common_drugs"]:
                if drug:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_drugs (disease_name, drug_name, drug_type) VALUES (?, ?, 'common')",
                            (rec["name"], drug),
                        )
                        drug_count += cursor.rowcount
                    except Exception:
                        pass
            for drug in rec["recommand_drugs"]:
                if drug:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_drugs (disease_name, drug_name, drug_type) VALUES (?, ?, 'recommand')",
                            (rec["name"], drug),
                        )
                        drug_count += cursor.rowcount
                    except Exception:
                        pass

            # Insert foods
            for food in rec["do_eat"]:
                if food:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_foods (disease_name, food_name, food_type) VALUES (?, ?, 'do_eat')",
                            (rec["name"], food),
                        )
                        food_count += cursor.rowcount
                    except Exception:
                        pass
            for food in rec["not_eat"]:
                if food:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_foods (disease_name, food_name, food_type) VALUES (?, ?, 'not_eat')",
                            (rec["name"], food),
                        )
                        food_count += cursor.rowcount
                    except Exception:
                        pass
            for food in rec["recommand_eat"]:
                if food:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_foods (disease_name, food_name, food_type) VALUES (?, ?, 'recommand_eat')",
                            (rec["name"], food),
                        )
                        food_count += cursor.rowcount
                    except Exception:
                        pass

            # Insert checks
            for check in rec["checks"]:
                if check:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_checks (disease_name, check_name) VALUES (?, ?)",
                            (rec["name"], check),
                        )
                        check_count += cursor.rowcount
                    except Exception:
                        pass

            # Insert departments
            for dept in rec["departments"]:
                if dept:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_departments (disease_name, department_name) VALUES (?, ?)",
                            (rec["name"], dept),
                        )
                        dept_count += cursor.rowcount
                    except Exception:
                        pass

            # Insert acompany
            for ac in rec["acompany"]:
                if ac:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO disease_acompany (disease_name, acompany_name) VALUES (?, ?)",
                            (rec["name"], ac),
                        )
                        acompany_count += cursor.rowcount
                    except Exception:
                        pass

            if total % 1000 == 0:
                conn.commit()
                logger.info(f"  Progress: {total}/8808 diseases processed")

    conn.commit()

    logger.info(f"\n{'='*50}")
    logger.info("Import complete!")
    logger.info(f"  Diseases:       {disease_count}")
    logger.info(f"  Symptoms:       {symptom_count}")
    logger.info(f"  Drugs:          {drug_count}")
    logger.info(f"  Foods:          {food_count}")
    logger.info(f"  Checks:         {check_count}")
    logger.info(f"  Departments:    {dept_count}")
    logger.info(f"  Acompany:       {acompany_count}")


def verify_data(conn: sqlite3.Connection):
    """Run verification queries."""
    cursor = conn.cursor()

    logger.info(f"\n{'='*50}")
    logger.info("Verification:")
    logger.info(f"{'='*50}")

    for table in [
        "disease_info",
        "disease_symptoms",
        "disease_drugs",
        "disease_foods",
        "disease_checks",
        "disease_departments",
        "disease_acompany",
    ]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        logger.info(f"  {table}: {count:,} records")

    # Sample queries
    logger.info("\n  Sample: disease with most symptoms:")
    cursor.execute("""
        SELECT disease_name, COUNT(*) as cnt
        FROM disease_symptoms
        GROUP BY disease_name
        ORDER BY cnt DESC
        LIMIT 3
    """)
    for row in cursor.fetchall():
        logger.info(f"    {row[0]}: {row[1]} symptoms")

    logger.info("\n  Sample: disease with most drugs:")
    cursor.execute("""
        SELECT disease_name, COUNT(*) as cnt
        FROM disease_drugs
        GROUP BY disease_name
        ORDER BY cnt DESC
        LIMIT 3
    """)
    for row in cursor.fetchall():
        logger.info(f"    {row[0]}: {row[1]} drugs")


def main():
    start = time.time()

    logger.info("Starting KG data import...")
    logger.info(f"Source: {KG_JSON_PATH}")
    logger.info(f"Target: {DB_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA synchronous = OFF")
    conn.execute("PRAGMA journal_mode = MEMORY")

    try:
        create_tables(conn)
        import_data(conn)
        verify_data(conn)
    finally:
        conn.close()

    elapsed = time.time() - start
    logger.info(f"\nTotal time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
