"""
適配器模組

提供與外部系統的介面適配器
"""

from .icd10_adapter import ICD10Adapter
from .medical_order_adapter import MedicalOrderAdapter
from .atc_drug_adapter import ATCDrugAdapter
from .notebooklm_adapter import NotebookLMAdapter

__all__ = [
    "ICD10Adapter",
    "MedicalOrderAdapter",
    "ATCDrugAdapter",
    "NotebookLMAdapter",
]
