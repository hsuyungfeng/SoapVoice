"""整合協調器 — 協調三個醫療子系統的完整流程"""

import logging
from typing import List, Optional
from dataclasses import dataclass

from ..models.soap_note import SOAPNote
from ..models.diagnosis import Diagnosis
from ..models.medical_order import MedicalOrder
from ..models.drug_recommendation import DrugRecommendation
from .diagnosis_engine import DiagnosisEngine
from .order_generator import OrderGenerator
from .drug_recommender import DrugRecommender


logger = logging.getLogger(__name__)


@dataclass
class IntegrationResult:
    """整合處理結果"""

    soap_note: SOAPNote
    diagnoses: List[Diagnosis]
    orders: List[MedicalOrder]
    drug_recommendations: List[DrugRecommendation]
    total_fee: float
    processing_time: float

    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "soap_note": self.soap_note.dict(),
            "diagnoses": [d.to_dict() for d in self.diagnoses],
            "orders": [o.to_dict() for o in self.orders],
            "drug_recommendations": [d.to_dict() for d in self.drug_recommendations],
            "total_fee": self.total_fee,
            "processing_time": self.processing_time,
            "summary": {
                "diagnosis_count": len(self.diagnoses),
                "order_count": len(self.orders),
                "drug_count": len(self.drug_recommendations),
                "primary_diagnosis": self.diagnoses[0].name if self.diagnoses else None,
            },
        }

    def __str__(self) -> str:
        """字串表示"""
        lines = [
            "=" * 60,
            f"SOAP 病歷分析結果",
            "=" * 60,
            "",
            f"病患: {self.soap_note.patient_id or '未指定'}",
            f"就診日期: {self.soap_note.visit_date or '未指定'}",
            "",
            "診斷結果:",
            "-" * 40,
            f"共 {len(self.diagnoses)} 個診斷",
        ]

        for i, diagnosis in enumerate(self.diagnoses[:3], 1):
            lines.append(f"{i}. {diagnosis.icd10_code} - {diagnosis.name}")
            lines.append(f"   信心度: {diagnosis.confidence:.1%}")

        if len(self.diagnoses) > 3:
            lines.append(f"  ... 共 {len(self.diagnoses)} 個診斷")

        lines.extend(["", "醫囑建議:", "-" * 40, f"共 {len(self.orders)} 個醫囑"])

        for i, order in enumerate(self.orders[:3], 1):
            lines.append(f"{i}. {order.code} - {order.name}")
            lines.append(f"   類型: {order.order_type.value}")

        if len(self.orders) > 3:
            lines.append(f"  ... 共 {len(self.orders)} 個醫囑")

        lines.extend(["", "藥物建議:", "-" * 40, f"共 {len(self.drug_recommendations)} 種建議藥物"])

        for i, drug in enumerate(self.drug_recommendations[:3], 1):
            lines.append(f"{i}. {drug.drug.name} - {drug.drug.generic_name or 'N/A'}")
            lines.append(f"   劑量: {drug.dosage} {drug.frequency}")

        if len(self.drug_recommendations) > 3:
            lines.append(f"  ... 共 {len(self.drug_recommendations)} 種藥物")

        lines.append("=" * 60)
        return "\n".join(lines)


