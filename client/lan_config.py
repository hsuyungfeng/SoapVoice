"""LAN 客戶端設定模組

提供 `LANConfig` dataclass，集中管理客戶端所有可調參數：
- 伺服器位址（可從環境變數 SOAPVOICE_SERVER_URL 覆蓋）
- 連線/讀取/重試/退避參數
- 健康檢查輪詢頻率（預設每 3 秒）
- 本機暫存目錄（Windows: ~/AppData/Local/SoapVoice/cache）
- 版本檢查（min_api_version + required_services）

使用：
    >>> from client.lan_config import LANConfig
    >>> cfg = LANConfig(server_url="http://192.168.1.50:8010")
    >>> cfg.health_check_interval_sec
    3
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


def _default_cache_dir() -> str:
    """跨平台預設快取目錄。

    Windows: %LOCALAPPDATA%/SoapVoice/cache
    其他: ~/.cache/SoapVoice
    """
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        return os.path.join(localappdata, "SoapVoice", "cache")
    # 回退（Linux/macOS 開發環境）
    return os.path.join(os.path.expanduser("~"), ".cache", "SoapVoice")


@dataclass
class LANConfig:
    """LAN 客戶端設定。

    所有欄位皆有合理預設值，可由環境變數或 GUI 覆蓋。

    Attributes:
        server_url: 伺服器基礎 URL（預設讀取 SOAPVOICE_SERVER_URL 環境變數）
        api_version: API 版本前綴（預設 "v1"）
        connection_timeout_sec: 連線（建立握手）逾時秒數
        read_timeout_sec: 讀取回應逾時秒數
        max_retries: 最大重試次數
        retry_backoff_base: 指數退避基數（秒）
        health_check_interval_sec: 健康檢查輪詢頻率（秒）
        local_cache_dir: 本機暫存目錄（音檔/截圖/失敗重試 JSON）
        max_pending_uploads: 本機暫存上限
        min_api_version: 客戶端要求的最低伺服器版本（SemVer）
        required_services: 必要可用的伺服器服務（asr/llm/database）
    """

    server_url: str = field(
        default_factory=lambda: os.getenv("SOAPVOICE_SERVER_URL", "http://192.168.1.100:8010")
    )
    api_version: str = "v1"

    # 連線參數
    connection_timeout_sec: float = 5.0
    read_timeout_sec: float = 30.0
    max_retries: int = 3
    retry_backoff_base: float = 2.0
    health_check_interval_sec: int = 3

    # 本機暫存
    local_cache_dir: str = field(default_factory=_default_cache_dir)
    max_pending_uploads: int = 10

    # 版本檢查
    min_api_version: str = "1.1.0"
    required_services: List[str] = field(
        default_factory=lambda: ["asr", "llm", "database"]
    )

    @property
    def health_endpoint(self) -> str:
        """健康檢查端點（不含 base URL）。"""
        return f"api/{self.api_version}/health"

    @property
    def lan_process_endpoint(self) -> str:
        """問診上傳端點。"""
        return f"api/{self.api_version}/lan/process"

    @classmethod
    def from_env(cls) -> "LANConfig":
        """從環境變數構建設定（便於 CLI / 測試）。"""
        return cls()
