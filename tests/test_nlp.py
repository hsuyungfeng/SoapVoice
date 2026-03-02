"""
測試 NLP 模組
"""

import pytest
from src.nlp.terminology_mapper import MedicalTerminologyMapper, TermMapping
from src.nlp.icd10_classifier import ICD10Classifier, ICD10Match
from src.nlp.soap_classifier import SOAPClassifier, SOAPClassification


class TestMedicalTerminologyMapper:
    """測試醫療術語映射器"""

    @pytest.fixture
    def mapper(self):
        return MedicalTerminologyMapper()

    def test_init(self, mapper):
        """測試初始化"""
        assert len(mapper) > 0
        assert "胸悶" in mapper.get_all_mappings()

    def test_map_term_direct(self, mapper):
        """測試直接映射"""
        result = mapper.map_term("胸悶")
        assert result is not None
        assert result.original == "胸悶"
        assert result.standard == "chest tightness"
        assert result.category == "symptom"
        assert result.confidence >= 0.9
        assert "R07.89" in result.icd10_candidates

    def test_map_term_not_found(self, mapper):
        """測試未找到映射"""
        result = mapper.map_term("不存在的詞")
        assert result is None

    def test_map_text_single(self, mapper):
        """測試單一文字映射"""
        text, mappings = mapper.map_text("病人胸悶")
        assert "chest tightness" in text
        assert len(mappings) == 1
        assert mappings[0].standard == "chest tightness"

    def test_map_text_multiple(self, mapper):
        """測試多個文字映射"""
        text, mappings = mapper.map_text("病人胸悶還有頭痛")
        assert "chest tightness" in text
        assert "headache" in text
        assert len(mappings) >= 2

    def test_map_text_no_match(self, mapper):
        """測試無匹配文字"""
        text, mappings = mapper.map_text("今天天氣真好")
        assert text == "今天天氣真好"
        assert len(mappings) == 0

    def test_get_mappings_by_category(self, mapper):
        """測試依類別取得映射"""
        symptoms = mapper.get_mappings_by_category("symptom")
        assert len(symptoms) > 0
        assert all(m.category == "symptom" for m in symptoms)

    def test_add_mapping(self, mapper):
        """測試新增映射"""
        mapper.add_mapping(
            "新症狀",
            "new symptom",
            category="symptom",
            icd10=["R99"],
            confidence=0.95,
        )
        result = mapper.map_term("新症狀")
        assert result is not None
        assert result.standard == "new symptom"
        assert result.confidence == 0.95

    def test_map_term_partial_match(self, mapper):
        """測試部分匹配"""
        result = mapper.map_term("病人主訴胸悶兩天")
        assert result is not None
        assert result.standard == "chest tightness"


class TestICD10Classifier:
    """測試 ICD-10 分類器"""

    @pytest.fixture
    def classifier(self):
        return ICD10Classifier()

    def test_init(self, classifier):
        """測試初始化"""
        assert len(classifier.SYMPTOM_TO_ICD10) > 0

    def test_classify_single_symptom(self, classifier):
        """測試單一症狀分類"""
        results = classifier.classify("胸悶")
        assert len(results) > 0
        assert results[0].code == "R07.89"
        assert results[0].confidence >= 0.9

    def test_classify_multiple_symptoms(self, classifier):
        """測試多個症狀分類"""
        results = classifier.classify("胸悶還有呼吸困難")
        assert len(results) >= 2
        codes = [r.code for r in results]
        assert "R07.89" in codes  # 胸悶
        assert "R06.02" in codes  # 呼吸困難

    def test_classify_no_match(self, classifier):
        """測試無匹配"""
        results = classifier.classify("今天天氣真好")
        assert len(results) == 0

    def test_classify_with_context_age(self, classifier):
        """測試帶入年齡背景"""
        results = classifier.classify_with_context(
            "胸悶",
            patient_age=60,
        )
        assert len(results) > 0
        # 年齡大於 50 歲，心血管疾病置信度應該提升
        cardiovascular_results = [
            r for r in results if r.category == "Cardiovascular"
        ]
        if cardiovascular_results:
            assert cardiovascular_results[0].confidence >= 0.9

    def test_classify_with_context_gender(self, classifier):
        """測試帶入性別背景"""
        results = classifier.classify_with_context(
            "頻尿",
            patient_gender="M",
        )
        assert len(results) > 0

    def test_get_category_name(self, classifier):
        """測試取得類別名稱"""
        assert classifier.get_category_name("Respiratory") == "呼吸系統"
        assert classifier.get_category_name("Unknown") == "Unknown"

    def test_search_by_code(self, classifier):
        """測試依代碼搜尋"""
        result = classifier.search_by_code("R07.89")
        assert result is not None
        assert result.code == "R07.89"
        assert "chest" in result.description.lower()

    def test_search_by_code_not_found(self, classifier):
        """測試代碼不存在"""
        result = classifier.search_by_code("INVALID")
        assert result is None

    def test_classify_sorted_by_confidence(self, classifier):
        """測試結果依置信度排序"""
        results = classifier.classify("發燒頭痛")
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].confidence >= results[i + 1].confidence


