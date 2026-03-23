"""藥物推薦器 — 根據診斷推薦適當藥物"""

import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from ..models.drug_recommendation import DrugRecommendation
from ..adapters.atc_drug_adapter import ATCDrugAdapter


logger = logging.getLogger(__name__)


@dataclass
class DrugRecommendationResult:
    """藥物推薦結果"""

    diagnosis_code: str
    recommendations: List[DrugRecommendation]
    atc_classes: List[str]
    total_drugs: int

    def to_dict(self) -> dict:
        """轉換為字典格式"""
        return {
            "diagnosis_code": self.diagnosis_code,
            "recommendations": [rec.to_dict() for rec in self.recommendations],
            "atc_classes": self.atc_classes,
            "total_drugs": self.total_drugs,
        }

    def __str__(self) -> str:
        """字串表示"""
        return (
            f"診斷: {self.diagnosis_code}\n"
            f"推薦藥物: {self.total_drugs} 種\n"
            f"ATC 分類: {', '.join(self.atc_classes)}"
        )


class DrugRecommender:
    """藥物推薦器"""

    def __init__(self, adapter: Optional[ATCDrugAdapter] = None):
        """初始化藥物推薦器

        Args:
            adapter: ATC 藥物適配器，若為 None 則自動建立
        """
        self._adapter = adapter or ATCDrugAdapter()
        logger.info("藥物推薦器初始化完成")

    def recommend_drugs(
        self,
        diagnosis_code: str,
        atc_classes: Optional[List[str]] = None,
        max_recommendations: int = 10,
    ) -> DrugRecommendationResult:
        """根據診斷代碼推薦藥物

        Args:
            diagnosis_code: 診斷代碼
            atc_classes: ATC 分類篩選
            max_recommendations: 最大推薦數量

        Returns:
            DrugRecommendationResult: 藥物推薦結果
        """
        try:
            logger.info(f"為診斷 {diagnosis_code} 推薦藥物")

            # 取得相關藥物
            drugs = self._adapter.get_drugs_by_diagnosis(diagnosis_code, atc_classes)

            if not drugs:
                logger.warning(f"未找到診斷 {diagnosis_code} 的相關藥物")
                return DrugRecommendationResult(
                    diagnosis_code=diagnosis_code,
                    recommendations=[],
                    atc_classes=atc_classes or [],
                    total_drugs=0,
                )

            # 限制推薦數量
            if len(drugs) > max_recommendations:
                drugs = self._prioritize_drugs(drugs)[:max_recommendations]
                logger.info(f"限制推薦數量為 {max_recommendations}")

            # 收集 ATC 分類
            all_atc_classes = list(set(drug.atc_code[:3] for drug in drugs if drug.atc_code))

            result = DrugRecommendationResult(
                diagnosis_code=diagnosis_code,
                recommendations=drugs,
                atc_classes=all_atc_classes,
                total_drugs=len(drugs),
            )

            logger.info(f"為診斷 {diagnosis_code} 推薦 {len(drugs)} 種藥物")
            return result

        except Exception as e:
            logger.error(f"推薦藥物時發生錯誤: {e}")
            raise

    def _prioritize_drugs(self, drugs: List[DrugRecommendation]) -> List[DrugRecommendation]:
        """優先排序藥物

        Args:
            drugs: 藥物列表

        Returns:
            排序後的藥物列表
        """
        # 根據多個因素排序
        scored_drugs = []
        for drug in drugs:
            score = self._calculate_drug_score(drug)
            scored_drugs.append((score, drug))

        # 按分數降序排序
        scored_drugs.sort(key=lambda x: x[0], reverse=True)
        return [drug for _, drug in scored_drugs]

    def _calculate_drug_score(self, drug: DrugRecommendation) -> float:
        """計算藥物分數

        Args:
            drug: 藥物推薦

        Returns:
            分數 (0-100)
        """
        score = 0.0

        # 1. ATC 分類分數 (越具體越好)
        if drug.atc_code:
            # ATC 代碼長度代表分類詳細程度
            atc_length = len(drug.atc_code.replace(".", ""))
            score += min(atc_length * 5, 30)  # 最多 30 分

        # 2. 適應症匹配分數
        if drug.indications:
            # 簡單的關鍵字匹配分數
            indication_keywords = ["適應症", "治療", "用於", "適用"]
            for keyword in indication_keywords:
                if keyword in drug.indications:
                    score += 10
                    break

        # 3. 劑型分數 (口服優先)
        if drug.form:
            form_scores = {"口服": 20, "注射": 15, "外用": 10, "吸入": 10, "栓劑": 5}
            score += form_scores.get(drug.form, 5)

        # 4. 藥物名稱分數 (通用名優先)
        if drug.name and "(" not in drug.name:  # 沒有商品名括號
            score += 5

        return min(score, 100.0)

    def filter_by_contraindications(
        self, drugs: List[DrugRecommendation], patient_conditions: List[str]
    ) -> List[DrugRecommendation]:
        """根據病人禁忌症篩選藥物

        Args:
            drugs: 藥物列表
            patient_conditions: 病人禁忌症列表

        Returns:
            篩選後的藥物列表
        """
        if not patient_conditions:
            return drugs

        filtered = []
        for drug in drugs:
            if not self._has_contraindications(drug, patient_conditions):
                filtered.append(drug)

        logger.info(f"禁忌症篩選: 從 {len(drugs)} 個篩選到 {len(filtered)} 個藥物")
        return filtered

    def _has_contraindications(
        self, drug: DrugRecommendation, patient_conditions: List[str]
    ) -> bool:
        """檢查藥物是否有禁忌症

        Args:
            drug: 藥物
            patient_conditions: 病人禁忌症列表

        Returns:
            是否有禁忌症
        """
        # 簡單的關鍵字匹配
        # 實際應用中應有更完整的禁忌症資料庫
        contraindication_keywords = ["肝", "腎", "心", "孕", "哺乳", "過敏", "哮喘", "青光眼"]

        for condition in patient_conditions:
            for keyword in contraindication_keywords:
                if keyword in condition:
                    # 檢查藥物是否可能與此禁忌症衝突
                    if self._check_drug_contraindication(drug, keyword):
                        return True

        return False

    def _check_drug_contraindication(
        self, drug: DrugRecommendation, condition_keyword: str
    ) -> bool:
        """檢查藥物是否與特定禁忌症衝突

        Args:
            drug: 藥物
            condition_keyword: 禁忌症關鍵字

        Returns:
            是否衝突
        """
        # 簡單的規則匹配
        # 實際應用中應有更完整的藥物禁忌症資料庫
        contraindication_rules = {
            "肝": ["肝毒性", "肝功能", "肝酶"],
            "腎": ["腎毒性", "腎功能", "肌酐"],
            "心": ["心臟", "心律", "血壓"],
            "孕": ["孕婦", "懷孕", "胎兒"],
            "過敏": ["過敏", "過敏反應"],
        }

        if condition_keyword in contraindication_rules:
            keywords = contraindication_rules[condition_keyword]
            drug_info = f"{drug.name} {drug.indications or ''} {drug.notes or ''}"

            for keyword in keywords:
                if keyword in drug_info:
                    return True

        return False

    def generate_prescription(
        self, drugs: List[DrugRecommendation], duration_days: int = 7
    ) -> Dict[str, Any]:
        """生成處方箋

        Args:
            drugs: 藥物列表
            duration_days: 治療天數

        Returns:
            處方箋字典
        """
        prescription = {
            "medications": [],
            "total_drugs": len(drugs),
            "duration_days": duration_days,
            "instructions": [],
        }

        for drug in drugs:
            med_info = {
                "name": drug.name,
                "code": drug.code,
                "atc_code": drug.atc_code,
                "form": drug.form,
                "dosage": self._suggest_dosage(drug),
                "frequency": self._suggest_frequency(drug),
                "duration": f"{duration_days} 天",
                "instructions": self._generate_instructions(drug),
            }
            prescription["medications"].append(med_info)

        # 生成用藥指示
        prescription["instructions"] = self._generate_prescription_instructions(drugs)

        return prescription

    def _suggest_dosage(self, drug: DrugRecommendation) -> str:
        """建議劑量

        Args:
            drug: 藥物

        Returns:
            劑量建議
        """
        # 簡單的劑量建議規則
        # 實際應用中應有更完整的劑量資料庫
        if "錠" in drug.form or "膠囊" in drug.form:
            return "1 錠"
        elif "毫升" in drug.form or "ml" in drug.form.lower():
            return "5-10 ml"
        elif "克" in drug.form or "g" in drug.form.lower():
            return "0.5-1 g"
        else:
            return "依醫囑"

    def _suggest_frequency(self, drug: DrugRecommendation) -> str:
        """建議用藥頻率

        Args:
            drug: 藥物

        Returns:
            頻率建議
        """
        # 簡單的頻率建議規則
        form = drug.form.lower() if drug.form else ""

        if "口服" in form:
            return "每日 3 次，飯後服用"
        elif "外用" in form:
            return "每日 2-3 次"
        elif "注射" in form:
            return "每日 1 次"
        else:
            return "依醫囑"

    def _generate_instructions(self, drug: DrugRecommendation) -> str:
        """生成用藥指示

        Args:
            drug: 藥物

        Returns:
            用藥指示
        """
        instructions = []

        if drug.indications:
            instructions.append(f"適應症: {drug.indications}")

        if drug.notes:
            instructions.append(f"注意事項: {drug.notes}")

        return "；".join(instructions)

    def _generate_prescription_instructions(self, drugs: List[DrugRecommendation]) -> List[str]:
        """生成處方箋總指示

        Args:
            drugs: 藥物列表

        Returns:
            指示列表
        """
        instructions = [
            "請按時服藥，勿自行增減劑量",
            "如有不適或過敏反應，請立即停藥並就醫",
            "請將藥物存放於陰涼乾燥處，避免兒童誤食",
        ]

        # 根據藥物類型添加特定指示
        forms = [drug.form.lower() if drug.form else "" for drug in drugs]

        if any("口服" in form for form in forms):
            instructions.append("口服藥物請飯後服用，以減少腸胃不適")

        if any("外用" in form for form in forms):
            instructions.append("外用藥物請清潔患處後使用，避免接觸眼睛")

        if any("注射" in form for form in forms):
            instructions.append("注射藥物需由專業醫護人員執行")

        return instructions
