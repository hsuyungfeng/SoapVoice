"""醫療訂單適配器 — 整合 medicalordertreeview 醫療服務支付標準系統"""

import json
import logging
import requests
from typing import List, Optional, Dict, Any
from pathlib import Path

from ..models.medical_order import MedicalOrder


logger = logging.getLogger(__name__)


class MedicalOrderAdapter:
    """醫療訂單適配器"""

    def __init__(self, api_base_url: Optional[str] = None):
        """初始化醫療訂單適配器

        Args:
            api_base_url: API 基礎 URL，若為 None 則使用預設或本地資料
        """
        self._api_base_url = api_base_url or "http://localhost:5000"
        self._local_data_path = self._get_local_data_path()
        self._diagnosis_to_orders: Dict[str, List[Dict[str, Any]]] = {}
        self._load_data()
        logger.info(f"醫療訂單適配器初始化完成，API: {self._api_base_url}")

    def _get_local_data_path(self) -> Optional[str]:
        """取得本地資料路徑"""
        base_path = Path(__file__).parent.parent.parent.parent.parent
        data_path = base_path / "CliVoice" / "medicalordertreeview" / "backend" / "data"

        if data_path.exists():
            return str(data_path)

        return None

    def _load_data(self):
        """載入醫療訂單資料"""
        try:
            if self._test_api_connection():
                logger.info("API 連線正常，使用 API 模式")
                self._use_api_mode = True
            else:
                logger.info("API 連線失敗，使用本地資料模式")
                self._use_api_mode = False
                self._load_local_data()

        except Exception as e:
            logger.error(f"載入醫療訂單資料時發生錯誤: {e}")
            self._use_api_mode = False
            self._load_example_data()

    def _test_api_connection(self) -> bool:
        """測試 API 連線

        Returns:
            bool: 連線是否成功
        """
        try:
            response = requests.get(f"{self._api_base_url}/api/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _load_local_data(self):
        """載入本地資料"""
        if not self._local_data_path:
            logger.warning("無本地資料路徑，使用範例資料")
            self._load_example_data()
            return

        try:
            data_dir = Path(self._local_data_path)
            json_files = list(data_dir.glob("*.json"))
            if json_files:
                for json_file in json_files[:3]:
                    try:
                        with open(json_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            self._process_data_file(data)
                    except Exception as e:
                        logger.warning(f"無法讀取檔案 {json_file}: {e}")

            if not self._diagnosis_to_orders:
                self._load_example_data()

        except Exception as e:
            logger.error(f"載入本地資料時發生錯誤: {e}")
            self._load_example_data()

    def _process_data_file(self, data: Any):
        """處理資料檔案

        Args:
            data: 資料內容
        """
        if isinstance(data, list):
            for item in data:
                self._process_order_item(item)
        elif isinstance(data, dict):
            if "items" in data:
                for item in data["items"]:
                    self._process_order_item(item)
            else:
                self._process_order_item(data)

    def _process_order_item(self, item: Dict[str, Any]):
        """處理訂單項目

        Args:
            item: 訂單項目
        """
        try:
            diagnosis_codes = item.get("diagnosis_codes", [])
            if not diagnosis_codes and "diagnosis_code" in item:
                diagnosis_codes = [item["diagnosis_code"]]

            order = {
                "code": item.get("code", ""),
                "name": item.get("name", ""),
                "category": item.get("category", "其他"),
                "fee": float(item.get("fee", 0.0)),
                "description": item.get("description", ""),
                "unit": item.get("unit", "次"),
                "frequency": item.get("frequency", "依醫囑"),
                "duration": item.get("duration", ""),
                "priority": item.get("priority", "standard"),
            }

            for diagnosis_code in diagnosis_codes:
                if diagnosis_code not in self._diagnosis_to_orders:
                    self._diagnosis_to_orders[diagnosis_code] = []
                self._diagnosis_to_orders[diagnosis_code].append(order)

        except Exception as e:
            logger.warning(f"處理訂單項目時發生錯誤: {e}")

    def _load_example_data(self):
        """載入範例資料"""
        logger.info("載入範例醫療訂單資料")

        example_orders = {
            "J06.9": [
                {
                    "code": "M001",
                    "name": "一般診察費",
                    "category": "診斷",
                    "fee": 150.0,
                    "description": "門診一般診察",
                    "unit": "次",
                    "frequency": "1次",
                    "priority": "essential",
                },
                {
                    "code": "L001",
                    "name": "喉部檢查",
                    "category": "檢查",
                    "fee": 100.0,
                    "description": "喉部視診檢查",
                    "unit": "次",
                    "frequency": "1次",
                    "priority": "standard",
                },
                {
                    "code": "D001",
                    "name": "感冒藥",
                    "category": "藥物",
                    "fee": 50.0,
                    "description": "感冒症狀緩解藥物",
                    "unit": "日份",
                    "frequency": "每日3次，飯後",
                    "duration": "3天",
                    "priority": "essential",
                },
            ],
            "J20.9": [
                {
                    "code": "M001",
                    "name": "一般診察費",
                    "category": "診斷",
                    "fee": 150.0,
                    "description": "門診一般診察",
                    "unit": "次",
                    "frequency": "1次",
                    "priority": "essential",
                },
                {
                    "code": "C001",
                    "name": "胸部X光檢查",
                    "category": "檢查",
                    "fee": 300.0,
                    "description": "胸部X光攝影檢查",
                    "unit": "次",
                    "frequency": "1次",
                    "priority": "standard",
                },
                {
                    "code": "D002",
                    "name": "支氣管擴張劑",
                    "category": "藥物",
                    "fee": 80.0,
                    "description": "緩解支氣管痙攣藥物",
                    "unit": "日份",
                    "frequency": "每日3次",
                    "duration": "5天",
                    "priority": "essential",
                },
            ],
            "K29.70": [
                {
                    "code": "M001",
                    "name": "一般診察費",
                    "category": "診斷",
                    "fee": 150.0,
                    "description": "門診一般診察",
                    "unit": "次",
                    "frequency": "1次",
                    "priority": "essential",
                },
                {
                    "code": "G001",
                    "name": "胃鏡檢查",
                    "category": "檢查",
                    "fee": 1200.0,
                    "description": "上消化道內視鏡檢查",
                    "unit": "次",
                    "frequency": "1次",
                    "priority": "standard",
                },
                {
                    "code": "D004",
                    "name": "胃藥",
                    "category": "藥物",
                    "fee": 60.0,
                    "description": "制酸劑保護胃黏膜",
                    "unit": "日份",
                    "frequency": "每日2次，飯前",
                    "duration": "7天",
                    "priority": "essential",
                },
            ],
        }

        self._diagnosis_to_orders = example_orders

    def get_orders_by_diagnosis(
        self, diagnosis_code: str, category: Optional[str] = None
    ) -> List[MedicalOrder]:
        """根據診斷代碼取得相關醫囑

        Args:
            diagnosis_code: 診斷代碼
            category: 醫囑類別篩選

        Returns:
            List[MedicalOrder]: 醫療訂單列表
        """
        try:
            if self._use_api_mode:
                return self._get_orders_from_api(diagnosis_code, category)
            else:
                return self._get_orders_from_local(diagnosis_code, category)

        except Exception as e:
            logger.error(f"取得醫囑時發生錯誤: {e}")
            return []

    def _get_orders_from_api(
        self, diagnosis_code: str, category: Optional[str]
    ) -> List[MedicalOrder]:
        """從 API 取得醫囑

        Args:
            diagnosis_code: 診斷代碼
            category: 醫囑類別篩選

        Returns:
            List[MedicalOrder]: 醫療訂單列表
        """
        try:
            params = {"diagnosis_code": diagnosis_code}
            if category:
                params["category"] = category

            response = requests.get(f"{self._api_base_url}/api/orders", params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                orders = []

                for item in data.get("orders", []):
                    order = MedicalOrder(
                        code=item.get("code", ""),
                        name=item.get("name", ""),
                        category=item.get("category", "其他"),
                        fee=float(item.get("fee", 0.0)),
                        description=item.get("description", ""),
                        unit=item.get("unit", "次"),
                        frequency=item.get("frequency", "依醫囑"),
                        duration=item.get("duration", ""),
                        priority=item.get("priority", "standard"),
                    )
                    orders.append(order)

                logger.info(f"從 API 取得 {len(orders)} 個醫囑")
                return orders
            else:
                logger.warning(f"API 請求失敗: {response.status_code}")
                return self._get_orders_from_local(diagnosis_code, category)

        except Exception as e:
            logger.error(f"API 請求時發生錯誤: {e}")
            return self._get_orders_from_local(diagnosis_code, category)

    def _get_orders_from_local(
        self, diagnosis_code: str, category: Optional[str]
    ) -> List[MedicalOrder]:
        """從本地資料取得醫囑

        Args:
            diagnosis_code: 診斷代碼
            category: 醫囑類別篩選

        Returns:
            List[MedicalOrder]: 醫療訂單列表
        """
        orders_data = self._diagnosis_to_orders.get(diagnosis_code, [])
        orders = []

        for item in orders_data:
            if category and item.get("category") != category:
                continue

            order = MedicalOrder(
                code=item.get("code", ""),
                name=item.get("name", ""),
                category=item.get("category", "其他"),
                fee=float(item.get("fee", 0.0)),
                description=item.get("description", ""),
                unit=item.get("unit", "次"),
                frequency=item.get("frequency", "依醫囑"),
                duration=item.get("duration", ""),
                priority=item.get("priority", "standard"),
            )
            orders.append(order)

        logger.info(f"從本地資料取得 {len(orders)} 個醫囑")
        return orders

    def search_orders(self, keyword: str, max_results: int = 20) -> List[MedicalOrder]:
        """搜尋醫囑

        Args:
            keyword: 搜尋關鍵字
            max_results: 最大結果數量

        Returns:
            List[MedicalOrder]: 醫療訂單列表
        """
        try:
            if self._use_api_mode:
                return self._search_orders_from_api(keyword, max_results)
            else:
                return self._search_orders_from_local(keyword, max_results)

        except Exception as e:
            logger.error(f"搜尋醫囑時發生錯誤: {e}")
            return []

    def _search_orders_from_api(self, keyword: str, max_results: int) -> List[MedicalOrder]:
        """從 API 搜尋醫囑

        Args:
            keyword: 搜尋關鍵字
            max_results: 最大結果數量

        Returns:
            List[MedicalOrder]: 醫療訂單列表
        """
        try:
            response = requests.get(
                f"{self._api_base_url}/api/orders/search",
                params={"q": keyword, "limit": max_results},
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                orders = []

                for item in data.get("results", []):
                    order = MedicalOrder(
                        code=item.get("code", ""),
                        name=item.get("name", ""),
                        category=item.get("category", "其他"),
                        fee=float(item.get("fee", 0.0)),
                        description=item.get("description", ""),
                        unit=item.get("unit", "次"),
                        frequency=item.get("frequency", "依醫囑"),
                        duration=item.get("duration", ""),
                        priority=item.get("priority", "standard"),
                    )
                    orders.append(order)

                logger.info(f"從 API 搜尋到 {len(orders)} 個醫囑")
                return orders
            else:
                logger.warning(f"API 搜尋失敗: {response.status_code}")
                return self._search_orders_from_local(keyword, max_results)

        except Exception as e:
            logger.error(f"API 搜尋時發生錯誤: {e}")
            return self._search_orders_from_local(keyword, max_results)

    def _search_orders_from_local(self, keyword: str, max_results: int) -> List[MedicalOrder]:
        """從本地資料搜尋醫囑

        Args:
            keyword: 搜尋關鍵字
            max_results: 最大結果數量

        Returns:
            List[MedicalOrder]: 醫療訂單列表
        """
        keyword_lower = keyword.lower()
        results = []

        for diagnosis_code, orders_data in self._diagnosis_to_orders.items():
            for item in orders_data:
                name = item.get("name", "").lower()
                description = item.get("description", "").lower()

                if (
                    keyword_lower in name
                    or keyword_lower in description
                    or keyword_lower in diagnosis_code.lower()
                ):
                    order = MedicalOrder(
                        code=item.get("code", ""),
                        name=item.get("name", ""),
                        category=item.get("category", "其他"),
                        fee=float(item.get("fee", 0.0)),
                        description=item.get("description", ""),
                        unit=item.get("unit", "次"),
                        frequency=item.get("frequency", "依醫囑"),
                        duration=item.get("duration", ""),
                        priority=item.get("priority", "standard"),
                    )
                    results.append(order)

                    if len(results) >= max_results:
                        break

            if len(results) >= max_results:
                break

        logger.info(f"從本地資料搜尋到 {len(results)} 個醫囑")
        return results
