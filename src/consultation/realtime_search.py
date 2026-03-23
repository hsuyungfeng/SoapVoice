"""
即時資料庫搜尋模組

在諮詢過程中提供即時的 ICD-10、藥品、醫療服務建議
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from src.db.local_database import LocalDatabase
from src.db.atc_classification import (
    get_atc_info,
    get_atc_by_symptom,
)


logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜尋結果"""

    category: str  # "icd10", "drug", "order"
    code: str
    name: str
    description: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchContext:
    """搜尋上下文"""

    symptoms: List[str] = field(default_factory=list)
    diagnoses: List[str] = field(default_factory=list)
    treatments: List[str] = field(default_factory=list)
    custom_keywords: List[str] = field(default_factory=list)


class RealtimeSearch:
    """即時資料庫搜尋器

    在諮詢過程中根據對話內容即時提供建議
    """

    # 症狀關鍵字列表
    SYMPTOM_KEYWORDS = [
        "頭痛",
        "頭暈",
        "眩暈",
        "昏倒",
        "意識模糊",
        "發燒",
        "發熱",
        "高燒",
        "低燒",
        "畏寒",
        "咳嗽",
        "乾咳",
        "有痰咳嗽",
        "夜咳",
        "久咳",
        "喉嚨痛",
        "喉嚨不適",
        "吞嚥困難",
        "聲音沙啞",
        "鼻塞",
        "流鼻水",
        "鼻涕",
        "打噴嚏",
        "嗅覺喪失",
        "胸悶",
        "胸痛",
        "心悸",
        "呼吸困難",
        "氣短",
        "喘",
        "腹痛",
        "胃痛",
        "腹脹",
        "噁心",
        "嘔吐",
        "腹瀉",
        "便秘",
        "血便",
        "黑便",
        "消化不良",
        "胃酸",
        "胃灼熱",
        "關節痛",
        "關節腫脹",
        "關節僵硬",
        "肌肉痛",
        "肌肉痙攣",
        "背痛",
        "腰痛",
        "頸痛",
        "肩膀痛",
        "手腳麻木",
        "皮膚癢",
        "皮膚紅疹",
        "濕疹",
        "蕁麻疹",
        "青春痘",
        "癬",
        "香港腳",
        "脫皮",
        "脫髮",
        "指甲問題",
        "失眠",
        "嗜睡",
        "疲倦",
        "焦慮",
        "憂鬱",
        "情緒問題",
        "記憶力減退",
        "注意力不集中",
        "血壓高",
        "血壓低",
        "血糖高",
        "血糖低",
        "水腫",
        "體重減輕",
        "體重增加",
        "頻尿",
        "尿急",
        "尿痛",
        "血尿",
        "排尿困難",
        "月經不規則",
        "經痛",
        "陰道分泌物",
        "性功能問題",
        "眼睛紅",
        "眼睛癢",
        "視力模糊",
        "眼睛疼痛",
        "耳朵痛",
        "耳朵有分泌物",
        "聽力減退",
        "耳鳴",
        "過敏",
        "過敏反應",
        "過敏性休克",
    ]

    def __init__(
        self,
        db: Optional[LocalDatabase] = None,
        db_path: str = "data/local_db/medical.db",
    ):
        """初始化即時搜尋器

        Args:
            db: 現有的 LocalDatabase 實例
            db_path: 資料庫路徑
        """
        self._db = db
        self._db_path = db_path
        self._cache: Dict[str, List[SearchResult]] = {}
        self._context = SearchContext()

    def _get_db(self) -> Optional[LocalDatabase]:
        """取得資料庫連線"""
        if self._db is None:
            try:
                from pathlib import Path

                self._db = LocalDatabase(Path(self._db_path))
            except Exception as e:
                logger.warning(f"無法連線資料庫: {e}")
                return None
        return self._db

    def set_context(self, context: SearchContext) -> None:
        """設定搜尋上下文

        Args:
            context: 搜尋上下文
        """
        self._context = context

    def update_context(self, **kwargs) -> None:
        """更新搜尋上下文

        Args:
            **kwargs: 要更新的欄位
        """
        if "symptoms" in kwargs:
            self._context.symptoms.extend(kwargs["symptoms"])
        if "diagnoses" in kwargs:
            self._context.diagnoses.extend(kwargs["diagnoses"])
        if "treatments" in kwargs:
            self._context.treatments.extend(kwargs["treatments"])
        if "custom_keywords" in kwargs:
            self._context.custom_keywords.extend(kwargs["custom_keywords"])

        # 去重
        self._context.symptoms = list(set(self._context.symptoms))
        self._context.diagnoses = list(set(self._context.diagnoses))
        self._context.treatments = list(set(self._context.treatments))

    def search_all(self, text: str) -> Dict[str, List[SearchResult]]:
        """搜尋所有類別

        Args:
            text: 搜尋文字

        Returns:
            依分類的搜尋結果
        """
        symptoms = self._extract_symptoms(text)
        keywords = self._extract_keywords(text)

        all_terms = list(set(symptoms + keywords + self._context.symptoms))

        results: Dict[str, List[SearchResult]] = {
            "icd10": [],
            "drug": [],
            "order": [],
        }

        for term in all_terms:
            term_results = self._search_by_term(term)
            for r in term_results:
                if r.category == "icd10" and r not in results["icd10"]:
                    results["icd10"].append(r)
                elif r.category == "drug" and r not in results["drug"]:
                    results["drug"].append(r)
                elif r.category == "order" and r not in results["order"]:
                    results["order"].append(r)

        # 限制每類結果數量
        for key in results:
            results[key] = results[key][:10]

        return results

    def search_icd10(self, text: str, limit: int = 10) -> List[SearchResult]:
        """搜尋 ICD-10

        Args:
            text: 搜尋文字
            limit: 最大結果數

        Returns:
            ICD-10 結果列表
        """
        cache_key = f"icd10:{text}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        db = self._get_db()
        if not db:
            return []

        symptoms = self._extract_symptoms(text)
        keywords = self._extract_keywords(text)
        all_terms = list(set(symptoms + keywords))

        results = []
        for term in all_terms:
            icd10_results = db.search_icd10(term, limit=5)
            for r in icd10_results:
                results.append(
                    SearchResult(
                        category="icd10",
                        code=r.code,
                        name=r.name_cn,
                        description=f"{r.name_en} | {r.category}",
                        metadata={"name_en": r.name_en, "category": r.category},
                    )
                )

        # 去重並排序
        seen_codes = set()
        unique_results = []
        for r in results:
            if r.code not in seen_codes:
                seen_codes.add(r.code)
                unique_results.append(r)

        self._cache[cache_key] = unique_results[:limit]
        return self._cache[cache_key]

    def search_drugs(self, text: str, limit: int = 10) -> List[SearchResult]:
        """搜尋藥品

        Args:
            text: 搜尋文字
            limit: 最大結果數

        Returns:
            藥品結果列表
        """
        cache_key = f"drug:{text}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        db = self._get_db()
        if not db:
            return []

        symptoms = self._extract_symptoms(text)
        keywords = self._extract_keywords(text)
        all_terms = list(set(symptoms + keywords))

        results = []
        for term in all_terms:
            # 先根據症狀取得 ATC 分類
            atc_codes = get_atc_by_symptom(term)
            for atc_code in atc_codes[:2]:
                drug_results = db.search_drugs_by_atc_class(atc_code, limit=5)
                for r in drug_results:
                    results.append(
                        SearchResult(
                            category="drug",
                            code=r.drug_code,
                            name=r.drug_name_cn,
                            description=f"ATC: {r.atc_code} | {r.drug_class} | {r.dosage_form}",
                            metadata={
                                "atc_code": r.atc_code,
                                "price": r.payment_price,
                                "drug_class": r.drug_class,
                                "dosage_form": r.dosage_form,
                            },
                        )
                    )

            # 直接搜尋藥品名稱
            drug_results = db.search_drugs(term, limit=5)
            for r in drug_results:
                results.append(
                    SearchResult(
                        category="drug",
                        code=r.drug_code,
                        name=r.drug_name_cn,
                        description=f"ATC: {r.atc_code} | {r.drug_class} | {r.dosage_form}",
                        metadata={
                            "atc_code": r.atc_code,
                            "price": r.payment_price,
                            "drug_class": r.drug_class,
                            "dosage_form": r.dosage_form,
                        },
                    )
                )

        # 去重並排序（價格由高到低）
        seen_codes = set()
        unique_results = []
        for r in results:
            if r.code not in seen_codes:
                seen_codes.add(r.code)
                unique_results.append(r)

        unique_results.sort(key=lambda x: x.metadata.get("price", 0), reverse=True)
        self._cache[cache_key] = unique_results[:limit]
        return self._cache[cache_key]

    def search_medical_orders(self, text: str, limit: int = 10) -> List[SearchResult]:
        """搜尋醫療服務

        Args:
            text: 搜尋文字
            limit: 最大結果數

        Returns:
            醫療服務結果列表
        """
        cache_key = f"order:{text}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        db = self._get_db()
        if not db:
            return []

        symptoms = self._extract_symptoms(text)
        keywords = self._extract_keywords(text)
        all_terms = list(set(symptoms + keywords))

        results = []
        for term in all_terms:
            order_results = db.search_medical_orders(term, limit=5)
            for r in order_results:
                results.append(
                    SearchResult(
                        category="order",
                        code=r.order_code,
                        name=r.name_cn,
                        description=f"{r.name_en} | {r.category} | {r.fee_points}點",
                        metadata={
                            "name_en": r.name_en,
                            "category": r.category,
                            "fee_points": r.fee_points,
                        },
                    )
                )

        # 去重
        seen_codes = set()
        unique_results = []
        for r in results:
            if r.code not in seen_codes:
                seen_codes.add(r.code)
                unique_results.append(r)

        self._cache[cache_key] = unique_results[:limit]
        return self._cache[cache_key]

    def get_drug_interactions(self, drug_codes: List[str]) -> List[Dict[str, Any]]:
        """檢查藥品交互作用

        Args:
            drug_codes: 藥品代碼列表

        Returns:
            交互作用資訊列表
        """
        interactions = []

        # TODO: 實作藥品交互作用檢查（需要專業資料庫）
        # common_interactions = {
        #     ("warfarin", "aspirin"): "增加出血風險",
        #     ("digoxin", "furosemide"): "可能導致低血鉀",
        #     ("metformin", "contrast"): "可能導致乳酸中毒",
        #     ("ssri", "maoi"): "血清素症候群風險",
        # }

        return interactions

    def get_atc_recommendations(self, symptoms: List[str]) -> Dict[str, List[Dict[str, str]]]:
        """根據症狀取得 ATC 分類建議

        Args:
            symptoms: 症狀列表

        Returns:
            ATC 分類建議
        """
        recommendations = {}

        for symptom in symptoms:
            atc_codes = get_atc_by_symptom(symptom)
            atc_info = []

            for code in atc_codes[:3]:
                info = get_atc_info(code)
                if info:
                    atc_info.append(
                        {
                            "code": info.code,
                            "name_cn": info.name_cn,
                            "name_en": info.name_en,
                            "description": info.description,
                        }
                    )

            if atc_info:
                recommendations[symptom] = atc_info

        return recommendations

    def _search_by_term(self, term: str) -> List[SearchResult]:
        """根據單一術語搜尋所有類別

        Args:
            term: 搜尋術語

        Returns:
            搜尋結果列表
        """
        results = []

        # ICD-10
        icd10_results = self.search_icd10(term, limit=5)
        results.extend(icd10_results)

        # 藥品
        drug_results = self.search_drugs(term, limit=5)
        results.extend(drug_results)

        # 醫療服務
        order_results = self.search_medical_orders(term, limit=5)
        results.extend(order_results)

        return results

    def _extract_symptoms(self, text: str) -> List[str]:
        """從文字中提取症狀

        Args:
            text: 文字

        Returns:
            症狀列表
        """
        found = []
        for symptom in self.SYMPTOM_KEYWORDS:
            if symptom in text:
                found.append(symptom)
        return found

    def _extract_keywords(self, text: str) -> List[str]:
        """從文字中提取關鍵字

        Args:
            text: 文字

        Returns:
            關鍵字列表
        """
        # 簡單的關鍵字提取（去除停用詞）
        stopwords = {
            "我",
            "你",
            "他",
            "她",
            "它",
            "的",
            "了",
            "是",
            "在",
            "有",
            "和",
            "就",
            "不",
            "也",
        }

        words = []
        current_word = ""

        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                current_word += char
            else:
                if current_word and current_word not in stopwords:
                    words.append(current_word)
                current_word = ""

        if current_word and current_word not in stopwords:
            words.append(current_word)

        # 去重
        return list(set(words))

    def clear_cache(self) -> None:
        """清除搜尋快取"""
        self._cache.clear()

    def get_cached_results(self, text: str) -> Optional[Dict[str, List[SearchResult]]]:
        """取得快取的搜尋結果

        Args:
            text: 搜尋文字

        Returns:
            快取的結果或 None
        """
        icd10_key = f"icd10:{text}"
        drug_key = f"drug:{text}"
        order_key = f"order:{text}"

        if icd10_key in self._cache or drug_key in self._cache or order_key in self._cache:
            return {
                "icd10": self._cache.get(icd10_key, []),
                "drug": self._cache.get(drug_key, []),
                "order": self._cache.get(order_key, []),
            }

        return None
