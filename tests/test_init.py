"""
測試 __init__.py 模組
"""

import pytest


class TestSrcInit:
    """測試 src 模組初始化"""

    def test_import_ollama_engine(self):
        """測試匯入 Ollama 引擎"""
        from src import OllamaEngine, ModelConfig

        assert OllamaEngine is not None
        assert ModelConfig is not None

    def test_import_websocket_router(self):
        """測試匯入 WebSocket 路由"""
        from src import websocket_router

        assert websocket_router is not None


class TestNlpInit:
    """測試 NLP 模組初始化"""

    def test_import_terminology_mapper(self):
        """測試匯入術語映射器"""
        from src.nlp import MedicalTerminologyMapper, TermMapping

        assert MedicalTerminologyMapper is not None
        assert TermMapping is not None

    def test_import_icd10_classifier(self):
        """測試匯入 ICD-10 分類器"""
        from src.nlp import ICD10Classifier, ICD10Match

        assert ICD10Classifier is not None
        assert ICD10Match is not None

    def test_import_soap_classifier(self):
        """測試匯入 SOAP 分類器"""
        from src.nlp import SOAPClassifier, SOAPClassification

        assert SOAPClassifier is not None
        assert SOAPClassification is not None


class TestSoapInit:
    """測試 SOAP 模組初始化"""

    def test_import_soap_generator(self):
        """測試匯入 SOAP 生成器"""
        from src.soap import SOAPGenerator, SOAPConfig

        assert SOAPGenerator is not None
        assert SOAPConfig is not None


class TestApiInit:
    """測試 API 模組初始化"""

    def test_import_websocket_router(self):
        """測試匯入 WebSocket 路由"""
        from src.api import websocket_router

        assert websocket_router is not None
