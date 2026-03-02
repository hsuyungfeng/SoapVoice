"""
SOAP 生成模組

將醫療對話轉換成結構化 SOAP 病歷
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.llm.ollama_engine import OllamaEngine, ModelConfig


logger = logging.getLogger(__name__)


# SOAP 分類關鍵字
SOAP_KEYWORDS = {
    "subjective": [
        "痛", "癢", "暈", "咳", "燒", "燙", "疲倦", "沒胃口", "嘔吐", "噁心",
        "胸悶", "喘", "腹瀉", "便秘", "頭痛", "頭暈", "失眠", "焦慮",
        "心悸", "腹脹", "抽筋", "麻木", "耳鳴", "視力模糊",
        "pain", "itch", "dizzy", "cough", "fever", "tired", "nausea",
        "vomiting", "diarrhea", "constipation", "headache", "insomnia",
        "anxiety", "palpitation", "dyspnea", "fatigue",
    ],
    "objective": [
        "紅腫", "水泡", "血壓", "心跳", "體溫", "呼吸", "觸診", "影像",
        "化驗", "檢查", "TBSA", "聽診", "叩診", "X 光", "超音波", "X 射線",
        "erythema", "swelling", "blister", "bullae", "blood pressure",
        "heart rate", "temperature", "respiration", "xray", "x-ray", "ultrasound",
        "ct", "mri", "ecg", "lab", "test", "examination", "finding",
    ],
    "assessment": [
        "診斷", "初判", "可能", "疑似", "感染", "ICD", "確定", "臨床",
        "diagnosis", "assess", "suggest", "suspect", "confirm", "likely",
        "probable", "consistent with", "indicative of",
    ],
    "plan": [
        "換藥", "上藥", "追蹤", "開藥", "衛教", "回診", "治療", "用藥",
        "手術", "復健", "飲食", "運動", "檢查", "檢驗", "轉診",
        "medication", "treatment", "follow-up", "prescription", "surgery",
        "therapy", "diet", "exercise", "referral", "advice", "plan",
    ],
}


@dataclass
class SOAPConfig:
    """SOAP 生成配置"""

    model_id: str = "qwen3.5:35b"
    api_base: str = "http://localhost:11434"
    max_tokens: int = 512
    temperature: float = 0.3
    num_ctx: int = 4096
    max_subjective_length: int = 100  # 字元限制


class SOAPGenerator:
    """SOAP 病歷生成器"""

    def __init__(self, config: Optional[SOAPConfig] = None):
        """初始化 SOAP 生成器

        Args:
            config: SOAP 生成配置
        """
        self.config = config or SOAPConfig()
        self._engine: Optional[OllamaEngine] = None

    def initialize(self, engine: Optional[OllamaEngine] = None) -> None:
        """初始化 LLM 引擎

        Args:
            engine: 可選的 OllamaEngine 實例
        """
        if engine:
            self._engine = engine
        else:
            model_config = ModelConfig(
                model_id=self.config.model_id,
                api_base=self.config.api_base,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                num_ctx=self.config.num_ctx,
            )
            from src.llm.ollama_engine import initialize_engine
            self._engine = initialize_engine(model_config)
        logger.info("SOAPGenerator initialized")

    def _build_prompt(self, transcript: str, patient_context: Optional[Dict[str, Any]] = None) -> str:
        """建立 SOAP 生成提示詞

        Args:
            transcript: 醫療對話記錄
            patient_context: 病患背景資訊（年齡、性別等）

        Returns:
            完整的提示詞
        """
        context_str = ""
        if patient_context:
            age = patient_context.get("age", "")
            gender = patient_context.get("gender", "")
            chief_complaint = patient_context.get("chief_complaint", "")
            if age or gender:
                context_str += f"Patient: {age}yo {gender}\n"
            if chief_complaint:
                context_str += f"Chief Complaint: {chief_complaint}\n"

        prompt = f"""You are an advanced medical documentation assistant. Convert the following clinician-patient conversation into a structured SOAP note.

{context_str}
Conversation Transcript:
{transcript}

Rules:
- Correct transcription errors and remove filler words
- Normalize colloquial expressions into standard medical English
- Apply keyword-based S/O/A/P classification
- Subjective section must be ≤{self.config.max_subjective_length} characters
- Omit Plan section if no plan mentioned
- Add Traditional Chinese conversation summary (3-5 sentences)
- Output only the structured SOAP and summary

