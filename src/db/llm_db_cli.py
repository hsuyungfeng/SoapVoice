"""
LLM Database CLI Interface

提供給 LLM 生成器使用的結構化資料庫查詢介面
支援 ICD-10、藥品、醫療服務的查詢與檢索

This module serves as a bridge between LLM and database,
allowing the LLM to query clinical data during SOAP generation.
"""

import logging
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from src.db.local_database import LocalDatabase, ICD10Result, DrugResult, MedicalOrderResult

logger = logging.getLogger(__name__)


class LLMDatabaseCLI:
    """LLM 資料庫 CLI 查詢介面

    提供給 LLM 在生成 SOAP 時使用的結構化查詢命令。
    所有查詢結果均為 JSON 格式，易於 LLM 解析。
    """

    def __init__(self, db_path: Path):
        """初始化 LLM Database CLI

        Args:
            db_path: 資料庫路徑
        """
        self.db = LocalDatabase(db_path)
        self._query_cache: Dict[str, Any] = {}

    def query_icd10(self, keyword: str, limit: int = 5) -> Dict[str, Any]:
        """查詢 ICD-10 診斷代碼

        Usage in LLM prompt:
            <query_icd10: chest pain>

        Args:
            keyword: 症狀或診斷關鍵字（中文或英文）
            limit: 最大結果數

        Returns:
            JSON 格式的 ICD-10 結果
            {
                "status": "success",
                "results": [
                    {
                        "code": "R07.9",
                        "name_en": "Chest pain, unspecified",
                        "name_cn": "胸痛，未詳細說明",
                        "category": "Symptom"
                    }
                ]
            }
        """
        try:
            # 檢查快取
            cache_key = f"icd10:{keyword}:{limit}"
            if cache_key in self._query_cache:
                return self._query_cache[cache_key]

            results = self.db.search_icd10(keyword, limit=limit)

            formatted_results = [
                {
                    "code": r.code,
                    "name_en": r.name_en,
                    "name_cn": r.name_cn,
                    "category": r.category,
                    "confidence": r.confidence
                }
                for r in results
            ]

            response = {
                "status": "success",
                "count": len(formatted_results),
                "results": formatted_results
            }

            # 快取結果
            self._query_cache[cache_key] = response
            return response

        except Exception as e:
            logger.error(f"ICD-10 查詢失敗: {e}")
            return {
                "status": "error",
                "message": f"查詢失敗: {str(e)}",
                "results": []
            }

    def query_drugs(self, keyword: str, limit: int = 5) -> Dict[str, Any]:
        """查詢藥品資訊

        Usage in LLM prompt:
            <query_drugs: paracetamol>

        Args:
            keyword: 藥品名稱或 ATC 代碼
            limit: 最大結果數

        Returns:
            JSON 格式的藥品結果
            {
                "status": "success",
                "results": [
                    {
                        "drug_code": "A001",
                        "drug_name_en": "Acetaminophen",
                        "drug_name_cn": "乙醯胺酚",
                        "atc_code": "N02BE01",
                        "drug_class": "Analgesic",
                        "dosage_form": "Tablet",
                        "payment_price": 50.5
                    }
                ]
            }
        """
        try:
            cache_key = f"drugs:{keyword}:{limit}"
            if cache_key in self._query_cache:
                return self._query_cache[cache_key]

            results = self.db.search_drugs(keyword, limit=limit)

            formatted_results = [
                {
                    "drug_code": r.drug_code,
                    "drug_name_en": r.drug_name_en,
                    "drug_name_cn": r.drug_name_cn,
                    "atc_code": r.atc_code,
                    "drug_class": r.drug_class,
                    "dosage_form": r.dosage_form,
                    "payment_price": r.payment_price,
                    "payment_rules": r.payment_rules
                }
                for r in results
            ]

            response = {
                "status": "success",
                "count": len(formatted_results),
                "results": formatted_results
            }

            self._query_cache[cache_key] = response
            return response

        except Exception as e:
            logger.error(f"藥品查詢失敗: {e}")
            return {
                "status": "error",
                "message": f"查詢失敗: {str(e)}",
                "results": []
            }

    def query_drugs_by_atc(self, atc_code: str, limit: int = 10) -> Dict[str, Any]:
        """根據 ATC 分類查詢藥品

        Usage in LLM prompt:
            <query_drugs_by_atc: N02>

        Args:
            atc_code: ATC 分類代碼（如 N02 表示止痛藥）
            limit: 最大結果數

        Returns:
            JSON 格式的藥品結果
        """
        try:
            cache_key = f"drugs_atc:{atc_code}:{limit}"
            if cache_key in self._query_cache:
                return self._query_cache[cache_key]

            results = self.db.search_drugs_by_atc_class(atc_code, limit=limit)

            formatted_results = [
                {
                    "drug_code": r.drug_code,
                    "drug_name_en": r.drug_name_en,
                    "drug_name_cn": r.drug_name_cn,
                    "atc_code": r.atc_code,
                    "drug_class": r.drug_class
                }
                for r in results
            ]

            response = {
                "status": "success",
                "count": len(formatted_results),
                "results": formatted_results
            }

            self._query_cache[cache_key] = response
            return response

        except Exception as e:
            logger.error(f"ATC 查詢失敗: {e}")
            return {
                "status": "error",
                "message": f"查詢失敗: {str(e)}",
                "results": []
            }

    def query_medical_orders(self, keyword: str, limit: int = 5) -> Dict[str, Any]:
        """查詢醫療服務與處置

        Usage in LLM prompt:
            <query_medical_orders: X-ray>

        Args:
            keyword: 服務或處置名稱
            limit: 最大結果數

        Returns:
            JSON 格式的醫療服務結果
            {
                "status": "success",
                "results": [
                    {
                        "order_code": "M001",
                        "name_en": "Chest X-ray",
                        "name_cn": "胸部 X 光",
                        "category": "Radiology",
                        "fee_points": 500
                    }
                ]
            }
        """
        try:
            cache_key = f"orders:{keyword}:{limit}"
            if cache_key in self._query_cache:
                return self._query_cache[cache_key]

            results = self.db.search_medical_orders(keyword, limit=limit)

            formatted_results = [
                {
                    "order_code": r.order_code,
                    "name_en": r.name_en,
                    "name_cn": r.name_cn,
                    "category": r.category,
                    "fee_points": r.fee_points,
                    "payment_rules": r.payment_rules
                }
                for r in results
            ]

            response = {
                "status": "success",
                "count": len(formatted_results),
                "results": formatted_results
            }

            self._query_cache[cache_key] = response
            return response

        except Exception as e:
            logger.error(f"醫療服務查詢失敗: {e}")
            return {
                "status": "error",
                "message": f"查詢失敗: {str(e)}",
                "results": []
            }

    def get_icd10_by_code(self, code: str) -> Dict[str, Any]:
        """根據 ICD-10 代碼獲取詳細資訊

        Usage in LLM prompt:
            <get_icd10_details: R07.9>

        Args:
            code: ICD-10 代碼

        Returns:
            ICD-10 詳細資訊或錯誤信息
        """
        try:
            cache_key = f"icd10_detail:{code}"
            if cache_key in self._query_cache:
                return self._query_cache[cache_key]

            result = self.db.get_icd10_by_code(code)

            if result:
                response = {
                    "status": "success",
                    "code": result.code,
                    "name_en": result.name_en,
                    "name_cn": result.name_cn,
                    "category": result.category
                }
            else:
                response = {
                    "status": "not_found",
                    "message": f"ICD-10 代碼未找到: {code}"
                }

            self._query_cache[cache_key] = response
            return response

        except Exception as e:
            logger.error(f"ICD-10 詳細查詢失敗: {e}")
            return {
                "status": "error",
                "message": f"查詢失敗: {str(e)}"
            }

    def get_statistics(self) -> Dict[str, Any]:
        """取得資料庫統計資訊

        Usage in LLM prompt:
            <get_db_stats>

        Returns:
            資料庫統計信息
        """
        try:
            stats = self.db.get_statistics()
            return {
                "status": "success",
                "statistics": stats
            }
        except Exception as e:
            logger.error(f"統計查詢失敗: {e}")
            return {
                "status": "error",
                "message": f"查詢失敗: {str(e)}"
            }

    def close(self):
        """關閉資料庫連線"""
        self.db.close()


# 便利函式：用於 SOAP Generator 整合
def create_llm_db_cli(db_path: Optional[Path] = None) -> LLMDatabaseCLI:
    """創建 LLM Database CLI 實例

    Args:
        db_path: 資料庫路徑，預設為 data/local_db/medical.db

    Returns:
        LLMDatabaseCLI 實例
    """
    if db_path is None:
        db_path = Path("data/local_db/medical.db")

    if not db_path.exists():
        logger.warning(f"資料庫不存在: {db_path}")

    return LLMDatabaseCLI(db_path)
