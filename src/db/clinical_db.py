import sqlite3
import os
import logging
from typing import List, Dict

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
                # 搜尋藥物名稱或 ai_notes (包含適應症資訊)
                cursor.execute("""
                    SELECT drug_name_cn, drug_name_en, ai_notes 
                    FROM drugs 
                    WHERE (drug_name_cn LIKE ? OR ai_notes LIKE ?) 
                    AND ai_notes IS NOT NULL 
                    AND ai_notes != ''
                    LIMIT 2
                """, (f"%{symptom}%", f"%{symptom}%"))
                for row in cursor.fetchall():
                    drug_name = row[0]
                    ai_notes = row[2] if row[2] else ""
                    
                    # 從 ai_notes 提取適應症部分 (假設格式為 **主要用途/適應症**)
                    indication = "請參照仿單"
                    if "適應症" in ai_notes:
                        parts = ai_notes.split("適應症")
                        if len(parts) > 1:
                            indication = parts[1].split("**")[0].strip("- \n")
                            # 限制長度
                            if "\n" in indication:
                                indication = indication.split("\n")[0]

                    # 排除不相關的產科藥物 (除非症狀包含產科關鍵字)
                    if ("剖腹" in indication or "產" in indication) and "產" not in "".join(symptoms):
                        continue

                    dosage = "遵醫囑"
                    if ai_notes and "用法用量" in ai_notes:
                         parts = ai_notes.split("用法用量")
                         if len(parts) > 1:
                            dosage = parts[1].split("**")[0].strip("- : \n")
                            if "\n" in dosage:
                                dosage = dosage.split("\n")[0]
                            dosage = dosage[:30]
                    
                    drugs.append({
                        "name": drug_name,
                        "dosage": dosage,
                        "indication": indication[:100] + "..." if len(indication) > 100 else indication,
                        "category": "建議用藥"
                    })
                    
        except Exception as e:
            logger.error(f"查詢藥物失敗: {e}")
        finally:
            conn.close()
                    
        return drugs[:5]
