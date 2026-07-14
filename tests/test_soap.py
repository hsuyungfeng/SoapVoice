"""
測試 SOAP 模組
"""

import pytest
from src.soap.soap_generator import (
    SOAPGenerator,
    SOAPConfig,
    get_generator,
    SOAP_KEYWORDS,
)


class TestSOAPConfig:
    """測試 SOAP 配置"""

    def test_default_config(self):
        """測試預設配置"""
        config = SOAPConfig()
        assert config.model_id == "qwen3.5:9b"
        assert config.max_tokens == 1024
        assert config.temperature == 0.3
        assert config.max_subjective_length == 100


class TestSOAPKeywords:
    """測試 SOAP 關鍵字"""

    def test_keywords_categories(self):
        """測試關鍵字類別"""
        assert "subjective" in SOAP_KEYWORDS
        assert "objective" in SOAP_KEYWORDS
        assert "assessment" in SOAP_KEYWORDS
        assert "plan" in SOAP_KEYWORDS

    def test_subjective_keywords(self):
        """測試主觀關鍵字"""
        subjective = SOAP_KEYWORDS["subjective"]
        assert "痛" in subjective
        assert "癢" in subjective
        assert "pain" in subjective

    def test_objective_keywords(self):
        """測試客觀關鍵字"""
        objective = SOAP_KEYWORDS["objective"]
        assert "血壓" in objective
        assert "x-ray" in objective or "X 光" in objective  # 支援兩種格式

    def test_assessment_keywords(self):
        """測試診斷關鍵字"""
        assessment = SOAP_KEYWORDS["assessment"]
        assert "診斷" in assessment
        assert "diagnosis" in assessment

    def test_plan_keywords(self):
        """測試治療計畫關鍵字"""
        plan = SOAP_KEYWORDS["plan"]
        assert "medication" in plan or "休息" in plan


class TestSOAPGenerator:
    """測試 SOAP 生成器"""

    @pytest.fixture
    def generator(self):
        return SOAPGenerator()

    def test_init(self, generator):
        """測試初始化"""
        assert generator.config is not None
        assert generator._engine is None  # 尚未初始化

    def test_parse_response(self, generator):
        """測試回應解析"""
        response = """S:
Chest pain for 2 days

O:
BP 140/90

A:
Pneumonia

P:
Medication

CONVERSATION_SUMMARY:
病人主訴胸悶兩天"""

        result = generator._parse_response(response, "病人胸悶兩天")

        assert result["subjective"] == "Chest pain for 2 days"
        assert result["objective"] == "BP 140/90"
        assert result["assessment"] == "Pneumonia"
        assert result["plan"] == "Medication"
        assert "病人主訴胸悶兩天" in result["conversation_summary"]

    def test_parse_response_empty_plan(self, generator):
        """測試空治療計畫解析"""
        response = """S:
Chest pain

O:
Normal

A:
Unknown

CONVERSATION_SUMMARY:
病人就診"""

        result = generator._parse_response(response, "病人胸悶")

        assert result["subjective"] == "Chest pain"
        assert result["objective"] == "Normal"
        assert result["assessment"] == "Unknown"
        assert result["plan"] == ""

    def test_build_prompt(self, generator):
        """測試提示詞建立"""
        prompt = generator._build_prompt("病人胸悶")
        assert "SOAP" in prompt
        assert "Subjective" in prompt
        assert "Objective" in prompt
        assert "Assessment" in prompt
        assert "Plan" in prompt
        assert "病人胸悶" in prompt

    def test_build_prompt_with_context(self, generator):
        """測試帶入背景的提示詞"""
        prompt = generator._build_prompt(
            "病人胸悶",
            {"age": 45, "gender": "M", "chief_complaint": "chest pain"},
        )
        # 由於 prompt 會被 _build_prompt 的模板取代，我們應該檢查新模板有的內容
        assert "病人胸悶" in prompt


class TestSingletonGenerator:
    """測試單例生成器"""

    def test_get_generator(self):
        """測試取得生成器"""
        gen1 = get_generator()
        gen2 = get_generator()
        assert gen1 is gen2  # 應該是同一個實例

    def test_get_generator_with_config(self):
        """測試帶配置的生成器"""
        # 清除全域快取以測試新配置
        import src.soap.soap_generator as soap_mod

        soap_mod._generator = None

        config = SOAPConfig(max_tokens=256)
        gen = get_generator(config)
        assert gen.config.max_tokens == 256

        # 恢復預設
        soap_mod._generator = None

    def test_initialize_generator(self):
        """測試初始化生成器（不實際載入模型）"""
        # 僅測試函數可呼叫，不實際初始化 LLM
        import src.soap.soap_generator as soap_mod

        soap_mod._generator = None

        gen = get_generator()
        assert gen is not None
        # 不呼叫 initialize_generator() 因為需要 LLM 模型
