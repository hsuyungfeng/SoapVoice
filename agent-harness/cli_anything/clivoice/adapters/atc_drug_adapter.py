"""ATC 藥物適配器 — 整合 ATCcodeTW 台灣藥物分類系統"""

import json
import logging
import requests
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..models.drug_recommendation import DrugRecommendation


logger = logging.getLogger(__name__)


class ATCDrugAdapter:
    """ATC 藥物適配器"""

    def __init__(self, api_base_url: Optional[str] = None):
        self._api_base_url = api_base_url or "http://localhost:5001"
        self._local_data_path = self._get_local_data_path()
        self._diagnosis_to_drugs: Dict[str, List[Dict[str, Any]]] = {}
        self._load_data()
        logger.info(f"ATC 藥物適配器初始化完成")

    def _get_local_data_path(self) -> Optional[str]:
        base_path = Path(__file__).parent.parent.parent.parent.parent
        data_path = base_path / "CliVoice" / "ATCcodeTW" / "data"
        return str(data_path) if data_path.exists() else None

    def _load_data(self):
        try:
            if self._test_api_connection():
                logger.info("API 連線正常")
                self._use_api_mode = True
            else:
                logger.info("API 連線失敗，使用本地資料")
                self._use_api_mode = False
                self._load_example_data()
        except Exception as e:
            logger.error(f"載入資料時發生錯誤: {e}")
            self._use_api_mode = False
            self._load_example_data()

    def _test_api_connection(self) -> bool:
        try:
            response = requests.get(f"{self._api_base_url}/api/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _load_example_data(self):
        logger.info("載入範例 ATC 藥物資料")

        example_drugs = {
            "J06.9": [
                {
                    "code": "ACET01",
                    "name": "乙醯胺酚",
                    "atc_code": "N02BE01",
                    "form": "口服錠劑",
                    "indications": "退燒、止痛",
                    "dosage": "成人每次500mg",
                    "category": "解熱鎮痛藥",
                },
                {
                    "code": "IBUP01",
                    "name": "布洛芬",
                    "atc_code": "M01AE01",
                    "form": "口服錠劑",
                    "indications": "退燒、止痛、消炎",
                    "dosage": "成人每次200-400mg",
                    "category": "消炎鎮痛藥",
                },
            ],
            "J20.9": [
                {
                    "code": "AMOX01",
                    "name": "阿莫西林",
                    "atc_code": "J01CA04",
                    "form": "口服膠囊",
                    "indications": "細菌感染、支氣管炎",
                    "dosage": "成人每次500mg",
                    "category": "抗生素",
                },
                {
                    "code": "SALB01",
                    "name": "沙丁胺醇",
                    "atc_code": "R03AC02",
                    "form": "吸入劑",
                    "indications": "支氣管痙攣",
                    "dosage": "需要時1-2噴",
                    "category": "呼吸系統藥",
                },
            ],
            "K29.70": [
                {
                    "code": "OMEP01",
                    "name": "奧美拉唑",
                    "atc_code": "A02BC01",
                    "form": "口服膠囊",
                    "indications": "胃潰瘍、胃炎",
                    "dosage": "成人每日20-40mg",
                    "category": "消化系統藥",
                },
                {
                    "code": "RANIT01",
                    "name": "雷尼替丁",
                    "atc_code": "A02BA02",
                    "form": "口服錠劑",
                    "indications": "胃潰瘍、胃炎",
                    "dosage": "成人每次150mg",
                    "category": "消化系統藥",
                },
            ],
        }

        self._diagnosis_to_drugs = example_drugs

    def get_drugs_by_diagnosis(
        self, diagnosis_code: str, atc_class: Optional[str] = None
    ) -> List[DrugRecommendation]:
        try:
            if self._use_api_mode:
                return self._get_drugs_from_api(diagnosis_code, atc_class)
            else:
                return self._get_drugs_from_local(diagnosis_code, atc_class)
        except Exception as e:
            logger.error(f"取得藥物時發生錯誤: {e}")
            return []

    def _get_drugs_from_api(
        self, diagnosis_code: str, atc_class: Optional[str]
    ) -> List[DrugRecommendation]:
        try:
            params = {"diagnosis_code": diagnosis_code}
            if atc_class:
                params["atc_class"] = atc_class

            response = requests.get(f"{self._api_base_url}/api/drugs", params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                drugs = []

                for item in data.get("drugs", []):
                    drug = DrugRecommendation(
                        code=item.get("code", ""),
                        name=item.get("name", ""),
                        atc_code=item.get("atc_code", ""),
                        form=item.get("form", ""),
                        indications=item.get("indications", ""),
                        dosage=item.get("dosage", ""),
                        contraindications=item.get("contraindications", ""),
                        side_effects=item.get("side_effects", ""),
                        notes=item.get("notes", ""),
                        category=item.get("category", "其他"),
                    )
                    drugs.append(drug)

                logger.info(f"從 API 取得 {len(drugs)} 種藥物")
                return drugs
            else:
                logger.warning(f"API 請求失敗: {response.status_code}")
                return self._get_drugs_from_local(diagnosis_code, atc_class)

        except Exception as e:
            logger.error(f"API 請求時發生錯誤: {e}")
            return self._get_drugs_from_local(diagnosis_code, atc_class)

    def _get_drugs_from_local(
        self, diagnosis_code: str, atc_class: Optional[str]
    ) -> List[DrugRecommendation]:
        drugs_data = self._diagnosis_to_drugs.get(diagnosis_code, [])
        drugs = []

        for item in drugs_data:
            if atc_class and not item.get("atc_code", "").startswith(atc_class):
                continue

            drug = DrugRecommendation(
                code=item.get("code", ""),
                name=item.get("name", ""),
                atc_code=item.get("atc_code", ""),
                form=item.get("form", ""),
                indications=item.get("indications", ""),
                dosage=item.get("dosage", ""),
                contraindications=item.get("contraindications", ""),
                side_effects=item.get("side_effects", ""),
                notes=item.get("notes", ""),
                category=item.get("category", "其他"),
            )
            drugs.append(drug)

        logger.info(f"從本地資料取得 {len(drugs)} 種藥物")
        return drugs
