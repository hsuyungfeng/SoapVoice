#!/usr/bin/env python3
"""Compare LLM models with detailed results"""

import json
import time
import httpx
from pathlib import Path
import sys
import os

API_BASE = "http://localhost:8000"
STATIC_DIR = Path("/home/hsu/Desktop/SoapVoice/static")

AUDIO_FILES = [
    ("chest_pain.wav", "胸痛"),
    ("hypertension.wav", "高血壓"),
    ("diabetes.wav", "糖尿病"),
    ("wound_care.wav", "傷口護理"),
    ("respiratory.wav", "呼吸道"),
    ("drug_order.wav", "醫囑"),
    ("surgery_record.wav", "手術記錄"),
    ("doctor_patient.wav", "醫病對話"),
]


def get_audio_info(file_path: str) -> tuple:
    import wave

    try:
        with wave.open(str(file_path), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            duration = round(frames / rate, 1)
            size = round(file_path.stat().st_size / 1024, 1)
            return duration, size
    except:
        return 0, 0


def format_symptoms(symptoms):
    """格式化症狀列表"""
    if not symptoms:
        return "無"
    return ", ".join([s if isinstance(s, str) else s.get("name", "") for s in symptoms])


def format_icd10(codes):
    """格式化 ICD-10"""
    if not codes:
        return "無"
    return " | ".join([f"{c.get('code', '')} - {c.get('description', '')}" for c in codes])


def format_drugs(drugs):
    """格式化藥物建議"""
    if not drugs:
        return "無"
    return " | ".join([f"{d.get('name', '')}: {d.get('dosage', '依醫囑')}" for d in drugs])


def format_orders(orders):
    """格式化醫囑"""
    if not orders:
        return "無"
    return " | ".join(orders)


def process_single(model: str, audio_file: str, name: str) -> dict:
    result = {
        "name": name,
        "file": audio_file,
        "model": model,
    }

    audio_path = STATIC_DIR / audio_file
    duration, size = get_audio_info(audio_path)
    result["audio_duration"] = duration
    result["audio_size"] = size

    start_time = time.time()

    try:
        # Transcribe
        with open(audio_path, "rb") as f:
            files = {"audio": (audio_file, f, "audio/wav")}
            resp = httpx.post(f"{API_BASE}/api/v1/extended/transcribe", files=files, timeout=180)

        if resp.status_code == 200:
            data = resp.json()
            result["transcript"] = data.get("transcript", "")
            result["transcribe_time"] = round(time.time() - start_time, 2)
            result["asr_model"] = "whisper"
        else:
            result["error"] = f"Transcribe failed: {resp.status_code}"
            result["total_time"] = round(time.time() - start_time, 2)
            return result

        if not result["transcript"]:
            result["error"] = "No transcript"
            result["total_time"] = round(time.time() - start_time, 2)
            return result

        # Generate SOAP
        llm_start = time.time()
        resp = httpx.post(
            f"{API_BASE}/api/v1/extended/process",
            json={"transcript": result["transcript"], "model": model, "output_lang": "en"},
            timeout=300,
        )

        if resp.status_code == 200:
            soap_data = resp.json()
            result["llm_time"] = round(time.time() - llm_start, 2)
            result["total_time"] = round(time.time() - start_time, 2)

            # 詳細結果
            result["symptoms"] = soap_data.get("symptoms", [])
            result["icd10_codes"] = soap_data.get("icd10_codes", [])
            result["drug_recommendations"] = soap_data.get("drug_recommendations", [])
            result["medical_orders"] = soap_data.get("medical_orders", [])
            result["soap"] = soap_data.get("soap", {})
        else:
            result["error"] = f"SOAP failed: {resp.status_code}"
            result["llm_time"] = 0
            result["total_time"] = round(time.time() - start_time, 2)
    except Exception as e:
        result["error"] = str(e)
        result["total_time"] = round(time.time() - start_time, 2)

    return result


def generate_result_text(r):
    """產生格式化的結果文字"""
    lines = []
    lines.append(
        f"⏱️ 總處理時間: {r.get('total_time', 0)}秒 | 🎤 ASR: {r.get('asr_model', 'whisper')} ({r.get('transcribe_time', 0)}秒) | 🧠 LLM: {r.get('model', '')} ({r.get('llm_time', 0)}秒)"
    )
    lines.append("")
    lines.append("📋 症狀分析")
    lines.append(format_symptoms(r.get("symptoms", [])))
    lines.append("")
    lines.append("🏥 ICD-10 診斷")
    lines.append(format_icd10(r.get("icd10_codes", [])))
    lines.append("")
    lines.append("💊 藥物建議")
    lines.append(format_drugs(r.get("drug_recommendations", [])))
    lines.append("")
    lines.append("📝 醫囑")
    lines.append(format_orders(r.get("medical_orders", [])))
    lines.append("")
    lines.append("📄 SOAP 病歷")
    lines.append(r.get("soap", {}).get("en", "無"))
    lines.append("")
    lines.append("─" * 50)
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_detailed.py <model>")
        print("Example: python compare_detailed.py qwen2.5:3b")
        sys.exit(1)

    model = sys.argv[1]
    results = []
    output_file = Path(
        f"/home/hsu/Desktop/SoapVoice/tests/fixtures/results/{model.replace(':', '_')}_results.json"
    )

    print(f"Testing model: {model}")
    print(f"Audio files: {len(AUDIO_FILES)}\n")

    for audio_file, name in AUDIO_FILES:
        print(f"Processing: {name}...", end=" ", flush=True)
        result = process_single(model, audio_file, name)
        results.append(result)

        if result.get("error"):
            print(f"❌ {result['error']}")
            print(f"   總時間: {result.get('total_time', 0)}秒")
        else:
            print(f"✅ {result['total_time']}秒")
            # 印出格式化的結果
            print(generate_result_text(result))

    # Save JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to: {output_file}")


if __name__ == "__main__":
    main()