Output format:
S:
[Subjective - English, ≤{self.config.max_subjective_length} chars]

O:
[Objective findings - English]

A:
[Assessment + ICD-10 if possible]

P:
[Plan - omit if empty]

CONVERSATION_SUMMARY:
[3-5 sentences in Traditional Chinese]
"""
        return prompt

    def generate(
        self,
        transcript: str,
        patient_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """生成 SOAP 病歷

        Args:
            transcript: 醫療對話記錄
            patient_context: 病患背景資訊

        Returns:
            SOAP 病歷字典
        """
        if not self._engine:
            self.initialize()

        prompt = self._build_prompt(transcript, patient_context)

        try:
            response = self._engine.generate(
                prompt=prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
            )
            return self._parse_response(response, transcript)
        except Exception as e:
            logger.error(f"SOAP generation error: {e}")
            raise

    def _parse_response(
        self,
        response: str,
        transcript: str,
    ) -> Dict[str, Any]:
        """解析 LLM 回應成結構化 SOAP

        Args:
            response: LLM 生成的文字
            transcript: 原始對話記錄

        Returns:
            SOAP 病歷字典
        """
        soap = {
            "subjective": "",
            "objective": "",
            "assessment": "",
            "plan": "",
            "conversation_summary": "",
            "raw_response": response,
        }

        lines = response.strip().split("\n")
        current_section = None

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            if line_stripped.startswith("S:"):
                current_section = "subjective"
            elif line_stripped.startswith("O:"):
                current_section = "objective"
            elif line_stripped.startswith("A:"):
                current_section = "assessment"
            elif line_stripped.startswith("P:"):
                current_section = "plan"
            elif line_stripped.startswith("CONVERSATION_SUMMARY:"):
                current_section = "conversation_summary"
            elif current_section:
                soap[current_section] += line_stripped + "\n"

        # 清理多餘空白
        for key in soap:
            soap[key] = soap[key].strip()

        # 計算分類置信度
        soap["classification_confidence"] = self._calculate_confidence(transcript, soap)

        return soap

    def _calculate_confidence(
        self,
        transcript: str,
        soap: Dict[str, Any],
    ) -> Dict[str, float]:
        """計算 SOAP 分類置信度

        Args:
            transcript: 原始對話記錄
            soap: SOAP 病歷字典

        Returns:
            各分類置信度分數
        """
        confidence = {
            "subjective": 0.0,
            "objective": 0.0,
            "assessment": 0.0,
            "plan": 0.0,
        }

        transcript_lower = transcript.lower()

        for category, keywords in SOAP_KEYWORDS.items():
            match_count = sum(1 for kw in keywords if kw.lower() in transcript_lower)
            # 簡單置信度計算：匹配關鍵字數 / 總關鍵字數
            confidence[category] = min(match_count / len(keywords) * 2, 1.0)

        return confidence

    def classify_text(self, text: str) -> List[Dict[str, str]]:
        """將文本分類為 S/O/A/P 候選

        Args:
            text: 輸入文本（可以是句子或段落）

        Returns:
            分類結果列表
        """
        results = []
        text_lower = text.lower()

        for category, keywords in SOAP_KEYWORDS.items():
            matches = [kw for kw in keywords if kw.lower() in text_lower]
            if matches:
                results.append({
                    "category": category,
                    "matched_keywords": matches,
                    "confidence": len(matches) / len(keywords),
                })

        # 依置信度排序
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results


# 全域生成器實例（單例模式）
_generator: Optional[SOAPGenerator] = None


def get_generator(config: Optional[SOAPConfig] = None) -> SOAPGenerator:
    """獲取全域 SOAP 生成器實例

    Args:
        config: SOAP 生成配置

    Returns:
        SOAPGenerator 實例
    """
    global _generator
    if _generator is None:
        _generator = SOAPGenerator(config)
    return _generator


def initialize_generator(config: Optional[SOAPConfig] = None) -> SOAPGenerator:
    """初始化全域 SOAP 生成器

    Args:
        config: SOAP 生成配置

    Returns:
        已初始化的 SOAPGenerator 實例
    """
    gen = get_generator(config)
    if not gen._engine:  # pylint: disable=protected-access
        gen.initialize()
    return gen
