"""
醫療詞彙測試

測試詞彙載入與管理功能
"""

import pytest
import json
from pathlib import Path


class TestMedicalVocabulary:
    """醫療詞彙測試類"""

    @pytest.fixture
    def vocab_file(self, tmp_path):
        """建立臨時詞彙檔案"""
        vocab_data = {
            "medications": ["aspirin", "ibuprofen", "acetaminophen"],
            "diagnoses": ["hypertension", "diabetes"],
            "procedures": ["surgery", "biopsy"],
            "anatomy": ["heart", "lung"],
            "symptoms": ["fever", "cough"],
        }
        vocab_path = tmp_path / "test_vocab.json"
        with open(vocab_path, "w", encoding="utf-8") as f:
            json.dump(vocab_data, f)
        return str(vocab_path)

    def test_load_vocabulary(self, vocab_file):
        """測試詞彙庫載入"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary(vocab_file)
        result = vocab.load_vocabulary()

        assert isinstance(result, dict)
        assert "medications" in result
        assert "diagnoses" in result

    def test_get_all_words(self, vocab_file):
        """測試取得所有詞彙"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary(vocab_file)
        words = vocab.get_all_words()

        assert isinstance(words, list)
        assert len(words) >= 10  # At least 5 categories * 2 words each

    def test_get_words_by_category(self, vocab_file):
        """測試依類別取得詞彙"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary(vocab_file)

        meds = vocab.get_words_by_category("medications")
        assert meds == ["aspirin", "ibuprofen", "acetaminophen"]

        diagnoses = vocab.get_words_by_category("diagnoses")
        assert diagnoses == ["hypertension", "diabetes"]

    def test_vocabulary_count(self):
        """測試詞彙數量足夠"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary()

        # 檢查每個類別至少有 50 個詞彙
        assert len(vocab.get_words_by_category("medications")) >= 50
        assert len(vocab.get_words_by_category("diagnoses")) >= 50
        assert len(vocab.get_words_by_category("procedures")) >= 50
        assert len(vocab.get_words_by_category("anatomy")) >= 50
        assert len(vocab.get_words_by_category("symptoms")) >= 50

    def test_get_boosted_words(self):
        """測試取得強化詞彙"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary()
        boosted = vocab.get_boosted_words()

        assert isinstance(boosted, dict)
        assert "medications" in boosted
        assert "diagnoses" in boosted

    def test_len(self):
        """測試詞彙總數"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary()
        assert len(vocab) >= 50

    def test_repr(self):
        """測試字串表示"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary()
        repr_str = repr(vocab)

        assert "MedicalVocabulary" in repr_str
        assert "config/medical_vocabulary.json" in repr_str

    def test_invalid_category(self, vocab_file):
        """測試無效類別"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary(vocab_file)

        with pytest.raises(ValueError):
            vocab.get_words_by_category("invalid_category")

    def test_missing_file(self):
        """測試檔案不存在"""
        from src.asr.vocabulary import MedicalVocabulary

        vocab = MedicalVocabulary("nonexistent.json")

        with pytest.raises(FileNotFoundError):
            vocab.load_vocabulary()
