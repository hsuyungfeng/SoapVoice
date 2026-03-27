#!/usr/bin/env python3
"""模型比較測試 - 執行 3 個模型並比較結果"""

import requests
import json
import time
from pathlib import Path
from datetime import datetime

RESULTS_DIR = Path("tests/fixtures/results")
API_URL = "http://localhost:8000"

FILES = [
    ("chest_pain.wav", "胸痛"),
    ("hypertension.wav", "高血壓"),
    ("diabetes.wav", "糖尿病"),
    ("wound_care.wav", "傷口護理"),
    ("respiratory.wav", "呼吸道"),
    ("drug_order.wav", "醫囑"),
    ("surgery_record.wav", "手術記錄"),
    ("doctor_patient.wav", "醫病對話"),
]

MODELS = ["qwen2.5:14b", "qwen2.5:7b", "qwen2.5:3b"]


def transcribe(audio_file):
    """轉錄音訊"""
    with open(f"static/{audio_file}", "rb") as f:
        r = requests.post(
            f"{API_URL}/api/v1/extended/transcribe",
            files={"audio": (audio_file, f, "audio/wav")},
            timeout=60,
        )
    if r.status_code == 200:
        return r.json()["transcript"]
    return None


def process(transcript, model):
    """處理轉錄結果"""
    r = requests.post(
        f"{API_URL}/api/v1/extended/process",
        json={"transcript": transcript, "model": model},
        timeout=120,
    )
    if r.status_code == 200:
        return r.json()
    return None


def main():
    print("=" * 60)
    print(" SoapVoice 模型比較測試")
    print("=" * 60)

    all_results = {}

    for model in MODELS:
        print(f"\n{'=' * 60}")
        print(f"🔄 測試模型: {model}")
        print(f"{'=' * 60}")

        results = []
        start_time = time.time()

        for filename, name in FILES:
            print(f"\n  📄 {name} ({filename})")

            # Step 1: 轉錄
            t0 = time.time()
            transcript = transcribe(filename)
            t_transcribe = time.time() - t0

            if transcript is None:
                print(f"     ❌ 轉錄失敗")
                continue

            print(f"     ✅ 轉錄: {transcript[:30]}...")
            print(f"     ⏱️ 轉譯時間: {t_transcribe:.1f}秒")

            # Step 2: LLM 處理
            t0 = time.time()
            data = process(transcript, model)
            t_llm = time.time() - t0

            if data is None:
                print(f"     ❌ LLM 處理失敗")
                continue

            result = {
                "name": name,
                "file": filename,
                "model": model,
                "transcript": transcript,
                "transcribe_time": round(t_transcribe, 2),
                "llm_time": round(t_llm, 2),
                "total_time": round(t_transcribe + t_llm, 2),
                "symptoms": data.get("symptoms", []),
                "icd10_codes": data.get("icd10_codes", []),
                "medical_orders": data.get("medical_orders", []),
                "drug_recommendations": data.get("drug_recommendations", []),
                "soap": data.get("soap", {}),
            }
            results.append(result)

            print(f"     ✅ 症狀: {result['symptoms'][:3]}")
            print(f"     ✅ ICD-10: {[c['code'] for c in result['icd10_codes']]}")
            print(f"     ⏱️ LLM 時間: {t_llm:.1f}秒")

        total_time = time.time() - start_time
        all_results[model] = {
            "results": results,
            "total_time": round(total_time, 2),
            "avg_transcribe": sum(r["transcribe_time"] for r in results) / len(results),
            "avg_llm": sum(r["llm_time"] for r in results) / len(results),
        }

        print(f"\n  📊 {model} 測試完成:")
        print(f"     - 總時間: {total_time:.1f}秒")
        print(f"     - 平均轉譯: {all_results[model]['avg_transcribe']:.1f}秒")
        print(f"     - 平均 LLM: {all_results[model]['avg_llm']:.1f}秒")

    # 儲存結果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RESULTS_DIR / f"compare_{timestamp}.json"
    output_file.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{'=' * 60}")
    print(f"💾 已儲存至: {output_file}")
    print(f"{'=' * 60}")

    # 比較摘要
    print("\n📊 比較摘要")
    print("-" * 60)
    print(f"{'模型':<15} {'總時間':<10} {'平均轉譯':<10} {'平均 LLM':<10}")
    print("-" * 60)
    for model, data in all_results.items():
        print(
            f"{model:<15} {data['total_time']:<10.1f} {data['avg_transcribe']:<10.1f} {data['avg_llm']:<10.1f}"
        )
    print("-" * 60)

    # 每個測試檔案的 ICD-10 比較
    print("\n📋 各檔案 ICD-10 比較")
    print("-" * 60)
    for i, (filename, name) in enumerate(FILES):
        print(f"\n  {name}:")
        for model in MODELS:
            result = (
                all_results[model]["results"][i] if i < len(all_results[model]["results"]) else None
            )
            if result:
                icd10 = [c["code"] for c in result["icd10_codes"]]
                print(f"    {model:<15}: {icd10}")

    print(f"\n{'=' * 60}")
    print("✅ 測試完成!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
