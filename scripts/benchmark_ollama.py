#!/usr/bin/env python3
"""
效能基準測試 - 多模型比較 (Qwen2.5 vs Qwen3.5)

測試不同 Qwen 模型的效能，寫入測試結果
"""

import time
import psutil
import json
import logging
import statistics
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_system_info() -> Dict[str, Any]:
    info = {
        "cpu_cores": psutil.cpu_count(logical=False),
        "cpu_threads": psutil.cpu_count(logical=True),
        "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
    }
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
                        }
                    )
            info["gpus"] = gpus
    except Exception:
        pass
    return info


def get_available_models() -> List[str]:
    import httpx

    try:
        response = httpx.get("http://localhost:11434/api/tags", timeout=10)
        data = response.json()
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def test_ollama_inference(model: str, prompt: str, max_tokens: int = 256) -> Dict[str, Any]:
    import httpx

    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.3},
    }
    start_time = time.time()
    response = httpx.post(url, json=payload, timeout=180.0)
    end_time = time.time()
    result = response.json()
    inference_time = end_time - start_time
    tokens = len(result.get("response", "").split())
    return {
        "inference_time_sec": round(inference_time, 3),
        "tokens": tokens,
        "tokens_per_second": round(tokens / inference_time, 2) if inference_time > 0 else 0,
    }


def run_benchmark(name: str, model: str, test_prompts: List[str], runs: int = 3) -> Dict[str, Any]:
    logger.info(f"\n{'=' * 50}")
    logger.info(f"測試: {name}")
    logger.info(f"{'=' * 50}")

    all_times = []
    all_tokens_per_sec = []

    for run in range(runs):
        logger.info(f"  Run {run + 1}/{runs}...")
        for prompt in test_prompts:
            try:
                result = test_ollama_inference(model, prompt)
                all_times.append(result["inference_time_sec"])
                all_tokens_per_sec.append(result["tokens_per_second"])
            except Exception as e:
                logger.warning(f"    Error: {e}")

    return {
        "name": name,
        "model": model,
        "runs": runs,
        "avg_inference_time_sec": round(statistics.mean(all_times), 3) if all_times else 0,
        "avg_tokens_per_second": round(statistics.mean(all_tokens_per_sec), 2)
        if all_tokens_per_sec
        else 0,
    }


def main():
    system_info = get_system_info()
    logger.info(f"\n系統: CPU {system_info['cpu_cores']} 核心, {system_info['memory_total_gb']} GB")
    if "gpus" in system_info:
        for gpu in system_info["gpus"]:
            logger.info(f"  GPU: {gpu['name']} ({gpu['memory_total_mb']} MiB)")

    available = get_available_models()
    logger.info(f"\n可用模型: {available}")

    test_models = [
        ("Qwen2.5:3b", "qwen2.5:3b"),
        ("Qwen2.5:7b", "qwen2.5:7b"),
        ("Qwen2.5:14b", "qwen2.5:14b"),
        ("Qwen3.5:9b", "qwen3.5:9b"),
    ]
    test_models = [(n, m) for n, m in test_models if m in available]

    test_prompts = [
        "請將以下醫療對話轉換為 SOAP 病歷：病人咳嗽兩天，有痰，喉嚨痛。",
        "病人胸悶兩天，有高血壓病史。",
    ]

    results = []
    for name, model in test_models:
        try:
            result = run_benchmark(name, model, test_prompts, runs=3)
            results.append(result)
            logger.info(
                f"  推理時間: {result['avg_inference_time_sec']:.3f}s, 吞吐量: {result['avg_tokens_per_second']:.2f} tokens/s"
            )
        except Exception as e:
            logger.warning(f"測試失敗: {e}")

    benchmark_data = {
        "system_info": system_info,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "available_models": available,
        "results": results,
    }

    with open("tests/fixtures/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=2, ensure_ascii=False)

    logger.info(f"\n{'=' * 50}")
    logger.info("效能測試摘要")
    logger.info(f"{'=' * 50}")
    for r in results:
        logger.info(
            f"{r['name']}: {r['avg_inference_time_sec']:.3f}s, {r['avg_tokens_per_second']:.2f} tokens/s"
        )
    logger.info(f"\n結果已儲存到: tests/fixtures/benchmark_results.json")


if __name__ == "__main__":
    main()
