import sqlite3
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ClinicalDatabase:
    """臨床醫囑與藥物資料庫 API - 連接到 data/local_db/medical.db"""
    
    def __init__(self, db_path: str = "data/local_db/medical.db"):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
             logger.warning(f"資料庫檔案不存在: {self.db_path}")
        
    def _get_connection(self):
        """建立資料庫連接"""
        try:
            return sqlite3.connect(self.db_path)
        except Exception as e:
            logger.error(f"資料庫連接失敗: {e}")
            return None

    def get_medical_orders(self, symptoms: List[str], icd10_codes: List[str]) -> List[str]:
        """根據症狀和 ICD-10 獲取醫囑建議"""
        conn = self._get_connection()
        if not conn:
            return []
            
        orders = []
        try:
            cursor = conn.cursor()
            # 優先根據 ICD-10 代碼搜尋醫囑
            if icd10_codes:
                placeholders = ",".join(["?"] * len(icd10_codes))
                # 這裡假設醫囑表中可能有關聯欄位，若無則進行關鍵字搜尋
                # 先嘗試診斷直接對應 (mock 一下 ICD10 logic 若表無 direct mapping)
                for code in icd10_codes:
                    # 搜尋名稱中包含 ICD 代碼描述的部分
                    cursor.execute("SELECT name_cn FROM medical_orders WHERE notes LIKE ? OR name_cn LIKE ? LIMIT 3", (f"%{code}%", f"%{code}%"))
                    for row in cursor.fetchall():
                        orders.append(row[0])
            
            # 若無醫囑，搜尋類別
            if not orders:
                cursor.execute("SELECT name_cn FROM medical_orders WHERE category IN ('診察費', '處置費') LIMIT 3")
                for row in cursor.fetchall():
                    orders.append(row[0])
                    
        except Exception as e:
            logger.error(f"查詢醫囑失敗: {e}")
        finally:
            conn.close()
                
        return list(set(orders))[:5]
        
    def get_drug_recommendations(self, symptoms: List[str], icd10_codes: List[str]) -> List[Dict[str, str]]:
        """根據症狀和 ICD-10 獲獲藥物建議"""
        conn = self._get_connection()
        if not conn:
            return []
            
        drugs = []
        try:
            cursor = conn.cursor()
            for symptom in symptoms:
                # 搜尋藥物適應症或名稱
                cursor.execute("SELECT drug_name_cn, drug_name_en, ai_notes FROM drugs WHERE drug_name_cn LIKE ? OR drug_name_en LIKE ? LIMIT 2", (f"%{symptom}%", f"%{symptom}%"))
                for row in cursor.fetchall():
                    # 優先使用 ai_notes 中的劑量資訊（若有）
                    dosage = "遵醫囑"
                    if row[2] and "用法用量" in row[2]:
                         # 簡單解析 snippet
                         parts = row[2].split("用法用量")
                         if len(parts) > 1:
                            dosage = parts[1].split("\n")[0].strip(": ")[:30]
                    
                    drugs.append({
                        "name": row[0],
                        "dosage": dosage,
                        "category": "建議用藥"
                    })
                    
        except Exception as e:
            logger.error(f"查詢藥物失敗: {e}")
        finally:
            conn.close()
                    
        return drugs[:5]
