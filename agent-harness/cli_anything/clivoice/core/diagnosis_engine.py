"""
診斷引擎

從 SOAP 病歷分析症狀並匹配 ICD-10 診斷代碼
"""

import re
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from ..models import (
    Patient,
    SOAPNote,
    Diagnosis,
    DiagnosisResult,
    DiagnosisConfidence,
)
from ..adapters.icd10_adapter import ICD10Adapter


logger = logging.getLogger(__name__)


class DiagnosisEngine:
    """診斷引擎"""

    def __init__(self, icd10_adapter: Optional[ICD10Adapter] = None):
        """初始化診斷引擎

        Args:
            icd10_adapter: ICD-10 適配器，預設為 None 會自動建立
        """
        self.icd10_adapter = icd10_adapter or ICD10Adapter()
        self._symptom_patterns = self._load_symptom_patterns()
        self._diagnosis_rules = self._load_diagnosis_rules()

    def _load_symptom_patterns(self) -> Dict[str, List[str]]:
        """載入症狀模式"""
        return {
            "respiratory": ["咳嗽", "咳痰", "呼吸困難", "胸悶", "喘", "喉嚨痛", "流鼻水", "鼻塞"],
            "fever": ["發燒", "發熱", "畏寒", "寒顫"],
            "gastrointestinal": ["腹痛", "腹瀉", "便秘", "噁心", "嘔吐", "胃痛", "消化不良"],
            "neurological": ["頭痛", "頭暈", "暈眩", "意識不清", "抽搐", "麻木", "無力"],
            "musculoskeletal": ["關節痛", "肌肉痛", "背痛", "頸痛", "四肢痛"],
            "cardiovascular": ["胸痛", "心悸", "心跳過快", "心跳過慢", "水腫"],
            "dermatological": ["皮疹", "搔癢", "紅腫", "水泡", "脫皮"],
            "general": ["疲倦", "虛弱", "食慾不振", "體重減輕", "失眠"],
        }

    def _load_diagnosis_rules(self) -> List[Dict[str, Any]]:
        """載入診斷規則"""
        return [
            {
                "symptoms": ["咳嗽", "發燒", "呼吸困難"],
                "icd10_codes": ["J20.9", "J18.9", "J22"],
                "confidence": 0.85,
                "name": "急性下呼吸道感染",
            },
            {
                "symptoms": ["胸痛", "呼吸困難", "心悸"],
                "icd10_codes": ["I20.9", "I21.9", "R07.4"],
                "confidence": 0.75,
                "name": "缺血性心臟病",
            },
            {
                "symptoms": ["頭痛", "噁心", "嘔吐"],
                "icd10_codes": ["R51", "G43.9", "G44.2"],
                "confidence": 0.70,
                "name": "頭痛症候群",
            },
            {
                "symptoms": ["腹痛", "腹瀉", "發燒"],
                "icd10_codes": ["A09", "K52.9", "A04.9"],
                "confidence": 0.80,
                "name": "感染性腸胃炎",
            },
            {
                "symptoms": ["關節痛", "紅腫", "發熱"],
                "icd10_codes": ["M25.50", "M13.9", "M79.6"],
                "confidence": 0.65,
                "name": "關節炎",
            },
        ]

    def extract_symptoms(self, soap_note: SOAPNote) -> List[str]:
        """從 SOAP 病歷提取症狀

        Args:
            soap_note: SOAP 病歷

        Returns:
            症狀列表
        """
        symptoms = []

        # 從主觀陳述提取
        subjective_text = soap_note.subjective.content.lower()

        for category, symptom_list in self._symptom_patterns.items():
            for symptom in symptom_list:
                if symptom in subjective_text:
                    symptoms.append(symptom)

        # 從客觀發現提取
        objective_text = soap_note.objective.content.lower()
        objective_keywords = ["體溫升高", "血壓異常", "心跳過快", "呼吸音異常"]

        for keyword in objective_keywords:
            if keyword in objective_text:
                symptoms.append(keyword)

        # 去重複
        return list(set(symptoms))

    def match_diagnoses(
        self,
        symptoms: List[str],
        patient: Optional[Patient] = None,
    ) -> DiagnosisResult:
        """匹配症狀與診斷

        Args:
            symptoms: 症狀列表
            patient: 病患資訊

        Returns:
            診斷結果
        """
        start_time = datetime.now()

        # 建立診斷結果
        result = DiagnosisResult(
            source_text=", ".join(symptoms),
            patient_id=patient.patient_id if patient else None,
            processing_time_ms=0,  # 初始值，稍後會更新
            metadata={
                "patient_age": patient.get_age() if patient else None,
                "patient_gender": patient.info.gender if patient else None,
                "symptom_count": len(symptoms),
            },
        )

        # 規則匹配
        for rule in self._diagnosis_rules:
            matched_symptoms = [s for s in rule["symptoms"] if s in symptoms]

            if matched_symptoms:
                match_ratio = len(matched_symptoms) / len(rule["symptoms"])
                confidence = rule["confidence"] * match_ratio

                # 根據病患年齡調整信心度
                if patient:
                    age = patient.get_age()
                    if age is not None and (age < 18 or age > 65):
                        confidence *= 0.9  # 極端年齡信心度稍降

                for icd10_code in rule["icd10_codes"]:
                    # 取得 ICD-10 詳細資訊
                    icd10_diagnosis = self.icd10_adapter.search_by_code(icd10_code)

                    diagnosis = Diagnosis(
                        icd10_code=icd10_code,
                        name=icd10_diagnosis.name if icd10_diagnosis else rule["name"],
                        name_en=icd10_diagnosis.name_en if icd10_diagnosis else "",
                        confidence=min(confidence, 0.95),  # 上限 95%
                        confidence_level=DiagnosisConfidence.HIGH
                        if min(confidence, 0.95) >= 0.8
                        else DiagnosisConfidence.MEDIUM,
                        symptoms=matched_symptoms,
                        differential_diagnoses=[],
                        recommendations=self._generate_recommendations(
                            icd10_code, matched_symptoms
                        ),
                        severity=self._assess_severity(matched_symptoms),
                        onset="近期",
                        duration="急性",
                        notes="基於症狀匹配規則",
                    )

                    result.add_diagnosis(diagnosis)

        # ICD-10 直接搜尋
        if symptoms:
            symptom_text = " ".join(symptoms)
            icd10_results = self.icd10_adapter.search(symptom_text, limit=5)

            for icd10_item in icd10_results:
                # 避免重複
                if not result.get_by_code(icd10_item["code"]):
                    # 計算症狀匹配度
                    symptom_match = self._calculate_symptom_match(icd10_item, symptoms)

                    if symptom_match > 0.3:  # 匹配度門檻
                        diagnosis = Diagnosis(
                            icd10_code=icd10_item["code"],
                            name=icd10_item.get("name_cn", icd10_item.get("name", "")),
                            name_en=icd10_item.get("name_en", ""),
                            confidence=symptom_match * 0.8,  # 調整信心度
                            confidence_level=DiagnosisConfidence.HIGH
                            if symptom_match * 0.8 >= 0.8
                            else DiagnosisConfidence.MEDIUM,
                            symptoms=symptoms,
                            differential_diagnoses=[],
                            recommendations=self._generate_recommendations(
                                icd10_item["code"], symptoms
                            ),
                            severity=self._assess_severity(symptoms),
                            onset="近期",
                            duration="急性",
                            notes="基於症狀關鍵字匹配",
                        )

                        result.add_diagnosis(diagnosis)

        # 計算處理時間
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        result.processing_time_ms = int(processing_time)

        logger.info(
            f"診斷匹配完成: {len(result.diagnoses)} 個診斷, 處理時間: {processing_time:.0f}ms"
        )

        return result

    def _calculate_symptom_match(
        self,
        icd10_item: Dict[str, Any],
        symptoms: List[str],
    ) -> float:
        """計算症狀匹配度

        Args:
            icd10_item: ICD-10 項目
            symptoms: 症狀列表

        Returns:
            匹配度 (0.0-1.0)
        """
        # 從 ICD-10 名稱提取關鍵字
        name_cn = icd10_item.get("name_cn", "")
        name_en = icd10_item.get("name_en", "")

        # 建立關鍵字列表
        keywords = []
        if name_cn:
            keywords.extend(re.findall(r"[\u4e00-\u9fff]+", name_cn))
        if name_en:
            # 簡單的英文單詞提取
            keywords.extend(re.findall(r"\b[a-zA-Z]+\b", name_en.lower()))

        # 計算匹配
        if not keywords:
            return 0.0

        symptom_text = " ".join(symptoms).lower()
        matched_keywords = [kw for kw in keywords if kw.lower() in symptom_text]

        return len(matched_keywords) / len(keywords)

    def _generate_recommendations(
        self,
        icd10_code: str,
        symptoms: List[str],
    ) -> List[str]:
        """生成建議事項

        Args:
            icd10_code: ICD-10 代碼
            symptoms: 症狀列表

        Returns:
            建議事項列表
        """
        recommendations = []

        # 根據 ICD-10 章節生成建議
        chapter = icd10_code[0] if icd10_code else ""

        if chapter in ["A", "B"]:  # 傳染病
            recommendations.extend(
                [
                    "感染控制措施",
                    "必要時隔離",
                    "追蹤接觸者",
                ]
            )

        if chapter in ["I"]:  # 循環系統疾病
            recommendations.extend(
                [
                    "監測生命徵象",
                    "心電圖檢查",
                    "必要時轉介心臟科",
                ]
            )

        if chapter in ["J"]:  # 呼吸系統疾病
            recommendations.extend(
                [
                    "呼吸功能評估",
                    "胸部X光檢查",
                    "必要時使用氧氣",
                ]
            )

        if "發燒" in symptoms:
            recommendations.append("監測體溫，必要時使用退燒藥")

        if "呼吸困難" in symptoms:
            recommendations.append("評估呼吸狀態，必要時緊急處置")

        if "胸痛" in symptoms:
            recommendations.append("排除心臟問題，必要時緊急處置")

        # 一般建議
        recommendations.extend(
            [
                "充分休息",
                "適當水分補充",
                "症狀惡化時立即就醫",
            ]
        )

        return recommendations

    def _assess_severity(self, symptoms: List[str]) -> str:
        """評估嚴重程度

        Args:
            symptoms: 症狀列表

        Returns:
            嚴重程度
        """
        severe_symptoms = ["呼吸困難", "胸痛", "意識不清", "大量出血"]
        moderate_symptoms = ["發燒", "劇烈疼痛", "持續嘔吐", "無法進食"]

        if any(symptom in symptoms for symptom in severe_symptoms):
            return "嚴重"
        elif any(symptom in symptoms for symptom in moderate_symptoms):
            return "中度"
        else:
            return "輕度"

    def analyze_soap(
        self,
        soap_note: SOAPNote,
        patient: Optional[Patient] = None,
    ) -> DiagnosisResult:
        """分析 SOAP 病歷

        Args:
            soap_note: SOAP 病歷
            patient: 病患資訊

        Returns:
            診斷結果
        """
        logger.info(f"開始分析 SOAP 病歷: {soap_note.total_word_count} 字")

        # 提取症狀
        symptoms = self.extract_symptoms(soap_note)
        logger.info(f"提取症狀: {len(symptoms)} 個 - {symptoms}")

        # 匹配診斷
        result = self.match_diagnoses(symptoms, patient)

        # 添加元數據
        result.metadata.update(
            {
                "soap_word_count": soap_note.total_word_count,
                "extracted_symptoms": symptoms,
                "soap_has_plan": soap_note.has_plan,
            }
        )

        return result

    def search_diagnoses(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜尋診斷

        Args:
            query: 搜尋查詢
            limit: 結果數量限制

        Returns:
            診斷搜尋結果
        """
        return self.icd10_adapter.search(query, limit=limit)

    def get_diagnosis_details(self, icd10_code: str) -> Optional[Dict[str, Any]]:
        """取得診斷詳細資訊

        Args:
            icd10_code: ICD-10 代碼

        Returns:
            診斷詳細資訊
        """
        return self.icd10_adapter.get_code_info(icd10_code)
