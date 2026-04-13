"""
資源路徑偵測工具

提供凍結環境（PyInstaller 打包）與開發環境下一致的資源路徑存取。
"""

import sys
import os
from pathlib import Path
from typing import Union


def get_resource_path(relative_path: str) -> Path:
    """取得打包資源的絕對路徑

    檢查 `sys.frozen` 與 `sys._MEIPASS`，回傳資源絕對路徑。若為開發環境，則基於專案根目錄計算。

    Args:
        relative_path: 相對於資源根目錄的路徑（例如 "models/qwen2.5-3b-instruct-q4_k_m.gguf"）

    Returns:
        Path: 資源的絕對路徑
    """
    if getattr(sys, "frozen", False):
        # 如果是打包後的執行檔
        base_path = getattr(sys, "_MEIPASS", Path(sys.executable).parent)
    else:
        # 開發環境：基於專案根目錄（此檔案位於 src/utils/，根目錄為上兩層）
        base_path = Path(__file__).parent.parent.parent

    return Path(base_path) / relative_path


def get_user_data_dir() -> Path:
    """取得使用者可寫入的資料目錄

    Windows 為 `%APPDATA%\\SoapVoice`，Linux/macOS 為 `~/.soapvoice`。
    目錄會自動建立。

    Returns:
        Path: 使用者資料目錄
    """
    app_name = "SoapVoice"
    if os.name == "nt":
        base = Path(os.getenv("APPDATA", "")) / app_name
    else:
        base = Path.home() / f".{app_name.lower()}"

    base.mkdir(parents=True, exist_ok=True)
    return base


# 環境變數優先覆寫的輔助函式
def get_model_path(env_var: str, default_relative: str) -> Path:
    """取得模型路徑，優先使用環境變數

    Args:
        env_var: 環境變數名稱（例如 "LLAMA_MODEL_PATH"）
        default_relative: 預設相對路徑（例如 "models/qwen2.5-3b-instruct-q4_k_m.gguf"）

    Returns:
        Path: 模型檔案的絕對路徑
    """
    env_path = os.getenv(env_var)
    if env_path:
        return Path(env_path)
    return get_resource_path(default_relative)
