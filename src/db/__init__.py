"""
本地資料庫模組

提供本地 SQLite 資料庫的查詢介面
"""

from .initialize_database import LocalDatabaseInitializer, DataSourceConfig
from .local_database import LocalDatabase, ICD10Result, DrugResult, MedicalOrderResult
from .atc_classification import (
    ATC_CLASSIFICATIONS,
    SYMPTOM_TO_ATC,
    get_atc_info,
    get_atc_by_symptom,
    get_all_categories,
    ATCCategory,
)

__all__ = [
    # 初始化
    "LocalDatabaseInitializer",
    "DataSourceConfig",
    # 查詢介面
    "LocalDatabase",
    "ICD10Result",
    "DrugResult",
    "MedicalOrderResult",
    # ATC 分類
    "ATC_CLASSIFICATIONS",
    "SYMPTOM_TO_ATC",
    "get_atc_info",
    "get_atc_by_symptom",
    "get_all_categories",
    "ATCCategory",
]
