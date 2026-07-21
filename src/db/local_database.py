"""
本地資料庫查詢介面

提供快速查詢本地資料庫的介面
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ICD10Result:
    """ICD-10 查詢結果"""

    code: str
    name_en: str
    name_cn: str
    category: str
    confidence: float = 1.0


@dataclass
class DrugResult:
    """藥品查詢結果"""

    drug_code: str
    atc_code: str
    drug_name_cn: str
    drug_name_en: str
    drug_class: str
    dosage_form: str
    payment_price: float
    payment_rules: str


@dataclass
class MedicalOrderResult:
    """醫療服務查詢結果"""

    order_code: str
    name_cn: str
    name_en: str
    category: str
    fee_points: int
    payment_rules: str


@dataclass
class DiseaseInfoResult:
    """疾病知識查詢結果"""

    name: str
    description: str = ""
    cause: str = ""
    prevent: str = ""
    cure_way: str = ""
    cure_lasttime: str = ""
    cured_prob: str = ""


@dataclass
class DiseaseSymptomResult:
    """疾病症狀查詢結果"""

    disease_name: str
    symptom_name: str


@dataclass
class DiseaseDrugResult:
    """疾病藥品查詢結果"""

    disease_name: str
    drug_name: str
    drug_type: str


@dataclass
class DiseaseFoodResult:
    """疾病飲食建議查詢結果"""

    disease_name: str
    food_name: str
    food_type: str  # do_eat / not_eat / recommand_eat


@dataclass
class DiseaseCheckResult:
    """疾病檢查項目查詢結果"""

    disease_name: str
    check_name: str


@dataclass
class DiseaseProfileResult:
    """完整疾病資訊"""

    info: DiseaseInfoResult
    symptoms: List[str]
    drugs: List[str]
    foods: Dict[str, List[str]]  # {do_eat: [...], not_eat: [...], recommand_eat: [...]}
    checks: List[str]
    departments: List[str]
    acompany: List[str]


class LocalDatabase:
    """本地資料庫查詢介面"""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def _get_connection(self) -> sqlite3.Connection:
        """取得資料庫連線"""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def close(self):
        """關閉資料庫連線"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def search_icd10(self, query: str, limit: int = 10) -> List[ICD10Result]:
        """搜尋 ICD-10

        Args:
            query: 搜尋關鍵字
            limit: 最大結果數

        Returns:
            ICD-10 結果列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # 中文或英文搜尋
        cursor.execute(
            """
            SELECT code, name_en, name_cn, category
            FROM icd10_codes
            WHERE name_cn LIKE ?
               OR name_en LIKE ?
               OR code LIKE ?
            ORDER BY
                CASE WHEN name_cn LIKE ? THEN 0 ELSE 1 END,
                CASE WHEN code = ? THEN 0 ELSE 1 END
            LIMIT ?
        """,
            (
                f"%{query}%",
                f"%{query}%",
                f"%{query}%",  # 搜尋條件
                f"{query}%",  # 中文優先
                query,  # 精確代碼優先
                limit,
            ),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                ICD10Result(
                    code=row["code"],
                    name_en=row["name_en"],
                    name_cn=row["name_cn"],
                    category=row["category"],
                    confidence=1.0,
                )
            )

        return results

    def get_icd10_by_code(self, code: str) -> Optional[ICD10Result]:
        """根據代碼取得 ICD-10"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT code, name_en, name_cn, category
            FROM icd10_codes
            WHERE code = ?
        """,
            (code,),
        )

        row = cursor.fetchone()
        if row:
            return ICD10Result(
                code=row["code"],
                name_en=row["name_en"],
                name_cn=row["name_cn"],
                category=row["category"],
            )
        return None

    def search_drugs(
        self, query: str, atc_code: Optional[str] = None, limit: int = 10
    ) -> List[DrugResult]:
        """搜尋藥品

        Args:
            query: 搜尋關鍵字
            atc_code: ATC 代碼前綴（可選）
            limit: 最大結果數

        Returns:
            藥品結果列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT drug_code, atc_code, drug_name_cn, drug_name_en,
                   drug_class, dosage_form, payment_price, payment_rules
            FROM drugs
            WHERE (drug_name_cn LIKE ?
                OR drug_name_en LIKE ?
                OR drug_code LIKE ?
                OR atc_code LIKE ?)
        """
        params = [f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"]

        if atc_code:
            sql += " AND atc_code LIKE ?"
            params.append(f"{atc_code}%")

        sql += " ORDER BY payment_price DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)

        results = []
        for row in cursor.fetchall():
            results.append(
                DrugResult(
                    drug_code=row["drug_code"],
                    atc_code=row["atc_code"] or "",
                    drug_name_cn=row["drug_name_cn"] or "",
                    drug_name_en=row["drug_name_en"] or "",
                    drug_class=row["drug_class"] or "",
                    dosage_form=row["dosage_form"] or "",
                    payment_price=row["payment_price"] or 0,
                    payment_rules=row["payment_rules"] or "",
                )
            )

        return results

    def search_drugs_by_atc_class(self, atc_class: str, limit: int = 20) -> List[DrugResult]:
        """根據 ATC 分類搜尋藥品"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT drug_code, atc_code, drug_name_cn, drug_name_en,
                   drug_class, dosage_form, payment_price, payment_rules
            FROM drugs
            WHERE atc_code LIKE ?
            ORDER BY drug_name_cn
            LIMIT ?
        """,
            (f"{atc_class}%", limit),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                DrugResult(
                    drug_code=row["drug_code"],
                    atc_code=row["atc_code"] or "",
                    drug_name_cn=row["drug_name_cn"] or "",
                    drug_name_en=row["drug_name_en"] or "",
                    drug_class=row["drug_class"] or "",
                    dosage_form=row["dosage_form"] or "",
                    payment_price=row["payment_price"] or 0,
                    payment_rules=row["payment_rules"] or "",
                )
            )

        return results

    def search_medical_orders(
        self, query: str, category: Optional[str] = None, limit: int = 10
    ) -> List[MedicalOrderResult]:
        """搜尋醫療服務

        Args:
            query: 搜尋關鍵字
            category: 類別（可選）
            limit: 最大結果數

        Returns:
            醫療服務結果列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT order_code, name_cn, name_en, category,
                   fee_points, payment_rules
            FROM medical_orders
            WHERE name_cn LIKE ?
        """
        params = [f"%{query}%"]

        if category:
            sql += " AND category = ?"
            params.append(category)

        sql += " ORDER BY fee_points DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)

        results = []
        for row in cursor.fetchall():
            results.append(
                MedicalOrderResult(
                    order_code=row["order_code"],
                    name_cn=row["name_cn"],
                    name_en=row["name_en"] or "",
                    category=row["category"],
                    fee_points=row["fee_points"] or 0,
                    payment_rules=row["payment_rules"] or "",
                )
            )

        return results

    def get_medical_orders_by_category(
        self, category: str, limit: int = 20
    ) -> List[MedicalOrderResult]:
        """根據類別取得醫療服務"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT order_code, name_cn, name_en, category,
                   fee_points, payment_rules
            FROM medical_orders
            WHERE category = ?
            ORDER BY fee_points DESC
            LIMIT ?
        """,
            (category, limit),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                MedicalOrderResult(
                    order_code=row["order_code"],
                    name_cn=row["name_cn"],
                    name_en=row["name_en"] or "",
                    category=row["category"],
                    fee_points=row["fee_points"] or 0,
                    payment_rules=row["payment_rules"] or "",
                )
            )

        return results

    def search_diseases(self, query: str, limit: int = 10) -> List[DiseaseInfoResult]:
        """搜尋疾病知識

        Args:
            query: 搜尋關鍵字
            limit: 最大結果數

        Returns:
            疾病資訊列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name, description, cause, prevent,
                   cure_way, cure_lasttime, cured_prob
            FROM disease_info
            WHERE name LIKE ?
               OR description LIKE ?
               OR cause LIKE ?
            ORDER BY
                CASE WHEN name LIKE ? THEN 0 ELSE 1 END
            LIMIT ?
        """,
            (
                f"%{query}%",
                f"%{query}%",
                f"%{query}%",
                f"{query}%",
                limit,
            ),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                DiseaseInfoResult(
                    name=row["name"],
                    description=row["description"] or "",
                    cause=row["cause"] or "",
                    prevent=row["prevent"] or "",
                    cure_way=row["cure_way"] or "",
                    cure_lasttime=row["cure_lasttime"] or "",
                    cured_prob=row["cured_prob"] or "",
                )
            )

        return results

    def search_symptoms(self, query: str, limit: int = 10) -> List[DiseaseSymptomResult]:
        """搜尋症狀及其對應疾病

        Args:
            query: 症狀關鍵字
            limit: 最大結果數

        Returns:
            症狀-疾病對應列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT disease_name, symptom_name
            FROM disease_symptoms
            WHERE symptom_name LIKE ?
            LIMIT ?
        """,
            (f"%{query}%", limit),
        )

        results = []
        for row in cursor.fetchall():
            results.append(
                DiseaseSymptomResult(
                    disease_name=row["disease_name"],
                    symptom_name=row["symptom_name"],
                )
            )

        return results

    def get_disease_symptoms(self, disease_name: str) -> List[str]:
        """取得疾病的所有症狀"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT symptom_name FROM disease_symptoms WHERE disease_name = ? ORDER BY symptom_name",
            (disease_name,),
        )
        return [row["symptom_name"] for row in cursor.fetchall()]

    def get_disease_drugs(self, disease_name: str, drug_type: Optional[str] = None) -> List[DiseaseDrugResult]:
        """取得疾病的藥品

        Args:
            disease_name: 疾病名稱
            drug_type: 藥品類型 (common/recommand)，None 表示全部

        Returns:
            藥品列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if drug_type:
            cursor.execute(
                "SELECT disease_name, drug_name, drug_type FROM disease_drugs WHERE disease_name = ? AND drug_type = ? ORDER BY drug_name",
                (disease_name, drug_type),
            )
        else:
            cursor.execute(
                "SELECT disease_name, drug_name, drug_type FROM disease_drugs WHERE disease_name = ? ORDER BY drug_type, drug_name",
                (disease_name,),
            )

        results = []
        for row in cursor.fetchall():
            results.append(
                DiseaseDrugResult(
                    disease_name=row["disease_name"],
                    drug_name=row["drug_name"],
                    drug_type=row["drug_type"],
                )
            )

        return results

    def get_disease_foods(self, disease_name: str, food_type: Optional[str] = None) -> Dict[str, List[str]]:
        """取得疾病的飲食建議

        Args:
            disease_name: 疾病名稱
            food_type: 飲食類型 (do_eat/not_eat/recommand_eat)，None 表示全部

        Returns:
            飲食建議字典
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if food_type:
            cursor.execute(
                "SELECT food_name, food_type FROM disease_foods WHERE disease_name = ? AND food_type = ? ORDER BY food_name",
                (disease_name, food_type),
            )
        else:
            cursor.execute(
                "SELECT food_name, food_type FROM disease_foods WHERE disease_name = ? ORDER BY food_type, food_name",
                (disease_name,),
            )

        result: Dict[str, List[str]] = {}
        for row in cursor.fetchall():
            ft = row["food_type"]
            if ft not in result:
                result[ft] = []
            result[ft].append(row["food_name"])

        return result

    def get_disease_checks(self, disease_name: str) -> List[str]:
        """取得疾病的檢查項目"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT check_name FROM disease_checks WHERE disease_name = ? ORDER BY check_name",
            (disease_name,),
        )
        return [row["check_name"] for row in cursor.fetchall()]

    def get_disease_departments(self, disease_name: str) -> List[str]:
        """取得疾病對應的科室"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT department_name FROM disease_departments WHERE disease_name = ? ORDER BY department_name",
            (disease_name,),
        )
        return [row["department_name"] for row in cursor.fetchall()]

    def get_disease_acompany(self, disease_name: str) -> List[str]:
        """取得疾病的併發症"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT acompany_name FROM disease_acompany WHERE disease_name = ? ORDER BY acompany_name",
            (disease_name,),
        )
        return [row["acompany_name"] for row in cursor.fetchall()]

    def get_disease_profile(self, disease_name: str) -> Optional[DiseaseProfileResult]:
        """取得完整疾病資訊

        Args:
            disease_name: 疾病名稱

        Returns:
            完整疾病資訊
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT name, description, cause, prevent,
                      cure_way, cure_lasttime, cured_prob
               FROM disease_info WHERE name = ?""",
            (disease_name,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        info = DiseaseInfoResult(
            name=row["name"],
            description=row["description"] or "",
            cause=row["cause"] or "",
            prevent=row["prevent"] or "",
            cure_way=row["cure_way"] or "",
            cure_lasttime=row["cure_lasttime"] or "",
            cured_prob=row["cured_prob"] or "",
        )

        profile = DiseaseProfileResult(
            info=info,
            symptoms=self.get_disease_symptoms(disease_name),
            drugs=[d.drug_name for d in self.get_disease_drugs(disease_name)],
            foods=self.get_disease_foods(disease_name),
            checks=self.get_disease_checks(disease_name),
            departments=self.get_disease_departments(disease_name),
            acompany=self.get_disease_acompany(disease_name),
        )

        return profile

    def get_statistics(self) -> Dict[str, Any]:
        """取得資料庫統計"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        for table in [
            "icd10_codes",
            "drugs",
            "medical_orders",
            "case_templates",
            "disease_info",
            "disease_symptoms",
            "disease_drugs",
            "disease_foods",
            "disease_checks",
            "disease_departments",
            "disease_acompany",
        ]:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[table] = cursor.fetchone()[0]
            except Exception:
                stats[table] = 0

        return stats


