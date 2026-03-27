#!/usr/bin/env python3
"""執行模型比較測試"""

import requests
import json
import time
from pathlib import Path

RESULTS_DIR = Path("tests/fixtures/results")

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

MODEL = "qwen2.5:14b"
OUTPUT_FILE = RESULTS_DIR / f"{MODEL.replace(':', '_')}_results_new.json"

results = []

for filename, name in FILES:
    print(f"\n=== 測試: {name} ({filename}) ===")

    # Step 1: Transcribe
    with open(f"static/{filename}", "rb") as f:
        files_dict = {"audio": (filename, f, "audio/wav")}
        r1 = requests.post(
            "http://localhost:8000/api/v1/extended/transcribe",
            files=files_dict,
            timeout=30,
        )

    if r1.status_code != 200:
        print(f"  [錯誤] 轉譯失敗: {r1.status_code}")
        continue

    data1 = r1.json()
    transcript = data1["transcript"]
    transcribe_time = data1.get("processing_time", 0)
    print(f"  轉譯: {transcript[:40]}...")

    # Step 2: Process with LLM
    start = time.time()
    r2 = requests.post(
        "http://localhost:8000/api/v1/extended/process",
        json={"transcript": transcript, "model": MODEL},
        timeout=120,
    )
    llm_time = time.time() - start

    if r2.status_code == 200:
        data2 = r2.json()
        result = {
            "name": name,
            "file": filename,
            "model": MODEL,
            "transcript": transcript,
            "transcribe_time": round(transcribe_time, 2),
            "llm_time": round(llm_time, 2),
            "total_time": round(transcribe_time + llm_time, 2),
            "symptoms": data2.get("symptoms", []),
            "icd10_codes": data2.get("icd10_codes", []),
            "drug_recommendations": data2.get("drug_recommendations", []),
            "medical_orders": data2.get("medical_orders", []),
            "soap": data2.get("soap", {}),
        }
        results.append(result)
        print(f"  症狀: {result['symptoms'][:3]}")
        print(f"  ICD-10: {[c['code'] for c in result['icd10_codes']]}")
    else:
        print(f"  [錯誤] LLM 處理失敗: {r2.status_code}")

# Save results
OUTPUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n=== 已儲存 {len(results)} 筆結果至 {OUTPUT_FILE} ===")
