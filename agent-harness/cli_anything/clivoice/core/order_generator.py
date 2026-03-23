"""醫囑生成器 — 根據診斷生成醫療服務訂單"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from ..models.medical_order import MedicalOrder
from ..adapters.medical_order_adapter import MedicalOrderAdapter


logger = logging.getLogger(__name__)


@dataclass
class OrderGenerationResult:
    """醫囑生成結果"""

    diagnosis_code: str
    orders: List[MedicalOrder]
    total_fee: float
    categories: List[str]

    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "diagnosis_code": self.diagnosis_code,
            "orders": [order.to_dict() for order in self.orders],
            "total_fee": self.total_fee,
            "categories": self.categories,
            "order_count": len(self.orders),
        }

    def __str__(self) -> str:
        """字串表示"""
        return (
            f"診斷: {self.diagnosis_code}\n"
            f"醫囑數量: {len(self.orders)}\n"
            f"總費用: {self.total_fee}\n"
            f"類別: {', '.join(self.categories)}"
        )


class OrderGenerator:
    """醫囑生成器"""

    def __init__(self, adapter: Optional[MedicalOrderAdapter] = None):
        """初始化醫囑生成器

        Args:
            adapter: 醫療訂單適配器，若為 None 則自動建立
        """
        self._adapter = adapter or MedicalOrderAdapter()
        logger.info("醫囑生成器初始化完成")

    def generate_orders(
        self,
        diagnosis_code: str,
        categories: Optional[List[str]] = None,
        max_fee: Optional[float] = None,
    ) -> OrderGenerationResult:
        """根據診斷代碼生成醫囑

        Args:
            diagnosis_code: 診斷代碼
            categories: 醫囑類別篩選
            max_fee: 最大費用限制

        Returns:
            OrderGenerationResult: 醫囑生成結果
        """
        try:
            logger.info(f"為診斷 {diagnosis_code} 生成醫囑")

            # 取得相關醫囑
            orders = self._adapter.get_orders_by_diagnosis(diagnosis_code, categories)

            if not orders:
                logger.warning(f"未找到診斷 {diagnosis_code} 的相關醫囑")
                return OrderGenerationResult(
                    diagnosis_code=diagnosis_code,
                    orders=[],
                    total_fee=0.0,
                    categories=categories or [],
                )

            # 應用費用限制
            if max_fee is not None:
                orders = [order for order in orders if order.fee <= max_fee]
                logger.info(f"應用費用限制後剩餘 {len(orders)} 個醫囑")

            # 計算總費用
            total_fee = sum(order.fee for order in orders)

            # 收集類別
            all_categories = list(set(order.category for order in orders))

            result = OrderGenerationResult(
                diagnosis_code=diagnosis_code,
                orders=orders,
                total_fee=total_fee,
                categories=all_categories,
            )

            logger.info(f"為診斷 {diagnosis_code} 生成 {len(orders)} 個醫囑，總費用 {total_fee}")
            return result

        except Exception as e:
            logger.error(f"生成醫囑時發生錯誤: {e}")
            raise

    def filter_orders_by_priority(
        self, orders: List[MedicalOrder], priority_level: str = "standard"
    ) -> List[MedicalOrder]:
        """根據優先級篩選醫囑

        Args:
            orders: 醫囑列表
            priority_level: 優先級別 (essential/standard/optional)

        Returns:
            篩選後的醫囑列表
        """
        priority_map = {
            "essential": ["診斷", "檢查", "治療"],
            "standard": ["診斷", "檢查", "治療", "藥物", "追蹤"],
            "optional": ["診斷", "檢查", "治療", "藥物", "追蹤", "衛教", "復健"],
        }

        if priority_level not in priority_map:
            logger.warning(f"未知的優先級別 {priority_level}，使用 standard")
            priority_level = "standard"

        allowed_categories = priority_map[priority_level]
        filtered = [order for order in orders if order.category in allowed_categories]

        logger.info(
            f"根據優先級 {priority_level} 篩選，從 {len(orders)} 個篩選到 {len(filtered)} 個醫囑"
        )
        return filtered

    def optimize_orders(self, orders: List[MedicalOrder], budget: float) -> List[MedicalOrder]:
        """根據預算優化醫囑選擇

        Args:
            orders: 醫囑列表
            budget: 預算限制

        Returns:
            優化後的醫囑列表
        """
        if not orders:
            return []

        # 簡單的貪婪算法：按費用效益比排序
        # 這裡假設每個醫囑都有優先級分數 (1-10)
        scored_orders = []
        for order in orders:
            # 計算費用效益比 (分數/費用)
            # 實際應用中應有更複雜的評分機制
            score = self._calculate_order_score(order)
            cost_benefit = score / max(order.fee, 1.0)
            scored_orders.append((cost_benefit, order))

        # 按費用效益比降序排序
        scored_orders.sort(key=lambda x: x[0], reverse=True)

        # 選擇不超過預算的醫囑
        selected = []
        current_cost = 0.0

        for _, order in scored_orders:
            if current_cost + order.fee <= budget:
                selected.append(order)
                current_cost += order.fee
            else:
                break

        logger.info(
            f"預算優化: 預算 {budget}，選擇 {len(selected)}/{len(orders)} 個醫囑，總費用 {current_cost}"
        )
        return selected

    def _calculate_order_score(self, order: MedicalOrder) -> float:
        """計算醫囑分數

        Args:
            order: 醫療訂單

        Returns:
            分數 (1-10)
        """
        # 簡單的評分規則
        category_scores = {
            "診斷": 10.0,
            "治療": 9.0,
            "檢查": 8.0,
            "藥物": 7.0,
            "追蹤": 6.0,
            "衛教": 5.0,
            "復健": 4.0,
        }

        base_score = category_scores.get(order.category, 5.0)

        # 根據費用調整分數 (費用越低分數越高)
        fee_factor = 1.0 / max(order.fee / 1000.0, 0.1)

        return min(base_score * fee_factor, 10.0)
