"""測試資料模型"""

import pytest
from datetime import datetime
from ..models.patient import Patient, Gender
from ..models.diagnosis import Diagnosis
from ..models.medical_order import MedicalOrder
from ..models.drug_recommendation import DrugRecommendation
from ..models.soap_note import SOAPNote


class TestPatientModel:
    """測試病人模型"""

    def test_patient_creation(self):
        """測試病人建立"""
        patient = Patient(
            id="P001", name="張三", gender=Gender.MALE, age=35, birth_date=datetime(1990, 1, 1)
        )

        assert patient.id == "P001"
        assert patient.name == "張三"
        assert patient.gender == Gender.MALE
        assert patient.age == 35
        assert patient.birth_date.year == 1990

    def test_patient_to_dict(self):
        """測試轉換為字典"""
        patient = Patient(id="P001", name="張三", gender=Gender.MALE, age=35)

        data = patient.to_dict()
        assert data["id"] == "P001"
        assert data["name"] == "張三"
        assert data["gender"] == "男"
        assert data["age"] == 35


class TestDiagnosisModel:
    """測試診斷模型"""

    def test_diagnosis_creation(self):
        """測試診斷建立"""
        diagnosis = Diagnosis(
            code="J06.9",
            name="急性上呼吸道感染",
            description="Acute upper respiratory infection",
            confidence=0.85,
            category="呼吸系統疾病",
        )

        assert diagnosis.code == "J06.9"
        assert diagnosis.name == "急性上呼吸道感染"
        assert diagnosis.confidence == 0.85
        assert diagnosis.category == "呼吸系統疾病"

    def test_diagnosis_to_dict(self):
        """測試轉換為字典"""
        diagnosis = Diagnosis(code="J06.9", name="急性上呼吸道感染", confidence=0.85)

        data = diagnosis.to_dict()
        assert data["code"] == "J06.9"
        assert data["name"] == "急性上呼吸道感染"
        assert data["confidence"] == 0.85


class TestMedicalOrderModel:
    """測試醫療訂單模型"""

    def test_medical_order_creation(self):
        """測試醫療訂單建立"""
        order = MedicalOrder(
            code="M001",
            name="一般診察費",
            category="診斷",
            fee=150.0,
            description="門診一般診察",
            unit="次",
            frequency="1次",
            priority="essential",
        )

        assert order.code == "M001"
        assert order.name == "一般診察費"
        assert order.category == "診斷"
        assert order.fee == 150.0
        assert order.priority == "essential"

    def test_medical_order_to_dict(self):
        """測試轉換為字典"""
        order = MedicalOrder(code="M001", name="一般診察費", category="診斷", fee=150.0)

        data = order.to_dict()
        assert data["code"] == "M001"
        assert data["name"] == "一般診察費"
        assert data["fee"] == 150.0


class TestDrugRecommendationModel:
    """測試藥物推薦模型"""

    def test_drug_recommendation_creation(self):
        """測試藥物推薦建立"""
        drug = DrugRecommendation(
            code="ACET01",
            name="乙醯胺酚",
            atc_code="N02BE01",
            form="口服錠劑",
            indications="退燒、止痛",
            dosage="成人每次500mg",
            category="解熱鎮痛藥",
        )

        assert drug.code == "ACET01"
        assert drug.name == "乙醯胺酚"
        assert drug.atc_code == "N02BE01"
        assert drug.form == "口服錠劑"
        assert drug.indications == "退燒、止痛"

    def test_drug_recommendation_to_dict(self):
        """測試轉換為字典"""
        drug = DrugRecommendation(
            code="ACET01", name="乙醯胺酚", atc_code="N02BE01", form="口服錠劑"
        )

        data = drug.to_dict()
        assert data["code"] == "ACET01"
        assert data["name"] == "乙醯胺酚"
        assert data["atc_code"] == "N02BE01"


class TestSOAPNoteModel:
    """測試 SOAP 病歷模型"""

    def test_soap_note_creation(self):
        """測試 SOAP 病歷建立"""
        soap_note = SOAPNote(
            subjective="病人主訴咳嗽、發燒三天",
            objective="體溫38.5°C，喉嚨紅腫",
            assessment="急性上呼吸道感染",
            plan="給予退燒藥，建議休息多喝水",
        )

        assert soap_note.subjective == "病人主訴咳嗽、發燒三天"
        assert soap_note.objective == "體溫38.5°C，喉嚨紅腫"
        assert soap_note.assessment == "急性上呼吸道感染"
        assert soap_note.plan == "給予退燒藥，建議休息多喝水"

    def test_soap_note_from_text(self):
        """測試從文字解析 SOAP 病歷"""
        text = """
        主觀資料(S): 病人主訴咳嗽、發燒三天
        客觀資料(O): 體溫38.5°C，喉嚨紅腫
        評估(A): 急性上呼吸道感染
        計畫(P): 給予退燒藥，建議休息多喝水
        """

        soap_note = SOAPNote.from_text(text)

        assert "咳嗽" in soap_note.subjective
        assert "38.5" in soap_note.objective
        assert "上呼吸道" in soap_note.assessment
        assert "退燒藥" in soap_note.plan

    def test_soap_note_summary(self):
        """測試病歷摘要"""
        soap_note = SOAPNote(
            subjective="咳嗽、發燒", objective="體溫38.5°C", assessment="感冒", plan="休息"
        )

        summary = soap_note.summary
        assert "咳嗽" in summary
        assert "感冒" in summary

    def test_soap_note_to_dict(self):
        """測試轉換為字典"""
        soap_note = SOAPNote(subjective="咳嗽", objective="體溫高", assessment="感冒", plan="休息")

        data = soap_note.to_dict()
        assert data["subjective"] == "咳嗽"
        assert data["assessment"] == "感冒"
        assert "summary" in data