class IntegrationOrchestrator:
    """整合協調器"""

    def __init__(
        self,
        diagnosis_engine: Optional[DiagnosisEngine] = None,
        order_generator: Optional[OrderGenerator] = None,
        drug_recommender: Optional[DrugRecommender] = None,
    ):
        """初始化整合協調器

        Args:
            diagnosis_engine: 診斷引擎
            order_generator: 醫囑生成器
            drug_recommender: 藥物推薦器
        """
        self._diagnosis_engine = diagnosis_engine or DiagnosisEngine()
        self._order_generator = order_generator or OrderGenerator()
        self._drug_recommender = drug_recommender or DrugRecommender()
        logger.info("整合協調器初始化完成")

    def process_soap_note(self, soap_note: SOAPNote) -> IntegrationResult:
        """處理 SOAP 病歷並執行完整流程

        Args:
            soap_note: SOAP 病歷

        Returns:
            IntegrationResult: 整合處理結果
        """
        import time

        start_time = time.time()

        try:
            logger.info(f"開始處理 SOAP 病歷: {soap_note.subjective.content[:50]}...")

            # 步驟 1: 提取症狀並匹配診斷
            symptoms = self._diagnosis_engine.extract_symptoms(soap_note)
            diagnosis_result = self._diagnosis_engine.match_diagnoses(symptoms)
            diagnoses = diagnosis_result.diagnoses

            if not diagnoses:
                logger.warning("未找到匹配的診斷")
                diagnoses = []

            logger.info(f"找到 {len(diagnoses)} 個診斷")

            # 步驟 2: 根據主要診斷生成醫囑
            orders = []
            total_fee = 0.0

            if diagnoses:
                primary_diagnosis = diagnoses[0]
                order_result = self._order_generator.generate_orders(
                    primary_diagnosis.icd10_code, categories=["診斷", "檢查", "治療", "藥物"]
                )
                orders = order_result.orders
                total_fee = order_result.total_fee
                logger.info(f"生成 {len(orders)} 個醫囑，總費用 {total_fee}")

            # 步驟 3: 根據診斷推薦藥物
            drug_recommendations = []

            if diagnoses:
                for diagnosis in diagnoses[:2]:  # 前兩個診斷
                    drug_result = self._drug_recommender.recommend_drugs(
                        diagnosis.icd10_code, max_recommendations=5
                    )
                    drug_recommendations.extend(drug_result.recommendations)

                logger.info(f"推薦 {len(drug_recommendations)} 種藥物")

            # 計算處理時間
            processing_time = time.time() - start_time

            result = IntegrationResult(
                soap_note=soap_note,
                diagnoses=diagnoses,
                orders=orders,
                drug_recommendations=drug_recommendations,
                total_fee=total_fee,
                processing_time=processing_time,
            )

            logger.info(f"SOAP 病歷處理完成，耗時 {processing_time:.2f} 秒")
            return result

        except Exception as e:
            logger.error(f"處理 SOAP 病歷時發生錯誤: {e}")
            raise

    def process_batch(self, soap_notes: List[SOAPNote]) -> List[IntegrationResult]:
        """批次處理多個 SOAP 病歷

        Args:
            soap_notes: SOAP 病歷列表

        Returns:
            整合處理結果列表
        """
        results = []

        logger.info(f"開始批次處理 {len(soap_notes)} 個 SOAP 病歷")

        for i, soap_note in enumerate(soap_notes, 1):
            try:
                logger.info(f"處理第 {i}/{len(soap_notes)} 個病歷")
                result = self.process_soap_note(soap_note)
                results.append(result)

            except Exception as e:
                logger.error(f"處理第 {i} 個病歷時發生錯誤: {e}")
                # 繼續處理下一個病歷

        logger.info(f"批次處理完成，成功處理 {len(results)}/{len(soap_notes)} 個病歷")
        return results

    def optimize_treatment_plan(
        self, result: IntegrationResult, budget: Optional[float] = None, priority: str = "standard"
    ) -> IntegrationResult:
        """優化治療計畫

        Args:
            result: 原始整合結果
            budget: 預算限制
            priority: 優先級別

        Returns:
            優化後的整合結果
        """
        if not result.diagnoses:
            return result

        logger.info("開始優化治療計畫")

        # 優化醫囑
        optimized_orders = result.orders

        if priority != "standard":
            optimized_orders = self._order_generator.filter_orders_by_priority(
                optimized_orders, priority
            )

        if budget is not None:
            optimized_orders = self._order_generator.optimize_orders(optimized_orders, budget)

        # 重新計算總費用
        total_fee = sum(order.fee for order in optimized_orders)

        # 根據優化後的醫囑調整藥物推薦
        optimized_drugs = result.drug_recommendations

        # 創建優化後的結果
        optimized_result = IntegrationResult(
            soap_note=result.soap_note,
            diagnoses=result.diagnoses,
            orders=optimized_orders,
            drug_recommendations=optimized_drugs,
            total_fee=total_fee,
            processing_time=result.processing_time,
        )

        logger.info(
            f"治療計畫優化完成，醫囑從 {len(result.orders)} 優化為 {len(optimized_orders)} 個"
        )
        return optimized_result

    def generate_report(self, result: IntegrationResult, format: str = "text") -> str:
        """生成報告

        Args:
            result: 整合結果
            format: 報告格式 (text/json/markdown)

        Returns:
            報告內容
        """
        if format == "json":
            import json

            return json.dumps(result.to_dict(), ensure_ascii=False, indent=2)

        elif format == "markdown":
            return self._generate_markdown_report(result)

        else:  # text
            return str(result)

    def _generate_markdown_report(self, result: IntegrationResult) -> str:
        """生成 Markdown 格式報告

        Args:
            result: 整合結果

        Returns:
            Markdown 報告
        """
        lines = [
            "# CliVoice 醫療整合報告",
            "",
            f"**生成時間**: {result.processing_time:.2f} 秒",
            "",
            "## SOAP 病歷摘要",
            f"{result.soap_note.subjective.content[:50]}...",
            "",
            "## 診斷結果",
            "",
        ]

        for diagnosis in result.diagnoses:
            confidence_star = "⭐ " if diagnosis.confidence > 0.7 else ""
            lines.append(f"- **{diagnosis.code}** - {diagnosis.name} {confidence_star}")
            lines.append(f"  - 信心度: {diagnosis.confidence:.1%}")
            if diagnosis.description:
                lines.append(f"  - 描述: {diagnosis.description}")
            lines.append("")

        lines.extend(
            [
                "## 醫療訂單",
                f"**總計**: {len(result.orders)} 個醫囑，總費用: {result.total_fee:.2f}",
                "",
            ]
        )

        for order in result.orders:
            lines.append(f"- **{order.code}** - {order.name}")
            lines.append(f"  - 類別: {order.category}")
            lines.append(f"  - 費用: {order.fee}")
            if order.description:
                lines.append(f"  - 描述: {order.description}")
            lines.append("")

        lines.extend(
            ["## 藥物建議", f"**總計**: {len(result.drug_recommendations)} 種建議藥物", ""]
        )

        for drug in result.drug_recommendations:
            lines.append(f"- **{drug.code}** - {drug.name}")
            if drug.atc_code:
                lines.append(f"  - ATC 代碼: {drug.atc_code}")
            if drug.form:
                lines.append(f"  - 劑型: {drug.form}")
            if drug.indications:
                lines.append(f"  - 適應症: {drug.indications}")
            lines.append("")

        lines.append("---")
        lines.append("*本報告由 CliVoice 系統自動生成*")

        return "\n".join(lines)