# 快速查詢範例
def quick_search_demo():
    """快速查詢示範"""
    from pathlib import Path

    db = LocalDatabase(Path("data/local_db/medical.db"))

    print("=" * 60)
    print("本地資料庫快速查詢示範（含疾病知識）")
    print("=" * 60)

    # ICD-10 搜尋
    print("\n1. ICD-10 搜尋「咳嗽」:")
    results = db.search_icd10("咳嗽", limit=5)
    for r in results:
        print(f"   {r.code} - {r.name_cn}")

    # 藥品搜尋
    print("\n2. 藥品搜尋「止痛」:")
    results = db.search_drugs("止痛", limit=5)
    for r in results:
        print(f"   {r.drug_code} - {r.drug_name_cn} (ATC: {r.atc_code})")

    # 醫療服務搜尋
    print("\n3. 醫療服務搜尋「注射」:")
    results = db.search_medical_orders("注射", limit=5)
    for r in results:
        print(f"   {r.order_code} - {r.name_cn} ({r.fee_points}點)")

    # ATC 分類搜尋
    print("\n4. ATC N02 (止痛藥) 分類:")
    results = db.search_drugs_by_atc_class("N02", limit=5)
    for r in results:
        print(f"   {r.atc_code} - {r.drug_name_cn}")

    # 疾病知識搜尋
    print("\n5. 疾病搜尋「糖尿病」:")
    diseases = db.search_diseases("糖尿病", limit=3)
    for d in diseases:
        print(f"   {d.name}: {d.description[:60]}...")

    # 症狀搜尋
    print("\n6. 症狀搜尋「發燒」:")
    results = db.search_symptoms("發燒", limit=5)
    for r in results:
        print(f"   {r.symptom_name} → {r.disease_name}")

    # 完整疾病資訊
    print("\n7. 完整疾病資訊「百日咳」:")
    profile = db.get_disease_profile("百日咳")
    if profile:
        print(f"   描述: {profile.info.description[:80]}...")
        print(f"   症狀: {', '.join(profile.symptoms[:5])}")
        print(f"   常用藥品: {', '.join(profile.drugs[:5])}")
        print(f"   宜吃: {', '.join(profile.foods.get('do_eat', [])[:5])}")
        print(f"   忌吃: {', '.join(profile.foods.get('not_eat', [])[:5])}")
        print(f"   檢查: {', '.join(profile.checks[:5])}")
        print(f"   科室: {', '.join(profile.departments[:5])}")
        print(f"   併發症: {', '.join(profile.acompany[:5])}")

    # 統計資訊
    print("\n8. 資料庫統計:")
    stats = db.get_statistics()
    for k, v in stats.items():
        if v:
            print(f"   {k}: {v:,}")

    db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    quick_search_demo()
