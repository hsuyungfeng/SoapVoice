"""
SOAP 模組

醫療 SOAP 病歷生成與分類
"""

from src.soap.soap_generator import (
    SOAPGenerator,
    SOAPConfig,
    get_generator,
    initialize_generator,
    SOAP_KEYWORDS,
)

__all__ = [
    "SOAPGenerator",
    "SOAPConfig",
    "get_generator",
    "initialize_generator",
    "SOAP_KEYWORDS",
]
