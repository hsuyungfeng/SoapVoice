"""
本地資料庫初始化模組

使用 CurrentData 目錄中的真實資料初始化 SQLite 資料庫

資料來源：
- ICD-10: icd10-data.js (96,802 筆)
- 藥品: 藥品項查詢項目檔260316 AI 摘要支付價大於0.csv (409,804 筆)
- 醫療服務: 醫療服務給付項目NotebookLM1150316.csv (27,287 筆)
- 病例範本: 各种病例规范模板/
"""

import sqlite3
import csv
import json
import logging
import re
from pathlib import Path
from typing import Iterator, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DataSourceConfig:
    """資料來源設定"""

    icd10_path: Path
    drug_csv_path: Path
    orders_csv_path: Path
    case_template_dir: Path
    db_path: Path


class LocalDatabaseInitializer:
    """本地資料庫初始化器"""

    def __init__(self, config: DataSourceConfig):
        self.config = config
        self.batch_size = 1000

    def initialize(self) -> None:
        """初始化所有資料庫"""
        logger.info("=" * 60)
        logger.info("開始初始化本地資料庫")
        logger.info("=" * 60)

        # 建立資料庫目錄
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.config.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

        try:
            # 建立資料表
            logger.info("[1/5] 建立資料表...")
            self._create_tables(conn)

            # 初始化 ICD-10
            logger.info("[2/5] 初始化 ICD-10 資料...")
            self._initialize_icd10(conn)

            # 初始化藥品資料
            logger.info("[3/5] 初始化藥品資料...")
            self._initialize_drugs(conn)

            # 初始化醫療服務
            logger.info("[4/5] 初始化醫療服務資料...")
            self._initialize_medical_orders(conn)

            # 初始化病例範本
            logger.info("[5/5] 初始化病例範本...")
            self._initialize_case_templates(conn)

            # 建立索引
            logger.info("[額外] 建立搜尋索引...")
            self._create_indexes(conn)

            conn.commit()
            logger.info("=" * 60)
            logger.info("資料庫初始化完成！")
            logger.info("=" * 60)

        except Exception as e:
            conn.rollback()
            logger.error(f"資料庫初始化失敗: {e}")
            raise
        finally:
            conn.close()

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        """建立資料表"""
        cursor = conn.cursor()

        # ICD-10 資料表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS icd10_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(10) NOT NULL UNIQUE,
                name_en VARCHAR(500),
                name_cn VARCHAR(500),
                category VARCHAR(100),
                parent_code VARCHAR(10),
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 藥品資料表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS drugs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drug_code VARCHAR(20) NOT NULL UNIQUE,
                atc_code VARCHAR(20),
                drug_name_cn VARCHAR(500),
                drug_name_en VARCHAR(500),
                drug_class VARCHAR(200),
                dosage_form VARCHAR(100),
                ingredient VARCHAR(500),
                payment_price DECIMAL(10,2),
                effective_start DATE,
                effective_end DATE,
                manufacturer VARCHAR(200),
                specifications VARCHAR(200),
                payment_rules TEXT,
                ai_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 醫療服務資料表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS medical_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code VARCHAR(20) NOT NULL UNIQUE,
                name_cn VARCHAR(500),
                name_en VARCHAR(500),
                category VARCHAR(200),
                fee_points INTEGER,
                notes TEXT,
                effective_start DATE,
                effective_end DATE,
                payment_rules TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 病例範本資料表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS case_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                template_name VARCHAR(200) NOT NULL,
                category VARCHAR(100),
                specialty VARCHAR(100),
                content TEXT,
                source_file VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 搜尋歷史資料表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_type VARCHAR(50) NOT NULL,
                query TEXT NOT NULL,
                results_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        logger.info("資料表建立完成")

    def _initialize_icd10(self, conn: sqlite3.Connection) -> None:
        """初始化 ICD-10 資料"""
        cursor = conn.cursor()

        if not self.config.icd10_path.exists():
            logger.warning(f"ICD-10 檔案不存在: {self.config.icd10_path}")
            return

        # 讀取 JavaScript 檔案
        with open(self.config.icd10_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 移除 JavaScript 語法
        content = re.sub(r"^const\s+\w+\s*=\s*", "", content)
        content = content.rstrip(";")

        # 解析 JSON
        data = json.loads(content)
        total = len(data)
        logger.info(f"讀取到 {total} 筆 ICD-10 資料")

        # 批次插入
        inserted = 0
        for i in range(0, total, self.batch_size):
            batch = data[i : i + self.batch_size]
            values = [
                (
                    item.get("code", ""),
                    item.get("nameEn", ""),
                    item.get("nameCn", ""),
                    self._get_icd_category(item.get("code", "")),
                    self._get_parent_code(item.get("code", "")),
                    item.get("use", "0") == "1",
                )
                for item in batch
            ]
            cursor.executemany(
                """
                INSERT OR IGNORE INTO icd10_codes 
                (code, name_en, name_cn, category, parent_code, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                values,
            )
            inserted += len(values)

            if (i + self.batch_size) % 10000 == 0:
                conn.commit()
                logger.info(f"ICD-10 進度: {inserted}/{total} ({(inserted / total * 100):.1f}%)")

        conn.commit()
        logger.info(f"ICD-10 資料初始化完成: {inserted} 筆")

    def _get_icd_category(self, code: str) -> str:
        """取得 ICD-10 大類別"""
        if not code:
            return ""
        category_map = {
            "A": "傳染病",
            "B": "傳染病",
            "C": "腫瘤",
            "D": "血液疾病",
            "E": "內分泌疾病",
            "F": "精神疾病",
            "G": "神經系統疾病",
            "H": "眼耳疾病",
            "I": "循環系統疾病",
            "J": "呼吸系統疾病",
            "K": "消化系統疾病",
            "L": "皮膚疾病",
            "M": "肌肉骨骼疾病",
            "N": "泌尿系統疾病",
            "O": "妊娠疾病",
            "P": "新生兒疾病",
            "Q": "先天性疾病",
            "R": "症狀與徵候",
            "S": "損傷",
            "T": "中毒",
            "V": "外部因素",
            "W": "外部因素",
            "X": "外部因素",
            "Y": "外部因素",
            "Z": "因素",
        }
        letter = code[0] if code else ""
        return category_map.get(letter, "其他")

    def _get_parent_code(self, code: str) -> Optional[str]:
        """取得父代碼"""
        if not code or len(code) <= 3:
            return None
        # 例如: A00.1 -> A00
        match = re.match(r"^([A-Z]\d{2})", code)
        return match.group(1) if match else None

    def _initialize_drugs(self, conn: sqlite3.Connection) -> None:
        """初始化藥品資料"""
        cursor = conn.cursor()

        if not self.config.drug_csv_path.exists():
            logger.warning(f"藥品檔案不存在: {self.config.drug_csv_path}")
            return

        with open(self.config.drug_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        logger.info(f"讀取到 {total} 筆藥品資料")

        inserted = 0
        for i in range(0, total, self.batch_size):
            batch = rows[i : i + self.batch_size]
            values = [
                (
                    row.get("藥品代號", ""),
                    row.get("ATC代碼", ""),
                    row.get("藥品中文名稱", ""),
                    row.get("藥品英文名稱", ""),
                    row.get("藥品分類", ""),
                    row.get("劑型", ""),
                    row.get("成分", ""),
                    self._parse_price(row.get("支付價", "0")),
                    self._parse_date(row.get("有效起日", "")),
                    self._parse_date(row.get("有效迄日", "")),
                    row.get("藥商", ""),
                    row.get("規格單位", ""),
                    row.get("給付規定", ""),
                    row.get("AI-note", ""),
                )
                for row in batch
            ]
            cursor.executemany(
                """
                INSERT OR IGNORE INTO drugs 
                (drug_code, atc_code, drug_name_cn, drug_name_en, drug_class,
                 dosage_form, ingredient, payment_price, effective_start, effective_end,
                 manufacturer, specifications, payment_rules, ai_notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                values,
            )
            inserted += len(values)

            if (i + self.batch_size) % 10000 == 0:
                conn.commit()
                logger.info(f"藥品進度: {inserted}/{total} ({(inserted / total * 100):.1f}%)")

        conn.commit()
        logger.info(f"藥品資料初始化完成: {inserted} 筆")

    def _parse_price(self, price_str: str) -> Optional[float]:
        """解析價格"""
        try:
            return float(price_str.replace(",", "").strip()) if price_str else None
        except (ValueError, AttributeError):
            return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """解析日期 (民國年轉西元年)"""
        if not date_str:
            return None
        try:
            # 例如: 1091201 -> 2020-12-01
            if len(date_str) == 7:
                year = int(date_str[:3]) + 1911
                month = date_str[3:5]
                day = date_str[5:7]
                return f"{year}-{month}-{day}"
            return date_str
        except (ValueError, IndexError):
            return None

    def _initialize_medical_orders(self, conn: sqlite3.Connection) -> None:
        """初始化醫療服務資料"""
        cursor = conn.cursor()

        if not self.config.orders_csv_path.exists():
            logger.warning(f"醫療服務檔案不存在: {self.config.orders_csv_path}")
            return

        with open(self.config.orders_csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        logger.info(f"讀取到 {total} 筆醫療服務資料")

        inserted = 0
        for i in range(0, total, self.batch_size):
            batch = rows[i : i + self.batch_size]
            values = [
                (
                    row.get("診療項目代碼", ""),
                    row.get("中文項目名稱", ""),
                    row.get("英文項目名稱", ""),
                    self._extract_order_category(row.get("中文項目名稱", "")),
                    self._parse_price(row.get("健保支付點數", "0")),
                    row.get("備註", ""),
                    self._parse_date(row.get("生效起日", "")),
                    self._parse_date(row.get("生效迄日", "")),
                    row.get("支付規定", ""),
                )
                for row in batch
            ]
            cursor.executemany(
                """
                INSERT OR IGNORE INTO medical_orders 
                (order_code, name_cn, name_en, category, fee_points,
                 notes, effective_start, effective_end, payment_rules)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                values,
            )
            inserted += len(values)

            if (i + self.batch_size) % 5000 == 0:
                conn.commit()
                logger.info(f"醫療服務進度: {inserted}/{total} ({(inserted / total * 100):.1f}%)")

        conn.commit()
        logger.info(f"醫療服務資料初始化完成: {inserted} 筆")

    def _extract_order_category(self, name: str) -> str:
        """從名稱提取類別"""
        if not name:
            return "其他"

        category_keywords = {
            "診察費": "診察費",
            "藥事服務費": "藥事服務費",
            "藥費": "藥費",
            "注射": "注射",
            "處置": "處置",
            "手術": "手術",
            "檢查": "檢查",
            "檢驗": "檢驗",
            "復健": "復健",
            "透析": "透析",
            "精神": "精神科",
            "牙科": "牙科",
            "中醫": "中醫",
        }

        for keyword, category in category_keywords.items():
            if keyword in name:
                return category
        return "其他"

    def _initialize_case_templates(self, conn: sqlite3.Connection) -> None:
        """初始化病例範本"""
        cursor = conn.cursor()

        if not self.config.case_template_dir.exists():
            logger.warning(f"病例範本目錄不存在: {self.config.case_template_dir}")
            return

        # 掃描所有 .txt 檔案
        template_files = list(self.config.case_template_dir.rglob("*.txt"))
        logger.info(f"找到 {len(template_files)} 個病例範本檔案")

        for file_path in template_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # 從路徑提取類別和專科
                relative_path = file_path.relative_to(self.config.case_template_dir)
                parts = relative_path.parts

                specialty = parts[0] if len(parts) > 1 else "一般"
                category = parts[-2] if len(parts) > 2 else "病例"
                template_name = file_path.stem

                cursor.execute(
                    """
                    INSERT INTO case_templates 
                    (template_name, category, specialty, content, source_file)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (template_name, category, specialty, content, str(file_path)),
                )

            except Exception as e:
                logger.warning(f"無法讀取範本 {file_path}: {e}")

        conn.commit()
        logger.info("病例範本初始化完成")

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """建立搜尋索引"""
        cursor = conn.cursor()

        # ICD-10 索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_icd10_code ON icd10_codes(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_icd10_category ON icd10_codes(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_icd10_name_cn ON icd10_codes(name_cn)")

        # 藥品索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_drugs_code ON drugs(drug_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_drugs_atc ON drugs(atc_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_drugs_name_cn ON drugs(drug_name_cn)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_drugs_name_en ON drugs(drug_name_en)")

        # 醫療服務索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_code ON medical_orders(order_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_category ON medical_orders(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_name_cn ON medical_orders(name_cn)")

        conn.commit()
        logger.info("索引建立完成")


def main():
    """主程式"""
    # 設定日誌
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    # 設定路徑
    base_path = Path("/home/hsu/Desktop/SoapVoice/CurrentData")
    db_path = Path("/home/hsu/Desktop/SoapVoice/data/local_db/medical.db")

    config = DataSourceConfig(
        icd10_path=base_path / "icd10-data.js",
        drug_csv_path=base_path / "藥品項查詢項目檔260316 AI  摘要支付價大於0.csv",
        orders_csv_path=base_path / "醫療服務給付項目NotebookLM1150316.csv",
        case_template_dir=base_path / "各种病例规范模板",
        db_path=db_path,
    )

    # 執行初始化
    initializer = LocalDatabaseInitializer(config)
    initializer.initialize()


if __name__ == "__main__":
    main()
