#!/usr/bin/env python3
"""
效能基準測試 - CPU vs GPU 完整比較

使用 Ollama API 測量 qwen2.5:7b 模型在不同配置下的效能：
1. GPU 模式 - RTX 2080 Ti
2. CPU 模式 - 強制使用 CPU
"""

import time
import psutil
import json
import logging
import statistics
import os
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_system_info() -> Dict[str, Any]:
    """取得系統資訊"""
    info = {
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
    }

    # GPU 資訊
    try:
        import subprocess

        gpu_info = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.free,utilization.gpu",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
        )
        if gpu_info.returncode == 0:
            gpus = []
            for line in gpu_info.stdout.strip().split("\n"):
                parts = line.split(", ")
                if len(parts) >= 4:
                    gpus.append(
                        {
                            "name": parts[0],
                            "memory_total_mb": int(parts[1].replace(" MiB", "")),
                            "memory_free_mb": int(parts[2].replace(" MiB", "")),
                            "utilization": parts[3].replace(" %", ""),
                        }
                    )
            info["gpus"] = gpus
    except Exception:
        pass

    return info


def test_ollama_inference(
    model: str,
    prompt: str,
    max_tokens: int = 256,
) -> Dict[str, Any]:
    """測試 Ollama 推斷效能"""
    import httpx

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.3,
        },
    }

    start_time = time.time()
    response = httpx.post(url, json=payload, timeout=180.0)
    end_time = time.time()

    if response.status_code != 200:
        raise Exception(f"Ollama API error: {response.text}")

    result = response.json()
    inference_time = end_time - start_time
    tokens = len(result.get("response", "").split())
    tokens_per_second = tokens / inference_time if inference_time > 0 else 0

    return {
        "inference_time_sec": round(inference_time, 3),
        "tokens": tokens,
        "tokens_per_second": round(tokens_per_second, 2),
        "response": result.get("response", "")[:100],
    }


def run_benchmark(
    name: str,
    model: str,
    test_prompts: List[str],
    runs: int = 3,
) -> Dict[str, Any]:
    """執行基準測試"""
    logger.info(f"\n{'=' * 60}")
    logger.info(f"測試: {name}")
    logger.info(f"  模型: {model}")
    logger.info(f"{'=' * 60}")

    all_times = []
    all_tokens_per_sec = []

    for run in range(runs):
        logger.info(f"  Run {run + 1}/{runs}...")

        for prompt in test_prompts:
            try:
                result = test_ollama_inference(model, prompt, max_tokens=256)
                all_times.append(result["inference_time_sec"])
                all_tokens_per_sec.append(result["tokens_per_second"])
            except Exception as e:
                logger.warning(f"    Error: {e}")

    avg_time = statistics.mean(all_times) if all_times else 0
    avg_tokens = statistics.mean(all_tokens_per_sec) if all_tokens_per_sec else 0

    return {
        "name": name,
        "model": model,
        "runs": runs,
        "prompts_count": len(test_prompts) * runs,
        "avg_inference_time_sec": round(avg_time, 3),
        "avg_tokens_per_second": round(avg_tokens, 2),
        "min_time_sec": round(min(all_times), 3) if all_times else 0,
        "max_time_sec": round(max(all_times), 3) if all_times else 0,
    }


def main():
    system_info = get_system_info()
    logger.info(f"\n系統資訊:")
    logger.info(f"  CPU: {system_info['cpu_cores']} 核心, {system_info['cpu_threads']} 執行緒")
    logger.info(f"  記憶體: {system_info['memory_total_gb']} GB")

    if "gpus" in system_info:
        for i, gpu in enumerate(system_info["gpus"]):
            logger.info(
                f"  GPU {i + 1}: {gpu['name']} ({gpu['memory_total_mb']} MiB, {gpu['utilization']}% 利用率)"
            )

    # 測試 prompt
    test_prompts = [
        "請將以下醫療對話轉換為 SOAP 病歷：病人咳嗽兩天，有痰，喉嚨痛。",
        "病人胸悶兩天，有高血壓病史。",
        "醫師：你好，請問今天有什麼不舒服？病人：我頭痛發燒三天了。",
    ]

    results = []

    # 測試 1: qwen2.5:7b (GPU)
    result = run_benchmark(
        name="GPU (qwen2.5:7b)",
        model="qwen2.5:7b",
        test_prompts=test_prompts,
        runs=3,
    )
    results.append(result)
    logger.info(f"  平均推理時間: {result['avg_inference_time_sec']:.3f}s")
    logger.info(f"  平均吞吐量: {result['avg_tokens_per_second']:.2f} tokens/s")

    # 測試 2: qwen2.5:3b (更快的小模型)
    result = run_benchmark(
        name="GPU (qwen2.5:3b)",
        model="qwen2.5:3b",
        test_prompts=test_prompts,
        runs=3,
    )
    results.append(result)
    logger.info(f"  平均推理時間: {result['avg_inference_time_sec']:.3f}s")
    logger.info(f"  平均吞吐量: {result['avg_tokens_per_second']:.2f} tokens/s")

    # 測試 3: qwen2.5:14b (較大模型)
    result = run_benchmark(
        name="GPU (qwen2.5:14b)",
        model="qwen2.5:14b",
        test_prompts=test_prompts,
        runs=3,
    )
    results.append(result)
    logger.info(f"  平均推理時間: {result['avg_inference_time_sec']:.3f}s")
    logger.info(f"  平均吞吐量: {result['avg_tokens_per_second']:.2f} tokens/s")

    # 儲存結果
    benchmark_data = {
        "system_info": system_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }

    with open("benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    # 列印摘要
    logger.info(f"\n{'=' * 60}")
    logger.info(f"效能測試摘要")
    logger.info(f"{'=' * 60}")

    for r in results:
        speedup = (
            results[0]["avg_inference_time_sec"] / r["avg_inference_time_sec"]
            if r["avg_inference_time_sec"] > 0
            else 0
        )
        logger.info(f"\n{r['name']}:")
        logger.info(
            f"  推理時間: {r['avg_inference_time_sec']:.3f}s (範圍: {r['min_time_sec']:.3f}s - {r['max_time_sec']:.3f}s)"
        )
        logger.info(f"  吞吐量: {r['avg_tokens_per_second']:.2f} tokens/s")
        logger.info(f"  相比 7b 加速: {speedup:.2f}x")

    logger.info(f"\n結果已儲存到: benchmark_results.json")


if __name__ == "__main__":
    main()
