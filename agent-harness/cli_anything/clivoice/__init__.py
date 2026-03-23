"""CliVoice — 醫療語音轉 SOAP 病歷系統的 CLI 介面

整合三個醫療子系統：
1. ICD10v2 — 疾病診斷代碼系統
2. medicalordertreeview — 醫療服務支付標準系統
3. ATCcodeTW — 台灣 ATC 藥物分類系統
"""

__version__ = "1.0.0"
__author__ = "CliVoice Team"

from .cli.main import cli
from .core.integration_orchestrator import IntegrationOrchestrator
from .models.soap_note import SOAPNote

__all__ = ["cli", "IntegrationOrchestrator", "SOAPNote"]
