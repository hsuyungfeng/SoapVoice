# -*- coding: utf-8 -*-
"""
Clinical Compliance Guard for SoapVoice.
Queries DrtoolboxLocalServer's clinic.db to verify generated SOAP plans against medical graph rules.
"""

import os
import sqlite3
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Resolve path relative to this file's directory: src/nlp/../../data/local_db/medical.db
DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/local_db/medical.db"))
CLINIC_DB_PATH = os.getenv("CLINIC_DB_PATH", DEFAULT_DB_PATH)

class ClinicalComplianceGuard:
    def __init__(self, db_path: str = CLINIC_DB_PATH):
        self.db_path = db_path

    def _get_connection(self):
        if not os.path.exists(self.db_path):
            return None
        return sqlite3.connect(self.db_path)

    def check_compliance(self, soap_result: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Verify SOAP assessment and plan against clinical database graph rules.
        """
        warnings = []
        conn = self._get_connection()
        if not conn:
            logger.warning(f"Clinical database not found at {self.db_path}, skipping compliance checks.")
            return warnings

        try:
            cursor = conn.cursor()
            
            assessment_text = soap_result.get("assessment", "")
            plan_text = soap_result.get("plan", "")

            # 1. Match diseases in assessment text
            cursor.execute("SELECT id, name FROM medical_nodes WHERE label = 'Disease'")
            all_diseases = cursor.fetchall()
            matched_diseases = []
            for d_id, d_name in all_diseases:
                if d_name in assessment_text:
                    matched_diseases.append((d_id, d_name))

            # 2. Match drugs and foods in plan text
            cursor.execute("SELECT id, name, label FROM medical_nodes WHERE label IN ('Drug', 'Food')")
            all_entities = cursor.fetchall()
            matched_drugs = []
            matched_foods = []
            for e_id, e_name, e_label in all_entities:
                if e_name in plan_text:
                    if e_label == "Drug":
                        matched_drugs.append((e_id, e_name))
                    elif e_label == "Food":
                        matched_foods.append((e_id, e_name))

            # 3. Verify relationships
            for d_id, d_name in matched_diseases:
                # Query relationships for this disease
                cursor.execute("""
                    SELECT n2.name, e.relation 
                    FROM medical_edges e
                    JOIN medical_nodes n2 ON e.target_id = n2.id
                    WHERE e.source_id = ?
                """, (d_id,))
                relations = cursor.fetchall()
                
                no_eat_foods = [name for name, rel in relations if rel == 'no_eat']
                recommand_drugs = [name for name, rel in relations if rel in ['recommand_drug', 'common_drug']]

                # Check for prohibited food (no_eat)
                for f_id, f_name in matched_foods:
                    if f_name in no_eat_foods:
                        warnings.append({
                            "type": "CRITICAL",
                            "message": f"【飲食警告】診斷為「{d_name}」，但處置計畫中包含忌吃食物「{f_name}」！"
                        })

                # Check for drug alignment
                for dr_id, dr_name in matched_drugs:
                    if dr_name in recommand_drugs:
                        warnings.append({
                            "type": "INFO",
                            "message": f"【用藥驗證】診斷為「{d_name}」，處置計畫中使用推薦用藥「{dr_name}」，符合臨床圖譜指引。"
                        })

            conn.close()
        except Exception as e:
            logger.error(f"Error checking clinical compliance: {e}")
            if conn:
                conn.close()

        return warnings
