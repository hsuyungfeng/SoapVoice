"""
LLM 效能基準測試

測試不同 LLM 模型的效能，記錄結果到 tests/fixtures/results/

執行方式:
    uv run pytest tests/test_llm_benchmark.py -v
    uv run pytest tests/test_llm_benchmark.py::TestLLMBenchmark::test_llm_qwen2_5_3b -v
"""

import pytest
import time
import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class TestLLMBenchmark:
    """LLM 模型效能測試"""

    @pytest.fixture
    def system_info(self) -> Dict[str, Any]:
        import psutil

        info = {
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        }
        try:
            import subprocess

            gpu = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                capture_output=True,
                text=True,
            )
            if gpu.returncode == 0:
                info["gpu"] = gpu.stdout.strip().split("\n")[0]
        except Exception:
            pass
        return info

    @pytest.fixture
    def test_prompts(self) -> List[str]:
        return [
            "病人咳嗽兩天，有痰，喉嚨痛。",
            "病人胸悶兩天，有高血壓病史。",
            "醫師：你好，請問今天有什麼不舒服？病人：我頭痛發燒三天了。",
        ]

    @pytest.fixture
    def results_file(self) -> Path:
        return Path("tests/fixtures/results/llm_benchmark_latest.json")

    def _save_results(self, results_file: Path, system_info: Dict, results: List[Dict]):
        results_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "system_info": system_info,
            "results": results,
        }
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @pytest.mark.asyncio
    async def test_llm_qwen2_5_3b(self, system_info, test_prompts, results_file):
        """測試 qwen2.5:3b 模型效能"""
        import httpx

        model = "qwen2.5:3b"
        times = []
        errors = []

        for prompt in test_prompts:
            try:
                start = time.time()
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(
                        "http://localhost:11434/api/generate",
                        json={"model": model, "prompt": prompt, "stream": False},
                    )
                elapsed = time.time() - start

                if resp.status_code == 200:
                    times.append(elapsed)
                else:
                    errors.append(f"HTTP {resp.status_code}")
            except Exception as e:
                errors.append(str(e))

        if errors:
            logger.warning(f"qwen2.5:3b 有錯誤: {errors}")
            pytest.skip(f"qwen2.5:3b 測試失敗: {errors}")

        result = {
            "model": model,
            "runs": len(test_prompts),
            "avg_time_sec": round(sum(times) / len(times), 3),
            "min_time_sec": round(min(times), 3),
            "max_time_sec": round(max(times), 3),
            "times": [round(t, 3) for t in times],
        }

        self._save_results(results_file, system_info, [result])
        logger.info(f"qwen2.5:3b: {result['avg_time_sec']}s")
        assert result["avg_time_sec"] < 20

    @pytest.mark.asyncio
    async def test_llm_qwen2_5_7b(self, system_info, test_prompts, results_file):
        """測試 qwen2.5:7b 模型效能"""
        import httpx

        model = "qwen2.5:7b"
        times = []
        errors = []

        for prompt in test_prompts:
            try:
                start = time.time()
                async with httpx.AsyncClient(timeout=180.0) as client:
                    resp = await client.post(
                        "http://localhost:11434/api/generate",
                        json={"model": model, "prompt": prompt, "stream": False},
                    )
                elapsed = time.time() - start

                if resp.status_code == 200:
                    times.append(elapsed)
                else:
                    errors.append(f"HTTP {resp.status_code}")
            except Exception as e:
                errors.append(str(e))

        if errors:
            logger.warning(f"qwen2.5:7b 有錯誤: {errors}")
            pytest.skip(f"qwen2.5:7b 測試失敗: {errors}")

        result = {
            "model": model,
            "runs": len(test_prompts),
            "avg_time_sec": round(sum(times) / len(times), 3),
            "min_time_sec": round(min(times), 3),
            "max_time_sec": round(max(times), 3),
        }

        if results_file.exists():
            with open(results_file) as f:
                data = json.load(f)
                data["results"].append(result)
        else:
            data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "system_info": system_info,
                "results": [result],
            }

        with open(results_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"qwen2.5:7b: {result['avg_time_sec']}s")
        assert result["avg_time_sec"] < 30

    @pytest.mark.asyncio
    async def test_llm_qwen2_5_14b(self, system_info, test_prompts, results_file):
        """測試 qwen2.5:14b 模型效能"""
        import httpx

        model = "qwen2.5:14b"
        times = []
        errors = []

        for prompt in test_prompts:
            try:
                start = time.time()
                async with httpx.AsyncClient(timeout=300.0) as client:
                    resp = await client.post(
                        "http://localhost:11434/api/generate",
                        json={"model": model, "prompt": prompt, "stream": False},
                    )
                elapsed = time.time() - start

                if resp.status_code == 200:
                    times.append(elapsed)
                else:
                    errors.append(f"HTTP {resp.status_code}")
            except Exception as e:
                errors.append(str(e))

        if errors:
            logger.warning(f"qwen2.5:14b 有錯誤: {errors}")
            pytest.skip(f"qwen2.5:14b 測試失敗: {errors}")

        result = {
            "model": model,
            "runs": len(test_prompts),
            "avg_time_sec": round(sum(times) / len(times), 3),
            "min_time_sec": round(min(times), 3),
            "max_time_sec": round(max(times), 3),
        }

        if results_file.exists():
            with open(results_file) as f:
                data = json.load(f)
                data["results"].append(result)
        else:
            data = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "system_info": system_info,
                "results": [result],
            }

        with open(results_file, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"qwen2.5:14b: {result['avg_time_sec']}s")
        assert result["avg_time_sec"] < 60

    @pytest.mark.asyncio
    async def test_llm_qwen3_5_9b(self, system_info, test_prompts, results_file):
        """測試 qwen3.5:9b 模型效能 - 跳過（CUDA 兼容性問題）"""
        # qwen3.5:9b 在 RTX 2080 Ti 雙卡環境有 CUDA illegal instruction 問題
        # 錯誤: CUDA error: an illegal instruction was encountered
        # 可能原因: Qwen3.5 需要較新的 CUDA 架構
        pytest.skip("qwen3.5:9b 有 CUDA 兼容性問題，需要較新的 GPU 或更新驅動")
