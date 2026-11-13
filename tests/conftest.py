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


@pytest.fixture(autouse=True, scope="session")
def isolated_rag_db(tmp_path_factory):
    """測試期間將 RAG（chroma）資料庫指向暫存副本，避免測試寫入 data/rag/chroma。"""
    import shutil
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "data" / "rag" / "chroma"
    dst = tmp_path_factory.mktemp("rag") / "chroma"
    if src.exists():
        shutil.copytree(src, dst)
    else:
        dst.mkdir(parents=True)

    try:
        import src.soap.soap_generator as soap_generator
    except Exception:
        yield dst
        return

    original = soap_generator.RAG_DB_PATH
    soap_generator.RAG_DB_PATH = dst
    try:
        yield dst
    finally:
        soap_generator.RAG_DB_PATH = original
