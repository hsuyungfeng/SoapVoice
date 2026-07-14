import pytest
from unittest.mock import MagicMock

@pytest.fixture(autouse=True)
def mock_sentence_transformer(monkeypatch):
    """全局 mock SentenceTransformer 避免在測試中重複載入 PyTorch 導致 C++ 崩潰或 OOM"""
    mock_st = MagicMock()
    try:
        import sentence_transformers
        monkeypatch.setattr(sentence_transformers, "SentenceTransformer", mock_st)
    except ImportError:
        pass
