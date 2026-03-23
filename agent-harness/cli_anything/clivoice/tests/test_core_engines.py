"""測試核心引擎"""

import pytest
from ..models.soap_note import SOAPNote
from ..core.diagnosis_engine import DiagnosisEngine
from ..core.order_generator import OrderGenerator
from ..core.drug_recommender import DrugRecommender
from ..core.integration_orchestrator import IntegrationOrchestrator


class TestDiagnosisEngine:
    """測試診斷引擎"""

    def setup_method(self):
        self.engine = DiagnosisEngine()

    def test_extract_symptoms(self):
        """測試症狀提取"""
        soap_note = SOAPNote(
            subjective="病人主訴咳嗽、發燒三天，喉嚨痛",
            objective="體溫38.5°C，喉嚨紅腫",
            assessment="急性上呼吸道感染",
            plan="給予退燒藥",
        )

        symptoms = self.engine.extract_symptoms(soap_note)

        assert len(symptoms) > 0
        assert any("咳嗽" in symptom for symptom in symptoms)
        assert any("發燒" in symptom for symptom in symptoms)

    def test_match_diagnoses(self):
        """測試診斷匹配"""
        symptoms = ["咳嗽", "發燒", "喉嚨痛"]

        diagnoses = self.engine.match_diagnoses(symptoms)

        assert len(diagnoses) > 0
        for diagnosis in diagnoses:
            assert diagnosis.code
            assert diagnosis.name
            assert 0 <= diagnosis.confidence <= 1.0


class TestOrderGenerator:
    """測試醫囑生成器"""

    def setup_method(self):
        self.generator = OrderGenerator()

    def test_generate_orders(self):
        """測試醫囑生成"""
        result = self.generator.generate_orders("J06.9")

        assert result.diagnosis_code == "J06.9"
        assert len(result.orders) > 0
        assert result.total_fee >= 0
        assert len(result.categories) > 0

    def test_filter_orders_by_priority(self):
        """測試優先級篩選"""
        # 建立測試醫囑
        from ..models.medical_order import MedicalOrder

        orders = [
            MedicalOrder(code="M001", name="診斷", category="診斷", fee=100.0),
            MedicalOrder(code="M002", name="檢查", category="檢查", fee=200.0),
            MedicalOrder(code="M003", name="衛教", category="衛教", fee=50.0),
        ]

        filtered = self.generator.filter_orders_by_priority(orders, "essential")

        assert len(filtered) <= len(orders)
        categories = [order.category for order in filtered]
        assert "診斷" in categories
        assert "檢查" in categories


class TestDrugRecommender:
    """測試藥物推薦器"""

    def setup_method(self):
        self.recommender = DrugRecommender()

    def test_recommend_drugs(self):
        """測試藥物推薦"""
        result = self.recommender.recommend_drugs("J06.9")

        assert result.diagnosis_code == "J06.9"
        assert len(result.recommendations) > 0
        assert result.total_drugs == len(result.recommendations)
        assert len(result.atc_classes) > 0

    def test_generate_prescription(self):
        """測試處方箋生成"""
        from ..models.drug_recommendation import DrugRecommendation

        drugs = [
            DrugRecommendation(
                code="ACET01",
                name="乙醯胺酚",
                atc_code="N02BE01",
                form="口服錠劑",
                indications="退燒、止痛",
            )
        ]

        prescription = self.recommender.generate_prescription(drugs)

        assert prescription["total_drugs"] == 1
        assert len(prescription["medications"]) == 1
        assert len(prescription["instructions"]) > 0


class TestIntegrationOrchestrator:
    """測試整合協調器"""

    def setup_method(self):
        self.orchestrator = IntegrationOrchestrator()

    def test_process_soap_note(self):
        """測試 SOAP 病歷處理"""
        soap_note = SOAPNote(
            subjective="咳嗽、發燒", objective="體溫38.5°C", assessment="感冒", plan="休息"
        )

        result = self.orchestrator.process_soap_note(soap_note)

        assert result.soap_note == soap_note
        assert isinstance(result.diagnoses, list)
        assert isinstance(result.orders, list)
        assert isinstance(result.drug_recommendations, list)
        assert result.processing_time >= 0

    def test_generate_report(self):
        """測試報告生成"""
        soap_note = SOAPNote(subjective="咳嗽", objective="體溫高", assessment="感冒", plan="休息")

        result = self.orchestrator.process_soap_note(soap_note)

        # 測試文字報告
        text_report = self.orchestrator.generate_report(result, "text")
        assert isinstance(text_report, str)
        assert len(text_report) > 0

        # 測試 JSON 報告
        json_report = self.orchestrator.generate_report(result, "json")
        assert isinstance(json_report, str)
        assert "diagnoses" in json_report

        # 測試 Markdown 報告
        md_report = self.orchestrator.generate_report(result, "markdown")
        assert isinstance(md_report, str)
        assert "#" in md_report  # 包含標題
