"""
醫療術語標準化模組

提供口語中文轉專業醫療英文術語的映射功能
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TermMapping:
    """術語映射資料結構"""
    original: str  # 原始口語中文
    standard: str  # 標準醫療英文
    category: str  # 類別 (symptom, anatomy, procedure, medication)
    confidence: float  # 置信度
    icd10_candidates: Optional[List[str]] = None  # 可能的 ICD-10 代碼


class MedicalTerminologyMapper:
    """醫療術語映射器"""

    # 口語中文 -> 專業英文映射表
    CHINESE_TO_ENGLISH = {
        # 症狀類
        "胸悶": ("chest tightness", "symptom", ["R07.89"]),
        "胸痛": ("chest pain", "symptom", ["R07.9"]),
        "頭痛": ("headache", "symptom", ["R51"]),
        "頭暈": ("dizziness", "symptom", ["R42"]),
        "發燒": ("fever", "symptom", ["R50.9"]),
        "咳嗽": ("cough", "symptom", ["R05"]),
        "喘": ("dyspnea", "symptom", ["R06.02"]),
        "呼吸困難": ("dyspnea", "symptom", ["R06.02"]),
        "腹痛": ("abdominal pain", "symptom", ["R10.9"]),
        "腹瀉": ("diarrhea", "symptom", ["R19.7"]),
        "便秘": ("constipation", "symptom", ["K59.0"]),
        "噁心": ("nausea", "symptom", ["R11.0"]),
        "嘔吐": ("vomiting", "symptom", ["R11.2"]),
        "疲倦": ("fatigue", "symptom", ["R53.83"]),
        "失眠": ("insomnia", "symptom", ["G47.0"]),
        "心悸": ("palpitation", "symptom", ["R00.2"]),
        "水腫": ("edema", "symptom", ["R60.9"]),
        "紅腫": ("erythema and swelling", "symptom", ["L20.83"]),
        "很痛": ("severe pain", "symptom", ["R52"]),
        "很癢": ("pruritus", "symptom", ["L29.9"]),
        "水泡": ("blister", "symptom", ["L10.9"]),
        "起水泡": ("blister formation", "symptom", ["L10.9"]),
        "燙傷": ("scald burn", "symptom", ["T30.0"]),
        "二度燙傷": ("second-degree burn", "symptom", ["T30.2"]),
        "傷口外圍癢": ("peri-wound pruritus", "symptom", ["L29.9"]),
        
        # 解剖部位
        "胸部": ("chest", "anatomy", []),
        "腹部": ("abdomen", "anatomy", []),
        "頭部": ("head", "anatomy", []),
        "手部": ("hand", "anatomy", []),
        "腳部": ("foot", "anatomy", []),
        "背部": ("back", "anatomy", []),
        "頸部": ("neck", "anatomy", []),
        "手臂": ("arm", "anatomy", []),
        "腿部": ("leg", "anatomy", []),
        "膝蓋": ("knee", "anatomy", []),
        "肩膀": ("shoulder", "anatomy", []),
        "腰部": ("waist", "anatomy", []),
        "眼睛": ("eye", "anatomy", []),
        "耳朵": ("ear", "anatomy", []),
        "鼻子": ("nose", "anatomy", []),
        "喉嚨": ("throat", "anatomy", []),
        "心臟": ("heart", "anatomy", []),
        "肺": ("lung", "anatomy", []),
        "肝": ("liver", "anatomy", []),
        "腎": ("kidney", "anatomy", []),
        "胃": ("stomach", "anatomy", []),
        "腸": ("intestine", "anatomy", []),
        "膀胱": ("bladder", "anatomy", []),
        
        # 診斷相關
        "高血壓": ("hypertension", "diagnosis", ["I10"]),
        "糖尿病": ("diabetes mellitus", "diagnosis", ["E11.9"]),
        "肺炎": ("pneumonia", "diagnosis", ["J18.9"]),
        "支氣管炎": ("bronchitis", "diagnosis", ["J40"]),
        "胃炎": ("gastritis", "diagnosis", ["K29.7"]),
        "尿道炎": ("urethritis", "diagnosis", ["N34.2"]),
        "皮膚炎": ("dermatitis", "diagnosis", ["L30.9"]),
        "感染": ("infection", "diagnosis", ["A49.9"]),
        "發炎": ("inflammation", "diagnosis", []),
        "骨折": ("fracture", "diagnosis", ["S72.9"]),
        "扭傷": ("sprain", "diagnosis", ["S93.4"]),
        "過敏": ("allergy", "diagnosis", ["T78.40"]),
        
        # 檢查/處置
        "量血壓": ("blood pressure measurement", "procedure", []),
        "照 X 光": ("X-ray examination", "procedure", []),
        "抽血": ("blood draw", "procedure", []),
        "驗尿": ("urinalysis", "procedure", []),
        "心電圖": ("ECG", "procedure", []),
        "超音波": ("ultrasound", "procedure", []),
        "CT": ("CT scan", "procedure", []),
        "MRI": ("MRI scan", "procedure", []),
        "換藥": ("dressing change", "procedure", []),
        "縫合": ("suturing", "procedure", []),
        "開藥": ("prescription", "procedure", []),
        "打針": ("injection", "procedure", []),
        "點滴": ("IV infusion", "procedure", []),
    }

    def __init__(self, vocab_file: Optional[str] = None):
        """
        初始化醫療術語映射器

        Args:
            vocab_file: 可選的外部詞彙庫 JSON 檔案路徑
        """
        self._mappings: Dict[str, TermMapping] = {}
        self._load_builtin_mappings()
        
        if vocab_file:
            self._load_external_vocab(vocab_file)

    def _load_builtin_mappings(self) -> None:
        """載入內建映射表"""
        for chinese, (english, category, icd10_list) in self.CHINESE_TO_ENGLISH.items():
            self._mappings[chinese] = TermMapping(
                original=chinese,
                standard=english,
                category=category,
                confidence=0.95,
                icd10_candidates=icd10_list if icd10_list else None,
            )
        logger.info(f"Loaded {len(self._mappings)} built-in term mappings")

    def _load_external_vocab(self, vocab_file: str) -> None:
        """載入外部詞彙庫"""
        path = Path(vocab_file)
        if not path.exists():
            logger.warning(f"External vocab file not found: {vocab_file}")
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                vocab = json.load(f)

            # 處理醫療詞彙庫格式
            for category, words in vocab.items():
                if isinstance(words, list):
                    for word in words:
                        # 如果詞彙已在內建表中，跳過
                        if word not in self._mappings:
                            self._mappings[word] = TermMapping(
                                original=word,
                                standard=word,  # 英文詞彙保持不變
                                category=category,
                                confidence=0.8,
                            )
            logger.info(f"Loaded external vocabulary from {vocab_file}")
        except Exception as e:
            logger.error(f"Failed to load external vocab: {e}")

    def map_term(self, text: str) -> Optional[TermMapping]:
        """
        映射單一術語

        Args:
            text: 輸入文字（中文或英文）

        Returns:
            TermMapping 或 None
        """
        # 直接匹配
        if text in self._mappings:
            return self._mappings[text]

        # 部分匹配（最長匹配優先）
        for key in sorted(self._mappings.keys(), key=len, reverse=True):
            if key in text:
                return self._mappings[key]

        return None

    def map_text(self, text: str) -> Tuple[str, List[TermMapping]]:
        """
        映射整段文字，將口語中文轉為專業英文

        Args:
            text: 輸入文字

        Returns:
            (轉換後文字，映射記錄列表)
        """
        mappings_found: List[TermMapping] = []
        result = text

        # 依長度排序，先處理長詞
        sorted_terms = sorted(
            self._mappings.keys(),
            key=len,
            reverse=True
        )

        for term in sorted_terms:
            if term in result:
                mapping = self._mappings[term]
                result = result.replace(term, mapping.standard)
                mappings_found.append(mapping)

        return result, mappings_found

    def get_all_mappings(self) -> Dict[str, TermMapping]:
        """取得所有映射"""
        return self._mappings.copy()

    def get_mappings_by_category(self, category: str) -> List[TermMapping]:
        """依類別取得映射"""
        return [
            m for m in self._mappings.values()
            if m.category == category
        ]

    def add_mapping(
        self,
        chinese: str,
        english: str,
        category: str = "symptom",
        icd10: Optional[List[str]] = None,
        confidence: float = 0.9,
    ) -> None:
        """
        新增自定義映射

        Args:
            chinese: 口語中文
            english: 專業英文
            category: 類別
            icd10: ICD-10 代碼列表
            confidence: 置信度
        """
        self._mappings[chinese] = TermMapping(
            original=chinese,
            standard=english,
            category=category,
            confidence=confidence,
            icd10_candidates=icd10,
        )

    def __len__(self) -> int:
        """取得映射總數"""
        return len(self._mappings)

    def __repr__(self) -> str:
        """字串表示"""
        return f"MedicalTerminologyMapper(mappings={len(self._mappings)})"
