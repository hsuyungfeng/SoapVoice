#!/usr/bin/env python3
"""
Llama.cpp 效能基準測試 - CPU vs GPU 比較

測試不同配置下的推理效能：
1. CPU only (n_gpu_layers=0)
2. GPU (n_gpu_layers=全部)
"""

import time
import psutil
import logging
from pathlib import Path
from typing import Dict, Any, List
import json

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class LlamaBenchmark:
    """Llama.cpp 效能基準測試"""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self.results: List[Dict[str, Any]] = []

    def get_system_info(self) -> Dict[str, Any]:
        """取得系統資訊"""
        return {
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "cpu_freq": psutil.cpu_freq().current if psutil.cpu_freq() else None,
            "memory_total_gb": psutil.virtual_memory().total / (1024**3),
            "memory_available_gb": psutil.virtual_memory().available / (1024**3),
        }

    def run_benchmark(
        self,
        name: str,
        n_gpu_layers: int,
        n_threads: int = 8,
        test_prompts: List[str] = None,
    ) -> Dict[str, Any]:
        """執行基準測試"""
        from llama_cpp import Llama

        if test_prompts is None:
            test_prompts = [
                "請將以下醫療對話轉換為 SOAP 病歷：病人咳嗽兩天，有痰，喉嚨痛。",
                "病人胸悶兩天，有高血壓病史。",
                "醫師：你好，請問今天有什麼不舒服？病人：我頭痛發燒三天了。",
            ]

        logger.info(f"\n{'=' * 60}")
        logger.info(f"測試: {name}")
        logger.info(f"  n_gpu_layers: {n_gpu_layers}")
        logger.info(f"  n_threads: {n_threads}")
        logger.info(f"{'=' * 60}")

        # 記錄初始記憶體
        process = psutil.Process()
        mem_before = process.memory_info().rss / (1024**2)  # MB

        # 載入模型
        start_load = time.time()
        model = Llama(
            model_path=self.model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=2048,
            n_threads=n_threads,
            n_threads_batch=n_threads,
            verbose=False,
        )
        load_time = time.time() - start_load

        mem_after_load = process.memory_info().rss / (1024**2)

        # 執行推理測試
        inference_times = []
        tokens_per_second = []

        for i, prompt in enumerate(test_prompts):
            logger.info(f"  測試 {i + 1}/{len(test_prompts)}...")

            start_time = time.time()
            output = model(prompt, max_tokens=256, temperature=0.3, top_p=0.9)
            end_time = time.time()

            inference_time = end_time - start_time
            tokens = len(output["choices"][0]["text"].split())

            inference_times.append(inference_time)
            tokens_per_second.append(tokens / inference_time if inference_time > 0 else 0)

        # 計算平均
        avg_inference_time = sum(inference_times) / len(inference_times)
        avg_tokens_per_sec = sum(tokens_per_second) / len(tokens_per_second)

        result = {
            "name": name,
            "n_gpu_layers": n_gpu_layers,
            "n_threads": n_threads,
            "load_time_sec": round(load_time, 2),
            "memory_used_mb": round(mem_after_load - mem_before, 2),
            "avg_inference_time_sec": round(avg_inference_time, 3),
            "avg_tokens_per_second": round(avg_tokens_per_sec, 2),
            "test_prompts": len(test_prompts),
        }

        logger.info(f"  模型載入時間: {load_time:.2f}s")
        logger.info(f"  記憶體使用: {mem_after_load - mem_before:.2f} MB")
        logger.info(f"  平均推理時間: {avg_inference_time:.3f}s")
        logger.info(f"  平均 tokens/s: {avg_tokens_per_sec:.2f}")

        self.results.append(result)
        return result

    def save_results(self, filepath: str = "benchmark_results.json"):
        """儲存結果"""
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "system_info": self.get_system_info(),
                    "model_path": self.model_path,
                    "results": self.results,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        logger.info(f"\n結果已儲存到: {filepath}")

    def print_summary(self):
        """列印摘要"""
        logger.info("\n" + "=" * 60)
        logger.info("效能測試摘要")
        logger.info("=" * 60)

        for r in self.results:
            logger.info(f"\n{r['name']}:")
            logger.info(f"  推理時間: {r['avg_inference_time_sec']:.3f}s")
            logger.info(f"  吞吐量: {r['avg_tokens_per_second']:.2f} tokens/s")
            logger.info(f"  記憶體: {r['memory_used_mb']:.2f} MB")
            logger.info(f"  載入時間: {r['load_time_sec']:.2f}s")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Llama.cpp 效能基準測試")
    parser.add_argument(
        "--model",
        default="models/qwen2.5-7b-instruct-q4_k_m.gguf",
        help="模型路徑",
    )
    parser.add_argument(
        "--output",
        default="benchmark_results.json",
        help="輸出檔案",
    )
    args = parser.parse_args()

    # 檢查模型檔案
    model_path = Path(args.model)
    if not model_path.exists():
        logger.error(f"模型檔案不存在: {model_path}")
        return

    benchmark = LlamaBenchmark(str(model_path))

    # 系統資訊
    sys_info = benchmark.get_system_info()
    logger.info(f"\n系統資訊:")
    logger.info(f"  CPU: {sys_info['cpu_cores']} 核心, {sys_info['cpu_threads']} 執行緒")
    logger.info(f"  記憶體: {sys_info['memory_total_gb']:.1f} GB")

    # 測試 1: CPU only
    benchmark.run_benchmark(
        name="CPU Only (n_gpu_layers=0)",
        n_gpu_layers=0,
        n_threads=8,
    )

    # 測試 2: GPU (使用全部層)
    benchmark.run_benchmark(
        name="GPU (n_gpu_layers=35)",
        n_gpu_layers=35,
        n_threads=4,
    )

    # 測試 3: GPU + 更多執行緒
    benchmark.run_benchmark(
        name="GPU + High Threads (n_gpu_layers=35, n_threads=8)",
        n_gpu_layers=35,
        n_threads=8,
    )

    # 儲存與列印結果
    benchmark.save_results(args.output)
    benchmark.print_summary()


if __name__ == "__main__":
    main()
