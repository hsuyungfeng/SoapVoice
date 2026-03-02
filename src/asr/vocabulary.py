"""
醫療詞彙管理模組

提供詞彙載入與 Faster-Whisper 整合功能
"""

import json
from pathlib import Path
from typing import Optional


class MedicalVocabulary:
    """醫療詞彙管理類"""

    def __init__(self, vocab_file: str = "config/medical_vocabulary.json"):
        """
        初始化醫療詞彙管理器

        Args:
            vocab_file: 詞彙庫 JSON 檔案路徑
        """
        self.vocab_file = Path(vocab_file)
        self._vocabulary: Optional[dict] = None

    def load_vocabulary(self) -> dict:
        """
        載入詞彙庫

        Returns:
            dict: 包含各類別詞彙的字典
        """
        if not self.vocab_file.exists():
            raise FileNotFoundError(f"詞彙庫檔案不存在: {self.vocab_file}")

        with open(self.vocab_file, "r", encoding="utf-8") as f:
            self._vocabulary = json.load(f)

        return self._vocabulary

    def get_all_words(self) -> list:
        """
        取得所有詞彙

        Returns:
            list: 合併所有類別的詞彙列表
        """
        if self._vocabulary is None:
            self.load_vocabulary()

        all_words = []
        for category_words in self._vocabulary.values():
            if isinstance(category_words, list):
                all_words.extend(category_words)

        return all_words

    def get_words_by_category(self, category: str) -> list:
        """
        依類別取得詞彙

        Args:
            category: 詞彙類別 (medications, diagnoses, procedures, anatomy, symptoms)

        Returns:
            list: 指定類別的詞彙列表
        """
        if self._vocabulary is None:
            self.load_vocabulary()

        if category not in self._vocabulary:
            raise ValueError(f"未知的詞彙類別: {category}")

        return self._vocabulary[category]

    def apply_to_whisper(self, whisper_model) -> None:
        """
        將詞彙注入到 Faster-Whisper 模型

        使用 Faster-Whisper 的 word_boosts 參數進行詞彙強化

        Args:
            whisper_model: Faster-Whisper 模型實例
        """
        words = self.get_all_words()

        # 設定詞彙強化
        if hasattr(whisper_model, "word_boosts"):
            whisper_model.word_boosts = words
        elif hasattr(whisper_model, "model") and hasattr(whisper_model.model, "word_boosts"):
            whisper_model.model.word_boosts = words
        else:
            # 如果模型不支援 word_boosts，記錄詞彙供後續使用
            whisper_model._boosted_words = words

    def get_boosted_words(self) -> dict:
        """
        取得需要強化的詞彙（依類別分組）

        Returns:
            dict: 各類別的詞彙列表
        """
        if self._vocabulary is None:
            self.load_vocabulary()

        return {k: v for k, v in self._vocabulary.items() if isinstance(v, list)}

    def __len__(self) -> int:
        """取得詞彙總數"""
        return len(self.get_all_words())

    def __repr__(self) -> str:
        """字串表示"""
        count = len(self) if self._vocabulary else 0
        return f"MedicalVocabulary(vocab_file={self.vocab_file}, words={count})"
