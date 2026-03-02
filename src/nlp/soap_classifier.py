"""
SOAP 分類器模組

使用關鍵字規則進行 S/O/A/P 分類
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SOAPClassification:
    """SOAP 分類結果"""
    text: str  # 原始文字
    category: str  # S/O/A/P
    confidence: float  # 置信度
    matched_keywords: List[str]  # 匹配的關鍵詞


class SOAPClassifier:
    """SOAP 分類器"""

    # 各類別關鍵字
    KEYWORDS = {
        "subjective": [
            # 症狀（中文）
            "痛", "癢", "暈", "咳", "燒", "燙", "疲倦", "沒胃口", "嘔吐", "噁心",
            "胸悶", "喘", "腹瀉", "便秘", "頭痛", "頭暈", "失眠", "焦慮",
            "心悸", "腹脹", "抽筋", "麻木", "耳鳴", "視力模糊",
            # 症狀（英文）
            "pain", "itch", "dizzy", "cough", "fever", "tired", "nausea",
            "vomiting", "diarrhea", "constipation", "headache", "insomnia",
            "anxiety", "palpitation", "dyspnea", "fatigue",
        ],
        "objective": [
            # 檢查測量（中文）
            "紅腫", "水泡", "血壓", "心跳", "體溫", "呼吸", "觸診", "影像",
            "化驗", "檢查", "TBSA", "聽診", "叩診", "X 光", "超音波",
            # 檢查測量（英文）
            "erythema", "swelling", "blister", "bullae", "blood pressure",
            "heart rate", "temperature", "respiration", "X-ray", "ultrasound",
            "CT", "MRI", "ECG", "lab", "test", "examination", "finding",
        ],
        "assessment": [
            # 診斷（中文）
            "診斷", "初判", "可能", "疑似", "感染", "ICD", "確定", "臨床",
            # 診斷（英文）
            "diagnosis", "assess", "suggest", "suspect", "confirm", "likely",
            "probable", "consistent with", "indicative of",
        ],
        "plan": [
            # 治療（中文）
            "換藥", "上藥", "追蹤", "開藥", "衛教", "回診", "治療", "用藥",
            "手術", "復健", "飲食", "運動", "檢查", "檢驗", "轉診",
            # 治療（英文）
            "medication", "treatment", "follow-up", "prescription", "surgery",
            "therapy", "diet", "exercise", "referral", "advice", "plan",
        ],
    }

    def __init__(self, threshold: float = 0.3):
        """
        初始化 SOAP 分類器

        Args:
            threshold: 置信度閾值，低於此值歸類為 unknown
        """
        self.threshold = threshold

    def classify(self, text: str) -> SOAPClassification:
        """
        分類單一句子

        Args:
            text: 輸入文字

        Returns:
            SOAPClassification 分類結果
        """
        text_lower = text.lower()
        best_match: Optional[SOAPClassification] = None
        best_score = 0.0

        for category, keywords in self.KEYWORDS.items():
            matches = [kw for kw in keywords if kw.lower() in text_lower]
            if not matches:
                continue

            # 計算置信度：匹配關鍵字數 / 總關鍵字數
            score = len(matches) / len(keywords) * 2  # 放大 2 倍
            score = min(score, 1.0)  # 限制在 1.0 以內

            if score > best_score:
                best_score = score
                best_match = SOAPClassification(
                    text=text,
                    category=category,
                    confidence=score,
                    matched_keywords=matches,
                )

        # 低於閾值，歸類為 unknown
        if best_score < self.threshold:
            return SOAPClassification(
                text=text,
                category="unknown",
                confidence=best_score,
                matched_keywords=[],
            )

        return best_match

    def classify_batch(self, texts: List[str]) -> List[SOAPClassification]:
        """
        批次分類多個句子

        Args:
            texts: 文字列表

        Returns:
            SOAPClassification 列表
        """
        return [self.classify(text) for text in texts]

    def classify_to_dict(self, text: str) -> Dict:
        """
        分類並回傳字典格式

        Args:
            text: 輸入文字

        Returns:
            分類結果字典
        """
        result = self.classify(text)
        return {
            "text": result.text,
            "category": result.category,
            "confidence": result.confidence,
            "matched_keywords": result.matched_keywords,
        }

    def group_by_category(
        self,
        texts: List[str],
    ) -> Dict[str, List[SOAPClassification]]:
        """
        將文字依 SOAP 類別分組

        Args:
            texts: 文字列表

        Returns:
            依類別分組的字典
        """
        grouped: Dict[str, List[SOAPClassification]] = {
            "subjective": [],
            "objective": [],
            "assessment": [],
            "plan": [],
            "unknown": [],
        }

        for text in texts:
            result = self.classify(text)
            if result.category in grouped:
                grouped[result.category].append(result)
            else:
                grouped["unknown"].append(result)

        # 移除空列表
        return {k: v for k, v in grouped.items() if v}

    def __repr__(self) -> str:
        """字串表示"""
        return f"SOAPClassifier(categories={len(self.KEYWORDS)})"
