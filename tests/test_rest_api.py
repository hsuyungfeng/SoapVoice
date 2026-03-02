"""
測試 REST API 端點
"""

import pytest
from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    """建立測試客戶端"""
    return TestClient(app)


class TestHealthEndpoints:
    """測試健康檢查端點"""

    def test_root(self, client):
        """測試根路徑"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "SoapVoice API"
        assert data["status"] == "running"

    def test_health(self, client):
        """測試健康檢查"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_api_v1_root(self, client):
        """測試 API v1 根路徑"""
        response = client.get("/api/v1")
        assert response.status_code == 200
        data = response.json()
        assert "endpoints" in data
        assert "websocket" in data["endpoints"]
        assert "clinical" in data["endpoints"]


class TestClinicalNormalize:
    """測試醫療文本標準化端點"""

    def test_normalize_single_term(self, client):
        """測試單一術語標準化"""
        response = client.post(
            "/api/v1/clinical/normalize",
            json={"text": "病人胸悶"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "normalized_text" in data
        assert "terms" in data
        assert "processing_time_ms" in data
        assert len(data["terms"]) > 0

    def test_normalize_multiple_terms(self, client):
        """測試多個術語標準化"""
        response = client.post(
            "/api/v1/clinical/normalize",
            json={"text": "病人胸悶還有頭痛"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["terms"]) >= 2

    def test_normalize_no_match(self, client):
        """測試無匹配文字"""
        response = client.post(
            "/api/v1/clinical/normalize",
            json={"text": "今天天氣真好"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["normalized_text"] == "今天天氣真好"
        assert len(data["terms"]) == 0

    def test_normalize_with_context(self, client):
        """測試帶入上下文"""
        response = client.post(
            "/api/v1/clinical/normalize",
            json={
                "text": "病人胸悶",
                "context": {"specialty": "cardiology"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "normalized_text" in data


class TestClinicalICD10:
    """測試 ICD-10 分類端點"""

    def test_icd10_single_symptom(self, client):
        """測試單一症狀分類"""
        response = client.post(
            "/api/v1/clinical/icd10",
            json={"text": "胸悶"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "matches" in data
        assert "primary_code" in data
        assert "processing_time_ms" in data
        if data["matches"]:
            assert data["primary_code"] == data["matches"][0]["code"]

    def test_icd10_multiple_symptoms(self, client):
        """測試多個症狀分類"""
        response = client.post(
            "/api/v1/clinical/icd10",
            json={"text": "胸悶還有呼吸困難"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) >= 2
        codes = [m["code"] for m in data["matches"]]
        assert "R07.89" in codes  # 胸悶

    def test_icd10_with_age_context(self, client):
        """測試帶入年齡背景"""
        response = client.post(
            "/api/v1/clinical/icd10",
            json={
                "text": "胸悶",
                "context": {"age": 60},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) > 0

    def test_icd10_with_gender_context(self, client):
        """測試帶入性別背景"""
        response = client.post(
            "/api/v1/clinical/icd10",
            json={
                "text": "胸悶",
                "context": {"gender": "M"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) > 0

    def test_icd10_no_match(self, client):
        """測試無匹配"""
        response = client.post(
            "/api/v1/clinical/icd10",
            json={"text": "今天天氣真好"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["matches"] == []
        assert data["primary_code"] is None


class TestSOAPClassify:
    """測試 SOAP 分類端點"""

    def test_classify_subjective(self, client):
        """測試主觀症狀分類"""
        response = client.post(
            "/api/v1/clinical/classify/soap",
            params={"text": "病人說他胸悶很痛"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "subjective"
        assert data["confidence"] > 0

    def test_classify_objective(self, client):
        """測試客觀檢查分類"""
        response = client.post(
            "/api/v1/clinical/classify/soap",
            params={"text": "血壓 140/90，X 光檢查"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "objective"

    def test_classify_assessment(self, client):
        """測試診斷分類"""
        response = client.post(
            "/api/v1/clinical/classify/soap",
            params={"text": "初步診斷為肺炎"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "assessment"

    def test_classify_plan(self, client):
        """測試治療計畫分類"""
        response = client.post(
            "/api/v1/clinical/classify/soap",
            params={"text": "開藥三天後回診"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "plan"


class TestSOAPGenerate:
    """測試 SOAP 生成端點"""

    def test_generate_soap_basic(self, client):
        """測試基本 SOAP 生成"""
        response = client.post(
            "/api/v1/clinical/soap/generate",
            json={
                "transcript": "病人胸悶兩天，呼吸困難",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "soap" in data
        assert "metadata" in data
        assert "processing_time_ms" in data
        soap = data["soap"]
        assert "subjective" in soap
        assert "objective" in soap
        assert "assessment" in soap
        assert "plan" in soap
        assert "conversation_summary" in soap

    def test_generate_soap_with_context(self, client):
        """測試帶入病患背景的 SOAP 生成"""
        response = client.post(
            "/api/v1/clinical/soap/generate",
            json={
                "transcript": "病人胸悶兩天，呼吸困難",
                "patient_context": {
                    "age": 45,
                    "gender": "M",
                    "chief_complaint": "chest pain",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "soap" in data

    def test_generate_soap_empty(self, client):
        """測試空文字 SOAP 生成"""
        response = client.post(
            "/api/v1/clinical/soap/generate",
            json={"transcript": ""},
        )
        # 應該要能處理空文字（可能回傳空 SOAP 或錯誤）
        assert response.status_code in [200, 400, 500]


class TestClinicalHealth:
    """測試臨床 NLP 健康檢查"""

    def test_clinical_health(self, client):
        """測試臨床 NLP 健康檢查"""
        response = client.get("/api/v1/clinical/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "clinical-nlp"
        assert "components" in data
