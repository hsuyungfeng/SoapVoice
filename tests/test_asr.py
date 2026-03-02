"""
測試 ASR 模組
"""

import pytest
from src.asr.whisper_model import WhisperModel
from src.asr.vocabulary import MedicalVocabulary


class TestMedicalVocabulary:
    """測試醫療詞彙"""

    @pytest.fixture
    def vocab(self):
        return MedicalVocabulary()

    def test_init(self, vocab):
        """測試初始化"""
        assert vocab.vocab_file.exists()

    def test_load_vocabulary(self, vocab):
        """測試載入詞彙"""
        result = vocab.load_vocabulary()
        assert isinstance(result, dict)
        assert "medications" in result
        assert "diagnoses" in result
        assert "symptoms" in result

    def test_get_all_words(self, vocab):
        """測試取得所有詞彙"""
        vocab.load_vocabulary()
        words = vocab.get_all_words()
        assert len(words) > 0
        assert isinstance(words, list)

    def test_get_words_by_category(self, vocab):
        """測試依類別取得詞彙"""
        vocab.load_vocabulary()
        meds = vocab.get_words_by_category("medications")
        assert len(meds) > 0
        assert "acetaminophen" in meds

    def test_get_words_by_category_invalid(self, vocab):
        """測試無效類別"""
        vocab.load_vocabulary()
        with pytest.raises(ValueError):
            vocab.get_words_by_category("invalid_category")

    def test_len(self, vocab):
        """測試長度"""
        vocab.load_vocabulary()
        assert len(vocab) > 0

    def test_repr(self, vocab):
        """測試字串表示"""
        vocab.load_vocabulary()
        repr_str = repr(vocab)
        assert "MedicalVocabulary" in repr_str
        assert "words=" in repr_str


class TestWhisperModel:
    """測試 Whisper 模型"""

    def test_init(self):
        """測試初始化"""
        model = WhisperModel(
            model_id="tiny",
            device="cpu",
            compute_type="int8",
        )
        assert model.model_id == "tiny"
        assert model.device == "cpu"
