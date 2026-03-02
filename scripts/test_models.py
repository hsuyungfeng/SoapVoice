#!/usr/bin/env python3
"""
模型下載與驗證腳本

用於下載和驗證所需的 AI 模型：
- Faster-Whisper large-v3
- Qwen3-32B-Instruct (通過 vLLM)
"""

import os
import sys
import logging
from pathlib import Path

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_huggingface_token() -> bool:
    """檢查 HuggingFace Token 是否設置"""
    token = os.getenv("HF_TOKEN")
    if not token:
        logger.warning("HF_TOKEN 環境變數未設置")
        logger.info("請到 https://huggingface.co/settings/tokens 取得 token")
        logger.info("然後執行：export HF_TOKEN=your_token")
        return False
    logger.info("HF_TOKEN 已設置")
    return True


def check_gpu() -> bool:
    """檢查 GPU 是否可用"""
    try:
        import torch
        if not torch.cuda.is_available():
            logger.warning("CUDA 不可用，請檢查 NVIDIA 驅動和 CUDA 安裝")
            return False
        
        gpu_count = torch.cuda.device_count()
        logger.info(f"檢測到 {gpu_count} 個 GPU")
        
        for i in range(gpu_count):
            gpu_name = torch.cuda.get_device_name(i)
            gpu_memory = torch.cuda.get_device_properties(i).total_memory / 1024**3
            logger.info(f"GPU {i}: {gpu_name} ({gpu_memory:.1f} GB)")
        
        return True
    except ImportError:
        logger.warning("PyTorch 未安裝")
        return False


def check_disk_space(required_gb: int = 100) -> bool:
    """檢查磁碟空間"""
    # 模型快取目錄
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # 取得可用空間
    stat = os.statvfs(cache_dir)
    available_gb = (stat.f_bavail * stat.f_frsize) / 1024**3
    
    logger.info(f"可用磁碟空間：{available_gb:.1f} GB")
    logger.info(f"建議最小空間：{required_gb} GB")
    
    if available_gb < required_gb:
        logger.warning("磁碟空間不足，建議清理或擴充")
        return False
    
    return True


def test_whisper_model(model_id: str = "large-v3") -> bool:
    """測試 Faster-Whisper 模型"""
    logger.info(f"測試 Faster-Whisper 模型：{model_id}")
    
    try:
        from faster_whisper import WhisperModel
        
        # 使用 int8 量化版本減少記憶體使用
        logger.info("下載/載入模型（首次執行會下載）...")
        model = WhisperModel(
            model_id,
            device="cpu",  # 先用 CPU 測試
            compute_type="int8",
        )
        
        logger.info("✓ Faster-Whisper 模型載入成功")
        return True
        
    except Exception as e:
        logger.error(f"✗ Faster-Whisper 模型測試失敗：{e}")
        return False


def test_vllm_model(model_id: str = "Qwen/Qwen3-32B-Instruct") -> bool:
    """測試 vLLM 模型"""
    logger.info(f"測試 vLLM 模型：{model_id}")
    
    try:
        from vllm import LLM, SamplingParams
        
        logger.info("注意：vLLM 模型需要大量 VRAM（約 40GB）")
        logger.info("此測試僅驗證模組可匯入，實際載入請使用 docker compose")
        
        # 僅測試模組可匯入
        logger.info("✓ vLLM 模組匯入成功")
        return True
        
    except Exception as e:
        logger.error(f"✗ vLLM 模組測試失敗：{e}")
        return False


def test_download_models() -> bool:
    """測試下載所有模型"""
    logger.info("========================================")
    logger.info("模型下載與驗證")
    logger.info("========================================")
    
    results = []
    
    # 檢查前置條件
    logger.info("\n[前置檢查]")
    results.append(("HuggingFace Token", check_huggingface_token()))
    results.append(("GPU 可用性", check_gpu()))
    results.append(("磁碟空間", check_disk_space(100)))
    
    # 測試模型
    logger.info("\n[模型測試]")
    results.append(("Faster-Whisper", test_whisper_model()))
    results.append(("vLLM", test_vllm_model()))
    
    # 總結
    logger.info("\n========================================")
    logger.info("測試摘要")
    logger.info("========================================")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✓" if result else "✗"
        logger.info(f"{status} {name}")
    
    logger.info(f"\n通過：{passed}/{total}")
    
    if passed == total:
        logger.info("所有模型測試通過！")
        return True
    else:
        logger.warning("部分測試失敗，請檢查上述錯誤")
        return False


def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="模型下載與驗證腳本")
    parser.add_argument(
        "--skip-gpu",
        action="store_true",
        help="跳過 GPU 檢查（使用 CPU 測試）",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="跳過下載（僅檢查配置）",
    )
    
    args = parser.parse_args()
    
    if args.skip_download:
        logger.info("跳過下載，僅檢查配置")
        check_huggingface_token()
        check_gpu()
        check_disk_space(100)
        return 0
    
    success = test_download_models()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
