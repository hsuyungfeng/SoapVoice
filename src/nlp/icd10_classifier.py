"""
ICD-10 分類器模組

提供症狀描述到 ICD-10 代碼的映射功能
"""

import logging
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ICD10Match:
    """ICD-10 匹配結果"""
    code: str  # ICD-10 代碼
    description: str  # 描述（英文）
    description_zh: str  # 描述（中文）
    category: str  # 類別
    confidence: float  # 置信度
    matched_keywords: List[str]  # 匹配的關鍵詞


class ICD10Classifier:
    """ICD-10 分類器"""

    # 症狀關鍵字 -> ICD-10 映射
    SYMPTOM_TO_ICD10 = {
        # 呼吸系統症狀
        "胸悶": [("R07.89", "Chest tightness", "胸悶", "Respiratory", 0.9)],
        "胸痛": [("R07.9", "Chest pain, unspecified", "胸痛未特指", "Respiratory", 0.9)],
        "喘": [("R06.02", "Shortness of breath", "呼吸急促", "Respiratory", 0.85)],
        "呼吸困難": [("R06.02", "Shortness of breath", "呼吸急促", "Respiratory", 0.9)],
        "咳嗽": [("R05", "Cough", "咳嗽", "Respiratory", 0.9)],
        "咳血": [("R04.2", "Hemoptysis", "咳血", "Respiratory", 0.95)],
        
        # 全身性症狀
        "發燒": [("R50.9", "Fever, unspecified", "發燒未特指", "General", 0.9)],
        "疲倦": [("R53.83", "Other fatigue", "其他疲倦", "General", 0.85)],
        "體重減輕": [("R63.4", "Abnormal weight loss", "異常體重減輕", "General", 0.85)],
        "盜汗": [("R61", "Hyperhidrosis", "多汗症", "General", 0.8)],
        
        # 神經系統症狀
        "頭痛": [("R51", "Headache", "頭痛", "Neurological", 0.9)],
        "頭暈": [("R42", "Dizziness and giddiness", "頭暈", "Neurological", 0.85)],
        "暈倒": [("R55", "Syncope and collapse", "暈厥和虛脫", "Neurological", 0.9)],
        "失眠": [("G47.0", "Disorders of initiating and maintaining sleep", "失眠症", "Neurological", 0.85)],
        "焦慮": [("F41.9", "Anxiety disorder, unspecified", "焦慮症未特指", "Psychiatric", 0.8)],
        
        # 消化系統症狀
        "腹痛": [("R10.9", "Unspecified abdominal pain", "腹痛未特指", "Digestive", 0.85)],
        "腹瀉": [("R19.7", "Diarrhea, unspecified", "腹瀉未特指", "Digestive", 0.9)],
        "便秘": [("K59.0", "Constipation", "便秘", "Digestive", 0.9)],
        "噁心": [("R11.0", "Nausea", "噁心", "Digestive", 0.85)],
        "嘔吐": [("R11.2", "Vomiting", "嘔吐", "Digestive", 0.9)],
        "胃灼熱": [("R12", "Heartburn", "胃灼熱", "Digestive", 0.85)],
        
        # 心血管系統症狀
        "心悸": [("R00.2", "Palpitations", "心悸", "Cardiovascular", 0.85)],
        "心跳過快": [("R00.0", "Tachycardia, unspecified", "心搏過速未特指", "Cardiovascular", 0.85)],
        "心跳過慢": [("R00.1", "Bradycardia, unspecified", "心搏過緩未特指", "Cardiovascular", 0.85)],
        "高血壓": [("I10", "Essential (primary) hypertension", "原發性高血壓", "Cardiovascular", 0.9)],
        "低血壓": [("I95.9", "Hypotension, unspecified", "低血壓未特指", "Cardiovascular", 0.85)],
        
        # 肌肉骨骼症狀
        "背痛": [("M54.9", "Dorsalgia, unspecified", "背痛未特指", "Musculoskeletal", 0.85)],
        "頸痛": [("M54.2", "Cervicalgia", "頸痛", "Musculoskeletal", 0.85)],
        "關節痛": [("M25.50", "Pain in unspecified joint", "關節痛未特指", "Musculoskeletal", 0.85)],
        "肌肉痛": [("M79.1", "Myalgia", "肌痛", "Musculoskeletal", 0.85)],
        
        # 皮膚症狀
        "紅腫": [("L20.83", "Atopic dermatitis", "異位性皮膚炎", "Dermatological", 0.75)],
        "皮疹": [("R21", "Rash and other nonspecific skin eruption", "皮疹", "Dermatological", 0.85)],
        "癢": [("L29.9", "Pruritus, unspecified", "癢未特指", "Dermatological", 0.85)],
        "水泡": [("L10.9", "Pemphigus, unspecified", "天皰瘡未特指", "Dermatological", 0.7)],
        "燙傷": [("T30.0", "Burn of unspecified degree", "燙傷未特指程度", "Injury", 0.8)],
        
        # 泌尿系統症狀
        "頻尿": [("R35.0", "Frequency of micturition", "尿頻", "Genitourinary", 0.9)],
        "尿急": [("R39.15", "Urgency of urination", "尿急", "Genitourinary", 0.9)],
        "尿痛": [("R30.9", "Painful micturition, unspecified", "排尿痛未特指", "Genitourinary", 0.85)],
        "血尿": [("R31.9", "Hematuria, unspecified", "血尿未特指", "Genitourinary", 0.9)],
        
        # 常見診斷
        "糖尿病": [("E11.9", "Type 2 diabetes mellitus without complications", "第 2 型糖尿病無併發症", "Endocrine", 0.9)],
        "肺炎": [("J18.9", "Pneumonia, unspecified organism", "肺炎未特指病原體", "Respiratory", 0.85)],
        "支氣管炎": [("J40", "Bronchitis, not specified as acute or chronic", "支氣管炎", "Respiratory", 0.85)],
        "胃炎": [("K29.7", "Gastritis, unspecified", "胃炎未特指", "Digestive", 0.85)],
        "過敏": [("T78.40", "Allergy, unspecified, initial encounter", "過敏未特指", "Immunological", 0.8)],
        "感染": [("A49.9", "Bacterial infection, unspecified", "細菌感染未特指", "Infectious", 0.75)],
    }

    # ICD-10 類別描述
    CATEGORY_DESCRIPTIONS = {
        "Respiratory": "呼吸系統",
        "General": "全身性",
        "Neurological": "神經系統",
        "Psychiatric": "精神科",
        "Digestive": "消化系統",
        "Cardiovascular": "心血管系統",
        "Musculoskeletal": "肌肉骨骼系統",
        "Dermatological": "皮膚科",
        "Injury": "外傷",
        "Genitourinary": "泌尿生殖系統",
        "Endocrine": "內分泌系統",
        "Infectious": "感染症",
        "Immunological": "免疫系統",
    }

    def __init__(self):
        """初始化 ICD-10 分類器"""
        self._matches_cache: Dict[str, List[ICD10Match]] = {}

    def classify(self, text: str) -> List[ICD10Match]:
        """
        分類文字，找出可能的 ICD-10 代碼

        Args:
            text: 輸入文字（症狀描述）

        Returns:
            ICD10Match 列表，依置信度排序
        """
        # 檢查快取
        if text in self._matches_cache:
            return self._matches_cache[text]

        matches: List[ICD10Match] = []
        text_lower = text.lower()

        # 搜尋所有關鍵字
        for keyword, icd_list in self.SYMPTOM_TO_ICD10.items():
            if keyword.lower() in text_lower:
                for code, desc_en, desc_zh, category, confidence in icd_list:
                    matches.append(ICD10Match(
                        code=code,
                        description=desc_en,
                        description_zh=desc_zh,
                        category=category,
                        confidence=confidence,
                        matched_keywords=[keyword],
                    ))

        # 依置信度排序
        matches.sort(key=lambda x: x.confidence, reverse=True)

        # 移除重複代碼（保留最高置信度）
        seen_codes = set()
        unique_matches = []
        for match in matches:
            if match.code not in seen_codes:
                seen_codes.add(match.code)
                unique_matches.append(match)

        # 快取結果
        self._matches_cache[text] = unique_matches

        return unique_matches

    def classify_with_context(
        self,
        text: str,
        patient_age: Optional[int] = None,
        patient_gender: Optional[str] = None,
    ) -> List[ICD10Match]:
        """
        帶入病患背景進行分類

        Args:
            text: 症狀描述
            patient_age: 病患年齡
            patient_gender: 病患性別

        Returns:
            ICD10Match 列表
        """
        matches = self.classify(text)

        # 根據年齡和性別調整置信度
        for match in matches:
            # 年齡相關調整
            if patient_age is not None:
                if match.code.startswith("I") and patient_age > 50:  # 心血管疾病
                    match.confidence = min(match.confidence + 0.05, 1.0)
                if match.code.startswith("E") and patient_age > 40:  # 內分泌疾病
                    match.confidence = min(match.confidence + 0.05, 1.0)

            # 性別相關調整
            if patient_gender:
                if patient_gender.upper() == "M":
                    if match.code.startswith("N40"):  # 前列腺疾病
                        match.confidence = min(match.confidence + 0.1, 1.0)
                elif patient_gender.upper() == "F":
                    if match.code.startswith("N80"):  # 子宮內膜異位
                        match.confidence = min(match.confidence + 0.1, 1.0)

        # 重新排序
        matches.sort(key=lambda x: x.confidence, reverse=True)
        return matches

    def get_category_name(self, category: str) -> str:
        """取得類別的中文名稱"""
        return self.CATEGORY_DESCRIPTIONS.get(category, category)

    def get_all_categories(self) -> Dict[str, str]:
        """取得所有類別"""
        return self.CATEGORY_DESCRIPTIONS.copy()

    def search_by_code(self, code: str) -> Optional[ICD10Match]:
        """
        依 ICD-10 代碼搜尋

        Args:
            code: ICD-10 代碼

        Returns:
            ICD10Match 或 None
        """
        for keyword, icd_list in self.SYMPTOM_TO_ICD10.items():
            for c, desc_en, desc_zh, category, confidence in icd_list:
                if c == code:
                    return ICD10Match(
                        code=code,
                        description=desc_en,
                        description_zh=desc_zh,
                        category=category,
                        confidence=confidence,
                        matched_keywords=[keyword],
                    )
        return None

    def __repr__(self) -> str:
        """字串表示"""
        return f"ICD10Classifier(symptoms={len(self.SYMPTOM_TO_ICD10)})"
