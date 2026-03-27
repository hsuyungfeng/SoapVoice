#!/usr/bin/env python3
"""
SoapVoice 離線一鍵啟動模組

包含：
- FastAPI 伺服器
- llama.cpp 推理引擎
- 內建 Qwen2.5:7b GGUF 模型
- 內建 faster-whisper-small 模型
- SQLite 資料庫 (medical.db)

無需網路，直接啟動！
"""

import os
import sys
import logging
from pathlib import Path

# 添加專案根目錄
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_dependencies() -> bool:
    """檢查必要依賴"""
    required = ["llama_cpp", "fastapi", "uvicorn", "faster_whisper"]
    missing = []

    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        logger.error(f"缺少依賴: {', '.join(missing)}")
        logger.info("執行: uv sync")
        return False

    return True


def check_llm_model() -> bool:
    """檢查 LLM 模型"""
    model_paths = [
        PROJECT_ROOT / "models" / "qwen2.5-7b-instruct-q4_k_m.gguf",
    ]

    for path in model_paths:
        if path.exists():
            size_gb = path.stat().st_size / (1024**3)
            logger.info(f"找到 LLM 模型: {path.name} ({size_gb:.1f}GB)")
            return True

    logger.warning("未找到 GGUF 模型，將使用 Ollama 回退")
    return False


def check_whisper_model() -> bool:
    """檢查 Whisper 模型"""
    whisper_dir = PROJECT_ROOT / "models" / "whisper"

    if whisper_dir.exists():
        # 檢查是否有 blobs 目錄
        if (whisper_dir / "blobs").exists():
            logger.info(f"找到 Whisper 模型: {whisper_dir}")
            return True

    logger.warning("未找到本地 Whisper 模型，將嘗試下載")
    return False


def get_model_paths() -> dict:
    """取得模型路徑配置"""
    whisper_dir = PROJECT_ROOT / "models" / "whisper"
    whisper_path = str(whisper_dir) if whisper_dir.exists() else None

    return {
        "whisper_model_dir": whisper_path,
        "llm_model_path": str(PROJECT_ROOT / "models" / "qwen2.5-7b-instruct-q4_k_m.gguf"),
    }


def start_server():
    """啟動伺服器"""
    logger.info("=" * 50)
    logger.info("SoapVoice 離線伺服器")
    logger.info("=" * 50)

    # 顯示配置
    paths = get_model_paths()
    logger.info(f"Whisper 模型: {paths['whisper_model_dir'] or 'None (需下載)'}")
    logger.info(f"LLM 模型: {paths['llm_model_path']}")

    # 啟動 FastAPI
    import uvicorn

    # 設定環境變數（讓 whisper 使用本地模型）
    if paths["whisper_model_dir"]:
        os.environ["HF_HOME"] = paths["whisper_model_dir"]

    from src.main import app

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


def main():
    """主函數"""
    print("=" * 50)
    print("SoapVoice - 醫療語音轉 SOAP 病歷系統")
    print("離線完整版 (含模型 + 資料庫)")
    print("=" * 50)

    # 檢查依賴
    if not check_dependencies():
        sys.exit(1)

    # 檢查模型
    check_llm_model()
    check_whisper_model()

    # 啟動伺服器
    try:
        start_server()
    except KeyboardInterrupt:
        logger.info("使用者中斷")
    except Exception as e:
        logger.error(f"啟動失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
