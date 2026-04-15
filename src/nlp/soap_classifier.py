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

    # 各類別關鍵字 (由 prompt.md 同步)
    KEYWORDS = {
        "subjective": [
            "乏力", "乾渴", "便祕", "便秘", "冰冷", "出汗", "厭食", "口乾", "口渴", "吐",
            "呼吸困難", "咳", "咳嗽", "喉嚨痛", "喉痛", "喘", "喘不過氣", "嘔吐", "噁心",
            "四肢無力", "夜間頻尿", "失眠", "尿頻", "心悸", "心臟跳動", "心跳加速", "怕冷",
            "手腳冰冷", "打噴嚏", "搔癢", "撕裂傷", "暈", "暈眩", "月經", "模糊",
            "沒精神", "沒胃口", "流鼻水", "消瘦", "無力", "無力感", "生理期", "疲倦",
            "疲勞", "疼痛", "痛", "痠", "癢", "發汗", "發熱", "發燒", "發胖", "皮膚",
            "看不清", "眩暈", "眼睛", "睡眠不足", "睡眠障礙", "紅疹", "經期", "耳鳴",
            "聽力下降", "肌肉無力", "肚子痛", "肚痛", "肥胖", "胃口", "胃痛", "胸悶",
            "胸痛", "胸部不適", "脹", "腹瀉", "腹痛", "視力", "起疹子", "酸", "頭暈",
            "頭痛", "頻尿", "食慾", "體重", "體重下降", "鼻塞",
            # 英文關鍵字保留以便支援多語系
            "pain", "itch", "dizzy", "cough", "fever", "tired", "nausea",
            "vomiting", "diarrhea", "constipation", "headache", "insomnia",
            "anxiety", "palpitation", "dyspnea", "fatigue",
        ],
        "objective": [
            "ALT", "AST", "CT", "ECG", "EKG", "GOT", "GPT", "Hb", "MRI", "RBC", "WBC",
            "三酸甘油酯", "低密度脂蛋白", "內視鏡", "反射", "叩診", "呼吸頻率", "四肢",
            "大腸鏡", "實質", "尿潛血", "尿糖", "尿素氮", "尿蛋白", "心跳", "心電圖",
            "感覺", "擴大", "核磁共振", "檢查", "浸潤", "液體", "淋巴結", "甲狀腺",
            "白血球", "瞳孔", "神經學檢查", "積液", "紅血球", "結節", "聽診", "肌酸酐",
            "肝功能", "肝脾", "肥厚", "肫瘤", "胃鏡", "胸水", "胸部X光", "胸部攝影",
            "脈搏", "脊椎", "腫塊", "腹水", "腹部", "腺體", "膽固醇", "膽紅素", "萎縮",
            "血壓", "血小板", "血氧", "血清", "血管", "血糖", "血紅蛋白", "血脂",
            "視診", "觸診", "超音波", "運動", "關節", "陰影", "體溫",
            # 英文
            "erythema", "swelling", "blister", "bullae", "blood pressure",
            "heart rate", "temperature", "respiration", "xray", "x-ray", "ultrasound",
            "finding", "examination",
        ],
        "assessment": [
            "中風", "代謝症候群", "低血壓", "低血糖", "初步診斷", "十二指腸潰瘍", "可能",
            "大腸激躁症", "失眠症", "尿酸", "心臟病", "惡性腫瘤", "感冒", "感染", "憂鬱症",
            "扭傷", "排除", "支氣管炎", "椎間盤突出", "流感", "濕疹", "焦慮症", "甲狀腺",
            "甲狀腺亢進", "甲狀腺低下", "疑似", "痛風", "癌症", "發炎", "發炎症狀",
            "皮膚炎", "皮膚病", "符合", "糖尿病", "肌肉拉傷", "肝炎", "肝硬化", "肥胖症",
            "肺炎", "胃潰瘍", "胃炎", "腎臟病", "腦梗塞", "腦血管", "腫瘤", "腰椎",
            "腸胃炎", "膽囊炎", "膽囊結石", "膽結石", "臨床診斷", "蕁麻疹", "診斷",
            "診為", "貧血", "過敏", "過敏反應", "過敏性", "鑑別", "關節炎", "頸椎",
            "類風濕", "骨折", "骨關節炎", "高血壓", "高血脂",
            # 英文
            "diagnosis", "assess", "suggest", "suspect", "confirm", "likely",
        ],
        "plan": [
            "不受風", "不要", "中醫", "休息", "低糖", "低脂", "低鹽", "住院",
            "保持溫暖", "保暖", "健康教育", "備註", "充足睡眠", "出院", "出院後", "刮痧",
            "化學治療", "化療", "吃藥", "回診", "增重", "多喝水", "定期", "定期回診",
            "定期檢查", "居家觀察", "復健", "復建", "急診", "急診就醫", "戒菸", "戒酒",
            "手術", "打針", "投予", "抗生素", "拔罐", "放射治療", "放射線", "服用",
            "止咳", "止痛", "水分", "治療", "治療方式", "治療計畫", "注射", "注意事項",
            "減重", "物理治療", "特別注意", "用藥", "監測", "睡眠", "禁止", "禁菸", "禁酒",
            "肌肉注射", "腹膜透析", "膏藥", "藥物", "血液透析", "衛教", "補充水分",
            "複查", "複診", "複驗", "觀察", "貼", "貼布", "貼藥", "輸液", "轉介",
            "轉診", "轉送", "轉院", "追蹤", "追蹤檢查", "退燒", "透析", "運動",
            "適度運動", "避免", "針灸", "開刀", "開刀房", "靜脈注射", "靜脈輸液",
            "飲食", "飲食控制", "飲食衛教", "體重控制", "麻醉", "點滴",
            # 英文
            "medication", "treatment", "follow-up", "prescription", "advice",
        ],
    }

    def __init__(self, threshold: float = 0.05):
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

            # 修改置信度計算：每個匹配關鍵字給予 0.2 的基本分數，最高 1.0
            # 這樣短句子只要有一個關鍵字就能達到 0.2，超過 0.05 閾值
            score = min(len(matches) * 0.25, 1.0)

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