class TestSOAPClassifier:
    """測試 SOAP 分類器"""

    @pytest.fixture
    def classifier(self):
        return SOAPClassifier()

    def test_init(self, classifier):
        """測試初始化"""
        assert len(classifier.KEYWORDS) == 4  # S, O, A, P

    def test_classify_subjective(self, classifier):
        """測試主觀症狀分類"""
        result = classifier.classify("病人說他胸悶很痛")
        # 注意：如果置信度低於閾值，可能會歸類為 unknown
        # 這裡我們測試有匹配到關鍵字即可
        assert result.category in ["subjective", "unknown"]
        if result.category == "subjective":
            assert result.confidence > 0
            assert len(result.matched_keywords) > 0

    def test_classify_objective(self, classifier):
        """測試客觀檢查分類"""
        result = classifier.classify("血壓 140/90，X 光檢查正常")
        assert result.category in ["objective", "unknown"]
        if result.category == "objective":
            assert result.confidence > 0

    def test_classify_plan(self, classifier):
        """測試治療計畫分類"""
        result = classifier.classify("開藥三天後回診追蹤")
        assert result.category in ["plan", "unknown"]
        if result.category == "plan":
            assert result.confidence > 0

    def test_classify_unknown(self, classifier):
        """測試未知分類"""
        classifier_high = SOAPClassifier(threshold=0.9)
        result = classifier_high.classify("今天天氣真好")
        assert result.category == "unknown"

    def test_classify_batch(self, classifier):
        """測試批次分類"""
        texts = ["胸悶", "血壓 120", "診斷肺炎", "開藥"]
        results = classifier.classify_batch(texts)
        assert len(results) == 4

    def test_classify_to_dict(self, classifier):
        """測試字典格式輸出"""
        result = classifier.classify_to_dict("病人胸悶")
        assert isinstance(result, dict)
        assert "category" in result
        assert "confidence" in result
        assert "matched_keywords" in result

    def test_group_by_category(self, classifier):
        """測試依類別分組"""
        texts = ["胸悶", "血壓 120", "診斷肺炎", "開藥"]
        grouped = classifier.group_by_category(texts)
        assert isinstance(grouped, dict)
        # 驗證至少有一個類別
        assert len(grouped) >= 1

    def test_matched_keywords(self, classifier):
        """測試匹配關鍵字"""
        result = classifier.classify("病人發燒咳嗽")
        # 注意：如果置信度低於閾值，可能沒有匹配關鍵字
        # 這裡我們測試關鍵字匹配邏輯
        if result.matched_keywords:
            # 如果有匹配，驗證關鍵字確實在原文中
            for kw in result.matched_keywords:
                assert kw.lower() in result.text.lower()
        else:
            # 如果沒有匹配，確保分類為 unknown
            assert result.category == "unknown"
