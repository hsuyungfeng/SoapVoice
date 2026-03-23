"""ICD-10 適配器 — 整合 ICD10v2 疾病分類系統"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
import requests

from ..models.diagnosis import Diagnosis, DiagnosisConfidence


logger = logging.getLogger(__name__)


class ICD10Adapter:
    """ICD-10 疾病分類適配器"""

    def __init__(self, data_path: Optional[str] = None):
        """初始化 ICD-10 適配器

        Args:
            data_path: ICD-10 資料檔案路徑，若為 None 則使用預設路徑
        """
        self._data_path = data_path or self._get_default_data_path()
        self._icd10_data: List[Dict[str, Any]] = []
        self._symptom_to_icd10: Dict[str, List[str]] = {}
        self._load_data()
        logger.info(f"ICD-10 適配器初始化完成，載入 {len(self._icd10_data)} 筆資料")

    def _get_default_data_path(self) -> str:
        """取得預設資料路徑"""
        # 嘗試從 CliVoice/ICD10v2 目錄讀取資料
        base_path = Path(__file__).parent.parent.parent.parent.parent
        icd10_path = base_path / "CliVoice" / "ICD10v2" / "icd10-data.js"

        if icd10_path.exists():
            return str(icd10_path)

        # 備用路徑：使用內建範例資料
        return ""

    def _load_data(self):
        """載入 ICD-10 資料"""
        try:
            if self._data_path and Path(self._data_path).exists():
                self._load_from_file()
            else:
                self._load_example_data()

            # 建立症狀到 ICD-10 的映射
            self._build_symptom_mapping()

        except Exception as e:
            logger.error(f"載入 ICD-10 資料時發生錯誤: {e}")
            self._load_example_data()

    def _load_from_file(self):
        """從檔案載入資料"""
        logger.info(f"從檔案載入 ICD-10 資料: {self._data_path}")

        with open(self._data_path, "r", encoding="utf-8") as f:
            content = f.read()

            # 解析 JavaScript 檔案中的 JSON 資料
            # 尋找 ICD10_DATA 陣列
            match = re.search(r"const ICD10_DATA = (\[.*?\]);", content, re.DOTALL)
            if match:
                json_str = match.group(1)
                self._icd10_data = json.loads(json_str)
            else:
                logger.warning("無法解析 ICD10_DATA，使用範例資料")
                self._load_example_data()

    def _load_example_data(self):
        """載入範例資料"""
        logger.info("載入範例 ICD-10 資料")

        # 常見疾病的範例資料
        self._icd10_data = [
            {
                "code": "J06.9",
                "use": "1",
                "nameEn": "Acute upper respiratory infection, unspecified",
                "nameCn": "急性上呼吸道感染",
            },
            {
                "code": "J20.9",
                "use": "1",
                "nameEn": "Acute bronchitis, unspecified",
                "nameCn": "急性支氣管炎",
            },
            {
                "code": "J11.1",
                "use": "1",
                "nameEn": "Influenza with other respiratory manifestations, virus not identified",
                "nameCn": "流行性感冒伴有其他呼吸道表徵，病毒未鑑定",
            },
            {
                "code": "K29.70",
                "use": "1",
                "nameEn": "Gastritis, unspecified, without bleeding",
                "nameCn": "胃炎",
            },
            {
                "code": "K52.9",
                "use": "1",
                "nameEn": "Noninfective gastroenteritis and colitis, unspecified",
                "nameCn": "非感染性胃腸炎及結腸炎",
            },
            {"code": "M54.5", "use": "1", "nameEn": "Low back pain", "nameCn": "下背痛"},
            {"code": "R50.9", "use": "1", "nameEn": "Fever, unspecified", "nameCn": "發燒"},
            {"code": "R05", "use": "1", "nameEn": "Cough", "nameCn": "咳嗽"},
            {"code": "R11", "use": "1", "nameEn": "Nausea and vomiting", "nameCn": "噁心及嘔吐"},
            {"code": "R51", "use": "1", "nameEn": "Headache", "nameCn": "頭痛"},
        ]

    def _build_symptom_mapping(self):
        """建立症狀到 ICD-10 的映射"""
        # 症狀關鍵字到 ICD-10 代碼的映射
        symptom_mapping = {
            "咳嗽": ["J06.9", "J20.9", "J11.1", "R05"],
            "發燒": ["J06.9", "J11.1", "R50.9"],
            "頭痛": ["R51", "J06.9"],
            "喉嚨痛": ["J06.9", "J02.9"],
            "流鼻水": ["J06.9", "J00"],
            "鼻塞": ["J06.9", "J34.8"],
            "噁心": ["K29.70", "K52.9", "R11"],
            "嘔吐": ["K29.70", "K52.9", "R11"],
            "腹瀉": ["K52.9", "A09"],
            "腹痛": ["K29.70", "K52.9", "R10.4"],
            "背痛": ["M54.5", "M54.9"],
            "疲倦": ["R53", "J06.9"],
            "肌肉酸痛": ["M79.1", "J11.1"],
            "呼吸困難": ["J06.9", "J20.9", "R06.0"],
            "胸痛": ["R07.4", "I20.9"],
            "感冒": ["J06.9", "J00"],
            "流感": ["J11.1", "J10.1"],
            "胃炎": ["K29.70", "K29.9"],
            "腸胃炎": ["K52.9", "A09"],
            "支氣管炎": ["J20.9", "J40"],
        }

        self._symptom_to_icd10 = symptom_mapping

    def search_by_code(self, code: str) -> Optional[Diagnosis]:
        """根據代碼搜尋診斷

        Args:
            code: ICD-10 代碼

        Returns:
            Diagnosis: 診斷物件，若未找到則返回 None
        """
        for item in self._icd10_data:
            if item["code"] == code:
                return Diagnosis(
                    icd10_code=item["code"],
                    name=item["nameCn"],
                    name_en=item.get("nameEn", ""),
                    confidence=1.0,
                    confidence_level=DiagnosisConfidence.HIGH,
                    symptoms=[],
                    differential_diagnoses=[],
                    recommendations=[],
                    severity=None,
                    onset=None,
                    duration=None,
                    notes=None,
                )

        return None

    def search_by_name(self, name: str, language: str = "cn") -> List[Diagnosis]:
        """根據名稱搜尋診斷

        Args:
            name: 診斷名稱
            language: 語言 (cn/en)

        Returns:
            List[Diagnosis]: 診斷列表
        """
        results = []
        name_lower = name.lower()

        for item in self._icd10_data:
            if language == "cn":
                search_field = item.get("nameCn", "")
            else:
                search_field = item.get("nameEn", "")

            if name_lower in search_field.lower():
                results.append(
                    Diagnosis(
                        icd10_code=item["code"],
                        name=item["nameCn"],
                        name_en=item.get("nameEn", ""),
                        confidence=0.8 if name_lower in search_field.lower() else 0.5,
                        confidence_level=DiagnosisConfidence.MEDIUM,
                        symptoms=[],
                        differential_diagnoses=[],
                        recommendations=[],
                        severity=None,
                        onset=None,
                        duration=None,
                        notes=None,
                    )
                )

        return results

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """搜尋 ICD-10 診斷

        Args:
            query: 搜尋查詢
            limit: 結果數量限制

        Returns:
            List[Dict[str, Any]]: 搜尋結果
        """
        results = []
        query_lower = query.lower()

        for item in self._icd10_data:
            name_cn = item.get("nameCn", "").lower()
            name_en = item.get("nameEn", "").lower()
            code = item.get("code", "").lower()

            if query_lower in name_cn or query_lower in name_en or query_lower in code:
                results.append(
                    {
                        "code": item["code"],
                        "name_cn": item.get("nameCn", ""),
                        "name_en": item.get("nameEn", ""),
                        "use": item.get("use", "0"),
                    }
                )

            if len(results) >= limit:
                break

        return results

    def search_by_symptom(self, symptom: str) -> List[Diagnosis]:
        """根據症狀搜尋診斷

        Args:
            symptom: 症狀描述

        Returns:
            List[Diagnosis]: 診斷列表
        """
        results = []
        symptom_lower = symptom.lower()

        # 檢查症狀映射
        for symptom_key, codes in self._symptom_to_icd10.items():
            if symptom_key in symptom_lower:
                for code in codes:
                    diagnosis = self.search_by_code(code)
                    if diagnosis:
                        # 調整信心度基於匹配程度
                        if symptom_key == symptom_lower:
                            diagnosis.confidence = 0.9
                        else:
                            diagnosis.confidence = 0.7
                        results.append(diagnosis)

        # 如果沒有找到映射，嘗試模糊搜尋
        if not results:
            for item in self._icd10_data:
                name_cn = item.get("nameCn", "").lower()
                name_en = item.get("nameEn", "").lower()

                if symptom_lower in name_cn or symptom_lower in name_en:
                    results.append(
                        Diagnosis(
                            icd10_code=item["code"],
                            name=item["nameCn"],
                            name_en=item.get("nameEn", ""),
                            confidence=0.6,
                            confidence_level=DiagnosisConfidence.MEDIUM,
                            symptoms=[],
                            differential_diagnoses=[],
                            recommendations=[],
                            severity=None,
                            onset=None,
                            duration=None,
                            notes=None,
                        )
                    )

        # 去重並按信心度排序
        unique_results = {}
        for diagnosis in results:
            if (
                diagnosis.icd10_code not in unique_results
                or diagnosis.confidence > unique_results[diagnosis.icd10_code].confidence
            ):
                unique_results[diagnosis.icd10_code] = diagnosis

        return sorted(unique_results.values(), key=lambda x: x.confidence, reverse=True)

    def get_children(self, parent_code: str) -> List[Diagnosis]:
        """取得子分類診斷

        Args:
            parent_code: 父代碼

        Returns:
            List[Diagnosis]: 子診斷列表
        """
        results = []

        for item in self._icd10_data:
            code = item["code"]
            if code.startswith(parent_code + ".") or (
                len(parent_code) == 3 and code.startswith(parent_code) and "." in code
            ):
                results.append(
                    Diagnosis(
                        icd10_code=code,
                        name=item["nameCn"],
                        name_en=item.get("nameEn", ""),
                        confidence=1.0,
                        confidence_level=DiagnosisConfidence.HIGH,
                        symptoms=[],
                        differential_diagnoses=[],
                        recommendations=[],
                        severity=None,
                        onset=None,
                        duration=None,
                        notes=None,
                    )
                )

        return results

    def get_parent(self, child_code: str) -> Optional[Diagnosis]:
        """取得父分類診斷

        Args:
            child_code: 子代碼

        Returns:
            Diagnosis: 父診斷，若未找到則返回 None
        """
        # 尋找父代碼 (移除最後一部分)
        parts = child_code.split(".")
        if len(parts) > 1:
            parent_code = ".".join(parts[:-1])
        else:
            # 如果是三碼代碼，尋找章節
            if len(child_code) == 3:
                parent_code = child_code[0]
            else:
                return None

        return self.search_by_code(parent_code)

    def get_chapter(self, code: str) -> Optional[str]:
        """取得章節代碼

        Args:
            code: ICD-10 代碼

        Returns:
            str: 章節代碼，若未找到則返回 None
        """
        if not code:
            return None

        chapter_code = code[0]
        chapter_names = {
            "A": "某些傳染病及寄生蟲病",
            "B": "某些傳染病及寄生蟲病",
            "C": "腫瘤",
            "D": "血液及造血器官疾病和某些涉及免疫機制的疾患",
            "E": "內分泌、營養和代謝疾病",
            "F": "精神與行為障礙",
            "G": "神經系統疾病",
            "H": "眼和附器疾病",
            "I": "循環系統疾病",
            "J": "呼吸系統疾病",
            "K": "消化系統疾病",
            "L": "皮膚和皮下組織疾病",
            "M": "肌肉骨骼系統和結締組織疾病",
            "N": "泌尿生殖系統疾病",
            "O": "妊娠、分娩和產褥期",
            "P": "起源於圍生期的某些情況",
            "Q": "先天性畸形、變形和染色體異常",
            "R": "症狀、體徵和臨床與實驗室異常所見，不可歸類在他處者",
            "S": "損傷、中毒和外因的某些其他後果",
            "T": "損傷、中毒和外因的某些其他後果",
            "V": "疾病和死亡的外因",
            "Y": "疾病和死亡的外因",
            "Z": "影響健康狀態和與保健機構接觸的因素",
        }

        return chapter_names.get(chapter_code, "未知章節")

    def _get_category_from_code(self, code: str) -> str:
        """從代碼取得分類

        Args:
            code: ICD-10 代碼

        Returns:
            str: 分類名稱
        """
        if not code:
            return "其他"

        first_char = code[0]
        category_map = {
            "A": "傳染病",
            "B": "傳染病",
            "C": "腫瘤",
            "D": "血液疾病",
            "E": "內分泌疾病",
            "F": "精神疾病",
            "G": "神經疾病",
            "H": "眼科疾病",
            "I": "心血管疾病",
            "J": "呼吸疾病",
            "K": "消化疾病",
            "L": "皮膚疾病",
            "M": "骨骼肌肉疾病",
            "N": "泌尿疾病",
            "O": "產科疾病",
            "P": "新生兒疾病",
            "Q": "先天性疾病",
            "R": "症狀",
            "S": "損傷",
            "T": "損傷",
            "V": "外因",
            "Y": "外因",
            "Z": "健康狀態",
        }

        return category_map.get(first_char, "其他")

    def validate_code(self, code: str) -> bool:
        """驗證 ICD-10 代碼格式

        Args:
            code: ICD-10 代碼

        Returns:
            bool: 是否為有效格式
        """
        if not code:
            return False

        # 基本格式檢查: 字母開頭，後接數字和點號
        pattern = r"^[A-Z][0-9]{2}(\.[0-9]{1,2})?$"
        return bool(re.match(pattern, code))

    def get_code_info(self, code: str) -> Optional[Dict[str, Any]]:
        """取得代碼詳細資訊

        Args:
            code: ICD-10 代碼

        Returns:
            Dict[str, Any]: 代碼詳細資訊，若未找到則返回 None
        """
        for item in self._icd10_data:
            if item["code"] == code:
                return {
                    "code": item["code"],
                    "name_cn": item.get("nameCn", ""),
                    "name_en": item.get("nameEn", ""),
                    "use": item.get("use", "0"),
                    "chapter": self.get_chapter(code),
                    "category": self._get_category_from_code(code),
                }
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """取得統計資料

        Returns:
            Dict[str, Any]: 統計資料
        """
        total = len(self._icd10_data)

        # 計算各章節數量
        chapter_counts = {}
        for item in self._icd10_data:
            chapter = self.get_chapter(item["code"])
            if chapter:
                chapter_counts[chapter] = chapter_counts.get(chapter, 0) + 1

        return {
            "total_diagnoses": total,
            "chapters": chapter_counts,
            "data_source": "file"
            if self._data_path and Path(self._data_path).exists()
            else "example",
        }
