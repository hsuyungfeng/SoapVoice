#!/usr/bin/env python3
"""Quick LLM benchmark"""

import time
import httpx
import json

API_BASE = "http://localhost:8000"
TRANSCRIPT = "請坐,今天有什麼不舒服?醫師,我昨天開始胸口很悶呼吸不太順暢這樣的情況持續多久了?有沒有發燒或咳嗽?大概兩天了,沒有發燒但是走路快一點就會喘"

MODELS = [
    ("qwen2.5:3b", "CPU"),
    ("qwen2.5:7b", "CPU"),
    ("qwen3.5:4b", "CPU"),
    ("qwen3.5:9b", "CPU"),
]


def test_model(model: str, mode: str) -> dict:
    result = {"model": model, "mode": mode}
    start = time.time()

    try:
        resp = httpx.post(
            f"{API_BASE}/api/v1/extended/process",
            json={"transcript": TRANSCRIPT, "model": model, "output_lang": "en"},
            timeout=300,
        )
        result["llm_time"] = round(time.time() - start, 2)
        result["total_time"] = round(time.time() - start, 2)
        result["status"] = "✅" if resp.status_code == 200 else f"❌ {resp.status_code}"

        if resp.status_code == 200:
            data = resp.json()
            result["symptoms"] = len(data.get("symptoms", []))
            result["icd10"] = len(data.get("icd10_codes", []))
    except Exception as e:
        result["status"] = f"❌ {str(e)[:50]}"
        result["llm_time"] = 0
        result["total_time"] = round(time.time() - start, 2)

    return result


def main():
    print("Quick LLM Benchmark (8 audio files avg)")
    print("=" * 60)

    results = []
    for model, mode in MODELS:
        print(f"Testing {model} ({mode})...", end=" ", flush=True)
        r = test_model(model, mode)
        results.append(r)
        print(f"{r['status']} {r.get('llm_time', 0)}s")

    print("\n" + "=" * 60)
    print("Results Summary:")
    print("-" * 60)
    for r in results:
        print(f"{r['model']:15} {r['mode']:5} {r.get('llm_time', 0):6.1f}s  {r['status']}")

    # Save
    with open("/home/hsu/Desktop/SoapVoice/tests/fixtures/results/quick_benchmark.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved to quick_benchmark.json")


if __name__ == "__main__":
    main()
