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
            # 優先根據 ICD-10 代碼搜尋具體處置或檢查
            if icd10_codes:
                for code in icd10_codes:
                    # 排除行政、訪視費、診察費、護理費
                    cursor.execute("""
                        SELECT name_cn FROM medical_orders 
                        WHERE (notes LIKE ? OR name_cn LIKE ?) 
                        AND category NOT IN ('診察費', '訪視費', '行政費', '護理費', '材料費')
                        AND name_cn NOT LIKE '%訪視%'
                        AND name_cn NOT LIKE '%離島%'
                        AND name_cn NOT LIKE '%費%'
                        LIMIT 3
                    """, (f"%{code}%", f"%{code}%"))
                    for row in cursor.fetchall():
                        orders.append(row[0])
            
            # 若無 ICD 對應，根據症狀關鍵字搜尋醫囑
            if not orders and symptoms:
                for symptom in symptoms:
                    if len(symptom) < 2: continue
                    cursor.execute("""
                        SELECT name_cn FROM medical_orders 
                        WHERE (name_cn LIKE ? OR notes LIKE ?)
                        AND category IN ('檢查費', '治療處置費', '放射線診療費')
                        AND name_cn NOT LIKE '%費%'
                        LIMIT 2
                    """, (f"%{symptom}%", f"%{symptom}%"))
                    for row in cursor.fetchall():
                        orders.append(row[0])
                    
        except Exception as e:
            logger.error(f"查詢醫囑失敗: {e}")
        finally:
            conn.close()
                
        return sorted(list(set(orders)))[:5]
        
    def get_drug_recommendations(self, symptoms: List[str], icd10_codes: List[str]) -> List[Dict[str, str]]:
        """根據症狀和 ICD-10 獲取藥物建議"""
        conn = self._get_connection()
        if not conn:
            return []
            
        drugs = []
        try:
            cursor = conn.cursor()
            for symptom in symptoms:
                if len(symptom) < 2: continue
                # 搜尋藥物名稱或適應症
                cursor.execute("""
                    SELECT drug_name_cn, drug_name_en, ai_notes, indications 
                    FROM drugs 
                    WHERE (drug_name_cn LIKE ? OR indications LIKE ?) 
                    AND indications IS NOT NULL 
                    AND indications != ''
                    LIMIT 2
                """, (f"%{symptom}%", f"%{symptom}%"))
                for row in cursor.fetchall():
                    # 排除不相關的產科藥物 (除非症狀包含產科關鍵字)
                    indication = row[3] if row[3] else ""
                    if ("剖腹" in indication or "產" in indication) and "產" not in "".join(symptoms):
                        continue

                    dosage = "遵醫囑"
                    if row[2] and "用法用量" in row[2]:
                         parts = row[2].split("用法用量")
                         if len(parts) > 1:
                            dosage = parts[1].split("\n")[0].strip(": ")[:30]
                    
                    drugs.append({
                        "name": row[0],
                        "dosage": dosage,
                        "indication": indication[:100] + "..." if len(indication) > 100 else indication,
                        "category": "建議用藥"
                    })
                    
        except Exception as e:
            logger.error(f"查詢藥物失敗: {e}")
        finally:
            conn.close()
                    
        return drugs[:5]
